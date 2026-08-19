# PI droop

This is Basic Block Catalog type `78` (`picdro`). It processes measurement or control signals for use inside a dynamic control model.

## Behaviour

- Library location: `Native / Control and Measurement / Controllers`.
- Inputs: 3.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 0.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - proc_{picdro\_0})
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `condition` | Input signal consumed by the block | model-dependent |
| Input | `Tpick` | Input signal consumed by the block | model-dependent |
| Input | `Tdrop` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
