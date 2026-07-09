"""
Build and query the full per-bus MDHEM-PV artifact for ACTIVSg2000.

This file intentionally keeps the same full query space as
``mdhelm_pv_case14_query_artifact.py``:

* one ``P`` dimension per PQ bus,
* one ``Q`` dimension per PQ bus,
* one ``P`` dimension per PV bus.

Nothing is reduced here. The point of this file is to run the exact full-space
artifact builder on ``case_ACTIVSg2000.matpower``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from mdhelm import count_coefficients
from mdhelm_pv_case14_fire_test import build_device_bus_mapping
from mdhelm_pv_case14_fire_test import create_fire_test_scenarios
from mdhelm_pv_case14_fire_test import create_nr_options
from mdhelm import MDHEMQueryResult
from mdhelm import MDHEMPVQueryArtifact
from mdhelm import VeraGridQueryCaseData
from mdhelm import build_artifact_from_case
from mdhelm import create_mdhelm_inputs
from mdhelm import import_veragrid_engine_modules
from mdhelm import load_multicircuit_from_file
from mdhelm import load_query_artifact
from mdhelm import save_query_artifact
from mdhelm import validate_multi_index_table_shape

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


def create_nr_seed_results(grid: "MultiCircuit") -> "PowerFlowResults":
    """
    Run one Newton-Raphson solve to seed the full artifact.

    :param grid:
        VeraGrid grid.
    :return:
        Converged Newton-Raphson power-flow result.
    """
    vg: object
    cf: object
    vg, cf = import_veragrid_engine_modules()
    _ = cf
    nr_results: "PowerFlowResults" = vg.power_flow(
        grid=grid,
        options=create_nr_options(vg=vg),
    )
    return nr_results


def print_full_space_preflight(case_data: VeraGridQueryCaseData, max_order: int) -> None:
    """
    Print the full-space dimension and coefficient estimate.

    :param case_data:
        Compiled VeraGrid case data.
    :param max_order:
        Maximum total polynomial order.
    :return:
        None.
    """
    pq_count: int = int(case_data.pq.size)
    pv_count: int = int(case_data.pv.size)
    dimension_count: int = 2 * pq_count + pv_count
    expected_coefficients: int = count_coefficients(dims=dimension_count, max_order=max_order)

    print("\nACTIVSg2000 full MDHEM-PV artifact preflight")
    print("--------------------------------------------")
    print(f"Buses:                        {case_data.ybus.shape[0]}")
    print(f"PQ buses:                     {pq_count}")
    print(f"PV buses:                     {pv_count}")
    print(f"Embedding dimensions:         {dimension_count}")
    print(f"Maximum order:                {max_order}")
    print(f"Expected coefficient count:   {expected_coefficients}")
    validate_multi_index_table_shape(
        dims=dimension_count,
        max_order=max_order,
        total_terms=expected_coefficients,
    )


def query_base_case(
    artifact: MDHEMPVQueryArtifact,
    case_data: VeraGridQueryCaseData,
    tolerance: float,
) -> MDHEMQueryResult:
    """
    Query the restored artifact at the compiled base case.

    :param artifact:
        Restored full query artifact.
    :param case_data:
        Compiled VeraGrid case data.
    :param tolerance:
        Convergence-like tolerance.
    :return:
        Artifact query result.
    """
    pq_active_power: np.ndarray = case_data.base_power[case_data.pq].real.copy()
    pq_reactive_power: np.ndarray = case_data.base_power[case_data.pq].imag.copy()
    pv_active_power: np.ndarray = case_data.base_power[case_data.pv].real.copy()
    result: MDHEMQueryResult = artifact.query(
        pq_active_power=pq_active_power,
        pq_reactive_power=pq_reactive_power,
        pv_active_power=pv_active_power,
        tolerance=tolerance,
    )
    return result


def query_one_random_scenario(
    artifact: MDHEMPVQueryArtifact,
    case_data: VeraGridQueryCaseData,
    grid: "MultiCircuit",
    tolerance: float,
) -> MDHEMQueryResult:
    """
    Query the restored artifact at one random physical scenario.

    :param artifact:
        Restored full query artifact.
    :param case_data:
        Compiled VeraGrid case data.
    :param grid:
        Base VeraGrid grid.
    :param tolerance:
        Convergence-like tolerance.
    :return:
        Artifact query result for the first random scenario.
    """
    mapping = build_device_bus_mapping(grid=grid, case_data=case_data)
    scenarios = create_fire_test_scenarios(
        case_data=case_data,
        mapping=mapping,
        scenario_count=2,
        seed=2000,
    )
    scenario = scenarios[1]
    result: MDHEMQueryResult = artifact.query(
        pq_active_power=scenario.pq_active_power,
        pq_reactive_power=scenario.pq_reactive_power,
        pv_active_power=scenario.pv_active_power,
        tolerance=tolerance,
    )
    return result


def run_activsg2000_full_artifact_demo() -> None:
    """
    Build, save, load and query the full per-bus ACTIVSg2000 artifact.

    :return:
        None.
    """
    case_path: Path = Path(__file__).resolve().with_name("case_ACTIVSg2000.matpower")
    artifact_path: Path = Path(__file__).resolve().with_name("mdhelm_pv_activsg2000_full_query_artifact.npz")
    max_order: int = 4
    tolerance: float = 1.0e-8
    use_nr_seed: bool = True
    grid: "MultiCircuit" = load_multicircuit_from_file(matpower_path=case_path)
    case_data: VeraGridQueryCaseData = create_mdhelm_inputs(grid=grid)
    try:
        print_full_space_preflight(case_data=case_data, max_order=max_order)
    except MemoryError as exc:
        print(str(exc))
        return
    germ_seed_results: "PowerFlowResults | None"

    # The full-space artifact build is left exactly as requested. The only
    # convenience here is the optional NR seed, because it centers the germ on
    # the physical operating point of the imported 2000-bus case.
    if use_nr_seed:
        germ_seed_results = create_nr_seed_results(grid=grid)
    else:
        germ_seed_results = None

    built_case_data: VeraGridQueryCaseData
    artifact: MDHEMPVQueryArtifact
    germ_error: float
    built_case_data, artifact, germ_error = build_artifact_from_case(
        grid=grid,
        max_order=max_order,
        germ_seed_results=germ_seed_results,
    )
    save_query_artifact(path=artifact_path, artifact=artifact)
    restored_artifact: MDHEMPVQueryArtifact = load_query_artifact(path=artifact_path)
    base_result: MDHEMQueryResult = query_base_case(
        artifact=restored_artifact,
        case_data=built_case_data,
        tolerance=tolerance,
    )
    random_result: MDHEMQueryResult = query_one_random_scenario(
        artifact=restored_artifact,
        case_data=built_case_data,
        grid=grid,
        tolerance=tolerance,
    )

    print("\nACTIVSg2000 full MDHEM-PV query artifact")
    print("----------------------------------------")
    print(f"Artifact path:                 {artifact_path}")
    print(f"Maximum order:                 {restored_artifact.get_max_order()}")
    print(f"Embedding dimensions:          {restored_artifact.get_dimensions_count()}")
    print(f"Artifact germ residual:        {germ_error:.4e}")
    print(f"Base-case query mismatch:      {base_result.mismatch_norm:.4e}")
    print(f"Base-case PV voltage error:    {base_result.pv_voltage_error:.4e}")
    print(f"Base-case converged-like:      {base_result.converged_like}")
    print(f"Random-case query mismatch:    {random_result.mismatch_norm:.4e}")
    print(f"Random-case PV voltage error:  {random_result.pv_voltage_error:.4e}")
    print(f"Random-case converged-like:    {random_result.converged_like}")


if __name__ == "__main__":
    run_activsg2000_full_artifact_demo()
