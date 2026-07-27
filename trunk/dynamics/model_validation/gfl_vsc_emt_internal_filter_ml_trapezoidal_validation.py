# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""GFL internal-filter reference-vs-ML EMT validation with Trapezoidal run.

The reference warm-up is used as the common settled operating point.  The plotted
comparison window then runs both the original internal-filter equations and the
trig-transform multilinear variant with the Trapezoidal EMT method.
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt


os.environ.setdefault("VERAGRID_GFL_EMT_TIME_STEP", "1e-5")
os.environ.setdefault("VERAGRID_GFL_EMT_SIM_TIME", "0.5")
os.environ.setdefault("VERAGRID_GFL_EMT_WARMUP_TIME", "0.5")
os.environ.setdefault("VERAGRID_GFL_EMT_INTEGRATION_METHOD", "DaeTrapezoidal")

import gfl_vsc_emt_internal_filter_validation as vg
import VeraGridEngine.Utils.Symbolic.symbolic_ml as symbolic_ml


THIS_DIR = Path(__file__).resolve().parent
PLOT_DIR = THIS_DIR / "gfl_vsc_emt_internal_filter_ml_trapezoidal_plots"
WARMUP_METHOD_NAME = os.environ.get("VERAGRID_GFL_EMT_WARMUP_INTEGRATION_METHOD", "DaeBackEuler")
RUN_METHOD_NAME = os.environ.get("VERAGRID_GFL_EMT_RUN_INTEGRATION_METHOD", "DaeTrapezoidal")
USE_WARM_START = os.environ.get("VERAGRID_GFL_EMT_USE_WARM_START", "1") != "0"
INIT_DIAG = os.environ.get("VERAGRID_GFL_EMT_INIT_DIAG", "0") != "0"


def savefig(name: str) -> None:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / name, dpi=150)
    plt.close()


def _ml_trig_aux_block(vf, theta):
    theta_aux = vf.add_var("theta_aux_filter_inv")
    aux_block = vg.Block(
        algebraic_vars=[theta_aux],
        algebraic_eqs=[theta_aux - (vf.add_const(0.0) - theta)],
        init_eqs={theta_aux: vf.add_const(0.0) - theta},
        name="filter_inverse_park_angle_aux",
    )
    trig_block, u_cos, u_sin = symbolic_ml.trig_transform(vf, theta_aux)
    trig_block.name = "filter_inverse_park_trig_transform"
    u_cos.name = "u_cos_filter_inv"
    u_sin.name = "u_sin_filter_inv"

    d_theta_aux = theta_aux.diff_var
    if d_theta_aux is not None and theta.diff_var is not None and u_cos.diff_var is not None and u_sin.diff_var is not None:
        d_theta_aux_expr = vf.add_const(0.0) - theta.diff_var
        trig_block.diff_init_eqs.update({
            d_theta_aux: d_theta_aux_expr,
            u_cos.diff_var: -d_theta_aux_expr * u_sin,
            u_sin.diff_var: d_theta_aux_expr * u_cos,
        })

    trig_block.add(aux_block)
    return trig_block, u_cos, u_sin


