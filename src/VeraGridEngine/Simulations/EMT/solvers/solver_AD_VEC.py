# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Tuple, Callable, List, Any, Dict, Optional
import uuid
import time

import numpy as np
import numba as nb
import scipy.sparse as sp
from scipy.sparse import csc_matrix

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Utils.Symbolic.symbolic import DiffVar
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler
from VeraGridEngine.Utils.Symbolic.diagnostic import (
    with_newton_diagnostics,
    NewtonDiagnosticsConfig,
    NewtonSolveContext,
    dense_lstsq_fallback,
    sparse_lsqr_fallback,
)
from VeraGridEngine.basic_structures import Vec, Mat

# ==============================================================================
# Generic helpers
# ==============================================================================

def _safe_njit(py_func: Callable, *, fastmath: bool = True, cache: bool = True, signature=None):
    """
    Numba cannot cache functions whose source filename is '<string>' (exec/generated code).
    We transparently disable caching in that case to avoid RuntimeError.
    """
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
    jvp: np.ndarray,
    data: np.ndarray,
    color_ptr: np.ndarray,
    color_cols: np.ndarray,  # kept for signature compatibility / layout coherence
    col_ptr: np.ndarray,
    row_idx: np.ndarray,
    data_idx: np.ndarray,
    color_id: int,
) -> None:
    """
    Scatter a single JVP evaluation into CSC data for one color group.
    """
    k0 = color_ptr[color_id]
    k1 = color_ptr[color_id + 1]
    for k in range(k0, k1):
        p0 = col_ptr[k]
        p1 = col_ptr[k + 1]
        for p in range(p0, p1):
            data[data_idx[p]] = jvp[row_idx[p]]


# ==============================================================================
# Sparse AD Jacobian (same functional behavior as AD backend)
# ==============================================================================

