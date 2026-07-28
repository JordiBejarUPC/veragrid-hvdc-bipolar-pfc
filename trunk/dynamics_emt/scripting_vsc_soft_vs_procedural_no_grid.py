# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path
import os
import sys
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def ensure_repo_import_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src"
    trunk_root = repo_root / "trunk"
    for path in (str(src_root), str(trunk_root), str(repo_root), str(Path(__file__).resolve().parent)):
        if path not in sys.path:
            sys.path.insert(0, path)


ensure_repo_import_paths()

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes

from dynamics_emt.support.switched_converter_handover_case import get_plot_output_path
from scripting_vsc_soft_vs_procedural_switched_compare import SOFT_SIGN_LAMDA, find_problem_var_by_prefix, set_init_if_present


def get_soft_switched_emt_converter(vf: VarFactory, name: str) -> None:
    """
    Reject the removed soft-switched production-converter path explicitly.

    :param vf: Shared EMT variable factory.
    :param name: Symbolic model name.
    :return: None.
    """
    raise RuntimeError(
        "soft switched full-converter comparison is disabled because the production converter templates were restored"
    )


def suffixed_plot_file_name(file_name: str, plot_suffix: str) -> str:
    """
    Append an optional suffix before the PNG extension.

    :param file_name: Base PNG file name.
    :param plot_suffix: Suffix appended before the extension, or empty string.
    :return: Suffixed PNG file name.
    """
    if plot_suffix == "":
        suffixed_name: str = file_name
    else:
        path: Path = Path(file_name)
        suffixed_name = f"{path.stem}_{plot_suffix}{path.suffix}"
    return suffixed_name


def inverse_park_phase_refs(theta_value: float, v_cmd_d: float, v_cmd_q: float, v_cmd_0: float) -> tuple[float, float, float]:
    """
    Convert converter dq0 voltage commands to abc phase references.

    :param theta_value: Park angle in radians.
    :param v_cmd_d: D-axis voltage command.
    :param v_cmd_q: Q-axis voltage command.
    :param v_cmd_0: Zero-sequence voltage command.
    :return: Phase voltage references in abc order.
    """
    theta_b: float = theta_value - 2.0 * np.pi / 3.0
    theta_c: float = theta_value + 2.0 * np.pi / 3.0
    phase_refs: tuple[float, float, float] = (
        v_cmd_d * np.sin(theta_value) - v_cmd_q * np.cos(theta_value) + v_cmd_0,
        v_cmd_d * np.sin(theta_b) - v_cmd_q * np.cos(theta_b) + v_cmd_0,
        v_cmd_d * np.sin(theta_c) - v_cmd_q * np.cos(theta_c) + v_cmd_0,
    )
    return phase_refs


def _init_value(problem: NoGridConverterProblem, prefix: str, default: float = 0.0) -> float:
    var = find_problem_var_by_prefix(problem, prefix)
    if var is None:
        return default
    return float(problem.init_guess.get(var.uid, default))


def _runtime_value(problem: NoGridConverterProblem, prefix: str, default: float = 0.0) -> float:
    var = find_problem_var_by_prefix(problem, prefix)
    if var is None or var.uid not in problem.uid2idx_event_params:
        return default
    return float(problem.event_params_values[problem.uid2idx_event_params[var.uid]])


