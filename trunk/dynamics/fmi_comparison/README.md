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

## OpenModelica SMIB dynamic comparison

`run_smib_comparison` builds the maintained Modelica single-machine infinite-bus
plant with OpenModelica, exports one FMI 2.0 Co-Simulation archive, and executes
that exact archive through VeraGrid, direct FMPy, and OMSimulator. OpenModelica's
native DASSL result is retained as the independent model-fidelity reference.

All executable paths, versions, sizes, and SHA-256 identities are explicit
arguments. The runner does not search `PATH` or mutate the process environment.
It uses a 4 s horizon, a 0.002 s retained output grid, fault boundaries at
1.001 s and 1.151 s, and a 0.000125 s communication step for the three FMU
runtimes. A separate five-level VeraGrid refinement study uses steps from
0.002 s down to 0.000125 s.

```text
python -m trunk.dynamics.fmi_comparison.run_smib_comparison \
  --source-path <smib_network_plant.mo> \
  --source-size-bytes <bytes> \
  --source-sha256 <lowercase-sha256> \
  --omc-executable <absolute-path-to-omc.exe> \
  --omc-version <exact-version> \
  --omc-size-bytes <bytes> \
  --omc-sha256 <lowercase-sha256> \
  --build-output-dir <new-build-package-directory> \
  --omsimulator-executable <absolute-path-to-OMSimulator.exe> \
  --omsimulator-version <exact-version> \
  --omsimulator-size-bytes <bytes> \
  --omsimulator-sha256 <lowercase-sha256> \
  --fmpy-version 0.3.31 \
  --fmpy-distribution-sha256 <lowercase-sha256> \
  --comparison-output-dir <new-comparison-package-directory>
```

Acceptance has two independent numerical oracles. First, every pair among
VeraGrid, FMPy, and OMSimulator must agree on the exact common lattice within
`1e-12 + 1e-11 * scale`. Second, each FMU result must remain within normalized
maximum and RMS bounds of 0.01 and 0.005 against the native DASSL trajectory.
The refinement series must also decrease monotonically with every adjacent ratio
in the closed interval [1.8, 2.2]. These metrics are recomputed from the retained
raw CSV files and compared
exactly with the manifest before atomic publication.

The comparison package retains raw traces, process logs, and three sober figures
as PDF, editable SVG, and 300 dpi PNG: overlaid trajectories with event markers,
native-reference
errors, and convergence. The figures are review aids; the CSV recomputation is
the acceptance oracle. This evidence supports only the recorded FMI 2.0 CS SMIB
execution on the recorded Windows host. It is not FMI certification,
multiplatform evidence, or evidence for FMI 1.0, FMI 3.0, or Model Exchange. The
separate caller-selected build directory owns OpenModelica's generated FMU and
native outputs; the comparison manifest binds their identities without copying
the maintained Modelica source or Lua driver into the evidence package.

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

## VDMCheck static validation matrix

`run_vdmcheck_validation` validates the same four authenticated Reference FMUs
once per file with two independent static validators: FMPy 0.3.31 and VDMCheck
1.1.3. Each FMU declares both Co-Simulation and Model Exchange, but static
validation is intentionally file-level rather than repeated per interface.

The caller supplies the complete JRE root, both complete version-specific
VDMCheck distribution roots, the Reference FMU corpus, and every expected tree
identity. The adapter derives `bin/java.exe`, `vdmcheck2.jar`, and
`vdmcheck3.jar` only inside authenticated roots. Each copied validator tree is
authenticated before and after every operation that can consume it. It never
searches `PATH`, reads environment variables, downloads tools, or retains a
runtime in the published package.

Each file validation uses VDMCheck's documented `-v` option with Python's
non-configurable `os.devnull` path. This prevents generated VDM source from
being written beside the staged JAR while preserving the exact validator
output. The version probe does not use `-v`, and every staged tree must remain
byte-identical before and after each Java process.

```text
python -m trunk.dynamics.fmi_comparison.run_vdmcheck_validation \
  --output-dir <new-package-directory> \
  --source-branch devel_dynamics_rebuild \
  --source-revision <40-character-commit> \
  --source-tree-sha256 <64-character-tree-digest> \
  --catalog-path <reference_fmu_catalog.json> \
  --corpus-root <extracted-Reference-FMUs-v0.0.41-root> \
  --fmpy-version 0.3.31 \
  --fmpy-distribution-sha256 39eb2d78370dd241001e5724734f79caf2afcaafc968ba8f93afc597a0337e85 \
  --java-runtime-root <authenticated-jre-root> \
  --java-runtime-file-count <files> \
  --java-runtime-size-bytes <bytes> \
  --java-runtime-tree-sha256 <lowercase-sha256> \
  --java-version <exact-runtime-version-line> \
  --vdmcheck-two-root <complete-vdmcheck2-distribution> \
  --vdmcheck-two-file-count 55 \
  --vdmcheck-two-size-bytes 3155146 \
  --vdmcheck-two-tree-sha256 36facab758b6c2f45de5cde45a93ddec02f5efc37eaaecb962eaad0ca925bd1f \
  --vdmcheck-two-version <exact-version> \
  --vdmcheck-three-root <complete-vdmcheck3-distribution> \
  --vdmcheck-three-file-count 56 \
  --vdmcheck-three-size-bytes 3760225 \
  --vdmcheck-three-tree-sha256 26c80b20d52febb7041aaf4bbd38767b1b9a76311a63e0ae20a97cd64606d2cc \
  --vdmcheck-three-version <exact-version> \
  --process-timeout-seconds 30 \
  --stream-limit-bytes 1048576
```