def add_internal_filter_block_ml(grid, vsc_mdl) -> None:
    vf = grid.var_factory
    r_filter = vf.add_var("R_filter")
    theta = vg.find_name_in_block("theta", vsc_mdl)
    v_d_c = vg.find_name_in_block("v_d_c", vsc_mdl)
    v_q_c = vg.find_name_in_block("v_q_c", vsc_mdl)
    y_vd_hat = vg.find_name_in_block("y_vd_hat", vsc_mdl)
    y_vq_hat = vg.find_name_in_block("y_vq_hat", vsc_mdl)
    v_d_g = vg.find_name_in_block("vg_d", vsc_mdl)
    v_q_g = vg.find_name_in_block("vg_q", vsc_mdl)
    p_meas = vg.find_name_in_block("P", vsc_mdl)
    q_meas = vg.find_name_in_block("Q", vsc_mdl)
    l_filter = vg.find_name_in_block("L", vsc_mdl)
    omega = vg.find_name_in_block("omega", vsc_mdl)
    i_d = vg.find_name_in_block("i_line_d", vsc_mdl)
    i_q = vg.find_name_in_block("i_line_q", vsc_mdl)
    i_d_ref = vg.find_name_in_block("i_d_ref", vsc_mdl)
    i_q_ref = vg.find_name_in_block("i_q_ref", vsc_mdl)
    u_vd_hat = vg.find_name_in_block("u_vd_hat", vsc_mdl)
    u_vq_hat = vg.find_name_in_block("u_vq_hat", vsc_mdl)
    sqrt3 = vf.add_const(np.sqrt(3.0))
    half = vf.add_const(0.5)
    third = vf.add_const(1.0 / 3.0)
    va_conv = vf.add_var("va_v")
    vb_conv = vf.add_var("vb_v")
    vc_conv = vf.add_var("vc_v")
    i_filter_a = vf.add_var("i_filter_A")
    i_filter_b = vf.add_var("i_filter_B")
    i_filter_c = vf.add_var("i_filter_C")
    d_i_filter_a = vf.add_diff_var(name="dt_i_filter_A", base_var=i_filter_a)
    d_i_filter_b = vf.add_diff_var(name="dt_i_filter_B", base_var=i_filter_b)
    d_i_filter_c = vf.add_diff_var(name="dt_i_filter_C", base_var=i_filter_c)
    omega_base = vf.add_const(2.0 * np.pi * grid.fBase)
    v_bus_a = vg.find_name_in_block("vg_A", vsc_mdl)
    v_bus_b = vg.find_name_in_block("vg_B", vsc_mdl)
    v_bus_c = vg.find_name_in_block("vg_C", vsc_mdl)
    i_vsc_a = vsc_mdl.external_mapping[vg.VarPowerFlowReferenceType.i_A]
    i_vsc_b = vsc_mdl.external_mapping[vg.VarPowerFlowReferenceType.i_B]
    i_vsc_c = vsc_mdl.external_mapping[vg.VarPowerFlowReferenceType.i_C]
    vsc_mdl.update_model(i_vsc_a, i_filter_a)
    vsc_mdl.update_model(i_vsc_b, i_filter_b)
    vsc_mdl.update_model(i_vsc_c, i_filter_c)
    filter_current_uids = {i_filter_a.uid, i_filter_b.uid, i_filter_c.uid}

    for block in vsc_mdl.get_all_blocks():
        filtered_eqs = []
        for eq in block.algebraic_eqs:
            eq_text = str(eq)
            if u_vd_hat is not None and eq_text.startswith("(u_vd_hat) - "):
                filtered_eqs.append(u_vd_hat - (i_d - i_d_ref))
                continue
            if u_vq_hat is not None and eq_text.startswith("(u_vq_hat) - "):
                filtered_eqs.append(u_vq_hat - (i_q - i_q_ref))
                continue
            if p_meas is not None and eq_text.startswith("(P) - ((0.5)"):
                continue
            if q_meas is not None and eq_text.startswith("(Q) - ((0.5)"):
                continue
            if not (
                eq_text.startswith("(v_d_c) - (((y_vd_hat) + (vg_d))")
                or eq_text.startswith("(v_q_c) - (((y_vq_hat) + (vg_q))")
                or eq_text == "(vc_d) - (v_d_c)"
                or eq_text == "(vc_q) - (v_q_c)"
                or eq_text == "((vc_A) + (vc_B)) + (vc_C)"
                or eq_text.startswith("(vc_d) - ((0.3333333333333333)")
                or eq_text.startswith("(vc_q) - ((0.3333333333333333)")
            ):
                filtered_eqs.append(eq)
        block.algebraic_eqs = filtered_eqs
        block.algebraic_vars = [
            var for var in block.algebraic_vars
            if hasattr(var, "non_mutable_uid")
            and getattr(var, "name", None) not in {"vc_d", "vc_q"}
            and getattr(var, "uid", None) not in filter_current_uids
        ]

    trig_block, u_cos, u_sin = _ml_trig_aux_block(vf, theta)
    filter_block = vg.Block(
        algebraic_vars=[va_conv, vb_conv, vc_conv],
        state_vars=[i_filter_a, i_filter_b, i_filter_c],
        diff_vars=[d_i_filter_a, d_i_filter_b, d_i_filter_c],
        state_eqs=[
            omega_base * (v_bus_a - va_conv - r_filter * i_filter_a) / l_filter,
            omega_base * (v_bus_b - vb_conv - r_filter * i_filter_b) / l_filter,
            omega_base * (v_bus_c - vc_conv - r_filter * i_filter_c) / l_filter,
        ],
        algebraic_eqs=[
            p_meas - third * (v_bus_a * i_filter_a + v_bus_b * i_filter_b + v_bus_c * i_filter_c),
            q_meas - (third / sqrt3) * ((v_bus_b - v_bus_c) * i_filter_a + (v_bus_c - v_bus_a) * i_filter_b + (v_bus_a - v_bus_b) * i_filter_c),
            v_d_c - (y_vd_hat + v_d_g + r_filter * i_d - l_filter * omega * i_q),
            v_q_c - (y_vq_hat + v_q_g + r_filter * i_q + l_filter * omega * i_d),
            va_conv - (v_d_c * u_cos + v_q_c * u_sin),
            vb_conv - (v_d_c * (-half * u_cos - half * sqrt3 * u_sin) + v_q_c * (-half * u_sin + half * sqrt3 * u_cos)),
            vc_conv - (v_d_c * (-half * u_cos + half * sqrt3 * u_sin) + v_q_c * (-half * u_sin - half * sqrt3 * u_cos)),
        ],
        event_dict={r_filter: vf.add_const(0.0)},
        name="internal_vsc_filter_rl_ml",
    )
    filter_block.add(trig_block)
    vsc_mdl.add(filter_block)
    vsc_mdl.unify_blocks()


