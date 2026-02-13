# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import uuid
import numpy as np
from typing import Tuple, Sequence, List, Dict, Optional

from enum import Enum, auto

from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Devices.Dynamic.events import RmsEvent
from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr, abs,
                                                    DiffVar, heaviside)
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, ParamPowerFlowRefferenceType


def _new_uid() -> int:
    """
    Generate a fresh UUID‑v4 string.
    :return: UUIDv4 in integer format
    """
    return uuid.uuid4().int

def tf_to_block(num: np.ndarray,
                den: np.ndarray,
                x: Var | Expr,
                y: Var = None,
                name: Optional[str] = '') -> Tuple[Block, Var]:
    """
    num: list of numerator coefficients [b0, b1, ..., bm]
    den: list of denominator coefficients [a0, a1, ..., an]
    x:   sympy symbol for input
    y:   sympy function of t for output
    """
    if len(num) > len(den):
        raise ValueError("Transfer function is improper: numerator degree > denominator degree.")

    if y is None:
        y = Var('y_' + name)

    aux_eqs = []
    aux_vars = []
    # check if is an expression
    if not isinstance(x, Var):
        u = Var('u_' + name)
        aux_eqs.append((u - x).simplify())
        aux_vars.append(u)
        x = u

    diff_vars_x = [x]
    diff_vars_y = [y]
    diff_vars = []
    base_var = x
    for i in range(1, len(num)):
        if base_var.diff_var is None:
            new_diff = DiffVar(name=f'dt_{i}_' + x.name, base_var=base_var)
            diff_vars.append(new_diff)
        diff_vars_x.append(x.diff_var)
        base_var = x.diff_var
    base_var = y
    for i in range(1, len(den)):
        if base_var.diff_var is None:
            new_diff = DiffVar(name=f'dt_{i}_' + y.name, base_var=base_var)
            diff_vars.append(new_diff)
        diff_vars_y.append(y.diff_var)
        base_var = y.diff_var

    # Create the diff equation
    rhs = np.array(diff_vars_x) @ np.array(num)
    lhs = np.array(diff_vars_y) @ np.array(den)

    block = Block()
    block.algebraic_vars = [y] + aux_vars
    block.algebraic_vars = [y] + aux_vars
    block.algebraic_eqs = [lhs - rhs] + aux_eqs
    block.diff_vars = diff_vars

    return block, y


def tf_to_diffblock_with_output(num: np.ndarray,
                                den: np.ndarray,
                                x: Var | Expr,
                                y: Var = None,
                                name: Optional[str] = ''):
    """
    num: list of numerator coefficients [b0, b1, ..., bm]
    den: list of denominator coefficients [a0, a1, ..., an]
    x:   sympy symbol for input
    y:   sympy function of t for output
    """
    if len(num) > len(den):
        raise ValueError("Transfer function is improper: numerator degree > denominator degree.")
    if num[-1] == 0 or den[-1] == 0:
        raise ValueError("Leading coefficient of cannot be zero.")

    if y is None:
        y = Var('y_' + name)

    aux_eqs = []
    aux_vars = []
    # check if is an expression
    if not isinstance(x, Var):
        u = Var('u_' + name)
        aux_eqs.append((u - x).simplify())
        aux_vars.append(u)
        x = u

    diff_vars_x = [x]
    diff_vars_y = [y]
    diff_vars = []
    base_var = x
    for i in range(1, len(num)):
        if base_var.diff_var is None:
            new_diff = DiffVar(name=f'dt_{i}_' + x.name, base_var=base_var)
            diff_vars.append(new_diff)
        diff_vars_x.append(x.diff_var)
        base_var = x.diff_var
    base_var = y
    for i in range(1, len(den)):
        if base_var.diff_var is None:
            new_diff = DiffVar(name=f'dt_{i}_' + y.name, base_var=base_var)

            diff_vars.append(new_diff)
        diff_vars_y.append(y.diff_var)
        base_var = y.diff_var

    # Create the diff equation
    rhs = np.array(diff_vars_x) @ np.array(num)
    lhs = np.array(diff_vars_y) @ np.array(den)

    block = Block()
    block.algebraic_vars = [y] + aux_vars
    block.algebraic_eqs = [lhs - rhs] + aux_eqs
    block.diff_vars = diff_vars

    return block, y, x


