# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys
from typing import Dict, Tuple, cast

import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR: str = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT: str = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SRC_ROOT: str = os.path.join(REPO_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
else:
    sys.path = sys.path

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
else:
    sys.path = sys.path

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.converter_emt_template import get_pseudo_emt_converter
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    SolverType,
)

"""Minimal EMT example with Thevenin source, pseudo-EMT converter and DC R load."""

def build_grid() -> Tuple[gce.MultiCircuit, gce.Bus, gce.Bus, gce.Generator, gce.VSC, gce.Load]:
    """
    Build a minimal AC/DC network for the pseudo-EMT converter demo.

    The AC side is represented by a slack bus with a Thevenin-equivalent EMT
    generator. The converter connects this AC bus to a DC bus feeding a resistive
    DC load around a nominal operating point.

    :return:
        Tuple with the grid and the key devices used by the example.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(
        name="Grid - Thevenin + pseudo EMT converter + DC R load",
        Sbase=100.0,
        fbase=50.0,
    )

    bus_ac: gce.Bus = gce.Bus(name="Bus_AC", Vnom=230.0, is_slack=True)
    bus_dc: gce.Bus = gce.Bus(name="Bus_DC", Vnom=320.0, is_dc=True)
    grid.add_bus(bus_ac)
    grid.add_bus(bus_dc)

    generator: gce.Generator = gce.Generator(
        name="Gen_Thev",
        vset=1.0,
        Snom=grid.Sbase,
        freq=50.0,
        r1=0.001,
        x1=0.3,
    )
    grid.add_generator(bus_ac, generator)

    p_transfer_mw: float = 30.0
    q_transfer_mvar: float = 0.0
    converter: gce.VSC = gce.VSC(
        name="PseudoVSC",
        bus_from=bus_dc,
        bus_to=bus_ac,
        rate=grid.Sbase,
        control1=ConverterControlType.Qac,
        control2=ConverterControlType.Vm_dc,
        control1_val=q_transfer_mvar,
        control2_val=1.0,
    )
    grid.add_vsc(converter)

    dc_load: gce.Load = gce.Load(name="DC_R_Load", P=p_transfer_mw, Q=0.0)
    grid.add_load(bus_dc, dc_load)

    return grid, bus_ac, bus_dc, generator, converter, dc_load


def attach_emt_models(
    grid: gce.MultiCircuit,
    generator: gce.Generator,
    converter: gce.VSC,
    dc_load: gce.Load,
    pf_results: PowerFlowResults,
) -> Tuple[Block, Block, Block]:
    """
    Attach EMT models to the Thevenin source, converter and DC load.

    The converter uses the new pseudo-EMT grid-following template. The DC load is
    represented as a constant resistance around the requested active-power transfer.

    :param grid:
        Example grid.
    :param generator:
        Thevenin source API object.
    :param converter:
        VSC API object.
    :param dc_load:
        DC load API object.
    :param pf_results:
        Balanced power-flow results used to seed losses and EMT initialization.
    :return:
        Attached EMT blocks for generator, converter and DC load.
    """
    bus: gce.Bus
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    gen_mdl: Block = get_generator_thevenin_rl_emt_template(vf=grid.var_factory).block

    vsc_index: int = grid.get_vsc().index(converter)
    losses_vsc = getattr(pf_results, "losses_vsc", None)
    p_loss0: float = float(losses_vsc[vsc_index]) if losses_vsc is not None else 0.0

    vsc_mdl: Block = get_pseudo_emt_converter(
        vf=grid.var_factory,
        name=converter.name,
        sbase=grid.Sbase,
        fbase=grid.fBase,
        P_ref0=float(dc_load.P),
        Q_ref0=float(converter.control1_val),
        Vdc_ref0=1.0,
        R_eq=0.03,
        L_eq=0.12,
        C_dc=0.08,
        R_dc=1e6,
        R_dc_term=1e-4,
        pll_kp=40.0,
        pll_ki=400.0,
        i_kp=0.6,
        i_ki=50.0,
        vdc_kp=2.0,
        vdc_ki=30.0,
        q_kp=0.8,
        q_ki=20.0,
        i_max=1.3,
        m_max=0.95,
        P_loss0=p_loss0,
        P_loss_i1=0.01,
        P_loss_i2=0.01,
        tau_meas=0.01,
        aw_gain=1.0,
        vdc_floor=0.05,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_val=1.0,
        control2_val=0.0,
    ).block

    dc_load_r_pu: float = grid.Sbase / float(dc_load.P)
    dc_load_mdl: Block = get_dc_load_emt_template(
        grid=grid,
        P_dc=dc_load.P,
        R_dc=dc_load_r_pu,
        name="dc_r_load_emt",
    ).block

    set_emt_model(device=generator, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=converter, model=vsc_mdl, var_factory=grid.var_factory)
    set_emt_model(device=dc_load, model=dc_load_mdl, var_factory=grid.var_factory)

    return gen_mdl, vsc_mdl, dc_load_mdl


def build_power_flow_options() -> PowerFlowOptions:
    """
    Create the balanced power-flow options used to seed the EMT initialization.

    :return:
        Power-flow options.
    """
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=True,
        verbose=False,
        tolerance=1e-6,
        max_iter=100,
        control_q=True,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )


def run_power_flow(grid: gce.MultiCircuit) -> PowerFlowResults:
    """
    Run the balanced AC/DC power flow used for EMT initialization.

    :param grid:
        Example grid.
    :return:
        Balanced power-flow results.
    """
    return gce.power_flow(grid=grid, options=build_power_flow_options())


def build_problem(grid: gce.MultiCircuit, pf_results: PowerFlowResults) -> EmtProblemDae:
    """
    Build the EMT DAE problem for the pseudo-EMT converter demo.

    :param grid:
        Example grid.
    :param pf_results:
        Balanced power-flow results.
    :return:
        Configured EMT DAE problem.
    """
    options: EmtOptions = EmtOptions(
        time_step=2.0e-5,
        simulation_time=0.1,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        initialization_method=EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=1,
    )
    return EmtProblemDae(grid=grid, options=options, pf_results_3Ph=None, pf_results=pf_results)


def build_solver(problem: EmtProblemDae) -> StructuralCompiledSolver:
    """
    Build the compiled EMT solver backend.

    :param problem:
        EMT problem.
    :return:
        Configured solver.
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
    Extract one symbolic trajectory from the EMT solution matrix.

    :param problem:
        EMT problem with variable indexing.
    :param root_block:
        Root block where the variable will be searched.
    :param variable_name:
        Symbolic variable name.
    :param y:
        EMT variable trajectory matrix.
    :return:
        Selected trajectory.
    """
    variable: Var | None = find_name_in_block(variable_name, root_block)

    if variable is None:
        raise ValueError(f"Variable '{variable_name}' not found in block '{root_block.name}'.")
    else:
        return y[:, problem.get_var_idx(variable)]


def validate_initialization(problem: EmtProblemDae) -> None:
    """
    Print a compact initialization report.

    :param problem:
        EMT problem.
    :return:
        None.
    """
    x0: np.ndarray = problem.get_x0()
    dx0: np.ndarray = problem.get_dx0()

    print("EMT initialization report")
    print(f"  finite x0 : {bool(np.all(np.isfinite(x0)))}")
    print(f"  finite dx0: {bool(np.all(np.isfinite(dx0)))}")

    if problem.initialization_report is not None:
        report = problem.initialization_report
        print(f"  method    : {report.method_used.name}")
        print(f"  status    : {report.status.name}")
        print(f"  residual  : {report.final_residual_inf:.3e}")


def build_plot_data(
    problem: EmtProblemDae,
    bus_ac: gce.Bus,
    bus_dc: gce.Bus,
    gen_mdl: Block,
    vsc_mdl: Block,
    dc_load_mdl: Block,
    y: np.ndarray,
) -> Dict[str, np.ndarray]:
    """
    Collect the key trajectories that validate pseudo-EMT converter behaviour.

    :param problem:
        EMT problem.
    :param bus_ac:
        AC bus.
    :param bus_dc:
        DC bus.
    :param gen_mdl:
        Thevenin EMT model.
    :param vsc_mdl:
        Pseudo-EMT converter model.
    :param dc_load_mdl:
        DC resistive load model.
    :param y:
        EMT trajectory matrix.
    :return:
        Named trajectories for plotting.
    """
    data: Dict[str, np.ndarray] = dict()

    data["v_ac_a"] = get_signal(problem, bus_ac.emt_model, "v_A_Bus_AC_emt_template", y)
    data["v_ac_b"] = get_signal(problem, bus_ac.emt_model, "v_B_Bus_AC_emt_template", y)
    data["v_ac_c"] = get_signal(problem, bus_ac.emt_model, "v_C_Bus_AC_emt_template", y)
    data["v_dc_bus"] = get_signal(problem, bus_dc.emt_model, "v_DC_Bus_DC_emt_template", y)

    data["i_gen_a"] = get_signal(problem, gen_mdl, "i_A_emt_thevenin_eq_generator_template", y)
    data["i_conv_a"] = get_signal(problem, vsc_mdl, "i_A_PseudoVSC", y)
    data["i_conv_b"] = get_signal(problem, vsc_mdl, "i_B_PseudoVSC", y)
    data["i_conv_c"] = get_signal(problem, vsc_mdl, "i_C_PseudoVSC", y)
    data["i_dc_conv"] = get_signal(problem, vsc_mdl, "i_dc_PseudoVSC", y)
    data["i_dc_load"] = -get_signal(problem, dc_load_mdl, "i_dc_dc_r_load_emt", y)

    data["v_dc_internal"] = get_signal(problem, vsc_mdl, "v_dc_PseudoVSC", y)
    data["theta_pll"] = get_signal(problem, vsc_mdl, "theta_pll_PseudoVSC", y)
    data["i_d"] = get_signal(problem, vsc_mdl, "i_d_PseudoVSC", y)
    data["i_q"] = get_signal(problem, vsc_mdl, "i_q_PseudoVSC", y)
    data["P"] = get_signal(problem, vsc_mdl, "P_PseudoVSC", y)
    data["Q"] = get_signal(problem, vsc_mdl, "Q_PseudoVSC", y)

    return data


def plot_results(t: np.ndarray, data: Dict[str, np.ndarray]) -> None:
    """
    Plot the key trajectories of the pseudo-EMT converter demo.

    :param t:
        Time vector.
    :param data:
        Named trajectories.
    :return:
        None.
    """
    figure, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)

    axes[0].plot(t, data["v_ac_a"], label="Va")
    axes[0].plot(t, data["v_ac_b"], label="Vb")
    axes[0].plot(t, data["v_ac_c"], label="Vc")
    axes[0].set_ylabel("Voltage [pu]")
    axes[0].set_title("AC bus voltages at the converter PCC")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")

    axes[1].plot(t, data["i_conv_a"], label="i_conv_a")
    axes[1].plot(t, data["i_conv_b"], label="i_conv_b")
    axes[1].plot(t, data["i_conv_c"], label="i_conv_c")
    axes[1].plot(t, data["i_gen_a"], "--", label="i_gen_a")
    axes[1].set_ylabel("Current [pu]")
    axes[1].set_title("AC current injection of the pseudo-EMT converter")
    axes[1].grid(True)
    axes[1].legend(loc="upper right")

    axes[2].plot(t, data["v_dc_bus"], label="v_dc_bus")
    axes[2].plot(t, data["v_dc_internal"], "--", label="v_dc_internal")
    axes[2].plot(t, data["i_dc_conv"], label="i_dc_conv")
    axes[2].plot(t, data["i_dc_load"], ":", label="i_dc_load")
    axes[2].set_ylabel("DC quantities [pu]")
    axes[2].set_title("DC-link and DC terminal behaviour")
    axes[2].grid(True)
    axes[2].legend(loc="upper right")

    axes[3].plot(t, data["i_d"], label="i_d")
    axes[3].plot(t, data["i_q"], label="i_q")
    axes[3].plot(t, data["P"], label="P")
    axes[3].plot(t, data["Q"], label="Q")
    axes[3].plot(t, data["theta_pll"], label="theta_pll")
    axes[3].set_xlabel("Time [s]")
    axes[3].set_ylabel("dq / power / angle")
    axes[3].set_title("Internal pseudo-EMT converter states")
    axes[3].grid(True)
    axes[3].legend(loc="upper right")

    figure.tight_layout()
    plt.show()


def main() -> None:
    """
    Run the pseudo-EMT converter validation example.

    :return:
        None.
    """
    grid, bus_ac, bus_dc, generator, converter, dc_load = build_grid()
    pf_results: PowerFlowResults = run_power_flow(grid)

    print("Balanced power flow results")
    print(f"  converged: {pf_results.converged}")
    if not pf_results.converged:
        raise RuntimeError("Power flow did not converge for the pseudo-EMT converter example.")

    print(pf_results.get_bus_df())
    print(pf_results.get_branch_df())

    gen_mdl, vsc_mdl, dc_load_mdl = attach_emt_models(
        grid=grid,
        generator=generator,
        converter=converter,
        dc_load=dc_load,
        pf_results=pf_results,
    )

    problem: EmtProblemDae = build_problem(grid=grid, pf_results=pf_results)
    validate_initialization(problem)

    solver: StructuralCompiledSolver = build_solver(problem)
    t, y, _ = solver.simulate(boundary_updater=cast(object, problem))

    plot_data: Dict[str, np.ndarray] = build_plot_data(
        problem=problem,
        bus_ac=bus_ac,
        bus_dc=bus_dc,
        gen_mdl=gen_mdl,
        vsc_mdl=vsc_mdl,
        dc_load_mdl=dc_load_mdl,
        y=y,
    )
    plot_results(t=t, data=plot_data)


if __name__ == "__main__":
    main()
