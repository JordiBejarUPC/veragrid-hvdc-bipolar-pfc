# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Build ``Investment_demo.veragrid``: a self-contained IEEE39 snapshot carrying a preloaded,
cost-calibrated portfolio of candidate investments.

The file is meant to be opened live in a client discovery meeting and run straight through
``Investments Evaluation`` with the ``PowerFlow`` objective and the ``NSGA3`` method, producing a
well-populated Pareto curve within seconds and without any preparation.

The build has four stages:

1. Extract the peak-demand hour of the IEEE39 one-week case and freeze it as a snapshot.
2. Stress that snapshot into a forward-looking planning scenario (scaled demand and dispatch,
   seasonal thermal ratings on the older circuits, planning voltage band).
3. Add five families of candidate investments, each in its own investments group.
4. Calibrate every CAPEX so that total spend is commensurate with total technical benefit,
   which is what keeps both Pareto axes visible.
"""
import os
from typing import List, Tuple

import numpy as np

import VeraGridEngine as gce
import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.Diagrams.graphic_location import GraphicLocation
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.InvestmentsEvaluation.Problems.power_flow_problem import (
    PowerFlowInvestmentProblem,
)
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.enumerations import GeneratorControlMode

SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT: str = os.path.abspath(os.path.join(SCRIPT_DIR, '../..', '..'))
SOURCE_GRID: str = os.path.join(REPO_ROOT, 'Grids_and_profiles', 'grids', 'IEEE39_1W.gridcal')
OUTPUT_GRID: str = os.path.join(SCRIPT_DIR, 'Investment_demo.veragrid')

# Demand and dispatch are scaled together so that corridor flows grow. Scaling demand alone would
# only shift the slack generator's output and would barely move the flows at all.
STRESS_FACTOR: float = 1.45

# Planning voltage band. The source grid ships with 0.94/1.06, which is so wide that the voltage
# term of the objective stays at zero and reactive candidates can never earn a place on the front.
VOLTAGE_MIN: float = 0.95
VOLTAGE_MAX: float = 1.05

# Penalty applied per pu of voltage excursion. The objective sums raw MW of losses (order 70 here)
# and overload cost (order 1500), so without a multiplier of this size a 0.03 pu total excursion
# would be numerically invisible next to them.
VOLTAGE_COST: float = 10000.0

# Seasonal thermal de-rating of the older circuits, as branch index -> summer rating in MVA.
# Without this the case has only two binding thermal constraints, which would collapse the Pareto
# front onto the two or three candidates that relieve them.
DERATED_BRANCHES: List[Tuple[int, float]] = [
    (17, 480.0),   # bus 9  -> bus 10
    (12, 390.0),   # bus 5  -> bus 10
    (36, 700.0),   # bus 21 -> bus 34
    (4, 690.0),    # bus 1  -> bus 29
]


class NewCircuitSpec:
    """
    A second circuit strung on an existing corridor, electrically identical to the one already
    there. This is the most expensive way to relieve a corridor and anchors the costly end of the
    Pareto front.
    """
    __slots__ = ('branch_idx', 'capex')

    def __init__(self, branch_idx: int, capex: float) -> None:
        """
        Constructor

        :param branch_idx: index of the parent branch in ``grid.get_branches(...)``
        :param capex: capital expenditure before calibration
        """
        self.branch_idx: int = branch_idx
        self.capex: float = capex


class ReconductorSpec:
    """
    Replacement of an existing conductor with a high-temperature low-sag conductor: more thermal
    capacity on the same towers and the same right of way, and slightly lower resistance. Cheaper
    than a second circuit, so it competes directly against :class:`NewCircuitSpec` on the same
    corridors, which is what gives the middle of the Pareto front its texture.
    """
    __slots__ = ('branch_idx', 'rate_factor', 'r_factor', 'capex')

    def __init__(self, branch_idx: int, rate_factor: float, r_factor: float, capex: float) -> None:
        """
        Constructor

        :param branch_idx: index of the branch being reconductored
        :param rate_factor: multiplier applied to the existing rating
        :param r_factor: multiplier applied to the existing series resistance
        :param capex: capital expenditure before calibration
        """
        self.branch_idx: int = branch_idx
        self.rate_factor: float = rate_factor
        self.r_factor: float = r_factor
        self.capex: float = capex


class ShuntSpec:
    """
    A switched shunt: a capacitor bank when ``b_mvar`` is positive, a reactor when it is negative.
    These are the cheapest candidates in the portfolio and therefore populate the low-cost end of
    the Pareto front.
    """
    __slots__ = ('bus_name', 'b_mvar', 'capex')

    def __init__(self, bus_name: str, b_mvar: float, capex: float) -> None:
        """
        Constructor

        :param bus_name: name of the bus the shunt is connected to
        :param b_mvar: susceptance in MVAr at 1 pu; positive injects reactive power
        :param capex: capital expenditure before calibration
        """
        self.bus_name: str = bus_name
        self.b_mvar: float = b_mvar
        self.capex: float = capex


class BatterySpec:
    """
    A grid-scale battery sited in a load pocket and discharging at the peak hour represented by
    this snapshot. It is modelled in reactive-power control mode so that it relieves corridor
    loading through its active power injection without also propping up the local voltage, which
    keeps its role distinct from that of the shunt candidates.
    """
    __slots__ = ('bus_name', 'p_mw', 'capex')

    def __init__(self, bus_name: str, p_mw: float, capex: float) -> None:
        """
        Constructor

        :param bus_name: name of the bus the battery is connected to
        :param p_mw: active power discharged at the snapshot hour
        :param capex: capital expenditure before calibration
        """
        self.bus_name: str = bus_name
        self.p_mw: float = p_mw
        self.capex: float = capex


# Second circuits on the corridors that carry the congestion.
NEW_CIRCUITS: List[NewCircuitSpec] = [
    NewCircuitSpec(branch_idx=26, capex=148.0),   # bus 15 -> bus 18
    NewCircuitSpec(branch_idx=2, capex=132.0),    # bus 1  -> bus 2
    NewCircuitSpec(branch_idx=17, capex=96.0),    # bus 9  -> bus 10
    NewCircuitSpec(branch_idx=12, capex=118.0),   # bus 5  -> bus 10
    NewCircuitSpec(branch_idx=36, capex=174.0),   # bus 21 -> bus 34
    NewCircuitSpec(branch_idx=4, capex=166.0),    # bus 1  -> bus 29
    NewCircuitSpec(branch_idx=8, capex=104.0),    # bus 3  -> bus 13
]

# Reconductoring options. The first four deliberately target corridors that also have a
# second-circuit option, so the optimizer has to choose between them.
RECONDUCTORS: List[ReconductorSpec] = [
    ReconductorSpec(branch_idx=26, rate_factor=1.6, r_factor=0.85, capex=72.0),
    ReconductorSpec(branch_idx=2, rate_factor=1.6, r_factor=0.85, capex=64.0),
    ReconductorSpec(branch_idx=17, rate_factor=1.6, r_factor=0.85, capex=46.0),
    ReconductorSpec(branch_idx=12, rate_factor=1.6, r_factor=0.85, capex=58.0),
    ReconductorSpec(branch_idx=38, rate_factor=1.6, r_factor=0.85, capex=84.0),
    ReconductorSpec(branch_idx=33, rate_factor=1.6, r_factor=0.85, capex=78.0),
]

# Capacitor banks across the depressed-voltage pocket in the load centre.
#
# The two reactors are sited on the highest-voltage buses that are NOT generator terminals. A
# shunt on a voltage-controlled generator bus cannot move the local voltage at all, because the
# machine simply re-dispatches its reactive output to hold its setpoint; siting a reactor there
# would create a candidate that can never do anything. In this scenario the system is
# voltage-depressed rather than voltage-high, so the reactors are deliberately high-regret
# options that the optimizer is expected to reject most of the time.
SHUNTS: List[ShuntSpec] = [
    ShuntSpec(bus_name='bus 11', b_mvar=120.0, capex=16.0),
    ShuntSpec(bus_name='bus 6', b_mvar=100.0, capex=14.0),
    ShuntSpec(bus_name='bus 7', b_mvar=90.0, capex=12.5),
    ShuntSpec(bus_name='bus 4', b_mvar=75.0, capex=11.0),
    ShuntSpec(bus_name='bus 5', b_mvar=60.0, capex=9.0),
    ShuntSpec(bus_name='bus 14', b_mvar=50.0, capex=8.0),
    ShuntSpec(bus_name='bus 0', b_mvar=-60.0, capex=10.5),
    ShuntSpec(bus_name='bus 24', b_mvar=-50.0, capex=8.5),
]

# Storage sited at the largest load pockets.
BATTERIES: List[BatterySpec] = [
    BatterySpec(bus_name='bus 26', p_mw=150.0, capex=138.0),
    BatterySpec(bus_name='bus 7', p_mw=100.0, capex=96.0),
    BatterySpec(bus_name='bus 20', p_mw=80.0, capex=78.0),
    BatterySpec(bus_name='bus 15', p_mw=50.0, capex=52.0),
]


def build_power_flow_options() -> gce.PowerFlowOptions:
    """
    Power flow settings used both for the build-time calibration and, by default, for the live
    evaluation. Newton-Raphson without control loops keeps every one of the ~1250 evaluations of
    an NSGA3 run fast and, more importantly, deterministic in front of an audience.

    :return: the power flow options
    """
    return gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                tolerance=1e-6,
                                max_iter=40,
                                control_q=False,
                                retry_with_other_methods=False,
                                verbose=0)


def extract_peak_snapshot() -> MultiCircuit:
    """
    Load the IEEE39 one-week case, find the hour of highest total demand and freeze the grid in
    that state. The profiles are then deleted so that the delivered file cannot accidentally
    trigger a time-series run, which would take minutes instead of seconds.

    :return: the snapshot grid, with no time profiles
    """
    grid: MultiCircuit = gce.open_file(SOURCE_GRID)

    # Sum every load profile to find the system peak rather than any individual bus peak.
    n_time: int = grid.get_time_number()
    total_demand: Vec = np.zeros(n_time, dtype=float)
    for load in grid.get_loads():
        total_demand += np.asarray(load.P_prof.toarray(), dtype=float)

    t_peak: int = int(np.argmax(total_demand))
    print(f"Peak hour t={t_peak} of {n_time}, total demand {total_demand[t_peak]:.1f} MW")

    grid.set_state(t_peak)
    grid.delete_profiles()
    grid.name = "Investment demo - IEEE39 New England 2035 peak"

    return grid


def apply_planning_scenario(grid: MultiCircuit) -> None:
    """
    Turn the historical peak hour into a forward-looking planning scenario. Demand and dispatch
    are scaled together, the older circuits take their seasonal thermal rating, and the voltage
    band is narrowed to a planning criterion with a penalty large enough for the voltage term of
    the objective to register next to losses and overloads.

    :param grid: the snapshot grid, modified in place
    """
    # Scale demand and generation by the same factor. Doing only one of the two would be absorbed
    # by the slack bus and would leave the corridor flows essentially unchanged.
    for load in grid.get_loads():
        load.P = load.P * STRESS_FACTOR
        load.Q = load.Q * STRESS_FACTOR

    for generator in grid.get_generators():
        generator.P = generator.P * STRESS_FACTOR

        # Bring every voltage setpoint inside the planning band. The source case schedules one
        # machine at 1.0636 pu, and because a generator holds its terminal voltage no investment
        # of any kind could ever clear that excursion. Left alone it would add a constant penalty
        # to every point of the Pareto front and make a fully compliant solution impossible.
        generator.Vset = min(max(generator.Vset, VOLTAGE_MIN), VOLTAGE_MAX)

    # Seasonal ratings on the older circuits.
    branches = grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)
    for branch_idx, summer_rate in DERATED_BRANCHES:
        branches[branch_idx].rate = summer_rate

    # Planning voltage band and its penalty.
    for bus in grid.get_buses():
        bus.Vmin = VOLTAGE_MIN
        bus.Vmax = VOLTAGE_MAX
        bus.Vm_cost = VOLTAGE_COST


def find_bus(grid: MultiCircuit, bus_name: str) -> dev.Bus:
    """
    Resolve a bus by name.

    :param grid: the grid to search
    :param bus_name: the name to look for
    :return: the matching bus
    """
    for bus in grid.get_buses():
        if bus.name == bus_name:
            return bus
        else:
            pass

    raise ValueError(f"Bus '{bus_name}' not found in the grid")


def add_new_circuit_candidates(grid: MultiCircuit) -> None:
    """
    Add a second, electrically identical circuit on each congested corridor. Each new line is
    created inactive and paired with a single investment that switches it on.

    :param grid: the grid, modified in place
    """
    branches = grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)

    for spec in NEW_CIRCUITS:
        parent = branches[spec.branch_idx]

        # The new circuit must start out switched off. ``active`` is passed into the constructor
        # rather than assigned afterwards, because a later assignment sets only the scalar flag and
        # leaves any profile array untouched.
        candidate: dev.Line = dev.Line(bus_from=parent.bus_from,
                                       bus_to=parent.bus_to,
                                       name=f"{parent.name} 2nd circuit",
                                       r=parent.R,
                                       x=parent.X,
                                       b=parent.B,
                                       rate=parent.rate,
                                       cost=parent.Cost,
                                       active=False)
        grid.add_line(candidate)

        group: dev.InvestmentsGroup = dev.InvestmentsGroup(
            name=f"New circuit {parent.bus_from.name} - {parent.bus_to.name}",
            category="Transmission line"
        )
        grid.add_investments_group(group)
        grid.add_investment(dev.Investment(device=candidate,
                                           name=f"Build {candidate.name}",
                                           CAPEX=spec.capex,
                                           status=True,
                                           group=group))


def add_reconductoring_candidates(grid: MultiCircuit) -> None:
    """
    Add a reconductoring option on selected corridors. The engine's investment machinery only ever
    toggles the ``active`` flag, so an in-place parameter change has to be expressed as a pair of
    investments in one group: switch on an uprated replacement line, and switch off the original.

    :param grid: the grid, modified in place
    """
    branches = grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)

    for spec in RECONDUCTORS:
        parent = branches[spec.branch_idx]

        # The replacement shares the towers, so only the rating and the resistance change.
        replacement: dev.Line = dev.Line(bus_from=parent.bus_from,
                                         bus_to=parent.bus_to,
                                         name=f"{parent.name} reconductored",
                                         r=parent.R * spec.r_factor,
                                         x=parent.X,
                                         b=parent.B,
                                         rate=parent.rate * spec.rate_factor,
                                         cost=parent.Cost,
                                         active=False)
        grid.add_line(replacement)

        group: dev.InvestmentsGroup = dev.InvestmentsGroup(
            name=f"Reconductor {parent.bus_from.name} - {parent.bus_to.name}",
            category="Reconductoring"
        )
        grid.add_investments_group(group)

        # Carry the whole cost of the group on the activating investment.
        grid.add_investment(dev.Investment(device=replacement,
                                           name=f"Install {replacement.name}",
                                           CAPEX=spec.capex,
                                           status=True,
                                           group=group))

        # ``status=False`` retires the original conductor whenever this group is selected.
        grid.add_investment(dev.Investment(device=parent,
                                           name=f"Retire {parent.name}",
                                           CAPEX=0.0,
                                           status=False,
                                           group=group))


def add_shunt_candidates(grid: MultiCircuit) -> None:
    """
    Add switched capacitor banks in the depressed-voltage pocket and shunt reactors where the
    snapshot voltage runs high. These are the only candidates that act directly on the voltage
    term of the objective.

    :param grid: the grid, modified in place
    """
    for spec in SHUNTS:
        bus: dev.Bus = find_bus(grid=grid, bus_name=spec.bus_name)

        if spec.b_mvar >= 0.0:
            kind: str = "Capacitor bank"
        else:
            kind = "Shunt reactor"

        candidate: dev.Shunt = dev.Shunt(name=f"{kind} {spec.bus_name}",
                                         G=0.0,
                                         B=spec.b_mvar,
                                         active=False)
        grid.add_shunt(bus, candidate)

        group: dev.InvestmentsGroup = dev.InvestmentsGroup(
            name=f"{kind} at {spec.bus_name} ({abs(spec.b_mvar):.0f} MVAr)",
            category=kind
        )
        grid.add_investments_group(group)
        grid.add_investment(dev.Investment(device=candidate,
                                           name=f"Install {candidate.name}",
                                           CAPEX=spec.capex,
                                           status=True,
                                           group=group))


def add_battery_candidates(grid: MultiCircuit) -> None:
    """
    Add grid-scale storage at the largest load pockets. Reactive control mode is used so that the
    battery relieves corridor loading through its active power injection alone, leaving voltage
    support to the shunt candidates.

    :param grid: the grid, modified in place
    """
    for spec in BATTERIES:
        bus: dev.Bus = find_bus(grid=grid, bus_name=spec.bus_name)

        candidate: dev.Battery = dev.Battery(name=f"BESS {spec.bus_name}",
                                             P=spec.p_mw,
                                             Pmin=-spec.p_mw,
                                             Pmax=spec.p_mw,
                                             Snom=spec.p_mw,
                                             Enom=spec.p_mw * 4.0,
                                             control_mode=GeneratorControlMode.Q,
                                             active=False)
        grid.add_battery(bus, candidate)

        group: dev.InvestmentsGroup = dev.InvestmentsGroup(
            name=f"Battery at {spec.bus_name} ({spec.p_mw:.0f} MW / 4h)",
            category="Storage"
        )
        grid.add_investments_group(group)
        grid.add_investment(dev.Investment(device=candidate,
                                           name=f"Install {candidate.name}",
                                           CAPEX=spec.capex,
                                           status=True,
                                           group=group))


def register_candidate_lines_in_diagram(grid: MultiCircuit) -> int:
    """
    Put every candidate line onto the existing schematic diagram.

    Devices created after a diagram has been built are not drawn unless the diagram holds a
    location for them, so without this step the candidate circuits would be invisible in the GUI
    and selecting a Pareto point would appear to change nothing on the one-line diagram. A line's
    geometry is derived from its two buses, so an empty location is all that is required.
    Injections do not need an entry at all: they are drawn as children of their bus, which is why
    the source grid's loads and generators are absent from the diagram data.

    :param grid: the grid, whose diagrams are modified in place
    :return: number of line locations added
    """
    n_added: int = 0

    for diagram in grid.diagrams:
        for line in grid.get_lines():
            if diagram.query_point(line) is None:
                diagram.set_point(device=line, location=GraphicLocation(api_object=line))
                n_added += 1
            else:
                pass

    return n_added


def calibrate_capex(grid: MultiCircuit, pf_options: gce.PowerFlowOptions) -> float:
    """
    Scale every CAPEX so that spending the whole portfolio costs about as much as the technical
    benefit it delivers.

    The objective adds a financial score to a technical score without normalising either, so if
    the two differ by orders of magnitude one axis flattens and the Pareto front degenerates into
    a single cluster. Anchoring total spend to total benefit puts the knee of the curve in the
    middle of the plot, where it is visible.

    :param grid: the grid carrying the candidate portfolio, modified in place
    :param pf_options: power flow settings used for the two probe evaluations
    :return: the multiplier that was applied to every CAPEX
    """
    problem: PowerFlowInvestmentProblem = PowerFlowInvestmentProblem(grid=grid, pf_options=pf_options)
    n_groups: int = len(grid.investments_groups)

    # Technical score with nothing built, and with everything built.
    f_none: Vec = problem.objective_function(x=np.zeros(n_groups, dtype=int))
    f_all: Vec = problem.objective_function(x=np.ones(n_groups, dtype=int))

    technical_none: float = float(f_none[5])
    technical_all: float = float(f_all[5])
    benefit: float = technical_none - technical_all
    total_capex: float = float(sum(inv.CAPEX for inv in grid.investments))

    print(f"  technical score, nothing built : {technical_none:10.1f}")
    print(f"  technical score, all built     : {technical_all:10.1f}")
    print(f"  total technical benefit        : {benefit:10.1f}")
    print(f"  total CAPEX before calibration : {total_capex:10.1f}")

    if benefit > 0.0 and total_capex > 0.0:
        factor: float = benefit / total_capex
    else:
        raise RuntimeError("Cannot calibrate: the portfolio delivers no measurable benefit")

    for investment in grid.investments:
        investment.CAPEX = round(investment.CAPEX * factor, 2)

    print(f"  calibration factor             : {factor:10.4f}")

    return factor


def report_violations(grid: MultiCircuit, pf_options: gce.PowerFlowOptions, label: str) -> None:
    """
    Run a snapshot power flow and print every thermal and voltage violation. Used to confirm that
    the delivered base case is stressed enough to be worth optimising.

    :param grid: the grid to solve
    :param pf_options: power flow settings
    :param label: heading printed above the report
    """
    driver: gce.PowerFlowDriver = gce.PowerFlowDriver(grid=grid, options=pf_options)
    driver.run()

    loading = np.abs(driver.results.loading)
    voltage = np.abs(driver.results.voltage)
    branches = grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)
    buses = grid.get_buses()

    print(f"\n{label} (converged: {bool(driver.results.converged)})")
    print(f"  losses: {driver.results.losses.real.sum():.1f} MW")

    overloaded = np.where(loading > 1.0)[0]
    print(f"  overloaded branches: {len(overloaded)}")
    for i in overloaded:
        print(f"    {branches[i].name:24s} {loading[i] * 100.0:6.1f} %  (rate {branches[i].rate:.0f} MVA)")

    out_of_band = np.where((voltage < VOLTAGE_MIN) | (voltage > VOLTAGE_MAX))[0]
    print(f"  buses outside {VOLTAGE_MIN}-{VOLTAGE_MAX} pu: {len(out_of_band)}")
    for i in out_of_band:
        print(f"    {buses[i].name:24s} {voltage[i]:.4f} pu")


def main() -> None:
    """
    Build the demo grid and write it to ``Investment_demo.veragrid``.
    """
    pf_options: gce.PowerFlowOptions = build_power_flow_options()

    print("=== 1. Peak snapshot ===")
    grid: MultiCircuit = extract_peak_snapshot()

    print("\n=== 2. Planning scenario ===")
    apply_planning_scenario(grid=grid)
    report_violations(grid=grid, pf_options=pf_options, label="Base case, no investments")

    print("\n=== 3. Candidate portfolio ===")
    add_new_circuit_candidates(grid=grid)
    add_reconductoring_candidates(grid=grid)
    add_shunt_candidates(grid=grid)
    add_battery_candidates(grid=grid)
    print(f"  investment groups: {len(grid.investments_groups)}")
    print(f"  investments      : {len(grid.investments)}")
    print(f"  candidate lines drawn on the diagram: {register_candidate_lines_in_diagram(grid=grid)}")

    print("\n=== 4. CAPEX calibration ===")
    calibrate_capex(grid=grid, pf_options=pf_options)

    gce.save_file(grid, OUTPUT_GRID)
    print(f"\nSaved: {OUTPUT_GRID}")


if __name__ == '__main__':
    main()
