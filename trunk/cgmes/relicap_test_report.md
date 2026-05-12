# Relicap Test Book Report for VeraGrid 6.0.10

- Generated: `2026-05-12 14:45:56 UTC`
- Script: `/home/santi/Git/eRoots/VeraGrid/trunk/cgmes/run_relicap_tests.py`
- Relicap base folder: `/home/santi/Git/GitHub/relicapgrid/Instance`

## Summary

- Total chapters: `42`
- PASS: `26`
- SKIP: `14`
- FAIL: `2`

## Dataset Coverage (loaded cases)

- `Belgovia`: existing files `18`, missing files `0`
- `Espheim`: existing files `17`, missing files `0`
- `Svedala`: existing files `22`, missing files `1`


## Contingencies use cases

*file*: `Contingencies_use_cases/Contingencies_use_cases.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | PF_UC1 | Power Flow Base Validation | PASS | OK: found 4 contingency objects across CO classes |
| 2 | BDS_UC1 | Boundary Dataset Structure | SKIP | SKIP: no specific checks provided by the test specification |
| 3 | CD_UC1 | Common Data Validation | SKIP | SKIP: no specific checks provided by the test specification |
| 4 | RD_UC1 | Regional Dataset Validation | SKIP | SKIP: no specific checks provided by the test specification |
| 5 | CO_UC1 | Contingencies use cases | PASS | OK: found 4 contingency objects across CO classes |
| 6 | CO_UC1 | Contingency row: Loss of TieLine between Belgovia and Galia | PASS | OK: resolved+executed+exported checks passed for row |
| 7 | CO_UC1 | Contingency row: Loss of TieLine between Belgovia and Svedala | PASS | OK: resolved+executed+exported checks passed for row |
| 8 | CO_UC1 | Contingency row: Loss of TieLine between Espheim and Svedala | PASS | OK: resolved+executed+exported checks passed for row |
| 9 | CO_UC1 | Contingency row: Loss of power transformer in Svedala | PASS | OK: resolved+executed+exported checks passed for row |
| 10 | CO_UC1 | Contingency row: Loss of LinearShuntCompensator | PASS | OK: resolved+executed+exported checks passed for row |
| 11 | CO_UC1 | Contingency row: Loss of NonlinearShuntCompensator | PASS | OK: resolved+executed+exported checks passed for row |
| 12 | CO_UC1 | Contingency row: Loss of HVDC converter DC-3P-Convert-1 | FAIL | FAIL: resolution check failed; missing EQ IDs: 038ce404-30dc-4289-b9db-7076cb870b8e ; missing CO IDs: 038ce404-30dc-4289-b9db-7076cb870b8e |
| 13 | CO_UC1 | Contingency row: Loss of HVDC line | FAIL | FAIL: resolution check failed; missing EQ IDs: be09fc02-de3f-49e4-aa84-94803bcc5d76 ; missing CO IDs:  |
| 14 | CO_UC1 | Contingency row: Loss of synchronous machine | PASS | OK: resolved+executed+exported checks passed for row |
| 15 | CO_UC1 | Contingency row: Loss of demand facility | PASS | OK: resolved+executed+exported checks passed for row |
| 16 | CO_UC1 | Contingency row: N-2 loss of two tie-lines | PASS | OK: resolved+executed+exported checks passed for row |

## Remedial Action Use Cases

*file*: `Remedial_Action_use_cases/Remedial_Action_use_cases.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | ER_UC1 | Equipment Reliability Variant 1 | SKIP | SKIP: no specific checks provided by the test specification |
| 2 | ER_UC2 | Equipment Reliability Variant 2 | SKIP | SKIP: no specific checks provided by the test specification |
| 3 | RA_UC1 | Topology RA with one action | PASS | OK: topology remedial action with one topology action exists |
| 4 | RA_UC2 | Dependent topology RAs | PASS | OK: dependent topology remedial actions exist |
| 5 | RA_UC3 | Pre-RAO topology RA modification | PASS | OK: pre-RAO modification objects exist |
| 6 | RA_UC4 | Post-RAO topology RA proposal | PASS | OK: post-RAO proposal objects exist |
| 7 | RA_UC5 | Post-RAO topology RA activation | PASS | OK: post-RAO activation objects exist |
| 8 | RA_UC6 | Countertrade RA | PASS | OK: countertrade remedial action objects exist |
| 9 | RA_UC7 | Redispatch RA | PASS | OK: redispatch remedial action objects exist |
| 10 | RAS_UC8 | Remedial Action Schedule handling | PASS | OK: post-RAO proposal objects exist |
| 11 | RA_UC9 Shared RA on Boundary | Shared RA on Boundary | SKIP | SKIP: no specific checks provided by the test specification |
| 12 | OR_UC1 | Operational Rules Validation | SKIP | SKIP: no specific checks provided by the test specification |

