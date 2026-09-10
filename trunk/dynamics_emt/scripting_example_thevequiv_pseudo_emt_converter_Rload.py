# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys
from typing import Dict, Tuple

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
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.converter_emt_template import get_full_pseudo_emt_converter
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_balanced_3ph_voltage_source_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
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

    The AC side uses a slack/source bus and a separate converter PCC connected
    through a small transformer. This avoids the degenerate case where the
    converter sits directly on the slack bus and the PF reports zero AC-side
    converter power even though the DC side is loaded.

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
        x1=0.04,
    )
    grid.add_generator(bus_ac, generator)

    p_transfer_mw: float = 30.0
    q_transfer_mvar: float = 0.0
    converter: gce.VSC = gce.VSC(
        name="pseudo_converter_emt",
        bus_from=bus_dc,
        bus_to=bus_ac,
        rate=grid.Sbase,
        # For this VSC orientation (`bus_from=DC`, `bus_to=AC`), negative `Pdc`
        # means the converter imports power from the AC side into the DC bus.
        # That is the consistent PF operating point for feeding the positive DC
        # load below.
        control1=ConverterControlType.Pdc,
        control2=ConverterControlType.Qac,
        control1_val=-p_transfer_mw,
        control2_val=q_transfer_mvar,
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
        Attached EMT blocks for generator, transformer, converter and DC load.
    """
    bus: gce.Bus
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    # Use a stiff Norton sinusoidal source for the converter-only baseline.  A
    # dynamic Thevenin branch introduces its own PF-to-EMT current handover and
    # would make a source transient indistinguishable from converter init error.
    gen_mdl: Block = get_balanced_3ph_voltage_source_emt_template(
        vf=grid.var_factory,
        amplitude_value=np.sqrt(2.0),
        frequency_hz=grid.fBase,
        phase_a_deg=0.0,
        source_conductance_value=1000.0,
        name="stiff_balanced_ac_source",
    ).block

    # Preserve the solved DC-power transfer for the pre-handover equilibrium.
    # Vm_dc control is introduced only after this pseudo baseline is stationary.
    converter.control1 = ConverterControlType.Pdc
    converter.control2 = ConverterControlType.Qac
    converter.control1_val = float(dc_load.P)
    converter.control2_val = 0.0

    vsc_mdl: Block = get_full_pseudo_emt_converter(
        vf=grid.var_factory,
    ).block

    # Parameter names inside the assembled hierarchy are the plain symbolic
    # names below; the old device-suffixed names matched nothing and silently
    # left all template defaults active.
    vsc_mdl.set_parameter_in_model(var_name="R_eq", new_value=0.03)
    vsc_mdl.set_parameter_in_model(var_name="L_eq", new_value=0.12)
    vsc_mdl.set_parameter_in_model(var_name="C_dc", new_value=0.08)
    vsc_mdl.set_parameter_in_model(var_name="R_dc", new_value=1e6)
    vsc_mdl.set_parameter_in_model(var_name="R_dc_term", new_value=0.0001)
    vsc_mdl.set_parameter_in_model(var_name="pll_kp", new_value=40.0)
    vsc_mdl.set_parameter_in_model(var_name="pll_ki", new_value=400.0)
    vsc_mdl.set_parameter_in_model(var_name="i_kp", new_value=0.6)
    vsc_mdl.set_parameter_in_model(var_name="i_ki", new_value=50.0)
    vsc_mdl.set_parameter_in_model(var_name="vdc_kp", new_value=2.0)
    vsc_mdl.set_parameter_in_model(var_name="vdc_ki", new_value=30.0)
    vsc_mdl.set_parameter_in_model(var_name="q_kp", new_value=0.8)
    vsc_mdl.set_parameter_in_model(var_name="q_ki", new_value=20.0)
    vsc_mdl.set_parameter_in_model(var_name="i_max", new_value=1.3)
    vsc_mdl.set_parameter_in_model(var_name="m_max", new_value=0.95)
    vsc_mdl.set_parameter_in_model(var_name="tau_meas", new_value=0.01)
    vsc_mdl.set_parameter_in_model(var_name="aw_gain", new_value=0.1)
    vsc_mdl.set_parameter_in_model(var_name="vdc_floor", new_value=0.05)

    dc_load_mdl: Block = get_dc_load_emt_template(
        vf=grid.var_factory,
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
        solver_type=SolverType.LM,
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
        simulation_time=0.15,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        verbose=0,
    )
    return EmtProblemDae(grid=grid, options=options, pf_results_3ph=None, pf_results=pf_results)


def build_solver(problem: EmtProblemDae) -> JitSymbolicSolver:
    """
    Build the EMT solver backend.

    :param problem:
        EMT problem.
    :return:
        Configured solver.
    """
    return JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )


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

    data["v_ac_a"] = get_signal(problem, bus_ac.emt_model, "v_A", y)
    data["v_ac_b"] = get_signal(problem, bus_ac.emt_model, "v_B", y)
    data["v_ac_c"] = get_signal(problem, bus_ac.emt_model, "v_C", y)
    data["v_dc_bus"] = get_signal(problem, bus_dc.emt_model, "v_DC", y)

    data["i_gen_a"] = get_signal(problem, gen_mdl, "i_A", y)
    data["i_conv_a"] = get_signal(problem, vsc_mdl, "i_A", y)
    data["i_conv_b"] = get_signal(problem, vsc_mdl, "i_B", y)
    data["i_conv_c"] = get_signal(problem, vsc_mdl, "i_C", y)
    data["i_dc_conv"] = get_signal(problem, vsc_mdl, "i_dc", y)
    data["i_dc_load"] = -get_signal(problem, dc_load_mdl, "i_dc", y)

    data["v_dc_internal"] = get_signal(problem, vsc_mdl, "v_dc", y)
    data["theta_pll"] = get_signal(problem, vsc_mdl, "theta_pll", y)
    data["i_d"] = get_signal(problem, vsc_mdl, "i_d", y)
    data["i_q"] = get_signal(problem, vsc_mdl, "i_q", y)
    data["P"] = get_signal(problem, vsc_mdl, "P", y)
    data["Q"] = get_signal(problem, vsc_mdl, "Q", y)

    return data


def plot_results(t: np.ndarray, data: Dict[str, np.ndarray]) -> str:
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
    output_dir: str = os.path.join(SCRIPT_DIR, "plot_results", "pseudo_converter")
    os.makedirs(output_dir, exist_ok=True)
    output_path: str = os.path.join(output_dir, "pseudo_converter_initialization.png")
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    print(f"Saved plot: {output_path}")
    return output_path


def validate_steady_baseline(t: np.ndarray, data: Dict[str, np.ndarray]) -> None:
    """Reject phase imbalance, reactive drift, or DC drift in the last cycle."""
    cycle_start: float = float(t[-1] - 1.0 / 50.0)
    tail: np.ndarray = t >= cycle_start
    phase_sum: np.ndarray = data["v_ac_a"] + data["v_ac_b"] + data["v_ac_c"]
    voltage_rms: np.ndarray = np.asarray([
        np.sqrt(np.mean(data[phase][tail] ** 2))
        for phase in ("v_ac_a", "v_ac_b", "v_ac_c")
    ])
    dc_drift: float = float(data["v_dc_internal"][-1] - data["v_dc_internal"][tail][0])
    q_peak: float = float(np.max(np.abs(data["Q"][tail])))

    print("Pseudo-EMT steady-baseline checks")
    print(f"  phase-sum max       : {np.max(np.abs(phase_sum[tail])):.3e} pu")
    print(f"  phase RMS spread    : {np.ptp(voltage_rms):.3e} pu")
    print(f"  last-cycle DC drift : {dc_drift:.3e} pu")
    print(f"  last-cycle |Q| peak : {q_peak:.3e} pu")

    if np.max(np.abs(phase_sum[tail])) > 1.0e-8:
        raise RuntimeError("Pseudo-EMT phase voltages are not balanced.")
    if np.ptp(voltage_rms) > 2.0e-3:
        raise RuntimeError("Pseudo-EMT phase RMS magnitudes do not match.")
    if abs(dc_drift) > 2.0e-4:
        raise RuntimeError("Pseudo-EMT DC link is not stationary over the last cycle.")
    if q_peak > 2.0e-3:
        raise RuntimeError("Pseudo-EMT reactive-power initialization is not stationary.")


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

    # solver: StructuralCompiledSolver = build_solver(problem)
    solver: JitSymbolicSolver = build_solver(problem)
    # t, y, _, well_initialized , converged  = solver.simulate(boundary_updater=cast(object, problem))
    t, y, _, well_initialized, converged = solver.simulate()
    print(f"well_initialized = {well_initialized}")
    print(f"converged = {converged}")
    if not well_initialized or not converged:
        raise RuntimeError("Pseudo-EMT baseline did not initialize and integrate cleanly.")

    plot_data: Dict[str, np.ndarray] = build_plot_data(
        problem=problem,
        bus_ac=bus_ac,
        bus_dc=bus_dc,
        gen_mdl=gen_mdl,
        vsc_mdl=vsc_mdl,
        dc_load_mdl=dc_load_mdl,
        y=y,
    )
    validate_steady_baseline(t=t, data=plot_data)
    plot_results(t=t, data=plot_data)


if __name__ == "__main__":
    main()
