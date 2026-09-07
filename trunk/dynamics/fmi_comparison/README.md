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

The RMS comparison runner executes VeraGrid and direct FMPy consumption against
the exact same generated FMU archive, then publishes its evidence atomically:

```text
python -m trunk.dynamics.fmi_comparison.run_rms_comparison \
  --output-dir <new-package-directory> \
  --source-revision <revision> \
  --source-tree-sha256 <lowercase-sha256>
```

The caller owns the revision and tree digest because the benchmark never invokes
Git or infers provenance. Generated FMUs, reports, tables, manifests, and plots
belong in caller-selected output directories and are not versioned in this
package.

The comparison is engineering evidence, not a certification claim. FMPy is the
independent public consumer used for the open-source baseline; the package
records that backend explicitly so the plots and tables cannot imply multiple
independent tools when only one was executed.

Product integration tests live under `src/tests/FMI` and deliberately use
their own fixtures. They must not import, invoke, or add this `trunk` package
to their import path.
