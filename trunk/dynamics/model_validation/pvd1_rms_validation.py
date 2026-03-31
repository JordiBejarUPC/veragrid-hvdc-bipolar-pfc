# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

import VeraGridEngine.api as vge
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.pvd1_rms_template import get_pvd1_rms_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup
def build_constant_pq_generator_model(vf, name: str) -> Block:
    vm = vf.add_var(f"Vm_{name}", VarPowerFlowRefferenceType.Vm)
    va = vf.add_var(f"Va_{name}", VarPowerFlowRefferenceType.Va)
    p = vf.add_var(f"P_{name}")
    q = vf.add_var(f"Q_{name}")
    p0 = vf.add_var(f"P0_{name}")
    q0 = vf.add_var(f"Q0_{name}")

    return Block(
        algebraic_eqs=[p - p0, q - q0],
        algebraic_vars=[p, q],
        in_vars=[vm, va],
        init_eqs={p0: p, q0: q},
        event_dict={p0: vf.add_const(None), q0: vf.add_const(None)},
        external_mapping={
            VarPowerFlowRefferenceType.Vm: vm,
            VarPowerFlowRefferenceType.Va: va,
            VarPowerFlowRefferenceType.P: p,
            VarPowerFlowRefferenceType.Q: q,
        },
        out_vars=[p, q],
    )


def create_grid() -> vge.MultiCircuit:
    grid = vge.MultiCircuit(name="PVD1 RMS validation", Sbase=100.0)

    bus_slack = vge.Bus(name="B1", Vnom=230.0, is_slack=True)
    bus_pv = vge.Bus(name="B2", Vnom=230.0)

    grid.add_bus(bus_slack)
    grid.add_bus(bus_pv)

    line = vge.Line(name="L12", bus_from=bus_slack, bus_to=bus_pv, r=0.02, x=0.08, b=0.02, rate=200.0)
    grid.add_line(line)

    gen_slack = vge.Generator(name="G_slack", P=80.0, vset=1.0)
    grid.add_generator(bus=bus_slack, api_obj=gen_slack)

    gen_pv = vge.Generator(name="PV_PVD1", P=-80.0, vset=1.01)
    grid.add_generator(bus=bus_pv, api_obj=gen_pv)

    return grid


def run_pf(grid: vge.MultiCircuit):
    pf_options = vge.PowerFlowOptions(
        solver_type=vge.SolverType.NR,
        tolerance=1e-8,
        max_iter=100,
        verbose=False,
    )
    return vge.power_flow(grid=grid, options=pf_options)


def initialize_rms_models(grid: vge.MultiCircuit):
    vf = grid.rms_var_factory

    for bus in grid.buses:
        initialize_bus_rms(bus=bus, vf=vf)

    for line in grid.lines:
        line_model = get_line_rms_template(vfactory=vf, name=f"Line_{line.name}").block
        line_model.connect([line_model.in_vars[0], line_model.in_vars[1]], [line.bus_from.rms_model.out_vars[0], line.bus_from.rms_model.out_vars[1]])
        line_model.connect([line_model.in_vars[2], line_model.in_vars[3]], [line.bus_to.rms_model.out_vars[0], line.bus_to.rms_model.out_vars[1]])
        line_model.unify_blocks()
        line.rms_model = line_model

    slack_gen = grid.generators[0]
    slack_model = build_constant_pq_generator_model(vf=vf, name=f"Const_{slack_gen.name}")
    slack_model.connect([slack_model.in_vars[0], slack_model.in_vars[1]], [slack_gen.bus.rms_model.out_vars[0], slack_gen.bus.rms_model.out_vars[1]])
    slack_model.unify_blocks()
    slack_gen.rms_model = slack_model

    pv_gen = grid.generators[1]
    pvd1_model = get_pvd1_rms_template(vfactory=vf, name=f"PVD1_{pv_gen.name}").block
    pvd1_model.connect([pvd1_model.in_vars[0], pvd1_model.in_vars[1]], [pv_gen.bus.rms_model.out_vars[0], pv_gen.bus.rms_model.out_vars[1]])
    pvd1_model.unify_blocks()
    pv_gen.rms_model = pvd1_model


def run_rms(grid: vge.MultiCircuit, pf_results):
    events_group = RmsEventsGroup(name="pvd1_base_case")
    grid.add_rms_events_group(events_group)

    rms_options = vge.RmsOptions(
        simulation_time=1.0,
        time_step=0.005,
        max_iter=30,
        tolerance=1e-6,
        integration_method=vge.DynamicIntegrationMethod.DaeBackEuler,
    )

    rms_driver = vge.RmsSimulationDriver(
        grid=grid,
        options=rms_options,
        pf_results=pf_results,
        engine=vge.EngineType.VeraGrid,
    )
    rms_driver.run()
    return rms_driver.results


def main() -> int:
    grid = create_grid()

    pf_results = run_pf(grid=grid)
    print(f"Power flow converged: {pf_results.converged}")
    if not pf_results.converged:
        return 1

    initialize_rms_models(grid=grid)
    results = run_rms(grid=grid, pf_results=pf_results)
    well_init = bool(results.well_initialized.size > 0 and results.well_initialized.all())
    converged = bool(results.converged.size > 0 and results.converged.all())
    print(f"RMS well initialized: {results.well_initialized}")
    print(f"RMS converged: {results.converged}")

    return 0 if (well_init and converged) else 1


if __name__ == "__main__":
    raise SystemExit(main())
