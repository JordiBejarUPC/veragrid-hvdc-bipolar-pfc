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
