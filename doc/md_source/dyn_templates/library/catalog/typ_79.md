# PI droop (constant)

This is Basic Block Catalog type `79` (`picdro_const`). It processes measurement or control signals for use inside a dynamic control model.

## Behaviour

- Library location: `Native / Control and Measurement / Controllers`.
- Inputs: 1.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 2.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - proc_{picdro\_const\_0})
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `condition` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `Tpick` | Configurable model parameter | model-dependent |
| Parameter | `Tdrop` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