def build_emt_models(grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3, add_filter_fn, add_event=True):
    line23_mdl = vg.get_pi_line_emt_template(vf=grid.var_factory, name="Pi23").block
    gen_mdl = vg.get_generator_thevenin_rl_emt_template_with_ref(grid.var_factory).block
    dc_source_mdl = vg.get_dc_voltage_source_emt_template(
        vf=grid.var_factory,
        source_voltage_value=1.03,
        name="dc_voltage_source",
    ).block
    vsc_mdl = vg.VscGflEmtBuild(
        grid.var_factory,
        control1=vg.ConverterControlType.Pac,
        control2=vg.ConverterControlType.Qac,
        frozen_voltage_source=False,
    ).block
    add_filter_fn(grid, vsc_mdl)

    vg.set_emt_model(device=line23, model=line23_mdl, var_factory=grid.var_factory)
    vg.set_emt_model(device=gen1, model=gen_mdl, var_factory=grid.var_factory)
    vg.set_emt_model(device=dc_source, model=dc_source_mdl, var_factory=grid.var_factory)
    vg.set_emt_model(device=vsc1, model=vsc_mdl, var_factory=grid.var_factory)
    vg.connect_internal_filter_ports(grid, vsc_mdl)
    grid.var_factory.add_connections(
        [vg.find_name_in_block("vg_A", vsc_mdl), vg.find_name_in_block("vg_B", vsc_mdl), vg.find_name_in_block("vg_C", vsc_mdl)],
        [vg.find_name_in_block("v_A", bus2.emt_model), vg.find_name_in_block("v_B", bus2.emt_model), vg.find_name_in_block("v_C", bus2.emt_model)],
    )

    vsc_filter_r = 3.0 * 0.029585798816568046
    vsc_filter_l = 3.0 * 0.07100591715976332
    va_pcc0, vb_pcc0, vc_pcc0 = vg.pf_voltage_abc(grid, pf_results, bus2)
    best_theta_ref = 0.0
    best_abs_d_ref = None
    for theta_candidate in np.linspace(-np.pi, np.pi, 40001):
        vd_candidate, vq_candidate = vg.park_dq_value(theta_candidate, va_pcc0, vb_pcc0, vc_pcc0)
        if vq_candidate > 0.0 and (best_abs_d_ref is None or abs(vd_candidate) < best_abs_d_ref):
            best_abs_d_ref = abs(vd_candidate)
            best_theta_ref = theta_candidate

    line23_idx = grid.lines.index(line23)
    line23_s_from = complex(pf_results.Sf[line23_idx]) / grid.Sbase
    p_ref0 = float(np.real(line23_s_from))
    q_ref0 = float(np.imag(line23_s_from))
    vq_ref0 = vg.park_dq_value(best_theta_ref, va_pcc0, vb_pcc0, vc_pcc0)[1]
    for name, value in (
        ("Vdc_ref", abs(pf_results.voltage[grid.buses.index(bus_dc)])),
        ("Vm_ac_ref", vq_ref0),
        ("P_ref", p_ref0),
        ("Q_ref", q_ref0),
        ("Kp_pol", vg.Q_CONTROL_KP_POL),
        ("Ki_pol", vg.Q_CONTROL_KI_POL),
        ("Kp_icl", vg.CURRENT_CONTROL_KP_ICL),
        ("Ki_icl", vg.CURRENT_CONTROL_KI_ICL),
        ("Kp_pll", vg.PLL_KP),
        ("Ki_pll", vg.PLL_KI),
        ("L", vsc_filter_l),
        ("Cdc", vg.DC_LINK_CAPACITANCE),
        ("R_filter", vsc_filter_r),
        ("L_filter", vsc_filter_l),
    ):
        vg.set_event_value_in_block(grid.var_factory, name, vsc_mdl, value)

    if add_event and vg.P_REF_EVENT_ENABLED:
        p_ref_var = vg.find_name_in_block("P_ref", vsc_mdl)
        p_ref_event_value = p_ref0 + vg.P_REF_EVENT_DELTA
        grid.add_emt_event(vg.EmtEvent(device=vsc1, parameter=p_ref_var, time=vg.P_REF_EVENT_TIME, value=p_ref_event_value))
        print(f"Added P_ref EMT event: t={vg.P_REF_EVENT_TIME:g}, initial={p_ref0:.9e}, value={p_ref_event_value:.9e}")

    return vsc_mdl, dc_source_mdl, p_ref0, best_theta_ref


