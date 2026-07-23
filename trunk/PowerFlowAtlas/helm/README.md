# MDHEM

This directory is intentionally reduced to one library file and two example scripts:

- [`mdhelm.py`](mdhelm.py): the library
- [`example_ieee14_full.py`](example_ieee14_full.py): IEEE14 full-coefficient example with parity metrics
- [`example_activsg2000_tensor.py`](example_activsg2000_tensor.py): ACTIVSg2000 tensor-decomposed example with parity metrics

The MATPOWER case files stay beside them because the examples load them directly:

- `case14.matpower`
- `case_ACTIVSg2000.matpower`

## What each example does

`example_ieee14_full.py`

- builds or reloads a full MDHEM artifact with one independent dimension per `PQ_P`, `PQ_Q`, and `PV_P`
- generates deterministic random scenarios around the base case
- queries the artifact only
- runs Newton-Raphson only as an external reference
- prints worst-case metrics for voltage, branch flow, loading, and mismatch

Run it with:

```bash
python3 trunk/helm/example_ieee14_full.py --rebuild-artifact
```

`example_activsg2000_tensor.py`

- builds or reloads an order-2 compressed artifact
- compares `projected_bundle` and `directional_on_demand`
- keeps all full query dimensions in the public input space
- evaluates deterministic random scenarios against Newton-Raphson reference results
- prints the same parity metrics and reports the better large-case mode

Run it with:

```bash
python3 trunk/helm/example_activsg2000_tensor.py --mode auto --rebuild-artifact
```

## Rules of this setup

- No Newton-Raphson corrector is used in the artifact query path.
- Newton-Raphson is allowed only as:
  - an optional build seed,
  - an external metric reference.
- IEEE14 is the full-coefficient example.
- ACTIVSg2000 is the tensor-decomposed example.

## Main library entry points

Full coefficients:

- `build_artifact_from_case(...)`
- `MDHEMPVQueryArtifact`
- `save_query_artifact(...)`
- `load_query_artifact(...)`

Tensor decomposition on the large case:

- `build_order2_compressed_artifact_from_case(...)`
- `MDHEMOrder2CompressedArtifact`
- `save_order2_compressed_artifact(...)`
- `load_order2_compressed_artifact(...)`

Skipped: extra demos, reports, and experiment scripts. Add them back only if one of these three files stops being enough.
