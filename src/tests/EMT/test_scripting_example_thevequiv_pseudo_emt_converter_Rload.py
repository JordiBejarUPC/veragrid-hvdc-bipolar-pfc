# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Templates.Emt.converter_emt_template import get_full_pseudo_emt_converter
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_transformer_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import ConverterControlType, DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, SolverType


def build_grid() -> Tuple[gce.MultiCircuit, gce.Bus, gce.Bus, gce.Bus, gce.Generator, gce.Transformer2W, gce.VSC, gce.Load]:
    """
    Build the AC/DC network used by the pseudo-converter scripting regression.

    :return: Grid and the key devices used by the case.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(
        name="Grid - Thevenin + pseudo EMT converter + DC R load",
        Sbase=100.0,
        fbase=50.0,
    )
    bus_slack_ac: gce.Bus = gce.Bus(name="Bus_SLACK_AC", Vnom=230.0, is_slack=True)
    bus_ac: gce.Bus = gce.Bus(name="Bus_AC", Vnom=230.0)
    bus_dc: gce.Bus = gce.Bus(name="Bus_DC", Vnom=320.0, is_dc=True)
    generator: gce.Generator = gce.Generator(name="Gen_Thev", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=0.04)
    transformer: gce.Transformer2W = gce.Transformer2W(
        name="AC_Thevenin_Link",
        bus_from=bus_slack_ac,
        bus_to=bus_ac,
        rate=grid.Sbase,
        r=1.0e-5,
        x=1.0e-5,
        tap_module=1.0,
        tap_phase=0.0,
    )
    p_transfer_mw: float = 30.0
    q_transfer_mvar: float = 0.0
    converter: gce.VSC = gce.VSC(
        name="pseudo_converter_emt",
        bus_from=bus_dc,
        bus_to=bus_ac,
        rate=grid.Sbase,
        control1=ConverterControlType.Pdc,
        control2=ConverterControlType.Qac,
        control1_val=-p_transfer_mw,
        control2_val=q_transfer_mvar,
    )
    dc_load: gce.Load = gce.Load(name="DC_R_Load", P=p_transfer_mw, Q=0.0)

    grid.add_bus(bus_slack_ac)
    grid.add_bus(bus_ac)
    grid.add_bus(bus_dc)
    grid.add_generator(bus_slack_ac, generator)
    grid.add_transformer2w(transformer)
    grid.add_vsc(converter)
    grid.add_load(bus_dc, dc_load)
    return grid, bus_slack_ac, bus_ac, bus_dc, generator, transformer, converter, dc_load


def attach_emt_models(
        grid: gce.MultiCircuit,
        generator: gce.Generator,
        transformer: gce.Transformer2W,
        converter: gce.VSC,
        dc_load: gce.Load,
        pf_results: PowerFlowResults,
) -> Tuple[Block, Block, Block, Block]:
    """
    Attach the EMT models used by the pseudo-converter scripting case.

    :param grid: Example grid.
    :param generator: Thevenin source API object.
    :param transformer: AC-side interface transformer.
    :param converter: Pseudo-EMT converter API object.
    :param dc_load: DC resistive load API object.
    :param pf_results: Balanced power-flow seed.
    :return: Attached EMT blocks for the main devices.
    """
    _ = pf_results
    bus: gce.Bus
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    gen_mdl: Block = get_generator_thevenin_rl_emt_template(vf=grid.var_factory).block
    transformer_mdl: Block = get_transformer_emt_template(vf=grid.var_factory, name="ac_thevenin_link_emt").block

    converter.control1 = ConverterControlType.Vm_dc
    converter.control2 = ConverterControlType.Qac
    converter.control1_val = 1.0
    converter.control2_val = 0.0

    vsc_mdl: Block = get_full_pseudo_emt_converter(vf=grid.var_factory).block
    vsc_mdl.set_parameter_in_model(var_name="sbase_pseudo_converter_emt", new_value=grid.Sbase)
    vsc_mdl.set_parameter_in_model(var_name="R_eq_pseudo_converter_emt", new_value=0.03)
    vsc_mdl.set_parameter_in_model(var_name="L_eq_pseudo_converter_emt", new_value=0.12)
    vsc_mdl.set_parameter_in_model(var_name="C_dc_pseudo_converter_emt", new_value=0.08)
    vsc_mdl.set_parameter_in_model(var_name="R_dc_pseudo_converter_emt", new_value=1e6)
    vsc_mdl.set_parameter_in_model(var_name="R_dc_term_pseudo_converter_emt", new_value=0.0001)
    vsc_mdl.set_parameter_in_model(var_name="P0_pseudo_converter_emt", new_value=float(dc_load.P))
    vsc_mdl.set_parameter_in_model(var_name="pll_kp_pseudo_converter_emt", new_value=40.0)
    vsc_mdl.set_parameter_in_model(var_name="pll_ki_pseudo_converter_emt", new_value=400.0)
    vsc_mdl.set_parameter_in_model(var_name="i_kp_pseudo_converter_emt", new_value=0.6)
    vsc_mdl.set_parameter_in_model(var_name="i_ki_pseudo_converter_emt", new_value=50.0)
    vsc_mdl.set_parameter_in_model(var_name="vdc_kp_pseudo_converter_emt", new_value=2.0)
    vsc_mdl.set_parameter_in_model(var_name="vdc_ki_pseudo_converter_emt", new_value=30.0)
    vsc_mdl.set_parameter_in_model(var_name="q_kp_pseudo_converter_emt", new_value=0.8)
    vsc_mdl.set_parameter_in_model(var_name="q_ki_pseudo_converter_emt", new_value=20.0)
    vsc_mdl.set_parameter_in_model(var_name="i_max_pseudo_converter_emt", new_value=1.3)
    vsc_mdl.set_parameter_in_model(var_name="m_max_pseudo_converter_emt", new_value=0.95)
    vsc_mdl.set_parameter_in_model(var_name="P_loss_i1_pseudo_converter_emt", new_value=0.01)
    vsc_mdl.set_parameter_in_model(var_name="P_loss_i2_pseudo_converter_emt", new_value=0.01)
    vsc_mdl.set_parameter_in_model(var_name="tau_meas_pseudo_converter_emt", new_value=0.01)
    vsc_mdl.set_parameter_in_model(var_name="aw_gain_pseudo_converter_emt", new_value=0.1)
    vsc_mdl.set_parameter_in_model(var_name="vdc_floor_pseudo_converter_emt", new_value=0.05)

    dc_load_mdl: Block = get_dc_load_emt_template(vf=grid.var_factory, name="dc_r_load_emt").block

    set_emt_model(device=generator, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=transformer, model=transformer_mdl, var_factory=grid.var_factory)
    set_emt_model(device=converter, model=vsc_mdl, var_factory=grid.var_factory)
    set_emt_model(device=dc_load, model=dc_load_mdl, var_factory=grid.var_factory)
    return gen_mdl, transformer_mdl, vsc_mdl, dc_load_mdl


def build_power_flow_options() -> PowerFlowOptions:
    """
    Build the balanced power-flow options used by the pseudo-converter case.

    :return: Balanced power-flow options.
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
    Run the balanced AC/DC power flow used by the regression case.

    :param grid: Example grid.
    :return: Balanced power-flow results.
    """
    return gce.power_flow(grid=grid, options=build_power_flow_options())


def build_problem(grid: gce.MultiCircuit, pf_results: PowerFlowResults) -> EmtProblemDae:
    """
    Build the EMT problem used by the pseudo-converter regression case.

    :param grid: Example grid.
    :param pf_results: Balanced power-flow results.
    :return: Configured EMT problem.
    """
    options: EmtOptions = EmtOptions(
        time_step=2.0e-5,
        simulation_time=0.15,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=1,
    )
    return EmtProblemDae(grid=grid, options=options, pf_results_3ph=None, pf_results=pf_results)


def build_solver(problem: EmtProblemDae) -> StructuralCompiledSolver:
    """
    Build the compiled EMT solver used by the pseudo-converter regression case.

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


