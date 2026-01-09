# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List, Dict
import numpy as np
import math

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, Expr, VarPowerFlowRefferenceType, tf_to_diffblock, \
    tf_to_block_with_states, tf_to_diffblock_with_states, hard_sat, tf_to_diffblock_with_output
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, real, imag, conj, angle, exp, log, abs, UndefinedConst,  \
      sqrt, atan, f_exc, heaviside, UNDEFINED
from scipy.optimize import fsolve

def solve_Ve_init(
    y4, Ifd, Ke, Kd,
    VeMinPu, VeMaxPu,
    Se_threshold,
    AEx, BEx,
    tol=1e-6,
    max_iter=1000
):
    # Initial unsaturated guess
    Ve = (y4 - Ifd * Kd) / Ke
    Ve = max(VeMinPu, min(Ve, VeMaxPu))

    for _ in range(max_iter):
        # Saturation function Se(Ve)
        if Ve > Se_threshold:
            Se = AEx * Ve * math.exp(BEx * (Ve - Se_threshold))
        else:
            Se = 0.0
        Ve_new = (y4 - Ifd * Kd) / (Ke + Se)
        Ve_new = max(VeMinPu, min(Ve_new, VeMaxPu))

        # Convergence check
        if abs(Ve_new - Ve) < tol:
            return Ve_init

        Ve = Ve_new
    # Unsaturated value corresponding to final Se
    Ve_init = (y4 - Ifd * Kd) / (Ke + Se)

    return Ve_init

def Efd_diff(UsRefPu, x):
    # ----------------------------
    # Unpack vector
    # ----------------------------
    Ifd           = x[0]
    y1            = x[1]
    E_fd_desired  = x[2]

    Ka            = x[3]
    Ke            = x[4]
    Kd            = x[5]
    Kc            = x[6]

    VeMinPu       = x[7]
    VeMaxPu       = x[8]
    EfeMinPu      = x[9]
    EfeMaxPu      = x[10]

    AEx           = x[11]
    BEx           = x[12]
    Se_threshold  = x[13]

    # ----------------------------
    # Algebraic signals
    # ----------------------------
    y3 = -y1 + UsRefPu
    y4 = y3 * Ka

    # ----------------------------
    # Solve Ve_init / Ve_sat
    # ----------------------------
    Ve_init, Ve_sat = solve_Ve_init(
        y4=y4,
        Ifd=Ifd,
        Ke=Ke,
        Kd=Kd,
        VeMinPu=VeMinPu,
        VeMaxPu=VeMaxPu,
        Se_threshold=Se_threshold,
        AEx=AEx,
        BEx=BEx,
    )

    # ----------------------------
    # Saturated Efe
    # ----------------------------
    Efe = max(EfeMinPu, min(y4, EfeMaxPu))

    # ----------------------------
    # Saturation function Se(Ve)
    # ----------------------------
    if Ve_sat > Se_threshold:
        Se = AEx * Ve_sat * math.exp(BEx * (Ve_sat - Se_threshold))
    else:
        Se = 0.0

    # ----------------------------
    # Remaining algebra
    # ----------------------------
    u_aux = Ke * Ve_init + Se * Ve_init
    Vfe   = u_aux + Ifd * Kd

    f_input  = Kc * Ifd / max(Ve_sat, 1e-6)
    f_output = f_exc(Const(f_input)).simplify().value
    E_fd     = f_output * Ve_sat

    # ----------------------------
    # Residual
    # ----------------------------
    return E_fd - E_fd_desired

def solve_x(A, B, C, Ke, x0=0.1):
    """
    Solves the equation:
        -A - x*C*exp(B*x) - x*Ke = 0
    for x using fsolve.
    """
    f = lambda x: -A - x*C*np.exp(B*x) - x*Ke
    sol, info, ier, msg = fsolve(f, x0, full_output=True)

    if ier != 1:
        print("Root finding did not fully converge:")
        print(msg)
    return sol[0]

def find_name_in_block(name:str, block:Block):
    for var in block.algebraic_vars + block.state_vars:
        if name == var.name:
            return var

    for block_child in block.children:
        result = find_name_in_block(name, block_child)
        if result is not None:   # found in a child
            return result

    return None

