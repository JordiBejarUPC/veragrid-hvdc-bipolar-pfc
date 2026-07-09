# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import cProfile
import os
import sys
import matplotlib
import numpy as np

matplotlib.use("Agg")

from matplotlib import pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

from VeraGridEngine.Utils.Symbolic.block import Block, Const
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.vsc_gfl_emt import VscGflEmtBuild
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.block_helpers import tf_to_block
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.initialization_emt import _compute_missing_dx0
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import (
    build_residual_evaluator,
    evaluate_vectorized_residual,
    fill_full_parameter_buffer,
)
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector

from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.enumerations import ConverterControlType, DeviceType, VarPowerFlowReferenceType
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

profiler = cProfile.Profile()
profiler.enable()


def find_name_in_block(name: str, block: Block):
    """Recursively find a variable by name in the block and all its children."""
    def find_match(search_block: Block, allow_prefix: bool):
        block_vars = (
            search_block.algebraic_vars
            + search_block.state_vars
            + search_block.diff_vars
            + search_block.in_vars
            + search_block.out_vars
            + list(search_block.event_dict.keys())
        )
        for var in block_vars:
            if name == var.name or (allow_prefix and var.name.startswith(f"{name}_")):
                return var

        for mdl in search_block.children:
            res = find_match(mdl, allow_prefix)
            if res is not None:
                return res

        return None

    exact = find_match(block, allow_prefix=False)
    if exact is not None:
        return exact

    prefixed = find_match(block, allow_prefix=True)
    if prefixed is not None:
        return prefixed

    return None


def set_event_value_in_block(name: str, block: Block, value: float) -> bool:
    for var in block.event_dict.keys():
        if name == var.name:
            block.event_dict[var] = grid.var_factory.add_const(float(value))
            return True

    for mdl in block.children:
        if set_event_value_in_block(name, mdl, value):
            return True

    return False


def set_problem_runtime_value(problem, block: Block, name: str, value: float) -> None:
    var = find_name_in_block(name, block)
    problem.set_internal_runtime_if_exists(block, name, value)
    if var is None:
        return

    uid2idx = getattr(problem, "_uid2idx_event_params", getattr(problem, "uid2idx_event_params", {}))
    if var.uid not in uid2idx:
        return

    idx = uid2idx[var.uid]
    value_float = float(value)
    problem._event_params_values[idx] = value_float
    problem._event_parameters_eqs[idx] = Const(value_float)
    if hasattr(problem, "_runtime_all_eqs_source"):
        problem._runtime_all_eqs_source[idx] = Const(value_float)
    if hasattr(problem, "_runtime_parameter_eqs0"):
        problem._runtime_parameter_eqs0[idx] = Const(value_float)


PLOT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "statcom_emt_validation_plots")


def save_and_show_or_close_plot(filename: str):
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, filename), dpi=150)
    if matplotlib.get_backend().lower() == "agg":
        plt.close()
    else:
        plt.show()


def get_dc_link_capacitor_emt_block(vf, capacitance_f: float, name: str = "dc_link_capacitor") -> Block:
    """Build a DC-link capacitor injection connected to a DC EMT bus."""
    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)
    i_dc = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)
    v_cap = vf.add_var(name=f"v_cap_{name}")
    dv_cap = vf.add_diff_var(name=f"dv_cap_{name}", base_var=v_cap)
    c_dc = vf.add_var(name=f"C_dc_{name}")

    block = Block(
        algebraic_vars=[i_dc],
        state_vars=[v_cap],
        diff_vars=[dv_cap],
        in_vars=[v_dc],
        out_vars=[i_dc],
        state_eqs=[-i_dc / c_dc],
        algebraic_eqs=[v_cap - v_dc],
        event_dict={c_dc: vf.add_const(float(capacitance_f))},
        init_eqs={
            v_cap: v_dc,
            i_dc: -c_dc * dv_cap,
        },
        external_mapping={
            VarPowerFlowReferenceType.Vdc: v_dc,
            VarPowerFlowReferenceType.Idc: i_dc,
        },
    )
    block.name = name
    block.tpe = DeviceType.GeneratorDevice
    return block


def build_statcom_gfl_emt_block(vfactory, control2, frozen_voltage_source: bool = False) -> Block:
    """Build a STATCOM EMT block: GFL VSC plus DC-voltage-to-P-ref control."""
    statcom_block = VscGflEmtBuild(
        vfactory,
        control1=ConverterControlType.Pac,
        control2=control2,
        frozen_voltage_source=frozen_voltage_source,
    ).block

    fixed_p_ref = find_name_in_block("P_ref", statcom_block)
    vdc_ref = find_name_in_block("Vdc_ref", statcom_block)
    v_dc = find_name_in_block("Vdc_", statcom_block)
    kp_vdc = find_name_in_block("Kp_vdc", statcom_block)
    ki_vdc = find_name_in_block("Ki_vdc", statcom_block)

    if fixed_p_ref is None or vdc_ref is None or v_dc is None or kp_vdc is None or ki_vdc is None:
        raise RuntimeError("Could not build STATCOM DC voltage control: missing VSC control variables")

    p_ref_statcom = vfactory.add_var("P_ref_statcom")
    # COLIB STATCOM controls capacitor energy, so the outer loop acts on Vdc^2.
    dc_voltage_error = STATCOM_DC_POWER_SIGN * (vdc_ref ** 2 - v_dc ** 2)
    dc_voltage_ctrl, _ = tf_to_block(
        vfactory,
        num=[ki_vdc, kp_vdc],
        den=[0, 1],
        x=dc_voltage_error,
        y=p_ref_statcom,
        name="STATCOM_Vdc_ctrl",
    )

    statcom_block.update_model(fixed_p_ref, p_ref_statcom)
    if fixed_p_ref in statcom_block.event_dict:
        del statcom_block.event_dict[fixed_p_ref]
    statcom_block.add(dc_voltage_ctrl)
    statcom_block.name = "statcom_gfl_emt"
    return statcom_block


def print_top_residuals_at_t0(solver, problem, count: int = 12, states_override=None, derivatives_override=None) -> None:
    if not getattr(solver, "vectorized_ready", False):
        solver.auto_detect_vectorization(options.integration_method)

    x0 = problem.get_x0().copy()
    dx0 = problem.get_dx0().copy() if derivatives_override is None else derivatives_override.copy()
    if states_override is None:
        x_eval = x0.copy()
        diff_idx_by_base_uid = {
            diff_var.base_var.uid: problem.uid2idx_diff[diff_var.uid]
            for diff_var in problem.get_diff_vars()
            if diff_var.base_var is not None and diff_var.uid in problem.uid2idx_diff
        }
        for state_var in problem.get_state_vars():
            state_idx = problem.get_var_idx(state_var)
            diff_idx = diff_idx_by_base_uid.get(state_var.uid, None)
            if state_idx is not None and diff_idx is not None:
                x_eval[state_idx] += options.time_step * dx0[diff_idx]
    else:
        x_eval = states_override.copy()
    ev_params = problem.event_params_values.copy()
    static_params = solver._static_parameter_buffer
    full_params = np.zeros(len(ev_params) + static_params.shape[0], dtype=np.float64)
    runtime_params = problem.def_event_params_fn(ev_params, 0.0)
    fill_full_parameter_buffer(runtime_params, static_params, full_params)

    residual = np.zeros(len(problem.get_state_vars()) + len(problem.get_algebraic_vars()), dtype=np.float64)
    residual_evaluator = build_residual_evaluator(solver.fused_residual, solver.vec_flat_args)
    res_inf = evaluate_vectorized_residual(
        residual_evaluator=residual_evaluator,
        states=x_eval,
        params=full_params,
        history=x0,
        d_history=dx0,
        h=options.time_step,
        history2=x0,
        residual_out=residual,
    )

    labels = []
    for state_var, state_eq in zip(problem.get_state_vars(), problem.get_state_eqs()):
        labels.append(("state", state_var.name, f"d({state_var.name}) - ({state_eq})"))
    for alg_var, alg_eq in zip(problem.get_algebraic_vars(), problem.get_algebraic_eqs()):
        labels.append(("algebraic", alg_var.name, str(alg_eq)))

    order = np.argsort(-np.abs(residual))[:count]
    print(f"Top t=0 residual equations: res_inf={res_inf:.6e}")
    for eq_idx in order:
        kind, var_name, label = labels[int(eq_idx)]
        print(f"  eq={int(eq_idx)}, kind={kind}, var={var_name}, residual={residual[eq_idx]:.6e}, label={label}")


def print_vsc_residuals_at_t0(solver, problem, vsc_model: Block, states_override=None, derivatives_override=None) -> None:
    if not getattr(solver, "vectorized_ready", False):
        solver.auto_detect_vectorization(options.integration_method)

    x0 = problem.get_x0().copy()
    dx0 = problem.get_dx0().copy() if derivatives_override is None else derivatives_override.copy()
    x_eval = x0.copy() if states_override is None else states_override.copy()
    ev_params = problem.event_params_values.copy()
    static_params = solver._static_parameter_buffer
    full_params = np.zeros(len(ev_params) + static_params.shape[0], dtype=np.float64)
    runtime_params = problem.def_event_params_fn(ev_params, 0.0)
    fill_full_parameter_buffer(runtime_params, static_params, full_params)

    residual = np.zeros(len(problem.get_state_vars()) + len(problem.get_algebraic_vars()), dtype=np.float64)
    residual_evaluator = build_residual_evaluator(solver.fused_residual, solver.vec_flat_args)
    evaluate_vectorized_residual(
        residual_evaluator=residual_evaluator,
        states=x_eval,
        params=full_params,
        history=x0,
        d_history=dx0,
        h=options.time_step,
        history2=x0,
        residual_out=residual,
    )

    vsc_var_uids = set()

    def collect_vars(block: Block) -> None:
        block_vars = (
            block.algebraic_vars
            + block.state_vars
            + block.diff_vars
            + block.in_vars
            + block.out_vars
            + list(block.event_dict.keys())
        )
        for block_var in block_vars:
            vsc_var_uids.add(block_var.uid)
        for child in block.children:
            collect_vars(child)

    collect_vars(vsc_model)

    rows = []
    for idx, (state_var, state_eq) in enumerate(zip(problem.get_state_vars(), problem.get_state_eqs())):
        if state_var.uid in vsc_var_uids:
            rows.append((idx, "state", state_var.name, float(residual[idx]), f"d({state_var.name}) - ({state_eq})"))

    state_count = len(problem.get_state_vars())
    for alg_idx, (alg_var, alg_eq) in enumerate(zip(problem.get_algebraic_vars(), problem.get_algebraic_eqs())):
        eq_idx = state_count + alg_idx
        if alg_var.uid in vsc_var_uids:
            rows.append((eq_idx, "algebraic", alg_var.name, float(residual[eq_idx]), str(alg_eq)))

    rows.sort(key=lambda row: -abs(row[3]))
    max_vsc_residual = 0.0 if not rows else max(abs(row[3]) for row in rows)
    status = "PASS" if max_vsc_residual <= options.tolerance else "FAIL"
    print(
        f"VSC t=0 residual check: max_abs={max_vsc_residual:.6e}, "
        f"tolerance={options.tolerance:.6e}, status={status}"
    )
    for eq_idx, kind, var_name, res_value, label in rows[:12]:
        print(f"  eq={eq_idx}, kind={kind}, var={var_name}, residual={res_value:.6e}, label={label}")


def refresh_initial_derivatives_from_residuals(problem) -> None:
    """Make dx0 consistent with the non-steady EMT state equations."""
    if problem.initialization_report is None:
        return

    _compute_missing_dx0(
        problem=problem,
        report=problem.initialization_report,
        x_full=problem.get_x0(),
        dx_full=problem.get_dx0(),
        runtime_params=problem.event_params_values.copy(),
        constant_params=np.asarray(
            [float(const.value) for const in problem.get_parameters_values()],
            dtype=np.float64,
        ),
        include_existing=True,
    )


def seed_vsc_theta_dx0(problem, vsc_model: Block) -> None:
    omega_var = find_name_in_block('omega', vsc_model)
    if omega_var is None:
        return
    omega0 = problem.get_x0()[problem.get_var_idx(omega_var)]
    theta_dx0 = 2.0 * np.pi * grid.fBase * omega0
    for diff_var in problem.get_diff_vars():
        base_var = getattr(diff_var, 'base_var', None)
        if 'theta' in diff_var.name or (base_var is not None and base_var.name == 'theta'):
            problem.diff_init_guess[diff_var.uid] = theta_dx0


def print_vsc_control_inputs(problem, vsc_model: Block) -> None:
    print("Initial VSC control/reference inputs:")
    for name in ("P_ref", "Q_ref", "Vdc_ref", "Vm_ac_ref", "Kp_pol", "Ki_pol", "Kp_pll", "Ki_pll", "Pt_vsc", "Qt_vsc", "P", "Q"):
        var = find_name_in_block(name, vsc_model)
        if var is None:
            print(f"  {name}: not found")
            continue
        if var.uid in problem._uid2idx_vars:
            value = problem.get_x0()[problem.get_var_idx(var)]
            source = "x0"
        elif var.uid in problem.uid2idx_event_params:
            value = problem.event_params_values[problem.uid2idx_event_params[var.uid]]
            source = "event/runtime"
        else:
            print(f"  {name}: found but not in x0 or event params")
            continue
        print(f"  {name}={value: .6e} ({source})")


