# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
"""
Expanded RMS Test Script - Multi-Bus Grid

This script creates a multi-bus grid similar to hvdc_powerflow_validation.py
and tests RMS initialization step by step.
"""

import numpy as np
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

import VeraGridEngine as gce
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod, VarPowerFlowRefferenceType
from VeraGridEngine.Utils.Symbolic import Block


def create_expanded_grid():
    """Create a multi-bus grid similar to the HVDC validation grid."""
    print("\n=== Creating Multi-Bus Grid ===")
    
    grid = gce.MultiCircuit(name='Multi-Bus Test Grid', Sbase=100)
    
    # Buses (10 kV system)
    bus1 = Bus(name="Bus 1", Vnom=10, is_slack=True)
    bus2 = Bus(name="Bus 2", Vnom=10)
    bus3 = Bus(name="Bus 3", Vnom=10)
    bus4 = Bus(name="Bus 4", Vnom=10)
    
    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)
    grid.add_bus(bus4)
    print(f"  Added 4 buses")
    
    # Generators
    gen1 = gce.Generator(name='Gen1', P=50.0, vset=1.00)
    grid.add_generator(bus1, gen1)
    
    gen3 = gce.Generator(name='Gen3', P=30.0, vset=1.05)
    grid.add_generator(bus3, gen3)
    print(f"  Added 2 generators")
    
    # Loads
    load2 = Load(name="Load 2", P=40.0, Q=15.0)
    grid.add_load(bus2, load2)
    
    load4 = Load(name="Load 4", P=35.0, Q=12.0)
    grid.add_load(bus4, load4)
    print(f"  Added 2 loads")
    
    # Lines with realistic impedances
    line1 = Line(bus_from=bus1, bus_to=bus2, name='Line 1-2', r=0.03, x=0.07, b=0.02, rate=100.0)
    line2 = Line(bus_from=bus2, bus_to=bus3, name='Line 2-3', r=0.025, x=0.06, b=0.015, rate=100.0)
    line3 = Line(bus_from=bus3, bus_to=bus4, name='Line 3-4', r=0.03, x=0.07, b=0.02, rate=100.0)
    line4 = Line(bus_from=bus4, bus_to=bus1, name='Line 4-1', r=0.035, x=0.08, b=0.025, rate=100.0)
    line5 = Line(bus_from=bus2, bus_to=bus4, name='Line 2-4', r=0.02, x=0.05, b=0.01, rate=100.0)
    
    grid.add_line(line1)
    grid.add_line(line2)
    grid.add_line(line3)
    grid.add_line(line4)
    grid.add_line(line5)
    print(f"  Added 5 lines")
    
    print(f"\nGrid created: {len(grid.buses)} buses, {len(grid.lines)} lines, "
          f"{len(list(grid.get_generators()))} generators, {len(list(grid.get_loads()))} loads")
    return grid


