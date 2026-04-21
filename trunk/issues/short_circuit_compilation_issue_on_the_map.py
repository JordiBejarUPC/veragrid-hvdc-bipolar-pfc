"""
Debug script: open the grid file and attempt to compile the numerical circuit.
No neutralization, no IEC-60909 corrections — just open + compile.
"""

import os
import VeraGridEngine as gce

script_dir = os.path.dirname(__file__)

# input_grid = os.path.join(
#     script_dir, '..', '..', 'Model', 'daily_freezes', '20260312', 'merge_20260312.veragrid'
# )

input_grid = "/home/santi/Git/eRoots/M-project/Model/daily_freezes/20260312/merge_20260312.veragrid"

print(f"Loading grid: {input_grid}")
grid = gce.open_file(input_grid)
print(f"Grid loaded. Buses: {len(grid.buses)}, Generators: {len(grid.generators)}")

print("Compiling numerical circuit...")
nc = gce.compile_numerical_circuit_at(circuit=grid)
print(f"Compiled. nbus={nc.nbus}, ngen={nc.ngen}")