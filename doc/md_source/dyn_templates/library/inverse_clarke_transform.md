# Inverse Clarke transform

### Purpose

The inverse Clarke transform converts stationary-frame quantities back into three-phase `abc` quantities.

### Behavior

- Receives `alpha-beta` or `alpha-beta-zero` components.
- Produces three-phase outputs.
- Is used after current or voltage control stages that operate in orthogonal coordinates.

### Characteristics

- Available in power-invariant and non-power-invariant variants.
- Commonly paired with Clarke and Park transform blocks.

## Characteristic equations

$$
\begin{bmatrix}x_A \\ x_B \\ x_C\end{bmatrix} = T_C^{-1} \begin{bmatrix}x_\alpha \\ x_\beta \\ x_0\end{bmatrix}
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `x_alpha` | Stationary alpha-axis component | model-dependent |
| Input | `x_beta` | Stationary beta-axis component | model-dependent |
| Input | `x_0` | Zero-sequence component in the variants that use it | model-dependent |
| Output | `x_A` | Phase-A reconstructed quantity | model-dependent |
| Output | `x_B` | Phase-B reconstructed quantity | model-dependent |
| Output | `x_C` | Phase-C reconstructed quantity | model-dependent |

## How to use it

- Use this block when a controller works in orthogonal coordinates but the actuator or plant requires three-phase outputs.
- Make sure the chosen inverse transform matches the forward transform convention used upstream.
