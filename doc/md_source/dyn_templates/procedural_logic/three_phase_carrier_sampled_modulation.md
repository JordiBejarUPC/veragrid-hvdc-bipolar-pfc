# Three-phase carrier sampled modulation

## Purpose

Samples three modulation references at carrier half-period boundaries and retains the sampled values for use by switching logic.

## Configuration

- **Modulation A/B/C**: source DAE variables.
- **Sample mode A/B/C**: retained sampled outputs.
- **Switching frequency**: runtime angular frequency in radians per second.
- **Carrier phase**: runtime phase offset.

## Runtime behavior

Samples are updated only at carrier boundaries and remain constant between them. The logic requests those boundaries from the solver. Place it before a PWM entry that consumes the sampled modes during the same accepted update.
