# Inverse Park transform

### Purpose

The inverse Park transform converts rotating-frame `dq` or `dq0` quantities back into stationary or phase-domain signals.

### Behavior

- Receives `d`, `q`, optionally `0`, and one electrical angle.
- Produces a signal in `abc` form or in one equivalent stationary representation.

### Characteristics

- Essential for turning synchronous-frame controller outputs into phase-domain commands.

## Characteristic equations

$$
\begin{bmatrix}x_A \\ x_B \\ x_C\end{bmatrix} = T_P^{-1}(\theta) \begin{bmatrix}x_d \\ x_q \\ x_0\end{bmatrix}
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `x_d` | d-axis input component | model-dependent |
| Input | `x_q` | q-axis input component | model-dependent |
| Input | `x_0` | Zero-sequence input component in dq0 variants | model-dependent |
| Input | `theta` | Electrical angle of the rotating frame | rad |
| Output | `x_A` | Phase-A reconstructed quantity | model-dependent |
| Output | `x_B` | Phase-B reconstructed quantity | model-dependent |
| Output | `x_C` | Phase-C reconstructed quantity | model-dependent |

## How to use it

- Use it after a synchronous-frame control law when the final command must be expressed in phase variables.
- Make sure the same angle convention is used as in the forward Park transform.
