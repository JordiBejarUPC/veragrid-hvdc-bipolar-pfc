# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.vsc_gfl_emt import VscGflEmtBuild
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_dc_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import ConverterControlType, DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes
import VeraGridEngine.api as gce


PLOT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "gfl_vsc_emt_internal_filter_validation_plots")


def find_name_in_block(name: str, block: Block):
    """Recursively find a variable/event parameter by exact name, then by generated prefix."""

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

    return find_match(block, allow_prefix=True)


def set_event_value_in_block(vf, name: str, block: Block, value: float) -> bool:
    for var in block.event_dict.keys():
        if name == var.name:
            block.event_dict[var] = vf.add_const(float(value))
            return True

    for mdl in block.children:
        if set_event_value_in_block(vf, name, mdl, value):
            return True

    return False


def set_problem_runtime_value(problem: EmtProblemDae, vf, block: Block, name: str, value: float) -> None:
    problem.set_internal_runtime_if_exists(block, name, value)
    var = find_name_in_block(name, block)
    if var is None:
        return

    idx = problem.uid2idx_event_params.get(var.uid, None)
    if idx is None:
        return

    const_value = vf.add_const(float(value))
    problem.event_params_values[idx] = float(value)
    problem._event_parameters_eqs[idx] = const_value
    if hasattr(problem, "_runtime_parameter_eqs0"):
        problem._runtime_parameter_eqs0[idx] = const_value
    if hasattr(problem, "_runtime_all_eqs_source"):
        problem._runtime_all_eqs_source[idx] = const_value


def pf_voltage_abc(grid: gce.MultiCircuit, pf_results, bus: gce.Bus) -> tuple[float, float, float]:
    v_complex = complex(pf_results.voltage[grid.buses.index(bus)])
    v_peak = np.sqrt(2.0) * abs(v_complex)
    v_angle = np.angle(v_complex)
    return (
        v_peak * np.sin(v_angle),
        v_peak * np.sin(v_angle - 2.0 * np.pi / 3.0),
        v_peak * np.sin(v_angle + 2.0 * np.pi / 3.0),
    )


def park_dq_value(theta_value: float, va_value: float, vb_value: float, vc_value: float) -> tuple[float, float]:
    cos_t = np.cos(theta_value)
    sin_t = np.sin(theta_value)
    sqrt3 = np.sqrt(3.0)
    vd_value = (1.0 / 3.0) * (
        2.0 * cos_t * va_value
        + (-cos_t - sqrt3 * sin_t) * vb_value
        + (-cos_t + sqrt3 * sin_t) * vc_value
    )
    vq_value = (1.0 / 3.0) * (
        2.0 * sin_t * va_value
        + (-sin_t + sqrt3 * cos_t) * vb_value
        + (-sin_t - sqrt3 * cos_t) * vc_value
    )
    return vd_value, vq_value


def inverse_park_value(theta_value: float, vd_value: float, vq_value: float) -> tuple[float, float, float]:
    cos_t = np.cos(theta_value)
    sin_t = np.sin(theta_value)
    sqrt3 = np.sqrt(3.0)
    va_value = vd_value * cos_t + vq_value * sin_t
    vb_value = (-0.5 * vd_value - 0.5 * sqrt3 * vq_value) * cos_t + (0.5 * sqrt3 * vd_value - 0.5 * vq_value) * sin_t
    vc_value = (-0.5 * vd_value + 0.5 * sqrt3 * vq_value) * cos_t + (-0.5 * sqrt3 * vd_value - 0.5 * vq_value) * sin_t
    return va_value, vb_value, vc_value


def set_init_if_exists(problem: EmtProblemDae, block: Block, name: str, value: float) -> None:
    var = find_name_in_block(name, block)
    if var is not None:
        problem.init_guess[var.uid] = float(value)


def trace_for_var(problem: EmtProblemDae, y: np.ndarray, var):
    if var is None or var.uid not in problem._uid2idx_vars:
        return None

    return y[:, problem.get_var_idx(var)]


def save_plot(filename: str) -> None:
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, filename), dpi=150)
    plt.close()


