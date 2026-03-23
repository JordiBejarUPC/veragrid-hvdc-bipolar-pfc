import sympy as sp
import numpy as np
from typing import List, Dict, Optional, Any
import time
import re

from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr)
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicParamsVector, SymbolicDerivative
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler


class MTI_Problem(RmsProblemTemplate):
    """
    Mathematical DAE/ODE problem builder for TenSyGrid.

    This class handles the parsing of symbolic equations and maps operating points
    directly from a provided dictionary (v_dict). It ensures that state, algebraic,
    and derivative variables (dx/xp) are correctly synchronized for stable
    linearization in the iMTI framework.
    """
    __slots__ = (
        "init_guess", "_state_vars", "_state_eqs", "_algebraic_vars",
        "_algebraic_eqs", "_diff_vars", "_variable_parameters",
        "_event_parameters_eqs", "_constant_parameters", "_parameters_values",
        "_compiler_names_dict", "_alias_names_dict", "_uid2idx_vars",
        "_uid2idx_params", "_uid2idx_diff", "_uid2idx_t", "_uid2idx_event_params",
        "_glob_time", "_n_event_params", "_dt", "_delta", "_state_algeb_vars",
        "_n_state", "_n_alg", "_n_algebraic", "_n_diff", "timings",
        "_derivative_fn", "_event_params_fn", "_rhs_algeb_fn", "_rhs_state_fn"
    )

    VARS_NAME: str = "vars"
    VARIABLE_PARAMS_NAME: str = "vprms"
    CONSTANT_PARAMS_NAME: str = "cprms"
    DIFF_NAME: str = "diff"
    TIME_NAME: str = "glob_time"

    def __init__(self, eqs_str: List[str], v_dict: Dict[str, float]):
        """
        Initializes the problem using a flat dictionary of operating points.

        :param eqs_str: List of mathematical equations as strings.
        :param v_dict: Dictionary mapping variable names (e.g., 'x1', 'dx1', 'y1')
                       to their numerical values at the operating point.
        """
        super().__init__()

        all_eqs = " ".join(eqs_str)

        # --- 1. Dimension Discovery via Regex ---
        # Scan equations to find the highest index used for each variable category.
        # This ensures the internal vectors (vars, diff, params) are sized correctly.
        max_x = self._get_max_idx(r'\b(?:xp|dx|x)(\d+)\b', all_eqs, 0)
        max_y = self._get_max_idx(r'\by(\d+)\b', all_eqs, 0)
        max_z = self._get_max_idx(r'\bz(\d+)\b', all_eqs, 0)
        max_u = self._get_max_idx(r'\bu(\d+)\b', all_eqs, 0)

        # --- 2. Initialize Containers ---
        self.init_guess = {}
        self._state_vars, self._state_eqs = [], []
        self._algebraic_vars, self._algebraic_eqs = [], []
        self._diff_vars, self._constant_parameters = [], []
        self._variable_parameters, self._event_parameters_eqs = [], []
        self._parameters_values = []

        self._compiler_names_dict, self._alias_names_dict = {}, {}
        self._uid2idx_vars, self._uid2idx_params = {}, {}
        self._uid2idx_diff, self._uid2idx_t = {}, {}
        self._uid2idx_event_params = {}

        self._glob_time = Var(self.TIME_NAME)
        self._register_time_var()

        sym_dict: Dict[str, sp.Symbol] = {}
        var_dict: Dict[str, Var] = {}

        # --- 3. Build State and Differential Variables ---
        for i in range(max_x):
            idx = i + 1
            # Register state variable (x)
            v_x = Var(f"x{idx}")
            self._state_vars.append(v_x)
            self.init_guess[v_x.uid] = float(v_dict.get(f"x{idx}", 0.0))
            self._register_var(v_x, self.VARS_NAME, i, sym_dict, var_dict)

            # Register derivative variable (xp/dx)
            # This is critical for non-linear stability where f depends on x_dot
            v_xp = Var(f"xp{idx}")
            v_xp.base_var = v_x
            self._diff_vars.append(v_xp)

            # Extract derivative value: supports both 'xpN' and 'dxN' aliases
            val_xp = v_dict.get(f"xp{idx}", v_dict.get(f"dx{idx}", 0.0))
            self.init_guess[v_xp.uid] = float(val_xp)

            # JIT Compiler mapping for the diff vector
            self._compiler_names_dict[v_xp.uid] = f"{self.DIFF_NAME}[{i}]"
            self._alias_names_dict[v_xp.uid] = f"{self.DIFF_NAME}_{i}"
            self._uid2idx_diff[v_xp.uid] = i

            # Allow SymPy to recognize both notations during parsing
            for prefix in ["xp", "dx"]:
                name = f"{prefix}{idx}"
                sym_dict[name] = sp.Symbol(name)
                var_dict[name] = v_xp

        # --- 4. Build Algebraic and Output Variables ---
        # Map 'y' variables
        for i in range(max_y):
            idx = i + 1
            v_y = Var(f"y{idx}")
            self._algebraic_vars.append(v_y)
            self.init_guess[v_y.uid] = float(v_dict.get(f"y{idx}", 0.0))
            self._register_var(v_y, self.VARS_NAME, max_x + i, sym_dict, var_dict)

        # Map 'z' variables
        for i in range(max_z):
            idx = i + 1
            v_z = Var(f"z{idx}")
            self._algebraic_vars.append(v_z)
            self.init_guess[v_z.uid] = float(v_dict.get(f"z{idx}", 0.0))
            # Offset by max_x + max_y to keep the 'vars' vector contiguous
            self._register_var(v_z, self.VARS_NAME, max_x + max_y + i, sym_dict, var_dict)

        # --- 5. Build Constant Parameters (u) ---
        for i in range(max_u):
            idx = i + 1
            v_u = Var(f"u{idx}")
            self._constant_parameters.append(v_u)
            val_u = float(v_dict.get(f"u{idx}", 0.0))
            self._parameters_values.append(Const(val_u))
            self._register_param(v_u, i, sym_dict, var_dict)

        # --- 6. Equation Parsing and JIT Compilation ---
        self._parse_and_compile(eqs_str, sym_dict, var_dict)

    def _get_max_idx(self, p: str, text: str, d: int) -> int:
        """Finds the maximum numeric index referenced in equations via regex."""
        found = [int(m) for m in re.findall(p, text)]
        return max(max(found, default=0), d)

    def _register_var(self, v: Var, base: str, idx: int, s_d: dict, v_d: dict) -> None:
        """Helper to register a variable in the compiler mapping dictionaries."""
        self._compiler_names_dict[v.uid] = f"{base}[{idx}]"
        self._alias_names_dict[v.uid] = f"{base}_{idx}"
        self._uid2idx_vars[v.uid] = idx
        s_d[v.name] = sp.Symbol(v.name)
        v_d[v.name] = v

    def _register_param(self, v: Var, idx: int, s_d: dict, v_d: dict) -> None:
        """Helper to register a constant parameter (u) in mapping dictionaries."""
        self._compiler_names_dict[v.uid] = f"{self.CONSTANT_PARAMS_NAME}[{idx}]"
        self._alias_names_dict[v.uid] = f"{self.CONSTANT_PARAMS_NAME}_{idx}"
        self._uid2idx_params[v.uid] = idx
        s_d[v.name] = sp.Symbol(v.name)
        v_d[v.name] = v

    def _register_time_var(self) -> None:
        """Maps the global time variable for the JIT compiler."""
        self._compiler_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._alias_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._uid2idx_t[self._glob_time.uid] = 0

    def _parse_and_compile(self, eqs: List[str], s_d: dict, v_d: dict) -> None:
        """Parses strings to symbolic residues and triggers JIT compilation."""
        for eq_str in eqs:
            # Convert string to SymPy expression using locals for variable mapping
            expr_sympy = sp.sympify(eq_str, locals=s_d)
            eq_symbols = list(expr_sympy.free_symbols)
            eq_vars = [v_d[s.name] for s in eq_symbols]

            # Lambdify to convert SymPy to VeraGrid Var objects
            func = sp.lambdify(eq_symbols, expr_sympy)
            expr_var = func(*eq_vars)

            # Categorize residue: If it contains a derivative, it's a state equation
            if any(re.match(r'^(xp|dx)\d+', s.name) for s in eq_symbols):
                self._state_eqs.append(expr_var)
            else:
                self._algebraic_eqs.append(expr_var)

        self._state_algeb_vars = self._state_vars + self._algebraic_vars
        self._n_state, self._n_alg = len(self._state_vars), len(self._algebraic_vars)
        self._n_algebraic, self._n_diff = len(self._algebraic_eqs), len(self._diff_vars)

        # Standard simulation parameters (internal to the RMS solver)
        self._n_event_params = 0
        self._dt, self._delta = Var('dt'), Var('delta')
        self._variable_parameters.extend([self._dt, self._delta])
        self._event_parameters_eqs.extend([Const(1e-3), Const(1)])

        for p in [self._dt, self._delta]:
            self._compiler_names_dict[p.uid] = f"{self.VARIABLE_PARAMS_NAME}[{self._n_event_params}]"
            self._alias_names_dict[p.uid] = f"{self.VARIABLE_PARAMS_NAME}_{self._n_event_params}"
            self._uid2idx_event_params[p.uid] = self._n_event_params
            self._n_event_params += 1

        self.timings = {}
        self._compile_system()

    def _compile_system(self) -> None:
        """Invokes the RMSCompiler to generate optimized binary residue functions."""
        t0 = time.time()
        self._derivative_fn = SymbolicDerivative(self._state_algeb_vars, self._uid2idx_vars, self._diff_vars,
                                                 self._compiler_names_dict)
        rms_compiler = RMSCompiler(self._state_algeb_vars, self._diff_vars, self._variable_parameters,
                                   self._constant_parameters, self._dt, self._compiler_names_dict)

        self._rhs_algeb_fn = rms_compiler.compile_rhs(self._algebraic_eqs, "rhs_algeb")
        if self._n_state > 0:
            self._rhs_state_fn = rms_compiler.compile_rhs(self._state_eqs, "rhs_state")
        self.timings["Compilation"] = time.time() - t0