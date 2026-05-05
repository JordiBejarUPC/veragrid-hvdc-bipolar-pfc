# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper, JitSymbolicSolver
from VeraGridEngine.Templates.Emt.dc_line_emt_template import get_dc_line_emt_template
from VeraGridEngine.Templates.Emt.valve_emt_template import get_valve_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    ValveEmtModelVariant,
    ValveEmtType,
    ValveInitializationState,
    VarPowerFlowRefferenceType,
)


class GenericEmtProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by the standalone DC branch demos.
    """

    __slots__ = []


class DcLineDemoResult:
    """
    Store the traces produced by the DC line EMT demo.
    """

    __slots__ = [
        "_time_s",
        "_v_source_pu",
        "_v_load_pu",
        "_i_branch_pu",
        "_p_source_pu",
        "_p_load_pu",
        "_g_load_time_s",
        "_g_load_trace",
    ]

    def __init__(
            self,
            time_s: np.ndarray,
            v_source_pu: np.ndarray,
            v_load_pu: np.ndarray,
            i_branch_pu: np.ndarray,
            p_source_pu: np.ndarray,
            p_load_pu: np.ndarray,
            g_load_time_s: np.ndarray,
            g_load_trace: np.ndarray,
    ) -> None:
        """
        Build one DC line demo result container.

        :param time_s: EMT time vector.
        :param v_source_pu: Source-side voltage trace.
        :param v_load_pu: Load-side voltage trace.
        :param i_branch_pu: Branch-current trace.
        :param p_source_pu: Source-side power trace.
        :param p_load_pu: Load-side power trace.
        :param g_load_time_s: Time vector of the applied load-conductance step.
        :param g_load_trace: Applied load-conductance trace.
        :return: None.
        """
        self._time_s = np.array(time_s, copy=True)
        self._v_source_pu = np.array(v_source_pu, copy=True)
        self._v_load_pu = np.array(v_load_pu, copy=True)
        self._i_branch_pu = np.array(i_branch_pu, copy=True)
        self._p_source_pu = np.array(p_source_pu, copy=True)
        self._p_load_pu = np.array(p_load_pu, copy=True)
        self._g_load_time_s = np.array(g_load_time_s, copy=True)
        self._g_load_trace = np.array(g_load_trace, copy=True)

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

    def get_p_source_pu(self) -> np.ndarray:
        """
        Return the source-side power trace.

        :return: Source-side power trace.
        """
        return np.array(self._p_source_pu, copy=True)

    def get_p_load_pu(self) -> np.ndarray:
        """
        Return the load-side power trace.

        :return: Load-side power trace.
        """
        return np.array(self._p_load_pu, copy=True)

    def get_g_load_time_s(self) -> np.ndarray:
        """
        Return the time vector of the applied load-conductance step.

        :return: Load-step time vector.
        """
        return np.array(self._g_load_time_s, copy=True)

    def get_g_load_trace(self) -> np.ndarray:
        """
        Return the applied load-conductance trace.

        :return: Load-conductance trace.
        """
        return np.array(self._g_load_trace, copy=True)


class ValveDemoResult:
    """
    Store the traces produced by one EMT valve demo case.
    """

    __slots__ = [
        "_time_s",
        "_v_source_pu",
        "_v_load_pu",
        "_i_branch_pu",
        "_v_valve_pu",
        "_control_time_s",
        "_gate_trace",
        "_mode_trace",
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
        Build one valve demo result container.

        :param time_s: EMT time vector.
        :param v_source_pu: Source-side voltage trace.
        :param v_load_pu: Load-side voltage trace.
        :param i_branch_pu: Branch-current trace.
        :param v_valve_pu: Valve-voltage trace.
        :param control_time_s: Time vector of the gate/mode records.
        :param gate_trace: Gate-command trace.
        :param mode_trace: Retained mode trace.
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
        Return the time vector of the gate/mode records.

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
        Return the retained mode trace.

        :return: Retained mode trace.
        """
        return np.array(self._mode_trace, copy=True)


