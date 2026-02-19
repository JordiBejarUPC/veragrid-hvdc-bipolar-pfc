# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List, Dict, Any, Optional
import numpy as np
import math

from VeraGridEngine.enumerations import DeviceType, ConverterControlType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (Block, Var, Const, DiffVar, VarPowerFlowRefferenceType, tf_to_diffblock)
import VeraGridEngine.Utils.Symbolic.symbolic as sym

def build_gfm_converter_model(inputs: List[Var], 
                               multilinear: bool = False):
    """
    Build Grid Forming Converter model (Droop + voltage + current control)
    based on the provided conceptual equations.
    """
    Vm = inputs[0]
    Va = inputs[1]
    Pt_vsc = inputs[2]
    Qt_vsc = inputs[3]

    algebraic_eqs = []
    algebraic_vars = []
    res_block = Block()

    # Filter elements (per-unitized on converter base)
    Rf = Var('Rf')   # Resistance
    Lf = Var('Lf')   # Inductance
    Cf = Var('Cf')   # Capacitance
    
    # Droop gains and references
    Kdp = Var('Kdp')
    Kdq = Var('Kdq')
    omega_nom = Var('omega_nom') # rad/s
    omega_ref = Var('omega_ref') # p.u.
    V_ref = Var('V_ref')
    P_ref = Var('P_ref')
    Q_ref = Var('Q_ref')
    fn = Var('fn')
    
    # Inner loop PI gains
    Kp_icl = Var('Kp_icl')
    Ki_icl = Var('Ki_icl')
    
    # Filter time constants for power measurements
    tau_P = Var('tau_P')
    tau_Q = Var('tau_Q')
    
    # Limits
    V_max = Var('V_max')
    I_max = Var('I_max')

    event_dict = {
        Rf: Const(0.02),
        Lf: Const(0.15),
        Cf: Const(0.05),
        Kdp: Const(0.02),
        Kdq: Const(0.05),
        omega_nom: Const(2 * math.pi * 50),
        omega_ref: Const(1.0),
        V_ref: Const(1.0),
        P_ref: Const(None), # Initialized from power flow
        Q_ref: Const(None),
        fn: Const(50.0),
        Kp_icl: Const(0.05),
        Ki_icl: Const(50.0),
        tau_P: Const(0.01),
        tau_Q: Const(0.01),
        V_max: Const(1.1),
        I_max: Const(1.2),
    }

    # Variables
    P = Var('P')
    Q = Var('Q')
    omega = Var('omega')
    theta = Var('theta')
    V = Var('V')
    
    vd_g = Var('vd_g')
    vq_g = Var('vq_g')
    
    id_c = Var('id_c')
    iq_c = Var('iq_c')
    vd_f = Var('vd_f')
    vq_f = Var('vq_f')
    id_g = Var('id_g')
    iq_g = Var('iq_g')
    
    vd_c_ref = Var('vd_c_ref')
    vq_c_ref = Var('vq_c_ref')
    
    id_c_ref = Var('id_c_ref')
    iq_c_ref = Var('iq_c_ref')

    # Mapping terminal voltages to dq relative to internal angle theta
    algebraic_eqs.append(vd_g - Vm * sym.sin(Va - theta))
    algebraic_eqs.append(vq_g - Vm * sym.cos(Va - theta))
    
    # Filter nodes (simplified algebraic representation for RMS)
    algebraic_eqs.append(vd_f - vd_g)
    algebraic_eqs.append(vq_f - vq_g)
    
    # Grid currents (mapped from converter side)
    algebraic_eqs.append(id_g - id_c) 
    algebraic_eqs.append(iq_g - iq_c) 
    
    # Power measurement
    algebraic_eqs.append(P - Const(1.5) * (vq_g * iq_g + vd_g * id_g))
    algebraic_eqs.append(Q - Const(1.5) * (vq_g * id_g - vd_g * iq_g))
    
    # Droop control with Low-pass filters
    block_P, P_lowpass = tf_to_diffblock(num=[Const(1)], den=[tau_P, Const(1)], x=P, name='P_loop')
    block_Q, Q_lowpass = tf_to_diffblock(num=[Const(1)], den=[tau_Q, Const(1)], x=Q, name='Q_loop')
    res_block.add(block_P)
    res_block.add(block_Q)

    # omega = omega_ref - Kdp * (P_filt - P_ref)
    algebraic_eqs.append(omega - (omega_ref - Kdp * (P_lowpass - P_ref)))
    # V = V_ref - Kdq * (Q_filt - Q_ref)
    algebraic_eqs.append(V - (V_ref - Kdq * (Q_lowpass - Q_ref)))
    
    # Internal angle integration
    # d(theta)/dt = 2*pi*fn * (omega - 1)
    dt_theta = DiffVar('dt_theta', base_var=theta)
    algebraic_eqs.append(dt_theta - 2 * math.pi * fn * (omega - 1))
    
    # Voltage control loop
    vd_ref = Const(0)
    vq_ref = sym.hard_sat(V, -V_max, V_max)
    
    # PI controllers for voltage
    block_vd, id_hat = tf_to_diffblock(num=[Ki_icl, Kp_icl], den=[0, 1], x=vd_ref - vd_f, name='vd_ctrl')
    block_vq, iq_hat = tf_to_diffblock(num=[Ki_icl, Kp_icl], den=[0, 1], x=vq_ref - vq_f, name='vq_ctrl')
    res_block.add(block_vd)
    res_block.add(block_vq)
    
    # Current reference calculation (with feedforward and decoupling)
    algebraic_eqs.append(id_c_ref - (iq_hat + iq_g - Cf * omega * vq_f))
    algebraic_eqs.append(iq_c_ref - (id_hat + id_g + Cf * omega * vd_f))
    
    # Current loop PI controllers
    block_id, vd_hat = tf_to_diffblock(num=[Ki_icl, Kp_icl], den=[0, 1], x=id_c_ref - id_c, name='id_ctrl')
    block_iq, vq_hat = tf_to_diffblock(num=[Ki_icl, Kp_icl], den=[0, 1], x=iq_c_ref - iq_c, name='iq_ctrl')
    res_block.add(block_id)
    res_block.add(block_iq)
    
    # Converter voltage reference calculation
    algebraic_eqs.append(vd_c_ref - (vd_hat + vd_f - Lf * omega * iq_c))
    algebraic_eqs.append(vq_c_ref - (vq_hat + vq_f + Lf * omega * id_c))
    
    # Collect all variables
    algebraic_vars.extend([P, Q, omega, theta, V, vd_g, vq_g, id_c, iq_c, vd_f, vq_f, id_g, iq_g, vd_c_ref, vq_c_ref, id_c_ref, iq_c_ref])
    
    core_block = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        diff_vars=[dt_theta],
        event_dict=event_dict,
        init_eqs={
            P: -Pt_vsc,
            Q: -Qt_vsc,
            P_ref: P,
            Q_ref: Q,
            theta: Va,
            omega: Const(1.0),
            V: Vm,
            V_ref: Vm,
            vd_g: Const(0.0),
            vq_g: Vm,
            vd_f: vd_g,
            vq_f: vq_g,
            id_g: (2 / 3) * Q / vq_g,
            iq_g: (2 / 3) * P / vq_g,
            id_c: id_g,
            iq_c: iq_g,
            id_c_ref: id_c,
            iq_c_ref: iq_c,
            vd_c_ref: vd_f - Lf * omega * iq_c,
            vq_c_ref: vq_f + Lf * omega * id_c,
            vd_hat: vd_c_ref - (vd_f - Lf * omega * iq_c),
            vq_hat: vq_c_ref - (vq_f + Lf * omega * id_c),
            id_hat: id_c_ref - (id_g - Cf * omega * vq_f),
            iq_hat: iq_c_ref - (iq_g + Cf * omega * vd_f)
        },
        external_mapping={
            VarPowerFlowRefferenceType.P: P,
            VarPowerFlowRefferenceType.Q: Q,
        }
    )
    res_block.add(core_block)
    res_block.unify_blocks()
    
    return res_block, id_c, iq_c, P, Q