def setup_rms_models_expanded(grid):
    """Set up RMS models step by step for expanded grid."""
    print("\n=== Setting up RMS Models ===")
    
    # Step 1: Bus RMS models
    print("\n1. Setting up Bus RMS models...")
    for i, bus in enumerate(grid.buses):
        initialize_bus_rms(bus, vf=grid.var_factory)
        print(f"   Bus {bus.name}: {[v.name for v in bus.rms_model.out_vars]}")
    
    # Step 2: Generator RMS models
    print("\n2. Setting up Generator RMS models...")
    for gen in grid.get_generators():
        template = get_genrow_rms_template(grid.var_factory, name=f"Gen_{gen.name}")
        genrow_mdl = template.block
        
        bus = gen.bus
        print(f"   Connecting Gen {gen.name} to Bus {bus.name}...")
        grid.var_factory.add_connections([genrow_mdl.in_vars[0]], [bus.rms_model.out_vars[0]])  # Vm
        grid.var_factory.add_connections([genrow_mdl.in_vars[1]], [bus.rms_model.out_vars[1]])  # Va
        genrow_mdl.unify_blocks()
        
        big_gen = Block(children=[genrow_mdl])
        big_gen.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl.out_vars[0]})
        big_gen.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl.out_vars[1]})
        big_gen.unify_blocks()
        
        gen.rms_model = big_gen
        print(f"   ✓ Generator {gen.name} connected")
    
    # Step 3: Load RMS models (with minus sign for injection direction)
    print("\n3. Setting up Load RMS models...")
    for load in grid.get_loads():
        Pl0_pu = load.P / grid.Sbase
        Ql0_pu = load.Q / grid.Sbase
        # Negative sign because load consumes power (injection is negative)
        load_template = ZIPLoadBuild(grid.var_factory, name=f"Load_{load.name}",
                                     Pl0=-Pl0_pu, Ql0=-Ql0_pu)
        load_mdl = load_template.block
        
        bus = load.bus
        print(f"   Connecting Load {load.name} to Bus {bus.name}...")
        grid.var_factory.add_connections([load_mdl.in_vars[0]], [bus.rms_model.out_vars[0]])  # Vm
        load_mdl.unify_blocks()
        
        load.rms_model = load_mdl
        print(f"   ✓ Load {load.name} connected (P={load.P}MW, Q={load.Q}MVAr)")
    
    # Step 4: Line RMS models
    print("\n4. Setting up Line RMS models...")
    for line in grid.lines:
        line_mdl = get_line_rms_template(grid.var_factory, name=f"Line_{line.name}").block
        
        from_bus = line.bus_from
        to_bus = line.bus_to
        print(f"   Connecting Line {line.name} ({from_bus.name} → {to_bus.name})...")

        grid.var_factory.add_connections([line_mdl.in_vars[0]], [from_bus.rms_model.out_vars[0]])  # Vmf
        grid.var_factory.add_connections([line_mdl.in_vars[1]], [from_bus.rms_model.out_vars[1]])  # Vaf
        grid.var_factory.add_connections([line_mdl.in_vars[2]], [to_bus.rms_model.out_vars[0]])    # Vmt
        grid.var_factory.add_connections([line_mdl.in_vars[3]], [to_bus.rms_model.out_vars[1]])    # Vat
        line_mdl.unify_blocks()
        
        line.rms_model = line_mdl
        print(f"   ✓ Line {line.name} connected")
    
    print(f"\n=== RMS Models Setup Complete ===")
    print(f"   Buses: {len(grid.buses)}")
    print(f"   Generators: {len(list(grid.get_generators()))}")
    print(f"   Loads: {len(list(grid.get_loads()))}")
    print(f"   Lines: {len(grid.lines)}")


def run_power_flow(grid):
    """Run power flow using the driver."""
    print("\n=== Running Power Flow ===")
    
    pf_driver = gce.PowerFlowDriver(grid=grid)
    pf_driver.run()
    pf_results = pf_driver.results
    
    if not pf_results.converged:
        print("ERROR: Power flow did not converge!")
        return None
    
    print("Power flow converged!")
    print(f"\nBus Voltages:")
    for i, bus in enumerate(grid.buses):
        v = abs(pf_results.voltage[i])
        angle = np.angle(pf_results.voltage[i], deg=True)
        print(f"  {bus.name}: V={v:.4f} p.u., angle={angle:.2f}°")
    
    print(f"\nLine Flows:")
    for i, line in enumerate(grid.lines):
        Sf = pf_results.Sf[i]
        St = pf_results.St[i]
        print(f"  {line.name}: Sf={Sf.real:.3f}+j{Sf.imag:.3f}, St={St.real:.3f}+j{St.imag:.3f}")
    
    return pf_results


def run_rms_simulation(grid, pf_results):
    """Run RMS simulation."""
    print("\n=== Running RMS Simulation ===")
    
    options = RmsOptions(
        time_step=0.001,
        simulation_time=0.5,  # Shorter simulation for testing
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=100,
        verbose=1
    )
    
    print("\nInitializing RmsProblemDae...")
    problem = RmsProblemDae(grid=grid, options=options, pf_results=pf_results)
    
    print("Creating BackEuler solver...")
    solver = BackEulerImplicitIntegration(
        problem=problem, t0=0, t_end=options.simulation_time,
        h=options.time_step, max_iter=options.max_iter
    )
    
    print(f"Simulating {options.simulation_time} seconds...")
    t, y, well_init, converged = solver.simulate()
    
    print(f"\n=== Results ===")
    print(f"Well initialized: {well_init}")
    print(f"Converged: {converged}")
    print(f"Time points: {len(t)}")
    
    return well_init, converged


def main():
    """Main function."""
    print("="*60)
    print("EXPANDED RMS INITIALIZATION TEST")
    print("="*60)
    
    # Create expanded grid
    grid = create_expanded_grid()
    
    # Run power flow
    pf_results = run_power_flow(grid)
    if pf_results is None:
        return False
    
    # Set up RMS models step by step
    setup_rms_models_expanded(grid)
    
    # Run RMS simulation
    well_init, converged = run_rms_simulation(grid, pf_results)
    
    print("\n" + "="*60)
    if well_init and converged:
        print("SUCCESS: RMS initialized and converged!")
    elif well_init:
        print("PARTIAL SUCCESS: RMS initialized but simulation did not converge")
    else:
        print("FAILED: RMS did not initialize properly")
    print("="*60)
    
    return well_init


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
