from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_grounding_link_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, ShuntConnectionType, SolverType, VarPowerFlowReferenceType
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory

import VeraGridEngine.api as gce


def _get_demo_options() -> EmtOptions:
    return EmtOptions(
        time_step=5e-6,
        simulation_time=0.03,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=0,
    )


def _get_pf_options() -> PowerFlowOptions:
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=False,
        generate_report=False,
    )


def _get_four_wire_matrices() -> tuple[np.ndarray, np.ndarray]:
    z_nabc = np.array([
        [0.2735 + 1j * 0.8143, 0.0173 + 1j * 0.0509, 0.0173 + 1j * 0.0509, 0.0173 + 1j * 0.0509],
        [0.0173 + 1j * 0.0509, 0.3465 + 1j * 1.0179, 0.1560 + 1j * 0.5017, 0.1580 + 1j * 0.4236],
        [0.0173 + 1j * 0.0509, 0.1560 + 1j * 0.5017, 0.3375 + 1j * 1.0478, 0.1535 + 1j * 0.3849],
        [0.0173 + 1j * 0.0509, 0.1580 + 1j * 0.4236, 0.1535 + 1j * 0.3849, 0.3414 + 1j * 1.0348],
    ], dtype=complex) / 1.60934

    y_nabc = np.array([
        [1j * 6.1541, -1j * 1.8918, -1j * 2.0022, -1j * 2.2602],
        [-1j * 1.8918, 1j * 6.2998, -1j * 1.9958, -1j * 1.2595],
        [-1j * 2.0022, -1j * 1.9958, 1j * 5.9597, -1j * 0.7417],
        [-1j * 2.2602, -1j * 1.2595, -1j * 0.7417, 1j * 5.6386],
    ], dtype=complex) / (10.0 ** 6) / 1.60934
    return z_nabc, y_nabc


