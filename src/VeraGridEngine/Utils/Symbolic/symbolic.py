# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import json
import math
import ast
import uuid
import numpy as np
from enum import Enum
import numba as nb
from dataclasses import dataclass, field
from types import MappingProxyType

from typing import Any, Callable, ClassVar, Dict, Mapping, Union, List, Sequence, Tuple, Set, Optional

NUMBER = Union[int, float, complex]


# -----------------------------------------------------------------------------
# UUID helper
# -----------------------------------------------------------------------------

def _new_uid() -> int:
    """Generate a fresh UUID‑v4 string."""
    return uuid.uuid4().int


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------


def _to_expr(val: Any) -> "Expr":
    if isinstance(val, Expr):
        return val
    if isinstance(val, (int, float, complex)):
        return Const(val)
    if val is None:
        return Const(None)
    raise TypeError(f"Cannot convert {val!r} to Expr")


def _var_name(sym: Var | str) -> str:
    return sym.name if isinstance(sym, Var) else sym


def _var_uid(sym: Var | str) -> str:
    return sym.uid if isinstance(sym, Var) else sym


# ----------------------------------------------------------------------------
# Function helpers
# ----------------------------------------------------------------------------


class CmpOp(Enum):
    LE = "≤"  # ≤
    GE = "≥"  # ≥
    LT = "<"
    GT = ">"
    EQ = "="  # =


@dataclass(frozen=True, slots=True)
class Comparison:
    lhs: "Expr"
    op: CmpOp  # "<=", ">=", "=="
    rhs: Union["Expr", NUMBER]


class Expr:
    """
    Abstract base class for all expression nodes.
    """

    __slots__ = ("uid",)

    def __init__(self, uid: int | None = None):
        """

        :param uid: (optional UID)
        """
        self.uid: int = _new_uid() if uid is None else uid  # real dataclass field lives in subclasses

    def get_vars(self, vars_found: Optional[list["Var"]] = None) -> list["Var"]:
        """

        :param vars_found:
        :return:
        """
        if vars_found is None:
            vars_found = []

        if isinstance(self, Var):
            if self not in vars_found:
                vars_found.append(self)

        elif isinstance(self, BinOp):
            self.left.get_vars(vars_found)
            self.right.get_vars(vars_found)

        elif isinstance(self, UnOp):
            self.operand.get_vars(vars_found)

        elif isinstance(self, Func):
            self.arg.get_vars(vars_found)

        # Todo: add comparisions

        return vars_found

    def eval(self, **bindings: float | int) -> float | int:  # pragma: no cover – abstract
        """
        Numeric evaluation
        :param bindings:
        :return:
        """
        raise NotImplementedError

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:  # pragma: no cover – abstract
        """

        :param uid_bindings:
        :return:
        """
        raise NotImplementedError

    __call__ = eval  # allow f(x=…)

    def diff(self, var: Var | str, order: int = 1) -> "Expr":
        """
        Differentiation (higher‑order)
        :param var:
        :param order:
        :return:
        """
        if order < 0:
            raise ValueError("order must be >= 0")
        expr: Expr = self
        for _ in range(order):
            expr = expr._diff1(var).simplify()
        return expr

    def _diff1(self, var: Var | str) -> "Expr":  # pragma: no cover
        raise NotImplementedError

    def simplify(self) -> "Expr":
        """
        Simplification & substitution (no‑ops by default)
        :return:
        """
        return self

    def subs(self, mapping: Dict[Any, "Expr"]) -> "Expr":
        return mapping.get(self, self)

    def to_dict(self) -> Dict[str, Any]:
        # return _expr_to_dict(self)
        return dict()

    def to_json(self, **json_kwargs: Any) -> str:
        return json.dumps(self.to_dict(), **json_kwargs)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Expr":
        return _dict_to_expr(data)

    @staticmethod
    def from_json(blob: str) -> "Expr":
        return _dict_to_expr(json.loads(blob))

    # ------------------------------------------------------------------
    # Operator helpers
    # ------------------------------------------------------------------
    def __add__(self, other: Any) -> Expr:
        return BinOp(self, "+", _to_expr(other))

    def __radd__(self, other: Any) -> Expr:
        return BinOp(_to_expr(other), "+", self)

    def __sub__(self, other: Any) -> Expr:
        return BinOp(self, "-", _to_expr(other))

    def __rsub__(self, other: Any) -> Expr:
        return BinOp(_to_expr(other), "-", self)

    def __mul__(self, other: Any) -> Expr:
        return BinOp(self, "*", _to_expr(other))

    def __rmul__(self, other: Any) -> Expr:
        return BinOp(_to_expr(other), "*", self)

    def __truediv__(self, other: Any) -> Expr:
        return BinOp(self, "/", _to_expr(other))

    def __rtruediv__(self, other: Any) -> Expr:
        return BinOp(_to_expr(other), "/", self)

    def __pow__(self, other: Any) -> Expr:
        return BinOp(self, "**", _to_expr(other))

    def __rpow__(self, other: Any) -> Expr:
        return BinOp(_to_expr(other), "**", self)

    def __neg__(self) -> "Expr":
        return UnOp("-", self)

    def __le__(self, other: Expr | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.LE, other)

    def __ge__(self, other: Expr | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.GE, other)

    def __eq__(self, other: Expr | NUMBER) -> Comparison:  # type: ignore[override]
        return Comparison(self, CmpOp.EQ, other)

    def __lt__(self, other: Expr | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.LT, other)

    def __gt__(self, other: Expr | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.GT, other)

    def __str__(self) -> str:  # pragma: no cover – abstract
        """
        Display helper
        :return:
        """
        raise NotImplementedError

    def __repr__(self):
        return self.__str__()

    def __hash__(self) -> int:
        return hash(repr(self))


# ----------------------------------------------------------------------------------------------------------------------
# Atomic nodes
# ----------------------------------------------------------------------------------------------------------------------



