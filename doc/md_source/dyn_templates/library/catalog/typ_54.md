# Bias

This is Basic Block Catalog type `54` (`Bias`). It evaluates the mathematical function identified by the block name.

## Behaviour

- Library location: `Native / Math and Functions / Scaling and Products`.
- Inputs: 0.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 0.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - Bias_{bias})
$$

$$
Bias_{bias}(t_0) = yo
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Output | `yo` | Output signal produced by the block | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
