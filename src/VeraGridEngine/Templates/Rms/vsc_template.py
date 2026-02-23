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

def VSCShuntBuild(name: str = "") -> RmsModelTemplate:
    """
     VSC shunt model
     with from side the DC bus and to side the AC bus
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.VscDevice
    inputs = [Var("Vm_"), Var("Va_"), Var("Vdc_"), Var("Idc_")]
    Vm = inputs[0]
    Va = inputs[1]
    v_dc = inputs[2]
    i_dc = inputs[3]

    #Vars:
    P_ac = Var('P_ac')
    Q_ac = Var('Q_ac')
    P_dc = Var('P_dc')
    alpha = Var('alpha')
    am = Var('am')
    Im = Var('Im')
    Ia = Var('Ia')

    #Parameters:
    bt = Var('bt')
    gt = Var('gt')
    event_dict = {
        bt: Const(0.0),
        gt: Const(0.1),
    }

    sqrt_38 = Const(np.sqrt(3/8))
    vsc_block = Block(
        algebraic_eqs=[
            P_ac - (gt*Vm**2 - sqrt_38*am*v_dc*Vm*sym.cos(Va - alpha)
                    - sqrt_38*bt*am*v_dc*Vm*sym.sin(Va - alpha)),
            Q_ac - (-bt*Vm**2 + sqrt_38*bt*am*v_dc*Vm*sym.cos(Va - alpha)
                    - sqrt_38*bt*am*v_dc*Vm*sym.sin(Va - alpha)),
            gt*(sqrt_38*am*v_dc)**2 - sqrt_38*am*v_dc*Vm*sym.cos(Va-alpha)
                + sqrt_38*am*v_dc*Vm*sym.sin(Va - alpha),
            P_ac**2 + Q_ac**2  - Vm*Im,
            P_ac*sym.sin(Va - alpha) - Q_ac*sym.cos(Va - alpha),
        ],
        algebraic_vars=[P_ac, Q_ac, alpha, am, Im, Ia],
    )

    vsc_block.event_dict = event_dict
    vsc_block.in_vars = inputs
    vsc_block.out_vars = [P_ac, Q_ac, alpha, am]

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Vmt: inputs[0],
        VarPowerFlowRefferenceType.Vat: inputs[1],
        VarPowerFlowRefferenceType.Pt: P_ac,
        VarPowerFlowRefferenceType.Qt: Q_ac,
        VarPowerFlowRefferenceType.Pf: v_dc*i_dc,
        VarPowerFlowRefferenceType.Vdc: v_dc,
        VarPowerFlowRefferenceType.Idc: i_dc,
    }

    vsc_block.name = name
    templ.block = vsc_block
    return templ

def VSCShuntBuild2(name: str = "") -> RmsModelTemplate:
    """
     VSC shunt model
     with from side the DC bus and to side the AC bus
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.VscDevice
    inputs = [Var("Vm_"), Var("Va_"), Var("Vdc_")]
    Vm = inputs[0]
    Va = inputs[1]
    v_dc = inputs[2]

    #Vars:
    Pt_vsc = Var('Pt_vsc')
    Qt_vsc = Var('Qt_vsc')
    Pf_vsc = Var('Pf_vsc')
    vsh = Var('vsh')
    ash = Var('ash')
    #Parameters:
    bt = Var('bt')
    gt = Var('gt')
    Qf = Var('Qf')
    event_dict = {
        Qf: Const(0.0),
        bt: Const(0.0),
        gt: Const(0.1),
    }

    sqrt_38 = Const(np.sqrt(3/8))
    exp1 = Qt_vsc + bt*Vm**2
    exp2 = Pt_vsc - gt*Vm**2
    vsc_block = Block(
        algebraic_eqs=[
            Pt_vsc + (-bt*vsh*Vm*sym.sin(ash - Va) + gt*Vm**2 - gt*vsh*Vm*sym.cos(ash - Va)),
            Qt_vsc + ( bt*vsh*Vm*sym.cos(ash - Va) - bt*Vm**2 - gt*vsh*Vm*sym.sin(ash - Va)),
            Pf_vsc + ( bt*vsh*Vm*sym.sin(ash - Va) + gt*Vm**2 - gt*vsh*Vm*sym.cos(ash - Va)),
        ],
        algebraic_vars=[Pt_vsc, Qt_vsc, vsh, ash, Pf_vsc],
        init_eqs={
            vsh: sym.sqrt((exp1**2 + exp2**2)/(gt**2 + bt**2))/Vm,
            ash: sym.atan((-gt*exp1 - bt*exp2)/(bt*exp1 - gt*exp2)),
        }
    )

    vsc_block.event_dict = event_dict
    vsc_block.in_vars = inputs
    vsc_block.out_vars = [Pt_vsc, Qt_vsc, vsh, ash, Pf_vsc]

    vsc_block.external_mapping = {
        VarPowerFlowRefferenceType.Vmt: inputs[0],
        VarPowerFlowRefferenceType.Vat: inputs[1],
        VarPowerFlowRefferenceType.Pt: Pt_vsc,
        VarPowerFlowRefferenceType.Qt: Qt_vsc,
        VarPowerFlowRefferenceType.Pf: Pf_vsc,
        VarPowerFlowRefferenceType.Qf: Qf,
        VarPowerFlowRefferenceType.Vdc: v_dc,
    }

    vsc_block.name = name
    templ.block = vsc_block
    return templ

