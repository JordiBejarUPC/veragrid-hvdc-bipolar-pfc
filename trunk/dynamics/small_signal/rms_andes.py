# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Run any validated ANDES RMS time-domain benchmark from PyCharm."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any

import andes
import numpy as np

from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import case_label
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import engine_results_directory
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import perturbation_state_label
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkCase
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkConfiguration
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkScenario
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import write_key_value_csv
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import write_trajectory_csv


def resolve_andes_case_path(case_tpe: RmsBenchmarkCase) -> Path:
    """Resolve the physical ANDES case used by one benchmark preset.

    :param case_tpe: Selected benchmark case.
    :return: Absolute ANDES-readable case path.
    """
    script_directory: Path = Path(__file__).resolve().parent
    if case_tpe is RmsBenchmarkCase.KUNDUR:
        case_path: Path = script_directory / "kundur_ieee_no_shunt.json"
    elif case_tpe is RmsBenchmarkCase.IEEE14:
        case_path = Path(andes.get_case("ieee14/ieee14_full.xlsx"))
    elif case_tpe is RmsBenchmarkCase.IEEE39:
        case_path = Path(andes.get_case("ieee39/ieee39_full.xlsx"))
    elif case_tpe is RmsBenchmarkCase.NPCC140:
        case_path = Path(andes.get_case("npcc/npcc.xlsx"))
    else:
        case_path = Path(andes.get_case("wecc/wecc_full.xlsx"))
    return case_path.resolve()


def andes_power_flow_tolerance(case_tpe: RmsBenchmarkCase) -> float:
    """Return the strictest established ANDES tolerance for one case.

    :param case_tpe: Selected benchmark case.
    :return: Newton power-flow tolerance.
    """
    if case_tpe is RmsBenchmarkCase.WECC179:
        tolerance: float = 1.0e-10
    else:
        tolerance = 1.0e-13
    return tolerance


def configure_andes_system(
    system: Any,
    configuration: RmsBenchmarkConfiguration,
) -> None:
    """Configure constant-power loads and an exact fixed-step Backward Euler run.

    :param system: Loaded ANDES system.
    :param configuration: Shared benchmark configuration.
    :return: None.
    """
    # These fractions disable ANDES voltage-dependent load conversion so the
    # dynamic case retains the same constant-power model used by VeraGrid.
    system.files.no_output = True
    system.PQ.config.p2p = 1.0
    system.PQ.config.p2i = 0
    system.PQ.config.p2z = 0
    system.PQ.config.q2q = 1.0
    system.PQ.config.q2i = 0
    system.PQ.config.q2z = 0
    system.PFlow.config.tol = andes_power_flow_tolerance(configuration.case_tpe)

    # Both tools now solve the identical implicit Backward Euler formula on an
    # immutable 1 ms grid. Step shrinking and stability early-stop criteria are
    # disabled because VeraGrid does not use them in this benchmark.
    system.TDS.config.method = "backeuler"
    system.TDS.set_method("backeuler")
    system.TDS.config.t0 = 0.0
    system.TDS.config.tf = configuration.simulation_time
    system.TDS.config.tstep = configuration.time_step
    system.TDS.config.fixt = 1
    system.TDS.config.shrinkt = 0
    system.TDS.config.tol = configuration.integration_tolerance
    system.TDS.config.max_iter = configuration.maximum_iterations
    system.TDS.config.honest = 1
    system.TDS.config.g_scale = 0
    system.TDS.config.reset_tiny = 0
    system.TDS.config.criteria = 0
    system.TDS.config.no_tqdm = 1
    system.TDS.config.save_every = 1


def disable_andes_case_events(system: Any, simulation_time: float) -> list[str]:
    """Disable case-file switching devices absent from the VeraGrid scenario.

    :param system: Loaded ANDES system before setup.
    :param simulation_time: Benchmark horizon in seconds.
    :return: Labels and counts for disabled event model types.
    """
    disabled_models: list[str] = list()
    event_model_names: tuple[str, ...] = ("Toggle", "Alter", "Fault")
    event_model_name: str
    for event_model_name in event_model_names:
        event_model: Any | None = system.models.get(event_model_name, None)
        if event_model is not None and int(event_model.n) > 0:
            event_index: int
            for event_index in range(int(event_model.n)):
                event_model.u.v[event_index] = 0.0
                # ANDES still registers switch times for inactive event rows.
                # Moving their timers beyond the benchmark horizon preserves
                # the exact uniform grid required for a solver comparison.
                if event_model_name in ("Toggle", "Alter"):
                    event_model.t.v[event_index] = simulation_time + 10.0
                elif event_model_name == "Fault":
                    event_model.tf.v[event_index] = simulation_time + 10.0
                    event_model.tc.v[event_index] = simulation_time + 11.0
                else:
                    pass
            disabled_models.append(f"{event_model_name}:{int(event_model.n)}")
        else:
            pass
    return disabled_models


