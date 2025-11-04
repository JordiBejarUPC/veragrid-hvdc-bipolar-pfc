# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import uuid
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple, Sequence, List, Dict, Any

from VeraGridEngine.Devices.Dynamic.events import RmsEvent
from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, make_symbolic, UndefinedConst, cos, sin, real, \
    imag, conj, angle, exp, log, abs, piecewise
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType


def _new_uid() -> int:
    """
    Generate a fresh UUID‑v4 string.
    :return: UUIDv4 in integer format
    """
    return uuid.uuid4().int


def _serialize_expr_list(exprs: List[Expr]) -> List[Dict[str, Any]]:
    """

    :param exprs:
    :return:
    """
    return [expr.to_dict() for expr in exprs]


def _serialize_var_list(vars_: List[Var | Const]) -> List[Dict[str, Any]]:
    """
    Serialize list of variables or constants
    :param vars_: list of Var or Const
    :return: List of dictionaries with the serialized data
    """
    return [v.to_dict() for v in vars_]


def _serialize_undefinedconst_list(undefconsts_: List[UndefinedConst]) -> List[Dict[str, Any]]:
    """
    Serialize list of variables or constants
    :param vars_: list of Var or Const
    :return: List of dictionaries with the serialized data
    """
    return [undefconst.to_dict() for undefconst in undefconsts_]


def _deserialize_expr_list(expr_dicts: List[Dict[str, Any]]) -> List[Expr]:
    """

    :param expr_dicts:
    :return:
    """
    return [Expr.from_dict(d) for d in expr_dicts]


def _deserialize_var_list(var_dicts: List[Dict[str, Any]]) -> List[Var | Const | UndefinedConst]:
    """
    De-serialize previously serialized data into List of Vars or Const
    :param var_dicts: List of serialized data
    :return: List of Vars or Const
    """
    result = list()
    for d in var_dicts:
        if d["type"] == "Var":
            result.append(Var(name=d["name"], uid=d["uid"]))
        elif d["type"] == "Const":
            result.append(Const(value=d["value"], uid=d["uid"]))
        elif d['type'] == "UndefinedConst":
            result.append(UndefinedConst())
        else:
            raise ValueError(f"Unknown variable type {d['type']}")
    return result


