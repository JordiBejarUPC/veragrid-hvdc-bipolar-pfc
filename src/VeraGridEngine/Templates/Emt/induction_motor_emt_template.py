"""EMT induction-motor templates.

This module provides three EMT induction-motor builders that share the same
external ABC bus interface and the same load-oriented power-flow parameter
mappings. The recommended implementation is the Level-2 single-cage EMT model.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block, Expr, Var
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowRefferenceType, VarPowerFlowRefferenceType


_PI: float = math.pi
_SQRT3: float = math.sqrt(3.0)
_A_POS: complex = complex(-0.5, _SQRT3 / 2.0)
_A_NEG: complex = complex(-0.5, -_SQRT3 / 2.0)


def _build_motor_external_mapping(
    v_a: Var,
    v_b: Var,
    v_c: Var,
    i_a: Var,
    i_b: Var,
    i_c: Var,
    d_v_a: Var,
    d_v_b: Var,
    d_v_c: Var,
) -> Dict[VarPowerFlowRefferenceType, Var | None]:
    """Build one ABC load external mapping for the motor.

    :param v_a: Phase-A terminal voltage.
    :param v_b: Phase-B terminal voltage.
    :param v_c: Phase-C terminal voltage.
    :param i_a: Phase-A injected current.
    :param i_b: Phase-B injected current.
    :param i_c: Phase-C injected current.
    :param d_v_a: Phase-A voltage derivative.
    :param d_v_b: Phase-B voltage derivative.
    :param d_v_c: Phase-C voltage derivative.
    :return: EMT external mapping dictionary.
    """
    return dict({
        VarPowerFlowRefferenceType.v_N: None,
        VarPowerFlowRefferenceType.v_A: v_a,
        VarPowerFlowRefferenceType.v_B: v_b,
        VarPowerFlowRefferenceType.v_C: v_c,
        VarPowerFlowRefferenceType.P: None,
        VarPowerFlowRefferenceType.Q: None,
        VarPowerFlowRefferenceType.P_N: None,
        VarPowerFlowRefferenceType.Q_N: None,
        VarPowerFlowRefferenceType.P_A: None,
        VarPowerFlowRefferenceType.Q_A: None,
        VarPowerFlowRefferenceType.P_B: None,
        VarPowerFlowRefferenceType.Q_B: None,
        VarPowerFlowRefferenceType.P_C: None,
        VarPowerFlowRefferenceType.Q_C: None,
        VarPowerFlowRefferenceType.i_N: None,
        VarPowerFlowRefferenceType.i_A: i_a,
        VarPowerFlowRefferenceType.i_B: i_b,
        VarPowerFlowRefferenceType.i_C: i_c,
        VarPowerFlowRefferenceType.phi_v: None,
        VarPowerFlowRefferenceType.phi: None,
        VarPowerFlowRefferenceType.Vpk: None,
        VarPowerFlowRefferenceType.Ipk: None,
        VarPowerFlowRefferenceType.d_v_N: None,
        VarPowerFlowRefferenceType.d_v_A: d_v_a,
        VarPowerFlowRefferenceType.d_v_B: d_v_b,
        VarPowerFlowRefferenceType.d_v_C: d_v_c,
    })


def _build_motor_api_mapping(
    omega_base: Var,
    p0_a: Var,
    p0_b: Var,
    p0_c: Var,
    q0_a: Var,
    q0_b: Var,
    q0_c: Var,
) -> Dict[ParamPowerFlowRefferenceType, Var | None]:
    """Build the API parameter mapping used by EMT initialization.

    :param omega_base: Electrical base speed in rad/s.
    :param p0_a: Phase-A active-power target.
    :param p0_b: Phase-B active-power target.
    :param p0_c: Phase-C active-power target.
    :param q0_a: Phase-A reactive-power target.
    :param q0_b: Phase-B reactive-power target.
    :param q0_c: Phase-C reactive-power target.
    :return: API object mapping dictionary.
    """
    return dict({
        ParamPowerFlowRefferenceType.omega_base: omega_base,
        ParamPowerFlowRefferenceType.Pl0_A: p0_a,
        ParamPowerFlowRefferenceType.Pl0_B: p0_b,
        ParamPowerFlowRefferenceType.Pl0_C: p0_c,
        ParamPowerFlowRefferenceType.Ql0_A: q0_a,
        ParamPowerFlowRefferenceType.Ql0_B: q0_b,
        ParamPowerFlowRefferenceType.Ql0_C: q0_c,
    })


def _phase_peak_phasor(voltage_var: Var, derivative_var: Var, omega_base: Var, eps: Expr) -> Expr:
    """Return one peak complex phasor from EMT ``v`` and ``d_v`` inputs.

    :param voltage_var: Instantaneous phase voltage at ``t = 0``.
    :param derivative_var: Instantaneous voltage derivative at ``t = 0``.
    :param omega_base: Electrical base speed in rad/s.
    :param eps: Small positive denominator protection.
    :return: Complex peak phasor expression.
    """
    return derivative_var / (omega_base + eps) + sym.Const(complex(0.0, 1.0)) * voltage_var


def _abc_to_alpha_beta(a_val: Expr, b_val: Expr, c_val: Expr) -> Tuple[Expr, Expr]:
    """Apply the amplitude-invariant Clarke transform to one ABC triple.

    :param a_val: Phase-A value.
    :param b_val: Phase-B value.
    :param c_val: Phase-C value.
    :return: Tuple ``(alpha, beta)``.
    """
    alpha_val: Expr = sym.Const(2.0 / 3.0) * (a_val - sym.Const(0.5) * b_val - sym.Const(0.5) * c_val)
    beta_val: Expr = sym.Const(1.0 / _SQRT3) * (b_val - c_val)
    return alpha_val, beta_val


def _alpha_beta_to_abc(alpha_val: Expr, beta_val: Expr) -> Tuple[Expr, Expr, Expr]:
    """Return one inverse Clarke transform for three-wire ABC currents.

    :param alpha_val: Alpha-axis value.
    :param beta_val: Beta-axis value.
    :return: Tuple ``(a, b, c)``.
    """
    a_val: Expr = alpha_val
    b_val: Expr = -sym.Const(0.5) * alpha_val + sym.Const(_SQRT3 / 2.0) * beta_val
    c_val: Expr = -sym.Const(0.5) * alpha_val - sym.Const(_SQRT3 / 2.0) * beta_val
    return a_val, b_val, c_val


def _space_vector_positive_sequence(a_val: Expr, b_val: Expr, c_val: Expr) -> Expr:
    """Return one positive-sequence phase-A peak phasor estimate.

    :param a_val: Phase-A peak phasor.
    :param b_val: Phase-B peak phasor.
    :param c_val: Phase-C peak phasor.
    :return: Positive-sequence phase-A phasor.
    """
    return (a_val + sym.Const(_A_POS) * b_val + sym.Const(_A_NEG) * c_val) / sym.Const(3.0)


def _build_common_events(
    vf: VarFactory,
    block: Block,
    name: str,
) -> Dict[str, Var]:
    """Create the common motor parameters and their default values.

    :param vf: EMT variable factory.
    :param block: Target symbolic block.
    :param name: Symbolic suffix.
    :return: Dictionary with the created parameter variables.
    """
    parameters: Dict[str, Var] = dict()

    parameters["omega_base"] = vf.add_var(name=f"omega_base_{name}")
    parameters["p0_a"] = vf.add_var(name=f"P0_A_{name}")
    parameters["p0_b"] = vf.add_var(name=f"P0_B_{name}")
    parameters["p0_c"] = vf.add_var(name=f"P0_C_{name}")
    parameters["q0_a"] = vf.add_var(name=f"Q0_A_{name}")
    parameters["q0_b"] = vf.add_var(name=f"Q0_B_{name}")
    parameters["q0_c"] = vf.add_var(name=f"Q0_C_{name}")

    parameters["r_s"] = vf.add_var(name=f"r_s_{name}")
    parameters["x_ls"] = vf.add_var(name=f"x_ls_{name}")
    parameters["x_m"] = vf.add_var(name=f"x_m_{name}")
    parameters["h"] = vf.add_var(name=f"H_{name}")
    parameters["d"] = vf.add_var(name=f"D_{name}")
    parameters["slip_init"] = vf.add_var(name=f"slip_init_{name}")
    parameters["slip_min"] = vf.add_var(name=f"slip_min_{name}")
    parameters["slip_max"] = vf.add_var(name=f"slip_max_{name}")
    parameters["speed_eps"] = vf.add_var(name=f"speed_eps_{name}")
    parameters["t_load_nom"] = vf.add_var(name=f"t_load_nom_{name}")

    block.event_dict[parameters["omega_base"]] = vf.add_const(2.0 * _PI * 50.0)
    block.event_dict[parameters["p0_a"]] = vf.add_const(0.10 / 3.0)
    block.event_dict[parameters["p0_b"]] = vf.add_const(0.10 / 3.0)
    block.event_dict[parameters["p0_c"]] = vf.add_const(0.10 / 3.0)
    block.event_dict[parameters["q0_a"]] = vf.add_const(0.04 / 3.0)
    block.event_dict[parameters["q0_b"]] = vf.add_const(0.04 / 3.0)
    block.event_dict[parameters["q0_c"]] = vf.add_const(0.04 / 3.0)
    block.event_dict[parameters["r_s"]] = vf.add_const(0.025)
    block.event_dict[parameters["x_ls"]] = vf.add_const(0.12)
    block.event_dict[parameters["x_m"]] = vf.add_const(3.0)
    block.event_dict[parameters["h"]] = vf.add_const(0.5)
    block.event_dict[parameters["d"]] = vf.add_const(0.0)
    block.event_dict[parameters["slip_init"]] = vf.add_const(0.02)
    block.event_dict[parameters["slip_min"]] = vf.add_const(1e-3)
    block.event_dict[parameters["slip_max"]] = vf.add_const(1.0)
    block.event_dict[parameters["speed_eps"]] = vf.add_const(1e-3)
    block.event_dict[parameters["t_load_nom"]] = vf.add_const(None)
    return parameters


def _set_common_block_metadata(
    templ: EmtModelTemplate,
    name: str,
    v_a: Var,
    v_b: Var,
    v_c: Var,
    i_a: Var,
    i_b: Var,
    i_c: Var,
    d_v_a: Var,
    d_v_b: Var,
    d_v_c: Var,
    params: Dict[str, Var],
) -> None:
    """Publish the common load metadata for one motor template.

    :param templ: EMT template to populate.
    :param name: Template name.
    :param v_a: Phase-A voltage input.
    :param v_b: Phase-B voltage input.
    :param v_c: Phase-C voltage input.
    :param i_a: Phase-A injected current output.
    :param i_b: Phase-B injected current output.
    :param i_c: Phase-C injected current output.
    :param d_v_a: Phase-A voltage derivative input.
    :param d_v_b: Phase-B voltage derivative input.
    :param d_v_c: Phase-C voltage derivative input.
    :param params: Dictionary of common parameter variables.
    :return: None.
    """
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    templ.block.name = name
    templ.block.in_vars = [v_a, v_b, v_c]
    templ.block.out_vars = [i_a, i_b, i_c]
    templ.block.external_mapping = _build_motor_external_mapping(
        v_a=v_a,
        v_b=v_b,
        v_c=v_c,
        i_a=i_a,
        i_b=i_b,
        i_c=i_c,
        d_v_a=d_v_a,
        d_v_b=d_v_b,
        d_v_c=d_v_c,
    )
    templ.block.api_obj_mapping = _build_motor_api_mapping(
        omega_base=params["omega_base"],
        p0_a=params["p0_a"],
        p0_b=params["p0_b"],
        p0_c=params["p0_c"],
        q0_a=params["q0_a"],
        q0_b=params["q0_b"],
        q0_c=params["q0_c"],
    )


def get_induction_motor_single_cage_emt_template(
    vf: VarFactory,
    name: str = "induction_motor_emt_template",
) -> EmtModelTemplate:
    """Build the recommended Level-2 EMT single-cage induction-motor template.

    The model uses a stationary ``alpha-beta`` formulation internally so it can
    connect directly to the existing EMT ABC bus architecture while still keeping
    explicit stator and rotor electrical dynamics.

    Mechanical torque follows a quadratic speed law, which is a practical default
    for fan- and pump-like motor loads. The nominal torque coefficient is seeded
    from the electrical initial condition so the machine starts from a consistent
    operating point when power-flow data is available.

    :param vf: EMT variable factory.
    :param name: Symbolic template name.
    :return: Configured EMT template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    block: Block = templ.block
    params: Dict[str, Var] = _build_common_events(vf=vf, block=block, name=name)
    r_r: Var = vf.add_var(name=f"r_r_{name}")
    x_lr: Var = vf.add_var(name=f"x_lr_{name}")
    block.event_dict[r_r] = vf.add_const(0.02)
    block.event_dict[x_lr] = vf.add_const(0.12)

    v_a: Var = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_b: Var = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_c: Var = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)
    d_v_a: Var = vf.add_var(name=f"d_v_A_{name}")
    d_v_b: Var = vf.add_var(name=f"d_v_B_{name}")
    d_v_c: Var = vf.add_var(name=f"d_v_C_{name}")
    block.event_dict[d_v_a] = vf.add_const(None)
    block.event_dict[d_v_b] = vf.add_const(None)
    block.event_dict[d_v_c] = vf.add_const(None)

    psi_s_alpha: Var = vf.add_var(name=f"psi_s_alpha_{name}")
    psi_s_beta: Var = vf.add_var(name=f"psi_s_beta_{name}")
    psi_r_alpha: Var = vf.add_var(name=f"psi_r_alpha_{name}")
    psi_r_beta: Var = vf.add_var(name=f"psi_r_beta_{name}")
    omega_r: Var = vf.add_var(name=f"omega_r_{name}")

    d_psi_s_alpha: Var = vf.add_diff_var(name=f"d_psi_s_alpha_{name}", base_var=psi_s_alpha)
    d_psi_s_beta: Var = vf.add_diff_var(name=f"d_psi_s_beta_{name}", base_var=psi_s_beta)
    d_psi_r_alpha: Var = vf.add_diff_var(name=f"d_psi_r_alpha_{name}", base_var=psi_r_alpha)
    d_psi_r_beta: Var = vf.add_diff_var(name=f"d_psi_r_beta_{name}", base_var=psi_r_beta)
    d_omega_r: Var = vf.add_diff_var(name=f"d_omega_r_{name}", base_var=omega_r)

    i_s_alpha: Var = vf.add_var(name=f"i_s_alpha_{name}")
    i_s_beta: Var = vf.add_var(name=f"i_s_beta_{name}")
    i_r_alpha: Var = vf.add_var(name=f"i_r_alpha_{name}")
    i_r_beta: Var = vf.add_var(name=f"i_r_beta_{name}")
    i_a: Var = vf.add_var(name=f"i_A_{name}", reference=VarPowerFlowRefferenceType.i_A)
    i_b: Var = vf.add_var(name=f"i_B_{name}", reference=VarPowerFlowRefferenceType.i_B)
    i_c: Var = vf.add_var(name=f"i_C_{name}", reference=VarPowerFlowRefferenceType.i_C)
    p_motor: Var = vf.add_var(name=f"P_motor_{name}")
    q_motor: Var = vf.add_var(name=f"Q_motor_{name}")
    torque_e: Var = vf.add_var(name=f"T_e_{name}")
    torque_m: Var = vf.add_var(name=f"T_m_{name}")
    slip: Var = vf.add_var(name=f"slip_{name}")
    v_alpha: Var = vf.add_var(name=f"v_alpha_{name}")
    v_beta: Var = vf.add_var(name=f"v_beta_{name}")

    c_eps: Expr = vf.add_const(1e-9)
    c_speed_eps: Expr = params["speed_eps"]
    c_one: Expr = vf.add_const(1.0)
    c_two: Expr = vf.add_const(2.0)
    c_three_halves: Expr = vf.add_const(1.5)

    l_s: Expr = (params["x_ls"] + params["x_m"]) / (params["omega_base"] + c_eps)
    l_r: Expr = (x_lr + params["x_m"]) / (params["omega_base"] + c_eps)
    l_m: Expr = params["x_m"] / (params["omega_base"] + c_eps)
    det_lr: Expr = l_s * l_r - l_m * l_m + c_eps
    omega_r_e: Expr = params["omega_base"] * omega_r
    omega_speed_safe: Expr = sym.max(sym.abs(omega_r), c_speed_eps)
    torque_speed_term: Expr = omega_r * omega_speed_safe

    v_alpha_expr, v_beta_expr = _abc_to_alpha_beta(v_a, v_b, v_c)
    i_a_motor_expr, i_b_motor_expr, i_c_motor_expr = _alpha_beta_to_abc(i_s_alpha, i_s_beta)

    block.state_vars = [psi_s_alpha, psi_s_beta, psi_r_alpha, psi_r_beta, omega_r]
    block.diff_vars = [d_psi_s_alpha, d_psi_s_beta, d_psi_r_alpha, d_psi_r_beta, d_omega_r]
    block.state_eqs = [
        v_alpha - params["r_s"] * i_s_alpha,
        v_beta - params["r_s"] * i_s_beta,
        -r_r * i_r_alpha - omega_r_e * psi_r_beta,
        -r_r * i_r_beta + omega_r_e * psi_r_alpha,
        (torque_e - torque_m - params["d"] * (omega_r - c_one)) / (c_two * params["h"] + c_eps),
    ]
    block.algebraic_vars = [
        i_s_alpha,
        i_s_beta,
        i_r_alpha,
        i_r_beta,
        i_a,
        i_b,
        i_c,
        p_motor,
        q_motor,
        torque_e,
        torque_m,
        slip,
        v_alpha,
        v_beta,
    ]
    block.algebraic_eqs = [
        i_s_alpha - (l_r * psi_s_alpha - l_m * psi_r_alpha) / det_lr,
        i_s_beta - (l_r * psi_s_beta - l_m * psi_r_beta) / det_lr,
        i_r_alpha - (-l_m * psi_s_alpha + l_s * psi_r_alpha) / det_lr,
        i_r_beta - (-l_m * psi_s_beta + l_s * psi_r_beta) / det_lr,
        i_a + i_a_motor_expr,
        i_b + i_b_motor_expr,
        i_c + i_c_motor_expr,
        p_motor - c_three_halves * (v_alpha * i_s_alpha + v_beta * i_s_beta),
        q_motor - c_three_halves * (v_beta * i_s_alpha - v_alpha * i_s_beta),
        torque_e - c_three_halves * params["omega_base"] * (psi_s_alpha * i_s_beta - psi_s_beta * i_s_alpha),
        torque_m - params["t_load_nom"] * torque_speed_term,
        slip - (c_one - omega_r),
        v_alpha - v_alpha_expr,
        v_beta - v_beta_expr,
    ]

    _set_common_block_metadata(
        templ=templ,
        name=name,
        v_a=v_a,
        v_b=v_b,
        v_c=v_c,
        i_a=i_a,
        i_b=i_b,
        i_c=i_c,
        d_v_a=d_v_a,
        d_v_b=d_v_b,
        d_v_c=d_v_c,
        params=params,
    )

    v_a_peak: Expr = _phase_peak_phasor(v_a, d_v_a, params["omega_base"], c_eps)
    v_b_peak: Expr = _phase_peak_phasor(v_b, d_v_b, params["omega_base"], c_eps)
    v_c_peak: Expr = _phase_peak_phasor(v_c, d_v_c, params["omega_base"], c_eps)

    s_a: Expr = params["p0_a"] + sym.Const(complex(0.0, 1.0)) * params["q0_a"]
    s_b: Expr = params["p0_b"] + sym.Const(complex(0.0, 1.0)) * params["q0_b"]
    s_c: Expr = params["p0_c"] + sym.Const(complex(0.0, 1.0)) * params["q0_c"]
    i_a_peak: Expr = c_two * sym.conj(s_a / (v_a_peak + sym.Const(complex(1e-9, 0.0))))
    i_b_peak: Expr = c_two * sym.conj(s_b / (v_b_peak + sym.Const(complex(1e-9, 0.0))))
    i_c_peak: Expr = c_two * sym.conj(s_c / (v_c_peak + sym.Const(complex(1e-9, 0.0))))

    v_pos: Expr = _space_vector_positive_sequence(v_a_peak, v_b_peak, v_c_peak)
    i_pos: Expr = _space_vector_positive_sequence(i_a_peak, i_b_peak, i_c_peak)
    z_s: Expr = params["r_s"] + sym.Const(complex(0.0, 1.0)) * params["x_ls"]
    z_m: Expr = sym.Const(complex(0.0, 1.0)) * params["x_m"]
    v_airgap: Expr = v_pos - z_s * i_pos
    i_mag: Expr = v_airgap / (z_m + sym.Const(complex(1e-9, 0.0)))
    i_rotor_phase: Expr = i_pos - i_mag
    z_rotor_est: Expr = v_airgap / (i_rotor_phase + sym.Const(complex(1e-9, 0.0)))
    slip_from_pf: Expr = sym.hard_sat(
        r_r / sym.max(sym.real(z_rotor_est), r_r / params["slip_max"]),
        params["slip_min"],
        params["slip_max"],
    )
    omega_init: Expr = c_one - slip_from_pf

    i_r_a_peak: Expr = i_rotor_phase
    i_r_b_peak: Expr = sym.Const(_A_NEG) * i_rotor_phase
    i_r_c_peak: Expr = sym.Const(_A_POS) * i_rotor_phase
    i_s_alpha_peak, i_s_beta_peak = _abc_to_alpha_beta(i_a_peak, i_b_peak, i_c_peak)
    i_r_alpha_peak, i_r_beta_peak = _abc_to_alpha_beta(i_r_a_peak, i_r_b_peak, i_r_c_peak)
    rotor_flux_den: Expr = c_one + sym.Const(complex(0.0, 1.0)) * slip_from_pf * (x_lr + params["x_m"]) / (r_r + c_eps)
    psi_r_alpha_peak: Expr = l_m * i_s_alpha_peak / rotor_flux_den
    psi_r_beta_peak: Expr = l_m * i_s_beta_peak / rotor_flux_den
    i_r_alpha_peak = -sym.Const(complex(0.0, 1.0)) * params["omega_base"] * slip_from_pf * psi_r_alpha_peak / (r_r + c_eps)
    i_r_beta_peak = -sym.Const(complex(0.0, 1.0)) * params["omega_base"] * slip_from_pf * psi_r_beta_peak / (r_r + c_eps)
    psi_s_alpha_peak: Expr = l_s * i_s_alpha_peak + l_m * i_r_alpha_peak
    psi_s_beta_peak: Expr = l_s * i_s_beta_peak + l_m * i_r_beta_peak

    block.init_eqs = dict({
        v_alpha: v_alpha_expr,
        v_beta: v_beta_expr,
        i_s_alpha: sym.imag(i_s_alpha_peak),
        i_s_beta: sym.imag(i_s_beta_peak),
        i_r_alpha: sym.imag(i_r_alpha_peak),
        i_r_beta: sym.imag(i_r_beta_peak),
        i_a: -sym.imag(i_a_peak),
        i_b: -sym.imag(i_b_peak),
        i_c: -sym.imag(i_c_peak),
        psi_s_alpha: sym.imag(psi_s_alpha_peak),
        psi_s_beta: sym.imag(psi_s_beta_peak),
        psi_r_alpha: sym.imag(psi_r_alpha_peak),
        psi_r_beta: sym.imag(psi_r_beta_peak),
        omega_r: omega_init,
        slip: c_one - omega_r,
        p_motor: params["p0_a"] + params["p0_b"] + params["p0_c"],
        q_motor: params["q0_a"] + params["q0_b"] + params["q0_c"],
        torque_e: c_three_halves * params["omega_base"] * (psi_s_alpha * i_s_beta - psi_s_beta * i_s_alpha),
        params["t_load_nom"]: torque_e / sym.max(omega_r * sym.abs(omega_r), c_speed_eps * c_speed_eps),
        torque_m: params["t_load_nom"] * torque_speed_term,
    })
    block.diff_init_eqs = dict({
        d_psi_s_alpha: v_alpha - params["r_s"] * i_s_alpha,
        d_psi_s_beta: v_beta - params["r_s"] * i_s_beta,
        d_psi_r_alpha: -r_r * i_r_alpha - omega_r_e * psi_r_beta,
        d_psi_r_beta: -r_r * i_r_beta + omega_r_e * psi_r_alpha,
        d_omega_r: (torque_e - torque_m - params["d"] * (omega_r - c_one)) / (c_two * params["h"] + c_eps),
    })
    return templ