def tf_to_diffblock_with_states(num: np.ndarray,
                                den: np.ndarray,
                                x: Var | Expr,
                                y: Var = None, name: Optional[str] = ''):
    """
    num: numerator coefficients [b0,...,bm]
    den: denominator coefficients [a0,...,an], with an != 0
    u:   input Var
    y:   output Var
    """
    if len(num) > len(den):
        raise ValueError("Transfer function is improper: numerator degree > denominator degree.")
    if num[-1] == 0 or den[-1] == 0:
        raise ValueError("Leading coefficient of cannot be zero.")

    if y is None:
        y = Var('y_' + name)

    aux_eqs = []
    aux_vars = []
    # check if x is a expression
    if not isinstance(x, Var):
        u = Var('u_' + name)
        aux_eqs.append(u - x)
        aux_vars.append(u)
        x = u

    # Normalize
    den = [c / den[-1] for c in den]
    num = [c / den[-1] for c in num]

    # States
    x_states = [x]
    y_states = [y]
    y_states.extend([Var(f"y{i}") for i in range(1, len(den))])  # y1,...,yn
    x_states.extend([Var(f"x{i}") for i in range(1, len(num))])  # x1,...,xm

    # Differential equations (canonical form)
    diff_eqs = []
    diff_vars = []
    for i in range(len(y_states) - 1):
        if y_states[i].diff_var is None:
            dy = DiffVar(f"d_{y_states[i].name}", base_var=y_states[i])
            diff_vars.append(dy)
        diff_eqs.append(y_states[i + 1] - y_states[i].diff_var)

    for i in range(len(num) - 1):
        if x_states[i].diff_var is None:
            dx = DiffVar(f"d^{i}_{x_states[i].name}", base_var=x_states[i])
            diff_vars.append(dx)
        diff_eqs.append(x_states[i + 1] - x_states[i].diff_var)

        # Last equation: linear combination
    last_eq = (
            sum(den[i] * y_states[i] for i in range(len(y_states)))
            - sum(num[i] * x_states[i] for i in range(len(x_states)))
    )
    diff_eqs.append(last_eq)

    block = Block(
        algebraic_vars=y_states + x_states[1:] + aux_vars,
        algebraic_eqs=diff_eqs + aux_eqs,
    )
    block.diff_vars = diff_vars
    block.name = 'TF'
    return block, y_states[0]


def tf_to_block_with_states(num: np.ndarray,
                            den: np.ndarray, x):
    """
    num: numerator coefficients [b0,...,bm]
    den: denominator coefficients [a0,...,an], with an != 0
    u:   input Expr or Var
    y:   output Var
    """
    if len(num) >= len(den):
        raise ValueError("Transfer function is improper: numerator degree > denominator degree.")
    if num[-1] == 0 or den[-1] == 0:
        raise ValueError("Leading coefficient of cannot be zero.")

    aux_eqs = []
    aux_vars = []
    # check if xis a expression
    if not isinstance(x, Var):
        u = Var('u')
        aux_eqs.append(u - x)
        aux_vars.append(u)
        x = u

    # Normalize
    den = [c / den[-1] for c in den]
    num = [c / den[-1] for c in num]

    order = len(den)  # system order
    x_states = [x]  # x0
    x_states.extend([Var(f"x{i}") for i in range(1, order + 1)])  # x1,...,xn

    # Differential equations (canonical form)
    state_eqs = []
    state_vars = []
    for i in range(1, order):
        state_eqs.append(x_states[i])
        state_vars.append(x_states[i + 1])

    y_states = [Var(f"y{i}") for i in range(len(num) + 1)]  # x1,...,xn
    for i in range(len(num)):
        state_eqs.append(y_states[i])
        state_vars.append(y_states[i + 1])

    # Last equation: linear combination
    last_eq = (
            sum(den[i] * y_states[i] for i in range(order))
            - sum(num[i] * x_states[i] for i in range(len(num)))
    )

    aux_eqs.append(last_eq)

    block = Block(
        state_eqs=state_eqs,
        state_vars=state_vars,
        algebraic_eqs=aux_eqs,
        # TODO: this is highly suspicious (better add vars to aux_vars)
        algebraic_vars=x_states[0] + y_states[0] + aux_vars,
    )
    return block, y_states[0]


