# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Graph-agnostic typed GNN for AC power-flow learning across many MultiCircuit models.

The goal of this module is to provide a base architecture for training one shared
GNN across a user-provided collection of VeraGrid ``MultiCircuit`` models.

This version is intentionally conservative:

- graph data is passed at runtime rather than stored as fixed model buffers
- one shared set of weights is used across all graphs
- training samples several graph windows per optimizer step
- heterogeneous graphs are handled explicitly one sample at a time

That design keeps graph size handling explicit and avoids hiding indexing bugs
behind early padding or packed batching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

import numpy as np
import torch
import torch.nn as nn
import VeraGridEngine as vg
import matplotlib.pyplot as plt
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

if TYPE_CHECKING:
    from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit


@dataclass(frozen=True)
class GraphSpec:
    """
    Runtime graph specification for one electrical network.

    :param from_bus: from-bus indices, shape ``(M,)``
    :param to_bus: to-bus indices, shape ``(M,)``
    :param r: branch resistance, shape ``(M,)``
    :param x: branch reactance, shape ``(M,)``
    :param b: branch total shunt susceptance, shape ``(M,)``
    :param tap: tap module, shape ``(M,)``
    :param shift: tap angle in radians, shape ``(M,)``
    :param g_shunt_bus: bus shunt conductance, shape ``(N,)``
    :param b_shunt_bus: bus shunt susceptance, shape ``(N,)``
    :param bus_type: bus type code, shape ``(N,)``
    :param n_bus: number of buses ``N``
    :param n_branch: number of branches ``M``
    """

    from_bus: torch.Tensor
    to_bus: torch.Tensor
    r: torch.Tensor
    x: torch.Tensor
    b: torch.Tensor
    tap: torch.Tensor
    shift: torch.Tensor
    g_shunt_bus: torch.Tensor
    b_shunt_bus: torch.Tensor
    bus_type: torch.Tensor
    n_bus: int
    n_branch: int

    def validate(self) -> None:
        """
        Validate graph tensor sizes and dtypes.

        :returns: ``None``
        """
        # Algorithmically, the graph is the invariant object shared by all time steps of one network.
        # If these tensors are malformed, every later message-passing and physics scatter/gather is wrong.
        # Topology indices must stay integer because they are used for indexed gathers/adds.
        if self.from_bus.dtype != torch.long or self.to_bus.dtype != torch.long:
            raise TypeError("from_bus and to_bus must be torch.long.")
        else:
            pass
        # Bus type drives masking logic inside the typed solver, so it must also stay integer-coded.
        if self.bus_type.dtype != torch.long:
            raise TypeError("bus_type must be torch.long.")
        else:
            pass

        # The solver assumes one coherent branch set. Mismatched lengths would mean the graph itself
        # is ambiguous, so there is no meaningful electrical problem to solve.
        # Validate that all branch-shaped tensors agree on the same branch count M.
        m: int = int(self.n_branch)
        n: int = int(self.n_bus)
        if int(self.from_bus.numel()) != m or int(self.to_bus.numel()) != m:
            raise ValueError("from_bus and to_bus must have length n_branch.")
        else:
            pass

        # Validate that all per-branch electrical parameters match the stored topology size.
        if int(self.r.numel()) != m or int(self.x.numel()) != m or int(self.b.numel()) != m:
            raise ValueError("r, x and b must have length n_branch.")
        else:
            pass
        if int(self.tap.numel()) != m or int(self.shift.numel()) != m:
            raise ValueError("tap and shift must have length n_branch.")
        else:
            pass
        if int(self.g_shunt_bus.numel()) != n or int(self.b_shunt_bus.numel()) != n:
            raise ValueError("bus shunt tensors must have length n_bus.")
        else:
            pass
        if int(self.bus_type.numel()) != n:
            raise ValueError("bus_type must have length n_bus.")
        else:
            pass

        # Message passing and branch-current assembly both use bus indices as direct addresses,
        # so they must point to valid buses inside [0, N).
        if int(torch.min(self.from_bus).item()) < 0 or int(torch.min(self.to_bus).item()) < 0:
            raise ValueError("Bus indices must be >= 0.")
        else:
            pass
        if int(torch.max(self.from_bus).item()) >= n or int(torch.max(self.to_bus).item()) >= n:
            raise ValueError("Bus indices must be < n_bus.")
        else:
            pass

    def to_runtime(self, device: torch.device, dtype: torch.dtype) -> GraphSpec:
        """
        Copy the graph to a runtime device and floating dtype.

        :param device: target device
        :param dtype: target floating dtype
        :returns: copied graph specification
        """
        # The graph is immutable, so moving it to a device means building a new runtime copy.
        copied_graph: GraphSpec = GraphSpec(
            from_bus=self.from_bus.to(device=device, dtype=torch.long),
            to_bus=self.to_bus.to(device=device, dtype=torch.long),
            r=self.r.to(device=device, dtype=dtype),
            x=self.x.to(device=device, dtype=dtype),
            b=self.b.to(device=device, dtype=dtype),
            tap=self.tap.to(device=device, dtype=dtype),
            shift=self.shift.to(device=device, dtype=dtype),
            g_shunt_bus=self.g_shunt_bus.to(device=device, dtype=dtype),
            b_shunt_bus=self.b_shunt_bus.to(device=device, dtype=dtype),
            bus_type=self.bus_type.to(device=device, dtype=torch.long),
            n_bus=int(self.n_bus),
            n_branch=int(self.n_branch),
        )
        return copied_graph


@dataclass(frozen=True)
class MultiGridDataset:
    """
    One time-series dataset tied to one graph.

    Global role in the training pipeline:

    - one ``MultiGridDataset`` corresponds to one VeraGrid file
    - the graph is fixed for that file
    - the tensors store the time-varying operating states on that fixed graph
    - training does not feed the whole time series at once
    - instead, training repeatedly samples windows from this object

    So the dataset is the bridge between:

    - a full solved VeraGrid time series
    - many smaller solver-training examples

    Conceptually:

    - ``graph`` says what network exists
    - ``vr_true`` / ``vi_true`` say what the solved voltages were over time
    - ``pinj`` / ``qinj`` say what operating point must be matched
    - ``branch_active`` says which branches were available at each time step
    - ``vref`` carries the explicit slack reference used by the solver

    :param name: dataset identifier, typically the file name
    :param graph: graph specification
    :param vr_true: real voltage target, shape ``(T, N)``
    :param vi_true: imaginary voltage target, shape ``(T, N)``
    :param vref: complex slack reference, shape ``(T, N)``
    :param vr_init: real initial voltage guess, shape ``(T, N)``
    :param vi_init: imaginary initial voltage guess, shape ``(T, N)``
    :param pinj: active power injection target, shape ``(T, N)``
    :param qinj: reactive power injection target, shape ``(T, N)``
    :param branch_active: branch active mask, shape ``(T, M)``
    :param time_array: original time axis, shape ``(T,)``
    :param unix_time: UNIX time in seconds, shape ``(T,)``
    :param time_features: temporal feature matrix, shape ``(T, 4)``
    :param n_time: number of time steps ``T``
    """

    name: str
    graph: GraphSpec
    vr_true: torch.Tensor
    vi_true: torch.Tensor
    vref: torch.Tensor
    vr_init: torch.Tensor
    vi_init: torch.Tensor
    pinj: torch.Tensor
    qinj: torch.Tensor
    branch_active: torch.Tensor
    time_array: np.ndarray
    unix_time: torch.Tensor
    time_features: torch.Tensor
    n_time: int

    def sample_window(self, window: int, rng: np.random.Generator) -> MultiGridWindow:
        """
        Sample one time window from this dataset.

        :param window: window length
        :param rng: random number generator
        :returns: sampled window
        """
        # Algorithmically, training on windows instead of full trajectories gives many more examples
        # per file and keeps memory bounded. The solver still sees temporal variation, but on short,
        # reusable operating segments.
        # We sample one contiguous time slice so the solver sees a local operating trajectory.
        window_int: int = int(window)
        if self.n_time < window_int:
            raise ValueError(f"Dataset {self.name} does not have enough time steps for window={window_int}.")
        else:
            pass
        # Snapshot datasets with T=1 are valid. In that case the only possible window is the full series.
        # More generally, if the requested window covers the full available time range, the start is forced to 0.
        # The start index is the only random part; the graph itself stays fixed for the full window.
        t0: int
        if self.n_time == window_int:
            t0 = 0
        else:
            t0 = int(rng.integers(0, self.n_time - window_int + 1))
        tw: slice = slice(t0, t0 + window_int)
        # This separation is the core data model:
        # - graph = fixed topology/parameters
        # - tensors = time-varying operating state on that graph
        # The sampled window keeps the original graph reference and slices only the time-varying tensors.
        window_sample: MultiGridWindow = MultiGridWindow(
            dataset_name=self.name,
            graph=self.graph,
            vr_true=self.vr_true[tw],
            vi_true=self.vi_true[tw],
            vref=self.vref[tw],
            vr_init=self.vr_init[tw],
            vi_init=self.vi_init[tw],
            pinj=self.pinj[tw],
            qinj=self.qinj[tw],
            branch_active=self.branch_active[tw],
            unix_time=self.unix_time[tw],
            time_features=self.time_features[tw],
        )
        return window_sample


@dataclass(frozen=True)
class MultiGridWindow:
    """
    One sampled window from one dataset.

    Global role in the training pipeline:

    - this is the actual object consumed by the solver during training
    - it contains one graph plus one short time slice on that graph
    - every optimizer step is built from several of these window objects

    The important idea is that the graph does not change inside a window,
    but the electrical state does change from row to row inside that window.

    :param dataset_name: source dataset name
    :param graph: graph specification
    :param vr_true: real voltage target, shape ``(Tw, N)``
    :param vi_true: imaginary voltage target, shape ``(Tw, N)``
    :param vref: complex slack reference, shape ``(Tw, N)``
    :param vr_init: real initial voltage guess, shape ``(Tw, N)``
    :param vi_init: imaginary initial voltage guess, shape ``(Tw, N)``
    :param pinj: active injections, shape ``(Tw, N)``
    :param qinj: reactive injections, shape ``(Tw, N)``
    :param branch_active: branch active mask, shape ``(Tw, M)``
    :param unix_time: UNIX time in seconds, shape ``(Tw,)``
    :param time_features: temporal feature matrix, shape ``(Tw, 4)``
    """

    dataset_name: str
    graph: GraphSpec
    vr_true: torch.Tensor
    vi_true: torch.Tensor
    vref: torch.Tensor
    vr_init: torch.Tensor
    vi_init: torch.Tensor
    pinj: torch.Tensor
    qinj: torch.Tensor
    branch_active: torch.Tensor
    unix_time: torch.Tensor
    time_features: torch.Tensor


@dataclass(frozen=True)
class PhysicsEvaluation:
    """
    Output of the AC physics evaluator.

    :param p_bus: bus active injections, shape ``(T, N)``
    :param q_bus: bus reactive injections, shape ``(T, N)``
    :param pf: from-end active flow, shape ``(T, M)``
    :param qf: from-end reactive flow, shape ``(T, M)``
    :param pt: to-end active flow, shape ``(T, M)``
    :param qt: to-end reactive flow, shape ``(T, M)``
    :param dp: active mismatch, shape ``(T, N)``, or ``None``
    :param dq: reactive mismatch, shape ``(T, N)``, or ``None``
    :param loss_mismatch: scalar mismatch loss, or ``None``
    """

    p_bus: torch.Tensor
    q_bus: torch.Tensor
    pf: torch.Tensor
    qf: torch.Tensor
    pt: torch.Tensor
    qt: torch.Tensor
    dp: Optional[torch.Tensor]
    dq: Optional[torch.Tensor]
    loss_mismatch: Optional[torch.Tensor]


