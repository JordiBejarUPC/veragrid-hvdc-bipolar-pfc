# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp, Comparison, Const, Expr, Var, _dict_to_expr, _expr_to_dict
from VeraGridEngine.basic_structures import Vec


def _expr_like_to_dict(expr: Expr | Comparison) -> Dict[str, Any]:
    if isinstance(expr, Comparison):
        rhs = expr.rhs
        return {
            "kind": "Comparison",
            "lhs": _expr_to_dict(expr.lhs),
            "op": expr.op.value,
            "rhs": _expr_to_dict(rhs) if isinstance(rhs, Expr) else rhs,
            "rhs_is_expr": isinstance(rhs, Expr),
        }
    return {
        "kind": "Expr",
        "expr": _expr_to_dict(expr),
    }


def _expr_like_from_dict(data: Dict[str, Any]) -> Expr | Comparison:
    kind = str(data.get("kind", "Expr"))
    if kind == "Expr":
        return _dict_to_expr(data["expr"])

    if kind == "Comparison":
        rhs_raw = data["rhs"]
        rhs = _dict_to_expr(rhs_raw) if bool(data.get("rhs_is_expr", False)) else rhs_raw
        op_text = str(data["op"])

        return Comparison(
            lhs=_dict_to_expr(data["lhs"]),
            op=CmpOp(op_text),
            rhs=rhs,
        )

    raise ValueError(f"Unsupported procedural expression kind '{kind}'")


def _subs_expr_like(expr: Expr | Comparison, mapping: Dict[Any, Expr]) -> Expr | Comparison:
    if isinstance(expr, Comparison):
        rhs = expr.rhs.subs(mapping) if isinstance(expr.rhs, Expr) else expr.rhs
        return Comparison(lhs=expr.lhs.subs(mapping), op=expr.op, rhs=rhs)
    return expr.subs(mapping)


def _build_name_mapping(var_mapping: Dict[Any, Expr]) -> Dict[str, str]:
    mapping: Dict[str, str] = dict()
    for old, new in var_mapping.items():
        if isinstance(old, Var) and isinstance(new, Var):
            mapping[old.name] = new.name
        elif isinstance(old, str) and isinstance(new, Var):
            mapping[old] = new.name
    return mapping


def _coerce_var_name(var_or_name: Var | str) -> str:
    if isinstance(var_or_name, Var):
        return var_or_name.name
    return str(var_or_name)


def _bool_expr(expr: Expr | Comparison | float | int) -> Expr:
    if isinstance(expr, Comparison):
        return expr.to_expression()
    if isinstance(expr, Expr):
        return expr
    return Const(float(expr))


def _value_expr(expr: Expr | Comparison | float | int) -> Expr:
    if isinstance(expr, Comparison):
        return expr.to_expression()
    if isinstance(expr, Expr):
        return expr
    return Const(float(expr))


def bool_and(*args: Expr | Comparison | float | int) -> Expr:
    if len(args) == 0:
        return Const(1.0)

    result = _bool_expr(args[0])
    for arg in args[1:]:
        result = result * _bool_expr(arg)
    return result


def bool_or(*args: Expr | Comparison | float | int) -> Expr:
    if len(args) == 0:
        return Const(0.0)

    result = _bool_expr(args[0])
    for arg in args[1:]:
        arg_expr = _bool_expr(arg)
        result = Const(1.0) - (Const(1.0) - result) * (Const(1.0) - arg_expr)
    return result


def bool_not(arg: Expr | Comparison | float | int) -> Expr:
    return Const(1.0) - _bool_expr(arg)


def bool_nand(*args: Expr | Comparison | float | int) -> Expr:
    return bool_not(bool_and(*args))


def bool_nor(*args: Expr | Comparison | float | int) -> Expr:
    return bool_not(bool_or(*args))


def bool_eor(left: Expr | Comparison | float | int, right: Expr | Comparison | float | int) -> Expr:
    left_expr = _bool_expr(left)
    right_expr = _bool_expr(right)
    return left_expr + right_expr - Const(2.0) * left_expr * right_expr


def select(
    boolexpr: Expr | Comparison | float | int,
    when_true: Expr | Comparison | float | int,
    when_false: Expr | Comparison | float | int,
) -> Expr:
    _unused = (boolexpr, when_true, when_false)
    raise RuntimeError(
        "`select()` is blocked in equation expressions. Move the switching decision to "
        "`block.procedural_logic` and consume the resulting mode/flag inside the equations."
    )


def ifelse(
    boolexpr: Expr | Comparison | float | int,
    when_true: Expr | Comparison | float | int,
    when_false: Expr | Comparison | float | int,
) -> Expr:
    _unused = (boolexpr, when_true, when_false)
    raise RuntimeError(
        "`ifelse()` is blocked in equation expressions. Move the switching decision to "
        "`block.procedural_logic` and consume the resulting mode/flag inside the equations."
    )