def seed_no_grid_soft_bridge(problem: NoGridConverterProblem) -> None:
    theta = _init_value(problem, "theta_pll", 0.0)
    omega_base = _runtime_value(problem, "omega_base", 2.0 * np.pi * 50.0)
    v_cmd_d = _init_value(problem, "v_cmd_d", np.sqrt(2.0))
    v_cmd_q = _init_value(problem, "v_cmd_q", 0.0)
    v_cmd_0 = _init_value(problem, "v_cmd_0", 0.0)
    v_dc = _init_value(problem, "v_dc", 1.0)
    k_v_conv = _init_value(problem, "k_v_conv", 1.0)
    m_max = _runtime_value(problem, "m_max", 0.95)
    vdc_floor = _runtime_value(problem, "vdc_floor", 0.05)
    omega_sw = _runtime_value(problem, "omega_sw", 2.0 * np.pi * 1000.0)
    carrier_enable = 0.0
    carrier = 0.0
    v_dc_eff = max(v_dc, vdc_floor)
    v_mod_scale = max(k_v_conv * v_dc_eff, 1.0e-10)
    v_leg_scale = k_v_conv * v_dc_eff
    theta_pwm = theta + carrier_enable * omega_base * np.pi / (2.0 * max(omega_sw, 1.0e-10))

    refs_raw = inverse_park_phase_refs(theta_value=theta, v_cmd_d=v_cmd_d, v_cmd_q=v_cmd_q, v_cmd_0=v_cmd_0)
    refs_pwm = inverse_park_phase_refs(theta_value=theta_pwm, v_cmd_d=v_cmd_d, v_cmd_q=v_cmd_q, v_cmd_0=v_cmd_0)
    common_raw = 0.5 * (max(refs_raw) + min(refs_raw))
    common_pwm = 0.5 * (max(refs_pwm) + min(refs_pwm))
    refs = tuple(ref - common_raw for ref in refs_raw)
    refs_pwm = tuple(ref - common_pwm for ref in refs_pwm)
    m_u_values = tuple(ref / v_mod_scale for ref in refs_pwm)
    m_values = tuple(float(np.clip(m_u, -m_max, m_max)) for m_u in m_u_values)
    gates = []
    for phase, raw_ref, ref, pwm_ref, m_u_value, m_value in zip(("a", "b", "c"), refs_raw, refs, refs_pwm, m_u_values, m_values):
        set_init_if_present(problem, f"v_ref_{phase}_raw_switched_converter_emt_plant_bridge", raw_ref)
        set_init_if_present(problem, f"v_ref_{phase}_switched_converter_emt_plant_bridge", ref)
        set_init_if_present(problem, f"v_ref_{phase}_pwm_switched_converter_emt_plant_bridge", pwm_ref)
        set_init_if_present(problem, f"m_{phase}_u_switched_converter_emt_plant_bridge", m_u_value)
        set_init_if_present(problem, f"m_{phase}_switched_converter_emt_plant_bridge", m_value)
        x_value = m_value - carrier
        radicand = x_value * x_value + SOFT_SIGN_LAMDA
        denom = float(np.sqrt(radicand))
        softsign = x_value / denom
        gate = 0.5 * (1.0 + softsign)
        gates.append(gate)
        set_init_if_present(problem, f"softsign_x_aux_pwm_{phase}_switched_converter_emt_plant_bridge", x_value)
        set_init_if_present(problem, f"softsign_radicand_pwm_{phase}_switched_converter_emt_plant_bridge", radicand)
        set_init_if_present(problem, f"softsign_denom_a_pwm_{phase}_switched_converter_emt_plant_bridge", denom)
        set_init_if_present(problem, f"softsign_denom_b_pwm_{phase}_switched_converter_emt_plant_bridge", denom)
        set_init_if_present(problem, f"softsign_pwm_{phase}_switched_converter_emt_plant_bridge", softsign)
        set_init_if_present(problem, f"gate_pwm_{phase}_switched_converter_emt_plant_bridge", gate)
        set_init_if_present(problem, f"gate_{phase}_switched_converter_emt_plant_bridge", gate)
        diff_var = find_problem_var_by_prefix(problem, f"dt_gate_{phase}_switched_converter_emt_plant_bridge")
        if diff_var is not None:
            problem.diff_init_guess[diff_var.uid] = 0.0

    v_leg_a = (2.0 * gates[0] - 1.0) * v_leg_scale
    v_leg_b = (2.0 * gates[1] - 1.0) * v_leg_scale
    v_leg_c = (2.0 * gates[2] - 1.0) * v_leg_scale
    v_common = (v_leg_a + v_leg_b + v_leg_c) / 3.0
    v_conv_a = v_leg_a - v_common
    v_conv_b = v_leg_b - v_common
    v_conv_c = v_leg_c - v_common
    theta_b = theta - 2.0 * np.pi / 3.0
    theta_c = theta + 2.0 * np.pi / 3.0
    v_conv_d = (2.0 / 3.0) * (np.sin(theta) * v_conv_a + np.sin(theta_b) * v_conv_b + np.sin(theta_c) * v_conv_c)
    v_conv_q = -(2.0 / 3.0) * (np.cos(theta) * v_conv_a + np.cos(theta_b) * v_conv_b + np.cos(theta_c) * v_conv_c)
    for name, value in (
        ("v_ref_common_inj_switched_converter_emt_plant_bridge", common_raw),
        ("theta_pwm_sample_switched_converter_emt_plant_bridge", theta_pwm),
        ("v_p_switched_converter_emt_plant_bridge", 0.5 * v_dc_eff),
        ("v_n_switched_converter_emt_plant_bridge", -0.5 * v_dc_eff),
        ("v_leg_a_switched_converter_emt_plant_bridge", v_leg_a),
        ("v_leg_b_switched_converter_emt_plant_bridge", v_leg_b),
        ("v_leg_c_switched_converter_emt_plant_bridge", v_leg_c),
        ("v_common_mode_switched_converter_emt_plant_bridge", v_common),
        ("v_conv_a_switched_converter_emt_plant_bridge", v_conv_a),
        ("v_conv_b_switched_converter_emt_plant_bridge", v_conv_b),
        ("v_conv_c_switched_converter_emt_plant_bridge", v_conv_c),
        ("v_conv_d_switched_converter_emt_plant_bridge", v_conv_d),
        ("v_conv_q_switched_converter_emt_plant_bridge", v_conv_q),
        ("v_conv_0_switched_converter_emt_plant_bridge", 0.0),
    ):
        set_init_if_present(problem, name, value)


