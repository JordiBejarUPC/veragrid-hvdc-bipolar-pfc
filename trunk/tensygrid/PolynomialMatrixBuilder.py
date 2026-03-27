import sympy as sp
import numpy as np
from numpy import dtype, ndarray
from scipy import sparse, linalg
from sympy.parsing.sympy_parser import parse_expr
from enum import Enum
from typing import Optional, Any, List, Tuple


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

def _get_symbol_name(sym: sp.Symbol) -> str:
    """
    Returns the name of a sympy symbol to act as a sorting key.

    :param sym: SymPy Symbol object.
    :type sym: sp.Symbol
    :return: The string name of the symbol.
    :rtype: str
    """
    return sym.name


def _sort_symbol(sym: sp.Symbol) -> tuple:
    """
    Provides the sorting key tuple for symbols based on TenSyGrid rules.

    :param sym: SymPy Symbol object.
    :type sym: sp.Symbol
    :return: A tuple containing the priority integer and the symbol name.
    :rtype: tuple
    """
    name: str = sym.name

    if name.startswith('dx') or name.startswith('xp') or name.startswith('d_') or name.startswith('dt_'):
        return 0, name
    elif name.startswith('x') and not name.startswith('xp'):
        return 1, name
    elif name.startswith('u'):
        return 2, name
    elif name.startswith('y'):
        return 3, name
    elif name.startswith('z'):
        return 4, name
    else:
        return 5, name


def _get_real_part(val: complex) -> float:
    """
    Returns the real part of a complex number to act as a sorting key.

    :param val: Complex number.
    :type val: complex
    :return: Real part of the complex number.
    :rtype: float
    """
    return float(val.real)


def _arr2str(a: np.ndarray) -> str:
    """
    Formats a numpy array into a structured string.

    :param a: Input array.
    :type a: np.ndarray
    :return: Formatted string representation.
    :rtype: str
    """
    return np.array2string(
        np.asarray(a),
        max_line_width=99999,
        precision=6,
        suppress_small=True,
        threshold=99999,
    )


def _section(title: str, content: str) -> str:
    """
    Formats text into a standardized section for reporting.

    :param title: Section title.
    :type title: str
    :param content: Section body content.
    :type content: str
    :return: Formatted section block.
    :rtype: str
    """
    bar: str = "=" * (len(title) + 4)
    return f"{bar}\n  {title}\n{bar}\n{content}\n"


# ------------------------------------------------------------------
# Main Class
# ------------------------------------------------------------------

