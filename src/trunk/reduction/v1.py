import os
import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.Topology.GridReduction.ptdf_grid_reduction import ptdf_reduction, ptdf_reduction_projected
from VeraGridEngine.Topology.GridReduction.ward_equivalents import ward_standard_reduction
from VeraGridEngine.Topology.GridReduction.di_shi_grid_reduction import di_shi_reduction


def run_simple_ptdf_projected():
    """
    Test to check the PTDF projected reduction in a very simple grid
    :return:
    """
    fname = '/Users/josep/Documents/grids_ree_ane1/6bus_antena.veragrid'
    # fname = '/Users/josep/Documents/grids_ree_ane1/5bus_linear_v2.veragrid'
    grid = gce.open_file(filename=fname)

    # First run basic linear analysis
    flows_dr = gce.LinearAnalysisDriver(grid=grid, options=gce.LinearAnalysisOptions(distribute_slack=True))
    flows_dr.run()
    flows_branches = flows_dr.results.Sf

    for load in grid.loads:
        print(f"Load {load.name}: {load.P}")

    for gen in grid.generators:
        print(f"Generator {gen.name}: {gen.P}")

    # Then reduce the network
    bus_to_remove = np.array([1])
    red_grid, logger = ptdf_reduction_projected(grid=grid, reduction_bus_indices=bus_to_remove, distribute_slack=True)
    flows_dr_red = gce.LinearAnalysisDriver(grid=red_grid, options=gce.LinearAnalysisOptions(distribute_slack=True))
    flows_dr_red.run()
    flows_branches_red = flows_dr_red.results.Sf

    print(f"Flows initial: {flows_branches}")
    print(f"Flows reduced: {flows_branches_red}")

    for load in grid.loads:
        print(f"Load {load.name}: {load.P}")

    for gen in grid.generators:
        print(f"Generator {gen.name}: {gen.P}")

    return None


if __name__ == "__main__":
    run_simple_ptdf_projected()     

 
