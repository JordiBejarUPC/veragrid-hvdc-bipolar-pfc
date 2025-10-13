# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import uuid
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple, Sequence, List, Dict, Any

from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, make_symbolic, UndefinedConst, cos, sin, real, imag, conj, angle, exp, log, abs, piecewise
from VeraGridEngine.enumerations import DynamicVarType



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


@dataclass(frozen=False)
class Block:
    """
    This represents a group of equations or a group of blocks
    """
    uid: int = field(default_factory=_new_uid)
    vars2device:Dict[int, PhysicalDevice] = field(default_factory=dict)
    vars_glob_name2uid: Dict[str, uid] = field(default_factory=dict)

    # internal vars
    state_vars: List[Var] = field(default_factory=list)
    state_eqs: List[Expr] = field(default_factory=list)
    algebraic_vars: List[Var] = field(default_factory=list)
    algebraic_eqs: List[Expr] = field(default_factory=list)

    # initialization
    init_vars: List[Var] = field(default_factory=list)
    init_eqs: Dict[Var, Expr] = field(default_factory=dict)
    fix_vars: List[UndefinedConst] = field(default_factory=list)
    fix_vars_eqs: Dict[Any, Expr] = field(default_factory=dict)


    external_mapping: Dict[DynamicVarType, Var] = field(default_factory=dict)


    parameters: List[Var | Const] = field(default_factory=list)
    parameters_eqs: List[Expr] = field(default_factory=list)

    # parameters (parameters affected by events)
    event_parameters: List[Var] = field(default_factory=list)
    event_parameters_eqs: List[Expr] = field(default_factory=list)

    name: str = ""

    # vars to make this recursive
    children: list["Block"] = field(default_factory=list)
    in_vars: List[Var] = field(default_factory=list)
    out_vars: List[Var] = field(default_factory=list)
    active_in_vars: List[Var] = field(default_factory=list)

    def __post_init__(self) -> None:
        # if len(self.algebraic_vars) != len(self.algebraic_eqs):
        #     raise ValueError(
        #         f"algebraic_vars and algebraic_eqs must have the same length: vars is {len(self.algebraic_vars)}, eqs is {len(self.algebraic_eqs)}")
        # if len(self.state_vars) != len(self.state_eqs):
        #     raise ValueError("state_vars and state_eqs must have the same length")
        self.var_mapping = {v.name: v for v in self.algebraic_vars}

    def empty(self):
        return (len(self.state_vars) + len(self.algebraic_vars)) == 0

    def E(self, d: DynamicVarType) -> Var:
        return self.external_mapping[d]

    def V(self, d: str) -> Var:
        return self.var_mapping[d]

    def add(self, val: "Block"):
        """
        Add another block
        :param val: Block
        """
        self.children.append(val)

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
            "init_vars": _serialize_var_list(self.init_vars),
            "init_eqs": {var.to_dict(): expr.to_dict() for var, expr in self.init_eqs.items()},
            "fix_vars": _serialize_undefinedconst_list(self.fix_vars),
            "fix_vars_eqs": {undefconst.uid: expr.to_dict() for undefconst, expr in self.fix_vars_eqs.items()},
            "external_mapping": {dynvartype.__str__(): var.to_dict() for dynvartype, var in self.external_mapping.items()},
            "parameters": _serialize_var_list(self.parameters),
            "parameters_eqs": _serialize_expr_list(self.parameters_eqs),
            "name": self.name,
            "children": [child.to_dict() for child in self.children],
            "in_vars": _serialize_var_list(self.in_vars),
            "out_vars": _serialize_var_list(self.out_vars),
            "active_in_vars": _serialize_var_list(self.active_in_vars),
        }

    @staticmethod
    def parse(data: Dict[str, Any]) -> "Block":
        block = Block(
            uid=data["uid"],
            state_vars=_deserialize_var_list(data["state_vars"]),
            state_eqs=_deserialize_expr_list(data["state_eqs"]),
            algebraic_vars=_deserialize_var_list(data["algebraic_vars"]),
            algebraic_eqs=_deserialize_expr_list(data["algebraic_eqs"]),
            init_vars=_deserialize_var_list(data.get("init_vars", [])),
            fix_vars=_deserialize_var_list(data.get("fix_vars", [])),
            fix_vars_eqs={UndefinedConst(): Expr.from_dict(expr_dict)
            for undefconst_dict, expr_dict in data["fix_vars_eqs"]},
            external_mapping={
                DynamicVarType(k): Var(name=d["name"], uid=d["uid"])
                for k, d in data.get("external_mapping", {}).items()
            },
            init_eqs={Var(name=var_dict["name"], uid=var_dict["uid"]): Expr.from_dict(expr_dict)
            for var_dict, expr_dict in data["init_eqs"]},
            parameters=_deserialize_var_list(data["parameters"]),
            parameters_eqs=_deserialize_expr_list(data.get("parameters_eqs", [])),
            name=data.get("name", ""),
            children=[Block.parse(child) for child in data.get("children", [])],
            in_vars=_deserialize_var_list(data.get("in_vars", [])),
            out_vars=_deserialize_var_list(data.get("out_vars", [])),
            active_in_vars=_deserialize_var_list(data.get("active_in_vars", [])),
        )
        return block

    @staticmethod
    def parse_type(data: Dict[str, Any]):
        block = Block(
            state_vars=[Var(v) for v in data["state_vars"]],
            state_eqs=_deserialize_expr_list(data["state_eqs"]),
            algebraic_vars=_deserialize_var_list(data["algebraic_vars"]),
            algebraic_eqs=_deserialize_expr_list(data["algebraic_eqs"]),
            init_vars=_deserialize_var_list(data.get("init_vars", [])),
            fix_vars=_deserialize_var_list(data.get("fix_vars", [])),
            fix_vars_eqs={UndefinedConst(): Expr.from_dict(expr_dict)
                          for undefconst_dict, expr_dict in data["fix_vars_eqs"]},
            external_mapping={
                DynamicVarType(k): Var(name=d["name"], uid=d["uid"])
                for k, d in data.get("external_mapping", {}).items()
            },
            init_eqs={Var(name=var_dict["name"], uid=var_dict["uid"]): Expr.from_dict(expr_dict)
                      for var_dict, expr_dict in data["init_eqs"]},
            parameters=_deserialize_var_list(data["parameters"]),
            parameters_eqs=_deserialize_expr_list(data.get("parameters_eqs", [])),
            name=data.get("name", ""),
            children=[Block.parse(child) for child in data.get("children", [])],
            in_vars=_deserialize_var_list(data.get("in_vars", [])),
            out_vars=_deserialize_var_list(data.get("out_vars", [])),
            active_in_vars=_deserialize_var_list(data.get("active_in_vars", [])),
        )
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