class Const(Expr):

    def __init__(self, value: NUMBER | None = None, uid: int | None = None, name: str = ""):
        super().__init__(uid=uid)
        self.value: NUMBER | None = value
        self.name: str = name

    def __deepcopy__(self, memo):
        return Const(self.value, self.uid, self.name)

    def eval(self, **bindings: NUMBER) -> NUMBER | None:
        return self.value

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER | None:
        return self.value

    def _diff1(self, var: Var | str) -> "Expr":
        return Const(0)

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        if self in mapping:
            return mapping[self]
        if self.name in mapping:
            return mapping[self.name]
        return self

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return self.__str__()

    def to_dict(self) -> Dict[str, Any]:

        d = super().to_dict()

        d["type"] = "Const"

        # return _expr_to_dict(self)
        if isinstance(self.value, complex):
            d["value"] = [self.value.real, self.value.imag]
            d["kind"] = "complex"
            return d

        if self.value is None:
            d["value"] = None
            d["kind"] = "undefined"
            return d

        d["value"] = self.value
        d["kind"] = "float"
        return d


class Var(Expr):
    """
    Any variable
    """

    __slots__ = ("name", "uid", "diff_var")

    def __init__(self, name: str, uid: int | None = None, diff_var: "DiffVar | None" = None):
        """

        :param name:
        :param uid:
        :param diff_var:
        """
        super().__init__(uid=uid)
        self.name: str = name
        self.diff_var = diff_var

    def __deepcopy__(self, memo):
        return Var(self.name, self.uid, self.diff_var)

    def eval(self, **bindings: NUMBER) -> NUMBER:
        try:
            return bindings[self.name]
        except KeyError as exc:
            raise ValueError(f"No value for variable '{self.name}'.") from exc

    def eval_uid(self, uid_bindings: Dict[int, NUMBER]) -> NUMBER:
        try:
            return uid_bindings[self.uid]
        except KeyError as exc:
            raise ValueError(f"No value for uid '{self.uid}'.") from exc

    def _diff1(self, var: Var | str) -> Expr:
        return Const(1 if self.uid == _var_uid(var) else 0)

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        if self in mapping:
            return mapping[self]
        if self.name in mapping:
            return mapping[self.name]
        return self

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def __eq__(self, other):
        if isinstance(other, Var):
            return self.uid == other.uid
        return False

    def to_dict(self) -> Dict[str, Any]:
        """

        :return:
        """
        d = super().to_dict()
        d["type"] = "Var"
        d["name"] = self.name
        return d

    def __hash__(self) -> int:
        return hash(repr(self))




class LagVar(Expr):
    __slots__ = ("name", "uid", "base_var", "lag")

    def __init__(self, name: str, uid: int | None = None, base_var: Var | None = None, lag: int = 0):
        """

        :param name:
        :param uid:
        :param base_var:
        """
        super().__init__(uid=uid)
        self.name: str = name
        self.base_var = base_var
        self.lag: int = lag

        # Optionally, you could add checks here to ensure base_var is an instance of Var
        if not isinstance(self.base_var, Var):
            raise TypeError(f"base_var must be an argument")

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        if self in mapping:
            return mapping[self]
        if self.name in mapping:
            return mapping[self.name]
        return self

    def __eq__(self, other):
        return isinstance(other, LagVar) and self.base_var.uid == other.base_var.uid and self.lag == other.lag

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def __hash__(self):
        return hash((self.base_var, self.lag))

    def populate_initial_lag(self, x0: float, dx0: np.ndarray, lag_x: float, dt: Optional[Var], h: float):
        """

        :param x0:
        :param dx0:
        :param lag_x:
        :param dt:
        :param h:
        :return:
        """
        # function that initializes the lag of the same order for the same original_var
        diff_order = self.lag
        if diff_order == 1:
            return x0
        elif diff_order == 2:
            return x0 - dt * dx0[0]
        else:
            res = x0 - dt * dx0[0]

        for i in range(1, diff_order + 1):
            val = (diff_order + 1 - i) * (dt ** i) * ((-1) ** i) * dx0[i - 1]
            res += val
        return res.eval(dt=h)

    def _diff1(self, var: Var | str) -> Expr:
        return Const(1 if self.uid == _var_uid(var) else 0)

    def to_dict(self) -> Dict[str, Any]:
        """

        :return:
        """
        d = super().to_dict()
        d["type"] = "Var"
        d["name"] = self.name
        d["base_var"] = self.base_var.uid
        d["lag"] = self.lag
        return d


class DiffVar(Var):
    """
    dx
    """

    __slots__ = ("base_var",)

    def __init__(self, name: str, base_var: Var | None = None, uid: int | None = None):
        """

        :param name:
        :param base_var:
        """
        super().__init__(name=name, uid=uid)
        self.base_var: Var = base_var  # assign reference to base var

        self.base_var.diff_var = self  # assign reference to me in the base var

    def __eq__(self, other):
        return isinstance(other, DiffVar) and self.base_var.uid == other.base_var.uid

    def __hash__(self):
        return hash(self.base_var)

    def to_dict(self) -> Dict[str, Any]:
        """

        :return:
        """
        d = super().to_dict()
        d["type"] = "DiffVar"
        d["base_var"] = self.base_var.uid
        return d

    @property
    def diff_order(self) -> int:
        order = 0
        var = self
        while isinstance(var, DiffVar):
            var = var.base_var
            order += 1
        return order

    @property
    def origin_var(self) -> Var:
        origin = self.base_var
        while isinstance(origin, DiffVar):
            origin = origin.base_var
        return origin

    def populate_initial_lag(self, x0: float, dx0: np.ndarray, lag_x: float, dt: Optional[Const]):
        """

        :param x0:
        :param dx0:
        :param lag_x:
        :param dt:
        :return:
        """
        # function that initializes the lag of the same order for the same original_var
        diff_order = self.diff_order
        central_difference = True
        res = Expr()
        for i in range(diff_order):
            res += (dt ** (i + 1)) * (-1) ** (i + 1) * dx0[i]
        return res.eval()

    def approximation_expr(self, dt: Optional[Var], lag_can_be_0=True, central=False) -> Tuple:
        """
        Computes the n-th backward finite difference approximation of the derivative
        using the closed-form backward difference formula.
        """
        origin_name = self.origin_var.name
        if lag_can_be_0:
            lag_var_0 = LagVar(
                name=f"{origin_name}_lag_{0}",
                base_var=self.origin_var,
                lag=0
            )
        else:
            lag_var_0 = self.origin_var

        origin_name = self.origin_var.name
        lag_total = self.diff_order
        if self.diff_order == 1 and central:
            lag_var_2 = LagVar(
                name=f"{origin_name}_lag_{2}",
                base_var=self.origin_var,
                lag=2
            )
            return (lag_var_0 - lag_var_2) / (2 * dt), lag_total

        # Compute the sum: ∑_{i=0}^{n} (-1)^i * C(n, i) * f(x - i*dt)
        terms = []
        minus1 = Const(-1)

        for i in range(lag_total + 1):
            if i == 0:
                lag_var = lag_var_0
            else:
                lag_var = LagVar(
                    name=f"{origin_name}_lag_{i}",
                    base_var=self.origin_var,
                    lag=i
                )
            coeff = minus1 ** i * Const(math.comb(lag_total, i))
            terms.append(coeff * lag_var)

        finite_diff_sum = sum(terms)

        # Divide by dt^n for n-th derivative
        result = finite_diff_sum / dt ** lag_total
        return result.simplify(), lag_total


