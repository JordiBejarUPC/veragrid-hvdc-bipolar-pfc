"""
IEEE14 full-coefficient MDHEM example with parity metrics.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from mdhelm import MDHEMPVQueryArtifact
from mdhelm import VeraGridQueryCaseData
from mdhelm import build_artifact_from_case
from mdhelm import create_mdhelm_inputs
from mdhelm import import_veragrid_engine_modules
from mdhelm import load_multicircuit_from_file
from mdhelm import load_query_artifact
from mdhelm import save_query_artifact


@dataclass
class DeviceBusMapping:
    pq_load_indices: list[list[int]]
    pv_generator_indices: list[list[int]]
    pq_base_net_active: np.ndarray
    pq_base_net_reactive: np.ndarray
    pv_base_net_active: np.ndarray
    pq_base_load_active_total_mw: np.ndarray
    pq_base_load_reactive_total_mvar: np.ndarray
    pv_base_generator_active_total_mw: np.ndarray
    pq_bus_mutable: np.ndarray
    pv_bus_mutable: np.ndarray


@dataclass
class Scenario:
    name: str
    pq_active_power: np.ndarray
    pq_reactive_power: np.ndarray
    pv_active_power: np.ndarray


def build_bus_position_lookup(bus_indices: np.ndarray, nbus: int) -> np.ndarray:
    lookup: np.ndarray = -np.ones(nbus, dtype=np.int64)
    position: int
    for position in range(bus_indices.size):
        lookup[int(bus_indices[position])] = position
    return lookup


def build_device_bus_mapping(grid: object, case_data: VeraGridQueryCaseData) -> DeviceBusMapping:
    bus_index_dict: dict[object, int] = grid.get_bus_index_dict()
    pq_lookup: np.ndarray = build_bus_position_lookup(case_data.pq, case_data.ybus.shape[0])
    pv_lookup: np.ndarray = build_bus_position_lookup(case_data.pv, case_data.ybus.shape[0])
    pq_load_indices: list[list[int]] = [list() for _ in range(case_data.pq.size)]
    pv_generator_indices: list[list[int]] = [list() for _ in range(case_data.pv.size)]
    pq_base_load_active_total_mw: np.ndarray = np.zeros(case_data.pq.size, dtype=np.float64)
    pq_base_load_reactive_total_mvar: np.ndarray = np.zeros(case_data.pq.size, dtype=np.float64)
    pv_base_generator_active_total_mw: np.ndarray = np.zeros(case_data.pv.size, dtype=np.float64)
    load_index: int
    for load_index, load in enumerate(grid.get_loads()):
        bus_index: int = int(bus_index_dict[load.bus])
        pq_position: int = int(pq_lookup[bus_index])
        if pq_position >= 0:
            pq_load_indices[pq_position].append(load_index)
            pq_base_load_active_total_mw[pq_position] = pq_base_load_active_total_mw[pq_position] + float(load.P)
            pq_base_load_reactive_total_mvar[pq_position] = pq_base_load_reactive_total_mvar[pq_position] + float(load.Q)
    generator_index: int
    for generator_index, generator in enumerate(grid.get_generators()):
        bus_index = int(bus_index_dict[generator.bus])
        pv_position: int = int(pv_lookup[bus_index])
        if pv_position >= 0:
            pv_generator_indices[pv_position].append(generator_index)
            pv_base_generator_active_total_mw[pv_position] = pv_base_generator_active_total_mw[pv_position] + float(generator.P)
    pq_bus_mutable: np.ndarray = np.asarray([len(indices) > 0 for indices in pq_load_indices], dtype=bool)
    pv_bus_mutable: np.ndarray = np.asarray([len(indices) > 0 for indices in pv_generator_indices], dtype=bool)
    return DeviceBusMapping(
        pq_load_indices=pq_load_indices,
        pv_generator_indices=pv_generator_indices,
        pq_base_net_active=case_data.base_power[case_data.pq].real.copy(),
        pq_base_net_reactive=case_data.base_power[case_data.pq].imag.copy(),
        pv_base_net_active=case_data.base_power[case_data.pv].real.copy(),
        pq_base_load_active_total_mw=pq_base_load_active_total_mw,
        pq_base_load_reactive_total_mvar=pq_base_load_reactive_total_mvar,
        pv_base_generator_active_total_mw=pv_base_generator_active_total_mw,
        pq_bus_mutable=pq_bus_mutable,
        pv_bus_mutable=pv_bus_mutable,
    )


def calculate_distribution_weights(reference_values: np.ndarray) -> np.ndarray:
    absolute_reference: np.ndarray = np.abs(reference_values)
    reference_sum: float = float(np.sum(absolute_reference))
    if reference_values.size == 0:
        raise ValueError("reference_values must not be empty")
    if reference_sum > 0.0:
        return absolute_reference / reference_sum
    return np.full(reference_values.size, 1.0 / float(reference_values.size), dtype=np.float64)


def distribute_total(reference_values: np.ndarray, target_total: float) -> np.ndarray:
    return target_total * calculate_distribution_weights(reference_values=reference_values)


def create_base_scenario(case_data: VeraGridQueryCaseData) -> Scenario:
    return Scenario(
        name="base",
        pq_active_power=case_data.base_power[case_data.pq].real.copy(),
        pq_reactive_power=case_data.base_power[case_data.pq].imag.copy(),
        pv_active_power=case_data.base_power[case_data.pv].real.copy(),
    )


def create_random_scenario(
    case_data: VeraGridQueryCaseData,
    mapping: DeviceBusMapping,
    scenario_index: int,
    shrink_factor: float,
    rng: np.random.Generator,
) -> Scenario:
    base_pq_active: np.ndarray = case_data.base_power[case_data.pq].real.copy()
    base_pq_reactive: np.ndarray = case_data.base_power[case_data.pq].imag.copy()
    base_pv_active: np.ndarray = case_data.base_power[case_data.pv].real.copy()
    pq_active_scale: np.ndarray = np.maximum(mapping.pq_base_load_active_total_mw / case_data.sbase, 0.03)
    pq_reactive_scale: np.ndarray = np.maximum(np.abs(mapping.pq_base_load_reactive_total_mvar) / case_data.sbase, 0.02)
    pv_active_scale: np.ndarray = np.maximum(mapping.pv_base_generator_active_total_mw / case_data.sbase, 0.03)
    pv_positive_mask: np.ndarray = np.logical_and(mapping.pv_bus_mutable, mapping.pv_base_generator_active_total_mw > 1.0e-9)
    pq_active_scale = pq_active_scale * mapping.pq_bus_mutable.astype(np.float64)
    pq_reactive_scale = pq_reactive_scale * mapping.pq_bus_mutable.astype(np.float64)
    pv_active_scale = pv_active_scale * pv_positive_mask.astype(np.float64)
    pq_active_delta: np.ndarray = shrink_factor * rng.normal(0.0, 0.08, size=case_data.pq.size) * pq_active_scale
    pq_reactive_delta: np.ndarray = shrink_factor * rng.normal(0.0, 0.08, size=case_data.pq.size) * pq_reactive_scale
    pv_active_delta: np.ndarray = shrink_factor * rng.normal(0.0, 0.06, size=case_data.pv.size) * pv_active_scale
    active_delta_sum: float = float(np.sum(pq_active_delta) + np.sum(pv_active_delta))
    pv_balance_weights: np.ndarray = calculate_distribution_weights(
        (mapping.pv_base_generator_active_total_mw / case_data.sbase) * pv_positive_mask.astype(np.float64)
    )
    pv_active_delta = pv_active_delta - active_delta_sum * pv_balance_weights
    reactive_delta_sum: float = float(np.sum(pq_reactive_delta))
    pq_balance_weights: np.ndarray = calculate_distribution_weights(
        (np.abs(base_pq_reactive) + 1.0e-6) * mapping.pq_bus_mutable.astype(np.float64)
    )
    pq_reactive_delta = pq_reactive_delta - reactive_delta_sum * pq_balance_weights
    return Scenario(
        name=f"random_{scenario_index:02d}",
        pq_active_power=base_pq_active + pq_active_delta,
        pq_reactive_power=base_pq_reactive + pq_reactive_delta,
        pv_active_power=base_pv_active + pv_active_delta,
    )


def scenario_is_physical(mapping: DeviceBusMapping, case_data: VeraGridQueryCaseData, scenario: Scenario) -> bool:
    pq_index: int
    for pq_index in range(case_data.pq.size):
        target_load_active_total_mw: float = mapping.pq_base_load_active_total_mw[pq_index] - (
            (float(scenario.pq_active_power[pq_index]) - float(mapping.pq_base_net_active[pq_index])) * case_data.sbase
        )
        if target_load_active_total_mw < 0.0:
            return False
    pv_index: int
    for pv_index in range(case_data.pv.size):
        target_generator_active_total_mw: float = mapping.pv_base_generator_active_total_mw[pv_index] + (
            (float(scenario.pv_active_power[pv_index]) - float(mapping.pv_base_net_active[pv_index])) * case_data.sbase
        )
        if target_generator_active_total_mw < 0.0:
            return False
    return True


def create_scenarios(
    case_data: VeraGridQueryCaseData,
    mapping: DeviceBusMapping,
    scenario_count: int,
    seed: int,
) -> list[Scenario]:
    scenarios: list[Scenario] = [create_base_scenario(case_data=case_data)]
    rng: np.random.Generator = np.random.default_rng(seed)
    scenario_index: int = 1
    while scenario_index < scenario_count:
        shrink_factor: float = 1.0
        trial_index: int = 0
        while trial_index < 8:
            scenario: Scenario = create_random_scenario(
                case_data=case_data,
                mapping=mapping,
                scenario_index=scenario_index,
                shrink_factor=shrink_factor,
                rng=rng,
            )
            if scenario_is_physical(mapping=mapping, case_data=case_data, scenario=scenario):
                scenarios.append(scenario)
                scenario_index = scenario_index + 1
                break
            shrink_factor = 0.5 * shrink_factor
            trial_index = trial_index + 1
        else:
            raise RuntimeError(f"Could not create physical scenario {scenario_index}")
    return scenarios


def apply_pq_targets(loads: list[object], mapping: DeviceBusMapping, case_data: VeraGridQueryCaseData, scenario: Scenario) -> None:
    pq_index: int
    for pq_index in range(case_data.pq.size):
        device_indices: list[int] = mapping.pq_load_indices[pq_index]
        if len(device_indices) == 0:
            continue
        target_load_active_total_mw: float = mapping.pq_base_load_active_total_mw[pq_index] - (
            (float(scenario.pq_active_power[pq_index]) - float(mapping.pq_base_net_active[pq_index])) * case_data.sbase
        )
        target_load_reactive_total_mvar: float = mapping.pq_base_load_reactive_total_mvar[pq_index] - (
            (float(scenario.pq_reactive_power[pq_index]) - float(mapping.pq_base_net_reactive[pq_index])) * case_data.sbase
        )
        active_reference: np.ndarray = np.asarray([float(loads[index].P) for index in device_indices], dtype=np.float64)
        reactive_reference: np.ndarray = np.asarray([float(loads[index].Q) for index in device_indices], dtype=np.float64)
        active_values: np.ndarray = distribute_total(active_reference, target_load_active_total_mw)
        reactive_values: np.ndarray = distribute_total(reactive_reference, target_load_reactive_total_mvar)
        local_index: int
        for local_index, device_index in enumerate(device_indices):
            loads[device_index].P = float(active_values[local_index])
            loads[device_index].Q = float(reactive_values[local_index])


def apply_pv_targets(generators: list[object], mapping: DeviceBusMapping, case_data: VeraGridQueryCaseData, scenario: Scenario) -> None:
    pv_index: int
    for pv_index in range(case_data.pv.size):
        device_indices: list[int] = mapping.pv_generator_indices[pv_index]
        if len(device_indices) == 0:
            continue
        target_generator_active_total_mw: float = mapping.pv_base_generator_active_total_mw[pv_index] + (
            (float(scenario.pv_active_power[pv_index]) - float(mapping.pv_base_net_active[pv_index])) * case_data.sbase
        )
        active_reference: np.ndarray = np.asarray([float(generators[index].P) for index in device_indices], dtype=np.float64)
        active_values: np.ndarray = distribute_total(active_reference, target_generator_active_total_mw)
        local_index: int
        for local_index, device_index in enumerate(device_indices):
            generators[device_index].P = float(active_values[local_index])


def create_nr_options(vg: object) -> object:
    try:
        return vg.PowerFlowOptions(
            solver_type=vg.SolverType.NR,
            retry_with_other_methods=False,
            control_q=True,
            control_taps_phase=False,
            control_taps_modules=False,
            apply_temperature_correction=False,
            use_stored_guess=False,
            tolerance=1e-10,
            max_iter=25,
        )
    except TypeError:
        return vg.PowerFlowOptions(vg.SolverType.NR, verbose=False)


def create_nr_seed(grid: object) -> object:
    vg, _ = import_veragrid_engine_modules()
    return vg.power_flow(grid=grid, options=create_nr_options(vg=vg))


def run_nr_reference(base_grid: object, case_data: VeraGridQueryCaseData, mapping: DeviceBusMapping, scenario: Scenario) -> tuple[object, VeraGridQueryCaseData]:
    vg, _ = import_veragrid_engine_modules()
    grid_copy: object = base_grid.copy()
    apply_pq_targets(loads=grid_copy.get_loads(), mapping=mapping, case_data=case_data, scenario=scenario)
    apply_pv_targets(generators=grid_copy.get_generators(), mapping=mapping, case_data=case_data, scenario=scenario)
    modified_case_data: VeraGridQueryCaseData = create_mdhelm_inputs(grid=grid_copy)
    nr_results: object = vg.power_flow(grid=grid_copy, options=create_nr_options(vg=vg))
    return nr_results, modified_case_data


def calculate_write_error(modified_case_data: VeraGridQueryCaseData, scenario: Scenario) -> float:
    pq_active_error: np.ndarray = np.abs(modified_case_data.base_power[modified_case_data.pq].real - scenario.pq_active_power)
    pq_reactive_error: np.ndarray = np.abs(modified_case_data.base_power[modified_case_data.pq].imag - scenario.pq_reactive_power)
    pv_active_error: np.ndarray = np.abs(modified_case_data.base_power[modified_case_data.pv].real - scenario.pv_active_power)
    return float(np.max(np.concatenate((pq_active_error, pq_reactive_error, pv_active_error))))


def run_example() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-order", type=int, default=4)
    parser.add_argument("--scenario-count", type=int, default=20)
    parser.add_argument("--scenario-seed", type=int, default=2001)
    parser.add_argument("--rebuild-artifact", action="store_true")
    args: argparse.Namespace = parser.parse_args()

    case_path: Path = Path(__file__).resolve().with_name("case14.matpower")
    artifact_path: Path = Path(__file__).resolve().with_name("case14_full_coefficients_artifact.npz")
    base_grid: object = load_multicircuit_from_file(matpower_path=case_path)
    case_data: VeraGridQueryCaseData
    artifact: MDHEMPVQueryArtifact
    germ_error: float
    if artifact_path.exists() and not bool(args.rebuild_artifact):
        case_data = create_mdhelm_inputs(grid=base_grid)
        artifact = load_query_artifact(path=artifact_path)
        germ_error = 0.0
    else:
        case_data, artifact, germ_error = build_artifact_from_case(
            grid=base_grid,
            max_order=int(args.max_order),
        )
        save_query_artifact(path=artifact_path, artifact=artifact)

    mapping: DeviceBusMapping = build_device_bus_mapping(grid=base_grid, case_data=case_data)
    scenarios: list[Scenario] = create_scenarios(
        case_data=case_data,
        mapping=mapping,
        scenario_count=int(args.scenario_count),
        seed=int(args.scenario_seed),
    )
    voltage_errors: list[float] = []
    flow_errors: list[float] = []
    loading_errors: list[float] = []
    mismatch_errors: list[float] = []
    write_errors: list[float] = []
    passed_count: int = 0

    for scenario in scenarios:
        artifact_result = artifact.query(
            pq_active_power=scenario.pq_active_power,
            pq_reactive_power=scenario.pq_reactive_power,
            pv_active_power=scenario.pv_active_power,
            tolerance=1.0e-6,
        )
        nr_results, modified_case_data = run_nr_reference(
            base_grid=base_grid,
            case_data=case_data,
            mapping=mapping,
            scenario=scenario,
        )
        write_error: float = calculate_write_error(modified_case_data=modified_case_data, scenario=scenario)
        voltage_error: float = float(np.max(np.abs(artifact_result.voltage - nr_results.voltage)))
        flow_error: float = float(np.max(np.abs(artifact_result.branch_from_power - nr_results.Sf)))
        loading_error: float = float(np.max(np.abs(artifact_result.branch_loading - nr_results.loading)))
        passed: bool = bool(
            write_error <= 2.0e-6
            and float(artifact_result.mismatch_norm) <= 1.0e-6
            and voltage_error <= 1.0e-3
            and flow_error <= 1.0
            and loading_error <= 2.0e-3
        )
        passed_count = passed_count + int(passed)
        write_errors.append(write_error)
        mismatch_errors.append(float(artifact_result.mismatch_norm))
        voltage_errors.append(voltage_error)
        flow_errors.append(flow_error)
        loading_errors.append(loading_error)
        print(
            f"{scenario.name:>10}  pass={passed!s:<5}  "
            f"mismatch={artifact_result.mismatch_norm:.3e}  "
            f"dV={voltage_error:.3e}  dSf={flow_error:.3e} MVA  dL={loading_error:.3e}"
        )

    print("\nIEEE14 full coefficients")
    print(f"artifact={artifact_path.name}")
    print(f"max_order={artifact.get_max_order()} dims={artifact.get_dimensions_count()} germ_error={germ_error:.3e}")
    print(f"passed={passed_count}/{len(scenarios)}")
    print(f"worst_write_error={max(write_errors):.3e}")
    print(f"worst_mismatch={max(mismatch_errors):.3e}")
    print(f"worst_voltage_diff={max(voltage_errors):.3e}")
    print(f"worst_flow_diff_mva={max(flow_errors):.3e}")
    print(f"worst_loading_diff={max(loading_errors):.3e}")


if __name__ == "__main__":
    run_example()
