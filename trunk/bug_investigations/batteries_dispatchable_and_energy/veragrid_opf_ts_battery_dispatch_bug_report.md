# VeraGrid Linear OPF TS Bug Report

## Summary

There is a source-code bug in the linear OPF time-series formulation for batteries when a battery switches between `dispatchable=True` and `dispatchable=False` across consecutive time steps.

In the investigated model:

- File: `/home/santi/Descargas/SimulacionSantaLucia_fixed.veragrid`
- Study: linear OPF time series
- Dispatch mode: `Normal`

The full horizon becomes infeasible, but the root cause is not network adequacy. The problem is that the battery energy state is not created or propagated for non-dispatchable batteries, and then the next dispatchable step tries to use a missing previous energy state.

## Reproduction

### Model

Use:

- `/home/santi/Descargas/SimulacionSantaLucia_fixed.veragrid`

This is the same as the original `SimulacionSantaLucia.veragrid`, except the negative generator `Pmax_prof` values at `t=0` were clamped to `0.0`.

### Repro command

```bash
PYTHONPATH=/home/santi/Git/eRoots/VeraGrid/src python3 - <<'PY'
import numpy as np
from VeraGridEngine.api import FileOpen, OptimalPowerFlowOptions, SolverType, PowerFlowOptions, TimeGrouping, MIPSolvers, MIPFramework, OpfDispatchMode
from VeraGridEngine.Simulations.OPF.opf_ts_driver import OptimalPowerFlowTimeSeriesDriver

path='/home/santi/Descargas/SimulacionSantaLucia_fixed.veragrid'
grid = FileOpen(path).open()
options = OptimalPowerFlowOptions(
    verbose=0,
    dispatch_mode=OpfDispatchMode.Normal,
    solver=SolverType.LINEAR_OPF,
    power_flow_options=PowerFlowOptions(),
    time_grouping=TimeGrouping.NoGrouping,
    mip_solver=MIPSolvers.HIGHS,
    mip_framework=MIPFramework.PuLP,
)
drv = OptimalPowerFlowTimeSeriesDriver(
    grid=grid,
    options=options,
    time_indices=grid.get_all_time_indices(),
)
drv.run()
print('errors', drv.logger.error_count())
print('converged', bool(np.all(drv.results.converged)))
PY
```

Expected current behavior:

- full 288-step run fails
- shorter prefixes solve

### Boundary of failure

By binary search on the horizon length:

- last good horizon: `286`
- first bad horizon: `287`

So the failure is triggered when adding time index `286` after a problematic state at `285`.

## Critical model fact

Battery `batt@Bus 1` has a one-step dispatchability event:

- default `enabled_dispatch=True`
- `enabled_dispatch_prof[285] = false`
- then returns to `true` at `286`

Extracted from the model:

```json
{
  "is_sparse": true,
  "size": 288,
  "default": true,
  "sparse_data": {
    "map": {
      "285": false
    }
  }
}
```

## Root cause

The bug is in:

- `/home/santi/Git/eRoots/VeraGrid/src/VeraGridEngine/Simulations/OPF/Formulations/linear_opf_ts.py`

### Dispatchable branch

When `batt_data_t.dispatchable[k]` is true, the formulation creates:

- `batt_vars.e[t, k]`
- energy bounds
- intertemporal energy balance

Relevant lines:

- energy var creation near `1913`
- recursive energy constraint near `1919`
- initial energy constraint near `1925`

### Non-dispatchable branch

When `batt_data_t.dispatchable[k]` is false, the formulation switches to the branch starting near `1930`.

That branch:

- formulates fixed battery power with optional shedding
- does **not** create `batt_vars.e[t, k]`
- does **not** propagate battery energy state

### Consequence

At `t=285`, `batt@Bus 1` is non-dispatchable, so `batt_vars.e[285, 0]` is never created.

At `t=286`, the same battery is dispatchable again, so the code enters:

```python
batt_vars.e[t, k] == batt_vars.e[t - 1, k] + ...
```

But `batt_vars.e[285, 0]` was never assigned as an LP variable. In practice:

- the previous energy state is effectively missing
- the extracted solution shows `0.0` for that previous state
- the next step becomes infeasible because compiled battery bounds still require:
  - `e_min = 4.0 MWh`
  - `e_max = 39.6 MWh`

## Evidence collected

### Compiled battery data is correct

At `t=285` and `t=286`, the compiled circuit still has:

- `e_min = [4.0, 12.0]`
- `e_max = [39.6, 39.6]`

So this is not a compiler-data issue for `e_min/e_max`.

### LP variable presence

For a 286-step solve:

- `batt_e_284_0` exists
- `batt_e_285_0` does **not** exist
- `batt_e_285_1` exists

This proves battery 0 drops out of the energy-state formulation exactly at the non-dispatchable step.

### Isolating the cause

For the first bad horizon (`287` steps):

- as-is: infeasible
- disable batteries: feasible
- disable remote generators: still infeasible

So the storage formulation is the decisive cause of infeasibility.

## What another Codex should fix

### Required behavior

Battery energy state must remain well-defined across time even if `enabled_dispatch` changes.

The formulation must support:

- dispatchable at `t-1`, non-dispatchable at `t`
- non-dispatchable at `t-1`, dispatchable at `t`
- non-dispatchable for any contiguous interval

### Likely fix direction

In `add_linear_battery_formulation()`:

1. Always create `batt_vars.e[t, k]` for active batteries, regardless of dispatchability.
2. Always apply energy bounds and energy transition.
3. For the non-dispatchable branch, use the fixed battery power `p` in the energy update instead of skipping the energy state.
4. Make sure the next step can always reference a valid `batt_vars.e[t - 1, k]`.

### Practical design target

The non-dispatchable branch should still preserve:

- fixed power behavior
- optional shedding behavior if intended

But it must also preserve:

- battery state of charge continuity
- valid energy bounds at every time step

## Suggested verification after fix

### Primary regression

Run the full 288-step linear OPF time series on:

- `/home/santi/Descargas/SimulacionSantaLucia_fixed.veragrid`

with:

- `dispatch_mode = Normal`
- `solver = Linear OPF`

Expected:

- no infeasibility
- no missing battery energy state when dispatchability toggles

### Targeted assertions

For this case:

- `batt_vars.e[285, 0]` must exist
- `batt_vars.e[286, 0]` must be computed from a valid previous state
- energy should never drop below `4.0 MWh` for `batt@Bus 1`

### Recommended unit test

Add a small synthetic test with:

- one battery
- known `Enom`, `min_soc`, `max_soc`
- `enabled_dispatch_prof` flipping `True -> False -> True`
- nonzero battery power profile during the non-dispatchable step

Assertions:

- model remains feasible
- battery energy state exists at every step
- final energy matches the expected recurrence

## Secondary note

The original `.veragrid` also had negative generator `Pmax_prof` values at `t=0`. That was a separate data issue affecting nonlinear OPF at the first snapshot, not the source-code bug described here.
