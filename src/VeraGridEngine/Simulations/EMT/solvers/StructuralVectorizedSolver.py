# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Tuple, Callable, List, Any, Dict, Union, Set
import time
import hashlib

import numpy as np
import numba as nb
from scipy.sparse import csc_matrix
from scipy.linalg import lu_factor, lu_solve
from scipy.sparse.linalg import splu, SuperLU

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const, BinOp, UnOp, Func
from VeraGridEngine.Utils.Symbolic.diagnostic import (
    NewtonDiagnosticsConfig,
    NewtonSolveContext,
    dense_lstsq_fallback,
    maybe_apply_backtracking,
    maybe_check_index1,
    sparse_lsqr_fallback,
    with_newton_diagnostics,
)
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler, MatrixVectorizedCompiler, _compile_to_file
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.basic_structures import Vec, Mat


DenseFactorization = Tuple[Any, Any]
DenseSolveBundle = Tuple[DenseFactorization, np.ndarray]
SparseSolveBundle = Tuple[SuperLU, csc_matrix]


# ==============================================================================
# Generic helpers
# ==============================================================================

def _safe_njit(py_func: Callable[..., Any], fastmath: bool = True, cache: bool = True, signature: Any = None) -> \
Callable[..., Any]:
    """
    Safely wraps a python function with Numba's njit compiler.
    The caller must explicitly pass cache=False if the function is generated via strings.

    :param py_func: The python function to compile.
    :type py_func: Callable[..., Any]
    :param fastmath: Flag to enable fastmath operations, defaults to True.
    :type fastmath: bool
    :param cache: Flag to enable caching of the compiled function, defaults to True.
    :type cache: bool
    :param signature: Optional Numba signature.
    :type signature: Any
    :return: The Numba JIT compiled function.
    :rtype: Callable[..., Any]
    """
    if signature is not None:
        return nb.njit(signature, fastmath=fastmath, cache=cache)(py_func)
    else:
        return nb.njit(fastmath=fastmath, cache=cache)(py_func)


def _canonicalize_node(
        node: Expr,
        runtime_uids: Set[int],
        param_uids: Set[int],
        runtime_slots: Dict[int, str],
        param_slots: Dict[int, str],
        found_runtime_vars_ordered: List[Var],
        seen_runtime_uids: Set[int]
) -> str:
    """
    Canonicalizes an expression while distinguishing runtime variables from parameters.

    Runtime variables get placeholders __RVAR_k__ and are also collected in order.
    Parameters get placeholders __PARAM_k__ but are NOT collected into template vars.
    """

    if isinstance(node, Var):
        target_uid: int = node.uid if node.base_var is None else node.base_var.uid

        if target_uid in runtime_uids:
            if target_uid not in runtime_slots:
                runtime_slots[target_uid] = f"__RVAR_{len(runtime_slots)}__"

            if target_uid not in seen_runtime_uids:
                seen_runtime_uids.add(target_uid)
                found_runtime_vars_ordered.append(node)

            return runtime_slots[target_uid]

        elif target_uid in param_uids:
            if target_uid not in param_slots:
                param_name: str = getattr(node, 'name', f'uid_{target_uid}')
                param_slots[target_uid] = f"__PARAM_{param_name}_{target_uid}__"

            return param_slots[target_uid]

        else:
            raise RuntimeError(
                f"Canonicalization found Var not classified as runtime or parameter: "
                f"name={getattr(node, 'name', '<?>')}, target_uid={target_uid}"
            )

    elif isinstance(node, Const):
        return f"{float(node.value):.6g}"

    elif isinstance(node, BinOp):
        left_str: str = _canonicalize_node(
            node.left, runtime_uids, param_uids,
            runtime_slots, param_slots,
            found_runtime_vars_ordered, seen_runtime_uids
        )
        right_str: str = _canonicalize_node(
            node.right, runtime_uids, param_uids,
            runtime_slots, param_slots,
            found_runtime_vars_ordered, seen_runtime_uids
        )

        if node.op in ['+', '*'] and left_str > right_str:
            left_str, right_str = right_str, left_str

        return f"({left_str}{node.op}{right_str})"

    elif isinstance(node, UnOp):
        op_str: str = _canonicalize_node(
            node.operand, runtime_uids, param_uids,
            runtime_slots, param_slots,
            found_runtime_vars_ordered, seen_runtime_uids
        )
        return f"{node.op}({op_str})"

    elif isinstance(node, Func):
        arg_str: str = _canonicalize_node(
            node.arg, runtime_uids, param_uids,
            runtime_slots, param_slots,
            found_runtime_vars_ordered, seen_runtime_uids
        )
        return f"{node.op}({arg_str})"

    else:
        return str(node)


