# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Any, Callable, Dict, List, Set, Tuple
import hashlib
import time

import numba as nb
from numba import types
import numpy as np
import numpy.typing as npt
from scipy.linalg import lu_factor, lu_solve
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import SuperLU, splu

from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, Const, Expr, Func, UnOp, Var
from VeraGridEngine.Utils.Symbolic.jit_compiler import EagerEquationCompiler, _compile_to_file
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.basic_structures import Mat, Vec


Float64Vector = npt.NDArray[np.float64]
Float64Matrix = npt.NDArray[np.float64]
Int32Vector = npt.NDArray[np.int32]
Int32Matrix = npt.NDArray[np.int32]


def _safe_njit(
        py_func: Callable[..., Any],
        signature_tpe: Any,
        fastmath: bool = True,
        cache: bool = True,
) -> Callable[..., Any]:
    """
    Compile a Python function with Numba using an eager signature when provided.

    :param py_func: Python function created from generated symbolic source.
    :type py_func: Callable[..., Any]
    :param signature_tpe: Eager Numba signature or ``None``.
    :type signature_tpe: Any
    :param fastmath: Whether Numba should enable fastmath rewrites.
    :type fastmath: bool
    :param cache: Whether Numba should persist the compiled machine code.
    :type cache: bool
    :return: Compiled Numba function.
    :rtype: Callable[..., Any]
    """
    compiled_func: Callable[..., Any]

    if signature_tpe is None:
        compiled_func = nb.njit(fastmath=fastmath, cache=cache)(py_func)
    else:
        compiled_func = nb.njit(signature_tpe, fastmath=fastmath, cache=cache)(py_func)

    return compiled_func


def _build_fused_residual_signature() -> Any:
    """
    Return the eager signature of the fused residual dispatcher.

    :return: Eager Numba signature.
    :rtype: Any
    """
    float64_vector_tpe: Any = types.Array(types.float64, 1, "C")
    float64_matrix_tpe: Any = types.Array(types.float64, 2, "C")

    return types.void(
        float64_vector_tpe,
        float64_vector_tpe,
        float64_vector_tpe,
        float64_vector_tpe,
        types.float64,
        float64_vector_tpe,
        float64_vector_tpe,
        float64_matrix_tpe,
    )


def _build_master_jacobian_signature() -> Any:
    """
    Return the eager signature of the sparse Jacobian dispatcher.

    :return: Eager Numba signature.
    :rtype: Any
    """
    float64_vector_tpe: Any = types.Array(types.float64, 1, "C")
    float64_matrix_tpe: Any = types.Array(types.float64, 2, "C")
    int32_vector_tpe: Any = types.Array(types.int32, 1, "C")

    return types.void(
        float64_vector_tpe,
        float64_vector_tpe,
        float64_vector_tpe,
        float64_vector_tpe,
        float64_vector_tpe,
        types.float64,
        float64_vector_tpe,
        float64_vector_tpe,
        int32_vector_tpe,
        int32_vector_tpe,
        int32_vector_tpe,
        int32_vector_tpe,
        float64_matrix_tpe,
    )


def _get_runtime_uid(var_obj: Var) -> int:
    """
    Return the canonical runtime UID of a symbolic variable.

    :param var_obj: Symbolic variable or differential placeholder.
    :type var_obj: Var
    :return: Canonical runtime UID.
    :rtype: int
    """
    runtime_uid: int

    if var_obj.base_var is None:
        runtime_uid = var_obj.uid
    else:
        runtime_uid = var_obj.base_var.uid

    return runtime_uid


def _canonicalize_symbolic_node(
        node: Expr,
        runtime_uids: Set[int],
        parameter_uids: Set[int],
        runtime_slots: Dict[int, str],
        parameter_slots: Dict[int, str],
        ordered_runtime_vars: List[Var],
        visited_runtime_nodes: Set[int],
) -> str:
    """
    Convert a symbolic expression into a structural canonical string.

    :param node: Symbolic node to canonicalize.
    :type node: Expr
    :param runtime_uids: UIDs that belong to the state or algebraic runtime vector.
    :type runtime_uids: Set[int]
    :param parameter_uids: UIDs that belong to the parameter vector.
    :type parameter_uids: Set[int]
    :param runtime_slots: Runtime placeholder mapping.
    :type runtime_slots: Dict[int, str]
    :param parameter_slots: Parameter placeholder mapping.
    :type parameter_slots: Dict[int, str]
    :param ordered_runtime_vars: Ordered runtime variables found in the expression.
    :type ordered_runtime_vars: List[Var]
    :param visited_runtime_nodes: Visited node identifiers for stable collection.
    :type visited_runtime_nodes: Set[int]
    :return: Canonical structural representation.
    :rtype: str
    """
    if isinstance(node, Var):
        runtime_uid: int = _get_runtime_uid(node)
        node_identifier: int = id(node)

        if runtime_uid in runtime_uids:
            if runtime_uid in runtime_slots:
                pass
            else:
                runtime_slots[runtime_uid] = f"__RVAR_{len(runtime_slots)}__"

            if node_identifier in visited_runtime_nodes:
                pass
            else:
                visited_runtime_nodes.add(node_identifier)
                ordered_runtime_vars.append(node)

            return runtime_slots[runtime_uid]
        elif runtime_uid in parameter_uids:
            if runtime_uid in parameter_slots:
                pass
            else:
                parameter_slots[runtime_uid] = f"__PARAM_{len(parameter_slots)}__"

            return parameter_slots[runtime_uid]
        else:
            raise RuntimeError(f"Unclassified symbolic variable uid={runtime_uid}")
    elif isinstance(node, Const):
        return f"{float(node.value):.16g}"
    elif isinstance(node, BinOp):
        left_str: str = _canonicalize_symbolic_node(
            node.left,
            runtime_uids,
            parameter_uids,
            runtime_slots,
            parameter_slots,
            ordered_runtime_vars,
            visited_runtime_nodes,
        )
        right_str: str = _canonicalize_symbolic_node(
            node.right,
            runtime_uids,
            parameter_uids,
            runtime_slots,
            parameter_slots,
            ordered_runtime_vars,
            visited_runtime_nodes,
        )
        return f"({left_str}{node.op}{right_str})"
    elif isinstance(node, UnOp):
        operand_str: str = _canonicalize_symbolic_node(
            node.operand,
            runtime_uids,
            parameter_uids,
            runtime_slots,
            parameter_slots,
            ordered_runtime_vars,
            visited_runtime_nodes,
        )
        return f"{node.op}({operand_str})"
    elif isinstance(node, Func):
        argument_str: str = _canonicalize_symbolic_node(
            node.arg,
            runtime_uids,
            parameter_uids,
            runtime_slots,
            parameter_slots,
            ordered_runtime_vars,
            visited_runtime_nodes,
        )
        return f"{node.op}({argument_str})"
    else:
        return str(node)


def canonicalize_expression(
        expr: Expr,
        runtime_uids: Set[int],
        parameter_uids: Set[int],
) -> Tuple[str, List[Var]]:
    """
    Return the canonical signature and ordered runtime variables of an expression.

    :param expr: Symbolic expression to analyze.
    :type expr: Expr
    :param runtime_uids: UIDs that belong to the runtime vector.
    :type runtime_uids: Set[int]
    :param parameter_uids: UIDs that belong to the parameter vector.
    :type parameter_uids: Set[int]
    :return: Canonical structural string and ordered runtime variables.
    :rtype: Tuple[str, List[Var]]
    """
    runtime_slots: Dict[int, str] = dict()
    parameter_slots: Dict[int, str] = dict()
    ordered_runtime_vars: List[Var] = list()
    visited_runtime_nodes: Set[int] = set()
    signature_str: str = _canonicalize_symbolic_node(
        expr,
        runtime_uids,
        parameter_uids,
        runtime_slots,
        parameter_slots,
        ordered_runtime_vars,
        visited_runtime_nodes,
    )
    return signature_str, ordered_runtime_vars


