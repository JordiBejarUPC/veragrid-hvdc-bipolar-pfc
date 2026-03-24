# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Dict, List, TYPE_CHECKING

import numpy as np
import VeraGridEngine.Devices as dev
from VeraGridEngine.enumerations import DeviceType, ProceduralGridMethods
from VeraGridEngine.basic_structures import Mat, Vec
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.special import gammaincinv
import random
import pandas as pd

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit


class TransitionMatrix:

    def __init__(self, grid: MultiCircuit):

        # Find out my unique voltages
        voltages = set()
        for branch in grid.get_branches(add_vsc=True, add_hvdc=True, add_switch=True):
            V1 = branch.bus_from.Vnom
            V2 = branch.bus_to.Vnom
            voltages.add(V1)
            voltages.add(V2)

        self.voltages_sorted = sorted(voltages)
        self.voltages_dict = {v: i for i, v in enumerate(self.voltages_sorted)}
        self.transition_matrix = np.zeros((len(self.voltages_sorted), len(self.voltages_sorted)))
        for branch in grid.get_branches(add_vsc=True, add_hvdc=True, add_switch=True):
            V1 = branch.bus_from.Vnom
            V2 = branch.bus_to.Vnom
            i1 = self.voltages_dict[V1]
            i2 = self.voltages_dict[V2]

            self.transition_matrix[i1, i2] += 1.0
            self.transition_matrix[i2, i1] += 1.0

        # normalize
        for i in range(self.transition_matrix.shape[0]):
            self.transition_matrix[i, :] /= self.transition_matrix[i, :].sum()

    def at(self, V1: float, V2: float):
        """
        Get probability associated to V1, transitioning to V2
        :param V1: Voltage Source
        :param V2: Voltage target
        :return: Probability of transition
        """
        i1 = self.voltages_dict[V1]
        i2 = self.voltages_dict[V2]
        return self.transition_matrix[i1, i2]

    def get_most_likely_transition_voltage(self, V: float):
        """
        Get the most likely voltage to transition to, given a voltage
        :param V: Some voltage source
        :return: The most likely voltage target
        """
        i1 = self.voltages_dict[V]
        i2 = np.argmax(self.transition_matrix[i1, :])
        return self.voltages_sorted[i2]


