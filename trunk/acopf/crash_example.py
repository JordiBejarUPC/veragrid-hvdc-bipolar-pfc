import VeraGridEngine as vg

fname = "/home/santi/Git/eRoots/VeraGridDemos/Trainings/CND/Training_CND_19AUG2026_real.veragrid"
grid = vg.open_file(fname)

if grid is not None:
    opts = vg.OptimalPowerFlowOptions(
        solver=vg.SolverType.NONLINEAR_OPF
    )
    res = vg.nonlinear_opf(grid, opts)
    print("converged:", res.converged)