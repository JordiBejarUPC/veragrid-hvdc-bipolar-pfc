import os
import pandas as pd
import VeraGridEngine as vg

FOLDER = "/home/santi/Git/GitHub/relicapgrid/Instance"

SUBFOLDERS = {
    "Belgovia": [  # Belgovia
        f"{FOLDER}/Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_TP_1.xml",
        f"{FOLDER}/Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_SSH_1.xml",
        f"{FOLDER}/Belgovia/Grid/cimxml/20220615T2230Z__Belgovia_EQ_1.xml",
        f"{FOLDER}/Belgovia/Grid/cimxml/20220615T2230Z_2D_Belgovia_SV_1.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml",
        f"{FOLDER}/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml",
    ],

    "Britheim": [  # Britheim
        f"{FOLDER}/Britheim/Grid/cimxml/20220615T2230Z_2D_Britheim_TP_1.xml",
        f"{FOLDER}/Britheim/Grid/cimxml/20220615T2230Z_2D_Britheim_SSH_1.xml",
        f"{FOLDER}/Britheim/Grid/cimxml/20220615T2230Z__Britheim_EQ_1.xml",
        f"{FOLDER}/Britheim/Grid/cimxml/20220615T2230Z_2D_Britheim_SV_1.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml",
        f"{FOLDER}/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml",
    ],

    "Espheim": [  # Espheim
        f"{FOLDER}/Espheim/Grid/cimxml/20220615T2230Z__Espheim_EQ_1.xml",
        f"{FOLDER}/Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_SSH_1.xml",
        f"{FOLDER}/Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_SV_1.xml",
        f"{FOLDER}/Espheim/Grid/cimxml/20220615T2230Z_2D_Espheim_TP_1.xml",
        f"{FOLDER}/DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_TP_1.xml",
        f"{FOLDER}/DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SV_1.xml",
        f"{FOLDER}/DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SSH_1.xml",
        f"{FOLDER}/DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z__HVDC-Espheim-Svedala_EQ_1.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml",
        f"{FOLDER}/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml",

    ],

    "Galia": [  # Galia
        f"{FOLDER}/Galia/Grid/cimxml/20220615T2230Z_2D_Galia_TP_1.xml",
        f"{FOLDER}/Galia/Grid/cimxml/20220615T2230Z_2D_Galia_SSH_1.xml",
        f"{FOLDER}/Galia/Grid/cimxml/20220615T2230Z__Galia_EQ_1.xml",
        f"{FOLDER}/Galia/Grid/cimxml/20220615T2230Z_2D_Galia_SV_1.xml",
        # f"{FOLDER}/DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z_2D_HVDC-Nordheim-Galia_SSH_1.xml",
        # f"{FOLDER}/DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z_2D_HVDC-Nordheim-Galia_TP_1.xml",
        # f"{FOLDER}/DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z__HVDC-Nordheim-Galia_EQ_1.xml",
        # f"{FOLDER}/DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z_2D_HVDC-Nordheim-Galia_SV_1.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml",
        f"{FOLDER}/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml",
    ],

    "Jotunheim": [
        f"{FOLDER}/Jotunheim/Grid/cimxml/20220615T2230Z_2D_Svedala_SSH_2.xml",
        f"{FOLDER}/Jotunheim/Grid/cimxml/20220615T2230Z_2D_Britheim_SSH_2.xml",
        f"{FOLDER}/Jotunheim/Grid/cimxml/20220615T2230Z_2D_Jotunheim_TP_1.xml",
        f"{FOLDER}/Jotunheim/Grid/cimxml/20220615T2230Z_2D_Belgovia_SSH_2.xml",
        f"{FOLDER}/Jotunheim/Grid/cimxml/20220615T2230Z_2D_HVDC_Espheim-Svedala_SSH_2.xml",
        f"{FOLDER}/Jotunheim/Grid/cimxml/20220615T2230Z_2D_HVDC_Nordheim-Galia_SSH_2.xml",
        f"{FOLDER}/Jotunheim/Grid/cimxml/20220615T2230Z_2D_Jotunheim_SV_1.xml",
        f"{FOLDER}/Jotunheim/Grid/cimxml/20220615T2230Z_2D_Espheim_SSH_2.xml",
        f"{FOLDER}/Jotunheim/Grid/cimxml/20241223T0642Z_2D_Portheim_SSH_2.xml",
        f"{FOLDER}/Jotunheim/Grid/cimxml/20220615T2230Z_2D_Nordheim_SSH_2.xml",
        f"{FOLDER}/Jotunheim/Grid/cimxml/20220615T2230Z_2D_Galia_SSH_2.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml",
        f"{FOLDER}/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml",
    ],

    "Nordheim": [
        f"{FOLDER}/Nordheim/Grid/cimxml/20220615T2230Z_2D_Nordheim_SV_1.xml",
        f"{FOLDER}/Nordheim/Grid/cimxml/20220615T2230Z_2D_Nordheim_SSH_1.xml",
        f"{FOLDER}/Nordheim/Grid/cimxml/20220615T2230Z__Nordheim_EQ_1.xml",
        f"{FOLDER}/Nordheim/Grid/cimxml/20220615T2230Z_2D_Nordheim_TP_1.xml",
        # f"{FOLDER}/DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z_2D_HVDC-Nordheim-Galia_SSH_1.xml",
        # f"{FOLDER}/DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z_2D_HVDC-Nordheim-Galia_TP_1.xml",
        # f"{FOLDER}/DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z__HVDC-Nordheim-Galia_EQ_1.xml",
        # f"{FOLDER}/DC-Nordheim-Galia/Grid/cimxml/20220615T2230Z_2D_HVDC-Nordheim-Galia_SV_1.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml",
        f"{FOLDER}/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml",
    ],

    "Portheim": [
        f"{FOLDER}/Portheim/Grid/cimxml/20241223T0642Z_2D_Portheim_EQ_1.xml",
        f"{FOLDER}/Portheim/Grid/cimxml/20241223T0642Z_2D_Portheim_SSH_1.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml",
        f"{FOLDER}/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml",
    ],

    "Svedala": [
        f"{FOLDER}/Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SV_1.xml",
        f"{FOLDER}/Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_TP_1.xml",
        f"{FOLDER}/Svedala/Grid/cimxml/20220615T2230Z_2D_Svedala_SSH_1.xml",
        f"{FOLDER}/Svedala/Grid/cimxml/20220615T2230Z__Svedala_EQ_1.xml",
        # f"{FOLDER}/DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_TP_1.xml",
        # f"{FOLDER}/DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SV_1.xml",
        # f"{FOLDER}/DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z_2D_HVDC-Espheim-Svedala_SSH_1.xml",
        # f"{FOLDER}/DC-Espheim-Svedala/Grid/cimxml/20220615T2230Z__HVDC-Espheim-Svedala_EQ_1.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Belgovia.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Britheim.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Espheim.xml",
        f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Svedala-Belgovia.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Espheim-Portheim.xml",
        # f"{FOLDER}/boundaryData/Grid/cimxml/Boundary_Border-Galia-Nordheim.xml",
        f"{FOLDER}/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml",
        # f"{FOLDER}/commonData/NetworkCode/cimxml/Org-NineRealms_CD_OR.xml",
    ]
}