class ParameterScheduleWrapper(BoundaryUpdateWrapper):
    """
    Apply one piecewise-constant parameter schedule and optionally delegate to a base updater.
    """

    __slots__ = [
        "_param_idx",
        "_event_time_s",
        "_event_value",
        "_base_updater",
        "_record_time_s",
        "_record_value",
        "_record_aux_idx",
        "_record_aux",
        "_record_count",
    ]

    def __init__(
            self,
            param_idx: int,
            event_time_s: np.ndarray,
            event_value: np.ndarray,
            max_records: int,
            base_updater: BoundaryUpdateWrapper | None = None,
            record_aux_idx: int | None = None,
    ) -> None:
        """
        Build one scheduled-parameter boundary updater.

        :param param_idx: Full-parameter-vector index of the scheduled parameter.
        :param event_time_s: Sorted event times.
        :param event_value: Piecewise-constant values associated with the event times.
        :param max_records: Maximum number of stored samples.
        :param base_updater: Optional base updater invoked after the parameter write.
        :param record_aux_idx: Optional full-parameter-vector index recorded alongside the schedule.
        :return: None.
        """
        self._param_idx = int(param_idx)
        self._event_time_s = np.array(event_time_s, copy=True)
        self._event_value = np.array(event_value, copy=True)
        self._base_updater = base_updater
        self._record_time_s = np.zeros(max_records, dtype=float)
        self._record_value = np.zeros(max_records, dtype=float)
        self._record_aux_idx = record_aux_idx
        self._record_aux = np.zeros(max_records, dtype=float)
        self._record_count = 0

    def _get_scheduled_value(self, time_s: float) -> float:
        """
        Return the scheduled parameter value at one time instant.

        :param time_s: Current simulation time.
        :return: Scheduled parameter value.
        """
        event_idx: int = 0
        value: float = float(self._event_value[0])

        while event_idx < len(self._event_time_s):
            if time_s >= float(self._event_time_s[event_idx]):
                value = float(self._event_value[event_idx])
            else:
                pass
            event_idx += 1

        return value

    def _get_next_local_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Return the next scheduled event time inside ``(t_prev, t_target]``.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest local event time or ``None``.
        """
        event_idx: int = 0

        while event_idx < len(self._event_time_s):
            event_time: float = float(self._event_time_s[event_idx])
            if t_prev < event_time <= t_target:
                return event_time
            else:
                pass
            event_idx += 1

        return None

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Apply the scheduled parameter value and then invoke the optional base updater.

        :param t: Current simulation time.
        :param x: Accepted EMT state vector.
        :param params: Full parameter vector.
        :return: None.
        """
        scheduled_value: float = self._get_scheduled_value(float(t))

        # The scheduled value is written before the delegated updater runs so the downstream
        # procedural logic sees the latest command or load step inside the same accepted step.
        params[self._param_idx] = scheduled_value

        if self._base_updater is not None:
            self._base_updater.update(float(t), x, params)
        else:
            pass

        if self._record_count < len(self._record_time_s):
            self._record_time_s[self._record_count] = float(t)
            self._record_value[self._record_count] = scheduled_value
            if self._record_aux_idx is not None:
                self._record_aux[self._record_count] = float(params[self._record_aux_idx])
            else:
                self._record_aux[self._record_count] = 0.0
            self._record_count += 1
        else:
            pass

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Return the earliest forced event from the local schedule or the delegated updater.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest forced event time or ``None``.
        """
        local_time: float | None = self._get_next_local_event_time(float(t_prev), float(t_target))

        if self._base_updater is None:
            base_time: float | None = None
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
        Return the recorded time vector.

        :return: Recorded time vector.
        """
        return np.array(self._record_time_s[:self._record_count], copy=True)

    def get_record_value(self) -> np.ndarray:
        """
        Return the recorded scheduled-value trace.

        :return: Recorded scheduled-value trace.
        """
        return np.array(self._record_value[:self._record_count], copy=True)

    def get_record_aux(self) -> np.ndarray:
        """
        Return the recorded auxiliary trace.

        :return: Recorded auxiliary trace.
        """
        return np.array(self._record_aux[:self._record_count], copy=True)


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


