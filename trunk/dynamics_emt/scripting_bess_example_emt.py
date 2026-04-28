# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple

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
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Templates.Emt.bess_avm_emt_template import (
    get_bess_avm_grid_following_emt_template,
)
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import (
    get_generator_thevenin_rl_emt_template,
)
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_transformer_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    BranchImpedanceMode,
    SolverType,
)

"""
Level-1 BESS averaged-value EMT example.

The power-flow case is deliberately built as a clean AC-only equivalent:

    slack Thevenin bus -> unity transformer -> BESS PCC bus

The BESS is represented in the balanced power flow by a temporary PQ load at
the PCC. A negative load represents discharge, while a positive load represents
charge. The EMT model attached to that same API object then replaces the static
PQ approximation by the full averaged BESS model:

    internal battery + imported pseudo-EMT VSC/PLL/control/interface blocks.

This avoids the previous degenerate AC/DC power-flow setup with a floating DC
bus. The BESS is an AC injection device with an internal DC side, so no
external DC bus is needed for this example.
"""


@dataclass(frozen=True)
class BessCase:
    """
    Container for one BESS EMT simulation case.

    :param name: Human-readable case name.
    :param active_power_mw: EMT active-power reference. Positive means intended
        battery discharge, negative means intended battery charge.
    :param reactive_power_mvar: EMT reactive-power reference.
    :param initial_soc: Initial battery state of charge in pu.
    """

    name: str
    active_power_mw: float
    reactive_power_mvar: float
    initial_soc: float


@dataclass(frozen=True)
class BessRunObjects:
    """
    Key objects created for one EMT case.

    :param grid: VeraGrid circuit.
    :param bus_grid: Slack/source AC bus.
    :param bus_bess: AC PCC where the BESS is connected.
    :param generator: Thevenin source generator.
    :param transformer: Unity-ratio AC transformer between source and BESS PCC.
    :param bess_equivalent: Static PQ carrier used for PF and for attaching the
        complete BESS EMT model.
    """

    grid: gce.MultiCircuit
    bus_grid: gce.Bus
    bus_bess: gce.Bus
    generator: gce.Generator
    transformer: gce.Transformer2W
    bess_equivalent: gce.Load


@dataclass(frozen=True)
class BessEmtBlocks:
    """
    EMT blocks attached to the key static devices.

    :param gen_mdl: Thevenin source EMT block.
    :param transformer_mdl: EMT transformer block.
    :param bess_mdl: Complete BESS EMT block.
    """

    gen_mdl: Block
    transformer_mdl: Block
    bess_mdl: Block


CASES: List[BessCase] = [
    BessCase(name="discharge", active_power_mw=5.0, reactive_power_mvar=0.0, initial_soc=0.70),
    BessCase(name="charge", active_power_mw=-5.0, reactive_power_mvar=0.0, initial_soc=0.30),
]


def _converter_control_type_code(control: ConverterControlType) -> float:
    """
    Return the numeric code used internally by the imported converter template.

    The BESS is attached to a load-like API object in this example so the normal
    VSC api-object mapping is not used for these parameters. We therefore set
    the exposed event parameters explicitly with the same codes used by
    ``converter_emt_template.py``.

    :param control: Converter control enum.
    :return: Numeric control code.
    :raises ValueError: If the control is not supported in this example.
    """
    if control == ConverterControlType.Qac:
        return 4.0
    if control == ConverterControlType.Pac:
        return 6.0

    raise ValueError(f"Unsupported BESS example control mode: {control}")