def PVControlBuild2(name: str = "") -> RmsModelTemplate:
    templ = RmsModelTemplate()
    inputs = [Var("Vm_"), Var("Vdc_"), Var("vhs_"), Var("ahs_"), Var("Pdc_")]
    Vm = inputs[0]
    vdc = inputs[1]
    vhs = inputs[2]
    ahs = inputs[3]
    Pdc = inputs[4]

    #Vars:
    x = Var('x')

    #Parameters:
    Kp = Var('Kp')
    Ki = Var('Ki')
    vdc_ref = Var('vdc_ref')
    Temp = Var('Temp')
    G = Var('G')
    gamma_p = Var('gamma_p')
    Pref = Var('Pref')
    Gref = Var('Gref')
    Tref = Var('Tref')
    vref = Var('vref')
    Km = Var('Km')
    Ts = Var('Ts_controller')
    event_dict = {
        vref: Const(None),
        Km: Const(10.0),
        Ts: Const(0.01),
        Kp: Const(0.1),
        Ki: Const(0.1),
        Temp: Const(300.0),
        G: Const(1000.0),
        Gref: Const(1000.0),
        Pref: Const(None),
        Tref: Const(300.0),
        gamma_p: Const(-0.001),
        vdc_ref: Const(1.033),
    }

    Ppv = (G/Const(1000.0))*(Pref*(1+gamma_p*(Temp - Tref)))
    i_dc_ref = Ppv / vdc_ref
    init_eqs = {
        vref: inputs[0],
        Pref: inputs[4],
    }

    block_vhs_control, _ = tf_to_diffblock_with_antiwindup(
        x =(Vm-vref),
        y = vhs,
        num = [Km],
        den = [Const(1), Ts],  
        name = "VSC Vhs Control",
        sat_min = Const(-1.0),      
        sat_max = Const(1.0),
    )      
    #Block that Controls Vdc_ref based on MPPT optimal point
    solar_block = Block(
        state_eqs=[ Ki*(vdc_ref - vdc) ],   
        state_vars=[x],
        algebraic_eqs=[
            Kp*(vdc_ref - vdc) + x - ahs,
            i_dc_ref + vdc_ref*i_dc_ref.diff(vdc_ref),
        ],
        algebraic_vars=[vdc_ref],
        in_vars=inputs,
        init_eqs= init_eqs,
        #children = [block_vhs_control],
        event_dict= event_dict,
    )

    solar_block.name = name

    templ.block = solar_block
    templ.block.event_dict = event_dict

    return templ

def PVControlBuild(name: str = "") -> RmsModelTemplate:
    templ = RmsModelTemplate()
    inputs = [Var("Vdc_"), Var("ahs_")]
    Vdc = inputs[0]
    alpha = inputs[1]

    #Vars:
    x = Var('x')

    #Parameters:
    Kp = Var('Kp')
    Ki = Var('Ki')
    vdc_ref = Var('vdc_ref')
    Temp = Var('Temp')
    G = Var('G')
    gamma_p = Var('gamma_p')
    Pref = Var('Pref')
    Gref = Var('Gref')
    Tref = Var('Tref')

    event_dict = {
        vdc_ref: Const(1.0),
        Kp: Const(0.1),
        Ki: Const(0.1),
        Temp: Const(300.0),
        G: Const(1000.0),
        Gref: Const(1000.0),
        Pref: Const(0.1),
        Tref: Const(300.0),
        gamma_p: Const(-0.001),
    }

    Ppv = (G/Const(1000.0))*(Pref*(1+gamma_p*(Temp - Tref)))
    i_dc_ref = Ppv / vdc_ref
    init_eqs = {}
    solar_block = Block(
        state_eqs=[ Ki*(vdc_ref - Vdc) ],   
        state_vars=[x],
        algebraic_eqs=[
            Kp*(vdc_ref - Vdc) + x - alpha,
            i_dc_ref + vdc_ref*i_dc_ref.diff(vdc_ref),
        ],
        in_vars=inputs,
        init_eqs= init_eqs,
    )

    solar_block.name = name
    templ.block = solar_block
    templ.block.event_dict = event_dict

    return templ