def _unique_named_vars(vars_iterable):
    named = {}
    duplicates = set()
    for var in vars_iterable:
        name = getattr(var, "name", None)
        if not name:
            continue
        if name in named:
            duplicates.add(name)
        else:
            named[name] = var
    for name in duplicates:
        named.pop(name, None)
    return named


def _block_vars(block):
    vars_list = []
    for child in block.get_all_blocks():
        vars_list.extend(child.state_vars)
        vars_list.extend(child.algebraic_vars)
    return vars_list


def _block_diff_vars(block):
    vars_list = []
    for child in block.get_all_blocks():
        vars_list.extend(child.diff_vars)
    return vars_list


def make_seed(problem, y, dy, vsc_mdl):
    final_y = np.asarray(y[-1, :], dtype=float)
    uid2idx_diff = getattr(problem, "uid2idx_diff", getattr(problem, "_uid2idx_diff", {}))
    seed = {"values": {}, "diff_values": {}, "vsc_values": {}, "vsc_diff_values": {}}

    for scope, vars_iter in (("values", list(problem.get_state_vars()) + list(problem.get_algebraic_vars())), ("vsc_values", _block_vars(vsc_mdl))):
        for name, var in _unique_named_vars(vars_iter).items():
            if var.uid in problem._uid2idx_vars:
                seed[scope][name] = float(final_y[problem.get_var_idx(var)])

    if dy is not None and len(uid2idx_diff) > 0:
        final_dy = np.asarray(dy[-1, :], dtype=float)
        for scope, vars_iter in (("diff_values", problem.get_diff_vars()), ("vsc_diff_values", _block_diff_vars(vsc_mdl))):
            for name, var in _unique_named_vars(vars_iter).items():
                idx = uid2idx_diff.get(var.uid, None)
                if idx is not None and idx < final_dy.size:
                    seed[scope][name] = float(final_dy[idx])
    return seed


def apply_seed(problem, seed, vsc_mdl):
    for scope, vars_iter in (("values", list(problem.get_state_vars()) + list(problem.get_algebraic_vars())), ("vsc_values", _block_vars(vsc_mdl))):
        target = _unique_named_vars(vars_iter)
        for name, value in seed.get(scope, {}).items():
            var = target.get(name)
            if var is not None:
                problem.init_guess[var.uid] = float(value)

    for scope, vars_iter in (("diff_values", problem.get_diff_vars()), ("vsc_diff_values", _block_diff_vars(vsc_mdl))):
        target = _unique_named_vars(vars_iter)
        for name, value in seed.get(scope, {}).items():
            var = target.get(name)
            if var is not None:
                problem.diff_init_guess[var.uid] = float(value)


