import sympy as sp
import numpy as np
from scipy import sparse, linalg
from enum import Enum
from typing import Optional, Any, Tuple
import re


# ------------------------------------------------------------------
# Enums for Options
# ------------------------------------------------------------------

class ConstraintType(Enum):
    """
    Enum representing the type of constraint to process.
    Replaces the usage of string options or ambiguous booleans.
    """
    EQUALITY = 1
    INEQUALITY = 2


# ------------------------------------------------------------------
# Helper Functions (Replacing Lambdas and Nested Functions)
# ------------------------------------------------------------------

def _sort_symbol(sym: sp.Symbol) -> tuple:
    """
        Evaluates a SymPy symbol to determine if it represents a derivative or a standard state variable,
        generating a sorting key tuple.

        From an algorithmic perspective, this function acts as a custom sorting key. In symbolic system
        formulation, it is strictly necessary to segregate time-derivatives from standard algebraic variables
        to properly structure Differential Algebraic Equations (DAEs) or state-space representations.

        The function extracts the string name of the symbol and checks it against standard derivative
        prefixes ('dx', 'xp', 'd_', 'dt_'). By returning a tuple of `(integer_priority, name)`, it forces
        Python sorting algorithms to group all derivatives first (priority 0) and standard variables second
        (priority 1). The inclusion of the string name in the tuple ensures that within those two categories,
        the symbols are sorted alphabetically.

        :param sym: The symbolic variable to be evaluated and categorized.
        :type sym: sp.Symbol
        :return: A tuple used for sorting, containing the priority integer (0 if it is a derivative,
                 1 otherwise) and the string name of the symbol.
        :rtype: tuple
        """
    name: str = sym.name
    if name.startswith('dx') or name.startswith('xp') or name.startswith('d_') or name.startswith('dt_'):
        return 0, name
    else:
        return 1, name


def _get_real_part(val: complex) -> float:
    return float(val.real)