def print_vsc_init_to_x0_deltas(problem, vsc_model: Block, count: int = 30) -> None:
    vsc_vars = []

    def collect_vars(block: Block) -> None:
        block_vars = (
            block.algebraic_vars
            + block.state_vars
            + block.in_vars
            + block.out_vars
            + list(block.event_dict.keys())
        )
        vsc_vars.extend(block_vars)
        for child in block.children:
            collect_vars(child)

    collect_vars(vsc_model)

    rows = []
    seen = set()
    for var in vsc_vars:
        if var.uid in seen or var.uid not in problem._uid2idx_vars:
            continue
        seen.add(var.uid)
        x0_value = float(problem.get_x0()[problem.get_var_idx(var)])
        init_value = problem.init_guess.get(var.uid, None)
        if init_value is None:
            continue
        init_value = float(init_value)
        delta = x0_value - init_value
        rows.append((abs(delta), var.name, init_value, x0_value, delta))

    rows.sort(reverse=True, key=lambda row: row[0])
    print("VSC init guess to x0 largest deltas:")
    if not rows:
        print("  no comparable VSC init guesses found")
        return
    for abs_delta, name, init_value, x0_value, delta in rows[:count]:
        print(
            f"  {name}: init={init_value: .9e}, x0={x0_value: .9e}, "
            f"delta={delta: .9e}, abs_delta={abs_delta: .9e}"
        )


def print_q_control_initialization(problem, vsc_model: Block, label: str, x: np.ndarray) -> None:
    q_var = find_name_in_block("Q", vsc_model)
    q_ref_var = find_name_in_block("Q_ref", vsc_model)
    u_qac_ctrl_var = find_name_in_block("u_Qac_ctrl", vsc_model)
    if q_var is None or q_ref_var is None:
        return

    q = float(x[problem.get_var_idx(q_var)])
    if q_ref_var.uid in problem._uid2idx_vars:
        q_ref = float(x[problem.get_var_idx(q_ref_var)])
    elif q_ref_var.uid in problem.uid2idx_event_params:
        q_ref = float(problem.event_params_values[problem.uid2idx_event_params[q_ref_var.uid]])
    else:
        return

    print(f"Q control initialization check ({label}):")
    print(f"  Q={q: .9e}, Q_ref={q_ref: .9e}, Q_ref-Q={q_ref - q: .9e}")
    if u_qac_ctrl_var is not None and u_qac_ctrl_var.uid in problem._uid2idx_vars:
        u_qac_ctrl = float(x[problem.get_var_idx(u_qac_ctrl_var)])
        print(f"  u_Qac_ctrl={u_qac_ctrl: .9e}")


def build_gfl_vsc_first_step_guess(problem, vsc_model: Block, measurement_bus: gce.Bus, h: float) -> tuple[np.ndarray, np.ndarray]:
    x = problem.get_x0().copy()
    dx = problem.get_dx0().copy()
    x_old = x.copy()
    diff_idx_by_base_uid = {
        diff_var.base_var.uid: problem.uid2idx_diff[diff_var.uid]
        for diff_var in problem.get_diff_vars()
        if diff_var.base_var is not None and diff_var.uid in problem.uid2idx_diff
    }

    def var(name: str):
        return find_name_in_block(name, vsc_model)

    def bus_var(phase: str):
        return find_name_in_block(f"v_{phase}", measurement_bus.emt_model)

    def value(v):
        return x[problem.get_var_idx(v)]

    def set_value(name: str, val: float) -> None:
        v = var(name)
        if v is not None and v.uid in problem._uid2idx_vars:
            x[problem.get_var_idx(v)] = float(val)

    def set_derivative(name: str, val: float) -> None:
        v = var(name)
        if v is None:
            return
        diff_idx = diff_idx_by_base_uid.get(v.uid, None)
        if diff_idx is not None:
            dx[diff_idx] = float(val)

    def runtime_or_x(name: str) -> float:
        v = var(name)
        if v is None:
            return 0.0
        if v.uid in problem._uid2idx_vars:
            return float(x[problem.get_var_idx(v)])
        if v.uid in problem.uid2idx_event_params:
            return float(problem.event_params_values[problem.uid2idx_event_params[v.uid]])
        return 0.0

    def runtime_or_default(name: str, default: float) -> float:
        v = var(name)
        if v is None:
            return default
        if v.uid in problem._uid2idx_vars:
            return float(x[problem.get_var_idx(v)])
        if v.uid in problem.uid2idx_event_params:
            return float(problem.event_params_values[problem.uid2idx_event_params[v.uid]])
        return default

    def old_x_value(name: str, default: float = 0.0) -> float:
        v = var(name)
        if v is not None and v.uid in problem._uid2idx_vars:
            return float(x_old[problem.get_var_idx(v)])
        return default

    for state_var in problem.get_state_vars():
        state_idx = problem.get_var_idx(state_var)
        diff_idx = diff_idx_by_base_uid.get(state_var.uid, None)
        if state_idx is not None and diff_idx is not None:
            x[state_idx] += h * dx[diff_idx]

    theta_old = x_old[problem.get_var_idx(var("theta"))]
    omega_old = x_old[problem.get_var_idx(var("omega"))]
    va = value(bus_var("A"))
    vb = value(bus_var("B"))
    vc = value(bus_var("C"))
    sqrt3 = np.sqrt(3.0)

    def park_dq(theta_value: float) -> tuple[float, float]:
        theta_park = -theta_value - 0.5 * np.pi
        cos_t = np.cos(theta_park)
        sin_t = np.sin(theta_park)
        d_axis = (1.0 / 3.0) * (
            2.0 * cos_t * va
            + (-cos_t - sqrt3 * sin_t) * vb
            + (-cos_t + sqrt3 * sin_t) * vc
        )
        q_axis = (1.0 / 3.0) * (
            2.0 * sin_t * va
            + (-sin_t + sqrt3 * cos_t) * vb
            + (-sin_t - sqrt3 * cos_t) * vc
        )
        return d_axis, q_axis

    theta = value(var("theta"))
    omega = value(var("omega"))
    omega_base = 2.0 * np.pi * grid.fBase
    pll_ki = runtime_or_default("Ki_pll", PLL_KI)
    pll_kp = runtime_or_default("Kp_pll", PLL_KP)
    xi_pll_old = old_x_value("xi_PLL")
    for _ in range(8):
        vg_d_iter, _ = park_dq(theta)
        pll_error_iter = vg_d_iter
        f1 = theta - theta_old - h * omega_base * omega
        f2 = omega - (1.0 + pll_kp * pll_error_iter + pll_ki * (xi_pll_old + h * pll_error_iter))
        if max(abs(f1), abs(f2)) < 1.0e-14:
            break
        eps = 1.0e-7
        vg_d_eps, _ = park_dq(theta + eps)
        pll_error_eps = vg_d_eps
        df1_dtheta = 1.0
        df1_domega = -h * omega_base
        df2_dtheta = -(pll_kp + h * pll_ki) * (pll_error_eps - pll_error_iter) / eps
        df2_domega = 1.0
        det = df1_dtheta * df2_domega - df1_domega * df2_dtheta
        if abs(det) < 1.0e-18:
            break
        delta_theta = (-f1 * df2_domega + df1_domega * f2) / det
        omega_step = (-df1_dtheta * f2 + f1 * df2_dtheta) / det
        theta += delta_theta
        omega += omega_step

    set_value("theta", theta)
    set_value("omega", omega)
    theta_pll_park = -theta - 0.5 * np.pi
    cos_v = np.cos(theta_pll_park)
    sin_v = np.sin(theta_pll_park)
    vg_d = (1.0 / 3.0) * (
        2.0 * cos_v * va
        + (-cos_v - sqrt3 * sin_v) * vb
        + (-cos_v + sqrt3 * sin_v) * vc
    )
    vg_q = (1.0 / 3.0) * (
        2.0 * sin_v * va
        + (-sin_v + sqrt3 * cos_v) * vb
        + (-sin_v - sqrt3 * cos_v) * vc
    )

    i_d = value(var("i_d"))
    i_q = value(var("i_q"))
    r = runtime_or_default("R", 0.1)
    l = runtime_or_default("L", vsc_filter_l)
    p = 0.5 * (vg_d * i_d + vg_q * i_q)
    q = 0.5 * (vg_q * i_d - vg_d * i_q)
    if var("u_Pac_ctrl") is not None:
        active_ctrl_input_name = "u_Pac_ctrl"
        active_ctrl_input = runtime_or_x("P_ref") - p
        active_ctrl_ki = runtime_or_default("Ki_pol", 1.0)
        active_ctrl_kp = runtime_or_default("Kp_pol", 0.05)
    elif var("u_Pdc_ctrl") is not None:
        active_ctrl_input_name = "u_Pdc_ctrl"
        active_ctrl_input = runtime_or_x("P_ref") - p
        active_ctrl_ki = runtime_or_default("Ki_pol", 1.0)
        active_ctrl_kp = runtime_or_default("Kp_pol", 0.05)
    else:
        active_ctrl_input_name = "u_Vdc_ctrl"
        active_ctrl_input = runtime_or_x("Vdc_ref") - value(find_name_in_block("v_DC", bus_dc.emt_model))
        active_ctrl_ki = runtime_or_default("Ki_vdc", 2.0)
        active_ctrl_kp = runtime_or_default("Kp_vdc", 0.1)

    if var("u_Qac_ctrl") is not None:
        reactive_ctrl_input_name = "u_Qac_ctrl"
        reactive_ctrl_input = runtime_or_x("Q_ref") - q
        reactive_ctrl_ki = runtime_or_default("Ki_pol", 1.0)
        reactive_ctrl_kp = runtime_or_default("Kp_pol", 0.05)
    else:
        reactive_ctrl_input_name = "u_Vac_ctrl"
        reactive_ctrl_input = runtime_or_x("Vm_ac_ref") - vg_d
        reactive_ctrl_ki = runtime_or_default("Ki_vac", 2.0)
        reactive_ctrl_kp = runtime_or_default("Kp_vac", 0.1)

    def dx_for(name: str) -> float:
        v = var(name)
        if v is None:
            return 0.0
        diff_idx = diff_idx_by_base_uid.get(v.uid, None)
        return 0.0 if diff_idx is None else float(dx[diff_idx])

    dt_id = dx_for("i_d")
    dt_iq = dx_for("i_q")
    v_d_c = vg_d + r * i_d - omega * l * i_q + l * dt_id
    v_q_c = vg_q + r * i_q - omega * l * i_d + l * dt_iq
    y_vd_hat = v_d_c - (vg_d - l * omega * i_q)
    y_vq_hat = v_q_c - (vg_q + l * omega * i_d)

    set_value("vg_d", vg_d)
    set_value("vg_q", vg_q)
    d_vg_d = (vg_d - x_old[problem.get_var_idx(var("vg_d"))]) / h
    d_vg_q = (vg_q - x_old[problem.get_var_idx(var("vg_q"))]) / h
    pll_error = vg_d
    set_value("u_PLL_pi", pll_error)
    set_value("xi_PLL", xi_pll_old + h * pll_error)
    set_derivative("vg_d", d_vg_d)
    set_derivative("vg_q", d_vg_q)
    set_derivative("u_PLL_pi", d_vg_d)
    set_derivative("xi_PLL", pll_error)
    set_value("P", p)
    set_value("Q", q)
    set_value("Pt_vsc", -p)
    set_value("Qt_vsc", -q)
    set_value(active_ctrl_input_name, active_ctrl_input)
    set_value(reactive_ctrl_input_name, reactive_ctrl_input)
    d_active_ctrl_input = (active_ctrl_input - old_x_value(active_ctrl_input_name)) / h
    d_reactive_ctrl_input = (reactive_ctrl_input - old_x_value(reactive_ctrl_input_name)) / h
    d_omega = (omega - omega_old) / h
    d_i_q_ref = active_ctrl_ki * active_ctrl_input + active_ctrl_kp * d_active_ctrl_input
    d_i_d_ref = reactive_ctrl_ki * reactive_ctrl_input + reactive_ctrl_kp * d_reactive_ctrl_input
    i_q_ref = x_old[problem.get_var_idx(var("i_q_ref"))] + h * d_i_q_ref
    i_d_ref = x_old[problem.get_var_idx(var("i_d_ref"))] + h * d_i_d_ref
    set_value("omega", omega)
    set_derivative("theta", omega_base * omega)
    set_value("i_q_ref", i_q_ref)
    set_value("i_d_ref", i_d_ref)
    set_derivative(active_ctrl_input_name, d_active_ctrl_input)
    set_derivative(reactive_ctrl_input_name, d_reactive_ctrl_input)
    set_derivative("omega", d_omega)
    set_derivative("i_q_ref", d_i_q_ref)
    set_derivative("i_d_ref", d_i_d_ref)

    i_max = 1.2
    id_max = np.sqrt(max(i_max * i_max - max(i_q, i_q_ref) ** 2, 1.0e-5))
    i_d_ref_sat = min(max(i_d_ref, -id_max), id_max)
    i_q_ref_sat = min(max(i_q_ref, -i_max), i_max)
    u_vd_hat = i_d - i_d_ref_sat
    u_vq_hat = i_q - i_q_ref_sat
    set_value("u_vd_hat", u_vd_hat)
    set_value("u_vq_hat", u_vq_hat)
    d_u_vd_hat = (u_vd_hat - old_x_value("u_vd_hat")) / h
    d_u_vq_hat = (u_vq_hat - old_x_value("u_vq_hat")) / h
    d_y_vd_hat = 1.0 * u_vd_hat + 0.05 * d_u_vd_hat
    d_y_vq_hat = 1.0 * u_vq_hat + 0.05 * d_u_vq_hat
    set_derivative("u_vd_hat", d_u_vd_hat)
    set_derivative("u_vq_hat", d_u_vq_hat)
    set_derivative("y_vd_hat", d_y_vd_hat)
    set_derivative("y_vq_hat", d_y_vq_hat)
    y_vd_hat = old_x_value("y_vd_hat") + h * d_y_vd_hat
    y_vq_hat = old_x_value("y_vq_hat") + h * d_y_vq_hat
    v_d_c = y_vd_hat + vg_d - l * omega * i_q
    v_q_c = y_vq_hat + vg_q + l * omega * i_d
    set_value("y_vd_hat", y_vd_hat)
    set_value("y_vq_hat", y_vq_hat)
    set_value("v_d_c", v_d_c)
    set_value("v_q_c", v_q_c)

    dt_id = (v_d_c - vg_d - r * i_d - omega * l * i_q) / l
    i_d = x_old[problem.get_var_idx(var("i_d"))] + h * dt_id
    v_q_c = y_vq_hat + vg_q + l * omega * i_d
    p = 0.5 * (vg_d * i_d + vg_q * i_q)
    q = 0.5 * (vg_q * i_d - vg_d * i_q)
    set_value("i_d", i_d)
    set_derivative("i_d", dt_id)
    set_value("v_q_c", v_q_c)
    set_value("P", p)
    set_value("Q", q)
    set_value("Pt_vsc", -p)
    set_value("Qt_vsc", -q)

    cos_t = np.cos(theta_pll_park)
    sin_t = np.sin(theta_pll_park)
    vq_inv = v_q_c
    va_cmd = v_d_c * cos_t + vq_inv * sin_t
    vb_cmd = (-0.5 * v_d_c - sqrt3 * 0.5 * vq_inv) * cos_t + (sqrt3 * 0.5 * v_d_c - 0.5 * vq_inv) * sin_t
    vc_cmd = (-0.5 * v_d_c + sqrt3 * 0.5 * vq_inv) * cos_t + (-sqrt3 * 0.5 * v_d_c - 0.5 * vq_inv) * sin_t
    set_value("va_v", va_cmd)
    set_value("vb_v", vb_cmd)
    set_value("vc_v", vc_cmd)
    return x, dx


