# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys
from typing import Any, Optional

import numpy as np
import matplotlib.pyplot as plt

SCRIPT_DIR: str = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT: str = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
SRC_ROOT: str = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
else:
    pass

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
else:
    pass

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledWarmupPolicy
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_transformer_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import ConverterControlType, DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, SolverType, VarPowerFlowRefferenceType


def find_name_in_block(name: str, block: Block) -> Optional[Var]:
    """
    Return one symbolic variable from a block hierarchy by name.

    :param name: Requested symbolic-variable name.
    :param block: Root symbolic block.
    :return: Matching variable or ``None``.
    """
    variable: Var
    child_block: Block
    nested_result: Optional[Var]

    for variable_list in [block.in_vars, block.out_vars, block.algebraic_vars, block.state_vars, block.diff_vars]:
        for variable in variable_list:
            if variable.name == name:
                return variable
            else:
                pass

    for variable in list(block.event_dict.keys()):
        if variable.name == name:
            return variable
        else:
            pass

    for child_block in block.children:
        nested_result = find_name_in_block(name, child_block)
        if nested_result is not None:
            return nested_result
        else:
            pass

    return None


def build_power_flow_options() -> PowerFlowOptions:
    """
    Build the balanced PF options used by the switched VSC EMT script.

    :return: Balanced PF options.
    """
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=False,
        max_iter=25,
        tolerance=1e-5,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )


def build_emt_options(
        solver_type: EmtSolverTypes = EmtSolverTypes.StructuralCompiled,
        initialization_method: EmtInitializationMethod = EmtInitializationMethod.Auto,
        integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeBackEuler,
        time_step: float = 1e-5,
        simulation_time: float = 1.2e-3,
        compiled_warmup_policy: StructuralCompiledWarmupPolicy = StructuralCompiledWarmupPolicy.Off,
) -> EmtOptions:
    """
    Build the EMT options used by the switched VSC EMT script.

    :return: EMT options instance.
    """
    return EmtOptions(
        time_step=time_step,
        simulation_time=simulation_time,
        tolerance=1e-6,
        solver_type=solver_type,
        integration_method=integration_method,
        initialization_method=initialization_method,
        compiled_warmup_policy=compiled_warmup_policy,
        verbose=0,
    )


def run_power_flow(grid: gce.MultiCircuit) -> tuple[Any, Any]:
    """
    Run the balanced PF used to seed the switched EMT case.

    :param grid: Circuit under test.
    :return: Tuple ``(pf_results, None)``.
    """
    pf_results: Any = gce.power_flow(grid=grid, options=build_power_flow_options())
    return pf_results, None


