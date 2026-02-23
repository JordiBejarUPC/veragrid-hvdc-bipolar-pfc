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

# Import libraries for utils
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Callable
import os
import importlib.util
import hashlib
import scipy.sparse as sp

#RMS
from VeraGridEngine.Utils.Symbolic.symbolic import get_expression_vars,expression2numba
#Totally integrated
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, BinOp, UnOp, Func, Var, Const, LagVar


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

class ContinuousMethod(DiscretizationMethod):
    """Strategy for continuous systems (RMS Small Signal). Does not discretize."""
    def discretize(self, state_idx: int, h_var: str = 'h') -> str:
        return f"dx[{state_idx}]"

    def discretize_dot(self, state_idx: int, h_var: str = 'h', seeds_var: str = 'seeds') -> str:
        return "0.0"

# ==============================================================================
# 2. CSE (Common Subexpression Elimination) Analyzer (large systems)
# ==============================================================================
class SubexpressionAnalyzer:
    """
    Find and catalog subexpressions that appear multiple times.
    OPTIMIZED: Uses memoization for complexity calc and string generation.
    """

    def __init__(self, threshold: int = 2):
        self.threshold = threshold
        self.expr_counts: Dict[str, int] = {}
        self.expr_objects: Dict[str, Expr] = {}
        self.expr_complexity: Dict[str, int] = {}

        # Caches
        self.memo_complexity = {}
        self.memo_canonical = {}
        self.visited_traversal = set()

    def analyze(self, equations: List[Expr]) -> Dict[str, str]:
        # Reset caches
        self.expr_counts.clear()
        self.expr_objects.clear()
        self.expr_complexity.clear()
        self.memo_complexity.clear()
        self.memo_canonical.clear()

        self.visited_traversal.clear()

        for eq in equations:
            self._count_subexpressions(eq)

        candidates = []
        for expr_hash, count in self.expr_counts.items():
            if count >= self.threshold:
                complexity = self.expr_complexity[expr_hash]
                benefit = count * complexity
                candidates.append((benefit, expr_hash))

        candidates.sort(reverse=True)
        temp_vars = {}
        for i, (_, expr_hash) in enumerate(candidates):
            temp_vars[expr_hash] = f"_t{i}"
        return temp_vars

    def _count_subexpressions(self, node: Expr):
        if isinstance(node, (Const, Var)):
            return

        complexity = self._calculate_complexity(node)

        if complexity > 1:
            expr_hash = self._hash_expr(node)
            self.expr_counts[expr_hash] = self.expr_counts.get(expr_hash, 0) + 1
            self.expr_objects[expr_hash] = node
            self.expr_complexity[expr_hash] = complexity

        if id(node) in self.visited_traversal:
            return
        self.visited_traversal.add(id(node))

        if isinstance(node, BinOp):
            self._count_subexpressions(node.left)
            self._count_subexpressions(node.right)
        elif isinstance(node, UnOp):
            self._count_subexpressions(node.operand)
        elif isinstance(node, Func):
            self._count_subexpressions(node.arg)

    def _calculate_complexity(self, node: Expr) -> int:
        if id(node) in self.memo_complexity:
            return self.memo_complexity[id(node)]

        res = 0
        if isinstance(node, (Const, Var)):
            res = 0
        elif isinstance(node, BinOp):
            op_cost = 2 if node.op in ['*', '/', '**'] else 1
            res = op_cost + self._calculate_complexity(node.left) + \
                  self._calculate_complexity(node.right)
        elif isinstance(node, UnOp):
            res = 1 + self._calculate_complexity(node.operand)
        elif isinstance(node, Func):
            res = 5 + self._calculate_complexity(node.arg)
        else:
            res = 1

        self.memo_complexity[id(node)] = res
        return res

    def _hash_expr(self, node: Expr) -> str:
        canonical = self._expr_to_canonical_string(node)
        return hashlib.md5(canonical.encode()).hexdigest()[:12]

    def _expr_to_canonical_string(self, node: Expr) -> str:
        if id(node) in self.memo_canonical:
            return self.memo_canonical[id(node)]

        res = ""
        if isinstance(node, Const):
            res = f"C{node.value}"
        elif isinstance(node, Var):
            base_var = getattr(node, 'base_var', None)
            if base_var is not None:
                res = f"D{base_var.name}"
            else:
                res = f"V{node.name}"
        elif isinstance(node, BinOp):
            left = self._expr_to_canonical_string(node.left)
            right = self._expr_to_canonical_string(node.right)
            if node.op in ['+', '*']:
                if left > right:
                    left, right = right, left
            res = f"({left}{node.op}{right})"
        elif isinstance(node, UnOp):
            operand = self._expr_to_canonical_string(node.operand)
            res = f"{node.op}{operand}"
        elif isinstance(node, Func):
            res = f"{node.op}({self._expr_to_canonical_string(node.arg)})"
        elif isinstance(node, LagVar):
            res = f"L{node.lag}{node.base_var.name}"
        else:
            res = str(node)

        self.memo_canonical[id(node)] = res
        return res


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
        self._str_cache = {}

    def visit(self, node: Expr, precedence: int = 0) -> str:
        if self.analyzer and self.cse_map and not self.in_cse_def:
            if not isinstance(node, (Var, Const, LagVar)):
                h = self.analyzer._hash_expr(node)
                if h in self.cse_map:
                    return self.cse_map[h]

        cache_key = (id(node), precedence)
        if cache_key in self._str_cache:
            return self._str_cache[cache_key]

        if isinstance(node, Func):
            type_name = 'Func'
        else:
            type_name = type(node).__name__

        visitor = getattr(self, f'visit_{type_name}', self.generic_visit)
        result = visitor(node, precedence)

        self._str_cache[cache_key] = result
        return result

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

    def visit_Var(self, node: Var, prec: int) -> str:
        if node.uid in self.var_map:
            return f"states[{self.var_map[node.uid]}]"
        if node.uid in self.param_map:
            return f"params[{self.param_map[node.uid]}]"

        if getattr(node, 'base_var', None) is not None:
            return self.visit_DiffVar(node, prec)

        if node.name == 'h':
            return 'h'

        raise ValueError(f"Variable '{node.name}' (UID: {node.uid}) Not mapped in compiler.")

    def visit_DiffVar(self, node: Var, prec: int) -> str:
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
    def __init__(self, var_map: Dict[int, int], param_map: Dict[int, int],
                 method: DiscretizationMethod, seeds_var: str = 'seeds',
                 active_indices: set = None):
        super().__init__(var_map, param_map, method)
        self.seeds_var = seeds_var
        self.active_indices = active_indices

    def _is_zero(self, s):
        return s in ["0.0", "0", "0.00", "(-0.0)"]

    def _is_one(self, s):
        return s in ["1.0", "1", "1.00"]

    def visit(self, node: Expr, precedence: int = 0):
        # 1. CSE Check
        if self.analyzer and self.cse_map and not self.in_cse_def:
            if not isinstance(node, (Var, Const, LagVar)):
                h = self.analyzer._hash_expr(node)
                if h in self.cse_map: return self.cse_map[h], f"{self.cse_map[h]}_d"

        # 2. Cache Check (Critical for AD speed)
        cache_key = (id(node), precedence)
        if cache_key in self._str_cache:
            return self._str_cache[cache_key]

        # 3. Visit
        if isinstance(node, Func):
            type_name = 'Func'
        else:
            type_name = type(node).__name__
        visitor = getattr(self, f'visit_{type_name}', self.generic_visit)
        res = visitor(node, precedence)

        # 4. Store
        self._str_cache[cache_key] = res
        return res

    def visit_Const(self, node: Const, _):
        return str(node.value), "0.0"

    def visit_Var(self, node: Var, _):
        # 1. Standard mapping for states
        if node.uid in self.var_map:
            i = self.var_map[node.uid]
            val = f"states[{i}]"
            # Use 1.0 for the 'active' column being differentiated, 0.0 otherwise
            if self.active_indices is not None:
                seed_val = "1.0" if i in self.active_indices else "0.0"
            else:
                seed_val = f"{self.seeds_var}[{i}]"
            return val, seed_val

        # 2. Parameter mapping
        if node.uid in self.param_map:
            return f"params[{self.param_map[node.uid]}]", "0.0"

        # 3. Fallback for Derivatives: If node is d_x, call visit_DiffVar
        # to get the discretization AND the correct AD seed.
        if getattr(node, 'base_var', None) is not None:
            return self.visit_DiffVar(node, 100)

        raise ValueError(f"Var '{node.name}' (UID: {node.uid}) Not mapped.")

    def visit_LagVar(self, node: LagVar, _):
        base_uid = node.base_var.uid
        if node.lag == 1 and base_uid in self.var_map: return f"history[{self.var_map[base_uid]}]", "0.0"
        raise NotImplementedError("Complex LagVar not supported.")

    def visit_DiffVar(self, node: Var, prec: int):
        base_uid = node.base_var.uid
        i = self.var_map[base_uid]
        if self.active_indices is not None:
            seed = "1.0" if i in self.active_indices else "0.0"
        else:
            seed = f"{self.seeds_var}[{i}]"

        if isinstance(self.method, BackwardEulerMethod):
            val = f"((states[{i}] - history[{i}]) / h)"
            dot = "0.0" if seed == "0.0" else ("(1.0/h)" if seed == "1.0" else f"({seed}/h)")
        elif isinstance(self.method, TrapezoidalMethod):
            val = f"((2.0/h)*(states[{i}] - history[{i}]) - d_history[{i}])"
            dot = "0.0" if seed == "0.0" else ("(2.0/h)" if seed == "1.0" else f"(2.0*{seed}/h)")
        elif isinstance(self.method, BDF2Method):
            val = f"((1.5*states[{i}] - 2.0*history[{i}] + 0.5*history2[{i}]) / h)"
            dot = "0.0" if seed == "0.0" else ("(1.5/h)" if seed == "1.0" else f"(1.5*{seed}/h)")
        else:
            raise NotImplementedError
        return (f"({val})", f"({dot})") if prec > 10 else (val, dot)

    def visit_BinOp(self, node: BinOp, prec: int):
        curr_prec = self.OP_PRECEDENCE.get(node.op, 0)
        lv, ld = self.visit(node.left, curr_prec)
        rv, rd = self.visit(node.right, curr_prec)
        op = node.op

        v = ""
        if op == '+':
            v = rv if self._is_zero(lv) else (lv if self._is_zero(rv) else f"{lv} + {rv}")
        elif op == '-':
            v = lv if self._is_zero(rv) else (f"-{rv}" if self._is_zero(lv) else f"{lv} - {rv}")
        elif op == '*':
            v = "0.0" if (self._is_zero(lv) or self._is_zero(rv)) else (
                rv if self._is_one(lv) else (lv if self._is_one(rv) else f"{lv} * {rv}"))
        elif op == '/':
            v = "0.0" if self._is_zero(lv) else (lv if self._is_one(rv) else f"{lv} / {rv}")
        elif op == '**':
            v = "1.0" if self._is_zero(rv) else (lv if self._is_one(rv) else (
                f"({lv})**({node.right.value})" if isinstance(node.right, Const) else f"({lv})**({rv})"))

        d = "0.0"
        if op == '+':
            d = rd if self._is_zero(ld) else (ld if self._is_zero(rd) else f"({ld} + {rd})")
        elif op == '-':
            d = f"(-{rd})" if self._is_zero(ld) else (ld if self._is_zero(rd) else f"({ld} - {rd})")
        elif op == '*':
            t1 = "0.0"
            if not self._is_zero(ld): t1 = rv if self._is_one(ld) else (ld if self._is_one(rv) else f"({ld})*({rv})")
            t2 = "0.0"
            if not self._is_zero(rd): t2 = lv if self._is_one(rd) else (rd if self._is_one(lv) else f"({lv})*({rd})")
            d = t2 if t1 == "0.0" else (t1 if t2 == "0.0" else f"({t1} + {t2})")
        elif op == '/':
            if self._is_zero(ld) and self._is_zero(rd):
                d = "0.0"
            elif self._is_zero(rd):
                d = ld if self._is_one(rv) else f"({ld}) / ({rv})"
            else:
                d = f"(({ld})*({rv}) - ({lv})*({rd})) / (({rv})*({rv}))"
        elif op == '**':
            if not (self._is_zero(ld) and self._is_zero(rd)):
                if isinstance(node.right, Const):
                    val = float(node.right.value)
                    if val == 1.0:
                        d = ld
                    elif val == 2.0:
                        d = f"2.0*({lv})*({ld})"
                    else:
                        d = f"({val})*(({lv})**({val - 1}))*({ld})"
                else:
                    d = f"(({v}) * ( ({rd})*np.log({lv}) + ({rv})*({ld})/({lv}) ))"

        return (f"({v})", f"({d})") if curr_prec < prec else (v, d)

    def visit_UnOp(self, node: UnOp, _):
        ov, od = self.visit(node.operand, 100)
        if self._is_zero(od):
            s = f"{node.op}({ov})"
            if node.op == '+': s = ov
            return s, "0.0"
        if node.op == '+': return f"(+({ov}))", f"(+({od}))"
        if node.op == '-': return f"(-({ov}))", f"(-({od}))"
        raise NotImplementedError

    def visit_Func(self, node: Func, _):
        av, ad = self.visit(node.arg, 0)
        if self._is_zero(ad):
            if node.op == 'heaviside': return f"_heaviside({av})", "0.0"
            if node.op == 'abs': return f"np.abs({av})", "0.0"
            return f"np.{node.op}({av})", "0.0"

        if node.op == 'heaviside': return f"_heaviside({av})", "0.0"
        if node.op == 'abs': return f"np.abs({av})", f"(np.sign({av})*({ad}))"
        if node.op == 'sin': return f"np.sin({av})", f"(np.cos({av})*({ad}))"
        if node.op == 'cos': return f"np.cos({av})", f"(-np.sin({av})*({ad}))"
        if node.op == 'exp': return f"np.exp({av})", f"({f'np.exp({av})'})*({ad})"
        if node.op == 'log': return f"np.log({av})", f"({ad})/({av})"
        if node.op == 'sqrt': return f"np.sqrt({av})", f"0.5*({ad})/({f'np.sqrt({av})'})"
        raise NotImplementedError

