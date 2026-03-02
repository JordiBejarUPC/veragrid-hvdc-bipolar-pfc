# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List
import numpy as np
from collections import defaultdict, deque

from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicVector, SymbolicParamsVectorInit
from VeraGridEngine.Utils.Symbolic.symbolic import get_expression_vars
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, find_vars_order


# ask Maria for usages and delete
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


def init_explicit(mdl: Block,
                  sys_vars: Dict[int, Var],
                  variable_parameters: List[Var],
                  event_parameters_eqs: List[Expr | Const],
                  constant_parameters: List[Var],
                  init_guess: Dict[int, float],
                  uid2idx_vars: Dict[int, int],
                  uid2idx_params: Dict[int, int],
                  uid2idx_event_params: Dict[int, int],
                  compiler_names_dict: Dict[int, str],
                  alias_names_dict: Dict[int, str],
                  VARIABLE_PARAMS_NAME: str,
                  TIME_NAME: str,
                  VARS_NAME: str,
                  DIFF_NAME: str,
                  CONSTANT_PARAMS_NAME: str):
    """

    initialize model using explicit equations

    :param mdl:
    :type mdl: VeraGridEngine.Utils.Symbolic.block.Block
    :param sys_vars:
    :type sys_vars: Union[List[Tuple[int, str]], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], List[Tuple[int, str]], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], List[Tuple[int, str]], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var]]
    :param variable_parameters:
    :type variable_parameters: List[VeraGridEngine.Utils.Symbolic.symbolic.Var]
    :param event_parameters_eqs:
    :type event_parameters_eqs:
    :param constant_parameters:
    :type constant_parameters: List[VeraGridEngine.Utils.Symbolic.symbolic.Var]
    :param init_guess:
    :type init_guess: Dict[Tuple[int, str], float]
    :param uid2idx_vars:
    :type uid2idx_vars: Dict[int, int]
    :param uid2idx_params:
    :type uid2idx_params: Dict[int, int]
    :param uid2idx_event_params:
    :type uid2idx_event_params: Dict[int, int]
    :param compiler_names_dict:
    :type compiler_names_dict: Dict[int, str]
    :param alias_names_dict:
    :type alias_names_dict: Dict[int, str]
    :param VARIABLE_PARAMS_NAME:
    :type VARIABLE_PARAMS_NAME: str
    :param TIME_NAME:
    :type TIME_NAME: str
    :param VARS_NAME:
    :type VARS_NAME: str
    :param DIFF_NAME:
    :type DIFF_NAME: str
    :param CONSTANT_PARAMS_NAME:
    :type CONSTANT_PARAMS_NAME:
    :return:
    :rtype: Union[None, Tuple[Dict[Tuple[int, str], float], VeraGridEngine.Utils.Symbolic.block.Block]]
    """

    # initialize array for model variables
    x = np.ones(len(sys_vars))

    # assign initial guesses for known variables
    for uid, val in init_guess.items():
        x[uid2idx_vars[uid]] = val

    # initialize array for model params
    params_array = np.zeros(len(constant_parameters))

    # compute and assign parameters value
    for param, const in mdl.parameters.items():
        params_array[uid2idx_params[param.uid]] = const.value

    # compute and assign known event parameters value
    event_params_array = np.ones(len(variable_parameters))
    for event_param in mdl.event_dict.keys():
        eq = mdl.event_dict[event_param]

        if (isinstance(eq, Const) and eq.value is not None) or not isinstance(eq, Const):
            vars_list = find_vars_order(eq)

            uid_bindings: Dict[int, float] = {
                var.uid: event_params_array[uid2idx_event_params[var.uid]]
                for var in vars_list
            }
            result = eq.eval_uid(uid_bindings)
            # eq_fn = SymbolicParamsVectorInit([eq], compiler_names_dict, alias_names_dict, VARS_NAME,
            #                                  VARIABLE_PARAMS_NAME, TIME_NAME)
            # result = float(eq_fn(x, event_params_array, 0.0)[0])
            event_params_array[uid2idx_event_params[event_param.uid]] = result

    # compute and assign missing init_vars and None event parameters

    ####################################################################################################################################

    # construct graph of dependencies
    graph = defaultdict(list)
    in_degree = defaultdict(int)

    dependencies = {}

    for var, eq in mdl.init_eqs.items():

        vars_in_eq = get_expression_vars(eq)
        deps = [v.uid for v in vars_in_eq if v in mdl.init_eqs]

        dependencies[var.uid] = deps

        for dep_uid in deps:
            if dep_uid != var.uid:
                graph[dep_uid].append(var.uid)
                in_degree[var.uid] += 1

        if var.uid not in in_degree:
            in_degree[var.uid] = 0

    # topological sort
    queue = deque([uid for uid in in_degree if in_degree[uid] == 0])
    topo_order = []

    while queue:
        u = queue.popleft()
        topo_order.append(u)

        for v in graph[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if len(topo_order) != len(mdl.init_eqs):
        raise RuntimeError("Cycle detected between different variables")

    # evaluate
    for uid in topo_order:

        var = next(v for v in mdl.init_eqs if v.uid == uid)
        eq = mdl.init_eqs[var]
        vars_list = find_vars_order(eq)

        if var in mdl.event_dict.keys():
            uid_bindings: Dict[int, float] = {}
            for vr in vars_list:
                if vr.uid in uid2idx_event_params:
                    uid_bindings.update({vr.uid: event_params_array[uid2idx_event_params[vr.uid]]})
                elif vr.uid in uid2idx_vars:
                    uid_bindings.update({vr.uid: x[uid2idx_vars[vr.uid]]})

            result = eq.eval_uid(uid_bindings)
            # eq_fn = SymbolicParamsVectorInit([eq], compiler_names_dict, alias_names_dict, VARS_NAME,
            #                                  VARIABLE_PARAMS_NAME, TIME_NAME)
            #
            # result = float(eq_fn(x, event_params_array, 0.0)[0])
            mdl.event_dict[var] = Const(result)
            event_params_array[uid2idx_event_params[var.uid]] = result
            index = variable_parameters.index(var)
            if event_parameters_eqs[index].value is None:
                event_parameters_eqs[index] = Const(result)


        else:
            # check if implicit equation
            is_self_implicit = uid in dependencies[uid]

            if not is_self_implicit:
                uid_bindings: Dict[int, float] = {}
                vars_list = find_vars_order(eq)
                for vr in vars_list:
                    if vr.uid in uid2idx_event_params:
                        uid_bindings.update({vr.uid: event_params_array[uid2idx_event_params[vr.uid]]})
                    elif vr.uid in uid2idx_vars:
                        uid_bindings.update({vr.uid: x[uid2idx_vars[vr.uid]]})
                    elif vr.uid in uid2idx_params:
                        uid_bindings.update({vr.uid: params_array[uid2idx_params[vr.uid]]})

                result = eq.eval_uid(uid_bindings)
                # eq_fn = SymbolicVector([eq], compiler_names_dict, alias_names_dict, VARS_NAME,
                #                        DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME)
                # result = float(eq_fn(x, np.ones(1), event_params_array, params_array)[0])
                init_guess[var.uid] = result
                x[uid2idx_vars[var.uid]] = result

            else:
                eq_fn = SymbolicVector([eq], compiler_names_dict, alias_names_dict, VARS_NAME, DIFF_NAME,
                                       VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME)
                init_val = 0
                tol = 1e-8
                error = 1
                alpha = 1.3
                x0 = 1.2
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
                init_guess[var.uid] = init_val
                x[uid2idx_vars[var.uid]] = init_val


def init_pseudo_transient():
    """
    initialize model using pseudotransient method
    :return:
    :rtype:
    """
    raise NotImplementedError(f'pseudotransient initialization method not implemented yet')