def tf_to_diffblock_with_antiwindup(num: Vec,
                                    den: Vec,
                                    x: Var,
                                    y: Var = None,
                                    name: Optional[str] = '',
                                    sat_min: Expr = Const(float(-1e6)),
                                    sat_max: Expr = Const(float(1e6)),
                                    multilinear=False,
                                    PI: bool = False):
    """
    num: numerator coefficients [b0, ..., bm]
    den: denominator coefficients [a0, ..., an]
    x:   input (Var or Expr)
    y:   output Var
    sat_min, sat_max: saturation limits for anti-windup
    """

    if len(num) > len(den):
        raise ValueError("Transfer function is improper: numerator degree > denominator degree.")
    if num[-1] == 0 or den[-1] == 0:
        raise ValueError("Leading coefficient cannot be zero.")

    if y is None:
        y = Var('y_' + name)

    aux_eqs = []
    aux_vars = []

    # If x is an expression, wrap it in a Var
    if not isinstance(x, Var):
        u = Var('u_' + name)
        aux_eqs.append((u - x).simplify())
        aux_vars.append(u)
        x = u

    diff_vars_x = [x]
    diff_vars_y = [y]
    diff_vars = []

    # Derivative chain for x
    base_var = x
    for i in range(1, len(num)):
        if base_var.diff_var is None:
            new_diff = DiffVar(name=f'dt_{i}_' + x.name, base_var=base_var)
            diff_vars.append(new_diff)
        diff_vars_x.append(x.diff_var)
        base_var = x.diff_var

    # Derivative chain for y
    base_var = y
    for i in range(1, len(den)):
        if base_var.diff_var is None:
            new_diff = DiffVar(name=f'dt_{i}_' + y.name, base_var=base_var)
            diff_vars.append(new_diff)
        diff_vars_y.append(y.diff_var)
        base_var = y.diff_var

    # Base equations
    rhs = np.array(diff_vars_x) @ np.array(num)
    lhs = np.array(diff_vars_y) @ np.array(den)

    # -----------------------------------------------------------
    # ANTI-WINDUP BY MULTIPLYING ALL COEFFICIENTS BY h
    # -----------------------------------------------------------

    # TODO: review multilinear implementation
    # if not multilinear:
    h1 = heaviside(y - sat_min)
    h2 = heaviside(sat_max - y)

    # TODO: review multilinear implementation
    # else:
    #     h1, ml_block1 = heaviside(y - sat_min, name=f'h1_{name}')
    #     h2, ml_block2 = heaviside(sat_max - y, name=f'h2_{name}')

    # Build LHS term-by-term, skipping multiplication on dy
    rhs = Const(0.0)
    lhs = Const(0.0)
    if not PI:
        for i, term in enumerate(np.array(den) * np.array(diff_vars_y)):
            if i != 1:
                lhs += term
        for i, term in enumerate(np.array(num) * np.array(diff_vars_x)):
            rhs += term
    else:
        for i, term in enumerate(np.array(num) * np.array(diff_vars_x)):
            rhs += term

    f = (rhs - lhs) / Const(den[1])
    hf = heaviside(rhs - lhs)
    ha = h1 * h2
    hb = (1 - h1) * hf
    hc = (1 - h2) * (1 - hf)
    h = heaviside(ha + hb + hc)
    # Differential equation (single equation)
    eq_main = (diff_vars_y[1] - h * f).simplify()

    block = Block(
        name=name,
        algebraic_vars=[y] + aux_vars,
        algebraic_eqs=[eq_main] + aux_eqs,
        diff_vars=diff_vars,
    )

    # TODO: review multilinear implementation
    # if multilinear:
    #     block.add(ml_block1)
    #     block.add(ml_block2)
    return block, y


