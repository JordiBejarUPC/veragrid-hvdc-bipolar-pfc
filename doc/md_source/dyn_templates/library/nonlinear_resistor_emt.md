# Nonlinear resistor EMT

The nonlinear resistor is an EMT shunt element whose current is a nonlinear
function of terminal voltage. It can represent surge arresters, voltage-
dependent resistors, and simplified saturation-like conductances.

## Characteristic relation

$$
i = f(v)
$$

The selected curve parameters define `f`. The instantaneous relation is
evaluated independently for every enabled phase.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `v_X` | Phase-to-reference voltage | V or p.u. |
| Output | `i_X` | Current drawn by the element | A or p.u. |
| Parameter | Curve settings | Shape and scale of `f` | model-dependent |

By default the block exposes phases A, B, and C. Neutral is enabled only when
the network topology explicitly requires it.
