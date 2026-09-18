# FMI interoperability status

This is the master inventory of FMI validation campaigns maintained by
VeraGrid. It separates executable recipes from authenticated executions and
distinguishes VeraGrid acting as exporter, importer, orchestrator or observer.
The detailed reproduction commands remain in [README.md](README.md) and the
linked subpackages.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| `PASS` | Exact authenticated execution evidence is available in the stated evidence envelope. |
| `DOCUMENTED_PASS` | The tracked documentation records a successful campaign outcome, but this inventory did not re-authenticate its raw external receipt. |
| `COMPLETED_WITH_FINDINGS` | The campaign completed and retained one or more limitations or failing cells. |
| `NOT_EXECUTED` | This bounded evidence envelope contains a maintained harness but no execution result. It is not a claim about every historical machine or session. |
| `NOT_APPLICABLE` | The named tool and version do not support the combination. |
| `UNKNOWN` | The available evidence does not justify an execution verdict. |

`Currency` is independent from status. `Historical lineage` identifies an
authenticated prior run that is not proof of a replay from the current
checkout. `Profile` separates standard FMUs from tool-specific compatibility
derivatives. A runner's presence alone never implies `PASS`.

## Master campaign table

| Campaign | Ecosystem | VeraGrid role / other tool role | FMI | Interface | Model or purpose | Status | Currency / profile | Evidence and limit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Device examples | Open-source | VeraGrid exporter and local example host | 2.0 | CS, ME | RMS and EMT examples | `UNKNOWN` | Recipe only / standard | [`run_device_examples.py`](run_device_examples.py) is a smoke recipe, not independent interoperability evidence. |
| RMS comparison | Open-source | VeraGrid exporter; VeraGrid, FMPy and OMSimulator import/run | 2.0 | CS, ME | RMS network fixture | `DOCUMENTED_PASS` | Recorded / standard | [Root recipe](README.md) records common-FMU comparison. FMPy is also VeraGrid's backend, while OMSimulator is the independent runtime. |
| OpenModelica SMIB | Open-source | OpenModelica exporter; VeraGrid, FMPy and OMSimulator import/run | 2.0 | CS | Dynamic SMIB plant | `DOCUMENTED_PASS` | Recorded / standard | [OpenModelica section](README.md#openmodelica-smib-dynamic-comparison). This is one external exporter and one model family. |
| Reference corpus preparation | Open-source | Corpus authentication only | 2.0, 3.0 | CS, ME | BouncingBall and Stair | `DOCUMENTED_PASS` | Recorded / standard | [Corpus section](README.md#reference-fmu-corpus). Corpus readiness is not runtime interoperability. |
| Reference execution matrix | Open-source | FMPy and fmusim import/run Reference FMUs | 2.0, 3.0 | CS, ME | BouncingBall and Stair | `DOCUMENTED_PASS` | Recorded / standard | [Execution section](README.md#reference-fmu-execution-matrix). It does not prove VeraGrid runtime behavior. |
| VDMCheck matrix | Open-source | FMPy and VDMCheck static validators | 2.0, 3.0 | CS, ME | Reference FMUs | `COMPLETED_WITH_FINDINGS` | Recorded / standard | [VDMCheck section](README.md#vdmcheck-static-validation-matrix): four FMPy passes, four VDMCheck failures and five retained findings. |
| libcosim composition | Open-source | libcosim composition master compared with VeraGrid | 2.0 | CS | Coupled SMIB and governor | `DOCUMENTED_PASS` | Recorded / standard | [libcosim section](README.md#libcosim-composed-co-simulation). Windows/WSL host evidence only. |
| FMI.jl runtime | Open-source | FMI.jl independent runtime compared with VeraGrid | 2.0 | CS | Retained comparison FMUs | `DOCUMENTED_PASS` | Recorded / standard | [FMI.jl section](README.md#fmijl-independent-runtime-comparison). It is not FMI.jl composition-master conformance. |
| PathSim-FMI orchestration | Open-source | PathSim-FMI/FMPy wrapper imports Reference FMUs | 2.0, 3.0 | CS, ME | BouncingBall and Stair | `COMPLETED_WITH_FINDINGS` | Recorded / standard | [PathSim section](README.md#pathsim-fmi-orchestration-comparison): four BouncingBall cells pass; four Stair cells retain Integer/Int32 output limitations. |
| FMUGym orchestration | Open-source | FMUGym/FMPy wrapper compared with direct FMPy | 2.0, 3.0 | CS | SMIB and Feedthrough | `COMPLETED_WITH_FINDINGS` | Recorded / standard | [FMUGym section](README.md#fmugym-orchestration-comparison): numerical cells pass; finite-horizon time behavior remains a finding. |
| train_fmu_gym | Open-source | Learning wrapper compared with direct core execution | 2.0, 3.0 | CS | Packaged learning environments | `COMPLETED_WITH_FINDINGS` | Recorded / standard | [train_fmu_gym section](README.md#train_fmu_gym-learning-comparison): direct core passes; public CLI child-interpreter behavior remains a finding. |
| EnergyPlusToFMU | Open-source | EnergyPlusToFMU exporter; direct FMPy importer | 1.0 | CS | EnergyPlus Schedule model | `UNKNOWN` | Recipe plus documented gate / compatibility patch | [EnergyPlus section](README.md#energyplustofmu-export-comparison) defines a PASS gate, but this inventory does not contain an authenticated executed receipt. It is not VeraGrid importer evidence. |
| Maestro composition | Open-source | Maestro composition master compared with VeraGrid | 2.0 | CS | Delayed two-FMU SMIB loop | `NOT_EXECUTED` | Harness only / standard | [`run_maestro_comparison.py`](run_maestro_comparison.py) exists, but no execution receipt or outcome is present in this bounded evidence envelope. |
| Simulink commercial replay | Commercial | VeraGrid exporter; Simulink importer | 1.0, 2.0, 3.0 | CS, ME | Normalized first-order fixture | `PASS` | Historical lineage / standard | [`validated_run.json`](simulink_first_order/validated_run.json) records 6/6 cells under MATLAB/Simulink R2025b Update 1. It explicitly is not a current-checkout replay. |
| PowerFactory commercial replay | Commercial | VeraGrid exporter; PowerFactory importer | 2.0, 3.0 | CS, ME | Normalized first-order fixture | `PASS` | Retained authenticated replay / standard plus PF-specific FMI 3 derivative | [PowerFactory recipe](powerfactory_first_order/README.md). FMI 2 uses standard FMUs. The unmodified FMI 3 archives failed `ComInc`; the passing FMI 3 cells use documented PowerFactory-specific derivatives. FMI 1 is `NOT_APPLICABLE` for PowerFactory 2025 SP4. |
| Six-cell local generation | Open-source toolchain | VeraGrid exporter; local FMPy execution | 1.0, 2.0, 3.0 | CS, ME | Normalized first-order fixture | `PASS` | Authenticated commit `95a156461`; standard | External manifest SHA-256 `67a5cc0bfac3b1d6b9ec2db85c32451990f3d7b5918233b64792e41e42b0c798`; 6/6 cells passed. This is not a new licensed replay. |
| Standard electrical example catalog | Open-source toolchain | VeraGrid exporter; local FMPy execution | 1.0, 2.0, 3.0 | CS, ME | GENSAL, TGOV1, ESDC2A — three distinct physical families | `PASS` | Current local worktree; win64 standard; not externally distributed | [Catalog manifest](veragrid_standard_examples/published/win64/manifest.json) and [recipe](veragrid_standard_examples/generate_standard_examples.py): 18/18 local cells, phase-aware pointwise comparisons, 94/94 file hashes and MPL/source notices verified. No Simulink or PowerFactory execution of these exact artifacts. |
| Standard electrical Simulink replay | Commercial | VeraGrid exporter; licensed Simulink importer | 1.0, 2.0, 3.0 | CS, ME | GENSAL, TGOV1, ESDC2A | `PASS` | Authenticated R2025b Update 1 replay / current worktree recipe | [Reproducible R2025b harness](veragrid_standard_examples/SIMULINK_VALIDATION.md) executed the exact 18 win64 hashes: 18/18 pointwise cells and all channel-identification gates passed. Maximum physical-wave absolute/normalized error was 0.002880763429; maximum signature error 0.002831148144; minimum observable response 0.01185778113; minimum required separation 0.01428571429. Generated external evidence contains the build/run/validation receipts, 18 comparison CSVs and 12 PNG plus 12 PDF figures. |
| Standard electrical PowerFactory import | Commercial | VeraGrid exporter; prospective PowerFactory importer | 2.0, 3.0 | CS, ME | GENSAL, TGOV1, ESDC2A | `UNKNOWN` | Not executed / exact hashes pending licensed replay | Simulink PASS does not transfer importer compatibility to PowerFactory. FMI 1 is not applicable on the installed PowerFactory importer. |

The two plotting entry points for Reference FMUs and VDMCheck are renderers,
not additional simulation campaigns, and are intentionally excluded from the
campaign count.

The locally executed exporter catalog now covers four distinct model families
when the prior normalized first-order fixture is included. Commercial exporter
evidence now covers all four families in licensed Simulink; PowerFactory
coverage of the three new families remains `UNKNOWN`. The new catalog's `NOT_FOR_EXTERNAL_DISTRIBUTION`
state remains until its corresponding source/artifact revision is available
remotely.

## Repository qualification evidence

The campaign count is separate from the product regression suite. The retained
verification receipt for commit `95a156461` has SHA-256
`303121cba9e586c8de49e92a722404c93be802ce23fe91c3ef492d94f9a65f70`
and records:

- complete `src/tests/FMI`: 633 passed, 4 skipped, 0 failed;
- focused compiler lifecycle tests: 44 passed, 1 skipped, 0 failed;
- first-order FMI 1/2/3 CS/ME matrix: 6 passed, 0 failed;
- PowerFactory reproducibility recipe: 14 passed, 0 failed; and
- no new licensed Simulink or PowerFactory execution in that qualification run.

## What this proves

The commercial rows prove VeraGrid **exporter** interoperability because
Simulink and PowerFactory imported VeraGrid-generated FMUs. They do not prove
that VeraGrid imported FMUs exported by those commercial tools. Conversely,
the OpenModelica SMIB row is VeraGrid **importer** evidence for one external
exporter and one model family. Wrapper-based lanes remain labelled as such so
they are not mistaken for independent low-level FMI runtimes.

This inventory is engineering evidence, not an official FMI certification or
an entry in the FMI tools list.
