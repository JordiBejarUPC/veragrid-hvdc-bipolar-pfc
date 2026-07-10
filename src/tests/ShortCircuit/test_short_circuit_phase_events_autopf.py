from pathlib import Path

import numpy as np

import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType


def test_phase_short_circuit_events_auto_run_3ph_power_flow():
    repo_root = Path(__file__).resolve().parents[3]
    grid_path = repo_root / "trunk" / "bug_investigations" / "short_circuit_no_values" / "IEEE9_bus_Modified.veragrid"

    grid = vge.open_file(str(grid_path))

    pf_options = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
    )
    pf_results = vge.power_flow(grid=grid, options=pf_options)

    sc_driver = vge.ShortCircuitDriver(
        grid=grid,
        options=ShortCircuitOptions(),
        pf_options=pf_options,
        pf_results=pf_results,
        pf_results3ph=None,
    )
    sc_driver.run()

    assert sc_driver.pf_results3ph is not None
    assert np.any(np.abs(sc_driver.results.voltage1) > 0.0)
    assert np.any(np.abs(sc_driver.results.SCpower) > 0.0)
