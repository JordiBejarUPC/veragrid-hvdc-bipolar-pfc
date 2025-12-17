from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Callable
import random
import math
import copy
import matplotlib.pyplot as plt


# ======================================================================
#  DATA MODEL
# ======================================================================
@dataclass
class LineType:
    id: str
    capacity_mva: float
    r: float
    x: float
    cost_per_km: float


@dataclass
class TransformerType:
    id: str
    rating_mva: float
    r: float
    x: float
    cost: float


@dataclass
class Demand:
    id: str
    p_mw: float
    q_mvar: float
    x: float
    y: float


@dataclass
class ExistingBus:
    id: str
    x: float
    y: float
    kv: float


@dataclass
class IntermediateBusCandidate:
    id: str
    x: float
    y: float


@dataclass
class Edge:
    a: str
    b: str
    line_type: LineType
    transformer_type: Optional[TransformerType]
    length_km: float


@dataclass
class Solution:
    edges: List[Edge]
    active_intermediate_buses: List[str]

    def copy(self) -> "Solution":
        return copy.deepcopy(self)


@dataclass
class Problem:
    demands: List[Demand]
    existing_buses: List[ExistingBus]
    intermediate_candidates: List[IntermediateBusCandidate]
    line_types: List[LineType]
    transformer_types: List[TransformerType]
    positions: Dict[str, Tuple[float, float]]


# ======================================================================
#  UTILITIES
# ======================================================================
def distance(x1, y1, x2, y2):
    return math.hypot(x1 - x2, y1 - y2)


def length_between(a, b, pos):
    x1, y1 = pos[a]
    x2, y2 = pos[b]
    return distance(x1, y1, x2, y2)


def get_min_line_type(line_types):
    return min(line_types, key=lambda lt: lt.capacity_mva)


def get_max_line_type(line_types):
    return max(line_types, key=lambda lt: lt.capacity_mva)


# ======================================================================
#  COST + ECONOMIES OF SCALE
# ======================================================================
COLLECTOR_FIXED_COST = 150_000.0
ECONOMY_ALPHA = 0.4
DISCONNECT_PENALTY = 10_000_000.0
LONG_DIRECT_THRESHOLD = 20.0
LONG_DIRECT_PENALTY_PER_KM = 5_000.0


def evaluate(sol: Solution, problem: Problem) -> float:
    pos = problem.positions
    supply_ids = {s.id for s in problem.existing_buses}
    demand_ids = {d.id for d in problem.demands}

    # adjacency
    adj: Dict[str, List[Tuple[str, int]]] = {}
    for idx, e in enumerate(sol.edges):
        adj.setdefault(e.a, []).append((e.b, idx))
        adj.setdefault(e.b, []).append((e.a, idx))

    downstream = [0] * len(sol.edges)
    disconnected = 0

    for d in problem.demands:
        start = d.id
        queue = [start]
        parent = {start: None}
        parent_edge = {start: None}
        found = None

        while queue and found is None:
            node = queue.pop(0)
            if node in supply_ids:
                found = node
                break
            for neigh, e_idx in adj.get(node, []):
                if neigh not in parent:
                    parent[neigh] = node
                    parent_edge[neigh] = e_idx
                    queue.append(neigh)

        if found is None:
            disconnected += 1
            continue

        cur = found
        while parent[cur] is not None:
            e_idx = parent_edge[cur]
            downstream[e_idx] += 1
            cur = parent[cur]

    total = 0
    for idx, e in enumerate(sol.edges):
        base = e.length_km * e.line_type.cost_per_km
        n = downstream[idx]
        factor = 1 / (1 + ECONOMY_ALPHA * max(0, n - 1))
        edge_cost = base * factor

        # penalty for long d->s
        if ((e.a in demand_ids and e.b in supply_ids) or
            (e.b in demand_ids and e.a in supply_ids)):
            if e.length_km > LONG_DIRECT_THRESHOLD:
                edge_cost += (e.length_km - LONG_DIRECT_THRESHOLD) * LONG_DIRECT_PENALTY_PER_KM

        total += edge_cost

        if e.transformer_type:
            total += e.transformer_type.cost

    total += COLLECTOR_FIXED_COST * len(sol.active_intermediate_buses)
    total += disconnected * DISCONNECT_PENALTY
    return total


