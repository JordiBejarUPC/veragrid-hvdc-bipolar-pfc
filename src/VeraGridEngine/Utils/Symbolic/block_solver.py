# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Any, Callable, Dict, List, Sequence, Tuple
from collections import defaultdict
import numpy as np
import uuid
import numba as nb
import math
import scipy.sparse as sp
import concurrent.futures
import time
from scipy.sparse.linalg import gmres
from scipy.sparse import csc_matrix
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, DiffVar, Const, Expr,
                                                    expression2numba, heaviside_num, get_expression_vars)
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Utils.Sparse.csc import pack_4_by_4_scipy
from VeraGridEngine.basic_structures import Vec, IntVec


def _tic():
    return time.perf_counter()


def _toc(t0):
    return time.perf_counter() - t0


# -----------------------------------------------------------------------------
# UUID helper
# -----------------------------------------------------------------------------

def compile_jac_block(block_id, block_eqs, block_offsets, used_vars_count,
                      compiler_names_dict, alias_names_dict, namespace, VARS_NAME: str, DIFF_NAME: str,
                      EVENT_PARAMS_NAME: str,
                      PARAMS_NAME: str, ALTER_PARAMS_NAME: str, use_jit):
    fname = f"jac_block_{block_id}"
    src = f"def {fname}({VARS_NAME}, {DIFF_NAME}, {EVENT_PARAMS_NAME}, {PARAMS_NAME}, {ALTER_PARAMS_NAME}, out):\n"
    final_names_dict = {}
    for uid, count in used_vars_count.items():
        if count > 1:
            final_names_dict[uid] = alias_names_dict[uid]
            src += f"    {alias_names_dict[uid]} = {compiler_names_dict[uid]}\n"
        else:
            final_names_dict[uid] = compiler_names_dict[uid]

    offset = block_offsets[block_id]
    for i, e in enumerate(block_eqs):
        src += f"    out[{offset + i}] = {expression2numba(e.simplify(), final_names_dict)}\n"

    exec(src, namespace)

    if use_jit:
        func = nb.njit(
            nb.void(nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:]),
            fastmath=True,
            cache=False
        )(namespace[fname])
    else:
        func = namespace[fname]

    return block_id, func


class SymbolicJacobian:
    """
       Class to store and evaluate a symbolic jacobian
       """

    def __init__(self,
                 eqs: list,
                 variables: list,
                 diff_variables: list,
                 compiler_names_dict: dict,
                 alias_names_dict: dict,
                 VARS_NAME: str,
                 DIFF_NAME: str,
                 EVENT_PARAMS_NAME: str,
                 PARAMS_NAME: str,
                 ALTER_PARAMS_NAME: str,
                 uid2idx_vars: dict,
                 dt=None,
                 use_jit=True,
                 batch_size=500,
                 n_jobs=4):  # número de threads para compilación paralela

        """
                JIT‑compile a sparse Jacobian evaluator for *equations* w.r.t *variables*.
                :param eqs: Array of equations
                :param variables: Array of variables to differentiate against
                :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
                :param uid2sym_params:
                :param use_jit: if true, the function is compiled by numba
                :return:
                        jac_fn : callable(values: np.ndarray, params: np.ndarray) -> scipy.sparse.csc_matrix
                            Fast evaluator in which *values* is a 1‑D NumPy vector of length
                            ``len(variables)``and *params* is a 1‑D NumPy vector of length
                            ``len(parameters)``
                        sparsity_pattern : tuple(np.ndarray, np.ndarray)
                            Row/col indices of structurally non‑zero entries.
                """
        if dt is None:
            dt = Const(0.001)

        # --- Build triplets and count variable usage ---------------------------------
        used_vars_count = defaultdict(int)
        triplets = []

        for row, eq in enumerate(eqs):
            for col, var in enumerate(variables):
                d_expression = eq.diff(var, dt=dt)
                if not (isinstance(d_expression, Const) and d_expression.value == 0):
                    triplets.append((col, row, d_expression))
                for v in get_expression_vars(d_expression):
                    used_vars_count[v.uid] += 1

        triplets.sort(key=lambda t: (t[0], t[1]))
        cols_sorted, rows_sorted, equations_sorted = zip(*triplets) if triplets else ([], [], [])

        # --- Assemble sparse CSC Jacobian structure ---------------------------------
        nnz = len(cols_sorted)
        indices = np.fromiter(rows_sorted, dtype=np.int32, count=nnz)
        indptr = np.zeros(len(variables) + 1, dtype=np.int32)
        for c in cols_sorted:
            indptr[c + 1] += 1
        np.cumsum(indptr, out=indptr)

        self.nvar = len(variables)
        neq = len(eqs)
        self.J = sp.csc_matrix((np.zeros(nnz), indices, indptr), shape=(neq, self.nvar))

        # --- Batch compilation ------------------------------------------------------
        self.namespace: Dict[str, Any] = {
            "math": math,
            "np": np,
            "nb": nb,
            "_heaviside": _heaviside,
        }

        blocks = [
            equations_sorted[i:i + batch_size]
            for i in range(0, len(equations_sorted), batch_size)
        ]
        self.block_offsets = [i for i in range(0, len(equations_sorted), batch_size)]
        self.funcs: List[Callable[[Vec, Vec, Vec, Vec, Vec, Vec], None] | None] = [None] * len(blocks)

        # --- Compile blocks sequentially -------------------------------------------
        # --- Compile blocks in parallel ---------------------------------------------
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_jobs) as executor:
            futures = [
                executor.submit(
                    compile_jac_block,
                    i, block, self.block_offsets, used_vars_count,
                    compiler_names_dict, alias_names_dict,
                    self.namespace, VARS_NAME, DIFF_NAME, EVENT_PARAMS_NAME, PARAMS_NAME, ALTER_PARAMS_NAME, use_jit
                )
                for i, block in enumerate(blocks)
            ]
            for f in concurrent.futures.as_completed(futures):
                block_id, func = f.result()
                self.funcs[block_id] = func

    def __call__(self,
                 x: Vec,
                 dx: Vec,
                 variable_params: Vec,
                 constant_params: Vec,
                 alter_params: Vec,
                 h: float):
        """

        :param x:
        :param dx:
        :param variable_params:
        :param constant_params:
        :param alter_params:
        :param h:
        :return:
        """
        for func in self.funcs:
            if func is not None:
                func(x, dx, variable_params, constant_params, alter_params, self.J.data)
        return self.J