def VscGfmBuild(name: str = "") -> RmsModelTemplate:
    """
    VSC GFM (Grid Forming) model template builder.
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.VscDevice
    
    inputs = [Var("Vm_"), Var("Va_"), Var("Vdc_")]
    Vm = inputs[0]
    Va = inputs[1]
    v_dc = inputs[2]

    # Power Flow related variables
    Pt_vsc = Var('Pt_vsc')
    Qt_vsc = Var('Qt_vsc')
    Pf_vsc = Var('Pf_vsc')

    # Optional loss parameters (following GFL pattern)
    a0 = Var('a0')
    a1 = Var('a1')
    a2 = Var('a2')
    Qf = Var('Qf')
    
    event_dict = {
        a0: Const(0.0),
        a1: Const(0.0),
        a2: Const(0.0),
        Qf: Const(0.0),
    }

    gfm_block, i_d, i_q, P, Q = build_gfm_converter_model(inputs=[Vm, Va, Pt_vsc, Qt_vsc])

    Im = sym.sqrt(i_d**2 + i_q**2 + Const(1e-5))
    
    vsc_wrapper = Block(
        algebraic_eqs=[
            Pf_vsc - (P - (a0 + a1 * Im + a2 * Im**2)),
            Pt_vsc + P,
            Qt_vsc + Q,
        ],
        algebraic_vars=[Pt_vsc, Qt_vsc, Pf_vsc],
        event_dict=event_dict,
        external_mapping={
            VarPowerFlowRefferenceType.Vmt: inputs[0],
            VarPowerFlowRefferenceType.Vat: inputs[1],
            VarPowerFlowRefferenceType.Pt: Pt_vsc,
            VarPowerFlowRefferenceType.Qt: Qt_vsc,
            VarPowerFlowRefferenceType.Pf: Pf_vsc,
            VarPowerFlowRefferenceType.Qf: Qf,
            VarPowerFlowRefferenceType.Vdc: v_dc,
        },
        in_vars=inputs,
        out_vars=[Pt_vsc, Qt_vsc, Pf_vsc]
    )
    
    vsc_wrapper.add(gfm_block)
    vsc_wrapper.name = 'gfm_block'
    
    templ.block = vsc_wrapper
    return templ