class Block:
    """
    Class representing a Block
    """

    def __init__(self,
                 state_vars: List[Var] | None = None,
                 state_eqs: List[Expr] | None = None,
                 algebraic_vars: List[Var] | None = None,
                 algebraic_eqs: List[Expr] | None = None,
                 init_eqs: Dict[Var, Expr] | None = None,
                 children: List["Block"] | None = None,
                 in_vars: Dict[str, Var] | None = None,
                 out_vars: Dict[str, Var] | None = None):

        # ,
        # external_mapping: Dict[VarPowerFlowRefferenceType, Var] | None = None
        """
        This represents a group of equations or a group of blocks

        :param algebraic_vars: List of non differential variables (AKA algebraic)
        :param algebraic_eqs: List of equations that provide values for the algebraic variables
        :param state_vars: List of differential variables (AKA state variables)
        :param state_eqs: List of equations that provide values for the state variables
        :param children: List of other blocks to be flattened later into this block
        :param in_vars: List of variables from other blocks that we use here
        :param out_vars: List of variables that already exist in algebraic_vars or state_vars that we want to expose
        :param init_eqs: List of equations that help initializing the block variables (algebraic and state)
        """

        self.name: str = ""

        self.uid: int = _new_uid()
        self.vars2device: Dict[int, PhysicalDevice] = dict()
        self.vars_glob_name2uid: Dict[str, int] = dict()

        # TODO: Change to dictionary of Var : Expr
        self.state_vars: List[Var] = list() if state_vars is None else state_vars
        self.state_eqs: List[Expr] = list() if state_eqs is None else state_eqs

        # TODO: Change to dictionary of Var : Expr
        self.algebraic_vars: List[Var] = list() if algebraic_vars is None else algebraic_vars
        self.algebraic_eqs: List[Expr] = list() if algebraic_eqs is None else algebraic_eqs

        # initialization
        self.init_eqs: Dict[Var, Expr] = dict() if init_eqs is None else init_eqs

        # vars to make this recursive
        self.children: List["Block"] = list() if children is None else children

        self.in_vars: Dict[str, Var] = dict() if in_vars is None else in_vars
        self.out_vars: Dict[str, Var] = dict() if out_vars is None else out_vars

        # self.external_mapping: Dict[VarPowerFlowRefferenceType, Var] = dict if external_mapping is None else {elm.pf_ref: elm
        #                                                                 for elm in self.algebraic_vars}
        self.external_mapping: Dict[VarPowerFlowRefferenceType, Var] = dict()
        self.fix_vars: List[UndefinedConst] = list()
        self.fix_vars_eqs: Dict[Any, Expr] = dict()

        self.var_mapping = {v.name: v for v in self.algebraic_vars}



        # Dictionary of Variables and their Expressions that appear due to an event
        # this is the dictionary of "parameters" that may change and their equations
        self.event_dict: Dict[Var, Expr] = dict()

    def empty(self) -> bool:
        """

        :return:
        """
        return (len(self.state_vars) + len(self.algebraic_vars)) == 0

    def E(self, d: VarPowerFlowRefferenceType) -> Var:
        """

        :param d:
        :return:
        """
        return self.external_mapping[d]

    def V(self, d: str) -> Var:
        """

        :param d:
        :return:
        """
        return self.var_mapping[d]

    def add(self, val: "Block"):
        """
        Add another block
        :param val: Block
        """
        self.children.append(val)

    def remove(self, val: Block):
        """
        Remove a block from block children
        :param val: Block
        """
        self.children.remove(val)

    def apply_events(self, events: List[RmsEvent]):
        """
        Apply events to this block
        :param events:
        :return:
        """
        # TODO Implement filling self.event_dicts with the RmsEvents info
        pass

    def get_all_blocks(self) -> List[Block]:
        """
        Depth-first collection of all *primitive* Blocks.
        """

        flat: List[Block] = [self]
        for el in self.children:
            flat.extend(el.get_all_blocks())

        return flat

    def get_vars(self) -> List[Var]:
        """
        Get a list of algebraic + state vars
        :return: List[Var]
        """
        return self.algebraic_vars + self.state_vars

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "vars2device": {var_uid: dev.uid for var_uid, dev in self.vars2device.items()},
            "vars_glob_name2uid": self.vars_glob_name2uid,
            "state_vars": _serialize_var_list(self.state_vars),
            "state_eqs": _serialize_expr_list(self.state_eqs),
            "algebraic_vars": _serialize_var_list(self.algebraic_vars),
            "algebraic_eqs": _serialize_expr_list(self.algebraic_eqs),
            "init_eqs": [
                {"var": var.to_dict(), "expr": expr.to_dict()}
                for var, expr in self.init_eqs.items()
            ],
            "fix_vars": _serialize_undefinedconst_list(self.fix_vars),
            "fix_vars_eqs": [
                {"uid": undef.uid, "expr": expr.to_dict()}
                for undef, expr in self.fix_vars_eqs.items()
            ],
            "external_mapping": {str(dynvartype): var.to_dict() for dynvartype, var in self.external_mapping.items()},
            "event_dict": [
                {"var": var.to_dict(), "expr": expr.to_dict()}
                for var, expr in self.event_dict.items()
            ],
            "name": self.name,
            "children": [child.to_dict() for child in self.children],
            "in_vars":  [{"number": number, "var": var.to_dict()} for number, var in self.in_vars.items()],
            "out_vars": [{"number": number, "var": var.to_dict()} for number, var in self.out_vars.items()]
        }

    @staticmethod
    def parse(data: Dict[str, Any]) -> "Block":
        state_vars = _deserialize_var_list(data.get("state_vars", []))
        state_eqs = _deserialize_expr_list(data.get("state_eqs", []))
        algebraic_vars = _deserialize_var_list(data.get("algebraic_vars", []))
        algebraic_eqs = _deserialize_expr_list(data.get("algebraic_eqs", []))
        children = [Block.parse(child) for child in data.get("children", [])]

        block = Block(
            state_vars=state_vars,
            state_eqs=state_eqs,
            algebraic_vars=algebraic_vars,
            algebraic_eqs=algebraic_eqs,
            init_eqs={},
            children=children,
        )

        block.uid = int(data.get("uid", block.uid))
        block.name = data.get("name", "")
        block.vars_glob_name2uid = data.get("vars_glob_name2uid", {})
        block.vars2device = {int(k): v for k, v in data.get("vars2device", {}).items()}

        block.init_eqs = {}
        for pair in data.get("init_eqs", []):
            var_dict = pair["var"]
            expr_dict = pair["expr"]
            var = Var(name=var_dict["name"], uid=var_dict.get("uid"))
            expr = Expr.from_dict(expr_dict)
            block.init_eqs[var] = expr

        fv_list = _deserialize_var_list(data.get("fix_vars", []))
        block.fix_vars = [v for v in fv_list if isinstance(v, UndefinedConst)]

        block.fix_vars_eqs = {}
        undef_by_uid = {getattr(u, "uid", None): u for u in block.fix_vars}
        for item in data.get("fix_vars_eqs", []):
            uid = item.get("uid")
            expr = Expr.from_dict(item["expr"])
            undef = undef_by_uid.get(uid)
            if undef is not None:
                block.fix_vars_eqs[undef] = expr
            else:
                new_undef = UndefinedConst()
                block.fix_vars_eqs[new_undef] = expr
                block.fix_vars.append(new_undef)

        block.external_mapping = {}
        for key_str, var_dict in data.get("external_mapping", {}).items():
            try:
                key = VarPowerFlowRefferenceType[
                    key_str] if key_str in VarPowerFlowRefferenceType.__members__ else VarPowerFlowRefferenceType(
                    key_str)
            except Exception:
                key = key_str
            var = Var(name=var_dict["name"], uid=var_dict.get("uid"))
            block.external_mapping[key] = var

        block.event_dict = {}
        for pair in data.get("event_dict", []):
            var_dict = pair["var"]
            expr_dict = pair["expr"]
            var = Var(name=var_dict["name"], uid=var_dict.get("uid"))
            expr = Expr.from_dict(expr_dict)
            block.event_dict[var] = expr

        block.in_vars = {}
        for pair in data.get("in_vars", []):
            number = pair["number"]
            var_dict = pair["var"]
            var = Var(name=var_dict["name"], uid=var_dict.get("uid"))
            block.in_vars[number] = var

        block.out_vars = {}
        for pair in data.get("out_vars", []):
            number = pair["number"]
            var_dict = pair["var"]
            var = Var(name=var_dict["name"], uid=var_dict.get("uid"))
            block.out_vars[number] = var

        block.var_mapping = {v.name: v for v in block.algebraic_vars}
        return block

    def copy(self) -> "Block":
        """
        Make a deep copy of this
        :return: deep copy Block
        """
        return Block.parse(data=self.to_dict())

    def __eq__(self, other):
        if isinstance(other, Block):
            return self.to_dict() == other.to_dict()
        else:
            return False