# ==============================================================================
# 5. Compiler (sym-num)(discretized)
# ==============================================================================

class EquationCompiler:
    """Main interface for compiling symbolic equations into executable functions."""

    METHODS = {
        'trapezoidal': TrapezoidalMethod(),
        'be': BackwardEulerMethod(),
        'bdf2': BDF2Method(),
        'continuous': ContinuousMethod()
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

    def _compile_to_file(self, full_source: str, func_name: str) -> Callable:
        """
        Writes source code to a file in __pycache_jit__ and imports it.
        This allows Numba's cache=True to work.
        """
        import sys

        header = "import numpy as np\nimport math\nfrom VeraGridEngine.Utils.Symbolic.symbolic import heaviside_num as _heaviside\n\n"
        full_content = header + full_source

        root_dir = os.getcwd()
        cache_dir = os.path.join(root_dir, "__pycache_jit__")
        os.makedirs(cache_dir, exist_ok=True)

        if cache_dir not in sys.path:
            sys.path.append(cache_dir)

        content_hash = hashlib.md5(full_content.encode('utf-8')).hexdigest()[:16]
        mod_name = f"{func_name}_{content_hash}"
        filename = f"{mod_name}.py"
        filepath = os.path.join(cache_dir, filename)

        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                f.write(full_content)

        if mod_name in sys.modules:
            return getattr(sys.modules[mod_name], func_name)

        spec = importlib.util.spec_from_file_location(mod_name, filepath)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)

        return getattr(module, func_name)

    def compile(self, equations: List[Expr], func_name: str = "step_fn", use_cse: bool = True,
                offset: int = 0, inplace: bool = False) -> Callable:

        # Header depends on mode
        if inplace:
            # Writes to 'residuals' array starting at 'offset'
            lines = [f"def {func_name}(states, params, history, d_history, h, residuals, history2=None):"]
        else:
            # Allocates and returns
            lines = [f"def {func_name}(states, params, history, d_history, h, history2=None):"]

        # --- CSE Block ---
        if use_cse:
            analyzer = SubexpressionAnalyzer()
            cse_map = analyzer.analyze(equations)
            self.visitor.analyzer = analyzer
            self.visitor.cse_map = cse_map
            self.visitor._str_cache = {}

            if cse_map:
                sorted_cse = sorted(cse_map.items(), key=lambda x: int(x[1][2:]))
                for expr_hash, var_name in sorted_cse:
                    expr_obj = analyzer.expr_objects[expr_hash]
                    self.visitor.in_cse_def = True
                    expr_code = self.visitor.visit(expr_obj)
                    self.visitor.in_cse_def = False
                    lines.append(f"    {var_name} = {expr_code}")

        # --- Body ---
        if not inplace:
            lines.append(f"    residuals = np.zeros({len(equations)}, dtype=np.float64)")

        for i, eq in enumerate(equations):
            code = self.visitor.visit(eq)
            # Apply offset if inplace
            target_idx = i + offset if inplace else i
            lines.append(f"    residuals[{target_idx}] = {code}")

        if not inplace:
            lines.append("    return residuals")

        # Clean visitor
        self.visitor.cse_map = {}
        self.visitor.analyzer = None
        self.visitor._str_cache = {}

        full_source = "\n".join(lines)

        return self._compile_to_file(full_source, func_name)

    def compile_ad_kernel(self, equations: List[Expr], func_name: str = "ad_step", use_cse: bool = True,
                          active_indices: set = None) -> Callable:
        adv = ADVisitor(self.var_map, self.param_map, self.strategy, seeds_var='seeds', active_indices=active_indices)
        lines = [f"def {func_name}(states, seeds, params, history, d_history, h, history2=None):"]

        if use_cse:
            analyzer = SubexpressionAnalyzer()
            cse_map = analyzer.analyze(equations)
            adv.analyzer = analyzer
            adv.cse_map = cse_map
            adv._str_cache = {}

            if cse_map:
                sorted_cse = sorted(cse_map.items(), key=lambda x: int(x[1][2:]))
                for expr_hash, var_name in sorted_cse:
                    expr_obj = analyzer.expr_objects[expr_hash]
                    adv.in_cse_def = True
                    expr_val, expr_dot = adv.visit(expr_obj)
                    adv.in_cse_def = False
                    lines.append(f"    {var_name} = {expr_val}")
                    if expr_dot != "0.0": lines.append(f"    {var_name}_d = {expr_dot}")

        n = len(equations)
        lines.append(f"    jvp = np.zeros({n}, dtype=np.float64)")
        for i, eq in enumerate(equations):
            val, dot = adv.visit(eq)
            if dot != "0.0": lines.append(f"    jvp[{i}] = {dot}")
        lines.append("    return jvp")

        adv.cse_map = {}
        adv.analyzer = None
        adv._str_cache = {}

        full_source = "\n".join(lines)

        return self._compile_to_file(full_source, func_name)