@dataclass(frozen=True)
class SolverWindowResult:
    """
    Predicted voltage state for one window.

    :param vr_pred: predicted real voltage, shape ``(Tw, N)``
    :param vi_pred: predicted imaginary voltage, shape ``(Tw, N)``
    """

    vr_pred: torch.Tensor
    vi_pred: torch.Tensor


@dataclass(frozen=True)
class EvaluationMetrics:
    """
    Evaluation metrics for one held-out window.

    :param voltage_mse: Cartesian voltage mean-squared error
    :param voltage_magnitude_mse: voltage-magnitude mean-squared error
    :param pf_mismatch: power-flow mismatch mean-squared error
    :param branch_active_flow_mse: branch active-flow mean-squared error
    :param branch_reactive_flow_mse: branch reactive-flow mean-squared error
    """

    voltage_mse: float
    voltage_magnitude_mse: float
    pf_mismatch: float
    branch_active_flow_mse: float
    branch_reactive_flow_mse: float


@dataclass(frozen=True)
class EvaluationResult:
    """
    Full post-training evaluation result for one dataset window.

    :param metrics: scalar metrics for the evaluated window
    :param vr_pred: predicted real voltage, shape ``(Tw, N)``
    :param vi_pred: predicted imaginary voltage, shape ``(Tw, N)``
    :param physics_evaluation: physics evaluation on the predicted state
    :param start_idx: effective evaluation start index
    :param window: effective evaluation window length
    """

    metrics: EvaluationMetrics
    vr_pred: torch.Tensor
    vi_pred: torch.Tensor
    physics_evaluation: PhysicsEvaluation
    start_idx: int
    window: int


class StatelessAcPowerFlowPhysics(nn.Module):
    """
    AC physics evaluator that receives the graph at runtime.

    :param dtype: floating dtype for internal computations
    """

    def __init__(self, dtype: torch.dtype = torch.float32) -> None:
        super().__init__()
        self._dtype: torch.dtype = dtype
        # Small impedance floor used to avoid division by zero on pathological branch data.
        self.register_buffer("eps_z", torch.tensor(1e-12, dtype=dtype))

    def forward(
            self,
            graph: GraphSpec,
            vr: torch.Tensor,
            vi: torch.Tensor,
            branch_active: Optional[torch.Tensor],
            pinj_target: Optional[torch.Tensor] = None,
            qinj_target: Optional[torch.Tensor] = None,
    ) -> PhysicsEvaluation:
        """
        Evaluate AC power-flow equations for one graph and one voltage trajectory.

        :param graph: runtime graph specification
        :param vr: real voltage, shape ``(T, N)``
        :param vi: imaginary voltage, shape ``(T, N)``
        :param branch_active: branch active mask, shape ``(T, M)``, or ``None``
        :param pinj_target: active power target, shape ``(T, N)``, or ``None``
        :param qinj_target: reactive power target, shape ``(T, N)``, or ``None``
        :returns: physics evaluation struct
        """
        # Algorithmically, the physics block is not learned. It exists to tell the network whether a
        # proposed voltage state is electrically consistent for the current graph and injections.
        # The module is only a thin nn.Module wrapper so the actual physics stays in a typed function.
        evaluation: PhysicsEvaluation = evaluate_ac_power_flow(
            graph=graph,
            vr=vr,
            vi=vi,
            branch_active=branch_active,
            pinj_target=pinj_target,
            qinj_target=qinj_target,
            dtype=self._dtype,
            eps_z=self.eps_z,
        )
        return evaluation


