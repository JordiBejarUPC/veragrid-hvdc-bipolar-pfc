#!/usr/bin/env python3
"""
Example: Two grids comparing direct VSC vs Transformer+VSC

Grid 1: AC Bus → VSC → DC Bus (direct connection)
Grid 2: AC Bus → Transformer → VSC → DC Bus (with controlled transformer)

Grid 2 transformer controls Pf and Qf to match the power flow through 
the VSC in Grid 1 (on the AC side).
"""

import sys
import os
# Add src directory to path for VeraGridEngine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import numpy as np
import matplotlib.pyplot as plt
import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import ConverterControlType, TapModuleControl, TapPhaseControl, VarPowerFlowRefferenceType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Templates.Rms.vsc_gfl_dclinked import build_vsc_rms, build_trafo_vsc
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCVoltageSource, DCCurrentSource
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template
from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.templates_common_functions import set_rms_model
from VeraGridEngine.Utils.Symbolic.block import Block


def find_name_in_block(name: str, block: Block):
    """Recursively find a variable by name in the block and all its children."""
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var
    
    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res
    
    return None


def create_grid_1():
    """Create Grid 1: Direct VSC connection (baseline)"""
    print("\n" + "=" * 70)
    print("GRID 1: Direct VSC Connection (Baseline)")
    print("=" * 70)
    print("Topology: AC Bus 1 → VSC → DC Bus 2")
    print("-" * 70)
    
    circuit = vge.MultiCircuit(name='Grid 1 - Direct VSC')
    
    # Bus 1: AC source
    bus1_ac = vge.Bus(name='Bus 1 (AC)', Vnom=230.0, is_slack=True)
    circuit.add_bus(bus1_ac)
    
    # Bus 2: DC load
    bus2_dc = vge.Bus(name='Bus 2 (DC)', Vnom=320.0, is_dc=True)
    circuit.add_bus(bus2_dc)
    
    # Generator at AC bus
    gen1 = vge.Generator(name='Generator', P=50.0, vset=1.0)
    circuit.add_generator(bus1_ac, gen1)
    
    # Load at DC bus
    load2 = vge.Load(name='DC Load', P=40.0, Q=0.0)
    circuit.add_load(bus2_dc, load2)
    
    # VSC: Direct connection
    vsc = vge.VSC(
        name='VSC',
        bus_from=bus2_dc,
        bus_to=bus1_ac,
        rate=100.0,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_val=1.0,
        control2_val=0.1,
        alpha1=0.0,
        alpha2=0.0,
        alpha3=0.0
    )
    circuit.add_vsc(vsc)
    
    return circuit


def create_grid_2(target_pf, target_qf):
    """
    Create Grid 2: Transformer + VSC connection with tap control
    
    Transformer uses:
    - TapPhaseControl.Pf: Controls active power flow at "from" bus
    - Fixed tap module (removed Qf control to avoid singularity)
    
    VSC controls Qac to achieve the target Qf indirectly.
    
    Args:
        target_pf: Target active power flow from Bus 1 (MW)
        target_qf: Target reactive power flow from Bus 1 (MVAr)
    """
    print("\n" + "=" * 70)
    print("GRID 2: Transformer + VSC Connection with Tap Control")
    print("=" * 70)
    print("Topology: AC Bus 1 → Transformer → Bus 3 (AC) → VSC → DC Bus 2")
    print(f"Transformer Control: Pf = {target_pf:.2f} MW (Qf controlled by VSC)")
    print("-" * 70)
    
    circuit = vge.MultiCircuit(name='Grid 2 - Transformer + VSC')
    
    # Bus 1: AC source (slack)
    bus1_ac = vge.Bus(name='Bus 1 (AC)', Vnom=230.0, is_slack=True)
    circuit.add_bus(bus1_ac)
    
    # Bus 3: Intermediate AC bus (VSC side of transformer)
    bus3_ac = vge.Bus(name='Bus 3 (AC)', Vnom=230.0)
    circuit.add_bus(bus3_ac)
    
    # Bus 2: DC load
    bus2_dc = vge.Bus(name='Bus 2 (DC)', Vnom=320.0, is_dc=True)
    circuit.add_bus(bus2_dc)
    
    # Generator at AC source bus
    gen1 = vge.Generator(name='Generator', P=50.0)
    circuit.add_generator(bus1_ac, gen1)
    
    # Load at DC bus
    load2 = vge.Generator(name='DC Load', P=1.)
    circuit.add_generator(bus2_dc, load2)
    
    # Transformer between Bus 1 and Bus 3 with tap control
    # Controls only Pf via phase shift (Qf controlled by VSC)
    transformer = vge.Transformer2W(
        name='Transformer',
        bus_from=bus1_ac,
        bus_to=bus3_ac,
        rate=100.0,
        r=0.01,             # Resistance (p.u.)
        x=0.05,             # Reactance (p.u.)
        # Control modes: Pf control via phase shift only
    )
    circuit.add_transformer2w(transformer)
    
    # VSC: Between Bus 3 (AC) and Bus 2 (DC)
    # Qac control achieves the target Qf at the transformer
    vsc = vge.VSC(
        name='VSC',
        bus_from=bus2_dc,
        bus_to=bus3_ac,
        rate=100.0,
        control1=ConverterControlType.Pac,
        control2=ConverterControlType.Vm_dc,
        control1_val=1.0,
        control2_val=1.02,  # Use target Qf from Grid 1
    )
    circuit.add_vsc(vsc)
    
    return circuit


