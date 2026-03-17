import sympy as sp
import numpy as np
from typing import List, Dict
import time
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr, piecewise)
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicParamsVector, SymbolicDerivative
from VeraGridEngine.basic_structures import Vec, ObjVec, BoolVec, Logger
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler
import re


class GenericMathematicalProblem(RmsProblemTemplate):
    """
    Mathematical DAE/ODE class.

    This class bypasses electrical grid topology and directly constructs
    the simulation structures from pure abstract mathematical equations.
    """
    VARS_NAME = "vars"
    VARIABLE_PARAMS_NAME = "vprms"
    CONSTANT_PARAMS_NAME = "cprms"
    DIFF_NAME = "diff"
    ALTER_PARAMS_NAME = "alter"
    TIME_NAME = "glob_time"

    def __init__(self, eqs_str: List[str], xOP: np.ndarray, uOP: np.ndarray):
        super().__init__()

        # --- 0. Robust Padding (Auto-discover missing variables in tests) ---
        max_x = len(xOP)
        max_u = len(uOP)

        for eq in eqs_str:
            u_indices = [int(m) for m in re.findall(r'\bu(\d+)\b', eq)]
            x_indices = [int(m) for m in re.findall(r'\bx(\d+)\b', eq)]

            if u_indices: max_u = max(max_u, max(u_indices))
            if x_indices: max_x = max(max_x, max(x_indices))

        if max_x > len(xOP): xOP = np.append(xOP, np.zeros(max_x - len(xOP)))
        if max_u > len(uOP): uOP = np.append(uOP, np.zeros(max_u - len(uOP)))

        # --- 1. Base container initialization ---
        self.init_guess: Dict[int, float] = dict()

        self._state_vars: List[Var] = list()
        self._state_eqs: List[sp.Expr] = list()
        self._algebraic_vars: List[Var] = list()
        self._algebraic_eqs: List[sp.Expr] = list()
        self._diff_vars: List[Var] = list()

        self._variable_parameters: List[Var] = list()
        self._event_parameters_eqs: List = list()
        self._constant_parameters: List[Var] = list()
        self._parameters_values: List = list()

        self._compiler_names_dict: Dict[int, str] = dict()
        self._alias_names_dict: Dict[int, str] = dict()
        self._uid2idx_vars: Dict[int, int] = dict()
        self._uid2idx_params: Dict[int, int] = dict()
        self._uid2idx_diff: Dict[int, int] = dict()
        self._uid2idx_t: Dict[int, int] = dict()
        self._uid2idx_event_params: Dict[int, int] = dict()

        self._glob_time: Var = Var(self.TIME_NAME)
        self._compiler_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._alias_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._uid2idx_t[self._glob_time.uid] = 0

        # --- 2. Registration of State Variables (x, xp) and Inputs (u) ---
        x_vars, xp_vars, u_vars = {}, {}, {}

        for i in range(len(xOP)):
            idx = i + 1
            x_var = Var(f'x{idx}')
            self._state_vars.append(x_var)
            x_vars[f'x{idx}'] = x_var
            self.init_guess[x_var.uid] = float(xOP[i])
            self._compiler_names_dict[x_var.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[x_var.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[x_var.uid] = i

            xp_var = Var(f'xp{idx}')
            xp_var.base_var = x_var  # Enlace necesario para el SymbolicDerivative

            self._diff_vars.append(xp_var)
            xp_vars[f'xp{idx}'] = xp_var
            self.init_guess[xp_var.uid] = 0.0
            self._compiler_names_dict[xp_var.uid] = f"{self.DIFF_NAME}[{i}]"
            self._alias_names_dict[xp_var.uid] = f"{self.DIFF_NAME}_{i}"
            self._uid2idx_diff[xp_var.uid] = i

        for j in range(len(uOP)):
            idx = j + 1
            u_var = Var(f'u{idx}')
            self._constant_parameters.append(u_var)
            u_vars[f'u{idx}'] = u_var
            self._parameters_values.append(Const(float(uOP[j])))
            self._compiler_names_dict[u_var.uid] = f"{self.CONSTANT_PARAMS_NAME}[{j}]"
            self._alias_names_dict[u_var.uid] = f"{self.CONSTANT_PARAMS_NAME}_{j}"
            self._uid2idx_params[u_var.uid] = j

        # --- 3. Parsing Text Equations strictly to specific SymPy lambda ---
        sym_dict = {f'x{i + 1}': sp.Symbol(f'x{i + 1}') for i in range(len(xOP))}
        sym_dict.update({f'xp{i + 1}': sp.Symbol(f'xp{i + 1}') for i in range(len(xOP))})
        sym_dict.update({f'u{i + 1}': sp.Symbol(f'u{i + 1}') for i in range(len(uOP))})

        var_dict = {**x_vars, **xp_vars, **u_vars}

        for eq_str in eqs_str:
            expr_sympy = sp.sympify(eq_str, locals=sym_dict)

            eq_symbols = list(expr_sympy.free_symbols)
            eq_vars = [var_dict[sym.name] for sym in eq_symbols]

            func = sp.lambdify(eq_symbols, expr_sympy)
            expr_var = func(*eq_vars)

            self._state_eqs.append(expr_var)

        # --- 4. Framework configuration variables (dt, delta) ---
        self._n_event_params = 0
        self._dt = Var(name='dt')
        self._delta = Var(name='delta')
        self._variable_parameters.extend([self._dt, self._delta])
        self._event_parameters_eqs.extend([Const(1e-3), Const(1)])

        for param in [self._dt, self._delta]:
            self._compiler_names_dict[param.uid] = f"{self.VARIABLE_PARAMS_NAME}[{self._n_event_params}]"
            self._alias_names_dict[param.uid] = f"{self.VARIABLE_PARAMS_NAME}_{self._n_event_params}"
            self._uid2idx_event_params[param.uid] = self._n_event_params
            self._n_event_params += 1

        # --- 5. Final counters for the compilers ---
        self._state_algeb_vars = self._state_vars + self._algebraic_vars
        self._n_state = len(self._state_vars)
        self._n_alg = len(self._algebraic_vars)
        self._n_algebraic = len(self._algebraic_eqs)
        self._n_diff = len(self._diff_vars)

        # --------------------------------------------------------------------------------------------------------------
        # 6. Compile RHS and Jacobian using JIT Native Compiler
        # --------------------------------------------------------------------------------------------------------------
        self.timings = dict()
        print("Compiling generic mathematical problem using JIT Native Compiler...")

        t0 = time.time()
        self._derivative_fn = SymbolicDerivative(
            vars=self._state_algeb_vars, uid2idx_vars=self._uid2idx_vars,
            diff_vars=self._diff_vars, compiler_names_dict=self._compiler_names_dict
        )
        self.timings["SymbolicDerivative"] = time.time() - t0

        t0 = time.time()
        self._event_params_fn = SymbolicParamsVector(
            eqs=self._event_parameters_eqs, compiler_names_dict=self._compiler_names_dict,
            alias_names_dict=self._alias_names_dict, EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
            TIME_NAME=self.TIME_NAME,
        )
        self.timings["Event parameters"] = time.time() - t0

        t0 = time.time()
        rms_compiler = RMSCompiler(
            variables=self._state_algeb_vars, diff_vars=self._diff_vars,
            v_params=self._variable_parameters, c_params=self._constant_parameters,
            dt_var=self._dt, compiler_names_dict=self._compiler_names_dict
        )
        self.timings["Compiler Setup"] = time.time() - t0

        t0 = time.time()
        self._rhs_algeb_fn = rms_compiler.compile_rhs(self._algebraic_eqs, "rhs_algeb")
        self.timings["RHS algebraic"] = time.time() - t0

        if len(self._state_eqs) != 0:
            t0 = time.time()
            self._rhs_state_fn = rms_compiler.compile_rhs(self._state_eqs, "rhs_state")
            self.timings["RHS state"] = time.time() - t0