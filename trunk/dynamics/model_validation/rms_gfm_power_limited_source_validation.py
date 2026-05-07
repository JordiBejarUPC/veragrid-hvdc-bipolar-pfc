#!/usr/bin/env python3
"""
RMS validation using Grid 2 topology with a power-limited DC source
and a Grid-Forming (GFM) VSC controller.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import DynamicIntegrationMethod, VarPowerFlowRefferenceType
from VeraGridEngine.Templates.Rms.vsc_gfm import VscGfmBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCPowerLimitedSource
from VeraGridEngine.Templates.Rms.transformer_rms_template import initialize_trafo_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent

import rms_gfl_validation as base


def initialize_grid2_rms_models_power_limited_gfm(grid2, pf_results):
    print("\n" + "-" * 70)
    print("Initializing RMS Models for Grid 2 with GFM VSC + power-limited DC source")
    print("-" * 70)

    vf = grid2.var_factory

    for bus in grid2.buses:
        if bus.rms_model.empty():
            initialize_bus_rms(bus, vf)

    for vsc in grid2.vsc_devices:
        print(f"  Initializing VSC '{vsc.name}' with VscGfmBuild...")
        vsc.rms_model = VscGfmBuild(vfactory=vf, name=vsc.name).block

        vm_ac = vsc.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmt]
        va_ac = vsc.rms_model.external_mapping[VarPowerFlowRefferenceType.Vat]
        vdc = vsc.rms_model.external_mapping[VarPowerFlowRefferenceType.Vdc]

        bus_vm_ac = vsc.bus_to.rms_model.external_mapping[VarPowerFlowRefferenceType.Vm]
        bus_va_ac = vsc.bus_to.rms_model.external_mapping[VarPowerFlowRefferenceType.Va]
        bus_vdc = vsc.bus_from.rms_model.external_mapping[VarPowerFlowRefferenceType.Vdc]
        vsc.rms_model.connect([vm_ac, va_ac, vdc], [bus_vm_ac, bus_va_ac, bus_vdc])

        vsc_idx = list(grid2.vsc_devices).index(vsc)
        if vsc_idx < len(pf_results.St_vsc):
            p_pf = float(np.real(pf_results.St_vsc[vsc_idx]) / grid2.Sbase)
            q_pf = float(np.imag(pf_results.St_vsc[vsc_idx]) / grid2.Sbase)

            pref = base.find_name_in_block('P_ref', vsc.rms_model)
            qref = base.find_name_in_block('Q_ref', vsc.rms_model)
            if pref is not None:
                base.set_event_in_block(pref, -p_pf, vf, vsc.rms_model)
            if qref is not None:
                base.set_event_in_block(qref, -q_pf, vf, vsc.rms_model)

        print("    ✓ GFM VSC RMS model assigned")

    for trafo in grid2.transformers2w:
        print(f"  Initializing Transformer '{trafo.name}' with passive RMS template...")
        initialize_trafo_rms(trafo=trafo, vf=vf, Sbase=grid2.Sbase)
        set_rms_model(device=trafo, model=trafo.rms_model, var_factory=vf)
        print("    ✓ Transformer RMS model assigned")

    for line in grid2.lines:
        print(f"  Initializing AC Line '{line.name}' with RMS line model...")
        line.rms_model = get_line_rms_template(vf, name=line.name).block
        set_rms_model(device=line, model=line.rms_model, var_factory=vf)
        print("    ✓ AC line RMS model assigned")

    for gen in grid2.generators:
        bus = gen.bus
        if bus.is_dc:
            print(f"  Initializing DC Generator '{gen.name}' at DC bus '{bus.name}' with DCPowerLimitedSource...")
            vdc = bus.rms_model.external_mapping[VarPowerFlowRefferenceType.Vdc]
            gen.rms_model = DCPowerLimitedSource(vfactory=vf, Vdc=vdc, name=gen.name).block

            c_var = base.find_name_in_block('C', gen.rms_model)
            pmax_var = base.find_name_in_block('Pmax', gen.rms_model)
            pref_var = base.find_name_in_block('Pdc_ref0', gen.rms_model)

            if c_var is not None:
                base.set_event_in_block(c_var, 0.10, vf, gen.rms_model)
            if pmax_var is not None:
                base.set_event_in_block(pmax_var, 0.08, vf, gen.rms_model)
            if pref_var is not None:
                base.set_event_in_block(pref_var, float(gen.P) / grid2.Sbase, vf, gen.rms_model)

            print("    - Tuned power-limited DC source: C=0.10, Pmax=0.08")
            print("    ✓ DC Generator RMS model assigned")
        else:
            print(f"  Initializing AC Generator '{gen.name}' at AC bus '{bus.name}'...")
            gen_model = get_complete_generator_template_rms(vfactory=vf, name=gen.name).block
            set_rms_model(device=gen, model=gen_model, var_factory=vf)

    for load in grid2.get_loads():
        print(f"  Initializing AC Load '{load.name}' with ZIP load model...")
        load.rms_model = ZIPLoadBuild(
            vfactory=vf,
            name=load.name,
            Pl0=-float(load.P) / grid2.Sbase,
            Ql0=-float(load.Q) / grid2.Sbase,
        ).block
        set_rms_model(device=load, model=load.rms_model, var_factory=vf)
        print("    ✓ AC load RMS model assigned")

    print("  ✓ All RMS models initialized successfully")


def run_rms_simulation_power_limited_gfm(grid2, pf_results):
    print("\n" + "-" * 70)
    print("Running RMS Dynamic Simulation (GFM + Power-Limited DC Source)")
    print("-" * 70)

    events_group = RmsEventsGroup(name="Grid2 RMS Simulation - GFM + Power Limited")
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
    print("INVERTER EXAMPLE: GFM VSC + power-limited DC source")
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
    base.print_trafo_powerflow_equation_consistency(grid2, results2)

    initialize_grid2_rms_models_power_limited_gfm(grid2, results2)
    run_rms_simulation_power_limited_gfm(grid2, results2)
