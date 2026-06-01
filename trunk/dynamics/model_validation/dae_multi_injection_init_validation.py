# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
DAE initialization validation with multiple injection devices on one bus.

This script builds a small but non-trivial AC grid where one bus has
multiple injection devices (generator + two loads), then runs:
1) power flow,
2) DAE RMS initialization,
3) a short dynamic simulation.

It prints initialization residual metrics so we can validate the
multi-device bus initialization logic in `RmsProblemDae`.
"""

from __future__ import annotations

import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

import VeraGridEngine.api as gce
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod, VarPowerFlowReferenceType
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup


def create_grid() -> gce.MultiCircuit:
    grid = gce.MultiCircuit(name="DAE Multi-Injection Validation", Sbase=100.0, fbase=50.0)

    bus0 = gce.Bus(name="Bus0", Vnom=110.0, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=110.0)
    bus2 = gce.Bus(name="Bus2", Vnom=110.0)
    bus3 = gce.Bus(name="Bus3", Vnom=110.0)

    for bus in (bus0, bus1, bus2, bus3):
        grid.add_bus(bus)

    # Meshed network for a proper PF/RMS case.
    grid.add_line(gce.Line(name="L01", bus_from=bus0, bus_to=bus1, r=0.02, x=0.06, b=0.02, rate=250.0))
    grid.add_line(gce.Line(name="L12", bus_from=bus1, bus_to=bus2, r=0.025, x=0.07, b=0.02, rate=250.0))
    grid.add_line(gce.Line(name="L23", bus_from=bus2, bus_to=bus3, r=0.02, x=0.06, b=0.02, rate=250.0))
    grid.add_line(gce.Line(name="L30", bus_from=bus3, bus_to=bus0, r=0.03, x=0.08, b=0.02, rate=250.0))
    grid.add_line(gce.Line(name="L13", bus_from=bus1, bus_to=bus3, r=0.02, x=0.05, b=0.015, rate=250.0))

    # Slack machine.
    gen_slack = gce.Generator(name="G_slack", P=75.0, vset=1.00, Snom=240.0)
    gen_slack_b = gce.Generator(name="G_slack_b", P=20.0, vset=1.00, Snom=60.0)
    grid.add_generator(bus=bus0, api_obj=gen_slack)
    grid.add_generator(bus=bus0, api_obj=gen_slack_b)

    # This bus has multiple injection devices by design:
    #  - one generator
    #  - two loads
    gen_bus1 = gce.Generator(name="G_bus1", P=35.0, vset=1.01, Snom=120.0)
    load_bus1_a = gce.Load(name="L_bus1_a", P=28.0, Q=9.0)
    load_bus1_b = gce.Load(name="L_bus1_b", P=16.0, Q=5.0)
    grid.add_generator(bus=bus1, api_obj=gen_bus1)
    grid.add_load(bus=bus1, api_obj=load_bus1_a)
    grid.add_load(bus=bus1, api_obj=load_bus1_b)

    # Remaining demand elsewhere.
    grid.add_load(bus=bus2, api_obj=gce.Load(name="L_bus2", P=40.0, Q=12.0))
    grid.add_load(bus=bus3, api_obj=gce.Load(name="L_bus3", P=32.0, Q=10.0))

    return grid


def setup_rms_models(grid: gce.MultiCircuit) -> None:
    for bus in grid.buses:
        initialize_bus_rms(bus, vf=grid.var_factory)

    for gen in grid.get_generators():
        gen_mdl = get_genrow1_rms_template(grid.var_factory, name=f"Gen_{gen.name}").block
        grid.var_factory.add_connections([gen_mdl.in_vars[0]], [gen.bus.rms_model.out_vars[0]])
        grid.var_factory.add_connections([gen_mdl.in_vars[1]], [gen.bus.rms_model.out_vars[1]])
        gen_mdl.unify_blocks()

        wrapper = Block(children=[gen_mdl])
        wrapper.external_mapping.update({VarPowerFlowReferenceType.P: gen_mdl.out_vars[0]})
        wrapper.external_mapping.update({VarPowerFlowReferenceType.Q: gen_mdl.out_vars[1]})
        wrapper.unify_blocks()
        gen.rms_model = wrapper

    for load in grid.get_loads():
        p_pu = float(load.P) / grid.Sbase
        q_pu = float(load.Q) / grid.Sbase
        load_mdl = ZIPLoadBuild(grid.var_factory, name=f"Load_{load.name}", Pl0=-p_pu, Ql0=-q_pu).block
        for var, const in load_mdl.event_dict.items():
            if var.name == "V0" and const.value is None:
                const.value = 1.0
        grid.var_factory.add_connections([load_mdl.in_vars[0]], [load.bus.rms_model.out_vars[0]])
        load_mdl.unify_blocks()
        load.rms_model = load_mdl

    for line in grid.lines:
        line_mdl = get_line_rms_template(grid.var_factory, name=f"Line_{line.name}").block
        grid.var_factory.add_connections([line_mdl.in_vars[0]], [line.bus_from.rms_model.out_vars[0]])
        grid.var_factory.add_connections([line_mdl.in_vars[1]], [line.bus_from.rms_model.out_vars[1]])
        grid.var_factory.add_connections([line_mdl.in_vars[2]], [line.bus_to.rms_model.out_vars[0]])
        grid.var_factory.add_connections([line_mdl.in_vars[3]], [line.bus_to.rms_model.out_vars[1]])
        line_mdl.unify_blocks()
        line.rms_model = line_mdl


def print_buses_with_many_injections(grid: gce.MultiCircuit, min_devices: int = 2) -> None:
    by_bus = {bus: [] for bus in grid.buses}
    for dev in grid.get_injection_devices_iter():
        if dev.bus is not None:
            by_bus[dev.bus].append(dev)

    print("\nBuses with multiple injection devices:")
    found = False
    for bus, devs in by_bus.items():
        if len(devs) >= min_devices:
            found = True
            labels = ", ".join(f"{d.device_type.value}:{d.name}" for d in devs)
            print(f"  - {bus.name}: {len(devs)} devices -> {labels}")
    if not found:
        print("  - none")


def print_slack_gen_weights(grid: gce.MultiCircuit) -> None:
    slack_gens = [gen for gen in grid.get_generators() if gen.bus is not None and gen.bus.is_slack]
    if len(slack_gens) == 0:
        return
    total_snom = sum(float(getattr(gen, "Snom", 0.0)) for gen in slack_gens)
    if total_snom <= 0.0:
        total_snom = float(len(slack_gens))

    print("\nSlack-bus generator Snom weights (expected residual split):")
    for gen in slack_gens:
        snom = float(getattr(gen, "Snom", 0.0))
        if snom <= 0.0:
            snom = 1.0
        print(f"  - {gen.name} at {gen.bus.name}: Snom={snom:.3f}, weight={snom / total_snom:.6f}")


def print_pf_bus_power_closure(grid: gce.MultiCircuit, pf_results) -> None:
    bus_idx = {bus: i for i, bus in enumerate(grid.buses)}
    branch_sum = np.zeros(len(grid.buses), dtype=complex)

    branches = list(grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True))
    for br, sf, st in zip(branches, pf_results.Sf / grid.Sbase, pf_results.St / grid.Sbase):
        branch_sum[bus_idx[br.bus_from]] += sf
        branch_sum[bus_idx[br.bus_to]] += st

    sbus = pf_results.Sbus / grid.Sbase
    res = branch_sum - sbus
    worst = int(np.argmax(np.abs(res)))
    print("\nPF bus power closure check (branch terminal sum - Sbus):")
    print(f"  max|res| = {np.max(np.abs(res)):.6e} at bus {grid.buses[worst].name}")


def set_zip_v0_from_pf(grid: gce.MultiCircuit, pf_results) -> None:
    bus_idx = {bus: i for i, bus in enumerate(grid.buses)}
    for load in grid.get_loads():
        mdl = load.rms_model
        if mdl is None:
            continue
        vm0 = float(np.abs(pf_results.voltage[bus_idx[load.bus]]))
        for var, const in mdl.event_dict.items():
            if var.name == "V0":
                const.value = vm0


def print_init_residual(problem: RmsProblemDae, tol: float = 1e-6) -> None:
    x0 = problem.get_x0()
    dx0 = np.zeros(problem.get_diff_var_number(), dtype=float)

    state_res = np.array([], dtype=float)
    if problem.get_states_number() > 0:
        try:
            state_res = np.asarray(problem.rhs_state(x0, dx0), dtype=float)
        except ValueError:
            state_res = np.array([], dtype=float)
    algeb_res = np.asarray(problem.rhs_algebraic(x0, dx0), dtype=float)
    rhs = np.r_[state_res, algeb_res]

    max_abs = float(np.max(np.abs(rhs))) if rhs.size > 0 else 0.0
    print("\nInitialization consistency check at (x0, dx=0):")
    print(f"  max|residual| = {max_abs:.6e}, tol = {tol:.1e}, ok = {max_abs <= tol}")


def main() -> None:
    print("=" * 72)
    print("DAE MULTI-INJECTION INITIALIZATION VALIDATION")
    print("=" * 72)

    grid = create_grid()
    print(f"Grid: {len(grid.buses)} buses, {len(grid.lines)} lines, {len(grid.generators)} generators, {len(grid.loads)} loads")
    print_buses_with_many_injections(grid=grid, min_devices=2)
    print_slack_gen_weights(grid=grid)

    setup_rms_models(grid)

    pf_options = gce.PowerFlowOptions(tolerance=1e-9)
    pf_results = gce.power_flow(grid, options=pf_options)
    print(f"\nPower flow converged: {pf_results.converged}")
    if not pf_results.converged:
        raise RuntimeError("Power flow did not converge; cannot validate DAE initialization.")

    print_pf_bus_power_closure(grid=grid, pf_results=pf_results)
    set_zip_v0_from_pf(grid=grid, pf_results=pf_results)

    options = RmsOptions(
        time_step=0.001,
        simulation_time=0.02,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=100,
        verbose=0,
    )

    problem = RmsProblemDae(grid=grid, options=options, pf_results=pf_results)
    problem.set_events_group(RmsEventsGroup(name="default"))
    print_init_residual(problem=problem, tol=1e-6)

    solver = BackEulerImplicitIntegration(
        problem=problem,
        t0=0.0,
        t_end=options.simulation_time,
        h=options.time_step,
        max_iter=options.max_iter,
    )
    _, _, well_initialized, converged = solver.simulate()

    print("\nDynamic run status:")
    print(f"  well_initialized = {well_initialized}")
    print(f"  converged = {converged}")


if __name__ == "__main__":
    main()
