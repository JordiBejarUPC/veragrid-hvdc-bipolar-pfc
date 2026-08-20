# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path

from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (DynamicIntegrationMethod,
                                         EmtInitializationMethod,
                                         EmtSolverTypes)

import run_emt_thevenin_line_Rload as base_case


def find_event_parameter(block: Block,
                         parameter_name: str) -> Var | None:
    """
    Find one event parameter in a symbolic block hierarchy.

    Resistance parameters of the three-phase shunt-load template are stored
    in ``event_dict`` rather than among the ordinary state or algebraic
    variables. Searching the hierarchy explicitly keeps the event attached to
    the exact variables used by the loaded ``.veragrid`` model.

    :param block: Root symbolic block of the EMT load model.
    :type block: Block
    :param parameter_name: Exact symbolic name of the required parameter.
    :type parameter_name: str
    :return: Matching event parameter, or ``None`` when it is unavailable.
    :rtype: Var | None
    """
    parameter: Var

    # Inspect the current block before its children so the search follows the
    # same ownership order as the symbolic model hierarchy.
    for parameter in block.event_dict:
        if parameter.name == parameter_name:
            return parameter
        else:
            pass

    child_block: Block

    # Phase parameters live in a child block in the saved shunt-load model,
    # hence the recursive stage is required for this concrete case.
    for child_block in block.children:
        child_parameter: Var | None = find_event_parameter(
            block=child_block,
            parameter_name=parameter_name,
        )
        if child_parameter is not None:
            return child_parameter
        else:
            pass

    return None


def deactivate_stored_event_groups(grid: MultiCircuit) -> None:
    """
    Deactivate event groups loaded from the stored comparison case.

    The source case contains an active no-event group used by the stationary
    benchmark. It must remain in the in-memory circuit for stable identities,
    but it is deactivated so only the new resistance-step trajectory is run.

    :param grid: Loaded circuit whose stored EMT groups must be deactivated.
    :type grid: MultiCircuit
    :return: None.
    :rtype: None
    """
    stored_group: EmtEventsGroup

    for stored_group in grid.emt_events_groups:
        stored_group.active = False


def build_step_emt_options() -> EmtOptions:
    """
    Build the 1.5-second EMT configuration for the two-step load case.

    The solver, integration method and five-microsecond time step remain
    identical to the validated stationary comparison. Only the horizon is
    extended so the restored 30 p.u. operating point is observed for 0.5 s.

    :return: Configured EMT options for the two-step run.
    :rtype: EmtOptions
    """
    return EmtOptions(
        time_step=5.0e-6,
        simulation_time=1.5,
        tolerance=1.0e-6,
        solver_type=EmtSolverTypes.StructuralAD,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=1,
    )


def run_step_emt(grid: MultiCircuit,
                 power_flow_results: PowerFlowResults3Ph) -> EmtResults:
    """
    Run the 1.5-second EMT trajectory containing both resistance steps.

    :param grid: Loaded circuit with the active two-step event group.
    :type grid: MultiCircuit
    :param power_flow_results: Three-phase operating point for initialization.
    :type power_flow_results: PowerFlowResults3Ph
    :return: Completed EMT simulation results.
    :rtype: EmtResults
    """
    emt_driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=build_step_emt_options(),
        pf_results_3ph=power_flow_results,
        pf_results=None,
    )

    # The driver applies both parameter transitions in one continuous state
    # trajectory, matching the single 1.5-second Simulink execution.
    emt_driver.run()
    emt_results: EmtResults | None = emt_driver.results

    if emt_results is not None:
        return emt_results
    else:
        raise RuntimeError("The EMT driver did not produce two-step results.")


def add_balanced_resistance_transition(
        grid: MultiCircuit,
        load: Load,
        events_group: EmtEventsGroup,
        phase_parameters: tuple[Var, Var, Var],
        event_time_s: float,
        resistance_value_pu: float,
        event_label: str) -> None:
    """
    Add one simultaneous A/B/C resistance transition to an event group.

    :param grid: Circuit that owns the resulting EMT events.
    :type grid: MultiCircuit
    :param load: Three-phase shunt load targeted by every event.
    :type load: Load
    :param events_group: Active group receiving the events.
    :type events_group: EmtEventsGroup
    :param phase_parameters: Resistance event parameters for phases A, B and C.
    :type phase_parameters: tuple[Var, Var, Var]
    :param event_time_s: Exact transition time in seconds.
    :type event_time_s: float
    :param resistance_value_pu: Resistance assigned after the transition.
    :type resistance_value_pu: float
    :param event_label: Human-readable transition description.
    :type event_label: str
    :return: None.
    :rtype: None
    """
    phase_names: tuple[str, str, str] = ("A", "B", "C")
    phase_index: int

    # VeraGrid models each phase resistance as an independent parameter, so a
    # balanced physical transition is represented by three aligned events.
    for phase_index in range(3):
        event: EmtEvent = EmtEvent(
            name="Rload phase " + phase_names[phase_index] + " " + event_label,
            device=load,
            parameter=phase_parameters[phase_index],
            time=event_time_s,
            value=resistance_value_pu,
            group=events_group,
            force_step_alignment=True,
        )
        grid.add_emt_event(event)


