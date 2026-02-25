# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
from typing import Tuple, List, Optional, Dict, Callable, Union

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr, heaviside, expression2numba, get_expression_vars)
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
    Backward Euler integration. It's designed for debugging and testing
    individual blocks without requiring a full grid setup.
    
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
    from scipy.sparse.linalg import spsolve
    from VeraGridEngine.Utils.Symbolic.symbolic import Var, expression2numba, get_expression_vars
    
    # Collect all variables from the block
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
    
    # Add diff vars (derivative variables)
    diff_var_idx = []
    for var in block.diff_vars:
        if var.name not in var_name_to_idx:
            var_name_to_idx[var.name] = len(all_vars)
            all_vars.append(var)
        diff_var_idx.append(var_name_to_idx[var.name])
    
    # Collect all variables that appear in equations (including derivatives)
    all_eqs = block.algebraic_eqs + block.state_eqs
    vars_in_eqs = set()
    for eq in all_eqs:
        vars_in_eqs.update(get_expression_vars(eq))
    
    # Add any missing variables from equations
    for var in vars_in_eqs:
        if var.uid not in [v.uid for v in all_vars]:
            var_name_to_idx[var.name] = len(all_vars)
            all_vars.append(var)
    
    n_vars = len(all_vars)
    n_algebraic = len(block.algebraic_vars)
    n_states = len(block.state_vars)
    n_diff = len(block.diff_vars)
    
    # Determine input variables
    if input_var_names is not None:
        input_vars = [all_vars[var_name_to_idx[name]] for name in input_var_names 
                     if name in var_name_to_idx]
    elif block.in_vars:
        input_vars = block.in_vars
    else:
        # No inputs specified - input_values will not be applied automatically
        input_vars = []
    
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
    
    # Create symbolic names for compilation
    var_sym = {uid: f"vars[{i}]" for uid, i in uid2idx.items()}
    
    # Compile equations
    def compile_equations(eqs, var_sym):
        """Compile equations to a callable function"""
        import uuid
        
        fname = f"rhs_{uuid.uuid4().hex[:8]}"
        src = f"def {fname}(vars):\n"
        src += f"    out = np.zeros({len(eqs)})\n"
        for i, eq in enumerate(eqs):
            src += f"    out[{i}] = {expression2numba(eq, var_sym)}\n"
        src += f"    return out"
        
        namespace = {"np": np, "math": __import__("math")}
        exec(src, namespace)
        return namespace[fname]
    
    # Compile RHS function
    rhs_func = compile_equations(all_eqs, var_sym)
    
    # Compile Jacobian
    def compile_jacobian(eqs, vars_list, uid2idx, var_sym):
        """Compile Jacobian to a callable function"""
        import uuid
        
        triplets = []
        for row, eq in enumerate(eqs):
            for col, var in enumerate(vars_list):
                deriv = eq.diff(var).simplify()
                is_zero = False
                if hasattr(deriv, 'value'):
                    is_zero = deriv.value == 0
                elif hasattr(deriv, 'is_number') and deriv.is_number:
                    is_zero = float(deriv) == 0.0
                
                if not is_zero:
                    triplets.append((row, col, deriv))
        
        if not triplets:
            return None, None
        
        rows, cols, equations = zip(*triplets)
        
        fname = f"jac_{uuid.uuid4().hex[:8]}"
        src = f"def {fname}(vars, out):\n"
        for i, eq in enumerate(equations):
            src += f"    out[{i}] = {expression2numba(eq, var_sym)}\n"
        
        namespace = {"np": np, "math": __import__("math")}
        exec(src, namespace)
        
        # Create sparse structure
        nnz = len(triplets)
        J = sp.lil_matrix((len(eqs), len(vars_list)))
        J.data = np.zeros(nnz)
        
        return namespace[fname], J, rows, cols
    
    jac_result = compile_jacobian(all_eqs, all_vars, uid2idx, var_sym)
    
    if jac_result[0] is not None:
        jac_func, J_struct, jac_rows, jac_cols = jac_result
    else:
        jac_func, J_struct = None, None
    
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
        # Get input at t0
        input_vals_t0 = input_values(t0)
    else:
        input_vals_t0 = input_values
    
    for i, (var, val) in enumerate(zip(input_vars, input_vals_t0)):
        if var.uid in uid2idx:
            x[uid2idx[var.uid]] = val
    
    # Time stepping
    n_steps = int(np.ceil((t_end - t0) / time_step))
    t = np.zeros(n_steps + 1)
    y = np.zeros((n_steps + 1, n_vars))
    
    t[0] = t0
    y[0, :] = x
    
    # Build mapping from diff var to base var and sort by derivative order
    diff_to_base = {}
    for var in block.diff_vars:
        if hasattr(var, 'base_var') and var.base_var is not None:
            diff_to_base[var] = var.base_var
    
    # Sort diff_vars by derivative order (lowest first) to ensure correct computation
    def get_derivative_order(var, order=0):
        if var not in diff_to_base:
            return order
        return get_derivative_order(diff_to_base[var], order + 1)
    
    sorted_diff_vars = sorted(diff_to_base.keys(), key=lambda v: get_derivative_order(v))
    
    # Identify variables to solve for (exclude inputs and diff_vars)
    input_var_set = set(v.uid for v in input_vars)
    solver_vars = [var for var in all_vars 
                   if var.uid not in input_var_set and var not in diff_to_base]
    solver_var_indices = [uid2idx[v.uid] for v in solver_vars]
    
    # Simulation loop with symbolic discretization
    for step in range(n_steps):
        t_step = t[step]
        x_n = y[step, :].copy()
        x_new = x_n.copy()
        
        # Get input values at current time
        if is_callable_input:
            input_vals_step = input_values(t_step + time_step)  # Input at new time
        else:
            input_vals_step = input_values
        
        # Create discretized equations by substituting diff_vars and inputs
        # Backward Euler: diff_var = (base_var - base_var_n) / h
        discretized_eqs = []
        for eq in all_eqs:
            new_eq = eq
            
            # Substitute input variables with their values
            for i, (var, val) in enumerate(zip(input_vars, input_vals_step)):
                if var.uid in uid2idx:
                    new_eq = new_eq.subs({var: Const(val)}).simplify()
            
            # Substitute diff_vars with Backward Euler discretization
            # Process in sorted order (lowest derivative first) for correct substitution
            for diff_var in sorted_diff_vars:
                base_var = diff_to_base[diff_var]
                base_idx = uid2idx[base_var.uid]
                replacement = (base_var - Const(x_n[base_idx])) / Const(time_step)
                new_eq = new_eq.subs({diff_var: replacement}).simplify()
            
            discretized_eqs.append(new_eq)
        
        # Compile discretized equations for this time step
        fname = f"rhs_step_{step}"
        src = f"def {fname}(vars):\n"
        src += f"    out = np.zeros({len(discretized_eqs)})\n"
        for i, eq in enumerate(discretized_eqs):
            src += f"    out[{i}] = {expression2numba(eq, var_sym)}\n"
        src += f"    return out"
        
        namespace = {"np": np, "math": __import__("math")}
        exec(src, namespace)
        disc_rhs_func = namespace[fname]
        
        # Compile Jacobian for discretized equations
        triplets = []
        for row, eq in enumerate(discretized_eqs):
            for col, var in enumerate(all_vars):
                deriv = eq.diff(var).simplify()
                is_zero = False
                if hasattr(deriv, 'value'):
                    is_zero = deriv.value == 0
                elif hasattr(deriv, 'is_number') and deriv.is_number:
                    is_zero = float(deriv) == 0.0
                
                if not is_zero:
                    triplets.append((row, col, deriv))
        
        if triplets:
            rows, cols, equations = zip(*triplets)
            
            fname_jac = f"jac_step_{step}"
            src_jac = f"def {fname_jac}(vars, out):\n"
            for i, eq in enumerate(equations):
                src_jac += f"    out[{i}] = {expression2numba(eq, var_sym)}\n"
            
            exec(src_jac, namespace)
            disc_jac_func = namespace[fname_jac]
            
            # Create dense Jacobian structure  
            jac_nrows = len(discretized_eqs)
            jac_ncols = len(all_vars)
        else:
            disc_jac_func = None
        
        # Newton iteration
        converged = False
        residual_norm = float('inf')
        
        for iteration in range(max_iter):
            # Compute residual
            residual = disc_rhs_func(x_new)
            residual_norm = np.linalg.norm(residual, np.inf)
            
            if residual_norm < tol:
                converged = True
                break
            
            # Compute Jacobian and solve
            if disc_jac_func is not None:
                # Evaluate Jacobian densely
                J_data = np.zeros(len(triplets))
                disc_jac_func(x_new, J_data)
                
                # Build reduced Jacobian for solver variables only
                n_solver = len(solver_vars)
                J_reduced = np.zeros((len(discretized_eqs), n_solver))
                for i, (row, col) in enumerate(zip(rows, cols)):
                    if col in solver_var_indices:
                        solver_col = solver_var_indices.index(col)
                        J_reduced[row, solver_col] = J_data[i]
                
                # Solve linear system for solver variables only
                try:
                    delta_reduced = np.linalg.lstsq(J_reduced, -residual, rcond=None)[0]
                    # Update only solver variables
                    for i, idx in enumerate(solver_var_indices):
                        x_new[idx] += delta_reduced[i]
                except Exception:
                    # Fallback: fixed-point iteration on solver variables only
                    for idx in solver_var_indices:
                        x_new[idx] = x_n[idx] - 0.1 * residual[0] if len(residual) > 0 else x_n[idx]
            else:
                # No Jacobian, use fixed-point on solver variables only
                for idx in solver_var_indices:
                    x_new[idx] = x_n[idx] - 0.1 * residual[0] if len(residual) > 0 else x_n[idx]
        
        # Reset input values to ensure they stay constant
        for i, (var, val) in enumerate(zip(input_vars, input_vals_step)):
            if var.uid in uid2idx:
                x_new[uid2idx[var.uid]] = val
        
        # Compute diff_vars (derivatives) from base_vars in sorted order
        for diff_var in sorted_diff_vars:
            base_var = diff_to_base[diff_var]
            diff_idx = uid2idx[diff_var.uid]
            base_idx = uid2idx[base_var.uid]
            x_new[diff_idx] = (x_new[base_idx] - x_n[base_idx]) / time_step
        
        if converged:
            y[step + 1, :] = x_new
            t[step + 1] = t[step] + time_step
        else:
            if verbose:
                print(f"Warning: Did not converge at step {step}, residual={residual_norm:.2e}")
            y[step + 1, :] = x_new
            t[step + 1] = t[step] + time_step
    
    return t, y, [var.name for var in all_vars]
