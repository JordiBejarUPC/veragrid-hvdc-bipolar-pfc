# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List
import numpy as np

from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicVector, SymbolicParamsVectorInit
from VeraGridEngine.Utils.Symbolic.symbolic import  get_expression_vars
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const



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


def init_explicit(mdl: Block,
                  sys_vars:Dict[int, Var],
                  variable_parameters:List[Var],
                  constant_parameters:List[Var],
                  init_guess: Dict[int, float],
                  uid2idx_vars: Dict[int, int],
                  uid2idx_params:Dict[int, int],
                  uid2idx_event_params:Dict[int, int],
                  compiler_names_dict:Dict[int, str],
                  alias_names_dict:Dict[int, str],
                  VARIABLE_PARAMS_NAME: str,
                  TIME_NAME:str,
                  VARS_NAME:str,
                  DIFF_NAME:str,
                  CONSTANT_PARAMS_NAME:str):
    """
    Initialize using explicit equations
    """

    # initialize array for model variables
    #this is general but has to be here because needs the total length of variables array
    x = np.ones(len(sys_vars))

    # assign initial guesses for known variables

    for uid, val in init_guess.items():
        x[uid2idx_vars[uid]] = val

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
                                                   DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME)
                            init_val = float(eq_fn(x, np.ones(1), event_params_array, params_array)[0])
                            init_guess[var.uid] = init_val
                            x[uid2idx_vars[var.uid]] = init_val
                        else:
                            eq_fn = SymbolicVector([eq], compiler_names_dict, alias_names_dict, VARS_NAME, DIFF_NAME,
                                                   VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME)
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
    raise NotImplementedError(f'pseudotransient initialization method not implemented yet')