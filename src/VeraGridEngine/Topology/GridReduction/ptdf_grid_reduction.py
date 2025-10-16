# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
import networkx as nx
from typing import Tuple, Sequence, TYPE_CHECKING
from VeraGridEngine.basic_structures import IntVec, Mat, Logger, Vector
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.battery import Battery
from VeraGridEngine.Devices.Injections.static_generator import StaticGenerator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysisTs, LinearAnalysis

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysisTs


def ptdf_reduction_old(grid: MultiCircuit,
                       reduction_bus_indices: IntVec,
                       PTDF: Mat,
                       lin_ts: LinearAnalysisTs,
                       tol=1e-8,
                       aggregate_devices: bool = False) -> Tuple[MultiCircuit, Logger]:
    """
    In-place Grid reduction using the PTDF injection mirroring
    No theory available
    :param grid: MultiCircuit
    :param reduction_bus_indices: Bus indices of the buses to delete
    :param PTDF: PTDF matrix
    :param lin_ts: LinearAnalysisTs
    :param tol: Tolerance, any equivalent power value under this is omitted
    :param aggregate_devices: Aggregate boundary devices (optional)
    """
    logger = Logger()

    # find the boundary set: buses from the internal set the join to the external set
    e_buses, b_buses, i_buses, b_branches = grid.get_reduction_sets(reduction_bus_indices=reduction_bus_indices)

    if len(e_buses) == 0:
        logger.add_info(msg="Nothing to reduce")
        return grid, logger

    if len(i_buses) == 0:
        logger.add_info(msg="Nothing to keep (null grid as a result)")
        return grid, logger

    if len(b_buses) == 0:
        logger.add_info(msg="The reducible and non reducible sets are disjoint and cannot be reduced")
        return grid, logger

    # Start moving objects
    e_buses_set = set(e_buses)
    bus_dict = grid.get_bus_index_dict()
    has_ts = grid.has_time_series

    if has_ts and lin_ts is None:
        logger.add_error("You must provide the lin_ts parameter")
        return grid, logger

    nb = len(b_buses)
    boundary_generators_with_srap = np.zeros(nb, dtype=int)
    boundary_generators_count = np.zeros(nb, dtype=int)
    boundary_generators = Vector(nb, value=list())
    boundary_batteries = Vector(nb, value=list())
    boundary_loads = Vector(nb, value=list())
    boundary_stagen = Vector(nb, value=list())

    for elm in grid.get_injection_devices():
        if elm.bus is not None:
            i = bus_dict[elm.bus]  # bus index where it is currently connected

            if i in e_buses_set:
                # this injection is to be reduced

                for b in range(len(b_buses)):
                    bus_idx = b_buses[b]
                    branch_idx = b_branches[b]
                    bus = grid.buses[bus_idx]
                    ptdf_val = PTDF[branch_idx, bus_idx]

                    if abs(ptdf_val) > tol:

                        # create new device at the boundary bus
                        if elm.device_type == DeviceType.GeneratorDevice:
                            new_elm = elm.copy()
                            elm.bus = bus
                            new_elm.comment = "PTDF reduced equivalent generator"
                            new_elm.P = ptdf_val * elm.P
                            if has_ts:
                                new_elm.P_prof = lin_ts.get_branch_flow_ts(branch_idx, bus_idx, elm.P_prof.toarray())

                            new_elm.comment = "PTDF reduced equivalent generator"
                            if aggregate_devices:
                                boundary_generators[b].append(new_elm)
                                boundary_generators_count[b] += 1
                                if elm.srap_enabled:
                                    boundary_generators_with_srap[b] += 1
                            else:
                                grid.add_generator(bus=bus, api_obj=new_elm)

                        elif elm.device_type == DeviceType.BatteryDevice:
                            new_elm = elm.copy()
                            elm.bus = bus
                            new_elm.P = ptdf_val * elm.P
                            if has_ts:
                                new_elm.P_prof = lin_ts.get_branch_flow_ts(branch_idx, bus_idx, elm.P_prof.toarray())

                            new_elm.comment = "PTDF reduced equivalent battery"

                            if aggregate_devices:
                                boundary_batteries[b].append(new_elm)
                            else:
                                grid.add_battery(bus=bus, api_obj=new_elm)

                        elif elm.device_type == DeviceType.StaticGeneratorDevice:
                            new_elm = elm.copy()
                            elm.bus = bus
                            new_elm.P = ptdf_val * elm.P
                            new_elm.Q = ptdf_val * elm.Q
                            if has_ts:
                                new_elm.P_prof = lin_ts.get_branch_flow_ts(branch_idx, bus_idx, elm.P_prof.toarray())
                                new_elm.Q_prof = lin_ts.get_branch_flow_ts(branch_idx, bus_idx, elm.Q_prof.toarray())

                            new_elm.comment = "PTDF reduced equivalent static generator"

                            if aggregate_devices:
                                boundary_stagen[b].append(new_elm)
                            else:
                                grid.add_static_generator(bus=bus, api_obj=new_elm)

                        elif elm.device_type == DeviceType.LoadDevice:
                            new_elm = elm.copy()
                            elm.bus = bus
                            new_elm.P = ptdf_val * elm.P
                            new_elm.Q = ptdf_val * elm.Q
                            if has_ts:
                                new_elm.P_prof = lin_ts.get_branch_flow_ts(branch_idx, bus_idx, elm.P_prof.toarray())
                                new_elm.Q_prof = lin_ts.get_branch_flow_ts(branch_idx, bus_idx, elm.Q_prof.toarray())

                            new_elm.comment = "PTDF reduced equivalent load"

                            if aggregate_devices:
                                boundary_loads[b].append(new_elm)
                            else:
                                grid.add_load(bus=bus, api_obj=new_elm)

                        else:
                            # device I don't care about
                            logger.add_warning(msg="Ignored device",
                                               device=str(elm),
                                               device_class=elm.device_type.value)

    if aggregate_devices:

        for b in range(nb):  # for every boundary bus ...

            bus_idx = b_buses[b]
            bus = grid.buses[bus_idx]

            # Generators -----------------------------------------------------------------------------------------------
            gen_list = boundary_generators[b]
            srap_gen_count = boundary_generators_with_srap[b]
            total_gen_count = boundary_generators_count[b]

            if total_gen_count > 0:

                if srap_gen_count > 0:
                    # we make 2 generator because of things
                    gen_no_srap = Generator(name=f"Gen no Srap")
                    gen_srap = Generator(name=f"Gen with Srap", srap_enabled=True)

                    for gen in gen_list:
                        if gen.srap_enabled:
                            gen_srap += gen
                        else:
                            gen_no_srap += gen

                    grid.add_generator(bus=bus, api_obj=gen_srap)
                    grid.add_generator(bus=bus, api_obj=gen_no_srap)

                else:
                    gen_no_srap = Generator(name=f"Equivalent boundary gen")
                    for gen in gen_list:
                        gen_no_srap += gen
                    grid.add_generator(bus=bus, api_obj=gen_no_srap)
            else:
                pass

            # Loads ----------------------------------------------------------------------------------------------------
            load = Load(name=f"Equivalent boundary load")
            for elm in boundary_loads[b]:
                load += elm
            grid.add_load(bus=bus, api_obj=load)

            # StaticGenerator ------------------------------------------------------------------------------------------
            stagen = StaticGenerator(name=f"Equivalent boundary load")
            for elm in boundary_stagen[b]:
                stagen += elm
            grid.add_static_generator(bus=bus, api_obj=stagen)

            # Batteries ------------------------------------------------------------------------------------------------
            batt = Battery(name=f"Equivalent boundary battery")
            for elm in boundary_batteries[b]:
                batt += elm
            grid.add_battery(bus=bus, api_obj=batt)

    # Delete the external buses
    to_be_deleted = [grid.buses[e] for e in e_buses]
    for bus in to_be_deleted:
        grid.delete_bus(obj=bus, delete_associated=True)

    return grid, logger


