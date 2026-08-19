# Absolute value

The Absolute value block returns the non-negative magnitude of its scalar
input. It is commonly used before limits, comparisons, and magnitude-based
protection logic.

## Characteristic equation

$$
y = |u|
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `u` | Signed input signal | model-dependent |
| Output | `y` | Absolute magnitude | same as `u` |

The operation is algebraic and is non-differentiable only at `u = 0`.
