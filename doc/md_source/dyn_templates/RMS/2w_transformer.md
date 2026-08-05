# 2W Transformer

This model represents a positive-sequence two-winding transformer for RMS studies.

### Purpose

It is a positive-sequence two-winding transformer RMS branch model.

### Behavior

- Uses from-side and to-side voltage magnitudes and angles.
- Computes active and reactive power at both transformer terminals.
- Includes series admittance, core-loss terms, magnetizing terms, and tap scaling.
- Represents tap module and tap phase shift as branch parameters.

### Characteristics

- Algebraic-only RMS transformer model.
- Appropriate for positive-sequence RMS network studies.
- Does not model EMT winding transients or magnetic saturation transients.
## Characteristic equations

$$
P_f = \frac{V_{mf}^2(g_{Fe}+g_t)}{(m v_{tap,f})^2} - \frac{g_t}{m v_{tap,f} v_{tap,t}}V_{mf}V_{mt}\cos(\theta_{hk}-\phi) - \frac{b_t}{m v_{tap,f} v_{tap,t}}V_{mf}V_{mt}\sin(\theta_{hk}-\phi-\phi_d)
$$

$$
Q_f = -\frac{V_{mf}^2(b_{mu}/2+b_t)}{(m v_{tap,f})^2} - \frac{g_t}{m v_{tap,f} v_{tap,t}}V_{mf}V_{mt}\sin(\theta_{hk}-\phi) + \frac{b_t}{m v_{tap,f} v_{tap,t}}V_{mf}V_{mt}\cos(\theta_{hk}-\phi-\phi_d)
$$

Equivalent expressions are used for the to-side terminal powers.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `Vmf` | From-side voltage magnitude | pu |
| Input | `Vaf` | From-side voltage angle | rad |
| Input | `Vmt` | To-side voltage magnitude | pu |
| Input | `Vat` | To-side voltage angle | rad |
| Output | `Pf` | Active power at the from-side transformer terminal | pu |
| Output | `Pt` | Active power at the to-side transformer terminal | pu |
| Output | `Qf` | Reactive power at the from-side transformer terminal | pu |
| Output | `Qt` | Reactive power at the to-side transformer terminal | pu |
| Variable | `Pf` | Algebraic from-side active-power variable | pu |
| Variable | `Pt` | Algebraic to-side active-power variable | pu |
| Variable | `Qf` | Algebraic from-side reactive-power variable | pu |
| Variable | `Qt` | Algebraic to-side reactive-power variable | pu |
| Parameter | `g` | Series conductance of the transformer branch equivalent | pu |
| Parameter | `b` | Series susceptance of the transformer branch equivalent | pu |
| Parameter | `gFe` | Core-loss conductance term | pu |
| Parameter | `bmu` | Magnetizing susceptance term | pu |
| Parameter | `m` | Tap magnitude factor | pu |
| Parameter | `phi` | Tap phase-shift angle | rad |
| Parameter | `vtap_f` | Virtual tap scaling applied on the from side | pu |
| Parameter | `vtap_t` | Virtual tap scaling applied on the to side | pu |

## How to use it

- Use it when transformer power transfer and tap representation are needed in RMS simulations.
- Do not use it when phase-domain or electromagnetic winding dynamics are required.
