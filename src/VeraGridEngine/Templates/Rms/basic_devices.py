# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import math

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_helpers import tf_to_block

def get_pll_transform_rms(vfactory: VarFactory, name: str = "Pll_transform_rms") -> RmsModelTemplate:
    """
     Pll
    """
    suffix = f"_{name}" if name else ""
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    inputs = [vfactory.add_var("Vm_" + name, reference=VarPowerFlowReferenceType.Vm),
              vfactory.add_var("Va_" + name, reference=VarPowerFlowReferenceType.Va),
              ]

    # Variables
    theta = vfactory.add_var(f'theta{suffix}', shared_reference="theta_reference")
    vd = vfactory.add_var(f'vd{suffix}', shared_reference="vd_reference")
    vq = vfactory.add_var(f'vq{suffix}', shared_reference="vq_reference")


    # Parameters
    Kp_pll = vfactory.add_var(f'Kp_pll{suffix}')
    Ki_pll = vfactory.add_var(f'Ki_pll{suffix}')
    fn = vfactory.add_var(f'fn{suffix}')

    res_event_dict = {
        fn: vfactory.add_const(50),
        Kp_pll: vfactory.add_const(0.001),
        Ki_pll: vfactory.add_const(0.1),
    }

    PI_block, omega = tf_to_block(vfactory,
                                  num=[Ki_pll, Kp_pll],
                                  den=[0, 1],
                                  x=(inputs[0] * sym.sin(inputs[1] - theta)),
                                  name='PLL_integrator'
                                  )

    res_block = Block(
        state_eqs=[2 * math.pi * fn * (omega - 1)],
        state_vars=[theta],
        algebraic_eqs=[
            vd - inputs[0] * sym.sin(inputs[1] - theta),
            vq - inputs[0] * sym.cos(inputs[1] - theta),
        ],
        algebraic_vars=[vd, vq],
        event_dict=res_event_dict,
        init_eqs={
            omega: vfactory.add_const(1),
            theta: inputs[1],
            vd: inputs[0] * sym.sin(inputs[1] - theta),
            vq: inputs[0] * sym.cos(inputs[1] - theta),
        },
        name= 'Pll transformer',
        out_vars = [vd, vq, theta, omega],
        in_vars=inputs,
        children=[PI_block]
    )
    res_block.unify_blocks()



    #Todo: add this method to var factory
    vfactory.add_shared_ref_to_var(omega, "omega_reference")
    templ.block = res_block

    return templ

def get_pi_current_controller(vfactory: VarFactory, name: str = "current_ctrl_iq") -> RmsModelTemplate:
    """
     Current control iq
    """
    suffix = f"_{name}" if name else ""
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    Kp_icl = vfactory.add_var('Kp_icl')  # proportional gain for inner current loop
    Ki_icl = vfactory.add_var('Ki_icl')  # integral gain for inner current loop

    block = Block()

    event_dict = {
        Kp_icl: vfactory.add_const(0.05),
        Ki_icl: vfactory.add_const(1.0),
    }

    i_q = vfactory.add_var('i_q', shared_reference='i_q_reference')
    i_q_ref_sat = vfactory.add_var('i_q_ref_sat', shared_reference='i_q_ref_sat_reference')
    i_d = vfactory.add_var('i_d', shared_reference='i_d_reference')
    i_d_ref_sat = vfactory.add_var('i_d_ref_sat', shared_reference='i_d_ref_sat_reference')

    inputs = [i_q, i_q_ref_sat, i_d, i_d_ref_sat]

    control_block_iq, vq_hat = tf_to_block(vfactory,
                                           num=[Ki_icl, Kp_icl],
                                           den=[0, 1],
                                           x=inputs[0] - inputs[1],
                                           name='vq_hat',
                                           output_var_name = 'vq_hat'
                                           )

    control_block_iq.algebraic_vars.remove(vq_hat)
    control_block_iq.init_eqs = {
    }

    vfactory.add_shared_ref_to_var(vq_hat, "vq_hat_reference")

    control_block_id, vd_hat = tf_to_block(vfactory,
                                           num=[Ki_icl, Kp_icl],
                                           den=[0, 1],
                                           x=inputs[2] - inputs[3],
                                           name='vq_hat',
                                           output_var_name='vd_hat'
                                           )

    control_block_id.algebraic_vars.remove(vd_hat)
    control_block_id.init_eqs = {
    }

    vfactory.add_shared_ref_to_var(vd_hat, "vd_hat_reference")

    control_block_iq.in_vars = [i_q, i_q_ref_sat]
    control_block_iq.out_vars = [vq_hat]

    control_block_id.in_vars = [i_d, i_d_ref_sat]
    control_block_id.out_vars = [vd_hat]

    block.event_dict = event_dict
    block.in_vars = inputs
    block.out_vars = [vq_hat, vd_hat]
    block.children = [control_block_iq, control_block_id]

    templ.block = block


    return templ


