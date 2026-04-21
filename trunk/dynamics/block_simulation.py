# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Simple block simulation using basic building blocks.

This module provides a clean implementation for simulating dynamic systems
using basic blocks like gain, integrator, adder, etc. from predefined_blocks.py
"""

from __future__ import annotations

import numpy as np
from typing import Callable, List, Tuple, Optional, Dict

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Templates.predefined_blocks import (
    gain, adder, substract, integrator, constant
)


def simulate_single_block(
    block: Block,
    input_func: Callable[[float], float] | float,
    t0: float = 0.0,
    t_end: float = 10.0,
    dt: float = 0.01,
    init_values: Optional[Dict[str, float]] = None,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Simulate a single block using Forward Euler integration.
    
    This function simulates a block composed of basic building blocks
    (gain, integrator, adder, etc.) using simple Forward Euler integration.
    
    Parameters
    ----------
    block : Block
        The block to simulate (composed of basic blocks)
    input_func : callable or float
        Input function u(t) that returns the input at time t,
        or a constant float value
    t0 : float
        Initial time (default 0.0)
    t_end : float
        End time (default 10.0)
    dt : float
        Time step (default 0.01)
    init_values : dict, optional
        Initial values for state variables {var_name: value}
    
    Returns
    -------
    tuple : (time_array, solution_array, variable_names)
        - time_array: 1D array of time points
        - solution_array: 2D array of shape (n_steps, n_variables)
        - variable_names: List of variable names
    """
    
    # Handle constant input
    if not callable(input_func):
        const_val = float(input_func)
        input_func = lambda t: const_val
    
    # Create time array
    n_steps = int((t_end - t0) / dt) + 1
    t = np.linspace(t0, t_end, n_steps)
    
    # Collect all variables from the block
    all_vars = []
    var_name_to_idx = {}
    
    # Add algebraic variables
    for var in block.algebraic_vars:
        if var.name not in var_name_to_idx:
            var_name_to_idx[var.name] = len(all_vars)
            all_vars.append(var)
    
    # Add state variables
    for var in block.state_vars:
        if var.name not in var_name_to_idx:
            var_name_to_idx[var.name] = len(all_vars)
            all_vars.append(var)
    
    # Add input variables
    for var in block.in_vars:
        if var.name not in var_name_to_idx:
            var_name_to_idx[var.name] = len(all_vars)
            all_vars.append(var)
    
    n_vars = len(all_vars)
    
    # Initialize solution array
    y = np.zeros((n_steps, n_vars))
    
    # Set initial values
    if init_values:
        for name, val in init_values.items():
            if name in var_name_to_idx:
                y[0, var_name_to_idx[name]] = val
    
    # Set block's init_values
    for var, const in block.init_values.items():
        if var.name in var_name_to_idx:
            y[0, var_name_to_idx[var.name]] = const.value
    
    # Simulation loop using Forward Euler
    for i in range(n_steps - 1):
        # Current time and state
        t_curr = t[i]
        x_curr = y[i, :].copy()
        
        # Get input at current time
        u_val = input_func(t_curr)
        for var in block.in_vars:
            if var.name in var_name_to_idx:
                x_curr[var_name_to_idx[var.name]] = u_val
        
        # Compute derivatives for state variables
        # For each state variable, evaluate its state equation
        dx_dt = np.zeros(n_vars)
        
        for j, (state_var, state_eq) in enumerate(zip(block.state_vars, block.state_eqs)):
            # The state equation gives dx/dt directly
            # We need to evaluate it by substituting current values
            
            # Simple evaluation: substitute variables in the expression
            expr_val = _eval_expr(state_eq, x_curr, var_name_to_idx, all_vars)
            if state_var.name in var_name_to_idx:
                dx_dt[var_name_to_idx[state_var.name]] = expr_val
        
        # Update state variables using Forward Euler: x_{n+1} = x_n + dt * dx/dt
        y[i + 1, :] = x_curr + dt * dx_dt
        
        # Solve algebraic equations at the new time step
        # For simple blocks, algebraic equations are of form: y - expr = 0
        # We solve for y given the current inputs and states
        
        # Multiple iterations for convergence (in case of coupled algebraic eqs)
        for _ in range(10):
            x_new = y[i + 1, :].copy()
            max_change = 0.0
            
            for eq in block.algebraic_eqs:
                # Evaluate the equation: result = 0 when satisfied
                # For y - expr = 0, we have y = expr
                # We update y directly
                
                residual = _eval_expr(eq, x_new, var_name_to_idx, all_vars)
                
                # Find which variable this equation is for
                # For y - expr, the variable is the algebraic variable
                vars_in_eq = eq.get_vars()
                for var in vars_in_eq:
                    if var in block.algebraic_vars:
                        # Update this variable
                        if var.name in var_name_to_idx:
                            idx = var_name_to_idx[var.name]
                            # Simple update: y_new = y_old - residual
                            # This works for equations of form y - expr = 0
                            old_val = x_new[idx]
                            new_val = old_val - residual
                            x_new[idx] = new_val
                            max_change = max(max_change, abs(new_val - old_val))
            
            y[i + 1, :] = x_new
            
            if max_change < 1e-10:
                break
    
    return t, y, [var.name for var in all_vars]


