# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sys
from pathlib import Path
from types import MethodType

import matplotlib.pyplot as plt
import numpy as np

project_base = Path(__file__).resolve().parents[2]
src_path = project_base / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import VeraGridEngine.api as vge
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.Rms.numerical.back_euler_mti import BackEulerImplicitIntegrationMTI
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.problems.rms_problem_MTI import RmsProblemMTI
from VeraGridEngine.Simulations.Rms.problems.rms_problem_phasor import RmsProblemPhasor
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.enumerations import (
    VarPowerFlowRefferenceType,
    ParamPowerFlowRefferenceType,
    RmsInitializationMethod,
)


def build_grid_case() -> vge.MultiCircuit:
    grid_folder = project_base / "Grids_and_profiles" / "grids"
    grid_path = grid_folder / "IEEE 9 Bus.gridcal"
    if not grid_path.exists():
        raise FileNotFoundError(f"Grid file not found: {grid_path}")
    return vge.open_file(str(grid_path))


def build_rms_models_explicit(grid: vge.MultiCircuit) -> None:
    ensure_unique_device_names(grid)

    for bus in grid.buses:
        if bus.rms_model.empty():
            vge.initialize_bus_phasor_rms(bus, vf=grid.var_factory)

    for igen, gen in enumerate(grid.generators):
        if not gen.rms_model.empty():
            continue
        genqec = vge.get_complete_generator_template_phasor(grid.var_factory, name=f"Gen{igen}").block
        genqec.connect([genqec.in_vars[0]], [gen.bus.rms_model.out_vars[0]])
        genqec.connect([genqec.in_vars[1]], [gen.bus.rms_model.out_vars[1]])
        set_rms_model(device=gen, model=genqec, var_factory=grid.var_factory)

    for line in grid.lines:
        if not line.rms_model.empty():
            continue
        lineec = vge.get_line_phasor_rms_template(grid.var_factory, name=line.name).block
        lineec.connect([lineec.in_vars[0]], [line.bus_from.rms_model.out_vars[0]])
        lineec.connect([lineec.in_vars[1]], [line.bus_from.rms_model.out_vars[1]])
        lineec.connect([lineec.in_vars[2]], [line.bus_to.rms_model.out_vars[0]])
        lineec.connect([lineec.in_vars[3]], [line.bus_to.rms_model.out_vars[1]])
        lineec = vge.to_implicit(lineec, grid.var_factory)
        set_rms_model(device=line, model=lineec, var_factory=grid.var_factory)

    for load in grid.loads:
        if not load.rms_model.empty():
            continue
        loadec = vge.get_load_phasor_current_rms_template(grid.var_factory, name=load.name).block
        loadec.connect([loadec.in_vars[0]], [load.bus.rms_model.out_vars[0]])
        loadec.connect([loadec.in_vars[1]], [load.bus.rms_model.out_vars[1]])
        set_rms_model(device=load, model=loadec, var_factory=grid.var_factory)

    for trafo in grid.transformers2w:
        if not trafo.rms_model.empty():
            continue
        trafoec = vge.initialize_trafo_rms(trafo, grid.var_factory, use_phasor_template=True).block
        trafoec.connect([trafoec.in_vars[0]], [trafo.bus_from.rms_model.out_vars[0]])
        trafoec.connect([trafoec.in_vars[1]], [trafo.bus_from.rms_model.out_vars[1]])
        trafoec.connect([trafoec.in_vars[2]], [trafo.bus_to.rms_model.out_vars[0]])
        trafoec.connect([trafoec.in_vars[3]], [trafo.bus_to.rms_model.out_vars[1]])
        trafoec = vge.to_implicit(trafoec, grid.var_factory)
        set_rms_model(device=trafo, model=trafoec, var_factory=grid.var_factory)

    for shunt in grid.shunts:
        if not shunt.rms_model.empty():
            continue
        shuntec = vge.get_shunt_template(grid.var_factory, name=shunt.name, phasor=True).block
        shuntec.connect([shuntec.in_vars[0]], [shunt.bus.rms_model.out_vars[0]])
        shuntec.connect([shuntec.in_vars[1]], [shunt.bus.rms_model.out_vars[1]])
        shuntec = vge.to_implicit(shuntec, grid.var_factory)
        set_rms_model(device=shunt, model=shuntec, var_factory=grid.var_factory)

    sanitize_runtime_parameter_names(grid)


def sanitize_runtime_parameter_names(grid):
    def _sanitize_block(block, tag):
        block.unify_blocks()
        all_syms = list(block.algebraic_vars) + list(block.state_vars) + list(block.diff_vars)
        all_syms += list(block.event_dict.keys()) + list(block.mode_dict.keys())
        seen = {}
        for k, sym in enumerate(all_syms):
            nm = str(sym.name)
            if nm not in seen:
                seen[nm] = 0
                continue
            seen[nm] += 1
            sym.name = f"{nm}__{tag}_{seen[nm]}_{k}"

    for i, dev in enumerate(grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True)):
        if not dev.rms_model.empty():
            _sanitize_block(dev.rms_model, f"br{i}")

    for i, dev in enumerate(grid.get_injection_devices_iter()):
        if not dev.rms_model.empty():
            _sanitize_block(dev.rms_model, f"inj{i}")