def relocate_injections(grid: MultiCircuit,
                        reduction_bus_indices: Sequence[int]):
    """
    Relocate generators
    :param grid: MultiCircuit
    :param reduction_bus_indices: array of bus indices to reduce (external set)
    :return: None
    """
    G = nx.Graph()
    bus_idx_dict = grid.get_bus_index_dict()
    external_set = set(reduction_bus_indices)
    external_gen_set = set()
    external_gen_data = list()
    internal_set = set()

    # loop through the generators in the external set
    for k, elm in enumerate(grid.get_injection_devices_iter()):
        i = bus_idx_dict[elm.bus]
        if i in external_set:
            external_set.remove(i)
            external_gen_set.add(i)
            external_gen_data.append((k, i, elm, 'injection'))
            G.add_node(i)

    # loop through the branches
    for branch in grid.get_branches(add_vsc=False, add_hvdc=False, add_switch=True):
        f = bus_idx_dict[branch.bus_from]
        t = bus_idx_dict[branch.bus_to]
        if f in external_set or t in external_set:
            # the branch belongs to the external set
            pass
        else:
            # f nor t are in the external set: both belong to the internal set
            internal_set.add(f)
            internal_set.add(t)

        G.add_node(f)
        G.add_node(t)
        w = branch.get_weight()
        G.add_edge(f, t, weight=w)

    # convert to arrays and sort
    # external = np.sort(np.array(list(external_set)))
    # purely_internal_set = np.sort(np.array(list(purely_internal_set)))

    purely_internal_set = list(internal_set - external_gen_set)

    # now, for every generator, we need to find the shortest path in the "purely internal set"
    for elm_idx, bus_idx, elm, tpe in external_gen_data:
        # Compute shortest path lengths from this source
        lengths = nx.single_source_shortest_path_length(G, bus_idx)

        # Filter only target nodes
        target_distances = {t: lengths[t] for t in purely_internal_set if t in lengths}
        if target_distances:

            # Pick the closest
            closest = min(target_distances, key=target_distances.get)

            # relocate
            if tpe == 'injection':
                elm.bus = grid.buses[closest]