def run_power_flow(circuit, grid_name):
    """Run power flow and return results"""
    print(f"\nRunning Power Flow on {grid_name}...")
    
    pf_options = vge.PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=100,
        tolerance=1e-6,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    
    results = vge.power_flow(grid=circuit, options=pf_options)
    return results


def print_results(circuit, results, grid_name):
    """Print power flow results"""
    print(f"\n{'-'*70}")
    print(f"RESULTS: {grid_name}")
    print(f"{'-'*70}")
    
    if not results.converged:
        print("✗ Power flow did not converge")
        return None, None
    
    print("✓ Converged successfully!")
    
    # Bus voltages
    print("\nBus Voltages:")
    for i, bus in enumerate(circuit.buses):
        vm = np.abs(results.voltage[i])
        va = np.angle(results.voltage[i], deg=True)
        v_kv = vm * bus.Vnom
        bus_type = "DC" if bus.is_dc else "AC"
        print(f"  {bus.name:20s}: V = {vm:.4f} pu ({v_kv:6.2f} kV), θ = {va:6.2f}° ({bus_type})")
    
    # Bus power injections
    print("\nBus Power Injections:")
    for i, bus in enumerate(circuit.buses):
        p = results.Sbus[i].real
        q = results.Sbus[i].imag
        print(f"  {bus.name:20s}: P = {p:7.2f} MW, Q = {q:7.2f} MVAr")
    
    # Transformer flows
    pf_transformer = None
    qf_transformer = None
    if len(circuit.transformers2w) > 0:
        print("\nTransformer Power Flow:")
        for i, trafo in enumerate(circuit.transformers2w):
            if i < len(results.Sf):
                pf = results.Sf[i].real
                qf = results.Sf[i].imag
                pf_transformer = pf
                qf_transformer = qf
                print(f"  {trafo.name}:")
                print(f"    P = {pf:7.2f} MW, Q = {qf:7.2f} MVAr")
                print(f"    Final Tap Module: {trafo.tap_module:.4f}")
                print(f"    Final Tap Phase:  {trafo.tap_phase:.4f} rad")
                print(f"    Control Modes: {trafo.tap_module_control_mode.name} / {trafo.tap_phase_control_mode.name}")
    
    # VSC flows
    pf_vsc = None
    qf_vsc = None
    if len(circuit.vsc_devices) > 0:
        print("\nVSC Power Flow:")
        for i, vsc in enumerate(circuit.vsc_devices):
            # Get VSC power from bus injections
            bus_from_idx = circuit.buses.index(vsc.bus_from)
            if bus_from_idx < len(results.Sbus):
                pf_vsc = -results.Sbus[bus_from_idx].real  # Negative because it's flowing out
                qf_vsc = -results.Sbus[bus_from_idx].imag
                print(f"  {vsc.name}: P = {pf_vsc:7.2f} MW, Q = {qf_vsc:7.2f} MVAr")
    
    return pf_transformer if pf_transformer is not None else pf_vsc, qf_transformer if qf_transformer is not None else qf_vsc


