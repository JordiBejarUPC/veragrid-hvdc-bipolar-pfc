# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Tuple, Union, Optional
import numpy as np
from enum import Enum, auto
import time
import warnings
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from VeraGridEngine.enumerations import EmtInitializationMethod
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian, SymbolicVector
from VeraGridEngine.Utils.Symbolic.symbolic import get_expression_vars
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, find_vars_order


class InitializationStatus(Enum):
    """Enumeration to track the progress of the initialization solver."""
    PENDING = auto()
    RESOLVED = auto()
    FAILED = auto()


class EmtInitializationReport:
    """
    Stores the outcome of the EMT-native initialization workflow.
    """

    __slots__ = [
        "status",
        "method_requested",
        "method_used",
        "initial_residual_inf",
        "final_residual_inf",
        "newton_iterations",
        "pseudo_transient_steps",
        "unknown_var_count",
        "unresolved_state_count",
        "automatic_dx0_count",
        "elapsed_s",
        "message",
    ]

    def __init__(self, method_requested: EmtInitializationMethod) -> None:
        """
        Build an empty EMT initialization report.

        :param method_requested: Requested initialization workflow.
        :return: None
        """
        self.status: InitializationStatus = InitializationStatus.PENDING
        self.method_requested: EmtInitializationMethod = method_requested
        self.method_used: EmtInitializationMethod = EmtInitializationMethod.Explicit
        self.initial_residual_inf: float = 0.0
        self.final_residual_inf: float = 0.0
        self.newton_iterations: int = 0
        self.pseudo_transient_steps: int = 0
        self.unknown_var_count: int = 0
        self.unresolved_state_count: int = 0
        self.automatic_dx0_count: int = 0
        self.elapsed_s: float = 0.0
        self.message: str = ""


def build_uid_bindings(
        eq: Union[Expr, Const],
        event_params_array: np.ndarray,
        x: np.ndarray,
        params_array: np.ndarray,
        dx: np.ndarray,
        uid2idx_event_params: Dict[int, int],
        uid2idx_vars: Dict[int, int],
        uid2idx_params: Dict[int, int],
        uid2idx_diff: Dict[int, int]
) -> Dict[int, float]:
    """
    Builds a mapping of Unique Identifiers (UIDs) to their current numeric values.

    :param eq: The symbolic expression to analyze.
    :param event_params_array: Array containing resolved event parameters.
    :param x: Array containing state and algebraic variables.
    :param params_array: Array containing constant model parameters.
    :param dx: Array containing derivative values.
    :param uid2idx_event_params: Mapping of UID to index for event parameters.
    :param uid2idx_vars: Mapping of UID to index for variables.
    :param uid2idx_params: Mapping of UID to index for constants.
    :param uid2idx_diff: Mapping of UID to index for derivatives.
    :return: A dictionary mapping UIDs to their float values.
    """
    uid_bindings: Dict[int, float] = dict()
    vars_list: List[Var] = find_vars_order(eq)

    for vr in vars_list:
        resolved_value: Optional[float] = None
        event_idx: Optional[int] = uid2idx_event_params.get(vr.uid, None)
        state_idx: Optional[int] = uid2idx_vars.get(vr.uid, None)
        param_idx: Optional[int] = uid2idx_params.get(vr.uid, None)
        diff_idx: Optional[int] = uid2idx_diff.get(vr.uid, None)

        if event_idx is None:
            if state_idx is None:
                if param_idx is None:
                    if diff_idx is None:
                        resolved_value = None
                    else:
                        resolved_value = float(dx[diff_idx])
                else:
                    resolved_value = float(params_array[param_idx])
            else:
                resolved_value = float(x[state_idx])
        else:
            resolved_value = float(event_params_array[event_idx])

        if resolved_value is None:
            uid_bindings = uid_bindings
        else:
            uid_bindings[vr.uid] = resolved_value

    return uid_bindings


def event_param_is_resolved(v: Var, mdl: Block) -> bool:
    """
    Checks if an event parameter has been assigned a concrete value.

    :param v: The variable representing the event parameter.
    :param mdl: The symbolic model block.
    :return: True if resolved, False otherwise.
    """
    if v in mdl.event_dict:
        eqv: Union[Expr, Const] = mdl.event_dict[v]
        if isinstance(eqv, Const):
            if eqv.value is None:
                return False
            else:
                return True
        else:
            return True
    else:
        return True


