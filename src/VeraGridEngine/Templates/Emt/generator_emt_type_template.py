# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DeviceType


def get_generator_emt_template(vf: VarFactory, name: str="emt type generator template") -> EmtModelTemplate:
    """
    Get the EMT template of a generator
    :return: EmtModelTemplate
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name

    inputs = [vf.add_var("v_A_" + name),
              vf.add_var("v_B_" + name),
              vf.add_var("v_C_" + name)]

    # in vars
    theta = vf.add_var("theta_" + name)
    omega = vf.add_var("omega_" + name)
    psi_d = vf.add_var("psi_d_" + name)
    psi_q = vf.add_var("psi_q_" + name)
    psi_f = vf.add_var("psi_f_" + name)
    psi_0 = vf.add_var("psi_0_" + name)

    et = vf.add_var("et_" + name)

    d_omega = vf.add_diff_var('d_omega', base_var=omega)
    d_theta = vf.add_diff_var('d_theta', base_var=theta)
    d_psi_d = vf.add_diff_var('d_psi_d', base_var=psi_d)
    d_psi_q = vf.add_diff_var('d_psi_q', base_var=psi_q)
    d_psi_0 = vf.add_diff_var('d_psi_0', base_var=psi_0)
    d_psi_f = vf.add_diff_var('d_psi_f', base_var=psi_f)

    d_et = vf.add_diff_var('d_et', base_var=et)

    i_A = vf.add_var("i_A_" + name)
    i_B = vf.add_var("i_B_" + name)
    i_C = vf.add_var("i_C_" + name)

    v_d = vf.add_var("v_d_" + name)
    v_q = vf.add_var("v_q_" + name)
    v_0 = vf.add_var("v_0_" + name)

    i_d = vf.add_var("i_d_" + name)
    i_q = vf.add_var("i_q_" + name)
    i_0 = vf.add_var("i_0_" + name)

    v_f = vf.add_var("v_f_" + name)
    i_f = vf.add_var("i_f_" + name)

    Te = vf.add_var("Te_" + name)
    Tm = vf.add_var("Tm_" + name)
    Pe = vf.add_var("Pe_" + name)
    Qe = vf.add_var("Qe_" + name)
    Pm = vf.add_var("Pm_" + name)

    # --------------------------------------------------------------------------------------
    # parameters
    # --------------------------------------------------------------------------------------
    freq = vf.add_var("Freq")
    omega_base = vf.add_var("omega_base")
    H = vf.add_var("H")
    D = vf.add_var("D")

    Ra = vf.add_var("Ra")
    La = vf.add_var("La")
    Lmd = vf.add_var("Lmd")
    Lmq = vf.add_var("Lmq")
    Lf = vf.add_var("Lf")
    Rf = vf.add_var("Rf")
    R0 = vf.add_var("R0")
    L0 = vf.add_var("L0")

    omega_ref = vf.add_var("omega_ref")
    Kp = vf.add_var("Kp")
    Ki = vf.add_var("Ki")

    v_f0 = vf.add_var("v_f0")  # this will disappear when the generator and the exciter model are decoupled

    templ.block = Block(
        state_eqs=[
            v_d - Ra * i_d - omega * psi_q,
            v_q - Ra * i_q + omega * psi_d,
            v_0 - R0 * i_0,
            v_f - Rf * i_f,
            omega_base * omega,
            (Tm - Te - D * (omega - omega_ref)) / (2 * H),
            omega_base * (omega_ref - omega),  # d_et
        ],
        state_vars=[psi_d, psi_q, psi_0, psi_f, theta, omega, et], #6

        algebraic_eqs=[
            psi_d - ((Lmd + La) * i_d + Lmd * i_f),  # i_d
            psi_q - ((Lmq + La) * i_q),  # i_q
            psi_f - (Lmd * i_d + (Lmd + Lf) * i_f),  # i_f
            psi_0 - L0 * i_0,  # i_0

            v_d - (2 / 3) * (inputs[0] * sym.cos(theta) + inputs[1] * sym.cos(theta - 2 * np.pi / 3) + inputs[2] * sym.cos(theta + 2 * np.pi / 3)),  # v_d
            v_q - (2 / 3) * (inputs[0] * sym.sin(theta) + inputs[1] * sym.sin(theta - 2 * np.pi / 3) + inputs[2] * sym.sin(theta + 2 * np.pi / 3)),  # v_q
            v_0 - (2 / 3) * (inputs[0] * 0.5 + inputs[1] * 0.5 + inputs[2] * 0.5),  # v_0

            i_A - (i_d * sym.cos(theta) + i_q * sym.sin(theta) + i_0),  # i_A
            i_B - (i_d * sym.cos(theta - 2 * np.pi / 3) + i_q * sym.sin(theta - 2 * np.pi / 3) + i_0),  # i_B
            i_C - (i_d * sym.cos(theta + 2 * np.pi / 3) + i_q * sym.sin(theta + 2 * np.pi / 3) + i_0),  # i_C

            Te + (3 / 2) * (psi_d * i_q - psi_q * i_d),  # T_e

            Pe - (i_A * inputs[0] + i_B * inputs[1] + i_C * inputs[2]),  # Pe
            Qe - (1 / np.sqrt(3)) * ((inputs[0] - inputs[1]) * i_C + (inputs[1] - inputs[2]) * i_A + (inputs[2] - inputs[0]) * i_B),  # Qe

            Tm - (Te + Kp * (omega_ref - omega) + Ki * et),  # Tm
            v_f - v_f0,  # v_f
            Pm - Pe  # Pm
            # Pm - omega * Tm  # Pm
        ],
        algebraic_vars=[i_d, i_q, i_f, i_0,  # v_A, v_B, v_C,
                        v_d, v_q, v_0, i_A, i_B, i_C, Te, Pe, Qe,
                        Tm, v_f, Pm],
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C],
    )

    templ.block.diff_vars = [d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_et]

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.P: Pe,
        VarPowerFlowRefferenceType.Q: Qe,
        VarPowerFlowRefferenceType.i_N: None,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,
        VarPowerFlowRefferenceType.theta: theta
    }

    templ.block.event_dict = {freq: vf.add_const(50.0),
                       omega_base: vf.add_const(2 * np.pi * 50.0),
                       H: vf.add_const(5.0),
                       D: vf.add_const(2.0),
                       Ra: vf.add_const(0.001),
                       La: vf.add_const(0.15),
                       Lmd: vf.add_const(1.55),
                       Lmq: vf.add_const(1.55),
                       Lf: vf.add_const(0.10),
                       Rf: vf.add_const(0.017),
                       R0: vf.add_const(0.001),
                       L0: vf.add_const(0.14),
                       omega_ref: vf.add_const(1.0),
                       Kp: vf.add_const(2.0),
                       Ki: vf.add_const(2.0),
                       # v_f0: vf.add_const(-0.018508071106644895)}
                       v_f0: vf.add_const(-0.017823457188517983)} #TODO: find vf0 from exciter/governor

    templ.block.init_eqs = {
        omega: vf.add_const(1.0),
        Pm: Pe,
        et: vf.add_const(0.0),

        v_d: 2 / 3 * (sym.cos(theta) * inputs[0] + sym.cos(theta - 2 * np.pi / 3) * inputs[1] + sym.cos(theta + 2 * np.pi / 3) * inputs[2]),
        v_q: 2 / 3 * (sym.sin(theta) * inputs[0] + sym.sin(theta - 2 * np.pi / 3) * inputs[1] + sym.sin(theta + 2 * np.pi / 3) * inputs[2]),
        v_0: 2 / 3 * (0.5 * inputs[0] + 0.5 * inputs[1] + 0.5 * inputs[2]),

        i_d: 2 / 3 * (sym.cos(theta) * i_A + sym.cos(theta - 2 * np.pi / 3) * i_B + sym.cos(theta + 2 * np.pi / 3) * i_C),
        i_q: 2 / 3 * (sym.sin(theta) * i_A + sym.sin(theta - 2 * np.pi / 3) * i_B + sym.sin(theta + 2 * np.pi / 3) * i_C),
        i_0: 2 / 3 * (0.5 * i_A + 0.5 * i_B + 0.5 * i_C),

        psi_d: (i_q * Ra - v_q) / omega,
        i_f: -((La + Lmd) * i_d - psi_d) / Lmd,
        v_f: i_f * Rf,

        psi_f: Lmd * i_d + (Lmd + Lf) * i_f,
        psi_q: -(Ra * i_d - v_d) / omega,
        psi_0: L0 * i_0,

        Te: - (3 / 2) * (psi_d * i_q - psi_q * i_d),
        Tm: Te,
    }

    return templ