def _build_full_residual_equations(
        state_vars: List[Var],
        state_eqs: List[Expr],
        algebraic_eqs: List[Expr],
) -> List[Expr]:
    """
    Build the full implicit residual system used by Newton iterations.

    :param state_vars: Ordered state variables.
    :type state_vars: List[Var]
    :param state_eqs: Differential right-hand sides.
    :type state_eqs: List[Expr]
    :param algebraic_eqs: Algebraic constraints.
    :type algebraic_eqs: List[Expr]
    :return: Full residual system in solver order.
    :rtype: List[Expr]
    """
    n_state: int = len(state_eqs)
    n_alg: int = len(algebraic_eqs)
    full_eqs: List[Expr] = [Const(0.0) for _ in range(n_state + n_alg)]
    i: int = 0

    # The differential block is converted into d_x - f(x, y, p) = 0.
    while i < n_state:
        state_var: Var = state_vars[i]
        differential_term: Var = Var(name=f"d_{state_var.name}", base_var=state_var)
        full_eqs[i] = differential_term - state_eqs[i]
        i += 1

    # The algebraic block is appended directly after the state residuals.
    i = 0
    while i < n_alg:
        full_eqs[n_state + i] = algebraic_eqs[i]
        i += 1

    return full_eqs


def _build_parameter_uid_set(
        variable_parameters: List[Var],
        constant_parameters: List[Var],
) -> Set[int]:
    """
    Build the parameter UID set used by structural canonicalization.

    :param variable_parameters: Runtime parameters.
    :type variable_parameters: List[Var]
    :param constant_parameters: Constant parameters.
    :type constant_parameters: List[Var]
    :return: UID set of all parameters visible to the solver.
    :rtype: Set[int]
    """
    parameter_uids: Set[int] = set()
    parameter: Var

    for parameter in variable_parameters:
        parameter_uids.add(parameter.uid)

    for parameter in constant_parameters:
        parameter_uids.add(parameter.uid)

    return parameter_uids


def _build_backend_cache_token(
        method: DynamicIntegrationMethod,
        n_rows: int,
        n_cols: int,
        group_keys: List[str],
) -> str:
    """
    Return a deterministic cache token for backend-generated dispatchers.

    :param method: Integration method used by the backend.
    :type method: DynamicIntegrationMethod
    :param n_rows: Number of residual equations.
    :type n_rows: int
    :param n_cols: Number of runtime variables.
    :type n_cols: int
    :param group_keys: Structural group signatures.
    :type group_keys: List[str]
    :return: Stable cache token.
    :rtype: str
    """
    payload: str = "|".join([method.name, str(n_rows), str(n_cols), *group_keys])
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]


def _greedy_color_columns(col_rows: List[List[int]], n_rows: int) -> Tuple[Int32Vector, int, List[List[int]]]:
    """
    Color the sparse column dependency graph with a greedy heuristic.

    :param col_rows: Row indices present in each sparse column.
    :type col_rows: List[List[int]]
    :param n_rows: Total number of rows in the Jacobian.
    :type n_rows: int
    :return: Colors per column, number of colors and explicit color groups.
    :rtype: Tuple[Int32Vector, int, List[List[int]]]
    """
    n_cols: int = len(col_rows)
    row_cols: List[List[int]] = list()
    adjacency: List[Set[int]] = list()
    color_groups: List[List[int]] = list()
    degrees: Int32Vector
    order: Int32Vector
    colors: Int32Vector
    used: npt.NDArray[np.bool_]
    row_index: int
    col_index: int

    row_index = 0
    while row_index < n_rows:
        row_cols.append(list())
        row_index += 1

    col_index = 0
    while col_index < n_cols:
        row_list: List[int] = col_rows[col_index]
        row_position: int = 0

        while row_position < len(row_list):
            row_cols[row_list[row_position]].append(col_index)
            row_position += 1

        col_index += 1

    col_index = 0
    while col_index < n_cols:
        adjacency.append(set())
        col_index += 1

    row_index = 0
    while row_index < n_rows:
        cols_in_row: List[int] = row_cols[row_index]
        left_pos: int = 0

        while left_pos < len(cols_in_row):
            right_pos: int = left_pos + 1

            while right_pos < len(cols_in_row):
                left_col: int = cols_in_row[left_pos]
                right_col: int = cols_in_row[right_pos]

                if left_col == right_col:
                    pass
                else:
                    adjacency[left_col].add(right_col)
                    adjacency[right_col].add(left_col)

                right_pos += 1

            left_pos += 1

        row_index += 1

    degrees = np.zeros(n_cols, dtype=np.int32)
    col_index = 0
    while col_index < n_cols:
        degrees[col_index] = len(adjacency[col_index])
        col_index += 1

    order = np.argsort(-degrees).astype(np.int32)
    colors = -np.ones(n_cols, dtype=np.int32)
    used = np.zeros(n_cols, dtype=np.bool_)
    max_color: int = -1

    col_index = 0
    while col_index < len(order):
        candidate_col: int = int(order[col_index])
        used[:] = False

        neighbor_col: int
        for neighbor_col in adjacency[candidate_col]:
            neighbor_color: int = int(colors[neighbor_col])

            if neighbor_color >= 0:
                used[neighbor_color] = True
            else:
                pass

        color_value: int = 0
        while color_value < n_cols and used[color_value]:
            color_value += 1

        colors[candidate_col] = color_value

        if color_value > max_color:
            max_color = color_value
        else:
            pass

        col_index += 1

    color_index: int = 0
    while color_index < max_color + 1:
        color_groups.append(list())
        color_index += 1

    col_index = 0
    while col_index < n_cols:
        color_groups[int(colors[col_index])].append(col_index)
        col_index += 1

    return colors, int(max_color + 1), color_groups


@nb.njit(cache=True, fastmath=True)
def _scatter_color_jvp_to_csc_data(
        jvp: Float64Vector,
        data: Float64Vector,
        color_ptr: Int32Vector,
        col_ptr: Int32Vector,
        row_idx: Int32Vector,
        data_idx: Int32Vector,
        color_id: int,
) -> None:
    """
    Scatter a colored JVP vector into CSC numeric storage.

    :param jvp: JVP vector for the active color.
    :type jvp: Float64Vector
    :param data: Target CSC numeric values.
    :type data: Float64Vector
    :param color_ptr: Pointer to the column-color groups.
    :type color_ptr: Int32Vector
    :param col_ptr: Pointer to each grouped column map.
    :type col_ptr: Int32Vector
    :param row_idx: Row indices in CSC order.
    :type row_idx: Int32Vector
    :param data_idx: Direct positions inside ``data``.
    :type data_idx: Int32Vector
    :param color_id: Active color identifier.
    :type color_id: int
    :return: None
    :rtype: None
    """
    k0: int = int(color_ptr[color_id])
    k1: int = int(color_ptr[color_id + 1])
    k: int = k0

    while k < k1:
        p0: int = int(col_ptr[k])
        p1: int = int(col_ptr[k + 1])
        p: int = p0

        while p < p1:
            data[data_idx[p]] = jvp[row_idx[p]]
            p += 1

        k += 1


@nb.njit(cache=True, fastmath=True)
def _max_abs_value(values: Float64Vector) -> float:
    """
    Compute the infinity norm without allocating temporary arrays.

    :param values: Vector to inspect.
    :type values: Float64Vector
    :return: Maximum absolute value.
    :rtype: float
    """
    max_value: float = 0.0
    index: int = 0

    while index < values.shape[0]:
        raw_value: float = float(values[index])
        abs_value: float

        if raw_value < 0.0:
            abs_value = -raw_value
        else:
            abs_value = raw_value

        if abs_value > max_value:
            max_value = abs_value
        else:
            pass

        index += 1

    return max_value


