# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import List
import math

from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType, ParamPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (Block, Var)
from VeraGridEngine.Templates.templates_common_functions import tf_to_block
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import ConverterControlType

TYPE_CHECKING = True
if TYPE_CHECKING:
    from VeraGridEngine.Devices.Substation.bus import Bus
    from VeraGridEngine.Devices.Branches.transformer import Transformer2W, WindingType, WindingsConnection

def parse_windings_connection(conn: WindingsConnection) -> tuple[WindingType, WindingType]:
    """
    Parse a WindingsConnection enum into (conn_f, conn_t) WindingType values.
    
    WindingsConnection values are two-character strings:
    - G: GroundedStar
    - S: NeutralStar (ungrounded star)  
    - D: Delta
    
    Examples:
    - GG -> (GroundedStar, GroundedStar)
    - GD -> (GroundedStar, Delta)
    - DD -> (Delta, Delta)
    """
    conn_str = str(conn)
    if len(conn_str) != 2:
        raise ValueError(f"Invalid WindingsConnection: {conn}")
    
    char_to_winding = {
        'G': WindingType.GroundedStar,
        'S': WindingType.NeutralStar,
        'D': WindingType.Delta,
    }
    
    conn_f = char_to_winding.get(conn_str[0])
    conn_t = char_to_winding.get(conn_str[1])
    
    if conn_f is None or conn_t is None:
        raise ValueError(f"Invalid WindingsConnection characters: {conn_str}")
    
    return conn_f, conn_t

def build_vsc_rms(vfactory: VarFactory, name:str = ''):
    """
    Build power control loop model for Grid Following Converter.
    Supports multiple control modes via ConverterControlType.
    from bus is DC
    to   bus is AC
        """

    templ = RmsModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name

    inputs: List[Var] = [vfactory.add_var("Im_placeholder" + name)]

    Im = inputs[0]
    Pf = vfactory.add_var("Pf_vsc")
    Pt = vfactory.add_var("Pt_vsc")

    alpha1 = vfactory.add_var("alpha1")
    alpha2 = vfactory.add_var("alpha2")
    alpha3 = vfactory.add_var("alpha3")

    block = Block()
    block.parameters[alpha1] = vfactory.add_const(0.0)
    block.parameters[alpha2] = vfactory.add_const(0.0)
    block.parameters[alpha3] = vfactory.add_const(0.0)

    block.algebraic_vars = [Pf, Pt]

    #Active power is conserved Reactive isnt
    block.algebraic_eqs  = [
        Pf - Pt - (alpha1 + alpha2*Im + alpha3*Im**2),
    ]

    block.external_mapping = {
        VarPowerFlowRefferenceType.Pf: Pf,
        VarPowerFlowRefferenceType.Pt: Pt,
    }

    block.api_obj_mapping= {
        ParamPowerFlowRefferenceType.alpha1 : alpha1,
        ParamPowerFlowRefferenceType.alpha2 : alpha2,
        ParamPowerFlowRefferenceType.alpha3 : alpha3,
    }

    block.in_vars =  inputs
    templ.block = block

    return templ

def build_vsc_transformer_control(vf:VarFactory, name:str=''):
    #Inputs
    Vm  = vf.add_var('Vm')
    vdc = vf.add_var('vdc')
    inputs = [Vm, vdc]

    #Variables
    am = vf.add_var('am')
    alpha = vf.add_var('am')
    
    #Reference Values:
    p_ref = vf.add_var('p_ref')
    v_ref = vf.add_var('v_ref')
    i_ref = vf.add_var('i_ref')

    #Controller Parameters:
    Kp = vf.add_var('Kp') 
    Ki = vf.add_var('Ki') 
    Km = vf.add_var('Km') 
    Ks = vf.add_var('Ks') 
    alpha_max = vf.add_var('alpha_max') 
    alpha_min = vf.add_var('alpha_min') 
    u_max = vf.add_var('u_max') 
    u_min = vf.add_var('u_min') 

    block = Block()
    block.algebraic_vars = [am, alpha]
    outputs = []
    return

