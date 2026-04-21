import os
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
import VeraGridEngine.api as vg

# Load the 12-bus AC/DC grid
fname = os.path.join(os.path.dirname(__file__), "12bus_acdc.gridcal")
grid = vg.open_file(fname)

# Set up power flow options
pf_options = vg.PowerFlowOptions(solver_type=vg.SolverType.NR,
                                 tolerance=1e-10,
                                 retry_with_other_methods=False)

# Run the power flow
pf_driver = PowerFlowDriver(grid, pf_options)
pf_driver.run()

# Print results
print(f"Converged: {pf_driver.results.converged}")
print(f"Voltages: {pf_driver.results.voltage}")
