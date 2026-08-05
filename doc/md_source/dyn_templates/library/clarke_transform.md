# Clarke transform

### Purpose

The Clarke transform converts three-phase `abc` quantities into stationary orthogonal components such as `alpha-beta` or `alpha-beta-zero`.

### Behavior

- Receives phase quantities in `abc` form.
- Produces stationary-frame components.
- Is used to simplify control and analysis of three-phase systems.

### Characteristics

- Available in power-invariant and non-power-invariant variants.
- Often used ahead of Park transforms and vector-control blocks.

## Characteristic equations

$$
\begin{bmatrix}x_\alpha \\ x_\beta \\ x_0\end{bmatrix} = T_C \begin{bmatrix}x_A \\ x_B \\ x_C\end{bmatrix}
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `x_A` | Phase-A input quantity | model-dependent |
| Input | `x_B` | Phase-B input quantity | model-dependent |
| Input | `x_C` | Phase-C input quantity | model-dependent |
| Output | `x_alpha` | Stationary alpha-axis component | model-dependent |
| Output | `x_beta` | Stationary beta-axis component | model-dependent |
| Output | `x_0` | Zero-sequence component in dq0-capable variants | model-dependent |

## How to use it

- Use it when a three-phase signal must be analyzed or controlled in an orthogonal stationary frame.
- Make sure the chosen variant matches the intended power-scaling convention.
