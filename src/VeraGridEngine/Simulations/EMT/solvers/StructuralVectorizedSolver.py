# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Tuple, Callable, List, Any, Dict, Optional
import uuid
import time
import hashlib
from collections import defaultdict

import numpy as np
import numba as nb
from scipy.sparse import csc_matrix
from scipy.linalg import lu_factor, lu_solve
from scipy.sparse.linalg import splu

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const, BinOp, UnOp, Func
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler, MatrixVectorizedCompiler
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.basic_structures import Vec, Mat


# ==============================================================================
# Generic helpers
# ==============================================================================

def _safe_njit(py_func: Callable, *, fastmath: bool = True, cache: bool = True, signature=None):
    try:
        code_obj = getattr(py_func, "__code__", None)
        filename = code_obj.co_filename if code_obj else None
    except Exception:
        filename = None

    use_cache = bool(cache) and (filename is not None) and (filename != "<string>")

    if signature is not None:
        return nb.njit(signature, fastmath=fastmath, cache=use_cache)(py_func)
    return nb.njit(fastmath=fastmath, cache=use_cache)(py_func)


@nb.njit(cache=True, fastmath=True)
def _scatter_color_jvp_to_csc_data(
        jvp: np.ndarray, data: np.ndarray, color_ptr: np.ndarray,
        color_cols: np.ndarray, col_ptr: np.ndarray,
        row_idx: np.ndarray, data_idx: np.ndarray, color_id: int,
) -> None:
    k0 = color_ptr[color_id]
    k1 = color_ptr[color_id + 1]
    for k in range(k0, k1):
        p0 = col_ptr[k]
        p1 = col_ptr[k + 1]
        for p in range(p0, p1):
            data[data_idx[p]] = jvp[row_idx[p]]


# ==============================================================================
# Sparse AD Jacobian
# ==============================================================================

