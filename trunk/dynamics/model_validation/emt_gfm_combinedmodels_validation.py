#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model

from emt_gfm_aggregated_model import build_emt_gfm_aggregated_model


def create_grid() -> tuple[vge.MultiCircuit, vge.Generator, vge.Generator, vge.Load]:
    grid = vge.MultiCircuit(name="EMT GFM aggregated validation", Sbase=100.0, fbase=50.0)

    # Exactly the same grid as rms_gfm_combinedmodels.py
    bus1_ac = vge.Bus(name="Bus 1 (AC)", Vnom=230.0, is_slack=True)
    bus3_ac = vge.Bus(name="Bus 1_1 (AC)", Vnom=230.0)
    bus4_ac = vge.Bus(name="Bus 4 (AC)", Vnom=230.0)
    grid.add_bus(bus1_ac)
    grid.add_bus(bus3_ac)
    grid.add_bus(bus4_ac)

    gen_slack = vge.Generator(name="Generator", P=10.0, vset=0.98)
    gen_gfm = vge.Generator(name="GFM Generator", P=4.0, vset=1.00)
    ac_load = vge.Load(name="AC Load", P=3.0, Q=0.0)

    line13 = vge.Line(
        name="Line13",
        bus_from=bus3_ac,
        bus_to=bus1_ac,
        rate=100.0,
        r=0.01,
        x=0.05,
        b=0.0,
    )
    line34 = vge.Line(
        name="Line 3-4",
        bus_from=bus3_ac,
        bus_to=bus4_ac,
        rate=100.0,
        r=0.02,
        x=0.08,
        b=0.0,
    )

    grid.add_generator(bus=bus1_ac, api_obj=gen_slack)
    grid.add_generator(bus=bus3_ac, api_obj=gen_gfm)
    grid.add_load(bus=bus4_ac, api_obj=ac_load)
    grid.add_line(line13)
    grid.add_line(line34)
    grid.apply_all_branch_types()

    return grid, gen_slack, gen_gfm, ac_load


def main() -> None:
    grid, gen_slack, gen_gfm, load_pcc = create_grid()

    pf_opts = vge.PowerFlowOptions(solver_type=vge.SolverType.NR, tolerance=1e-6, max_iter=30, verbose=0)
    pf = vge.power_flow(grid, pf_opts)
    print(f"Power flow converged: {pf.converged}")
    pf_for_emt = pf if pf.converged else None

    for bus in grid.buses:
        get_bus_emt_template(grid=grid, bus=bus)

    gfm_model = build_emt_gfm_aggregated_model(vf=grid.var_factory, name="vsc_gfm_park")
    set_emt_model(gen_gfm, gfm_model, grid.var_factory)

    for ln in grid.lines:
        line_model = get_pi_line_emt_template(vf=grid.var_factory).block
        set_emt_model(ln, line_model, grid.var_factory)

    gen_model = get_simple_generator_emt_template(vf=grid.var_factory).block
    set_emt_model(gen_slack, gen_model, grid.var_factory)

    load_model = get_load_ZIP_emt_template(vf=grid.var_factory).block
    set_emt_model(load_pcc, load_model, grid.var_factory)

    emt_opts = EmtOptions(
        time_step=1e-4,
        simulation_time=0.2,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=EmtInitializationMethod.Auto,
        init_newton_max_iter=40,
        verbose=1,
    )

    driver = EmtSimulationDriver(grid=grid, options=emt_opts, pf_results=pf_for_emt)
    driver.run()
    print("EMT run finished")


if __name__ == "__main__":
    main()
