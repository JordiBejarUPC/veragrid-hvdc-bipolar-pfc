# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Shared switched-converter EMT handover case for demos, scripting and tests.

This module centralizes one scientifically traceable EMT case around the hybrid
switched VSC model. The same construction, solve path and validation rules are
reused by:

1. trunk demos for interactive inspection,
2. scripting examples for colleagues,
3. automated tests that keep the case from regressing.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any, Optional


def ensure_repo_import_paths() -> None:
    """
    Add the repository ``src`` tree to ``sys.path`` when this module is executed from ``trunk``.

    :return: None.
    """
    repo_root: Path = Path(__file__).resolve().parents[3]
    src_root: Path = repo_root / "src"
    trunk_root: Path = repo_root / "trunk"
    repo_root_text: str = str(repo_root)
    src_root_text: str = str(src_root)
    trunk_root_text: str = str(trunk_root)

    # The support module is called from ``trunk`` scripts, so the source tree must be injected
    # explicitly when the repository is used without installing the package.
    if src_root_text not in sys.path:
        sys.path.insert(0, src_root_text)
    else:
        pass

    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)
    else:
        pass

    if trunk_root_text not in sys.path:
        sys.path.insert(0, trunk_root_text)
    else:
        pass


ensure_repo_import_paths()

import matplotlib.pyplot as plt
import numpy as np

import VeraGridEngine.api as gce
from dynamics_emt.support.emt_plot_exports import get_plot_results_directory
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_transformer_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    SolverType,
)


class RuntimeTraceUpdater(BoundaryUpdateWrapper):
    """
    Boundary-updater wrapper that records one retained runtime mode trace.

    :param base_updater: Real boundary updater used by the solver.
    :param tracked_mode_idx: Runtime-parameter index to record.
    :return: None.
    """

    __slots__ = list(["base_updater", "tracked_mode_idx", "trace_t", "trace_mode"])

    def __init__(self, base_updater: BoundaryUpdateWrapper, tracked_mode_idx: int) -> None:
        self.base_updater: BoundaryUpdateWrapper = base_updater
        self.tracked_mode_idx: int = int(tracked_mode_idx)
        self.trace_t: list[float] = list()
        self.trace_mode: list[float] = list()

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Forward one boundary update and store the accepted retained mode.

        :param t: Accepted solver time.
        :param x: Accepted state vector.
        :param params: Full runtime-plus-constant parameter buffer.
        :return: None.
        """
        _unused_x: np.ndarray = x

        # The physical procedural logic must run before the recorded mode is sampled.
        self.base_updater.update(t, x, params)

        # The retained mode is recorded after the update so the trace matches the accepted EMT state.
        self.trace_t.append(float(t))
        self.trace_mode.append(float(params[self.tracked_mode_idx]))

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Delegate exact-event requests to the wrapped boundary updater.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest forced event requested by the wrapped updater.
        """
        forced_time: Optional[float] = self.base_updater.get_next_forced_event_time(t_prev, t_target)
        return forced_time

    def get_time_trace(self) -> np.ndarray:
        """
        Return the recorded time samples.

        :return: Dense time trace.
        """
        time_trace: np.ndarray = np.asarray(self.trace_t, dtype=float)
        return time_trace

    def get_mode_trace(self) -> np.ndarray:
        """
        Return the recorded runtime-mode samples.

        :return: Dense retained-mode trace.
        """
        mode_trace: np.ndarray = np.asarray(self.trace_mode, dtype=float)
        return mode_trace


class SwitchedConverterCaseContext:
    """
    Structured case context returned by the switched EMT VSC builder.

    :param problem: EMT problem instance.
    :param bus_ac: AC slack bus.
    :param bus_dc: Converter DC bus.
    :param vsc: Converter device.
    :return: None.
    """

    __slots__ = list(["problem", "bus_ac", "bus_dc", "vsc"])

    def __init__(
            self,
            problem: EmtProblemDae,
            bus_ac: gce.Bus,
            bus_dc: gce.Bus,
            vsc: gce.VSC,
    ) -> None:
        self.problem: EmtProblemDae = problem
        self.bus_ac: gce.Bus = bus_ac
        self.bus_dc: gce.Bus = bus_dc
        self.vsc: gce.VSC = vsc


class SwitchedConverterHandoverTrace:
    """
    Structured simulation results for the hybrid switched-converter handover case.

    :param t_arr: Solver time samples.
    :param mode_t_arr: Runtime-mode update times.
    :param mode_arr: Recorded switching-enabled mode.
    :param t_enable_s: Exact startup-handover time.
    :param v_bus_a_arr: Bus phase-A voltage trace.
    :param v_bus_b_arr: Bus phase-B voltage trace.
    :param v_bus_c_arr: Bus phase-C voltage trace.
    :param v_dc_arr: Converter DC-link voltage trace.
    :param i_a_arr: Converter phase-A current trace.
    :param i_b_arr: Converter phase-B current trace.
    :param i_c_arr: Converter phase-C current trace.
    :param v_conv_a_arr: Applied phase-A converter voltage seen by the plant.
    :param v_ref_a_raw_arr: Raw phase-A voltage reference before common-mode injection.
    :param v_ref_common_inj_arr: Common-mode injection signal applied by the switched bridge modulator.
    :param v_ref_a_arr: Averaged phase-A reference voltage from the bridge modulator.
    :param bridge_v_conv_a_arr: Discrete bridge phase-A voltage.
    :param i_dc_arr: Applied DC current injected to the DC network.
    :param i_dc_conv_eff_arr: Effective converter current used by the hybrid DC-link model.
    :param i_dc_conv_sw_arr: Switched bridge DC current reconstructed from gates and phase currents.
    :param i_d_arr: Plant d-axis current trace.
    :param i_q_arr: Plant q-axis current trace.
    :param i_d_ref_arr: Outer-loop d-axis current reference trace.
    :param i_q_ref_arr: Outer-loop q-axis current reference trace.
    :param P_f_arr: Filtered active-power measurement trace.
    :param Q_f_arr: Filtered reactive-power measurement trace.
    :param v_cmd_d_arr: d-axis converter voltage command trace.
    :param v_cmd_q_arr: q-axis converter voltage command trace.
    :param v_lim_arr: Converter voltage-limit trace.
    :param m_a_u_arr: Unsaturated phase-A modulation trace.
    :param gate_a_arr: Phase-A gate trace.
    :param gate_b_arr: Phase-B gate trace.
    :param gate_c_arr: Phase-C gate trace.
    :param solver_tpe: Solver enum used for the run.
    :param integration_method: Integration method used for the run.
    :param well_initialized: Initialization flag returned by the solver.
    :param converged: Convergence flag returned by the solver.
    :param initialization_requested: Initialization method requested by the EMT workflow.
    :param initialization_used: Initialization method effectively used by the EMT workflow.
    :param sim_loop_s: Integration-loop wall time in seconds.
    :param total_newton_iterations: Total Newton iterations.
    :param jacobian_evaluations: Total Jacobian evaluations.
    :param aligned_substeps: Forced aligned substeps.
    :return: None.
    """

    __slots__ = list([
        "t_arr",
        "mode_t_arr",
        "mode_arr",
        "t_enable_s",
        "v_bus_a_arr",
        "v_bus_b_arr",
        "v_bus_c_arr",
        "v_dc_arr",
        "i_a_arr",
        "i_b_arr",
        "i_c_arr",
        "v_conv_a_arr",
        "v_ref_a_raw_arr",
        "v_ref_common_inj_arr",
        "v_ref_a_arr",
        "bridge_v_conv_a_arr",
        "i_dc_arr",
        "i_dc_conv_eff_arr",
        "i_dc_conv_sw_arr",
        "i_d_arr",
        "i_q_arr",
        "i_d_ref_arr",
        "i_q_ref_arr",
        "P_f_arr",
        "Q_f_arr",
        "v_cmd_d_arr",
        "v_cmd_q_arr",
        "v_lim_arr",
        "m_a_u_arr",
        "gate_a_arr",
        "gate_b_arr",
        "gate_c_arr",
        "solver_tpe",
        "integration_method",
        "well_initialized",
        "converged",
        "initialization_requested",
        "initialization_used",
        "sim_loop_s",
        "total_newton_iterations",
        "jacobian_evaluations",
        "aligned_substeps",
    ])

    def __init__(
            self,
            t_arr: np.ndarray,
            mode_t_arr: np.ndarray,
            mode_arr: np.ndarray,
            t_enable_s: float,
            v_bus_a_arr: np.ndarray,
            v_bus_b_arr: np.ndarray,
            v_bus_c_arr: np.ndarray,
            v_dc_arr: np.ndarray,
            i_a_arr: np.ndarray,
            i_b_arr: np.ndarray,
            i_c_arr: np.ndarray,
            v_conv_a_arr: np.ndarray,
            v_ref_a_raw_arr: np.ndarray,
            v_ref_common_inj_arr: np.ndarray,
            v_ref_a_arr: np.ndarray,
            bridge_v_conv_a_arr: np.ndarray,
            i_dc_arr: np.ndarray,
            i_dc_conv_eff_arr: np.ndarray,
            i_dc_conv_sw_arr: np.ndarray,
            i_d_arr: np.ndarray,
            i_q_arr: np.ndarray,
            i_d_ref_arr: np.ndarray,
            i_q_ref_arr: np.ndarray,
            P_f_arr: np.ndarray,
            Q_f_arr: np.ndarray,
            v_cmd_d_arr: np.ndarray,
            v_cmd_q_arr: np.ndarray,
            v_lim_arr: np.ndarray,
            m_a_u_arr: np.ndarray,
            gate_a_arr: np.ndarray,
            gate_b_arr: np.ndarray,
            gate_c_arr: np.ndarray,
            solver_tpe: EmtSolverTypes,
            integration_method: DynamicIntegrationMethod,
            well_initialized: bool,
            converged: bool,
            initialization_requested: str,
            initialization_used: str,
            sim_loop_s: float,
            total_newton_iterations: float,
            jacobian_evaluations: float,
            aligned_substeps: float,
    ) -> None:
        self.t_arr: np.ndarray = t_arr
        self.mode_t_arr: np.ndarray = mode_t_arr
        self.mode_arr: np.ndarray = mode_arr
        self.t_enable_s: float = float(t_enable_s)
        self.v_bus_a_arr: np.ndarray = v_bus_a_arr
        self.v_bus_b_arr: np.ndarray = v_bus_b_arr
        self.v_bus_c_arr: np.ndarray = v_bus_c_arr
        self.v_dc_arr: np.ndarray = v_dc_arr
        self.i_a_arr: np.ndarray = i_a_arr
        self.i_b_arr: np.ndarray = i_b_arr
        self.i_c_arr: np.ndarray = i_c_arr
        self.v_conv_a_arr: np.ndarray = v_conv_a_arr
        self.v_ref_a_raw_arr: np.ndarray = v_ref_a_raw_arr
        self.v_ref_common_inj_arr: np.ndarray = v_ref_common_inj_arr
        self.v_ref_a_arr: np.ndarray = v_ref_a_arr
        self.bridge_v_conv_a_arr: np.ndarray = bridge_v_conv_a_arr
        self.i_dc_arr: np.ndarray = i_dc_arr
        self.i_dc_conv_eff_arr: np.ndarray = i_dc_conv_eff_arr
        self.i_dc_conv_sw_arr: np.ndarray = i_dc_conv_sw_arr
        self.i_d_arr: np.ndarray = i_d_arr
        self.i_q_arr: np.ndarray = i_q_arr
        self.i_d_ref_arr: np.ndarray = i_d_ref_arr
        self.i_q_ref_arr: np.ndarray = i_q_ref_arr
        self.P_f_arr: np.ndarray = P_f_arr
        self.Q_f_arr: np.ndarray = Q_f_arr
        self.v_cmd_d_arr: np.ndarray = v_cmd_d_arr
        self.v_cmd_q_arr: np.ndarray = v_cmd_q_arr
        self.v_lim_arr: np.ndarray = v_lim_arr
        self.m_a_u_arr: np.ndarray = m_a_u_arr
        self.gate_a_arr: np.ndarray = gate_a_arr
        self.gate_b_arr: np.ndarray = gate_b_arr
        self.gate_c_arr: np.ndarray = gate_c_arr
        self.solver_tpe: EmtSolverTypes = solver_tpe
        self.integration_method: DynamicIntegrationMethod = integration_method
        self.well_initialized: bool = bool(well_initialized)
        self.converged: bool = bool(converged)
        self.initialization_requested: str = initialization_requested
        self.initialization_used: str = initialization_used
        self.sim_loop_s: float = float(sim_loop_s)
        self.total_newton_iterations: float = float(total_newton_iterations)
        self.jacobian_evaluations: float = float(jacobian_evaluations)
        self.aligned_substeps: float = float(aligned_substeps)

    def get_pre_handover_mask(self, margin_s: float = 1.0e-12) -> np.ndarray:
        """
        Return the samples that are strictly before the exact handover time.

        :param margin_s: Numerical margin around the exact event time.
        :return: Boolean mask for pre-handover samples.
        """
        mask: np.ndarray = self.t_arr < (self.t_enable_s - margin_s)
        return mask

    def get_post_handover_mask(self, margin_s: float = 1.0e-12) -> np.ndarray:
        """
        Return the samples that are strictly after the exact handover time.

        :param margin_s: Numerical margin around the exact event time.
        :return: Boolean mask for post-handover samples.
        """
        mask: np.ndarray = self.t_arr > (self.t_enable_s + margin_s)
        return mask

    def get_tail_mask(self, window_s: float | None = None) -> np.ndarray:
        """
        Return a mask for the final analysis window of the trajectory.

        :param window_s: Requested tail-window duration in seconds.
        :return: Boolean mask selecting the final analysis window.
        """
        time_horizon_s: float = float(self.t_arr[-1] - self.t_arr[0])
        selected_window_s: float

        if window_s is None:
            selected_window_s = min(2.0e-3, max(5.0 * 1.0e-5, 0.2 * time_horizon_s))
        else:
            selected_window_s = float(window_s)

        start_time_s: float = float(self.t_arr[-1] - selected_window_s)
        mask: np.ndarray = self.t_arr >= start_time_s
        return mask


