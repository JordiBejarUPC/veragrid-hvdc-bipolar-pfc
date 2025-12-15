from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Callable
import random
import math
import copy
import matplotlib.pyplot as plt


# ======================================================================
#  GLOBAL PARAMETERS (TUNE THESE)
# ======================================================================
# Maximum distance for a demand to connect to a NON-SUPPLY parent (hub or other demand)
R_PARENT_MAX = 20.0      # [km], adjust to your scale

# Soft discouragement for long demand→parent spokes
R_SOFT = 12.0            # [km] threshold where penalty starts
LONG_SPOKE_PENALTY = 2000.0  # cost factor for long spokes

# Economies-of-scale factor for backbone lines
ECON_ALPHA = 0.4

# Hub fixed cost
COLLECTOR_COST = 150_000.0

# Penalty if some demand cannot reach any supply (should not happen with MST)
DISCONNECT_PENALTY = 10_000_000.0

ROOT = "__ROOT__"


# ======================================================================
#  DATA CLASSES
# ======================================================================
@dataclass
class Demand:
    id: str
    p_mw: float
    q_mvar: float
    x: float
    y: float


@dataclass
class SupplyBus:
    id: str
    x: float
    y: float
    kv: float


@dataclass
class HubCandidate:
    id: str
    x: float
    y: float


@dataclass
class LineType:
    id: str
    cost_per_km: float
    capacity_mva: float


@dataclass
class Edge:
    a: str
    b: str
    length_km: float
    line_type: LineType


@dataclass
class Problem:
    demands: List[Demand]
    supplies: List[SupplyBus]
    hubs: List[HubCandidate]
    line_low: LineType
    line_high: LineType
    positions: Dict[str, Tuple[float, float]]


@dataclass
class Solution:
    # demand_id -> parent_id (parent can be supply, hub, or another demand)
    assign: Dict[str, str]

    def copy(self) -> "Solution":
        return Solution(assign=dict(self.assign))


# ======================================================================
#  GEOMETRY UTILITIES
# ======================================================================
def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)


def length_between(a: str, b: str, pos: Dict[str, Tuple[float, float]]) -> float:
    x1, y1 = pos[a]
    x2, y2 = pos[b]
    return math.hypot(x1 - x2, y1 - y2)


def distance_to_closest_supply(node_id: str, problem: Problem) -> float:
    x, y = problem.positions[node_id]
    best = float("inf")
    for s in problem.supplies:
        L = distance(x, y, s.x, s.y)
        if L < best:
            best = L
    return best


# ======================================================================
#  NETWORK CONSTRUCTION (DEMAND TREE + BACKBONE MST)
# ======================================================================
def build_edges(sol: Solution, problem: Problem) -> List[Edge]:
    """
    Build full network from assignment:
      - Demand → parent (low-voltage lines).
      - Backbone MST over supplies + used hubs + demand-parents (high-voltage lines).
    """
    pos = problem.positions
    low = problem.line_low
    high = problem.line_high

    demand_ids = [d.id for d in problem.demands]
    supply_ids = [s.id for s in problem.supplies]
    hub_ids = [h.id for h in problem.hubs]

    edges: List[Edge] = []
    used_hubs: set[str] = set()
    used_demands_as_parents: set[str] = set()

    # 1) demand → parent
    for d_id in demand_ids:
        parent = sol.assign[d_id]
        if parent == d_id:
            continue  # safety, should not occur
        L = length_between(d_id, parent, pos)
        edges.append(Edge(d_id, parent, L, low))
        if parent in hub_ids:
            used_hubs.add(parent)
        if parent in demand_ids:
            used_demands_as_parents.add(parent)

    # 2) backbone MST over supplies + used hubs + demand-parents
    backbone_nodes = set(supply_ids) | used_hubs | used_demands_as_parents
    backbone_nodes = list(backbone_nodes)

    if len(backbone_nodes) <= 1:
        # Only one supply (or nothing); no backbone needed
        return edges

    remaining = set(backbone_nodes)
    start = backbone_nodes[0]
    remaining.remove(start)
    in_tree = {start}

    while remaining:
        best_pair = None
        best_L = float("inf")
        for u in in_tree:
            for v in remaining:
                L = length_between(u, v, pos)
                if L < best_L:
                    best_L = L
                    best_pair = (u, v)
        u, v = best_pair
        edges.append(Edge(u, v, best_L, high))
        in_tree.add(v)
        remaining.remove(v)

    return edges


