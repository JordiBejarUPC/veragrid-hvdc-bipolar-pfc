import VeraGridEngine as vg

fname = "/home/santi/Git/eRoots/VeraGridDemos/CND/Training_CND_19AUG2026_real.veragrid"
grid = vg.open_file(fname)

if grid is not None:
    opts = vg.ContingencyAnalysisOptions(
        contingency_method=vg.ContingencyMethod.PowerFlow,
        contingency_groups=grid.contingency_groups,
        pf_options=vg.PowerFlowOptions(
            solver_type=vg.SolverType.HELM
        )
    )
    res = vg.contingency_analysis(grid, opts)