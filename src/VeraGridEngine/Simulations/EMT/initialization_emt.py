# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List
import numpy as np

from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicVector, SymbolicParamsVectorInit
from VeraGridEngine.Utils.Symbolic.symbolic import get_expression_vars
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr


def init_explicit_emt(mdl: Block,
                      sys_vars: Dict[int, Var],
                      sys_diff_vars: Dict[int, Var],
                      variable_parameters: List[Var],
                      event_parameters_eqs: List[Expr | Const],
                      constant_parameters: List[Var],
                      init_guess: Dict[int, float],
                      diff_init_guess: Dict[int, float],
                      uid2idx_vars: Dict[int, int],
                      uid2idx_diff: Dict[int, int],
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
    :param sys_diff_vars:
    :type sys_diff_vars: Union[List[Tuple[int, str]], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], List[Tuple[int, str]], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var], List[Tuple[int, str]], Dict[int, VeraGridEngine.Utils.Symbolic.symbolic.Var]]
    :param variable_parameters:
    :type variable_parameters: List[VeraGridEngine.Utils.Symbolic.symbolic.Var]
    :param event_parameters_eqs:
    :type event_parameters_eqs:
    :param constant_parameters:
    :type constant_parameters: List[VeraGridEngine.Utils.Symbolic.symbolic.Var]
    :param init_guess:
    :type init_guess: Dict[Tuple[int, str], float]
    :param diff_init_guess:
    :type diff_init_guess: Dict[Tuple[int, str], float]
    :param uid2idx_vars:
    :type uid2idx_vars: Dict[int, int]
    :param uid2idx_diff:
    :type uid2idx_diff: Dict[int, int]
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

    # Initialize array for model variables and derivatives
    x = np.ones(len(sys_vars))
    dx = np.zeros(len(sys_diff_vars))  # Initialized to zero as default

    # Assign initial guesses for known variables
    for uid, val in init_guess.items():
        x[uid2idx_vars[uid]] = val

    # Initialize known derivatives from initial guess (if any provided)
    for uid, val in diff_init_guess.items():
        dx[uid2idx_diff[uid]] = val

    # Initialize array for constant model params
    params_array = np.zeros(len(constant_parameters))
    for param, const in mdl.parameters.items():
        params_array[uid2idx_params[param.uid]] = const.value

    # Compute and assign known event parameters value (initial pass)
    event_params_array = np.ones(len(variable_parameters))
    for event_param in mdl.event_dict.keys():
        eq = mdl.event_dict[event_param]
        if (isinstance(eq, Const) and eq.value is not None) or not isinstance(eq, Const):
            eq_fn = SymbolicParamsVectorInit([eq], compiler_names_dict, alias_names_dict, VARS_NAME,
                                             VARIABLE_PARAMS_NAME, TIME_NAME)
            param_val = float(eq_fn(x, event_params_array, 0.0)[0])
            event_params_array[uid2idx_event_params[event_param.uid]] = param_val

    # Tracking resolved items: variables and derivatives
    vars_initialized: List[int] = list()
    diff_vars_initialized: List[int] = list()

    # Target counts: all variables in init_eqs and all diff_vars in diff_init_eqs
    total_to_init = len(mdl.init_eqs) + len(mdl.diff_init_eqs)

    while (len(vars_initialized) + len(diff_vars_initialized)) < total_to_init:
        progress = False
        init_count_start = len(vars_initialized) + len(diff_vars_initialized)

        # --- PART 1: Resolve init_eqs (Algebraic and State variables) ---
        for var, eq in mdl.init_eqs.items():
            if var.uid not in vars_initialized:
                vars_needed = get_expression_vars(eq)

                # Check if all dependencies are ready
                calculate_now = True
                for v_dep in vars_needed:
                    if v_dep in mdl.event_dict.keys():
                        if isinstance(mdl.event_dict[v_dep], Const) and mdl.event_dict[v_dep].value is None:
                            calculate_now = False
                    else:
                        if v_dep.uid not in init_guess and v_dep.uid != var.uid:
                            calculate_now = False

                if calculate_now:
                    # Logic for Parameters (Event Dict)
                    if var in mdl.event_dict.keys():
                        eq_fn = SymbolicParamsVectorInit([eq], compiler_names_dict, alias_names_dict, VARS_NAME,
                                                         VARIABLE_PARAMS_NAME, TIME_NAME)
                        param_val = float(eq_fn(x, event_params_array, 0.0)[0])
                        mdl.event_dict[var] = Const(param_val)
                        event_params_array[uid2idx_event_params[var.uid]] = param_val

                        idx_param = variable_parameters.index(var)
                        if event_parameters_eqs[idx_param].value is None:
                            event_parameters_eqs[idx_param] = Const(param_val)

                    # Logic for Variables (Algebraic/States)
                    else:
                        vars_in_eqs = get_expression_vars(eq)
                        eq_fn = SymbolicVector([eq], compiler_names_dict, alias_names_dict, VARS_NAME,
                                               DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME)

                        if var not in vars_in_eqs:
                            # Explicit assignment
                            init_val = float(eq_fn(x, dx, event_params_array, params_array)[0])
                        else:
                            # Implicit/Iterative resolution (Small Fixed-point iteration)
                            init_val = 0
                            tol = 1e-8
                            error = 1
                            alpha = 1.3
                            x0 = 1.2
                            x[uid2idx_vars[var.uid]] = x0
                            while error > tol:
                                try:
                                    init_val = float(eq_fn(x, dx, event_params_array, params_array)[0])
                                except:
                                    x[uid2idx_vars[var.uid]] = -0.1
                                    init_val = float(eq_fn(x, dx, event_params_array, params_array)[0])
                                x[uid2idx_vars[var.uid]] = (1 - alpha) * x0 + alpha * init_val
                                error = np.linalg.norm(init_val - x0)
                                x0 = x[uid2idx_vars[var.uid]]

                        init_guess[var.uid] = init_val
                        x[uid2idx_vars[var.uid]] = init_val

                    vars_initialized.append(var.uid)
                    progress = True

        # --- PART 2: Resolve diff_init_eqs (Derivatives) ---
        for d_var, eq in mdl.diff_init_eqs.items():
            if d_var.uid not in diff_vars_initialized:
                # Get dependencies for the derivative RHS
                deps_needed = get_expression_vars(eq)

                calculate_now = True
                for v_dep in deps_needed:
                    # Check if dependency is a parameter not yet resolved
                    if v_dep in mdl.event_dict.keys():
                        if isinstance(mdl.event_dict[v_dep], Const) and mdl.event_dict[v_dep].value is None:
                            calculate_now = False
                    # Check if dependency is a variable not yet initialized
                    elif v_dep.uid not in init_guess:
                        calculate_now = False

                if calculate_now:
                    # Evaluate derivative RHS: dx_i = f(x, p)
                    eq_fn = SymbolicVector([eq], compiler_names_dict, alias_names_dict, VARS_NAME,
                                           DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME)

                    # Compute derivative value using current state x and params
                    init_val = float(eq_fn(x, dx, event_params_array, params_array)[0])

                    # Store in diff_init_guess and update dx vector
                    diff_init_guess[d_var.uid] = init_val
                    dx[uid2idx_diff[d_var.uid]] = init_val

                    diff_vars_initialized.append(d_var.uid)
                    progress = True

        if not progress:
            unresolved_vars = [v.name for v in mdl.init_eqs if v.uid not in vars_initialized]
            unresolved_diff = [v.name for v in mdl.diff_init_eqs if v.uid not in diff_vars_initialized]
            raise RuntimeError(f"Unresolvable equations: Vars: {unresolved_vars}, Diffs: {unresolved_diff}")

    return init_guess, diff_init_guess


def init_pseudo_transient():
    """
    initialize model using pseudotransient method
    :return:
    :rtype:
    """
    raise NotImplementedError(f'pseudotransient initialization method not implemented yet')
