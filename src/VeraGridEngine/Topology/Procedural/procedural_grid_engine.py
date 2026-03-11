# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Dict, List, TYPE_CHECKING

import numpy as np
import VeraGridEngine.Devices as dev
from VeraGridEngine import Substation
from VeraGridEngine.Devices.types import BRANCH_TYPES
from VeraGridEngine.enumerations import DeviceType, ProceduralGridMethods
from VeraGridEngine.basic_structures import Mat
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.special import gammaincinv

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit

class ProceduralGridComputationEngine:
    """
    Core engine for procedural grid expansion calculations.
    """

    def __init__(
        self,
        method: ProceduralGridMethods,
        targets: List[Substation],
        candidates: List[Substation]
    ):
        self.method = method
        self.targets = targets
        self.candidates = candidates

    def run_steiner_alone(self):
        """
        Executes the Steiner Tree algorithm without further optimization.
        """
        print("Running Steiner Tree calculation")
        # Add your Steiner Tree logic here
        # 1. Fetch coordinates
        M = len(self.candidates)
        N = len(self.targets)

        coord_M = np.array([[sg.lat, sg.lon] for sg in self.candidates])
        coord_N = np.array([[sg.lat, sg.lon] for sg in self.targets])
        # TODO: Get the voltages you inputed in the substations.
        #  The idea is to get the electrical element form the graphic element and then use get_substaiton_buses()
        # print(MultiCircuit.get_substation_buses(self.candidate_list[0].api_object))
        Vnom_kV_M = None
        Vnom_kV_N = None

        load_MW_M = None
        load_MW_N = None

        # 2A. Run VSA: Create an initial radial topology with a Steiner tree approach
        network = Graph(coord_M, coord_N, max_iteration=15000)
        raw_vector, history = network.run_vsa()
        raw_steiner_pts = network.decode_solution(raw_vector)

        # 2B. Prune redundant nodes
        final_steiner_pts = network.prune_redundant_nodes(raw_steiner_pts)

        # 2C. Get edges of the final network
        coords_final_network = np.vstack((network.all_coords, final_steiner_pts))
        _, final_mst = network.get_mst_cost(coords_final_network)
        edges = network.generate_edges(final_mst)

        # 2E. Assign voltages to Steiner Points
        closest_voltage = []
        for i in range(len(final_steiner_pts)):
            steiner_coord = final_steiner_pts[i]
            dists_to_M = np.linalg.norm(coord_M - steiner_coord, axis=1)
            dists_to_N = np.linalg.norm(coord_N - steiner_coord, axis=1)
            min_dist_M = np.min(dists_to_M)
            min_dist_N = np.min(dists_to_N)
            if min_dist_M < min_dist_N:
                closest_bus_idx = np.argmin(dists_to_M)
                closest_voltage.append(Vnom_kV_M[closest_bus_idx])
            else:
                closest_bus_idx = np.argmin(dists_to_N)
                closest_voltage.append(Vnom_kV_N[closest_bus_idx])

        node_objects = []
        for i in range(len(coords_final_network)):
            if 0 <= i <= M - 1:
                tpe = 0
                id_number = i
                x, y = coords_final_network[i]
                voltage = Vnom_kV_M[i]
                load = load_MW_M[i]

            elif M <= i <= M + N - 1:
                tpe  = 1
                id_number = i - M
                x, y = coords_final_network[i]
                voltage = Vnom_kV_N[i - M]
                load = load_MW_N[i - M]

            else:
                # For now, each Steiner Point will have the voltage of the closest M or N bus
                tpe = 2
                id_number = i - (M + N) + 1
                x, y = coords_final_network[i]
                voltage = closest_voltage[i - (M + N)]
                load = None

            node_objects.append(Node(tpe, id_number, x, y, load, voltage))

        edge_objects = []
        for edge in edges:
            edge_objects.append(Edge(node_objects[edge[0]],node_objects[edge[1]]))

        topology = Topology(network, node_objects, edge_objects)

        # 3. Convert to VeraGrid object
        grid = Grid(topology)

        # 4. Display in the diagram
        # TODO: Display in the diagram

        return None

    def run_optimization(self):
        """
        Executes the Steiner Tree algorithm followed by an optimization pass.
        """
        print("Running Steiner Tree plus Optimization")
        # Add your Steiner Tree plus Optimization logic here
        # TODO: Implement steiner tree + optimization

        return None

class Graph:
    """
    Class to create the Graph
    A graph is a set of nodes and edges
    """
    def __init__(self, m_coords, n_coords, max_iteration=1500):
        # to do: Add all hardcoded values to constructor
        self.m_coords = np.array(m_coords)
        self.n_coords = np.array(n_coords)
        self.max_iteration = max_iteration
        self.all_coords = np.vstack([self.m_coords, self.n_coords])
        self.total_nodes = len(self.all_coords)
        self.visited = [False] * self.total_nodes
        self.edges = []

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

        plt.scatter(self.n_coords[:, 0], self.n_coords[:, 1], c='blue', s=100, marker='s', label='Network Extension Points',
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

class Topology(Graph):
    """
    Class to create the Topology
    A Topology is a set of nodes, edges, buses and connections.
    """
    def __init__(self, m_coords, n_coords, max_iteration=1500, Nodes: List[Node], Edges: List[Edge]):
        super().__init__(m_coords, n_coords, max_iteration)
        # Additional attributes for Topology can be added here
        self.Nodes = Nodes
        self.Edges = Edges

    def generate_2D_markov(self):

        for edge in self.edges:
            bus_from = edge[0]
            bus_to = edge[1]
        combination, lengths, coords = generate_1D_markov(input_bus=label_bus1,
                                                          output_bus=label_bus2,
                                                          coord_input=coord_bus1,
                                                          coord_output=coord_bus2,
                                                          n_combinations=1,
                                                          seed=26)

class Grid(Topology):
    """
    Class to create the Grid
    A grid contains the data to create a VeraGrid object modeling the grid
    """

    def __init__(self, m_coords, n_coords, max_iteration=1500):
        super().__init__(m_coords, n_coords, max_iteration)
        # Additional attributes for Grid can be added here

class Node:

    def __init__(self, tpe: int, id_number: int, x: float, y: float, load: float, voltage: int):
        self.tpe = tpe # 0 for M, 1 for N, 2 for Steiner Point
        self.id_number = id_number
        self.x = x
        self.y = y
        self.load = load
        self.voltage = voltage

    #def add_node(self, candidate: int):
    #    self.candidates.append(candidate)

class Edge:

    def __init__(self, start_node: Node, end_node: Node):
        self.start_node = start_node
        self.end_node = end_node

class Bus:

    def __init__(self, id_number: int, x: float, y: float, load: float, voltage: int):
        self.id_number = id_number
        self.x = x
        self.y = y
        self.voltage = voltage

    #def add_bus(self, candidate: CandidateDevice):
    #    self.candidates.append(candidate)

class Connection:

    def __init__(self, bus_from: Bus, bus_to: Bus, tpe: int, catalogue_entry: str, length: float):
        self.bus_from = bus_from
        self.bus_to = bus_to
        self.tpe = tpe  # 0 for cable, 1 for transformer
        self.catalogue_entry = catalogue_entry
        self.length = length

    #def add_connection(self, candidate: CandidateDevice):
    #    self.candidates.append(candidate)

    #def add_template(self, candidate: CandidateDevice):
    #    self.candidates.append(candidate)

if __name__ == '__main__':

    pass
