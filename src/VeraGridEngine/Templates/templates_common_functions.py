# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
from typing import Tuple,  Optional

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr, heaviside)
from VeraGridEngine.Utils.Symbolic.block import Block


def tf_to_block(var_factory: VarFactory,
                num: Vec,
                den: Vec,
                x: Var | Expr,
                y: Var = None,
                name: Optional[str] = '') -> Tuple[Block, Var]:
    """
    "transform definition" to block
    num: list of numerator coefficients [b0, b1, ..., bm]
    den: list of denominator coefficients [a0, a1, ..., an]
    x:   sympy symbol for input
    y:   sympy function of t for output
    """
    if len(num) > len(den):
        raise ValueError("Transfer function is improper: numerator degree > denominator degree.")

    if y is None:
        y = var_factory.add_var('y_' + name)

    aux_eqs = []
    aux_vars = []
    # check if is an expression
    if not isinstance(x, Var):
        u = var_factory.add_var('u_' + name)
        aux_eqs.append((u - x).simplify())
        aux_vars.append(u)
        x = u

    diff_vars_x = [x]
    diff_vars_y = [y]
    diff_vars = []
    base_var = x
    for i in range(1, len(num)):
        if base_var.diff_var is None:
            new_diff = var_factory.add_diff_var(name=f'dt_{i}_' + x.name, base_var=base_var)
            diff_vars.append(new_diff)
        diff_vars_x.append(x.diff_var)
        base_var = x.diff_var
    base_var = y
    for i in range(1, len(den)):
        if base_var.diff_var is None:
            new_diff = var_factory.add_diff_var(name=f'dt_{i}_' + y.name, base_var=base_var)
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


def tf_to_diffblock_with_output(
        var_factory: VarFactory,
        num: Vec,
        den: Vec,
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
        y = var_factory.add_var('y_' + name)

    aux_eqs = []
    aux_vars = []
    # check if is an expression
    if not isinstance(x, Var):
        u = var_factory.add_var('u_' + name)
        aux_eqs.append((u - x).simplify())
        aux_vars.append(u)
        x = u

    diff_vars_x = [x]
    diff_vars_y = [y]
    diff_vars = []
    base_var = x
    for i in range(1, len(num)):
        if base_var.diff_var is None:
            new_diff = var_factory.add_diff_var(name=f'dt_{i}_' + x.name, base_var=base_var)
            diff_vars.append(new_diff)
        diff_vars_x.append(x.diff_var)
        base_var = x.diff_var
    base_var = y
    for i in range(1, len(den)):
        if base_var.diff_var is None:
            new_diff = var_factory.add_diff_var(name=f'dt_{i}_' + y.name, base_var=base_var)

            diff_vars.append(new_diff)
        diff_vars_y.append(y.diff_var)
        base_var = y.diff_var

    # Create the diff equation
    rhs: Vec = np.array(diff_vars_x) @ np.array(num)
    lhs: Vec = np.array(diff_vars_y) @ np.array(den)

    block = Block()
    block.algebraic_vars = [y] + aux_vars
    block.algebraic_eqs = [lhs - rhs] + aux_eqs
    block.diff_vars = diff_vars

    return block, y, x


def tf_to_diffblock_with_states(
        var_factory: VarFactory,
        num: Vec,
        den: Vec,
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
        y = var_factory.add_var('y_' + name)

    aux_eqs = []
    aux_vars = []
    # check if x is a expression
    if not isinstance(x, Var):
        u = var_factory.add_var('u_' + name)
        aux_eqs.append(u - x)
        aux_vars.append(u)
        x = u

    # Normalize
    den = [c / den[-1] for c in den]
    num = [c / den[-1] for c in num]

    # States
    x_states = [x]
    y_states = [y]
    y_states.extend([var_factory.add_var(f"y{i}") for i in range(1, len(den))])  # y1,...,yn
    x_states.extend([var_factory.add_var(f"x{i}") for i in range(1, len(num))])  # x1,...,xm

    # Differential equations (canonical form)
    diff_eqs = []
    diff_vars = []
    for i in range(len(y_states) - 1):
        if y_states[i].diff_var is None:
            dy = var_factory.add_diff_var(f"d_{y_states[i].name}", base_var=y_states[i])
            diff_vars.append(dy)
        diff_eqs.append(y_states[i + 1] - y_states[i].diff_var)

    for i in range(len(num) - 1):
        if x_states[i].diff_var is None:
            dx = var_factory.add_diff_var(f"d^{i}_{x_states[i].name}", base_var=x_states[i])
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


def tf_to_block_with_states(
        var_factory: VarFactory,
        num: Vec,
        den: Vec, x):
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
        u = var_factory.add_var('u')
        aux_eqs.append(u - x)
        aux_vars.append(u)
        x = u

    # Normalize
    den = [c / den[-1] for c in den]
    num = [c / den[-1] for c in num]

    order = len(den)  # system order
    x_states = [x]  # x0
    x_states.extend([var_factory.add_var(f"x{i}") for i in range(1, order + 1)])  # x1,...,xn

    # Differential equations (canonical form)
    state_eqs = []
    state_vars = []
    for i in range(1, order):
        state_eqs.append(x_states[i])
        state_vars.append(x_states[i + 1])

    y_states = [var_factory.add_var(f"y{i}") for i in range(len(num) + 1)]  # x1,...,xn
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


def tf_to_diffblock_with_antiwindup(
        var_factory: VarFactory,
        num: Vec,
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
        y = var_factory.add_var('y_' + name)

    aux_eqs = []
    aux_vars = []

    # If x is an expression, wrap it in a Var
    if not isinstance(x, Var):
        u = var_factory.add_var('u_' + name)
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
            new_diff = var_factory.add_diff_var(name=f'dt_{i}_' + x.name, base_var=base_var)
            diff_vars.append(new_diff)
        diff_vars_x.append(x.diff_var)
        base_var = x.diff_var

    # Derivative chain for y
    base_var = y
    for i in range(1, len(den)):
        if base_var.diff_var is None:
            new_diff = var_factory.add_diff_var(name=f'dt_{i}_' + y.name, base_var=base_var)
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
        var_factory: VarFactory,
        num: Vec,
        den: Vec,
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
        y = var_factory.add_var(f'y_{name}')

    aux_eqs = []
    aux_vars = []

    # Wrap input expression
    if not isinstance(x, Var):
        u_in = var_factory.add_var(f'u_in_{name}')
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
        dv = var_factory.add_diff_var(f'dt_{i}_{x.name}', base_var=base)
        diff_vars.append(dv)
        diff_x.append(dv)
        base = dv

    base = y
    for i in range(1, len(den)):
        dv = var_factory.add_diff_var(f'dt_{i}_{y.name}', base_var=base)
        diff_vars.append(dv)
        diff_y.append(dv)
        base = dv

    # --------------------------------------------------
    # Unsaturated output (internal)
    # --------------------------------------------------
    u = var_factory.add_var(f'u_{name}')
    aux_vars.append(u)

    tf_rhs = np.dot(num, diff_x)
    tf_lhs = np.dot(den, diff_y)

    aux_eqs.append((u - tf_rhs).simplify())

    # --------------------------------------------------
    # Saturation
    # --------------------------------------------------
    u_sat = var_factory.add_var(f'u_sat_{name}')
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
