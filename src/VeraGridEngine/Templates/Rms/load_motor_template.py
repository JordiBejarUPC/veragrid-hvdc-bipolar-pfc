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


def MotorLoadBuild(name: str = "") -> RmsModelTemplate:
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    res_block = Block()
    pi = math.pi
    #Inputs:
    inputs = [Var('Vm'), Var('Va')]
    Vm = inputs[0]
    Va = inputs[1]
    #Variables:
    omega = Var('omega')
    Id = Var('Id')
    Iq = Var('Iq')
    P = Var('Pl')
    Q = Var('Ql')
    Vq = Var('Vq')
    Vd = Var('Vd')
    Ed_prime  = Var('Ed_prime')
    Eq_prime  = Var('Eq_prime')
    Ed_2prime = Var('Ed_2prime')
    Eq_2prime = Var('Eq_2prime')

    #Parameters:
    u = Var('u')
    Ls  = Var('Ls')
    Lp  = Var('Lp')
    Rs  = Var('Ra')
    Tp0 = Var('Tp0')
    H   = Var('H')
    D   = Var('D')
    n   = Var('n')
    VT  = Var('VT')
    TV  = Var('TV')
    Lpp = Var('Lpp')
    Cl0 = Var('Cl0')
    Tpp0 = Var('Tpp0')
    omega_s = Var('omega_s')
    omega0 = Var('omega_0')
    SLIP0 = Var('SLIP0')
    
    #Shunt Parameters
    b = Var('b')
    g = Var('g')

    events_dict = {
    # Electrical (induction motor typical ranges)
    Rs:   Const(0.015),   # Stator resistance (pu) ~ 0.01–0.03
    Ls:   Const(0.15),    # Stator leakage inductance (pu) ~ 0.10–0.25
    Lp:   Const(3.00),    # Magnetising (mutual) inductance (pu) ~ 2–5

    # Transient / rotor dynamics (approx. rotor open-circuit constants)
    Tp0:  Const(0.60),    # "Transient" time constant (s) ~ 0.2–1.0
    Lpp:  Const(0.12),    # Subtransient/leakage-like inductance (pu), < Ls
    Tpp0: Const(0.05),    # Fast electrical time constant (s) ~ 0.02–0.10

    # Mechanical
    H:    Const(0.8),    # Inertia constant (s) ~ 0.2–1.5
    D:    Const(0.0),     # Damping (often 0 unless explicitly modelled)
    n:    Const(1.0),     # Exponent of the torque speed dependency (unitless)
    Cl0:  Const(None),     # Initial load torque	(pu)
    SLIP0:  Const(0.0),     # Initial load torque	(pu)

    # Voltage measurement / filtering
    VT:   Const(1.0),     # Nominal terminal voltage (pu)
    TV:   Const(0.02),    # Voltage transducer / RMS estimator time (s)
    u:  Const(0.0),
    #frequency
    omega_s: Const(1.0),          #nominal frequency in pu
    omega0:  Const(None),          #initial frequency in pu

    g: Const(0.0),
    b: Const(0.0),
    }

    

    SLIP = 1-omega
    dt_Ed = Eq_prime*omega_s*SLIP  - ( Iq*(Ls-Lp) + Ed_prime )/Tp0
    dt_Eq = -Ed_prime*omega_s*SLIP  - ( -Id*(Ls-Lp)   + Eq_prime )/Tp0
    block1 = Block(
        state_eqs = [
            u*dt_Ed, #dt Ed_prime
            u*dt_Eq, #dt Eq_prime
            u*(-(Eq_prime - Eq_2prime)*omega_s*SLIP - (Ed_prime - Eq_2prime - (Lp-Lpp)*Iq)/Tpp0 + dt_Ed), #dt Ed_2prime
            u*((Ed_prime - Ed_2prime)*omega_s*SLIP - (Eq_prime - Ed_2prime + (Lp-Lpp)*Id)/Tpp0 + dt_Eq), #dt Eq_2prime
        ],
        state_vars = [Ed_prime, Eq_prime, Ed_2prime, Eq_2prime],
    )

    Te = Var('Te')
    block2 = Block(
        state_eqs = [
            u*((Eq_2prime*Iq + Ed_2prime*Id) - Cl0*sym.abs(omega/omega0)**n)/2*H,
        ],
        state_vars = [omega],
        algebraic_eqs= [ 
                    Te - (Eq_2prime*Iq + Ed_2prime*Id),
                    u*(Vd - Ed_2prime + Rs*Id - Lpp*Iq),
                    u*(Vq - Eq_2prime + Rs*Iq + Lpp*Id),
                    Vd - (-Vm*sym.sin(Va)),
                    Vq - (Vm*sym.cos(Va)),
                    u*(P - (Vd*Id + Vq*Iq - g*Vm**2)),
                    u*(Q - (Vq*Id - Vd*Iq + b*Vm**2)),
        ],
        algebraic_vars=[Id, Iq, P, Q, Vd, Vq, Te]
    )

    res_block = Block(children=[block1, block2])
    res_block.event_dict = events_dict
    res_block.external_mapping = {
        VarPowerFlowRefferenceType.Vm: inputs[0],
        VarPowerFlowRefferenceType.Va: inputs[1],
        VarPowerFlowRefferenceType.P: P,
        VarPowerFlowRefferenceType.Q: Q,
    }
    res_block.in_vars = inputs

    I = sym.conj(-(P + 1j*Q))/(Vm * sym.exp(1j * Va))
    Ii = sym.imag(I)
    Ir = sym.real(I)
    Vi = sym.imag(Vm * sym.exp(1j * Va))
    Vr = sym.real(Vm * sym.exp(1j * Va))

    a = Tp0*omega_s*SLIP
    L = (Ls - Lp)
    Ed_prime_calc = L*(-Iq + a*Id)/(1 + a**2)
    Eq_prime_calc = L*( Id + a*Iq)/(1 + a**2)
    A =  ( Iq*(Ls-Lp) + Ed_prime_calc )/Tp0
    omega_init = -A/(omega_s*Eq_prime_calc) + Const(1.0)
    res_block.init_eqs ={
        Vd: -Vm*sym.sin(Va),
        Vq: Vm*sym.cos(Va),
        Id: (P*Vd +Q*Vq)/(Vd**2 +Vq**2),
        Iq: (P*Vq -Q*Vd)/(Vd**2 +Vq**2),
        Ed_2prime: u*(Vd + (Rs*Id - Lpp*Iq)),
        Eq_2prime: u*(Vq + (Rs*Iq + Lpp*Id)),
        Te: u*(Eq_2prime*Iq + Ed_2prime*Id),
        Cl0: u*((Eq_2prime*Iq + Ed_2prime*Id)),
        omega: u*(omega_init),
        Ed_prime:  u*Ed_prime_calc,
        Eq_prime:  u*Eq_prime_calc,
        omega0:omega,
    }

    templ.block = res_block
    return templ