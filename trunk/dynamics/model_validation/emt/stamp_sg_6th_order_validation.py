# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Validate the STAMP sixth-order synchronous-generator EMT template.

This is a structural validation script, not a network time-domain benchmark. It
checks that the standalone sixth-order core and the complete generator wrapper
instantiate with the expected STAMP-style states, algebraic interface, EMT
external mappings and controller connections.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Iterable

import numpy as np

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")))

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.stamp_synchronous_generator_emt_template import (
    get_stamp_synchronous_generator_emt_template,
    get_stamp_synchronous_machine_6th_order_emt_template,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)


PLOT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "stamp_sg_6th_order_validation_plots")


@dataclass(frozen=True)
class ValidationResult:
    name: str
    passed: bool
    detail: str


def _vars_in_block(block: Block) -> list:
    variables = []
    variables.extend(block.state_vars)
    variables.extend(block.diff_vars)
    variables.extend(block.algebraic_vars)
    variables.extend(block.in_vars)
    variables.extend(block.out_vars)
    variables.extend(block.event_dict.keys())
    variables.extend(block.api_obj_mapping.values())
    variables.extend(v for v in block.external_mapping.values() if v is not None)
    for child in block.children:
        variables.extend(_vars_in_block(child))
    return variables


def _names(items: Iterable) -> set[str]:
    return {item.name for item in items if item is not None}


def _contains_name(block: Block, expected: str) -> bool:
    return expected in _names(_vars_in_block(block))


def _find_name_in_block(name: str, block: Block):
    for var in _vars_in_block(block):
        if var is not None and var.name == name:
            return var
    for var in _vars_in_block(block):
        if var is not None and var.name.startswith(f"{name}_"):
            return var
    return None


def _state_value(problem: EmtProblemDae, states: np.ndarray, block: Block, name: str) -> float:
    var = _find_name_in_block(name=name, block=block)
    if var is None:
        return np.nan
    if var.uid in problem._uid2idx_vars:
        return float(states[problem.get_var_idx(var)])
    if var.uid in problem.uid2idx_event_params:
        return float(problem.event_params_values[problem.uid2idx_event_params[var.uid]])
    return np.nan


def _api_parameter_value(problem: EmtProblemDae, block: Block, ref: ParamPowerFlowReferenceType) -> float:
    target = block.api_obj_mapping.get(ref, None)
    if target is None:
        return np.nan
    if target.uid in problem.uid2idx_event_params:
        return float(problem.event_params_values[problem.uid2idx_event_params[target.uid]])
    if target.uid in problem.uid2idx_params:
        return float(problem.get_parameters_values()[problem.uid2idx_params[target.uid]].value)
    return np.nan


def _subtransient_derivative_values(problem: EmtProblemDae, states: np.ndarray, gen_mdl: Block) -> tuple[float, float]:
    psi_pp_d = _state_value(problem=problem, states=states, block=gen_mdl, name="psi_pp_d")
    psi_pp_q = _state_value(problem=problem, states=states, block=gen_mdl, name="psi_pp_q")
    e_qp = _state_value(problem=problem, states=states, block=gen_mdl, name="e_qp")
    e_dp = _state_value(problem=problem, states=states, block=gen_mdl, name="e_dp")
    i_d = _state_value(problem=problem, states=states, block=gen_mdl, name="i_d")
    i_q = _state_value(problem=problem, states=states, block=gen_mdl, name="i_q")
    xdp = _state_value(problem=problem, states=states, block=gen_mdl, name="xdp")
    xqp = _state_value(problem=problem, states=states, block=gen_mdl, name="xqp")
    xl = _state_value(problem=problem, states=states, block=gen_mdl, name="xl")
    td0pp = _state_value(problem=problem, states=states, block=gen_mdl, name="Td0pp")
    tq0pp = _state_value(problem=problem, states=states, block=gen_mdl, name="Tq0pp")

    d_psi_pp_d_rhs = (-psi_pp_d + e_qp - (xdp - xl) * i_d) / td0pp
    d_psi_pp_q_rhs = (-psi_pp_q - e_dp - (xqp - xl) * i_q) / tq0pp
    return d_psi_pp_d_rhs, d_psi_pp_q_rhs


