# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
from typing import Tuple, Optional, List, Any

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr, heaviside, expression2numba, get_expression_vars)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType


def tf_to_block(var_factory: VarFactory,
                num: List[Var | float],
                den: List[Var | float],
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

    aux_eqs: List[Expr] = []
    aux_vars: List[Expr] = []
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
        diff_vars_x.append(base_var.diff_var)
        base_var = base_var.diff_var
    base_var = y
    for i in range(1, len(den)):
        if base_var.diff_var is None:
            new_diff = var_factory.add_diff_var(name=f'dt_{i}_' + y.name, base_var=base_var)
            diff_vars.append(new_diff)
        diff_vars_y.append(base_var.diff_var)
        base_var = base_var.diff_var

    # Create the diff equation
    rhs = np.array(diff_vars_x) @ np.array(num)
    lhs = np.array(diff_vars_y) @ np.array(den)

    block = Block()
    block.algebraic_vars = [y] + aux_vars
    block.algebraic_eqs = [lhs - rhs] + aux_eqs
    block.diff_vars = diff_vars
    block.in_vars = [x]  # Input is x
    block.out_vars = [y]  # Output is y

    return block, y


def tf_to_diffblock_with_output(
        var_factory: VarFactory,
        num: List[Var | float],
        den: List[Var | float],
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

    aux_eqs: List[Var | Expr] = []
    aux_vars: List[Var | Expr] = []
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
        diff_vars_x.append(base_var.diff_var)
        base_var = base_var.diff_var
    base_var = y
    for i in range(1, len(den)):
        if base_var.diff_var is None:
            new_diff = var_factory.add_diff_var(name=f'dt_{i}_' + y.name, base_var=base_var)
            diff_vars.append(new_diff)
        diff_vars_y.append(base_var.diff_var)
        base_var = base_var.diff_var

    # Create the diff equation
    rhs: Vec = np.array(diff_vars_x) @ np.array(num)
    lhs: Vec = np.array(diff_vars_y) @ np.array(den)

    block = Block()
    block.algebraic_vars = [y] + aux_vars
    block.algebraic_eqs = [lhs - rhs] + aux_eqs
    block.diff_vars = diff_vars

    return block, y, x


def tf_to_block_with_states(
        var_factory: VarFactory,
        num: List[Var | float],
        den: List[Var | float],
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


def tf_to_block2(
        var_factory: VarFactory,
        num: List[Var | float],
        den: List[Var | float],
        x: Var | float,
        y: Var = None,
        name:str = ''):
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

    aux_eqs: List[Expr] = []
    aux_vars: List[Var] = []
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
    x_states: List[Var] = [x]  # x0
    x_states.extend([var_factory.add_var(f"x{i}") for i in range(1, order + 1)])  # x1,...,xn

    # Differential equations (canonical form)
    state_eqs = []
    state_vars = []
    for i in range(1, order):
        state_eqs.append(x_states[i])
        state_vars.append(x_states[i + 1])

    y_states: List[Var] = [var_factory.add_var(f"y{i}") for i in range(len(num) + 1)]  # x1,...,xn
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
        num: List[Var | float],
        den: List[Var | float],
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
        num: List[Var | float],
        den: List[Var | float],
        x: Var,
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


def deadband_block(
        var_factory: VarFactory,
        x: Var | Expr,
        y: Var = None,
        name: Optional[str] = '',
        deadband: Expr = Const(0.1)) -> Tuple[Block, Var]:
    """
    Creates a deadband function block.
    
    The deadband function returns:
    - 0 when input is within the deadband [-deadband, +deadband]
    - input - deadband when input > deadband
    - input + deadband when input < -deadband
    
    Parameters:
    -----------
    var_factory: VarFactory instance for creating variables
    x: input signal (Var or Expr)
    y: output variable (optional, created if None)
    name: name prefix for variables
    deadband: deadband threshold (default 0.1)
    
    Returns:
    --------
    Tuple of (Block, output_var)
    """
    if y is None:
        y = var_factory.add_var('y_deadband_' + name)
    
    aux_eqs = []
    aux_vars = []
    
    # Wrap input expression if needed
    if not isinstance(x, Var):
        u = var_factory.add_var('u_deadband_' + name)
        aux_eqs.append((u - x).simplify())
        aux_vars.append(u)
        x = u
    
    # Deadband logic using Heaviside step functions
    # y = (u - deadband) * H(u - deadband) + (u + deadband) * H(-deadband - u)
    #   = (u - deadband) * H(u - deadband) + (u + deadband) * H(-u - deadband)
    
    h_pos = heaviside(x - deadband)
    h_neg = heaviside(-x - deadband)
    
    # Output expression
    output_expr = (x - deadband) * h_pos + (x + deadband) * h_neg
    
    # Algebraic equation: y - output_expr = 0
    eq = (y - output_expr).simplify()
    
    block = Block(
        name=name + '_deadband',
        algebraic_vars=[y] + aux_vars,
        algebraic_eqs=[eq] + aux_eqs,
        diff_vars=[]
    )
    
    return block, y


def simulate_single_block(
    block: Block,
    input_values: list[float] | Callable[[float], list[float]],
    t0: float = 0.0,
    t_end: float = 10.0,
    time_step: float = 0.001,
    max_iter: int = 100,
    tol: float = 1e-6,
    input_var_names: Optional[list[str]] = None,
    output_var_names: Optional[list[str]] = None,
    init_guess: Optional[dict[str, float]] = None,
    verbose: bool = False,
) -> Tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Simulate a single block with given input values.
    
    This function runs a dynamic simulation for a single block using
    Backward Euler integration with SymbolicVector, SymbolicJacobian, and
    SymbolicDerivative for proper numerical integration.
    
    Parameters:
    -----------
    block: The Block to simulate
    input_values: List of input values (constant) or callable f(t) -> list[float] (time-varying)
    t0: Initial time (default 0.0)
    t_end: End time (default 10.0)
    time_step: Simulation time step (default 0.001)
    max_iter: Maximum Newton iterations per time step (default 100)
    tol: Convergence tolerance (default 1e-6)
    input_var_names: Optional list of variable names to treat as inputs.
                    If None, uses block.in_vars
    output_var_names: Optional list of variable names to record as outputs.
                     If None, uses block.out_vars
    init_guess: Optional dictionary of initial guesses for variables
    
    Returns:
    --------
    Tuple of (time_array, solution_array, variable_names)
    - time_array: 1D array of time points
    - solution_array: 2D array of shape (n_time_steps, n_variables)
    - variable_names: List of variable names corresponding to solution columns
    """
    import scipy.sparse as sp
    from scipy.sparse.linalg import spsolve, lsqr
    from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, get_namespace
    from VeraGridEngine.Utils.Symbolic.block_solver import SymbolicVector, SymbolicJacobian, SymbolicDerivative
    
    # Determine input variables first
    if input_var_names is not None:
        input_vars = []
        for name in input_var_names:
            # Find the variable in block
            for var in block.algebraic_vars + block.state_vars + list(block.diff_vars):
                if var.name == name:
                    input_vars.append(var)
                    break
    elif block.in_vars:
        input_vars = list(block.in_vars)
    else:
        input_vars = []
    
    # Build mapping from diff vars to their base vars first
    diff_to_base = {}
    for var in block.diff_vars:
        if hasattr(var, 'base_var') and var.base_var is not None:
            diff_to_base[var] = var.base_var
    
    # Sort diff_vars by derivative order
    def get_derivative_order(var, order=0):
        if var not in diff_to_base:
            return order
        return get_derivative_order(diff_to_base[var], order + 1)
    
    sorted_diff_vars = sorted(diff_to_base.keys(), key=lambda v: get_derivative_order(v))
    
    # Collect all variables from the block (excluding ALL diff vars)
    # Diff vars are computed separately via SymbolicDerivative
    all_vars = []
    var_name_to_idx = {}
    
    # Add algebraic variables
    for i, var in enumerate(block.algebraic_vars):
        var_name_to_idx[var.name] = len(all_vars)
        all_vars.append(var)
    
    # Add state variables
    for i, var in enumerate(block.state_vars):
        var_name_to_idx[var.name] = len(all_vars)
        all_vars.append(var)
    
    # Add input variables (if not already in all_vars)
    for var in input_vars:
        if var.name not in var_name_to_idx:
            var_name_to_idx[var.name] = len(all_vars)
            all_vars.append(var)
    
    n_vars = len(all_vars)
    n_algebraic = len(block.algebraic_vars)
    n_states = len(block.state_vars)
    n_diff = len(block.diff_vars)
    
    # Determine output variables
    if output_var_names is not None:
        output_vars = [all_vars[var_name_to_idx[name]] for name in output_var_names
                      if name in var_name_to_idx]
    elif block.out_vars:
        output_vars = block.out_vars
    else:
        output_vars = all_vars
    
    # Create mapping from var uid to index
    uid2idx = {var.uid: i for i, var in enumerate(all_vars)}
    
    # Identify solver variables (exclude inputs and diff vars' base variables)
    diff_to_base = {}
    for var in block.diff_vars:
        if hasattr(var, 'base_var') and var.base_var is not None:
            diff_to_base[var] = var.base_var
    
    # All equations: algebraic + state
    all_eqs = block.algebraic_eqs + block.state_eqs
    
    # Sort diff_vars by derivative order
    def get_derivative_order(var, order=0):
        if var not in diff_to_base:
            return order
        return get_derivative_order(diff_to_base[var], order + 1)
    
    sorted_diff_vars = sorted(diff_to_base.keys(), key=lambda v: get_derivative_order(v))
    
    # Build compiler names dictionaries for SymbolicVector and SymbolicJacobian
    compiler_names_dict: Dict[int, str] = {}
    alias_names_dict: Dict[int, str] = {}
    
    # vars array: algebraic + state variables + input variables (appended at end)
    for i, var in enumerate(all_vars):
        compiler_names_dict[var.uid] = f"vars[{i}]"
        alias_names_dict[var.uid] = f"vars_{i}"
    
    # Add input variables to vars array (if not already present)
    input_var_idx_start = len(all_vars)
    for i, var in enumerate(input_vars):
        if var.uid not in compiler_names_dict:
            idx = input_var_idx_start + i
            compiler_names_dict[var.uid] = f"vars[{idx}]"
            alias_names_dict[var.uid] = f"vars_input_{i}"
    
    # diff array: derivative variables
    for i, var in enumerate(sorted_diff_vars):
        compiler_names_dict[var.uid] = f"diff[{i}]"
        alias_names_dict[var.uid] = f"diff_{i}"
    
    # event_params array: time, dt, delta (dt at index 1, i.e., -2 from end)
    # Create a dummy dt variable for Jacobian computation
    dt_var = Var(name='dt')
    compiler_names_dict[dt_var.uid] = "event_params[1]"
    alias_names_dict[dt_var.uid] = "dt"
    
    # Add any constants that appear in equations to compiler dicts
    from VeraGridEngine.Utils.Symbolic.symbolic import Const
    vars_in_eqs = set()
    for eq in all_eqs:
        vars_in_eqs.update(eq.get_vars())
    
    for var in vars_in_eqs:
        if var.uid not in compiler_names_dict:
            if isinstance(var, Const):
                # Constants are compiled directly as their values
                pass
            else:
                # Other variables get a default mapping
                compiler_names_dict[var.uid] = f"vars[{len(all_vars)}]"
                alias_names_dict[var.uid] = f"vars_extra_{len(all_vars)}"
    
    # Add input variables to compiler dicts (treated as constants)
    input_var_set = set(v.uid for v in input_vars)
    
    # Identify solver variables (non-input, non-diff vars)
    # Diff vars are computed from their base vars via discretization, not solved directly
    solver_vars = [var for var in all_vars 
                   if var.uid not in input_var_set and var not in diff_to_base.keys()]
    solver_var_indices = [uid2idx[v.uid] for v in solver_vars]
    n_solver = len(solver_vars)
    
    # Create index mapping for solver vars
    uid2idx_solver = {var.uid: i for i, var in enumerate(solver_vars)}
    
    # Compile RHS function using SymbolicVector
    # Substitute input variables with constants (will be updated each step)
    _rhs_func = SymbolicVector(
        eqs=all_eqs,
        compiler_names_dict=compiler_names_dict,
        alias_names_dict=alias_names_dict,
        use_jit=True
    )
    
    # Compile Jacobian using SymbolicJacobian
    _jac_func = SymbolicJacobian(
        eqs=all_eqs,
        variables=solver_vars,
        diff_variables=block.diff_vars,
        compiler_names_dict=compiler_names_dict,
        alias_names_dict=alias_names_dict,
        uid2idx_vars=uid2idx_solver,
        dt=dt_var,
        use_jit=True
    )
    
    # Compile derivative computation using SymbolicDerivative
    _deriv_func = SymbolicDerivative(
        vars=all_vars,
        uid2idx_vars=uid2idx,
        diff_vars=sorted_diff_vars,
        compiler_names_dict=compiler_names_dict,
        use_jit=True
    )
    
    # Initialize solution
    x = np.zeros(n_vars)
    
    # Apply initial guesses
    if init_guess:
        for name, val in init_guess.items():
            if name in var_name_to_idx:
                x[var_name_to_idx[name]] = val
    
    # Apply block init values
    for var, const in block.init_values.items():
        if var.uid in uid2idx:
            x[uid2idx[var.uid]] = const.value
    
    # Determine if input is callable (time-varying) or constant
    is_callable_input = callable(input_values)
    
    # Apply initial input values
    if is_callable_input:
        input_vals_t0 = input_values(t0)
    else:
        input_vals_t0 = input_values
    
    for i, (var, val) in enumerate(zip(input_vars, input_vals_t0)):
        if var.uid in uid2idx:
            x[uid2idx[var.uid]] = val
    
    # Initialize derivative values (all zeros)
    dx = np.zeros(n_diff)
    dx_last = np.zeros(n_diff)
    
    # Time stepping arrays
    n_steps = int(np.ceil((t_end - t0) / time_step))
    t = np.zeros(n_steps + 1)
    y = np.zeros((n_steps + 1, n_vars))
    
    t[0] = t0
    y[0, :] = x
    
    # Event params: [time, dt, ...] - dt at index -2
    n_event_params = 3  # time, dt, delta
    event_params = np.ones(n_event_params)
    event_params[-2] = time_step  # dt
    
    # Empty params array (no parameters for now)
    params = np.array([])
    
    # Simulation loop
    for step in range(n_steps):
        t_step = t[step]
        x_n = y[step, :].copy()
        x_new = x_n.copy()
        
        # Get input values at current time
        if is_callable_input:
            input_vals_step = input_values(t_step + time_step)
        else:
            input_vals_step = input_values
        
        # Apply input values to x_new
        for i, (var, val) in enumerate(zip(input_vars, input_vals_step)):
            if var.uid in uid2idx:
                x_new[uid2idx[var.uid]] = val
        
        # Newton iteration
        converged = False
        residual_norm = float('inf')
        
        for iteration in range(max_iter):
            # Compute derivatives using SymbolicDerivative
            dx = _deriv_func(x_new, x_n, dx_last, time_step)
            
            # Compute residual using SymbolicVector
            residual = _rhs_func(x_new, dx, event_params, params)
            
            residual_norm = np.linalg.norm(residual, np.inf)
            
            if residual_norm < tol:
                converged = True
                break
            
            # Compute Jacobian using SymbolicJacobian
            J_full = _jac_func(x_new, dx, event_params, params, time_step)
            
            # Extract Jacobian for solver variables only
            J_solver = J_full[:, solver_var_indices]
            
            # Solve linear system
            try:
                delta = spsolve(J_solver, -residual)
                if delta is None or not np.all(np.isfinite(delta)):
                    raise ValueError("spsolve returned non-finite values")
            except Exception:
                # Fallback to least squares
                delta, *_ = lsqr(J_solver, -residual)[:1]
                if not np.all(np.isfinite(delta)):
                    # Last resort: fixed-point iteration
                    delta = -0.1 * residual[:n_solver] if len(residual) >= n_solver else np.zeros(n_solver)
            
            # Update solver variables
            for i, idx in enumerate(solver_var_indices):
                x_new[idx] += delta[i]
            
            # Re-apply input values to ensure they stay fixed
            for i, (var, val) in enumerate(zip(input_vars, input_vals_step)):
                if var.uid in uid2idx:
                    x_new[uid2idx[var.uid]] = val
            
            # Recompute derivatives with updated x_new for consistency
            dx = _deriv_func(x_new, x_n, dx_last, time_step)
        
        # Store solution
        y[step + 1, :] = x_new
        t[step + 1] = t[step] + time_step
        
        # Update dx_last for next step
        dx_last = dx.copy()
        
        if not converged and verbose:
            print(f"Warning: Did not converge at step {step}, residual={residual_norm:.2e}")
    
    return t, y, [var.name for var in all_vars]

def connect_rms_models(mdl1: Block, mdl2: Block):
    """
    This function substitutes input variables for output variables to connect two rms models
    :param mdl1:
    :param mdl2:
    :return:
    """
    # connect inputs mdl2 with outputs mdl1
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == inpt.ref
    ]

    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])

    # connect inputs mdl2 with outputs mdl1
    pairs = [
        (outp, inpt)
        for outp in mdl2.out_vars
        for inpt in mdl1.in_vars
        if outp.ref == inpt.ref
    ]

    for outp, inpt in pairs:
        mdl1.connect([inpt], [outp])

    print("")


def set_rms_model(device: Any, model:Block):
    """
    Set the RMS model
    :return:
    :rtype:
    """
    # connect bus variables

    if device.device_type in [DeviceType.BranchDevice, DeviceType.LineDevice, DeviceType.Transformer2WDevice, DeviceType.Transformer3WDevice]:
        if not device.bus_from.rms_model.model.empty():
            connect_rms_models(device.bus_from.rms_model.model, model)
        else:
            raise ValueError(f"Connection Bus RMS model cannot be empty, initialize {device.bus_from.name} RMS model")

        if not device.bus_to.rms_model.model.empty():
            connect_rms_models(device.bus_to.rms_model.model, model)
        else:
            raise ValueError(f"Connection Bus RMS model cannot be empty, initialize {device.bus_to.name} RMS model")

    else:
        if not device.bus.rms_model.model.empty():
            connect_rms_models(device.bus.rms_model.model, model)

        else:
            raise ValueError(f"Connection Bus RMS model cannot be empty, initialize {device.bus.name} RMS model")

    device.rms_model.model = model


