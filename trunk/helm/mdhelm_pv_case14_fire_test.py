"""
Run a fire test for the case14 MDHEM-PV query artifact.

This script performs the following stages:

1. load the local MATPOWER case14 file into a VeraGrid ``MultiCircuit``,
2. build and save the MDHEM-PV artifact once,
3. generate several near-balanced power-injection scenarios,
4. evaluate each scenario with the saved artifact,
5. evaluate the same scenario with VeraGrid Newton-Raphson power flow,
6. compare the voltages and branch flows.

The test scenarios use the artifact query variables directly:

* PQ buses: active and reactive power,
* PV buses: active power.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from mdhelm_pv_case14_query_artifact import MDHEMQueryResult
from mdhelm_pv_case14_query_artifact import MDHEMPVQueryArtifact
from mdhelm_pv_case14_query_artifact import VeraGridQueryCaseData
from mdhelm_pv_case14_query_artifact import build_artifact_from_case
from mdhelm_pv_case14_query_artifact import import_veragrid_engine_modules
from mdhelm_pv_case14_query_artifact import load_multicircuit_from_file
from mdhelm_pv_case14_query_artifact import load_query_artifact
from mdhelm_pv_case14_query_artifact import load_veragrid_case_data
from mdhelm_pv_case14_query_artifact import save_query_artifact

if TYPE_CHECKING:
    from VeraGridEngine.Devices.Injections.generator import Generator
    from VeraGridEngine.Devices.Injections.load import Load
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


class DeviceBusMapping:
    """
    Store the device-to-bus information needed to replay scenarios on a grid.

    :param pq_load_indices: Load indices for each PQ bus.
    :param pv_generator_indices: Generator indices for each PV bus.
    :param pq_base_net_active: Base active net injections at PQ buses in per unit.
    :param pq_base_net_reactive: Base reactive net injections at PQ buses in per unit.
    :param pv_base_net_active: Base active net injections at PV buses in per unit.
    :param pq_base_load_active_total_mw: Base total load active power at each PQ bus in MW.
    :param pq_base_load_reactive_total_mvar: Base total load reactive power at each PQ bus in MVAr.
    :param pv_base_generator_active_total_mw: Base total generator active power at each PV bus in MW.
    :param pq_bus_mutable: Flags indicating whether each PQ bus can be replayed through load devices.
    :param pv_bus_mutable: Flags indicating whether each PV bus can be replayed through generator devices.
    """

    __slots__ = (
        "pq_load_indices",
        "pv_generator_indices",
        "pq_base_net_active",
        "pq_base_net_reactive",
        "pv_base_net_active",
        "pq_base_load_active_total_mw",
        "pq_base_load_reactive_total_mvar",
        "pv_base_generator_active_total_mw",
        "pq_bus_mutable",
        "pv_bus_mutable",
    )

    def __init__(
        self,
        pq_load_indices: list[list[int]],
        pv_generator_indices: list[list[int]],
        pq_base_net_active: np.ndarray,
        pq_base_net_reactive: np.ndarray,
        pv_base_net_active: np.ndarray,
        pq_base_load_active_total_mw: np.ndarray,
        pq_base_load_reactive_total_mvar: np.ndarray,
        pv_base_generator_active_total_mw: np.ndarray,
        pq_bus_mutable: np.ndarray,
        pv_bus_mutable: np.ndarray,
    ) -> None:
        self.pq_load_indices: list[list[int]] = pq_load_indices
        self.pv_generator_indices: list[list[int]] = pv_generator_indices
        self.pq_base_net_active: np.ndarray = pq_base_net_active
        self.pq_base_net_reactive: np.ndarray = pq_base_net_reactive
        self.pv_base_net_active: np.ndarray = pv_base_net_active
        self.pq_base_load_active_total_mw: np.ndarray = pq_base_load_active_total_mw
        self.pq_base_load_reactive_total_mvar: np.ndarray = pq_base_load_reactive_total_mvar
        self.pv_base_generator_active_total_mw: np.ndarray = pv_base_generator_active_total_mw
        self.pq_bus_mutable: np.ndarray = pq_bus_mutable
        self.pv_bus_mutable: np.ndarray = pv_bus_mutable


class FireTestScenario:
    """
    Store one fire-test scenario in artifact query coordinates.

    :param name: Scenario name.
    :param pq_active_power: PQ active powers in per unit.
    :param pq_reactive_power: PQ reactive powers in per unit.
    :param pv_active_power: PV active powers in per unit.
    :param active_delta_sum: Sum of active-power perturbations relative to the base case.
    :param reactive_delta_sum: Sum of PQ reactive-power perturbations relative to the base case.
    """

    __slots__ = (
        "name",
        "pq_active_power",
        "pq_reactive_power",
        "pv_active_power",
        "active_delta_sum",
        "reactive_delta_sum",
    )

    def __init__(
        self,
        name: str,
        pq_active_power: np.ndarray,
        pq_reactive_power: np.ndarray,
        pv_active_power: np.ndarray,
        active_delta_sum: float,
        reactive_delta_sum: float,
    ) -> None:
        self.name: str = name
        self.pq_active_power: np.ndarray = pq_active_power
        self.pq_reactive_power: np.ndarray = pq_reactive_power
        self.pv_active_power: np.ndarray = pv_active_power
        self.active_delta_sum: float = active_delta_sum
        self.reactive_delta_sum: float = reactive_delta_sum


class FireTestMetrics:
    """
    Store the comparison metrics for one scenario.

    :param scenario_name: Scenario name.
    :param nr_converged: Newton-Raphson convergence flag.
    :param artifact_converged: Artifact convergence-like flag.
    :param injection_write_error: Maximum bus-injection write error in per unit.
    :param nr_error: Newton-Raphson reported power-flow error.
    :param artifact_error: Artifact mismatch norm.
    :param max_voltage_diff: Maximum complex-voltage difference in per unit.
    :param max_flow_diff_mva: Maximum branch-from flow difference in MVA.
    :param max_loading_diff: Maximum branch-loading difference.
    :param passed: Scenario pass flag against the configured thresholds.
    """

    __slots__ = (
        "scenario_name",
        "nr_converged",
        "artifact_converged",
        "injection_write_error",
        "nr_error",
        "artifact_error",
        "max_voltage_diff",
        "max_flow_diff_mva",
        "max_loading_diff",
        "passed",
    )

    def __init__(
        self,
        scenario_name: str,
        nr_converged: bool,
        artifact_converged: bool,
        injection_write_error: float,
        nr_error: float,
        artifact_error: float,
        max_voltage_diff: float,
        max_flow_diff_mva: float,
        max_loading_diff: float,
        passed: bool,
    ) -> None:
        self.scenario_name: str = scenario_name
        self.nr_converged: bool = nr_converged
        self.artifact_converged: bool = artifact_converged
        self.injection_write_error: float = injection_write_error
        self.nr_error: float = nr_error
        self.artifact_error: float = artifact_error
        self.max_voltage_diff: float = max_voltage_diff
        self.max_flow_diff_mva: float = max_flow_diff_mva
        self.max_loading_diff: float = max_loading_diff
        self.passed: bool = passed


def build_bus_position_lookup(bus_indices: np.ndarray, nbus: int) -> np.ndarray:
    """
    Build a full-bus to local-position lookup.

    :param bus_indices: Bus indices to map.
    :param nbus: Total number of buses.
    :return: Integer lookup vector with ``-1`` for buses outside ``bus_indices``.
    """
    lookup: np.ndarray = -np.ones(nbus, dtype=np.int64)
    position: int
    for position in range(bus_indices.size):
        lookup[int(bus_indices[position])] = position
    return lookup


def build_device_bus_mapping(grid: "MultiCircuit", case_data: VeraGridQueryCaseData) -> DeviceBusMapping:
    """
    Build the device-to-bus mapping required to replay bus-power scenarios.

    :param grid: Base VeraGrid circuit.
    :param case_data: Base compiled case data.
    :return: DeviceBusMapping for the copied-grid scenario replay.
    """
    bus_index_dict: dict[object, int] = grid.get_bus_index_dict()
    pq_lookup: np.ndarray = build_bus_position_lookup(
        bus_indices=case_data.pq,
        nbus=case_data.ybus.shape[0],
    )
    pv_lookup: np.ndarray = build_bus_position_lookup(
        bus_indices=case_data.pv,
        nbus=case_data.ybus.shape[0],
    )
    pq_load_indices: list[list[int]] = list()
    pv_generator_indices: list[list[int]] = list()
    pq_index: int

    # Each PQ bus receives one list of load-device indices.
    for pq_index in range(case_data.pq.size):
        pq_load_indices.append(list())

    pv_index: int

    # Each PV bus receives one list of generator-device indices.
    for pv_index in range(case_data.pv.size):
        pv_generator_indices.append(list())

    pq_base_load_active_total_mw: np.ndarray = np.zeros(case_data.pq.size, dtype=np.float64)
    pq_base_load_reactive_total_mvar: np.ndarray = np.zeros(case_data.pq.size, dtype=np.float64)
    pv_base_generator_active_total_mw: np.ndarray = np.zeros(case_data.pv.size, dtype=np.float64)
    pq_bus_mutable: np.ndarray = np.zeros(case_data.pq.size, dtype=bool)
    pv_bus_mutable: np.ndarray = np.zeros(case_data.pv.size, dtype=bool)

    # The mapping stage groups the physical devices by their owning bus.
    load_index: int
    for load_index, load in enumerate(grid.get_loads()):
        bus_index: int = int(bus_index_dict[load.bus])
        pq_position: int = int(pq_lookup[bus_index])

        if pq_position >= 0:
            pq_load_indices[pq_position].append(load_index)
            pq_base_load_active_total_mw[pq_position] = pq_base_load_active_total_mw[pq_position] + float(load.P)
            pq_base_load_reactive_total_mvar[pq_position] = pq_base_load_reactive_total_mvar[pq_position] + float(load.Q)
        else:
            pass

    generator_index: int
    for generator_index, generator in enumerate(grid.get_generators()):
        bus_index = int(bus_index_dict[generator.bus])
        pv_position: int = int(pv_lookup[bus_index])

        if pv_position >= 0:
            pv_generator_indices[pv_position].append(generator_index)
            pv_base_generator_active_total_mw[pv_position] = pv_base_generator_active_total_mw[pv_position] + float(generator.P)
        else:
            pass

    # The fire test only targets buses that already have the corresponding devices.
    for pq_index in range(case_data.pq.size):
        if len(pq_load_indices[pq_index]) > 0:
            pq_bus_mutable[pq_index] = True
        else:
            pq_bus_mutable[pq_index] = False

    for pv_index in range(case_data.pv.size):
        if len(pv_generator_indices[pv_index]) > 0:
            pv_bus_mutable[pv_index] = True
        else:
            pv_bus_mutable[pv_index] = False

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
    """
    Calculate non-negative proportional weights for device redistribution.

    :param reference_values: Reference device values.
    :return: Weight vector whose sum is one.
    """
    absolute_reference: np.ndarray = np.abs(reference_values)
    reference_sum: float = float(np.sum(absolute_reference))
    weights: np.ndarray = np.zeros(reference_values.size, dtype=np.float64)

    if reference_values.size > 0:
        if reference_sum > 0.0:
            weights = absolute_reference / reference_sum
        else:
            weights[:] = 1.0 / float(reference_values.size)
    else:
        raise ValueError("reference_values must not be empty")

    return weights


def distribute_total(reference_values: np.ndarray, target_total: float) -> np.ndarray:
    """
    Distribute one scalar total across several devices proportionally.

    :param reference_values: Reference device values used for the proportions.
    :param target_total: Requested total after redistribution.
    :return: Device values whose sum equals ``target_total``.
    """
    weights: np.ndarray = calculate_distribution_weights(reference_values=reference_values)
    distributed_values: np.ndarray = target_total * weights
    return distributed_values


def apply_pq_bus_targets_to_grid(
    loads: list["Load"],
    mapping: DeviceBusMapping,
    case_data: VeraGridQueryCaseData,
    scenario: FireTestScenario,
) -> None:
    """
    Apply the PQ-bus target powers to the copied load devices.

    :param loads: Copied load list.
    :param mapping: Device-to-bus mapping.
    :param case_data: Base case data.
    :param scenario: Scenario to apply.
    :return: None.
    """
    pq_index: int
    for pq_index in range(case_data.pq.size):
        base_net_active_pu: float = float(mapping.pq_base_net_active[pq_index])
        base_net_reactive_pu: float = float(mapping.pq_base_net_reactive[pq_index])
        target_net_active_pu: float = float(scenario.pq_active_power[pq_index])
        target_net_reactive_pu: float = float(scenario.pq_reactive_power[pq_index])
        device_indices: list[int] = mapping.pq_load_indices[pq_index]

        # Some compiled PQ buses are immutable because the MATPOWER import leaves
        # them without load devices. Those buses must remain at their base values.
        if len(device_indices) > 0:
            # The copied loads absorb the entire change in the PQ-bus specified net
            # power, while any non-load devices at that bus remain unchanged.
            target_load_active_total_mw: float = mapping.pq_base_load_active_total_mw[pq_index] - (
                (target_net_active_pu - base_net_active_pu) * case_data.sbase
            )
            target_load_reactive_total_mvar: float = mapping.pq_base_load_reactive_total_mvar[pq_index] - (
                (target_net_reactive_pu - base_net_reactive_pu) * case_data.sbase
            )

            if target_load_active_total_mw >= 0.0:
                active_reference: np.ndarray = np.zeros(len(device_indices), dtype=np.float64)
                reactive_reference: np.ndarray = np.zeros(len(device_indices), dtype=np.float64)
                local_index: int
                for local_index in range(len(device_indices)):
                    device_index: int = int(device_indices[local_index])
                    active_reference[local_index] = float(loads[device_index].P)
                    reactive_reference[local_index] = float(loads[device_index].Q)

                active_values: np.ndarray = distribute_total(
                    reference_values=active_reference,
                    target_total=target_load_active_total_mw,
                )
                reactive_values: np.ndarray = distribute_total(
                    reference_values=reactive_reference,
                    target_total=target_load_reactive_total_mvar,
                )

                for local_index in range(len(device_indices)):
                    device_index = int(device_indices[local_index])
                    loads[device_index].P = float(active_values[local_index])
                    loads[device_index].Q = float(reactive_values[local_index])
            else:
                raise RuntimeError(f"Scenario {scenario.name} makes PQ bus active load negative")
        else:
            if np.isclose(target_net_active_pu, base_net_active_pu) and np.isclose(
                target_net_reactive_pu,
                base_net_reactive_pu,
            ):
                pass
            else:
                raise RuntimeError(f"Scenario {scenario.name} perturbs immutable PQ bus {int(case_data.pq[pq_index]) + 1}")


def apply_pv_bus_targets_to_grid(
    generators: list["Generator"],
    mapping: DeviceBusMapping,
    case_data: VeraGridQueryCaseData,
    scenario: FireTestScenario,
) -> None:
    """
    Apply the PV-bus target active powers to the copied generators.

    :param generators: Copied generator list.
    :param mapping: Device-to-bus mapping.
    :param case_data: Base case data.
    :param scenario: Scenario to apply.
    :return: None.
    """
    pv_index: int
    for pv_index in range(case_data.pv.size):
        base_net_active_pu: float = float(mapping.pv_base_net_active[pv_index])
        target_net_active_pu: float = float(scenario.pv_active_power[pv_index])
        device_indices: list[int] = mapping.pv_generator_indices[pv_index]

        # A PV bus without generator devices cannot be replayed and therefore
        # must remain fixed at its base active injection.
        if len(device_indices) > 0:
            # The copied generators absorb the PV active-power change, while the
            # voltage setpoints remain unchanged and reactive power is solved by NR.
            target_generator_active_total_mw: float = mapping.pv_base_generator_active_total_mw[pv_index] + (
                (target_net_active_pu - base_net_active_pu) * case_data.sbase
            )

            if target_generator_active_total_mw >= 0.0:
                active_reference: np.ndarray = np.zeros(len(device_indices), dtype=np.float64)
                local_index: int
                for local_index in range(len(device_indices)):
                    device_index: int = int(device_indices[local_index])
                    active_reference[local_index] = float(generators[device_index].P)

                active_values: np.ndarray = distribute_total(
                    reference_values=active_reference,
                    target_total=target_generator_active_total_mw,
                )

                for local_index in range(len(device_indices)):
                    device_index = int(device_indices[local_index])
                    generators[device_index].P = float(active_values[local_index])
            else:
                raise RuntimeError(f"Scenario {scenario.name} makes PV bus generation negative")
        else:
            if np.isclose(target_net_active_pu, base_net_active_pu):
                pass
            else:
                raise RuntimeError(f"Scenario {scenario.name} perturbs immutable PV bus {int(case_data.pv[pv_index]) + 1}")


def scenario_is_physical(
    mapping: DeviceBusMapping,
    case_data: VeraGridQueryCaseData,
    scenario: FireTestScenario,
) -> bool:
    """
    Check whether one scenario keeps load and generator totals non-negative.

    :param mapping: Device-to-bus mapping.
    :param case_data: Base case data.
    :param scenario: Scenario candidate.
    :return: ``True`` when the copied-device totals remain non-negative.
    """
    is_physical: bool = True
    pq_index: int
    for pq_index in range(case_data.pq.size):
        target_load_active_total_mw: float = mapping.pq_base_load_active_total_mw[pq_index] - (
            (float(scenario.pq_active_power[pq_index]) - float(mapping.pq_base_net_active[pq_index])) * case_data.sbase
        )
        if target_load_active_total_mw >= 0.0:
            pass
        else:
            is_physical = False

    pv_index: int
    for pv_index in range(case_data.pv.size):
        target_generator_active_total_mw: float = mapping.pv_base_generator_active_total_mw[pv_index] + (
            (float(scenario.pv_active_power[pv_index]) - float(mapping.pv_base_net_active[pv_index])) * case_data.sbase
        )

        if target_generator_active_total_mw >= 0.0:
            pass
        else:
            is_physical = False

    return is_physical


def create_base_scenario(case_data: VeraGridQueryCaseData) -> FireTestScenario:
    """
    Create the unperturbed base-case scenario.

    :param case_data: Base case data.
    :return: Base FireTestScenario.
    """
    return FireTestScenario(
        name="base",
        pq_active_power=case_data.base_power[case_data.pq].real.copy(),
        pq_reactive_power=case_data.base_power[case_data.pq].imag.copy(),
        pv_active_power=case_data.base_power[case_data.pv].real.copy(),
        active_delta_sum=0.0,
        reactive_delta_sum=0.0,
    )


def create_random_scenario(
    case_data: VeraGridQueryCaseData,
    mapping: DeviceBusMapping,
    scenario_index: int,
    shrink_factor: float,
    rng: np.random.Generator,
) -> FireTestScenario:
    """
    Create one random near-balanced scenario around the base operating point.

    :param case_data: Base case data.
    :param mapping: Device-to-bus mapping used to freeze immutable buses.
    :param scenario_index: Scenario number used in the scenario name.
    :param shrink_factor: Scalar used to reduce the perturbation size when needed.
    :param rng: NumPy random generator.
    :return: Random FireTestScenario.
    """
    base_pq_active: np.ndarray = case_data.base_power[case_data.pq].real.copy()
    base_pq_reactive: np.ndarray = case_data.base_power[case_data.pq].imag.copy()
    base_pv_active: np.ndarray = case_data.base_power[case_data.pv].real.copy()
    pq_active_scale: np.ndarray = np.maximum(mapping.pq_base_load_active_total_mw / case_data.sbase, 0.03)
    pq_reactive_scale: np.ndarray = np.maximum(
        np.abs(mapping.pq_base_load_reactive_total_mvar) / case_data.sbase,
        0.02,
    )
    pv_positive_generator_mask: np.ndarray = np.logical_and(
        mapping.pv_bus_mutable,
        mapping.pv_base_generator_active_total_mw > 1.0e-9,
    )
    pv_active_scale: np.ndarray = np.maximum(
        mapping.pv_base_generator_active_total_mw / case_data.sbase,
        0.03,
    )
    pq_active_scale = pq_active_scale * mapping.pq_bus_mutable.astype(np.float64)
    pq_reactive_scale = pq_reactive_scale * mapping.pq_bus_mutable.astype(np.float64)
    pv_active_scale = pv_active_scale * pv_positive_generator_mask.astype(np.float64)
    pq_active_delta: np.ndarray = shrink_factor * rng.normal(0.0, 0.08, size=case_data.pq.size) * pq_active_scale
    pq_reactive_delta: np.ndarray = shrink_factor * rng.normal(0.0, 0.08, size=case_data.pq.size) * pq_reactive_scale
    pv_active_delta: np.ndarray = shrink_factor * rng.normal(0.0, 0.06, size=case_data.pv.size) * pv_active_scale

    # The active-power perturbations are recentered so the non-slack total
    # injection remains close to the base case.
    active_delta_sum: float = float(np.sum(pq_active_delta) + np.sum(pv_active_delta))
    pv_balance_weights: np.ndarray = calculate_distribution_weights(
        reference_values=(mapping.pv_base_generator_active_total_mw / case_data.sbase) * pv_positive_generator_mask.astype(np.float64),
    )
    pv_active_delta = pv_active_delta - active_delta_sum * pv_balance_weights

    # The PQ reactive perturbations are also recentered so the scenarios remain
    # close to the original reactive balance.
    reactive_delta_sum: float = float(np.sum(pq_reactive_delta))
    pq_balance_weights: np.ndarray = calculate_distribution_weights(
        reference_values=(np.abs(base_pq_reactive) + 1e-6) * mapping.pq_bus_mutable.astype(np.float64),
    )
    pq_reactive_delta = pq_reactive_delta - reactive_delta_sum * pq_balance_weights

    return FireTestScenario(
        name=f"random_{scenario_index:02d}",
        pq_active_power=base_pq_active + pq_active_delta,
        pq_reactive_power=base_pq_reactive + pq_reactive_delta,
        pv_active_power=base_pv_active + pv_active_delta,
        active_delta_sum=float(np.sum(pq_active_delta) + np.sum(pv_active_delta)),
        reactive_delta_sum=float(np.sum(pq_reactive_delta)),
    )


def create_fire_test_scenarios(
    case_data: VeraGridQueryCaseData,
    mapping: DeviceBusMapping,
    scenario_count: int,
    seed: int,
) -> list[FireTestScenario]:
    """
    Create the fire-test scenario batch.

    :param case_data: Base case data.
    :param mapping: Device-to-bus mapping.
    :param scenario_count: Number of scenarios including the base case.
    :param seed: Random seed.
    :return: List of FireTestScenario objects.
    """
    scenarios: list[FireTestScenario] = list()
    scenarios.append(create_base_scenario(case_data=case_data))
    rng: np.random.Generator = np.random.default_rng(seed)
    scenario_index: int = 1

    while scenario_index < scenario_count:
        shrink_factor: float = 1.0
        trial_index: int = 0
        scenario_created: bool = False

        while trial_index < 8 and scenario_created is False:
            scenario: FireTestScenario = create_random_scenario(
                case_data=case_data,
                mapping=mapping,
                scenario_index=scenario_index,
                shrink_factor=shrink_factor,
                rng=rng,
            )

            if scenario_is_physical(mapping=mapping, case_data=case_data, scenario=scenario):
                scenarios.append(scenario)
                scenario_created = True
            else:
                shrink_factor = 0.5 * shrink_factor

            trial_index = trial_index + 1

        if scenario_created:
            scenario_index = scenario_index + 1
        else:
            raise RuntimeError(f"Could not create a physical scenario for index {scenario_index}")

    return scenarios


def create_nr_options(vg: object) -> object:
    """
    Create Newton-Raphson power-flow options for the fire test.

    :param vg: Imported VeraGridEngine module.
    :return: VeraGridEngine PowerFlowOptions object.
    """
    try:
        options: object = vg.PowerFlowOptions(
            solver_type=vg.SolverType.NR,
            retry_with_other_methods=False,
            control_q=True,
            control_taps_phase=False,
            control_taps_modules=False,
            apply_temperature_correction=False,
            use_stored_guess=False,
            tolerance=1e-10,
        )
    except TypeError:
        options = vg.PowerFlowOptions(vg.SolverType.NR, verbose=False)

    return options


def run_newton_reference(
    base_grid: "MultiCircuit",
    case_data: VeraGridQueryCaseData,
    mapping: DeviceBusMapping,
    scenario: FireTestScenario,
) -> tuple["PowerFlowResults", VeraGridQueryCaseData]:
    """
    Run the Newton-Raphson reference for one scenario.

    :param base_grid: Base VeraGrid grid.
    :param case_data: Base case data.
    :param mapping: Device-to-bus mapping.
    :param scenario: Scenario to apply.
    :return: ``(power_flow_results, compiled_modified_case_data)``.
    """
    vg: object
    cf: object
    vg, cf = import_veragrid_engine_modules()
    _ = cf
    grid_copy: "MultiCircuit" = base_grid.copy()
    loads: list["Load"] = grid_copy.get_loads()
    generators: list["Generator"] = grid_copy.get_generators()

    # The copied grid is edited in device space so VeraGrid NR sees exactly the
    # same intended bus injections that the artifact sees in bus space.
    apply_pq_bus_targets_to_grid(
        loads=loads,
        mapping=mapping,
        case_data=case_data,
        scenario=scenario,
    )
    apply_pv_bus_targets_to_grid(
        generators=generators,
        mapping=mapping,
        case_data=case_data,
        scenario=scenario,
    )

    modified_case_data: VeraGridQueryCaseData = load_veragrid_case_data(grid=grid_copy)
    nr_results: "PowerFlowResults" = vg.power_flow(
        grid=grid_copy,
        options=create_nr_options(vg=vg),
    )
    return nr_results, modified_case_data


def calculate_injection_write_error(
    modified_case_data: VeraGridQueryCaseData,
    scenario: FireTestScenario,
) -> float:
    """
    Calculate the maximum target-vs-written bus-injection error.

    :param modified_case_data: Compiled case data after applying the scenario.
    :param scenario: Requested scenario.
    :return: Maximum absolute injection write error in per unit.
    """
    pq_active_error: np.ndarray = np.abs(modified_case_data.base_power[modified_case_data.pq].real - scenario.pq_active_power)
    pq_reactive_error: np.ndarray = np.abs(modified_case_data.base_power[modified_case_data.pq].imag - scenario.pq_reactive_power)
    pv_active_error: np.ndarray = np.abs(modified_case_data.base_power[modified_case_data.pv].real - scenario.pv_active_power)
    stacked_error: np.ndarray = np.concatenate((pq_active_error, pq_reactive_error, pv_active_error))
    return float(np.max(stacked_error))


def compare_artifact_with_nr(
    artifact_result: MDHEMQueryResult,
    nr_results: "PowerFlowResults",
) -> tuple[float, float, float]:
    """
    Compare the artifact output with Newton-Raphson results.

    :param artifact_result: Artifact query result.
    :param nr_results: Newton-Raphson result.
    :return: ``(max_voltage_diff, max_flow_diff_mva, max_loading_diff)``.
    """
    max_voltage_diff: float = float(np.max(np.abs(artifact_result.voltage - nr_results.voltage)))
    max_flow_diff_mva: float = float(np.max(np.abs(artifact_result.branch_from_power - nr_results.Sf)))
    max_loading_diff: float = float(np.max(np.abs(artifact_result.branch_loading - nr_results.loading)))
    return max_voltage_diff, max_flow_diff_mva, max_loading_diff


def evaluate_scenario(
    base_grid: "MultiCircuit",
    case_data: VeraGridQueryCaseData,
    mapping: DeviceBusMapping,
    artifact: MDHEMPVQueryArtifact,
    scenario: FireTestScenario,
    artifact_tolerance: float,
    voltage_threshold: float,
    branch_flow_threshold_mva: float,
    loading_threshold: float,
    injection_write_threshold: float,
) -> FireTestMetrics:
    """
    Evaluate one fire-test scenario against the artifact and NR reference.

    :param base_grid: Base VeraGrid grid.
    :param case_data: Base case data.
    :param mapping: Device-to-bus mapping.
    :param artifact: Loaded artifact.
    :param scenario: Scenario to evaluate.
    :param artifact_tolerance: Internal artifact tolerance used for its convergence-like flag.
    :param voltage_threshold: Maximum accepted complex-voltage error in per unit.
    :param branch_flow_threshold_mva: Maximum accepted branch-from flow error in MVA.
    :param loading_threshold: Maximum accepted loading error.
    :param injection_write_threshold: Maximum accepted target write error in per unit.
    :return: FireTestMetrics for the scenario.
    """
    artifact_result: MDHEMQueryResult = artifact.query(
        pq_active_power=scenario.pq_active_power,
        pq_reactive_power=scenario.pq_reactive_power,
        pv_active_power=scenario.pv_active_power,
        tolerance=artifact_tolerance,
    )
    nr_results: "PowerFlowResults"
    modified_case_data: VeraGridQueryCaseData
    nr_results, modified_case_data = run_newton_reference(
        base_grid=base_grid,
        case_data=case_data,
        mapping=mapping,
        scenario=scenario,
    )
    injection_write_error: float = calculate_injection_write_error(
        modified_case_data=modified_case_data,
        scenario=scenario,
    )
    max_voltage_diff: float
    max_flow_diff_mva: float
    max_loading_diff: float
    max_voltage_diff, max_flow_diff_mva, max_loading_diff = compare_artifact_with_nr(
        artifact_result=artifact_result,
        nr_results=nr_results,
    )
    passed: bool = False

    # The pass flag checks both solver health and numerical agreement.
    if nr_results.converged:
        if artifact_result.converged_like:
            if injection_write_error <= injection_write_threshold:
                if max_voltage_diff <= voltage_threshold:
                    if max_flow_diff_mva <= branch_flow_threshold_mva:
                        if max_loading_diff <= loading_threshold:
                            passed = True
                        else:
                            passed = False
                    else:
                        passed = False
                else:
                    passed = False
            else:
                passed = False
        else:
            passed = False
    else:
        passed = False

    return FireTestMetrics(
        scenario_name=scenario.name,
        nr_converged=bool(nr_results.converged),
        artifact_converged=bool(artifact_result.converged_like),
        injection_write_error=injection_write_error,
        nr_error=float(nr_results.error),
        artifact_error=float(artifact_result.mismatch_norm),
        max_voltage_diff=max_voltage_diff,
        max_flow_diff_mva=max_flow_diff_mva,
        max_loading_diff=max_loading_diff,
        passed=passed,
    )


def print_fire_test_report(
    scenarios: list[FireTestScenario],
    metrics_list: list[FireTestMetrics],
    voltage_threshold: float,
    branch_flow_threshold_mva: float,
    loading_threshold: float,
    injection_write_threshold: float,
) -> None:
    """
    Print the fire-test results and summary.

    :param scenarios: Scenario batch.
    :param metrics_list: Metrics for the scenario batch.
    :param voltage_threshold: Voltage pass threshold.
    :param branch_flow_threshold_mva: Branch-flow pass threshold.
    :param loading_threshold: Loading pass threshold.
    :param injection_write_threshold: Injection write pass threshold.
    :return: None.
    """
    print("\nMDHEM-PV case14 fire test")
    print("-------------------------")
    print(f"Voltage threshold:       {voltage_threshold:.4e} p.u.")
    print(f"Branch flow threshold:   {branch_flow_threshold_mva:.4f} MVA")
    print(f"Loading threshold:       {loading_threshold:.4e}")
    print(f"Injection write limit:   {injection_write_threshold:.4e} p.u.")
    print("\nScenario results")
    print("name, dP_sum, dQ_sum, nr_conv, art_conv, write_err, nr_err, art_err, max_dV, max_dSf, max_dloading, passed")

    scenario_index: int
    for scenario_index in range(len(scenarios)):
        scenario: FireTestScenario = scenarios[scenario_index]
        metrics: FireTestMetrics = metrics_list[scenario_index]
        print(
            f"{scenario.name}, "
            f"{scenario.active_delta_sum:+.3e}, "
            f"{scenario.reactive_delta_sum:+.3e}, "
            f"{metrics.nr_converged}, "
            f"{metrics.artifact_converged}, "
            f"{metrics.injection_write_error:.3e}, "
            f"{metrics.nr_error:.3e}, "
            f"{metrics.artifact_error:.3e}, "
            f"{metrics.max_voltage_diff:.3e}, "
            f"{metrics.max_flow_diff_mva:.3e}, "
            f"{metrics.max_loading_diff:.3e}, "
            f"{metrics.passed}"
        )

    passed_count: int = 0
    worst_voltage_diff: float = 0.0
    worst_flow_diff_mva: float = 0.0
    worst_loading_diff: float = 0.0
    worst_write_error: float = 0.0
    for metrics in metrics_list:
        if metrics.passed:
            passed_count = passed_count + 1
        else:
            passed_count = passed_count + 0
        worst_voltage_diff = max(worst_voltage_diff, metrics.max_voltage_diff)
        worst_flow_diff_mva = max(worst_flow_diff_mva, metrics.max_flow_diff_mva)
        worst_loading_diff = max(worst_loading_diff, metrics.max_loading_diff)
        worst_write_error = max(worst_write_error, metrics.injection_write_error)

    print("\nSummary")
    print(f"Passed scenarios:        {passed_count}/{len(metrics_list)}")
    print(f"Worst voltage diff:      {worst_voltage_diff:.4e} p.u.")
    print(f"Worst branch flow diff:  {worst_flow_diff_mva:.4f} MVA")
    print(f"Worst loading diff:      {worst_loading_diff:.4e}")
    print(f"Worst write error:       {worst_write_error:.4e} p.u.")


def run_case14_fire_test() -> None:
    """
    Build the artifact once and compare it with Newton-Raphson on multiple scenarios.

    :return: None.
    """
    case_path: Path = Path(__file__).resolve().with_name("case14.matpower")
    artifact_path: Path = Path(__file__).resolve().with_name("mdhelm_pv_case14_fire_test_artifact.npz")
    max_order: int = 4
    scenario_count: int = 10
    seed: int = 14
    artifact_tolerance: float = 1.0e-5
    voltage_threshold: float = 2.0e-2
    branch_flow_threshold_mva: float = 10.0
    loading_threshold: float = 1.0e-1
    injection_write_threshold: float = 2.0e-6
    base_grid: "MultiCircuit" = load_multicircuit_from_file(matpower_path=case_path)
    case_data: VeraGridQueryCaseData
    artifact: MDHEMPVQueryArtifact
    germ_error: float
    case_data, artifact, germ_error = build_artifact_from_case(grid=base_grid, max_order=max_order)
    mapping: DeviceBusMapping = build_device_bus_mapping(grid=base_grid, case_data=case_data)
    scenarios: list[FireTestScenario] = create_fire_test_scenarios(
        case_data=case_data,
        mapping=mapping,
        scenario_count=scenario_count,
        seed=seed,
    )

    # The artifact is saved and reloaded so the fire test covers the actual
    # persistent artifact path rather than only the in-memory object.
    save_query_artifact(path=artifact_path, artifact=artifact)
    restored_artifact: MDHEMPVQueryArtifact = load_query_artifact(path=artifact_path)
    metrics_list: list[FireTestMetrics] = list()
    scenario: FireTestScenario

    for scenario in scenarios:
        metrics: FireTestMetrics = evaluate_scenario(
            base_grid=base_grid,
            case_data=case_data,
            mapping=mapping,
            artifact=restored_artifact,
            scenario=scenario,
            artifact_tolerance=artifact_tolerance,
            voltage_threshold=voltage_threshold,
            branch_flow_threshold_mva=branch_flow_threshold_mva,
            loading_threshold=loading_threshold,
            injection_write_threshold=injection_write_threshold,
        )
        metrics_list.append(metrics)

    print(f"\nArtifact path:           {artifact_path}")
    print(f"Artifact germ residual:  {germ_error:.4e}")
    print(f"Scenarios:               {scenario_count}")
    print(f"Polynomial order:        {max_order}")

    print_fire_test_report(
        scenarios=scenarios,
        metrics_list=metrics_list,
        voltage_threshold=voltage_threshold,
        branch_flow_threshold_mva=branch_flow_threshold_mva,
        loading_threshold=loading_threshold,
        injection_write_threshold=injection_write_threshold,
    )


if __name__ == "__main__":
    run_case14_fire_test()
else:
    pass