def _print_exciter_values(problem: EmtProblemDae, states: np.ndarray, gen_mdl: Block, label: str) -> None:
    names = [
        "Vm",
        "Vc",
        "UsRefPu",
        "V_pss",
        "Verr",
        "exc_tr",
        "exc_field_feedback",
        "exc_leadlag_x",
        "exc_leadlag_y",
        "exc_avr",
        "Vf",
        "IRPu",
    ]
    values = {name: _state_value(problem=problem, states=states, block=gen_mdl, name=name) for name in names}
    print(label)
    for name in names:
        print(f"  {name:<20s} = {values[name]: .9e}")


def _signal(problem: EmtProblemDae, states: np.ndarray, block: Block, name: str) -> np.ndarray:
    var = _find_name_in_block(name=name, block=block)
    if var is None or var.uid not in problem._uid2idx_vars:
        return np.full(states.shape[0], np.nan)
    return states[:, problem.get_var_idx(var)]


def _save_sg_plots(problem: EmtProblemDae, t: np.ndarray, y: np.ndarray, gen_mdl: Block) -> None:
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)

    omega = _signal(problem=problem, states=y, block=gen_mdl, name="omega")
    omega_s = _signal(problem=problem, states=y, block=gen_mdl, name="omega_s")
    delta = _signal(problem=problem, states=y, block=gen_mdl, name="delta")
    te = _signal(problem=problem, states=y, block=gen_mdl, name="Te")
    tm = _signal(problem=problem, states=y, block=gen_mdl, name="Tm")
    irpu = _signal(problem=problem, states=y, block=gen_mdl, name="IRPu")
    ia = _signal(problem=problem, states=y, block=gen_mdl, name="i_A")
    ib = _signal(problem=problem, states=y, block=gen_mdl, name="i_B")
    ic = _signal(problem=problem, states=y, block=gen_mdl, name="i_C")
    eqp = _signal(problem=problem, states=y, block=gen_mdl, name="e_qp")
    edp = _signal(problem=problem, states=y, block=gen_mdl, name="e_dp")
    psi_pp_d = _signal(problem=problem, states=y, block=gen_mdl, name="psi_pp_d")
    psi_pp_q = _signal(problem=problem, states=y, block=gen_mdl, name="psi_pp_q")
    vm = _signal(problem=problem, states=y, block=gen_mdl, name="Vm")
    vc = _signal(problem=problem, states=y, block=gen_mdl, name="Vc")
    us_ref = _signal(problem=problem, states=y, block=gen_mdl, name="UsRefPu")
    vpss = _signal(problem=problem, states=y, block=gen_mdl, name="V_pss")
    verr = _signal(problem=problem, states=y, block=gen_mdl, name="Verr")
    exc_tr = _signal(problem=problem, states=y, block=gen_mdl, name="exc_tr")
    exc_fb = _signal(problem=problem, states=y, block=gen_mdl, name="exc_field_feedback")
    exc_ll_x = _signal(problem=problem, states=y, block=gen_mdl, name="exc_leadlag_x")
    exc_ll_y = _signal(problem=problem, states=y, block=gen_mdl, name="exc_leadlag_y")
    exc_avr = _signal(problem=problem, states=y, block=gen_mdl, name="exc_avr")
    vf = _signal(problem=problem, states=y, block=gen_mdl, name="Vf")

    plt.figure(figsize=(9, 6))
    plt.subplot(2, 1, 1)
    plt.plot(t, omega, label="omega [pu]")
    plt.plot(t, omega - omega_s, label="omega - omega_s [pu]")
    plt.grid(True)
    plt.legend()
    plt.subplot(2, 1, 2)
    plt.plot(t, delta, label="delta [rad]")
    plt.grid(True)
    plt.legend()
    plt.xlabel("Time [s]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "sg_speed_angle.png"), dpi=150)
    plt.close()

    plt.figure(figsize=(9, 6))
    plt.plot(t, ia, label="i_A")
    plt.plot(t, ib, label="i_B")
    plt.plot(t, ic, label="i_C")
    plt.grid(True)
    plt.legend()
    plt.xlabel("Time [s]")
    plt.ylabel("Current [pu]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "sg_phase_currents.png"), dpi=150)
    plt.close()

    plt.figure(figsize=(9, 6))
    plt.subplot(2, 1, 1)
    plt.plot(t, te, label="Te")
    plt.plot(t, tm, label="Tm")
    plt.plot(t, tm - te, label="Tm - Te")
    plt.grid(True)
    plt.legend()
    plt.subplot(2, 1, 2)
    plt.plot(t, irpu, label="IRPu / field signal")
    plt.grid(True)
    plt.legend()
    plt.xlabel("Time [s]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "sg_torque_field.png"), dpi=150)
    plt.close()

    plt.figure(figsize=(9, 6))
    plt.plot(t, eqp, label="e_qp")
    plt.plot(t, edp, label="e_dp")
    plt.plot(t, psi_pp_d, label="psi_pp_d")
    plt.plot(t, psi_pp_q, label="psi_pp_q")
    plt.grid(True)
    plt.legend()
    plt.xlabel("Time [s]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "sg_internal_states.png"), dpi=150)
    plt.close()

    plt.figure(figsize=(10, 8))
    plt.subplot(3, 1, 1)
    plt.plot(t, vm, label="Vm")
    plt.plot(t, vc, label="Vc")
    plt.plot(t, us_ref, label="UsRefPu")
    plt.plot(t, vpss, label="V_pss")
    plt.grid(True)
    plt.legend()
    plt.subplot(3, 1, 2)
    plt.plot(t, verr, label="Verr")
    plt.plot(t, exc_fb, label="field feedback")
    plt.plot(t, exc_ll_x, label="leadlag x")
    plt.plot(t, exc_ll_y, label="leadlag y")
    plt.grid(True)
    plt.legend()
    plt.subplot(3, 1, 3)
    plt.plot(t, exc_avr, label="exc_avr")
    plt.plot(t, vf, label="Vf")
    plt.plot(t, irpu, label="IRPu")
    plt.grid(True)
    plt.legend()
    plt.xlabel("Time [s]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "sg_exciter_states.png"), dpi=150)
    plt.close()

    plt.figure(figsize=(9, 6))
    plt.plot(t, exc_tr, label="exc_tr")
    plt.plot(t, exc_fb, label="exc_field_feedback")
    plt.plot(t, exc_ll_x, label="exc_leadlag_x")
    plt.plot(t, exc_ll_y, label="exc_leadlag_y")
    plt.plot(t, exc_avr, label="exc_avr")
    plt.grid(True)
    plt.legend()
    plt.xlabel("Time [s]")
    plt.ylabel("State value [pu]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "sg_exciter_dynamic_states.png"), dpi=150)
    plt.close()


def _save_load_event_plots(problem: EmtProblemDae, t: np.ndarray, y: np.ndarray, load_mdl: Block) -> None:
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)

    p_a = _signal(problem=problem, states=y, block=load_mdl, name="P_A")
    q_a = _signal(problem=problem, states=y, block=load_mdl, name="Q_A")
    ia = _signal(problem=problem, states=y, block=load_mdl, name="i_A")
    ib = _signal(problem=problem, states=y, block=load_mdl, name="i_B")
    ic = _signal(problem=problem, states=y, block=load_mdl, name="i_C")

    plt.figure(figsize=(9, 6))
    plt.subplot(2, 1, 1)
    plt.plot(t, p_a, label="Load P_A")
    plt.plot(t, q_a, label="Load Q_A")
    plt.grid(True)
    plt.legend()
    plt.subplot(2, 1, 2)
    plt.plot(t, ia, label="Load i_A")
    plt.plot(t, ib, label="Load i_B")
    plt.plot(t, ic, label="Load i_C")
    plt.grid(True)
    plt.legend()
    plt.xlabel("Time [s]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "load_event_response.png"), dpi=150)
    plt.close()


def _save_startup_diagnostic_plots(problem: EmtProblemDae, t: np.ndarray, y: np.ndarray, line_mdl: Block, load_mdl: Block) -> None:
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)

    startup_mask = t <= 0.01
    if not np.any(startup_mask):
        startup_mask = np.ones_like(t, dtype=bool)
    t_start = t[startup_mask]
    y_start = y[startup_mask]

    p_a = _signal(problem=problem, states=y_start, block=load_mdl, name="P_A")
    q_a = _signal(problem=problem, states=y_start, block=load_mdl, name="Q_A")
    ia = _signal(problem=problem, states=y_start, block=load_mdl, name="i_A")
    ib = _signal(problem=problem, states=y_start, block=load_mdl, name="i_B")
    ic = _signal(problem=problem, states=y_start, block=load_mdl, name="i_C")

    plt.figure(figsize=(9, 6))
    plt.subplot(2, 1, 1)
    plt.plot(t_start, p_a, label="Load P_A")
    plt.plot(t_start, q_a, label="Load Q_A")
    plt.grid(True)
    plt.legend()
    plt.subplot(2, 1, 2)
    plt.plot(t_start, ia, label="Load i_A")
    plt.plot(t_start, ib, label="Load i_B")
    plt.plot(t_start, ic, label="Load i_C")
    plt.grid(True)
    plt.legend()
    plt.xlabel("Time [s]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "startup_load_event_response_zoom.png"), dpi=150)
    plt.close()

    vm_a = _signal(problem=problem, states=y_start, block=load_mdl, name="VmA")
    ratio_a = _signal(problem=problem, states=y_start, block=load_mdl, name="rA")
    u_a = _signal(problem=problem, states=y_start, block=load_mdl, name="u_A")
    q_sogi_a = _signal(problem=problem, states=y_start, block=load_mdl, name="q_A")

    plt.figure(figsize=(9, 7))
    plt.subplot(3, 1, 1)
    plt.plot(t_start, p_a, label="Load P_A")
    plt.plot(t_start, q_a, label="Load Q_A")
    plt.grid(True)
    plt.legend()
    plt.subplot(3, 1, 2)
    plt.plot(t_start, vm_a, label="VmA")
    plt.plot(t_start, ratio_a, label="rA = VmA / V0")
    plt.grid(True)
    plt.legend()
    plt.subplot(3, 1, 3)
    plt.plot(t_start, u_a, label="u_A")
    plt.plot(t_start, q_sogi_a, label="q_A SOGI")
    plt.grid(True)
    plt.legend()
    plt.xlabel("Time [s]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "startup_load_power_vs_voltage_magnitude.png"), dpi=150)
    plt.close()

    plt.figure(figsize=(10, 8))
    plt.subplot(3, 1, 1)
    for phase in ("A", "B", "C"):
        plt.plot(t_start, _signal(problem, y_start, line_mdl, f"i_ser_Pi_gen_load_{phase}"), label=f"i_ser_{phase}")
    plt.grid(True)
    plt.legend()
    plt.subplot(3, 1, 2)
    for phase in ("A", "B", "C"):
        plt.plot(t_start, _signal(problem, y_start, line_mdl, f"q_f_Pi_gen_load_{phase}"), label=f"q_f_{phase}")
        plt.plot(t_start, _signal(problem, y_start, line_mdl, f"q_t_Pi_gen_load_{phase}"), linestyle="--", label=f"q_t_{phase}")
    plt.grid(True)
    plt.legend(ncol=2)
    plt.subplot(3, 1, 3)
    for phase in ("A", "B", "C"):
        plt.plot(t_start, _signal(problem, y_start, line_mdl, f"i_cap_f_Pi_gen_load_{phase}"), label=f"i_cap_f_{phase}")
        plt.plot(t_start, _signal(problem, y_start, line_mdl, f"i_cap_t_Pi_gen_load_{phase}"), linestyle="--", label=f"i_cap_t_{phase}")
    plt.grid(True)
    plt.legend(ncol=2)
    plt.xlabel("Time [s]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "startup_pi_line_states.png"), dpi=150)
    plt.close()

    plt.figure(figsize=(10, 8))
    plt.subplot(3, 1, 1)
    for phase in ("A", "B", "C"):
        plt.plot(t_start, _signal(problem, y_start, load_mdl, f"u_{phase}_LoadZIP_2bus"), label=f"u_{phase}")
    plt.grid(True)
    plt.legend()
    plt.subplot(3, 1, 2)
    for phase in ("A", "B", "C"):
        plt.plot(t_start, _signal(problem, y_start, load_mdl, f"q_{phase}_LoadZIP_2bus"), label=f"q_{phase}")
    plt.grid(True)
    plt.legend()
    plt.subplot(3, 1, 3)
    for phase in ("A", "B", "C"):
        plt.plot(t_start, _signal(problem, y_start, load_mdl, f"i_{phase}_LoadZIP_2bus"), label=f"i_{phase}")
    plt.grid(True)
    plt.legend()
    plt.xlabel("Time [s]")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "startup_zip_load_states.png"), dpi=150)
    plt.close()


def _check(condition: bool, name: str, ok_detail: str, fail_detail: str) -> ValidationResult:
    return ValidationResult(name=name, passed=condition, detail=ok_detail if condition else fail_detail)


def validate_machine_core() -> list[ValidationResult]:
    vf = VarFactory()
    template = get_stamp_synchronous_machine_6th_order_emt_template(vf=vf, name="stamp_core_validation")
    block = template.block

    expected_state_suffixes = {
        "theta_abs_stamp_core_validation",
        "delta_stamp_core_validation",
        "omega_stamp_core_validation",
        "e_qp_stamp_core_validation",
        "e_dp_stamp_core_validation",
        "psi_pp_d_stamp_core_validation",
        "psi_pp_q_stamp_core_validation",
    }
    actual_states = _names(block.state_vars)
    expected_static_refs = {
        ParamPowerFlowReferenceType.omega_base,
        ParamPowerFlowReferenceType.R1,
        ParamPowerFlowReferenceType.X1,
        ParamPowerFlowReferenceType.X0,
        ParamPowerFlowReferenceType.Ra,
        ParamPowerFlowReferenceType.Rs,
        ParamPowerFlowReferenceType.Xd,
        ParamPowerFlowReferenceType.Xq,
        ParamPowerFlowReferenceType.Xd_prime,
        ParamPowerFlowReferenceType.Xq_prime,
        ParamPowerFlowReferenceType.Xd_2prime,
        ParamPowerFlowReferenceType.Xq_2prime,
        ParamPowerFlowReferenceType.Xl,
        ParamPowerFlowReferenceType.Td0_prime,
        ParamPowerFlowReferenceType.Tq0_prime,
        ParamPowerFlowReferenceType.Td0_2prime,
        ParamPowerFlowReferenceType.Tq0_2prime,
        ParamPowerFlowReferenceType.D,
    }

    results = [
        _check(
            len(block.state_vars) == 7,
            "core_state_count",
            "core has 7 dynamic states: 6th-order machine plus EMT absolute angle",
            f"expected 7 states, got {len(block.state_vars)}",
        ),
        _check(
            expected_state_suffixes.issubset(actual_states),
            "core_state_names",
            "core state names match STAMP 6th-order structure",
            f"missing states: {sorted(expected_state_suffixes - actual_states)}",
        ),
        _check(
            len(block.state_eqs) == len(block.state_vars) == len(block.diff_vars),
            "core_state_equation_lengths",
            "state equations, state variables and diff variables are aligned",
            f"state_eqs={len(block.state_eqs)}, state_vars={len(block.state_vars)}, diff_vars={len(block.diff_vars)}",
        ),
        _check(
            len(block.algebraic_eqs) == len(block.algebraic_vars),
            "core_algebraic_equation_lengths",
            "algebraic equations and variables are aligned",
            f"algebraic_eqs={len(block.algebraic_eqs)}, algebraic_vars={len(block.algebraic_vars)}",
        ),
        _check(
            len(block.in_vars) == 5 and len(block.out_vars) == 6,
            "core_ports",
            "core exposes abc voltage, mechanical torque and field-voltage inputs plus current/speed/field/torque outputs",
            f"expected 5 inputs and 6 outputs, got {len(block.in_vars)} inputs and {len(block.out_vars)} outputs",
        ),
        _check(
            all(ref in block.external_mapping for ref in (
                VarPowerFlowReferenceType.i_A,
                VarPowerFlowReferenceType.i_B,
                VarPowerFlowReferenceType.i_C,
                VarPowerFlowReferenceType.d_v_A,
                VarPowerFlowReferenceType.d_v_B,
                VarPowerFlowReferenceType.d_v_C,
                VarPowerFlowReferenceType.P_A,
                VarPowerFlowReferenceType.Q_A,
                VarPowerFlowReferenceType.P_B,
                VarPowerFlowReferenceType.Q_B,
                VarPowerFlowReferenceType.P_C,
                VarPowerFlowReferenceType.Q_C,
            )),
            "core_external_mapping",
            "core has the EMT power-flow initialization mapping needed by the DAE initializer",
            "core external mapping is missing one or more EMT initialization references",
        ),
        _check(
            expected_static_refs.issubset(set(block.api_obj_mapping)),
            "core_api_mapping",
            "core has API mappings for frequency, sequence impedance and STAMP machine parameters",
            f"core API mapping is missing refs: {sorted(ref.value for ref in expected_static_refs - set(block.api_obj_mapping))}",
        ),
    ]
    return results


def validate_complete_wrapper() -> list[ValidationResult]:
    vf = VarFactory()
    template = get_stamp_synchronous_generator_emt_template(vf=vf, name="stamp_wrapper_validation")
    block = template.block

    child_names = [child.name for child in block.children]
    results = [
        _check(
            len(block.children) == 4,
            "wrapper_child_count",
            "wrapper contains machine, governor, stabilizer and exciter children",
            f"expected 4 child blocks, got {len(block.children)}: {child_names}",
        ),
        _check(
            any("_gen" in name for name in child_names)
            and any("_governor" in name for name in child_names)
            and any("_stabilizer" in name for name in child_names)
            and any("_exciter" in name for name in child_names),
            "wrapper_child_names",
            "wrapper child names identify machine, governor, stabilizer and exciter blocks",
            f"unexpected wrapper child names: {child_names}",
        ),
        _check(
            len(block.in_vars) == 3 and len(block.out_vars) == 3,
            "wrapper_ports",
            "wrapper exposes only the standard EMT generator abc voltage/current boundary",
            f"expected 3 inputs and 3 outputs, got {len(block.in_vars)} inputs and {len(block.out_vars)} outputs",
        ),
        _check(
            all(ref in block.external_mapping for ref in (
                VarPowerFlowReferenceType.v_A,
                VarPowerFlowReferenceType.v_B,
                VarPowerFlowReferenceType.v_C,
                VarPowerFlowReferenceType.i_A,
                VarPowerFlowReferenceType.i_B,
                VarPowerFlowReferenceType.i_C,
                VarPowerFlowReferenceType.P_A,
                VarPowerFlowReferenceType.Q_A,
                VarPowerFlowReferenceType.P_B,
                VarPowerFlowReferenceType.Q_B,
                VarPowerFlowReferenceType.P_C,
                VarPowerFlowReferenceType.Q_C,
            )),
            "wrapper_external_mapping",
            "wrapper exposes voltage/current and PF initialization references",
            "wrapper external mapping is missing EMT terminal or initialization references",
        ),
        _check(
            ParamPowerFlowReferenceType.generator_share_p_ref in block.api_obj_mapping,
            "wrapper_governor_reference_mapping",
            "wrapper exposes the governor mechanical-power sharing reference",
            "wrapper does not expose the governor mechanical-power sharing reference",
        ),
        _check(
            _contains_name(block, "Tm_stamp_wrapper_validation_governor")
            and _contains_name(block, "Vf_stamp_wrapper_validation_exciter")
            and _contains_name(block, "V_pss_stamp_wrapper_validation_stabilizer"),
            "wrapper_controller_variables",
            "governor torque, exciter field voltage and PSS output variables are present",
            "one or more controller variables are missing from the wrapper hierarchy",
        ),
    ]
    return results


def build_two_bus_emt_case() -> tuple[gce.MultiCircuit, EmtProblemDae, Block, Block, Block]:
    grid = gce.MultiCircuit(name="STAMP SG 6th-order EMT validation", Sbase=100.0, fbase=50.0)
    grid.fBase = 50.0

    bus_gen = gce.Bus(name="B_gen", Vnom=110.0, is_slack=True)
    bus_load = gce.Bus(name="B_load", Vnom=110.0)
    grid.add_bus(bus_gen)
    grid.add_bus(bus_load)

    get_bus_emt_template(grid, bus_gen)
    get_bus_emt_template(grid, bus_load)

    line = gce.Line(
        name="L_gen_load",
        bus_from=bus_gen,
        bus_to=bus_load,
        r=0.01,
        x=0.08,
        b=0.01,
        rate=250.0,
    )
    gen = gce.Generator(
        name="G_stamp_6th",
        P=55.0,
        vset=1.0,
        Snom=100.0,
        freq=50.0,
        r1=0.0025,
        x1=1.8,
        x0=0.14,
    )
    load = gce.Load(name="Load_2bus", P=50.0, Q=15.0)

    grid.add_line(line)
    grid.add_generator(bus=bus_gen, api_obj=gen)
    grid.add_load(bus=bus_load, api_obj=load)

    pf_options = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-7,
        max_iter=30,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    pf_results = gce.power_flow(grid, options=pf_options)

    line_mdl = get_pi_line_emt_template(vf=grid.var_factory, name="Pi_gen_load").block
    gen_mdl = get_stamp_synchronous_generator_emt_template(
        vf=grid.var_factory,
        name="StampSG6th_2bus",
    ).block
    load_mdl = get_load_ZIP_emt_template(vf=grid.var_factory, name="LoadZIP_2bus").block

    set_emt_model(device=line, model=line_mdl, var_factory=grid.var_factory)
    set_emt_model(device=gen, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    load_p_a_ref = load_mdl.api_obj_mapping[ParamPowerFlowReferenceType.Pl0_A]
    load_step_event = EmtEvent(
        device=load,
        parameter=load_p_a_ref,
        time=0.02,
        value=0.22,
        force_step_alignment=True,
        name="Load phase-A active-power step",
    )
    grid.add_emt_event(load_step_event)

    emt_options = EmtOptions(
        time_step=0.0001,
        simulation_time=0.08,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        solver_type=EmtSolverTypes.StructuralAD,
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=emt_options, pf_results=pf_results)
    problem.set_events_group(None)
    return grid, problem, gen_mdl, load_mdl, line_mdl


def validate_two_bus_simulation() -> list[ValidationResult]:
    try:
        _, problem, gen_mdl, load_mdl, line_mdl = build_two_bus_emt_case()
        solver = build_emt_solver(
            options=problem.options,
            problem=problem,
            t0=0.0,
            t_end=problem.options.simulation_time,
            h=problem.options.time_step,
            method=problem.options.integration_method,
        )
        t, y, _, well_initialized, converged = solver.simulate()
        _save_sg_plots(problem=problem, t=t, y=y, gen_mdl=gen_mdl)
        _save_load_event_plots(problem=problem, t=t, y=y, load_mdl=load_mdl)
        _save_startup_diagnostic_plots(problem=problem, t=t, y=y, line_mdl=line_mdl, load_mdl=load_mdl)
    except Exception as exc:
        return [ValidationResult(
            name="two_bus_simulation_exception",
            passed=False,
            detail=f"2-bus EMT simulation raised {type(exc).__name__}: {exc}",
        )]

    final_state = y[-1] if len(y) else np.array([])
    gen_ia = _state_value(problem=problem, states=final_state, block=gen_mdl, name="i_A")
    load_ia = _state_value(problem=problem, states=final_state, block=load_mdl, name="i_A")
    omega = _state_value(problem=problem, states=final_state, block=gen_mdl, name="omega")
    omega_s = _state_value(problem=problem, states=final_state, block=gen_mdl, name="omega_s")
    omega_dev = omega - omega_s

    initial_state = y[0] if len(y) else np.array([])
    omega0 = _state_value(problem=problem, states=initial_state, block=gen_mdl, name="omega")
    omega_s0 = _state_value(problem=problem, states=initial_state, block=gen_mdl, name="omega_s")
    omega_dev0 = omega0 - omega_s0
    omega_base = _api_parameter_value(problem=problem, block=gen_mdl, ref=ParamPowerFlowReferenceType.omega_base)
    r1 = _api_parameter_value(problem=problem, block=gen_mdl, ref=ParamPowerFlowReferenceType.R1)
    x1 = _api_parameter_value(problem=problem, block=gen_mdl, ref=ParamPowerFlowReferenceType.X1)
    x0 = _api_parameter_value(problem=problem, block=gen_mdl, ref=ParamPowerFlowReferenceType.X0)
    d_psi_pp_d0, d_psi_pp_q0 = _subtransient_derivative_values(problem=problem, states=initial_state, gen_mdl=gen_mdl)
    d_psi_pp_d1, d_psi_pp_q1 = _subtransient_derivative_values(problem=problem, states=final_state, gen_mdl=gen_mdl)

    print(f"Mapped omega_base = {omega_base:.9e}")
    print(f"Mapped R1/X1/X0  = {r1:.9e} / {x1:.9e} / {x0:.9e}")
    print(f"Initial omega - omega_s = {omega_dev0:.9e}")
    print(f"Final   omega - omega_s = {omega_dev:.9e}")
    print(f"Initial d_psi_pp_d RHS = {d_psi_pp_d0:.9e}")
    print(f"Initial d_psi_pp_q RHS = {d_psi_pp_q0:.9e}")
    print(f"Final   d_psi_pp_d RHS = {d_psi_pp_d1:.9e}")
    print(f"Final   d_psi_pp_q RHS = {d_psi_pp_q1:.9e}")
    _print_exciter_values(problem=problem, states=initial_state, gen_mdl=gen_mdl, label="Initial exciter values")
    _print_exciter_values(problem=problem, states=final_state, gen_mdl=gen_mdl, label="Final exciter values")

    print("First exciter samples: k, t, Vf, IRPu, Vm, UsRefPu, Verr, exc_avr")
    for k in range(min(6, len(t))):
        row = y[k]
        print(
            f"  {k:2d} {t[k]:.7f} "
            f"{_state_value(problem, row, gen_mdl, 'Vf'): .9e} "
            f"{_state_value(problem, row, gen_mdl, 'IRPu'): .9e} "
            f"{_state_value(problem, row, gen_mdl, 'Vm'): .9e} "
            f"{_state_value(problem, row, gen_mdl, 'UsRefPu'): .9e} "
            f"{_state_value(problem, row, gen_mdl, 'Verr'): .9e} "
            f"{_state_value(problem, row, gen_mdl, 'exc_avr'): .9e}"
        )

    return [
        _check(
            bool(well_initialized),
            "two_bus_well_initialized",
            "2-bus EMT problem initialized successfully",
            "2-bus EMT problem was not well initialized",
        ),
        _check(
            bool(converged),
            "two_bus_converged",
            "2-bus EMT simulation converged",
            "2-bus EMT simulation did not converge",
        ),
        _check(
            len(t) >= 2 and len(y) == len(t),
            "two_bus_time_series",
            f"2-bus EMT simulation produced {len(t)} time samples",
            f"invalid time/state output lengths: len(t)={len(t)}, len(y)={len(y)}",
        ),
        _check(
            final_state.size > 0 and np.all(np.isfinite(final_state)),
            "two_bus_finite_states",
            "2-bus EMT final state is finite",
            "2-bus EMT final state has NaN/Inf values or is empty",
        ),
        _check(
            np.isclose(omega_base, 2.0 * np.pi * 50.0)
            and np.isclose(r1, 0.0025)
            and np.isclose(x1, 1.8)
            and np.isclose(x0, 0.14),
            "two_bus_generator_api_values",
            "Generator-derived omega_base/R1/X1/X0 values reached the EMT model",
            f"unexpected mapped generator values: omega_base={omega_base}, R1={r1}, X1={x1}, X0={x0}",
        ),
        _check(
            np.isfinite(gen_ia) and abs(gen_ia) > 1e-8 and np.isfinite(load_ia) and abs(load_ia) > 1e-8,
            "two_bus_nonzero_currents",
            f"generator/load phase-A currents are finite and non-zero: gen={gen_ia:.6e}, load={load_ia:.6e}",
            f"invalid generator/load phase-A currents: gen={gen_ia}, load={load_ia}",
        ),
        _check(
            np.isfinite(omega) and 0.5 < omega < 1.5,
            "two_bus_generator_speed",
            f"generator speed remains in a plausible pu range: omega={omega:.6e}, omega-omega_s={omega_dev:.6e}",
            f"generator speed is invalid or implausible: omega={omega}, omega-omega_s={omega_dev}",
        ),
        _check(
            np.all(np.isfinite([d_psi_pp_d0, d_psi_pp_q0, d_psi_pp_d1, d_psi_pp_q1])),
            "two_bus_subtransient_derivatives",
            f"subtransient derivative RHS values are finite: initial=({d_psi_pp_d0:.6e}, {d_psi_pp_q0:.6e}), final=({d_psi_pp_d1:.6e}, {d_psi_pp_q1:.6e})",
            f"invalid subtransient derivative RHS values: initial=({d_psi_pp_d0}, {d_psi_pp_q0}), final=({d_psi_pp_d1}, {d_psi_pp_q1})",
        ),
    ]


def run_validation() -> bool:
    results = validate_machine_core() + validate_complete_wrapper() + validate_two_bus_simulation()
    max_name_len = max(len(result.name) for result in results)
    ok = True
    print("STAMP sixth-order SG EMT validation")
    print("=" * 39)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status:4s}  {result.name:<{max_name_len}s}  {result.detail}")
        ok = ok and result.passed
    print("=" * 39)
    print("Result:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if run_validation() else 1)
