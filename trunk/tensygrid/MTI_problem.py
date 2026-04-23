import sympy as sp
import numpy as np
from typing import List, Dict, Optional, Any
import time
import re

from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr)
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicDerivative
from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler
import VeraGridEngine.api as vge
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate

class MTI_Problem(RmsProblemTemplate):
    """
    Mathematical DAE/ODE problem builder for TenSyGrid.

    This class handles the parsing of symbolic equations and maps operating points
    from an optionally provided dictionary (v_dict). It ensures that state, algebraic,
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

    def __init__(self, eqs_str: List[str], v_dict: Optional[Dict[str, float]] = None):
        """
        Initializes the problem using a flat dictionary of operating points.

        :param eqs_str: List of mathematical equations as strings.
        :param v_dict: Optional dictionary mapping variable names (e.g., 'x1', 'dx1', 'y1')
                       to their numerical values at the operating point. If omitted,
                       all values default to 0.0 and can be set later via set_operating_point().
        """
        super().__init__()

        # Default to an empty dictionary if no initial guess is provided yet
        if v_dict is None:
            v_dict = dict()

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

    def set_operating_point(self, v_dict: Dict[str, float]) -> None:
        """
        Updates the initial guess and parameter values dynamically.
        Use this to inject a v_dict after the problem has been instantiated.

        :param v_dict: Dictionary mapping variable names to their values.
        """
        # Update states (x)
        for v_x in self._state_vars:
            if v_x.name in v_dict:
                self.init_guess[v_x.uid] = float(v_dict[v_x.name])

        # Update derivatives (xp / dx)
        for v_xp in self._diff_vars:
            alt_name = v_xp.name.replace("xp", "dx")
            if v_xp.name in v_dict:
                self.init_guess[v_xp.uid] = float(v_dict[v_xp.name])
            elif alt_name in v_dict:
                self.init_guess[v_xp.uid] = float(v_dict[alt_name])

        # Update algebraic variables (y, z)
        for v_alg in self._algebraic_vars:
            if v_alg.name in v_dict:
                self.init_guess[v_alg.uid] = float(v_dict[v_alg.name])

        # Update constant parameters (u)
        for i, v_u in enumerate(self._constant_parameters):
            if v_u.name in v_dict:
                self._parameters_values[i] = Const(float(v_dict[v_u.name]))

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
        """
        Parses strings to symbolic residues and triggers JIT compilation.
        Converts SymPy expressions into VeraGrid Var structures safely.

        :param eqs: List of equation strings.
        :type eqs: List[str]
        :param s_d: Dictionary mapping strings to SymPy Symbols.
        :type s_d: dict
        :param v_d: Dictionary mapping strings to VeraGrid Var objects.
        :type v_d: dict
        :return: None
        :rtype: None
        """
        # Rule: Explicit initialization and no lambdas.
        # We pass our explicit function to handle the 'sqrt' logic.
        custom_math: dict = dict()
        custom_math["sqrt"] = _convert_sqrt_to_pow

        # ALGORITHM: Dynamically map native symbolic transcendental functions if supported.
        # This prevents numpy's ufunc from crashing when applied to VeraGrid Var objects.
        import VeraGridEngine.Utils.Symbolic.symbolic as vg_sym
        if hasattr(vg_sym, 'sin'):
            custom_math["sin"] = vg_sym.sin
        if hasattr(vg_sym, 'cos'):
            custom_math["cos"] = vg_sym.cos
        if hasattr(vg_sym, 'tan'):
            custom_math["tan"] = vg_sym.tan
        if hasattr(vg_sym, 'exp'):
            custom_math["exp"] = vg_sym.exp
        if hasattr(vg_sym, 'log'):
            custom_math["log"] = vg_sym.log

        eq_str: str
        for eq_str in eqs:
            # Convert string to SymPy expression using locals for variable mapping
            expr_sympy: sp.Expr = sp.sympify(eq_str, locals=s_d)
            eq_symbols: list = list(expr_sympy.free_symbols)

            # Extract the actual Var objects matching the SymPy symbols
            eq_vars: list = list()
            s: sp.Symbol
            for s in eq_symbols:
                eq_vars.append(v_d[s.name])

            # ALGORITHM: Lambdify maps the SymPy tree to a callable Python function.
            # By injecting custom_math, transcendentals and 'sqrt' are intercepted safely.
            func: Any = sp.lambdify(
                eq_symbols,
                expr_sympy,
                modules=[custom_math, "numpy"]
            )
            expr_var: Any = func(*eq_vars)

            # Categorize residue: If it contains a derivative, it's a state equation
            is_state: bool = False
            s_check: sp.Symbol
            for s_check in eq_symbols:
                # Using standard if/else logic
                if re.match(r'^(xp|dx)\d+', s_check.name):
                    is_state = True
                else:
                    pass

            if is_state:
                self._state_eqs.append(expr_var)
            else:
                self._algebraic_eqs.append(expr_var)

        # Rule: Explicit list building instead of adding lists (no 'list1 + list2')
        self._state_algeb_vars = list()

        v_state: Var
        for v_state in self._state_vars:
            self._state_algeb_vars.append(v_state)

        v_alg: Var
        for v_alg in self._algebraic_vars:
            self._state_algeb_vars.append(v_alg)

        self._n_state = len(self._state_vars)
        self._n_alg = len(self._algebraic_vars)
        self._n_algebraic = len(self._algebraic_eqs)
        self._n_diff = len(self._diff_vars)

        # Standard simulation parameters (internal to the RMS solver)
        self._n_event_params = 0
        self._dt = Var('dt')
        self._delta = Var('delta')

        self._variable_parameters.append(self._dt)
        self._variable_parameters.append(self._delta)

        self._event_parameters_eqs.append(Const(1e-3))
        self._event_parameters_eqs.append(Const(1.0))

        # Register event parameters explicitly
        p_list: list = list([self._dt, self._delta])
        p: Var
        for p in p_list:
            self._compiler_names_dict[p.uid] = str(f"{self.VARIABLE_PARAMS_NAME}[{self._n_event_params}]")
            self._alias_names_dict[p.uid] = str(f"{self.VARIABLE_PARAMS_NAME}_{self._n_event_params}")
            self._uid2idx_event_params[p.uid] = self._n_event_params

            # Explicit counter increment
            self._n_event_params = self._n_event_params + 1

        self.timings = dict()
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


def _convert_sqrt_to_pow(x: Any) -> Any:
    """
    ALGORITHM: Maps the square root operation to a fractional power.
    This allows SymPy's lambdify to evaluate 'sqrt' using the native
    dunder method __pow__ of the custom 'Var' object, avoiding the
    need for a dedicated .sqrt() attribute.

    :param x: The base variable or expression (typically a Var object).
    :type x: Any
    :return: The resulting expression object representing x raised to 0.5.
    :rtype: Any
    """
    return x ** 0.5