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
import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import ConverterControlType, TapModuleControl, TapPhaseControl
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType


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
        bus_from=bus1_ac,
        bus_to=bus2_dc,
        rate=100.0,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_val=1.0,
        control2_val=0.0,
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
    - TapModuleControl.Qf: Controls reactive power flow at "from" bus
    
    Args:
        target_pf: Target active power flow from Bus 1 (MW)
        target_qf: Target reactive power flow from Bus 1 (MVAr)
    """
    print("\n" + "=" * 70)
    print("GRID 2: Transformer + VSC Connection with Tap Control")
    print("=" * 70)
    print("Topology: AC Bus 1 → Transformer → Bus 3 (AC) → VSC → DC Bus 2")
    print(f"Transformer Control: Pf = {target_pf:.2f} MW, Qf = {target_qf:.2f} MVAr")
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
    gen1 = vge.Generator(name='Generator', P=50.0, vset=1.0)
    circuit.add_generator(bus1_ac, gen1)
    
    # Load at DC bus
    load2 = vge.Load(name='DC Load', P=40.0, Q=0.0)
    circuit.add_load(bus2_dc, load2)
    
    # Transformer between Bus 1 and Bus 3 with tap control
    # Controls active power flow to match Grid 1
    # Use phase shift to control Pf, fixed tap module
    transformer = vge.Transformer2W(
        name='Transformer',
        bus_from=bus1_ac,
        bus_to=bus3_ac,
        rate=100.0,
        r=0.01,             # Resistance (p.u.)
        x=0.05,             # Reactance (p.u.)
        # Control modes: Pf control via phase shift
        tap_module_control_mode=TapModuleControl.fixed,
        tap_phase_control_mode=TapPhaseControl.Pf,
        Pset=target_pf,     # Target active power flow
    )
    circuit.add_transformer2w(transformer)
    
    # VSC: Between Bus 3 (AC) and Bus 2 (DC)
    vsc = vge.VSC(
        name='VSC',
        bus_from=bus3_ac,
        bus_to=bus2_dc,
        rate=100.0,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_val=1.0,
        control2_val=0.0,
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
        control_q=True,
        control_taps_modules=True,
        control_taps_phase=True
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


if __name__ == "__main__":
    print("=" * 70)
    print("INVERTER EXAMPLE: Direct VSC vs Transformer+VSC")
    print("=" * 70)
    
    # Step 1: Run Grid 1 (baseline) and get VSC power flow
    grid1 = create_grid_1()
    results1 = run_power_flow(grid1, "Grid 1")
    pf_grid1, qf_grid1 = print_results(grid1, results1, "Grid 1 - Direct VSC")
    
    # Save Grid 1
    if results1.converged:
        vge.save_file(grid=grid1, filename='inverter_2bus_grid1.veragrid')
        print("\n✓ Grid 1 saved to: inverter_2bus_grid1.veragrid")
    
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
        
        # Save Grid 2
        if results2.converged:
            vge.save_file(grid=grid2, filename='inverter_2bus_grid2.veragrid')
            print("\n✓ Grid 2 saved to: inverter_2bus_grid2.veragrid")
        
        # Step 3: Final comparison
        print("\n" + "=" * 70)
        print("COMPARISON: Grid 1 vs Grid 2")
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