class SparseADJacobian:
    """
    Sparse Jacobian evaluator with graph-coloring + JVP scatter.
    This is self-contained (does NOT depend on external AD solver class).
    """

    def __init__(
        self,
        equations: List[Any],
        variables: List[Any],
        parameters: List[Any],
        method_str: str,
        use_cse: bool = True,
        dtype=np.float64,
        verbose: bool = False,
    ):
        t_start = time.perf_counter()
        self.verbose = verbose
        if self.verbose:
            print(f"   [ADVEC-Jac] Init started for {len(equations)} eqs...")

        self.equations = equations
        self.variables = variables
        self.parameters = parameters
        self.method_str = method_str
        self.use_cse = use_cse
        self.dtype = dtype

        self.n_rows = len(equations)
        self.n_cols = len(variables)

        self.var_map = {v.uid: i for i, v in enumerate(variables)}
        self.param_map = {p.uid: i for i, p in enumerate(parameters)}

        t_maps = time.perf_counter()
        if self.verbose:
            print(f"   [ADVEC-Jac] Maps built in {t_maps - t_start:.4f}s")

        # 1) Sparsity detection
        col_rows: List[List[int]] = [[] for _ in range(self.n_cols)]
        count_edges = 0

        for r, eq in enumerate(equations):
            stack = [eq]
            visited = set()
            uids = set()

            while stack:
                n = stack.pop()
                nid = id(n)
                if nid in visited:
                    continue
                visited.add(nid)

                cname = n.__class__.__name__

                if cname == "Var" and hasattr(n, "uid"):
                    uids.add(n.uid)
                    continue

                if cname == "DiffVar":
                    bv = getattr(n, "base_var", None)
                    if bv is not None:
                        uids.add(bv.uid)
                    continue

                if cname == "LagVar":
                    bv = getattr(n, "base_var", None)
                    if bv is not None:
                        uids.add(bv.uid)
                    continue

                l = getattr(n, "left", None)
                if l is not None:
                    stack.append(l)
                rr = getattr(n, "right", None)
                if rr is not None:
                    stack.append(rr)
                a = getattr(n, "arg", None)
                if a is not None:
                    stack.append(a)
                o = getattr(n, "operand", None)
                if o is not None:
                    stack.append(o)

                args = getattr(n, "args", None)
                if args is not None:
                    for ch in args:
                        stack.append(ch)

            for uid in uids:
                j = self.var_map.get(uid, -1)
                if j >= 0:
                    col_rows[j].append(r)
                    count_edges += 1

        self.col_rows = [sorted(set(rows)) for rows in col_rows]

        t_sparsity = time.perf_counter()
        if self.verbose:
            print(f"   [ADVEC-Jac] Sparsity in {t_sparsity - t_maps:.4f}s. Edges={count_edges}")

        # 2) CSC structure
        indptr = np.zeros(self.n_cols + 1, dtype=np.int32)
        nnz = 0
        for j in range(self.n_cols):
            nnz += len(self.col_rows[j])
            indptr[j + 1] = nnz

        indices = np.empty(nnz, dtype=np.int32)
        data = np.zeros(nnz, dtype=self.dtype)

        k = 0
        for j in range(self.n_cols):
            rows = self.col_rows[j]
            for r in rows:
                indices[k] = r
                k += 1

        self.J = csc_matrix((data, indices, indptr), shape=(self.n_rows, self.n_cols))

        t_csc = time.perf_counter()
        if self.verbose:
            print(f"   [ADVEC-Jac] CSC built in {t_csc - t_sparsity:.4f}s")

        # 3) Coloring
        self.colors, self.n_colors = self._greedy_color_columns(self.col_rows, self.n_rows)

        groups: List[List[int]] = [[] for _ in range(self.n_colors)]
        for j in range(self.n_cols):
            groups[self.colors[j]].append(j)
        self.color_groups = groups

        t_color = time.perf_counter()
        if self.verbose:
            print(f"   [ADVEC-Jac] Coloring in {t_color - t_csc:.4f}s. Colors={self.n_colors}")

        # 4) Precompute scatter map
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
            rows = self.col_rows[j]
            for local, r in enumerate(rows):
                row_idx[pos] = r
                data_idx[pos] = base + local
                pos += 1

        self.color_ptr = color_ptr
        self.color_cols = np.asarray(color_cols, dtype=np.int32)
        self.col_ptr = col_ptr
        self.row_idx = row_idx
        self.data_idx = data_idx

        t_scatter = time.perf_counter()
        if self.verbose:
            print(f"   [ADVEC-Jac] Scatter map in {t_scatter - t_color:.4f}s")

        # 5) Compile specialized kernels by color
        self._compiler = EquationCompiler(variables=variables, parameters=parameters, method=method_str)
        self.ad_kernels = []

        if self.verbose:
            print(f"   [ADVEC-Jac] Compiling {self.n_colors} color kernels...")

        t_comp_start = time.perf_counter()
        for c in range(self.n_colors):
            active_cols = set(self.color_groups[c])
            k_name = f"advec_step_color_{c}_{uuid.uuid4().hex[:4]}"

            py_ad = self._compiler.compile_ad_kernel(
                equations,
                func_name=k_name,
                use_cse=use_cse,
                active_indices=active_cols,
            )
            ker = _safe_njit(py_ad, cache=False, fastmath=True)
            self.ad_kernels.append(ker)

        t_comp_end = time.perf_counter()
        if self.verbose:
            print(f"   [ADVEC-Jac] Kernels compiled in {t_comp_end - t_comp_start:.4f}s")
            print(f"   [ADVEC-Jac] Total init {t_comp_end - t_start:.4f}s")

        # Seeds vector (kept for API compatibility)
        self._seeds = np.zeros(self.n_cols, dtype=self.dtype)

    @staticmethod
    def _greedy_color_columns(col_rows: List[List[int]], n_rows: int) -> Tuple[np.ndarray, int]:
        n_cols = len(col_rows)
        row_cols: List[List[int]] = [[] for _ in range(n_rows)]

        for j in range(n_cols):
            for r in col_rows[j]:
                row_cols[r].append(j)

        adj = [set() for _ in range(n_cols)]
        for cols in row_cols:
            m = len(cols)
            for a in range(m):
                ja = cols[a]
                for b in range(a + 1, m):
                    jb = cols[b]
                    if jb != ja:
                        adj[ja].add(jb)
                        adj[jb].add(ja)

        degrees = np.array([len(adj[j]) for j in range(n_cols)], dtype=np.int32)
        order = list(np.argsort(-degrees))

        colors = -np.ones(n_cols, dtype=np.int32)
        max_color = -1
        used = np.zeros(n_cols, dtype=np.bool_)

        for j in order:
            used[:] = False
            for nbj in adj[j]:
                c = colors[nbj]
                if c >= 0:
                    used[c] = True

            c = 0
            while c < n_cols and used[c]:
                c += 1
            colors[j] = c
            if c > max_color:
                max_color = c

        return colors, int(max_color + 1)

    def __call__(
        self,
        states: np.ndarray,
        params: np.ndarray,
        history: np.ndarray,
        d_history: np.ndarray,
        h: float,
        history2: Optional[np.ndarray] = None,
    ) -> csc_matrix:
        data = self.J.data
        seeds = self._seeds

        for c in range(self.n_colors):
            kernel = self.ad_kernels[c]
            jvp = kernel(states, seeds, params, history, d_history, h, history2)

            _scatter_color_jvp_to_csc_data(
                jvp,
                data,
                self.color_ptr,
                self.color_cols,
                self.col_ptr,
                self.row_idx,
                self.data_idx,
                c,
            )
        return self.J