class NoGridConverterProblem(EmtProblemTemplate):
    __slots__ = []


class IdealTerminalSourceUpdater:
    __slots__ = ["wrapped", "indices", "v_peak", "f_hz", "vdc", "trace_t"]

    def __init__(self, wrapped: Any, indices: tuple[int, int, int, int], v_peak: float, f_hz: float, vdc: float) -> None:
        self.wrapped = wrapped
        self.indices = tuple(int(idx) for idx in indices)
        self.v_peak = float(v_peak)
        self.f_hz = float(f_hz)
        self.vdc = float(vdc)
        self.trace_t: list[float] = []

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        if self.wrapped is not None:
            self.wrapped.update(t, x, params)
        theta = 2.0 * np.pi * self.f_hz * float(t)
        va = self.v_peak * np.sin(theta)
        vb = self.v_peak * np.sin(theta - 2.0 * np.pi / 3.0)
        vc = self.v_peak * np.sin(theta + 2.0 * np.pi / 3.0)
        params[self.indices[0]] = va
        params[self.indices[1]] = vb
        params[self.indices[2]] = vc
        params[self.indices[3]] = self.vdc
        self.trace_t.append(float(t))

    def get_next_forced_event_time(self, t_prev: float, t_target: float):
        if self.wrapped is None:
            return None
        return self.wrapped.get_next_forced_event_time(t_prev, t_target)


def build_no_grid_problem(
        use_soft_bridge: bool,
        init_seed_by_name: dict[str, float] | None = None,
) -> tuple[NoGridConverterProblem, IdealTerminalSourceUpdater, Block]:
    vf = VarFactory()
    converter = (
        get_soft_switched_emt_converter(name="switched_converter_emt", vf=vf).block
        if use_soft_bridge
        else get_switched_emt_converter(name="switched_converter_emt", vf=vf).block
    )
    v_a = find_name_in_block("v_A", converter)
    v_b = find_name_in_block("v_B", converter)
    v_c = find_name_in_block("v_C", converter)
    vdc = find_name_in_block("v_dc_bus", converter)
    if v_a is None or v_b is None or v_c is None or vdc is None:
        raise RuntimeError("No-grid converter test could not resolve terminal inputs")

    root = Block(
        name="no_grid_converter_root",
        children=[converter],
        event_dict={
            v_a: Const(0.0),
            v_b: Const(float(np.sqrt(2.0) * np.sin(-2.0 * np.pi / 3.0))),
            v_c: Const(float(np.sqrt(2.0) * np.sin(2.0 * np.pi / 3.0))),
            vdc: Const(1.0),
        },
    )
    root.unify_blocks()
    problem = NoGridConverterProblem(sys_block=root, glob_time=Var("t_no_grid_converter"), static_parameter_values_mapping={})
    if init_seed_by_name is not None:
        for var in problem.get_state_vars():
            if var.name in init_seed_by_name:
                problem.init_guess[var.uid] = float(init_seed_by_name[var.name])
        for var in problem.get_algebraic_vars():
            if var.name in init_seed_by_name:
                problem.init_guess[var.uid] = float(init_seed_by_name[var.name])
    if use_soft_bridge:
        seed_no_grid_soft_bridge(problem)
    source_indices = (
        problem.uid2idx_event_params[v_a.uid],
        problem.uid2idx_event_params[v_b.uid],
        problem.uid2idx_event_params[v_c.uid],
        problem.uid2idx_event_params[vdc.uid],
    )
    updater = IdealTerminalSourceUpdater(
        wrapped=build_boundary_updater_from_block(problem),
        indices=source_indices,
        v_peak=np.sqrt(2.0),
        f_hz=50.0,
        vdc=1.0,
    )
    return problem, updater, converter


