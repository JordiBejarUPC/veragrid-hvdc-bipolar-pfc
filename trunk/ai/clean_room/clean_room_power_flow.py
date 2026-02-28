# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Typed-GNN PF voltage solver + Physics layer + Training + PLOTS (no batch dimension required)
===========================================================================================

This is the same solver/physics demo as before, but now it ALSO PLOTS a test window
so you can visually confirm it works.

Key points
----------
- You DO NOT provide a batch dimension. You only use:
    - Vr_true:   (T_total, N)
    - Vi_true:   (T_total, N)
    - branch_active: (T_total, M)
    - Pinj/Qinj: (T_total, N)

- Training creates "more points" by sampling random windows:
    - window voltages: (Tw, N)
    - window branch_active: (Tw, M)
    - window injections: (Tw, N)
  One window at a time (still no batch dim).

- The solver is an unrolled typed message-passing network (paper-style), but using
  Cartesian voltage updates (ΔVr, ΔVi) for numerical consistency.

- Plotting section at the end shows:
    1) Vr_true vs Vr_pred for a few buses (over time)
    2) Vi_true vs Vi_pred for a few buses
    3) Voltage error RMS over time (single curve)
    4) PF mismatch RMS over time (ΔP RMS and ΔQ RMS)
    5) Pf (from-end flow) true vs pred for a few branches (optional but very informative)

No Tuple[int, ...] is used anywhere. Input formats are explicitly described in docstrings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, TYPE_CHECKING

import numpy as np
import torch
import torch.nn as nn
import VeraGridEngine as vg
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.PowerFlow.power_flow_ts_results import PowerFlowTimeSeriesResults


# ======================================================================================================================
# 1) Utility: get device even if module has no parameters (buffers-only)
# ======================================================================================================================

def get_module_device(module: nn.Module) -> torch.device:
    """
    Return a device for a module, even if it has NO parameters (buffers-only).

    :param module: nn.Module
    :returns: torch.device
    """
    try:
        return next(module.buffers()).device
    except StopIteration:
        pass
    try:
        return next(module.parameters()).device
    except StopIteration:
        return torch.device("cpu")


def prod_int_list(shape_list: list) -> int:
    """
    Multiply ints in a list.

    :param shape_list: list of ints
    :returns: product
    """
    p = 1
    for x in shape_list:
        p *= int(x)
    return int(p)


def flatten_last_dim(x: torch.Tensor):
    """
    Flatten every leading dimension into one axis so x becomes (B_flat, F),
    where F is the last dimension.

    This helper is what lets the rest of the code support both:
      - 2D tensors like (T, N)
      - 3D tensors like (B, T, N)

    Why 3D now?
      - The new first dimension is a real batch dimension: B
      - The second dimension is the time axis inside each sampled window: T
      - The last dimension is still the electrical entity axis:
          N for buses
          M for branches

    Internally, many operations do not actually care whether the leading
    axes mean "batch" or "time"; they only care that the last axis is the
    bus or branch axis. So we flatten the leading axes into one dimension,
    do the electrical computation on (B_flat, F), and then reshape back.

    Input:
      x: (..., F)

    Output:
      x_flat: (B, F)
      lead_shape: list of ints (the leading dims)
      f: int (the last dim)

    Example:
      x: (T, N) => x_flat: (T, N), lead_shape=[T], f=N
      x: (B, T, N) => x_flat: (B*T, N), lead_shape=[B, T], f=N

    :param x: tensor shaped (...,F)
    :returns: (x_flat, lead_shape_list, f)
    """
    if x.ndim < 1:
        raise ValueError("x must have at least 1 dimension.")
    lead_shape = [int(s) for s in x.shape[:-1]]
    f = int(x.shape[-1])
    b = prod_int_list(lead_shape) if len(lead_shape) > 0 else 1
    return x.reshape(b, f), lead_shape, f


def reshape_back(x_flat: torch.Tensor, lead_shape: list, last_dim: int) -> torch.Tensor:
    """
    Reshape (B,last_dim) back into (*lead_shape,last_dim).

    :param x_flat: tensor (B,last_dim)
    :param lead_shape: list of ints
    :param last_dim: int
    :returns: tensor (*lead_shape,last_dim)
    """
    if len(lead_shape) == 0:
        return x_flat.reshape(last_dim)
    shape = list(lead_shape) + [int(last_dim)]
    return x_flat.reshape(shape)


def as_complex(vr: torch.Tensor, vi: torch.Tensor) -> torch.Tensor:
    """
    Convert (vr,vi) to a complex tensor.

    :param vr: real
    :param vi: imag
    :returns: complex
    """
    return torch.complex(vr, vi)


def complex_tap(tau: torch.Tensor, shift: torch.Tensor) -> torch.Tensor:
    """
    tap = tau * exp(j*shift)

    :param tau: (M,)
    :param shift: (M,) radians
    :returns: (M,) complex
    """
    return torch.complex(tau * torch.cos(shift), tau * torch.sin(shift))


def _map_veragrid_bus_types(bus_types: np.ndarray) -> np.ndarray:
    """
    Map VeraGrid bus type codes to the clean-room convention.

    VeraGrid:
      1 = PQ
      2 = PV
      3 = Slack
      4 = PQV
      5 = P

    Clean-room:
      0 = slack
      1 = PV-like
      2 = PQ-like

    :param bus_types: VeraGrid bus type codes
    :returns: clean-room bus type codes
    """
    out = np.full(bus_types.shape, fill_value=-1, dtype=np.int64)
    out[bus_types == 3] = 0
    out[np.isin(bus_types, [2, 4, 5])] = 1
    out[bus_types == 1] = 2

    bad = np.where(out < 0)[0]
    if bad.size > 0:
        bad_vals = np.unique(bus_types[bad])
        raise ValueError(f"Unsupported VeraGrid bus type codes: {bad_vals.tolist()}")

    return out





def _finite_row_mask_complex(x: np.ndarray) -> np.ndarray:
    """
    Return a mask of rows whose real and imaginary parts are finite.

    :param x: complex array shaped (T, K)
    :returns: boolean mask shaped (T,)
    """
    return np.isfinite(x.real).all(axis=1) & np.isfinite(x.imag).all(axis=1)


def _validate_clean_room_compatibility(nc: "NumericalCircuit") -> None:
    """
    Validate that a compiled VeraGrid numerical circuit only uses features represented by the clean-room physics.

    :param nc: NumericalCircuit
    :returns: None
    """
    pbd = nc.passive_branch_data
    abd = nc.active_branch_data

    if np.any(np.asarray(pbd.dc) != 0):
        raise ValueError("The clean-room AC physics does not support DC branches.")
    if np.any(np.abs(np.asarray(pbd.G)) > 1e-12):
        raise ValueError("The clean-room AC physics does not support branch conductance shunts (G != 0).")
    if np.any(np.abs(np.asarray(pbd.virtual_tap_f) - 1.0) > 1e-12):
        raise ValueError("The clean-room AC physics does not support non-unit VeraGrid virtual_tap_f.")
    if np.any(np.abs(np.asarray(pbd.virtual_tap_t) - 1.0) > 1e-12):
        raise ValueError("The clean-room AC physics does not support non-unit VeraGrid virtual_tap_t.")
    if np.any(np.asarray(abd.tap_module) <= 0.0):
        raise ValueError("All branch tap modules must be strictly positive.")


def build_superset_grid_from_multicircuit(
    grid: "MultiCircuit",
    t_idx: Optional[int] = None,
) -> SupersetGrid:
    """
    Compile a VeraGrid MultiCircuit snapshot into the clean-room SupersetGrid format.

    This preserves VeraGrid's canonical bus/branch indexing from the compiled NumericalCircuit.

    :param grid: VeraGrid MultiCircuit
    :param t_idx: optional time index to compile, None uses the snapshot values
    :returns: SupersetGrid
    """


    nc = compile_numerical_circuit_at(circuit=grid, t_idx=t_idx)
    _validate_clean_room_compatibility(nc)

    y_shunt_bus = nc.get_Yshunt_bus_pu()
    bus_type = _map_veragrid_bus_types(np.asarray(nc.bus_data.bus_types))

    return SupersetGrid(
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
    )


def _extract_status_matrix_from_multicircuit(grid: "MultiCircuit", n_time: int) -> np.ndarray:
    """
    Compile branch active states for every time step.

    :param grid: VeraGrid MultiCircuit
    :param n_time: number of time steps
    :returns: status matrix shaped (T,M)
    """
    n_time = int(n_time)
    if n_time < 1:
        raise ValueError("Cannot extract branch active states from an empty time axis.")

    nc_0 = compile_numerical_circuit_at(circuit=grid, t_idx=0)
    expected_m = int(np.asarray(nc_0.passive_branch_data.active).shape[0])
    status_rows = np.empty((n_time, expected_m), dtype=np.float32)

    for t_idx in range(n_time):
        nc_t = nc_0 if t_idx == 0 else compile_numerical_circuit_at(circuit=grid, t_idx=t_idx)
        branch_active_t = np.asarray(nc_t.passive_branch_data.active, dtype=np.float32)

        if int(branch_active_t.shape[0]) != expected_m:
            raise ValueError("Branch count changed across time; clean-room coupling requires fixed branch indexing.")

        status_rows[t_idx, :] = branch_active_t

    return status_rows