def plot_traces(t: np.ndarray, problem: EmtProblemDae, y: np.ndarray, vsc_mdl: Block, bus_dc: gce.Bus, bus2: gce.Bus) -> None:
    v_a_b2 = trace_for_var(problem, y, find_name_in_block('v_A', bus2.emt_model))
    v_b_b2 = trace_for_var(problem, y, find_name_in_block('v_B', bus2.emt_model))
    v_c_b2 = trace_for_var(problem, y, find_name_in_block('v_C', bus2.emt_model))
    plt.figure(figsize=(10, 6))
    plt.plot(t, v_a_b2, label="v_A")
    plt.plot(t, v_b_b2, label="v_B")
    plt.plot(t, v_c_b2, label="v_C")
    plt.xlabel("Time (s)")
    plt.ylabel("Voltage (pu peak)")
    plt.title("B2 Phase Voltages")
    plt.grid(True)
    plt.legend(loc="upper right")
    plt.tight_layout()
    save_plot("b2_phase_voltages.png")

    i_a = trace_for_var(problem, y, find_name_in_block('i_a_f', vsc_mdl))
    i_b = trace_for_var(problem, y, find_name_in_block('i_b_f', vsc_mdl))
    i_c = trace_for_var(problem, y, find_name_in_block('i_c_f', vsc_mdl))
    plt.figure(figsize=(10, 6))
    plt.plot(t, i_a, label="i_A")
    plt.plot(t, i_b, label="i_B")
    plt.plot(t, i_c, label="i_C")
    plt.xlabel("Time (s)")
    plt.ylabel("Current (pu peak)")
    plt.title("VSC Internal Filter Currents")
    plt.grid(True)
    plt.legend(loc="upper right")
    plt.tight_layout()
    save_plot("vsc_internal_filter_currents.png")

    p_trace = trace_for_var(problem, y, find_name_in_block('P', vsc_mdl))
    q_trace = trace_for_var(problem, y, find_name_in_block('Q', vsc_mdl))
    plt.figure(figsize=(10, 6))
    plt.plot(t, p_trace, label="P")
    plt.plot(t, q_trace, label="Q")
    plt.xlabel("Time (s)")
    plt.ylabel("Power (pu)")
    plt.title("VSC PCC Power")
    plt.grid(True)
    plt.legend(loc="upper right")
    plt.tight_layout()
    save_plot("vsc_pq.png")

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(t, trace_for_var(problem, y, find_name_in_block('vg_d', vsc_mdl)), label="vg_d")
    axes[0].plot(t, trace_for_var(problem, y, find_name_in_block('vg_q', vsc_mdl)), label="vg_q")
    axes[0].plot(t, trace_for_var(problem, y, find_name_in_block('v_d_c', vsc_mdl)), label="v_d_c", linestyle="--")
    axes[0].plot(t, trace_for_var(problem, y, find_name_in_block('v_q_c', vsc_mdl)), label="v_q_c", linestyle="--")
    axes[0].set_ylabel("Voltage (pu peak)")
    axes[0].legend(loc="upper right")
    axes[0].grid(True)

    axes[1].plot(t, trace_for_var(problem, y, find_name_in_block('i_line_d', vsc_mdl)), label="i_d")
    axes[1].plot(t, trace_for_var(problem, y, find_name_in_block('i_line_q', vsc_mdl)), label="i_q")
    axes[1].plot(t, trace_for_var(problem, y, find_name_in_block('i_d_ref', vsc_mdl)), label="i_d_ref", linestyle="--")
    axes[1].plot(t, trace_for_var(problem, y, find_name_in_block('i_q_ref', vsc_mdl)), label="i_q_ref", linestyle="--")
    axes[1].set_ylabel("Current (pu peak)")
    axes[1].legend(loc="upper right")
    axes[1].grid(True)

    vdc_trace = trace_for_var(problem, y, bus_dc.emt_model.out_vars[0])
    axes[2].plot(t, vdc_trace, label="Vdc")
    axes[2].set_xlabel("Time (s)")
    axes[2].set_ylabel("Voltage (pu)")
    axes[2].legend(loc="upper right")
    axes[2].grid(True)
    fig.suptitle("VSC Internal Filter dq Variables and DC Voltage")
    fig.tight_layout()
    save_plot("vsc_dq_and_dc_voltage.png")