def get_pi_power_controller(vfactory: VarFactory, name: str = "current_ctrl_iq") -> RmsModelTemplate:
    """
     Current control iq
    """
    suffix = f"_{name}" if name else ""
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    Kp_pol = vfactory.add_var('Kp_pol')  # proportional gain for outer power loop
    Ki_pol = vfactory.add_var('Ki_pol')  # integral gain for outer power loop

    P = vfactory.add_var('P', shared_reference='P_reference')
    Q = vfactory.add_var('Q', shared_reference='Q_reference')
    P_ref = vfactory.add_var('P_ref', shared_reference='P_ref_reference')
    Q_ref = vfactory.add_var('Q_ref', shared_reference='Q_ref_reference')

    event_dict = {
        Kp_pol: vfactory.add_const(0.05),
        Ki_pol: vfactory.add_const(1.0),
        P_ref: P,
        Q_ref: Q,
    }

    block = Block()



    i_q_ref = vfactory.add_var('i_q_ref', shared_reference='i_q_ref_reference')
    i_d_ref = vfactory.add_var('i_d_ref', shared_reference='i_d_ref_reference')

    inputs = [P, P_ref, i_q_ref, Q, Q_ref, i_d_ref]

    control_block_1, _ = tf_to_block(vfactory,
                                     num=[Ki_pol, Kp_pol],
                                     den=[0, 1],
                                     x=P_ref - P,
                                     y=i_q_ref,
                                     name='Pac_ctrl'
                                     )

    control_block_2, _ = tf_to_block(vfactory,
                                    num=[Ki_pol, Kp_pol],
                                    den=[0, 1],
                                    x=Q_ref - Q,
                                    y=i_d_ref,
                                    name='Qac_ctrl'
                                    )

    control_block_1.in_vars = [P, P_ref, i_q_ref]
    control_block_2.in_vars = [Q, Q_ref, i_d_ref]
    control_block_1.event_dict = event_dict
    control_block_2.event_dict = event_dict

    block.children = [control_block_1, control_block_2]

    block.in_vars = inputs

    templ.block = block

    return templ