def build_trafo_vsc(vf:VarFactory, trafo:Transformer2W, name:str = ''):
    #from bus is GRID
    #to   bus is CONVERTER

    templ = RmsModelTemplate()
    templ.name = name
    vdc = vf.add_var('vdc_'+ name, VarPowerFlowRefferenceType.Vdc)
    vmf = vf.add_var('vmf_'+ name, VarPowerFlowRefferenceType.Vmf)
    vmt = vf.add_var('vmt_'+ name, VarPowerFlowRefferenceType.Vmt)
    vaf = vf.add_var('vaf_'+ name, VarPowerFlowRefferenceType.Vaf)
    vat = vf.add_var('vat_'+ name, VarPowerFlowRefferenceType.Vat)
    inputs = [vdc, vmf, vmt, vaf, vat]

    #Variables
    Qf = vf.add_var("Qf_" + name,VarPowerFlowRefferenceType.Qf)
    Qt = vf.add_var("Qt_" + name,VarPowerFlowRefferenceType.Qt)
    Pf = vf.add_var("Pf_" + name,VarPowerFlowRefferenceType.Pf)
    Pt = vf.add_var("Pt_" + name,VarPowerFlowRefferenceType.Pt)
    Im = vf.add_var("Im_" + name)
    m = vf.add_var('m')
    am = vf.add_var('am')
    phi = vaf

    #Parameters
    ys = 1.0 / complex(trafo.R, trafo.X)
    ysh = trafo.G + 1j * trafo.B
    gt  = vf.add_var("g")
    bt  = vf.add_var("b")
    gFe = vf.add_var('gFe')
    bmu = vf.add_var('bmu')
    am_ref  = vf.add_var('am_ref')
    phi_ref = vf.add_var('phi_ref')
    vtap_f, vtap_t = trafo.get_virtual_taps()
    
    print(f"DEBUG Trafo: R={trafo.R}, X={trafo.X}, G={trafo.G}, B={trafo.B}")
    print(f"DEBUG Trafo: tap_mod={trafo.tap_module}, tap_phase={trafo.tap_phase}, vtap_f={vtap_f}, vtap_t={vtap_t}")
    print(f"vtap  p is {vtap_f}")
    print(f"vtap  t is {vtap_t}")
    print(f'ys is {ys} ysh is {ysh}')
    
    # Calculate phase displacement matching transformer_admittance logic
    # Use conn attribute (preserves user intent) instead of conn_f/conn_t (may be overwritten by template)
    conn_f, conn_t = parse_windings_connection(trafo.conn)
    conn_y_from = conn_f == WindingType.NeutralStar or conn_f == WindingType.GroundedStar
    conn_y_to = conn_t == WindingType.NeutralStar or conn_t == WindingType.GroundedStar
    if conn_f == WindingType.Delta and conn_y_to:  # Dy
        phase_displacement = np.deg2rad(60.0)
    elif conn_y_from and conn_t == WindingType.Delta:  # Yd
        phase_displacement = np.deg2rad(0.0)
    else:
        phase_displacement = 0.0

    theta_hk = vaf - vat
    k = vf.add_const(np.sqrt(3/8))
    block = Block(
        algebraic_vars=[am, Pf, Pt, Qf, Qt, Im],
        algebraic_eqs=[
            # From side: Pf = Re(Vf * (Yff*Vf + Yft*Vt)*)
            vmt - vdc*am*k,
            Pf - ((vmf ** 2 * (gFe + gt)) / (m * vtap_f) ** 2 - gt / (m * vtap_f * vtap_t) * vmf * vmt * sym.cos(
                theta_hk - phi) - bt / (m * vtap_f * vtap_t) * vmf * vmt * sym.sin(
                theta_hk - phi - phase_displacement)),
            Qf - (-vmf ** 2 * (bmu / 2 + bt) / (m * vtap_f) ** 2 - gt / (m * vtap_f * vtap_t) * vmf * vmt * sym.sin(
                theta_hk - phi) + bt / (m * vtap_f * vtap_t) * vmf * vmt * sym.cos(
                theta_hk - phi - phase_displacement)),

            # To side: Pt = Re(Vt * (Ytf*Vf + Ytt*Vt)*)
            Pt - ((vmt ** 2 * (gFe + gt)) / vtap_t ** 2 - gt / (m * vtap_f * vtap_t) * vmt * vmf * sym.cos(
                theta_hk - phi) + bt / (m * vtap_f * vtap_t) * vmt * vmf * sym.sin(
                theta_hk - phi - phase_displacement)),
            Qt - (-vmt ** 2 * (bmu / 2 + bt) / vtap_t ** 2 + gt / (m * vtap_f * vtap_t) * vmt * vmf * sym.sin(
                theta_hk - phi) + bt / (m * vtap_f * vtap_t) * vmt * vmf * sym.cos(
                theta_hk - phi - phase_displacement)),
            Im - sym.sqrt(Pt**2 + Qt**2)/vmt,
            phi - phi_ref,
            am - am_ref,
        ],
        init_eqs={
            am: vmt/k*vdc,
            Im: sym.sqrt(Pt**2 + Qt**2)/vmt,
            am_ref : am,
            phi_ref: phi,
        },
        event_dict={
            m      : vf.add_const(trafo.tap_module),
            phi_ref   : vf.add_const(None),
            am_ref    : vf.add_const(None),
        },
        in_vars=inputs,
    )

    block.external_mapping = {
        VarPowerFlowRefferenceType.Vaf: vaf,
        VarPowerFlowRefferenceType.Vat: vat,
        VarPowerFlowRefferenceType.Vmf: vmf,
        VarPowerFlowRefferenceType.Vmt: vmt,
        VarPowerFlowRefferenceType.Pf: Pf,
        VarPowerFlowRefferenceType.Pt: Pt,
        VarPowerFlowRefferenceType.Qf: Qf,
        VarPowerFlowRefferenceType.Qt: Qt,
    }

    block.api_obj_mapping = {
        ParamPowerFlowRefferenceType.g: gt,
        ParamPowerFlowRefferenceType.b: bt,
        ParamPowerFlowRefferenceType.bsh: bmu,
    }
    block.parameters = {
        gt:vf.add_const(ys.real),
        bt:vf.add_const(ys.imag),
        gFe:vf.add_const(ysh.real),
        bmu:vf.add_const(ysh.imag)
    }

    block.out_vars = [Im]
    templ.block = block
    return templ