#!/usr/bin/env python3
"""
RMS validation using Grid 2 topology with TrafoGFL + simple VSC RMS model.

Topology:
AC Bus 1 -> Transformer (TrafoGFL) -> AC Bus 3 -> VSC -> DC Bus 2
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import numpy as np
import matplotlib.pyplot as plt
import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import ConverterControlType, VarPowerFlowRefferenceType
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Templates.Rms.vsc_gfl_dclinked import build_vsc_rms
from VeraGridEngine.Templates.Rms.vsc_gfl import TrafoGflBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCCurrentSource
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
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


def set_event_in_block(var, value, vf, block: Block) -> bool:
    if var in block.event_dict:
        block.event_dict[var] = vf.add_const(value)
        return True
    for mdl in block.children:
        if set_event_in_block(var, value, vf, mdl):
            return True
    return False


def get_event_value_by_name(block: Block, name: str):
    for var, eq in block.event_dict.items():
        if var.name == name and hasattr(eq, 'value'):
            return eq.value
    for mdl in block.children:
        val = get_event_value_by_name(mdl, name)
        if val is not None:
            return val
    return None


def print_gfl_init_consistency(grid2, pf_results):
    if len(grid2.transformers2w) == 0 or len(grid2.vsc_devices) == 0:
        return

    trafo = grid2.transformers2w[0]
    vsc = grid2.vsc_devices[0]

    bus_names = [b.name for b in grid2.buses]
    idx_f = bus_names.index(trafo.bus_from.name)
    idx_t = bus_names.index(trafo.bus_to.name)

    vm_f = np.abs(pf_results.voltage[idx_f])
    va_f = np.angle(pf_results.voltage[idx_f])
    vm_t = np.abs(pf_results.voltage[idx_t])
    va_t = np.angle(pf_results.voltage[idx_t])

    # For TrafoGflBuild initialization, P/Q are tied to transformer "to" side
    # (VarPowerFlowRefferenceType.Pt/Qt on the transformer model), not St_vsc.
    branch_list = list(grid2.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True))
    branch_idx = branch_list.index(trafo)
    pt_vsc = float(np.real(pf_results.St[branch_idx]) / grid2.Sbase)
    qt_vsc = float(np.imag(pf_results.St[branch_idx]) / grid2.Sbase)

    # Parameters used by build_gfl_converter_model defaults
    k_pq = get_event_value_by_name(trafo.rms_model, 'k_pq')
    R = get_event_value_by_name(trafo.rms_model, 'R')
    L = get_event_value_by_name(trafo.rms_model, 'L')
    if k_pq is None:
        k_pq = 1.5
    if R is None:
        R = 0.01
    if L is None:
        L = 0.05

    k_pq = 1.0
    R = 0.01
    L = 0.05

    P = -pt_vsc
    Q = -qt_vsc
    theta = va_t 
    omega = 1.0
    k = 1.0
    v_d_g = 0.0
    v_q_g = vm_t
    i_q = (1.0 / k_pq) * P / v_q_g
    i_d = (1.0 / k_pq) * Q / v_q_g

    # Estimate dq currents from transformer branch current phasor
    # using the same dq frame angle (theta = Va_t).
    i_d_from_if = None
    i_q_from_if = None
    i_d_from_it = None
    i_q_from_it = None
    if trafo in branch_list:
        branch_idx = branch_list.index(trafo)
        if branch_idx < len(pf_results.If):
            i_f = pf_results.If[branch_idx]
            i_d_from_if = np.abs(i_f) * np.sin(np.angle(i_f) - theta)
            i_q_from_if = np.abs(i_f) * np.cos(np.angle(i_f) - theta)
        if branch_idx < len(pf_results.It):
            i_t = pf_results.It[branch_idx]
            i_d_from_it = np.abs(i_t) * np.sin(np.angle(i_t) - theta)
            i_q_from_it = np.abs(i_t) * np.cos(np.angle(i_t) - theta)

    v_d_c_from_pq = v_d_g - ( R * i_d - omega * L * i_q)
    v_q_c_from_pq = v_q_g - (-R * i_q - omega * L * i_d)

    v_d_c_from_internal_bus = vm_f * np.sin(va_f - theta)
    v_q_c_from_internal_bus = vm_f * np.cos(va_f - theta)

    print("\n" + "-" * 70)
    print("GFL Init Consistency Check")
    print("-" * 70)
    print(f"  Vm_f={vm_f:.6f}, Va_f={va_f:.6f} rad, Vm_t={vm_t:.6f}, Va_t={va_t:.6f} rad")
    print(f"  Pt_vsc={pt_vsc:.6f}, Qt_vsc={qt_vsc:.6f} -> P={P:.6f}, Q={Q:.6f}")
    print(f"  k_pq={k_pq:.6f}, R={R:.6f}, L={L:.6f}, omega={omega:.6f}")
    print(f"  i_d={i_d:.6f}, i_q={i_q:.6f}")
    if i_d_from_if is not None and i_q_from_if is not None:
        print(f"  i_d/i_q from If phasor = {i_d_from_if:.6f}, {i_q_from_if:.6f}")
    if i_d_from_it is not None and i_q_from_it is not None:
        print(f"  i_d/i_q from It phasor = {i_d_from_it:.6f}, {i_q_from_it:.6f}")
    print(f"  v_d_c from P/Q init = {v_d_c_from_pq:.9f}")
    print(f"  v_q_c from P/Q init = {v_q_c_from_pq:.9f}")
    print(f"  v_d_c from internal bus = {v_d_c_from_internal_bus:.9f}")
    print(f"  v_q_c from internal bus = {v_q_c_from_internal_bus:.9f}")
    print(f"  mismatch dv_d = {v_d_c_from_pq - v_d_c_from_internal_bus:.6f}")
    print(f"  mismatch dv_q = {v_q_c_from_pq - v_q_c_from_internal_bus:.6f}")


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
        bus_from=bus3_ac,
        bus_to=bus1_ac,
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


def initialize_grid2_rms_models(grid2, pf_results):
    print("\n" + "-" * 70)
    print("Initializing RMS Models for Grid 2 with TrafoGFL + simple VSC model")
    print("-" * 70)

    vf = grid2.rms_var_factory

    for vsc in grid2.vsc_devices:
        print(f"  Initializing VSC '{vsc.name}' with build_vsc_rms...")
        vsc.rms_model = build_vsc_rms(vfactory=vf, name=vsc.name).block
        # Avoid automatic branch->vsc wiring from overriding our custom inputs.
        im_in = vsc.rms_model.in_vars[0]
        pt_in = vsc.rms_model.in_vars[1]
        vsc.rms_model.in_vars = [vf.add_var(f"dummy_in_{vsc.name}"), im_in, pt_in]
        print("    ✓ VSC RMS model assigned")

    for trafo in grid2.transformers2w:
        print(f"  Initializing Transformer '{trafo.name}' with TrafoGflBuild...")
        trafo.rms_model = TrafoGflBuild(
            vfactory=vf,
            name=trafo.name,
            control1=ConverterControlType.Vm_dc,
            control2=ConverterControlType.Qac,
        ).block
        trafo.rms_model.unify_blocks()

        if trafo.bus_from.rms_model.empty():
            initialize_bus_rms(trafo.bus_from, vf)
        if trafo.bus_to.rms_model.empty():
            initialize_bus_rms(trafo.bus_to, vf)

        vm_f = trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmf]
        va_f = trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Vaf]
        vm_t = trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmt]
        va_t = trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Vat]

        bus_vm_f = trafo.bus_from.rms_model.external_mapping[VarPowerFlowRefferenceType.Vm]
        bus_va_f = trafo.bus_from.rms_model.external_mapping[VarPowerFlowRefferenceType.Va]
        bus_vm_t = trafo.bus_to.rms_model.external_mapping[VarPowerFlowRefferenceType.Vm]
        bus_va_t = trafo.bus_to.rms_model.external_mapping[VarPowerFlowRefferenceType.Va]

        trafo.rms_model.connect([vm_f, va_f, vm_t, va_t], [bus_vm_f, bus_va_f, bus_vm_t, bus_va_t])

        # Force TrafoGFL reactive initialization to match PF branch "to" side.
        branch_list = list(grid2.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True))
        if trafo in branch_list:
            branch_idx = branch_list.index(trafo)
            qt_pf = pf_results.St[branch_idx].imag / grid2.Sbase
            qt_var = trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Qt]
            trafo.rms_model.init_eqs[qt_var] = vf.add_const(float(qt_pf))

            q_ref_var = find_name_in_block('Q_ref', trafo.rms_model)
            if q_ref_var is not None:
                set_event_in_block(q_ref_var, float(-qt_pf), vf, trafo.rms_model)
        print("    ✓ Transformer RMS model assigned")

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
            gen_model = get_complete_generator_template_rms(vfactory=vf, name=gen.name).block
            set_rms_model(device=gen, model=gen_model, var_factory=vf)

    if len(grid2.vsc_devices) > 0 and len(grid2.transformers2w) > 0:
        vsc = grid2.vsc_devices[0]
        trafo = grid2.transformers2w[0]
        if hasattr(vsc.bus_from, 'rms_model') and vsc.bus_from.rms_model is not None:
            if hasattr(trafo.rms_model, 'in_vars') and len(trafo.rms_model.in_vars) > 0:
                im_trafo = find_name_in_block('Im_vsc_control', trafo.rms_model)
                if im_trafo is not None:
                    vsc.rms_model.connect([vsc.rms_model.in_vars[1]], [im_trafo])

                vdc_trafo = trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Vdc]
                vdc_bus = vsc.bus_from.rms_model.out_vars[0]
                trafo.rms_model.connect([vdc_trafo], [vdc_bus])
                pf_trafo = trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Pf]
                pt_vsc = vsc.rms_model.in_vars[2]
                vsc.rms_model.connect([pt_vsc], [pf_trafo])
                pt_vsc_var = vsc.rms_model.external_mapping[VarPowerFlowRefferenceType.Pt]
                #vsc.rms_model.algebraic_eqs.append(pt_vsc_var - pf_trafo)

                trafo_qt = trafo.rms_model.external_mapping[VarPowerFlowRefferenceType.Qt]
                #trafo.rms_model.algebraic_eqs.append(trafo_qt)
                print("  ✓ Connected transformer to DC bus")

    print("  ✓ All RMS models initialized successfully")


def run_rms_simulation(grid2, pf_results):
    print("\n" + "-" * 70)
    print("Running RMS Dynamic Simulation on Grid 2")
    print("-" * 70)

    events_group = RmsEventsGroup(name="Grid2 RMS Simulation")
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
                value=0.015,
                group=events_group,
            )
            grid2.add_rms_event(event)
            print("  Added event: Idc_src0 step at t=0.1s")

    rms_options = vge.RmsOptions(
        simulation_time=3,
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

    plot_rms_results(grid2, results)


def plot_rms_results(grid2, results):
    print("\n" + "-" * 70)
    print("Plotting RMS Results")
    print("-" * 70)

    if results is None or results.values is None or len(results.time_array) == 0:
        print("  ⚠ No results to plot")
        return

    t = np.array(results.time_array)
    y = results.values[:, :, 0]

    # Skip the final sample to keep plots available even if
    # the last integration step fails to converge.
    n_samples = min(len(t), y.shape[0])
    if n_samples == 0:
        print("  ⚠ No samples available to plot")
        return
    n_plot = n_samples - 200 if n_samples > 1 else n_samples
    t_plot = t[:n_plot]
    y_plot = y[:n_plot, :]
    uid2idx = results.uid2idx

    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    ax1, ax2, ax3 = axes

    trafo = grid2.transformers2w[0] if len(grid2.transformers2w) > 0 else None
    vsc = grid2.vsc_devices[0] if len(grid2.vsc_devices) > 0 else None
    dc_gen = next((g for g in grid2.generators if g.bus.is_dc), None)

    def plot_var(ax, block, var_name, label):
        var = find_name_in_block(var_name, block)
        if var is None:
            return False
        idx = uid2idx.get(var.uid)
        if idx is None:
            return False
        ax.plot(t_plot, y_plot[:, idx], label=label, linewidth=1.5)
        return True

    plotted1 = False
    plotted2 = False
    plotted3 = False

    if trafo is not None and trafo.rms_model is not None:
        plotted1 |= plot_var(ax1, trafo.rms_model, 'v_d_c', 'v_d_c')
        plotted1 |= plot_var(ax1, trafo.rms_model, 'v_q_c', 'v_q_c')
        plotted1 |= plot_var(ax1, trafo.rms_model, 'i_d', 'i_d')
        plotted1 |= plot_var(ax1, trafo.rms_model, 'i_q', 'i_q')
        plotted1 |= plot_var(ax1, trafo.rms_model, 'i_d_ref', 'i_d_ref')
        plotted1 |= plot_var(ax1, trafo.rms_model, 'i_q_ref', 'i_q_ref')
        plotted1 |= plot_var(ax1, trafo.rms_model, 'i_d_ref_sat', 'i_d_ref_sat')
        plotted1 |= plot_var(ax1, trafo.rms_model, 'i_q_ref_sat', 'i_q_ref_sat')
        plotted1 |= plot_var(ax1, trafo.rms_model, 'y_vd_hat', 'vd_hat')
        plotted1 |= plot_var(ax1, trafo.rms_model, 'y_vq_hat', 'vq_hat')

        plotted2 |= plot_var(ax2, trafo.rms_model, 'Pf_vsc_control', 'Pf_vsc_control')
        plotted2 |= plot_var(ax2, trafo.rms_model, 'Pt_vsc_control', 'Pt_vsc_control')
        plotted2 |= plot_var(ax2, trafo.rms_model, 'Qt_vsc_control', 'Qt_vsc_control')

    if vsc is not None and vsc.rms_model is not None:
        plotted2 |= plot_var(ax2, vsc.rms_model, 'Pf_vsc', 'Pf_vsc')
        plotted2 |= plot_var(ax2, vsc.rms_model, 'Pt', 'Pt')

    if dc_gen is not None and dc_gen.rms_model is not None:
        plotted3 |= plot_var(ax3, dc_gen.rms_model, 'Idc', 'Idc')
        plotted3 |= plot_var(ax3, dc_gen.rms_model, 'Idc_src', 'Idc_src')
        plotted3 |= plot_var(ax3, dc_gen.rms_model, 'Pdc', 'Pdc')
        if dc_gen.bus.rms_model is not None:
            plotted3 |= plot_var(ax3, dc_gen.bus.rms_model, 'Vdc', 'Vdc_bus')

    if plotted1:
        ax1.set_title('TrafoGFL dq Variables')
        ax1.set_ylabel('pu')
        ax1.grid(True)
        ax1.legend(loc='upper right')

    if plotted2:
        ax2.set_title('Power Variables')
        ax2.set_ylabel('pu')
        ax2.grid(True)
        ax2.legend(loc='upper right')

    if plotted3:
        ax3.set_title('DC Variables')
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('pu')
        ax3.grid(True)
        ax3.legend(loc='upper right')
        ax3.axvline(x=0.1, color='red', linestyle=':', alpha=0.7)

    for ax in axes:
        ax.set_xlim([0, t_plot[-1]])

    plt.tight_layout()
    plt.show()
    plt.savefig('rms_gfl_validation_results.png', dpi=150)
    plt.close(fig)
    print("  ✓ Plot saved to rms_gfl_validation_results.png")


if __name__ == "__main__":
    print("=" * 70)
    print("INVERTER EXAMPLE: Transformer (TrafoGFL) + simple VSC RMS")
    print("=" * 70)

    grid2 = create_grid_2()
    results2 = run_power_flow(grid2, "Grid 2")

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

    print("\n" + "-" * 70)
    print("Transformer Taps (Power Flow)")
    print("-" * 70)
    for trafo in grid2.transformers2w:
        print(f"  {trafo.name:20s}: tap_module={trafo.tap_module:.6f}, tap_phase={trafo.tap_phase:.6f} rad")

    initialize_grid2_rms_models(grid2, results2)
    print_gfl_init_consistency(grid2, results2)
    run_rms_simulation(grid2, results2)
