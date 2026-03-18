import sympy as sp
import numpy as np
from scipy import sparse, linalg
from sympy.parsing.sympy_parser import parse_expr
from enum import Enum
from typing import Optional, Any



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
# Main Class
# ------------------------------------------------------------------

class PolynomialMatrixBuilder:
    """
    Builds the S_H / Phi_H (and S_W / Phi_W) matrices from a list of
    polynomial equations, and performs analytic linearization using the
    iMTI / CPN representation described in the TenSyGrid papers.
    """

    # Finalizing the class to prevent dynamic attribute assignment and save memory
    #__slots__ = ['verbose', 'eqs', 'ineqs', 'all_symbols', 'sym_to_idx','S_H', 'Phi_H', 'S_W', 'Phi_W', 'E', 'A', 'B', 'EABC''state_vars', 'algebraic_vars']

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
        """
        Initializes the PolynomialMatrixBuilder.

        :param problem: The simulation problem instance (e.g., GenericMathematicalProblem).
        :type problem: Optional[Any]
        :param eqs: Optional polynomial equality constraints. Extracted from problem if None.
        :type eqs: Optional[list]
        :param ineqs: Optional polynomial inequality constraints.
        :type ineqs: Optional[list]
        :param state_vars: Optional list of state variable names. Extracted from problem if None.
        :type state_vars: Optional[list]
        :param algebraic_vars: Optional list of algebraic variable names. Extracted from problem if None.
        :type algebraic_vars: Optional[list]
        :param verbose: Print debugging information.
        :type verbose: bool
        :return: None
        :rtype: None
        """
        self.verbose: bool = verbose

        # Initialize explicit lists for internal storage
        self.eqs: list = list()
        self.ineqs: list = list()
        self.state_vars: list = list()
        self.algebraic_vars: list = list()

        # Step: Handle optional inputs and extract from problem if necessary.
        processed_eqs: list = list()
        processed_ineqs: list = list()
        processed_state_vars: list = list()
        processed_algebraic_vars: list = list()

        # Helper method inline to safely extract string representation from any Node/BinOp
        def _safe_to_string(item: Any) -> str:
            if hasattr(item, 'expr'):
                return str(getattr(item, 'expr'))
            elif hasattr(item, 'to_string'):
                return item.to_string()
            return str(item)

        has_problem: bool = problem is not None

        # --- 1. Equations processing ---
        if eqs is not None:
            processed_eqs = eqs
        else:
            if has_problem:
                if hasattr(problem, '_state_eqs'):
                    s_eq: Any
                    for s_eq in problem._state_eqs:
                        processed_eqs.append(_safe_to_string(s_eq))
                else:
                    pass

                if hasattr(problem, '_algebraic_eqs'):
                    a_eq: Any
                    for a_eq in problem._algebraic_eqs:
                        processed_eqs.append(_safe_to_string(a_eq))
                else:
                    pass
            else:
                pass

        # --- 2. Inequations processing ---
        if ineqs is not None:
            processed_ineqs = ineqs
        else:
            pass

        # --- 3. State variables processing ---
        if state_vars is not None:
            processed_state_vars = state_vars
        else:
            if has_problem:
                if hasattr(problem, '_state_vars'):
                    s_var: Any
                    for s_var in problem._state_vars:
                        processed_state_vars.append(_safe_to_string(s_var))
                else:
                    pass
            else:
                pass

        # --- 4. Algebraic variables processing ---
        if algebraic_vars is not None:
            processed_algebraic_vars = algebraic_vars
        else:
            if has_problem:
                if hasattr(problem, '_algebraic_vars'):
                    a_var: Any
                    for a_var in problem._algebraic_vars:
                        processed_algebraic_vars.append(_safe_to_string(a_var))
                else:
                    pass
            else:
                pass

        # Rule: Explicit state. Define global dictionary for the parser
        parsing_context: dict = dict()
        parsing_context['cos'] = sp.cos
        parsing_context['sin'] = sp.sin
        parsing_context['tan'] = sp.tan
        parsing_context['exp'] = sp.exp
        parsing_context['sqrt'] = sp.sqrt
        parsing_context['pi'] = sp.pi

        # EXPLICIT OVERRIDES: Prevent SymPy from shadowing electrical variables
        parsing_context['Id'] = sp.Symbol('Id')
        parsing_context['Iq'] = sp.Symbol('Iq')
        parsing_context['I'] = sp.Symbol('I')
        parsing_context['E'] = sp.Symbol('E')
        parsing_context['Q'] = sp.Symbol('Q')
        parsing_context['N'] = sp.Symbol('N')
        parsing_context['O'] = sp.Symbol('O')
        parsing_context['S'] = sp.Symbol('S')

        # Parse State Variables explicitly
        parsed_predefined: list = list()

        s_name: str
        for s_name in processed_state_vars:
            new_sym: sp.Symbol = sp.Symbol(s_name)
            parsing_context[s_name] = new_sym
            parsed_predefined.append(new_sym)
            self.state_vars.append(new_sym)

        # Parse Algebraic Variables explicitly
        a_name: str
        for a_name in processed_algebraic_vars:
            new_sym: sp.Symbol = sp.Symbol(a_name)
            parsing_context[a_name] = new_sym
            parsed_predefined.append(new_sym)
            self.algebraic_vars.append(new_sym)

        # Parse equations with explicit loops and type defense against BinOp
        raw_eq: Any
        for raw_eq in processed_eqs:
            eq_str: str
            if isinstance(raw_eq, str):
                eq_str = raw_eq
            else:
                eq_str = str(raw_eq)

            parsed_eq: sp.Expr = parse_expr(
                eq_str,
                local_dict=parsing_context,
                evaluate=True
            )
            self.eqs.append(parsed_eq)

        raw_ineq: Any
        for raw_ineq in processed_ineqs:
            ineq_str: str
            if isinstance(raw_ineq, str):
                ineq_str = raw_ineq
            else:
                ineq_str = str(raw_ineq)

            parsed_ineq: sp.Expr = parse_expr(
                ineq_str,
                local_dict=parsing_context,
                evaluate=True
            )
            self.ineqs.append(parsed_ineq)

        self.all_symbols: list = list()
        self.sym_to_idx: dict = dict()

        # We merge lists for symbol extraction explicitly
        combined_exprs: list = list()
        parsed_e: sp.Expr
        for parsed_e in self.eqs:
            combined_exprs.append(parsed_e)
        parsed_i: sp.Expr
        for parsed_i in self.ineqs:
            combined_exprs.append(parsed_i)

        # Pass the pre-parsed known symbols to the extractor
        self.extract_symbols(combined_exprs, predefined=parsed_predefined)

        # Build the symbol dictionary index explicitly
        idx: int = 0
        sym: sp.Symbol
        for sym in self.all_symbols:
            self.sym_to_idx[sym.name] = idx
            idx = idx + 1

        S_H_sp: sparse.csc_matrix
        Phi_H_sp: sparse.csr_matrix
        S_H_sp, Phi_H_sp = self.matrix_creation(self.eqs)

        S_W_sp: sparse.csc_matrix
        Phi_W_sp: sparse.csr_matrix
        S_W_sp, Phi_W_sp = self.matrix_creation(self.ineqs)

        # Store dense arrays
        self.S_H: np.ndarray = S_H_sp.toarray()
        self.Phi_H: np.ndarray = Phi_H_sp.toarray()
        self.S_W: np.ndarray = S_W_sp.toarray()
        self.Phi_W: np.ndarray = Phi_W_sp.toarray()

        # Protected interactive states
        self.E: Optional[np.ndarray] = None
        self.A: Optional[np.ndarray] = None
        self.B: Optional[np.ndarray] = None
        self.EABC: Optional[np.ndarray] = None


    # ------------------------------------------------------------------
    # Helper Functions (Replacing Lambdas and Nested Functions)
    # ------------------------------------------------------------------

    def _get_symbol_name(self, sym: sp.Symbol) -> str:
        """
        Returns the name of a sympy symbol to act as a sorting key.

        :param sym: SymPy Symbol object.
        :type sym: sp.Symbol
        :return: The string name of the symbol.
        :rtype: str
        """
        return sym.name

    def _sort_symbol(self, sym: sp.Symbol) -> tuple:
        """
        Provides the sorting key tuple for symbols based on TenSyGrid rules.

        :param sym: SymPy Symbol object.
        :type sym: sp.Symbol
        :return: A tuple containing the priority integer and the symbol name.
        :rtype: tuple
        """
        name: str = sym.name
        
        if name.startswith('dx'):
            return (0, name)
        elif name.startswith('xp'):
            return (0, name)
        elif name.startswith('x') and not name.startswith('xp'):
            return (1, name)
        elif name.startswith('u'):
            return (2, name)
        elif name.startswith('y'):
            return (3, name)
        elif name.startswith('z'):
            return (4, name)
        else:
            return (5, name)

    def _get_real_part(self, val: complex) -> float:
        """
        Returns the real part of a complex number to act as a sorting key.

        :param val: Complex number.
        :type val: complex
        :return: Real part of the complex number.
        :rtype: float
        """
        return float(val.real)

    def _arr2str(self, a: np.ndarray) -> str:
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

    def _section(self, title: str, content: str) -> str:
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
            eq_symbols.sort(key=self._get_symbol_name)

            for sym in eq_symbols:
                if sym not in seen:
                    seen.add(sym)
                    extracted_symbols.append(sym)
                else:
                    pass

        # Apply priority sorting strictly to all gathered symbols
        extracted_symbols.sort(key=self._sort_symbol)

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
            """
            if self.verbose:
                print(f"\nEquation {eq_idx + 1}: {eq}")
            else:
                pass
            """

            terms: list
            if eq.is_Add:
                terms = list(eq.args)
            else:
                terms = [eq]

            current_eq_coeffs: dict = dict()

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

            expanded_sub_terms: tuple = sp.Add.make_args(term.expand())
            
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

                        # MULTILINEARITY CHECK: Prevent TypeError on float() cast
                        if not b_val_sym.is_number:
                            deg = sp.degree(f, s)
                            if deg > 1:
                                raise ValueError(
                                    f"\n[TenSyGrid Error] Non-multilinear term detected: '{f}'.\n"
                                    f"Variable '{s.name}' has a degree higher than 1 ({deg}).\n"
                                    f"The iMTI representation requires strictly multilinear equations. "
                                    f"Please define an auxiliary algebraic variable to perform the 'lifting'."
                            )
                            elif deg < 1:
                                raise ValueError(
                                    f"\n[TenSyGrid Error] Non-multilinear term detected: '{f}'.\n"
                                    f"Variable '{s.name}' has a degree lower than 1 ({deg}).\n"
                                    f"The iMTI representation requires strictly multilinear equations. "
                                    f"Please define an auxiliary algebraic variable to perform the 'lifting'."
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

    # ------------------------------------------------------------------
    # Linearisation – public entry point
    # ------------------------------------------------------------------

    def linearize(self, v_dict: dict, c_type: ConstraintType = ConstraintType.EQUALITY):
        """
        Analytic linearization for iMTI models (CPN representation).

        :param v_dict: Variable name mapped to value at the operating point.
        :type v_dict: dict
        :param c_type: Enum indicating whether to use equality or inequality matrices.
        :type c_type: ConstraintType
        :return: Full EABC Jacobian matrix.
        :rtype: np.ndarray
        """
        S: np.ndarray
        Phi: np.ndarray
        S, Phi = self._get_matrices(c_type)

        v: np.ndarray = self._build_v_vector(v_dict)
        F: np.ndarray = self._compute_jacobian(S, v)
        self.EABC: np.ndarray = Phi @ F.T
        self.E, self.A, self.B = self._split_EABC(self.EABC)



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

    def _build_v_vector(self, v_dict: Optional[dict]) -> np.ndarray:
        """
        Build the operating-point vector from a dictionary.

        This function maps the provided values to their corresponding indices
        in the state and algebraic vector. It uses Duck Typing to handle keys
        that might be strings, SymPy symbols, or VeraGrid objects.

        :param v_dict: Operating point variables mapped to their numerical values.
        :type v_dict: Optional[dict]
        :return: Vector array of operating points initialized with the mapped values.
        :rtype: np.ndarray
        """
        # Step: Initialize the numpy array with zeros.
        # The size is explicitly known in advance via len(self.all_symbols)
        # complying with the performance rule of pre-allocating sizes.
        v: np.ndarray = np.zeros(len(self.all_symbols))

        # Step: Check if v_dict is not None to avoid runtime iteration errors.
        if v_dict is not None:

            # Step: Iterate directly. We process keys dynamically avoiding class checks.
            key: Any
            val: Any
            for key, val in v_dict.items():

                # Step: Ensure the value is not None to protect the numpy array.
                if val is not None:

                    # Step: Duck Typing for key extraction.
                    # We need a string to query self.sym_to_idx.
                    key_str: str
                    if isinstance(key, str):
                        key_str = key
                    elif hasattr(key, 'name'):
                        # Handles SymPy symbols or VeraGrid nodes with a 'name' attribute
                        key_str = str(getattr(key, 'name'))
                    else:
                        # Fallback to absolute string representation
                        key_str = str(key)

                    # Step: Lookup the index safely using the string name.
                    idx_opt: Optional[int] = self.sym_to_idx.get(key_str, None)

                    if idx_opt is not None:
                        # Force float casting to avoid numpy internal type conversion issues
                        v[idx_opt] = float(val)
                    else:
                        # Explicit else: key not found in our extracted symbols, skip gracefully.
                        pass
                else:
                    # Explicit else: The value is None, skip assignment.
                    pass

        else:
            # Explicit else: If v_dict is None, we do nothing and return the zeros array.
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

        :param EABC: Full Jacobian matrix.
        :type EABC: np.ndarray
        :return: Tuple containing E, A, and B matrices.
        :rtype: tuple
        """
        idx_dx: list = list()
        idx_vars: list = list()
        idx_u: list = list()

        # Explicit loops to categorize indices
        idx_counter: int = 0
        for s in self.all_symbols:
            s_name: str = s.name
            if s_name.startswith('dx') or s_name.startswith('xp'):
                idx_dx.append(idx_counter)
            elif s_name.startswith('x') or s_name.startswith('y') or s_name.startswith('z'):
                idx_vars.append(idx_counter)
            elif s_name.startswith('u'):
                idx_u.append(idx_counter)
            else:
                pass
            idx_counter = idx_counter + 1

        n_eqs: int = int(EABC.shape[0])
        
        E: np.ndarray = np.zeros((n_eqs, n_eqs))
        
        for i in range(len(idx_dx)):
            if i < n_eqs:
                col_idx_e: int = idx_dx[i]
                E[:, i] = -EABC[:, col_idx_e]
            else:
                pass

        A: np.ndarray = np.zeros((n_eqs, n_eqs))
        
        cols_to_take: int = len(idx_vars)
        if cols_to_take > n_eqs:
            cols_to_take = n_eqs
        else:
            pass
            
        A[:, :cols_to_take] = EABC[:, idx_vars[:cols_to_take]]

        B: np.ndarray = EABC[:, idx_u]

        return E, A, B

    # ------------------------------------------------------------------
    # Stability analysis
    # ------------------------------------------------------------------

    def compute_stability(self) -> tuple:
        """
        Compute generalised eigenvalues for the descriptor pair (A, E).

        :return: tuple of (eigenvalues, left_evecs, right_evecs, participation, is_stable, max_real)
        :rtype: tuple
        """
        current_a: np.ndarray | None = self.A
        current_e: np.ndarray | None = self.E

        if current_a is None or current_e is None:
            return None, None, None, None, False, None
        else:
            pass

        try:
            evals: np.ndarray
            evecs_left: np.ndarray
            evecs_right: np.ndarray
            evals, evecs_left, evecs_right = linalg.eig(current_a, current_e, left=True, right=True)
            
            finite_evs: np.ndarray = evals[np.isfinite(evals)]

            if len(finite_evs) == 0:
                return evals, evecs_left, evecs_right, None, True, -np.inf
            else:
                pass

            for i in range(len(evals)):
                scaling: complex = np.dot(evecs_left[:, i].conj(), evecs_right[:, i])
                evecs_left[:, i] = evecs_left[:, i] / scaling

            participation_matrix: np.ndarray = np.abs(evecs_right) * np.abs(evecs_left).T

            max_real: float = float(np.max(np.real(finite_evs)))
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
                sorted_evs: list = sorted(valid_evs, key=self._get_real_part, reverse=True)
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
                        formatted_mat: str = self._arr2str(mat_w)
                        section_str: str = self._section(label_w, formatted_mat)
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

                final_section: str = self._section("Stability Analysis", stability_txt)
                f.write(final_section)

            print(f"\nMatrices saved to: {save_path}")
        else:
            pass