class BinOp(Expr):
    """
    Binary operation expression
    """

    __slots__ = ("op", "left", "right")

    def __init__(self, left: Expr, op: str, right: Expr, uid: int | None = None):
        """

        :param left:
        :param op:
        :param right:
        :param uid:
        """
        super().__init__(uid=uid)
        self.op: str = op
        self.left: Expr = left
        self.right: Expr = right

    # _impl: ClassVar[Mapping[str, Callable[[NUMBER, NUMBER], NUMBER]]] = MappingProxyType({
    #     "+": lambda a, b: a + b,
    #     "-": lambda a, b: a - b,
    #     "*": lambda a, b: a * b,
    #     "/": lambda a, b: a / b,
    #     "**": lambda a, b: a ** b,
    # })

    def eval(self, **bindings: NUMBER) -> NUMBER:
        """
        Evaluation using names
        :param bindings:
        :return:
        """
        # return self._impl[self.op](self.left.eval(**bindings), self.right.eval(**bindings))
        if self.op == "+":
            return self.left.eval(**bindings) + self.right.eval(**bindings)
        elif self.op == "-":
            return self.left.eval(**bindings) - self.right.eval(**bindings)
        elif self.op == "*":
            return self.left.eval(**bindings) * self.right.eval(**bindings)
        elif self.op == "/":
            return self.left.eval(**bindings) / self.right.eval(**bindings)
        elif self.op == "**":
            return self.left.eval(**bindings) ** self.right.eval(**bindings)
        else:
            raise Exception(f"operation {self.op} not implemented")

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:
        """
        Evaluate using uuid's
        :param uid_bindings:
        :return:
        """
        # return self._impl[self.op](self.left.eval_uid(uid_bindings), self.right.eval_uid(uid_bindings))
        if self.op == "+":
            return self.left.eval_uid(uid_bindings) + self.right.eval_uid(uid_bindings)
        elif self.op == "-":
            return self.left.eval_uid(uid_bindings) - self.right.eval_uid(uid_bindings)
        elif self.op == "*":
            return self.left.eval_uid(uid_bindings) * self.right.eval_uid(uid_bindings)
        elif self.op == "/":
            return self.left.eval_uid(uid_bindings) / self.right.eval_uid(uid_bindings)
        elif self.op == "**":
            return self.left.eval_uid(uid_bindings) ** self.right.eval_uid(uid_bindings)
        else:
            raise Exception(f"operation {self.op} not implemented")

    def _diff1(self, var: Var | str) -> Expr:
        """
        Differentiation of this expression w.r.t var
        :param var: variable to differentiate with respect to
        :return: Expression
        """
        u, v = self.left, self.right
        du, dv = u._diff1(var), v._diff1(var)
        if self.op == "+":
            return du + dv
        if self.op == "-":
            return du - dv
        if self.op == "*":
            return du * v + u * dv
        if self.op == "/":
            return (du * v - u * dv) / (v ** Const(2))
        if self.op == "**":
            if isinstance(v, Const):
                # numeric exponent
                n = v.value
                return Const(n) * (u ** Const(n - 1)) * du
            else:
                # general exponent: u**v = exp(v*log u)
                return self * (dv * log(u) + du * v / u)
        raise ValueError("Unsupported operator for diff")

    def simplify(self) -> Expr:
        """
        Simplify expression
        :return: Simplified expression
        """
        l, r = self.left.simplify(), self.right.simplify()
        if isinstance(l, Const) and isinstance(r, Const):
            if self.op == "+":
                return Const(r.value + l.value)
            elif self.op == "-":
                return Const(r.value - l.value)
            elif self.op == "*":
                return Const(r.value * l.value)
            elif self.op == "/":
                if l.value != 0.0:
                    return Const(r.value / l.value)
                else:
                    raise Exception("Division by zero :/")
            elif self.op == "**":
                return Const(r.value ** l.value)
            else:
                raise Exception(f"operation {self.op} not implemented")

        if self.op == "+":
            if isinstance(l, Const) and l.value == 0:
                return r
            if isinstance(r, Const) and r.value == 0:
                return l

        if self.op == "*":
            for a, b in ((l, r), (r, l)):
                if isinstance(a, Const):
                    if a.value == 0:
                        return Const(0)
                    if a.value == 1:
                        return b

        if self.op == "**" and isinstance(r, Const):
            if r.value == 1:
                return l
            if r.value == 0:
                return Const(1)

        if self.op == '/' and isinstance(l, Const):
            if l.value == 0:
                return l
        if self.op == '/':
            if l.uid == r.uid:
                return Const(1)

        return BinOp(l, self.op, r)

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        """
        Substitution
        :param mapping: mapping of variables to expressions
        :return:
        """
        if self in mapping:
            return mapping[self]
        return BinOp(self.left.subs(mapping), self.op, self.right.subs(mapping))

    def __str__(self) -> str:
        return f"({self.left}) {self.op} ({self.right})"

    def __repr__(self) -> str:
        return self.__str__()

    def to_dict(self) -> Dict[str, Any]:
        """

        :return:
        """
        d = super().to_dict()
        d["type"] = "BinOp"
        d["op"] = self.op
        d["left"] = self.left.to_dict()
        d["right"] = self.right.to_dict()
        return d