def _eval_expr(expr, x_curr, var_name_to_idx, all_vars):
    """
    Evaluate an expression given current variable values.
    
    This is a simple evaluator that substitutes variable values into expressions.
    """
    # Get the expression as a lambda function
    from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
    
    # Create a simple substitution dictionary
    subs = {}
    vars_in_expr = expr.get_vars()
    
    for var in vars_in_expr:
        if isinstance(var, Var) and var.name in var_name_to_idx:
            subs[var] = Const(x_curr[var_name_to_idx[var.name]])
    
    # Substitute and evaluate
    result = expr.subs(subs)
    
    if isinstance(result, Const):
        return result.value
    elif isinstance(result, (int, float)):
        return float(result)
    else:
        # Try to get numeric value
        try:
            return float(result)
        except:
            return 0.0


def create_first_order_block(vf: VarFactory, K: float = 1.0, tau: float = 1.0, name: str = "first_order") -> Tuple[Block, Var]:
    """
    Create a first-order transfer function block: G(s) = K / (tau*s + 1)
    
    Using basic blocks: gain -> integrator -> gain -> adder
    
    Parameters
    ----------
    vf : VarFactory
        Variable factory
    K : float
        Gain (default 1.0)
    tau : float
        Time constant (default 1.0)
    name : str
        Block name
    
    Returns
    -------
    tuple : (block, output_var)
        The assembled block and its output variable
    """
    # Input variable
    u = vf.add_var(f"u_{name}")
    
    # State variable (integrator output)
    x = vf.add_var(f"x_{name}")
    
    # Output variable
    y = vf.add_var(f"y_{name}")
    
    # First-order system: tau * dx/dt + x = K * u
    # Rearranged: dx/dt = (K*u - x) / tau
    
    # We need: dx/dt = (K*u - x) / tau
    # Use: subtract(K*u, x) -> divide by tau -> integrate
    
    # But let's do it more directly with state equations
    # State equation: dx/dt = (K*u - x) / tau
    
    K_const = vf.add_const(K)
    tau_const = vf.add_const(tau)
    
    # dx/dt = (K*u - x) / tau
    from VeraGridEngine.Utils.Symbolic.symbolic import Const
    state_eq = (K_const * u - x) / tau_const
    
    # Output equation: y = x
    output_eq = y - x
    
    block = Block(
        name=name,
        state_vars=[x],
        state_eqs=[state_eq],
        algebraic_vars=[y],
        algebraic_eqs=[output_eq],
        in_vars=[u],
        out_vars=[y]
    )
    
    return block, y


def create_integrator_block(vf: VarFactory, K: float = 1.0, name: str = "integrator") -> Tuple[Block, Var]:
    """
    Create an integrator block: G(s) = K / s
    
    Using the basic integrator block.
    
    Parameters
    ----------
    vf : VarFactory
        Variable factory
    K : float
        Integrator gain (default 1.0)
    name : str
        Block name
    
    Returns
    -------
    tuple : (block, output_var)
        The assembled block and its output variable
    """
    # Input variable
    u = vf.add_var(f"u_{name}")
    
    # Create state variable
    x = vf.add_var(f"x_{name}")
    
    # Output variable  
    y = vf.add_var(f"y_{name}")
    
    # Integrator: dx/dt = K * u
    K_const = vf.add_const(K)
    state_eq = K_const * u
    
    # Output: y = x
    output_eq = y - x
    
    block = Block(
        name=name,
        state_vars=[x],
        state_eqs=[state_eq],
        algebraic_vars=[y],
        algebraic_eqs=[output_eq],
        in_vars=[u],
        out_vars=[y]
    )
    
    return block, y


def create_gain_block(vf: VarFactory, K: float = 1.0, name: str = "gain") -> Tuple[Block, Var]:
    """
    Create a gain block: G(s) = K
    
    Pure algebraic block.
    
    Parameters
    ----------
    vf : VarFactory
        Variable factory
    K : float
        Gain (default 1.0)
    name : str
        Block name
    
    Returns
    -------
    tuple : (block, output_var)
        The assembled block and its output variable
    """
    # Input and output variables
    u = vf.add_var(f"u_{name}")
    y = vf.add_var(f"y_{name}")
    
    # Gain: y = K * u
    K_const = vf.add_const(K)
    from VeraGridEngine.Utils.Symbolic.symbolic import Const
    output_eq = y - K_const * u
    
    block = Block(
        name=name,
        algebraic_vars=[y],
        algebraic_eqs=[output_eq],
        in_vars=[u],
        out_vars=[y]
    )
    
    return block, y