def _extract_vbus_guess_matrix_from_multicircuit(grid: "MultiCircuit", n_time: int) -> np.ndarray:
    """
    Compile bus initial guesses for every time step.

    :param grid: VeraGrid MultiCircuit
    :param n_time: number of time steps
    :returns: Vbus guess matrix shaped (T,N)
    """
    n_time = int(n_time)
    if n_time < 1:
        raise ValueError("Cannot extract Vbus guesses from an empty time axis.")

    nc_0 = compile_numerical_circuit_at(circuit=grid, t_idx=0)
    expected_n = int(np.asarray(nc_0.bus_data.Vbus).shape[0])
    v_rows = np.empty((n_time, expected_n), dtype=np.complex128)

    for t_idx in range(n_time):
        nc_t = nc_0 if t_idx == 0 else compile_numerical_circuit_at(circuit=grid, t_idx=t_idx)
        v_t = np.asarray(nc_t.bus_data.Vbus, dtype=complex)

        if int(v_t.shape[0]) != expected_n:
            raise ValueError("Bus count changed across time; clean-room coupling requires fixed bus indexing.")

        v_rows[t_idx, :] = v_t

    return v_rows


def _validate_result_taps_against_grid(
    grid: "MultiCircuit",
    results: "PowerFlowTimeSeriesResults",
    superset_grid: SupersetGrid,
    atol: float = 1e-6,
) -> None:
    """
    Ensure time-series tap controls do not violate the clean-room static-parameter assumption.

    :param grid: VeraGrid MultiCircuit
    :param results: PowerFlowTimeSeriesResults
    :param superset_grid: compiled static clean-room grid
    :param atol: absolute tolerance
    :returns: None
    """
    tap_module = np.asarray(getattr(results, "tap_module", None))
    tap_angle = np.asarray(getattr(results, "tap_angle", None))

    if tap_module.size == 0 or tap_angle.size == 0:
        return

    expected_shape = (len(results.time_array), int(superset_grid.from_bus.numel()))
    if tap_module.shape != expected_shape or tap_angle.shape != expected_shape:
        return

    # Some VeraGrid paths leave these arrays at constructor defaults.
    if np.allclose(tap_module, 0.0, atol=atol) and np.allclose(tap_angle, 0.0, atol=atol):
        return

    tap0 = tap_module[0]
    ang0 = tap_angle[0]
    if not np.allclose(tap_module, tap0[None, :], atol=atol):
        raise ValueError("PowerFlowTimeSeriesResults has time-varying tap_module values; clean-room physics assumes static branch parameters.")
    if not np.allclose(tap_angle, ang0[None, :], atol=atol):
        raise ValueError("PowerFlowTimeSeriesResults has time-varying tap_angle values; clean-room physics assumes static branch parameters.")

    if not np.allclose(tap0, superset_grid.tap.cpu().numpy(), atol=atol):
        raise ValueError("Static tap_module values in PowerFlowTimeSeriesResults do not match the compiled MultiCircuit snapshot.")
    if not np.allclose(ang0, superset_grid.shift.cpu().numpy(), atol=atol):
        raise ValueError("Static tap_angle values in PowerFlowTimeSeriesResults do not match the compiled MultiCircuit snapshot.")


def build_clean_room_dataset_from_veragrid(
    grid: "MultiCircuit",
    results: "PowerFlowTimeSeriesResults",
    device: Optional[torch.device] = None,
    dtype: torch.dtype = torch.float32,
) -> CleanRoomDataset:
    """
    Couple the clean-room model to a VeraGrid MultiCircuit + PowerFlowTimeSeriesResults pair.

    Returned tensors follow the same conventions used by the clean-room solver:
      vr_true: (T,N)
      vi_true: (T,N)
      branch_active: (T,M)
      pinj:    (T,N)
      qinj:    (T,N)

    Limitations enforced here:
      - static branch electrical parameters across time
      - no DC branches
      - no branch conductance shunts
      - no non-unit VeraGrid virtual taps

    :param grid: VeraGrid MultiCircuit
    :param results: VeraGrid PowerFlowTimeSeriesResults
    :param device: torch device, defaults to CUDA if available
    :param dtype: floating dtype for the physics layer
    :returns: typed clean-room dataset bundle
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    superset_grid = build_superset_grid_from_multicircuit(grid=grid, t_idx=0)

    n_time = len(results.time_array)
    n_bus = int(superset_grid.n_bus)
    n_branch = int(superset_grid.from_bus.numel())

    voltage = results.voltage
    s_bus = results.S / grid.Sbase

    _validate_result_taps_against_grid(grid=grid, results=results, superset_grid=superset_grid)
    status = _extract_status_matrix_from_multicircuit(grid=grid, n_time=n_time)
    v0 = _extract_vbus_guess_matrix_from_multicircuit(grid=grid, n_time=n_time)
    if status.shape != (n_time, n_branch):
        raise ValueError(f"Compiled status matrix must have shape {(n_time, n_branch)}, got {status.shape}.")
    if v0.shape != (n_time, n_bus):
        raise ValueError(f"Compiled Vbus guess matrix must have shape {(n_time, n_bus)}, got {v0.shape}.")

    valid_mask = _finite_row_mask_complex(voltage) & _finite_row_mask_complex(s_bus)
    valid_mask = valid_mask & _finite_row_mask_complex(v0)
    if hasattr(results, "converged_values"):
        valid_mask = valid_mask & np.asarray(results.converged_values, dtype=bool)

    n_valid = int(np.sum(valid_mask))
    if n_valid == 0:
        raise ValueError("No valid converged finite time steps were found in PowerFlowTimeSeriesResults.")
    if n_valid < n_time:
        print(f"[data] dropping {n_time - n_valid} invalid or non-converged time steps before training")

    voltage = voltage[valid_mask]
    s_bus = s_bus[valid_mask]
    status = status[valid_mask]
    v0 = v0[valid_mask]
    time_array = np.asarray(results.time_array)[valid_mask]

    slack_idx = np.where(superset_grid.bus_type.cpu().numpy() == 0)[0]
    ref_bus = int(slack_idx[0]) if slack_idx.size > 0 else 0
    vr_fixed, vi_fixed = gauge_fix_cartesian(np.real(voltage), np.imag(voltage), ref_bus=ref_bus)
    voltage = vr_fixed + 1j * vi_fixed
    vr0_fixed, vi0_fixed = gauge_fix_cartesian(np.real(v0), np.imag(v0), ref_bus=ref_bus)
    v0 = vr0_fixed + 1j * vi0_fixed

    vref = np.zeros_like(v0)
    if slack_idx.size > 0:
        vref[:, slack_idx] = v0[:, slack_idx]

    physics = AcPowerFlowPhysics(grid=superset_grid, dtype=dtype).to(device)

    vr_true = torch.tensor(np.real(voltage), dtype=dtype, device=device)
    vi_true = torch.tensor(np.imag(voltage), dtype=dtype, device=device)
    complex_dtype = torch.complex64 if dtype == torch.float32 else torch.complex128
    vref_t = torch.tensor(vref, dtype=complex_dtype, device=device)
    pinj = torch.tensor(np.real(s_bus), dtype=dtype, device=device)
    qinj = torch.tensor(np.imag(s_bus), dtype=dtype, device=device)
    branch_active_t = torch.tensor(status, dtype=torch.float32, device=device)

    return CleanRoomDataset(
        grid=superset_grid,
        physics=physics,
        vr_true=vr_true,
        vi_true=vi_true,
        vref=vref_t,
        status=branch_active_t,
        pinj=pinj,
        qinj=qinj,
        time_array=time_array,
    )


# ======================================================================================================================
# 2) Superset grid: fixed indexing embedded in the artifact
# ======================================================================================================================

@dataclass
class SupersetGrid:
    """
    Fixed superset grid (canonical indexing) embedded in your "AI blob".

    Explicit shapes:
      N = number of buses
      M = number of branches

    Required tensors:
      from_bus: (M,) int64
      to_bus:   (M,) int64
      r,x,b:    (M,) float
      tap:      (M,) float (use 1.0 for lines)
      shift:    (M,) float rad (use 0.0 for lines)
      g_shunt_bus: (N,) float
      b_shunt_bus: (N,) float
      bus_type: (N,) int64 values:
         0 = slack, 1 = PV, 2 = PQ
      n_bus: int
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

    def validate(self) -> None:
        """
        Validate shapes/dtypes.

        :returns: None
        """
        if self.from_bus.dtype != torch.long or self.to_bus.dtype != torch.long:
            raise TypeError("from_bus/to_bus must be torch.long (int64).")
        if self.bus_type.dtype != torch.long:
            raise TypeError("bus_type must be torch.long (int64).")

        m = int(self.from_bus.numel())
        if int(self.to_bus.numel()) != m:
            raise ValueError("to_bus must have length M equal to from_bus length.")

        for name in ["r", "x", "b", "tap", "shift"]:
            t = getattr(self, name)
            if int(t.numel()) != m:
                raise ValueError(f"{name} must have length M.")

        n = int(self.n_bus)
        if int(self.g_shunt_bus.numel()) != n or int(self.b_shunt_bus.numel()) != n:
            raise ValueError("g_shunt_bus/b_shunt_bus must have length N.")
        if int(self.bus_type.numel()) != n:
            raise ValueError("bus_type must have length N.")

        if int(torch.min(self.from_bus).item()) < 0 or int(torch.min(self.to_bus).item()) < 0:
            raise ValueError("Bus indices must be >= 0.")
        if int(torch.max(self.from_bus).item()) >= n or int(torch.max(self.to_bus).item()) >= n:
            raise ValueError("Bus indices must be < n_bus.")





