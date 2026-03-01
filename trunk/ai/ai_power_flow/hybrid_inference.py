# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Hybrid GNN + native power-flow refinement utilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

import numpy as np
import torch
import VeraGridEngine as vg
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc

from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import EvaluationMetrics
from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import GeneralPurposeTypedGNNSolver
from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import GraphSpec
from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import MultiGridDataset
from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import voltage_magnitude_loss

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit


@dataclass(frozen=True)
class HybridRefinementConfig:
    """
    Configuration for native power-flow refinement.

    :param max_iter: maximum native solver iterations
    :param verbose: native solver verbosity
    """

    max_iter: int
    verbose: int


@dataclass(frozen=True)
class GnnPredictionResult:
    """
    Pure GNN prediction result for one window.

    :param vr_pred: predicted real voltage, shape ``(Tw, N)``
    :param vi_pred: predicted imaginary voltage, shape ``(Tw, N)``
    :param start_idx: effective start index
    :param window: effective window length
    """

    vr_pred: torch.Tensor
    vi_pred: torch.Tensor
    start_idx: int
    window: int


@dataclass(frozen=True)
class NativeRefinementResult:
    """
    Native refinement result for one window.

    :param voltage_refined: refined complex voltage, shape ``(Tw, N)``
    """

    voltage_refined: np.ndarray


@dataclass(frozen=True)
class HybridInferenceResult:
    """
    Full hybrid inference result.

    :param gnn_prediction: GNN warm-start prediction
    :param native_refinement: native refined voltage
    :param gnn_metrics: GNN-only metrics against the dataset target
    :param refined_metrics: refined metrics against the dataset target
    """

    gnn_prediction: GnnPredictionResult
    native_refinement: NativeRefinementResult
    gnn_metrics: EvaluationMetrics
    refined_metrics: EvaluationMetrics


def build_native_power_flow_options(config: HybridRefinementConfig) -> object:
    """
    Build VeraGrid native power-flow options.

    :param config: refinement configuration
    :returns: native power-flow options object
    """
    options: object = vg.PowerFlowOptions(
        solver_type=vg.SolverType.NR,
        max_iter=int(config.max_iter),
        verbose=int(config.verbose),
    )
    return options


def predict_voltage_window_with_gnn(
    solver: GeneralPurposeTypedGNNSolver,
    dataset: MultiGridDataset,
    window: int,
    start_idx: int = 0,
) -> GnnPredictionResult:
    """
    Predict one dataset window with the GNN only.

    :param solver: trained solver
    :param dataset: evaluation dataset
    :param window: requested window length
    :param start_idx: requested start index
    :returns: GNN prediction result
    """
    window_int: int = int(window)
    start_idx_clamped: int = int(max(0, min(int(start_idx), dataset.n_time - window_int)))
    tw: slice = slice(start_idx_clamped, start_idx_clamped + window_int)

    solver.eval()
    with torch.no_grad():
        vr_pred: torch.Tensor
        vi_pred: torch.Tensor
        vr_pred, vi_pred = solver(
            graph=dataset.graph,
            pinj_tn=dataset.pinj[tw],
            qinj_tn=dataset.qinj[tw],
            branch_active_tm=dataset.branch_active[tw],
            vref_tn=dataset.vref[tw],
            time_features_tk=dataset.time_features[tw],
        )

    result: GnnPredictionResult = GnnPredictionResult(
        vr_pred=vr_pred,
        vi_pred=vi_pred,
        start_idx=start_idx_clamped,
        window=window_int,
    )
    return result


def refine_snapshot_with_native_power_flow(
    grid: "MultiCircuit",
    t_idx: int,
    predicted_voltage: np.ndarray,
    config: HybridRefinementConfig,
) -> np.ndarray:
    """
    Refine one time step with the native power-flow solver using the GNN voltage as initial guess.

    :param grid: source grid
    :param t_idx: time index
    :param predicted_voltage: complex predicted voltage, shape ``(N,)``
    :param config: refinement configuration
    :returns: refined complex voltage, shape ``(N,)``
    """
    # The refinement algorithm is:
    # 1. compile the numerical circuit at the requested time step
    # 2. overwrite the compiled initial voltage guess with the GNN prediction
    # 3. run the native NR power flow on that compiled circuit
    # 4. return the refined voltage
    nc = compile_numerical_circuit_at(circuit=grid, t_idx=int(t_idx))
    nc.bus_data.Vbus = predicted_voltage.copy()
    options: object = build_native_power_flow_options(config=config)
    pf_result: object = multi_island_pf_nc(nc=nc, options=options)
    refined_voltage: np.ndarray = np.asarray(pf_result.voltage)
    return refined_voltage


