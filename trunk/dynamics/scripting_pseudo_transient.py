# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import VeraGridEngine.api as gce
import numpy as np
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.templates_common_functions import set_rms_model
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae


def build_grid() -> gce.MultiCircuit:
    grid = gce.MultiCircuit(Sbase=100.0, fbase=50.0)

    bus0 = gce.Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10.0)
    initialize_bus_rms(bus0, vf=grid.var_factory)
    initialize_bus_rms(bus1, vf=grid.var_factory)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line = gce.Line(
        name="Line0-1",
        bus_from=bus0,
        bus_to=bus1,
        r=0.029585798816568046,
        x=0.07100591715976332,
        b=0.03,
        rate=900.0,
    )
    grid.add_line(line)

    load = gce.Load(name="Load1", P=9.999999, Q=0.999999)
    grid.add_load(bus=bus1, api_obj=load)

    gen = gce.Generator(
        name="Gen0",
        P=10.0,
        vset=1.0,
        Snom=900.0,
        r1=0.3,
        x1=0.86138701,
        freq=50.0,
    )
    grid.add_generator(bus=bus0, api_obj=gen)

    if line.rms_model.empty():
        set_rms_model(device=line, model=get_line_rms_template(grid.var_factory, name=line.name).block, var_factory=grid.var_factory)
    if load.rms_model.empty():
        set_rms_model(device=load, model=get_load_rms_template(grid.var_factory, name=load.name).block, var_factory=grid.var_factory)
    if gen.rms_model.empty():
        set_rms_model(
            device=gen,
            model=get_complete_generator_template_rms(grid.var_factory, name=gen.name).block,
            var_factory=grid.var_factory,
        )

    group = gce.RmsEventsGroup(name="BaseCase")
    grid.add_rms_events_group(group)

    return grid


def run_validation() -> None:
    grid = build_grid()

    pf_options = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        distributed_slack=False,
    )
    pf_results = gce.power_flow(grid, options=pf_options)

    print(f"Power flow converged: {pf_results.converged}")

    rms_options = gce.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        integration_method=gce.DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=gce.RmsInitializationMethod.PseudoTransient,
        max_iter=1000,
        tolerance=1e-8,
        verbose=1,
    )

    problem = RmsProblemDae(
        grid=grid,
        options=rms_options,
        pf_results=pf_results,
    )
    problem.set_events_group(grid.rms_events_groups[0])

    x0 = problem.get_x0()
    if x0.size == 0:
        raise RuntimeError("Pseudo-transient initialization produced an empty state vector")
    if not np.all(np.isfinite(x0)):
        raise RuntimeError("Pseudo-transient initialization produced non-finite values")

    print(f"Initialized variable count: {x0.size}")
    print(f"x0 infinity norm: {np.linalg.norm(x0, np.inf):.3e}")

    print("Pseudo-transient initialization validation passed")


if __name__ == "__main__":
    run_validation()