The current pinned corpus is expected to produce four FMPy PASS verdicts and
four VDMCheck FAIL verdicts containing five findings. That is a completed,
reproducible `COMPLETED_WITH_FINDINGS` result, not a rewritten PASS. Exit code
one is accepted as a validator result only when its native output follows the
exact documented finding grammar; timeouts, excessive output, identity drift,
unexpected exits, nonempty stderr, or malformed text abort publication.

The atomically published package contains one manifest and exactly eight raw
logs. Static XML validation has no numerical trajectory, so this lane correctly
produces no figure. Event and overlaid-trajectory PNG/PDF/SVG evidence belongs
to the Reference FMU execution and SMIB comparison packages described above.
This result is not FMI certification, VeraGrid runtime evidence, FMI 1 evidence,
or multiplatform evidence.

## libcosim composed co-simulation

`run_libcosim_comparison` executes the authenticated Linux libcosim command-line
bundle through an explicitly identified WSL distribution. It composes the SMIB
plant and governor FMUs with a delayed feedback connection, runs the native
master from 0.0 s through 4.0 s with a 0.002 s communication step, and compares
the resulting 2,001-row trajectory against the sealed VeraGrid reference.

The scenario contains two related network-reactance events: the fault is applied
at 1.001 s and cleared at 1.151 s. The comparison covers rotor angle, speed,
electrical power, effective reactance, plant mechanical input, controller speed
input, and controller action. Passing requires exact event-boundary values and
agreement of all 14,007 signal values after six-significant-digit
serialization; it also reports maximum and RMS absolute errors without using
interpolation or synthetic samples.

```text
python -m trunk.dynamics.fmi_comparison.run_libcosim_comparison \
  --output-dir <new-package-directory> \
  --source-branch devel_dynamics_rebuild \
  --source-revision <40-character-commit> \
  --source-tree-sha256 <64-character-tree-digest> \
  --wsl-executable <absolute-path-to-wsl.exe> \
  --wsl-executable-size-bytes <bytes> \
  --wsl-executable-sha256 <lowercase-sha256> \
  --wsl-version <exact-version> \
  --wsl-distribution <distribution-name> \
  --wsl-distribution-pretty-name <exact-pretty-name> \
  --wsl-distribution-version-id <exact-version-id> \
  --wsl-architecture <exact-architecture> \
  --wsl-kernel <exact-kernel> \
  --wsl-glibc-version <exact-glibc-version> \
  --libcosim-bundle <authenticated-zip> \
  --libcosim-bundle-size-bytes <bytes> \
  --libcosim-bundle-sha256 <lowercase-sha256> \
  --cosim-version <exact-cli-version> \
  --libcosim-version <exact-library-version> \
  --reference-manifest <sealed-reference-manifest> \
  --reference-manifest-size-bytes <bytes> \
  --reference-manifest-sha256 <lowercase-sha256> \
  --plant-fmu <authenticated-plant-fmu> \
  --plant-fmu-size-bytes <bytes> \
  --plant-fmu-sha256 <lowercase-sha256> \
  --governor-fmu <authenticated-governor-fmu> \
  --governor-fmu-size-bytes <bytes> \
  --governor-fmu-sha256 <lowercase-sha256> \
  --process-timeout-seconds <positive-seconds> \
  --stream-limit-bytes <positive-byte-limit>
```

The runner does not search `PATH`, read environment variables, download tools,
or publish runtime binaries. It verifies the WSL host, the complete extracted
libcosim tree, both FMUs, and the reference evidence before and after native
execution. A successful run atomically publishes exactly fifteen files: the two
native input documents, four process logs, four canonical native result files,
the copied VeraGrid reference CSV, three scientific figures, and `manifest.json`.

This lane proves the recorded FMI 2.0 Co-Simulation composition on the recorded
Windows/WSL host with the authenticated libcosim distribution. It is not by
itself FMI certification, FMI 1 or FMI 3 evidence, Model Exchange evidence, or
proof of another operating system.

