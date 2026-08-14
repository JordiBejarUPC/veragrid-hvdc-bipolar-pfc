# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Shared configuration, execution and persistence for RMS time-domain benchmarks."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd

from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.enumerations import RmsInitializationMethod
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
import VeraGridEngine.api as gce


class RmsBenchmarkCase(Enum):
    """Networks supported by the RMS dynamic benchmark."""

    KUNDUR = "kundur"
    IEEE14 = "ieee14"
    IEEE39 = "ieee39"
    NPCC140 = "npcc140"
    WECC179 = "wecc179"


class RmsBenchmarkScenario(Enum):
    """Dynamic disturbances supported by the RMS benchmark."""

    BASE = "base"
    ROTOR_SPEED_STATE_STEP = "rotor_speed_state_step"


class RmsBenchmarkConfiguration:
    """Numerical settings shared exactly by ANDES and VeraGrid."""

    __slots__ = (
        "case_tpe",
        "time_step",
        "simulation_time",
        "integration_tolerance",
        "maximum_iterations",
        "speed_perturbation_pu",
        "scenario_tpe",
        "event_time",
        "event_state_step_pu",
    )

    def __init__(
        self: RmsBenchmarkConfiguration,
        case_tpe: RmsBenchmarkCase,
        time_step: float = 0.001,
        simulation_time: float = 1.0,
        integration_tolerance: float = 1.0e-6,
        maximum_iterations: int = 1000,
        speed_perturbation_pu: float = 1.0e-4,
        scenario_tpe: RmsBenchmarkScenario = RmsBenchmarkScenario.BASE,
        event_time: float = 0.2,
        event_state_step_pu: float = 1.0e-4,
    ) -> None:
        """Create one immutable-size benchmark configuration.

        :param case_tpe: Network selected for the run.
        :param time_step: Fixed integration step in seconds.
        :param simulation_time: Final simulation time in seconds.
        :param integration_tolerance: Nonlinear integration tolerance.
        :param maximum_iterations: Maximum Newton iterations per time step.
        :param speed_perturbation_pu: Initial first-generator speed perturbation.
        :param scenario_tpe: Base run or common physical event scenario.
        :param event_time: Rotor-speed state-step application time in seconds.
        :param event_state_step_pu: Additive rotor-speed event magnitude in p.u.
        :return: None.
        """
        self.case_tpe: RmsBenchmarkCase = case_tpe
        self.time_step: float = time_step
        self.simulation_time: float = simulation_time
        self.integration_tolerance: float = integration_tolerance
        self.maximum_iterations: int = maximum_iterations
        self.speed_perturbation_pu: float = speed_perturbation_pu
        self.scenario_tpe: RmsBenchmarkScenario = scenario_tpe
        self.event_time: float = event_time
        self.event_state_step_pu: float = event_state_step_pu


def case_label(case_tpe: RmsBenchmarkCase) -> str:
    """Return the stable report label for one benchmark case.

    :param case_tpe: Benchmark case.
    :return: Stable case label.
    """
    if case_tpe is RmsBenchmarkCase.KUNDUR:
        label: str = "KUNDUR_no_shunt"
    elif case_tpe is RmsBenchmarkCase.IEEE14:
        label = "IEEE14"
    elif case_tpe is RmsBenchmarkCase.IEEE39:
        label = "IEEE39"
    elif case_tpe is RmsBenchmarkCase.NPCC140:
        label = "NPCC140"
    else:
        label = "WECC179"
    return label


def parse_case_name(case_name: str) -> RmsBenchmarkCase:
    """Parse a human case name into the benchmark enumeration.

    :param case_name: Case name supplied by Python or a command-line caller.
    :return: Parsed benchmark case.
    """
    normalized_name: str = case_name.strip().lower().replace("-", "").replace("_", "")
    if normalized_name in ("kundur", "kundurnoshunt"):
        case_tpe: RmsBenchmarkCase = RmsBenchmarkCase.KUNDUR
    elif normalized_name == "ieee14":
        case_tpe = RmsBenchmarkCase.IEEE14
    elif normalized_name == "ieee39":
        case_tpe = RmsBenchmarkCase.IEEE39
    elif normalized_name == "npcc140":
        case_tpe = RmsBenchmarkCase.NPCC140
    elif normalized_name == "wecc179":
        case_tpe = RmsBenchmarkCase.WECC179
    else:
        raise ValueError(f"Unsupported RMS benchmark case: {case_name}")
    return case_tpe


