# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Dict, List, TYPE_CHECKING

import numpy as np
import VeraGridEngine.Devices as dev
from VeraGrid.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem
import VeraGridEngine as gce
from VeraGridEngine import Substation
from VeraGridEngine.Devices.types import BRANCH_TYPES
from VeraGridEngine.enumerations import DeviceType, ProceduralGridMethods
from VeraGridEngine.basic_structures import Mat
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.special import gammaincinv
import random
import pandas as pd


if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit

class ProceduralGridComputationEngine:
    """
    Core engine for procedural grid expansion calculations.
    """

    def __init__(
        self,
        grid: MultiCircuit,
        method: ProceduralGridMethods,
        targets: List[Substation],
        candidates: List[Substation]
    ):
        self.grid = grid
        self.method = method
        self.targets = targets
        self.candidates = candidates

    def run_steiner_alone(self):
        """
        Executes the Steiner Tree algorithm without further optimization.
        """
        print("Running Steiner Tree calculation")

        _CATALOGUE_CACHE = {} # needed for the catalogue_data_fectcher() function

        # 1. Parse inputs
        coord_M = np.array([[sg.latitude, sg.longitude] for sg in self.candidates])
        coord_N = np.array([[sg.latitude, sg.longitude] for sg in self.targets])

        Vnom_kV_M = []
        for sg in self.candidates:
            # TODO: Extract the voltage from each bus
            bus_list = self.grid.get_substation_buses(sg) # bus_list = self.grid.get_voltage_levels()
            # TODO: Check the assumption below
            Vnom_kV_M.append(bus_list[0])  # Assuming the first bus represents the substation voltage

        Vnom_kV_N = []
        for sg in self.targets:
            # TODO: Extract the voltage from each bus
            bus_list = self.grid.get_substation_buses(sg)
            # TODO: Check the assumption below
            Vnom_kV_N.append(bus_list[0])  # Assuming the first bus represents the substation voltage

        load_MW_M = None # TODO: How do we enter the generation and load capacities in the substations?
        load_MW_N = None # TODO: How do we enter the generation and load capacities in the substations?

        # 2A. Run VSA: Create an initial radial topology with a Steiner tree approach
        network = Graph(coord_M, coord_N, Vnom_kV_M, Vnom_kV_N, load_MW_M, load_MW_N, max_iteration=15000)
        raw_vector, history = network.run_vsa()
        raw_steiner_pts = network.decode_solution(raw_vector)

        # 2B. Prune redundant nodes
        final_steiner_pts = network.prune_redundant_nodes(raw_steiner_pts)

        # 2C. Get edges of the final network
        coords_final_network = np.vstack((network.all_coords, final_steiner_pts))
        _, final_mst = network.get_mst_cost(coords_final_network)
        edges = network.generate_edges(final_mst)

        # 2E. Assign voltages to Steiner Points
        closest_voltage = network.assign_voltages_to_Steiner_Points(final_steiner_pts)

        # 2F. Create Node and Edge objects
        node_objects = network.create_node_objects(coords_final_network, closest_voltage)
        edge_objects = network.create_edge_objects(node_objects, edges)

        # 3. Create Topology from Graph

        TRANSITION_MATRIX = {
        132: {132: 0.7,  220: 0.15, 380: 0.15, 500: 0},
        220: {132: 0.15, 220: 0.7,  380: 0.1,  500: 0.05},
        380: {132: 0.15, 220: 0.1,  380: 0.7,  500: 0.05},
        500: {132: 0,  220: 0.15, 380: 0.15, 500: 0.7}
        }

        topology = Topology(network,
                            node_objects,
                            edge_objects,
                            discretization=25.0,
                            transition_matrix=TRANSITION_MATRIX,
                            catalogue_path="path/to/catalogue.ods")

        # 4. Convert to VeraGrid object
        expansion_grid = Grid(topology)

        # 5. Display in the diagram
        # TODO: Display in the diagram section of the GUI

        return None

    def run_optimization(self):
        """
        Executes the Steiner Tree algorithm followed by an optimization pass.
        """
        print("Running Steiner Tree plus Optimization")
        # Add your Steiner Tree plus Optimization logic here

        return None

class Graph:
    """
    Handles the mathematical matrix operations and optimization.
    """
    def __init__(self, m_coords, n_coords, vnom_M, vnom_N, load_M, load_N, max_iteration=1500):
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
                tpe = "S" # S for Steiner Point
                id_number = i - (self.m + self.n) + 1
                voltage = closest_voltage[i - (self.m + self.n)]
                load = None

            node_objects.append(Node(tpe, id_number, x, y, load, voltage, is_DC=False))

        return node_objects

    def create_edge_objects(self, node_objects, final_edges):

        edge_objects = []
        for edge in final_edges:
            edge_objects.append(Edge(node_objects[edge[0]],node_objects[edge[1]]))

        return edge_objects


