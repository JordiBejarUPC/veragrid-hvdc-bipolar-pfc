from pathlib import Path
import sys

import numpy as np

this_file = Path(__file__).resolve()
repo_root = this_file.parents[3]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import VeraGridEngine as vg
from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.rms_problem_factory import build_rms_problem
from build_and_populate_tuvalu_grid import TuvaluGridPopulator, initialize_tuvalu_rms_models


def main() -> int:
    base_grid_path = repo_root / "trunk" / "tuvalu" / "funafuti_base.veragrid"
    profiles_excel = repo_root.parent / "Tuvalu" / "data" / "profiles_and_scenarios.xlsx"
    demand_excel = repo_root.parent / "Tuvalu" / "data" / "plant_data" / "combined_output_hand_corrected.xlsx"

    print(f"Loading Tuvalu base grid: {base_grid_path}")
    grid = vg.open_file(str(base_grid_path))

    print("Populating one-step time-series profiles...")
    populator = TuvaluGridPopulator(
        grid=grid,
        profiles_and_scenarios_excel=profiles_excel,
        demand_excel=demand_excel,
        start_year=2024,
        profile_steps=1,
    )
    populator.populate()

    initialize_tuvalu_rms_models(grid)

    print("Running snapshot power flow...")
    pf_driver = vg.PowerFlowDriver(
        grid=grid,
        options=vg.PowerFlowOptions(solver_type=vg.SolverType.HELM),
    )
    pf_driver.run()
    pf_results = pf_driver.results
    print(f"Power flow converged: {pf_results.converged}")
    if not pf_results.converged:
        return 1

    if not grid.rms_events_groups:
        grid.add_rms_events_group(RmsEventsGroup(name="tuvalu_base_case"))

    print("Running RMS dynamic simulation...")
    rms_options = vg.RmsOptions(
        simulation_time=0.1,
        time_step=0.01,
        max_iter=60,
        tolerance=1e-6,
        integration_method=vg.DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=vg.RmsInitializationMethod.Explicit,
    )
    problem = build_rms_problem(
        grid=grid,
        options=rms_options,
        pf_results=pf_results,
        progress_signal=None,
    )
    problem.set_events_group(rms_events_group=grid.rms_events_groups[0])
    problem.reset_boundary_update_state(0.0)

    solver = BackEulerImplicitIntegration(
        problem=problem,
        t0=0.0,
        t_end=rms_options.simulation_time,
        h=rms_options.time_step,
        max_iter=rms_options.max_iter,
    )
    t, _, well_init, converged = solver.simulate()
    print(f"RMS well initialized: {well_init}")
    print(f"RMS converged: {converged}")
    print(f"Computed RMS time samples: {len(t)}")

    return 0 if bool(well_init and converged) else 3


if __name__ == "__main__":
    raise SystemExit(main())
