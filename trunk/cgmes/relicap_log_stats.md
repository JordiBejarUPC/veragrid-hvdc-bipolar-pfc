# ReliCapGrid CGMES Loading Log Statistics for VeraGrid 6.0.12

- Generated: `2026-05-13 11:23:05 UTC`
- Script: `/home/santi/Git/eRoots/VeraGrid/trunk/cgmes/run_relicap_tests.py`
- Relicap base folder: `/home/santi/Git/GitHub/relicapgrid/Instance`

## Summary

- Models: `15`
- Total log entries: `45525`
- Errors: `37242`
- Warnings: `5844`
- Information: `2439`
- Divergences: `0`

## Per-model logger statistics

| Model name | Total | Errors | Warnings | Information | Divergences | Top messages |
|---|---:|---:|---:|---:|---:|---|
| Belgovia | 246 | 147 | 77 | 22 | 0 | ConductingEquipment is missing for terminal. (90)<br>Not supported operational limit kind for OperationalLimitType (45)<br>Value error (17)<br>Reference not found (16)<br>TopologicalNode skipped because a ConnectivityNode exists (15) |
| Britheim | 67 | 42 | 14 | 11 | 0 | ConductingEquipment is missing for terminal. (16)<br>Cannot retrieve voltage from a DC terminal, this is a CGMES design error (12)<br>Not supported operational limit kind for OperationalLimitType (8)<br>Missing object property (7)<br>TopologicalNode skipped because a ConnectivityNode exists (6) |
| Combination 1 (Belgovia + Svedala) | 2043 | 1160 | 614 | 269 | 0 | ConductingEquipment is missing for terminal. (1054)<br>Not supported operational limit kind for OperationalLimitType (527)<br>TopologicalNode skipped because a ConnectivityNode exists (249)<br>Value error (46)<br>Reference not found (27) |
| Combination 2 (Belgovia + Svedala +Galia) | 2369 | 1436 | 657 | 276 | 0 | ConductingEquipment is missing for terminal. (1114)<br>Not supported operational limit kind for OperationalLimitType (557)<br>TopologicalNode skipped because a ConnectivityNode exists (256)<br>Missing object property (222)<br>Value error (47) |
| Combination 3 (Belgovia + Svedala +Galia + Espheim + Britheim ) | 5071 | 3083 | 1517 | 471 | 0 | ConductingEquipment is missing for terminal. (2722)<br>Not supported operational limit kind for OperationalLimitType (1361)<br>TopologicalNode skipped because a ConnectivityNode exists (436)<br>Missing object property (225)<br>Value error (47) |
| DC-Espheim-Svedala | 89 | 52 | 20 | 17 | 0 | ConductingEquipment is missing for terminal. (20)<br>Not supported operational limit kind for OperationalLimitType (10)<br>Missing reference (8)<br>Missing object property (7)<br>Nominal voltage is 0. :( (6) |
| DC-Nordheim-Galia | 108 | 75 | 18 | 15 | 0 | ConductingEquipment is missing for terminal. (20)<br>Cannot retrieve voltage from a DC terminal, this is a CGMES design error (18)<br>Not supported operational limit kind for OperationalLimitType (10)<br>No DCTerminal in DCNode Terminals [0:1] (8)<br>TopologicalNode skipped because a ConnectivityNode exists (8) |
| Espheim + DC-Espheim-Svedala | 2683 | 1631 | 857 | 195 | 0 | ConductingEquipment is missing for terminal. (1592)<br>Not supported operational limit kind for OperationalLimitType (796)<br>TopologicalNode skipped because a ConnectivityNode exists (179)<br>RegulatingCondEq has no control (22)<br>Reference not found (12) |
| Espheim | 2630 | 1606 | 845 | 179 | 0 | ConductingEquipment is missing for terminal. (1572)<br>Not supported operational limit kind for OperationalLimitType (786)<br>TopologicalNode skipped because a ConnectivityNode exists (174)<br>RegulatingCondEq has no control (21)<br>Reference not found (14) |
| Galia | 355 | 290 | 51 | 14 | 0 | Missing object property (213)<br>ConductingEquipment is missing for terminal. (60)<br>Not supported operational limit kind for OperationalLimitType (30)<br>TopologicalNode skipped because a ConnectivityNode exists (12)<br>Reference not found (9) |
| Jotunheim | 26068 | 25585 | 39 | 444 | 0 | The object is not a ConductingEquipment (7117)<br>OperationalLimitSet missing. (4149)<br>No terminal for the device (3210)<br>Not exactly two terminals (2839)<br>Missing reference (2646) |
| Nordheim | 16 | 11 | 3 | 2 | 0 | Missing object property (7)<br>File does not contain any FullModel or DifferenceModel; imported as extension profile (2)<br>Reference not found (2)<br>Class dictionary collision while merging NCP assets (1)<br>Missing reference (1) |
| Portheim | 41 | 26 | 14 | 1 | 0 | Reference not found (8)<br>Missing object property (7)<br>Not exactly two terminals (5)<br>CGMES Switch.retained is preserved as metadata but ignored for topology reduction; switch forced reducible. (5)<br>ConductingEquipment is missing for terminal. (4) |
| Svedala + DC-Espheim-Svedala | 1902 | 1066 | 567 | 269 | 0 | ConductingEquipment is missing for terminal. (984)<br>Not supported operational limit kind for OperationalLimitType (492)<br>TopologicalNode skipped because a ConnectivityNode exists (242)<br>Value error (29)<br>Reference not found (21) |
| Svedala | 1837 | 1032 | 551 | 254 | 0 | ConductingEquipment is missing for terminal. (964)<br>Not supported operational limit kind for OperationalLimitType (482)<br>TopologicalNode skipped because a ConnectivityNode exists (237)<br>Value error (29)<br>Reference not found (20) |