# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (BranchImpedanceMode, DynamicIntegrationMethod,
                                         EmtInitializationMethod, EmtSolverTypes, SolverType)


def build_power_flow_options() -> PowerFlowOptions:
    """
    Build the three-phase power-flow configuration used to initialize EMT.

    The balanced case is solved with the three-phase driver so the explicit
    EMT initialization receives one phase-consistent operating point.

    :return: Configured three-phase power-flow options.
    :rtype: PowerFlowOptions
    """
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )


def build_emt_options() -> EmtOptions:
    """
    Build the fixed-step EMT configuration shared with the Simulink case.

    DAE trapezoidal integration matches a discrete Specialized Power Systems
    ``powergui`` using its trapezoidal/Tustin discretization. A five-microsecond
    step provides exactly 200,000 integration intervals over one second.

    :return: Configured EMT options for the comparison run.
    :rtype: EmtOptions
    """
    return EmtOptions(
        time_step=5.0e-6,
        simulation_time=1.0,
        tolerance=1.0e-6,
        solver_type=EmtSolverTypes.StructuralAD,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=1,
    )


def open_case(grid_path: Path) -> MultiCircuit:
    """
    Open the VeraGrid case stored beside this script.

    :param grid_path: Absolute path to the ``.veragrid`` case.
    :type grid_path: Path
    :return: Loaded electrical grid.
    :rtype: MultiCircuit
    """
    file_open: FileOpen = FileOpen(file_name=str(grid_path))
    grid: MultiCircuit | None = file_open.open()

    if grid is not None:
        return grid
    else:
        raise RuntimeError("VeraGrid did not return a circuit for " + str(grid_path))


def run_three_phase_power_flow(grid: MultiCircuit) -> PowerFlowResults3Ph:
    """
    Run the three-phase power flow required by explicit EMT initialization.

    :param grid: Loaded comparison grid.
    :type grid: MultiCircuit
    :return: Converged three-phase power-flow results.
    :rtype: PowerFlowResults3Ph
    """
    power_flow_driver: PowerFlowDriver3Ph = PowerFlowDriver3Ph(
        grid=grid,
        options=build_power_flow_options(),
    )

    # The power-flow state supplies phase voltages and branch currents to the
    # explicit EMT initialization, so EMT must not start after a failed solve.
    power_flow_driver.run()
    power_flow_results: PowerFlowResults3Ph = power_flow_driver.results
    power_flow_converged: bool = bool(np.all(power_flow_results.converged))

    if power_flow_converged:
        return power_flow_results
    else:
        raise RuntimeError("The three-phase power flow did not converge.")


def run_emt(grid: MultiCircuit,
            power_flow_results: PowerFlowResults3Ph) -> EmtResults:
    """
    Run the one-second fixed-step EMT simulation.

    :param grid: Loaded comparison grid with its stored EMT models.
    :type grid: MultiCircuit
    :param power_flow_results: Three-phase operating point for initialization.
    :type power_flow_results: PowerFlowResults3Ph
    :return: Completed EMT simulation results.
    :rtype: EmtResults
    """
    emt_driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=build_emt_options(),
        pf_results_3ph=power_flow_results,
        pf_results=None,
    )

    # The active no-event group stored in the case produces the undisturbed
    # trajectory that is directly comparable with the current Simulink setup.
    emt_driver.run()
    emt_results: EmtResults | None = emt_driver.results

    if emt_results is not None:
        return emt_results
    else:
        raise RuntimeError("The EMT driver did not produce results.")


def get_simulated_group_index(results: EmtResults) -> int:
    """
    Select the first event-group column that contains simulated samples.

    :param results: Completed EMT results container.
    :type results: EmtResults
    :return: Index of the first simulated EMT event group.
    :rtype: int
    """
    simulated_indices: np.ndarray = np.flatnonzero(results.has_event_group_results)

    if simulated_indices.size > 0:
        return int(simulated_indices[0])
    else:
        raise RuntimeError("No active EMT event group was simulated.")