def can_compute_init(
        var: Var,
        eq: Union[Expr, Const],
        mdl: Block,
        init_guess: Dict[int, float],
        diff_init_guess: Dict[int, float],
        uid2idx_diff: Dict[int, int],
        uid2idx_vars: Dict[int, int]
) -> bool:
    """
    Determines if an initialization equation is computable based on current knowns.

    :param var: Target variable.
    :param eq: The expression to evaluate.
    :param mdl: The model block.
    :param init_guess: Current variable guesses.
    :param diff_init_guess: Current derivative guesses.
    :param uid2idx_diff: UID map for derivatives.
    :param uid2idx_vars: UID map for variables.
    :return: Boolean indicating if all dependencies are met.
    """
    vars_needed: List[Var] = get_expression_vars(eq)
    for v_dep in vars_needed:
        if v_dep.uid == var.uid:
            dependency_ready: bool = True
        elif v_dep in mdl.event_dict:
            dependency_ready = event_param_is_resolved(v_dep, mdl)
        elif v_dep.uid in uid2idx_diff:
            dependency_ready = v_dep.uid in diff_init_guess
        elif v_dep.uid in uid2idx_vars:
            dependency_ready = v_dep.uid in init_guess
        else:
            dependency_ready = True

        if dependency_ready:
            dependency_ready = dependency_ready
        else:
            return False
    return True


def init_explicit_emt(
        mdl: Block,
        sys_vars: Dict[int, Var],
        sys_diff_vars: Dict[int, Var],
        variable_parameters: List[Var],
        event_parameters_eqs: List[Union[Expr, Const]],
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
        VARS_NAME: str,
        DIFF_NAME: str,
        CONSTANT_PARAMS_NAME: str,
        verbose: bool = False) -> Optional[Tuple[Dict[int, float], Dict[int, float]]]:
# ) -> Union[None, Tuple[Dict[int, float], Block]]:
    """
    Initializes the EMT model by solving initialization and differential equations.

    This function performs a topological-like resolution of model variables.
    It uses fixed-point iteration for self-referencing equations and handles
    dependencies between algebraic and differential states.

    :param mdl: Symbolic model block.
    :param sys_vars: Registry of system variables.
    :param sys_diff_vars: Registry of system differential variables.
    :param variable_parameters: List of parameters that change on events.
    :param event_parameters_eqs: Initial equations for event parameters.
    :param constant_parameters: List of constant parameters.
    :param init_guess: Initial guesses for variables.
    :param diff_init_guess: Initial guesses for derivatives.
    :param uid2idx_vars: Index map for variables.
    :param uid2idx_diff: Index map for derivatives.
    :param uid2idx_params: Index map for parameters.
    :param uid2idx_event_params: Index map for event parameters.
    :param compiler_names_dict: Map for variable naming in compilation.
    :param alias_names_dict: Map for variable aliases.
    :param VARIABLE_PARAMS_NAME: Name for variable parameter array.
    :param VARS_NAME: Name for state variable array.
    :param DIFF_NAME: Name for derivative array.
    :param CONSTANT_PARAMS_NAME: Name for constant parameter array.
    :param verbose: Whether to print explicit initialization diagnostics.
    :return: Updated initial guesses and modified model block.
    """

    # Initialize memory buffers for numerical evaluation
    # EMT solvers require flat arrays for efficient computation
    x: np.ndarray = np.ones(len(sys_vars))
    dx: np.ndarray = np.zeros(len(sys_diff_vars))

    # Hydrate buffers with existing user-provided guesses
    for uid, val in init_guess.items():
        if verbose:
            print(f"Var {sys_vars[uid].name} with uid= {uid} initialized with val: {val} ")
        x[uid2idx_vars[uid]] = val

    for uid, val in diff_init_guess.items():
        if verbose:
            print(f"Diff var {sys_diff_vars[uid].name} with uid= {uid} initialized with val: {val} ")
        dx[uid2idx_diff[uid]] = val

    # Setup constant parameter array
    params_array: np.ndarray = np.zeros(len(constant_parameters))
    for param, const in mdl.parameters.items():
        params_array[uid2idx_params[param.uid]] = const.value

    # Primary pass: resolve basic event parameters that are constant or immediate
    event_params_array: np.ndarray = np.ones(len(variable_parameters))
    for event_param in mdl.event_dict.keys():
        eq: Union[Expr, Const] = mdl.event_dict[event_param]

        # Determine if the expression is concrete enough to evaluate
        is_concrete_const: bool = isinstance(eq, Const) and eq.value is not None
        is_expression: bool = not isinstance(eq, Const)

        if is_concrete_const or is_expression:
            vars_list: List[Var] = find_vars_order(eq)
            # Bind current values for calculation
            uid_bindings: Dict[int, float] = dict()
            for var in vars_list:
                uid_bindings[var.uid] = float(event_params_array[uid2idx_event_params[var.uid]])

            result: float = eq.eval_uid(uid_bindings)
            event_params_array[uid2idx_event_params[event_param.uid]] = result
            if verbose:
                print(f"event_param:{event_param.name} initialized from events_dict with: {result}")
        else:
            event_param = event_param

    # Track pending equations that require dependency resolution
    init_pending: Dict[int, Tuple[Var, Union[Expr, Const]]] = dict()
    for v, e in mdl.init_eqs.items():
        init_pending[v.uid] = (v, e)

    diff_pending: Dict[int, Tuple[Var, Union[Expr, Const]]] = dict()
    for v, e in mdl.diff_init_eqs.items():
        diff_pending[v.uid] = (v, e)

    # Iterative solver loop
    while len(init_pending) > 0 or len(diff_pending) > 0:
        progress_made: bool = False

        # Solve for Algebraic/State variables
        for uid in list(init_pending.keys()):
            var, eq = init_pending[uid]
            if can_compute_init(var, eq, mdl, init_guess, diff_init_guess, uid2idx_diff, uid2idx_vars):

                # Logic for variables that are registered as event parameters
                if var in mdl.event_dict:
                    if isinstance(eq, Const) and eq.value is not None:
                        event_params_array[uid2idx_event_params[var.uid]] = float(eq.value)
                    else:
                        bindings: Dict[int, float] = build_uid_bindings(
                            eq, event_params_array, x, params_array, dx,
                            uid2idx_event_params, uid2idx_vars, uid2idx_params, uid2idx_diff
                        )
                        res: float = eq.eval_uid(bindings)
                        mdl.event_dict[var] = Const(res)
                        event_params_array[uid2idx_event_params[var.uid]] = res
                        print(f"event_param:{var.name} initialized from init_eqs with: {res}")


                        param_idx: int = variable_parameters.index(var)
                        if event_parameters_eqs[param_idx].value is None:
                            event_parameters_eqs[param_idx] = Const(res)
                        else:
                            event_parameters_eqs[param_idx] = event_parameters_eqs[param_idx]

                # Logic for standard algebraic variables
                else:
                    vars_in_eqs: List[Var] = get_expression_vars(eq)
                    if var not in vars_in_eqs:
                        # Direct assignment
                        bindings = build_uid_bindings(
                            eq, event_params_array, x, params_array, dx,
                            uid2idx_event_params, uid2idx_vars, uid2idx_params, uid2idx_diff
                        )
                        res = eq.eval_uid(bindings)
                        init_guess[var.uid] = res
                        x[uid2idx_vars[var.uid]] = res
                    else:
                        # Implicit resolution using a damped fixed-point iteration
                        eq_fn: SymbolicVector = SymbolicVector(
                            [eq], compiler_names_dict, alias_names_dict,
                            VARS_NAME, DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME
                        )

                        # Fixed-point parameters
                        tol: float = 1e-8
                        error: float = 1.0
                        alpha: float = 1.3
                        curr_x: float = 1.2

                        x[uid2idx_vars[var.uid]] = curr_x
                        while error > tol:
                            try:
                                # Evaluate expression with current state
                                eval_res: float = float(eq_fn(x, dx, event_params_array, params_array)[0])
                            except Exception:
                                # Fallback/Reset on numerical instability
                                x[uid2idx_vars[var.uid]] = -0.1
                                eval_res = float(eq_fn(x, dx, event_params_array, params_array)[0])

                            # Update with damping (Successive Over-Relaxation style)
                            x[uid2idx_vars[var.uid]] = (1 - alpha) * curr_x + alpha * eval_res
                            error = float(abs(eval_res - curr_x))
                            curr_x = float(x[uid2idx_vars[var.uid]])

                        init_guess[var.uid] = curr_x

                del init_pending[uid]
                progress_made = True
            else:
                uid = uid

        # Solve for Differential variables
        for uid in list(diff_pending.keys()):
            d_var, eq = diff_pending[uid]
            # Use separate check for diff equations to ensure variables are ready
            if can_compute_init(d_var, eq, mdl, init_guess, diff_init_guess, uid2idx_diff, uid2idx_vars):
                vars_in_eqs = get_expression_vars(eq)

                if d_var not in vars_in_eqs:
                    bindings = build_uid_bindings(
                        eq, event_params_array, x, params_array, dx,
                        uid2idx_event_params, uid2idx_vars, uid2idx_params, uid2idx_diff
                    )
                    res = eq.eval_uid(bindings)
                    diff_init_guess[d_var.uid] = res
                    dx[uid2idx_diff[d_var.uid]] = res
                else:
                    # Fixed-point iteration for derivatives
                    eq_fn = SymbolicVector(
                        [eq], compiler_names_dict, alias_names_dict,
                        VARS_NAME, DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME
                    )
                    tol = 1e-8
                    error = 1.0
                    alpha = 1.3
                    curr_dx: float = 1.2

                    dx[uid2idx_diff[d_var.uid]] = curr_dx
                    while error > tol:
                        try:
                            eval_res = float(eq_fn(x, dx, event_params_array, params_array)[0])
                        except Exception:
                            dx[uid2idx_diff[d_var.uid]] = -0.1
                            eval_res = float(eq_fn(x, dx, event_params_array, params_array)[0])

                        dx[uid2idx_diff[d_var.uid]] = (1 - alpha) * curr_dx + alpha * eval_res
                        error = float(abs(eval_res - curr_dx))
                        curr_dx = float(dx[uid2idx_diff[d_var.uid]])

                    diff_init_guess[d_var.uid] = curr_dx

                del diff_pending[uid]
                progress_made = True
            else:
                uid = uid

        # If no variables were resolved in this pass, the system is unsolvable
        if not progress_made:
            # We return None to signify failure rather than raising, per directive
            return None
        else:
            progress_made = progress_made

    return init_guess, diff_init_guess