def GenqecBuild(name: str = "") -> RmsModelTemplate:
    """
     generator with quadratic saturation
    """
    pi = math.pi
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice

    # Inputs
    # Vm: Bus voltage module
    # Va: Bus voltage angle
    # Tm: mechanical torque (from governor)
    # Vf: excitation voltage (from exciter)

    inputs: List[Var] = [Var("Vm_" + name),
                         Var("Va_" + name),
                         Var("Tm_" + name),
                         Var("Vf_" + name)]

    # ______________________________________________________________________________________
    #                                    variables
    # ______________________________________________________________________________________

    # State variables
    delta = Var("delta" + name)  # rotor angle
    omega = Var("omega" + name)  # rotor electrical speed
    Eq1 = Var("Eq1" + name)  # internal emf behind Xd'
    Ed1 = Var("Ed1" + name)
    Eq_prime = Var("Eq_prime" + name)  # transient voltage q-axis
    Ed_prime = Var("Ed_prime" + name)  # transient voltage d-axis
    Psid_prime = Var("Psid_prime" + name)  # transient voltage d-axis
    Psiq_prime = Var("Psiq_prime" + name)  # transient voltage d-axis

    # Algebraic variables
    Pg = Var('Pg' + name)
    Qg = Var('Qg' + name)
    Id = Var("Id" + name)
    Iq = Var("Iq" + name)
    Vd = Var("Vd" + name)
    Vq = Var("Vq" + name)
    Psid = Var("Psid" + name)
    Psiq = Var("Psiq" + name)
    Te = Var("Te" + name)
    IRPu = Var("IRPu" + name)

    # Saturated resistances
    Xd_2prime_sat = Var('Xd_2prime_sat' + name)
    Xq_2prime_sat = Var('Xq_2prime_sat' + name)
    Sa = Var('Sa' + name)
    V_qag = Var('V_qag' + name)
    V_dag = Var('V_dag' + name)
    Psi_ag = Var('Psi_ag' + name)

    # ______________________________________________________________________________________
    #                                    parameters
    # ______________________________________________________________________________________
    fn = Var('fn')  # system frequency [Hz]
    ws = Var('ws')  # synchronous speed [rad/s]
    M = Var('M')  # inertia constant
    D = Var('D')  # damping (optional)
    Rs = Var('Rs')  # stator resistance
    Ra = Var('Ra')  # armature resistance (if distinct)

    # Reactances
    Xd = Var('Xd')
    Xq = Var('Xq')
    Xd_prime = Var('Xd_prime')
    Xq_prime = Var('Xq_prime')
    Xd_2prime = Var('Xd_2prime')
    Xq_2prime = Var('Xq_2prime')
    Xl = Var('Xl')

    # Time constants
    Td0_prime = Var('Td0_prime')
    Tq0_prime = Var('Tq0_prime')
    Td0_2prime = Var('Td0_2prime')
    Tq0_2prime = Var('Tq0_2prime')

    #Auxiliary expressions
    Viag_expr = inputs[0] * sin(inputs[1]) + imag(
                conj(Pg + 1j * Qg) / conj(inputs[0] * exp(1j * inputs[1]))) * Ra + real(
                conj(Pg + 1j * Qg) / conj(inputs[0] * exp(1j * inputs[1]))) * Xl
    Vrag_expr = inputs[0] * cos(inputs[1]) + real(
                conj(Pg + 1j * Qg) / conj(inputs[0] * exp(1j * inputs[1]))) * Ra - imag(
                conj(Pg + 1j * Qg) / conj(inputs[0] * exp(1j * inputs[1]))) *(Xl)

    A = Var('A')
    B = Var("B")
    event_dict = {
        fn: Const(50.0),
        ws: Const(1.0),
        M: Const(3.5),
        D: Const(10.0),
        Rs: Const(0.003),
        Ra: Const(0.003),

        # Reactances
        Xd: Const(1.8),
        Xq: Const(1.7),
        Xd_prime: Const(0.3),
        Xq_prime: Const(0.55),
        Xd_2prime: Const(0.25),
        Xq_2prime: Const(0.35),
        Xl: Const(0.15),

        # Time constants
        Td0_prime: Const(8.0),
        Tq0_prime: Const(0.4),
        Td0_2prime: Const(0.03),
        Tq0_2prime: Const(0.05),

        A: Const(5.0),
        B: Const(1.0)
    }
    Xdaux =  ((Xd_prime  -Xd_2prime)/(Xd_prime -Xl)**2).simplify()
    Xdaux2 = ((Xd_prime  -Xd_2prime)/(Xd_prime -Xl)).simplify()
    Xdaux3 = ((Xd_2prime -Xl)/(Xd_prime -Xl)).simplify()

    Xqaux =  ((Xq_prime -Xq_2prime)/(Xq_prime -Xl)**2).simplify()
    Xqaux2 = ((Xq_prime -Xq_2prime)/(Xq_prime -Xl)).simplify()
    Xqaux3 = ((Xq_2prime -Xl)/(Xq_prime -Xl)).simplify()

    Eq_2prime_expr = Psid_prime*Xdaux2 + Eq_prime*Xdaux3
    Ed_2prime_expr = Psiq_prime*Xqaux2 + Ed_prime*Xqaux3
    Sat = 1 + Sa
    #Xd_2prime_sat = (Xd_2prime - Xl)/Sat + Xl
    #Xq_2prime_sat = (Xq_2prime - Xl)/Sat + Xl

    templ.block = Block(
        state_eqs=[
            (omega - Const(1)) * ws,  # dδ/dt
            (inputs[2] - Te - D * (omega - Const(1))) * (1 / M),  # dω/dt
            inputs[3] / Td0_prime - Sat * Eq1 / Td0_prime,  # dEq'/dt
            -Sat * Ed1 / Tq0_prime,  # dEd'/dt
            (-Psiq_prime + Iq*(Xq_prime - Xl)/Sat + Ed_prime),  # dPsiq'/dt
            (-Psid_prime + Id*(Xd_prime - Xl)/Sat + Eq_prime),  # dPsid'/dt
        ],
        state_vars=[delta, omega, Eq_prime, Ed_prime, Psiq_prime, Psid_prime],
        algebraic_eqs=[
            Vd - (-inputs[0] * sin(inputs[1] - delta)),  # from input block
            Vq - (inputs[0] * cos(inputs[1] - delta)),  # from input block
            Pg - (Vd * Id + Vq * Iq),  # from input block
            Qg - (Vq * Id - Vd * Iq),  # from input block
            Vd - (omega*Ed_2prime_expr + Iq * Xq_2prime_sat - Id * Ra),
            Vq - (omega*Eq_2prime_expr - Id * Xd_2prime_sat - Iq * Ra),
            Psid - (Eq_2prime_expr - Id * Xd_2prime_sat),
            Psiq - (-Ed_2prime_expr - Iq * Xq_2prime_sat),
            Te - (Psid * Iq - Psiq * Id),

            Ed1 - (Ed_prime - (Xq-Xq_prime)*(Iq/Sat - (Ed_prime - Psiq_prime + Iq*(Xq_prime - Xl)/Sat)*Xqaux)),
            Eq1 - (Eq_prime + (Xd-Xd_prime)*(Id/Sat + (Eq_prime - Psid_prime - Id*(Xd_prime - Xl)/Sat)*Xdaux)),
            
            # saturated resistance
            Sat * Xd_2prime_sat - (Xd_2prime - Xl + Xl * Sat),
            Sat * Xq_2prime_sat - (Xq_2prime - Xl + Xl * Sat),

            # flux
            V_dag - (Vd + Id * Ra - Iq * Xl),
            V_qag - (Vq + Iq * Ra + Id * Xl),
            omega * Psi_ag - ws * sqrt(V_qag * V_qag + V_dag * V_dag),
            # saturations (quadratic)
            Sa - A / 2 * ((Psi_ag - B) + sqrt((Psi_ag - B) ** 2 + Const(1e-4))) ** 2,

            #Eq1, Eq2, Ed1, Ed2 exciter
            IRPu - Eq1 * Sat,
        ],
        algebraic_vars=[Pg, Qg, Vd, Vq, Psid, Psiq, Te, Ed1, Eq1, Id, Iq,
                        # saturated resistance
                        Xq_2prime_sat, Xd_2prime_sat,
                        # flux
                        Sa, V_dag, V_qag, Psi_ag,
                        IRPu],
        init_eqs={
            #Air Gap Voltages and delta
            omega: Const(1),
            Psi_ag: sqrt(Viag_expr ** 2 + Vrag_expr ** 2),
            Sa: A / 2 * ((Psi_ag - B) + sqrt((Psi_ag - B) ** 2 + Const(1e-4))) ** 2,
            delta: atan(
                (inputs[0] * sin(inputs[1]) + imag(
                    conj(Pg + 1j * Qg) / conj(inputs[0] * exp(1j * inputs[1]))) * Ra + real(
                    conj(Pg + 1j * Qg) / conj(inputs[0] * exp(1j * inputs[1]))) *
                 ((Xq - Xl) / (Const(1) + Sa) + Xl)) /
                (inputs[0] * cos(inputs[1]) + real(
                    conj(Pg + 1j * Qg) / conj(inputs[0] * exp(1j * inputs[1]))) * Ra - imag(
                    conj(Pg + 1j * Qg) / conj(inputs[0] * exp(1j * inputs[1]))) *
                 ((Xq - Xl) / (Const(1) + Sa) + Xl))),

            #Saturated Resistances
            Xd_2prime_sat : (Xd_2prime - Xl + Xl * Sat)/Sat,
            Xq_2prime_sat : (Xq_2prime - Xl + Xl * Sat)/Sat,

            #Terminal Voltages and Intensities in dq frame
            Vd: -(inputs[0] * sin(inputs[1] - delta)),
            Vq: (inputs[0] * cos(inputs[1] - delta)),
            Id: (Pg*Vd + Qg*Vq)/(Vd**2 + Vq**2),
            Iq: (Pg*Vq - Qg*Vd)/(Vd**2 + Vq**2),
            V_dag : (Vd + Id * Ra - Iq * Xl),
            V_qag : (Vq + Iq * Ra + Id * Xl),

            #We initialize the states Eq', Ed', Psid', Psiq'
            Psid_prime: (Vq + Xd_2prime_sat*Id + Ra*Iq)/(omega) - (Xd_2prime - Xl)*Id/Sat,
            Ed_prime: (Xq - Xq_prime)*Iq/Sat,
            Psiq_prime: (Xq - Xl)*Iq/Sat,
            Eq_prime: Psid_prime + (Xq_prime - Xl)*Id/Sat,
            Ed1 : (Ed_prime - (Xq-Xq_prime)*(Iq/Sat - (Ed_prime - Psiq_prime + Iq*(Xq_prime - Xl)/Sat)*Xqaux)),
            Eq1 : (Eq_prime + (Xd-Xd_prime)*(Id/Sat + (Eq_prime - Psid_prime - Id*(Xd_prime - Xl)/Sat)*Xdaux)),

            Psid:(Eq_2prime_expr - Id * Xd_2prime_sat),
            Psiq:(-Ed_2prime_expr - Iq * Xq_2prime_sat),
            Te:(Psid * Iq - Psiq * Id),
            
            IRPu: Eq1 * (1 + Sa),
        },
        out_vars=[Pg, Qg, omega, IRPu, Te],
        in_vars=inputs,
        event_dict=event_dict,
        name="genqec"
    )

    return templ


