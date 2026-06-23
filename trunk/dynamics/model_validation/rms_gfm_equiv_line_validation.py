#!/usr/bin/env python3
"""RMS validation for GFM VSC using one equivalent pi line for the LCL filter."""

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
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.shunt_template import ShuntLoadBuild
from VeraGridEngine.Templates.Rms.vsc_gfm import VscGfmLossBuild

import rms_gfm_validation as explicit


def equivalent_lcl_pi():
    z1 = complex(explicit.RF, explicit.LF)
    z2 = complex(explicit.RC, explicit.LC)
    ysh = complex(1.0 / explicit.RFCAP, explicit.CF)
    y1 = 1.0 / z1
    y2 = 1.0 / z2
    yn = y1 + y2 + ysh
    y12 = -(y1 * y2) / yn
    y11 = y1 - y1 * y1 / yn
    y22 = y2 - y2 * y2 / yn
    y_series = -y12
    z_series = 1.0 / y_series
    y_sh_from = y11 - y_series
    y_sh_to = y22 - y_series
    return z_series.real, z_series.imag, y_sh_from, y_sh_to


def hidden_filter_voltage_from_pf(grid, pf_results):
    buses = {bus.name: i for i, bus in enumerate(grid.buses)}
    vc = pf_results.voltage[buses['VSC Bus (AC)']]
    vg = pf_results.voltage[buses['Grid Bus (AC)']]
    y1 = 1.0 / complex(explicit.RF, explicit.LF)
    y2 = 1.0 / complex(explicit.RC, explicit.LC)
    ysh = complex(1.0 / explicit.RFCAP, explicit.CF)
    return (y1 * vc + y2 * vg) / (y1 + y2 + ysh)


def hidden_grid_side_power_from_pf(grid, pf_results):
    buses = {bus.name: i for i, bus in enumerate(grid.buses)}
    vf = hidden_filter_voltage_from_pf(grid, pf_results)
    vg = pf_results.voltage[buses['Grid Bus (AC)']]
    y = 1.0 / complex(explicit.RC, explicit.LC)
    s_grid_into_line = vg * np.conj((vg - vf) * y)
    return -s_grid_into_line.real, -s_grid_into_line.imag


def create_grid():
    circuit = vge.MultiCircuit(name='RMS GFM VSC equivalent-line validation')

    grid_bus = vge.Bus(name='Grid Bus (AC)', Vnom=230.0, is_slack=True)
    load_bus = vge.Bus(name='Load Bus (AC)', Vnom=230.0)
    vsc_bus = vge.Bus(name='VSC Bus (AC)', Vnom=230.0)
    dc_bus = vge.Bus(name='DC Bus', Vnom=320.0, is_dc=True)
    for bus in (grid_bus, load_bus, vsc_bus, dc_bus):
        circuit.add_bus(bus)

    circuit.add_generator(grid_bus, vge.Generator(name='Grid Generator', P=3.0, vset=1.0))
    circuit.add_generator(dc_bus, vge.Generator(name='DC Source', P=4.0))
    circuit.add_load(bus=load_bus, api_obj=vge.Load(name='Grid Load', P=3.0, Q=0.2))

    circuit.add_line(vge.Line(
        name='Line Grid-Load', bus_from=grid_bus, bus_to=load_bus,
        r=0.01, x=0.04, b=0.0, rate=100.0,
    ))

    r_eq, x_eq, y_sh_from, y_sh_to = equivalent_lcl_pi()
    circuit.add_line(vge.Line(
        name='Equivalent LCL Line', bus_from=vsc_bus, bus_to=grid_bus,
        r=r_eq, x=x_eq, b=0.0, rate=100.0,
    ))

    circuit.add_shunt(bus=vsc_bus, api_obj=vge.Shunt(
        name='Equivalent LCL Shunt From',
        G=100.0 * y_sh_from.real,
        B=100.0 * y_sh_from.imag,
    ))
    circuit.add_shunt(bus=grid_bus, api_obj=vge.Shunt(
        name='Equivalent LCL Shunt To',
        G=100.0 * y_sh_to.real,
        B=100.0 * y_sh_to.imag,
    ))

    circuit.add_vsc(vge.VSC(
        name='GFM VSC', bus_from=dc_bus, bus_to=vsc_bus, rate=100.0,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_val=1.02,
        control2_val=0.0,
        alpha1=0.0,
        alpha2=0.0,
        alpha3=0.0,
    ))
    return circuit


