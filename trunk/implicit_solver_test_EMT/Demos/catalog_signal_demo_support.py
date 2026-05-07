# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict, Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, Const, Expr, Var


class GenericEmtProblem(EmtProblemTemplate):
    """
    Minimal generic EMT problem used by catalog-block demos.
    """

    __slots__ = []


def bind_internal_time_vars(root_block: Block, glob_time_var: Var) -> None:
    """
    Replace catalog-local `glob_time_*` variables with the problem global time.

    :param root_block: Root block to update.
    :param glob_time_var: Shared problem global time variable.
    :return: None.
    """
    candidate_vars: dict[int, Var] = dict()
    block_obj: Block
    var_list: Iterable[Var]
    var_obj: Var

    for block_obj in root_block.get_all_blocks():
        for var_list in [
            block_obj.algebraic_vars,
            block_obj.state_vars,
            block_obj.in_vars,
            block_obj.out_vars,
            list(block_obj.event_dict.keys()),
            list(block_obj.mode_dict.keys()),
            list(block_obj.init_eqs.keys()),
            list(block_obj.diff_init_eqs.keys()),
        ]:
            for var_obj in var_list:
                if var_obj.name.startswith("glob_time_"):
                    candidate_vars[var_obj.uid] = var_obj
                else:
                    pass

        expr_obj_list = list(block_obj.algebraic_eqs) + list(block_obj.state_eqs)
        expr_obj_list.extend(list(block_obj.init_eqs.values()))
        expr_obj_list.extend(list(block_obj.diff_init_eqs.values()))

        for expr_obj in expr_obj_list:
            for var_obj in expr_obj.get_vars():
                if var_obj.name.startswith("glob_time_"):
                    candidate_vars[var_obj.uid] = var_obj
                else:
                    pass

    for var_obj in candidate_vars.values():
        root_block.update_model(var_obj, glob_time_var)


def set_event_parameter_by_name(block: Block, parameter_name: str, value: float) -> None:
    """
    Assign one event parameter by its logical constant name.

    :param block: Target block.
    :param parameter_name: Logical event-parameter name.
    :param value: Numeric value to assign.
    :return: None.
    """
    var_obj: Var
    expr_obj: Const

    for var_obj, expr_obj in block.event_dict.items():
        if isinstance(expr_obj, Const) and expr_obj.name == parameter_name:
            block.event_dict[var_obj] = Const(float(value), name=parameter_name)
        else:
            pass


def promote_internal_equation_vars(root_block: Block) -> None:
    """
    Promote internal equation-only variables to algebraic variables for implicit demos.

    Some catalog-derived blocks keep helper variables referenced by equations and
    `init_eqs` without listing them in `algebraic_vars`. The implicit demo solver
    needs them on the explicit unknown surface.

    :param root_block: Root block to normalize in place.
    :return: None.
    """
    block_obj: Block
    known_uids: set[int]
    global_known_uids: set[int] = set()
    expr_obj: object
    var_obj: Var

    for block_obj in root_block.get_all_blocks():
        for var_obj in list(block_obj.state_vars) + list(block_obj.algebraic_vars) + list(block_obj.diff_vars) + list(block_obj.in_vars) + list(block_obj.out_vars):
            global_known_uids.add(var_obj.uid)

        for var_obj in list(block_obj.event_dict.keys()) + list(block_obj.mode_dict.keys()) + list(block_obj.parameters.keys()):
            global_known_uids.add(var_obj.uid)

    for block_obj in root_block.get_all_blocks():
        known_uids = set()
        for var_obj in list(block_obj.state_vars) + list(block_obj.algebraic_vars) + list(block_obj.diff_vars) + list(block_obj.in_vars) + list(block_obj.out_vars):
            known_uids.add(var_obj.uid)

        for var_obj in list(block_obj.event_dict.keys()) + list(block_obj.mode_dict.keys()) + list(block_obj.parameters.keys()):
            known_uids.add(var_obj.uid)

        for expr_obj in list(block_obj.algebraic_eqs) + list(block_obj.state_eqs) + list(block_obj.init_eqs.values()) + list(block_obj.diff_init_eqs.values()):
            for var_obj in expr_obj.get_vars():
                if var_obj.uid in known_uids or var_obj.uid in global_known_uids:
                    pass
                else:
                    block_obj.algebraic_vars.append(var_obj)
                    known_uids.add(var_obj.uid)


