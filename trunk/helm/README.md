# MDHEM IEEE14 Artifact Notes

This directory contains a practical MDHEM artifact workflow for IEEE 14 built around VeraGrid objects.

The intended usage is:

1. build the artifact once from a `MultiCircuit`,
2. keep the polynomial coefficients as a persistent artifact,
3. query the artifact later with:
   - `P, Q` for PQ buses,
   - `P` for PV buses,
4. recover voltages and branch flows without running Newton-Raphson inside the query path.

## Important boundary

The artifact query path is MDHEM-only.

- `artifact.query(...)` does not call Newton-Raphson.
- `artifact.power_flow(...)` does not call Newton-Raphson.
- `mdhelm_power_flow(...)` does not call Newton-Raphson.

Newton-Raphson is allowed only in two optional contexts:

1. as an external validation reference in the fire tests and reports,
2. as an explicit training seed if you pass a converged `PowerFlowResults` object into `build_artifact_from_case(...)`.

If you do not pass a seed result, the builder uses its internal HELM germ path.

## Main file

[`mdhelm_pv_case14_query_artifact.py`](/home/santi/Git/eRoots/VeraGrid/trunk/helm/mdhelm_pv_case14_query_artifact.py)

This file contains:

- the artifact builder,
- the persistent `npz` save/load path,
- the query API,
- VeraGrid-like wrappers returning `PowerFlowResults`,
- coefficient getters so the trained mapping can be inspected or reused.

The main builder entry point is:

```python
case_data, artifact, germ_error = build_artifact_from_case(
    grid=grid,
    max_order=4,
    germ_seed_results=None,
)
```

The `germ_seed_results` input is optional.

- `None`: internal HELM germ solve.
- converged HELM `PowerFlowResults`: explicit HELM-centered artifact.
- converged NR `PowerFlowResults`: explicit NR-centered artifact.

The artifact exposes the stored coefficients through:

- `get_voltage_coefficients()`
- `get_reciprocal_voltage_coefficients()`
- `get_pv_reactive_power_coefficients()`
- `get_scheduled_basis()`
- `get_multi_index_alphas()`

## Query API

The closest VeraGrid-style entry points are:

```python
result = artifact.power_flow(
    grid=grid,
    pq_active_power=pq_active_power,
    pq_reactive_power=pq_reactive_power,
    pv_active_power=pv_active_power,
    tolerance=1e-5,
)
```

or:

```python
result = mdhelm_power_flow(
    grid=grid,
    artifact=artifact,
    pq_active_power=pq_active_power,
    pq_reactive_power=pq_reactive_power,
    pv_active_power=pv_active_power,
    tolerance=1e-5,
)
```

These return a VeraGrid `PowerFlowResults` object populated from the artifact evaluation.

## Validation scripts

[`mdhelm_pv_case14_fire_test.py`](/home/santi/Git/eRoots/VeraGrid/trunk/helm/mdhelm_pv_case14_fire_test.py)

- builds one artifact,
- generates several near-balanced scenarios,
- compares the artifact outputs against external Newton-Raphson.

Run it with:

```bash
python3 trunk/helm/mdhelm_pv_case14_fire_test.py
```

[`mdhelm_pv_case14_seed_options_report.py`](/home/santi/Git/eRoots/VeraGrid/trunk/helm/mdhelm_pv_case14_seed_options_report.py)

- builds three artifacts:
  - internal HELM germ,
  - explicit HELM seed,
  - explicit NR seed,
- evaluates all of them on the same scenario batch,
- writes a markdown report to:
  - `trunk/helm/mdhelm_pv_case14_seed_options_report.md`

Run it with:

```bash
python3 trunk/helm/mdhelm_pv_case14_seed_options_report.py
```

The report makes the distinction explicit:

- whether NR was used as a training seed,
- whether NR was used only as an external reference,
- how each artifact compares against NR on voltages and branch flows.

## Practical interpretation

If the internal HELM germ and the explicit HELM seed perform similarly to the explicit NR seed, then the artifact training is already robust without NR assistance.

If the explicit NR seed materially improves the worst-case mismatch, that means the local polynomial expansion is sensitive to the chosen germ and that the NR-centered artifact is a useful optional operating mode.
