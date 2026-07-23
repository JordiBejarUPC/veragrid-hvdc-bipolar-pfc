"""Test power flow convergence on the IEEE 33 FlexDis grid with VSC converters."""
import sys
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.enumerations import SolverType

grid = gce.open_file('/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid')

print(f"Grid: {len(grid.buses)} buses, {len(grid.vsc_devices)} VSC devices, "
      f"{len(grid.generators)} generators, {len(grid.lines)} lines")
print()

pf_options = PowerFlowOptions(solver_type=SolverType.NR, retry_with_other_methods=False)
results = gce.power_flow(grid, options=pf_options)

# Convergence reports
print("=== Convergence Reports ===")
for i, report in enumerate(results.convergence_reports):
    for j in range(len(report.methods_)):
        print(f"  Island {i}, method={report.methods_[j]}: "
              f"converged={report.converged_[j]}, "
              f"error={report.error_[j]:.6e}, "
              f"iterations={report.iterations_[j]}, "
              f"elapsed={report.elapsed_[j]:.4f}s")

print()

# Bus voltages
print("=== Bus Voltages ===")
bus_names = grid.get_bus_names()
for i, (name, v) in enumerate(zip(bus_names, results.voltage)):
    vm = abs(v)
    va = np.degrees(np.angle(v))
    print(f"  {name:15s}  |V|={vm:.4f} p.u.  angle={va:+.4f} deg")

print()

# VSC results
print("=== VSC Results ===")
for i, vsc in enumerate(grid.vsc_devices):
    print(f"  {vsc.name:20s}  "
          f"Pfp={results.Pfp_vsc[i]:+.4f} MW  "
          f"St={results.St_vsc[i]:.4f} MVA  "
          f"losses={results.losses_vsc[i]:.6f} MW  "
          f"loading={results.loading_vsc[i]*100:.2f}%")
