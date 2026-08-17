# Flip-flop

This is Basic Block Catalog type `68` (`flipflop`). It implements logical or event-driven signal behaviour.

## Behaviour

- Library location: `Native / Logic and Events / Gates and Memory`.
- Inputs: 2.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 0.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - proc_{flipflop\_0})
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `set` | Input signal consumed by the block | model-dependent |
| Input | `rst` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
