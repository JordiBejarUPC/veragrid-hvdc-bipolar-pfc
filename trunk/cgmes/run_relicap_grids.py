import os
import VeraGridEngine as vg

FOLDER = "/home/santi/Git/GitHub/relicapgrid/Instance"

SUBFOLDERS = [
    (f"{FOLDER}/Belgovia/Grid/cimxml",),

    (f"{FOLDER}/Britheim/Grid/cimxml",),

    (f"{FOLDER}/Espheim/Grid/cimxml",
     f"{FOLDER}/DC-Espheim-Svedala/Grid/cimxml"),

    (f"{FOLDER}/Galia/Grid/cimxml",
     f"{FOLDER}/DC-Nordheim-Galia/Grid/cimxml"),

    (f"{FOLDER}/Jotunheim/Grid/cimxml",),

    (f"{FOLDER}/Nordheim/Grid/cimxml",
     f"{FOLDER}/DC-Nordheim-Galia/Grid/cimxml"),

    (f"{FOLDER}/Portheim/Grid/cimxml",),

    (f"{FOLDER}/Svedala/Grid/cimxml",
     f"{FOLDER}/DC-Espheim-Svedala/Grid/cimxml"),
]

COMMON_FOLDERS = [
    f"{FOLDER}/boundaryData",
    f"{FOLDER}/commonData"
]

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
for folders1 in SUBFOLDERS:
    name = folders1[0].replace(FOLDER, "").split("/")[1]

    folders2 = list(folders1) + COMMON_FOLDERS
    files1 = get_xml_files_from_folders(folders2)
    # grid = vg.open_cgmes(filenames=files1, cgmes_version=vg.CGMESVersions.v3_0_0)

    handler = vg.FileOpen(
        file_name=files1,
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
        for e in files1:
            print("\t", e)
        res = vg.power_flow(grid, pf_options)
        handler.logger.to_xlsx(name + ".xlsx")
        print("\tconverged:", res.converged)