# ======================================================================
#  COST MODEL
# ======================================================================
def evaluate(sol: Solution, problem: Problem) -> float:
    pos = problem.positions
    demand_ids = {d.id for d in problem.demands}
    supply_ids = {s.id for s in problem.supplies}
    hub_ids = {h.id for h in problem.hubs}

    edges = build_edges(sol, problem)

    # adjacency (node -> list[(neigh, edge_idx)])
    adj: Dict[str, List[Tuple[str, Optional[int]]]] = {}
    for idx, e in enumerate(edges):
        adj.setdefault(e.a, []).append((e.b, idx))
        adj.setdefault(e.b, []).append((e.a, idx))

    # connect ROOT to all supplies (zero-cost)
    for s in problem.supplies:
        adj.setdefault(ROOT, []).append((s.id, None))
        adj.setdefault(s.id, []).append((ROOT, None))

    # downstream demand counting
    downstream = [0] * len(edges)
    disconnected = 0

    for d in problem.demands:
        start = d.id
        queue = [start]
        parent_node: Dict[str, Optional[str]] = {start: None}
        parent_edge: Dict[str, Optional[int]] = {start: None}
        found_root = False

        while queue and not found_root:
            node = queue.pop(0)
            if node == ROOT:
                found_root = True
                break
            for neigh, e_idx in adj.get(node, []):
                if neigh not in parent_node:
                    parent_node[neigh] = node
                    parent_edge[neigh] = e_idx
                    queue.append(neigh)

        if not found_root:
            disconnected += 1
            continue

        # backtrack ROOT → demand
        cur = ROOT
        while parent_node[cur] is not None:
            e_idx = parent_edge[cur]
            if e_idx is not None:
                downstream[e_idx] += 1
            cur = parent_node[cur]

    total = 0.0
    used_hubs: set[str] = set()

    for idx, e in enumerate(edges):
        base = e.length_km * e.line_type.cost_per_km

        # soft penalty for long spokes on low-voltage lines
        if e.line_type is problem.line_low and e.length_km > R_SOFT:
            total += (e.length_km - R_SOFT) ** 2 * LONG_SPOKE_PENALTY

        # economies of scale on backbone
        if e.line_type is problem.line_high:
            n = downstream[idx]
            factor = 1.0 / (1.0 + ECON_ALPHA * max(0, n - 1))
        else:
            factor = 1.0

        edge_cost = base * factor
        total += edge_cost

        # track used hubs
        if e.a in hub_ids:
            used_hubs.add(e.a)
        if e.b in hub_ids:
            used_hubs.add(e.b)

    total += COLLECTOR_COST * len(used_hubs)
    total += DISCONNECT_PENALTY * disconnected
    return total


# ======================================================================
#  NEIGHBOURHOODS
# ======================================================================
def nbh_move_single_demand(sol: Solution, problem: Problem) -> Solution:
    """
    Move a single demand to another parent (supply, hub, or demand),
    respecting R_PARENT_MAX for non-supply parents.
    """
    s = sol.copy()
    if not problem.demands:
        return s

    d = random.choice(problem.demands)
    d_id = d.id
    pos = problem.positions

    supply_ids = {sup.id for sup in problem.supplies}
    hub_ids = {h.id for h in problem.hubs}
    demand_ids = {dd.id for dd in problem.demands}

    candidate_parents = list(supply_ids | hub_ids | (demand_ids - {d_id}))

    current = s.assign[d_id]
    choices = [c for c in candidate_parents if c != current]

    # filter by distance for non-supplies
    feasible: List[str] = []
    for c in choices:
        L = length_between(d_id, c, pos)
        if c in supply_ids:
            # allow any distance to supplies (baseline)
            feasible.append(c)
        else:
            if L <= R_PARENT_MAX:
                feasible.append(c)

    if not feasible:
        return s

    s.assign[d_id] = random.choice(feasible)
    return s