# ======================================================================
#  TOPOLOGY NEIGHBOURHOODS
# ======================================================================
def nbh_reassign_demand(sol, problem):
    s = sol.copy()
    d = random.choice(problem.demands)
    supp = random.choice(problem.existing_buses)
    lt = get_min_line_type(problem.line_types)

    s.edges = [e for e in s.edges if d.id not in (e.a, e.b)]
    length = length_between(d.id, supp.id, problem.positions)
    s.edges.append(Edge(d.id, supp.id, lt, None, length))
    return s


def nbh_insert_intermediate(sol, problem):
    s = sol.copy()
    if not s.edges or not problem.intermediate_candidates:
        return s
    e = random.choice(s.edges)
    mid = random.choice(problem.intermediate_candidates)
    s.edges.remove(e)
    lt = get_min_line_type(problem.line_types)
    length1 = length_between(e.a, mid.id, problem.positions)
    length2 = length_between(mid.id, e.b, problem.positions)
    s.edges.append(Edge(e.a, mid.id, lt, None, length1))
    s.edges.append(Edge(mid.id, e.b, lt, None, length2))
    if mid.id not in s.active_intermediate_buses:
        s.active_intermediate_buses.append(mid.id)
    return s


def nbh_remove_intermediate(sol, problem):
    s = sol.copy()
    if not s.active_intermediate_buses:
        return s

    mid_id = random.choice(s.active_intermediate_buses)
    inc = [e for e in s.edges if mid_id in (e.a, e.b)]
    if len(inc) != 2:
        return s

    e1, e2 = inc
    n1 = e1.b if e1.a == mid_id else e1.a
    n2 = e2.b if e2.a == mid_id else e2.a

    s.edges.remove(e1)
    s.edges.remove(e2)
    s.active_intermediate_buses.remove(mid_id)

    lt = get_min_line_type(problem.line_types)
    length = length_between(n1, n2, problem.positions)
    s.edges.append(Edge(n1, n2, lt, None, length))
    return s


def nbh_build_collector_cluster(sol, problem):
    s = sol.copy()
    if not problem.intermediate_candidates:
        return s

    supp = random.choice(problem.existing_buses)
    sx, sy = supp.x, supp.y
    radius = 40
    nearby = [
        d for d in problem.demands
        if distance(d.x, d.y, sx, sy) <= radius
    ]
    if len(nearby) < 2:
        return s

    k = random.randint(2, min(8, len(nearby)))
    cluster = random.sample(nearby, k)
    cx = sum(d.x for d in cluster) / len(cluster)
    cy = sum(d.y for d in cluster) / len(cluster)

    best_mid = min(
        problem.intermediate_candidates,
        key=lambda ic: distance(ic.x, ic.y, cx, cy) + distance(ic.x, ic.y, sx, sy)
    )
    collector_id = best_mid.id

    cluster_ids = {d.id for d in cluster}
    s.edges = [e for e in s.edges if e.a not in cluster_ids and e.b not in cluster_ids]

    lt_small = get_min_line_type(problem.line_types)
    for d in cluster:
        length = length_between(d.id, collector_id, problem.positions)
        s.edges.append(Edge(d.id, collector_id, lt_small, None, length))

    lt_big = get_max_line_type(problem.line_types)
    length = length_between(collector_id, supp.id, problem.positions)
    s.edges.append(Edge(collector_id, supp.id, lt_big, None, length))

    if collector_id not in s.active_intermediate_buses:
        s.active_intermediate_buses.append(collector_id)

    return s


