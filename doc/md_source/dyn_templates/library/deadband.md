# Deadband

### Purpose

A deadband block suppresses small signal variations around a central region.

### Behavior

- Receives one signal.
- Outputs zero or a bypassed value while the input stays inside the deadband.
- Becomes active only when the input leaves the deadband interval.

### Characteristics

- Useful to avoid controller chatter around zero or around one operating point.

## Characteristic equations

$$
y = 0 \quad \text{if} \quad x_{min} \le x \le x_{max}
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Signal to be processed by the deadband | model-dependent |
| Output | `yo` | Deadband-processed signal | model-dependent |
| Parameter | `xmin` | Lower deadband threshold | model-dependent |
| Parameter | `xmax` | Upper deadband threshold | model-dependent |

## How to use it

- Use it to ignore small deviations that should not trigger control action.
- Make sure the thresholds are expressed in the same units as the input signal.