def canonicalize_expression(
        expr: Expr,
        runtime_uids: Set[int],
        param_uids: Set[int]
) -> Tuple[str, List[Var]]:
    """
    Returns a canonical structural signature and the ordered runtime variables only.
    """

    runtime_slots: Dict[int, str] = dict()
    param_slots: Dict[int, str] = dict()
    found_runtime_vars_ordered: List[Var] = list()
    seen_runtime_uids: Set[int] = set()

    canonical_str: str = _canonicalize_node(
        node=expr,
        runtime_uids=runtime_uids,
        param_uids=param_uids,
        runtime_slots=runtime_slots,
        param_slots=param_slots,
        found_runtime_vars_ordered=found_runtime_vars_ordered,
        seen_runtime_uids=seen_runtime_uids
    )
    return canonical_str, found_runtime_vars_ordered


def _compile_fused_residual(kernels_data: List[Dict[str, Any]]) -> Callable[..., Any]:
    """
    Compiles a fused residual kernel that calls all sub-kernels in sequence.

    :param kernels_data: List of dictionaries containing the kernel functions and their indices.
    :type kernels_data: List[Dict[str, Any]]
    :return: A Numba JIT compiled fused function.
    :rtype: Callable[..., Any]
    """
    lines: List[str] = list()
    signature_payload = "|".join(
        f"{i}:{list(k_data['target'])}:{tuple(k_data['indices'].shape)}"
        for i, k_data in enumerate(kernels_data)
    )
    func_name = f"fused_residual_kernel_{hashlib.md5(signature_payload.encode()).hexdigest()[:12]}"

    lines.append(f"def {func_name}(states, params, history, d_history, h, args, out, history2=None):")
    lines.append("    out[:] = 0.0")

    for i, k_data in enumerate(kernels_data):
        lines.append(f"    target_{i} = args[{2 * i}]")
        lines.append(f"    indices_{i} = args[{2 * i + 1}]")
        lines.append(f"    r_part_{i} = func_{i}(states, params, history, d_history, h, indices_{i}, history2)")
        lines.append(f"    out[target_{i}] = r_part_{i}")

    py_func = _compile_to_file("\n".join(lines), func_name)
    for i, k_data in enumerate(kernels_data):
        py_func.__globals__[f"func_{i}"] = k_data['func']

    return nb.njit(fastmath=True, cache=True)(py_func)

@nb.njit(cache=True, fastmath=True)
def _scatter_color_jvp_to_csc_data(
        jvp: np.ndarray, data: np.ndarray, color_ptr: np.ndarray,col_ptr: np.ndarray,
        row_idx: np.ndarray, data_idx: np.ndarray, color_id: int) -> None:
    k0 = color_ptr[color_id]
    k1 = color_ptr[color_id + 1]
    for k in range(k0, k1):
        p0 = col_ptr[k]
        p1 = col_ptr[k + 1]
        for p in range(p0, p1):
            data[data_idx[p]] = jvp[row_idx[p]]


class Predictor:
    """
    Computes an explicit predictor for the Newton initial guess x_iter.
    """
    __slots__ = ['n_states']

    def __init__(self,
                 n_states: int) -> None:
        self.n_states = n_states

    def predict(self,
                x_iter: Vec,
                x_prev: Vec,
                dx_prev: Vec,
                h: float,
                pred_method: Union[DynamicIntegrationMethod|None] = DynamicIntegrationMethod.DaeBackEuler) -> Vec:
        """
        Apply predictor in-place and return x_iter.
        :param x_iter: Array to be written with the predictor guess (in-place).
        :param x_prev: Previous full variable vector at time n.
        :param dx_prev: Previous derivative vector (only first n_states are meaningful).
        :param h: Time step.
        :param pred_method: Integration method enum/value at the prediction step
        :return:
        """

        # Default: no-op predictor
        x_iter[:] = x_prev

        # Dispatch per method
        if pred_method == DynamicIntegrationMethod.OdeEuler:
            return self._predict_euler_state(x_iter, x_prev, dx_prev, h)
        elif pred_method == DynamicIntegrationMethod.DaeBDF2:
            raise NotImplementedError(f"predictor method {pred_method} ")

        # Otherwise keep default x_iter = x_prev
        return x_iter

    # ---------------------------------------------------------------------
    # Predictor implementations
    # ---------------------------------------------------------------------
    def _predict_euler_state(self,
                             x_iter: Vec,
                             x_prev: Vec,
                             dx_prev: Vec,
                             h: float) -> Vec:
        """
        Explicit Euler predictor for the *state* subset:
            x_{n+1}^0 = x_n + h * dx_n   (states only)
        Algebraics remain at x_prev by default (already set in caller).
        """
        ns = self.n_states
        x_iter[:ns] = x_prev[:ns] + h * dx_prev[:ns]
        return x_iter