def configure_balanced_load_resistance_steps(
        grid: MultiCircuit,
        first_event_time_s: float,
        second_event_time_s: float,
        resistance_low_pu: float,
        resistance_restored_pu: float) -> EmtEventsGroup:
    """
    Add simultaneous ``R1 -> R2 -> R1`` transitions to the EMT load.

    All three phase parameters receive the same value at the same integration
    instant, preserving the balanced nature of the benchmark. The static load
    data remain unchanged, so the explicit initialization still starts from
    the original 30 p.u. resistance operating point.

    :param grid: Loaded Thevenin-line-resistive-load circuit.
    :type grid: MultiCircuit
    :param first_event_time_s: Time of the 30 to 24 p.u. transition.
    :type first_event_time_s: float
    :param second_event_time_s: Time of the 24 to 30 p.u. transition.
    :type second_event_time_s: float
    :param resistance_low_pu: Phase resistance during the middle interval.
    :type resistance_low_pu: float
    :param resistance_restored_pu: Phase resistance after the second event.
    :type resistance_restored_pu: float
    :return: Active EMT event group containing all six phase events.
    :rtype: EmtEventsGroup
    """
    load_count: int = len(grid.loads)

    # This benchmark has exactly one load; refusing an ambiguous selection
    # prevents an event from silently being attached to the wrong device.
    if load_count == 1:
        load: Load = grid.loads[0]
    else:
        raise RuntimeError(
            "Expected exactly one load, found " + str(load_count) + "."
        )

    load_model: Block = load.emt_model
    resistance_a: Var | None = find_event_parameter(
        block=load_model,
        parameter_name="R_A_Shunt_R_3ph",
    )
    resistance_b: Var | None = find_event_parameter(
        block=load_model,
        parameter_name="R_B_Shunt_R_3ph",
    )
    resistance_c: Var | None = find_event_parameter(
        block=load_model,
        parameter_name="R_C_Shunt_R_3ph",
    )

    # A balanced step is valid only if the saved EMT template exposes all
    # three phase resistances as event-capable symbolic parameters.
    parameters_found: bool = (
        resistance_a is not None
        and resistance_b is not None
        and resistance_c is not None
    )

    if parameters_found:
        phase_parameters: tuple[Var, Var, Var] = (
            resistance_a,
            resistance_b,
            resistance_c,
        )
    else:
        raise RuntimeError(
            "The EMT load model does not expose all three phase resistances."
        )

    # Preserve stored groups but ensure the driver simulates only the newly
    # declared step case and exports one unambiguous result column.
    deactivate_stored_event_groups(grid=grid)
    events_group: EmtEventsGroup = EmtEventsGroup(
        name="balanced_Rload_steps_30_to_24_to_30_pu",
        active=True,
    )
    grid.add_emt_events_group(events_group)

    # The first transition increases absorbed active power; the second restores
    # the exact initial parameter values without reinitializing dynamic states.
    add_balanced_resistance_transition(
        grid=grid,
        load=load,
        events_group=events_group,
        phase_parameters=phase_parameters,
        event_time_s=first_event_time_s,
        resistance_value_pu=resistance_low_pu,
        event_label="30 to 24 pu",
    )
    add_balanced_resistance_transition(
        grid=grid,
        load=load,
        events_group=events_group,
        phase_parameters=phase_parameters,
        event_time_s=second_event_time_s,
        resistance_value_pu=resistance_restored_pu,
        event_label="24 to 30 pu",
    )

    return events_group


