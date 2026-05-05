# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np

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

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper, JitSymbolicSolver
from VeraGridEngine.Templates.Emt.valve_emt_template import get_valve_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block
from VeraGridEngine.enumerations import DynamicIntegrationMethod, ValveEmtModelVariant, ValveEmtType, ValveInitializationState, VarPowerFlowRefferenceType


class GenericEmtProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by the self-contained valve script.
    """

    __slots__ = []


class GateScheduleBoundaryUpdater(BoundaryUpdateWrapper):
    """
    Apply a piecewise-constant gate schedule while preserving the block-owned EMT update.
    """

    __slots__ = [
        '_base_updater',
        '_gate_param_idx',
        '_mode_param_idx',
        '_event_time_s',
        '_event_value',
        '_record_time_s',
        '_record_gate',
        '_record_mode',
        '_record_count',
    ]

    def __init__(
            self,
            base_updater: BoundaryUpdateWrapper | None,
            gate_param_idx: int,
            mode_param_idx: int,
            event_time_s: np.ndarray,
            event_value: np.ndarray,
            max_records: int,
    ) -> None:
        """
        Build one gate-schedule boundary updater.

        :param base_updater: Optional updater generated from the block procedural logic.
        :param gate_param_idx: Runtime index of the gate parameter.
        :param mode_param_idx: Runtime index of the retained valve mode.
        :param event_time_s: Sorted event times.
        :param event_value: Piecewise-constant gate values.
        :param max_records: Maximum number of recorded samples.
        :return: None.
        """
        self._base_updater = base_updater
        self._gate_param_idx = int(gate_param_idx)
        self._mode_param_idx = int(mode_param_idx)
        self._event_time_s = np.array(event_time_s, copy=True)
        self._event_value = np.array(event_value, copy=True)
        self._record_time_s = np.zeros(max_records, dtype=float)
        self._record_gate = np.zeros(max_records, dtype=float)
        self._record_mode = np.zeros(max_records, dtype=float)
        self._record_count = 0

    def _get_gate_value(self, time_s: float) -> float:
        """
        Return the scheduled gate value at one time instant.

        :param time_s: Current simulation time.
        :return: Scheduled gate value.
        """
        event_idx: int = 0
        gate_value: float = float(self._event_value[0])

        while event_idx < len(self._event_time_s):
            if time_s >= float(self._event_time_s[event_idx]):
                gate_value = float(self._event_value[event_idx])
            else:
                pass
            event_idx += 1

        return gate_value

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Apply the gate command and then delegate to the optional base updater.

        :param t: Current simulation time.
        :param x: Accepted EMT state vector.
        :param params: Full parameter vector.
        :return: None.
        """
        gate_value: float = self._get_gate_value(float(t))

        # The new gate value must be visible to the retained valve logic in the same accepted step.
        params[self._gate_param_idx] = gate_value

        if self._base_updater is not None:
            self._base_updater.update(float(t), x, params)
        else:
            pass

        if self._record_count < len(self._record_time_s):
            self._record_time_s[self._record_count] = float(t)
            self._record_gate[self._record_count] = gate_value
            self._record_mode[self._record_count] = float(params[self._mode_param_idx])
            self._record_count += 1
        else:
            pass

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Return the earliest forced event from the gate schedule or the delegated updater.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest forced event time or ``None``.
        """
        event_idx: int = 0
        local_time: float | None = None
        base_time: float | None

        while event_idx < len(self._event_time_s):
            event_time: float = float(self._event_time_s[event_idx])
            if float(t_prev) < event_time <= float(t_target):
                local_time = event_time
                event_idx = len(self._event_time_s)
            else:
                event_idx += 1

        if self._base_updater is None:
            base_time = None
        else:
            base_time = self._base_updater.get_next_forced_event_time(float(t_prev), float(t_target))

        if local_time is None:
            return base_time
        else:
            pass

        if base_time is None:
            return local_time
        else:
            pass

        if local_time <= base_time:
            return local_time
        else:
            return base_time

    def get_record_time_s(self) -> np.ndarray:
        """
        Return the recorded control-update time vector.

        :return: Recorded control-update time vector.
        """
        return np.array(self._record_time_s[:self._record_count], copy=True)

    def get_record_gate(self) -> np.ndarray:
        """
        Return the recorded gate trace.

        :return: Recorded gate trace.
        """
        return np.array(self._record_gate[:self._record_count], copy=True)

    def get_record_mode(self) -> np.ndarray:
        """
        Return the recorded retained mode trace.

        :return: Recorded retained mode trace.
        """
        return np.array(self._record_mode[:self._record_count], copy=True)


class ValveCaseResult:
    """
    Store the traces produced by one self-contained EMT valve case.
    """

    __slots__ = [
        '_time_s',
        '_v_source_pu',
        '_v_load_pu',
        '_i_branch_pu',
        '_v_valve_pu',
        '_control_time_s',
        '_gate_trace',
        '_mode_trace',
    ]

    def __init__(
            self,
            time_s: np.ndarray,
            v_source_pu: np.ndarray,
            v_load_pu: np.ndarray,
            i_branch_pu: np.ndarray,
            v_valve_pu: np.ndarray,
            control_time_s: np.ndarray,
            gate_trace: np.ndarray,
            mode_trace: np.ndarray,
    ) -> None:
        """
        Build one result container.

        :param time_s: EMT time vector.
        :param v_source_pu: Source-side voltage trace.
        :param v_load_pu: Load-side voltage trace.
        :param i_branch_pu: Branch-current trace.
        :param v_valve_pu: Valve-voltage trace.
        :param control_time_s: Time vector of the control records.
        :param gate_trace: Gate-command trace.
        :param mode_trace: Retained-mode trace.
        :return: None.
        """
        self._time_s = np.array(time_s, copy=True)
        self._v_source_pu = np.array(v_source_pu, copy=True)
        self._v_load_pu = np.array(v_load_pu, copy=True)
        self._i_branch_pu = np.array(i_branch_pu, copy=True)
        self._v_valve_pu = np.array(v_valve_pu, copy=True)
        self._control_time_s = np.array(control_time_s, copy=True)
        self._gate_trace = np.array(gate_trace, copy=True)
        self._mode_trace = np.array(mode_trace, copy=True)

    def get_time_s(self) -> np.ndarray:
        """
        Return the EMT time vector.

        :return: EMT time vector.
        """
        return np.array(self._time_s, copy=True)

    def get_v_source_pu(self) -> np.ndarray:
        """
        Return the source-side voltage trace.

        :return: Source-side voltage trace.
        """
        return np.array(self._v_source_pu, copy=True)

    def get_v_load_pu(self) -> np.ndarray:
        """
        Return the load-side voltage trace.

        :return: Load-side voltage trace.
        """
        return np.array(self._v_load_pu, copy=True)

    def get_i_branch_pu(self) -> np.ndarray:
        """
        Return the branch-current trace.

        :return: Branch-current trace.
        """
        return np.array(self._i_branch_pu, copy=True)

    def get_v_valve_pu(self) -> np.ndarray:
        """
        Return the valve-voltage trace.

        :return: Valve-voltage trace.
        """
        return np.array(self._v_valve_pu, copy=True)

    def get_control_time_s(self) -> np.ndarray:
        """
        Return the control-record time vector.

        :return: Control-record time vector.
        """
        return np.array(self._control_time_s, copy=True)

    def get_gate_trace(self) -> np.ndarray:
        """
        Return the gate-command trace.

        :return: Gate-command trace.
        """
        return np.array(self._gate_trace, copy=True)

    def get_mode_trace(self) -> np.ndarray:
        """
        Return the retained-mode trace.

        :return: Retained-mode trace.
        """
        return np.array(self._mode_trace, copy=True)


def _build_constant_algebraic_var(vf: VarFactory, name: str, value: float) -> Tuple[Var, Expr]:
    """
    Build one algebraic variable constrained to a constant reference value.

    :param vf: Shared symbolic variable factory.
    :param name: Variable name.
    :param value: Constant reference value.
    :return: Tuple ``(variable, equation)``.
    """
    variable: Var = vf.add_var(name=name)
    reference_value: Const = vf.add_const(float(value))
    equation: Expr = variable - reference_value
    return variable, equation


def _set_block_runtime_parameter(block: Block, parameter_name: str, value: float) -> None:
    """
    Overwrite one block runtime-parameter default by symbolic name.

    :param block: Block to modify.
    :param parameter_name: Runtime-parameter variable name.
    :param value: New runtime default.
    :return: None.
    """
    parameter_var: Var
    updated_event_dict: Dict[Var, Const | Expr] = dict()
    found_parameter: bool = False

    for parameter_var, parameter_expr in block.event_dict.items():
        if parameter_var.name == parameter_name:
            updated_event_dict[parameter_var] = Const(float(value))
            found_parameter = True
        else:
            updated_event_dict[parameter_var] = parameter_expr

    if found_parameter:
        block.event_dict = updated_event_dict
    else:
        raise KeyError(f"Runtime parameter '{parameter_name}' was not found in block '{block.name}'")


def _connect_valve_terminals(block: Block, v_source: Var, v_load: Var) -> None:
    """
    Connect one valve block to the source and load bus variables.

    :param block: Valve block to connect.
    :param v_source: Source-side voltage variable.
    :param v_load: Load-side voltage variable.
    :return: None.
    """
    vf_terminal: Var
    vt_terminal: Var

    vf_terminal = block.external_mapping[VarPowerFlowRefferenceType.Vf_dc]
    vt_terminal = block.external_mapping[VarPowerFlowRefferenceType.Vt_dc]
    block.update_model(vf_terminal, v_source)
    block.update_model(vt_terminal, v_load)


def _find_name_in_block(name: str, block: Block) -> Var | None:
    """
    Return one symbolic variable from a block hierarchy by name.

    :param name: Requested symbolic-variable name.
    :param block: Root symbolic block.
    :return: Matching variable or ``None``.
    """
    variable: Var
    child_block: Block
    nested_result: Var | None

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

    for variable in list(block.mode_dict.keys()):
        if variable.name == name:
            return variable
        else:
            pass

    for child_block in block.children:
        nested_result = _find_name_in_block(name, child_block)
        if nested_result is not None:
            return nested_result
        else:
            pass

    return None


def _get_gate_schedule(valve_tpe: ValveEmtType) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return the gate schedule used by one valve case.

    :param valve_tpe: Valve physical type.
    :return: Tuple ``(event_time_s, event_value)``.
    """
    if valve_tpe == ValveEmtType.Diode:
        return np.array([0.0], dtype=float), np.array([0.0], dtype=float)
    else:
        pass

    if valve_tpe == ValveEmtType.Igbt:
        return np.array([0.0, 2.0e-3, 6.0e-3], dtype=float), np.array([0.0, 1.0, 0.0], dtype=float)
    else:
        pass

    if valve_tpe == ValveEmtType.Thyristor:
        return np.array([0.0, 2.0e-3, 2.4e-3], dtype=float), np.array([0.0, 1.0, 0.0], dtype=float)
    else:
        raise ValueError(f"Unsupported valve scripting type '{valve_tpe}'")