def run_case(
        use_soft_bridge: bool,
        t_end: float,
        h: float,
        init_seed_by_name: dict[str, float] | None = None,
):
    problem, updater, converter = build_no_grid_problem(use_soft_bridge=use_soft_bridge, init_seed_by_name=init_seed_by_name)
    options = EmtOptions()
    options.solver_type = EmtSolverTypes.Symbolic
    options.newton_max_iter = 20
    solver = build_emt_solver(
        options=options,
        problem=problem,
        t0=0.0,
        t_end=float(t_end),
        h=float(h),
        method=DynamicIntegrationMethod.DaeBackEuler,
    )
    t, y, dy, well_initialized, converged = solver.simulate(boundary_updater=updater)
    return problem, converter, t, y, dy, bool(well_initialized), bool(converged)


def trace(problem: NoGridConverterProblem, y: np.ndarray, block: Block, name: str) -> np.ndarray:
    var = find_name_in_block(name, block)
    if var is None:
        raise RuntimeError(f"Missing trace variable: {name}")
    return np.asarray(y[:, problem.get_var_idx(var)], dtype=float)


def values_by_name(problem: NoGridConverterProblem, y_row: np.ndarray) -> dict[str, float]:
    values: dict[str, float] = {}
    for var in list(problem.get_state_vars()) + list(problem.get_algebraic_vars()):
        values[var.name] = float(y_row[problem.get_var_idx(var)])
    return values


def main() -> None:
    time_step: float = float(os.environ.get("VERAGRID_SOFT_PROC_NO_GRID_TIME_STEP", "1.0e-5"))
    simulation_time: float = float(os.environ.get("VERAGRID_SOFT_PROC_NO_GRID_SIM_TIME", "2.0e-3"))
    plot_suffix: str = os.environ.get("VERAGRID_SOFT_PROC_NO_GRID_PLOT_SUFFIX", "")
    proc_problem, proc_block, proc_t, proc_y, _proc_dy, proc_init, proc_conv = run_case(
        use_soft_bridge=False,
        t_end=simulation_time,
        h=time_step,
    )
    print(f"Procedural no-grid initialized={proc_init} converged={proc_conv} samples={len(proc_t)}")

    try:
        soft_problem, soft_block, soft_t, soft_y, _soft_dy, soft_init, soft_conv = run_case(
            use_soft_bridge=True,
            t_end=simulation_time,
            h=time_step,
            init_seed_by_name=values_by_name(proc_problem, proc_y[0]),
        )
    except RuntimeError as exc:
        print(f"Soft no-grid solve failed: {exc}")
        names = ("i_A", "i_B", "i_C", "gate_a", "gate_b", "gate_c", "v_conv_d", "v_conv_q")
        fig, axes = plt.subplots(len(names), 1, figsize=(11, 2.0 * len(names)), sharex=True)
        for axis, name in zip(np.atleast_1d(axes), names):
            proc_arr = trace(proc_problem, proc_y, proc_block, name)
            axis.plot(proc_t, proc_arr, label="procedural")
            axis.set_ylabel(name)
            axis.grid(True)
            axis.legend(loc="best")
        axes[-1].set_xlabel("Time [s]")
        fig.tight_layout()
        out_path = get_plot_output_path(suffixed_plot_file_name("procedural_no_grid_converter.png", plot_suffix=plot_suffix))
        fig.savefig(out_path, dpi=180)
        plt.close(fig)
        print(f"Procedural plot saved to: {out_path}")
        return

    print(f"Soft no-grid initialized={soft_init} converged={soft_conv} samples={len(soft_t)}")

    names = ("i_A", "i_B", "i_C", "gate_a", "gate_b", "gate_c", "v_conv_d", "v_conv_q")
    fig, axes = plt.subplots(len(names), 1, figsize=(11, 2.0 * len(names)), sharex=True)
    for axis, name in zip(np.atleast_1d(axes), names):
        proc_arr = trace(proc_problem, proc_y, proc_block, name)
        soft_arr = trace(soft_problem, soft_y, soft_block, name)
        rmse = float(np.sqrt(np.mean((soft_arr - proc_arr) ** 2)))
        max_abs = float(np.max(np.abs(soft_arr - proc_arr)))
        print(f"{name:8s} rmse={rmse: .6e} max_abs={max_abs: .6e}")
        axis.plot(proc_t, proc_arr, label="procedural")
        axis.plot(soft_t, soft_arr, label="soft", linestyle="--")
        axis.set_ylabel(name)
        axis.grid(True)
        axis.legend(loc="best")
    axes[-1].set_xlabel("Time [s]")
    fig.tight_layout()
    out_path = get_plot_output_path(suffixed_plot_file_name("soft_vs_procedural_no_grid_converter.png", plot_suffix=plot_suffix))
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    print(f"Plot saved to: {out_path}")


if __name__ == "__main__":
    main()
