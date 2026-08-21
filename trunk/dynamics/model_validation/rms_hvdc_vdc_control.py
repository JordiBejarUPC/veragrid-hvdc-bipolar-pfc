#!/usr/bin/env python3
"""Point-to-point HVDC Vdc-control example using VeraGrid RMS models.

This is the RMS counterpart of ``dynamics_emt/scripting_hvdc_vdc_control.py``.
Each converter station uses the same split used by ``rms_gfl_validation.py``:
a TrafoGFL control/electrical model plus the DC-linked VSC power-balance model.
"""

from __future__ import annotations

import os
import sys
from typing import Optional
from types import SimpleNamespace

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import VeraGridEngine.api as vge
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Templates.Rms.voltage_source_template import VoltageSourceBuild
from VeraGridEngine.Templates.Rms.vsc_gfl import TrafoGflBuild
from VeraGridEngine.Templates.Rms.vsc_gfl_dclinked import build_vsc_rms
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DynamicIntegrationMethod,
    RmsInitializationMethod,
    SolverType,
    VarPowerFlowReferenceType,
)


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict):
        if var.name == name:
            return var
    for child in block.children:
        result = find_name_in_block(name, child)
        if result is not None:
            return result
    return None


def set_event_value(block: Block, name: str, value: float, vf) -> bool:
    var = find_name_in_block(name, block)
    if var is None:
        return False
    if var in block.event_dict:
        block.event_dict[var] = vf.add_const(value)
        return True
    for child in block.children:
        if set_event_value(child, name, value, vf):
            return True
    return False


def create_grid() -> vge.MultiCircuit:
    sbase = 100.0
    ac_kv = 90.0
    dc_kv = 145.0
    zbase_ac = ac_kv * ac_kv / sbase
    omega = 2.0 * np.pi * 50.0

    grid = vge.MultiCircuit(name="Point-to-point HVDC RMS Vdc-control example", Sbase=sbase, fbase=50.0)
    ac_grid_1 = vge.Bus(name="Bus_Grid_1", Vnom=ac_kv, is_slack=True)
    ac_vsc_1 = vge.Bus(name="Bus_VSC_1", Vnom=ac_kv)
    dc_1 = vge.Bus(name="Bus_DC_1", Vnom=dc_kv, is_dc=True)
    dc_2 = vge.Bus(name="Bus_DC_2", Vnom=dc_kv, is_dc=True)
    ac_vsc_2 = vge.Bus(name="Bus_VSC_2", Vnom=ac_kv)
    ac_grid_2 = vge.Bus(name="Bus_Grid_2", Vnom=ac_kv, is_slack=True)
    for bus in (ac_grid_1, ac_vsc_1, dc_1, dc_2, ac_vsc_2, ac_grid_2):
        grid.add_bus(bus)

    grid_r_pu = (4.8 * 0.669) / zbase_ac
    grid_x_pu = omega * (0.052 * 0.669) / zbase_ac
    for idx, bus in enumerate((ac_grid_1, ac_grid_2), 1):
        grid.add_generator(bus, vge.Generator(
            name=f"Generator_Grid_{idx}", P=0.0, vset=1.0, Snom=sbase,
            freq=50.0, r1=grid_r_pu, x1=grid_x_pu,
        ))

    # TrafoGFL is the RMS converter control/electrical interface.
    for idx, bus_vsc, bus_grid in ((1, ac_vsc_1, ac_grid_1), (2, ac_vsc_2, ac_grid_2)):
        grid.add_transformer2w(vge.Transformer2W(
            name=f"TrafoGFL_{idx}", bus_from=bus_vsc, bus_to=bus_grid,
            rate=sbase, r=0.01, x=0.05,
        ))

    vsc_1 = vge.VSC(
        name="VSC_1", bus_from=dc_1, bus_to=ac_vsc_1, rate=sbase,
        control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Qac,
        control1_val=1.0, control2_val=0.0,
    )
    vsc_2 = vge.VSC(
        name="VSC_2", bus_from=dc_2, bus_to=ac_vsc_2, rate=sbase,
        control1=ConverterControlType.Pdc, control2=ConverterControlType.Qac,
        # RMS DC buses are algebraic (no EMT capacitor state), so initialize
        # the link at a non-zero transfer to avoid the I_dc=0 singular point.
        control1_val=20.0, control2_val=0.0,
    )
    grid.add_vsc(vsc_1)
    grid.add_vsc(vsc_2)
    for vsc in (vsc_1, vsc_2):
        vsc.alpha1 = 0.0
        vsc.alpha2 = 0.0
        vsc.alpha3 = 0.0

    zbase_dc = dc_kv * dc_kv / sbase
    grid.add_dc_line(vge.DcLine(
        name="HVDC_Line", bus_from=dc_1, bus_to=dc_2,
        r=(0.5 + 0.25 + 0.4) / zbase_dc, rate=sbase,
    ))
    return grid