def _build_valve_problem(valve_tpe: ValveEmtType) -> Tuple[GenericEmtProblem, int, int, Dict[str, Var]]:
    """
    Build the self-contained EMT valve problem for one valve type.

    The system is a fixed DC source feeding an RC load through the EMT valve block.
    This setup isolates the valve behaviour and keeps the waveform interpretation
    directly tied to the semiconductor state instead of to converter-control side effects.

    :param valve_tpe: Valve physical type.
    :return: Tuple with the EMT problem, the gate index, the retained-mode index and tracked variables.
    """
    vf: VarFactory = VarFactory()
    block_name: str = f'{valve_tpe.value.lower()}_valve_script'
    v_source_ref: float = 1.04
    g_load_value: float
    c_load_value: float
    antiparallel_enabled: bool
    initial_state: ValveInitializationState
    v_source: Var
    v_source_eq: Expr
    v_load: Var
    d_v_load: Var
    g_load: Var
    c_load: Var
    valve_block: Block
    i_branch: Var
    v_valve: Var | None
    root_block: Block
    problem: GenericEmtProblem
    gate_idx: int
    mode_idx: int
    tracked_vars: Dict[str, Var]

    if valve_tpe == ValveEmtType.Igbt:
        # The IGBT case needs a clearly visible post-turn-off discharge window.
        g_load_value = 1.0
        c_load_value = 0.002
        antiparallel_enabled = False
        initial_state = ValveInitializationState.Blocked
    else:
        # Diode and thyristor cases benefit from a slower load capacitor so the natural charging is visible.
        g_load_value = 0.35
        c_load_value = 0.02
        antiparallel_enabled = False
        if valve_tpe == ValveEmtType.Diode:
            initial_state = ValveInitializationState.Blocked
        else:
            initial_state = ValveInitializationState.Blocked

    v_source, v_source_eq = _build_constant_algebraic_var(vf=vf, name=f'v_source_{block_name}', value=v_source_ref)
    v_load = vf.add_var(name=f'v_load_{block_name}')
    d_v_load = vf.add_diff_var(name=f'd_v_load_{block_name}', base_var=v_load)
    g_load = vf.add_var(name=f'g_load_{block_name}')
    c_load = vf.add_var(name=f'c_load_{block_name}')

    valve_block = get_valve_emt_template(
        vf=vf,
        name=block_name,
        valve_tpe=valve_tpe,
        model_variant=ValveEmtModelVariant.Complete,
        initial_state=initial_state,
        antiparallel_diode=antiparallel_enabled,
    ).block

    # The complete variant is regularized with a finite Ron and tiny off-conductance to keep the EMT DAE well posed.
    _set_block_runtime_parameter(valve_block, f'on_resistance_{block_name}', 0.02)
    _set_block_runtime_parameter(valve_block, f'off_conductance_{block_name}', 1.0e-6)
    _set_block_runtime_parameter(valve_block, f'forward_voltage_{block_name}', 0.0)
    _set_block_runtime_parameter(valve_block, f'snubber_enabled_{block_name}', 0.0)
    _connect_valve_terminals(valve_block, v_source=v_source, v_load=v_load)

    i_branch = valve_block.external_mapping[VarPowerFlowRefferenceType.If_dc]
    v_valve = _find_name_in_block(f'v_valve_{block_name}', valve_block)
    if v_valve is None:
        raise KeyError(f"Valve voltage variable for block '{block_name}' could not be resolved")
    else:
        pass

    root_block = Block(
        name=f'ValveStandaloneScript_{valve_tpe.value}',
        children=list([valve_block]),
        algebraic_vars=list([v_source]),
        algebraic_eqs=list([v_source_eq]),
        state_vars=list([v_load]),
        diff_vars=list([d_v_load]),
        state_eqs=list([(i_branch - g_load * v_load) / c_load]),
        parameters=dict([
            (g_load, Const(g_load_value)),
            (c_load, Const(c_load_value)),
        ]),
        init_eqs=dict([
            (v_source, Const(v_source_ref)),
            (v_load, Const(0.0)),
        ]),
    )
    root_block.unify_blocks()

    static_parameter_values_mapping: Dict[Var, Const] = dict(root_block.parameters)
    problem = GenericEmtProblem(
        sys_block=root_block,
        glob_time=vf.add_var(f't_{block_name}'),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    gate_idx = -1
    mode_idx = -1
    for parameter in problem.get_variable_parameters():
        if parameter.name == f'gate_fired_{block_name}':
            gate_idx = int(problem.uid2idx_event_params[parameter.uid])
        else:
            pass

        if parameter.name == f'path_mode_{block_name}':
            mode_idx = int(problem.uid2idx_event_params[parameter.uid])
        else:
            pass

    if gate_idx < 0 or mode_idx < 0:
        raise KeyError(f"Valve runtime indices for '{block_name}' could not be resolved")
    else:
        pass

    tracked_vars = dict([
        ('v_source', v_source),
        ('v_load', v_load),
        ('i_branch', i_branch),
        ('v_valve', v_valve),
    ])
    return problem, gate_idx, mode_idx, tracked_vars


def _create_symbolic_solver(problem: GenericEmtProblem) -> JitSymbolicSolver:
    """
    Create the symbolic EMT solver used by the self-contained valve script.

    :param problem: EMT problem under test.
    :return: Configured symbolic EMT solver.
    """
    return JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=1.0e-2,
        h=1.0e-5,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )


def run_valve_case(valve_tpe: ValveEmtType, enable_plots: bool = False) -> ValveCaseResult:
    """
    Run one self-contained EMT valve scripting case.

    Expected behaviour:

    - ``Diode``: the load-side voltage rises automatically from zero and the retained mode settles at ``+1``.
    - ``IGBT``: the load voltage stays near zero while the gate is low, rises while the gate is high, and then decays after turn-off.
    - ``Thyristor``: a short gate pulse turns the valve on and the retained mode stays at ``+1`` afterwards.

    :param valve_tpe: Valve physical type.
    :param enable_plots: Display matplotlib figures when ``True``.
    :return: Recorded valve-case traces.
    """
    problem: GenericEmtProblem
    gate_idx: int
    mode_idx: int
    tracked_vars: Dict[str, Var]
    base_updater: BoundaryUpdateWrapper | None
    gate_time_s: np.ndarray
    gate_value: np.ndarray
    boundary_updater: GateScheduleBoundaryUpdater
    solver: JitSymbolicSolver
    time_s: np.ndarray
    state_traj: np.ndarray
    _diff_traj: np.ndarray
    result: ValveCaseResult

    problem, gate_idx, mode_idx, tracked_vars = _build_valve_problem(valve_tpe=valve_tpe)
    base_updater = build_boundary_updater_from_block(problem)
    gate_time_s, gate_value = _get_gate_schedule(valve_tpe)
    boundary_updater = GateScheduleBoundaryUpdater(
        base_updater=base_updater,
        gate_param_idx=gate_idx,
        mode_param_idx=mode_idx,
        event_time_s=gate_time_s,
        event_value=gate_value,
        max_records=4000,
    )
    solver = _create_symbolic_solver(problem=problem)
    time_s, state_traj, _diff_traj = solver.simulate(boundary_updater=boundary_updater)

    result = ValveCaseResult(
        time_s=time_s,
        v_source_pu=np.array(state_traj[:, problem.get_var_idx(tracked_vars['v_source'])], copy=True),
        v_load_pu=np.array(state_traj[:, problem.get_var_idx(tracked_vars['v_load'])], copy=True),
        i_branch_pu=np.array(state_traj[:, problem.get_var_idx(tracked_vars['i_branch'])], copy=True),
        v_valve_pu=np.array(state_traj[:, problem.get_var_idx(tracked_vars['v_valve'])], copy=True),
        control_time_s=boundary_updater.get_record_time_s(),
        gate_trace=boundary_updater.get_record_gate(),
        mode_trace=boundary_updater.get_record_mode(),
    )

    print('=' * 72)
    print(f'{valve_tpe.value.upper()} EMT SUMMARY')
    print('=' * 72)
    print(f'Final source voltage    : {result.get_v_source_pu()[-1]: .6f} p.u.')
    print(f'Final load voltage      : {result.get_v_load_pu()[-1]: .6f} p.u.')
    print(f'Final branch current    : {result.get_i_branch_pu()[-1]: .6f} p.u.')
    print(f'Final retained mode     : {result.get_mode_trace()[-1]: .6f}')

    if enable_plots:
        _plot_valve_results(valve_tpe=valve_tpe, result=result)
    else:
        pass

    return result