# ==============================================================================
# AD_VEC Solver (self-contained, no dependency on AD solver class)
# ==============================================================================

class AdVecSolver:
    """
    Self-contained AD_VEC solver extracted from block_solver behavior.
    """

    def __init__(
        self,
        problem: EmtProblemTemplate,
        t0: float,
        t_end: float,
        h: float,
        method_str: str = "trapezoidal",
        dense_threshold: int = 100,
        verbose: bool = False,
        auto_vectorization: bool = True,
    ):
        self.problem = problem
        self.t0 = t0
        self.t_end = t_end
        self.h = h
        self.method_str = method_str
        self.dense_threshold = dense_threshold
        self.verbose = verbose
        self.auto_vectorization = auto_vectorization

        self.steps = int(np.ceil((t_end - t0) / h))
        self.t: Vec = np.empty(self.steps + 1)
        self.y: Mat = np.empty((self.steps + 1, self.problem.get_all_vars_number()))

        # Keep both "public-like" and "_" aliases to match legacy internal usage
        self.state_vars = self.problem.get_state_vars()
        self.algebraic_vars = self.problem.get_algebraic_vars()
        self.state_eqs = self.problem.get_state_eqs()
        self.algebraic_eqs = self.problem.get_algebraic_eqs()

        self.sorted_vars = self.state_vars + self.algebraic_vars
        self._state_vars = self.state_vars
        self._algebraic_vars = self.algebraic_vars
        self._state_eqs = self.state_eqs
        self._algebraic_eqs = self.algebraic_eqs

        self._n_state = len(self.state_vars)
        self._n_algebraic = len(self.algebraic_vars)
        self._n_vars = len(self.sorted_vars)

        self._event_parameters = self.problem.get_variable_parameters()
        self._parameters = self.problem.get_constant_parameters()
        self._parameters_values = self.problem.get_parameters_values()
        self._event_params_fn = self.problem.def_event_params_fn

        # Own caches (NO dependency on AD solver)
        self.jit_kernels_ad_vec: Dict[str, List[Callable]] = {}
        self.jit_jacobians_ad_vec: Dict[str, SparseADJacobian] = {}

        # Vectorized execution flags / state
        self.vectorized_ready = False
        self.vec_method = method_str
        self.vec_jacobian: Optional[SparseADJacobian] = None
        self.vec_residual_kernels: Optional[List[Callable]] = None

        if self.auto_vectorization:
            self._auto_detect_vectorization()

    # --------------------------------------------------------------------------
    # Build pipeline
    # --------------------------------------------------------------------------

    def _build_equations(self) -> List[Any]:
        equations: List[Any] = []
        for i, rhs in enumerate(self._state_eqs):
            sv = self._state_vars[i]
            d_term = DiffVar(name=f"d_{sv.name}", base_var=sv)
            equations.append(d_term - rhs)
        equations.extend(self._algebraic_eqs)
        return equations

    def _build_jit_ad_vec(self, method_str: str, only_jacobian: bool = False):
        """
        Self-contained build: compiles residual kernels + sparse AD Jacobian for AD_VEC backend.
        """
        if (method_str in self.jit_kernels_ad_vec) and (method_str in self.jit_jacobians_ad_vec) and (not only_jacobian):
            return

        if self.verbose:
            mode = "Jacobian ONLY" if only_jacobian else "Residual + Jacobian"
            print(f"--- [AD_VEC] Building {mode} ({method_str}) ---")

        sorted_vars = self._state_vars + self._algebraic_vars
        all_params = self._event_parameters + self._parameters
        equations = self._build_equations()

        # Jacobian (always required)
        if method_str not in self.jit_jacobians_ad_vec:
            jac = SparseADJacobian(
                equations=equations,
                variables=sorted_vars,
                parameters=all_params,
                method_str=method_str,
                use_cse=True,
                verbose=self.verbose,
            )
            self.jit_jacobians_ad_vec[method_str] = jac

        # Residual (optional in jac-only mode, but needed for simulate path)
        if (not only_jacobian) and (method_str not in self.jit_kernels_ad_vec):
            compiler = EquationCompiler(variables=sorted_vars, parameters=all_params, method=method_str)
            BATCH_SIZE = 100
            n_eqs = len(equations)
            batched_kernels: List[Callable] = []

            if self.verbose:
                print(f"   [AD_VEC] Splitting {n_eqs} residual eqs into {int(np.ceil(n_eqs / BATCH_SIZE))} batches...")
            t0 = time.time()

            for i in range(0, n_eqs, BATCH_SIZE):
                chunk = equations[i:i + BATCH_SIZE]
                fname = f"jit_step_{method_str}_advec_part_{i}"
                py_func = compiler.compile(chunk, func_name=fname, use_cse=True, offset=i, inplace=True)
                jit_func = _safe_njit(py_func, cache=True, fastmath=True)
                batched_kernels.append(jit_func)

            self.jit_kernels_ad_vec[method_str] = batched_kernels
            if self.verbose:
                print(f"   [AD_VEC] Residual batches compiled in {time.time() - t0:.4f}s")

    def _auto_detect_vectorization(self):
        """
        Prepare vectorized runtime resources.
        NOTE: This does NOT depend on AD solver anymore.
        """
        method_str = self.vec_method

        # Build local jacobian (and residual kernels if not present)
        if method_str not in self.jit_jacobians_ad_vec:
            self._build_jit_ad_vec(method_str=method_str, only_jacobian=False)

        self.vec_jacobian = self.jit_jacobians_ad_vec[method_str]
        self.vec_residual_kernels = self.jit_kernels_ad_vec.get(method_str, None)
        self.vectorized_ready = True

        if self.verbose:
            print(f"[AD_VEC] Vectorized path ready for method='{method_str}'")

    # --------------------------------------------------------------------------
    # Simulation
    # --------------------------------------------------------------------------

    def simulate(self, x0=None, dx0=None, params0=None, boundary_update_fn=None) -> Tuple[Vec, Mat]:
        """
        Main simulation entrypoint.
        """
        if not self.vectorized_ready:
            self._auto_detect_vectorization()
        return self._simulate_vectorized(x0=x0, dx0=dx0, params0=params0, boundary_update_fn=boundary_update_fn)

    def _simulate_vectorized(self, x0=None, dx0=None, params0=None, boundary_update_fn=None) -> Tuple[Vec, Mat]:
        t_start = time.time()
        method_str = self.vec_method

        if method_str not in self.jit_kernels_ad_vec or method_str not in self.jit_jacobians_ad_vec:
            self._build_jit_ad_vec(method_str=method_str, only_jacobian=False)

        kernel_list = self.jit_kernels_ad_vec[method_str]
        current_jacobian = self.jit_jacobians_ad_vec[method_str]

        n_eqs = self.problem.get_all_vars_number()
        n_states = self.problem.get_states_number()

        use_dense_solver = (n_eqs <= self.dense_threshold)

        t = np.linspace(self.t0, self.t_end, self.steps + 1, dtype=np.float64)
        self.t = t

        if x0 is None:
            x0 = self.problem.get_x0()

        self.y[0, :] = x0.copy()

        x_prev = x0.copy()
        dx_prev = dx0.copy() if dx0 is not None else np.zeros(n_eqs, dtype=np.float64)
        x_prev2 = x0.copy()
        x_iter = x0.copy()

        static_vals = np.array([c.value for c in self._parameters_values], dtype=np.float64)
        n_event_params = len(self._event_parameters)
        ev_params = params0.copy() if params0 is not None else np.zeros(n_event_params, dtype=np.float64)

        trace_collector = self.problem.get_newton_trace_collector()

        diag_cfg = NewtonDiagnosticsConfig(
            step_norm_explode=1e6,
            dense_cond_warn=1e12,
            compute_dense_cond=True,
            enable_fallback=True,
        )
        dense_solve = with_newton_diagnostics(
            np.linalg.solve,
            fallback_solve=dense_lstsq_fallback,
            collector=trace_collector,
            config=diag_cfg,
            solver_name="dense",
        )
        sparse_solve = with_newton_diagnostics(
            sp.linalg.spsolve,
            fallback_solve=sparse_lsqr_fallback,
            collector=trace_collector,
            config=diag_cfg,
            solver_name="sparse",
        )

        if self.verbose:
            print(f"-> Starting AD_VEC simulation ({method_str}, {self.steps} steps)...")

        for i in range(self.steps):
            t_curr = t[i + 1]

            # Update event params through problem callback
            ev_params = self._event_params_fn(ev_params, float(t_curr))
            full_params = np.concatenate((ev_params, static_vals))

            if boundary_update_fn is not None:
                boundary_update_fn(t_curr, x_prev, full_params)

            x_iter[:] = x_prev

            for k in range(15):
                ctx = NewtonSolveContext(
                    t=float(t_curr),
                    step_idx=int(i),
                    newton_iter=int(k),
                    phase="ad_vec",
                    method=str(method_str),
                )

                # Residual evaluation (batched)
                res = np.zeros(n_eqs, dtype=np.float64)
                for kn in kernel_list:
                    kn(x_iter, full_params, x_prev, dx_prev, self.h, res, x_prev2)

                if np.linalg.norm(res, np.inf) < 1e-5:
                    break

                # Jacobian evaluation
                J = current_jacobian(
                    states=x_iter,
                    params=full_params,
                    history=x_prev,
                    d_history=dx_prev,
                    h=self.h,
                    history2=x_prev2,
                )

                # Linear solve
                if use_dense_solver:
                    delta = dense_solve(J.toarray(), -res, ctx)
                else:
                    delta = sparse_solve(J, -res, ctx)

                x_iter += delta

            self.y[i + 1, :] = x_iter

            # Integration-history update
            if method_str == "trapezoidal":
                dx_prev[:n_states] = (2.0 / self.h) * (x_iter[:n_states] - x_prev[:n_states]) - dx_prev[:n_states]
            elif method_str == "bdf2":
                x_prev2 = x_prev.copy()
            else:  # back_euler
                dx_prev[:n_states] = (x_iter[:n_states] - x_prev[:n_states]) / self.h

            if method_str != "bdf2":
                x_prev2 = x_prev.copy()

            x_prev = x_iter.copy()

        if self.verbose:
            print(f"AD_VEC Finished: {time.time() - t_start:.4f}s")

        return self.t, self.y