class SparseADJacobian:
    def __init__(
            self, equations: List[Any], variables: List[Any], parameters: List[Any],
            method_str: str, use_cse: bool = True, dtype=np.float64, verbose: bool = False,
    ):
        self.verbose = verbose
        self.equations = equations
        self.variables = variables
        self.parameters = parameters
        self.method_str = method_str
        self.dtype = dtype

        self.n_rows = len(equations)
        self.n_cols = len(variables)

        self.var_map = {v.uid: i for i, v in enumerate(variables)}

        # Sparsity detection
        col_rows: List[List[int]] = [[] for _ in range(self.n_cols)]
        for r, eq in enumerate(equations):
            stack = [eq]
            visited = set()
            uids = set()

            while stack:
                n = stack.pop()
                if id(n) in visited: continue
                visited.add(id(n))

                cname = n.__class__.__name__
                if cname == "Var" and hasattr(n, "uid"):
                    uids.add(n.uid)
                    if getattr(n, "base_var", None): uids.add(n.base_var.uid)
                    continue
                if cname in ("DiffVar", "LagVar"):
                    if getattr(n, "base_var", None): uids.add(n.base_var.uid)
                    continue

                for attr in ("left", "right", "arg", "operand"):
                    val = getattr(n, attr, None)
                    if val is not None: stack.append(val)
                if getattr(n, "args", None):
                    for ch in n.args: stack.append(ch)

            for uid in uids:
                j = self.var_map.get(uid, -1)
                if j >= 0: col_rows[j].append(r)

        self.col_rows = [sorted(set(rows)) for rows in col_rows]

        # CSC structure
        indptr = np.zeros(self.n_cols + 1, dtype=np.int32)
        nnz = 0
        for j in range(self.n_cols):
            nnz += len(self.col_rows[j])
            indptr[j + 1] = nnz

        indices = np.empty(nnz, dtype=np.int32)
        data = np.zeros(nnz, dtype=self.dtype)

        k = 0
        for j in range(self.n_cols):
            for r in self.col_rows[j]:
                indices[k] = r;
                k += 1

        self.J = csc_matrix((data, indices, indptr), shape=(self.n_rows, self.n_cols))

        # Coloring
        self.colors, self.n_colors = self._greedy_color_columns(self.col_rows, self.n_rows)
        groups: List[List[int]] = [[] for _ in range(self.n_colors)]
        for j in range(self.n_cols): groups[self.colors[j]].append(j)
        self.color_groups = groups

        # Scatter map
        color_cols: List[int] = []
        color_ptr = np.zeros(self.n_colors + 1, dtype=np.int32)
        for c in range(self.n_colors):
            color_ptr[c] = len(color_cols)
            color_cols.extend(self.color_groups[c])
        color_ptr[self.n_colors] = len(color_cols)

        col_ptr = np.zeros(len(color_cols) + 1, dtype=np.int32)
        total_map = 0
        for kk, j in enumerate(color_cols):
            total_map += len(self.col_rows[j])
            col_ptr[kk + 1] = total_map

        row_idx = np.empty(total_map, dtype=np.int32)
        data_idx = np.empty(total_map, dtype=np.int32)

        pos = 0
        indptr_arr = self.J.indptr
        for kk, j in enumerate(color_cols):
            base = indptr_arr[j]
            for local, r in enumerate(self.col_rows[j]):
                row_idx[pos] = r;
                data_idx[pos] = base + local;
                pos += 1

        self.color_ptr, self.color_cols = color_ptr, np.asarray(color_cols, dtype=np.int32)
        self.col_ptr, self.row_idx, self.data_idx = col_ptr, row_idx, data_idx

        # Compile kernels
        self._compiler = EquationCompiler(variables=variables, parameters=parameters, method=method_str)
        self.ad_kernels = []

        for c in range(self.n_colors):
            k_name = f"advec_step_color_{c}_{uuid.uuid4().hex[:4]}"
            py_ad = self._compiler.compile_ad_kernel(equations, func_name=k_name, use_cse=use_cse,
                                                     active_indices=set(self.color_groups[c]))
            self.ad_kernels.append(_safe_njit(py_ad, cache=False, fastmath=True))

        global_env = {"_scatter": _scatter_color_jvp_to_csc_data}
        for c in range(self.n_colors): global_env[f"kernel_{c}"] = self.ad_kernels[c]

        src = [
            "def master_jac(states, seeds, params, history, d_history, h, history2, data, color_ptr, color_cols, col_ptr, row_idx, data_idx):"]
        for c in range(self.n_colors):
            src.append(f"    jvp_{c} = kernel_{c}(states, seeds, params, history, d_history, h, history2)")
            src.append(f"    _scatter(jvp_{c}, data, color_ptr, color_cols, col_ptr, row_idx, data_idx, {c})")

        exec("\n".join(src), global_env)
        self.master_jac = _safe_njit(global_env["master_jac"], fastmath=True, cache=False)
        self._seeds = np.zeros(self.n_cols, dtype=self.dtype)

    @staticmethod
    def _greedy_color_columns(col_rows: List[List[int]], n_rows: int) -> Tuple[np.ndarray, int]:
        n_cols = len(col_rows)
        row_cols: List[List[int]] = [[] for _ in range(n_rows)]
        for j in range(n_cols):
            for r in col_rows[j]: row_cols[r].append(j)

        adj = [set() for _ in range(n_cols)]
        for cols in row_cols:
            m = len(cols)
            for a in range(m):
                for b in range(a + 1, m):
                    if cols[b] != cols[a]:
                        adj[cols[a]].add(cols[b]);
                        adj[cols[b]].add(cols[a])

        degrees = np.array([len(adj[j]) for j in range(n_cols)], dtype=np.int32)
        order = list(np.argsort(-degrees))
        colors = -np.ones(n_cols, dtype=np.int32)
        max_color = -1
        used = np.zeros(n_cols, dtype=np.bool_)

        for j in order:
            used[:] = False
            for nbj in adj[j]:
                if colors[nbj] >= 0: used[colors[nbj]] = True
            c = 0
            while c < n_cols and used[c]: c += 1
            colors[j] = c
            if c > max_color: max_color = c
        return colors, int(max_color + 1)

    def __call__(self, states, params, history, d_history, h, history2=None) -> csc_matrix:
        self.master_jac(states, self._seeds, params, history, d_history, h, history2, self.J.data, self.color_ptr,
                        self.color_cols, self.col_ptr, self.row_idx, self.data_idx)
        return self.J