def _build_demo_grid(case_name: str) -> tuple[gce.MultiCircuit, gce.Bus, gce.Load, gce.Load | None]:
    grid = gce.MultiCircuit(Sbase=2.0, fbase=60.0)
    bus0 = gce.Bus(name="Bus0", Vnom=4.16, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=4.16)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    generator = gce.Generator(name="Gen", vset=1.0, Snom=grid.Sbase, freq=60.0, r1=0.001, x1=1.7)
    grid.add_generator(bus=bus0, api_obj=generator)

    z_nabc, y_nabc = _get_four_wire_matrices()
    if case_name == "y_floating":
        line_configuration = gce.create_known_abc_overhead_template(
            name="3 wire line",
            z_nabc=z_nabc[1:, 1:],
            ysh_nabc=y_nabc[1:, 1:],
            phases=np.array([1, 2, 3]),
            Vnom=4.16,
            frequency=60,
        )
        line_has_neutral = False
    elif case_name in {"yg_solid", "yn_grounding_link"}:
        line_configuration = gce.create_known_abc_overhead_template(
            name="4 wire line",
            z_nabc=z_nabc,
            ysh_nabc=y_nabc,
            phases=np.array([0, 1, 2, 3]),
            Vnom=4.16,
            frequency=60,
        )
        line_has_neutral = True
    else:
        raise ValueError(f"Unsupported neutral/ground EMT case '{case_name}'")

    grid.add_overhead_line(line_configuration)
    line = gce.Line(name="Line", bus_from=bus0, bus_to=bus1, length=100.0 * 0.0003048)
    line.apply_template(line_configuration, grid.Sbase, grid.fBase, gce.Logger())
    grid.add_line(obj=line)

    phase_voltage_kv: float = float(bus1.Vnom) / np.sqrt(3.0)
    resistance_ohm: float = 100.0
    active_power_mw: float = float((phase_voltage_kv * phase_voltage_kv) / resistance_ohm)
    main_load = gce.Load(name="Load", P1=active_power_mw, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0)
    main_load.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus1, api_obj=main_load)

    dummy_load_b = gce.Load(name="LoadB", P1=0.0, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0)
    dummy_load_c = gce.Load(name="LoadC", P1=0.0, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0)
    dummy_load_b.conn = ShuntConnectionType.FloatingStar
    dummy_load_c.conn = ShuntConnectionType.FloatingStar
    grid.add_load(bus=bus1, api_obj=dummy_load_b)
    grid.add_load(bus=bus1, api_obj=dummy_load_c)

    source_ground_device: gce.Load | None = None
    external_ground_device: gce.Load | None = None
    if line_has_neutral:
        source_ground_device = gce.Load(name="SourceGround", P1=0.0, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0)
        source_ground_device.conn = ShuntConnectionType.GroundedStar
        grid.add_load(bus=bus0, api_obj=source_ground_device)
    else:
        pass

    if case_name == "yn_grounding_link":
        external_ground_device = gce.Load(name="GroundLink", P1=0.0, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0)
        external_ground_device.conn = ShuntConnectionType.GroundedStar
        grid.add_load(bus=bus1, api_obj=external_ground_device)
    else:
        pass

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    generator_model = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="Gen").block
    line_model = get_pi_line_emt_template(vf=grid.var_factory, phN=line_has_neutral, phA=True, phB=True, phC=True, name="Line").block
    if case_name == "y_floating":
        load_connection = ShuntConnectionType.FloatingStar
    elif case_name == "yg_solid":
        load_connection = ShuntConnectionType.GroundedStar
    else:
        load_connection = ShuntConnectionType.NeutralStar

    main_load_model = get_shunt_rlc_combo_emt_template(
        vf=grid.var_factory,
        include_r=True,
        include_l=False,
        include_c=False,
        phA=True,
        phB=False,
        phC=False,
        connection_type=load_connection,
        direct_r_value=resistance_ohm,
        name="Load_R_ground_demo",
    ).block
    load_b_model = get_shunt_rlc_combo_emt_template(
        vf=grid.var_factory,
        include_r=True,
        include_l=False,
        include_c=False,
        phA=False,
        phB=True,
        phC=False,
        connection_type=ShuntConnectionType.FloatingStar,
        direct_r_value=1.0e9,
        name="Load_B_dummy_demo",
    ).block
    load_c_model = get_shunt_rlc_combo_emt_template(
        vf=grid.var_factory,
        include_r=True,
        include_l=False,
        include_c=False,
        phA=False,
        phB=False,
        phC=True,
        connection_type=ShuntConnectionType.FloatingStar,
        direct_r_value=1.0e9,
        name="Load_C_dummy_demo",
    ).block

    set_emt_model(device=generator, model=generator_model, var_factory=grid.var_factory)
    set_emt_model(device=line, model=line_model, var_factory=grid.var_factory)
    set_emt_model(device=main_load, model=main_load_model, var_factory=grid.var_factory)
    set_emt_model(device=dummy_load_b, model=load_b_model, var_factory=grid.var_factory)
    set_emt_model(device=dummy_load_c, model=load_c_model, var_factory=grid.var_factory)

    if source_ground_device is not None:
        source_ground_model = get_grounding_link_emt_template(
            vf=grid.var_factory,
            include_r=False,
            include_l=False,
            include_c=False,
            solid_connection=True,
            name="Source_Grounding_Link_demo",
        ).block
        set_emt_model(device=source_ground_device, model=source_ground_model, var_factory=grid.var_factory)
    else:
        pass

    if external_ground_device is not None:
        external_ground_model = get_grounding_link_emt_template(
            vf=grid.var_factory,
            include_r=False,
            include_l=False,
            include_c=False,
            solid_connection=True,
            name="Load_Grounding_Link_demo",
        ).block
        set_emt_model(device=external_ground_device, model=external_ground_model, var_factory=grid.var_factory)
    else:
        pass

    return grid, bus1, main_load, external_ground_device