# Grid instantiation
grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Define buses: DC bus -> converter terminal -> grid/PCC -> slack grid.
bus_dc = gce.Bus(name='Bdc', Vnom=100, is_dc=True)
bus1 = gce.Bus(name='B1', Vnom=135)
bus2 = gce.Bus(name='B2', Vnom=135)
bus3 = gce.Bus(name='B3', Vnom=135, is_slack=True)

grid.add_bus(bus_dc)
grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_bus(bus3)

# Initialize EMT models for buses
for bus in grid.buses:
    get_bus_emt_template(grid, bus)

# Define AC lines
line12 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2,
                  r=3.0 * 0.029585798816568046, x=3.0 * 0.07100591715976332, b=0.03 / 3.0,
                  rate=900.0)
line23 = gce.Line(name="line 2-3", bus_from=bus2, bus_to=bus3,
                  r=3.0 * 0.029585798816568046, x=3.0 * 0.07100591715976332, b=0.03 / 3.0,
                  rate=900.0)
vsc_filter_l = line12.X

# Select control modes for the VSC
PF_CONTROL1_MODE = ConverterControlType.Vm_dc
CONTROL1_MODE = ConverterControlType.Vm_dc
CONTROL2_MODE = ConverterControlType.Qac
FREEZE_VSC_VOLTAGE_SOURCE = False
DEBUG_PI_LINE_INIT = False
STATCOM_DC_CAPACITANCE_F = 1.5
STATCOM_DC_KP = 0.1
STATCOM_DC_KI = 2.0
STATCOM_DC_POWER_SIGN = 1.0
Q_CONTROL_KP_POL = 0.1
Q_CONTROL_KI_POL = 3.0
CURRENT_CONTROL_KP_ICL = 0.1
CURRENT_CONTROL_KI_ICL = 0.2
PLL_KP = 0.0002
PLL_KI = 0.02

# Define VSCs with the selected control modes
vsc1 = gce.VSC(name='VSC1', bus_from=bus_dc, bus_to=bus1, rate=100, alpha1=0.0, alpha2=0.0, alpha3=0.0,
               control1=PF_CONTROL1_MODE, control2=CONTROL2_MODE,
               control1_val=1.03, control2_val=1.001)

# Define generators
gen1 = gce.Generator(name='Gen1', P=5.0, vset=1.00, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=1.7)

# Static zero-power placeholder; its EMT model is the STATCOM DC-link capacitor.
# A Shunt would be conceptually closer, but the EMT DC injection seeding path expects Snom.
gen3 = gce.Generator(name='DC Link Capacitor', P=0.0, vset=1.03)
grid.add_generator(bus=bus_dc, api_obj=gen3)

###############
# Add to the grid
grid.add_line(line12)
grid.add_line(line23)
grid.add_vsc(vsc1)
grid.add_generator(bus=bus3, api_obj=gen1)

#########
options = gce.PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=0,
    initialize_with_existing_solution=True,
    tolerance=1e-6,
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

res = gce.power_flow(grid, options=options)
print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

######################################################################################################
# Build EMT models
######################################################################################################



#Initialise the EMT
line12_mdl = get_pi_line_emt_template(vf=grid.var_factory, name="Pi12").block
line23_mdl = get_pi_line_emt_template(vf=grid.var_factory, name="Pi23").block
genrow_mdl1 = get_generator_thevenin_rl_emt_template_with_ref(grid.var_factory).block

# Build STATCOM EMT model: DC-link voltage loop produces the active-power reference.
vsc_mdl = build_statcom_gfl_emt_block(
    vfactory=grid.var_factory,
    control2=CONTROL2_MODE,
    frozen_voltage_source=FREEZE_VSC_VOLTAGE_SOURCE,
)
dc_capacitor = get_dc_link_capacitor_emt_block(
    vf=grid.var_factory,
    capacitance_f=STATCOM_DC_CAPACITANCE_F,
    name="statcom_dc_link_capacitor",
)

# Attach EMT models and let the current helper create bus/device connections.
set_emt_model(device=line12, model=line12_mdl, var_factory=grid.var_factory)
set_emt_model(device=line23, model=line23_mdl, var_factory=grid.var_factory)
set_emt_model(device=gen1, model=genrow_mdl1, var_factory=grid.var_factory)
set_emt_model(device=gen3, model=dc_capacitor, var_factory=grid.var_factory)
set_emt_model(device=vsc1, model=vsc_mdl, var_factory=grid.var_factory)

grid.var_factory.add_connections(
    vsc_mdl.in_vars[0:3],
    [find_name_in_block('v_A', bus1.emt_model), find_name_in_block('v_B', bus1.emt_model), find_name_in_block('v_C', bus1.emt_model)],
)

grid.var_factory.add_connections(
    [find_name_in_block('vg_A', vsc_mdl), find_name_in_block('vg_B', vsc_mdl), find_name_in_block('vg_C', vsc_mdl)],
    [find_name_in_block('v_A', bus2.emt_model), find_name_in_block('v_B', bus2.emt_model), find_name_in_block('v_C', bus2.emt_model)],
)
grid.var_factory.add_connections(
    [find_name_in_block('i_line_A', vsc_mdl), find_name_in_block('i_line_B', vsc_mdl), find_name_in_block('i_line_C', vsc_mdl)],
    [find_name_in_block('it_Pi12_A', line12_mdl), find_name_in_block('it_Pi12_B', line12_mdl), find_name_in_block('it_Pi12_C', line12_mdl)],
)

set_event_value_in_block('Vdc_ref', vsc_mdl, abs(res.voltage[grid.buses.index(vsc1.bus_from)]))
vm_ac_ref_bus = bus1 if FREEZE_VSC_VOLTAGE_SOURCE else bus2
set_event_value_in_block('Vm_ac_ref', vsc_mdl, np.sqrt(2.0) * abs(res.voltage[grid.buses.index(vm_ac_ref_bus)]))
line12_idx = grid.lines.index(line12)
line12_s = complex(res.St[line12_idx]) / grid.Sbase
P_Q_REF_SCALE = 1.0
p_ref0 = float(P_Q_REF_SCALE * np.real(line12_s))
q_ref0 = float(P_Q_REF_SCALE * np.imag(line12_s))
set_event_value_in_block('P_ref', vsc_mdl, p_ref0)
set_event_value_in_block('Q_ref', vsc_mdl, q_ref0)
def pf_voltage_abc(bus):
    v_complex = complex(res.voltage[grid.buses.index(bus)])
    v_peak = np.sqrt(2.0) * abs(v_complex)
    v_angle = np.angle(v_complex)
    return (
        v_peak * np.sin(v_angle),
        v_peak * np.sin(v_angle - 2.0 * np.pi / 3.0),
        v_peak * np.sin(v_angle + 2.0 * np.pi / 3.0),
    )


def park_dq_value(theta_value, va_value, vb_value, vc_value):
    cos_t = np.cos(theta_value)
    sin_t = np.sin(theta_value)
    vd_value = (1.0 / 3.0) * (
        2.0 * cos_t * va_value
        + (-cos_t - np.sqrt(3.0) * sin_t) * vb_value
        + (-cos_t + np.sqrt(3.0) * sin_t) * vc_value
    )
    vq_value = (1.0 / 3.0) * (
        2.0 * sin_t * va_value
        + (-sin_t + np.sqrt(3.0) * cos_t) * vb_value
        + (-sin_t - np.sqrt(3.0) * cos_t) * vc_value
    )
    return vd_value, vq_value


va_pcc0, vb_pcc0, vc_pcc0 = pf_voltage_abc(bus2)
best_theta_ref = 0.0
best_abs_d_ref = None
for theta_candidate in np.linspace(-np.pi, np.pi, 40001):
    vd_candidate, vq_candidate = park_dq_value(theta_candidate, va_pcc0, vb_pcc0, vc_pcc0)
    if vq_candidate > 0.0 and (best_abs_d_ref is None or abs(vd_candidate) < best_abs_d_ref):
        best_abs_d_ref = abs(vd_candidate)
        best_theta_ref = theta_candidate

va_conv0, vb_conv0, vc_conv0 = pf_voltage_abc(bus1)
vd_c_ref0, vq_c_ref0 = park_dq_value(best_theta_ref, va_conv0, vb_conv0, vc_conv0)
vq_ref0 = park_dq_value(best_theta_ref, va_pcc0, vb_pcc0, vc_pcc0)[1]
id_ref0 = 2.0 * q_ref0 / vq_ref0
iq_ref0 = 2.0 * p_ref0 / vq_ref0
if FREEZE_VSC_VOLTAGE_SOURCE:
    set_event_value_in_block('v_d_c_ref', vsc_mdl, vd_c_ref0)
    set_event_value_in_block('v_q_c_ref', vsc_mdl, vq_c_ref0)
    set_event_value_in_block('Vm_ac_ref', vsc_mdl, vq_c_ref0)
    print(
        "PF Bus1 frozen VSC command: "
        f"vd_c_ref={vd_c_ref0: .9e}, vq_c_ref={vq_c_ref0: .9e}, "
        f"id_ref={id_ref0: .9e}, iq_ref={iq_ref0: .9e}"
    )
set_event_value_in_block('Kp_pol', vsc_mdl, Q_CONTROL_KP_POL)
set_event_value_in_block('Ki_pol', vsc_mdl, Q_CONTROL_KI_POL)
set_event_value_in_block('Kp_vdc', vsc_mdl, STATCOM_DC_KP)
set_event_value_in_block('Ki_vdc', vsc_mdl, STATCOM_DC_KI)
set_event_value_in_block('Kp_icl', vsc_mdl, CURRENT_CONTROL_KP_ICL)
set_event_value_in_block('Ki_icl', vsc_mdl, CURRENT_CONTROL_KI_ICL)
set_event_value_in_block('Kp_pll', vsc_mdl, PLL_KP)
set_event_value_in_block('Ki_pll', vsc_mdl, PLL_KI)
set_event_value_in_block('L', vsc_mdl, vsc_filter_l)

V_src = find_name_in_block('V_src_dc_voltage_source', gen3.emt_model)

