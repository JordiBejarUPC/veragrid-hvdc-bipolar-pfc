# FMI tools-list readiness

VeraGrid is preparing evidence; it is **not** claiming an official FMI
certification or tools-list entry. No pull request is part of this phase.

## Current tools-list process

The current official website guide is fixed here to
[`modelica/fmi-standard.org` commit `b25ad9e8`](https://github.com/modelica/fmi-standard.org/blob/b25ad9e88db1f635c52afc2829b90abbbea43db1/CONTRIBUTING.md)
(content SHA-256
`d3086ef036b2406ca9b42f81effb7fcc5c075625286ed15b9ff3e76bc7e688cd`).
The corresponding
[`tools.json`](https://github.com/modelica/fmi-standard.org/blob/b25ad9e88db1f635c52afc2829b90abbbea43db1/static/assets/tools.json)
has SHA-256
`e66f9121634c238b7e8910e4c72ea1656469a72f5f421d768c27c615ed345d0e`.
It says that the tools page is generated from `tools.json`, changes are made by
pull request, and `examplesURL` points to vendor-maintained compatibility
information. Exporters should list successful importing tools and are
encouraged to publish an FMU with `_ref.csv`, optional `_in.csv`, `_ref.opt`
and `Readme.txt`. Importers should list successfully tested exporters and
FMUs. The current guide also requires quoted CSV headers, exact
`modelDescription.xml` variable names, monotonic time, C-style numeric
literals and files below 1 MB.

| Current preparation item | State | Evidence or remaining work |
| --- | --- | --- |
| Neutral tool identity and description | `READY_FOR_DRAFT` | VeraGrid is MPL-2.0, so the prospective `tools.json` license class is `osi`. Final wording still belongs to the later PR phase. |
| FMI versions and import/export interfaces | `READY_FOR_DRAFT` | Use only the combinations supported by current VeraGrid implementation and the evidence table; do not infer from a runner alone. |
| Vendor-owned compatibility page (`examplesURL`) | `READY_ON_BRANCH_NOT_STABLE` | [Interoperability status](INTEROPERABILITY_STATUS.md), the replay recipes and this page provide the traceable content. The final URL must target a stable public revision selected for release, not this development branch. |
| Exporter compatibility information | `READY_AS_EVIDENCE` | Simulink has authenticated evidence for the first-order fixture plus GENSAL, TGOV1 and ESDC2A across FMI 1/2/3 CS/ME. PowerFactory has authenticated evidence for all twelve applicable GENSAL, TGOV1 and ESDC2A FMI 2/3 CS/ME cells; FMI 1 is not supported by that importer. |
| Importer compatibility information | `IN_PROGRESS` | OpenModelica SMIB supplies one documented external-exporter/model-family lane. Other rows must not be inferred from FMPy-only tests. |
| Public example FMU package | `VALIDATED_NEEDS_SUBMISSION_VIEW` | [Three-family win64 catalog](veragrid_standard_examples/published/win64/README.md) contains 18/18 locally executed GENSAL, TGOV1 and ESDC2A FMUs with companions, hashes, license and source notices. Simulink passed all 18 cells; PowerFactory passed all 12 applicable FMI 2/3 cells. The immutable evidence catalog intentionally remains unchanged. A derived publication view must quote CSV headers and provide `Readme.txt` without changing or replacing the evidence hashes. |
| Official tools-list PR | `NOT_STARTED` | Explicitly deferred until the evidence package and publication location are complete. |

## Review precedents from real tools-list submissions

These merged submissions show what maintainers actually requested. They are
review precedents, not additional normative requirements.

| Tool and pull request | Maintainer request | VeraGrid preparation consequence |
| --- | --- | --- |
| [FastSim #903](https://github.com/modelica/fmi-standard.org/pull/903) | Provide generated FMUs for direct download, describe import tests with FMUs from other tools, and preferably include binaries for supported platforms. | Keep the canonical FMUs downloadable, name every importing tool and version, retain third-party importer evidence, and do not claim an untested platform binary. |
| [AgentLib #847](https://github.com/modelica/fmi-standard.org/pull/847) | Make `examplesURL` self-explanatory with at least a README stating which FMUs, exporting tools and Reference FMUs were tested. | The compatibility page must be understandable without inspecting scripts or receipts and must separate VeraGrid-exporter from VeraGrid-importer evidence. |
| [Quix FMU Runner #856](https://github.com/modelica/fmi-standard.org/pull/856) | Remove an unrelated news post and document which sample FMUs were tested at `examplesURL`. | Keep the future PR limited to the tool entry and optional logo; publish the compatibility matrix before linking it. |
| [PathSim #799](https://github.com/modelica/fmi-standard.org/pull/799) and [#814](https://github.com/modelica/fmi-standard.org/pull/814) | The initial focused entry was approved; a later PR corrected its URL. | Resolve and verify every public URL before submission so the first entry is durable. |

## Prospective `tools.json` entry

This is the prepared field-level draft. It is deliberately not emitted as a
copy-paste JSON object while release ownership and the stable `examplesURL`
remain unresolved; placeholders in an official entry would be misleading.

| Field | Prospective value | Gate |
| --- | --- | --- |
| `name` | `VeraGrid` | Ready |
| `license` | `osi` | Ready: MPL-2.0 is OSI approved |
| `url` | `https://github.com/SanPen/VeraGrid` | Ready; matches package metadata |
| `logo` | Existing VeraGrid SVG, final asset to be selected | Human approval required because submission authorizes display on the FMI page |
| `vendor` | `eRoots Analytics` | Confirm with CTO before submission |
| `vendorURL` | `https://eroots.tech/` | Confirm with CTO before submission |
| `examplesURL` | Stable public location for this compatibility dossier | Blocked until the publication branch/tag is selected |
| `description` | `Power-system modelling, analysis and simulation software` | Ready; neutral and does not repeat table fields |
| `features` | `[]` | Ready; reserved field |
| `platforms` | `Linux`, `macOS`, `Windows` | Recheck against the release package matrix before submission |
| `interfaces` | `GUI`, `CLI`, `library` | Ready from the maintained package topology |
| `fmiVersions` | `1.0`, `2.0`, `3.0` | Ready from current import/export implementation and tests |
| `fmuExport` | `CS`, `ME` | Ready from current implementation and external importer evidence |
| `fmuImport` | `CS`, `ME` | Implementation-ready; compatibility page must retain the narrower external-exporter evidence |
| `layeredStandards` | `[]` | Ready; none claimed |

## Historical cross-check readiness

The following section is a conservative gap analysis against the **archived**
Cross-Check 4.1 rules, not the current tools-list admission requirement. The
source is fixed to
[`modelica/fmi-cross-check` commit `55c6704b`](https://github.com/modelica/fmi-cross-check/blob/55c6704bbcaed3e0f4f788a02af0aba08b7faa4a/FMI-CROSS-CHECK-RULES.md)
(content SHA-256
`7debe8a74c57184f1133a38facb14466614f7fa248634d5c847a6f9a5e6f1b05`).

Those archived rules required an exporter to publish at least three FMUs for
each claimed platform and FMI variant, with another vendor successfully
importing at least three for green status. An importer needed three FMUs from
each of three other exporting vendors for one platform: a 3 vendors by 3 FMUs
matrix.

### VeraGrid as exporter: three distinct model families

Changing FMI version or CS/ME mode does not create a new model family. The six
first-order variants therefore count as one family.

| VeraGrid model family | Other-vendor importer evidence | Evidence status | Architectural disposition |
| --- | --- | --- | --- |
| Normalized first-order fixture | Simulink: FMI 1/2/3 CS/ME; PowerFactory: FMI 2 CS/ME and FMI 3 CS/ME with the documented compatibility profile | `PASS` for the exact recorded cells | `READY_AS_EVIDENCE`; binary publication still requires identity and redistribution checks |
| GENSAL | Simulink R2025b Update 1: FMI 1/2/3 CS/ME; PowerFactory 2025 SP4: FMI 2/3 CS/ME | `PASS` 6/6 Simulink and 4/4 PowerFactory | Existing standard template reused; any permanent `src`/network example location remains `DEFERRED_CTO` |
| TGOV1 | Simulink R2025b Update 1: FMI 1/2/3 CS/ME; PowerFactory 2025 SP4: FMI 2/3 CS/ME | `PASS` 6/6 Simulink and 4/4 PowerFactory | Existing standard template reused; any permanent `src`/network example location remains `DEFERRED_CTO` |
| ESDC2A | Simulink R2025b Update 1: FMI 1/2/3 CS/ME; PowerFactory 2025 SP4: FMI 2/3 CS/ME | `PASS` 6/6 Simulink and 4/4 PowerFactory | Existing standard template reused; any permanent `src`/network example location remains `DEFERRED_CTO` |

The historical exporter-family count is now four families with licensed
Simulink importer evidence. PowerFactory covers all twelve applicable FMI 2/3
cells for the three electrical families and remains reported separately;
publication in the archived cross-check structure has not been performed.
FMI versions or CS/ME variants do not multiply the family count.

### VeraGrid as importer: historical 3x3 matrix

One matrix must hold platform, FMI version and interface fixed. The current
candidate below uses Windows x86-64, FMI 2.0 Co-Simulation because that is where
the OpenModelica SMIB evidence exists. A cell represents a distinct external
FMU model family successfully imported and run by VeraGrid. Reference FMUs are
valuable supplementary coverage but are not silently counted as one of the
three other exporting-tool vendors.

| External exporting vendor | FMU family 1 | FMU family 2 | FMU family 3 | Row status |
| --- | --- | --- | --- | --- |
| OpenModelica | SMIB — `DOCUMENTED_PASS` | `UNKNOWN` | `UNKNOWN` | Incomplete: 1/3 |
| External vendor 2 — not selected | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | Incomplete: 0/3 |
| External vendor 3 — not selected | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | Incomplete: 0/3 |

Every unproved cell retains evidence status `UNKNOWN`. Selection or placement
work may be deferred, but that disposition never changes the evidence verdict.
The historical importer gate is therefore incomplete: **one of nine** cells is
documented, and only one of three external vendors is represented.

## Next gated work

1. Push the source/artifact commit and this updated dossier so the exact
   18-FMU evidence package is remotely addressable.
2. Create a separate official-publication view with quoted CSV headers and
   `Readme.txt`; retain the committed evidence catalog byte-for-byte so its
   Simulink and PowerFactory receipts stay valid.
3. Ask the CTO to confirm vendor text, vendor URL, logo, stable
   `examplesURL`, and any later permanent `src`/network example placement.
4. Select two additional external exporting vendors and three distinct FMI 2.0
   CS families per vendor if the team chooses to satisfy the archived importer
   matrix as an extra quality target.
5. Recheck all URLs and the release platform matrix, then convert the prepared
   field table into the exact upstream `tools.json` object.
6. Open no PR until all preceding evidence and ownership decisions are closed.