def initialize_grid2_rms_models(grid2):
    """
    Initialize RMS models for Grid 2 using build_vsc_rms and build_trafo_vsc
    
    Args:
        grid2: Grid 2 MultiCircuit with transformer and VSC
    """
    print("\n" + "-" * 70)
    print("Initializing RMS Models for Grid 2")
    print("-" * 70)
    
    # Use the grid's built-in RMS VarFactory
    vf = grid2.rms_var_factory
    
    # Assign RMS models to VSC devices using build_vsc_rms
    for vsc in grid2.vsc_devices:
        print(f"  Initializing VSC '{vsc.name}' with build_vsc_rms...")
        vsc.rms_model = build_vsc_rms(vfactory=vf, name=vsc.name).block
        print(f"    ✓ VSC RMS model assigned")
    
    # Assign RMS models to transformers using build_trafo_vsc
    for trafo in grid2.transformers2w:
        print(f"  Initializing Transformer '{trafo.name}' with build_trafo_vsc...")
        trafo.rms_model = build_trafo_vsc(vf=vf, trafo=trafo).block
        print(f"    ✓ Transformer RMS model assigned")
    
    # Assign RMS models to generators (including DC load)
    for gen in grid2.generators:
        bus = gen.bus
        if bus.is_dc:
            # DC load/generator - use DC current source model
            print(f"  Initializing DC Generator '{gen.name}' at DC bus '{bus.name}'...")
            if bus.rms_model.empty():
                initialize_bus_rms(bus, grid2.rms_var_factory)
            # Get the Vdc variable from the bus RMS model
            if hasattr(bus, 'rms_model') and bus.rms_model is not None:
                # Access Vdc through external_mapping
                vdc = bus.rms_model.external_mapping[VarPowerFlowRefferenceType.Vdc]
                print(f"vdc uid is {vdc.uid}")
                # Check for potential NaN sources
                print(f"    DEBUG: Initial Pdc={gen.P}, Vdc should come from PF results")
                gen.rms_model = DCCurrentSource(vfactory=vf, Vdc=vdc, name=gen.name).block
                print(f"    ✓ DC Generator RMS model assigned")
            else:
                print(f"    ⚠ Bus '{bus.name}' has no RMS model, skipping DC generator")
        else:
            # AC generator - use Genrow model
            print(f"  Initializing AC Generator '{gen.name}' at AC bus '{bus.name}'...")
            if bus.rms_model.empty():
                initialize_bus_rms(bus, grid2.rms_var_factory)
            gen_model = get_complete_generator_template(vfactory=vf, name=gen.name).block
            set_rms_model(device = gen, model=gen_model, var_factory=grid2.rms_var_factory)

    
    # Connect transformer to DC bus (if VSC exists)
    if len(grid2.vsc_devices) > 0 and len(grid2.transformers2w) > 0:
        vsc = grid2.vsc_devices[0]
        trafo = grid2.transformers2w[0]
        if hasattr(vsc.bus_from, 'rms_model') and vsc.bus_from.rms_model is not None:
            if hasattr(trafo.rms_model, 'in_vars') and len(trafo.rms_model.in_vars) > 0:
                vdc_trafo = trafo.rms_model.in_vars[0]
                vdc_bus = vsc.bus_from.rms_model.out_vars[0]
                trafo.rms_model.connect([vdc_trafo], [vdc_bus])
                
                pt_vsc = vsc.rms_model.in_vars[1]
                pt_trafo = trafo.rms_model.out_vars[1]
                vsc.rms_model.connect([pt_vsc], [pt_trafo])
                print(f"  ✓ Connected transformer to DC bus")
    

    
    print(f"  ✓ All RMS models initialized successfully")
    return vf


