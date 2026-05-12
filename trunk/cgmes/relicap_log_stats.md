# ReliCapGrid CGMES Loading Log Statistics for VeraGrid 6.0.10

- Generated: `2026-05-12 17:47:41 UTC`
- Script: `/home/santi/Git/eRoots/VeraGrid/trunk/cgmes/run_relicap_tests.py`
- Relicap base folder: `/home/santi/Git/GitHub/relicapgrid/Instance`

## Summary

- Models: `15`
- Total log entries: `45463`
- Errors: `37217`
- Warnings: `5821`
- Information: `2425`
- Divergences: `0`

## Per-model logger statistics

| Model name | Total | Errors | Warnings | Information | Divergences | Top messages |
|---|---:|---:|---:|---:|---:|---|
| Belgovia | 245 | 147 | 76 | 22 | 0 | ConductingEquipment is missing for terminal. (90)<br>Not supported operational limit kind for OperationalLimitType (45)<br>Value error (17)<br>Reference not found (16)<br>TopologicalNode skipped because a ConnectivityNode exists (15) |
| Britheim | 66 | 42 | 13 | 11 | 0 | ConductingEquipment is missing for terminal. (16)<br>Cannot retrieve voltage from a DC terminal, this is a CGMES design error (12)<br>Not supported operational limit kind for OperationalLimitType (8)<br>Missing object property (7)<br>TopologicalNode skipped because a ConnectivityNode exists (6) |
| Espheim | 2629 | 1606 | 844 | 179 | 0 | ConductingEquipment is missing for terminal. (1572)<br>Not supported operational limit kind for OperationalLimitType (786)<br>TopologicalNode skipped because a ConnectivityNode exists (174)<br>RegulatingCondEq has no control (21)<br>Reference not found (14) |
| DC-Espheim-Svedala | 89 | 52 | 19 | 18 | 0 | ConductingEquipment is missing for terminal. (20)<br>Not supported operational limit kind for OperationalLimitType (10)<br>Missing reference (8)<br>Missing object property (7)<br>Nominal voltage is 0. :( (6) |
| Espheim + DC-Espheim-Svedala | 2686 | 1631 | 860 | 195 | 0 | ConductingEquipment is missing for terminal. (1592)<br>Not supported operational limit kind for OperationalLimitType (796)<br>TopologicalNode skipped because a ConnectivityNode exists (179)<br>RegulatingCondEq has no control (22)<br>Reference not found (12) |
| Galia | 354 | 290 | 50 | 14 | 0 | Missing object property (213)<br>ConductingEquipment is missing for terminal. (60)<br>Not supported operational limit kind for OperationalLimitType (30)<br>TopologicalNode skipped because a ConnectivityNode exists (12)<br>Reference not found (9) |
| DC-Nordheim-Galia | 107 | 75 | 17 | 15 | 0 | ConductingEquipment is missing for terminal. (20)<br>Cannot retrieve voltage from a DC terminal, this is a CGMES design error (18)<br>Not supported operational limit kind for OperationalLimitType (10)<br>No DCTerminal in DCNode Terminals [0:1] (8)<br>TopologicalNode skipped because a ConnectivityNode exists (8) |
| Jotunheim | 26067 | 25585 | 38 | 444 | 0 | The object is not a ConductingEquipment (7117)<br>OperationalLimitSet missing. (4149)<br>No terminal for the device (3210)<br>Not exactly two terminals (2839)<br>Missing reference (2646) |
| Nordheim | 15 | 11 | 2 | 2 | 0 | Missing object property (7)<br>File does not contain any FullModel or DifferenceModel; imported as extension profile (2)<br>Reference not found (2)<br>Missing reference (1)<br>Nominal voltage is 0. :( (1) |
| Portheim | 40 | 26 | 13 | 1 | 0 | Reference not found (8)<br>Missing object property (7)<br>Not exactly two terminals (5)<br>CGMES Switch.retained is preserved as metadata but ignored for topology reduction; switch forced reducible. (5)<br>ConductingEquipment is missing for terminal. (4) |
| Svedala | 1836 | 1032 | 550 | 254 | 0 | ConductingEquipment is missing for terminal. (964)<br>Not supported operational limit kind for OperationalLimitType (482)<br>TopologicalNode skipped because a ConnectivityNode exists (237)<br>Value error (29)<br>Reference not found (20) |
| Svedala + DC-Espheim-Svedala | 1902 | 1066 | 566 | 270 | 0 | ConductingEquipment is missing for terminal. (984)<br>Not supported operational limit kind for OperationalLimitType (492)<br>TopologicalNode skipped because a ConnectivityNode exists (242)<br>Value error (29)<br>Reference not found (21) |
| Combination 1 (Belgovia + Svedala) | 2042 | 1160 | 613 | 269 | 0 | ConductingEquipment is missing for terminal. (1054)<br>Not supported operational limit kind for OperationalLimitType (527)<br>TopologicalNode skipped because a ConnectivityNode exists (249)<br>Value error (46)<br>Reference not found (27) |
| Combination 2 (Belgovia + Svedala +Galia) | 2368 | 1436 | 656 | 276 | 0 | ConductingEquipment is missing for terminal. (1114)<br>Not supported operational limit kind for OperationalLimitType (557)<br>TopologicalNode skipped because a ConnectivityNode exists (256)<br>Missing object property (222)<br>Value error (47) |
| Combination 3 (Belgovia + Svedala +Galia + Espheim + Britheim ) | 5017 | 3058 | 1504 | 455 | 0 | ConductingEquipment is missing for terminal. (2702)<br>Not supported operational limit kind for OperationalLimitType (1351)<br>TopologicalNode skipped because a ConnectivityNode exists (431)<br>Missing object property (225)<br>Value error (47) |