def nbh_move_cluster(sol: Solution, problem: Problem, radius: float = 20.0) -> Solution:
    """
    Move a cluster of nearby demands to a new parent, enforcing distance
    constraints for non-supply parents.
    """
    s = sol.copy()
    pos = problem.positions
    demands = problem.demands
    if not demands:
        return s

    pivot = random.choice(demands)
    px, py = pivot.x, pivot.y

    cluster = [
        d for d in demands
        if distance(px, py, d.x, d.y) <= radius
    ]
    if len(cluster) <= 1:
        return s

    supply_ids = {sup.id for sup in problem.supplies}
    hub_ids = {h.id for h in problem.hubs}
    demand_ids = {dd.id for dd in demands}

    target_candidates = list(supply_ids | hub_ids | demand_ids)

    pivot_current = s.assign[pivot.id]
    possible_targets = [t for t in target_candidates if t != pivot_current]
    if not possible_targets:
        return s

    new_target = random.choice(possible_targets)

    for d in cluster:
        d_id = d.id
        L = length_between(d_id, new_target, pos)
        if new_target in supply_ids:
            # allow any distance to supplies
            s.assign[d_id] = new_target
        else:
            if L <= R_PARENT_MAX:
                s.assign[d_id] = new_target

    return s


def nbh_assign_to_nearest(sol: Solution, problem: Problem, fraction: float = 0.2) -> Solution:
    """
    Intensification: for a subset of demands, assign to nearest feasible parent.
    Non-supply parents must be within R_PARENT_MAX; otherwise nearest supply.
    """
    s = sol.copy()
    pos = problem.positions
    demands = problem.demands

    if not demands:
        return s

    supply_ids = {sup.id for sup in problem.supplies}
    hub_ids = {h.id for h in problem.hubs}
    demand_ids = {dd.id for dd in demands}

    all_parents = list(supply_ids | hub_ids | demand_ids)

    k = max(1, int(len(demands) * fraction))
    selected = random.sample(demands, k)

    for d in selected:
        d_id = d.id

        # first, find nearest parent among all nodes
        best = None
        best_L = float("inf")
        for p in all_parents:
            if p == d_id:
                continue
            L = length_between(d_id, p, pos)
            if L < best_L:
                best_L = L
                best = p

        if best is None:
            continue

        # if best is a supply, take it regardless of distance
        if best in supply_ids:
            s.assign[d_id] = best
            continue

        # if best is non-supply but within R_PARENT_MAX → OK
        if best_L <= R_PARENT_MAX:
            s.assign[d_id] = best
            continue

        # otherwise fallback: nearest supply (even if far)
        best_s = None
        best_Ls = float("inf")
        for sup in problem.supplies:
            Ls = length_between(d_id, sup.id, pos)
            if Ls < best_Ls:
                best_Ls = Ls
                best_s = sup.id
        if best_s is not None:
            s.assign[d_id] = best_s

    return s