def build_switched_vsc_case(emt_options: Optional[EmtOptions] = None) -> tuple[EmtProblemDae, Bus, Bus, Bus, VSC]:
    """
    Build the switched EMT VSC validation case.

    :return: EMT problem plus the main buses and VSC object.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(name='Grid - Switched EMT VSC', Sbase=100.0, fbase=50.0)

    bus1_ac: Bus = gce.Bus(name='Bus1_AC', Vnom=230.0, is_slack=True)
    bus2_ac: Bus = gce.Bus(name='Bus2_AC', Vnom=230.0)
    bus3_dc: Bus = gce.Bus(name='Bus3_DC', Vnom=320.0, is_dc=True)
    grid.add_bus(bus1_ac)
    grid.add_bus(bus2_ac)
    grid.add_bus(bus3_dc)

    gen1: Generator = gce.Generator(name='Generator', vset=1.0, Snom=100.0, freq=50.0, r1=0.001, x1=0.4)
    transformer: Transformer2W = gce.Transformer2W(name='Transformer', bus_from=bus1_ac, bus_to=bus2_ac, rate=100.0, r=0.01, x=0.1, tap_module=1.0, tap_phase=0.0)
    vsc: VSC = gce.VSC(name='VSC', bus_from=bus3_dc, bus_to=bus2_ac, rate=100.0, control1=ConverterControlType.Qac, control2=ConverterControlType.Vm_dc, control1_val=0.0, control2_val=1.0)
    dc_load: Load = gce.Load(name='DC_Load', P=30.0, Q=0.0)

    grid.add_generator(bus1_ac, gen1)
    grid.add_transformer2w(transformer)
    grid.add_vsc(vsc)
    grid.add_load(bus3_dc, dc_load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    pf_results: Any
    pf_results_3ph: Any
    pf_results, pf_results_3ph = run_power_flow(grid)

    gen_mdl: Block = get_generator_thevenin_rl_emt_template(vf=grid.var_factory).block
    trafo_mdl: Block = get_transformer_emt_template(vf=grid.var_factory, name=transformer.name).block
    vsc_mdl: Block = get_switched_emt_converter(vf=grid.var_factory, name=vsc.name).block
    dc_load_mdl: Block = get_dc_load_emt_template(vf=grid.var_factory, name='dc_load_emt_switched').block

    set_emt_model(device=gen1, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=transformer, model=trafo_mdl, var_factory=grid.var_factory)
    set_emt_model(device=vsc, model=vsc_mdl, var_factory=grid.var_factory)
    set_emt_model(device=dc_load, model=dc_load_mdl, var_factory=grid.var_factory)

    resolved_emt_options: EmtOptions = build_emt_options() if emt_options is None else emt_options

    problem: EmtProblemDae = EmtProblemDae(
        grid=grid,
        options=resolved_emt_options,
        pf_results=pf_results,
        pf_results_3Ph=pf_results_3ph,
    )
    return problem, bus1_ac, bus2_ac, bus3_dc, vsc


def run_switched_vsc_case(enable_plots: bool = False, emt_options: Optional[EmtOptions] = None) -> None:
    """
    Run the switched EMT VSC scripting case.

    Expected behaviour:

    - all three gate traces must switch between ``0`` and ``1``,
    - AC currents must remain bounded,
    - the DC voltage must remain finite,
    - the switched model should run with the same outer VSC interface as the averaged EMT converter.

    :param enable_plots: Display matplotlib figures when ``True``.
    :return: None.
    """
    problem: EmtProblemDae
    bus1_ac: Bus
    bus2_ac: Bus
    bus3_dc: Bus
    vsc: VSC
    solver: Any
    time_s: np.ndarray
    state_traj: np.ndarray
    _diff_traj: np.ndarray
    v_A_bus2_var: Var | None
    v_B_bus2_var: Var | None
    v_C_bus2_var: Var | None
    v_dc_var: Var | None
    i_A_var: Var | None
    i_B_var: Var | None
    i_C_var: Var | None
    i_dc_var: Var | None
    gate_a_var: Var | None
    gate_b_var: Var | None
    gate_c_var: Var | None
    v_conv_a_var: Var | None
    v_conv_b_var: Var | None
    v_conv_c_var: Var | None

    resolved_emt_options = build_emt_options() if emt_options is None else emt_options
    problem, bus1_ac, bus2_ac, bus3_dc, vsc = build_switched_vsc_case(emt_options=resolved_emt_options)

    if problem.options.solver_type == EmtSolverTypes.Symbolic:
        solver = JitSymbolicSolver(
            problem=problem,
            t0=0.0,
            t_end=problem.options.simulation_time,
            h=problem.options.time_step,
            method=problem.options.integration_method,
            pred_method=DynamicIntegrationMethod.OdeEuler,
            dense_threshold=0,
            verbose=False,
        )
    else:
        solver = build_emt_solver(
            options=problem.options,
            problem=problem,
            t0=0.0,
            t_end=problem.options.simulation_time,
            h=problem.options.time_step,
            method=problem.options.integration_method,
        )

    time_s, state_traj, _diff_traj = solver.simulate(boundary_updater=problem)

    v_A_bus2_var = find_name_in_block('v_A_Bus2_AC_emt_template', bus2_ac.emt_model)
    v_B_bus2_var = find_name_in_block('v_B_Bus2_AC_emt_template', bus2_ac.emt_model)
    v_C_bus2_var = find_name_in_block('v_C_Bus2_AC_emt_template', bus2_ac.emt_model)
    v_dc_var = bus3_dc.emt_model.external_mapping[VarPowerFlowRefferenceType.Vdc]

    i_A_var = find_name_in_block('i_A_VSC', vsc.emt_model)
    i_B_var = find_name_in_block('i_B_VSC', vsc.emt_model)
    i_C_var = find_name_in_block('i_C_VSC', vsc.emt_model)
    i_dc_var = find_name_in_block('i_dc_VSC', vsc.emt_model)

    gate_a_var = find_name_in_block('gate_a_VSC', vsc.emt_model)
    gate_b_var = find_name_in_block('gate_b_VSC', vsc.emt_model)
    gate_c_var = find_name_in_block('gate_c_VSC', vsc.emt_model)
    v_conv_a_var = find_name_in_block('v_conv_a_VSC', vsc.emt_model)
    v_conv_b_var = find_name_in_block('v_conv_b_VSC', vsc.emt_model)
    v_conv_c_var = find_name_in_block('v_conv_c_VSC', vsc.emt_model)

    if v_A_bus2_var is None or v_B_bus2_var is None or v_C_bus2_var is None or i_A_var is None or i_B_var is None or i_C_var is None or i_dc_var is None or gate_a_var is None or gate_b_var is None or gate_c_var is None or v_conv_a_var is None or v_conv_b_var is None or v_conv_c_var is None:
        raise KeyError('One or more switched EMT VSC plotting variables could not be resolved')
    else:
        pass

    gate_a_trace: np.ndarray = np.array(state_traj[:, problem.get_var_idx(gate_a_var)], copy=True)
    gate_b_trace: np.ndarray = np.array(state_traj[:, problem.get_var_idx(gate_b_var)], copy=True)
    gate_c_trace: np.ndarray = np.array(state_traj[:, problem.get_var_idx(gate_c_var)], copy=True)

    print('=' * 72)
    print('SWITCHED VSC EMT SUMMARY')
    print('=' * 72)
    if problem.initialization_report is not None:
        print(f'Initialization requested: {problem.initialization_report.method_requested}')
        print(f'Initialization used     : {problem.initialization_report.method_used}')
    else:
        pass
    print(f'Solver type           : {problem.options.solver_type}')
    print(f'Final Vdc            : {float(state_traj[-1, problem.get_var_idx(v_dc_var)]): .6f} p.u.')
    print(f'Final Idc            : {float(state_traj[-1, problem.get_var_idx(i_dc_var)]): .6f} p.u.')
    print(f'Gate A range         : {float(np.min(gate_a_trace)): .3f} .. {float(np.max(gate_a_trace)): .3f}')
    print(f'Gate B range         : {float(np.min(gate_b_trace)): .3f} .. {float(np.max(gate_b_trace)): .3f}')
    print(f'Gate C range         : {float(np.min(gate_c_trace)): .3f} .. {float(np.max(gate_c_trace)): .3f}')

    if enable_plots:
        _plot_switched_vsc_results(
            time_s=time_s,
            state_traj=state_traj,
            problem=problem,
            v_A_bus2_var=v_A_bus2_var,
            v_B_bus2_var=v_B_bus2_var,
            v_C_bus2_var=v_C_bus2_var,
            v_dc_var=v_dc_var,
            i_A_var=i_A_var,
            i_B_var=i_B_var,
            i_C_var=i_C_var,
            i_dc_var=i_dc_var,
            gate_a_var=gate_a_var,
            gate_b_var=gate_b_var,
            gate_c_var=gate_c_var,
            v_conv_a_var=v_conv_a_var,
            v_conv_b_var=v_conv_b_var,
            v_conv_c_var=v_conv_c_var,
        )
    else:
        pass


def _plot_switched_vsc_results(
        time_s: np.ndarray,
        state_traj: np.ndarray,
        problem: EmtProblemDae,
        v_A_bus2_var: Var,
        v_B_bus2_var: Var,
        v_C_bus2_var: Var,
        v_dc_var: Var,
        i_A_var: Var,
        i_B_var: Var,
        i_C_var: Var,
        i_dc_var: Var,
        gate_a_var: Var,
        gate_b_var: Var,
        gate_c_var: Var,
        v_conv_a_var: Var,
        v_conv_b_var: Var,
        v_conv_c_var: Var,
) -> None:
    """
    Plot the switched EMT VSC results.

    :param time_s: EMT time vector.
    :param state_traj: EMT state trajectory.
    :param problem: EMT DAE problem.
    :param v_A_bus2_var: Bus2 phase-A voltage variable.
    :param v_B_bus2_var: Bus2 phase-B voltage variable.
    :param v_C_bus2_var: Bus2 phase-C voltage variable.
    :param v_dc_var: DC-bus voltage variable.
    :param i_A_var: Converter phase-A current variable.
    :param i_B_var: Converter phase-B current variable.
    :param i_C_var: Converter phase-C current variable.
    :param i_dc_var: Converter DC current variable.
    :param gate_a_var: Gate-A variable.
    :param gate_b_var: Gate-B variable.
    :param gate_c_var: Gate-C variable.
    :param v_conv_a_var: Applied converter phase-A voltage variable.
    :param v_conv_b_var: Applied converter phase-B voltage variable.
    :param v_conv_c_var: Applied converter phase-C voltage variable.
    :return: None.
    """
    fig, axes = plt.subplots(5, 1, figsize=(14.0, 13.0), sharex=True)

    axes[0].plot(time_s, state_traj[:, problem.get_var_idx(v_A_bus2_var)], label='Bus2 - Phase A', color='blue')
    axes[0].plot(time_s, state_traj[:, problem.get_var_idx(v_B_bus2_var)], label='Bus2 - Phase B', color='red')
    axes[0].plot(time_s, state_traj[:, problem.get_var_idx(v_C_bus2_var)], label='Bus2 - Phase C', color='green')
    axes[0].set_ylabel('Voltage [p.u.]')
    axes[0].set_title('Switched VSC EMT - AC Bus Voltages')
    axes[0].grid(True)
    axes[0].legend(loc='best')

    axes[1].plot(time_s, state_traj[:, problem.get_var_idx(v_conv_a_var)], label='v_conv_a', color='blue')
    axes[1].plot(time_s, state_traj[:, problem.get_var_idx(v_conv_b_var)], label='v_conv_b', color='red')
    axes[1].plot(time_s, state_traj[:, problem.get_var_idx(v_conv_c_var)], label='v_conv_c', color='green')
    axes[1].set_ylabel('Voltage [p.u.]')
    axes[1].set_title('Switched VSC EMT - Converter Voltages')
    axes[1].grid(True)
    axes[1].legend(loc='best')

    axes[2].plot(time_s, state_traj[:, problem.get_var_idx(i_A_var)], label='i_A', color='blue')
    axes[2].plot(time_s, state_traj[:, problem.get_var_idx(i_B_var)], label='i_B', color='red')
    axes[2].plot(time_s, state_traj[:, problem.get_var_idx(i_C_var)], label='i_C', color='green')
    axes[2].plot(time_s, state_traj[:, problem.get_var_idx(i_dc_var)], label='i_dc', color='orange')
    axes[2].set_ylabel('Current [p.u.]')
    axes[2].set_title('Switched VSC EMT - Currents')
    axes[2].grid(True)
    axes[2].legend(loc='best')

    axes[3].plot(time_s, state_traj[:, problem.get_var_idx(v_dc_var)], label='Vdc', color='purple')
    axes[3].set_ylabel('Voltage [p.u.]')
    axes[3].set_title('Switched VSC EMT - DC Voltage')
    axes[3].grid(True)
    axes[3].legend(loc='best')

    axes[4].step(time_s, state_traj[:, problem.get_var_idx(gate_a_var)], where='post', label='gate_A', color='blue')
    axes[4].step(time_s, state_traj[:, problem.get_var_idx(gate_b_var)], where='post', label='gate_B', color='red')
    axes[4].step(time_s, state_traj[:, problem.get_var_idx(gate_c_var)], where='post', label='gate_C', color='green')
    axes[4].set_xlabel('Time [s]')
    axes[4].set_ylabel('Gate [-]')
    axes[4].set_title('Switched VSC EMT - Gates')
    axes[4].grid(True)
    axes[4].legend(loc='best')

    fig.tight_layout()
    plt.show()


def main() -> None:
    """
    Run the switched EMT VSC scripting case.

    :return: None.
    """
    run_switched_vsc_case(enable_plots=True)


if __name__ == '__main__':
    main()