# ----------------------------------------------------------------------------------------------------------------------
# Pre defined blocks
# ----------------------------------------------------------------------------------------------------------------------

def constant(item_name:str = "") -> Block:
    name: str = "const_"
    y = Var(name + item_name)
    param = Var("param_" + item_name)

    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - param])
    blk.event_dict[param] = Const(0.0)
    blk.in_vars = dict()
    blk.out_vars[str(0)] = y
    blk.name = "const"
    return blk

def gain(item_name:str = "") -> Block:
    inputs = [Var("inp_num_" + item_name)]
    name: str = "gain"
    y = Var(name + item_name)
    gain_param = Var("gain_param_" + item_name)
    in_vars_dict: Dict[str, Var] = dict()
    for i, inpt in enumerate(inputs):
        in_vars_dict[str(i)] = inpt
    expr: Expr = gain_param * inputs[0]
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - expr])
    blk.event_dict[gain_param] = Const(0.0)
    blk.in_vars=in_vars_dict
    blk.out_vars[str(0)] = y
    blk.name = "gain"
    return blk



def variable(name: str = "variable_", vartype: str = "vartype_") -> Tuple[Var, Block]:
    y = Var(name)
    if vartype == 'state':
        blk = Block(state_vars=[y])
    else:
        blk = Block(algebraic_vars=[y])
    return y, blk


def equation(expr: str = 'expression', etype: str = "etype") -> Block:
    if etype == 'state':
        blk = Block(state_eqs=[make_symbolic(expr)])
    else:
        blk = Block(algebraic_eqs=[make_symbolic(expr)])
    return blk