def seed_ml_trig_from_theta(problem, vsc_mdl):
    theta = vg.find_name_in_block("theta", vsc_mdl)
    if theta is None or theta.uid not in problem.init_guess:
        return
    theta_aux_value = -float(problem.init_guess[theta.uid])
    vg.set_init_if_exists(problem, vsc_mdl, "theta_aux_filter_inv", theta_aux_value)
    vg.set_init_if_exists(problem, vsc_mdl, "u_cos_filter_inv", np.cos(theta_aux_value))
    vg.set_init_if_exists(problem, vsc_mdl, "u_sin_filter_inv", np.sin(theta_aux_value))

    theta_aux = vg.find_name_in_block("theta_aux_filter_inv", vsc_mdl)
    u_cos = vg.find_name_in_block("u_cos_filter_inv", vsc_mdl)
    u_sin = vg.find_name_in_block("u_sin_filter_inv", vsc_mdl)
    if theta.diff_var is None or theta.diff_var.uid not in problem.diff_init_guess:
        return
    d_theta_aux_value = -float(problem.diff_init_guess[theta.diff_var.uid])
    if theta_aux is not None and theta_aux.diff_var is not None:
        problem.diff_init_guess[theta_aux.diff_var.uid] = d_theta_aux_value
    if u_cos is not None and u_cos.diff_var is not None:
        problem.diff_init_guess[u_cos.diff_var.uid] = -d_theta_aux_value * np.sin(theta_aux_value)
    if u_sin is not None and u_sin.diff_var is not None:
        problem.diff_init_guess[u_sin.diff_var.uid] = d_theta_aux_value * np.cos(theta_aux_value)


def make_options(method_name: str, sim_time: float | None = None):
    return vg.EmtOptions(
        time_step=vg.VERAGRID_GFL_EMT_TIME_STEP,
        simulation_time=vg.VERAGRID_GFL_EMT_SIM_TIME if sim_time is None else sim_time,
        tolerance=1e-6,
        integration_method=vg.DynamicIntegrationMethod[method_name],
        solver_type=vg.EmtSolverTypes.StructuralAD,
        initialization_method=vg.EmtInitializationMethod.Explicit,
        verbose=0,
    )


def build_case(label: str, use_ml: bool, add_event=True):
    add_filter_fn = add_internal_filter_block_ml if use_ml else vg.add_internal_filter_block
    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = vg.build_grid()
    pf_results = vg.run_power_flow(grid)
    vsc_mdl, dc_source_mdl, p_ref0, theta_ref = build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3, add_filter_fn, add_event=add_event
    )
    options = make_options(RUN_METHOD_NAME)
    problem = vg.EmtProblemDae(grid=grid, options=options, pf_results=pf_results)
    vg.seed_internal_filter_guess(problem, grid, pf_results, vsc_mdl, dc_source_mdl, line23, bus_dc, bus2, theta_ref)
    return grid, bus2, vsc_mdl, problem, options, p_ref0


def run_reference_warmup_seed():
    _grid, _bus2, vsc_mdl, problem, _options, _p_ref0 = build_case("reference_warmup", use_ml=False, add_event=False)
    warmup_options = make_options(WARMUP_METHOD_NAME, sim_time=vg.VERAGRID_GFL_EMT_WARMUP_TIME)
    print(f"[reference_warmup] event-free warm-up: {vg.VERAGRID_GFL_EMT_WARMUP_TIME:g} s, method={WARMUP_METHOD_NAME}")
    tw, yw, dyw, warm_well_initialized, warm_converged = vg.run_emt(problem, warmup_options, vg.VERAGRID_GFL_EMT_WARMUP_TIME)
    print(f"[reference_warmup] samples={len(tw)}, well_initialized={warm_well_initialized}, converged={warm_converged}")
    if not (warm_well_initialized and warm_converged):
        return None
    return make_seed(problem, yw, dyw, vsc_mdl)


def run_case(label: str, use_ml: bool, seed=None, add_event=True):
    grid, bus2, vsc_mdl, problem, options, p_ref0 = build_case(label, use_ml=use_ml, add_event=add_event)

    if seed is not None:
        print(f"[{label}] applying event-free reference warm-up seed; run method={RUN_METHOD_NAME}")
        apply_seed(problem, seed, vsc_mdl)
        if use_ml:
            seed_ml_trig_from_theta(problem, vsc_mdl)
    else:
        print(f"[{label}] cold start; run method={RUN_METHOD_NAME}")
        if use_ml:
            seed_ml_trig_from_theta(problem, vsc_mdl)

    t, y, dy, well_initialized, converged = vg.run_emt(problem, options, vg.VERAGRID_GFL_EMT_SIM_TIME)
    print(f"[{label}] samples={len(t)}, well_initialized={well_initialized}, converged={converged}")
    return {"label": label, "grid": grid, "bus2": bus2, "vsc_mdl": vsc_mdl, "problem": problem, "time": np.asarray(t), "values": np.asarray(y), "dy": dy, "p_ref0": p_ref0, "converged": converged}