def init_pseudo_transient(problem: EmtProblemTemplate, options: EmtOptions) -> EmtInitializationReport:
    """
    Run the EMT-native initialization workflow forcing the pseudo-transient path.

    :param problem: EMT problem being initialized.
    :param options: EMT simulation options.
    :return: Initialization report.
    """
    options.initialization_method = EmtInitializationMethod.PseudoTransient
    return run_emt_native_initialization(problem, options)


def run_emt_explicit_initialization(problem: EmtProblemTemplate, verbose: bool = False) -> None:
    """
    Run the explicit EMT initialization stage on a full problem object.

    :param problem: EMT problem being initialized.
    :param verbose: Print explicit initialization details.
    :return: None
    """
    sys_vars: Dict[int, Var] = {v.uid: v for v in (problem.get_state_vars() + problem.get_algebraic_vars())}
    sys_diff_vars: Dict[int, Var] = {dv.uid: dv for dv in problem.get_diff_vars()}

    init_explicit_emt(
        mdl=problem.sys_block,
        sys_vars=sys_vars,
        sys_diff_vars=sys_diff_vars,
        variable_parameters=problem.get_variable_parameters(),
        event_parameters_eqs=problem.get_event_parameter_equations(),
        constant_parameters=problem.get_constant_parameters(),
        init_guess=problem.init_guess,
        diff_init_guess=problem.diff_init_guess,
        uid2idx_vars=problem.uid2idx_vars,
        uid2idx_diff=problem.uid2idx_diff,
        uid2idx_params=problem.uid2idx_params,
        uid2idx_event_params=problem.uid2idx_event_params,
        compiler_names_dict=problem.get_compiler_names_dict(),
        alias_names_dict=problem.get_alias_names_dict(),
        VARIABLE_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
        VARS_NAME=problem.VARS_NAME,
        DIFF_NAME=problem.DIFF_NAME,
        CONSTANT_PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
        verbose=verbose,
    )
    problem.rebuild_runtime_param_vectors()


class ReducedInitializationSystem:
    """
    Reduced EMT initialization system built on top of the unresolved variables only.
    """

    __slots__ = [
        "unknown_vars",
        "residual_eqs",
        "state_unknown_mask",
        "residual_fn",
        "jacobian_fn",
    ]

    def __init__(
            self,
            problem: EmtProblemTemplate,
            unknown_vars: List[Var],
            residual_eqs: List[Expr],
            state_unknown_mask: np.ndarray,
    ) -> None:
        """
        Compile the reduced residual and Jacobian used by the consistent initializer.

        :param problem: EMT problem being initialized.
        :param unknown_vars: Unknown variables solved by the reduced system.
        :param residual_eqs: Residual equations enforcing consistency.
        :param state_unknown_mask: Mask marking which reduced unknowns correspond to states.
        :return: None
        """
        self.unknown_vars = unknown_vars
        self.residual_eqs = residual_eqs
        self.state_unknown_mask = state_unknown_mask
        self.residual_fn = SymbolicVector(
            eqs=residual_eqs,
            compiler_names_dict=problem.get_compiler_names_dict(),
            alias_names_dict=problem.get_alias_names_dict(),
            VARS_NAME=problem.VARS_NAME,
            DIFF_NAME=problem.DIFF_NAME,
            EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
            PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
        )
        self.jacobian_fn = SymbolicJacobian(
            eqs=residual_eqs,
            variables=unknown_vars,
            compiler_names_dict=problem.get_compiler_names_dict(),
            alias_names_dict=problem.get_alias_names_dict(),
            VARS_NAME=problem.VARS_NAME,
            DIFF_NAME=problem.DIFF_NAME,
            EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
            PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
        )


def _build_constant_param_array(problem: EmtProblemTemplate) -> np.ndarray:
    """
    Build the dense constant-parameter vector used by the initialization solvers.

    :param problem: EMT problem being initialized.
    :return: Constant-parameter array.
    """
    const_values: List[Const] = problem.get_parameters_values()
    return np.asarray([float(item.value) for item in const_values], dtype=np.float64)


def _build_runtime_param_array(problem: EmtProblemTemplate) -> np.ndarray:
    """
    Build the runtime-parameter snapshot at the initialization time.

    :param problem: EMT problem being initialized.
    :return: Runtime-parameter array at time zero.
    """
    runtime_params: np.ndarray = problem.event_params_values.copy()
    runtime_params = problem.def_event_params_fn(runtime_params, 0.0)
    return runtime_params