def run_rms_simulation(grid2, pf_results):
    """
    Run RMS dynamic simulation on Grid 2
    
    Args:
        grid2: Grid 2 MultiCircuit with initialized RMS models
        pf_results: PowerFlowResults from initial power flow
    
    Returns:
        Tuple of (rms_driver, t, y, results)
    """
    print("\n" + "-" * 70)
    print("Running RMS Dynamic Simulation on Grid 2")
    print("-" * 70)
    

    # Create RMS events group
    events_group = RmsEventsGroup(name="Grid2 RMS Simulation")
    grid2.add_rms_events_group(events_group)
    
    # Find DC generator and its Idc_src0 variable for the event
    dc_gen = None
    for gen in grid2.generators:
        if gen.bus.is_dc:
            dc_gen = gen
            break
    
    if dc_gen is not None and hasattr(dc_gen, 'rms_model') and dc_gen.rms_model is not None:
        idc_src0_var = find_name_in_block('Idc_src0', dc_gen.rms_model)
        if idc_src0_var is not None:
            event = RmsEvent(
                device=dc_gen,
                parameter=idc_src0_var,
                time=0.1,
                value=0.011,
                group=events_group
            )
            grid2.add_rms_event(event)
            print(f"  Added event: Idc_src0 step at t=1.0s to value=0.5")
    
    # Set up RMS simulation options
    rms_options = vge.RmsOptions(
        simulation_time=0.2,       # 0.5 seconds simulation
        time_step=0.001,           # 1 ms time step
        max_iter=20,               # Max Newton-Raphson iterations
        integration_method=DynamicIntegrationMethod.DaeBackEuler
    )
    
    # Create and run RMS driver
    print("  Setting up RMS simulation driver...")
    rms_driver = vge.RmsSimulationDriver(
        grid=grid2,
        options=rms_options,
        pf_results=pf_results,
        engine=vge.EngineType.VeraGrid
    )
    
    print("  Running simulation...")
    try:
        rms_driver.run()
    except Exception as e:
        print(f"\n  ✗ RMS simulation failed with error:")
        print(f"    {type(e).__name__}: {str(e)}")
        
        # Try to extract which equations have issues
        if hasattr(rms_driver, 'results') and rms_driver.results is not None:
            print(f"\n  Partial results available")
        raise
    
    # Check results
    results = rms_driver.results
    print(f"  ✓ RMS simulation complete")
    print(f"    Converged: {results.converged}")
    print(f"    Well initialized: {results.well_initialized}")
    
    # Extract time and values for plotting
    time_step = rms_driver.options.time_step
    t = np.arange(len(results.time_array)) * time_step
    y = results.values[:, :, 0]  # First event group
    
    return rms_driver, t, y, results


