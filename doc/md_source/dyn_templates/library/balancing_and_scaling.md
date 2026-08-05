# Balancing and scaling blocks

### Purpose

Balancing and scaling blocks modify signal magnitude or create balanced signal sets from one reference signal.

### Behavior

- A scaling block multiplies, divides, offsets, or normalizes a signal.
- A balancing block generates several coordinated outputs, typically for multi-phase systems.

### Characteristics

- Useful for unit conversion, normalization, phase replication, and signal conditioning.

## Characteristic equations

$$
y = k x + b
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Signal to be scaled or balanced | model-dependent |
| Output | `yo` | Scaled output signal | model-dependent |
| Output | `yo_A` | Balanced phase-A output in balancing variants | model-dependent |
| Output | `yo_B` | Balanced phase-B output in balancing variants | model-dependent |
| Output | `yo_C` | Balanced phase-C output in balancing variants | model-dependent |
| Parameter | `k` | Scaling gain | model-dependent |
| Parameter | `b` | Bias or offset term | model-dependent |

## How to use it

- Use scaling blocks for unit adaptation or normalization.
- Use balancing blocks when one reference must be expanded into coordinated multi-phase signals.