def _build_state_equation_lookup(problem: EmtProblemTemplate) -> Dict[int, Expr]:
    """
    Build a UID lookup for state equations.

    :param problem: EMT problem being initialized.
    :return: Mapping from state variable UID to its differential right-hand side.
    """
    lookup: Dict[int, Expr] = dict()
    state_vars: List[Var] = problem.get_state_vars()
    state_eqs: List[Expr] = problem.get_state_eqs()

    idx: int = 0
    while idx < len(state_vars):
        lookup[state_vars[idx].uid] = state_eqs[idx]
        idx += 1

    return lookup


def _extract_unknown_vector(problem: EmtProblemTemplate, unknown_vars: List[Var], x: np.ndarray) -> np.ndarray:
    """
    Extract the reduced unknown vector from the full EMT variable vector.

    :param problem: EMT problem being initialized.
    :param unknown_vars: Unknown variables solved by the reduced system.
    :param x: Full EMT variable vector.
    :return: Reduced unknown vector.
    """
    n_unknown: int = len(unknown_vars)
    out: np.ndarray = np.zeros(n_unknown, dtype=np.float64)

    idx: int = 0
    while idx < n_unknown:
        var: Var = unknown_vars[idx]
        out[idx] = float(x[problem.uid2idx_vars[var.uid]])
        idx += 1

    return out


def _scatter_unknown_vector(problem: EmtProblemTemplate, unknown_vars: List[Var], x: np.ndarray, reduced_x: np.ndarray) -> None:
    """
    Scatter the reduced unknown vector back into the full EMT variable vector.

    :param problem: EMT problem being initialized.
    :param unknown_vars: Unknown variables solved by the reduced system.
    :param x: Full EMT variable vector updated in place.
    :param reduced_x: Reduced unknown vector.
    :return: None
    """
    idx: int = 0
    while idx < len(unknown_vars):
        var: Var = unknown_vars[idx]
        x[problem.uid2idx_vars[var.uid]] = float(reduced_x[idx])
        idx += 1


def _build_reduced_initialization_system(
        problem: EmtProblemTemplate,
        allow_state_equilibrium: bool,
) -> ReducedInitializationSystem | None:
    """
    Build the reduced initialization system for unresolved EMT variables.

    The reduced system always enforces all algebraic equations. In addition, any
    state variable still missing after the explicit stage receives one extra
    consistency equation, either from `init_eqs` or from a steady-state residual.

    :param problem: EMT problem being initialized.
    :param allow_state_equilibrium: Whether unresolved states may use f(x,z,p)=0.
    :return: Reduced initialization system or None if nothing remains to solve.
    """
    unknown_vars: List[Var] = list()
    residual_eqs: List[Expr] = list()
    state_unknown_flags: List[float] = list()
    state_eq_lookup: Dict[int, Expr] = _build_state_equation_lookup(problem)
    init_eq_lookup: Dict[Var, Expr] = problem.sys_block.init_eqs

    algebraic_vars: List[Var] = problem.get_algebraic_vars()
    algebraic_eqs: List[Expr] = problem.get_algebraic_eqs()
    alg_idx: int = 0
    while alg_idx < len(algebraic_vars):
        algebraic_var: Var = algebraic_vars[alg_idx]
        if algebraic_var.uid in problem.init_guess:
            algebraic_var = algebraic_var
        else:
            unknown_vars.append(algebraic_var)
            residual_eqs.append(algebraic_eqs[alg_idx])
            state_unknown_flags.append(0.0)
        alg_idx += 1

    for state_var in problem.get_state_vars():
        if state_var.uid in problem.init_guess:
            unknown_vars = unknown_vars
        else:
            unknown_vars.append(state_var)
            state_unknown_flags.append(1.0)

            if state_var in init_eq_lookup:
                residual_eqs.append(state_var - init_eq_lookup[state_var])
            elif allow_state_equilibrium and state_var.uid in state_eq_lookup:
                residual_eqs.append(state_eq_lookup[state_var.uid])
            else:
                residual_eqs.append(state_var)

    if len(unknown_vars) == 0:
        return None
    else:
        mask_array: np.ndarray = np.asarray(state_unknown_flags, dtype=np.float64)
        return ReducedInitializationSystem(
            problem=problem,
            unknown_vars=unknown_vars,
            residual_eqs=residual_eqs,
            state_unknown_mask=mask_array,
        )


def _evaluate_initialization_residual(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
) -> np.ndarray:
    """
    Evaluate the reduced initialization residual.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :return: Reduced residual vector.
    """
    _unused = problem
    return reduced_system.residual_fn(x, dx, runtime_params, constant_params).copy()