def get_signal(problem: EmtProblemDae, root_block: Block, variable_name: str, state_traj: np.ndarray) -> np.ndarray:
    """
    Extract one named symbolic trajectory from the EMT solution matrix.

    :param problem: EMT problem with variable indexing.
    :param root_block: Root block where the variable will be searched.
    :param variable_name: Symbolic variable name.
    :param state_traj: EMT variable trajectory matrix.
    :return: Selected trajectory.
    """
    variable: Var | None = find_name_in_block(variable_name, root_block)

    if variable is None:
        raise ValueError(f"Variable '{variable_name}' not found in block '{root_block.name}'.")
    else:
        return state_traj[:, problem.get_var_idx(variable)]


def build_plot_data(
        problem: EmtProblemDae,
        bus_ac: gce.Bus,
        bus_dc: gce.Bus,
        gen_mdl: Block,
        vsc_mdl: Block,
        dc_load_mdl: Block,
        state_traj: np.ndarray,
) -> Dict[str, np.ndarray]:
    """
    Collect the named trajectories used by the pseudo-converter script plots.

    :param problem: EMT problem.
    :param bus_ac: AC bus.
    :param bus_dc: DC bus.
    :param gen_mdl: Thevenin EMT model.
    :param vsc_mdl: Pseudo-EMT converter model.
    :param dc_load_mdl: DC load model.
    :param state_traj: EMT state trajectory matrix.
    :return: Named trajectories.
    """
    data: Dict[str, np.ndarray] = dict()
    data["v_ac_a"] = get_signal(problem, bus_ac.emt_model, "v_A_Bus_AC_emt_template", state_traj)
    data["v_ac_b"] = get_signal(problem, bus_ac.emt_model, "v_B_Bus_AC_emt_template", state_traj)
    data["v_ac_c"] = get_signal(problem, bus_ac.emt_model, "v_C_Bus_AC_emt_template", state_traj)
    data["v_dc_bus"] = get_signal(problem, bus_dc.emt_model, "v_DC_Bus_DC_emt_template", state_traj)
    data["i_gen_a"] = get_signal(problem, gen_mdl, "i_A_emt_thevenin_eq_generator_template", state_traj)
    data["i_conv_a"] = get_signal(problem, vsc_mdl, "i_A_pseudo_converter_emt", state_traj)
    data["i_conv_b"] = get_signal(problem, vsc_mdl, "i_B_pseudo_converter_emt", state_traj)
    data["i_conv_c"] = get_signal(problem, vsc_mdl, "i_C_pseudo_converter_emt", state_traj)
    data["i_dc_conv"] = get_signal(problem, vsc_mdl, "i_dc_pseudo_converter_emt", state_traj)
    data["i_dc_load"] = -get_signal(problem, dc_load_mdl, "i_dc_dc_r_load_emt", state_traj)
    data["v_dc_internal"] = get_signal(problem, vsc_mdl, "v_dc_pseudo_converter_emt", state_traj)
    data["theta_pll"] = get_signal(problem, vsc_mdl, "theta_pll_pseudo_converter_emt", state_traj)
    data["i_d"] = get_signal(problem, vsc_mdl, "i_d_pseudo_converter_emt", state_traj)
    data["i_q"] = get_signal(problem, vsc_mdl, "i_q_pseudo_converter_emt", state_traj)
    data["P"] = get_signal(problem, vsc_mdl, "P_pseudo_converter_emt", state_traj)
    data["Q"] = get_signal(problem, vsc_mdl, "Q_pseudo_converter_emt", state_traj)
    return data


