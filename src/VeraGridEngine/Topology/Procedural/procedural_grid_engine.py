# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Dict, List, TYPE_CHECKING

import numpy as np
import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.types import BRANCH_TYPES
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.basic_structures import Mat
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.special import gammaincinv

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit

class InterNodeDevices:

    def __init__(self, bus_from: str, bus_to: str, tpe: str, subtpe: str,
                 catalogue_entry: str, length: float, x: float, y: float,
                 candidates: list):

        # For connections AND buses
        self.catalogue_entry = catalogue_entry
        self.length = length
        self.tpe = tpe # "connection" or "bus"

        # For connections
        self.bus_from = bus_from
        self.bus_to = bus_to
        self.subtpe = subtpe  # "cable" or "transformer"
        self.candidates = candidates

        # For buses
        self.x = x
        self.y = y

    def add_element(self, candidate: CandidateDevice):
        self.candidates.append(candidate)

    def add_template(self, candidate: CandidateDevice):
        self.candidates.append(candidate)


class Node:

    def __init__(self, name: str, load: float):
        self.name = name
        self.load = load

class Graph:
    """
    Class to create the Graph
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
    """

    def __init__(self, m_coords, n_coords, max_iteration=1500):
        super().__init__(m_coords, n_coords, max_iteration)
        # Additional attributes for Topology can be added here
        self.M = len(self.m_coords)
        self.N = len(self.n_coords)
        self.Node = Node
        self.InterNodeDevices = InterNodeDevices

    def generate_2D_markov(self):
        for edge in self.edges:  # edge is a tuple (i,j)
            if 0 <= edge[0] <= self.M - 1:
                label_bus1 = Vnom_kV_M[edge[0]]
                coord_bus1 = coords_final_network[edge[0]]
                name_bus1 = f"M_{edge[0]}"

            elif self.M <= edge[0] <= self.M + self.N - 1:
                label_bus1 = Vnom_kV_N[edge[0] - self.M]
                coord_bus1 = coords_final_network[edge[0]]
                name_bus1 = f"N_{edge[0] - self.M}"
            else:
                # For now, each Steiner Point will have the voltage of the closest M or N bus
                label_bus1 = closest_voltage[edge[0] - (self.M + self.N)]
                coord_bus1 = coords_final_network[edge[0]]
                name_bus1 = f"Sp_{edge[0] - (self.M + self.N) + 1}"

            if 0 <= edge[1] <= self.M - 1:
                label_bus2 = Vnom_kV_M[edge[1]]
                coord_bus2 = coords_final_network[edge[1]]
                name_bus2 = f"M_{edge[1]}"

            elif M <= edge[1] <= self.M + self.N - 1:
                label_bus2 = Vnom_kV_N[edge[1] - self.M]
                coord_bus2 = coords_final_network[edge[1]]
                name_bus2 = f"N_{edge[1] - self.M}"

            else:
                # For now, each Steiner Point will have the voltage of the closest M or N bus
                label_bus2 = closest_voltage[edge[1] - (self.M + self.N)]
                coord_bus2 = coords_final_network[edge[1]]
                name_bus2 = f"Sp_{edge[1] - (self.M + self.N) + 1}"

class Grid(Topology):
    """
    Class to create the Grid
    """

    def __init__(self, m_coords, n_coords, max_iteration=1500):
        super().__init__(m_coords, n_coords, max_iteration)
        # Additional attributes for Grid can be added here


if __name__ == '__main__':

    pass
