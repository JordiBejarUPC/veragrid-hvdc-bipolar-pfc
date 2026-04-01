# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Dynamic simulation validation for complex phasor-based RMS problem (RmsProblemComplex).

This script validates that the complex phasor approach with multilinear current equations
can successfully run dynamic simulations.
"""

import numpy as np
from matplotlib import pyplot as plt

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.Rms.problems.rms_problem_complex import RmsProblemComplex
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Templates.Rms.bus_complex_rms_template import initialize_bus_complex_rms
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod


def create_test_grid():
    """Create a simple 3-bus test grid."""
    grid = gce.MultiCircuit(Sbase=100, fbase=50.0)
    
    bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10)
    bus2 = gce.Bus(name="Bus2", Vnom=10)
    
    grid.add_bus(bus0)
    grid.add_bus(bus1)
    grid.add_bus(bus2)
    
    line0 = gce.Line(
        name="line 0-1", 
        bus_from=bus0, 
        bus_to=bus1, 
        r=0.029585798816568046, 
        x=0.07100591715976332, 
        b=0.03,
        rate=900.0
    )
    line1 = gce.Line(
        name="line 1-2", 
        bus_from=bus1, 
        bus_to=bus2, 
        r=0.029585798816568046, 
        x=0.07100591715976332, 
        b=0.03,
        rate=900.0
    )
    grid.add_line(line0)
    grid.add_line(line1)
    
    load1 = gce.Load(P=9.999999, Q=0.999999)
    load2 = gce.Load(P=10.0, Q=0.0)
    grid.add_load(bus=bus1, api_obj=load1)
    grid.add_load(bus=bus2, api_obj=load2)
    
    gen0 = gce.Generator(
        name="Gen0", 
        P=10, 
        vset=1.0, 
        Snom=900,
        x1=0.86138701, 
        r1=0.3, 
        freq=50.0,
        M=10.0,
        D=1.0,
        omega_ref=1.0,
        Kp=1.0,
        Ki=10.0,
    )
    grid.add_generator(bus=bus0, api_obj=gen0)
    
    return grid


def main():
    """Run dynamic simulation validation."""
    print("=" * 60)
    print("COMPLEX PHASOR DYNAMIC SIMULATION VALIDATION")
    print("=" * 60)
    print()
    
    # Create grid
    print("Creating test grid...")
    grid = create_test_grid()
    
    # Initialize with complex phasor
    for bus in grid.buses:
        initialize_bus_complex_rms(bus, vf=grid.var_factory)
    
    # Run power flow
    print("Running power flow...")
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=0)
    res = gce.power_flow(grid, options=pf_options)
    
    if not res.converged:
        print("✗ Power flow did not converge")
        return False
    
    print(f"✓ Power flow converged")
    print()
    
    # Create problem
    print("Creating RmsProblemComplex...")
    options = RmsOptions(
        time_step=0.001,
        simulation_time=0.5,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.BackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=100,
        verbose=0
    )
    
    try:
        problem = RmsProblemComplex(grid=grid, options=options, pf_results=res)
        print(f"✓ Problem created: {problem.get_all_vars_number()} variables")
        print()
        
        # Run simulation
        print("Running dynamic simulation...")
        solver = BackEulerImplicitIntegration(
            problem=problem,
            t0=0,
            t_end=options.simulation_time,
            h=options.time_step,
            max_iter=options.max_iter
        )
        
        t, y, well_init, converged = solver.simulate()
        
        print(f"✓ Simulation completed: {len(t)} time steps")
        print(f"✓ Converged: {converged}")
        print()
        
        # Extract and plot results
        n_buses = 3
        vm = np.zeros((len(t), n_buses))
        va = np.zeros((len(t), n_buses))
        
        for i in range(n_buses):
            Vr = y[:, 2*i]
            Vi = y[:, 2*i + 1]
            vm[:, i] = np.sqrt(Vr**2 + Vi**2)
            va[:, i] = np.degrees(np.arctan2(Vi, Vr))
        
        # Plot
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        
        ax = axes[0]
        for i in range(n_buses):
            ax.plot(t, vm[:, i], linewidth=2, label=f'Bus {i}')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Voltage Magnitude (pu)')
        ax.set_title('Voltage Magnitudes')
        ax.legend()
        ax.grid(True)
        
        ax = axes[1]
        for i in range(n_buses):
            ax.plot(t, va[:, i], linewidth=2, label=f'Bus {i}')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Voltage Angle (degrees)')
        ax.set_title('Voltage Angles')
        ax.legend()
        ax.grid(True)
        
        plt.tight_layout()
        plt.savefig('complex_phasor_dynamic.png', dpi=150)
        print("Plot saved to: complex_phasor_dynamic.png")
        plt.show()
        
        return converged
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