@nb.njit(cache=True, fastmath=True)
def _copy_negated_vector(values: Float64Vector, out: Float64Vector) -> None:
    """
    Write the negated vector into a preallocated buffer.

    :param values: Source vector.
    :type values: Float64Vector
    :param out: Destination vector.
    :type out: Float64Vector
    :return: None
    :rtype: None
    """
    index: int = 0

    while index < values.shape[0]:
        out[index] = -values[index]
        index += 1


class StructuralCompiledBoundaryUpdateWrapper:
    """
    Boundary update interface for the structural compiled solver.

    The structural compiled solver keeps the linear algebra outside Numba, but it still needs a
    typed boundary update object to refresh runtime parameters between local
    substeps.
    """

    __slots__ = []

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Update the parameter vector in place.

        :param t: Current simulation time.
        :type t: float
        :param x: Current Newton iterate.
        :type x: Vec
        :param params: Full parameter vector.
        :type params: Vec
        :return: None
        :rtype: None
        """
        _unused: Tuple[float, Vec, Vec] = (t, x, params)
        return None

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Return the next forced event time inside the local substep.

        :param t_prev: Local substep start.
        :type t_prev: float
        :param t_target: Local substep nominal end.
        :type t_target: float
        :return: Next forced event time or ``None``.
        :rtype: float | None
        """
        _unused: Tuple[float, float] = (t_prev, t_target)
        return None


class StructuralCompiledPredictor:
    """
    Explicit predictor used to initialize the Newton iteration.
    """

    __slots__ = ["_n_states"]

    def __init__(self, n_states: int) -> None:
        """
        Create the predictor.

        :param n_states: Number of differential states.
        :type n_states: int
        :return: None
        :rtype: None
        """
        self._n_states = n_states

    def predict(
            self,
            x_iter: Vec,
            x_prev: Vec,
            dx_prev: Vec,
            h: float,
            pred_method: DynamicIntegrationMethod | None,
    ) -> Vec:
        """
        Write the predictor guess in place.

        :param x_iter: Destination vector for the predictor guess.
        :type x_iter: Vec
        :param x_prev: Previous variable vector.
        :type x_prev: Vec
        :param dx_prev: Previous differential vector.
        :type dx_prev: Vec
        :param h: Local time step.
        :type h: float
        :param pred_method: Predictor integration method.
        :type pred_method: DynamicIntegrationMethod | None
        :return: Updated predictor vector.
        :rtype: Vec
        """
        # The default predictor is a no-op copy because it is always safe.
        x_iter[:] = x_prev

        # Explicit Euler is only applied to the differential subset.
        if pred_method == DynamicIntegrationMethod.OdeEuler:
            x_iter[:self._n_states] = x_prev[:self._n_states] + h * dx_prev[:self._n_states]
        else:
            pass

        return x_iter


class StructuralCompiledEquationGroup:
    """
    Structural group of equations that share the same vectorized template.
    """

    __slots__ = ["_index_matrix", "_row_indices", "_template_eq", "_template_vars"]

    def __init__(self) -> None:
        """
        Create an empty structural group.

        :return: None
        :rtype: None
        """
        self._index_matrix: List[List[int]] = list()
        self._row_indices: List[int] = list()
        self._template_eq: Expr | None = None
        self._template_vars: List[Var] | None = None

    def set_template(self, template_eq: Expr, template_vars: List[Var]) -> None:
        """
        Store the canonical template of the group.

        :param template_eq: Canonical structural equation.
        :type template_eq: Expr
        :param template_vars: Ordered runtime variables of the template.
        :type template_vars: List[Var]
        :return: None
        :rtype: None
        """
        self._template_eq = template_eq
        self._template_vars = list(template_vars)

    def add_indices(self, variable_indices: List[int], row_index: int) -> None:
        """
        Append one grouped equation instance.

        :param variable_indices: Runtime indices used by this equation instance.
        :type variable_indices: List[int]
        :param row_index: Global residual row index.
        :type row_index: int
        :return: None
        :rtype: None
        """
        self._index_matrix.append(list(variable_indices))
        self._row_indices.append(row_index)

    def get_index_matrix(self) -> List[List[int]]:
        """
        Return the grouped runtime index matrix.

        :return: Grouped runtime index matrix.
        :rtype: List[List[int]]
        """
        return self._index_matrix

    def get_row_indices(self) -> List[int]:
        """
        Return the residual rows covered by the group.

        :return: Residual row indices.
        :rtype: List[int]
        """
        return self._row_indices

    def get_template_eq(self) -> Expr | None:
        """
        Return the template equation.

        :return: Template equation or ``None``.
        :rtype: Expr | None
        """
        return self._template_eq

    def get_template_vars(self) -> List[Var] | None:
        """
        Return the template runtime variables.

        :return: Ordered template runtime variables or ``None``.
        :rtype: List[Var] | None
        """
        return self._template_vars


class StructuralCompiledVectorKernel:
    """
    Typed container for one vectorized residual kernel.
    """

    __slots__ = ["_kernel", "_indices", "_target_rows", "_row_count"]

    def __init__(self, kernel: Callable[..., Any], indices: Int32Matrix, target_rows: Int32Vector) -> None:
        """
        Create the vectorized kernel container.

        :param kernel: Compiled eager kernel.
        :type kernel: Callable[..., Any]
        :param indices: Runtime gather matrix.
        :type indices: Int32Matrix
        :param target_rows: Residual rows written by the kernel.
        :type target_rows: Int32Vector
        :return: None
        :rtype: None
        """
        self._kernel = kernel
        self._indices = indices
        self._target_rows = target_rows
        self._row_count = int(target_rows.shape[0])

    def get_kernel(self) -> Callable[..., Any]:
        """
        Return the compiled kernel.

        :return: Compiled kernel.
        :rtype: Callable[..., Any]
        """
        return self._kernel

    def get_indices(self) -> Int32Matrix:
        """
        Return the runtime gather matrix.

        :return: Runtime gather matrix.
        :rtype: Int32Matrix
        """
        return self._indices

    def get_target_rows(self) -> Int32Vector:
        """
        Return the residual target rows.

        :return: Residual target rows.
        :rtype: Int32Vector
        """
        return self._target_rows

    def get_row_count(self) -> int:
        """
        Return the number of rows emitted by the kernel.

        :return: Number of grouped rows.
        :rtype: int
        """
        return self._row_count


def _compile_fused_residual_kernel(kernel_specs: List[StructuralCompiledVectorKernel], cache_token: str) -> Callable[..., Any]:
    """
    Build the eager residual dispatcher that reuses preallocated work buffers.

    :param kernel_specs: Vectorized residual kernels.
    :type kernel_specs: List[StructuralCompiledVectorKernel]
    :return: Compiled fused residual dispatcher.
    :rtype: Callable[..., Any]
    """
    lines: List[str] = list()
    kernel_index: int = 0
    func_name: str = f"structural_compiled_fused_residual_{cache_token}"

    # The dispatcher clears the global residual first and then reuses one work row per group.
    lines.append(f"def {func_name}(states, params, history, d_history, h, history2, data_out, work_buffers):")
    lines.append("    data_out[:] = 0.0")

    while kernel_index < len(kernel_specs):
        kernel_spec: StructuralCompiledVectorKernel = kernel_specs[kernel_index]
        function_name: str = f"kernel_{kernel_index}"
        indices_name: str = f"indices_{kernel_index}"
        target_name: str = f"target_{kernel_index}"
        row_count: int = kernel_spec.get_row_count()

        # Each structural group writes into its dedicated row of the work matrix.
        lines.append(f"    local_out_{kernel_index} = work_buffers[{kernel_index}, :{row_count}]")
        lines.append(
            f"    {function_name}(states, params, history, d_history, h, {indices_name}, local_out_{kernel_index}, history2)"
        )
        lines.append(f"    for local_index_{kernel_index} in range({row_count}):")
        lines.append(
            f"        data_out[{target_name}[local_index_{kernel_index}]] = local_out_{kernel_index}[local_index_{kernel_index}]"
        )

        kernel_index += 1

    py_func: Callable[..., Any] = _compile_to_file("\n".join(lines), func_name)

    for kernel_index, kernel_spec in enumerate(kernel_specs):
        py_func.__globals__[f"kernel_{kernel_index}"] = kernel_spec.get_kernel()
        py_func.__globals__[f"indices_{kernel_index}"] = kernel_spec.get_indices()
        py_func.__globals__[f"target_{kernel_index}"] = kernel_spec.get_target_rows()

    return _safe_njit(
        py_func,
        signature_tpe=_build_fused_residual_signature(),
        fastmath=True,
        cache=True,
    )


