import pygslv as pg

# pg.activate(r"my_license.gslv", verbose=True)
pg.search_license_and_activate()

print("GSLV", pg.get_version())

logger = pg.Logger()
verbose = 0
fname = "/home/santi/Documentos/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal"
mc: pg.MultiCircuit = pg.read_file(fname, logger, verbose)

options = pg.PowerFlowOptions(solver_type=pg.SolverType.NR)
nt = len(mc.time_array)
res = pg.multi_island_pf(grid=mc, options=options, time_indices=list(range(nt)))

pg.Bus()

print(res.voltage)  # per-unit voltage matrix