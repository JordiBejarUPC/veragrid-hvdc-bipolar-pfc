# Limit

### Purpose

A limit block constrains a signal between lower and upper bounds.

### Behavior

- Receives one signal.
- Clips the signal to a valid interval.
- Protects downstream blocks from unrealistic or unsafe command values.

### Characteristics

- Often used around current references, voltage references, modulation indices, and mechanical commands.

## Characteristic equations

$$
y = \min(\max(x, x_{min}), x_{max})
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Signal to be limited | model-dependent |
| Output | `yo` | Limited output signal | model-dependent |
| Parameter | `vmin` | Lower limit | model-dependent |
| Parameter | `vmax` | Upper limit | model-dependent |

## How to use it

- Use it whenever a physical variable cannot exceed a known range.
- Make sure the limits use the same units as the signal being limited.
