# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np
import math

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (Block, Var, Const, VarPowerFlowRefferenceType, tf_to_diffblock,
                                                 tf_to_diffblock_with_output, tf_to_diffblock_with_antiwindup)
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import ConverterControlType

def find_name_in_block(name:str, block:Block):
    for var in block.algebraic_vars + block.state_vars + block.parameters:
        if name == var.name:
            return var
        
    for block_child in block.children:
        result = find_name_in_block(name, block_child)
        if result is not None:   # found in a child
            return result
    
    return None

def inverse_park_transform_block(v_dq: list[Var], theta: Var, aux_vars = None, multilinear: bool = False, name:str =''):
    """
    Create a symbolic inverse Park transform (dq → abc) block for voltages.

    v_dq = [v_d_c, v_q_c]
    theta : grid angle (from PLL)
    multilinear : if True, use u_cos/u_sin auxiliary variables (for multilinearization)
    """

    v_d_c, v_q_c = v_dq

    # abc variables
    va_c = Var(name[0]+'a_'+name[-1])
    vb_c = Var(name[0]+'b_'+name[-1])
    vc_c = Var(name[0]+'c_'+name[-1])

    sqrt3 = Const(np.sqrt(3))
    reformulated_vars = []
    if not multilinear:
        # Non-multilinear form (explicit cos/sin)
        algebraic_eqs = [
            va_c - (v_d_c * sym.cos(theta) + v_q_c * sym.sin(theta)),

            vb_c - ((-Const(0.5) * v_d_c - (sqrt3 / Const(2)) * v_q_c) * sym.cos(theta)
                    + ((sqrt3 / Const(2)) * v_d_c - Const(0.5) * v_q_c) * sym.sin(theta)),

            vc_c - ((-Const(0.5) * v_d_c + (sqrt3 / Const(2)) * v_q_c) * sym.cos(theta)
                    + ((-sqrt3 / Const(2)) * v_d_c - Const(0.5) * v_q_c) * sym.sin(theta)),
        ]
        algebraic_vars = [va_c, vb_c, vc_c]
        trig_block = Block()
        aux_vars = None

    inv_park_block = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        reformulated_vars = reformulated_vars
    )
    inv_park_block.add(trig_block)

    return inv_park_block, (va_c, vb_c, vc_c), aux_vars

def park_transform_block(v_abc: list[Var], theta: Var, multilinear:bool = False, aux_vars = None, name:str = ''):
    """
    Create a symbolic Park transform (abc → dq) block for voltages and currents.

    i_abc = [i_a, i_b, i_c]
    v_abc = [v_a, v_b, v_c]
    theta : grid angle (from PLL)
    """

    v_a, v_b, v_c = v_abc

    # dq variables
    x_d = Var(name + '_d')
    x_q = Var(name + '_q')

    if not multilinear:
        algebraic_eqs = [
            # dq voltages
            x_d - (Const(1/3) * (
                (Const(2) * sym.cos(theta) * v_a)
                + (-sym.cos(theta) - Const(np.sqrt(3)) * sym.sin(theta)) * v_b
                + (-sym.cos(theta) + Const(np.sqrt(3)) * sym.sin(theta)) * v_c
            )),

            x_q - (Const(1/3) * (
                (Const(2) * sym.sin(theta) * v_a)
                + (-sym.sin(theta) + Const(np.sqrt(3)) * sym.cos(theta)) * v_b
                + (-sym.sin(theta) - Const(np.sqrt(3)) * sym.cos(theta)) * v_c
            )),
        ]
        algebraic_vars = [x_d, x_q]
        trig_block = Block()
        aux_vars = None


    park_block = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars
    )
    park_block.add(trig_block)

    return park_block, (x_d, x_q), aux_vars

def pll_transform_rms(Vm, Va, name:str = ''):
    #Variables 
    theta = Var('theta')
    vd = Var('vd')
    vq = Var('vq')

    #Parameters
    Kp_pll = Var('Kp_pll')      
    Ki_pll = Var('Ki_pll')        
    fn = Var('fn')

    event_dict = {
        fn: Const(50),
        Kp_pll: Const(0.001),
        Ki_pll: Const(0.1),
    }
    PI_block, omega = tf_to_diffblock(
        num=[Ki_pll, Kp_pll],
        den=[0, 1],
        x= (Vm*sym.sin(Va - theta)),
        name='PLL_integrator'
    )

    res_block = Block(
        state_eqs=[2*math.pi*fn*omega],
        state_vars=[theta],
        algebraic_eqs= [
            vd - Vm*sym.sin(Va - theta),
            vq - Vm*sym.cos(Va - theta),
        ],
        algebraic_vars = [vd,vq],
        event_dict = event_dict,
        children = [PI_block]
    )

    outputs = [vd, vq, theta, omega]
    return res_block, outputs