# ==============================================================================
# 6. Matrix Vectorized Compiler (HPC Optimized - No Dictionaries)
# ==============================================================================

class MatrixVectorizedVisitor(SymbolicToPythonVisitor):
    """
    HPC-optimized visitor. Instead of performing dictionary lookups (slow),
    it accesses state variable indices directly from a mapping matrix (fast).
    Generates code such as: states[indices[:, 5]]
    """

    def __init__(self, var_map, param_map, method, col_map):
        super().__init__(var_map, param_map, method)
        self.col_map = col_map  # Maps variable_name -> column_index (int)

    def visit_Var(self, node: Var, _) -> str:
        # Parameters remain unchanged (global index access)
        if node.uid in self.param_map:
            return f"params[{self.param_map[node.uid]}]"

        # States: Direct matrix column access.
        # This eliminates runtime dictionary hash lookups.
        if node.uid in self.var_map:
            # Usamos el nombre para mapear a la columna de la matriz
            col_idx = self.col_map[node.name]
            return f"states[indices[:, {col_idx}]]"

        # EMT Support: If the node is a derivative, call visit_DiffVar
        if getattr(node, 'base_var', None) is not None:
            return self.visit_DiffVar(node, 100)

        raise ValueError(f"Var '{node.name}' (UID: {node.uid}) Not mapped in matrix visitor.")

    def visit_DiffVar(self, node: Var, prec: int) -> str:
        # Vectorized discretization over index matrices
        base_name = node.base_var.name
        col_idx = self.col_map[base_name]
        idx_access = f"indices[:, {col_idx}]"

        # set direct discretization strings for arrays to ensure performance
        if isinstance(self.method, TrapezoidalMethod):
            term = f"((2.0/h) * (states[{idx_access}] - history[{idx_access}]) - d_history[{idx_access}])"
        elif isinstance(self.method, BackwardEulerMethod):
            term = f"((states[{idx_access}] - history[{idx_access}]) / h)"
        elif isinstance(self.method, BDF2Method):
            term = f"((1.5*states[{idx_access}] - 2.0*history[{idx_access}] + 0.5*history2[{idx_access}]) / h)"
        else:
            raise NotImplementedError(f"Method {type(self.method)} not supported in matrix vectorization.")

        return f"({term})" if prec > 10 else term


