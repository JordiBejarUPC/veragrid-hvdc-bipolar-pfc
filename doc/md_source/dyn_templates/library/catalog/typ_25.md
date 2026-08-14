# yi less than or equal C

This is Basic Block Catalog type `25` (`yi less than or equal C`). It implements logical or event-driven signal behaviour.

## Behaviour

- Library location: `Native / Logic and Events / Comparators`.
- Inputs: 1.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 1.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - proc_{select\_const\_0} \cdot 1 + (1 - proc_{select\_const\_0}) \cdot 0)
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `C` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