def pll_transform(v_abc, multilinear:bool = False, name:str = ''):
    theta = Var('theta')
    omega = Var('omega')
    omega_nom = Const(2*math.pi*50)
    Kp_pll = Const(0.001)      # proportional gain
    Ki_pll = Const(0.1)      # integral gain

    park_block, v_dq, aux_vars = park_transform_block(v_abc, theta, multilinear=multilinear, name = name) 
    v_d, v_q = v_dq
    res_block = Block()

    pi_block, _ = tf_to_diffblock(
        num=[Ki_pll, Kp_pll],
        den=[0, 1],
        x= v_d,
        y = omega,
        name='PLL_pi'
    )
    integrator, _ = tf_to_diffblock(
        num=[1],
        den=[0, 1],
        x= (omega),
        y = theta,
        name='PLL_integrator'
    )

    res_block.add(pi_block)
    res_block.add(integrator)
    res_block.add(park_block)
    return res_block, v_dq, omega, theta, aux_vars


def build_gfl_converter_model(inputs, 
                              control1: ConverterControlType = ConverterControlType.Pac, 
                              control2: ConverterControlType = ConverterControlType.Qac,
                              multilinear:bool = False):
    """
    Build power control loop model for Grid Forming Converter.

    power_vars = [P_ref, v_d, v_q, i_d, i_q]
    """
    Vm     = inputs[0]  
    Va     = inputs[1]  
    i_d    = inputs[2]
    i_q    = inputs[3]
    Pt_vsc = inputs[4]
    Qt_vsc = inputs[5]

    algebraic_eqs = []
    algebraic_vars = []
    gfl_block = Block()
    # ==============================
    # Inputs and variables
    # ==============================

    pll_block, outputs = pll_transform_rms(Vm, Va, name = 'vg')
    v_d_g = outputs[0]
    v_q_g = outputs[1]
    theta = outputs[2]
    omega = outputs[3]

    # i_d = Var('i_d') 
    # i_q = Var('i_q') 
    # algebraic_eqs.append(i_d - Im*sym.sin(Ia-theta))
    # algebraic_eqs.append(i_q - Im*sym.cos(Ia-theta))
    # algebraic_vars.extend([i_d,i_q])

    
    # Parameters
    Kp_icl = Var('Kp_icl')     # proportional gain
    Ki_icl = Var('Ki_icl')       # integral gain
    Kp_pol = Var('Kp_pol')       # proportional gain
    Ki_pol = Var('Ki_pol')       # integral gain
    R = Var('R') 
    L = Var('L') 

    #VARS
    i_d_ref = Var('i_d_ref')
    i_q_ref = Var('i_q_ref')
    
    #POWER LOOP 
    P = Var('P')
    Q = Var('Q') 
    P_ref = Var('P_ref') 
    Q_ref = Var('Q_ref') 
    v_d_c = Var('v_d_c')
    v_q_c = Var('v_q_c')

    event_dict = {
        Kp_icl: Const(0.05),      # proportional gain
        Ki_icl: Const(1.0) ,     # integral gain
        Kp_pol: Const(0.05),      # proportional gain
        Ki_pol: Const(1.0) ,     # integral gain
        R: Const(0.1),
        L: Const(0.01),
        P_ref: Const(None),
        Q_ref: Const(None),
    }

    #P and Q at the point of common coupling
    algebraic_eqs.append(P - Const(3/2)*(v_q_g*i_q + v_d_g*i_d))
    algebraic_eqs.append(Q - Const(3/2)*(v_q_g*i_d - v_d_g*i_q))
    algebraic_vars.append(P)
    algebraic_vars.append(Q)
    control_block_P , _ = tf_to_diffblock(
        num=[Ki_pol, Kp_pol],
        den=[0, 1],
        x= Q-Q_ref,
        y = i_d_ref,
        name='P'
    )
    control_block_Q , _ = tf_to_diffblock(
        num=[Ki_pol, Kp_pol],
        den=[0, 1],
        x = P-P_ref,
        y = i_q_ref,
        name='Q'
    )

    #Physical Current Limits, TODO add AntiWindup
    I_max = Const(1.2)
    operation = 'normal'
    if operation == 'normal':
        id_max = sym.sqrt( max(I_max**2- max(i_q, i_q_ref)**2, Const(1e-5)))     
        i_d_ref = sym.hard_sat(i_d_ref, -id_max, id_max)
        i_q_ref = sym.hard_sat(i_q_ref, -I_max, I_max)


    #Voltage Control Loop
    control_block_iq , vq_hat = tf_to_diffblock(
        num=[Ki_icl, Kp_icl],
        den=[0, 1],
        x= i_q_ref - i_q,
        name='vq_hat'
    )
    control_block_id , vd_hat = tf_to_diffblock(
        num=[Ki_icl, Kp_icl],
        den=[0, 1],
        x= i_d_ref - i_d,
        name='vd_hat'
    )
    vsh = Var('vsh')
    ash = Var('ash')

    algebraic_eqs.append(v_d_c - (vd_hat + v_d_g + L*(omega)*i_q))
    algebraic_eqs.append(v_q_c - (vq_hat + v_q_g - L*(omega)*i_d))
    algebraic_eqs.append(v_d_c - (-vsh*sym.cos(ash - theta)))
    algebraic_eqs.append(v_q_c - ( vsh*sym.sin(ash - theta)))
    algebraic_vars.extend([v_q_c, v_d_c, vsh, ash])

    gfl_block_aux = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        event_dict= event_dict,
        init_eqs={
            P_ref: -Pt_vsc,
            Q_ref: -Qt_vsc,
        },
        external_mapping={
            VarPowerFlowRefferenceType.P:P,
            VarPowerFlowRefferenceType.Q:Q,
        }
    )
    gfl_block.add(gfl_block_aux)

    gfl_block.add(control_block_P)
    gfl_block.add(control_block_Q)
    gfl_block.add(control_block_id)
    gfl_block.add(control_block_iq)

    gfl_block.add(pll_block)

    return gfl_block, vsh, ash, P, Q

