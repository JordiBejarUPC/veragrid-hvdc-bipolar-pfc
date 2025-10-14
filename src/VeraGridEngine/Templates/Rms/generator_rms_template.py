# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, Expr, VarPowerFlowRefferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, real, imag, conj, angle, exp, log, abs, UndefinedConst


class GeneratorRmsTemplate(RmsModelTemplate):

    def __init__(self, name: str = "rms_generator_template"):
        super().__init__(name=name)


        self.tpe: DeviceType = DeviceType.GeneratorDevice


        self.Vm: Var = Var('')
        self.Va: Var = Var('')

        self.P_g: Var = Var('P_g')
        self.Q_g: Var = Var('Q_g')

        self.delta = Var("delta")
        self.omega = Var("omega")
        self.psid = Var("psid")
        self.psiq = Var("psiq")
        self.i_d = Var("i_d")
        self.i_q = Var("i_q")
        self.v_d = Var("v_d")
        self.v_q = Var("v_q")
        self.te = Var("te")
        self.et = Var("et")
        self.tm = Var("tm")

        self.R1 = Var("R1")
        self.X1 = Var("X1")
        self.freq = Var("frequ")
        self.M = Var("M")
        self.D = Var("D")
        self.omega_ref = Var("omega_ref")
        self.Kp = Var("Kp")
        self.Ki = Var("Ki")

    def build_template_block(self):
        """

        :return:
        """

        vf = UndefinedConst()
        tm0 = UndefinedConst()

        # vf = Var('vf')
        # tm0 = Var("tm0")

        self._block = Block(
            state_eqs=[
                (2 * np.pi * self.freq) * (self.omega - self.omega_ref),
                (self.tm - self.te - self.D * (self.omega - self.omega_ref)) / self.M,
            ],
            state_vars=[self.delta, self.omega],
            algebraic_eqs=[
                self.psid - (self.R1 * self.i_q +self. v_q),
                self.psiq + (self.R1 * self.i_d + self.v_d),
                0 - (self.psid + self.X1 * self.i_d - vf),
                0 - (self.psiq + self.X1 * self.i_q),
                self.v_d - (self.Vm * sin(self.delta - self.Va)),
                self.v_q - (self.Vm * cos(self.delta - self.Va)),
                self.te - (self.psid * self.i_q - self.psiq * self.i_d),
                self.P_g - (self.v_d * self.i_d + self.v_q * self.i_q),
                self.Q_g - (self.v_q * self.i_d - self.v_d * self.i_q),
                self.tm - (tm0 + self.Kp * (self.omega - self.omega_ref) + self.Ki * self.et),
                2 * np.pi * self.freq * self.et - self.delta,  #
            ],
            algebraic_vars=[self.P_g, self.Q_g, self.v_d, self.v_q, self.i_d, self.i_q, self.psid, psiq, te, tm, et],
            init_eqs={
                delta: imag(
                    log((self.Vm * exp(1j * self.Va) + (self.R1 + 1j * self.X1) * (
                        conj((self.P_g + 1j * self.Q_g) / (self.Vm * exp(1j * self.Va))))) / (
                            abs(self.Vm * exp(1j * self.Va) + (self.R1 + 1j * self.X1) * (
                                conj((self.P_g + 1j * self.Q_g) / (self.Vm * exp(1j * self.Va)))))))),
                omega: self.omega_ref,
                v_d: real((self.Vm * exp(1j * self.Va)) * exp(-1j * (delta - np.pi / 2))),
                v_q: imag((self.Vm * exp(1j * self.Va)) * exp(-1j * (delta - np.pi / 2))),
                i_d: real(
                    conj((self.P_g + 1j * self.Q_g) / (self.Vm * exp(1j * self.Va))) * exp(-1j * (delta - np.pi / 2))),
                i_q: imag(
                    conj((self.P_g + 1j * self.Q_g) / (self.Vm * exp(1j * self.Va))) * exp(-1j * (delta - np.pi / 2))),
                psid: self.R1 * i_q + v_q,
                psiq: -self.R1 * i_d - v_d,
                te: psid * i_q - psiq * i_d,
                tm: te,
                et: Const(0),
            },
            init_vars=[delta, omega, et, v_d, v_q, i_d, i_q, psid, psiq, te, tm],
            fix_vars=[tm0, vf],
            fix_vars_eqs={tm0.uid: tm,
                          vf.uid: psid + self.X1 * i_d},
            external_mapping={
                VarPowerFlowRefferenceType.P: self.P_g,
                VarPowerFlowRefferenceType.Q: self.Q_g
            }
        )