# Find appropriate reference variable based on control mode
if CONTROL1_MODE == ConverterControlType.Vm_dc:
    ref_var = find_name_in_block('Vdc_ref', vsc_mdl)
    print(f"Using Vdc_ref for control mode {CONTROL1_MODE}")
elif CONTROL1_MODE in [ConverterControlType.Pac, ConverterControlType.Pdc]:
    ref_var = find_name_in_block('P_ref', vsc_mdl)
    print(f"Using P_ref for control mode {CONTROL1_MODE}")
else:
    ref_var = find_name_in_block('P_ref', vsc_mdl)
    print(f"Using P_ref for control mode {CONTROL1_MODE}")

event1 = None if V_src is None else EmtEvent(device=gen3, parameter=V_src, time=1, value=0.3)
event2 = EmtEvent(device=vsc1, parameter=ref_var, time=1, value=0.1)
event3 = EmtEvent(device=vsc1, parameter=ref_var, time=1, value=1.03)
if event1 is not None:
    grid.add_emt_event(event1)
grid.add_emt_event(event2)
#grid.add_emt_event(event3)

options = EmtOptions(time_step=0.0001,  # EMT requires smaller time step
                     simulation_time=3.0,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     solver_type=EmtSolverTypes.StructuralAD,
                     initialization_method=EmtInitializationMethod.Explicit,
                     verbose=0)
print(f"EMT initialization method: {options.initialization_method!r}")

problem = EmtProblemDae(grid=grid,
                        options=options,
                        pf_results=res)
newton_trace = NewtonTraceCollector()
problem.set_newton_trace_collector(newton_trace)


def seed_gfl_vsc_initial_guess(problem, vsc, pf_results, converter_bus, grid_bus):
    bus_names = [bus.name for bus in grid.buses]

    def value_of(var):
        return problem.get_x0()[problem.get_var_idx(var)]

    v_a_var = find_name_in_block('v_A', grid_bus.emt_model)
    v_b_var = find_name_in_block('v_B', grid_bus.emt_model)
    v_c_var = find_name_in_block('v_C', grid_bus.emt_model)
    va0 = value_of(v_a_var)
    vb0 = value_of(v_b_var)
    vc0 = value_of(v_c_var)

    best_theta = 0.0
    best_abs_d = None
    best_q = 1.0
    for theta_candidate in np.linspace(-np.pi, np.pi, 40001):
        vd_candidate = (1.0 / 3.0) * (
            2.0 * np.cos(theta_candidate) * va0
            + (-np.cos(theta_candidate) - np.sqrt(3.0) * np.sin(theta_candidate)) * vb0
            + (-np.cos(theta_candidate) + np.sqrt(3.0) * np.sin(theta_candidate)) * vc0
        )
        vq_candidate = (1.0 / 3.0) * (
            2.0 * np.sin(theta_candidate) * va0
            + (-np.sin(theta_candidate) + np.sqrt(3.0) * np.cos(theta_candidate)) * vb0
            + (-np.sin(theta_candidate) - np.sqrt(3.0) * np.cos(theta_candidate)) * vc0
        )
        if vq_candidate > 0.0 and (best_abs_d is None or abs(vd_candidate) < best_abs_d):
            best_abs_d = abs(vd_candidate)
            best_theta = theta_candidate
            best_q = vq_candidate

    vpk = float(best_q)

    line12_idx = grid.lines.index(line12)
    line12_s = complex(pf_results.St[line12_idx]) / grid.Sbase
    p0 = 0.0
    q0 = float(np.imag(line12_s))
    theta0 = float(-best_theta)
    theta_park0 = -theta0
    vd0 = 0.0
    vq0 = vpk
    id0 = 2.0 * q0 / vq0
    iq0 = 2.0 * p0 / vq0

    l0 = vsc_filter_l
    omega0 = 1.0
    vc_a0 = value_of(find_name_in_block('v_A', converter_bus.emt_model))
    vc_b0 = value_of(find_name_in_block('v_B', converter_bus.emt_model))
    vc_c0 = value_of(find_name_in_block('v_C', converter_bus.emt_model))
    cos_t = np.cos(theta_park0)
    sin_t = np.sin(theta_park0)
    vd_c0 = (1.0 / 3.0) * (
        2.0 * cos_t * vc_a0
        + (-cos_t - np.sqrt(3.0) * sin_t) * vc_b0
        + (-cos_t + np.sqrt(3.0) * sin_t) * vc_c0
    )
    vq_c0 = (1.0 / 3.0) * (
        2.0 * sin_t * vc_a0
        + (-sin_t + np.sqrt(3.0) * cos_t) * vc_b0
        + (-sin_t - np.sqrt(3.0) * cos_t) * vc_c0
    )
    if FREEZE_VSC_VOLTAGE_SOURCE:
        vd_c0 = vd_c_ref0
        vq_c0 = vq_c_ref0
    ia_from0 = value_of(find_name_in_block('if_Pi12_A', line12_mdl))
    ib_from0 = value_of(find_name_in_block('if_Pi12_B', line12_mdl))
    ic_from0 = value_of(find_name_in_block('if_Pi12_C', line12_mdl))
    ia_vsc0 = -ia_from0
    ib_vsc0 = -ib_from0
    ic_vsc0 = -ic_from0
    p_conv0 = -(vc_a0 * ia_vsc0 + vc_b0 * ib_vsc0 + vc_c0 * ic_vsc0) / 3.0
    vdc0 = value_of(find_name_in_block('v_DC', bus_dc.emt_model))
    i_dc0 = p_conv0 / vdc0
    ia_line0 = value_of(find_name_in_block('it_Pi12_A', line12_mdl))
    ib_line0 = value_of(find_name_in_block('it_Pi12_B', line12_mdl))
    ic_line0 = value_of(find_name_in_block('it_Pi12_C', line12_mdl))
    cos_t = np.cos(theta_park0)
    sin_t = np.sin(theta_park0)
    id0 = (1.0 / 3.0) * (
        2.0 * cos_t * ia_line0
        + (-cos_t - np.sqrt(3.0) * sin_t) * ib_line0
        + (-cos_t + np.sqrt(3.0) * sin_t) * ic_line0
    )
    iq0 = (1.0 / 3.0) * (
        2.0 * sin_t * ia_line0
        + (-sin_t + np.sqrt(3.0) * cos_t) * ib_line0
        + (-sin_t - np.sqrt(3.0) * cos_t) * ic_line0
    )
    vd_hat0 = vd_c0 - (vd0 - l0 * omega0 * iq0)
    vq_hat0 = vq_c0 - (vq0 + l0 * omega0 * id0)

    values = {
        'P': p0,
        'Q': q0,
        'P_ref_statcom': p0,
        'P_f': p0,
        'Q_f': q0,
        'Pt_vsc': -p0,
        'Qt_vsc': -q0,
        'i_a_f': ia_vsc0,
        'i_b_f': ib_vsc0,
        'i_c_f': ic_vsc0,
        'i_dc': i_dc0,
        'P_conv': p_conv0,
        'theta': theta0,
        'omega': omega0,
        'xi_PLL': 0.0,
        'vg_d': vd0,
        'vg_q': vq0,
        'vc_d': vd_c0,
        'vc_q': vq_c0,
        'i_line_d': id0,
        'i_line_q': iq0,
        'i_d_ref': id0,
        'i_q_ref': iq0,
        'v_d_c': vd_c0,
        'v_q_c': vq_c0,
        'va_v': vc_a0,
        'vb_v': vc_b0,
        'vc_v': vc_c0,
        'y_vd_hat': vd_hat0,
        'y_vq_hat': vq_hat0,
        'u_Pac_ctrl': 0.0,
        'u_STATCOM_Vdc_ctrl': 0.0,
        'u_Pdc_ctrl': 0.0,
        'u_Qac_ctrl': 0.0,
        'u_Vdc_ctrl': 0.0,
        'u_Vac_ctrl': 0.0,
        'u_PLL_pi': vd0,
        'u_vd_hat': 0.0,
        'u_vq_hat': 0.0,
    }
    for name, value in values.items():
        var = find_name_in_block(name, vsc.emt_model)
        if var is not None:
            problem.init_guess[var.uid] = float(value)

    dc_capacitor_values = {
        'i_dc_statcom_dc_link_capacitor': i_dc0,
        'v_cap_statcom_dc_link_capacitor': vdc0,
        'dv_cap_statcom_dc_link_capacitor': -i_dc0 / STATCOM_DC_CAPACITANCE_F,
    }
    for name, value in dc_capacitor_values.items():
        var = find_name_in_block(name, dc_capacitor)
        if var is not None:
            if var.uid in problem._uid2idx_vars:
                problem.init_guess[var.uid] = float(value)
            elif var.uid in problem.uid2idx_diff:
                problem.diff_init_guess[var.uid] = float(value)
            elif var.uid in problem.uid2idx_event_params:
                problem.event_params_values[problem.uid2idx_event_params[var.uid]] = float(value)

    theta_var = find_name_in_block('theta', vsc.emt_model)
    if theta_var is not None and theta_var.diff_var is not None:
        problem.diff_init_guess[theta_var.diff_var.uid] = 2.0 * np.pi * grid.fBase * omega0
    theta_diff_var = find_name_in_block('dt_1_theta', vsc.emt_model)
    if theta_diff_var is not None:
        problem.diff_init_guess[theta_diff_var.uid] = 2.0 * np.pi * grid.fBase * omega0
    for diff_var in problem.get_diff_vars():
        base_var = getattr(diff_var, 'base_var', None)
        if 'theta' in diff_var.name or (base_var is not None and 'theta' in base_var.name):
            problem.diff_init_guess[diff_var.uid] = 2.0 * np.pi * grid.fBase * omega0
    for state_var in problem.get_state_vars():
        if 'theta' in state_var.name and state_var.diff_var is not None:
            problem.diff_init_guess[state_var.diff_var.uid] = 2.0 * np.pi * grid.fBase * omega0

    problem.set_internal_runtime_if_exists(
        vsc.emt_model,
        'Vdc_ref',
        float(abs(pf_results.voltage[bus_names.index(vsc.bus_from.name)])),
    )
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'Vm_ac_ref', vq0)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'P_ref', p0)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'Q_ref', q0)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'Kp_pol', Q_CONTROL_KP_POL)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'Ki_pol', Q_CONTROL_KI_POL)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'Kp_vdc', STATCOM_DC_KP)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'Ki_vdc', STATCOM_DC_KI)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'Kp_icl', CURRENT_CONTROL_KP_ICL)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'Ki_icl', CURRENT_CONTROL_KI_ICL)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'Kp_pll', PLL_KP)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'Ki_pll', PLL_KI)
    problem.set_internal_runtime_if_exists(vsc.emt_model, 'L', vsc_filter_l)
    return None


seed_gfl_vsc_initial_guess(problem, vsc1, res, bus1, bus2)
refresh_initial_derivatives_from_residuals(problem)
seed_vsc_theta_dx0(problem, vsc_mdl)
print_vsc_control_inputs(problem, vsc_mdl)
print_vsc_init_to_x0_deltas(problem, vsc_mdl)

print("Initial bus phase voltage seeds:")
for bus in (bus1, bus2):
    values = []
    for phase in ("A", "B", "C"):
        var = find_name_in_block(f"v_{phase}", bus.emt_model)
        values.append(problem.get_x0()[problem.get_var_idx(var)] if var is not None else None)
    print(f"  {bus.name}: v_A={values[0]: .6e}, v_B={values[1]: .6e}, v_C={values[2]: .6e}")

print("Initial derivative parameter seeds:")
for line_name, line_mdl in (("line12", line12_mdl), ("line23", line23_mdl)):
    parts = []
    for side in ("f", "t"):
        for phase in ("A", "B", "C"):
            var = find_name_in_block(f"d_v{side}_{phase}", line_mdl)
            if var is not None:
                idx = problem.uid2idx_event_params.get(var.uid, None)
                value = problem.event_params_values[idx] if idx is not None else None
                parts.append(f"d_v{side}_{phase}={value: .6e}" if value is not None else f"d_v{side}_{phase}=None")
    print(f"  {line_name}: " + ", ".join(parts))


