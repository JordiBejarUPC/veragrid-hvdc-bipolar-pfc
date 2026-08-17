# Three-phase carrier PWM

## Purpose

Generates three retained gate signals by comparing phase modulation references with a triangular switching carrier.

## Configuration

- **Modulation A/B/C**: DAE modulation references.
- **Gate mode A/B/C**: retained gate outputs.
- **Switching frequency**: runtime angular frequency in radians per second.
- **Carrier phase**: runtime phase offset.

## Runtime behavior

The logic clips modulation references to the carrier range, schedules within-half-cycle switching instants and requests exact event boundaries. A near-zero switching frequency freezes the carrier on a very long interval. All three gate modes are written by this single entry.
