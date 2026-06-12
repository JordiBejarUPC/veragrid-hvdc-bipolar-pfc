#!/usr/bin/env python3
"""
RMS validation for a GFM VSC with an explicit AC filter network.

Topology:
DC bus -> VSC -> AC VSC bus -> line -> filter bus -> line -> grid bus
                                      |
                                    shunt

The VSC device itself receives the GFM RMS model from
VeraGridEngine.Templates.Rms.vsc_gfm.VscGfmBuild. The AC filter network is
kept as regular grid elements so the VSC is not split into a transformer and a
separate converter model.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import matplotlib.pyplot as plt

import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DynamicIntegrationMethod,
    RmsInitializationMethod,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCPVSourceAveraged
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.shunt_template import ShuntLoadBuild
from VeraGridEngine.Templates.Rms.vsc_gfm import VscGfmLossBuild
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup

import rms_gfl_validation as base


RFCAP = 1e6
CF = 0.05
RF = 0.02
LF = 0.15
RC = 0.01
LC = 0.10


def create_grid():
    circuit = vge.MultiCircuit(name='RMS GFM VSC validation')

    grid_bus = vge.Bus(name='Grid Bus (AC)', Vnom=230.0, is_slack=True)
    load_bus = vge.Bus(name='Load Bus (AC)', Vnom=230.0)
    filter_bus = vge.Bus(name='Filter Bus (AC)', Vnom=230.0)
    vsc_bus = vge.Bus(name='VSC Bus (AC)', Vnom=230.0)
    dc_bus = vge.Bus(name='DC Bus', Vnom=320.0, is_dc=True)
    for bus in (grid_bus, load_bus, filter_bus, vsc_bus, dc_bus):
        circuit.add_bus(bus)

    gen = vge.Generator(name='Grid Generator', P=3.0, vset=1.0)
    circuit.add_generator(grid_bus, gen)

    dc_source = vge.Generator(name='DC Source', P=4.0)
    circuit.add_generator(dc_bus, dc_source)

    load = vge.Load(name='Grid Load', P=3.0, Q=0.2)
    circuit.add_load(bus=load_bus, api_obj=load)

    line_grid_load = vge.Line(
        name='Line Grid-Load',
        bus_from=grid_bus,
        bus_to=load_bus,
        r=0.01,
        x=0.04,
        b=0.0,
        rate=100.0,
    )
    circuit.add_line(line_grid_load)

    line_vsc_filter = vge.Line(
        name='Line VSC-Filter',
        bus_from=vsc_bus,
        bus_to=filter_bus,
        r=RF,
        x=LF,
        b=0.0,
        rate=100.0,
    )
    circuit.add_line(line_vsc_filter)

    shunt = vge.Shunt(name='Filter Shunt', G=100.0 / RFCAP, B=100.0 * CF)
    circuit.add_shunt(bus=filter_bus, api_obj=shunt)

    line_filter_grid = vge.Line(
        name='Line Filter-Grid',
        bus_from=filter_bus,
        bus_to=grid_bus,
        r=RC,
        x=LC,
        b=0.0,
        rate=100.0,
    )
    circuit.add_line(line_filter_grid)

    vsc = vge.VSC(
        name='GFM VSC',
        bus_from=dc_bus,
        bus_to=vsc_bus,
        rate=100.0,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_val=1.02,
        control2_val=0.0,
        alpha1=0.0,
        alpha2=0.0,
        alpha3=0.0,
    )
    circuit.add_vsc(vsc)

    return circuit


def run_power_flow(circuit):
    options = vge.PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=200,
        tolerance=1e-11,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    return vge.power_flow(grid=circuit, options=options)


def connect_to_bus(vf, model, bus_model, mappings):
    vf.add_connections(
        [model.external_mapping[src] for src, _ in mappings],
        [bus_model.external_mapping[dst] for _, dst in mappings],
    )


def tune_event(block, vf, name, value):
    var = base.find_name_in_block(name, block)
    if var is not None:
        base.set_event_in_block(var, value, vf, block)


def initialize_rms_models(grid, pf_results):
    print("\n" + "-" * 70)
    print("Initializing RMS models for explicit-filter GFM VSC")
    print("-" * 70)

    vf = grid.var_factory

    for bus in grid.buses:
        if bus.rms_model.empty():
            initialize_bus_rms(bus, vf)

    for line in grid.lines:
        print(f"  Initializing line '{line.name}'...")
        line.rms_model = get_line_rms_template(vf, name=line.name).block
        set_rms_model(device=line, model=line.rms_model, var_factory=vf)
        connect_to_bus(vf, line.rms_model, line.bus_from.rms_model, [
            (VarPowerFlowReferenceType.Vmf, VarPowerFlowReferenceType.Vm),
            (VarPowerFlowReferenceType.Vaf, VarPowerFlowReferenceType.Va),
        ])
        connect_to_bus(vf, line.rms_model, line.bus_to.rms_model, [
            (VarPowerFlowReferenceType.Vmt, VarPowerFlowReferenceType.Vm),
            (VarPowerFlowReferenceType.Vat, VarPowerFlowReferenceType.Va),
        ])
        print("    ✓ Line RMS model assigned")

    for vsc in grid.vsc_devices:
        print(f"  Initializing VSC '{vsc.name}' with VscGfmLossBuild...")
        line_vsc_filter = next(line for line in grid.lines if line.name == 'Line VSC-Filter')
        line_filter_grid = next(line for line in grid.lines if line.name == 'Line Filter-Grid')
        current_power_inputs = [
            line_vsc_filter.rms_model.external_mapping[VarPowerFlowReferenceType.Pf],
            line_vsc_filter.rms_model.external_mapping[VarPowerFlowReferenceType.Qf],
            -line_filter_grid.rms_model.external_mapping[VarPowerFlowReferenceType.Pt],
            -line_filter_grid.rms_model.external_mapping[VarPowerFlowReferenceType.Qt],
        ]
        vsc.rms_model = VscGfmLossBuild(vfactory=vf, name=vsc.name, current_power_inputs=current_power_inputs).block
        filter_bus = grid.shunts[0].bus
        grid_bus = next(bus for bus in grid.buses if bus.is_slack and not bus.is_dc)
        connect_to_bus(vf, vsc.rms_model, vsc.bus_to.rms_model, [
            (VarPowerFlowReferenceType.Vmt, VarPowerFlowReferenceType.Vm),
            (VarPowerFlowReferenceType.Vat, VarPowerFlowReferenceType.Va),
        ])
        connect_to_bus(vf, vsc.rms_model, grid_bus.rms_model, [
            (VarPowerFlowReferenceType.Vmf, VarPowerFlowReferenceType.Vm),
            (VarPowerFlowReferenceType.Vaf, VarPowerFlowReferenceType.Va),
        ])
        vf.add_connections(
            [vsc.rms_model.in_vars[2], vsc.rms_model.in_vars[3]],
            [
                filter_bus.rms_model.external_mapping[VarPowerFlowReferenceType.Vm],
                filter_bus.rms_model.external_mapping[VarPowerFlowReferenceType.Va],
            ],
        )
        vf.add_connections(
            [vsc.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]],
            [vsc.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]],
        )
        tune_event(vsc.rms_model, vf, 'Rf', RF)
        tune_event(vsc.rms_model, vf, 'Lf', LF)
        tune_event(vsc.rms_model, vf, 'Rc', RC)
        tune_event(vsc.rms_model, vf, 'Lc', LC)
        tune_event(vsc.rms_model, vf, 'Cf', CF)
        tune_event(vsc.rms_model, vf, 'Rcap', RFCAP)
        tune_event(vsc.rms_model, vf, 'Kdp', 0.005)
        tune_event(vsc.rms_model, vf, 'Kdq', 0.005)
        tune_event(vsc.rms_model, vf, 'tau_P', 0.10)
        tune_event(vsc.rms_model, vf, 'tau_Q', 0.10)
        tune_event(vsc.rms_model, vf, 'a0', float(vsc.alpha1))
        tune_event(vsc.rms_model, vf, 'a1', float(vsc.alpha2))
        tune_event(vsc.rms_model, vf, 'a2', float(vsc.alpha3))

        filter_bus_idx = list(grid.buses).index(filter_bus)
        filter_vm = float(np.abs(pf_results.voltage[filter_bus_idx]))
        tune_event(vsc.rms_model, vf, 'V_ref', filter_vm)

        branch_list = list(grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True))
        filter_grid_idx = branch_list.index(line_filter_grid)
        p_ref = -float(np.real(pf_results.St[filter_grid_idx]) / grid.Sbase)
        q_ref = -float(np.imag(pf_results.St[filter_grid_idx]) / grid.Sbase)
        tune_event(vsc.rms_model, vf, 'P_ref', p_ref)
        tune_event(vsc.rms_model, vf, 'Q_ref', q_ref)

        print("    - Tuned GFM filter parameters from explicit network")
        print("    ✓ GFM VSC RMS model assigned")

    for shunt in grid.shunts:
        print(f"  Initializing shunt '{shunt.name}' from Rcap/Cf...")
        shunt.rms_model = ShuntLoadBuild(vfactory=vf, name=shunt.name).block
        shunt.rms_model.external_mapping.pop(VarPowerFlowReferenceType.Va, None)
        shunt.rms_model.in_vars = [shunt.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]]
        tune_event(shunt.rms_model, vf, 'g', 1.0 / RFCAP)
        tune_event(shunt.rms_model, vf, 'b', CF)
        p_sh = shunt.rms_model.external_mapping[VarPowerFlowReferenceType.P]
        q_sh = shunt.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
        vm_sh = shunt.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
        shunt.rms_model.init_eqs[p_sh] = -(1.0 / RFCAP) * vm_sh ** 2
        shunt.rms_model.init_eqs[q_sh] = CF * vm_sh ** 2
        set_rms_model(device=shunt, model=shunt.rms_model, var_factory=vf)
        connect_to_bus(vf, shunt.rms_model, shunt.bus.rms_model, [
            (VarPowerFlowReferenceType.Vm, VarPowerFlowReferenceType.Vm),
        ])
        print("    ✓ Shunt RMS model assigned")

    for gen in grid.generators:
        if gen.bus.is_dc:
            print(f"  Initializing DC source '{gen.name}' with DCPVSourceAveraged...")
            vdc = gen.bus.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]
            gen.rms_model = DCPVSourceAveraged(vfactory=vf, Vdc=vdc, name=gen.name).block

            vdc0 = float(np.abs(pf_results.voltage[list(grid.buses).index(gen.bus)]))
            pdc0 = float(gen.P) / grid.Sbase
            eta0 = 0.98
            vmp0 = max(0.8 * vdc0, min(0.98 * vdc0, vdc0 - 1e-3))
            ratio = max(vmp0 / (vdc0 + 1e-6), 1e-3)
            isc0 = abs(pdc0) / (eta0 * ratio + 1e-6) if abs(pdc0) > 0.0 else 0.0

            tune_event(gen.rms_model, vf, 'Cdc', 0.10)
            tune_event(gen.rms_model, vf, 'eta_boost', eta0)
            tune_event(gen.rms_model, vf, 'Vmp_stc', vmp0)
            tune_event(gen.rms_model, vf, 'Isc_stc', isc0)
            tune_event(gen.rms_model, vf, 'eps_v', 1e-6)
            tune_event(gen.rms_model, vf, 'G', 1000.0)
            tune_event(gen.rms_model, vf, 'T', 25.0)
            print("    ✓ DC source RMS model assigned")
        else:
            print(f"  Initializing AC generator '{gen.name}' with complete generator RMS template...")
            gen.rms_model = get_complete_generator_template_rms(vfactory=vf, name=gen.name).block
            set_rms_model(device=gen, model=gen.rms_model, var_factory=vf)
            print("    ✓ AC generator RMS model assigned")

    for load in grid.get_loads():
        if load.bus.is_dc:
            print(f"  Skipping DC load '{load.name}' for RMS; VscGfmBuild does not use Vdc dynamics")
            continue
        print(f"  Initializing load '{load.name}'...")
        load.rms_model = ZIPLoadBuild(
            vfactory=vf,
            name=load.name,
            Pl0=-float(load.P) / grid.Sbase,
            Ql0=-float(load.Q) / grid.Sbase,
        ).block
        set_rms_model(device=load, model=load.rms_model, var_factory=vf)
        vf.add_connections(
            [load.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]],
            [load.bus.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]],
        )
        print("    ✓ Load RMS model assigned")

    print("  ✓ All RMS models initialized successfully")


def run_rms_simulation(grid, pf_results):
    print("\n" + "-" * 70)
    print("Running RMS simulation")
    print("-" * 70)

    events_group = RmsEventsGroup(name='Explicit filter GFM validation')
    grid.add_rms_events_group(events_group)

    vsc = grid.vsc_devices[0]
    pref = base.find_name_in_block('P_ref', vsc.rms_model)
    if pref is not None:
        p_ref0 = -float(np.real(pf_results.St_vsc[0]) / grid.Sbase)
        p_ref_step = 0.005
        event = RmsEvent(device=vsc, parameter=pref, time=0.10, value=p_ref0 + p_ref_step, group=events_group)
        grid.add_rms_event(event)
        print(f"  Added event: VSC P_ref step {p_ref0:.6f} -> {p_ref0 + p_ref_step:.6f} at t=0.10s")

    options = vge.RmsOptions(
        simulation_time=10.0,
        time_step=0.001,
        tolerance=1e-7,
        max_iter=1000,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
    )

    driver = vge.RmsSimulationDriver(
        grid=grid,
        options=options,
        pf_results=pf_results,
        engine=vge.EngineType.VeraGrid,
    )
    driver.run()
    results = driver.results
    print(f"  ✓ RMS simulation complete (converged={results.converged})")
    plot_results(grid, results)


def plot_results(grid, results):
    if results is None or results.values is None or len(results.time_array) == 0:
        print("  No RMS results to plot")
        return

    y = results.values[:, :, 0]
    dt = 0.001
    t = np.arange(y.shape[0], dtype=float) * dt
    row_norm = np.max(np.abs(y), axis=1)
    valid_idx = np.where(np.isfinite(row_norm) & (row_norm > 0.0))[0]
    if len(valid_idx) == 0:
        valid_idx = np.asarray([0], dtype=int)
    uid2idx = results.uid2idx
    vsc = grid.vsc_devices[0]

    fig, axes = plt.subplots(3, 1, figsize=(12, 10))

    def plot_var(ax, block, name, label):
        var = base.find_name_in_block(name, block)
        if var is None:
            return False
        idx = uid2idx.get(var.uid)
        if idx is None:
            return False
        ax.plot(t[valid_idx], y[valid_idx, idx], label=label, linewidth=1.5)
        return True

    def get_trace(block, name):
        var = base.find_name_in_block(name, block)
        if var is None:
            return None
        idx = uid2idx.get(var.uid)
        if idx is None:
            return None
        return y[:, idx]

    last_idx = valid_idx[np.argmax(t[valid_idx])]

    print(f"  Last accepted RMS sample: t={t[last_idx]:.6f}s")
    for name in ['P', 'Q', 'omega', 'V', 'vd_f', 'vq_f', 'vd_c', 'vq_c', 'id_c', 'iq_c', 'id_c_ref', 'iq_c_ref', 'i_d_ref_sat', 'i_q_ref_sat']:
        trace = get_trace(vsc.rms_model, name)
        if trace is not None:
            print(f"    {name}: {trace[last_idx]:.6f}")

    plot_var(axes[0], vsc.rms_model, 'P', 'GFM P')
    plot_var(axes[0], vsc.rms_model, 'Q', 'GFM Q')
    plot_var(axes[1], vsc.rms_model, 'id_g', 'id_g')
    plot_var(axes[1], vsc.rms_model, 'iq_g', 'iq_g')
    plot_var(axes[1], vsc.rms_model, 'y_vd_ctrl', 'id_hat')
    plot_var(axes[1], vsc.rms_model, 'id_c_ref', 'id_c_ref')
    plot_var(axes[1], vsc.rms_model, 'iq_c_ref', 'iq_c_ref')
    id_hat = get_trace(vsc.rms_model, 'y_vd_ctrl')
    id_g = get_trace(vsc.rms_model, 'id_g')
    omega = get_trace(vsc.rms_model, 'omega')
    vq_f = get_trace(vsc.rms_model, 'vq_f')
    if id_hat is not None and id_g is not None and omega is not None and vq_f is not None:
        axes[1].plot(t[valid_idx], (id_hat + id_g - CF * omega * vq_f)[valid_idx], label='i_d_ref_raw', linewidth=1.5)
    plot_var(axes[2], vsc.rms_model, 'omega', 'omega')
    plot_var(axes[2], vsc.rms_model, 'omega_ref', 'omega_ref')
    plot_var(axes[2], vsc.rms_model, 'V', 'V')
    plot_var(axes[2], vsc.rms_model, 'V_ref', 'V_ref')
    plot_var(axes[2], vsc.rms_model, 'vd_f', 'vd_f')
    plot_var(axes[2], vsc.rms_model, 'vq_f', 'vq_f')

    axes[0].set_title('GFM Power')
    axes[1].set_title('Grid Currents')
    axes[2].set_title('Droop States')
    for ax in axes:
        ax.grid(True)
        ax.legend(loc='best')
        ax.axvline(x=0.10, color='red', linestyle=':', alpha=0.7)

    axes[-1].set_xlabel('Time (s)')
    plt.tight_layout()
    plt.savefig('rms_gfm_validation_results.png', dpi=150)
    plt.close(fig)
    print("  ✓ Plot saved to rms_gfm_validation_results.png")


if __name__ == '__main__':
    print("=" * 70)
    print("INVERTER EXAMPLE: GFM VSC with explicit line-shunt-line filter")
    print("=" * 70)

    grid = create_grid()
    pf_results = run_power_flow(grid)

    if not pf_results.converged:
        print("\nPower flow did not converge")
        sys.exit(1)

    print("\n" + "-" * 70)
    print("Bus Voltages (Power Flow)")
    print("-" * 70)
    for i, bus in enumerate(grid.buses):
        vm = np.abs(pf_results.voltage[i])
        va_deg = np.degrees(np.angle(pf_results.voltage[i]))
        bus_type = 'DC' if bus.is_dc else 'AC'
        print(f"  {bus.name:20s}: Vm={vm:.6f} pu, Va={va_deg:.4f} deg ({bus_type})")

    base.print_vsc_pf_loss_consistency(grid, pf_results)
    initialize_rms_models(grid, pf_results)
    run_rms_simulation(grid, pf_results)
