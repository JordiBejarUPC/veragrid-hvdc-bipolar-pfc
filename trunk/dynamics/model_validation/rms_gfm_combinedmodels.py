#!/usr/bin/env python3
"""
RMS validation with a single aggregated GFM source model.

Internally, the model combines:
- GFM VSC (droop-based)
- averaged PV/DC source

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
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod, VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.vsc_gfm import VscGfmBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCPVSourceAveraged, DCSimpleSourceAveraged
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


def find_all_names_in_block(name: str, block: Block):
    found = []
    for var in block.algebraic_vars + block.state_vars + block.in_vars + block.out_vars + list(block.event_dict.keys()):
        if var.name == name:
            found.append(var)
    for mdl in block.children:
        found.extend(find_all_names_in_block(name, mdl))
    return found


def patch_missing_vm_va_init_deps(model: Block, vm0: float, va0: float) -> int:
    vm_names = {"Vm"}
    va_names = {"Va"}
    for v in model.in_vars:
        if v.ref == VarPowerFlowReferenceType.Vm:
            vm_names.add(v.name)
        elif v.ref == VarPowerFlowReferenceType.Va:
            va_names.add(v.name)

    patched_eqs = 0
    for key, expr in list(model.init_eqs.items()):
        if key.name not in vm_names and key.name not in va_names:
            continue
        if hasattr(expr, "uid") and expr.uid == key.uid:
            del model.init_eqs[key]
            patched_eqs += 1

    return patched_eqs


def build_gfm_current_injection_model(
    vf: vge.VarFactory,
    name: str,
) -> Block:
    vm = vf.add_var(f"Vm_{name}", VarPowerFlowReferenceType.Vm)
    va = vf.add_var(f"Va_{name}", VarPowerFlowReferenceType.Va)
    vdc = vf.add_var(f"Vdc_{name}")

    ir = vf.add_var(f"Ir_{name}")
    ii = vf.add_var(f"Ii_{name}")
    p = vf.add_var(f"P_{name}")
    q = vf.add_var(f"Q_{name}")

    vsc_block = VscGfmBuild(vfactory=vf, name=f"{name}_gfm").block
    pv_block = DCSimpleSourceAveraged(vfactory=vf, Vdc=vdc, name=f"{name}_pv").block

    vm_vsc = vsc_block.external_mapping[VarPowerFlowReferenceType.Vmt]
    va_vsc = vsc_block.external_mapping[VarPowerFlowReferenceType.Vat]
    vdc_vsc = vsc_block.external_mapping[VarPowerFlowReferenceType.Vdc]
    pf_vsc = vsc_block.external_mapping[VarPowerFlowReferenceType.Pf]
    pt_vsc = vsc_block.external_mapping[VarPowerFlowReferenceType.Pt]
    qt_vsc = vsc_block.external_mapping[VarPowerFlowReferenceType.Qt]

    pdc = pv_block.external_mapping[VarPowerFlowReferenceType.P]

    vsc_block.connect([vm_vsc, va_vsc, vdc_vsc], [vm, va, vdc])

    vm_eps = vm + vf.add_const(1e-9)
    algebraic_eqs = [
        p + pt_vsc,
        q + qt_vsc,
        pdc - pf_vsc,
    ]

    model = Block(
        children=[vsc_block, pv_block],
        algebraic_vars=[p, q, vdc],
        algebraic_eqs=algebraic_eqs,
        init_eqs={
            vdc: vm,
        },
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
    model.external_mapping[VarPowerFlowReferenceType.P] = p
    model.external_mapping[VarPowerFlowReferenceType.Q] = q

    pt_var = find_name_in_block("Pt_vsc", model)
    qt_var = find_name_in_block("Qt_vsc", model)
    pf_var = find_name_in_block("Pf_vsc", model)
    pdc_var = find_name_in_block("Pdc", model)
    vd_c_var = find_name_in_block("vd_c", model)
    vq_c_var = find_name_in_block("vq_c", model)
    id_c_var = find_name_in_block("id_c", model)
    iq_c_var = find_name_in_block("iq_c", model)
    idc_var = find_name_in_block("Idc", model)
    idc_src_var = find_name_in_block("Idc_src", model)
    if pt_var is not None:
        model.init_eqs[pt_var] = -p
    if qt_var is not None:
        model.init_eqs[qt_var] = -q
    pf_expr = None
    if vd_c_var is not None and vq_c_var is not None and id_c_var is not None and iq_c_var is not None:
        pf_expr = vf.add_const(1.5) * (vq_c_var * iq_c_var + vd_c_var * id_c_var)
    elif pdc_var is not None:
        pf_expr = pdc_var

    if pf_var is not None and pf_expr is not None:
        model.init_eqs[pf_var] = -pf_expr
    if pdc_var is not None and pf_var is not None:
        model.init_eqs[pdc_var] = pf_var
    elif pdc_var is not None and pf_expr is not None:
        model.init_eqs[pdc_var] = -pf_expr
    if idc_var is not None and pdc_var is not None:
        model.init_eqs[idc_var] = pdc_var / vdc
    if idc_src_var is not None and idc_var is not None:
        model.init_eqs[idc_src_var] = idc_var

    return model


def create_grid() -> vge.MultiCircuit:
    grid = vge.MultiCircuit(name="Grid 2 - GFM aggregated source")

    bus1_ac = vge.Bus(name="Bus 1 (AC)", Vnom=230.0, is_slack=True)
    bus3_ac = vge.Bus(name="Bus 1_1 (AC)", Vnom=230.0)
    bus4_ac = vge.Bus(name="Bus 4 (AC)", Vnom=230.0)
    grid.add_bus(bus1_ac)
    grid.add_bus(bus3_ac)
    grid.add_bus(bus4_ac)

    gen_slack = vge.Generator(name="Generator", P=10.0, vset=0.98)
    gen_gfm = vge.Generator(name="GFM Generator", P=4.0, vset=1.00)
    grid.add_generator(bus1_ac, gen_slack)
    grid.add_generator(bus3_ac, gen_gfm)

    ac_load = vge.Load(name="AC Load", P=3.0, Q=0.0)
    grid.add_load(bus=bus4_ac, api_obj=ac_load)

    line13 = vge.Line(
        name="Line13",
        bus_from=bus3_ac,
        bus_to=bus1_ac,
        rate=100.0,
        r=0.01,
        x=0.05,
    )
    grid.add_line(line13)

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
    print("Initializing RMS Models (aggregated GFM source)")
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

    gfm_gen = grid.generators[1]
    bus_idx = list(grid.buses).index(gfm_gen.bus)
    vm0 = float(np.abs(pf_results.voltage[bus_idx]))
    va0 = float(np.angle(pf_results.voltage[bus_idx]))

    if hasattr(pf_results, "Sbus") and len(pf_results.Sbus) > bus_idx:
        s0 = complex(pf_results.Sbus[bus_idx]) / grid.Sbase
    else:
        s0 = complex(float(gfm_gen.P) / grid.Sbase, 0.0)

    p0 = float(np.real(s0))
    q0 = float(np.imag(s0))

    gfm_model = build_gfm_current_injection_model(
        vf=vf,
        name=gfm_gen.name.replace(" ", "_"),
    )
    set_rms_model(device=gfm_gen, model=gfm_model, var_factory=vf)
    n_patched = patch_missing_vm_va_init_deps(gfm_gen.rms_model, vm0=vm0, va0=va0)
    if n_patched:
        print(f"  + Patched {n_patched} missing Vm/Va init dependencies")

    print(f"  + Aggregated GFM RMS model: {gfm_gen.name} (P0={p0:.6f}, Q0={q0:.6f})")

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

    events_group = RmsEventsGroup(name="GFM active-power step")
    grid.add_rms_events_group(events_group)

    gfm_gen = grid.generators[1]
    p_ref = find_name_in_block("P_ref", gfm_gen.rms_model)
    if p_ref is not None and p_ref in gfm_gen.rms_model.event_dict:
        bus_idx = list(grid.buses).index(gfm_gen.bus)
        if hasattr(pf_results, "Sbus") and len(pf_results.Sbus) > bus_idx:
            p0 = float(np.real(complex(pf_results.Sbus[bus_idx]) / grid.Sbase))
        else:
            p0 = float(gfm_gen.P) / grid.Sbase
        p1 = p0 + 0.02
        evt = RmsEvent(device=gfm_gen, parameter=p_ref, time=0.50, value=p1, group=events_group)
        grid.add_rms_event(evt)
        print(f"  Added event: P_ref step {p0:.6f} -> {p1:.6f} at t=0.50s")

    rms_options = vge.RmsOptions(
        simulation_time=5.0,
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


def plot_results(grid: vge.MultiCircuit, results, file_name: str = "rms_gfm_combinedmodels.png"):
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

    gfm_gen = grid.generators[1] if len(grid.generators) > 1 else None
    bus_gfm = gfm_gen.bus if gfm_gen is not None else None
    sfx = gfm_gen.name.replace(" ", "_") if gfm_gen is not None else ""

    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)

    if bus_gfm is not None:
        vm = values_for(bus_gfm.rms_model, "Vm")
        va = values_for(bus_gfm.rms_model, "Va")
        if vm is not None:
            axes[0].plot(t, vm, label="Vm", linewidth=1.5)
        if va is not None:
            axes[0].plot(t, np.degrees(va), label="Va (deg)", linewidth=1.5)
        axes[0].set_ylabel("Bus")
        axes[0].grid(True)
        axes[0].legend(loc="best")

    if gfm_gen is not None:
        p = values_for(gfm_gen.rms_model, f"P_{sfx}")
        q = values_for(gfm_gen.rms_model, f"Q_{sfx}")
        if p is not None:
            axes[1].plot(t, p, label="P", linewidth=1.5)
        if q is not None:
            axes[1].plot(t, q, label="Q", linewidth=1.5)
        axes[1].set_ylabel("P/Q")
        axes[1].grid(True)
        axes[1].legend(loc="best")

        ir = values_for(gfm_gen.rms_model, f"Ir_{sfx}")
        ii = values_for(gfm_gen.rms_model, f"Ii_{sfx}")
        if ir is not None:
            axes[2].plot(t, ir, label="Ir", linewidth=1.5)
        if ii is not None:
            axes[2].plot(t, ii, label="Ii", linewidth=1.5)
        axes[2].set_ylabel("I")
        axes[2].grid(True)
        axes[2].legend(loc="best")

        vdc = values_for(gfm_gen.rms_model, f"Vdc_{sfx}")
        pdc = values_for(gfm_gen.rms_model, "Pdc")
        if vdc is not None:
            axes[3].plot(t, vdc, label="Vdc", linewidth=1.5)
        if pdc is not None:
            axes[3].plot(t, pdc, label="Pdc", linewidth=1.5)

    axes[3].set_ylabel("DC")
    axes[3].set_xlabel("Time (s)")
    axes[3].grid(True)
    axes[3].legend(loc="best")

    for ax in axes:
        ax.axvline(x=0.50, color="red", linestyle=":", alpha=0.7)
        ax.set_xlim([0.0, t[-1]])

    plt.tight_layout()
    plt.savefig(file_name, dpi=150)
    plt.close(fig)
    print(f"Plot saved to {file_name}")


if __name__ == "__main__":
    print("=" * 70)
    print("INVERTER EQUIVALENT: Aggregated GFM source")
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