def get_gfl_converter_rms(vfactory: VarFactory, name: str = "current_ctrl_iq") -> RmsModelTemplate:
    """
     Current control iq
    """
    suffix = f"_{name}" if name else ""
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    # input variables
    Vm = vfactory.add_var('Vm', reference= VarPowerFlowReferenceType.Vm)
    Va = vfactory.add_var('Va', reference=VarPowerFlowReferenceType.Va)
    v_dc = vfactory.add_var('v_dc', shared_reference='v_dc_reference')
    Pt_vsc = vfactory.add_var('Pt_vsc', reference=VarPowerFlowReferenceType.P)
    Qt_vsc = vfactory.add_var('Qt_vsc', reference=VarPowerFlowReferenceType.Q)

    inputs = [Vm, Va, v_dc, Pt_vsc, Qt_vsc]

    # variables from pll
    v_d_g = vfactory.add_var('v_d_g', shared_reference='vd_reference')
    v_q_g = vfactory.add_var('v_q_g', shared_reference='vq_reference')
    theta = vfactory.add_var('theta', shared_reference='theta_reference')
    omega = vfactory.add_var('omega', shared_reference='omega_reference')

    # variables from control
    vq_hat = vfactory.add_var('vq_hat', shared_reference='vq_hat_reference')
    vd_hat = vfactory.add_var('vd_hat', shared_reference='vd_hat_reference')

    # electrical block variables
    v_d_c = vfactory.add_var('v_d_c')
    v_q_c = vfactory.add_var('v_q_c')
    i_d = vfactory.add_var('i_d', shared_reference = 'i_d_reference')
    i_q = vfactory.add_var('i_q', shared_reference = 'i_q_reference')
    P = vfactory.add_var('P', shared_reference = 'P_reference')
    Q = vfactory.add_var('Q', shared_reference = 'Q_reference')
    dt_id = vfactory.add_diff_var('dt_id', base_var=i_d)
    dt_iq = vfactory.add_diff_var('dt_iq', base_var=i_q)


    # electrical block parameters
    R = vfactory.add_var('R')
    L = vfactory.add_var('L')

    # limiter block input variables
    i_d_lim = vfactory.add_var('i_d_lim', shared_reference='i_d_reference')
    i_q_lim = vfactory.add_var('i_q_lim', shared_reference='i_q_reference')

    # limiter block constants
    I_max = vfactory.add_const(1.2)

    # limiter block variables
    i_d_ref = vfactory.add_var('i_d_ref', shared_reference='i_d_ref_reference')
    i_q_ref = vfactory.add_var('i_q_ref', shared_reference='i_q_ref_reference')
    id_max = sym.sqrt(sym.max(I_max ** 2 - sym.max(i_q, i_q_ref) ** 2, vfactory.add_const(1e-5)))
    i_d_ref_sat = sym.hard_sat(i_d_ref, -id_max, id_max)
    i_q_ref_sat = sym.hard_sat(i_q_ref, -I_max, I_max)
    i_d_ref_sat_var = vfactory.add_var('i_d_ref_sat')
    i_q_ref_sat_var = vfactory.add_var('i_q_ref_sat')



    pll_block = get_pll_transform_rms(vfactory)

    pi_current_controller = get_pi_current_controller(vfactory)
    pi_power_controller = get_pi_power_controller(vfactory)


    electrical_block = Block(
        algebraic_eqs=[
            v_d_c - v_d_g + (R * i_d + L * dt_id - omega * L * i_q),
            v_q_c - v_q_g + (-R * i_q + L * dt_iq - omega * L * i_d),
            v_d_c - (vd_hat + v_d_g - L * omega * i_q),
            v_q_c - (vq_hat + v_q_g + L * omega * i_d),
            P - (v_q_g * i_q + v_d_g * i_d),
            Q - (v_q_g * i_d - v_d_g * i_q)

        ],
        algebraic_vars=[v_q_c, v_d_c, i_d, i_q, P, Q, vd_hat, vq_hat],
        diff_vars=[dt_id, dt_iq],
        event_dict={
            R: vfactory.add_const(0.01),
            L: vfactory.add_const(0.05),
        },
        in_vars = [v_d_g, v_q_g, theta, omega, vd_hat, vq_hat],
        out_vars = [P, Q, i_d, i_q],
        init_eqs = {
        P: -Pt_vsc,
        Q: -Qt_vsc,
        i_q: P / v_q_g,
        i_d: Q / v_q_g,
        v_d_c: v_d_g - (R * i_d - omega * L * i_q),
        v_q_c: v_q_g - (-R * i_q - omega * L * i_d),
        vd_hat: v_d_c - (v_d_g - L * omega * i_q),
        vq_hat: v_q_c - (v_q_g + L * omega * i_d),
    }
    )

    current_limiter_block =  Block(
        algebraic_eqs = [i_d_ref_sat_var - i_d_ref_sat,
                         i_q_ref_sat_var - i_q_ref_sat,
                         ],
        algebraic_vars = [i_d_ref_sat_var, i_q_ref_sat_var],
        out_vars = [i_d_ref, i_q_ref],
        in_vars = [i_d_lim, i_q_lim],
        init_eqs={
            i_d_ref_sat_var: i_d_ref_sat,
            i_q_ref_sat_var: i_q_ref_sat,
            i_q_ref: i_q_lim,
            i_d_ref: i_d_lim,
        }
    )

    block = Block()
    block.children = [pll_block.block, pi_current_controller.block, pi_power_controller.block, electrical_block, current_limiter_block]
    block.in_vars = inputs
    block.out_vars = [i_d, i_q, P, Q, theta, v_d_c, v_q_c, vd_hat, vq_hat, R, L]
    templ.block = block

    return templ