## Availability _Schedule_use_case

*file*: `Availability _Schedule_use_case/Availability _Schedule_use_case.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | AS_UC1 | Availability Schedule | PASS | OK: availability schedule and remedial action objects are present |

## Assessed Elements – Use Cases

*file*: `Assessed_Element_use_cases/Assessed_Element_use_cases.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | AE_UC1 | Secured Assessed Element | PASS | OK: assessed element IDs and key flags are valid |
| 2 | AE_UC2 | Scanned Assessed Element | PASS | OK: assessed element IDs and key flags are valid |
| 3 | AE_UC3 | Disable Assessed Element | PASS | OK: assessed element IDs and key flags are valid |
| 4 | AE_UC4 | Exclude Assessed Element | PASS | OK: assessed element IDs and key flags are valid |
| 5 | AE_UC5 | Assessed Element with Contingency | PASS | OK: assessed element IDs and key flags are valid |
| 6 | AE_UC6 | Assessed Element with Remedial Action | PASS | OK: assessed element IDs and key flags are valid |

## Implementing SIPS Gate Logic with Cardinality Constraints (Run-back Function on HVDC Link)

*file*: `Implementing_SIPS_Gate_Logic_with_Cardinality_Constraints/Implementing_SIPS_Gate_Logic_with_Cardinality_Constraints.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Special Automation / SIPS Rules | SKIP | SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance |

## Correction of generation production due to a power flow limit violation

*file*: `Correction_of_generation_production_due_to_a_power_flow_limit_violation/Correction_of_generation_production_due_to_a_power_flow_limit_violation.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | PF_UC1 | Correction of generation production due to a power flow limit violation | SKIP | SKIP: markdown says anonymized IGM still needs integration |

## Modelling complex SIPS logic (Automatic Generation Shedding)

*file*: `Modelling_complex_SIPS_logic/Modelling_complex_SIPS_logic.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Modelling complex SIPS logic | SKIP | SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance |

## Modelling Current Flow Conditions Against PATL or TATL

*file*: `Modelling_Current_Flow_Conditions_Against_PATL_or_TATL/Modelling_Current_Flow_Conditions_Against_PATL_or_TATL.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Modelling Current Flow Conditions Against PATL or TATL | SKIP | SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance |

## Modelling Element Disconnection by Monitoring the Power Flow (Last Line Disconnection)

*file*: `Modelling_Element_Disconnection_by_Monitoring_the_Power_Flow/Modelling_Element_Disconnection_by_Monitoring_the_Power_Flow.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Modelling Element Disconnection by Monitoring the Power Flow | SKIP | SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance |

## Modelling SIPS Actions Based on Generation (Anti-swing Protection)

*file*: `Modelling_SIPS_Actions_Based_on_Generation/Modelling_SIPS_Actions_Based_on_Generation.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Modelling SIPS Actions Based on Generation | SKIP | SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance |

## Modelling Voltage Dependent Tripping Conditions (Overvoltage Protection)

*file*: `Modelling_Voltage_Dependent_Tripping_Conditions/Modelling_Voltage_Dependent_Tripping_Conditions.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Modelling Voltage Dependent Tripping Conditions | SKIP | SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance |

## Failure Details

1. Contingency row: Loss of HVDC converter DC-3P-Convert-1: FAIL: resolution check failed; missing EQ IDs: 038ce404-30dc-4289-b9db-7076cb870b8e ; missing CO IDs: 038ce404-30dc-4289-b9db-7076cb870b8e
2. Contingency row: Loss of HVDC line: FAIL: resolution check failed; missing EQ IDs: be09fc02-de3f-49e4-aa84-94803bcc5d76 ; missing CO IDs: 

## Notes

- `SKIP` means the chapter was recognized but cannot be fully executed with currently available local datasets.
- Chapters mapped to SIPS use cases currently return `SKIP` until the referenced SIPS datasets are available in the local instance.