class MLP(nn.Module):
    """
    Small helper MLP.

    :param in_dim: input feature dimension
    :param hidden_dim: hidden feature dimension
    :param out_dim: output feature dimension
    """

    def __init__(self, in_dim: int, hidden_dim: int, out_dim: int) -> None:
        super().__init__()
        # Small MLPs are used because the graph structure and physics already provide most of the prior.
        # The network only needs a compact learned correction mechanism, not a huge generic backbone.
        # Keep the learnable blocks small and explicit: encode -> nonlinearity -> project.
        self.net: nn.Sequential = nn.Sequential(
            nn.Linear(int(in_dim), int(hidden_dim)),
            nn.GELU(),
            nn.Linear(int(hidden_dim), int(out_dim)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply the MLP.

        :param x: input tensor
        :returns: output tensor
        """
        y: torch.Tensor = self.net(x)
        return y


class GeneralPurposeTypedGNNSolver(nn.Module):
    """
    Shared-weight typed GNN that receives the graph at runtime.

    :param embed_dim: embedding dimension
    :param msg_hidden: hidden width of message/update MLPs
    :param tgn_layers: number of unrolled solver layers
    :param msg_steps: message passing steps per layer
    :param dtype: floating dtype for the physics helper
    """

    def __init__(
            self,
            embed_dim: int = 64,
            msg_hidden: int = 128,
            tgn_layers: int = 6,
            msg_steps: int = 2,
            dtype: torch.dtype = torch.float32,
    ) -> None:
        super().__init__()
        self.embed_dim: int = int(embed_dim)
        self.msg_hidden: int = int(msg_hidden)
        self.tgn_layers: int = int(tgn_layers)
        self.msg_steps: int = int(msg_steps)
        self.dtype: torch.dtype = dtype
        self.temporal_in_dim: int = 10
        self.bus_in_dim: int = 17 + self.embed_dim
        self.temporal_gru: nn.GRU = nn.GRU(
            input_size=self.temporal_in_dim,
            hidden_size=self.embed_dim,
            num_layers=1,
            batch_first=True,
        )
        self.enc_bus: nn.Linear = nn.Linear(self.bus_in_dim, self.embed_dim)
        self.enc_branch: nn.Linear = nn.Linear(3, self.embed_dim)
        self.upd_branch: MLP = MLP(3 * self.embed_dim, self.msg_hidden, self.embed_dim)
        self.msg_br_to_bus: MLP = MLP(2 * self.embed_dim, self.msg_hidden, self.embed_dim)
        self.upd_bus: MLP = MLP(2 * self.embed_dim, self.msg_hidden, self.embed_dim)
        self.norm_branch: nn.LayerNorm = nn.LayerNorm(self.embed_dim)
        self.norm_bus: nn.LayerNorm = nn.LayerNorm(self.embed_dim)
        self.dec_dvr: MLP = MLP(self.embed_dim, self.msg_hidden, 1)
        self.dec_dvi: MLP = MLP(self.embed_dim, self.msg_hidden, 1)
        # Each unrolled layer behaves like one learned numerical iteration.
        # The learned step scale controls how aggressive each unrolled correction step is.
        self.step_scale: nn.Parameter = nn.Parameter(torch.tensor(0.05, dtype=torch.float32))

    def forward(
            self,
            graph: GraphSpec,
            pinj_tn: torch.Tensor,
            qinj_tn: torch.Tensor,
            branch_active_tm: torch.Tensor,
            vref_tn: Optional[torch.Tensor] = None,
            vr_init_tn: Optional[torch.Tensor] = None,
            vi_init_tn: Optional[torch.Tensor] = None,
            time_features_tk: Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Predict bus voltages for one graph window.

        :param graph: runtime graph specification
        :param pinj_tn: active power target, shape ``(T, N)``
        :param qinj_tn: reactive power target, shape ``(T, N)``
        :param branch_active_tm: branch active mask, shape ``(T, M)``
        :param vref_tn: complex slack reference, shape ``(T, N)``, or ``None``
        :param vr_init_tn: real initial voltage guess, shape ``(T, N)``, or ``None``
        :param vi_init_tn: imaginary initial voltage guess, shape ``(T, N)``, or ``None``
        :param time_features_tk: temporal feature matrix, shape ``(T, 4)``, or ``None``
        :returns: ``(vr_pred, vi_pred)``, each shaped ``(T, N)``
        """
        # Forward delegates to the typed window runner so the main logic is centralized.
        result: SolverWindowResult = self.run_window(
            graph=graph,
            pinj_tn=pinj_tn,
            qinj_tn=qinj_tn,
            branch_active_tm=branch_active_tm,
            vref_tn=vref_tn,
            vr_init_tn=vr_init_tn,
            vi_init_tn=vi_init_tn,
            time_features_tk=time_features_tk,
        )
        return result.vr_pred, result.vi_pred

    def run_window(
            self,
            graph: GraphSpec,
            pinj_tn: torch.Tensor,
            qinj_tn: torch.Tensor,
            branch_active_tm: torch.Tensor,
            vref_tn: Optional[torch.Tensor],
            vr_init_tn: Optional[torch.Tensor],
            vi_init_tn: Optional[torch.Tensor],
            time_features_tk: Optional[torch.Tensor],
    ) -> SolverWindowResult:
        """
        Run the shared solver on one graph window.

        :param graph: graph specification
        :param pinj_tn: active injections, shape ``(T, N)``
        :param qinj_tn: reactive injections, shape ``(T, N)``
        :param branch_active_tm: branch active mask, shape ``(T, M)``
        :param vref_tn: complex slack reference, or ``None``
        :param vr_init_tn: real initial voltage guess, or ``None``
        :param vi_init_tn: imaginary initial voltage guess, or ``None``
        :param time_features_tk: temporal feature matrix, or ``None``
        :returns: predicted voltage window
        """
        # The class owns the learned parameters, but the explicit solver loop stays external so the
        # algorithm is easy to inspect as a sequence of typed steps.
        result: SolverWindowResult = run_general_purpose_solver(
            solver=self,
            graph=graph,
            pinj_tn=pinj_tn,
            qinj_tn=qinj_tn,
            branch_active_tm=branch_active_tm,
            vref_tn=vref_tn,
            vr_init_tn=vr_init_tn,
            vi_init_tn=vi_init_tn,
            time_features_tk=time_features_tk,
        )
        return result

    def encode_temporal_context(
            self,
            pinj_tn: torch.Tensor,
            qinj_tn: torch.Tensor,
            vm_ref_tn: torch.Tensor,
            va_ref_tn: torch.Tensor,
            vr_init_tn: torch.Tensor,
            vi_init_tn: torch.Tensor,
            time_features_tk: torch.Tensor,
    ) -> torch.Tensor:
        """
        Encode temporal operating context for every bus with a GRU.

        :param pinj_tn: active injections, shape ``(T, N)``
        :param qinj_tn: reactive injections, shape ``(T, N)``
        :param vm_ref_tn: voltage-magnitude reference, shape ``(T, N)``
        :param va_ref_tn: voltage-angle reference, shape ``(T, N)``
        :param vr_init_tn: real initial voltage guess, shape ``(T, N)``
        :param vi_init_tn: imaginary initial voltage guess, shape ``(T, N)``
        :param time_features_tk: temporal feature matrix, shape ``(T, 4)``
        :returns: temporal embedding tensor shaped ``(T, N, D)``
        """
        # The temporal encoder sees each bus trajectory through time before spatial message passing begins.
        # This gives the model explicit memory of operating evolution instead of only one-step clock features.
        t_steps: int = int(pinj_tn.shape[0])
        n_bus: int = int(pinj_tn.shape[1])
        broadcast_time: torch.Tensor = time_features_tk[:, None, :].expand(t_steps, n_bus, 4)
        temporal_input: torch.Tensor = torch.cat(
            [
                pinj_tn[:, :, None].to(torch.float32),
                qinj_tn[:, :, None].to(torch.float32),
                vm_ref_tn[:, :, None],
                va_ref_tn[:, :, None],
                vr_init_tn[:, :, None],
                vi_init_tn[:, :, None],
                broadcast_time,
            ],
            dim=2,
        )
        temporal_input_btd: torch.Tensor = temporal_input.permute(1, 0, 2).contiguous()
        temporal_output_btd: torch.Tensor
        temporal_output_btd, _ = self.temporal_gru(temporal_input_btd)
        temporal_output: torch.Tensor = temporal_output_btd.permute(1, 0, 2).contiguous()
        return temporal_output

    def update_branch_embeddings(
            self,
            graph: GraphSpec,
            h_bus: torch.Tensor,
            h_branch: torch.Tensor,
            branch_active_tm: torch.Tensor,
    ) -> torch.Tensor:
        """
        Update branch embeddings from endpoint bus embeddings.

        :param graph: graph specification
        :param h_bus: bus embeddings
        :param h_branch: branch embeddings
        :param branch_active_tm: branch active mask
        :returns: updated branch embeddings
        """
        # Algorithmically, a branch should update from the state of its two endpoint buses.
        # This is the edge-update half of message passing on the electrical graph.
        # Gather endpoint embeddings for every branch and update the branch state from both ends.
        device: torch.device = h_bus.device
        from_bus: torch.Tensor = graph.from_bus.to(device=device)
        to_bus: torch.Tensor = graph.to_bus.to(device=device)
        h_f: torch.Tensor = h_bus[:, from_bus, :]
        h_t: torch.Tensor = h_bus[:, to_bus, :]
        x: torch.Tensor = torch.cat([h_branch, h_f, h_t], dim=2)
        new_h: torch.Tensor = self.upd_branch(x)
        # Inactive branches must emit no learned state, so we zero them here.
        active_mask: torch.Tensor = branch_active_tm[:, :, None].to(device=device, dtype=torch.float32)
        residual_branch: torch.Tensor = active_mask * new_h
        out: torch.Tensor = self.norm_branch(h_branch + residual_branch)
        return out

    def update_bus_embeddings(
            self,
            graph: GraphSpec,
            h_bus: torch.Tensor,
            h_branch: torch.Tensor,
            branch_active_tm: torch.Tensor,
    ) -> torch.Tensor:
        """
        Update bus embeddings from incident branch embeddings.

        :param graph: graph specification
        :param h_bus: bus embeddings
        :param h_branch: branch embeddings
        :param branch_active_tm: branch active mask
        :returns: updated bus embeddings
        """
        # Algorithmically, each bus needs information from all incident branches before deciding
        # its next voltage correction. That is why we aggregate branch messages back into buses.
        # Aggregate incident-branch messages back into buses with explicit topology-indexed sums.
        device: torch.device = h_bus.device
        t_steps: int = int(h_bus.shape[0])
        n_bus: int = int(graph.n_bus)
        dim_hidden: int = int(h_bus.shape[2])
        from_bus: torch.Tensor = graph.from_bus.to(device=device)
        to_bus: torch.Tensor = graph.to_bus.to(device=device)
        active_mask: torch.Tensor = branch_active_tm[:, :, None].to(device=device, dtype=torch.float32)
        h_f: torch.Tensor = h_bus[:, from_bus, :]
        h_t: torch.Tensor = h_bus[:, to_bus, :]
        msg_f: torch.Tensor = self.msg_br_to_bus(torch.cat([h_branch, h_f], dim=2)) * active_mask
        msg_t: torch.Tensor = self.msg_br_to_bus(torch.cat([h_branch, h_t], dim=2)) * active_mask
        agg: torch.Tensor = torch.zeros((t_steps, n_bus, dim_hidden), device=device, dtype=h_bus.dtype)
        agg.index_add_(1, from_bus, msg_f)
        agg.index_add_(1, to_bus, msg_t)
        # The bus updater mixes the previous bus embedding with the aggregated branch evidence.
        residual_bus: torch.Tensor = self.upd_bus(torch.cat([h_bus, agg], dim=2))
        out: torch.Tensor = self.norm_bus(h_bus + residual_bus)
        return out


def get_module_device(module: nn.Module) -> torch.device:
    """
    Return a device for a module, even if it has no parameters.

    :param module: torch module
    :returns: device where the module lives
    """
    # Prefer buffers first because some wrappers may have no parameters but still live on a device.
    try:
        device: torch.device = next(module.buffers()).device
    except StopIteration:
        try:
            device = next(module.parameters()).device
        except StopIteration:
            device = torch.device("cpu")
    return device


def as_complex(vr: torch.Tensor, vi: torch.Tensor) -> torch.Tensor:
    """
    Convert Cartesian tensors into a complex tensor.

    :param vr: real part
    :param vi: imaginary part
    :returns: complex tensor
    """
    value: torch.Tensor = torch.complex(vr, vi)
    return value


def complex_tap(tau: torch.Tensor, shift: torch.Tensor) -> torch.Tensor:
    """
    Compute the complex transformer tap.

    :param tau: tap module
    :param shift: tap angle in radians
    :returns: complex tap tensor
    """
    tap_value: torch.Tensor = torch.complex(tau * torch.cos(shift), tau * torch.sin(shift))
    return tap_value


def gauge_fix_cartesian(vr_tn: np.ndarray, vi_tn: np.ndarray, ref_bus: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Rotate each time step so the reference bus has zero angle.

    :param vr_tn: real voltage, shape ``(T, N)``
    :param vi_tn: imaginary voltage, shape ``(T, N)``
    :param ref_bus: reference bus index
    :returns: gauge-fixed real and imaginary voltages
    """
    # Algorithmically, global voltage angle is a gauge freedom. Removing it prevents the network
    # from wasting capacity on arbitrary global rotations that do not change the physical state.
    # Rotate every time step so the reference-bus angle becomes zero in the training frame.
    v: np.ndarray = vr_tn + 1j * vi_tn
    phi: np.ndarray = np.angle(v[:, int(ref_bus)])
    rot: np.ndarray = np.exp(-1j * phi)
    v2: np.ndarray = v * rot[:, None]
    vr_fixed: np.ndarray = np.real(v2).astype(np.float32)
    vi_fixed: np.ndarray = np.imag(v2).astype(np.float32)
    return vr_fixed, vi_fixed


def voltage_magnitude_loss(
        vr_pred: torch.Tensor,
        vi_pred: torch.Tensor,
        vr_true: torch.Tensor,
        vi_true: torch.Tensor,
) -> torch.Tensor:
    """
    Compute voltage-magnitude mean-squared error.

    :param vr_pred: predicted real voltage
    :param vi_pred: predicted imaginary voltage
    :param vr_true: target real voltage
    :param vi_true: target imaginary voltage
    :returns: scalar loss tensor
    """
    # Voltage magnitude is a stable supervised target across graphs and operating points.
    # It is less brittle than raw Cartesian components with respect to reference-frame effects.
    vm_pred: torch.Tensor = torch.sqrt(vr_pred * vr_pred + vi_pred * vi_pred + 1e-12)
    vm_true: torch.Tensor = torch.sqrt(vr_true * vr_true + vi_true * vi_true + 1e-12)
    loss_value: torch.Tensor = torch.mean((vm_pred - vm_true) ** 2)
    return loss_value


def voltage_cartesian_loss(
        vr_pred: torch.Tensor,
        vi_pred: torch.Tensor,
        vr_true: torch.Tensor,
        vi_true: torch.Tensor,
) -> torch.Tensor:
    """
    Compute Cartesian voltage mean-squared error.

    :param vr_pred: predicted real voltage
    :param vi_pred: predicted imaginary voltage
    :param vr_true: target real voltage
    :param vi_true: target imaginary voltage
    :returns: scalar loss tensor
    """
    # Cartesian supervision directly matches the voltage error metric later reported in evaluation.
    # This removes the mismatch where magnitude improves but phase-related RMS error remains large.
    loss_value: torch.Tensor = torch.mean((vr_pred - vr_true) ** 2 + (vi_pred - vi_true) ** 2)
    return loss_value


def build_time_features_from_unix_time(unix_time_seconds: np.ndarray) -> np.ndarray:
    """
    Build temporal features from UNIX timestamps.

    :param unix_time_seconds: UNIX timestamps in seconds, shape ``(T,)``
    :returns: temporal feature matrix shaped ``(T, 4)``
    """
    # The GNN already models spatial correlation through message passing.
    # UNIX time-derived features expose temporal correlation explicitly without changing graph topology handling.
    unix_time_float: np.ndarray = np.asarray(unix_time_seconds, dtype=np.float64)
    if int(unix_time_float.size) == 0:
        raise ValueError("Temporal feature construction requires at least one UNIX timestamp.")
    else:
        pass

    elapsed_hours: np.ndarray = (unix_time_float - unix_time_float[0]) / 3600.0
    delta_hours: np.ndarray = np.r_[0.0, np.diff(unix_time_float) / 3600.0]
    seconds_per_day: float = 86400.0
    daily_angle: np.ndarray = 2.0 * np.pi * np.mod(unix_time_float, seconds_per_day) / seconds_per_day
    scale_hours: float = float(max(1.0, np.max(np.abs(elapsed_hours))))
    elapsed_hours_normalized: np.ndarray = elapsed_hours / scale_hours

    features: np.ndarray = np.column_stack(
        (
            elapsed_hours_normalized.astype(np.float32),
            delta_hours.astype(np.float32),
            np.sin(daily_angle).astype(np.float32),
            np.cos(daily_angle).astype(np.float32),
        )
    )
    return features


def map_veragrid_bus_types(bus_types: np.ndarray) -> np.ndarray:
    """
    Map VeraGrid bus type codes into the clean-room convention.

    :param bus_types: VeraGrid bus type array
    :returns: clean-room bus type array
    """
    # Algorithmically, the solver only needs the behavioral categories that matter for PF:
    # slack, PV-like and PQ-like. Everything else is reduced into that control taxonomy.
    # The shared solver only understands the reduced clean-room bus taxonomy.
    out: np.ndarray = np.full(bus_types.shape, fill_value=-1, dtype=np.int64)
    out[bus_types == 3] = 0
    out[np.isin(bus_types, np.array([2, 4, 5], dtype=bus_types.dtype))] = 1
    out[bus_types == 1] = 2
    bad: np.ndarray = np.where(out < 0)[0]
    if bad.size > 0:
        bad_vals: np.ndarray = np.unique(bus_types[bad])
        raise ValueError(f"Unsupported VeraGrid bus type codes: {bad_vals.tolist()}")
    else:
        pass
    return out


def finite_row_mask_complex(x: np.ndarray) -> np.ndarray:
    """
    Return a row mask whose rows are finite in real and imaginary parts.

    :param x: complex array shaped ``(T, K)``
    :returns: boolean mask shaped ``(T,)``
    """
    mask: np.ndarray = np.isfinite(x.real).all(axis=1) & np.isfinite(x.imag).all(axis=1)
    return mask


def validate_graph_spec(graph: GraphSpec) -> None:
    """
    Validate graph tensor sizes and dtypes.

    :param graph: graph specification
    :returns: ``None``
    """
    graph.validate()


def graph_spec_to_device(graph: GraphSpec, device: torch.device, dtype: torch.dtype) -> GraphSpec:
    """
    Copy a graph specification to a device and floating dtype.

    :param graph: input graph
    :param device: target device
    :param dtype: target floating dtype
    :returns: copied graph spec
    """
    copied_graph: GraphSpec = graph.to_runtime(device=device, dtype=dtype)
    return copied_graph


def validate_clean_room_compatibility(nc: "NumericalCircuit") -> None:
    """
    Validate that a numerical circuit only uses features represented by this model.

    :param nc: compiled numerical circuit
    :returns: ``None``
    """
    pbd = nc.passive_branch_data
    abd = nc.active_branch_data

    if np.any(np.asarray(pbd.dc) != 0):
        raise ValueError("The clean-room AC physics does not support DC branches.")
    else:
        pass
    if np.any(np.abs(np.asarray(pbd.G)) > 1e-12):
        raise ValueError("The clean-room AC physics does not support branch conductance shunts (G != 0).")
    else:
        pass
    if np.any(np.abs(np.asarray(pbd.virtual_tap_f) - 1.0) > 1e-12):
        raise ValueError("The clean-room AC physics does not support non-unit VeraGrid virtual_tap_f.")
    else:
        pass
    if np.any(np.abs(np.asarray(pbd.virtual_tap_t) - 1.0) > 1e-12):
        raise ValueError("The clean-room AC physics does not support non-unit VeraGrid virtual_tap_t.")
    else:
        pass
    if np.any(np.asarray(abd.tap_module) <= 0.0):
        raise ValueError("All branch tap modules must be strictly positive.")
    else:
        pass


def evaluate_ac_power_flow(
        graph: GraphSpec,
        vr: torch.Tensor,
        vi: torch.Tensor,
        branch_active: Optional[torch.Tensor],
        pinj_target: Optional[torch.Tensor],
        qinj_target: Optional[torch.Tensor],
        dtype: torch.dtype,
        eps_z: torch.Tensor,
) -> PhysicsEvaluation:
    """
    Evaluate AC power-flow equations for one graph and one trajectory.

    :param graph: graph specification
    :param vr: real voltage, shape ``(T, N)``
    :param vi: imaginary voltage, shape ``(T, N)``
    :param branch_active: branch mask, shape ``(T, M)``, or ``None``
    :param pinj_target: active power target, or ``None``
    :param qinj_target: reactive power target, or ``None``
    :param dtype: internal floating dtype
    :param eps_z: impedance floor tensor
    :returns: physics evaluation
    """
    # Algorithmically, this function is the fixed electrical oracle used by the learned solver.
    # It maps a candidate voltage trajectory into injections and flows on the current graph.
    # Validate once at the top because every later gather/add assumes the graph is internally consistent.
    validate_graph_spec(graph=graph)

    if vr.shape != vi.shape:
        raise ValueError("vr and vi must have the same shape.")
    else:
        pass
    if vr.ndim != 2:
        raise ValueError("This module expects 2D tensors shaped (T,N).")
    else:
        pass
    if int(vr.shape[1]) != int(graph.n_bus):
        raise ValueError("vr and vi last dimension must equal graph.n_bus.")
    else:
        pass

    t_steps: int = int(vr.shape[0])
    n_bus: int = int(graph.n_bus)
    n_branch: int = int(graph.n_branch)
    device: torch.device = vr.device
    # The same graph may be reused many times, but each call needs a runtime copy living on the
    # active device and dtype so vectorized electrical operations can run without implicit casts.
    # Convert the immutable graph struct into a runtime copy on the active device/dtype.
    runtime_graph: GraphSpec = graph_spec_to_device(graph=graph, device=device, dtype=dtype)

    branch_active_local: torch.Tensor
    if branch_active is None:
        # If no explicit branch mask is provided, we assume all branches are in service.
        branch_active_local = torch.ones((t_steps, n_branch), device=device, dtype=torch.float32)
    else:
        if branch_active.shape != (t_steps, n_branch):
            raise ValueError("branch_active must be shaped (T,M).")
        else:
            branch_active_local = branch_active.to(device=device, dtype=torch.float32)

    # AC branch equations are naturally expressed with complex voltages, currents and powers.
    # Convert Cartesian state into complex form because the AC equations are cleaner there.
    v: torch.Tensor = as_complex(vr.to(dtype), vi.to(dtype))
    complex_dtype: torch.dtype
    if dtype == torch.float32:
        complex_dtype = torch.complex64
    else:
        complex_dtype = torch.complex128

    # These arrays are the physical outputs of interest: bus injections and branch-end flows.
    # Preallocate all outputs so the branch sweep only fills values instead of growing objects.
    ibus: torch.Tensor = torch.zeros((t_steps, n_bus), device=device, dtype=complex_dtype)
    pf: torch.Tensor = torch.zeros((t_steps, n_branch), device=device, dtype=dtype)
    qf: torch.Tensor = torch.zeros((t_steps, n_branch), device=device, dtype=dtype)
    pt: torch.Tensor = torch.zeros((t_steps, n_branch), device=device, dtype=dtype)
    qt: torch.Tensor = torch.zeros((t_steps, n_branch), device=device, dtype=dtype)

    # Algorithmically, branch admittance is the local physics primitive that connects bus voltages
    # to branch currents. Taps modify that relation, so both are assembled here before evaluation.
    # Build branch admittances and transformer taps once for the full graph.
    tau_safe: torch.Tensor = torch.where(runtime_graph.tap > 0.0, runtime_graph.tap, torch.ones_like(runtime_graph.tap))
    tap: torch.Tensor = complex_tap(tau=tau_safe, shift=runtime_graph.shift)

    z: torch.Tensor = torch.complex(runtime_graph.r, runtime_graph.x)
    z_abs: torch.Tensor = torch.abs(z)
    z_safe: torch.Tensor = torch.where(z_abs > eps_z, z, torch.complex(eps_z, torch.zeros_like(eps_z)))
    y: torch.Tensor = 1.0 / z_safe
    ysh_total: torch.Tensor = torch.complex(torch.zeros_like(runtime_graph.b), runtime_graph.b)

    # An outage is modeled by zeroing the corresponding branch contribution in the admittance model.
    # Branch activity acts as a multiplicative mask on the branch admittance model.
    a_c: torch.Tensor = torch.complex(branch_active_local.to(dtype), torch.zeros_like(branch_active_local.to(dtype)))
    y_k: torch.Tensor = y[None, :] * a_c
    ysh_k: torch.Tensor = ysh_total[None, :] * a_c
    tap_k: torch.Tensor = tap[None, :]

    tap_abs2: torch.Tensor = tap_k * torch.conj(tap_k)
    ysh_half: torch.Tensor = 0.5 * ysh_k
    yff: torch.Tensor = (y_k + ysh_half) / tap_abs2
    yft: torch.Tensor = -y_k / torch.conj(tap_k)
    ytf: torch.Tensor = -y_k / tap_k
    ytt: torch.Tensor = y_k + ysh_half

    # This is the core electrical evaluation step:
    # endpoint voltages -> branch currents -> branch complex powers.
    # Gather endpoint voltages and evaluate branch currents and powers in vectorized form.
    vf: torch.Tensor = v[:, runtime_graph.from_bus]
    vt: torch.Tensor = v[:, runtime_graph.to_bus]
    i_f: torch.Tensor = yff * vf + yft * vt
    i_t: torch.Tensor = ytf * vf + ytt * vt
    s_f: torch.Tensor = vf * torch.conj(i_f)
    s_t: torch.Tensor = vt * torch.conj(i_t)

    pf[:, :] = s_f.real.to(dtype)
    qf[:, :] = s_f.imag.to(dtype)
    pt[:, :] = s_t.real.to(dtype)
    qt[:, :] = s_t.imag.to(dtype)

    # Bus injections are recovered by summing all incident branch currents plus bus shunts.
    # Scatter branch currents back to buses to recover bus injection currents.
    ibus.index_add_(1, runtime_graph.from_bus, i_f)
    ibus.index_add_(1, runtime_graph.to_bus, i_t)

    ysh_bus: torch.Tensor = torch.complex(runtime_graph.g_shunt_bus, runtime_graph.b_shunt_bus)
    ibus = ibus + v * ysh_bus[None, :]
    sbus: torch.Tensor = v * torch.conj(ibus)
    p_bus: torch.Tensor = sbus.real.to(dtype)
    q_bus: torch.Tensor = sbus.imag.to(dtype)

    # During training, the solver is driven by mismatch between calculated injections and requested
    # injections. During plain evaluation, we sometimes only need flows and bus injections.
    # Mismatch terms are optional because the same evaluator is used for both pure physics and training loss.
    dp: Optional[torch.Tensor] = None
    dq: Optional[torch.Tensor] = None
    loss_mismatch: Optional[torch.Tensor] = None
    if pinj_target is None and qinj_target is None:
        pass
    else:
        if pinj_target is None or qinj_target is None:
            raise ValueError("Provide both pinj_target and qinj_target, or neither.")
        else:
            if pinj_target.shape != (t_steps, n_bus) or qinj_target.shape != (t_steps, n_bus):
                raise ValueError("pinj_target and qinj_target must be shaped (T,N).")
            else:
                dp = p_bus - pinj_target.to(device=device, dtype=dtype)
                dq = q_bus - qinj_target.to(device=device, dtype=dtype)
                loss_mismatch = (dp * dp + dq * dq).mean()

    evaluation: PhysicsEvaluation = PhysicsEvaluation(
        p_bus=p_bus,
        q_bus=q_bus,
        pf=pf,
        qf=qf,
        pt=pt,
        qt=qt,
        dp=dp,
        dq=dq,
        loss_mismatch=loss_mismatch,
    )
    return evaluation


def build_branch_features(graph: GraphSpec, device: torch.device) -> torch.Tensor:
    """
    Build branch features used by the GNN encoder.

    :param graph: graph specification
    :param device: runtime device
    :returns: branch feature tensor shaped ``(M, 3)``
    """
    # Algorithmically, the GNN should start from physical edge descriptors rather than arbitrary
    # branch identities, otherwise it will memorize graphs instead of learning transferable behavior.
    # Edge features are derived from physical branch parameters rather than arbitrary IDs.
    runtime_graph: GraphSpec = graph_spec_to_device(graph=graph, device=device, dtype=torch.float32)
    rho: torch.Tensor = 1.0 / torch.sqrt(runtime_graph.r * runtime_graph.r + runtime_graph.x * runtime_graph.x + 1e-12)
    delta: torch.Tensor = -torch.atan2(runtime_graph.x, runtime_graph.r + 1e-12)
    branch_feat: torch.Tensor = torch.stack([rho, delta, runtime_graph.b], dim=1)
    return branch_feat


def build_bus_type_masks(graph: GraphSpec, device: torch.device) -> tuple[
    torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Build slack, PV, PQ and non-slack masks.

    :param graph: graph specification
    :param device: runtime device
    :returns: ``(slack, pv, pq, non_slack)``
    """
    # Typed PF behavior is not optional: slack, PV and PQ buses obey different update constraints.
    # These masks drive the typed solver behavior for slack, PV and PQ buses.
    bus_type: torch.Tensor = graph.bus_type.to(device=device)
    slack: torch.Tensor = (bus_type == 0).to(torch.float32)
    pv: torch.Tensor = (bus_type == 1).to(torch.float32)
    pq: torch.Tensor = (bus_type == 2).to(torch.float32)
    non_slack: torch.Tensor = (bus_type != 0).to(torch.float32)
    return slack, pv, pq, non_slack


def build_reference_features(
        vref_tn: Optional[torch.Tensor],
        t_steps: int,
        n_bus: int,
        device: torch.device,
) -> tuple[Optional[torch.Tensor], Optional[torch.Tensor], torch.Tensor, torch.Tensor]:
    """
    Build voltage reference tensors.

    :param vref_tn: optional complex reference, shape ``(T, N)``
    :param t_steps: number of time steps
    :param n_bus: number of buses
    :param device: runtime device
    :returns: ``(vr_ref, vi_ref, vm_ref, va_ref)``
    """
    # Algorithmically, prescribed voltages are prior information, not prediction targets.
    # The reference tensor only anchors prescribed buses; the rest of the network is solved by the GNN.
    vr_ref: Optional[torch.Tensor] = None
    vi_ref: Optional[torch.Tensor] = None
    vm_ref: torch.Tensor = torch.zeros((t_steps, n_bus), device=device, dtype=torch.float32)
    va_ref: torch.Tensor = torch.zeros((t_steps, n_bus), device=device, dtype=torch.float32)
    if vref_tn is None:
        pass
    else:
        if vref_tn.shape != (t_steps, n_bus):
            raise ValueError("vref_tn must be shaped (T,N).")
        else:
            vref_local: torch.Tensor = vref_tn.to(device=device)
            vr_ref = vref_local.real.to(torch.float32)
            vi_ref = vref_local.imag.to(torch.float32)
            vm_ref = torch.sqrt(vr_ref * vr_ref + vi_ref * vi_ref + 1e-12)
            va_ref = torch.atan2(vi_ref, vr_ref)
    return vr_ref, vi_ref, vm_ref, va_ref


def build_temporal_bus_features(
        time_features_tk: Optional[torch.Tensor],
        t_steps: int,
        n_bus: int,
        device: torch.device,
) -> torch.Tensor:
    """
    Build per-bus temporal feature tensors from window time features.

    :param time_features_tk: temporal feature matrix, shape ``(T, 4)``, or ``None``
    :param t_steps: number of time steps
    :param n_bus: number of buses
    :param device: runtime device
    :returns: temporal feature tensor shaped ``(T, N, 4)``
    """
    # Time is global to the operating point, so the same temporal descriptor is broadcast to every bus.
    # This lets the model couple graph structure with operating-time context during message passing.
    base_features: torch.Tensor
    if time_features_tk is None:
        base_features = torch.zeros((t_steps, 4), device=device, dtype=torch.float32)
    else:
        if time_features_tk.shape != (t_steps, 4):
            raise ValueError("time_features_tk must be shaped (T,4).")
        else:
            base_features = time_features_tk.to(device=device, dtype=torch.float32)
    temporal_bus_features: torch.Tensor = base_features[:, None, :].expand(t_steps, n_bus, 4)
    return temporal_bus_features


def run_general_purpose_solver(
        solver: GeneralPurposeTypedGNNSolver,
        graph: GraphSpec,
        pinj_tn: torch.Tensor,
        qinj_tn: torch.Tensor,
        branch_active_tm: torch.Tensor,
        vref_tn: Optional[torch.Tensor],
        vr_init_tn: Optional[torch.Tensor],
        vi_init_tn: Optional[torch.Tensor],
        time_features_tk: Optional[torch.Tensor],
) -> SolverWindowResult:
    """
    Run the shared-weight solver on one graph window.

    :param solver: solver module
    :param graph: graph specification
    :param pinj_tn: active injections, shape ``(T, N)``
    :param qinj_tn: reactive injections, shape ``(T, N)``
    :param branch_active_tm: branch active mask, shape ``(T, M)``
    :param vref_tn: complex slack reference, shape ``(T, N)``, or ``None``
    :param vr_init_tn: real initial voltage guess, shape ``(T, N)``, or ``None``
    :param vi_init_tn: imaginary initial voltage guess, shape ``(T, N)``, or ``None``
    :param time_features_tk: temporal feature matrix, shape ``(T, 4)``, or ``None``
    :returns: solver voltage prediction
    """
    # Algorithmically, this is the learned iterative solver:
    # injections + graph + branch state + reference -> voltage trajectory.
    # The solver is graph-agnostic, so every call starts by validating the runtime graph contract.
    validate_graph_spec(graph=graph)

    if pinj_tn.shape != qinj_tn.shape:
        raise ValueError("pinj_tn and qinj_tn must have the same shape.")
    else:
        pass
    if pinj_tn.ndim != 2:
        raise ValueError("This module expects 2D tensors shaped (T,N).")
    else:
        pass
    if pinj_tn.shape[1] != graph.n_bus:
        raise ValueError("pinj_tn and qinj_tn must use the graph bus dimension.")
    else:
        pass
    if branch_active_tm.shape != (pinj_tn.shape[0], graph.n_branch):
        raise ValueError("branch_active_tm must be shaped (T,M) for the graph.")
    else:
        pass

    device: torch.device = pinj_tn.device
    t_steps: int = int(pinj_tn.shape[0])
    n_bus: int = int(graph.n_bus)
    n_branch: int = int(graph.n_branch)
    # Every learned iteration is closed by a fixed physics evaluation.
    # That is what makes this a learned solver rather than a pure feedforward regressor.
    # This local physics module evaluates the current electrical state after each learned correction step.
    physics_module: StatelessAcPowerFlowPhysics = StatelessAcPowerFlowPhysics(dtype=solver.dtype).to(device)

    slack: torch.Tensor
    pv: torch.Tensor
    pq: torch.Tensor
    non_slack: torch.Tensor
    # Bus-type masks implement the typed behavior of the solver.
    slack, pv, pq, non_slack = build_bus_type_masks(graph=graph, device=device)

    # The solver starts from VeraGrid's compiled Vbus guess rather than a flat profile.
    # Learning a correction around a physically meaningful initialization is easier than solving from scratch.
    vr_init_local: torch.Tensor
    vi_init_local: torch.Tensor
    if vr_init_tn is None or vi_init_tn is None:
        vr_init_local = torch.ones((t_steps, n_bus), device=device, dtype=torch.float32)
        vi_init_local = torch.zeros((t_steps, n_bus), device=device, dtype=torch.float32)
    else:
        if vr_init_tn.shape != (t_steps, n_bus) or vi_init_tn.shape != (t_steps, n_bus):
            raise ValueError("vr_init_tn and vi_init_tn must be shaped (T,N).")
        else:
            vr_init_local = vr_init_tn.to(device=device, dtype=torch.float32)
            vi_init_local = vi_init_tn.to(device=device, dtype=torch.float32)
    vr: torch.Tensor = vr_init_local.clone()
    vi: torch.Tensor = vi_init_local.clone()

    vr_ref: Optional[torch.Tensor]
    vi_ref: Optional[torch.Tensor]
    vm_ref: torch.Tensor
    va_ref: torch.Tensor
    vr_ref, vi_ref, vm_ref, va_ref = build_reference_features(
        vref_tn=vref_tn,
        t_steps=t_steps,
        n_bus=n_bus,
        device=device,
    )
    temporal_bus_features: torch.Tensor = build_temporal_bus_features(
        time_features_tk=time_features_tk,
        t_steps=t_steps,
        n_bus=n_bus,
        device=device,
    )
    temporal_hidden: torch.Tensor = solver.encode_temporal_context(
        pinj_tn=pinj_tn,
        qinj_tn=qinj_tn,
        vm_ref_tn=vm_ref,
        va_ref_tn=va_ref,
        vr_init_tn=vr_init_local,
        vi_init_tn=vi_init_local,
        time_features_tk=temporal_bus_features[:, 0, :],
    )
    if vr_ref is None or vi_ref is None:
        pass
    else:
        vr = vr * non_slack[None, :] + vr_ref * slack[None, :]
        vi = vi * non_slack[None, :] + vi_ref * slack[None, :]

    # Branch embeddings are static within one graph window because the branch parameters do not
    # change from row to row inside the sampled window.
    # Encode one static branch embedding base for this graph from physical branch features.
    branch_feat: torch.Tensor = build_branch_features(graph=graph, device=device)
    h_branch0: torch.Tensor = solver.enc_branch(branch_feat)
    h_branch: torch.Tensor = h_branch0[None, :, :].expand(t_steps, n_branch, -1).contiguous()
    # Bus type enters as one-hot context in the bus feature tensor at every unrolled step.
    type_oh: torch.Tensor = torch.stack([slack, pv, pq], dim=1)[None, :, :].expand(t_steps, n_bus, 3)

    layer_idx: int
    for layer_idx in range(solver.tgn_layers):
        _ = layer_idx
        # Step 1 of each learned iteration:
        # evaluate the current state with exact physics to know what is still wrong.
        # First evaluate the current voltage state against the AC equations.
        physics_eval: PhysicsEvaluation = physics_module(
            graph=graph,
            vr=vr,
            vi=vi,
            branch_active=branch_active_tm,
            pinj_target=None,
            qinj_target=None,
        )
        p_calc: torch.Tensor = physics_eval.p_bus
        q_calc: torch.Tensor = physics_eval.q_bus
        # Step 2:
        # translate electrical inconsistency into mismatch signals that the GNN can act on.
        # Convert the physics result into the mismatch signals that drive the next learned correction.
        d_p: torch.Tensor = (pinj_tn - p_calc).to(torch.float32) * non_slack[None, :]
        d_q: torch.Tensor = (qinj_tn - q_calc).to(torch.float32) * pq[None, :]

        # Step 3:
        # assemble the local information each bus needs before message passing.
        # Build the full bus feature tensor from state, mismatch, targets, references and bus type.
        bus_feat: torch.Tensor = torch.cat(
            [
                vr[:, :, None],
                vi[:, :, None],
                d_p[:, :, None],
                d_q[:, :, None],
                pinj_tn.to(torch.float32)[:, :, None],
                qinj_tn.to(torch.float32)[:, :, None],
                vm_ref[:, :, None],
                va_ref[:, :, None],
                vr_init_local[:, :, None],
                vi_init_local[:, :, None],
                temporal_bus_features,
                type_oh,
                temporal_hidden,
            ],
            dim=2,
        )
        h_bus: torch.Tensor = solver.enc_bus(bus_feat)

        msg_step_idx: int
        for msg_step_idx in range(solver.msg_steps):
            _ = msg_step_idx
            # Step 4:
            # propagate local information across the network so each bus can react to remote structure too.
            # Alternate edge and node updates so information propagates across the electrical graph.
            h_branch = solver.update_branch_embeddings(
                graph=graph,
                h_bus=h_bus,
                h_branch=h_branch,
                branch_active_tm=branch_active_tm,
            )
            h_bus = solver.update_bus_embeddings(
                graph=graph,
                h_bus=h_bus,
                h_branch=h_branch,
                branch_active_tm=branch_active_tm,
            )

        # Step 5:
        # decode the aggregated graph information into the next voltage correction.
        # Decode the learned bus embedding back into a voltage correction in Cartesian coordinates.
        dvr: torch.Tensor = torch.tanh(solver.dec_dvr(h_bus).squeeze(2)) * non_slack[None, :]
        dvi: torch.Tensor = torch.tanh(solver.dec_dvi(h_bus).squeeze(2)) * non_slack[None, :]
        vr = vr + solver.step_scale * dvr
        vi = vi + solver.step_scale * dvi

        # Step 6:
        # keep prescribed buses prescribed, otherwise the learned updates would violate PF bus semantics.
        # Re-apply the reference anchor so slack buses remain prescribed across all unrolled steps.
        if vr_ref is None or vi_ref is None:
            pass
        else:
            vr = vr * non_slack[None, :] + vr_ref * slack[None, :]
            vi = vi * non_slack[None, :] + vi_ref * slack[None, :]

    result: SolverWindowResult = SolverWindowResult(vr_pred=vr, vi_pred=vi)
    return result


def build_graph_spec_from_multicircuit(grid: "MultiCircuit", t_idx: int = 0) -> GraphSpec:
    """
    Compile one VeraGrid snapshot into a graph specification.

    :param grid: VeraGrid multi-circuit model
    :param t_idx: time index to compile
    :returns: graph specification
    """
    # Compile one numerical snapshot because the graph definition comes from VeraGrid, not from learned IDs.
    nc: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, t_idx=t_idx)
    validate_clean_room_compatibility(nc=nc)
    y_shunt_bus: np.ndarray = nc.get_Yshunt_bus_pu()
    bus_type: np.ndarray = map_veragrid_bus_types(np.asarray(nc.bus_data.bus_types))
    # Materialize the compiled electrical graph into the runtime graph struct expected by the solver.
    graph: GraphSpec = GraphSpec(
        from_bus=torch.tensor(np.asarray(nc.passive_branch_data.F), dtype=torch.long),
        to_bus=torch.tensor(np.asarray(nc.passive_branch_data.T), dtype=torch.long),
        r=torch.tensor(np.asarray(nc.passive_branch_data.R), dtype=torch.float32),
        x=torch.tensor(np.asarray(nc.passive_branch_data.X), dtype=torch.float32),
        b=torch.tensor(np.asarray(nc.passive_branch_data.B), dtype=torch.float32),
        tap=torch.tensor(np.asarray(nc.active_branch_data.tap_module), dtype=torch.float32),
        shift=torch.tensor(np.asarray(nc.active_branch_data.tap_angle), dtype=torch.float32),
        g_shunt_bus=torch.tensor(np.real(y_shunt_bus), dtype=torch.float32),
        b_shunt_bus=torch.tensor(np.imag(y_shunt_bus), dtype=torch.float32),
        bus_type=torch.tensor(bus_type, dtype=torch.long),
        n_bus=int(nc.nbus),
        n_branch=int(np.asarray(nc.passive_branch_data.F).shape[0]),
    )
    validate_graph_spec(graph=graph)
    return graph


def extract_branch_active_matrix(grid: "MultiCircuit", n_time: int) -> np.ndarray:
    """
    Compile branch active states for every time step.

    :param grid: VeraGrid multi-circuit model
    :param n_time: number of time steps
    :returns: branch active matrix shaped ``(T, M)``
    """
    n_time_int: int = int(n_time)
    if n_time_int < 1:
        raise ValueError("Cannot extract branch active states from an empty time axis.")
    else:
        pass

    # Compile the first time step once to determine the fixed branch count and allocate the full matrix.
    nc_0: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, t_idx=0)
    n_branch: int = int(np.asarray(nc_0.passive_branch_data.active).shape[0])
    out: np.ndarray = np.empty((n_time_int, n_branch), dtype=np.float32)

    t_idx: int
    for t_idx in range(n_time_int):
        nc_t: NumericalCircuit
        if t_idx == 0:
            nc_t = nc_0
        else:
            nc_t = compile_numerical_circuit_at(circuit=grid, t_idx=t_idx)
        # Each row stores the branch in-service mask for one time step.
        row: np.ndarray = np.asarray(nc_t.passive_branch_data.active, dtype=np.float32)
        if int(row.shape[0]) != n_branch:
            raise ValueError("Branch count changed across time.")
        else:
            out[t_idx, :] = row
    return out


def extract_vbus_guess_matrix(grid: "MultiCircuit", n_time: int) -> np.ndarray:
    """
    Compile bus voltage guesses for every time step.

    :param grid: VeraGrid multi-circuit model
    :param n_time: number of time steps
    :returns: Vbus guess matrix shaped ``(T, N)``
    """
    n_time_int: int = int(n_time)
    if n_time_int < 1:
        raise ValueError("Cannot extract Vbus guesses from an empty time axis.")
    else:
        pass

    # Compile the first time step once to determine the fixed bus count and allocate the full matrix.
    nc_0: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, t_idx=0)
    n_bus: int = int(np.asarray(nc_0.bus_data.Vbus).shape[0])
    out: np.ndarray = np.empty((n_time_int, n_bus), dtype=np.complex128)

    t_idx: int
    for t_idx in range(n_time_int):
        nc_t: NumericalCircuit
        if t_idx == 0:
            nc_t = nc_0
        else:
            nc_t = compile_numerical_circuit_at(circuit=grid, t_idx=t_idx)
        # Each row stores VeraGrid's compiled voltage reference/guess for that time step.
        row: np.ndarray = np.asarray(nc_t.bus_data.Vbus, dtype=np.complex128)
        if int(row.shape[0]) != n_bus:
            raise ValueError("Bus count changed across time.")
        else:
            out[t_idx, :] = row
    return out