class UnOp(Expr):
    """
    Unary operation expression
    """

    __slots__ = ("op", "operand",)

    def __init__(self, op: str, operand: Expr, uid: int | None = None):
        """

        :param op:
        :param operand:
        :param uid:
        """
        super().__init__(uid=uid)
        self.op: str = op
        self.operand = operand

    def eval(self, **bindings: NUMBER) -> NUMBER:
        """

        :param bindings:
        :return:
        """
        val = self.operand.eval(**bindings)
        return -val if self.op == "-" else math.nan

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:
        """

        :param uid_bindings:
        :return:
        """
        val = self.operand.eval_uid(uid_bindings)
        if self.op == "-":
            return -val
        else:
            raise Exception(f"Unknown operand {self.op}")

    def _diff1(self, var: Var | str) -> "Expr":
        """

        :param var:
        :return:
        """
        if self.op == "-":
            return -self.operand._diff1(var)
        else:
            raise Exception(f"Unknown operand {self.op}")

    def simplify(self) -> Expr:
        """

        :return:
        """
        opr = self.operand.simplify()
        if isinstance(opr, Const):
            return Const(-opr.value)
        return UnOp(self.op, opr)

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        """

        :param mapping:
        :return:
        """
        if self in mapping:
            return mapping[self]
        return UnOp(self.op, self.operand.subs(mapping))

    def __str__(self) -> str:
        return f"{self.op}({self.operand})"

    def __repr__(self) -> str:
        return self.__str__()

    def to_dict(self) -> Dict[str, Any]:
        """

        :return:
        """
        d = super().to_dict()
        d["type"] = "UnOp"
        d["op"] = self.op
        d["operand"] = self.operand.to_dict()
        return d


# ----------------------------------------------------------------------------------------------------------------------
# Functional nodes
# ----------------------------------------------------------------------------------------------------------------------
@nb.njit
def _heaviside(x):
    return 0.0 if x <= 0 else 1.0


functions_dict: Mapping[str, Callable[[NUMBER], NUMBER]] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": np.exp,
    "log": math.log,
    "sqrt": math.sqrt,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "real": np.real,
    "imag": np.imag,
    "conj": np.conj,
    "angle": np.angle,
    "abs": np.abs,
    "heaviside": _heaviside
}


class PrimaryFunction(Expr):
    __slots__ = ("op", "arg", "fn", "fnd")

    def __init__(self, arg: Expr, op: str = "", uid: int | None = None):
        """

        :param op:
        :param uid:
        """
        super().__init__(uid=uid)
        self.op: str = op
        self.arg: Expr = arg

        self.fn: Callable[[NUMBER], NUMBER] = functions_dict[self.op]

    # --- evaluation ----------------------------------------------------------
    def eval(self, **bindings: NUMBER) -> NUMBER:
        return self.fn(self.arg.eval(**bindings))

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:
        return self.fn(self.arg.eval_uid(uid_bindings))

    def to_dict(self) -> Dict[str, Any]:
        """

        :return:
        """
        d = super().to_dict()
        d["type"] = "Func"
        d["op"] = self.op
        d["arg"] = self.arg.to_dict()
        return d


def abs(x: Expr):  # TODO: Rename to not shadow
    return PrimaryFunction(_to_expr(x), "abs")


def real(x: Expr):
    return PrimaryFunction(_to_expr(x), "real")


def imag(x: Expr):
    return PrimaryFunction(_to_expr(x), "imag")


def conj(x: Expr):
    return PrimaryFunction(_to_expr(x), "conj")


def angle(x: Expr):
    return PrimaryFunction(_to_expr(x), "angle")


def sin(x: Expr):
    return PrimaryFunction(_to_expr(x), "sin")


def sin_diff(u: Expr, du: Expr) -> Expr:
    return cos(u) * du


def cos(x: Expr):
    return PrimaryFunction(_to_expr(x), "cos")


def cos_diff(u: Expr, du: Expr) -> Expr:
    return -sin(u) * du


def sec(x: Any) -> Expr:
    return Const(1) / cos(x)


def tan(x: Expr):
    return PrimaryFunction(_to_expr(x), "tan")


def tan_diff(u: Expr, du: Expr):
    return (sec(u) ** Const(2)) * du


def exp(x: Expr):
    return PrimaryFunction(_to_expr(x), "exp")


def exp_diff(u: Expr, du: Expr):
    return exp(u) * du


def log(x: Expr):
    return PrimaryFunction(_to_expr(x), "log")


def log_diff(u: Expr, du: Expr):
    return du / u


def sqrt(x: Expr):
    return PrimaryFunction(_to_expr(x), "sqrt")


def sqrt_diff(u: Expr, du: Expr):
    return du / (Const(2) * sqrt(u))


def asin(x: Expr):
    return PrimaryFunction(_to_expr(x), "asin")


def asin_diff(u: Expr, du: Expr) -> Expr:
    return du / sqrt(Const(1) - u ** Const(2))


def acos(x: Expr):
    return PrimaryFunction(_to_expr(x), "acos")


def acos_diff(u: Expr, du: Expr) -> Expr:
    return -du / sqrt(Const(1) - u ** Const(2))


def atan(x: Expr):
    return PrimaryFunction(_to_expr(x), "atan")


def atan_diff(u: Expr, du: Expr) -> Expr:
    return du / (Const(1) + u ** Const(2))


def sinh(x: Expr):
    return PrimaryFunction(_to_expr(x), "sinh")


def cosh(x: Expr):
    return PrimaryFunction(_to_expr(x), "cosh")