def get_induction_motor_double_cage_emt_template(
    vf: VarFactory,
    name: str = "induction_motor_double_cage_emt_template",
) -> EmtModelTemplate:
    """Build the Level-3 EMT double-cage induction-motor template.

    This model keeps the same ABC EMT terminal interface as the Level-2 block,
    but it splits the rotor current into two parallel cages that share one common
    magnetizing branch. The resulting model is better suited to capture high
    inrush current and deep-bar behaviour during startup.

    The initialization is intentionally conservative: it uses the power-flow
    target to seed the stator current and then distributes the rotor current
    between cages according to their impedances at the estimated slip.

    :param vf: EMT variable factory.
    :param name: Symbolic template name.
    :return: Configured EMT template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    block: Block = templ.block
    params: Dict[str, Var] = _build_common_events(vf=vf, block=block, name=name)
    r_r1: Var = vf.add_var(name=f"r_r1_{name}")
    x_lr1: Var = vf.add_var(name=f"x_lr1_{name}")
    r_r2: Var = vf.add_var(name=f"r_r2_{name}")
    x_lr2: Var = vf.add_var(name=f"x_lr2_{name}")
    block.event_dict[r_r1] = vf.add_const(0.025)
    block.event_dict[x_lr1] = vf.add_const(0.10)
    block.event_dict[r_r2] = vf.add_const(0.080)
    block.event_dict[x_lr2] = vf.add_const(0.35)

    v_a: Var = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_b: Var = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_c: Var = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)
    d_v_a: Var = vf.add_var(name=f"d_v_A_{name}")
    d_v_b: Var = vf.add_var(name=f"d_v_B_{name}")
    d_v_c: Var = vf.add_var(name=f"d_v_C_{name}")
    block.event_dict[d_v_a] = vf.add_const(None)
    block.event_dict[d_v_b] = vf.add_const(None)
    block.event_dict[d_v_c] = vf.add_const(None)

    psi_s_alpha: Var = vf.add_var(name=f"psi_s_alpha_{name}")
    psi_s_beta: Var = vf.add_var(name=f"psi_s_beta_{name}")
    psi_r1_alpha: Var = vf.add_var(name=f"psi_r1_alpha_{name}")
    psi_r1_beta: Var = vf.add_var(name=f"psi_r1_beta_{name}")
    psi_r2_alpha: Var = vf.add_var(name=f"psi_r2_alpha_{name}")
    psi_r2_beta: Var = vf.add_var(name=f"psi_r2_beta_{name}")
    omega_r: Var = vf.add_var(name=f"omega_r_{name}")

    d_psi_s_alpha: Var = vf.add_diff_var(name=f"d_psi_s_alpha_{name}", base_var=psi_s_alpha)
    d_psi_s_beta: Var = vf.add_diff_var(name=f"d_psi_s_beta_{name}", base_var=psi_s_beta)
    d_psi_r1_alpha: Var = vf.add_diff_var(name=f"d_psi_r1_alpha_{name}", base_var=psi_r1_alpha)
    d_psi_r1_beta: Var = vf.add_diff_var(name=f"d_psi_r1_beta_{name}", base_var=psi_r1_beta)
    d_psi_r2_alpha: Var = vf.add_diff_var(name=f"d_psi_r2_alpha_{name}", base_var=psi_r2_alpha)
    d_psi_r2_beta: Var = vf.add_diff_var(name=f"d_psi_r2_beta_{name}", base_var=psi_r2_beta)
    d_omega_r: Var = vf.add_diff_var(name=f"d_omega_r_{name}", base_var=omega_r)

    i_s_alpha: Var = vf.add_var(name=f"i_s_alpha_{name}")
    i_s_beta: Var = vf.add_var(name=f"i_s_beta_{name}")
    i_r1_alpha: Var = vf.add_var(name=f"i_r1_alpha_{name}")
    i_r1_beta: Var = vf.add_var(name=f"i_r1_beta_{name}")
    i_r2_alpha: Var = vf.add_var(name=f"i_r2_alpha_{name}")
    i_r2_beta: Var = vf.add_var(name=f"i_r2_beta_{name}")
    i_a: Var = vf.add_var(name=f"i_A_{name}", reference=VarPowerFlowRefferenceType.i_A)
    i_b: Var = vf.add_var(name=f"i_B_{name}", reference=VarPowerFlowRefferenceType.i_B)
    i_c: Var = vf.add_var(name=f"i_C_{name}", reference=VarPowerFlowRefferenceType.i_C)
    p_motor: Var = vf.add_var(name=f"P_motor_{name}")
    q_motor: Var = vf.add_var(name=f"Q_motor_{name}")
    torque_e: Var = vf.add_var(name=f"T_e_{name}")
    torque_m: Var = vf.add_var(name=f"T_m_{name}")
    slip: Var = vf.add_var(name=f"slip_{name}")
    v_alpha: Var = vf.add_var(name=f"v_alpha_{name}")
    v_beta: Var = vf.add_var(name=f"v_beta_{name}")

    c_eps: Expr = vf.add_const(1e-9)
    c_one: Expr = vf.add_const(1.0)
    c_two: Expr = vf.add_const(2.0)
    c_three_halves: Expr = vf.add_const(1.5)
    c_speed_eps: Expr = params["speed_eps"]

    l_ls: Expr = params["x_ls"] / (params["omega_base"] + c_eps)
    l_lr1: Expr = x_lr1 / (params["omega_base"] + c_eps)
    l_lr2: Expr = x_lr2 / (params["omega_base"] + c_eps)
    l_m: Expr = params["x_m"] / (params["omega_base"] + c_eps)
    omega_r_e: Expr = params["omega_base"] * omega_r
    torque_speed_term: Expr = omega_r * sym.max(sym.abs(omega_r), c_speed_eps)

    # The three-branch inductance matrix is identical on alpha and beta axes, so
    # one explicit symbolic inverse keeps the implementation compact and readable.
    den_matrix: Expr = (
        l_ls * l_lr1 * l_lr2
        + l_m * l_lr1 * l_lr2
        + l_m * l_ls * l_lr2
        + l_m * l_ls * l_lr1
        + c_eps
    )
    i_a_motor_expr, i_b_motor_expr, i_c_motor_expr = _alpha_beta_to_abc(i_s_alpha, i_s_beta)
    v_alpha_expr, v_beta_expr = _abc_to_alpha_beta(v_a, v_b, v_c)

    block.state_vars = [psi_s_alpha, psi_s_beta, psi_r1_alpha, psi_r1_beta, psi_r2_alpha, psi_r2_beta, omega_r]
    block.diff_vars = [d_psi_s_alpha, d_psi_s_beta, d_psi_r1_alpha, d_psi_r1_beta, d_psi_r2_alpha, d_psi_r2_beta, d_omega_r]
    block.state_eqs = [
        v_alpha - params["r_s"] * i_s_alpha,
        v_beta - params["r_s"] * i_s_beta,
        -r_r1 * i_r1_alpha + omega_r_e * psi_r1_beta,
        -r_r1 * i_r1_beta - omega_r_e * psi_r1_alpha,
        -r_r2 * i_r2_alpha + omega_r_e * psi_r2_beta,
        -r_r2 * i_r2_beta - omega_r_e * psi_r2_alpha,
        (torque_e - torque_m - params["d"] * (omega_r - c_one)) / (c_two * params["h"] + c_eps),
    ]
    block.algebraic_vars = [
        i_s_alpha,
        i_s_beta,
        i_r1_alpha,
        i_r1_beta,
        i_r2_alpha,
        i_r2_beta,
        i_a,
        i_b,
        i_c,
        p_motor,
        q_motor,
        torque_e,
        torque_m,
        slip,
        v_alpha,
        v_beta,
    ]
    block.algebraic_eqs = [
        i_s_alpha - (
            (l_lr1 * l_lr2 + l_m * l_lr1 + l_m * l_lr2) * psi_s_alpha
            - l_m * l_lr2 * psi_r1_alpha
            - l_m * l_lr1 * psi_r2_alpha
        ) / den_matrix,
        i_s_beta - (
            (l_lr1 * l_lr2 + l_m * l_lr1 + l_m * l_lr2) * psi_s_beta
            - l_m * l_lr2 * psi_r1_beta
            - l_m * l_lr1 * psi_r2_beta
        ) / den_matrix,
        i_r1_alpha - (
            -l_m * l_lr2 * psi_s_alpha
            + (l_ls * l_lr2 + l_m * l_ls + l_m * l_lr2) * psi_r1_alpha
            - l_m * l_ls * psi_r2_alpha
        ) / den_matrix,
        i_r1_beta - (
            -l_m * l_lr2 * psi_s_beta
            + (l_ls * l_lr2 + l_m * l_ls + l_m * l_lr2) * psi_r1_beta
            - l_m * l_ls * psi_r2_beta
        ) / den_matrix,
        i_r2_alpha - (
            -l_m * l_lr1 * psi_s_alpha
            - l_m * l_ls * psi_r1_alpha
            + (l_ls * l_lr1 + l_m * l_ls + l_m * l_lr1) * psi_r2_alpha
        ) / den_matrix,
        i_r2_beta - (
            -l_m * l_lr1 * psi_s_beta
            - l_m * l_ls * psi_r1_beta
            + (l_ls * l_lr1 + l_m * l_ls + l_m * l_lr1) * psi_r2_beta
        ) / den_matrix,
        i_a + i_a_motor_expr,
        i_b + i_b_motor_expr,
        i_c + i_c_motor_expr,
        p_motor - c_three_halves * (v_alpha * i_s_alpha + v_beta * i_s_beta),
        q_motor - c_three_halves * (v_beta * i_s_alpha - v_alpha * i_s_beta),
        torque_e - c_three_halves * params["omega_base"] * (psi_s_alpha * i_s_beta - psi_s_beta * i_s_alpha),
        torque_m - params["t_load_nom"] * torque_speed_term,
        slip - (c_one - omega_r),
        v_alpha - v_alpha_expr,
        v_beta - v_beta_expr,
    ]

    _set_common_block_metadata(
        templ=templ,
        name=name,
        v_a=v_a,
        v_b=v_b,
        v_c=v_c,
        i_a=i_a,
        i_b=i_b,
        i_c=i_c,
        d_v_a=d_v_a,
        d_v_b=d_v_b,
        d_v_c=d_v_c,
        params=params,
    )

    # The double-cage initializer prioritizes robustness over a perfect P/Q match.
    # It first estimates slip from one aggregated equivalent branch and then
    # distributes the air-gap current between both cages using that slip estimate.
    v_a_peak: Expr = _phase_peak_phasor(v_a, d_v_a, params["omega_base"], c_eps)
    v_b_peak: Expr = _phase_peak_phasor(v_b, d_v_b, params["omega_base"], c_eps)
    v_c_peak: Expr = _phase_peak_phasor(v_c, d_v_c, params["omega_base"], c_eps)
    s_a: Expr = params["p0_a"] + sym.Const(complex(0.0, 1.0)) * params["q0_a"]
    s_b: Expr = params["p0_b"] + sym.Const(complex(0.0, 1.0)) * params["q0_b"]
    s_c: Expr = params["p0_c"] + sym.Const(complex(0.0, 1.0)) * params["q0_c"]
    i_a_peak: Expr = c_two * sym.conj(s_a / (v_a_peak + sym.Const(complex(1e-9, 0.0))))
    i_b_peak: Expr = c_two * sym.conj(s_b / (v_b_peak + sym.Const(complex(1e-9, 0.0))))
    i_c_peak: Expr = c_two * sym.conj(s_c / (v_c_peak + sym.Const(complex(1e-9, 0.0))))
    i_pos: Expr = _space_vector_positive_sequence(i_a_peak, i_b_peak, i_c_peak)
    v_pos: Expr = _space_vector_positive_sequence(v_a_peak, v_b_peak, v_c_peak)
    z_s: Expr = params["r_s"] + sym.Const(complex(0.0, 1.0)) * params["x_ls"]
    y_m: Expr = sym.Const(1.0) / (sym.Const(complex(0.0, 1.0)) * params["x_m"] + sym.Const(complex(1e-9, 0.0)))
    v_airgap: Expr = v_pos - z_s * i_pos
    y_rot_total: Expr = i_pos / (v_airgap + sym.Const(complex(1e-9, 0.0))) - y_m
    z_rot_total: Expr = sym.Const(1.0) / (y_rot_total + sym.Const(complex(1e-9, 0.0)))
    slip_est: Expr = sym.hard_sat(
        r_r1 / sym.max(sym.real(z_rot_total), r_r1 / params["slip_max"]),
        params["slip_min"],
        params["slip_max"],
    )
    z_r1: Expr = r_r1 / slip_est + sym.Const(complex(0.0, 1.0)) * x_lr1
    z_r2: Expr = r_r2 / slip_est + sym.Const(complex(0.0, 1.0)) * x_lr2
    i_r1_phase: Expr = v_airgap / (z_r1 + sym.Const(complex(1e-9, 0.0)))
    i_r2_phase: Expr = v_airgap / (z_r2 + sym.Const(complex(1e-9, 0.0)))
    i_r1_alpha_peak, i_r1_beta_peak = _abc_to_alpha_beta(i_r1_phase, sym.Const(_A_NEG) * i_r1_phase, sym.Const(_A_POS) * i_r1_phase)
    i_r2_alpha_peak, i_r2_beta_peak = _abc_to_alpha_beta(i_r2_phase, sym.Const(_A_NEG) * i_r2_phase, sym.Const(_A_POS) * i_r2_phase)
    i_s_alpha_peak, i_s_beta_peak = _abc_to_alpha_beta(i_a_peak, i_b_peak, i_c_peak)
    psi_s_alpha_peak: Expr = l_ls * i_s_alpha_peak + l_m * (i_s_alpha_peak + i_r1_alpha_peak + i_r2_alpha_peak)
    psi_s_beta_peak: Expr = l_ls * i_s_beta_peak + l_m * (i_s_beta_peak + i_r1_beta_peak + i_r2_beta_peak)
    psi_r1_alpha_peak: Expr = l_lr1 * i_r1_alpha_peak + l_m * (i_s_alpha_peak + i_r1_alpha_peak + i_r2_alpha_peak)
    psi_r1_beta_peak: Expr = l_lr1 * i_r1_beta_peak + l_m * (i_s_beta_peak + i_r1_beta_peak + i_r2_beta_peak)
    psi_r2_alpha_peak: Expr = l_lr2 * i_r2_alpha_peak + l_m * (i_s_alpha_peak + i_r1_alpha_peak + i_r2_alpha_peak)
    psi_r2_beta_peak: Expr = l_lr2 * i_r2_beta_peak + l_m * (i_s_beta_peak + i_r1_beta_peak + i_r2_beta_peak)

    block.init_eqs = dict({
        v_alpha: v_alpha_expr,
        v_beta: v_beta_expr,
        i_s_alpha: sym.imag(i_s_alpha_peak),
        i_s_beta: sym.imag(i_s_beta_peak),
        i_r1_alpha: sym.imag(i_r1_alpha_peak),
        i_r1_beta: sym.imag(i_r1_beta_peak),
        i_r2_alpha: sym.imag(i_r2_alpha_peak),
        i_r2_beta: sym.imag(i_r2_beta_peak),
        i_a: -sym.imag(i_a_peak),
        i_b: -sym.imag(i_b_peak),
        i_c: -sym.imag(i_c_peak),
        psi_s_alpha: sym.imag(psi_s_alpha_peak),
        psi_s_beta: sym.imag(psi_s_beta_peak),
        psi_r1_alpha: sym.imag(psi_r1_alpha_peak),
        psi_r1_beta: sym.imag(psi_r1_beta_peak),
        psi_r2_alpha: sym.imag(psi_r2_alpha_peak),
        psi_r2_beta: sym.imag(psi_r2_beta_peak),
        omega_r: c_one - slip_est,
        slip: c_one - omega_r,
        p_motor: params["p0_a"] + params["p0_b"] + params["p0_c"],
        q_motor: params["q0_a"] + params["q0_b"] + params["q0_c"],
        torque_e: c_three_halves * params["omega_base"] * (psi_s_alpha * i_s_beta - psi_s_beta * i_s_alpha),
        params["t_load_nom"]: torque_e / sym.max(omega_r * sym.abs(omega_r), c_speed_eps * c_speed_eps),
        torque_m: params["t_load_nom"] * torque_speed_term,
    })
    block.diff_init_eqs = dict({
        d_psi_s_alpha: v_alpha - params["r_s"] * i_s_alpha,
        d_psi_s_beta: v_beta - params["r_s"] * i_s_beta,
        d_psi_r1_alpha: -r_r1 * i_r1_alpha + omega_r_e * psi_r1_beta,
        d_psi_r1_beta: -r_r1 * i_r1_beta - omega_r_e * psi_r1_alpha,
        d_psi_r2_alpha: -r_r2 * i_r2_alpha + omega_r_e * psi_r2_beta,
        d_psi_r2_beta: -r_r2 * i_r2_beta - omega_r_e * psi_r2_alpha,
        d_omega_r: (torque_e - torque_m - params["d"] * (omega_r - c_one)) / (c_two * params["h"] + c_eps),
    })
    return templ


def get_induction_motor_rms_equivalent_emt_template(
    vf: VarFactory,
    name: str = "induction_motor_rms_equivalent_emt_template",
) -> EmtModelTemplate:
    """Build the Level-1 RMS-equivalent ``dq`` induction-motor EMT template.

    This level is intentionally simplified and exists only as a conceptual bridge
    from the existing RMS motor model to the EMT framework. It uses a synchronous
    ``dq`` formulation driven from ABC EMT voltages, but it is not the preferred
    EMT representation because it filters out part of the electromagnetic detail
    that the stationary-frame single-cage model captures naturally.

    :param vf: EMT variable factory.
    :param name: Symbolic template name.
    :return: Configured EMT template.
    """
    # Reuse the recommended electrical parameter set, but keep a distinct builder
    # and symbolic namespace so the simplified dq model stays clearly separated.
    templ: EmtModelTemplate = EmtModelTemplate()
    block: Block = templ.block
    params: Dict[str, Var] = _build_common_events(vf=vf, block=block, name=name)
    r_r: Var = vf.add_var(name=f"r_r_{name}")
    x_lr: Var = vf.add_var(name=f"x_lr_{name}")
    block.event_dict[r_r] = vf.add_const(0.02)
    block.event_dict[x_lr] = vf.add_const(0.12)

    v_a: Var = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_b: Var = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_c: Var = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)
    d_v_a: Var = vf.add_var(name=f"d_v_A_{name}")
    d_v_b: Var = vf.add_var(name=f"d_v_B_{name}")
    d_v_c: Var = vf.add_var(name=f"d_v_C_{name}")
    block.event_dict[d_v_a] = vf.add_const(None)
    block.event_dict[d_v_b] = vf.add_const(None)
    block.event_dict[d_v_c] = vf.add_const(None)

    theta_syn: Var = vf.add_var(name=f"theta_syn_{name}")
    psi_sd: Var = vf.add_var(name=f"psi_sd_{name}")
    psi_sq: Var = vf.add_var(name=f"psi_sq_{name}")
    psi_rd: Var = vf.add_var(name=f"psi_rd_{name}")
    psi_rq: Var = vf.add_var(name=f"psi_rq_{name}")
    omega_r: Var = vf.add_var(name=f"omega_r_{name}")

    d_theta_syn: Var = vf.add_diff_var(name=f"d_theta_syn_{name}", base_var=theta_syn)
    d_psi_sd: Var = vf.add_diff_var(name=f"d_psi_sd_{name}", base_var=psi_sd)
    d_psi_sq: Var = vf.add_diff_var(name=f"d_psi_sq_{name}", base_var=psi_sq)
    d_psi_rd: Var = vf.add_diff_var(name=f"d_psi_rd_{name}", base_var=psi_rd)
    d_psi_rq: Var = vf.add_diff_var(name=f"d_psi_rq_{name}", base_var=psi_rq)
    d_omega_r: Var = vf.add_diff_var(name=f"d_omega_r_{name}", base_var=omega_r)

    i_sd: Var = vf.add_var(name=f"i_sd_{name}")
    i_sq: Var = vf.add_var(name=f"i_sq_{name}")
    i_rd: Var = vf.add_var(name=f"i_rd_{name}")
    i_rq: Var = vf.add_var(name=f"i_rq_{name}")
    v_d: Var = vf.add_var(name=f"v_d_{name}")
    v_q: Var = vf.add_var(name=f"v_q_{name}")
    i_a: Var = vf.add_var(name=f"i_A_{name}", reference=VarPowerFlowRefferenceType.i_A)
    i_b: Var = vf.add_var(name=f"i_B_{name}", reference=VarPowerFlowRefferenceType.i_B)
    i_c: Var = vf.add_var(name=f"i_C_{name}", reference=VarPowerFlowRefferenceType.i_C)
    p_motor: Var = vf.add_var(name=f"P_motor_{name}")
    q_motor: Var = vf.add_var(name=f"Q_motor_{name}")
    torque_e: Var = vf.add_var(name=f"T_e_{name}")
    torque_m: Var = vf.add_var(name=f"T_m_{name}")
    slip: Var = vf.add_var(name=f"slip_{name}")

    c_eps: Expr = vf.add_const(1e-9)
    c_one: Expr = vf.add_const(1.0)
    c_two: Expr = vf.add_const(2.0)
    c_three_halves: Expr = vf.add_const(1.5)
    c_speed_eps: Expr = params["speed_eps"]
    l_s: Expr = (params["x_ls"] + params["x_m"]) / (params["omega_base"] + c_eps)
    l_r: Expr = (x_lr + params["x_m"]) / (params["omega_base"] + c_eps)
    l_m: Expr = params["x_m"] / (params["omega_base"] + c_eps)
    det_lr: Expr = l_s * l_r - l_m * l_m + c_eps
    omega_slip: Expr = params["omega_base"] * (c_one - omega_r)
    sin_t: Expr = sym.sin(theta_syn)
    cos_t: Expr = sym.cos(theta_syn)

    v_alpha_expr, v_beta_expr = _abc_to_alpha_beta(v_a, v_b, v_c)
    i_alpha_expr: Expr = cos_t * i_sd - sin_t * i_sq
    i_beta_expr: Expr = sin_t * i_sd + cos_t * i_sq
    i_a_motor_expr, i_b_motor_expr, i_c_motor_expr = _alpha_beta_to_abc(i_alpha_expr, i_beta_expr)
    v_d_expr: Expr = cos_t * v_alpha_expr + sin_t * v_beta_expr
    v_q_expr: Expr = -sin_t * v_alpha_expr + cos_t * v_beta_expr
    torque_speed_term: Expr = omega_r * sym.max(sym.abs(omega_r), c_speed_eps)

    block.state_vars = [theta_syn, psi_sd, psi_sq, psi_rd, psi_rq, omega_r]
    block.diff_vars = [d_theta_syn, d_psi_sd, d_psi_sq, d_psi_rd, d_psi_rq, d_omega_r]
    block.state_eqs = [
        params["omega_base"],
        v_d + params["omega_base"] * psi_sq - params["r_s"] * i_sd,
        v_q - params["omega_base"] * psi_sd - params["r_s"] * i_sq,
        -r_r * i_rd + omega_slip * psi_rq,
        -r_r * i_rq - omega_slip * psi_rd,
        (torque_e - torque_m - params["d"] * (omega_r - c_one)) / (c_two * params["h"] + c_eps),
    ]
    block.algebraic_vars = [i_sd, i_sq, i_rd, i_rq, v_d, v_q, i_a, i_b, i_c, p_motor, q_motor, torque_e, torque_m, slip]
    block.algebraic_eqs = [
        i_sd - (l_r * psi_sd - l_m * psi_rd) / det_lr,
        i_sq - (l_r * psi_sq - l_m * psi_rq) / det_lr,
        i_rd - (-l_m * psi_sd + l_s * psi_rd) / det_lr,
        i_rq - (-l_m * psi_sq + l_s * psi_rq) / det_lr,
        v_d - v_d_expr,
        v_q - v_q_expr,
        i_a + i_a_motor_expr,
        i_b + i_b_motor_expr,
        i_c + i_c_motor_expr,
        p_motor - c_three_halves * (v_d * i_sd + v_q * i_sq),
        q_motor - c_three_halves * (v_q * i_sd - v_d * i_sq),
        torque_e - c_three_halves * params["omega_base"] * (psi_sd * i_sq - psi_sq * i_sd),
        torque_m - params["t_load_nom"] * torque_speed_term,
        slip - (c_one - omega_r),
    ]

    _set_common_block_metadata(
        templ=templ,
        name=name,
        v_a=v_a,
        v_b=v_b,
        v_c=v_c,
        i_a=i_a,
        i_b=i_b,
        i_c=i_c,
        d_v_a=d_v_a,
        d_v_b=d_v_b,
        d_v_c=d_v_c,
        params=params,
    )

    v_a_peak: Expr = _phase_peak_phasor(v_a, d_v_a, params["omega_base"], c_eps)
    i_a_peak: Expr = c_two * sym.conj(
        (params["p0_a"] + sym.Const(complex(0.0, 1.0)) * params["q0_a"]) / (v_a_peak + sym.Const(complex(1e-9, 0.0)))
    )
    z_s: Expr = params["r_s"] + sym.Const(complex(0.0, 1.0)) * params["x_ls"]
    z_m: Expr = sym.Const(complex(0.0, 1.0)) * params["x_m"]
    v_airgap: Expr = v_a_peak - z_s * i_a_peak
    i_rotor_peak: Expr = i_a_peak - v_airgap / (z_m + sym.Const(complex(1e-9, 0.0)))
    z_rotor_est: Expr = v_airgap / (i_rotor_peak + sym.Const(complex(1e-9, 0.0)))
    slip_est: Expr = sym.hard_sat(
        r_r / sym.max(sym.real(z_rotor_est), r_r / params["slip_max"]),
        params["slip_min"],
        params["slip_max"],
    )
    theta_init: Expr = sym.angle(v_a_peak)
    i_alpha_peak: Expr = sym.Const(2.0 / 3.0) * (i_a_peak - sym.Const(0.5) * sym.Const(_A_NEG) * i_a_peak - sym.Const(0.5) * sym.Const(_A_POS) * i_a_peak)
    i_beta_peak: Expr = sym.Const(1.0 / _SQRT3) * (sym.Const(_A_NEG) * i_a_peak - sym.Const(_A_POS) * i_a_peak)
    i_d_peak: Expr = sym.cos(theta_init) * i_alpha_peak + sym.sin(theta_init) * i_beta_peak
    i_q_peak: Expr = -sym.sin(theta_init) * i_alpha_peak + sym.cos(theta_init) * i_beta_peak
    i_rd_peak: Expr = i_d_peak - v_airgap / (z_m + sym.Const(complex(1e-9, 0.0)))
    i_rq_peak: Expr = i_q_peak
    psi_sd_peak: Expr = l_s * i_d_peak + l_m * i_rd_peak
    psi_sq_peak: Expr = l_s * i_q_peak + l_m * i_rq_peak
    psi_rd_peak: Expr = l_m * i_d_peak + l_r * i_rd_peak
    psi_rq_peak: Expr = l_m * i_q_peak + l_r * i_rq_peak

    block.init_eqs = dict({
        theta_syn: theta_init,
        v_d: v_d_expr,
        v_q: v_q_expr,
        i_sd: sym.imag(i_d_peak),
        i_sq: sym.imag(i_q_peak),
        i_rd: sym.imag(i_rd_peak),
        i_rq: sym.imag(i_rq_peak),
        i_a: -sym.imag(i_a_peak),
        i_b: -sym.imag(sym.Const(_A_NEG) * i_a_peak),
        i_c: -sym.imag(sym.Const(_A_POS) * i_a_peak),
        psi_sd: sym.imag(psi_sd_peak),
        psi_sq: sym.imag(psi_sq_peak),
        psi_rd: sym.imag(psi_rd_peak),
        psi_rq: sym.imag(psi_rq_peak),
        omega_r: c_one - slip_est,
        slip: c_one - omega_r,
        p_motor: params["p0_a"] + params["p0_b"] + params["p0_c"],
        q_motor: params["q0_a"] + params["q0_b"] + params["q0_c"],
        torque_e: c_three_halves * params["omega_base"] * (psi_sd * i_sq - psi_sq * i_sd),
        params["t_load_nom"]: torque_e / sym.max(omega_r * sym.abs(omega_r), c_speed_eps * c_speed_eps),
        torque_m: params["t_load_nom"] * torque_speed_term,
    })
    block.diff_init_eqs = dict({
        d_theta_syn: params["omega_base"],
        d_psi_sd: v_d + params["omega_base"] * psi_sq - params["r_s"] * i_sd,
        d_psi_sq: v_q - params["omega_base"] * psi_sd - params["r_s"] * i_sq,
        d_psi_rd: -r_r * i_rd + omega_slip * psi_rq,
        d_psi_rq: -r_r * i_rq - omega_slip * psi_rd,
        d_omega_r: (torque_e - torque_m - params["d"] * (omega_r - c_one)) / (c_two * params["h"] + c_eps),
    })
    return templ


def get_induction_motor_emt_template(
    vf: VarFactory,
    level: int = 2,
    name: str = "induction_motor_emt_template",
) -> EmtModelTemplate:
    """Build one induction-motor EMT template for the requested fidelity level.

    Level selection:

    * ``1``: RMS-equivalent ``dq`` EMT bridge model.
    * ``2``: Recommended EMT single-cage model.
    * ``3``: EMT double-cage model.

    :param vf: EMT variable factory.
    :param level: Requested model level.
    :param name: Symbolic template name.
    :return: Configured EMT template.
    :raises ValueError: If the requested level is not supported.
    """
    if level == 1:
        return get_induction_motor_rms_equivalent_emt_template(vf=vf, name=name)
    if level == 2:
        return get_induction_motor_single_cage_emt_template(vf=vf, name=name)
    if level == 3:
        return get_induction_motor_double_cage_emt_template(vf=vf, name=name)
    raise ValueError(f"Unsupported induction motor EMT level '{level}'")
