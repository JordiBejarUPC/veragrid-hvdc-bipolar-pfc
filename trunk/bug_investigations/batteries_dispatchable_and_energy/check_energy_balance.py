from __future__ import annotations

from pathlib import Path
from typing import Sequence
import argparse

import numpy as np

from VeraGridEngine.Devices.Injections.battery import Battery
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.OPF.Formulations.linear_opf_ts import get_model_step_hours
from VeraGridEngine.Simulations.OPF.opf_ts_driver import OptimalPowerFlowTimeSeriesDriver
from VeraGridEngine.api import (
    FileOpen,
    MIPFramework,
    MIPSolvers,
    OpfDispatchMode,
    OptimalPowerFlowOptions,
    PowerFlowOptions,
    SolverType,
    TimeGrouping,
)


DEFAULT_CASE_PATH = Path(__file__).with_name("SimulacionSantaLucia_fixed.veragrid")
DEFAULT_TOLERANCE_MWH = 1e-6
DEFAULT_POWER_TOLERANCE_MW = 1e-6
DEFAULT_REPORT_LIMIT = 20


class EnergyBalanceViolation:
    """
    Store one battery-energy balance mismatch.

    :param battery_name: Battery name.
    :param local_t: Local time index inside the simulated horizon.
    :param global_t: Original grid time index.
    :param dispatchable: Dispatchability flag at the checked time step.
    :param dt_hours: Time-step duration in hours.
    :param power_mw: Solved battery active power in MW.
    :param previous_energy_mwh: Previous battery energy in MWh.
    :param expected_energy_mwh: Recomputed energy in MWh.
    :param actual_energy_mwh: Reported solved energy in MWh.
    :param abs_error_mwh: Absolute mismatch in MWh.
    """

    __slots__ = (
        "battery_name",
        "local_t",
        "global_t",
        "dispatchable",
        "dt_hours",
        "power_mw",
        "previous_energy_mwh",
        "expected_energy_mwh",
        "actual_energy_mwh",
        "abs_error_mwh",
    )

    def __init__(
        self,
        battery_name: str,
        local_t: int,
        global_t: int,
        dispatchable: bool,
        dt_hours: float,
        power_mw: float,
        previous_energy_mwh: float,
        expected_energy_mwh: float,
        actual_energy_mwh: float,
        abs_error_mwh: float,
    ) -> None:
        """
        Initialize one stored mismatch.

        :return: ``None``.
        """
        self.battery_name: str = battery_name
        self.local_t: int = local_t
        self.global_t: int = global_t
        self.dispatchable: bool = dispatchable
        self.dt_hours: float = dt_hours
        self.power_mw: float = power_mw
        self.previous_energy_mwh: float = previous_energy_mwh
        self.expected_energy_mwh: float = expected_energy_mwh
        self.actual_energy_mwh: float = actual_energy_mwh
        self.abs_error_mwh: float = abs_error_mwh


