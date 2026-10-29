import pygslv as pg

print("GSLV", pg.get_version())
pg.search_license_and_activate()

logger = pg.Logger()
verbose = 0
mc: pg.MultiCircuit = pg.read_file("IEEE39_1W.VeraGrid", logger, verbose)

options = pg.PowerFlowOptions(solver_type=pg.SolverType.NR)
nt = len(mc.time_array)
res = pg.multi_island_pf(grid=mc, options=options, time_indices=list(range(nt)))

print(res.voltage)  # per-unit voltage matrix