def _evaluate_initialization_jacobian(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
) -> sp.csc_matrix:
    """
    Evaluate the reduced initialization Jacobian.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :return: Reduced sparse Jacobian.
    """
    _unused = problem
    return reduced_system.jacobian_fn(x, dx, runtime_params, constant_params, 1.0).tocsc(copy=True)


def _max_abs_value(values: np.ndarray) -> float:
    """
    Return the infinity norm of one dense vector.

    :param values: Dense vector.
    :return: Maximum absolute value.
    """
    if values.size == 0:
        return 0.0
    else:
        return float(np.max(np.abs(values)))


def _solve_reduced_linear_system(
        matrix: sp.csc_matrix,
        rhs: np.ndarray,
        dense_threshold: int,
) -> np.ndarray:
    """
    Solve one reduced linear system using a dense or sparse backend depending on size.

    :param matrix: Reduced Jacobian-like matrix.
    :param rhs: Right-hand-side vector.
    :param dense_threshold: Dense/sparse switching threshold.
    :return: Linear-system solution vector.
    """
    n_unknown: int = int(matrix.shape[0])

    if n_unknown <= dense_threshold:
        dense_matrix: np.ndarray = matrix.toarray()
        try:
            return np.linalg.solve(dense_matrix, rhs)
        except np.linalg.LinAlgError:
            solution, _, _, _ = np.linalg.lstsq(dense_matrix, rhs, rcond=None)
            return solution
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                return spla.spsolve(matrix, rhs)
        except Exception:
            lsqr_solution = spla.lsqr(matrix, rhs)
            return np.asarray(lsqr_solution[0], dtype=np.float64)


def _run_reduced_newton_initialization(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
        options: EmtOptions,
        report: EmtInitializationReport,
) -> bool:
    """
    Solve the reduced initialization system with damped sparse Newton iterations.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector updated in place.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :param options: EMT simulation options.
    :param report: Initialization report updated in place.
    :return: True if Newton converged.
    """
    reduced_x: np.ndarray = _extract_unknown_vector(problem, reduced_system.unknown_vars, x)
    max_iter: int = int(options.init_newton_max_iter)
    tol: float = float(options.init_newton_tol)

    iter_idx: int = 0
    while iter_idx < max_iter:
        _scatter_unknown_vector(problem, reduced_system.unknown_vars, x, reduced_x)
        residual: np.ndarray = _evaluate_initialization_residual(reduced_system, problem, x, dx, runtime_params, constant_params)
        res_norm: float = _max_abs_value(residual)

        if iter_idx == 0:
            report.initial_residual_inf = res_norm
        else:
            report.initial_residual_inf = report.initial_residual_inf

        report.final_residual_inf = res_norm
        if res_norm <= tol:
            report.newton_iterations = iter_idx
            return True
        else:
            report.final_residual_inf = report.final_residual_inf

        jacobian: sp.csc_matrix = _evaluate_initialization_jacobian(reduced_system, problem, x, dx, runtime_params, constant_params)
        delta: np.ndarray = _solve_reduced_linear_system(jacobian, -residual, int(options.init_dense_threshold))

        if np.all(np.isfinite(delta)):
            delta = delta
        else:
            return False

        alpha: float = 1.0
        accepted: bool = False
        while alpha >= 1.0e-4:
            trial_reduced_x: np.ndarray = reduced_x + alpha * delta
            _scatter_unknown_vector(problem, reduced_system.unknown_vars, x, trial_reduced_x)
            trial_residual: np.ndarray = _evaluate_initialization_residual(reduced_system, problem, x, dx, runtime_params, constant_params)
            trial_norm: float = _max_abs_value(trial_residual)

            if (not options.init_newton_backtracking) or (trial_norm < res_norm):
                reduced_x = trial_reduced_x
                accepted = True
                break
            else:
                alpha *= 0.5

        if accepted:
            reduced_x = reduced_x
        else:
            return False

        iter_idx += 1

    report.newton_iterations = max_iter
    return False


