# Inverse Lookup array object (linear)

This is Basic Block Catalog type `6` (`Inverse Lookup array object (linear)`). It evaluates tabulated or array-based data using the selected lookup formulation.

## Behaviour

- Library location: `Native / Arrays and Matrices`.
- Inputs: 1.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 1.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - arr_{x1} \cdot \Theta\left(arr_{y1} - yi - 1e-06\right) + (\frac{arr_{x2} - arr_{x1}}{arr_{y2} - arr_{y1}} \cdot yi + arr_{x1} - \frac{arr_{x2} - arr_{x1}}{arr_{y2} - arr_{y1}} \cdot arr_{y1}) \cdot \Theta\left(yi - arr_{y1} + 1e-06\right) \cdot \Theta\left(arr_{y2} - yi - 1e-06\right) + (\frac{arr_{x3} - arr_{x2}}{arr_{y3} - arr_{y2}} \cdot yi + arr_{x2} - \frac{arr_{x3} - arr_{x2}}{arr_{y3} - arr_{y2}} \cdot arr_{y2}) \cdot \Theta\left(yi - arr_{y2} + 1e-06\right) \cdot \Theta\left(arr_{y3} - yi - 1e-06\right) + arr_{x3} \cdot \Theta\left(yi - arr_{y3} + 1e-06\right))
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `oarray_K` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