def adder(item_name:str = "") -> Block:
    inputs = [Var("sum_in_1_" + item_name), Var("sum_in_2_" + item_name)] # will not be specified if inputs can be more than 2
    y = Var("sum_out_" + item_name)
    in_vars_dict: Dict[str, Var] = dict()
    expr: Expr = inputs[0]
    for i, inpt in enumerate(inputs):
        in_vars_dict[str(i)] = inpt
        if i>0:
            expr += inpt
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - expr])
    blk.in_vars=in_vars_dict
    blk.out_vars[str(0)] = y
    blk.name = "sum"
    return blk

def substract(item_name:str = "") -> Block:
    inputs = [Var("minuend_" + item_name), Var("subtrahend_" + item_name)]
    y = Var("difference_" + item_name)
    in_vars_dict: Dict[str, Var] = dict()
    expr: Expr = inputs[0] - inputs[1]
    for i, inpt in enumerate(inputs):
        in_vars_dict[str(i)] = inpt
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - expr])
    blk.in_vars = in_vars_dict
    blk.out_vars[str(0)] = y
    blk.name = "substraction"
    return blk

def product(item_name:str = "") -> Block:
    inputs = [Var("factor1_" + item_name), Var("factor2_" + item_name)] # will not be specified if inputs can be more than 2
    y = Var("product_out_" + item_name)
    in_vars_dict: Dict[str, Var] = dict()
    expr: Expr = inputs[0] * inputs[1]
    for i, inpt in enumerate(inputs):
        in_vars_dict[str(i)] = inpt
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - expr])
    blk.in_vars=in_vars_dict
    blk.out_vars[str(0)] = y
    blk.name = "product"
    return blk

def divide(item_name:str = "") -> Block:
    inputs = [Var("divident_" + item_name), Var("divisor_" + item_name)] # will not be specified if inputs can be more than 2
    y = Var("quotient_" + item_name)
    in_vars_dict: Dict[str, Var] = dict()
    expr: Expr = inputs[0]/inputs[1]
    for i, inpt in enumerate(inputs):
        in_vars_dict[str(i)] = inpt
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - expr])
    blk.in_vars=in_vars_dict
    blk.out_vars[str(0)] = y
    blk.name = "divide"
    return blk

def absolut(item_name:str = "") -> Block:
    inputs = [Var("inp_num_" + item_name)] # will not be specified if inputs can be more than 2
    y = Var("absolut_" + item_name)
    in_vars_dict: Dict[str, Var] = dict()
    expr: Expr = abs(inputs[0])
    for i, inpt in enumerate(inputs):
        in_vars_dict[str(i)] = inpt
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - expr])
    blk.in_vars=in_vars_dict
    blk.out_vars[str(0)] = y
    blk.name = "abs"
    return blk


def integrator(u: Var | Const, name: str = "x") -> Tuple[Var, Block]:
    x = Var(name)
    blk = Block(state_vars=[x], state_eqs=[u])
    return x, blk


def pi_controller(err: Var, kp: float, ki: float, name: str = "pi") -> Block:
    up, blk_kp = gain(kp, err, f"{name}_up")
    ie, blk_int = integrator(err, f"{name}_int")
    ui, blk_ki = gain(ki, ie, f"{name}_ui")
    u, blk_sum = adder([up, ui], f"{name}_u")
    return Block(name="",
                 children=[blk_kp, blk_int, blk_ki, blk_sum],
                 in_vars=[err],
                 out_vars=[u])

def bus(api_object) -> Block:
    Vm = Var("Vm")
    Va = Var("Va")
    P = Var("P")
    Q = Var("Q")
    bus_block = Block(
        algebraic_vars=[Vm, Va],
        external_mapping={
            VarPowerFlowRefferenceType.Vm: Vm,
            VarPowerFlowRefferenceType.Va: Va,
            VarPowerFlowRefferenceType.P: P,
            VarPowerFlowRefferenceType.Q: Q}
    )
    return bus_block