class GridBalanceViolation:
    """
    Store one whole-grid power and energy balance mismatch.

    :param local_t: Local time index inside the simulated horizon.
    :param global_t: Original grid time index.
    :param dt_hours: Time-step duration in hours.
    :param generation_mw: Total solved generator power in MW.
    :param battery_mw: Total solved battery power in MW.
    :param served_load_mw: Total served load in MW.
    :param power_residual_mw: Whole-grid power residual in MW.
    :param energy_residual_mwh: Whole-grid energy residual in MWh.
    """

    __slots__ = (
        "local_t",
        "global_t",
        "dt_hours",
        "generation_mw",
        "battery_mw",
        "served_load_mw",
        "power_residual_mw",
        "energy_residual_mwh",
    )

    def __init__(
        self,
        local_t: int,
        global_t: int,
        dt_hours: float,
        generation_mw: float,
        battery_mw: float,
        served_load_mw: float,
        power_residual_mw: float,
        energy_residual_mwh: float,
    ) -> None:
        """
        Initialize one stored mismatch.

        :return: ``None``.
        """
        self.local_t: int = local_t
        self.global_t: int = global_t
        self.dt_hours: float = dt_hours
        self.generation_mw: float = generation_mw
        self.battery_mw: float = battery_mw
        self.served_load_mw: float = served_load_mw
        self.power_residual_mw: float = power_residual_mw
        self.energy_residual_mwh: float = energy_residual_mwh


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    :return: Parsed arguments namespace.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Run VeraGrid linear OPF TS and check battery energy balance."
    )

    # The case path stays local to the investigation folder by default so the script is runnable
    # without additional setup.
    parser.add_argument(
        "--case",
        type=Path,
        default=DEFAULT_CASE_PATH,
        help="Path to the .veragrid case to solve.",
    )
    parser.add_argument(
        "--tolerance-mwh",
        type=float,
        default=DEFAULT_TOLERANCE_MWH,
        help="Absolute tolerance used for the energy-balance check in MWh.",
    )
    parser.add_argument(
        "--power-tolerance-mw",
        type=float,
        default=DEFAULT_POWER_TOLERANCE_MW,
        help="Absolute tolerance used for the whole-grid power-balance check in MW.",
    )
    parser.add_argument(
        "--report-limit",
        type=int,
        default=DEFAULT_REPORT_LIMIT,
        help="Maximum number of mismatches printed in detail.",
    )

    args: argparse.Namespace = parser.parse_args()
    return args


def run_case(case_path: Path) -> tuple[MultiCircuit, np.ndarray, OptimalPowerFlowTimeSeriesDriver]:
    """
    Load the case and run the linear OPF time series.

    :param case_path: Path to the case file.
    :return: Grid, simulated time indices and completed driver.
    """
    grid: MultiCircuit = FileOpen(str(case_path)).open()
    time_indices: np.ndarray = np.array(grid.get_all_time_indices(), dtype=int)

    # The investigation targets the exact linear OPF mode that exposed the battery dispatch bug.
    options: OptimalPowerFlowOptions = OptimalPowerFlowOptions(
        verbose=0,
        dispatch_mode=OpfDispatchMode.Normal,
        solver=SolverType.LINEAR_OPF,
        power_flow_options=PowerFlowOptions(),
        time_grouping=TimeGrouping.NoGrouping,
        mip_solver=MIPSolvers.HIGHS,
        mip_framework=MIPFramework.PuLP,
    )

    driver: OptimalPowerFlowTimeSeriesDriver = OptimalPowerFlowTimeSeriesDriver(
        grid=grid,
        options=options,
        time_indices=time_indices,
    )
    driver.run()

    return grid, time_indices, driver


def compute_expected_energy_mwh(
    previous_energy_mwh: float,
    power_mw: float,
    charge_efficiency: float,
    discharge_efficiency: float,
    dt_hours: float,
) -> float:
    """
    Recompute one battery energy step from the solved battery power.

    :param previous_energy_mwh: Energy at the previous modeled step.
    :param power_mw: Solved battery power. Positive means discharge.
    :param charge_efficiency: Charging efficiency.
    :param discharge_efficiency: Discharging efficiency.
    :param dt_hours: Duration of the modeled step in hours.
    :return: Expected energy in MWh.
    """
    expected_energy_mwh: float = previous_energy_mwh

    # The OPF formulation uses a signed split: positive power discharges the battery and negative
    # power charges it. The recurrence is reconstructed with the same sign convention.
    if power_mw >= 0.0:
        expected_energy_mwh = previous_energy_mwh - dt_hours * power_mw / discharge_efficiency
    else:
        expected_energy_mwh = previous_energy_mwh - dt_hours * power_mw * charge_efficiency

    return expected_energy_mwh


