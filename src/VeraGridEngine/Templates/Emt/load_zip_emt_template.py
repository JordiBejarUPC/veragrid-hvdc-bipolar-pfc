# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np

from VeraGridEngine import MultiCircuit
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DeviceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate

def get_load_ZIP_3ph_emt_template(grid : MultiCircuit, load: Load,  name: str = "ZIP_Load_EMT_3ph") -> EmtModelTemplate:
    """
    ZIP load model template in the abc domain
    :param grid: MultiCircuit
    :param load: Load object to apply the template
    :param name: string to identify the load and model
    :return: EmtModelTemplate
    """


    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    vf: VarFactory = grid.rms_var_factory
    fbase: float = grid.fBase
    sbase: float = grid.Sbase

    # Symbolic constants for math operations
    c0 = vf.add_const(0.0)
    c2 = vf.add_const(2.0)
    c05 = vf.add_const(0.5)

    # Inputs: Instantaneous phase voltages from the grid
    v_A = vf.add_var("v_A_" + name)
    v_B = vf.add_var("v_B_" + name)
    v_C = vf.add_var("v_C_" + name)
    d_v_A = vf.add_diff_var(name=f"d_v_A_{name}", base_var=v_A)
    d_v_B = vf.add_diff_var(name=f"d_v_B_{name}", base_var=v_B)
    d_v_C = vf.add_diff_var(name=f"d_v_C_{name}", base_var=v_C)
    templ.block.in_vars = [v_A, v_B, v_C, d_v_A, d_v_B, d_v_C]

    # Parameters: Nominal power (P0, Q0) and Voltage (V0)
    P0_A = vf.add_var("P0_A_" + name)
    Q0_A = vf.add_var("Q0_A_" + name)
    P0_B = vf.add_var("P0_B_" + name)
    Q0_B = vf.add_var("Q0_B_" + name)
    P0_C = vf.add_var("P0_C_" + name)
    Q0_C = vf.add_var("Q0_C_" + name)
    V0 = vf.add_var("V0_" + name)

    # ZIP coefficients and SOGI filter parameters
    a1 = vf.add_var("a1_" + name)
    a2 = vf.add_var("a2_" + name)
    a3 = vf.add_var("a3_" + name)
    a4 = vf.add_var("a4_" + name)
    a5 = vf.add_var("a5_" + name)
    a6 = vf.add_var("a6_" + name)
    k_sogi = vf.add_var("k_sogi_" + name)
    eps = vf.add_var("eps_" + name)
    omega = vf.add_var("omega_" + name)

    PA0 = load.Pa / sbase
    QA0 = load.Qa / sbase
    PB0 = load.Pb / sbase
    QB0 = load.Qb / sbase
    PC0 = load.Pc / sbase
    QC0 = load.Qc / sbase
    # Fundamental angular frequency
    w_const = (2.0 * np.pi) * fbase
    templ.block.event_dict[P0_A] = vf.add_const(PA0)
    templ.block.event_dict[Q0_A] = vf.add_const(QA0)
    templ.block.event_dict[P0_B] = vf.add_const(PB0)
    templ.block.event_dict[Q0_B] = vf.add_const(QB0)
    templ.block.event_dict[P0_C] = vf.add_const(PC0)
    templ.block.event_dict[Q0_C] = vf.add_const(QC0)
    templ.block.event_dict[V0] = vf.add_const(np.sqrt(2))
    templ.block.event_dict[k_sogi] = vf.add_const(np.sqrt(2))
    templ.block.event_dict[eps] = vf.add_const(1e-12)
    templ.block.event_dict[omega] = vf.add_const(w_const)

    # Default ZIP coefficients: Constant Power behavior (a3=1, a6=1)
    for p in [a1, a2, a4, a5]: templ.block.event_dict[p] = c0
    for p in [a3, a6]: templ.block.event_dict[p] = vf.add_const(1.0)

    # State Variables (SOGI output and its quadrature signal)
    u_A = vf.add_var("u_A_" + name)
    q_A = vf.add_var("q_A_" + name)
    u_B = vf.add_var("u_B_" + name)
    q_B = vf.add_var("q_B_" + name)
    u_C = vf.add_var("u_C_" + name)
    q_C = vf.add_var("q_C_" + name)
    templ.block.state_vars = [u_A, q_A, u_B, q_B, u_C, q_C]

    # Differential Variables (Derivatives)
    d_u_A = vf.add_diff_var("d_u_A_" + name, base_var=u_A)
    d_q_A = vf.add_diff_var("d_q_A_" + name, base_var=q_A)
    d_u_B = vf.add_diff_var("d_u_B_" + name, base_var=u_B)
    d_q_B = vf.add_diff_var("d_q_B_" + name, base_var=q_B)
    d_u_C = vf.add_diff_var("d_u_C_" + name, base_var=u_C)
    d_q_C = vf.add_diff_var("d_q_C_" + name, base_var=q_C)
    templ.block.diff_vars = [d_u_A, d_q_A, d_u_B, d_q_B, d_u_C, d_q_C]

    # State Equations: SOGI Dynamics (Standard Orthogonal Filter)
    templ.block.state_eqs = [
        (k_sogi * omega * (v_A - u_A) - omega * q_A),
        (omega * u_A),

        (k_sogi * omega * (v_B - u_B) - omega * q_B),
        (omega * u_B),

        (k_sogi * omega * (v_C - u_C) - omega * q_C),
        (omega * u_C),
    ]

    # Algebraic Variables for ZIP model
    VA2 = vf.add_var("VA2_" + name)
    VB2 = vf.add_var("VB2_" + name)
    VC2 = vf.add_var("VC2_" + name)
    VmA = vf.add_var("VmA_" + name)
    VmB = vf.add_var("VmB_" + name)
    VmC = vf.add_var("VmC_" + name)
    rA = vf.add_var("rA_" + name)
    rB = vf.add_var("rB_" + name)
    rC = vf.add_var("rC_" + name)
    P_A = vf.add_var("P_A_" + name)
    Q_A = vf.add_var("Q_A_" + name)
    P_B = vf.add_var("P_B_" + name)
    Q_B = vf.add_var("Q_B_" + name)
    P_C = vf.add_var("P_C_" + name)
    Q_C = vf.add_var("Q_C_" + name)
    i_A = vf.add_var("i_A_" + name)
    i_B = vf.add_var("i_B_" + name)
    i_C = vf.add_var("i_C_" + name)

    templ.block.algebraic_vars = [
        VA2, VB2, VC2, VmA, VmB, VmC, rA, rB, rC,
        P_A, Q_A, P_B, Q_B, P_C, Q_C, i_A, i_B, i_C
    ]

    # Algebraic Equations: Definitions for magnitudes and the ZIP polynomial
    templ.block.algebraic_eqs = [
        # Magnitudes squared (u^2 + q^2)
        VA2 - (u_A ** 2 + q_A ** 2),
        VB2 - (u_B ** 2 + q_B ** 2),
        VC2 - (u_C ** 2 + q_C ** 2),
        # Peak amplitudes
        VmA - ((VA2 + eps) ** c05),
        VmB - ((VB2 + eps) ** c05),
        VmC - ((VC2 + eps) ** c05),
        # Voltage ratios (V/V_nominal)
        rA - (VmA / V0),
        rB - (VmB / V0),
        rC - (VmC / V0),
        # ZIP Polynomials for P and Q
        P_A + (P0_A * (a1 * rA ** 2 + a2 * rA + a3)),
        Q_A + (Q0_A * (a4 * rA ** 2 + a5 * rA + a6)),
        P_B + (P0_B * (a1 * rB ** 2 + a2 * rB + a3)),
        Q_B + (Q0_B * (a4 * rB ** 2 + a5 * rB + a6)),
        P_C + (P0_C * (a1 * rC ** 2 + a2 * rC + a3)),
        Q_C + (Q0_C * (a4 * rC ** 2 + a5 * rC + a6)),

        # P_A - (P0_A * (a1 * rA ** 2 + a2 * rA + a3)),
        # Q_A - (Q0_A * (a4 * rA ** 2 + a5 * rA + a6)),
        # P_B - (P0_B * (a1 * rB ** 2 + a2 * rB + a3)),
        # Q_B - (Q0_B * (a4 * rB ** 2 + a5 * rB + a6)),
        # P_C - (P0_C * (a1 * rC ** 2 + a2 * rC + a3)),
        # Q_C - (Q0_C * (a4 * rC ** 2 + a5 * rC + a6)),
        # Current injection: i = 2 * (u*P + q*Q) / V_peak^2
        i_A + (c2 * (u_A * (-P_A) + q_A * (-Q_A)) / (VA2 + eps)),
        i_B + (c2 * (u_B * (-P_B) + q_B * (-Q_B)) / (VB2 + eps)),
        i_C + (c2 * (u_C * (-P_C) + q_C * (-Q_C)) / (VC2 + eps)),
    ]

    templ.block.init_eqs = {
        u_A: v_A,
        u_B: v_B,
        u_C: v_C,
        q_A: -d_v_A / omega,
        q_B: -d_v_B / omega,
        q_C: -d_v_C / omega,
        VA2: (u_A ** 2 + q_A ** 2), VmA: ((VA2 + eps) ** c05), rA: (VmA / V0),
        VB2: (u_B ** 2 + q_B ** 2), VmB: ((VB2 + eps) ** c05), rB: (VmB / V0),
        VC2: (u_C ** 2 + q_C ** 2), VmC: ((VC2 + eps) ** c05), rC: (VmC / V0),
    }

    templ.block.diff_init_eqs = {
        d_u_A: d_v_A,
        d_q_A: omega * u_A,
        d_u_B: d_v_B,
        d_q_B: omega * u_B,
        d_u_C: d_v_C,
        d_q_C: omega * u_C,
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
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,
        VarPowerFlowRefferenceType.theta: None
    }

    return templ