def export_pu_results(results: EmtResults,
                      group_index: int,
                      csv_path: Path) -> None:
    """
    Export every EMT state and algebraic variable to a p.u. CSV file.

    VeraGrid EMT electrical trajectories already use the model p.u. bases, so
    no additional voltage or current scaling is applied here. Rotor/source
    angles are converted from radians to electrical revolutions to match the
    Simulink exporter, where one revolution is one p.u. Time is converted from
    the result datetime index to elapsed seconds for waveform alignment.

    :param results: Completed EMT results container.
    :type results: EmtResults
    :param group_index: Simulated event-group column to export.
    :type group_index: int
    :param csv_path: Destination CSV path.
    :type csv_path: Path
    :return: None.
    :rtype: None
    """
    time_nanoseconds: np.ndarray = results.time_array.asi8
    time_seconds: np.ndarray = (time_nanoseconds - time_nanoseconds[0]) * 1.0e-9
    variables: List[Var] = results.variables
    column_names: List[str] = list()
    values_pu: np.ndarray = results.values[:, :, group_index].copy()
    variable: Var
    variable_index: int

    # Global symbolic names remain unique even when devices expose local
    # variables with identical phase names. All exported value columns carry
    # an explicit p.u. suffix so their scaling is evident at comparison time.
    for variable_index, variable in enumerate(variables):
        global_name: str = results.uid2vars_glob_name[variable.uid]
        column_names.append(global_name + "_pu")

        # Angles are dimensionless but the two tools otherwise use different
        # units. Converting radians to revolutions matches phase_*_pu from the
        # Simulink CSV without altering electrical voltage/current states.
        if variable.name.startswith("theta"):
            values_pu[:, variable_index] = values_pu[:, variable_index] / (2.0 * np.pi)
        else:
            pass

    output_frame: pd.DataFrame = pd.DataFrame(values_pu, columns=column_names)
    output_frame.insert(loc=0, column="time_s", value=time_seconds)
    output_frame.to_csv(csv_path, index=False)


def report_results(results: EmtResults,
                   group_index: int,
                   csv_path: Path) -> None:
    """
    Print the numerical status and output location of the comparison run.

    :param results: Completed EMT results container.
    :type results: EmtResults
    :param group_index: Exported event-group index.
    :type group_index: int
    :param csv_path: Generated p.u. CSV path.
    :type csv_path: Path
    :return: None.
    :rtype: None
    """
    well_initialized: bool = bool(results.well_initialized[group_index])
    converged: bool = bool(results.converged[group_index])
    sample_count: int = int(results.values.shape[0])

    print("EMT configuration: DAE trapezoidal, dt=5e-6 s, duration=1.0 s")
    print("Initialization method: explicit")
    print("EMT well initialized: " + str(well_initialized))
    print("EMT converged: " + str(converged))
    print("Exported samples: " + str(sample_count))
    print("p.u. CSV: " + str(csv_path))

    if well_initialized and converged:
        pass
    else:
        raise RuntimeError("The EMT run did not finish with a valid numerical status.")


def main() -> None:
    """
    Open the stored case, initialize it and run the comparison EMT simulation.

    :return: None.
    :rtype: None
    """
    # Resolving paths from this file makes the script independent of the shell
    # working directory and keeps the case and exported waveform together.
    case_directory: Path = Path(__file__).resolve().parent
    grid_path: Path = case_directory / "thev_pi_Rload.veragrid"
    csv_path: Path = case_directory / "veragrid_results_thev_line_Rload_pu.csv"

    if grid_path.is_file():
        grid: MultiCircuit = open_case(grid_path=grid_path)
        power_flow_results: PowerFlowResults3Ph = run_three_phase_power_flow(grid=grid)
        emt_results: EmtResults = run_emt(
            grid=grid,
            power_flow_results=power_flow_results,
        )
        group_index: int = get_simulated_group_index(results=emt_results)
        export_pu_results(
            results=emt_results,
            group_index=group_index,
            csv_path=csv_path,
        )
        report_results(
            results=emt_results,
            group_index=group_index,
            csv_path=csv_path,
        )
    else:
        raise FileNotFoundError("Missing VeraGrid case: " + str(grid_path))


if __name__ == "__main__":
    main()
else:
    pass