def get_xml_files_from_folders(folders):
    xml_files = []
    for folder in folders:
        if not os.path.isdir(folder):
            continue

        for root, _, files in os.walk(folder):
            for file_name in files:
                if file_name.lower().endswith(".xml"):
                    xml_files.append(os.path.join(root, file_name))
    return xml_files


pf_options = vg.PowerFlowOptions(tolerance=1e-6,
                                 solver_type=vg.SolverType.NR,
                                 retry_with_other_methods=False,
                                 ignore_single_node_islands=True)

summary = list()
for name, files in SUBFOLDERS.items():

    handler = vg.FileOpen(
        file_name=files,
        options=vg.FileOpenOptions(
            cgmes_version=vg.CGMESVersions.v3_0_0,
            file_type=vg.FileType.CGMES
        )
    )
    grid = handler.open()

    if grid is not None:
        print("-" * 200)
        print(name)
        print("")
        for e in files:
            print("\t", e)
        res = vg.power_flow(grid, pf_options)
        handler.cgmes_logger.to_xlsx(name + ".xlsx")
        print("\tconverged:", res.converged)

        summary.append((name, res.converged, res.error))

print("-" * 200)

summary_df = pd.DataFrame(data=summary, columns=["Name", "Converged", "Error"])
with pd.option_context("display.float_format", "{:.3e}".format):
    print(summary_df)