def print_pi_line_initial_consistency(problem, line, line_mdl, pf_results, label):
    x0 = problem.get_x0()
    omega_base = 2.0 * np.pi * grid.fBase
    alpha = 2.0 * np.pi / 3.0
    line_suffix = label.replace("line", "Pi")
    line_idx = grid.lines.index(line)
    vf_base = complex(pf_results.voltage[grid.buses.index(line.bus_from)])
    vt_base = complex(pf_results.voltage[grid.buses.index(line.bus_to)])
    sf_static = complex(pf_results.Sf[line_idx]) / grid.Sbase
    st_static = complex(pf_results.St[line_idx]) / grid.Sbase
    sf_phase = sf_static / 3.0
    st_phase = st_static / 3.0
    z_series = complex(line.R, line.X)
    b_half = line.B / 2.0
    g_damp = 1.0e-5
    s_series_sum = 0.0 + 0.0j
    s_from_terminal_sum = 0.0 + 0.0j
    s_to_terminal_sum = 0.0 + 0.0j

    print(f"Pi-line initial consistency diagnostic: {label}")
    for phase, rot in (("A", 1.0 + 0.0j), ("B", np.exp(-1j * alpha)), ("C", np.exp(1j * alpha))):
        vf = vf_base * rot
        vt = vt_base * rot
        i_f_pf = np.conj(sf_phase / vf)
        i_t_pf = np.conj(st_phase / vt)
        i_ser_pf = (vf - vt) / z_series
        i_cap_f_pf = 1j * b_half * vf
        i_cap_t_pf = 1j * b_half * vt
        i_from_terminal_pf = i_ser_pf + i_cap_f_pf
        i_to_terminal_pf = -i_ser_pf + i_cap_t_pf

        s_series_sum += vf * np.conj(i_ser_pf)
        s_from_terminal_sum += vf * np.conj(i_from_terminal_pf)
        s_to_terminal_sum += vt * np.conj(i_to_terminal_pf)

        vf_var = find_name_in_block(f"v_{phase}", line.bus_from.emt_model)
        vt_var = find_name_in_block(f"v_{phase}", line.bus_to.emt_model)
        if_var = find_name_in_block(f"if_{line_suffix}_{phase}", line_mdl)
        it_var = find_name_in_block(f"it_{line_suffix}_{phase}", line_mdl)
        i_ser_var = find_name_in_block(f"i_ser_{line_suffix}_{phase}", line_mdl)
        i_cap_f_var = find_name_in_block(f"i_cap_f_{line_suffix}_{phase}", line_mdl)
        i_cap_t_var = find_name_in_block(f"i_cap_t_{line_suffix}_{phase}", line_mdl)
        d_vf_var = find_name_in_block(f"d_vf_{phase}", line_mdl)
        d_vt_var = find_name_in_block(f"d_vt_{phase}", line_mdl)

        vf0 = x0[problem.get_var_idx(vf_var)]
        vt0 = x0[problem.get_var_idx(vt_var)]
        if0 = x0[problem.get_var_idx(if_var)]
        it0 = x0[problem.get_var_idx(it_var)]
        i_ser0 = x0[problem.get_var_idx(i_ser_var)]
        i_cap_f0 = x0[problem.get_var_idx(i_cap_f_var)]
        i_cap_t0 = x0[problem.get_var_idx(i_cap_t_var)]
        d_vf_idx = problem.uid2idx_event_params.get(d_vf_var.uid, None)
        d_vt_idx = problem.uid2idx_event_params.get(d_vt_var.uid, None)
        d_vf0 = problem.event_params_values[d_vf_idx] if d_vf_idx is not None else np.nan
        d_vt0 = problem.event_params_values[d_vt_idx] if d_vt_idx is not None else np.nan

        i_ser_from = if0 - i_cap_f0 - g_damp * vf0
        i_ser_to = -it0 + i_cap_t0 + g_damp * vt0
        rhs_di = (vf0 - vt0 - line.R * i_ser0) / (line.X / omega_base)
        expected = {
            "vf": np.sqrt(2.0) * np.imag(vf),
            "vt": np.sqrt(2.0) * np.imag(vt),
            "if": np.sqrt(2.0) * np.imag(i_f_pf),
            "it": np.sqrt(2.0) * np.imag(i_t_pf),
            "iser": np.sqrt(2.0) * np.imag(i_ser_pf),
            "icapf": np.sqrt(2.0) * np.imag(i_cap_f_pf),
            "icapt": np.sqrt(2.0) * np.imag(i_cap_t_pf),
            "diser": omega_base * np.sqrt(2.0) * np.real(i_ser_pf),
            "dvf": omega_base * np.sqrt(2.0) * np.real(vf),
            "dvt": omega_base * np.sqrt(2.0) * np.real(vt),
        }
        print(
            f"  {phase}: if0={if0: .9e}, it0={it0: .9e}, i_ser0={i_ser0: .9e}, "
            f"i_ser_from={i_ser_from: .9e}, i_ser_to={i_ser_to: .9e}"
        )
        print(
            f"     expected if={expected['if']: .9e}, it={expected['it']: .9e}, "
            f"iser={expected['iser']: .9e}, icapf={expected['icapf']: .9e}, icapt={expected['icapt']: .9e}"
        )
        print(
            f"     caps x0: icapf={i_cap_f0: .9e}, icapt={i_cap_t0: .9e}; "
            f"dv: x0 f/t={d_vf0: .9e}/{d_vt0: .9e}, expected={expected['dvf']: .9e}/{expected['dvt']: .9e}"
        )
        print(
            f"     di_ser rhs={rhs_di: .9e}, expected d(iser)={expected['diser']: .9e}, "
            f"rhs-error={rhs_di - expected['diser']: .9e}"
        )

    print(
        f"  static PF totals: Sf={sf_static.real: .9e}+j{sf_static.imag: .9e}, "
        f"St={st_static.real: .9e}+j{st_static.imag: .9e}"
    )
    print(
        f"  direct-Z abc sum: series-from={s_series_sum.real: .9e}+j{s_series_sum.imag: .9e}, "
        f"terminal-from={s_from_terminal_sum.real: .9e}+j{s_from_terminal_sum.imag: .9e}, "
        f"terminal-to={s_to_terminal_sum.real: .9e}+j{s_to_terminal_sum.imag: .9e}"
    )
    print(
        f"  direct-Z errors: terminal-from-Sf={s_from_terminal_sum - sf_static: .9e}, "
        f"terminal-to-St={s_to_terminal_sum - st_static: .9e}"
    )
    print("  expected values above use balanced per-phase currents from total static PF powers")


if DEBUG_PI_LINE_INIT:
    print_pi_line_initial_consistency(problem, line12, line12_mdl, res, "line12")
    print_pi_line_initial_consistency(problem, line23, line23_mdl, res, "line23")



solver = build_emt_solver(
    options=options,
    problem=problem,
    t0=0.0,
    t_end=options.simulation_time,
    h=options.time_step,
    method=options.integration_method,
)

print_q_control_initialization(problem, vsc_mdl, "true x0", problem.get_x0())
print_top_residuals_at_t0(
    solver,
    problem,
    states_override=problem.get_x0(),
)
print_vsc_residuals_at_t0(
    solver,
    problem,
    vsc_mdl,
)

t, y, dy, well_initialized, converged = solver.simulate()

print("First Newton diagnostics:")
for record in newton_trace.records[:10]:
    print(
        f"  t={record['t']:.6f}, step={record['step']}, it={record['newton_iter']}, "
        f"res_inf={record['res_norm_inf']}, dx_inf={record['dx_norm_inf']}, "
        f"dx_2={record['dx_norm_2']}, fallback={record['used_fallback']}"
    )

if newton_trace.residual_records:
    first_residual = newton_trace.residual_records[0]
    print("Top first-step residual equations:")
    for row in first_residual["top"]:
        print(
            f"  eq={row['eq_idx']}, kind={row.get('kind', '')}, var={row.get('var_name', '')}, "
            f"residual={row['res']:.6e}, label={row.get('label', '')}"
        )

profiler.disable()
profiler.dump_stats("profiling_stats_emt.prof")

xlim = options.simulation_time

# Find variables for plotting
v_A_bus1 = find_name_in_block("v_A", bus1.emt_model)
v_B_bus1 = find_name_in_block("v_B", bus1.emt_model)
v_C_bus1 = find_name_in_block("v_C", bus1.emt_model)

v_A_bus2 = find_name_in_block("v_A", bus2.emt_model)
v_B_bus2 = find_name_in_block("v_B", bus2.emt_model)
v_C_bus2 = find_name_in_block("v_C", bus2.emt_model)

i_A_vsc = find_name_in_block("i_a_f", vsc_mdl)
i_B_vsc = find_name_in_block("i_b_f", vsc_mdl)
i_C_vsc = find_name_in_block("i_c_f", vsc_mdl)
i_A_line12_from = find_name_in_block("if_Pi12_A", line12_mdl)
i_B_line12_from = find_name_in_block("if_Pi12_B", line12_mdl)
i_C_line12_from = find_name_in_block("if_Pi12_C", line12_mdl)
i_A_line12_to = find_name_in_block("it_Pi12_A", line12_mdl)
i_B_line12_to = find_name_in_block("it_Pi12_B", line12_mdl)
i_C_line12_to = find_name_in_block("it_Pi12_C", line12_mdl)

P = find_name_in_block('P', vsc_mdl)
Q = find_name_in_block('Q', vsc_mdl)
Vdc = bus_dc.emt_model.out_vars[0]
theta_vsc = find_name_in_block('theta', vsc_mdl)
omega_vsc = find_name_in_block('omega', vsc_mdl)
v_d_g = find_name_in_block('vg_d', vsc_mdl)
v_q_g = find_name_in_block('vg_q', vsc_mdl)
i_d_vsc = find_name_in_block('i_line_d', vsc_mdl)
i_q_vsc = find_name_in_block('i_line_q', vsc_mdl)
i_d_ref_vsc = find_name_in_block('i_d_ref', vsc_mdl)
i_q_ref_vsc = find_name_in_block('i_q_ref', vsc_mdl)
v_d_c_vsc = find_name_in_block('v_d_c', vsc_mdl)
v_q_c_vsc = find_name_in_block('v_q_c', vsc_mdl)
y_vd_hat_vsc = find_name_in_block('y_vd_hat', vsc_mdl)
y_vq_hat_vsc = find_name_in_block('y_vq_hat', vsc_mdl)
u_vdc_ctrl = find_name_in_block('u_Vdc_ctrl', vsc_mdl)
u_pac_ctrl = find_name_in_block('u_Pac_ctrl', vsc_mdl)
u_pdc_ctrl = find_name_in_block('u_Pdc_ctrl', vsc_mdl)
u_vac_ctrl = find_name_in_block('u_Vac_ctrl', vsc_mdl)
u_qac_ctrl = find_name_in_block('u_Qac_ctrl', vsc_mdl)
reactive_outer_error = u_vac_ctrl if u_vac_ctrl is not None else u_qac_ctrl
vdc_ref_var = find_name_in_block('Vdc_ref', vsc_mdl)
p_ref_var = find_name_in_block('P_ref', vsc_mdl)
p_ref_statcom_var = find_name_in_block('P_ref_statcom', vsc_mdl)
u_statcom_vdc_ctrl = find_name_in_block('u_STATCOM_Vdc_ctrl', vsc_mdl)
vm_ac_ref_var = find_name_in_block('Vm_ac_ref', vsc_mdl)
q_ref_var = find_name_in_block('Q_ref', vsc_mdl)
statcom_cap_current = find_name_in_block('i_dc_statcom_dc_link_capacitor', dc_capacitor)
statcom_cap_voltage = find_name_in_block('v_cap_statcom_dc_link_capacitor', dc_capacitor)
statcom_cap_dv = find_name_in_block('dv_cap_statcom_dc_link_capacitor', dc_capacitor)
dt_theta_vsc = find_name_in_block('dt_1_theta', vsc_mdl)
dt_omega_vsc = find_name_in_block('dt_1_omega', vsc_mdl)
dt_vg_d = find_name_in_block('dt_1_vg_d', vsc_mdl)
dt_vg_q = find_name_in_block('dt_1_vg_q', vsc_mdl)
u_pll_pi = find_name_in_block('u_PLL_pi', vsc_mdl)
dt_u_pll_pi = find_name_in_block('dt_1_u_PLL_pi', vsc_mdl)
xi_pll = find_name_in_block('xi_PLL', vsc_mdl)
dt_xi_pll = find_name_in_block('dt_1_xi_PLL', vsc_mdl)
omega_base_pll = find_name_in_block('omega_base', vsc_mdl)


def trace_or_runtime_constant(var):
    if var is None:
        return None
    if var.uid in problem._uid2idx_vars:
        return y[:, problem.get_var_idx(var)]
    if var.uid in problem.uid2idx_diff:
        return dy[:, problem.uid2idx_diff[var.uid]]
    if var.uid in problem.uid2idx_event_params:
        return np.full_like(t, problem.event_params_values[problem.uid2idx_event_params[var.uid]])
    return None


def numeric_derivative(trace: np.ndarray) -> np.ndarray:
    if trace.size < 2:
        return np.zeros_like(trace)
    return np.gradient(trace, t)