def VscGflBuild(name: str = "") -> RmsModelTemplate:
    """
     VSC GFL model
     with from side the DC bus and to side the AC bus
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.VscDevice
    inputs = [Var("Vm_"), Var("Va_"), Var("Vdc_")]
    Vm = inputs[0]
    Va = inputs[1]
    v_dc = inputs[2]

    #Vars:
    Id = Var("Id")
    Iq = Var("Iq")
    Pt_vsc = Var('Pt_vsc')
    Qt_vsc = Var('Qt_vsc')
    Pf_vsc = Var('Pf_vsc')
    #Parameters:
    bt = Var('bt')
    gt = Var('gt')
    Qf = Var('Qf')
    gfl_block, vsh, ash, P, Q = build_gfl_converter_model(inputs=[Vm, Va, Id, Iq, Pt_vsc, Qt_vsc])

    event_dict = {
        Qf: Const(0.0),
        bt: Const(0.0),
        gt: Const(0.1),
    }
    exp1 = Qt_vsc + bt*Vm**2
    exp2 = Pt_vsc - gt*Vm**2
    vsc_block = Block(
        algebraic_eqs=[
            Pt_vsc + (-bt*vsh*Vm*sym.sin(ash - Va) + gt*Vm**2 - gt*vsh*Vm*sym.cos(ash - Va)),
            Qt_vsc + ( bt*vsh*Vm*sym.cos(ash - Va) - bt*Vm**2 - gt*vsh*Vm*sym.sin(ash - Va)),
            Pf_vsc + ( bt*vsh*Vm*sym.sin(ash - Va) + gt*Vm**2 - gt*vsh*Vm*sym.cos(ash - Va)),
            Pt_vsc + P,
            Qt_vsc + Q,
        ],
        algebraic_vars=[Pt_vsc, Qt_vsc, Pf_vsc, Id, Iq],
        init_eqs={
            vsh: sym.sqrt((exp1**2 + exp2**2)/(gt**2 + bt**2))/Vm,
            ash: sym.atan((-gt*exp1 - bt*exp2)/(bt*exp1 - gt*exp2)),
        },
        event_dict= event_dict,
        external_mapping={
            VarPowerFlowRefferenceType.P: P,
            VarPowerFlowRefferenceType.Q: Q,
        },
        in_vars= inputs,
        out_vars = [Pt_vsc, Qt_vsc, vsh, ash, Pf_vsc]
    )
    vsc_block.external_mapping = {
        VarPowerFlowRefferenceType.Vmt: inputs[0],
        VarPowerFlowRefferenceType.Vat: inputs[1],
        VarPowerFlowRefferenceType.Pt: Pt_vsc,
        VarPowerFlowRefferenceType.Qt: Qt_vsc,
        VarPowerFlowRefferenceType.Pf: Pf_vsc,
        VarPowerFlowRefferenceType.Qf: Qf,
        VarPowerFlowRefferenceType.Vdc: v_dc,
    }

    vsc_block.add(gfl_block)
    #vsc_block.unify_blocks()
    vsc_block.name = 'gfl_block'

    #new_block = vsc_block.unify_blocks()
    new_block = vsc_block
    print(len(new_block.algebraic_vars))
    print(len(new_block.algebraic_eqs))
    templ.block = vsc_block
    return templ