def run_power_flow(grid):
    options = vge.PowerFlowOptions(
        solver_type=SolverType.NR, retry_with_other_methods=True, verbose=False,
        tolerance=1.0e-8, max_iter=100, control_q=False,
        control_taps_modules=False, control_taps_phase=False,
        orthogonalize_controls=False,
    )
    return vge.power_flow(grid=grid, options=options)


def initialize_rms_models(grid, pf_results) -> None:
    vf = grid.var_factory
    for bus in grid.buses:
        initialize_bus_rms(bus, vf)

    for generator in grid.generators:
        # A stiff external-grid voltage source is the RMS equivalent of the
        # EMT Thevenin sources used by the reference case.
        model = VoltageSourceBuild(vf, name=generator.name).block
        set_rms_model(generator, model, vf)

    for index, (vsc, trafo) in enumerate(zip(grid.vsc_devices, grid.transformers2w)):
        vsc.rms_model = build_vsc_rms(vfactory=vf, name=vsc.name).block
        # Put the capacitor inside the DC-linked VSC power balance:
        # Pf_total = Pf_converter + Cdc*Vdc*dVdc/dt.  Since the original
        # converter equation is Pf_converter + Pt - Ploss = 0, the terminal
        # equation becomes Pf_total + Pt - Ploss - Cdc*Vdc*dVdc/dt = 0.
        vdc_bus = vsc.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]
        dvdc_dt = vf.add_diff_var(f"dVdc_dt_{vsc.name}", base_var=vdc_bus)
        cdc = vf.add_var(f"Cdc_{vsc.name}")
        vsc_power_block = vsc.rms_model.children[0]
        vsc_power_block.algebraic_eqs[0] = (
            vsc_power_block.algebraic_eqs[0] - cdc * vdc_bus * dvdc_dt
        )
        vsc_power_block.diff_vars.append(dvdc_dt)
        vsc_power_block.diff_init_eqs[dvdc_dt] = vf.add_const(0.0)
        vsc_power_block.parameters[cdc] = vf.add_const(0.40)
        qt_pf = float(np.imag(pf_results.St_vsc[index]) / grid.Sbase)
        set_event_value(vsc.rms_model, "Qt_ref", qt_pf, vf)
        grid.var_factory.add_connections(
            [vsc.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]],
            [vsc.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]],
        )

        trafo.rms_model = TrafoGflBuild(
            vfactory=vf, name=trafo.name,
            control1=vsc.control1, control2=vsc.control2,
        ).block
        trafo.rms_model.unify_blocks()
        # The polarity test confirms the template's positive Vdc gains are
        # restoring. The previous loop was simply far too slow to arrest the
        # constant-power-load voltage collapse.
        set_event_value(trafo.rms_model, "Kp_vdc", 0.20, vf)
        set_event_value(trafo.rms_model, "Ki_vdc", 1.00, vf)
        set_event_value(trafo.rms_model, "Kp_icl", 0.20, vf)
        set_event_value(trafo.rms_model, "Ki_icl", 5.00, vf)
        set_event_value(trafo.rms_model, "Kp_pol", 0.02, vf)
        set_event_value(trafo.rms_model, "Ki_pol", 0.10, vf)

        mapping = trafo.rms_model.external_mapping
        grid.var_factory.add_connections(
            [mapping[VarPowerFlowReferenceType.Vmf], mapping[VarPowerFlowReferenceType.Vaf],
             mapping[VarPowerFlowReferenceType.Vmt], mapping[VarPowerFlowReferenceType.Vat]],
            [trafo.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Vm],
             trafo.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Va],
             trafo.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Vm],
             trafo.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Va]],
        )
        vdc_trafo = mapping[VarPowerFlowReferenceType.Vdc]
        vdc_bus = vsc.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]
        grid.var_factory.add_connections([vdc_trafo], [vdc_bus])

        branches = list(grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True))
        branch_idx = branches.index(trafo)
        qt = float(np.imag(pf_results.St[branch_idx]) / grid.Sbase)
        trafo.rms_model.init_eqs[mapping[VarPowerFlowReferenceType.Qt]] = vf.add_const(qt)
        set_event_value(trafo.rms_model, "Q_ref", -qt, vf)

    dc_line = grid.dc_lines[0]
    # Equivalent to get_dc_line_rms_template, with the equations attached to
    # the returned root block (the current template drops its local child).
    model = Block(name=dc_line.name)
    vdc_f = vf.add_var("Vdcf", reference=VarPowerFlowReferenceType.Vmf)
    vdc_t = vf.add_var("Vdct", reference=VarPowerFlowReferenceType.Vmt)
    i_dc = vf.add_var("If_dc", reference=VarPowerFlowReferenceType.If_dc)
    p_f = vf.add_var("Pf_dc", reference=VarPowerFlowReferenceType.Pf)
    p_t = vf.add_var("Pt_dc", reference=VarPowerFlowReferenceType.Pt)
    di_dt = vf.add_diff_var("dIf_dcdt", base_var=i_dc)
    r_dc = vf.add_var("r_dc")
    l_dc = vf.add_var("l_dc")
    model.parameters = {r_dc: vf.add_const(dc_line.R), l_dc: vf.add_const(0.05)}
    model.algebraic_vars = [i_dc, p_f, p_t]
    model.diff_vars = [di_dt]
    model.algebraic_eqs = [
        l_dc * di_dt + r_dc * i_dc - (vdc_f - vdc_t),
        p_f - vdc_f * i_dc,
        p_t + vdc_t * i_dc,
    ]
    model.init_eqs = {i_dc: (vdc_f - vdc_t) / r_dc, p_f: vdc_f * i_dc, p_t: -vdc_t * i_dc}
    model.diff_init_eqs = {di_dt: sym.Const(0.0)}
    model.in_vars = [vdc_f, vdc_t]
    model.out_vars = [i_dc, p_f, p_t]
    model.external_mapping = {
        VarPowerFlowReferenceType.Vmf: vdc_f, VarPowerFlowReferenceType.Vmt: vdc_t,
        VarPowerFlowReferenceType.If_dc: i_dc, VarPowerFlowReferenceType.Pf: p_f,
        VarPowerFlowReferenceType.Pt: p_t,
    }
    dc_line.rms_model = model
    # Register the line's algebraic/differential variables with the RMS compiler.
    set_rms_model(dc_line, dc_line.rms_model, vf)
    line_map = dc_line.rms_model.external_mapping
    grid.var_factory.add_connections(
        [line_map[VarPowerFlowReferenceType.Vmf], line_map[VarPowerFlowReferenceType.Vmt]],
        [dc_line.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc],
         dc_line.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]],
    )