def GovernorBuild(name: str = "") -> RmsModelTemplate:
    templ = RmsModelTemplate()

    parameters = {
        # Time constants
        "T1": Const(1.0),  # governor time constant (s)
        "T2": Const(1.0),  # reheater time constant (s)
        "T3": Const(10.0),  # crossover time constant (s)
        "T4": Const(0.2),  # lead/lag constant (s)
        "T5": Const(0.5),  # lead/lag constant (s)
        "T6": Const(0.1),  # lead/lag constant (s)
        "T7": Const(0.05),  # lead/lag constant (s)

        # Steam fractions (distribution factors)
        "K1": Const(0.5),
        "K2": Const(0.5),
        "K3": Const(0.0),
        "K4": Const(0.0),
        "K5": Const(0.0),
        "K6": Const(0.0),
        "K7": Const(0.0),
        "K8": Const(0.0),
    }

    inputs = [Var("omega_"), Var('Te_')]

    # ______________________________________________________________________________________
    #                                    variables
    # ______________________________________________________________________________________

    Tm = Var("Tm")  # Mechanical power input (pu
    et = Var("et")

    # reference
    Pm_ref = Var('Pm_ref')
    algebraic_eqs = []
    algebraic_vars = []

    # ______________________________________________________________________________________
    #                                    parameters
    # ______________________________________________________________________________________

    # Gains and limits
    K = Var("K")  # governor gain (inverse droop)
    Pmax = Var("Pmax")  # max mechanical power (pu)
    Pmin = Var("Pmin")  # min mechanical power (pu)
    Uc = Var("Uc")  # max valve closing rate (pu/s)
    Uo = Var("Uo")  # max valve opening rate (pu/s)
    T_aux = Var("T_aux")

    # Control
    Kp = Var("Kp")
    Ki = Var("Ki")
    omega_ref = Var('omega_ref')
    p0 = Var('p0')
    P0 = Var('P0')

    events_dict = {
        # control parameters
        Pm_ref: Const(UNDEFINED),
        Kp: Const(-0.01),
        Ki: Const(-0.01),
        p0: Const(1.0),
        P0: Const(0.01),
        omega_ref: Const(1),
        # Governor parameters
        K: Const(10.0),  # governor gain (inverse droop)
        Pmax: Const(12.0),  # max mechanical power (pu)
        Pmin: Const(-1.0),  # min mechanical power (pu)
        Uc: Const(-0.5),  # max valve closing rate (pu/s)
        Uo: Const(0.5),  # max valve opening rate (pu/s)
        T_aux: Const(0.0),

    }
    controller_block = Block(
        state_eqs=[
            P0 * (inputs[0] - omega_ref)
        ],
        state_vars=[et],
        algebraic_eqs=[
            T_aux - (Kp * (inputs[0] - omega_ref) + Ki * et),
        ],
        algebraic_vars=[T_aux],
    )
    controller_block = Block()

    u1 = inputs[0] - omega_ref
    lead_lag_block, y1, x1 = tf_to_diffblock_with_output(
        num=np.array([1, parameters["T2"]]),
        den=np.array([1, parameters["T1"]]),
        x=u1,
        name='gov0',
    )

    # ==============================
    # First Feed back Loop
    y2_3 = Var('y2_3_gov')
    algebraic_vars.append(y2_3)
    x2 = Pm_ref - K * y1 - y2_3

    y2 = x2 * (1 / parameters["T3"])
    y2_1 = hard_sat(y2, Uc, Uo)
    tf1, y2_2, u_gov1 = tf_to_diffblock_with_output(
        num=np.array([1]),
        den=np.array([0, 1]),
        x=y2_1,
        name='gov1',
    )
    algebraic_eqs.append(y2_3 - hard_sat(y2_2, Pmin, Pmax))

    # ==============================
    # We compute different outputs for every tf
    tf2, y3_1 = tf_to_diffblock(
        num=np.array([1]),
        den=np.array([1, parameters["T4"]]),
        x=y2_3,
        name='gov2',
    )
    tf3, y3_2 = tf_to_diffblock(
        num=np.array([1]),
        den=np.array([1, parameters["T5"]]),
        x=y3_1,
        name='gov3',
    )
    tf4, y3_3 = tf_to_diffblock(
        num=np.array([1]),
        den=np.array([1, parameters["T6"]]),
        x=y3_2,
        name='gov4',
    )
    tf5, y3_4 = tf_to_diffblock(
        num=np.array([1]),
        den=np.array([1, parameters["T7"]]),
        x=y3_3,
        name='gov5',
    )

    u = parameters["K1"] * y3_1 + parameters["K2"] * y3_2 + parameters["K3"] * y3_3 + \
        parameters["K4"] * y3_4
    aux_block = Block(
        algebraic_eqs=[u - Tm] + algebraic_eqs,
        algebraic_vars=[Tm] + algebraic_vars,
    )

    templ.block = Block(
        children=[lead_lag_block, tf1, tf2, tf3, tf4, tf5, aux_block, controller_block],
        out_vars=[Tm],
        in_vars=inputs,
        event_dict=events_dict,
        name="governor",

        init_eqs={
            Pm_ref: inputs[1],
            y1: Const(0.0),
            x1: inputs[0] - omega_ref,
            u_gov1: Const(0),
            y2_2: Pm_ref,
            y2_3: Pm_ref,
            y3_1: Pm_ref,
            y3_2: Pm_ref,
            y3_3: Pm_ref,
            y3_4: Pm_ref,
            Tm: Pm_ref
        }
    )

    return templ