class SwitchedConverterPowerSweepRow:
    """
    One compact row of switched-converter power-sweep diagnostics.

    :param p_transfer_mw: Active-power transfer imposed by the DC load.
    :param well_initialized: Solver initialization flag.
    :param converged: Solver convergence flag.
    :param vdc_final: Final DC-link voltage in pu.
    :param vdc_min: Minimum DC-link voltage in pu.
    :param vdc_max: Maximum DC-link voltage in pu.
    :param i_d_ref_mean: Mean d-axis current reference over the tail window.
    :param i_d_mean: Mean d-axis current over the tail window.
    :param i_q_ref_mean: Mean q-axis current reference over the tail window.
    :param i_q_mean: Mean q-axis current over the tail window.
    :param p_f_mean: Mean filtered active power over the tail window.
    :param q_f_mean: Mean filtered reactive power over the tail window.
    :param d_axis_utilization: Mean d-axis voltage-command utilization.
    :param q_axis_utilization: Mean q-axis voltage-command utilization.
    :param current_balance_rms: RMS of ``i_A + i_B + i_C`` over the tail window.
    :return: None.
    """

    __slots__ = list([
        "p_transfer_mw",
        "well_initialized",
        "converged",
        "vdc_final",
        "vdc_min",
        "vdc_max",
        "i_d_ref_mean",
        "i_d_mean",
        "i_q_ref_mean",
        "i_q_mean",
        "p_f_mean",
        "q_f_mean",
        "d_axis_utilization",
        "q_axis_utilization",
        "current_balance_rms",
    ])

    def __init__(
            self,
            p_transfer_mw: float,
            well_initialized: bool,
            converged: bool,
            vdc_final: float,
            vdc_min: float,
            vdc_max: float,
            i_d_ref_mean: float,
            i_d_mean: float,
            i_q_ref_mean: float,
            i_q_mean: float,
            p_f_mean: float,
            q_f_mean: float,
            d_axis_utilization: float,
            q_axis_utilization: float,
            current_balance_rms: float,
    ) -> None:
        self.p_transfer_mw: float = float(p_transfer_mw)
        self.well_initialized: bool = bool(well_initialized)
        self.converged: bool = bool(converged)
        self.vdc_final: float = float(vdc_final)
        self.vdc_min: float = float(vdc_min)
        self.vdc_max: float = float(vdc_max)
        self.i_d_ref_mean: float = float(i_d_ref_mean)
        self.i_d_mean: float = float(i_d_mean)
        self.i_q_ref_mean: float = float(i_q_ref_mean)
        self.i_q_mean: float = float(i_q_mean)
        self.p_f_mean: float = float(p_f_mean)
        self.q_f_mean: float = float(q_f_mean)
        self.d_axis_utilization: float = float(d_axis_utilization)
        self.q_axis_utilization: float = float(q_axis_utilization)
        self.current_balance_rms: float = float(current_balance_rms)


class SwitchedConverterLongAnalysis:
    """
    Long-horizon diagnostics used to compare the switched bridge against its averaged reference.

    :param fit_window_s: Final time window used for the fundamental fit.
    :param frequency_hz: Fundamental frequency used for the fit.
    :param v_ref_a_raw_fund_amplitude: Fundamental amplitude of the raw phase-A bridge reference.
    :param v_ref_a_raw_fund_phase_deg: Fundamental phase of the raw phase-A bridge reference.
    :param v_ref_a_fund_amplitude: Fundamental amplitude of the averaged phase-A reference.
    :param v_ref_a_fund_phase_deg: Fundamental phase of the averaged phase-A reference.
    :param v_conv_a_bridge_fund_amplitude: Fundamental amplitude of the switched bridge phase-A voltage.
    :param v_conv_a_bridge_fund_phase_deg: Fundamental phase of the switched bridge phase-A voltage.
    :param averaged_to_raw_amplitude_ratio: Averaged/raw fundamental amplitude ratio.
    :param bridge_to_ref_amplitude_ratio: Bridge/reference fundamental amplitude ratio.
    :param bridge_minus_ref_phase_deg: Bridge minus reference phase shift in degrees.
    :param bridge_minus_ref_delay_us: Equivalent bridge-minus-reference delay in microseconds.
    :param v_ref_common_inj_rms: RMS of the common-mode injection over the fit window.
    :param v_ref_common_inj_peak: Peak absolute common-mode injection over the fit window.
    :param m_a_u_mean: Mean unsaturated phase-A modulation over the fit window.
    :param m_a_u_abs_max: Peak absolute unsaturated phase-A modulation over the fit window.
    :param i_d_ref_mean: Mean d-axis current reference over the final window.
    :param i_d_mean: Mean plant d-axis current over the final window.
    :param i_d_tracking_error: Mean d-axis tracking error over the final window.
    :param i_q_ref_mean: Mean q-axis current reference over the final window.
    :param i_q_mean: Mean plant q-axis current over the final window.
    :param i_q_tracking_error: Mean q-axis tracking error over the final window.
    :param p_f_mean: Mean filtered active power over the final window.
    :param q_f_mean: Mean filtered reactive power over the final window.
    :param d_axis_utilization: Mean d-axis voltage-command utilization.
    :param q_axis_utilization: Mean q-axis voltage-command utilization.
    :param current_balance_rms: RMS of ``i_A + i_B + i_C`` over the final window.
    :param i_pos_amplitude: Positive-sequence current amplitude.
    :param i_neg_amplitude: Negative-sequence current amplitude.
    :param i_neg_to_pos_ratio: Negative-to-positive sequence current amplitude ratio.
    :return: None.
    """

    __slots__ = list([
        "fit_window_s",
        "frequency_hz",
        "v_ref_a_raw_fund_amplitude",
        "v_ref_a_raw_fund_phase_deg",
        "v_ref_a_fund_amplitude",
        "v_ref_a_fund_phase_deg",
        "v_conv_a_bridge_fund_amplitude",
        "v_conv_a_bridge_fund_phase_deg",
        "averaged_to_raw_amplitude_ratio",
        "bridge_to_ref_amplitude_ratio",
        "bridge_minus_ref_phase_deg",
        "bridge_minus_ref_delay_us",
        "v_ref_common_inj_rms",
        "v_ref_common_inj_peak",
        "m_a_u_mean",
        "m_a_u_abs_max",
        "i_d_ref_mean",
        "i_d_mean",
        "i_d_tracking_error",
        "i_q_ref_mean",
        "i_q_mean",
        "i_q_tracking_error",
        "p_f_mean",
        "q_f_mean",
        "d_axis_utilization",
        "q_axis_utilization",
        "current_balance_rms",
        "i_pos_amplitude",
        "i_neg_amplitude",
        "i_neg_to_pos_ratio",
    ])

    def __init__(
            self,
            fit_window_s: float,
            frequency_hz: float,
            v_ref_a_raw_fund_amplitude: float,
            v_ref_a_raw_fund_phase_deg: float,
            v_ref_a_fund_amplitude: float,
            v_ref_a_fund_phase_deg: float,
            v_conv_a_bridge_fund_amplitude: float,
            v_conv_a_bridge_fund_phase_deg: float,
            averaged_to_raw_amplitude_ratio: float,
            bridge_to_ref_amplitude_ratio: float,
            bridge_minus_ref_phase_deg: float,
            bridge_minus_ref_delay_us: float,
            v_ref_common_inj_rms: float,
            v_ref_common_inj_peak: float,
            m_a_u_mean: float,
            m_a_u_abs_max: float,
            i_d_ref_mean: float,
            i_d_mean: float,
            i_d_tracking_error: float,
            i_q_ref_mean: float,
            i_q_mean: float,
            i_q_tracking_error: float,
            p_f_mean: float,
            q_f_mean: float,
            d_axis_utilization: float,
            q_axis_utilization: float,
            current_balance_rms: float,
            i_pos_amplitude: float,
            i_neg_amplitude: float,
            i_neg_to_pos_ratio: float,
    ) -> None:
        self.fit_window_s: float = float(fit_window_s)
        self.frequency_hz: float = float(frequency_hz)
        self.v_ref_a_raw_fund_amplitude: float = float(v_ref_a_raw_fund_amplitude)
        self.v_ref_a_raw_fund_phase_deg: float = float(v_ref_a_raw_fund_phase_deg)
        self.v_ref_a_fund_amplitude: float = float(v_ref_a_fund_amplitude)
        self.v_ref_a_fund_phase_deg: float = float(v_ref_a_fund_phase_deg)
        self.v_conv_a_bridge_fund_amplitude: float = float(v_conv_a_bridge_fund_amplitude)
        self.v_conv_a_bridge_fund_phase_deg: float = float(v_conv_a_bridge_fund_phase_deg)
        self.averaged_to_raw_amplitude_ratio: float = float(averaged_to_raw_amplitude_ratio)
        self.bridge_to_ref_amplitude_ratio: float = float(bridge_to_ref_amplitude_ratio)
        self.bridge_minus_ref_phase_deg: float = float(bridge_minus_ref_phase_deg)
        self.bridge_minus_ref_delay_us: float = float(bridge_minus_ref_delay_us)
        self.v_ref_common_inj_rms: float = float(v_ref_common_inj_rms)
        self.v_ref_common_inj_peak: float = float(v_ref_common_inj_peak)
        self.m_a_u_mean: float = float(m_a_u_mean)
        self.m_a_u_abs_max: float = float(m_a_u_abs_max)
        self.i_d_ref_mean: float = float(i_d_ref_mean)
        self.i_d_mean: float = float(i_d_mean)
        self.i_d_tracking_error: float = float(i_d_tracking_error)
        self.i_q_ref_mean: float = float(i_q_ref_mean)
        self.i_q_mean: float = float(i_q_mean)
        self.i_q_tracking_error: float = float(i_q_tracking_error)
        self.p_f_mean: float = float(p_f_mean)
        self.q_f_mean: float = float(q_f_mean)
        self.d_axis_utilization: float = float(d_axis_utilization)
        self.q_axis_utilization: float = float(q_axis_utilization)
        self.current_balance_rms: float = float(current_balance_rms)
        self.i_pos_amplitude: float = float(i_pos_amplitude)
        self.i_neg_amplitude: float = float(i_neg_amplitude)
        self.i_neg_to_pos_ratio: float = float(i_neg_to_pos_ratio)


