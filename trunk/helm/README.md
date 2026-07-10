# MDHEM in VeraGrid

This directory contains the current multidimensional holomorphic embedding workflow for AC power-flow artifacts in VeraGrid.

The intended workflow is simple:

1. load a MATPOWER case into a VeraGrid `MultiCircuit`,
2. build an MDHEM artifact once, offline,
3. save the artifact to `npz`,
4. query it later with:
   - `P, Q` for PQ buses,
   - `P` for PV buses,
5. recover bus voltages, PV reactive powers, scheduled powers and branch flows without running Newton-Raphson inside the query path.

The business logic now lives in [`mdhelm.py`](mdhelm.py). The other files in this directory are demos, reports, parity tests, and large-case experiments.

## What is implemented

There are three practical levels in this directory.

### 1. Full per-bus MDHEM artifact

Implemented in [`mdhelm.py`](mdhelm.py) through:

- `build_artifact_from_case(...)`
- `MDHEMPVQueryArtifact`
- `save_query_artifact(...)`
- `load_query_artifact(...)`

This is the direct "one variable per physical query input" artifact:

- one variable per `PQ_P`,
- one variable per `PQ_Q`,
- one variable per `PV_P`.

This is the cleanest API and the closest one to direct VeraGrid integration.

### 2. Order-2 compressed artifact

Implemented in [`mdhelm.py`](mdhelm.py) through:

- `build_order2_compressed_artifact_from_case(...)`
- `MDHEMOrder2CompressedArtifact`
- `save_order2_compressed_artifact(...)`
- `load_order2_compressed_artifact(...)`

This keeps the exact full linear map and only applies quadratic terms on a selected subset of dimensions.

It exists because the full multidimensional coefficient count grows combinatorially and becomes impossible on large grids at moderate orders.

### 3. Reduced-subspace large-grid artifact

Implemented separately in [`mdhelm_pv_activsg2000_local_artifact.py`](mdhelm_pv_activsg2000_local_artifact.py).

This is not the same object as the full per-bus artifact. It does not expose one independent variable per PQ/PV quantity. Instead it trains a low-dimensional local coordinate map around the germ. Right now this is the best-performing large-grid path in this directory for `case_ACTIVSg2000.matpower`.

## Hard boundary: no NR in the query path

This is the main behavioral rule of the implementation.

- `artifact.query(...)` does not call Newton-Raphson.
- `artifact.query_from_sbus(...)` does not call Newton-Raphson.
- `artifact.query_matrix(...)` does not call Newton-Raphson.
- `artifact.power_flow(...)` only converts the artifact answer into a VeraGrid `PowerFlowResults`.
- `mdhelm_power_flow(...)` only wraps the artifact answer into `PowerFlowResults`.

Newton-Raphson is allowed only in two optional roles:

1. as a training seed if you explicitly pass a converged `PowerFlowResults` into `build_artifact_from_case(...)` or `build_order2_compressed_artifact_from_case(...)`,
2. as an external validation reference in the parity and fire-test scripts.

If no seed is provided, the builder obtains the germ internally through the HELM-based path implemented in `mdhelm.py`.

## Theory

### From HELM to MDHEM

The paper in this folder,
`MDHEM-dimensional holomorphic embedding method to solve AC power flows.pdf`,
proposes an extension of HELM where the power-flow solution is written as a multivariate analytic expansion instead of a single-parameter expansion.

The core idea is:

- ordinary power flow is nonlinear in voltages,
- HELM rewrites the problem so the physical branch of the solution can be expanded as a holomorphic series around a known germ,
- MDHEM introduces several independent embedding variables instead of only one,
- each variable scales one physical input direction,
- the final result is an explicit multivariate map from the chosen inputs to bus voltages and PV reactive powers.

For this repository, the independent variables are chosen so that the public query API is expressed in physical powers:

- PQ active power,
- PQ reactive power,
- PV active power.

That choice is what makes the artifact easy to query later.

### Physical germ

The paper emphasizes the use of a physical germ instead of a trivial no-load white germ.

That matters here because the artifact is meant to be queried around an operating point that already looks like the real grid. In this implementation the germ is:

- a solved voltage vector,
- the corresponding scheduled complex power vector,
- the PV voltage targets taken from that solved operating point.

