# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import math
from VeraGridEngine.Templates.templates_common_functions import tf_to_block
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Branches.hvdc_line import HvdcLine
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import sin, cos, sqrt
from VeraGridEngine.enumerations import HvdcControlType

class HvdcRmsTemplate(RmsModelTemplate):
    """
    RMS Template for HVDC Line with fixed power setpoint control.
    

    """

    def __init__(self, hvdc: HvdcLine, vf: VarFactory, Sbase: float = 100, name: str = "hvdc_rms_template"):
        """
        Create the RMS Template of an HVDC Line
        
        :param hvdc: HVDC Line device
        :param vf: VarFactory for creating symbolic variables
        :param Sbase: System base power (MVA)
        :param name: Name of the RMS Model
        """
        super().__init__(name=name)
        
        self.tpe: DeviceType = DeviceType.HVDCLineDevice
        
        if hvdc.rms_model.empty():
            # Create algebraic variables for power flow
            Pf = vf.add_var("Pf")
            Pt = vf.add_var("Pt")
            Qf = vf.add_var("Qf")
            Qt = vf.add_var("Qt")
            
            # Get voltage magnitude references from connected buses
            # These are symbolic variables linked to bus voltages via .E()
            Vmf = vf.add_var(f"Vmf_{hvdc.name}")
            Vaf = vf.add_var(f"Vaf_{hvdc.name}")
            Vmt = vf.add_var(f"Vmt_{hvdc.name}")
            Vat = vf.add_var(f"Vat_{hvdc.name}")    
            
            #Parameters
            Ti = vf.add_var('Ti')  # Time constant for control dynamics
            Tr = vf.add_var('Tr')  # Time constant for control dynamics
            Ki = vf.add_var('Ki')  # Time constant for control dynamics
            Kp = vf.add_var('Kp')  # Time constant for control dynamics
            vdc_ref = vf.add_var('vdc_ref')  # Time constant for control dynamics
            vac_ref = vf.add_var('vac_ref')  # Time constant for control dynamics
            gamma_ref = vf.add_var('gamma_ref')  # Time constant for control dynamics

            #We initialize parameters
            parameters={
                vac_ref: hvdc.Vset_f,
                vdc_ref: hvdc.dc_link_voltage,
                gamma_ref: vf.add_const(None)
            }            #Internal HVDC states
            pi = math.pi
            phi_f = vf.add_var(f"phi_h_{hvdc.name}")  #Phase for reactive power control
            alpha = vf.add_var(f"alpha_{hvdc.name}")  # Firing angle for reactive power control
            gamma = vf.add_var(f"gamma_{hvdc.name}")  # Firing angle for reactive power control
            phi_t = vf.add_var(f"phi_t_{hvdc.name}")  #Phase for reactive power control
            ir_dc = vf.add_var(f"ir_dc_{hvdc.name}")  # DC current variable
            k = vf.add_const(0.9995*3/pi)*sqrt(2)
            K_droop = vf.add_const(0.05)  # Droop gain for frequency control
            
            x_r = vf.add_var(f"m_f_{hvdc.name}")  # Tap for from side (rectifier control)
            x_i = vf.add_var(f"m_t_{hvdc.name}")  # Tap for to side (inverter control)
            ii_dc = ir_dc
            m_f = x_r  
            m_t = x_i 

            vr_dc = k*m_f*Vmf*cos(phi_f)
            vi_dc = k*m_t*Vmt*cos(phi_t)


            block = Block(
                algebraic_vars=[Pf, Pt, Qf, Qt, gamma, alpha, phi_f, phi_t, m_f, m_t, ir_dc],
                algebraic_eqs=[
                    Pf - (-vr_dc*ir_dc),
                    Qf - (-k*m_f*Vmf*ir_dc*sin(phi_f)),
                    k*m_f*Vmt*(cos(alpha) - cos(phi_f)) - vf.add_const(3/pi)*x_r*ir_dc,
                    Pt - (-vi_dc*ii_dc),
                    Qt - (k*m_t*Vmt*ii_dc*sin(phi_t)),
                    k*m_t*Vmt*(cos(pi-gamma) + cos(phi_t)) - vf.add_const(3/pi)*x_i*ii_dc,
                ],
                parameters = parameters,
                init_eqs={
                    m_f: vf.add_const(1.0),
                    m_t: vf.add_const(1.0),
                    phi_f: vf.add_const(pi/2),  # Initial phase for reactive power control
                    phi_t: vf.add_const(pi/2),  # Initial phase for reactive power control
                    alpha: vf.add_const(pi/2),  # Initial firing angle
                    gamma: vf.add_const(pi/2),  # Initial firing angle
                    ir_dc: vf.add_const(hvdc.Pset/hvdc.dc_link_voltage)  # Initial DC current based on power setpoint and voltage
                },
                in_vars=[Vmf, Vaf, Vmt, Vat],
            )
            
            if hvdc.control_mode == HvdcControlType.type_0_free:
                Pdc_ref = hvdc.Pset/Sbase + K_droop*(Vaf - Vmt)
            elif hvdc.control_mode == HvdcControlType.type_1_Pset:
                Pdc_ref = hvdc.Pset/Sbase 
            idc_ref = Pdc_ref/vdc_ref
            control_block =Block(
                state_vars=[x_i, x_r],
                state_eqs=[
                    (vdc_ref - vi_dc)/Ti,
                    (Vmf - vac_ref)/Tr,
                    gamma - gamma_ref,
                ]
            )
            PI_block, _ = tf_to_block(
                var_factory = vf,
                x = idc_ref - ir_dc,
                y = alpha,
                num=[Ki, Kp],
                den=[0, 1]
            )

            block.children.append(control_block)
            block.children.append(PI_block)

            # External mapping for power flow references
            block.external_mapping = {
                VarPowerFlowRefferenceType.Pf: Pf,
                VarPowerFlowRefferenceType.Pt: Pt,
                VarPowerFlowRefferenceType.Qf: Qf,
                VarPowerFlowRefferenceType.Qt: Qt,
            }
            block.unify_blocks()
            self._block = block


def initialize_hvdc_rms(hvdc: HvdcLine, vf: VarFactory, Sbase: float = 100):
    """
    Initialize the RMS model for an HVDC Line
    
    :param hvdc: HVDC Line device
    :param vf: VarFactory
    :param Sbase: System base power (MVA)
    """
    hvdc.rms_model.model = HvdcRmsTemplate(hvdc=hvdc, vf=vf, Sbase=Sbase).block