def seed_zero_initial_guess(problem: EmtProblemTemplate) -> None:
    """
    Seed zero initial guesses for all state and algebraic variables.

    :param problem: EMT problem to seed.
    :return: None.
    """
    var_obj: Var

    for var_obj in problem.state_and_algebraic_vars():
        problem.init_guess[var_obj.uid] = 0.0


def _build_uid_bindings(problem: EmtProblemTemplate, x_vec: np.ndarray, params_vec: np.ndarray, tm: float) -> Dict[int, float]:
    """
    Build UID bindings for one manual demo evaluation step.

    :param problem: EMT problem.
    :param x_vec: Current state/algebraic vector.
    :param params_vec: Current runtime parameter vector.
    :param tm: Current simulation time.
    :return: UID bindings.
    """
    uid_bindings: Dict[int, float] = dict()
    var_obj: Var
    parameter_obj: Var
    parameter_index: int

    for var_obj in problem.get_state_vars():
        uid_bindings[var_obj.uid] = float(x_vec[problem.get_var_idx(var_obj)])

    for var_obj in problem.get_algebraic_vars():
        uid_bindings[var_obj.uid] = float(x_vec[problem.get_var_idx(var_obj)])

    for parameter_index, parameter_obj in enumerate(problem.get_variable_parameters()):
        uid_bindings[parameter_obj.uid] = float(params_vec[parameter_index])

    for parameter_index, parameter_obj in enumerate(problem.get_constant_parameters()):
        uid_bindings[parameter_obj.uid] = float(problem.get_parameters_values()[parameter_index].value)

    uid_bindings[problem.glob_time.uid] = float(tm)
    return uid_bindings


def _extract_assignment_rhs(eq_obj: Expr, target_var: Var) -> Expr | None:
    """
    Extract the right-hand side of one direct algebraic assignment equation.

    :param eq_obj: Candidate algebraic equation.
    :param target_var: Target algebraic variable.
    :return: Assignment rhs or None.
    """
    if isinstance(eq_obj, BinOp) and eq_obj.op == "-":
        if eq_obj.left is target_var:
            return eq_obj.right
        else:
            if eq_obj.right is target_var:
                return eq_obj.left
            else:
                return None
    else:
        return None


def _solve_direct_algebraics(problem: EmtProblemTemplate, x_vec: np.ndarray, params_vec: np.ndarray, tm: float) -> None:
    """
    Solve direct assignment-style algebraic equations in place.

    :param problem: EMT problem.
    :param x_vec: Current state/algebraic vector.
    :param params_vec: Current runtime parameter vector.
    :param tm: Current simulation time.
    :return: None.
    """
    alg_var: Var
    alg_eq: Expr
    rhs_expr: Expr | None
    uid_bindings: Dict[int, float]

    iteration_index: int

    for iteration_index in range(8):
        uid_bindings = _build_uid_bindings(problem, x_vec, params_vec, tm)

        for alg_var in problem.get_algebraic_vars():
            rhs_expr = None

            for alg_eq in problem.get_algebraic_eqs():
                rhs_expr = _extract_assignment_rhs(alg_eq, alg_var)

                if rhs_expr is not None:
                    break
                else:
                    pass

            if rhs_expr is not None:
                x_vec[problem.get_var_idx(alg_var)] = float(rhs_expr.eval_uid(uid_bindings))
                uid_bindings[alg_var.uid] = float(x_vec[problem.get_var_idx(alg_var)])
            else:
                pass


def apply_init_equations(problem: EmtProblemTemplate, x_vec: np.ndarray, params_vec: np.ndarray, tm: float) -> None:
    """
    Apply explicit initialization equations to the current state/algebraic vector.

    :param problem: EMT problem.
    :param x_vec: Current state/algebraic vector.
    :param params_vec: Current runtime parameter vector.
    :param tm: Initialization time.
    :return: None.
    """
    uid_bindings: Dict[int, float] = _build_uid_bindings(problem, x_vec, params_vec, tm)
    var_obj: Var
    expr_obj: Expr

    for var_obj, expr_obj in problem.sys_block.init_eqs.items():
        if var_obj.uid in problem.uid2idx_vars:
            x_vec[problem.uid2idx_vars[var_obj.uid]] = float(expr_obj.eval_uid(uid_bindings))
            uid_bindings[var_obj.uid] = float(x_vec[problem.uid2idx_vars[var_obj.uid]])
        else:
            pass


