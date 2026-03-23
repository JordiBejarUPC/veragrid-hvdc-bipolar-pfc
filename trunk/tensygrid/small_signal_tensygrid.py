# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Small Signal Analysis for Phasor-based RMS Grid.

This script creates the phasor problem manually and injects it into the SmallSignalStabilityRmsDriver.
"""
#import sys
#import numpy as np
from PolynomialMatrixBuilder import PolynomialMatrixBuilder
#from matplotlib import pyplot as plt
import VeraGridEngine.api as vge


def define_problem():

    # ===================================================================
    # CREATE GRID (Same as phasor validation)
    # ===================================================================
    print("\n[1] Creating phasor grid...")

    Sbase = 100.0
    grid = vge.MultiCircuit(Sbase=Sbase, fbase=50.0)

    bus0 = vge.Bus(name="Bus0", Vnom=10, is_slack=True)
    bus1 = vge.Bus(name="Bus1", Vnom=10)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    for bus in grid.buses:
        vge.initialize_bus_phasor_rms(bus, vf=grid.rms_var_factory)

    line = vge.Line(name="Line", bus_from=bus0, bus_to=bus1,
                    r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
    grid.add_line(line)

    load = vge.Load(P=9.999999, Q=0.999999)
    grid.add_load(bus=bus1, api_obj=load)

    gen = vge.Generator(name="Gen0", P=10, vset=1.0, Snom=900)
    grid.add_generator(bus=bus0, api_obj=gen)

    # Build RMS models
    genqec = vge.get_complete_generator_template_phasor(grid.rms_var_factory, name="Gen0").block

    line_mdl = vge.get_line_phasor_rms_template(grid.rms_var_factory).block
    line_mdl.connect([line_mdl.in_vars[0]], [bus0.rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[1]], [bus0.rms_model.out_vars[1]])
    line_mdl.connect([line_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])

    # Attach line model to the line device
    vge.set_rms_model(device=line, model=line_mdl, var_factory=grid.rms_var_factory)

    genqec.connect([genqec.in_vars[0]], [bus0.rms_model.out_vars[0]])
    genqec.connect([genqec.in_vars[1]], [bus0.rms_model.out_vars[1]])

    vge.set_rms_model(device=gen, model=genqec, var_factory=grid.rms_var_factory)

    load_mdl = vge.get_load_phasor_current_rms_template(grid.rms_var_factory).block
    load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
    load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])
    # Convert power to current: I = S* / V* (approximation for initialization)
    # For V ≈ 1.0, Ir ≈ P, Ii ≈ Q
    load_mdl.set_parameter_in_model(var_name="Ir0", new_value=-0.1)
    load_mdl.set_parameter_in_model(var_name="Ii0", new_value=-0.01)
    vge.set_rms_model(device=load, model=load_mdl, var_factory=grid.rms_var_factory)

    print("  ✓ Grid created with multilinear generator")

    # ===================================================================
    # POWER FLOW
    # ===================================================================
    print("\n[2] Running power flow...")
    pf_options = vge.PowerFlowOptions()
    pf_results = vge.power_flow(grid, pf_options)

    if pf_results.converged:
        print(f"  ✓ Power flow converged")
        for i, bus in enumerate(grid.buses):
            v = pf_results.voltage[i]
            print(f"    {bus.name}: Vm={abs(v):.4f} pu")
    else:
        print("  ✗ Power flow failed")
        return False

    # ===================================================================
    # CREATE PHASOR PROBLEM
    # ===================================================================
    print("\n[3] Creating phasor problem...")

    rms_options = vge.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        tolerance=1e-6,
        max_iter=20
    )

    phasor_problem = vge.RmsProblemPhasor(grid=grid, options=rms_options, pf_results=pf_results)
    print(f"  ✓ Phasor problem created with {phasor_problem.get_states_number()} states")

    return phasor_problem


def solve_problem(phasor_problem):
    builder = PolynomialMatrixBuilder(
        problem=phasor_problem,
        verbose=True
    )
    builder.linearize(v_dict={})
    evals, evecs_left, evecs_right, participation_matrix, is_stable, max_real= builder.compute_stability
    pass


if __name__ == "__main__":
    phasor_problem = define_problem()
    solve_problem(phasor_problem)



