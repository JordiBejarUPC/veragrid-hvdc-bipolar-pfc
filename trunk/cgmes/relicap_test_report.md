# Relicap Test Book Report for VeraGrid 6.0.12

- Generated: `2026-05-13 11:39:18 UTC`
- Script: `/home/santi/Git/eRoots/VeraGrid/trunk/cgmes/run_relicap_tests.py`
- Relicap base folder: `/home/santi/Git/GitHub/relicapgrid/Instance`

## Summary

- Total rows: `43`
- PASS: `25`
- SKIP: `18`
- FAIL: `0`
- Power-flow model rows: `15`

## Test models power flow

| Model name | Files included | Converged | Error achieved |
|---|---|---|---|
| Belgovia | Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_TP_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_SSH_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z__Belgovia_EQ_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_SV_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_AE.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_CO.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_ER.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_PS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RA.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RAS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RAS_FAP.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_SHS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_SIS.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 1.362573e-13 |
| Britheim | Britheim/Grid/cimxml/20220615T2230Z_2D_Britheim_TP_1.xml<br>Britheim/Grid/cimxml/20220615T2230Z_2D_Britheim_SSH_1.xml<br>Britheim/Grid/cimxml/20220615T2230Z__Britheim_EQ_1.xml<br>Britheim/Grid/cimxml/20220615T2230Z_2D_Britheim_SV_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 1.920914e-07 |
| Espheim | Espheim/Grid/cimxml/20220615T2230Z__Espheim_EQ_1.xml<br>Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_SSH_1.xml<br>Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_SV_1.xml<br>Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_TP_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>Espheim/NetworkCode/cimxml/Espheim_AE.xml<br>Espheim/NetworkCode/cimxml/Espheim_CO.xml<br>Espheim/NetworkCode/cimxml/Espheim_ER.xml<br>Espheim/NetworkCode/cimxml/Espheim_OR.xml<br>Espheim/NetworkCode/cimxml/Espheim_RA.xml<br>Espheim/NetworkCode/cimxml/Espheim_RAS.xml<br>Espheim/NetworkCode/cimxml/Espheim_SIS.xml<br>Espheim/NetworkCode/cimxml/Espheim_SSI.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 2.690448e-11 |
| DC-Espheim-Svedala | DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_TP_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SV_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SSH_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z__HVDC-Espheim-Svedala_EQ_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 2.886497e-08 |
| Espheim + DC-Espheim-Svedala | Espheim/Grid/cimxml/20220615T2230Z__Espheim_EQ_1.xml<br>Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_SSH_1.xml<br>Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_SV_1.xml<br>Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_TP_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_TP_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SV_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SSH_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z__HVDC-Espheim-Svedala_EQ_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>Espheim/NetworkCode/cimxml/Espheim_AE.xml<br>Espheim/NetworkCode/cimxml/Espheim_CO.xml<br>Espheim/NetworkCode/cimxml/Espheim_ER.xml<br>Espheim/NetworkCode/cimxml/Espheim_OR.xml<br>Espheim/NetworkCode/cimxml/Espheim_RA.xml<br>Espheim/NetworkCode/cimxml/Espheim_RAS.xml<br>Espheim/NetworkCode/cimxml/Espheim_SIS.xml<br>Espheim/NetworkCode/cimxml/Espheim_SSI.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 1.242964e-10 |
| Galia | Galia/Grid/cimxml/20220615T2230Z_2D_Galia_TP_1.xml<br>Galia/Grid/cimxml/20220615T2230Z_2D_Galia_SSH_1.xml<br>Galia/Grid/cimxml/20220615T2230Z__Galia_EQ_1.xml<br>Galia/Grid/cimxml/20220615T2230Z_2D_Galia_SV_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>Galia/NetworkCode/cimxml/Galia_AE.xml<br>Galia/NetworkCode/cimxml/Galia_CO.xml<br>Galia/NetworkCode/cimxml/Galia_ER.xml<br>Galia/NetworkCode/cimxml/Galia_RA.xml<br>Galia/NetworkCode/cimxml/Galia_RAS.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 4.062088e-08 |
| DC-Nordheim-Galia | DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z_2D_HVDC-Nordheim-Galia_SSH_1.xml<br>DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z_2D_HVDC-Nordheim-Galia_TP_1.xml<br>DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z__HVDC-Nordheim-Galia_EQ_1.xml<br>DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z_2D_HVDC-Nordheim-Galia_SV_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 2.872146e-09 |
| Jotunheim | Jotunheim/Grid/cimxml/20220615T2230Z_2D_Svedala_SSH_2.xml<br>Jotunheim/Grid/cimxml/20220615T2230Z_2D_Britheim_SSH_2.xml<br>Jotunheim/Grid/cimxml/20220615T2230Z_2D_Jotunheim_TP_1.xml<br>Jotunheim/Grid/cimxml/20220615T2230Z_2D_Belgovia_SSH_2.xml<br>Jotunheim/Grid/cimxml/20220615T2230Z_2D_HVDC_Espheim-Svedala_SSH_2.xml<br>Jotunheim/Grid/cimxml/20220615T2230Z_2D_HVDC_Nordheim-Galia_SSH_2.xml<br>Jotunheim/Grid/cimxml/20220615T2230Z_2D_Jotunheim_SV_1.xml<br>Jotunheim/Grid/cimxml/20220615T2230Z_2D_Espheim_SSH_2.xml<br>Jotunheim/Grid/cimxml/20241223T0642Z_2D_Portheim_SSH_2.xml<br>Jotunheim/Grid/cimxml/20220615T2230Z_2D_Nordheim_SSH_2.xml<br>Jotunheim/Grid/cimxml/20220615T2230Z_2D_Galia_SSH_2.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 0.000000e+00 |
| Nordheim | Nordheim/Grid/cimxml/20220615T2230Z_2D_Nordheim_SV_1.xml<br>Nordheim/Grid/cimxml/20220615T2230Z_2D_Nordheim_SSH_1.xml<br>Nordheim/Grid/cimxml/20220615T2230Z__Nordheim_EQ_1.xml<br>Nordheim/Grid/cimxml/20220615T2230Z_2D_Nordheim_TP_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 0.000000e+00 |
| Portheim | Portheim/Grid/cimxml/20241223T0642Z_2D_Portheim_EQ_1.xml<br>Portheim/Grid/cimxml/20241223T0642Z_2D_Portheim_SSH_1.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 7.422052e-10 |
| Svedala | Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SV_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_TP_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SSH_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z__Svedala_EQ_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>Svedala/NetworkCode/cimxml/Svedala-Belgovia_CO.xml<br>Svedala/NetworkCode/cimxml/Svedala_AE.xml<br>Svedala/NetworkCode/cimxml/Svedala_AS.xml<br>Svedala/NetworkCode/cimxml/Svedala_CO.xml<br>Svedala/NetworkCode/cimxml/Svedala_ER.xml<br>Svedala/NetworkCode/cimxml/Svedala_FAP_PV.xml<br>Svedala/NetworkCode/cimxml/Svedala_FAP_RAS_simple.xml<br>Svedala/NetworkCode/cimxml/Svedala_RA.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_Jotunheim_ordered.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_Jotunheim_proposed.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_acceptance_proposal.xml<br>Svedala/NetworkCode/cimxml/Svedala_SIS.xml<br>Svedala/NetworkCode/cimxml/Svedala_SSI.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 6.849078e-07 |
| Svedala + DC-Espheim-Svedala | Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SV_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_TP_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SSH_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z__Svedala_EQ_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_TP_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SV_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SSH_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z__HVDC-Espheim-Svedala_EQ_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>Svedala/NetworkCode/cimxml/Svedala-Belgovia_CO.xml<br>Svedala/NetworkCode/cimxml/Svedala_AE.xml<br>Svedala/NetworkCode/cimxml/Svedala_AS.xml<br>Svedala/NetworkCode/cimxml/Svedala_CO.xml<br>Svedala/NetworkCode/cimxml/Svedala_ER.xml<br>Svedala/NetworkCode/cimxml/Svedala_FAP_PV.xml<br>Svedala/NetworkCode/cimxml/Svedala_FAP_RAS_simple.xml<br>Svedala/NetworkCode/cimxml/Svedala_RA.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_Jotunheim_ordered.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_Jotunheim_proposed.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_acceptance_proposal.xml<br>Svedala/NetworkCode/cimxml/Svedala_SIS.xml<br>Svedala/NetworkCode/cimxml/Svedala_SSI.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 6.849078e-07 |
| Combination 1 (Belgovia + Svedala) | Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_TP_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_SSH_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z__Belgovia_EQ_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_SV_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SV_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_TP_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SSH_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z__Svedala_EQ_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_AE.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_CO.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_ER.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_PS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RA.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RAS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RAS_FAP.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_SHS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_SIS.xml<br>Svedala/NetworkCode/cimxml/Svedala-Belgovia_CO.xml<br>Svedala/NetworkCode/cimxml/Svedala_AE.xml<br>Svedala/NetworkCode/cimxml/Svedala_AS.xml<br>Svedala/NetworkCode/cimxml/Svedala_CO.xml<br>Svedala/NetworkCode/cimxml/Svedala_ER.xml<br>Svedala/NetworkCode/cimxml/Svedala_FAP_PV.xml<br>Svedala/NetworkCode/cimxml/Svedala_FAP_RAS_simple.xml<br>Svedala/NetworkCode/cimxml/Svedala_RA.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_Jotunheim_ordered.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_Jotunheim_proposed.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_acceptance_proposal.xml<br>Svedala/NetworkCode/cimxml/Svedala_SIS.xml<br>Svedala/NetworkCode/cimxml/Svedala_SSI.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 1.007194e-12 |
| Combination 2 (Belgovia + Svedala +Galia) | Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_TP_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_SSH_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z__Belgovia_EQ_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_SV_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SV_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_TP_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SSH_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z__Svedala_EQ_1.xml<br>Galia/Grid/cimxml/20220615T2230Z_2D_Galia_TP_1.xml<br>Galia/Grid/cimxml/20220615T2230Z_2D_Galia_SSH_1.xml<br>Galia/Grid/cimxml/20220615T2230Z__Galia_EQ_1.xml<br>Galia/Grid/cimxml/20220615T2230Z_2D_Galia_SV_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_AE.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_CO.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_ER.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_PS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RA.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RAS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RAS_FAP.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_SHS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_SIS.xml<br>Svedala/NetworkCode/cimxml/Svedala-Belgovia_CO.xml<br>Svedala/NetworkCode/cimxml/Svedala_AE.xml<br>Svedala/NetworkCode/cimxml/Svedala_AS.xml<br>Svedala/NetworkCode/cimxml/Svedala_CO.xml<br>Svedala/NetworkCode/cimxml/Svedala_ER.xml<br>Svedala/NetworkCode/cimxml/Svedala_FAP_PV.xml<br>Svedala/NetworkCode/cimxml/Svedala_FAP_RAS_simple.xml<br>Svedala/NetworkCode/cimxml/Svedala_RA.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_Jotunheim_ordered.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_Jotunheim_proposed.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_acceptance_proposal.xml<br>Svedala/NetworkCode/cimxml/Svedala_SIS.xml<br>Svedala/NetworkCode/cimxml/Svedala_SSI.xml<br>Galia/NetworkCode/cimxml/Galia_AE.xml<br>Galia/NetworkCode/cimxml/Galia_CO.xml<br>Galia/NetworkCode/cimxml/Galia_ER.xml<br>Galia/NetworkCode/cimxml/Galia_RA.xml<br>Galia/NetworkCode/cimxml/Galia_RAS.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 1.593519e-08 |
| Combination 3 (Belgovia + Svedala +Galia + Espheim + Britheim ) | Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_TP_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_SSH_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z__Belgovia_EQ_1.xml<br>Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_SV_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SV_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_TP_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SSH_1.xml<br>Svedala/Grid/cimxml/20220615T2230Z__Svedala_EQ_1.xml<br>Galia/Grid/cimxml/20220615T2230Z_2D_Galia_TP_1.xml<br>Galia/Grid/cimxml/20220615T2230Z_2D_Galia_SSH_1.xml<br>Galia/Grid/cimxml/20220615T2230Z__Galia_EQ_1.xml<br>Galia/Grid/cimxml/20220615T2230Z_2D_Galia_SV_1.xml<br>Espheim/Grid/cimxml/20220615T2230Z__Espheim_EQ_1.xml<br>Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_SSH_1.xml<br>Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_SV_1.xml<br>Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_TP_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z__HVDC-Espheim-Svedala_EQ_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SSH_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SV_1.xml<br>DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_TP_1.xml<br>Britheim/Grid/cimxml/20220615T2230Z_2D_Britheim_TP_1.xml<br>Britheim/Grid/cimxml/20220615T2230Z_2D_Britheim_SSH_1.xml<br>Britheim/Grid/cimxml/20220615T2230Z__Britheim_EQ_1.xml<br>Britheim/Grid/cimxml/20220615T2230Z_2D_Britheim_SV_1.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml<br>boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml<br>commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_AE.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_CO.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_ER.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_PS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RA.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RAS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_RAS_FAP.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_SHS.xml<br>Belgovia/NetworkCode/cimxml/Belgovia_SIS.xml<br>Svedala/NetworkCode/cimxml/Svedala-Belgovia_CO.xml<br>Svedala/NetworkCode/cimxml/Svedala_AE.xml<br>Svedala/NetworkCode/cimxml/Svedala_AS.xml<br>Svedala/NetworkCode/cimxml/Svedala_CO.xml<br>Svedala/NetworkCode/cimxml/Svedala_ER.xml<br>Svedala/NetworkCode/cimxml/Svedala_FAP_PV.xml<br>Svedala/NetworkCode/cimxml/Svedala_FAP_RAS_simple.xml<br>Svedala/NetworkCode/cimxml/Svedala_RA.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_Jotunheim_ordered.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_Jotunheim_proposed.xml<br>Svedala/NetworkCode/cimxml/Svedala_RAS_acceptance_proposal.xml<br>Svedala/NetworkCode/cimxml/Svedala_SIS.xml<br>Svedala/NetworkCode/cimxml/Svedala_SSI.xml<br>Galia/NetworkCode/cimxml/Galia_AE.xml<br>Galia/NetworkCode/cimxml/Galia_CO.xml<br>Galia/NetworkCode/cimxml/Galia_ER.xml<br>Galia/NetworkCode/cimxml/Galia_RA.xml<br>Galia/NetworkCode/cimxml/Galia_RAS.xml<br>Espheim/NetworkCode/cimxml/Espheim_AE.xml<br>Espheim/NetworkCode/cimxml/Espheim_CO.xml<br>Espheim/NetworkCode/cimxml/Espheim_ER.xml<br>Espheim/NetworkCode/cimxml/Espheim_OR.xml<br>Espheim/NetworkCode/cimxml/Espheim_RA.xml<br>Espheim/NetworkCode/cimxml/Espheim_RAS.xml<br>Espheim/NetworkCode/cimxml/Espheim_SIS.xml<br>Espheim/NetworkCode/cimxml/Espheim_SSI.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml<br>commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml | True | 1.920914e-07 |

