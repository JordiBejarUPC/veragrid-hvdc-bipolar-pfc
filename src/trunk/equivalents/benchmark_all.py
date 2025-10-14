import os
import numpy as np
import pandas as pd
import VeraGridEngine as vg
from VeraGridEngine.Topology.GridReduction.di_shi_grid_reduction import di_shi_reduction
from VeraGridEngine.Topology.GridReduction.ptdf_grid_reduction import ptdf_reduction
from VeraGridEngine.Topology.GridReduction.ward_equivalents import ward_standard_reduction

fname = os.path.join('..', '..', 'tests', 'data', 'grids', 'Matpower', 'case118.m')

grid = vg.open_file(fname)

reduction_bus_indices = np.array([
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
    20, 21, 22, 23, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 38, 113, 114, 115, 117
]) - 1  # minus 1 for zero based indexing

for pf_method in [vg.SolverType.NR, vg.SolverType.Linear]:
    pf_opt = vg.PowerFlowOptions(solver_type=pf_method)
    pf_res = vg.power_flow(grid=grid, options=pf_opt)

    # build a dictionary with the from flows
    flow_d = {
        br.idtag: pf_res.Sf[k]
        for k, br in enumerate(grid.get_branches_iter())
    }

    for method in [vg.GridReductionMethod.DiShi,
                   vg.GridReductionMethod.PTDF,
                   vg.GridReductionMethod.Ward]:

        if method == vg.GridReductionMethod.DiShi:

            grid2, logger = di_shi_reduction(
                grid=grid.copy(),
                reduction_bus_indices=reduction_bus_indices,
                V0=pf_res.voltage
            )

        elif method == vg.GridReductionMethod.PTDF:

            nc = vg.compile_numerical_circuit_at(circuit=grid, t_idx=None)
            lin = vg.LinearAnalysis(nc=nc)

            if grid.has_time_series:
                lin_ts = vg.LinearAnalysisTs(grid=grid)
            else:
                lin_ts = None

            grid2, logger = ptdf_reduction(
                grid=grid.copy(),
                reduction_bus_indices=reduction_bus_indices,
                PTDF=lin.PTDF,
                lin_ts=lin_ts
            )

        elif method == vg.GridReductionMethod.Ward:

            grid2 = ward_standard_reduction(
                grid=grid.copy(),
                reduction_bus_indices=reduction_bus_indices,
                V0=pf_res.voltage,
                logger=vg.Logger()
            )
        else:
            raise Exception("Method not found :(")

        # run a power flow after
        pf_res2 = vg.power_flow(grid=grid2, options=pf_opt)

        # build the flows comparison dictionary
        flow_d2 = dict()

        for k, br in enumerate(grid2.get_branches_iter()):
            Sf_pre = flow_d.get(br.idtag, None)

            if Sf_pre is not None:
                flow_d2[br.idtag] = {
                    "name": br.name,
                    "Pf pre": Sf_pre.real,
                    "Pf post": pf_res2.Sf[k].real,
                    "Pf err": abs(Sf_pre.real - pf_res2.Sf[k].real),
                    "Pf err %": abs(Sf_pre.real - pf_res2.Sf[k].real) / Sf_pre.real,
                    "Qf pre": Sf_pre.imag,
                    "Qf post": pf_res2.Sf[k].imag,
                    "Qf err": abs(Sf_pre.imag - pf_res2.Sf[k].imag),
                }

        df_flow_comp = pd.DataFrame(data=flow_d2).transpose()

        # print(df_flow_comp)

        print()
        print(pf_method.value, method.value)
        print("Mean error:", df_flow_comp["Pf err"].mean(), '+-', df_flow_comp["Pf err"].std())
        print("Mean error %:", df_flow_comp["Pf err %"].mean(), '+-', df_flow_comp["Pf err %"].std())
