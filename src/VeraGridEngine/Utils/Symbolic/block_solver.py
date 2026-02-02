# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Any, Callable, Dict, List, Sequence, Tuple, Set, Literal
from collections import defaultdict
import numpy as np
import uuid
import numba as nb
import math
import scipy.sparse as sp
import concurrent.futures
import time
import matplotlib.pyplot as plt
from scipy.sparse import csc_matrix

from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver_no_diff import _compile_equations
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, LagVar, DiffVar, Const, Expr, cos, sin,
                                                    expression2numba, _heaviside)
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, SimulationBackend
from VeraGridEngine.Utils.Sparse.csc import pack_4_by_4_scipy
from VeraGridEngine.basic_structures import Vec, IntVec
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler

from VeraGridEngine.Utils.Symbolic.diagnostic import (with_newton_diagnostics, NewtonDiagnosticsConfig,
                                                      NewtonSolveContext, dense_lstsq_fallback,
                                                      sparse_lsqr_fallback)


def _tic():
    return time.perf_counter()


def _toc(t0):
    return time.perf_counter() - t0


# -----------------------------------------------------------------------------
# UUID helper
# -----------------------------------------------------------------------------

def compile_jac_block(block_id, block_eqs, block_offsets, used_vars_count,
                      compiler_names_dict, alias_names_dict, namespace, use_jit):
    fname = f"jac_block_{block_id}"
    src = f"def {fname}(vars, diff, event_params, params, out):\n"
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
            nb.void(nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:]),
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
                for v in d_expression.get_vars():
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
        self.funcs: List[Callable[[Vec, Vec, Vec, Vec, Vec], None] | None] = [None] * len(blocks)

        # --- Compile blocks in parallel ---------------------------------------------
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_jobs) as executor:
            futures = [
                executor.submit(
                    compile_jac_block,
                    i, block, self.block_offsets, used_vars_count,
                    compiler_names_dict, alias_names_dict,
                    self.namespace, use_jit
                )
                for i, block in enumerate(blocks)
            ]
            for f in concurrent.futures.as_completed(futures):
                block_id, func = f.result()
                self.funcs[block_id] = func

    def __call__(self, x: Vec, dx: Vec, variable_params: Vec, constant_params: Vec, h: float):
        variable_params[-2] = h
        for func in self.funcs:
            if func is not None:
                func(x, dx, variable_params, constant_params, self.J.data)
        return self.J


class SymbolicVector:
    """
    SymbolicFunction
    """

    def __init__(self, eqs: Sequence[Expr],
                 compiler_names_dict: Dict[int, str],
                 alias_names_dict: Dict[int, str],
                 use_jit: bool = True):
        """
        Compile the array of expressions to a function that returns an array of values for those expressions
        :param eqs: Iterable of expressions (Expr)
        :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
        :param uid2sym_params:
        :return: Function pointer that returns an array
        """
        self.func: Callable[[Vec, Vec, Vec, Vec, Vec], None] | None = None
        used_vars_count = defaultdict(int)
        for eq in eqs:
            for var in eq.get_vars():
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
            src = f"def {fname}(vars, diff, event_params, params, out):\n"
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
                self.func = nb.njit(nb.void(nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:]),
                                    fastmath=True)(self.namespace[fname])
            else:
                self.func = self.namespace[fname]
        else:
            self.func = None

        self.data: Vec = np.zeros(len(eqs))

    def __call__(self, values: Vec, diff_values: Vec, event_params: Vec, params: Vec) -> Vec:
        """
        Call the compiled function
        :param values:
        :param diff_values:
        :param event_params:
        :param params:
        :return:
        """
        if self.func is not None:
            self.func(values, diff_values, event_params, params, self.data)
        return self.data