def find_name_in_block(name: str, block: Block) -> Var | None:
    """
    Return one symbolic variable from a block hierarchy by name.

    :param name: Requested symbolic-variable name.
    :param block: Root symbolic block.
    :return: Matching variable or ``None``.
    """
    variable_lists: tuple[list[Var], list[Var], list[Var], list[Var], list[Var]] = (
        block.in_vars,
        block.out_vars,
        block.algebraic_vars,
        block.state_vars,
        block.diff_vars,
    )
    variable_list: list[Var]
    variable: Var
    event_variable: Var
    child_block: Block
    nested_result: Var | None

    # Every symbolic variable category must be inspected because unified blocks keep separate stores.
    for variable_list in variable_lists:
        for variable in variable_list:
            if variable.name == name:
                return variable
            else:
                pass

    # Runtime parameters are stored separately and therefore need their own scan.
    for event_variable in list(block.event_dict.keys()):
        if event_variable.name == name:
            return event_variable
        else:
            pass

    # Nested bridge and controller variables remain inside child blocks before unification.
    for child_block in block.children:
        nested_result = find_name_in_block(name=name, block=child_block)
        if nested_result is not None:
            return nested_result
        else:
            pass

    return None


def require_problem_var(problem: EmtProblemDae, var_name: str) -> Var:
    """
    Return one problem variable by name and assert that it exists.

    :param problem: EMT problem under inspection.
    :param var_name: Requested variable name.
    :return: Matching symbolic variable.
    """
    variable: Var | None = find_name_in_block(name=var_name, block=problem.sys_block)
    assert variable is not None
    return variable


def require_runtime_mode_index(problem: EmtProblemDae, mode_name: str) -> int:
    """
    Return one runtime-mode parameter index by name and assert that it exists.

    :param problem: EMT problem under inspection.
    :param mode_name: Requested runtime-mode name.
    :return: Runtime-parameter index.
    """
    runtime_mode: Var

    # Runtime modes are stored separately from state and algebraic variables.
    for runtime_mode in problem.get_runtime_mode_parameters():
        if runtime_mode.name == mode_name:
            return int(problem.uid2idx_event_params[runtime_mode.uid])
        else:
            pass

    assert False
    return -1


def compute_switched_bridge_dc_current(
        gate_a_arr: np.ndarray,
        gate_b_arr: np.ndarray,
        gate_c_arr: np.ndarray,
        i_a_arr: np.ndarray,
        i_b_arr: np.ndarray,
        i_c_arr: np.ndarray,
        k_v_conv_arr: np.ndarray,
) -> np.ndarray:
    """
    Reconstruct the switched bridge DC current from retained gate states and phase currents.

    :param gate_a_arr: Phase-A gate trace.
    :param gate_b_arr: Phase-B gate trace.
    :param gate_c_arr: Phase-C gate trace.
    :param i_a_arr: Phase-A current trace.
    :param i_b_arr: Phase-B current trace.
    :param i_c_arr: Phase-C current trace.
    :param k_v_conv_arr: Effective bridge voltage gain trace.
    :return: Switched bridge DC current trace.
    """
    gate_current_sum_arr: np.ndarray = gate_a_arr * i_a_arr + gate_b_arr * i_b_arr + gate_c_arr * i_c_arr
    gate_sum_arr: np.ndarray = gate_a_arr + gate_b_arr + gate_c_arr
    phase_current_sum_arr: np.ndarray = i_a_arr + i_b_arr + i_c_arr
    i_dc_sw_arr: np.ndarray = -2.0 * k_v_conv_arr * (gate_current_sum_arr - (gate_sum_arr * phase_current_sum_arr) / 3.0)
    return i_dc_sw_arr


def build_power_flow_options() -> PowerFlowOptions:
    """
    Build the balanced PF options used by the switched VSC EMT case.

    :return: Balanced PF options.
    """
    options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.LM,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=100,
        tolerance=1.0e-6,
        control_q=True,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    return options


def build_three_phase_power_flow_options() -> PowerFlowOptions:
    """
    Build the three-phase PF options used during EMT initialization.

    :return: Three-phase PF options.
    """
    options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1.0e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    return options


def build_emt_options(
        solver_type: EmtSolverTypes = EmtSolverTypes.Symbolic,
        initialization_method: EmtInitializationMethod = EmtInitializationMethod.Explicit,
        integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
        time_step: float = 1.0e-5,
        simulation_time: float = 1.2e-3,
        newton_max_iter: int = 20,
) -> EmtOptions:
    """
    Build the EMT options used by the switched VSC handover case.

    :param solver_type: EMT solver backend.
    :param initialization_method: EMT initialization strategy.
    :param integration_method: EMT integration method.
    :param time_step: EMT time step.
    :param simulation_time: EMT horizon.
    :param newton_max_iter: Maximum Newton iterations per local EMT substep.
    :return: EMT options instance.
    """
    options: EmtOptions = EmtOptions(
        time_step=time_step,
        simulation_time=simulation_time,
        tolerance=1.0e-6,
        solver_type=solver_type,
        integration_method=integration_method,
        initialization_method=initialization_method,
        newton_max_iter=newton_max_iter,
        verbose=0,
    )
    return options


def run_power_flow(grid: gce.MultiCircuit) -> tuple[object, object]:
    """
    Solve the balanced and three-phase power-flow problems for the switched EMT case.

    :param grid: Grid to solve.
    :return: Tuple with balanced and three-phase power-flow results.
    """
    pf_results: object = gce.power_flow(grid=grid, options=build_power_flow_options())
    return pf_results, None


def build_switched_vsc_case(
        emt_options: Optional[EmtOptions] = None,
        p_transfer_mw: float = 30.0,
        pf_seed_p_transfer_mw: float | None = None,
        omega_sw_hz: float = 1000.0,
) -> SwitchedConverterCaseContext:
    """
    Build the switched EMT VSC validation case.

    :param emt_options: Optional EMT options override.
    :param p_transfer_mw: Active-power transfer absorbed by the DC load in MW.
    :param pf_seed_p_transfer_mw: Optional active-power value used only for the PF seed.
    :param omega_sw_hz: PWM switching frequency in hertz.
    :return: Structured case context.
    """
    resolved_pf_seed_p_transfer_mw: float = float(p_transfer_mw if pf_seed_p_transfer_mw is None else pf_seed_p_transfer_mw)
    grid: gce.MultiCircuit = gce.MultiCircuit(name="Grid - Thevenin + switched EMT converter + DC load", Sbase=100.0, fbase=50.0)
    bus_ac: gce.Bus = gce.Bus(name="Bus_AC", Vnom=230.0, is_slack=True)
    bus_dc: gce.Bus = gce.Bus(name="Bus_DC", Vnom=320.0, is_dc=True)
    gen1: gce.Generator = gce.Generator(name="Gen_Thev", vset=1.0, Snom=100.0, freq=50.0, r1=0.001, x1=0.04)
    vsc: gce.VSC = gce.VSC(
        name="switched_converter_emt",
        bus_from=bus_dc,
        bus_to=bus_ac,
        rate=grid.Sbase,
        control1=ConverterControlType.Qac,
        control2=ConverterControlType.Vm_dc,
        control1_val=0.0,
        control2_val=1.0,
    )
    # The PF seed and the EMT load can be decoupled so power sweeps do not depend on PF convergence
    # at every operating point. This is useful when debugging control limits around one trusted base case.
    dc_load: gce.Load = gce.Load(name="DC_R_Load", P=resolved_pf_seed_p_transfer_mw, Q=0.0)
    bus: gce.Bus
    pf_results: object
    pf_results_3ph: object
    gen_mdl: Block
    vsc_mdl: Block
    dc_load_mdl: Block
    resolved_emt_options: EmtOptions = build_emt_options() if emt_options is None else emt_options
    problem: EmtProblemDae
    case_context: SwitchedConverterCaseContext

    # The network is intentionally compact so the handover evidence is easy to inspect and explain.
    grid.add_bus(bus_ac)
    grid.add_bus(bus_dc)
    grid.add_generator(bus_ac, gen1)
    grid.add_vsc(vsc)
    grid.add_load(bus_dc, dc_load)

    # Every bus must own an EMT shell before branch and injection models are attached.
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    # The balanced PF solution provides the operating point used by EMT seeding.
    pf_results, pf_results_3ph = run_power_flow(grid=grid)

    # After the PF seed is computed, the EMT load can be moved to the requested sweep value.
    dc_load.P = float(p_transfer_mw)

    # Every physical device receives its EMT model before the DAE is assembled.
    gen_mdl = get_generator_thevenin_rl_emt_template(vf=grid.var_factory).block
    vsc_mdl = get_switched_emt_converter(vf=grid.var_factory, name=vsc.name).block
    dc_load_mdl = get_dc_load_emt_template(vf=grid.var_factory, name="dc_load_emt_switched").block

    # Align the switched case with the pseudo-EMT reference tuning on the same physical topology.
    vsc_mdl.set_parameter_in_model(var_name=f"R_eq_{vsc.name}", new_value=0.03)
    # The switched benchmark needs a stronger AC filter than the pseudo-EMT average model so that the
    # bus voltage remains close to a sinusoidal waveform while the bridge still commutates explicitly.
    vsc_mdl.set_parameter_in_model(var_name=f"L_eq_{vsc.name}", new_value=1.0)
    vsc_mdl.set_parameter_in_model(var_name=f"pll_kp_{vsc.name}", new_value=40.0)
    vsc_mdl.set_parameter_in_model(var_name=f"pll_ki_{vsc.name}", new_value=400.0)
    vsc_mdl.set_parameter_in_model(var_name=f"i_kp_{vsc.name}", new_value=0.6)
    vsc_mdl.set_parameter_in_model(var_name=f"i_ki_{vsc.name}", new_value=50.0)
    vsc_mdl.set_parameter_in_model(var_name=f"vdc_kp_{vsc.name}", new_value=2.0)
    vsc_mdl.set_parameter_in_model(var_name=f"vdc_ki_{vsc.name}", new_value=30.0)
    vsc_mdl.set_parameter_in_model(var_name=f"q_kp_{vsc.name}", new_value=0.8)
    vsc_mdl.set_parameter_in_model(var_name=f"q_ki_{vsc.name}", new_value=20.0)
    vsc_mdl.set_parameter_in_model(var_name=f"i_max_{vsc.name}", new_value=1.3)
    vsc_mdl.set_parameter_in_model(var_name=f"m_max_{vsc.name}", new_value=0.95)
    vsc_mdl.set_parameter_in_model(var_name=f"tau_meas_{vsc.name}", new_value=0.01)
    vsc_mdl.set_parameter_in_model(var_name=f"aw_gain_{vsc.name}", new_value=0.1)
    vsc_mdl.set_parameter_in_model(var_name=f"vdc_floor_{vsc.name}", new_value=0.05)
    vsc_mdl.set_parameter_in_model(var_name=f"omega_sw_{vsc.name}", new_value=2.0 * np.pi * float(omega_sw_hz))

    set_emt_model(device=gen1, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=vsc, model=vsc_mdl, var_factory=grid.var_factory)
    set_emt_model(device=dc_load, model=dc_load_mdl, var_factory=grid.var_factory)

    # The resulting EMT problem is the single source of truth reused by demos, scripting and tests.
    problem = EmtProblemDae(
        grid=grid,
        options=resolved_emt_options,
        pf_results=pf_results,
        pf_results_3Ph=pf_results_3ph,
    )
    case_context = SwitchedConverterCaseContext(
        problem=problem,
        bus_ac=bus_ac,
        bus_dc=bus_dc,
        vsc=vsc,
    )
    return case_context


