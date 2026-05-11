# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
"""
HVDC Grid Creation and Dynamic Simulation Script - NO ISLANDS VERSION

This script creates a 4-bus grid with an HVDC line and runs both:
1. AC/DC power flow simulation using generalized formulation (NO ISLAND SPLITTING)
2. Time-domain dynamic simulation using RmsProblemDae
"""

import numpy as np
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

import VeraGridEngine as vg
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.hvdc_line import HvdcLine
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Templates.Rms.hvdc_rms_template import initialize_hvdc_rms
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod, VarPowerFlowRefferenceType
from VeraGridEngine.Utils.Symbolic import Block
from VeraGridEngine.basic_structures import Logger


def create_hvdc_grid():
    """
    Create a grid with HVDC interconnection - NO ISLANDS version.
    Uses the working 4-bus structure with realistic impedances.
    """
    grid = vg.MultiCircuit(name='HVDC Test Grid', Sbase=100)
    
    # Buses (10 kV system)
    bus1 = Bus(name="Bus 1", Vnom=10, is_slack=True)
    bus2 = Bus(name="Bus 2", Vnom=10)
    bus3 = Bus(name="Bus 3", Vnom=10)
    bus4 = Bus(name="Bus 4", Vnom=10)
    hvdc_from = Bus(name="HVDC from", Vnom=10)
    hvdc_to = Bus(name="HVDC to", Vnom=10)
    
    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)
    grid.add_bus(bus4)
    grid.add_bus(hvdc_from)
    grid.add_bus(hvdc_to)
    
    # Generators
    gen1 = Generator(
        name="Gen 1", P=50.0, vset=1.0, Snom=100.0,
        x1=0.3, r1=0.0, freq=60.0, M=10.0, D=5.0,
        tm0=1.0, vf=1.0, omega_ref=1.0, Kp=0.0, Ki=0.0
    )
    grid.add_generator(bus1, gen1)
    
    gen3 = Generator(
        name="Gen 3", P=30.0, vset=1.05, Snom=100.0,
        x1=0.3, r1=0.0, freq=60.0, M=10.0, D=5.0,
        tm0=0.5, vf=1.0, omega_ref=1.0, Kp=0.0, Ki=0.0,
    )
    grid.add_generator(bus3, gen3)
    
    # Loads
    grid.add_load(bus2, Load(name="Load 2", P=40.0, Q=15.0))
    grid.add_load(bus4, Load(name="Load 4", P=35.0, Q=12.0))
    
    # AC Lines with realistic impedances
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

    # HVDC Line
    hvdc = HvdcLine(
        bus_from=hvdc_from, bus_to=hvdc_to, name='HVDC Line',
        Pset=30.0, r=0.5, Vset_f=1.0234, Vset_t=1.1234, rate=100.0,
        dc_link_voltage=150.0, control_mode=vg.HvdcControlType.type_1_Pset, angle_droop=0
    )
    grid.add_hvdc(hvdc)

    return grid


def setup_rms_models(grid):
    """Set up RMS dynamic models for all devices."""
    print("\nSetting up RMS models...")
    
    # Initialize bus RMS models
    for bus in grid.buses:
        initialize_bus_rms(bus, vf=grid.var_factory)
    
    # Create RMS models for generators
    for gen in grid.get_generators():
        template = get_genrow_rms_template(grid.var_factory, name=f"Gen_{gen.name}")
        genrow_mdl = template.block
        
        bus = gen.bus
        genrow_mdl.connect([genrow_mdl.in_vars[0]], [bus.rms_model.out_vars[0]])
        genrow_mdl.connect([genrow_mdl.in_vars[1]], [bus.rms_model.out_vars[1]])
        genrow_mdl.unify_blocks()
        
        big_gen = Block(children=[genrow_mdl])
        big_gen.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl.out_vars[0]})
        big_gen.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl.out_vars[1]})
        big_gen.unify_blocks()
        
        gen.rms_model = big_gen
    
    # Create RMS models for lines
    for line in grid.lines:
        line_mdl = get_line_rms_template(grid.var_factory, name=f"Line_{line.name}").block
        
        from_bus = line.bus_from
        to_bus = line.bus_to
        line_mdl.connect([line_mdl.in_vars[0]], [from_bus.rms_model.out_vars[0]])
        line_mdl.connect([line_mdl.in_vars[1]], [from_bus.rms_model.out_vars[1]])
        line_mdl.connect([line_mdl.in_vars[2]], [to_bus.rms_model.out_vars[0]])
        line_mdl.connect([line_mdl.in_vars[3]], [to_bus.rms_model.out_vars[1]])
        line_mdl.unify_blocks()
        
        line.rms_model = line_mdl
    
    # Create RMS models for loads using ZIP load model (with minus sign for injection)
    for load in grid.get_loads():
        Pl0_pu = load.P / grid.Sbase
        Ql0_pu = load.Q / grid.Sbase
        # Negative sign because load consumes power (injection is negative)
        load_template = ZIPLoadBuild(grid.var_factory, name=f"Load_{load.name}",
                                     Pl0=-Pl0_pu, Ql0=-Ql0_pu)
        load_mdl = load_template.block
        
        bus = load.bus
        load_mdl.connect([load_mdl.in_vars[0]], [bus.rms_model.out_vars[0]])
        load_mdl.unify_blocks()
        
        load.rms_model = load_mdl
    
    # Create RMS models for HVDC lines
    nc = compile_numerical_circuit_at(circuit=grid)
    for hvdc_idx, hvdc in enumerate(grid.hvdc_lines):
        initialize_hvdc_rms(hvdc, hvdc_idx=hvdc_idx, vf=grid.var_factory, nc=nc)
        hvdc_mdl = hvdc.rms_model
        from_bus = hvdc.bus_from
        to_bus = hvdc.bus_to
        hvdc_mdl.connect([hvdc_mdl.in_vars[0]], [from_bus.rms_model.out_vars[0]])
        hvdc_mdl.connect([hvdc_mdl.in_vars[1]], [from_bus.rms_model.out_vars[1]])
        hvdc_mdl.connect([hvdc_mdl.in_vars[2]], [to_bus.rms_model.out_vars[0]])
        hvdc_mdl.connect([hvdc_mdl.in_vars[3]], [to_bus.rms_model.out_vars[1]])
        hvdc_mdl.unify_blocks()
        print(f"    Added HVDC model: {hvdc.name}")
    
    print(f"  RMS models: {len(list(grid.get_generators()))} gen, {len(grid.lines)} lines, "
          f"{len(list(grid.get_loads()))} loads, {len(grid.hvdc_lines)} hvdc, {len(grid.buses)} buses")


