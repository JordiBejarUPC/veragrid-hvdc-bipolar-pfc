import os
import VeraGridEngine as vg

fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', "rms_simple_model.veragrid")
fname = "/home/pablo/Desktop/eroots/VeraGrid/Grids_and_profiles/grids/rms_simple_model.veragrid"
# fname = "/Users/santi/Git/GitHub/VeraGrid/Grids_and_profiles/grids/rms_simple_model.veragrid"

grid = vg.open_file(fname)

pf_results = vg.power_flow(grid=grid)

rms_driver = vg.RmsSimulationDriver(grid=grid, options=vg.RmsOptions(),
                                    pf_results=pf_results)

rms_driver.run()