def collect_energy_balance_violations(
    grid: MultiCircuit,
    time_indices: np.ndarray,
    driver: OptimalPowerFlowTimeSeriesDriver,
    tolerance_mwh: float,
) -> list[EnergyBalanceViolation]:
    """
    Compare solved battery energies against the recurrence implied by the solved powers.

    :param grid: Solved grid.
    :param time_indices: Simulated time indices.
    :param driver: Completed OPF TS driver.
    :param tolerance_mwh: Allowed absolute mismatch in MWh.
    :return: List of detected mismatches.
    """
    violations: list[EnergyBalanceViolation] = list()
    battery_power: np.ndarray = np.asarray(driver.results.battery_power, dtype=float)
    battery_energy: np.ndarray = np.asarray(driver.results.battery_energy, dtype=float)

    # The checker walks each battery through the horizon exactly as the formulation does so that
    # any missing state propagation or wrong dt selection appears as a direct mismatch.
    for battery_idx, battery in enumerate(grid.get_batteries()):
        battery_obj: Battery = battery
        previous_energy_mwh: float = battery_obj.soc_0 * battery_obj.Enom

        for local_t, global_t in enumerate(time_indices):
            global_t_idx: int = int(global_t)
            dt_hours: float = get_model_step_hours(
                time_array=grid.time_profile,
                local_t=local_t,
                global_t=global_t_idx,
            )
            power_mw: float = float(battery_power[local_t, battery_idx])
            actual_energy_mwh: float = float(battery_energy[local_t, battery_idx])
            expected_energy_mwh: float = compute_expected_energy_mwh(
                previous_energy_mwh=previous_energy_mwh,
                power_mw=power_mw,
                charge_efficiency=float(battery_obj.charge_efficiency),
                discharge_efficiency=float(battery_obj.discharge_efficiency),
                dt_hours=dt_hours,
            )
            abs_error_mwh: float = abs(actual_energy_mwh - expected_energy_mwh)
            dispatchable: bool = bool(battery_obj.get_enabled_dispatch_at(global_t_idx))

            # Only mismatches beyond the tolerance matter for this investigation.
            if abs_error_mwh > tolerance_mwh:
                violation: EnergyBalanceViolation = EnergyBalanceViolation(
                    battery_name=battery_obj.name,
                    local_t=local_t,
                    global_t=global_t_idx,
                    dispatchable=dispatchable,
                    dt_hours=dt_hours,
                    power_mw=power_mw,
                    previous_energy_mwh=previous_energy_mwh,
                    expected_energy_mwh=expected_energy_mwh,
                    actual_energy_mwh=actual_energy_mwh,
                    abs_error_mwh=abs_error_mwh,
                )
                violations.append(violation)

            previous_energy_mwh = actual_energy_mwh

    return violations


def print_violations(
    violations: Sequence[EnergyBalanceViolation],
    report_limit: int,
) -> None:
    """
    Print a compact mismatch report.

    :param violations: Violations to print.
    :param report_limit: Maximum number of entries to print.
    :return: ``None``.
    """
    shown_count: int = min(len(violations), report_limit)

    for idx in range(shown_count):
        violation: EnergyBalanceViolation = violations[idx]
        print(
            "ENERGY MISMATCH "
            f"battery={violation.battery_name} "
            f"local_t={violation.local_t} "
            f"global_t={violation.global_t} "
            f"dispatchable={violation.dispatchable} "
            f"dt_h={violation.dt_hours:.6f} "
            f"p_mw={violation.power_mw:.6f} "
            f"e_prev_mwh={violation.previous_energy_mwh:.6f} "
            f"e_expected_mwh={violation.expected_energy_mwh:.6f} "
            f"e_actual_mwh={violation.actual_energy_mwh:.6f} "
            f"abs_error_mwh={violation.abs_error_mwh:.6e}"
        )