# ==============================================================================
# StructuralVectorizedSolver
# ==============================================================================

class StructuralVectorizedSolver:
    def __init__(
            self,
            problem: EmtProblemTemplate,
            t0: float,
            t_end: float,
            h: float,
            integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.Trapezoid,
            dense_threshold: int = 100,
            verbose: bool = False,
            auto_vectorization: bool = True,
    ):
        self.problem = problem
        self.t0 = t0
        self.t_end = t_end
        self.h = h
        self.method_str = integration_method
        self.dense_threshold = dense_threshold
        self.verbose = verbose

        self._state_vars = self.problem.get_state_vars()
        self._algebraic_vars = self.problem.get_algebraic_vars()
        self._state_eqs = self.problem.get_state_eqs()
        self._algebraic_eqs = self.problem.get_algebraic_eqs()

        self.sorted_vars = self._state_vars + self._algebraic_vars
        self._n_state = len(self._state_vars)
        self._n_vars = len(self.sorted_vars)

        self.uid2idx_vars = {v.uid: i for i, v in enumerate(self.sorted_vars)}

        self._event_parameters = self.problem.get_variable_parameters()
        self._parameters = self.problem.get_constant_parameters()
        self._parameters_values = self.problem.get_parameters_values()
        self._event_params_fn = self.problem.def_event_params_fn

        self.jit_jacobians_ad: Dict[str, SparseADJacobian] = {}
        self.vectorized_ready = False

        if auto_vectorization:
            self._auto_detect_vectorization(integration_method)

    def _canonicalize_expression(self, expr: Expr) -> Tuple[str, List[Var]]:
        unique_slots = {}
        found_vars_ordered = []
        seen_nodes = set()

        def _visit_recursive(node):
            if isinstance(node, Var):
                target_uid = node.base_var.uid if getattr(node, "base_var", None) else node.uid
                if target_uid not in unique_slots:
                    unique_slots[target_uid] = f"__VAR_{len(unique_slots)}__"

                if id(node) not in seen_nodes:
                    seen_nodes.add(id(node))
                    found_vars_ordered.append(node)
                return unique_slots[target_uid]

            elif isinstance(node, Const):
                return f"{float(node.value):.6g}"
            elif isinstance(node, BinOp):
                return f"({_visit_recursive(node.left)}{node.op}{_visit_recursive(node.right)})"
            elif isinstance(node, UnOp):
                return f"{node.op}({_visit_recursive(node.operand)})"
            elif isinstance(node, Func):
                return f"{node.op}({_visit_recursive(node.arg)})"
            return str(node)

        canonical_str = _visit_recursive(expr)
        return canonical_str, found_vars_ordered

    def _auto_detect_vectorization(self, method_str: DynamicIntegrationMethod = None):
        """
        Infers the algebraic structure of the DAE system (Clustering) and compiles
        the vectorized matrix kernels.
        """
        if method_str is None:
            method_str = self.method_str

        print(f"--- [AUTO-VEC] Inferring Algebraic Structure (Clustering) ---")
        t0 = time.time()

        groups = defaultdict(lambda: {
            'idx_matrix': [],
            'row_indices': [],
            'template_eq': None,
            'template_vars': None
        })

        full_eq_list = []
        for i, rhs_eq in enumerate(self._state_eqs):
            sv = self._state_vars[i]
            d_term = Var(name=f"d_{sv.name}", base_var=sv)
            full_eq_list.append(d_term - rhs_eq)
        full_eq_list.extend(self._algebraic_eqs)

        # PHASE 2: CLUSTERING
        for i, residual_eq in enumerate(full_eq_list):
            sig_str, all_vars_found = self._canonicalize_expression(residual_eq)
            eq_hash = hashlib.md5(sig_str.encode()).hexdigest()

            group = groups[eq_hash]
            if group['template_eq'] is None:
                group['template_eq'] = residual_eq
                group['template_vars'] = all_vars_found

            var_indices = []
            for v in all_vars_found:
                target_var = getattr(v, "base_var", None) or v
                # Usar .get() para evitar KeyErrors con parámetros constantes
                var_indices.append(self.uid2idx_vars.get(target_var.uid, -1))

            group['idx_matrix'].append(var_indices)
            group['row_indices'].append(i)

        print(f"   [AUTO-VEC] Detected {len(groups)} patterns in {len(full_eq_list)} total equations.")

        self.vec_kernels = []
        all_params = self._event_parameters + self._parameters

        vec_compiler = MatrixVectorizedCompiler(self.sorted_vars, all_params, method=method_str)

        for signature, data in groups.items():
            k_name = f"vec_kernel_{signature[:8]}"
            py_func = vec_compiler.compile_matrix_kernel(
                data['template_eq'],
                func_name=k_name,
                template_vars=data['template_vars']
            )

            self.vec_kernels.append({
                'func': nb.njit(cache=True, fastmath=True)(py_func),
                'indices': np.array(data['idx_matrix'], dtype=np.int32),
                'target': np.array(data['row_indices'], dtype=np.int32)
            })

        # PHASE 4: DISPATCHER SETUP
        self.fused_residual = self._compile_fused_residual(self.vec_kernels)
        self.vec_flat_args = []
        for k in self.vec_kernels:
            self.vec_flat_args.extend([k['target'], k['indices']])
        self.vec_flat_args = tuple(self.vec_flat_args)

        # PHASE 5: JACOBIAN SETUP
        if method_str not in self.jit_jacobians_ad:
            self.jit_jacobians_ad[method_str] = SparseADJacobian(
                full_eq_list, self.sorted_vars, all_params, method_str, verbose=self.verbose
            )

        self.vec_jacobian = self.jit_jacobians_ad[method_str]
        self.vectorized_ready = True
        print(f"   [AUTO-VEC] Setup finished in {time.time() - t0:.4f}s")

    def _compile_fused_residual(self, kernels_data):
        namespace = {'np': np, 'nb': nb}
        lines = ["def fused_residual_kernel(states, params, history, d_history, h, args, out, history2=None):",
                 "    out[:] = 0.0"]
        for i, k_data in enumerate(kernels_data):
            func_key = f"func_{i}"
            namespace[func_key] = k_data['func']
            lines.extend([f"    target_{i} = args[{2 * i}]", f"    indices_{i} = args[{2 * i + 1}]",
                          f"    r_part_{i} = {func_key}(states, params, history, d_history, h, indices_{i}, history2)",
                          f"    out[target_{i}] = r_part_{i}"])
        exec("\n".join(lines), namespace)
        return nb.njit(fastmath=True, cache=False)(namespace['fused_residual_kernel'])

    def simulate(self, x0=None, dx0=None, params0=None, boundary_update_fn=None) -> Tuple[Vec, Mat]:
        if x0 is None: x0 = self.problem.get_x0()
        if dx0 is None: dx0 = np.zeros(self._n_vars, dtype=np.float64)
        if params0 is None: params0 = np.zeros(len(self._event_parameters), dtype=np.float64)
        return self._simulate_vectorized(self.t0, self.t_end, self.h, x0, dx0, params0, self.method_str,
                                         boundary_update_fn, self.verbose, self.dense_threshold)

    def _simulate_vectorized(self,
                             t0,
                             t_end,
                             h,
                             x0,
                             dx0,
                             params0,
                             method_str,
                             boundary_update_fn,
                             verbose,
                             dense_threshold):
        if not self.vectorized_ready:
            self._auto_detect_vectorization(method_str)

        steps = int(np.ceil((t_end - t0) / h))
        t = np.linspace(t0, t_end, steps + 1)
        y = np.zeros((steps + 1, self._n_vars), dtype=np.float64)
        y[0] = x0.copy()

        x_prev, dx_prev, x_prev2, x_iter = x0.copy(), dx0.copy(), x0.copy(), x0.copy()
        res_global = np.zeros(self._n_vars, dtype=np.float64)

        static_params = np.array([c.value for c in self._parameters_values], dtype=np.float64)
        ev_params = np.asarray(params0, dtype=np.float64)

        full_params = np.empty(len(self._event_parameters) + len(static_params), dtype=np.float64)
        full_params[len(ev_params):] = static_params

        use_dense = (self._n_vars <= 200)

        if verbose: print(f"-> JIT Warmup...")
        self.fused_residual(x_prev, full_params, x_prev, dx_prev, h, self.vec_flat_args, res_global, x_prev2)
        _ = self.vec_jacobian(states=x_prev, params=full_params, history=x_prev, d_history=dx_prev, h=h,
                              history2=x_prev2)

        cached_J, cached_lu = None, None
        t_start_loop = time.time()  # Timer local para debug

        if verbose: print(f"-> Starting VECTORIZED Simulation (Bucle de integración)...")

        for i in range(steps):
            if verbose: print(f"Simulating at step {i}")
            t_curr = t[i + 1]

            # Update params in-place
            full_params[:len(ev_params)] = self._event_params_fn(ev_params, float(t_curr))

            if boundary_update_fn:
                boundary_update_fn(t_curr, x_prev, full_params)

            x_iter[:] = x_prev
            last_res_norm = 1.0

            for k in range(15):
                self.fused_residual(x_iter, full_params, x_prev, dx_prev, h, self.vec_flat_args, res_global, x_prev2)
                res_norm = np.max(np.abs(res_global))

                if res_norm < 1e-6: break

                recompute = (cached_lu is None) or (k > 0 and (res_norm / (last_res_norm + 1e-16)) > 0.5)

                if recompute:
                    cached_J = self.vec_jacobian(x_iter, full_params, x_prev, dx_prev, h, x_prev2)
                    cached_lu = lu_factor(cached_J.toarray()) if use_dense else splu(cached_J.tocsc())

                delta = lu_solve(cached_lu, -res_global) if use_dense else cached_lu.solve(-res_global)
                x_iter += delta
                last_res_norm = res_norm

            y[i + 1] = x_iter

            if method_str == DynamicIntegrationMethod.Trapezoid:
                dx_prev[:self._n_state] = (2.0 / h) * (x_iter[:self._n_state] - x_prev[:self._n_state]) - dx_prev[
                    :self._n_state]
            elif method_str == DynamicIntegrationMethod.BDF2:
                x_prev2[:] = x_prev
                dx_prev[:self._n_state] = (1.5 * x_iter[:self._n_state] - 2.0 * x_prev[:self._n_state] + 0.5 * x_prev2[
                    :self._n_state]) / h
            else:
                dx_prev[:self._n_state] = (x_iter[:self._n_state] - x_prev[:self._n_state]) / h

            if method_str != DynamicIntegrationMethod.BDF2: x_prev2[:] = x_prev
            x_prev[:] = x_iter

        self._last_sim_loop_time = time.time() - t_start_loop
        if verbose: print(f"VECTORIZED INTEGRATION LOOP Finished: {self._last_sim_loop_time:.4f}s")

        return t, y