def build_grid(case: BessCase) -> BessRunObjects:
    """
    Build a PF-friendly AC equivalent grid that hosts the BESS EMT model.

    The static balanced power flow sees the BESS as a PQ equivalent at the PCC.
    This produces a non-degenerate operating point and meaningful branch flow for
    EMT initialization. The detailed BESS dynamics are only introduced when the
    EMT model is attached to ``bess_equivalent``.

    :param case: Simulation case definition.
    :return: Grid and key static devices.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(
        name=f"Grid - AC Thevenin + Level-1 AVM BESS EMT - {case.name}",
        Sbase=100.0,
        fbase=50.0,
    )

    bus_grid: gce.Bus = gce.Bus(name=f"Bus_GRID_{case.name}", Vnom=230.0, is_slack=True)
    bus_bess: gce.Bus = gce.Bus(name=f"Bus_BESS_{case.name}", Vnom=230.0)
    grid.add_bus(bus_grid)
    grid.add_bus(bus_bess)

    generator: gce.Generator = gce.Generator(
        name=f"Gen_Thev_{case.name}",
        vset=1.0,
        Snom=grid.Sbase,
        freq=50.0,
        r1=0.001,
        x1=0.04,
    )
    grid.add_generator(bus_grid, generator)

    # Keep a separate PCC bus so the balanced PF remains well-posed, while the
    # source non-ideality comes from the generator Thevenin impedance rather
    # than from an explicit PI line. The transformer is kept at unity ratio.
    transformer: gce.Transformer2W = gce.Transformer2W(
        bus_from=bus_grid,
        bus_to=bus_bess,
        name=f"Transformer_GRID_BESS_{case.name}",
        rate=grid.Sbase,
        r=1.0e-5,
        x=1.0e-5,
        tap_module=1.0,
        tap_phase=0.0,
    )
    grid.add_transformer2w(transformer)

    # Load sign convention: positive P consumes power. Therefore discharge is
    # represented by a negative load and charge by a positive load.
    pf_load_p_mw: float = -case.active_power_mw
    pf_load_q_mvar: float = -case.reactive_power_mvar
    bess_equivalent: gce.Load = gce.Load(
        name=f"BESS_PF_equivalent_{case.name}",
        P=pf_load_p_mw,
        Q=pf_load_q_mvar,
    )
    grid.add_load(bus_bess, bess_equivalent)

    return BessRunObjects(
        grid=grid,
        bus_grid=bus_grid,
        bus_bess=bus_bess,
        generator=generator,
        transformer=transformer,
        bess_equivalent=bess_equivalent,
    )


def build_power_flow_options() -> PowerFlowOptions:
    """
    Create robust balanced power-flow options for the simple AC equivalent.

    :return: Power-flow options.
    """
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=False,
        tolerance=1e-8,
        max_iter=50,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )


def run_power_flow(grid: gce.MultiCircuit) -> PowerFlowResults:
    """
    Run the balanced power flow used by the EMT initializer.

    :param grid: VeraGrid circuit.
    :return: Power-flow results.
    """
    return gce.power_flow(grid=grid, options=build_power_flow_options())


def build_power_flow_options_3ph() -> PowerFlowOptions:
    """
    Create the 3-phase PF options used to seed branch EMT initialization.

    Existing branch-based EMT examples in this repository use a 3-phase PF
    result. This example follows the same initialization path so the BESS EMT
    block receives a consistent per-phase operating point at its PCC bus.

    :return: 3-phase power-flow options.
    """
    return PowerFlowOptions(
        solver_type=SolverType.NR,
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


def run_power_flow_3ph(grid: gce.MultiCircuit) -> PowerFlowResults3Ph:
    """
    Run the 3-phase power flow used by the PI-line EMT initializer.

    :param grid: VeraGrid circuit.
    :return: 3-phase power-flow results.
    """
    power_flow_3ph: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, build_power_flow_options_3ph())
    power_flow_3ph.run()
    return power_flow_3ph.results


def attach_emt_models(objects: BessRunObjects, case: BessCase) -> BessEmtBlocks:
    """
    Attach bus, transformer, Thevenin source and complete BESS EMT models.

    :param objects: Grid and static device objects.
    :param case: Simulation case definition.
    :return: EMT blocks attached to source, transformer and BESS carrier.
    """
    emt_active_power_mw: float = case.active_power_mw

    vdc_nominal_pu: float = 0.85 + (1.15 - 0.85) * case.initial_soc

    bus: gce.Bus
    for bus in objects.grid.buses:
        get_bus_emt_template(objects.grid, bus)

    gen_mdl: Block = get_generator_thevenin_rl_emt_template(
        vf=objects.grid.var_factory,
        name=f"gen_thev_{case.name}",
    ).block

    transformer_mdl: Block = get_transformer_emt_template(
        vf=objects.grid.var_factory,
        name=f"transformer_grid_bess_{case.name}",
    ).block

    bess_mdl: Block = get_bess_avm_grid_following_emt_template(
        vf=objects.grid.var_factory,
        name=f"bess_avm_{case.name}",
    ).block

    # Converter/VSC side parameters.
    bess_mdl.set_parameter_in_model(var_name=f"sbase_bess_avm_{case.name}", new_value=objects.grid.Sbase)
    bess_mdl.set_parameter_in_model(var_name=f"control1_bess_avm_{case.name}", new_value=_converter_control_type_code(ConverterControlType.Pac))
    bess_mdl.set_parameter_in_model(var_name=f"control2_bess_avm_{case.name}", new_value=_converter_control_type_code(ConverterControlType.Qac))
    bess_mdl.set_parameter_in_model(var_name=f"control1_val_bess_avm_{case.name}", new_value=emt_active_power_mw)
    bess_mdl.set_parameter_in_model(var_name=f"control2_val_bess_avm_{case.name}", new_value=case.reactive_power_mvar)
    bess_mdl.set_parameter_in_model(var_name=f"P0_bess_avm_{case.name}", new_value=emt_active_power_mw)
    bess_mdl.set_parameter_in_model(var_name=f"Vdc_nom_bess_avm_{case.name}", new_value=vdc_nominal_pu)

    bess_mdl.set_parameter_in_model(var_name=f"R_eq_bess_avm_{case.name}", new_value=0.05)
    bess_mdl.set_parameter_in_model(var_name=f"L_eq_bess_avm_{case.name}", new_value=0.20)
    bess_mdl.set_parameter_in_model(var_name=f"C_dc_bess_avm_{case.name}", new_value=0.20)
    bess_mdl.set_parameter_in_model(var_name=f"R_dc_bess_avm_{case.name}", new_value=1e6)
    bess_mdl.set_parameter_in_model(var_name=f"R_dc_term_bess_avm_{case.name}", new_value=0.0001)
    bess_mdl.set_parameter_in_model(var_name=f"pll_kp_bess_avm_{case.name}", new_value=10.0)
    bess_mdl.set_parameter_in_model(var_name=f"pll_ki_bess_avm_{case.name}", new_value=100.0)
    bess_mdl.set_parameter_in_model(var_name=f"i_kp_bess_avm_{case.name}", new_value=0.3)
    bess_mdl.set_parameter_in_model(var_name=f"i_ki_bess_avm_{case.name}", new_value=20.0)
    bess_mdl.set_parameter_in_model(var_name=f"vdc_kp_bess_avm_{case.name}", new_value=2.0)
    bess_mdl.set_parameter_in_model(var_name=f"vdc_ki_bess_avm_{case.name}", new_value=40.0)
    bess_mdl.set_parameter_in_model(var_name=f"q_kp_bess_avm_{case.name}", new_value=0.6)
    bess_mdl.set_parameter_in_model(var_name=f"q_ki_bess_avm_{case.name}", new_value=20.0)
    bess_mdl.set_parameter_in_model(var_name=f"i_max_bess_avm_{case.name}", new_value=1.3)
    bess_mdl.set_parameter_in_model(var_name=f"m_max_bess_avm_{case.name}", new_value=0.95)
    bess_mdl.set_parameter_in_model(var_name=f"P_loss_i1_bess_avm_{case.name}", new_value=0.01)
    bess_mdl.set_parameter_in_model(var_name=f"P_loss_i2_bess_avm_{case.name}", new_value=0.01)
    bess_mdl.set_parameter_in_model(var_name=f"tau_meas_bess_avm_{case.name}", new_value=0.01)
    bess_mdl.set_parameter_in_model(var_name=f"aw_gain_bess_avm_{case.name}", new_value=0.1)
    bess_mdl.set_parameter_in_model(var_name=f"vdc_floor_bess_avm_{case.name}", new_value=0.05)

    # Battery-side parameters.
    bess_mdl.set_parameter_in_model(var_name=f"e_cap_bat_bess_avm_{case.name}", new_value=8.0)
    bess_mdl.set_parameter_in_model(var_name=f"v_min_bat_bess_avm_{case.name}", new_value=0.85)
    bess_mdl.set_parameter_in_model(var_name=f"v_max_bat_bess_avm_{case.name}", new_value=1.15)
    bess_mdl.set_parameter_in_model(var_name=f"r_bat_bess_avm_{case.name}", new_value=0.02)
    bess_mdl.set_parameter_in_model(var_name=f"eta_ch_bat_bess_avm_{case.name}", new_value=0.96)
    bess_mdl.set_parameter_in_model(var_name=f"eta_dis_bat_bess_avm_{case.name}", new_value=0.96)
    bess_mdl.set_parameter_in_model(var_name=f"soc_min_bat_bess_avm_{case.name}", new_value=0.05)
    bess_mdl.set_parameter_in_model(var_name=f"soc_max_bat_bess_avm_{case.name}", new_value=0.95)
    bess_mdl.set_parameter_in_model(var_name=f"soc0_bat_bess_avm_{case.name}", new_value=case.initial_soc)

    set_emt_model(device=objects.generator, model=gen_mdl, var_factory=objects.grid.var_factory)
    set_emt_model(device=objects.transformer, model=transformer_mdl, var_factory=objects.grid.var_factory)
    set_emt_model(device=objects.bess_equivalent, model=bess_mdl, var_factory=objects.grid.var_factory)

    return BessEmtBlocks(gen_mdl=gen_mdl, transformer_mdl=transformer_mdl, bess_mdl=bess_mdl)


def build_problem(
    grid: gce.MultiCircuit,
    pf_results: PowerFlowResults,
    pf_results_3ph: PowerFlowResults3Ph,
) -> EmtProblemDae:
    """
    Build the EMT DAE problem.

    :param grid: VeraGrid circuit.
    :param pf_results: Balanced power-flow results.
    :param pf_results_3ph: 3-phase power-flow results.
    :return: EMT DAE problem.
    """
    options: EmtOptions = EmtOptions(
        time_step=2.0e-5,
        simulation_time=0.5,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=1,
    )
    return EmtProblemDae(grid=grid, options=options, pf_results_3ph=pf_results_3ph, pf_results=pf_results)


def build_solver(problem: EmtProblemDae) -> StructuralCompiledSolver:
    """
    Build the structural compiled EMT solver.

    :param problem: EMT DAE problem.
    :return: Configured solver.
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