class ProceduralGridComputationEngine:
    """
    Core engine for procedural grid expansion calculations.
    """

    def __init__(self,
                 grid: MultiCircuit,
                 method: ProceduralGridMethods,
                 targets: List[dev.Substation],
                 candidates: List[dev.Substation]):
        """

        :param grid: MultiCircuit instance
        :param method: Method to use
        :param targets: List of substations to connect
        :param candidates: List of Substation that we may want to connect
        """
        self.grid = grid
        self.method = method
        self.targets_substations = targets
        self.candidates_substations = candidates

        self.target_buses: List[dev.Bus] = list()
        self.candidate_buses: List[dev.Bus] = list()
        self.steiner_buses: List[dev.Bus] = list()  # this is a result

        for sg in self.candidates_substations:
            for i, bus in enumerate(self.grid.get_substation_buses(sg)):
                bus.name = f"Candidate_{i}"
                bus.Vm_cost = bus.Vnom * 1000
                self.candidate_buses += bus

        for sg in self.targets_substations:
            for i, bus in enumerate(self.grid.get_substation_buses(sg)):
                bus.name = f"Target_{i}"
                bus.Vm_cost = bus.Vnom * 1000
                self.targets_substations += bus

        # TRANSITION_MATRIX = {
        #     132: {132: 0.7, 220: 0.15, 380: 0.15, 500: 0},
        #     220: {132: 0.15, 220: 0.7, 380: 0.1, 500: 0.05},
        #     380: {132: 0.15, 220: 0.1, 380: 0.7, 500: 0.05},
        #     500: {132: 0, 220: 0.15, 380: 0.15, 500: 0.7}
        # }

        self.transition_matrix = TransitionMatrix(grid)

    def run_steiner_alone(self):
        """
        Executes the Steiner Tree algorithm without further optimization.
        """

        # 2A. Run VSA: Create an initial radial topology with a Steiner tree approach
        network = ProceduralGridGraph(target_buses=self.target_buses,
                                      candidate_buses=self.candidate_buses,
                                      max_iterations=15000)

        initial_steiner_points, history = network.run_vsa()

        # 2B. Prune redundant nodes
        final_steiner_pts = network.prune_redundant_nodes(initial_steiner_points)

        # 2C. Get edges of the final network
        coords_final_network = np.r_[network.base_coords, final_steiner_pts]
        dist_matrix = cdist(coords_final_network, coords_final_network, metric='euclidean')
        final_mst = minimum_spanning_tree(dist_matrix).toarray()

        # generate edges
        rows, cols = np.where(final_mst > 0)
        edges = list(zip(rows, cols))

        # 2E. Assign voltages to Steiner Points
        closest_voltage = np.zeros(final_steiner_pts.shape[0])
        for i in range(final_steiner_pts.shape[0]):
            distances = np.linalg.norm(network.base_coords - final_steiner_pts[i, :], axis=1)
            closest = np.argmin(distances)
            closest_voltage[i] = network.base_voltages[closest]

        # 2F. Create Node buses (M, N, S)
        for i in range(final_steiner_pts.shape[0]):
            self.steiner_buses.append(
                dev.Bus(
                    name=f"Intermediate_{i}",
                    longitude=final_steiner_pts[i, 0],
                    latitude=final_steiner_pts[i, 1]
                )
            )

        all_buses = self.candidate_buses + self.target_buses + self.steiner_buses

        # 3. Create Topology from Graph

        # TRANSITION_MATRIX = {
        #     132: {132: 0.7, 220: 0.15, 380: 0.15, 500: 0},
        #     220: {132: 0.15, 220: 0.7, 380: 0.1, 500: 0.05},
        #     380: {132: 0.15, 220: 0.1, 380: 0.7, 500: 0.05},
        #     500: {132: 0, 220: 0.15, 380: 0.15, 500: 0.7}
        # }

        # TODO: Topology should accept:
        #  - edges
        #  - all_buses
        #  - grid  -> the catalogue comes here
        #  - TransitionMatrix
        #  - other numerical paramters like discretization

        topology = Topology(edges,
                            all_buses,
                            self.grid,
                            transition_matrix=self.transition_matrix,
                            discretization=25.0)

        topology.generate_markov()
        topology.add_loads()

        # 4. Display in the diagram
        # TODO: Display in the diagram section of the GUI

        return None

    def run_optimization(self):
        """
        Executes the Steiner Tree algorithm followed by an optimization pass.
        """
        print("Running Steiner Tree plus Optimization")
        # Add your Steiner Tree plus Optimization logic here

        return None