def print_problem_structure(problem: EmtProblemDae) -> None:
    state_vars = problem.get_state_vars()
    algebraic_vars = problem.get_algebraic_vars()
    state_eqs = problem.get_state_eqs()
    algebraic_eqs = problem.get_algebraic_eqs()
    state_uids = {var.uid for var in state_vars}
    alg_uids = {var.uid for var in algebraic_vars}
    duplicated = [var.name for var in algebraic_vars if var.uid in state_uids]
    print(
        "EMT structure: "
        f"states={len(state_vars)}, algebraic={len(algebraic_vars)}, "
        f"state_eqs={len(state_eqs)}, algebraic_eqs={len(algebraic_eqs)}, "
        f"unknowns={len(state_vars) + len(algebraic_vars)}, equations={len(state_eqs) + len(algebraic_eqs)}"
    )
    if duplicated:
        print(f"Variables present as both state and algebraic: {duplicated}")


def print_vsc_seed_values(problem: EmtProblemDae, vsc_mdl: Block) -> None:
    x0 = problem.get_x0()
    print("Post-seed VSC/filter x0 values:")
    for name in ('vg_d', 'vg_q', 'v_d_c', 'v_q_c', 'vc_d', 'vc_q', 'va_v', 'vb_v', 'vc_v', 'i_a_f', 'i_b_f', 'i_c_f'):
        var = find_name_in_block(name, vsc_mdl)
        idx = None if var is None or var.uid not in problem._uid2idx_vars else problem.get_var_idx(var)
        if idx is not None:
            print(f"  {name}={x0[idx]: .9e}")


def add_internal_filter_block(grid: gce.MultiCircuit, vsc_mdl: Block) -> None:
    vf = grid.var_factory
    r_filter = vf.add_var('R_filter')
    theta = find_name_in_block('theta', vsc_mdl)
    v_d_c = find_name_in_block('v_d_c', vsc_mdl)
    v_q_c = find_name_in_block('v_q_c', vsc_mdl)
    y_vd_hat = find_name_in_block('y_vd_hat', vsc_mdl)
    y_vq_hat = find_name_in_block('y_vq_hat', vsc_mdl)
    v_d_g = find_name_in_block('vg_d', vsc_mdl)
    v_q_g = find_name_in_block('vg_q', vsc_mdl)
    l_filter = find_name_in_block('L', vsc_mdl)
    omega = find_name_in_block('omega', vsc_mdl)
    i_d = find_name_in_block('i_line_d', vsc_mdl)
    i_q = find_name_in_block('i_line_q', vsc_mdl)
    park_theta = vf.add_const(0.0) - theta
    sqrt3 = vf.add_const(np.sqrt(3.0))
    half = vf.add_const(0.5)
    va_conv = vf.add_var('va_v')
    vb_conv = vf.add_var('vb_v')
    vc_conv = vf.add_var('vc_v')

    filtered_eqs = []
    for eq in vsc_mdl.algebraic_eqs:
        eq_text = str(eq)
        remove_eq = (
            eq_text.startswith("(v_d_c) - (((y_vd_hat) + (vg_d))")
            or eq_text.startswith("(v_q_c) - (((y_vq_hat) + (vg_q))")
            or eq_text == "(vc_d) - (v_d_c)"
            or eq_text == "(vc_q) - (v_q_c)"
            or eq_text == "((vc_A) + (vc_B)) + (vc_C)"
            or eq_text.startswith("(vc_d) - ((0.3333333333333333)")
            or eq_text.startswith("(vc_q) - ((0.3333333333333333)")
        )
        if not remove_eq:
            filtered_eqs.append(eq)
    vsc_mdl.algebraic_eqs = filtered_eqs
    vsc_mdl.algebraic_vars = [
        var for var in vsc_mdl.algebraic_vars
        if var.name not in {'vc_d', 'vc_q'}
    ]

    filter_block = Block(
        algebraic_vars=[va_conv, vb_conv, vc_conv],
        algebraic_eqs=[
            v_d_c - (y_vd_hat + v_d_g + r_filter * i_d - l_filter * omega * i_q),
            v_q_c - (y_vq_hat + v_q_g + r_filter * i_q + l_filter * omega * i_d),
            va_conv - (v_d_c * sym.cos(park_theta) + v_q_c * sym.sin(park_theta)),
            vb_conv - ((-half * v_d_c - half * sqrt3 * v_q_c) * sym.cos(park_theta)
                       + (half * sqrt3 * v_d_c - half * v_q_c) * sym.sin(park_theta)),
            vc_conv - ((-half * v_d_c + half * sqrt3 * v_q_c) * sym.cos(park_theta)
                       + (-half * sqrt3 * v_d_c - half * v_q_c) * sym.sin(park_theta)),
        ],
        event_dict={
            r_filter: vf.add_const(0.0),
        },
        name="internal_vsc_filter_rl",
    )
    vsc_mdl.add(filter_block)
    vsc_mdl.unify_blocks()