def values_for(results, block: Block, name: str) -> Optional[np.ndarray]:
    var = find_name_in_block(name, block)
    idx = None if var is None else results.uid2idx.get(var.uid)
    return None if idx is None else np.asarray(results.values[:, idx, 0], dtype=float)


def save_plots(grid, results, output_dir: str, p_event_time: float) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    t = np.asarray(results.time_array)
    if np.issubdtype(t.dtype, np.datetime64):
        t = ((t - t[0]) / np.timedelta64(1, "s")).astype(float)
    else:
        t = t.astype(float)

    paths = []
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for bus, label in ((grid.dc_lines[0].bus_from, "Vdc bus 1"), (grid.dc_lines[0].bus_to, "Vdc bus 2")):
        trace = values_for(results, bus.rms_model, "Vdc")
        if trace is not None:
            axes[0].plot(t, trace, label=label)
    axes[0].set_ylabel("Voltage [pu]")

    for vsc in grid.vsc_devices:
        for name in ("Pf_vsc", "Pt"):
            trace = values_for(results, vsc.rms_model, name)
            if trace is not None:
                axes[1].plot(t, trace, label=f"{vsc.name} {name}")
    dc_line = grid.dc_lines[0]
    vdc_from = values_for(results, dc_line.bus_from.rms_model, "Vdc")
    vdc_to = values_for(results, dc_line.bus_to.rms_model, "Vdc")
    idc = values_for(results, dc_line.rms_model, "If_dc")
    if vdc_from is not None and vdc_to is not None and idc is not None:
        axes[1].plot(t, vdc_from * idc, "--", linewidth=1.8, label="Pdc sending = Vdc1·Idc")
        axes[1].plot(t, vdc_to * idc, "--", linewidth=1.8, label="Pdc receiving = Vdc2·Idc")
    axes[1].axvline(p_event_time, color="k", linestyle=":", label="VSC2 Pdc step")
    axes[1].set_ylabel("Power [pu]")

    line = grid.dc_lines[0]
    for name in ("If_dc", "Pf", "Pt"):
        trace = values_for(results, line.rms_model, name)
        if trace is not None:
            axes[2].plot(t, trace, label=name)
    axes[2].set_ylabel("DC line [pu]")
    axes[2].set_xlabel("Time [s]")
    for ax in axes:
        ax.grid(True)
        ax.legend(loc="best")
    fig.tight_layout()
    path = os.path.join(output_dir, "hvdc_vdc_control_rms.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    paths.append(path)

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for ax, bus, title in zip(axes, (grid.buses[0], grid.buses[-1]), ("Grid 1", "Grid 2")):
        for name in ("Vm", "Va"):
            trace = values_for(results, bus.rms_model, name)
            if trace is not None:
                ax.plot(t, trace, label=name)
        ax.set_title(f"{title} RMS bus voltage")
        ax.grid(True)
        ax.legend(loc="best")
    axes[-1].set_xlabel("Time [s]")
    fig.tight_layout()
    path = os.path.join(output_dir, "hvdc_ac_bus_voltages_rms.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    paths.append(path)
    return paths


def run_simulation(
    simulation_time: float = 10.0,
    time_step: float = 0.002,
    p_event_time: float = 0.5,
    p_step_pu: float = -0.01,
):
    grid = create_grid()
    pf_results = run_power_flow(grid)
    if not pf_results.converged:
        raise RuntimeError("RMS HVDC power flow did not converge")
    initialize_rms_models(grid, pf_results)

    group = RmsEventsGroup(name="HVDC RMS Vdc control")
    grid.add_rms_events_group(group)
    p_ref = find_name_in_block("P_ref", grid.transformers2w[1].rms_model)
    if p_ref is None:
        raise RuntimeError("Could not find the TrafoGFL P_ref event variable")
    # The TrafoGFL reference is initialized from PF. Disturb it around that
    # equilibrium instead of attempting to energize an algebraic DC link from
    # exactly zero current (which is singular without a DC capacitor model).
    p0 = -float(np.real(pf_results.St[list(grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True)).index(grid.transformers2w[1])]) / grid.Sbase)
    grid.add_rms_event(RmsEvent(
        device=grid.transformers2w[1], parameter=p_ref,
        time=p_event_time, value=p0 + p_step_pu, group=group,
    ))

    options = vge.RmsOptions(
        simulation_time=simulation_time, time_step=time_step, max_iter=80, tolerance=1.0e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
    )
    # Build the problem explicitly so the DC-line state can be seeded from PF.
    # The generic RMS problem initializer currently skips If_dc for a DC bus
    # because it only checks the AC Vm slot.
    problem = RmsProblemDae(grid=grid, options=options, pf_results=pf_results)
    line_map = grid.dc_lines[0].rms_model.external_mapping
    vdc_f0 = float(abs(pf_results.voltage[grid.buses.index(grid.dc_lines[0].bus_from)]))
    if0 = float(np.real(pf_results.Sf[0]) / grid.Sbase / vdc_f0)
    problem.init_guess[line_map[VarPowerFlowReferenceType.If_dc].uid] = if0
    problem.init_guess[line_map[VarPowerFlowReferenceType.Pf].uid] = float(np.real(pf_results.Sf[0]) / grid.Sbase)
    problem.init_guess[line_map[VarPowerFlowReferenceType.Pt].uid] = float(np.real(pf_results.St[0]) / grid.Sbase)
    problem.set_events_group(group)
    solver = BackEulerImplicitIntegration(
        problem=problem, t0=0.0, t_end=simulation_time, h=time_step,
        max_iter=options.max_iter, tolerance=options.tolerance,
    )
    time, trajectory, well_initialized, converged = solver.simulate()
    results = SimpleNamespace(
        time_array=time,
        values=trajectory[:, :, np.newaxis],
        uid2idx=problem.uid2idx_vars,
        converged=np.array([converged]),
        well_initialized=well_initialized,
    )
    output_dir = os.path.join(SCRIPT_DIR, "rms_hvdc_vdc_control_plots")
    plot_paths = save_plots(grid, results, output_dir, p_event_time=p_event_time)
    grid_path = os.path.join(SCRIPT_DIR, "rms_hvdc_vdc_control.veragrid")
    vge.save_file(grid=grid, filename=grid_path)
    return grid, pf_results, results, plot_paths, grid_path


if __name__ == "__main__":
    _, pf, rms, plots, grid_file = run_simulation()
    print(f"Power flow converged: {pf.converged}")
    print(f"RMS converged: {rms.converged}")
    print(f"Grid saved to: {grid_file}")
    for plot in plots:
        print(f"Plot saved to: {plot}")