class EquationGroup:
    """
    Data structure to hold clustered equations for auto-vectorization.
    Replaces the generic dictionary for strict type hinting and safety.
    """
    __slots__ = ['_idx_matrix', '_row_indices', '_template_eq', '_template_vars']

    def __init__(self) -> None:
        self._idx_matrix: List[List[int]] = list()
        self._row_indices: List[int] = list()
        self._template_eq: Expr | None = None
        self._template_vars: List[Var] | None = None

    def add_indices(self, var_indices: List[int], row_index: int) -> None:
        """Adds matrix indices and row index to the cluster."""
        self._idx_matrix.append(var_indices)
        self._row_indices.append(row_index)

    def set_template(self, template_eq: Expr, template_vars: List[Var]) -> None:
        """Sets the structural template for this group."""
        self._template_eq = template_eq
        self._template_vars = template_vars

    def get_idx_matrix(self) -> List[List[int]]:
        """Returns the index matrix."""
        return self._idx_matrix

    def get_row_indices(self) -> List[int]:
        """Returns the row indices."""
        return self._row_indices

    def get_template_eq(self) -> Expr | None:
        """Returns the template equation."""
        return self._template_eq

    def get_template_vars(self) -> List[Var] | None:
        """Returns the template variables."""
        return self._template_vars


class BoundaryUpdateWrapper:
    """
    Interface for injecting boundary conditions and events before the Newton step.
    Users must inherit from this class to update parameters safely.
    """
    __slots__ = []  # No state allowed in the base class

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Updates the parameters vector in place based on the current time and state.

        :param t: The current simulation time.
        :type t: float
        :param x: The current state vector.
        :type x: Vec
        :param params: The parameter vector to be modified.
        :type params: Vec
        :rtype: None
        """
        pass  # Explicit no-op for base class

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Returns the next forced-alignment event time inside (t_prev, t_target].
        Returns None if no forced event exists in that interval.

        :param t_prev: Start of the current local substep.
        :type t_prev: float
        :param t_target: End of the current macro-step.
        :type t_target: float
        :return: Next forced event time or None.
        :rtype: float | None
        """
        _unused: Tuple["BoundaryUpdateWrapper", float, float] = (self, t_prev, t_target)
        return None

# ==============================================================================
# Sparse AD Jacobian
# ==============================================================================