def connect_internal_filter_ports(grid: gce.MultiCircuit, vsc_mdl: Block) -> None:
    va_conv = find_name_in_block('va_v', vsc_mdl)
    vb_conv = find_name_in_block('vb_v', vsc_mdl)
    vc_conv = find_name_in_block('vc_v', vsc_mdl)
    i_vsc_a = vsc_mdl.external_mapping[VarPowerFlowReferenceType.i_A]
    i_vsc_b = vsc_mdl.external_mapping[VarPowerFlowReferenceType.i_B]
    i_vsc_c = vsc_mdl.external_mapping[VarPowerFlowReferenceType.i_C]

    grid.var_factory.add_connections(
        vsc_mdl.in_vars[0:3],
        [va_conv, vb_conv, vc_conv],
    )
    grid.var_factory.add_connections(
        [find_name_in_block('i_line_A', vsc_mdl), find_name_in_block('i_line_B', vsc_mdl), find_name_in_block('i_line_C', vsc_mdl)],
        [i_vsc_a, i_vsc_b, i_vsc_c],
    )


def build_grid():
    grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

    bus_dc = gce.Bus(name='Bdc', Vnom=100, is_dc=True)
    bus2 = gce.Bus(name='B2', Vnom=135)
    bus3 = gce.Bus(name='B3', Vnom=135, is_slack=True)

    for bus in (bus_dc, bus2, bus3):
        grid.add_bus(bus)
        get_bus_emt_template(grid, bus)

    line23 = gce.Line(
        name="line 2-3",
        bus_from=bus2,
        bus_to=bus3,
        r=3.0 * 0.029585798816568046,
        x=3.0 * 0.07100591715976332,
        b=0.03 / 3.0,
        rate=900.0,
    )

    vsc1 = gce.VSC(
        name='VSC1',
        bus_from=bus_dc,
        bus_to=bus2,
        rate=100,
        alpha1=0.0,
        alpha2=0.0,
        alpha3=0.0,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_val=1.03,
        control2_val=1.001,
    )
    gen1 = gce.Generator(name='Gen1', P=5.0, vset=1.00, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=1.7)
    dc_source = gce.Generator(name='DC Source', P=3.0, vset=1.03)

    grid.add_line(line23)
    grid.add_vsc(vsc1)
    grid.add_generator(bus=bus3, api_obj=gen1)
    grid.add_generator(bus=bus_dc, api_obj=dc_source)

    return grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source


def run_power_flow(grid: gce.MultiCircuit):
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
    return gce.power_flow(grid, options=options)


def build_emt_models(grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2):
    line23_mdl = get_pi_line_emt_template(vf=grid.var_factory, name="Pi23").block
    gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(grid.var_factory).block
    dc_source_mdl = get_dc_voltage_source_emt_template(
        vf=grid.var_factory,
        source_voltage_value=1.03,
        name="dc_voltage_source",
    ).block
    vsc_mdl = VscGflEmtBuild(
        grid.var_factory,
        control1=ConverterControlType.Pac,
        control2=ConverterControlType.Qac,
        frozen_voltage_source=False,
    ).block
    add_internal_filter_block(grid, vsc_mdl)

    set_emt_model(device=line23, model=line23_mdl, var_factory=grid.var_factory)
    set_emt_model(device=gen1, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=dc_source, model=dc_source_mdl, var_factory=grid.var_factory)
    set_emt_model(device=vsc1, model=vsc_mdl, var_factory=grid.var_factory)
    connect_internal_filter_ports(grid, vsc_mdl)

    grid.var_factory.add_connections(
        [find_name_in_block('vg_A', vsc_mdl), find_name_in_block('vg_B', vsc_mdl), find_name_in_block('vg_C', vsc_mdl)],
        [find_name_in_block('v_A', bus2.emt_model), find_name_in_block('v_B', bus2.emt_model), find_name_in_block('v_C', bus2.emt_model)],
    )

    vsc_filter_r = 3.0 * 0.029585798816568046
    vsc_filter_l = 3.0 * 0.07100591715976332

    va_pcc0, vb_pcc0, vc_pcc0 = pf_voltage_abc(grid, pf_results, bus2)
    best_theta_ref = 0.0
    best_abs_d_ref = None
    for theta_candidate in np.linspace(-np.pi, np.pi, 40001):
        vd_candidate, vq_candidate = park_dq_value(theta_candidate, va_pcc0, vb_pcc0, vc_pcc0)
        if vq_candidate > 0.0 and (best_abs_d_ref is None or abs(vd_candidate) < best_abs_d_ref):
            best_abs_d_ref = abs(vd_candidate)
            best_theta_ref = theta_candidate

    line23_idx = grid.lines.index(line23)
    line23_s_from = complex(pf_results.Sf[line23_idx]) / grid.Sbase
    p_ref0 = float(np.real(line23_s_from))
    q_ref0 = float(np.imag(line23_s_from))
    vq_ref0 = park_dq_value(best_theta_ref, va_pcc0, vb_pcc0, vc_pcc0)[1]

    for name, value in (
        ('Vdc_ref', abs(pf_results.voltage[grid.buses.index(bus_dc)])),
        ('Vm_ac_ref', vq_ref0),
        ('P_ref', p_ref0),
        ('Q_ref', q_ref0),
        ('Kp_pol', 0.02),
        ('Ki_pol', 0.3),
        ('Kp_icl', 1.0),
        ('Ki_icl', 20.0),
        ('Kp_pll', 0.01),
        ('Ki_pll', 0.05),
        ('L', vsc_filter_l),
        ('R_filter', vsc_filter_r),
        ('L_filter', vsc_filter_l),
    ):
        set_event_value_in_block(grid.var_factory, name, vsc_mdl, value)

    return vsc_mdl, line23_mdl, gen_mdl, dc_source_mdl, vsc_filter_l, p_ref0, q_ref0, best_theta_ref


