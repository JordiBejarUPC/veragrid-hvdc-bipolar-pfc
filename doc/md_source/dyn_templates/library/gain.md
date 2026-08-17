# Gain

The Gain block multiplies one input signal by a configurable scalar. It is the
basic proportional operation used for unit conversion, feedback gains, and
linear signal scaling.

## Characteristic equation

$$
y = k u
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `u` | Signal to scale | model-dependent |
| Output | `y` | Scaled signal | model-dependent |
| Parameter | `k` | Multiplicative gain | `y/u` |

The block is algebraic: it does not add a state or a delay to the signal path.
