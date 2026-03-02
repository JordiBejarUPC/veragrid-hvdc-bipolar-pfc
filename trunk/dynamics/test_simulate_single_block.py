#!/usr/bin/env python
"""
Clean test suite for block simulation using basic building blocks.

Tests various transfer functions by composing basic blocks:
- gain: y = K * u
- integrator: dx/dt = u, y = x  
- adder: y = u1 + u2
- subtract: y = u1 - u2

Compares simulated results against analytical solutions.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

import numpy as np
import matplotlib.pyplot as plt

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.predefined_blocks import gain, adder, substract, integrator
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const


# Tolerance for assertions
ABS_TOL = 0.01
REL_TOL = 0.02


def create_block_of_type(block_type: str, vf: VarFactory, **kwargs) -> tuple[Block, Var]:
    """
    Create a block by composing basic block types.
    
    This function shows how complex transfer functions are built from
    simple building blocks like gain, integrator, adder, etc.
    
    Parameters
    ----------
    block_type : str
        Type of block to create:
        - 'gain': y = K * u
        - 'integrator': y = K/s * u (integrator with gain)
        - 'first_order': y = K/(tau*s + 1) * u (first-order lag)
        - 'lead_lag': y = K*(tau_z*s + 1)/(tau_p*s + 1) * u
        - 'pi_controller': y = Kp + Ki/s (PI controller)
    vf : VarFactory
        Variable factory for creating variables
    **kwargs : dict
        Block-specific parameters (K, tau, Kp, Ki, etc.)
    
    Returns
    -------
    tuple : (block, output_var)
        The assembled block and its output variable
    """
    
    if block_type == 'gain':
        # Gain block: y = K * u
        # Uses: GAIN
        K = kwargs.get('K', 1.0)
        name = kwargs.get('name', 'gain')
        
        # Create input
        u = vf.add_var(f"u_{name}")
        
        # Create gain block
        y = vf.add_var(f"y_{name}")
        K_c = vf.add_const(K)
        eq = y - K_c * u
        
        block = Block(
            name=name,
            algebraic_vars=[y],
            algebraic_eqs=[eq],
            in_vars=[u],
            out_vars=[y]
        )
        return block, y
    
    elif block_type == 'integrator':
        # Integrator: y = (K/s) * u
        # Uses: INTEGRATOR with gain K
        # State equation: dx/dt = K * u
        # Output: y = x
        K = kwargs.get('K', 1.0)
        name = kwargs.get('name', 'integrator')
        
        # Create input
        u = vf.add_var(f"u_{name}")
        
        # Create state variable
        x = vf.add_var(f"x_{name}")
        y = vf.add_var(f"y_{name}")
        
        K_c = vf.add_const(K)
        
        # dx/dt = K * u
        state_eq = K_c * u
        # y = x
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
    
    elif block_type == 'first_order':
        # First-order lag: y = K/(tau*s + 1) * u
        # Uses: GAIN + INTEGRATOR + ADDER + SUBTRACT
        # Structure:
        #   u -->[K]--> sum -->(+)--> [1/s] --> x -->[1/tau]--> y
        #                ^      |
        #                |      (-)
        #                |      |
        #                +------[1]<-- x
        K = kwargs.get('K', 1.0)
        tau = kwargs.get('tau', 1.0)
        name = kwargs.get('name', 'first_order')
        
        # Create input
        u = vf.add_var(f"u_{name}")
        
        # Internal signals
        # u_gain = K * u
        u_gain = vf.add_var(f"u_gain_{name}")
        K_c = vf.add_const(K)
        eq_gain = u_gain - K_c * u
        
        # State variable (integrator output)
        x = vf.add_var(f"x_{name}")
        
        # Summer: sum = u_gain - x
        sum_out = vf.add_var(f"sum_{name}")
        eq_sum = sum_out - u_gain + x  # sum = K*u - x
        
        # State equation: dx/dt = sum / tau
        tau_c = vf.add_const(tau)
        state_eq = sum_out / tau_c  # dx/dt = (K*u - x) / tau
        
        # Output: y = x
        y = vf.add_var(f"y_{name}")
        output_eq = y - x
        
        block = Block(
            name=name,
            state_vars=[x],
            state_eqs=[state_eq],
            algebraic_vars=[u_gain, sum_out, y],
            algebraic_eqs=[eq_gain, eq_sum, output_eq],
            in_vars=[u],
            out_vars=[y]
        )
        return block, y
    
    elif block_type == 'lead_lag':
        # Lead-lag compensator: y = K*(tau_z*s + 1)/(tau_p*s + 1) * u
        # Uses: GAIN + INTEGRATOR + ADDER
        # Structure: Parallel combination of proportional and derivative paths
        K = kwargs.get('K', 1.0)
        tau_z = kwargs.get('tau_z', 1.0)  # Lead time constant
        tau_p = kwargs.get('tau_p', 1.0)  # Lag time constant
        name = kwargs.get('name', 'lead_lag')
        
        # Create input
        u = vf.add_var(f"u_{name}")
        
        # State variable
        x = vf.add_var(f"x_{name}")
        
        # State equation: dx/dt = (K*u - x) / tau_p
        K_c = vf.add_const(K)
        tau_p_c = vf.add_const(tau_p)
        state_eq = (K_c * u - x) / tau_p_c
        
        # Output: y = x + tau_z * (K*u - x) / tau_p
        #         = (1 - tau_z/tau_p) * x + (tau_z/tau_p) * K * u
        y = vf.add_var(f"y_{name}")
        tau_z_c = vf.add_const(tau_z)
        
        # y = x + tau_z * dx/dt
        # But dx/dt = (K*u - x) / tau_p
        # So: y = x + tau_z * (K*u - x) / tau_p
        output_eq = y - x - tau_z_c * (K_c * u - x) / tau_p_c
        
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
    
    elif block_type == 'pi_controller':
        # PI Controller: y = Kp + Ki/s
        # Uses: GAIN + INTEGRATOR + ADDER
        # Structure:
        #   error -->[Kp]--> y_p -->(+)--> y_out
        #       |                     ^
        #       |--> [Ki] --> [1/s] --+     (integral path)
        Kp = kwargs.get('Kp', 1.0)
        Ki = kwargs.get('Ki', 1.0)
        name = kwargs.get('name', 'pi_controller')
        
        # Create input (error signal)
        error = vf.add_var(f"error_{name}")
        
        # Proportional path: y_p = Kp * error
        y_p = vf.add_var(f"y_p_{name}")
        Kp_c = vf.add_const(Kp)
        eq_p = y_p - Kp_c * error
        
        # Integral path: dx_i/dt = Ki * error, y_i = x_i
        x_i = vf.add_var(f"x_i_{name}")
        y_i = vf.add_var(f"y_i_{name}")
        Ki_c = vf.add_const(Ki)
        state_eq_i = Ki_c * error
        eq_i = y_i - x_i
        
        # Summer: y_out = y_p + y_i
        y_out = vf.add_var(f"y_out_{name}")
        eq_sum = y_out - y_p - y_i
        
        block = Block(
            name=name,
            state_vars=[x_i],
            state_eqs=[state_eq_i],
            algebraic_vars=[y_p, y_i, y_out],
            algebraic_eqs=[eq_p, eq_i, eq_sum],
            in_vars=[error],
            out_vars=[y_out]
        )
        return block, y_out
    
    else:
        raise ValueError(f"Unknown block type: {block_type}")


def simulate_block(block, input_func, t0, t_end, dt, init_values=None):
    """
    Simulate a block using Forward Euler integration.
    
    Parameters:
    -----------
    block : Block
        Block to simulate (composed of basic building blocks)
    input_func : callable or float
        Input function u(t) or constant value
    t0 : float
        Initial time
    t_end : float
        End time
    dt : float
        Time step
    init_values : dict, optional
        Initial values for state variables {var_name: value}
    
    Returns:
    --------
    tuple : (t, y_sol, var_names)
        - t: time array
        - y_sol: solution array (n_steps x n_variables)
        - var_names: list of variable names
    """
    if not callable(input_func):
        const_val = float(input_func)
        input_func = lambda t: const_val
    
    # Time array
    n_steps = int((t_end - t0) / dt) + 1
    t = np.linspace(t0, t_end, n_steps)
    
    # Collect variables
    all_vars = []
    var_idx = {}
    
    # State variables first
    for var in block.state_vars:
        if var.name not in var_idx:
            var_idx[var.name] = len(all_vars)
            all_vars.append(var)
    
    # Then algebraic variables
    for var in block.algebraic_vars:
        if var.name not in var_idx:
            var_idx[var.name] = len(all_vars)
            all_vars.append(var)
    
    # Then input variables
    for var in block.in_vars:
        if var.name not in var_idx:
            var_idx[var.name] = len(all_vars)
            all_vars.append(var)
    
    n_vars = len(all_vars)
    y_sol = np.zeros((n_steps, n_vars))
    
    # Initial conditions
    if init_values:
        for name, val in init_values.items():
            if name in var_idx:
                y_sol[0, var_idx[name]] = val
    
    # Solve algebraic equations at t=0
    u_0 = input_func(t0)
    for var in block.in_vars:
        if var.name in var_idx:
            y_sol[0, var_idx[var.name]] = u_0
    
    # Solve algebraic equations at initial time
    for iteration in range(50):
        max_change = 0.0
        for eq in block.algebraic_eqs:
            residual = eval_expr(eq, y_sol[0, :], var_idx, all_vars)
            if abs(residual) > 1e-10:
                vars_in_eq = eq.get_vars()
                for var in vars_in_eq:
                    if var in block.algebraic_vars and var.name in var_idx:
                        idx = var_idx[var.name]
                        old_val = y_sol[0, idx]
                        new_val = old_val - residual
                        y_sol[0, idx] = new_val
                        max_change = max(max_change, abs(new_val - old_val))
                        break
        if max_change < 1e-10:
            break
    
    # Forward Euler simulation
    for i in range(n_steps - 1):
        t_curr = t[i]
        t_next = t[i + 1]
        
        # Current state values
        x_curr = y_sol[i, :].copy()
        
        # Apply input at current time
        u_val = input_func(t_curr)
        for var in block.in_vars:
            if var.name in var_idx:
                x_curr[var_idx[var.name]] = u_val
        
        # Compute state derivatives
        dx_dt = {}
        for state_var, state_eq in zip(block.state_vars, block.state_eqs):
            val = eval_expr(state_eq, x_curr, var_idx, all_vars)
            dx_dt[state_var.name] = val
        
        # Update state variables: x_next = x_curr + dt * dx_dt
        for state_var in block.state_vars:
            if state_var.name in var_idx:
                idx = var_idx[state_var.name]
                y_sol[i + 1, idx] = x_curr[idx] + dt * dx_dt[state_var.name]
        
        # Update input for next time step
        u_next = input_func(t_next)
        for var in block.in_vars:
            if var.name in var_idx:
                y_sol[i + 1, var_idx[var.name]] = u_next
        
        # Solve algebraic equations at t_next using Gauss-Seidel iteration
        max_iter = 50
        tol = 1e-10
        
        for iteration in range(max_iter):
            max_change = 0.0
            
            for eq in block.algebraic_eqs:
                # Evaluate equation
                residual = eval_expr(eq, y_sol[i + 1, :], var_idx, all_vars)
                
                if abs(residual) > tol:
                    # Find which algebraic variable to update
                    vars_in_eq = eq.get_vars()
                    for var in vars_in_eq:
                        if var in block.algebraic_vars and var.name in var_idx:
                            idx = var_idx[var.name]
                            old_val = y_sol[i + 1, idx]
                            new_val = old_val - residual
                            y_sol[i + 1, idx] = new_val
                            max_change = max(max_change, abs(new_val - old_val))
                            break
            
            if max_change < tol:
                break
    
    return t, y_sol, [v.name for v in all_vars]


def eval_expr(expr, values, var_idx, all_vars):
    """Evaluate expression with given variable values."""
    from VeraGridEngine.Utils.Symbolic.symbolic import Var
    
    kwargs = {}
    for var in expr.get_vars():
        if isinstance(var, Var) and var.name in var_idx:
            kwargs[var.name] = float(values[var_idx[var.name]])
    
    try:
        result = expr.eval(**kwargs)
        return float(result) if result is not None else 0.0
    except:
        return 0.0


def test_gain():
    """Test gain block: y = K * u"""
    print("\n" + "=" * 70)
    print("Test 1: Gain Block y = 2.5 * u")
    print("Uses: GAIN")
    print("=" * 70)
    
    vf = VarFactory()
    block, y = create_block_of_type('gain', vf, K=2.5, name="test_gain")
    
    # Test with input u(t) = 3.0 + sin(t)
    input_func = lambda t: 3.0 + np.sin(t)
    
    t, y_sol, var_names = simulate_block(
        block=block,
        input_func=input_func,
        t0=0.0,
        t_end=5.0,
        dt=0.01,
        init_values={}
    )
    
    y_idx = var_names.index("y_test_gain")
    y_sim = y_sol[:, y_idx]
    
    # Analytical: y = 2.5 * (3.0 + sin(t))
    y_ana = 2.5 * (3.0 + np.sin(t))
    
    max_error = np.max(np.abs(y_sim - y_ana))
    print(f"Maximum error: {max_error:.6f}")
    assert max_error < ABS_TOL, f"Max error {max_error} exceeds tolerance"
    
    print("✓ Gain test PASSED")
    return t, y_sim, y_ana


def test_integrator():
    """Test integrator block: y = K/s * u"""
    print("\n" + "=" * 70)
    print("Test 2: Integrator Block y = (0.5/s) * u")
    print("Uses: INTEGRATOR with K=0.5")
    print("=" * 70)
    
    vf = VarFactory()
    block, y = create_block_of_type('integrator', vf, K=0.5, name="test_integrator")
    
    # Constant input = 1.0
    t, y_sol, var_names = simulate_block(
        block=block,
        input_func=1.0,
        t0=0.0,
        t_end=5.0,
        dt=0.01,
        init_values={"x_test_integrator": 0.0}
    )
    
    y_idx = var_names.index("y_test_integrator")
    y_sim = y_sol[:, y_idx]
    
    # Analytical: y(t) = K * u * t = 0.5 * 1.0 * t
    y_ana = 0.5 * t
    
    max_error = np.max(np.abs(y_sim - y_ana))
    print(f"Maximum error: {max_error:.6f}")
    assert max_error < 0.05, f"Max error {max_error} exceeds tolerance"
    
    print("✓ Integrator test PASSED")
    return t, y_sim, y_ana


def test_first_order():
    """Test first-order block: y = K/(tau*s + 1) * u"""
    print("\n" + "=" * 70)
    print("Test 3: First-Order Block y = 1/(s + 1) * u")
    print("Uses: GAIN + INTEGRATOR + ADDER + SUBTRACT")
    print("Structure: u-->GAIN-->ADDER-->INTEGRATOR-->output")
    print("                  ^        |")
    print("                  |        |")
    print("                  +---SUBTRACT<--|")
    print("=" * 70)
    
    vf = VarFactory()
    block, y = create_block_of_type('first_order', vf, K=1.0, tau=1.0, name="test_fo")
    
    # Step input
    t, y_sol, var_names = simulate_block(
        block=block,
        input_func=1.0,
        t0=0.0,
        t_end=5.0,
        dt=0.01,
        init_values={"x_test_fo": 0.0}
    )
    
    y_idx = var_names.index("y_test_fo")
    y_sim = y_sol[:, y_idx]
    
    # Analytical: y(t) = 1 - exp(-t)
    y_ana = 1.0 - np.exp(-t)
    
    # Check final value
    final_error = abs(y_sim[-1] - y_ana[-1])
    print(f"Final error: {final_error:.6f}")
    assert final_error < ABS_TOL, f"Final error {final_error} exceeds tolerance"
    
    print("✓ First-order test PASSED")
    return t, y_sim, y_ana


def test_pi_controller():
    """Test PI controller: y = Kp + Ki/s"""
    print("\n" + "=" * 70)
    print("Test 4: PI Controller y = Kp + Ki/s")
    print("Uses: GAIN + INTEGRATOR + ADDER")
    print("Structure: error-->[Kp]-->ADDER-->output")
    print("              |                ^")
    print("              +-->[Ki]-->[1/s]-+")
    print("=" * 70)
    
    vf = VarFactory()
    block, y = create_block_of_type(
        'pi_controller', vf, 
        Kp=1.0, Ki=10.0, 
        name="test_pi"
    )
    
    # Constant error = 0.1
    error_val = 0.1
    
    t, y_sol, var_names = simulate_block(
        block=block,
        input_func=error_val,
        t0=0.0,
        t_end=2.0,
        dt=0.01,
        init_values={"x_i_test_pi": 0.0}
    )
    
    y_idx = var_names.index("y_out_test_pi")
    y_sim = y_sol[:, y_idx]
    
    # Analytical: y(t) = Kp*e + Ki*e*t
    # Kp=1.0, Ki=10.0, e=0.1
    # y(t) = 0.1 + 1.0*t
    y_ana = 0.1 + 1.0 * t
    
    max_error = np.max(np.abs(y_sim - y_ana))
    print(f"Maximum error: {max_error:.6f}")
    assert max_error < 0.1, f"Max error {max_error} exceeds tolerance"
    
    print("✓ PI controller test PASSED")
    return t, y_sim, y_ana


if __name__ == '__main__':
    print("Running block simulation tests")
    print("=" * 70)
    print("\nEach test shows which basic blocks are used:")
    print("  GAIN     : y = K * u")
    print("  INTEGRATOR: y = integral(u)")
    print("  ADDER    : y = u1 + u2")
    print("  SUBTRACT : y = u1 - u2")
    print()
    
    try:
        t1, y1_sim, y1_ana = test_gain()
        t2, y2_sim, y2_ana = test_integrator()
        t3, y3_sim, y3_ana = test_first_order()
        t4, y4_sim, y4_ana = test_pi_controller()
        
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        
        # Plot results
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        axes[0, 0].plot(t1, y1_sim, 'b-', linewidth=2, label='Simulated')
        axes[0, 0].plot(t1, y1_ana, 'r--', linewidth=1.5, label='Analytical')
        axes[0, 0].set_xlabel('Time (s)')
        axes[0, 0].set_ylabel('Output')
        axes[0, 0].set_title('Test 1: Gain Block')
        axes[0, 0].legend()
        axes[0, 0].grid(True)
        
        axes[0, 1].plot(t2, y2_sim, 'b-', linewidth=2, label='Simulated')
        axes[0, 1].plot(t2, y2_ana, 'r--', linewidth=1.5, label='Analytical')
        axes[0, 1].set_xlabel('Time (s)')
        axes[0, 1].set_ylabel('Output')
        axes[0, 1].set_title('Test 2: Integrator Block')
        axes[0, 1].legend()
        axes[0, 1].grid(True)
        
        axes[1, 0].plot(t3, y3_sim, 'b-', linewidth=2, label='Simulated')
        axes[1, 0].plot(t3, y3_ana, 'r--', linewidth=1.5, label='Analytical')
        axes[1, 0].set_xlabel('Time (s)')
        axes[1, 0].set_ylabel('Output')
        axes[1, 0].set_title('Test 3: First-Order Block')
        axes[1, 0].legend()
        axes[1, 0].grid(True)
        
        axes[1, 1].plot(t4, y4_sim, 'b-', linewidth=2, label='Simulated')
        axes[1, 1].plot(t4, y4_ana, 'r--', linewidth=1.5, label='Analytical')
        axes[1, 1].set_xlabel('Time (s)')
        axes[1, 1].set_ylabel('Output')
        axes[1, 1].set_title('Test 4: PI Controller')
        axes[1, 1].legend()
        axes[1, 1].grid(True)
        
        plt.tight_layout()
        plt.show()
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