def StabilizerBuild(name: str = "") -> RmsModelTemplate:
    templ = RmsModelTemplate()

    parameters = {
        # Stabilizer parameters
        "A1": Const(1.0),  # notch filter coefficient 1
        "A2": Const(1.0),  # notch filter coefficient 2
        "t1": Const(0.1),  # lead time constant
        "t2": Const(0.02),  # lag time constant
        "t3": Const(0.02),  # lag time constant
        "t4": Const(0.1),  # second lag time constant
        "t5": Const(10.0),  # washout time constant
        "t6": Const(0.02),  # transducer time constant
    }

    # input variables
    # omega: omega from generator

    inputs = [Var("omega_")]

    # PSS parameters with typical values

    Ks = Var("Ks")  # stabilizer gain
    VPssMaxPu = Var("VPssMaxPu")  # max stabilizer output
    VPssMinPu = Var("VPssMinPu")  # min stabilizer output
    SNom = Var("SNom")  # nominal apparent power

    events_dict = {
        # Stabilizer parameters
        Ks: Const(20.0),  # stabilizer gain
        VPssMaxPu: Const(1.0),  # max stabilizer output
        VPssMinPu: Const(-1.0),  # min stabilizer output
        SNom: Const(1.0),  # nominal apparent power
    }

    # variables
    Vpss = Var('V_pss')

    vars_block = Block(
        algebraic_vars=[],
    )

    tf, y = tf_to_diffblock(
        num=np.array([1.0]),
        den=np.array([1, parameters["t6"]]),
        x=inputs[0],
        name='stabilizer1',
    )

    tf2, y2 = tf_to_diffblock(
        num=np.array([0, Ks * parameters["t5"]]),
        den=np.array([1, parameters["t5"]]),
        x=y,
        name='stabilizer2',
    )
    tf3, y3 = tf_to_diffblock(
        num=np.array([1]),
        den=np.array([1, parameters["A1"], parameters["A2"]]),
        x=y2,
        name='stabilizer3',
    )
    tf4, y4 = tf_to_diffblock(
        num=np.array([1, parameters["t1"]]),
        den=np.array([1, parameters["t2"]]),
        x=y3,
        name='stabilizer4',
    )
    tf5, y5 = tf_to_diffblock(
        num=np.array([1, parameters["t3"]]),
        den=np.array([1, parameters["t4"]]),
        x=y4,
        name='stabilizer5',
    )

    algebraic_eqs = list()
    algebraic_eqs.append(hard_sat(y5, VPssMinPu, VPssMaxPu) - Vpss)
    block_1 = Block()

    templ.block = Block(
        children=[tf, tf2, tf3, tf4, tf5],
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=[Vpss],
        in_vars=inputs,
        out_vars=[Vpss],
        event_dict=events_dict,
        name="stabilizer",

        init_eqs={
            Vpss: Const(0.0),
            y: Const(1.0),
            y2: Const(0.0),
            y3: Const(0.0),
            y4: Const(0.0),
            y5: Const(0.0),
        }
    )

    templ.block.add(vars_block)
    templ.block.add(block_1)

    return templ


