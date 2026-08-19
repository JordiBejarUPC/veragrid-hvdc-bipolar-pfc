# Deadband offset (parameter)

This is Basic Block Catalog type `92` (`Deadband offset [p`). It applies the declared limiting or nonlinear relation to its input signals.

## Behaviour

- Library location: `Native / Limits and Nonlinearities / Deadbands and Rate Limiters`.
- Inputs: 1.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 3.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - y_{min} + (proc_{selfix\_2} \cdot (proc_{select\_1} \cdot (proc_{select\_0} \cdot (yi - db) + (1 - proc_{select\_0}) \cdot (yi + db)) + (1 - proc_{select\_1}) \cdot 0) + (1 - proc_{selfix\_2}) \cdot yi - y_{min}) \cdot \Theta\left(proc_{selfix\_2} \cdot (proc_{select\_1} \cdot (proc_{select\_0} \cdot (yi - db) + (1 - proc_{select\_0}) \cdot (yi + db)) + (1 - proc_{select\_1}) \cdot 0) + (1 - proc_{selfix\_2}) \cdot yi - y_{min}\right) - (proc_{selfix\_2} \cdot (proc_{select\_1} \cdot (proc_{select\_0} \cdot (yi - db) + (1 - proc_{select\_0}) \cdot (yi + db)) + (1 - proc_{select\_1}) \cdot 0) + (1 - proc_{selfix\_2}) \cdot yi - y_{max}) \cdot \Theta\left(proc_{selfix\_2} \cdot (proc_{select\_1} \cdot (proc_{select\_0} \cdot (yi - db) + (1 - proc_{select\_0}) \cdot (yi + db)) + (1 - proc_{select\_1}) \cdot 0) + (1 - proc_{selfix\_2}) \cdot yi - y_{max}\right))
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `db` | Configurable model parameter | model-dependent |
| Parameter | `y_max` | Configurable model parameter | model-dependent |
| Parameter | `y_min` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
