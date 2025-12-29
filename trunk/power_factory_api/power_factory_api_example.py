from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit


fname = "IEEE_14.dgs"

pf_path = r"C:\Program Files\DIgSILENT\PowerFactory 2025 SP1"
dgs_grid2 = DgsCircuit()
dgs_grid2.from_api(pf_path=pf_path)

print()