def report_step_configuration(first_event_time_s: float,
                              second_event_time_s: float,
                              resistance_initial_pu: float,
                              resistance_middle_pu: float) -> None:
    """
    Print the balanced load-step definition used by the completed run.

    :param first_event_time_s: Time of the resistance reduction.
    :type first_event_time_s: float
    :param second_event_time_s: Time of the resistance restoration.
    :type second_event_time_s: float
    :param resistance_initial_pu: Initial and restored phase resistance.
    :type resistance_initial_pu: float
    :param resistance_middle_pu: Phase resistance between the two events.
    :type resistance_middle_pu: float
    :return: None.
    :rtype: None
    """
    print("Balanced Rload step times: " + str(first_event_time_s)
          + " s and " + str(second_event_time_s) + " s")
    print(
        "Rload phases A/B/C: "
        + str(resistance_initial_pu)
        + " pu -> "
        + str(resistance_middle_pu)
        + " pu -> "
        + str(resistance_initial_pu)
        + " pu"
    )


def report_step_results(results: EmtResults,
                        group_index: int,
                        csv_path: Path) -> None:
    """
    Report the numerical status of the completed 1.5-second step run.

    :param results: Completed two-step EMT results.
    :type results: EmtResults
    :param group_index: Exported active event-group index.
    :type group_index: int
    :param csv_path: Generated step-case CSV path.
    :type csv_path: Path
    :return: None.
    :rtype: None
    """
    well_initialized: bool = bool(results.well_initialized[group_index])
    converged: bool = bool(results.converged[group_index])
    sample_count: int = int(results.values.shape[0])

    print("EMT configuration: DAE trapezoidal, dt=5e-6 s, duration=1.5 s")
    print("Initialization method: explicit")
    print("EMT well initialized: " + str(well_initialized))
    print("EMT converged: " + str(converged))
    print("Exported samples: " + str(sample_count))
    print("p.u. CSV: " + str(csv_path))

    if well_initialized and converged:
        pass
    else:
        raise RuntimeError(
            "The two-step EMT run did not finish with a valid numerical status."
        )


def main() -> None:
    """
    Run and export the 1.5-second EMT two-step load comparison case.

    The numerical configuration and explicit initialization are imported from
    the already validated stationary script. Only the in-memory event group
    and the event-specific output file differ from that reference run.

    :return: None.
    :rtype: None
    """
    # Keep the event exactly on the common five-microsecond time grid. Reducing
    # resistance by 20 percent produces an approximately 25 percent active-
    # power increase while remaining a moderate, easy-to-compare disturbance.
    first_event_time_s: float = 0.5
    second_event_time_s: float = 1.0
    resistance_initial_pu: float = 30.0
    resistance_middle_pu: float = 120.0

    # Resolve every artifact relative to this script so PyCharm and terminal
    # runs operate on the same case regardless of their working directory.
    case_directory: Path = Path(__file__).resolve().parent
    grid_path: Path = case_directory / "thev_pi_Rload.veragrid"
    csv_path: Path = (
        case_directory / "veragrid_results_thev_line_Rload_steps_pu.csv"
    )

    if grid_path.is_file():
        grid: MultiCircuit = base_case.open_case(grid_path=grid_path)
        events_group: EmtEventsGroup = configure_balanced_load_resistance_steps(
            grid=grid,
            first_event_time_s=first_event_time_s,
            second_event_time_s=second_event_time_s,
            resistance_low_pu=resistance_middle_pu,
            resistance_restored_pu=resistance_initial_pu,
        )
        power_flow_results: PowerFlowResults3Ph = (
            base_case.run_three_phase_power_flow(grid=grid)
        )
        emt_results: EmtResults = run_step_emt(
            grid=grid,
            power_flow_results=power_flow_results,
        )
        group_index: int = base_case.get_simulated_group_index(
            results=emt_results,
        )

        # The explicit reference to the group keeps the configuration live and
        # makes the intended single active trajectory evident to maintainers.
        if events_group.active:
            base_case.export_pu_results(
                results=emt_results,
                group_index=group_index,
                csv_path=csv_path,
            )
            report_step_results(
                results=emt_results,
                group_index=group_index,
                csv_path=csv_path,
            )
            report_step_configuration(
                first_event_time_s=first_event_time_s,
                second_event_time_s=second_event_time_s,
                resistance_initial_pu=resistance_initial_pu,
                resistance_middle_pu=resistance_middle_pu,
            )
        else:
            raise RuntimeError("The balanced Rload event group is inactive.")
    else:
        raise FileNotFoundError("Missing VeraGrid case: " + str(grid_path))


if __name__ == "__main__":
    main()
else:
    pass
