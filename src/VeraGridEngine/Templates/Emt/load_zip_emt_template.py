# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np

from VeraGridEngine.enumerations import ParamPowerFlowRefferenceType, VarPowerFlowRefferenceType, DeviceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate


# --------------------------------------------------------------------------------------
# 2) ZIP / Exponential as abc current injection (phase-decoupled), without LagVars
#    We build an orthogonal voltage component vq using a SOGI (2nd-order generalized integrator).
#
#    SOGI (per phase):
#      u_dot = k*ω*(v - u) - ω*q
#      q_dot = ω*u
#    Steady state: u ≈ v, q ≈ -90deg shifted v.
#
#    Then current waveform (drawn current) to realise average P,Q is:
#      i_draw = (u*P + q*Q) / (u^2 + q^2 + eps)
#    Injected current:
#      i_inj = -i_draw
# --------------------------------------------------------------------------------------

# def get_load_ZIP_3ph_emt_template(vf: VarFactory, name: str = "ZIP_Load_EMT_3ph") -> EmtModelTemplate:
#     """
#     EMT 3-phase abc (phase-decoupled) ZIP load as CURRENT INJECTION.
#
#     - Inputs: vA, vB, vC (instantaneous phase voltages)
#     - SOGI states per phase: u, q (in-phase and quadrature fundamental components)
#     - Compute Vm = sqrt(u^2 + q^2)
#     - ZIP equations per phase (same form as RMS):
#         P = P0*(a1*(Vm/V0)^2 + a2*(Vm/V0) + a3)
#         Q = Q0*(a4*(Vm/V0)^2 + a5*(Vm/V0) + a6)
#     - Current injection (real waveform) to realise (P,Q):
#         i = (u*P + q*Q) / (u^2 + q^2 + eps)
#
#     Mean power (not instantaneous)
#     """
#
#     templ = EmtModelTemplate()
#     templ.tpe = DeviceType.LoadDevice
#     templ.name = name
#
#     # -------------------------
#     # Inputs (abc voltages)
#     # -------------------------
#     v_A = vf.add_var("v_A_" + name)
#     v_B = vf.add_var("v_B_" + name)
#     v_C = vf.add_var("v_C_" + name)
#     templ.block.in_vars = [v_A, v_B, v_C]
#
#     # -------------------------
#     # Parameters
#     # -------------------------
#     P0_A = vf.add_var("P0_A_" + name)
#     Q0_A = vf.add_var("Q0_A_" + name)
#     P0_B = vf.add_var("P0_B_" + name)
#     Q0_B = vf.add_var("Q0_B_" + name)
#     P0_C = vf.add_var("P0_C_" + name)
#     Q0_C = vf.add_var("Q0_C_" + name)
#
#     V0   = vf.add_var("V0_" + name)
#
#     a1 = vf.add_var("a1_" + name)
#     a2 = vf.add_var("a2_" + name)
#     a3 = vf.add_var("a3_" + name)
#     a4 = vf.add_var("a4_" + name)
#     a5 = vf.add_var("a5_" + name)
#     a6 = vf.add_var("a6_" + name)
#
#     f_nom  = vf.add_var("f_nom_" + name)
#     k_sogi = vf.add_var("k_sogi_" + name)
#     eps    = vf.add_var("eps_" + name)
#
#     # Defaults
#     templ.block.event_dict[P0_A] = vf.add_const(-0.0999999/3.0)
#     templ.block.event_dict[Q0_A] = vf.add_const(-0.009999999862208533/3.0)
#     templ.block.event_dict[P0_B] = vf.add_const(-0.0999999/3.0)
#     templ.block.event_dict[Q0_B] = vf.add_const(-0.009999999862208533/3.0)
#     templ.block.event_dict[P0_C] = vf.add_const(-0.0999999/3.0)
#     templ.block.event_dict[Q0_C] = vf.add_const(-0.009999999862208533/3.0)
#
#     templ.block.event_dict[V0] = vf.add_const(1.0)     # <-- set correctly for your EMT scaling
#     templ.block.event_dict[a1] = vf.add_const(0.1)
#     templ.block.event_dict[a2] = vf.add_const(0.1)
#     templ.block.event_dict[a3] = vf.add_const(0.8)
#     templ.block.event_dict[a4] = vf.add_const(0.1)
#     templ.block.event_dict[a5] = vf.add_const(0.1)
#     templ.block.event_dict[a6] = vf.add_const(0.8)
#
#     templ.block.event_dict[f_nom]  = vf.add_const(50.0)
#     templ.block.event_dict[k_sogi] = vf.add_const(1.41421356237)  # ~sqrt(2)
#     templ.block.event_dict[eps]    = vf.add_const(1e-6)
#
#     # -------------------------
#     # States (SOGI per phase)
#     # -------------------------
#     u_A = vf.add_var("u_A_" + name)
#     q_A = vf.add_var("q_A_" + name)
#     u_B = vf.add_var("u_B_" + name)
#     q_B = vf.add_var("q_B_" + name)
#     u_C = vf.add_var("u_C_" + name)
#     q_C = vf.add_var("q_C_" + name)
#
#     d_u_A = vf.add_diff_var("d_u_A_" + name, base_var=u_A)
#     d_q_A = vf.add_diff_var("d_q_A_" + name, base_var=q_A)
#     d_u_B = vf.add_diff_var("d-u_B_" + name, base_var=u_B)
#     d_q_B = vf.add_diff_var("d_q_B_" + name, base_var=q_B)
#     d_u_C = vf.add_diff_var("d_u_C_" + name, base_var=u_C)
#     d_q_C = vf.add_diff_var("d_q_C_" + name, base_var=q_C)
#
#     templ.block.state_vars = [u_A, q_A, u_B, q_B, u_C, q_C]
#     templ.block.diff_vars  = [d_u_A, d_q_A, d_u_B, d_q_B, d_u_C, d_q_C]
#
#     templ.block.state_eqs = [
#         d_u_A - (k_sogi * (2 * np.pi * f_nom) * (v_A - u_A) - (2 * np.pi * f_nom) * q_A),
#         d_q_A - ((2 * np.pi * f_nom) * u_A),
#
#         d_u_B - (k_sogi * (2 * np.pi * f_nom) * (v_B - u_B) - (2 * np.pi * f_nom) * q_B),
#         d_q_B - ((2 * np.pi * f_nom) * u_B),
#
#         d_u_C - (k_sogi * (2 * np.pi * f_nom) * (v_C - u_C) - (2 * np.pi * f_nom) * q_C),
#         d_q_C - ((2 * np.pi * f_nom) * u_C),
#     ]
#
#     # -------------------------
#     # Algebraic intermediates (explicit)
#     # -------------------------
#     VA2 = vf.add_var("VA2_" + name)
#     VB2 = vf.add_var("VB2_" + name)
#     VC2 = vf.add_var("VC2_" + name)
#     VmA = vf.add_var("VmA_" + name)
#     VmB = vf.add_var("VmB_" + name)
#     VmC = vf.add_var("VmC_" + name)
#     rA  = vf.add_var("rA_"  + name)
#     rB  = vf.add_var("rB_"  + name)
#     rC  = vf.add_var("rC_"  + name)
#
#     # Outputs per phase
#     P_A = vf.add_var("P_A_" + name)
#     Q_A = vf.add_var("Q_A_" + name)
#     P_B = vf.add_var("P_B_" + name)
#     Q_B = vf.add_var("Q_B_" + name)
#     P_C = vf.add_var("P_C_" + name)
#     Q_C = vf.add_var("Q_C_" + name)
#
#     # Currents (to stamp into KCL)
#     iA = vf.add_var("iA_" + name)
#     iB = vf.add_var("iB_" + name)
#     iC = vf.add_var("iC_" + name)
#
#     templ.block.algebraic_vars = [
#         VA2, VB2, VC2, VmA, VmB, VmC, rA, rB, rC,
#         P_A, Q_A, P_B, Q_B, P_C, Q_C,
#         iA, iB, iC
#     ]
#
#     templ.block.algebraic_eqs = [
#         # squared magnitudes from orthogonal signals
#         VA2 - (u_A*u_A + q_A*q_A),
#         VB2 - (u_B*u_B + q_B*q_B),
#         VC2 - (u_C*u_C + q_C*q_C),
#
#         # magnitude (with eps to avoid sqrt(0))
#         VmA - ((VA2 + eps) ** vf.add_const(0.5)),
#         VmB - ((VB2 + eps) ** vf.add_const(0.5)),
#         VmC - ((VC2 + eps) ** vf.add_const(0.5)),
#
#         # ratio
#         rA - (VmA / V0),
#         rB - (VmB / V0),
#         rC - (VmC / V0),
#
#         # ZIP P/Q (same form as RMS)
#         P_A - (P0_A * (a1*(rA**2.0) + a2*rA + a3)),
#         Q_A - (Q0_A * (a4*(rA**2.0) + a5*rA + a6)),
#
#         P_B - (P0_B * (a1*(rB**2.0) + a2*rB + a3)),
#         Q_B - (Q0_B * (a4*(rB**2.0) + a5*rB + a6)),
#
#         P_C - (P0_C * (a1*(rC**2.0) + a2*rC + a3)),
#         Q_C - (Q0_C * (a4*(rC**2.0) + a5*rC + a6)),
#
#         # current injection: i = (u*P + q*Q)/(u^2+q^2+eps) = (u*P+q*Q)/(V^2+eps)
#         iA - ((u_A*P_A + q_A*Q_A) / (VA2 + eps)),
#         iB - ((u_B*P_B + q_B*Q_B) / (VB2 + eps)),
#         iC - ((u_C*P_C + q_C*Q_C) / (VC2 + eps)),
#     ]
#
#     # init_eqs
#     templ.block.init_eqs = {
#         u_A: v_A,
#         q_A: vf.add_const(0.0),
#         u_B: v_B,
#         q_B: vf.add_const(0.0),
#         u_C: v_C,
#         q_C: vf.add_const(0.0),
#     }
#
#     templ.block.external_mapping = {
#         VarPowerFlowRefferenceType.P: None,
#         VarPowerFlowRefferenceType.Q: None,
#         VarPowerFlowRefferenceType.P_N: None,
#         VarPowerFlowRefferenceType.Q_N: None,
#         VarPowerFlowRefferenceType.P_A: P_A,
#         VarPowerFlowRefferenceType.Q_A: Q_A,
#         VarPowerFlowRefferenceType.P_B: P_B,
#         VarPowerFlowRefferenceType.Q_B: Q_B,
#         VarPowerFlowRefferenceType.P_C: P_C,
#         VarPowerFlowRefferenceType.Q_C: Q_C,
#         VarPowerFlowRefferenceType.i_N: None,
#         VarPowerFlowRefferenceType.i_A: iA,
#         VarPowerFlowRefferenceType.i_B: iB,
#         VarPowerFlowRefferenceType.i_C: iC,
#         VarPowerFlowRefferenceType.theta: None
#     }
#
#     templ.block.api_obj_mapping = {
#         ParamPowerFlowRefferenceType.Pl0_A: P0_A,
#         ParamPowerFlowRefferenceType.Ql0_A: Q0_A,
#         ParamPowerFlowRefferenceType.Pl0_B: P0_B,
#         ParamPowerFlowRefferenceType.Ql0_B: Q0_B,
#         ParamPowerFlowRefferenceType.Pl0_C: P0_C,
#         ParamPowerFlowRefferenceType.Ql0_C: Q0_C,
#     }
#
#     return templ