def ExciterBuild(name: str = "") -> RmsModelTemplate:
    """
    
    :param self: 
    :param name: 
    :return: 
    """
    templ = RmsModelTemplate()

    parameters = {
        # Exciter (AVR) parameters
        "Ka": Const(50.0),  # AVR gain
        "Kf": Const(0.03),  # exciter rate feedback gain

        # Time constants
        "tA": Const(0.02),  # AVR time constant (s)
        "tB": Const(10.0),  # lead-lag: lag time constant (s)
        "tC": Const(1.0),  # lead-lag: lead time constant (s)
        "tE": Const(0.5),  # exciter field time constant (s)
        "tF": Const(1.0),  # rate feedback time constant (s)
        "tR": Const(0.08),  # stator voltage filter time constant (s)

        # Exciter submodel parameters
        "Kc": Const(0.2),  # rectifier loading factor
        "Kd": Const(0.1),  # demagnetizing factor
        "Ke": Const(1.0),  # field resistance constant
        "Kfd": Const(0.5),  # converting factor

    }

    # input variables
    # IRPu: rotor current (pu) ???
    # Va: measured stator voltage (from generator) (pu)
    # Vpss: output from power system stabilizer (pu)

    inputs = [Var("IRPu_"), Var("Va_"), Var("Vpss_")]

    algebraic_vars = []

    # ______________________________________________________________________________________
    #                                    variables
    # ______________________________________________________________________________________

    Vf = Var("Vf")
    Efe = Var('Efe')
    UsRefPu = Var(name="UsRefPu")  # reference voltage (pu)

    # Exciter internal variables
    VeMaxPu = Var('VeMaxPu')
    u_aux = Var('u_aux')

    # ______________________________________________________________________________________
    #                                    parameters
    # ______________________________________________________________________________________

    # ---- Exciter (AVR) parameters ----
    AEz = Var("AEz")  # saturation gain
    BEz = Var("BEz")  # saturation exponential coefficient
    EfeMaxPu = Var("EfeMaxPu")  # max exciter field voltage (pu)
    EfeMinPu = Var("EfeMinPu")  # min exciter field voltage (pu)

    # ---- Exciter (AVR) time constants and limits ----

    TolLi = Var("TolLi")  # limiter crossing tolerance (fraction)

    VaMaxPu = Var("VaMaxPu")  # AVR output max (pu)
    VaMinPu = Var("VaMinPu")  # AVR output min (pu)
    VeMinPu = Var("VeMinPu")  # min exciter output voltage (pu)
    VfeMaxPu = Var("VfeMaxPu")  # max exciter field current signal (pu)

    # exciter submodel parameters
    AEx = Var("AEx")  # Gain of saturation function
    BEx = Var("BEx")  # Exponential coefficient of saturation function
    Se_threshold = Var("Se_threshold")  # Exponential coefficient of saturation function
    ToLLi = Var("ToLLi")  # Tolerance on limit crossing
    VeMinPu_submodel = Var("VeMinPu_submodel")  # Minimum exciter output voltage (pu)
    VfeMaxPu_submodel = Var("VfeMaxPu_submodel")  # Maximum exciter field current signal (pu)

    events_dict = {
        # Exciter (AVR) parameters
        UsRefPu: Const(UNDEFINED),  # reference voltage (pu)
        AEz: Const(0.02),  # saturation gain
        BEz: Const(1.5),  # saturation exponential coefficient
        Se_threshold: Const(1.0),  # saturation threshold
        EfeMaxPu: Const(15.0),  # max exciter field voltage (pu)
        EfeMinPu: Const(-5.0),  # min exciter field voltage (pu)

        # Time constants
        TolLi: Const(0.05),  # limiter crossing tolerance (fraction)

        # Limits
        VaMaxPu: Const(20.0),  # AVR output max (pu)
        VaMinPu: Const(-10.0),  # AVR output min (pu)
        VeMinPu: Const(-1.0),  # min exciter output voltage (pu)
        VfeMaxPu: Const(5.0),  # max exciter field current signal (pu)

        # Exciter submodel parameters
        AEx: Const(0.02),  # saturation gain
        BEx: Const(0.01),  # exponential coeff of saturation function
        ToLLi: Const(0.05),  # tolerance on limit crossing
        VeMinPu_submodel: Const(-5.1),  # minimum exciter output voltage
        VfeMaxPu_submodel: Const(5.0),  # max exciter field current signal
    }
    # ---Internal Blocks---
    tf1, y1 = tf_to_diffblock(
        num=np.array([1]),
        den=np.array([1, parameters["tR"].value]),
        x=inputs[1],
        name='exciter1',
    )  # filtered stator voltage

    # error1 = UPssPu - y + UsRefPu
    error1 = (- y1 + UsRefPu) + inputs[2]
    tf2, y2 = tf_to_diffblock(
        num=np.array([0, parameters["Kf"].value]),
        den=np.array([1, parameters["tF"].value]),
        x=Vf,
        name='exciter2',
    )
    error2 = error1 - y2

    tf3, y3 = tf_to_diffblock(
        num=np.array([1, parameters["tC"].value]),
        den=np.array([1, parameters["tB"].value]),
        x=error2,
        name='exciter3',
    )
    tf4, y4 = tf_to_diffblock(
        num=np.array([parameters["Ka"].value]),
        den=np.array([1, parameters["tA"].value]),
        x=y3,
        name='exciter4',
    )

    y5 = hard_sat(y4, VaMinPu, VaMaxPu)

    min_const = max(events_dict[VaMinPu].value, events_dict[EfeMinPu].value)
    max_const = min(events_dict[VaMaxPu].value, events_dict[EfeMaxPu].value)
    y6 = hard_sat(y4, min_const, max_const)

    # exciter submodel

    algebraic_eqs_submodel = []
    algebraic_vars_submodel = []

    x1 = VfeMaxPu - inputs[0] * parameters["Kd"]
    error1 = Efe - (inputs[0] * parameters["Kd"] + u_aux)

    tf1_sub, Ve_presat = tf_to_diffblock(
        num=np.array([1]),
        den=np.array([0, parameters["tE"].value]),
        x=error1,
        name='subexciter1',
    )

    Ve = hard_sat(Ve_presat, VeMinPu, Const(1000))
    Se_threshold = parameters['Ke']
    aux_expr = parameters['Ke']*Ve + AEx*Ve*(exp(BEx*(Ve-Se_threshold))- Const(1))*heaviside(Ve-Se_threshold) 
    algebraic_eqs_submodel.append(u_aux - aux_expr)
    algebraic_eqs_submodel.append(VeMaxPu * u_aux - x1*Ve)

    f_input = Var('f_input')
    f_output = Var('f_output')
    f_output_res = f_exc(f_input)
    algebraic_vars_submodel.append(f_input)
    algebraic_vars_submodel.append(f_output)
    algebraic_eqs_submodel.append(f_input * Ve - inputs[0] * parameters["Kc"])

    algebraic_eqs_submodel.append(Vf - f_output * Ve)
    algebraic_eqs_submodel.append(f_output_res - f_output)

    aux_model = Block(
        algebraic_eqs=algebraic_eqs_submodel,
        algebraic_vars=[u_aux, VeMaxPu, Vf] + algebraic_vars_submodel
    )

    exciter_submodel = Block(children=[tf1_sub, aux_model])

    linking_block = Block(
        algebraic_eqs=[y6 - Efe],
        algebraic_vars=[Efe] + algebraic_vars,
    )

    u_exciter3 = find_name_in_block('u_exciter3', tf3)
    u_subexciter1 = find_name_in_block('u_subexciter1', tf1_sub)
    y_subexciter1 = find_name_in_block('y_subexciter1', tf1_sub)

    Ve_sat = hard_sat(y_subexciter1, VeMinPu, VeMaxPu)
    Ve = hard_sat(y_subexciter1, VeMinPu, Const(1000))
    aux_expr = parameters['Ke']*Ve + AEx*Ve*(exp(BEx*(Ve-Se_threshold))- Const(1))*heaviside(Ve-Se_threshold) 

    templ.block = Block(
        children=[tf1, tf2, tf3, tf4, exciter_submodel, linking_block],
        out_vars=[Vf],
        in_vars=inputs,
        event_dict=events_dict,
        init_eqs={
            Vf:inputs[0],
            y_subexciter1: inputs[0]*(1/f_exc(inputs[0] * parameters["Kc"]/y_subexciter1) ),
            VeMaxPu: (VfeMaxPu -inputs[0]*parameters["Kd"])/(parameters["Ke"] + AEx*(exp(BEx*(Ve-Se_threshold))-Const(1))*heaviside(Ve-Se_threshold)),
            u_aux: aux_expr,
            Efe: inputs[0]*parameters["Kd"] + u_aux,
            UsRefPu: Efe/parameters['Ka'] + inputs[1],
            y1: inputs[1],
            y2: Const(0.0),
            y3: -y1 + UsRefPu,
            u_exciter3: y3,
            y4: y3*parameters["Ka"],
            u_subexciter1: Const(0.0),
            f_input: parameters['Kc']*inputs[0]/y_subexciter1,
            f_output: f_exc(f_input),   
        },
    )

    return templ


