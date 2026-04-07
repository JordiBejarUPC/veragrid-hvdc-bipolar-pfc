#!/usr/bin/env python3
"""
RMS validation using Grid 2 topology with GFL VSC model.

Topology:
AC Bus 1 -> Transformer -> AC Bus 3 -> VSC (GFL) -> DC Bus 2
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import numpy as np
import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import ConverterControlType, VarPowerFlowRefferenceType, ParamPowerFlowRefferenceType
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Templates.Rms.vsc_gfl import TrafoGflBuild
from VeraGridEngine.Templates.Rms.transformer_rms_template import initialize_trafo_rms
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCCurrentSource
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.templates_common_functions import set_rms_model
from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.Utils.Symbolic.block import Block


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

    return None


def create_grid_2():
    circuit = vge.MultiCircuit(name='Grid 2 - Transformer + GFL VSC')

    bus1_ac = vge.Bus(name='Bus 1 (AC)', Vnom=230.0, is_slack=True)
    bus3_ac = vge.Bus(name='Bus 3 (AC)', Vnom=230.0)
    bus2_dc = vge.Bus(name='Bus 2 (DC)', Vnom=320.0, is_dc=True)
    circuit.add_bus(bus1_ac)
    circuit.add_bus(bus3_ac)
    circuit.add_bus(bus2_dc)

    gen1 = vge.Generator(name='Generator', P=50.0)
    circuit.add_generator(bus1_ac, gen1)

    dc_load = vge.Generator(name='DC Load', P=1.0)
    circuit.add_generator(bus2_dc, dc_load)

    transformer = vge.Transformer2W(
        name='Transformer',
        bus_from=bus1_ac,
        bus_to=bus3_ac,
        rate=100.0,
        r=0.01,
        x=0.05,
    )
    circuit.add_transformer2w(transformer)

    vsc = vge.VSC(
        name='VSC',
        bus_from=bus2_dc,
        bus_to=bus3_ac,
        rate=100.0,
        control1=ConverterControlType.Pac,
        control2=ConverterControlType.Vm_dc,
        control1_val=1.0,
        control2_val=1.02,
    )
    circuit.add_vsc(vsc)

    return circuit


def run_power_flow(circuit, grid_name):
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
    return vge.power_flow(grid=circuit, options=pf_options)


def initialize_grid2_rms_models(grid2):
    print("\n" + "-" * 70)
    print("Initializing RMS Models for Grid 2 with GFL VSC")
    print("-" * 70)

    vf = grid2.var_factory

    for trafo in grid2.transformers2w:
        print(f"  Initializing Transformer '{trafo.name}' with initialize_trafo_rms...")
        if trafo.bus_from.rms_model.empty():
            initialize_bus_rms(trafo.bus_from, vf)
        if trafo.bus_to.rms_model.empty():
            initialize_bus_rms(trafo.bus_to, vf)
        initialize_trafo_rms(trafo=trafo, vf=vf, Sbase=grid2.Sbase)

        # Compatibility with RMSProblemDae branch initialization path.
        g = vf.add_var(f"g_{trafo.name}")
        b = vf.add_var(f"b_{trafo.name}")
        bsh = vf.add_var(f"bsh_{trafo.name}")
        trafo.rms_model.api_obj_mapping[ParamPowerFlowRefferenceType.g] = g
        trafo.rms_model.api_obj_mapping[ParamPowerFlowRefferenceType.b] = b
        trafo.rms_model.api_obj_mapping[ParamPowerFlowRefferenceType.bsh] = bsh
        ys = 1.0 / complex(trafo.R, trafo.X)
        trafo.rms_model.parameters[g] = vf.add_const(float(ys.real))
        trafo.rms_model.parameters[b] = vf.add_const(float(ys.imag))
        trafo.rms_model.parameters[bsh] = vf.add_const(float(trafo.B))

        vmf = trafo.bus_from.rms_model.external_mapping[VarPowerFlowRefferenceType.Vm]
        vaf = trafo.bus_from.rms_model.external_mapping[VarPowerFlowRefferenceType.Va]
        vmt = trafo.bus_to.rms_model.external_mapping[VarPowerFlowRefferenceType.Vm]
        vat = trafo.bus_to.rms_model.external_mapping[VarPowerFlowRefferenceType.Va]
        trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmf] = vmf
        trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Vaf] = vaf
        trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmt] = vmt
        trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Vat] = vat

        # Compatibility for VSC auto-connect path (value is ignored by dummy input).
        trafo.rms_model.out_vars = [trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Pf]]
        print("    ✓ Transformer RMS model assigned")

    for vsc in grid2.vsc_devices:
        print(f"  Initializing VSC '{vsc.name}' with TrafoGflBuild...")
        vsc.rms_model = TrafoGflBuild(
            vfactory=vf,
            name=vsc.name,
            control1=ConverterControlType.Vm_dc,
            control2=ConverterControlType.Qac,
        ).block
        vsc.rms_model.unify_blocks()

        # Align GFL initialization with RMS PF sign convention and control references.
        q_ref_var = find_name_in_block('Q_ref', vsc.rms_model)
        if q_ref_var is not None:
            vsc.rms_model.event_dict[q_ref_var] = vf.add_const(None)

        # Compatibility with RMSProblemDae VSC initialization path.
        alpha1 = vf.add_var(f"alpha1_{vsc.name}")
        alpha2 = vf.add_var(f"alpha2_{vsc.name}")
        alpha3 = vf.add_var(f"alpha3_{vsc.name}")
        vsc.rms_model.api_obj_mapping[ParamPowerFlowRefferenceType.alpha1] = alpha1
        vsc.rms_model.api_obj_mapping[ParamPowerFlowRefferenceType.alpha2] = alpha2
        vsc.rms_model.api_obj_mapping[ParamPowerFlowRefferenceType.alpha3] = alpha3
        vsc.rms_model.parameters[alpha1] = vf.add_const(0.0)
        vsc.rms_model.parameters[alpha2] = vf.add_const(0.0)
        vsc.rms_model.parameters[alpha3] = vf.add_const(0.0)

        # Prevent automatic branch->vsc in_vars[0] connection from overwriting real inputs.
        vsc.rms_model.in_vars = [vf.add_var(f"dummy_in_{vsc.name}")] + list(vsc.rms_model.in_vars)

        if vsc.bus_from.rms_model.empty():
            initialize_bus_rms(vsc.bus_from, vf)
        if vsc.bus_to.rms_model.empty():
            initialize_bus_rms(vsc.bus_to, vf)

        vdc_bus = vsc.bus_from.rms_model.external_mapping[VarPowerFlowRefferenceType.Vdc]
        vm_f_bus = vsc.bus_to.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmf]
        va_f_bus = vsc.bus_to.rms_model.external_mapping[VarPowerFlowRefferenceType.Vaf]
        vm_t_bus = vsc.bus_to.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmt]
        va_t_bus = vsc.bus_to.rms_model.external_mapping[VarPowerFlowRefferenceType.Vat]

        vdc_vsc = vsc.rms_model.external_mapping[VarPowerFlowRefferenceType.Vdc]
        vm_t_vsc = vsc.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmt]
        va_t_vsc = vsc.rms_model.external_mapping[VarPowerFlowRefferenceType.Vat]
        vm_f_vsc = vsc.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmf]
        va_f_vsc = vsc.rms_model.external_mapping[VarPowerFlowRefferenceType.Vaf]
        vsc.rms_model.connect([vdc_vsc, vm_t_vsc, va_t_vsc, vm_f_vsc, va_f_vsc], [vdc_bus, vm_f_bus, va_f_bus, vm_t_bus, va_t_bus])

        print("    ✓ VSC GFL RMS model assigned")

    for gen in grid2.generators:
        bus = gen.bus
        if bus.is_dc:
            print(f"  Initializing DC Generator '{gen.name}' at DC bus '{bus.name}'...")
            if bus.rms_model.empty():
                initialize_bus_rms(bus, vf)
            vdc = bus.rms_model.external_mapping[VarPowerFlowRefferenceType.Vdc]
            gen.rms_model = DCCurrentSource(vfactory=vf, Vdc=vdc, name=gen.name).block
            print("    ✓ DC Generator RMS model assigned")
        else:
            print(f"  Initializing AC Generator '{gen.name}' at AC bus '{bus.name}'...")
            if bus.rms_model.empty():
                initialize_bus_rms(bus, vf)
            gen_model = get_complete_generator_template(vfactory=vf, name=gen.name).block
            set_rms_model(device=gen, model=gen_model, var_factory=vf)

    # Close the missing reactive balance at the AC virtual bus used by VSC models.
    if len(grid2.transformers2w) > 0 and len(grid2.vsc_devices) > 0:
        trafo_qt = grid2.transformers2w[0].rms_model.external_mapping[VarPowerFlowRefferenceType.Qt]
        vsc_qt = grid2.vsc_devices[0].rms_model.external_mapping[VarPowerFlowRefferenceType.Qt]
        grid2.vsc_devices[0].rms_model.algebraic_eqs.append(trafo_qt + vsc_qt)

    print("  ✓ All RMS models initialized successfully")


def run_rms_simulation(grid2, pf_results):
    print("\n" + "-" * 70)
    print("Running RMS Dynamic Simulation on Grid 2")
    print("-" * 70)

    events_group = RmsEventsGroup(name="Grid2 GFL RMS Simulation")
    grid2.add_rms_events_group(events_group)

    dc_gen = None
    for gen in grid2.generators:
        if gen.bus.is_dc:
            dc_gen = gen
            break

    if dc_gen is not None and dc_gen.rms_model is not None:
        idc_src0_var = find_name_in_block('Idc_src0', dc_gen.rms_model)
        if idc_src0_var is not None:
            event = RmsEvent(
                device=dc_gen,
                parameter=idc_src0_var,
                time=0.1,
                value=0.011,
                group=events_group,
            )
            grid2.add_rms_event(event)
            print("  Added event: Idc_src0 step at t=0.1s")

    rms_options = vge.RmsOptions(
        simulation_time=1,
        time_step=0.005,
        max_iter=20,
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


if __name__ == "__main__":
    print("=" * 70)
    print("INVERTER EXAMPLE: Transformer + GFL VSC")
    print("=" * 70)

    grid2 = create_grid_2()
    results2 = run_power_flow(grid2, "Grid 2")

    if not results2.converged:
        print("\n✗ Grid 2 power flow did not converge")
        sys.exit(1)

    initialize_grid2_rms_models(grid2)
    run_rms_simulation(grid2, results2)
