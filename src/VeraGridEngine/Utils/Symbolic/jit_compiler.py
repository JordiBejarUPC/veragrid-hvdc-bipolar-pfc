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
from typing import Dict, List, Callable
import hashlib

# Importamos los componentes de tu framework simbólico
from .symbolic import Expr, BinOp, UnOp, Func, Var, Const, DiffVar, LagVar

# ==============================================================================
# 1. discretization strategy (Numerical Methods)
# ==============================================================================

class DiscretizationMethod(ABC):
    """Abstract base class for discretization strategies."""
    
    @abstractmethod
    def discretize(self, state_idx: int, h_var: str = 'h') -> str:
        """
        Returns the Python code to calculate the approximate derivative.
        :param state_idx: Index of the variable in the state array.
        :param h_var: Name of the time step variable in the generated string.
        """
        pass

class TrapezoidalMethod(DiscretizationMethod):
    """
    Trapezoid rule (Implicit, Order 2, A-stable).
    Formula: dx_n = (2/h)*(x_n - x_{n-1}) - dx_{n-1}
    """
    def discretize(self, idx: int, h: str = 'h') -> str:
        # Require: states, history (x_prev), d_history (dx_prev)
        return f"((2.0/{h}) * (states[{idx}] - history[{idx}]) - d_history[{idx}])"

class BackwardEulerMethod(DiscretizationMethod):
    """
    Backward Euler (Implicit, Order 1, L-stable).
    Fórmula: dx_n = (x_n - x_{n-1}) / h
    """
    def discretize(self, idx: int, h: str = 'h') -> str:
        # Require: states, history (x_prev)
        return f"((states[{idx}] - history[{idx}]) / {h})"

class BDF2Method(DiscretizationMethod):
    """
    Backward Differentiation Formula Order 2.
    Fórmula: dx_n = (1.5*x_n - 2*x_{n-1} + 0.5*x_{n-2}) / h
    Note: Requires an additional history buffer (history2).
    """
    def discretize(self, idx: int, h: str = 'h') -> str:
        return f"((1.5*states[{idx}] - 2.0*history[{idx}] + 0.5*history2[{idx}]) / {h})"

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
#3. Conversion to string based on visitor pattern (sequentiality)
# ==============================================================================

class SymbolicToPythonVisitor:
    OP_PRECEDENCE = {'+': 10, '-': 10, '*': 20, '/': 20, '**': 30}

    def __init__(self, var_map: Dict[str, int], param_map: Dict[str, int], method: DiscretizationMethod):
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
        if node.name in self.var_map: return f"states[{self.var_map[node.name]}]"
        if node.name in self.param_map: return f"params[{self.param_map[node.name]}]"
        raise ValueError(f"Variable '{node.name}' Not mapped in var_map or param_map.")

    def visit_DiffVar(self, node: DiffVar, prec: int) -> str:
        if node.base_var.name not in self.var_map:
            raise ValueError(f"Base var '{node.base_var.name}' DiffVar does not exist in states.")
        term = self.method.discretize(self.var_map[node.base_var.name])
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
        if node.lag == 1 and node.base_var.name in self.var_map:
            return f"history[{self.var_map[node.base_var.name]}]"
        raise NotImplementedError("Complex LagVar not supported.")

# ==============================================================================
# 3. Compiler (sym-num)(discretized)
# ==============================================================================

class EquationCompiler:
    """Main interface for compiling symbolic equations into executable functions."""
    
    METHODS = {
        'trapezoidal': TrapezoidalMethod(),
        'be': BackwardEulerMethod(),
        'bdf2': BDF2Method()
    }

    def __init__(self, variables: List[str], parameters: List[str] = None, method: str = 'trapezoidal'):
        self.variables = variables
        self.parameters = parameters or []
        
        if method not in self.METHODS:
            raise ValueError(f"Method '{method}' Unknown. Options: {list(self.METHODS.keys())}")
            
        self.strategy = self.METHODS[method]
        self.var_map = {name: i for i, name in enumerate(variables)}
        self.param_map = {name: i for i, name in enumerate(self.parameters)}
        
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

        # Limpiar visitor
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