# Constant

The Constant block publishes a fixed scalar value. It is useful for set-points,
biases, limits, and any signal that must remain unchanged during a simulation.

## Characteristic equation

$$
y = k
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Output | `y` | Constant output signal | model-dependent |
| Parameter | `k` | Configured constant value | same as `y` |

The block has no input and no dynamic state. Changing `k` through General
options rebuilds the symbolic constant used by downstream equations.
