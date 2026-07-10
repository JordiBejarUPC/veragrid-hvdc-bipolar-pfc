# VeraGrid Certified Power-Flow Atlas

This package implements a first production-oriented slice of a **power-flow atlas** using VeraGrid as the authoritative grid engine.

It does not train a global black-box regressor. For a fixed compiled network state, it stores a set of local analytic charts around solved operating points. A query is evaluated by generating a one-dimensional voltage series in the requested injection direction, evaluating it with a polynomial or Padé approximant, and certifying the returned voltage against the original AC equations.

The result is either:

- a certified analytic solution;
- a solution certified after a bounded VeraGrid Newton correction;
- an explicit full VeraGrid fallback result;
- or an explicit failure/status indicating that the artifact is not valid for the query.

## Implemented scope

The current implementation supports:

- fixed AC topology and fixed admittance state;
- constant-power nodal injections;
- classical slack, PV, and PQ bus regimes;
- multiple local PV/PQ active-set patches for the same `Ybus`;
- exact terminal branch currents and powers from the compiled VeraGrid `Yf` and `Yt` matrices;
- sparse CSC rectangular Jacobians;
- one reusable sparse LU factorization per patch;
- directional quadratic voltage-series generation;
- polynomial and Padé evaluation;
- exact AC residual verification;
- PV reactive-limit verification;
- bounded correction through VeraGrid's `PfBasicFormulation` and Newton solver;
- full `multi_island_pf_nc()` fallback;
- portable persistence of all sparse matrices and patch data.

The current implementation deliberately does **not** approximate:

- ZIP current or admittance injections;
- VSC or HVDC equations;
- active transformer module/phase controls;
- remote-voltage or other generalized control equations;
- a change in topology, tap state, switched-shunt state, branch decomposition, or bus order;
- variable PV voltage setpoints inside one patch.

Those states must use another atlas artifact or VeraGrid's full solver. This is a safety boundary, not a missing warning.

## Mathematical representation

For a fixed control regime, the rectangular AC equations are written as

\[
F(x,u)=0,
\]

where `x` contains the real and imaginary voltages of all non-slack buses and `u` contains the specified active and reactive injections.

Around an exact anchor `(x0, u0)`, the query follows

\[
u(t)=u_0+t\Delta u,
\qquad
x(t)=x_0+\sum_{k=1}^{M}x_k t^k.
\]

Because the rectangular constant-power equations are quadratic, every higher-order coefficient is obtained from already-known lower-order coefficients:

\[
J_0x_1=\Delta u,
\]

\[
J_0x_k=-\sum_{i=1}^{k-1}\mathcal{B}(x_i,x_{k-i}),
\qquad k\geq2.
\]

`J0` is factorized once per patch. Every query reuses that factorization for all series orders.

The fixed-regime equation order is:

1. active-power equations at all non-slack buses;
2. reactive-power equations at PQ buses;
3. squared-voltage equations at PV buses.

The final voltage is never accepted solely because a series was evaluated. The exact mismatch

\[
V\odot\overline{Y_{bus}V}-S_{target}
\]

is reconstructed and checked in the applicable equation rows. PV reactive outputs are separately checked against their stored nodal limits.

## Package structure

```text
power_flow_atlas/
    branch_flows.py          Exact Yf/Yt terminal-flow reconstruction
    builder.py               Patch and atlas construction
    enumerations.py          Explicit build/query/storage states
    model.py                 Light immutable-size data objects
    options.py               Typed options with explicit getters/setters
    rectangular_series.py    Jacobian, recurrence, Padé, residuals, signatures
    selector.py              Sensitivity-scaled patch selection
    storage.py               Portable CSC persistence and LU reconstruction
    veragrid_integration.py  VeraGrid offline builder and online engine

examples/
    build_and_query_atlas.py

tests/
    run_core_tests.py
```

## Dependencies

No dependency installer is included. The implementation uses only dependencies already required by this design:

- NumPy;
- SciPy;
- VeraGridEngine for the native integration module.

The numerical core and its tests can run without importing VeraGridEngine. The module `veragrid_integration.py` requires VeraGridEngine.

The adapter was written against the current VeraGrid 6.3.x API layout, including:

- `NumericalCircuit`;
- `compile_numerical_circuit_at()`;
- `PowerFlowOptions`;
- `PowerFlowResults` and `NumericPowerFlowResults`;
- `PfBasicFormulation`;
- `newton_raphson_fx()`;
- `multi_island_pf_nc()`.

## Offline construction

An atlas is built from a matrix of complex nodal injection scenarios in VeraGrid bus order.

Sign convention:

- positive real power means net generation;
- negative real power means net demand;
- positive reactive power means net reactive injection;
- negative reactive power means net reactive demand.

The scenario matrix has shape:

```text
(number_of_scenarios, numerical_circuit.nbus)
```

The builder solves every row with VeraGrid. The previous converged voltage is passed as the next initial guess, so ordering scenarios as a continuation path is advantageous.

For this scenario-matrix constructor, `control_q` must be `False`. The current VeraGrid `PowerFlowResults` object does not reliably expose the solver-final PV/PQ active set after reactive-limit switching. Freezing bus types prevents a solved PQ-limited point from being stored incorrectly as a PV chart. Active-set-specific charts remain supported through `build_from_power_flow_results(...)` when the supplied `bus_types` array is authoritative for the solved regime. Online full-solver fallback may still use `control_q=True`.

```python
from pathlib import Path

import numpy as np
import VeraGridEngine as vg
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

from power_flow_atlas.model import AtlasBuildResult, PowerFlowAtlas
from power_flow_atlas.options import PowerFlowAtlasOptions
from power_flow_atlas.storage import save_power_flow_atlas
from power_flow_atlas.veragrid_integration import VeraGridPowerFlowAtlasBuilder


grid_path: Path = Path("case118.m")
artifact_path: Path = Path("case118_atlas")
logger: vg.Logger = vg.Logger()
grid: vg.MultiCircuit = vg.open_file(filename=str(grid_path))

power_flow_options: vg.PowerFlowOptions = vg.PowerFlowOptions(
    solver_type=vg.SolverType.NR,
    retry_with_other_methods=True,
    tolerance=1.0e-10,
    control_q=False,
    control_taps_phase=False,
    control_taps_modules=False,
    verbose=0,
)

numerical_circuit = compile_numerical_circuit_at(
    circuit=grid,
    t_idx=None,
    logger=logger,
)

scenario_s_mva: np.ndarray = np.empty(
    (scenario_count, numerical_circuit.nbus),
    dtype=np.complex128,
)
# Fill every row explicitly from historical, forecast, OPF, or continuation cases.

atlas_options: PowerFlowAtlasOptions = PowerFlowAtlasOptions(
    series_order=10,
    series_tolerance=1.0e-9,
    newton_tolerance=1.0e-11,
    maximum_newton_iterations=3,
    validity_radius=0.20,
)

builder: VeraGridPowerFlowAtlasBuilder = VeraGridPowerFlowAtlasBuilder(
    numerical_circuit=numerical_circuit,
    atlas_options=atlas_options,
    logger=logger,
)

build_result: AtlasBuildResult = builder.build_from_injection_scenarios(
    scenario_s_mva=scenario_s_mva,
    power_flow_options=power_flow_options,
)
atlas: PowerFlowAtlas | None = build_result.get_atlas()

if atlas is not None:
    save_power_flow_atlas(
        directory_path=artifact_path,
        atlas=atlas,
    )
else:
    print(build_result.get_status(), build_result.get_message())
```

The complete editable example is in `examples/build_and_query_atlas.py`.

## Online evaluation

```python
from pathlib import Path

import numpy as np
import VeraGridEngine as vg
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

from power_flow_atlas.branch_flows import (
    AtlasBranchFlowResult,
    calculate_branch_flows,
)
from power_flow_atlas.model import AtlasStorageResult, PowerFlowAtlas
from power_flow_atlas.options import PowerFlowAtlasOptions
from power_flow_atlas.storage import load_power_flow_atlas
from power_flow_atlas.veragrid_integration import (
    VeraGridAtlasQueryResult,
    VeraGridPowerFlowAtlasEngine,
)


artifact_path: Path = Path("case118_atlas")
load_result: AtlasStorageResult = load_power_flow_atlas(
    directory_path=artifact_path,
)
atlas: PowerFlowAtlas | None = load_result.get_atlas()

if atlas is not None:
    grid = vg.open_file(filename="case118.m")
    logger: vg.Logger = vg.Logger()
    numerical_circuit = compile_numerical_circuit_at(
        circuit=grid,
        t_idx=None,
        logger=logger,
    )
    power_flow_options: vg.PowerFlowOptions = vg.PowerFlowOptions(
        solver_type=vg.SolverType.NR,
        tolerance=1.0e-10,
        control_q=True,
        control_taps_phase=False,
        control_taps_modules=False,
        verbose=0,
    )
    atlas_options: PowerFlowAtlasOptions = PowerFlowAtlasOptions()
    engine: VeraGridPowerFlowAtlasEngine = VeraGridPowerFlowAtlasEngine(
        numerical_circuit=numerical_circuit,
        atlas=atlas,
        atlas_options=atlas_options,
        power_flow_options=power_flow_options,
        logger=logger,
    )

    target_s_mva: np.ndarray = np.empty(
        numerical_circuit.nbus,
        dtype=np.complex128,
    )
    # Fill target_s_mva in the same compiled bus order.

    query_result: VeraGridAtlasQueryResult = engine.query_mva(
        target_s_mva=target_s_mva,
    )
    voltage: np.ndarray = query_result.get_voltage()
    flow_result: AtlasBranchFlowResult = calculate_branch_flows(
        atlas=atlas,
        voltage=voltage,
    )

    print(query_result.get_status())
    print(query_result.get_residual_norm())
    print(voltage)
    print(flow_result.get_from_power_mva())
    print(flow_result.get_to_power_mva())
else:
    print(load_result.get_status(), load_result.get_message())
```