def seed_internal_filter_guess(problem, grid, pf_results, vsc_mdl, dc_source_mdl, line23, bus_dc, bus2, theta_ref):
    va2, vb2, vc2 = pf_voltage_abc(grid, pf_results, bus2)
    vd_g, vq_g = park_dq_value(theta_ref, va2, vb2, vc2)

    line23_idx = grid.lines.index(line23)
    s_to = complex(pf_results.Sf[line23_idx]) / grid.Sbase
    i_q = 2.0 * s_to.real / vq_g
    i_d = 2.0 * s_to.imag / vq_g
    r_filter = 3.0 * 0.029585798816568046
    x_filter = 3.0 * 0.07100591715976332
    vd_c = vd_g + r_filter * i_d - x_filter * i_q
    vq_c = vq_g + r_filter * i_q + x_filter * i_d
    va_conv, vb_conv, vc_conv = inverse_park_value(theta_ref, vd_c, vq_c)
    cos_t = np.cos(theta_ref)
    sin_t = np.sin(theta_ref)
    ia = i_d * cos_t + i_q * sin_t
    ib = (-0.5 * i_d - np.sqrt(3.0) * 0.5 * i_q) * cos_t + (np.sqrt(3.0) * 0.5 * i_d - 0.5 * i_q) * sin_t
    ic = (-0.5 * i_d + np.sqrt(3.0) * 0.5 * i_q) * cos_t + (-np.sqrt(3.0) * 0.5 * i_d - 0.5 * i_q) * sin_t
    vdc0 = abs(pf_results.voltage[grid.buses.index(bus_dc)])
    p_conv = -(va_conv * ia + vb_conv * ib + vc_conv * ic) / 3.0
    omega_base = 2.0 * np.pi * grid.fBase
    dia = omega_base * (va_conv - va2 - r_filter * ia) / x_filter
    dib = omega_base * (vb_conv - vb2 - r_filter * ib) / x_filter
    dic = omega_base * (vc_conv - vc2 - r_filter * ic) / x_filter
    vd_hat = vd_c - (vd_g - x_filter * i_q)
    vq_hat = vq_c - (vq_g + x_filter * i_d)

    values = {
        'P': s_to.real,
        'Q': s_to.imag,
        'P_f': s_to.real,
        'Q_f': s_to.imag,
        'Pt_vsc': -s_to.real,
        'Qt_vsc': -s_to.imag,
        'i_a_f': ia,
        'i_b_f': ib,
        'i_c_f': ic,
        'i_filter_A': ia,
        'i_filter_B': ib,
        'i_filter_C': ic,
        'i_dc': p_conv / vdc0,
        'P_conv': p_conv,
        'theta': -theta_ref,
        'omega': 1.0,
        'xi_PLL': 0.0,
        'vg_d': vd_g,
        'vg_q': vq_g,
        'vc_d': vd_c,
        'vc_q': vq_c,
        'i_line_d': i_d,
        'i_line_q': i_q,
        'i_d_ref': i_d,
        'i_q_ref': i_q,
        'v_d_c': vd_c,
        'v_q_c': vq_c,
        'va_v': va_conv,
        'vb_v': vb_conv,
        'vc_v': vc_conv,
        'u_Pac_ctrl': 0.0,
        'u_Qac_ctrl': 0.0,
        'y_vd_hat': vd_hat,
        'y_vq_hat': vq_hat,
        'u_vd_hat': 0.0,
        'u_vq_hat': 0.0,
        'xi_Pac_ctrl': i_q / 0.3,
        'xi_Qac_ctrl': i_d / 0.3,
        'xi_vd_hat': vd_hat / 20.0,
        'xi_vq_hat': vq_hat / 20.0,
        'u_PLL_pi': vd_g,
    }
    for name, value in values.items():
        set_init_if_exists(problem, vsc_mdl, name, value)

    dc_current = p_conv / vdc0
    for name, value in (('i_dc_dc_voltage_source', dc_current), ('V_src_dc_voltage_source', vdc0 + dc_current / 100.0)):
        var = find_name_in_block(name, dc_source_mdl)
        if var is not None:
            if var.uid in problem._uid2idx_vars:
                problem.init_guess[var.uid] = float(value)
            elif var.uid in problem.uid2idx_event_params:
                problem.event_params_values[problem.uid2idx_event_params[var.uid]] = float(value)

    for name, value in (('P_ref', s_to.real), ('Q_ref', s_to.imag), ('Vm_ac_ref', vq_g)):
        set_problem_runtime_value(problem, grid.var_factory, vsc_mdl, name, value)

    theta_var = find_name_in_block('theta', vsc_mdl)
    if theta_var is not None and theta_var.diff_var is not None:
        problem.diff_init_guess[theta_var.diff_var.uid] = 2.0 * np.pi * grid.fBase
    for name, value in (('dt_i_filter_A', dia), ('dt_i_filter_B', dib), ('dt_i_filter_C', dic)):
        diff_var = find_name_in_block(name, vsc_mdl)
        if diff_var is not None:
            problem.diff_init_guess[diff_var.uid] = float(value)