def engine_results_directory(
    case_tpe: RmsBenchmarkCase,
    engine_label: str,
    scenario_tpe: RmsBenchmarkScenario = RmsBenchmarkScenario.BASE,
) -> Path:
    """Return one engine-specific RMS dynamic result directory.

    :param case_tpe: Benchmark case.
    :param engine_label: Engine name used in the folder name.
    :param scenario_tpe: Dynamic scenario represented by the results.
    :return: Absolute result directory.
    """
    script_directory: Path = Path(__file__).resolve().parent
    if scenario_tpe is RmsBenchmarkScenario.BASE:
        scenario_suffix: str = ""
    else:
        scenario_suffix = "_event"
    return script_directory / f"{case_label(case_tpe)}_rms_dynamic{scenario_suffix}_results_{engine_label}"


def perturbation_state_label(case_tpe: RmsBenchmarkCase) -> str:
    """Return the common physical rotor-speed state perturbed in both tools.

    :param case_tpe: Selected benchmark case.
    :return: ANDES-style state label.
    """
    if case_tpe is RmsBenchmarkCase.KUNDUR:
        label: str = "omega GENCLS 1"
    elif case_tpe is RmsBenchmarkCase.NPCC140:
        label = "omega GENROU 22"
    else:
        label = "omega GENROU 1"
    return label


def build_rms_options(configuration: RmsBenchmarkConfiguration) -> RmsOptions:
    """Build the VeraGrid options equivalent to ANDES Backward Euler.

    :param configuration: Shared numerical configuration.
    :return: VeraGrid RMS options.
    """
    return RmsOptions(
        time_step=configuration.time_step,
        simulation_time=configuration.simulation_time,
        tolerance=configuration.integration_tolerance,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=configuration.maximum_iterations,
        verbose=0,
    )


def build_unique_variable_labels(variables: list[Any]) -> list[str]:
    """Build deterministic labels from symbolic variable names and occurrence order.

    :param variables: Ordered VeraGrid symbolic variables.
    :return: Unique labels suitable for trajectory CSV columns.
    """
    occurrence_by_name: dict[str, int] = dict()
    labels: list[str] = list()
    variable: Any
    for variable in variables:
        variable_name: str = str(variable.name)
        occurrence: int | None = occurrence_by_name.get(variable_name, None)
        if occurrence is None:
            occurrence = 1
        else:
            occurrence += 1
        occurrence_by_name[variable_name] = occurrence
        labels.append(f"{variable_name}{occurrence}")
    return labels


def write_trajectory_csv(
    output_path: Path,
    time_values: np.ndarray,
    values: np.ndarray,
    labels: list[str],
) -> None:
    """Write one time-aligned state or algebraic trajectory table.

    :param output_path: Destination CSV file.
    :param time_values: Simulation timestamps in seconds.
    :param values: Two-dimensional trajectory matrix.
    :param labels: Variable labels aligned with matrix columns.
    :return: None.
    """
    if values.ndim == 2 and values.shape[1] == len(labels):
        pass
    else:
        raise ValueError("Trajectory values and labels are not dimensionally aligned.")
    data: dict[str, np.ndarray] = dict()
    data["time_s"] = np.asarray(time_values, dtype=float)
    label_index: int
    for label_index in range(len(labels)):
        data[labels[label_index]] = np.asarray(values[:, label_index], dtype=float)
    pd.DataFrame(data).to_csv(output_path, index=False, float_format="%.12e")


def write_key_value_csv(output_path: Path, values: list[tuple[str, str]]) -> None:
    """Write an ordered key-value table without losing unavailable values.

    :param output_path: Destination CSV file.
    :param values: Ordered key-value rows.
    :return: None.
    """
    frame: pd.DataFrame = pd.DataFrame(values, columns=list(("metric", "value")))
    frame.to_csv(output_path, index=False)


def run_power_flow_twice(
    grid: gce.MultiCircuit,
    options: PowerFlowOptions,
) -> tuple[PowerFlowResults, float, float]:
    """Run a cold and a warm VeraGrid power flow and retain only the second result.

    :param grid: RMS-ready VeraGrid network.
    :param options: Deterministic Newton power-flow options.
    :return: Authoritative warm result, cold time and warm time.
    """
    # The first solve triggers cold numerical compilation and is measured only
    # to document warm-up cost; it is excluded from the comparison total.
    cold_driver: PowerFlowDriver = PowerFlowDriver(grid, options)
    cold_start: float = time.perf_counter()
    cold_driver.run()
    cold_seconds: float = time.perf_counter() - cold_start
    if bool(cold_driver.results.converged):
        pass
    else:
        raise RuntimeError("The cold VeraGrid power flow did not converge.")

    # A fresh driver avoids reusing result containers while the process keeps
    # compiled numerical kernels warm. This second solution feeds the RMS DAE.
    warm_driver: PowerFlowDriver = PowerFlowDriver(grid, options)
    warm_start: float = time.perf_counter()
    warm_driver.run()
    warm_seconds: float = time.perf_counter() - warm_start
    if bool(warm_driver.results.converged):
        pass
    else:
        raise RuntimeError("The authoritative warm VeraGrid power flow did not converge.")
    return warm_driver.results, cold_seconds, warm_seconds