def get_reduction_sets(grid: MultiCircuit, reduction_bus_indices: Sequence[int],
                       add_vsc=False, add_hvdc=False, add_switch=True) -> Tuple[IntVec, IntVec, IntVec]:
    """
    Generate the set of bus indices for grid reduction
    :param grid: MultiCircuit
    :param reduction_bus_indices: array of bus indices to reduce (external set)
    :param add_vsc: Include the list of VSC?
    :param add_hvdc: Include the list of HvdcLine?
    :param add_switch: Include the list of Switch?
    :return: external, boundary, internal, boundary_branches
    """
    bus_idx_dict = grid.get_bus_index_dict()
    external_set = set(reduction_bus_indices)
    internal_set = set()
    internal_branches = list()

    for k, branch in enumerate(grid.get_branches(add_vsc=add_vsc, add_hvdc=add_hvdc, add_switch=add_switch)):
        f = bus_idx_dict[branch.bus_from]
        t = bus_idx_dict[branch.bus_to]
        if f in external_set:
            if t in external_set:
                # the branch belongs to the external set
                pass
            else:
                # the branch is a boundary link and t is a frontier bus
                pass
        else:
            # we know f is not external...

            if t in external_set:
                # f is not in the external set, but t is: the branch is a boundary link and f is a frontier bus
                pass
            else:
                # f nor t are in the external set: both belong to the internal set
                internal_set.add(f)
                internal_set.add(t)
                internal_branches.append(k)

    # convert to arrays and sort
    external = np.sort(np.array(list(external_set)))
    internal = np.sort(np.array(list(internal_set)))
    internal_branches = np.array(internal_branches)

    return external, internal, internal_branches


def ptdf_reduction(grid: MultiCircuit,
                   reduction_bus_indices: IntVec,
                   tol=1e-8) -> Tuple[MultiCircuit, Logger]:
    """
    In-place Grid reduction using the PTDF injection mirroring
    This is the same concept as the Di-Shi reduction but using the PTDF matrix instead.
    :param grid: MultiCircuit
    :param reduction_bus_indices: Bus indices of the buses to delete
    :param tol: Tolerance, any equivalent power value under this is omitted
    """
    logger = Logger()

    # find the boundary set: buses from the internal set the join to the external set
    e_buses, i_buses, i_branches = get_reduction_sets(grid=grid, reduction_bus_indices=reduction_bus_indices)

    if len(e_buses) == 0:
        logger.add_info(msg="Nothing to reduce")
        return grid, logger

    if len(i_buses) == 0:
        logger.add_info(msg="Nothing to keep (null grid as a result)")
        return grid, logger

    nc = compile_numerical_circuit_at(circuit=grid, t_idx=None)
    lin = LinearAnalysis(nc=nc)

    # base flows
    Pbus0 = grid.get_Pbus()

    # flows
    Flows0 = lin.PTDF @ Pbus0

    if grid.has_time_series:
        lin_ts = LinearAnalysisTs(grid=grid)
        Pbus0_ts = grid.get_Pbus_prof()
        Flows0_ts = lin_ts.get_flows_ts(P=Pbus0_ts)
    else:
        Flows0_ts = None

    # move the external injection to the boundary like in the Di-Shi method
    relocate_injections(grid=grid, reduction_bus_indices=reduction_bus_indices)

    # Eliminate the external buses
    to_be_deleted = [grid.buses[e] for e in e_buses]
    for bus in to_be_deleted:
        grid.delete_bus(obj=bus, delete_associated=True)

    # Injections that remain
    Pbus2 = grid.get_Pbus()

    # re-make the linear analysis
    nc2 = compile_numerical_circuit_at(grid)
    lin2 = LinearAnalysis(nc2)

    # reconstruct injections that should be to keep the flows the same
    Pbus3, _, _, _ = np.linalg.lstsq(lin2.PTDF, Flows0[i_branches])
    dPbus = Pbus2 - Pbus3

    if grid.has_time_series:
        lin_ts2 = LinearAnalysisTs(grid=grid)
        Pbus3_ts = lin_ts2.get_injections_ts(flows_ts=Flows0_ts[:, i_branches])
        Pbus2_ts = grid.get_Pbus_prof()
        dPbus_ts = Pbus2_ts - Pbus3_ts
    else:
        dPbus_ts = None

    n2 = grid.get_bus_number()
    for i in range(n2):
        bus = grid.buses[i]
        if abs(dPbus[i]) > tol:
            elm = Load(name=f"compensated load {i}", P=dPbus[i])

            if dPbus_ts is not None:
                elm.P_prof = dPbus_ts[:, i]

            grid.add_load(bus=bus, api_obj=elm)

    # proof that the flows are actually the same
    # Pbus4 = grid.get_Pbus()
    # Flows4 = lin2.PTDF @ Pbus4
    # diff = Flows0[i_branches] - Flows4

    return grid, logger


# if __name__ == "__main__":
    import VeraGridEngine as vg

    # circuit = vg.open_file("/home/santi/Documentos/Git/eRoots/VeraGrid/src/trunk/equivalents/completo.veragrid")
    #
    # ptdf_reduction(
    #     grid=circuit,
    #     reduction_bus_indices=[4],
    #     tol=1e-8
    # )
