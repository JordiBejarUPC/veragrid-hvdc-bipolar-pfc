# Park transform

### Purpose

The Park transform converts stationary or phase-domain quantities into a rotating `dq` or `dq0` reference frame.

### Behavior

- Receives a signal set plus one electrical angle.
- Produces components aligned with the rotating frame.
- Is fundamental in vector control, PLLs, and synchronous-frame current or voltage control.

### Characteristics

- Available in `dq` and `dq0` variants.
- Typically paired with inverse Park transform blocks.

## Characteristic equations

$$
\begin{bmatrix}x_d \\ x_q \\ x_0\end{bmatrix} = T_P(\theta) \begin{bmatrix}x_A \\ x_B \\ x_C\end{bmatrix}
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `x_A` | Phase-A or stationary-frame input quantity | model-dependent |
| Input | `x_B` | Phase-B or stationary-frame input quantity | model-dependent |
| Input | `x_C` | Phase-C or stationary-frame input quantity | model-dependent |
| Input | `theta` | Electrical angle of the rotating frame | rad |
| Output | `x_d` | d-axis component aligned with the chosen frame | model-dependent |
| Output | `x_q` | q-axis quadrature component aligned with the chosen frame | model-dependent |
| Output | `x_0` | Zero-sequence component in dq0-capable variants | model-dependent |

## How to use it

- Use it when vector-control laws or synchronous-frame measurements are needed.
- Make sure the angle source is consistent with the frame definition used in the rest of the model.