def refine_window_with_native_power_flow(
    file_name: str,
    gnn_prediction: GnnPredictionResult,
    default_hours_number: int,
    config: HybridRefinementConfig,
) -> NativeRefinementResult:
    """
    Refine one predicted window with the native power-flow solver.

    :param file_name: original grid file name
    :param gnn_prediction: GNN warm-start prediction
    :param default_hours_number: repeated time points for snapshot grids
    :param config: refinement configuration
    :returns: native refinement result
    """
    grid: MultiCircuit = vg.open_file(file_name)
    if not grid.has_time_series:
        grid.create_profiles(steps=int(default_hours_number), step_length=1, step_unit="h")
    else:
        pass

    window: int = int(gnn_prediction.window)
    start_idx: int = int(gnn_prediction.start_idx)
    voltage_refined: np.ndarray = np.empty(
        (window, int(gnn_prediction.vr_pred.shape[1])),
        dtype=np.complex128,
    )

    local_idx: int
    for local_idx in range(window):
        predicted_voltage: np.ndarray = (
            gnn_prediction.vr_pred[local_idx].detach().cpu().numpy()
            + 1j * gnn_prediction.vi_pred[local_idx].detach().cpu().numpy()
        )
        voltage_refined[local_idx, :] = refine_snapshot_with_native_power_flow(
            grid=grid,
            t_idx=start_idx + local_idx,
            predicted_voltage=predicted_voltage,
            config=config,
        )

    result: NativeRefinementResult = NativeRefinementResult(voltage_refined=voltage_refined)
    return result


def compute_voltage_metrics_from_prediction(
    dataset: MultiGridDataset,
    start_idx: int,
    window: int,
    vr_pred: torch.Tensor,
    vi_pred: torch.Tensor,
) -> EvaluationMetrics:
    """
    Compute scalar voltage metrics from a predicted window.

    :param dataset: evaluation dataset
    :param start_idx: start index
    :param window: window length
    :param vr_pred: predicted real voltage
    :param vi_pred: predicted imaginary voltage
    :returns: evaluation metrics
    """
    tw: slice = slice(int(start_idx), int(start_idx) + int(window))
    voltage_mse: float = float(
        (((vr_pred - dataset.vr_true[tw]) ** 2) + ((vi_pred - dataset.vi_true[tw]) ** 2)).mean().item()
    )
    vm_mse: float = float(
        voltage_magnitude_loss(
            vr_pred=vr_pred,
            vi_pred=vi_pred,
            vr_true=dataset.vr_true[tw],
            vi_true=dataset.vi_true[tw],
        ).item()
    )
    metrics: EvaluationMetrics = EvaluationMetrics(
        voltage_mse=voltage_mse,
        voltage_magnitude_mse=vm_mse,
        pf_mismatch=-1.0,
    )
    return metrics


def compute_voltage_metrics_from_native_refinement(
    dataset: MultiGridDataset,
    start_idx: int,
    window: int,
    refined_voltage: np.ndarray,
) -> EvaluationMetrics:
    """
    Compute scalar voltage metrics from a native-refined window.

    :param dataset: evaluation dataset
    :param start_idx: start index
    :param window: window length
    :param refined_voltage: refined complex voltage
    :returns: evaluation metrics
    """
    tw: slice = slice(int(start_idx), int(start_idx) + int(window))
    vr_refined: torch.Tensor = torch.tensor(
        np.real(refined_voltage),
        dtype=dataset.vr_true.dtype,
        device=dataset.vr_true.device,
    )
    vi_refined: torch.Tensor = torch.tensor(
        np.imag(refined_voltage),
        dtype=dataset.vi_true.dtype,
        device=dataset.vi_true.device,
    )
    metrics: EvaluationMetrics = compute_voltage_metrics_from_prediction(
        dataset=dataset,
        start_idx=start_idx,
        window=window,
        vr_pred=vr_refined,
        vi_pred=vi_refined,
    )
    return metrics


def predict_and_refine_dataset_window(
    solver: GeneralPurposeTypedGNNSolver,
    dataset: MultiGridDataset,
    file_name: str,
    window: int,
    start_idx: int,
    default_hours_number: int,
    refinement_config: HybridRefinementConfig,
) -> HybridInferenceResult:
    """
    Run GNN prediction and native refinement on one dataset window.

    :param solver: trained solver
    :param dataset: evaluation dataset
    :param file_name: original file name
    :param window: window length
    :param start_idx: requested start index
    :param default_hours_number: repeated time points for snapshot grids
    :param refinement_config: refinement configuration
    :returns: hybrid inference result
    """
    gnn_prediction: GnnPredictionResult = predict_voltage_window_with_gnn(
        solver=solver,
        dataset=dataset,
        window=window,
        start_idx=start_idx,
    )
    native_refinement: NativeRefinementResult = refine_window_with_native_power_flow(
        file_name=file_name,
        gnn_prediction=gnn_prediction,
        default_hours_number=default_hours_number,
        config=refinement_config,
    )
    gnn_metrics: EvaluationMetrics = compute_voltage_metrics_from_prediction(
        dataset=dataset,
        start_idx=gnn_prediction.start_idx,
        window=gnn_prediction.window,
        vr_pred=gnn_prediction.vr_pred,
        vi_pred=gnn_prediction.vi_pred,
    )
    refined_metrics: EvaluationMetrics = compute_voltage_metrics_from_native_refinement(
        dataset=dataset,
        start_idx=gnn_prediction.start_idx,
        window=gnn_prediction.window,
        refined_voltage=native_refinement.voltage_refined,
    )
    result: HybridInferenceResult = HybridInferenceResult(
        gnn_prediction=gnn_prediction,
        native_refinement=native_refinement,
        gnn_metrics=gnn_metrics,
        refined_metrics=refined_metrics,
    )
    return result
