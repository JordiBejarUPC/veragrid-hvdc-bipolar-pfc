# Complete HVDC VSC PowerFactory exports

These fixtures are declarative DGS exports of the PowerFactory project
used to validate HVDC converters, study case `Base`, produced with PowerFactory
2025 SP4 (API 25.0.6). The common `Grid` network was active for every export
and exactly one converter implementation was active:

| Fixture | Active converter network | SHA-256 |
| --- | --- | --- |
| `hvdc_vsc_v1_complete_static_dynamic.dgs` | `HVDC ver 1` | `0065D822C38D57F51126D743CEB5BB5665CF0C0A88C65050B1BFC4F93D90E0F0` |
| `hvdc_vsc_v2_complete_static_dynamic.dgs` | `HVDC ver 2` | `D8D8341DD60632A6A01EE6516324336CC6CB50942BA58C1BC3A520252970D334` |
| `hvdc_vsc_v3_complete_static_dynamic.dgs` | `HVDC ver 3` | `E34DA6F5DCD229B90379A17940D072E02BAF9382BD8405E96FF7175330294C57` |

Version 3 stores its converter composites below the `HVDC System` hierarchy.
The mature exporter did not traverse that nested hierarchy for native PLL
objects. The two missing declarative `ElmPhi` rows were therefore recovered
from the same live PowerFactory project through its API and appended to the
DGS fixture. Their structural bindings are:

- `PLL A`: composite FID `205`, measured terminal FID `265`, `Kp=100`, `Ki=30`.
- `PLL B`: composite FID `206`, measured terminal FID `266`, `Kp=100`, `Ki=30`.

## Solved-output boundary

PowerFactory columns prefixed with `m:` are optional solved operating-point
evidence. They are retained so regression tests can compare PowerFactory and
VeraGrid results, but they are not equipment configuration and must never
replace setpoints or topology during import. Converter construction uses
`psetp`, `qsetp`, `usetp`, `usetpdc`, equipment parameters and cubicle roles.
Missing or stale `m:` data makes the corresponding comparison unavailable; it
does not change the imported model.

## Frozen comparison references

The external comparison archive keeps the previously accepted PowerFactory and
VeraGrid time-series results.
The recorded simulation envelopes are:

| Version | Horizon | Output step | PowerFactory samples/signals | VeraGrid samples/signals | Events |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 3.9 s | 0.001 s | 4043 / 55 | 4001 / 59 | 50 |
| V2 | 4.0 s | 0.001 s | 4110 / 77 | 32801 / 77 | 8 |
| V3 | 2.0 s | 0.00025 s | 8415 / 84 | 8001 / 96 | 8 |

Those results are validation oracles, not input data for rebuilding the model.
