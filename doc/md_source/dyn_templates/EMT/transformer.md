# Transformer

This model represents a three-phase transformer for EMT studies.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `vf_A` | From-side phase-A terminal voltage applied to the transformer | pu |
| Input | `vf_B` | From-side phase-B terminal voltage applied to the transformer | pu |
| Input | `vf_C` | From-side phase-C terminal voltage applied to the transformer | pu |
| Input | `vt_A` | To-side phase-A terminal voltage applied to the transformer | pu |
| Input | `vt_B` | To-side phase-B terminal voltage applied to the transformer | pu |
| Input | `vt_C` | To-side phase-C terminal voltage applied to the transformer | pu |
| Input | `vf_n` | From-side neutral voltage when the selected winding connection exposes a neutral port | pu |
| Input | `vt_n` | To-side neutral voltage when the selected winding connection exposes a neutral port | pu |
| Output | `if_A` | Current injected by the transformer at the from-side phase-A port | pu |
| Output | `if_B` | Current injected by the transformer at the from-side phase-B port | pu |
| Output | `if_C` | Current injected by the transformer at the from-side phase-C port | pu |
| Output | `it_A` | Current injected by the transformer at the to-side phase-A port | pu |
| Output | `it_B` | Current injected by the transformer at the to-side phase-B port | pu |
| Output | `it_C` | Current injected by the transformer at the to-side phase-C port | pu |
| Output | `if_n` | Current injected at the from-side neutral port when a grounded-star connection is present | pu |
| Output | `it_n` | Current injected at the to-side neutral port when a grounded-star connection is present | pu |
| Variable | `i_f_A` | Internal from-side winding current state associated with phase A | pu |
| Variable | `i_f_B` | Internal from-side winding current state associated with phase B | pu |
| Variable | `i_f_C` | Internal from-side winding current state associated with phase C | pu |
| Variable | `i_t_A` | Internal to-side winding current state associated with phase A | pu |
| Variable | `i_t_B` | Internal to-side winding current state associated with phase B | pu |
| Variable | `i_t_C` | Internal to-side winding current state associated with phase C | pu |
| Variable | `if_A` | Exported from-side phase-A port current derived from the winding states | pu |
| Variable | `if_B` | Exported from-side phase-B port current derived from the winding states | pu |
| Variable | `if_C` | Exported from-side phase-C port current derived from the winding states | pu |
| Variable | `it_A` | Exported to-side phase-A port current derived from the winding states | pu |
| Variable | `it_B` | Exported to-side phase-B port current derived from the winding states | pu |
| Variable | `it_C` | Exported to-side phase-C port current derived from the winding states | pu |
| Parameter | `trafo_r1` | Resistance of the from-side winding | pu |
| Parameter | `trafo_r2` | Resistance of the to-side winding | pu |
| Parameter | `trafo_l1` | Leakage inductance of the from-side winding | pu s |
| Parameter | `trafo_l2` | Leakage inductance of the to-side winding | pu s |
| Parameter | `trafo_m` | Mutual inductance coupling the two windings | pu s |
| Parameter | `trafo_gm` | Magnetizing conductance or core-loss branch parameter | pu |
| Parameter | `trafo_tap_ratio` | Off-nominal tap ratio applied between the two windings | pu |
