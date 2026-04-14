import VeraGridEngine as vg

fname = "/home/santi/Documentos/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39.gridcal"

grid = vg.open_file(fname)

vg.save_file(grid=grid, filename="IEEE39_vg.dgs")