def trace(case, name, block=None):
    search_block = case["problem"].sys_block if block is None else block
    var = vg.find_name_in_block(name, search_block)
    if var is None or var.uid not in case["problem"]._uid2idx_vars:
        raise KeyError(f"{case['label']}: variable {name!r} not found")
    return case["values"][:, case["problem"].get_var_idx(var)]


def _value_at(case, name, k=0):
    var = vg.find_name_in_block(name, case["vsc_mdl"])
    if var is None or var.uid not in case["problem"]._uid2idx_vars:
        return None
    return float(case["values"][k, case["problem"].get_var_idx(var)])


def _diff_value_at(case, name, k=0):
    var = vg.find_name_in_block(name, case["vsc_mdl"])
    if var is None:
        return None
    uid2idx_diff = getattr(case["problem"], "uid2idx_diff", getattr(case["problem"], "_uid2idx_diff", {}))
    idx = uid2idx_diff.get(var.uid, None)
    if idx is None or case["dy"] is None:
        return None
    return float(case["dy"][k, idx])


def _filter_rhs_from_values(values):
    r_filter = 3.0 * 0.029585798816568046
    l_filter = 3.0 * 0.07100591715976332
    omega_base = 2.0 * np.pi * 50.0
    return {
        "dt_i_filter_A": omega_base * (values["v_A"] - values["va_v"] - r_filter * values["i_filter_A"]) / l_filter,
        "dt_i_filter_B": omega_base * (values["v_B"] - values["vb_v"] - r_filter * values["i_filter_B"]) / l_filter,
        "dt_i_filter_C": omega_base * (values["v_C"] - values["vc_v"] - r_filter * values["i_filter_C"]) / l_filter,
    }


def print_initial_step_diagnostics(case):
    if case["values"].shape[0] < 2:
        return

    h = float(case["time"][1] - case["time"][0])
    print(f"[{case['label']}] initial-step diagnostics, h={h:.12e}")
    names = [
        "P", "Q", "theta", "omega", "vg_d", "vg_q", "v_d_c", "v_q_c",
        "i_line_d", "i_line_q", "i_d_ref", "i_q_ref",
        "v_A", "v_B", "v_C", "va_v", "vb_v", "vc_v",
        "i_filter_A", "i_filter_B", "i_filter_C",
    ]
    state_uids = {var.uid for var in case["problem"].get_state_vars()}
    for name in names:
        var = vg.find_name_in_block(name, case["vsc_mdl"])
        if var is None or var.uid not in case["problem"]._uid2idx_vars:
            continue
        x0 = _value_at(case, name, 0)
        x1 = _value_at(case, name, 1)
        dx0 = None
        predictor = None
        if var.uid in state_uids and var.diff_var is not None:
            uid2idx_diff = getattr(case["problem"], "uid2idx_diff", getattr(case["problem"], "_uid2idx_diff", {}))
            idx = uid2idx_diff.get(var.diff_var.uid, None)
            if idx is not None:
                dx0 = float(case["dy"][0, idx])
                predictor = x0 + h * dx0
        if predictor is None:
            print(f"  {name}: x0={x0:.12e}, x1={x1:.12e}, dx={x1 - x0:.12e}")
        else:
            print(f"  {name}: x0={x0:.12e}, dx0={dx0:.12e}, euler_pred={predictor:.12e}, x1={x1:.12e}, x1-pred={x1 - predictor:.12e}")

    for k in (0, 1):
        values = {name: _value_at(case, name, k) for name in ("v_A", "v_B", "v_C", "va_v", "vb_v", "vc_v", "i_filter_A", "i_filter_B", "i_filter_C")}
        rhs = _filter_rhs_from_values(values)
        print(f"  filter RHS consistency at accepted sample {k}, t={case['time'][k]:.12e}")
        for phase_name, diff_name in (("A", "dt_i_filter_A"), ("B", "dt_i_filter_B"), ("C", "dt_i_filter_C")):
            dx = _diff_value_at(case, diff_name, k)
            print(f"    {diff_name}: dy={dx:.12e}, rhs={rhs[diff_name]:.12e}, dy-rhs={dx - rhs[diff_name]:.12e}")


