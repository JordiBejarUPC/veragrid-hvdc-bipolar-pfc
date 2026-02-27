# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List
import numpy as np

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
    vars_initialized: List[int] = list()
    while len(vars_initialized) < len(mdl.init_eqs):
        progress = False

        vars_init_at_start = len(vars_initialized)
        for var, eq in mdl.init_eqs.items():
            if var.uid not in vars_initialized:

                # get all the variables inside the initialization equation
                vars_needed = get_expression_vars(eq)

                calculate_now = True
                for v_init in vars_needed:
                    # check if this variable is already initialized
                    key_deps = v_init.uid

                    if v_init in mdl.event_dict.keys():
                        if isinstance(mdl.event_dict[v_init], Const) and mdl.event_dict[v_init].value is None:
                            calculate_now = False


                    else:
                        if key_deps not in init_guess and v_init.uid != var.uid:
                            calculate_now = False


                if calculate_now:

                    # We initialize the params with value None
                    if var in mdl.event_dict.keys():
                        if isinstance(eq, Const) and eq.value is not None:

                            raise ValueError(f"Parameter {var.name} already initialized")

                        else:
                            uid_bindings: Dict[int, float] = {}
                            vars_list = find_vars_order(eq)
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
                            index= variable_parameters.index(var)
                            if event_parameters_eqs[index].value is None:
                                event_parameters_eqs[index] = Const(result)

                    # We initialize the algebraic values
                    else:
                        vars_in_eqs = get_expression_vars(eq)

                        if var not in vars_in_eqs:
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

                    vars_initialized.append(var.uid)

        vars_init_at_end = len(vars_initialized)
        if vars_init_at_end > vars_init_at_start:
            progress = True

        if not progress:
            unresolved = [v.name for v in mdl.init_eqs if (v.uid, v.name) not in vars_initialized]
            raise RuntimeError(f"Unresolvable init equations: {unresolved}")


def init_pseudo_transient():
    """
    initialize model using pseudotransient method
    :return:
    :rtype:
    """
    raise NotImplementedError(f'pseudotransient initialization method not implemented yet')