def nbh_build_feeder_tree(sol, problem):
    """
    Synthesizes a radial MV feeder tree.
    """
    s = sol.copy()
    if not problem.intermediate_candidates or len(problem.demands) < 3:
        return s

    supp = random.choice(problem.existing_buses)
    sx, sy = supp.x, supp.y

    radius = 50
    nearby = [
        d for d in problem.demands
        if distance(d.x, d.y, sx, sy) <= radius
    ]
    if len(nearby) < 3:
        return s

    k = random.randint(3, min(12, len(nearby)))
    feeder_ds = random.sample(nearby, k)
    feeder_ids = {d.id for d in feeder_ds}
    s.edges = [e for e in s.edges if e.a not in feeder_ids and e.b not in feeder_ids]

    feeder_sorted = sorted(
        feeder_ds,
        key=lambda d: math.atan2(d.y - sy, d.x - sx)
    )

    if len(problem.intermediate_candidates) < k:
        return s

    mids = random.sample(problem.intermediate_candidates, k)
    mid_ids = [m.id for m in mids]

    for m in mids:
        if m.id not in s.active_intermediate_buses:
            s.active_intermediate_buses.append(m.id)

    lt_small = get_min_line_type(problem.line_types)

    for d, m in zip(feeder_sorted, mids):
        length = length_between(d.id, m.id, problem.positions)
        s.edges.append(Edge(d.id, m.id, lt_small, None, length))

    for a, b in zip(mid_ids[:-1], mid_ids[1:]):
        length = length_between(a, b, problem.positions)
        s.edges.append(Edge(a, b, lt_small, None, length))

    lt_big = get_max_line_type(problem.line_types)
    trunk_root = mid_ids[-1]
    length = length_between(trunk_root, supp.id, problem.positions)
    s.edges.append(Edge(trunk_root, supp.id, lt_big, None, length))

    return s


# ======================================================================
#  TECHNOLOGY NEIGHBOURHOODS
# ======================================================================
def nbh_change_line_type(sol, problem):
    s = sol.copy()
    if not s.edges:
        return s
    e = random.choice(s.edges)
    e.line_type = random.choice(problem.line_types)
    return s


def nbh_toggle_transformer(sol, problem):
    s = sol.copy()
    if not s.edges:
        return s
    e = random.choice(s.edges)
    if e.transformer_type is None:
        e.transformer_type = random.choice(problem.transformer_types)
    else:
        e.transformer_type = None
    return s


# ======================================================================
#  NESTED VNS
# ======================================================================
def inner_vns(sol, problem, max_k=2):
    neighs = [
        nbh_change_line_type,
        nbh_toggle_transformer,
    ]

    best = sol
    best_cost = evaluate(best, problem)
    k = 0

    while k < max_k:
        cand = neighs[k](best, problem)
        c_cost = evaluate(cand, problem)
        if c_cost < best_cost:
            best, best_cost = cand, c_cost
            k = 0
        else:
            k += 1

    return best, best_cost


def outer_vns(initial, problem, max_iterations=600, max_k_outer=5, inner_max_k=2):
    neighs = [
        nbh_reassign_demand,
        nbh_insert_intermediate,
        nbh_remove_intermediate,
        nbh_build_collector_cluster,
        nbh_build_feeder_tree,
    ]

    best = initial
    best_cost = evaluate(best, problem)

    for _ in range(max_iterations):
        k = 0
        while k < max_k_outer:
            shaken = neighs[k](best, problem)
            refined, r_cost = inner_vns(shaken, problem, inner_max_k)
            if r_cost < best_cost:
                best, best_cost = refined, r_cost
                k = 0
            else:
                k += 1

    return best, best_cost


# ======================================================================
#  INITIAL SOLUTION
# ======================================================================
def build_initial_solution(problem):
    lt = get_min_line_type(problem.line_types)
    edges = []
    for d in problem.demands:
        supp = random.choice(problem.existing_buses)
        length = length_between(d.id, supp.id, problem.positions)
        edges.append(Edge(d.id, supp.id, lt, None, length))
    return Solution(edges, [])


