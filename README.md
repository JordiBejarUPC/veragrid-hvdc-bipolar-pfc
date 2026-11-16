<div align="center">

# Steady-State Analysis of Bipolar MT-HVDC Networks under Balanced and Unbalanced Conditions incorporating Power Flow Controllers

**Case studies and reference implementation**

[![Paper](https://img.shields.io/badge/paper-under%20review-orange?style=flat-square)](#-citation)
[![Built on VeraGrid](https://img.shields.io/badge/built%20on-VeraGrid-1f6feb?style=flat-square)](https://github.com/SanPen/VeraGrid)
[![Docs](https://img.shields.io/badge/docs-readthedocs-8ca1af?style=flat-square)](https://veragrid.readthedocs.io/en/latest/index.html)

</div>

---

> [!NOTE]
> This repository contains the implementation and case studies that accompany the paper
> ***Steady-State Analysis of Bipolar MT-HVDC Networks under Balanced and Unbalanced Conditions incorporating Power Flow Controllers***,
> currently **under review**. The citation will be updated once the paper is published.

## Overview

The paper presents a unified AC/DC Newton–Raphson power flow formulation for **bipolar multi-terminal HVDC (MT-HVDC)** networks. It models the positive pole, the negative pole and the Dedicated Metallic Return (DMR) explicitly, so that balanced and unbalanced operation can be analysed. The formulation also incorporates **Power Flow Controllers (PFCs)**.

The formulation is implemented in [VeraGrid](https://github.com/SanPen/VeraGrid), an open-source power systems analysis tool. The case studies in [`src/trunk/Paper_CaseStudies/`](src/trunk/Paper_CaseStudies/) build the test systems used in the paper, run the power flow and report the results.

## Where to find things

| What | Location in the repository |
| :--- | :--- |
| 📂 **Case studies** | [`src/trunk/Paper_CaseStudies/`](src/trunk/Paper_CaseStudies/) |
| ⚙️ **Power flow algorithm** | [`src/VeraGridEngine/Simulations/PowerFlow/Formulations/pf_full_acdc_with_negative_poles.py`](src/VeraGridEngine/Simulations/PowerFlow/Formulations/pf_full_acdc_with_negative_poles.py) |
| 🧮 **Jacobian derivatives** | [`src/VeraGridEngine/Simulations/Derivatives/csc_derivatives.py`](src/VeraGridEngine/Simulations/Derivatives/csc_derivatives.py) |
| ✅ **MATLAB/Simulink validation models** | [`src/trunk/Paper_CaseStudies/ValidationFilesMatlab/`](src/trunk/Paper_CaseStudies/ValidationFilesMatlab/) |
| ⏱️ **Computational-time benchmarks** | [`src/trunk/Paper_CaseStudies/timing_analysis_data/`](src/trunk/Paper_CaseStudies/timing_analysis_data/) |

```text
src/trunk/Paper_CaseStudies/
├── CaseStudy1_Bipolar.py                     # Case 1 · Point-to-point bipolar link
├── CaseStudy2_Bipolar_WithPfc.py             # Case 2 · Bipolar link with a PFC in each pole
├── CaseStudy3_4TerminalBipolarSystem.py      # Case 3 · 4-terminal meshed bipolar grid with PFCs
├── CaseStudy3_4TerminalBipolarSystem_NOPFC.py  # Case 3 · same grid without PFCs (reference case)
├── grids/
│   └── case300.m                             # IEEE 300-bus system (MATPOWER format), used in Case 3
├── ValidationFilesMatlab/                    # MATLAB/Simulink models used to validate the results
│   ├── data_CaseStudy1and2.m                 #   Parameters for Cases 1 and 2
│   ├── data_CaseStudy3.m                     #   Parameters for Case 3
│   ├── CaseStudy1_Bipolar.slx                #   Simulink model of Case 1
│   ├── CaseStudy2_Bipolar_WithPFC.slx        #   Simulink model of Case 2
│   └── CaseStudy3_4TerminalBipolarSystem.slx #   Simulink model of the DC side of Case 3
└── timing_analysis_data/                     # Computational-time benchmarks (100 runs per case)
    ├── CaseStudy1_Bipolar_timing.py
    ├── CaseStudy2_Bipolar_WithPfc_timing.py
    └── CaseStudy3_4TerminalBipolarSystem_timings.py
```

## Case studies

| # | Script | Test system | What it shows |
| :-: | :--- | :--- | :--- |
| **1** | `CaseStudy1_Bipolar.py` | Point-to-point bipolar link with DMR; 4 VSCs, 100 km cables | Balanced and unbalanced bipolar operation and the resulting DMR return current |
| **2** | `CaseStudy2_Bipolar_WithPfc.py` | System of Case 1 with two parallel conductors per pole and a PFC in each pole | PFC current rerouting between parallel conductors |
| **3** | `CaseStudy3_4TerminalBipolarSystem.py` | PROSECCO benchmark: 4-terminal meshed bipolar grid (land and sea cables), two offshore wind farms, two IEEE 300-bus AC networks (600+ buses) | Droop-controlled VSCs, asymmetric pole dispatch and PFC congestion relief |
| **3 (ref.)** | `CaseStudy3_4TerminalBipolarSystem_NOPFC.py` | Same system as Case 3 with the PFCs removed (lines 1-2 and 1-5 connected directly to bus 1 of each pole) | Natural current distribution, used as the baseline to quantify the effect of the PFCs |

### Mapping to the paper

| Paper result | How to reproduce it |
| :--- | :--- |
| **Table: Case Study 1 validation**, Fig. of Case 1 line currents | `CaseStudy1_Bipolar.py`. Balanced scenario: `Pdc_vsc3 = Pdc_vsc4 = -1000` MW. Unbalanced scenario: `Pdc_vsc4 = -750` MW. Simulink: `CaseStudy1_Bipolar.slx` |
| **Table: PFC validation** at the OP ($I_2^+ = 1400$ A) | `CaseStudy2_Bipolar_WithPfc.py` with the default `Is_set_A = 1400`. Simulink: `CaseStudy2_Bipolar_WithPFC.slx` |
| **Fig.: internal series voltages of PFC+** (sweep of $I_2^+$ between 0 and 1.73 kA) | `CaseStudy2_Bipolar_WithPfc.py`, changing `Is_set_A` across the range and reading `PfcVr` / `PfcVs`. The neutral duty cycle (NDC) is at ≈ 864 A, where both voltages are zero |
| **Fig.: Case 2 branch currents** at the NDC and the OP | `CaseStudy2_Bipolar_WithPfc.py` with `Is_set_A ≈ 864` (NDC) and `Is_set_A = 1400` (OP) |
| **Table: DC line loading without and with PFC** (Case 3) | "Without PFC" columns: `CaseStudy3_4TerminalBipolarSystem_NOPFC.py`. "With PFC" columns: `CaseStudy3_4TerminalBipolarSystem.py` (`Is_set_A_pos = 400`, `Is_set_A_neg = 500`). Both write the line currents and loading to an Excel file (sheet `DC lines`) |
| **Fig.: convergence trajectories** | Printed by every case-study script (`It k, error …` lines) |
| **Computation times** (mean over 50 runs) | Scripts in `timing_analysis_data/` (see [benchmarks](#computational-time-benchmarks)) |

## Requirements

| Component | Needed for | Version used for the paper |
| :--- | :--- | :--- |
| Python | All case studies and timing benchmarks | 3.11 (any version ≥ 3.10 with the packages below should work) |
| VeraGrid (included in this repository under `src/`) | All Python scripts | 6.3.8 with the bipolar and PFC extensions. Do **not** install VeraGrid from PyPI |
| Python packages in [`requirements.txt`](requirements.txt) | All Python scripts | NumPy 2.3, SciPy 1.16, pandas 2.3 |
| MATLAB + Simulink + **Simscape Electrical** (Specialized Power Systems library) | Only the optional [MATLAB validation](#matlabsimulink-validation-models) | R2024b (the `.slx` files open in R2024b or newer) |

## Installation

The case studies rely on a version of VeraGrid that includes the bipolar formulation and the DC Power Flow Controller model, which are not yet available in the official VeraGrid release. **Install it from source by cloning this repository:**

```bash
# 1. Clone the repository
git clone https://github.com/JordiBejarUPC/veragrid-hvdc-bipolar-pfc.git
cd veragrid-hvdc-bipolar-pfc

# 2. (Recommended) create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install the dependencies
pip install -r requirements.txt
```

The scripts import `VeraGridEngine` from the `src/` folder, so add it to your `PYTHONPATH`:

```bash
export PYTHONPATH="$PWD/src"       # Windows (PowerShell): $env:PYTHONPATH = "$PWD\src"
```

> [!TIP]
> In PyCharm, right-click the `src` folder and select **Mark Directory as → Sources Root** instead.

For more information on installing or using VeraGrid, see the
**[VeraGrid documentation](https://veragrid.readthedocs.io/en/latest/index.html#)**.

## Running the case studies

From the repository root:

```bash
cd src/trunk/Paper_CaseStudies

python CaseStudy1_Bipolar.py
python CaseStudy2_Bipolar_WithPfc.py
python CaseStudy3_4TerminalBipolarSystem.py
python CaseStudy3_4TerminalBipolarSystem_NOPFC.py   # Case 3 reference without PFCs
```

Each script prints the Newton–Raphson iteration log, the convergence status, iterations and solution time, followed by bus voltages, branch flows, converter results and, where present, PFC results. All cases converge in 3–5 iterations with the default set-points.

| Script | Files written next to the script |
| :--- | :--- |
| `CaseStudy1_Bipolar.py`, `CaseStudy2_Bipolar_WithPfc.py` | None (console output only) |
| `CaseStudy3_4TerminalBipolarSystem.py` | `4TerminalBipolarSystem_droops_WithPFC.veragrid`, `CaseStudy3_DC_currents.xlsx` (sheets `DC lines`, `VSC Idc`, `PFC currents`) |
| `CaseStudy3_4TerminalBipolarSystem_NOPFC.py` | `4TerminalBipolarSystem_droops_WithoutPFC.veragrid`, `CaseStudy3_DC_currents_WithoutPFC.xlsx` |

> [!TIP]
> The Case 3 scripts wait for keyboard input (see below). To run them non-interactively with the paper defaults, pipe empty lines into them, e.g. `printf '\n\n\n\n' | python CaseStudy3_4TerminalBipolarSystem.py` (bash) or `"`n`n`n`n" | python CaseStudy3_4TerminalBipolarSystem.py` (PowerShell).

<details>
<summary><b>Case 3 · connecting the external AC networks</b></summary>

<br>

Case 3 (both with and without PFCs, and its timing script) asks interactively which AC networks to connect at the two onshore points of interconnection (POI). To reproduce the paper, simply press <kbd>Enter</kbd> at every prompt:

| Prompt | Input |
| :--- | :--- |
| Path for AC network 1 (`.m` or `.veragrid`) | <kbd>Enter</kbd> (uses `grids/case300.m`) |
| Bus name in AC network 1 to connect to the HVDC POI | <kbd>Enter</kbd> (uses bus `7049`) |
| Path for AC network 2 (`.m` or `.veragrid`) | <kbd>Enter</kbd> (uses `grids/case300.m`) |
| Bus name in AC network 2 to connect to the HVDC POI | <kbd>Enter</kbd> (uses bus `7049`) |

The saved `.veragrid` model can be opened in the VeraGrid GUI.

</details>

## Modifying the scenarios

All set-points are defined at the top of each script. By default, every script reproduces the operating point reported in the paper: Case 1 runs the **unbalanced** scenario (`Pdc_vsc4 = -750` MW; set it to `-1000` for the balanced one), Case 2 the OP with $I_2^+ = 1400$ A, and Case 3 the PFC set-points of 400 A and 500 A. Different set-points in each pole make the operation unbalanced.

| Parameter | Cases | Meaning |
| :--- | :-: | :--- |
| `Vdc` / `Vdc_vsc` | 1, 2, 3 | DC voltage set-point of the slack/droop converters (p.u.) |
| `Pdc_vsc3`, `Pdc_vsc4` | 1, 2 | DC power set-points of the positive- and negative-pole converters (MW) |
| `Pac_vsc3pos`, `Pac_vsc4pos`, `Pac_vsc3neg`, `Pac_vsc4neg` | 3 | AC power set-points of the offshore converters, per pole (MW) |
| `Is_set_A`, `Is_set_A_pos`, `Is_set_A_neg` | 2, 3 | PFC current set-point (A) |
| `control1` of each `gce.PFC` | 2, 3 | PFC controlled variable (see below) |

The available PFC control modes are:

| `gce.PfcControlType` | Controlled variable |
| :--- | :--- |
| `Iq_pfc`, `Ir_pfc`, `Is_pfc` | Current through line Q, R or S of the PFC |
| `Vr_pfc`, `Vs_pfc` | Voltage of the R- or S-side internal voltage source |

> [!WARNING]
> Avoid PFC current set-points that exceed the device rating or are exactly zero. Either can cause convergence problems.

## Modelling conventions

- **Per-unit bases:** $U_b = 525$ kV, $S_b = 100$ MW. This gives $I_b = S_b/U_b$ (kA) and $R_b = U_b^2/S_b$ (Ω). Reported currents are converted to amperes.
- **Poles:** every DC bus belongs to one conductor: positive pole, negative pole or DMR. Negative-pole buses are initialised with $V_{a,0} = \pi$ (negative DC voltage). DMR buses are initialised close to zero, and one DMR bus is grounded.
- **Converter losses:** quadratic model $P_{loss} = a + b\,I + c\,I^2$. The coefficients are taken from the CIGRE benchmark below and converted to per unit.
- **Cables:** copper conductors with $\rho_{20} = 1.7241\times10^{-8}$ Ω·m, cross-sections of 2500 mm² (sea) and 3000 mm² (land).

## MATLAB/Simulink validation models

The power flow results of Case Studies 1 and 2 were validated in the paper against time-domain simulations in MATLAB/Simulink R2024b. The Simulink model of Case 3 is provided as an additional check of the DC side. The models are in [`src/trunk/Paper_CaseStudies/ValidationFilesMatlab/`](src/trunk/Paper_CaseStudies/ValidationFilesMatlab/). They are built with the **Specialized Power Systems** blocks of Simscape Electrical (`powergui`, controlled voltage/current sources, series RLC branches and measurements). The steady state reached at the end of the simulation is compared with the VeraGrid solution.

| VeraGrid script | Simulink model | Parameter script | Stop time |
| :--- | :--- | :--- | :-: |
| `CaseStudy1_Bipolar.py` | `CaseStudy1_Bipolar.slx` | `data_CaseStudy1and2.m` | 0.1 ms |
| `CaseStudy2_Bipolar_WithPfc.py` | `CaseStudy2_Bipolar_WithPFC.slx` | `data_CaseStudy1and2.m` | 10 s |
| `CaseStudy3_4TerminalBipolarSystem.py` | `CaseStudy3_4TerminalBipolarSystem.slx` (DC side) | `data_CaseStudy3.m` | 10 s |

**Steps to reproduce the validation**

1. Open MATLAB (R2024b or newer) and set the current folder to `src/trunk/Paper_CaseStudies/ValidationFilesMatlab/`.
2. Run the parameter script of the case (`data_CaseStudy1and2.m` or `data_CaseStudy3.m`). It loads the variables the model reads from the base workspace (`Vb`, `VDC`, `Rbi`/`R`, `Vr_pfc_*`, `Vs_pfc_*`, the cable resistances `r0a … r5`, `Kdroop`, `Pdc_star`, …). The models do **not** load them on their own.
3. Open the matching `.slx` model and press **Run**. The `Display` blocks show the steady-state values directly on the diagram, and the `To Workspace` blocks store the signals in the `out` object.
4. Compare the steady-state voltages, currents and powers with the output of the corresponding Python script.

> [!IMPORTANT]
> The Simulink models do not solve a power flow. The converters are represented by controlled sources, and the PFCs by controlled voltage sources whose internal voltages (`Vr_pfc_pos`, `Vs_pfc_pos`, `Vr_pfc_neg`, `Vs_pfc_neg`, in V) are **taken from the VeraGrid solution** (`ResultTypes.PfcVr` / `PfcVs`, printed in kV by the Python scripts). The power set-points of the source blocks are entered directly in the models. If you change a scenario in Python, update those values in the `.m` script and in the `.slx` source blocks before re-running the validation.

## Computational time benchmarks

The scripts in `timing_analysis_data/` solve each case 100 times. The first runs include the numba JIT compilation, so the mean, standard deviation, minimum and maximum are computed over the **last 50 runs**. These are the figures quoted in the paper (CS 1: 2.05 ms, CS 2: 1.94 ms, CS 3: 11.2 ms on an Intel Core Ultra 7 155H, 32 GB RAM, tolerance $10^{-8}$ p.u.). Absolute times depend on the hardware, so expect different values on another machine. The trend between cases should stay the same.

```bash
cd src/trunk/Paper_CaseStudies/timing_analysis_data
python CaseStudy1_Bipolar_timing.py
python CaseStudy2_Bipolar_WithPfc_timing.py
python CaseStudy3_4TerminalBipolarSystem_timings.py   # asks for the AC networks: press Enter 4 times
```

Each script writes the following next to itself:

| Script | Model | Excel report (`Summary`, `Bus_Voltages`, `Timing_Raw_Data`) | Per-run plot |
| :--- | :--- | :--- | :--- |
| `CaseStudy1_Bipolar_timing.py` | `.veragrid` | `veragrid_case1_timing_results.xlsx` | `veragrid_case1_timing_per_run.png` |
| `CaseStudy2_Bipolar_WithPfc_timing.py` | `.veragrid` | `veragrid_case2_timing_results.xlsx` | `veragrid_case2_timing_per_run.png` |
| `CaseStudy3_4TerminalBipolarSystem_timings.py` | `.veragrid` | `veragrid_4terminal_case300_timing_results_v2.xlsx` | `veragrid_4terminal_case300_timing_per_run.png` |

## Reproducing the paper: checklist

1. Clone the repository, install `requirements.txt` and set `PYTHONPATH` to `src/` ([Installation](#installation)).
2. Run Cases 1, 2 and 3 (with and without PFCs) with the default set-points. Press <kbd>Enter</kbd> at every Case 3 prompt ([Running the case studies](#running-the-case-studies)).
3. Run the three timing scripts to obtain the computational-time figures ([Benchmarks](#computational-time-benchmarks)).
4. *(Optional, requires MATLAB)* Run the Simulink models and compare the steady state with the VeraGrid results ([Validation](#matlabsimulink-validation-models)).

## 📄 Citation

The paper is currently **under review**. Until it is published, please cite it as:

> J. Béjar-Rabascall, J. Girona-Badia, J. Fanals-i-Batllori and O. Gomis-Bellmunt, "Steady-State Analysis of Bipolar MT-HVDC Networks under Balanced and Unbalanced Conditions incorporating Power Flow Controllers," *under review*, 2026.

```bibtex
@unpublished{bejar2026bipolar,
  author = {B{\'e}jar-Rabascall, Jordi and Girona-Badia, Jaume and
            Fanals-i-Batllori, Josep and Gomis-Bellmunt, Oriol},
  title  = {Steady-State Analysis of Bipolar {MT-HVDC} Networks under Balanced and
            Unbalanced Conditions incorporating Power Flow Controllers},
  note   = {Under review},
  year   = {2026}
}
```

When using the software, please also cite [VeraGrid](https://github.com/SanPen/VeraGrid).

## References

- CIGRE, "Enhanced real-time multi-terminal HVDC power system benchmark models with performance evaluation strategies," *CIGRE Science & Engineering*, no. 32. Source of the cable resistance and converter loss parameters.
- R. D. Zimmerman, C. E. Murillo-Sánchez, R. J. Thomas, "MATPOWER: Steady-state operations, planning, and analysis tools for power systems research and education," *IEEE Trans. Power Syst.*, vol. 26, no. 1, pp. 12–19, 2011. Source of the IEEE 300-bus `case300.m`.

## Acknowledgements

This project has received funding from the European Union's Horizon Europe research and innovation programme under grant agreement No 101160687 (PROSECCO). Case Study 3 uses the PROSECCO benchmark network.
