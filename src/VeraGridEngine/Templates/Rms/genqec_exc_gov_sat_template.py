# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, Expr, VarPowerFlowRefferenceType, tf_to_diffblock, \
    tf_to_block_with_states, tf_to_diffblock_with_states, hard_sat, DiffBlock
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, real, imag, conj, angle, exp, log, abs, UndefinedConst, \
    sqrt, atan, f_exc


class GenqecExcGovSat(RmsModelTemplate):

    def __init__(self, name: str = "rms_genqec_exc_gov_sat_template"):
        super().__init__(name=name)


        self.tpe: DeviceType = DeviceType.GeneratorDevice

        # ______________________________________________________________________________________
        #                                    variables
        # ______________________________________________________________________________________

        self.Vm: Var = Var('Vm_placeholder')
        self.Va: Var = Var('Va_placeholder')

        self.Pg: Var = Var('P_g')
        self.Qg: Var = Var('Q_g')

        #Variables
        ## generator
        ### state variables
        self.delta = Var("delta")
        self.omega = Var("omega")
        self.Eq1 = Var("Eq1" )  # internal emf behind Xd'
        self.Ed1 = Var("Ed1")
        self.Eq2 = Var("Eq2")
        self.Ed2 = Var("Ed2")
        self.Eq_prime = Var("Eq_prime")  # transient voltage q-axis
        self.Ed_prime = Var("Ed_prime")  # transient voltage d-axis
        self.Eq_2prime = Var("Eq_2prime")  # subtransient voltage q-axis
        self.Ed_2prime = Var("Ed_2prime")  # subtransient voltage d-axis

        ### algebraic variables
        self.Psid = Var("psid")
        self.Psiq = Var("psiq")
        self.Id = Var("i_d")
        self.Iq = Var("i_q")
        self.Vd = Var("v_d")
        self.Vq = Var("v_q")
        self.Te = Var("Te")
        self.IRPu = Var("IRPu")

        ### Saturated resistances
        self.Xd_sat = Var('Xd_sat')
        self.Xq_sat = Var('Xq_sat')
        self.Xd_prime_sat = Var('Xd_prime_sat')
        self.Xq_prime_sat = Var('Xq_prime_sat')
        self.Xd_2prime_sat = Var('Xd_2prime_sat')
        self.Xq_2prime_sat = Var('Xq_2prime_sat')
        self.Ed2_coef = Var('Ed2_coef')
        self.Eq2_coef = Var('Eq2_coef')
        self.Sa = Var('Sa')
        self.V_qag = Var('V_qag')
        self.V_dag = Var('V_dag')
        self.Psi_ag = Var('Psi_ag')

        ### Saturation factors
        self.Sat_d = Var('Sat_d')
        self.Sat_q = Var('Sat_q')

        # governor
        self.Tm = Var("Tm")  # Mechanical power input (pu
        self.et = Var("et")
        # reference
        self.Pm_ref = Var('Pm_ref')

        # stabilizer
        self.Vpss = Var('V_pss')

        # exciter
        self.Vf = Var("Vf")
        self.Efe = Var('Efe')
        self.UsRefPu = Var("UsRefPu")  # reference voltage (pu)

        # Exciter internal variables
        self.VeMaxPu = Var('VeMaxPu')
        self.u_aux = Var('u_aux')

        # ______________________________________________________________________________________
        #                                    event parameters
        # ______________________________________________________________________________________

        ## generator
        self.fn = Var('fn')  # system frequency [Hz] # not specified in the generator, must be specified in multicircuit, like Sbase...
        self.ws = Var('ws')  # synchronous speed [rad/s]
        self.M = Var('M')  # inertia constant
        self.D = Var('D')  # damping (optional)
        self.Rs = Var('Rs')  # stator resistance
        self.Ra = Var('Ra')  # armature resistance (if distinct)

        # Reactances
        self.Xd = Var('Xd')
        self.Xq = Var('Xq')
        self.Xd_prime = Var('Xd_prime')
        self.Xq_prime = Var('Xq_prime')
        self.Xd_2prime = Var('Xd_2prime')
        self.Xq_2prime = Var('Xq_2prime')
        self.Xl = Var('Xl')

        # Time constants
        self.Td0_prime = Var('Td0_prime')
        self.Tq0_prime = Var('Tq0_prime')
        self.Td0_2prime = Var('Td0_2prime')
        self.Tq0_2prime = Var('Tq0_2prime')

        self.A = Var('A') # saturation speed RMS/EMT
        self.B = Var("B") # saturation threshold RMS/EMT

        # governor
        # Gains and limits
        self.K = Var("K")  # governor gain (inverse droop)
        self.Pmax = Var("Pmax")  # max mechanical power (pu)
        self.Pmin = Var("Pmin")  # min mechanical power (pu)
        self.Uc = Var("Uc")  # max valve closing rate (pu/s)
        self.Uo = Var("Uo")  # max valve opening rate (pu/s)
        self.T_aux = Var("T_aux")

        # Control
        self.Kp = Var("Kp")
        self.Ki = Var("Ki")
        self.omega_ref = Var('omega_ref')
        self.p0 = Var('p0')
        self.P0 = Var('P0')

        #stabilizer
        self.Ks = Var("Ks")  # stabilizer gain
        self.VPssMaxPu = Var("VPssMaxPu")  # max stabilizer output
        self.VPssMinPu = Var("VPssMinPu")  # min stabilizer output
        self.SNom = Var("SNom")  # nominal apparent power

        # ---- Exciter (AVR) parameters ----
        self.AEz = Var("AEz")  # saturation gain
        self.BEz = Var("BEz")  # saturation exponential coefficient
        self.EfeMaxPu = Var("EfeMaxPu")  # max exciter field voltage (pu)
        self.EfeMinPu = Var("EfeMinPu")  # min exciter field voltage (pu)

        # ---- Exciter (AVR) time constants and limits ----
        self.TolLi = Var("TolLi")  # limiter crossing tolerance (fraction)

        self.VaMaxPu = Var("VaMaxPu")  # AVR output max (pu)
        self.VaMinPu = Var("VaMinPu")  # AVR output min (pu)
        self.VeMinPu = Var("VeMinPu")  # min exciter output voltage (pu)
        self.VfeMaxPu = Var("VfeMaxPu")  # max exciter field current signal (pu)

        # exciter submodel parameters
        self.AEx = Var("AEx")  # Gain of saturation function
        self.BEx = Var("BEx")  # Exponential coefficient of saturation function
        self.ToLLi = Var("ToLLi")  # Tolerance on limit crossing
        self.VeMinPu_submodel = Var("VeMinPu_submodel")  # Minimum exciter output voltage (pu)
        self.VfeMaxPu_submodel = Var("VfeMaxPu_submodel")  # Maximum exciter field current signal (pu)
        self.F_rectifier = Var("F_rectifier")  # Rectifier factor

        # ______________________________________________________________________________________
        #                                    event_dict
        # ______________________________________________________________________________________

        self.event_dict = {
            #generator
            self.fn: Const(50.0),
            self.ws: Const(1.0),
            self.M: Const(3.5),
            self.D: Const(10.0),
            self.Rs: Const(0.003),
            self.Ra: Const(0.003),

            # Reactances
            self.Xd: Const(1.8),
            self.Xq: Const(1.7),
            self.Xd_prime: Const(0.3),
            self.Xq_prime: Const(0.55),
            self.Xd_2prime: Const(0.25),
            self.Xq_2prime: Const(0.25),
            self.Xl: Const(0.15),

            # Time constants
            self.Td0_prime: Const(8.0),
            self.Tq0_prime: Const(0.4),
            self.Td0_2prime: Const(0.03),
            self.Tq0_2prime: Const(0.05),

            self.A: Const(5.0),
            self.B: Const(1.0),

            # governor
            # control parameters
            self.Kp: Const(-0.01),
            self.Ki: Const(-0.01),
            self.p0: Const(1.0),
            self.P0: Const(0.01),
            self.omega_ref: Const(1),

            # Governor parameters
            self.K: Const(10.0),  # governor gain (inverse droop)
            self.Pmax: Const(2.0),  # max mechanical power (pu)
            self.Pmin: Const(0.0),  # min mechanical power (pu)
            self.Uc: Const(-0.1),  # max valve closing rate (pu/s)
            self.Uo: Const(0.1),  # max valve opening rate (pu/s)
            self.T_aux: Const(0.0),

            # Stabilizer parameters
            self.Ks: Const(20.0),  # stabilizer gain
            self.VPssMaxPu: Const(1.0),  # max stabilizer output
            self.VPssMinPu: Const(-1.0),  # min stabilizer output
            self.SNom: Const(1.0),  # nominal apparent power

            # Exciter (AVR) parameters
            self.AEz: Const(0.02),  # saturation gain
            self.BEz: Const(1.5),  # saturation exponential coefficient
            self.EfeMaxPu: Const(15.0),  # max exciter field voltage (pu)
            self.EfeMinPu: Const(-5.0),  # min exciter field voltage (pu)

            # Time constants
            self.TolLi: Const(0.05),  # limiter crossing tolerance (fraction)

           # Limits
            self.VaMaxPu: Const(20.0),  # AVR output max (pu)
            self.VaMinPu: Const(-10.0),  # AVR output min (pu)
            self.VeMinPu: Const(-1.0),  # min exciter output voltage (pu)
            self.VfeMaxPu: Const(5.0),  # max exciter field current signal (pu)

            # Exciter submodel parameters
            self.AEx: Const(0.02),  # saturation gain
            self.BEx: Const(-0.01),  # exponential coeff of saturation function
            self.ToLLi: Const(0.05),  # tolerance on limit crossing
            self.VeMinPu_submodel: Const(-0.1),  # minimum exciter output voltage
            self.VfeMaxPu_submodel: Const(5.0),  # max exciter field current signal
            self.F_rectifier: Const(1.0),  # rectifier factor (1=DC, 0.5=AC)
        }

        # ______________________________________________________________________________________
        #                                    parameters
        # ______________________________________________________________________________________
        #
        self.parameters = {
            # Governor
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

            # Stabilizer parameters
            "A1": Const(1.0),  # notch filter coefficient 1
            "A2": Const(1.0),  # notch filter coefficient 2
            "t1": Const(0.1),  # lead time constant
            "t2": Const(0.02),  # lag time constant
            "t3": Const(0.02),  # lag time constant
            "t4": Const(0.1),  # second lag time constant
            "t5": Const(10.0),  # washout time constant
            "t6": Const(0.02),  # transducer time constant

            # Exciter (AVR) parameters
            "Ka": Const(200.0),  # AVR gain
            "Kf": Const(0.03),  # exciter rate feedback gain

            # Time constants
            "tA": Const(0.02),  # AVR time constant (s)
            "tB": Const(10.0),  # lead-lag: lag time constant (s)
            "tC": Const(1.0),  # lead-lag: lead time constant (s)
            "tE": Const(0.5),  # exciter field time constant (s)
            "tF": Const(1.0),  # rate feedback time constant (s)
            "tR": Const(0.02),  # stator voltage filter time constant (s)

            # Exciter submodel parameters
            "Kc": Const(0.2),  # rectifier loading factor
            "Kd": Const(0.1),  # demagnetizing factor
            "Ke": Const(1.0),  # field resistance constant
        }

    def get_block(self):
        """

        :return:
        """
        generator_model = Block(
            state_eqs=[
                #generator
                (self.omega - Const(1)) * self.ws,  # dδ/dt
                (self.Tm - self.Te - self.D * (self.omega - Const(1))) * (1 / self.M),  # dω/dt
                self.Vf / self.Td0_prime - self.Sat_q * self.Eq1 / self.Td0_prime,  # dEq'/dt
                -self.Sat_q * self.Ed1 / self.Tq0_prime,  # dEd'/dt
                self.Eq2_coef * (-self.Eq2),  # dEq''/dt
                self.Ed2_coef * (-self.Ed2),  # dEd''/dt
                #governor
                self.P0 * (self.omega - self.omega_ref)
            ],
            state_vars=[
                        #generator
                        self.delta, self.omega, self.Eq_prime, self.Ed_prime, self.Eq_2prime, self.Ed_2prime,
                        #governor
                        self.et],
            algebraic_eqs=[
                #generator
                self.Vd - (-self.Tm * sin(self.Vf - self.delta)),  # from input block
                self.Vq - (self.Tm * cos(self.Vf - self.delta)),  # from input block
                self.Pg - (self.Vd * self.Id + self.Vq * self.Iq),  # from input block
                self.Qg - (self.Vq *self.Id - self.Vd * self.Iq),  # from input block
                self.Vd - (self.omega * self.Ed_2prime + self.Iq * self.Xq_2prime_sat - self.Id * self.Ra),
                self.Vq - (self.omega * self.Eq_2prime - self.Id * self.Xd_2prime_sat - self.Iq * self.Ra),
                self.Psid - (self.Eq_prime - self.Id * self.Xd_2prime_sat),
                self.Psiq - (-self.Ed_prime - self.Iq * self.Xq_2prime_sat),
                self.Te - (self.Psid * self.Iq - self.Psiq * self.Id),
                (self.Xd_sat - self.Xd_prime_sat) * self.Eq1 - (
                        (self.Xd_sat - self.Xd_prime_sat) * self.Eq_2prime + (self.Eq_prime - self.Eq_2prime) * (self.Xd_sat - self.Xd_2prime_sat)),
                # Eq1 definition
                (self.Xq_sat - self.Xq_prime_sat) * self.Ed1 - (
                        (self.Xq_sat - self.Xq_prime_sat) * self.Ed_2prime + (self.Ed_prime - self.Ed_2prime) * (self.Xq_sat - self.Xq_2prime_sat)),
                # Ed1 definition
                (self.Xd_sat - self.Xd_2prime_sat) * self.Eq2 - (-1) * (
                        (self.Eq_prime - self.Eq_2prime) * (self.Xd_sat - self.Xd_prime_sat) + self.Id * (self.Xd_sat - self.Xd_2prime_sat) ** 2),
                # Ed2 definition
                (self.Xq_sat - self.Xq_2prime_sat) * self.Ed2 - (-1) * (
                        (self.Ed_prime - self.Ed_2prime) * (self.Xq_sat - self.Xq_prime_sat) + self.Iq * (self.Xq_sat - self.Xq_2prime_sat) ** 2),
                # Eq2 definition
                self.Eq2_coef * (self.Tq0_2prime * (self.Xq_sat - self.Xq_2prime_sat)) - (self.Xq_prime_sat - self.Xq_2prime_sat) * self.Sat_q,
                self.Ed2_coef * (self.Td0_2prime * (self.Xd_sat - self.Xd_2prime_sat)) - (self.Xd_prime_sat - self.Xd_2prime_sat) * self.Sat_d,
                # saturated resistance
                self.Sat_d * self.Xd_2prime_sat - (self.Xd_2prime - self.Xl + self.Xl * self.Sat_d),
                self.Sat_q * self.Xq_2prime_sat - (self.Xq_2prime - self.Xl + self.Xl * self.Sat_q),
                self.Sat_d * self.Xd_prime_sat - (self.Xd_prime - self.Xl + self.Xl * self.Sat_d),
                self.Sat_q * self.Xq_prime_sat - (self.Xq_prime - self.Xl + self.Xl * self.Sat_q),
                self.Sat_d * self.Xd_sat - (self.Xd - self.Xl + self.Xl * self.Sat_d),
                self.Sat_q * self.Xq_sat - (self.Xq - self.Xl + self.Xl * self.Sat_q),
                # flux
                self.V_dag - (self.Vd - self.Ra * self.Id + self.Xq_2prime_sat * self.Iq + self.Iq * self.Ra + self.Id * self.Xl),
                self.V_qag - (self.Vq - self.Ra * self.Iq + self.Xd_2prime_sat * self.Id + self.Id * self.Ra - self.Iq * self.Xl),
                (self.omega) * self.Psi_ag - (self.ws) * sqrt(self.V_qag * self.V_qag + self.V_dag * self.V_dag),
                self.Sat_d - (Const(1) + self.Sa),
                self.Sat_q - (Const(1) + self.Sa),
                # saturations (quadratic)
                self.Sa - self.A * ((self.Psi_ag - self.B) + sqrt((self.Psi_ag - self.B) ** 2 + Const(1e-4))),
                self.IRPu - self.Eq1 * (1 + self.Sa),
                #governor
                self.T_aux - (self.Kp * (self.omega - self.omega_ref) + self.Ki * self.et)

            ],
            algebraic_vars=[
                            #generator
                            self.Pg, self.Qg, self.Vd, self.Vq, self.Psid, self.Psiq, self.Ed2_coef, self.Eq2_coef, self.Te, self.Ed1, self.Eq1, self.Ed2, self.Eq2, self.Id, self.Iq,
                            # saturated resistance
                            self.Xq_sat, self.Xd_sat, self.Xq_prime_sat, self.Xd_prime_sat, self.Xq_2prime_sat, self.Xd_2prime_sat,
                            # flux
                            self.Sa, self.V_dag, self.V_qag, self.Sat_d, self.Sat_q, self.Psi_ag, self.IRPu,
                            #governor
                            self.T_aux,
                            ],
            init_eqs={
                self.omega: Const(0),
                self.V_dag: self.Vm * sin(self.Va) + imag(
                    conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) * self.Ra + real(
                    conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) * self.Xl,
                self.V_qag: self.Vm * cos(self.Va) + real(
                    conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) * self.Ra + imag(
                    conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) * self.Xl,
                self.Psi_ag: sqrt(self.V_dag ** 2 + self.V_qag ** 2),
                self.Sa: self.A * (self.Psi_ag - self.B) ** 2,
                self.delta: atan(
                    (self.Vm * sin(self.Va) + imag(
                        conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) * self.Ra + real(
                        conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) *
                     ((self.Xq - self.Xl) / (Const(1) + self.Sa) + self.Xl)) /
                    (self.Vm * cos(self.Va) + real(
                        conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) * self.Ra + imag(
                        conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) *
                     ((self.Xq - self.Xl) / (Const(1) + self.Sa) + self.Xl))),
                self.Vd: (self.Vm * sin(self.delta - self.Va)),
                self.Vq: (self.Vm * cos(self.delta - self.Va)),
                self.Id: real(conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) * sin(self.delta) - real(
                    conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) * cos(self.delta),
                self.Iq: real(conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) * cos(self.delta) + real(
                    conj(self.Pg + 1j * self.Qg) / conj(self.Vm * exp(1j * self.Va))) * sin(self.delta),
                self.Ed_prime: (self.Xq - self.Xq_prime) * self.Iq / (Const(1) + self.Sa),
                self.Eq_prime: self.Ed_prime + (self.Xq_prime - self.Xl) * (self.Iq / (Const(1) + self.Sa)) + (self.Xq_prime - self.Xl) * (
                            self.Iq / (Const(1) + self.Sa)),
                self.Eq_2prime: self.Vd,
                self.Ed_2prime: self.Vq,
            })

        # governor_blocks:
        algebraic_eqs_gov = []
        algebraic_vars_gov = []

        u1 = self.omega - self.omega_ref
        lead_lag_block, y1 = tf_to_diffblock(
            num=np.array([1, self.parameters["T2"]]),
            den=np.array([1, self.parameters["T1"]]),
            x=u1,
            name='gov0',
        )

        # ==============================
        # First Feed back Loop
        y2_3 = Var('y2_3_gov')
        algebraic_vars_gov.append(y2_3)
        x2 = self.Pm_ref - self.K * y1 - y2_3

        y2 = x2 * (1 / self.parameters["T3"])
        y2_1 = hard_sat(y2, self.Uc, self.Uo)
        tf1, y2_2 = tf_to_diffblock(
            num=np.array([1]),
            den=np.array([0, 1]),
            x=y2_1,
            name='gov1',
        )
        algebraic_eqs_gov.append(y2_3 - hard_sat(y2_2, self.Pmin, self.Pmax))

        # ==============================
        # We compute different outputs for every tf
        tf2, y3_1 = tf_to_diffblock(
            num=np.array([1]),
            den=np.array([1, self.parameters["T4"]]),
            x=y2_3,
            name='gov2',
        )
        tf3, y3_2 = tf_to_diffblock(
            num=np.array([1]),
            den=np.array([1, self.parameters["T5"]]),
            x=y3_1,
            name='gov3',
        )
        tf4, y3_3 = tf_to_diffblock(
            num=np.array([1]),
            den=np.array([1, self.parameters["T6"]]),
            x=y3_2,
            name='gov4',
        )
        tf5, y3_4 = tf_to_diffblock(
            num=np.array([1]),
            den=np.array([1, self.parameters["T7"]]),
            x=y3_3,
            name='gov5',
        )

        u = self.parameters["K1"] * y3_1 + self.parameters["K2"] * y3_2 + self.parameters["K3"] * y3_3 + \
            self.parameters["K4"] * y3_4 + self.T_aux
        aux_block = Block(
            algebraic_eqs=[u - self.Tm] + algebraic_eqs_gov,
            algebraic_vars=[self.Tm, self.Pm_ref] + algebraic_vars_gov,
        )

        governor_block = Block(
            children=[lead_lag_block, tf1, tf2, tf3, tf4, tf5, aux_block, ]
        )

        # stabilizer

        vars_block = Block(
            algebraic_vars=[],
        )

        tf, y = tf_to_diffblock_with_states(
            num=np.array([1.0]),
            den=np.array([1, self.parameters["t6"]]),
            x= self.omega,
            name='stabilizer1',
        )

        tf2, y2 = tf_to_diffblock_with_states(
            num=np.array([0, self.parameters["t5"]]),
            den=np.array([1, self.parameters["t5"]]),
            x=self.Ks * y,
            name='stabilizer2',
        )
        tf3, y3 = tf_to_diffblock_with_states(
            num=np.array([1]),
            den=np.array([1, self.parameters["A1"], self.parameters["A2"]]),
            x=y2,
            name='stabilizer3',
        )
        tf4, y4 = tf_to_diffblock_with_states(
            num=np.array([1, self.parameters["t1"]]),
            den=np.array([1, self.parameters["t2"]]),
            x=y3,
            name='stabilizer4',
        )
        tf5, y5 = tf_to_diffblock_with_states(
            num=np.array([1, self.parameters["t3"]]),
            den=np.array([1, self.parameters["t4"]]),
            x=y4,
            name='stabilizer5',
        )

        algebraic_eqs_stabil = list()
        algebraic_eqs_stabil.append(hard_sat(y5, self.VPssMinPu, self.VPssMaxPu) - self.Vpss)
        block_1 = Block()

        stabilizer_block = Block(
            children=[tf, tf2, tf3, tf4, tf5],
            algebraic_eqs=algebraic_eqs_stabil,
            algebraic_vars=[self.Vpss],
        )

        stabilizer_block.add(vars_block)
        stabilizer_block.add(block_1)

        # exciter####################################################################
        #############################################################################

        # ---Internal Blocks---
        tf1, y1 = tf_to_diffblock(
            num=np.array([1]),
            den=np.array([1, self.parameters["tR"]]),
            x=self.Va,
            name='exciter1',
        )  # filtered stator voltage

        # error1 = UPssPu - y + UsRefPu
        error1 = (- y1 + self.UsRefPu) + self.Vpss
        tf2, y2 = tf_to_diffblock(
            num=np.array([0, self.parameters["Kf"]]),
            den=np.array([1, self.parameters["tF"]]),
            x=self.Vf,
            name='exciter2',
        )
        error2 = error1 - y2

        tf3, y3 = tf_to_diffblock(
            num=np.array([1, self.parameters["tC"]]),
            den=np.array([1, self.parameters["tB"]]),
            x=error2,
            name='exciter3',
        )
        tf4, y4 = tf_to_diffblock(
            num=np.array([self.parameters["Ka"]]),
            den=np.array([1, self.parameters["tA"]]),
            x=y3,
            name='exciter4',
        )

        y5 = hard_sat(y4, self.VaMinPu, self.VaMaxPu)

        min_const = Const(max(self.event_dict[self.VaMinPu], self.event_dict[self.EfeMinPu]))
        max_const = Const(min(self.event_dict[self.VaMaxPu], self.event_dict[self.EfeMaxPu]))
        y6 = hard_sat(y4, min_const, max_const)

        # exciter submodel

        algebraic_eqs_submodel = []
        algebraic_vars_submodel = []

        x1 = self.VfeMaxPu - self.IRPu * self.parameters["Kd"]
        error1 = self.Efe - (self.IRPu * self.parameters["Kd"] + self.u_aux)

        tf1_sub, Ve_presat = tf_to_diffblock(
            num=np.array([1]),
            den=np.array([0, self.parameters["tE"]]),
            x=error1,
            name='subexciter1',
        )

        Ve = hard_sat(Ve_presat, self.VeMinPu, Const(1000))
        aux_expr = self.parameters["Ke"] * Ve + self.AEx * Ve * exp(self.BEx * Ve)
        algebraic_eqs_submodel.append(self.u_aux - aux_expr)
        algebraic_eqs_submodel.append(sqrt((self.VeMaxPu * self.u_aux) ** 2 + Const(1e-5)) - x1)

        f_input = Var('f_input')
        f_output = Var('f_output')
        f_output_res = f_exc(f_input)
        algebraic_vars_submodel.append(f_input)
        algebraic_vars_submodel.append(f_output)
        algebraic_eqs_submodel.append(f_input * Ve - self.IRPu * self.parameters["Kc"])

        algebraic_eqs_submodel.append(self.Vf - f_output * Ve)
        algebraic_eqs_submodel.append(f_output_res - f_output)

        aux_model = DiffBlock(
            algebraic_eqs=algebraic_eqs_submodel,
            algebraic_vars=[self.u_aux, self.VeMaxPu, self.Vf] + algebraic_vars_submodel
        )

        exciter_submodel = DiffBlock(children=[tf1_sub, aux_model])

        linking_block = Block(
            algebraic_eqs=[y6 - self.Efe],
            algebraic_vars=[self.Efe, self.UsRefPu],

        )

        exciter_model = Block(children=[tf1, tf2, tf3, tf4, exciter_submodel, linking_block])

        main_block = Block()

        main_block.external_mapping = {
            VarPowerFlowRefferenceType.Vm: self.Vm,
            VarPowerFlowRefferenceType.Va: self.Va,
            VarPowerFlowRefferenceType.P: self.Pg,
            VarPowerFlowRefferenceType.Q: self.Qg
        }



        main_block.event_dict = self.event_dict
        main_block.children.append(governor_block)
        main_block.children.append(stabilizer_block)
        main_block.children.append(exciter_model)
        main_block.children.append(generator_model)


        return main_block