def sinh_diff(u: Expr, du: Expr) -> Expr:
    return cosh(u) * du


def cosh_diff(u: Expr, du: Expr) -> Expr:
    return sinh(u) * du


def heaviside(x: Expr):
    return PrimaryFunction(_to_expr(x), "heaviside")


def heaviside_diff(u: Expr, du: Expr) -> Expr:
    return du * u


def max(x: Expr, y: Expr) -> Expr:
    return x * heaviside((x - y)) + y * (Const(1) - heaviside((x - y)))


def min(x: Expr, y: Expr) -> Expr:
    return x * heaviside(y - x) + y * (Const(1) - heaviside(y - x))


def hard_sat(x: Expr, x_min: Expr | float, x_max: Expr | float) -> Expr:
    return x_min + (x - x_min) * heaviside(x - x_min) - (x - x_max) * heaviside(x - x_max)


def f_exc(In: Expr) -> Expr:
    b = ((Const(1) - Const(0.577) * In) - (sqrt(Const(0.75) - In ** 2 + Const(1e-5)))) * heaviside(Const(0.433) - In)
    c = ((sqrt(Const(0.75) - In ** 2 + Const(1e-5)) - (Const(1.732) - In * Const(1.732))) * heaviside(Const(0.75) - In))
    d = (Const(1.732) - In * Const(1.732)) * (Const(1) * heaviside(Const(1.0) - In))

    return b + c + d


def piecewise(time: Expr, t_events: np.ndarray, new_values: np.ndarray, default_value: Any) -> Expr:
    """
    Symbolic piecewise function.
    Returns default_value before the first event, then switches to
    corresponding new_values after each t_event.

    Parameters
    ----------
    time : Expr
        Symbolic time expression
    t_events : np.ndarray
        1D array of event times (must be sorted ascending)
    new_values : np.ndarray
        1D array of values after each event time
    default_value : Any
        Value before the first event
    """
    t_expr = _to_expr(time)
    result = _to_expr(default_value)

    for t_event, new_value in zip(t_events, new_values):
        step = heaviside(t_expr - Const(t_event))
        result = step * _to_expr(new_value) + (Const(1) - step) * result

    return result


functions_diff_dict: Mapping[str, Callable[[Expr, Expr], Expr]] = {
    "sin": sin_diff,
    "cos": cos_diff,
    "tan": tan_diff,
    "exp": exp_diff,
    "log": log_diff,
    "sqrt": sqrt_diff,
    "asin": asin_diff,
    "acos": acos_diff,
    "atan": atan_diff,
    "sinh": sinh_diff,
    "cosh": cosh_diff,
    "heaviside": heaviside_diff
}


class Func(PrimaryFunction):
    __slots__ = ("op", "arg", "fn", "fnd")

    def __init__(self, arg: Expr, op: str = "", uid: int | None = None):
        """

        :param op:
        :param uid:
        """
        super().__init__(arg=arg, op=op, uid=uid)

        # optional derivative function pointer
        self.fnd: Callable[[Expr, Expr], Expr] = functions_diff_dict.get(self.op, None)

    # --- evaluation ----------------------------------------------------------
    def eval(self, **bindings: NUMBER) -> NUMBER:
        return self.fn(self.arg.eval(**bindings))

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:
        return self.fn(self.arg.eval_uid(uid_bindings))

    # --- differentiation (chain rule) ---------------------------------------
    def _diff1(self, var: Var | str) -> "Expr":
        u = self.arg
        du = u._diff1(var)
        if isinstance(du, Const) and du.value == 0:
            return Const(0)
        else:
            if self.fnd is not None:
                self.fnd(u, du)
            else:
                raise Exception(f"No derivative defined for {self.op}")

    # --- simplification ------------------------------------------------------
    def simplify(self) -> "Expr":
        a = self.arg.simplify()
        if isinstance(a, Const):
            try:
                return Const(self.fn(a.value))
            except ValueError:
                pass  # domain error – keep symbolic
        return Func(a, self.op)

    def subs(self, mapping: Dict[Any, "Expr"]) -> "Expr":
        if self in mapping:
            return mapping[self]
        return Func(self.arg.subs(mapping), self.op)

    def __str__(self) -> str:
        return f"{self.op}({self.arg})"

    def __repr__(self) -> str:
        return self.__str__()


@dataclass(frozen=True)
class Func2(Expr):
    name: str
    arg1: Expr
    arg2: Expr
    uid: int = field(default_factory=_new_uid, init=False)

    _impl: ClassVar[Mapping[str, Callable[[NUMBER, NUMBER], NUMBER]]] = MappingProxyType({
        "atan2": np.atan2,
        "min": np.minimum,
        "max": np.maximum,
    })

    def eval(self, **bindings: NUMBER) -> NUMBER:
        return self._impl[self.name](
            self.arg1.eval(**bindings),
            self.arg2.eval(**bindings),
        )

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:
        return self._impl[self.name](
            self.arg1.eval_uid(uid_bindings),
            self.arg2.eval_uid(uid_bindings),
        )

    def _diff1(self, var: Var | str) -> Expr:
        x = self.arg1
        y = self.arg2

        dx = x._diff1(var)
        dy = y._diff1(var)

        # short-circuit: constant
        if (
                isinstance(dy, Const) and dy.value == 0 and
                isinstance(dx, Const) and dx.value == 0
        ):
            return Const(0)

        if self.name == "atan2":
            return (x * dy - y * dx) / (x ** Const(2) + y ** Const(2))
        if self.name == "min":
            return heaviside(x - y) * dx + heaviside(x - y) * dy
        if self.name == "max":
            return heaviside(y - x) * dx + heaviside(x - y) * dy

        raise ValueError(f"Unknown binary function '{self.name}'")

    # --- simplification ------------------------------------------------------
    def simplify(self) -> "Expr":
        a_s = self.arg1.simplify()
        b_s = self.arg2.simplify()

        # constant folding
        if isinstance(a_s, Const) and isinstance(b_s, Const):
            try:
                return Const(Func2._impl[self.name](a_s.value, b_s.value))
            except ValueError:
                pass  # domain error – keep symbolic

        # min(x, x) → x ; max(x, x) → x
        if (a_s == b_s) and self.name in ("min", "max"):
            return a_s

        # return simplified symbolic form
        return Func2(self.name, a_s, b_s)

    def subs(self, mapping: Dict[Any, "Expr"]) -> "Expr":
        if self in mapping:
            return mapping[self]
        return Func2(
            self.name,
            self.arg1.subs(mapping),
            self.arg2.subs(mapping),
        )

    def __str__(self) -> str:
        return f"{self.name}({self.arg1}, {self.arg2})"

    def __repr__(self) -> str:
        return self.__str__()


