from VeraGridEngine.Topology.GridReduction.ptdf_grid_reduction import ptdf_reduction, ptdf_reduction_projected
import VeraGridEngine.api as gce
import numpy as np


def get_total_generation_ts(grid: gce.MultiCircuit, time_indices: np.ndarray = None) -> np.ndarray:
    """
    Get total generation profile for time series
    :param grid: MultiCircuit instance
    :param time_indices: Optional array of time indices to select
    :return: Total generation profile in MW (nt,)
    """
    if time_indices is None:
        time_indices = grid.get_all_time_indices()

    nt = len(time_indices)
    total = np.zeros(nt, dtype=float)

    for gen in grid.generators:
        if gen.P_prof is not None:
            prof = gen.P_prof.toarray()[time_indices] * gen.active_prof.toarray()[time_indices]
            total += prof

    for batt in grid.batteries:
        if batt.P_prof is not None:
            prof = batt.P_prof.toarray()[time_indices] * batt.active_prof.toarray()[time_indices]
            total += prof

    for stagen in grid.static_generators:
        if stagen.P_prof is not None:
            prof = stagen.P_prof.toarray()[time_indices] * stagen.active_prof.toarray()[time_indices]
            total += prof

    return total


def get_total_load_ts(grid: gce.MultiCircuit, time_indices: np.ndarray = None) -> np.ndarray:
    """
    Get total load profile for time series
    :param grid: MultiCircuit instance
    :param time_indices: Optional array of time indices to select
    :return: Total load profile in MW (nt,)
    """
    if time_indices is None:
        time_indices = grid.get_all_time_indices()

    nt = len(time_indices)
    total = np.zeros(nt, dtype=float)

    for load in grid.loads:
        if load.P_prof is not None:
            prof = load.P_prof.toarray()[time_indices] * load.active_prof.toarray()[time_indices]
            total += prof

    return total


grid = gce.open_file("/home/santi/Escritorio/Redes/MOU_2022_5GW_v6c.gridcal")

# First run time series linear analysis
lin_ts = gce.LinearAnalysisTs(grid=grid, distributed_slack=False)
P_orig = grid.get_Pbus_prof()
Flows_orig = lin_ts.get_flows_ts(P=P_orig)

# Then reduce the network
bus_to_remove = list()
bus_idx_dict = grid.get_bus_index_dict()
for bus in grid.buses:
    if bus.Vnom < 400:
        bus_remove_idx = bus_idx_dict[bus]
        bus_to_remove.append(bus_remove_idx)

bus_to_remove = np.array(bus_to_remove)

# Get internal branches before reduction to compare later
external, boundary, internal, boundary_branches, internal_branches = grid.get_reduction_sets(
    reduction_bus_indices=bus_to_remove)

red_grid, logger = ptdf_reduction_projected(grid=grid, reduction_bus_indices=bus_to_remove, distribute_slack=False)

# Run time series linear analysis on reduced grid
lin_ts_red = gce.LinearAnalysisTs(grid=red_grid, distributed_slack=False)
P_red = red_grid.get_Pbus_prof()
Flows_red = lin_ts_red.get_flows_ts(P=P_red)

# Compare flows on internal branches
Flows_orig_internal = Flows_orig[:, internal_branches]

# Check if dimensions match
if not (Flows_red.shape[1] == len(internal_branches)):
    print("Dimensions are not equal")

# Compare flows
if not np.allclose(Flows_orig_internal, Flows_red, atol=1e-4):
    print("Flows are not equal")

    print(Flows_orig_internal)
    print(Flows_red)

# Check power balance for all time steps: total generation and demand should not change
all_time_indices = grid.get_all_time_indices()
P_orig_gen_ts = get_total_generation_ts(grid, time_indices=all_time_indices)
P_orig_load_ts = get_total_load_ts(grid, time_indices=all_time_indices)
P_red_gen_ts = get_total_generation_ts(red_grid, time_indices=all_time_indices)
P_red_load_ts = get_total_load_ts(red_grid, time_indices=all_time_indices)

if not np.allclose(P_orig_gen_ts, P_red_gen_ts, atol=1e-4):
    print("Injections snapshot not respected")

if not np.allclose(P_orig_load_ts, P_red_load_ts, atol=1e-4):
    print("Injections TS not respected")