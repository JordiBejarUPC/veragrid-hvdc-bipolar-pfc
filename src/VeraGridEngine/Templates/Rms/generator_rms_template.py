# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, DynamicVarType
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, real, imag, conj, angle, exp, log, abs, UndefinedConst


class GeneratorRmsTemplate(RmsModelTemplate):

    def __init__(self, name: str = "rms_generator_template"):
        super().__init__(name=name)

        self._device_type: DeviceType = DeviceType.GeneratorDevice
        self._block: Block = Block()



    delta = Var("delta")
    omega = Var("omega")
    psid = Var("psid")
    psiq = Var("psiq")
    i_d = Var("i_d")
    i_q = Var("i_q")
    v_d = Var("v_d")
    v_q = Var("v_q")
    te = Var("te")
    et = Var("et")
    tm = Var("tm")
    P_g = Var("P_g")
    Q_g = Var("Q_g")

    vf = UndefinedConst()
    tm0 = UndefinedConst()

    Vm = gen_object.bus.rms_model.model.E(DynamicVarType.Vm)
    Va = gen_object.bus.rms_model.model.E(DynamicVarType.Va)

    gen_block = Block(
        state_eqs=[
            (2 * np.pi * gen_object.freq) * (omega - gen_object.omega_ref),
            (tm - te - gen_object.D * (omega - gen_object.omega_ref)) / gen_object.M,
        ],
        state_vars=[delta, omega],
        algebraic_eqs=[
            psid - (gen_object.R1 * i_q + v_q),
            psiq + (gen_object.R1 * i_d + v_d),
            0 - (psid + gen_object.X1 * i_d - vf),
            0 - (psiq + gen_object.X1 * i_q),
            v_d - (Vm * sin(delta - Va)),
            v_q - (Vm * cos(delta - Va)),
            te - (psid * i_q - psiq * i_d),
            P_g - (v_d * i_d + v_q * i_q),
            Q_g - (v_q * i_d - v_d * i_q),
            tm - (gen_object.tm0 + gen_object.Kp * (omega - gen_object.omega_ref) + gen_object.Ki * et),
            2 * np.pi * gen_object.freq * et - delta,  #
        ],
        algebraic_vars=[P_g, Q_g, v_d, v_q, i_d, i_q, psid, psiq, te, tm, et],
        init_eqs={
            delta: imag(
                log((Vm * exp(1j * Va) + (gen_object.R1 + 1j * gen_object.X1) * (conj((P_g + 1j * Q_g) / (Vm * exp(1j * Va))))) / (
                    abs(Vm * exp(1j * Va) + (gen_object.R1 + 1j * gen_object.X1) * (
                        conj((P_g + 1j * Q_g) / (Vm * exp(1j * Va)))))))),
            omega: Const(gen_object.omega_ref),
            v_d: real((Vm * exp(1j * Va)) * exp(-1j * (delta - np.pi / 2))),
            v_q: imag((Vm * exp(1j * Va)) * exp(-1j * (delta - np.pi / 2))),
            i_d: real(conj((P_g + 1j * Q_g) / (Vm * exp(1j * Va))) * exp(-1j * (delta - np.pi / 2))),
            i_q: imag(conj((P_g + 1j * Q_g) / (Vm * exp(1j * Va))) * exp(-1j * (delta - np.pi / 2))),
            psid: gen_object.R1 * i_q + v_q,
            psiq: -gen_object.R1 * i_d - v_d,
            te: psid * i_q - psiq * i_d,
            tm: te,
            et: Const(0),
        },
        init_vars=[delta, omega, et, v_d, v_q, i_d, i_q, psid, psiq, te, tm],
        fix_vars=[tm0, vf],
        fix_vars_eqs={tm0.uid: tm,
                      vf.uid: psid + gen_object.X1 * i_d},

        external_mapping={
            DynamicVarType.P: P_g,
            DynamicVarType.Q: Q_g
        }
    )
    return gen_block