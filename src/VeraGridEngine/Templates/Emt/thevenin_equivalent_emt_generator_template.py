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

def get_generator_thevenin_rl_emt_template(
        grid: MultiCircuit,
        gen: Generator,
        name: str = "emt_thevenin_eq_generator_template"
) -> EmtModelTemplate:
    """
    Simple EMT three-phase Thevenin generator behind series R-X.

    Purpose:
        This is a robust test injection model to validate the EMT injection interface
        (bus KCL coupling, initialization from PF, current sign conventions, etc.)
        without the full complexity of a synchronous machine model.

    Sign convention:
        Currents i_A, i_B, i_C are positive when injected from the generator into the bus.
        This matches the sign convention already used by the rest of the EMT injection interface.

    Inputs:
        v_A, v_B, v_C : instantaneous bus terminal voltages [pu]

    States:
        i_A, i_B, i_C : phase currents injected into the bus [pu]
        theta         : absolute electrical angle of the internal source [rad]

    Differential equations:
        di/dt = omega_base * (e - R_s i - v_bus) / X_s
        dtheta/dt = omega_base

    Initialization from PF:
        The model expects the generic PF->EMT init layer to provide:
            - i_A, i_B, i_C  (instantaneous current values at t=0)
            - phi_v          (positive-sequence voltage angle)
            - phi            (current angle relative to positive-sequence voltage)
            - Vpk            (positive-sequence voltage peak magnitude)
            - Ipk            (positive-sequence current peak magnitude)

        From those values, the model computes:
            - delta : internal source angle relative to terminal positive-sequence voltage
            - Epk   : internal source peak magnitude
            - theta = phi_v + delta

        using the Thevenin steady-state relation:
            E = V + (R + jX) I

    :param grid: MultiCircuit
    :param gen: Generator object
    :param name: Model name
    :return: EmtModelTemplate
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name

    vf: VarFactory = grid.emt_var_factory

    # ----------------------------------------------------------------------------------
    # Constants for symbolic expressions
    # ----------------------------------------------------------------------------------
    c0 = vf.add_const(0.0)
    c05 = vf.add_const(0.5)

    # ----------------------------------------------------------------------------------
    # Inputs: bus terminal instantaneous phase voltages
    # ----------------------------------------------------------------------------------
    v_A = vf.add_var("v_A_" + name)
    v_B = vf.add_var("v_B_" + name)
    v_C = vf.add_var("v_C_" + name)
    inputs = [v_A, v_B, v_C]

    # ----------------------------------------------------------------------------------
    # States
    # ----------------------------------------------------------------------------------
    i_A = vf.add_var("i_A_" + name)
    i_B = vf.add_var("i_B_" + name)
    i_C = vf.add_var("i_C_" + name)
    theta = vf.add_var("theta_" + name)

    # Diff vars
    d_i_A = vf.add_diff_var(name=f"d_i_A_{name}", base_var=i_A)
    d_i_B = vf.add_diff_var(name=f"d_i_B_{name}", base_var=i_B)
    d_i_C = vf.add_diff_var(name=f"d_i_C_{name}", base_var=i_C)
    d_theta = vf.add_diff_var(name=f"d_theta_{name}", base_var=theta)

    # ----------------------------------------------------------------------------------
    # Algebraic vars
    # ----------------------------------------------------------------------------------
    e_A = vf.add_var("e_A_" + name)
    e_B = vf.add_var("e_B_" + name)
    e_C = vf.add_var("e_C_" + name)

    Pe = vf.add_var("Pe_" + name)
    Qe = vf.add_var("Qe_" + name)

    # ----------------------------------------------------------------------------------
    # Parameters
    # ----------------------------------------------------------------------------------
    omega_base = vf.add_var("omega_base")
    R_s = vf.add_var("R_s")
    X_s = vf.add_var("X_s")

    # Init-only / PF-derived auxiliary quantities
    phi_v = vf.add_var("phi_v_" + name)
    phi = vf.add_var("phi_" + name)
    Vpk = vf.add_var("Vpk_" + name)
    Ipk = vf.add_var("Ipk_" + name)

    # Init-only internal auxiliary quantities
    delta = vf.add_var("delta_" + name)
    Epk = vf.add_var("Epk_" + name)

    # ----------------------------------------------------------------------------------
    # Block
    # ----------------------------------------------------------------------------------
    templ.block = Block(
        state_eqs=[
            omega_base * (e_A - R_s * i_A - v_A) / X_s,
            omega_base * (e_B - R_s * i_B - v_B) / X_s,
            omega_base * (e_C - R_s * i_C - v_C) / X_s,
            omega_base,
        ],
        state_vars=[i_A, i_B, i_C, theta],

        algebraic_eqs=[
            e_A - Epk * sym.sin(theta),
            e_B - Epk * sym.sin(theta - 2 * np.pi / 3),
            e_C - Epk * sym.sin(theta + 2 * np.pi / 3),

            Pe - (i_A * v_A + i_B * v_B + i_C * v_C),
            Qe - (1 / np.sqrt(3)) * (
                (v_A - v_B) * i_C +
                (v_B - v_C) * i_A +
                (v_C - v_A) * i_B
            ),
        ],
        algebraic_vars=[e_A, e_B, e_C, Pe, Qe],

        in_vars=inputs,
        out_vars=[i_A, i_B, i_C],
    )

    templ.block.diff_vars = [d_i_A, d_i_B, d_i_C, d_theta]

    # ----------------------------------------------------------------------------------
    # External mapping
    # ----------------------------------------------------------------------------------
    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.P: None,
        VarPowerFlowRefferenceType.Q: None,
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
        VarPowerFlowRefferenceType.phi_v: phi_v,
        VarPowerFlowRefferenceType.phi: phi,
        VarPowerFlowRefferenceType.Vpk: Vpk,
        VarPowerFlowRefferenceType.Ipk: Ipk,
        VarPowerFlowRefferenceType.d_v_N: None,
        VarPowerFlowRefferenceType.d_v_A: None,
        VarPowerFlowRefferenceType.d_v_B: None,
        VarPowerFlowRefferenceType.d_v_C: None,
    }

    # ----------------------------------------------------------------------------------
    # Event dict
    # ----------------------------------------------------------------------------------
    w_base = 2.0 * np.pi * grid.fBase

    # Use the generator positive-sequence impedance as the simplest Thevenin impedance
    # for the test model.
    Rs_num = max(gen.R1, 1e-6)
    Xs_num = max(gen.X1, 1e-6)

    E_re = Vpk + R_s * Ipk * sym.cos(phi) - X_s * Ipk * sym.sin(phi)
    E_im = R_s * Ipk * sym.sin(phi) + X_s * Ipk * sym.cos(phi)

    templ.block.event_dict = {
        omega_base: vf.add_const(w_base),
        R_s: vf.add_const(Rs_num),
        X_s: vf.add_const(Xs_num),

        # PF-derived init-only values
        phi_v: vf.add_const(None),
        phi: vf.add_const(None),
        Vpk: vf.add_const(None),
        Ipk: vf.add_const(None),

        # Internal init-only auxiliary values
        # delta: vf.add_const(None),
        delta: sym.atan(E_im / E_re),
        # Epk: vf.add_const(None),
        Epk: ((E_re ** 2 + E_im ** 2) ** c05),
    }

    # ----------------------------------------------------------------------------------
    # Initialization equations
    # ----------------------------------------------------------------------------------
    #
    # Thevenin steady-state in positive sequence:
    #
    #   E = V + (R + jX) I
    #
    # If:
    #   V = Vpk ∠phi_v
    #   I = Ipk ∠(phi_v + phi)
    #
    # then relative to phi_v:
    #
    #   E_rel = Vpk + (R + jX) Ipk ∠phi
    #
    # whose rectangular components are:
    #
    #   E_re = Vpk + R Ipk cos(phi) - X Ipk sin(phi)
    #   E_im =       R Ipk sin(phi) + X Ipk cos(phi)
    #
    # so:
    #
    #   delta = angle(E_rel)
    #   Epk = |E_rel|
    #   theta = phi_v + delta
    #


    templ.block.init_eqs = {
        # delta: sym.atan(E_im / E_re),

        # Epk: ((E_re ** 2 + E_im ** 2) ** c05),

        theta: phi_v + delta,

        e_A: Epk * sym.sin(theta),
        e_B: Epk * sym.sin(theta - 2 * np.pi / 3),
        e_C: Epk * sym.sin(theta + 2 * np.pi / 3),

        Pe: (i_A * v_A + i_B * v_B + i_C * v_C),
        Qe: (1 / np.sqrt(3)) * (
            (v_A - v_B) * i_C +
            (v_B - v_C) * i_A +
            (v_C - v_A) * i_B
        ),
    }

    # ----------------------------------------------------------------------------------
    # Differential init equations
    # ----------------------------------------------------------------------------------
    #
    # If PF initialization is consistent, the currents are already those of the
    # steady-state operating point, so the current derivatives should start at zero.
    #
    templ.block.diff_init_eqs = {
        d_i_A: omega_base * (e_A - R_s * i_A - v_A) / X_s,
        d_i_B: omega_base * (e_B - R_s * i_B - v_B) / X_s,
        d_i_C: omega_base * (e_C - R_s * i_C - v_C) / X_s,
        d_theta: omega_base,
    }

    return templ