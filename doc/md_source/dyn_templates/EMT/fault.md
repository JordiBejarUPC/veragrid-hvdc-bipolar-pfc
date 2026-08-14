# EMT fault

The EMT fault block inserts a configurable low-impedance path between selected
conductors or between conductors and ground. It is intended for transient fault
events and can be placed on either terminal side of the edited device.

## Characteristic relation

For a fault resistance `R_f`, each active fault path follows

$$
v_f = R_f i_f
$$

## General options

- Enabled phases and neutral/ground participation.
- Fault topology, such as phase-to-phase or three-phase fault.
- Placement on the from or to side of the host branch.
- Event and impedance parameters exposed by the selected template.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `v_X` | Conductor voltage at the fault point | V or p.u. |
| Output | `i_X` | Fault current injected into the conductor | A or p.u. |
| Parameter | `R_f` | Fault-path resistance | ohm or p.u. |