def build_multigrid_dataset_from_veragrid(
        file_name: str,
        device: Optional[torch.device] = None,
        dtype: torch.dtype = torch.float32,
        default_hours_number: int = 1
) -> MultiGridDataset:
    """
    Load one VeraGrid file and convert it into a multi-grid dataset.

    :param file_name: ``.gridcal`` file path
    :param device: target device, or ``None``
    :param dtype: floating dtype
    :param default_hours_number: if the grid has no time series, then fill with this number of identical time steps
    :returns: multi-grid dataset
    """
    # Global view of this function:
    #
    # 1. Load one VeraGrid model and solve its time series.
    # 2. Extract the fixed graph description once.
    # 3. Extract the time-varying tensors that live on that graph.
    # 4. Remove bad rows that would poison training.
    # 5. Normalize the angular reference frame.
    # 6. Package everything into one reusable dataset object.
    #
    # Algorithmically, this stage separates two concerns:
    # - persistent per-file data preparation
    # - transient per-step training sampling
    # The output is not yet a training mini-batch. It is the persistent per-file
    # storage object from which many training windows will later be sampled.
    runtime_device: torch.device
    if device is None:
        runtime_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        runtime_device = device

    # Load the file as a VeraGrid model and run its time-series power flow once up front.
    grid: MultiCircuit = vg.open_file(file_name)

    if not grid.has_time_series:
        # print creating 1
        grid.create_profiles(steps=default_hours_number, step_length=1, step_unit="h")

    results = vg.power_flow_ts(grid)
    graph_cpu: GraphSpec = build_graph_spec_from_multicircuit(grid=grid, t_idx=0)

    # These arrays are the raw solved trajectories that define the learning target for one graph.
    # These arrays are the raw time-series supervision signals coming from VeraGrid.
    n_time: int = int(len(results.time_array))
    voltage: np.ndarray = np.asarray(results.voltage)
    s_bus: np.ndarray = np.asarray(results.S / grid.Sbase)
    branch_active_np: np.ndarray = extract_branch_active_matrix(grid=grid, n_time=n_time)
    v0_np: np.ndarray = extract_vbus_guess_matrix(grid=grid, n_time=n_time)
    unix_time_np: np.ndarray = np.asarray(grid.get_unix_time(), dtype=np.int64)
    if int(unix_time_np.shape[0]) != n_time:
        raise ValueError("Grid UNIX time length does not match the solved time-series length.")
    else:
        pass

    # Algorithmically, bad rows are removed here so the trainer never has to reason about invalid states.
    # Filter out any rows that are non-finite or not converged before training touches them.
    valid_mask: np.ndarray = (finite_row_mask_complex(voltage)
                              & finite_row_mask_complex(s_bus)
                              & finite_row_mask_complex(v0_np))
    converged_values: Optional[np.ndarray] = results.converged_values
    if converged_values is None:
        pass
    else:
        valid_mask = valid_mask & np.asarray(converged_values, dtype=bool)

    n_valid: int = int(np.sum(valid_mask))
    if n_valid == 0:
        raise ValueError(f"No valid converged time steps found in {file_name}.")
    else:
        pass

    # Apply the row filter once so every tensor stays aligned in time afterwards.
    voltage_valid: np.ndarray = voltage[valid_mask]
    s_bus_valid: np.ndarray = s_bus[valid_mask]
    branch_active_valid: np.ndarray = branch_active_np[valid_mask]
    v0_valid: np.ndarray = v0_np[valid_mask]
    time_array_valid: np.ndarray = np.asarray(results.time_array)[valid_mask]
    unix_time_valid: np.ndarray = unix_time_np[valid_mask]
    time_features_np: np.ndarray = build_time_features_from_unix_time(unix_time_seconds=unix_time_valid)

    # All rows must share one comparable reference frame, otherwise the network sees equivalent physical
    # states under different global angles as different targets.
    # Use the compiled slack bus to place all trajectories in a consistent angular reference frame.
    slack_idx: np.ndarray = np.where(graph_cpu.bus_type.cpu().numpy() == 0)[0]
    ref_bus: int
    if slack_idx.size > 0:
        ref_bus = int(slack_idx[0])
    else:
        ref_bus = 0

    vr_true_np: np.ndarray
    vi_true_np: np.ndarray
    # Gauge-fix both the solved voltages and the reference guess so the solver does
    # not waste capacity learning arbitrary global angle rotations.
    vr_true_np, vi_true_np = gauge_fix_cartesian(np.real(voltage_valid), np.imag(voltage_valid), ref_bus=ref_bus)
    vr0_fixed_np: np.ndarray
    vi0_fixed_np: np.ndarray
    vr0_fixed_np, vi0_fixed_np = gauge_fix_cartesian(np.real(v0_valid), np.imag(v0_valid), ref_bus=ref_bus)
    v0_fixed: np.ndarray = vr0_fixed_np + 1j * vi0_fixed_np

    # The solver needs to know which voltage components are prescribed by problem definition.
    # Only the slack entries are carried into the solver as explicit voltage references.
    vref_np: np.ndarray = np.zeros_like(v0_fixed)
    if slack_idx.size > 0:
        vref_np[:, slack_idx] = v0_fixed[:, slack_idx]
    else:
        pass

    complex_dtype: torch.dtype
    if dtype == torch.float32:
        complex_dtype = torch.complex64
    else:
        complex_dtype = torch.complex128

    # After this point, the file is fully converted into a runtime dataset object that can be sampled
    # many times without recompiling VeraGrid structures.
    # Move the immutable graph struct and all time-series tensors to the chosen runtime device.
    graph_device: GraphSpec = graph_spec_to_device(graph=graph_cpu, device=runtime_device, dtype=dtype)
    # This final object is the persistent training source for one file.
    dataset: MultiGridDataset = MultiGridDataset(
        name=file_name,
        graph=graph_device,
        vr_true=torch.tensor(vr_true_np, dtype=dtype, device=runtime_device),
        vi_true=torch.tensor(vi_true_np, dtype=dtype, device=runtime_device),
        vref=torch.tensor(vref_np, dtype=complex_dtype, device=runtime_device),
        vr_init=torch.tensor(vr0_fixed_np, dtype=dtype, device=runtime_device),
        vi_init=torch.tensor(vi0_fixed_np, dtype=dtype, device=runtime_device),
        pinj=torch.tensor(np.real(s_bus_valid), dtype=dtype, device=runtime_device),
        qinj=torch.tensor(np.imag(s_bus_valid), dtype=dtype, device=runtime_device),
        branch_active=torch.tensor(branch_active_valid, dtype=torch.float32, device=runtime_device),
        time_array=time_array_valid,
        unix_time=torch.tensor(unix_time_valid, dtype=torch.int64, device=runtime_device),
        time_features=torch.tensor(time_features_np, dtype=torch.float32, device=runtime_device),
        n_time=int(vr_true_np.shape[0]),
    )
    return dataset


