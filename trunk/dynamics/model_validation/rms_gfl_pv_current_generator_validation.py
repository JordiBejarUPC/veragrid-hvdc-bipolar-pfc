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
from VeraGridEngine.Templates.Rms.vsc_gfl_dclinked import build_vsc_rms
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCPVSourceAveraged
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


def patch_missing_vm_va_init_deps(model: Block, vm0: float, va0: float, vdc0: float) -> int:
    vm_names = {"Vm"}
    va_names = {"Va"}
    vdc_names = {"Vdc"}
    for v in model.in_vars:
        if v.ref == VarPowerFlowReferenceType.Vm:
            vm_names.add(v.name)
        elif v.ref == VarPowerFlowReferenceType.Va:
            va_names.add(v.name)
        elif v.ref == VarPowerFlowReferenceType.Vdc:
            vdc_names.add(v.name)
    for v in model.out_vars:
        if v.ref == VarPowerFlowReferenceType.Vdc:
            vdc_names.add(v.name)
        if v.name.startswith("Vdc_"):
            vdc_names.add(v.name)

    if not vm_names and not va_names:
        return 0

    patched_eqs = 0

    for key, expr in list(model.init_eqs.items()):
        mapping = {}
        for dep in get_expression_vars(expr):
            if dep.name in vm_names:
                mapping[dep] = sym.Const(vm0)
            elif dep.name in va_names:
                mapping[dep] = sym.Const(va0)
            elif dep.name in vdc_names:
                mapping[dep] = sym.Const(vdc0)

        if mapping:
            model.init_eqs[key] = expr.subs(mapping)
            patched_eqs += 1

    return patched_eqs


