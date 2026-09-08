# FMI comparison

This package owns reproducible FMI examples and interoperability evidence. It is
kept under `trunk` because it is benchmark material, not part of the
`VeraGridEngine` runtime API.

The device runner exports and executes four native cases through the public
product interfaces:

- RMS FMI 2.0 Co-Simulation
- RMS FMI 2.0 Model Exchange
- EMT FMI 2.0 Co-Simulation
- EMT FMI 2.0 Model Exchange

Run it from the repository root in an environment where VeraGridEngine and
FMPy are installed:

```text
python -m trunk.dynamics.fmi_comparison.run_device_examples --output-dir <output-directory>
```

The RMS comparison runner executes VeraGrid, direct FMPy, and an independent
OMSimulator process against the exact same generated FMU archive for each mode.
It then publishes the complete evidence package atomically:

```text
python -m trunk.dynamics.fmi_comparison.run_rms_comparison \
  --output-dir <new-package-directory> \
  --source-revision <revision> \
  --source-tree-sha256 <lowercase-sha256> \
  --omsimulator-executable <absolute-path-to-OMSimulator.exe>
```

Schema v3 retains exactly 32 declared artifacts: the two combined comparison
CSVs, two direct-FMPy raw CSVs, six raw OMSimulator artifacts per mode,
one FMU and one RMS report per mode, and twelve fixed PDF/SVG/PNG figures.
The manifest writer and verifier remain local to this `trunk` benchmark package;
no manifest or manifest handler is part of `src` or the product runtime.

The caller owns the revision and tree digest because the benchmark never invokes
Git or infers provenance. Generated FMUs, reports, tables, manifests, and plots
belong in caller-selected output directories and are not versioned in this
package.

The RMS comparison applies a physical active-power step to a separate native
load. The event boundary is retained at 0.1 s with the old value and the first
post-event sample is 0.101 s. Both the Co-Simulation and Model Exchange FMUs
capture the actual initial voltage as `x(0)=u(0)`, retain `x'=0`, and express
the response through `u-x`; no network-specific initial voltage is hardcoded.
Direct FMPy replays the exact retained bus-voltage samples. The voltage response
first appears at 0.101 s. Model Exchange can expose direct feedthrough at that
sample; the causal Co-Simulation FMU consumes the new input over the following
communication interval and its P/Q response therefore appears at 0.102 s.
The package publishes raw overlaid trajectories plus separate
absolute-error figures as PDF, editable SVG, and 300 dpi PNG files. CSV rows and
the manifest retain the event phase, shared input, equations, response checks,
and per-sample acceptance budgets; the figures are not the acceptance oracle.

The comparison is engineering evidence, not a certification claim. FMPy is both
the direct public consumer and VeraGrid's FMI 2 runtime backend in this lane;
OMSimulator supplies the independent runtime path. The package records that
backend relationship, the exact process arguments, runtime identities, raw
input/output and logs, pairwise errors, and derived budgets. The result supports
an FMI 2 CS/ME orchestration and coupled-response claim for this retained
zero-derivative fixture on the recorded Windows host. It does not claim solver
accuracy, FMI-native internal time-event export, or cross-platform coverage.

Product integration tests live under `src/tests/FMI` and deliberately use
their own fixtures. They must not import, invoke, or add this `trunk` package
to their import path.
## Reference FMU corpus

reference_fmu_catalog.json pins the official Reference FMUs v0.0.41
BouncingBall and Stair models for FMI 2.0 and FMI 3.0. Each retained FMU
declares both Co-Simulation and Model Exchange. The catalog is a sealed
benchmark identity: changing its release, case order, hash, scalar type, event
oracle, or termination semantics requires a reviewed catalog revision.

The catalog loader validates strict JSON, portable archive paths, exact release
and asset identities, complete time lattices, event intervals, and cross-field
oracle invariants. Schema v2 owns a separate oracle for Co-Simulation and Model
Exchange because communication samples and solver-located roots are different
observations of the same FMU semantics. Asset validation reads one explicit
local `.fmu` once and
returns the exact immutable bytes whose size and SHA-256 match the selected
case. It does not download, extract, load, compile, or execute native code.

The maintained event evidence now covers three distinct mechanisms:

- the existing RMS prescribed input discontinuity;
- Stair time events, including Integer in FMI 2.0 and Int32 in FMI 3.0;
- BouncingBall state events, including the final zero velocity sustained from
  the last impact through the configured stop.

Stair ends because the FMU requests termination at 9 s. BouncingBall does not
request termination and instead reaches the configured stop at 3 s. Keeping
those causes separate prevents a matching final timestamp from concealing
different lifecycle behavior.

The FMU archives remain external evidence and are never committed by this
package. A caller obtains the exact upstream release separately and supplies
the selected file path to the validator. Loading the catalog or validating its
bytes is corpus-readiness evidence only: it is not an interoperability PASS,
platform-support claim, or FMI certification claim. Those conclusions require
the separately controlled execution and comparison runners.

## Reference FMU execution matrix

`run_reference_fmu_execution` executes exactly sixteen current-host Windows
x86_64 cells: four pinned Reference FMUs, both CS and ME interfaces, and both
FMPy and official `fmusim`. All inputs are explicit; the runner does not search
Git, `PATH`, environment variables, tools, or corpus files.

```text
python -m trunk.dynamics.fmi_comparison.run_reference_fmu_execution \
  --output-dir <new-package-directory> \
  --source-branch devel_dynamics_rebuild \
  --source-revision <40-character-commit> \
  --source-tree-sha256 <64-character-tree-digest> \
  --catalog-path <reference_fmu_catalog.json> \
  --corpus-root <extracted-Reference-FMUs-v0.0.41-root> \
  --fmpy-version 0.3.31 \
  --fmpy-distribution-sha256 39eb2d78370dd241001e5724734f79caf2afcaafc968ba8f93afc597a0337e85 \
  --fmusim-executable <absolute-path-to-fmusim.exe> \
  --fmusim-size-bytes 6743040 \
  --fmusim-sha256 e25529b1a52d441a2c9f284193ba135a418b66a5ef26cc82754bd479c98ba874 \
  --fmusim-version "fmusim 0.10.0"
```

Co-Simulation is accepted against the official CSV embedded in each FMU with
absolute and relative tolerances of `1e-9`. Model Exchange is accepted by
cross-checking FMPy and fmusim at `1e-6`, while each raw event trace must also
satisfy its independent catalog oracle. BouncingBall ME therefore validates
eleven analytically bounded state-event roots. Stair ME validates eight visible
counter transitions and the ninth termination boundary; the semantic counter
reaches 10, but public output ends with 9 before the terminating event can
serialize the new value.

The runner retains all raw rows, including duplicate or native event rows. Its
regular views select existing samples only: they never insert, interpolate, or
synthesize data. A successful run atomically publishes `manifest.json` and 32
artifacts under `raw/cell-00` through `raw/cell-15`: one `trace.csv` per cell,
plus `stdout.log` and `stderr.log` for each fmusim process. Runtime FMU and tool
copies are removed before publication. This package deliberately produces no
plots.

The resulting package is evidence only for execution of the exact Reference
FMUs v0.0.41 with FMPy 0.3.31 and fmusim 0.10.0 on the recorded host. It is not
evidence of VeraGrid runtime behavior, FMI 1 support, another operating system,
multiplatform support, or FMI certification.