def load_multigrid_collection(
        file_names: list[str],
        device: Optional[torch.device] = None,
        dtype: torch.dtype = torch.float32,
        default_hours_number: int = 1
) -> list[MultiGridDataset]:
    """
    Load a hand-provided list of VeraGrid files.

    :param file_names: list of file paths
    :param device: target device, or ``None``
    :param dtype: floating dtype
    :param default_hours_number: if the grid has no time series, then fill with this number of identical time steps
    :returns: list of datasets
    """
    # Global view of this function:
    #
    # - each file becomes one dataset
    # - each dataset keeps its own graph and time series
    # - the returned collection is the full multi-grid training corpus
    #
    # Algorithmically, diversity enters here: different files mean different graphs and different
    # operating trajectories, all tied together by one shared solver.
    # Later, the trainer will sample across this collection to expose one shared
    # solver to many topologies and operating trajectories.
    # Load each file independently so every dataset keeps its own graph and time-series tensors.
    datasets: list[MultiGridDataset] = list()
    file_name: str
    for file_name in file_names:
        dataset: MultiGridDataset = build_multigrid_dataset_from_veragrid(
            file_name=file_name,
            device=device,
            dtype=dtype,
            default_hours_number=default_hours_number
        )
        datasets.append(dataset)
        print(f"[loaded] {file_name}  T={dataset.n_time}  N={dataset.graph.n_bus}  M={dataset.graph.n_branch}")

    if len(datasets) == 0:
        raise ValueError("load_multigrid_collection requires at least one file.")
    else:
        pass
    return datasets