def nbh_chain_nearby_demand(sol: Solution, problem: Problem, R_chain: float = 15.0) -> Solution:
    """
    Demand→demand chaining operator:
      - A chains to B if:
        * B is within R_chain,
        * B is closer to supplies than A,
        * B has limited fan-out (<= 3 children),
        * A→B is shorter than A→current_parent,
        * and respects R_PARENT_MAX (for non-supply parent).
    """
    s = sol.copy()
    demands = problem.demands
    if not demands:
        return s

    pos = problem.positions
    demand_ids = {d.id for d in demands}
    supply_ids = {sup.id for sup in problem.supplies}

    # pick demand A
    A = random.choice(demands)
    A_id = A.id
    A_parent = s.assign[A_id]
    A_supply_dist = distance_to_closest_supply(A_id, problem)

    # find nearby candidate demands B
    candidates: List[Demand] = []
    for B in demands:
        if B.id == A_id:
            continue
        if distance(A.x, A.y, B.x, B.y) <= R_chain:
            candidates.append(B)

    if not candidates:
        return s

    # pick B with smaller supply distance (pulling A "downhill" toward supplies)
    best_B: Optional[Demand] = None
    best_dist = float("inf")

    for B in candidates:
        dist_B = distance_to_closest_supply(B.id, problem)
        if dist_B < A_supply_dist and dist_B < best_dist:
            best_dist = dist_B
            best_B = B

    if best_B is None:
        return s

    B_id = best_B.id

    # fan-out limit: each demand can parent at most 3 children
    children_of_B = [d for d, p in s.assign.items() if p == B_id]
    if len(children_of_B) >= 3:
        return s

    # local cost check: A→B must be shorter than A→current_parent
    L_AB = length_between(A_id, B_id, pos)
    L_A_parent = length_between(A_id, A_parent, pos)

    if L_AB >= L_A_parent:
        return s

    # respect R_PARENT_MAX for non-supply parents
    if B_id not in supply_ids and L_AB > R_PARENT_MAX:
        return s

    # finally accept
    s.assign[A_id] = B_id
    return s


# ======================================================================
#  INNER VNS
# ======================================================================
def inner_vns(sol: Solution, problem: Problem, max_k: int = 2) -> Tuple[Solution, float]:
    best = sol
    best_cost = evaluate(best, problem)
    k = 0

    while k < max_k:
        # simple intensification: reassignment to nearest feasible parent
        cand = nbh_assign_to_nearest(best, problem, fraction=0.1 if k == 0 else 0.05)
        c_cost = evaluate(cand, problem)
        if c_cost < best_cost:
            best, best_cost = cand, c_cost
            k = 0
        else:
            k += 1

    return best, best_cost


# ======================================================================
#  OUTER VNS
# ======================================================================
def outer_vns(
    initial: Solution,
    problem: Problem,
    max_iterations: int = 300,
    max_k_outer: int = 4,
    inner_max_k: int = 2,
) -> Tuple[Solution, float]:
    neighbourhoods: List[Callable[[Solution, Problem], Solution]] = [
        nbh_chain_nearby_demand,
        nbh_move_single_demand,
        nbh_move_cluster,
        nbh_assign_to_nearest,
    ]

    best = initial
    best_cost = evaluate(best, problem)

    for _ in range(max_iterations):
        k = 0
        while k < max_k_outer:
            shaken = neighbourhoods[k](best, problem)
            refined, r_cost = inner_vns(shaken, problem, max_k=inner_max_k)
            if r_cost < best_cost:
                best, best_cost = refined, r_cost
                k = 0
            else:
                k += 1

    return best, best_cost


# ======================================================================
#  INITIAL SOLUTION (DEMAND → NEAREST SUPPLY)
# ======================================================================
def build_initial_solution(problem: Problem) -> Solution:
    assign: Dict[str, str] = {}
    for d in problem.demands:
        best_s = None
        best_L = float("inf")
        for s in problem.supplies:
            L = distance(d.x, d.y, s.x, s.y)
            if L < best_L:
                best_L = L
                best_s = s.id
        assign[d.id] = best_s
    return Solution(assign=assign)


