# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from VeraGridEngine.Templates.Emt.emt_model_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block import Var, DiffVar, Const
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType


def get_generator_emt_template() -> EmtModelTemplate:
    """
    Get the EMT template of a generator
    :return: EmtModelTemplate
    """
    
    templ = EmtModelTemplate()

    theta = Var("theta")
    omega = Var("omega")
    psi_d = Var("psi_d")
    psi_q = Var("psi_q")
    psi_f = Var("psi_f")
    psi_0 = Var("psi_0")

    et = Var("et")

    d_omega = DiffVar('d_omega', base_var=omega)
    d_theta = DiffVar('d_theta', base_var=theta)
    d_psi_d = DiffVar('d_psi_d', base_var=psi_d)
    d_psi_q = DiffVar('d_psi_q', base_var=psi_q)
    d_psi_0 = DiffVar('d_psi_0', base_var=psi_0)
    d_psi_f = DiffVar('d_psi_f', base_var=psi_f)

    d_et = DiffVar('d_et', base_var=et)

    i_a = Var("i_a")
    i_b = Var("i_b")
    i_c = Var("i_c")

    v_d = Var("v_d")
    v_q = Var("v_q")
    v_0 = Var("v_0")

    i_d = Var("i_d")
    i_q = Var("i_q")
    i_0 = Var("i_0")
    # i_1d = Var("i_1d")
    # i_1q = Var("i_1q")

    v_f = Var("v_f")
    i_f = Var("i_f")

    Te = Var("Te")
    # et = Var("et")
    Tm = Var("Tm")
    Pe = Var('Pe')
    Qe = Var('Qe')
    Pm = Var("Pm")

    # params
    freq = Var("Freq")
    omega_base = Var("omega_base")
    H = Var("H")
    D = Var("D")

    Ra = Var("Ra")
    La = Var("La")
    Lmd = Var("Lmd")
    Lmq = Var("Lmq")
    Lf = Var("Lf")
    Rf = Var("Rf")
    R0 = Var("R0")
    L0 = Var("L0")

    omega_ref = Var("omega_ref")
    Kp = Var("Kp")
    Ki = Var("Ki")

    Rload = Var("Rload")

    v_f0 = Var("v_f0")  # this will disappear when the generator and the exciter model are decoupled

    # in vars
    v_a = Var("v_a")
    v_b = Var("v_b")
    v_c = Var("v_c")

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

            v_a - i_a * Rload,  # v_a
            v_b - i_b * Rload,  # v_b
            v_c - i_c * Rload,  # v_c

            v_d - (2 / 3) * (v_a * sym.cos(theta) + v_b * sym.cos(theta - 2 * np.pi / 3) + v_c * sym.cos(theta + 2 * np.pi / 3)),  # v_d
            v_q - (2 / 3) * (v_a * sym.sin(theta) + v_b * sym.sin(theta - 2 * np.pi / 3) + v_c * sym.sin(theta + 2 * np.pi / 3)),  # v_q
            v_0 - (2 / 3) * (v_a * 0.5 + v_b * 0.5 + v_c * 0.5),  # v_0

            i_a - (i_d * sym.cos(theta) + i_q * sym.sin(theta) + i_0),  # i_a
            i_b - (i_d * sym.cos(theta - 2 * np.pi / 3) + i_q * sym.sin(theta - 2 * np.pi / 3) + i_0),  # i_b
            i_c - (i_d * sym.cos(theta + 2 * np.pi / 3) + i_q * sym.sin(theta + 2 * np.pi / 3) + i_0),  # i_c

            Te + (3 / 2) * (psi_d * i_q - psi_q * i_d),  # T_e

            Pe - (i_a * v_a + i_b * v_b + i_c * v_c),  # Pe
            Qe - (1 / np.sqrt(3)) * ((v_a - v_b) * i_c + (v_b - v_c) * i_a + (v_c - v_a) * i_b),  # Qe

            Tm - (Te + Kp * (omega_ref - omega) + Ki * et),  # Tm
            v_f - v_f0,  # v_f
            Pm - Pe  # Pm
            # Pm - omega * Tm  # Pm
        ],
        algebraic_vars=[i_d, i_q, i_f, i_0, v_a, v_b, v_c,
                        v_d, v_q, v_0, i_a, i_b, i_c, Te, Pe, Qe,
                        Tm, v_f, Pm],
        # in_vars=[v_a, v_b, v_c],
        # out_vars=[i_a, i_b, i_c],
    )

    templ.block.diff_vars = [d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_et]

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.P: Pe,
        VarPowerFlowRefferenceType.Q: Qe,
        VarPowerFlowRefferenceType.Ia: i_a,
        VarPowerFlowRefferenceType.Ib: i_b,
        VarPowerFlowRefferenceType.Ic: i_c,
        VarPowerFlowRefferenceType.theta: theta,
    }

    templ.block.event_dict = {freq: Const(50.0),
                       omega_base: Const(2 * np.pi * 50.0),
                       H: Const(5.0),
                       D: Const(2.0),
                       Ra: Const(0.001),
                       La: Const(0.15),
                       Lmd: Const(1.55),
                       Lmq: Const(1.55),
                       Lf: Const(0.10),
                       Rf: Const(0.017),
                       R0: Const(0.001),
                       L0: Const(0.14),
                       omega_ref: Const(1.0),
                       Kp: Const(2.0),
                       Ki: Const(2.0),
                       # Rload: Const(3.0),
                       Rload: Const(1 / 0.3833),
                       # v_f0: Const(-0.018508071106644895)}
                       v_f0: Const(-0.017823457188517983)}
                       # v_f0: Const(-6.263353826055606e-05)}





    templ.block.init_eqs = {
        omega: Const(1.0),
        Pm: Pe,
        et: Const(0.0),

        v_d: 2 / 3 * (sym.cos(theta) * v_a + sym.cos(theta - 2 * np.pi / 3) * v_b + sym.cos(theta + 2 * np.pi / 3) * v_c),
        v_q: 2 / 3 * (sym.sin(theta) * v_a + sym.sin(theta - 2 * np.pi / 3) * v_b + sym.sin(theta + 2 * np.pi / 3) * v_c),
        v_0: 2 / 3 * (0.5 * v_a + 0.5 * v_b + 0.5 * v_c),

        i_d: 2 / 3 * (sym.cos(theta) * i_a + sym.cos(theta - 2 * np.pi / 3) * i_b + sym.cos(theta + 2 * np.pi / 3) * i_c),
        i_q: 2 / 3 * (sym.sin(theta) * i_a + sym.sin(theta - 2 * np.pi / 3) * i_b + sym.sin(theta + 2 * np.pi / 3) * i_c),
        i_0: 2 / 3 * (0.5 * i_a + 0.5 * i_b + 0.5 * i_c),

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

