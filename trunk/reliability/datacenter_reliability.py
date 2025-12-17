import VeraGridEngine as vg

fname = '/home/santi/Descargas/ARGON_GRID_improved.veragrid'

grid = vg.open_file(fname)
grid.create_profiles(steps=8760, step_length=1, step_unit="h")

pf_options = vg.PowerFlowOptions()
drv = vg.ReliabilityStudyDriver(
    grid=grid,
    pf_options=pf_options,
    reliability_mode=vg.ReliabilityMode.GridMetrics,
    time_indices=None,  # all,
    n_sim=100
)

drv.run()

print()
