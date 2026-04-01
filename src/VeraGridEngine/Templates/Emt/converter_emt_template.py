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
    P = vf.add_var(name=f"P_{name}", reference=VarPowerFlowRefferenceType.P)
    Q = vf.add_var(name=f"Q_{name}", reference=VarPowerFlowRefferenceType.Q)

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

    Q_init_pu = Q_ref / c_sbase if regulate_q else vf.add_const(0.0)
    P_dc_init_pu = P_ref / c_sbase
    P_ac_init_pu = P_dc_init_pu + P_loss / c_sbase
    i_d_init = c_two_over_three * Q_init_pu / (Vpk + eps)
    i_q_init = c_two_over_three * P_ac_init_pu / (Vpk + eps)
    i_A_init = i_d_init * sym.cos(phi_v) + i_q_init * sym.sin(phi_v)
    i_B_init = ((-c_half * i_d_init - c_sqrt3_over_two * i_q_init) * sym.cos(phi_v)
                + ((c_sqrt3_over_two * i_d_init) - c_half * i_q_init) * sym.sin(phi_v))
    i_C_init = ((-c_half * i_d_init + c_sqrt3_over_two * i_q_init) * sym.cos(phi_v)
                + ((-c_sqrt3_over_two * i_d_init) - c_half * i_q_init) * sym.sin(phi_v))

    state_eqs = [omega_base]

    algebraic_eqs = [
        i_A - i_A_cmd,
        i_B - i_B_cmd,
        i_C - i_C_cmd,
        v_dc * i_dc + P_dc_cmd_pu,
        P - (v_A * i_A + v_B * i_B + v_C * i_C),
        Q - (1 / np.sqrt(3.0)) * ((v_A - v_B) * i_C + (v_B - v_C) * i_A + (v_C - v_A) * i_B),
    ]

    # =================================================================
    # ALGEBRAIC VARIABLES
    # =================================================================
    algebraic_vars = [i_A, i_B, i_C, i_dc, P, Q]

    # =================================================================
    # INITIALIZATION EQUATIONS
    # =================================================================
    init_eqs = {
        i_A: i_A_init,
        i_B: i_B_init,
        i_C: i_C_init,
        i_dc: -P_dc_init_pu / (Vdc_ref + eps),
        P: P_ac_init_pu,
        Q: Q_init_pu,
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
        diff_init_eqs={d_theta: omega_base},
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
        VarPowerFlowRefferenceType.P: P,
        VarPowerFlowRefferenceType.Q: Q,
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
    Build a pseudo-EMT averaged grid-following VSC with explicit DC-link
    capacitor, dq0 current dynamics and a PLL.

    Overview of the model
    ---------------------
    This is a reduced-order pseudo-EMT model of a voltage-source converter in
    grid-following mode. It is not a switching EMT model. The bridge is
    represented as an averaged internal AC voltage command behind an equivalent
    AC interface branch, coupled to an explicit DC-link capacitor.

    Numerically, the model is a DAE composed of:
    - differential states for the DC capacitor, PLL, dq currents, PI
      integrators, and filtered power measurements
    - algebraic equations for dq0 transforms, power calculation, current
      references, internal converter voltage commands, AC current injection, and
      DC terminal coupling

    Electrical interface with the AC network
    ----------------------------------------
    The AC terminal exchanges instantaneous phase voltages ``v_A``, ``v_B``,
    ``v_C`` and injected currents ``i_A``, ``i_B``, ``i_C`` with the EMT bus.
    Internally, the converter is connected to the AC bus through an equivalent
    branch parameterized by ``R_eq`` and ``L_eq``.

    ``L_eq`` is interpreted in the same normalized sense as the other EMT
    templates in this codebase, so the branch-current dynamics are scaled with
    ``omega_base / L_eq``.

    Sign conventions
    ----------------
    The implementation follows the EMT network sign conventions used by the
    framework:
    - AC-side branch currents are positive when leaving the AC bus.
    - DC-side branch current ``i_dc`` is positive when leaving the DC bus.
    - Positive ``P`` and ``Q`` therefore mean that the converter absorbs active
      and reactive power from the AC bus.
    - When the converter rectifies power from AC to DC, ``P`` is positive and
      ``i_dc`` is typically negative because current enters the DC bus.

    dq0 transformations and reference-frame convention
    --------------------------------------------------
    The dq0 convention used here is explicit and matches the requested test
    convention:
    - ``d`` is aligned with phase-a.
    - ``q`` is delayed by 90 electrical degrees with respect to ``d``.
    - zero sequence is retained explicitly through ``v_0`` and ``i_0``.

    The implemented abc -> dq0 equations are:

    ``v_d = (2/3) * [sin(theta)*v_A + sin(theta-2pi/3)*v_B + sin(theta+2pi/3)*v_C]``

    ``v_q = -(2/3) * [cos(theta)*v_A + cos(theta-2pi/3)*v_B + cos(theta+2pi/3)*v_C]``

    ``v_0 = (1/3) * (v_A + v_B + v_C)``

    The injected phase currents are reconstructed as:

    ``i_A = i_d*sin(theta) - i_q*cos(theta) + i_0``

    ``i_B = i_d*sin(theta-2pi/3) - i_q*cos(theta-2pi/3) + i_0``

    ``i_C = i_d*sin(theta+2pi/3) - i_q*cos(theta+2pi/3) + i_0``

    PLL subsystem
    -------------
    The PLL is a synchronous-reference-frame PLL. It uses the algebraic dq
    transform and drives ``v_q`` to zero:

    ``omega_pll = omega_base + pll_kp * v_q + xi_pll``

    ``d(theta_pll)/dt = omega_pll``

    ``d(xi_pll)/dt = pll_ki * v_q``

    With this convention, balanced steady state gives ``v_q ~= 0`` and active
    power is primarily carried by ``i_d`` while reactive power is primarily
    carried by ``i_q``.

    Current/reference/control logic
    -------------------------------
    The supported operating mode is intentionally minimal:
    - active-axis outer loop: ``Vm_dc``
    - reactive-axis outer loop: ``Qac``

    The active-axis loop regulates the explicit DC-link voltage through ``i_d``.
    It uses a feedforward term based on the scheduled AC-side active power,
    including the constant loss term, plus a PI correction through ``xi_vdc``.

    The reactive-axis loop regulates reactive power through ``i_q`` using a
    feedforward term and PI correction through ``xi_q``.

    The unsaturated current references are then limited by ``i_max`` and tracked
    by inner dq current PI controllers. The resulting internal converter voltage
    command is limited by a modulation magnitude ``v_lim`` proportional to
    ``m_max * v_dc``.

    Converter AC injection equations
    --------------------------------
    The AC interface current dynamics are written in the PLL dq frame as:

    ``di_d/dt = (omega_base / L_eq) * (v_d - v_cmd_d - R_eq*i_d + omega_ratio*L_eq*i_q)``

    ``di_q/dt = (omega_base / L_eq) * (v_q - v_cmd_q - R_eq*i_q - omega_ratio*L_eq*i_d)``

    where ``omega_ratio = omega_pll / omega_base``.

    Active and reactive power computation
    -------------------------------------
    Instantaneous AC power is computed as:

    ``P = 3/2 * (v_d*i_d + v_q*i_q) + 3*v_0*i_0``

    ``Q = 3/2 * (v_d*i_q - v_q*i_d)``

    ``P_f`` and ``Q_f`` are first-order filtered measurements used by the outer
    control loops.

    DC-link dynamics
    ----------------
    The converter-side DC state is ``v_dc`` and follows:

    ``C_dc * dv_dc/dt = i_dc - i_dc_conv - v_dc/R_dc``

    The loss model is:

    ``P_loss = P_loss0 + P_loss_i1*|i| + P_loss_i2*|i|^2``

    and the averaged bridge current is computed from absorbed AC power as:

    ``i_dc_conv = -(P - P_loss) / max(v_dc, vdc_floor)``

    DC terminal / DC load interaction
    ---------------------------------
    The converter-side capacitor node is coupled to the external DC bus through:

    ``i_dc = (v_dc_bus - v_dc) / R_dc_term``

    This preserves an explicit internal DC capacitor while exposing a current
    injection compatible with the existing EMT network assembly. In the target
    case, the DC load is a resistive bus injection model with negative injected
    current when it consumes power. DC-bus equilibrium is obtained when the load
    current injection and converter branch current satisfy bus KCL.

    Initialization and steady-state consistency
    -------------------------------------------
    Initialization is explicit and targeted to the balanced PF operating point.
    The model initializes:
    - ``theta_pll`` from ``phi_v``
    - ``v_d``, ``v_q``, and ``v_0`` from a balanced positive-sequence condition
    - ``i_d`` and ``i_q`` from scheduled active/reactive power
    - ``P_loss`` and ``i_dc_conv`` from the initial current magnitude
    - ``v_dc`` and ``i_dc`` from the DC terminal relation and leakage balance
    - outer-loop integrators so that the unsaturated current references are
      already coherent with the steady-state schedule

    Assumptions
    -----------
    - Averaged converter model with no switching functions or carrier.
    - Single equivalent AC interface branch.
    - Single lumped explicit DC-link capacitor.
    - Basic SRF-PLL and PI-based outer/inner control loops.
    - Current and modulation limits represented algebraically.
    - Losses represented by a simple current-dependent polynomial law.

    Limitations
    -----------
    The model omits detailed switching EMT phenomena, including PWM ripple,
    semiconductor commutation detail, dead time, detailed transformer magnetic
    effects, harmonic filtering detail, high-frequency resonances, protection
    blocking logic, and detailed DC-network dynamics. It should therefore be
    interpreted as a physically structured averaged pseudo-EMT VSC model rather
    than a full-switch EMT model.
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
    v_0 = vf.add_var(name=f"v_0_{name}")
    v_mag = vf.add_var(name=f"v_mag_{name}")
    P = vf.add_var(name=f"P_{name}")
    Q = vf.add_var(name=f"Q_{name}")
    omega_pll = vf.add_var(name=f"omega_pll_{name}")
    i_0 = vf.add_var(name=f"i_0_{name}")
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
    c_one = vf.add_const(1.0)
    c_one_over_three = vf.add_const(1.0 / 3.0)
    c_two = vf.add_const(2.0)
    c_two_over_three = vf.add_const(2.0 / 3.0)
    c_sqrt3 = vf.add_const(np.sqrt(3.0))
    c_sqrt3_over_two = vf.add_const(np.sqrt(3.0) / 2.0)
    c_three = vf.add_const(3.0)
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

    # Per-unit normalization and shared auxiliary quantities used by the power,
    # current-control, and DC-side equations.
    P_ref_pu = P_ref / c_sbase
    Q_ref_pu = Q_ref / c_sbase
    P_loss0_pu = P_loss0_p / c_sbase
    P_loss_i1_pu = P_loss_i1_p / c_sbase
    P_loss_i2_pu = P_loss_i2_p / c_sbase
    i_leak = v_dc / R_dc_p
    v_dc_eff = sym.max(v_dc, vdc_floor_p)
    theta_b = theta_pll - vf.add_const(2.0 * np.pi / 3.0)
    theta_c = theta_pll + vf.add_const(2.0 * np.pi / 3.0)
    omega_ratio = omega_pll / (omega_base + eps)

    # Feedforward terms and saturation geometry for current and modulation limits.
    i_d_ff = vf.add_var(name=f"i_d_ff_{name}")
    i_q_ff = vf.add_var(name=f"i_q_ff_{name}")
    i_d_cap = sym.hard_sat(i_d_ref_u, -i_max_p, i_max_p)
    i_q_cap = sym.sqrt(sym.max(i_max_p * i_max_p - i_d_ref * i_d_ref, eps))
    v_d_cap = sym.hard_sat(v_cmd_d_u, -v_lim, v_lim)
    v_q_cap = sym.sqrt(sym.max(v_lim * v_lim - v_cmd_d * v_cmd_d, eps))

    # Closed-form balanced operating-point quantities used by initialization.
    P_dc_ref_pu = P_ref_pu
    P_ac_ff_pu = P_dc_ref_pu + P_loss0_pu

    i_d0 = c_two_over_three * P_ac_ff_pu / (Vpk + eps)
    i_q0 = c_two_over_three * Q_ref_pu / (Vpk + eps)
    i_00 = vf.add_const(0.0)
    i_mag0 = sym.sqrt(i_d0 * i_d0 + i_q0 * i_q0 + c_three * i_00 * i_00 + eps)
    P0 = c_three_over_two * (Vpk * i_d0)
    Q0 = c_three_over_two * (Vpk * i_q0)
    P_loss0_expr = P_loss0_pu + P_loss_i1_pu * i_mag0 + P_loss_i2_pu * i_mag0 * i_mag0
    i_dc_conv0 = -(P0 - P_loss0_expr) / (Vdc_ref + eps)
    i_dc0 = (i_dc_conv0 + v_dc_bus / R_dc_p) / (c_one + R_dc_term_p / R_dc_p)
    v_dc0 = v_dc_bus - R_dc_term_p * i_dc0
    v_cmd_d0 = Vpk - R_eq_p * i_d0 + L_eq_p * i_q0
    v_cmd_q0 = -R_eq_p * i_q0 - L_eq_p * i_d0
    k_v_conv_p = vf.add_var(name=f"k_v_conv_{name}")

    # =================================================================
    # STATE EQUATIONS
    # =================================================================
    state_eqs = [
        # DC-link capacitor dynamics.
        (i_dc - i_dc_conv - i_leak) / C_dc_p,

        # PLL angle dynamics.
        omega_pll,

        # PLL integral state.
        pll_ki_p * v_q,

        # AC interface branch current dynamics in the PLL dq frame.
        (omega_base * (v_d - v_cmd_d - R_eq_p * i_d + omega_ratio * L_eq_p * i_q)) / L_eq_p,
        (omega_base * (v_q - v_cmd_q - R_eq_p * i_q - omega_ratio * L_eq_p * i_d)) / L_eq_p,

        # Inner current-controller integrators with back-calculation anti-windup.
        i_ki_p * ((i_d_ref - i_d) + aw_gain_p * (v_cmd_d - v_cmd_d_u)),
        i_ki_p * ((i_q_ref - i_q) + aw_gain_p * (v_cmd_q - v_cmd_q_u)),

        # Outer DC-voltage and reactive-power controller integrators.
        vdc_ki_p * ((Vdc_ref - v_dc) + aw_gain_p * (i_d_ref - i_d_ref_u)),
        q_ki_p * ((Q_ref_pu - Q_f) + aw_gain_p * (i_q_ref - i_q_ref_u)),

        # First-order active and reactive power measurement filters.
        (P - P_f) / tau_meas_p,
        (Q - Q_f) / tau_meas_p,
    ]

    # =================================================================
    # ALGEBRAIC EQUATIONS
    # =================================================================
    algebraic_eqs = [
        # abc to dq0 voltage transformation in the PLL reference frame.
        v_d - c_two_over_three * (
            sym.sin(theta_pll) * v_A
            + sym.sin(theta_b) * v_B
            + sym.sin(theta_c) * v_C
        ),
        v_q + c_two_over_three * (
            sym.cos(theta_pll) * v_A
            + sym.cos(theta_b) * v_B
            + sym.cos(theta_c) * v_C
        ),
        v_0 - c_one_over_three * (v_A + v_B + v_C),

        # dq voltage magnitude used by the outer-loop feedforward terms.
        v_mag - sym.sqrt(v_d * v_d + v_q * v_q + eps),

        # Zero-sequence current suppression for the balanced target case.
        i_0,

        # Instantaneous active and reactive power seen from the AC bus.
        P - (c_three_over_two * (v_d * i_d + v_q * i_q) + c_three * v_0 * i_0),
        Q - c_three_over_two * (v_d * i_q - v_q * i_d),

        # PLL algebraic frequency output.
        omega_pll - (omega_base + pll_kp_p * v_q + xi_pll),

        # Current magnitude and current-dependent converter loss model.
        i_mag - sym.sqrt(i_d * i_d + i_q * i_q + c_three * i_0 * i_0 + eps),
        P_loss - (P_loss0_pu + P_loss_i1_pu * i_mag + P_loss_i2_pu * i_mag * i_mag),

        # Averaged AC-to-DC bridge current implied by power transfer and losses.
        i_dc_conv + (P - P_loss) / v_dc_eff,

        # Outer-loop feedforward terms plus unsaturated and saturated current references.
        i_d_ff - c_two_over_three * P_ac_ff_pu / (v_mag + eps),
        i_q_ff - c_two_over_three * Q_ref_pu / (v_mag + eps),
        i_d_ref_u - (i_d_ff + vdc_kp_p * (Vdc_ref - v_dc) + xi_vdc),
        i_d_ref - i_d_cap,
        i_q_ref_u - (i_q_ff + q_kp_p * (Q_ref_pu - Q_f) + xi_q),
        i_q_ref - sym.hard_sat(i_q_ref_u, -i_q_cap, i_q_cap),

        # Inner dq current PI controller outputs.
        v_pi_d_u - (i_kp_p * (i_d_ref - i_d) + xi_id),
        v_pi_q_u - (i_kp_p * (i_q_ref - i_q) + xi_iq),

        # Internal converter voltage commands and modulation limit enforcement.
        v_cmd_d_u - (v_d - R_eq_p * i_d + omega_ratio * L_eq_p * i_q - v_pi_d_u),
        v_cmd_q_u - (v_q - R_eq_p * i_q - omega_ratio * L_eq_p * i_d - v_pi_q_u),
        k_v_conv_p - (sym.sqrt(v_cmd_d0 * v_cmd_d0 + v_cmd_q0 * v_cmd_q0 + eps) / (m_max_p * (Vdc_ref + eps))),
        v_lim - (k_v_conv_p * m_max_p * v_dc_eff),
        v_cmd_d - v_d_cap,
        v_cmd_q - sym.hard_sat(v_cmd_q_u, -v_q_cap, v_q_cap),

        # dq0 to abc reconstruction of the converter AC current injection.
        i_A - (i_d * sym.sin(theta_pll) - i_q * sym.cos(theta_pll) + i_0),
        i_B - (i_d * sym.sin(theta_b) - i_q * sym.cos(theta_b) + i_0),
        i_C - (i_d * sym.sin(theta_c) - i_q * sym.cos(theta_c) + i_0),

        # DC terminal relation between the bus voltage and the internal DC node.
        i_dc - (v_dc_bus - v_dc) / R_dc_term_p,
    ]

    algebraic_vars = [
        i_A, i_B, i_C, i_dc,
        v_d, v_q, v_0, v_mag,
        P, Q, omega_pll,
        i_0, i_mag, P_loss, i_dc_conv,
        i_d_ff, i_q_ff, i_d_ref_u, i_q_ref_u, i_d_ref, i_q_ref,
        v_pi_d_u, v_pi_q_u, v_cmd_d_u, v_cmd_q_u,
        k_v_conv_p, v_lim, v_cmd_d, v_cmd_q,
    ]

    # =================================================================
    # INITIALIZATION EQUATIONS
    # =================================================================
    init_eqs = {
        # Explicit steady-state operating point consistent with the scheduled PF
        # transfer, converter losses, and the DC terminal relation.
        v_dc: v_dc0,
        theta_pll: phi_v,
        xi_pll: vf.add_const(0.0),
        i_d: i_d0,
        i_q: i_q0,
        xi_id: vf.add_const(0.0),
        xi_iq: vf.add_const(0.0),
        xi_vdc: i_d0 - (c_two_over_three * P_ac_ff_pu / (Vpk + eps)) - vdc_kp_p * (Vdc_ref - v_dc0),
        xi_q: i_q0 - (c_two_over_three * Q_ref_pu / (Vpk + eps)) - q_kp_p * (Q_ref_pu - Q0),
        P_f: P0,
        Q_f: Q0,
        i_dc: i_dc0,
        v_d: Vpk,
        v_q: vf.add_const(0.0),
        v_0: vf.add_const(0.0),
        v_mag: Vpk,
        P: P0,
        Q: Q0,
        omega_pll: omega_base,
        i_0: vf.add_const(0.0),
        i_mag: i_mag0,
        P_loss: P_loss0_expr,
        i_dc_conv: i_dc_conv0,
        i_d_ff: c_two_over_three * P_ac_ff_pu / (Vpk + eps),
        i_q_ff: c_two_over_three * Q_ref_pu / (Vpk + eps),
        i_d_ref_u: i_d0,
        i_q_ref_u: i_q0,
        i_d_ref: i_d0,
        i_q_ref: i_q0,
        v_pi_d_u: vf.add_const(0.0),
        v_pi_q_u: vf.add_const(0.0),
        v_cmd_d_u: v_cmd_d0,
        v_cmd_q_u: v_cmd_q0,
        k_v_conv_p: sym.sqrt(v_cmd_d0 * v_cmd_d0 + v_cmd_q0 * v_cmd_q0 + eps) / (m_max_p * (Vdc_ref + eps)),
        v_lim: sym.sqrt(v_cmd_d0 * v_cmd_d0 + v_cmd_q0 * v_cmd_q0 + eps) * v_dc0 / (Vdc_ref + eps),
        v_cmd_d: v_cmd_d0,
        v_cmd_q: v_cmd_q0,
    }

    diff_init_eqs = {
        # Differential-state initialization at steady state.
        d_v_dc: vf.add_const(0.0),
        d_theta_pll: omega_base,
        d_xi_pll: vf.add_const(0.0),
        d_i_d: vf.add_const(0.0),
        d_i_q: vf.add_const(0.0),
        d_xi_id: vf.add_const(0.0),
        d_xi_iq: vf.add_const(0.0),
        d_xi_vdc: vf.add_const(0.0),
        d_xi_q: vf.add_const(0.0),
        d_P_f: vf.add_const(0.0),
        d_Q_f: vf.add_const(0.0),
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

    # External mapping seen by the EMT network assembly. The converter exchanges
    # AC branch currents with the AC bus and a branch current ``i_dc`` with the
    # DC bus while retaining the internal capacitor voltage ``v_dc`` explicitly.
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
