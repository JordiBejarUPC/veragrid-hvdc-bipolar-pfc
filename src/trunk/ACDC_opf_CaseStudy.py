import VeraGridEngine as gce
from VeraGridEngine.enumerations import FileType


my_grid = gce.open_file(filename="grids/case3120sp_acdc.m", options=gce.FileOpenOptions(file_type=FileType.Matpower))

gce.save_file(my_grid, "grids/case3120sp_acdc.veragrid")

input_grid = 'grids/case3120sp_acdc.veragrid'
grid = gce.open_file(input_grid)

# print("Grid Buses:")
# for i, bus in enumerate(grid.buses):
#     print(f"  [{i}] {bus.name} - is_dc: {bus.is_dc}, Vnom: {bus.Vnom}")

opf_options = gce.OptimalPowerFlowOptions(verbose=2,
                                          solver=gce.SolverType.NONLINEAR_OPF,
                                          ips_tolerance=1e-6,
                                          ips_iterations=500,
                                          ips_trust_radius=1.0,
                                          ips_init_with_pf=False,
                                          ips_control_q_limits=False,
                                          acopf_mode=gce.AcOpfMode.ACOPFstd,
                                          acopf_v0=None,
                                          acopf_S0=None,
                                         )

opf_driver = gce.OptimalPowerFlowDriver(grid=grid, options=opf_options)
opf_driver.run()

opf_res: gce.OptimalPowerFlowResults = opf_driver.results
print("Converged:", opf_res.converged)
print("Error:", opf_res.error)
print("Buses:\n", opf_res.get_bus_df())
print("Generators:\n", opf_res.get_gen_df())
print("Branches:\n", opf_res.get_branch_df())