# ======================================================================================================================
# 3) Physics layer: (Vr,Vi,branch_active) -> (Pcalc,Qcalc) and flows
# ======================================================================================================================

class AcPowerFlowPhysics(nn.Module):
    """
    Deterministic AC equation evaluator.

    Runtime inputs (NO batch needed):
      vr: (...,N)
      vi: (...,N)
      branch_active: (...,M) or None

    In practice this now supports both:
      - (T,N) / (T,M)
      - (B,T,N) / (B,T,M)

    Why the extra dimension?
      - B = how many sampled windows are processed together
      - T = time steps inside each window
      - N = buses
      - M = branches

    The physics is identical. The only difference is that we evaluate
    several windows in parallel by flattening the leading dimensions.

    Outputs:
      p_bus: (T,N) net bus injections implied by V and network
      q_bus: (T,N)
      pf,qf,pt,qt: (T,M) branch-end flows

    Optional mismatch:
      If pinj_target/qinj_target provided, returns dp,dq and loss_mismatch.

    IMPORTANT:
      This does NOT solve PF. It evaluates equations.
    """

    def __init__(self, grid: SupersetGrid, dtype: torch.dtype):
        super().__init__()
        grid.validate()

        self.n_bus = int(grid.n_bus)
        self.n_branch = int(grid.from_bus.numel())
        self._dtype = dtype

        # topology
        self.register_buffer("from_bus", grid.from_bus.clone())
        self.register_buffer("to_bus", grid.to_bus.clone())

        # branch params
        self.register_buffer("r", grid.r.to(dtype=dtype).clone())
        self.register_buffer("x", grid.x.to(dtype=dtype).clone())
        self.register_buffer("b", grid.b.to(dtype=dtype).clone())
        self.register_buffer("tap", grid.tap.to(dtype=dtype).clone())
        self.register_buffer("shift", grid.shift.to(dtype=dtype).clone())

        # bus shunts
        self.register_buffer("g_shunt_bus", grid.g_shunt_bus.to(dtype=dtype).clone())
        self.register_buffer("b_shunt_bus", grid.b_shunt_bus.to(dtype=dtype).clone())

        self.register_buffer("eps_z", torch.tensor(1e-12, dtype=dtype))

    def forward(
        self,
        vr: torch.Tensor,
        vi: torch.Tensor,
        branch_active: Optional[torch.Tensor],
        chunk_size: int,
        pinj_target: Optional[torch.Tensor],
        qinj_target: Optional[torch.Tensor],
    ) -> Dict[str, torch.Tensor]:
        """
        Explicit input formats:
          vr: (...,N)
          vi: (...,N)
          branch_active: (...,M) or None
          pinj_target/qinj_target: (...,N) or None

        :param vr: voltage real
        :param vi: voltage imag
        :param branch_active: branch mask
        :param chunk_size: branch chunk size (0=no chunking)
        :param pinj_target: optional target P injections
        :param qinj_target: optional target Q injections
        :returns: dict with p_bus/q_bus and flows (+ mismatch if targets given)
        """
        if vr.shape != vi.shape:
            raise ValueError("vr and vi must have the same shape.")
        if vr.ndim < 2:
            raise ValueError("vr/vi must have at least 2 dimensions: (...,N).")

        vr_flat, lead, n = flatten_last_dim(vr)
        vi_flat, lead2, n2 = flatten_last_dim(vi)
        if lead2 != lead or n2 != n:
            raise ValueError("vr/vi mismatch after flattening.")
        if int(n) != int(self.n_bus):
            raise ValueError("vr/vi last dim must equal n_bus.")

        # After flattening, bsz means "all leading samples collapsed together".
        # For 2D inputs this is just T. For 3D inputs this is B*T.
        bsz = int(vr_flat.shape[0])
        m = int(self.n_branch)
        device = vr.device

        if branch_active is None:
            branch_active_flat = torch.ones((bsz, m), device=device, dtype=torch.float32)
        else:
            if branch_active.ndim != vr.ndim:
                raise ValueError("branch_active must have the same number of dimensions as vr/vi.")
            branch_active_flat, lead_s, m2 = flatten_last_dim(branch_active)
            if lead_s != lead:
                raise ValueError("branch_active leading dims must match vr leading dims.")
            if int(m2) != int(m):
                raise ValueError("branch_active last dim must equal n_branch.")
            branch_active_flat = branch_active_flat.to(device=device, dtype=torch.float32)

        v = as_complex(vr_flat.to(self._dtype), vi_flat.to(self._dtype))

        complex_dtype = torch.complex64 if self._dtype == torch.float32 else torch.complex128
        ibus = torch.zeros((bsz, n), device=device, dtype=complex_dtype)

        # outputs
        pf = torch.zeros((bsz, m), device=device, dtype=self._dtype)
        qf = torch.zeros((bsz, m), device=device, dtype=self._dtype)
        pt = torch.zeros((bsz, m), device=device, dtype=self._dtype)
        qt = torch.zeros((bsz, m), device=device, dtype=self._dtype)

        # params
        r = self.r.to(device=device)
        x = self.x.to(device=device)
        bch = self.b.to(device=device)
        tau = self.tap.to(device=device)
        shift = self.shift.to(device=device)

        tau_safe = torch.where(tau > 0.0, tau, torch.ones_like(tau))
        tap = complex_tap(tau_safe, shift)

        z = torch.complex(r, x)
        z_abs = torch.abs(z)
        z = torch.where(z_abs > self.eps_z, z, torch.complex(self.eps_z, torch.zeros_like(self.eps_z)))
        y = 1.0 / z
        ysh_total = torch.complex(torch.zeros_like(bch), bch)

        step = int(chunk_size) if int(chunk_size) > 0 else m
        start = 0
        while start < m:
            end = min(m, start + step)
            idx = slice(start, end)

            fb = self.from_bus[idx].to(device=device)
            tb = self.to_bus[idx].to(device=device)

            a = branch_active_flat[:, idx]
            a_c = torch.complex(a.to(self._dtype), torch.zeros_like(a.to(self._dtype)))

            y_k = y[idx].to(device=device)[None, :] * a_c
            ysh_k = ysh_total[idx].to(device=device)[None, :] * a_c
            tap_k = tap[idx].to(device=device)[None, :]

            tap_abs2 = tap_k * torch.conj(tap_k)
            ysh_half = 0.5 * ysh_k

            yff = (y_k + ysh_half) / tap_abs2
            yft = -y_k / torch.conj(tap_k)
            ytf = -y_k / tap_k
            ytt = (y_k + ysh_half)

            vf = v[:, fb]
            vt = v[:, tb]

            i_f = yff * vf + yft * vt
            i_t = ytf * vf + ytt * vt

            s_f = vf * torch.conj(i_f)
            s_t = vt * torch.conj(i_t)

            pf[:, idx] = s_f.real.to(self._dtype)
            qf[:, idx] = s_f.imag.to(self._dtype)
            pt[:, idx] = s_t.real.to(self._dtype)
            qt[:, idx] = s_t.imag.to(self._dtype)

            ibus.index_add_(1, fb, i_f)
            ibus.index_add_(1, tb, i_t)

            start = end

        gsh = self.g_shunt_bus.to(device=device).to(self._dtype)
        bsh = self.b_shunt_bus.to(device=device).to(self._dtype)
        ysh_bus = torch.complex(gsh, bsh)
        ibus = ibus + v * ysh_bus[None, :]

        sbus = v * torch.conj(ibus)
        p_bus_flat = sbus.real.to(self._dtype)
        q_bus_flat = sbus.imag.to(self._dtype)

        out: Dict[str, torch.Tensor] = {
            "p_bus": reshape_back(p_bus_flat, lead, n),
            "q_bus": reshape_back(q_bus_flat, lead, n),
            "pf": reshape_back(pf, lead, m),
            "qf": reshape_back(qf, lead, m),
            "pt": reshape_back(pt, lead, m),
            "qt": reshape_back(qt, lead, m),
        }

        if pinj_target is not None or qinj_target is not None:
            if pinj_target is None or qinj_target is None:
                raise ValueError("Provide both pinj_target and qinj_target, or neither.")
            if pinj_target.shape != vr.shape or qinj_target.shape != vr.shape:
                raise ValueError("pinj_target/qinj_target must match vr shape.")

            dp = out["p_bus"] - pinj_target.to(device=device, dtype=self._dtype)
            dq = out["q_bus"] - qinj_target.to(device=device, dtype=self._dtype)
            out["dp"] = dp
            out["dq"] = dq
            out["loss_mismatch"] = (dp * dp + dq * dq).mean()

        return out