def build_switched_converter_trace(
        case_context: SwitchedConverterCaseContext,
        time_arr: np.ndarray,
        state_traj: np.ndarray,
        tracing_updater: RuntimeTraceUpdater,
        well_initialized: bool,
        converged: bool,
        runtime_stats: dict[str, float],
) -> SwitchedConverterHandoverTrace:
    """
    Extract one structured switched-converter trace object from a raw EMT trajectory.

    :param case_context: Structured case context.
    :param time_arr: EMT time vector.
    :param state_traj: EMT state trajectory.
    :param tracing_updater: Runtime-mode trace wrapper.
    :param well_initialized: Solver initialization flag.
    :param converged: Solver convergence flag.
    :param runtime_stats: Solver runtime statistics.
    :return: Structured switched-converter trace.
    """
    problem: EmtProblemDae = case_context.problem
    model_name: str = str(case_context.vsc.name)
    t_enable_var: Var = require_problem_var(problem=problem, var_name=f"t_enable_sw_{model_name}")
    t_enable_idx: int = int(problem.uid2idx_event_params[t_enable_var.uid])
    v_bus_a_var: Var = require_problem_var(problem=problem, var_name="v_A_Bus_AC_emt_template")
    v_bus_b_var: Var = require_problem_var(problem=problem, var_name="v_B_Bus_AC_emt_template")
    v_bus_c_var: Var = require_problem_var(problem=problem, var_name="v_C_Bus_AC_emt_template")
    v_dc_var: Var = require_problem_var(problem=problem, var_name=f"v_dc_{model_name}")
    i_a_var: Var = require_problem_var(problem=problem, var_name=f"i_A_{model_name}")
    i_b_var: Var = require_problem_var(problem=problem, var_name=f"i_B_{model_name}")
    i_c_var: Var = require_problem_var(problem=problem, var_name=f"i_C_{model_name}")
    v_conv_a_var: Var = require_problem_var(problem=problem, var_name=f"v_conv_a_{model_name}")
    v_ref_a_raw_var: Var = require_problem_var(problem=problem, var_name=f"v_ref_a_raw_{model_name}_plant_bridge")
    v_ref_common_inj_var: Var = require_problem_var(problem=problem, var_name=f"v_ref_common_inj_{model_name}_plant_bridge")
    v_ref_a_var: Var = require_problem_var(problem=problem, var_name=f"v_ref_a_{model_name}_plant_bridge")
    bridge_v_conv_a_var: Var = require_problem_var(problem=problem, var_name=f"v_conv_a_{model_name}_plant_bridge")
    i_dc_var: Var = require_problem_var(problem=problem, var_name=f"i_dc_{model_name}")
    i_dc_conv_eff_var: Var = require_problem_var(problem=problem, var_name=f"i_dc_conv_{model_name}")
    k_v_conv_var: Var = require_problem_var(problem=problem, var_name=f"k_v_conv_{model_name}")
    i_d_var: Var = require_problem_var(problem=problem, var_name=f"i_d_{model_name}_plant")
    i_q_var: Var = require_problem_var(problem=problem, var_name=f"i_q_{model_name}_plant")
    i_d_ref_var: Var = require_problem_var(problem=problem, var_name=f"i_d_ref_{model_name}")
    i_q_ref_var: Var = require_problem_var(problem=problem, var_name=f"i_q_ref_{model_name}")
    P_f_var: Var = require_problem_var(problem=problem, var_name=f"P_f_{model_name}")
    Q_f_var: Var = require_problem_var(problem=problem, var_name=f"Q_f_{model_name}")
    v_cmd_d_var: Var = require_problem_var(problem=problem, var_name=f"v_cmd_d_{model_name}")
    v_cmd_q_var: Var = require_problem_var(problem=problem, var_name=f"v_cmd_q_{model_name}")
    v_lim_var: Var = require_problem_var(problem=problem, var_name=f"v_lim_{model_name}")
    m_a_u_var: Var = require_problem_var(problem=problem, var_name=f"m_a_u_{model_name}_plant_bridge")
    gate_a_var: Var = require_problem_var(problem=problem, var_name=f"gate_a_{model_name}")
    gate_b_var: Var = require_problem_var(problem=problem, var_name=f"gate_b_{model_name}")
    gate_c_var: Var = require_problem_var(problem=problem, var_name=f"gate_c_{model_name}")
    gate_a_arr: np.ndarray
    gate_b_arr: np.ndarray
    gate_c_arr: np.ndarray
    i_a_arr: np.ndarray
    i_b_arr: np.ndarray
    i_c_arr: np.ndarray
    i_dc_conv_sw_arr: np.ndarray
    initialization_requested: str = ""
    initialization_used: str = ""
    trace: SwitchedConverterHandoverTrace

    if problem.initialization_report is None:
        initialization_requested = ""
        initialization_used = ""
    else:
        initialization_requested = str(problem.initialization_report.method_requested)
        initialization_used = str(problem.initialization_report.method_used)

    # The structured trace stores exactly the variables colleagues care about when reviewing the handover.
    gate_a_arr = np.array(state_traj[:, problem.get_var_idx(gate_a_var)], copy=True)
    gate_b_arr = np.array(state_traj[:, problem.get_var_idx(gate_b_var)], copy=True)
    gate_c_arr = np.array(state_traj[:, problem.get_var_idx(gate_c_var)], copy=True)
    i_a_arr = np.array(state_traj[:, problem.get_var_idx(i_a_var)], copy=True)
    i_b_arr = np.array(state_traj[:, problem.get_var_idx(i_b_var)], copy=True)
    i_c_arr = np.array(state_traj[:, problem.get_var_idx(i_c_var)], copy=True)
    i_dc_conv_sw_arr = compute_switched_bridge_dc_current(
        gate_a_arr=gate_a_arr,
        gate_b_arr=gate_b_arr,
        gate_c_arr=gate_c_arr,
        i_a_arr=i_a_arr,
        i_b_arr=i_b_arr,
        i_c_arr=i_c_arr,
        k_v_conv_arr=np.array(state_traj[:, problem.get_var_idx(k_v_conv_var)], copy=True),
    )

    trace = SwitchedConverterHandoverTrace(
        t_arr=np.array(time_arr, copy=True),
        mode_t_arr=tracing_updater.get_time_trace(),
        mode_arr=tracing_updater.get_mode_trace(),
        t_enable_s=float(problem.event_params_values[t_enable_idx]),
        v_bus_a_arr=np.array(state_traj[:, problem.get_var_idx(v_bus_a_var)], copy=True),
        v_bus_b_arr=np.array(state_traj[:, problem.get_var_idx(v_bus_b_var)], copy=True),
        v_bus_c_arr=np.array(state_traj[:, problem.get_var_idx(v_bus_c_var)], copy=True),
        v_dc_arr=np.array(state_traj[:, problem.get_var_idx(v_dc_var)], copy=True),
        i_a_arr=i_a_arr,
        i_b_arr=i_b_arr,
        i_c_arr=i_c_arr,
        v_conv_a_arr=np.array(state_traj[:, problem.get_var_idx(v_conv_a_var)], copy=True),
        v_ref_a_raw_arr=np.array(state_traj[:, problem.get_var_idx(v_ref_a_raw_var)], copy=True),
        v_ref_common_inj_arr=np.array(state_traj[:, problem.get_var_idx(v_ref_common_inj_var)], copy=True),
        v_ref_a_arr=np.array(state_traj[:, problem.get_var_idx(v_ref_a_var)], copy=True),
        bridge_v_conv_a_arr=np.array(state_traj[:, problem.get_var_idx(bridge_v_conv_a_var)], copy=True),
        i_dc_arr=np.array(state_traj[:, problem.get_var_idx(i_dc_var)], copy=True),
        i_dc_conv_eff_arr=np.array(state_traj[:, problem.get_var_idx(i_dc_conv_eff_var)], copy=True),
        i_dc_conv_sw_arr=i_dc_conv_sw_arr,
        i_d_arr=np.array(state_traj[:, problem.get_var_idx(i_d_var)], copy=True),
        i_q_arr=np.array(state_traj[:, problem.get_var_idx(i_q_var)], copy=True),
        i_d_ref_arr=np.array(state_traj[:, problem.get_var_idx(i_d_ref_var)], copy=True),
        i_q_ref_arr=np.array(state_traj[:, problem.get_var_idx(i_q_ref_var)], copy=True),
        P_f_arr=np.array(state_traj[:, problem.get_var_idx(P_f_var)], copy=True),
        Q_f_arr=np.array(state_traj[:, problem.get_var_idx(Q_f_var)], copy=True),
        v_cmd_d_arr=np.array(state_traj[:, problem.get_var_idx(v_cmd_d_var)], copy=True),
        v_cmd_q_arr=np.array(state_traj[:, problem.get_var_idx(v_cmd_q_var)], copy=True),
        v_lim_arr=np.array(state_traj[:, problem.get_var_idx(v_lim_var)], copy=True),
        m_a_u_arr=np.array(state_traj[:, problem.get_var_idx(m_a_u_var)], copy=True),
        gate_a_arr=gate_a_arr,
        gate_b_arr=gate_b_arr,
        gate_c_arr=gate_c_arr,
        solver_tpe=problem.options.solver_type,
        integration_method=problem.options.integration_method,
        well_initialized=well_initialized,
        converged=converged,
        initialization_requested=initialization_requested,
        initialization_used=initialization_used,
        sim_loop_s=float(runtime_stats.get("sim_loop_s", float("nan"))),
        total_newton_iterations=float(runtime_stats.get("total_newton_iterations", float("nan"))),
        jacobian_evaluations=float(runtime_stats.get("jacobian_evaluations", float("nan"))),
        aligned_substeps=float(runtime_stats.get("aligned_substeps", float("nan"))),
    )
    return trace