class ProceduralGridGraphLegacy:
    """
    Handles the mathematical matrix operations and optimization.
    """

    def __init__(self,
                 m_coords: np.array,
                 n_coords: np.array,
                 vnom_M: np.array,
                 vnom_N: np.array,
                 load_M: np.array,
                 load_N: np.array,
                 max_iteration: int = 1500):

        self.m_coords = m_coords
        self.n_coords = n_coords
        self.vnom_M = vnom_M
        self.vnom_N = vnom_N
        self.load_M = load_M
        self.load_N = load_N
        self.max_iteration = max_iteration

        self.all_coords = np.vstack([self.m_coords, self.n_coords])
        self.total_nodes = len(self.all_coords)
        self.visited = [False] * self.total_nodes
        self.edges = []
        self.m = len(self.m_coords)
        self.n = len(self.n_coords)
        self.n_fixed = len(self.all_coords)
        self.n_steiner = self.n_fixed - 2

        # We put 5 km as a margin
        min_all = np.min(self.all_coords)
        max_all = np.max(self.all_coords)
        self.bounds = np.array([min_all - 5.0, max_all + 5.0])

    def decode_solution(self, solution_vector):
        """Converts 1D VSA vector into 2D coordinates."""
        split_idx = len(solution_vector) // 2
        return np.column_stack((solution_vector[:split_idx], solution_vector[split_idx:]))

    def get_mst_cost(self, points):
        """Calculates MST cost for a set of 2D points."""
        if len(points) < 2:
            return 0, None
        dist_matrix = cdist(points, points, metric='euclidean')
        mst_matrix = minimum_spanning_tree(dist_matrix)
        return np.sum(mst_matrix.toarray()), mst_matrix

    def calculate_fitness(self, solution_vector):
        """VSA Fitness: MST Length + Degree Penalty."""
        steiner_points = self.decode_solution(solution_vector)
        all_nodes = np.vstack((self.all_coords, steiner_points))

        # MST Calculation
        dist_matrix = cdist(all_nodes, all_nodes)
        mst_matrix = minimum_spanning_tree(dist_matrix)
        mst_array = mst_matrix.toarray()

        total_length = np.sum(mst_array)

        # Penalty for Degree > 3 (Geometrically impossible for optimal ST)
        adj = mst_array + mst_array.T
        degrees = np.count_nonzero(adj, axis=1)
        steiner_degrees = degrees[self.n_fixed:]

        penalty = 0
        for d in steiner_degrees:
            if d > 3: penalty += 10000

        return total_length + penalty

    def prune_redundant_nodes(self, steiner_pts):
        """
        Iteratively removes Steiner points with Degree <= 2.
        """
        current_steiner = steiner_pts.copy()

        while True:
            if len(current_steiner) == 0: break

            # 1. Build MST with current set
            all_nodes = np.vstack((self.all_coords, current_steiner))
            cost, mst_matrix = self.get_mst_cost(all_nodes)
            mst_array = mst_matrix.toarray()

            # 2. Check degrees
            adj = mst_array + mst_array.T
            degrees = np.count_nonzero(adj, axis=1)

            # Extract Steiner degrees (indices after fixed nodes)
            st_degrees = degrees[self.n_fixed:]

            # 3. Identify useful points (Degree >= 3)
            useful_indices = np.where(st_degrees > 2)[0]

            # If no nodes are redundant, stop pruning
            if len(useful_indices) == len(current_steiner):
                break

            print(f"Pruning... Removed {len(current_steiner) - len(useful_indices)} nodes.\n")
            current_steiner = current_steiner[useful_indices]

        return current_steiner

    def run_vsa(self):
        dim = self.n_steiner * 2
        mu = np.random.uniform(self.bounds[0], self.bounds[1], dim)
        best_fitness = self.calculate_fitness(mu)
        best_solution = mu.copy()

        convergence_history = []

        radius_max = (self.bounds[1] - self.bounds[0]) / 2.0
        x_param = 0.1

        print("Running VSA...\n")
        for k in range(self.max_iteration):
            a_t = 1.0 - (k / self.max_iteration)
            a_t = max(a_t, 0.0001)
            r_t = radius_max * (1 / x_param) * gammaincinv(x_param, a_t)

            candidate = mu + r_t * np.random.randn(dim)
            candidate = np.clip(candidate, self.bounds[0], self.bounds[1])

            fitness = self.calculate_fitness(candidate)

            if fitness < best_fitness:
                best_fitness = fitness
                best_solution = candidate
                mu = candidate

            convergence_history.append(best_fitness)

        return best_solution, convergence_history

    def generate_edges(self, final_mst_):
        mst_array = final_mst_.toarray()
        rows, cols = np.where(mst_array > 0)
        connection_indices = list(zip(rows, cols))

        return connection_indices

    def plot_networks(self, history, raw_steiner_pts, final_steiner_pts):
        """
        Calculates final costs and plots both the Network Topology and VSA Convergence.
        """
        # --- Calculate Costs for Display ---
        # 1. Standard MST (No Steiner points)
        cost_standard, _ = self.get_mst_cost(self.all_coords)

        # 2. Raw VSA Result (Before Pruning)
        cost_raw, _ = self.get_mst_cost(np.vstack((self.all_coords, raw_steiner_pts)))

        # 3. Final Result (After Pruning) -> Need MST Matrix for plotting connections
        all_nodes = np.vstack((self.all_coords, final_steiner_pts))
        cost_pruned, final_mst = self.get_mst_cost(all_nodes)

        improvement = ((cost_standard - cost_pruned) / cost_standard) * 100

        # --- Plot 1: Network Topology ---
        plt.figure(figsize=(10, 8))
        plt.title(
            f"Optimized Steiner Tree (With Pruning)\n"
            f"Standard MST: {cost_standard:.2f} | Raw VSA: {cost_raw:.2f}\n"
            f"Pruned VSA: {cost_pruned:.2f} (Improvement: {improvement:.2f}%)"
        )

        # Draw Connections
        mst_array = final_mst.toarray()
        rows, cols = np.where(mst_array > 0)
        for r, c in zip(rows, cols):
            p1 = all_nodes[r]
            p2 = all_nodes[c]
            plt.plot([p1[0], p2[0]], [p1[1], p2[1]], 'k-', zorder=1, alpha=0.6)

        # Draw POIs and Network Extension Points
        plt.scatter(self.m_coords[:, 0], self.m_coords[:, 1], c='green', s=100, marker='s', label='POIs',
                    zorder=2)

        plt.scatter(self.n_coords[:, 0], self.n_coords[:, 1], c='blue', s=100, marker='s',
                    label='Network Extension Points',
                    zorder=2)

        # Draw Steiner Points
        for i, (x, y) in enumerate(final_steiner_pts):
            plt.scatter(x, y, c='grey', s=80, marker='o', label='Steiner Point' if i == 0 else "", zorder=3)
            plt.text(x, y + 3, f"Sp{i + 1}", fontsize=10, color='grey', ha='center')

        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.5)
        # Close the window 5 seconds after displaying
        plt.savefig("Topology.png")
        plt.pause(5)
        plt.close()

        # --- Plot 2: Cost vs. Iteration ---
        plt.figure(figsize=(10, 6))
        plt.plot(history, color='blue', linewidth=2)

        plt.title("VSA Convergence Analysis", fontsize=14)
        plt.xlabel("Iteration", fontsize=12)
        plt.ylabel("Best Cost (Network Length)", fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.6)
        # Close the window 5 seconds after displaying
        plt.savefig("VSA.png")
        plt.pause(5)
        plt.close()

    def assign_voltages_to_Steiner_Points(self, final_steiner_pts):

        closest_voltage = []
        for i in range(len(final_steiner_pts)):
            steiner_coord = final_steiner_pts[i]
            dists_to_M = np.linalg.norm(self.m_coords - steiner_coord, axis=1)
            dists_to_N = np.linalg.norm(self.n_coords - steiner_coord, axis=1)
            min_dist_M = np.min(dists_to_M)
            min_dist_N = np.min(dists_to_N)
            if min_dist_M < min_dist_N:
                closest_bus_idx = np.argmin(dists_to_M)
                closest_voltage.append(self.vnom_M[closest_bus_idx])
            else:
                closest_bus_idx = np.argmin(dists_to_N)
                closest_voltage.append(self.vnom_N[closest_bus_idx])

        return closest_voltage

    def create_node_objects(self, coords_final_network, closest_voltage):

        node_objects = []
        for i, (x, y) in enumerate(coords_final_network):
            if i < self.m:
                tpe = "M"
                id_number = i
                voltage = self.vnom_M[i]
                load = self.load_M[i]

            elif i < self.m + self.n:
                tpe = "N"
                id_number = i - self.m
                voltage = self.vnom_N[i - self.m]
                load = self.load_N[i - self.m]

            else:
                tpe = "S"  # S for Steiner Point
                id_number = i - (self.m + self.n) + 1
                voltage = closest_voltage[i - (self.m + self.n)]
                load = None

            node_objects.append(Node(tpe, id_number, x, y, load, voltage, is_DC=False))

        return node_objects

    def create_edge_objects(self, node_objects, final_edges):

        edge_objects = []
        for edge in final_edges:
            edge_objects.append(Edge(node_objects[edge[0]], node_objects[edge[1]]))

        return edge_objects


