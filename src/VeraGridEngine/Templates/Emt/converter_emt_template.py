# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from VeraGridEngine.enumerations import DeviceType, ConverterControlType
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
import VeraGridEngine.Utils.Symbolic.symbolic as sym

"""
Standard converter template for EMT simulation.

This is an ideal converter model that connects a DC bus with an AC bus,
maintaining power balance: P_ac = P_dc

The converter takes:
- DC side: V_dc (bus DC voltage) as input
- AC side: v_A, v_B, v_C (bus AC instantaneous voltages) as inputs

And provides:
- DC side: I_dc (current flowing into the DC bus)
- AC side: i_A, i_B, i_C (instantaneous three-phase currents)

External mapping for EmtProblemDae:
- v_A, v_B, v_C: AC bus voltages (from bus)
- Vdc: DC bus voltage (from bus)
- i_A, i_B, i_C: AC phase currents (to bus - entering the bus)
- Idc: DC current (to bus - entering the DC bus)

For KCL connection:
- If the DC bus is bus_from: If_dc is looked up
- If the DC bus is bus_to: It_dc is looked up
- AC currents i_A, i_B, i_C are added to the AC bus KCL
"""

def get_emt_ideal_converter(
    vf: VarFactory,
    name: str = "ideal_converter_emt",
    sbase: float = 1.0,
    fbase: float = 50.0,
    P_ref0: float = 0.0,
    Q_ref0: float = 0.0,
    P_loss0: float = 0.0,
    control1: ConverterControlType | None = None,
    control2: ConverterControlType | None = None,
    control1_val: float | None = None,
    control2_val: float | None = None,
    vdc_kp: float = 2.0,
) -> EmtModelTemplate:
    """
    Build an idealized averaged EMT converter model current injection type with DC power balance.

    It does not represent:
    switching,
    PLL,
    inner current loop,
    L filter,
    DC capacitor,
    Current or voltage dependent losses
    Transformer
    Snubbers or filters

    The AC-side current reference is synthesized from fundamental-frequency P/Q
    commands in a synchronized rotating frame. This is a better physical approximation of a grid-following
    converter than an instantaneous constant-power current source.

    ``P_ref``, ``Q_ref`` and ``P_loss`` are interpreted in system-base units
    (MW / MVAr on ``sbase``), because that is the convention used by the EMT
    initialization layer when it maps power-flow values into external references.

   :param vf: Variable factory for creating symbolic variables
   :param name: Name for the converter model
   :param sbase: System base power used to convert external power references to pu
   :param fbase: System base frequency for the synchronized current references

    :return: EmtModelTemplate with the converter block
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name
    templ.block.name = name

    # =================================================================
    # INPUT VARIABLES (from buses)
    # =================================================================
    # AC side voltages from the AC bus
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)

    # DC side voltage from the DC bus
    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowRefferenceType.Vdc)

    inputs = [v_A, v_B, v_C, v_dc]

    # =================================================================
    # OUTPUT VARIABLES (to buses)
    # =================================================================
    i_A = vf.add_var(name=f"i_A_{name}", reference=VarPowerFlowRefferenceType.i_A)
    i_B = vf.add_var(name=f"i_B_{name}", reference=VarPowerFlowRefferenceType.i_B)
    i_C = vf.add_var(name=f"i_C_{name}", reference=VarPowerFlowRefferenceType.i_C)
    theta = vf.add_var(name=f"theta_{name}")

    d_theta = vf.add_diff_var(name=f"d_theta_{name}", base_var=theta)

    i_dc = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowRefferenceType.Idc)

    # =================================================================
    # INTERNAL VARIABLES
    # =================================================================
    P_ref = vf.add_var(name=f"P_ref_{name}")
    Q_ref = vf.add_var(name=f"Q_ref_{name}")
    Vdc_ref = vf.add_var(name=f"Vdc_ref_{name}")
    P_loss = vf.add_var(name=f"P_loss_{name}")
    omega_base = vf.add_var(name=f"omega_base_{name}")
    phi_v = vf.add_var(name=f"phi_v_{name}")
    Vpk = vf.add_var(name=f"Vpk_{name}")

    # =================================================================
    # PARAMETERS
    # =================================================================

    regulate_vdc = (
        control1 == ConverterControlType.Vm_dc
        or control2 == ConverterControlType.Vm_dc
    )

    regulate_q = control1 == ConverterControlType.Qac or control2 == ConverterControlType.Qac

    vdc_ref0 = 1.0
    if control1 == ConverterControlType.Vm_dc and control1_val is not None:
        vdc_ref0 = float(control1_val)
    elif control2 == ConverterControlType.Vm_dc and control2_val is not None:
        vdc_ref0 = float(control2_val)

    eps = vf.add_const(1e-10)
    c_two_over_three = vf.add_const(2.0 / 3.0)
    c_sqrt3_over_two = vf.add_const(np.sqrt(3.0) / 2.0)
    c_half = vf.add_const(0.5)
    c_sbase = vf.add_const(max(float(sbase), 1e-12))
    event_dict = {
        P_ref: vf.add_const(P_ref0),
        Q_ref: vf.add_const(Q_ref0),
        Vdc_ref: vf.add_const(vdc_ref0),
        P_loss: vf.add_const(P_loss0),
        omega_base: vf.add_const(2.0 * np.pi * float(fbase)),
        phi_v: vf.add_const(0.0),
        Vpk: vf.add_const(np.sqrt(2.0)),
    }

    # =================================================================
    # CURRENT REFERENCE EQUATIONS
    # =================================================================
    P_dc_cmd = P_ref + vf.add_const(vdc_kp) * (v_dc - Vdc_ref) if regulate_vdc else P_ref
    Q_cmd = Q_ref if regulate_q else vf.add_const(0.0)
    P_dc_cmd_pu = P_dc_cmd / c_sbase
    Q_cmd_pu = Q_cmd / c_sbase
    P_ac_cmd_pu = P_dc_cmd_pu + P_loss / c_sbase

    i_d_cmd = c_two_over_three * Q_cmd_pu / (Vpk + eps)
    i_q_cmd = c_two_over_three * P_ac_cmd_pu / (Vpk + eps)

    i_A_cmd = i_d_cmd * sym.cos(theta) + i_q_cmd * sym.sin(theta)
    i_B_cmd = ((-c_half * i_d_cmd - c_sqrt3_over_two * i_q_cmd) * sym.cos(theta)
               + ((c_sqrt3_over_two * i_d_cmd) - c_half * i_q_cmd) * sym.sin(theta))
    i_C_cmd = ((-c_half * i_d_cmd + c_sqrt3_over_two * i_q_cmd) * sym.cos(theta)
               + ((-c_sqrt3_over_two * i_d_cmd) - c_half * i_q_cmd) * sym.sin(theta))

    state_eqs = [omega_base]

    algebraic_eqs = [
        i_A - i_A_cmd,
        i_B - i_B_cmd,
        i_C - i_C_cmd,
        v_dc * i_dc + P_dc_cmd_pu,
    ]

    # =================================================================
    # ALGEBRAIC VARIABLES
    # =================================================================
    algebraic_vars = [i_A, i_B, i_C, i_dc]

    # =================================================================
    # INITIALIZATION EQUATIONS
    # =================================================================
    init_eqs = {
        i_dc: -P_dc_cmd_pu / (v_dc + eps),
        theta: phi_v,
    }

    # =================================================================
    # BUILD THE BLOCK
    # =================================================================
    converter_block = Block(
        state_eqs=state_eqs,
        state_vars=[theta],
        diff_vars=[d_theta],
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        event_dict=event_dict,
        init_eqs=init_eqs,
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, i_dc],
    )

    # =================================================================
    # EXTERNAL MAPPING
    # =================================================================
    # This mapping tells EmtProblemDae how to connect the converter
    # to the buses based on the device configuration
    converter_block.external_mapping = {
        VarPowerFlowRefferenceType.v_N: None,
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: v_B,
        VarPowerFlowRefferenceType.v_C: v_C,

        VarPowerFlowRefferenceType.Vdc: v_dc,

        VarPowerFlowRefferenceType.i_N: None,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,

        VarPowerFlowRefferenceType.if_N: None,
        VarPowerFlowRefferenceType.if_A: None,
        VarPowerFlowRefferenceType.if_B: None,
        VarPowerFlowRefferenceType.if_C: None,

        VarPowerFlowRefferenceType.it_N: None,
        VarPowerFlowRefferenceType.it_A: None,
        VarPowerFlowRefferenceType.it_B: None,
        VarPowerFlowRefferenceType.it_C: None,

        VarPowerFlowRefferenceType.Sf_A: None,
        VarPowerFlowRefferenceType.Sf_B: None,
        VarPowerFlowRefferenceType.Sf_C: None,

        VarPowerFlowRefferenceType.St_A: None,
        VarPowerFlowRefferenceType.St_B: None,
        VarPowerFlowRefferenceType.St_C: None,

        VarPowerFlowRefferenceType.d_v_N_f: None,
        VarPowerFlowRefferenceType.d_v_A_f: None,
        VarPowerFlowRefferenceType.d_v_B_f: None,
        VarPowerFlowRefferenceType.d_v_C_f: None,

        VarPowerFlowRefferenceType.d_v_N_t: None,
        VarPowerFlowRefferenceType.d_v_A_t: None,
        VarPowerFlowRefferenceType.d_v_B_t: None,
        VarPowerFlowRefferenceType.d_v_C_t: None,

        # For KCL at DC bus (bus_from)
        VarPowerFlowRefferenceType.Idc: i_dc,
        VarPowerFlowRefferenceType.P: None,
        VarPowerFlowRefferenceType.Q: None,
        VarPowerFlowRefferenceType.phi_v: phi_v,
        VarPowerFlowRefferenceType.Vpk: Vpk,
    }

    converter_block.name = name
    templ.block = converter_block

    return templ


def get_pseudo_emt_converter(
    vf: VarFactory,
    name: str = "pseudo_converter_emt",
    sbase: float = 1.0,
    fbase: float = 50.0,
    P_ref0: float = 0.0,
    Q_ref0: float = 0.0,
    Vdc_ref0: float = 1.0,
    R_eq: float = 0.02,
    L_eq: float = 0.08,
    C_dc: float = 0.05,
    R_dc: float = 1e6,
    R_dc_term: float = 1e-4,
    pll_kp: float = 40.0,
    pll_ki: float = 400.0,
    i_kp: float = 0.5,
    i_ki: float = 40.0,
    vdc_kp: float = 1.5,
    vdc_ki: float = 30.0,
    q_kp: float = 0.6,
    q_ki: float = 25.0,
    i_max: float = 1.2,
    m_max: float = 0.95,
    P_loss0: float = 0.0,
    P_loss_i1: float = 0.01,
    P_loss_i2: float = 0.01,
    tau_meas: float = 0.01,
    aw_gain: float = 1.0,
    vdc_floor: float = 0.05,
    control1: ConverterControlType | None = ConverterControlType.Vm_dc,
    control2: ConverterControlType | None = ConverterControlType.Qac,
    control1_val: float | None = None,
    control2_val: float | None = None,
) -> EmtModelTemplate:
    """
    Build a pseudo-EMT averaged grid-following VSC model with explicit DC-link
    capacitor, SRF-PLL, outer Vdc/Q loops, inner dq current control, current
    limitation and converter voltage limitation.

    Physical meaning
    ----------------
    This model represents a three-phase voltage-source converter operated in
    grid-following mode. The converter is not modeled as an ideal current source.
    Instead, it creates an averaged internal converter voltage in a synchronous
    rotating frame and exchanges current with the AC bus through an equivalent
    series impedance ``R_eq + j w L_eq``. On the DC side, an explicit capacitor
    state ``v_dc`` stores energy and is balanced against the AC-side power,
    converter losses, and an optional DC leakage branch ``R_dc``.

    Main hypotheses
    ---------------
    - The converter is averaged: no switching functions, no carrier, no PWM
      ripple, no valve-level detail, and no explicit harmonic content from
      commutation are represented.
    - The AC interface is reduced to a single equivalent series branch that can
      lump reactor, transformer leakage and other dominant fundamental-frequency
      effects.
    - Synchronization is performed with a basic synchronous-reference-frame PLL
      that aligns the q-axis with the bus voltage, so ``v_d`` is driven to zero
      in normal operation.
    - The DC-link is explicit, but the terminal DC voltage mapping required by
      VeraGrid is preserved through a small explicit DC terminal resistance
      ``R_dc_term``. This gives a well-posed current-source interface for the
      existing EMT architecture while keeping the converter-side capacitor state
      explicit.

    Included phenomena
    ------------------
    - Explicit DC-link capacitor dynamics.
    - Optional DC leakage through ``R_dc``.
    - Fundamental dq current dynamics through ``R_eq`` and ``L_eq``.
    - SRF-PLL with angle state and integral state.
    - Outer control loops for DC voltage and reactive power.
    - Inner current PI control in dq.
    - First-order filtered measurements of ``P`` and ``Q``.
    - Current magnitude limit and internal converter voltage (modulation) limit.
    - Basic anti-windup via back-calculation terms in the outer and inner PI
      integrator states.
    - A simple loss model: ``P_loss = P_loss0 + P_loss_i1 * |I| + P_loss_i2 * I^2``.

    Not included
    ------------
    - Detailed switching, PWM carrier, dead time, semiconductor dynamics,
      saturation of magnetics, harmonic filters, MMC submodules, neutral-point
      balancing, sequence-selective control, unbalance-specific controllers,
      protection logic, and detailed DC-network line dynamics.

    States
    ------
    - ``v_dc``: DC-link capacitor voltage.
    - ``theta_pll``: PLL angle.
    - ``xi_pll``: PLL integral state.
    - ``i_d``, ``i_q``: equivalent filter currents in the PLL dq frame.
    - ``xi_id``, ``xi_iq``: current PI integrator states.
    - ``xi_vdc``, ``xi_q``: outer-loop PI integrator states.
    - ``P_f``, ``Q_f``: filtered active and reactive power measurements.

    Control structure
    -----------------
    - PLL: ``omega_pll = omega_base + pll_kp * v_d + xi_pll`` and
      ``d(xi_pll)/dt = pll_ki * v_d``.
    - Outer active-axis loop: the default and supported primary mode is
      ``ConverterControlType.Vm_dc``. It regulates the explicit DC-link voltage.
      ``P_ref`` is used as an operating-point feedforward that translates an
      initial active-power schedule into an initial q-axis current bias; this
      avoids forcing the Vdc integrator to carry the whole steady-state burden.
    - Outer reactive loop: the supported secondary mode is
      ``ConverterControlType.Qac`` using filtered ``Q`` feedback.
    - Inner loop: dq current PI plus standard decoupling/feedforward terms to
      command the internal averaged converter voltage.

    Main equations
    --------------
    AC side (dq frame, positive currents injected into the AC bus):

    ``P = 3/2 * (v_q * i_q + v_d * i_d)``

    ``Q = 3/2 * (v_q * i_d - v_d * i_q)``

    ``L_eq * di_d/dt = v_cmd_d - v_d - R_eq * i_d + omega_pll * L_eq * i_q``

    ``L_eq * di_q/dt = v_cmd_q - v_q - R_eq * i_q - omega_pll * L_eq * i_d``

    DC side:

    ``C_dc * dv_dc/dt = -i_dc - i_dc_conv - v_dc / R_dc``

    where ``i_dc`` is the current injected into the external DC bus following the
    VeraGrid sign convention (positive when entering the bus), and
    ``i_dc_conv = (P + P_loss) / max(v_dc, vdc_floor)`` is the averaged DC current
    demanded by the converter bridge.

    DC terminal relation:

    ``i_dc = (v_dc - v_dc_terminal) / R_dc_term``

    Power and measurement filters:

    ``d(P_f)/dt = (P - P_f) / tau_meas``

    ``d(Q_f)/dt = (Q - Q_f) / tau_meas``

    Current references:

    ``i_q_ref_u = i_q_ff + vdc_kp * (Vdc_ref - v_dc) + xi_vdc``

    ``i_d_ref_u = q_kp * (Q_ref - Q_f) + xi_q``

    with ``i_q_ff = (2/3) * P_ref / |v_dq|`` expressed on system base.

    Limits and anti-windup
    ----------------------
    - The total current is limited with q-axis priority. ``i_q_ref`` is clipped to
      ``[-i_max, i_max]`` and the available d-axis margin is
      ``sqrt(max(i_max^2 - i_q_ref^2, eps))``.
    - The internal converter voltage is limited with q-axis priority using
      ``v_lim = 0.5 * m_max * v_dc``.
    - Anti-windup is implemented by feeding the difference between saturated and
      unsaturated commands back into the corresponding integrator state
      derivatives.

    Initialization
    --------------
    Initialization is approximate but physically coherent and numerically robust.
    The PLL angle starts from ``phi_v`` obtained from the power-flow mapping,
    ``v_dc`` starts from the mapped DC terminal voltage, the dq currents are
    initialized from the requested ``P_ref0`` and ``Q_ref0`` using ``Vpk``, and the
    filtered powers are initialized at their instantaneous values. The current PI
    integrators start from zero, while the outer-loop integrators start from zero
    because the steady-state operating point is primarily carried by the explicit
    feedforward terms and by choosing ``Vdc_ref`` equal to the initial ``v_dc``.

    Supported control modes
    -----------------------
    This implementation intentionally supports only the clean minimal target
    combination requested for the pseudo-EMT model:
    - ``control1`` in ``{None, ConverterControlType.Vm_dc}``
    - ``control2`` in ``{None, ConverterControlType.Qac}``

    Any other combination raises ``ValueError``. This avoids embedding less
    consistent control logic into a model whose main purpose is to provide a more
    physical pseudo-EMT Vdc/Q grid-following converter.

    Units and parameter interpretation
    ----------------------------------
    - ``P_ref0``, ``Q_ref0`` and the loss coefficients are interpreted on system
      base ``sbase``, following the same convention as the ideal converter
      template in this file.
    - ``R_eq``, ``L_eq``, ``C_dc``, ``R_dc``, gains and limits are assumed to be
      in the same per-unit / normalized EMT formulation used by the surrounding
      template framework.

    Limitations
    -----------
    This remains a reduced-order averaged model. It captures the dominant energy,
    current-control and synchronization dynamics of a grid-following VSC, but it
    does not reproduce switching harmonics, sub-cycle modulation effects, exact
    semiconductor losses, detailed transformer magnetics, weak-grid sequence
    separation, fault blocking behaviour or detailed DC-side network resonances.
    """
    if control1 not in (None, ConverterControlType.Vm_dc):
        raise ValueError(
            f"Pseudo EMT converter supports only control1=None/Vm_dc, got {control1}"
        )
    if control2 not in (None, ConverterControlType.Qac):
        raise ValueError(
            f"Pseudo EMT converter supports only control2=None/Qac, got {control2}"
        )

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name
    templ.block.name = name

    # =================================================================
    # INPUT VARIABLES (from buses)
    # =================================================================
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)
    v_dc_bus = vf.add_var(name=f"v_dc_bus_{name}", reference=VarPowerFlowRefferenceType.Vdc)
    inputs = [v_A, v_B, v_C, v_dc_bus]

    # =================================================================
    # OUTPUT VARIABLES (to buses)
    # =================================================================
    i_A = vf.add_var(name=f"i_A_{name}", reference=VarPowerFlowRefferenceType.i_A)
    i_B = vf.add_var(name=f"i_B_{name}", reference=VarPowerFlowRefferenceType.i_B)
    i_C = vf.add_var(name=f"i_C_{name}", reference=VarPowerFlowRefferenceType.i_C)
    i_dc = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowRefferenceType.Idc)

    # =================================================================
    # STATES AND DIFFERENTIAL VARIABLES
    # =================================================================
    v_dc = vf.add_var(name=f"v_dc_{name}")
    theta_pll = vf.add_var(name=f"theta_pll_{name}")
    xi_pll = vf.add_var(name=f"xi_pll_{name}")
    i_d = vf.add_var(name=f"i_d_{name}")
    i_q = vf.add_var(name=f"i_q_{name}")
    xi_id = vf.add_var(name=f"xi_id_{name}")
    xi_iq = vf.add_var(name=f"xi_iq_{name}")
    xi_vdc = vf.add_var(name=f"xi_vdc_{name}")
    xi_q = vf.add_var(name=f"xi_q_{name}")
    P_f = vf.add_var(name=f"P_f_{name}")
    Q_f = vf.add_var(name=f"Q_f_{name}")

    d_v_dc = vf.add_diff_var(name=f"d_v_dc_{name}", base_var=v_dc)
    d_theta_pll = vf.add_diff_var(name=f"d_theta_pll_{name}", base_var=theta_pll)
    d_xi_pll = vf.add_diff_var(name=f"d_xi_pll_{name}", base_var=xi_pll)
    d_i_d = vf.add_diff_var(name=f"d_i_d_{name}", base_var=i_d)
    d_i_q = vf.add_diff_var(name=f"d_i_q_{name}", base_var=i_q)
    d_xi_id = vf.add_diff_var(name=f"d_xi_id_{name}", base_var=xi_id)
    d_xi_iq = vf.add_diff_var(name=f"d_xi_iq_{name}", base_var=xi_iq)
    d_xi_vdc = vf.add_diff_var(name=f"d_xi_vdc_{name}", base_var=xi_vdc)
    d_xi_q = vf.add_diff_var(name=f"d_xi_q_{name}", base_var=xi_q)
    d_P_f = vf.add_diff_var(name=f"d_P_f_{name}", base_var=P_f)
    d_Q_f = vf.add_diff_var(name=f"d_Q_f_{name}", base_var=Q_f)

    # =================================================================
    # INTERNAL ALGEBRAIC VARIABLES
    # =================================================================
    P_ref = vf.add_var(name=f"P_ref_{name}")
    Q_ref = vf.add_var(name=f"Q_ref_{name}")
    Vdc_ref = vf.add_var(name=f"Vdc_ref_{name}")
    omega_base = vf.add_var(name=f"omega_base_{name}")
    phi_v = vf.add_var(name=f"phi_v_{name}")
    Vpk = vf.add_var(name=f"Vpk_{name}")

    R_eq_p = vf.add_var(name=f"R_eq_{name}")
    L_eq_p = vf.add_var(name=f"L_eq_{name}")
    C_dc_p = vf.add_var(name=f"C_dc_{name}")
    R_dc_p = vf.add_var(name=f"R_dc_{name}")
    R_dc_term_p = vf.add_var(name=f"R_dc_term_{name}")
    pll_kp_p = vf.add_var(name=f"pll_kp_{name}")
    pll_ki_p = vf.add_var(name=f"pll_ki_{name}")
    i_kp_p = vf.add_var(name=f"i_kp_{name}")
    i_ki_p = vf.add_var(name=f"i_ki_{name}")
    vdc_kp_p = vf.add_var(name=f"vdc_kp_{name}")
    vdc_ki_p = vf.add_var(name=f"vdc_ki_{name}")
    q_kp_p = vf.add_var(name=f"q_kp_{name}")
    q_ki_p = vf.add_var(name=f"q_ki_{name}")
    i_max_p = vf.add_var(name=f"i_max_{name}")
    m_max_p = vf.add_var(name=f"m_max_{name}")
    P_loss0_p = vf.add_var(name=f"P_loss0_{name}")
    P_loss_i1_p = vf.add_var(name=f"P_loss_i1_{name}")
    P_loss_i2_p = vf.add_var(name=f"P_loss_i2_{name}")
    tau_meas_p = vf.add_var(name=f"tau_meas_{name}")
    aw_gain_p = vf.add_var(name=f"aw_gain_{name}")
    vdc_floor_p = vf.add_var(name=f"vdc_floor_{name}")

    v_d = vf.add_var(name=f"v_d_{name}")
    v_q = vf.add_var(name=f"v_q_{name}")
    v_mag = vf.add_var(name=f"v_mag_{name}")
    P = vf.add_var(name=f"P_{name}")
    Q = vf.add_var(name=f"Q_{name}")
    omega_pll = vf.add_var(name=f"omega_pll_{name}")
    i_mag = vf.add_var(name=f"i_mag_{name}")
    P_loss = vf.add_var(name=f"P_loss_{name}")
    i_dc_conv = vf.add_var(name=f"i_dc_conv_{name}")
    i_q_ff = vf.add_var(name=f"i_q_ff_{name}")
    i_q_ref_u = vf.add_var(name=f"i_q_ref_u_{name}")
    i_d_ref_u = vf.add_var(name=f"i_d_ref_u_{name}")
    i_q_ref = vf.add_var(name=f"i_q_ref_{name}")
    i_d_ref = vf.add_var(name=f"i_d_ref_{name}")
    v_pi_d_u = vf.add_var(name=f"v_pi_d_u_{name}")
    v_pi_q_u = vf.add_var(name=f"v_pi_q_u_{name}")
    v_cmd_d_u = vf.add_var(name=f"v_cmd_d_u_{name}")
    v_cmd_q_u = vf.add_var(name=f"v_cmd_q_u_{name}")
    v_lim = vf.add_var(name=f"v_lim_{name}")
    v_cmd_d = vf.add_var(name=f"v_cmd_d_{name}")
    v_cmd_q = vf.add_var(name=f"v_cmd_q_{name}")

    # =================================================================
    # PARAMETERS / EVENTS
    # =================================================================
    if control1 == ConverterControlType.Vm_dc and control1_val is not None:
        Vdc_ref0 = float(control1_val)
    if control2 == ConverterControlType.Qac and control2_val is not None:
        Q_ref0 = float(control2_val)

    eps = vf.add_const(1e-10)
    c_half = vf.add_const(0.5)
    c_two = vf.add_const(2.0)
    c_two_over_three = vf.add_const(2.0 / 3.0)
    c_sqrt3 = vf.add_const(np.sqrt(3.0))
    c_sqrt3_over_two = vf.add_const(np.sqrt(3.0) / 2.0)
    c_three_over_two = vf.add_const(1.5)
    c_sbase = vf.add_const(max(float(sbase), 1e-12))

    event_dict = {
        P_ref: vf.add_const(P_ref0),
        Q_ref: vf.add_const(Q_ref0),
        Vdc_ref: vf.add_const(Vdc_ref0),
        omega_base: vf.add_const(2.0 * np.pi * float(fbase)),
        phi_v: vf.add_const(0.0),
        Vpk: vf.add_const(np.sqrt(2.0)),
        R_eq_p: vf.add_const(max(float(R_eq), 1e-9)),
        L_eq_p: vf.add_const(max(float(L_eq), 1e-9)),
        C_dc_p: vf.add_const(max(float(C_dc), 1e-9)),
        R_dc_p: vf.add_const(max(float(R_dc), 1e-9)),
        R_dc_term_p: vf.add_const(max(float(R_dc_term), 1e-9)),
        pll_kp_p: vf.add_const(float(pll_kp)),
        pll_ki_p: vf.add_const(float(pll_ki)),
        i_kp_p: vf.add_const(float(i_kp)),
        i_ki_p: vf.add_const(float(i_ki)),
        vdc_kp_p: vf.add_const(float(vdc_kp)),
        vdc_ki_p: vf.add_const(float(vdc_ki)),
        q_kp_p: vf.add_const(float(q_kp)),
        q_ki_p: vf.add_const(float(q_ki)),
        i_max_p: vf.add_const(max(float(i_max), 1e-6)),
        m_max_p: vf.add_const(max(float(m_max), 1e-6)),
        P_loss0_p: vf.add_const(float(P_loss0)),
        P_loss_i1_p: vf.add_const(float(P_loss_i1)),
        P_loss_i2_p: vf.add_const(float(P_loss_i2)),
        tau_meas_p: vf.add_const(max(float(tau_meas), 1e-6)),
        aw_gain_p: vf.add_const(float(aw_gain)),
        vdc_floor_p: vf.add_const(max(float(vdc_floor), 1e-6)),
    }

    P_ref_pu = P_ref / c_sbase
    Q_ref_pu = Q_ref / c_sbase
    P_loss0_pu = P_loss0_p / c_sbase
    P_loss_i1_pu = P_loss_i1_p / c_sbase
    P_loss_i2_pu = P_loss_i2_p / c_sbase
    i_leak = v_dc / R_dc_p
    v_dc_eff = sym.max(v_dc, vdc_floor_p)
    i_q_cap = sym.hard_sat(i_q_ref_u, -i_max_p, i_max_p)
    i_d_cap = sym.sqrt(sym.max(i_max_p * i_max_p - i_q_ref * i_q_ref, eps))
    v_q_cap = sym.hard_sat(v_cmd_q_u, -v_lim, v_lim)
    v_d_cap = sym.sqrt(sym.max(v_lim * v_lim - v_cmd_q * v_cmd_q, eps))

    # =================================================================
    # STATE EQUATIONS
    # =================================================================
    state_eqs = [
        # DC-link capacitor dynamics
        (-i_dc - i_dc_conv - i_leak) / C_dc_p,

        # PLL dynamics
        omega_pll,
        pll_ki_p * v_d,

        # AC-side electrical plant (equivalent converter reactor + transformer leakage)
        (v_cmd_d - v_d - R_eq_p * i_d + omega_pll * L_eq_p * i_q) / L_eq_p,
        (v_cmd_q - v_q - R_eq_p * i_q - omega_pll * L_eq_p * i_d) / L_eq_p,

        # Inner current-loop PI integrators with anti-windup back-calculation
        i_ki_p * ((i_d_ref - i_d) + aw_gain_p * (v_cmd_d - v_cmd_d_u)),
        i_ki_p * ((i_q_ref - i_q) + aw_gain_p * (v_cmd_q - v_cmd_q_u)),

        # Outer control-loop PI integrators with anti-windup back-calculation
        vdc_ki_p * ((Vdc_ref - v_dc) + aw_gain_p * (i_q_ref - i_q_ref_u)),
        q_ki_p * ((Q_ref_pu - Q_f) + aw_gain_p * (i_d_ref - i_d_ref_u)),

        # Active/reactive power measurement filters
        (P - P_f) / tau_meas_p,
        (Q - Q_f) / tau_meas_p,
    ]

    # =================================================================
    # ALGEBRAIC EQUATIONS
    # =================================================================
    algebraic_eqs = [
        # abc -> dq voltage transformation using PLL angle
        v_d - (vf.add_const(1.0 / 3.0) * (
            c_two * sym.cos(theta_pll) * v_A
            + (-sym.cos(theta_pll) - c_sqrt3 * sym.sin(theta_pll)) * v_B
            + (-sym.cos(theta_pll) + c_sqrt3 * sym.sin(theta_pll)) * v_C
        )),
        v_q - (vf.add_const(1.0 / 3.0) * (
            c_two * sym.sin(theta_pll) * v_A
            + (-sym.sin(theta_pll) + c_sqrt3 * sym.cos(theta_pll)) * v_B
            + (-sym.sin(theta_pll) - c_sqrt3 * sym.cos(theta_pll)) * v_C
        )),

        # Voltage magnitude and AC power measurements
        v_mag - sym.sqrt(v_d * v_d + v_q * v_q + eps),
        P - c_three_over_two * (v_q * i_q + v_d * i_d),
        Q - c_three_over_two * (v_q * i_d - v_d * i_q),

        # PLL algebraic output
        omega_pll - (omega_base + pll_kp_p * v_d + xi_pll),

        # Loss model and DC conversion power balance
        i_mag - sym.sqrt(i_d * i_d + i_q * i_q + eps),
        P_loss - (P_loss0_pu + P_loss_i1_pu * i_mag + P_loss_i2_pu * i_mag * i_mag),
        i_dc_conv - (P + P_loss) / v_dc_eff,

        # Outer control loops: current references before saturation
        i_q_ff - c_two_over_three * P_ref_pu / (v_mag + eps),
        i_q_ref_u - (i_q_ff + vdc_kp_p * (Vdc_ref - v_dc) + xi_vdc),
        i_d_ref_u - (q_kp_p * (Q_ref_pu - Q_f) + xi_q),

        # Current limitation block
        i_q_ref - i_q_cap,
        i_d_ref - sym.hard_sat(i_d_ref_u, -i_d_cap, i_d_cap),

        # Inner dq current controller
        v_pi_d_u - (i_kp_p * (i_d_ref - i_d) + xi_id),
        v_pi_q_u - (i_kp_p * (i_q_ref - i_q) + xi_iq),
        v_cmd_d_u - (v_d + R_eq_p * i_d - omega_pll * L_eq_p * i_q + v_pi_d_u),
        v_cmd_q_u - (v_q + R_eq_p * i_q + omega_pll * L_eq_p * i_d + v_pi_q_u),

        # Modulation / internal converter voltage limitation
        v_lim - (c_half * m_max_p * v_dc_eff),
        v_cmd_q - v_q_cap,
        v_cmd_d - sym.hard_sat(v_cmd_d_u, -v_d_cap, v_d_cap),

        # dq -> abc current injection back to the AC bus
        i_A - (i_d * sym.cos(theta_pll) + i_q * sym.sin(theta_pll)),
        i_B - ((-c_half * i_d - c_sqrt3_over_two * i_q) * sym.cos(theta_pll)
               + (c_sqrt3_over_two * i_d - c_half * i_q) * sym.sin(theta_pll)),
        i_C - ((-c_half * i_d + c_sqrt3_over_two * i_q) * sym.cos(theta_pll)
               + (-c_sqrt3_over_two * i_d - c_half * i_q) * sym.sin(theta_pll)),

        # DC terminal coupling to the external EMT DC bus
        i_dc - (v_dc - v_dc_bus) / R_dc_term_p,
    ]

    algebraic_vars = [
        i_A, i_B, i_C, i_dc,
        v_d, v_q, v_mag,
        P, Q, omega_pll,
        i_mag, P_loss, i_dc_conv,
        i_q_ff, i_q_ref_u, i_d_ref_u, i_q_ref, i_d_ref,
        v_pi_d_u, v_pi_q_u, v_cmd_d_u, v_cmd_q_u,
        v_lim, v_cmd_d, v_cmd_q,
    ]

    # =================================================================
    # INITIALIZATION EQUATIONS
    # =================================================================
    # Approximate steady-state initialization consistent with the requested
    # operating point and with the reduced pseudo-EMT structure.
    i_q0 = c_two_over_three * P_ref_pu / (Vpk + eps)
    i_d0 = c_two_over_three * Q_ref_pu / (Vpk + eps)
    P0 = c_three_over_two * Vpk * i_q0
    Q0 = c_three_over_two * Vpk * i_d0
    P_loss0_expr = P_loss0_pu + P_loss_i1_pu * sym.sqrt(i_d0 * i_d0 + i_q0 * i_q0 + eps) + P_loss_i2_pu * (i_d0 * i_d0 + i_q0 * i_q0)

    init_eqs = {
        v_dc: Vdc_ref - R_dc_term_p * ((P0 + P_loss0_expr) / (Vdc_ref + eps) + Vdc_ref / R_dc_p),
        theta_pll: phi_v,
        xi_pll: vf.add_const(0.0),
        i_d: i_d0,
        i_q: i_q0,
        xi_id: vf.add_const(0.0),
        xi_iq: vf.add_const(0.0),
        xi_vdc: vf.add_const(0.0),
        xi_q: vf.add_const(0.0),
        P_f: P0,
        Q_f: Q0,
        i_dc: -(P0 + P_loss0_expr) / (v_dc + eps) - v_dc / R_dc_p,
        v_d: vf.add_const(0.0),
        v_q: Vpk,
        v_mag: Vpk,
        P: P0,
        Q: Q0,
        omega_pll: omega_base,
        i_mag: sym.sqrt(i_d0 * i_d0 + i_q0 * i_q0 + eps),
        P_loss: P_loss0_expr,
        i_dc_conv: (P0 + P_loss0_expr) / (v_dc + eps),
        i_q_ff: i_q0,
        i_q_ref_u: i_q0,
        i_d_ref_u: i_d0,
        i_q_ref: sym.hard_sat(i_q_ref_u, -i_max_p, i_max_p),
        i_d_ref: sym.hard_sat(i_d_ref_u, -i_d_cap, i_d_cap),
        v_pi_d_u: vf.add_const(0.0),
        v_pi_q_u: vf.add_const(0.0),
        v_cmd_d_u: v_d + R_eq_p * i_d - omega_pll * L_eq_p * i_q + v_pi_d_u,
        v_cmd_q_u: v_q + R_eq_p * i_q + omega_pll * L_eq_p * i_d + v_pi_q_u,
        v_lim: c_half * m_max_p * v_dc_eff,
        v_cmd_q: sym.hard_sat(v_cmd_q_u, -v_lim, v_lim),
        v_cmd_d: sym.hard_sat(v_cmd_d_u, -v_d_cap, v_d_cap),
    }

    diff_init_eqs = {
        d_v_dc: (-i_dc - i_dc_conv - i_leak) / C_dc_p,
        d_theta_pll: omega_pll,
        d_xi_pll: pll_ki_p * v_d,
        d_i_d: (v_cmd_d - v_d - R_eq_p * i_d + omega_pll * L_eq_p * i_q) / L_eq_p,
        d_i_q: (v_cmd_q - v_q - R_eq_p * i_q - omega_pll * L_eq_p * i_d) / L_eq_p,
        d_xi_id: i_ki_p * ((i_d_ref - i_d) + aw_gain_p * (v_cmd_d - v_cmd_d_u)),
        d_xi_iq: i_ki_p * ((i_q_ref - i_q) + aw_gain_p * (v_cmd_q - v_cmd_q_u)),
        d_xi_vdc: vdc_ki_p * ((Vdc_ref - v_dc) + aw_gain_p * (i_q_ref - i_q_ref_u)),
        d_xi_q: q_ki_p * ((Q_ref_pu - Q_f) + aw_gain_p * (i_d_ref - i_d_ref_u)),
        d_P_f: (P - P_f) / tau_meas_p,
        d_Q_f: (Q - Q_f) / tau_meas_p,
    }

    converter_block = Block(
        state_eqs=state_eqs,
        state_vars=[v_dc, theta_pll, xi_pll, i_d, i_q, xi_id, xi_iq, xi_vdc, xi_q, P_f, Q_f],
        diff_vars=[d_v_dc, d_theta_pll, d_xi_pll, d_i_d, d_i_q, d_xi_id, d_xi_iq, d_xi_vdc, d_xi_q, d_P_f, d_Q_f],
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        event_dict=event_dict,
        init_eqs=init_eqs,
        diff_init_eqs=diff_init_eqs,
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, i_dc],
    )

    converter_block.external_mapping = {
        VarPowerFlowRefferenceType.v_N: None,
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: v_B,
        VarPowerFlowRefferenceType.v_C: v_C,
        VarPowerFlowRefferenceType.Vdc: v_dc_bus,
        VarPowerFlowRefferenceType.i_N: None,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,
        VarPowerFlowRefferenceType.if_N: None,
        VarPowerFlowRefferenceType.if_A: None,
        VarPowerFlowRefferenceType.if_B: None,
        VarPowerFlowRefferenceType.if_C: None,
        VarPowerFlowRefferenceType.it_N: None,
        VarPowerFlowRefferenceType.it_A: None,
        VarPowerFlowRefferenceType.it_B: None,
        VarPowerFlowRefferenceType.it_C: None,
        VarPowerFlowRefferenceType.Sf_A: None,
        VarPowerFlowRefferenceType.Sf_B: None,
        VarPowerFlowRefferenceType.Sf_C: None,
        VarPowerFlowRefferenceType.St_A: None,
        VarPowerFlowRefferenceType.St_B: None,
        VarPowerFlowRefferenceType.St_C: None,
        VarPowerFlowRefferenceType.d_v_N_f: None,
        VarPowerFlowRefferenceType.d_v_A_f: None,
        VarPowerFlowRefferenceType.d_v_B_f: None,
        VarPowerFlowRefferenceType.d_v_C_f: None,
        VarPowerFlowRefferenceType.d_v_N_t: None,
        VarPowerFlowRefferenceType.d_v_A_t: None,
        VarPowerFlowRefferenceType.d_v_B_t: None,
        VarPowerFlowRefferenceType.d_v_C_t: None,
        VarPowerFlowRefferenceType.Idc: i_dc,
        VarPowerFlowRefferenceType.P: P,
        VarPowerFlowRefferenceType.Q: Q,
        VarPowerFlowRefferenceType.phi_v: phi_v,
        VarPowerFlowRefferenceType.Vpk: Vpk,
    }

    converter_block.name = name
    templ.block = converter_block

    return templ