# -----------------------------------------------------------------------------
# Public constructor helpers
# -----------------------------------------------------------------------------


# def _expr_to_dict(expr: Expr) -> Dict[str, Any]:
#     """
#     Serialise any `Expr` tree into a plain Python dictionary that’s
#     JSON-friendly.  Each node type becomes a small dict that records:
#
#         • its own type      (\"Const\", \"Var\", \"BinOp\", …)
#         • the data it carries (value, name, operator…)
#         • its unique uid     (string, so it survives round-trip)
#         • nested children    (recursively serialised)
#
#     The reverse operation is handled by `_dict_to_expr`.
#     """
#     # ------------------------------------------------------------------
#     # Atomic nodes
#     # ------------------------------------------------------------------
#     if isinstance(expr, Const):
#         val = expr.value
#         if isinstance(val, complex):
#             return {"type": "Const", "value": [val.real, val.imag], "kind": "complex", "uid": expr.uid}
#         if val is UNDEFINED:
#             return {"type": "Const", "value": None, "kind": "undefined", "uid": expr.uid}
#         return {"type": "Const", "value": expr.value, "uid": expr.uid}
#
#     if isinstance(expr, Var) and not isinstance(expr, DiffVar):
#         return {"type": "Var", "name": expr.name, "uid": expr.uid}
#
#     if isinstance(expr, DiffVar):
#         return {"type": "DiffVar",
#                 "name": expr.name,
#                 "uid": expr.uid,
#                 "base_var": _expr_to_dict(expr.base_var),
#                 }
#
#     # ------------------------------------------------------------------
#     # Composite nodes
#     # ------------------------------------------------------------------
#     if isinstance(expr, BinOp):
#         return {
#             "type": "BinOp",
#             "op": expr.op,
#             "left": _expr_to_dict(expr.left),
#             "right": _expr_to_dict(expr.right),
#             "uid": expr.uid,
#         }
#
#     if isinstance(expr, UnOp):
#         return {
#             "type": "UnOp",
#             "op": expr.op,  # only \"-\" for now
#             "operand": _expr_to_dict(expr.operand),
#             "uid": expr.uid,
#         }
#
#     if isinstance(expr, Func):
#         return {
#             "type": "Func",
#             "name": expr.name,  # sin, cos, log, …
#             "arg": _expr_to_dict(expr.arg),
#             "uid": expr.uid,
#         }
#
#     # ------------------------------------------------------------------
#     # Anything else is an API bug
#     # ------------------------------------------------------------------
#     raise TypeError(f"Unsupported Expr subclass: {type(expr).__name__}")


def _dict_to_expr(data: Dict[str, Any]) -> Expr:
    """
    De-Serialize expression from dictionary
    :param data:
    :return:
    """
    t = data["type"]
    if t == "Const":
        if data.get("kind") == "complex":
            arr = data["value"]
            obj = Const(complex(arr[0], arr[1]))
        elif data.get("kind") == "undefined":
            obj = Const()
        else:
            obj = Const(data["value"])
    elif t == "Var":
        obj = Var(data["name"])

    elif t == "DiffVar":

        # reconstruct base_var
        base_data = data["base_var"]
        base_var = _dict_to_expr(base_data)
        if not isinstance(base_var, Var):
            raise TypeError("base_var must be a Var")

        obj = DiffVar(name=data["name"], base_var=base_var)

        # registry_data = data["registry"]
        # for base_uid, dv_info in registry_data.items():
        #     bvar = Var(dv_info["name"], uid=dv_info["base_uid"])
        #     dv = DiffVar(name=dv_info["name"], base_var=bvar, uid=dv_info["uid"])
        #     object.__setattr__(dv, "uid", dv_info["uid"])
        #     DiffVar._registry[dv_info["base_uid"]] = dv
        #
        # abs_data = data.get("absolute_registry", {})
        # for key_str, dv_uid in abs_data.items():
        #     origin_uid, order = map(int, key_str.split(","))
        #     dv = next((v for v in DiffVar._registry.values() if v.uid == dv_uid), None)
        #     if dv is not None:
        #         DiffVar._absolute_registry[(origin_uid, order)] = dv

    elif t == "BinOp":
        obj = BinOp(_dict_to_expr(data["left"]), data["op"], _dict_to_expr(data["right"]))

    elif t == "UnOp":
        obj = UnOp(data["op"], _dict_to_expr(data["operand"]))

    elif t == "Func":
        op = data.get("op", None)
        if op is None:
            op = data["name"]
        obj = Func(_dict_to_expr(data["arg"]), op)

    else:
        raise ValueError(f"Unknown type '{t}' in deserialisation")

    object.__setattr__(obj, "uid", data["uid"])
    return obj


# ----------------------------------------------------------------------------------------------------------------------
# Convenience top‑level helpers
# ----------------------------------------------------------------------------------------------------------------------

def diff(expr: Expr, var: Var | str, order: int = 1) -> Expr:  # noqa: D401 – simple
    """
    Return ∂^order(expr)/∂var^order.
    :param expr: Expression
    :param var: Variable to differentiate against
    :param order: Derivative order
    :return: Derivative expression
    """
    return expr.diff(var, order)


def eval_uid(expr: Expr, uid_bindings: Dict[str, NUMBER]) -> NUMBER:  # noqa: D401 – simple
    """
    Evaluate *expr* with a mapping from node UID → numeric value.
    :param expr:
    :param uid_bindings:
    :return:
    """
    return expr.eval_uid(uid_bindings)