def _set_block_constant_parameter(block: Block, parameter_name: str, value: float) -> None:
    """
    Overwrite one block constant parameter by symbolic name.

    :param block: Block to modify.
    :param parameter_name: Constant-parameter variable name.
    :param value: New constant value.
    :return: None.
    """
    parameter_var: Var
    updated_parameters: Dict[Var, Const] = dict()
    found_parameter: bool = False

    for parameter_var, parameter_value in block.parameters.items():
        if parameter_var.name == parameter_name:
            updated_parameters[parameter_var] = Const(float(value))
            found_parameter = True
        else:
            updated_parameters[parameter_var] = parameter_value

    if found_parameter:
        block.parameters = updated_parameters
    else:
        raise KeyError(f"Constant parameter '{parameter_name}' was not found in block '{block.name}'")


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


def _connect_dc_branch_terminals(branch_block: Block, v_source: Var, v_load: Var) -> None:
    """
    Connect one DC branch block to the source and load bus variables.

    :param branch_block: Branch block to connect.
    :param v_source: Source-side voltage variable.
    :param v_load: Load-side voltage variable.
    :return: None.
    """
    vf_terminal: Var = branch_block.external_mapping[VarPowerFlowRefferenceType.Vf_dc]
    vt_terminal: Var = branch_block.external_mapping[VarPowerFlowRefferenceType.Vt_dc]

    branch_block.update_model(vf_terminal, v_source)
    branch_block.update_model(vt_terminal, v_load)