def train_general_purpose_solver(
        solver: GeneralPurposeTypedGNNSolver,
        physics: StatelessAcPowerFlowPhysics,
        datasets: list[MultiGridDataset],
        window: int,
        steps: int,
        graphs_per_step: int,
        lr: float,
        w_v: float,
        w_pf: float,
        w_branch_p: float,
        w_branch_q: float,
        verbose_every: int,
        seed: int = 0,
        use_cartesian_voltage_loss: bool = True,
) -> None:
    """
    Train one shared solver across many graph datasets.

    :param solver: shared-weight solver
    :param physics: stateless physics evaluator
    :param datasets: list of datasets
    :param window: window length
    :param steps: optimizer steps
    :param graphs_per_step: sampled graph windows per optimizer step
    :param lr: learning rate
    :param w_v: voltage supervised loss weight
    :param w_pf: power-flow mismatch loss weight
    :param w_branch_p: branch active-flow loss weight
    :param w_branch_q: branch reactive-flow loss weight
    :param verbose_every: log frequency
    :param seed: random seed
    :param use_cartesian_voltage_loss: whether to optimize Cartesian voltage loss instead of magnitude loss
    :returns: ``None``
    """
    # Global view of this function:
    #
    # - we do not train on one fixed grid
    # - we repeatedly pick several datasets from the collection
    # - from each chosen dataset we sample one short time window
    # - each sampled window is solved with the same shared GNN weights
    # - losses are accumulated across those graph-specific windows
    #
    # This is the mechanism that turns the single-grid solver idea into a
    # general-purpose multi-grid training regime.
    if len(datasets) == 0:
        raise ValueError("train_general_purpose_solver requires at least one dataset.")
    else:
        pass
    if int(graphs_per_step) < 1:
        raise ValueError("graphs_per_step must be >= 1.")
    else:
        pass

    # One RNG drives both graph selection and window selection so training is reproducible from one seed.
    rng: np.random.Generator = np.random.default_rng(int(seed))
    optimizer: torch.optim.AdamW = torch.optim.AdamW(solver.parameters(), lr=float(lr), weight_decay=1e-6)
    solver.train()

    step_idx: int
    for step_idx in range(1, int(steps) + 1):
        optimizer.zero_grad(set_to_none=True)
        total_loss: torch.Tensor = torch.tensor(0.0, device=get_module_device(solver))
        loss_v_sum: float = 0.0
        loss_pf_sum: float = 0.0
        loss_branch_p_sum: float = 0.0
        loss_branch_q_sum: float = 0.0

        # Each optimizer step is deliberately mixed across graphs so the shared weights are constantly
        # forced to solve different topologies instead of overfitting one network.
        # Multi-grid batching is implemented as several independently sampled graph windows per optimizer step.
        # Each sampled index picks one source file / one source graph.
        sampled_indices: np.ndarray = rng.integers(0, len(datasets), size=int(graphs_per_step))
        ds_idx: np.integer
        for ds_idx in sampled_indices:
            dataset: MultiGridDataset = datasets[int(ds_idx)]
            # This is where a full per-file time series becomes one concrete training example.
            window_sample: MultiGridWindow = dataset.sample_window(window=window, rng=rng)
            vr_pred: torch.Tensor
            vi_pred: torch.Tensor
            # Run the same shared solver weights on whichever graph was sampled for this contribution.
            vr_pred, vi_pred = solver(
                graph=window_sample.graph,
                pinj_tn=window_sample.pinj,
                qinj_tn=window_sample.qinj,
                branch_active_tm=window_sample.branch_active,
                vref_tn=window_sample.vref,
                vr_init_tn=window_sample.vr_init,
                vi_init_tn=window_sample.vi_init,
                time_features_tk=window_sample.time_features,
            )
            # This term keeps the learned solver close to the solved voltages seen in the data.
            # The default supervised term now matches the Cartesian voltage metric used in evaluation.
            loss_v: torch.Tensor
            if use_cartesian_voltage_loss:
                loss_v = voltage_cartesian_loss(
                    vr_pred=vr_pred,
                    vi_pred=vi_pred,
                    vr_true=window_sample.vr_true,
                    vi_true=window_sample.vi_true,
                )
            else:
                loss_v = voltage_magnitude_loss(
                    vr_pred=vr_pred,
                    vi_pred=vi_pred,
                    vr_true=window_sample.vr_true,
                    vi_true=window_sample.vi_true,
                )
            # Evaluate the predicted voltages against the exact AC equations for that same graph.
            evaluation: PhysicsEvaluation = physics(
                graph=window_sample.graph,
                vr=vr_pred,
                vi=vi_pred,
                branch_active=window_sample.branch_active,
                pinj_target=window_sample.pinj,
                qinj_target=window_sample.qinj,
            )
            if evaluation.loss_mismatch is None:
                raise RuntimeError("Physics evaluation unexpectedly returned no mismatch loss.")
            else:
                pass
            target_evaluation: PhysicsEvaluation = physics(
                graph=window_sample.graph,
                vr=window_sample.vr_true,
                vi=window_sample.vi_true,
                branch_active=window_sample.branch_active,
                pinj_target=window_sample.pinj,
                qinj_target=window_sample.qinj,
            )
            # This term keeps the learned solver physically grounded on the current graph.
            # The physics term says whether the predicted voltages satisfy the requested injections on that graph.
            loss_pf: torch.Tensor = evaluation.loss_mismatch
            loss_branch_p: torch.Tensor = (
                ((evaluation.pf - target_evaluation.pf) ** 2)
                + ((evaluation.pt - target_evaluation.pt) ** 2)
            ).mean()
            loss_branch_q: torch.Tensor = (
                ((evaluation.qf - target_evaluation.qf) ** 2)
                + ((evaluation.qt - target_evaluation.qt) ** 2)
            ).mean()
            total_loss = total_loss + (
                float(w_v) * loss_v
                + float(w_pf) * loss_pf
                + float(w_branch_p) * loss_branch_p
                + float(w_branch_q) * loss_branch_q
            )
            loss_v_sum += float(loss_v.detach().cpu().item())
            loss_pf_sum += float(loss_pf.detach().cpu().item())
            loss_branch_p_sum += float(loss_branch_p.detach().cpu().item())
            loss_branch_q_sum += float(loss_branch_q.detach().cpu().item())

        # Averaging keeps the effective optimization scale stable when the number of sampled graphs changes.
        # Average across sampled graph windows so the step size does not depend on graphs_per_step.
        total_loss = total_loss / float(graphs_per_step)
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(solver.parameters(), 1.0)
        optimizer.step()

        if int(verbose_every) > 0 and (step_idx % int(verbose_every) == 0 or step_idx == 1):
            print(
                f"[step {step_idx:6d}] "
                f"loss_v={loss_v_sum / float(graphs_per_step):.6e}  "
                f"loss_pf={loss_pf_sum / float(graphs_per_step):.6e}  "
                f"loss_branch_p={loss_branch_p_sum / float(graphs_per_step):.6e}  "
                f"loss_branch_q={loss_branch_q_sum / float(graphs_per_step):.6e}  "
                f"graphs_per_step={graphs_per_step}"
            )
        else:
            pass