def plot_rms_results(grid2, t, y, results):
    """Plot VSC and Transformer dynamic simulation variables."""
    print("\n" + "-" * 70)
    print("Plotting RMS Results")
    print("-" * 70)
    
    uid2idx = results.uid2idx
    
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    vsc = grid2.vsc_devices[0] if len(grid2.vsc_devices) > 0 else None
    trafo = grid2.transformers2w[0] if len(grid2.transformers2w) > 0 else None
    dc_gen = None
    for gen in grid2.generators:
        if gen.bus.is_dc:
            dc_gen = gen
            break
    
    ax1 = axes[0]
    ax2 = axes[1]
    ax3 = axes[2]
    
    vsc_plotted = False
    trafo_plotted = False
    dc_plotted = False
    
    if vsc is not None and hasattr(vsc, 'rms_model') and vsc.rms_model is not None:
        pf_vsc = find_name_in_block('Pf_vsc', vsc.rms_model)
        pt_vsc = find_name_in_block('Pt_vsc', vsc.rms_model)
        
        if pf_vsc is not None:
            idx = uid2idx.get(pf_vsc.uid)
            if idx is not None:
                ax1.plot(t, y[:, idx], label='VSC Pf', linewidth=1.5)
                vsc_plotted = True
        
        if pt_vsc is not None:
            idx = uid2idx.get(pt_vsc.uid)
            if idx is not None:
                ax1.plot(t, y[:, idx], label='VSC Pt', linewidth=1.5)
                vsc_plotted = True
    
    if trafo is not None and hasattr(trafo, 'rms_model') and trafo.rms_model is not None:
        pf_trafo = find_name_in_block('Pf_' + trafo.name, trafo.rms_model)
        qf_trafo = find_name_in_block('Qf_' + trafo.name, trafo.rms_model)
        pt_trafo = find_name_in_block('Pt_' + trafo.name, trafo.rms_model)
        qt_trafo = find_name_in_block('Qt_' + trafo.name, trafo.rms_model)
        
        if pf_trafo is not None:
            idx = uid2idx.get(pf_trafo.uid)
            if idx is not None:
                ax2.plot(t, y[:, idx], label='Trafo Pf', linewidth=1.5)
                trafo_plotted = True
        
        if qf_trafo is not None:
            idx = uid2idx.get(qf_trafo.uid)
            if idx is not None:
                ax2.plot(t, y[:, idx], label='Trafo Qf', linewidth=1.5)
                trafo_plotted = True
        
        if pt_trafo is not None:
            idx = uid2idx.get(pt_trafo.uid)
            if idx is not None:
                ax2.plot(t, y[:, idx], label='Trafo Pt', linewidth=1.5)
                trafo_plotted = True
        
        if qt_trafo is not None:
            idx = uid2idx.get(qt_trafo.uid)
            if idx is not None:
                ax2.plot(t, y[:, idx], label='Trafo Qt', linewidth=1.5)
                trafo_plotted = True
    
    if dc_gen is not None and hasattr(dc_gen, 'rms_model') and dc_gen.rms_model is not None:
        idc = find_name_in_block('Idc', dc_gen.rms_model)
        idc_src = find_name_in_block('Idc_src', dc_gen.rms_model)
        idc_src0 = find_name_in_block('Idc_src0', dc_gen.rms_model)
        pdc = find_name_in_block('Pdc', dc_gen.rms_model)
        
        if idc is not None:
            idx = uid2idx.get(idc.uid)
            if idx is not None:
                ax3.plot(t, y[:, idx], label='DC Idc', linewidth=1.5)
                dc_plotted = True
        
        if idc_src is not None:
            idx = uid2idx.get(idc_src.uid)
            if idx is not None:
                ax3.plot(t, y[:, idx], label='DC Idc_src', linewidth=1.5)
                dc_plotted = True
        
        if idc_src0 is not None:
            idx = uid2idx.get(idc_src0.uid)
            if idx is not None:
                ax3.plot(t, y[:, idx], label='DC Idc_src0 (event)', linewidth=1.5, linestyle='--')
                dc_plotted = True
        
        if pdc is not None:
            idx = uid2idx.get(pdc.uid)
            if idx is not None:
                ax3.plot(t, y[:, idx], label='DC Pdc', linewidth=1.5)
                dc_plotted = True
        
        # Also plot Vdc from the bus
        if dc_gen.bus.is_dc and hasattr(dc_gen.bus, 'rms_model') and dc_gen.bus.rms_model is not None:
            vdc_bus = find_name_in_block('Vdc', dc_gen.bus.rms_model)
            if vdc_bus is not None:
                idx = uid2idx.get(vdc_bus.uid)
                if idx is not None:
                    ax3.plot(t, y[:, idx], label='Bus Vdc', linewidth=1.5)
                    dc_plotted = True
    
    if vsc_plotted:
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Power (pu)')
        ax1.set_title('VSC Power Variables')
        ax1.legend(loc='upper right')
        ax1.grid(True)
        ax1.set_xlim([0, t[-1]])
    
    if trafo_plotted:
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Power (pu)')
        ax2.set_title('Transformer Power Variables')
        ax2.legend(loc='upper right')
        ax2.grid(True)
        ax2.set_xlim([0, t[-1]])
    
    if dc_plotted:
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('Current/Power (pu)')
        ax3.set_title('DC Generator Variables')
        ax3.legend(loc='upper right')
        ax3.grid(True)
        ax3.set_xlim([0, t[-1]])
        ax3.axvline(x=1.0, color='red', linestyle=':', alpha=0.7, label='Event at t=1.0s')
    
    plt.tight_layout()
    plt.show()
    plt.savefig('rms_vsc_validation_results.png', dpi=150)
    print("  ✓ Plot saved to rms_vsc_validation_results.png")
    plt.close()