def find_var_in_block_by_name(name: str, block: Block) -> Var | None:
    """
    Return the symbolic variable with the requested name from one block hierarchy.

    :param name: Requested symbolic-variable name.
    :param block: Root symbolic block.
    :return: Matching symbolic variable or ``None``.
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
        nested_result = find_var_in_block_by_name(name, child_block)
        if nested_result is not None:
            return nested_result
        else:
            pass

    return None


def _get_constant_parameter_full_index(problem: GenericEmtProblem, parameter_name: str) -> int:
    """
    Return the full-parameter-vector index of one constant parameter.

    :param problem: EMT problem under inspection.
    :param parameter_name: Constant-parameter symbolic name.
    :return: Full-parameter-vector index.
    """
    parameter: Var
    runtime_parameter_count: int = problem.get_variable_parameter_number()

    for parameter in problem.get_constant_parameters():
        if parameter.name == parameter_name:
            return int(runtime_parameter_count + problem.uid2idx_params[parameter.uid])
        else:
            pass

    raise KeyError(f"Constant parameter '{parameter_name}' was not found")


def get_runtime_parameter_index(problem: GenericEmtProblem, parameter_name: str) -> int:
    """
    Return the runtime-parameter index associated with one symbolic name.

    :param problem: EMT problem under inspection.
    :param parameter_name: Runtime-parameter symbolic name.
    :return: Runtime-parameter index.
    """
    parameter: Var

    for parameter in problem.get_variable_parameters():
        if parameter.name == parameter_name:
            return int(problem.uid2idx_event_params[parameter.uid])
        else:
            pass

    raise KeyError(f"Runtime parameter '{parameter_name}' was not found")


def extract_trace(problem: GenericEmtProblem, trajectory: np.ndarray, variable: Var) -> np.ndarray:
    """
    Extract one variable trace from the EMT trajectory.

    :param problem: EMT problem under inspection.
    :param trajectory: Solver state trajectory.
    :param variable: Symbolic variable to extract.
    :return: Extracted trace.
    """
    return np.array(trajectory[:, problem.get_var_idx(variable)], copy=True)


def create_symbolic_solver(problem: GenericEmtProblem, t_end: float, h: float) -> JitSymbolicSolver:
    """
    Create the symbolic EMT solver used by the standalone branch demos.

    :param problem: EMT problem.
    :param t_end: Final simulation time.
    :param h: Fixed EMT time step.
    :return: Configured symbolic solver.
    """
    return JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=float(t_end),
        h=float(h),
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )


def _compute_resistive_divider_voltage(v_source: float, g_branch: float, g_load: float) -> float:
    """
    Return the steady-state load voltage of one resistive source-branch-load divider.

    :param v_source: Source voltage in p.u.
    :param g_branch: Branch conductance in p.u.
    :param g_load: Load conductance in p.u.
    :return: Steady-state load voltage in p.u.
    """
    return float(v_source * g_branch / (g_branch + g_load))


def _build_load_capacitor_state_equation(branch_current: Var, g_load: Var, v_load: Var, c_load: Var) -> Expr:
    """
    Build the load-capacitor state equation shared by the DC branch demos.

    :param branch_current: Branch current entering the load node.
    :param g_load: Load conductance.
    :param v_load: Load-side voltage.
    :param c_load: Load-side capacitance.
    :return: Load-capacitor state equation.
    """
    return (branch_current - g_load * v_load) / c_load


def build_dc_line_demo_problem() -> Tuple[GenericEmtProblem, DcLineDemoResult, int, Dict[str, Var]]:
    """
    Build the standalone EMT problem used by the DC line demo.

    The system is a fixed DC source feeding one RC load through the EMT DC-line block.
    The load conductance is stepped during the simulation so the line current and the
    load voltage show a clear first-order transient.

    :return: Tuple with the EMT problem, an empty result container placeholder, the load-step parameter index and tracked variables.
    """
    vf: VarFactory = VarFactory()
    block_name: str = "dc_line_demo"
    v_source_ref: float = 1.04
    r_branch: float = 0.08
    g_branch: float = 1.0 / r_branch
    g_load_initial: float = 0.25
    c_load_value: float = 0.05

    v_source: Var
    v_source_eq: Expr
    v_source, v_source_eq = _build_constant_algebraic_var(vf=vf, name="v_source_demo", value=v_source_ref)

    v_load: Var = vf.add_var(name="v_load_demo")
    d_v_load: Var = vf.add_diff_var(name="d_v_load_demo", base_var=v_load)
    g_load: Var = vf.add_var(name="g_load_demo")
    c_load: Var = vf.add_var(name="c_load_demo")

    line_block: Block = get_dc_line_emt_template(vf=vf, name=block_name).block
    _set_block_constant_parameter(line_block, f"g_ser_{block_name}", g_branch)
    _connect_dc_branch_terminals(line_block, v_source=v_source, v_load=v_load)

    i_branch: Var = line_block.external_mapping[VarPowerFlowRefferenceType.If_dc]
    p_source: Var = line_block.external_mapping[VarPowerFlowRefferenceType.Pf]
    p_load: Var = line_block.external_mapping[VarPowerFlowRefferenceType.Pt]

    v_load_initial: float = _compute_resistive_divider_voltage(v_source=v_source_ref, g_branch=g_branch, g_load=g_load_initial)

    root_block: Block = Block(
        name="DcLineStandaloneDemo",
        children=list([line_block]),
        algebraic_vars=list([v_source]),
        algebraic_eqs=list([v_source_eq]),
        state_vars=list([v_load]),
        diff_vars=list([d_v_load]),
        state_eqs=list([
            _build_load_capacitor_state_equation(branch_current=i_branch, g_load=g_load, v_load=v_load, c_load=c_load),
        ]),
        parameters=dict([
            (c_load, Const(c_load_value)),
        ]),
        event_dict=dict([
            (g_load, Const(g_load_initial)),
        ]),
        init_eqs=dict([
            (v_source, Const(v_source_ref)),
            (v_load, Const(v_load_initial)),
        ]),
    )
    root_block.unify_blocks()

    static_parameter_values_mapping: Dict[Var, Const] = dict(root_block.parameters)
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=root_block,
        glob_time=vf.add_var("t_dc_line_demo"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    tracked_vars: Dict[str, Var] = dict([
        ("v_source", v_source),
        ("v_load", v_load),
        ("i_branch", i_branch),
        ("p_source", p_source),
        ("p_load", p_load),
    ])

    load_step_idx: int = get_runtime_parameter_index(problem, "g_load_demo")
    empty_result: DcLineDemoResult = DcLineDemoResult(
        time_s=np.zeros(0, dtype=float),
        v_source_pu=np.zeros(0, dtype=float),
        v_load_pu=np.zeros(0, dtype=float),
        i_branch_pu=np.zeros(0, dtype=float),
        p_source_pu=np.zeros(0, dtype=float),
        p_load_pu=np.zeros(0, dtype=float),
        g_load_time_s=np.zeros(0, dtype=float),
        g_load_trace=np.zeros(0, dtype=float),
    )
    return problem, empty_result, load_step_idx, tracked_vars


def get_default_gate_schedule(valve_tpe: ValveEmtType) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return the default gate schedule used by the standalone EMT valve demos.

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
        raise ValueError(f"Unsupported valve demo type {valve_tpe}")


def build_valve_demo_problem(valve_tpe: ValveEmtType) -> Tuple[GenericEmtProblem, ValveDemoResult, int, int, Dict[str, Var]]:
    """
    Build the standalone EMT problem used by one valve demo case.

    The system is a fixed DC source feeding one RC load through the EMT valve block.
    This setup makes the conduction state directly observable in the load voltage and
    in the branch current without the extra dynamics of a full AC/DC converter.

    :param valve_tpe: Valve physical type.
    :return: Tuple with the EMT problem, an empty result placeholder, the gate-parameter index, the retained-mode index and tracked variables.
    """
    vf: VarFactory = VarFactory()
    block_name: str = f"{valve_tpe.value.lower()}_valve_demo"
    v_source_ref: float = 1.04
    g_load_value: float
    c_load_value: float

    if valve_tpe == ValveEmtType.Igbt:
        # The IGBT demo needs a visibly faster discharge after the gate returns to zero.
        g_load_value = 1.0
        c_load_value = 0.002
    else:
        # Diode and thyristor demos benefit from a slower capacitor so their natural charging behaviour is visible.
        g_load_value = 0.35
        c_load_value = 0.02

    v_source: Var
    v_source_eq: Expr
    v_source, v_source_eq = _build_constant_algebraic_var(vf=vf, name=f"v_source_{block_name}", value=v_source_ref)

    v_load: Var = vf.add_var(name=f"v_load_{block_name}")
    d_v_load: Var = vf.add_diff_var(name=f"d_v_load_{block_name}", base_var=v_load)
    g_load: Var = vf.add_var(name=f"g_load_{block_name}")
    c_load: Var = vf.add_var(name=f"c_load_{block_name}")

    antiparallel_enabled: bool
    if valve_tpe == ValveEmtType.Igbt:
        antiparallel_enabled = False
    else:
        antiparallel_enabled = False

    valve_block: Block = get_valve_emt_template(
        vf=vf,
        name=block_name,
        valve_tpe=valve_tpe,
        model_variant=ValveEmtModelVariant.Complete,
        initial_state=ValveInitializationState.Blocked,
        antiparallel_diode=antiparallel_enabled,
    ).block
    _set_block_runtime_parameter(valve_block, f"on_resistance_{block_name}", 0.02)
    _set_block_runtime_parameter(valve_block, f"off_conductance_{block_name}", 1.0e-6)
    _set_block_runtime_parameter(valve_block, f"forward_voltage_{block_name}", 0.0)
    _set_block_runtime_parameter(valve_block, f"snubber_enabled_{block_name}", 0.0)
    _connect_dc_branch_terminals(valve_block, v_source=v_source, v_load=v_load)

    i_branch: Var = valve_block.external_mapping[VarPowerFlowRefferenceType.If_dc]
    v_valve: Var | None = find_var_in_block_by_name(f"v_valve_{block_name}", valve_block)
    if v_valve is None:
        raise KeyError(f"Valve voltage variable for block '{block_name}' was not found")
    else:
        pass

    root_block: Block = Block(
        name=f"ValveStandaloneDemo_{valve_tpe.value}",
        children=list([valve_block]),
        algebraic_vars=list([v_source]),
        algebraic_eqs=list([v_source_eq]),
        state_vars=list([v_load]),
        diff_vars=list([d_v_load]),
        state_eqs=list([
            _build_load_capacitor_state_equation(branch_current=i_branch, g_load=g_load, v_load=v_load, c_load=c_load),
        ]),
        parameters=dict([
            (c_load, Const(c_load_value)),
            (g_load, Const(g_load_value)),
        ]),
        init_eqs=dict([
            (v_source, Const(v_source_ref)),
            (v_load, Const(0.0)),
        ]),
    )
    root_block.unify_blocks()

    static_parameter_values_mapping: Dict[Var, Const] = dict(root_block.parameters)
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=root_block,
        glob_time=vf.add_var(f"t_{block_name}"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    tracked_vars: Dict[str, Var] = dict([
        ("v_source", v_source),
        ("v_load", v_load),
        ("i_branch", i_branch),
        ("v_valve", v_valve),
    ])

    gate_idx: int = get_runtime_parameter_index(problem, f"gate_fired_{block_name}")
    mode_idx: int = get_runtime_parameter_index(problem, f"path_mode_{block_name}")
    empty_result: ValveDemoResult = ValveDemoResult(
        time_s=np.zeros(0, dtype=float),
        v_source_pu=np.zeros(0, dtype=float),
        v_load_pu=np.zeros(0, dtype=float),
        i_branch_pu=np.zeros(0, dtype=float),
        v_valve_pu=np.zeros(0, dtype=float),
        control_time_s=np.zeros(0, dtype=float),
        gate_trace=np.zeros(0, dtype=float),
        mode_trace=np.zeros(0, dtype=float),
    )
    return problem, empty_result, gate_idx, mode_idx, tracked_vars


def build_valve_demo_boundary_updater(problem: GenericEmtProblem, gate_idx: int, mode_idx: int,
                                      valve_tpe: ValveEmtType) -> ParameterScheduleWrapper:
    """
    Build the gate-schedule updater used by one valve demo case.

    :param problem: Valve EMT problem.
    :param gate_idx: Runtime index of the gate parameter.
    :param mode_idx: Runtime index of the retained valve mode.
    :param valve_tpe: Valve physical type.
    :return: Gate-schedule updater.
    """
    base_updater: BoundaryUpdateWrapper | None = build_boundary_updater_from_block(problem)
    event_time_s: np.ndarray
    event_value: np.ndarray
    event_time_s, event_value = get_default_gate_schedule(valve_tpe)

    return ParameterScheduleWrapper(
        param_idx=gate_idx,
        event_time_s=event_time_s,
        event_value=event_value,
        max_records=5000,
        base_updater=base_updater,
        record_aux_idx=mode_idx,
    )


def build_dc_line_demo_boundary_updater(load_param_idx: int) -> ParameterScheduleWrapper:
    """
    Build the load-step updater used by the DC line demo.

    :param load_param_idx: Runtime index of the load conductance parameter.
    :return: Load-step updater.
    """
    return ParameterScheduleWrapper(
        param_idx=load_param_idx,
        event_time_s=np.array([0.0, 5.0e-3], dtype=float),
        event_value=np.array([0.25, 0.55], dtype=float),
        max_records=5000,
        base_updater=None,
        record_aux_idx=None,
    )