def initialize_rms_models(grid, pf_results):
    vf = grid.var_factory
    for bus in grid.buses:
        if bus.rms_model.empty():
            explicit.initialize_bus_rms(bus, vf)

    for line in grid.lines:
        line.rms_model = get_line_rms_template(vf, name=line.name).block
        explicit.set_rms_model(device=line, model=line.rms_model, var_factory=vf)
        explicit.connect_to_bus(vf, line.rms_model, line.bus_from.rms_model, [
            (VarPowerFlowReferenceType.Vmf, VarPowerFlowReferenceType.Vm),
            (VarPowerFlowReferenceType.Vaf, VarPowerFlowReferenceType.Va),
        ])
        explicit.connect_to_bus(vf, line.rms_model, line.bus_to.rms_model, [
            (VarPowerFlowReferenceType.Vmt, VarPowerFlowReferenceType.Vm),
            (VarPowerFlowReferenceType.Vat, VarPowerFlowReferenceType.Va),
        ])

    shunt_admittances = {
        'Equivalent LCL Shunt From': equivalent_lcl_pi()[2],
        'Equivalent LCL Shunt To': equivalent_lcl_pi()[3],
    }
    for shunt in grid.shunts:
        shunt.rms_model = ShuntLoadBuild(vfactory=vf, name=shunt.name).block
        shunt.rms_model.external_mapping.pop(VarPowerFlowReferenceType.Va, None)
        shunt.rms_model.in_vars = [shunt.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]]
        explicit.set_rms_model(device=shunt, model=shunt.rms_model, var_factory=vf)
        admittance = shunt_admittances[shunt.name]
        rms_admittance = -admittance if shunt.name == 'Equivalent LCL Shunt To' else admittance
        explicit.tune_event(shunt.rms_model, vf, 'g', float(rms_admittance.real))
        explicit.tune_event(shunt.rms_model, vf, 'b', float(rms_admittance.imag))
        vm = shunt.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
        p_sh = shunt.rms_model.external_mapping[VarPowerFlowReferenceType.P]
        q_sh = shunt.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
        shunt.rms_model.init_eqs[p_sh] = -float(rms_admittance.real) * vm ** 2
        shunt.rms_model.init_eqs[q_sh] = float(rms_admittance.imag) * vm ** 2
        explicit.connect_to_bus(vf, shunt.rms_model, shunt.bus.rms_model, [
            (VarPowerFlowReferenceType.Vm, VarPowerFlowReferenceType.Vm),
        ])

    eq_line = next(line for line in grid.lines if line.name == 'Equivalent LCL Line')
    for vsc in grid.vsc_devices:
        current_power_inputs = [
            eq_line.rms_model.external_mapping[VarPowerFlowReferenceType.Pf],
            eq_line.rms_model.external_mapping[VarPowerFlowReferenceType.Qf],
            -eq_line.rms_model.external_mapping[VarPowerFlowReferenceType.Pt],
            -eq_line.rms_model.external_mapping[VarPowerFlowReferenceType.Qt],
        ]
        vsc.rms_model = VscGfmLossBuild(
            vfactory=vf,
            name=vsc.name,
            current_power_inputs=current_power_inputs,
            reconstruct_filter_voltage=True,
        ).block
        explicit.connect_to_bus(vf, vsc.rms_model, vsc.bus_to.rms_model, [
            (VarPowerFlowReferenceType.Vmt, VarPowerFlowReferenceType.Vm),
            (VarPowerFlowReferenceType.Vat, VarPowerFlowReferenceType.Va),
        ])
        explicit.connect_to_bus(vf, vsc.rms_model, grid.buses[0].rms_model, [
            (VarPowerFlowReferenceType.Vmf, VarPowerFlowReferenceType.Vm),
            (VarPowerFlowReferenceType.Vaf, VarPowerFlowReferenceType.Va),
        ])
        vf.add_connections(
            [vsc.rms_model.in_vars[2], vsc.rms_model.in_vars[3]],
            [grid.buses[0].rms_model.external_mapping[VarPowerFlowReferenceType.Vm],
             grid.buses[0].rms_model.external_mapping[VarPowerFlowReferenceType.Va]],
        )
        vf.add_connections(
            [vsc.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]],
            [vsc.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]],
        )
        explicit.tune_event(vsc.rms_model, vf, 'V_ref', float(np.abs(hidden_filter_voltage_from_pf(grid, pf_results))))
        explicit.tune_event(vsc.rms_model, vf, 'Kdp', 0.005)
        explicit.tune_event(vsc.rms_model, vf, 'Kdq', 0.005)
        explicit.tune_event(vsc.rms_model, vf, 'tau_P', 0.10)
        explicit.tune_event(vsc.rms_model, vf, 'tau_Q', 0.10)
        explicit.tune_event(vsc.rms_model, vf, 'a0', float(vsc.alpha1))
        explicit.tune_event(vsc.rms_model, vf, 'a1', float(vsc.alpha2))
        explicit.tune_event(vsc.rms_model, vf, 'a2', float(vsc.alpha3))

        p_ref, q_ref = hidden_grid_side_power_from_pf(grid, pf_results)
        explicit.tune_event(vsc.rms_model, vf, 'P_ref', float(p_ref))
        explicit.tune_event(vsc.rms_model, vf, 'Q_ref', float(q_ref))

    for gen in grid.generators:
        if gen.bus.is_dc:
            vdc = gen.bus.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]
            gen.rms_model = explicit.DCPVSourceAveraged(vfactory=vf, Vdc=vdc, name=gen.name).block
            vdc0 = float(np.abs(pf_results.voltage[list(grid.buses).index(gen.bus)]))
            pdc0 = float(gen.P) / grid.Sbase
            eta0 = 0.98
            vmp0 = max(0.8 * vdc0, min(0.98 * vdc0, vdc0 - 1e-3))
            ratio = max(vmp0 / (vdc0 + 1e-6), 1e-3)
            isc0 = abs(pdc0) / (eta0 * ratio + 1e-6) if abs(pdc0) > 0.0 else 0.0
            explicit.tune_event(gen.rms_model, vf, 'Cdc', 0.10)
            explicit.tune_event(gen.rms_model, vf, 'eta_boost', eta0)
            explicit.tune_event(gen.rms_model, vf, 'Vmp_stc', vmp0)
            explicit.tune_event(gen.rms_model, vf, 'Isc_stc', isc0)
            explicit.tune_event(gen.rms_model, vf, 'eps_v', 1e-6)
            explicit.tune_event(gen.rms_model, vf, 'G', 1000.0)
            explicit.tune_event(gen.rms_model, vf, 'T', 25.0)
        else:
            gen.rms_model = explicit.get_complete_generator_template_rms(vfactory=vf, name=gen.name).block
            explicit.set_rms_model(device=gen, model=gen.rms_model, var_factory=vf)

    for load in grid.get_loads():
        load.rms_model = explicit.ZIPLoadBuild(
            vfactory=vf, name=load.name,
            Pl0=-float(load.P) / grid.Sbase,
            Ql0=-float(load.Q) / grid.Sbase,
        ).block
        explicit.set_rms_model(device=load, model=load.rms_model, var_factory=vf)
        vf.add_connections(
            [load.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]],
            [load.bus.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]],
        )


