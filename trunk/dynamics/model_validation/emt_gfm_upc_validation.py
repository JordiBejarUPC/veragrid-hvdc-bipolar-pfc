#!/usr/bin/env python3
"""EMT validation for a GFM UPC VSC with explicit two-line AC filter."""

from __future__ import annotations

import os
import sys
from typing import Any, Tuple, cast

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

import VeraGridEngine.api as vge
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_balanced_3ph_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_dc_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.vsc_emt_upc import get_vsc_emt_upc_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
    DeviceType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)

import rms_gfm_validation as rms_ref


TIME_STEP = 5.0e-5
SIM_TIME = 0.20


def find_name_in_block(name: str, block: Block) -> Any:
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if var.name == name:
            return var
    for child in block.children:
        found = find_name_in_block(name, child)
        if found is not None:
            return found
    return None


def build_rl_line_emt_template(vf: VarFactory, r_pu: float, x_pu: float, name: str) -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name
    templ.block.name = name

    r = vf.add_var(name=f"R_{name}")
    x = vf.add_var(name=f"X_{name}")
    omega_base = vf.add_var(name=f"omega_base_{name}")

    vf_A = vf.add_var(name=f"vf_A_{name}", reference=VarPowerFlowReferenceType.vf_A)
    vf_B = vf.add_var(name=f"vf_B_{name}", reference=VarPowerFlowReferenceType.vf_B)
    vf_C = vf.add_var(name=f"vf_C_{name}", reference=VarPowerFlowReferenceType.vf_C)
    vt_A = vf.add_var(name=f"vt_A_{name}", reference=VarPowerFlowReferenceType.vt_A)
    vt_B = vf.add_var(name=f"vt_B_{name}", reference=VarPowerFlowReferenceType.vt_B)
    vt_C = vf.add_var(name=f"vt_C_{name}", reference=VarPowerFlowReferenceType.vt_C)

    i_A = vf.add_var(name=f"i_ser_A_{name}")
    i_B = vf.add_var(name=f"i_ser_B_{name}")
    i_C = vf.add_var(name=f"i_ser_C_{name}")
    di_A = vf.add_diff_var(name=f"di_A_{name}", base_var=i_A)
    di_B = vf.add_diff_var(name=f"di_B_{name}", base_var=i_B)
    di_C = vf.add_diff_var(name=f"di_C_{name}", base_var=i_C)

    if_A = vf.add_var(name=f"if_A_{name}", reference=VarPowerFlowReferenceType.if_A)
    if_B = vf.add_var(name=f"if_B_{name}", reference=VarPowerFlowReferenceType.if_B)
    if_C = vf.add_var(name=f"if_C_{name}", reference=VarPowerFlowReferenceType.if_C)
    it_A = vf.add_var(name=f"it_A_{name}", reference=VarPowerFlowReferenceType.it_A)
    it_B = vf.add_var(name=f"it_B_{name}", reference=VarPowerFlowReferenceType.it_B)
    it_C = vf.add_var(name=f"it_C_{name}", reference=VarPowerFlowReferenceType.it_C)

    state_eqs = [
        omega_base * (vf_A - vt_A - r * i_A) / x,
        omega_base * (vf_B - vt_B - r * i_B) / x,
        omega_base * (vf_C - vt_C - r * i_C) / x,
    ]
    algebraic_eqs = [
        if_A - i_A, if_B - i_B, if_C - i_C,
        it_A + i_A, it_B + i_B, it_C + i_C,
    ]
    templ.block = Block(
        state_eqs=state_eqs,
        state_vars=[i_A, i_B, i_C],
        diff_vars=[di_A, di_B, di_C],
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=[if_A, if_B, if_C, it_A, it_B, it_C],
        in_vars=[vf_A, vf_B, vf_C, vt_A, vt_B, vt_C],
        out_vars=[if_A, if_B, if_C, it_A, it_B, it_C],
        event_dict={
            r: vf.add_const(float(r_pu)),
            x: vf.add_const(float(x_pu)),
            omega_base: vf.add_const(2.0 * np.pi * 50.0),
        },
        diff_init_eqs={di_A: state_eqs[0], di_B: state_eqs[1], di_C: state_eqs[2]},
    )
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.vf_A: vf_A,
        VarPowerFlowReferenceType.vf_B: vf_B,
        VarPowerFlowReferenceType.vf_C: vf_C,
        VarPowerFlowReferenceType.vt_A: vt_A,
        VarPowerFlowReferenceType.vt_B: vt_B,
        VarPowerFlowReferenceType.vt_C: vt_C,
        VarPowerFlowReferenceType.if_A: if_A,
        VarPowerFlowReferenceType.if_B: if_B,
        VarPowerFlowReferenceType.if_C: if_C,
        VarPowerFlowReferenceType.it_A: it_A,
        VarPowerFlowReferenceType.it_B: it_B,
        VarPowerFlowReferenceType.it_C: it_C,
    }
    templ.block.api_obj_mapping = {ParamPowerFlowReferenceType.omega_base: omega_base}
    return templ