def run_demo_simulation(
    root_block: Block,
    glob_time_var: Var,
    tracked_names: Sequence[str],
    t_end: float,
    dt: float,
) -> Dict[str, np.ndarray]:
    """
    Simulate one generic catalog-block demo and return tracked traces.

    :param root_block: Root symbolic block to simulate.
    :param glob_time_var: Shared global time variable.
    :param tracked_names: Variable names to extract from the solved history.
    :param t_end: Simulation end time.
    :param dt: Time step.
    :return: Trace dictionary.
    """
    promote_internal_equation_vars(root_block)
    root_block.unify_blocks()
    static_parameter_values_mapping: Dict[Var, Const] = dict()
    problem = GenericEmtProblem(sys_block=root_block, glob_time=glob_time_var,static_parameter_values_mapping=static_parameter_values_mapping)
    seed_zero_initial_guess(problem)
    boundary_updater = build_boundary_updater_from_block(problem)
    step_count: int = int(round(float(t_end) / float(dt)))
    tme: np.ndarray = np.linspace(0.0, float(t_end), step_count + 1, dtype=float)
    y_hist: np.ndarray = np.zeros((step_count + 1, problem.get_all_vars_number()), dtype=float)
    runtime_params: np.ndarray = problem.event_params_values.copy()
    x_vec: np.ndarray = problem.get_x0().copy()
    state_var: Var
    state_eq: Expr
    uid_bindings: Dict[int, float]
    step_index: int

    apply_init_equations(problem, x_vec, runtime_params, float(tme[0]))
    _solve_direct_algebraics(problem, x_vec, runtime_params, float(tme[0]))

    for step_index in range(step_count + 1):
        current_time: float = float(tme[step_index])
        runtime_params = problem.def_event_params_fn(runtime_params, current_time)

        if boundary_updater is not None:
            boundary_updater.update(current_time, x_vec, runtime_params)
        else:
            pass

        _solve_direct_algebraics(problem, x_vec, runtime_params, current_time)
        y_hist[step_index, :] = x_vec

        if step_index < step_count:
            uid_bindings = _build_uid_bindings(problem, x_vec, runtime_params, current_time)
            for state_var, state_eq in zip(problem.get_state_vars(), problem.get_state_eqs()):
                state_idx: int = problem.get_var_idx(state_var)
                x_vec[state_idx] = float(x_vec[state_idx] + float(dt) * float(state_eq.eval_uid(uid_bindings)))
            else:
                pass

    traces: Dict[str, np.ndarray] = dict({"time": np.asarray(tme, dtype=float)})
    tracked_name: str
    tracked_var: Var | None

    for tracked_name in tracked_names:
        tracked_var = find_name_in_block(tracked_name, problem.sys_block)
        if tracked_var is None:
            raise KeyError(f"Tracked variable '{tracked_name}' was not found in the demo block")
        else:
            traces[tracked_name] = np.asarray(y_hist[:, problem.get_var_idx(tracked_var)], dtype=float)

    return traces


def plot_named_traces(traces: Dict[str, np.ndarray], title: str, y_labels: Sequence[str], file_path: Path | None = None) -> None:
    """
    Plot one or more named traces against the common time vector.

    :param traces: Trace dictionary returned by `run_demo_simulation`.
    :param title: Figure title.
    :param y_labels: Ordered trace names to plot.
    :param file_path: Optional PNG output path.
    :return: None.
    """
    time_values: np.ndarray = traces["time"]
    plt.figure(figsize=(11, 7))
    trace_name: str

    for trace_name in y_labels:
        plt.plot(time_values, traces[trace_name], label=trace_name)

    plt.title(title)
    plt.xlabel("Time [s]")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    if file_path is not None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(file_path, dpi=200, bbox_inches="tight")
    else:
        pass

    if file_path is None:
        plt.show()
    else:
        pass

    plt.close()


def get_demo_plot_directory(case_name: str) -> Path:
    """
    Return the standard PNG output directory for implicit catalog demos.

    :param case_name: Demo case name.
    :return: Output directory path.
    """
    output_dir: Path = Path(__file__).resolve().parent / "plot_results" / case_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