def main() -> None:
    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = build_grid()
    pf_results = run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")
    print(pf_results.get_bus_df())
    print(pf_results.get_branch_df())

    vsc_mdl, line23_mdl, gen_mdl, dc_source_mdl, vsc_filter_l, p_ref0, q_ref0, theta_ref = build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2
    )
    print("Topology: VSC is connected to B2; only line 2-3 is in the MultiCircuit")
    print(f"Internal VSC filter L from former line 1-2 X: {vsc_filter_l:.9e}")
    print(f"Initial internal-filter references: P_ref={p_ref0:.9e}, Q_ref={q_ref0:.9e}")

    options = EmtOptions(
        time_step=0.0001,
        simulation_time=0.02,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        solver_type=EmtSolverTypes.Automatic,
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results=pf_results)
    seed_internal_filter_guess(problem, grid, pf_results, vsc_mdl, dc_source_mdl, line23, bus_dc, bus2, theta_ref)
    print_problem_structure(problem)
    print_vsc_seed_values(problem, vsc_mdl)

    solver = build_emt_solver(
        options=options,
        problem=problem,
        t0=0.0,
        t_end=options.simulation_time,
        h=options.time_step,
        method=options.integration_method,
    )
    t, y, dy, well_initialized, converged = solver.simulate()
    print(f"EMT well initialized: {well_initialized}")
    print(f"EMT converged: {converged}")
    print(f"Solved samples: {len(t)}")

    for name in ('P', 'Q', 'v_d_c', 'v_q_c', 'vg_d', 'vg_q', 'i_line_d', 'i_line_q'):
        var = find_name_in_block(name, vsc_mdl)
        if var is not None and var.uid in problem._uid2idx_vars:
            trace = y[:, problem.get_var_idx(var)]
            print(f"{name}: t0={trace[0]: .9e}, final={trace[-1]: .9e}")

    plot_traces(t, problem, y, vsc_mdl, bus_dc, bus2)
    print(f"Plots saved to: {PLOT_OUTPUT_DIR}")


if __name__ == '__main__':
    main()