@dataclass
class CleanRoomDataset:
    """
    Coupled VeraGrid dataset in the tensor layout expected by the clean-room solver.

    Attributes:
      grid: canonical clean-room grid
      physics: clean-room AC physics layer built on top of the grid
      vr_true: (T,N)
      vi_true: (T,N)
      vref: (T,N) complex slack-reference tensor; non-slack buses are zero
      status: (T,M)
      pinj: (T,N)
      qinj: (T,N)
      time_array: time axis from the VeraGrid results
    """
    grid: SupersetGrid
    physics: AcPowerFlowPhysics
    vr_true: torch.Tensor
    vi_true: torch.Tensor
    vref: torch.Tensor
    status: torch.Tensor
    pinj: torch.Tensor
    qinj: torch.Tensor
    time_array: np.ndarray

# ======================================================================================================================
# 4) Typed-GNN unrolled solver (paper-style, Cartesian updates)
# ======================================================================================================================

class MLP(nn.Module):
    """
    Small helper MLP: Linear -> GELU -> Linear.
    """

    def __init__(self, in_dim: int, hidden: int, out_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(int(in_dim), int(hidden)),
            nn.GELU(),
            nn.Linear(int(hidden), int(out_dim)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TypedGNNSolver(nn.Module):
    """
    Unrolled typed message-passing voltage solver.

    Inputs:
      pinj_tn:   (...,N)
      qinj_tn:   (...,N)
      branch_active_tm: (...,M)

    Outputs:
      vr_pred: (...,N)
      vi_pred: (...,N)

    The solver now supports a real batch dimension.

    Typical shapes:
      - no batching:
          pinj_tn:   (T,N)
          branch_active_tm: (T,M)
      - batched windows:
          pinj_tn:   (B,T,N)
          branch_active_tm: (B,T,M)

    Why 3D?
      - B = number of randomly sampled windows processed together
      - T = time samples inside each window
      - N = buses
      - M = branches

    Internally we flatten the leading dimensions to (B*T, ...), run the
    same typed message passing, and then reshape back.
    """

    def __init__(
        self,
        grid: SupersetGrid,
        physics: AcPowerFlowPhysics,
        embed_dim: int,
        msg_hidden: int,
        tgn_layers: int,
        msg_steps: int,
    ):
        super().__init__()
        grid.validate()

        self.n_bus = int(grid.n_bus)
        self.n_branch = int(grid.from_bus.numel())
        self.tgn_layers = int(tgn_layers)
        self.msg_steps = int(msg_steps)

        self.register_buffer("from_bus", grid.from_bus.clone())
        self.register_buffer("to_bus", grid.to_bus.clone())
        self.register_buffer("bus_type", grid.bus_type.clone())  # 0 slack, 1 PV, 2 PQ

        # branch features inspired by paper (rho, delta, b)
        r = grid.r.to(torch.float32)
        x = grid.x.to(torch.float32)
        b = grid.b.to(torch.float32)
        rho = 1.0 / torch.sqrt(r * r + x * x + 1e-12)
        delta = -torch.atan2(x, r + 1e-12)
        br_feat = torch.stack([rho, delta, b], dim=1)  # (M,3)
        self.register_buffer("branch_feat", br_feat)

        self.physics = physics

        # Bus input features:
        # [Vr, Vi, dP, dQ, Pinj, Qinj, Vm_ref, Va_ref, type_onehot3]
        # => 2 + 2 + 2 + 2 + 3 = 11 dims
        self.bus_in_dim = 11
        self.enc_bus = nn.Linear(self.bus_in_dim, int(embed_dim))
        self.enc_branch = nn.Linear(3, int(embed_dim))

        # Message passing
        self.upd_branch = MLP(in_dim=3 * int(embed_dim), hidden=int(msg_hidden), out_dim=int(embed_dim))
        self.msg_br_to_bus = MLP(in_dim=2 * int(embed_dim), hidden=int(msg_hidden), out_dim=int(embed_dim))
        self.upd_bus = MLP(in_dim=2 * int(embed_dim), hidden=int(msg_hidden), out_dim=int(embed_dim))

        # Decode ΔVr,ΔVi
        self.dec_dv = nn.Linear(int(embed_dim), 2)

        # Step scale
        self.step_scale = nn.Parameter(torch.tensor(0.05, dtype=torch.float32))

    def forward(
        self,
        pinj_tn: torch.Tensor,
        qinj_tn: torch.Tensor,
        branch_active_tm: torch.Tensor,
        vref_tn: Optional[torch.Tensor] = None,
    ):
        """
        Explicit inputs:
          pinj_tn: (...,N)
          qinj_tn: (...,N)
          branch_active_tm: (...,M)
          vref_tn: optional complex slack-reference tensor, shape (...,N)

        Output:
          (vr_pred, vi_pred) each (...,N)

        :returns: (vr_pred_tn, vi_pred_tn)
        """
        if pinj_tn.shape != qinj_tn.shape:
            raise ValueError("pinj_tn and qinj_tn must have the same shape (...,N).")
        if pinj_tn.ndim < 2:
            raise ValueError("pinj_tn and qinj_tn must have at least 2 dimensions: (...,N).")
        if branch_active_tm.ndim != pinj_tn.ndim:
            raise ValueError("branch_active_tm must have the same number of dimensions as pinj_tn.")

        pinj_flat, lead_shape, n_in = flatten_last_dim(pinj_tn)
        qinj_flat, lead_shape_q, n_q = flatten_last_dim(qinj_tn)
        branch_active_flat, lead_shape_s, m_in = flatten_last_dim(branch_active_tm)

        if lead_shape_q != lead_shape or n_q != n_in:
            raise ValueError("qinj_tn shape must match pinj_tn shape after flattening.")
        if lead_shape_s != lead_shape:
            raise ValueError("branch_active_tm leading dimensions must match pinj_tn leading dimensions.")
        if int(n_in) != int(self.n_bus):
            raise ValueError("pinj_tn last dimension must be N.")
        if int(m_in) != int(self.n_branch):
            raise ValueError("branch_active_tm last dimension must be M.")

        device = pinj_tn.device
        t_steps = int(pinj_flat.shape[0])
        n = int(self.n_bus)
        m = int(self.n_branch)

        # Bus type one-hot / masks
        bt = self.bus_type.to(device=device)
        slack = (bt == 0).to(torch.float32)
        pv = (bt == 1).to(torch.float32)
        pq = (bt == 2).to(torch.float32)
        non_slack = (bt != 0).to(torch.float32)

        vr = torch.ones((t_steps, n), device=device, dtype=torch.float32)
        vi = torch.zeros((t_steps, n), device=device, dtype=torch.float32)

        if vref_tn is not None:
            vref_flat, lead_shape_ref, n_ref = flatten_last_dim(vref_tn)
            if lead_shape_ref != lead_shape or n_ref != n:
                raise ValueError("vref_tn must match pinj_tn shape (...,N).")
            vref_flat = vref_flat.to(device=device)
            vr_ref = vref_flat.real.to(torch.float32)
            vi_ref = vref_flat.imag.to(torch.float32)
            vm_ref = torch.sqrt(vr_ref * vr_ref + vi_ref * vi_ref + 1e-12)
            va_ref = torch.atan2(vi_ref, vr_ref)
            vr = vr * non_slack[None, :] + vr_ref * slack[None, :]
            vi = vi * non_slack[None, :] + vi_ref * slack[None, :]
        else:
            vr_ref = None
            vi_ref = None
            vm_ref = torch.zeros((t_steps, n), device=device, dtype=torch.float32)
            va_ref = torch.zeros((t_steps, n), device=device, dtype=torch.float32)

        # Branch embedding base (constant)
        h_branch0 = self.enc_branch(self.branch_feat.to(device=device))  # (M,D)
        h_branch = h_branch0[None, :, :].expand(t_steps, m, -1).contiguous()  # (T,M,D)

        type_oh = torch.stack([slack, pv, pq], dim=1)          # (N,3)
        type_oh = type_oh[None, :, :].expand(t_steps, n, 3)    # (T,N,3)

        for _layer_idx in range(self.tgn_layers):
            # Compute Pcalc/Qcalc from current voltages
            out = self.physics(vr=vr, vi=vi, branch_active=branch_active_flat, chunk_size=0, pinj_target=None, qinj_target=None)
            p_calc = out["p_bus"]
            q_calc = out["q_bus"]

            # Mismatch = specified - calc
            dP = (pinj_flat - p_calc).to(torch.float32)
            dQ = (qinj_flat - q_calc).to(torch.float32)

            # Typed constraints (roughly matching paper’s compensation logic)
            dP = dP * non_slack[None, :]
            dQ = dQ * (pq.to(torch.float32))[None, :]

            # Build bus features: (T,N,9)
            bus_feat = torch.cat(
                [
                    vr[:, :, None],
                    vi[:, :, None],
                    dP[:, :, None],
                    dQ[:, :, None],
                    pinj_flat.to(torch.float32)[:, :, None],
                    qinj_flat.to(torch.float32)[:, :, None],
                    vm_ref[:, :, None],
                    va_ref[:, :, None],
                    type_oh,
                ],
                dim=2,
            )

            h_bus = self.enc_bus(bus_feat)  # (T,N,D)

            for _mp in range(self.msg_steps):
                h_branch = self._bus_to_branch_update(h_bus=h_bus, h_branch=h_branch, branch_active_tm=branch_active_flat)
                h_bus = self._branch_to_bus_update(h_bus=h_bus, h_branch=h_branch, branch_active_tm=branch_active_flat)

            dv = self.dec_dv(h_bus)  # (T,N,2)
            dvr = torch.tanh(dv[:, :, 0]) * non_slack[None, :]
            dvi = torch.tanh(dv[:, :, 1]) * non_slack[None, :]

            vr = vr + self.step_scale * dvr
            vi = vi + self.step_scale * dvi

            if vr_ref is not None:
                vr = vr * non_slack[None, :] + vr_ref * slack[None, :]
                vi = vi * non_slack[None, :] + vi_ref * slack[None, :]

        return reshape_back(vr, lead_shape, n), reshape_back(vi, lead_shape, n)

    def _bus_to_branch_update(self, h_bus: torch.Tensor, h_branch: torch.Tensor, branch_active_tm: torch.Tensor) -> torch.Tensor:
        """
        Branch update from endpoints.
        Shapes:
          h_bus: (T,N,D)
          h_branch: (T,M,D)
          branch_active_tm: (T,M)

        :returns: new h_branch (T,M,D)
        """
        device = h_bus.device
        fb = self.from_bus.to(device=device)
        tb = self.to_bus.to(device=device)

        h_f = h_bus[:, fb, :]
        h_t = h_bus[:, tb, :]
        x = torch.cat([h_branch, h_f, h_t], dim=2)
        new_h = self.upd_branch(x)

        a = branch_active_tm.to(device=device, dtype=torch.float32)[:, :, None]
        return a * new_h

    def _branch_to_bus_update(self, h_bus: torch.Tensor, h_branch: torch.Tensor, branch_active_tm: torch.Tensor) -> torch.Tensor:
        """
        Bus update from incident branches (sum aggregation).
        Shapes:
          h_bus: (T,N,D)
          h_branch: (T,M,D)
          branch_active_tm: (T,M)

        :returns: new h_bus (T,N,D)
        """
        device = h_bus.device
        t_steps = int(h_bus.shape[0])
        n = int(h_bus.shape[1])
        d = int(h_bus.shape[2])

        fb = self.from_bus.to(device=device)
        tb = self.to_bus.to(device=device)

        a = branch_active_tm.to(device=device, dtype=torch.float32)[:, :, None]

        h_f = h_bus[:, fb, :]
        x_f = torch.cat([h_branch, h_f], dim=2)
        msg_f = self.msg_br_to_bus(x_f) * a

        h_t = h_bus[:, tb, :]
        x_t = torch.cat([h_branch, h_t], dim=2)
        msg_t = self.msg_br_to_bus(x_t) * a

        agg = torch.zeros((t_steps, n, d), device=device, dtype=h_bus.dtype)
        agg.index_add_(1, fb, msg_f)
        agg.index_add_(1, tb, msg_t)

        x_bus = torch.cat([h_bus, agg], dim=2)
        return self.upd_bus(x_bus)


# ======================================================================================================================
# 5) Synthetic data + training + plotting
# ======================================================================================================================

def gauge_fix_cartesian(vr_tn: np.ndarray, vi_tn: np.ndarray, ref_bus: int):
    """
    Gauge-fix voltages by rotating each time so reference bus has angle ~ 0.

    Inputs:
      vr_tn: (T,N) numpy float32
      vi_tn: (T,N) numpy float32
    Output:
      (vr_fixed, vi_fixed) same shapes (T,N)

    :param vr_tn: voltage real
    :param vi_tn: voltage imag
    :param ref_bus: reference bus index
    :returns: (vr_fixed, vi_fixed)
    """
    v = vr_tn + 1j * vi_tn
    phi = np.angle(v[:, int(ref_bus)])
    rot = np.exp(-1j * phi)
    v2 = v * rot[:, None]
    return np.real(v2).astype(np.float32), np.imag(v2).astype(np.float32)


def gauge_fix_cartesian_torch(vr_tn: torch.Tensor, vi_tn: torch.Tensor, ref_bus: int) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Gauge-fix voltages by rotating each time so the reference bus has zero angle.

    :param vr_tn: voltage real, shape (T,N)
    :param vi_tn: voltage imag, shape (T,N)
    :param ref_bus: reference bus index
    :returns: gauge-fixed (vr, vi), each shape (T,N)
    """
    v = torch.complex(vr_tn, vi_tn)
    phi = torch.angle(v[:, int(ref_bus)])
    rot = torch.polar(torch.ones_like(phi), -phi)
    v2 = v * rot[:, None]
    return v2.real, v2.imag


def voltage_polar_loss(
    vr_pred: torch.Tensor,
    vi_pred: torch.Tensor,
    vr_true: torch.Tensor,
    vi_true: torch.Tensor,
    ref_bus: int,
) -> torch.Tensor:
    """
    Voltage loss using magnitude plus angle relative to a reference bus.

    This removes the global angle gauge while still supervising the voltage state.

    :param vr_pred: predicted real voltage, shape (T,N)
    :param vi_pred: predicted imag voltage, shape (T,N)
    :param vr_true: target real voltage, shape (T,N)
    :param vi_true: target imag voltage, shape (T,N)
    :param ref_bus: reference bus index
    :returns: scalar loss
    """
    v_pred = torch.complex(vr_pred, vi_pred)
    v_true = torch.complex(vr_true, vi_true)

    vm_pred = torch.abs(v_pred)
    vm_true = torch.abs(v_true)
    loss_vm = torch.mean((vm_pred - vm_true) ** 2)

    ang_pred = torch.angle(v_pred)
    ang_true = torch.angle(v_true)
    rel_pred = ang_pred - ang_pred[:, int(ref_bus):int(ref_bus) + 1]
    rel_true = ang_true - ang_true[:, int(ref_bus):int(ref_bus) + 1]
    ang_err = torch.atan2(torch.sin(rel_pred - rel_true), torch.cos(rel_pred - rel_true))
    loss_va = torch.mean(ang_err ** 2)

    return loss_vm + loss_va


def voltage_magnitude_loss(
    vr_pred: torch.Tensor,
    vi_pred: torch.Tensor,
    vr_true: torch.Tensor,
    vi_true: torch.Tensor,
) -> torch.Tensor:
    """
    Voltage supervision based only on magnitude.

    :param vr_pred: predicted real voltage, shape (T,N)
    :param vi_pred: predicted imag voltage, shape (T,N)
    :param vr_true: target real voltage, shape (T,N)
    :param vi_true: target imag voltage, shape (T,N)
    :returns: scalar loss
    """
    vm_pred = torch.sqrt(vr_pred * vr_pred + vi_pred * vi_pred + 1e-12)
    vm_true = torch.sqrt(vr_true * vr_true + vi_true * vi_true + 1e-12)
    return torch.mean((vm_pred - vm_true) ** 2)


def make_toy_grid(n_bus: int, n_branch: int, seed: int) -> SupersetGrid:
    """
    Create a small toy grid for a standalone demo.

    :param n_bus: N
    :param n_branch: M
    :param seed: RNG seed
    :returns: SupersetGrid
    """
    rng = np.random.default_rng(int(seed))

    fb = rng.integers(0, n_bus, size=n_branch, dtype=np.int64)
    tb = rng.integers(0, n_bus, size=n_branch, dtype=np.int64)
    for k in range(n_branch):
        if tb[k] == fb[k]:
            tb[k] = int((tb[k] + 1) % n_bus)

    r = rng.uniform(0.002, 0.03, size=n_branch).astype(np.float32)
    x = rng.uniform(0.02, 0.12, size=n_branch).astype(np.float32)
    b = rng.uniform(0.0, 0.03, size=n_branch).astype(np.float32)

    tap = np.ones(n_branch, dtype=np.float32)
    shift = np.zeros(n_branch, dtype=np.float32)

    gsh = np.zeros(n_bus, dtype=np.float32)
    bsh = np.zeros(n_bus, dtype=np.float32)

    bus_type = np.full((n_bus,), 2, dtype=np.int64)  # PQ
    bus_type[0] = 0  # slack
    if n_bus > 3:
        bus_type[1] = 1
        bus_type[2] = 1

    return SupersetGrid(
        from_bus=torch.tensor(fb, dtype=torch.long),
        to_bus=torch.tensor(tb, dtype=torch.long),
        r=torch.tensor(r, dtype=torch.float32),
        x=torch.tensor(x, dtype=torch.float32),
        b=torch.tensor(b, dtype=torch.float32),
        tap=torch.tensor(tap, dtype=torch.float32),
        shift=torch.tensor(shift, dtype=torch.float32),
        g_shunt_bus=torch.tensor(gsh, dtype=torch.float32),
        b_shunt_bus=torch.tensor(bsh, dtype=torch.float32),
        bus_type=torch.tensor(bus_type, dtype=torch.long),
        n_bus=int(n_bus),
    )


def make_synthetic_time_series(physics: AcPowerFlowPhysics, t_total: int, seed: int, outage_prob: float):
    """
    Build synthetic voltages + status, then compute consistent injections using physics.

    Outputs (torch tensors):
      vr_true: (T_total,N)
      vi_true: (T_total,N)
      status:  (T_total,M)
      pinj:    (T_total,N)
      qinj:    (T_total,N)

    :param physics: physics layer
    :param t_total: number of timesteps
    :param seed: RNG seed
    :param outage_prob: outage probability per branch per time
    :returns: (vr_true, vi_true, status, pinj, qinj)
    """
    rng = np.random.default_rng(int(seed))
    n = int(physics.n_bus)
    m = int(physics.n_branch)

    time = np.arange(t_total, dtype=np.float32)
    sys_wave = 0.01 * np.sin(2.0 * np.pi * time / 96.0)
    bus_offset = rng.normal(0.0, 0.005, size=n).astype(np.float32)

    vr = (1.0 + sys_wave[:, None] + bus_offset[None, :] + rng.normal(0.0, 0.002, size=(t_total, n))).astype(np.float32)
    vi = (rng.normal(0.0, 0.01, size=(t_total, n))).astype(np.float32)

    vr, vi = gauge_fix_cartesian(vr, vi, ref_bus=0)

    status = (rng.random((t_total, m)) > float(outage_prob)).astype(np.float32)

    device = get_module_device(physics)

    vr_t = torch.tensor(vr, dtype=torch.float32, device=device)
    vi_t = torch.tensor(vi, dtype=torch.float32, device=device)
    st_t = torch.tensor(status, dtype=torch.float32, device=device)

    with torch.no_grad():
        out = physics(vr=vr_t, vi=vi_t, branch_active=st_t, chunk_size=0, pinj_target=None, qinj_target=None)
        pinj = out["p_bus"].detach()
        qinj = out["q_bus"].detach()

    return vr_t, vi_t, st_t, pinj, qinj


def train_solver_with_windows(
    solver: TypedGNNSolver,
    physics: AcPowerFlowPhysics,
    vr_true_tn: torch.Tensor,
    vi_true_tn: torch.Tensor,
    vref_tn: Optional[torch.Tensor],
    pinj_tn: torch.Tensor,
    qinj_tn: torch.Tensor,
    branch_active_tm: torch.Tensor,
    window: int,
    steps: int,
    batch_size: int,
    accum_steps: int,
    lr: float,
    w_v: float,
    w_pf: float,
    verbose_every: int,
) -> None:
    """
    Train on random windows using time-series tensors shaped (T,N) and (T,M).

    Why are tensors now 3D inside this function?
      - The original full dataset is still stored as:
          vr_true_tn: (T_total, N)
          branch_active_tm:  (T_total, M)
      - But during training we now sample many windows at once.
      - After stacking those sampled windows, every batch becomes:
          vr_batch: (B, T_window, N)
          status_batch: (B, T_window, M)

    The dimensions mean:
      - B: how many random windows we train on in parallel
      - T_window: time steps inside each sampled window
      - N: buses
      - M: branches

    This is a real batch dimension, not a fake one. We batch over windows
    because each sampled window is an independent training example.

    The voltage supervision term is voltage magnitude only.

    :returns: None
    """
    device = next(solver.parameters()).device
    opt = torch.optim.AdamW(solver.parameters(), lr=float(lr), weight_decay=1e-6)

    t_total = int(vr_true_tn.shape[0])
    n = int(vr_true_tn.shape[1])
    m = int(branch_active_tm.shape[1])

    if vi_true_tn.shape != (t_total, n):
        raise ValueError("vi_true_tn must be (T_total,N).")
    if pinj_tn.shape != (t_total, n) or qinj_tn.shape != (t_total, n):
        raise ValueError("pinj_tn/qinj_tn must be (T_total,N).")
    if vref_tn is not None and vref_tn.shape != (t_total, n):
        raise ValueError("vref_tn must be (T_total,N).")
    if int(branch_active_tm.shape[0]) != t_total:
        raise ValueError("branch_active_tm must have T_total rows.")
    if int(solver.n_bus) != n or int(solver.n_branch) != m:
        raise ValueError("solver dimensions do not match data.")
    if t_total <= int(window):
        raise ValueError("Not enough timesteps for chosen window.")

    print("\n[train] shapes (NO batch dim):")
    print("  Vr_true:", tuple(vr_true_tn.shape), "Vi_true:", tuple(vi_true_tn.shape))
    print("  Pinj   :", tuple(pinj_tn.shape), "Qinj   :", tuple(qinj_tn.shape))
    print("  status :", tuple(branch_active_tm.shape))
    print("  window :", int(window), "batch_size:", int(batch_size), "accum_steps:", int(accum_steps))
    print("  solver unroll: TGN layers =", solver.tgn_layers, ", msg steps =", solver.msg_steps, "\n")

    solver.train()

    for step in range(1, int(steps) + 1):
        opt.zero_grad(set_to_none=True)
        v_sum = 0.0
        pf_sum = 0.0

        for _ in range(int(accum_steps)):
            # We sample B random windows and stack them into 3D tensors.
            # Example:
            #   one window voltage has shape (T_window, N)
            #   a batch of windows has shape (B, T_window, N)
            # The solver/physics now accept that 3D shape directly.
            t0_list = np.random.randint(0, t_total - int(window), size=int(batch_size))

            vr_w = torch.stack([vr_true_tn[t0:t0 + int(window)] for t0 in t0_list], dim=0).to(device)
            vi_w = torch.stack([vi_true_tn[t0:t0 + int(window)] for t0 in t0_list], dim=0).to(device)
            pinj_w = torch.stack([pinj_tn[t0:t0 + int(window)] for t0 in t0_list], dim=0).to(device)
            qinj_w = torch.stack([qinj_tn[t0:t0 + int(window)] for t0 in t0_list], dim=0).to(device)
            st_w = torch.stack([branch_active_tm[t0:t0 + int(window)] for t0 in t0_list], dim=0).to(device)

            if vref_tn is None:
                vref_w = None
            else:
                vref_w = torch.stack([vref_tn[t0:t0 + int(window)] for t0 in t0_list], dim=0).to(device)

            vr_pred, vi_pred = solver(
                pinj_tn=pinj_w,
                qinj_tn=qinj_w,
                branch_active_tm=st_w,
                vref_tn=vref_w,
            )

            if not torch.isfinite(vr_pred).all() or not torch.isfinite(vi_pred).all():
                raise RuntimeError(f"Non-finite predicted voltages encountered at training step {step}.")

            loss_v = voltage_magnitude_loss(
                vr_pred=vr_pred,
                vi_pred=vi_pred,
                vr_true=vr_w,
                vi_true=vi_w,
            )

            out = physics(vr=vr_pred, vi=vi_pred, branch_active=st_w, chunk_size=0, pinj_target=pinj_w, qinj_target=qinj_w)
            loss_pf = out["loss_mismatch"]
            if not torch.isfinite(loss_v) or not torch.isfinite(loss_pf):
                raise RuntimeError(f"Non-finite loss encountered at training step {step}.")

            loss = float(w_v) * loss_v + float(w_pf) * loss_pf
            (loss / float(accum_steps)).backward()

            v_sum += float(loss_v.detach().cpu().item())
            pf_sum += float(loss_pf.detach().cpu().item())

        torch.nn.utils.clip_grad_norm_(solver.parameters(), 1.0)
        opt.step()

        if int(verbose_every) > 0 and (step % int(verbose_every) == 0 or step == 1):
            print(
                f"[step {step:6d}] "
                f"loss_vm={v_sum/float(accum_steps):.6e}  "
                f"loss_pf={pf_sum/float(accum_steps):.6e}  "
                f"(w_v={w_v}, w_pf={w_pf})"
            )


# ======================================================================================================================
# 6) Plotting utilities (painfully clear)
# ======================================================================================================================

def rms_over_buses(x_tn: torch.Tensor) -> torch.Tensor:
    """
    Compute RMS over buses for each time step.

    Input:
      x_tn: (T,N)

    Output:
      rms_t: (T,)

    :param x_tn: tensor (T,N)
    :returns: tensor (T,)
    """
    return torch.sqrt(torch.mean(x_tn * x_tn, dim=1) + 1e-12)


def plot_test_window(
    physics: AcPowerFlowPhysics,
    vr_true: torch.Tensor,
    vi_true: torch.Tensor,
    vr_pred: torch.Tensor,
    vi_pred: torch.Tensor,
    status: torch.Tensor,
    pinj: torch.Tensor,
    qinj: torch.Tensor,
    bus_indices: list,
    branch_indices: list,
    title_prefix: str,
) -> None:
    """
    Create plots that visually show the solver works.

    Inputs (explicit):
      vr_true, vi_true: (Tw,N)
      vr_pred, vi_pred: (Tw,N)
      status: (Tw,M)
      pinj, qinj: (Tw,N)
      bus_indices: list of bus indices to plot
      branch_indices: list of branch indices to plot
      title_prefix: string

    What it plots:
      1) Vm error for chosen buses
      2) Voltage angle error for chosen buses, relative to the reference bus
      3) Voltage error RMS over time
      4) PF mismatch RMS over time: ΔP_rms(t), ΔQ_rms(t)
      5) Pf_true vs Pf_pred for chosen branches (computed via physics from voltages)

    :returns: None
    """
    with torch.no_grad():
        v_true = torch.complex(vr_true, vi_true)
        v_pred = torch.complex(vr_pred, vi_pred)
        vm_true = torch.abs(v_true).cpu().numpy()
        vm_pred = torch.abs(v_pred).cpu().numpy()
        vm_err = vm_pred - vm_true

        ref_bus = int(bus_indices[0]) if len(bus_indices) > 0 else 0
        ang_true = torch.angle(v_true)
        ang_pred = torch.angle(v_pred)
        rel_true = ang_true - ang_true[:, ref_bus:ref_bus + 1]
        rel_pred = ang_pred - ang_pred[:, ref_bus:ref_bus + 1]
        ang_err = torch.atan2(torch.sin(rel_pred - rel_true), torch.cos(rel_pred - rel_true)).cpu().numpy()

        # PF mismatch of predicted voltages w.r.t. specified injections
        out_pred = physics(vr=vr_pred, vi=vi_pred, branch_active=status, chunk_size=0, pinj_target=pinj, qinj_target=qinj)
        dp = out_pred["dp"]  # (Tw,N)
        dq = out_pred["dq"]  # (Tw,N)
        dp_rms = rms_over_buses(dp).cpu().numpy()
        dq_rms = rms_over_buses(dq).cpu().numpy()

        # Voltage error RMS
        dv_r = (vr_pred - vr_true)
        dv_i = (vi_pred - vi_true)
        v_err_rms = rms_over_buses(torch.sqrt(dv_r * dv_r + dv_i * dv_i)).cpu().numpy()

        # Flows: compare true vs pred using physics on both voltages
        out_true_flow = physics(vr=vr_true, vi=vi_true, branch_active=status, chunk_size=0, pinj_target=None, qinj_target=None)
        out_pred_flow = physics(vr=vr_pred, vi=vi_pred, branch_active=status, chunk_size=0, pinj_target=None, qinj_target=None)

        pf_true = out_true_flow["pf"].cpu().numpy()  # (Tw,M)
        pf_pred = out_pred_flow["pf"].cpu().numpy()  # (Tw,M)

    t = np.arange(int(vr_true.shape[0]))

    # 1) Vm error
    plt.figure()
    for b in bus_indices:
        plt.plot(t, vm_err[:, b], label=f"Vm error bus {b}")
    plt.title(f"{title_prefix} - Vm error (selected buses)")
    plt.xlabel("time index within window")
    plt.ylabel("Vm error (p.u.)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    # 2) Relative angle error
    plt.figure()
    for b in bus_indices:
        plt.plot(t, ang_err[:, b], label=f"Angle error bus {b}")
    plt.title(f"{title_prefix} - Relative angle error (selected buses)")
    plt.xlabel("time index within window")
    plt.ylabel("Angle error (rad)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    # 3) Voltage error RMS over time
    plt.figure()
    plt.plot(t, v_err_rms)
    plt.title(f"{title_prefix} - Voltage error RMS over buses")
    plt.xlabel("time index within window")
    plt.ylabel("RMS(|V_pred - V_true|) over buses")
    plt.grid(True)
    plt.tight_layout()

    # 4) PF mismatch RMS over time
    plt.figure()
    plt.plot(t, dp_rms, label="ΔP RMS over buses")
    plt.plot(t, dq_rms, label="ΔQ RMS over buses")
    plt.title(f"{title_prefix} - PF mismatch RMS (pred voltages vs specified injections)")
    plt.xlabel("time index within window")
    plt.ylabel("RMS mismatch")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    # 5) Pf comparison for selected branches
    if len(branch_indices) > 0:
        plt.figure()
        for e in branch_indices:
            plt.plot(t, pf_true[:, e], label=f"Pf true br {e}")
            plt.plot(t, pf_pred[:, e], linestyle="--", label=f"Pf pred br {e}")
        plt.title(f"{title_prefix} - Pf (from-end) selected branches")
        plt.xlabel("time index within window")
        plt.ylabel("Pf (p.u.)")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()

    plt.show()


# ======================================================================================================================
# 7) Main demo: end-to-end run with plots
# ======================================================================================================================

def main() -> None:
    torch.manual_seed(0)
    np.random.seed(0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float32

    # Demo sizes (keep small so it runs quickly)
    n_bus = 30
    n_branch = 60

    grid = make_toy_grid(n_bus=n_bus, n_branch=n_branch, seed=1)
    physics = AcPowerFlowPhysics(grid=grid, dtype=dtype).to(device)

    # Synthetic dataset (internally consistent)
    t_total = 1500
    vr_true, vi_true, status, pinj, qinj = make_synthetic_time_series(
        physics=physics,
        t_total=t_total,
        seed=2,
        outage_prob=0.03,
    )

    print("\n[data] NO batch dim tensors:")
    print("  Vr_true:", tuple(vr_true.shape))
    print("  Vi_true:", tuple(vi_true.shape))
    print("  status :", tuple(status.shape))
    print("  Pinj   :", tuple(pinj.shape))
    print("  Qinj   :", tuple(qinj.shape))

    # Solver hyperparams
    solver = TypedGNNSolver(
        grid=grid,
        physics=physics,
        embed_dim=64,
        msg_hidden=128,
        tgn_layers=10,
        msg_steps=2,
    ).to(device)

    train_solver_with_windows(
        solver=solver,
        physics=physics,
        vr_true_tn=vr_true,
        vi_true_tn=vi_true,
        vref_tn=None,
        pinj_tn=pinj,
        qinj_tn=qinj,
        branch_active_tm=status,
        window=96,
        steps=800,
        batch_size=8,
        accum_steps=4,
        lr=2e-3,
        w_v=0.5,
        w_pf=1.0,
        verbose_every=100,
    )

    # -------------------------
    # TEST + PLOTS on one window
    # -------------------------
    solver.eval()
    with torch.no_grad():
        t0 = 200
        tw = 200
        vr_w = vr_true[t0:t0 + tw]
        vi_w = vi_true[t0:t0 + tw]
        pinj_w = pinj[t0:t0 + tw]
        qinj_w = qinj[t0:t0 + tw]
        st_w = status[t0:t0 + tw]

        vr_pred, vi_pred = solver(pinj_tn=pinj_w, qinj_tn=qinj_w, branch_active_tm=st_w)

        out = physics(vr=vr_pred, vi=vi_pred, branch_active=st_w, chunk_size=0, pinj_target=pinj_w, qinj_target=qinj_w)
        mse_v = ((vr_pred - vr_w) ** 2 + (vi_pred - vi_w) ** 2).mean().item()
        pf_loss = out["loss_mismatch"].item()

        print("\n[test] one window numeric summary:")
        print("  voltage_mse :", float(mse_v))
        print("  pf_mismatch :", float(pf_loss))

    # Choose a few buses and branches to plot (you can change these indices)
    bus_indices = [0, 1, 2, 5]         # bus 0 is slack in our toy grid
    branch_indices = [0, 1, 2, 10]     # arbitrary branches

    plot_test_window(
        physics=physics,
        vr_true=vr_w,
        vi_true=vi_w,
        vr_pred=vr_pred,
        vi_pred=vi_pred,
        status=st_w,
        pinj=pinj_w,
        qinj=qinj_w,
        bus_indices=bus_indices,
        branch_indices=branch_indices,
        title_prefix="Typed-GNN PF Solver - Test Window",
    )

    print("\nDone.")


def main2(
    fname: str = "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal",
    embed_dim: int = 64,
    msg_hidden: int = 128,
    tgn_layers: int = 5,
    msg_steps: int = 2,
    train_window_pct: float = 10.0,
    test_window_pct: float = 20.0,
    test_start_pct: float = 50.0,
    steps: int = 800,
    batch_size: int = 8,
    accum_steps: int = 4,
    lr: float = 1e-3,
    w_v: float = 0.1,
    w_pf: float = 1.0,
    verbose_every: int = 100,
    bus_indices: Optional[list[int]] = None,
    branch_indices: Optional[list[int]] = None,
) -> None:
    """
    End-to-end VeraGrid example using the clean-room coupling.

    This function is deliberately parameterized so every knob that can
    affect shapes is explicit and then clamped against the actual dataset.
    The goal is to make it very hard to accidentally break dimensions when
    changing the example.

    Dataset shapes after coupling:
      vr_true / vi_true / pinj / qinj: (T_total, N)
      vref: (T_total, N) complex slack-reference tensor
      status: (T_total, M)

    Training-time batched window shapes:
      voltage-like tensors: (B, T_window, N)
      branch-status tensors: (B, T_window, M)

    :param fname: VeraGrid file path
    :param embed_dim: solver embedding dimension
    :param msg_hidden: hidden size of the message/update MLPs
    :param tgn_layers: number of unrolled solver layers
    :param msg_steps: message passing iterations inside each layer
    :param train_window_pct: requested training window as percentage of the full time series
    :param test_window_pct: requested evaluation window as percentage of the full time series
    :param test_start_pct: requested evaluation start as percentage of the valid start range
    :param steps: optimizer steps
    :param batch_size: windows per optimization batch
    :param accum_steps: gradient accumulation micro-steps
    :param lr: learning rate
    :param w_v: voltage magnitude loss weight
    :param w_pf: physics mismatch loss weight
    :param verbose_every: training log frequency
    :param bus_indices: optional buses to plot; invalid entries are discarded
    :param branch_indices: optional branches to plot; invalid entries are discarded
    :returns: None
    """
    torch.manual_seed(0)
    np.random.seed(0)

    grid = vg.open_file(fname)
    ts_res = vg.power_flow_ts(grid)

    dataset: CleanRoomDataset = build_clean_room_dataset_from_veragrid(
        grid=grid,
        results=ts_res,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float32


    physics = dataset.physics

    t_total = int(dataset.vr_true.shape[0])
    n_bus = int(dataset.vr_true.shape[1])
    n_branch = int(dataset.status.shape[1])

    if t_total < 2:
        raise ValueError("main2 requires at least 2 time steps in the VeraGrid time-series results.")
    if steps < 1:
        raise ValueError("steps must be >= 1.")
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1.")
    if accum_steps < 1:
        raise ValueError("accum_steps must be >= 1.")
    if not (0.0 < float(train_window_pct) <= 100.0):
        raise ValueError("train_window_pct must be in (0, 100].")
    if not (0.0 < float(test_window_pct) <= 100.0):
        raise ValueError("test_window_pct must be in (0, 100].")
    if not (0.0 <= float(test_start_pct) <= 100.0):
        raise ValueError("test_start_pct must be in [0, 100].")

    print("\n[data] NO batch dim tensors:")
    print("  Vr_true:", tuple(dataset.vr_true.shape))
    print("  Vi_true:", tuple(dataset.vi_true.shape))
    print("  status :", tuple(dataset.status.shape))
    print("  Pinj   :", tuple(dataset.pinj.shape))
    print("  Qinj   :", tuple(dataset.qinj.shape))

    solver = TypedGNNSolver(
        grid=dataset.grid,
        physics=physics,
        embed_dim=embed_dim,
        msg_hidden=msg_hidden,
        tgn_layers=tgn_layers,
        msg_steps=msg_steps,
    ).to(device)

    effective_train_window = max(1, min(int(round(t_total * float(train_window_pct) / 100.0)), t_total - 1))
    effective_test_window = max(1, min(int(round(t_total * float(test_window_pct) / 100.0)), t_total))
    max_test_start = t_total - effective_test_window
    effective_test_start = int(round(max_test_start * float(test_start_pct) / 100.0))

    print("\n[config] requested -> effective:")
    print("  train_window_pct :", float(train_window_pct), "->", int(effective_train_window), "steps")
    print("  test_window_pct  :", float(test_window_pct), "->", int(effective_test_window), "steps")
    print("  test_start_pct   :", float(test_start_pct), "->", int(effective_test_start), "start index")
    print("  batch_size   :", int(batch_size))
    print("  accum_steps  :", int(accum_steps))
    print("  embed_dim    :", int(embed_dim))
    print("  msg_hidden   :", int(msg_hidden))
    print("  tgn_layers   :", int(tgn_layers))
    print("  msg_steps    :", int(msg_steps))
    print("  lr           :", float(lr))
    print("  w_v          :", float(w_v))
    print("  w_pf         :", float(w_pf))

    train_solver_with_windows(
        solver=solver,
        physics=physics,
        vr_true_tn=dataset.vr_true,
        vi_true_tn=dataset.vi_true,
        vref_tn=dataset.vref,
        pinj_tn=dataset.pinj,
        qinj_tn=dataset.qinj,
        branch_active_tm=dataset.status,
        window=effective_train_window,
        steps=steps,
        batch_size=batch_size,
        accum_steps=accum_steps,
        lr=lr,
        w_v=w_v,
        w_pf=w_pf,
        verbose_every=verbose_every,
    )

    solver.eval()
    with torch.no_grad():
        vr_w = dataset.vr_true[effective_test_start:effective_test_start + effective_test_window]
        vi_w = dataset.vi_true[effective_test_start:effective_test_start + effective_test_window]
        vref_w = dataset.vref[effective_test_start:effective_test_start + effective_test_window]
        pinj_w = dataset.pinj[effective_test_start:effective_test_start + effective_test_window]
        qinj_w = dataset.qinj[effective_test_start:effective_test_start + effective_test_window]
        st_w = dataset.status[effective_test_start:effective_test_start + effective_test_window]

        vr_pred, vi_pred = solver(
            pinj_tn=pinj_w,
            qinj_tn=qinj_w,
            branch_active_tm=st_w,
            vref_tn=vref_w,
        )

        out = physics(vr=vr_pred, vi=vi_pred, branch_active=st_w, chunk_size=0, pinj_target=pinj_w, qinj_target=qinj_w)
        mse_v = ((vr_pred - vr_w) ** 2 + (vi_pred - vi_w) ** 2).mean().item()
        pf_loss = out["loss_mismatch"].item()

        print("\n[test] one window numeric summary:")
        print("  voltage_mse :", float(mse_v))
        print("  pf_mismatch :", float(pf_loss))

    if bus_indices is None:
        bus_indices = [0, 1, 2, 5]
    if branch_indices is None:
        branch_indices = [0, 1, 2, 10]

    bus_indices = [int(idx) for idx in bus_indices if 0 <= int(idx) < n_bus]
    branch_indices = [int(idx) for idx in branch_indices if 0 <= int(idx) < n_branch]

    if len(bus_indices) == 0:
        bus_indices = [0]

    plot_test_window(
        physics=physics,
        vr_true=vr_w,
        vi_true=vi_w,
        vr_pred=vr_pred,
        vi_pred=vi_pred,
        status=st_w,
        pinj=pinj_w,
        qinj=qinj_w,
        bus_indices=bus_indices,
        branch_indices=branch_indices,
        title_prefix="Typed-GNN PF Solver - VeraGrid Test Window",
    )

    print("\nDone.")


if __name__ == "__main__":
    main2()