def perturb_first_veragrid_speed_state(
    problem: RmsProblemDae,
    perturbation_pu: float,
    target_label: str,
    canonical_state_labels: list[str] | None,
) -> str:
    """Apply the common initial speed perturbation to the first machine state.

    :param problem: Initialized VeraGrid RMS DAE.
    :param perturbation_pu: Additive rotor-speed perturbation in per unit.
    :param target_label: Common ANDES-style physical state label.
    :param canonical_state_labels: Labels aligned with VeraGrid state order.
    :return: Perturbed symbolic state label.
    """
    perturbation_applied: bool = False
    perturbed_label: str = ""
    state_index: int
    for state_index in range(len(problem.state_vars)):
        state_variable: Any = problem.state_vars[state_index]
        if canonical_state_labels is None:
            is_target_state: bool = not perturbation_applied and str(state_variable.name) == "omega"
        else:
            is_target_state = canonical_state_labels[state_index] == target_label
        if not perturbation_applied and is_target_state:
            initial_values: np.ndarray = problem.get_x0()
            problem.init_guess[state_variable.uid] = float(initial_values[state_index]) + perturbation_pu
            perturbed_label = target_label
            perturbation_applied = True
        else:
            pass
    if perturbation_applied:
        pass
    else:
        raise ValueError("No VeraGrid omega state is available for the RMS perturbation.")
    return perturbed_label


def set_veragrid_initial_vector(problem: RmsProblemDae, values: np.ndarray) -> None:
    """Replace the DAE initial vector with one accepted integration snapshot.

    :param problem: Initialized VeraGrid RMS problem.
    :param values: State-then-algebraic snapshot in solver order.
    :return: None.
    """
    expected_size: int = problem.get_all_vars_number()
    if values.size == expected_size:
        pass
    else:
        raise ValueError("The accepted RMS snapshot does not match the DAE variable count.")
    state_index: int
    for state_index in range(len(problem.state_vars)):
        state_variable: Any = problem.state_vars[state_index]
        problem.init_guess[state_variable.uid] = float(values[state_index])
    algebraic_index: int
    state_count: int = len(problem.state_vars)
    for algebraic_index in range(len(problem.algebraic_vars)):
        algebraic_variable: Any = problem.algebraic_vars[algebraic_index]
        problem.init_guess[algebraic_variable.uid] = float(values[state_count + algebraic_index])


def combine_solver_timings(
    first_solver: BackEulerImplicitIntegration,
    second_solver: BackEulerImplicitIntegration,
) -> dict[str, float]:
    """Add internal timing accumulators from two consecutive solver segments.

    :param first_solver: Pre-event Backward Euler segment.
    :param second_solver: Post-event Backward Euler segment.
    :return: Summed timing values by internal phase.
    """
    combined: dict[str, float] = dict()
    timing_name: str
    for timing_name in first_solver._timings:
        combined[timing_name] = (
            float(first_solver._timings[timing_name])
            + float(second_solver._timings[timing_name])
        )
    return combined