def create_grid() -> vge.MultiCircuit:
    return rms_ref.create_grid()


def run_power_flow(grid: vge.MultiCircuit):
    options = vge.PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=100,
        tolerance=1e-9,
        control_q=False,
    )
    return vge.power_flow(grid=grid, options=options)


def initialize_emt_models(grid: vge.MultiCircuit) -> None:
    vf = grid.var_factory
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    for gen in grid.generators:
        if gen.bus.is_dc:
            model = get_dc_voltage_source_emt_template(vf=vf, source_voltage_value=1.0, source_conductance_value=200.0, name=gen.name).block
        else:
            model = get_balanced_3ph_voltage_source_emt_template(
                vf=vf,
                amplitude_value=np.sqrt(2.0),
                frequency_hz=50.0,
                phase_a_deg=0.0,
                source_conductance_value=200.0,
                name=gen.name,
            ).block
        set_emt_model(device=gen, model=model, var_factory=vf)

    for line in grid.lines:
        model = build_rl_line_emt_template(vf=vf, r_pu=float(line.R), x_pu=float(line.X), name=line.name).block
        set_emt_model(device=line, model=model, var_factory=vf)

    for shunt in grid.shunts:
        # TODO: add a capacitor shunt once the EMT capacitor template exposes
        # state equations compatible with native EMT initialization. The static
        # PF still contains this shunt, so the VSC positive-sequence init remains
        # based on the same static grid.
        shunt.emt_model = Block()

    for load in grid.get_loads():
        model = get_shunt_r_emt_template(vf=vf, phA=True, phB=True, phC=True, name=load.name).block
        set_emt_model(device=load, model=model, var_factory=vf)
        g_total_pu = float(load.P) / grid.Sbase
        r_phase = 1.0 / max(g_total_pu / 3.0, 1e-9)
        for phase in ("A", "B", "C"):
            r_var = find_name_in_block(f"R_{phase}_{load.name}_3ph", model)
            if r_var is not None:
                model.event_dict[r_var] = vf.add_const(r_phase)

    for vsc in grid.vsc_devices:
        template = get_vsc_emt_upc_template(vf=vf, name=vsc.name)
        for var_name, value in (
            (f"R_s_{vsc.name}", 1e-4),
            (f"X_s_{vsc.name}", 1e-4),
            (f"Kdp_{vsc.name}", 0.005),
            (f"Kdq_{vsc.name}", 0.005),
            (f"tau_omega_{vsc.name}", 0.05),
            (f"tau_v_{vsc.name}", 0.05),
        ):
            var = find_name_in_block(var_name, template.block)
            if var is not None:
                template.block.event_dict[var] = vf.add_const(value)
        set_emt_model(device=vsc, model=template.block, var_factory=vf)


def run_emt(grid: vge.MultiCircuit, pf_results) -> Tuple[np.ndarray, np.ndarray, EmtProblemDae]:
    options = EmtOptions(
        time_step=TIME_STEP,
        simulation_time=SIM_TIME,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results_3ph=None, pf_results=pf_results)
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=SIM_TIME,
        h=TIME_STEP,
        method=options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )
    t, y, _, _, _ = solver.simulate(boundary_updater=cast(Any, problem))
    return t, y, problem


def plot_results(grid: vge.MultiCircuit, t: np.ndarray, y: np.ndarray, problem: EmtProblemDae) -> None:
    vsc = grid.vsc_devices[0]

    def col(name: str) -> np.ndarray:
        var = find_name_in_block(name, vsc.emt_model)
        if var is None:
            return np.zeros_like(t)
        return y[:, problem.get_var_idx(var)]

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    axes[0].plot(t, col(f"Pe_{vsc.name}"), label="Pe")
    axes[0].plot(t, col(f"Qe_{vsc.name}"), label="Qe")
    axes[1].plot(t, col(f"omega_{vsc.name}"), label="omega")
    axes[1].plot(t, col(f"Epk_{vsc.name}"), label="Epk")
    axes[2].plot(t, col(f"i_A_{vsc.name}"), label="i_A")
    axes[2].plot(t, col(f"i_B_{vsc.name}"), label="i_B")
    axes[2].plot(t, col(f"i_C_{vsc.name}"), label="i_C")
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
    axes[-1].set_xlabel("time [s]")
    fig.tight_layout()
    out = os.path.join(os.path.dirname(__file__), "emt_gfm_upc_validation_results.png")
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"Plot saved to {out}")


if __name__ == "__main__":
    grid = create_grid()
    pf_results = run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")
    initialize_emt_models(grid)
    t, y, problem = run_emt(grid, pf_results)
    print(f"EMT samples: {len(t)}, t_end={t[-1]:.6f}s")
    plot_results(grid, t, y, problem)
