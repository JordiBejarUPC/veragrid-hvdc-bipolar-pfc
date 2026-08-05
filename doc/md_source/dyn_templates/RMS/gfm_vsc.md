# GFM VSC

This model represents a positive-sequence RMS grid-forming voltage-source converter.

### Purpose

Represent a compact RMS grid-forming VSC through power-balance relationships and terminal power channels.

### Behavior

- Uses AC terminal voltage magnitude and angle plus DC voltage input.
- Computes a compact active-power balance relation with configurable loss coefficients.
- Exposes active-power channels on both sides of the converter representation and one reactive-power reference channel.

### Characteristics

- Very compact averaged converter representation.
- Suitable for high-level RMS converter behavior studies.
- Simpler than the EMT converter family and simpler than a detailed RMS converter control hierarchy.
## Characteristic equations

$$
i_m = \frac{\sqrt{P_t^2 + Q_{t,ref}^2}}{V_{m,t}}
$$

$$
P_f + P_t = \alpha_1 + \alpha_2 i_m + \alpha_3 i_m^2
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `Vm_t` | AC terminal voltage magnitude seen by the converter model | pu |
| Input | `Va_t` | AC terminal voltage angle seen by the converter model | rad |
| Input | `Vdc` | DC-side voltage input | pu |
| Output | `Pf_vsc` | Active power at the converter from side | pu |
| Output | `Pt` | Active power at the converter to side | pu |
| Output | `Qt_ref` | Reactive-power reference channel exported by the model | pu |
| Variable | `Pf_vsc` | Algebraic from-side active-power variable | pu |
| Variable | `Pt` | Algebraic to-side active-power variable | pu |
| Variable | `Qt_ref` | Runtime reactive-power reference used by the compact model | pu |
| Variable | `im` | Effective current magnitude used by the loss model | pu |
| Parameter | `alpha1` | Constant term of the converter loss polynomial | model units |
| Parameter | `alpha2` | Linear coefficient of the converter loss polynomial | model units |
| Parameter | `alpha3` | Quadratic coefficient of the converter loss polynomial | model units |

## How to use it

- Use it when you want a very compact RMS converter representation.
- Do not interpret it as a detailed EMT-style grid-forming implementation.
