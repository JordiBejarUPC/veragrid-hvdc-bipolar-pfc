# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, Expr, DynamicVarType
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, real, imag, conj, angle, exp, log, abs, UndefinedConst


class GeneratorRmsTemplate(RmsModelTemplate):

    def __init__(self, name: str = "rms_generator_template"):
        super().__init__(name=name)

        self.name = name
        # self._block = Block()
        self._device_type: DeviceType = DeviceType.GeneratorDevice
        self.parameters: List[str] = ['R1', 'X1', 'freq', 'M', 'D', 'omega_ref', 'Kp', 'Ki']

        self.event_parameters: List[Var] = list()
        self.event_parameters_eqs: List[Expr] = list()

        self.Vm: Var = Var('')
        self.Va: Var = Var('')

        self.P_g: Var = Var('P_g')
        self.Q_g: Var = Var('Q_g')

        self.R1 = Const(1e-20)
        self.X1 = Const(1e-20)
        self.freq = Const(60.0)
        self.M = Const(1.0 / 100.0 * 900.0)  # from Machine to System base
        self.D = Const(4.0 / 100.0 * 900.0)  # from Machine to System base
        self.omega_ref = Const(1.0)
        self.Kp = Const(0.0)
        self.Ki = Const(0.0)

    def build_template_block(self):

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


        vf = UndefinedConst()
        tm0 = UndefinedConst()

        # vf = Var('vf')
        # tm0 = Var("tm0")

        self._block = Block(
            state_eqs=[
                (2 * np.pi * self.freq) * (omega - self.omega_ref),
                (tm - te - self.D * (omega - self.omega_ref)) / self.M,
            ],
            state_vars=[delta, omega],
            algebraic_eqs=[
                psid - (self.R1 * i_q + v_q),
                psiq + (self.R1 * i_d + v_d),
                0 - (psid + self.X1 * i_d - vf),
                0 - (psiq + self.X1 * i_q),
                v_d - (self.Vm * sin(delta - self.Va)),
                v_q - (self.Vm * cos(delta - self.Va)),
                te - (psid * i_q - psiq * i_d),
                self.P_g - (v_d * i_d + v_q * i_q),
                self.Q_g - (v_q * i_d - v_d * i_q),
                tm - (tm0 + self.Kp * (omega - self.omega_ref) + self.Ki * et),
                2 * np.pi * self.freq * et - delta,  #
            ],
            algebraic_vars=[self.P_g, self.Q_g, v_d, v_q, i_d, i_q, psid, psiq, te, tm, et],
            init_eqs={
                delta: imag(
                    log((self.Vm * exp(1j * self.Va) + (self.R1 + 1j * self.X1) * (conj((self.P_g + 1j * self.Q_g) / (self.Vm * exp(1j * self.Va))))) / (
                    abs(self.Vm * exp(1j * self.Va) + (self.R1 + 1j * self.X1) * (
                        conj((self.P_g + 1j * self.Q_g) / (self.Vm * exp(1j * self.Va)))))))),
                omega: self.omega_ref,
                v_d: real((self.Vm * exp(1j * self.Va)) * exp(-1j * (delta - np.pi / 2))),
                v_q: imag((self.Vm * exp(1j * self.Va)) * exp(-1j * (delta - np.pi / 2))),
                i_d: real(conj((self.P_g + 1j * self.Q_g) / (self.Vm * exp(1j * self.Va))) * exp(-1j * (delta - np.pi / 2))),
                i_q: imag(conj((self.P_g + 1j * self.Q_g) / (self.Vm * exp(1j * self.Va))) * exp(-1j * (delta - np.pi / 2))),
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
                DynamicVarType.P: self.P_g,
                DynamicVarType.Q: self.Q_g
            }
        )