def ensure_unique_device_names(grid):
    def _rename(devices, prefix):
        seen = {}
        for i, dev in enumerate(devices):
            base = str(dev.name).strip() if getattr(dev, 'name', None) else f"{prefix}_{i}"
            if base not in seen:
                seen[base] = 0
                dev.name = base
            else:
                seen[base] += 1
                dev.name = f"{base}_{seen[base]}"

    _rename(list(grid.generators), "gen")
    _rename(list(grid.lines), "line")
    _rename(list(grid.transformers2w), "trafo")
    _rename(list(grid.loads), "load")
    _rename(list(grid.shunts), "shunt")


def inject_mti_boolean_logic(grid: vge.MultiCircuit, use_mode_dict_coupling: bool) -> tuple[object, object]:
    bus0 = grid.buses[0]
    mode_var = grid.var_factory.add_var(name="mti_mode_test_bus0")
    # For phasor-based MTI (RmsProblemMTI <- RmsProblemPhasor), runtime
    # parameters are registered from event_dict. Keep mode_dict optional so
    # we can test whether mode_dict coupling destabilizes the Jacobian.
    bus0.rms_model.event_dict[mode_var] = grid.var_factory.add_const(0.0)
    if use_mode_dict_coupling:
        bus0.rms_model.mode_dict[mode_var] = grid.var_factory.add_const(0.0)

    # Drive boolean logic from a continuous signal (bus voltage magnitude)
    # instead of self-referencing the mode variable.
    vr = bus0.rms_model.out_vars[0]
    vi = bus0.rms_model.out_vars[1]
    vm_sq = vr * vr + vi * vi
    vth = 0.98
    vth_sq = vth * vth

    # Guard residual is true when Vm <= Vth (low-voltage region).
    low_voltage_guard = vm_sq <= vth_sq
    bus0.rms_model.boolean_guards[mode_var] = low_voltage_guard
    bus0.rms_model.inequalities.append(low_voltage_guard)
    return bus0, mode_var


def add_proper_runtime_event(grid: vge.MultiCircuit) -> RmsEventsGroup:

    loads = list(grid.loads)
    if len(loads) == 0:
        raise RuntimeError("No loads available for RMS event injection.")
    target = loads[0]
    if len(target.rms_model.event_dict) == 0:
        raise RuntimeError("Selected load model has no runtime event parameters.")

    event_param = target.rms_model.api_obj_mapping.get(ParamPowerFlowRefferenceType.Pl0, None)
    if event_param is None or event_param not in target.rms_model.event_dict:
        raise RuntimeError("Could not find load Pl0 runtime parameter in event_dict.")
    base_expr = target.rms_model.event_dict[event_param]
    event_value = 0.98
    if hasattr(base_expr, "value") and base_expr.value is not None:
        event_value = 0.9 * float(base_expr.value)

    event_group = RmsEventsGroup(name="MTIValidationEventGroup")
    grid.add_rms_events_group(event_group)
    grid.add_rms_event(
        RmsEvent(
            device=target,
            parameter=event_param,
            time=0.05,
            value=float(event_value),
            group=event_group,
            force_step_alignment=True,
        )
    )
    return event_group


def ensure_problem_event_api(problem) -> None:
    if not hasattr(problem, "get_next_forced_event_time"):
        def _get_next_forced_event_time(self, t_local_prev, t_macro_target):
            return None
        problem.get_next_forced_event_time = MethodType(_get_next_forced_event_time, problem)

    if not hasattr(problem, "update"):
        def _update(self, t, x_snapshot, variable_parameters):
            return None
        problem.update = MethodType(_update, problem)