def genqec(name: str = "") -> Block:
    inputs = [Var("tm_" + name), Var("vf_" + name)]

    in_vars_dict: Dict[str, Var] = dict()
    for i, inpt in enumerate(inputs):
        in_vars_dict[str(i)] = inpt
    # Saturation factors
    Sat_d = Var('Sat_d'+ name)
    Sat_q = Var('Sat_q'+ name)

    # Inputs (already in inputs_dict)
    T_m = Var("T_m"+ name)  # mechanical torque
    E_fd = Var("E_fd"+ name)  # field excitation

    # States
    delta = Var("delta"+ name)  # rotor angle
    omega = Var("omega"+ name)  # rotor electrical speed
    Eq1 = Var("Eq1"+ name)  # internal emf behind Xd'
    Ed1 = Var("Ed1"+ name)
    Eq2 = Var("Eq2"+ name)
    Ed2 = Var("Ed2"+ name)
    Eq_prime = Var("Eq_prime"+ name)  # transient voltage q-axis
    Ed_prime = Var("Ed_prime"+ name)  # transient voltage d-axis
    Eq_2prime = Var("Eq_2prime"+ name)  # subtransient voltage q-axis
    Ed_2prime = Var("Ed_2prime"+ name)  # subtransient voltage d-axis

    # Algebraic variables
    Id = Var("Id"+ name)
    Iq = Var("Iq"+ name)
    Vd = Var("Vd"+ name)
    Vq = Var("Vq"+ name)
    Psid = Var("Psid"+ name)
    Psiq = Var("Psiq"+ name)
    Te = Var("Te"+ name)

    # Saturated resistances
    Xd_sat = Var('Xd_sat'+ name)
    Xq_sat = Var('Xq_sat'+ name)
    Xd_prime_sat = Var('Xd_prime_sat'+ name)
    Xq_prime_sat = Var('Xq_prime_sat'+ name)
    Xd_2prime_sat = Var('Xd_2prime_sat'+ name)
    Xq_2prime_sat = Var('Xq_2prime_sat'+ name)
    Ed2_coef = Var('Ed2_coef'+ name)
    Eq2_coef = Var('Eq2_coef'+ name)

    Vg = Var('Vg'+ name)
    dg = Var('dg'+ name)
    Pg = Var('Pg'+ name)
    Qg = Var('Qg'+ name)

    out_vars[str(0)] = Pg
    out_vars[str(1)] = Qg

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
        Xq_2prime: Const(0.25),
        Xl: Const(0.15),

        # Time constants
        Td0_prime: Const(8.0),
        Tq0_prime: Const(0.4),
        Td0_2prime: Const(0.03),
        Tq0_2prime: Const(0.05)
    }

    generator_block = Block(
        state_eqs=[
            (omega - Const(1)) * ws,  # dδ/dt
            (T_m - Te - D * (omega - Const(1))) * (1 / (M)),  # dω/dt
            E_fd / Td0_prime - Sat_q * Eq1 / Td0_prime,  # dEq'/dt
            -Sat_q * Ed1 / Tq0_prime,  # dEd'/dt
            Eq2_coef * (-Eq2),  # dEq''/dt
            Ed2_coef * (-Ed2),  # dEd''/dt
        ],
        state_vars=[delta, omega, Eq_prime, Ed_prime, Eq_2prime, Ed_2prime],
        algebraic_eqs=[
            Vd - (-Vg * sin(dg - delta)),
            Vq - (Vg * cos(dg - delta)),
            Pg - (Vd * Id + Vq * Iq),
            Qg - (Vq * Id - Vd * Iq),
            Vd - ((omega) * Ed_2prime + Iq * Xq_2prime_sat - Id * Ra),
            Vq - ((omega) * Eq_2prime - Id * Xd_2prime_sat - Iq * Ra),
            Psid - (Eq_prime - Id * Xd_2prime_sat),
            Psiq - (-Ed_prime - Iq * Xq_2prime_sat),
            Te - (Psid * Iq - Psiq * Id),
            (Xd_sat - Xd_prime_sat) * Eq1 - (
                        (Xd_sat - Xd_prime_sat) * Eq_2prime + (Eq_prime - Eq_2prime) * (Xd_sat - Xd_2prime_sat)),
            # Eq1 definition
            (Xq_sat - Xq_prime_sat) * Ed1 - (
                        (Xq_sat - Xq_prime_sat) * Ed_2prime + (Ed_prime - Ed_2prime) * (Xq_sat - Xq_2prime_sat)),
            # Ed1 definition
            (Xd_sat - Xd_2prime_sat) * Eq2 - (-1) * (
                        (Eq_prime - Eq_2prime) * (Xd_sat - Xd_prime_sat) + Id * (Xd_sat - Xd_2prime_sat) ** 2),
            # Ed2 definition
            (Xq_sat - Xq_2prime_sat) * Ed2 - (-1) * (
                        (Ed_prime - Ed_2prime) * (Xq_sat - Xq_prime_sat) + Iq * (Xq_sat - Xq_2prime_sat) ** 2),
            # Eq2 definition
            Eq2_coef * (Tq0_2prime * (Xq_sat - Xq_2prime_sat)) - (Xq_prime_sat - Xq_2prime_sat) * Sat_q,
            Ed2_coef * (Td0_2prime * (Xd_sat - Xd_2prime_sat)) - (Xd_prime_sat - Xd_2prime_sat) * Sat_d,
        ],
        algebraic_vars=[Vd, Vq, Psid, Psiq, Ed2_coef, Eq2_coef, Te, Ed1, Eq1, Ed2, Eq2, Id, Iq])

    generator_block.external_mapping={
            VarPowerFlowRefferenceType.P: Pg,
            VarPowerFlowRefferenceType.Q: Qg,
            VarPowerFlowRefferenceType.Vm: Vg,
            VarPowerFlowRefferenceType.Va: dg,
        }
    generator_block.in_vars=in_vars_dict
    generator_block.out_vars[str(0)] = Pg
    generator_block.out_vars[str(1)] = Qg



    return generator_block


