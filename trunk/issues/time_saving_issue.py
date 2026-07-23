import VeraGridEngine as vg

#fname = "/Users/santi/Desktop/TYNDP/TYNDP_2030_TOOT_PINT_results.veragrid"
fname = "/Users/santi/Desktop/TYNDP/base_s_all___2030.veragrid"

grid1 = vg.open_file(fname)
print(grid1.time_profile)

fname2 = "test.veragrid"
vg.save_file(grid=grid1, filename=fname2)
grid2 = vg.open_file(fname2)
print(grid2.time_profile)

# -------------------------------------
print("-" * 200)

mv1 = vg.open_multiverse(fname)
print(mv1.base_model.time_profile)

fname2 = "test_mv.veragrid"
vg.save_multiverse(mv=mv1, filename=fname2)
mv2 = vg.open_multiverse(fname2)
print(mv2.base_model.time_profile)