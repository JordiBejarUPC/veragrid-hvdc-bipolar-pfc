from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.IO.fmu.exporter.build import host_build_capable
from VeraGridEngine.IO.fmu.exporter.compat import Var
from VeraGridEngine.IO.fmu.importer.model_description import FmuInterfaceMode
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from tests.FMI.fmi_test_support import execute_test_rms_fmu_case


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_rms_fmu_co_simulation_runs_end_to_end(tmp_path: Path) -> None:
    """Exercise RMS Co-Simulation through the complete product integration path.

    :param tmp_path: Isolated FMU and native staging directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    driver: RmsSimulationDriver
    load: Load
    fmu_path: Path
    driver, load, fmu_path = execute_test_rms_fmu_case(
        tmp_path,
        FmuInterfaceMode.CO_SIMULATION,
    )

    if driver.results is None:
        raise AssertionError("The RMS Co-Simulation case did not publish results")
    else:
        results: RmsResults = driver.results
    available_group_indices: np.ndarray = np.flatnonzero(
        results.has_event_group_results
    )
    assert available_group_indices.size == 1
    group_index: int = int(available_group_indices[0])
    assert bool(results.well_initialized[group_index])
    assert bool(results.converged[group_index])
    assert float(results.time_array[-1].value) * 1.0e-9 == pytest.approx(5.0e-3)

    p_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.P]
    q_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
    p_values: np.ndarray = results.values[
        :, results.uid2idx[p_var.uid], group_index
    ]
    q_values: np.ndarray = results.values[
        :, results.uid2idx[q_var.uid], group_index
    ]
    assert bool(np.all(np.isfinite(p_values)))
    assert bool(np.all(np.isfinite(q_values)))
    assert abs(float(p_values[-1])) >= 1.0e-8
    assert abs(float(q_values[-1])) >= 1.0e-8
    assert fmu_path.exists()
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_rms_fmu_model_exchange_runs_end_to_end(tmp_path: Path) -> None:
    """Exercise RMS Model Exchange through the complete product integration path.

    :param tmp_path: Isolated FMU and native staging directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    driver: RmsSimulationDriver
    load: Load
    fmu_path: Path
    driver, load, fmu_path = execute_test_rms_fmu_case(
        tmp_path,
        FmuInterfaceMode.MODEL_EXCHANGE,
    )

    if driver.results is None:
        raise AssertionError("The RMS Model Exchange case did not publish results")
    else:
        results: RmsResults = driver.results
    available_group_indices: np.ndarray = np.flatnonzero(
        results.has_event_group_results
    )
    assert available_group_indices.size == 1
    group_index: int = int(available_group_indices[0])
    assert bool(results.well_initialized[group_index])
    assert bool(results.converged[group_index])
    assert float(results.time_array[-1].value) * 1.0e-9 == pytest.approx(5.0e-3)

    p_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.P]
    q_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
    p_values: np.ndarray = results.values[
        :, results.uid2idx[p_var.uid], group_index
    ]
    q_values: np.ndarray = results.values[
        :, results.uid2idx[q_var.uid], group_index
    ]
    assert bool(np.all(np.isfinite(p_values)))
    assert bool(np.all(np.isfinite(q_values)))
    assert abs(float(p_values[-1])) >= 1.0e-8
    assert abs(float(q_values[-1])) >= 1.0e-8
    assert fmu_path.exists()
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()