def _run_reduced_pseudo_transient_initialization(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
        options: EmtOptions,
        report: EmtInitializationReport,
) -> bool:
    """
    Solve the reduced initialization system with a pseudo-transient fallback.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector updated in place.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :param options: EMT simulation options.
    :param report: Initialization report updated in place.
    :return: True if pseudo-transient converged.
    """
    reduced_x: np.ndarray = _extract_unknown_vector(problem, reduced_system.unknown_vars, x)
    dtau: float = float(options.init_ptc_dtau0)
    dtau_min: float = float(options.init_ptc_dtau_min)
    dtau_max: float = float(options.init_ptc_dtau_max)
    max_iter: int = int(options.init_ptc_max_iter)
    tol: float = float(options.init_newton_tol)
    identity_mask: np.ndarray = np.ones(len(reduced_system.unknown_vars), dtype=np.float64)
    mass_matrix: sp.csc_matrix = sp.diags(identity_mask / max(dtau, dtau_min), format="csc")

    iter_idx: int = 0
    while iter_idx < max_iter:
        _scatter_unknown_vector(problem, reduced_system.unknown_vars, x, reduced_x)
        residual: np.ndarray = _evaluate_initialization_residual(reduced_system, problem, x, dx, runtime_params, constant_params)
        res_norm: float = _max_abs_value(residual)
        report.final_residual_inf = res_norm

        if res_norm <= tol:
            report.pseudo_transient_steps = iter_idx
            return True
        else:
            report.final_residual_inf = report.final_residual_inf

        jacobian: sp.csc_matrix = _evaluate_initialization_jacobian(reduced_system, problem, x, dx, runtime_params, constant_params)
        mass_matrix = sp.diags(identity_mask / max(dtau, dtau_min), format="csc")
        linear_matrix: sp.csc_matrix = (jacobian + mass_matrix).tocsc()

        delta: np.ndarray = _solve_reduced_linear_system(linear_matrix, -residual, int(options.init_dense_threshold))

        if np.all(np.isfinite(delta)):
            trial_reduced_x: np.ndarray = reduced_x + delta
            _scatter_unknown_vector(problem, reduced_system.unknown_vars, x, trial_reduced_x)
            trial_residual: np.ndarray = _evaluate_initialization_residual(reduced_system, problem, x, dx, runtime_params, constant_params)
            trial_norm: float = _max_abs_value(trial_residual)

            if trial_norm < res_norm:
                reduced_x = trial_reduced_x
                dtau = min(dtau_max, dtau * 2.0)
            else:
                dtau = max(dtau_min, dtau * 0.5)
        else:
            delta = _solve_reduced_linear_system(linear_matrix, -residual, int(options.init_dense_threshold))
            if np.all(np.isfinite(delta)):
                reduced_x = reduced_x + delta
                dtau = min(dtau_max, dtau * 2.0)
            else:
                dtau = max(dtau_min, dtau * 0.5)

        iter_idx += 1

    report.pseudo_transient_steps = max_iter
    return False


def _apply_solution_to_problem(problem: EmtProblemTemplate, x: np.ndarray) -> None:
    """
    Persist the reduced-solve state vector back into the initialization guess map.

    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector.
    :return: None
    """
    all_vars: List[Var] = list(problem.get_state_vars()) + list(problem.get_algebraic_vars())
    for var in all_vars:
        problem.init_guess[var.uid] = float(x[problem.uid2idx_vars[var.uid]])


def _compute_missing_dx0(problem: EmtProblemTemplate, report: EmtInitializationReport) -> None:
    """
    Compute missing differential initial values from the state equations.

    :param problem: EMT problem being initialized.
    :param report: Initialization report updated in place.
    :return: None
    """
    state_eqs: List[Expr] = problem.get_state_eqs()
    if len(state_eqs) == 0:
        return
    else:
        state_eqs = state_eqs

    x0: np.ndarray = problem.get_x0()
    dx0_seed: np.ndarray = problem.get_dx0()
    runtime_params: np.ndarray = _build_runtime_param_array(problem)
    constant_params: np.ndarray = _build_constant_param_array(problem)
    state_rhs_fn = SymbolicVector(
        eqs=state_eqs,
        compiler_names_dict=problem.get_compiler_names_dict(),
        alias_names_dict=problem.get_alias_names_dict(),
        VARS_NAME=problem.VARS_NAME,
        DIFF_NAME=problem.DIFF_NAME,
        EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
        PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
    )
    computed_dx: np.ndarray = state_rhs_fn(x0, dx0_seed, runtime_params, constant_params).copy()

    idx: int = 0
    while idx < len(problem.get_diff_vars()):
        diff_var: Var = problem.get_diff_vars()[idx]
        if diff_var.uid in problem.diff_init_guess:
            report.automatic_dx0_count = report.automatic_dx0_count
        else:
            problem.diff_init_guess[diff_var.uid] = float(computed_dx[idx])
            report.automatic_dx0_count += 1
        idx += 1


def _build_initialization_system_if_needed(
        problem: EmtProblemTemplate,
        options: EmtOptions,
        report: EmtInitializationReport,
) -> ReducedInitializationSystem | None:
    """
    Build the reduced initialization system only when unresolved work remains.

    :param problem: EMT problem being initialized.
    :param options: EMT simulation options.
    :param report: Initialization report updated in place.
    :return: Reduced initialization system or None.
    """
    reduced_system: ReducedInitializationSystem | None = _build_reduced_initialization_system(
        problem=problem,
        allow_state_equilibrium=bool(options.init_allow_state_equilibrium),
    )
    if reduced_system is None:
        report.unknown_var_count = 0
        report.unresolved_state_count = 0
    else:
        report.unknown_var_count = len(reduced_system.unknown_vars)
        report.unresolved_state_count = int(np.count_nonzero(reduced_system.state_unknown_mask))
    return reduced_system


