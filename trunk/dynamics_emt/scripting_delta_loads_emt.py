from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict

import matplotlib.pyplot as plt
import numpy as np

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_exponential_emt_template import get_exponential_load_emt
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, ShuntConnectionType, SolverType, VarPowerFlowRefferenceType
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory

import VeraGridEngine.api as gce


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


def _get_emt_options() -> EmtOptions:
    return EmtOptions(
        time_step=5e-6,
        simulation_time=0.0,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=0,
    )


def _build_line_configuration(vnom: float, frequency_hz: float):
    z_abc = np.array([
        [0.01 + 1j * 0.03, 0.0 + 0.0j, 0.0 + 0.0j],
        [0.0 + 0.0j, 0.01 + 1j * 0.03, 0.0 + 0.0j],
        [0.0 + 0.0j, 0.0 + 0.0j, 0.01 + 1j * 0.03],
    ], dtype=complex)
    y_abc = np.zeros((3, 3), dtype=complex)
    return gce.create_known_abc_overhead_template(
        name="Delta demo line",
        z_nabc=z_abc,
        ysh_nabc=y_abc,
        phases=np.array([1, 2, 3]),
        Vnom=vnom,
        frequency=frequency_hz,
    )


def _build_delta_demo_grid() -> tuple[gce.MultiCircuit, gce.Line, gce.Generator, gce.Load]:
    grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)
    bus0 = gce.Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10.0)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    generator = gce.Generator(name="Gen", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=0.2)
    line = gce.Line(name="Line", bus_from=bus0, bus_to=bus1, length=0.1, rate=900.0)
    line.apply_template(_build_line_configuration(vnom=10.0, frequency_hz=50.0), grid.Sbase, grid.fBase, gce.Logger())
    load = gce.Load(name="Load", P1=0.10, P2=0.10, P3=0.10, Q1=0.0, Q2=0.0, Q3=0.0)
    load.conn = ShuntConnectionType.Delta

    grid.add_line(line)
    grid.add_generator(bus=bus0, api_obj=generator)
    grid.add_load(bus=bus1, api_obj=load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    return grid, line, generator, load


def _run_power_flow(grid: gce.MultiCircuit):
    power_flow = PowerFlowDriver3Ph(grid, _get_pf_options())
    power_flow.run()
    return power_flow.results


def _build_problem(builder: Callable, case_name: str) -> tuple[EmtProblemDae, gce.Load, object]:
    grid, line, generator, load = _build_delta_demo_grid()
    pf_res_3ph = _run_power_flow(grid)

    generator_model = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="Gen").block
    line_model = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name="Line").block
    load_model = builder(
        vf=grid.var_factory,
        phA=True,
        phB=True,
        phC=True,
        connection_type=ShuntConnectionType.Delta,
        name=case_name,
    ).block

    set_emt_model(device=generator, model=generator_model, var_factory=grid.var_factory)
    set_emt_model(device=line, model=line_model, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_model, var_factory=grid.var_factory)

    problem = EmtProblemDae(grid=grid, options=_get_emt_options(), pf_results=None, pf_results_3ph=pf_res_3ph)
    return problem, load, pf_res_3ph


def _to_instantaneous_series(phasor: complex, time_values: np.ndarray, omega: float) -> np.ndarray:
    return np.sqrt(2.0) * np.imag(phasor * np.exp(1j * omega * time_values))