The builder computes that germ by either:

- solving it internally,
- or accepting a converged external `PowerFlowResults` as seed.

### Offline solve, online evaluation

MDHEM separates the work into two phases.

Offline phase:

- choose the input dimensions,
- build the multivariate coefficient table,
- solve the recursive coefficient equations order by order,
- store the coefficient tensors.

Online phase:

- convert the requested physical powers into local deviation coordinates,
- evaluate all required monomials,
- take dense products with the stored coefficient tensors,
- reconstruct voltages, PV reactive powers and branch flows.

That is the whole reason the artifact can be queried much faster than rerunning a nonlinear power-flow solve every time.

### Why PV buses need a Q series

The query API does not accept `Q` for PV buses. It accepts only `P` for PV buses and must still satisfy the PV voltage magnitude target.

So the artifact stores a separate multivariate series for PV reactive power. During query:

- the voltage series gives the complex bus voltages,
- the PV-Q series gives the reactive injection that keeps the PV buses on their voltage surface.

### Why the full query space explodes

Let:

- `D` = number of embedding dimensions,
- `K` = maximum total order.

Then the total number of multivariate coefficients up to order `K` is:

`C(D + K, K)`

That growth is the central practical limit of direct MDHEM.

Examples:

- order 1: linear in `D`,
- order 2: roughly `D^2 / 2`,
- order 4: roughly `D^4 / 24`.

For a large case, the dimension count is:

`D = 2 * n_pq + n_pv`

For `case_ACTIVSg2000.matpower`, that is large enough that:

- a full order-2 artifact is already heavy,
- a full order-4 per-bus artifact is not practical,
- the direct dense multi-index table can become completely infeasible in memory.

That is why this directory contains compressed and reduced-subspace variants in addition to the direct full artifact.

## Implementation in `mdhelm.py`

### 1. Grid extraction

`load_multicircuit_from_file(...)` loads the MATPOWER file into a VeraGrid `MultiCircuit`.

`create_mdhelm_inputs(...)` compiles the VeraGrid circuit into the numerical data needed by the solver:

- `Ybus`, `Yf`, `Yt`,
- bus partitions: slack, PQ, PV, non-slack,
- base injections,
- voltage setpoints,
- branch ratings and branch bus indices.

### 2. Basis construction

`build_query_basis(...)` builds the physical query basis used by the full artifact.

Each dimension is tagged with:

- kind: `PQ_P`, `PQ_Q`, or `PV_P`,
- full bus index,
- local non-slack index.

This basis is what connects a user query to the internal multivariate coordinates.

### 3. Physical germ solve

`solve_physical_germ(...)` computes the germ state used as the expansion point.

The code keeps that germ physical:

- the zero-order voltage coefficients equal the germ voltages,
- the zero-order PV reactive coefficients equal the germ PV reactive powers,
- the PV magnitude targets are aligned with the solved germ voltage magnitudes.

### 4. Multi-index compression

`MultiIndexTable` is the key internal structure.

Instead of storing every exponent operation in a naive dense recursive form, it stores compressed lookup arrays:

- order offsets,
- active dimensions per term,
- predecessor positions for `alpha - e_d`,
- proper sub-term pairs for convolutions.

This is what lets the code evaluate monomials and convolution sums without Python recursion in the hot path.

### 5. Coefficient recursion

`solve_mdhelm_query_artifact_from_basis(...)` performs the coefficient solve.

At each total order it:

- builds the known convolution terms from lower orders,
- assembles the right-hand side block,
- solves a sparse linear system with the same matrix for many right-hand sides,
- writes the new voltage, reciprocal-voltage and PV-Q coefficients.

The implementation uses one sparse LU factorization and reuses it across all coefficients of the artifact.

### 6. Artifact query

The online query path in `MDHEMPVQueryArtifact` is:

1. `build_deviation_vector(...)` or `build_deviation_matrix(...)`
2. `calculate_monomial_weights_from_table(...)` or the batch version
3. evaluate:
   - voltage coefficients,
   - PV-Q coefficients
4. `calculate_scheduled_power(...)` or `calculate_scheduled_power_matrix(...)`
5. compute:
   - `S = V * conj(Ybus * V)`,
   - mismatch,
   - PV voltage error,
   - branch flows and loading