def tf_to_diffblock_with_antiwindup_by_feedback(
        num: np.ndarray,
        den: np.ndarray,
        x,
        y: Var = None,
        name: Optional[str] = '',
        sat_min: Expr = Const(-1e6),
        sat_max: Expr = Const(1e6),
        Kaw: Expr = Const(10.0),  # anti-windup gain (1/Tt)
):
    """
    Implements a back-calculation anti-windup controller using (u_sat - u) as feedback input.
    Works better for implicit solvers
    num: numerator coefficients [b0, ..., bm]
    den: denominator coefficients [a0, ..., an]
    x:   input signal
    y:   output (saturated)
    """

    if len(num) > len(den):
        raise ValueError("Improper TF")

    if y is None:
        y = Var(f'y_{name}')

    aux_eqs = []
    aux_vars = []

    # Wrap input expression
    if not isinstance(x, Var):
        u_in = Var(f'u_in_{name}')
        aux_eqs.append((u_in - x).simplify())
        aux_vars.append(u_in)
        x = u_in

    # --------------------------------------------------
    # Build derivative chains
    # --------------------------------------------------
    diff_vars = []
    diff_x = [x]
    diff_y = [y]

    base = x
    for i in range(1, len(num)):
        dv = DiffVar(f'dt_{i}_{x.name}', base)
        diff_vars.append(dv)
        diff_x.append(dv)
        base = dv

    base = y
    for i in range(1, len(den)):
        dv = DiffVar(f'dt_{i}_{y.name}', base)
        diff_vars.append(dv)
        diff_y.append(dv)
        base = dv

    # --------------------------------------------------
    # Unsaturated output (internal)
    # --------------------------------------------------
    u = Var(f'u_{name}')
    aux_vars.append(u)

    tf_rhs = np.dot(num, diff_x)
    tf_lhs = np.dot(den, diff_y)

    aux_eqs.append((u - tf_rhs).simplify())

    # --------------------------------------------------
    # Saturation
    # --------------------------------------------------
    u_sat = Var(f'u_sat_{name}')
    aux_vars.append(u_sat)

    sat_expr = (
            sat_min
            + (u - sat_min) * heaviside(u - sat_min)
            - (u - sat_max) * heaviside(u - sat_max)
    )

    aux_eqs.append((u_sat - sat_expr).simplify())

    # --------------------------------------------------
    # Main differential equation
    # Add anti-windup ONLY to integrator (dy/dt term)
    # --------------------------------------------------
    lhs = Const(0)
    rhs = Const(0)

    for i, term in enumerate(den * np.array(diff_y)):
        lhs += term

    for term in num * np.array(diff_x):
        rhs += term

    # Anti-windup injection
    rhs += Kaw * (u_sat - u)

    eq_main = (lhs - rhs).simplify()

    block = Block(
        name=name,
        algebraic_vars=[y, u, u_sat] + aux_vars,
        algebraic_eqs=[eq_main] + aux_eqs,
        diff_vars=diff_vars,
    )

    return block, y