def park_dq_from_abc(theta_trace: np.ndarray, va_trace: np.ndarray, vb_trace: np.ndarray, vc_trace: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    cos_t = np.cos(theta_trace)
    sin_t = np.sin(theta_trace)
    sqrt3 = np.sqrt(3.0)
    d_trace = (1.0 / 3.0) * (
        2.0 * cos_t * va_trace
        + (-cos_t - sqrt3 * sin_t) * vb_trace
        + (-cos_t + sqrt3 * sin_t) * vc_trace
    )
    q_trace = (1.0 / 3.0) * (
        2.0 * sin_t * va_trace
        + (-sin_t + sqrt3 * cos_t) * vb_trace
        + (-sin_t - sqrt3 * cos_t) * vc_trace
    )
    return d_trace, q_trace


def trace_or_numeric_derivative(var, source_var=None, force_numeric: bool = False):
    trace = None if force_numeric else trace_or_runtime_constant(var)
    if trace is not None:
        return trace
    source_trace = trace_or_runtime_constant(source_var)
    if source_trace is None:
        return None
    return numeric_derivative(source_trace)


def print_trace_diagnostics(title: str, items: list[tuple[str, object]]) -> None:
    print(title)
    for item in items:
        force_numeric = False
        if len(item) == 2:
            label, var = item
            source_var = None
        elif len(item) == 3:
            label, var, source_var = item
        else:
            label, var, source_var, force_numeric = item
        trace = trace_or_numeric_derivative(var, source_var, force_numeric=force_numeric)
        if trace is None:
            print(f"  {label}: not available")
            continue
        pre_trace = trace[pre_event]
        print(
            f"  {label}: t0={trace[0]: .9e}, pre_last={pre_trace[-1]: .9e}, "
            f"pre_min={np.min(pre_trace): .9e}, pre_max={np.max(pre_trace): .9e}, "
            f"pre_delta_max={np.max(np.abs(pre_trace - pre_trace[0])): .9e}"
        )
        print(f"  {label} first samples: {pre_trace[:10]}")

pre_event = t < 0.19
if np.any(pre_event):
    vdc_trace_for_ctrl = y[:, problem.get_var_idx(Vdc)]
    vdc_ref_trace_for_ctrl = trace_or_runtime_constant(vdc_ref_var)
    p_ref_statcom_trace = trace_or_runtime_constant(p_ref_statcom_var)
    statcom_error_sq_trace = None
    if vdc_ref_trace_for_ctrl is not None:
        statcom_error_sq_trace = STATCOM_DC_POWER_SIGN * (vdc_ref_trace_for_ctrl ** 2 - vdc_trace_for_ctrl ** 2)

    print("STATCOM DC-control startup diagnostic:")
    if p_ref_statcom_trace is not None:
        print(
            f"  P_ref_statcom: t0={p_ref_statcom_trace[0]: .9e}, "
            f"pre_min={np.min(p_ref_statcom_trace[pre_event]): .9e}, "
            f"pre_max={np.max(p_ref_statcom_trace[pre_event]): .9e}, "
            f"pre_delta={np.max(np.abs(p_ref_statcom_trace[pre_event] - p_ref_statcom_trace[0])): .9e}"
        )
        print(f"  P_ref_statcom first samples: {p_ref_statcom_trace[:10]}")
    if statcom_error_sq_trace is not None:
        print(
            f"  Vdc_ref^2 - Vdc^2: t0={statcom_error_sq_trace[0]: .9e}, "
            f"pre_min={np.min(statcom_error_sq_trace[pre_event]): .9e}, "
            f"pre_max={np.max(statcom_error_sq_trace[pre_event]): .9e}"
        )
        print(f"  Vdc squared-error first samples: {statcom_error_sq_trace[:10]}")
    if statcom_cap_current is not None and statcom_cap_dv is not None:
        cap_i_trace = trace_or_runtime_constant(statcom_cap_current)
        cap_dv_trace = trace_or_runtime_constant(statcom_cap_dv)
        if cap_i_trace is not None and cap_dv_trace is not None:
            print(
                f"  DC capacitor current/dV at t0: i_cap={cap_i_trace[0]: .9e}, "
                f"dVcap={cap_dv_trace[0]: .9e}, C={STATCOM_DC_CAPACITANCE_F: .9e}"
            )
            print(f"  DC capacitor current first samples: {cap_i_trace[:10]}")

    print("Closed-loop first-step controller table:")
    table_vars = [
        ("t", None),
        ("i_d", i_d_vsc),
        ("i_d_ref", i_d_ref_vsc),
        ("err_d", None),
        ("vd_hat", y_vd_hat_vsc),
        ("v_d_c", v_d_c_vsc),
        ("i_q", i_q_vsc),
        ("i_q_ref", i_q_ref_vsc),
        ("err_q", None),
        ("vq_hat", y_vq_hat_vsc),
        ("v_q_c", v_q_c_vsc),
        ("Q", Q),
        ("P", P),
    ]
    header = " ".join(f"{label:>12s}" for label, _ in table_vars)
    print(header)
    n_table = min(20, len(t))
    for row_idx in range(n_table):
        row_values = []
        for label, var in table_vars:
            if label == "t":
                value = t[row_idx]
            elif label == "err_d":
                value = y[row_idx, problem.get_var_idx(i_d_ref_vsc)] - y[row_idx, problem.get_var_idx(i_d_vsc)]
            elif label == "err_q":
                value = y[row_idx, problem.get_var_idx(i_q_ref_vsc)] - y[row_idx, problem.get_var_idx(i_q_vsc)]
            else:
                value = y[row_idx, problem.get_var_idx(var)]
            row_values.append(f"{value:12.5e}")
        print(" ".join(row_values))

    print("Closed-loop sampled controller table:")
    print(header)
    sampled_rows = np.unique(np.linspace(0, len(t) - 1, min(16, len(t)), dtype=int))
    for row_idx in sampled_rows:
        row_values = []
        for label, var in table_vars:
            if label == "t":
                value = t[row_idx]
            elif label == "err_d":
                value = y[row_idx, problem.get_var_idx(i_d_ref_vsc)] - y[row_idx, problem.get_var_idx(i_d_vsc)]
            elif label == "err_q":
                value = y[row_idx, problem.get_var_idx(i_q_ref_vsc)] - y[row_idx, problem.get_var_idx(i_q_vsc)]
            else:
                value = y[row_idx, problem.get_var_idx(var)]
            row_values.append(f"{value:12.5e}")
        print(" ".join(row_values))

    for label, var in [("Vdc", Vdc), ("Vdc_ref", vdc_ref_var), ("Vm_ac_ref", vm_ac_ref_var), ("Q_ref", q_ref_var), ("u_Vdc_ctrl", u_vdc_ctrl), ("u_Vac_ctrl", u_vac_ctrl), ("u_Qac_ctrl", u_qac_ctrl), ("P", P), ("Q", Q), ("theta", theta_vsc), ("omega", omega_vsc), ("v_d_g", v_d_g), ("v_q_g", v_q_g), ("i_d", i_d_vsc), ("i_q", i_q_vsc), ("i_d_ref", i_d_ref_vsc), ("i_q_ref", i_q_ref_vsc), ("v_d_c", v_d_c_vsc), ("v_q_c", v_q_c_vsc)]:
        full_trace = trace_or_runtime_constant(var)
        if full_trace is None:
            print(f"Skipping {label}: not a solved variable")
            continue
        trace = full_trace[pre_event]
        print(f"Pre-event max |Delta {label}|: {np.max(np.abs(trace - trace[0])):.6e}")
        print(f"  {label}: t0={trace[0]:.6e}, min={np.min(trace):.6e}, max={np.max(trace):.6e}")
        print(f"  {label} first samples: {trace[:5]}")

    p_calc = 0.5 * (
        y[pre_event, problem.get_var_idx(v_d_g)] * y[pre_event, problem.get_var_idx(i_d_vsc)]
        + y[pre_event, problem.get_var_idx(v_q_g)] * y[pre_event, problem.get_var_idx(i_q_vsc)]
    )
    print(f"  P equation calc first samples: {p_calc[:5]}")
    print(f"  P trace minus calc first samples: {(y[pre_event, problem.get_var_idx(P)] - p_calc)[:5]}")
    print("dq voltage diagnostics:")
    for label, var in (("v_d_g", v_d_g), ("v_q_g", v_q_g)):
        trace = y[:, problem.get_var_idx(var)]
        pre_trace = trace[pre_event]
        print(
            f"  {label}: t0={trace[0]: .9e}, pre_last={pre_trace[-1]: .9e}, "
            f"pre_min={np.min(pre_trace): .9e}, pre_max={np.max(pre_trace): .9e}, "
            f"pre_pp={np.max(pre_trace) - np.min(pre_trace): .9e}"
        )
        print(f"  {label} first samples: {pre_trace[:10]}")
    print_trace_diagnostics(
        "PLL/dq internal derivative diagnostics:",
        [
            ("theta", theta_vsc),
            ("dt(theta)", dt_theta_vsc, theta_vsc),
            ("omega", omega_vsc),
            ("dt(omega)", dt_omega_vsc, omega_vsc),
            ("u_PLL_pi", u_pll_pi),
            ("dt(u_PLL_pi)", dt_u_pll_pi, u_pll_pi),
            ("xi_PLL", xi_pll),
            ("dt(xi_PLL)", dt_xi_pll, xi_pll),
            ("v_d_g", v_d_g),
            ("dt(v_d_g) numeric", dt_vg_d, v_d_g, True),
            ("v_q_g", v_q_g),
            ("dt(v_q_g) numeric", dt_vg_q, v_q_g, True),
        ],
    )
    omega_base_trace = trace_or_runtime_constant(omega_base_pll)
    omega_base_value = 2.0 * np.pi * grid.fBase if omega_base_trace is None else float(omega_base_trace[0])
    print("PLL constants:")
    print(f"  omega_base={omega_base_value: .9e}")
    for pll_gain_name in ("Kp_pll", "Ki_pll"):
        pll_gain_var = find_name_in_block(pll_gain_name, vsc_mdl)
        if pll_gain_var is not None and pll_gain_var.uid in problem.uid2idx_event_params:
            pll_gain_value = problem.event_params_values[problem.uid2idx_event_params[pll_gain_var.uid]]
            print(f"  {pll_gain_name}={pll_gain_value: .9e}")
    theta_dot_trace = trace_or_runtime_constant(dt_theta_vsc)
    omega_trace = trace_or_runtime_constant(omega_vsc)
    if theta_dot_trace is not None and omega_trace is not None:
        theta_dot_error = theta_dot_trace - omega_base_value * omega_trace
        print("PLL theta derivative consistency:")
        print(f"  dt(theta)(0)={theta_dot_trace[0]: .9e}, omega_base*omega(0)={(omega_base_value * omega_trace[0]): .9e}, error={theta_dot_error[0]: .9e}")
        print(f"  pre-event max |dt(theta)-omega_base*omega|={np.max(np.abs(theta_dot_error[pre_event])):.9e}")
    q_ref_trace = trace_or_runtime_constant(q_ref_var)
    if q_ref_trace is not None:
        q_trace = y[:, problem.get_var_idx(Q)]
        q_error = q_ref_trace - q_trace
        print("Q control initialization check:")
        print(f"  Q(0)={q_trace[0]: .9e}, Q_ref(0)={q_ref_trace[0]: .9e}, Q_ref-Q={q_error[0]: .9e}")
        print(f"  pre-event max |Q_ref-Q|={np.max(np.abs(q_error[pre_event])):.9e}")
        print(f"  Q_ref-Q first samples: {q_error[pre_event][:5]}")
        if u_qac_ctrl is not None:
            u_qac_trace = y[:, problem.get_var_idx(u_qac_ctrl)]
            print(f"  u_Qac_ctrl(0)={u_qac_trace[0]: .9e}, u_Qac_ctrl first samples: {u_qac_trace[pre_event][:5]}")

    theta_trace = y[:, problem.get_var_idx(theta_vsc)]
    va_pcc_trace = y[:, problem.get_var_idx(v_A_bus2)]
    vb_pcc_trace = y[:, problem.get_var_idx(v_B_bus2)]
    vc_pcc_trace = y[:, problem.get_var_idx(v_C_bus2)]
    park_convention_traces = [
        ("theta", *park_dq_from_abc(theta_trace, va_pcc_trace, vb_pcc_trace, vc_pcc_trace)),
        ("-theta", *park_dq_from_abc(-theta_trace, va_pcc_trace, vb_pcc_trace, vc_pcc_trace)),
        ("theta + pi/2", *park_dq_from_abc(theta_trace + 0.5 * np.pi, va_pcc_trace, vb_pcc_trace, vc_pcc_trace)),
        ("pi/2 - theta", *park_dq_from_abc(0.5 * np.pi - theta_trace, va_pcc_trace, vb_pcc_trace, vc_pcc_trace)),
    ]
    print("PLL/Park convention diagnostic at PCC:")
    convention_scores = []
    for label, d_trace, q_trace in park_convention_traces:
        d_pre = d_trace[pre_event]
        q_pre = q_trace[pre_event]
        d_rms = float(np.sqrt(np.mean(d_pre * d_pre)))
        q_mean = float(np.mean(q_pre))
        q_abs_mean = float(np.mean(np.abs(q_pre)))
        convention_scores.append((d_rms, label))
        print(
            f"  {label}: d_rms={d_rms: .9e}, d_min={np.min(d_pre): .9e}, "
            f"d_max={np.max(d_pre): .9e}, q_mean={q_mean: .9e}, mean|q|={q_abs_mean: .9e}"
        )
    best_d_rms, best_label = min(convention_scores, key=lambda item: item[0])
    print(f"  best d-axis cancellation: {best_label} (d_rms={best_d_rms: .9e})")

    va_b1_trace = y[:, problem.get_var_idx(v_A_bus1)]
    vb_b1_trace = y[:, problem.get_var_idx(v_B_bus1)]
    vc_b1_trace = y[:, problem.get_var_idx(v_C_bus1)]
    ia_from_trace = y[:, problem.get_var_idx(i_A_line12_from)]
    ib_from_trace = y[:, problem.get_var_idx(i_B_line12_from)]
    ic_from_trace = y[:, problem.get_var_idx(i_C_line12_from)]
    ia_to_trace = y[:, problem.get_var_idx(i_A_line12_to)]
    ib_to_trace = y[:, problem.get_var_idx(i_B_line12_to)]
    ic_to_trace = y[:, problem.get_var_idx(i_C_line12_to)]

    p_abc_from = (va_b1_trace * ia_from_trace + vb_b1_trace * ib_from_trace + vc_b1_trace * ic_from_trace) / 3.0
    q_abc_from = (1.0 / (3.0 * np.sqrt(3.0))) * (
        (va_b1_trace - vb_b1_trace) * ic_from_trace
        + (vb_b1_trace - vc_b1_trace) * ia_from_trace
        + (vc_b1_trace - va_b1_trace) * ib_from_trace
    )
    p_abc_to = (va_pcc_trace * ia_to_trace + vb_pcc_trace * ib_to_trace + vc_pcc_trace * ic_to_trace) / 3.0
    q_abc_to = (1.0 / (3.0 * np.sqrt(3.0))) * (
        (va_pcc_trace - vb_pcc_trace) * ic_to_trace
        + (vb_pcc_trace - vc_pcc_trace) * ia_to_trace
        + (vc_pcc_trace - va_pcc_trace) * ib_to_trace
    )
    ia_vsc_trace = y[:, problem.get_var_idx(i_A_vsc)]
    ib_vsc_trace = y[:, problem.get_var_idx(i_B_vsc)]
    ic_vsc_trace = y[:, problem.get_var_idx(i_C_vsc)]
    kcl_a = ia_vsc_trace + ia_from_trace
    kcl_b = ib_vsc_trace + ib_from_trace
    kcl_c = ic_vsc_trace + ic_from_trace
    p_vsc_ac = (va_b1_trace * ia_vsc_trace + vb_b1_trace * ib_vsc_trace + vc_b1_trace * ic_vsc_trace) / 3.0
    q_vsc_ac = (1.0 / (3.0 * np.sqrt(3.0))) * (
        (va_b1_trace - vb_b1_trace) * ic_vsc_trace
        + (vb_b1_trace - vc_b1_trace) * ia_vsc_trace
        + (vc_b1_trace - va_b1_trace) * ib_vsc_trace
    )
    print("VSC current/KCL diagnostic:")
    print(
        f"  max |i_vsc + if_line12|: A={np.max(np.abs(kcl_a[pre_event])): .9e}, "
        f"B={np.max(np.abs(kcl_b[pre_event])): .9e}, C={np.max(np.abs(kcl_c[pre_event])): .9e}"
    )
    print(f"  kcl first samples A/B/C: {kcl_a[pre_event][:5]}, {kcl_b[pre_event][:5]}, {kcl_c[pre_event][:5]}")
    print(f"  VSC abc P first samples: {p_vsc_ac[pre_event][:5]}")
    print(f"  line from abc P first samples: {p_abc_from[pre_event][:5]}")
    print(f"  VSC + line from P first samples: {(p_vsc_ac + p_abc_from)[pre_event][:5]}")
    print(f"  VSC abc Q first samples: {q_vsc_ac[pre_event][:5]}")
    print(f"  line from abc Q first samples: {q_abc_from[pre_event][:5]}")
    print(f"  VSC + line from Q first samples: {(q_vsc_ac + q_abc_from)[pre_event][:5]}")
    p_model = y[:, problem.get_var_idx(P)]
    q_model = y[:, problem.get_var_idx(Q)]
    print("P/Q abc-vs-dq convention diagnostic:")
    for label, p_abc, q_abc in (("B1/line12-from", p_abc_from, q_abc_from), ("B2/line12-to", p_abc_to, q_abc_to)):
        print(
            f"  model-vs-{label}: P_rms_err={np.sqrt(np.mean((p_model[pre_event] - p_abc[pre_event]) ** 2)): .9e}, "
            f"P_neg_rms_err={np.sqrt(np.mean((p_model[pre_event] + p_abc[pre_event]) ** 2)): .9e}, "
            f"Q_rms_err={np.sqrt(np.mean((q_model[pre_event] - q_abc[pre_event]) ** 2)): .9e}, "
            f"Q_neg_rms_err={np.sqrt(np.mean((q_model[pre_event] + q_abc[pre_event]) ** 2)): .9e}"
        )
        print(f"  {label} abc P first samples: {p_abc[pre_event][:5]}")
        print(f"  {label} abc Q first samples: {q_abc[pre_event][:5]}")
    print(f"  model P first samples: {p_model[pre_event][:5]}")
    print(f"  model Q first samples: {q_model[pre_event][:5]}")

    voltage_candidates = [
        ("v(theta)", *park_dq_from_abc(theta_trace, va_pcc_trace, vb_pcc_trace, vc_pcc_trace)),
        ("v(-theta)", *park_dq_from_abc(-theta_trace, va_pcc_trace, vb_pcc_trace, vc_pcc_trace)),
    ]
    current_candidates = [
        ("i(theta)", *park_dq_from_abc(theta_trace, ia_from_trace, ib_from_trace, ic_from_trace)),
        ("i(-theta)", *park_dq_from_abc(-theta_trace, ia_from_trace, ib_from_trace, ic_from_trace)),
    ]
    candidate_rows = []
    for v_label, vd_trace, vq_trace in voltage_candidates:
        for i_label, id_trace, iq_trace in current_candidates:
            for id_sign, iq_sign in ((1.0, 1.0), (1.0, -1.0), (-1.0, 1.0), (-1.0, -1.0)):
                id_eff = id_sign * id_trace
                iq_eff = iq_sign * iq_trace
                p_dq = 0.5 * (vd_trace * id_eff + vq_trace * iq_eff)
                q_dq = 0.5 * (vd_trace * iq_eff - vq_trace * id_eff)
                p_err = float(np.sqrt(np.mean((p_dq[pre_event] - p_abc_from[pre_event]) ** 2)))
                q_err = float(np.sqrt(np.mean((q_dq[pre_event] - q_abc_from[pre_event]) ** 2)))
                q_neg_err = float(np.sqrt(np.mean((q_dq[pre_event] + q_abc_from[pre_event]) ** 2)))
                candidate_rows.append((p_err + min(q_err, q_neg_err), p_err, q_err, q_neg_err, v_label, i_label, id_sign, iq_sign))
    candidate_rows.sort(key=lambda row: row[0])
    print("  best dq P/Q reconstruction candidates:")
    for _, p_err, q_err, q_neg_err, v_label, i_label, id_sign, iq_sign in candidate_rows[:8]:
        print(
            f"    {v_label}, {i_label}, id_sign={id_sign:+.0f}, iq_sign={iq_sign:+.0f}: "
            f"P_rms_err={p_err: .9e}, Q_rms_err={q_err: .9e}, Q_neg_rms_err={q_neg_err: .9e}"
        )

# Plot 1: Bus 1 Three-phase voltages
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(v_A_bus1)], label="v_A (pu)", color='r')
plt.plot(t, y[:, problem.get_var_idx(v_B_bus1)], label="v_B (pu)", color='g')
plt.plot(t, y[:, problem.get_var_idx(v_C_bus1)], label="v_C (pu)", color='b')
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Voltage (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'Bus 1 Voltages (EMT): {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
save_and_show_or_close_plot("bus1_voltages.png")

# Plot 2: Bus 2 Three-phase voltages
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(v_A_bus2)], label="v_A (pu)", color='r')
plt.plot(t, y[:, problem.get_var_idx(v_B_bus2)], label="v_B (pu)", color='g')
plt.plot(t, y[:, problem.get_var_idx(v_C_bus2)], label="v_C (pu)", color='b')
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Voltage (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'Bus 2 Voltages (EMT): {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
save_and_show_or_close_plot("bus2_voltages.png")

# Plot 3: VSC Three-phase currents
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(i_A_vsc)], label="i_A (pu)", color='r')
plt.plot(t, y[:, problem.get_var_idx(i_B_vsc)], label="i_B (pu)", color='g')
plt.plot(t, y[:, problem.get_var_idx(i_C_vsc)], label="i_C (pu)", color='b')
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Current (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC GFL Currents (EMT): {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
save_and_show_or_close_plot("vsc_currents.png")

# Plot 4: VSC P and Q
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(P)], label="P (pu)", color='r')
plt.plot(t, y[:, problem.get_var_idx(Q)], label="Q (pu)", color='b')
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Power (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC GFL Power (EMT): {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
save_and_show_or_close_plot("vsc_power.png")

# Plot 5: VSC model P/Q versus abc instantaneous P/Q
ia_from_trace = y[:, problem.get_var_idx(i_A_line12_from)]
ib_from_trace = y[:, problem.get_var_idx(i_B_line12_from)]
ic_from_trace = y[:, problem.get_var_idx(i_C_line12_from)]
ia_to_trace = y[:, problem.get_var_idx(i_A_line12_to)]
ib_to_trace = y[:, problem.get_var_idx(i_B_line12_to)]
ic_to_trace = y[:, problem.get_var_idx(i_C_line12_to)]
va_b1_trace = y[:, problem.get_var_idx(v_A_bus1)]
vb_b1_trace = y[:, problem.get_var_idx(v_B_bus1)]
vc_b1_trace = y[:, problem.get_var_idx(v_C_bus1)]
va_pcc_trace = y[:, problem.get_var_idx(v_A_bus2)]
vb_pcc_trace = y[:, problem.get_var_idx(v_B_bus2)]
vc_pcc_trace = y[:, problem.get_var_idx(v_C_bus2)]
p_abc_from_trace = (va_b1_trace * ia_from_trace + vb_b1_trace * ib_from_trace + vc_b1_trace * ic_from_trace) / 3.0
q_abc_from_trace = (1.0 / (3.0 * np.sqrt(3.0))) * (
    (va_b1_trace - vb_b1_trace) * ic_from_trace
    + (vb_b1_trace - vc_b1_trace) * ia_from_trace
    + (vc_b1_trace - va_b1_trace) * ib_from_trace
)
p_abc_to_trace = (va_pcc_trace * ia_to_trace + vb_pcc_trace * ib_to_trace + vc_pcc_trace * ic_to_trace) / 3.0
q_abc_to_trace = (1.0 / (3.0 * np.sqrt(3.0))) * (
    (va_pcc_trace - vb_pcc_trace) * ic_to_trace
    + (vb_pcc_trace - vc_pcc_trace) * ia_to_trace
    + (vc_pcc_trace - va_pcc_trace) * ib_to_trace
)
fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
axes[0].plot(t, y[:, problem.get_var_idx(P)], label="P model", color='tab:red')
axes[0].plot(t, p_abc_from_trace, label="P abc B1/from", color='tab:red', linestyle='--')
axes[0].plot(t, p_abc_to_trace, label="P abc B2/to", color='tab:orange', linestyle=':')
axes[0].set_ylabel("P (pu)")
axes[0].legend(loc='upper right')
axes[0].grid(True)
axes[1].plot(t, y[:, problem.get_var_idx(Q)], label="Q model", color='tab:blue')
axes[1].plot(t, q_abc_from_trace, label="Q abc B1/from", color='tab:blue', linestyle='--')
axes[1].plot(t, q_abc_to_trace, label="Q abc B2/to", color='tab:cyan', linestyle=':')
axes[1].plot(t, -q_abc_to_trace, label="-Q abc B2/to", color='tab:purple', linestyle='-.')
axes[1].set_xlabel("Time (s)")
axes[1].set_ylabel("Q (pu)")
axes[1].legend(loc='upper right')
axes[1].grid(True)
axes[1].set_xlim([0, xlim])
fig.suptitle(f'VSC P/Q Model vs abc: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
fig.tight_layout()
save_and_show_or_close_plot("vsc_power_model_vs_abc.png")

# Plot 6: VSC outer-loop generated current references
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(i_d_ref_vsc)], label="i_d_ref from Qac loop", color='tab:blue')
plt.plot(t, y[:, problem.get_var_idx(i_d_vsc)], label="i_d actual", color='tab:blue', linestyle='--')
plt.plot(t, y[:, problem.get_var_idx(i_q_ref_vsc)], label="i_q_ref from Vdc loop", color='tab:red')
plt.plot(t, y[:, problem.get_var_idx(i_q_vsc)], label="i_q actual", color='tab:red', linestyle='--')
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Current reference (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC Outer-Loop Current References: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
save_and_show_or_close_plot("vsc_outer_loop_current_refs.png")

# Plot 7: VSC outer-loop errors and controlled quantities
vdc_ref_trace = trace_or_runtime_constant(vdc_ref_var)
p_ref_trace = trace_or_runtime_constant(p_ref_var)
vm_ac_ref_trace = trace_or_runtime_constant(vm_ac_ref_var)
fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
if u_vdc_ctrl is not None:
    axes[0].plot(t, y[:, problem.get_var_idx(Vdc)], label="Vdc measured", color='tab:red')
    if vdc_ref_trace is not None:
        axes[0].plot(t, vdc_ref_trace, label="Vdc_ref", color='tab:red', linestyle='--')
    axes[0].plot(t, y[:, problem.get_var_idx(u_vdc_ctrl)], label="u_Vdc_ctrl = Vdc_ref - Vdc", color='tab:orange')
    axes[0].set_ylabel("DC voltage / error")
elif u_pac_ctrl is not None or u_pdc_ctrl is not None:
    active_ctrl = u_pac_ctrl if u_pac_ctrl is not None else u_pdc_ctrl
    active_name = "u_Pac_ctrl" if u_pac_ctrl is not None else "u_Pdc_ctrl"
    axes[0].plot(t, y[:, problem.get_var_idx(P)], label="P measured", color='tab:red')
    if p_ref_trace is not None:
        axes[0].plot(t, p_ref_trace, label="P_ref", color='tab:red', linestyle='--')
    axes[0].plot(t, y[:, problem.get_var_idx(active_ctrl)], label=f"{active_name} = P_ref - P", color='tab:orange')
    axes[0].set_ylabel("Active power / error")
axes[0].legend(loc='upper right')
axes[0].grid(True)


if u_qac_ctrl is not None:
    axes[1].plot(t, y[:, problem.get_var_idx(Q)], label="Q measured", color='tab:purple')
    q_ref_trace = trace_or_runtime_constant(q_ref_var)
    if q_ref_trace is not None:
        axes[1].plot(t, q_ref_trace, label="Q_ref", color='tab:purple', linestyle='--')
    axes[1].plot(t, y[:, problem.get_var_idx(u_qac_ctrl)], label="u_Qac_ctrl = Q_ref - Q", color='tab:green')
axes[1].set_xlabel("Time (s)")
axes[1].set_ylabel("Reactive power / error")
axes[1].legend(loc='upper right')
axes[1].grid(True)
axes[1].set_xlim([0, xlim])
fig.suptitle(f'VSC Outer-Loop Errors: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
fig.tight_layout()
save_and_show_or_close_plot("vsc_outer_loop_errors.png")

# Plot 8: VSC grid voltage in dq frame
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(v_d_g)], label="v_d_g", color='tab:blue')
plt.plot(t, y[:, problem.get_var_idx(v_q_g)], label="v_q_g", color='tab:orange')
plt.axhline(0.0, color='black', linewidth=0.8, linestyle='--')
plt.legend(loc='upper right')
plt.xlabel("Time (s)")
plt.ylabel("Voltage (pu peak)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC Grid Voltage dq Frame: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
save_and_show_or_close_plot("vsc_grid_voltage_dq.png")

# Plot 9: PLL d-axis error and frequency
fig, ax_vd = plt.subplots(figsize=(10, 6))
ax_omega = ax_vd.twinx()
line_vd, = ax_vd.plot(t, y[:, problem.get_var_idx(v_d_g)], label="v_d_g", color='tab:blue')
line_omega, = ax_omega.plot(t, y[:, problem.get_var_idx(omega_vsc)], label="omega", color='tab:orange')
ax_vd.axhline(0.0, color='tab:blue', linewidth=0.8, linestyle='--')
ax_omega.axhline(1.0, color='tab:orange', linewidth=0.8, linestyle='--')
ax_vd.set_xlabel("Time (s)")
ax_vd.set_ylabel("v_d_g (pu peak)", color='tab:blue')
ax_omega.set_ylabel("omega (pu)", color='tab:orange')
ax_vd.tick_params(axis='y', labelcolor='tab:blue')
ax_omega.tick_params(axis='y', labelcolor='tab:orange')
ax_vd.set_xlim([0, xlim])
ax_vd.grid(True)
ax_vd.legend([line_vd, line_omega], [line_vd.get_label(), line_omega.get_label()], loc='upper right')
fig.tight_layout()
plt.title(f'PLL d-Axis Error and Frequency: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
save_and_show_or_close_plot("vsc_pll_vd_omega.png")

# Plot 10: PLL/Park convention candidates at PCC
theta_trace = y[:, problem.get_var_idx(theta_vsc)]
va_pcc_trace = y[:, problem.get_var_idx(v_A_bus2)]
vb_pcc_trace = y[:, problem.get_var_idx(v_B_bus2)]
vc_pcc_trace = y[:, problem.get_var_idx(v_C_bus2)]
park_convention_traces = [
    ("theta", *park_dq_from_abc(theta_trace, va_pcc_trace, vb_pcc_trace, vc_pcc_trace)),
    ("-theta", *park_dq_from_abc(-theta_trace, va_pcc_trace, vb_pcc_trace, vc_pcc_trace)),
    ("theta + pi/2", *park_dq_from_abc(theta_trace + 0.5 * np.pi, va_pcc_trace, vb_pcc_trace, vc_pcc_trace)),
    ("pi/2 - theta", *park_dq_from_abc(0.5 * np.pi - theta_trace, va_pcc_trace, vb_pcc_trace, vc_pcc_trace)),
]
fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
for label, d_trace, q_trace in park_convention_traces:
    axes[0].plot(t, d_trace, label=f"d({label})")
    axes[1].plot(t, q_trace, label=f"q({label})")
axes[0].axhline(0.0, color='black', linewidth=0.8, linestyle='--')
axes[0].set_ylabel("d-axis voltage")
axes[0].legend(loc='upper right', ncol=2)
axes[0].grid(True)
axes[1].axhline(0.0, color='black', linewidth=0.8, linestyle='--')
axes[1].set_xlabel("Time (s)")
axes[1].set_ylabel("q-axis voltage")
axes[1].legend(loc='upper right', ncol=2)
axes[1].grid(True)
axes[1].set_xlim([0, xlim])
fig.suptitle(f'PLL/Park Convention Candidates at PCC: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
fig.tight_layout()
save_and_show_or_close_plot("vsc_pll_park_convention_candidates.png")

# Plot 11: PLL angle and frequency
fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
axes[0].plot(t, y[:, problem.get_var_idx(theta_vsc)], label="theta", color='tab:blue')
axes[0].set_ylabel("theta (rad)")
axes[0].legend(loc='upper right')
axes[0].grid(True)
axes[1].plot(t, y[:, problem.get_var_idx(omega_vsc)], label="omega", color='tab:orange')
axes[1].axhline(1.0, color='black', linewidth=0.8, linestyle='--', label="nominal")
axes[1].set_xlabel("Time (s)")
axes[1].set_ylabel("omega (pu)")
axes[1].legend(loc='upper right')
axes[1].grid(True)
axes[1].set_xlim([0, xlim])
fig.suptitle(f'VSC PLL Angle and Frequency: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
fig.tight_layout()
save_and_show_or_close_plot("vsc_pll_theta_omega.png")

# Plot 12: PLL related variables
pll_plot_items = [
    ("theta", theta_vsc, None, False, "rad"),
    ("dt(theta)", dt_theta_vsc, theta_vsc, False, "rad/s"),
    ("omega", omega_vsc, None, False, "pu"),
    ("dt(omega)", dt_omega_vsc, omega_vsc, False, "pu/s"),
    ("u_PLL_pi", u_pll_pi, None, False, "pu peak"),
    ("xi_PLL", xi_pll, None, False, "pu peak s"),
    ("dt(xi_PLL)", dt_xi_pll, xi_pll, False, "pu peak"),
    ("v_d_g", v_d_g, None, False, "pu peak"),
    ("dt(v_d_g) numeric", dt_vg_d, v_d_g, True, "pu/s"),
    ("v_q_g", v_q_g, None, False, "pu peak"),
    ("dt(v_q_g) numeric", dt_vg_q, v_q_g, True, "pu/s"),
]
available_pll_plot_items = [
    (label, var, source_var, force_numeric, ylabel)
    for label, var, source_var, force_numeric, ylabel in pll_plot_items
    if trace_or_numeric_derivative(var, source_var, force_numeric=force_numeric) is not None
]
fig, axes = plt.subplots(len(available_pll_plot_items), 1, figsize=(10, max(8, 2.0 * len(available_pll_plot_items))), sharex=True)
if len(available_pll_plot_items) == 1:
    axes = [axes]
for ax, (label, var, source_var, force_numeric, ylabel) in zip(axes, available_pll_plot_items):
    trace = trace_or_numeric_derivative(var, source_var, force_numeric=force_numeric)
    ax.plot(t, trace, label=label)
    if label == "omega":
        ax.axhline(1.0, color='black', linewidth=0.8, linestyle='--', label="nominal")
    elif label == "dt(theta)":
        ax.axhline(omega_base_value, color='black', linewidth=0.8, linestyle='--', label="omega_base")
    elif label in ("u_PLL_pi", "xi_PLL", "dt(xi_PLL)", "v_d_g", "dt(v_d_g) numeric", "dt(omega)", "dt(v_q_g) numeric"):
        ax.axhline(0.0, color='black', linewidth=0.8, linestyle='--')
    ax.set_ylabel(ylabel)
    ax.legend(loc='upper right')
    ax.grid(True)
axes[-1].set_xlabel("Time (s)")
axes[-1].set_xlim([0, xlim])
fig.suptitle(f'VSC PLL Related Variables: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
fig.tight_layout()
save_and_show_or_close_plot("vsc_pll_all_variables.png")

# Plot 13: DC Voltage
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(Vdc)], label="Vdc (pu)", color='b')
plt.legend(loc='upper right')
plt.xlabel("Time (s)")
plt.ylabel("Voltage (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC DC Voltage (EMT): {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
save_and_show_or_close_plot("dc_voltage.png")

# Plot 14: STATCOM DC voltage control loop
vdc_trace = y[:, problem.get_var_idx(Vdc)]
vdc_ref_trace = trace_or_runtime_constant(vdc_ref_var)
p_ref_statcom_trace = trace_or_runtime_constant(p_ref_statcom_var)
u_statcom_trace = trace_or_runtime_constant(u_statcom_vdc_ctrl)
cap_i_trace = trace_or_runtime_constant(statcom_cap_current)
cap_dv_trace = trace_or_runtime_constant(statcom_cap_dv)
dc_sq_error_trace = None
if vdc_ref_trace is not None:
    dc_sq_error_trace = STATCOM_DC_POWER_SIGN * (vdc_ref_trace ** 2 - vdc_trace ** 2)

fig, axes = plt.subplots(5, 1, figsize=(10, 12), sharex=True)
axes[0].plot(t, vdc_trace, label="Vdc", color='tab:blue')
if vdc_ref_trace is not None:
    axes[0].plot(t, vdc_ref_trace, label="Vdc_ref", color='black', linestyle='--')
axes[0].set_ylabel("Vdc (pu)")
axes[0].legend(loc='upper right')
axes[0].grid(True)

if dc_sq_error_trace is not None:
    axes[1].plot(t, dc_sq_error_trace, label="Vdc_ref^2 - Vdc^2", color='tab:orange')
if u_statcom_trace is not None:
    axes[1].plot(t, u_statcom_trace, label="u_STATCOM_Vdc_ctrl", color='tab:red', linestyle='--')
axes[1].axhline(0.0, color='black', linewidth=0.8, linestyle=':')
axes[1].set_ylabel("DC error")
axes[1].legend(loc='upper right')
axes[1].grid(True)

if p_ref_statcom_trace is not None:
    axes[2].plot(t, p_ref_statcom_trace, label="P_ref_statcom", color='tab:green')
axes[2].plot(t, y[:, problem.get_var_idx(P)], label="P measured", color='tab:red', linestyle='--')
axes[2].axhline(0.0, color='black', linewidth=0.8, linestyle=':')
axes[2].set_ylabel("P (pu)")
axes[2].legend(loc='upper right')
axes[2].grid(True)

axes[3].plot(t, y[:, problem.get_var_idx(i_q_ref_vsc)], label="i_q_ref", color='tab:purple')
axes[3].plot(t, y[:, problem.get_var_idx(i_q_vsc)], label="i_q", color='tab:purple', linestyle='--')
axes[3].set_ylabel("q-axis current")
axes[3].legend(loc='upper right')
axes[3].grid(True)

if cap_i_trace is not None:
    axes[4].plot(t, cap_i_trace, label="i_dc_cap", color='tab:brown')
if cap_dv_trace is not None:
    axes[4].plot(t, cap_dv_trace, label="dVcap", color='tab:cyan', linestyle='--')
axes[4].axhline(0.0, color='black', linewidth=0.8, linestyle=':')
axes[4].set_xlabel("Time (s)")
axes[4].set_ylabel("Cap state")
axes[4].legend(loc='upper right')
axes[4].grid(True)
axes[4].set_xlim([0, xlim])
fig.suptitle("STATCOM DC Voltage Control Loop")
fig.tight_layout()
save_and_show_or_close_plot("statcom_dc_control_loop.png")

print(f"\nEMT Simulation completed with control modes: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}")
print("Supported combinations:")
print("  - Pac + Qac: Active and reactive power control")
print("  - Pac + Vm_ac: Active power and AC voltage control")
print("  - Pdc + Qac: DC power and reactive power control")
print("  - Pdc + Vm_ac: DC power and AC voltage control")
print("  - Vm_dc + Qac: DC voltage and reactive power control")
print("  - Vm_dc + Vm_ac: DC voltage and AC voltage control")