class Topology:
    """
    Represents the physical layout using domain objects.
    Contains a Graph instance via composition.
    """

    def __init__(self,
                 edges: list[tuple[int, int]],
                 all_buses: List[dev.Bus],
                 grid: MultiCircuit,
                 transition_matrix: TransitionMatrix,
                 discretization: float = 25.0):

        self.edges = edges
        self.all_buses = all_buses
        self.grid = grid
        self.transition_matrix = transition_matrix
        self.discretization = discretization  # km between buses

    def generate_markov(self):
        """
        Generates combinations that are valid by construction.
        """
        expansion_grid = MultiCircuit()

        for edge in self.edges:

            lengths = []
            bus_name_log = []  # np.array(len(self.nodes), dtype=str)

            input_bus = self.all_buses[edge[0]]
            output_bus = self.all_buses[edge[1]]

            coord_input = np.array([input_bus.longitude, input_bus.latitude])
            coord_output = np.array([output_bus.longitude, output_bus.latitude])
            distance = np.linalg.norm(coord_input - coord_output)

            if distance % self.discretization == 0:
                n_buses = int(distance // self.discretization + 1)
                n_slots = int(n_buses - 1)
                for i in range(n_slots):
                    lengths.append(self.discretization)
            else:
                n_buses = int(distance // self.discretization + 2)
                n_slots = int(n_buses - 1)
                for i in range(n_slots):
                    if i == n_slots - 1:
                        lengths.append(distance % self.discretization)
                    else:
                        lengths.append(self.discretization)

            accumulated_length = 0.0
            conn_counter = 0
            intermediate_bus_counter = 0

            # Add the first bus to the Multicircuit
            next_bus = input_bus

            if next_bus.name not in bus_name_log:
                expansion_grid.add_bus(obj=next_bus)
                # Add the bus in bus_name_log
                bus_name_log.append(next_bus.name)

            voltage_options = sorted(self.transition_matrix.get(input_bus.Vnom, {}).keys())

            while accumulated_length < distance:

                # Update next bus to current bus
                current_bus = next_bus

                # Check if we are at the last connection
                is_last_conn = (conn_counter == n_slots - 1)

                # Add next bus to Multicircuit
                if is_last_conn:
                    next_bus = output_bus

                    # If statement to discard transitions that are not allowed by the transition matrix
                    if self.transition_matrix[current_bus.Vnom].get(next_bus.Vnom) == 0:
                        print(
                            f"Added an intermediate bus to allow transition from {current_bus.Vnom}kV to {next_bus.Vnom}kV.")
                        # next_bus_volts = self.last_bus_fix(self.transition_matrix, current_bus_volt, next_bus_volt,
                        #                                    expansion_grid)
                        break
                    else:

                        if next_bus.name not in bus_name_log:
                            expansion_grid.add_bus(obj=next_bus)
                            # Add the bus in bus_name_log
                            bus_name_log.append(next_bus.name)

                else:
                    next_bus_options = sorted([b for b in voltage_options])
                    current_transitions = self.transition_matrix[current_bus.Vnom]
                    weights = []
                    for bus in next_bus_options:
                        # Default to 0 probability if a voltage is not in the matrix
                        weight = current_transitions.get(bus, 0.0)
                        weights.append(weight)

                    # random.choices returns a list, so get the first element [0]
                    next_bus.Vnom = random.choices(next_bus_options, weights=weights, k=1)[0]
                    next_bus.Vm_cost = next_bus.Vnom * 1000

                    expansion_grid.add_bus(obj=next_bus)

                    intermediate_bus_counter += 1

                # Add connection between current bus and next bus to Multicircuit
                conn_options = sorted(self.get_possible_connections(current_bus.Vnom, next_bus.Vnom, current_bus.is_dc,
                                                                    next_bus.is_dc))
                if not conn_options:
                    print(f"Combo failed due to lack of next connection options.")
                    break

                connection = random.choice(conn_options)

                if connection == "overhead AC line":
                    r = self.catalogue_data_fetcher(connection.identifier, 'R [Ohm/km AC@20°C]',
                                                    file_name=self.catalogue_path)
                    x = self.catalogue_data_fetcher(connection.identifier, 'X [Ohm/km]', file_name=self.catalogue_path)
                    b = self.catalogue_data_fetcher(connection.identifier, 'B [uS/km]', file_name=self.catalogue_path)
                    p_rated = self.catalogue_data_fetcher(connection.identifier, 'Rated Power [MW]',
                                                          file_name=self.catalogue_path)
                    capex = self.catalogue_data_fetcher(connection.identifier, 'Dummy Cost [EUR/km]',
                                                        file_name=self.catalogue_path)

                    line = dev.Line(
                        name=f"AC_Line_{current_bus.name}_{next_bus.name}",  # Added idx_1D to ensure uniqueness
                        bus_from=current_bus, bus_to=next_bus,
                        length=lengths[conn_counter], r=r, x=x, b=b, rate=p_rated,
                        capex=capex, opex=0, cost=100
                    )
                    expansion_grid.add_line(obj=line)

                    accumulated_length += lengths[conn_counter]
                    conn_counter += 1

                elif connection == "transformer":
                    hv_val = self.catalogue_data_fetcher(connection.identifier, 'HV (kV)',
                                                         file_name=self.catalogue_path)
                    lv_val = self.catalogue_data_fetcher(connection.identifier, 'LV (kV)',
                                                         file_name=self.catalogue_path)
                    pcu = self.catalogue_data_fetcher(connection.identifier, 'Copper losses (kW)',
                                                      file_name=self.catalogue_path)
                    pfe = self.catalogue_data_fetcher(connection.identifier, 'No load losses (kW)',
                                                      file_name=self.catalogue_path)
                    i0 = self.catalogue_data_fetcher(connection.identifier, 'No load current (%)',
                                                     file_name=self.catalogue_path)
                    vsc = self.catalogue_data_fetcher(connection.identifier, 'V short circuit (%)',
                                                      file_name=self.catalogue_path)
                    rate = self.catalogue_data_fetcher(connection.identifier, 'Rate (MVA)',
                                                       file_name=self.catalogue_path)
                    capex = self.catalogue_data_fetcher(connection.identifier, 'Dummy Cost [EUR]',
                                                        file_name=self.catalogue_path)

                    z_complex = dev.Devices.Branches.transformer_type.get_impedances(
                        VH_bus=max(hv_val, lv_val), VL_bus=min(hv_val, lv_val),
                        Sn=rate, HV=hv_val, LV=lv_val, Pcu=pcu, Pfe=pfe, I0=i0, Vsc=vsc,
                        Sbase=100, GR_hv1=0.5
                    )[0]

                    trafo = dev.Transformer2W(
                        name=f"TR_{current_bus.name}_{next_bus.name}",  # Added idx_1D to ensure uniqueness
                        bus_from=current_bus, bus_to=next_bus,
                        HV=max(hv_val, lv_val), LV=min(hv_val, lv_val),
                        r=np.real(z_complex), x=np.imag(z_complex),
                        rate=rate, capex=capex, opex=0, cost=5000
                    )
                    trafo.Pcu = pcu
                    trafo.Pfe = pfe
                    expansion_grid.add_transformer2w(obj=trafo)

            # TODO: Add the merge_lines function outside generate_markov and inside Topology
            # combination, length_elements_ = merge_lines(combination, length_elements_)

    def coord_calc(self, current_bus_lat: float, current_bus_lon: float, length: float, coord_out: np.array):
        """
        Calculate the coordinates of the next bus based on the current bus, the length to be covered, and the output coordinates.
        """
        line_angle = np.arctan2(coord_out[1] - current_bus_lon, coord_out[0] - current_bus_lat)
        delta_x = np.cos(line_angle) * length
        delta_y = np.sin(line_angle) * length
        new_coord = np.array([current_bus_lat + delta_x, current_bus_lon + delta_y])

        return new_coord

    def get_possible_connections(self, current_bus: float, next_bus: float, current_bus_is_DC: bool, next_bus_is_DC: bool):
        """
        Determines valid connections for a pair of buses, enforcing all rules.
        Only considers type A connections for A-slots and type B connections for B-slots.
        """
        current_bus = int(current_bus)
        next_bus = int(next_bus)

        if current_bus == next_bus:
            if not current_bus_is_DC and not next_bus_is_DC:
                return ["overhead AC line"]
            elif current_bus_is_DC and next_bus_is_DC:
                return ["DC cable"]
            else:
                return ["VSC"]
        else:
            if not current_bus_is_DC and not next_bus_is_DC:
                return ["transformer"]
            elif current_bus_is_DC != next_bus_is_DC:
                return ["VSC"]
            else:
                return []

    def catalogue_data_fetcher(self, identifier, parameter, file_name):
        """
        Fetches the specified parameter for a given identifier from the catalogue.
        """
        global _CATALOGUE_CACHE

        if file_name not in _CATALOGUE_CACHE:
            # print(f"Loading catalogue into memory: {file_name} ...")
            try:
                # Load all sheets
                all_sheets = pd.read_excel(file_name, sheet_name=None, engine='odf')

                file_lookup = {}
                for df in all_sheets.values():
                    if 'Name' in df.columns:
                        # 1. Drop rows without a name
                        df_clean = df.dropna(subset=['Name'])

                        # 2. CRITICAL FIX: Remove duplicates, keeping the first occurrence
                        # This prevents the "Index must be unique" error
                        df_clean = df_clean.drop_duplicates(subset=['Name'], keep='first')

                        # 3. Convert to dictionary
                        records = df_clean.set_index('Name').to_dict(orient='index')
                        file_lookup.update(records)

                _CATALOGUE_CACHE[file_name] = file_lookup

            except Exception as e:
                print(f"Critical Error loading catalogue: {e}")
                return None

        # Retrieve data
        file_data = _CATALOGUE_CACHE.get(file_name)
        if file_data is None: return None

        row_data = file_data.get(identifier)
        if row_data is None:
            # print(f"Error: Element '{element_name}' not found in catalogue.")
            return None

        val = row_data.get(parameter)
        if val is None: return None

        return float(val)

    def last_bus_fix(self, transition_matrix, current_bus_volt, next_bus_volt):
        pass

    def add_loads(self):
        'Function to add loads and generators to the VeraGrid grid object'
        pass


class Node:

    def __init__(self, tpe: str, id_number: int, x: float, y: float, load: float, voltage: int, is_DC: bool):
        self.tpe = tpe  # M, N, or S
        self.id_number = id_number
        self.x = x
        self.y = y
        self.load = load
        self.voltage = voltage
        self.is_DC = is_DC

    # def add_node(self, candidate: int):
    #    self.candidates.append(candidate)


class Edge:

    def __init__(self, start_node: Node, end_node: Node):
        self.start_node = start_node
        self.end_node = end_node


class ProceduralGridGraph:

    def __init__(self,
                 target_buses: List[dev.Bus],
                 candidate_buses: List[dev.Bus],
                 max_iterations: int = 1000, ):
        """

        :param target_buses:
        :param candidate_buses:
        :param max_iterations: Maximum number of iterations
        """
        self.target_buses: List[dev.Bus] = target_buses
        self.candidate_buses: List[dev.Bus] = candidate_buses
        self.max_iterations: int = max_iterations

        self.n_target = len(self.target_buses)
        self.n_candidate = len(self.candidate_buses)

        self.n_steiner = self.n_target + self.n_candidate - 2

        # 1. Parse inputs
        self.coord_candidate = np.zeros((self.n_candidate, 2))  # dim, (lon, lat)
        self.coord_target = np.zeros((self.n_target, 2))  # dim, (lon, lat)
        Vnom_kV_candidate = np.zeros(self.n_candidate)
        Vnom_kV_target = np.zeros(self.n_target)

        self.min_lon = np.inf
        self.min_lat = np.inf
        self.max_lon = 0
        self.max_lat = 0

        for i, bus in enumerate(self.target_buses):
            lon, lat = bus.try_to_find_coordinates()
            self.coord_target[i, 0] = lon
            self.coord_target[i, 1] = lat
            Vnom_kV_target[i] = bus.Vnom

            self.min_lon = min(self.min_lon, lon)
            self.min_lat = min(self.min_lat, lat)
            self.max_lon = max(self.max_lon, lon)
            self.max_lat = max(self.max_lat, lat)

        for i, bus in enumerate(self.candidate_buses):
            lon, lat = bus.try_to_find_coordinates()
            self.coord_candidate[i, 0] = lon
            self.coord_candidate[i, 1] = lat
            Vnom_kV_candidate[i] = bus.Vnom

            self.min_lon = min(self.min_lon, lon)
            self.min_lat = min(self.min_lat, lat)
            self.max_lon = max(self.max_lon, lon)
            self.max_lat = max(self.max_lat, lat)

        self.base_coords = np.r_[self.coord_candidate, self.coord_target]
        self.base_voltages = np.r_[Vnom_kV_candidate, Vnom_kV_target]

    def calculate_fitness(self, mu_lon: Vec, mu_lat: Vec):
        """
        VSA Fitness: MST Length + Degree Penalty.
        :param mu_lat: steiner points latitudes
        :param mu_lon: steiner points longitudes
        """
        steiner_coords = np.c_[mu_lon, mu_lat]
        all_coords = np.r_[self.base_coords, self.coord_target, steiner_coords]

        # MST Calculation
        dist_matrix = cdist(all_coords, all_coords)
        mst_matrix = minimum_spanning_tree(dist_matrix)
        mst_array = mst_matrix.toarray()

        total_length = np.sum(mst_array)

        # Penalty for Degree > 3 (Geometrically impossible for optimal ST)
        adj = mst_array + mst_array.T
        degrees = np.count_nonzero(adj, axis=1)
        steiner_degrees = degrees[self.n_target + self.n_candidate:]

        penalty = 0
        for d in steiner_degrees:
            if d > 3: penalty += 10000

        return total_length + penalty

    def run_vsa(self):
        """

        :return: best_solution (dim, (lat, lon))
        """
        dim = self.n_steiner * 2

        mu_lon = np.random.uniform(self.min_lon, self.max_lon, dim)
        mu_lat = np.random.uniform(self.min_lat, self.max_lat, dim)

        best_fitness = self.calculate_fitness(mu_lon=mu_lon, mu_lat=mu_lat)
        best_solution = np.c_[mu_lat, mu_lon]

        convergence_history = []

        radius_max = np.sqrt((self.max_lat - self.min_lat) ** 2 + (self.max_lon - self.min_lon) ** 2) / 2.0
        x_param = 0.1

        # print("Running VSA...\n")
        for k in range(self.max_iterations):
            a_t = 1.0 - (k / self.max_iterations)
            a_t = max(a_t, 0.0001)
            r_t = radius_max * (1 / x_param) * gammaincinv(x_param, a_t)

            candidate_lon = mu_lon + r_t * np.random.randn(dim)
            candidate_lat = mu_lat + r_t * np.random.randn(dim)

            candidate_lon = np.clip(candidate_lon, self.min_lon, self.max_lon)
            candidate_lat = np.clip(candidate_lat, self.min_lat, self.max_lat)

            fitness = self.calculate_fitness(mu_lon=candidate_lon, mu_lat=candidate_lat)

            if fitness < best_fitness:
                best_fitness = fitness
                best_solution = np.c_[candidate_lon, candidate_lat]

            convergence_history.append(best_fitness)

        return best_solution, convergence_history

    def prune_redundant_nodes(self, steiner_coords: Mat):
        """
        Iteratively removes Steiner points with Degree <= 2.
        :param steiner_coords: steiner points coordinates (dim, (lon, lat))
        """
        current_steiner = steiner_coords.copy()

        while True:
            if len(current_steiner) == 0:
                break

            # 1. Build MST with current set
            all_coords = np.r_[self.base_coords, self.coord_target, current_steiner]

            dist_matrix = cdist(all_coords, all_coords, metric='euclidean')
            mst_array = minimum_spanning_tree(dist_matrix).toarray()
            # cost = np.sum(mst_array)

            # 2. Check degrees
            adj = mst_array + mst_array.T
            degrees = np.count_nonzero(adj, axis=1)

            # Extract Steiner degrees (indices after fixed nodes)
            st_degrees = degrees[self.n_target + self.n_candidate:]

            # 3. Identify useful points (Degree >= 3)
            useful_indices = np.where(st_degrees > 2)[0]

            # If no nodes are redundant, stop pruning
            if len(useful_indices) == len(current_steiner):
                break

            print(f"Pruning... Removed {len(current_steiner) - len(useful_indices)} nodes.\n")
            current_steiner = current_steiner[useful_indices, :]

        return current_steiner