class SymbolicVector:
    """
    SymbolicFunction
    """

    def __init__(self, eqs: Sequence[Expr],
                 compiler_names_dict: Dict[int, str],
                 alias_names_dict: Dict[int, str],
                 VARS_NAME: str,
                 DIFF_NAME: str,
                 EVENT_PARAMS_NAME: str,
                 PARAMS_NAME: str,
                 ALTER_PARAMS_NAME: str,
                 use_jit: bool = True):
        """
        Compile the array of expressions to a function that returns an array of values for those expressions
        :param eqs: Iterable of expressions (Expr)
        :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
        :param uid2sym_params:
        :return: Function pointer that returns an array
        """
        self.func: Callable[[Vec, Vec, Vec, Vec, Vec, Vec], None] | None = None
        used_vars_count = defaultdict(int)
        for eq in eqs:
            for var in get_expression_vars(eq):
                used_vars_count[var.uid] += 1
                if var.uid not in compiler_names_dict.keys():
                    print()
                if var.uid not in alias_names_dict.keys():
                    print()

        if len(eqs):
            self.namespace: Dict[str, Any] = {
                "math": math,
                "np": np,
                "nb": nb,
                "_heaviside": _heaviside,
            }

            fname = f"func"  # since we compile into a namespace, there won't be repeated names

            # Build source
            src = f"def {fname}({VARS_NAME}, {DIFF_NAME}, {EVENT_PARAMS_NAME}, {PARAMS_NAME}, {ALTER_PARAMS_NAME}, out):\n"
            final_names_dict = compiler_names_dict.copy()
            for uid, count in used_vars_count.items():
                if count > 1:
                    final_names_dict[uid] = alias_names_dict[uid]
                    src += f"    {alias_names_dict[uid]} = {compiler_names_dict[uid]}\n"
            src += "\n".join(
                [f"    out[{i}] = {expression2numba(e.simplify(), final_names_dict)}" for i, e in
                 enumerate(eqs)]) + "\n"

            # compile in python namespace
            exec(src, self.namespace)

            # compile in numba
            if use_jit:
                self.func = nb.njit(
                    nb.void(nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:]),
                    fastmath=True)(self.namespace[fname])
            else:
                self.func = self.namespace[fname]
        else:
            self.func = None

        self.data: Vec = np.zeros(len(eqs))

    def __call__(self, values: Vec, diff_values: Vec, event_params: Vec, params: Vec, alter_params: Vec) -> Vec:
        """
        Call the compiled function
        :param values:
        :param diff_values:
        :param event_params:
        :param params:
        :return:
        """
        if self.func is not None:
            self.func(values, diff_values, event_params, params, alter_params, self.data)
        return self.data


class SymbolicParamsVector:
    """
    SymbolicFunction
    """

    def __init__(self, eqs: Sequence[Expr],
                 compiler_names_dict: Dict[int, str],
                 alias_names_dict: Dict[int, str],
                 EVENT_PARAMS_NAME: str,
                 TIME_NAME: str,
                 use_jit: bool = True):
        """
        Compile the array of expressions to a function that returns an array of values for those expressions
        :param eqs: Iterable of expressions (Expr)
        :param uid2sym_t: dictionary relating the uid of a var with its array name (i.e. var[0])
        :return: Function pointer that returns an array
        """
        self.func: Callable[[Vec, float, Vec], None] | None = None
        used_vars_count = defaultdict(int)
        for eq in eqs:
            for var in get_expression_vars(eq):
                used_vars_count[var.uid] += 1

        if len(eqs):
            self.namespace: Dict[str, Any] = {
                "math": math,
                "np": np,
                "nb": nb,
                "_heaviside": _heaviside,
            }

            fname = f"func"  # since we compile into a namespace, there won't be repeated names

            # Build source
            src = f"def {fname}({EVENT_PARAMS_NAME}, {TIME_NAME}, out):\n"
            final_names_dict = compiler_names_dict.copy()
            for uid, count in used_vars_count.items():
                if count > 1:
                    final_names_dict[uid] = alias_names_dict[uid]
                    src += f"    {alias_names_dict[uid]} = {compiler_names_dict[uid]}\n"
            src += "\n".join(
                [f"    out[{i}] = {expression2numba(e, compiler_names_dict)}" for i, e in enumerate(eqs)]) + "\n"

            # compile in python namespace
            exec(src, self.namespace)

            # compile in numba
            if use_jit:
                self.func = nb.njit(nb.void(nb.float64[:], nb.float64, nb.float64[:]),
                                    fastmath=True)(self.namespace[fname])
            else:
                self.func = self.namespace[fname]
        else:
            self.func = None

        self.data = np.zeros(len(eqs))

    def __call__(self, event_params: Vec, glob_time: float) -> Vec:
        """
        Call the compiled function
        :param glob_time:
        :return:
        """
        if self.func is not None:
            self.func(event_params, glob_time, self.data)
        return self.data