def get_signal(problem: EmtProblemDae, root_block: Block, variable_name: str, y_values: np.ndarray) -> np.ndarray:
    """
    Extract one symbolic trajectory from the EMT solution matrix.

    :param problem: EMT problem with variable indexing.
    :param root_block: Block where the variable will be searched.
    :param variable_name: Symbolic variable name.
    :param y_values: EMT trajectory matrix.
    :return: Selected trajectory.
    :raises ValueError: If the variable cannot be found.
    """
    variable: Var | None = find_name_in_block(variable_name, root_block)

    if variable is None:
        raise ValueError(f"Variable '{variable_name}' not found in block '{root_block.name}'.")
    else:
        return y_values[:, problem.get_var_idx(variable)]


def get_optional_signal(
    problem: EmtProblemDae,
    root_block: Block,
    variable_name: str,
    y_values: np.ndarray,
) -> np.ndarray | None:
    """
    Extract one symbolic trajectory if it exists.

    This helper keeps the plotting code robust while the BESS template evolves.

    :param problem: EMT problem with variable indexing.
    :param root_block: Block where the variable will be searched.
    :param variable_name: Symbolic variable name.
    :param y_values: EMT trajectory matrix.
    :return: Selected trajectory or None.
    """
    variable: Var | None = find_name_in_block(variable_name, root_block)

    if variable is None:
        return None
    else:
        return y_values[:, problem.get_var_idx(variable)]


