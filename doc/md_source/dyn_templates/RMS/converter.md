# Converter

This model represents the converter submodel used within the RMS grid-forming VSC model.

### Purpose

It is the compact RMS VSC block built by `build_vsc_rms()`.

### Behavior

- Uses AC terminal voltage magnitude/angle and DC voltage input.
- Computes compact active-power balance behavior with configurable losses.
- Exposes a reactive-power reference output channel.

### Characteristics

- Compact averaged converter model.
- Intended for RMS converter-level studies.
- Simpler than the EMT converter hierarchy.
## Characteristic equations

Representative equations are:

$$
i_m = \frac{\sqrt{P_t^2 + Q_{t,ref}^2}}{V_{m,t}}
$$

$$
P_f + P_t = \alpha_1 + \alpha_2 i_m + \alpha_3 i_m^2
$$

This is a compact power-balance and loss model, not a detailed control hierarchy.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `Vm_t` | AC terminal voltage magnitude seen by the converter model | pu |
| Input | `Va_t` | AC terminal voltage angle seen by the converter model | rad |
| Input | `Vdc` | DC-side voltage input used by the compact converter balance | pu |
| Output | `Pf_vsc` | Converter active power on the from side of the compact RMS model | pu |
| Output | `Pt` | Converter active power on the to side of the compact RMS model | pu |
| Output | `Qt_ref` | Reactive power reference channel exposed by the block | pu |
| Variable | `Pf_vsc` | Algebraic active-power variable representing converter from-side power | pu |
| Variable | `Pt` | Algebraic active-power variable representing converter to-side power | pu |
| Variable | `im` | Effective current magnitude used in the loss expression | pu |
| Parameter | `alpha1` | Constant term of the converter loss polynomial | model units |
| Parameter | `alpha2` | Linear coefficient of the converter loss polynomial | model units |
| Parameter | `alpha3` | Quadratic coefficient of the converter loss polynomial | model units |

## How to use it

- Use it when you want a very compact RMS converter representation.
- Do not interpret it as a detailed EMT grid-forming hardware model.
