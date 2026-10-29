import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_dc_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Emt.vsc_gfl_emt import VscGflEmtBuild
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    ConverterControlType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
)


def find_name_in_block(name: str, block: Block):
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
        for child in search_block.children:
            found = find_match(child, allow_prefix)
            if found is not None:
                return found
        return None

    exact = find_match(block, allow_prefix=False)
    return exact if exact is not None else find_match(block, allow_prefix=True)


def set_event_value_in_block(name: str, block: Block, value: float, var_factory) -> bool:
    for var in block.event_dict.keys():
        if name == var.name:
            block.event_dict[var] = var_factory.add_const(float(value))
            return True
    for child in block.children:
        if set_event_value_in_block(name, child, value, var_factory):
            return True
    return False


def x0_value(problem: EmtProblemDae, var) -> float:
    if var is None:
        return np.nan
    if var.uid in problem._uid2idx_vars:
        return float(problem.get_x0()[problem.get_var_idx(var)])
    if var.uid in problem.uid2idx_event_params:
        return float(problem.event_params_values[problem.uid2idx_event_params[var.uid]])
    return np.nan


def vsc_x0(problem: EmtProblemDae, vsc_mdl: Block, name: str) -> float:
    return x0_value(problem, find_name_in_block(name, vsc_mdl))


def state_value(problem: EmtProblemDae, states: np.ndarray, var) -> float:
    if var is None:
        return np.nan
    if var.uid in problem._uid2idx_vars:
        return float(states[problem.get_var_idx(var)])
    if var.uid in problem.uid2idx_event_params:
        return float(problem.event_params_values[problem.uid2idx_event_params[var.uid]])
    return np.nan


def vsc_state_value(problem: EmtProblemDae, states: np.ndarray, vsc_mdl: Block, name: str) -> float:
    return state_value(problem, states, find_name_in_block(name, vsc_mdl))


def print_compare(label: str, actual: float, expected: float) -> None:
    error = actual - expected
    rel = np.nan if abs(expected) < 1e-14 else error / expected
    print(f"  {label:<28s} actual={actual: .9e} expected={expected: .9e} error={error: .3e} rel={rel: .3e}")


def safe_div(num: float, den: float) -> float:
    return np.nan if abs(den) < 1e-14 else num / den


def park_dq(theta: float, a: float, b: float, c: float) -> tuple[float, float]:
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    sqrt3 = np.sqrt(3.0)
    d = (1.0 / 3.0) * (2.0 * cos_t * a + (-cos_t - sqrt3 * sin_t) * b + (-cos_t + sqrt3 * sin_t) * c)
    q = (1.0 / 3.0) * (2.0 * sin_t * a + (-sin_t + sqrt3 * cos_t) * b + (-sin_t - sqrt3 * cos_t) * c)
    return d, q


def phase_power_q(a_v: float, b_v: float, c_v: float, a_i: float, b_i: float, c_i: float) -> tuple[float, float]:
    p_total = a_v * a_i + b_v * b_i + c_v * c_i
    q_total = ((a_v - b_v) * c_i + (b_v - c_v) * a_i + (c_v - a_v) * b_i) / np.sqrt(3.0)
    return p_total / 3.0, q_total / 3.0


def total_power_q(a_v: float, b_v: float, c_v: float, a_i: float, b_i: float, c_i: float) -> tuple[float, float]:
    p_phase, q_phase = phase_power_q(a_v, b_v, c_v, a_i, b_i, c_i)
    return 3.0 * p_phase, 3.0 * q_phase


def pf_voltage_abc(grid: gce.MultiCircuit, pf_results, bus: gce.Bus) -> tuple[float, float, float]:
    v_complex = complex(pf_results.voltage[grid.buses.index(bus)])
    v_peak = np.sqrt(2.0) * abs(v_complex)
    angle = np.angle(v_complex)
    return (
        v_peak * np.sin(angle),
        v_peak * np.sin(angle - 2.0 * np.pi / 3.0),
        v_peak * np.sin(angle + 2.0 * np.pi / 3.0),
    )


