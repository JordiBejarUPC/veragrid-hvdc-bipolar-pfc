#!/usr/bin/env python3
"""
RMS validation using Grid 2 topology with a power-limited DC source.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCPowerLimitedSource
from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Aggregation import RmsEvent

import rms_gfl_validation as base


def initialize_grid2_rms_models_power_limited(grid2, pf_results):
    base.initialize_grid2_rms_models(grid2, pf_results)

    vf = grid2.rms_var_factory
    dc_gen = next((g for g in grid2.generators if g.bus.is_dc), None)
    if dc_gen is None:
        return

    vdc = dc_gen.bus.rms_model.external_mapping[base.VarPowerFlowRefferenceType.Vdc]
    dc_gen.rms_model = DCPowerLimitedSource(vfactory=vf, Vdc=vdc, name=dc_gen.name).block

    c_var = base.find_name_in_block('C', dc_gen.rms_model)
    pmax_var = base.find_name_in_block('Pmax', dc_gen.rms_model)
    pref_var = base.find_name_in_block('Pdc_ref0', dc_gen.rms_model)

    if c_var is not None:
        base.set_event_in_block(c_var, 0.10, vf, dc_gen.rms_model)
    if pmax_var is not None:
        base.set_event_in_block(pmax_var, 0.08, vf, dc_gen.rms_model)
    if pref_var is not None:
        base.set_event_in_block(pref_var, float(dc_gen.P) / grid2.Sbase, vf, dc_gen.rms_model)

    print("  ✓ Replaced DC source with DCPowerLimitedSource (C=0.10, Pmax=0.08)")


def run_rms_simulation_power_limited(grid2, pf_results):
    print("\n" + "-" * 70)
    print("Running RMS Dynamic Simulation (Power-Limited DC Source)")
    print("-" * 70)

    events_group = RmsEventsGroup(name="Grid2 RMS Simulation - Power Limited")
    grid2.add_rms_events_group(events_group)

    dc_gen = next((g for g in grid2.generators if g.bus.is_dc), None)
    if dc_gen is not None and dc_gen.rms_model is not None:
        pdc_ref0_var = base.find_name_in_block('Pdc_ref0', dc_gen.rms_model)
        if pdc_ref0_var is not None:
            p0 = float(dc_gen.P) / grid2.Sbase
            p1 = p0 + 0.001
            evt = RmsEvent(
                device=dc_gen,
                parameter=pdc_ref0_var,
                time=0.10,
                value=p1,
                group=events_group,
            )
            grid2.add_rms_event(evt)
            print(f"  Added event: Pdc_ref0 step {p0:.6f} -> {p1:.6f} at t=0.10s")

    rms_options = vge.RmsOptions(
        simulation_time=40,
        time_step=0.02,
        max_iter=30,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
    )

    rms_driver = vge.RmsSimulationDriver(
        grid=grid2,
        options=rms_options,
        pf_results=pf_results,
        engine=vge.EngineType.VeraGrid,
    )

    rms_driver.run()
    results = rms_driver.results
    print(f"  ✓ RMS simulation complete (converged={results.converged})")
    base.plot_rms_results(grid2, results)


if __name__ == "__main__":
    print("=" * 70)
    print("INVERTER EXAMPLE: Transformer (TrafoGFL) + power-limited DC source")
    print("=" * 70)

    grid2 = base.create_grid_2()
    results2 = base.run_power_flow(grid2, "Grid 2")

    if not results2.converged:
        print("\n✗ Grid 2 power flow did not converge")
        sys.exit(1)

    print("\n" + "-" * 70)
    print("Bus Voltages (Power Flow)")
    print("-" * 70)
    for i, bus in enumerate(grid2.buses):
        vm = np.abs(results2.voltage[i])
        va_deg = np.degrees(np.angle(results2.voltage[i]))
        bus_type = "DC" if bus.is_dc else "AC"
        print(f"  {bus.name:20s}: Vm={vm:.6f} pu, Va={va_deg:.4f} deg ({bus_type})")

    base.print_vsc_pf_loss_consistency(grid2, results2)
    initialize_grid2_rms_models_power_limited(grid2, results2)
    base.print_gfl_init_consistency(grid2, results2)
    base.print_trafo_powerflow_equation_consistency(grid2, results2)
    run_rms_simulation_power_limited(grid2, results2)