def collect_grid_balance_violations(
    grid: MultiCircuit,
    time_indices: np.ndarray,
    driver: OptimalPowerFlowTimeSeriesDriver,
    power_tolerance_mw: float,
) -> list[GridBalanceViolation]:
    """
    Compare whole-grid served load against solved generation and battery injection.

    :param grid: Solved grid.
    :param time_indices: Simulated time indices.
    :param driver: Completed OPF TS driver.
    :param power_tolerance_mw: Allowed absolute power mismatch in MW.
    :return: List of detected whole-grid mismatches.
    """
    violations: list[GridBalanceViolation] = list()
    generator_power: np.ndarray = np.asarray(driver.results.generator_power, dtype=float)
    battery_power: np.ndarray = np.asarray(driver.results.battery_power, dtype=float)
    load_power: np.ndarray = np.asarray(driver.results.load_power, dtype=float)

    # The linear OPF bus balance uses generation and battery injections with positive sign and
    # served load with negative sign, so the whole-grid residual is their direct sum.
    for local_t, global_t in enumerate(time_indices):
        global_t_idx: int = int(global_t)
        dt_hours: float = get_model_step_hours(
            time_array=grid.time_profile,
            local_t=local_t,
            global_t=global_t_idx,
        )
        generation_mw: float = float(np.sum(generator_power[local_t, :]))
        battery_mw: float = float(np.sum(battery_power[local_t, :]))
        served_load_mw: float = float(np.sum(load_power[local_t, :]))
        power_residual_mw: float = generation_mw + battery_mw - served_load_mw
        energy_residual_mwh: float = power_residual_mw * dt_hours

        if abs(power_residual_mw) > power_tolerance_mw:
            violation: GridBalanceViolation = GridBalanceViolation(
                local_t=local_t,
                global_t=global_t_idx,
                dt_hours=dt_hours,
                generation_mw=generation_mw,
                battery_mw=battery_mw,
                served_load_mw=served_load_mw,
                power_residual_mw=power_residual_mw,
                energy_residual_mwh=energy_residual_mwh,
            )
            violations.append(violation)

    return violations


def print_grid_balance_violations(
    violations: Sequence[GridBalanceViolation],
    report_limit: int,
) -> None:
    """
    Print a compact whole-grid mismatch report.

    :param violations: Violations to print.
    :param report_limit: Maximum number of entries to print.
    :return: ``None``.
    """
    shown_count: int = min(len(violations), report_limit)

    for idx in range(shown_count):
        violation: GridBalanceViolation = violations[idx]
        print(
            "GRID BALANCE MISMATCH "
            f"local_t={violation.local_t} "
            f"global_t={violation.global_t} "
            f"dt_h={violation.dt_hours:.6f} "
            f"gen_mw={violation.generation_mw:.6f} "
            f"batt_mw={violation.battery_mw:.6f} "
            f"load_mw={violation.served_load_mw:.6f} "
            f"power_residual_mw={violation.power_residual_mw:.6e} "
            f"energy_residual_mwh={violation.energy_residual_mwh:.6e}"
        )


def main() -> None:
    """
    Run the investigation script.

    :return: ``None``.
    """
    args: argparse.Namespace = parse_args()
    case_path: Path = args.case.resolve()

    # Running the exact investigation case first keeps the checker tied to the reported failure.
    grid, time_indices, driver = run_case(case_path=case_path)
    energy_violations: list[EnergyBalanceViolation] = collect_energy_balance_violations(
        grid=grid,
        time_indices=time_indices,
        driver=driver,
        tolerance_mwh=float(args.tolerance_mwh),
    )
    grid_balance_violations: list[GridBalanceViolation] = collect_grid_balance_violations(
        grid=grid,
        time_indices=time_indices,
        driver=driver,
        power_tolerance_mw=float(args.power_tolerance_mw),
    )

    converged_all: bool = bool(np.all(np.asarray(driver.results.converged, dtype=bool)))
    battery_count: int = len(grid.get_batteries())
    step_count: int = len(time_indices)

    print(f"case={case_path}")
    print(f"converged_all={converged_all}")
    print(f"battery_count={battery_count}")
    print(f"time_step_count={step_count}")
    print(f"tolerance_mwh={float(args.tolerance_mwh):.6e}")
    print(f"power_tolerance_mw={float(args.power_tolerance_mw):.6e}")
    print(f"battery_energy_balance_violations={len(energy_violations)}")
    print(f"whole_grid_balance_violations={len(grid_balance_violations)}")

    if energy_violations:
        print_violations(violations=energy_violations, report_limit=int(args.report_limit))
    else:
        print("Battery energy balance matches the solved OPF results within tolerance.")

    if grid_balance_violations:
        print_grid_balance_violations(
            violations=grid_balance_violations,
            report_limit=int(args.report_limit),
        )
    else:
        print("Whole-grid served-load balance matches solved generation plus battery injection.")

    if energy_violations or grid_balance_violations:
        raise AssertionError("Energy-balance mismatches detected.")


if __name__ == "__main__":
    main()