def evaluate_general_purpose_solver_on_dataset(
        solver: GeneralPurposeTypedGNNSolver,
        physics: StatelessAcPowerFlowPhysics,
        dataset: MultiGridDataset,
        window: int,
        start_idx: int = 0,
) -> EvaluationResult:
    """
    Evaluate one held-out window from one dataset.

    :param solver: shared-weight solver
    :param physics: stateless physics evaluator
    :param dataset: evaluation dataset
    :param window: window length
    :param start_idx: requested start index
    :returns: full evaluation result including metrics and predicted tensors
    """
    # Global view of this function:
    #
    # - pick one window from one dataset
    # - run the shared solver on that graph/window pair
    # - measure voltage and physics error
    #
    # Algorithmically, this answers the real question:
    # after shared training, how well does the solver handle one particular graph and one operating window?
    # This is the same runtime path as training, just without gradient updates.
    window_int: int = int(window)
    if dataset.n_time < window_int:
        raise ValueError("Requested evaluation window is larger than the dataset.")
    else:
        pass
    # Clamp the evaluation start so the requested window always remains inside the available time range.
    start_idx_clamped: int = int(max(0, min(int(start_idx), dataset.n_time - window_int)))
    tw: slice = slice(start_idx_clamped, start_idx_clamped + window_int)

    solver.eval()
    with torch.no_grad():
        vr_pred: torch.Tensor
        vi_pred: torch.Tensor
        # Evaluation uses exactly the same graph-specific runtime path as training, just without gradients.
        vr_pred, vi_pred = solver(
            graph=dataset.graph,
            pinj_tn=dataset.pinj[tw],
            qinj_tn=dataset.qinj[tw],
            branch_active_tm=dataset.branch_active[tw],
            vref_tn=dataset.vref[tw],
            vr_init_tn=dataset.vr_init[tw],
            vi_init_tn=dataset.vi_init[tw],
            time_features_tk=dataset.time_features[tw],
        )
        evaluation: PhysicsEvaluation = physics(
            graph=dataset.graph,
            vr=vr_pred,
            vi=vi_pred,
            branch_active=dataset.branch_active[tw],
            pinj_target=dataset.pinj[tw],
            qinj_target=dataset.qinj[tw],
        )
        if evaluation.loss_mismatch is None:
            raise RuntimeError("Physics evaluation unexpectedly returned no mismatch loss.")
        else:
            pass
        physics_true: PhysicsEvaluation = physics(
            graph=dataset.graph,
            vr=dataset.vr_true[tw],
            vi=dataset.vi_true[tw],
            branch_active=dataset.branch_active[tw],
            pinj_target=dataset.pinj[tw],
            qinj_target=dataset.qinj[tw],
        )
        voltage_mse: float = float(
            (((vr_pred - dataset.vr_true[tw]) ** 2) + ((vi_pred - dataset.vi_true[tw]) ** 2)).mean().item())
        voltage_magnitude_mse: float = float(
            voltage_magnitude_loss(
                vr_pred=vr_pred,
                vi_pred=vi_pred,
                vr_true=dataset.vr_true[tw],
                vi_true=dataset.vi_true[tw],
            ).item()
        )
        pf_mismatch: float = float(evaluation.loss_mismatch.item())
        branch_active_flow_mse: float = float(
            (
                ((evaluation.pf - physics_true.pf) ** 2)
                + ((evaluation.pt - physics_true.pt) ** 2)
            ).mean().item()
        )
        branch_reactive_flow_mse: float = float(
            (
                ((evaluation.qf - physics_true.qf) ** 2)
                + ((evaluation.qt - physics_true.qt) ** 2)
            ).mean().item()
        )

        metrics: EvaluationMetrics = EvaluationMetrics(
            voltage_mse=voltage_mse,
            voltage_magnitude_mse=voltage_magnitude_mse,
            pf_mismatch=pf_mismatch,
            branch_active_flow_mse=branch_active_flow_mse,
            branch_reactive_flow_mse=branch_reactive_flow_mse,
        )

    result: EvaluationResult = EvaluationResult(
        metrics=metrics,
        vr_pred=vr_pred,
        vi_pred=vi_pred,
        physics_evaluation=evaluation,
        start_idx=start_idx_clamped,
        window=window_int,
    )
    return result