def print_last_sample(grid, results, dt):
    if results is None or results.values is None or len(results.time_array) == 0:
        print('No RMS result samples available')
        return

    y = results.values[:, :, 0]
    row_norm = np.max(np.abs(y), axis=1)
    valid_idx = np.where(np.isfinite(row_norm) & (row_norm > 0.0))[0]
    if len(valid_idx) == 0:
        print('No finite RMS samples available')
        return

    last_idx = valid_idx[-1]
    t = last_idx * dt
    uid2idx = results.uid2idx
    vsc = grid.vsc_devices[0]
    print(f'Last available RMS sample: t={t:.6f}s')
    for name in ['P', 'Q', 'omega', 'V', 'vd_f', 'vq_f', 'vd_c', 'vq_c', 'id_c', 'iq_c', 'id_g', 'iq_g', 'id_c_ref', 'iq_c_ref']:
        var = explicit.base.find_name_in_block(name, vsc.rms_model)
        if var is None:
            continue
        idx = uid2idx.get(var.uid)
        if idx is None:
            continue
        print(f'  {name}: {y[last_idx, idx]:.9f}')


def plot_results(grid, results, dt, filename):
    if results is None or results.values is None or len(results.time_array) == 0:
        print('No RMS result samples to plot')
        return

    y = results.values[:, :, 0]
    row_norm = np.max(np.abs(y), axis=1)
    valid_idx = np.where(np.isfinite(row_norm) & (row_norm > 0.0))[0]
    if len(valid_idx) == 0:
        print('No finite RMS samples to plot')
        return

    t = np.arange(y.shape[0], dtype=float) * dt
    uid2idx = results.uid2idx
    vsc = grid.vsc_devices[0]

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    def plot_var(ax, name, label=None):
        var = explicit.base.find_name_in_block(name, vsc.rms_model)
        if var is None:
            return False
        idx = uid2idx.get(var.uid)
        if idx is None:
            return False
        ax.plot(t[valid_idx], y[valid_idx, idx], label=label or name, linewidth=1.4)
        return True

    for name in ['P', 'Q']:
        plot_var(axes[0], name)
    axes[0].set_title('Power')

    for name in ['id_c', 'iq_c', 'id_g', 'iq_g', 'id_c_ref', 'iq_c_ref']:
        plot_var(axes[1], name)
    axes[1].set_title('Currents')

    for name in ['omega', 'V', 'vd_f', 'vq_f', 'vd_c', 'vq_c']:
        plot_var(axes[2], name)
    axes[2].set_title('Voltage and Droop')

    for ax in axes:
        ax.grid(True)
        ax.legend(loc='best')
        ax.axvline(x=0.10, color='red', linestyle=':', alpha=0.7)
    axes[-1].set_xlabel('Time (s)')
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close(fig)
    print(f'Plot saved to {filename}')