class MatrixVectorizedCompiler(EquationCompiler):
    """
    Compiler utilizing the Matrix Vectorized Visitor.
    Generates kernels that accept 'indices' as a 2D int32 array for batch processing.
    """

    def compile_matrix_kernel(self, template_eq: Expr, func_name: str, template_vars: List[Var]) -> Callable:
        # 1. Create a deterministic column map (Var index within the kernel)
        col_map = {}
        for i, v in enumerate(template_vars):
            name = v.base_var.name if v.base_var is not None else v.name
            col_map[name] = i

        # 2. Generate source code using the Matrix Visitor
        visitor = MatrixVectorizedVisitor(self.var_map, self.param_map, self.strategy, col_map)
        rhs_code = visitor.visit(template_eq)

        # 3. Package into a function (indices is now a 2D int32 array)
        lines = [
            f"def {func_name}(states, params, history, d_history, h, indices, history2=None):",
            f"    # Vectorized Matrix Kernel (No Dicts)",
            f"    residuals = {rhs_code}",
            f"    return residuals"
        ]
        full_source = "\n".join(lines)

        # 4. Compile to file (enabling Numba's persistent cache)
        return self._compile_to_file(full_source, func_name)

# ==============================================================================
# 7. RMS Native Compiler (Continuous Time & Sparse Jacobians)
# ==============================================================================
class RMSCompiler(EquationCompiler):
    """
    O(N) compiler for RMS (Root Mean Square) Continuous-Time Simulations.

    This compiler generates highly optimized Right-Hand Side (RHS) vectors and
    Sparse Jacobian matrices using a structural analysis approach. By leveraging
    the official `expression2numba` translator, it ensures 100% mathematical
    consistency with legacy systems while drastically reducing symbolic evaluation
    and compilation times.
    """

    def __init__(self,
                 variables: List[Var],
                 diff_vars: List[Var],
                 v_params: List[Var],
                 c_params: List[Var],
                 dt_var: Var,
                 compiler_names_dict: Dict[int, str]):
        """
        Initializes the RMS Compiler with the system's mathematical components.

        Args:
            variables (List[Var]): State and algebraic variables of the system.
            diff_vars (List[Var]): Differential variables (dx/dt).
            v_params (List[Var]): Variable (event-driven) parameters.
            c_params (List[Var]): Constant parameters.
            dt_var (Var): The symbolic variable representing the integration time step.
            compiler_names_dict (Dict[int, str]): Dictionary mapping variable UIDs to
                                                  their executable string representations.
        """
        super().__init__(variables, c_params, method='continuous')
        self.dt_var = dt_var
        self.compiler_names_dict = compiler_names_dict

    def compile_rhs(self, equations: List[Expr], func_name: str) -> Callable:
        """
        Compiles the residual equations (RHS) into a fast, executable JIT function.

        Args:
            equations (List[Expr]): The list of symbolic expressions to evaluate.
            func_name (str): The desired name for the compiled target function.

        Returns:
            Callable: An executable function computing the RHS residuals.
        """
        # Use the exact array names expected by the legacy solver interface: vars, diff, vprms, cprms
        lines = [f"def {func_name}(vars, diff, vprms, cprms):"]
        lines.append(f"    out = np.zeros({len(equations)}, dtype=np.float64)")

        for i, eq in enumerate(equations):
            expr_str = expression2numba(eq, self.compiler_names_dict)
            lines.append(f"    out[{i}] = {expr_str}")

        lines.append("    return out")

        return self._compile_to_file("\n".join(lines), func_name)

    def compile_sparse_jacobian(self, eqs: List[Expr], wrt_vars: List[Var], func_name: str) -> Callable:
        """
        Compiles a sparse Jacobian evaluator using an O(N) structural extraction algorithm.

        Args:
            eqs (List[Expr]): The list of symbolic equations (F or G).
            wrt_vars (List[Var]): The variables to differentiate with respect to (x or y).
            func_name (str): The desired name for the compiled target function.

        Returns:
            Callable: A function that populates and returns a scipy.sparse.csc_matrix.
        """
        wrt_map = {v.uid: (i, v) for i, v in enumerate(wrt_vars)}
        triplets = []

        # O(N) Algorithmic Extraction:
        # We check ALL variable-equation pairs to correctly handle chain rules
        # through differential variables. This is less efficient than checking only
        # variables that appear in each equation, but it ensures correctness.
        for row, eq in enumerate(eqs):
            for col, var in enumerate(wrt_vars):
                # Differentiate with respect to the physical time variable (dt_var)
                d_expr = eq.diff(var, dt=self.dt_var)

                if not (isinstance(d_expr, Const) and d_expr.value == 0):
                    triplets.append((col, row, d_expr))

        triplets.sort(key=lambda t: (t[0], t[1]))

        # Handle edge case: Empty Jacobian matrix (no dependencies found)
        if not triplets:
            J_empty = sp.csc_matrix((len(eqs), len(wrt_vars)))
            return lambda vars, diff, vprms, cprms, h: J_empty

        # Extract sorted coordinates and corresponding symbolic derivatives
        cols_sorted = [t[0] for t in triplets]
        rows_sorted = [t[1] for t in triplets]
        d_exprs = [t[2] for t in triplets]

        # Precompute CSC (Compressed Sparse Column) pointer arrays
        nnz = len(cols_sorted)
        indices = np.fromiter(rows_sorted, dtype=np.int32, count=nnz)
        indptr = np.zeros(len(wrt_vars) + 1, dtype=np.int32)
        for c in cols_sorted:
            indptr[c + 1] += 1
        np.cumsum(indptr, out=indptr)

        # Initialize the sparse matrix template
        J_template = sp.csc_matrix((np.zeros(nnz), indices, indptr), shape=(len(eqs), len(wrt_vars)))

        # The Jacobian receives 'h' in its signature for solver compatibility,
        # even though 'expression2numba' internally resolves 'dt' via vprms[...]
        lines = [f"def {func_name}_filler(vars, diff, vprms, cprms, h, data_out):"]
        for i, expr in enumerate(d_exprs):
            expr_str = expression2numba(expr, self.compiler_names_dict)
            lines.append(f"    data_out[{i}] = {expr_str}")

        filler_fn = self._compile_to_file("\n".join(lines), f"{func_name}_filler")

        # Wrapper function to evaluate and return the actual CSC matrix natively
        def jac_evaluator(vars, diff, vprms, cprms, h):
            filler_fn(vars, diff, vprms, cprms, h, J_template.data)
            return J_template

        return jac_evaluator