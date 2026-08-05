# Stabilizer

This model represents the stabilizer block used with the EMT complete generator model.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `omega` | Generator speed signal fed into the power-system stabilizer | pu |
| Output | `V_pss` | Stabilizing voltage signal sent to the exciter auxiliary input | pu |
| Variable | `y_stabilizer1` | Transducer output state that filters the raw speed deviation signal | pu |
| Variable | `y_stabilizer2` | Washout state that removes the steady-state component from the stabilizer input | pu |
| Variable | `y_stabilizer3` | Gain-stage output after applying the stabilizer gain to the washout channel | pu |
| Variable | `y_stabilizer4` | First lead-lag state used to shape phase compensation | pu |
| Variable | `y_stabilizer5` | Second lead-lag state used to shape phase compensation before output limiting | pu |
| Parameter | `Ks` | Main stabilizer gain applied to the filtered speed-deviation signal | pu/pu |
| Parameter | `VPssMaxPu` | Upper limiter applied to the stabilizer output | pu |
| Parameter | `VPssMinPu` | Lower limiter applied to the stabilizer output | pu |
| Parameter | `SNom` | Nominal power base used by the stabilizer block when mapped from machine data | MVA |
| Parameter | `t1` | Lead time constant of the first lead-lag block | s |
| Parameter | `t2` | Lag time constant of the first lead-lag block | s |
| Parameter | `t3` | Lead time constant of the second lead-lag block | s |
| Parameter | `t4` | Lag time constant of the second lead-lag block | s |
| Parameter | `t5` | Washout time constant | s |
| Parameter | `t6` | Input transducer time constant | s |