class Block:
    """
    Class representing a Block
    """

    def __init__(self,
                 state_vars: List[Var] | None = None,
                 state_eqs: List[Expr] | None = None,
                 algebraic_vars: List[Var] | None = None,
                 algebraic_eqs: List[Expr] | None = None,
                 diff_vars: List[DiffVar] | None = None,
                 reformulated_vars: List[DiffVar] | None = None,
                 differential_eqs: List[Expr] | None = None,
                 parameters: Dict[Var, Const] | None = None,
                 alter_params: List[Var] | None = None,
                 init_values: Dict[Var, Const] | None = None,
                 init_eqs: Dict[Var, Expr] | None = None,
                 children: List["Block"] | None = None,
                 in_vars: List[Var] | None = None,
                 out_vars: List[Var] | None = None,
                 event_dict: Dict[Var, Expr] | None = None,
                 external_mapping: Dict[VarPowerFlowRefferenceType, Var] | None = None,
                 api_obj_mapping: Dict[ParamPowerFlowRefferenceType, Var] | None = None,
                 name: str = "",
                 uid: int | None = None):
        """
        This represents a group of equations or a group of blocks

        :param algebraic_vars: List of non-differential variables (AKA algebraic)
        :param algebraic_eqs: List of equations that provide values for the algebraic variables
        :param state_vars: List of differential variables (AKA state variables)
        :param state_eqs: List of equations that provide values for the state variables
        :param children: List of other blocks to be flattened later into this block
        :param in_vars: List of variables from other blocks that we use here
        :param out_vars: List of variables that already exist in algebraic_vars or state_vars that we want to expose
        :param init_eqs: List of equations that help initializing the block variables (algebraic and state)
        :param event_dict: Dictionary of parameters that can change during the simulations
        :param external_mapping: Dictionary of vars that are related to the Power flow initialization
        :param name: name of the block
        """

        self.name: str = name

        self.uid: int = _new_uid() if uid is None else uid
        self.vars2device: Dict[int, PhysicalDevice] = dict()
        self.vars_glob_name2uid: Dict[str, int] = dict()

        self.state_vars: List[Var] = list() if state_vars is None else state_vars
        self.state_eqs: List[Expr] = list() if state_eqs is None else state_eqs

        self.algebraic_vars: List[Var] = list() if algebraic_vars is None else algebraic_vars
        self.algebraic_eqs: List[Expr] = list() if algebraic_eqs is None else algebraic_eqs

        self.diff_vars: List[DiffVar] = list() if diff_vars is None else diff_vars
        self.reformulated_vars: List[DiffVar] = list() if reformulated_vars is None else reformulated_vars
        self.differential_eqs: List[Expr] = list() if differential_eqs is None else differential_eqs

        # initialization
        self.init_eqs: Dict[Var, Expr] = dict() if init_eqs is None else init_eqs

        # vars to make this recursive
        self.children: List["Block"] = list() if children is None else children

        self.in_vars: List[Var] = list() if in_vars is None else in_vars
        self.out_vars: List[Var] = list() if out_vars is None else out_vars

        self.parameters: Dict[Var, Const] = dict() if parameters is None else parameters

        self.alter_params: List[Var] = list() if alter_params is None else alter_params

        self.external_mapping: Dict[VarPowerFlowRefferenceType, Var] = (dict()
                                                                        if external_mapping is None
                                                                        else external_mapping)

        self.api_obj_mapping: Dict[ParamPowerFlowRefferenceType, Var] = (dict()
                                                                         if api_obj_mapping is None
                                                                         else api_obj_mapping)
        # initialization
        self.init_values: Dict[Var, Const] = dict() if init_values is None else init_values

        self.var_mapping = {v.name: v for v in self.algebraic_vars}

        # Dictionary of Variables and their Expressions that appear due to an event
        # this is the dictionary of "parameters" that may change and their equations
        self.event_dict: Dict[Var, Expr | Const] = dict() if event_dict is None else event_dict
        
    def set_parameter(self, ref: ParamPowerFlowRefferenceType, cte: Const):
        """
        assign a parameter to the block parameters

        :param ref: 
        :param cte: 
        :return: 
        """
        var = self.api_obj_mapping.get(ref, None)
        if var is not None:
            self.parameters[var] = cte

    def check_empty(self) -> bool:
        """
        check if a model does not have state and algebraic variables

        :return:
        """
        return (len(self.state_vars) + len(self.algebraic_vars)) == 0

    def empty(self) -> bool:
        """
        check if a model is empty
        :return:
        """
        if not self.children:
            empty = self.check_empty()
            if empty:
                return empty
        else:
            empty = self.check_empty()
            if not empty:
                return empty

            for child in self.children:
                child.empty()

        return False

    def E(self, d: VarPowerFlowRefferenceType) -> Var:
        """

        returns the value of the external mapping coresponding to d VarPowerFlowRefferenceType

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

    def add(self, val: Block):
        """
        Add another block to children of the model
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

    def unify_blocks(self):
        """
        This function collects all variables and equations of a block, returns a flat block
        Returns
        -------
        Union[None, VeraGridEngine.Utils.Symbolic.block.Block]
        """
        mdl_placeholder = Block()
        for b in self.get_all_blocks():
            mdl_placeholder.algebraic_vars.extend(b.algebraic_vars)
            mdl_placeholder.algebraic_eqs.extend(b.algebraic_eqs)
            mdl_placeholder.state_vars.extend(b.state_vars)
            mdl_placeholder.state_eqs.extend(b.state_eqs)
            mdl_placeholder.diff_vars.extend(b.diff_vars)
            mdl_placeholder.external_mapping.update(b.external_mapping)
            for event_param, eq in b.event_dict.items():
                mdl_placeholder.event_dict[event_param] = eq

            for param, const in b.parameters.items():
                mdl_placeholder.parameters[param] = const

            for var, init_eq in b.init_eqs.items():
                mdl_placeholder.init_eqs[var] = init_eq
        self.algebraic_vars = mdl_placeholder.algebraic_vars
        self.algebraic_eqs = mdl_placeholder.algebraic_eqs
        self.state_vars = mdl_placeholder.state_vars
        self.state_eqs = mdl_placeholder.state_eqs
        self.diff_vars = mdl_placeholder.diff_vars
        self.event_dict = mdl_placeholder.event_dict
        self.parameters = mdl_placeholder.parameters
        self.init_eqs = mdl_placeholder.init_eqs
        self.external_mapping = mdl_placeholder.external_mapping
        self.children = list()

    def get_vars(self) -> List[Var]:
        """
        returns variables of the flat block
        :return: List[Var]
        """
        vars_list = list()
        variables_lists = [self.algebraic_vars, self.state_vars, self.diff_vars]
        for lst in variables_lists:
            for var in lst:
                vars_list.append(var)

        return vars_list

    def get_all_vars(self):
        """
        returns all the variables of a block
        :return:
        """
        variables: List[Var] = list()
        all_blocks = self.get_all_blocks()
        for blk in all_blocks:
            variables.extend(blk.algebraic_vars)
            variables.extend(blk.state_vars)
            variables.extend(blk.diff_vars)
        return variables

    def update_equations(self, old, new):
        """
        this function changes the variable old for the variable new in a block
        :param old:
        :param new:
        :return:
        """
        init_eqs_new = dict()
        event_dict_new = dict()

        for i, eq in enumerate(self.algebraic_eqs):
            new_equ = eq.subs({old: new})
            self.algebraic_eqs[i] = new_equ
        for i, eq in enumerate(self.state_eqs):
            new_equ = eq.subs({old: new})
            self.state_eqs[i] = new_equ
        for i, eq in enumerate(self.differential_eqs):
            new_equ = eq.subs({old: new})
            self.differential_eqs[i] = new_equ
        for var, expr in self.init_eqs.items():
            new_expr = expr.subs({old: new})
            if var is old:
                init_eqs_new.update({new: new_expr})
            else:
                init_eqs_new.update({var: new_expr})

        self.init_eqs = init_eqs_new

        for var, expr in self.event_dict.items():
            new_expr = expr.subs({old: new})
            if var is old:
                event_dict_new.update({new: new_expr})
            else:
                event_dict_new.update({var: new_expr})

        self.event_dict = event_dict_new

        for var_pf_ref, mdl_var in self.external_mapping.items():
            if mdl_var is old:
                self.external_mapping.update({var_pf_ref: new})

    def update_model(self, old, new):
        """
        :param old:
        :param new:
        :return:
        """
        self.update_equations(old, new)
        if self.children:
            for child in self.children:
                child.update_model(old, new)

    def connect(self, vars_to_subs: List[Var], incoming_vars: List[Var]):
        """
        Function to connect two blocks by variables sharing
        """

        for var_to_subs, incoming_var in zip(vars_to_subs, incoming_vars):
            self.update_model(var_to_subs, incoming_var)

