# Bergeron line (ABC)

This model represents a three-phase Bergeron transmission line for EMT studies.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `v_f_A` | From-side phase-A terminal voltage used by the Bergeron line equations when phase A is active | pu |
| Input | `v_f_B` | From-side phase-B terminal voltage used by the Bergeron line equations when phase B is active | pu |
| Input | `v_f_C` | From-side phase-C terminal voltage used by the Bergeron line equations when phase C is active | pu |
| Input | `v_t_A` | To-side phase-A terminal voltage used by the Bergeron line equations when phase A is active | pu |
| Input | `v_t_B` | To-side phase-B terminal voltage used by the Bergeron line equations when phase B is active | pu |
| Input | `v_t_C` | To-side phase-C terminal voltage used by the Bergeron line equations when phase C is active | pu |
| Output | `if_A` | Current injected by the line at the from-side phase-A port | pu |
| Output | `if_B` | Current injected by the line at the from-side phase-B port | pu |
| Output | `if_C` | Current injected by the line at the from-side phase-C port | pu |
| Output | `it_A` | Current injected by the line at the to-side phase-A port | pu |
| Output | `it_B` | Current injected by the line at the to-side phase-B port | pu |
| Output | `it_C` | Current injected by the line at the to-side phase-C port | pu |
| Variable | `Ih_f_A` | Bergeron history current seen from the from-side phase-A port after one travel delay | pu |
| Variable | `Ih_f_B` | Bergeron history current seen from the from-side phase-B port after one travel delay | pu |
| Variable | `Ih_f_C` | Bergeron history current seen from the from-side phase-C port after one travel delay | pu |
| Variable | `Ih_t_A` | Bergeron history current seen from the to-side phase-A port after one travel delay | pu |
| Variable | `Ih_t_B` | Bergeron history current seen from the to-side phase-B port after one travel delay | pu |
| Variable | `Ih_t_C` | Bergeron history current seen from the to-side phase-C port after one travel delay | pu |
| Variable | `history_buffer_f` | Runtime delay buffer that stores from-side wave-history samples between EMT steps | sample history |
| Variable | `history_buffer_t` | Runtime delay buffer that stores to-side wave-history samples between EMT steps | sample history |
| Parameter | `R_reduced` | Reduced series-resistance matrix used in the Bergeron line companion form | pu |
| Parameter | `L_reduced` | Reduced series-inductance matrix used in the Bergeron line companion form | pu |
| Parameter | `Zc_reduced` | Reduced characteristic-impedance matrix used to relate terminal voltages and traveling-wave currents | pu |
| Parameter | `tau_delay` | Wave travel time used by the history update logic | s |