def build_pv_current_injection_model(vf, name: str) -> Block:
    vm = vf.add_var(f"Vm_{name}", VarPowerFlowReferenceType.Vm)
    va = vf.add_var(f"Va_{name}", VarPowerFlowReferenceType.Va)
    vdc = vf.add_var(f"Vdc_{name}")

    ir = vf.add_var(f"Ir_{name}")
    ii = vf.add_var(f"Ii_{name}")
    p = vf.add_var(f"P_{name}")
    q = vf.add_var(f"Q_{name}")

    trafo_block = TrafoGflBuild(
        vfactory=vf,
        name=f"{name}_trafo",
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
    ).block
    vsc_block = build_vsc_rms(vfactory=vf, name=f"{name}_vsc").block
    pv_block = DCPVSourceAveraged(vfactory=vf, Vdc=vdc, name=f"{name}_pv").block

    vm_f = trafo_block.external_mapping[VarPowerFlowReferenceType.Vmf]
    va_f = trafo_block.external_mapping[VarPowerFlowReferenceType.Vaf]
    vm_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Vmt]
    va_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Vat]
    vdc_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Vdc]
    pf_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Pf]
    pt_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Pt]
    qt_t = trafo_block.external_mapping[VarPowerFlowReferenceType.Qt]

    vm_vsc = vsc_block.external_mapping[VarPowerFlowReferenceType.Vm]
    pf_vsc = vsc_block.external_mapping[VarPowerFlowReferenceType.Pf]
    pt_vsc = vsc_block.external_mapping[VarPowerFlowReferenceType.Pt]

    pdc = pv_block.external_mapping[VarPowerFlowReferenceType.P]
    qt_ref = find_name_in_block("Qt_ref", vsc_block)

    grid.var_factory.add_connections([vm_f, va_f, vm_t, va_t, vdc_t], [vm, va, vm, va, vdc])
    grid.var_factory.add_connections([vm_vsc], [vm])

    vm_inner = find_name_in_block("Vm", trafo_block)
    va_inner = find_name_in_block("Va", trafo_block)
    if vm_inner is not None:
        grid.var_factory.add_connections([vm_inner], [vm])
    if va_inner is not None:
        grid.var_factory.add_connections([va_inner], [va])

    algebraic_eqs = [
        p + pt_t,
        q + qt_t,
        p - vm * (ir * sym.cos(va) + ii * sym.sin(va)),
        q + vm * (ii * sym.cos(va) - ir * sym.sin(va)),
        pt_vsc - pt_t,
        pf_vsc - pf_t,
        pdc + pt_t,
    ]
    if qt_ref is not None:
        algebraic_eqs.append(qt_ref + qt_t)

    extra_vars = []
    seen_extra_uids = set()
    init_exprs = list(trafo_block.init_eqs.values()) + list(vsc_block.init_eqs.values())
    for expr in init_exprs:
        for dep in get_expression_vars(expr):
            if dep.name == "Vm" and dep.uid not in seen_extra_uids:
                seen_extra_uids.add(dep.uid)
                extra_vars.append(dep)
                algebraic_eqs.append(dep - vm)
            elif dep.name == "Va" and dep.uid not in seen_extra_uids:
                seen_extra_uids.add(dep.uid)
                extra_vars.append(dep)
                algebraic_eqs.append(dep - va)

    model = Block(
        children=[trafo_block, vsc_block, pv_block],
        algebraic_vars=[ir, ii, p, q, vdc] + extra_vars,
        algebraic_eqs=algebraic_eqs,
        in_vars=[vm, va],
        out_vars=[p, q, ir, ii, vdc],
        external_mapping={
            VarPowerFlowReferenceType.Vm: vm,
            VarPowerFlowReferenceType.Va: va,
            VarPowerFlowReferenceType.P: p,
            VarPowerFlowReferenceType.Q: q,
        },
    )
    model.unify_blocks()

    known_uids = {v.uid for v in model.algebraic_vars + model.state_vars}
    for expr in list(model.init_eqs.values()):
        for dep in get_expression_vars(expr):
            if dep.uid in known_uids:
                continue
            if dep.name == "Vm":
                model.algebraic_vars.append(dep)
                model.algebraic_eqs.append(dep - vm)
                known_uids.add(dep.uid)
            elif dep.name == "Va":
                model.algebraic_vars.append(dep)
                model.algebraic_eqs.append(dep - va)
                known_uids.add(dep.uid)

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

    transformer = vge.Transformer2W(
        name="Transformer",
        bus_from=bus3_ac,
        bus_to=bus1_ac,
        rate=100.0,
        r=0.01,
        x=0.05,
    )
    grid.add_transformer2w(transformer)

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

    for br in list(grid.lines) + list(grid.transformers2w):
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

    pv_model = build_pv_current_injection_model(vf=vf, name=pv_gen.name.replace(" ", "_"))
    set_rms_model(device=pv_gen, model=pv_model, var_factory=vf)
    n_patched = patch_missing_vm_va_init_deps(pv_gen.rms_model, vm0=vm0, va0=va0, vdc0=vdc0)
    if n_patched:
        print(f"  + Patched {n_patched} missing Vm/Va init dependencies")

    if hasattr(pf_results, "Sbus") and len(pf_results.Sbus) > bus_idx:
        s0 = complex(pf_results.Sbus[bus_idx]) / grid.Sbase
    else:
        s0 = complex(float(pv_gen.P) / grid.Sbase, 0.0)

    p0 = float(np.real(s0))
    q0 = float(np.imag(s0))
    ir0 = (p0 * np.cos(va0) - q0 * np.sin(va0)) / max(vm0, 1e-6)
    ii0 = (p0 * np.sin(va0) + q0 * np.cos(va0)) / max(vm0, 1e-6)

    q_ref = find_name_in_block("Q_ref", pv_gen.rms_model)
    if q_ref is not None:
        set_event_in_block(q_ref, q0, vf, pv_gen.rms_model)

    qt_ref = find_name_in_block("Qt_ref", pv_gen.rms_model)
    if qt_ref is not None:
        set_event_in_block(qt_ref, -q0, vf, pv_gen.rms_model)

    kp_vdc = find_name_in_block("Kp_vdc", pv_gen.rms_model)
    ki_vdc = find_name_in_block("Ki_vdc", pv_gen.rms_model)
    if kp_vdc is not None:
        set_event_in_block(kp_vdc, 0.01, vf, pv_gen.rms_model)
    if ki_vdc is not None:
        set_event_in_block(ki_vdc, 0.006, vf, pv_gen.rms_model)

    vdc0 = max(float(np.abs(pf_results.voltage[bus_idx])), 0.2)
    pdc0 = max(abs(p0), 1e-4)
    eta0 = 0.98
    vmp0 = max(0.8 * vdc0, min(0.98 * vdc0, vdc0 - 1e-3))
    ratio = max(vmp0 / (vdc0 + 1e-6), 1e-3)
    isc0 = max(pdc0 / (eta0 * ratio + 1e-6), 1e-4)
    duty0 = float(np.clip(1.0 - (vmp0 / (vdc0 + 1e-6)), 0.0, 1.0))

    cdc = find_name_in_block("Cdc", pv_gen.rms_model)
    eta = find_name_in_block("eta_boost", pv_gen.rms_model)
    vmp = find_name_in_block("Vmp_stc", pv_gen.rms_model)
    isc = find_name_in_block("Isc_stc", pv_gen.rms_model)
    eps_v = find_name_in_block("eps_v", pv_gen.rms_model)
    g = find_name_in_block("G", pv_gen.rms_model)
    t = find_name_in_block("T", pv_gen.rms_model)
    if cdc is not None:
        set_event_in_block(cdc, 0.10, vf, pv_gen.rms_model)
    if eta is not None:
        set_event_in_block(eta, eta0, vf, pv_gen.rms_model)
    if vmp is not None:
        set_event_in_block(vmp, vmp0, vf, pv_gen.rms_model)
    if isc is not None:
        set_event_in_block(isc, isc0, vf, pv_gen.rms_model)
    if eps_v is not None:
        set_event_in_block(eps_v, 1e-6, vf, pv_gen.rms_model)
    if g is not None:
        set_event_in_block(g, 1000.0, vf, pv_gen.rms_model)
    if t is not None:
        set_event_in_block(t, 25.0, vf, pv_gen.rms_model)

    for var_name, var_value in [
        (f"P_{pv_gen.name.replace(' ', '_')}", p0),
        (f"Q_{pv_gen.name.replace(' ', '_')}", q0),
        (f"Ir_{pv_gen.name.replace(' ', '_')}", ir0),
        (f"Ii_{pv_gen.name.replace(' ', '_')}", ii0),
        (f"Vdc_{pv_gen.name.replace(' ', '_')}", vdc0),
        ("Vpv_ref", vmp0),
        ("duty", duty0),
    ]:
        vr = find_name_in_block(var_name, pv_gen.rms_model)
        if vr is not None:
            set_init_in_block(vr, float(var_value), pv_gen.rms_model)

    print(f"  + Aggregated PV RMS model: {pv_gen.name} (P0={p0:.6f}, Q0={q0:.6f})")

    for load in grid.get_loads():
        load_model = ZIPLoadBuild(
            vfactory=vf,
            name=load.name,
            Pl0=-float(load.P) / grid.Sbase,
            Ql0=-float(load.Q) / grid.Sbase,
        ).block
        set_rms_model(device=load, model=load_model, var_factory=vf)
        print(f"  + Load RMS model: {load.name}")