def run_veragrid_rms_benchmark(
    grid: gce.MultiCircuit,
    power_flow_options: PowerFlowOptions,
    configuration: RmsBenchmarkConfiguration,
    case_build_seconds: float,
    workflow_start: float,
    canonical_state_labels: list[str] | None = None,
) -> None:
    """Run, time and persist one VeraGrid RMS time-domain benchmark.

    :param grid: Fully configured VeraGrid RMS network.
    :param power_flow_options: Case-specific static solver options.
    :param configuration: Shared dynamic numerical settings.
    :param case_build_seconds: Measured network and model construction time.
    :param workflow_start: Wall-clock counter captured before case construction.
    :param canonical_state_labels: Optional ANDES-style labels aligned with VeraGrid states.
    :return: None.
    """
    pf_results: PowerFlowResults
    cold_pf_seconds: float
    warm_pf_seconds: float
    pf_results, cold_pf_seconds, warm_pf_seconds = run_power_flow_twice(
        grid=grid,
        options=power_flow_options,
    )

    # Constructing RmsProblemDae performs explicit dynamic initialization and
    # compiles the symbolic residuals and Jacobians into numerical functions.
    rms_options: RmsOptions = build_rms_options(configuration)
    initialization_start: float = time.perf_counter()
    problem: RmsProblemDae = RmsProblemDae(
        grid=grid,
        options=rms_options,
        pf_results=pf_results,
    )
    # The benchmark state event is applied between two solver segments, so the
    # compiled DAE itself remains the same before and after the instantaneous
    # state jump.
    events_group: RmsEventsGroup = RmsEventsGroup(name="benchmark_scenario")
    problem.set_events_group(events_group)
    problem.reset_boundary_update_state(0.0)
    target_state_label: str = perturbation_state_label(configuration.case_tpe)
    if (
        configuration.scenario_tpe is RmsBenchmarkScenario.BASE
        and configuration.speed_perturbation_pu != 0.0
    ):
        perturbed_state_label: str = perturb_first_veragrid_speed_state(
            problem=problem,
            perturbation_pu=configuration.speed_perturbation_pu,
            target_label=target_state_label,
            canonical_state_labels=canonical_state_labels,
        )
    else:
        perturbed_state_label = "none"
    initialization_seconds: float = time.perf_counter() - initialization_start

    # Solver construction allocates the fixed time grid and trajectory arrays;
    # no integration step is executed in this phase.
    solver_setup_start: float = time.perf_counter()
    if configuration.scenario_tpe is RmsBenchmarkScenario.BASE:
        solver: BackEulerImplicitIntegration = BackEulerImplicitIntegration(
            problem=problem,
            t0=0.0,
            t_end=configuration.simulation_time,
            h=configuration.time_step,
            max_iter=configuration.maximum_iterations,
            tolerance=configuration.integration_tolerance,
        )
        pre_event_solver: BackEulerImplicitIntegration | None = None
        post_event_solver: BackEulerImplicitIntegration | None = None
    else:
        pre_event_solver = BackEulerImplicitIntegration(
            problem=problem,
            t0=0.0,
            t_end=configuration.event_time,
            h=configuration.time_step,
            max_iter=configuration.maximum_iterations,
            tolerance=configuration.integration_tolerance,
        )
        post_event_solver = BackEulerImplicitIntegration(
            problem=problem,
            t0=configuration.event_time,
            t_end=configuration.simulation_time,
            h=configuration.time_step,
            max_iter=configuration.maximum_iterations,
            tolerance=configuration.integration_tolerance,
        )
        solver = pre_event_solver
    solver_setup_seconds: float = time.perf_counter() - solver_setup_start

    integration_start: float = time.perf_counter()
    if configuration.scenario_tpe is RmsBenchmarkScenario.BASE:
        simulation_output: tuple[np.ndarray, np.ndarray, bool, bool] = solver.simulate()
        time_values: np.ndarray = np.asarray(simulation_output[0], dtype=float)
        all_values: np.ndarray = np.asarray(simulation_output[1], dtype=float)
        well_initialized: bool = bool(simulation_output[2])
        converged: bool = bool(simulation_output[3])
        solver_timings: dict[str, float] = solver._timings
    else:
        if pre_event_solver is not None and post_event_solver is not None:
            pass
        else:
            raise RuntimeError("The event benchmark solver segments were not constructed.")
        pre_event_output: tuple[np.ndarray, np.ndarray, bool, bool] = pre_event_solver.simulate()
        pre_event_values: np.ndarray = np.asarray(pre_event_output[1], dtype=float)
        set_veragrid_initial_vector(problem=problem, values=pre_event_values[-1, :])
        perturbed_state_label = perturb_first_veragrid_speed_state(
            problem=problem,
            perturbation_pu=configuration.event_state_step_pu,
            target_label=target_state_label,
            canonical_state_labels=canonical_state_labels,
        )
        post_event_output: tuple[np.ndarray, np.ndarray, bool, bool] = post_event_solver.simulate()
        time_values = np.concatenate((
            np.asarray(pre_event_output[0], dtype=float)[:-1],
            np.asarray(post_event_output[0], dtype=float),
        ))
        all_values = np.vstack((
            pre_event_values[:-1, :],
            np.asarray(post_event_output[1], dtype=float),
        ))
        well_initialized = bool(pre_event_output[2]) and bool(post_event_output[2])
        converged = bool(pre_event_output[3]) and bool(post_event_output[3])
        solver_timings = combine_solver_timings(
            first_solver=pre_event_solver,
            second_solver=post_event_solver,
        )
    integration_seconds: float = time.perf_counter() - integration_start
    if converged:
        pass
    else:
        raise RuntimeError("The VeraGrid RMS integration did not converge.")

    state_count: int = problem.get_states_number()
    state_values: np.ndarray = all_values[:, :state_count]
    algebraic_values: np.ndarray = all_values[:, state_count:]
    if canonical_state_labels is None:
        state_labels: list[str] = build_unique_variable_labels(list(problem.state_vars))
    elif len(canonical_state_labels) == state_count:
        state_labels = list(canonical_state_labels)
    else:
        raise ValueError(
            "Canonical state-label count does not match the VeraGrid RMS state count."
        )
    algebraic_labels: list[str] = build_unique_variable_labels(list(problem.algebraic_vars))

    output_directory: Path = engine_results_directory(
        configuration.case_tpe,
        "VeraGrid",
        configuration.scenario_tpe,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    export_start: float = time.perf_counter()
    write_trajectory_csv(
        output_path=output_directory / "state_trajectory.csv",
        time_values=time_values,
        values=state_values,
        labels=state_labels,
    )
    write_trajectory_csv(
        output_path=output_directory / "algebraic_trajectory.csv",
        time_values=time_values,
        values=algebraic_values,
        labels=algebraic_labels,
    )
    export_seconds: float = time.perf_counter() - export_start

    benchmark_total_seconds: float = (
        case_build_seconds
        + warm_pf_seconds
        + initialization_seconds
        + solver_setup_seconds
        + integration_seconds
    )
    process_total_seconds: float = time.perf_counter() - workflow_start
    timing_rows: list[tuple[str, str]] = list()
    timing_rows.append(("case_and_model_build_s", f"{case_build_seconds:.12e}"))
    timing_rows.append(("power_flow_cold_excluded_s", f"{cold_pf_seconds:.12e}"))
    timing_rows.append(("power_flow_warm_analyzed_s", f"{warm_pf_seconds:.12e}"))
    timing_rows.append(("dynamic_initialization_and_symbolic_numeric_s", f"{initialization_seconds:.12e}"))
    timing_rows.append(("solver_setup_s", f"{solver_setup_seconds:.12e}"))
    timing_rows.append(("rms_integration_s", f"{integration_seconds:.12e}"))
    timing_rows.append(("result_export_excluded_s", f"{export_seconds:.12e}"))
    timing_rows.append(("benchmark_total_analyzed_s", f"{benchmark_total_seconds:.12e}"))
    timing_rows.append(("process_wall_total_s", f"{process_total_seconds:.12e}"))
    timing_rows.append(("integration_rhs_s", f"{solver_timings['rhs_time']:.12e}"))
    timing_rows.append(("integration_jacobian_s", f"{solver_timings['jacobian_time']:.12e}"))
    timing_rows.append(("integration_linear_solver_s", f"{solver_timings['linear_solver_time']:.12e}"))
    write_key_value_csv(output_directory / "timings.csv", timing_rows)

    metadata_rows: list[tuple[str, str]] = list()
    metadata_rows.append(("engine", "VeraGrid"))
    metadata_rows.append(("case", case_label(configuration.case_tpe)))
    metadata_rows.append(("scenario", configuration.scenario_tpe.value))
    metadata_rows.append(("solver", "Backward Euler"))
    metadata_rows.append(("fixed_step", "True"))
    metadata_rows.append(("adaptive_step_reduction", "False"))
    metadata_rows.append(("time_step_s", f"{configuration.time_step:.12e}"))
    metadata_rows.append(("simulation_time_s", f"{configuration.simulation_time:.12e}"))
    metadata_rows.append(("integration_tolerance", f"{configuration.integration_tolerance:.12e}"))
    metadata_rows.append(("perturbation", configuration.scenario_tpe.value))
    metadata_rows.append(("perturbed_state", perturbed_state_label))
    metadata_rows.append(("speed_perturbation_pu", f"{configuration.speed_perturbation_pu:.12e}"))
    metadata_rows.append(("event_type", configuration.scenario_tpe.value))
    metadata_rows.append(("event_time_s", f"{configuration.event_time:.12e}"))
    metadata_rows.append(("event_state_step_pu", f"{configuration.event_state_step_pu:.12e}"))
    metadata_rows.append(("event_target_state", target_state_label))
    metadata_rows.append(("sample_count", str(time_values.size)))
    metadata_rows.append(("state_count", str(state_count)))
    metadata_rows.append(("algebraic_count", str(algebraic_values.shape[1])))
    metadata_rows.append(("power_flow_source", "second warm solve"))
    metadata_rows.append(("well_initialized", str(well_initialized)))
    metadata_rows.append(("converged", str(converged)))
    write_key_value_csv(output_directory / "metadata.csv", metadata_rows)
    print(f"VeraGrid RMS results written to: {output_directory}")
