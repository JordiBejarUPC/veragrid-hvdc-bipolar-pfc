# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np
import math

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (Block, Var, Const, VarPowerFlowRefferenceType)
from VeraGridEngine.Templates.templates_common_functions import (tf_to_diffblock)
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import ConverterControlType



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
        state_eqs=[2*math.pi*fn*(omega-1)],
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
    Build power control loop model for Grid Following Converter.
    Supports multiple control modes via ConverterControlType.

    Args:
        inputs: [Vm, Va, Vdc] - AC voltage mag/angle, DC voltage
        control1: First control mode (typically active power or DC voltage related)
        control2: Second control mode (typically reactive power or AC voltage related)
        multilinear: Use multilinearization for Park transforms

    Returns:
        gfl_block: The complete converter block
        i_d, i_q: Current references
        P, Q: Active and reactive power measurements
    """
    Vm     = inputs[0]  
    Va     = inputs[1]  
    v_dc   = inputs[2]  # DC voltage for DC voltage control mode
    Pt_vsc = inputs[3]  # DC voltage for DC voltage control mode
    Qt_vsc = inputs[4]  # DC voltage for DC voltage control mode

    algebraic_eqs = []
    algebraic_vars = []
    gfl_block = Block()
    control_blocks = []
    
    # ==============================
    # Inputs and variables
    # ==============================

    pll_block, outputs = pll_transform_rms(Vm, Va, name = 'vg')
    v_d_g = outputs[0]
    v_q_g = outputs[1]
    theta = outputs[2]
    omega = outputs[3]

    # Parameters
    Kp_icl = Var('Kp_icl')     # proportional gain for inner current loop
    Ki_icl = Var('Ki_icl')     # integral gain for inner current loop
    Kp_pol = Var('Kp_pol')     # proportional gain for outer power loop
    Ki_pol = Var('Ki_pol')     # integral gain for outer power loop
    Kp_vdc = Var('Kp_vdc')     # proportional gain for DC voltage control
    Ki_vdc = Var('Ki_vdc')     # integral gain for DC voltage control
    Kp_vac = Var('Kp_vac')     # proportional gain for AC voltage control
    Ki_vac = Var('Ki_vac')     # integral gain for AC voltage control
    R = Var('R') 
    L = Var('L') 

    # VARS
    i_d = Var('i_d')
    i_q = Var('i_q')
    i_d_ref = Var('i_d_ref')
    i_q_ref = Var('i_q_ref')
    
    # POWER LOOP 
    P = Var('P')
    Q = Var('Q') 
    P_ref = Var('P_ref') 
    Q_ref = Var('Q_ref') 
    
    # Voltage references for control modes
    Vdc_ref = Var('Vdc_ref')
    Vm_ac_ref = Var('Vm_ac_ref')
    
    v_d_c = Var('v_d_c')
    v_q_c = Var('v_q_c')

    event_dict = {
        Kp_icl: Const(0.05),
        Ki_icl: Const(1.0),
        Kp_pol: Const(0.05),
        Ki_pol: Const(1.0),
        Kp_vdc: Const(0.1),
        Ki_vdc: Const(2.0),
        Kp_vac: Const(0.1),
        Ki_vac: Const(2.0),
        R: Const(0.1),
        L: Const(0.1),
        P_ref: Const(0.0),
        Q_ref: Const(0.0),
        Vdc_ref: Const(1.0),
        Vm_ac_ref: Const(1.0),
    }

    # P and Q at the point of common coupling
    algebraic_eqs.append(P - Const(3/2)*(v_q_g*i_q + v_d_g*i_d))
    algebraic_eqs.append(Q - Const(3/2)*(v_q_g*i_d - v_d_g*i_q))
    algebraic_vars.append(P)
    algebraic_vars.append(Q)

    # ==============================
    # CONTROL 1: Active Power Axis (i_q_ref)
    # ==============================
    # Control1 maps to i_q_ref (q-axis current controls active power)
    
    if control1 == ConverterControlType.Pac:
        # Active power control at AC side
        control_block_1, _ = tf_to_diffblock(
            num=[Ki_pol, Kp_pol],
            den=[0, 1],
            x= P_ref - P,
            y = i_q_ref,
            name='Pac_ctrl'
        )
        control_blocks.append(control_block_1)
        
    elif control1 == ConverterControlType.Pdc:
        # Active power control at DC side (Pdc ~ Pac in steady state)
        # For simplicity, we control Pac which is approximately Pdc
        control_block_1, _ = tf_to_diffblock(
            num=[Ki_pol, Kp_pol],
            den=[0, 1],
            x= P_ref - P,  # P_ref represents desired Pdc
            y = i_q_ref,
            name='Pdc_ctrl'
        )
        control_blocks.append(control_block_1)
        
    elif control1 == ConverterControlType.Vm_dc:
        # DC voltage control - regulates v_dc to Vdc_ref
        # Positive i_q_ref increases power flow from DC to AC, reducing v_dc
        control_block_1, _ = tf_to_diffblock(
            num=[Ki_vdc, Kp_vdc],
            den=[0, 1],
            x= Vdc_ref - v_dc,
            y = i_q_ref,
            name='Vdc_ctrl'
        )
        control_blocks.append(control_block_1)
    else:
        raise ValueError(f"Control1 type {control1} not supported for GFL converter. "
                        f"Supported: Pac, Pdc, Vm_dc")

    # ==============================
    # CONTROL 2: Reactive Power Axis (i_d_ref)
    # ==============================
    # Control2 maps to i_d_ref (d-axis current controls reactive power)
    
    if control2 == ConverterControlType.Qac:
        # Reactive power control
        control_block_2, _ = tf_to_diffblock(
            num=[Ki_pol, Kp_pol],
            den=[0, 1],
            x= Q_ref - Q,
            y = i_d_ref,
            name='Qac_ctrl'
        )
        control_blocks.append(control_block_2)
        
    elif control2 == ConverterControlType.Vm_ac:
        # AC voltage magnitude control
        # Use v_q_g as the measured voltage magnitude in dq frame (vd ~ 0)
        control_block_2, _ = tf_to_diffblock(
            num=[Ki_vac, Kp_vac],
            den=[0, 1],
            x= Vm_ac_ref - v_q_g,  # v_q_g is approximately Vm in dq frame
            y = i_d_ref,
            name='Vac_ctrl'
        )
        control_blocks.append(control_block_2)
    else:
        raise ValueError(f"Control2 type {control2} not supported for GFL converter. "
                        f"Supported: Qac, Vm_ac")

    # Physical Current Limits, TODO add AntiWindup
    I_max = Const(1.2)
    operation = 'normal'
    if operation == 'normal':
        id_max = sym.sqrt(sym.max(I_max**2 - sym.max(i_q, i_q_ref)**2, Const(1e-5)))     
        i_d_ref_sat = sym.hard_sat(i_d_ref, -id_max, id_max)
        i_q_ref_sat = sym.hard_sat(i_q_ref, -I_max, I_max)

    # Voltage Control Loop (Inner Current Loop)
    control_block_iq , vq_hat = tf_to_diffblock(
        num=[Ki_icl, Kp_icl],
        den=[0, 1],
        x= i_q_ref_sat - i_q,
        name='vq_hat'
    )
    control_block_id , vd_hat = tf_to_diffblock(
        num=[Ki_icl, Kp_icl],
        den=[0, 1],
        x= i_d_ref_sat - i_d,
        name='vd_hat'
    )

    # EMT block (differential equations for currents)
    dt_id = Var('dt_id', base_var= i_d)
    dt_iq = Var('dt_iq', base_var= i_q)
    EMT_block=Block(
        algebraic_eqs = [
            v_d_c - v_d_g - (R*i_d + L*dt_id - omega*L*i_q),
            v_q_c - v_q_g - (R*i_q + L*dt_iq - omega*L*i_d),
        ],
        diff_vars= [dt_id, dt_iq]
    )

    algebraic_eqs.append(v_d_c - (vd_hat + v_d_g + L*(omega)*i_q))
    algebraic_eqs.append(v_q_c - (vq_hat + v_q_g - L*(omega)*i_d))
    algebraic_vars.extend([v_q_c, v_d_c, i_d, i_q])

    # Build initialization equations based on control modes
    # P and Q are initialized from power flow results via external mapping
    init_eqs = {
        P: -Pt_vsc,
        Q: -Qt_vsc,
        theta: Va,
        omega: Const(1),
        v_d_g: Const(0),
        v_q_g: Vm,
        i_q: (2 / 3) * P / v_q_g,
        i_d: (2 / 3) * Q / v_q_g,
        i_q_ref: i_q,
        i_d_ref: i_d,
        v_d_c: v_d_g + (R*i_d - omega*L*i_q),
        v_q_c: v_q_g + (R*i_q - omega*L*i_d),
        vd_hat: v_d_c - (v_d_g + L*(omega)*i_q),
        vq_hat: v_q_c - (v_q_g - L*(omega)*i_d),
    }
    
    # Add control-specific initialization
    if control1 in [ConverterControlType.Pac, ConverterControlType.Pdc]:
        init_eqs[P_ref] = P
    elif control1 == ConverterControlType.Vm_dc:
        init_eqs[Vdc_ref] = v_dc
        # For DC voltage control, initialize i_q_ref based on initial power flow
        init_eqs[i_q_ref] = (2 / 3) * P / v_q_g
    
    if control2 == ConverterControlType.Qac:
        init_eqs[Q_ref] = Q
    elif control2 == ConverterControlType.Vm_ac:
        init_eqs[Vm_ac_ref] = v_q_g
        # For AC voltage control, initialize i_d_ref based on initial reactive power
        init_eqs[i_d_ref] = (2 / 3) * Q / v_q_g

    gfl_block_aux = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        event_dict= event_dict,
        init_eqs=init_eqs,
        external_mapping={
            VarPowerFlowRefferenceType.P:P,
            VarPowerFlowRefferenceType.Q:Q,
        }
    )
    gfl_block.add(gfl_block_aux)

    # Add all control blocks
    for ctrl_block in control_blocks:
        gfl_block.add(ctrl_block)
    gfl_block.add(control_block_id)
    gfl_block.add(control_block_iq)

    gfl_block.add(pll_block)
    gfl_block.add(EMT_block)
    gfl_block.unify_blocks()

    return gfl_block, i_d, i_q, P, Q

def VscGflBuild(name: str = "",
                control1: ConverterControlType = ConverterControlType.Pac,
                control2: ConverterControlType = ConverterControlType.Qac) -> RmsModelTemplate:
    """
    VSC GFL (Grid Following) model
    with from side the DC bus and to side the AC bus
    
    Args:
        name: Model name
        control1: First control mode (Pac, Pdc, or Vm_dc)
        control2: Second control mode (Qac or Vm_ac)
    
    Supported control combinations:
        - Pac + Qac: Active and reactive power control
        - Pac + Vm_ac: Active power and AC voltage control
        - Pdc + Qac: DC power and reactive power control
        - Pdc + Vm_ac: DC power and AC voltage control
        - Vm_dc + Qac: DC voltage and reactive power control
        - Vm_dc + Vm_ac: DC voltage and AC voltage control
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.VscDevice
    # Inputs: Vm, Va, Vdc (Pt_vsc and Qt_vsc come from power flow initialization)
    inputs = [Var("Vm_"), Var("Va_"), Var("Vdc_")]
    Vm = inputs[0]
    Va = inputs[1]
    v_dc = inputs[2]

    # Vars:
    Pt_vsc = Var('Pt_vsc')
    Qt_vsc = Var('Qt_vsc')
    Pf_vsc = Var('Pf_vsc')

    # Parameters:
    bt = Var('bt')
    gt = Var('gt')
    Qf = Var('Qf')
    a0 = Var('a0')
    a1 = Var('a1')
    a2 = Var('a2')
    
    # Build the converter model with specified control modes
    gfl_block, i_d, i_q, P, Q = build_gfl_converter_model(
        inputs=[Vm, Va, v_dc, Pt_vsc, Qt_vsc],
        control1=control1,
        control2=control2
    )

    event_dict = {
        Qf: Const(0.0),
        bt: Const(0.0),
        gt: Const(0.1),
        a0: Const(0.0),
        a1: Const(0.0),
        a2: Const(0.0),
    }
    
    Im = sym.sqrt(i_d**2 + i_q**2 + Const(1e-5))
    vsc_block = Block(
        algebraic_eqs=[
            Pf_vsc - (P - (a0 + a1*Im + a2*Im**2)),
            Pt_vsc + P,
            Qt_vsc + Q,
        ],
        algebraic_vars=[Pt_vsc, Qt_vsc, Pf_vsc],
        init_eqs={
            # vsh: sym.sqrt((exp1**2 + exp2**2)/(gt**2 + bt**2))/Vm,
            # ash: sym.atan((-gt*exp1 - bt*exp2)/(bt*exp1 - gt*exp2)),
        },
        event_dict= event_dict,
        external_mapping={
            VarPowerFlowRefferenceType.P: P,
            VarPowerFlowRefferenceType.Q: Q,
        },
        in_vars= inputs,
        out_vars = [Pt_vsc, Qt_vsc, Pf_vsc]
    )
    vsc_block.external_mapping = {
        VarPowerFlowRefferenceType.Vmt: inputs[0],
        VarPowerFlowRefferenceType.Vat: inputs[1],
        VarPowerFlowRefferenceType.Vdc: inputs[2],
        VarPowerFlowRefferenceType.Pt: Pt_vsc,
        VarPowerFlowRefferenceType.Qt: Qt_vsc,
        VarPowerFlowRefferenceType.Pf: Pf_vsc,
        VarPowerFlowRefferenceType.Qf: Qf,
    }

    vsc_block.add(gfl_block)
    vsc_block.name = 'gfl_block'

    new_block = vsc_block
    templ.block = vsc_block
    return templ
