# DC voltage source EMT

Fixed DC EMT voltage source represented as a Norton equivalent. The block reads
the connected bus voltage and injects the current required by its internal
source voltage and conductance.

## Characteristic equation

$$
i_{dc} = g_{src}(V_{src} - v_{dc})
$$

A larger `g_src` makes the terminal voltage stiffer but can also worsen the
numerical conditioning of the EMT system.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `v_dc` | Connected DC-bus voltage | V |
| Output | `i_dc` | Current injected into the DC bus | A |
| Parameter | `V_src` | Internal fixed source voltage | V |
| Parameter | `g_src` | Norton source conductance | S |

## How to use it

- Connect `v_dc` and `i_dc` to the same DC network terminal.
- Use a controlled DC voltage source when the voltage command must come from
  another dynamic block.
- Check the current sign when combining this source with storage or converter models.