class SparseADJacobian:
    __slots__ = [
        'verbose', 'equations', 'variables', 'parameters', 'method', 'dtype',
        'n_rows', 'n_cols', 'var_map', 'col_rows', 'J', 'colors', 'n_colors',
        'color_groups', 'color_ptr', 'color_cols', 'col_ptr', 'row_idx', 'data_idx',
        '_compiler', 'ad_kernel', 'master_jac', '_seed_matrix'
    ]
    def __init__(
            self, equations: List[Any], variables: List[Any], parameters: List[Any],
            method: DynamicIntegrationMethod, use_cse: bool = True, dtype=np.float64, verbose: bool = False,
    ):
        self.verbose = verbose
        self.equations = equations
        self.variables = variables
        self.parameters = parameters
        self.method = method
        self.dtype = dtype

        self.n_rows = len(equations)
        self.n_cols = len(variables)

        self.var_map: Dict[int, int] = dict({id(v): i for i, v in enumerate(variables)})

        # Sparsity detection
        col_rows: List[List[int]] = list([list() for _ in range(self.n_cols)])
        for r_idx, eq in enumerate(equations):
            stack: List[Expr] = list([eq])
            visited: set = set()
            uids: set = set()

            while stack:
                node: Expr = stack.pop()
                if id(node) in visited:
                    pass
                else:
                    visited.add(id(node))

                    match node:
                        case Var():
                            uids.add(id(node))
                            if node.base_var is not None:
                                uids.add(id(node.base_var))
                            else:
                                pass

                        case BinOp(left=l, right=r):
                            stack.append(l)
                            stack.append(r)

                        case UnOp(operand=op):
                            stack.append(op)

                        case Func(arg=a):
                            stack.append(a)

                        case _:
                            pass

            for uid in uids:
                j: int = self.var_map.get(uid, -1)
                if j >= 0:
                    col_rows[j].append(r_idx)
                else:
                    pass

        self.col_rows = list([sorted(set(rows)) for rows in col_rows])

        # CSC structure
        indptr = np.zeros(self.n_cols + 1, dtype=np.int32)
        nnz: int = 0
        for j in range(self.n_cols):
            nnz += len(self.col_rows[j])
            indptr[j + 1] = nnz

        indices = np.empty(nnz, dtype=np.int32)
        data = np.zeros(nnz, dtype=self.dtype)

        k: int = 0
        for j in range(self.n_cols):
            for r_idx in self.col_rows[j]:
                indices[k] = r_idx
                k += 1

        self.J = csc_matrix((data, indices, indptr), shape=(self.n_rows, self.n_cols))

        # Coloring
        self.colors, self.n_colors = self._greedy_color_columns(self.col_rows, self.n_rows)
        groups: List[List[int]] = list([list() for _ in range(self.n_colors)])
        for j in range(self.n_cols):
            groups[self.colors[j]].append(j)
        self.color_groups = groups

        # Scatter map
        color_cols: List[int] = []
        color_ptr = np.zeros(self.n_colors + 1, dtype=np.int32)
        for c in range(self.n_colors):
            color_ptr[c] = len(color_cols)
            color_cols.extend(self.color_groups[c])
        color_ptr[self.n_colors] = len(color_cols)

        col_ptr = np.zeros(len(color_cols) + 1, dtype=np.int32)
        total_map:int = 0
        for kk, j in enumerate(color_cols):
            total_map += len(self.col_rows[j])
            col_ptr[kk + 1] = total_map

        row_idx = np.empty(total_map, dtype=np.int32)
        data_idx = np.empty(total_map, dtype=np.int32)

        pos: int = 0
        indptr_arr = self.J.indptr
        for kk, j in enumerate(color_cols):
            base = indptr_arr[j]
            for local, r_idx in enumerate(self.col_rows[j]):
                row_idx[pos] = r_idx
                data_idx[pos] = base + local
                pos += 1

        self.color_ptr, self.color_cols = color_ptr, np.asarray(color_cols, dtype=np.int32)
        self.col_ptr, self.row_idx, self.data_idx = col_ptr, row_idx, data_idx

        # Compile kernels
        self._compiler = EquationCompiler(variables=variables, parameters=parameters, method=method)
        k_name = f"advec_step_generic_{method}_{self.n_rows}_{self.n_cols}"
        py_ad = self._compiler.compile_ad_kernel(
            equations,
            func_name=k_name,
            use_cse=use_cse,
            active_indices=None,
        )
        self.ad_kernel = _safe_njit(py_ad, cache=True, fastmath=True)

        self._seed_matrix = np.zeros((self.n_colors, self.n_cols), dtype=self.dtype)
        for c in range(self.n_colors):
            self._seed_matrix[c, self.color_groups[c]] = 1.0

        func_name = f"master_jac_{method}_{self.n_rows}_{self.n_cols}_{self.n_colors}"
        src: List[str] = list([
            f"def {func_name}(states, seed_matrix, params, history, d_history, h, history2, data, color_ptr, col_ptr, row_idx, data_idx):"
        ])
        for c in range(self.n_colors):
            src.append(f"    jvp_{c} = kernel(states, seed_matrix[{c}], params, history, d_history, h, history2)")
            src.append(f"    _scatter(jvp_{c}, data, color_ptr, col_ptr, row_idx, data_idx, {c})")

        py_func = _compile_to_file("\n".join(src), func_name)
        py_func.__globals__["_scatter"] = _scatter_color_jvp_to_csc_data
        py_func.__globals__["kernel"] = self.ad_kernel
        self.master_jac = _safe_njit(py_func, fastmath=True, cache=True)

    @staticmethod
    def _greedy_color_columns(col_rows: List[List[int]], n_rows: int) -> Tuple[np.ndarray, int]:
        n_cols: int = len(col_rows)
        row_cols: List[List[int]] = list([list() for _ in range(n_rows)])
        for j in range(n_cols):
            for r_idx in col_rows[j]:
                row_cols[r_idx].append(j)

        adj: List[set] = list([set() for _ in range(n_cols)])
        for cols in row_cols:
            m: int = len(cols)
            for a in range(m):
                for b in range(a + 1, m):
                    if cols[b] != cols[a]:
                        adj[cols[a]].add(cols[b])
                        adj[cols[b]].add(cols[a])
                    else:
                        pass

        degrees = np.array([len(adj[j]) for j in range(n_cols)], dtype=np.int32)
        order = list(np.argsort(-degrees))
        colors = -np.ones(n_cols, dtype=np.int32)
        max_color = -1
        used = np.zeros(n_cols, dtype=np.bool_)

        for j in order:
            used[:] = False
            for nbj in adj[j]:
                if colors[nbj] >= 0:
                    used[colors[nbj]] = True
                else:
                    pass
            c: int = 0
            while c < n_cols and used[c]:
                c += 1
            colors[j] = c
            if c > max_color:
                max_color = c
            else:
                pass
        return colors, int(max_color + 1)

    def __call__(self, states, params, history, d_history, h, history2=None) -> csc_matrix:
        self.master_jac(states, self._seed_matrix, params, history, d_history, h, history2, self.J.data, self.color_ptr,
                        self.col_ptr, self.row_idx, self.data_idx)
        return self.J