class SymbolicDerivative:
    """
    SymbolicFunction
    """

    def __init__(self,
                 vars: Sequence[Var],
                 uid2idx_vars: Dict[int, int],
                 diff_vars: Sequence[DiffVar],
                 compiler_names_dict: Dict[int, str],
                 use_jit: bool = True):
        self.func: Callable[[Vec, Vec, Vec, float, Vec], Vec] | None = None

        self.data: Vec = np.zeros(len(diff_vars))
        self.index_map: IntVec = np.zeros(len(diff_vars), dtype=np.int32)

        self.namespace: Dict[str, Any] = {
            "math": math,
            "np": np,
            "nb": nb,
            "_heaviside": _heaviside,
        }
        fname = f"func"  # since we compile into a namespace, there won't be repeated names
        # Build source
        uid2dx_expression = {}
        # TODO: order diff vars by order
        src = f"def {fname}(vars, lagvars, lagdx, h, out):\n"
        for i, diff_var in enumerate(diff_vars):
            base_var_uid = diff_var.base_var.uid
            uid = diff_var.uid
            if diff_var.diff_order == 1:
                j = uid2idx_vars[base_var_uid]
                rhs = f" (vars[{j}] - lagvars[{j}]) / h\n"
            else:
                dx_expression = uid2dx_expression[diff_var.base_var.uid]
                rhs = f" ({dx_expression}- lagdx[{i}]) / h\n"
            to_src = f"    out[{i}] = {rhs}\n"
            uid2dx_expression[uid] = rhs

            src += to_src
        src += f"    return out"
        exec(src, self.namespace)

        # compile in python namespace
        # compile in numba
        if use_jit:
            self.func = nb.njit(nb.float64[:](nb.float64[:], nb.float64[:], nb.float64[:], nb.float64, nb.float64[:]),
                                fastmath=True)(self.namespace[fname])
        else:
            self.func = self.namespace[fname]

    def __call__(self, x: Vec, xn: Vec, dx: Vec, h: float) -> Vec:
        """
        Call the compiled function
        :param x:
        :param xn:
        :param dx:
        :param h:
        :return:
        """
        if self.func is not None:
            self.func(x, xn, dx, h, self.data)
        return self.data


def _new_uid() -> int:
    """Generate a fresh UUID‑v4 string."""
    return uuid.uuid4().int


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars:
        if name == var.name:
            return var

    for block_child in block.children:
        result = find_name_in_block(name, block_child)
        if result is not None:  # found in a child
            return result

    return None


def pack_blocks_scipy(blocks: dict, n_batches: int):
    """
    Pack an n_batches x n_batches dict of sparse submatrices into one big csc_matrix.
    blocks[(i,j)] = submatrix
    """
    # row blocks per i
    row_blocks = []
    # print(blocks.keys())
    for i in range(n_batches):
        col_blocks = [blocks[i, j] for j in range(n_batches)]
        row_blocks.append(sp.hstack(col_blocks, format="csc"))
    return sp.vstack(row_blocks, format="csc")


def delete_vars_from_block(block: Block, deleted_vars: List[Var]):
    deleted_vars_uid = set(var.uid for var in deleted_vars)
    for b in block.get_all_blocks():
        algebraic_vars_copy = b.algebraic_vars.copy()
        b.algebraic_vars = []
        for var in algebraic_vars_copy:
            if var.uid not in deleted_vars_uid:
                b.algebraic_vars.append(var)
            else:
                # print(f'Deleting var {var.name} from block {b.name}')
                _ = 0


class SolverError(Exception):
    """Base class for all solver-related errors."""
    pass


class ConvergenceError(SolverError):
    """Raised when solver fails to converge within max iterations."""
    pass


class SingularJacobianError(SolverError):
    """Raised when Jacobian is singular or ill-conditioned."""
    pass


class NaNError(SolverError):
    """Raised when NaNs or Infs appear in the solution."""
    pass