def run_rms_simulation(grid, pf_results, simulation_time=10.0):
    events_group = RmsEventsGroup(name='Equivalent filter GFM validation')
    grid.add_rms_events_group(events_group)

    vsc = grid.vsc_devices[0]
    pref = explicit.base.find_name_in_block('P_ref', vsc.rms_model)
    if pref is not None:
        p_ref0, _ = hidden_grid_side_power_from_pf(grid, pf_results)
        event = RmsEvent(device=vsc, parameter=pref, time=0.10, value=p_ref0 + 0.005, group=events_group)
        grid.add_rms_event(event)
        print(f'Added event: VSC P_ref step {p_ref0:.6f} -> {p_ref0 + 0.005:.6f} at t=0.10s')

    dt = 0.001
    options = vge.RmsOptions(
        simulation_time=simulation_time,
        time_step=dt,
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
    try:
        driver.run()
    except Exception as exc:
        print(f'RMS simulation failed: {exc}')
    print_last_sample(grid, driver.results, dt)
    plot_results(grid, driver.results, dt, 'rms_gfm_equiv_line_results.png')
    return driver


if __name__ == '__main__':
    r_eq, x_eq, y_sh_from, y_sh_to = equivalent_lcl_pi()
    print(f'Equivalent series: r={r_eq:.9f}, x={x_eq:.9f}')
    print(f'Equivalent shunt from: g={y_sh_from.real:.9f}, b={y_sh_from.imag:.9f}')
    print(f'Equivalent shunt to:   g={y_sh_to.real:.9f}, b={y_sh_to.imag:.9f}')
    grid = create_grid()
    pf_results = explicit.run_power_flow(grid)
    print(f'Power flow converged: {pf_results.converged}')
    for i, bus in enumerate(grid.buses):
        print(f'  {bus.name}: Vm={abs(pf_results.voltage[i]):.6f}, Va={np.degrees(np.angle(pf_results.voltage[i])):.4f} deg')
    initialize_rms_models(grid, pf_results)
    driver = run_rms_simulation(grid, pf_results)
    if driver.results is None or not np.all(driver.results.converged):
        print('Retrying short run before the observed failure point...')
        grid = create_grid()
        pf_results = explicit.run_power_flow(grid)
        initialize_rms_models(grid, pf_results)
        short_driver = run_rms_simulation(grid, pf_results, simulation_time=1.0)
        plot_results(grid, short_driver.results, 0.001, 'rms_gfm_equiv_line_short_results.png')