def validate_initialization(problem: EmtProblemDae) -> None:
    """
    Print a compact EMT initialization report.

    :param problem: EMT problem.
    :return: None.
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
        print(f"  succeeded : {report.status.name in {'SUCCESS', 'RESOLVED'}}")


def build_plot_data(
    problem: EmtProblemDae,
    objects: BessRunObjects,
    blocks: BessEmtBlocks,
    y_values: np.ndarray,
    case: BessCase,
) -> Dict[str, np.ndarray | None]:
    """
    Collect key trajectories for BESS validation plots.

    :param problem: EMT problem.
    :param objects: Static grid objects.
    :param blocks: Attached EMT blocks.
    :param y_values: EMT solution matrix.
    :param case: Simulation case.
    :return: Named signal dictionary.
    """
    data: Dict[str, np.ndarray | None] = dict()

    data["v_ac_a"] = get_signal(problem, objects.bus_bess.emt_model, f"v_A_Bus_BESS_{case.name}_emt_template", y_values)
    data["v_ac_b"] = get_signal(problem, objects.bus_bess.emt_model, f"v_B_Bus_BESS_{case.name}_emt_template", y_values)
    data["v_ac_c"] = get_signal(problem, objects.bus_bess.emt_model, f"v_C_Bus_BESS_{case.name}_emt_template", y_values)

    data["i_a"] = get_signal(problem, blocks.bess_mdl, f"i_A_bess_avm_{case.name}", y_values)
    data["i_b"] = get_signal(problem, blocks.bess_mdl, f"i_B_bess_avm_{case.name}", y_values)
    data["i_c"] = get_signal(problem, blocks.bess_mdl, f"i_C_bess_avm_{case.name}", y_values)

    data["p"] = get_signal(problem, blocks.bess_mdl, f"P_bess_avm_{case.name}", y_values)
    data["q"] = get_signal(problem, blocks.bess_mdl, f"Q_bess_avm_{case.name}", y_values)
    data["v_dc_internal"] = get_signal(problem, blocks.bess_mdl, f"v_dc_bess_avm_{case.name}", y_values)
    data["i_dc"] = get_signal(problem, blocks.bess_mdl, f"i_dc_bess_avm_{case.name}", y_values)

    data["soc"] = get_signal(problem, blocks.bess_mdl, f"soc_bess_avm_{case.name}", y_values)
    data["v_oc"] = get_signal(problem, blocks.bess_mdl, f"v_oc_bat_bess_avm_{case.name}", y_values)
    data["v_dc_bus"] = get_signal(problem, blocks.bess_mdl, f"v_dc_bus_bat_bess_avm_{case.name}", y_values)
    data["i_bat"] = get_signal(problem, blocks.bess_mdl, f"i_bat_bess_avm_{case.name}", y_values)
    data["p_bat"] = get_signal(problem, blocks.bess_mdl, f"p_bat_bess_avm_{case.name}", y_values)

    data["theta_pll"] = get_optional_signal(problem, blocks.bess_mdl, f"theta_pll_bess_avm_{case.name}", y_values)
    data["omega_pll"] = get_optional_signal(problem, blocks.bess_mdl, f"omega_pll_bess_avm_{case.name}", y_values)
    data["i_d"] = get_optional_signal(problem, blocks.bess_mdl, f"i_d_bess_avm_{case.name}", y_values)
    data["i_q"] = get_optional_signal(problem, blocks.bess_mdl, f"i_q_bess_avm_{case.name}", y_values)
    data["i_0"] = get_optional_signal(problem, blocks.bess_mdl, f"i_0_bess_avm_{case.name}", y_values)

    if data["p"] is None:
        data["p_grid"] = None
    else:
        data["p_grid"] = -data["p"]

    return data


def print_case_metrics(case: BessCase, time_values: np.ndarray, data: Dict[str, np.ndarray | None]) -> None:
    """
    Print compact numerical diagnostics for one case.

    :param case: Simulation case.
    :param time_values: Simulation time vector.
    :param data: Signal dictionary.
    :return: None.
    """
    p_values: np.ndarray | None = data["p"]
    p_grid_values: np.ndarray | None = data["p_grid"]
    q_values: np.ndarray | None = data["q"]
    soc_values: np.ndarray | None = data["soc"]
    vdc_values: np.ndarray | None = data["v_dc_internal"]
    pbat_values: np.ndarray | None = data["p_bat"]

    mask: np.ndarray = time_values >= 0.5 * time_values[-1]

    print("\n" + "=" * 80)
    print(f"BESS EMT metrics | case = {case.name}")
    print("=" * 80)
    print("  note                    : `P AC` is converter sign, `P grid` is export-positive, `P_bat` is battery-discharge-positive")

    if p_values is not None:
        print(f"  mean P AC second half   : {float(np.mean(p_values[mask])): .6f} pu")
    if p_grid_values is not None:
        print(f"  mean P grid second half : {float(np.mean(p_grid_values[mask])): .6f} pu")
    if q_values is not None:
        print(f"  mean Q second half      : {float(np.mean(q_values[mask])): .6f} pu")
    if pbat_values is not None:
        print(f"  mean P_bat second half  : {float(np.mean(pbat_values[mask])): .6f} pu")
    if soc_values is not None:
        print(f"  initial SoC             : {float(soc_values[0]): .6f}")
        print(f"  final SoC               : {float(soc_values[-1]): .6f}")
        print(f"  min/max SoC             : {float(np.min(soc_values)): .6f} / {float(np.max(soc_values)): .6f}")
    if vdc_values is not None:
        print(f"  min/max internal Vdc    : {float(np.min(vdc_values)): .6f} / {float(np.max(vdc_values)): .6f}")


def plot_one_case(case: BessCase, time_values: np.ndarray, data: Dict[str, np.ndarray | None]) -> None:
    """
    Plot one complete BESS EMT simulation case.

    :param case: Simulation case.
    :param time_values: Simulation time vector.
    :param data: Signal dictionary.
    :return: None.
    """
    figure, axes = plt.subplots(5, 1, figsize=(13, 15), sharex=True)
    figure.suptitle(f"Level-1 AVM grid-following BESS EMT example | {case.name}")

    axes[0].plot(time_values, data["v_ac_a"], label="Va")
    axes[0].plot(time_values, data["v_ac_b"], label="Vb")
    axes[0].plot(time_values, data["v_ac_c"], label="Vc")
    axes[0].set_ylabel("Voltage [pu]")
    axes[0].set_title("AC bus phase voltages")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")

    axes[1].plot(time_values, data["i_a"], label="iA BESS")
    axes[1].plot(time_values, data["i_b"], label="iB BESS")
    axes[1].plot(time_values, data["i_c"], label="iC BESS")
    axes[1].set_ylabel("Current [pu]")
    axes[1].set_title("BESS AC current injection")
    axes[1].grid(True)
    axes[1].legend(loc="upper right")

    axes[2].plot(time_values, data["p"], label="P AC")
    axes[2].plot(time_values, data["p_grid"], label="P grid")
    axes[2].plot(time_values, data["q"], label="Q AC")
    axes[2].plot(time_values, data["p_bat"], "--", label="P battery")
    axes[2].axhline(case.active_power_mw / 100.0, linestyle=":", linewidth=1.0, label="Battery P target / Sbase")
    axes[2].set_ylabel("Power [pu]")
    axes[2].set_title("AC power, grid export power and battery terminal power")
    axes[2].grid(True)
    axes[2].legend(loc="upper right")

    axes[3].plot(time_values, data["v_dc_internal"], label="internal Vdc")
    axes[3].plot(time_values, data["v_dc_bus"], "--", label="battery terminal Vdc")
    axes[3].plot(time_values, data["v_oc"], ":", label="battery OCV")
    axes[3].plot(time_values, data["i_dc"], label="VSC Idc")
    axes[3].plot(time_values, data["i_bat"], "--", label="battery current")
    axes[3].set_ylabel("DC [pu]")
    axes[3].set_title("DC-link and battery terminal variables")
    axes[3].grid(True)
    axes[3].legend(loc="upper right")

    axes[4].plot(time_values, data["soc"], label="SoC")
    if data["i_d"] is not None:
        axes[4].plot(time_values, data["i_d"], label="i_d")
    if data["i_q"] is not None:
        axes[4].plot(time_values, data["i_q"], label="i_q")
    if data["i_0"] is not None:
        axes[4].plot(time_values, data["i_0"], label="i_0")
    if data["omega_pll"] is not None:
        axes[4].plot(time_values, data["omega_pll"], label="omega_pll")
    axes[4].set_xlabel("Time [s]")
    axes[4].set_ylabel("Internal values")
    axes[4].set_title("SoC, dq0 currents and PLL diagnostic variables")
    axes[4].grid(True)
    axes[4].legend(loc="upper right")

    figure.tight_layout()
    plt.show()


def run_case(case: BessCase) -> Tuple[np.ndarray, Dict[str, np.ndarray | None]]:
    """
    Build, initialize and simulate one BESS EMT case.

    :param case: Simulation case.
    :return: Time vector and signal dictionary.
    """
    objects: BessRunObjects = build_grid(case)
    pf_results: PowerFlowResults = run_power_flow(objects.grid)

    print("\n" + "=" * 80)
    print(f"Balanced power flow results | case = {case.name}")
    print("=" * 80)
    print(f"  converged: {pf_results.converged}")
    if not pf_results.converged:
        raise RuntimeError(f"Power flow did not converge for BESS case '{case.name}'.")

    print(pf_results.get_bus_df())
    print(pf_results.get_branch_df())

    pf_results_3ph: PowerFlowResults3Ph = run_power_flow_3ph(objects.grid)
    print(f"  3ph converged: {pf_results_3ph.converged}")
    if not pf_results_3ph.converged:
        raise RuntimeError(f"3-phase power flow did not converge for BESS case '{case.name}'.")

    blocks: BessEmtBlocks = attach_emt_models(objects=objects, case=case)
    problem: EmtProblemDae = build_problem(grid=objects.grid, pf_results=pf_results, pf_results_3ph=pf_results_3ph)
    validate_initialization(problem)

    solver: StructuralCompiledSolver = build_solver(problem)
    time_values, y_values, _, well_initialized, converged = solver.simulate()

    print(f"well_initialized = {well_initialized}")
    print(f"converged = {converged}")

    data: Dict[str, np.ndarray | None] = build_plot_data(
        problem=problem,
        objects=objects,
        blocks=blocks,
        y_values=y_values,
        case=case,
    )
    print_case_metrics(case=case, time_values=time_values, data=data)

    return time_values, data


def main() -> None:
    """
    Run the charge and discharge BESS EMT examples.

    :return: None.
    """
    for case in CASES:
        time_values, data = run_case(case)
        plot_one_case(case=case, time_values=time_values, data=data)


if __name__ == "__main__":
    main()