# ==============================================================================
# StructuralVectorizedSolver
# ==============================================================================
class StructuralVectorizedSolver:
    __slots__ = [
        'problem', 't0', 't_end', 'h', 'method', 'pred_method', 'dense_threshold', 'verbose',
        'vec_jacobian', 'vec_flat_args', 'fused_residual', 'vec_kernels',
        '_state_vars', '_algebraic_vars', '_diff_vars', '_state_eqs', '_algebraic_eqs',
        'sorted_vars', '_n_state', '_n_vars', '_n_diff', 'uid2idx_vars',
        '_event_parameters', '_parameters', '_parameters_values', '_event_params_fn',
        'jit_jacobians_ad', 'vectorized_ready', '_last_sim_loop_time', '_newton_diag_config', '_vectorized_warmup_done'
    ]

    def __init__(self,
                 problem: EmtProblemTemplate,
                 t0: float,
                 t_end: float,
                 h: float,
                 method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
                 pred_method:DynamicIntegrationMethod = None,
                 dense_threshold: int = 100,
                 verbose: bool = False,
                 auto_vectorization: bool = True,
                 newton_diag_config: NewtonDiagnosticsConfig | None = None)-> None:
        """
        :param problem: The DAE problem definition.
        :param t0: Initial time.
        :param t_end: End time.
        :param h: Time step.
        :param method: DynamicIntegrationMethod (DaeTrapezoidal, DaeBackEuler, DaeBDF2).
        :param pred_method: DynamicIntegrationMethod used in the predictor step if method is explicit.
        :param dense_threshold: Threshold to switch between dense and sparse linear solvers.
        :param verbose: Print compilation and simulation timings.
        """
        self.problem = problem
        self.t0 = t0
        self.t_end = t_end
        self.h = h
        self.method = method
        self.pred_method = pred_method
        self.dense_threshold = dense_threshold
        self.verbose = verbose
        self._newton_diag_config = newton_diag_config or NewtonDiagnosticsConfig(
            compute_dense_cond=False,
            enable_fallback=False,
            enable_index1_check=False,
            enable_backtracking=False,
        )

        self.vec_jacobian = None
        self.vec_flat_args = None
        self.fused_residual = None
        self.vec_kernels = None

        self._state_vars = self.problem.get_state_vars()
        self._algebraic_vars = self.problem.get_algebraic_vars()
        self._diff_vars = self.problem.get_diff_vars()
        self._state_eqs = self.problem.get_state_eqs()
        self._algebraic_eqs = self.problem.get_algebraic_eqs()


        self.sorted_vars: List[Any] = list()
        self.sorted_vars.extend(self._state_vars)
        self.sorted_vars.extend(self._algebraic_vars)
        self._n_state = len(self._state_vars)
        self._n_vars = len(self.sorted_vars)
        self._n_diff = len(self._diff_vars)

        self.uid2idx_vars = {v.uid: i for i, v in enumerate(self.sorted_vars)}

        self._event_parameters = self.problem.get_variable_parameters()
        self._parameters = self.problem.get_constant_parameters()
        self._parameters_values = self.problem.get_parameters_values()

        self.jit_jacobians_ad: Dict[DynamicIntegrationMethod, SparseADJacobian] = dict()
        self.vectorized_ready = False
        self._vectorized_warmup_done = False

        if auto_vectorization:
            self.auto_detect_vectorization(method)

    def auto_detect_vectorization(self, method: DynamicIntegrationMethod = None):
        """
        Infers the algebraic structure of the DAE system (clustering) and compiles
        the vectorized matrix kernels.
        """
        if method is None:
            method = self.method

        if self.verbose:
            print("--- [AUTO-VEC] Inferring Algebraic Structure (Clustering) ---")
        t0 = time.time()

        groups: Dict[str, EquationGroup] = dict()

        n_state: int = len(self._state_eqs)
        n_alg: int = len(self._algebraic_eqs)
        full_eq_list: List[Expr] = [Const(0.0) for _ in range(n_state + n_alg)]

        # Build full residual system:
        #   differential eqs -> d_x - f(x, y, p) = 0
        #   algebraic eqs    -> g(x, y, p) = 0
        for i, rhs_eq in enumerate(self._state_eqs):
            sv = self._state_vars[i]
            d_term = Var(name=f"d_{sv.name}", base_var=sv)
            full_eq_list[i] = d_term - rhs_eq

        for j, alg_eq in enumerate(self._algebraic_eqs):
            full_eq_list[n_state + j] = alg_eq

        # UIDs of runtime variables (states + algebraics + diff placeholders through base_var)
        runtime_uids: Set[int] = set(self.uid2idx_vars.keys())

        # UIDs of parameters
        param_uids: Set[int] = set()
        for p in self._event_parameters:
            param_uids.add(p.uid)
        for p in self._parameters:
            param_uids.add(p.uid)

        # -----------------------------
        # PHASE 2: CLUSTERING
        # -----------------------------
        for i, residual_eq in enumerate(full_eq_list):
            sig_str, runtime_vars = canonicalize_expression(
                residual_eq,
                runtime_uids=runtime_uids,
                param_uids=param_uids
            )

            # Cluster by structural signature
            eq_hash = hashlib.md5(sig_str.encode()).hexdigest()

            if eq_hash in groups:
                group = groups[eq_hash]
            else:
                group = EquationGroup()
                groups[eq_hash] = group

            var_indices: List[int] = []
            for v in runtime_vars:
                target_uid: int = v.uid if v.base_var is None else v.base_var.uid
                idx: int | None = self.uid2idx_vars.get(target_uid, None)

                if idx is None:
                    raise RuntimeError(
                        f"Runtime variable missing in uid2idx_vars. "
                        f"eq={i}, var={getattr(v, 'name', '<?>')}, target_uid={target_uid}"
                    )

                var_indices.append(idx)

            if group.get_template_eq() is None:
                group.set_template(residual_eq, runtime_vars)
            else:
                template_vars = group.get_template_vars()
                if template_vars is None:
                    raise RuntimeError(f"Internal error: template_vars is None for group {eq_hash}")

                if len(var_indices) != len(template_vars):
                    raise RuntimeError(
                        f"Inconsistent clustered runtime var count for group {eq_hash}. "
                        f"eq={i}, got={len(var_indices)}, expected={len(template_vars)}"
                    )

            group.add_indices(var_indices, i)

        if self.verbose:
            print(f"   [AUTO-VEC] Detected {len(groups)} patterns in {len(full_eq_list)} total equations.")

        # -----------------------------
        # PHASE 3: KERNEL COMPILATION
        # -----------------------------
        self.vec_kernels: List[Dict[str, Any]] = list()

        all_params: List[Any] = list()
        all_params.extend(self._event_parameters)
        all_params.extend(self._parameters)

        vec_compiler = MatrixVectorizedCompiler(self.sorted_vars, all_params, method=method)

        for group_key_index, signature in enumerate(sorted(groups.keys())):
            group_data = groups[signature]
            k_name = f"vec_kernel_{method.name}_{group_key_index}"

            py_func = vec_compiler.compile_matrix_kernel(
                group_data.get_template_eq(),
                func_name=k_name,
                template_vars=group_data.get_template_vars()
            )

            self.vec_kernels.append({
                'func': nb.njit(cache=True, fastmath=True)(py_func),
                'indices': np.array(group_data.get_idx_matrix(), dtype=np.int32),
                'target': np.array(group_data.get_row_indices(), dtype=np.int32)
            })

        # -----------------------------
        # PHASE 4: DISPATCHER SETUP
        # -----------------------------
        self.fused_residual = _compile_fused_residual(self.vec_kernels)

        temp_args: List[Any] = list()
        for k in self.vec_kernels:
            temp_args.extend([k['target'], k['indices']])

        self.vec_flat_args = tuple(temp_args)

        # -----------------------------
        # PHASE 5: JACOBIAN SETUP
        # -----------------------------
        if method not in self.jit_jacobians_ad:
            self.jit_jacobians_ad[method] = SparseADJacobian(
                full_eq_list, self.sorted_vars, all_params, method, verbose=self.verbose
            )

        self.vec_jacobian = self.jit_jacobians_ad[method]
        self.vectorized_ready = True

        if self.verbose:
            print(f"   [AUTO-VEC] Setup finished in {time.time() - t0:.4f}s")


    def simulate(self,
                 x0: Union[Vec| None] = None,
                 dx0: Union[Vec| None] = None,
                 params0: Union[Vec| None] = None,
                 boundary_updater: BoundaryUpdateWrapper| None = None) -> Tuple[Vec, Mat, Mat]:

        """
        Run the vectorized DAE time-domain simulation.

        :param x0: Initial state vector.
        :param dx0: Initial derivative vector.
        :param params0: Initial event parameters.
        :param boundary_updater: Boundary condition updater.
        :return: Time vector and state trajectory matrix.
        """

        if x0 is None:
            x0 = self.problem.get_x0()
        else: pass

        if dx0 is None:
            dx0 = self.problem.get_dx0()
        else: pass

        if params0 is None:
            params0 = np.zeros(len(self._event_parameters), dtype=np.float64)
        else: pass

        return self._simulate_vectorized(self.t0, self.t_end, self.h, x0, dx0, params0, self.method,
                                         boundary_updater, self.verbose, self.dense_threshold)

    def _simulate_vectorized(self,
                             t0:float,
                             t_end:float,
                             h: float,
                             x0: Vec,
                             dx0: Vec,
                             params0: Vec,
                             method: DynamicIntegrationMethod,
                             boundary_updater: BoundaryUpdateWrapper,
                             verbose: bool,
                             dense_threshold: int)-> Tuple[Vec, Mat, Mat]:
        if not self.vectorized_ready:
            self.auto_detect_vectorization(method)

        steps: int = int(np.ceil((t_end - t0) / h))
        t: Vec = t0 + h * np.arange(steps + 1, dtype=np.float64)
        y: Mat = np.zeros((steps + 1, self._n_vars), dtype=np.float64)
        dy: Mat = np.zeros((steps + 1, self._n_diff), dtype=np.float64)
        y[0] = x0.copy()
        dy[0] = dx0.copy()

        x_prev: Vec = x0.copy()
        dx_prev: Vec = dx0.copy()
        x_prev2: Vec = x0.copy()
        x_iter: Vec = x0.copy()
        res_global: Vec = np.zeros(self._n_vars, dtype=np.float64)
        trial_state: Vec = np.zeros(self._n_vars, dtype=np.float64)
        trial_residual: Vec = np.zeros(self._n_vars, dtype=np.float64)

        static_params = np.array([c.value for c in self._parameters_values], dtype=np.float64)
        ev_params = np.asarray(params0, dtype=np.float64)

        full_params = np.empty(len(self._event_parameters) + len(static_params), dtype=np.float64)

        if len(ev_params) > 0:
            full_params[:len(ev_params)] = self.problem.def_event_params_fn(ev_params, float(t0))

        full_params[len(ev_params):] = static_params

        if boundary_updater is not None:
            boundary_updater.update(float(t0), x_prev, full_params)

        if len(ev_params) > 0:
            ev_params[:] = full_params[:len(ev_params)]

        use_dense: bool = (self._n_vars <= dense_threshold)
        trace_collector = self.problem.get_newton_trace_collector()
        diag_cfg = self._newton_diag_config
        diagnostics_enabled: bool = (
            trace_collector is not None
            or diag_cfg.compute_dense_cond
            or diag_cfg.enable_fallback
            or diag_cfg.enable_index1_check
            or diag_cfg.enable_backtracking
        )

        dense_solve: Callable[..., Vec] | None = None
        sparse_solve: Callable[..., Vec] | None = None

        if diagnostics_enabled:
            dense_solve = with_newton_diagnostics(
                lambda bundle, rhs: lu_solve(bundle[0], rhs),
                fallback_solve=lambda bundle, rhs: dense_lstsq_fallback(bundle[1], rhs),
                collector=trace_collector,
                config=diag_cfg,
                solver_name="dense_lu",
                matrix_getter=lambda bundle: bundle[1],
            )
            sparse_solve = with_newton_diagnostics(
                lambda bundle, rhs: bundle[0].solve(rhs),
                fallback_solve=lambda bundle, rhs: sparse_lsqr_fallback(bundle[1], rhs),
                collector=trace_collector,
                config=diag_cfg,
                solver_name="superlu",
                matrix_getter=lambda bundle: bundle[1],
            )
        else:
            pass

        if verbose:
            print("-> JIT Warmup.")

        self.fused_residual(x_prev, full_params, x_prev, dx_prev, h, self.vec_flat_args, res_global, x_prev2)
        _ = self.vec_jacobian(
            states=x_prev,
            params=full_params,
            history=x_prev,
            d_history=dx_prev,
            h=h,
            history2=x_prev2
        )

        t_start_loop = time.time()  # Timer local para debug

        if verbose: print(f"-> Starting VECTORIZED Simulation (Integration loop)...")

        for i in range(steps):
            if verbose:
                print(f"Simulating at step {i}")

            t_step_start: float = float(t[i])
            t_step_target: float = float(t[i + 1])

            t_local_prev: float = t_step_start
            is_first_local_step: bool = True

            while t_local_prev < (t_step_target - 1e-15):

                forced_event_time: float | None = None
                if boundary_updater is None:
                    pass
                else:
                    forced_event_time = boundary_updater.get_next_forced_event_time(
                        t_prev=float(t_local_prev),
                        t_target=float(t_step_target),
                    )

                if forced_event_time is None:
                    t_curr = t_step_target
                else:
                    t_curr = min(float(forced_event_time), t_step_target)

                    if t_curr <= t_local_prev + 1e-15:
                        t_curr = t_step_target
                    else:
                        pass

                is_aligned_substep: bool = t_curr < (t_step_target - 1e-15)

                if method == DynamicIntegrationMethod.DaeBDF2 and is_aligned_substep:
                    raise NotImplementedError(
                        "force_step_alignment is not implemented for DaeBDF2 in StructuralVectorizedSolver."
                    )
                else:
                    pass

                h_eff: float = float(t_curr - t_local_prev)

                # Update params in-place for the local substep end
                full_params[:len(ev_params)] = self.problem.def_event_params_fn(ev_params, float(t_curr))

                if boundary_updater is not None:
                    boundary_updater.update(t_curr, x_prev, full_params)
                else:
                    pass

                ev_params[:] = full_params[:len(ev_params)]

                x_iter[:] = x_prev
                last_res_norm: float = 1.0

                # IMPORTANT:
                # LU factors must be local to each substep, because x_prev, params and h_eff may change.
                cached_lu_dense: DenseSolveBundle | None = None
                cached_lu_sparse: SparseSolveBundle | None = None

                # PREDICTOR
                if i == 0 and is_first_local_step and method == DynamicIntegrationMethod.DaeTrapezoidal:
                    n_states = self.problem.get_states_number()
                    predictor = Predictor(n_states=n_states)
                    predictor.predict(
                        x_iter=x_iter,
                        x_prev=x_prev,
                        dx_prev=dx_prev,
                        h=h_eff,
                        pred_method=self.pred_method,
                    )
                else:
                    pass

                for k in range(15):
                    ctx: NewtonSolveContext | None = None
                    self.fused_residual(
                        x_iter,
                        full_params,
                        x_prev,
                        dx_prev,
                        h_eff,
                        self.vec_flat_args,
                        res_global,
                        x_prev2
                    )
                    res_norm: float = np.max(np.abs(res_global))

                    if res_norm < 1e-6:
                        break
                    else:
                        pass

                    if diagnostics_enabled:
                        ctx = NewtonSolveContext(
                            t=float(t_curr),
                            step_idx=int(i),
                            newton_iter=int(k),
                            phase="jit_vec",
                            method=str(method),
                        )
                        ctx.res_norm_inf = res_norm
                    else:
                        pass

                    recompute: bool = (cached_lu_dense is None and cached_lu_sparse is None) or \
                                      (k > 0 and (res_norm / (last_res_norm + 1e-16)) > 0.5)

                    if recompute:
                        cached_J: csc_matrix = self.vec_jacobian(
                            states=x_iter,
                            params=full_params,
                            history=x_prev,
                            d_history=dx_prev,
                            h=h_eff,
                            history2=x_prev2
                        )

                        if use_dense:
                            dense_jacobian = cached_J.toarray()

                            if diagnostics_enabled and ctx is not None:
                                maybe_check_index1(dense_jacobian, self._n_state, ctx=ctx, config=diag_cfg)
                            else:
                                pass

                            cached_lu_dense = (lu_factor(dense_jacobian), dense_jacobian)
                            cached_lu_sparse = None
                        else:
                            if diagnostics_enabled and ctx is not None:
                                maybe_check_index1(cached_J, self._n_state, ctx=ctx, config=diag_cfg)
                            else:
                                pass

                            cached_lu_sparse = (splu(cached_J), cached_J)
                            cached_lu_dense = None
                    else:
                        pass

                    if use_dense:
                        if diagnostics_enabled and ctx is not None:
                            assert dense_solve is not None
                            assert cached_lu_dense is not None
                            delta = dense_solve(cached_lu_dense, -res_global, ctx)
                        else:
                            assert cached_lu_dense is not None
                            delta = lu_solve(cached_lu_dense[0], -res_global)
                    else:
                        if diagnostics_enabled and ctx is not None:
                            assert sparse_solve is not None
                            assert cached_lu_sparse is not None
                            delta = sparse_solve(cached_lu_sparse, -res_global, ctx)
                        else:
                            assert cached_lu_sparse is not None
                            delta = cached_lu_sparse[0].solve(-res_global)

                    if diag_cfg.enable_backtracking:
                        def _evaluate_trial_residual(trial_x: Vec, out_res: Vec) -> float:
                            self.fused_residual(
                                trial_x,
                                full_params,
                                x_prev,
                                dx_prev,
                                h_eff,
                                self.vec_flat_args,
                                out_res,
                                x_prev2,
                            )
                            return float(np.max(np.abs(out_res)))

                        maybe_apply_backtracking(
                            x_iter,
                            delta,
                            res_norm,
                            trial_state,
                            trial_residual,
                            evaluate_residual=_evaluate_trial_residual,
                            config=diag_cfg,
                        )
                    else:
                        x_iter += delta

                    last_res_norm = res_norm

                if method == DynamicIntegrationMethod.DaeTrapezoidal:
                    dx_prev[:self._n_state] = (
                            (2.0 / h_eff) * (x_iter[:self._n_state] - x_prev[:self._n_state])
                            - dx_prev[:self._n_state]
                    )
                elif method == DynamicIntegrationMethod.DaeBDF2:
                    x_prev2[:] = x_prev
                    dx_prev[:self._n_state] = (
                                                      1.5 * x_iter[:self._n_state]
                                                      - 2.0 * x_prev[:self._n_state]
                                                      + 0.5 * x_prev2[:self._n_state]
                                              ) / h_eff
                else:
                    dx_prev[:self._n_state] = (
                                                      x_iter[:self._n_state] - x_prev[:self._n_state]
                                              ) / h_eff

                if method != DynamicIntegrationMethod.DaeBDF2:
                    x_prev2[:] = x_prev
                else:
                    pass

                x_prev[:] = x_iter
                t_local_prev = t_curr
                is_first_local_step = False

            y[i + 1] = x_prev
            dy[i + 1] = dx_prev

        self._last_sim_loop_time = time.time() - t_start_loop
        if verbose: print(f"VECTORIZED INTEGRATION LOOP Finished: {self._last_sim_loop_time:.4f}s")

        return t, y, dy
