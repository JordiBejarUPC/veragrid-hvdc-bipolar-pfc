# A Hands-on Open-source Dynamic Simulation tutorial using VeraGrid

## Guide contents

1. [eRoots Analytics, VeraGrid and session context](#1-eroots-analytics-veragrid-and-session-context)
   1. [Who we are](#11-who-we-are)
   2. [What is VeraGrid?](#12-what-is-veragrid)
   3. [Purpose of the session](#13-purpose-of-the-session)
2. [Learning objectives](#2-learning-objectives)
3. [System overview](#3-system-overview)
   1. [Network topology](#31-network-topology)
   2. [Control philosophy](#32-control-philosophy)
   3. [Modelling conventions and bases](#33-modelling-conventions-and-bases)
4. [Static network data](#4-static-network-data)
   1. [Grid and buses](#41-grid-and-buses)
   2. [External AC grids](#42-external-ac-grids)
   3. [Coupling transformers](#43-coupling-transformers)
   4. [Voltage-source converters](#44-voltage-source-converters)
   5. [DC line](#45-dc-line)
5. [RMS dynamic models](#5-rms-dynamic-models)
   1. [Model assignment summary](#51-model-assignment-summary)
   2. [External-grid voltage-source model](#52-external-grid-voltage-source-model)
   3. [Passive transformer model](#53-passive-transformer-model)
   4. [Standalone HVDC GFL VSC model](#54-standalone-hvdc-gfl-vsc-model)
   5. [Dynamic DC-line model](#55-dynamic-dc-line-model)
6. [GUI construction procedure](#6-gui-construction-procedure)
   1. [Create the circuit](#61-create-the-circuit)
   2. [Build the static diagram](#62-build-the-static-diagram)
   3. [Check the static model](#63-check-the-static-model)
   4. [Verify the RMS Library](#64-verify-the-rms-library)
   5. [Assign and edit the RMS models](#65-assign-and-edit-the-rms-models)
7. [RMS events](#7-rms-events)
8. [Simulation settings](#8-simulation-settings)
9. [Results and expected response](#9-results-and-expected-response)
10. [Troubleshooting](#10-troubleshooting)
11. [Final checklist](#11-final-checklist)

---

## 1. eRoots Analytics, VeraGrid and session context

### 1.1. Who we are

eRoots Analytics is a Barcelona-based spin-off of the Universitat Politècnica de Catalunya (UPC), founded in 2022. The company develops and commercializes advanced tools and services for electrical-power-system modelling, simulation and decision support.

The eRoots team brings together power-system engineers and software developers with experience in grid modelling, renewable-energy integration, energy markets and numerical methods. Its work follows three connected activities:

1. **Data:** cleaning, validating and organizing fragmented energy data into trusted datasets suitable for modelling and simulation.
2. **Algorithms:** developing open-source and high-performance methods for energy-system and electrical-grid studies.
3. **Insights:** translating complex study results into clear technical information that supports engineering and business decisions.

This scope extends across both time and system scale: from electromagnetic phenomena that occur within microseconds to planning scenarios that extend decades into the future, and from individual electrical components to large interconnected grids.

VeraGrid is the central open-source platform developed by eRoots. The company also provides engineering support, model development, data processing and validated studies for grid operators, utilities, manufacturers, engineering companies and research organizations.

### 1.2. What is VeraGrid?

VeraGrid is an open-source platform for modelling, analysing and visualizing electrical and energy systems. It is designed to support the complete grid-study workflow within a common data model, from high-level aggregated energy scenarios to detailed electrical-network representations.

Its principal characteristics are:

- **Open-source development:** the source code, modelling methods and interfaces can be inspected, extended and validated by users and contributors.
- **End-to-end workflow:** the same project can contain network data, time variations, study configurations, events and results without requiring a separate model for every analysis stage.
- **Interoperability:** VeraGrid can exchange data with commonly used grid formats and can be integrated into wider engineering workflows.
- **GUI and library access:** studies can be created interactively in the graphical user interface or automated through the VeraGrid Python library. Both interfaces operate on the same underlying network model.
- **Scalable modelling:** the platform is intended for both small educational examples and large practical networks.

VeraGrid covers three broad study areas:

| Area | Representative capabilities |
|---|---|
| Energy and market modelling | Investment analysis, adequacy, sector coupling, dispatch and optimal power flow |
| Static and time-series grid studies | Power flow, contingency analysis, short circuits and time-series simulations |
| Dynamic simulation | Small-signal stability, RMS time-domain simulation and EMT simulation |

The graphical interface allows users to create multiple schematics and maps, inspect interactive result displays, manage device and template databases, and configure simulations without writing code. The Python library exposes the same modelling and calculation capabilities for reproducible studies, batch processing and automation.

This hands-on session focuses on the RMS dynamic-simulation part of VeraGrid. Participants will construct the system from the GUI while working with the same device definitions, symbolic models and study concepts that are available through the library.

### 1.3. Purpose of the session

This hands-on session reproduces, from the VeraGrid graphical user interface, the point-to-point HVDC system defined in:

`trunk/dynamics/model_validation/rms_hvdc_vdc_control_standalone_vsc.py`

The system contains two independent AC grids connected through a detailed DC link. Each terminal uses a standalone grid-following voltage-source converter (GFL VSC). One converter regulates the DC voltage and the other regulates the transferred DC power. Both converters regulate their AC reactive-power exchange.

The exercise covers the complete study workflow:

- static AC/DC network construction;
- converter-control selection;
- assignment and inspection of RMS models;
- construction of the dynamic DC-line equations;
- definition of RMS events;
- RMS simulation configuration;
- interpretation of voltages, powers and DC current.

This document is intended to be used as a recovery guide during the live demonstration. A participant who falls behind should be able to identify the required device, parameter and value without referring to the Python implementation.

## 2. Learning objectives

At the end of the session, participants should be able to:

- distinguish an AC bus from a DC bus in VeraGrid;
- create a detailed point-to-point HVDC system using `VSC` and `DcLine` devices;
- select compatible converter controls for an AC/DC power flow;
- understand why one HVDC terminal regulates DC voltage and the other regulates active power;
- assign the complete device RMS models from the Dynamic Editor Library;
- identify the main control loops of a grid-following VSC;
- define an event on a dynamic reference rather than on a static device property;
- run an RMS study and assess its initialization and convergence;
- interpret the sign and per-unit conventions of the principal results.

## 3. System overview

### 3.1. Network topology

The network is symmetrical at both terminals. The detailed connection order is:

![System overview](example_hvdcLFE.png)

The device directions used by the reference case are:

| Device | `from` bus | `to` bus |
|---|---|---|
| `TrafoGFL_1` | `Bus_VSC_1` | `Bus_Grid_1` |
| `VSC_1` | `Bus_DC_1` | `Bus_VSC_1` |
| `HVDC_Line` | `Bus_DC_1` | `Bus_DC_2` |
| `VSC_2` | `Bus_DC_2` | `Bus_VSC_2` |
| `TrafoGFL_2` | `Bus_VSC_2` | `Bus_Grid_2` |

For a VeraGrid `VSC`, the positive DC terminal is always the `from` side and the AC terminal is always the `to` side. The GUI may correct a reversed drawing automatically, but the final properties must still be checked.

> **Important:** use a physical `DcLine` between the two DC buses. Do not use the aggregated `HvdcLine` device. The exercise represents converters, DC buses and the DC line explicitly.

### 3.2. Control philosophy

Every VSC must contribute two independent control equations to the AC/DC power flow. The selected controls are:

| Converter | Active-axis control | Reactive-axis control | Role in the HVDC link |
|---|---|---|---|
| `VSC_1` | `Vm_dc` | `Qac` | Establishes the DC-voltage reference and acts as the DC slack terminal |
| `VSC_2` | `Pdc` | `Qac` | Establishes the transferred DC power |

This allocation is fundamental. A connected DC island requires one DC-voltage controller. If neither terminal controls `Vm_dc`, the DC voltage has no reference. If both terminals impose the same DC-voltage degree of freedom, the model is over-constrained.

The two AC grids are separate AC islands connected only through the converter-based DC system. Each AC island therefore has its own slack bus and stiff voltage-source equivalent.

### 3.3. Modelling conventions and bases

| Quantity | Value | Use |
|---|---:|---|
| System base power, `Sbase` | 100 MVA | Common base for all per-unit powers and impedances |
| Nominal frequency, `fBase` | 50 Hz | AC nominal frequency and PLL base |
| AC nominal voltage | 90 kV | All four AC buses |
| DC nominal voltage | 145 kV | Both DC buses |
| AC impedance base, `Zbase_ac` | 81 ohm | `90^2 / 100` |
| DC impedance base, `Zbase_dc` | 210.25 ohm | `145^2 / 100` |

Unless a static property explicitly states MW, MVAr, MVA or kV, dynamic quantities in this exercise are expressed in per unit on the 100 MVA system base.

Useful conversions are:

- `1.0 p.u.` active power = `100 MW`;
- `0.20 p.u.` active power = `20 MW`;
- `0.01 p.u.` active-power change = `1 MW`;
- `1.0 p.u.` AC voltage = `90 kV`;
- `1.0 p.u.` DC voltage = `145 kV`.

## 4. Static network data

### 4.1. Grid and buses

Create the circuit with the name `Point-to-point HVDC RMS Vdc-control example`.

| Object | Parameter | Value | Meaning |
|---|---|---:|---|
| Grid | `Sbase` | 100 MVA | System power base |
| Grid | `fBase` | 50 Hz | Nominal frequency |
| `Bus_Grid_1` | `Vnom` | 90 kV | AC-grid terminal voltage |
| `Bus_Grid_1` | `is_dc` | `False` | AC bus |
| `Bus_Grid_1` | `is_slack` | `True` | Angle and voltage reference of AC island 1 |
| `Bus_VSC_1` | `Vnom` | 90 kV | Converter-side AC bus |
| `Bus_VSC_1` | `is_dc` | `False` | AC bus |
| `Bus_VSC_1` | `is_slack` | `False` | Non-slack AC bus |
| `Bus_DC_1` | `Vnom` | 145 kV | DC terminal 1 |
| `Bus_DC_1` | `is_dc` | `True` | DC bus |
| `Bus_DC_1` | `is_slack` | `False` | DC voltage is controlled by `VSC_1`, not by the bus flag |
| `Bus_DC_2` | `Vnom` | 145 kV | DC terminal 2 |
| `Bus_DC_2` | `is_dc` | `True` | DC bus |
| `Bus_DC_2` | `is_slack` | `False` | DC voltage follows the link solution |
| `Bus_VSC_2` | `Vnom` | 90 kV | Converter-side AC bus |
| `Bus_VSC_2` | `is_dc` | `False` | AC bus |
| `Bus_VSC_2` | `is_slack` | `False` | Non-slack AC bus |
| `Bus_Grid_2` | `Vnom` | 90 kV | AC-grid terminal voltage |
| `Bus_Grid_2` | `is_dc` | `False` | AC bus |
| `Bus_Grid_2` | `is_slack` | `True` | Angle and voltage reference of AC island 2 |

The usual voltage limits may remain at their defaults of `Vmin = 0.9 p.u.` and `Vmax = 1.1 p.u.`.

### 4.2. External AC grids

Attach one generator injection to each grid bus.

| Device | Bus | Parameter | Value |
|---|---|---|---:|
| `Generator_Grid_1` | `Bus_Grid_1` | `P` | 0 MW |
| `Generator_Grid_1` | `Bus_Grid_1` | `Vset` | 1.0 p.u. |
| `Generator_Grid_1` | `Bus_Grid_1` | `Snom` | 100 MVA |
| `Generator_Grid_1` | `Bus_Grid_1` | `freq` | 50 Hz |
| `Generator_Grid_1` | `Bus_Grid_1` | `R1` | 0.039644444 p.u. |
| `Generator_Grid_1` | `Bus_Grid_1` | `X1` | 0.134925587 p.u. |
| `Generator_Grid_2` | `Bus_Grid_2` | Same values | Same values |

The equivalent sequence values are obtained from the reference-case conversion:

```text
R1 = (4.8 * 0.669) / Zbase_ac
X1 = (2 * pi * 50 * 0.052 * 0.669) / Zbase_ac
```

In this particular RMS study, the dynamic voltage-source block directly fixes the grid-bus voltage magnitude and angle while its active- and reactive-power limits are not reached. Consequently, `R1` and `X1` are retained as source-device data but are not the coupling impedance used by that ideal voltage-source RMS block. The explicit coupling impedance is provided by `TrafoGFL_1` and `TrafoGFL_2`.

### 4.3. Coupling transformers

Both transformers are ordinary passive two-winding transformer devices. Despite the historical `TrafoGFL` name, they do not contain the converter controller.

| Device | Parameter | Value | Meaning |
|---|---|---:|---|
| `TrafoGFL_1` | `rate` | 100 MVA | Operational rating |
| `TrafoGFL_1` | `R` | 0.01 p.u. | Series resistance |
| `TrafoGFL_1` | `X` | 0.05 p.u. | Series reactance |
| `TrafoGFL_1` | `tap_module` | 1.0 p.u. | Fixed tap magnitude |
| `TrafoGFL_1` | `tap_phase` | 0 rad | Fixed phase shift |
| `TrafoGFL_1` | `HV` / `LV` | 90 / 90 kV | No voltage-ratio change |
| `TrafoGFL_2` | Same values | Same values | Symmetrical terminal |

The transformers provide the station resistance and reactance. The standalone VSC model therefore uses zero internal converter resistance for this example to avoid duplicating losses.

### 4.4. Voltage-source converters

| Device | Parameter | Value | Units and purpose |
|---|---|---:|---|
| `VSC_1` | `rate` | 100 | MVA rating |
| `VSC_1` | `control1` | `Vm_dc` | DC-voltage control |
| `VSC_1` | `control1_val` | 1.0 | p.u. DC-voltage target |
| `VSC_1` | `control2` | `Qac` | AC reactive-power control |
| `VSC_1` | `control2_val` | 0.0 | MVAr target in the static power flow |
| `VSC_1` | `alpha1` | 0.0 | Constant converter-loss coefficient |
| `VSC_1` | `alpha2` | 0.0 | Linear converter-loss coefficient |
| `VSC_1` | `alpha3` | 0.0 | Quadratic converter-loss coefficient |
| `VSC_2` | `rate` | 100 | MVA rating |
| `VSC_2` | `control1` | `Pdc` | DC active-power control |
| `VSC_2` | `control1_val` | 20.0 | MW target in the static power flow |
| `VSC_2` | `control2` | `Qac` | AC reactive-power control |
| `VSC_2` | `control2_val` | 0.0 | MVAr target in the static power flow |
| `VSC_2` | `alpha1` | 0.0 | Constant converter-loss coefficient |
| `VSC_2` | `alpha2` | 0.0 | Linear converter-loss coefficient |
| `VSC_2` | `alpha3` | 0.0 | Quadratic converter-loss coefficient |

`control1_val` follows the units of the selected control. Enter `1.0` for the `Vm_dc` voltage target, but enter `20.0`, not `0.20`, for the static `Pdc` target because the static GUI property is in MW.

The loss coefficients are set to zero so that the power balance remains easy to inspect. The physical losses retained in the example are the transformer series losses and the DC-line resistive loss.

### 4.5. DC line

| Device | Parameter | Value | Meaning |
|---|---|---:|---|
| `HVDC_Line` | `rate` | 100 MVA | Operational rating |
| `HVDC_Line` | `R` | 0.005469679 p.u. | Static DC-line resistance |
| `HVDC_Line` | `from` | `Bus_DC_1` | Sending-side DC bus |
| `HVDC_Line` | `to` | `Bus_DC_2` | Receiving-side DC bus |

The per-unit resistance is obtained from:

```text
R_dc = (0.5 + 0.25 + 0.4) / Zbase_dc
     = 1.15 / 210.25
     = 0.00546967895 p.u.
```

Only `R` is part of the static `DcLine` device. The series dynamic coefficient `l_dc = 0.05 p.u.` is introduced in the RMS model described in Section 5.5.

## 5. RMS dynamic models

### 5.1. Model assignment summary

| Static device | RMS model | Main function |
|---|---|---|
| `Generator_Grid_1`, `Generator_Grid_2` | Voltage source | Stiff external-grid voltage and angle reference |
| `TrafoGFL_1`, `TrafoGFL_2` | Transformer 2W | Passive AC branch equations |
| `VSC_1` | Gfl VSC hvdc | Set `control1 = Vm_dc`, `control2 = Qac` |
| `VSC_2` | Gfl VSC hvdc | Set `control1 = Pdc`, `control2 = Qac` |
| `HVDC_Line` | DC line explicit state | DC-current dynamics and terminal powers |

Bus RMS connection shells are managed by VeraGrid when the device models are attached. They provide `Vm` and `Va` on AC buses and `Vdc` on DC buses.

### 5.2. External-grid voltage-source model

The two source generators use an RMS voltage-source equivalent. Its purpose is to maintain the solved AC-bus voltage while allowing the exchanged active and reactive powers to be determined by the network.

| Dynamic parameter | Value | Description |
|---|---:|---|
| `Vg0` | Initialized from power flow | Voltage-magnitude reference |
| `Ag0` | Initialized from power flow | Voltage-angle reference |
| `Pmax_G` | 9.999 p.u. | Maximum active power |
| `Pmin_G` | -9.999 p.u. | Minimum active power |
| `Qmax_G` | 9.999 p.u. | Maximum reactive power |
| `Qmin_G` | -9.999 p.u. | Minimum reactive power |

Within these wide limits, the block imposes `Vm = Vg0` and `Va = Ag0`. If a limit is reached, the corresponding voltage constraint is replaced by the saturated power constraint.

For an exact reproduction, drag `Voltage source` from the generator RMS Library. A complete synchronous-generator template is a different physical model and will not reproduce the same stiff-grid behaviour without additional parameterization.

### 5.3. Passive transformer model

Drag `Transformer 2W` from the transformer RMS Library for both `TrafoGFL` devices. This model:

- reads the transformer conductance, susceptance, tap magnitude and tap angle from the static object;
- calculates `Pf`, `Qf`, `Pt` and `Qt` from the terminal voltage magnitudes and angles;
- contains no converter control loops and no additional dynamic parameters for this exercise.

Do not assign a combined transformer-plus-GFL model. In the standalone architecture, all converter electrical and control equations belong to the `VSC` object.

### 5.4. Standalone HVDC GFL VSC model

Drag the single `Gfl VSC hvdc` block into each VSC RMS editor. Open **Block Properties** and select the required `control1` and `control2` values. The control combinations are properties of one model; they are not separate Library blocks.

#### 5.4.1. Structural properties

| Property | `VSC_1` | `VSC_2` | Description |
|---|---|---|---|
| `control1` | `Vm_dc` | `Pdc` | Active-axis outer-loop mode |
| `control2` | `Qac` | `Qac` | Reactive-axis outer-loop mode |
| `cdc` | 0.40 p.u. | 0.40 p.u. | DC-link capacitance represented by each converter |
| `name` | `VSC_1` | `VSC_2` | Display name of the block |

The structural control properties must agree with the static VSC controls. Changing only the static `control1` property does not rebuild an already-created dynamic block.

#### 5.4.2. Controller and electrical parameters

| Parameter | Value | Function |
|---|---:|---|
| `Cdc` | 0.40 p.u. | DC-link capacitance in the converter power-balance equation |
| `Kp_vdc` | 0.20 | Proportional gain of the DC-voltage outer loop |
| `Ki_vdc` | 1.00 | Integral gain of the DC-voltage outer loop |
| `Kp_pol` | 0.02 | Proportional gain used by the active- and reactive-power outer loops |
| `Ki_pol` | 0.10 | Integral gain used by the active- and reactive-power outer loops |
| `Kp_icl` | 0.20 | Proportional gain of the inner current loop |
| `Ki_icl` | 5.00 | Integral gain of the inner current loop |
| `Kp_vac` | 0.10 | Proportional gain of the AC-voltage loop; retained but inactive with `Qac` control |
| `Ki_vac` | 1.00 | Integral gain of the AC-voltage loop; retained but inactive with `Qac` control |
| `R` | 0.00 p.u. | Internal converter-interface resistance; zero avoids duplicating transformer resistance |
| `L` | 0.05 p.u. | Internal converter-interface inductive coefficient |
| `Kp_pll` | 0.001 | PLL proportional gain |
| `Ki_pll` | 0.10 | PLL integral gain |
| `fn` | 50 Hz | PLL nominal frequency |
| `I_max` | 1.20 p.u. | Internal current-reference limit |
| `a0`, `a1`, `a2` | 0.0 | Converter loss coefficients, mapped from static `alpha1`, `alpha2`, `alpha3` |

`I_max` is an internal model constant in the reference template rather than an event parameter. The voltage-control gains are relevant to `VSC_1`; the power-control gains are relevant to `VSC_2`; the current loop and PLL are active at both terminals.

#### 5.4.3. References and initialization

| Dynamic reference | Initialization | Used by |
|---|---|---|
| `Vdc_ref` | Solved DC voltage | `Vm_dc` mode on `VSC_1` |
| `P_ref` | Solved converter active power | `Pdc` mode on `VSC_2` and the RMS events |
| `Q_ref` | Solved converter reactive power | `Qac` mode on both VSCs |
| `Vm_ac_ref` | Solved AC voltage magnitude | Available for `Vm_ac` mode, inactive here |

References are initialized from the converged power flow. This avoids an artificial transient at `t = 0` and ensures that the controller states start at the operating point.

The principal internal functions are:

1. a PLL that follows the AC-grid angle;
2. an outer `Vdc` or `Pdc` loop that produces the active-axis current reference;
3. an outer `Qac` loop that produces the reactive-axis current reference;
4. a current-reference limiter;
5. the **d-axis current PI controller** and **q-axis current PI controller**, which regulate the respective currents and produce voltage corrections `y_vd_hat` and `y_vq_hat` for the electrical equations (formerly labelled `vd hat` and `vq hat`);
6. the converter AC/DC power balance;
7. the DC-link capacitor equation.

The converter power balance includes the dynamic capacitor term:

```text
Pf_dc + Pt_ac - Ploss - Cdc * Vdc * dVdc/dt = 0
```

### 5.5. Dynamic DC-line model

The static `DcLine` resistance is supplemented by the `DC line explicit state` model available in the device RMS Library. Use the following variables when checking the model in the Dynamic Editor.

| Symbol | Role | Mapping or value | Description |
|---|---|---|---|
| `Vdcf` | Input | From-side DC voltage | DC voltage at `Bus_DC_1` |
| `Vdct` | Input | To-side DC voltage | DC voltage at `Bus_DC_2` |
| `If_dc` | State variable and output | DC-line current | Positive from bus 1 to bus 2 |
| `Pf` | Algebraic variable and output | From-side active power | `Vdcf * If_dc` |
| `Pt` | Algebraic variable and output | To-side active power | `-Vdct * If_dc` |
| `r_dc` | Fixed parameter | 0.005469679 p.u. | Copied from the static line resistance |
| `l_dc` | Fixed parameter | 0.05 p.u. | Series dynamic coefficient |

Use these exact external mappings to reproduce the reference block:

| Variable | `VarPowerFlowReferenceType` mapping |
|---|---|
| `Vdcf` | `Vmf` |
| `Vdct` | `Vmt` |
| `If_dc` | `If_dc` |
| `Pf` | `Pf` |
| `Pt` | `Pt` |

`Vmf` and `Vmt` are used here as the branch-side semantic slots for the two DC-voltage inputs. The connected DC bus models supply their `Vdc` variables through the branch connection logic.

The line block implements the following standard state-space relations:

```text
dIf_dc/dt = (Vdcf - Vdct - r_dc * If_dc) / l_dc
Pf = Vdcf * If_dc
Pt = -Vdct * If_dc
```

`If_dc`, `Pf` and `Pt` are initialized directly from the solved power flow. They must not appear in `init_eqs`, because an explicit initialization equation would overwrite values that are already authoritative. At the nominal operating point, the current magnitude is approximately `0.20 p.u.`.

When creating the model manually, semantic mappings are as important as variable names. Map both terminal voltages, `If_dc`, `Pf` and `Pt` with the corresponding from/to RMS references offered by the editor. A variable called `Vdcf` without a terminal mapping is not connected to the bus.

## 6. GUI construction procedure

### 6.1. Create the circuit

1. Open VeraGrid and create a new circuit.
2. Set the circuit name to `Point-to-point HVDC RMS Vdc-control example`.
3. Set `Sbase = 100 MVA` and `fBase = 50 Hz`.
4. Save the working file before starting the live construction.

### 6.2. Build the static diagram

1. Drag six buses from the **Library** to the schematic.
2. Rename and configure the buses according to Section 4.1.
3. Set `is_dc = True` on `Bus_DC_1` and `Bus_DC_2` before drawing the VSCs and DC line.
4. Set `is_slack = True` on `Bus_Grid_1` and `Bus_Grid_2`.
5. Right-click each grid bus and add its generator injection.
6. Draw `TrafoGFL_1` between `Bus_VSC_1` and `Bus_Grid_1`.
7. Draw `TrafoGFL_2` between `Bus_VSC_2` and `Bus_Grid_2`.
8. Draw `VSC_1` between `Bus_DC_1` and `Bus_VSC_1`.
9. Draw `VSC_2` between `Bus_DC_2` and `Bus_VSC_2`.
10. Draw a DC line between `Bus_DC_1` and `Bus_DC_2` and name it `HVDC_Line`.
11. Enter all device values from Section 4.
12. Select each branch and verify its final `bus_from` and `bus_to` properties.

When the diagram is complete, count the objects before proceeding:

| Object type | Expected count |
|---|---:|
| Buses | 6 |
| Generators | 2 |
| Two-winding transformers | 2 |
| VSCs | 2 |
| DC lines | 1 |
| Loads | 0 |
| Aggregated HVDC lines | 0 |

### 6.3. Check the static model

Run a power flow from the upper toolbar only after checking the control allocation.

Recommended power-flow settings for the reference case are:

| Parameter | Value |
|---|---:|
| Solver | Newton-Raphson (`NR`) |
| Tolerance | `1e-8` |
| Maximum iterations | 100 |
| Retry with other methods | Enabled |
| Reactive-power control | Disabled for this exercise |
| Tap-module control | Disabled |
| Tap-phase control | Disabled |

Before building the dynamic models, verify that:

- the power flow converges;
- `VSC_1` maintains approximately `1.0 p.u.` at the DC-voltage-controlled terminal;
- `VSC_2` transfers approximately `20 MW`;
- both converter reactive-power targets are approximately `0 MVAr`;
- both AC grid buses remain close to `1.0 p.u.`;
- the DC buses have non-zero power transfer and non-zero DC current.

The non-zero `20 MW` initial transfer is intentional. Starting the algebraic DC system at exactly zero current exposes a singular operating point for this formulation.

### 6.4. Verify the RMS Library

No catalogue import is required for this exercise. Open the RMS editor of each device and verify that its contextual **Library -> Devices** branch contains:

- `Voltage source` for each grid generator;
- `Transformer 2W` for each coupling transformer;
- one `Gfl VSC hvdc` block for each VSC;
- `DC line explicit state` for `HVDC_Line`.

For the two converters, use the same `Gfl VSC hvdc` block and choose the control combination in **Block Properties**. Do not create separate Vdc/Q and Pdc/Q model variants.

### 6.5. Assign and edit the RMS models

For each device:

1. Right-click the device and open the **RMS editor**.
2. Keep the automatically provided grid-connection blocks.
3. Drag the required device block from **Library -> Devices** onto the canvas.
4. Connect its ports to the corresponding grid-connection ports.
5. Double-click the model and inspect **Block properties**.
6. Confirm the structural options and parameter values from Section 5.
7. Use **Validate** or **Validate all code** before applying the model.
8. Apply the block changes.
9. Save the complete device model back to the grid and confirm the **Model saved** notification.

Use this order to reduce connection mistakes:

1. both grid voltage sources;
2. both passive transformers;
3. `VSC_1` with `Vm_dc/Qac`;
4. `VSC_2` with `Pdc/Qac`;
5. the R-L model of `HVDC_Line`.

In **Block properties**:

- **Variables** defines inputs, algebraic variables, states, derivatives and outputs;
- **Parameters** distinguishes fixed parameters from dynamic parameters;
- **DAE model** contains the algebraic, state and initialization equations;
- the mapping column connects symbolic variables to the static device and network quantities.

`P_ref`, `Q_ref`, `Vdc_ref` and `Cdc` are dynamic parameters because they form part of the runtime/event interface. Physical line coefficients such as `r_dc` and `l_dc` are fixed parameters.

## 7. RMS events

Create one RMS event group:

| Property | Value |
|---|---|
| Name | `HVDC RMS Vdc control` |
| Active | `True` |

The disturbance is applied to the dynamic `P_ref` parameter of `VSC_2`. It is not applied to the static `control1_val` field.

Let `p0` be the initialized dynamic power reference obtained from the power-flow result. In this case, `p0` is approximately `0.20 p.u.`. The first event is:

| Device | Time | Parameter | Value | Transition |
|---|---:|---|---:|---|
| `VSC_2` | 5 s | `P_ref` | `p0 - 0.01 p.u.` (approximately 0.19 p.u.) | Step |

For a two-transition conference demonstration, restore the original set point with:

| Device | Time | Parameter | Value | Transition |
|---|---:|---|---:|---|
| `VSC_2` | 15 s | `P_ref` | `p0` (approximately 0.20 p.u.) | Step |

> **Reference-script note:** the current Python source creates both event records with the value `p0 - 0.01`. In that literal configuration, the second record causes no additional transition. The saved reference `.veragrid` case uses approximately `0.19 p.u.` at 5 s and restores approximately `0.20 p.u.` at 15 s. Confirm the intended version before the live session.

To create the events from the GUI:

1. Select `VSC_2`.
2. Add an RMS event to the selected device.
3. Create or select the `HVDC RMS Vdc control` group.
4. Select the dynamic parameter `P_ref`.
5. Enter the event time, target value and `Step` transition.
6. Inspect the final records under **Database -> Dynamic -> RMS Events Group** and **RMS Event**.

## 8. Simulation settings

Use the following RMS options:

| Parameter | Value |
|---|---:|
| Simulation time | 30 s |
| Time step | 0.002 s |
| Integration method | DAE Backward Euler |
| Initialization method | Explicit |
| Tolerance | `1e-6` |
| Maximum iterations | 80 |
| Events group | `HVDC RMS Vdc control` |

> **Required tolerance:** set the RMS tolerance to `1e-6`. Do not retain the GUI initial value of `1e-4` for this case. With a time step of `0.002 s`, the `1e-4` tolerance can accept the small Backward Euler residuals of the explicit PI integrator states without updating those states. The controllers then appear numerically frozen and the DC-voltage response is reduced to round-off-level variations. A `1e-6` tolerance reproduces the reference scripted response.

Backward Euler is an implicit, robust integration method suitable for the differential-algebraic converter and network equations used in the exercise.

After the simulation, always check both status indicators:

- **well initialized:** the RMS initial state is consistent with the solved power flow;
- **converged:** the integration completed successfully for the selected event group.

## 9. Results and expected response

Open **Results -> RMS Dynamic**. Create plots for the following quantities.

### 9.1. DC voltages

Plot `Vdc` for `Bus_DC_1` and `Bus_DC_2`.

Expected behaviour:

- both voltages start close to `1.0 p.u.`;
- `VSC_1` acts to restore its DC-voltage reference after the `P_ref` step at `VSC_2`;
- the two terminal voltages differ slightly because of the DC-line resistance and current;
- the response should remain inside approximately `0.99-1.01 p.u.` for this small disturbance.

### 9.2. Converter powers

Plot the available VSC active powers, particularly `Pf_vsc` and `Pt`, for both converters.

Expected behaviour:

- `VSC_2` follows the active-power reference change;
- `VSC_1` changes its power exchange to maintain the DC voltage and balance the link;
- the active-power change is approximately `0.01 p.u.`, equivalent to `1 MW`;
- reactive power remains close to its zero reference, apart from the control transient.

### 9.3. DC-line current and powers

Plot `If_dc`, `Pf` and `Pt` for `HVDC_Line`.

Expected behaviour:

- the initial current magnitude is approximately `0.20 p.u.`;
- the current changes dynamically rather than instantaneously because of `l_dc`;
- `Pf` is approximately `Vdcf * If_dc`;
- `Pt` has the opposite sign because branch power is defined with power entering each terminal;
- the difference in terminal power magnitudes represents the DC-line resistive loss.

Power signs depend on the branch terminal convention. A forward transfer does not imply that `Pf` and `Pt` have equal positive values. Check the balance and magnitudes rather than comparing signs without considering the terminal definition.

### 9.4. AC-grid voltages

Plot `Vm` and `Va` for `Bus_Grid_1` and `Bus_Grid_2`.

The voltage-source models keep the external-grid buses stiff. Only small changes are expected for this disturbance.

## 10. Troubleshooting

| Symptom | Likely cause | Corrective action |
|---|---|---|
| A VSC cannot be created | Both connected buses have the same AC/DC type | Set the DC terminal bus to `is_dc = True` before drawing the VSC |
| The wrong branch appears between DC buses | An aggregated `HvdcLine` was selected | Replace it with a physical `DcLine` |
| Power flow is under-determined | No VSC controls `Vm_dc` | Set `VSC_1 control1 = Vm_dc` |
| Power flow is over-constrained | Both VSCs impose incompatible DC-voltage controls | Use `Vm_dc` only at `VSC_1` and `Pdc` at `VSC_2` |
| Static transfer is 0.2 MW instead of 20 MW | Per-unit value entered in a static MW field | Set `VSC_2 control1_val = 20.0` MW |
| Dynamic event changes power by 0.01 MW instead of 1 MW | Static units were assumed for `P_ref` | Enter dynamic event values in p.u.; `0.01 p.u. = 1 MW` |
| Event parameter is not available | The VSC RMS model was not saved or the wrong VSC template was used | Save the `Pdc/Q` model on `VSC_2` and target its dynamic `P_ref` |
| Event at 15 s produces no visible response | Both step records have the same target | Set the second target to `p0` if a restoration step is intended |
| RMS initialization fails near zero current | DC link was initialized with zero active-power transfer | Restore the `20 MW` static `Pdc` set point and rerun the power flow |
| DC current has no dynamics | `HVDC_Line` has only its static resistance | Add the R-L RMS model with `l_dc = 0.05` |
| DC voltage behaves algebraically or becomes singular | `Cdc` is missing or the wrong VSC model was assigned | Use the standalone HVDC GFL VSC template with `Cdc = 0.40` |
| Losses are much larger than expected | Resistance or converter-loss coefficients were counted twice | Keep VSC `R = 0` and `alpha1 = alpha2 = alpha3 = 0`; retain transformer and DC-line resistance |
| Transformer model shows converter controls | A combined GFL transformer model was assigned | Replace it with the passive `Transformer 2W` RMS model |
| Model changes disappear after closing the editor | Changes were applied only inside Block Properties | Apply the block changes and then save the complete device model to the grid |
| A correctly named variable remains disconnected | Semantic mapping was not assigned | Set the appropriate `VarPowerFlowReferenceType` mapping in Block Properties |

## 11. Final checklist

Before the session starts, verify the following items:

- [ ] Circuit base is `100 MVA` and frequency is `50 Hz`.
- [ ] There are four AC buses at `90 kV` and two DC buses at `145 kV`.
- [ ] `Bus_Grid_1` and `Bus_Grid_2` are slack buses.
- [ ] `Bus_DC_1` and `Bus_DC_2` have `is_dc = True`.
- [ ] Each VSC is connected `from DC` to `to AC`.
- [ ] `VSC_1` uses `Vm_dc = 1.0 p.u.` and `Qac = 0 MVAr`.
- [ ] `VSC_2` uses `Pdc = 20 MW` and `Qac = 0 MVAr`.
- [ ] Both VSC ratings are `100 MVA` and all converter-loss coefficients are zero.
- [ ] Both transformers use `R = 0.01`, `X = 0.05` and `rate = 100 MVA`.
- [ ] The DC line is a `DcLine` with `R = 0.005469679 p.u.` and `rate = 100 MVA`.
- [ ] The static power flow converges before any RMS model is edited.
- [ ] Both generators use the stiff voltage-source RMS equivalent.
- [ ] Both transformers use the passive two-winding RMS model.
- [ ] `VSC_1` uses the standalone `Vdc/Q` GFL model with `Cdc = 0.40`.
- [ ] `VSC_2` uses the standalone `Pdc/Q` GFL model with `Cdc = 0.40`.
- [ ] The DC-line RMS model contains `r_dc = 0.005469679` and `l_dc = 0.05`.
- [ ] Every model has been validated, applied and saved to its device.
- [ ] The RMS event group is selected in the simulation options.
- [ ] The event targets the dynamic `P_ref` of `VSC_2`.
- [ ] The intended second event value has been confirmed before the live demo.
- [ ] Simulation time is `30 s`, time step is `0.002 s`, integration is DAE Backward Euler and initialization is Explicit.
- [ ] The result layout includes DC voltage, VSC power, DC-line current/power and AC-grid voltage plots.

The exercise is complete when the static power flow converges, the RMS model reports successful initialization and convergence, and the plotted response is consistent with the converter-control allocation described in Section 3.2.
