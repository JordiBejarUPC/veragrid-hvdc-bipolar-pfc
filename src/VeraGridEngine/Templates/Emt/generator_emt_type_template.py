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


def get_generator_emt_template(var_factory: VarFactory, name="emt type generator template") -> EmtModelTemplate:
    """
    Get the EMT template of a generator
    :return: EmtModelTemplate
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    theta = var_factory.add_var("theta")
    omega = var_factory.add_var("omega")
    psi_d = var_factory.add_var("psi_d")
    psi_q = var_factory.add_var("psi_q")
    psi_f = var_factory.add_var("psi_f")
    psi_0 = var_factory.add_var("psi_0")

    et = var_factory.add_var("et")

    d_omega = var_factory.add_diff_var('d_omega', base_var=omega)
    d_theta = var_factory.add_diff_var('d_theta', base_var=theta)
    d_psi_d = var_factory.add_diff_var('d_psi_d', base_var=psi_d)
    d_psi_q = var_factory.add_diff_var('d_psi_q', base_var=psi_q)
    d_psi_0 = var_factory.add_diff_var('d_psi_0', base_var=psi_0)
    d_psi_f = var_factory.add_diff_var('d_psi_f', base_var=psi_f)

    d_et = var_factory.add_diff_var('d_et', base_var=et)

    i_A = var_factory.add_var("i_A")
    i_B = var_factory.add_var("i_B")
    i_C = var_factory.add_var("i_C")

    v_d = var_factory.add_var("v_d")
    v_q = var_factory.add_var("v_q")
    v_0 = var_factory.add_var("v_0")

    i_d = var_factory.add_var("i_d")
    i_q = var_factory.add_var("i_q")
    i_0 = var_factory.add_var("i_0")

    v_f = var_factory.add_var("v_f")
    i_f = var_factory.add_var("i_f")

    Te = var_factory.add_var("Te")
    Tm = var_factory.add_var("Tm")
    Pe = var_factory.add_var('Pe')
    Qe = var_factory.add_var('Qe')
    Pm = var_factory.add_var("Pm")

    # params
    freq = var_factory.add_var("Freq")
    omega_base = var_factory.add_var("omega_base")
    H = var_factory.add_var("H")
    D = var_factory.add_var("D")

    Ra = var_factory.add_var("Ra")
    La = var_factory.add_var("La")
    Lmd = var_factory.add_var("Lmd")
    Lmq = var_factory.add_var("Lmq")
    Lf = var_factory.add_var("Lf")
    Rf = var_factory.add_var("Rf")
    R0 = var_factory.add_var("R0")
    L0 = var_factory.add_var("L0")

    omega_ref = var_factory.add_var("omega_ref")
    Kp = var_factory.add_var("Kp")
    Ki = var_factory.add_var("Ki")

    v_f0 = var_factory.add_var("v_f0")  # this will disappear when the generator and the exciter model are decoupled

    # in vars
    v_A = var_factory.add_var("v_A")
    v_B = var_factory.add_var("v_B")
    v_C = var_factory.add_var("v_C")

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

            v_d - (2 / 3) * (v_A * sym.cos(theta) + v_B * sym.cos(theta - 2 * np.pi / 3) + v_C * sym.cos(theta + 2 * np.pi / 3)),  # v_d
            v_q - (2 / 3) * (v_A * sym.sin(theta) + v_B * sym.sin(theta - 2 * np.pi / 3) + v_C * sym.sin(theta + 2 * np.pi / 3)),  # v_q
            v_0 - (2 / 3) * (v_A * 0.5 + v_B * 0.5 + v_C * 0.5),  # v_0

            i_A - (i_d * sym.cos(theta) + i_q * sym.sin(theta) + i_0),  # i_A
            i_B - (i_d * sym.cos(theta - 2 * np.pi / 3) + i_q * sym.sin(theta - 2 * np.pi / 3) + i_0),  # i_B
            i_C - (i_d * sym.cos(theta + 2 * np.pi / 3) + i_q * sym.sin(theta + 2 * np.pi / 3) + i_0),  # i_C

            Te + (3 / 2) * (psi_d * i_q - psi_q * i_d),  # T_e

            Pe - (i_A * v_A + i_B * v_B + i_C * v_C),  # Pe
            Qe - (1 / np.sqrt(3)) * ((v_A - v_B) * i_C + (v_B - v_C) * i_A + (v_C - v_A) * i_B),  # Qe

            Tm - (Te + Kp * (omega_ref - omega) + Ki * et),  # Tm
            v_f - v_f0,  # v_f
            Pm - Pe  # Pm
            # Pm - omega * Tm  # Pm
        ],
        algebraic_vars=[i_d, i_q, i_f, i_0,  # v_A, v_B, v_C,
                        v_d, v_q, v_0, i_A, i_B, i_C, Te, Pe, Qe,
                        Tm, v_f, Pm],
        in_vars=[v_A, v_B, v_C],
        out_vars=[i_A, i_B, i_C],
    )

    templ.block.diff_vars = [d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_et]

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.P: Pe,
        VarPowerFlowRefferenceType.Q: Qe,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,
        # VarPowerFlowRefferenceType.theta: theta,
    }

    templ.block.event_dict = {freq: var_factory.add_const(50.0),
                       omega_base: var_factory.add_const(2 * np.pi * 50.0),
                       H: var_factory.add_const(5.0),
                       D: var_factory.add_const(2.0),
                       Ra: var_factory.add_const(0.001),
                       La: var_factory.add_const(0.15),
                       Lmd: var_factory.add_const(1.55),
                       Lmq: var_factory.add_const(1.55),
                       Lf: var_factory.add_const(0.10),
                       Rf: var_factory.add_const(0.017),
                       R0: var_factory.add_const(0.001),
                       L0: var_factory.add_const(0.14),
                       omega_ref: var_factory.add_const(1.0),
                       Kp: var_factory.add_const(2.0),
                       Ki: var_factory.add_const(2.0),
                       # v_f0: var_factory.add_const(-0.018508071106644895)}
                       v_f0: var_factory.add_const(-0.017823457188517983)}

    templ.block.init_eqs = {
        omega: var_factory.add_const(1.0),
        # TODO: add theta init eq
        Pm: Pe,
        et: var_factory.add_const(0.0),

        v_d: 2 / 3 * (sym.cos(theta) * v_A + sym.cos(theta - 2 * np.pi / 3) * v_B + sym.cos(theta + 2 * np.pi / 3) * v_C),
        v_q: 2 / 3 * (sym.sin(theta) * v_A + sym.sin(theta - 2 * np.pi / 3) * v_B + sym.sin(theta + 2 * np.pi / 3) * v_C),
        v_0: 2 / 3 * (0.5 * v_A + 0.5 * v_B + 0.5 * v_C),

        i_d: 2 / 3 * (sym.cos(theta) * i_A + sym.cos(theta - 2 * np.pi / 3) * i_B + sym.cos(theta + 2 * np.pi / 3) * i_C),
        i_q: 2 / 3 * (sym.sin(theta) * i_A + sym.sin(theta - 2 * np.pi / 3) * i_B + sym.sin(theta + 2 * np.pi / 3) * i_C),
        i_0: 2 / 3 * (0.5 * i_A + 0.5 * i_B + 0.5 * i_C),

        psi_d: (i_q * Ra - v_q) / omega,
        i_f: -((La + Lmd) * i_d - psi_d) / Lmd,
        v_f: i_f * Rf,

        psi_f: Lmd * i_d + (Lmd + Lf) * i_f,
        # psi_q: (La + Lmd) * i_q,
        psi_q: -(Ra * i_d - v_d) / omega,
        psi_0: L0 * i_0,

        Te: - (3 / 2) * (psi_d * i_q - psi_q * i_d),
        Tm: Te,
    }

    return templ