def _run_case(case_name: str) -> Dict[str, object]:
    grid, load_bus, load_device, external_ground_device = _build_demo_grid(case_name)
    power_flow = PowerFlowDriver3Ph(grid, _get_pf_options())
    power_flow.run()
    pf_results_3ph = power_flow.results

    problem = EmtProblemDae(grid=grid, options=_get_demo_options(), pf_results=None, pf_results_3ph=pf_results_3ph)
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
        verbose=False,
    )
    time_vector, y_hist, _dy_hist, _converged, _diag = solver.simulate(boundary_updater=problem)

    load_i_a_var = load_device.emt_model.external_mapping[VarPowerFlowReferenceType.i_A]
    load_i_n_var = load_device.emt_model.external_mapping.get(VarPowerFlowReferenceType.i_N, None)
    bus_v_n_var = load_bus.emt_model.external_mapping.get(VarPowerFlowReferenceType.v_N, None)
    bus_v_a_var = load_bus.emt_model.external_mapping[VarPowerFlowReferenceType.v_A]

    load_i_n_trace = np.zeros(len(time_vector), dtype=float)
    if load_i_n_var is not None:
        load_i_n_trace = np.asarray(y_hist[:, problem.get_var_idx(load_i_n_var)], dtype=float)
    else:
        pass

    bus_v_n_trace = np.zeros(len(time_vector), dtype=float)
    if bus_v_n_var is not None:
        bus_v_n_trace = np.asarray(y_hist[:, problem.get_var_idx(bus_v_n_var)], dtype=float)
    else:
        pass

    traces: Dict[str, object] = dict({
        "time": np.asarray(time_vector, dtype=float),
        "bus_v_n": bus_v_n_trace,
        "bus_v_a": np.asarray(y_hist[:, problem.get_var_idx(bus_v_a_var)], dtype=float),
        "load_i_a": np.asarray(y_hist[:, problem.get_var_idx(load_i_a_var)], dtype=float),
        "load_i_n": load_i_n_trace,
    })

    if external_ground_device is not None:
        grounding_i_n_var = external_ground_device.emt_model.external_mapping[VarPowerFlowReferenceType.i_N]
        traces["grounding_i_n"] = np.asarray(y_hist[:, problem.get_var_idx(grounding_i_n_var)], dtype=float)
    else:
        traces["grounding_i_n"] = np.asarray(np.zeros(len(time_vector), dtype=float))

    steady_index: int = max(1, len(time_vector) // 2)
    traces["steady_abs_load_i_a"] = float(np.mean(np.abs(traces["load_i_a"][steady_index:])))
    traces["steady_abs_load_i_n"] = float(np.mean(np.abs(traces["load_i_n"][steady_index:])))
    traces["steady_abs_bus_v_n"] = float(np.mean(np.abs(traces["bus_v_n"][steady_index:])))
    return traces


def run_neutral_ground_shunt_cases(enable_plots: bool = True) -> Dict[str, object]:
    case_names = ["y_floating", "yg_solid", "yn_grounding_link"]
    case_results: Dict[str, Dict[str, object]] = dict()
    case_name: str

    for case_name in case_names:
        case_results[case_name] = _run_case(case_name)

    output_dir: Path = get_plot_results_directory("neutral_ground_shunt_emt", "symbolic")
    png_path: Path = output_dir / "neutral_ground_shunt_emt_comparison.png"

    figure, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    colors = {
        "y_floating": "tab:gray",
        "yg_solid": "tab:green",
        "yn_grounding_link": "tab:blue",
    }

    for case_name in case_names:
        traces = case_results[case_name]
        axes[0].plot(traces["time"], traces["load_i_a"], label=case_name, color=colors[case_name])
        axes[1].plot(traces["time"], traces["load_i_n"], label=case_name, color=colors[case_name])
        axes[2].plot(traces["time"], traces["bus_v_n"], label=case_name, color=colors[case_name])

    axes[0].set_ylabel("i_A")
    axes[0].set_title("Phase-A Load Current")
    axes[1].set_ylabel("i_N")
    axes[1].set_title("Neutral Current")
    axes[2].set_ylabel("v_N")
    axes[2].set_xlabel("Time [s]")
    axes[2].set_title("Neutral Voltage")

    for axis in axes:
        axis.grid(True)
        axis.legend()

    figure.tight_layout()
    figure.savefig(png_path, dpi=200, bbox_inches="tight")

    if enable_plots:
        plt.show()
    else:
        plt.close(figure)

    return dict({
        "cases": case_results,
        "png_path": str(png_path),
    })


if __name__ == "__main__":
    run_neutral_ground_shunt_cases(enable_plots=True)