def run_rms_simulation(grid: vge.MultiCircuit, pf_results):
    print("\n" + "-" * 70)
    print("Running RMS Dynamic Simulation")
    print("-" * 70)

    events_group = RmsEventsGroup(name="PV irradiance ramp")
    grid.add_rms_events_group(events_group)

    pv_gen = grid.generators[1]
    g_var = find_name_in_block("G", pv_gen.rms_model)
    if g_var is not None and g_var in pv_gen.rms_model.event_dict:
        g0 = float(pv_gen.rms_model.event_dict[g_var].value)
        g1 = 700.0
        for k, t_evt in enumerate([0.10, 0.12, 0.14, 0.16], start=1):
            alpha = k / 4.0
            val = (1.0 - alpha) * g0 + alpha * g1
            evt = RmsEvent(device=pv_gen, parameter=g_var, time=t_evt, value=val, group=events_group)
            grid.add_rms_event(evt)
        print(f"  Added event: G ramp {g0:.1f} -> {g1:.1f} (0.10s-0.16s)")

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
        axes[0].legend(loc="best")

    if pv_gen is not None:
        p = values_for(pv_gen.rms_model, f"P_{sfx}")
        q = values_for(pv_gen.rms_model, f"Q_{sfx}")
        if p is not None:
            axes[1].plot(t, p, label="P", linewidth=1.5)
        if q is not None:
            axes[1].plot(t, q, label="Q", linewidth=1.5)
        axes[1].set_ylabel("P/Q")
        axes[1].grid(True)
        axes[1].legend(loc="best")

        ir = values_for(pv_gen.rms_model, f"Ir_{sfx}")
        ii = values_for(pv_gen.rms_model, f"Ii_{sfx}")
        if ir is not None:
            axes[2].plot(t, ir, label="Ir", linewidth=1.5)
        if ii is not None:
            axes[2].plot(t, ii, label="Ii", linewidth=1.5)
        axes[2].set_ylabel("I")
        axes[2].grid(True)
        axes[2].legend(loc="best")

        vdc = values_for(pv_gen.rms_model, f"Vdc_{sfx}")
        pdc = values_for(pv_gen.rms_model, "Pdc")
        if vdc is not None:
            axes[3].plot(t, vdc, label="Vdc", linewidth=1.5)
        if pdc is not None:
            axes[3].plot(t, pdc, label="Pdc", linewidth=1.5)

    axes[3].set_ylabel("DC")
    axes[3].set_xlabel("Time (s)")
    axes[3].grid(True)
    axes[3].legend(loc="best")

    for ax in axes:
        ax.axvline(x=0.10, color="red", linestyle=":", alpha=0.7)
        ax.set_xlim([0.0, t[-1]])

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
