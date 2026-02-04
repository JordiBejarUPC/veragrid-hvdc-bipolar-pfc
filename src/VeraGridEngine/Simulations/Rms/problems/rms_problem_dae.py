# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Tuple, Sequence, Callable, Any
from collections import defaultdict
import time
import numpy as np
import numba as nb
import scipy.sparse as sp
import math
import concurrent.futures
from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block_solver import compile_jac_block
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, DiffVar, Const, Expr, piecewise,
                                                    _heaviside, expression2numba,
                                                    get_expression_vars)

from VeraGridEngine.enumerations import SimulationBackend, VarPowerFlowRefferenceType
from VeraGridEngine.basic_structures import Vec, ObjVec, IntVec, BoolVec, Logger
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.initialization import compose_system_block
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Devices.types import ALL_DEV_TYPES


def _tic():
    return time.perf_counter()


def _toc(t0):
    return time.perf_counter() - t0


def setP(P: ObjVec, P_used: BoolVec, k: int, val: object):
    """

    :param P:
    :param P_used:
    :param k:
    :param val:
    :return:
    """
    if not P_used[k]:
        P[k] = val
        P_used[k] = 1
    else:
        P[k] += val


def setQ(Q: ObjVec, Q_used: BoolVec, k: int, val: object):
    """

    :param Q:
    :param Q_used:
    :param k:
    :param val:
    :return:
    """
    if not Q_used[k]:
        Q[k] = val
        Q_used[k] = 1
    else:
        Q[k] += val


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

    def __init__(self,
                 eqs: List[Expr],
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


class RmsProblemDae(RmsProblemTemplate):
    """
    DAE (Differential-Algebraic Equation) class to store and manage.

    Responsibilities:
        - Store state and algebraic variables (x, y)
        - Store Jacobian matrices
        - Store residual equations
        - Store sparsity patterns
    """
    VARS_NAME = "vars"
    VARIABLE_PARAMS_NAME = "vprms"
    CONSTANT_PARAMS_NAME = "cprms"
    DIFF_NAME = "diff"
    ALTER_PARAMS_NAME = "alter"
    TIME_NAME = "glob_time"

    def __init__(self,
                 grid: MultiCircuit,
                 options: RmsOptions,
                 pf_results: PowerFlowResults | None):
        """

        :param grid:
        :param options:
        :param pf_results:
        """
        super().__init__()

        self.logger = Logger()

        # --------------------------------------------------------------------------------------------------------------
        # Initialize the RMS problem
        # --------------------------------------------------------------------------------------------------------------
        self._glob_time: Var = Var(self.TIME_NAME)

        vars2device: Dict[int, ALL_DEV_TYPES] = dict()
        self._vars_info: Dict[ALL_DEV_TYPES, List[Var]] = dict()
        vars_glob_name2uid: Dict[str, int] = dict()
        # find events
        rms_events = grid.rms_events

        # already computed grid power flow

        bus_dict = dict()

        # balance equation arrays
        n = len(grid.buses)
        P: ObjVec = np.zeros(n, dtype=object)
        Q: ObjVec = np.zeros(n, dtype=object)
        P_used: IntVec = np.zeros(n, dtype=int)
        Q_used: IntVec = np.zeros(n, dtype=int)

        # initialize buses
        for i, elm in enumerate(grid.buses):
            bus_dict[elm] = i
            for var in elm.rms_model.model.get_all_vars():
                vars2device[var.uid] = elm
                vars_glob_name2uid[var.name + elm.name] = var.uid

        # initialize branches
        for elm in grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):

            mdl = elm.rms_model.model
            f = bus_dict[elm.bus_from]
            t = bus_dict[elm.bus_to]
            # add variable to conservation equations of the bus to which the element is connected
            setP(P, P_used, f, -mdl.E(VarPowerFlowRefferenceType.Pf))
            setP(P, P_used, t, -mdl.E(VarPowerFlowRefferenceType.Pt))
            setQ(Q, Q_used, f, -mdl.E(VarPowerFlowRefferenceType.Qf))
            setQ(Q, Q_used, t, -mdl.E(VarPowerFlowRefferenceType.Qt))

            for var in elm.rms_model.model.get_all_vars():
                vars2device[var.uid] = elm
                vars_glob_name2uid[var.name + elm.name] = var.uid
                self.add_device_var(dev=elm, var=var)

        # initialize injections
        for elm in grid.get_injection_devices_iter():

            # create dictionary for collecting events of the same parameter

            if elm.rms_model.model.event_dict is not None:
                collect_events = {
                    key: {"times": [], "values": []}
                    for key in elm.rms_model.model.event_dict.keys()
                }
                # find out if there are events affecting the device parameters
                rms_evts = [rms_evt for rms_evt in rms_events if rms_evt.device_idtag == elm.idtag]
                if len(rms_evts) != 0:
                    for rms_evt in rms_evts:
                        collect_events[rms_evt.parameter]["times"].append(rms_evt.time)
                        collect_events[rms_evt.parameter]["values"].append(rms_evt.value)
                        # TODO: implement the function in block: apply_event
                    for param, events_info in collect_events.items():
                        default_value = elm.rms_model.model.event_dict[param]
                        elm.rms_model.model.event_dict[param] = piecewise(
                            time_var=self._glob_time,
                            t_events=np.array(events_info["times"]),
                            new_values=np.array(events_info["values"]),
                            default_value=default_value
                        )

            # after applying the events the model has to be "build"
            mdl = elm.rms_model.model

            # add variable to conservation equations of the bus to which the element is connected
            k = bus_dict[elm.bus]
            setP(P, P_used, k, mdl.E(VarPowerFlowRefferenceType.P))
            setQ(Q, Q_used, k, mdl.E(VarPowerFlowRefferenceType.Q))

            for var in elm.rms_model.model.get_all_vars():
                vars2device[var.uid] = elm
                vars_glob_name2uid[var.name + elm.name] = var.uid

        # add the nodal balance equations
        for i, elm in enumerate(grid.buses):
            mdl = elm.rms_model.model
            if len(mdl.algebraic_eqs) == 0:
                if P_used[i] == 0 and Q_used[i] == 0:
                    self.logger.add_error("Isolated bus", value=i)
                else:
                    mdl.algebraic_eqs.append(P[i])
                    mdl.algebraic_eqs.append(Q[i])

        self._block_system, self._initial_guess_mapping = compose_system_block(
            time_var=self._glob_time,
            grid=grid,
            TIME_NAME=self.TIME_NAME,
            VARS_NAME=self.VARS_NAME,
            power_flow_results=pf_results,
            vars2device=vars2device,
            vars_glob_name2uid=vars_glob_name2uid,
            use_init_values=options.use_init_values,
            method=options.initialization_method
        )

        # --------------------------------------------------------------------------------------------------------------
        # collect equations
        # --------------------------------------------------------------------------------------------------------------

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
        self._variable_parameters: List[Var] = list()
        self._event_parameters_eqs: List[Expr] = list()
        self._constant_parameters: List[Var] = list()
        self._parameters_values: List[Const] = list()
        self._stability_eqs: List[Expr] = list()
        self._alter_params = np.zeros(0)  # NOTE: this is needed for the jacobian calls but it is only relevant for EMT

        # Class-level registry
        self._registry: Dict[int, DiffVar] = dict()  # int uuid , DiffVar
        self._absolute_registry: Dict[Tuple[int, int], DiffVar] = dict()

        # self.v_glob_name2uid = self.block_system.vars_glob_name2uid

        self._substitute = True

        # Numerical trace
        self._newton_trace_collector = None
        self._backend = SimulationBackend.SymbolicImplicit

        for b in self._block_system.get_all_blocks():
            self._algebraic_vars.extend(b.algebraic_vars)
            self._algebraic_eqs.extend(b.algebraic_eqs)
            self._state_vars.extend(b.state_vars)
            self._state_eqs.extend(b.state_eqs)
            for param, eq in b.event_dict.items():
                self._variable_parameters.append(param)
                self._event_parameters_eqs.append(eq)
            for param, constant in b.parameters.items():
                self._constant_parameters.append(param)
                self._parameters_values.append(constant)

            # if isinstance(b, DiffBlock):
            self._diff_vars.extend(b.diff_vars)

        self._diff_vars = sorted(self._diff_vars, key=lambda dv: dv.diff_order)
        self._state_algeb_vars = self._state_vars + self._algebraic_vars
        self._state_eqs_substituted = self._state_eqs.copy()

        # We define the parameter dt and delta
        self._dt = Var(name='dt')
        self._delta = Var(name='delta')
        self._variable_parameters.append(self._dt)
        self._variable_parameters.append(self._delta)
        self._event_parameters_eqs.append(Const(1e-3))
        self._event_parameters_eqs.append(Const(1))

        self._n_state = len(self._state_vars)
        self._n_alg = len(self._algebraic_vars)
        self._n_vars = self._n_state + self._n_alg
        self._n_event_params = len(self._variable_parameters)
        self._n_params = len(self._constant_parameters)
        self._n_diff = len(self._diff_vars)
        self._n_algebraic = len(self._algebraic_eqs)

        # generate the in-code names for each variable
        # inside the compiled functions the variables are
        # going to be represented by an array called vars[]

        self._compiler_names_dict: Dict[int, str] = dict()
        self._alias_names_dict: Dict[int, str] = dict()
        self._uid2idx_vars: Dict[int, int] = dict()
        self._uid2idx_event_params: Dict[int, int] = dict()
        self._uid2idx_params: Dict[int, int] = dict()
        self._uid2idx_diff: Dict[int, int] = dict()
        self._uid2idx_t: Dict[int, int] = dict()

        i = 0
        for v in self._state_vars:
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[v.uid] = i
            i += 1

        for v in self._algebraic_vars:
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[v.uid] = i
            i += 1

        for j, ep in enumerate(self._constant_parameters):
            self._compiler_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}[{j}]"
            self._alias_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}_{j}"
            self._uid2idx_params[ep.uid] = j

        for k, ep in enumerate(self._variable_parameters):
            self._compiler_names_dict[ep.uid] = f"{self.VARIABLE_PARAMS_NAME}[{k}]"
            self._alias_names_dict[ep.uid] = f"{self.VARIABLE_PARAMS_NAME}_{k}"
            self._uid2idx_event_params[ep.uid] = k

        for k, ep in enumerate(self._diff_vars):
            self._compiler_names_dict[ep.uid] = f"{self.DIFF_NAME}[{k}]"
            self._alias_names_dict[ep.uid] = f"{self.DIFF_NAME}_{k}"
            self._uid2idx_diff[ep.uid] = k

        self._compiler_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._uid2idx_t[self._glob_time.uid] = 0

        for it, eq in enumerate(self._event_parameters_eqs):
            if isinstance(eq, Const) and eq.value is None:
                raise Exception(f' Event parameter {self._variable_parameters[it]} has None Value')

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

        # --------------------------------------------------------------------------------------------------------------
        # Compile RHS and Jacobian
        # --------------------------------------------------------------------------------------------------------------

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
            uid2idx_vars=self._uid2idx_vars,
            diff_vars=self._diff_vars,
            compiler_names_dict=self._compiler_names_dict
        )
        timings["SymbolicDerivative"] = _toc(t0)

        t0 = _tic()
        self._rhs_algeb_fn = SymbolicVector(
            eqs=self._algebraic_eqs,
            compiler_names_dict=self._compiler_names_dict,
            alias_names_dict=self._alias_names_dict,
            VARS_NAME=self.VARS_NAME,
            EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
            PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
            DIFF_NAME=self.DIFF_NAME,
            ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
        )
        timings["RHS algebraic"] = _toc(t0)

        t0 = _tic()
        self._event_params_fn = SymbolicParamsVector(
            eqs=self._event_parameters_eqs,
            compiler_names_dict=self._compiler_names_dict,
            alias_names_dict=self._alias_names_dict,
            EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
            TIME_NAME=self.TIME_NAME,
        )
        timings["Event parameters"] = _toc(t0)

        if len(self._state_eqs) != 0:

            t0 = _tic()
            self._rhs_state_fn = SymbolicVector(
                eqs=self._state_eqs,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
            )
            timings["RHS state"] = _toc(t0)

            t0 = _tic()
            self._j11_fn = SymbolicJacobian(
                eqs=self._state_eqs,
                variables=self._state_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                uid2idx_vars=self._uid2idx_vars,
                dt=self._dt,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
            )
            timings["J11 (dF/dx)"] = _toc(t0)

            t0 = _tic()
            self._j12_fn = SymbolicJacobian(
                eqs=self._state_eqs,
                variables=self._algebraic_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                uid2idx_vars=self._uid2idx_vars,
                dt=self._dt,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
            )
            timings["J12 (dF/dy)"] = _toc(t0)

            t0 = _tic()
            self._j21_fn = SymbolicJacobian(
                eqs=self._algebraic_eqs,
                variables=self._state_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                uid2idx_vars=self._uid2idx_vars,
                dt=self._dt,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
            )
            timings["J21 (dG/dx)"] = _toc(t0)

            t0 = _tic()
            self._j22_fn = SymbolicJacobian(
                eqs=self._algebraic_eqs,
                variables=self._algebraic_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                uid2idx_vars=self._uid2idx_vars,
                dt=self._dt,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
            )
            timings["J22 (dG/dy)"] = _toc(t0)

        else:
            t0 = _tic()
            self._j22_fn = SymbolicJacobian(
                eqs=self._algebraic_eqs,
                variables=self._algebraic_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                uid2idx_vars=self._uid2idx_vars,
                dt=self._dt,
                VARS_NAME=self.VARS_NAME,
                EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                ALTER_PARAMS_NAME=self.ALTER_PARAMS_NAME,
            )
            timings["J22 only (no states)"] = _toc(t0)

        if options.verbose > 0:
            print(
                f"Model compiled with {self._n_vars} variables, "
                f"{len(self._algebraic_eqs_substituted)} algebraic eqs and "
                f"{len(self._state_eqs_substituted)} state eqs"
            )

            print("\nCompilation timing summary:")
            for k, v in timings.items():
                print(f"  {k: 30s}: {v: 8.4f} s")

        # --------------------------------------------------------------------------------------------------------------
        # Collect parameters' vectors
        # --------------------------------------------------------------------------------------------------------------

        self._variable_parameters = np.ones(self.get_variable_parameter_number())

        # TODO: think about this thing of calling twice here
        self._variable_params = self._event_params_fn(self._variable_parameters, 0.0)
        self._variable_params = self._event_params_fn(self._variable_params, 0.0)

        self._constant_params = np.array([const.value for const in self._parameters_values])

        if options.verbose > 0:
            print(f"\nTotal compile time: {sum(timings.values()):.4f} s")

    def get_vars_info(self) -> Dict[ALL_DEV_TYPES, List[Var]]:
        return self._vars_info

    def add_device_var(self, dev: ALL_DEV_TYPES, var: Var):
        """
        Associate a variable with a device
        :param dev: Device
        :param var: Variable
        """
        var_list = self._vars_info.get(dev, None)

        if var_list is None:
            self._vars_info[dev] = [var]
        else:
            var_list.append(var)

    @property
    def v_glob_name2uid(self):
        """

        :return:
        """
        return self._block_system.vars_glob_name2uid

    def get_all_vars_number(self) -> int:
        return self._n_vars

    def get_diff_var_number(self) -> int:
        """
        Get the number of diff vars
        :return:
        """
        return len(self._diff_vars)

    def get_algebraic_var_number(self) -> int:
        return len(self._algebraic_vars)

    def get_states_number(self) -> int:
        return self._n_state

    def get_variable_parameter_number(self) -> int:
        return len(self._constant_parameters)

    def get_x0(self) -> Vec:
        """
        Helper function to build the initial vector
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._state_vars) + len(self._algebraic_vars))

        for key, val in self._initial_guess_mapping.items():
            uid, name = key
            if uid in self._uid2idx_vars.keys():
                i = self._uid2idx_vars[uid]
                x[i] = val
            else:
                raise ValueError(f"Missing uid {key} definition")

        return x

    def update_variable_params(self, t: float):
        """
        Update the variable parameters
        :param t:
        :return:
        """
        self._variable_parameters = self._event_params_fn(np.array(self._variable_parameters), t)

    def get_dx(self, x: Vec, xn: Vec, dx: Vec, h: float) -> Vec:
        return self._derivative_fn(x, xn, dx, h)

    def rhs_state(self, x: Vec, dx: Vec, ) -> Vec:
        return self._rhs_state_fn(x, dx,
                                 self._variable_params,
                                 self._constant_params,
                                 self._alter_params)

    def rhs_algebraic(self, x: Vec, dx: Vec) -> Vec:
        return self._rhs_algeb_fn(x, dx,
                                 self._variable_params,
                                 self._constant_params,
                                 self._alter_params)

    def get_j11(self, x: Vec, dx: Vec, h: float):
        return self._j11_fn(x, dx,
                           self._variable_params,
                           self._constant_params,
                           self._alter_params,
                           h)

    def get_j12(self, x: Vec, dx: Vec, h: float):
        return self._j12_fn(x, dx,
                           self._variable_params,
                           self._constant_params,
                           self._alter_params,
                           h)

    def get_j21(self, x: Vec, dx: Vec, h: float):
        return self._j21_fn(x, dx,
                           self._variable_params,
                           self._constant_params,
                           self._alter_params,
                           h)

    def get_j22(self, x: Vec, dx: Vec, h: float):
        return self._j22_fn(x, dx,
                           self._variable_params,
                           self._constant_params,
                           self._alter_params,
                           h)
