# Lookup matrix object (linear)

This is Basic Block Catalog type `19` (`Lookup matrix object (linear)`). It evaluates tabulated or array-based data using the selected lookup formulation.

## Behaviour

- Library location: `Native / Arrays and Matrices`.
- Inputs: 2.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 1.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yo - 0 + (arr_{z1\_1} \cdot (1 - \frac{arr_{x1} + (yi1 - arr_{x1}) \cdot \Theta\left(yi1 - arr_{x1}\right) - (yi1 - arr_{x2}) \cdot \Theta\left(yi1 - arr_{x2}\right) - arr_{x1}}{arr_{x2} - arr_{x1}}) \cdot (1 - \frac{arr_{y1} + (yi2 - arr_{y1}) \cdot \Theta\left(yi2 - arr_{y1}\right) - (yi2 - arr_{y2}) \cdot \Theta\left(yi2 - arr_{y2}\right) - arr_{y1}}{arr_{y2} - arr_{y1}}) + arr_{z1\_2} \cdot \frac{arr_{x1} + (yi1 - arr_{x1}) \cdot \Theta\left(yi1 - arr_{x1}\right) - (yi1 - arr_{x2}) \cdot \Theta\left(yi1 - arr_{x2}\right) - arr_{x1}}{arr_{x2} - arr_{x1}} \cdot (1 - \frac{arr_{y1} + (yi2 - arr_{y1}) \cdot \Theta\left(yi2 - arr_{y1}\right) - (yi2 - arr_{y2}) \cdot \Theta\left(yi2 - arr_{y2}\right) - arr_{y1}}{arr_{y2} - arr_{y1}}) + arr_{z2\_1} \cdot (1 - \frac{arr_{x1} + (yi1 - arr_{x1}) \cdot \Theta\left(yi1 - arr_{x1}\right) - (yi1 - arr_{x2}) \cdot \Theta\left(yi1 - arr_{x2}\right) - arr_{x1}}{arr_{x2} - arr_{x1}}) \cdot \frac{arr_{y1} + (yi2 - arr_{y1}) \cdot \Theta\left(yi2 - arr_{y1}\right) - (yi2 - arr_{y2}) \cdot \Theta\left(yi2 - arr_{y2}\right) - arr_{y1}}{arr_{y2} - arr_{y1}} + arr_{z2\_2} \cdot \frac{arr_{x1} + (yi1 - arr_{x1}) \cdot \Theta\left(yi1 - arr_{x1}\right) - (yi1 - arr_{x2}) \cdot \Theta\left(yi1 - arr_{x2}\right) - arr_{x1}}{arr_{x2} - arr_{x1}} \cdot \frac{arr_{y1} + (yi2 - arr_{y1}) \cdot \Theta\left(yi2 - arr_{y1}\right) - (yi2 - arr_{y2}) \cdot \Theta\left(yi2 - arr_{y2}\right) - arr_{y1}}{arr_{y2} - arr_{y1}}) \cdot \Theta\left(arr_{x1} + (yi1 - arr_{x1}) \cdot \Theta\left(yi1 - arr_{x1}\right) - (yi1 - arr_{x2}) \cdot \Theta\left(yi1 - arr_{x2}\right) - arr_{x1} + 1e-06\right) \cdot \Theta\left(arr_{y1} + (yi2 - arr_{y1}) \cdot \Theta\left(yi2 - arr_{y1}\right) - (yi2 - arr_{y2}) \cdot \Theta\left(yi2 - arr_{y2}\right) - arr_{y1} + 1e-06\right))
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi1` | Input signal consumed by the block | model-dependent |
| Input | `yi2` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `omatrix_K` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