def simulate_switched_converter_handover(
        emt_options: Optional[EmtOptions] = None,
        p_transfer_mw: float = 30.0,
        pf_seed_p_transfer_mw: float | None = None,
        omega_sw_hz: float = 1000.0,
) -> SwitchedConverterHandoverTrace:
    """
    Simulate the full hybrid switched-converter case and collect handover traces.

    :param emt_options: Optional EMT options override.
    :param p_transfer_mw: Active-power transfer absorbed by the DC load in MW.
    :param pf_seed_p_transfer_mw: Optional active-power value used only for the PF seed.
    :param omega_sw_hz: PWM switching frequency in hertz.
    :return: Structured switched-converter handover trace.
    """
    case_context: SwitchedConverterCaseContext = build_switched_vsc_case(
        emt_options=emt_options,
        p_transfer_mw=p_transfer_mw,
        pf_seed_p_transfer_mw=pf_seed_p_transfer_mw,
        omega_sw_hz=omega_sw_hz,
    )
    problem: EmtProblemDae = case_context.problem
    switching_enabled_idx: int = require_runtime_mode_index(
        problem=problem,
        mode_name=f"switching_enabled_mode_{case_context.vsc.name}",
    )
    base_updater: BoundaryUpdateWrapper | None = build_boundary_updater_from_block(problem)
    tracing_updater: RuntimeTraceUpdater
    solver: Any
    time_arr: np.ndarray
    state_traj: np.ndarray
    _diff_traj: np.ndarray
    well_initialized: bool
    converged: bool
    runtime_stats: dict[str, float]
    trace: SwitchedConverterHandoverTrace

    assert base_updater is not None
    tracing_updater = RuntimeTraceUpdater(base_updater=base_updater, tracked_mode_idx=switching_enabled_idx)

    # The solver backend is selected through the normal factory so the scripting path matches production usage.
    solver = build_emt_solver(
        options=problem.options,
        problem=problem,
        t0=0.0,
        t_end=float(problem.options.simulation_time),
        h=float(problem.options.time_step),
        method=problem.options.integration_method,
    )
    time_arr, state_traj, _diff_traj, well_initialized, converged = solver.simulate(
        boundary_updater=tracing_updater,
    )
    runtime_stats = solver.get_last_runtime_stats()
    trace = build_switched_converter_trace(
        case_context=case_context,
        time_arr=time_arr,
        state_traj=state_traj,
        tracing_updater=tracing_updater,
        well_initialized=well_initialized,
        converged=converged,
        runtime_stats=runtime_stats,
    )
    return trace


def validate_switched_converter_handover(trace: SwitchedConverterHandoverTrace) -> None:
    """
    Assert that the switched converter satisfies the intended hybrid handover contract.

    :param trace: Structured switched-converter handover trace.
    :return: None.
    """
    pre_mask: np.ndarray = trace.get_pre_handover_mask()
    post_mask: np.ndarray = trace.get_post_handover_mask()
    first_enabled_indices: np.ndarray = np.flatnonzero(trace.mode_arr > 0.5)
    first_enabled_time: float
    pre_avg_voltage_error: float
    post_switched_voltage_error: float
    pre_discrete_voltage_gap: float
    post_average_voltage_gap: float
    pre_dc_gap: float
    post_dc_error: float
    gate_a_span: float
    gate_b_span: float
    gate_c_span: float

    # The scripted case is only acceptable when the solver both initializes and converges cleanly.
    assert trace.well_initialized
    assert trace.converged

    # The handover evidence must exist on both sides of the exact startup event.
    assert np.any(pre_mask)
    assert np.any(post_mask)

    # The retained startup mode must flip exactly at the configured handover time.
    assert len(first_enabled_indices) > 0
    first_enabled_time = float(trace.mode_t_arr[int(first_enabled_indices[0])])
    assert abs(first_enabled_time - trace.t_enable_s) <= 1.0e-12

    # Before handover the applied converter voltage must follow the averaged bridge reference.
    pre_avg_voltage_error = float(np.max(np.abs(trace.v_conv_a_arr[pre_mask] - trace.v_ref_a_arr[pre_mask])))
    pre_discrete_voltage_gap = float(np.max(np.abs(trace.v_conv_a_arr[pre_mask] - trace.bridge_v_conv_a_arr[pre_mask])))
    assert pre_avg_voltage_error <= 1.0e-6
    assert pre_discrete_voltage_gap >= 1.0e-3

    # After handover the applied converter voltage must coincide with the discrete bridge voltage.
    post_switched_voltage_error = float(np.max(np.abs(trace.v_conv_a_arr[post_mask] - trace.bridge_v_conv_a_arr[post_mask])))
    post_average_voltage_gap = float(np.max(np.abs(trace.v_conv_a_arr[post_mask] - trace.v_ref_a_arr[post_mask])))
    assert post_switched_voltage_error <= 1.0e-6
    assert post_average_voltage_gap >= 1.0e-3

    # The effective converter current must follow the averaged branch before handover and the
    # switched bridge current afterwards.
    pre_dc_gap = float(np.max(np.abs(trace.i_dc_conv_eff_arr[pre_mask] - trace.i_dc_conv_sw_arr[pre_mask])))
    post_dc_error = float(np.max(np.abs(trace.i_dc_conv_eff_arr[post_mask] - trace.i_dc_conv_sw_arr[post_mask])))
    assert pre_dc_gap >= 1.0e-4
    assert post_dc_error <= 1.0e-6

    # The published handover case must keep the DC voltage finite and positive.
    assert np.all(np.isfinite(trace.v_dc_arr))
    assert float(np.min(trace.v_dc_arr)) > 0.0

    # All three phase gates must keep switching; otherwise the discrete bridge is not active.
    gate_a_span = float(np.max(trace.gate_a_arr) - np.min(trace.gate_a_arr))
    gate_b_span = float(np.max(trace.gate_b_arr) - np.min(trace.gate_b_arr))
    gate_c_span = float(np.max(trace.gate_c_arr) - np.min(trace.gate_c_arr))
    assert gate_a_span > 0.5
    assert gate_b_span > 0.5
    assert gate_c_span > 0.5


def add_vertical_marker(ax: plt.Axes, time_value: float, label: str, color: str, linestyle: str) -> None:
    """
    Draw one labeled vertical marker on a plot axis.

    :param ax: Target axis.
    :param time_value: Marker time.
    :param label: Marker label.
    :param color: Marker color.
    :param linestyle: Marker line style.
    :return: None.
    """
    ax.axvline(time_value, color=color, linestyle=linestyle, linewidth=1.3, label=label)


def plot_switched_converter_handover(
        trace: SwitchedConverterHandoverTrace,
        show_plot: bool = True,
        save_path: Path | None = None,
) -> None:
    """
    Plot the main AC, DC, gate and runtime-mode handover traces.

    :param trace: Structured switched-converter handover trace.
    :param show_plot: When ``True`` the matplotlib window is displayed.
    :param save_path: Optional output path used to save the figure.
    :return: None.
    """
    fig: plt.Figure
    axes: np.ndarray
    ax_bus: plt.Axes
    ax_conv: plt.Axes
    ax_dc: plt.Axes
    ax_current: plt.Axes
    ax_gate: plt.Axes
    ax_mode: plt.Axes

    # The panels expose the exact physical contract colleagues need to review: network voltages,
    # averaged-to-discrete converter voltage handover, DC current source handover and gate activity.
    fig, axes = plt.subplots(6, 1, figsize=(11.5, 13.5), sharex=True)
    ax_bus = axes[0]
    ax_conv = axes[1]
    ax_dc = axes[2]
    ax_current = axes[3]
    ax_gate = axes[4]
    ax_mode = axes[5]

    ax_bus.plot(trace.t_arr, trace.v_bus_a_arr, label="Bus_AC phase A")
    ax_bus.plot(trace.t_arr, trace.v_bus_b_arr, label="Bus_AC phase B")
    ax_bus.plot(trace.t_arr, trace.v_bus_c_arr, label="Bus_AC phase C")
    add_vertical_marker(ax=ax_bus, time_value=trace.t_enable_s, label="handover", color="black", linestyle="-.")
    ax_bus.set_ylabel("Voltage [pu]")
    ax_bus.set_title("Hybrid switched EMT converter handover")
    ax_bus.grid(True)
    ax_bus.legend(loc="best")

    ax_conv.plot(trace.t_arr, trace.v_conv_a_arr, label="v_conv_a applied")
    ax_conv.plot(trace.t_arr, trace.v_ref_a_arr, label="v_ref_a averaged", linestyle="--")
    ax_conv.plot(trace.t_arr, trace.bridge_v_conv_a_arr, label="v_conv_a bridge", linestyle=":")
    add_vertical_marker(ax=ax_conv, time_value=trace.t_enable_s, label="handover", color="black", linestyle="-.")
    ax_conv.set_ylabel("Voltage [pu]")
    ax_conv.grid(True)
    ax_conv.legend(loc="best")

    ax_dc.plot(trace.t_arr, trace.v_dc_arr, label="v_dc")
    ax_dc.plot(trace.t_arr, trace.i_dc_arr, label="i_dc")
    ax_dc.plot(trace.t_arr, trace.i_dc_conv_eff_arr, label="i_dc_conv_eff", linestyle="--")
    ax_dc.plot(trace.t_arr, trace.i_dc_conv_sw_arr, label="i_dc_conv_sw", linestyle=":")
    add_vertical_marker(ax=ax_dc, time_value=trace.t_enable_s, label="handover", color="black", linestyle="-.")
    ax_dc.set_ylabel("DC vars [pu]")
    ax_dc.grid(True)
    ax_dc.legend(loc="best")

    ax_current.plot(trace.t_arr, trace.i_a_arr, label="i_A")
    ax_current.plot(trace.t_arr, trace.i_b_arr, label="i_B")
    ax_current.plot(trace.t_arr, trace.i_c_arr, label="i_C")
    add_vertical_marker(ax=ax_current, time_value=trace.t_enable_s, label="handover", color="black", linestyle="-.")
    ax_current.set_ylabel("Current [pu]")
    ax_current.grid(True)
    ax_current.legend(loc="best")

    ax_gate.step(trace.t_arr, trace.gate_a_arr, where="post", label="gate_a")
    ax_gate.step(trace.t_arr, trace.gate_b_arr, where="post", label="gate_b")
    ax_gate.step(trace.t_arr, trace.gate_c_arr, where="post", label="gate_c")
    add_vertical_marker(ax=ax_gate, time_value=trace.t_enable_s, label="handover", color="black", linestyle="-.")
    ax_gate.set_ylabel("Gate [-]")
    ax_gate.grid(True)
    ax_gate.legend(loc="best")

    ax_mode.step(trace.mode_t_arr, trace.mode_arr, where="post", label="switching_enabled_mode")
    add_vertical_marker(
        ax=ax_mode,
        time_value=trace.t_enable_s,
        label=f"t_enable = {trace.t_enable_s:.6e} s",
        color="black",
        linestyle="-.",
    )
    ax_mode.set_xlabel("Time [s]")
    ax_mode.set_ylabel("Mode [-]")
    ax_mode.grid(True)
    ax_mode.legend(loc="best")

    fig.tight_layout()

    if save_path is not None:
        # Saving first makes the demo robust even when the active backend does not surface a window.
        fig.savefig(save_path, dpi=180)
    else:
        pass

    if show_plot:
        plt.show()
    else:
        plt.close(fig)


