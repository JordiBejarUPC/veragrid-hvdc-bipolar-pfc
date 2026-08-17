# Ke^-sT (forward increment)

This is Basic Block Catalog type `98` (`Ke^-sT _incforward`). It represents a continuous-time dynamic operation, including any declared internal states.

## Behaviour

- Library location: `Native / Continuous / Delays and Memory`.
- Inputs: 1.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 2.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - K \cdot proc_{delay\_0})
$$

$$
yo(t_0) = (K \cdot yi)
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `K` | Configurable model parameter | model-dependent |
| Parameter | `T` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
