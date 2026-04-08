import sympy as sp
import numpy as np
from scipy import sparse, linalg
from enum import Enum
from typing import Optional, Any, List, Tuple
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

'''def _get_symbol_name(sym: sp.Symbol) -> str:
    return sym.name'''


def _sort_symbol(sym: sp.Symbol) -> tuple:
    """
    Pre: A symbol.
    Post: Returns if it's a derivative
    """
    name: str = sym.name
    if name.startswith('dx') or name.startswith('xp') or name.startswith('d_') or name.startswith('dt_'):
        return 0, name
    else:
        return 1, name


def _get_real_part(val: complex) -> float:
    return float(val.real)


'''
def _section(title: str, content: str) -> str:
    bar: str = "=" * (len(title) + 4)
    return f"{bar}\n  {title}\n{bar}\n{content}\n"
'''


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
            c = str(n)
            c = c.replace('dt_1_', 'dt_').replace('d_1_', 'dt_')
            c = re.sub(r'\bd_', 'dt_', c)
            return c

        def _extract_mappings(var_list: list) -> None:
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
                F[zero_row, col] = S[zero_row, col] * np.prod(other_factors)

        return F

    def _split_EABC(self, EABC: np.ndarray) -> tuple:
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

    def report(self, eigenvalues=None, is_stable=False, max_real=None, print_matrices=True, save_path=None):
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