def _collect_vars(expr: Expr, out: Set[Var]) -> None:
    """
    Collect variables in a deterministic order
    Depth-first, left-to-right variable harvest.
    :param expr: Some expression
    :param out: List to fill
    :return: None
    """
    if isinstance(expr, Var):
        if expr not in out:
            out.add(expr)
    elif isinstance(expr, BinOp):
        _collect_vars(expr.left, out)
        _collect_vars(expr.right, out)
    elif isinstance(expr, UnOp):
        _collect_vars(expr.operand, out)
    elif isinstance(expr, Func):
        _collect_vars(expr.arg, out)


def _all_vars(expressions: Sequence[Expr]) -> List[Var]:
    """
    Collect all variables in a list of expressions
    :param expressions: Any iterable of expressions
    :return: List of non-repeated variables
    """
    res: Set[Var] = set()
    for e in expressions:
        _collect_vars(e, res)
    return list(res)


def expression2numba(expr: Expr,
                     uid_map_vars: Dict[int, str],
                     uid_map_event_params: Dict[int, str],
                     uid_map_params: Dict[int, str]) -> str:
    """
    Create a pure-Python (Numba-friendly) expression string for the function compilation
    :param expr: Expr (expression)
    :param uid_map_vars: relate UID with compilation name i.e. {1: "vars[1]", 2: vars[2], ...}
    :param uid_map_event_params: relate UID with compilation name i.e. {1: "event[1]", 2: event[2], ...}
    :param uid_map_params:  relate UID with fixed param compilation name i.e. {1: "param[1]", 2: param[2], ...}
    :return: string expression
    """

    if isinstance(expr, Const):
        return repr(expr.value)

    if isinstance(expr, Var):
        if expr.uid in uid_map_vars.keys():
            return uid_map_vars[expr.uid]  # positional variable
        elif expr.uid in uid_map_params.keys():
            return uid_map_params[expr.uid]
        elif expr.uid in uid_map_event_params.keys():
            return uid_map_event_params[expr.uid]
        else:
            raise ValueError(f'{expr} not found')

    if isinstance(expr, UnOp):
        return f"-({expression2numba(expr.operand, uid_map_vars, uid_map_event_params, uid_map_params)})"

    if isinstance(expr, BinOp):
        return (f"({expression2numba(expr.left, uid_map_vars, uid_map_event_params, uid_map_params)} "
                f"{expr.op} "
                f"{expression2numba(expr.right, uid_map_vars, uid_map_event_params, uid_map_params)})")

    if isinstance(expr, Func):
        # if expr.op in ("real", "imag", "conj", "angle", "sin", "cos", "tan",
        #                "exp", "log", "sqrt", "asin", "acos", "atan", "atan2",
        #                "sinh", "cosh", "abs"):
        #     return f"np.{expr.op}({_emit(expr.arg, uid_map_vars, uid_map_event_params, uid_map_params)})"
        if expr.op == "heaviside":
            return f"_heaviside({expression2numba(expr.arg, uid_map_vars, uid_map_event_params, uid_map_params)})"
        else:
            return f"np.{expr.op}({expression2numba(expr.arg, uid_map_vars, uid_map_event_params, uid_map_params)})"

    raise TypeError(type(expr))


def _emit_event_params_eq(expr: Expr, uid_map_t: Dict[int, str] = None) -> str:
    """
    TODO: proper docstring
    Emit a pure-Python (Numba-friendly) expression string
    :param expr: Expr (expression)
    :param uid_map_t:
    :return:
    """

    if isinstance(expr, Const):
        return repr(expr.value)

    if isinstance(expr, Var):
        if expr.uid in uid_map_t.keys():
            return uid_map_t[expr.uid]

    if isinstance(expr, UnOp):
        return f"-({_emit_event_params_eq(expr.operand, uid_map_t)})"

    if isinstance(expr, BinOp):
        return f"({_emit_event_params_eq(expr.left, uid_map_t)} {expr.op} {_emit_event_params_eq(expr.right, uid_map_t)})"

    if isinstance(expr, Func):
        # Use numpy functions for standard numeric functions
        # if expr.op in ("real", "imag", "conj", "angle", "sin", "cos", "tan",
        #                  "exp", "log", "sqrt", "asin", "acos", "atan", "atan2",
        #                  "sinh", "cosh", "abs"):
        #
        if expr.op == "heaviside":
            return f"_heaviside({_emit_event_params_eq(expr.arg, uid_map_t)})"
        else:
            return f"np.{expr.op}({_emit_event_params_eq(expr.arg, uid_map_t)})"
    else:
        raise ValueError(f"Unknown function '{expr.name}' in _emit_params_eq")


def _emit_one(expr: Expr, uid_map_vars: Dict[int, str], uid_map_event_params: Dict[int, str],
              uid_map_params: Dict[int, str]) -> str:
    """
    Emit a pure-Python (Numba-friendly) expression string
    :param expr: Expr (expression)
    :param uid_map_vars:
    :return:
    """
    if isinstance(expr, Const):
        return repr(expr.value)

    if isinstance(expr, Var):
        if expr.uid in uid_map_vars.keys():
            return uid_map_vars[expr.uid]  # positional variable
        elif expr.uid in uid_map_event_params.keys():
            return uid_map_event_params[expr.uid]  # positional variable
        else:
            return uid_map_params[expr.uid]

    if isinstance(expr, UnOp):
        return f"-({_emit_one(expr.operand, uid_map_vars, uid_map_event_params, uid_map_params)})"

    if isinstance(expr, BinOp):
        return (f"({_emit_one(expr.left, uid_map_vars, uid_map_event_params, uid_map_params)} "
                f"{expr.op} {_emit_one(expr.right, uid_map_vars, uid_map_event_params, uid_map_params)})")

    if isinstance(expr, Func):
        # if expr.name in ("real", "imag", "conj", "angle", "sin", "cos", "atan",
        #                  "exp", "log", "sqrt", "asin", "acos", "atan", "atan2",
        #                  "sinh", "cosh", "abs"):
        #
        if expr.op == "heaviside":
            return f"_heaviside({_emit_one(expr.arg, uid_map_vars, uid_map_event_params, uid_map_params)})"
        else:
            return f"np.{expr.op}({_emit_one(expr.arg, uid_map_vars, uid_map_event_params, uid_map_params)})"

    raise TypeError(expr)


