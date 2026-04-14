"""
Simple AC-DC-AC grid topology with VSC converters and HVDC line.

Topology:
                    ┌── AC Line ──┐
                    │             │
  AC Bus 1 ←──VSC 1──→ DC Bus 1 ←──HVDC──→ DC Bus 2 ←──VSC 2──→ AC Bus 2

Power flows from Bus 1 (excess generation) to Bus 2 (generation deficit) 
through both AC line and HVDC in parallel.
"""

import numpy as np
import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType


def create_simple_acdc_grid():
    """
    Create a simple AC-DC-AC grid with VSC converters, HVDC line, and parallel AC line.
    
    Returns:
        MultiCircuit: The created grid
    """
    # Create the circuit
    grid = vge.MultiCircuit(name='AC-DC-AC Grid with Parallel Paths')

    # ------------------------------------------------------------------------------------------------------------------
    # Create AC Buses
    # ------------------------------------------------------------------------------------------------------------------
    # AC Bus 1: Slack bus with generation
    ac_bus1 = vge.Bus(name='AC Bus 1', Vnom=230.0, is_slack=True)
    grid.add_bus(ac_bus1)

    # AC Bus 2: PV bus with some generation  
    ac_bus2 = vge.Bus(name='AC Bus 2', Vnom=230.0)
    grid.add_bus(ac_bus2)

    # ------------------------------------------------------------------------------------------------------------------
    # Create DC Buses
    # ------------------------------------------------------------------------------------------------------------------
    dc_bus1 = vge.Bus(name='DC Bus 1', Vnom=320.0, is_dc=True)
    grid.add_bus(dc_bus1)

    dc_bus2 = vge.Bus(name='DC Bus 2', Vnom=320.0, is_dc=True)
    grid.add_bus(dc_bus2)

    # ------------------------------------------------------------------------------------------------------------------
    # Add Generators and Loads
    # ------------------------------------------------------------------------------------------------------------------
    # AC Bus 1: Large generator, small load -> exports power
    gen1 = vge.Generator(name='Gen 1 (Slack)', P=100.0, vset=1.02)
    grid.add_generator(ac_bus1, gen1)

    load1 = vge.Load(name='Load 1', P=40.0, Q=20.0)
    grid.add_load(ac_bus1, load1)

    # AC Bus 2: Small generator, large load -> imports power
    gen2 = vge.Generator(name='Gen 2', P=20.0, vset=1.0)
    grid.add_generator(ac_bus2, gen2)

    load2 = vge.Load(name='Load 2', P=80.0, Q=40.0)
    grid.add_load(ac_bus2, load2)

    # ------------------------------------------------------------------------------------------------------------------
    # Add Parallel AC Line
    # ------------------------------------------------------------------------------------------------------------------
    ac_line = vge.Line(
        name='AC Line 1-2',
        bus_from=ac_bus1,
        bus_to=ac_bus2,
        r=2.0,      # Resistance (ohms)
        x=10.0,     # Reactance (ohms) - significant impedance
        b=0.0005,   # Susceptance (S)
        rate=100.0  # Rating (MVA)
    )
    grid.add_line(ac_line)

    # ------------------------------------------------------------------------------------------------------------------
    # Add VSC Converters
    # ------------------------------------------------------------------------------------------------------------------
    # VSC 1: Rectifier at Bus 1 (controls DC voltage)
    vsc1 = vge.VSC(
        name='VSC 1',
        bus_from=ac_bus1,
        bus_to=dc_bus1,
        rate=100.0,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_val=1.0,
        control2_val=0.0
    )
    grid.add_vsc(vsc1)

    # VSC 2: Inverter at Bus 2 (controls active power)
    vsc2 = vge.VSC(
        name='VSC 2',
        bus_from=dc_bus2,
        bus_to=ac_bus2,
        rate=100.0,
        control1=ConverterControlType.Pac,
        control2=ConverterControlType.Qac,
        control1_val=20.0,  # Inject 20 MW from DC to AC
        control2_val=0.0
    )
    grid.add_vsc(vsc2)

    # ------------------------------------------------------------------------------------------------------------------
    # Add HVDC Line
    # ------------------------------------------------------------------------------------------------------------------
    hvdc_line = vge.HvdcLine(
        name='HVDC Link',
        bus_from=dc_bus1,
        bus_to=dc_bus2,
        r=1.0,
        Pset=20.0,  # 20 MW from Bus 1 to Bus 2
        rate=100.0
    )
    grid.add_hvdc(hvdc_line)

    return grid