def _collect_delta_reference(problem: EmtProblemDae, load: gce.Load, pf_res_3ph) -> Dict[str, object]:
    x0 = problem.get_x0()
    bus_index = 1
    omega = 2.0 * np.pi * float(problem.grid.fBase)
    time_values = np.linspace(0.0, 2.0 / float(problem.grid.fBase), 2000, dtype=float)

    v_a_ph = complex(pf_res_3ph.voltage_A[bus_index])
    v_b_ph = complex(pf_res_3ph.voltage_B[bus_index])
    v_c_ph = complex(pf_res_3ph.voltage_C[bus_index])
    v_ab_ph_phase_base = v_a_ph - v_b_ph
    v_bc_ph_phase_base = v_b_ph - v_c_ph
    v_ca_ph_phase_base = v_c_ph - v_a_ph
    v_ab_ph = v_ab_ph_phase_base / np.sqrt(3.0)
    v_bc_ph = v_bc_ph_phase_base / np.sqrt(3.0)
    v_ca_ph = v_ca_ph_phase_base / np.sqrt(3.0)

    s_ab = complex(load.Pa, load.Qa) / float(problem.grid.Sbase)
    s_bc = complex(load.Pb, load.Qb) / float(problem.grid.Sbase)
    s_ca = complex(load.Pc, load.Qc) / float(problem.grid.Sbase)
    i_ab_ph = np.conj(s_ab / v_ab_ph_phase_base)
    i_bc_ph = np.conj(s_bc / v_bc_ph_phase_base)
    i_ca_ph = np.conj(s_ca / v_ca_ph_phase_base)
    i_a_ph = -i_ab_ph + i_ca_ph
    i_b_ph = -i_bc_ph + i_ab_ph
    i_c_ph = -i_ca_ph + i_bc_ph

    bus_model = load.bus.emt_model
    load_model = load.emt_model
    seed_v_a = float(x0[problem.get_var_idx(bus_model.external_mapping[VarPowerFlowRefferenceType.v_A])])
    seed_v_b = float(x0[problem.get_var_idx(bus_model.external_mapping[VarPowerFlowRefferenceType.v_B])])
    seed_v_c = float(x0[problem.get_var_idx(bus_model.external_mapping[VarPowerFlowRefferenceType.v_C])])
    seed_i_a = float(x0[problem.get_var_idx(load_model.external_mapping[VarPowerFlowRefferenceType.i_A])])
    seed_i_b = float(x0[problem.get_var_idx(load_model.external_mapping[VarPowerFlowRefferenceType.i_B])])
    seed_i_c = float(x0[problem.get_var_idx(load_model.external_mapping[VarPowerFlowRefferenceType.i_C])])
    seed_v_ab = float((seed_v_a - seed_v_b) / np.sqrt(3.0))
    seed_v_bc = float((seed_v_b - seed_v_c) / np.sqrt(3.0))
    seed_v_ca = float((seed_v_c - seed_v_a) / np.sqrt(3.0))
    bus_v_ab = _to_instantaneous_series(v_ab_ph, time_values, omega)
    bus_v_bc = _to_instantaneous_series(v_bc_ph, time_values, omega)
    bus_v_ca = _to_instantaneous_series(v_ca_ph, time_values, omega)
    load_i_a = _to_instantaneous_series(i_a_ph, time_values, omega)
    load_i_b = _to_instantaneous_series(i_b_ph, time_values, omega)
    load_i_c = _to_instantaneous_series(i_c_ph, time_values, omega)

    # The demo reference is anchored at the EMT initialization point so the
    # exported steady-state trace and the highlighted x0 sample start together.
    bus_v_ab[0] = seed_v_ab
    bus_v_bc[0] = seed_v_bc
    bus_v_ca[0] = seed_v_ca
    load_i_a[0] = seed_i_a
    load_i_b[0] = seed_i_b
    load_i_c[0] = seed_i_c

    return dict({
        "time": time_values,
        "bus_v_ab": bus_v_ab,
        "bus_v_bc": bus_v_bc,
        "bus_v_ca": bus_v_ca,
        "load_i_a": load_i_a,
        "load_i_b": load_i_b,
        "load_i_c": load_i_c,
        "seed_v_ab": seed_v_ab,
        "seed_v_bc": seed_v_bc,
        "seed_v_ca": seed_v_ca,
        "seed_i_a": seed_i_a,
        "seed_i_b": seed_i_b,
        "seed_i_c": seed_i_c,
    })


def _plot_reference(reference: Dict[str, object], title: str, png_path: Path, enable_plots: bool) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(reference["time"], reference["bus_v_ab"], label="v_AB", color="tab:blue")
    axes[0].plot(reference["time"], reference["bus_v_bc"], label="v_BC", color="tab:orange")
    axes[0].plot(reference["time"], reference["bus_v_ca"], label="v_CA", color="tab:green")
    axes[0].scatter([0.0, 0.0, 0.0], [reference["seed_v_ab"], reference["seed_v_bc"], reference["seed_v_ca"]], color=["tab:blue", "tab:orange", "tab:green"], zorder=3, label="EMT x0")
    axes[0].grid(True)
    axes[0].legend()
    axes[0].set_ylabel("Voltage [pu inst, LL base]")
    axes[0].set_title(title + " - steady-state reference")

    axes[1].plot(reference["time"], reference["load_i_a"], label="i_A", color="tab:blue")
    axes[1].plot(reference["time"], reference["load_i_b"], label="i_B", color="tab:orange")
    axes[1].plot(reference["time"], reference["load_i_c"], label="i_C", color="tab:green")
    axes[1].scatter([0.0, 0.0, 0.0], [reference["seed_i_a"], reference["seed_i_b"], reference["seed_i_c"]], color=["tab:blue", "tab:orange", "tab:green"], zorder=3, label="EMT x0")
    axes[1].grid(True)
    axes[1].legend()
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Current [pu inst]")
    figure.tight_layout()
    figure.savefig(png_path, dpi=200, bbox_inches="tight")

    if enable_plots:
        plt.show()
    else:
        plt.close(figure)


def _run_delta_case(builder: Callable, case_name: str, enable_plots: bool) -> Dict[str, object]:
    problem, load, pf_res_3ph = _build_problem(builder=builder, case_name=case_name)
    reference = _collect_delta_reference(problem=problem, load=load, pf_res_3ph=pf_res_3ph)
    output_dir = get_plot_results_directory("delta_loads_emt", "symbolic")
    png_path = output_dir / f"{case_name}.png"
    _plot_reference(reference=reference, title=case_name.replace("_", " ").title(), png_path=png_path, enable_plots=enable_plots)
    reference["png_path"] = str(png_path)
    return reference


def run_exponential_delta_case(enable_plots: bool = True) -> Dict[str, object]:
    return _run_delta_case(builder=get_exponential_load_emt, case_name="exponential_delta_load_emt", enable_plots=enable_plots)


def run_zip_delta_case(enable_plots: bool = True) -> Dict[str, object]:
    return _run_delta_case(builder=get_load_ZIP_emt_template, case_name="zip_delta_load_emt", enable_plots=enable_plots)


def run_delta_load_cases(enable_plots: bool = True) -> Dict[str, object]:
    return dict({
        "exponential": run_exponential_delta_case(enable_plots=enable_plots),
        "zip": run_zip_delta_case(enable_plots=enable_plots),
    })


if __name__ == "__main__":
    run_delta_load_cases(enable_plots=True)
