# ax^2 + bx + c

This is Basic Block Catalog type `3` (`ax^2 + bx + c`). It evaluates the mathematical function identified by the block name.

## Behaviour

- Library location: `Native / Math and Functions / Scaling and Products`.
- Inputs: 1.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 3.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - a \cdot yi \cdot yi + b \cdot yi + c)
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `a` | Configurable model parameter | model-dependent |
| Parameter | `b` | Configurable model parameter | model-dependent |
| Parameter | `c` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
