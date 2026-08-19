# Lookup array (linear noclipping)

This is Basic Block Catalog type `8` (`Lookup array (linear_noclipping)`). It evaluates tabulated or array-based data using the selected lookup formulation.

## Behaviour

- Library location: `Native / Arrays and Matrices`.
- Inputs: 1.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 1.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - (\frac{arr_{y2} - arr_{y1}}{arr_{x2} - arr_{x1}} \cdot yi + arr_{y1} - \frac{arr_{y2} - arr_{y1}}{arr_{x2} - arr_{x1}} \cdot arr_{x1}) \cdot \Theta\left(arr_{x2} - yi - 1e-06\right) + (\frac{arr_{y3} - arr_{y2}}{arr_{x3} - arr_{x2}} \cdot yi + arr_{y2} - \frac{arr_{y3} - arr_{y2}}{arr_{x3} - arr_{x2}} \cdot arr_{x2}) \cdot \Theta\left(yi - arr_{x2} + 1e-06\right))
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `array_K` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