def find_vars_order(expressions: Union[Expr, Sequence[Expr]],
                    ordering: Sequence[Var] | None = None,
                    var_dict: Dict[int, Var] | None = None) -> List[Var]:
    """
    Return the variable list that positional JIT functions will expect.
    :param expressions: Single expression or any iterable of expressions.
    :param ordering: Is provided, it overrides the default left‑to‑right order.
                    Items in *ordering* can be Var objects or variable names (strings).
    :param var_dict: Dictionary of var uid to var ({v.uid: v for v in vars_list})
    :return:
    """

    if isinstance(expressions, Expr):

        vars_list = _all_vars([expressions])
    else:
        vars_list = _all_vars(expressions)

    if ordering is None:
        return vars_list

    if var_dict is None:
        var_dict: Dict[int, Var] = {v.uid: v for v in vars_list}

    return [v if isinstance(v, Var) else var_dict[v.uid] for v in ordering]


# mapping of Python operator nodes → our BinOp symbols
# TODO: eliminate with all its consequences -> Marina
_BINOP_MAP = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.Pow: "**",
}

# TODO: eliminate with all its consequences -> Marina
_UNOP_MAP = {
    ast.USub: "-",
}

# mapping of allowed function names → our constructor functions
# TODO: eliminate with all its consequences -> Marina
_FUNC_MAP = {
    "sin": sin,
    "cos": cos,
    "tan": tan,
    "exp": exp,
    "log": log,
    "sqrt": sqrt,
    "asin": asin,
    "acos": acos,
    "atan": atan,
    "sinh": sinh,
    "cosh": cosh,
    # "real": real,
    # "imag": imag,
    # "conj": conj,
    # "angle": angle,
    # "abs": abs,  #
    "heaviside": heaviside,
    "_dict_to_expression": _dict_to_expr
}


# TODO: eliminate with all its consequences -> Marina
def make_symbolic(expr_str: str, variables: Dict[str, Var] | None = None) -> Expr:
    """
    Parse a string like "sin(x) + 2*y" into a symbolic Expr tree.
    variables: optional mapping of variable names -> Var. If None, new Var is created.
    """
    tree = ast.parse(expr_str, mode="eval").body

    def _convert(node: ast.AST) -> Expr:
        # if isinstance(node, ast.Num):  # Python <3.8
        #     return Const(node.n)
        if isinstance(node, ast.Constant):  # Python 3.8+
            if isinstance(node.value, (int, float, complex)):
                return Const(node.value)
            raise TypeError(f"Unsupported constant: {node.value}")
        if isinstance(node, ast.Name):
            if variables is not None and node.id in variables:
                return variables[node.id]
            return Var(node.id)
        if isinstance(node, ast.BinOp):
            op = _BINOP_MAP.get(type(node.op))
            if op is None:
                raise TypeError(f"Unsupported binary operator {node.op}")
            return BinOp(_convert(node.left), op, _convert(node.right))
        if isinstance(node, ast.UnaryOp):
            op = _UNOP_MAP.get(type(node.op))
            if op is None:
                raise TypeError(f"Unsupported unary operator {node.op}")
            return UnOp(op, _convert(node.operand))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise TypeError("Only simple function calls allowed")
            fname = node.func.id
            if fname not in _FUNC_MAP:
                raise ValueError(f"Unknown function '{fname}'")
            if len(node.args) != 1:
                raise ValueError(f"Function '{fname}' takes one argument")
            return _FUNC_MAP[fname](_convert(node.args[0]))
        raise TypeError(f"Unsupported expression: {ast.dump(node)}")

    return _convert(tree)


def symbolic_to_string(expr: Expr) -> str:
    """
    Convert a symbolic expression into a string (parsable by parse_expr).
    """
    if isinstance(expr, Const):
        return str(expr.value)
    elif isinstance(expr, Var):
        return expr.name
    elif isinstance(expr, UnOp):
        if expr.op == "-":
            return f"-({symbolic_to_string(expr.operand)})"
        return f"{expr.op}({symbolic_to_string(expr.operand)})"
    elif isinstance(expr, BinOp):
        left = symbolic_to_string(expr.left)
        right = symbolic_to_string(expr.right)
        return f"({left} {expr.op} {right})"
    elif isinstance(expr, Func):
        return f"{expr.op}({symbolic_to_string(expr.arg)})"
    elif isinstance(expr, Comparison):
        left = symbolic_to_string(expr.lhs)
        right = symbolic_to_string(expr.rhs)
        return f"({left} {expr.op} {right})"
    else:
        raise TypeError(f"Unsupported expression type: {type(expr)}")


# -----------------------------------------------------------------------------
# Public interface
# -----------------------------------------------------------------------------

__all__ = [
    "Expr", "Const", "Var", "BinOp", "UnOp", "Func", "CmpOp", "Comparison", "LagVar", "DiffVar",
    "sin", "cos", "tan", "exp", "log", "sqrt",
    "asin", "acos", "atan", "sinh", "cosh",
    "diff", "eval_uid",
    "find_vars_order",
    "heaviside",
    "piecewise",
    "symbolic_to_string",
    "make_symbolic",
    "DiffVar",
    "hard_sat",
    "f_exc",
    'expression2numba',
    '_emit_event_params_eq',
    '_heaviside'
]
#
# x = Var("x")
# y = Var("y")
#
# expr1 = make_symbolic("sin(x) + 2*y", {"x": x, "y": y})
# print(expr1)  # sin(x) + (2 * y)
#
# # You can also create new Vars on the fly:
# expr2 = make_symbolic("exp(z) + 3")
# print(expr2)  # exp(z) + 3
