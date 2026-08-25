# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Build the two contingency analysis demo files:

* ``Contingency_demo.veragrid``    - N-1 outage of every circuit, plus the trip of every
                                     generating unit.
* ``Contingency_demo_N2.veragrid`` - a small, hand-picked set of common-mode N-2 events.

Both are meant to be opened live in a client discovery meeting and run straight through
``Contingency Analysis`` with the ``Power flow`` method, producing a readable contingencies
report in a couple of seconds and without any preparation.

They are built on the same IEEE39 New England grid as the investments demo in
``trunk/Demos/Investments``, so the two can be presented back to back as one story: here is the
N-1 risk, and here is the investment plan that removes it.

The build has four stages:

1. Take the standard IEEE39 base case and give every device a name a planner would recognise.
2. Set a coherent set of circuit ratings so that the base case is N-0 secure but a number of
   single outages are not, and give every circuit a short-term contingency rating.
3. Replace the contingency plan shipped with the source file with the plan this demo needs.
4. Run the study and print the report that the README documents.
"""
import os
from typing import List, Tuple

import numpy as np

import VeraGridEngine as gce
import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (
    ContingencyAnalysisDriver,
)
from VeraGridEngine.Simulations.ContingencyAnalysis.contingency_analysis_options import (
    ContingencyAnalysisOptions,
)
from VeraGridEngine.Simulations.ContingencyAnalysis.contingency_plan import (
    generate_automatic_contingency_plan,
)
from VeraGridEngine.enumerations import (
    ContingencyMethod,
    ContingencyOperationTypes,
    DeviceType,
)

SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT: str = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
SOURCE_GRID: str = os.path.join(REPO_ROOT, 'Grids_and_profiles', 'grids', 'IEEE39_1W.gridcal')
OUTPUT_N1: str = os.path.join(SCRIPT_DIR, 'Contingency_demo.veragrid')
OUTPUT_N2: str = os.path.join(SCRIPT_DIR, 'Contingency_demo_N2.veragrid')

# Operating voltage band used to check the base case. The source grid ships with 0.94/1.06.
VOLTAGE_MIN: float = 0.95
VOLTAGE_MAX: float = 1.05

# Ceiling applied to every generator voltage setpoint. The source case schedules one machine at
# 1.0636 pu, which sits outside the band above; 1.04 leaves a margin so that no bus lands exactly
# on a limit and gets reported through floating point noise alone.
VSET_MAX: float = 1.04

# Short-term rating multiplier applied to every circuit, i.e. the overload a control room will
# tolerate for the minutes it takes to redispatch. This has to be greater than 1.0: it is the
# threshold that separates the report's "Overload acceptable" verdict from "Overload not
# acceptable", and the device default of exactly 1.0 makes the acceptable verdict unreachable.
CONTINGENCY_FACTOR: float = 1.20

# Every circuit outside the demonstration set below is rated so that its worst single outage
# leaves it at this loading, which keeps it out of the report entirely.
SECURITY_MARGIN: float = 0.98

# Three area partition of the system, as area name -> the buses it contains. The split follows the
# topology: the western string of load buses with their units, the north eastern loop, and the
# south eastern pocket behind buses 26 to 29.
AREA_DEFINITIONS: List[Tuple[str, Tuple[int, ...]]] = [
    ("Area 1 - West", (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 30, 31, 32, 39)),
    ("Area 2 - North East", (15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 33, 34, 35, 36)),
    ("Area 3 - South East", (25, 26, 27, 28, 29, 37, 38)),
]

# The demonstration set, as branch index -> rating in MVA. The source file rates most circuits at
# a flat 600 or 900 MVA, which is far above anything the base case produces, so an untouched
# IEEE39 is almost entirely N-1 secure and the study would return a nearly empty report. These
# values are chosen against the measured flows: every one leaves its circuit below 90% in the
# intact network, and takes it past 100% for at least one credible outage. Together they spread
# the resulting violations across all four verdict bands the report can produce.
#
# This is what a planner's case actually looks like when they bring a problem to a meeting: a
# system that is secure everywhere except on the handful of corridors under discussion.
CIRCUIT_RATINGS: List[Tuple[int, float]] = [
    (45, 1000.0),   # L29-38, evacuation of the 830 MW unit at bus 38
    (13, 1400.0),   # L06-31, evacuation of the unit at bus 31
    (37, 650.0),    # L23-24
    (34, 720.0),    # L21-22
    (11, 620.0),    # L06-07
    (10, 680.0),    # L05-08
    (44, 500.0),    # L28-29
    (31, 460.0),    # L19-20
    (33, 600.0),    # L20-34
    (27, 560.0),    # L16-21
]


class MultiDeviceEventSpec:
    """
    One hand-picked common-mode event: a set of circuits, and optionally a generating unit, that a
    single physical failure would take out together. This is what makes an N-2 study different
    from running two N-1 cases, and it is the reason a contingency *group* rather than a single
    contingency is the unit of simulation.
    """
    __slots__ = ('name', 'category', 'line_names', 'generator_bus_names')

    def __init__(self,
                 name: str,
                 category: str,
                 line_names: List[str],
                 generator_bus_names: List[str]) -> None:
        """
        Constructor

        :param name: name shown in the report's ``Contingency`` column
        :param category: contingency group category
        :param line_names: names of the circuits lost in the event
        :param generator_bus_names: names of the buses whose generating unit is lost in the event
        """
        self.name: str = name
        self.category: str = category
        self.line_names: List[str] = line_names
        self.generator_bus_names: List[str] = generator_bus_names


# The curated N-2 set. Each entry is one physical failure, not two coincident ones. They are
# ordered as they are meant to be discussed: the two severe cases first, then the pair that only
# a common-mode study can find, then a moderate one, then the two that show what a clean answer
# and a structural answer look like.
CURATED_EVENTS: List[MultiDeviceEventSpec] = [
    MultiDeviceEventSpec(
        name="Common tower - Bus 06 western exits",
        category="common tower",
        line_names=["L05-06", "L06-07"],
        generator_bus_names=list(),
    ),
    MultiDeviceEventSpec(
        name="Unit and circuit - G39 with L09-39",
        category="combined",
        line_names=["L09-39"],
        generator_bus_names=["Bus 39"],
    ),
    MultiDeviceEventSpec(
        # Each of these two circuits is the other's worst single outage, so a study that only ever
        # opens one at a time reports both as merely uncomfortable. Opened together they are the
        # clearest illustration of what N-1 screening cannot see.
        name="Common tower - L21-22 with L23-24",
        category="common tower",
        line_names=["L21-22", "L23-24"],
        generator_bus_names=list(),
    ),
    MultiDeviceEventSpec(
        name="Common tower - Bus 04 exits",
        category="common tower",
        line_names=["L04-05", "L04-14"],
        generator_bus_names=list(),
    ),
    MultiDeviceEventSpec(
        # Bus 22 carries only three circuits, so losing the busbar separates it and the unit at
        # bus 35 from the rest of the system. Nothing overloads, because the problem is not a
        # thermal one: this is what a structural failure looks like in the results.
        name="Busbar fault - Bus 22",
        category="busbar",
        line_names=["L21-22", "L22-23", "L22-35"],
        generator_bus_names=list(),
    ),
    MultiDeviceEventSpec(
        # Two circuits far enough apart that no single failure could take both, included as the
        # control case: the study is meant to return nothing for it.
        name="Independent pair - L03-18 with L25-26",
        category="double",
        line_names=["L03-18", "L25-26"],
        generator_bus_names=list(),
    ),
]


def build_power_flow_options() -> gce.PowerFlowOptions:
    """
    Power flow settings used for every contingency evaluation. Newton-Raphson without reactive
    control loops keeps each of the ~55 solves fast and, more importantly, deterministic in front
    of an audience.

    :return: the power flow options
    """
    return gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                tolerance=1e-6,
                                max_iter=40,
                                control_q=False,
                                retry_with_other_methods=False,
                                verbose=0)


def build_contingency_options(pf_options: gce.PowerFlowOptions) -> ContingencyAnalysisOptions:
    """
    Contingency study settings. The full AC power flow method is used rather than a linear screen,
    because the demo is about the quality of the answer rather than the speed of it, and at this
    size the difference is a couple of seconds.

    SRAP is switched off: the report still fills its ``SRAP availability`` column from the circuit
    ratings, which is enough to explain what a remedial action scheme would be asked to do,
    without introducing a second mechanism to explain in the same sitting.

    :param pf_options: the power flow options to solve each contingency with
    :return: the contingency analysis options
    """
    return ContingencyAnalysisOptions(pf_options=pf_options,
                                      contingency_method=ContingencyMethod.PowerFlow,
                                      use_srap=False,
                                      contingency_deadband=0.0)


def load_base_case() -> MultiCircuit:
    """
    Load the standard IEEE39 New England case and make it presentable.

    The source file is a one-week time series whose snapshot state already holds the textbook
    dispatch, so the profiles are simply dropped rather than sampled: the snapshot is both the
    recognisable operating point and the one that keeps the delivered file from ever triggering a
    time series run by accident.

    Everything in the source is named ``bus 0``, ``branch 7`` and so on. Since the whole point of
    the demo is to read a report out loud, buses are renumbered to the usual 1-based IEEE39
    convention and every circuit and unit is named after the buses it connects.

    :return: the renamed snapshot grid, with no time profiles
    """
    grid: MultiCircuit = gce.open_file(SOURCE_GRID)
    grid.delete_profiles()

    for i, bus in enumerate(grid.get_buses()):
        bus.name = f"Bus {i + 1:02d}"
        bus.Vmin = VOLTAGE_MIN
        bus.Vmax = VOLTAGE_MAX

    for line in grid.get_lines():
        bus_from: int = int(line.bus_from.name.split()[1])
        bus_to: int = int(line.bus_to.name.split()[1])
        line.name = f"L{bus_from:02d}-{bus_to:02d}"

    for generator in grid.get_generators():
        generator.name = f"G{int(generator.bus.name.split()[1]):02d}"

        # Keep every scheduled voltage inside the band the base case is checked against, so that
        # the demo never opens on a voltage violation that no outage caused.
        generator.Vset = min(max(generator.Vset, VOLTAGE_MIN), VSET_MAX)

    assign_areas(grid=grid)

    return grid


def assign_areas(grid: MultiCircuit) -> None:
    """
    Replace the areas that ship with the source file with a three area partition of the system.

    The source carries forty areas, one per bus, each named after a random identifier. Those names
    are what the report prints in its ``Area 1`` and ``Area 2`` columns, which makes two of the
    twenty columns unreadable. A conventional geographic split makes them useful instead: the
    columns then say which corner of the system a violation sits in, and let a planner filter the
    report down to the interface they are responsible for.

    :param grid: the grid, modified in place
    """
    grid.areas.clear()

    for area_name, bus_numbers in AREA_DEFINITIONS:
        area = dev.Area(name=area_name)
        grid.add_area(area)

        for bus in grid.get_buses():
            if int(bus.name.split()[1]) in bus_numbers:
                bus.area = area
            else:
                pass


def apply_operational_ratings(grid: MultiCircuit) -> None:
    """
    Apply the demo's circuit ratings and give every circuit a short-term contingency rating.

    :param grid: the grid, modified in place
    """
    branches = grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)

    for branch_idx, rating in CIRCUIT_RATINGS:
        branches[branch_idx].rate = rating

    # The short-term rating is what the report compares against to decide whether a post
    # contingency overload is tolerable, so it has to be set on every circuit and not only on the
    # ones expected to overload.
    for branch in branches:
        branch.contingency_factor = CONTINGENCY_FACTOR


def compute_worst_contingency_flows(grid: MultiCircuit,
                                    options: ContingencyAnalysisOptions) -> np.ndarray:
    """
    Solve every contingency in the plan and return, per circuit, the largest flow seen across all
    of them.

    Ratings do not enter the power flow at all, they are only thresholds the report compares
    against, so these flows can be measured once and then used to choose the ratings.

    :param grid: the grid to study, with its contingency plan already in place
    :param options: the contingency analysis options
    :return: array of worst contingency flows in MVA, one per circuit
    """
    driver = ContingencyAnalysisDriver(grid=grid, options=options)
    driver.run()

    return np.abs(driver.results.Sf).max(axis=0)


def harden_untargeted_circuits(grid: MultiCircuit, worst_flows: np.ndarray) -> int:
    """
    Raise the rating of every circuit outside the demonstration set until its worst single outage
    no longer overloads it.

    Without this the report runs to some forty five rows, most of them circuits drifting a few
    percent past a rating the source file chose arbitrarily. Those rows are not wrong, but they
    bury the ones worth discussing, and a report nobody can read through in a meeting is a report
    that does not get read.

    :param grid: the grid, modified in place
    :param worst_flows: worst contingency flow per circuit, from
                        :func:`compute_worst_contingency_flows`
    :return: the number of circuits whose rating was raised
    """
    targeted = set(branch_idx for branch_idx, _ in CIRCUIT_RATINGS)
    branches = grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)
    n_raised: int = 0

    for i, branch in enumerate(branches):
        if i in targeted:
            pass
        else:
            # Round up to the next 10 MVA so the delivered file carries ratings that look like
            # ratings rather than like the output of a solver.
            required: float = float(np.ceil(worst_flows[i] / SECURITY_MARGIN / 10.0) * 10.0)

            if required > branch.rate:
                branch.rate = required
                n_raised += 1
            else:
                pass

    return n_raised


def clear_contingency_plan(grid: MultiCircuit) -> None:
    """
    Remove the contingency plan that ships with the source file.

    ``IEEE39_1W.gridcal`` already carries a complete 46 group N-1 plan. Adding a plan on top of it
    silently doubles every group, and the report then shows each violation twice.

    :param grid: the grid, modified in place
    """
    grid.contingencies.clear()
    grid.contingency_groups.clear()


def add_circuit_outages(grid: MultiCircuit) -> int:
    """
    Add the outage of every circuit as its own contingency group.

    This is the same call the GUI makes behind ``Events -> Initialize contingencies``, so the file
    can be reproduced by hand in front of the client if the question comes up.

    :param grid: the grid, modified in place
    :return: the number of groups added
    """
    contingencies, groups = generate_automatic_contingency_plan(
        grid=grid,
        k=1,
        consider_branches=True,
        branch_types=[DeviceType.LineDevice],
        consider_injections=False,
    )

    for group in groups:
        grid.add_contingency_group(group)

    for contingency in contingencies:
        grid.add_contingency(contingency)

    return len(groups)


def add_unit_trips(grid: MultiCircuit) -> int:
    """
    Add the trip of every generating unit as its own contingency group.

    These are built here rather than through ``generate_automatic_contingency_plan``, because that
    route models an injection contingency as a percentage of scheduled power and the engine
    applies it as ``P *= value / 100``. At the default of 100 that is a multiplication by one, so
    the generated contingencies do nothing at all, and the value that would model a full trip,
    zero, makes the revert step divide by zero. Switching the unit off with an ``Active`` event
    avoids both problems and reverts cleanly.

    The slack machine is skipped: it is the one that absorbs the imbalance left by every other
    outage, so tripping it is a study about the reference rather than about the network.

    :param grid: the grid, modified in place
    :return: the number of groups added
    """
    n_added: int = 0

    for generator in grid.get_generators():
        if generator.bus.is_slack:
            pass
        else:
            group = dev.ContingencyGroup(name=f"Unit trip {generator.name}", category='generator')
            grid.add_contingency_group(group)
            grid.add_contingency(dev.Contingency(device=generator,
                                                 name=generator.name,
                                                 code=generator.code,
                                                 prop=ContingencyOperationTypes.Active,
                                                 value=0,
                                                 group=group))
            n_added += 1

    return n_added


def find_line(grid: MultiCircuit, line_name: str) -> dev.Line:
    """
    Resolve a circuit by name.

    :param grid: the grid to search
    :param line_name: the name to look for
    :return: the matching line
    """
    for line in grid.get_lines():
        if line.name == line_name:
            return line
        else:
            pass

    raise ValueError(f"Line '{line_name}' not found in the grid")


def find_generator_at_bus(grid: MultiCircuit, bus_name: str) -> dev.Generator:
    """
    Resolve the generating unit connected to a given bus.

    :param grid: the grid to search
    :param bus_name: the name of the bus the unit sits on
    :return: the matching generator
    """
    for generator in grid.get_generators():
        if generator.bus.name == bus_name:
            return generator
        else:
            pass

    raise ValueError(f"No generator found at bus '{bus_name}'")


def add_curated_events(grid: MultiCircuit) -> int:
    """
    Add the hand-picked common-mode events.

    The engine can enumerate every N-2 pair automatically, but on this grid that is more than two
    thousand groups, which is neither presentable nor informative: the overwhelming majority are
    pairs of unrelated circuits that no single failure would ever take out together. A short list
    of events that correspond to real failure modes says considerably more.

    :param grid: the grid, modified in place
    :return: the number of groups added
    """
    for spec in CURATED_EVENTS:
        group = dev.ContingencyGroup(name=spec.name, category=spec.category)
        grid.add_contingency_group(group)

        # Every device in the event goes into the same group, which is what makes the engine open
        # all of them within a single power flow rather than one at a time.
        for line_name in spec.line_names:
            line = find_line(grid=grid, line_name=line_name)
            grid.add_contingency(dev.Contingency(device=line,
                                                 name=line.name,
                                                 code=line.code,
                                                 prop=ContingencyOperationTypes.Active,
                                                 value=0,
                                                 group=group))

        for bus_name in spec.generator_bus_names:
            generator = find_generator_at_bus(grid=grid, bus_name=bus_name)
            grid.add_contingency(dev.Contingency(device=generator,
                                                 name=generator.name,
                                                 code=generator.code,
                                                 prop=ContingencyOperationTypes.Active,
                                                 value=0,
                                                 group=group))

    return len(CURATED_EVENTS)


def report_base_case(grid: MultiCircuit, pf_options: gce.PowerFlowOptions) -> None:
    """
    Solve and describe the intact network. The demo only works if this is clean, so it is checked
    at build time rather than discovered in the meeting.

    :param grid: the grid to solve
    :param pf_options: the power flow options
    """
    driver = gce.PowerFlowDriver(grid=grid, options=pf_options)
    driver.run()

    loading = np.abs(driver.results.loading)
    voltage = np.abs(driver.results.voltage)
    n_overload: int = int((loading > 1.0).sum())
    n_voltage: int = int(((voltage < VOLTAGE_MIN) | (voltage > VOLTAGE_MAX)).sum())

    print(f"  base case: converged={bool(driver.results.converged)}, "
          f"overloads={n_overload}, buses out of band={n_voltage}")
    print(f"  highest loading {loading.max() * 100:.1f}%, "
          f"voltage range {voltage.min():.4f} - {voltage.max():.4f} pu")


def print_report(grid: MultiCircuit, options: ContingencyAnalysisOptions) -> int:
    """
    Run the contingency study and print the report the way the GUI shows it.

    :param grid: the grid to study
    :param options: the contingency analysis options
    :return: the number of report rows
    """
    driver = ContingencyAnalysisDriver(grid=grid, options=options)
    driver.run()

    data = driver.results.report.get_data()
    n_rows: int = int(data.shape[0]) if data.size else 0

    print(f"  groups {grid.get_contingency_groups_number()}, report rows {n_rows}")

    if n_rows > 0:
        print(f"  {'Monitored':<10} {'Contingency':<38} {'base%':>7} {'post%':>7} "
              f"{'Overload':<24} {'SRAP availability':<20}")

        # Sort by severity, which is the order the violations get discussed in. Column 14 is the
        # post contingency loading in per unit.
        severity = np.array([float(data[k, 14]) for k in range(n_rows)], dtype=float)
        for k in np.argsort(-severity):
            print(f"  {data[k, 5]:<10} {data[k, 6]:<38} {float(data[k, 13]) * 100:>7.1f} "
                  f"{float(data[k, 14]) * 100:>7.1f} {data[k, 16]:<24} {data[k, 17]:<20}")
    else:
        print("  the network is secure for every contingency in the plan")

    return n_rows


def main() -> None:
    """
    Build, check and save both demo files.
    """
    pf_options = build_power_flow_options()
    options = build_contingency_options(pf_options=pf_options)

    # --- Part 1: every circuit and every unit, one at a time ---------------------------------
    print("Part 1 - N-1 circuit outages and unit trips")
    grid_n1 = load_base_case()
    grid_n1.name = "Contingency demo - IEEE39 New England N-1"

    clear_contingency_plan(grid=grid_n1)
    n_circuits: int = add_circuit_outages(grid=grid_n1)
    n_units: int = add_unit_trips(grid=grid_n1)
    print(f"  contingency plan: {n_circuits} circuit outages, {n_units} unit trips")

    # Measure first, then rate: the ratings are chosen so that the only circuits able to appear in
    # the report are the ones this demo is about.
    worst_flows = compute_worst_contingency_flows(grid=grid_n1, options=options)
    apply_operational_ratings(grid=grid_n1)
    n_raised: int = harden_untargeted_circuits(grid=grid_n1, worst_flows=worst_flows)
    print(f"  ratings: {len(CIRCUIT_RATINGS)} in the demonstration set, {n_raised} raised to be "
          f"N-1 secure")
    report_base_case(grid=grid_n1, pf_options=pf_options)

    print_report(grid=grid_n1, options=options)
    gce.save_file(grid_n1, OUTPUT_N1)
    print(f"  saved {OUTPUT_N1}")

    # --- Part 2: hand-picked common-mode events -----------------------------------------------
    print("\nPart 2 - curated N-2 common-mode events")
    grid_n2 = load_base_case()
    grid_n2.name = "Contingency demo - IEEE39 New England N-2"
    apply_operational_ratings(grid=grid_n2)

    # Hardened against the same single outages as part 1, so that whatever appears in this report
    # is by construction a violation that N-1 screening does not find.
    harden_untargeted_circuits(grid=grid_n2, worst_flows=worst_flows)

    clear_contingency_plan(grid=grid_n2)
    n_events: int = add_curated_events(grid=grid_n2)
    print(f"  contingency plan: {n_events} common-mode events")

    print_report(grid=grid_n2, options=options)
    gce.save_file(grid_n2, OUTPUT_N2)
    print(f"  saved {OUTPUT_N2}")


if __name__ == "__main__":
    main()
