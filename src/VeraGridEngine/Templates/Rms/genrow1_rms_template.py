# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Var, Const, VarPowerFlowRefferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, exp, imag, log, conj, real, abs

def get_genrow1_rms_template(name = "Genrow rms template") -> RmsModelTemplate:
    """
    Get the RMS template model of the Genrow
    :return: RmsModelTemplate
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name

    inputs: List[Var] = [Var("Vm_" + name),
                         Var("Va_" + name)]

    P_g: Var = Var('P_g')
    Q_g: Var = Var('Q_g')

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

    R1 = Var("R1")
    X1 = Var("X1")
    freq = Var("frequ")
    M = Var("M")
    D = Var("D")
    omega_ref = Var("omega_ref")
    Kp = Var("Kp")
    Ki = Var("Ki")
    
    vf = Var("vf")
    tm0 = Var("tm0")

    templ.block.event_dict[R1] = Const(0.0)
    templ.block.event_dict[X1] = Const(0.3 * 100.0 / 900.0)
    templ.block.event_dict[freq] = Const(50.0)
    templ.block.event_dict[M] = Const(13.0 * 9.0)
    templ.block.event_dict[D] = Const(10.0 * 9.0)
    templ.block.event_dict[omega_ref] = Const(1.0)
    templ.block.event_dict[Kp] = Const(-20)
    templ.block.event_dict[Ki] = Const(00)
    templ.block.event_dict[vf] = Const(None)
    templ.block.event_dict[tm0] = Const(None)
    
    templ.block.algebraic_vars = [P_g, Q_g, v_d, v_q, i_d, i_q, psid, psiq, te, tm, et]

    templ.block.algebraic_eqs = [
        psid - (R1 * i_q + v_q),
        psiq + (R1 * i_d + v_d),
        0 - (psid + X1 * i_d - vf),
        0 - (psiq + X1 * i_q),
        v_d - (inputs[0] * sin(delta - inputs[1])),
        v_q - (inputs[0] * cos(delta - inputs[1])),
        te - (psid * i_q - psiq * i_d),
        P_g - (v_d * i_d + v_q * i_q),
        Q_g - (v_q * i_d - v_d * i_q),
        tm - (tm0 + Kp * (omega - omega_ref) + Ki * et),
        2 * np.pi * freq * et - delta,
    ]

    templ.block.state_vars = [delta, omega]
    templ.block.state_eqs = [
                (2 * np.pi * freq) * (omega - omega_ref),
                (tm - te - D * (omega - omega_ref)) / M,
            ]
    
    templ.block.init_eqs = {
                delta: imag(
                    log((inputs[0] * exp(1j * inputs[1]) + (R1 + 1j * X1) * (
                        conj((P_g + 1j * Q_g) / (inputs[0] * exp(1j * inputs[1]))))) / (
                            abs(inputs[0] * exp(1j * inputs[1]) + (R1 + 1j * X1) * (
                                conj((P_g + 1j * Q_g) / (inputs[0] * exp(1j * inputs[1])))))))),
                omega: omega_ref,
                v_d: real((inputs[0] * exp(1j * inputs[1])) * exp(-1j * (delta - np.pi / 2))),
                v_q: imag((inputs[0] * exp(1j * inputs[1])) * exp(-1j * (delta - np.pi / 2))),
                i_d: real(
                    conj((P_g + 1j * Q_g) / (inputs[0] * exp(1j * inputs[1]))) * exp(-1j * (delta - np.pi / 2))),
                i_q: imag(
                    conj((P_g + 1j * Q_g) / (inputs[0] * exp(1j * inputs[1]))) * exp(-1j * (delta - np.pi / 2))),
                psid: R1 * i_q + v_q,
                psiq: -R1 * i_d - v_d,
                te: psid * i_q - psiq * i_d,
                tm: te,
                et: delta / (2 * np.pi * freq),
                tm0: tm,
                vf: psid + X1 * i_d
            }

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Vm: inputs[0],
        VarPowerFlowRefferenceType.Va: inputs[1],
        VarPowerFlowRefferenceType.P: P_g,
        VarPowerFlowRefferenceType.Q: Q_g
    }

    templ.block.in_vars = inputs
    templ.block.out_vars = [P_g, Q_g]

    return templ
