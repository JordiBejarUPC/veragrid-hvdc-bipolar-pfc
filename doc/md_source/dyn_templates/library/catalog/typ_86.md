# Set if condition (constant)

This is Basic Block Catalog type `86` (`selfix_const`). It implements logical or event-driven signal behaviour.

## Behaviour

- Library location: `Native / Logic and Events / Switching and Selection`.
- Inputs: 1.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 2.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - proc_{selfix\_const\_0} \cdot K_{true} + (1 - proc_{selfix\_const\_0}) \cdot K_{false})
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `condition` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `K_true` | Configurable model parameter | model-dependent |
| Parameter | `K_false` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