def generator(api_object) -> Block:
    gen_object = api_object

    delta = Var("delta")
    omega = Var("omega")
    psid = Var("psid")
    psiq = Var("psiq")
    i_d = Var("i_d")
    i_q = Var("i_q")
    v_d = Var("v_d")
    v_q = Var("v_q")
    te = Var("te")
    et = Var("et")
    tm = Var("tm")
    P_g = Var("P_g")
    Q_g = Var("Q_g")

    vf = UndefinedConst()
    tm0 = UndefinedConst()

    Vm = gen_object.bus.rms_model.model.E(VarPowerFlowRefferenceType.Vm)
    Va = gen_object.bus.rms_model.model.E(VarPowerFlowRefferenceType.Va)

    gen_block = Block(
        state_eqs=[
            (2 * np.pi * gen_object.freq) * (omega - gen_object.omega_ref),
            (tm - te - gen_object.D * (omega - gen_object.omega_ref)) / gen_object.M,
        ],
        state_vars=[delta, omega],
        algebraic_eqs=[
            psid - (gen_object.R1 * i_q + v_q),
            psiq + (gen_object.R1 * i_d + v_d),
            0 - (psid + gen_object.X1 * i_d - vf),
            0 - (psiq + gen_object.X1 * i_q),
            v_d - (Vm * sin(delta - Va)),
            v_q - (Vm * cos(delta - Va)),
            te - (psid * i_q - psiq * i_d),
            P_g - (v_d * i_d + v_q * i_q),
            Q_g - (v_q * i_d - v_d * i_q),
            tm - (gen_object.tm0 + gen_object.Kp * (omega - gen_object.omega_ref) + gen_object.Ki * et),
            2 * np.pi * gen_object.freq * et - delta,  #
        ],
        algebraic_vars=[P_g, Q_g, v_d, v_q, i_d, i_q, psid, psiq, te, tm, et],
        init_eqs={
            delta: imag(
                log((Vm * exp(1j * Va) + (gen_object.R1 + 1j * gen_object.X1) * (
                    conj((P_g + 1j * Q_g) / (Vm * exp(1j * Va))))) / (
                        abs(Vm * exp(1j * Va) + (gen_object.R1 + 1j * gen_object.X1) * (
                            conj((P_g + 1j * Q_g) / (Vm * exp(1j * Va)))))))),
            omega: Const(gen_object.omega_ref),
            v_d: real((Vm * exp(1j * Va)) * exp(-1j * (delta - np.pi / 2))),
            v_q: imag((Vm * exp(1j * Va)) * exp(-1j * (delta - np.pi / 2))),
            i_d: real(conj((P_g + 1j * Q_g) / (Vm * exp(1j * Va))) * exp(-1j * (delta - np.pi / 2))),
            i_q: imag(conj((P_g + 1j * Q_g) / (Vm * exp(1j * Va))) * exp(-1j * (delta - np.pi / 2))),
            psid: gen_object.R1 * i_q + v_q,
            psiq: -gen_object.R1 * i_d - v_d,
            te: psid * i_q - psiq * i_d,
            tm: te,
            et: Const(0),
        },
        init_vars=[delta, omega, et, v_d, v_q, i_d, i_q, psid, psiq, te, tm],
        fix_vars=[tm0, vf],
        fix_vars_eqs={tm0.uid: tm,
                      vf.uid: psid + gen_object.X1 * i_d},

        external_mapping={
            VarPowerFlowRefferenceType.P: P_g,
            VarPowerFlowRefferenceType.Q: Q_g
        }
    )
    return gen_block