class BlockSolver:

    def __init__(self, block_system: Block, glob_time: Var, use_jit: bool = True):
        """
        Constructor
        :param block_system: BlockSystem
        """
        self.block_system: Block = block_system

        # Flatten the block lists, preserving declaration order
        self._algebraic_vars: List[Var] = list()
        self._algebraic_eqs: List[Expr] = list()
        self._algebraic_eqs_substituted: List[Expr] = list()
        self._state_vars: List[Var] = list()
        self._state_eqs: List[Expr] = list()
        self._state_eqs_substituted: List[Expr] = list()
        self._diff_vars: List[DiffVar] = list()
        self._differential_eqs: List[Expr] = list()
        self._reformulated_vars: List[Var] = list()
        self._event_parameters: List[Var] = list()
        self._event_parameters_eqs: List[Expr] = list()
        self._parameters: List[Var] = list()
        self._parameters_values: List[Const] = list()
        self._alter_params: List[Var] = list()
        self._stability_eqs: List[Expr] = list()

        # Class-level registry
        self._registry: Dict[int, DiffVar] = dict()  # int uuid , DiffVar
        self._absolute_registry: Dict[Tuple[int, int], DiffVar] = dict()

        self.v_glob_name2uid = block_system.vars_glob_name2uid
        self.glob_time: Var = glob_time
        self.substitute = True

        for b in self.block_system.get_all_blocks():
            self._algebraic_vars.extend(b.algebraic_vars)
            self._algebraic_eqs.extend(b.algebraic_eqs)
            self._state_vars.extend(b.state_vars)
            self._state_eqs.extend(b.state_eqs)
            self._alter_params.extend(b.alter_params)
            for param, eq in b.event_dict.items():
                self._event_parameters.append(param)
                self._event_parameters_eqs.append(eq)
            for param, constant in b._parameters.items():
                self._parameters.append(param)
                self._parameters_values.append(constant)

            # if isinstance(b, DiffBlock):
            self._diff_vars.extend(b.diff_vars)
            # self._lag_vars.extend(b.lag_vars)
            # self._differential_eqs.extend(b.differential_eqs)
            # self._reformulated_vars.extend(b.reformulated_vars)

        self._diff_vars = sorted(self._diff_vars, key=lambda dv: dv.diff_order)
        self._state_algeb_vars = self._state_vars + self._algebraic_vars
        self._state_eqs_substituted = self._state_eqs.copy()

        # We define the parameter dt and delta
        self.dt = Var(name='dt')
        self.delta = Var(name='delta')
        self._event_parameters.append(self.dt)
        self._event_parameters.append(self.delta)
        self._event_parameters_eqs.append(Const(1e-3))
        self._event_parameters_eqs.append(Const(1))

        self._n_state = len(self._state_vars)
        self._n_alg = len(self._algebraic_vars)
        self._n_vars = self._n_state + self._n_alg
        self._n_event_params = len(self._event_parameters)
        self._n_params = len(self._parameters)
        self._n_diff = len(self._diff_vars)
        self.n_algebraic = len(self._algebraic_eqs)
        self._n_alter_params = len(self._alter_params)

        # generate the in-code names for each variable
        # inside the compiled functions the variables are
        # going to be represented by an array called vars[]

        self.compiler_names_dict: Dict[int, str] = dict()
        self.alias_names_dict: Dict[int, str] = dict()
        # self.uid2sym_event_params: Dict[int, str] = dict()
        # self.uid2sym_params: Dict[int, str] = dict()
        # self.uid2sym_diff: Dict[int, str] = dict()
        # self.uid2sym_t: Dict[int, str] = dict()
        self.uid2idx_vars: Dict[int, int] = dict()
        self.uid2idx_event_params: Dict[int, int] = dict()
        self.uid2idx_params: Dict[int, int] = dict()
        self.uid2idx_alter_params: Dict[int, int] = dict()
        self.uid2idx_diff: Dict[int, int] = dict()
        # self.uid2idx_lag: Dict[int, int] = dict()
        self.uid2idx_t: Dict[int, int] = dict()

        self.VARS_NAME = "vars"
        self.EVENT_PARAMS_NAME = "event_params"
        self.PARAMS_NAME = "params"
        self.DIFF_NAME = "diff"
        self.ALTER_PARAMS_NAME = "alter"
        self.TIME_NAME = "glob_time"

        i = 0
        for v in self._state_vars:
            self.compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self.alias_names_dict[v.uid] = f"{self.VARS_NAME}{i}"
            self.uid2idx_vars[v.uid] = i
            i += 1

        for v in self._algebraic_vars:
            self.compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self.alias_names_dict[v.uid] = f"{self.VARS_NAME}{i}"
            self.uid2idx_vars[v.uid] = i
            i += 1

        j = 0
        for j, ep in enumerate(self._parameters):
            self.compiler_names_dict[ep.uid] = f"{self.PARAMS_NAME}[{j}]"
            self.alias_names_dict[ep.uid] = f"{self.PARAMS_NAME}{j}"
            self.uid2idx_params[ep.uid] = j
            j += 1

        l = 0
        for j, ep in enumerate(self._alter_params):
            self.compiler_names_dict[ep.uid] = f"{self.ALTER_PARAMS_NAME}[{j}]"
            self.alias_names_dict[ep.uid] = f"{self.ALTER_PARAMS_NAME}{j}"
            self.uid2idx_alter_params[ep.uid] = l
            l += 1

        l = 0
        for l, ep in enumerate(self._event_parameters):
            self.compiler_names_dict[ep.uid] = f"{self.EVENT_PARAMS_NAME}[{l}]"
            self.alias_names_dict[ep.uid] = f"{self.EVENT_PARAMS_NAME}{l}"
            self.uid2idx_event_params[ep.uid] = l
            l += 1

        k = 0
        for ep in self._diff_vars:
            self.compiler_names_dict[ep.uid] = f"{self.DIFF_NAME}[{k}]"
            self.alias_names_dict[ep.uid] = f"{self.DIFF_NAME}{k}"
            self.uid2idx_diff[ep.uid] = k
            k += 1

        k = 0
        self.compiler_names_dict[self.glob_time.uid] = f"{self.TIME_NAME}"
        self.uid2idx_t[self.glob_time.uid] = k

        for it, eq in enumerate(self._event_parameters_eqs):
            if isinstance(eq, Const) and eq.value is None:
                raise Exception(f' Event parameter {self._event_parameters[it]} has None Value')

        # define parameters
        self.alpha = 1
        alpha = self.alpha
        lag_can_be_0 = False  # TODO: will this allways be False??
        if lag_can_be_0:
            lag_init = 0
        else:
            lag_init = 1

        # Substitute in state eqs

        # Substitute in algebraic eqs
        self._stability_eqs = list()
        self._algebraic_eqs_substituted = self._algebraic_eqs.copy() + self._differential_eqs.copy()

        # fill stability equations by putting algebraic equations equal zero
        for it, eq in enumerate(self._algebraic_eqs):
            for diff_var in self._diff_vars:
                eq = eq.subs({diff_var: Const(0)})
                eq = eq.simplify()
            self._stability_eqs.append(eq)

        i = len(self.uid2idx_vars)
        l = 0
        # Compile RHS and Jacobian

        """
                   state Var   algeb var  
        state eq |J11        | J12       |    | ∆ state var|    | ∆ state eq |
                 |           |           |    |            |    |            |
                 ------------------------- x  |------------|  = |------------|
        algeb eq |J21        | J22       |    | ∆ algeb var|    | ∆ algeb eq |
                 |           |           |    |            |    |            |
        """
        timings = dict()

        print("Compiling...")

        t0 = _tic()
        self._derivative_fn = SymbolicDerivative(
            vars=self._state_algeb_vars,
            uid2idx_vars=self.uid2idx_vars,
            diff_vars=self._diff_vars,
            compiler_names_dict=self.compiler_names_dict
        )
        timings["SymbolicDerivative"] = _toc(t0)

        t0 = _tic()
        self._rhs_algeb_fn = SymbolicVector(
            eqs=self._algebraic_eqs,
            compiler_names_dict=self.compiler_names_dict,
            alias_names_dict=self.alias_names_dict,
            VARS_NAME=self.VARS_NAME,
            EVENT_PARAMS_NAME=self.EVENT_PARAMS_NAME,
            PARAMS_NAME=self.PARAMS_NAME,
            DIFF_NAME=self.DIFF_NAME,
            ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
        )
        timings["RHS algebraic"] = _toc(t0)

        t0 = _tic()
        self._event_params_fn = SymbolicParamsVector(
            eqs=self._event_parameters_eqs,
            compiler_names_dict=self.compiler_names_dict,
            alias_names_dict=self.alias_names_dict,
            EVENT_PARAMS_NAME=self.EVENT_PARAMS_NAME,
            TIME_NAME=self.TIME_NAME,
        )
        timings["Event parameters"] = _toc(t0)

        if len(self._state_eqs) != 0:

            t0 = _tic()
            self._rhs_state_fn = SymbolicVector(
                eqs=self._state_eqs,
                compiler_names_dict=self.compiler_names_dict,
                alias_names_dict=self.alias_names_dict,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.EVENT_PARAMS_NAME,
                PARAMS_NAME=self.PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
            )
            timings["RHS state"] = _toc(t0)

            t0 = _tic()
            self._j11_fn = SymbolicJacobian(
                eqs=self._state_eqs,
                variables=self._state_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self.compiler_names_dict,
                alias_names_dict=self.alias_names_dict,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.EVENT_PARAMS_NAME,
                PARAMS_NAME=self.PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
                uid2idx_vars=self.uid2idx_vars,

                dt=self.dt
            )
            timings["J11 (dF/dx)"] = _toc(t0)

            t0 = _tic()
            self._j12_fn = SymbolicJacobian(
                eqs=self._state_eqs,
                variables=self._algebraic_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self.compiler_names_dict,
                alias_names_dict=self.alias_names_dict,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.EVENT_PARAMS_NAME,
                PARAMS_NAME=self.PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
                uid2idx_vars=self.uid2idx_vars,
                dt=self.dt
            )
            timings["J12 (dF/dy)"] = _toc(t0)

            t0 = _tic()
            self._j21_fn = SymbolicJacobian(
                eqs=self._algebraic_eqs,
                variables=self._state_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self.compiler_names_dict,
                alias_names_dict=self.alias_names_dict,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.EVENT_PARAMS_NAME,
                PARAMS_NAME=self.PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
                uid2idx_vars=self.uid2idx_vars,
                dt=self.dt
            )
            timings["J21 (dG/dx)"] = _toc(t0)

            t0 = _tic()
            self._j22_fn = SymbolicJacobian(
                eqs=self._algebraic_eqs,
                variables=self._algebraic_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self.compiler_names_dict,
                alias_names_dict=self.alias_names_dict,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.EVENT_PARAMS_NAME,
                PARAMS_NAME=self.PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
                uid2idx_vars=self.uid2idx_vars,
                dt=self.dt
            )
            timings["J22 (dG/dy)"] = _toc(t0)

        else:
            t0 = _tic()
            self._j22_fn = SymbolicJacobian(
                eqs=self._algebraic_eqs,
                variables=self._algebraic_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self.compiler_names_dict,
                alias_names_dict=self.alias_names_dict,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.EVENT_PARAMS_NAME,
                PARAMS_NAME=self.PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
                uid2idx_vars=self.uid2idx_vars,
                dt=self.dt
            )
            timings["J22 only (no states)"] = _toc(t0)

        print(
            f"Model compiled with {self._n_vars} variables, "
            f"{len(self._algebraic_eqs_substituted)} algebraic eqs and "
            f"{len(self._state_eqs_substituted)} state eqs"
        )

        print("\nCompilation timing summary:")
        for k, v in timings.items():
            print(f"  {k:30s}: {v:8.4f} s")

        print(f"\nTotal compile time: {sum(timings.values()):.4f} s")

    @property
    def diff_vars_number(self):
        return len(self._diff_vars)

    @property
    def state_vars(self):
        return self._state_vars

    @property
    def algebraic_vars(self):
        return self._algebraic_vars

    @property
    def diff_vars(self):
        return self._diff_vars

    def get_var_idx(self, v: Var) -> int:
        """

        :param v:
        :return:
        """
        return self.uid2idx_vars[v.uid]

    def get_vars_idx(self, variables: Sequence[Var]) -> np.ndarray:
        """

        :param variables:
        :return:
        """
        return np.array([self.uid2idx_vars[v.uid] for v in variables])

    def rhs_pseudo_transient(self, x: Vec, xn: Vec, dx: Vec, event_params: Vec, params: Vec, alter_params: Vec,
                             sim_step, h: float) -> Vec:
        # returns algeb rhs is there is no states, is there is states, returns states and algebs rhs

        """
        Return 𝑑x/dt given the current *state* vector.
        :param x: get the right-hand-side give a state vector
        :param xn:
        :param dx:
        :param event_params:
        :param params: params array
        :param alter_params:
        :param sim_step: simulation step
        :param h: simulation step
        :return [f_state_update, f_algeb]
        """
        event_params[-2] = 1e50

        f_algeb = self._rhs_algeb_fn(x, 0 * dx, event_params, params, alter_params)
        sim_step = sim_step
        if self._n_state > 0:
            f_state = self._rhs_state_fn(x, dx, event_params, params, alter_params)
            f_state_update = (x[:self._n_state] - xn[:self._n_state]) / h - f_state
            return np.r_[f_state_update, f_algeb]

        else:
            return f_algeb

    def rhs_implicit(self, x: Vec, dx: Vec, xn: Vec, event_params: Vec, params: Vec, alter_params: Vec, sim_step,
                     h: float) -> Vec:
        """
        Return 𝑑x/dt given the current *state* vector.
        :param x: get the right-hand-side give a state vector
        :param xn:
        :param event_params:
        :param params: params array
        :param alter_params:
        :param sim_step: simulation step
        :param h: simulation step
        :return [f_state_update, f_algeb]
        """
        f_algeb = self._rhs_algeb_fn(x, dx, event_params, params, alter_params)

        if self._n_state > 0:
            f_state = self._rhs_state_fn(x, dx, event_params, params, alter_params)
            f_state_update = x[:self._n_state] - xn[:self._n_state] - h * f_state
            return np.r_[f_state_update, f_algeb]

        else:
            return f_algeb

    def rhs_fixed(self, x: Vec, dx: Vec, event_params: np.ndarray, params: Vec, alter_params: Vec) -> np.ndarray:
        """
        Return 𝑑x/dt given the current *state* vector.
        :param event_params:
        :param params:
        :param alter_params:
        :param x: get the right-hand-side give a state vector
        :return [f_state_update, f_algeb]
        """
        f_algeb = np.array(self._rhs_algeb_fn(x, dx, event_params, params, alter_params))

        if self._n_state > 0:
            f_state = np.array(self._rhs_state_fn(x, dx, event_params, params, alter_params))
            return np.r_[f_state, f_algeb]
        else:
            return f_algeb

    def jacobian_implicit(self, x: Vec, dx: Vec, event_params: Vec, params: Vec, alter_params: Vec,
                          h: float) -> sp.csc_matrix:
        """
        :param x: vector or variables' values
        :param dx: vector of diff values
        :param event_params:
        :param params: params array
        :param alter_params:
        :param h: step
        :return:

        Parameters
        ----------
        alter_params :
        """

        """
                  state Var    algeb var
        state eq |I - h * J11 | - h* J12  |    | ∆ state var|    | ∆ state eq |
                 |            |           |    |            |    |            |
                 -------------------------- x  |------------|  = |------------|
        algeb eq |J21         | J22       |    | ∆ algeb var|    | ∆ algeb eq |
                 |            |           |    |            |    |            |
        """

        # returns only j22 if no states, returns J if states
        event_params[-2] = h
        if len(self._state_eqs) == 0:
            j22: sp.csc_matrix = self._j22_fn(x, dx, event_params, params, alter_params, h)
            return j22

        j11_val: csc_matrix = self._j11_fn(x, dx, event_params, params, alter_params, h)
        j12_val: csc_matrix = self._j12_fn(x, dx, event_params, params, alter_params, h)
        j21_val: csc_matrix = self._j21_fn(x, dx, event_params, params, alter_params, h)
        j22_val: csc_matrix = self._j22_fn(x, dx, event_params, params, alter_params, h)

        I = sp.eye(m=self._n_state, n=self._n_state)
        j11: sp.csc_matrix = (I - h * j11_val).tocsc()
        j12: sp.csc_matrix = - h * j12_val
        j21: sp.csc_matrix = j21_val
        j22: sp.csc_matrix = j22_val

        J = pack_4_by_4_scipy(j11, j12, j21, j22)

        return J

    #### initialization

    def jacobian_pseudo_transient(self, x: Vec, dx: Vec, event_params: Vec, params: Vec, alter_params: Vec,
                                  h: float) -> sp.csc_matrix:
        """
        #We want to build an equivalent of the following Jacobian:
                J11 = delta^-1 * I + Jf
        """
        # Now we have J = -delta^-1 * I - Jf so we need to multiply J by -1.
        J = self.jacobian_implicit(x, dx, event_params, params, alter_params, h)

        return J

    def build_init_alter_params_vector(self, mapping: dict[Any, Const]) -> np.ndarray:
        """
        Helper function to build the initial vector
        :alter_param mapping: var->initial value mapping
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(self._n_alter_params)

        for uid, val in mapping.items():
            i = self.uid2idx_alter_params[uid]  # uid
            x[i] = val.value

        return x

    def build_init_vars_vector_from_uid(self, mapping: dict[tuple[int, str], float]) -> Vec:
        """
        Helper function to build the initial vector
        :param mapping: var->initial value mapping
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._state_vars) + len(self._algebraic_vars))

        for key, val in mapping.items():
            uid, name = key
            if uid in self.uid2idx_vars.keys():
                i = self.uid2idx_vars[uid]
                x[i] = val
            else:
                raise ValueError(f"Missing uid {key} definition")

        return x

    def sort_vars_from_uid(self, mapping: dict[tuple[int, str], float]) -> Vec:
        """
        Helper function to build the initial vector
        :param mapping: var->initial value mapping
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._state_vars) + len(self._algebraic_vars), dtype=object)

        for key, val in mapping.items():
            uid, name = key
            i = self.uid2idx_vars[uid]
            x[i] = uid

        return x

    def sort_vars(self, mapping: dict[Var, float]) -> Vec:
        """
        Helper function to build the initial vector
        :param mapping: var->initial value mapping
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._state_vars) + len(self._algebraic_vars), dtype=object)

        for key, val in mapping.items():
            i = self.uid2idx_vars[key.uid]
            x[i] = key

        return x

    def build_init_diffvars_vector(self, mapping: dict[Var, float]) -> Vec:
        """
        Helper function to build the initial vector
        :param mapping: var->initial value mapping
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._diff_vars))

        for key, val in mapping.items():
            if key.uid in self.uid2idx_diff.keys():
                i = self.uid2idx_diff[key.uid]
                x[i] = val
            else:
                raise ValueError(f"Missing variable {key} definition")

        return x

    def build_initial_guess(self, x0: Vec, dx0: Vec, h) -> Vec:
        res = x0.copy()
        for diff_var in self._diff_vars:
            if diff_var.diff_order > 1:
                continue
            uid = diff_var.base_var.uid
            idx = self.uid2idx_vars[uid]
            diff_idx = self.uid2idx_diff[diff_var.uid]
            res[idx] += h * dx0[diff_idx]
        return res

    def simulate(self,
                 t0: float,
                 t_end: float,
                 h: float,
                 x0: Vec,
                 dx0: Vec,
                 method: DynamicIntegrationMethod = DynamicIntegrationMethod.RungeKutta4,
                 newton_tol: float = 1e-8,
                 alter_params: Vec | None = None,
                 newton_max_iter: int = 1000,
                 followed_vars=None,
                 initialized=False,
                 verbose=False):
        """
        :param t0: start time
        :param t_end: end time
        :param h: step
        :param x0: initial values
        :param dx0
        :param method: method
        :param newton_tol:
        :param alter_params:
        :param newton_max_iter:
        :param followed_vars:
        :param initialized:
        :param verbose:
        :return: 1D time array, 2D array of simulated variables
        """

        if alter_params is None:
            alter_params = np.zeros(len(self._alter_params))

        if initialized:
            x0 = x0[:self._n_alg]
        else:
            x0 = x0

        if method == DynamicIntegrationMethod.BackEuler:
            return self._simulate_implicit_euler_diff(
                t0=t0, t_end=t_end, h=h, x0=x0, dx0=dx0, alter_params=alter_params,
                max_iter=newton_max_iter, verbose=verbose,
                followed_vars=followed_vars,
            )

        else:
            raise ValueError(f"Unknown method '{method}'")

    def _simulate_implicit_euler_diff(self, t0: float, t_end: float, h: float, x0: Vec, dx0: Vec,
                                      alter_params: Vec | None,
                                      max_iter=1e6, verbose=False, followed_vars=None):
        """
        :param t0:
        :param t_end:
        :param h:
        :param x0:
        :params_matrix:
        :param max_iter:
        :return:
        """

        init_time = time.time()
        steady_state = np.allclose(dx0, 0.0, atol=1e-12)
        max_iter_0 = max_iter
        steps = int(np.ceil((t_end - t0) / h))
        t = np.empty(steps + 1)
        y = np.empty((steps + 1, self._n_vars))
        self.y = y
        self.t = t

        # timing accumulators
        timings = {
            "jacobian_time": 0.0,
            "rhs_time": 0.0,
            "lag_update_time": 0.0,
            "linear_solver_time": 0.0,
            "initial_step_time": 0.0,
        }

        params_current = self._event_params_fn(np.ones(len(self._event_parameters)), float(0.0))
        params_current = self._event_params_fn(params_current, float(0.0))
        t[0] = t0
        y[0] = x0.copy()
        dx = dx0.copy()
        dx_last = dx0.copy()
        x_new = x0.copy()
        for step_idx in range(steps):
            self.step_idx = step_idx
            params_previous = params_current.copy()
            discontinuity = False
            converged = False
            n_iter = 0
            current_time = t[step_idx]

            params_current = self._event_params_fn(params_current, float(current_time))
            params_current[-2] = h
            params = np.array([const.value for const in self._parameters_values])

            if step_idx == 0:
                tol = 1e-7
                xn = x0.copy()
                initial_step_start = time.time()
            else:
                xn = y[step_idx]
                tol = 1e-7
            residual = None
            while not converged and n_iter < 1e5:
                if step_idx == 0:
                    dx = dx0.copy()
                else:
                    dx = self._derivative_fn(x_new, xn, dx_last, h)

                # ---------------- lag update ----------------
                lag_update_start = time.time()
                lag_update_end = time.time()
                timings["lag_update_time"] += lag_update_end - lag_update_start
                # ------------------------------------------------

                if discontinuity:
                    tol = 1e-8
                    max_iter = 5e5

                params_current = np.asarray(params_current, dtype=np.float64)
                # ---------------- rhs calculation ----------------
                rhs_start = time.time()
                rhs = self.rhs_implicit(x_new, dx, xn, params_current, params, alter_params, step_idx + 1, h)
                # print(rhs)
                rhs_end = time.time()
                timings["rhs_time"] += rhs_end - rhs_start
                # -------------------------------------------------

                # recompute Jacobian for next iteration
                jac_start = time.time()
                # Jf = self.jacobian_implicit(xnew_lags, params_current, h)
                jac_end = time.time()
                if step_idx == 0:
                    _ = 0
                    # print(f'jacobian time is {(jac_end - jac_start)}')
                timings["jacobian_time"] += jac_end - jac_start

                residual = np.linalg.norm(rhs, np.inf)
                converged = residual < tol
                Jf = self.jacobian_implicit(x_new, dx, params_current, params, alter_params, h)

                if step_idx == 0:
                    Jf = self.jacobian_implicit(x_new, dx, params_current, params, alter_params, h)
                    delta = sp.linalg.spsolve(Jf, -rhs)
                    if converged:
                        print("System well initialized.")
                        print(f"x is {x_new}")
                    else:
                        print(f"System bad initialized. DAE resiudal is {residual}.")
                        print(f'rhs is {rhs}')
                        non_zero_indexes = np.where(np.abs(rhs) > 1e-7)[0]
                        all_eq = self._state_eqs + self._algebraic_eqs
                        print("eqs are")
                        for i in non_zero_indexes:
                            eq = all_eq[i]
                            print(f"eq {eq} with error {rhs[i]}")
                        exit()
                else:
                    max_iter = max_iter_0

                if converged:
                    break

                solved = False
                linear_start = time.time()
                delta = sp.linalg.spsolve(Jf, -rhs)
                linear_end = time.time()
                timings["linear_solver_time"] += linear_end - linear_start
                solved = np.all(np.isfinite(delta))

                if not solved:
                    delta, *_ = sp.linalg.lsqr(Jf, -rhs)
                    solved = np.all(np.isfinite(delta))
                    u, s, vh = np.linalg.svd(Jf.toarray() if sp.issparse(Jf) else Jf)
                    singular_dirs = np.where(s < tol)[0]
                    for i in singular_dirs:
                        v = vh.T[:, i]  # variable-space vector
                        abs_v = np.abs(v)
                        dominant_idx = np.argsort(abs_v)[::-1][:5]  # top 5 vars
                        print(f"\nSingular direction {i}, σ={s[i]:.3e}")
                        for j in dominant_idx:
                            if j < len(self._algebraic_vars):
                                var_name = self._algebraic_vars[j].name
                                print(f"  {var_name:20s} {v[j]:+.3e}")
                    print("Using LSQR")

                if not solved:
                    nan_indices = np.where(np.isnan(rhs))[0]
                    # nan_indices = np.where(np.abs(rhs) > 1e-2)[0]
                    nan_eqs = [self._algebraic_eqs[i] for i in nan_indices]
                    print(f'Jf is {Jf}')
                    raise ValueError(
                        f"spsolve returned non-finite values (NaN or Inf).\n"
                        f"delta = {delta}\n"
                        f"rhs = {rhs}\n"
                        f"Jacobian shape = {Jf.shape}\n"
                        f"NaNs found at indices {nan_indices.tolist()} in equations:\n{nan_eqs}",
                    )

                if not solved:
                    raise RuntimeError("Failed to solve linear system even with regularization.")

                x_new += delta
                n_iter += 1

            if converged:
                if step_idx == 0:
                    initial_step_end = time.time()
                    timings['initial_step_time'] = initial_step_end - initial_step_end
                    print(f'diff residual is {np.linalg.norm(x0[:self._n_alg] - x_new[:self._n_alg])}')
                lag_update_start = time.time()
                print(f'converged is {converged} at step {step_idx} and iter {n_iter}')

                if verbose:
                    _ = 0

                if discontinuity:
                    _ = 0
                    y[step_idx + 1] = x_new
                else:
                    y[step_idx + 1] = x_new
                t[step_idx + 1] = t[step_idx] + h

                dx_last = dx.copy()
                lag_update_end = time.time()
                timings["lag_update_time"] += lag_update_end - lag_update_start

            else:
                print(f"Failed to converge at step {step_idx} and n_iter is {n_iter}")
                print(f'Residual is {residual}')
                break

        return t, y, timings