def get_load_ZIP_3ph_emt_template(vf: VarFactory, name: str = "ZIP_Load_EMT_3ph") -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    c0 = vf.add_const(0.0)
    c05 = vf.add_const(0.5)

    # Inputs
    v_A = vf.add_var("v_A_" + name)
    v_B = vf.add_var("v_B_" + name)
    v_C = vf.add_var("v_C_" + name)
    templ.block.in_vars = [v_A, v_B, v_C]

    # "Parameters" as event params
    P0_A = vf.add_var("P0_A_" + name); Q0_A = vf.add_var("Q0_A_" + name)
    P0_B = vf.add_var("P0_B_" + name); Q0_B = vf.add_var("Q0_B_" + name)
    P0_C = vf.add_var("P0_C_" + name); Q0_C = vf.add_var("Q0_C_" + name)

    V0 = vf.add_var("V0_" + name)

    a1 = vf.add_var("a1_" + name); a2 = vf.add_var("a2_" + name); a3 = vf.add_var("a3_" + name)
    a4 = vf.add_var("a4_" + name); a5 = vf.add_var("a5_" + name); a6 = vf.add_var("a6_" + name)

    f_nom  = vf.add_var("f_nom_" + name)
    k_sogi = vf.add_var("k_sogi_" + name)
    eps    = vf.add_var("eps_" + name)

    templ.block.event_dict[P0_A] = vf.add_const(-0.0999999/3.0)
    templ.block.event_dict[Q0_A] = vf.add_const(-0.009999999862208533/3.0)
    templ.block.event_dict[P0_B] = vf.add_const(-0.0999999/3.0)
    templ.block.event_dict[Q0_B] = vf.add_const(-0.009999999862208533/3.0)
    templ.block.event_dict[P0_C] = vf.add_const(-0.0999999/3.0)
    templ.block.event_dict[Q0_C] = vf.add_const(-0.009999999862208533/3.0)

    templ.block.event_dict[V0] = vf.add_const(1.0)
    templ.block.event_dict[a1] = vf.add_const(0.1)
    templ.block.event_dict[a2] = vf.add_const(0.1)
    templ.block.event_dict[a3] = vf.add_const(0.8)
    templ.block.event_dict[a4] = vf.add_const(0.1)
    templ.block.event_dict[a5] = vf.add_const(0.1)
    templ.block.event_dict[a6] = vf.add_const(0.8)

    templ.block.event_dict[f_nom]  = vf.add_const(50.0)
    templ.block.event_dict[k_sogi] = vf.add_const(1.41421356237)
    templ.block.event_dict[eps]    = vf.add_const(1e-6)

    # States (SOGI)
    u_A = vf.add_var("u_A_" + name); q_A = vf.add_var("q_A_" + name)
    u_B = vf.add_var("u_B_" + name); q_B = vf.add_var("q_B_" + name)
    u_C = vf.add_var("u_C_" + name); q_C = vf.add_var("q_C_" + name)

    d_u_A = vf.add_diff_var("d_u_A_" + name, base_var=u_A)
    d_q_A = vf.add_diff_var("d_q_A_" + name, base_var=q_A)
    d_u_B = vf.add_diff_var("d_u_B_" + name, base_var=u_B)   # <-- FIX: sin guion
    d_q_B = vf.add_diff_var("d_q_B_" + name, base_var=q_B)
    d_u_C = vf.add_diff_var("d_u_C_" + name, base_var=u_C)
    d_q_C = vf.add_diff_var("d_q_C_" + name, base_var=q_C)

    templ.block.state_vars = [u_A, q_A, u_B, q_B, u_C, q_C]
    templ.block.diff_vars  = [d_u_A, d_q_A, d_u_B, d_q_B, d_u_C, d_q_C]

    w = (2 * np.pi) * f_nom

    templ.block.state_eqs = [
        d_u_A - (k_sogi * w * (v_A - u_A) - w * q_A),
        d_q_A - (w * u_A),

        d_u_B - (k_sogi * w * (v_B - u_B) - w * q_B),
        d_q_B - (w * u_B),

        d_u_C - (k_sogi * w * (v_C - u_C) - w * q_C),
        d_q_C - (w * u_C),
    ]

    # Algebraic vars
    VA2 = vf.add_var("VA2_" + name); VB2 = vf.add_var("VB2_" + name); VC2 = vf.add_var("VC2_" + name)
    VmA = vf.add_var("VmA_" + name); VmB = vf.add_var("VmB_" + name); VmC = vf.add_var("VmC_" + name)
    rA  = vf.add_var("rA_"  + name); rB  = vf.add_var("rB_"  + name); rC  = vf.add_var("rC_"  + name)

    P_A = vf.add_var("P_A_" + name); Q_A = vf.add_var("Q_A_" + name)
    P_B = vf.add_var("P_B_" + name); Q_B = vf.add_var("Q_B_" + name)
    P_C = vf.add_var("P_C_" + name); Q_C = vf.add_var("Q_C_" + name)

    iA = vf.add_var("iA_" + name); iB = vf.add_var("iB_" + name); iC = vf.add_var("iC_" + name)

    templ.block.algebraic_vars = [
        VA2, VB2, VC2, VmA, VmB, VmC, rA, rB, rC,
        P_A, Q_A, P_B, Q_B, P_C, Q_C,
        iA, iB, iC
    ]

    templ.block.algebraic_eqs = [
        VA2 - (u_A*u_A + q_A*q_A),
        VB2 - (u_B*u_B + q_B*q_B),
        VC2 - (u_C*u_C + q_C*q_C),

        VmA - ((VA2 + eps) ** c05),
        VmB - ((VB2 + eps) ** c05),
        VmC - ((VC2 + eps) ** c05),

        rA - (VmA / V0),
        rB - (VmB / V0),
        rC - (VmC / V0),

        P_A - (P0_A * (a1*(rA**2.0) + a2*rA + a3)),
        Q_A - (Q0_A * (a4*(rA**2.0) + a5*rA + a6)),

        P_B - (P0_B * (a1*(rB**2.0) + a2*rB + a3)),
        Q_B - (Q0_B * (a4*(rB**2.0) + a5*rB + a6)),

        P_C - (P0_C * (a1*(rC**2.0) + a2*rC + a3)),
        Q_C - (Q0_C * (a4*(rC**2.0) + a5*rC + a6)),

        iA - ((u_A*P_A + q_A*Q_A) / (VA2 + eps)),
        iB - ((u_B*P_B + q_B*Q_B) / (VB2 + eps)),
        iC - ((u_C*P_C + q_C*Q_C) / (VC2 + eps)),
    ]

    # -------------------------
    # FULL init_eqs (all internal vars)
    # -------------------------
    templ.block.init_eqs = {
        # SOGI states
        u_A: v_A, q_A: c0,
        u_B: v_B, q_B: c0,
        u_C: v_C, q_C: c0,

        # algebraic chain A
        VA2: (u_A*u_A + q_A*q_A),
        VmA: ((VA2 + eps) ** c05),
        rA:  (VmA / V0),
        P_A: (P0_A * (a1*(rA**2.0) + a2*rA + a3)),
        Q_A: (Q0_A * (a4*(rA**2.0) + a5*rA + a6)),
        iA:  ((u_A*P_A + q_A*Q_A) / (VA2 + eps)),

        # algebraic chain B
        VB2: (u_B*u_B + q_B*q_B),
        VmB: ((VB2 + eps) ** c05),
        rB:  (VmB / V0),
        P_B: (P0_B * (a1*(rB**2.0) + a2*rB + a3)),
        Q_B: (Q0_B * (a4*(rB**2.0) + a5*rB + a6)),
        iB:  ((u_B*P_B + q_B*Q_B) / (VB2 + eps)),

        # algebraic chain C
        VC2: (u_C*u_C + q_C*q_C),
        VmC: ((VC2 + eps) ** c05),
        rC:  (VmC / V0),
        P_C: (P0_C * (a1*(rC**2.0) + a2*rC + a3)),
        Q_C: (Q0_C * (a4*(rC**2.0) + a5*rC + a6)),
        iC:  ((u_C*P_C + q_C*Q_C) / (VC2 + eps)),
    }

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.P: None,
        VarPowerFlowRefferenceType.Q: None,
        VarPowerFlowRefferenceType.P_N: None,
        VarPowerFlowRefferenceType.Q_N: None,
        VarPowerFlowRefferenceType.P_A: P_A,
        VarPowerFlowRefferenceType.Q_A: Q_A,
        VarPowerFlowRefferenceType.P_B: P_B,
        VarPowerFlowRefferenceType.Q_B: Q_B,
        VarPowerFlowRefferenceType.P_C: P_C,
        VarPowerFlowRefferenceType.Q_C: Q_C,
        VarPowerFlowRefferenceType.i_N: None,
        VarPowerFlowRefferenceType.i_A: iA,
        VarPowerFlowRefferenceType.i_B: iB,
        VarPowerFlowRefferenceType.i_C: iC,
        VarPowerFlowRefferenceType.theta: None
    }

    return templ