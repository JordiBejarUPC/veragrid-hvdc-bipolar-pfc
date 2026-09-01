from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.fmu.exporter.compat import Block, Var
from VeraGridEngine.IO.fmu.exporter.build import host_build_capable
from VeraGridEngine.IO.fmu.importer.examples.common import (
    _build_rms_results_summary,
    run_rms_cs_example,
    run_rms_me_example,
)
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.enumerations import VarPowerFlowReferenceType


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_rms_fmu_example_runs_end_to_end(tmp_path: Path) -> None:
    """
    Export one FMU, attach it to a load, and run the RMS example end to end.

    :param tmp_path: Temporary pytest output directory.
    :return: None.
    """

    pytest.importorskip("fmpy")

    report_path: Path = run_rms_cs_example(tmp_path)

    report_text: str = report_path.read_text(encoding="utf-8")
    p_line: str = next(line for line in report_text.splitlines() if line.startswith("P_final = "))
    q_line: str = next(line for line in report_text.splitlines() if line.startswith("Q_final = "))

    assert report_path.exists()
    assert "mode = CoSimulation" in report_text
    assert "event_group_count = 1" in report_text
    assert "well_initialized = True" in report_text
    assert "converged = True" in report_text
    assert "final_time_seconds = 0.005000000000" in report_text
    assert abs(float(p_line.removeprefix("P_final = "))) >= 1.0e-8
    assert abs(float(q_line.removeprefix("Q_final = "))) >= 1.0e-8
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_rms_me_fmu_example_runs_end_to_end(tmp_path: Path) -> None:
    """Export and execute the native RMS Model Exchange example.

    :param tmp_path: Temporary pytest output directory.
    :return: None.
    """

    pytest.importorskip("fmpy")

    report_path: Path = run_rms_me_example(tmp_path)

    report_text: str = report_path.read_text(encoding="utf-8")
    p_line: str = next(line for line in report_text.splitlines() if line.startswith("P_final = "))
    q_line: str = next(line for line in report_text.splitlines() if line.startswith("Q_final = "))

    assert report_path.exists()
    assert "mode = ModelExchange" in report_text
    assert "event_group_count = 1" in report_text
    assert "well_initialized = True" in report_text
    assert "converged = True" in report_text
    assert "final_time_seconds = 0.005000000000" in report_text
    assert abs(float(p_line.removeprefix("P_final = "))) >= 1.0e-8
    assert abs(float(q_line.removeprefix("Q_final = "))) >= 1.0e-8
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()


@pytest.mark.parametrize(
    "failure_case",
    (
        "missing_results",
        "group_mismatch",
        "failed_status",
        "wrong_time",
        "missing_variable",
        "nan_output",
        "infinite_output",
        "zero_placeholder",
    ),
)
def test_rms_results_summary_rejects_inconclusive_results(failure_case: str) -> None:
    """Reject every result state that cannot prove one conclusive RMS run.

    :param failure_case: Result contract violation introduced into a valid baseline.
    :return: None.
    """

    # Two real groups place the sole active result at index one, proving that
    # the summary does not flatten or assume the first preallocated group.
    grid: MultiCircuit = MultiCircuit()
    grid.add_rms_events_group(RmsEventsGroup(name="inactive", active=False))
    grid.add_rms_events_group(RmsEventsGroup(name="active", active=True))

    # A real Block supplies the same external P/Q identity contract used by an
    # attached FMU device, without constructing or patching a native runtime.
    p_var: Var = Var("P_test")
    q_var: Var = Var("Q_test")
    load: Load = Load(name="RMS summary test load")
    load.rms_model = Block(
        algebraic_vars=list((p_var, q_var)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.P, p_var),
            (VarPowerFlowReferenceType.Q, q_var),
        )),
    )

    # The driver only owns the result container in this focused test. A real
    # empty PowerFlowResults instance satisfies its typed construction contract.
    power_flow_results: PowerFlowResults = PowerFlowResults(
        n=0,
        m=0,
        n_hvdc=0,
        n_vsc=0,
        n_gen=0,
        n_batt=0,
        n_sh=0,
        bus_names=np.array([], dtype=str),
        branch_names=np.array([], dtype=str),
        hvdc_names=np.array([], dtype=str),
        vsc_names=np.array([], dtype=str),
        gen_names=np.array([], dtype=str),
        batt_names=np.array([], dtype=str),
        sh_names=np.array([], dtype=str),
        bus_types=np.array([], dtype=int),
    )
    driver: RmsSimulationDriver = RmsSimulationDriver(
        grid=grid,
        options=RmsOptions(simulation_time=5.0e-3),
        pf_results=power_flow_results,
    )
    results: RmsResults = RmsResults(
        time_array=pd.DatetimeIndex(pd.to_datetime(np.array([0.0, 5.0e6], dtype=float))),
        rms_events_group_names=np.array(["inactive", "active"], dtype=str),
        rms_events_group_idtags=np.array(["inactive-id", "active-id"], dtype=str),
        variables=list((p_var, q_var)),
        uid2idx=dict(((p_var.uid, 0), (q_var.uid, 1))),
        vars_glob_name2uid=dict((("P_test", p_var.uid), ("Q_test", q_var.uid))),
        devices_vars_info=dict(),
        has_event_group_results=np.array([False, True], dtype=bool),
    )
    results.values[-1, 0, 1] = -0.1
    results.values[-1, 1, 1] = -0.01
    results.well_initialized[1] = True
    results.converged[1] = True
    driver.results = results

    # Each mutation isolates one fail-closed requirement while preserving every
    # other valid owner and value from the baseline above.
    if failure_case == "missing_results":
        driver.results = None
    elif failure_case == "group_mismatch":
        results.has_event_group_results = np.array([True, False], dtype=bool)
    elif failure_case == "failed_status":
        results.converged[1] = False
    elif failure_case == "wrong_time":
        results.time_array = pd.DatetimeIndex(
            pd.to_datetime(np.array([0.0, 4.0e6], dtype=float))
        )
    elif failure_case == "missing_variable":
        results.uid2idx.pop(q_var.uid)
    elif failure_case == "nan_output":
        results.values[-1, 0, 1] = np.nan
    elif failure_case == "infinite_output":
        results.values[-1, 0, 1] = np.inf
    elif failure_case == "zero_placeholder":
        results.values[-1, 0, 1] = 0.0
    else:
        raise AssertionError("Unhandled RMS summary failure case")

    with pytest.raises(RuntimeError):
        _build_rms_results_summary(driver, load)