# ======================================================================
#  PROBLEM GENERATION (RANDOM EXAMPLE)
# ======================================================================
def generate_problem(
    n_demands: int = 60,
    n_supplies: int = 2,
    n_hubs: int = 20,
    width: float = 120.0,
    height: float = 100.0,
) -> Problem:
    random.seed(123)

    supplies: List[SupplyBus] = []
    for i in range(n_supplies):
        supplies.append(
            SupplyBus(
                id=f"s{i+1}",
                x=random.uniform(0, width),
                y=random.uniform(0, height),
                kv=132.0,
            )
        )

    demands: List[Demand] = []
    for i in range(n_demands):
        demands.append(
            Demand(
                id=f"d{i+1}",
                p_mw=random.uniform(1, 10),
                q_mvar=random.uniform(0.2, 3.0),
                x=random.uniform(0, width),
                y=random.uniform(0, height),
            )
        )

    hubs: List[HubCandidate] = []
    for i in range(n_hubs):
        hubs.append(
            HubCandidate(
                id=f"h{i+1}",
                x=random.uniform(0, width),
                y=random.uniform(0, height),
            )
        )

    line_low = LineType("L_low", cost_per_km=50.0, capacity_mva=20.0)
    line_high = LineType("L_high", cost_per_km=80.0, capacity_mva=200.0)

    positions: Dict[str, Tuple[float, float]] = {}
    for s in supplies:
        positions[s.id] = (s.x, s.y)
    for d in demands:
        positions[d.id] = (d.x, d.y)
    for h in hubs:
        positions[h.id] = (h.x, h.y)

    return Problem(
        demands=demands,
        supplies=supplies,
        hubs=hubs,
        line_low=line_low,
        line_high=line_high,
        positions=positions,
    )


# ======================================================================
#  PLOTTING
# ======================================================================
def plot_network(sol: Solution, problem: Problem, title: str = "Optimised Network") -> None:
    pos = problem.positions
    edges = build_edges(sol, problem)

    demand_ids = {d.id for d in problem.demands}
    supply_ids = {s.id for s in problem.supplies}
    hub_ids = {h.id for h in problem.hubs}

    used_hubs: set[str] = set()
    used_demand_parents: set[str] = set()

    for d_id, parent in sol.assign.items():
        if parent in hub_ids:
            used_hubs.add(parent)
        if parent in demand_ids:
            used_demand_parents.add(parent)

    # Plot edges
    plt.figure(figsize=(12, 10))
    for e in edges:
        x1, y1 = pos[e.a]
        x2, y2 = pos[e.b]
        lw = 1.4 if e.line_type.id == "L_high" else 0.8
        plt.plot([x1, x2], [y1, y2], c="gray", lw=lw, alpha=0.7)

    # Nodes
    demand_x = [pos[d][0] for d in demand_ids]
    demand_y = [pos[d][1] for d in demand_ids]

    supply_x = [pos[s][0] for s in supply_ids]
    supply_y = [pos[s][1] for s in supply_ids]

    hub_x = [pos[h][0] for h in used_hubs]
    hub_y = [pos[h][1] for h in used_hubs]

    parent_dem_x = [pos[d][0] for d in used_demand_parents]
    parent_dem_y = [pos[d][1] for d in used_demand_parents]

    plt.scatter(demand_x, demand_y, c="cornflowerblue", s=25, label="Demands")
    plt.scatter(supply_x, supply_y, c="green", marker="s", s=90, label="Supplies")
    plt.scatter(hub_x, hub_y, c="orange", marker="D", s=50, label="Hubs (used)")
    plt.scatter(parent_dem_x, parent_dem_y, c="red", marker="o", s=35, label="Demand-parents")

    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


# ======================================================================
#  MAIN
# ======================================================================
if __name__ == "__main__":
    problem = generate_problem(
        n_demands=20,
        n_supplies=5,
        n_hubs=20,
        width=120.0,
        height=100.0,
    )

    initial = build_initial_solution(problem)
    init_cost = evaluate(initial, problem)
    print(f"Initial cost: {init_cost:,.1f}")

    best, best_cost = outer_vns(initial, problem)
    print(f"Best cost:   {best_cost:,.1f}")

    # Summary
    hub_ids = {h.id for h in problem.hubs}
    demand_ids = {d.id for d in problem.demands}
    used_hubs = {p for p in best.assign.values() if p in hub_ids}
    used_demand_parents = {p for p in best.assign.values() if p in demand_ids}

    print(f"Used hubs: {len(used_hubs)} / {len(problem.hubs)}")
    print(f"Demand parents: {len(used_demand_parents)}")
    print(f"Total edges in final network: {len(build_edges(best, problem))}")

    plot_network(best, problem, title="Optimised Feeder Network (with Distance Constraints)")
