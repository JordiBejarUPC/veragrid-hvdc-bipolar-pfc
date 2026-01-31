# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Module: JIT Equation Compiler & Numerical Discretization Engine
===============================================================

Abstract
--------
This module implements a symbolic-to-numeric translation engine designed to generate
optimized executable kernels for Differential-Algebraic Equation (DAE) systems.
It operates by traversing the symbolic Abstract Syntax Tree (AST) of the model and
injecting discrete time-stepping schemes (e.g., Implicit Trapezoidal, BDF2) directly
into the residual evaluation code.

Architectural Rationale
-----------------------
The decoupling of the compilation logic from the `DiffBlockSolver` enforces a strict
separation of concerns between the network topology management (Solver) and the
numerical discretization strategy (Compiler). This abstraction allows for the
interchangeability of integration methods—facilitating the switch between A-stable
and L-stable schemes—without altering the solver's core iterative algorithms.

Performance Optimization
------------------------
By fusing the physical model equations with the numerical integration formulas into
a single JIT-compiled kernel, this module eliminates the interpreter overhead and
intermediate memory allocations typical of vectorized Numpy operations. This results
in a monolithic residual evaluation function optimized for the high-frequency
computation requirements of Electromagnetic Transient (EMT) simulations.
"""

import math
import numpy as np
from abc import ABC, abstractmethod
from typing import Any,Dict, List, Callable
import hashlib

from VeraGridEngine.Utils.Symbolic.symbolic import Expr, BinOp, UnOp, Func, Var, Const, DiffVar, LagVar


# ==============================================================================
# 1. Discretization strategy (Numerical Methods)
# ==============================================================================
class DiscretizationMethod(ABC):
    """Abstract base class for discretization strategies."""

    @abstractmethod
    def discretize(self, state_idx: int, h_var: str = 'h') -> str:
        pass

    @abstractmethod
    def discretize_dot(self, state_idx: int, h_var: str = 'h', seeds_var: str = 'seeds') -> str:
        pass


class TrapezoidalMethod(DiscretizationMethod):
    def discretize(self, state_idx: int, h_var: str = 'h') -> str:
        return f"((2.0/{h_var}) * (states[{state_idx}] - history[{state_idx}]) - d_history[{state_idx}])"

    def discretize_dot(self, state_idx: int, h_var: str = 'h', seeds_var: str = 'seeds') -> str:
        return f"((2.0/{h_var}) * ({seeds_var}[{state_idx}]))"


class BackwardEulerMethod(DiscretizationMethod):
    def discretize(self, state_idx: int, h_var: str = 'h') -> str:
        return f"((states[{state_idx}] - history[{state_idx}]) / {h_var})"

    def discretize_dot(self, state_idx: int, h_var: str = 'h', seeds_var: str = 'seeds') -> str:
        return f"(({seeds_var}[{state_idx}]) / {h_var})"


class BDF2Method(DiscretizationMethod):
    def discretize(self, state_idx: int, h_var: str = 'h') -> str:
        return f"((1.5*states[{state_idx}] - 2.0*history[{state_idx}] + 0.5*history2[{state_idx}]) / {h_var})"

    def discretize_dot(self, state_idx: int, h_var: str = 'h', seeds_var: str = 'seeds') -> str:
        return f"((1.5*{seeds_var}[{state_idx}]) / {h_var})"


# ==============================================================================
# 2. CSE (Common Subexpression Elimination) Analyzer (large systems)
# ==============================================================================
class SubexpressionAnalyzer:
    """
    Find and catalog subexpressions that appear multiple times.

    Algorithm:
    1. Traverse the AST of each equation
    2. Generate a unique hash for each subexpression
    3. Count occurrences
    4. Assign temporary variables to frequent expressions
    """

    def __init__(self, threshold: int = 2):
        """
        :param threshold: Minimum number of occurrences to consider CSE
        """
        self.threshold = threshold
        self.expr_counts: Dict[str, int] = {}
        self.expr_objects: Dict[str, Expr] = {}
        self.expr_complexity: Dict[str, int] = {}

    def analyze(self, equations: List[Expr]) -> Dict[str, str]:
        """
        Returns hash mapping -> temporary_variable_name.
        """
        # Reset
        self.expr_counts.clear()
        self.expr_objects.clear()
        self.expr_complexity.clear()

        # First pass: counting
        for eq in equations:
            self._count_subexpressions(eq)

        # Second pass: assign temporary variables
        # Sort by profit (count * complexity)
        candidates = []
        for expr_hash, count in self.expr_counts.items():
            if count >= self.threshold:
                complexity = self.expr_complexity[expr_hash]
                benefit = count * complexity
                candidates.append((benefit, expr_hash))

        candidates.sort(reverse=True)

        # Assign names
        temp_vars = {}
        for i, (_, expr_hash) in enumerate(candidates):
            temp_vars[expr_hash] = f"_t{i}"

        return temp_vars

    def _count_subexpressions(self, node: Expr, depth: int = 0):
        """Traverse the AST counting nodes."""
        # Ignore trivial nodes
        if isinstance(node, (Const, Var)):
            return

        # DiffVar is special—we don't count it as a CSE candidate.
        if isinstance(node, DiffVar):
            return

        # Calculate complexity (number of operations)
        complexity = self._calculate_complexity(node)

        # We only consider expressions with complexity > 1
        if complexity > 1:
            expr_hash = self._hash_expr(node)
            self.expr_counts[expr_hash] = self.expr_counts.get(expr_hash, 0) + 1
            self.expr_objects[expr_hash] = node
            self.expr_complexity[expr_hash] = complexity

        # Recursion
        if isinstance(node, BinOp):
            self._count_subexpressions(node.left, depth + 1)
            self._count_subexpressions(node.right, depth + 1)
        elif isinstance(node, UnOp):
            self._count_subexpressions(node.operand, depth + 1)
        elif isinstance(node, Func):
            self._count_subexpressions(node.arg, depth + 1)

    def _calculate_complexity(self, node: Expr) -> int:
        """Estimate the computational cost of an expression."""
        if isinstance(node, (Const, Var, DiffVar)):
            return 0
        elif isinstance(node, BinOp):
            # Multiplication/division cost more than addition/subtraction.
            op_cost = 2 if node.op in ['*', '/', '**'] else 1
            return op_cost + self._calculate_complexity(node.left) + \
                self._calculate_complexity(node.right)
        elif isinstance(node, UnOp):
            return 1 + self._calculate_complexity(node.operand)
        elif isinstance(node, Func):
            return 5 + self._calculate_complexity(node.arg)
        return 1

    def _hash_expr(self, node: Expr) -> str:
        """Generates a unique hash based on structure."""
        canonical = self._expr_to_canonical_string(node)
        return hashlib.md5(canonical.encode()).hexdigest()[:12]

    def _expr_to_canonical_string(self, node: Expr) -> str:
        """Converts expression to canonical representation."""
        if isinstance(node, Const):
            return f"C{node.value}"
        elif isinstance(node, Var):
            return f"V{node.name}"
        elif isinstance(node, DiffVar):
            return f"D{node.base_var.name}"
        elif isinstance(node, BinOp):
            left = self._expr_to_canonical_string(node.left)
            right = self._expr_to_canonical_string(node.right)
            # Normalize commutative operations
            if node.op in ['+', '*']:
                if left > right:
                    left, right = right, left
            return f"({left}{node.op}{right})"
        elif isinstance(node, UnOp):
            operand = self._expr_to_canonical_string(node.operand)
            return f"{node.op}{operand}"
        elif isinstance(node, Func):
            return f"{node.op}({self._expr_to_canonical_string(node.arg)})"
        elif isinstance(node, LagVar):
            return f"L{node.lag}{node.base_var.name}"
        return str(node)


# ==============================================================================
# 3. Conversion to string based on visitor pattern (sequentiality)
# ==============================================================================

class SymbolicToPythonVisitor:
    OP_PRECEDENCE = {'+': 10, '-': 10, '*': 20, '/': 20, '**': 30}

    def __init__(self, var_map: Dict[int, int], param_map: Dict[int, int], method: DiscretizationMethod):
        self.var_map = var_map
        self.param_map = param_map or {}
        self.method = method
        self.cse_map = {}
        self.analyzer = None
        self.in_cse_def = False

    def visit(self, node: Expr, precedence: int = 0) -> str:
        # CSE Check
        if self.analyzer and self.cse_map and not self.in_cse_def:
            if not isinstance(node, (Var, Const, DiffVar, LagVar)):
                h = self.analyzer._hash_expr(node)
                if h in self.cse_map:
                    return self.cse_map[h]

        # Double Dispatch: Redirect PrimaryFunction to visit_Func
        if isinstance(node, Func):
            type_name = 'Func'
        else:
            type_name = type(node).__name__

        visitor = getattr(self, f'visit_{type_name}', self.generic_visit)
        return visitor(node, precedence)

    def generic_visit(self, node, _):
        raise NotImplementedError(f"Node not supported: {type(node)}")

    def visit_BinOp(self, node: BinOp, prec: int) -> str:
        curr_prec = self.OP_PRECEDENCE.get(node.op, 0)
        l = self.visit(node.left, curr_prec)
        r = self.visit(node.right, curr_prec)
        code = f"{l} {node.op} {r}"
        return f"({code})" if curr_prec < prec else code

    def visit_UnOp(self, node: UnOp, _) -> str:
        return f"{node.op}{self.visit(node.operand, 100)}"

    def visit_Const(self, node: Const, _) -> str:
        return str(node.value)

    def visit_Var(self, node: Var, _) -> str:
        if node.uid in self.var_map: return f"states[{self.var_map[node.uid]}]"
        if node.uid in self.param_map: return f"params[{self.param_map[node.uid]}]"

        raise ValueError(f"Variable '{node.name}' (UID: {node.uid}) Not mapped in compiler.")

    def visit_DiffVar(self, node: DiffVar, prec: int) -> str:
        base_uid = node.base_var.uid
        if base_uid not in self.var_map:
            raise ValueError(f"Base var '{node.base_var.name}' (UID: {base_uid})"
                             f" for DiffVar does not exist in states.")

        term = self.method.discretize(self.var_map[base_uid])
        return f"({term})" if prec > 10 else term

    def visit_Func(self, node: Func, _) -> str:
        arg = self.visit(node.arg, 0)

        op = node.op
        if op == 'heaviside':
            return f"_heaviside({arg})"
        if op == 'abs':
            return f"np.abs({arg})"

        return f"np.{op}({arg})"

    def visit_LagVar(self, node: LagVar, _) -> str:
        base_uid = node.base_var.uid
        if node.lag == 1 and base_uid in self.var_map:
            return f"history[{self.var_map[base_uid]}]"
        raise NotImplementedError("Complex LagVar not supported.")

# =============================================================================================
# 4. Solution for large-scale algebraic frameworks, based on differential automatic composition
# =============================================================================================

class ADVisitor(SymbolicToPythonVisitor):
    """
    Forward-mode AD visitor (dual numbers) returning (val_code, dot_code).

    - dot_code is the directional derivative wrt `states`, seeded by `seeds`.
    - params are treated as constants (dot = 0.0), keeping solver agnostic.
    - Supports CSE by returning (_tK, _tK_d) when a subexpression is lifted.
    """

    def __init__(self, var_map: Dict[int, int], param_map: Dict[int, int],
                 method: DiscretizationMethod, seeds_var: str = 'seeds'):
        super().__init__(var_map, param_map, method)
        self.seeds_var = seeds_var

    def visit(self, node: Expr, precedence: int = 0):
        # CSE Check (dual)
        if self.analyzer and self.cse_map and not self.in_cse_def:
            if not isinstance(node, (Var, Const, DiffVar, LagVar)):
                h = self.analyzer._hash_expr(node)
                if h in self.cse_map:
                    t = self.cse_map[h]
                    return t, f"{t}_d"

        # Double Dispatch
        if isinstance(node, Func):
            type_name = 'Func'
        else:
            type_name = type(node).__name__

        visitor = getattr(self, f'visit_{type_name}', self.generic_visit)
        return visitor(node, precedence)

    # ---- primitives ----
    def visit_Const(self, node: Const, _):
        return str(node.value), "0.0"

    def visit_Var(self, node: Var, _):
        if node.uid in self.var_map:
            i = self.var_map[node.uid]
            return f"states[{i}]", f"{self.seeds_var}[{i}]"
        if node.uid in self.param_map:
            j = self.param_map[node.uid]
            return f"params[{j}]", "0.0"
        raise ValueError(f"Variable '{node.name}' (UID: {node.uid}) Not mapped in compiler.")

    def visit_LagVar(self, node: LagVar, _):
        # history is constant within Newton => dot=0
        base_uid = node.base_var.uid
        if node.lag == 1 and base_uid in self.var_map:
            return f"history[{self.var_map[base_uid]}]", "0.0"
        raise NotImplementedError("Complex LagVar not supported.")

    def visit_DiffVar(self, node: DiffVar, prec: int):
        base_uid = node.base_var.uid
        if base_uid not in self.var_map:
            raise ValueError(
                f"Base var '{node.base_var.name}' not mapped for DiffVar"
            )

        i = self.var_map[base_uid]

        # Discretized value (residual term)
        if isinstance(self.method, BackwardEulerMethod):
            val = f"((states[{i}] - history[{i}]) / h)"
            dot = f"(+{self.seeds_var}[{i}] / h)"

        elif isinstance(self.method, TrapezoidalMethod):
            val = f"((2.0/h)*(states[{i}] - history[{i}]) - d_history[{i}])"
            dot = f"(+2.0*{self.seeds_var}[{i}] / h)"

        elif isinstance(self.method, BDF2Method):
            val = f"((1.5*states[{i}] - 2.0*history[{i}] + 0.5*history2[{i}]) / h)"
            dot = f"(+1.5*{self.seeds_var}[{i}] / h)"

        else:
            raise NotImplementedError("Unknown discretization method")

        if prec > 10:
            return f"({val})", f"({dot})"
        return val, dot

    # ---- operators ----
    def visit_BinOp(self, node: BinOp, prec: int):
        curr_prec = self.OP_PRECEDENCE.get(node.op, 0)
        lv, ld = self.visit(node.left, curr_prec)
        rv, rd = self.visit(node.right, curr_prec)

        op = node.op
        if op == '+':
            v = f"{lv} + {rv}"
            d = f"({ld} + {rd})"
        elif op == '-':
            v = f"{lv} - {rv}"
            d = f"({ld} - {rd})"
        elif op == '*':
            v = f"{lv} * {rv}"
            d = f"(({ld})*({rv}) + ({lv})*({rd}))"
        elif op == '/':
            v = f"{lv} / {rv}"
            d = f"(({ld})*({rv}) - ({lv})*({rd})) / (({rv})*({rv}))"
        elif op == '**':
            if isinstance(node.right, Const):
                p = float(node.right.value)
                v = f"({lv})**({p})"
                d = f"({p})*(({lv})**({p - 1.0}))*({ld})"
            else:
                v = f"({lv})**({rv})"
                d = f"(({v}) * ( ({rd})*np.log({lv}) + ({rv})*({ld})/({lv}) ))"
        else:
            raise NotImplementedError(f"Unsupported BinOp: {op}")

        v_out = f"({v})" if curr_prec < prec else v
        d_out = f"({d})" if curr_prec < prec else d
        return v_out, d_out

    def visit_UnOp(self, node: UnOp, _):
        ov, od = self.visit(node.operand, 100)
        if node.op == '+':
            return f"(+({ov}))", f"(+({od}))"
        if node.op == '-':
            return f"(-({ov}))", f"(-({od}))"
        raise NotImplementedError(f"Unsupported UnOp: {node.op}")

    def visit_Func(self, node: Func, _):
        av, ad = self.visit(node.arg, 0)
        op = node.op

        # Non-smooth / event-like ops: derivative treated as 0 inside Newton
        if op == 'heaviside':
            return f"_heaviside({av})", "0.0"

        if op == 'abs':
            # piecewise derivative: sign(x)*dx (sign(0)->0 is acceptable)
            return f"np.abs({av})", f"(np.sign({av})*({ad}))"

        # Smooth numpy unary functions
        if op == 'sin':
            return f"np.sin({av})", f"(np.cos({av})*({ad}))"
        if op == 'cos':
            return f"np.cos({av})", f"(-np.sin({av})*({ad}))"
        if op == 'exp':
            v = f"np.exp({av})"
            return v, f"({v})*({ad})"
        if op == 'log':
            return f"np.log({av})", f"({ad})/({av})"
        if op == 'sqrt':
            v = f"np.sqrt({av})"
            return v, f"0.5*({ad})/({v})"

        # If your AST uses other ops (tanh, asin, etc.), add cases here explicitly.
        raise NotImplementedError(f"ADVisitor: unsupported function '{op}'")

# ==============================================================================
# 5. Compiler (sym-num)(discretized)
# ==============================================================================

class EquationCompiler:
    """Main interface for compiling symbolic equations into executable functions."""

    METHODS = {
        'trapezoidal': TrapezoidalMethod(),
        'be': BackwardEulerMethod(),
        'bdf2': BDF2Method()
    }

    def __init__(self, variables: List[Var], parameters: List[Var] = None, method: str = 'trapezoidal'):
        self.variables_objs = variables
        self.parameters_objs = parameters or []

        if method not in self.METHODS:
            raise ValueError(f"Method '{method}' Unknown. Options: {list(self.METHODS.keys())}")

        self.strategy = self.METHODS[method]

        self.var_map = {v.uid: i for i, v in enumerate(self.variables_objs)}
        self.param_map = {p.uid: i for i, p in enumerate(self.parameters_objs)}

        self.visitor = SymbolicToPythonVisitor(self.var_map, self.param_map, self.strategy)

    def compile(self, equations: List[Expr], func_name: str = "step_fn", use_cse: bool = True) -> Callable:
        lines = []
        lines.append(f"def {func_name}(states, params, history, d_history, h, history2=None):")

        # ---CSE Block ---
        if use_cse:
            analyzer = SubexpressionAnalyzer()
            cse_map = analyzer.analyze(equations)

            self.visitor.analyzer = analyzer
            self.visitor.cse_map = cse_map

            if cse_map:
                sorted_cse = sorted(cse_map.items(), key=lambda x: int(x[1][2:]))

                for expr_hash, var_name in sorted_cse:
                    expr_obj = analyzer.expr_objects[expr_hash]

                    self.visitor.in_cse_def = True
                    expr_code = self.visitor.visit(expr_obj)
                    self.visitor.in_cse_def = False

                    lines.append(f"    {var_name} = {expr_code}")

        lines.append(f"    residuals = np.zeros({len(equations)}, dtype=np.float64)")

        for i, eq in enumerate(equations):
            code = self.visitor.visit(eq)
            lines.append(f"    residuals[{i}] = {code}")

        lines.append("    return residuals")

        # Clean visitor
        self.visitor.cse_map = {}
        self.visitor.analyzer = None

        full_source = "\n".join(lines)

        from .symbolic import _heaviside
        context = {'np': np, 'math': math, '_heaviside': _heaviside}
        local_scope = {}

        try:
            exec(full_source, context, local_scope)
        except Exception as e:
            print(f"Error compiling:\n{full_source}")
            raise e

        compiled = local_scope[func_name]
        compiled.source_code = full_source
        return compiled

    def compile_ad_kernel(self, equations: List[Expr], func_name: str = "ad_step", use_cse: bool = True) -> Callable:
        """
        Compiles a forward-mode AD kernel that returns only the JVP:

            jvp = J(states) @ seeds

        Signature (as required by SparseADJacobian / BlockSolver):
            def ad_step(states, seeds, params, history, d_history, h, history2=None) -> np.ndarray

        Notes:
          - `params` is the concatenation of event parameters + static parameters in the same order
            used when building `EquationCompiler(parameters=...)`.
          - `history`, `d_history`, `history2` are treated as constants within Newton => their dots are 0.
        """
        adv = ADVisitor(self.var_map, self.param_map, self.strategy, seeds_var='seeds')

        lines: List[str] = []
        lines.append(f"def {func_name}(states, seeds, params, history, d_history, h, history2=None):")

        # --- CSE Block (dual: _tK and _tK_d) ---
        if use_cse:
            analyzer = SubexpressionAnalyzer()
            cse_map = analyzer.analyze(equations)

            adv.analyzer = analyzer
            adv.cse_map = cse_map

            if cse_map:
                sorted_cse = sorted(cse_map.items(), key=lambda x: int(x[1][2:]))

                for expr_hash, var_name in sorted_cse:
                    expr_obj = analyzer.expr_objects[expr_hash]

                    adv.in_cse_def = True
                    expr_val, expr_dot = adv.visit(expr_obj)
                    adv.in_cse_def = False

                    lines.append(f"    {var_name} = {expr_val}")
                    lines.append(f"    {var_name}_d = {expr_dot}")

        n = len(equations)
        lines.append(f"    jvp = np.zeros({n}, dtype=np.float64)")

        for i, eq in enumerate(equations):
            val , dot = adv.visit(eq)
            lines.append(f"    jvp[{i}] = {dot}")

        lines.append("    return jvp")

        # cleanup
        adv.cse_map = {}
        adv.analyzer = None

        full_source = "\n".join(lines)

        from .symbolic import _heaviside
        context = {'np': np, 'math': math, '_heaviside': _heaviside}
        local_scope: Dict[str, Any] = {}

        try:
            exec(full_source, context, local_scope)
        except Exception as e:
            print(f"Error compiling AD kernel:\n{full_source}")
            raise e

        compiled = local_scope[func_name]
        compiled.source_code = full_source
        return compiled