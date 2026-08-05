# Delay and timer

### Purpose

Delay and timer blocks represent time-based logic such as waiting, holding, and event timing.

### Behavior

- A delay block reproduces an input after a specified time lag.
- A timer block measures elapsed time since one triggering condition.
- Some variants support reset, hold, or bypass logic.

### Characteristics

- Useful in protection, sequence logic, and staged control actions.

## Characteristic equations

$$
y(t) = x(t - T_d)
$$

$$
\frac{d\tau}{dt} = 1
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Signal or trigger input | model-dependent |
| Output | `yo` | Delayed or timer-related output | model-dependent |
| Variable | `tau` | Internal elapsed-time state in timer-like variants | s |
| Parameter | `Td` | Delay time | s |
| Parameter | `Treset` | Reset time or reset-related timing parameter in timer variants | s |

## How to use it

- Use delay blocks for pure transport-like timing.
- Use timer blocks when logic depends on how long a condition has been active.