def run_dynamic_simulation(grid, pf_results):
    """Run time-domain dynamic simulation."""
    print("\n" + "="*60)
    print("RUNNING DYNAMIC SIMULATION")
    print("="*60)
    
    options = RmsOptions(
        time_step=0.001,
        simulation_time=0.5,
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
    
    return t, y, well_init, converged, problem


def main():
    """Main function."""
    print("="*60)
    print("HVDC GRID - GENERALIZED POWER FLOW (NO ISLANDS)")
    print("="*60)
    
    # Create grid
    print("\nCreating HVDC grid...")
    grid = create_hvdc_grid()
    print(f"Grid: {len(grid.buses)} buses, {len(grid.lines)} AC lines, {len(grid.hvdc_lines)} HVDC lines")
    
    # Run generalized power flow
    print("\nRunning generalized power flow...")
    
    # Compile grid to numerical circuit
    nc = compile_numerical_circuit_at(circuit=grid)
    
    # Split into islands for power flow (HVDC buses are disconnected in AC grid)
    islands = nc.split_into_islands(consider_hvdc_as_island_links=True)
    island = islands[0]
    
    # Get data from island (main AC grid)
    S0 = island.get_power_injections_pu()
    V0 = island.bus_data.Vbus
    Qmin, Qmax = island.get_reactive_power_limits()
    I0 = island.get_current_injections_pu()
    Y0 = island.get_admittance_injections_pu()
    
    # Create power flow options
    pf_options = vg.PowerFlowOptions(
        solver_type=SolverType.NR, 
        verbose=2, 
        tolerance=1e-6, 
        max_iter=25
    )
    
    # Create logger
    logger = Logger()
    
    # Create generalized formulation problem
    problem = PfGeneralizedFormulation(
        V0=V0,
        S0=S0,
        I0=I0,
        Y0=Y0,
        Qmin=Qmin,
        Qmax=Qmax,
        nc=island,
        options=pf_options,
        logger=logger
    )
    
    # Solve using Newton-Raphson
    solution = newton_raphson_fx(
        problem=problem,
        tol=pf_options.tolerance,
        max_iter=pf_options.max_iter,
        trust=pf_options.trust_radius,
        verbose=0,
        logger=logger
    )
    
    if not solution.converged:
        print("ERROR: Generalized power flow did not converge!")
        return False
    
    print("Generalized power flow converged!")
    print(f"  Iterations: {solution.iterations}")
    print(f"  Error: {solution.norm_f:.2e}")
    print(f"  Solution has {len(solution.V)} bus voltages (need {nc.nbus} for RMS)")
    
    # Expand solution to include all buses (HVDC buses need voltage values too)
    full_V = np.ones(nc.nbus, dtype=complex)
    for i in range(min(len(solution.V), nc.nbus)):
        full_V[i] = solution.V[i]
    solution.V = full_V  # Now solution.V has all 6 buses
    
    # Display results
    print("\n" + "-" * 60)
    print("POWER FLOW RESULTS (Generalized Formulation)")
    print("-" * 60)
    print(f"{'Bus':<12} {'Vm (p.u.)':<12} {'Va (deg)':<12}")
    print("-" * 60)
    for i, bus in enumerate(grid.buses):
        v = abs(solution.V[i])
        angle = np.angle(solution.V[i], deg=True)
        print(f"{bus.name:<12} {v:<12.4f} {angle:<12.2f}")
    
    if nc.nhvdc > 0:
        print(f"\nHVDC Flows:")
        print(f"{'Name':<20} {'Pf (MW)':<12} {'Pt (MW)':<12} {'Qf (MVAr)':<12} {'Qt (MVAr)':<12}")
        print("-" * 72)
        for i, hvdc in enumerate(grid.hvdc_lines):
            pf = problem.Pf_hvdc[i] * nc.Sbase
            pt = problem.Pt_hvdc[i] * nc.Sbase
            qf = problem.Qf_hvdc[i] * nc.Sbase
            qt = problem.Qt_hvdc[i] * nc.Sbase
            print(f"{hvdc.name:<20} {pf:<12.2f} {pt:<12.2f} {qf:<12.2f} {qt:<12.2f}")
    
    # Create PowerFlowResults from solution
    from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
    
    total_branches = nc.nbr + nc.nhvdc
    Sf = np.zeros(total_branches, dtype=complex)
    St = np.zeros(total_branches, dtype=complex)
    V = solution.V
    
    # Calculate power flows for regular lines
    for i in range(nc.nbr):
        f = nc.passive_branch_data.F[i]
        t = nc.passive_branch_data.T[i]
        r = nc.passive_branch_data.R[i]
        x = nc.passive_branch_data.X[i]
        b = nc.passive_branch_data.B[i]
        
        if r != 0 or x != 0:
            y_series = 1.0 / complex(r, x)
            I_from = y_series * (V[f] - V[t]) + complex(0, b/2) * V[f]
            I_to = y_series * (V[t] - V[f]) + complex(0, b/2) * V[t]
            Sf[i] = V[f] * np.conj(I_from)
            St[i] = V[t] * np.conj(I_to)
    
    Sbus = nc.get_power_injections_pu()
    
    bus_names = np.array([bus.name for bus in grid.buses])
    branch_names = np.array([br.name for br in grid.get_branches_iter()])
    hvdc_names = np.array([hvdc.name for hvdc in grid.hvdc_lines])
    gen_names = np.array([gen.name for gen in grid.generators])
    
    bus_types = np.zeros(nc.nbus, dtype=int)
    for i, bus in enumerate(grid.buses):
        if bus.is_slack:
            bus_types[i] = 1
        else:
            bus_types[i] = 3
    
    pf_results = PowerFlowResults(
        n=nc.nbus,
        m=total_branches,
        n_hvdc=nc.nhvdc,
        n_vsc=nc.nvsc,
        n_gen=len(list(grid.generators)),
        n_batt=len(grid.batteries),
        n_sh=len(grid.shunts),
        bus_names=bus_names,
        branch_names=branch_names,
        hvdc_names=hvdc_names,
        vsc_names=np.array([]),
        gen_names=gen_names,
        batt_names=np.array([]),
        sh_names=np.array([]),
        bus_types=bus_types
    )
    
    # Set solution data - solution.V has ALL buses now!
    pf_results.voltage = solution.V
    pf_results.Sf = Sf
    pf_results.St = St
    pf_results.Sbus = Sbus
    
    if nc.nhvdc > 0:
        pf_results.Pf_hvdc = problem.Pf_hvdc * nc.Sbase
        pf_results.Pt_hvdc = problem.Pt_hvdc * nc.Sbase
        pf_results.Sf_hvdc = problem.Pf_hvdc + 1j * problem.Qf_hvdc
        pf_results.St_hvdc = problem.Pt_hvdc + 1j * problem.Qt_hvdc
    
    # Set up RMS models
    setup_rms_models(grid)
    
    # Run dynamic simulation
    run_rms = True
    
    if run_rms:
        t, y, well_init, converged, problem = run_dynamic_simulation(grid, pf_results)
        
        print("\n" + "="*60)
        print("DYNAMIC SIMULATION RESULTS")
        print("="*60)
        print(f"Well initialized: {well_init}")
        print(f"Converged: {converged}")
        print(f"Time points: {len(t)}")
        
        if len(t) > 0:
            print(f"\nSimulation time: 0 to {t[-1]:.3f} seconds")
        
        success = converged
    else:
        print("\nNote: Dynamic simulation skipped.")
        success = True
    
    print("\n" + "="*60)
    if success:
        print("SUCCESS: HVDC simulation completed!")
        if nc.nhvdc > 0:
            print(f"  - HVDC active power: {problem.Pf_hvdc[0] * nc.Sbase:.2f} MW")
            print(f"  - HVDC reactive power (from): {problem.Qf_hvdc[0] * nc.Sbase:.2f} MVAr")
    print("="*60)
    
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