## Assessed Element use cases

*file*: `Assessed_Element_use_cases/Assessed_Element_use_cases.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | AE_UC1 | Secured Assessed Element | PASS | OK: dataset imported; secured assessed element is in the base case and has SecuredForRegion |
| 2 | AE_UC2 | Scanned Assessed Element | PASS | OK: scanned assessed elements have the expected region references and exclusion reason |
| 3 | AE_UC3 | Disable Assessed Element | PASS | OK: schedule and timepoint disable the secured assessed element for the specified time |
| 4 | AE_UC4 | Exclude Assessed Element | PASS | OK: excluded assessed element is outside the base case and remains scanned |
| 5 | AE_UC5 | Assessed Element with Contingency | PASS | OK: full-scope, excluded, and included AE-contingency combinations match the specification |
| 6 | AE_UC6 | Assessed Element with Remedial Action | PASS | OK: assessed element and remedial action association is present and included |

## Availability Schedule use case

*file*: `Availability _Schedule_use_case/Availability _Schedule_use_case.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | AS_UC1 | Availability Schedule | PASS | OK: schedule and availability remedial action are imported; schedule references the action and carries a cancellation time |

## Contingency uses cases

*file*: `Contingencies_use_cases/Contingencies_use_cases.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | PF_UC1 | Power Flow (base integration) | SKIP | SKIP: no specific checks provided by the test specification |
| 2 | BDS_UC1 | Boundary Data Set | SKIP | SKIP: no specific checks provided by the test specification |
| 3 | CD_UC1 | Common Data | SKIP | SKIP: no specific checks provided by the test specification |
| 4 | RD_UC1 | Reference Data | SKIP | SKIP: no specific checks provided by the test specification |
| 5 | CO_UC1 | Importing, executing, updating and exporting contingencies | SKIP | SKIP: no specific checks provided by the test specification |
| 6 | CO_UC1 | CO_UC1#1 Loss of TieLine between Belgovia and Galia | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (7e31c67d-67ba-4592-8ac1-9e806d697c8e_CO_export.zip) |
| 7 | CO_UC1 | CO_UC1#2 Loss of TieLine between Belgovia and Svedala | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (e9eab3fe-c328-4f78-9bc1-77adb59f6ba7_CO_export.zip) |
| 8 | CO_UC1 | CO_UC1#3 Loss of TieLine between Espheim and Svedala | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (e9eab3fe-c328-4f78-9bc1-77adb59f6ba7_CO_export.zip) |
| 9 | CO_UC1 | CO_UC1#4 Loss of power transformer in Svedala | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (e05bbe20-9d4a-40da-9777-8424d216785d_CO_export.zip) |
| 10 | CO_UC1 | CO_UC1#5 Loss of LinearShuntCompensator | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (62eac668-82a1-4739-8cfc-de929b78ef7e_CO_export.zip) |
| 11 | CO_UC1 | CO_UC1#6 Loss of NonlinearShuntCompensator | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (ab92defa-ef8e-4d13-a242-5b1a9fe956f6_CO_export.zip) |
| 12 | CO_UC1 | CO_UC1#7 Loss of HVDC converter DC-3P-Convert-1 | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (038ce404-30dc-4289-b9db-7076cb870b8e_CO_export.zip) |
| 13 | CO_UC1 | CO_UC1#8 Loss of HVDC line | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (504b48fb-de1f-4f7e-928f-8585daaf7b72_CO_export.zip) |
| 14 | CO_UC1 | CO_UC1#9 Loss of synchronous machine | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (37997e71-cb7d-4a8c-baa6-2a1594956da9_CO_export.zip) |
| 15 | CO_UC1 | CO_UC1#10 Loss of demand facility | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (65582e87-5035-4465-8dd9-cb655224b29f_CO_export.zip) |
| 16 | CO_UC1 | CO_UC1#11 N-2 loss of two tie-lines | PASS | OK: resolved against model; execution check executed; and CO export zip contains row IDs (9d17b84c-33b5-4a68-b8b9-ed5b31038d40_CO_export.zip) |

## Correction of generation production due to a power flow limit violation

*file*: `Correction_of_generation_production_due_to_a_power_flow_limit_violation/Correction_of_generation_production_due_to_a_power_flow_limit_violation.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | PF_UC1 | Correction workflow | SKIP | SKIP: markdown says the anonymized IGM and SPS file still need to be integrated before this scenario can be automated |

