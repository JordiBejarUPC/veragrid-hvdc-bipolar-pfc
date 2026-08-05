# DC line

This model represents a DC line with distributed electrical parameters for EMT studies.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `v_f_dc` | From-side DC terminal voltage applied to the line model | pu |
| Input | `v_t_dc` | To-side DC terminal voltage applied to the line model | pu |
| Input | `p_cmd` | Power-transfer command used by the power-input DC line variant selected by the catalogue | pu |
| Output | `i_f_dc` | Current injected by the line into the from-side DC node | pu |
| Output | `i_t_dc` | Current injected by the line into the to-side DC node | pu |
| Variable | `i_line` | Internal branch current carried by the DC line between the two terminals | pu |
| Variable | `p_line` | Instantaneous power transferred through the DC line model | pu |
| Parameter | `R_dc` | Series resistance of the DC line branch | pu |
| Parameter | `L_dc` | Series inductance of the DC line branch when dynamic current evolution is enabled | pu |
