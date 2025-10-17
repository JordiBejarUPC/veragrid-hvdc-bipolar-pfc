# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.Topology.GridReduction.ptdf_grid_reduction import ptdf_reduction


def test_ward_reduction():
    """
    Test to check the PTDF reduction
    :return:
    """
    fname = os.path.join('data', 'grids', 'case89pegase.m')
    grid = gce.open_file(filename=fname)

    remove_bus_idx = np.array([21, 36, 44, 50, 53])
    expected_boundary_idx = np.sort(np.array([20, 77, 15, 32]))

    external, boundary, internal, boundary_branches, internal_branches = grid.get_reduction_sets(reduction_bus_indices=remove_bus_idx)

    assert np.equal(expected_boundary_idx, boundary).all()

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.Linear)

    pf_res = gce.power_flow(grid=grid, options=pf_options)

    # gce.ward_reduction(grid=grid, reduction_bus_indices=remove_bus_idx, pf_res=pf_res)
    nc = gce.compile_numerical_circuit_at(circuit=grid, t_idx=None)
    lin = gce.LinearAnalysis(nc=nc)

    P0 = grid.get_Pbus()
    Flows0 = lin.get_flows(P0)

    # if grid.has_time_series:
    #     lin_ts = gce.LinearAnalysisTs(grid=grid)
    # else:
    #     lin_ts = None

    grid2, logger = ptdf_reduction(grid=grid,
                                   reduction_bus_indices=remove_bus_idx)

    nc2 = gce.compile_numerical_circuit_at(circuit=grid2, t_idx=None)
    lin2 = gce.LinearAnalysis(nc=nc2)

    # proof that the flows are actually the same
    Pbus4 = grid.get_Pbus()
    Flows4 = lin2.PTDF @ Pbus4
    diff = Flows0[internal_branches] - Flows4

    ok = np.allclose(Flows4, Flows0[internal_branches], atol=1e-10)
    assert ok


if __name__ == '__main__':
    test_ward_reduction()