def get_plot_output_path(file_name: str) -> Path:
    """
    Return the plot-results path used by switched-converter demos and scripting examples.

    :param file_name: Plot file name.
    :return: Absolute output path for the generated PNG figure.
    """
    output_dir: Path = get_plot_results_directory(
        case_name="switched_converter",
        solver_key="symbolic",
        output_root_name="plot_results",
    )
    plot_path: Path = output_dir / file_name

    return plot_path


def open_plot_file(plot_path: Path) -> None:
    """
    Open one saved plot file with the platform default viewer.

    :param plot_path: Existing plot path.
    :return: None.
    """
    if os.name == "nt":
        os.startfile(str(plot_path))
    else:
        pass


def compute_control_diagnostics(trace: SwitchedConverterHandoverTrace) -> dict[str, float]:
    """
    Compute compact control-oriented diagnostics over the final analysis window.

    :param trace: Structured switched-converter handover trace.
    :return: Dictionary with scalar diagnostics for quick engineering review.
    """
    tail_mask: np.ndarray = trace.get_tail_mask()
    current_balance_rms: float = float(np.sqrt(np.mean((trace.i_a_arr[tail_mask] + trace.i_b_arr[tail_mask] + trace.i_c_arr[tail_mask]) ** 2)))
    i_d_ref_mean: float = float(np.mean(trace.i_d_ref_arr[tail_mask]))
    i_d_mean: float = float(np.mean(trace.i_d_arr[tail_mask]))
    i_q_ref_mean: float = float(np.mean(trace.i_q_ref_arr[tail_mask]))
    i_q_mean: float = float(np.mean(trace.i_q_arr[tail_mask]))
    P_f_mean: float = float(np.mean(trace.P_f_arr[tail_mask]))
    Q_f_mean: float = float(np.mean(trace.Q_f_arr[tail_mask]))
    v_cmd_d_mean: float = float(np.mean(trace.v_cmd_d_arr[tail_mask]))
    v_cmd_q_mean: float = float(np.mean(trace.v_cmd_q_arr[tail_mask]))
    v_lim_mean: float = float(np.mean(trace.v_lim_arr[tail_mask]))
    diagnostics: dict[str, float] = dict()

    diagnostics["tail_window_s"] = float(trace.t_arr[-1] - trace.t_arr[tail_mask][0])
    diagnostics["current_balance_rms"] = current_balance_rms
    diagnostics["i_d_ref_mean"] = i_d_ref_mean
    diagnostics["i_d_mean"] = i_d_mean
    diagnostics["i_d_tracking_error"] = i_d_mean - i_d_ref_mean
    diagnostics["i_q_ref_mean"] = i_q_ref_mean
    diagnostics["i_q_mean"] = i_q_mean
    diagnostics["i_q_tracking_error"] = i_q_mean - i_q_ref_mean
    diagnostics["P_f_mean"] = P_f_mean
    diagnostics["Q_f_mean"] = Q_f_mean
    diagnostics["v_cmd_d_mean"] = v_cmd_d_mean
    diagnostics["v_cmd_q_mean"] = v_cmd_q_mean
    diagnostics["v_lim_mean"] = v_lim_mean
    diagnostics["d_axis_utilization"] = abs(v_cmd_d_mean) / max(abs(v_lim_mean), 1.0e-12)
    diagnostics["q_axis_utilization"] = abs(v_cmd_q_mean) / max(abs(v_lim_mean), 1.0e-12)
    return diagnostics


def build_power_sweep_row(
        p_transfer_mw: float,
        trace: SwitchedConverterHandoverTrace,
) -> SwitchedConverterPowerSweepRow:
    """
    Build one power-sweep diagnostics row from one switched-converter trace.

    :param p_transfer_mw: Active-power transfer imposed by the DC load in MW.
    :param trace: Structured switched-converter trace.
    :return: One compact sweep row.
    """
    control_diag: dict[str, float] = compute_control_diagnostics(trace=trace)
    row: SwitchedConverterPowerSweepRow = SwitchedConverterPowerSweepRow(
        p_transfer_mw=p_transfer_mw,
        well_initialized=trace.well_initialized,
        converged=trace.converged,
        vdc_final=float(trace.v_dc_arr[-1]),
        vdc_min=float(np.min(trace.v_dc_arr)),
        vdc_max=float(np.max(trace.v_dc_arr)),
        i_d_ref_mean=control_diag["i_d_ref_mean"],
        i_d_mean=control_diag["i_d_mean"],
        i_q_ref_mean=control_diag["i_q_ref_mean"],
        i_q_mean=control_diag["i_q_mean"],
        p_f_mean=control_diag["P_f_mean"],
        q_f_mean=control_diag["Q_f_mean"],
        d_axis_utilization=control_diag["d_axis_utilization"],
        q_axis_utilization=control_diag["q_axis_utilization"],
        current_balance_rms=control_diag["current_balance_rms"],
    )
    return row


def run_switched_converter_power_sweep(
        p_transfer_values_mw: list[float],
        emt_options: Optional[EmtOptions] = None,
        pf_seed_p_transfer_mw: float = 30.0,
) -> list[SwitchedConverterPowerSweepRow]:
    """
    Run one active-power sweep over the switched converter case.

    :param p_transfer_values_mw: Active-power values in MW to be tested.
    :param emt_options: Optional EMT options override reused for every sweep point.
    :param pf_seed_p_transfer_mw: Active-power value used to build the common PF seed.
    :return: Sweep diagnostics rows in the same order as the requested power values.
    """
    rows: list[SwitchedConverterPowerSweepRow] = list()
    p_transfer_mw: float
    trace: SwitchedConverterHandoverTrace

    # Every sweep point is solved independently so the diagnostic table stays reproducible.
    for p_transfer_mw in p_transfer_values_mw:
        trace = simulate_switched_converter_handover(
            emt_options=emt_options,
            p_transfer_mw=p_transfer_mw,
            pf_seed_p_transfer_mw=pf_seed_p_transfer_mw,
        )
        rows.append(build_power_sweep_row(p_transfer_mw=p_transfer_mw, trace=trace))

    return rows


def print_switched_converter_power_sweep(rows: list[SwitchedConverterPowerSweepRow]) -> None:
    """
    Print one compact active-power sweep table for the switched converter case.

    :param rows: Ordered sweep diagnostics rows.
    :return: None.
    """
    row: SwitchedConverterPowerSweepRow

    print("=" * 120)
    print("SWITCHED EMT CONVERTER POWER SWEEP")
    print("=" * 120)
    print("P_MW | init | conv | Vdc_fin | Vdc_min | Vdc_max | i_d_ref | i_d | i_q_ref | i_q | P_f | Q_f | d_util | q_util | i_sum_rms")
    print("-" * 120)

    for row in rows:
        print(
            f"{row.p_transfer_mw:4.0f} | "
            f"{int(row.well_initialized):4d} | "
            f"{int(row.converged):4d} | "
            f"{row.vdc_final:7.4f} | "
            f"{row.vdc_min:7.4f} | "
            f"{row.vdc_max:7.4f} | "
            f"{row.i_d_ref_mean:7.4f} | "
            f"{row.i_d_mean:7.4f} | "
            f"{row.i_q_ref_mean:8.4f} | "
            f"{row.i_q_mean:7.4f} | "
            f"{row.p_f_mean:6.4f} | "
            f"{row.q_f_mean:6.4f} | "
            f"{row.d_axis_utilization:6.4f} | "
            f"{row.q_axis_utilization:6.4f} | "
            f"{row.current_balance_rms:8.3e}"
        )


def fit_known_frequency_component(
        time_arr: np.ndarray,
        signal_arr: np.ndarray,
        frequency_hz: float,
        mask: np.ndarray,
) -> dict[str, float]:
    """
    Fit one known-frequency sinusoidal component plus DC offset to a signal window.

    :param time_arr: Full time vector.
    :param signal_arr: Full signal vector.
    :param frequency_hz: Known fundamental frequency in hertz.
    :param mask: Boolean mask selecting the fitting window.
    :return: Dictionary with amplitude, phase, offset and RMS fit error.
    """
    tt: np.ndarray = time_arr[mask]
    yy: np.ndarray = signal_arr[mask]
    omega: float = 2.0 * np.pi * float(frequency_hz)
    design_matrix: np.ndarray
    coefficients: np.ndarray
    fitted_signal: np.ndarray
    diagnostics: dict[str, float] = dict()

    if len(tt) == 0:
        diagnostics["amplitude"] = float("nan")
        diagnostics["phase_rad"] = float("nan")
        diagnostics["phase_deg"] = float("nan")
        diagnostics["offset"] = float("nan")
        diagnostics["rms_error"] = float("nan")
        return diagnostics
    else:
        pass

    design_matrix = np.column_stack(list([
        np.sin(omega * tt),
        np.cos(omega * tt),
        np.ones_like(tt),
    ]))
    coefficients, _, _, _ = np.linalg.lstsq(design_matrix, yy, rcond=None)
    fitted_signal = design_matrix @ coefficients

    diagnostics["amplitude"] = float(np.sqrt(coefficients[0] * coefficients[0] + coefficients[1] * coefficients[1]))
    diagnostics["phase_rad"] = float(np.arctan2(coefficients[1], coefficients[0]))
    diagnostics["phase_deg"] = float(np.degrees(diagnostics["phase_rad"]))
    diagnostics["offset"] = float(coefficients[2])
    diagnostics["rms_error"] = float(np.sqrt(np.mean((yy - fitted_signal) ** 2)))
    return diagnostics