class ProceduralLogicBase:
    """
    Base class for procedural logic objects attached to symbolic blocks.

    Procedural logic is evaluated outside the compiled residual kernels and is intended
    to drive runtime modes, retained flags, timers, or event scheduling in a structured way.
    """

    __slots__ = ["name", "_problem", "_sample_time"]
    logic_type = "base"

    def __init__(self, name: str = "") -> None:
        self.name = name
        self._problem: Optional[EmtProblemTemplate] = None
        self._sample_time: Optional[float] = None

    def bind(self, problem: EmtProblemTemplate) -> None:
        """
        Bind the logic to a concrete EMT problem.

        :param problem: EMT problem owning the block and variable maps.
        :return: None
        """
        self._problem = problem
        self._sample_time = None

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Update mode or event parameters before the Newton step.

        :param t: Current solver time.
        :param x: Current accepted state.
        :param params: Runtime parameter vector to mutate in place.
        :return: None
        """
        _unused = (t, x, params)

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return the next exact event time inside the interval if known.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Event time or None.
        """
        self._sample_time = float(t_prev)
        _unused = t_target
        return None

    def remap(self, var_mapping: Dict[Any, Expr]) -> "ProceduralLogicBase":
        _unused = var_mapping
        return build_procedural_logic_entry(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize static configuration.

        :return: Dictionary representation.
        """
        return {
            "logic_type": self.logic_type,
            "name": self.name,
        }

    def _get_problem(self) -> EmtProblemTemplate:
        if self._problem is None:
            raise RuntimeError("Procedural logic must be bound to an EMT problem before runtime evaluation")
        return self._problem

    def _get_sample_time(self, t: float) -> float:
        return float(t if self._sample_time is None else self._sample_time)

    def _eval_numeric(self, expr: Expr | Comparison, t: float, x: Vec, params: Vec) -> float:
        problem = self._get_problem()
        sample_time = self._get_sample_time(t)

        if isinstance(expr, (float, int)):
            return float(expr)

        expr_eval: Expr = expr.to_expression() if isinstance(expr, Comparison) else expr

        if isinstance(expr_eval, Const):
            return 0.0 if expr_eval.value is None else float(expr_eval.value)

        if isinstance(expr_eval, Var):
            if expr_eval.name in {"time", "glob_time"}:
                return sample_time

            idx_var = problem.uid2idx_vars.get(expr_eval.uid, None)
            if idx_var is not None:
                return float(x[idx_var])

            idx_runtime = problem.uid2idx_event_params.get(expr_eval.uid, None)
            if idx_runtime is not None:
                return float(params[idx_runtime])

            idx_const = problem.uid2idx_params.get(expr_eval.uid, None)
            if idx_const is not None:
                n_runtime = problem.get_variable_parameter_number()
                if len(params) >= n_runtime + len(problem.get_parameters_values()):
                    return float(params[n_runtime + idx_const])
                return float(problem.get_parameters_values()[idx_const].value)

            raise KeyError(f"Unknown procedural variable '{expr_eval.name}'")

        uid_bindings: Dict[int, float] = dict()
        for uid, idx in problem.uid2idx_vars.items():
            uid_bindings[uid] = float(x[idx])

        for uid, idx in problem.uid2idx_event_params.items():
            uid_bindings[uid] = float(params[idx])

        n_runtime = problem.get_variable_parameter_number()
        const_values = problem.get_parameters_values()
        params_has_consts = len(params) >= n_runtime + len(const_values)
        for uid, idx in problem.uid2idx_params.items():
            if params_has_consts:
                uid_bindings[uid] = float(params[n_runtime + idx])
            else:
                uid_bindings[uid] = float(const_values[idx].value)

        uid_bindings[problem.glob_time.uid] = sample_time
        for var in expr_eval.get_vars():
            if var.name in {"time", "glob_time"}:
                uid_bindings[var.uid] = sample_time

        return float(expr_eval.eval_uid(uid_bindings))

    def _eval_bool(self, expr: Expr | Comparison, t: float, x: Vec, params: Vec) -> bool:
        return self._eval_numeric(expr, t, x, params) > 0.5


class FixedSampleLogic(ProceduralLogicBase):
    __slots__ = ["output_var_name", "condition_expr", "output_idx", "initialized"]
    logic_type = "fixed_sample"

    def __init__(self, output_var_name: str, condition_expr: Expr | Comparison, name: str = "") -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.condition_expr = condition_expr
        self.output_idx = -1
        self.initialized = False

    def bind(self, problem: EmtProblemTemplate) -> None:
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.initialized = False

    def update(self, t: float, x: Vec, params: Vec) -> None:
        if self.initialized:
            return

        params[self.output_idx] = 1.0 if self._eval_bool(self.condition_expr, t, x, params) else 0.0
        self.initialized = True

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "output_var_name": self.output_var_name,
            "condition_expr": _expr_like_to_dict(self.condition_expr),
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FixedSampleLogic":
        return cls(
            output_var_name=str(data["output_var_name"]),
            condition_expr=_expr_like_from_dict(data["condition_expr"]),
            name=str(data.get("name", "")),
        )

    def remap(self, var_mapping: Dict[Any, Expr]) -> "FixedSampleLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return FixedSampleLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            condition_expr=_subs_expr_like(self.condition_expr, var_mapping),
            name=self.name,
        )


class SampledValueLogic(ProceduralLogicBase):
    __slots__ = ["output_var_name", "source_expr", "output_idx"]
    logic_type = "sampled_value"

    def __init__(self, output_var_name: str, source_expr: Expr | Comparison, name: str = "") -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.source_expr = source_expr
        self.output_idx = -1

    def bind(self, problem: EmtProblemTemplate) -> None:
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])

    def update(self, t: float, x: Vec, params: Vec) -> None:
        params[self.output_idx] = self._eval_numeric(self.source_expr, t, x, params)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "output_var_name": self.output_var_name,
            "source_expr": _expr_like_to_dict(self.source_expr),
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SampledValueLogic":
        return cls(
            output_var_name=str(data["output_var_name"]),
            source_expr=_expr_like_from_dict(data["source_expr"]),
            name=str(data.get("name", "")),
        )

    def remap(self, var_mapping: Dict[Any, Expr]) -> "SampledValueLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return SampledValueLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            source_expr=_subs_expr_like(self.source_expr, var_mapping),
            name=self.name,
        )


class FlipFlopLogic(ProceduralLogicBase):
    __slots__ = ["output_var_name", "set_expr", "reset_expr", "output_idx", "state", "initialized"]
    logic_type = "flipflop"

    def __init__(
        self,
        output_var_name: str,
        set_expr: Expr | Comparison,
        reset_expr: Expr | Comparison,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.set_expr = set_expr
        self.reset_expr = reset_expr
        self.output_idx = -1
        self.state = 0.0
        self.initialized = False

    def bind(self, problem: EmtProblemTemplate) -> None:
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.state = 0.0
        self.initialized = False

    def update(self, t: float, x: Vec, params: Vec) -> None:
        set_on = self._eval_bool(self.set_expr, t, x, params)
        reset_on = self._eval_bool(self.reset_expr, t, x, params)

        if not self.initialized:
            if set_on and reset_on:
                raise ValueError(f"flipflop '{self.name or self.output_var_name}' cannot initialize with set=1 and reset=1")
            self.state = 1.0 if set_on else 0.0
            self.initialized = True
        elif set_on and not reset_on:
            self.state = 1.0
        elif (not set_on) and reset_on:
            self.state = 0.0

        params[self.output_idx] = self.state

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "output_var_name": self.output_var_name,
            "set_expr": _expr_like_to_dict(self.set_expr),
            "reset_expr": _expr_like_to_dict(self.reset_expr),
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlipFlopLogic":
        return cls(
            output_var_name=str(data["output_var_name"]),
            set_expr=_expr_like_from_dict(data["set_expr"]),
            reset_expr=_expr_like_from_dict(data["reset_expr"]),
            name=str(data.get("name", "")),
        )

    def remap(self, var_mapping: Dict[Any, Expr]) -> "FlipFlopLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return FlipFlopLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            set_expr=_subs_expr_like(self.set_expr, var_mapping),
            reset_expr=_subs_expr_like(self.reset_expr, var_mapping),
            name=self.name,
        )


class AnalogFlipFlopLogic(ProceduralLogicBase):
    __slots__ = [
        "output_var_name",
        "input_expr",
        "set_expr",
        "reset_expr",
        "output_idx",
        "state",
        "initialized",
        "held_value",
    ]
    logic_type = "analog_flipflop"

    def __init__(
        self,
        output_var_name: str,
        input_expr: Expr | Comparison,
        set_expr: Expr | Comparison,
        reset_expr: Expr | Comparison,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.input_expr = input_expr
        self.set_expr = set_expr
        self.reset_expr = reset_expr
        self.output_idx = -1
        self.state = 0.0
        self.initialized = False
        self.held_value = 0.0

    def bind(self, problem: EmtProblemTemplate) -> None:
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.state = 0.0
        self.initialized = False
        self.held_value = 0.0

    def update(self, t: float, x: Vec, params: Vec) -> None:
        input_value = self._eval_numeric(self.input_expr, t, x, params)
        set_on = self._eval_bool(self.set_expr, t, x, params)
        reset_on = self._eval_bool(self.reset_expr, t, x, params)

        if not self.initialized:
            if set_on and reset_on:
                raise ValueError(f"aflipflop '{self.name or self.output_var_name}' cannot initialize with set=1 and reset=1")
            self.state = 1.0 if set_on else 0.0
            self.held_value = input_value
            self.initialized = True
        elif set_on and not reset_on and self.state < 0.5:
            self.state = 1.0
            self.held_value = input_value
        elif (not set_on) and reset_on and self.state > 0.5:
            self.state = 0.0

        params[self.output_idx] = self.held_value if self.state > 0.5 else input_value

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "output_var_name": self.output_var_name,
            "input_expr": _expr_like_to_dict(self.input_expr),
            "set_expr": _expr_like_to_dict(self.set_expr),
            "reset_expr": _expr_like_to_dict(self.reset_expr),
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalogFlipFlopLogic":
        return cls(
            output_var_name=str(data["output_var_name"]),
            input_expr=_expr_like_from_dict(data["input_expr"]),
            set_expr=_expr_like_from_dict(data["set_expr"]),
            reset_expr=_expr_like_from_dict(data["reset_expr"]),
            name=str(data.get("name", "")),
        )

    def remap(self, var_mapping: Dict[Any, Expr]) -> "AnalogFlipFlopLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return AnalogFlipFlopLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            input_expr=_subs_expr_like(self.input_expr, var_mapping),
            set_expr=_subs_expr_like(self.set_expr, var_mapping),
            reset_expr=_subs_expr_like(self.reset_expr, var_mapping),
            name=self.name,
        )


class PickupDropoffLogic(ProceduralLogicBase):
    __slots__ = [
        "output_var_name",
        "bool_expr",
        "pickup_delay_expr",
        "drop_delay_expr",
        "output_idx",
        "state",
        "initialized",
        "pickup_started_at",
        "drop_started_at",
        "pending_pickup_time",
        "pending_drop_time",
    ]
    logic_type = "pickup_dropoff"

    def __init__(
        self,
        output_var_name: str,
        bool_expr: Expr | Comparison,
        pickup_delay_expr: Expr | Comparison,
        drop_delay_expr: Expr | Comparison,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.bool_expr = bool_expr
        self.pickup_delay_expr = pickup_delay_expr
        self.drop_delay_expr = drop_delay_expr
        self.output_idx = -1
        self.state = 0.0
        self.initialized = False
        self.pickup_started_at: Optional[float] = None
        self.drop_started_at: Optional[float] = None
        self.pending_pickup_time: Optional[float] = None
        self.pending_drop_time: Optional[float] = None

    def bind(self, problem: EmtProblemTemplate) -> None:
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.state = 0.0
        self.initialized = False
        self.pickup_started_at = None
        self.drop_started_at = None
        self.pending_pickup_time = None
        self.pending_drop_time = None

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        super().get_next_forced_event_time(t_prev, t_target)
        candidates: List[float] = list()
        if self.pending_pickup_time is not None and t_prev < self.pending_pickup_time <= t_target:
            candidates.append(float(self.pending_pickup_time))
        if self.pending_drop_time is not None and t_prev < self.pending_drop_time <= t_target:
            candidates.append(float(self.pending_drop_time))
        if len(candidates) == 0:
            return None
        return min(candidates)

    def _eval_delay(self, expr: Expr | Comparison, t: float, x: Vec, params: Vec) -> float:
        return max(0.0, self._eval_numeric(expr, t, x, params))

    def update(self, t: float, x: Vec, params: Vec) -> None:
        tol = 1.0e-15
        sample_time = self._get_sample_time(t)
        bool_on = self._eval_bool(self.bool_expr, t, x, params)

        if not self.initialized:
            self.initialized = True
            if bool_on:
                pickup_delay = self._eval_delay(self.pickup_delay_expr, t, x, params)
                if pickup_delay <= tol:
                    self.state = 1.0
                else:
                    self.pickup_started_at = sample_time
                    self.pending_pickup_time = sample_time + pickup_delay

        if self.state < 0.5:
            self.drop_started_at = None
            self.pending_drop_time = None

            if bool_on:
                if self.pickup_started_at is None:
                    self.pickup_started_at = sample_time
                self.pending_pickup_time = self.pickup_started_at + self._eval_delay(self.pickup_delay_expr, t, x, params)
            else:
                self.pickup_started_at = None
                self.pending_pickup_time = None

            if self.pending_pickup_time is not None and t >= (self.pending_pickup_time - tol):
                self.state = 1.0
                self.pickup_started_at = None
                self.pending_pickup_time = None

        else:
            self.pickup_started_at = None
            self.pending_pickup_time = None

            if not bool_on:
                if self.drop_started_at is None:
                    self.drop_started_at = sample_time
                self.pending_drop_time = self.drop_started_at + self._eval_delay(self.drop_delay_expr, t, x, params)
            else:
                self.drop_started_at = None
                self.pending_drop_time = None

            if self.pending_drop_time is not None and t >= (self.pending_drop_time - tol):
                self.state = 0.0
                self.drop_started_at = None
                self.pending_drop_time = None

        params[self.output_idx] = self.state

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "output_var_name": self.output_var_name,
            "bool_expr": _expr_like_to_dict(self.bool_expr),
            "pickup_delay_expr": _expr_like_to_dict(self.pickup_delay_expr),
            "drop_delay_expr": _expr_like_to_dict(self.drop_delay_expr),
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PickupDropoffLogic":
        return cls(
            output_var_name=str(data["output_var_name"]),
            bool_expr=_expr_like_from_dict(data["bool_expr"]),
            pickup_delay_expr=_expr_like_from_dict(data["pickup_delay_expr"]),
            drop_delay_expr=_expr_like_from_dict(data["drop_delay_expr"]),
            name=str(data.get("name", "")),
        )

    def remap(self, var_mapping: Dict[Any, Expr]) -> "PickupDropoffLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return PickupDropoffLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            bool_expr=_subs_expr_like(self.bool_expr, var_mapping),
            pickup_delay_expr=_subs_expr_like(self.pickup_delay_expr, var_mapping),
            drop_delay_expr=_subs_expr_like(self.drop_delay_expr, var_mapping),
            name=self.name,
        )


class ResetOnRisingEdgeLogic(ProceduralLogicBase):
    __slots__ = [
        "target_var_name",
        "reset_expr",
        "value_expr",
        "target_state_idx",
        "target_param_idx",
        "initialized",
        "last_reset_high",
    ]
    logic_type = "reset_on_rising_edge"

    def __init__(
        self,
        target_var_name: str,
        reset_expr: Expr | Comparison,
        value_expr: Expr | Comparison,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.target_var_name = target_var_name
        self.reset_expr = reset_expr
        self.value_expr = value_expr
        self.target_state_idx = -1
        self.target_param_idx = -1
        self.initialized = False
        self.last_reset_high = False

    def bind(self, problem: EmtProblemTemplate) -> None:
        super().bind(problem)
        target_var = _find_var_by_name(problem.sys_block, self.target_var_name)
        self.target_state_idx = int(problem.uid2idx_vars.get(target_var.uid, -1))
        self.target_param_idx = int(problem.uid2idx_event_params.get(target_var.uid, -1))

        if self.target_state_idx < 0 and self.target_param_idx < 0:
            raise KeyError(f"Reset target '{self.target_var_name}' is not a state/algebraic variable nor a runtime parameter")

        self.initialized = False
        self.last_reset_high = False

    def update(self, t: float, x: Vec, params: Vec) -> None:
        reset_high = self._eval_bool(self.reset_expr, t, x, params)

        if not self.initialized:
            self.initialized = True
            self.last_reset_high = reset_high
            return

        if (not self.last_reset_high) and reset_high:
            reset_value = self._eval_numeric(self.value_expr, t, x, params)
            if self.target_state_idx >= 0:
                x[self.target_state_idx] = reset_value
            else:
                params[self.target_param_idx] = reset_value

        self.last_reset_high = reset_high

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "target_var_name": self.target_var_name,
            "reset_expr": _expr_like_to_dict(self.reset_expr),
            "value_expr": _expr_like_to_dict(self.value_expr),
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResetOnRisingEdgeLogic":
        return cls(
            target_var_name=str(data["target_var_name"]),
            reset_expr=_expr_like_from_dict(data["reset_expr"]),
            value_expr=_expr_like_from_dict(data["value_expr"]),
            name=str(data.get("name", "")),
        )

    def remap(self, var_mapping: Dict[Any, Expr]) -> "ResetOnRisingEdgeLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return ResetOnRisingEdgeLogic(
            target_var_name=name_mapping.get(self.target_var_name, self.target_var_name),
            reset_expr=_subs_expr_like(self.reset_expr, var_mapping),
            value_expr=_subs_expr_like(self.value_expr, var_mapping),
            name=self.name,
        )


def fixed_sample(output: Var | str, when: Expr | Comparison, name: str = "") -> FixedSampleLogic:
    output_name = _coerce_var_name(output)
    return FixedSampleLogic(
        output_var_name=output_name,
        condition_expr=when,
        name=output_name if name == "" else name,
    )


def selfix(boolexpr: Expr | Comparison, output: Var | str, name: str = "") -> FixedSampleLogic:
    return fixed_sample(output=output, when=boolexpr, name=name)


def selfix_const(boolexpr: Expr | Comparison, output: Var | str, name: str = "") -> FixedSampleLogic:
    return fixed_sample(output=output, when=boolexpr, name=name)


def sampled_value(output: Var | str, source: Expr | Comparison, name: str = "") -> SampledValueLogic:
    output_name = _coerce_var_name(output)
    return SampledValueLogic(
        output_var_name=output_name,
        source_expr=source,
        name=output_name if name == "" else name,
    )


def lastvalue(input_expr: Expr | Comparison, output: Var | str, name: str = "") -> SampledValueLogic:
    return sampled_value(output=output, source=input_expr, name=name)


def flipflop(boolset: Expr | Comparison, boolreset: Expr | Comparison, output: Var | str, name: str = "") -> FlipFlopLogic:
    output_name = _coerce_var_name(output)
    return FlipFlopLogic(
        output_var_name=output_name,
        set_expr=boolset,
        reset_expr=boolreset,
        name=output_name if name == "" else name,
    )


def aflipflop(
    x: Expr | Comparison,
    boolset: Expr | Comparison,
    boolreset: Expr | Comparison,
    output: Var | str,
    name: str = "",
) -> AnalogFlipFlopLogic:
    output_name = _coerce_var_name(output)
    return AnalogFlipFlopLogic(
        output_var_name=output_name,
        input_expr=x,
        set_expr=boolset,
        reset_expr=boolreset,
        name=output_name if name == "" else name,
    )


def pickup_dropoff(
    output: Var | str,
    boolexpr: Expr | Comparison,
    Tpick: Expr | Comparison,
    Tdrop: Expr | Comparison,
    name: str = "",
) -> PickupDropoffLogic:
    output_name = _coerce_var_name(output)
    return PickupDropoffLogic(
        output_var_name=output_name,
        bool_expr=boolexpr,
        pickup_delay_expr=Tpick,
        drop_delay_expr=Tdrop,
        name=output_name if name == "" else name,
    )


def picdro(
    boolexpr: Expr | Comparison,
    Tpick: Expr | Comparison,
    Tdrop: Expr | Comparison,
    output: Var | str,
    name: str = "",
) -> PickupDropoffLogic:
    return pickup_dropoff(output=output, boolexpr=boolexpr, Tpick=Tpick, Tdrop=Tdrop, name=name)


def picdro_const(
    boolexpr: Expr | Comparison,
    Tpick: Expr | Comparison,
    Tdrop: Expr | Comparison,
    output: Var | str,
    name: str = "",
) -> PickupDropoffLogic:
    return pickup_dropoff(output=output, boolexpr=boolexpr, Tpick=Tpick, Tdrop=Tdrop, name=name)


def reset(var: Var | str, rst: Expr | Comparison, val: Expr | Comparison, name: str = "") -> ResetOnRisingEdgeLogic:
    target_name = _coerce_var_name(var)
    return ResetOnRisingEdgeLogic(
        target_var_name=target_name,
        reset_expr=rst,
        value_expr=val,
        name=f"{target_name}_reset" if name == "" else name,
    )

def _iter_block_vars(block: Block) -> List[Var]:
    vars_found: List[Var] = list()
    vars_found.extend(block.state_vars)
    vars_found.extend(block.algebraic_vars)
    vars_found.extend(block.diff_vars)
    vars_found.extend(block.in_vars)
    vars_found.extend(block.out_vars)
    vars_found.extend(list(block.event_dict.keys()))
    vars_found.extend(list(block.mode_dict.keys()))

    for child in block.children:
        vars_found.extend(_iter_block_vars(child))

    return vars_found


def _find_var_by_name(block: Block, var_name: str) -> Var:
    for var in _iter_block_vars(block):
        if var.name == var_name:
            return var
    raise KeyError(f"Variable '{var_name}' not found in block tree")


class DelayedThresholdLatchLogic(ProceduralLogicBase):
    """
    Comparator + timer + latch procedural logic for runtime modes.

    The logic watches one state variable, arms a timer when a threshold is crossed,
    applies a mode change after a delay, and optionally resets after a second delay.
    """

    __slots__ = [
        "monitored_var_name",
        "mode_var_name",
        "threshold",
        "delay",
        "reset_delay",
        "mode_idx",
        "monitored_idx",
        "pickup_time",
        "pending_trip_time",
        "pending_reset_time",
        "tripped",
        "trip_applied_time",
        "trip_applied_solver_time",
        "reset_applied_time",
        "reset_applied_solver_time",
        "last_t_prev",
        "trace_t",
        "trace_measure",
        "trace_comparator",
        "trace_timer_armed",
        "trace_latched",
        "trace_mode",
    ]
    logic_type = "delayed_threshold_latch"

    def __init__(
        self,
        monitored_var_name: str,
        mode_var_name: str,
        threshold: float,
        delay: float,
        reset_delay: Optional[float] = None,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.monitored_var_name = monitored_var_name
        self.mode_var_name = mode_var_name
        self.threshold = float(threshold)
        self.delay = float(delay)
        self.reset_delay = None if reset_delay is None else float(reset_delay)

        self.mode_idx = -1
        self.monitored_idx = -1
        self.pickup_time: Optional[float] = None
        self.pending_trip_time: Optional[float] = None
        self.pending_reset_time: Optional[float] = None
        self.tripped = False
        self.trip_applied_time: Optional[float] = None
        self.trip_applied_solver_time: Optional[float] = None
        self.reset_applied_time: Optional[float] = None
        self.reset_applied_solver_time: Optional[float] = None
        self.last_t_prev: Optional[float] = None

        self.trace_t: List[float] = list()
        self.trace_measure: List[float] = list()
        self.trace_comparator: List[float] = list()
        self.trace_timer_armed: List[float] = list()
        self.trace_latched: List[float] = list()
        self.trace_mode: List[float] = list()

    def bind(self, problem: EmtProblemTemplate) -> None:
        super().bind(problem)
        mode_var = _find_var_by_name(problem.sys_block, self.mode_var_name)
        monitored_var = _find_var_by_name(problem.sys_block, self.monitored_var_name)
        self.mode_idx = int(problem.uid2idx_event_params[mode_var.uid])
        self.monitored_idx = int(problem.get_var_idx(monitored_var))

    def _append_trace_point(
        self,
        trace_time: float,
        measured_value: float,
        comparator: float,
        timer_armed: float,
        latched: float,
        mode_value: float,
    ) -> None:
        self.trace_t.append(float(trace_time))
        self.trace_measure.append(float(measured_value))
        self.trace_comparator.append(float(comparator))
        self.trace_timer_armed.append(float(timer_armed))
        self.trace_latched.append(float(latched))
        self.trace_mode.append(float(mode_value))

    def _record_sample_trace(self, sample_time: float, measured_value: float, params: np.ndarray) -> None:
        comparator = 1.0 if measured_value >= self.threshold else 0.0
        timer_armed = 1.0 if self.pending_trip_time is not None else 0.0
        latched = 1.0 if self.tripped else 0.0
        mode_value = float(params[self.mode_idx])
        self._append_trace_point(sample_time, measured_value, comparator, timer_armed, latched, mode_value)

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        super().get_next_forced_event_time(t_prev, t_target)
        self.last_t_prev = float(t_prev)
        candidates: List[float] = list()
        if self.pending_trip_time is not None and t_prev < self.pending_trip_time <= t_target:
            candidates.append(float(self.pending_trip_time))
        if self.pending_reset_time is not None and t_prev < self.pending_reset_time <= t_target:
            candidates.append(float(self.pending_reset_time))
        if len(candidates) == 0:
            return None
        return min(candidates)

    def update(self, t: float, x: Vec, params: Vec) -> None:
        tol = 1.0e-15
        sample_time = float(self.last_t_prev if self.last_t_prev is not None else t)
        measured_value = float(x[self.monitored_idx])
        comparator_on = measured_value >= self.threshold
        comparator_value = 1.0 if comparator_on else 0.0

        if self.tripped:
            params[self.mode_idx] = 0.0
            if self.pending_reset_time is not None and t >= (self.pending_reset_time - tol):
                self.tripped = False
                self.reset_applied_time = float(self.pending_reset_time)
                self.reset_applied_solver_time = float(t)
                self.pickup_time = None
                self.pending_trip_time = None
                self.pending_reset_time = None
                params[self.mode_idx] = 1.0
                self._append_trace_point(t, measured_value, comparator_value, 0.0, 0.0, 1.0)
                return
            self._record_sample_trace(sample_time, measured_value, params)
            return

        if comparator_on:
            if self.pickup_time is None:
                self.pickup_time = sample_time
                self.pending_trip_time = sample_time + self.delay
        else:
            self.pickup_time = None
            self.pending_trip_time = None

        if self.pending_trip_time is not None and t >= (self.pending_trip_time - tol):
            self.tripped = True
            self.trip_applied_time = float(self.pending_trip_time)
            self.trip_applied_solver_time = float(t)
            params[self.mode_idx] = 0.0
            if self.reset_delay is not None:
                self.pending_reset_time = self.trip_applied_time + self.reset_delay
            self.pending_trip_time = None
            self._append_trace_point(t, measured_value, comparator_value, 0.0, 1.0, 0.0)
            return

        params[self.mode_idx] = 1.0
        self._record_sample_trace(sample_time, measured_value, params)

    def get_trace_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        return (
            np.asarray(self.trace_t, dtype=float),
            np.asarray(self.trace_measure, dtype=float),
            np.asarray(self.trace_comparator, dtype=float),
            np.asarray(self.trace_timer_armed, dtype=float),
            np.asarray(self.trace_latched, dtype=float),
            np.asarray(self.trace_mode, dtype=float),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "monitored_var_name": self.monitored_var_name,
            "mode_var_name": self.mode_var_name,
            "threshold": self.threshold,
            "delay": self.delay,
            "reset_delay": self.reset_delay,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DelayedThresholdLatchLogic":
        return cls(
            monitored_var_name=str(data["monitored_var_name"]),
            mode_var_name=str(data["mode_var_name"]),
            threshold=float(data["threshold"]),
            delay=float(data["delay"]),
            reset_delay=None if data.get("reset_delay", None) is None else float(data["reset_delay"]),
            name=str(data.get("name", "")),
        )

    def remap(self, var_mapping: Dict[Any, Expr]) -> "DelayedThresholdLatchLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return DelayedThresholdLatchLogic(
            monitored_var_name=name_mapping.get(self.monitored_var_name, self.monitored_var_name),
            mode_var_name=name_mapping.get(self.mode_var_name, self.mode_var_name),
            threshold=self.threshold,
            delay=self.delay,
            reset_delay=self.reset_delay,
            name=self.name,
        )


class BlockProceduralLogicUpdater(BoundaryUpdateWrapper):
    """
    Boundary updater that delegates runtime decisions to block-attached procedural logic entries.
    """

    __slots__ = ["problem", "logic_entries"]

    def __init__(self, problem: EmtProblemTemplate, logic_entries: List[ProceduralLogicBase]) -> None:
        self.problem = problem
        self.logic_entries = logic_entries
        for logic in self.logic_entries:
            logic.bind(problem)

    def update(self, t: float, x: Vec, params: Vec) -> None:
        for logic in self.logic_entries:
            logic.update(t, x, params)

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        candidates: List[float] = list()
        for logic in self.logic_entries:
            candidate = logic.get_next_forced_event_time(t_prev, t_target)
            if candidate is not None:
                candidates.append(candidate)
        if len(candidates) == 0:
            return None
        return min(candidates)


def build_procedural_logic_entry(data: Dict[str, Any]) -> ProceduralLogicBase:
    """
    Deserialize one procedural logic entry.

    :param data: Serialized logic config.
    :return: Procedural logic object.
    """
    logic_type = str(data.get("logic_type", ""))
    if logic_type == FixedSampleLogic.logic_type:
        return FixedSampleLogic.from_dict(data)
    if logic_type == SampledValueLogic.logic_type:
        return SampledValueLogic.from_dict(data)
    if logic_type == FlipFlopLogic.logic_type:
        return FlipFlopLogic.from_dict(data)
    if logic_type == AnalogFlipFlopLogic.logic_type:
        return AnalogFlipFlopLogic.from_dict(data)
    if logic_type == PickupDropoffLogic.logic_type:
        return PickupDropoffLogic.from_dict(data)
    if logic_type == ResetOnRisingEdgeLogic.logic_type:
        return ResetOnRisingEdgeLogic.from_dict(data)
    if logic_type == DelayedThresholdLatchLogic.logic_type:
        return DelayedThresholdLatchLogic.from_dict(data)
    raise ValueError(f"Unsupported procedural logic type '{logic_type}'")


def procedural_logic_to_dict(entries: List[ProceduralLogicBase]) -> List[Dict[str, Any]]:
    """
    Serialize a list of procedural logic entries.

    :param entries: Logic entries.
    :return: Serialized representation.
    """
    return [entry.to_dict() for entry in entries]


def procedural_logic_from_dict(entries: List[Dict[str, Any]]) -> List[ProceduralLogicBase]:
    """
    Deserialize a list of procedural logic entries.

    :param entries: Serialized entries.
    :return: Procedural logic objects.
    """
    return [build_procedural_logic_entry(item) for item in entries]


def clone_procedural_logic_entries(entries: List[ProceduralLogicBase], var_mapping: Dict[Any, Expr]) -> List[ProceduralLogicBase]:
    return [entry.remap(var_mapping) for entry in entries]


def build_boundary_updater_from_block(problem: EmtProblemTemplate) -> Optional[BlockProceduralLogicUpdater]:
    """
    Build a boundary updater from ``problem.sys_block.procedural_logic``.

    :param problem: EMT problem containing the root block.
    :return: Boundary updater or None.
    """
    entries = getattr(problem.sys_block, "procedural_logic", None)
    if entries is None or len(entries) == 0:
        return None
    return BlockProceduralLogicUpdater(problem, entries)
