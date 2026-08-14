# RLC Combo

Combined EMT passive branch with configurable R, L, and C terms.

## Internal composition

RLC Combo is a composite phase-selective shunt. It can include any combination
of resistive, inductive, and capacitive child branches and builds one copy per
enabled phase. The branches share the same terminal voltage and their currents
are combined into the exported network injection.

General options control the R/L/C inclusion flags, phase mask, star connection,
and direct component values. Applying a structural change rebuilds the child
blocks while preserving surviving ports by semantic phase identity.

The default is a grounded-star, three-wire ABC block with R, L, and C enabled.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Terminal | `p` | Positive terminal | model-dependent |
| Terminal | `n` | Negative terminal | model-dependent |
| Parameter | `R` | Resistance | ohm |
| Parameter | `L` | Inductance | H |
| Parameter | `C` | Capacitance | F |

## Constitutive relations

$$
i_R = \frac{v}{R}, \qquad
\frac{di_L}{dt} = \frac{v}{L}, \qquad
i_C = C\frac{dv}{dt}
$$

## How to use it

- Disable components that are not part of the physical shunt.
- Keep enabled component values inside their valid ranges.
- Match phases and connection type to the static topology before initialization.
