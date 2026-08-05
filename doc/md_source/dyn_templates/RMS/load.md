# Load

This model represents a positive-sequence RMS load with voltage-dependent active and reactive power behavior.

### Purpose

It is a constant-power RMS load template.

### Behavior

- Uses bus voltage magnitude and angle as external inputs.
- Outputs active and reactive power consumed by the load.
- In the current implementation, active and reactive power are held directly at their setpoint values.
- The voltage inputs are present for network coupling and initialization consistency, but they do not modulate the power in the present model equations.

### Characteristics

- Algebraic-only RMS load model.
- Suitable as a simple constant-PQ dynamic load representation.
- Appropriate when no voltage-dependent or frequency-dependent load behavior is needed.
## Characteristic equations

$$
P_l = P_{l0}
$$

$$
Q_l = Q_{l0}
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `Vm` | Terminal voltage magnitude at the load bus | pu |
| Input | `Va` | Terminal voltage angle at the load bus | rad |
| Output | `Pl` | Active power consumed by the load | pu |
| Output | `Ql` | Reactive power consumed by the load | pu |
| Variable | `Pl0` | Internal active-power setpoint used by the algebraic equations | pu |
| Variable | `Ql0` | Internal reactive-power setpoint used by the algebraic equations | pu |
| Variable | `Pl` | Algebraic active-power variable exported to the network model | pu |
| Variable | `Ql` | Algebraic reactive-power variable exported to the network model | pu |
| Parameter | none | This template does not use a separate fixed parameter block | - |

## How to use it

- Use this template when you need a simple constant-PQ load in RMS studies.
- Do not use it when the load must change with voltage, frequency, or internal control logic.