def run_emt_native_initialization(problem: EmtProblemTemplate, options: EmtOptions) -> EmtInitializationReport:
    """
    Run the EMT-native initialization stages after PF projection and explicit init.

    The workflow keeps the current PF/explicit seeds intact, then solves only the
    unresolved subset with a reduced consistent Newton method. When Newton fails,
    the workflow may fall back to a pseudo-transient continuation. Missing
    differential initial values are computed automatically from the state equations.

    :param problem: EMT problem being initialized.
    :param options: EMT simulation options.
    :return: Initialization report.
    """
    report = EmtInitializationReport(method_requested=options.initialization_method)
    start_time: float = time.perf_counter()
    x: np.ndarray = problem.get_x0()
    x_seed: np.ndarray = x.copy()
    dx: np.ndarray = problem.get_dx0()
    method_requested: EmtInitializationMethod = options.initialization_method

    if method_requested == EmtInitializationMethod.Explicit:
        report.status = InitializationStatus.RESOLVED
        report.method_used = EmtInitializationMethod.Explicit
    else:
        reduced_system: ReducedInitializationSystem | None
        runtime_params: np.ndarray
        constant_params: np.ndarray

        try:
            reduced_system = _build_initialization_system_if_needed(problem, options, report)
            runtime_params = _build_runtime_param_array(problem)
            constant_params = _build_constant_param_array(problem)
        except (FloatingPointError, ZeroDivisionError, ValueError, RuntimeError):
            reduced_system = None
            runtime_params = np.zeros(0, dtype=np.float64)
            constant_params = np.zeros(0, dtype=np.float64)
            report.status = InitializationStatus.FAILED
            report.method_used = EmtInitializationMethod.Explicit
            report.message = "Reduced initialization system construction failed; keeping explicit initialization."

        if reduced_system is None:
            if report.status == InitializationStatus.FAILED:
                x[:] = x_seed
            else:
                report.status = InitializationStatus.RESOLVED
                report.method_used = EmtInitializationMethod.Explicit
        else:
            try:
                residual0: np.ndarray = _evaluate_initialization_residual(reduced_system, problem, x, dx, runtime_params, constant_params)
                report.initial_residual_inf = _max_abs_value(residual0)
            except (FloatingPointError, ZeroDivisionError, ValueError, RuntimeError):
                x[:] = x_seed
                report.status = InitializationStatus.FAILED
                report.method_used = EmtInitializationMethod.Explicit
                report.message = "Reduced initialization residual evaluation failed; keeping explicit initialization."
                reduced_system = None

        if reduced_system is None:
            report.final_residual_inf = report.initial_residual_inf
        else:
            use_newton: bool = method_requested in {EmtInitializationMethod.Auto, EmtInitializationMethod.ConsistentNewton}
            use_ptc: bool = method_requested in {EmtInitializationMethod.Auto, EmtInitializationMethod.PseudoTransient} or bool(options.init_pseudo_transient_enable)

            converged: bool = False
            if use_newton:
                converged = _run_reduced_newton_initialization(
                    reduced_system=reduced_system,
                    problem=problem,
                    x=x,
                    dx=dx,
                    runtime_params=runtime_params,
                    constant_params=constant_params,
                    options=options,
                    report=report,
                )
                if converged:
                    report.method_used = EmtInitializationMethod.ConsistentNewton
                else:
                    converged = converged
            else:
                converged = False

            if converged:
                report.status = InitializationStatus.RESOLVED
            elif use_ptc:
                converged = _run_reduced_pseudo_transient_initialization(
                    reduced_system=reduced_system,
                    problem=problem,
                    x=x,
                    dx=dx,
                    runtime_params=runtime_params,
                    constant_params=constant_params,
                    options=options,
                    report=report,
                )
                if converged:
                    converged = converged
                else:
                    converged = _run_reduced_newton_initialization(
                        reduced_system=reduced_system,
                        problem=problem,
                        x=x,
                        dx=dx,
                        runtime_params=runtime_params,
                        constant_params=constant_params,
                        options=options,
                        report=report,
                    )
                if converged:
                    report.status = InitializationStatus.RESOLVED
                    report.method_used = EmtInitializationMethod.PseudoTransient
                else:
                    x[:] = x_seed
                    report.status = InitializationStatus.FAILED
                    report.method_used = EmtInitializationMethod.Explicit
                    report.message = "Consistent initialization failed after pseudo-transient fallback; keeping explicit initialization."
            else:
                x[:] = x_seed
                report.status = InitializationStatus.FAILED
                report.method_used = EmtInitializationMethod.Explicit
                report.message = "Consistent initialization failed and pseudo-transient fallback was disabled."

    _apply_solution_to_problem(problem, x)
    _compute_missing_dx0(problem, report)
    report.elapsed_s = float(time.perf_counter() - start_time)
    return report
