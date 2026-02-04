from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit


fname = "IEEE_14.dgs"

dgs_grid = DgsCircuit()
dgs_grid.parse_dgs(fname)
dgs_grid.write_dgs("example.dgs")

grid = dgs_grid.to_veragrid()

print()