The batch path is the same algorithm, just vectorized over scenarios.

### 7. Batch query API

The matrix API is implemented directly in `mdhelm.py` on both artifact classes:

- `split_sbus_input_matrix(...)`
- `build_deviation_matrix(...)`
- `evaluate_deviation_matrix(...)`
- `query_matrix(...)`
- `query_matrix_from_sbus(...)`

This is the right API if you want to query many scenarios at once.

The batch monomial evaluation and scheduled-power reconstruction are array-based, and the main per-scenario loops are passed through numba where it pays off.

### 8. Order-2 compressed artifact

`MDHEMOrder2CompressedArtifact` does not try to store the full quadratic map on every dimension.

Instead it does:

- exact full linear artifact,
- quadratic correction only on selected dimensions,
- full public query API identical in shape to the direct artifact.

That keeps the user-facing API simple while reducing offline storage and solve cost.

The tradeoff is obvious:

- better scalability than full dense order 2 or order 4,
- less accuracy away from the retained quadratic subspace.

## Public API

### Load a MATPOWER case

```python
from pathlib import Path
from mdhelm import load_multicircuit_from_file

case_path = Path("trunk/helm/case14.matpower")
grid = load_multicircuit_from_file(case_path)
```

### Build a full per-bus artifact

```python
from mdhelm import build_artifact_from_case

case_data, artifact, germ_error = build_artifact_from_case(
    grid=grid,
    max_order=2,
    germ_seed_results=None,
)
```

Arguments:

- `grid`: VeraGrid `MultiCircuit`
- `max_order`: maximum total multivariate order
- `germ_seed_results`: optional converged `PowerFlowResults`

Returns:

- `case_data`: extracted numerical case data
- `artifact`: `MDHEMPVQueryArtifact`
- `germ_error`: scalar germ residual/error summary

### Save and load the full artifact

```python
from pathlib import Path
from mdhelm import load_query_artifact
from mdhelm import save_query_artifact

artifact_path = Path("trunk/helm/mdhelm_pv_case14_query_artifact.npz")
save_query_artifact(path=artifact_path, artifact=artifact)
artifact = load_query_artifact(path=artifact_path)
```

### Scalar query with physical powers

```python
result = artifact.query(
    pq_active_power=pq_active_power,
    pq_reactive_power=pq_reactive_power,
    pv_active_power=pv_active_power,
    tolerance=1e-8,
)
```

Inputs:

- `pq_active_power`: shape `(n_pq,)`
- `pq_reactive_power`: shape `(n_pq,)`
- `pv_active_power`: shape `(n_pv,)`

Selected outputs on `result`:

- `result.voltage`
- `result.scheduled_power`
- `result.calculated_power`
- `result.pv_reactive_power`
- `result.mismatch_norm`
- `result.pv_voltage_error`
- `result.branch_from_power`
- `result.branch_to_power`
- `result.branch_loading`
- `result.branch_losses`

### Query from a full `Sbus`

```python
result = artifact.query_from_sbus(
    s_bus=s_bus,
    tolerance=1e-8,
)
```

Input:

- `s_bus`: shape `(n_bus,)`, complex per-unit bus powers

Internally this is split into:

- PQ `P`,
- PQ `Q`,
- PV `P`.

### Batch query

```python
batch_result = artifact.query_matrix(
    pq_active_power_matrix=pq_active_power_matrix,
    pq_reactive_power_matrix=pq_reactive_power_matrix,
    pv_active_power_matrix=pv_active_power_matrix,
    tolerance=1e-8,
)
```

Shapes:

- `pq_active_power_matrix`: `(n_scenarios, n_pq)`
- `pq_reactive_power_matrix`: `(n_scenarios, n_pq)`
- `pv_active_power_matrix`: `(n_scenarios, n_pv)`

Selected outputs:

- `batch_result.voltage`: `(n_scenarios, n_bus)`
- `batch_result.scheduled_power`: `(n_scenarios, n_bus)`
- `batch_result.calculated_power`: `(n_scenarios, n_bus)`
- `batch_result.pv_reactive_power`: `(n_scenarios, n_pv)`
- `batch_result.mismatch_norm`: `(n_scenarios,)`
- `batch_result.pv_voltage_error`: `(n_scenarios,)`
- `batch_result.converged_like`: `(n_scenarios,)`
- `batch_result.branch_from_power`: `(n_scenarios, n_branch)`

