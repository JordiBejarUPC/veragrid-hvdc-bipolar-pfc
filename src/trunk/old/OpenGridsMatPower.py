import VeraGridEngine as gce

my_grid = gce.open_file("../grids/case5_2grids_MC.m")

gce.save_file(my_grid, "case5_2grids_MC.veragrid")