def _compile_master_jacobian_kernel(
        ad_kernels: List[Callable[..., Any]],
        n_colors: int,
        cache_token: str,
) -> Callable[..., Any]:
    """
    Build the eager sparse Jacobian dispatcher.

    :param ad_kernels: Color-specific AD kernels.
    :type ad_kernels: List[Callable[..., Any]]
    :param n_colors: Number of graph colors.
    :type n_colors: int
    :return: Compiled master Jacobian dispatcher.
    :rtype: Callable[..., Any]
    """
    lines: List[str] = list()
    color_index: int = 0
    func_name: str = f"structural_compiled_master_jacobian_{cache_token}"

    # The dispatcher reuses one JVP buffer per color and then scatters into CSC storage.
    lines.append(
        f"def {func_name}(states, seeds, params, history, d_history, h, history2, data, color_ptr, col_ptr, row_idx, data_idx, work_jvp):"
    )

    while color_index < n_colors:
        kernel_name: str = f"kernel_{color_index}"
        lines.append(f"    local_jvp_{color_index} = work_jvp[{color_index}]")
        lines.append(
            f"    {kernel_name}(states, seeds, params, history, d_history, h, local_jvp_{color_index}, history2)"
        )
        lines.append(
            f"    _scatter(local_jvp_{color_index}, data, color_ptr, col_ptr, row_idx, data_idx, {color_index})"
        )
        color_index += 1

    py_func: Callable[..., Any] = _compile_to_file("\n".join(lines), func_name)
    py_func.__globals__["_scatter"] = _scatter_color_jvp_to_csc_data

    for color_index in range(n_colors):
        py_func.__globals__[f"kernel_{color_index}"] = ad_kernels[color_index]

    return _safe_njit(
        py_func,
        signature_tpe=_build_master_jacobian_signature(),
        fastmath=True,
        cache=True,
    )


class StructuralCompiledResidualAssembler:
    """
    Residual dispatcher that reuses preallocated grouped work buffers.
    """

    __slots__ = ["_kernel_specs", "_dispatcher", "_work_buffer", "_build_stats"]

    def __init__(self, kernel_specs: List[StructuralCompiledVectorKernel], cache_token: str) -> None:
        """
        Create the residual assembler.

        :param kernel_specs: Vectorized residual kernels.
        :type kernel_specs: List[StructuralCompiledVectorKernel]
        :return: None
        :rtype: None
        """
        t_start: float = time.perf_counter()
        self._kernel_specs: List[StructuralCompiledVectorKernel] = kernel_specs

        t_dispatcher_start: float = time.perf_counter()
        self._dispatcher: Callable[..., Any] = _compile_fused_residual_kernel(kernel_specs, cache_token)
        dispatcher_build_s: float = time.perf_counter() - t_dispatcher_start

        max_kernel_size: int = 0
        kernel_spec: StructuralCompiledVectorKernel
        for kernel_spec in kernel_specs:
            if kernel_spec.get_row_count() > max_kernel_size:
                max_kernel_size = kernel_spec.get_row_count()
            else:
                pass

        t_buffer_start: float = time.perf_counter()

        # The work matrix has one row per structural group and enough columns for the largest group.
        self._work_buffer: Float64Matrix = np.zeros((len(kernel_specs), max_kernel_size), dtype=np.float64)

        buffer_alloc_s: float = time.perf_counter() - t_buffer_start
        self._build_stats: Dict[str, float] = {
            "dispatcher_build_s": dispatcher_build_s,
            "buffer_alloc_s": buffer_alloc_s,
            "total_s": time.perf_counter() - t_start,
        }

    def evaluate(
            self,
            states: Vec,
            params: Vec,
            history: Vec,
            d_history: Vec,
            h: float,
            history2: Vec,
            data_out: Vec,
    ) -> None:
        """
        Evaluate the grouped residual system in place.

        :param states: Current Newton iterate.
        :type states: Vec
        :param params: Full parameter vector.
        :type params: Vec
        :param history: Previous state vector.
        :type history: Vec
        :param d_history: Previous differential vector.
        :type d_history: Vec
        :param h: Local time step.
        :type h: float
        :param history2: Secondary history vector.
        :type history2: Vec
        :param data_out: Residual output buffer.
        :type data_out: Vec
        :return: None
        :rtype: None
        """
        self._dispatcher(states, params, history, d_history, h, history2, data_out, self._work_buffer)

    def get_work_buffer(self) -> Float64Matrix:
        """
        Return the grouped work buffer.

        :return: Grouped work buffer.
        :rtype: Float64Matrix
        """
        return self._work_buffer

    def get_build_stats(self) -> Dict[str, float]:
        """
        Return residual assembler setup timings.

        :return: Residual assembler build timings.
        :rtype: Dict[str, float]
        """
        return dict(self._build_stats)


