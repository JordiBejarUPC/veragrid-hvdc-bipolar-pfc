#!/usr/bin/env python3
"""
RMS validation with a single PV generator model that internally aggregates:
- TrafoGFL
- VSC loss model
- averaged PV cell/DC source

Externally, the device behaves as a generator at one AC bus with P/Q output
mapped from an equivalent current injection (Ir, Ii).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import numpy as np
import matplotlib.pyplot as plt

import VeraGridEngine.api as vge
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Utils.Symbolic.symbolic import get_expression_vars
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod, VarPowerFlowReferenceType, ConverterControlType
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.vsc_gfl import TrafoGflBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCPVSourceAveraged, DCPowerLimitedSource
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if var.name == name:
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


def set_init_in_block(var, value, block: Block) -> bool:
    if (
        var in block.algebraic_vars
        or var in block.state_vars
        or var in block.in_vars
        or var in block.out_vars
        or var in block.event_dict
        or var in block.init_eqs
    ):
        block.init_eqs[var] = sym.Const(value)
        return True
    for mdl in block.children:
        if set_init_in_block(var, value, mdl):
            return True
    return False


def set_init_by_name_in_block(name: str, value: float, block: Block) -> int:
    set_count = 0
    for var in block.algebraic_vars + block.state_vars + block.in_vars + block.out_vars:
        if var.name == name:
            block.init_eqs[var] = sym.Const(value)
            set_count += 1
    for mdl in block.children:
        set_count += set_init_by_name_in_block(name, value, mdl)
    return set_count

def build_pv_current_injection_model(
        vf: vge.VarFactory,
        name: str,
    ) -> Block:
    vm_f_src = vf.add_var(f"Vm_f_{name}")
    va_f_src = vf.add_var(f"Va_f_{name}")
    vm_t_src = vf.add_var(f"Vm_t_{name}", VarPowerFlowReferenceType.Vm)
    va_t_src = vf.add_var(f"Va_t_{name}", VarPowerFlowReferenceType.Va)
    vdc = vf.add_var(f"Vdc_{name}")
    p_out = vf.add_var(f"P_{name}", VarPowerFlowReferenceType.P)
    q_out = vf.add_var(f"Q_{name}", VarPowerFlowReferenceType.Q)

    trafo_block = TrafoGflBuild(
        vfactory=vf,
        name=f"{name}_trafo",
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
    ).block
    pv_block = DCPowerLimitedSource(vfactory=vf, Vdc=vdc, name=f"{name}_pv").block

    vm_f = trafo_block.external_mapping[VarPowerFlowReferenceType.Vmf]
    va_f = trafo_block.external_mapping[VarPowerFlowReferenceType.Vaf]
    vm_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Vmt]
    va_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Vat]
    vdc_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Vdc]
    pf_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Pf]
    pt_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Pt]
    qt_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Qt]

    pdc = pv_block.external_mapping[VarPowerFlowReferenceType.P]
    del pv_block.external_mapping[VarPowerFlowReferenceType.P]

    vdc_pv = pv_block.external_mapping[VarPowerFlowReferenceType.Vdc]
    trafo_block.connect([vm_f, va_f, vm_t, va_t, vdc_t], [vm_f_src, va_f_src, vm_t_src, va_t_src, vdc])

    algebraic_eqs = [
        p_out + pt_t,
        q_out + qt_t,
        pdc - pf_t,
    ]

    model = Block(
        children=[trafo_block, pv_block],
        algebraic_vars=[p_out, q_out, vdc, vm_f_src, va_f_src],
        algebraic_eqs=algebraic_eqs,
        init_eqs={},
        in_vars=[vm_t_src, va_t_src],
        out_vars=[p_out, q_out, vdc],
        external_mapping={
            VarPowerFlowReferenceType.Vm: vm_t_src,
            VarPowerFlowReferenceType.Va: va_t_src,
        },
    )
    model.unify_blocks()
    model.external_mapping[VarPowerFlowReferenceType.P] = p_out
    model.external_mapping[VarPowerFlowReferenceType.Q] = q_out

    # Avoid registering bus variables as local algebraic variables after substitutions.
    bus_uids = {vm_t_src.uid, va_t_src.uid}
    model.algebraic_vars = [v for v in model.algebraic_vars if v.uid not in bus_uids]



    # Direct initialization (no name-based bulk setter)
    pt0 = -p_out
    qt0 = -q_out
    r_var = find_name_in_block("R", model)
    vm_var = find_name_in_block("Vm", model)
    if vm_var is None:
        vm_var = vm_t_src
    im0 = sym.sqrt(pt0 * pt0 + qt0 * qt0) / vm_var
    if r_var is not None:
        pf0 = -pt0 + r_var * (im0 ** 2)
    else:
        pf0 = -pt0

    # Source-side electrical states (from side)
    pdc_var = find_name_in_block("Pdc", model)

    # Bus-side interface states
    model.init_eqs[pdc_var] = pf0
    model.init_eqs[vdc] = pdc_var / im0

    # Internal power/control anchors
    pt_var = find_name_in_block("Pt_vsc_control", model)
    qt_var = find_name_in_block("Qt_vsc_control", model)
    pf_var = find_name_in_block("Pf_vsc_control", model)
    qf_var = find_name_in_block("Qf", model)
    pf_net_var = find_name_in_block("Pf", model)
    p_int_var = find_name_in_block("P", model)
    q_int_var = find_name_in_block("Q", model)
    theta_var = find_name_in_block("theta_vg", model)
    vd_c_var = find_name_in_block("v_d_c", model)
    vq_c_var = find_name_in_block("v_q_c", model)
    idc = find_name_in_block("Idc", model)
    idc_src = find_name_in_block("Idc_src", model)
    pdc_ref0_var = find_name_in_block("Pdc_ref0", model)
    pmax_var = find_name_in_block("Pmax", model)
    eps_v_var = find_name_in_block("eps_v", model)
    vdc_ref_var = find_name_in_block("Vdc_ref", model)
    u_vdc_ctrl_var = find_name_in_block("u_Vdc_ctrl", model)
    vdc_out_var = find_name_in_block(f"Vdc_{name}", model)

    model.init_eqs[vm_f_src] = sym.sqrt(vd_c_var * vd_c_var + vq_c_var * vq_c_var)
    model.init_eqs[va_f_src] = theta_var + sym.atan(vd_c_var / vq_c_var)
    model.init_eqs[idc] = im0
    if pdc_ref0_var is not None:
        model.init_eqs[pdc_ref0_var] = pdc_var
    if idc_src is not None and pdc_ref0_var is not None and pmax_var is not None and eps_v_var is not None:
        model.init_eqs[idc_src] = sym.hard_sat(pdc_ref0_var, -pmax_var, pmax_var) / (vdc + eps_v_var)
    elif idc_src is not None:
        model.init_eqs[idc_src] = idc
    if vdc_ref_var is not None:
        model.init_eqs[vdc_ref_var] = vdc_out_var if vdc_out_var is not None else vdc
    if u_vdc_ctrl_var is not None and vdc_ref_var is not None:
        model.init_eqs[u_vdc_ctrl_var] = (vdc_out_var if vdc_out_var is not None else vdc) - vdc_ref_var
    if pt_var is not None:
        model.init_eqs[pt_var] = pt0
    if qt_var is not None:
        model.init_eqs[qt_var] = qt0
    if pf_var is not None:
        model.init_eqs[pf_var] = pf0
    if qf_var is not None:
        model.init_eqs[qf_var] = q_out
    if pf_net_var is not None:
        model.init_eqs[pf_net_var] = p_out
    if p_int_var is not None:
        model.init_eqs[p_int_var] = p_out
    if q_int_var is not None:
        model.init_eqs[q_int_var] = q_out


    # Keep the DC source template initialization untouched.

    # Keep the phasor init derived from dq values.

    return model


def create_grid() -> vge.MultiCircuit:
    grid = vge.MultiCircuit(name="Grid 2 - PV aggregated generator")

    bus1_ac = vge.Bus(name="Bus 1 (AC)", Vnom=230.0, is_slack=True)
    bus3_ac = vge.Bus(name="Bus 1_1 (AC)", Vnom=230.0)
    bus4_ac = vge.Bus(name="Bus 4 (AC)", Vnom=230.0)
    grid.add_bus(bus1_ac)
    grid.add_bus(bus3_ac)
    grid.add_bus(bus4_ac)

    gen_slack = vge.Generator(name="Generator", P=10.0, vset=0.98)
    gen_pv = vge.Generator(name="PV Generator", P=4.0, vset=1.00)
    grid.add_generator(bus1_ac, gen_slack)
    grid.add_generator(bus3_ac, gen_pv)

    ac_load = vge.Load(name="AC Load", P=3.0, Q=0.0)
    grid.add_load(bus=bus4_ac, api_obj=ac_load)

    line13 = vge.Line(
        name="Line 13",
        bus_from=bus3_ac,
        bus_to=bus1_ac,
        rate=100.0,
        r=0.01,
        x=0.05,
    )

    line34 = vge.Line(
        name="Line 3-4",
        bus_from=bus3_ac,
        bus_to=bus4_ac,
        r=0.02,
        x=0.08,
        b=0.0,
        rate=100.0,
    )
    grid.add_line(line34)
    grid.add_line(line13)

    return grid


def run_power_flow(grid: vge.MultiCircuit):
    print("\nRunning Power Flow...")
    pf_options = vge.PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=100,
        tolerance=1e-11,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    return vge.power_flow(grid=grid, options=pf_options)


def initialize_rms_models(grid: vge.MultiCircuit, pf_results):
    print("\n" + "-" * 70)
    print("Initializing RMS Models (aggregated PV model)")
    print("-" * 70)

    vf = grid.var_factory

    for bus in grid.buses:
        if bus.rms_model.empty():
            initialize_bus_rms(bus, vf)

    for br in list(grid.lines):
        br_model = get_line_rms_template(vfactory=vf, name=br.name).block
        set_rms_model(device=br, model=br_model, var_factory=vf)
        print(f"  + Branch RMS model: {br.name}")

    slack_gen = grid.generators[0]
    slack_model = get_complete_generator_template_rms(vfactory=vf, name=slack_gen.name).block
    set_rms_model(device=slack_gen, model=slack_model, var_factory=vf)
    print(f"  + Slack generator RMS model: {slack_gen.name}")

    pv_gen = grid.generators[1]
    bus_idx = list(grid.buses).index(pv_gen.bus)
    vm0 = float(np.abs(pf_results.voltage[bus_idx]))
    va0 = float(np.angle(pf_results.voltage[bus_idx]))
    vdc0 = max(vm0, 0.2)

    pv_model = build_pv_current_injection_model(
        vf=vf,
        name=pv_gen.name.replace(" ", "_"),
    )
    set_rms_model(device=pv_gen, model=pv_model, var_factory=vf)
    for load in grid.get_loads():
        load_bus_idx = list(grid.buses).index(load.bus)
        load_vm0 = float(np.abs(pf_results.voltage[load_bus_idx]))
        load_model = ZIPLoadBuild(
            vfactory=vf,
            name=load.name,
            Pl0=-float(load.P) / grid.Sbase,
            Ql0=-float(load.Q) / grid.Sbase,
        ).block
        v0 = find_name_in_block("V0", load_model)
        if v0 is not None:
            set_event_in_block(v0, load_vm0, vf, load_model)
            load_model.init_eqs[v0] = sym.Const(load_vm0)
        set_rms_model(device=load, model=load_model, var_factory=vf)
        load_vm = load_model.external_mapping[VarPowerFlowReferenceType.Vm]
        bus_vm = load.bus.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
        vf.add_connections([load_vm], [bus_vm])
        print(f"  + Load RMS model: {load.name}")


def run_rms_simulation(grid: vge.MultiCircuit, pf_results):
    print("\n" + "-" * 70)
    print("Running RMS Dynamic Simulation")
    print("-" * 70)

    events_group = RmsEventsGroup(name="PV combined model events")
    grid.add_rms_events_group(events_group)

    rms_options = vge.RmsOptions(
        simulation_time=20.0,
        time_step=0.01,
        max_iter=30,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
    )

    rms_driver = vge.RmsSimulationDriver(
        grid=grid,
        options=rms_options,
        pf_results=pf_results,
        engine=vge.EngineType.VeraGrid,
    )
    rms_driver.run()
    results = rms_driver.results
    print(f"  + RMS simulation complete (converged={results.converged})")
    return results


def plot_results(grid: vge.MultiCircuit, results, file_name: str = "rms_gfl_pv_current_generator_validation.png"):
    if results is None or results.values is None or len(results.time_array) == 0:
        print("No results to plot")
        return

    t_raw = np.array(results.time_array)
    if np.issubdtype(t_raw.dtype, np.datetime64):
        t = ((t_raw - t_raw[0]) / np.timedelta64(1, "s")).astype(float)
    else:
        t = t_raw.astype(float)

    y = results.values[:, :, 0]
    n = min(len(t), y.shape[0])
    if n == 0:
        print("No aligned samples to plot")
        return

    t = t[:n]
    y = y[:n, :]
    uid2idx = results.uid2idx

    def values_for(block: Block, var_name: str):
        var = find_name_in_block(var_name, block)
        if var is None:
            return None
        idx = uid2idx.get(var.uid)
        if idx is None:
            return None
        return y[:, idx]

    pv_gen = grid.generators[1] if len(grid.generators) > 1 else None
    bus_pv = pv_gen.bus if pv_gen is not None else None
    sfx = pv_gen.name.replace(" ", "_") if pv_gen is not None else ""

    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)

    if bus_pv is not None:
        vm = values_for(bus_pv.rms_model, "Vm")
        va = values_for(bus_pv.rms_model, "Va")
        if vm is not None:
            axes[0].plot(t, vm, label="Vm", linewidth=1.5)
        if va is not None:
            axes[0].plot(t, np.degrees(va), label="Va (deg)", linewidth=1.5)
        axes[0].set_ylabel("Bus")
        axes[0].grid(True)

    if pv_gen is not None:
        p = values_for(pv_gen.rms_model, f"P_{sfx}")
        q = values_for(pv_gen.rms_model, f"Q_{sfx}")
        if p is not None:
            axes[1].plot(t, p, label="P", linewidth=1.5)
        if q is not None:
            axes[1].plot(t, q, label="Q", linewidth=1.5)
        axes[1].set_ylabel("P/Q")
        axes[1].grid(True)

        ir = values_for(pv_gen.rms_model, f"Ir_{sfx}")
        ii = values_for(pv_gen.rms_model, f"Ii_{sfx}")
        if ir is not None:
            axes[2].plot(t, ir, label="Ir", linewidth=1.5)
        if ii is not None:
            axes[2].plot(t, ii, label="Ii", linewidth=1.5)
        axes[2].set_ylabel("I")
        axes[2].grid(True)

        vdc = values_for(pv_gen.rms_model, f"Vdc_{sfx}")
        pdc = values_for(pv_gen.rms_model, "Pdc")
        if vdc is not None:
            axes[3].plot(t, vdc, label="Vdc", linewidth=1.5)
        if pdc is not None:
            axes[3].plot(t, pdc, label="Pdc", linewidth=1.5)

    axes[3].set_ylabel("DC")
    axes[3].set_xlabel("Time (s)")
    axes[3].grid(True)

    for ax in axes:
        ax.axvline(x=0.10, color="red", linestyle=":", alpha=0.7)
        ax.set_xlim([0.0, t[-1]])

    for ax in axes:
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles, labels, loc="best")

    plt.tight_layout()
    plt.savefig(file_name, dpi=150)
    plt.close(fig)
    print(f"Plot saved to {file_name}")


if __name__ == "__main__":
    print("=" * 70)
    print("INVERTER EQUIVALENT: Aggregated PV current-injection generator")
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
        print(f"  {bus.name:20s}: Vm={vm:.6f} pu, Va={va_deg:.4f} deg")

    initialize_rms_models(grid, pf_results)
    results = run_rms_simulation(grid, pf_results)
    plot_results(grid, results)
