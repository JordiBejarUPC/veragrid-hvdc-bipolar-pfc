# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple, Any, Sequence, Callable, Dict, List
import math
import numba as nb
import numpy as np

import uuid
from collections import defaultdict

from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.symbolic import expression2numba, _emit_one, sin, cos, get_expression_vars
from VeraGridEngine.Utils.Symbolic.block import Block, Expr, Var, block2implicit
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, RmsInitializationMethod
from VeraGridEngine.basic_structures import Logger, ObjVec, BoolVec
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const, expression2numba, \
    heaviside_num, piecewise, heaviside
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver, NaNError, SingularJacobianError, ConvergenceError, \
    SolverError

from VeraGridEngine.enumerations import RmsInitializationMethod



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
                "_heaviside": heaviside_num,
            }

            fname = f"func"  # since we compile into a namespace, there won't be repeated names

            # Build source
            src = f"def {fname}({VARS_NAME}, {DIFF_NAME}, {EVENT_PARAMS_NAME}, {PARAMS_NAME}, out):\n"
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
                    nb.void(nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:]),
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



class SymbolicParamsVectorInit:
    """
    SymbolicFunction
    """

    def __init__(self, eqs: Sequence[Expr],
                 compiler_names_dict: Dict[int, str],
                 alias_names_dict: Dict[int, str],
                 VARS_NAME: str,
                 EVENT_PARAMS_NAME: str,
                 TIME_NAME: str,
                 use_jit: bool = True,
                 ):
        """
        Compile the array of expressions to a function that returns an array of values for those expressions
        :param eqs: Iterable of expressions (Expr)
        :param uid2sym_t: dictionary relating the uid of a var with its array name (i.e. var[0])
        :return: Function pointer that returns an array
        """
        self.func: Callable[[Vec, Vec, float, Vec], None] | None = None
        used_vars_count = defaultdict(int)
        for eq in eqs:
            for var in get_expression_vars(eq):
                used_vars_count[var.uid] += 1

        if len(eqs):
            self.namespace: Dict[str, Any] = {
                "math": math,
                "np": np,
                "nb": nb,
                "_heaviside": heaviside_num,
            }

            fname = f"func"  # since we compile into a namespace, there won't be repeated names

            # Build source
            src = f"def {fname}({VARS_NAME}, {EVENT_PARAMS_NAME}, {TIME_NAME}, out):\n"
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
                self.func = nb.njit(nb.void(nb.float64[:], nb.float64[:], nb.float64, nb.float64[:]),
                                    fastmath=True)(self.namespace[fname])
            else:
                self.func = self.namespace[fname]
        else:
            self.func = None

        self.data = np.zeros(len(eqs))

    def __call__(self, variables, event_params: Vec, glob_time: float) -> Vec:
        """
        Call the compiled function
        :param glob_time:
        :return:
        """
        if self.func is not None:
            self.func(variables, event_params, glob_time, self.data)
        return self.data

def delete_vars_from_block(block: Block, deleted_vars: List[Var]):
    """

    :param block:
    :param deleted_vars:
    :return:
    """
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


def find_name_in_block(name: str, block: Block):
    lists = [block.algebraic_vars, block.state_vars]
    for lst in lists:
        for var in lst:
            if name == var.name:
                return var
    raise ValueError(f"Could not find name {name}")


def build_init_vars_vector(uid2idx_vars, mapping: dict[Var, float]) -> np.ndarray:
    """
    Helper function to build the initial vector
    :param uid2idx_vars:
    :param mapping: var->initial value mapping
    :return: array matching with the mapping, matching the solver ordering
    """
    x = np.zeros(len(mapping.items()))

    for key, val in mapping.items():
        if key.uid in uid2idx_vars.keys():
            i = uid2idx_vars[key.uid]
            x[i] = val
        else:
            raise ValueError(f"Missing variable {key} definition")

    return x


def parse_vars(dev_mdl, init_guess_dict, vars_list) -> tuple[Dict, List]:
    for var in dev_mdl.state_vars:
        vars_list.append(var)
        init_guess_dict.update({var: np.random.rand()})
    for var in dev_mdl.algebraic_vars:
        vars_list.append(var)
        init_guess_dict.update({var: np.random.rand()})
    # if hasattr(dev_mdl, 'diff_vars'):
    #     for var in dev_mdl.diff_vars:
    #         vars_list.append(var)
    #         init_guess_dict.update({var: np.random.rand()})
    if dev_mdl.children:
        for child in dev_mdl.children:
            parse_vars(child, init_guess_dict, vars_list)

    return init_guess_dict, vars_list