The returned native VeraGrid objects are also available:

- `get_numeric_results()` for certified series or bounded-Newton results;
- `get_power_flow_results()` for a full VeraGrid fallback.

## Query statuses

`CertifiedSeries`
: The directional series is inside the patch radius, satisfies the exact residual tolerance, and respects the stored PV reactive limits.

`CertifiedNewton`
: The series was used as an initial state and a bounded VeraGrid Newton correction produced a certified result.

`FullPowerFlowFallback`
: The chart could not be certified, so VeraGrid's full multi-island solver was executed.

`OutsideAtlas`
: The query is outside the selected chart and full fallback is disabled.

`RegimeMismatch`
: The selected PV/PQ regime violates its reactive limits and full fallback is disabled.

`Failed`
: The model, topology signature, input, stored limits, series evaluation, or fallback is invalid.

## Artifact consistency checks

The persisted topology signature includes:

- system base power;
- the complete CSC `Ybus` data and index structure;
- the complete CSC `Yf` and `Yt` data and index structures;
- branch from/to terminal ordering.

At query time the engine additionally checks:

- injection-vector size and finite values;
- zero ZIP current injections;
- zero ZIP admittance injections;
- absence of VSC and HVDC devices in the analytic path;
- absence of active branch-control equations;
- equality of runtime and stored nodal reactive limits.

The sparse `SuperLU` object is never serialized. Each stored CSC Jacobian is factorized again during loading, avoiding a non-portable dependency on Python, SciPy, operating system, and processor-specific internals.

## Scenario design

A useful artifact depends more on anchor placement than on raw scenario count. A production scenario set should combine:

- historical operating snapshots;
- forecast samples;
- OPF dispatch samples;
- regional load, wind, solar, hydro, and interchange factors;
- continuation trajectories toward stressed states;
- points immediately before and after PV-to-PQ transitions;
- targeted samples in high-curvature injection directions;
- samples generated from recurrent online fallback cases.

Do not uniformly sample every nodal injection independently. That space is unnecessarily large and mostly physically irrelevant.

A practical enrichment loop is:

1. build an initial atlas from historical and planned scenarios;
2. run unseen validation scenarios through the engine;
3. retain every fallback or high-residual query;
4. solve those points with VeraGrid;
5. add new anchors only where they improve validation coverage;
6. recalibrate the patch validity radius from observed certification results.

## Tests

`tests/run_core_tests.py` currently verifies:

- the analytic rectangular CSC Jacobian against central finite differences;
- the directional Padé series against an independent rectangular Newton solve;
- exact fixed-regime residual certification;
- storage/load reconstruction of sparse matrices and LU factors;
- topology-signature preservation;
- exact nodal balance from reconstructed terminal branch powers;
- option validation and safe defaults.

In the supplied build environment, these core tests pass.

The VeraGrid adapter could not be executed in the supplied build environment because VeraGridEngine is not installed there. Its imports and calls were aligned against the current public VeraGrid source tree, but it must be run against the exact eRoots VeraGrid branch before merge because internal APIs can change.

## Immediate integration work inside VeraGrid

Before merging this into the VeraGrid repository, the recommended steps are:

1. place `power_flow_atlas` under the appropriate VeraGrid simulation package;
2. update imports to the final repository module path;
3. add native VeraGrid test grids for Slack/PQ, Slack/PV/PQ, multiple islands, and Q-limit transitions;
4. compare every result field against `PowerFlowDriver`, not only voltage;
5. add performance benchmarks for patch selection, coefficient generation, post-processing, bounded correction, and full fallback;
6. define an explicit version field tying each artifact to the VeraGrid numerical-model schema;
7. add one artifact per topology/admittance state, or extend the container to dispatch among multiple topology-specific atlases.