def constant(value: float, name: str = "const") -> Tuple[Var, Block]:
    y = Var(name)
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - Const(value)])
    return y, blk

def variable(name: str = "variable",  vartype: str = "vartype") -> Tuple[Var, Block]:
    y = Var(name)
    if vartype == 'state':
        blk = Block(state_vars=[y])
    else:
        blk = Block(algebraic_vars=[y])
    return y, blk

def equation(expr: str = 'expression', etype: str = "etype")-> Block:
    if etype == 'state':
        blk = Block(state_eqs=[make_symbolic(expr)])
    else:
        blk = Block(algebraic_eqs=[make_symbolic(expr)])
    return blk


def gain(k: float, u: Var | Const, name: str = "gain_out") -> Tuple[Var, Block]:
    y = Var(name)
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - Const(k) * u])
    return y, blk


def adder(inputs: Sequence[Var | Const], name: str = "sum_out") -> Tuple[Var, Block]:
    if len(inputs) == 0:
        raise ValueError("adder() needs at least one input variable")
    y = Var(name)
    expr: Expr = inputs[0]
    for v in inputs[1:]:
        expr += v
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - expr])
    return y, blk


def substract(inputs: Sequence[Var | Const], name: str = "substract_out") -> Tuple[Var, Block]:
    if len(inputs) == 0:
        raise ValueError("adder() needs at least one input variable")
    y = Var(name)
    expr: Expr = inputs[0]
    for v in inputs[1:]:
        expr += v
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - expr])
    return y, blk




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

    def placeholders(n, base):
        return [Var(f"{base}{i}") for i in range(n)]

def bus(api_object) -> Block:

    Vm = Var("Vm")
    Va = Var("Va")
    P = Var("P")
    Q = Var("Q")
    bus_block = Block(
                algebraic_vars=[Vm, Va],
                external_mapping={
                    DynamicVarType.Vm: Vm,
                    DynamicVarType.Va: Va,
                    DynamicVarType.P: P,
                    DynamicVarType.Q: Q}
            )
    return bus_block

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

    Vm = gen_object.bus.rms_model.model.E(DynamicVarType.Vm)
    Va = gen_object.bus.rms_model.model.E(DynamicVarType.Va)

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
                log((Vm * exp(1j * Va) + (gen_object.R1 + 1j * gen_object.X1) * (conj((P_g + 1j * Q_g) / (Vm * exp(1j * Va))))) / (
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
            DynamicVarType.P: P_g,
            DynamicVarType.Q: Q_g
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
            DynamicVarType.P: Pl,
            DynamicVarType.Q: Ql
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

    Vmf = line_object.bus_from.rms_model.model.E(DynamicVarType.Vm)
    Vaf = line_object.bus_from.rms_model.model.E(DynamicVarType.Va)
    Vmt = line_object.bus_to.rms_model.model.E(DynamicVarType.Vm)
    Vat = line_object.bus_to.rms_model.model.E(DynamicVarType.Va)

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
            DynamicVarType.Pf: Pf,
            DynamicVarType.Pt: Pt,
            DynamicVarType.Qf: Qf,
            DynamicVarType.Qt: Qt,
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








def generic(state_inputs: int, state_outputs: Sequence[str], algebraic_inputs: int, algebraic_outputs: Sequence[str]) -> Block:
    blk = Block()
    blk.name = "generic"
    input_vars = [Var(f"Vport{i}") for i in range(state_inputs + algebraic_inputs)]
    blk.in_vars = input_vars

    for v in state_outputs:
        var = Var(v)
        blk.state_vars.append(var)
        blk.out_vars.append(var)

    for v in algebraic_outputs:
        var = Var(v)
        blk.algebraic_vars.append(var)
        blk.out_vars.append(var)

    return blk