class PolynomialMatrixBuilder:
    """
    Builds the S_H / Phi_H (and S_W / Phi_W) matrices from a list of
    polynomial equations, and performs analytic linearization using the
    iMTI / CPN representation described in the TenSyGrid papers.
    """

    # Finalizing the class to prevent dynamic attribute assignment and save memory
    # __slots__ = ['verbose', 'eqs', 'ineqs', 'all_symbols', 'sym_to_idx','S_H', 'Phi_H', 'S_W', 'Phi_W', 'E', 'A', 'B', 'EABC''state_vars', 'algebraic_vars']

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

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

        # --- FIX: INITIALIZE LOCAL PROCESSING LISTS TO PREVENT UNBOUND ERRORS ---
        processed_eqs: list = list()
        processed_ineqs: list = list()
        processed_state_vars: list = list()
        processed_algebraic_vars: list = list()

        def _safe_to_string(item: Any) -> str:
            if hasattr(item, 'expr'):
                return str(getattr(item, 'expr'))
            elif hasattr(item, 'to_string'):
                return item.to_string()
            return str(item)

        has_problem: bool = problem is not None

        if eqs is not None:
            processed_eqs = list(eqs)
        elif has_problem:
            if hasattr(problem, '_state_eqs'):
                for s_eq in problem._state_eqs:
                    processed_eqs.append(_safe_to_string(s_eq))
            if hasattr(problem, '_algebraic_eqs'):
                for a_eq in problem._algebraic_eqs:
                    processed_eqs.append(_safe_to_string(a_eq))

        if ineqs is not None:
            processed_ineqs = list(ineqs)

        if state_vars is not None:
            processed_state_vars = list(state_vars)
        elif has_problem:
            if hasattr(problem, '_state_vars'):
                for s_var in problem._state_vars:
                    processed_state_vars.append(_safe_to_string(s_var))

        if algebraic_vars is not None:
            processed_algebraic_vars = list(algebraic_vars)
        elif has_problem:
            if hasattr(problem, '_algebraic_vars'):
                for a_var in problem._algebraic_vars:
                    processed_algebraic_vars.append(_safe_to_string(a_var))

        parsing_context: dict = dict()
        parsing_context['cos'] = sp.cos
        parsing_context['sin'] = sp.sin
        parsing_context['tan'] = sp.tan
        parsing_context['exp'] = sp.exp
        parsing_context['sqrt'] = sp.sqrt
        parsing_context['pi'] = sp.pi

        parsing_context['Id'] = sp.Symbol('Id')
        parsing_context['Iq'] = sp.Symbol('Iq')
        parsing_context['I'] = sp.Symbol('I')
        parsing_context['E'] = sp.Symbol('E')
        parsing_context['Q'] = sp.Symbol('Q')
        parsing_context['N'] = sp.Symbol('N')
        parsing_context['O'] = sp.Symbol('O')
        parsing_context['S'] = sp.Symbol('S')

        parsed_predefined: list = list()

        for s_name in processed_state_vars:
            new_sym: sp.Symbol = sp.Symbol(s_name)
            parsing_context[s_name] = new_sym
            parsed_predefined.append(new_sym)
            self.state_vars.append(new_sym)

        for a_name in processed_algebraic_vars:
            new_sym: sp.Symbol = sp.Symbol(a_name)
            parsing_context[a_name] = new_sym
            parsed_predefined.append(new_sym)
            self.algebraic_vars.append(new_sym)

        for raw_eq in processed_eqs:
            eq_str: str = raw_eq if isinstance(raw_eq, str) else str(raw_eq)
            parsed_eq: sp.Expr = parse_expr(eq_str, local_dict=parsing_context, evaluate=True)
            self.eqs.append(parsed_eq)

        for raw_ineq in processed_ineqs:
            ineq_str: str = raw_ineq if isinstance(raw_ineq, str) else str(raw_ineq)
            parsed_ineq: sp.Expr = parse_expr(ineq_str, local_dict=parsing_context, evaluate=True)
            self.ineqs.append(parsed_ineq)

        self.all_symbols: list = list()
        self.sym_to_idx: dict = dict()

        combined_exprs: list = list()
        for parsed_e in self.eqs:
            combined_exprs.append(parsed_e)
        for parsed_i in self.ineqs:
            combined_exprs.append(parsed_i)


        self.extract_symbols(combined_exprs, predefined=parsed_predefined)

        # --- FIX: AUTOMATIC FLATTENING & GLOBAL SORTING ---
        self._argaux_map: dict = dict()
        self._flatten_nonlinear_arguments()
        self._apply_automatic_trig_lifting()
        self.all_symbols.sort(key=_sort_symbol)

        self.sym_to_idx.clear()
        idx: int = 0
        for sym in self.all_symbols:
            self.sym_to_idx[sym.name] = idx
            idx = idx + 1

        # --- ALGORITHM: TWO-PASS COMPILATION FOR AUTOMATIC LIFTING ---
        self.matrix_creation(self.eqs)
        self._generate_lifting_equations()

        S_H_sp: sparse.csc_matrix
        Phi_H_sp: sparse.csr_matrix
        S_H_sp, Phi_H_sp = self.matrix_creation(self.eqs)

        S_W_sp: sparse.csc_matrix
        Phi_W_sp: sparse.csr_matrix
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

    def extract_symbols(self, all_exprs: list, predefined: list | None = None) -> list:
        """
        Extracts and sorts symbols from a list of SymPy expressions, incorporating
        any predefined state and algebraic symbols passed by the user.

        :param all_exprs: SymPy expressions to scan.
        :type all_exprs: list
        :param predefined: Optional list of pre-parsed SymPy symbols to include.
        :type predefined: list | None
        :return: Sorted list of unique symbols.
        :rtype: list
        """
        seen: set = set()
        extracted_symbols: list = list()

        # Explicitly inject predefined symbols first
        if predefined is not None:
            sym_p: sp.Symbol
            for sym_p in predefined:
                if sym_p not in seen:
                    seen.add(sym_p)
                    extracted_symbols.append(sym_p)
                else:
                    pass
        else:
            pass

        # Scan expressions for any additional symbols not predefined
        for eq in all_exprs:
            eq_symbols: list = list(eq.free_symbols)
            eq_symbols.sort(key=_get_symbol_name)

            for sym in eq_symbols:
                if sym not in seen:
                    seen.add(sym)
                    extracted_symbols.append(sym)
                else:
                    pass

        # Apply priority sorting strictly to all gathered symbols
        extracted_symbols.sort(key=_sort_symbol)

        if self.verbose:
            print(f"Unified symbols order: {extracted_symbols}\n")
        else:
            pass

        self.all_symbols = extracted_symbols
        return extracted_symbols

    # ------------------------------------------------------------------
    # Matrix creation
    # ------------------------------------------------------------------

    def matrix_creation(self, all_exprs: list) -> tuple:
        """
        Creates the S and Phi sparse matrices with automatic L1 normalisation.

        :param all_exprs: SymPy expressions to encode.
        :type all_exprs: list
        :return: Tuple containing S (csc_matrix) and Phi (csr_matrix).
        :rtype: tuple
        """
        S_list: list = list()
        Phi_data: list = list()
        monom_to_idx: dict = dict()

        if self.verbose:
            print("--- Analyzing Expressions for Matrices ---")
        else:
            pass

        eq_idx: int = 0
        for eq in all_exprs:
            if self.verbose:
                print(f"\nEquation {eq_idx + 1}: {eq}")
            else:
                pass

            # We split the equation into the different terms
            terms: list
            if eq.is_Add:
                terms = list(eq.args)
            else:
                terms = [eq]

            current_eq_coeffs: dict = dict()

            # It gets the factors of each term that go in S and Phi
            for term in terms:
                current_eq_coeffs = self._get_monomial_weights(
                    term, S_list, monom_to_idx, current_eq_coeffs
                )

            Phi_data.append(current_eq_coeffs)
            eq_idx = eq_idx + 1

        # Assemble sparse matrices
        S: sparse.csc_matrix
        Phi: sparse.csr_matrix

        if len(S_list) > 0:
            S_raw: np.ndarray = np.vstack(S_list).T.astype(float)
            S = sparse.csc_matrix(S_raw)
            num_cols: int = S_raw.shape[1]
            phi_rows: list = list()

            for eq_dict in Phi_data:
                row: np.ndarray = np.zeros(num_cols)
                # Dictionary iteration is safe here as it represents matrix columns
                for col_idx, val in eq_dict.items():
                    row[col_idx] = val
                phi_rows.append(row)

            Phi = sparse.csr_matrix(np.vstack(phi_rows))
        else:
            # Matrices are empty, use correct shapes
            S = sparse.csc_matrix((len(self.all_symbols), 0))
            Phi = sparse.csr_matrix((len(all_exprs), 0))

        return S, Phi

    def _get_monomial_weights(
            self,
            term: sp.Expr,
            S_list: list,
            monom_to_idx: dict,
            current_eq_coeffs: dict
    ) -> dict:
        """
        Processes a term to extract its global coefficients and internal weights.
        If the term contains multi-variable factors, it expands it recursively.

        :param term: The mathematical term to be processed.
        :type term: sp.Expr
        :param S_list: The collection of unique monomial weight arrays.
        :type S_list: list
        :param monom_to_idx: Dictionary mapping a monomial weight tuple to its matrix index.
        :type monom_to_idx: dict
        :param current_eq_coeffs: Dictionary of global coefficients for the current equation.
        :type current_eq_coeffs: dict
        :return: The updated dictionary of global coefficients for the current equation.
        :rtype: dict
        """
        coeff_sym: sp.Expr
        symbolic_part: tuple
        coeff_sym, symbolic_part = term.as_coeff_mul()

        factors: tuple = sp.Mul.make_args(sp.Mul(*symbolic_part))
        requires_expansion: bool = False

        # Checks if the term is of the form k(a+y_i)x or k(a+y_i+y_j)x => Later requires expansion
        for f in factors:
            f_vars: list = list(f.free_symbols)
            if len(f_vars) > 1:
                requires_expansion = True
            else:
                pass

        if requires_expansion:
            if self.verbose:
                print(f"   Expanding complex term: {term}")
            else:
                pass

            expanded_expr: sp.Expr = term.expand()
            expanded_sub_terms: tuple = sp.Add.make_args(expanded_expr)

            # --- ALGORITHM: PREVENT INFINITE RECURSION ---
            # If expanding the term returns the exact same single term, it means
            # it is an irreducible multi-variable non-polynomial (e.g., sqrt(x**2 + y**2)).
            # iMTI requires intermediate variables for such cases.
            if len(expanded_sub_terms) == 1:
                if expanded_sub_terms[0] == term:
                    raise ValueError(
                        f"Irreducible multi-variable non-linear term detected: {term}. "
                        "The iMTI CPN methodology requires non-polynomial functions to be "
                        "applied to single variables. Please define an intermediate "
                        "algebraic variable (e.g., z1 = x1**2 + x2**2) in your equations."
                    )
                else:
                    pass
            else:
                pass

            sub_t: sp.Expr
            for sub_t in expanded_sub_terms:
                current_eq_coeffs = self._get_monomial_weights(
                    sub_t, S_list, monom_to_idx, current_eq_coeffs
                )
            return current_eq_coeffs

        else:
            global_phi: float = float(coeff_sym)
            weights: list = list()

            for _ in range(len(self.all_symbols)):
                weights.append(0.0)

            for f in factors:
                f_vars_inner: list = list(f.free_symbols)

                if len(f_vars_inner) == 1:
                    s: sp.Symbol = f_vars_inner[0]
                    idx_val: int | None = self.sym_to_idx.get(s.name, None)

                    if idx_val is not None:
                        b_val_sym: sp.Expr = sp.diff(f, s)

                        # --- MULTILINEARITY CHECK (Lifting) ---
                        # ALGORITHM: Extract degree as float to prevent truncating 0.5 to 0
                        deg: float = 1.0
                        if isinstance(f, sp.Pow):
                            deg = float(f.exp)
                        else:
                            deg = float(sp.degree(f, s))

                        # Floating point comparison for safety
                        is_sqrt: bool = abs(deg - 0.5) < 1e-6

                        if (deg > 1.0 or deg < 0.0) and not is_sqrt:
                            # 1. Determine lifting type and number of variables
                            is_positive: bool = deg > 1.0
                            num_aux: int = int(deg - 1.0) if is_positive else int(-deg + 1.0)
                            prefix: str = "mulaux" if is_positive else "invaux"

                            # Rule: Explicit loop instead of list comprehension
                            new_vars_names: list = list()
                            i_aux: int
                            for i_aux in range(num_aux):
                                new_vars_names.append(str(f"{s.name}_{prefix}{i_aux}"))

                            new_symbols_list: list = list()
                            vars_added: bool = False

                            # 2. Register variables in the global state
                            v_name: str
                            for v_name in new_vars_names:
                                if v_name not in self.sym_to_idx:
                                    new_sym_obj: sp.Symbol = sp.Symbol(v_name)
                                    self.all_symbols.append(new_sym_obj)
                                    self.sym_to_idx[v_name] = len(self.all_symbols) - 1
                                    new_symbols_list.append(new_sym_obj)
                                    vars_added = True
                                else:
                                    # Retrieve existing symbol object
                                    idx_existing: int = self.sym_to_idx[v_name]
                                    new_symbols_list.append(self.all_symbols[idx_existing])

                            # 3. CRITICAL: If variables were added, pad S_list
                            if vars_added:
                                new_total_size: int = len(self.all_symbols)
                                i_p: int
                                for i_p in range(len(S_list)):
                                    current_vec: np.ndarray = S_list[i_p]
                                    padding_size: int = new_total_size - current_vec.shape[0]
                                    if padding_size > 0:
                                        # Use np.concatenate for zero overhead padding
                                        S_list[i_p] = np.concatenate([current_vec, np.zeros(padding_size)])
                                    else:
                                        pass
                            else:
                                pass

                            # 4. Create the multilinear equivalent expression
                            multilinear_f: sp.Expr = s
                            sym_aux: sp.Symbol
                            for sym_aux in new_symbols_list:
                                multilinear_f = multilinear_f * sym_aux

                            if self.verbose:
                                print(f"LIFTING: {f} -> {multilinear_f}")
                            else:
                                pass

                            # 5. RE-CALL: Re-process the term with the new multilinear form
                            new_term: sp.Expr = (term / f) * multilinear_f
                            return self._get_monomial_weights(
                                new_term, S_list, monom_to_idx, current_eq_coeffs
                            )

                        elif is_sqrt:
                            # 1. Determine lifting type: sqrt(s) -> s_sqrtaux0, s_sqrtaux1
                            # We MUST use TWO variables to maintain the strict multilinear basis
                            new_vars_names_sqrt: list = list([str(f"{s.name}_sqrtaux0"), str(f"{s.name}_sqrtaux1")])
                            new_symbols_list_sqrt: list = list()
                            vars_added_sqrt: bool = False

                            # 2. Register variables in the global state
                            v_name_sqrt: str
                            for v_name_sqrt in new_vars_names_sqrt:
                                if v_name_sqrt not in self.sym_to_idx:
                                    new_sym_obj_sqrt: sp.Symbol = sp.Symbol(v_name_sqrt)
                                    self.all_symbols.append(new_sym_obj_sqrt)
                                    self.sym_to_idx[v_name_sqrt] = len(self.all_symbols) - 1
                                    new_symbols_list_sqrt.append(new_sym_obj_sqrt)
                                    vars_added_sqrt = True
                                else:
                                    # Retrieve existing symbol object explicitly from registry
                                    idx_existing_sqrt: int = self.sym_to_idx[v_name_sqrt]
                                    new_symbols_list_sqrt.append(self.all_symbols[idx_existing_sqrt])

                            # 3. CRITICAL: Pad previous monoms in S_list
                            if vars_added_sqrt:
                                new_total_size_sqrt: int = len(self.all_symbols)
                                i_p_sqrt: int
                                for i_p_sqrt in range(len(S_list)):
                                    current_vec_sqrt: np.ndarray = S_list[i_p_sqrt]
                                    padding_size_sqrt: int = new_total_size_sqrt - current_vec_sqrt.shape[0]
                                    if padding_size_sqrt > 0:
                                        # Zero overhead padding
                                        S_list[i_p_sqrt] = np.concatenate(
                                            [current_vec_sqrt, np.zeros(padding_size_sqrt)])
                                    else:
                                        pass
                            else:
                                pass

                            # 4. Create the multilinear equivalent expression
                            # The term itself is replaced by the first auxiliary symbol
                            multilinear_f_sqrt: sp.Expr = new_symbols_list_sqrt[0]

                            if self.verbose:
                                print(f"LIFTING SQRT: {f} -> {multilinear_f_sqrt} (with multilinear constraints)")
                            else:
                                pass

                            # 5. RE-CALL: Re-process the term with the new form
                            new_term_sqrt: sp.Expr = (term / f) * multilinear_f_sqrt
                            return self._get_monomial_weights(
                                new_term_sqrt, S_list, monom_to_idx, current_eq_coeffs
                            )
                        else:
                            pass

                        b_val: float = float(b_val_sym)
                        a_val: float = float(f.subs(s, 0))

                        scale: float = abs(a_val) + abs(b_val)
                        if scale == 0.0:
                            scale = 1.0
                        else:
                            pass

                        weights[idx_val] = b_val / scale
                        global_phi = global_phi * scale
                    else:
                        pass

                elif len(f_vars_inner) == 0:
                    global_phi = global_phi * float(f)
                else:
                    pass

            monom_tuple: tuple = tuple(weights)
            existing_idx: int | None = monom_to_idx.get(monom_tuple, None)
            final_idx: int = 0

            if existing_idx is None:
                final_idx = len(S_list)
                monom_to_idx[monom_tuple] = final_idx
                S_list.append(np.array(monom_tuple))
            else:
                final_idx = existing_idx

            current_val: float | None = current_eq_coeffs.get(final_idx, None)

            if current_val is None:
                current_eq_coeffs[final_idx] = global_phi
            else:
                current_eq_coeffs[final_idx] = current_val + global_phi

            return current_eq_coeffs

    def _apply_automatic_trig_lifting(self) -> None:
        """
        ALGORITHM: Automatic Multilinear Lifting via Lie-Bäcklund Isomorphism.
        Transforms trigonometric non-linearities into extended polynomial states.
        Registers the new variables globally to ensure matrix column allocation.
        """
        import sympy as sp

        new_eqs: list = list()
        subs_dict: dict = dict()
        processed_args: set = set()

        for eq in self.eqs:
            trig_terms = eq.atoms(sp.sin, sp.cos)

            for term in trig_terms:
                arg = term.args[0]

                if arg not in processed_args:
                    # 1. Define extended state and derivative variables using native prefixes
                    s_var = sp.Symbol(f"x_sin_{arg.name}")
                    c_var = sp.Symbol(f"x_cos_{arg.name}")

                    sp_var = sp.Symbol(f"xp_sin_{arg.name}")
                    cp_var = sp.Symbol(f"xp_cos_{arg.name}")

                    # Assume the derivative of the argument replaces 'x' with 'xp'
                    arg_p = sp.Symbol(arg.name.replace('x', 'xp'))

                    # 2. Formulate the differential equations for the tangent space
                    eq_ds = sp_var - (c_var * arg_p)
                    eq_dc = cp_var + (s_var * arg_p)

                    new_eqs.extend([eq_ds, eq_dc])

                    # 3. Store the substitution mapping
                    subs_dict[sp.sin(arg)] = s_var
                    subs_dict[sp.cos(arg)] = c_var

                    # --- ARCHITECTURE FIX: REGISTER IN GLOBAL STATE ---
                    # We must tell the Builder that these new variables exist
                    # before it calls self.all_symbols.sort() in __init__
                    for new_sym in [s_var, c_var, sp_var, cp_var]:
                        if new_sym not in self.all_symbols:
                            self.all_symbols.append(new_sym)

                    processed_args.add(arg)

        # 4. Apply substitutions and append the new differential equations
        lifted_original_eqs: list = [eq.subs(subs_dict) for eq in self.eqs]
        self.eqs = lifted_original_eqs + new_eqs

        if self.verbose:
            print(f"[LIFTING] Applied Lie-Bäcklund isomorphism to {len(processed_args)} angular variables.")

    def _generate_lifting_equations(self) -> None:
        """
        Automatically generates and appends the algebraic constraint equations
        for all internally generated auxiliary variables (lifting).
        This ensures the system matrix remains square and mathematically valid.

        :return: None
        :rtype: None
        """
        # Rule: Explicit lists
        new_constraints: list = list()

        sym: sp.Symbol
        for sym in self.all_symbols:
            s_name: str = sym.name

            # --- ALGORITHM: LIFTING DETECTION ---
            is_mul: bool = "_mulaux" in s_name
            is_inv: bool = "_invaux" in s_name
            is_sqrt: bool = "_sqrtaux" in s_name

            if is_mul:
                # Generate x_base - x_aux = 0
                base_name_m: str = s_name.split("_mulaux")[0]
                base_sym_m: Optional[sp.Symbol] = self._get_symbol_by_name(base_name_m)

                if base_sym_m is not None:
                    constraint_m: sp.Expr = base_sym_m - sym
                    # Prevent duplicates if method is called safely multiple times
                    if constraint_m not in self.eqs:
                        new_constraints.append(constraint_m)
                    else:
                        pass
                else:
                    pass

            elif is_inv:
                # Generate x_base * x_aux - 1.0 = 0
                base_name_i: str = s_name.split("_invaux")[0]
                base_sym_i: Optional[sp.Symbol] = self._get_symbol_by_name(base_name_i)

                if base_sym_i is not None:
                    constraint_i: sp.Expr = base_sym_i * sym - 1.0
                    if constraint_i not in self.eqs:
                        new_constraints.append(constraint_i)
                    else:
                        pass
                else:
                    pass


            elif is_sqrt:
                # We need to find both aux variables to form the multilinear constraints
                if s_name.endswith("_sqrtaux0"):
                    base_name_s: str = s_name.split("_sqrtaux0")[0]
                    base_sym_s: Optional[sp.Symbol] = self._get_symbol_by_name(base_name_s)
                    sym_aux1: Optional[sp.Symbol] = self._get_symbol_by_name(f"{base_name_s}_sqrtaux1")
                    if base_sym_s is not None and sym_aux1 is not None:
                        # Constraint 1: base - z0*z1 = 0 (Strict multilinear square)
                        constraint_s1: sp.Expr = base_sym_s - (sym * sym_aux1)
                        if constraint_s1 not in self.eqs:
                            new_constraints.append(constraint_s1)
                        else:
                            pass
                        # Constraint 2: z0 - z1 = 0 (Equality enforcement)
                        constraint_s2: sp.Expr = sym - sym_aux1
                        if constraint_s2 not in self.eqs:
                            new_constraints.append(constraint_s2)
                        else:
                            pass
                    else:
                        pass
                else:
                    # _sqrtaux1 is handled when the loop processes _sqrtaux0
                    pass

        # --- ALGORITHM: MATRIX AUGMENTATION ---
        # Append the new structural equations directly to the core list
        if len(new_constraints) > 0:
            if self.verbose:
                print(f"Adding {len(new_constraints)} lifting constraints to the system.")
            else:
                pass

            constraint_eq: sp.Expr
            for constraint_eq in new_constraints:
                self.eqs.append(constraint_eq)
        else:
            pass

    def _get_symbol_by_name(self, name: str) -> Optional[sp.Symbol]:
        """
        Helper method to retrieve a sympy Symbol safely.

        :param name: The string name of the symbol to find.
        :type name: str
        :return: The sympy Symbol if found, None otherwise.
        :rtype: Optional[sp.Symbol]
        """
        target_sym: sp.Symbol
        for target_sym in self.all_symbols:
            if target_sym.name == name:
                return target_sym
            else:
                pass
        return None

    def _flatten_nonlinear_arguments(self) -> None:
        """
        ALGORITHM: Automatic Argument Lifting (Flattening).
        Scans all equations for non-linear functions (like fractional powers)
        that have complex multi-variable expressions as arguments.
        Automatically generates intermediate algebraic variables (nodes)
        to satisfy the iMTI CPN requirements transparently to the user.
        """
        new_constraints: list = list()
        arg_counter: int = 0

        lists_to_process: list = [self.eqs, self.ineqs]

        eq_list: list
        for eq_list in lists_to_process:
            i: int
            for i in range(len(eq_list)):
                current_eq: sp.Expr = eq_list[i]

                # Find all power operations (sqrt is interpreted as Pow(base, 0.5))
                powers: set = current_eq.find(sp.Pow)

                p: sp.Pow
                for p in powers:
                    exp_val: sp.Expr = p.exp

                    # Check if it is a non-linear (fractional) power
                    is_fractional: bool = False
                    if not exp_val.is_integer:
                        is_fractional = True
                    else:
                        pass

                    if is_fractional:
                        base_expr: sp.Expr = p.base

                        # Check if the base is a complex expression (not a single symbol)
                        if not isinstance(base_expr, sp.Symbol):
                            aux_name: str = str(f"argaux{arg_counter}")
                            arg_counter = arg_counter + 1

                            new_sym: sp.Symbol = sp.Symbol(aux_name)
                            if new_sym not in self.all_symbols:
                                self.all_symbols.append(new_sym)
                            else:
                                pass

                            # Save the exact mathematical mapping for operating point synchronization
                            self._argaux_map[new_sym] = base_expr

                            # Replace the complex base with the new single symbol in the equation
                            new_p: sp.Expr = new_sym ** exp_val
                            current_eq = current_eq.subs(p, new_p)

                            # Create the structural constraint: argaux - (x1**2 + x2**2) = 0
                            constraint: sp.Expr = new_sym - base_expr
                            new_constraints.append(constraint)
                        else:
                            pass
                    else:
                        pass

                # Apply the flattened equation back to the list
                eq_list[i] = current_eq

        # Append all new structural constraints to the system equations
        c: sp.Expr
        for c in new_constraints:
            self.eqs.append(c)

    # ------------------------------------------------------------------
    # Linearisation – public entry point
    # ------------------------------------------------------------------
    def linearize_with_problem(self, problem: Any, v_dict_override: Optional[dict] = None) -> np.ndarray:
        """
        Syncs the MTI_Problem's internal state (including dxOP) with the builder
        to ensure nonlinear terms are linearized at the correct operating point.
        """
        # Start with the problem's full initial guess (x, y, dx, u, etc.)
        full_v = problem.init_guess.copy()

        # Override with any specific values from your test's v_dict
        if v_dict_override:
            full_v.update(v_dict_override)

        # Call the standard linearization
        return self.linearize(full_v)

    def linearize(self, v_dict: dict, c_type: ConstraintType = ConstraintType.EQUALITY) -> np.ndarray:
        """
        Analytic linearization for iMTI models (CPN representation).
        Automatically computes the operating points for lifted trigonometric variables
        before evaluating the Jacobian matrix.
        """
        import math

        keys_to_check: list = list(v_dict.keys())
        key: str
        for key in keys_to_check:
            if key.startswith('x') and 'p' not in key:
                val: float = float(v_dict[key])

                # --- ARCHITECTURE FIX: EXACT PREFIX MATCHING ---
                # These keys MUST match the sp.Symbol names generated in the lifting method
                v_dict[f"x_sin_{key}"] = math.sin(val)
                v_dict[f"x_cos_{key}"] = math.cos(val)

                v_dict[f"xp_sin_{key}"] = 0.0
                v_dict[f"xp_cos_{key}"] = 0.0

        S: np.ndarray
        Phi: np.ndarray
        S, Phi = self._get_matrices(c_type)

        v: np.ndarray = self._build_v_vector(v_dict)
        F: np.ndarray = self._compute_jacobian(S, v)

        self.EABC = Phi @ F.T
        self.E, self.A, self.B = self._split_EABC(self.EABC)

        return self.EABC

    # ------------------------------------------------------------------
    # Linearisation – private helpers
    # ------------------------------------------------------------------

    def _get_matrices(self, c_type: ConstraintType) -> tuple:
        """
        Return the (S, Phi) pair for equations or inequalities based on Enum.

        :param c_type: Type of constraint matrix to retrieve.
        :type c_type: ConstraintType
        :return: S and Phi arrays.
        :rtype: tuple
        """
        if c_type == ConstraintType.INEQUALITY:
            return self.S_W, self.Phi_W
        else:
            return self.S_H, self.Phi_H

    def _build_v_vector(self, v_dict_local: dict) -> np.ndarray:
        """
        Builds the numerical state vector ensuring all iMTI lifted
        variables (argaux, sqrtaux, mulaux) are strictly synchronized
        to prevent singular Jacobians during evaluation.
        """
        n_vars: int = len(self.all_symbols)
        v: np.ndarray = np.zeros(n_vars, dtype=float)

        # 1. Fill standard variables from user dictionary
        k: str
        val: float
        for k, val in v_dict_local.items():
            if k in self.sym_to_idx:
                v[self.sym_to_idx[k]] = float(val)
            else:
                pass

        # 2. ALGORITHM: COMPLEX ARGUMENT SYNCHRONIZATION
        # Evaluate argaux variables first, as other lifted variables depend on them
        sym_arg: sp.Symbol
        for sym_arg in self.all_symbols:
            if sym_arg in self._argaux_map:
                base_expr: sp.Expr = self._argaux_map[sym_arg]

                subs_dict: dict = dict()
                s_free: sp.Symbol
                for s_free in base_expr.free_symbols:
                    idx_free: Optional[int] = self.sym_to_idx.get(s_free.name, None)
                    if idx_free is not None:
                        subs_dict[s_free] = float(v[idx_free])
                    else:
                        pass

                idx_arg: Optional[int] = self.sym_to_idx.get(sym_arg.name, None)
                if idx_arg is not None:
                    v[idx_arg] = float(base_expr.subs(subs_dict))
                else:
                    pass

        # 3. ALGORITHM: STANDARD LIFTING VARIABLES SYNCHRONIZATION
        sym: sp.Symbol
        for sym in self.all_symbols:
            s_name: str = sym.name
            if s_name not in v_dict_local:
                idx_current: int = self.sym_to_idx[s_name]

                # Multiplicative auxiliary variables
                if "_mulaux" in s_name:
                    base_name_m: str = s_name.split("_mulaux")[0]
                    base_idx_m: Optional[int] = self.sym_to_idx.get(base_name_m, None)
                    if base_idx_m is not None:
                        v[idx_current] = v[base_idx_m]
                    else:
                        pass

                # Square root auxiliary variables
                elif "_sqrtaux" in s_name:
                    base_name_s: str = s_name.split("_sqrtaux")[0]
                    base_idx_s: Optional[int] = self.sym_to_idx.get(base_name_s, None)
                    if base_idx_s is not None:
                        val_base_s: float = float(v[base_idx_s])
                        if val_base_s > 0.0:
                            v[idx_current] = float(np.sqrt(val_base_s))
                        else:
                            pass
                    else:
                        pass
                else:
                    pass

        return v

    def _compute_jacobian(self, S: np.ndarray, v: np.ndarray) -> np.ndarray:
        """
        Compute the analytic Jacobian of the monomial basis at point *v*.

        :param S: Weight matrix (n_vars x n_monomials).
        :type S: np.ndarray
        :param v: Operating-point vector (n_vars,).
        :type v: np.ndarray
        :return: Jacobian F (n_vars x n_monomials).
        :rtype: np.ndarray
        """
        X: np.ndarray = (S.T * v) + (1.0 - np.abs(S.T))
        Y: np.ndarray = np.prod(X, axis=1)

        with np.errstate(divide='ignore', invalid='ignore'):
            invX: np.ndarray = np.where(np.abs(X) > 1e-12, 1.0 / X, 0.0)
            F: np.ndarray = S * (Y[:, np.newaxis] * invX).T

            zeros_per_col: np.ndarray = np.sum(np.abs(X) < 1e-12, axis=1)
            single_zero_cols: tuple = np.where(zeros_per_col == 1)

            for col in single_zero_cols[0]:
                zero_row_tuple: tuple = np.where(np.abs(X[col, :]) < 1e-12)
                zero_row: int = int(zero_row_tuple[0][0])
                other_factors: np.ndarray = np.delete(X[col, :], zero_row)
                F[zero_row, col] = S[zero_row, col] * np.prod(other_factors)

        return F

    def _split_EABC(self, EABC: np.ndarray) -> tuple:
        """
        Splits the EABC matrix into E, A, and B descriptor matrices.
        ALGORITHM: Strictly aligns derivative variables in E with their
        corresponding state variables in A to prevent matrix dislocation.

        :param EABC: Full Jacobian matrix.
        :type EABC: np.ndarray
        :return: Tuple containing E, A, and B matrices.
        :rtype: tuple
        """
        idx_dx: list = list()
        idx_vars: list = list()
        idx_u: list = list()

        # 1. Categorize indices
        idx_counter: int = 0
        s: sp.Symbol
        for s in self.all_symbols:
            s_name: str = s.name
            if s_name.startswith('dx') or s_name.startswith('xp') or s_name.startswith('d_') or s_name.startswith(
                'dt_'):
                idx_dx.append(idx_counter)
            elif s_name.startswith('u') and not s_name.startswith('u_'):
                idx_u.append(idx_counter)
            else:
                # All other variables (x, y, z, argaux, sqrtaux) belong to the state vector
                idx_vars.append(idx_counter)

            idx_counter = idx_counter + 1
        #print(f"\n[DEBUG] Derivadas detectadas en la lista: {[self.all_symbols[idx].name for idx in idx_dx]}")
        n_eqs: int = int(EABC.shape[0])
        E: np.ndarray = np.zeros((n_eqs, n_eqs))
        A: np.ndarray = np.zeros((n_eqs, n_eqs))

        cols_to_take: int = len(idx_vars)
        if cols_to_take > n_eqs:
            cols_to_take = n_eqs
        else:
            pass

        # 2. Build A matrix (State variables)
        A[:, :cols_to_take] = EABC[:, idx_vars[:cols_to_take]]

        # 3. Build E matrix (Derivatives strictly aligned to state variables)
        i: int
        for i in range(cols_to_take):
            state_idx: int = idx_vars[i]
            state_sym: sp.Symbol = self.all_symbols[state_idx]
            state_name: str = state_sym.name

            # Identify expected derivative names
            deriv_names: list = list()
            if state_name.startswith('x'):
                deriv_names.append(str("xp" + state_name[1:]))
                deriv_names.append(str("dx" + state_name[1:]))

            deriv_names.append(str("dt_" + state_name))
            deriv_names.append(str("d_" + state_name))

            # 1. Búsqueda exacta (Ej: d_u_cos -> u_cos)
            deriv_idx: int = -1
            d_name: str
            for d_name in deriv_names:
                if d_name in self.sym_to_idx:
                    deriv_idx = self.sym_to_idx[d_name]
                    break

            # 2. Búsqueda flexible para prefijos de componentes (Ej: dt_1_Vf -> Vf)
            if deriv_idx == -1:
                for dx_idx in idx_dx:
                    dx_name = self.all_symbols[dx_idx].name
                    # Si la derivada termina en "_Vf" y el estado es "Vf", es la suya
                    if dx_name.endswith(f"_{state_name}") and (dx_name.startswith("dt_") or dx_name.startswith("d_")):
                        deriv_idx = dx_idx
                        break

            # If a derivative exists, place it in the EXACT SAME column as the state
            if deriv_idx != -1 and deriv_idx in idx_dx:
                E[:, i] = -EABC[:, deriv_idx]

        B: np.ndarray = EABC[:, idx_u]

        return E, A, B

    # ------------------------------------------------------------------
    # Stability analysis
    # ------------------------------------------------------------------

    def compute_stability(self) -> Tuple[
        Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], bool, Optional[float]]:
        """
        Compute generalised eigenvalues for the descriptor pair (A, E).

        :return: tuple of (eigenvalues, left_evecs, right_evecs, participation, is_stable, max_real)
        :rtype: Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], bool, Optional[float]]
        """
        current_a: np.ndarray | None = self.A
        current_e: np.ndarray | None = self.E

        if current_a is None or current_e is None:
            return None, None, None, None, False, None
        else:
            pass

        try:
            evals: np.ndarray
            evecs_left_raw: np.ndarray
            evecs_right_raw: np.ndarray
            evals, evecs_left_raw, evecs_right_raw = linalg.eig(current_a, current_e, left=True, right=True)

            # --- ALGORITHM: INFINITE AND NAN FILTERING ---
            # 1. Identify which indices correspond to valid finite values
            valid_idx: np.ndarray = np.isfinite(evals)

            # 2. Keep only the valid finite eigenvalues
            evals = evals[valid_idx]

            # --- ALGORITHM: MEMORY SPACE PROTECTION ---
            # 3. Filter eigenvector columns to match valid eigenvalues, and cast to
            #    complex to prevent TypeError during complex normalization.
            evecs_left: np.ndarray = evecs_left_raw[:, valid_idx].astype(complex)
            evecs_right: np.ndarray = evecs_right_raw[:, valid_idx].astype(complex)

            if len(evals) == 0:
                return evals, evecs_left, evecs_right, None, True, -np.inf
            else:
                pass

            # --- ALGORITHM: PARTICIPATION MATRIX NORMALIZATION ---
            n_states: int = int(evecs_right.shape[1])
            i: int
            for i in range(n_states):
                # 1. Calculate the normalization scalar
                scaling_val: complex = complex(np.vdot(evecs_left[:, i], evecs_right[:, i]))
                scaling_mag: float = float(np.abs(scaling_val))

                # 2. Safety check against division by zero AND NaN propagation
                is_invalid: bool = False
                if np.isnan(scaling_mag):
                    is_invalid = True
                elif scaling_mag < 1e-12:
                    is_invalid = True
                else:
                    pass

                if is_invalid:
                    # If the mode is singular or defective, zeroing the left eigenvector
                    # forces its participation to 0.0, avoiding NaN propagation.
                    evecs_left[:, i] = 0.0 + 0.0j
                else:
                    # 3. Normalization
                    evecs_left[:, i] = evecs_left[:, i] / scaling_val

            # 4. Element-wise matrix multiplication to compute participation factors
            participation_matrix: np.ndarray = np.abs(evecs_right) * np.abs(evecs_left)

            max_real: float = float(np.max(np.real(evals)))
            is_stable: bool = False

            if max_real < 0.0:
                is_stable = True
            else:
                pass

            return evals, evecs_left, evecs_right, participation_matrix, is_stable, max_real

        except linalg.LinAlgError as e:
            # We catch strictly LinAlgError because Scipy internally throws this on convergence failure
            print(f"Error computing eigenvalues: {e}")
            if self.verbose:
                det_val: float = float(linalg.det(current_e - current_a))
                print(f"det(E - A) = {det_val}")
            else:
                pass
            return None, None, None, None, False, None

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def report(
            self,
            eigenvalues: np.ndarray | None = None,
            is_stable: bool = False,
            max_real: float | None = None,
            print_matrices: bool = True,
            save_path: str | None = None,
    ) -> None:
        """
        Print and/or save all matrices and stability results.

        :param eigenvalues: Array of eigenvalues.
        :type eigenvalues: np.ndarray | None
        :param is_stable: Boolean flag indicating if the system is stable.
        :type is_stable: bool
        :param max_real: Maximum real part among the eigenvalues.
        :type max_real: float | None
        :param print_matrices: Flag to trigger stdout printing.
        :type print_matrices: bool
        :param save_path: Absolute or relative file path for writing outputs.
        :type save_path: str | None
        :return: None
        :rtype: None
        """
        if print_matrices:
            # Replaced comprehension with explicit loop of tuples
            matrix_refs: list = [
                ("S", self.S_H),
                ("Phi", self.Phi_H),
                ("E", self.E),
                ("A", self.A),
                ("B", self.B),
            ]

            for label, mat in matrix_refs:
                if mat is not None:
                    print(f"\n--- {label} Matrix ---")
                    print(sparse.csc_matrix(mat))
                else:
                    pass

            print("\n--- Stability Analysis ---")
            print(f"Is stable:     {is_stable}")
            print(f"Max Real Part: {max_real}")

            if eigenvalues is not None:
                valid_evs: list = list(eigenvalues[np.isfinite(eigenvalues)])
                sorted_evs: list = sorted(valid_evs, key=_get_real_part, reverse=True)
                print("Eigenvalues:")
                for ev in sorted_evs:
                    print(f"  {ev.real:.6f} + {ev.imag:.6f}j")
            else:
                pass
        else:
            pass

        if save_path is not None:
            import os
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)

            # Using an explicit file writer structure
            with open(save_path, "w", encoding="utf-8") as f:

                matrix_write_refs: list = [
                    ("S Matrix", self.S_H),
                    ("Phi Matrix", self.Phi_H),
                    ("E Matrix", self.E),
                    ("A Matrix", self.A),
                    ("B Matrix", self.B),
                ]

                for label_w, mat_w in matrix_write_refs:
                    if mat_w is not None:
                        formatted_mat: str = _arr2str(mat_w)
                        section_str: str = _section(label_w, formatted_mat)
                        f.write(section_str + "\n")
                    else:
                        pass

                stability_txt: str = (
                    f"Is stable:     {is_stable}\n"
                    f"Max Real Part: {max_real}\n"
                )

                if eigenvalues is not None:
                    evs_str_list: list = list()
                    for ev in eigenvalues:
                        evs_str_list.append(f"  {ev}")

                    # Using a simple loop instead of join with comprehension
                    evs_txt: str = ""
                    for s_ev in evs_str_list:
                        evs_txt = evs_txt + s_ev + "\n"

                    stability_txt = stability_txt + f"Eigenvalues:\n{evs_txt}\n"
                else:
                    pass

                final_section: str = _section("Stability Analysis", stability_txt)
                f.write(final_section)

            print(f"\nMatrices saved to: {save_path}")
        else:
            pass