def get_complete_generator_template(name="complete generator rms template") -> RmsModelTemplate:
    """
    
    :return: 
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name

    # generate models
    genqec_mdl = GenqecBuild().block
    exciter_mdl = ExciterBuild().block
    governor_mdl = GovernorBuild().block
    stabilizer_mdl = StabilizerBuild().block

    # connect models
    genqec_mdl.connect([genqec_mdl.in_vars[3]], [exciter_mdl.out_vars[0]])
    exciter_mdl.connect([exciter_mdl.in_vars[0]], [genqec_mdl.out_vars[3]])
    exciter_mdl.connect([exciter_mdl.in_vars[1]], [genqec_mdl.in_vars[1]])

    stabilizer_mdl.connect([stabilizer_mdl.in_vars[0]], [genqec_mdl.out_vars[2]])

    exciter_mdl.connect([exciter_mdl.in_vars[2]], [stabilizer_mdl.out_vars[0]])

    genqec_mdl.connect([genqec_mdl.in_vars[2]], [governor_mdl.out_vars[0]])

    governor_mdl.connect([governor_mdl.in_vars[0]], [genqec_mdl.out_vars[2]])

    governor_mdl.connect([governor_mdl.in_vars[1]], [genqec_mdl.out_vars[4]])

    templ.block.children.append(governor_mdl)
    templ.block.children.append(stabilizer_mdl)
    templ.block.children.append(exciter_mdl)
    templ.block.children.append(genqec_mdl)

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Vm: genqec_mdl.in_vars[0],
        VarPowerFlowRefferenceType.Va: genqec_mdl.in_vars[1],
        VarPowerFlowRefferenceType.P: genqec_mdl.out_vars[0],
        VarPowerFlowRefferenceType.Q: genqec_mdl.out_vars[1],
    }

    return templ
