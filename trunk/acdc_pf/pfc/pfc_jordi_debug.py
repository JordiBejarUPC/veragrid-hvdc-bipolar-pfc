from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
import VeraGridEngine.api as vg

grid = vg.open_file("src/trunk/acdc_pf/pfc/pfc_example_connected.veragrid")

pf_options = vg.PowerFlowOptions(solver_type = vg.SolverType.NR,
                                 tolerance=1e-10,
                                 retry_with_other_methods=False)

pf_driver = PowerFlowDriver(grid, pf_options)

pf_driver.run()

print(f"Converged: {pf_driver.results.converged}")
print(f"Abs voltages: {pf_driver.results.voltage}")