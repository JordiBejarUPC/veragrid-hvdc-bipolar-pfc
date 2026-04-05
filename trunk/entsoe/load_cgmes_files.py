import VeraGridEngine as vg


grid = vg.open_cgmes(
    filenames=[
"/home/santi/Git/eRoots/VeraGrid/src/tests/data/grids/CGMES_2_4_15/micro_grid_NL_T1.zip",
"/home/santi/Git/eRoots/VeraGrid/src/tests/data/grids/CGMES_2_4_15/micro_grid_BD.zip"
    ]
)

print(grid)