def compute_voltage_fundamental_comparison_diagnostics(
        trace: SwitchedConverterHandoverTrace,
        frequency_hz: float = 50.0,
) -> dict[str, float]:
    """
    Compare the averaged voltage reference against the switched bridge fundamental component.

    :param trace: Structured switched-converter handover trace.
    :param frequency_hz: Fundamental frequency used for the fit.
    :return: Dictionary with the fitted fundamental comparison diagnostics.
    """
    period_s: float = 1.0 / float(frequency_hz)
    post_mask: np.ndarray = trace.get_post_handover_mask()
    available_post_window_s: float = float(trace.t_arr[-1] - trace.t_enable_s)
    selected_window_s: float
    start_time_s: float
    fit_mask: np.ndarray
    minimum_window_fraction: float = 0.25
    reference_fit: dict[str, float]
    bridge_fit: dict[str, float]
    diagnostics: dict[str, float] = dict()

    # When there is at least one full fundamental period after the handover, compare over the final cycle.
    if available_post_window_s >= period_s:
        selected_window_s = period_s
    else:
        selected_window_s = max(available_post_window_s, float(trace.t_arr[1] - trace.t_arr[0]))

    start_time_s = float(trace.t_arr[-1] - selected_window_s)
    fit_mask = np.logical_and(post_mask, trace.t_arr >= start_time_s)

    reference_fit = fit_known_frequency_component(
        time_arr=trace.t_arr,
        signal_arr=trace.v_ref_a_arr,
        frequency_hz=frequency_hz,
        mask=fit_mask,
    )
    bridge_fit = fit_known_frequency_component(
        time_arr=trace.t_arr,
        signal_arr=trace.bridge_v_conv_a_arr,
        frequency_hz=frequency_hz,
        mask=fit_mask,
    )

    diagnostics["fit_window_s"] = selected_window_s
    diagnostics["cycle_fraction"] = selected_window_s / max(period_s, 1.0e-12)

    # Less than a quarter cycle is not a meaningful basis to infer a 50 Hz fundamental component.
    if diagnostics["cycle_fraction"] < minimum_window_fraction:
        diagnostics["fit_valid"] = 0.0
        diagnostics["v_ref_a_fund_amplitude"] = float("nan")
        diagnostics["v_ref_a_fund_phase_deg"] = float("nan")
        diagnostics["v_ref_a_fund_offset"] = float("nan")
        diagnostics["v_ref_a_fund_rms_error"] = float("nan")
        diagnostics["v_conv_a_bridge_fund_amplitude"] = float("nan")
        diagnostics["v_conv_a_bridge_fund_phase_deg"] = float("nan")
        diagnostics["v_conv_a_bridge_fund_offset"] = float("nan")
        diagnostics["v_conv_a_bridge_fund_rms_error"] = float("nan")
        diagnostics["bridge_to_ref_amplitude_ratio"] = float("nan")
        diagnostics["bridge_minus_ref_phase_deg"] = float("nan")
        return diagnostics
    else:
        diagnostics["fit_valid"] = 1.0

    diagnostics["v_ref_a_fund_amplitude"] = reference_fit["amplitude"]
    diagnostics["v_ref_a_fund_phase_deg"] = reference_fit["phase_deg"]
    diagnostics["v_ref_a_fund_offset"] = reference_fit["offset"]
    diagnostics["v_ref_a_fund_rms_error"] = reference_fit["rms_error"]
    diagnostics["v_conv_a_bridge_fund_amplitude"] = bridge_fit["amplitude"]
    diagnostics["v_conv_a_bridge_fund_phase_deg"] = bridge_fit["phase_deg"]
    diagnostics["v_conv_a_bridge_fund_offset"] = bridge_fit["offset"]
    diagnostics["v_conv_a_bridge_fund_rms_error"] = bridge_fit["rms_error"]
    diagnostics["bridge_to_ref_amplitude_ratio"] = (
        bridge_fit["amplitude"] / max(reference_fit["amplitude"], 1.0e-12)
    )
    diagnostics["bridge_minus_ref_phase_deg"] = bridge_fit["phase_deg"] - reference_fit["phase_deg"]
    return diagnostics


def compute_sequence_component_diagnostics(
        trace: SwitchedConverterHandoverTrace,
        frequency_hz: float,
        window_s: float,
) -> dict[str, float]:
    """
    Compute positive- and negative-sequence current magnitudes over a final analysis window.

    :param trace: Structured switched-converter handover trace.
    :param frequency_hz: Fundamental frequency used for the phasor extraction.
    :param window_s: Final analysis-window duration in seconds.
    :return: Dictionary with positive/negative sequence amplitudes.
    """
    omega: float = 2.0 * np.pi * float(frequency_hz)
    start_time_s: float = float(trace.t_arr[-1] - window_s)
    mask: np.ndarray = trace.t_arr >= start_time_s
    tt: np.ndarray = trace.t_arr[mask]
    a_operator: complex = np.exp(1j * 2.0 * np.pi / 3.0)
    phasor_a: complex
    phasor_b: complex
    phasor_c: complex
    pos_seq: complex
    neg_seq: complex
    diagnostics: dict[str, float] = dict()

    if len(tt) == 0:
        diagnostics["i_pos_amplitude"] = float("nan")
        diagnostics["i_neg_amplitude"] = float("nan")
        diagnostics["i_neg_to_pos_ratio"] = float("nan")
        return diagnostics
    else:
        pass

    phasor_a = (2.0 / len(tt)) * np.sum(trace.i_a_arr[mask] * np.exp(-1j * omega * tt))
    phasor_b = (2.0 / len(tt)) * np.sum(trace.i_b_arr[mask] * np.exp(-1j * omega * tt))
    phasor_c = (2.0 / len(tt)) * np.sum(trace.i_c_arr[mask] * np.exp(-1j * omega * tt))
    pos_seq = (phasor_a + a_operator * phasor_b + (a_operator * a_operator) * phasor_c) / 3.0
    neg_seq = (phasor_a + (a_operator * a_operator) * phasor_b + a_operator * phasor_c) / 3.0

    diagnostics["i_pos_amplitude"] = float(np.abs(pos_seq))
    diagnostics["i_neg_amplitude"] = float(np.abs(neg_seq))
    diagnostics["i_neg_to_pos_ratio"] = diagnostics["i_neg_amplitude"] / max(diagnostics["i_pos_amplitude"], 1.0e-12)
    return diagnostics


def compute_long_horizon_alignment_analysis(
        trace: SwitchedConverterHandoverTrace,
        frequency_hz: float = 50.0,
        fit_window_s: float = 0.02,
) -> SwitchedConverterLongAnalysis:
    """
    Compute the long-horizon alignment analysis requested for converter debugging.

    :param trace: Structured switched-converter handover trace.
    :param frequency_hz: Fundamental frequency used for the phasor fit.
    :param fit_window_s: Final window duration used by the long-horizon analysis.
    :return: Long-horizon alignment diagnostics.
    """
    fit_mask: np.ndarray = trace.t_arr >= (trace.t_arr[-1] - fit_window_s)
    voltage_diag: dict[str, float] = compute_voltage_fundamental_comparison_diagnostics(trace=trace, frequency_hz=frequency_hz)
    raw_ref_diag: dict[str, float] = fit_known_frequency_component(
        time_arr=trace.t_arr,
        signal_arr=trace.v_ref_a_raw_arr,
        frequency_hz=frequency_hz,
        mask=fit_mask,
    )
    sequence_diag: dict[str, float] = compute_sequence_component_diagnostics(trace=trace, frequency_hz=frequency_hz, window_s=fit_window_s)
    v_ref_common_inj_rms: float = float(np.sqrt(np.mean(trace.v_ref_common_inj_arr[fit_mask] ** 2)))
    v_ref_common_inj_peak: float = float(np.max(np.abs(trace.v_ref_common_inj_arr[fit_mask])))
    m_a_u_mean: float = float(np.mean(trace.m_a_u_arr[fit_mask]))
    m_a_u_abs_max: float = float(np.max(np.abs(trace.m_a_u_arr[fit_mask])))
    bridge_minus_ref_delay_us: float = 1.0e6 * voltage_diag["bridge_minus_ref_phase_deg"] / (360.0 * frequency_hz)
    i_d_ref_mean: float = float(np.mean(trace.i_d_ref_arr[fit_mask]))
    i_d_mean: float = float(np.mean(trace.i_d_arr[fit_mask]))
    i_q_ref_mean: float = float(np.mean(trace.i_q_ref_arr[fit_mask]))
    i_q_mean: float = float(np.mean(trace.i_q_arr[fit_mask]))
    p_f_mean: float = float(np.mean(trace.P_f_arr[fit_mask]))
    q_f_mean: float = float(np.mean(trace.Q_f_arr[fit_mask]))
    v_cmd_d_mean: float = float(np.mean(trace.v_cmd_d_arr[fit_mask]))
    v_cmd_q_mean: float = float(np.mean(trace.v_cmd_q_arr[fit_mask]))
    v_lim_mean: float = float(np.mean(trace.v_lim_arr[fit_mask]))
    current_balance_rms: float = float(np.sqrt(np.mean((trace.i_a_arr[fit_mask] + trace.i_b_arr[fit_mask] + trace.i_c_arr[fit_mask]) ** 2)))
    analysis: SwitchedConverterLongAnalysis = SwitchedConverterLongAnalysis(
        fit_window_s=fit_window_s,
        frequency_hz=frequency_hz,
        v_ref_a_raw_fund_amplitude=raw_ref_diag["amplitude"],
        v_ref_a_raw_fund_phase_deg=raw_ref_diag["phase_deg"],
        v_ref_a_fund_amplitude=voltage_diag["v_ref_a_fund_amplitude"],
        v_ref_a_fund_phase_deg=voltage_diag["v_ref_a_fund_phase_deg"],
        v_conv_a_bridge_fund_amplitude=voltage_diag["v_conv_a_bridge_fund_amplitude"],
        v_conv_a_bridge_fund_phase_deg=voltage_diag["v_conv_a_bridge_fund_phase_deg"],
        averaged_to_raw_amplitude_ratio=voltage_diag["v_ref_a_fund_amplitude"] / max(raw_ref_diag["amplitude"], 1.0e-12),
        bridge_to_ref_amplitude_ratio=voltage_diag["bridge_to_ref_amplitude_ratio"],
        bridge_minus_ref_phase_deg=voltage_diag["bridge_minus_ref_phase_deg"],
        bridge_minus_ref_delay_us=bridge_minus_ref_delay_us,
        v_ref_common_inj_rms=v_ref_common_inj_rms,
        v_ref_common_inj_peak=v_ref_common_inj_peak,
        m_a_u_mean=m_a_u_mean,
        m_a_u_abs_max=m_a_u_abs_max,
        i_d_ref_mean=i_d_ref_mean,
        i_d_mean=i_d_mean,
        i_d_tracking_error=i_d_mean - i_d_ref_mean,
        i_q_ref_mean=i_q_ref_mean,
        i_q_mean=i_q_mean,
        i_q_tracking_error=i_q_mean - i_q_ref_mean,
        p_f_mean=p_f_mean,
        q_f_mean=q_f_mean,
        d_axis_utilization=abs(v_cmd_d_mean) / max(abs(v_lim_mean), 1.0e-12),
        q_axis_utilization=abs(v_cmd_q_mean) / max(abs(v_lim_mean), 1.0e-12),
        current_balance_rms=current_balance_rms,
        i_pos_amplitude=sequence_diag["i_pos_amplitude"],
        i_neg_amplitude=sequence_diag["i_neg_amplitude"],
        i_neg_to_pos_ratio=sequence_diag["i_neg_to_pos_ratio"],
    )
    return analysis


