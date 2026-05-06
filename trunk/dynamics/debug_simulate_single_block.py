#!/usr/bin/env python
"""
Debug script to test single block simulation

This script tests the simulate_single_block function by creating
simple transfer function blocks and running simulations on them.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

import numpy as np
import matplotlib.pyplot as plt

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.templates_common_functions import simulate_single_block
from VeraGridEngine.Utils.Symbolic.block_helpers import tf_to_block, tf_to_diffblock_with_output
from VeraGridEngine.Utils.Symbolic.symbolic import Var


def test_first_order_system():
    """Test a simple first-order transfer function: G(s) = 1/(s + 1)"""
    print("=" * 70)
    print("Test 1: First-order system G(s) = 1/(s + 1)")
    print("=" * 70)
    
    # Create variable factory
    vf = VarFactory()
    
    # Create input variable (step input)
    u = vf.add_var('input')
    
    # Transfer function: G(s) = 1/(s + 1) -> num=[1], den=[1, 1]
    num = [1.0]
    den = [1.0, 1.0]
    
    # Create block
    block, y = tf_to_block(vf, num, den, u, name='first_order')
    
    print(f"Block created with:")
    print(f"  Algebraic vars: {[v.name for v in block.algebraic_vars]}")
    print(f"  Differential vars: {[v.name for v in block.diff_vars]}")
    print(f"  Equations: {len(block.algebraic_eqs)}")
    
    # Simulate with unit step input
    input_value = 1.0
    
    print(f"\nRunning simulation with input={input_value}...")
    
    try:
        t, y_sol, var_names = simulate_single_block(
            block=block,
            input_values=[input_value],
            t0=0.0,
            t_end=10.0,
            time_step=0.01,
            max_iter=100,
            tol=1e-6,
            init_guess={'input': input_value}
        )
        
        print(f"Simulation completed successfully!")
        print(f"  Time steps: {len(t)}")
        print(f"  Variables: {var_names}")
        
        # Plot results
        plt.figure(figsize=(10, 6))
        
        # Find output variable index
        output_idx = var_names.index('y_first_order') if 'y_first_order' in var_names else -1
        input_idx = var_names.index('input') if 'input' in var_names else -1
        
        if output_idx >= 0:
            plt.plot(t, y_sol[:, output_idx], 'b-', linewidth=2, label='Output y(t)')
        
        if input_idx >= 0:
            plt.plot(t, y_sol[:, input_idx], 'r--', linewidth=1, label='Input u(t)')
        
        # Analytical solution for first-order step response: y(t) = 1 - exp(-t)
        y_analytical = 1.0 - np.exp(-t)
        plt.plot(t, y_analytical, 'g:', linewidth=2, label='Analytical: 1 - exp(-t)')
        
        plt.xlabel('Time (s)')
        plt.ylabel('Amplitude')
        plt.title('First-Order System Step Response')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        
    except Exception as e:
        print(f"Simulation failed with error: {e}")
        import traceback
        traceback.print_exc()


def test_second_order_system():
    """Test a second-order transfer function: G(s) = 1/(s^2 + 2*s + 1)"""
    print("\n" + "=" * 70)
    print("Test 2: Second-order system G(s) = 1/(s^2 + 2*s + 1)")
    print("=" * 70)
    
    # Create variable factory
    vf = VarFactory()
    
    # Create input variable
    u = vf.add_var('input')
    
    # Transfer function: G(s) = 1/(s^2 + 2*s + 1) -> num=[1], den=[1, 2, 1]
    num = [1.0]
    den = [1.0, 2.0, 1.0]
    
    # Create block
    block, y = tf_to_block(vf, num, den, u, name='second_order')
    
    print(f"Block created with:")
    print(f"  Algebraic vars: {[v.name for v in block.algebraic_vars]}")
    print(f"  Differential vars: {[v.name for v in block.diff_vars]}")
    print(f"  Equations: {len(block.algebraic_eqs)}")
    
    # Simulate with unit step input
    input_value = 1.0
    
    print(f"\nRunning simulation with input={input_value}...")
    
    try:
        t, y_sol, var_names = simulate_single_block(
            block=block,
            input_values=[input_value],
            t0=0.0,
            t_end=10.0,
            time_step=0.01,
            max_iter=100,
            tol=1e-6,
            init_guess={'input': input_value}
        )
        
        print(f"Simulation completed successfully!")
        print(f"  Time steps: {len(t)}")
        print(f"  Variables: {var_names}")
        
        # Plot results
        plt.figure(figsize=(10, 6))
        
        # Find output variable index
        output_idx = var_names.index('y_second_order') if 'y_second_order' in var_names else -1
        input_idx = var_names.index('input') if 'input' in var_names else -1
        
        if output_idx >= 0:
            plt.plot(t, y_sol[:, output_idx], 'b-', linewidth=2, label='Output y(t)')
        
        if input_idx >= 0:
            plt.plot(t, y_sol[:, input_idx], 'r--', linewidth=1, label='Input u(t)')
        
        # Analytical solution for critically damped second-order: y(t) = 1 - (1 + t)*exp(-t)
        y_analytical = 1.0 - (1.0 + t) * np.exp(-t)
        plt.plot(t, y_analytical, 'g:', linewidth=2, label='Analytical: 1 - (1+t)*exp(-t)')
        
        plt.xlabel('Time (s)')
        plt.ylabel('Amplitude')
        plt.title('Second-Order System Step Response')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        
    except Exception as e:
        print(f"Simulation failed with error: {e}")
        import traceback
        traceback.print_exc()


def test_pi_controller():
    """Test a PI controller: G(s) = Kp + Ki/s"""
    print("\n" + "=" * 70)
    print("Test 3: PI Controller G(s) = 1 + 10/s")
    print("=" * 70)
    
    # Create variable factory
    vf = VarFactory()
    
    # Create input variable (error signal)
    u = vf.add_var('error')
    
    # PI controller: G(s) = Kp + Ki/s = (Kp*s + Ki)/s
    # For Kp=1, Ki=10: G(s) = (s + 10)/s -> num=[1, 10], den=[1, 0]
    Kp = 1.0
    Ki = 10.0
    # Use a small epsilon to avoid division by zero in the integrator
    # This approximates the integrator as a very slow first-order system
    epsilon = 1e-6
    num = [Kp, Ki]
    den = [1.0, epsilon]  # Approximate integrator
    
    # Create block using standard tf_to_block
    block, y = tf_to_block(vf, num, den, u, name='pi_controller')
    
    print(f"Block created with:")
    print(f"  Algebraic vars: {[v.name for v in block.algebraic_vars]}")
    print(f"  Differential vars: {[v.name for v in block.diff_vars]}")
    print(f"  Equations: {len(block.algebraic_eqs)}")
    
    # Simulate with constant error input (should produce ramp output due to integral action)
    input_value = 0.1
    
    print(f"\nRunning simulation with constant error={input_value}...")
    
    try:
        t, y_sol, var_names = simulate_single_block(
            block=block,
            input_values=[input_value],
            t0=0.0,
            t_end=5.0,
            time_step=0.01,
            max_iter=100,
            tol=1e-6,
            init_guess={'error': input_value}
        )
        
        print(f"Simulation completed successfully!")
        print(f"  Time steps: {len(t)}")
        print(f"  Variables: {var_names}")
        
        # Plot results
        plt.figure(figsize=(10, 6))
        
        # Find output variable index
        output_idx = var_names.index('y_pi_controller') if 'y_pi_controller' in var_names else -1
        input_idx = var_names.index('error') if 'error' in var_names else -1
        
        if output_idx >= 0:
            plt.plot(t, y_sol[:, output_idx], 'b-', linewidth=2, label='Controller Output')
        
        if input_idx >= 0:
            plt.plot(t, y_sol[:, input_idx], 'r--', linewidth=1, label='Error Input')
        
        # Analytical solution for PI with constant error e: y(t) = Kp*e + Ki*e*t
        y_analytical = Kp * input_value + Ki * input_value * t
        plt.plot(t, y_analytical, 'g:', linewidth=2, label=f'Analytical: {Kp}*e + {Ki}*e*t')
        
        plt.xlabel('Time (s)')
        plt.ylabel('Amplitude')
        plt.title('PI Controller Response to Constant Error')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        
    except Exception as e:
        print(f"Simulation failed with error: {e}")
        import traceback
        traceback.print_exc()


def test_variable_input():
    """Test with time-varying input (sinusoid)"""
    print("\n" + "=" * 70)
    print("Test 4: System with Sinusoidal Input")
    print("=" * 70)
    
    # Create variable factory
    vf = VarFactory()
    
    # Create input variable
    u = vf.add_var('input')
    
    # Low-pass filter: G(s) = 1/(s + 1)
    num = [1.0]
    den = [1.0, 1.0]
    
    # Create block
    block, y = tf_to_block(vf, num, den, u, name='lowpass')
    
    # For time-varying input, we need to set up the block differently
    # This is a simplified test with constant input for now
    print("Note: Time-varying input requires additional setup.")
    print("This test uses constant input for demonstration.")
    
    # Simulate with unit step input
    input_value = 1.0
    
    try:
        t, y_sol, var_names = simulate_single_block(
            block=block,
            input_values=[input_value],
            t0=0.0,
            t_end=10.0,
            time_step=0.01,
            max_iter=100,
            tol=1e-6,
            init_guess={'input': input_value}
        )
        
        print(f"Simulation completed successfully!")
        
        # Plot results
        plt.figure(figsize=(10, 6))
        
        output_idx = var_names.index('y_lowpass') if 'y_lowpass' in var_names else -1
        if output_idx >= 0:
            plt.plot(t, y_sol[:, output_idx], 'b-', linewidth=2, label='Filter Output')
            plt.plot(t, y_sol[:, var_names.index('input')], 'r--', linewidth=1, label='Step Input')
        
        plt.xlabel('Time (s)')
        plt.ylabel('Amplitude')
        plt.title('Low-Pass Filter Step Response')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        
    except Exception as e:
        print(f"Simulation failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Single Block Simulation Test Suite")
    print("=" * 70)
    print()
    
    # Run all tests
    test_first_order_system()
    test_second_order_system()
    test_pi_controller()
    test_variable_input()
    
    print("\n" + "=" * 70)
    print("All tests completed!")
    print("=" * 70)
