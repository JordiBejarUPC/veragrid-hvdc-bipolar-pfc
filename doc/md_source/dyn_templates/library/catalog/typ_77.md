# Moving average

This is Basic Block Catalog type `77` (`movingavg`). It represents a continuous-time dynamic operation, including any declared internal states.

## Behaviour

- Library location: `Native / Continuous / Delays and Memory`.
- Inputs: 1.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 2.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - proc_{movingavg\_0})
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `Tdel` | Configurable model parameter | model-dependent |
| Parameter | `Tlength` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