def _build_results_dataframe(time_s: np.ndarray, data: Dict[str, np.ndarray]) -> pd.DataFrame:
    """
    Build the snapshot dataframe used by the pseudo-converter regression test.

    :param time_s: EMT simulation time vector.
    :param data: Named simulation trajectories.
    :return: Snapshot dataframe indexed by time.
    """
    dataframe_dict: Dict[str, np.ndarray] = dict()
    column_name: str

    for column_name, values in data.items():
        dataframe_dict[column_name] = np.asarray(values, dtype=float)

    results_df: pd.DataFrame = pd.DataFrame(dataframe_dict, index=np.asarray(time_s, dtype=float))
    results_df.index.name = "time_s"
    return results_df


def test_scripting_example_thevequiv_pseudo_emt_converter_rload() -> None:
    """
    Run the pseudo-EMT converter scripting example and compare its named
    trajectories against the stored CSV snapshot.

    :return: None.
    """
    reference_name: str = "scripting_example_thevequiv_pseudo_emt_converter_Rload.csv"
    reference_path: str = os.path.join(os.path.dirname(__file__), "..", "data", "dynamics", reference_name)
    reference_df: pd.DataFrame = pd.read_csv(reference_path)

    grid, _bus_slack_ac, bus_ac, bus_dc, generator, transformer, converter, dc_load = build_grid()
    pf_results: PowerFlowResults = run_power_flow(grid)
    gen_mdl, _transformer_mdl, vsc_mdl, dc_load_mdl = attach_emt_models(
        grid=grid,
        generator=generator,
        transformer=transformer,
        converter=converter,
        dc_load=dc_load,
        pf_results=pf_results,
    )
    problem: EmtProblemDae = build_problem(grid=grid, pf_results=pf_results)
    solver: StructuralCompiledSolver = build_solver(problem)
    time_s, state_traj, _diff_traj, well_initialized, converged = solver.simulate(boundary_updater=problem)

    assert bool(well_initialized) is True
    assert bool(np.all(np.isfinite(state_traj))) is True

    plot_data: Dict[str, np.ndarray] = build_plot_data(
        problem=problem,
        bus_ac=bus_ac,
        bus_dc=bus_dc,
        gen_mdl=gen_mdl,
        vsc_mdl=vsc_mdl,
        dc_load_mdl=dc_load_mdl,
        state_traj=state_traj,
    )
    results_df: pd.DataFrame = _build_results_dataframe(time_s=time_s, data=plot_data)
    results_df = results_df.reset_index(drop=False)

    assert_frame_equal(
        results_df,
        reference_df,
        check_dtype=False,
        check_index_type=False,
        atol=1.0e-9,
        rtol=1.0e-9,
    )
    assert bool(converged) is False