class BlockType(Enum):
    "this class contains the existing types of blocks"
    CONST = auto()
    GAIN = auto()
    SUM = auto()
    SUBSTR = auto()
    PRODUCT = auto()
    DIVIDE = auto()
    ABS = auto()
    GENRAW = auto()
    GENQEC = auto()
    GOV = auto()
    STAB = auto()
    EXCITER = auto()
    LINE = auto()
    LOAD = auto()
    GENERIC = auto()
    BUS_CONNECTION = auto()
    EXTERNAL_MAPPING = auto()


# ----------------------------------------------------------------------------------------------------------------------
# Pre defined blocks
# ----------------------------------------------------------------------------------------------------------------------

def constant(item_name: str = "") -> Block:
    """

    :param item_name:
    :return:
    """
    name: str = "const_"
    y = Var(name + item_name)
    param = Var("param_" + item_name)

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - param],
        out_vars=[y],
        event_dict={param: Const(0.0)},
        name="const"
    )

    return blk


def gain(item_name: str = "") -> Block:
    """

    :param item_name:
    :return:
    """
    inputs = [Var("inp_num_" + item_name)]
    name: str = "gain"
    y = Var(name + item_name)
    gain_param = Var("gain_param_" + item_name)

    expr: Expr = gain_param * inputs[0]
    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        out_vars=[y],
        in_vars=inputs,
        event_dict={gain_param: Const(0.0)},
        name="gain"
    )
    return blk