def init_explicit(mdl: Block, sys_vars, variable_parameters, constant_parameters, init_guess, uid2idx_vars, uid2idx_params, uid2idx_event_params,
                  compiler_names_dict, alias_names_dict, VARIABLE_PARAMS_NAME, TIME_NAME, VARS_NAME, DIFF_NAME, PARAMS_NAME):
    """
    Initialize using explicit equations
    """

    # initialize array for model variables
    #this is general but has to be here because needs the total length of variables array
    x = np.ones(len(sys_vars))

    # assign initial guesses for known variables
    for uid, var in sys_vars.items():
        key = (uid, var.name)
        if key in init_guess:
            x[uid2idx_vars[uid]] = init_guess[key]

    # initialize array for model params
    #this is general but has to be here because needs the total length of variables array
    params_array = np.zeros(len(constant_parameters))
    # compute and assign parameters value


    for param, const in mdl.parameters.items():
        param_val = const.value
        params_array[uid2idx_params[param.uid]] = param_val

    # initialize array for model event params
    #this is general but has to be here because needs the total length of variables array
    event_params_array = np.ones(len(variable_parameters))
    # compute and assign event parameters non undefined value

    for event_param in mdl.event_dict.keys():
        eq = mdl.event_dict[event_param]

        if (isinstance(eq, Const) and eq.value is not None) or not isinstance(eq, Const):
            eq_fn = SymbolicParamsVectorInit([eq], compiler_names_dict, alias_names_dict, VARS_NAME, VARIABLE_PARAMS_NAME, TIME_NAME)
            param_val = float(eq_fn(x, event_params_array, 0.0)[0])
            event_params_array[uid2idx_event_params[event_param.uid]] = param_val

    # compute and assign missing init_vars and undefined parameters
    vars_initialized: set[tuple[int, str]] = set()
    while len(vars_initialized) < len(mdl.init_eqs):
        progress = False

        vars_init_at_start = len(vars_initialized)
        for var, eq in mdl.init_eqs.items():
            key = (var.uid, var.name)
            if key not in vars_initialized:

                # get all the variables inside the initialization equation
                vars_needed = get_expression_vars(eq)

                calculate_now = True
                for v_init in vars_needed:
                    # check if this variable is already initialized
                    key_deps = (v_init.uid, v_init.name)

                    if v_init in mdl.event_dict.keys():
                        if isinstance(mdl.event_dict[v_init], Const) and mdl.event_dict[v_init].value is None:
                            calculate_now = False
                            break

                    else:
                        if key_deps not in init_guess and v_init.uid != var.uid:
                            calculate_now = False
                            break

                if calculate_now:

                    # We initialize the params with value None
                    if var in mdl.event_dict.keys():
                        if isinstance(eq, Const) and eq.value is not None:

                            raise ValueError(f"Parameter {var.name} already initialized")

                        else:
                            eq_fn = SymbolicParamsVectorInit([eq], compiler_names_dict, alias_names_dict, VARS_NAME, VARIABLE_PARAMS_NAME, TIME_NAME)
                            param_val = float(eq_fn(x, event_params_array, 0.0)[0])
                            mdl.event_dict[var] = Const(param_val)
                            event_params_array[uid2idx_event_params[var.uid]] = param_val

                    # We initialize the algebraic values
                    else:
                        vars_in_eqs = get_expression_vars(eq)

                        if var not in vars_in_eqs:
                            eq_fn = SymbolicVector([eq], compiler_names_dict, alias_names_dict, VARS_NAME,
                                                   DIFF_NAME, VARIABLE_PARAMS_NAME, PARAMS_NAME)
                            init_val = float(eq_fn(x, np.ones(1), event_params_array, params_array)[0])
                            init_guess[key] = init_val
                            x[uid2idx_vars[var.uid]] = init_val
                        else:
                            eq_fn = SymbolicVector([eq], compiler_names_dict, alias_names_dict, VARS_NAME, DIFF_NAME, VARIABLE_PARAMS_NAME, PARAMS_NAME)
                            init_val = 0
                            tol = 1e-8
                            error = 1
                            alpha = 0.5
                            x0 = 0.9
                            x[uid2idx_vars[var.uid]] = x0
                            while error > tol:
                                try:
                                    init_val = float(eq_fn(x, np.ones(1), event_params_array, params_array)[0])
                                except:
                                    x[uid2idx_vars[var.uid]] = -0.1
                                    init_val = float(eq_fn(x, np.ones(1), event_params_array, params_array)[0])
                                x[uid2idx_vars[var.uid]] = (1 - alpha) * x0 + alpha * init_val
                                error = np.linalg.norm(init_val - x0)
                                x0 = x[uid2idx_vars[var.uid]]
                            init_guess[key] = init_val
                            x[uid2idx_vars[var.uid]] = init_val

                    vars_initialized.add(key)

        vars_init_at_end = len(vars_initialized)
        if vars_init_at_end > vars_init_at_start:
            progress = True

        if not progress:
            unresolved = [v.name for v in mdl.init_eqs if (v.uid, v.name) not in vars_initialized]
            raise RuntimeError(f"Unresolvable init equations: {unresolved}")


def init_pseudo_transient(bus, region: Block, grid, sys_block, res, init_guess, time):
    region_time = Var('region_time')
    uid2idx_region_vars: Dict[int, int] = dict()
    init_guess_region: Dict[Var, float] = dict()
    bus_index = grid.buses.index(bus)
    bus_block = bus.rms_model.model
    region.unify_blocks()
    # add bus variables to init_guess_region

    x0_region = build_init_vars_vector(uid2idx_region_vars, init_guess_region)

    x0_pst, init_guess_pst = pseudo_transient(bus_index, bus_block, region, region_time, x0_region, init_guess_region,
                                              res,
                                              grid, uid2idx_region_vars)
    for var, value in init_guess_pst.items():
        init_guess[(var.uid, var.name)] = value

    for param, eq in region.event_dict.items():
        if isinstance(eq, Const) and eq.value is None:
            region.event_dict[param] = init_guess[(param.uid, param.name)]
    sys_block.add(region)

    return time, sys_block, init_guess


