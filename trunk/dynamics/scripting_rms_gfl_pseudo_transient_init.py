#!/usr/bin/env python3
"""
Pseudo-transient initialization diagnostic for the RMS GFL validation grid.

This script reuses the grid and RMS model setup from
``model_validation.rms_gfl_validation`` and builds the RMS problem with
``RmsInitializationMethod.PseudoTransient``.  It prints the initialized residuals
and selected reference/control variables so the VSC initialization can be checked
without relying on a time-domain simulation to hide initialization errors.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import VeraGridEngine.api as vge
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.Rms.rms_problem_factory import build_rms_problem
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod

from model_validation import rms_gfl_validation


def find_name_in_block(name: str, block: Block) -> Optional[object]:
    """
    Find a symbolic variable by name inside a block tree.

    :param name: Symbolic variable name to search for.
    :param block: Root symbolic block.
    :return: Matching variable object, or ``None`` when the name is absent.
    """
    result: Optional[object] = rms_gfl_validation.find_name_in_block(name=name, block=block)
    return result


def get_problem_variable_value(problem: RmsProblemDae, grid: vge.MultiCircuit, name: str) -> Optional[float]:
    """
    Get one initialized variable value from the RMS problem by symbolic name.

    :param problem: Built RMS DAE problem.
    :param grid: Circuit whose devices own the RMS model blocks.
    :param name: Symbolic variable name to locate.
    :return: Initial value as a float, or ``None`` when the variable is not part of the problem state.
    """
    x0: Vec = problem.get_x0()
    devices: list[object] = list()

    # Search all model owners that can carry the VSC, source, bus, and load references.
    for device in grid.transformers2w:
        devices.append(device)
    for device in grid.vsc_devices:
        devices.append(device)
    for device in grid.generators:
        devices.append(device)
    for device in grid.buses:
        devices.append(device)
    for device in grid.get_loads():
        devices.append(device)
    for device in grid.lines:
        devices.append(device)

    for device in devices:
        block: Optional[Block] = getattr(device, "rms_model", None)
        if block is None:
            pass
        else:
            variable: Optional[object] = find_name_in_block(name=name, block=block)
            if variable is None:
                pass
            else:
                variable_uid: int = int(variable.uid)
                variable_index: Optional[int] = problem.uid2idx_vars.get(variable_uid, None)
                if variable_index is None:
                    pass
                else:
                    return float(x0[variable_index])

    return None


def evaluate_initial_residual(problem: RmsProblemDae) -> Vec:
    """
    Evaluate the DAE residual at the initialized point and zero derivatives.

    :param problem: Built and event-group configured RMS DAE problem.
    :return: Residual vector containing state residuals followed by algebraic residuals.
    """
    x0: Vec = problem.get_x0()
    dx0: Vec = problem.get_dx0()

    # Initialize runtime event parameters at the initial point before evaluating equations.
    problem.update_variable_params(t=0.0, x_snapshot=x0, scheduled_t=0.0)
    problem.update(0.0, x0, problem._variable_parameters_values)

    if problem.get_states_number() > 0:
        state_residual: Vec = problem.rhs_state(x0, dx0)
    else:
        state_residual = np.zeros(0, dtype=float)

    algebraic_residual: Vec = problem.rhs_algebraic(x0, dx0)
    residual: Vec = np.r_[state_residual, algebraic_residual]
    return residual


def print_reference_values(problem: RmsProblemDae, grid: vge.MultiCircuit) -> None:
    """
    Print key initialized VSC reference and control variables.

    :param problem: Built RMS DAE problem.
    :param grid: Circuit whose RMS model blocks contain the variables.
    :return: None.
    """
    names: list[str] = [
        "Vdc",
        "Vdc_",
        "Vdc_ref",
        "P_ref",
        "Q_ref",
        "Vm_ac_ref",
        "P",
        "Q",
        "Pt_vsc_control",
        "Qt_vsc_control",
        "Pf_vsc_control",
        "i_d",
        "i_q",
        "i_d_ref",
        "i_q_ref",
        "i_d_ref_sat",
        "i_q_ref_sat",
        "v_d_c",
        "v_q_c",
        "Pdc",
        "Idc",
        "Idc_src",
        "duty",
    ]

    print("\nInitialized reference/control variables")
    print("-" * 70)
    for name in names:
        value: Optional[float] = get_problem_variable_value(problem=problem, grid=grid, name=name)
        if value is None:
            pass
        else:
            print(f"{name:22s} {value: .12e}")


def print_top_residual_equations(problem: RmsProblemDae, residual: Vec, top_n: int) -> None:
    """
    Print the equations with the largest absolute residual values.

    :param problem: Built RMS DAE problem.
    :param residual: Residual vector evaluated at the initialized point.
    :param top_n: Number of equations to print.
    :return: None.
    """
    all_equations: list[Expr] = list(problem.state_eqs) + list(problem.algebraic_eqs)
    n_state: int = problem.get_states_number()
    order: Vec = np.argsort(np.abs(residual))[::-1]
    rows_to_print: int = min(int(top_n), int(order.size))

    print("\nLargest pseudo-transient initialization residual equations")
    print("-" * 70)
    for rank in range(rows_to_print):
        residual_index: int = int(order[rank])
        residual_value: float = float(residual[residual_index])
        residual_magnitude: float = float(abs(residual_value))

        if residual_index < n_state:
            equation_kind: str = "state"
            local_index: int = residual_index
        else:
            equation_kind = "algebraic"
            local_index = residual_index - n_state

        if residual_index < len(all_equations):
            equation_text: str = str(all_equations[residual_index])
        else:
            equation_text = "<equation index out of range>"

        print(
            f"#{rank + 1:02d} {equation_kind}[{local_index}] "
            f"res={residual_value: .9e} |res|={residual_magnitude: .9e} :: {equation_text}"
        )


def build_pseudo_transient_problem(grid: vge.MultiCircuit, pf_results: object) -> RmsProblemDae:
    """
    Build the RMS DAE problem using pseudo-transient initialization.

    :param grid: Initialized circuit containing RMS models.
    :param pf_results: Power-flow results used to seed initialization.
    :return: Built RMS DAE problem.
    """
    options: vge.RmsOptions = vge.RmsOptions(
        simulation_time=0.01,
        time_step=0.01,
        tolerance=1.0e-8,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.PseudoTransient,
        max_iter=1000,
        verbose=0,
    )

    problem: RmsProblemDae = build_rms_problem(
        grid=grid,
        options=options,
        pf_results=pf_results,
        progress_signal=None,
    )
    return problem


def main() -> None:
    """
    Run the pseudo-transient initialization diagnostic.

    :return: None.
    """
    print("=" * 70)
    print("RMS GFL pseudo-transient initialization diagnostic")
    print("=" * 70)

    # Build the exact validation grid so pseudo-transient is tested on the same model stack.
    grid: vge.MultiCircuit = rms_gfl_validation.create_grid_2()
    pf_results: object = rms_gfl_validation.run_power_flow(grid, "RMS GFL pseudo-transient init grid")

    if not bool(pf_results.converged):
        print("Power flow did not converge; pseudo-transient initialization was not attempted.")
    else:
        # Assign all RMS templates and connections before the RMS problem is built.
        rms_gfl_validation.initialize_grid2_rms_models(grid, pf_results)

        events_group: RmsEventsGroup = RmsEventsGroup(name="Pseudo-transient init diagnostic")
        grid.add_rms_events_group(events_group)

        try:
            problem: RmsProblemDae = build_pseudo_transient_problem(grid=grid, pf_results=pf_results)
            problem.set_events_group(rms_events_group=events_group)
            residual: Vec = evaluate_initial_residual(problem=problem)

            residual_inf: float = float(np.linalg.norm(residual, np.inf)) if residual.size > 0 else 0.0
            print("\nPseudo-transient initialization summary")
            print("-" * 70)
            print(f"x0 size      : {problem.get_x0().size}")
            print(f"x0 finite    : {bool(np.all(np.isfinite(problem.get_x0())))}")
            print(f"residual inf : {residual_inf:.9e}")

            print_reference_values(problem=problem, grid=grid)
            print_top_residual_equations(problem=problem, residual=residual, top_n=20)
        except Exception as exc:
            print("\nPseudo-transient initialization failed while building/evaluating the RMS problem")
            print("-" * 70)
            print(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