def variable(name: str = "variable_", vartype: str = "vartype_") -> Tuple[Var, Block]:
    y = Var(name)
    if vartype == 'state':
        blk = Block(state_vars=[y])
    else:
        blk = Block(algebraic_vars=[y])
    return y, blk


def adder(item_name: str = "") -> Block:
    """

    :param item_name:
    :return:
    """
    inputs = [Var("sum_in_1_" + item_name),
              Var("sum_in_2_" + item_name)]  # will not be specified if inputs can be more than 2
    y = Var("sum_out_" + item_name)

    expr: Expr = inputs[0]
    for i, inpt in enumerate(inputs):
        if i > 0:
            expr += inpt

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="sum"
    )

    return blk


def substract(item_name: str = "") -> Block:
    """

    :param item_name:
    :return:
    """
    inputs = [Var("minuend_" + item_name), Var("subtrahend_" + item_name)]
    y = Var("difference_" + item_name)

    expr: Expr = inputs[0] - inputs[1]

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="substraction"
    )

    return blk


def product(item_name: str = "") -> Block:
    """

    :param item_name:
    :return:
    """
    inputs = [Var("factor1_" + item_name),
              Var("factor2_" + item_name)]  # will not be specified if inputs can be more than 2
    y = Var("product_out_" + item_name)

    expr: Expr = inputs[0] * inputs[1]

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="product"
    )

    return blk


def divide(item_name: str = "") -> Block:
    """

    :param item_name:
    :return:
    """
    inputs = [Var("divident_" + item_name),
              Var("divisor_" + item_name)]  # will not be specified if inputs can be more than 2
    y = Var("quotient_" + item_name)

    expr: Expr = inputs[0] / inputs[1]

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="divide"
    )

    return blk


def absolut(item_name: str = "") -> Block:
    """

    :param item_name:
    :return:
    """
    inputs = [Var("inp_num_" + item_name)]  # will not be specified if inputs can be more than 2
    y = Var("absolut_" + item_name)

    expr: Expr = abs(inputs[0])

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="abs"
    )

    return blk


def integrator(u: Var | Const, name: str = "x") -> Tuple[Var, Block]:
    x = Var(name)
    blk = Block(state_vars=[x], state_eqs=[u])
    return x, blk


def pi_controller(err: Var, kp: float, ki: float, name: str = "pi") -> Block:
    up, blk_kp = gain()
    ie, blk_int = integrator(err)
    ui, blk_ki = gain()
    u, blk_sum = adder()
    return Block(name="",
                 children=[blk_kp, blk_int, blk_ki, blk_sum],
                 in_vars=[err],
                 out_vars=[u])


def generic(state_inputs: int,
            state_outputs: Sequence[str],
            algebraic_inputs: int,
            algebraic_outputs: Sequence[str]) -> Block:
    """

    :param state_inputs:
    :param state_outputs:
    :param algebraic_inputs:
    :param algebraic_outputs:
    :return:
    """
    blk = Block(
        name="generic",
        in_vars=[Var(f"Vport{i}") for i in range(state_inputs + algebraic_inputs)]
    )

    for i, v in enumerate(state_outputs):
        var = Var(v)
        blk.state_vars.append(var)
        blk.out_vars.append(var)

    for i, v in enumerate(algebraic_outputs):
        var = Var(v)
        blk.algebraic_vars.append(var)
        blk.out_vars.append(var)

    return blk