def plot_testing_performance(
        solver: GeneralPurposeTypedGNNSolver,
        physics: StatelessAcPowerFlowPhysics,
        dataset: MultiGridDataset,
        evaluation_result: EvaluationResult,
        bus_indices: Optional[list[int]] = None,
        branch_indices: Optional[list[int]] = None,
) -> None:
    """
    Plot post-training testing performance for one dataset window.

    :param solver: trained shared-weight solver
    :param physics: stateless physics evaluator
    :param dataset: testing dataset
    :param evaluation_result: result returned by ``evaluate_general_purpose_solver_on_dataset``
    :param bus_indices: bus indices to plot, or ``None``
    :param branch_indices: branch indices to plot, or ``None``
    :returns: ``None``
    """
    _ = solver

    # Global view of this plotting function:
    #
    # - it visualizes the testing window after training has finished
    # - it compares predicted voltage magnitude against solved target magnitude
    # - it shows the bus-injection mismatch implied by the predicted voltages
    # - it compares predicted and target branch active-power flows
    #
    # Algorithmically, these plots answer three different questions:
    # 1. Did the solver recover the target voltage state?
    # 2. Did the predicted state satisfy the requested injections?
    # 3. Did the predicted state reproduce branch-level power-flow behavior?
    start_idx: int = int(evaluation_result.start_idx)
    window: int = int(evaluation_result.window)
    tw: slice = slice(start_idx, start_idx + window)

    vr_true: torch.Tensor = dataset.vr_true[tw]
    vi_true: torch.Tensor = dataset.vi_true[tw]
    vr_pred: torch.Tensor = evaluation_result.vr_pred
    vi_pred: torch.Tensor = evaluation_result.vi_pred
    branch_active: torch.Tensor = dataset.branch_active[tw]
    pinj: torch.Tensor = dataset.pinj[tw]
    qinj: torch.Tensor = dataset.qinj[tw]

    n_bus: int = int(dataset.graph.n_bus)
    n_branch: int = int(dataset.graph.n_branch)

    bus_idx_list: list[int]
    if bus_indices is None:
        bus_idx_list = list()
        bus_idx_list.append(0)
        if n_bus > 1:
            bus_idx_list.append(1)
        else:
            pass
        if n_bus > 2:
            bus_idx_list.append(2)
        else:
            pass
        if n_bus > 5:
            bus_idx_list.append(5)
        else:
            pass
    else:
        bus_idx_list = list()
        bus_idx_candidate: int
        for bus_idx_candidate in bus_indices:
            if 0 <= int(bus_idx_candidate) < n_bus:
                bus_idx_list.append(int(bus_idx_candidate))
            else:
                pass
    if len(bus_idx_list) == 0:
        bus_idx_list = list()
        bus_idx_list.append(0)
    else:
        pass

    branch_idx_list: list[int]
    if branch_indices is None:
        branch_idx_list = list()
        branch_idx_list.append(0)
        if n_branch > 1:
            branch_idx_list.append(1)
        else:
            pass
        if n_branch > 2:
            branch_idx_list.append(2)
        else:
            pass
        if n_branch > 10:
            branch_idx_list.append(10)
        else:
            pass
    else:
        branch_idx_list = list()
        branch_idx_candidate: int
        for branch_idx_candidate in branch_indices:
            if 0 <= int(branch_idx_candidate) < n_branch:
                branch_idx_list.append(int(branch_idx_candidate))
            else:
                pass
    if len(branch_idx_list) == 0:
        branch_idx_list = list()
        branch_idx_list.append(0)
    else:
        pass

    with torch.no_grad():
        # Compute target flows from the solved target voltages for a direct branch-level comparison.
        physics_true: PhysicsEvaluation = physics(
            graph=dataset.graph,
            vr=vr_true,
            vi=vi_true,
            branch_active=branch_active,
            pinj_target=pinj,
            qinj_target=qinj,
        )

        vm_true: torch.Tensor = torch.sqrt(vr_true * vr_true + vi_true * vi_true + 1e-12)
        vm_pred: torch.Tensor = torch.sqrt(vr_pred * vr_pred + vi_pred * vi_pred + 1e-12)
        vm_error: torch.Tensor = vm_pred - vm_true

        if evaluation_result.physics_evaluation.dp is None or evaluation_result.physics_evaluation.dq is None:
            raise RuntimeError("Testing plot requires mismatch tensors, but they are missing.")
        else:
            pass

        dp_rms: torch.Tensor = torch.sqrt(torch.mean(evaluation_result.physics_evaluation.dp ** 2, dim=1) + 1e-12)
        dq_rms: torch.Tensor = torch.sqrt(torch.mean(evaluation_result.physics_evaluation.dq ** 2, dim=1) + 1e-12)

        v_error_rms: torch.Tensor = torch.sqrt(
            torch.mean((vr_pred - vr_true) ** 2 + (vi_pred - vi_true) ** 2, dim=1) + 1e-12
        )

    time_index: np.ndarray = np.arange(window, dtype=np.int64)
    vm_error_np: np.ndarray = vm_error.detach().cpu().numpy()
    dp_rms_np: np.ndarray = dp_rms.detach().cpu().numpy()
    dq_rms_np: np.ndarray = dq_rms.detach().cpu().numpy()
    v_error_rms_np: np.ndarray = v_error_rms.detach().cpu().numpy()
    pf_true_np: np.ndarray = physics_true.pf.detach().cpu().numpy()
    pf_pred_np: np.ndarray = evaluation_result.physics_evaluation.pf.detach().cpu().numpy()

    plt.figure()
    bus_idx: int
    for bus_idx in bus_idx_list:
        plt.plot(time_index, vm_error_np[:, bus_idx], label=f"Vm error bus {bus_idx}")
    plt.title(f"Testing - Voltage Magnitude Error - {dataset.name}")
    plt.xlabel("time index within testing window")
    plt.ylabel("Vm error (p.u.)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    plt.figure()
    plt.plot(time_index, v_error_rms_np, label="voltage error RMS")
    plt.title(f"Testing - Voltage Error RMS - {dataset.name}")
    plt.xlabel("time index within testing window")
    plt.ylabel("RMS voltage error")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    plt.figure()
    plt.plot(time_index, dp_rms_np, label="Delta P RMS")
    plt.plot(time_index, dq_rms_np, label="Delta Q RMS")
    plt.title(f"Testing - Power Mismatch RMS - {dataset.name}")
    plt.xlabel("time index within testing window")
    plt.ylabel("RMS mismatch")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    plt.figure()
    branch_idx: int
    for branch_idx in branch_idx_list:
        plt.plot(time_index, pf_true_np[:, branch_idx], label=f"Pf true br {branch_idx}")
        plt.plot(time_index, pf_pred_np[:, branch_idx], "--", label=f"Pf pred br {branch_idx}")
    plt.title(f"Testing - Branch Active Power Flow - {dataset.name}")
    plt.xlabel("time index within testing window")
    plt.ylabel("Pf (p.u.)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    plt.show()


def main_multigrid_example(
        train_file_names: list[str],
        test_file_names: list[str],
        embed_dim: int = 64,
        msg_hidden: int = 128,
        tgn_layers: int = 6,
        msg_steps: int = 2,
        window: int = 96,
        steps: int = 400,
        graphs_per_step: int = 4,
        lr: float = 1e-3,
        w_v: float = 0.1,
        w_pf: float = 1.0,
        verbose_every: int = 50,
        plot_testing: bool = True,
        default_hours_number: int = 1
) -> None:
    """
    Base multi-grid example using a hand-provided file list.

    :param train_file_names: training file list
    :param test_file_names: testing file list
    :param embed_dim: solver embedding width
    :param msg_hidden: message/update MLP hidden width
    :param tgn_layers: unrolled solver layers
    :param msg_steps: message passing steps per layer
    :param window: requested training/evaluation window
    :param steps: optimizer steps
    :param graphs_per_step: sampled graph windows per optimizer step
    :param lr: learning rate
    :param w_v: voltage magnitude loss weight
    :param w_pf: power-flow mismatch loss weight
    :param verbose_every: log frequency
    :param plot_testing: whether to create testing plots after evaluation
    :param default_hours_number: if the grid has no time series, then fill with this number of identical time steps
    :returns: ``None``
    """
    # Global view of this example:
    #
    # - the user provides a training file list and a testing file list
    # - each training file becomes one training dataset object
    # - each testing file becomes one testing dataset object
    # - one shared graph-agnostic solver is created
    # - the solver is trained only on the training datasets
    # - the solver is then evaluated on the testing datasets
    #
    # For now, you may pass the same file list for both roles. Even in that case, the code still
    # keeps training-data construction and testing-data construction as separate explicit stages.
    #
    # This makes the control flow honest:
    # - stage 1: build training corpus
    # - stage 2: train shared solver
    # - stage 3: build / use testing corpus
    # - stage 4: evaluate and plot testing performance
    # Keep the example deterministic so architecture changes are easier to compare.
    torch.manual_seed(0)
    np.random.seed(0)

    device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype: torch.dtype = torch.float32

    print("\n[stage 1] building training datasets")
    train_datasets: list[MultiGridDataset] = load_multigrid_collection(
        file_names=train_file_names,
        device=device,
        dtype=dtype,
        default_hours_number=default_hours_number
    )

    print("\n[stage 2] building testing datasets")
    test_datasets: list[MultiGridDataset] = load_multigrid_collection(
        file_names=test_file_names,
        device=device,
        dtype=dtype,
        default_hours_number=default_hours_number
    )

    physics: StatelessAcPowerFlowPhysics = StatelessAcPowerFlowPhysics(dtype=dtype).to(device)
    solver: GeneralPurposeTypedGNNSolver = GeneralPurposeTypedGNNSolver(
        embed_dim=embed_dim,
        msg_hidden=msg_hidden,
        tgn_layers=tgn_layers,
        msg_steps=msg_steps,
        dtype=dtype,
    ).to(device)

    # The example uses one common window length, so clamp it against the shortest dataset
    # across both the training and the testing collections.
    # Snapshot datasets with T=1 are explicitly supported, so the minimum valid window is 1.
    min_time_train: int = min(dataset.n_time for dataset in train_datasets)
    min_time_test: int = min(dataset.n_time for dataset in test_datasets)
    min_time: int = min(min_time_train, min_time_test)
    effective_window: int = int(max(1, min(int(window), min_time)))
    if effective_window != int(window):
        print(f"[config] window requested={window} -> effective={effective_window}")
    else:
        pass

    print("\n[training datasets]")
    dataset: MultiGridDataset
    for dataset in train_datasets:
        print(f"  {dataset.name}: T={dataset.n_time} N={dataset.graph.n_bus} M={dataset.graph.n_branch}")

    print("\n[testing datasets]")
    for dataset in test_datasets:
        print(f"  {dataset.name}: T={dataset.n_time} N={dataset.graph.n_bus} M={dataset.graph.n_branch}")

    print("\n[stage 3] training shared solver on training datasets")
    train_general_purpose_solver(
        solver=solver,
        physics=physics,
        datasets=train_datasets,
        window=effective_window,
        steps=steps,
        graphs_per_step=graphs_per_step,
        lr=lr,
        w_v=w_v,
        w_pf=w_pf,
        w_branch_p=1.0,
        w_branch_q=0.5,
        verbose_every=verbose_every,
        seed=0,
        use_cartesian_voltage_loss=True,
    )

    print("\n[stage 4] testing shared solver on testing datasets")
    print("[note] this is post-training evaluation.")
    print("[note] if train_file_names and test_file_names are the same, this is still an evaluation stage,")
    print("[note] but it is not an unseen-grid generalization test yet.")
    for dataset in test_datasets:
        evaluation_result: EvaluationResult = evaluate_general_purpose_solver_on_dataset(
            solver=solver,
            physics=physics,
            dataset=dataset,
            window=effective_window,
            start_idx=0,
        )
        print(
            f"  {dataset.name}: "
            f"voltage_mse={evaluation_result.metrics.voltage_mse:.6e}  "
            f"vm_mse={evaluation_result.metrics.voltage_magnitude_mse:.6e}  "
            f"pf_mismatch={evaluation_result.metrics.pf_mismatch:.6e}  "
            f"branch_p_mse={evaluation_result.metrics.branch_active_flow_mse:.6e}  "
            f"branch_q_mse={evaluation_result.metrics.branch_reactive_flow_mse:.6e}"
        )
        if plot_testing:
            plot_testing_performance(
                solver=solver,
                physics=physics,
                dataset=dataset,
                evaluation_result=evaluation_result,
                bus_indices=None,
                branch_indices=None,
            )
        else:
            pass
