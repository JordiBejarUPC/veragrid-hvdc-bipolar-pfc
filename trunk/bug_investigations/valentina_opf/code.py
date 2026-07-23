from __future__ import annotations

from pathlib import Path

import numpy as np

from VeraGridEngine.api import (
    EngineType,
    FileOpen,
    MIPSolvers,
    OpfDispatchMode,
    OptimalPowerFlowOptions,
    OptimalPowerFlowTimeSeriesDriver,
    PowerFlowOptions,
    SolverType,
    TimeGrouping,
)


CASE_PATH = Path(__file__).with_name("New.England_solar_case_OPF.gridcal")
LOAD_COST = 12000.0
GEN_COSTS = {
    "Gen 04": 40.0,
    "Gen 05": 80.0,
}
GEN_LIMITS = {
    "Gen 04": {"ramp_up": 18.0, "ramp_down": 18.0, "min_time_up": 24.0, "min_time_down": 24.0},
    "Gen 05": {"ramp_up": 200.0, "ramp_down": 200.0, "min_time_up": 2.0, "min_time_down": 2.0},
}
EPS = 1e-6


def _flat_profile(value: float, nt: int) -> np.ndarray:
    return np.full(nt, value, dtype=float)


def configure_case():
    grid = FileOpen(str(CASE_PATH)).open()
    time_indices = np.array(grid.get_all_time_indices(), dtype=int)
    nt = len(time_indices)

    for gen in grid.get_generators():
        if gen.name in GEN_COSTS:
            gen.Cost = GEN_COSTS[gen.name]
            gen.Cost_prof = _flat_profile(GEN_COSTS[gen.name], nt)
        if gen.name in GEN_LIMITS:
            limits = GEN_LIMITS[gen.name]
            gen.ramp_up = limits["ramp_up"]
            gen.ramp_down = limits["ramp_down"]
            gen.min_time_up = limits["min_time_up"]
            gen.min_time_down = limits["min_time_down"]

    for load in grid.get_loads():
        load.Cost = LOAD_COST
        load.Cost_prof = _flat_profile(LOAD_COST, nt)

    return grid, time_indices


def run_case():
    grid, time_indices = configure_case()
    options = OptimalPowerFlowOptions(
        solver=SolverType.LINEAR_OPF,
        dispatch_mode=OpfDispatchMode.Normal,
        time_grouping=TimeGrouping.NoGrouping,
        mip_solver=MIPSolvers.HIGHS,
        power_flow_options=PowerFlowOptions(),
        consider_ramps=True,
        consider_time_up_down=True,
    )
    driver = OptimalPowerFlowTimeSeriesDriver(
        grid=grid,
        options=options,
        time_indices=time_indices,
        engine=EngineType.VeraGrid,
    )
    driver.run()
    return grid, time_indices, driver


def collect_ramp_violations(driver):
    gen_names = list(driver.results.generator_names)
    power = np.asarray(driver.results.generator_power, dtype=float)
    time_array = np.asarray(driver.results.time_array)
    violations = []

    for gen_name, limits in GEN_LIMITS.items():
        idx = gen_names.index(gen_name)
        ramp_up = limits["ramp_up"]
        ramp_down = limits["ramp_down"]

        for t in range(1, power.shape[0]):
            delta = power[t, idx] - power[t - 1, idx]
            if delta > ramp_up + EPS:
                violations.append((gen_name, "up", str(time_array[t]), float(delta), ramp_up))
            if -delta > ramp_down + EPS:
                violations.append((gen_name, "down", str(time_array[t]), float(-delta), ramp_down))

    return violations


def collect_load_shedding(driver):
    load_names = list(driver.results.load_names)
    shedding = np.asarray(driver.results.load_shedding, dtype=float)
    time_array = np.asarray(driver.results.time_array)
    events = []

    nz_t, nz_l = np.nonzero(shedding > EPS)
    for t, l in zip(nz_t, nz_l):
        events.append((str(time_array[t]), load_names[l], float(shedding[t, l])))

    return events


def main():
    _, _, driver = run_case()

    ramp_violations = collect_ramp_violations(driver)
    load_shedding_events = collect_load_shedding(driver)

    print(f"acceptable_solution={driver.results.converged.all()}")
    print(f"ramp_violations={len(ramp_violations)}")
    for gen_name, direction, when, actual, limit in ramp_violations[:20]:
        print(
            f"RAMP VIOLATION gen={gen_name} dir={direction} time={when} "
            f"actual_delta={actual:.6f} limit={limit:.6f}"
        )

    print(f"load_shedding_events={len(load_shedding_events)}")
    for when, load_name, mw in load_shedding_events[:20]:
        print(f"LOAD SHEDDING time={when} load={load_name} mw={mw:.6f}")

    assert not ramp_violations, "Ramp-limit violations should be fixed for Valentina's case."
    if not load_shedding_events:
        print("No load shedding reproduced with this scripted setup.")


if __name__ == "__main__":
    main()
