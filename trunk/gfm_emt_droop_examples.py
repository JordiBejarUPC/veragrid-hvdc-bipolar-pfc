# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Grid-forming VSC EMT droop experiment.

Builds the small DC-fed GFM island from
``src/tests/EMT/test_vsc_gfm_emt_system.py``, applies a resistive
load-step event, runs the full EMT DAE simulation and sweeps the two
grid-forming droop gains:

* ``Kdp`` — P-f droop gain. ``omega_setpoint = omega_ref - Kdp*(Pe - P_ref)``
* ``Kdq`` — Q-V droop gain. ``Epk_setpoint = V_ref - Kdq*(Qe - Q_ref)``

The script produces two PNG figures next to itself:

* ``gfm_droop_sweep_Kdp.png`` — omega / Pe / i_A response as Kdp varies.
* ``gfm_droop_sweep_Kdq.png`` — Epk / Qe response as Kdq varies.

Run:  ``.venv/bin/python trunk/gfm_emt_droop_examples.py``
"""

from __future__ import annotations

import os,sys
from typing import Any, Dict, List, Tuple, cast
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_dc_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import get_bergeron_line_emt_template
from VeraGridEngine.Templates.Emt.vsc_gfm_emt import get_gfm_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DeviceType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ParamPowerFlowReferenceType,
    ShuntConnectionType,
    VarPowerFlowReferenceType,
    SolverType,
)

HERE = os.path.dirname(os.path.abspath(__file__))

# Event / simulation timing (shared by every run in a sweep).
EVENT_TIME = 0.04          # s, when the load step happens
R_STEP_VALUE = 3.0         # ohm, post-event per-phase load resistance
SIM_TIME = 0.20            # s, total simulated window
TIME_STEP = 5.0e-5         # s, integration step


def _build_rl_line_emt_template(vf: VarFactory, R_pu: float, X_pu: float,
                                name: str = "RL") -> EmtModelTemplate:
    """Minimal three-phase series-RL line EMT template (no shunt, no history)."""
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name
    templ.block.name = name

    R_par = vf.add_var(name=f"R_{name}")
    X_par = vf.add_var(name=f"X_{name}")
    omega_base = vf.add_var(name=f"omega_base_{name}")

    vf_A = vf.add_var(name=f"vf_A_{name}", reference=VarPowerFlowReferenceType.vf_A)
    vf_B = vf.add_var(name=f"vf_B_{name}", reference=VarPowerFlowReferenceType.vf_B)
    vf_C = vf.add_var(name=f"vf_C_{name}", reference=VarPowerFlowReferenceType.vf_C)
    vt_A = vf.add_var(name=f"vt_A_{name}", reference=VarPowerFlowReferenceType.vt_A)
    vt_B = vf.add_var(name=f"vt_B_{name}", reference=VarPowerFlowReferenceType.vt_B)
    vt_C = vf.add_var(name=f"vt_C_{name}", reference=VarPowerFlowReferenceType.vt_C)

    i_ser_A = vf.add_var(name=f"i_ser_A_{name}")
    i_ser_B = vf.add_var(name=f"i_ser_B_{name}")
    i_ser_C = vf.add_var(name=f"i_ser_C_{name}")
    di_A = vf.add_diff_var(name=f"di_A_{name}", base_var=i_ser_A)
    di_B = vf.add_diff_var(name=f"di_B_{name}", base_var=i_ser_B)
    di_C = vf.add_diff_var(name=f"di_C_{name}", base_var=i_ser_C)

    if_A = vf.add_var(name=f"if_A_{name}", reference=VarPowerFlowReferenceType.if_A)
    if_B = vf.add_var(name=f"if_B_{name}", reference=VarPowerFlowReferenceType.if_B)
    if_C = vf.add_var(name=f"if_C_{name}", reference=VarPowerFlowReferenceType.if_C)
    it_A = vf.add_var(name=f"it_A_{name}", reference=VarPowerFlowReferenceType.it_A)
    it_B = vf.add_var(name=f"it_B_{name}", reference=VarPowerFlowReferenceType.it_B)
    it_C = vf.add_var(name=f"it_C_{name}", reference=VarPowerFlowReferenceType.it_C)

    state_eqs = [
        omega_base * (vf_A - vt_A - R_par * i_ser_A) / X_par,
        omega_base * (vf_B - vt_B - R_par * i_ser_B) / X_par,
        omega_base * (vf_C - vt_C - R_par * i_ser_C) / X_par,
    ]
    algebraic_eqs = [
        if_A - i_ser_A, if_B - i_ser_B, if_C - i_ser_C,
        it_A - (-i_ser_A), it_B - (-i_ser_B), it_C - (-i_ser_C),
    ]
    templ.block = Block(
        state_eqs=state_eqs,
        state_vars=[i_ser_A, i_ser_B, i_ser_C],
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=[if_A, if_B, if_C, it_A, it_B, it_C],
        in_vars=[vf_A, vf_B, vf_C, vt_A, vt_B, vt_C],
        out_vars=[if_A, if_B, if_C, it_A, it_B, it_C],
    )
    templ.block.diff_vars = [di_A, di_B, di_C]
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
    templ.block.event_dict = {
        omega_base: vf.add_const(2.0 * np.pi * 50.0),
        R_par: vf.add_const(float(R_pu)),
        X_par: vf.add_const(float(X_pu)),
    }
    templ.block.diff_init_eqs = {
        di_A: omega_base * (vf_A - vt_A - R_par * i_ser_A) / X_par,
        di_B: omega_base * (vf_B - vt_B - R_par * i_ser_B) / X_par,
        di_C: omega_base * (vf_C - vt_C - R_par * i_ser_C) / X_par,
    }
    return templ


def _find_name_in_block(name: str, block: Block) -> Any:
    """Locate one symbolic variable by name inside a block hierarchy."""
    for var in (block.algebraic_vars + block.state_vars
                + list(block.event_dict.keys()) + block.diff_vars):
        if name == var.name:
            return var
    for child in block.children:
        found = _find_name_in_block(name, child)
        if found is not None:
            return found
    return None


def build_dc_fed_gfm_island(kdp: float, kdq: float,
                            use_rl_main_line: bool = False) -> Tuple[Any, Any, Any, Any, Any, Any]:
    """
    Assemble the DC-fed GFM island with the GFM droop gains overridden.

    :param kdp: P-f droop gain for the grid-forming VSC.
    :param kdq: Q-V droop gain for the grid-forming VSC.
    :param use_rl_main_line: if True, model the main AC line with the
        perfectly symmetric lumped RL template instead of the
        travelling-wave Bergeron line (control experiment for the ripple).
    :return: ``(grid, vsc, load, R_A, R_B, R_C)``.
    """
    vnom_ac: float = 10.0
    vnom_dc: float = 1.0
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

    bus_dc = gce.Bus(name="Bus_DC", Vnom=vnom_dc, is_dc=True, is_slack=True)
    bus_vsc_int = gce.Bus(name="Bus_VSC_Internal", Vnom=vnom_ac)
    bus_ac1 = gce.Bus(name="Bus_AC1", Vnom=vnom_ac)
    bus_ac2 = gce.Bus(name="Bus_AC2", Vnom=vnom_ac)
    for b in (bus_dc, bus_vsc_int, bus_ac1, bus_ac2):
        grid.add_bus(b)

    gen_dc = gce.Generator(name="DC_Gen", vset=1.0, Snom=2.0, freq=50.0, r1=0.001, x1=0.01)
    grid.add_generator(bus_dc, gen_dc)

    vsc = gce.VSC(
        name="GFM_VSC", bus_from=bus_dc, bus_to=bus_vsc_int, rate=2.0,
        control1=ConverterControlType.Vm_ac, control2=ConverterControlType.Va_ac,
        control1_val=1.0, control2_val=0.0,
    )
    grid.add_vsc(vsc)

    filter_R_pu, filter_X_pu = 0.01, 0.1
    filter_line = gce.Line(name="VSC_Filter", bus_from=bus_vsc_int, bus_to=bus_ac1,
                           r=filter_R_pu, x=filter_X_pu, b=0.0, rate=2.0)
    grid.add_line(filter_line)

    line = gce.Line(name="Line", bus_from=bus_ac1, bus_to=bus_ac2, length=10.0, rate=2.0)
    tower = gce.OverheadLineType(name="Tower", Vnom=vnom_ac)
    wire = gce.Wire(name="Panther 30/7 ACSR", diameter=21.0, diameter_internal=9.0,
                    is_tube=True, r=0.1363, max_current=1)
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line.apply_template(tower, grid.Sbase, grid.fBase)
    grid.add_line(line)

    R_load_initial = 100.0
    v_ph = vnom_ac / np.sqrt(3.0)
    G_ph_initial = (v_ph * v_ph) / R_load_initial
    G_total_initial = 3.0 * G_ph_initial
    load = gce.Load(name="Load", G=G_total_initial, B=0.0,
                    G1=G_ph_initial, G2=G_ph_initial, G3=G_ph_initial,
                    B1=0.0, B2=0.0, B3=0.0)
    load.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus_ac2, load)

    R_damp = 1.0e3
    G_ph_damp = (v_ph * v_ph) / R_damp
    G_total_damp = 3.0 * G_ph_damp
    damp_shunt = gce.Load(name="DampShunt", G=G_total_damp, B=0.0,
                          G1=G_ph_damp, G2=G_ph_damp, G3=G_ph_damp,
                          B1=0.0, B2=0.0, B3=0.0)
    damp_shunt.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus_ac1, damp_shunt)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    dc_src_mdl = get_dc_voltage_source_emt_template(
        vf=grid.var_factory, source_voltage_value=1.0,
        source_conductance_value=200.0, name="DC_Gen").block

    vsc_template = get_gfm_emt_template(vf=grid.var_factory, name="GFM_VSC")
    R_s_var = _find_name_in_block("R_s_GFM_VSC", vsc_template.block)
    X_s_var = _find_name_in_block("X_s_GFM_VSC", vsc_template.block)
    Kdp_var = _find_name_in_block("Kdp_GFM_VSC", vsc_template.block)
    Kdq_var = _find_name_in_block("Kdq_GFM_VSC", vsc_template.block)
    assert all(v is not None for v in (R_s_var, X_s_var, Kdp_var, Kdq_var))
    # GFM internal impedance lives in the filter line; make GFM near-ideal.
    vsc_template.block.event_dict[R_s_var] = grid.var_factory.add_const(1.0e-4)
    vsc_template.block.event_dict[X_s_var] = grid.var_factory.add_const(1.0e-4)
    # The two gains under study.
    vsc_template.block.event_dict[Kdp_var] = grid.var_factory.add_const(float(kdp))
    vsc_template.block.event_dict[Kdq_var] = grid.var_factory.add_const(float(kdq))
    vsc_mdl = vsc_template.block

    if use_rl_main_line:
        # Positive-sequence R/X of the templated line (already pu on grid Sbase).
        R_main_pu = float(line.R) if line.R > 0 else 0.05
        X_main_pu = float(line.X) if line.X > 0 else 0.20
        line_mdl = _build_rl_line_emt_template(
            vf=grid.var_factory, R_pu=R_main_pu, X_pu=X_main_pu, name="MainRL").block
    else:
        line_mdl = get_bergeron_line_emt_template(
            vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True).block
    filter_mdl = _build_rl_line_emt_template(
        vf=grid.var_factory, R_pu=filter_R_pu, X_pu=filter_X_pu, name="VSC_Filter").block
    load_mdl = get_shunt_r_emt_template(
        vf=grid.var_factory, phA=True, phB=True, phC=True).block
    damp_mdl = get_shunt_r_emt_template(
        vf=grid.var_factory, phA=True, phB=True, phC=True, name="DampShunt_R").block

    set_emt_model(device=gen_dc, model=dc_src_mdl, var_factory=grid.var_factory)
    set_emt_model(device=vsc, model=vsc_mdl, var_factory=grid.var_factory)
    set_emt_model(device=filter_line, model=filter_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line, model=line_mdl, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)
    set_emt_model(device=damp_shunt, model=damp_mdl, var_factory=grid.var_factory)

    def _override_shunt_r(template: Any, event_suffix: str, G_total_pu: float) -> None:
        R_pu = 1.0 / (G_total_pu / 3.0)
        for phase_label in ("A", "B", "C"):
            R_var = _find_name_in_block(f"R_{phase_label}_{event_suffix}", template)
            assert R_var is not None
            template.event_dict[R_var] = grid.var_factory.add_const(R_pu)

    _override_shunt_r(load_mdl, "Shunt_R_3ph", G_total_pu=G_total_initial / grid.Sbase)
    _override_shunt_r(damp_mdl, "DampShunt_R_3ph", G_total_pu=G_total_damp / grid.Sbase)

    R_A = _find_name_in_block("R_A_Shunt_R_3ph", load_mdl)
    R_B = _find_name_in_block("R_B_Shunt_R_3ph", load_mdl)
    R_C = _find_name_in_block("R_C_Shunt_R_3ph", load_mdl)
    return grid, vsc, load, R_A, R_B, R_C


def run_case(kdp: float, kdq: float, use_rl_main_line: bool = False) -> Dict[str, np.ndarray]:
    """
    Run one full EMT simulation of the load-step transient for a (kdp, kdq) pair.

    :param kdp: P-f droop gain.
    :param kdq: Q-V droop gain.
    :param use_rl_main_line: if True, use the perfectly symmetric lumped RL
        line (no travelling-wave reflections) → essentially ripple-free.
    :return: dict of trajectories keyed by signal name (plus ``"t"``).
    """
    grid, vsc, load, R_A, R_B, R_C = build_dc_fed_gfm_island(
        kdp=kdp, kdq=kdq, use_rl_main_line=use_rl_main_line)

    pf_options = PowerFlowOptions(solver_type=SolverType.NR, verbose=False,
                                  retry_with_other_methods=True, max_iter=50, tolerance=1e-6)
    pf_results = gce.power_flow(grid=grid, options=pf_options)
    assert pf_results.converged, f"PF did not converge for Kdp={kdp}, Kdq={kdq}"

    events_group = EmtEventsGroup(name="gfm_load_step")
    grid.add_emt_events_group(events_group)
    for phase_R in (R_A, R_B, R_C):
        grid.add_emt_event(EmtEvent(device=load, parameter=phase_R,
                                    time=EVENT_TIME, value=R_STEP_VALUE,
                                    group=events_group))

    options = EmtOptions(time_step=TIME_STEP, simulation_time=SIM_TIME, tolerance=1e-6,
                         solver_type=EmtSolverTypes.Symbolic,
                         initialization_method=EmtInitializationMethod.Auto,
                         integration_method=DynamicIntegrationMethod.DaeBackEuler, verbose=0)
    problem = EmtProblemDae(grid=grid, options=options, pf_results_3ph=None,
                            pf_results=pf_results)
    problem.set_events_group(events_group)

    solver = JitSymbolicSolver(problem=problem, t0=0.0, t_end=SIM_TIME, h=TIME_STEP,
                               method=options.integration_method,
                               pred_method=DynamicIntegrationMethod.OdeEuler,
                               dense_threshold=0, verbose=False)
    t, y, _, _, _ = solver.simulate(boundary_updater=cast(Any, problem))

    def col(name: str) -> np.ndarray:
        var = _find_name_in_block(name, vsc.emt_model)
        assert var is not None, f"missing {name}"
        return y[:, problem.get_var_idx(var)]

    return {
        "t": t,
        "omega": col("omega_GFM_VSC"),
        "Pe": col("Pe_GFM_VSC"),
        "Qe": col("Qe_GFM_VSC"),
        "Epk": col("Epk_GFM_VSC"),
        "i_A": col("i_A_GFM_VSC"),
    }


def _settle(t: np.ndarray, sig: np.ndarray) -> float:
    """Mean of a signal over the last 20 ms (post-event steady value)."""
    mask = t > (t[-1] - 0.02)
    return float(np.mean(sig[mask]))


def sweep_kdp(kdp_values: List[float], kdq_fixed: float) -> None:
    """Sweep Kdp, fixed Kdq; plot omega / Pe / i_A response to the load step."""
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    print(f"\n=== Kdp sweep (Kdq = {kdq_fixed}) ===")
    print(f"{'Kdp':>6} | {'omega_settle':>12} | {'Pe_settle':>10} | {'omega_min':>10}")
    for kdp in kdp_values:
        r = run_case(kdp=kdp, kdq=kdq_fixed)
        lbl = f"Kdp={kdp:g}"
        axes[0].plot(r["t"], r["omega"], label=lbl)
        axes[1].plot(r["t"], r["Pe"], label=lbl)
        axes[2].plot(r["t"], r["i_A"], label=lbl)
        print(f"{kdp:>6g} | {_settle(r['t'], r['omega']):>12.6f} | "
              f"{_settle(r['t'], r['Pe']):>10.4f} | {float(np.min(r['omega'])):>10.6f}")

    for ax in axes:
        ax.axvline(EVENT_TIME, color="k", ls=":", lw=0.8, alpha=0.6)
        ax.legend(fontsize=8, loc="best")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("omega [pu]")
    axes[1].set_ylabel("Pe [3·pu]")
    axes[2].set_ylabel("i_A [pu]")
    axes[2].set_xlabel("time [s]")
    axes[0].set_title(f"GFM load-step response — Kdp sweep (Kdq={kdq_fixed}), "
                      f"R step to {R_STEP_VALUE} ohm at t={EVENT_TIME}s")
    fig.tight_layout()
    out = os.path.join(HERE, "gfm_droop_sweep_Kdp.png")
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(f"saved {out}")


def sweep_kdq(kdq_values: List[float], kdp_fixed: float) -> None:
    """Sweep Kdq, fixed Kdp; plot Epk / Qe response to the load step."""
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    print(f"\n=== Kdq sweep (Kdp = {kdp_fixed}) ===")
    print(f"{'Kdq':>6} | {'Epk_settle':>10} | {'Qe_settle':>10} | {'Epk_min':>10}")
    for kdq in kdq_values:
        r = run_case(kdp=kdp_fixed, kdq=kdq)
        lbl = f"Kdq={kdq:g}"
        axes[0].plot(r["t"], r["Epk"], label=lbl)
        axes[1].plot(r["t"], r["Qe"], label=lbl)
        print(f"{kdq:>6g} | {_settle(r['t'], r['Epk']):>10.4f} | "
              f"{_settle(r['t'], r['Qe']):>10.4f} | {float(np.min(r['Epk'])):>10.4f}")

    for ax in axes:
        ax.axvline(EVENT_TIME, color="k", ls=":", lw=0.8, alpha=0.6)
        ax.legend(fontsize=8, loc="best")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("Epk [pu]")
    axes[1].set_ylabel("Qe [3·pu]")
    axes[1].set_xlabel("time [s]")
    axes[0].set_title(f"GFM load-step response — Kdq sweep (Kdp={kdp_fixed}), "
                      f"R step to {R_STEP_VALUE} ohm at t={EVENT_TIME}s")
    fig.tight_layout()
    out = os.path.join(HERE, "gfm_droop_sweep_Kdq.png")
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(f"saved {out}")


def compare_line_models(kdp: float = 0.05, kdq: float = 0.05) -> None:
    """
    Run the load-step transient twice — once with the travelling-wave
    Bergeron line, once with a perfectly balanced lumped RL line — and
    overlay omega / Pe / Qe so the ripple difference is visible.

    :param kdp: P-f droop gain (same for both runs).
    :param kdq: Q-V droop gain (same for both runs).
    """
    print(f"\n=== line-model comparison (Kdp={kdp}, Kdq={kdq}) ===")
    cases = [
        ("Bergeron (travelling-wave)", "C0", False),
        ("Balanced lumped RL", "C3", True),
    ]
    results = []
    for label, _color, rl in cases:
        r = run_case(kdp=kdp, kdq=kdq, use_rl_main_line=rl)
        mask = r["t"] > (r["t"][-1] - 0.02)
        print(f"{label:28s} | Pe pk-pk(post)={np.ptp(r['Pe'][mask]):.4f} | "
              f"Qe pk-pk(post)={np.ptp(r['Qe'][mask]):.4f}")
        results.append((label, _color, r))

    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    for label, color, r in results:
        axes[0].plot(r["t"], r["omega"], color=color, label=label)
        axes[1].plot(r["t"], r["Pe"], color=color, label=label)
        axes[2].plot(r["t"], r["Qe"], color=color, label=label)

    for ax in axes:
        ax.axvline(EVENT_TIME, color="k", ls=":", lw=0.8, alpha=0.6)
        ax.legend(fontsize=8, loc="best")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("omega [pu]")
    axes[1].set_ylabel("Pe [3·pu]")
    axes[2].set_ylabel("Qe [3·pu]")
    axes[2].set_xlabel("time [s]")
    axes[0].set_title(f"GFM load-step: travelling-wave line vs perfectly balanced "
                      f"RL line (Kdp={kdp}, Kdq={kdq})")
    fig.tight_layout()
    out = os.path.join(HERE, "gfm_line_model_compare.png")
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(f"saved {out}")


if __name__ == "__main__":
    sweep_kdp(kdp_values=[0.01, 0.05, 0.10, 0.20], kdq_fixed=0.05)
    sweep_kdq(kdq_values=[0.01, 0.05, 0.10, 0.20], kdp_fixed=0.05)
    compare_line_models(kdp=0.05, kdq=0.05)
    print("\nDone.")