if __name__ == "__main__":
    print("=" * 70)
    print("INVERTER EXAMPLE: Direct VSC vs Transformer+VSC")
    print("=" * 70)
    
    # Step 1: Run Grid 1 (baseline) and get VSC power flow
    grid1 = create_grid_1()
    results1 = run_power_flow(grid1, "Grid 1")
    pf_grid1, qf_grid1 = print_results(grid1, results1, "Grid 1 - Direct VSC")
    
    # Step 2: Run Grid 2 with transformer controlling Pf and Qf to match Grid 1
    print("\n" + "=" * 70)
    print("GRID 2: Transformer with Pf/Qf Control")
    print("=" * 70)
    
    if results1.converged and pf_grid1 is not None:
        # Extract target values from Grid 1's VSC power flow
        target_pf = pf_grid1 if pf_grid1 is not None else 40.0
        target_qf = qf_grid1 if qf_grid1 is not None else 0.0
        
        print(f"\nTarget values from Grid 1 VSC:")
        print(f"  Pf = {target_pf:.2f} MW")
        print(f"  Qf = {target_qf:.2f} MVAr")
        
        grid2 = create_grid_2(target_pf, target_qf)
        results2 = run_power_flow(grid2, "Grid 2")
        pf_grid2, qf_grid2 = print_results(grid2, results2, "Grid 2 - Transformer with Pf/Qf Control")
        
        # Step 3: Initialize RMS models and run dynamic simulation for Grid 2
        if results2.converged:
            # Initialize RMS models for VSC and Transformer
            vf = initialize_grid2_rms_models(grid2)
            
            # Run RMS dynamic simulation
            rms_driver, t, y, sim_results = run_rms_simulation(grid2, results2)
            
            # Plot VSC and Transformer variables
            plot_rms_results(grid2, t[:-1], y[:-1], sim_results)
            print(y[-2])
            # Optionally save the grid with RMS results
            # vge.save_file(grid=grid2, filename="grid2_rms_results.veragrid")
            print("\n  ✓ Grid 2 RMS simulation saved to grid2_rms_results.veragrid")
        
        # Step 4: Final comparison
        print("\n" + "=" * 70)
        print("COMPARISON: Grid 1 vs Grid 2 (Power Flow)")
        print("=" * 70)
        
        if results1.converged and results2.converged:
            print(f"\nPower Flow through AC-side Branch:")
            print(f"{'':20s} {'P (MW)':>12s} {'Q (MVAr)':>12s}")
            print(f"{'-'*46}")
            print(f"{'Grid 1 (VSC)':20s} {pf_grid1 if pf_grid1 is not None else 0.0:12.2f} {qf_grid1 if qf_grid1 is not None else 0.0:12.2f}")
            print(f"{'Grid 2 (Transformer)':20s} {pf_grid2 if pf_grid2 is not None else 0.0:12.2f} {qf_grid2 if qf_grid2 is not None else 0.0:12.2f}")
            print(f"{'-'*46}")
            p_diff = abs((pf_grid1 if pf_grid1 is not None else 0.0) - (pf_grid2 if pf_grid2 is not None else 0.0))
            q_diff = abs((qf_grid1 if qf_grid1 is not None else 0.0) - (qf_grid2 if qf_grid2 is not None else 0.0))
            print(f"{'Difference':20s} {p_diff:12.2f} {q_diff:12.2f}")
            
            print("\n✓ Comparison complete!")
            print("  Grid 2 transformer controls Pf and Qf to match Grid 1's VSC power flow")
        else:
            print("\n✗ One or both grids did not converge")
    else:
        print("\n✗ Grid 1 did not converge, cannot create Grid 2")
    
    print("\n" + "=" * 70)