def pseudo_transient(bus_index, bus_block, region_system, region_time, alter_params, x0: np.ndarray,
                     init_guess: dict[Var, float], res,
                     grid: MultiCircuit, uid2idx_vars: Dict[int, int],
                     dtau0=1e0, max_iter: int = 1e3, plot: bool = False, predictor: bool = False,
                     type: str = None):
    """
    :param uid2idx_vars:
    :param bus_index:
    :param region_solver:
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
    uid2sym_t = {}
    solved: bool = False
    alpha: float = 0.8
    reference_vars: List[Var] = list()

    # We add the buses variables to the model
    Pg = region_system.external_mapping[VarPowerFlowRefferenceType.P]
    Qg = region_system.external_mapping[VarPowerFlowRefferenceType.Q]
    Vm = bus_block.external_mapping[VarPowerFlowRefferenceType.Vm]
    Va = bus_block.external_mapping[VarPowerFlowRefferenceType.Va]

    delete_vars_from_block(region_system, [Pg, Qg])
    connection_block = Block()
    connection_block.event_dict = {Pg: Const(float(np.real(res.Sbus[bus_index] / grid.Sbase))),
                                   Qg: Const(float(np.imag(res.Sbus[bus_index] / grid.Sbase))),
                                   Vm: Const(float(np.abs(res.voltage[bus_index]))),
                                   Va: Const(float(np.angle(res.voltage[bus_index])))}

    new_event_dict = {}
    for key, val in region_system.event_dict.items():
        if isinstance(val, Const) and val.value is None:
            region_system.algebraic_vars.append(key)
        else:
            new_event_dict[key] = val
    region_system.event_dict = new_event_dict
    init_block = Block(
        children=[region_system, connection_block]
    )
    # 2 out of [Pg, Qg, Vm, Va] need to be deleted from the algebraic vars to have a square system
    init_block = block2implicit(init_block)
    solver = BlockSolver(init_block, region_time)

    while not solved:
        try:
            print(f'Trying dtau0 = {dtau0} with max_iter {max_iter}')
            x0_mdl, init_guess_mdl = solver.pseudo_transient_routine(x0.copy(), dtau0=dtau0, alter_params=alter_params,
                                                                     max_iter=max_iter, max_tries=1e2,
                                                                     plot=plot,
                                                                     predictor=predictor,
                                                                     verbose=True)
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
            raise e

    for var in reference_vars:
        init_block.event_dict[var] = Const(x0[uid2idx_vars[var.uid]])

    init_guess.update(init_guess_mdl)

    # print('Pseudo-Transient ended')
    return x0, init_guess


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


def initialize_rms(grid: MultiCircuit,
                   power_flow_results,
                   use_init_values: bool = False,
                   logger: Logger = Logger(),
                   method: RmsInitializationMethod = RmsInitializationMethod.Explicit):
    """
    Initialize all RMS models
    :param grid:
    :param power_flow_results:
    :param use_init_values:
    :param logger:
    :param method
    :return:
    """

    # create time variable

    time = Var("global_time")

    # instantiate vars2device  and vars_glob_name2uid dicts

    vars2device: Dict[int, ALL_DEV_TYPES] = dict()
    device_vars_dict: Dict[ALL_DEV_TYPES, List[Var]] = dict()
    vars_glob_name2uid: Dict[str, int] = dict()
    # find events
    rms_events = grid.rms_events

    # already computed grid power flow

    bus_dict = dict()

    # balance equation arrays
    n = len(grid.buses)
    P: ObjVec = np.zeros(n, dtype=object)
    Q: ObjVec = np.zeros(n, dtype=object)
    P_used = np.zeros(n, dtype=int)
    Q_used = np.zeros(n, dtype=int)

    # initialize buses
    for i, elm in enumerate(grid.buses):
        # elm.initialize_rms()
        bus_dict[elm] = i
        for var in elm.rms_model.model.get_all_vars():
            vars2device[var.uid] = elm
            vars_glob_name2uid[var.name + elm.name] = var.uid

    # initialize branches
    for elm in grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
        # elm.initialize_rms()
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

    # initialize injections
    for elm in grid.get_injection_devices_iter():
        # elm.initialize_rms()
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
                    elm.rms_model.model.event_dict[param] = piecewise(time, np.array(events_info["times"]),
                                                                      np.array(events_info["values"]), default_value)

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
                logger.add_error("Isolated bus", value=i)
            else:
                mdl.algebraic_eqs.append(P[i])
                mdl.algebraic_eqs.append(Q[i])

    return compose_system_block(time, grid, power_flow_results, vars2device, vars_glob_name2uid, use_init_values,
                                method)