def print_long_horizon_alignment_analysis(analysis: SwitchedConverterLongAnalysis) -> None:
    """
    Print the long-horizon alignment analysis in a compact engineering format.

    :param analysis: Long-horizon switched-converter diagnostics.
    :return: None.
    """
    print("=" * 80)
    print("LONG-HORIZON SWITCHED CONVERTER ANALYSIS")
    print("=" * 80)
    print(f"Fit window [s]          : {analysis.fit_window_s: .6f}")
    print(f"Frequency [Hz]          : {analysis.frequency_hz: .2f}")
    print(f"v_ref_a_raw fund amp    : {analysis.v_ref_a_raw_fund_amplitude: .6f}")
    print(f"v_ref_a_raw phase [deg] : {analysis.v_ref_a_raw_fund_phase_deg: .6f}")
    print(f"v_ref_a fund amp [pu]   : {analysis.v_ref_a_fund_amplitude: .6f}")
    print(f"v_ref/raw amp ratio     : {analysis.averaged_to_raw_amplitude_ratio: .6f}")
    print(f"bridge fund amp [pu]    : {analysis.v_conv_a_bridge_fund_amplitude: .6f}")
    print(f"bridge/ref amp ratio    : {analysis.bridge_to_ref_amplitude_ratio: .6f}")
    print(f"bridge-ref phase [deg]  : {analysis.bridge_minus_ref_phase_deg: .6f}")
    print(f"bridge-ref delay [us]   : {analysis.bridge_minus_ref_delay_us: .6f}")
    print(f"v_ref_common_inj rms    : {analysis.v_ref_common_inj_rms: .6f}")
    print(f"v_ref_common_inj peak   : {analysis.v_ref_common_inj_peak: .6f}")
    print(f"m_a_u mean              : {analysis.m_a_u_mean: .6f}")
    print(f"m_a_u abs max           : {analysis.m_a_u_abs_max: .6f}")
    print(f"i_d_ref mean [pu]       : {analysis.i_d_ref_mean: .6f}")
    print(f"i_d mean [pu]           : {analysis.i_d_mean: .6f}")
    print(f"i_d error [pu]          : {analysis.i_d_tracking_error: .6f}")
    print(f"i_q_ref mean [pu]       : {analysis.i_q_ref_mean: .6f}")
    print(f"i_q mean [pu]           : {analysis.i_q_mean: .6f}")
    print(f"i_q error [pu]          : {analysis.i_q_tracking_error: .6f}")
    print(f"P_f mean [pu]           : {analysis.p_f_mean: .6f}")
    print(f"Q_f mean [pu]           : {analysis.q_f_mean: .6f}")
    print(f"v_cmd_d / v_lim         : {analysis.d_axis_utilization: .6f}")
    print(f"v_cmd_q / v_lim         : {analysis.q_axis_utilization: .6f}")
    print(f"Current balance rms     : {analysis.current_balance_rms: .3e}")
    print(f"I_pos amplitude [pu]    : {analysis.i_pos_amplitude: .6f}")
    print(f"I_neg amplitude [pu]    : {analysis.i_neg_amplitude: .6f}")
    print(f"I_neg / I_pos [-]       : {analysis.i_neg_to_pos_ratio: .6f}")

    if analysis.averaged_to_raw_amplitude_ratio < 0.95:
        print("Interpretation           : common-mode injection is reducing the phase-A fundamental more than expected")
    elif analysis.bridge_to_ref_amplitude_ratio > 1.1:
        print("Interpretation           : bridge fundamental appears too strong relative to the averaged reference")
    else:
        if analysis.bridge_to_ref_amplitude_ratio < 0.9:
            print("Interpretation           : bridge fundamental appears too weak relative to the averaged reference")
        else:
            if abs(analysis.i_d_tracking_error) > 0.05 or abs(analysis.i_q_tracking_error) > 0.05:
                print("Interpretation           : bridge fundamental is roughly aligned; remaining error points to dq/controller mismatch")
            else:
                print("Interpretation           : bridge fundamental and dq tracking are both reasonably aligned")


def print_switched_converter_summary(trace: SwitchedConverterHandoverTrace) -> None:
    """
    Print one concise engineering summary of the switched EMT handover run.

    :param trace: Structured switched-converter handover trace.
    :return: None.
    """
    gate_a_span: float = float(np.max(trace.gate_a_arr) - np.min(trace.gate_a_arr))
    gate_b_span: float = float(np.max(trace.gate_b_arr) - np.min(trace.gate_b_arr))
    gate_c_span: float = float(np.max(trace.gate_c_arr) - np.min(trace.gate_c_arr))
    post_mask: np.ndarray = trace.get_post_handover_mask()
    post_bridge_voltage_error: float = float(np.max(np.abs(trace.v_conv_a_arr[post_mask] - trace.bridge_v_conv_a_arr[post_mask])))
    post_bridge_current_error: float = float(np.max(np.abs(trace.i_dc_conv_eff_arr[post_mask] - trace.i_dc_conv_sw_arr[post_mask])))
    control_diag: dict[str, float] = compute_control_diagnostics(trace=trace)
    voltage_diag: dict[str, float] = compute_voltage_fundamental_comparison_diagnostics(trace=trace)

    print("=" * 80)
    print("SWITCHED EMT CONVERTER HANDOVER SUMMARY")
    print("=" * 80)
    print(f"Solver type             : {trace.solver_tpe}")
    print(f"Integration method      : {trace.integration_method}")
    print(f"Initialization requested: {trace.initialization_requested}")
    print(f"Initialization used     : {trace.initialization_used}")
    print(f"Well initialized        : {trace.well_initialized}")
    print(f"Converged               : {trace.converged}")
    print(f"Handover time [s]       : {trace.t_enable_s:.6e}")
    print(f"Final Vdc [pu]          : {float(trace.v_dc_arr[-1]): .6f}")
    print(f"Final Idc [pu]          : {float(trace.i_dc_arr[-1]): .6f}")
    print(f"Gate A span             : {gate_a_span: .3f}")
    print(f"Gate B span             : {gate_b_span: .3f}")
    print(f"Gate C span             : {gate_c_span: .3f}")
    print(f"Post handover v_conv err: {post_bridge_voltage_error: .3e}")
    print(f"Post handover i_dc err  : {post_bridge_current_error: .3e}")
    print(f"Simulation loop [s]     : {trace.sim_loop_s: .6f}")
    print(f"Newton iterations       : {trace.total_newton_iterations: .0f}")
    print(f"Jacobian evaluations    : {trace.jacobian_evaluations: .0f}")
    print(f"Aligned substeps        : {trace.aligned_substeps: .0f}")
    print("-" * 80)
    print("TAIL-WINDOW CONTROL DIAGNOSTICS")
    print("-" * 80)
    print(f"Tail window [s]         : {control_diag['tail_window_s']: .6f}")
    print(f"Current balance rms     : {control_diag['current_balance_rms']: .3e}")
    print(f"i_d_ref mean [pu]       : {control_diag['i_d_ref_mean']: .6f}")
    print(f"i_d mean [pu]           : {control_diag['i_d_mean']: .6f}")
    print(f"i_d error [pu]          : {control_diag['i_d_tracking_error']: .6f}")
    print(f"i_q_ref mean [pu]       : {control_diag['i_q_ref_mean']: .6f}")
    print(f"i_q mean [pu]           : {control_diag['i_q_mean']: .6f}")
    print(f"i_q error [pu]          : {control_diag['i_q_tracking_error']: .6f}")
    print(f"P_f mean [pu]           : {control_diag['P_f_mean']: .6f}")
    print(f"Q_f mean [pu]           : {control_diag['Q_f_mean']: .6f}")
    print(f"v_cmd_d / v_lim         : {control_diag['d_axis_utilization']: .6f}")
    print(f"v_cmd_q / v_lim         : {control_diag['q_axis_utilization']: .6f}")
    print("-" * 80)
    print("FUNDAMENTAL COMPARISON")
    print("-" * 80)
    print(f"Fit window [s]          : {voltage_diag['fit_window_s']: .6f}")
    print(f"Cycle fraction [-]      : {voltage_diag['cycle_fraction']: .6f}")
    if voltage_diag['fit_valid'] > 0.5:
        print(f"v_ref_a fund amp [pu]   : {voltage_diag['v_ref_a_fund_amplitude']: .6f}")
        print(f"v_ref_a fund phase [deg]: {voltage_diag['v_ref_a_fund_phase_deg']: .6f}")
        print(f"bridge fund amp [pu]    : {voltage_diag['v_conv_a_bridge_fund_amplitude']: .6f}")
        print(f"bridge fund phase [deg] : {voltage_diag['v_conv_a_bridge_fund_phase_deg']: .6f}")
        print(f"bridge/ref amp ratio    : {voltage_diag['bridge_to_ref_amplitude_ratio']: .6f}")
        print(f"bridge-ref phase [deg]  : {voltage_diag['bridge_minus_ref_phase_deg']: .6f}")
        print(f"v_ref fit rms err [pu]  : {voltage_diag['v_ref_a_fund_rms_error']: .6f}")
        print(f"bridge fit rms err [pu] : {voltage_diag['v_conv_a_bridge_fund_rms_error']: .6f}")
    else:
        print("Fundamental fit status  : insufficient post-handover window for a meaningful 50 Hz estimate")


def run_switched_converter_handover_case(
        enable_plot_window: bool,
        save_plot: bool,
        open_saved_plot: bool,
        plot_file_name: str,
        emt_options: Optional[EmtOptions] = None,
        p_transfer_mw: float = 30.0,
        pf_seed_p_transfer_mw: float | None = None,
        omega_sw_hz: float = 1000.0,
) -> SwitchedConverterHandoverTrace:
    """
    Run the switched converter handover case, validate it and optionally export plots.

    :param enable_plot_window: Display matplotlib figures when ``True``.
    :param save_plot: Save the figure to disk when ``True``.
    :param open_saved_plot: Open the saved plot with the platform default viewer when ``True``.
    :param plot_file_name: PNG file name used for plot export.
    :param emt_options: Optional EMT options override.
    :param p_transfer_mw: Active-power transfer absorbed by the DC load in MW.
    :param pf_seed_p_transfer_mw: Optional active-power value used only for the PF seed.
    :param omega_sw_hz: PWM switching frequency in hertz.
    :return: Structured switched-converter handover trace.
    """
    trace: SwitchedConverterHandoverTrace = simulate_switched_converter_handover(
        emt_options=emt_options,
        p_transfer_mw=p_transfer_mw,
        pf_seed_p_transfer_mw=pf_seed_p_transfer_mw,
        omega_sw_hz=omega_sw_hz,
    )
    plot_path: Path | None

    # The validation is reused interactively so every published figure corresponds to a passing case.
    validate_switched_converter_handover(trace=trace)
    print_switched_converter_summary(trace=trace)

    if save_plot:
        plot_path = get_plot_output_path(file_name=plot_file_name)
    else:
        plot_path = None

    plot_switched_converter_handover(
        trace=trace,
        show_plot=enable_plot_window,
        save_path=plot_path,
    )

    if plot_path is not None:
        print(f"Plot saved to: {plot_path}")

        if open_saved_plot:
            open_plot_file(plot_path=plot_path)
        else:
            pass
    else:
        pass

    return trace