def plot_and_report(reference, ml):
    t_ref = reference["time"]
    t_ml = ml["time"]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(t_ref, trace(reference, "P", reference["vsc_mdl"]), label="ref P")
    axes[0].plot(t_ml, trace(ml, "P", ml["vsc_mdl"]), "--", label="ML P")
    axes[0].plot(t_ref, trace(reference, "Q", reference["vsc_mdl"]), label="ref Q")
    axes[0].plot(t_ml, trace(ml, "Q", ml["vsc_mdl"]), "--", label="ML Q")
    axes[0].set_ylabel("Power (pu)")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")
    for name in ("i_filter_A", "i_filter_B", "i_filter_C"):
        axes[1].plot(t_ref, trace(reference, name, reference["vsc_mdl"]), label=f"ref {name}")
        axes[1].plot(t_ml, trace(ml, name, ml["vsc_mdl"]), "--", label=f"ML {name}")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Filter current (pu peak)")
    axes[1].grid(True)
    axes[1].legend(loc="upper right", ncol=2)
    fig.suptitle(f"GFL Internal Filter ML, warm-up={WARMUP_METHOD_NAME}, run={RUN_METHOD_NAME}")
    savefig("pq_currents.png")

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for name in ("vg_d", "vg_q"):
        axes[0].plot(t_ref, trace(reference, name, reference["vsc_mdl"]), label=f"ref {name}")
        axes[0].plot(t_ml, trace(ml, name, ml["vsc_mdl"]), "--", label=f"ML {name}")
    axes[0].set_ylabel("Grid dq voltage")
    axes[0].grid(True)
    axes[0].legend(loc="upper right", ncol=2)
    for name in ("v_d_c", "v_q_c"):
        axes[1].plot(t_ref, trace(reference, name, reference["vsc_mdl"]), label=f"ref {name}")
        axes[1].plot(t_ml, trace(ml, name, ml["vsc_mdl"]), "--", label=f"ML {name}")
    axes[1].set_ylabel("Converter dq voltage")
    axes[1].grid(True)
    axes[1].legend(loc="upper right", ncol=2)
    for name in ("i_line_d", "i_line_q"):
        axes[2].plot(t_ref, trace(reference, name, reference["vsc_mdl"]), label=f"ref {name}")
        axes[2].plot(t_ml, trace(ml, name, ml["vsc_mdl"]), "--", label=f"ML {name}")
    axes[2].set_xlabel("Time (s)")
    axes[2].set_ylabel("Line current dq")
    axes[2].grid(True)
    axes[2].legend(loc="upper right", ncol=2)
    fig.suptitle("dq Voltages and Currents")
    savefig("dq_voltages_currents.png")

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for name in ("i_d_ref", "i_q_ref"):
        axes[0].plot(t_ref, trace(reference, name, reference["vsc_mdl"]), label=f"ref {name}")
        axes[0].plot(t_ml, trace(ml, name, ml["vsc_mdl"]), "--", label=f"ML {name}")
    axes[0].set_ylabel("Current refs")
    axes[0].grid(True)
    axes[0].legend(loc="upper right", ncol=2)
    axes[1].plot(t_ref, trace(reference, "i_line_d", reference["vsc_mdl"]) - trace(reference, "i_d_ref", reference["vsc_mdl"]), label="ref i_d - i_d_ref")
    axes[1].plot(t_ml, trace(ml, "i_line_d", ml["vsc_mdl"]) - trace(ml, "i_d_ref", ml["vsc_mdl"]), "--", label="ML i_d - i_d_ref")
    axes[1].plot(t_ref, trace(reference, "i_line_q", reference["vsc_mdl"]) - trace(reference, "i_q_ref", reference["vsc_mdl"]), label="ref i_q - i_q_ref")
    axes[1].plot(t_ml, trace(ml, "i_line_q", ml["vsc_mdl"]) - trace(ml, "i_q_ref", ml["vsc_mdl"]), "--", label="ML i_q - i_q_ref")
    axes[1].set_ylabel("Current error")
    axes[1].grid(True)
    axes[1].legend(loc="upper right", ncol=2)
    axes[2].plot(t_ref, trace(reference, "omega", reference["vsc_mdl"]), label="ref omega")
    axes[2].plot(t_ml, trace(ml, "omega", ml["vsc_mdl"]), "--", label="ML omega")
    axes[2].set_xlabel("Time (s)")
    axes[2].set_ylabel("PLL omega")
    axes[2].grid(True)
    axes[2].legend(loc="upper right")
    fig.suptitle("Current Controller and PLL")
    savefig("dq_current_control_pll.png")

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(t_ref, trace(reference, "theta", reference["vsc_mdl"]), label="ref theta")
    axes[0].plot(t_ml, trace(ml, "theta", ml["vsc_mdl"]), "--", label="ML theta")
    axes[0].set_ylabel("theta (rad)")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")
    theta_err = np.interp(t_ref, t_ml, trace(ml, "theta", ml["vsc_mdl"])) - trace(reference, "theta", reference["vsc_mdl"])
    axes[1].plot(t_ref, theta_err, label="ML theta - ref theta")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("theta error (rad)")
    axes[1].grid(True)
    axes[1].legend(loc="upper right")
    fig.suptitle("PLL Angle")
    savefig("pll_theta.png")

    theta_ml = trace(ml, "theta", ml["vsc_mdl"])
    u_cos = trace(ml, "u_cos_filter_inv", ml["vsc_mdl"])
    u_sin = trace(ml, "u_sin_filter_inv", ml["vsc_mdl"])
    plt.figure(figsize=(10, 5))
    plt.plot(t_ml, u_cos * u_cos + u_sin * u_sin - 1.0, label="u_cos^2 + u_sin^2 - 1")
    plt.plot(t_ml, u_cos - np.cos(-theta_ml), label="u_cos - cos(-theta)")
    plt.plot(t_ml, u_sin - np.sin(-theta_ml), label="u_sin - sin(-theta)")
    plt.xlabel("Time (s)")
    plt.ylabel("Error")
    plt.grid(True)
    plt.legend(loc="upper right")
    plt.title("ML Trig Auxiliary Consistency")
    savefig("trig_consistency.png")

    names = ["P", "Q", "vg_d", "vg_q", "v_d_c", "v_q_c", "i_filter_A", "i_filter_B", "i_filter_C", "omega"]
    for name in names:
        ref_values = trace(reference, name, reference["vsc_mdl"])
        ml_values = np.interp(t_ref, t_ml, trace(ml, name, ml["vsc_mdl"]))
        err = ml_values - ref_values
        idx = int(np.argmax(np.abs(err)))
        print(f"  max |ML-reference| {name}: {abs(err[idx]):.6e} at t={t_ref[idx]:.6f}")
    steady_names = ["P", "Q", "vg_d", "vg_q", "v_d_c", "v_q_c", "i_line_d", "i_line_q", "i_d_ref", "i_q_ref", "omega"]
    for case in (reference, ml):
        print(f"  {case['label']} peak-to-peak movement:")
        for name in steady_names:
            values = trace(case, name, case["vsc_mdl"])
            print(f"    {name}: first={values[0]:.6e}, last={values[-1]:.6e}, ptp={np.ptp(values):.6e}")
    print(f"  max |u_norm-1|: {np.max(np.abs(u_cos * u_cos + u_sin * u_sin - 1.0)):.6e}")
    print(f"  max |u_cos-cos(-theta)|: {np.max(np.abs(u_cos - np.cos(-theta_ml))):.6e}")
    print(f"  max |u_sin-sin(-theta)|: {np.max(np.abs(u_sin - np.sin(-theta_ml))):.6e}")


def main():
    print(f"Warm-up method: {WARMUP_METHOD_NAME}")
    print(f"Run method: {RUN_METHOD_NAME}")
    print(f"Use warm start: {USE_WARM_START}")
    seed = None
    if USE_WARM_START:
        seed = run_reference_warmup_seed()
        if seed is None:
            raise RuntimeError("Reference warm-up failed; cannot seed comparison runs")
    print("Running reference simulation...")
    reference = run_case("reference", use_ml=False, seed=seed)
    print("Running ML simulation...")
    ml = run_case("multilinear", use_ml=True, seed=seed)
    if INIT_DIAG:
        print_initial_step_diagnostics(reference)
        print_initial_step_diagnostics(ml)
    plot_and_report(reference, ml)
    print(f"Plots saved to: {PLOT_DIR}")
    print(f"Both simulations converged={bool(reference['converged']) and bool(ml['converged'])}")


if __name__ == "__main__":
    main()