class PolynomialMatrixBuilder:
    """
    Builds the S_H / Phi_H (and S_W / Phi_W) matrices from a list of
    polynomial equations, and performs analytic linearization using the
    iMTI / CPN representation described in the TenSyGrid papers.
    """

    def __init__(
            self,
            problem: Optional[Any] = None,
            eqs: Optional[list] = None,
            ineqs: Optional[list] = None,
            state_vars: Optional[list] = None,
            algebraic_vars: Optional[list] = None,
            verbose: bool = False
    ) -> None:

        self.verbose: bool = verbose
        self.eqs: list = list()
        self.ineqs: list = list()
        self.state_vars: list = list()
        self.algebraic_vars: list = list()
        self.has_problem: bool = problem is not None

        # --- 0. RESOLVE DUPLICATE VARIABLE NAMES DYNAMICALLY ---
        # This prevents SymPy from physically fusing distinct limiters together.
        if self.has_problem:
            seen_vars = set()
            name_counters = {}
            all_vg_vars = []

            if hasattr(problem, '_state_vars') and problem._state_vars is not None:
                all_vg_vars.extend(problem._state_vars)
            if hasattr(problem, '_algebraic_vars') and problem._algebraic_vars is not None:
                all_vg_vars.extend(problem._algebraic_vars)

            for var in all_vg_vars:
                if hasattr(var, 'name'):
                    vid = id(var)

                    if vid not in seen_vars:
                        seen_vars.add(vid)
                        base_name = getattr(var, 'name')

                        if base_name not in name_counters:
                            name_counters[base_name] = 0
                        else:
                            name_counters[base_name] += 1
                            new_name = f"{base_name}_{name_counters[base_name]}"
                            try:
                                var.name = new_name
                            except Exception as e:
                                print("Exception on for var in all_vg_vars", e)
                                pass

                            # Also rename the corresponding derivative variable to avoid mapping breaks
                            if hasattr(var, 'diff_var') and var.diff_var is not None:
                                d_var = var.diff_var
                                d_vid = id(d_var)
                                if d_vid not in seen_vars and hasattr(d_var, 'name'):
                                    seen_vars.add(d_vid)
                                    d_base = getattr(d_var, 'name')
                                    d_new = d_base.replace(base_name, new_name)
                                    if d_new == d_base:
                                        d_new = f"{d_base}_{name_counters[base_name]}"
                                    try:
                                        d_var.name = d_new
                                    except Exception as e:
                                        print("Exception in hasattrib")
                                        pass

        # 1. PARAMETER EXTRACTION
        self._param_map: dict = {}
        self._protected_params: list = []

        if self.has_problem:
            """TODO: Change _variable_parameters with a getter in the main class"""
            if hasattr(problem, '_variable_parameters') and problem._variable_parameters is not None:
                self._protected_params.extend([getattr(vp, 'name', str(vp)) for vp in problem._variable_parameters])

            if hasattr(problem, '_variable_parameters') and hasattr(problem, '_variable_parameters_values'):
                for i, vp in enumerate(problem._variable_parameters):
                    p_name = getattr(vp, 'name', str(vp))
                    if i < len(problem._variable_parameters_values):
                        self._param_map[p_name] = problem._variable_parameters_values[i]
            elif hasattr(problem, '_variable_parameters') and hasattr(problem, '_variable_parameter_values'):
                for i, vp in enumerate(problem._variable_parameters):
                    p_name = getattr(vp, 'name', str(vp))
                    if i < len(problem._variable_parameter_values):
                        self._param_map[p_name] = problem._variable_parameter_values[i]

            if hasattr(problem, '_constant_parameters') and hasattr(problem, '_constant_params'):
                self._protected_params.extend([getattr(cp, 'name', str(cp)) for cp in problem._constant_parameters])
                for i, cp in enumerate(problem._constant_parameters):
                    p_name = getattr(cp, 'name', str(cp))
                    if i < len(problem._constant_params):
                        self._param_map[p_name] = problem._constant_params[i]

        processed_eqs = list()
        processed_ineqs = list()
        processed_state_vars = list()
        processed_algebraic_vars = list()

        def _safe_to_string(item: Any) -> str:
            """TODO: Remove hasattr"""
            if hasattr(item, 'expr'):
                return str(getattr(item, 'expr'))
            elif hasattr(item, 'to_string'):
                return item.to_string()
            return str(item)

        if eqs is not None:
            processed_eqs = list(eqs)
        elif self.has_problem:
            """TODO: Remove hasattr"""
            if hasattr(problem, '_state_eqs'):
                for s_eq in problem._state_eqs:
                    processed_eqs.append(_safe_to_string(s_eq))
            if hasattr(problem, '_algebraic_eqs'):
                for a_eq in problem._algebraic_eqs:
                    processed_eqs.append(_safe_to_string(a_eq))

        if ineqs is not None:
            processed_ineqs = list(ineqs)

        self._explicit_deriv_map: dict = dict()

        def clean_name_fn(n):
            """
                Standardizes the string representation of a symbolic variable name by normalizing
                various time-derivative prefixes into a single canonical format.

                From an algorithmic perspective, different symbolic operations, external libraries,
                or intermediate parsing steps may generate inconsistent first-derivative prefixes
                (such as 'dt_1_', 'd_1_', or simply 'd_'). This cleaning step is critical in the
                broader algorithm because downstream processes—such as state-space formulation,
                variable mapping, or the previous sorting logic—rely on strict, predictable string
                matching to correctly identify and manipulate time derivatives.

                The function executes the following sequence:
                1. Casts the input to a string to guarantee that string manipulation methods are available,
                   allowing it to gracefully handle SymPy symbols or raw strings.
                2. Explicitly replaces known anomalous first-derivative notations ('dt_1_' and 'd_1_')
                   with the standard 'dt_' prefix.
                3. Utilizes a regular expression to find word-boundary instances of 'd_' (matching the
                   start of the string) and replaces them with 'dt_'. The word boundary is essential to
                   prevent the accidental replacement of 'd_' if it occurs in the middle or end of a
                   variable's base name.

                :param n: The variable or object whose name requires standardizing.
                :type n: Any (typically str or sp.Symbol)
                :return: The cleaned and standardized string name with a unified 'dt_' derivative prefix.
                :rtype: str
                """
            c = str(n)
            c = c.replace('dt_1_', 'dt_').replace('d_1_', 'dt_')
            c = re.sub(r'\bd_', 'dt_', c)
            return c

        def _extract_mappings(var_list: list) -> None:
            """
                Extracts and maps base variables to their explicit time-derivative counterparts
                from a list of variable objects.

                From an algorithmic perspective, this function builds a required lookup table
                (`self._explicit_deriv_map`) linking state variables to their corresponding derivatives.
                It iterates over the provided list, bypassing raw strings, and inspects objects for
                `diff_var` or `base_var` properties. By applying `clean_name_fn` to the extracted names,
                it guarantees standardized string matching for downstream differential equation assembly.

                :param var_list: A collection of variable objects to inspect for derivative relationships.
                :type var_list: list
                :return: Modifies the internal `_explicit_deriv_map` in place.
                :rtype: None
                """
            if not var_list: return
            for var_obj in var_list:
                if not isinstance(var_obj, str):
                    base_name_mappings = getattr(var_obj, 'name', None)
                    diff_var = getattr(var_obj, 'diff_var', None)
                    if diff_var is not None:
                        diff_name = getattr(diff_var, 'name', None)
                        if base_name_mappings and diff_name:
                            self._explicit_deriv_map[clean_name_fn(base_name_mappings)] = clean_name_fn(diff_name)

                    base_var = getattr(var_obj, 'base_var', None)
                    if base_var is not None:
                        base_var_name = getattr(base_var, 'name', None)
                        if base_var_name and base_name_mappings:
                            self._explicit_deriv_map[clean_name_fn(base_var_name)] = clean_name_fn(base_name_mappings)

        if state_vars is not None:
            _extract_mappings(state_vars)
            processed_state_vars = [_safe_to_string(v) for v in state_vars]
        elif self.has_problem:
            if hasattr(problem, '_state_vars'):
                _extract_mappings(problem._state_vars)
                for s_var in problem._state_vars:
                    processed_state_vars.append(_safe_to_string(s_var))

        if algebraic_vars is not None:
            _extract_mappings(algebraic_vars)
            processed_algebraic_vars = [_safe_to_string(v) for v in algebraic_vars]
        elif self.has_problem:
            if hasattr(problem, '_algebraic_vars'):
                _extract_mappings(problem._algebraic_vars)
                for a_var in problem._algebraic_vars:
                    processed_algebraic_vars.append(_safe_to_string(a_var))

        parsing_context = dict()
        parsing_context['cos'] = sp.cos
        parsing_context['sin'] = sp.sin
        parsing_context['tan'] = sp.tan
        parsing_context['exp'] = sp.exp
        parsing_context['sqrt'] = sp.sqrt
        parsing_context['pi'] = sp.pi

        parsed_predefined: list[sp.Symbol] = []

        # 2. Symbols Extraction
        for names, target_list in [(processed_state_vars, self.state_vars),
                                   (processed_algebraic_vars, self.algebraic_vars)]:
            for name in names:
                clean_name = name.replace('dt_1_', 'dt_').replace('d_1_', 'dt_')
                clean_name = re.sub(r'\bd_', 'dt_', clean_name)

                if clean_name not in parsing_context:
                    sym = sp.Symbol(clean_name)
                    parsing_context[clean_name] = sym
                    target_list.append(sym)
                    parsed_predefined.append(sym)

        # 3. Expression parsing
        for raw_exprs, target_list in [(processed_eqs, self.eqs), (processed_ineqs, self.ineqs)]:
            for raw in raw_exprs:
                s = raw if isinstance(raw, str) else str(raw)
                s = s.replace('dt_1_', 'dt_').replace('d_1_', 'dt_')
                s = re.sub(r'\bd_', 'dt_', s)

                expr = sp.parsing.sympy_parser.parse_expr(s, local_dict=parsing_context, evaluate=False)

                if self._param_map:
                    expr = expr.subs(self._param_map)

                target_list.append(expr)

        # 4. Symbols' inizialization
        self.all_symbols = []
        self.sym_to_idx = {}
        self.extract_symbols(self.eqs + self.ineqs, predefined=parsed_predefined)
        self._argaux_map = dict()

        self._flatten_nonlinear_arguments()
        self._apply_automatic_trig_lifting()

        self.all_symbols.sort(key=_sort_symbol)
        self.sym_to_idx.clear()
        for idx, sym in enumerate(self.all_symbols):
            self.sym_to_idx[sym.name] = idx

        # --- ALGORITHM: TWO-PASS COMPILATION FOR AUTOMATIC LIFTING ---
        self.matrix_creation(self.eqs)
        self._generate_lifting_equations(problem)

        S_H_sp, Phi_H_sp = self.matrix_creation(self.eqs)
        S_W_sp, Phi_W_sp = self.matrix_creation(self.ineqs)

        self.S_H: np.ndarray = S_H_sp.toarray()
        self.Phi_H: np.ndarray = Phi_H_sp.toarray()
        self.S_W: np.ndarray = S_W_sp.toarray()
        self.Phi_W: np.ndarray = Phi_W_sp.toarray()

        self.E: Optional[np.ndarray] = None
        self.A: Optional[np.ndarray] = None
        self.B: Optional[np.ndarray] = None
        self.EABC: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Symbol extraction
    # ------------------------------------------------------------------
    def _is_protected_param(self, var_name: str) -> bool:
        return hasattr(self, '_protected_params') and var_name in self._protected_params

    def extract_symbols(self, all_exprs: list, predefined: list | None = None) -> list:
        """
            Extracts and sorts unique symbolic variables from a list of equations.

            Algorithmically, this function builds the definitive sequence of state variables.
            It uses a set for O(1) deduplication, appending `predefined` symbols first.
            Then, it extracts `free_symbols` from all expressions, actively filtering out
            protected parameters. Finally, it applies the derivative-first sorting logic
            to guarantee a deterministic variable order for matrix and state-space assembly.

            :param all_exprs: List of symbolic expressions or equations to parse.
            :type all_exprs: list
            :param predefined: Optional list of symbols to force-include first.
            :type predefined: list | None
            :return: A sorted list of all unique, non-protected symbols.
            :rtype: list
        """
        seen: set = set()
        extracted_symbols: list = list()

        if predefined is not None:
            for sym_p in predefined:
                if sym_p not in seen:
                    seen.add(sym_p)
                    extracted_symbols.append(sym_p)

        for eq in all_exprs:
            for sym in list(eq.free_symbols):
                if sym not in seen and not self._is_protected_param(sym.name):
                    seen.add(sym)
                    extracted_symbols.append(sym)

        extracted_symbols.sort(key=_sort_symbol)
        self.all_symbols = extracted_symbols
        return extracted_symbols

    # ------------------------------------------------------------------
    # Matrix creation
    # ------------------------------------------------------------------
    def matrix_creation(self, all_exprs: list) -> tuple:
        """
            Assembles the sparse structural matrices S (monomial definitions) and Phi (coefficients)
            from a list of symbolic expressions.

            Algorithmically, this translates symbolic equations into a vectorized numeric format
            required for high-performance evaluation. It parses each equation into terms, extracts
            unique monomials to avoid redundancies, and maps their respective coefficients. To optimize
            memory and conform to sparse operations, it outputs S in CSC format and Phi in CSR format.

            :param all_exprs: A list of symbolic expressions representing the system equations.
            :type all_exprs: list
            :return: A tuple containing the (S, Phi) sparse matrices.
            :rtype: tuple
        """
        S_list: list = list()
        Phi_data: list = list()
        monom_to_idx: dict = dict()

        eq_idx: int = 0
        for eq in all_exprs:
            terms = list(eq.args) if eq.is_Add else [eq]
            current_eq_coeffs: dict = dict()
            for term in terms:
                current_eq_coeffs = self._get_monomial_weights(term, S_list, monom_to_idx, current_eq_coeffs)
            Phi_data.append(current_eq_coeffs)
            eq_idx += 1

        if len(S_list) > 0:
            S_raw: np.ndarray = np.vstack(S_list).T.astype(float)
            S = sparse.csc_matrix(S_raw)
            num_cols: int = S_raw.shape[1]
            phi_rows: list = list()

            for eq_dict in Phi_data:
                row: np.ndarray = np.zeros(num_cols)
                for col_idx, val in eq_dict.items():
                    row[col_idx] = val
                phi_rows.append(row)

            Phi = sparse.csr_matrix(np.vstack(phi_rows))
        else:
            S = sparse.csc_matrix((len(self.all_symbols), 0))
            Phi = sparse.csr_matrix((len(all_exprs), 0))

        return S, Phi

    def _get_monomial_weights(self, term: sp.Expr, S_list: list, monom_to_idx: dict, current_eq_coeffs: dict) -> dict:
        """
            Parses a symbolic term to extract its structural weights for the S matrix and
            its scalar coefficient for the Phi matrix.

            Algorithmically, this function is the core algebraic reducer for the TenSyGrid engine.
            It breaks down complex terms into standardized multilinear monomials. If it detects
            higher-order degrees, inverses, or square roots, it dynamically generates and injects
            auxiliary variables (`mulaux`, `invaux`, `sqrtaux`) to linearize the term's structure.
            During this process, it updates the global symbol registry and recursively pads
            existing structural arrays (`S_list`) on the fly to maintain matrix dimensionality.

            :param term: The specific symbolic algebraic term to be evaluated.
            :type term: sp.Expr
            :param S_list: List of numerical arrays representing the structural footprint of known monomials.
            :type S_list: list
            :param monom_to_idx: Dictionary mapping unique monomial structures to their column index.
            :type monom_to_idx: dict
            :param current_eq_coeffs: Dictionary accumulating the coefficient values for the current equation.
            :type current_eq_coeffs: dict
            :return: The updated dictionary of coefficients mapping monomial indices to their values.
            :rtype: dict
        """
        coeff_sym, symbolic_part = term.as_coeff_mul()
        factors: tuple = sp.Mul.make_args(sp.Mul(*symbolic_part))
        requires_expansion: bool = False

        for f in factors:
            if len(list(f.free_symbols)) > 1:
                requires_expansion = True

        if requires_expansion:
            expanded_expr: sp.Expr = term.expand()
            expanded_sub_terms: tuple = sp.Add.make_args(expanded_expr)
            if len(expanded_sub_terms) == 1 and expanded_sub_terms[0] == term:
                raise ValueError(f"Irreducible non-linear term detected: {term}")

            for sub_t in expanded_sub_terms:
                current_eq_coeffs = self._get_monomial_weights(sub_t, S_list, monom_to_idx, current_eq_coeffs)
            return current_eq_coeffs

        else:
            global_phi: float = float(coeff_sym)
            weights: list = [0.0] * len(self.all_symbols)

            for f in factors:
                f_vars_inner = list(f.free_symbols)
                if len(f_vars_inner) == 1:
                    s: sp.Symbol = f_vars_inner[0]
                    idx_val: int | None = self.sym_to_idx.get(s.name, None)

                    if idx_val is not None:
                        b_val_sym: sp.Expr = sp.diff(f, s)
                        deg: float = float(f.exp) if isinstance(f, sp.Pow) else float(sp.degree(f, s))
                        is_sqrt: bool = abs(deg - 0.5) < 1e-6
                        is_protected = self._is_protected_param(s.name)

                        if (deg > 1.0 or deg < 0.0) and not is_sqrt and not is_protected:
                            is_positive: bool = deg > 1.0
                            num_aux: int = int(deg - 1.0) if is_positive else int(-deg + 1.0)
                            prefix: str = "mulaux" if is_positive else "invaux"

                            new_vars_names = [f"{s.name}_{prefix}{i_aux}" for i_aux in range(num_aux)]
                            new_symbols_list, vars_added = [], False

                            for v_name in new_vars_names:
                                if v_name not in self.sym_to_idx:
                                    new_sym_obj = sp.Symbol(v_name)
                                    self.all_symbols.append(new_sym_obj)
                                    self.sym_to_idx[v_name] = len(self.all_symbols) - 1
                                    new_symbols_list.append(new_sym_obj)
                                    vars_added = True
                                else:
                                    new_symbols_list.append(self.all_symbols[self.sym_to_idx[v_name]])

                            if vars_added:
                                new_size = len(self.all_symbols)
                                for i_p in range(len(S_list)):
                                    padding = new_size - S_list[i_p].shape[0]
                                    if padding > 0:
                                        S_list[i_p] = np.concatenate([S_list[i_p], np.zeros(padding)])

                            multilinear_f = s
                            for sym_aux in new_symbols_list:
                                multilinear_f = multilinear_f * sym_aux

                            new_term = (term / f) * multilinear_f
                            return self._get_monomial_weights(new_term, S_list, monom_to_idx, current_eq_coeffs)

                        elif is_sqrt and not is_protected:
                            new_vars_names_sqrt = [f"{s.name}_sqrtaux0", f"{s.name}_sqrtaux1"]
                            new_symbols_list_sqrt, vars_added_sqrt = [], False

                            for v_name_sqrt in new_vars_names_sqrt:
                                if v_name_sqrt not in self.sym_to_idx:
                                    new_sym_obj_sqrt = sp.Symbol(v_name_sqrt)
                                    self.all_symbols.append(new_sym_obj_sqrt)
                                    self.sym_to_idx[v_name_sqrt] = len(self.all_symbols) - 1
                                    new_symbols_list_sqrt.append(new_sym_obj_sqrt)
                                    vars_added_sqrt = True
                                else:
                                    new_symbols_list_sqrt.append(self.all_symbols[self.sym_to_idx[v_name_sqrt]])

                            if vars_added_sqrt:
                                new_size = len(self.all_symbols)
                                for i_p in range(len(S_list)):
                                    padding = new_size - S_list[i_p].shape[0]
                                    if padding > 0:
                                        S_list[i_p] = np.concatenate([S_list[i_p], np.zeros(padding)])

                            multilinear_f_sqrt = new_symbols_list_sqrt[0]
                            new_term_sqrt = (term / f) * multilinear_f_sqrt
                            return self._get_monomial_weights(new_term_sqrt, S_list, monom_to_idx, current_eq_coeffs)

                        b_val = float(b_val_sym)
                        a_val = float(f.subs(s, 0))
                        scale = abs(a_val) + abs(b_val)
                        if scale == 0.0: scale = 1.0

                        weights[idx_val] = b_val / scale
                        global_phi *= scale

                elif len(f_vars_inner) == 0:
                    global_phi *= float(f)

            monom_tuple = tuple(weights)
            existing_idx = monom_to_idx.get(monom_tuple, None)

            if existing_idx is None:
                final_idx = len(S_list)
                monom_to_idx[monom_tuple] = final_idx
                S_list.append(np.array(monom_tuple))
            else:
                final_idx = existing_idx

            current_eq_coeffs[final_idx] = current_eq_coeffs.get(final_idx, 0.0) + global_phi
            return current_eq_coeffs

    def _apply_automatic_trig_lifting(self) -> None:
        """
            Applies automatic trigonometric lifting to eliminate transcendental functions
            by replacing them with polynomial proxy variables.

            Algorithmically, this step converts transcendental non-linearities into a purely
            polynomial Differential Algebraic Equation (DAE) system. It searches for sine and
            cosine operations, replaces them with auxiliary state variables (e.g., `x_sin_arg`),
            and automatically appends their analytical time-derivative constraints to the system
            equations. This is strictly required to ensure all terms can be subsequently parsed
            into standard multilinear monomial matrices.

            :return: Modifies the internal `eqs` and `all_symbols` lists in place.
            :rtype: None
        """
        new_eqs, subs_dict, processed_args = [], {}, set()

        for eq in self.eqs:
            for term in eq.atoms(sp.sin, sp.cos):
                arg = term.args[0]
                if arg not in processed_args:
                    arg_name = arg.name
                    if self._is_protected_param(arg_name): continue

                    s_var = sp.Symbol(f"x_sin_{arg.name}")
                    c_var = sp.Symbol(f"x_cos_{arg.name}")
                    sp_var = sp.Symbol(f"xp_sin_{arg.name}")
                    cp_var = sp.Symbol(f"xp_cos_{arg.name}")

                    arg_p = sp.Symbol(self._explicit_deriv_map.get(arg_name, arg_name.replace('x', 'xp')))

                    new_eqs.extend([sp_var - (c_var * arg_p), cp_var + (s_var * arg_p)])
                    subs_dict[sp.sin(arg)] = s_var
                    subs_dict[sp.cos(arg)] = c_var

                    for new_sym in [s_var, c_var, sp_var, cp_var]:
                        if new_sym not in self.all_symbols:
                            self.all_symbols.append(new_sym)

                    processed_args.add(arg)

        self.eqs = [eq.subs(subs_dict) for eq in self.eqs] + new_eqs


    def _get_symbol_by_name(self, name: str) -> Optional[sp.Symbol]:
        for target_sym in self.all_symbols:
            if target_sym.name == name: return target_sym
        return None

    def _generate_lifting_equations(self, problem) -> None:
        """
            Generates and appends exact algebraic constraint equations for auxiliary variables
            introduced during the structural reduction phase.

            Algorithmically, prior steps inject proxy variables (`_mulaux`, `_invaux`, `_sqrtaux`)
            to convert non-linearities (such as inverses and square roots) into purely multilinear terms.
            To ensure the resulting Differential Algebraic Equation (DAE) system remains mathematically
            closed and well-posed, this function automatically formulates their structural polynomial
            definitions (e.g., enforcing `base * invaux - 1 = 0` or `base - sqrtaux**2 = 0`) and
            appends them to the global system equations.

            :param problem: The overarching problem instance, used to filter out predefined variable parameters.
            :type problem: Any
            :return: Modifies the internal `eqs` list in place with the new algebraic constraints.
            :rtype: None
        """
        new_constraints = []
        for sym in self.all_symbols:
            if sym not in (problem._variable_parameters if hasattr(problem,
                                                                   '_variable_parameters') and problem._variable_parameters else []):
                s_name = sym.name
                if "_mulaux" in s_name:
                    base_sym = self._get_symbol_by_name(s_name.split("_mulaux")[0])
                    if base_sym and (base_sym - sym) not in self.eqs:
                        new_constraints.append(base_sym - sym)
                elif "_invaux" in s_name:
                    base_sym = self._get_symbol_by_name(s_name.split("_invaux")[0])
                    if base_sym and (base_sym * sym - 1.0) not in self.eqs:
                        new_constraints.append(base_sym * sym - 1.0)
                elif s_name.endswith("_sqrtaux0"):
                    base_sym = self._get_symbol_by_name(s_name.split("_sqrtaux0")[0])
                    sym_aux1 = self._get_symbol_by_name(f"{s_name.split('_sqrtaux0')[0]}_sqrtaux1")
                    if base_sym and sym_aux1:
                        if (base_sym - (sym * sym_aux1)) not in self.eqs:
                            new_constraints.append(base_sym - (sym * sym_aux1))
                        if (sym - sym_aux1) not in self.eqs:
                            new_constraints.append(sym - sym_aux1)

        self.eqs.extend(new_constraints)

    def _flatten_nonlinear_arguments(self) -> None:
        """
            Flattens complex expressions inside non-integer powers by introducing proxy state variables.

            Algorithmically, downstream structural parsers require the bases of fractional powers
            (e.g., square roots) to be single state variables rather than composite polynomials.
            This function scans all equations and inequalities for non-integer exponents applied
            to complex expressions. It replaces the complex base with an auxiliary variable (`argaux`)
            and automatically appends its explicit structural definition (`argaux - base_expr = 0`)
            to the global system constraints.

            :return: Modifies the internal `eqs`, `ineqs`, and `all_symbols` lists in place.
            :rtype: None
        """
        new_constraints, arg_counter = [], 0
        for eq_list in [self.eqs, self.ineqs]:
            for i in range(len(eq_list)):
                current_eq = eq_list[i]
                for p in current_eq.find(sp.Pow):
                    if not p.exp.is_integer:
                        base_expr = p.base
                        if isinstance(base_expr, sp.Symbol) and self._is_protected_param(base_expr.name): continue
                        if not isinstance(base_expr, sp.Symbol):
                            new_sym = sp.Symbol(f"argaux{arg_counter}")
                            arg_counter += 1
                            if new_sym not in self.all_symbols: self.all_symbols.append(new_sym)
                            self._argaux_map[new_sym] = base_expr
                            current_eq = current_eq.subs(p, new_sym ** p.exp)
                            new_constraints.append(new_sym - base_expr)
                eq_list[i] = current_eq
        self.eqs.extend(new_constraints)

    # ------------------------------------------------------------------
    # Linearization – public entry point
    # ------------------------------------------------------------------
    def linearize(self, v_dict: dict, c_type: ConstraintType = ConstraintType.EQUALITY) -> np.ndarray:
        """
            Evaluates the numerical linearization of the system around a specified operating point
            to extract the linear state-space matrices (E, A, B).

            Algorithmically, this function dynamically injects the exact numerical values for
            trigonometric proxy states to guarantee consistency at the operating point. It then
            computes the analytical Jacobian (F) of the target structural matrix (S) evaluated
            at the state vector. By projecting this Jacobian through the coefficient matrix (Phi),
            it algebraically computes the global linear state-space block `EABC` (Phi @ F^T),
            which dictates the local dynamic behavior of the system.

            :param v_dict: Dictionary containing the numerical values defining the operating point.
            :type v_dict: dict
            :param c_type: Specifies whether to linearize equality or inequality constraints.
            :type c_type: ConstraintType
            :return: The combined, linearized state-space matrix block EABC.
            :rtype: np.ndarray
        """
        import math
        for key in list(v_dict.keys()):
            if key.startswith('x') and 'p' not in key:
                val = float(v_dict[key])
                v_dict[f"x_sin_{key}"] = math.sin(val)
                v_dict[f"x_cos_{key}"] = math.cos(val)
                v_dict[f"xp_sin_{key}"] = 0.0
                v_dict[f"xp_cos_{key}"] = 0.0

        S, Phi = (self.S_W, self.Phi_W) if c_type == ConstraintType.INEQUALITY else (self.S_H, self.Phi_H)
        v = self._build_v_vector(v_dict)
        F = self._compute_jacobian(S, v)

        self.EABC = Phi @ F.T
        self.E, self.A, self.B = self._split_EABC(self.EABC)

        return self.EABC

    def _build_v_vector(self, v_dict_local: dict) -> np.ndarray:
        """
            Constructs the complete dense numerical state vector from a dictionary of operating point values.

            Algorithmically, this function maps user-defined inputs to the strict internal array layout
            required for Jacobian evaluation. It executes three critical completion passes: First, it applies
            a robust bridging logic to mirror derivative values across different canonical prefixes
            ('xp', 'dx', 'dt_', 'd_'). Second, it numerically evaluates complex base expressions to populate
            'argaux' proxy variables. Finally, it calculates the exact states of structural auxiliary variables
            ('mulaux', 'invaux', 'sqrtaux') directly from their parent values, ensuring the final vector
            is mathematically closed and fully consistent for matrix operations.

            :param v_dict_local: Dictionary mapping symbolic variable names to their scalar numerical values.
            :type v_dict_local: dict
            :return: A 1D NumPy array representing the fully populated state vector.
            :rtype: np.ndarray
        """
        v = np.zeros(len(self.all_symbols), dtype=float)
        for k, val in v_dict_local.items():
            if k in self.sym_to_idx:
                v[self.sym_to_idx[k]] = float(val)

            # Robust Bridge: Ensures manual derivative inputs are mirrored properly across models
            if k.startswith('xp'):
                base = k[2:]
                for alt in [f'dx{base}', f'dt_{base}', f'd_{base}']:
                    if alt in self.sym_to_idx: v[self.sym_to_idx[alt]] = float(val)
            elif k.startswith('dx'):
                base = k[2:]
                for alt in [f'xp{base}', f'dt_{base}', f'd_{base}']:
                    if alt in self.sym_to_idx: v[self.sym_to_idx[alt]] = float(val)
            elif k.startswith('dt_'):
                base = k[3:]
                for alt in [f'xp{base}', f'dx{base}', f'd_{base}']:
                    if alt in self.sym_to_idx: v[self.sym_to_idx[alt]] = float(val)
            elif k.startswith('d_'):
                base = k[2:]
                for alt in [f'xp{base}', f'dx{base}', f'dt_{base}']:
                    if alt in self.sym_to_idx: v[self.sym_to_idx[alt]] = float(val)

        for sym_arg in self.all_symbols:
            if sym_arg in self._argaux_map:
                base_expr = self._argaux_map[sym_arg]
                subs_dict = {s: float(v[self.sym_to_idx[s.name]]) for s in base_expr.free_symbols if
                             s.name in self.sym_to_idx}
                if sym_arg.name in self.sym_to_idx:
                    v[self.sym_to_idx[sym_arg.name]] = float(base_expr.subs(subs_dict))

        for sym in self.all_symbols:
            s_name = sym.name
            if s_name not in v_dict_local:
                idx_current = self.sym_to_idx[s_name]
                if "_mulaux" in s_name:
                    base_idx = self.sym_to_idx.get(s_name.split("_mulaux")[0])
                    if base_idx is not None: v[idx_current] = v[base_idx]
                elif "_invaux" in s_name:
                    base_idx = self.sym_to_idx.get(s_name.split("_invaux")[0])
                    if base_idx is not None:
                        val_base = float(v[base_idx])
                        v[idx_current] = 1.0 / val_base if abs(val_base) > 1e-12 else 1.0
                elif "_sqrtaux" in s_name:
                    base_idx = self.sym_to_idx.get(s_name.split("_sqrtaux")[0])
                    if base_idx is not None and float(v[base_idx]) > 0.0:
                        v[idx_current] = float(np.sqrt(float(v[base_idx])))

        return v

    def _compute_jacobian(self, S: np.ndarray, v: np.ndarray) -> np.ndarray:
        """
            Computes the analytical Jacobian matrix of the system's structural monomials evaluated
            at a specific state vector.

            Algorithmically, this function exploits the purely multilinear nature of the TenSyGrid
            formulation. It calculates all partial derivatives simultaneously using a highly optimized,
            vectorized inverse-product rule (where the derivative of a product is the product divided
            by the target variable). Crucially, it implements an algebraic safeguard for zero-crossings:
            if exactly one variable in a monomial evaluates to zero, it bypasses the resulting 0/0
            singularity by directly computing the product of the remaining non-zero factors.

            :param S: The structural matrix defining the variable compositions of each monomial.
            :type S: np.ndarray
            :param v: The 1D numerical array representing the populated state vector.
            :type v: np.ndarray
            :return: The numerically evaluated dense Jacobian matrix F.
            :rtype: np.ndarray
        """
        X = (S.T * v) + (1.0 - np.abs(S.T))
        Y = np.prod(X, axis=1)

        with np.errstate(divide='ignore', invalid='ignore'):
            invX = np.where(np.abs(X) > 1e-12, 1.0 / X, 0.0)
            F = S * (Y[:, np.newaxis] * invX).T
            zeros_per_col = np.sum(np.abs(X) < 1e-12, axis=1)
            single_zero_cols = np.where(zeros_per_col == 1)

            for col in single_zero_cols[0]:
                zero_row = int(np.where(np.abs(X[col, :]) < 1e-12)[0][0])
                other_factors = np.delete(X[col, :], zero_row)
                prod_val: float = float(np.prod(other_factors))
                s_val: float = float(S[zero_row, col])

                F[zero_row, col] = s_val * prod_val

        return F

    def _split_EABC(self, EABC: np.ndarray) -> tuple:
        """
            Partitions the combined linearized Jacobian block matrix into the canonical
            descriptor state-space matrices E, A, and B.

            Algorithmically, this function maps the global Jacobian back to the standard
            differential algebraic form (E*dx/dt = A*x + B*u). It scans all system symbols
            to classify the columns into states, time-derivatives, and control inputs. State
            columns directly populate the A matrix, while input columns form the B matrix.
            Crucially, it executes a rigorous heuristic and mapped search to pair each state
            variable with its exact explicit derivative; the negated columns of these derivatives
            are then assigned to the E (mass) matrix.

            :param EABC: The combined structural matrix representing the full system Jacobian.
            :type EABC: np.ndarray
            :return: A tuple containing the (E, A, B) numerical state-space matrices.
            :rtype: tuple
        """
        idx_dx, idx_vars, idx_u = [], [], []

        for idx_counter, s in enumerate(self.all_symbols):
            s_name = s.name
            if s_name.startswith('dx') or s_name.startswith('xp') or s_name.startswith('d_') or s_name.startswith(
                    'dt_'):
                idx_dx.append(idx_counter)
            elif s_name.startswith('u') and not s_name.startswith('u_'):
                idx_u.append(idx_counter)
            else:
                idx_vars.append(idx_counter)

        n_eqs = int(EABC.shape[0])
        cols_to_take = len(idx_vars)
        dim = max(n_eqs, cols_to_take)

        E = np.zeros((dim, dim))
        A = np.zeros((dim, dim))

        A[:n_eqs, :cols_to_take] = EABC[:, idx_vars[:cols_to_take]]

        for i in range(cols_to_take):
            state_sym = self.all_symbols[idx_vars[i]]
            state_name = state_sym.name

            # Critical FIX: Strictly isolate xp and dx to only apply to "x" state arrays
            deriv_names = []
            if state_name.startswith('x'):
                deriv_names.extend([f"xp{state_name[1:]}", f"dx{state_name[1:]}"])
            deriv_names.extend([f"dt_{state_name}", f"d_{state_name}"])

            deriv_idx = -1

            if hasattr(self, '_explicit_deriv_map') and state_name in self._explicit_deriv_map:
                exact_d_name = self._explicit_deriv_map[state_name]
                if exact_d_name in self.sym_to_idx:
                    deriv_idx = self.sym_to_idx[exact_d_name]

            if deriv_idx == -1:
                for d_name in deriv_names:
                    if d_name in self.sym_to_idx:
                        deriv_idx = self.sym_to_idx[d_name]
                        break

            if deriv_idx == -1:
                for dx_idx in idx_dx:
                    dx_name = self.all_symbols[dx_idx].name
                    if dx_name.endswith(f"_{state_name}") and (dx_name.startswith("dt_") or dx_name.startswith("d_")):
                        deriv_idx = dx_idx
                        break

            if deriv_idx != -1 and deriv_idx in idx_dx:
                E[:n_eqs, i] = -EABC[:, deriv_idx]

        B = EABC[:, idx_u] if len(idx_u) > 0 else np.zeros((dim, 0))
        return E, A, B

    def compute_stability(self) -> Tuple[
        Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], bool, Optional[float]]:
        """
            Computes the generalized eigenvalues, eigenvectors, and participation factors
            to evaluate the small-signal stability of the linearized system.

            Algorithmically, this function evaluates the generalized eigenvalue problem (A*v = lambda*E*v).
            Before calling the QZ algorithm, it performs 'Singular Pencil Patching' by scanning for completely
            empty rows and columns in both the E and A matrices, placing a -1.0 on the A diagonal for those
            indices. This critical regularization step neutralizes structural null-spaces, preventing numerical
            divergence during the decomposition. After extracting the finite physical modes, it computes the
            participation matrix (using the normalized Hadamard product of the left and right eigenvectors'
            magnitudes) to map the interaction between physical states and dynamic modes. Finally, it determines
            absolute stability by checking if the right-most eigenvalue resides in the left-half complex plane.

            :return: A tuple containing:
                     - evals (np.ndarray): The finite complex eigenvalues.
                     - evecs_left (np.ndarray): The left eigenvectors.
                     - evecs_right (np.ndarray): The right eigenvectors.
                     - participation_matrix (np.ndarray): State-to-mode participation factors.
                     - is_stable (bool): True if the maximum real part of the eigenvalues is strictly < 1e-6.
                     - max_real (float): The value of the maximum real part of the eigenvalues.
                     Returns (None, None, None, None, False, None) if computation fails or matrices are missing.
            :rtype: Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], bool, Optional[float]]
        """
        current_a, current_e = self.A, self.E
        if current_a is None or current_e is None: return None, None, None, None, False, None

        try:
            A_dense = current_a.toarray() if hasattr(current_a, 'toarray') else np.array(current_a)
            E_dense = current_e.toarray() if hasattr(current_e, 'toarray') else np.array(current_e)

            n_dims = A_dense.shape[0]
            patched_rows, patched_cols = 0, 0

            # --- SINGULAR PENCIL PATCHING (NULL SPACE ELIMINATION) ---
            # 1. Patch empty rows
            for i in range(n_dims):
                if np.max(np.abs(A_dense[i, :])) < 1e-10 and np.max(np.abs(E_dense[i, :])) < 1e-10:
                    A_dense[i, i] = -1.0
                    patched_rows += 1

            # 2. Patch empty columns
            for j in range(n_dims):
                if np.max(np.abs(A_dense[:, j])) < 1e-10 and np.max(np.abs(E_dense[:, j])) < 1e-10:
                    A_dense[j, j] = -1.0
                    patched_cols += 1

            if self.verbose and (patched_rows > 0 or patched_cols > 0):
                print(
                    f"\n[+] QZ Matrix Pre-conditioning: Neutralized {patched_rows} empty rows and {patched_cols} empty columns.")

            evals, evecs_left_raw, evecs_right_raw = linalg.eig(A_dense, b=E_dense, left=True, right=True)

            valid_idx = np.isfinite(evals)
            evals = evals[valid_idx]
            evecs_left = evecs_left_raw[:, valid_idx].astype(complex)
            evecs_right = evecs_right_raw[:, valid_idx].astype(complex)

            if len(evals) == 0: return evals, evecs_left, evecs_right, None, True, -np.inf

            n_states, n_modes = evecs_right.shape
            participation_matrix = np.zeros((n_states, n_modes), dtype=float)

            for m in range(n_modes):
                mag_product = np.abs(evecs_left[:, m]) * np.abs(evecs_right[:, m])
                total_mag = np.sum(mag_product)
                if total_mag > 1e-12: participation_matrix[:, m] = mag_product / total_mag

            max_real = float(np.max(np.real(evals)))
            is_stable = max_real < 1e-6

            if self.verbose:
                print("\n[6] Analysis complete!")
                print(f"  Found {len(evals)} finite eigenvalues (Physical Modes)\n")

            return evals, evecs_left, evecs_right, participation_matrix, is_stable, max_real

        except linalg.LinAlgError as e:
            print(f"Error computing eigenvalues: {e}")
            return None, None, None, None, False, None

    def get_participation_mapping(self, evals: np.ndarray, participation_matrix: np.ndarray,
                                  threshold: float = 0.05) -> dict:
        """
        Maps the raw participation matrix to the exact physical state variables for each dynamic mode.
        Filters out derivative and input tokens to match the true dimensions of the state-space.
        """
        mapping: dict = dict()
        if participation_matrix is None or evals is None: return mapping

        # 1. Dynamically rebuild the exact physical-state order (ignoring dx, xp, u)
        state_symbols: list = list()
        for s in self.all_symbols:
            s_name: str = s.name
            is_deriv: bool = s_name.startswith('dx') or s_name.startswith('xp') or s_name.startswith(
                'd_') or s_name.startswith('dt_')
            is_input: bool = s_name.startswith('u') and not s_name.startswith('u_')

            if not is_deriv and not is_input:
                state_symbols.append(s)

        n_modes: int = int(participation_matrix.shape[1])
        n_states: int = int(participation_matrix.shape[0])

        # 2. Map matrix participation factors to the filtered list
        for m in range(n_modes):
            mode_eval: complex = evals[m]
            mode_pfs: list = list()

            # Iterate up to n_states (in case Singular Pencil Patching / extra padding was applied)
            limit: int = min(n_states, len(state_symbols))
            for i in range(limit):
                pf_val: float = float(participation_matrix[i, m])
                if pf_val >= threshold:
                    mode_pfs.append((state_symbols[i].name, pf_val))

            # Sort variables by dominance level for this specific mode
            mode_pfs.sort(key=lambda x: x[1], reverse=True)
            mapping[mode_eval] = mode_pfs

        return mapping


    def report(self, eigenvalues=None, is_stable=False, max_real=None, print_matrices=True, save_path=None):
        """
            Outputs or exports the internal structural matrices and eigenvalue results
            for diagnostic inspection and external validation.

            Algorithmically, this function provides observability into the compiled Differential
            Algebraic Equation (DAE) system. It sequentially extracts and formats the sparse
            matrices (S, Phi, E, A, B). If eigenvalues are provided, it actively filters for
            finite values and sorts them by their real parts in descending order, immediately
            highlighting the most dynamically critical (or unstable) modes. It optionally serializes
            this system state to a specified file path for persistent logging.

            :param eigenvalues: Array of computed system eigenvalues.
            :type eigenvalues: np.ndarray | None
            :param is_stable: Boolean flag indicating if the system is stable.
            :type is_stable: bool
            :param max_real: The maximum real part found among the eigenvalues.
            :type max_real: float | None
            :param print_matrices: Flag to enable console printing of the matrices.
            :type print_matrices: bool
            :param save_path: Absolute or relative file path to save the exported text report.
            :type save_path: str | None
            :return: Modifies no state; performs I/O operations.
            :rtype: None
        """
        if print_matrices:
            for label, mat in [("S", self.S_H), ("Phi", self.Phi_H), ("E", self.E), ("A", self.A), ("B", self.B)]:
                if mat is not None:
                    print(f"\n--- {label} Matrix ---")
                    print(sparse.csc_matrix(mat))
            if eigenvalues is not None:
                for ev in sorted(list(eigenvalues[np.isfinite(eigenvalues)]), key=_get_real_part, reverse=True):
                    print(f"  {ev.real:.6f} + {ev.imag:.6f}j")

        if save_path is not None:
            import os
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                for label, mat in [("S Matrix", self.S_H), ("Phi Matrix", self.Phi_H), ("E Matrix", self.E),
                                   ("A Matrix", self.A)]:
                    if mat is not None:
                        f.write(f"\n--- {label} ---\n")
                        f.write(str(sparse.csc_matrix(mat)) + "\n")