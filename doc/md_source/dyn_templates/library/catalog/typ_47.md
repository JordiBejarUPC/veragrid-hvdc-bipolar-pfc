# yi1 greater than yi2 eps

This is Basic Block Catalog type `47` (`yi1 greater than yi2 _eps`). It implements logical or event-driven signal behaviour.

## Behaviour

- Library location: `Native / Logic and Events / Comparators`.
- Inputs: 2.
- Outputs: 1.
- Declared states: 0.
- Configurable parameters: 1.
- The imported definition is fully supported by the Dynamic Editor catalogue.

## Characteristic equations

$$
0 = (yi1 greater than yi2 _{eps\_set} - proc_{selfix\_1} \cdot 0 + (1 - proc_{selfix\_1}) \cdot (proc_{select\_const\_0} \cdot 1 + (1 - proc_{select\_const\_0}) \cdot 0))
$$

$$
0 = (yi1 greater than yi2 _{eps\_rst} - proc_{selfix\_3} \cdot 0 + (1 - proc_{selfix\_3}) \cdot (proc_{select\_const\_2} \cdot 1 + (1 - proc_{select\_const\_2}) \cdot 0))
$$

$$
0 = (yo - proc_{selfix\_6} \cdot (proc_{select\_const\_4} \cdot 1 + (1 - proc_{select\_const\_4}) \cdot 0) + (1 - proc_{selfix\_6}) \cdot proc_{flipflop\_5})
$$

$$
yi1 greater than yi2 _{eps\_set}(t_0) = (proc_{selfix\_const\_7} \cdot 1 + (1 - proc_{selfix\_const\_7}) \cdot 0)
$$

$$
yi1 greater than yi2 _{eps\_rst}(t_0) = (1 - yi1 greater than yi2 _{eps\_set})
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi1` | Input signal consumed by the block | model-dependent |
| Input | `yi2` | Input signal consumed by the block | model-dependent |
| Output | `yo` | Output signal produced by the block | model-dependent |
| Parameter | `eps` | Configurable model parameter | model-dependent |

## Editing notes

Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. Changing an Output flag only controls whether a variable is exported; it does not remove the variable from the model.
