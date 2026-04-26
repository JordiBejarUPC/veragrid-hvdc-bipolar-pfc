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
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.Emt.xfmr_emt_template import get_xfmr_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, ShuntConnectionType, SolverType, VarPowerFlowRefferenceType, WindingType
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory

import VeraGridEngine.api as gce


def _get_demo_options() -> EmtOptions:
    return EmtOptions(
        time_step=5e-6,
        simulation_time=0.06,
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


def _get_four_wire_configuration(vnom: float, frequency_hz: float):
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

    return gce.create_known_abc_overhead_template(
        name="4 wire line",
        z_nabc=z_nabc,
        ysh_nabc=y_nabc,
        phases=np.array([0, 1, 2, 3]),
        Vnom=vnom,
        frequency=frequency_hz,
    )


def _build_xfmr_neutral_grid() -> tuple[gce.MultiCircuit, gce.Transformer2W, gce.Load, gce.Load, gce.Load]:
    grid = gce.MultiCircuit(Sbase=2.0, fbase=60.0)
    bus_hv = gce.Bus(name="Bus_HV", Vnom=4.16, is_slack=True)
    bus_lv_mid = gce.Bus(name="Bus_LV_MID", Vnom=0.48)
    bus_load = gce.Bus(name="Bus_LOAD", Vnom=0.48)
    grid.add_bus(bus_hv)
    grid.add_bus(bus_lv_mid)
    grid.add_bus(bus_load)

    generator = gce.Generator(name="Gen", vset=1.0, Snom=grid.Sbase, freq=60.0, r1=0.001, x1=1.7)
    grid.add_generator(bus=bus_hv, api_obj=generator)

    xfmr = gce.Transformer2W(
        name="XFMR",
        bus_from=bus_hv,
        bus_to=bus_lv_mid,
        HV=4.16,
        LV=0.48,
        nominal_power=0.5,
        rate=0.5,
        r=1.1 * 2.0,
        x=2.0 * 2.0,
    )
    xfmr.conn_f = WindingType.Delta
    xfmr.conn_t = WindingType.GroundedStar
    grid.add_transformer2w(xfmr)

    line_configuration = _get_four_wire_configuration(vnom=4.16, frequency_hz=60.0)
    grid.add_overhead_line(line_configuration)
    line = gce.Line(name="Line", bus_from=bus_lv_mid, bus_to=bus_load, length=100.0 * 0.0003048)
    line.apply_template(line_configuration, grid.Sbase, grid.fBase, gce.Logger())
    grid.add_line(obj=line)

    phase_voltage_kv: float = float(bus_load.Vnom) / np.sqrt(3.0)
    resistance_ohm: float = 1.5
    active_power_mw: float = float((phase_voltage_kv * phase_voltage_kv) / resistance_ohm)
    load = gce.Load(name="Load", P1=active_power_mw, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0)
    load.conn = ShuntConnectionType.NeutralStar
    load_b = gce.Load(name="LoadB", P1=0.0, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0)
    load_c = gce.Load(name="LoadC", P1=0.0, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0)
    load_b.conn = ShuntConnectionType.FloatingStar
    load_c.conn = ShuntConnectionType.FloatingStar
    grid.add_load(bus=bus_load, api_obj=load)
    grid.add_load(bus=bus_load, api_obj=load_b)
    grid.add_load(bus=bus_load, api_obj=load_c)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    generator_model = get_generator_thevenin_rl_emt_template(vf=grid.var_factory, name="Gen").block
    xfmr_model = get_xfmr_emt_template(vf=grid.var_factory, conn_f=xfmr.conn_f, conn_t=xfmr.conn_t, name="XFMR").block
    line_model = get_pi_line_emt_template(vf=grid.var_factory, phN=True, phA=True, phB=True, phC=True, name="Line").block
    load_model = get_shunt_rlc_combo_emt_template(
        vf=grid.var_factory,
        include_r=True,
        include_l=False,
        include_c=False,
        phA=True,
        phB=False,
        phC=False,
        connection_type=ShuntConnectionType.NeutralStar,
        direct_r_value=resistance_ohm,
        name="Load_R_neutral_demo",
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
    set_emt_model(device=xfmr, model=xfmr_model, var_factory=grid.var_factory)
    set_emt_model(device=line, model=line_model, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_model, var_factory=grid.var_factory)
    set_emt_model(device=load_b, model=load_b_model, var_factory=grid.var_factory)
    set_emt_model(device=load_c, model=load_c_model, var_factory=grid.var_factory)
    return grid, xfmr, load, load_b, load_c


def run_xfmr_neutral_case(enable_plots: bool = True) -> Dict[str, object]:
    grid, xfmr, load, _load_b, _load_c = _build_xfmr_neutral_grid()
    power_flow = PowerFlowDriver3Ph(grid, _get_pf_options())
    power_flow.run()
    pf_res_3ph = power_flow.results

    problem = EmtProblemDae(grid=grid, options=_get_demo_options(), pf_results=None, pf_results_3ph=pf_res_3ph)
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
        verbose=False,
    )
    time_vector, y_hist, _dy_hist, _converged, _diag = solver.simulate(boundary_updater=problem)

    bus_mid_v_n_var = grid.buses[1].emt_model.external_mapping[VarPowerFlowRefferenceType.v_N]
    bus_load_v_n_var = grid.buses[2].emt_model.external_mapping[VarPowerFlowRefferenceType.v_N]
    xfmr_it_n_var = xfmr.emt_model.external_mapping[VarPowerFlowRefferenceType.it_N]
    load_i_n_var = load.emt_model.external_mapping[VarPowerFlowRefferenceType.i_N]
    xfmr_it_a_var = xfmr.emt_model.external_mapping[VarPowerFlowRefferenceType.it_A]
    load_i_a_var = load.emt_model.external_mapping[VarPowerFlowRefferenceType.i_A]
    bus_mid_v_n = np.asarray(y_hist[:, problem.get_var_idx(bus_mid_v_n_var)], dtype=float)
    bus_load_v_n = np.asarray(y_hist[:, problem.get_var_idx(bus_load_v_n_var)], dtype=float)
    xfmr_it_n = np.asarray(y_hist[:, problem.get_var_idx(xfmr_it_n_var)], dtype=float)
    load_i_n = np.asarray(y_hist[:, problem.get_var_idx(load_i_n_var)], dtype=float)
    xfmr_it_a = np.asarray(y_hist[:, problem.get_var_idx(xfmr_it_a_var)], dtype=float)
    load_i_a = np.asarray(y_hist[:, problem.get_var_idx(load_i_a_var)], dtype=float)

    traces: Dict[str, object] = dict({
        "time": np.asarray(time_vector, dtype=float),
        "bus_mid_v_n": bus_mid_v_n,
        "bus_load_v_n": bus_load_v_n,
        "xfmr_it_n": xfmr_it_n,
        "load_i_n": load_i_n,
        "xfmr_it_a": xfmr_it_a,
        "load_i_a": load_i_a,
    })

    output_dir: Path = get_plot_results_directory("xfmr_neutral_emt", "symbolic")
    voltage_png_path: Path = output_dir / "xfmr_neutral_lv_neutral_voltages.png"
    current_png_path: Path = output_dir / "xfmr_neutral_currents.png"

    figure_voltage = plt.figure(figsize=(10, 5))
    axis_voltage = figure_voltage.add_subplot(1, 1, 1)
    axis_voltage.plot(traces["time"], traces["bus_mid_v_n"], label="Bus_LV_MID v_N", color="tab:blue")
    axis_voltage.plot(traces["time"], traces["bus_load_v_n"], label="Bus_LOAD v_N", color="tab:orange")
    axis_voltage.grid(True)
    axis_voltage.legend()
    axis_voltage.set_xlabel("Time [s]")
    axis_voltage.set_ylabel("Voltage [pu inst]")
    axis_voltage.set_title("XFMR LV Neutral Voltages")
    figure_voltage.tight_layout()
    figure_voltage.savefig(voltage_png_path, dpi=200, bbox_inches="tight")

    figure_current, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(traces["time"], traces["xfmr_it_n"], label="XFMR it_N", color="tab:green")
    axes[0].plot(traces["time"], traces["load_i_n"], label="Load i_N", linestyle="--", color="tab:red")
    axes[0].grid(True)
    axes[0].legend()
    axes[0].set_ylabel("Neutral current [pu inst]")
    axes[0].set_title("XFMR Explicit Neutral Currents")

    axes[1].plot(traces["time"], traces["xfmr_it_a"], label="XFMR it_A", color="tab:green")
    axes[1].plot(traces["time"], traces["load_i_a"], label="Load i_A", linestyle="--", color="tab:red")
    axes[1].grid(True)
    axes[1].legend()
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Phase-A current [pu inst]")
    figure_current.tight_layout()
    figure_current.savefig(current_png_path, dpi=200, bbox_inches="tight")

    if enable_plots:
        plt.show()
    else:
        plt.close(figure_voltage)
        plt.close(figure_current)

    traces["voltage_png_path"] = str(voltage_png_path)
    traces["current_png_path"] = str(current_png_path)
    return traces


if __name__ == "__main__":
    run_xfmr_neutral_case(enable_plots=True)