class Topology:
    """
    Represents the physical layout using domain objects.
    Contains a Graph instance via composition.
    """

    def __init__(self,
                 network_graph: Graph,
                 nodes: List[Node],
                 edges: List[Edge],
                 discretization: float = 25.0,
                 transition_matrix: Dict[int, Dict[int, float]] = None,
                 catalogue_path: str = "path/to/catalogue.ods"):
        self.network_graph = network_graph
        self.nodes = nodes # creo que no hace falta importar esto ya que edges incluye la misma info
        self.edges = edges
        self.discretization = discretization  # km between buses
        self.transition_matrix = transition_matrix
        self.catalogue_path = catalogue_path

    def generate_markov(self):
        """
        Generates combinations that are valid by construction.
        """
        expansion_grid = gce.MultiCircuit()

        for edge in self.edges:

            lengths = []
            bus_name_log = [] # np.array(len(self.nodes), dtype=str)

            input_node = edge.start_node
            output_node = edge.end_node

            coord_input = np.array([input_node.x, input_node.y])
            coord_output = np.array([output_node.x, output_node.y])
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
            next_bus_volt = input_node.voltage
            next_bus_lat = input_node.x
            next_bus_lon = input_node.y
            next_bus_tpe = input_node.tpe
            next_bus_id_number = input_node.id_number
            next_bus_is_DC = input_node.is_DC
            next_bus = gce.Bus(
                name=f"{next_bus_tpe}{next_bus_id_number}",
                Vnom=next_bus_volt,
                is_dc=next_bus_is_DC,
                vmin=0.9, vmax=1.1,
                angle_min=-6.28, angle_max=6.28,
                latitude=next_bus_lat, longitude=next_bus_lon,
            )
            next_bus.Vm_cost = next_bus_volt * 1000

            if next_bus.name not in bus_name_log:
                expansion_grid.add_bus(obj=next_bus)
                # Add the bus in bus_name_log
                bus_name_log.append(next_bus.name)

            voltage_options = sorted(self.transition_matrix.get(input_node.voltage, {}).keys())

            while accumulated_length < distance:

                # Update next bus to current bus
                current_bus = next_bus
                current_bus_volt = next_bus_volt
                current_bus_lat = next_bus_lat
                current_bus_lon = next_bus_lon
                current_bus_is_DC = next_bus_is_DC

                # Check if we are at the last connection
                is_last_conn = (conn_counter == n_slots - 1)

                # Add next bus to Multicircuit
                if is_last_conn:
                    next_bus_volt = output_node.voltage

                    # If statement to discard transitions that are not allowed by the transition matrix
                    if self.transition_matrix[current_bus_volt].get(next_bus_volt) == 0:
                        print(f"Added an intermediate bus to allow transition from {current_bus_volt}kV to {next_bus_volt}kV.")
                        # TODO: Find out a way to solve this case
                    else:
                        next_bus = gce.Bus(
                            name=f"{output_node.tpe}{output_node.id_number}",
                            Vnom=next_bus_volt,
                            is_dc=output_node.is_DC,
                            vmin=0.9, vmax=1.1,
                            angle_min=-6.28, angle_max=6.28,
                            latitude=output_node.x, longitude=output_node.y,
                        )
                        next_bus.Vm_cost = next_bus_volt * 1000

                        if next_bus.name not in bus_name_log:
                            expansion_grid.add_bus(obj=next_bus)
                            # Add the bus in bus_name_log
                            bus_name_log.append(next_bus.name)

                else:
                    next_bus_options = sorted([b for b in voltage_options])
                    current_transitions =  self.transition_matrix[current_bus_volt]
                    weights = []
                    for bus in next_bus_options:
                        # Default to 0 probability if a voltage is not in the matrix
                        weight = current_transitions.get(bus,0.0)
                        weights.append(weight)

                    # random.choices returns a list, so get the first element [0]
                    next_bus_volt = random.choices(next_bus_options, weights=weights, k=1)[0]
                    next_bus = gce.Bus(
                        name=f"intermediate{intermediate_bus_counter}",
                        Vnom=next_bus_volt,
                        is_dc=current_bus_is_DC, # for now we keep it like this, since everything is AC
                        vmin=0.9, vmax=1.1,
                        angle_min=-6.28, angle_max=6.28,
                        latitude=self.coord_calc(current_bus_lat, current_bus_lon, lengths[conn_counter], coord_output)[0],
                        longitude=self.coord_calc(current_bus_lat,current_bus_lon,lengths[conn_counter],coord_output)[1]
                    )
                    next_bus.Vm_cost = next_bus_volt * 1000

                    expansion_grid.add_bus(obj=next_bus)

                    intermediate_bus_counter += 1

                # Add connection between current bus and next bus to Multicircuit
                conn_options = sorted(self.get_possible_connections(current_bus_volt, next_bus_volt, current_bus_is_DC, current_bus_is_DC))
                if not conn_options:
                    valid_combo = False
                    print(f"Combo failed due to lack of next connection options.")
                    break

                connection = random.choice(conn_options)

                # TODO: let the user choose the catalogue it wants using the "File" > "Import catalogue" from the GUI

                if connection.conn_type == "overhead AC line":
                    r = self.catalogue_data_fetcher(connection.identifier, 'R [Ohm/km AC@20°C]', file_name=self.catalogue_path)
                    x = self.catalogue_data_fetcher(connection.identifier, 'X [Ohm/km]', file_name=self.catalogue_path)
                    b = self.catalogue_data_fetcher(connection.identifier, 'B [uS/km]', file_name=self.catalogue_path)
                    p_rated = self.catalogue_data_fetcher(connection.identifier, 'Rated Power [MW]', file_name=self.catalogue_path)
                    capex = self.catalogue_data_fetcher(connection.identifier, 'Dummy Cost [EUR/km]', file_name=self.catalogue_path)

                    line = gce.Line(
                        name=f"AC_Line_{current_bus.name}_{next_bus.name}",  # Added idx_1D to ensure uniqueness
                        bus_from=current_bus, bus_to=next_bus,
                        length=lengths[conn_counter], r=r, x=x, b=b, rate=p_rated,
                        capex=capex, opex=0, cost=100
                    )
                    expansion_grid.add_line(obj=line)

                    accumulated_length += lengths[conn_counter]
                    conn_counter += 1

                elif connection.conn_type == "transformer":
                    hv_val = self.catalogue_data_fetcher(connection.identifier, 'HV (kV)', file_name=self.catalogue_path)
                    lv_val = self.catalogue_data_fetcher(connection.identifier, 'LV (kV)', file_name=self.catalogue_path)
                    pcu = self.catalogue_data_fetcher(connection.identifier, 'Copper losses (kW)', file_name=self.catalogue_path)
                    pfe = self.catalogue_data_fetcher(connection.identifier, 'No load losses (kW)', file_name=self.catalogue_path)
                    i0 = self.catalogue_data_fetcher(connection.identifier, 'No load current (%)', file_name=self.catalogue_path)
                    vsc = self.catalogue_data_fetcher(connection.identifier, 'V short circuit (%)', file_name=self.catalogue_path)
                    rate = self.catalogue_data_fetcher(connection.identifier, 'Rate (MVA)', file_name=self.catalogue_path)
                    capex = self.catalogue_data_fetcher(connection.identifier, 'Dummy Cost [EUR]', file_name=self.catalogue_path)

                    z_complex = gce.Devices.Branches.transformer_type.get_impedances(
                        VH_bus=max(hv_val, lv_val), VL_bus=min(hv_val, lv_val),
                        Sn=rate, HV=hv_val, LV=lv_val, Pcu=pcu, Pfe=pfe, I0=i0, Vsc=vsc,
                        Sbase=100, GR_hv1=0.5
                    )[0]

                    trafo = gce.Transformer2W(
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

    def coord_calc(self, current_bus_lat: float,current_bus_lon: float, length:float , coord_out: np.array):
        """
        Calculate the coordinates of the next bus based on the current bus, the length to be covered, and the output coordinates.
        """
        line_angle = np.arctan2(coord_out[1] - current_bus_lon, coord_out[0] - current_bus_lat)
        delta_x = np.cos(line_angle) * length
        delta_y = np.sin(line_angle) * length
        new_coord = np.array([current_bus_lat + delta_x, current_bus_lon + delta_y])

        return new_coord

    def get_possible_connections(self, current_bus: int, next_bus: int, current_bus_is_DC: bool, next_bus_is_DC: bool):
        """
        Determines valid connections for a pair of buses, enforcing all rules.
        Only considers type A connections for A-slots and type B connections for B-slots.
        """

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

class Grid:
    """
    Contains the data to create a VeraGrid object modeling the grid.
    Contains a Topology instance via composition.
    """
    def __init__(self, topology: Topology):
        self.topology = topology
        # Additional attributes for Grid can be added here

class Node:

    def __init__(self, tpe: str, id_number: int, x: float, y: float, load: float, voltage: int, is_DC: bool):
        self.tpe = tpe # M, N, or S
        self.id_number = id_number
        self.x = x
        self.y = y
        self.load = load
        self.voltage = voltage
        self.is_DC = is_DC

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

class Connection:

    def __init__(self, bus_from: Bus, bus_to: Bus, tpe: str, catalogue_entry: str, length: float):
        self.bus_from = bus_from
        self.bus_to = bus_to
        self.tpe = tpe  # "overhead AC line", "transformer", "VSC", etc.
        self.catalogue_entry = catalogue_entry
        self.length = length


if __name__ == '__main__':

    pass
