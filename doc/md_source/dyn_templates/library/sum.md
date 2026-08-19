# Sum

The Sum block combines a configurable number of positive and negative input
signals. General options controls how many addends and subtrahends are exposed
as ports.

## Characteristic equation

$$
y = \sum_i u_i - \sum_j v_j
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `add_i` | Inputs added to the result | model-dependent |
| Input | `subtract_j` | Inputs subtracted from the result | model-dependent |
| Output | `y` | Algebraic sum | same as the inputs |

All connected signals should use compatible units.