## Implementing SIPS Gate Logic with Cardinality Constraints

*file*: `Implementing_SIPS_Gate_Logic_with_Cardinality_Constraints/Implementing_SIPS_Gate_Logic_with_Cardinality_Constraints.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | SIPS gate logic | SKIP | SKIP: validation steps require load-flow/contingency/SIPS activation execution that is not automated in this structural CGMES test runner |

## Modelling complex SIPS logic

*file*: `Modelling_complex_SIPS_logic/Modelling_complex_SIPS_logic.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Complex SIPS logic | SKIP | SKIP: validation steps require load-flow/contingency/SIPS activation execution that is not automated in this structural CGMES test runner |

## Modelling Current Flow Conditions Against PATL or TATL

*file*: `Modelling_Current_Flow_Conditions_Against_PATL_or_TATL/Modelling_Current_Flow_Conditions_Against_PATL_or_TATL.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Current-flow condition checks | SKIP | SKIP: validation steps require load-flow/contingency/SIPS activation execution that is not automated in this structural CGMES test runner |

## Modelling Element Disconnection by Monitoring the Power Flow

*file*: `Modelling_Element_Disconnection_by_Monitoring_the_Power_Flow/Modelling_Element_Disconnection_by_Monitoring_the_Power_Flow.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Element disconnection by monitored flow | SKIP | SKIP: validation steps require load-flow/contingency/SIPS activation execution that is not automated in this structural CGMES test runner |

