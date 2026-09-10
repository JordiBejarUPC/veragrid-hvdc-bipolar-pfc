import os
import VeraGridEngine as vg

name = "COES_dgsv6.dgs"
grid_name = os.path.join(name)
grid = vg.open_file(grid_name, options=vg.FileOpenOptions(file_type=vg.FileType.DGS))

gens = grid.get_generators()

for gen in gens:
    gen.control_mode = "V"

vg.save_file(grid,"COES_dgsv6_Vmode.dgs")