def plot_results(t: np.ndarray, y: np.ndarray, z: np.ndarray, problem: RmsProblemPhasor) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)

    vr_entries = []
    vi_entries = []
    for uid, idx in problem.uid2idx_vars.items():
        var = problem.sys_vars[uid]
        if not hasattr(var, "ref"):
            continue
        if var.ref == VarPowerFlowRefferenceType.Vr:
            vr_entries.append((idx, str(var.name)))
        elif var.ref == VarPowerFlowRefferenceType.Vi:
            vi_entries.append((idx, str(var.name)))

    vr_entries.sort(key=lambda x: x[0])
    vi_entries.sort(key=lambda x: x[0])

    if vr_entries:
        for idx, name in vr_entries:
            axes[0].plot(t, y[:, idx], linewidth=1.7, label=name)
        axes[0].set_ylabel("Vr [pu]")
        axes[0].legend(loc="best", ncol=2, fontsize=8)
    else:
        axes[0].plot(t, np.zeros_like(t), linewidth=1.5)
        axes[0].set_ylabel("Vr [pu]")
    axes[0].grid(True, alpha=0.3)

    if vi_entries:
        for idx, name in vi_entries:
            axes[1].plot(t, y[:, idx], linewidth=1.7, label=name)
        axes[1].set_ylabel("Vi [pu]")
        axes[1].legend(loc="best", ncol=2, fontsize=8)
    else:
        axes[1].plot(t, np.zeros_like(t), linewidth=1.5)
        axes[1].set_ylabel("Vi [pu]")
    axes[1].grid(True, alpha=0.3)

    if z.shape[1] > 0:
        for k in range(z.shape[1]):
            axes[2].step(t, z[:, k], where="post", linewidth=2, label=f"z{k}")
        axes[2].legend(loc="best")
    else:
        axes[2].plot(t, np.zeros_like(t), linewidth=1.5)
    axes[2].set_ylabel("Boolean z")
    axes[2].set_xlabel("Time [s]")
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    out = project_base / "trunk" / "tensygrid" / "rms_mti_validation_plot.png"
    plt.savefig(out, dpi=150)
    print(f"Saved plot: {out}")


def run_validation() -> None:
    inject_boolean_logic = True
    use_mode_dict_coupling = False
    grid = build_grid_case()
    # Use the same explicit phasor-style model build strategy as
    # small_signal_tensygrid.py
    build_rms_models_explicit(grid)
    if inject_boolean_logic:
        inject_mti_boolean_logic(grid, use_mode_dict_coupling=use_mode_dict_coupling)
    events_group = add_proper_runtime_event(grid)

    pf_options = vge.PowerFlowOptions(tolerance=1e-6)
    pf_results = vge.power_flow(grid, pf_options)
    if not pf_results.converged:
        raise RuntimeError("Power flow did not converge; aborting MTI validation.")

    rms_options = RmsOptions(
        time_step=0.01,
        simulation_time=0.10,
        tolerance=1e-6,
        max_iter=20,
        verbose=1,
        initialization_method=RmsInitializationMethod.Explicit,
    )

    problem = RmsProblemMTI(grid=grid, options=rms_options, pf_results=pf_results)
    problem.set_events_group(events_group)
    ensure_problem_event_api(problem)

    solver = BackEulerImplicitIntegrationMTI(
        problem=problem,
        t0=0.0,
        t_end=rms_options.simulation_time,
        h=rms_options.time_step,
        max_iter=rms_options.max_iter,
        tolerance=rms_options.tolerance,
        inequality_tolerance=1e-9,
    )

    t, y, well_initialized, converged = solver.simulate()

    print("\n=== MTI Validation Report ===")
    print(f"Boolean injection enabled: {inject_boolean_logic}")
    print(f"Mode-dict coupling enabled: {use_mode_dict_coupling}")
    print(f"Power flow converged: {pf_results.converged}")
    print(f"RMS variables: {problem.get_all_vars_number()}")
    print(f"Boolean modes registered: {len(problem.get_mti_boolean_parameter_indices())}")
    print(f"Well initialized: {well_initialized}")
    print(f"Converged: {converged}")
    print(f"Simulated steps: {len(t)}")
    print(f"Final state norm: {np.linalg.norm(y[-1, :]):.6e}")

    vr_entries = []
    vi_entries = []
    for uid, idx in problem.uid2idx_vars.items():
        var = problem.sys_vars[uid]
        if not hasattr(var, "ref"):
            continue
        if var.ref == VarPowerFlowRefferenceType.Vr:
            vr_entries.append((idx, str(var.name)))
        elif var.ref == VarPowerFlowRefferenceType.Vi:
            vi_entries.append((idx, str(var.name)))
    vr_entries.sort(key=lambda x: x[0])
    vi_entries.sort(key=lambda x: x[0])

    if vr_entries or vi_entries:
        print("\nFinal phasor voltages (Vr, Vi):")
        for i in range(max(len(vr_entries), len(vi_entries))):
            vr_txt = "-"
            vi_txt = "-"
            if i < len(vr_entries):
                vr_idx, vr_name = vr_entries[i]
                vr_txt = f"{vr_name}={y[-1, vr_idx]:.6f}"
            if i < len(vi_entries):
                vi_idx, vi_name = vi_entries[i]
                vi_txt = f"{vi_name}={y[-1, vi_idx]:.6f}"
            print(f"  {vr_txt}, {vi_txt}")

    z_hist = solver.z[: len(t), :] if solver.z.shape[1] > 0 else solver.z
    if z_hist.shape[1] > 0:
        print(f"Final z: {z_hist[-1, :]}")
        print(f"Unique z values: {np.unique(z_hist, axis=0)}")

    plot_results(t, y, z_hist, problem)


if __name__ == "__main__":
    run_validation()