class SymbolicParamsVector:
    """
    SymbolicFunction
    """

    def __init__(self, eqs: Sequence[Expr],
                 compiler_names_dict: Dict[int, str],
                 alias_names_dict: Dict[int, str],
                 use_jit: bool = True):
        """
        Compile the array of expressions to a function that returns an array of values for those expressions
        :param eqs: Iterable of expressions (Expr)
        :param uid2sym_t: dictionary relating the uid of a var with its array name (i.e. var[0])
        :return: Function pointer that returns an array
        """
        self.func: Callable[[Vec, Vec], csc_matrix] | None = None
        used_vars_count = defaultdict(int)
        for eq in eqs:
            for var in eq.get_vars():
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
            src = f"def {fname}(event_params, glob_time, out):\n"
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
        self.func: Callable[[Vec, Vec], None] | None = None
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
        self._stability_eqs: List[Expr] = list()

        # Class-level registry
        self._registry: Dict[int, DiffVar] = dict()  # int uuid , DiffVar
        self._absolute_registry: Dict[Tuple[int, int], DiffVar] = dict()

        self.v_glob_name2uid = block_system.vars_glob_name2uid
        self.glob_time: Var = glob_time
        self.substitute = True

        # Numerical trace
        self.newton_trace_collector = None
        self.backend = SimulationBackend.SymbolicImplicit

        for b in self.block_system.get_all_blocks():
            self._algebraic_vars.extend(b.algebraic_vars)
            self._algebraic_eqs.extend(b.algebraic_eqs)
            self._state_vars.extend(b.state_vars)
            self._state_eqs.extend(b.state_eqs)
            for param, eq in b.event_dict.items():
                self._event_parameters.append(param)
                self._event_parameters_eqs.append(eq)
            for param, constant in b.parameters.items():
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
        self._n_algebraic = len(self._algebraic_eqs)

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
        self.uid2idx_diff: Dict[int, int] = dict()
        # self.uid2idx_lag: Dict[int, int] = dict()
        self.uid2idx_t: Dict[int, int] = dict()

        i = 0
        for v in self._state_vars:
            self.compiler_names_dict[v.uid] = f"vars[{i}]"
            self.alias_names_dict[v.uid] = f"vars_{i}"
            self.uid2idx_vars[v.uid] = i
            i += 1

        for v in self._algebraic_vars:
            self.compiler_names_dict[v.uid] = f"vars[{i}]"
            self.alias_names_dict[v.uid] = f"vars_{i}"
            self.uid2idx_vars[v.uid] = i
            i += 1

        j = 0
        for j, ep in enumerate(self._parameters):
            self.compiler_names_dict[ep.uid] = f"params[{j}]"
            self.alias_names_dict[ep.uid] = f"params_{j}"
            self.uid2idx_params[ep.uid] = j
            j += 1

        l = 0
        for l, ep in enumerate(self._event_parameters):
            self.compiler_names_dict[ep.uid] = f"event_params[{l}]"
            self.alias_names_dict[ep.uid] = f"event_params_{l}"
            self.uid2idx_event_params[ep.uid] = l
            l += 1

        k = 0
        for ep in self._diff_vars:
            self.compiler_names_dict[ep.uid] = f"diff[{k}]"
            self.alias_names_dict[ep.uid] = f"diff_{k}"
            self.uid2idx_diff[ep.uid] = k
            k += 1

        k = 0
        self.compiler_names_dict[self.glob_time.uid] = f"glob_time"
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
        )
        timings["RHS algebraic"] = _toc(t0)

        t0 = _tic()
        self._event_params_fn = SymbolicParamsVector(
            eqs=self._event_parameters_eqs,
            compiler_names_dict=self.compiler_names_dict,
            alias_names_dict=self.alias_names_dict,
        )
        timings["Event parameters"] = _toc(t0)

        if len(self._state_eqs) != 0:

            t0 = _tic()
            self._rhs_state_fn = SymbolicVector(
                eqs=self._state_eqs,
                compiler_names_dict=self.compiler_names_dict,
                alias_names_dict=self.alias_names_dict,
            )
            timings["RHS state"] = _toc(t0)

            t0 = _tic()
            self._j11_fn = SymbolicJacobian(
                eqs=self._state_eqs,
                variables=self._state_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self.compiler_names_dict,
                alias_names_dict=self.alias_names_dict,
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

    def _get_jacobian(self,
                      eqs: List[Expr],
                      variables: List[Var],
                      uid2sym_vars: Dict[int, str],
                      uid2sym_event_params: Dict[int, str],
                      uid2sym_params: Dict[int, str],
                      dt: Const = Const(0.001),
                      substitute: bool = True,
                      add_delta: bool = True):
        """
        JIT‑compile a sparse Jacobian evaluator for *equations* w.r.t *variables*.
        :param eqs: Array of equations
        :param variables: Array of variables to differentiate against
        :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
        :param uid2sym_params:
        :return:
                jac_fn : callable(values: Vec) -> scipy.sparse.csc_matrix
                    Fast evaluator in which *values* is a 1‑D NumPy vector of length
                    ``len(variables)``.
                sparsity_pattern : tuple(Vec, Vec)
                    Row/col indices of structurally non‑zero entries.
        """

        # Ensure deterministic variable order
        diff_vars = self._diff_vars
        if not substitute:
            _ = 0
            # diff_vars = []
        check_set = set()
        for v in variables:
            if v in check_set:
                raise ValueError(f"Repeated var {v.name} in the variables' list :(")
            else:
                check_set.add(v)

        # Cache compiled partials by UID so duplicates are reused
        fn_cache: Dict[str, Callable] = {}
        triplets: List[Tuple[int, int, Callable]] = []  # (col, row, fn)

        for row, eq in enumerate(eqs):
            for lag_var in self._lag_vars:
                if lag_var.lag == 0:
                    eq = eq.subs({lag_var: lag_var.base_var})

            for col, var in enumerate(variables):
                diff_var = DiffVar(var.name + '_diff', base_var=var)
                # d_expression = eq.diff(var).simplify() + (1/self.dt)*eq.diff(diff_var).simplify()
                d_expression = eq.diff(var).simplify()
                for diff_var in diff_vars:
                    deriv = eq.diff(diff_var)
                    continue
                # We substitute the remaining diff vars in d_expression
                for diff_var in diff_vars:
                    deriv = d_expression.diff(diff_var)
                    if getattr(deriv, 'value', 1) != 0:
                        if not substitute:
                            d_expression = d_expression.subs({diff_var: diff_var / self.delta})
                        else:
                            dx_dt, lag = diff_var.approximation_expr(dt=dt, lag_can_be_0=False)
                            d_expression = d_expression.subs({diff_var: dx_dt / self.delta})
                            new_lag = LagVar(diff_var.origin_var.name + '_lag_' + str(lag),
                                             base_var=diff_var.origin_var, lag=lag)
                            i = len(self.uid2idx_vars)
                            l = len(self.uid2idx_lag)
                            if new_lag not in self._lag_vars_set:
                                uid2sym_vars[new_lag.uid] = f"vars[{i}]"
                                self.uid2idx_vars[new_lag.uid] = i
                                self.uid2idx_lag[new_lag.uid] = l
                                self._lag_vars.append(new_lag)
                                self._lag_vars_set.add(new_lag)
                                i += 1
                                l += 1

                if isinstance(d_expression, Const) and d_expression.value == 0:
                    continue  # structural zero

                triplets.append((col, row, d_expression))
                if not substitute:
                    _ = 0
        # Sort by column, then row for CSC layout
        triplets.sort(key=lambda t: (t[0], t[1]))
        cols_sorted, rows_sorted, equations_sorted = zip(*triplets) if triplets else ([], [], [])
        functions_ptr = _compile_equations(eqs=equations_sorted, uid2sym_vars=uid2sym_vars,
                                           uid2sym_event_params=uid2sym_event_params,
                                           uid2sym_params=uid2sym_params)

        nnz = len(cols_sorted)
        indices = np.fromiter(rows_sorted, dtype=np.int32, count=nnz)

        indptr = np.zeros(len(variables) + 1, dtype=np.int32)
        for c in cols_sorted:
            indptr[c + 1] += 1
        np.cumsum(indptr, out=indptr)

        def jac_fn(values: Vec, event_params: Vec,
                   params: Vec) -> sp.csc_matrix:  # noqa: D401 – simple
            assert len(values) >= len(variables)
            ##print(f'Signtures are {functions_ptr.signatures}')

            jac_values = functions_ptr(values, event_params, params)
            data = np.array(jac_values, dtype=np.float64)

            return sp.csc_matrix((data, indices, indptr), shape=(len(eqs), len(variables)))

        return jac_fn

    def rhs_pseudo_transient(self, x: Vec, xn: Vec, dx: Vec, event_params: Vec, params: Vec,
                             sim_step, h: float) -> Vec:
        # returns algeb rhs is there is no states, is there is states, returns states and algebs rhs

        """
        Return 𝑑x/dt given the current *state* vector.
        :param x: get the right-hand-side give a state vector
        :param xn:
        :param event_params:
        :param params: params array
        :param sim_step: simulation step
        :param h: simulation step
        :return [f_state_update, f_algeb]
        """
        event_params[-2] = 1e50

        f_algeb = self._rhs_algeb_fn(x, 0 * dx, event_params, params)
        sim_step = sim_step
        if self._n_state > 0:
            f_state = self._rhs_state_fn(x, dx, event_params, params)
            f_state_update = (x[:self._n_state] - xn[:self._n_state]) / h - f_state
            return np.r_[f_state_update, f_algeb]

        else:
            return f_algeb

    def rhs_implicit(self, x: Vec, dx: Vec, xn: Vec, event_params: Vec, params: Vec, sim_step, h: float) -> Vec:
        """
        Return 𝑑x/dt given the current *state* vector.
        :param x: get the right-hand-side give a state vector
        :param xn:
        :param event_params:
        :param params: params array
        :param sim_step: simulation step
        :param h: simulation step
        :return [f_state_update, f_algeb]
        """
        f_algeb = self._rhs_algeb_fn(x, dx, event_params, params)

        if self._n_state > 0:
            f_state = self._rhs_state_fn(x, dx, event_params, params)
            f_state_update = x[:self._n_state] - xn[:self._n_state] - h * f_state
            return np.r_[f_state_update, f_algeb]

        else:
            return f_algeb

    def rhs_fixed(self, x: Vec, dx: Vec, event_params: np.ndarray, params: Vec) -> np.ndarray:
        """
        Return 𝑑x/dt given the current *state* vector.
        :param event_params:
        :param params:
        :param x: get the right-hand-side give a state vector
        :return [f_state_update, f_algeb]
        """
        f_algeb = np.array(self._rhs_algeb_fn(x, dx, event_params, params))

        if self._n_state > 0:
            f_state = np.array(self._rhs_state_fn(x, dx, event_params, params))
            return np.r_[f_state, f_algeb]
        else:
            return f_algeb

    def jacobian_implicit(self, x: Vec, dx: Vec, event_params: Vec, params: Vec, h: float) -> sp.csc_matrix:
        """
        :param x: vector or variables' values
        :param dx: vector of diff values
        :param event_params:
        :param params: params array
        :param h: step
        :return:
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
            j22: sp.csc_matrix = self._j22_fn(x, dx, event_params, params, h)
            return j22

        j11_val: csc_matrix = self._j11_fn(x, dx, event_params, params, h)
        j12_val: csc_matrix = self._j12_fn(x, dx, event_params, params, h)
        j21_val: csc_matrix = self._j21_fn(x, dx, event_params, params, h)
        j22_val: csc_matrix = self._j22_fn(x, dx, event_params, params, h)

        I = sp.eye(m=self._n_state, n=self._n_state)
        j11: sp.csc_matrix = (I - h * j11_val).tocsc()
        j12: sp.csc_matrix = - h * j12_val
        j21: sp.csc_matrix = j21_val
        j22: sp.csc_matrix = j22_val

        J = pack_4_by_4_scipy(j11, j12, j21, j22)

        return J

    #### initialization

    def jacobian_pseudo_transient(self, x: Vec, dx: Vec, event_params: Vec, params: Vec,
                                  h: float) -> sp.csc_matrix:
        """
        #We want to build an equivalent of the following Jacobian:
                J11 = delta^-1 * I + Jf
        """
        # Now we have J = -delta^-1 * I - Jf so we need to multiply J by -1.
        J = self.jacobian_implicit(x, dx, event_params, params, h)

        return J

    def build_init_params_vector(self, mapping: dict[Var, float]) -> Vec:
        """
        Helper function to build the initial vector
        :param mapping: var->initial value mapping
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(self._n_params)

        for key, val in mapping.items():
            i = self.uid2idx_event_params[key.uid]

            x[i] = val

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

    def warm_up_start(self):
        dummy_vals = np.zeros(len(self._algebraic_vars) + len(self._state_vars) + len(self._lag_vars), dtype=np.float64)
        dummy_params = np.random.rand(len(self._event_parameters))
        self.jacobian_implicit(dummy_vals, dummy_params, 0.001)  # triggers compilation once
        self._rhs_algeb_fn(dummy_vals, dummy_params)  # triggers compilation once

    def sort_vars(self, mapping: dict[Var, float], permissive: bool = False) -> Vec:
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

    def build_init_lagvars_vector(self, mapping: dict[Var, float]) -> Vec:
        """
        Helper function to build the initial vector
        :param mapping: var->initial value mapping
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._lag_vars))

        for key, val in mapping.items():
            if key.uid in self.uid2idx_vars.keys():
                try:
                    i = self.uid2idx_vars[key.uid]
                    x[i] = val
                except:
                    _ = 0
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

    #################################################################################################
    # (Legacy code) is retained in order to avoid conflicts while testing the unification method.
    # TODO: call of this function in GUI needs to be updated
    def simulate(self,
                 t0: float,
                 t_end: float,
                 h: float,
                 x0: Vec,
                 dx0: Vec,
                 params0: Vec,
                 method: DynamicIntegrationMethod = DynamicIntegrationMethod.RungeKutta4,
                 newton_tol: float = 1e-8,
                 newton_max_iter: int = 1000,
                 followed_vars=None,
                 initialized=False,
                 verbose=False):
        """
        :param params0:
        :param t0: start time
        :param t_end: end time
        :param h: step
        :param x0: initial values
        :param dx0
        :param method: method
        :param newton_tol:
        :param newton_max_iter:
        :param followed_vars:
        :param initialized:
        :param verbose:
        :return: 1D time array, 2D array of simulated variables
        """

        if initialized:
            x0 = x0[:self._n_alg]
        else:
            x0 = x0

        if method == DynamicIntegrationMethod.BackEuler:
            return self._simulate_implicit_euler_diff(
                t0=t0, t_end=t_end, h=h, x0=x0, dx0=dx0, params0=params0,
                max_iter=newton_max_iter, verbose=verbose,
                followed_vars=followed_vars,
            )

        else:
            raise ValueError(f"Unknown method '{method}'")

    # ==============================================================================
    # 1. UNIFIED SIMULATION INTERFACE
    # ==============================================================================

    def simulate_unified(self,
                         t0: float,
                         t_end: float,
                         h: float,
                         x0: Vec,
                         dx0: Vec,
                         params0: Vec,
                         method: DynamicIntegrationMethod = DynamicIntegrationMethod.Trapezoid,
                         boundary_update_fn=None,
                         verbose: bool = False,
                         dense_threshold: int = 100,
                         **kwargs):
        """
        Main simulation entry point. Dispatches the simulation to the appropriate engine
        (Implicit JIT or Explicit Legacy) based on the solver configuration.

        :param t0: Start time of the simulation.
        :param t_end: End time of the simulation.
        :param h: Time step size (fixed).
        :param x0: Initial state vector (includes algebraic variables).
        :param dx0: Initial derivative vector (optional, for implicit methods).
        :param params0: Initial parameters vector (optional).
        :param method: Integration scheme (e.g., Trapezoid, BDF2).
        :param solver_type: Solver engine type (Implicit JIT or Explicit Legacy).
        :param boundary_update_fn: Callback function for boundary/control updates per step.
        :param verbose: If True, prints simulation progress and stats.
        :param dense_threshold: Threshold N. Systems with N <= threshold use dense linear algebra.
        :return: Tuple (time_array, trajectory_array).
        """

        # --- Totally implicit (JIT / EMT) ---
        if self.backend == SimulationBackend.SymbolicImplicit:

            # Implicit-by-design engine
            if method not in {
                DynamicIntegrationMethod.Trapezoid,
                DynamicIntegrationMethod.BDF2,
                DynamicIntegrationMethod.BackEuler
            }:
                raise ValueError(f"Method {method} not supported by totally implicit engine.")

            return self._simulate_jit(
                t0, t_end, h, x0, dx0, params0,
                method_str=method.value,
                boundary_update_fn=boundary_update_fn,
                verbose=verbose,
                dense_threshold=dense_threshold
            )

        elif self.backend == SimulationBackend.LegacyExternal:

            if method not in {
                DynamicIntegrationMethod.Euler,
                DynamicIntegrationMethod.RungeKutta4
            }:
                raise ValueError(f"Method {method} not supported by classic solver.")

            if boundary_update_fn is not None:
                print("Warning: Classic backend ignores boundary_update_fn.")

            return self._simulate_classic(
                t0, t_end, h, x0, dx0, params0,
                method=method,
                verbose=verbose,
                **kwargs
            )

        else:
            raise ValueError(f"Unknown backend: {self.backend}")

    # ==============================================================================
    # 2. JIT IMPLICIT ENGINE
    # ==============================================================================

    def _build_jit_kernel(self, method_str: str):
        """
        Compiles the numerical residual function using the JIT compiler and caches it.
        It maps symbolic variables to the compiled array indices.
        """
        print(f"--- [JIT] Compiling Implicit Kernel ({method_str}) ---")

        if not hasattr(self, 'jit_kernels'):
            self.jit_kernels = {}

        # Use actual variable (Objects) for the compiler mapping
        sorted_vars = self._state_vars + self._algebraic_vars
        all_params = self._event_parameters + self._parameters

        # Build residual equations: DiffVar - RHS = 0
        equations = []
        for i, rhs in enumerate(self._state_eqs):
            sv = self._state_vars[i]
            d_term = DiffVar(name=f"d_{sv.name}", base_var=sv)
            equations.append(d_term - rhs)
        equations.extend(self._algebraic_eqs)

        # Compile and cache
        self.jit_compiler = EquationCompiler(variables=sorted_vars, parameters=all_params, method=method_str)
        kernel = self.jit_compiler.compile(equations, func_name=f"jit_step_{method_str}", use_cse=True)

        self.jit_kernels[method_str] = kernel

    def _simulate_jit(self, t0, t_end, h, x0, dx0, params0, method_str, boundary_update_fn, verbose,
                      dense_threshold):
        """
        Optimized internal simulation loop using JIT-compiled kernels and hybrid linear solvers.
        """

        # 1. Kernel Retrieval
        if not hasattr(self, 'jit_kernels'):
            self.jit_kernels = {}
        if method_str not in self.jit_kernels:
            self._build_jit_kernel(method_str)
        current_kernel = self.jit_kernels[method_str]

        # 2. Linear Solver Strategy Configuration
        use_dense_solver = (self._n_vars <= dense_threshold)

        if verbose:
            mode_str = "DENSE" if use_dense_solver else "SPARSE"
            print(
                f"   [Config] System N={self._n_vars}. Using {mode_str} linear solver (Threshold={dense_threshold}).")

        # 3. Initialization
        steps = int(np.ceil((t_end - t0) / h))
        t = np.linspace(t0, t_end, steps + 1)
        y = np.zeros((steps + 1, self._n_vars))
        y[0] = x0.copy()

        x_prev = x0.copy()
        dx_prev = dx0.copy() if dx0 is not None else np.zeros(self._n_vars)
        x_prev2 = x0.copy()

        static_vals = np.array([c.value for c in self._parameters_values])
        if params0 is not None and len(params0) == len(self._event_parameters):
            ev_params = params0
        else:
            ev_params = np.zeros(len(self._event_parameters))

        # Integration Coefficients
        if method_str == DynamicIntegrationMethod.Trapezoid.value:
            alpha = 2.0 / h
            h_eff = h / 2.0
        elif method_str == DynamicIntegrationMethod.BDF2.value:
            alpha = 1.5 / h
            h_eff = h * (2.0 / 3.0)
        else:
            alpha = 1.0 / h
            h_eff = h

        # Jacobian Scaling Factors
        row_scale = np.ones(self._n_vars)
        row_scale[:self._n_state] = alpha

        row_scaler_dense = None
        row_scaler_sparse = None

        if use_dense_solver:
            row_scaler_dense = row_scale[:, None]  # Broadcasting for dense arrays
        else:
            row_scaler_sparse = sp.diags(row_scale, format='csc')

        x_iter = x0.copy()
        t_start = time.time()

        if verbose:
            print(f"-> Starting JIT Simulation ({method_str}, {steps} steps)...")

        diag_cfg = NewtonDiagnosticsConfig(
            step_norm_explode=1e6,
            dense_cond_warn=1e12,
            compute_dense_cond=True,
            enable_fallback=True,
        )

        dense_solve = with_newton_diagnostics(
            np.linalg.solve,
            fallback_solve=dense_lstsq_fallback,
            collector=self.newton_trace_collector,
            config=diag_cfg,
            solver_name="dense",
        )

        sparse_solve = with_newton_diagnostics(
            sp.linalg.spsolve,
            fallback_solve=sparse_lsqr_fallback,
            collector=self.newton_trace_collector,
            config=diag_cfg,
            solver_name="sparse",
        )

        # 4. Main Time Loop
        for i in range(steps):
            t_curr = t[i + 1]

            # Update dynamic parameters
            ev_params = self._event_params_fn(ev_params, float(t_curr))
            full_params = np.concatenate((ev_params, static_vals))

            # External Control / Boundary Update
            if boundary_update_fn:
                boundary_update_fn(t_curr, x_prev, full_params)

            # Newton-Raphson Iteration
            for k in range(15):
                # Linear Solve (diagnostics wrapper)
                ctx = NewtonSolveContext(
                    t=float(t_curr),
                    step_idx=int(i),
                    newton_iter=int(k),
                    phase="jit",
                    method=str(method_str),
                )
                # Evaluate Residuals (JIT)
                res = current_kernel(x_iter, full_params, x_prev, dx_prev, h, x_prev2)

                res_norm_inf = float(np.linalg.norm(res, np.inf))
                ctx.res_norm_inf = res_norm_inf

                if np.linalg.norm(res, np.inf) < 1e-6:
                    break

                # Jacobian Evaluation
                dx_guess = (x_iter - x_prev) * alpha - dx_prev
                J_base = self.jacobian_implicit(x_iter, dx_guess, ev_params, static_vals, h_eff)

                if use_dense_solver:
                    J_dense = J_base.toarray()
                    J_final = J_dense * row_scaler_dense
                    delta = dense_solve(J_final, -res, ctx)
                else:
                    J_final = row_scaler_sparse @ J_base
                    delta = sparse_solve(J_final, -res, ctx)

                x_iter += delta

            # Update History
            y[i + 1] = x_iter

            if method_str == DynamicIntegrationMethod.Trapezoid.value:
                dx_new = np.zeros_like(dx_prev)
                mask = slice(0, self._n_state)
                dx_new[mask] = alpha * (x_iter[mask] - x_prev[mask]) - dx_prev[mask]
                dx_prev = dx_new
            elif method_str == DynamicIntegrationMethod.BDF2.value:
                x_prev2 = x_prev.copy()

            x_prev = x_iter.copy()

        if verbose:
            print(f"JIT Finished: {time.time() - t_start:.4f}s")
        return t, y

    # ==============================================================================
    # 3. LEGACY ENGINE WRAPPER
    # ==============================================================================

    def _simulate_classic(self, t0, t_end, h, x0, dx0, params0, method, verbose, **kwargs):
        """
        Wrapper for legacy explicit integration methods.
        """
        if method == DynamicIntegrationMethod.Euler:
            return self._simulate_fixed(t0, t_end, h, x0, params0, stepper="euler")

        if method == DynamicIntegrationMethod.RungeKutta4:
            return self._simulate_fixed(t0, t_end, h, x0, params0, stepper="rk4")

        if method == DynamicIntegrationMethod.BackEuler:
            return self._simulate_implicit_euler_diff(
                t0=t0, t_end=t_end, h=h, x0=x0, dx0=dx0, params0=params0,
                max_iter=kwargs.get('newton_max_iter', 1000),
                verbose=verbose,
                followed_vars=kwargs.get('followed_vars', None)
            )

        raise ValueError(f"Legacy method {method} not implemented in _simulate_classic")

    def _simulate_implicit_euler_diff(self, t0: float, t_end: float, h: float, x0: Vec, dx0: Vec, params0: Vec,
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
                rhs = self.rhs_implicit(x_new, dx, xn, params_current, params, step_idx + 1, h)
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
                Jf = self.jacobian_implicit(x_new, dx, params_current, params, h)

                if step_idx == 0:
                    Jf = self.jacobian_implicit(x_new, dx, params_current, params, h)
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

    def _simulate_fixed(self, t0, t_end, h, x0, event_params, stepper="euler"):
        """
        Fixed‑step helpers (Euler, RK‑4)
        :param t0:
        :param t_end:
        :param h:
        :param x0:
        :param stepper:
        :return:
        """
        steps = int(np.ceil((t_end - t0) / h))
        t = np.empty(steps + 1)
        y = np.empty((steps + 1, self._n_vars))
        t[0] = t0
        y[0, :] = x0.copy()
        params = np.array([const.value for const in self._parameters_values])

        for i in range(steps):
            tn = t[i]
            xn = y[i]
            if stepper == "euler":
                k1 = self.rhs_fixed(xn, event_params, params)
                y[i + 1] = xn + h * k1
            elif stepper == "rk4":
                k1 = self.rhs_fixed(xn, event_params, params)
                k2 = self.rhs_fixed(xn + 0.5 * h * k1, event_params, params)
                k3 = self.rhs_fixed(xn + 0.5 * h * k2, event_params, params)
                k4 = self.rhs_fixed(xn + h * k3, event_params, params)
                y[i + 1] = xn + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
            else:
                raise RuntimeError("unknown stepper")
            t[i + 1] = tn + h
        return t, y

    def compute_dx(self, xn: Vec, x: Vec, h: float) -> Vec:
        """
        Compute the numerical derivative (dx) for all differential variables
        using symbolic approximation expressions and lagged variables.

        Parameters
        ----------
        y : Vec
            State variable trajectory. `y[-1, :]` corresponds to the most recent
            values of the system variables.
        lag : Vec
            Array containing lagged values of variables (delayed states).
        h : float
            Time step (dt) used in the approximation.

        Returns
        -------
        Vec
            Array with computed derivatives for each differential variable,
            indexed consistently with `self._diff_vars`.
        """
        res = np.zeros(len(self._diff_vars))
        # TODO: implement for higher order diff vars
        for diff_var in self._diff_vars:
            uid_diff_var = diff_var.uid
            uid_var = diff_var.base_var.uid
            idx_diff_var = self.uid2idx_diff[uid_diff_var]

            dx_value = (xn[uid_var] - x[uid_var]) / h
            res[idx_diff_var] = dx_value

        return res

    def pseudo_transient(self, x0: Vec, init_guess: dict[Var, float], res, grid: MultiCircuit,
                         fix='V', dtau0=1, max_iter: int = 1e3, plot: bool = False, predictor: bool = False,
                         type: str = None):
        """
        :param x0: random init guess
        :param init_guess: init_guess for power flow vars
        :param res:
        :param grid:
        :param fix:
        :param dtau0:
        :param max_iter:
        :param plot:
        :param predictor:
        :param type:

        """
        for block in self.block_system.children:
            found = False
            if getattr(block, 'pseudo_transient', False):
                bus = block.bus
                t = self.glob_time
                for child_block in block.get_all_blocks():
                    if not hasattr(child_block, 'external_mapping'):
                        continue
                    if not VarPowerFlowRefferenceType.P in child_block.external_mapping.keys():
                        continue
                    Pg = child_block.external_mapping[VarPowerFlowRefferenceType.P]
                    Qg = child_block.external_mapping[VarPowerFlowRefferenceType.Q]
                    Vm = child_block.external_mapping[VarPowerFlowRefferenceType.Vm]
                    Va = child_block.external_mapping[VarPowerFlowRefferenceType.Va]
                    found = True
                    break

                if not found:
                    continue
                bus_block = Block()

                if fix == 'P':
                    delete_vars_from_block(block, [Pg, Qg])
                    bus_block = Block(
                        algebraic_vars=[Vm, Va])
                    bus_block.event_dict = {Pg: Const(float(np.real(res.Sbus[bus] / grid.Sbase))),
                                            Qg: Const(float(np.imag(res.Sbus[bus] / grid.Sbase)))}


                elif fix == 'V':
                    delete_vars_from_block(block, [Va, Vm])
                    bus_block = Block(
                        algebraic_vars=[Pg, Qg])
                    bus_block.event_dict = {Vm: Const(float(np.abs(res.voltage[bus]))),
                                            Va: Const(float(np.angle(res.voltage[bus])))}

                elif fix == 'I':
                    Im = Var('Im')
                    Ia = Var('Ia')
                    delta = find_name_in_block('delta', block)
                    Id = find_name_in_block('Id', block)
                    Iq = find_name_in_block('Iq', block)
                    v = res.voltage[bus]
                    Sb = res.Sbus[bus] / grid.Sbase

                    # Current from power and voltage
                    i = np.conj(Sb / v)  # ī = (p - jq) / v̄*

                    bus_block = Block(
                        algebraic_eqs=[
                            Id - (-Im * sin(Ia - delta)),
                            Iq - Im * cos(Ia - delta),
                        ],
                        algebraic_vars=[Pg, Qg, Vm, Va])
                    bus_block.event_dict = {Im: Const(float(np.abs(i))),
                                            Ia: Const(float(np.angle(i)))}

                elif fix == 'P&V':
                    delete_vars_from_block(block, [Pg, Qg, Vm, Va])
                    bus_block = Block()

                    bus_block.event_dict = {Pg: Const(float(np.real(res.Sbus[bus] / grid.Sbase))),
                                            Qg: Const(float(np.imag(res.Sbus[bus] / grid.Sbase))),
                                            Vm: Const(float(np.abs(res.voltage[bus]))),
                                            Va: Const(float(np.angle(res.voltage[bus])))}


                elif fix == 'mixed':
                    delete_vars_from_block(block, [Vm, Va, Pg, Qg])
                    bus_block = Block(
                        algebraic_vars=[Va, Qg])
                    bus_block.event_dict = {Vm: Const(float(np.abs(res.voltage[bus]))),
                                            Pg: Const(float(np.real(res.Sbus[bus] / grid.Sbase)))}

                init_block = Block(
                    children=[block, bus_block]
                )
                # 2 out of [Pg, Qg, Vm, Va] need to be deleted from the algebraic vars to have a square system
                solver = BlockSolver(init_block, t)

                init_guess_copy = init_guess.copy()

                init_guess_copy.update(
                    {Vm: float(np.real(res.Sbus[bus] / grid.Sbase)), Va: float(np.imag(res.Sbus[bus] / grid.Sbase))})
                x0_init_guess = solver.build_init_vars_vector(init_guess_copy, permissive=True)

                solved = False
                alpha = 0.9
                while not solved:
                    try:
                        print(f'Trying dtau0 = {dtau0} with max_iter {max_iter}')
                        if type == 'dae':
                            x0_mdl, init_guess_mdl = solver.pseudo_transient_daes(
                                x0_init_guess.copy(), dtau0=dtau0, max_iter=max_iter, max_tries=1e3, plot=plot,
                                predictor=predictor)
                        else:
                            x0_mdl, init_guess_mdl = solver.pseudo_transient_routine(
                                x0_init_guess.copy(), dtau0=dtau0, max_iter=max_iter, max_tries=1e3, plot=plot,
                                predictor=predictor)
                        solved = True
                    except NaNError as e:
                        msg = str(e).lower()
                        # print(msg)
                        dtau0 /= alpha
                    except ConvergenceError as e:
                        msg = str(e).lower()
                        # print(msg)
                        dtau0 *= alpha
                    except Exception as e:
                        # print(f"❌ Unexpected error: {e}")
                        raise
                for i, var in enumerate(solver._algebraic_vars):
                    x0[self.uid2idx_vars[var.uid]] = x0_mdl[solver.uid2idx_vars[var.uid]]

                init_guess.update(init_guess_mdl)

        # print('Pseudo-Transient ended')
        return x0, init_guess

    def pseudo_transient_routine(self, x0, init_guess=dict(), plot=True, dtau0=1e-3, h=1e-3, beta=0.8, tol=1e-5,
                                 predictor=False, max_iter=8e4, max_tries=200, verbose=False):
        # Init pseudo transient method, Block only has algebraic eqs

        dtau = dtau0
        dtau_max = 1e9
        dtau_min = 1e-5
        init_guess_uid = [var.uid for var in init_guess.keys()]
        self.compile_implicit_predictor()

        for var in self._algebraic_vars:
            if not var.uid in init_guess_uid:
                continue
            idx = self.uid2idx_vars[var.uid]
            x0[idx] = init_guess[var]
        for i in range(len(x0)):
            if x0[i] == 0:
                _ = 0
                x0[i] = 1.0 + 0.5 * np.random.rand()

        x0 = np.random.rand(self._n_algebraic)
        dx0 = np.zeros(self._n_diff)
        y = np.empty((5, self._n_vars))
        step_idx = 0
        x_new = x0.copy()
        xn = x0.copy()
        tries = 0
        params = np.array([const.value for const in self._parameters_values])
        event_params = np.random.rand(len(self._event_parameters))
        event_params = self._event_params_fn(event_params, float(0))
        event_params = self._event_params_fn(event_params, float(0))

        dx_error = 1
        residual = 10
        old_residual = 10

        # history containers
        dtau_hist = []
        dx_error_hist = []
        residual_hist = []
        x_hist = []
        dx_hist = []

        while step_idx < max_iter:
            tries += 1
            solved = False
            if step_idx == 0:
                xlast = xn
                xn = x_new.copy()
            else:
                xlast = xn
                xn = y[-1]

            # rhs = self.rhs_implicit(xnew_lags, xn_lags, params_current, 1, dtau)
            if verbose:
                print(f'Pseudo transient step started with max_iter {max_iter} and step idx {step_idx} and try {tries}')

            dx = self._derivative_fn(xn, xlast, dx0, 1e-3)
            rhs = self.rhs_pseudo_transient(x_new, xlast, dx, event_params, params, 1, dtau)
            if not np.all(np.isfinite(rhs)):
                raise NaNError
            Jf = self.jacobian_pseudo_transient(x_new, dx, event_params, params, dtau)
            residual = np.linalg.norm(rhs)
            try:
                delta = sp.linalg.spsolve(Jf, -rhs)
            except Exception as e:
                raise SingularJacobianError(f"Linear solver failed at try {tries}: {e}")

            solved = np.all(np.isfinite(delta))
            if not solved:
                print("Using LSQR")
                delta, *_ = sp.linalg.lsqr(Jf, -rhs)
                solved = np.all(np.isfinite(delta))

            if not solved:  # or not np.all(np.isfinite(delta)):
                print(f'jacobian is {Jf.toarray()}')
                print(f'delta is {delta}')
                print(f'x_new is {x_new}')
                print(f'rhs is {rhs}')
                print(f'residual is {np.linalg.norm(rhs)} try is {tries} and step is {step_idx}')
                raise NaNError(
                    f"Newton step failed at try {tries} and step {step_idx}: delta has NaN/Inf values with dtau {dtau}")
            dx0 = dx
            x_new += delta
            print(f'delta is {delta}')

            if step_idx == 0 and tries % 10 == 1:
                i = np.argmax(rhs)

            newton_residual = np.linalg.norm(rhs, np.inf)
            if verbose:
                _ = 0
                print(f'residual is {newton_residual}, step is {step_idx} try is {tries}')
                print(f'dtau is {dtau}')

            if solved:
                step_idx += 1
                tries = 0
                y = np.roll(y, shift=-1, axis=0)
                alpha = 1.0
                if step_idx > 2:
                    y[-1] = alpha * x_new + (1 - alpha) * y[-1]
                else:
                    y[-1] = x_new
                x_new = y[-1]

                dx = self._derivative_fn(xn, xlast, dx, dtau)
                dx_error = np.linalg.norm(dx)
                rhs = self.rhs_pseudo_transient(x_new, xn, dx, event_params, params, 1, dtau)
                residual = np.linalg.norm(rhs)

                # save history
                dtau_hist.append(dtau)
                dx_error_hist.append(dx_error)
                residual_hist.append(residual)
                x_hist.append(x_new.copy())
                dx_hist.append(dx.copy())

                if residual < tol:
                    break

                print(f'Convergence achieved for dtau={dtau:.2e},residual={residual:.2e}, step {step_idx}')
                print(f'rhs is {rhs}')
                eps = 1e-14
                avg_residual = 0.8 * old_residual + 0.2 * residual
                ratio = (avg_residual + eps) / residual
                ratio = (old_residual + eps) / residual

                # Default scaling factor
                beta = ratio
                if beta > 1.0:
                    beta = 2
                elif beta < 1.0:
                    beta = 0.5

                print(f'Updating dtau: {dtau} * {beta}')
                if dtau > 0:
                    dtau = min(dtau_max, max(dtau_min, dtau * beta))
                else:
                    dtau = -min(dtau_max, max(dtau_min, -dtau * beta))
                print(f'Updated dtau: {dtau}')

                old_residual = residual

            elif tries > max_tries:
                print(f'delta is {delta}')
                print(f'failed with dtau = {dtau}')
                raise ConvergenceError(f"Max tries reached at dtau={dtau:.2e}, residual={residual:.2e}")

        init_guess = {var: x_new[self.uid2idx_vars[var.uid]] for var in self._algebraic_vars}

        if not plot:
            return x_new, init_guess
        # --- Plotting section ---
        fig, axs = plt.subplots(3, 1, figsize=(8, 10), sharex=True)

        axs[0].semilogy(dx_error_hist, label="||dx||")
        axs[0].set_ylabel("dx error (log)")
        axs[0].legend()

        axs[1].semilogy(residual_hist, label="Residual norm")
        axs[1].set_ylabel("Residual (log)")
        axs[1].legend()

        axs[2].semilogy(dtau_hist, label="dtau")
        axs[2].set_ylabel("dtau")
        axs[2].set_xlabel("Step index")
        axs[2].legend()

        # --- Plot actual variables ---
        x_hist = np.array(x_hist)  # shape: (n_steps, n_vars)
        dx_hist = np.array(dx_hist)  # shape: (n_steps, n_vars)

        nvars = len(self._algebraic_vars)
        vars_per_plot = 5
        nplots = (nvars + vars_per_plot - 1) // vars_per_plot

        fig, axs = plt.subplots(nplots, 1, figsize=(10, 2.5 * nplots), sharex=True)

        # if there’s only one subplot, axs won’t be a list
        if nplots == 1:
            axs = [axs]
        if x_hist.ndim == 1:
            # print('Pseudo Transient finished')
            return x_new, init_guess

        for i in range(nplots):
            start = i * vars_per_plot
            end = min((i + 1) * vars_per_plot, nvars)
            for var in self._algebraic_vars[start:end]:
                axs[i].plot(x_hist[:, self.uid2idx_vars[var.uid]], label=var.name)
            axs[i].set_ylabel("Value")
            axs[i].legend(loc="best", fontsize="x-small", ncol=2, frameon=False)
        axs[-1].set_xlabel("Step index")

        nvars = len(self._diff_vars)
        vars_per_plot = 5
        nplots = (nvars + vars_per_plot - 1) // vars_per_plot

        fig, axs = plt.subplots(nplots, 1, figsize=(10, 2.5 * nplots), sharex=True)
        if nplots == 1:
            axs = [axs]

        for i in range(nplots):
            start = i * vars_per_plot
            end = min((i + 1) * vars_per_plot, nvars)
            for var in self._diff_vars[start:end]:
                axs[i].plot(dx_hist[:, self.uid2idx_diff[var.uid]], label=f"d{var.base_var.name}")
            axs[i].set_ylabel("dx")
            axs[i].set_yscale("symlog")
            axs[i].legend(loc="best", fontsize="x-small", ncol=2, frameon=False)
        axs[-1].set_xlabel("Step index")
        plt.tight_layout()
        plt.show()
        # print('Pseudo Transient finished')

        return x_new, init_guess

    def compile_implicit_predictor(self):
        self._rhs_predictor = self.rhs_implicit

        self._Jf_predictor = SymbolicJacobian(eqs=self._algebraic_eqs,
                                              variables=self._diff_vars,
                                              diff_variables=[],
                                              compiler_names_dict=self.compiler_names_dict,
                                              alias_names_dict=self.alias_names_dict,
                                              uid2idx_vars=self.uid2idx_vars, )

        self._diff_eq_index = []
        for i, eq in enumerate(self._algebraic_eqs):
            eq_save = eq
            for diff_var in self._diff_vars:
                eq = eq.subs({diff_var: Const(0)})
            if str(eq_save) != str(eq):
                continue
            eq = eq.simplify()
            self._diff_eq_index.append(i)

        self._rhs_feasible = self.rhs_implicit
        self._Jf_feasible = self.jacobian_implicit

        # TODO: adapt to explicit DAE systems
        def rhs_predictor(x_new: Vec, x_old: Vec, dx: Vec, params: Vec, event_params: Vec, h: float):
            dx = self._derivative_fn(x_new, x_old, dx, h)
            rhs = self._rhs_predictor(x_old, x_old, dx, params, event_params, h)
            return rhs

        def Jf_predictor(x_new: Vec, x_old: Vec, dx: Vec, params: Vec, event_params: Vec, h: float):
            dx = self._derivative_fn(x_new, x_old, dx, h)
            Jf = self._Jf_predictor(x_old, x_old, dx, params, event_params, h) * (1 / h)
            return Jf

        def rhs_corrector(x_new: Vec, x_predicted: Vec, x_old: Vec, dx: Vec, params: Vec, event_params: Vec, h: float):
            dx = self._derivative_fn(x_new, x_old, dx, h)
            x_mid = (x_predicted + x_old) / 2
            rhs = self._rhs_predictor(x_mid, x_mid, dx, params, event_params, h)
            return rhs

        def Jf_corrector(x_new: Vec, x_predicted: Vec, x_old: Vec, dx: Vec, params: Vec, event_params: Vec, h: float):
            dx = self._derivative_fn(x_new, x_old, dx, h)
            x_mid = (x_predicted + x_old) / 2
            Jf = self._Jf_predictor(x_mid, x_mid, dx, params, event_params, h) * (1 / h)
            return Jf

        def rhs_feasible(x: Vec, params: Vec, event_params: Vec, h: float):
            dx = np.zeros(self._n_diff)
            Jf = self._rhs_predictor(x, x, dx, params, event_params, h)[self._diff_eq_index]
            return Jf

        def Jf_feasible(x: Vec, params: Vec, event_params: Vec, h: float):
            dx = 0 * np.zeros(self._n_diff)
            Jf = self._j22_fn(x, x, dx, params, event_params, h)[self._diff_eq_index]
            return Jf

        self.rhs_predictor = rhs_predictor
        self.Jf_predictor = Jf_predictor
        self.Jf_feasible = Jf_feasible
        self.rhs_feasible = rhs_feasible
        self.Jf_corrector = Jf_corrector
        self.rhs_corrector = rhs_corrector

        # print("Predictor-Corrector Compiled")
        return

    def find_feasible_point(self, xn, params, x0=None, max_steps=2e3, tol=1e-4):
        residual = 10
        h = 1e-3
        dt = params[-1]
        j = 0
        if len(xn) == self._n_diff:
            if x0 is None:
                print('xo is random.')
                xaux = np.random.rand(self._n_alg)
            else:
                xaux = x0
                # 1 Handle first-order derivatives first
                for i, var in enumerate(self._diff_vars):
                    if var.diff_order != 1:
                        continue
                    base_var_uid = self.uid2idx_vars[var.base_var.uid]
                    xaux[base_var_uid] = xn[i]

                # 2 Sort differential variables by diff_order before building lags
                diff_vars_sorted = sorted(self._diff_vars, key=lambda v: v.diff_order)

                # 3 Build lag variables in increasing order of diff_order
                for i, var in enumerate(diff_vars_sorted):
                    if var.diff_order <= 1:
                        continue

                    origin_var = var.origin_var
                    diff_order = var.diff_order

                    # Previous lag (order-1)
                    prev_lag = LagVar.get_or_create(
                        name=f"{origin_var.name}_lag{diff_order - 1}",
                        base_var=origin_var,
                        lag=diff_order - 1,
                    )
                    prev_lag_uid = self.uid2idx_vars[prev_lag.uid]

                    # Current lag
                    lag_var = LagVar.get_or_create(
                        name=f"{origin_var.name}_lag{diff_order}",
                        base_var=origin_var,
                        lag=diff_order,
                    )
                    lag_uid = self.uid2idx_vars[lag_var.uid]

                    # Recursive lag update: x_lag_n = x_lag_(n-1) − h * x^(n)
                    xaux[lag_uid] = xaux[prev_lag_uid] - params[-1] * xn[i]

                xn = xaux
        elif len(xn) == self._n_alg:
            _ = 0
        else:
            raise Exception('Length of xn is not n_diff or n_alg')

        for i in range(len(xn)):
            if xn[i] == 0:
                xn[i] += 0.2 * np.random.rand()
        if not hasattr(self, 'Jf_feasible'):
            self.compile_implicit_predictor()

        alpha = 1
        step = 0
        while residual > tol and step < max_steps:
            x_old = xn
            j += 1
            lags = np.random.rand(len(self._lag_vars))
            x = np.r_[xn, lags]
            # print(f'x is {x}')
            rhs = self.rhs_feasible(x, params)
            Jf = self.Jf_feasible(x, params)
            delta = sp.linalg.lsqr(Jf, -rhs)[0]
            # print(f'delta is {len(delta)}')
            xn += delta
            xn = alpha * xn + (1 - alpha) * x_old
            rhs = self.rhs_feasible(x, params)
            residual = np.linalg.norm(rhs)
            ##print(f'residual is {residual}, step is {step}')
            step += 1

        if residual < tol:
            print(f'Feasible point found')
        else:
            print(f'Feasible solver failed')

        xn_aux = np.zeros(self._n_vars)
        xn_aux[:len(xn)] = xn
        for i, var in enumerate(self._diff_vars):
            if var.diff_order > 1:
                continue
            id = self.uid2idx_vars[var.origin_var.uid]
            xn_aux[id] = xn[id]
        for lag_var in self._lag_vars:
            lag_id = self.uid2idx_lag[lag_var.uid]
            var_id = self.uid2idx_vars[lag_var.base_var.uid]
            lags[lag_id] = xn[var_id]

        xn_aux = np.r_[xn_aux, lags]
        rhs = self.rhs_implicit(xn_aux, xn_aux, params, 0, 1e-3)
        residual_implicit = np.linalg.norm(rhs)
        # print(f'End of feasible point residual is {residual}, implicit res is {residual_implicit} x_new_compl is of length {len(xn)}')
        return xn

    def build_x_y(self, x, y):
        diff_base_var_uids = [diff_var.base_var.uid for diff_var in self._diff_vars]
        res = np.zeros(len(x) + len(y))
        i_x = 0
        i_y = 0
        for var in self._algebraic_vars:
            var_id = self.uid2idx_vars[var.uid]
            if var.uid in diff_base_var_uids:
                res[var_id] = x[i_x]
                i_x += 1
            else:
                res[var_id] = y[i_y]
                i_y += 1

        return res

    def find_feasible_given_x(self, x, x_old, params, max_steps=5e3, tol=1e-3):
        residual = 10
        h = 1e-3
        j = 0
        diff_base_vars = [diff_var.origin_var for diff_var in self._diff_vars]
        diff_base_vars_uid = [diff_var.base_var.uid for diff_var in self._diff_vars]
        x_index = [self.uid2idx_vars[var.uid] for var in diff_base_vars]
        y_index = [i for i in range(self._n_alg) if i not in x_index]

        y = np.ones(self._n_alg - len(x))
        i_xold = 0
        for var in self._algebraic_vars:
            if var.uid in diff_base_vars_uid:
                continue
            var_id = self.uid2idx_vars[var.uid]
            y[i_xold] = x_old[var_id]
            i_xold += 1

        if not hasattr(self, 'Jf_feasible'):
            self.compile_implicit_predictor()

        alpha = 1
        step = 0
        scale = False
        regularize = False
        while residual > tol and step < max_steps:
            j += 1
            x_y = self.build_x_y(x, y)
            rhs = self.rhs_feasible(x_y, params)
            Jf = self.Jf_feasible(x_y, params)
            delta = sp.linalg.lsmr(Jf, -rhs)[0]
            x += 0.1 * delta[x_index]
            y += delta[y_index]
            residual = np.linalg.norm(rhs)

            # print(f'residual is {residual}, rhs is {rhs}, step is {step}, delta is {Jf}')
            step += 1

        if step == max_steps:
            raise Exception('Convergence algorithm failed in the allowed number of steps.')
        else:
            _ = 0
            print(f'Found feasible y(x)')
        return x_y

    def predictor(self, x_old, params, max_step=1e3, tol=1e-4):
        x_new = np.random.rand(len(self._diff_vars))
        residual = 10
        step = 0
        if not hasattr(self, 'rhs_predictor'):
            self.compile_implicit_predictor()

        x_feasible = self.find_feasible_point(x_old[:self._n_alg], params, x0=x_old[:self._n_alg])
        x_old[:len(x_feasible)] = x_feasible
        for i, var in enumerate(self._diff_vars):
            id = self.uid2idx_vars[var.origin_var.uid]
            x_new[i] = x_feasible[id]

        rhs = self.rhs_predictor(x_new, x_old, params)
        residual = np.linalg.norm(rhs)
        while residual > tol and step < max_step:
            step += 1
            rhs = self.rhs_predictor(x_new, x_old, params)
            Jf = self.Jf_predictor(x_new, x_old, params)
            delta = sp.linalg.lsqr(Jf, -rhs)[0]
            x_new += delta
            residual = np.linalg.norm(rhs)
            ##print(f'Loop Predictor residual is {residual} for step {step}')

        lags = np.zeros(len(self._lag_vars))
        lags1 = lags.copy()
        lags2 = lags.copy()
        x_aux = x_old.copy()[:self._n_alg]

        for i, var in enumerate(self._diff_vars):
            id = self.uid2idx_vars[var.origin_var.uid]
            x_feasible[id] = x_new[i]
        try:
            x_y = self.find_feasible_given_x(x_new, x_feasible, params, max_steps=1e4)
            x_y_comp = np.r_[x_y, lags]
            rhs1 = self.rhs_implicit(x_y_comp, x_y, params, 0, 1e-3)
            residual1 = np.linalg.norm(rhs1)
            # print(f'End of predictor residual is {residual1}, x_y is of length {len(x_y_comp)}')
        except:
            # print(f'Find feasible x failed')
            _ = 0

        for var in self._diff_vars:
            base_var_id = self.uid2idx_vars[var.origin_var.uid]
            diff_var_id = self.uid2idx_diff[var.uid]
            x_aux[base_var_id] = x_new[diff_var_id]
        for lag_var in self._lag_vars:
            lag_id = self.uid2idx_lag[lag_var.uid]
            var_id = self.uid2idx_vars[lag_var.base_var.uid]
            lags[lag_id] = x_old[var_id]
            lags2[lag_id] = x_aux[var_id]

        x_new_comp = np.r_[x_aux, lags]
        # x_new = x_new_comp
        # print(f'End of predictor residual is {residual2}, x_new_compl is of length {len(x_new_comp)}')
        return x_new, x_feasible

    def corrector(self, x_predicted, x_old, x_feasible, params, max_step=10, tol=1e-3):
        x_new = np.zeros(len(self._diff_vars))
        residual = 10
        x_old = x_old[:self._n_alg]
        step = 0
        x_old_limited = np.zeros(len(self._diff_vars))
        for var in self._diff_vars:
            base_var_id = self.uid2idx_vars[var.origin_var.uid]
            diff_var_id = self.uid2idx_diff[var.uid]
            x_old_limited[diff_var_id] = x_old[base_var_id]

        try:
            x_predicted = self.find_feasible_given_x(x_predicted, x_feasible, params)
        except Exception as e:
            msg = str(e)
            print(msg)
            print('given x failed')
            x_predicted = self.find_feasible_point(x_predicted, params, x0=x_feasible)
        try:
            x_old = self.find_feasible_given_x(x_old_limited, x_feasible, params)
        except:
            print('given x failed')
            x_old = self.find_feasible_point(x_old_limited, params, x0=x_feasible)
        for i, var in enumerate(self._diff_vars):
            id = self.uid2idx_vars[var.base_var.uid]
            x_new[i] = x_predicted[id]

        alpha = 1.0
        x_mid = alpha * (x_predicted) + (1 - alpha) * x_old
        lags = np.zeros(len(self._lag_vars))
        for lag_var in self._lag_vars:
            lag_id = self.uid2idx_lag[lag_var.uid]
            var_id = self.uid2idx_vars[lag_var.base_var.uid]
            lags[lag_id] = x_old[var_id]

        x_predicted_withlags = np.r_[x_predicted, lags]
        rhs = self.rhs_implicit(x_predicted_withlags, x_predicted, params, 0, 1e-3)
        residual = np.linalg.norm(rhs)

        ##print(f'x_predicted of length {len(x_predicted)}')
        # print(f'Initial corrector {residual}, x_new is of length {len(x_new)}')
        while residual > tol and step < max_step:
            rhs = self.rhs_corrector(x_new, x_mid, x_old, params)
            Jf = self.Jf_corrector(x_new, x_mid, x_old, params)
            delta = sp.linalg.lsqr(Jf, -rhs)[0]
            x_new += delta

            residual = np.linalg.norm(rhs)
            step += 1
            # print(f'Corrector Loop residual is {residual} for step {step} delta_norrm is {np.linalg.norm(delta)}, rhs is {rhs}')

        if residual > tol:
            _ = 0
            print('Corrector failed')
            return x_new, x_mid
        else:
            print('Corrector Succeeded')

        for i, var in enumerate(self._diff_vars):
            idx = self.uid2idx_vars[var.origin_var.uid]
            x_mid[idx] = x_new[i]

        return x_new, x_mid

    def fixed_point_finder(self, x0=None, tol=1e-4):
        states = set()
        states = {var.base_var for var in self._diff_vars}
        self.states = list(states)
        self.n_states = len(states)
        if x0 is None:
            xstart = np.random.rand(len(self._lag_vars))
        else:
            xstart = np.zeros(len(self._lag_vars))
            for lag in self._lag_vars:
                base_var = lag.base_var
                base_var_idx = self.uid2idx_vars[base_var.uid]
                xstart[self.uid2idx_lag[lag.uid]] = x0[base_var_idx]

        params_current = self._event_params_fn(float(0))
        T_operator = self.T_operator(params_current)
        residual = 10
        alpha = 0.05
        x = xstart.copy()
        while residual > tol:
            x_new = (alpha) * x + (1 - alpha) * T_operator(x)
            residual = np.linalg.norm(x_new - x)
            x = x_new
        return x

    def enable_newton_tracing(self, collector):
        """
        Attach a Newton diagnostics trace collector.

        Parameters
        ----------
        collector : NewtonTraceCollector
            Collector used to store Newton iteration diagnostics.
        """
        self.newton_trace_collector = collector