You can also query a batch of full `Sbus` vectors:

```python
batch_result = artifact.query_matrix_from_sbus(
    s_bus_matrix=s_bus_matrix,
    tolerance=1e-8,
)
```

### VeraGrid-style wrapper

```python
from mdhelm import mdhelm_power_flow

pf_results = mdhelm_power_flow(
    grid=grid,
    artifact=artifact,
    pq_active_power=pq_active_power,
    pq_reactive_power=pq_reactive_power,
    pv_active_power=pv_active_power,
    tolerance=1e-8,
)
```

This returns a VeraGrid `PowerFlowResults` object filled from the artifact answer.

### Build a compressed order-2 artifact

```python
from mdhelm import build_order2_compressed_artifact_from_case

case_data, compressed_artifact, germ_error = build_order2_compressed_artifact_from_case(
    grid=grid,
    retained_dimensions=8,
    germ_seed_results=None,
    reactive_score_weight=1.0,
)
```

Persistence:

```python
from pathlib import Path
from mdhelm import load_order2_compressed_artifact
from mdhelm import save_order2_compressed_artifact

artifact_path = Path("trunk/helm/case14_order2_compressed_artifact.npz")
save_order2_compressed_artifact(path=artifact_path, artifact=compressed_artifact)
compressed_artifact = load_order2_compressed_artifact(path=artifact_path)
```

Query shape is the same:

```python
result = compressed_artifact.query(
    pq_active_power=pq_active_power,
    pq_reactive_power=pq_reactive_power,
    pv_active_power=pv_active_power,
    tolerance=1e-8,
)

batch_result = compressed_artifact.query_matrix(
    pq_active_power_matrix=pq_active_power_matrix,
    pq_reactive_power_matrix=pq_reactive_power_matrix,
    pv_active_power_matrix=pv_active_power_matrix,
    tolerance=1e-8,
)
```

## What the coefficients mean

The full artifact stores:

- voltage coefficients,
- reciprocal-voltage coefficients,
- PV reactive-power coefficients,
- the physical query basis,
- the compressed multi-index table.

You can inspect them through:

- `artifact.get_voltage_coefficients()`
- `artifact.get_reciprocal_voltage_coefficients()`
- `artifact.get_pv_reactive_power_coefficients()`
- `artifact.get_scheduled_basis()`
- `artifact.get_multi_index_alphas()`

That is the artifact you would keep if your goal is:

"train once, then repeatedly map physical power injections to power-flow states".

## Which script to run

### Small case demo

[`mdhelm_pv_case14_query_artifact.py`](mdhelm_pv_case14_query_artifact.py)

Builds, saves, loads and queries the IEEE 14-bus artifact.

```bash
python3 trunk/helm/mdhelm_pv_case14_query_artifact.py
```

### Seed comparison report

[`mdhelm_pv_case14_seed_options_report.py`](mdhelm_pv_case14_seed_options_report.py)

Compares:

- internal HELM germ,
- explicit HELM seed,
- explicit NR seed.

```bash
python3 trunk/helm/mdhelm_pv_case14_seed_options_report.py
```

### Fire test against NR

[`mdhelm_pv_case14_fire_test.py`](mdhelm_pv_case14_fire_test.py)

Generates near-balanced scenarios and compares the artifact against Newton-Raphson.

```bash
python3 trunk/helm/mdhelm_pv_case14_fire_test.py
```

### ACTIVSg2000 current best parity path

[`mdhelm_pv_activsg2000_parity_test.py`](mdhelm_pv_activsg2000_parity_test.py)

This tests the current best large-case path in this directory, which is the reduced balanced-subspace artifact from `mdhelm_pv_activsg2000_local_artifact.py`.

```bash
python3 trunk/helm/mdhelm_pv_activsg2000_parity_test.py
```

## Current numerical status

### Full per-bus artifact

This is the clean API and the one now directly supported in `mdhelm.py`, including batch query.

It is appropriate for:

- small and moderate cases,
- low order,
- cases where you truly need one explicit variable per physical PQ/PV query quantity.