def PVCellBuild(name: str = "") -> RmsModelTemplate:
    templ = RmsModelTemplate()
    inputs = [Var("Vdc_")]
    Vdc = inputs[0]

    #Vars:
    iD = Var('iD')
    iL = Var('iL')
    Idc = Var('Idc')
    vD = Var('vD')
    Pdc = Var('Pdc')

    #Parameters:
    Temp = Var('Temp')
    gamma_p = Var('gamma_p')
    Pref = Var('Pref')
    Gref = Var('Gref')
    Tref = Var('Tref')
    Rsh = Var('Rsh')
    Rse = Var('Rse')
    Temp0 = Var('Temp0')
    is0 = Var('is0')
    Sn = Var('Sn')
    Aa = Var('Aa')
    rho_e = Var('rho_e')
    C_temp = Var('C_temp')
    G = Var('G')
    iL0 = Var('iL0')

    event_dict = {
    Temp:   Const(298.15),
    gamma_p: Const(-0.004),
    Pref:   Const(0.02),
    Gref:   Const(1000.0),
    Tref:   Const(298.15),
    Rsh:    Const(1000.0),
    Rse:    Const(0.005),
    Temp0:  Const(298.15),
    is0:    Const(1e-10),
    Sn:     Const(1.0),
    Aa:     Const(1.2),
    rho_e:  Const(1.68e-8),
    C_temp: Const(1000.0),
    G:      Const(1000.0),  
    iL0:    Const(None)
    }

    qe = Const(1.60217662e-19)  # Electron charge (C)
    kB = Const(1.380649e-23)  # Boltzmann constant (J/K)
    gamma = Const(1.2)  # Diode ideality factor (unitless)

    def energy_band(Temp):
        # Empirical relation for silicon
        Eg0 = 1.17  # eV
        alpha = 4.73e-4  # eV/K
        beta = 636  # K
        Eg_of_Temp  = Eg0 - (alpha * Temp**2) / (Temp + beta)
        Eg_of_Temp0 = Eg0 - (alpha * Temp0**2) / (Temp0 + beta)
        return qe*Eg0/(kB*gamma)*(Eg_of_Temp0 - Eg_of_Temp)

    v_T = kB*Temp/qe
    Is  = is0*(Temp/Temp0)**3*sym.exp(energy_band(Temp))
    
    #TODO: Include Temperature dynamics model
    solar_block = Block(
        algebraic_eqs=[
            Idc - (iL - iD - vD/Rsh),
            Pdc - Idc*Vdc,
            vD - Vdc - Rse*Idc,
            Is*(sym.exp(vD/(gamma*v_T)) - Const(1)) - iD,
            iL - iL0,
        ],
        algebraic_vars=[iD, iL, Idc, vD, Pdc],
        in_vars=inputs,
        out_vars=[Pdc, Idc],
        external_mapping={
            VarPowerFlowRefferenceType.P: Pdc,
            VarPowerFlowRefferenceType.Idc: Idc,
            VarPowerFlowRefferenceType.Vdc: Vdc,
        },
        init_eqs={
            Idc : Pdc/Vdc,
            vD  : Vdc + Rse*Idc,
            iD  : Is*(sym.exp(vD/(gamma*v_T)) - Const(1)),
            iL0 : Idc - (- iD - vD/Rsh),
            iL  : Idc - (- iD - vD/Rsh),
        }
    )

    solar_block.name = "PVCell" + name
    solar_block.event_dict = event_dict
    templ.block = solar_block

    return templ


def VscControlledPV(name = 'VscControlledPV') -> RmsModelTemplate:

    templ = RmsModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice

    vsc_block = VSCShuntBuild2().block
    pv_block  = PVControlBuild2().block
    pv_cell_block  = PVCellBuild().block

    pv_block.connect([pv_block.in_vars[2]], [vsc_block.out_vars[2]])
    pv_block.connect([pv_block.in_vars[3]], [vsc_block.out_vars[3]])

    pv_cell_block.connect([pv_cell_block.in_vars[0]], [vsc_block.out_vars[0]])


    templ.block = Block(children=[pv_block, pv_cell_block])

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Vm: vsc_block.in_vars[0],
        VarPowerFlowRefferenceType.Va: vsc_block.in_vars[1],
        VarPowerFlowRefferenceType.P: vsc_block.out_vars[0],
        VarPowerFlowRefferenceType.Q: vsc_block.out_vars[1],
    }

    return templ, vsc