def select_andes_initial_outputs(system: Any) -> tuple[np.ndarray, np.ndarray]:
    """Select initial variables using the same ANDES Output mask as TDS storage.

    :param system: Initialized ANDES system.
    :return: Initial state and algebraic output rows.
    """
    if int(system.Output.n) > 0:
        initial_states: np.ndarray = np.asarray(system.dae.x[system.Output.xidx], dtype=float)
        initial_algebraics: np.ndarray = np.asarray(system.dae.y[system.Output.yidx], dtype=float)
    else:
        initial_states = np.asarray(system.dae.x, dtype=float).copy()
        initial_algebraics = np.asarray(system.dae.y, dtype=float).copy()
    return initial_states, initial_algebraics


def select_uniform_andes_outputs(
    time_values: np.ndarray,
    state_values: np.ndarray,
    algebraic_values: np.ndarray,
    configuration: RmsBenchmarkConfiguration,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Select exactly one stored ANDES row for every requested fixed-grid time.

    ANDES can store the final horizon twice when a timed event is present. The
    nonlinear solves still occur on the uniform grid; this function removes the
    duplicate storage row and rejects any missing requested time.

    :param time_values: Raw ANDES stored times including the explicit initial row.
    :param state_values: Raw state trajectories.
    :param algebraic_values: Raw algebraic trajectories.
    :param configuration: Shared fixed-grid settings.
    :return: Uniform times and aligned state/algebraic trajectories.
    """
    step_count: int = int(round(configuration.simulation_time / configuration.time_step))
    expected_times: np.ndarray = np.arange(step_count + 1, dtype=float) * configuration.time_step
    selected_indexes: np.ndarray = np.empty(expected_times.size, dtype=int)
    time_index: int
    for time_index in range(expected_times.size):
        nearest_index: int = int(np.argmin(np.abs(time_values - expected_times[time_index])))
        time_error: float = abs(float(time_values[nearest_index]) - float(expected_times[time_index]))
        if time_error <= 1.0e-10:
            selected_indexes[time_index] = nearest_index
        else:
            raise ValueError(
                f"ANDES did not store requested fixed-grid time {expected_times[time_index]:.12e}."
            )
    return (
        expected_times,
        state_values[selected_indexes, :],
        algebraic_values[selected_indexes, :],
    )


def perturb_first_andes_speed_state(
    system: Any,
    perturbation_pu: float,
    target_label: str,
) -> str:
    """Apply the common initial speed perturbation to the first ANDES machine.

    :param system: Dynamically initialized ANDES system.
    :param perturbation_pu: Additive rotor-speed perturbation in per unit.
    :param target_label: Common physical state label selected for this case.
    :return: Perturbed ANDES state label.
    """
    perturbation_applied: bool = False
    perturbed_label: str = ""
    state_index: int
    for state_index in range(len(system.dae.x_name)):
        state_label: str = str(system.dae.x_name[state_index])
        if not perturbation_applied and state_label == target_label:
            system.dae.x[state_index] = float(system.dae.x[state_index]) + perturbation_pu
            perturbed_label = state_label
            perturbation_applied = True
        else:
            pass
    if perturbation_applied:
        system.vars_to_models()
    else:
        raise ValueError("No ANDES omega state is available for the RMS perturbation.")
    return perturbed_label


def run_andes_rms(configuration: RmsBenchmarkConfiguration) -> None:
    """Run, time and persist one ANDES RMS time-domain benchmark.

    :param configuration: Case and common numerical settings.
    :return: None.
    """
    workflow_start: float = time.perf_counter()
    case_path: Path = resolve_andes_case_path(configuration.case_tpe)
    output_directory: Path = engine_results_directory(
        configuration.case_tpe,
        "Andes",
        configuration.scenario_tpe,
    )
    output_directory.mkdir(parents=True, exist_ok=True)

    # Parsing and object construction are timed independently from system.setup,
    # which creates model addresses and sparse numerical structures in ANDES.
    load_start: float = time.perf_counter()
    system: Any = andes.load(
        str(case_path),
        default_config=True,
        setup=False,
        autogen_stale=False,
    )
    load_seconds: float = time.perf_counter() - load_start
    configure_andes_system(system=system, configuration=configuration)
    disabled_event_models: list[str] = disable_andes_case_events(
        system=system,
        simulation_time=configuration.simulation_time,
    )
    setup_start: float = time.perf_counter()
    setup_success: bool = bool(system.setup())
    setup_seconds: float = time.perf_counter() - setup_start
    if setup_success:
        pass
    else:
        raise RuntimeError(f"ANDES setup failed for {case_path}.")

    # The first solve is the documented cold pass. The second pass is the only
    # power-flow result used to initialize and time the comparable RMS workflow.
    cold_pf_start: float = time.perf_counter()
    cold_pf_success: bool = bool(system.PFlow.run())
    cold_pf_seconds: float = time.perf_counter() - cold_pf_start
    if cold_pf_success:
        pass
    else:
        raise RuntimeError("The cold ANDES power flow did not converge.")
    warm_pf_start: float = time.perf_counter()
    warm_pf_success: bool = bool(system.PFlow.run())
    warm_pf_seconds: float = time.perf_counter() - warm_pf_start
    if warm_pf_success:
        pass
    else:
        raise RuntimeError("The authoritative warm ANDES power flow did not converge.")

    # Explicit TDS.init isolates dynamic model initialization, DAE expansion,
    # sparse-pattern assembly and mass-matrix construction from integration.
    initialization_start: float = time.perf_counter()
    system.TDS.init()
    initialization_seconds: float = time.perf_counter() - initialization_start
    if (
        configuration.scenario_tpe is RmsBenchmarkScenario.BASE
        and configuration.speed_perturbation_pu != 0.0
    ):
        perturbed_state_label: str = perturb_first_andes_speed_state(
            system=system,
            perturbation_pu=configuration.speed_perturbation_pu,
            target_label=perturbation_state_label(configuration.case_tpe),
        )
    else:
        perturbed_state_label = "none"
    initial_states: np.ndarray
    initial_algebraics: np.ndarray
    initial_states, initial_algebraics = select_andes_initial_outputs(system)
    state_labels: list[str] = list(system.dae.x_name_output)
    algebraic_labels: list[str] = list(system.dae.y_name_output)

    # Calling run after explicit initialization uses ANDES resume semantics.
    # Event cases stop exactly at the event time, apply the state discontinuity,
    # and resume on the same fixed grid without using an engine-specific timer.
    integration_start: float = time.perf_counter()
    event_states: np.ndarray | None = None
    event_algebraics: np.ndarray | None = None
    if configuration.scenario_tpe is RmsBenchmarkScenario.BASE:
        integration_success: bool = bool(system.TDS.run(no_summary=True))
    else:
        system.TDS.config.tf = configuration.event_time
        pre_event_success: bool = bool(system.TDS.run(no_summary=True))
        if pre_event_success and bool(system.TDS.converged):
            pass
        else:
            raise RuntimeError("The pre-event ANDES RMS segment did not converge.")
        perturbed_state_label = perturb_first_andes_speed_state(
            system=system,
            perturbation_pu=configuration.event_state_step_pu,
            target_label=perturbation_state_label(configuration.case_tpe),
        )
        event_states, event_algebraics = select_andes_initial_outputs(system)
        system.TDS.config.tf = configuration.simulation_time
        integration_success = bool(system.TDS.run(no_summary=True))
    integration_seconds: float = time.perf_counter() - integration_start
    stored_time: np.ndarray = np.asarray(system.dae.ts.t, dtype=float)
    stored_states: np.ndarray = np.asarray(system.dae.ts.x, dtype=float)
    stored_algebraics: np.ndarray = np.asarray(system.dae.ts.y, dtype=float)

    # ANDES can attempt a zero-length trailing step when floating-point time
    # accumulation lands infinitesimally below ``tf``. In that case ``run``
    # reports failure even though the requested final sample is already stored.
    # Accept only a complete requested grid; a genuine early termination still
    # raises below and can never enter the benchmark comparison.
    final_time_tolerance: float = max(1.0e-12, configuration.time_step * 1.0e-9)
    integration_grid_complete: bool = bool(
        stored_time.size > 0
        and np.isclose(
            stored_time[-1],
            configuration.simulation_time,
            rtol=0.0,
            atol=final_time_tolerance,
        )
    )
    raw_integration_converged: bool = bool(integration_success and system.TDS.converged)
    if raw_integration_converged or integration_grid_complete:
        accepted_integration: bool = True
    else:
        raise RuntimeError("The ANDES RMS integration did not produce the complete requested grid.")

    time_values: np.ndarray = np.concatenate((np.zeros(1, dtype=float), stored_time))
    state_values: np.ndarray = np.vstack((initial_states, stored_states))
    algebraic_values: np.ndarray = np.vstack((initial_algebraics, stored_algebraics))
    time_values, state_values, algebraic_values = select_uniform_andes_outputs(
        time_values=time_values,
        state_values=state_values,
        algebraic_values=algebraic_values,
        configuration=configuration,
    )
    if event_states is not None and event_algebraics is not None:
        event_index: int = int(round(configuration.event_time / configuration.time_step))
        state_values[event_index, :] = event_states
        algebraic_values[event_index, :] = event_algebraics
    else:
        pass

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
        load_seconds
        + setup_seconds
        + warm_pf_seconds
        + initialization_seconds
        + integration_seconds
    )
    process_total_seconds: float = time.perf_counter() - workflow_start
    timing_rows: list[tuple[str, str]] = list()
    timing_rows.append(("case_and_model_build_s", f"{load_seconds:.12e}"))
    timing_rows.append(("andes_system_setup_s", f"{setup_seconds:.12e}"))
    timing_rows.append(("power_flow_cold_excluded_s", f"{cold_pf_seconds:.12e}"))
    timing_rows.append(("power_flow_warm_analyzed_s", f"{warm_pf_seconds:.12e}"))
    timing_rows.append(("dynamic_initialization_and_symbolic_numeric_s", f"{initialization_seconds:.12e}"))
    timing_rows.append(("solver_setup_s", "N/A: included in ANDES dynamic initialization"))
    timing_rows.append(("rms_integration_s", f"{integration_seconds:.12e}"))
    timing_rows.append(("result_export_excluded_s", f"{export_seconds:.12e}"))
    timing_rows.append(("benchmark_total_analyzed_s", f"{benchmark_total_seconds:.12e}"))
    timing_rows.append(("process_wall_total_s", f"{process_total_seconds:.12e}"))
    timing_rows.append(("integration_rhs_s", "N/A: ANDES does not expose this phase"))
    timing_rows.append(("integration_jacobian_s", "N/A: ANDES does not expose this phase"))
    timing_rows.append(("integration_linear_solver_s", "N/A: ANDES does not expose this phase"))
    write_key_value_csv(output_directory / "timings.csv", timing_rows)

    metadata_rows: list[tuple[str, str]] = list()
    metadata_rows.append(("engine", "ANDES"))
    metadata_rows.append(("andes_version", str(andes.__version__)))
    metadata_rows.append(("case", case_label(configuration.case_tpe)))
    metadata_rows.append(("scenario", configuration.scenario_tpe.value))
    metadata_rows.append(("case_path", str(case_path)))
    metadata_rows.append(("solver", "Backward Euler"))
    metadata_rows.append(("newton_jacobian", "honest: refreshed each iteration"))
    metadata_rows.append(("algebraic_residual_scaling", "disabled"))
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
    metadata_rows.append(("event_target_state", perturbation_state_label(configuration.case_tpe)))
    metadata_rows.append(("sample_count", str(time_values.size)))
    metadata_rows.append(("state_count", str(state_values.shape[1])))
    metadata_rows.append(("algebraic_count", str(algebraic_values.shape[1])))
    metadata_rows.append(("power_flow_source", "second warm solve"))
    metadata_rows.append(("case_file_events", "disabled before applying the selected benchmark scenario"))
    metadata_rows.append(("disabled_event_models", ";".join(disabled_event_models)))
    metadata_rows.append(("well_initialized", str(bool(system.TDS.test_ok))))
    metadata_rows.append(("converged", str(accepted_integration)))
    metadata_rows.append(("andes_raw_run_converged", str(raw_integration_converged)))
    metadata_rows.append(("requested_grid_complete", str(integration_grid_complete)))
    write_key_value_csv(output_directory / "metadata.csv", metadata_rows)
    print(f"ANDES RMS results written to: {output_directory}")


def main() -> None:
    """Select and run one ANDES case directly with the PyCharm Run button.

    Change only the uncommented ``selected_case`` line below. No terminal
    argument is required.

    :return: None.
    """
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.KUNDUR
    selected_case: RmsBenchmarkCase = RmsBenchmarkCase.IEEE14
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.IEEE39
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.NPCC140
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.WECC179
    configuration: RmsBenchmarkConfiguration = RmsBenchmarkConfiguration(selected_case)
    run_andes_rms(configuration)


if __name__ == "__main__":
    main()
else:
    pass
