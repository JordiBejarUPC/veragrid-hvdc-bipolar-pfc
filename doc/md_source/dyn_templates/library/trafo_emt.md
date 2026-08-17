# Transformer EMT

EMT transformer template represented directly in the phase domain. The block
couples the from-side and to-side terminal voltages and currents while applying
the transformer ratio, winding connection, and leakage behavior.

## Configuration

General options select the winding connection independently on each side. The
default is grounded star on both sides. Delta and ungrounded-star choices change
the phase-to-winding incidence relations and therefore reconstruct the port and
equation structure when changes are applied.

The transformer uses the associated static device data for electrical
parameters; the modal does not duplicate those static nameplate values.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Terminal | `hv` | High-voltage winding terminals | model-dependent |
| Terminal | `lv` | Low-voltage winding terminals | model-dependent |
| Parameter | `ratio` | Turns ratio | pu |
| Parameter | `Xleak` | Leakage reactance | pu |

## How to use it

- Choose winding connections that agree with the static transformer.
- Connect every exposed phase on both terminals before simulation.
- Reopen the editor after changing static topology so the dynamic interface can
  be reconciled before EMT initialization.