def build_case(p_ref_scale: float = 1.0):
    grid = gce.MultiCircuit(Sbase=100)
    grid.fBase = 50.0

    bus_dc = gce.Bus(name='Bdc', Vnom=100, is_dc=True)
    bus1 = gce.Bus(name='B1', Vnom=135)
    bus2 = gce.Bus(name='B2', Vnom=135)
    bus3 = gce.Bus(name='B3', Vnom=135, is_slack=True)
    for bus in (bus_dc, bus1, bus2, bus3):
        grid.add_bus(bus)
        get_bus_emt_template(grid, bus)

    line12 = gce.Line(
        name="line 1-2",
        bus_from=bus1,
        bus_to=bus2,
        r=3.0 * 0.029585798816568046,
        x=3.0 * 0.07100591715976332,
        b=0.03 / 3.0,
        rate=900.0,
    )
    line23 = gce.Line(
        name="line 2-3",
        bus_from=bus2,
        bus_to=bus3,
        r=3.0 * 0.029585798816568046,
        x=3.0 * 0.07100591715976332,
        b=0.03 / 3.0,
        rate=900.0,
    )
    vsc_filter_l = line12.X

    vsc1 = gce.VSC(
        name='VSC1',
        bus_from=bus_dc,
        bus_to=bus1,
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
    gen3 = gce.Generator(name='DC Source', P=1.0, vset=1.03)

    grid.add_line(line12)
    grid.add_line(line23)
    grid.add_vsc(vsc1)
    grid.add_generator(bus=bus3, api_obj=gen1)
    grid.add_generator(bus=bus_dc, api_obj=gen3)

    pf_options = gce.PowerFlowOptions(
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
        branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    pf_results = gce.power_flow(grid, options=pf_options)

    line12_mdl = get_pi_line_emt_template(vf=grid.var_factory, name="Pi12").block
    line23_mdl = get_pi_line_emt_template(vf=grid.var_factory, name="Pi23").block
    genrow_mdl1 = get_generator_thevenin_rl_emt_template_with_ref(grid.var_factory).block
    vsc_mdl = VscGflEmtBuild(
        grid.var_factory,
        control1=ConverterControlType.Pac,
        control2=ConverterControlType.Qac,
        frozen_voltage_source=False,
    ).block
    dc_source = get_dc_voltage_source_emt_template(
        vf=grid.var_factory,
        source_voltage_value=1.03,
        name="dc_voltage_source",
    ).block

    set_emt_model(device=line12, model=line12_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line23, model=line23_mdl, var_factory=grid.var_factory)
    set_emt_model(device=gen1, model=genrow_mdl1, var_factory=grid.var_factory)
    set_emt_model(device=gen3, model=dc_source, var_factory=grid.var_factory)
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

    line12_idx = grid.lines.index(line12)
    line12_st = complex(pf_results.St[line12_idx]) / grid.Sbase
    set_event_value_in_block('Vdc_ref', vsc_mdl, abs(pf_results.voltage[grid.buses.index(vsc1.bus_from)]), grid.var_factory)
    set_event_value_in_block('Vm_ac_ref', vsc_mdl, np.sqrt(2.0) * abs(pf_results.voltage[grid.buses.index(bus2)]), grid.var_factory)
    set_event_value_in_block('P_ref', vsc_mdl, p_ref_scale * line12_st.real, grid.var_factory)
    set_event_value_in_block('Q_ref', vsc_mdl, p_ref_scale * line12_st.imag, grid.var_factory)
    set_event_value_in_block('L', vsc_mdl, vsc_filter_l, grid.var_factory)

    emt_options = EmtOptions(
        time_step=0.0001,
        simulation_time=0.01,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        solver_type=EmtSolverTypes.StructuralAD,
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=emt_options, pf_results=pf_results)
    return grid, pf_results, problem, vsc_mdl, line12_mdl, line12, bus1, bus2, p_ref_scale


def print_diagnostic(label: str, grid, pf_results, problem, vsc_mdl, line12_mdl, line12, bus2, states: np.ndarray, p_ref_scale: float) -> None:
    line_idx = grid.lines.index(line12)
    st_total = complex(pf_results.St[line_idx]) / grid.Sbase
    st_phase = st_total / 3.0

    P = vsc_state_value(problem, states, vsc_mdl, "P")
    Q = vsc_state_value(problem, states, vsc_mdl, "Q")
    P_ref = vsc_state_value(problem, states, vsc_mdl, "P_ref")
    Q_ref = vsc_state_value(problem, states, vsc_mdl, "Q_ref")
    vg_d = vsc_state_value(problem, states, vsc_mdl, "vg_d")
    vg_q = vsc_state_value(problem, states, vsc_mdl, "vg_q")
    i_d = vsc_state_value(problem, states, vsc_mdl, "i_line_d")
    i_q = vsc_state_value(problem, states, vsc_mdl, "i_line_q")

    p_dq_half = 0.5 * (vg_q * i_q + vg_d * i_d)
    q_dq_half = 0.5 * (vg_q * i_d - vg_d * i_q)
    p_dq_three_half = 1.5 * (vg_q * i_q + vg_d * i_d)
    q_dq_three_half = 1.5 * (vg_q * i_d - vg_d * i_q)

    va2 = state_value(problem, states, find_name_in_block('v_A', bus2.emt_model))
    vb2 = state_value(problem, states, find_name_in_block('v_B', bus2.emt_model))
    vc2 = state_value(problem, states, find_name_in_block('v_C', bus2.emt_model))
    ia_to = state_value(problem, states, find_name_in_block('it_Pi12_A', line12_mdl))
    ib_to = state_value(problem, states, find_name_in_block('it_Pi12_B', line12_mdl))
    ic_to = state_value(problem, states, find_name_in_block('it_Pi12_C', line12_mdl))
    p_abc_total, q_abc_total = total_power_q(va2, vb2, vc2, ia_to, ib_to, ic_to)
    p_abc_phase, q_abc_phase = phase_power_q(va2, vb2, vc2, ia_to, ib_to, ic_to)

    va_pf, vb_pf, vc_pf = pf_voltage_abc(grid, pf_results, bus2)
    theta = vsc_state_value(problem, states, vsc_mdl, "theta")
    vd_pf_at_theta, vq_pf_at_theta = park_dq(-theta, va_pf, vb_pf, vc_pf)

    print(f"\n{label}")
    print(f"  p_ref_scale={p_ref_scale: .9e}")
    print(f"  PF St line12 to total={st_total.real: .9e}+j{st_total.imag: .9e}")
    print(f"  PF St line12 to /3   ={st_phase.real: .9e}+j{st_phase.imag: .9e}")
    print("References")
    print_compare("P_ref vs PF total", P_ref, st_total.real)
    print_compare("P_ref vs PF /3", P_ref, st_phase.real)
    print_compare("Q_ref vs PF total", Q_ref, st_total.imag)
    print_compare("Q_ref vs PF /3", Q_ref, st_phase.imag)
    print("Initialized model P/Q")
    print_compare("P vs PF total", P, st_total.real)
    print_compare("P vs PF /3", P, st_phase.real)
    print_compare("Q vs PF total", Q, st_total.imag)
    print_compare("Q vs PF /3", Q, st_phase.imag)
    print("Power equations from initialized dq")
    print_compare("P vs 0.5*dq", P, p_dq_half)
    print_compare("Q vs 0.5*dq", Q, q_dq_half)
    print_compare("P vs 1.5*dq", P, p_dq_three_half)
    print_compare("Q vs 1.5*dq", Q, q_dq_three_half)
    print("ABC power from initialized B2/to line variables")
    print_compare("P vs abc total", P, p_abc_total)
    print_compare("P vs abc /3", P, p_abc_phase)
    print_compare("Q vs abc total", Q, q_abc_total)
    print_compare("Q vs abc /3", Q, q_abc_phase)
    print("Voltage/current initialization")
    print_compare("vg_d vs PF angle", vg_d, vd_pf_at_theta)
    print_compare("vg_q vs PF angle", vg_q, vq_pf_at_theta)
    print_compare("i_q vs 2*PFtotal/vq", i_q, safe_div(2.0 * st_total.real, vg_q))
    print_compare("i_q vs 2*PF/3/vq", i_q, safe_div(2.0 * st_phase.real, vg_q))
    print_compare("i_q vs (2/3)*PFtotal/vq", i_q, safe_div((2.0 / 3.0) * st_total.real, vg_q))
    print_compare("i_d vs 2*PFtotal/vq", i_d, safe_div(2.0 * st_total.imag, vg_q))
    print_compare("i_d vs 2*PF/3/vq", i_d, safe_div(2.0 * st_phase.imag, vg_q))
    print_compare("i_d vs (2/3)*PFtotal/vq", i_d, safe_div((2.0 / 3.0) * st_total.imag, vg_q))


def main() -> None:
    p_ref_scale = 1.0
    if "--phase-ref" in sys.argv:
        p_ref_scale = 1.0 / 3.0

    print("GFL VSC EMT initialization diagnostic")
    grid, pf_results, problem, vsc_mdl, line12_mdl, line12, bus1, bus2, p_ref_scale = build_case(p_ref_scale)
    print_diagnostic("Raw problem.get_x0()", grid, pf_results, problem, vsc_mdl, line12_mdl, line12, bus2, problem.get_x0(), p_ref_scale)

    solver = build_emt_solver(
        options=problem.options,
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
    )
    t, y, dy, well_initialized, converged = solver.simulate()
    print(f"\nSolver status: well_initialized={well_initialized}, converged={converged}")
    print_diagnostic("Simulation returned y[0]", grid, pf_results, problem, vsc_mdl, line12_mdl, line12, bus2, y[0], p_ref_scale)
    if len(t) > 1:
        print_diagnostic("Simulation returned y[1]", grid, pf_results, problem, vsc_mdl, line12_mdl, line12, bus2, y[1], p_ref_scale)


if __name__ == "__main__":
    main()
