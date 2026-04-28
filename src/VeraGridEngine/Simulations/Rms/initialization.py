# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import cProfile
import time
from copy import deepcopy
import traceback
from typing import Dict, List, Tuple, Any
import numpy as np
from collections import defaultdict, deque

from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler
import scipy.sparse as sp

from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicVector, SymbolicParamsVectorInit, SymbolicDerivative
from VeraGridEngine.Utils.Symbolic.symbolic import get_expression_vars
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, find_vars_order
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from VeraGridEngine.basic_structures import Vec





def add_items(blk, init_vars, init_event):
    """
    adds items from a block to the dictionary
    :param blk:
    :type blk:
    :param init_vars:
    :param init_event:
    init_dict
    :return:
    :rtype:
    """

    init_vars.update(blk.init_eqs)
    init_event.update(blk.event_dict)

def build_init_dict(mdl, init_vars, init_event):
    """
    builds initialization dictionary from mdl
    :param mdl:
    :type mdl:
    :param init_vars:
    :param init_event:
    :type init_vars:
    init_dict
    :return:
    :rtype:
    """
    add_items(mdl, init_vars, init_event)
    for blk in mdl.children:
        build_init_dict(blk, init_vars, init_event)



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

def solve_secant(eq_fn, x, idx, event_params_array, params_array,
                 tol=1e-8, max_iter=50, seed: float | None = None, fallback_seed: float = 10.0):
    if seed is not None and np.isfinite(seed):
        x0 = float(seed)
    elif np.isfinite(x[idx]):
        x0 = float(x[idx])
    else:
        x0 = float(fallback_seed)

    x1 = x0 + 0.1 if abs(x0) < 1e-6 else x0 * 1.1

    for _ in range(max_iter):

        x[idx] = x0
        f0 = float(eq_fn(x, np.ones(1), event_params_array, params_array)[0]) - x0
        if not np.isfinite(f0):
            x0 = float(fallback_seed)
            x1 = x0 + 0.1 if abs(x0) < 1e-6 else x0 * 1.1
            continue

        x[idx] = x1
        f1 = float(eq_fn(x, np.ones(1), event_params_array, params_array)[0]) - x1
        if not np.isfinite(f1):
            x1 = x0 + 0.1 if abs(x0) < 1e-6 else x0 * 1.1
            continue

        if abs(f1) < tol:
            return x1

        denom = (f1 - f0)
        if abs(denom) < 1e-12:
            break

        x2 = x1 - f1 * (x1 - x0) / denom
        if not np.isfinite(x2):
            raise ValueError(
                f"Secant init produced non-finite iterate at idx={idx}: x0={x0}, x1={x1}, x2={x2}"
            )

        x0, x1 = x1, x2

    if not np.isfinite(x1):
        raise ValueError(f"Secant init failed to converge to a finite value at idx={idx}")

    return x1