class StructuralCompiledSparseADJacobian:
    """
    Sparse structural AD Jacobian that writes directly into CSC storage.
    """

    __slots__ = [
        "_equations",
        "_variables",
        "_parameters",
        "_method",
        "_dtype",
        "_n_rows",
        "_n_cols",
        "_column_rows",
        "_jacobian_matrix",
        "_colors",
        "_n_colors",
        "_color_groups",
        "_color_ptr",
        "_col_ptr",
        "_row_idx",
        "_data_idx",
        "_compiler",
        "_ad_kernels",
        "_master_dispatcher",
        "_seed_buffer",
        "_jvp_work_buffer",
        "_data_buffer",
        "_build_stats",
    ]

    def __init__(
            self,
            equations: List[Expr],
            variables: List[Var],
            parameters: List[Var],
            method: DynamicIntegrationMethod,
            dtype: Any = np.float64,
            use_cse: bool = True,
            cache_token: str = "default",
    ) -> None:
        """
        Create the sparse AD Jacobian evaluator.

        :param equations: Full residual equations.
        :type equations: List[Expr]
        :param variables: Runtime variables of the DAE system.
        :type variables: List[Var]
        :param parameters: Full parameter list.
        :type parameters: List[Var]
        :param method: Implicit integration method.
        :type method: DynamicIntegrationMethod
        :param dtype: Numeric dtype of the Jacobian storage.
        :type dtype: Any
        :param use_cse: Whether color kernels should emit CSE temporaries.
        :type use_cse: bool
        :return: None
        :rtype: None
        """
        t_start: float = time.perf_counter()

        self._equations = equations
        self._variables = variables
        self._parameters = parameters
        self._method = method
        self._dtype = dtype
        self._n_rows = len(equations)
        self._n_cols = len(variables)

        # The sparsity pattern is extracted once from the symbolic graph and then reused forever.
        t_column_rows_start: float = time.perf_counter()
        self._column_rows = self._build_column_rows()
        column_rows_s: float = time.perf_counter() - t_column_rows_start

        t_csc_start: float = time.perf_counter()
        self._jacobian_matrix, self._data_buffer = self._build_csc_matrix()
        csc_shell_s: float = time.perf_counter() - t_csc_start

        t_coloring_start: float = time.perf_counter()
        self._colors, self._n_colors, self._color_groups = _greedy_color_columns(self._column_rows, self._n_rows)
        coloring_s: float = time.perf_counter() - t_coloring_start

        t_scatter_start: float = time.perf_counter()
        self._color_ptr, self._col_ptr, self._row_idx, self._data_idx = self._build_scatter_map()
        scatter_map_s: float = time.perf_counter() - t_scatter_start

        # The eager compiler emits strictly typed kernels that write into caller-owned buffers.
        self._compiler = EagerEquationCompiler(variables=variables, parameters=parameters, method=method)

        t_ad_kernels_start: float = time.perf_counter()
        self._ad_kernels = self._build_ad_kernels(use_cse)
        ad_kernels_s: float = time.perf_counter() - t_ad_kernels_start

        t_dispatcher_start: float = time.perf_counter()
        self._master_dispatcher = _compile_master_jacobian_kernel(self._ad_kernels, self._n_colors, cache_token)
        dispatcher_build_s: float = time.perf_counter() - t_dispatcher_start

        # The seed buffer remains zero because each color kernel already hardcodes its active columns.
        self._seed_buffer = np.zeros(self._n_cols, dtype=self._dtype)

        # One JVP row per color is enough because colors are executed sequentially.
        self._jvp_work_buffer = np.zeros((self._n_colors, self._n_rows), dtype=self._dtype)
        self._build_stats: Dict[str, float] = {
            "column_rows_s": column_rows_s,
            "csc_shell_s": csc_shell_s,
            "coloring_s": coloring_s,
            "scatter_map_s": scatter_map_s,
            "ad_kernels_s": ad_kernels_s,
            "dispatcher_build_s": dispatcher_build_s,
            "total_s": time.perf_counter() - t_start,
        }

    def _build_column_rows(self) -> List[List[int]]:
        """
        Build the symbolic sparsity pattern column by column.

        :return: Row indices present in each sparse column.
        :rtype: List[List[int]]
        """
        variable_index_by_uid: Dict[int, int] = dict()
        column_rows: List[List[int]] = list()
        row_index: int = 0
        variable_index: int = 0

        while variable_index < self._n_cols:
            variable_obj: Var = self._variables[variable_index]
            variable_index_by_uid[variable_obj.uid] = variable_index
            column_rows.append(list())
            variable_index += 1

        while row_index < self._n_rows:
            equation: Expr = self._equations[row_index]
            stack: List[Expr] = list()
            visited_nodes: Set[int] = set()
            dependent_uids: Set[int] = set()

            stack.append(equation)

            while len(stack) > 0:
                node: Expr = stack.pop()
                node_identifier: int = id(node)

                if node_identifier in visited_nodes:
                    pass
                else:
                    visited_nodes.add(node_identifier)

                    if isinstance(node, Var):
                        dependent_uids.add(node.uid)

                        if node.base_var is None:
                            pass
                        else:
                            dependent_uids.add(node.base_var.uid)
                    elif isinstance(node, BinOp):
                        stack.append(node.left)
                        stack.append(node.right)
                    elif isinstance(node, UnOp):
                        stack.append(node.operand)
                    elif isinstance(node, Func):
                        stack.append(node.arg)
                    else:
                        pass

            dependent_uid: int
            for dependent_uid in dependent_uids:
                column_index: int | None = variable_index_by_uid.get(dependent_uid, None)

                if column_index is None:
                    pass
                else:
                    column_rows[column_index].append(row_index)

            row_index += 1

        column_index = 0
        while column_index < self._n_cols:
            column_rows[column_index] = sorted(set(column_rows[column_index]))
            column_index += 1

        return column_rows

    def _build_csc_matrix(self) -> Tuple[csc_matrix, Vec]:
        """
        Build the reusable CSC matrix shell and numeric data buffer.

        :return: CSC matrix shell and numeric data buffer.
        :rtype: Tuple[csc_matrix, Vec]
        """
        indptr: Int32Vector = np.zeros(self._n_cols + 1, dtype=np.int32)
        column_index: int = 0
        nnz: int = 0

        while column_index < self._n_cols:
            nnz += len(self._column_rows[column_index])
            indptr[column_index + 1] = nnz
            column_index += 1

        indices: Int32Vector = np.empty(nnz, dtype=np.int32)
        data: Vec = np.zeros(nnz, dtype=self._dtype)
        data_position: int = 0

        column_index = 0
        while column_index < self._n_cols:
            local_index: int = 0
            rows_in_column: List[int] = self._column_rows[column_index]

            while local_index < len(rows_in_column):
                indices[data_position] = rows_in_column[local_index]
                data_position += 1
                local_index += 1

            column_index += 1

        matrix: csc_matrix = csc_matrix((data, indices, indptr), shape=(self._n_rows, self._n_cols))
        return matrix, matrix.data

    def _build_scatter_map(self) -> Tuple[Int32Vector, Int32Vector, Int32Vector, Int32Vector]:
        """
        Precompute the CSC scatter topology for colored JVPs.

        :return: ``color_ptr``, ``col_ptr``, ``row_idx`` and ``data_idx`` arrays.
        :rtype: Tuple[Int32Vector, Int32Vector, Int32Vector, Int32Vector]
        """
        color_cols: List[int] = list()
        color_ptr: Int32Vector = np.zeros(self._n_colors + 1, dtype=np.int32)
        color_index: int = 0

        while color_index < self._n_colors:
            color_ptr[color_index] = len(color_cols)
            group_columns: List[int] = self._color_groups[color_index]
            group_position: int = 0

            while group_position < len(group_columns):
                color_cols.append(group_columns[group_position])
                group_position += 1

            color_index += 1

        color_ptr[self._n_colors] = len(color_cols)

        col_ptr: Int32Vector = np.zeros(len(color_cols) + 1, dtype=np.int32)
        total_map: int = 0
        color_column_index: int = 0

        while color_column_index < len(color_cols):
            total_map += len(self._column_rows[color_cols[color_column_index]])
            col_ptr[color_column_index + 1] = total_map
            color_column_index += 1

        row_idx: Int32Vector = np.empty(total_map, dtype=np.int32)
        data_idx: Int32Vector = np.empty(total_map, dtype=np.int32)
        position: int = 0
        indptr_array: Int32Vector = self._jacobian_matrix.indptr.astype(np.int32, copy=False)

        color_column_index = 0
        while color_column_index < len(color_cols):
            column_index: int = color_cols[color_column_index]
            base_position: int = int(indptr_array[column_index])
            rows_in_column: List[int] = self._column_rows[column_index]
            local_index: int = 0

            while local_index < len(rows_in_column):
                row_idx[position] = rows_in_column[local_index]
                data_idx[position] = base_position + local_index
                position += 1
                local_index += 1

            color_column_index += 1

        return color_ptr, col_ptr, row_idx, data_idx

    def _build_ad_kernels(self, use_cse: bool) -> List[Callable[..., Any]]:
        """
        Compile one eager AD kernel per graph color.

        :param use_cse: Whether color kernels should emit CSE temporaries.
        :type use_cse: bool
        :return: Compiled AD kernels.
        :rtype: List[Callable[..., Any]]
        """
        kernels: List[Callable[..., Any]] = list()
        color_index: int = 0

        while color_index < self._n_colors:
            active_columns: Set[int] = set(self._color_groups[color_index])
            kernel_name: str = (
                f"structural_compiled_ad_color_{self._method.name}_{self._n_rows}_{self._n_cols}_{color_index}"
            )
            py_func: Callable[..., Any]
            signature_tpe: Any
            compiled_kernel: Callable[..., Any]

            py_func, signature_tpe = self._compiler.compile_ad_kernel(
                equations=self._equations,
                func_name=kernel_name,
                use_cse=use_cse,
                active_indices=active_columns,
            )
            compiled_kernel = _safe_njit(py_func, signature_tpe=signature_tpe, fastmath=True, cache=True)
            kernels.append(compiled_kernel)

            color_index += 1

        return kernels

    def evaluate(
            self,
            states: Vec,
            params: Vec,
            history: Vec,
            d_history: Vec,
            h: float,
            history2: Vec,
    ) -> csc_matrix:
        """
        Evaluate the sparse Jacobian into the reusable CSC storage.

        :param states: Current Newton iterate.
        :type states: Vec
        :param params: Full parameter vector.
        :type params: Vec
        :param history: Previous state vector.
        :type history: Vec
        :param d_history: Previous differential vector.
        :type d_history: Vec
        :param h: Local time step.
        :type h: float
        :param history2: Secondary history vector.
        :type history2: Vec
        :return: Reused CSC Jacobian matrix.
        :rtype: csc_matrix
        """
        self._master_dispatcher(
            states,
            self._seed_buffer,
            params,
            history,
            d_history,
            h,
            history2,
            self._data_buffer,
            self._color_ptr,
            self._col_ptr,
            self._row_idx,
            self._data_idx,
            self._jvp_work_buffer,
        )
        return self._jacobian_matrix

    def get_data_buffer(self) -> Vec:
        """
        Return the reusable CSC numeric buffer.

        :return: CSC numeric buffer.
        :rtype: Vec
        """
        return self._data_buffer

    def get_matrix(self) -> csc_matrix:
        """
        Return the reusable CSC matrix shell.

        :return: CSC Jacobian matrix.
        :rtype: csc_matrix
        """
        return self._jacobian_matrix

    def get_build_stats(self) -> Dict[str, float]:
        """
        Return sparse Jacobian build timings.

        :return: Sparse Jacobian build timings.
        :rtype: Dict[str, float]
        """
        return dict(self._build_stats)