## Modelling SIPS Actions Based on Generation

*file*: `Modelling_SIPS_Actions_Based_on_Generation/Modelling_SIPS_Actions_Based_on_Generation.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Generation-based SIPS actions | SKIP | SKIP: validation steps require load-flow/contingency/SIPS activation execution that is not automated in this structural CGMES test runner |

## Modelling Voltage Dependent Tripping Conditions

*file*: `Modelling_Voltage_Dependent_Tripping_Conditions/Modelling_Voltage_Dependent_Tripping_Conditions.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | SAR_UC1 | Voltage-dependent tripping checks | SKIP | SKIP: validation steps require load-flow/contingency/SIPS activation execution that is not automated in this structural CGMES test runner |

## Remedial Action use cases

*file*: `Remedial_Action_use_cases/Remedial_Action_use_cases.md`

| # | Use Case ID | Use Case | Status | Detail |
|---:|---|---|---|---|
| 1 | ER_UC1 | Equipment Reliability (single TSO) | SKIP | SKIP: no specific checks provided by the test specification |
| 2 | ER_UC2 | Equipment Reliability (common data) | SKIP | SKIP: no specific checks provided by the test specification |
| 3 | RA_UC1 | Topology RA with one topology action | PASS | OK: RA and target switch are imported; execution/topology-change step is not automated in this runner |
| 4 | RA_UC2 | Dependent topology RAs with multiple actions | PASS | OK: exclusive dependency objects are imported and reference remedial actions; mutually-exclusive execution is not automated |
| 5 | RA_UC3 | Modification prior to RAO | PASS | OK: SIS schedule references the topology action and contains enable/disable time points |
| 6 | RA_UC4 | Proposing modifications after RAO | PASS | OK: refusal response, none-dependency, and replacement schedule are imported |
| 7 | RA_UC5 | Activation after RAO | PASS | OK: activation schedules, event schedules, event time points, and exclusive group IDs are imported |
| 8 | RA_UC6 | Countertrade Remedial Action | PASS | OK: countertrade RA, generating unit, PowerSchedule, and PowerBidSchedule are imported; schedule values are present in parsed datasets |
| 9 | RA_UC7 | Redispatch Remedial Action | PASS | OK: redispatch RAs, bid schedule/timepoint, and power-shift-key objects are imported and linked |
| 10 | RAS_UC8 | RAS FAP acceptance | SKIP | SKIP: no specific checks provided by the test specification |
| 11 | RA_UC9 Shared RA on Boundary | Shared RA on Boundary | SKIP | SKIP: no specific checks provided by the test specification |
| 12 | OR_UC1 | Object Registry | SKIP | SKIP: no specific checks provided by the test specification |
| 13 | SAR_UC1 | Security Analysis Result | SKIP | SKIP: no specific checks provided by the test specification |

## Failures

- None