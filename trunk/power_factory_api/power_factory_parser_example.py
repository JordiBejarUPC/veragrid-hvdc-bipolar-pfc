from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit


fname = "IEEE_14.dgs"

dgs_grid = DgsCircuit()
dgs_grid.parse(fname)

print()