### Order-2 compressed artifact

This is the direct fallback when the full per-bus artifact starts to grow too fast.

Current report in this directory:

- file: `case_ACTIVSg2000_order2_compressed_report.md`
- retained dimensions: `8`
- base scenario passes
- one random test scenario shows noticeably larger error:
  - worst voltage diff `5.447419e-03` p.u.
  - worst branch flow diff `4.187224e+01` MVA

So the current order-2 compressed path is useful as an experiment, but not yet the best large-grid path here.

### Reduced-subspace ACTIVSg2000 path

Current report in this directory:

- file: `case_ACTIVSg2000_parity_test_report.md`
- model: reduced balanced-subspace artifact
- reduced dimensions: `6`
- max order: `4`
- passed scenarios: `80 / 100`
- P95 voltage diff: `3.496912e-04` p.u.
- P95 branch flow diff: `8.808183e-01` MVA
- P95 loading diff: `2.570726e-03`

This is why the large-case scripts currently favor the reduced-subspace artifact instead of the full per-bus artifact or the order-2 compressed artifact.

## Practical guidance

If your priority is:

### "I want the cleanest API"

Use the full `MDHEMPVQueryArtifact` from `mdhelm.py`.

You get:

- one variable per `PQ_P`,
- one variable per `PQ_Q`,
- one variable per `PV_P`,
- scalar query,
- full `Sbus` query,
- batch query.

### "I want something larger than IEEE14 but still per-bus-like"

Use the order-2 compressed artifact, but treat it as a compromise, not a final answer.

### "I want the best current ACTIVSg2000 behavior in this folder"

Use the reduced-subspace artifact scripts, because that is the path that currently has the best measured NR parity on that case.

## Minimal examples

### One-scenario query

```python
from pathlib import Path
import numpy as np

from mdhelm import build_artifact_from_case
from mdhelm import load_multicircuit_from_file

grid = load_multicircuit_from_file(Path("trunk/helm/case14.matpower"))
case_data, artifact, germ_error = build_artifact_from_case(grid=grid, max_order=2)

pq_p = np.asarray(case_data.base_power[case_data.pq].real, dtype=np.float64)
pq_q = np.asarray(case_data.base_power[case_data.pq].imag, dtype=np.float64)
pv_p = np.asarray(case_data.base_power[case_data.pv].real, dtype=np.float64)

result = artifact.query(
    pq_active_power=pq_p,
    pq_reactive_power=pq_q,
    pv_active_power=pv_p,
    tolerance=1e-8,
)

print(result.mismatch_norm)
print(result.voltage)
```

### Many-scenario query

```python
from pathlib import Path
import numpy as np

from mdhelm import build_artifact_from_case
from mdhelm import load_multicircuit_from_file

grid = load_multicircuit_from_file(Path("trunk/helm/case14.matpower"))
case_data, artifact, germ_error = build_artifact_from_case(grid=grid, max_order=2)

pq_p = np.asarray(case_data.base_power[case_data.pq].real, dtype=np.float64)
pq_q = np.asarray(case_data.base_power[case_data.pq].imag, dtype=np.float64)
pv_p = np.asarray(case_data.base_power[case_data.pv].real, dtype=np.float64)

pq_p_batch = np.vstack((pq_p, pq_p * 1.02))
pq_q_batch = np.vstack((pq_q, pq_q * 0.98))
pv_p_batch = np.vstack((pv_p, pv_p * 1.01))

batch = artifact.query_matrix(
    pq_active_power_matrix=pq_p_batch,
    pq_reactive_power_matrix=pq_q_batch,
    pv_active_power_matrix=pv_p_batch,
    tolerance=1e-8,
)

print(batch.mismatch_norm)
print(batch.voltage.shape)
```

## References

- Chengxi Liu, Bin Wang, Xin Xu, Kai Sun, Di Shi, Claus Leth Bak, `A Multi-Dimensional Holomorphic Embedding Method to Solve AC Power Flows`, IEEE Access, 2017.
- Local copy in this directory: `MDHEM-dimensional holomorphic embedding method to solve AC power flows.pdf`
- Base VeraGrid HELM implementation used as context: `src/VeraGridEngine/Simulations/PowerFlow/NumericalMethods/helm_power_flow.py`
