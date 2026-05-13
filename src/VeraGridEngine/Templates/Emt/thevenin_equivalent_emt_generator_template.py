# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from typing import List, Any
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DeviceType, ParamPowerFlowRefferenceType
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_pf_positive_sequence_init_refs

def get_generator_thevenin_rl_emt_template(vf: VarFactory,
                                           name: str = "emt_thevenin_eq_generator_template"
                                           ) -> EmtModelTemplate:
    """
    Return the unified ref-capable EMT Thevenin generator template.

    The codebase now keeps a single Thevenin implementation. Legacy callers that
    still import the old helper name are routed to the ref-capable variant so the
    EMT builder always sees the same external/API mapping contract.

    :param vf: EMT variable factory.
    :param name: Model name.
    :return: Configured EMT template.
    """
    return get_generator_thevenin_rl_emt_template_with_ref(vf=vf, name=name)

def get_generator_thevenin_rl_emt_template_with_ref(
        vf: VarFactory,
        name: str = "emt_thevenin_eq_generator_template",
) -> EmtModelTemplate:
    """
    Build a three-phase EMT Thevenin generator with optional slow sharing control.

    The model is still a balanced internal sinusoidal source behind a series
    ``R-X`` branch. The sharing extension is intentionally lightweight and does
    not try to emulate a full synchronous-machine + AVR + governor model.

    The key design decision is the following:

    * The absolute electrical angle ``theta`` keeps the nominal synchronous speed.
    * Active-power sharing acts on a bounded internal angle offset
      ``delta_share`` instead of acting directly on ``dtheta/dt``.
    * Reactive-power sharing acts on the internal emf scaling ``E_scale`` and
      includes a restoring term towards ``1.0``.

    This avoids the unbounded phase drift that appears when the active-power
    controller directly biases the absolute electrical speed.

    Inputs
    ------
    ``v_A``, ``v_B``, ``v_C``:
        Instantaneous bus terminal voltages in pu.

    States
    ------
    ``i_A``, ``i_B``, ``i_C``:
        Phase currents injected into the bus in pu.

    ``theta``:
        Absolute electrical angle of the internal balanced source in rad.

    ``delta_share``:
        Slow internal angle offset used only for active-power sharing.

    ``E_ctrl_scale``:
        Slow internal scaling factor used by the reactive-power sharing loop.

    ``xi_share_p``, ``xi_share_q``:
        Integral states of the active/reactive sharing controllers.

    Parameters
    ----------
    Static generator parameters:
        ``omega_base``, ``R_s``, ``X_s``

    PF-derived initialization parameters:
        ``phi_v``, ``phi``, ``Vpk``, ``Ipk``

    Optional sharing references:
        ``share_enable``, ``P_share_ref``, ``Q_share_ref``

    Event parameters:
        ``kp_share_p``, ``ki_share_p``, ``kp_share_q``, ``ki_share_q``,
        ``k_delta_share``, ``k_e_scale``, ``E_scale``

    Initialization
    --------------
    The PF initialization reconstructs the positive-sequence internal emf using:

    .. math::

        E = V + (R + jX) I

    and then initializes:

    * ``theta = phi_v + delta``
    * ``delta_share = 0``
    * ``E_ctrl_scale = 1``
    * ``xi_share_p = 0``
    * ``xi_share_q = 0``

    so that the sharing controller starts exactly from the open-loop PF point.

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :return: Configured EMT template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    # ------------------------------------------------------------------
    # Constants used in symbolic expressions.
    # ------------------------------------------------------------------
    c05 = vf.add_const(0.5)
    c_eps_emf = vf.add_const(1.0e-24)
    c0 = vf.add_const(0.0)
    c1 = vf.add_const(1.0)

    # ------------------------------------------------------------------
    # Inputs: terminal bus voltages in abc.
    # ------------------------------------------------------------------
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)
    # The sharing-enabled variant relies on the same PF-derived abc references as
    # the base Thevenin template so both models reconstruct the same operating
    # point during explicit initialization.
    d_v_A = vf.add_var(name=f"d_v_A_{name}", reference=VarPowerFlowRefferenceType.d_v_A)
    d_v_B = vf.add_var(name=f"d_v_B_{name}", reference=VarPowerFlowRefferenceType.d_v_B)
    d_v_C = vf.add_var(name=f"d_v_C_{name}", reference=VarPowerFlowRefferenceType.d_v_C)
    p_A = vf.add_var(name=f"P_A_{name}", reference=VarPowerFlowRefferenceType.P_A)
    q_A = vf.add_var(name=f"Q_A_{name}", reference=VarPowerFlowRefferenceType.Q_A)
    p_B = vf.add_var(name=f"P_B_{name}", reference=VarPowerFlowRefferenceType.P_B)
    q_B = vf.add_var(name=f"Q_B_{name}", reference=VarPowerFlowRefferenceType.Q_B)
    p_C = vf.add_var(name=f"P_C_{name}", reference=VarPowerFlowRefferenceType.P_C)
    q_C = vf.add_var(name=f"Q_C_{name}", reference=VarPowerFlowRefferenceType.Q_C)
    inputs: List[Any] = list([v_A, v_B, v_C])

    # ------------------------------------------------------------------
    # States:
    # - current dynamics
    # - absolute synchronous angle
    # - bounded sharing angle offset
    # - internal emf sharing scale
    # - PI controller integral states
    # ------------------------------------------------------------------
    i_A = vf.add_var(name=f"i_A_{name}", reference=VarPowerFlowRefferenceType.i_A)
    i_B = vf.add_var(name=f"i_B_{name}", reference=VarPowerFlowRefferenceType.i_B)
    i_C = vf.add_var(name=f"i_C_{name}", reference=VarPowerFlowRefferenceType.i_C)

    theta = vf.add_var(name=f"theta_{name}")
    delta_share = vf.add_var(name=f"delta_share_{name}")
    E_ctrl_scale = vf.add_var(name=f"E_ctrl_scale_{name}")
    xi_share_p = vf.add_var(name=f"xi_share_p_{name}")
    xi_share_q = vf.add_var(name=f"xi_share_q_{name}")

    d_i_A = vf.add_diff_var(name=f"d_i_A_{name}", base_var=i_A)
    d_i_B = vf.add_diff_var(name=f"d_i_B_{name}", base_var=i_B)
    d_i_C = vf.add_diff_var(name=f"d_i_C_{name}", base_var=i_C)
    d_theta = vf.add_diff_var(name=f"d_theta_{name}", base_var=theta)
    d_delta_share = vf.add_diff_var(name=f"d_delta_share_{name}", base_var=delta_share)
    d_E_ctrl_scale = vf.add_diff_var(name=f"d_E_ctrl_scale_{name}", base_var=E_ctrl_scale)
    d_xi_share_p = vf.add_diff_var(name=f"d_xi_share_p_{name}", base_var=xi_share_p)
    d_xi_share_q = vf.add_diff_var(name=f"d_xi_share_q_{name}", base_var=xi_share_q)

    # ------------------------------------------------------------------
    # Algebraic variables:
    # - internal phase emfs
    # - measured active/reactive power
    # ------------------------------------------------------------------
    e_A = vf.add_var(name=f"e_A_{name}")
    e_B = vf.add_var(name=f"e_B_{name}")
    e_C = vf.add_var(name=f"e_C_{name}")
    Pe = vf.add_var(name=f"Pe_{name}")
    Qe = vf.add_var(name=f"Qe_{name}")

    # ------------------------------------------------------------------
    # Static parameters and PF-derived initialization parameters.
    # ------------------------------------------------------------------
    omega_base = vf.add_var(name=f"omega_base_{name}")
    R_s = vf.add_var(name=f"R_s_{name}")
    X_s = vf.add_var(name=f"X_s_{name}")

    phi_v = vf.add_var(name=f"phi_v_{name}")
    phi = vf.add_var(name=f"phi_{name}")
    Vpk = vf.add_var(name=f"Vpk_{name}")
    Ipk = vf.add_var(name=f"Ipk_{name}")

    phi_v_init: sym.Expr
    phi_init: sym.Expr
    vpk_init: sym.Expr
    ipk_init: sym.Expr
    phi_v_init, phi_init, vpk_init, ipk_init = get_pf_positive_sequence_init_refs(
        v_a=v_A,
        v_b=v_B,
        v_c=v_C,
        d_v_a=d_v_A,
        d_v_b=d_v_B,
        d_v_c=d_v_C,
        p_a=p_A,
        q_a=q_A,
        p_b=p_B,
        q_b=q_B,
        p_c=p_C,
        q_c=q_C,
        omega_base=omega_base,
    )

    # ------------------------------------------------------------------
    # Optional sharing references and internal controller gains.
    # The references are assigned by EmtProblemDae when multiple generators
    # share the same slack bus. The gains remain purely local event params.
    # ------------------------------------------------------------------
    share_enable = vf.add_var(name=f"share_enable_{name}")
    P_share_ref = vf.add_var(name=f"P_share_ref_{name}")
    Q_share_ref = vf.add_var(name=f"Q_share_ref_{name}")

    kp_share_p = vf.add_var(name=f"kp_share_p_{name}")
    ki_share_p = vf.add_var(name=f"ki_share_p_{name}")
    kp_share_q = vf.add_var(name=f"kp_share_q_{name}")
    ki_share_q = vf.add_var(name=f"ki_share_q_{name}")
    k_delta_share = vf.add_var(name=f"k_delta_share_{name}")
    k_e_scale = vf.add_var(name=f"k_e_scale_{name}")
    E_scale = vf.add_var(name=f"E_scale_{name}")

    # ------------------------------------------------------------------
    # PF-consistent positive-sequence internal emf.
    # This part remains identical in spirit to the original Thevenin model.
    # ------------------------------------------------------------------
    E_re = Vpk + R_s * Ipk * sym.cos(phi) - X_s * Ipk * sym.sin(phi)
    E_im = R_s * Ipk * sym.sin(phi) + X_s * Ipk * sym.cos(phi)
    # ``atan2`` keeps the reconstructed emf angle consistent across quadrants and
    # avoids undefined divisions when the steady-state real component is zero.
    delta_expr = sym.atan2(E_im, E_re)
    Epk_expr = (E_re ** 2 + E_im ** 2 + c_eps_emf) ** c05

    # ------------------------------------------------------------------
    # Power measurement errors used by the sharing controllers.
    # ------------------------------------------------------------------
    p_error = P_share_ref - Pe
    q_error = Q_share_ref - Qe

    # ------------------------------------------------------------------
    # Controller design:
    #
    # 1. The absolute angle keeps the synchronous speed.
    # 2. Active-power sharing acts on a bounded internal angle offset.
    # 3. Reactive-power sharing acts on the emf scale with a restoring term.
    #
    # This avoids the unbounded drift produced when the controller acts
    # directly on dtheta/dt.
    # ------------------------------------------------------------------
    theta_speed = omega_base

    delta_share_speed = share_enable * (
        kp_share_p * p_error
        + xi_share_p
        - k_delta_share * delta_share
    )

    E_ctrl_scale_speed = share_enable * (
        kp_share_q * q_error
        + xi_share_q
        - k_e_scale * (E_ctrl_scale - c1)
    )

    # The actual electrical source angle used by the balanced internal emf.
    theta_eff = theta + delta_share
    total_e_scale = E_scale * E_ctrl_scale

    # ------------------------------------------------------------------
    # Build the EMT block.
    # ------------------------------------------------------------------
    state_eqs: List[Any] = list([
        omega_base * (e_A - R_s * i_A - v_A) / X_s,
        omega_base * (e_B - R_s * i_B - v_B) / X_s,
        omega_base * (e_C - R_s * i_C - v_C) / X_s,
        theta_speed,
        delta_share_speed,
        E_ctrl_scale_speed,
        share_enable * ki_share_p * p_error,
        share_enable * ki_share_q * q_error,
    ])

    state_vars: List[Any] = list([
        i_A,
        i_B,
        i_C,
        theta,
        delta_share,
        E_ctrl_scale,
        xi_share_p,
        xi_share_q,
    ])

    algebraic_eqs: List[Any] = list([
        e_A - total_e_scale * Epk_expr * sym.sin(theta_eff),
        e_B - total_e_scale * Epk_expr * sym.sin(theta_eff - 2.0 * np.pi / 3.0),
        e_C - total_e_scale * Epk_expr * sym.sin(theta_eff + 2.0 * np.pi / 3.0),
        Pe - (i_A * v_A + i_B * v_B + i_C * v_C),
        Qe - (1.0 / np.sqrt(3.0)) * (
            (v_A - v_B) * i_C +
            (v_B - v_C) * i_A +
            (v_C - v_A) * i_B
        ),
    ])

    algebraic_vars: List[Any] = list([e_A, e_B, e_C, Pe, Qe])

    templ.block = Block(
        state_eqs=state_eqs,
        state_vars=state_vars,
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        in_vars=inputs,
        out_vars=list([i_A, i_B, i_C]),
    )

    templ.block.diff_vars = list([
        d_i_A,
        d_i_B,
        d_i_C,
        d_theta,
        d_delta_share,
        d_E_ctrl_scale,
        d_xi_share_p,
        d_xi_share_q,
    ])

    # ------------------------------------------------------------------
    # External mapping:
    # keep the original EMT injection interface intact.
    # ------------------------------------------------------------------
    templ.block.external_mapping = dict({
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: v_B,
        VarPowerFlowRefferenceType.v_C: v_C,
        VarPowerFlowRefferenceType.d_v_A: d_v_A,
        VarPowerFlowRefferenceType.d_v_B: d_v_B,
        VarPowerFlowRefferenceType.d_v_C: d_v_C,
        VarPowerFlowRefferenceType.P_A: p_A,
        VarPowerFlowRefferenceType.Q_A: q_A,
        VarPowerFlowRefferenceType.P_B: p_B,
        VarPowerFlowRefferenceType.Q_B: q_B,
        VarPowerFlowRefferenceType.P_C: p_C,
        VarPowerFlowRefferenceType.Q_C: q_C,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,
        VarPowerFlowRefferenceType.phi_v: phi_v,
        VarPowerFlowRefferenceType.phi: phi,
        VarPowerFlowRefferenceType.Vpk: Vpk,
        VarPowerFlowRefferenceType.Ipk: Ipk
    })

    # ------------------------------------------------------------------
    # API-object mapping:
    # static generator parameters plus optional sharing references assigned
    # by EmtProblemDae.
    # ------------------------------------------------------------------
    templ.block.api_obj_mapping = dict({
        ParamPowerFlowRefferenceType.omega_base: omega_base,
        ParamPowerFlowRefferenceType.R1: R_s,
        ParamPowerFlowRefferenceType.X1: X_s,
        ParamPowerFlowRefferenceType.X0: None,
        ParamPowerFlowRefferenceType.generator_share_enable: share_enable,
        ParamPowerFlowRefferenceType.generator_share_p_ref: P_share_ref,
        ParamPowerFlowRefferenceType.generator_share_q_ref: Q_share_ref,
    })

    # ------------------------------------------------------------------
    # Event parameters:
    # PF-derived phasor quantities plus local controller gains.
    # The gains are intentionally conservative compared with the version
    # that acted directly on dtheta/dt.
    # ------------------------------------------------------------------
    templ.block.event_dict = dict({
        # The sharing-enabled variant uses the same seeded PF references. They
        # must be registered as runtime parameters so the EMT problem builder can
        # inject the three-phase PF data before initialization starts.
        d_v_A: vf.add_const(None),
        d_v_B: vf.add_const(None),
        d_v_C: vf.add_const(None),
        p_A: vf.add_const(None),
        q_A: vf.add_const(None),
        p_B: vf.add_const(None),
        q_B: vf.add_const(None),
        p_C: vf.add_const(None),
        q_C: vf.add_const(None),
        # These placeholders are resolved from ``init_eqs`` after the PF-derived
        # abc references have been seeded into the symbolic model.
        phi_v: vf.add_const(None),
        phi: vf.add_const(None),
        Vpk: vf.add_const(None),
        Ipk: vf.add_const(None),
        kp_share_p: vf.add_const(1.0),
        ki_share_p: vf.add_const(10.0),
        kp_share_q: vf.add_const(0.5),
        ki_share_q: vf.add_const(5.0),
        k_delta_share: vf.add_const(20.0),
        k_e_scale: vf.add_const(10.0),
        # This remains a pure event/runtime parameter so scripts and EMT events
        # can scale the Thevenin source magnitude from outside the model.
        E_scale: vf.add_const(1.0),
    })

    # ------------------------------------------------------------------
    # Initialization equations:
    # the sharing controller starts exactly from the PF-consistent open-loop
    # operating point, so it does not create a jump at t = 0.
    # ------------------------------------------------------------------
    templ.block.init_eqs = dict({
        phi_v: phi_v_init,
        phi: phi_init,
        Vpk: vpk_init,
        Ipk: ipk_init,
        theta: phi_v + delta_expr,
        delta_share: c0,
        # The internal sharing scale starts from unity so the external eventable
        # ``E_scale`` parameter is the only voltage-scaling action at t = 0.
        E_ctrl_scale: c1,
        xi_share_p: c0,
        xi_share_q: c0,
        e_A: total_e_scale * Epk_expr * sym.sin(theta_eff),
        e_B: total_e_scale * Epk_expr * sym.sin(theta_eff - 2.0 * np.pi / 3.0),
        e_C: total_e_scale * Epk_expr * sym.sin(theta_eff + 2.0 * np.pi / 3.0),
        Pe: (i_A * v_A + i_B * v_B + i_C * v_C),
        Qe: (1.0 / np.sqrt(3.0)) * (
            (v_A - v_B) * i_C +
            (v_B - v_C) * i_A +
            (v_C - v_A) * i_B
        ),
    })

    # ------------------------------------------------------------------
    # Differential initialization equations:
    # these keep the standard EMT explicit-init semantics.
    # ------------------------------------------------------------------
    templ.block.diff_init_eqs = dict({
        d_i_A: omega_base * (e_A - R_s * i_A - v_A) / X_s,
        d_i_B: omega_base * (e_B - R_s * i_B - v_B) / X_s,
        d_i_C: omega_base * (e_C - R_s * i_C - v_C) / X_s,
        d_theta: theta_speed,
        d_delta_share: delta_share_speed,
        d_E_ctrl_scale: E_ctrl_scale_speed,
        d_xi_share_p: share_enable * ki_share_p * p_error,
        d_xi_share_q: share_enable * ki_share_q * q_error,
    })

    return templ