# ======================================================================
#  PROBLEM GENERATION
# ======================================================================
def generate_large_problem(
    n_demands=80,
    n_existing=2,
    n_intermediate=60,
    width=120, height=100
):
    random.seed(42)

    ex = [
        ExistingBus(f"s{i+1}", random.uniform(0, width), random.uniform(0, height), 132)
        for i in range(n_existing)
    ]
    ds = [
        Demand(f"d{i+1}", random.uniform(1, 15), random.uniform(0.2, 4),
               random.uniform(0, width), random.uniform(0, height))
        for i in range(n_demands)
    ]
    inter = [
        IntermediateBusCandidate(f"i{i+1}", random.uniform(0, width), random.uniform(0, height))
        for i in range(n_intermediate)
    ]

    line_types = [
        LineType("L1", 20, 0.1, 0.2, 40),
        LineType("L2", 40, 0.08, 0.18, 60),
        LineType("L3", 80, 0.06, 0.15, 90),
        LineType("L4", 120, 0.05, 0.12, 120),
        LineType("L5", 200, 0.04, 0.10, 160),
    ]

    transformer_types = [
        TransformerType("T10", 10, 0.01, 0.05, 30_000),
        TransformerType("T20", 20, 0.008, 0.04, 45_000),
        TransformerType("T40", 40, 0.006, 0.03, 70_000),
    ]

    pos = {}
    for e in ex: pos[e.id] = (e.x, e.y)
    for d in ds: pos[d.id] = (d.x, d.y)
    for i in inter: pos[i.id] = (i.x, i.y)

    return Problem(ds, ex, inter, line_types, transformer_types, pos)


# ======================================================================
#  PLOTTING
# ======================================================================
def plot_network(solution: Solution, problem: Problem, title="Optimised Network"):

    pos = problem.positions

    # Collect coordinates
    demand_x = [pos[d.id][0] for d in problem.demands]
    demand_y = [pos[d.id][1] for d in problem.demands]

    supply_x = [pos[s.id][0] for s in problem.existing_buses]
    supply_y = [pos[s.id][1] for s in problem.existing_buses]

    intermediate_x = [pos[i][0] for i in solution.active_intermediate_buses]
    intermediate_y = [pos[i][1] for i in solution.active_intermediate_buses]

    # Plot nodes
    plt.figure(figsize=(12, 10))
    plt.scatter(demand_x, demand_y, c="cornflowerblue", s=25, label="Demand")
    plt.scatter(supply_x, supply_y, c="green", s=80, marker="s", label="Supply")
    plt.scatter(intermediate_x, intermediate_y, c="orange", s=40, marker="D", label="Intermediate")

    # Plot edges
    for e in solution.edges:
        x1, y1 = pos[e.a]
        x2, y2 = pos[e.b]

        # Line thickness scales with capacity
        lw = 1 + 0.03 * e.line_type.capacity_mva
        plt.plot([x1, x2], [y1, y2], c="gray", lw=lw, alpha=0.7)

    plt.title(title, fontsize=16)
    plt.xlabel("X coordinate (km)")
    plt.ylabel("Y coordinate (km)")
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


# ======================================================================
#  RUN
# ======================================================================
if __name__ == "__main__":
    random.seed(123)

    print("Generating large problem...")
    problem = generate_large_problem(
        n_demands=20,
        n_existing=5,
        n_intermediate=60,
        width=120,
        height=100,
    )

    init = build_initial_solution(problem)
    init_cost = evaluate(init, problem)
    print(f"Initial cost = {init_cost:,.1f}")

    print("Running NGVNS...")
    best, best_cost = outer_vns(init, problem)

    print("\n===== RESULT =====")
    print(f"Best cost = {best_cost:,.1f}")
    print(f"Intermediate buses = {len(best.active_intermediate_buses)}")
    print(f"Edges = {len(best.edges)}")

    plot_network(best, problem, title="Optimised Network Topology")