def solve_newton(eq_fn, x, idx, event_params_array, params_array,
                 dummy_diff,
                 tol=1e-8, max_iter=20, h=1e-6):

    x0 = x[idx]

    for _ in range(max_iter):

        x[idx] = x0
        fx = float(eq_fn(x, dummy_diff, event_params_array, params_array)[0])

        # g(x) = f(x) - x
        gx = fx - x0

        if abs(gx) < tol:
            return x0

        # numeric derivative
        x[idx] = x0 + h
        fx_h = float(eq_fn(x, dummy_diff, event_params_array, params_array)[0])

        g_prime = (fx_h - fx)/h - 1.0

        if abs(g_prime) < 1e-12:
            break

        x0 = x0 - gx / g_prime

    return x0


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

    rms_compiler = RMSCompiler(
        variables=list(sys_vars.values()),
        diff_vars=list(),
        v_params=variable_parameters,
        c_params=constant_parameters,
        dt_var= Var("dt"),
        compiler_names_dict=compiler_names_dict
    )

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
    # for event_param in mdl.event_dict.keys():
    #     eq = mdl.event_dict[event_param]
    #
    #     if (isinstance(eq, Const) and eq.value is not None) or not isinstance(eq, Const):
    #         vars_list = find_vars_order(eq)
    #
    #         uid_bindings: Dict[int, float] = {
    #             var.uid: event_params_array[uid2idx_event_params[var.uid]]
    #             for var in vars_list
    #         }
    #         result = eq.eval_uid(uid_bindings)
    #         # eq_fn = SymbolicParamsVectorInit([eq], compiler_names_dict, alias_names_dict, VARS_NAME,
    #         #                                  VARIABLE_PARAMS_NAME, TIME_NAME)
    #         # result = float(eq_fn(x, event_params_array, 0.0)[0])
    #         event_params_array[uid2idx_event_params[event_param.uid]] = result

    # unify event_dict and init_equations
    init_vars = dict()
    init_event = dict()
    build_init_dict(mdl, init_vars, init_event)

    for key, val in init_event.items():
        if not(isinstance(val, Const) and val.value is None):
            init_vars[key] = val
        else:
            pass

    # init_dict = mdl.event_dict.copy()
    # init_dict.update(mdl.init_eqs)

    # compute and assign missing init_vars and None event parameters

    ####################################################################################################################################

    # construct graph of dependencies
    graph = defaultdict(list)
    in_degree = defaultdict(int)

    dependencies = {}

    for var, eq in init_vars.items():

        vars_in_eq = get_expression_vars(eq)
        deps = [v for v in vars_in_eq if v in init_vars]

        dependencies[var] = deps

        for dep in deps:
            if dep.uid != var.uid:
                graph[dep].append(var)
                in_degree[var] += 1

        if var not in in_degree:
            in_degree[var] = 0

    # topological sort
    queue = deque([var for var in in_degree if in_degree[var] == 0])
    topo_order = []

    while queue:
        u = queue.popleft()
        topo_order.append(u)

        for v in graph[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if len(topo_order) != len(init_vars):
        raise RuntimeError("Cycle detected between different variables")

    def _resolve_numeric(value):
        if isinstance(value, Var):
            if value.uid in uid2idx_event_params:
                return float(event_params_array[uid2idx_event_params[value.uid]])
            if value.uid in uid2idx_vars:
                return float(x[uid2idx_vars[value.uid]])
            if value.uid in uid2idx_params:
                return float(params_array[uid2idx_params[value.uid]])
            if value.uid in init_guess:
                return float(init_guess[value.uid])
            raise ValueError(f"Could not resolve numeric value for '{value.name}' (uid={value.uid})")

        return float(value)

    # evaluate
    for var in topo_order:
        eq = init_vars[var]
        vars_list = find_vars_order(eq)

        if var in init_event.keys():
            uid_bindings: Dict[int, float] = {}
            for vr in vars_list:
                if vr.uid in uid2idx_event_params:
                    uid_bindings.update({vr.uid: event_params_array[uid2idx_event_params[vr.uid]]})
                elif vr.uid in uid2idx_vars:
                    uid_bindings.update({vr.uid: x[uid2idx_vars[vr.uid]]})
                elif vr.uid in uid2idx_params:
                    uid_bindings.update({vr.uid: params_array[uid2idx_params[vr.uid]]})

            missing = [f"{vr.name}:{vr.uid}" for vr in vars_list if vr.uid not in uid_bindings]
            if len(missing) > 0:
                raise ValueError(
                    f"Explicit init could not evaluate event equation for '{var.name}' (uid={var.uid}). "
                    f"Missing bindings: {', '.join(missing)}"
                )

            result = eq.eval_uid(uid_bindings)
            # eq_fn = SymbolicParamsVectorInit([eq], compiler_names_dict, alias_names_dict, VARS_NAME,
            #                                  VARIABLE_PARAMS_NAME, TIME_NAME)
            #
            # result = float(eq_fn(x, event_params_array, 0.0)[0])
            resolved_result = _resolve_numeric(result)
            if not np.isfinite(resolved_result):
                raise ValueError(
                    f"Explicit init produced non-finite event value for '{var.name}' (uid={var.uid}): "
                    f"{resolved_result}. Equation: {eq}"
                )
            event_params_array[uid2idx_event_params[var.uid]] = resolved_result
            index = variable_parameters.index(var)
            event_parameters_eqs[index] = Const(resolved_result)
        elif var.base_var is None:
            # check if implicit equation
            is_self_implicit = var in dependencies[var]

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

                missing = [f"{vr.name}:{vr.uid}" for vr in vars_list if vr.uid not in uid_bindings]
                if len(missing) > 0:
                    raise ValueError(
                        f"Explicit init could not evaluate equation for '{var.name}' (uid={var.uid}). "
                        f"Missing bindings: {', '.join(missing)}"
                    )

                result = eq.eval_uid(uid_bindings)
                # eq_fn = rms_compiler.compile_rhs([eq], "equation")
                # result = float(eq_fn(x, np.ones(1), event_params_array, params_array)[0])
                resolved_result = _resolve_numeric(result)
                if not np.isfinite(resolved_result):
                    raise ValueError(
                        f"Explicit init produced non-finite state/algebraic value for '{var.name}' (uid={var.uid}): "
                        f"{resolved_result}. Equation: {eq}"
                    )
                init_guess[var.uid] = resolved_result
                x[uid2idx_vars[var.uid]] = resolved_result

            else:
                # compile equations
                eq_fn = rms_compiler.compile_rhs([eq], "equation")

                idx = uid2idx_vars[var.uid]

                # solve using secant method
                init_val = solve_secant(
                    eq_fn=eq_fn,
                    x=x,
                    idx=idx,
                    event_params_array=event_params_array,
                    params_array=params_array,
                    tol=1e-8,
                    max_iter=50,
                    seed=init_guess.get(var.uid, None),
                )

                if not np.isfinite(init_val):
                    raise ValueError(
                        f"Explicit init produced non-finite implicit solve value for '{var.name}' "
                        f"(uid={var.uid}): {init_val}. Equation: {eq}"
                    )

                init_guess[var.uid] = init_val
                x[uid2idx_vars[var.uid]] = init_val

    # Debug print: show initialized values for all variables/params in this model
    seen = set()
    debug_vars = list(mdl.algebraic_vars) + list(mdl.state_vars) + list(mdl.diff_vars)
    for var in debug_vars:
        if var.uid in seen:
            continue
        seen.add(var.uid)

        if var.uid in uid2idx_vars:
            print(f"DEBUG_INIT_ALL: {var.name} = {x[uid2idx_vars[var.uid]]}")


def init_custom(mdl, init_guess):
    for lst in [mdl.state_vars, mdl.algebraic_vars]:
        for var in lst:
            init_guess[var.uid] = mdl.init_values[var.uid]





class PseudoTransientInitProblem:
    """
    Lightweight problem class for pseudo-transient initialization of a single device block.
    Similar interface to RmsProblemDae but for initialization only.
    """
    
    def __init__(self,
                 block: Block,
                 x_global: Vec,
                 compiler_names_dict: Dict[int, str],
                 alias_names_dict: Dict[int, str],
                 uid2idx_vars: Dict[int, int],
                 variable_parameters: List[Var],
                 constant_parameters: List[Var],
                 VARS_NAME: str = "vars",
                 DIFF_NAME: str = "diff",
                 VARIABLE_PARAMS_NAME: str = "vprms",
                 CONSTANT_PARAMS_NAME: str = "cprms"):
        """
        Initialize problem for pseudo-transient initialization.
        """

        self.x_global = x_global
        self.block = block
        self.compiler_names_dict = compiler_names_dict
        self.alias_names_dict = alias_names_dict
        self._uid2idx_vars_global = uid2idx_vars
        self._variable_parameters = variable_parameters
        self._constant_parameters = constant_parameters

        event_uid_map = {v.uid: eq for v, eq in block.event_dict.items()}
        mode_uid_map = {v.uid: eq for v, eq in block.mode_dict.items()}
        param_uid_map = {v.uid: c for v, c in block.parameters.items()}
        
        # Get block's variables (state + algebraic)
        self._state_vars = list(block.state_vars)
        self._algebraic_vars = list(block.algebraic_vars)
        self._all_vars = self._state_vars + self._algebraic_vars
        self._n_vars = len(self._all_vars)
        self._n_states = len(self._state_vars)
        self._diff_vars = list(block.diff_vars)

        # Build local indexing for this block initialization problem.
        self._uid2idx_vars = {v.uid: i for i, v in enumerate(self._all_vars)}
        self._uid2idx_diff = {v.uid: i for i, v in enumerate(self._diff_vars)}

        self._compiler_names_dict_local = dict(compiler_names_dict)
        self._alias_names_dict_local = dict(alias_names_dict)

        for uid, i in self._uid2idx_vars.items():
            self._compiler_names_dict_local[uid] = f"{VARS_NAME}[{i}]"
            self._alias_names_dict_local[uid] = f"{VARS_NAME}_{i}"

        for uid, i in self._uid2idx_diff.items():
            self._compiler_names_dict_local[uid] = f"{DIFF_NAME}[{i}]"
            self._alias_names_dict_local[uid] = f"{DIFF_NAME}_{i}"
        
        # Initialize parameter arrays
        self._variable_parameters_values = np.zeros(len(variable_parameters), dtype=float)
        for i, p in enumerate(variable_parameters):
            if p.uid in event_uid_map:
                eq = event_uid_map[p.uid]
                if isinstance(eq, Const) and eq.value is not None:
                    self._variable_parameters_values[i] = float(eq.value)
            elif p.uid in mode_uid_map:
                eq = mode_uid_map[p.uid]
                if isinstance(eq, Const) and eq.value is not None:
                    self._variable_parameters_values[i] = float(eq.value)
        self._constant_params = np.array([
            (param_uid_map[p.uid].value if p.uid in param_uid_map and param_uid_map[p.uid] is not None else 0.0)
            for p in constant_parameters
        ], dtype=float)
        
        # Compile functions
        self._compile_functions(VARS_NAME, DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME)
    
    def _compile_functions(self, VARS_NAME: str, DIFF_NAME: str,
                          VARIABLE_PARAMS_NAME: str, CONSTANT_PARAMS_NAME: str):
        """Compile RHS and derivative functions for the block."""
        # Collect all equations
        all_eqs = list(self.block.state_eqs) + list(self.block.algebraic_eqs)
        
        # Compile RHS function
        if all_eqs:
            self._rhs_fn = SymbolicVector(
                all_eqs,
                self._compiler_names_dict_local,
                self._alias_names_dict_local,
                VARS_NAME,
                DIFF_NAME,
                VARIABLE_PARAMS_NAME,
                CONSTANT_PARAMS_NAME
            )
        else:
            self._rhs_fn = None
        
        # Compile derivative function
        self._derivative_fn = SymbolicDerivative(
            vars=self._all_vars,
            uid2idx_vars=self._uid2idx_vars,
            diff_vars=self._diff_vars,
            compiler_names_dict=self._compiler_names_dict_local
        )
    
    def get_all_vars_number(self) -> int:
        return self._n_vars
    
    def get_states_number(self) -> int:
        return self._n_states
    
    def get_algebraic_var_number(self) -> int:
        return len(self._algebraic_vars)
    
    def get_diff_var_number(self) -> int:
        return len(self._diff_vars)
    
    def get_algebraic_vars(self):
        return self._algebraic_vars

    def algebraic_vars(self):
        return self._algebraic_vars

    def state_vars(self):
        return self._state_vars
    
    def rhs_algebraic(self, x: Vec, dx: Vec) -> Vec:
        """Evaluate RHS for algebraic equations."""
        if self._rhs_fn is None:
            return np.array([])
        
        full_rhs = self._rhs_fn(x, dx, self._variable_parameters_values, self._constant_params)
        # Return only algebraic part
        if self._n_states > 0:
            return full_rhs[self._n_states:]
        return full_rhs
    
    def rhs_state(self, x: Vec, dx: Vec) -> Vec:
        """Evaluate RHS for state equations."""
        if self._rhs_fn is None or self._n_states == 0:
            return np.array([])
        
        full_rhs = self._rhs_fn(x, dx, self._variable_parameters_values, self._constant_params)
        return full_rhs[:self._n_states]
    
    def get_dx(self, x: Vec, xn: Vec, dx: Vec, h: float) -> Vec:
        """Compute derivatives."""
        return self._derivative_fn(x, xn, dx, h)
    
    def update_variable_params(self, t: float):
        """Update variable parameters at time t."""
        for i, param in enumerate(self._variable_parameters):
            if param in self.block.event_dict:
                eq = self.block.event_dict[param]
                if isinstance(eq, Const):
                    self._variable_parameters_values[i] = eq.value

    def _compute_numerical_jacobian(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """Compute Jacobian numerically using finite differences."""
        n_total = self._n_vars
        if n_total == 0:
            return sp.csc_matrix((0, 0))

        # Compute RHS at current point
        rhs = np.array(self._compute_rhs_full(x, dx, h), dtype=float, copy=True)

        # Numerical Jacobian
        base_eps = 1e-7
        J_dense = np.zeros((len(rhs), n_total))

        for j in range(n_total):
            x_perturbed = x.copy()
            step = base_eps * (1.0 + abs(float(x[j])))
            x_perturbed[j] += step
            rhs_perturbed = np.array(self._compute_rhs_full(x_perturbed, dx, h), dtype=float, copy=True)
            J_dense[:, j] = (rhs_perturbed - rhs) / step

        return sp.csc_matrix(J_dense)

    def _compute_rhs_full(self, x: Vec, dx: Vec, h: float) -> Vec:
        """Compute full RHS (state + algebraic) for Jacobian computation."""
        if self._rhs_fn is None:
            return np.array([])
        return self._rhs_fn(x, dx, self._variable_parameters_values, self._constant_params)

    def get_j11(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """Jacobian of state equations w.r.t. state variables."""
        if self._n_states == 0:
            return sp.csc_matrix((0, 0))
        J_full = self._compute_numerical_jacobian(x, dx, h)
        return J_full[:self._n_states, :self._n_states]

    def get_j12(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """Jacobian of state equations w.r.t. algebraic variables."""
        if self._n_states == 0:
            return sp.csc_matrix((0, self.get_algebraic_var_number()))
        J_full = self._compute_numerical_jacobian(x, dx, h)
        n_alg = self.get_algebraic_var_number()
        return J_full[:self._n_states, self._n_states:self._n_states + n_alg]

    def get_j21(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """Jacobian of algebraic equations w.r.t. state variables."""
        n_alg = self.get_algebraic_var_number()
        if self._n_states == 0 or n_alg == 0:
            return sp.csc_matrix((n_alg, self._n_states))
        J_full = self._compute_numerical_jacobian(x, dx, h)
        return J_full[self._n_states:, :self._n_states]

    def get_j22(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """Jacobian of algebraic equations w.r.t. algebraic variables."""
        n_alg = self.get_algebraic_var_number()
        if n_alg == 0:
            return sp.csc_matrix((0, 0))
        if self._n_states == 0:
            return self._compute_numerical_jacobian(x, dx, h)
        J_full = self._compute_numerical_jacobian(x, dx, h)
        return J_full[self._n_states:, self._n_states:self._n_states + n_alg]

    @property
    def uid2idx_vars(self):
        return self._uid2idx_vars


def init_pseudo_transient(mdl: Block,
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
                          CONSTANT_PARAMS_NAME: str,
                          dtau0: float = 1e-3,
                          max_iter: int = 100,
                          tol: float = 1e-6,
                          verbose: bool = False):
    """
    Initialize model using pseudo-transient method.
    
    Similar interface to init_explicit but uses pseudo-transient simulation
    instead of explicit equation evaluation.
    """
    # Import here to avoid circular imports
    from VeraGridEngine.Simulations.Rms.numerical.pseudo_transient import PseudoTransient

    # Work on a copy so initialization rewrites do not alter the original model.
    mdl_work = deepcopy(mdl)
    mdl_work.unify_blocks()

    # Initialization-only stabilization: relax hard limiter bounds to avoid
    # branch-locking/flat Jacobian regions during pseudo-transient startup.
    wide_limits = {
        "Pmax": 1e3,
        "Pmin": -1e3,
        "Uo": 1e3,
        "Uc": -1e3,
        "VaMaxPu": 1e3,
        "VaMinPu": -1e3,
        "EfeMaxPu": 1e3,
        "EfeMinPu": -1e3,
        "V_oelmax": 1e3,
        "V_oelmin": -1e3,
        "V_invmax": 1e3,
        "V_invmin": -1e3,
    }

    for blk in mdl_work.get_all_blocks():
        for var, value in list(blk.event_dict.items()):
            if not isinstance(var, Var):
                continue
            if var.name not in wide_limits:
                continue
            if not isinstance(value, Const):
                continue
            blk.event_dict[var] = Const(float(wide_limits[var.name]))

    # Build global snapshot vector from current init guess.
    x_global = np.zeros(len(uid2idx_vars), dtype=float)
    for uid, val in init_guess.items():
        if uid in uid2idx_vars and val is not None:
            gidx = uid2idx_vars[uid]
            if 0 <= gidx < x_global.size:
                x_global[gidx] = float(val)

    # Freeze PF anchors in this local model: P, Q, Vm, Va, Vdc.
    pf_var_references = [
        VarPowerFlowRefferenceType.P,
        VarPowerFlowRefferenceType.Q,
        VarPowerFlowRefferenceType.Vm,
        VarPowerFlowRefferenceType.Va,
        VarPowerFlowRefferenceType.Vdc,
    ]
    for pf_ref in pf_var_references:
        if pf_ref not in mdl_work.external_mapping:
            continue
        pf_var = mdl_work.external_mapping[pf_ref]
        if not isinstance(pf_var, Var):
            continue
        if pf_var.uid not in uid2idx_vars:
            continue

        pf_val = x_global[uid2idx_vars[pf_var.uid]]

        for blk in mdl_work.get_all_blocks():
            remove_alg_idx = [i for i, v in enumerate(blk.algebraic_vars)
                              if isinstance(v, Var) and v.uid == pf_var.uid]
            for i in reversed(remove_alg_idx):
                del blk.algebraic_vars[i]

            blk.state_vars = [v for v in blk.state_vars if isinstance(v, Var) and v.uid != pf_var.uid]
            blk.diff_vars = [v for v in blk.diff_vars if isinstance(v, Var) and v.uid != pf_var.uid]

        mdl_work.update_model(pf_var, Const(pf_val))

    # Promote unresolved event parameters (Const(None)) to algebraic unknowns when init eq exists.
    for blk in mdl_work.get_all_blocks():
        unresolved = [
            var for var, value in blk.event_dict.items()
            if isinstance(var, Var) and isinstance(value, Const) and value.value is None
        ]
        for var in unresolved:
            if not any(v.uid == var.uid for v in blk.algebraic_vars):
                blk.algebraic_vars.append(var)
            del blk.event_dict[var]
    
    # Create problem for this device
    problem = PseudoTransientInitProblem(
        block=mdl_work,
        x_global=x_global,
        compiler_names_dict=compiler_names_dict,
        alias_names_dict=alias_names_dict,
        uid2idx_vars=uid2idx_vars,
        variable_parameters=variable_parameters,
        constant_parameters=constant_parameters,
        VARS_NAME=VARS_NAME,
        DIFF_NAME=DIFF_NAME,
        VARIABLE_PARAMS_NAME=VARIABLE_PARAMS_NAME,
        CONSTANT_PARAMS_NAME=CONSTANT_PARAMS_NAME
    )
    # Attach global index maps for richer diagnostics in the pseudo-transient solver.
    problem._uid2idx_params = uid2idx_params
    problem._uid2idx_event_params = uid2idx_event_params
    
    # Use the existing PseudoTransient solver
    # Note: h parameter is not used for initialization, we set it to 1.0

    solver = PseudoTransient(
        problem=problem,
        h=1.0,
        dtau0=1e-6,
        dtau_max=1e-5,
        dtau_min=1e-6,
        tol=tol,
        max_iter=1000,
        verbose=verbose,
    )
    
    # Build initial guess: random baseline, then overwrite with known init_guess values.
    x0 = np.random.rand(problem.get_all_vars_number())
    local_vars = list(mdl_work.state_vars) + list(mdl_work.algebraic_vars)
    for local_idx, var in enumerate(local_vars):
        if local_idx >= len(x0):
            continue
        if var.uid in init_guess and init_guess[var.uid] is not None:
            x0[local_idx] = float(init_guess[var.uid])

    # Re-evaluate runtime variable parameters from declared equations.
    ev0 = np.array(problem._variable_parameters_values, dtype=float, copy=True)
    params0 = np.array(problem._constant_params, dtype=float, copy=True)
    dx0 = np.zeros(problem.get_diff_var_number(), dtype=float)
    uid2idx_diff_empty: Dict[int, int] = dict()

    problem._variable_parameters_values = ev0
    
    # Run pseudo-transient simulation
    x_solution, _ = solver.simulate(plot=bool(verbose), x0=x0)

    # Validate final residual; fail fast on poor initialization.
    dx_check = np.zeros(problem.get_diff_var_number(), dtype=float)
    rhs_state = problem.rhs_state(x_solution, dx_check)
    rhs_algeb = problem.rhs_algebraic(x_solution, dx_check)
    residual_vec = np.r_[rhs_state, rhs_algeb]

    if not np.all(np.isfinite(residual_vec)):
        bad_idx = np.where(~np.isfinite(residual_vec))[0]
        bad_vals = residual_vec[bad_idx]
        raise RuntimeError(
            f"PseudoTransient final residual has NaN/Inf: bad_idx={bad_idx.tolist()}, "
            f"bad_vals={bad_vals.tolist()}"
        )

    residual_inf = float(np.linalg.norm(residual_vec, np.inf)) if residual_vec.size > 0 else 0.0
    residual_tol = max(float(tol), 1e-6)
    if residual_inf > residual_tol:
        raise RuntimeError(
            f"PseudoTransient final residual too large: "
            f"||r||_inf={residual_inf:.6e} > {residual_tol:.6e}"
        )

    # Update recovered values:
    # - system variables go to init_guess
    # - promoted runtime parameters go back to event_parameters_eqs as Const
    for local_idx, var in enumerate(local_vars):
        if local_idx >= len(x_solution):
            continue

        value = float(x_solution[local_idx])

        if var.uid in uid2idx_vars:
            init_guess[var.uid] = value
        elif var.uid in uid2idx_event_params:
            ep_idx = uid2idx_event_params[var.uid]
            if 0 <= ep_idx < len(event_parameters_eqs):
                event_parameters_eqs[ep_idx] = Const(value)

    return init_guess
