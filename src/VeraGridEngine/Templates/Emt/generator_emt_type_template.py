# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from VeraGridEngine import MultiCircuit
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DeviceType

def get_generator_emt_template(grid: MultiCircuit, gen: Generator, name: str = "emt_type_generator_template") -> EmtModelTemplate:
    """
    EMT type machine model
    :param grid: MultiCircuit
    :param gen: Generator object to apply the template
    :param name: string to identify the generator and model
    :return: EmtModelTemplate
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name

    vf: VarFactory = grid.var_factory

    # --------------------------------------------------------------------------------------
    # Inputs: instantaneous abc terminal voltages in pu (at bus)
    # --------------------------------------------------------------------------------------
    inputs = [
        vf.add_var("v_A_" + name),
        vf.add_var("v_B_" + name),
        vf.add_var("v_C_" + name),
    ]
    # --------------------------------------------------------------------------------------
    # States (pu, except theta [rad])
    # --------------------------------------------------------------------------------------
    theta = vf.add_var("theta_" + name)  # electrical angle [rad]
    omega = vf.add_var("omega_" + name)  # speed [pu]
    psi_d = vf.add_var("psi_d_" + name)  # flux linkages [pu] on psi_base = Vbase/omega_base
    psi_q = vf.add_var("psi_q_" + name)
    psi_f = vf.add_var("psi_f_" + name)
    psi_0 = vf.add_var("psi_0_" + name)
    et    = vf.add_var("et_" + name)     # PI integrator state (units: pu*s or equivalent)

    # Diff vars (derivatives)
    d_omega = vf.add_diff_var(name = f"d_omega_{name}", base_var=omega)
    d_theta = vf.add_diff_var(name = f"d_theta_{name}", base_var=theta)
    d_psi_d = vf.add_diff_var(name = f"d_psi_d_{name}", base_var=psi_d)
    d_psi_q = vf.add_diff_var(name = f"d_psi_q_{name}", base_var=psi_q)
    d_psi_0 = vf.add_diff_var(name = f"d_psi_0_{name}", base_var=psi_0)
    d_psi_f = vf.add_diff_var(name = f"d_psi_f_{name}", base_var=psi_f)
    d_et    = vf.add_diff_var(name = f"d_et_{name}", base_var=et)

    # --------------------------------------------------------------------------------------
    # Algebraic eqs
    # --------------------------------------------------------------------------------------
    i_A = vf.add_var("i_A_" + name)
    i_B = vf.add_var("i_B_" + name)
    i_C = vf.add_var("i_C_" + name)

    # dq0 voltages
    v_d = vf.add_var("v_d_" + name)
    v_q = vf.add_var("v_q_" + name)
    v_0 = vf.add_var("v_0_" + name)

    # dq0 currents
    i_d = vf.add_var("i_d_" + name)
    i_q = vf.add_var("i_q_" + name)
    i_0 = vf.add_var("i_0_" + name)

    # field
    v_f = vf.add_var("v_f_" + name)
    i_f = vf.add_var("i_f_" + name)

    # powers/torques
    Te = vf.add_var("Te_" + name)
    Tm = vf.add_var("Tm_" + name)
    Pe = vf.add_var("Pe_" + name)
    Qe = vf.add_var("Qe_" + name)
    Pm = vf.add_var("Pm_" + name)

    # --------------------------------------------------------------------------------------
    # Parameters
    # --------------------------------------------------------------------------------------
    omega_base = vf.add_var("omega_base")
    H = vf.add_var("H")
    D = vf.add_var("D")

    Ra  = vf.add_var("Ra")
    La  = vf.add_var("La")
    Lmd = vf.add_var("Lmd")
    Lmq = vf.add_var("Lmq")
    Lf  = vf.add_var("Lf")
    Rf  = vf.add_var("Rf")
    R0  = vf.add_var("R0")
    L0  = vf.add_var("L0")

    omega_ref = vf.add_var("omega_ref")  # pu
    Kp        = vf.add_var("Kp")
    Ki        = vf.add_var("Ki")

    v_f0 = vf.add_var("v_f0")  # temporary fixed exciter output

    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            -v_d - Ra * i_d + omega * psi_q,
            -v_q - Ra * i_q - omega * psi_d,
            -v_0 - R0 * i_0,
            v_f - Rf * i_f,
            omega,
            (Tm - Te - D * (omega - omega_ref)) / (2 * H),
            (omega_ref - omega),
        ],
        state_vars=[psi_d, psi_q, psi_0, psi_f, theta, omega, et],

        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            psi_d - (Lmd * i_f - (Lmd + La) * i_d),
            psi_q - (-(Lmq + La) * i_q),
            psi_0 - (-L0 * i_0),
            psi_f - ((Lmd + Lf) * i_f - Lmd * i_d),
            v_d - (2 / 3) * (
                    inputs[0] * sym.sin(theta) +
                    inputs[1] * sym.sin(theta - 2 * np.pi / 3) +
                    inputs[2] * sym.sin(theta + 2 * np.pi / 3)),
            v_q - (2 / 3) * (
                    inputs[0] * sym.cos(theta) +
                    inputs[1] * sym.cos(theta - 2 * np.pi / 3) +
                    inputs[2] * sym.cos(theta + 2 * np.pi / 3)),
            v_0 - (1 / 3) * (inputs[0] + inputs[1] + inputs[2]),
            i_A - (i_d * sym.cos(theta) - i_q * sym.sin(theta) + i_0),
            i_B - (i_d * sym.cos(theta - 2 * np.pi / 3) - i_q * sym.sin(theta - 2 * np.pi / 3) + i_0),
            i_C - (i_d * sym.cos(theta + 2 * np.pi / 3) - i_q * sym.sin(theta + 2 * np.pi / 3) + i_0),
            Te - (3 / 2) * (psi_d * i_q - psi_q * i_d),
            Pe - (i_A * inputs[0] + i_B * inputs[1] + i_C * inputs[2]),
            Qe - (1 / np.sqrt(3)) * ((inputs[0] - inputs[1]) * i_C +
                                     (inputs[1] - inputs[2]) * i_A +
                                     (inputs[2] - inputs[0]) * i_B),
            Tm - (Te + Kp * (omega_ref - omega) + Ki * et),
            v_f - v_f0,
            Pm - Tm * omega,
        ],
        algebraic_vars=[
            i_d, i_q, i_0, i_f,
            v_d, v_q, v_0,
            i_A, i_B, i_C,
            Te, Pe, Qe,
            Tm, v_f, Pm
        ],
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C],
    )

    templ.block.diff_vars = [d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_et]

    # --------------------------------------------------------------------------------------
    # external mapping
    # --------------------------------------------------------------------------------------

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.P: Pe,
        VarPowerFlowRefferenceType.Q: Qe,
        VarPowerFlowRefferenceType.P_N: None,
        VarPowerFlowRefferenceType.Q_N: None,
        VarPowerFlowRefferenceType.P_A: None,
        VarPowerFlowRefferenceType.Q_A: None,
        VarPowerFlowRefferenceType.P_B: None,
        VarPowerFlowRefferenceType.Q_B: None,
        VarPowerFlowRefferenceType.P_C: None,
        VarPowerFlowRefferenceType.Q_C: None,
        VarPowerFlowRefferenceType.i_N: None,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,
        VarPowerFlowRefferenceType.theta: theta,
    }

    # --------------------------------------------------------------------------------------
    # Event dict (constants)
    # --------------------------------------------------------------------------------------
    w = 2 * np.pi * grid.fBase
    # Ra = 0.001
    Ld = gen.X1
    La_num = 0.15
    Lmd_num = Ld - La_num

    templ.block.event_dict = {
        omega_base: vf.add_const(w),
        H:          vf.add_const(5.0),
        D:          vf.add_const(2.0),
        Ra:         vf.add_const(gen.R1),
        La:         vf.add_const(La_num),
        Lmd:        vf.add_const(Lmd_num),
        Lmq:        vf.add_const(1.55),
        Lf:         vf.add_const(0.10),
        Rf:         vf.add_const(0.017),
        R0:         vf.add_const(0.001),
        L0:         vf.add_const(0.14),
        omega_ref:  vf.add_const(1.0),
        Kp:         vf.add_const(2.0),
        Ki:         vf.add_const(2.0),
        v_f0:       vf.add_const(-0.015522),
    }

    # --------------------------------------------------------------------------------------
    # INIT EQUATIONS
    # --------------------------------------------------------------------------------------

    templ.block.init_eqs = {
        omega: vf.add_const(1.0),
        et: vf.add_const(0.0),
        v_d: 2 / 3 * (sym.sin(theta) * inputs[0] +
                      sym.sin(theta - 2 * np.pi / 3) * inputs[1] +
                      sym.sin(theta + 2 * np.pi / 3) * inputs[2]),
        v_q: 2 / 3 * (sym.cos(theta) * inputs[0] +
                      sym.cos(theta - 2 * np.pi / 3) * inputs[1] +
                      sym.cos(theta + 2 * np.pi / 3) * inputs[2]),
        i_d: 2 / 3 * (sym.sin(theta) * i_A +
                      sym.sin(theta - 2 * np.pi / 3) * i_B +
                      sym.sin(theta + 2 * np.pi / 3) * i_C),
        i_q: 2 / 3 * (sym.cos(theta) * i_A +
                      sym.cos(theta - 2 * np.pi / 3) * i_B +
                      sym.cos(theta + 2 * np.pi / 3) * i_C),
        psi_q: (v_d + Ra * i_d),
        psi_d: -(v_q + Ra * i_q),
        i_f: (psi_d + (Lmd + La) * i_d) / Lmd,
        v_f: i_f * Rf,
        psi_f: (Lmd + Lf) * i_f - Lmd * i_d,
        Te: (3 / 2) * (psi_d * i_q - psi_q * i_d),
        Tm: Te,
        Pm: Tm * omega,
    }

    # --------------------------------------------------------------------------------------
    # DIFF INIT EQS
    # --------------------------------------------------------------------------------------
    c0 = vf.add_const(0.0)
    templ.block.diff_init_eqs = {
        d_theta: omega,
        d_et: (omega_ref - omega),
        d_omega: c0,
        d_psi_d: c0,
        d_psi_q: c0,
        d_psi_0: c0,
        d_psi_f: c0,
    }

    return templ