class StructuralCompiledSolver:
    """
    Standalone structural EMT solver with eager kernels and reusable buffers.

    The solver keeps the linear algebra in SciPy, but it removes the Python-side
    allocation churn from residual assembly and sparse Jacobian evaluation.
    """

    __slots__ = [
        "_problem",
        "_t0",
        "_t_end",
        "_h",
        "_method",
        "_pred_method",
        "_dense_threshold",
        "_verbose",
        "_state_vars",
        "_algebraic_vars",
        "_diff_vars",
        "_state_eqs",
        "_algebraic_eqs",
        "_sorted_vars",
        "_event_parameters",
        "_constant_parameters",
        "_parameter_values",
        "_uid2idx_vars",
        "_n_state",
        "_n_vars",
        "_n_diff",
        "_n_event_parameters",
        "_n_constant_parameters",
        "_residual_assembler",
        "_jacobian_evaluator",
        "_residual_buffer",
        "_linear_rhs_buffer",
        "_jacobian_data_buffer",
        "_static_parameter_buffer",
        "_full_parameter_buffer",
        "_vectorized_ready",
        "_last_sim_loop_time",
        "_predictor",
        "_backend_build_stats",
    ]

    def __init__(
            self,
            problem: EmtProblemTemplate,
            t0: float,
            t_end: float,
            h: float,
            method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
            pred_method: DynamicIntegrationMethod | None = None,
            dense_threshold: int = 100,
            verbose: bool = False,
            auto_build: bool = True,
    ) -> None:
        """
        Create the structural compiled EMT solver.

        :param problem: EMT problem wrapper.
        :type problem: EmtProblemTemplate
        :param t0: Initial time.
        :type t0: float
        :param t_end: End time.
        :type t_end: float
        :param h: Nominal time step.
        :type h: float
        :param method: Implicit integration method.
        :type method: DynamicIntegrationMethod
        :param pred_method: Predictor method used on the first trapezoidal step.
        :type pred_method: DynamicIntegrationMethod | None
        :param dense_threshold: Threshold to switch between dense and sparse linear algebra.
        :type dense_threshold: int
        :param verbose: Whether to print build and simulation timings.
        :type verbose: bool
        :param auto_build: Whether to build the vectorized backend during construction.
        :type auto_build: bool
        :return: None
        :rtype: None
        """
        self._problem = problem
        self._t0 = t0
        self._t_end = t_end
        self._h = h
        self._method = method
        self._pred_method = pred_method
        self._dense_threshold = dense_threshold
        self._verbose = verbose

        # The solver captures the problem structure once so all hot loops use local buffers only.
        self._state_vars = self._problem.get_state_vars()
        self._algebraic_vars = self._problem.get_algebraic_vars()
        self._diff_vars = self._problem.get_diff_vars()
        self._state_eqs = self._problem.get_state_eqs()
        self._algebraic_eqs = self._problem.get_algebraic_eqs()
        self._sorted_vars = list()
        self._sorted_vars.extend(self._state_vars)
        self._sorted_vars.extend(self._algebraic_vars)

        self._event_parameters = self._problem.get_variable_parameters()
        self._constant_parameters = self._problem.get_constant_parameters()
        self._parameter_values = self._problem.get_parameters_values()

        self._uid2idx_vars = dict()
        self._n_state = len(self._state_vars)
        self._n_vars = len(self._sorted_vars)
        self._n_diff = len(self._diff_vars)
        self._n_event_parameters = len(self._event_parameters)
        self._n_constant_parameters = len(self._constant_parameters)

        variable_index: int = 0
        while variable_index < self._n_vars:
            variable_obj: Var = self._sorted_vars[variable_index]
            self._uid2idx_vars[variable_obj.uid] = variable_index
            variable_index += 1

        # The residual and right-hand-side buffers are persistent across all Newton iterations.
        self._residual_buffer = np.zeros(self._n_vars, dtype=np.float64)
        self._linear_rhs_buffer = np.zeros(self._n_vars, dtype=np.float64)
        self._jacobian_data_buffer = np.zeros(0, dtype=np.float64)

        # Constant parameters are flattened once because they never change during simulation.
        self._static_parameter_buffer = np.zeros(self._n_constant_parameters, dtype=np.float64)
        variable_index = 0
        while variable_index < self._n_constant_parameters:
            self._static_parameter_buffer[variable_index] = float(self._parameter_values[variable_index].value)
            variable_index += 1

        # The full parameter vector is reused and refreshed in place at every local substep.
        self._full_parameter_buffer = np.zeros(
            self._n_event_parameters + self._n_constant_parameters,
            dtype=np.float64,
        )

        self._residual_assembler: StructuralCompiledResidualAssembler | None = None
        self._jacobian_evaluator: StructuralCompiledSparseADJacobian | None = None
        self._vectorized_ready = False
        self._last_sim_loop_time = 0.0
        self._predictor = StructuralCompiledPredictor(self._n_state)
        self._backend_build_stats: Dict[str, float] = dict()

        if auto_build:
            self._build_vectorized_backend(method)
        else:
            pass

    def _build_vectorized_backend(self, method: DynamicIntegrationMethod) -> None:
        """
        Analyze the symbolic structure and build the eager numerical backend.

        :param method: Integration method used by the generated kernels.
        :type method: DynamicIntegrationMethod
        :return: None
        :rtype: None
        """
        t_start: float = time.perf_counter()
        groups: Dict[str, StructuralCompiledEquationGroup] = dict()
        runtime_uids: Set[int] = set(self._uid2idx_vars.keys())
        parameter_uids: Set[int] = _build_parameter_uid_set(self._event_parameters, self._constant_parameters)
        full_eqs: List[Expr] = _build_full_residual_equations(
            self._state_vars,
            self._state_eqs,
            self._algebraic_eqs,
        )
        equation_index: int = 0

        t_grouping_start: float = time.perf_counter()

        # Structural grouping uses the full canonical string as the lookup key to avoid hash collisions.
        while equation_index < len(full_eqs):
            equation: Expr = full_eqs[equation_index]
            signature_str: str
            runtime_vars: List[Var]
            group: StructuralCompiledEquationGroup
            variable_indices: List[int] = list()
            runtime_var_index: int = 0

            signature_str, runtime_vars = canonicalize_expression(equation, runtime_uids, parameter_uids)

            if signature_str in groups:
                group = groups[signature_str]
            else:
                group = StructuralCompiledEquationGroup()
                groups[signature_str] = group

            while runtime_var_index < len(runtime_vars):
                runtime_uid: int = _get_runtime_uid(runtime_vars[runtime_var_index])
                mapped_index: int | None = self._uid2idx_vars.get(runtime_uid, None)

                if mapped_index is None:
                    raise RuntimeError(f"Missing runtime variable mapping for uid={runtime_uid}")
                else:
                    variable_indices.append(mapped_index)

                runtime_var_index += 1

            if group.get_template_eq() is None:
                group.set_template(equation, runtime_vars)
            else:
                template_vars: List[Var] | None = group.get_template_vars()

                if template_vars is None:
                    raise RuntimeError("Internal structural group without template variables")
                else:
                    if len(template_vars) == len(variable_indices):
                        pass
                    else:
                        raise RuntimeError("Inconsistent runtime variable count inside structural group")

            group.add_indices(variable_indices, equation_index)
            equation_index += 1

        grouping_s: float = time.perf_counter() - t_grouping_start

        if self._verbose:
            print(f"--- [STRUCT-COMPILED] Detected {len(groups)} structural groups ---")
        else:
            pass

        all_parameters: List[Var] = list()
        all_parameters.extend(self._event_parameters)
        all_parameters.extend(self._constant_parameters)
        eager_compiler: EagerEquationCompiler = EagerEquationCompiler(
            variables=self._sorted_vars,
            parameters=all_parameters,
            method=method,
        )

        # Group kernels are compiled in deterministic order so disk cache keys remain stable.
        group_keys: List[str] = sorted(list(groups.keys()))
        backend_cache_token: str = _build_backend_cache_token(method, len(full_eqs), self._n_vars, group_keys)
        kernel_specs: List[StructuralCompiledVectorKernel] = list()
        group_key_index: int = 0

        t_vec_kernel_compile_start: float = time.perf_counter()

        while group_key_index < len(group_keys):
            group_key: str = group_keys[group_key_index]
            group_hash: str = hashlib.md5(group_key.encode("utf-8")).hexdigest()[:16]
            group: StructuralCompiledEquationGroup = groups[group_key]
            template_eq: Expr | None = group.get_template_eq()
            template_vars: List[Var] | None = group.get_template_vars()

            if template_eq is None or template_vars is None:
                raise RuntimeError("Invalid structural group without template information")
            else:
                pass

            kernel_name: str = f"structural_compiled_vec_{method.name}_{group_hash}"
            py_func: Callable[..., Any]
            signature_tpe: Any
            compiled_kernel: Callable[..., Any]
            indices: Int32Matrix = np.asarray(group.get_index_matrix(), dtype=np.int32)
            target_rows: Int32Vector = np.asarray(group.get_row_indices(), dtype=np.int32)

            py_func, signature_tpe = eager_compiler.compile_matrix_kernel(
                template_eq=template_eq,
                func_name=kernel_name,
                template_vars=template_vars,
            )
            compiled_kernel = _safe_njit(py_func, signature_tpe=signature_tpe, fastmath=True, cache=True)
            kernel_specs.append(StructuralCompiledVectorKernel(compiled_kernel, indices, target_rows))

            group_key_index += 1

        vec_kernel_compile_s: float = time.perf_counter() - t_vec_kernel_compile_start

        # The residual assembler owns the reusable grouped work buffers.
        t_residual_assembler_start: float = time.perf_counter()
        self._residual_assembler = StructuralCompiledResidualAssembler(kernel_specs, backend_cache_token)
        residual_assembler_s: float = time.perf_counter() - t_residual_assembler_start

        # The sparse Jacobian evaluator owns the reusable CSC numeric storage.
        t_jacobian_evaluator_start: float = time.perf_counter()
        self._jacobian_evaluator = StructuralCompiledSparseADJacobian(
            equations=full_eqs,
            variables=self._sorted_vars,
            parameters=all_parameters,
            method=method,
            dtype=np.float64,
            use_cse=True,
            cache_token=backend_cache_token,
        )
        jacobian_evaluator_s: float = time.perf_counter() - t_jacobian_evaluator_start
        self._jacobian_data_buffer = self._jacobian_evaluator.get_data_buffer()
        self._vectorized_ready = True

        residual_stats: Dict[str, float] = self._residual_assembler.get_build_stats()
        jacobian_stats: Dict[str, float] = self._jacobian_evaluator.get_build_stats()
        self._backend_build_stats = {
            "grouping_s": grouping_s,
            "vec_kernel_compile_s": vec_kernel_compile_s,
            "residual_assembler_s": residual_assembler_s,
            "residual_dispatcher_s": residual_stats.get("dispatcher_build_s", 0.0),
            "residual_buffer_alloc_s": residual_stats.get("buffer_alloc_s", 0.0),
            "jacobian_evaluator_s": jacobian_evaluator_s,
            "jac_column_rows_s": jacobian_stats.get("column_rows_s", 0.0),
            "jac_csc_shell_s": jacobian_stats.get("csc_shell_s", 0.0),
            "jac_coloring_s": jacobian_stats.get("coloring_s", 0.0),
            "jac_scatter_map_s": jacobian_stats.get("scatter_map_s", 0.0),
            "jac_ad_kernels_s": jacobian_stats.get("ad_kernels_s", 0.0),
            "jac_dispatcher_s": jacobian_stats.get("dispatcher_build_s", 0.0),
            "total_s": time.perf_counter() - t_start,
        }

        if self._verbose:
            elapsed: float = self._backend_build_stats["total_s"]
            print(f"--- [STRUCT-COMPILED] Backend ready in {elapsed:.4f}s ---")
        else:
            pass

    def get_last_sim_loop_time(self) -> float:
        """
        Return the last measured integration loop wall time.

        :return: Last measured loop time.
        :rtype: float
        """
        return self._last_sim_loop_time

    def is_vectorized_ready(self) -> bool:
        """
        Return whether the eager backend has already been built.

        :return: ``True`` when the backend is ready.
        :rtype: bool
        """
        return self._vectorized_ready

    def get_residual_buffer(self) -> Vec:
        """
        Return the persistent residual buffer.

        :return: Persistent residual buffer.
        :rtype: Vec
        """
        return self._residual_buffer

    def get_jacobian_data_buffer(self) -> Vec:
        """
        Return the persistent CSC numeric buffer.

        :return: Persistent CSC numeric buffer.
        :rtype: Vec
        """
        return self._jacobian_data_buffer

    def get_backend_build_stats(self) -> Dict[str, float]:
        """
        Return setup timings for the structural compiled backend build.

        :return: Setup timings grouped by build phase.
        :rtype: Dict[str, float]
        """
        return dict(self._backend_build_stats)

    def simulate(
            self,
            x0: Vec | None = None,
            dx0: Vec | None = None,
            params0: Vec | None = None,
            boundary_updater: StructuralCompiledBoundaryUpdateWrapper | None = None,
    ) -> Tuple[Vec, Mat, Mat]:
        """
        Run the implicit EMT simulation with eager structural kernels.

        :param x0: Optional initial state vector.
        :type x0: Vec | None
        :param dx0: Optional initial differential vector.
        :type dx0: Vec | None
        :param params0: Optional initial runtime parameters.
        :type params0: Vec | None
        :param boundary_updater: Optional boundary updater.
        :type boundary_updater: StructuralCompiledBoundaryUpdateWrapper | None
        :return: Time vector, state trajectory and differential trajectory.
        :rtype: Tuple[Vec, Mat, Mat]
        """
        if self._vectorized_ready:
            pass
        else:
            self._build_vectorized_backend(self._method)

        if self._residual_assembler is None or self._jacobian_evaluator is None:
            raise RuntimeError("Structural compiled backend was not built correctly")
        else:
            pass

        steps: int = int(np.ceil((self._t_end - self._t0) / self._h))
        t: Vec = self._t0 + self._h * np.arange(steps + 1, dtype=np.float64)
        y: Mat = np.zeros((steps + 1, self._n_vars), dtype=np.float64)
        dy: Mat = np.zeros((steps + 1, self._n_diff), dtype=np.float64)

        if x0 is None:
            x_prev: Vec = self._problem.get_x0().copy()
        else:
            x_prev = np.array(x0, dtype=np.float64, copy=True)

        if dx0 is None:
            dx_prev: Vec = self._problem.get_dx0().copy()
        else:
            dx_prev = np.array(dx0, dtype=np.float64, copy=True)

        x_prev2: Vec = x_prev.copy()
        x_iter: Vec = x_prev.copy()

        if params0 is None:
            runtime_params: Vec = np.zeros(self._n_event_parameters, dtype=np.float64)
        else:
            runtime_params = np.array(params0, dtype=np.float64, copy=True)

        y[0, :] = x_prev
        dy[0, :] = dx_prev

        full_params: Vec = self._full_parameter_buffer
        full_params[:] = 0.0

        if self._n_event_parameters > 0:
            full_params[:self._n_event_parameters] = self._problem.def_event_params_fn(runtime_params, float(self._t0))
        else:
            pass

        if self._n_constant_parameters > 0:
            full_params[self._n_event_parameters:] = self._static_parameter_buffer
        else:
            pass

        if boundary_updater is None:
            pass
        else:
            boundary_updater.update(float(self._t0), x_prev, full_params)

        if self._n_event_parameters > 0:
            runtime_params[:] = full_params[:self._n_event_parameters]
        else:
            pass

        use_dense_solver: bool = self._n_vars <= self._dense_threshold

        # Warm up the eager kernels once so the integration loop sees only machine-code execution.
        self._residual_assembler.evaluate(x_prev, full_params, x_prev, dx_prev, self._h, x_prev2, self._residual_buffer)
        self._jacobian_evaluator.evaluate(x_prev, full_params, x_prev, dx_prev, self._h, x_prev2)

        loop_start: float = time.time()

        if self._verbose:
            print("-> StructuralCompiled simulation started")
        else:
            pass

        step_index: int = 0
        while step_index < steps:
            t_step_start: float = float(t[step_index])
            t_step_target: float = float(t[step_index + 1])
            t_local_prev: float = t_step_start
            is_first_local_step: bool = True

            while t_local_prev < (t_step_target - 1e-15):
                forced_event_time: float | None

                if boundary_updater is None:
                    forced_event_time = None
                else:
                    forced_event_time = boundary_updater.get_next_forced_event_time(
                        t_prev=float(t_local_prev),
                        t_target=float(t_step_target),
                    )

                if forced_event_time is None:
                    t_curr: float = t_step_target
                else:
                    t_curr = min(float(forced_event_time), t_step_target)

                    if t_curr <= t_local_prev + 1e-15:
                        t_curr = t_step_target
                    else:
                        pass

                is_aligned_substep: bool = t_curr < (t_step_target - 1e-15)

                if self._method == DynamicIntegrationMethod.DaeBDF2 and is_aligned_substep:
                    raise NotImplementedError(
                        "force_step_alignment is not implemented for DaeBDF2 in StructuralCompiledSolver"
                    )
                else:
                    pass

                h_eff: float = float(t_curr - t_local_prev)

                # Runtime parameters are refreshed before every Newton solve because events may move them.
                if self._n_event_parameters > 0:
                    full_params[:self._n_event_parameters] = self._problem.def_event_params_fn(runtime_params, float(t_curr))
                else:
                    pass

                if boundary_updater is None:
                    pass
                else:
                    boundary_updater.update(float(t_curr), x_prev, full_params)

                if self._n_event_parameters > 0:
                    runtime_params[:] = full_params[:self._n_event_parameters]
                else:
                    pass

                x_iter[:] = x_prev
                last_res_norm: float = 1.0
                cached_lu_dense: Tuple[np.ndarray, np.ndarray] | None = None
                cached_lu_sparse: SuperLU | None = None

                # The first trapezoidal step benefits from a cheap explicit predictor.
                if step_index == 0 and is_first_local_step and self._method == DynamicIntegrationMethod.DaeTrapezoidal:
                    self._predictor.predict(x_iter, x_prev, dx_prev, h_eff, self._pred_method)
                else:
                    pass

                newton_index: int = 0
                while newton_index < 15:
                    # Residual assembly is fully in-place and reuses the grouped work buffers.
                    self._residual_assembler.evaluate(
                        x_iter,
                        full_params,
                        x_prev,
                        dx_prev,
                        h_eff,
                        x_prev2,
                        self._residual_buffer,
                    )
                    res_norm: float = _max_abs_value(self._residual_buffer)

                    if res_norm < 1e-6:
                        break
                    else:
                        pass

                    recompute_factorization: bool = (
                        (cached_lu_dense is None and cached_lu_sparse is None)
                        or (newton_index > 0 and (res_norm / (last_res_norm + 1e-16)) > 0.5)
                    )

                    if recompute_factorization:
                        # The Jacobian numeric values are written directly into CSC storage.
                        cached_jacobian: csc_matrix = self._jacobian_evaluator.evaluate(
                            x_iter,
                            full_params,
                            x_prev,
                            dx_prev,
                            h_eff,
                            x_prev2,
                        )

                        if use_dense_solver:
                            cached_lu_dense = lu_factor(cached_jacobian.toarray())
                            cached_lu_sparse = None
                        else:
                            cached_lu_sparse = splu(cached_jacobian)
                            cached_lu_dense = None
                    else:
                        pass

                    # The right-hand side is also written in place to avoid creating -res arrays.
                    _copy_negated_vector(self._residual_buffer, self._linear_rhs_buffer)

                    if use_dense_solver:
                        if cached_lu_dense is None:
                            delta: Vec = np.zeros(self._n_vars, dtype=np.float64)
                        else:
                            delta = lu_solve(cached_lu_dense, self._linear_rhs_buffer)
                    else:
                        if cached_lu_sparse is None:
                            delta = np.zeros(self._n_vars, dtype=np.float64)
                        else:
                            delta = cached_lu_sparse.solve(self._linear_rhs_buffer)

                    x_iter += delta
                    last_res_norm = res_norm
                    newton_index += 1

                # Differential history is updated according to the selected integration rule.
                if self._method == DynamicIntegrationMethod.DaeTrapezoidal:
                    dx_prev[:self._n_state] = (
                        (2.0 / h_eff) * (x_iter[:self._n_state] - x_prev[:self._n_state])
                        - dx_prev[:self._n_state]
                    )
                elif self._method == DynamicIntegrationMethod.DaeBDF2:
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

                if self._method == DynamicIntegrationMethod.DaeBDF2:
                    pass
                else:
                    x_prev2[:] = x_prev

                x_prev[:] = x_iter
                t_local_prev = t_curr
                is_first_local_step = False

            y[step_index + 1, :] = x_prev
            dy[step_index + 1, :] = dx_prev
            step_index += 1

        self._last_sim_loop_time = time.time() - loop_start

        if self._verbose:
            print(f"-> StructuralCompiled simulation finished in {self._last_sim_loop_time:.4f}s")
        else:
            pass

        return t, y, dy