def run_power_flow(grid):
    """Run power flow and print results."""
    print(f"\n{'='*70}")
    print(f"Running Power Flow on: {grid.name}")
    print(f"{'='*70}\n")

    # Simple power flow options
    pf_options = vge.PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        control_q=False,
        max_iter=100,
        tolerance=1e-6
    )

    # Run power flow
    results = vge.power_flow(grid=grid, options=pf_options)

    # Print results
    print(f"{'-'*70}")
    print("POWER FLOW RESULTS")
    print(f"{'-'*70}")
    print(f"Converged:     {results.converged}")
    print(f"Iterations:    {results.iterations}")
    print(f"Error:         {results.error:.2e}")
    print()

    print(f"{'-'*70}")
    print("BUS VOLTAGES")
    print(f"{'-'*70}")
    print(f"{'Bus Name':<20} {'V (pu)':<12} {'Angle (°)':<12}")
    print(f"{'-'*70}")
    for i, bus in enumerate(grid.buses):
        vm = abs(results.voltage[i])
        va = np.angle(results.voltage[i], deg=True)
        print(f"{bus.name:<20} {vm:<12.4f} {va:<12.2f}")
    print()

    print(f"{'-'*70}")
    print("POWER INJECTIONS AT BUSES")
    print(f"{'-'*70}")
    print(f"{'Bus Name':<20} {'P (MW)':<12} {'Q (MVAr)':<12}")
    print(f"{'-'*70}")
    for i, bus in enumerate(grid.buses):
        p = results.Sbus[i].real
        q = results.Sbus[i].imag
        print(f"{bus.name:<20} {p:<12.2f} {q:<12.2f}")
    print()

    print(f"{'-'*70}")
    print("PARALLEL PATHS POWER FLOW")
    print(f"{'-'*70}")
    
    # AC Line power flow
    for i, line in enumerate(grid.lines):
        pf = results.Sf[i].real
        qf = results.Sf[i].imag
        pt = results.St[i].real
        qt = results.St[i].imag
        losses = results.losses[i].real
        print(f"\nAC Line: {line.name}")
        print(f"  Power from Bus 1: P = {pf:7.2f} MW, Q = {qf:7.2f} MVAr")
        print(f"  Power to Bus 2:   P = {pt:7.2f} MW, Q = {qt:7.2f} MVAr")
        print(f"  Losses:           {losses:7.2f} MW")
    
    # HVDC power flow
    for i, hvdc in enumerate(grid.hvdc_lines):
        pf = results.Pf_hvdc[i]
        pt = results.Pt_hvdc[i]
        losses = results.losses_hvdc[i]
        print(f"\nHVDC Link: {hvdc.name}")
        print(f"  Power from Bus 1: P = {pf:7.2f} MW")
        print(f"  Power to Bus 2:   P = {pt:7.2f} MW")
        print(f"  Losses:           {losses:7.2f} MW")
    
    # Total power transfer
    total_ac_p = sum(results.Sf[i].real for i in range(len(grid.lines)))
    total_hvdc_p = sum(results.Pf_hvdc)
    print(f"\nTotal Power Transfer Bus 1 → Bus 2:")
    print(f"  Via AC Line:      {total_ac_p:7.2f} MW")
    print(f"  Via HVDC:         {total_hvdc_p:7.2f} MW")
    print(f"  Total:            {total_ac_p + total_hvdc_p:7.2f} MW")
    print(f"{'-'*70}")

    print(f"{'-'*70}")
    print("POWER BALANCE SUMMARY")
    print(f"{'-'*70}")
    total_gen = sum(g.P for g in grid.generators)
    total_load = sum(l.P for l in grid.loads)
    print(f"Total Generation:   {total_gen:7.2f} MW")
    print(f"Total Load:         {total_load:7.2f} MW")
    print(f"Net Export Needed:  {total_gen - total_load:7.2f} MW")
    print(f"{'-'*70}")

    return results


if __name__ == "__main__":
    # Create the grid
    grid = create_simple_acdc_grid()

    # Print grid topology
    print(f"{'='*70}")
    print(f"GRID: {grid.name}")
    print(f"{'='*70}")
    print(f"Buses:      {len(grid.buses)} (AC: 2, DC: 2)")
    print(f"Generators: {len(grid.generators)}")
    print(f"Loads:      {len(grid.loads)}")
    print(f"AC Lines:   {len(grid.lines)}")
    print(f"VSCs:       {len(grid.vsc_devices)}")
    print(f"HVDC Lines: {len(grid.hvdc_lines)}")

    # Run power flow
    results = run_power_flow(grid)

    # Save the grid
    print(f"\nGrid saved to: simple_acdc_grid.veragrid")
