# FMI tools-list readiness

VeraGrid is preparing evidence; it is **not** claiming an official FMI
certification or tools-list entry. No pull request is part of this phase.

## Current tools-list process

The current official website guide is fixed here to
[`modelica/fmi-standard.org` commit `138c0f98`](https://github.com/modelica/fmi-standard.org/blob/138c0f98ed91c65ab2c18474d6a6a1dd8bf2cac8/CONTRIBUTING.md)
(content SHA-256
`70f9189d29c2c653ca234efa3efa94e31511332cdce3999919ecc83135598c69`).
It says that the tools page is generated from `tools.json`, changes are made by
pull request, and `examplesURL` points to vendor-maintained compatibility
information. Exporters should list successful importing tools and are
encouraged to publish an FMU with `_ref.csv`, optional `_in.csv`, `_ref.opt`
and a readme. Importers should list successfully tested exporters and FMUs.

| Current preparation item | State | Evidence or remaining work |
| --- | --- | --- |
| Neutral tool identity and description | `READY_FOR_DRAFT` | VeraGrid is MPL-2.0, so the prospective `tools.json` license class is `osi`. Final wording still belongs to the later PR phase. |
| FMI versions and import/export interfaces | `READY_FOR_DRAFT` | Use only the combinations supported by current VeraGrid implementation and the evidence table; do not infer from a runner alone. |
| Vendor-owned compatibility page (`examplesURL`) | `IN_PROGRESS` | [Interoperability status](INTEROPERABILITY_STATUS.md) and this page provide the traceable base. Public URL is selected only when the repository location is final. |
| Exporter compatibility information | `IN_PROGRESS` | Simulink has authenticated standard-FMU evidence for the first-order fixture plus GENSAL, TGOV1 and ESDC2A across FMI 1/2/3 CS/ME. PowerFactory first-order evidence is recorded separately; its three new families remain pending. |
| Importer compatibility information | `IN_PROGRESS` | OpenModelica SMIB supplies one documented external-exporter/model-family lane. Other rows must not be inferred from FMPy-only tests. |
| Public example FMU package | `SIMULINK_VALIDATED_EXTERNAL_HOLD` | [Three-family win64 catalog](veragrid_standard_examples/published/win64/README.md) contains 18/18 locally executed GENSAL, TGOV1 and ESDC2A FMUs with companions, hashes, license and source notices. The [licensed Simulink replay recipe](veragrid_standard_examples/SIMULINK_VALIDATION.md) passed 18/18 exact cells and produced 12 PNG plus 12 PDF figures. PowerFactory execution and external source/artifact availability remain pending. |
| Official tools-list PR | `NOT_STARTED` | Explicitly deferred until the evidence package and publication location are complete. |

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
| GENSAL | Licensed Simulink R2025b Update 1: FMI 1/2/3 CS/ME, exact published hashes | `PASS` 6/6 | Existing standard template reused; any permanent `src`/network example location remains `DEFERRED_CTO` |
| TGOV1 | Licensed Simulink R2025b Update 1: FMI 1/2/3 CS/ME, exact published hashes | `PASS` 6/6 | Existing standard template reused; any permanent `src`/network example location remains `DEFERRED_CTO` |
| ESDC2A | Licensed Simulink R2025b Update 1: FMI 1/2/3 CS/ME, exact published hashes | `PASS` 6/6 | Existing standard template reused; any permanent `src`/network example location remains `DEFERRED_CTO` |

The historical exporter-family count is now four families with licensed
Simulink importer evidence. PowerFactory coverage is narrower and remains
reported separately; publication in the archived cross-check structure has
not been performed. FMI versions or CS/ME variants do not multiply the family
count.

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

1. Verify source/artifact commit availability before externally distributing
   the new 18-FMU catalog; the first-order binary set remains a separate
   publication question.
2. Preserve the completed licensed Simulink receipts for the exact GENSAL,
   TGOV1 and ESDC2A hashes, then execute the supported PowerFactory FMI
   combinations with per-cell receipts.
   Ask the CTO only about any later permanent `src`/network example placement;
   existing standard template ownership is unchanged.
3. Select two additional external exporting vendors and three distinct FMI 2.0
   CS families per vendor if the team chooses to satisfy the archived importer
   matrix as an extra quality target.
4. Draft `tools.json` metadata and `examplesURL` only after the public evidence
   location is stable.
5. Open no PR until all preceding evidence and ownership decisions are closed.
