# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Minimal EMT example with Thevenin source, pi line and exponential load."""

from __future__ import annotations

from typing import Dict, Tuple, cast

import matplotlib.pyplot as plt
import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_exponential_emt_template import get_exponential_load_emt
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, ShuntConnectionType


def build_grid() -> Tuple[gce.MultiCircuit, gce.Bus, gce.Bus, gce.Line, gce.Generator, gce.Load]:
    """
    Build the two-bus EMT example network.

    The load is configured as a grounded-star three-phase load. The actual EMT
    dynamics are attached later through the exponential EMT template.

    :return: Grid and key devices used by the example.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

    v_nom_kv: float = 10.0
    bus0: gce.Bus = gce.Bus(name="Bus0", Vnom=v_nom_kv, is_slack=True)
    bus1: gce.Bus = gce.Bus(name="Bus1", Vnom=v_nom_kv)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line0: gce.Line = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10.0, rate=900.0)

    tower: gce.OverheadLineType = gce.OverheadLineType(name="Tower", Vnom=v_nom_kv)
    wire: gce.Wire = gce.Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1.0,
    )
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line0.apply_template(tower, grid.Sbase, grid.fBase)

    r_phase_ohm: float = 100.0
    v_phase_kv_rms: float = v_nom_kv / np.sqrt(3.0)
    p_phase_mw: float = (v_phase_kv_rms * v_phase_kv_rms) / r_phase_ohm
    q_phase_mvar: float = 0.0

    load: gce.Load = gce.Load(
        name="load",
        P1=p_phase_mw,
        P2=p_phase_mw,
        P3=p_phase_mw,
        Q1=q_phase_mvar,
        Q2=q_phase_mvar,
        Q3=q_phase_mvar,
    )
    load.conn = ShuntConnectionType.GroundedStar

    generator: gce.Generator = gce.Generator(
        name="Gen0",
        vset=1.0,
        Snom=grid.Sbase,
        freq=50.0,
        r1=0.001,
        x1=1.7,
    )

    grid.add_line(line0)
    grid.add_generator(bus=bus0, api_obj=generator)
    grid.add_load(bus=bus1, api_obj=load)

    return grid, bus0, bus1, line0, generator, load


def attach_emt_models(
    grid: gce.MultiCircuit,
    line0: gce.Line,
    generator: gce.Generator,
    load: gce.Load,
) -> Tuple[Block, Block, Block]:
    """
    Attach EMT device models to the network.

    The exponential load is configured as a voltage-squared active-power law so
    the example stays physically close to the original resistive benchmark.

    :param grid: Example grid.
    :param line0: Network line.
    :param generator: Thevenin source.
    :param load: Static load API object.
    :return: Attached generator, line and load EMT blocks.
    """
    bus: gce.Bus
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    gen_mdl: Block = get_generator_thevenin_rl_emt_template(vf=grid.var_factory).block
    line_mdl = get_pi_line_emt_template(vf = grid.var_factory, phN = False, phA = True, phB = True, phC = True, name = "Pi").block
    load_mdl: Block = get_exponential_load_emt(vf=grid.var_factory, phA=True, phB=True, phC=True).block

    # ``a = 2`` reproduces an impedance-like active-power dependence. This keeps the
    # example aligned with the original resistive load while exercising the new EMT
    # exponential-load initialization chain.
    load_mdl.set_parameter_in_model(var_name="a_EXP_Load_EMT_3ph", new_value=2.0)
    load_mdl.set_parameter_in_model(var_name="b_EXP_Load_EMT_3ph", new_value=2.0)
    load_mdl.set_parameter_in_model(var_name="V0_EXP_Load_EMT_3ph", new_value=float(np.sqrt(2.0)))

    set_emt_model(device=generator, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line0, model=line_mdl, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    return gen_mdl, line_mdl, load_mdl


def build_power_flow_options() -> PowerFlowOptions:
    """
    Create the power-flow options used to seed the EMT initialization.

    :return: Power-flow options.
    """
    return PowerFlowOptions(
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


def run_power_flow(grid: gce.MultiCircuit) -> PowerFlowResults3Ph:
    """
    Run the balanced power flow used by the EMT explicit initializer.

    The EMT problem reconstructs the abc steady-state point from this phasor
    solution and then fills the exponential-load runtime parameters and seeds.

    :param grid: Example grid.
    :return: Power-flow results object.
    """
    driver: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, build_power_flow_options())
    driver.run()
    return driver.results


def build_problem(grid: gce.MultiCircuit, pf_results: PowerFlowResults3Ph) -> EmtProblemDae:
    """
    Build the EMT DAE problem using explicit initialization.

    Explicit initialization is used on purpose so the example validates that the
    exponential load template now provides a complete state, algebraic and
    differential initialization chain by itself.

    :param grid: Example grid.
    :param pf_results: Balanced power-flow results.
    :return: EMT DAE problem.
    """
    options: EmtOptions = EmtOptions(
        time_step=2.0e-5,
        simulation_time=0.04,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=1,
    )
    return EmtProblemDae(grid=grid, options=options, pf_results_3ph=pf_results, pf_results=None)


def build_solver(problem: EmtProblemDae) -> StructuralCompiledSolver:
    """
    Build the EMT solver backend.

    :param problem: EMT problem.
    :return: Configured compiled solver.
    """
    solver: StructuralCompiledSolver = StructuralCompiledSolver(
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
        auto_build=False,
    )
    solver._build_vectorized_backend(problem.options.integration_method)
    return solver


def get_signal(problem: EmtProblemDae, root_block: Block, variable_name: str, y: np.ndarray) -> np.ndarray:
    """
    Extract one EMT variable trajectory from the simulation output.

    :param problem: EMT problem containing the variable indices.
    :param root_block: Block tree where the variable is searched.
    :param variable_name: Symbolic variable name.
    :param y: Simulated EMT variable matrix.
    :return: One trajectory column.
    """
    variable: Var | None = find_name_in_block(variable_name, root_block)

    if variable is None:
        raise ValueError(f"Variable '{variable_name}' was not found in block '{root_block.name}'.")
    else:
        return y[:, problem.get_var_idx(variable)]


def validate_initialization(problem: EmtProblemDae) -> None:
    """
    Print a compact initialization validation report.

    This report matters because the example intentionally uses the explicit
    initialization path. Any missing algebraic or differential seed would show up
    here before the dynamic simulation starts.

    :param problem: EMT problem.
    :return: None.
    """
    x0: np.ndarray = problem.get_x0()
    dx0: np.ndarray = problem.get_dx0()
    report = problem.initialization_report

    print("Balanced EMT initialization report")
    print(f"  finite x0 : {bool(np.all(np.isfinite(x0)))}")
    print(f"  finite dx0: {bool(np.all(np.isfinite(dx0)))}")

    if report is not None:
        print(f"  method    : {report.method_used.name}")
        print(f"  status    : {report.status.name}")
        print(f"  residual  : {report.final_residual_inf:.3e}")
    else:
        print("  method    : unavailable")


def build_plot_data(
    problem: EmtProblemDae,
    bus0: gce.Bus,
    bus1: gce.Bus,
    line_mdl: Block,
    gen_mdl: Block,
    load_mdl: Block,
    y: np.ndarray,
) -> Dict[str, np.ndarray]:
    """
    Collect the trajectories plotted by the example.

    The chosen signals show the physically important relationships: sending-end
    voltage, receiving-end voltage, source current, line current and load current.

    :param problem: EMT problem.
    :param bus0: Source bus.
    :param bus1: Load bus.
    :param line_mdl: Pi-line model.
    :param gen_mdl: Thevenin model.
    :param load_mdl: Exponential load model.
    :param y: EMT state trajectory.
    :return: Named trajectories for plotting.
    """
    data: Dict[str, np.ndarray] = dict()

    data["v_bus0_a"] = get_signal(problem, bus0.emt_model, "v_A_Bus0_emt_template", y)
    data["v_bus0_b"] = get_signal(problem, bus0.emt_model, "v_B_Bus0_emt_template", y)
    data["v_bus0_c"] = get_signal(problem, bus0.emt_model, "v_C_Bus0_emt_template", y)
    data["v_bus1_a"] = get_signal(problem, bus1.emt_model, "v_A_Bus1_emt_template", y)
    data["v_bus1_b"] = get_signal(problem, bus1.emt_model, "v_B_Bus1_emt_template", y)
    data["v_bus1_c"] = get_signal(problem, bus1.emt_model, "v_C_Bus1_emt_template", y)

    data["i_gen_a"] = get_signal(problem, gen_mdl, "i_A_emt_thevenin_eq_generator_template", y)
    data["i_line_f_a"] = get_signal(problem, line_mdl, "if_Pi_A", y)
    data["i_line_t_a"] = get_signal(problem, line_mdl, "it_Pi_A", y)
    data["i_load_a"] = -get_signal(problem, load_mdl, "i_A_EXP_Load_EMT_3ph", y)

    data["p_load_a"] = get_signal(problem, load_mdl, "P_A_EXP_Load_EMT_3ph", y)
    data["q_load_a"] = get_signal(problem, load_mdl, "Q_A_EXP_Load_EMT_3ph", y)

    return data


def plot_results(t: np.ndarray, data: Dict[str, np.ndarray]) -> None:
    """
    Plot the physically relevant EMT trajectories.

    The first subplot verifies balanced sinusoidal voltages and the expected line
    drop. The second one verifies current continuity. The last one confirms that
    the exponential load behaves as a consuming device with nearly constant active
    power in this impedance-like operating point.

    :param t: Time vector.
    :param data: Named trajectories.
    :return: None.
    """
    figure, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    axes[0].plot(t, data["v_bus0_a"], label="Bus0 Va")
    axes[0].plot(t, data["v_bus0_b"], label="Bus0 Vb")
    axes[0].plot(t, data["v_bus0_c"], label="Bus0 Vc")
    axes[0].plot(t, data["v_bus1_a"], "--", label="Bus1 Va")
    axes[0].plot(t, data["v_bus1_b"], "--", label="Bus1 Vb")
    axes[0].plot(t, data["v_bus1_c"], "--", label="Bus1 Vc")
    axes[0].set_ylabel("Voltage [pu peak]")
    axes[0].set_title("Balanced bus voltages and pi-line voltage drop")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")

    axes[1].plot(t, data["i_gen_a"], label="Generator ia")
    axes[1].plot(t, data["i_line_f_a"], "--", label="Line if,a")
    axes[1].plot(t, -data["i_line_t_a"], ":", label="-Line it,a")
    axes[1].plot(t, data["i_load_a"], label="Load ia demand")
    axes[1].set_ylabel("Current [pu peak]")
    axes[1].set_title("Phase-A current consistency from source to load")
    axes[1].grid(True)
    axes[1].legend(loc="upper right")

    axes[2].plot(t, data["p_load_a"], label="Load P_A injection")
    axes[2].plot(t, data["q_load_a"], label="Load Q_A injection")
    axes[2].set_xlabel("Time [s]")
    axes[2].set_ylabel("Power [pu]")
    axes[2].set_title("Exponential load phase-A injected powers")
    axes[2].grid(True)
    axes[2].legend(loc="upper right")

    figure.tight_layout()
    plt.show()


def main() -> None:
    """
    Run the EMT example.

    :return: None.
    """
    grid, bus0, bus1, line0, generator, load = build_grid()
    gen_mdl, line_mdl, load_mdl = attach_emt_models(grid=grid, line0=line0, generator=generator, load=load)

    pf_results: PowerFlowResults3Ph = run_power_flow(grid)
    problem: EmtProblemDae = build_problem(grid=grid, pf_results=pf_results)
    validate_initialization(problem)

    solver: StructuralCompiledSolver = build_solver(problem)
    t, y, _, well_initialized , converged = solver.simulate(boundary_updater=cast(object, problem))
    print(f"well_initialized = {well_initialized}")
    print(f"converged = {converged}")

    plot_data: Dict[str, np.ndarray] = build_plot_data(
        problem=problem,
        bus0=bus0,
        bus1=bus1,
        line_mdl=line_mdl,
        gen_mdl=gen_mdl,
        load_mdl=load_mdl,
        y=y,
    )
    plot_results(t=t, data=plot_data)


if __name__ == "__main__":
    main()