def _plot_valve_results(valve_tpe: ValveEmtType, result: ValveCaseResult) -> None:
    """
    Plot the EMT valve results.

    :param valve_tpe: Valve physical type.
    :param result: Recorded valve-case traces.
    :return: None.
    """
    time_s: np.ndarray = result.get_time_s()
    control_time_s: np.ndarray = result.get_control_time_s()
    fig, axes = plt.subplots(4, 1, figsize=(13.0, 10.0), sharex=True)

    # The load-bus voltage directly shows whether the valve transfers the source-side energy or not.
    axes[0].plot(time_s, result.get_v_source_pu(), label='V source', color='tab:blue')
    axes[0].plot(time_s, result.get_v_load_pu(), label='V load', color='tab:orange')
    axes[0].set_ylabel('Voltage [p.u.]')
    axes[0].set_title(f'{valve_tpe.value} EMT - Bus Voltages')
    axes[0].grid(True)
    axes[0].legend(loc='best')

    # The electrical-response subplot shows when the branch actually conducts and what voltage it drops.
    axes[1].plot(time_s, result.get_i_branch_pu(), label='I branch', color='tab:green')
    axes[1].plot(time_s, result.get_v_valve_pu(), label='Valve voltage', color='tab:red')
    axes[1].set_ylabel('Current / Voltage [p.u.]')
    axes[1].set_title(f'{valve_tpe.value} EMT - Electrical Response')
    axes[1].grid(True)
    axes[1].legend(loc='best')

    # The gate subplot is flat for the diode, pulsed for the IGBT, and briefly pulsed for the thyristor.
    axes[2].step(control_time_s, result.get_gate_trace(), where='post', label='Gate', color='black')
    axes[2].set_ylabel('Gate [-]')
    axes[2].set_title(f'{valve_tpe.value} EMT - Gate Command')
    axes[2].grid(True)
    axes[2].legend(loc='best')

    # The retained mode highlights the behavioural difference between the three valve types.
    axes[3].step(control_time_s, result.get_mode_trace(), where='post', label='Path mode', color='tab:purple')
    axes[3].set_xlabel('Time [s]')
    axes[3].set_ylabel('Mode [-]')
    axes[3].set_title(f'{valve_tpe.value} EMT - Retained Conduction Mode')
    axes[3].grid(True)
    axes[3].legend(loc='best')

    fig.tight_layout()
    plt.show()


def main() -> None:
    """
    Run all EMT valve scripting cases.

    :return: None.
    """
    valve_tpe: ValveEmtType

    for valve_tpe in [ValveEmtType.Diode, ValveEmtType.Igbt, ValveEmtType.Thyristor]:
        run_valve_case(valve_tpe=valve_tpe, enable_plots=True)


if __name__ == '__main__':
    main()