def load(api_object) -> Block:
    load_object = api_object
    Ql = Var("Ql")
    Pl = Var("Pl")

    load_block = Block(
        algebraic_eqs=[
            Pl - load_object.Pl0,
            Ql - load_object.Ql0
        ],
        algebraic_vars=[Pl, Ql],
        init_eqs={},
        init_vars=[],
        parameters=[],
        external_mapping={
            VarPowerFlowRefferenceType.P: Pl,
            VarPowerFlowRefferenceType.Q: Ql
        }
    )
    return load_block


def line(api_object) -> Block:
    line_object = api_object
    Qf = Var("Qf")
    Qt = Var("Qt")
    Pf = Var("Pf")
    Pt = Var("Pt")

    ys = 1.0 / complex(line_object.R, line_object.X)
    g = Const(ys.real)
    b = Const(ys.imag)
    bsh = Const(line_object.B)

    Vmf = line_object.bus_from.rms_model.model.E(VarPowerFlowRefferenceType.Vm)
    Vaf = line_object.bus_from.rms_model.model.E(VarPowerFlowRefferenceType.Va)
    Vmt = line_object.bus_to.rms_model.model.E(VarPowerFlowRefferenceType.Vm)
    Vat = line_object.bus_to.rms_model.model.E(VarPowerFlowRefferenceType.Va)

    line_block = Block(
        algebraic_eqs=[
            Pf - ((Vmf ** 2 * g) - g * Vmf * Vmt * cos(Vaf - Vat) + b * Vmf * Vmt * cos(Vaf - Vat + np.pi / 2)),
            Qf - (Vmf ** 2 * (-bsh / 2 - b) - g * Vmf * Vmt * sin(Vaf - Vat) + b * Vmf * Vmt * sin(
                Vaf - Vat + np.pi / 2)),
            Pt - ((Vmt ** 2 * g) - g * Vmt * Vmf * cos(Vat - Vaf) + b * Vmt * Vmf * cos(Vat - Vaf + np.pi / 2)),
            Qt - (Vmt ** 2 * (-bsh / 2 - b) - g * Vmt * Vmf * sin(Vat - Vaf) + b * Vmt * Vmf * sin(
                Vat - Vaf + np.pi / 2)),
        ],
        algebraic_vars=[Pf, Pt, Qf, Qt],
        init_eqs={},
        init_vars=[],
        parameters=[],
        external_mapping={
            VarPowerFlowRefferenceType.Pf: Pf,
            VarPowerFlowRefferenceType.Pt: Pt,
            VarPowerFlowRefferenceType.Qf: Qf,
            VarPowerFlowRefferenceType.Qt: Qt,
        }
    )

    # bus_block = Block()
    # algebraic_inputs: int = 2
    # algebraic_outputs: Sequence[str] = ["Vm", "Va"]
    #
    # bus_block.algebraic_vars = [Var(v) for v in algebraic_outputs]
    # bus_block.in_vars = [Var(f"InVar{i}") for i in range(algebraic_inputs)]
    # bus_block.external_mapping = {
    #     DynamicVarType.Vm: Vm,
    #     DynamicVarType.Va: Va,
    #     DynamicVarType.P: P,
    #     DynamicVarType.Q: Q}


def generic(state_inputs: int, state_outputs: Sequence[str], algebraic_inputs: int,
            algebraic_outputs: Sequence[str]) -> Block:
    blk = Block()
    blk.name = "generic"
    input_vars = [Var(f"Vport{i}") for i in range(state_inputs + algebraic_inputs)]
    blk.in_vars = input_vars

    for i, v in enumerate(state_outputs):
        var = Var(v)
        blk.state_vars.append(var)
        blk.out_vars[str(i)] = var

    for i, v in enumerate(algebraic_outputs):
        var = Var(v)
        blk.algebraic_vars.append(var)
        blk.out_vars[str(i)] = var

    in_vars_dict: Dict[str, Var] = dict()
    for i, inpt in enumerate(input_vars):
        in_vars_dict[str(i)] = inpt
    blk.in_vars = in_vars_dict

    return blk