## FMI.jl independent runtime comparison

`run_fmi_jl_comparison` executes the same authenticated SMIB plant and governor
FMUs with FMI.jl 0.15.2 on Julia 1.12.6. FMI.jl is used here as an independent
low-level FMI runtime, not presented as a native composition master. The small
Julia runner performs explicit Jacobi boundary exchange between the two FMUs;
the Python adapter owns authentication, process bounds, comparison, figures and
atomic evidence publication.

The Julia project and complete package resolution are pinned by `Project.toml`
and `Manifest.toml`. Before execution, the adapter authenticates the WSL host,
its Python interpreter, the Julia archive and runtime tree, and the complete
FMI.jl source depot. It then creates a private depot copy with write permission
removed from every entry, rejects symlinks that escape that copy, and places a
new writable overlay in front of it. Julia runs through `/usr/bin/env -i` with
absolute paths, the isolated depot pair and precompilation disabled. The shared
source depot is never exposed to Julia and is authenticated again after the run;
the private workspace is removed on success and on handled failure. This avoids
host-environment discovery, package installation and mutation of shared inputs.

```text
python -m trunk.dynamics.fmi_comparison.run_fmi_jl_comparison \
  --output-dir <new-package-directory> \
  --source-branch devel_dynamics_rebuild \
  --source-revision <40-character-commit> \
  --source-tree-sha256 <64-character-tree-digest> \
  --wsl-executable <absolute-path-to-wsl.exe> \
  --wsl-executable-size-bytes <bytes> \
  --wsl-executable-sha256 <lowercase-sha256> \
  --wsl-distribution Ubuntu \
  --wsl-version 2.6.3.0 \
  --wsl-distribution-pretty-name "Ubuntu 24.04.4 LTS" \
  --wsl-distribution-version-id 24.04 \
  --wsl-architecture x86_64 \
  --wsl-kernel 6.6.87.2-microsoft-standard-WSL2 \
  --wsl-glibc-version 2.39 \
  --wsl-python-executable <absolute-wsl-unc-python-path> \
  --wsl-python-executable-size-bytes <bytes> \
  --wsl-python-executable-sha256 <lowercase-sha256> \
  --wsl-python-version 3.12.3 \
  --julia-archive <authenticated-julia-release-archive> \
  --julia-archive-size-bytes <bytes> \
  --julia-archive-sha256 <lowercase-sha256> \
  --julia-executable <absolute-wsl-unc-path> \
  --julia-executable-size-bytes <bytes> \
  --julia-executable-sha256 <lowercase-sha256> \
  --julia-runtime-entry-count <entries> \
  --julia-runtime-regular-bytes <bytes> \
  --julia-runtime-tree-sha256 <lowercase-sha256> \
  --julia-project <absolute-wsl-unc-project-path> \
  --julia-project-size-bytes <bytes> \
  --julia-project-sha256 <lowercase-sha256> \
  --julia-manifest <absolute-wsl-unc-manifest-path> \
  --julia-manifest-size-bytes <bytes> \
  --julia-manifest-sha256 <lowercase-sha256> \
  --julia-depot <absolute-wsl-unc-depot-path> \
  --julia-depot-entry-count <entries> \
  --julia-depot-regular-bytes <bytes> \
  --julia-depot-tree-sha256 <lowercase-sha256> \
  --wsl-home <absolute-linux-home> \
  --julia-version 1.12.6 \
  --fmi-jl-version 0.15.2 \
  --runner <fmi_jl_runner.jl> \
  --runner-size-bytes <bytes> \
  --runner-sha256 <lowercase-sha256> \
  --plant-fmu <authenticated-plant-fmu> \
  --plant-fmu-size-bytes <bytes> \
  --plant-fmu-sha256 <lowercase-sha256> \
  --governor-fmu <authenticated-governor-fmu> \
  --governor-fmu-size-bytes <bytes> \
  --governor-fmu-sha256 <lowercase-sha256> \
  --reference-manifest <sealed-reference-manifest> \
  --reference-manifest-size-bytes <bytes> \
  --reference-manifest-sha256 <lowercase-sha256> \
  --process-timeout-seconds 120 \
  --stream-limit-bytes 1048576
```

Passing requires exact fault-insertion and fault-clearing boundary samples plus
agreement with VeraGrid for all 14,007 values at an absolute tolerance of
`1e-12`. The verified package contains exactly nine files: the Julia runner,
three process/trajectory logs, the copied VeraGrid trace, three scientific
figure formats, and `manifest.json`. The figures overlay rotor angle, speed,
electrical power and governor command so the event response is directly visible.

This lane proves the recorded FMI 2.0 Co-Simulation runtime behavior only. It
does not claim FMI.jl composition-master conformance, FMI 1.0, FMI 3.0, Model
Exchange, another operating system, or FMI certification.
