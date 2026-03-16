# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Validation script for VSC AC-to-AC Converter Model

This script validates the VSC AC2AC RMS model with equations (18.9), (18.10), (18.11):

From (18.9) - AC power with transformer admittance gT + jbT = 1/(rT + jxT):
- pac = gT*vac^2 - sqrt(3/8)*am*vdc*vac*gT*cos(theta_ac - alpha) 
        - sqrt(3/8)*am*vdc*vac*bT*sin(theta_ac - alpha)
- qac = -bT*vac^2 + sqrt(3/8)*am*vdc*vac*bT*cos(theta_ac - alpha) 
        - sqrt(3/8)*am*vdc*vac*gT*sin(theta_ac - alpha)

From (18.10) - DC/AC power balance:
- 0 = gT*(sqrt(3/8)*am*vdc)^2 - sqrt(3/8)*am*vdc*vac*gT*cos(theta_ac - alpha) 
      + sqrt(3/8)*am*vdc*vac*bT*sin(theta_ac - alpha)

From (18.11) - AC current constraints:
- 0 = pac^2 + qac^2 - vac*iac
- 0 = pac*sin(theta_ac - phi_ac) - qac*cos(theta_ac - phi_ac)
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

import numpy as np
from matplotlib import pyplot as plt

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy
from VeraGridEngine.enumerations import (VarPowerFlowRefferenceType, 
                                        DynamicIntegrationMethod, 
                                        RmsInitializationMethod,
                                        ConverterControlType)
import VeraGridEngine.api as gce

# Import the VSC AC2AC model
from VeraGridEngine.Templates.Rms.vsc_ac2ac import VscAc2acModel


def find_name_in_block(name: str, block: Block):
    """Recursively find a variable by name in the block and all its children."""
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var
    
    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res
    
    return None


def validate_equations(results, tolerance=1e-6):
    """
    Validate that the VSC AC2AC equations (18.9, 18.10, 18.11) are satisfied.
    """
    print("\n" + "="*60)
    print("VALIDATING VSC AC2AC MODEL EQUATIONS")
    print("="*60)
    
    errors = []
    
    # Extract variables from results
    pac = results['pac']
    qac = results['qac']
    vac = results['vac']
    vdc = results['vdc']
    theta_ac = results['theta_ac']
    phi_ac = results['phi_ac']
    alpha = results['alpha']
    am = results['am']
    iac = results['iac']
    
    # Get transformer parameters (from model parameters)
    rT = 0.01  # Transformer resistance (pu)
    xT = 0.1   # Transformer reactance (pu)
    
    # Calculate transformer admittance: gT + jbT = 1/(rT + jxT)
    gT = rT / (rT**2 + xT**2)
    bT = -xT / (rT**2 + xT**2)
    
    sqrt_38 = np.sqrt(3.0 / 8.0)
    
    # Eq from (18.9a) - pac calculation
    pac_calc = gT * vac**2 - sqrt_38 * am * vdc * vac * gT * np.cos(theta_ac - alpha) \
               - sqrt_38 * am * vdc * vac * bT * np.sin(theta_ac - alpha)
    eq_pac_error = np.abs(pac - pac_calc)
    eq_pac_max = np.max(eq_pac_error)
    print(f"\nEq (18.9a) - pac calculation:")
    print(f"  Max error: {eq_pac_max:.2e}")
    print(f"  Status: {'PASS' if eq_pac_max < tolerance else 'FAIL'}")
    if eq_pac_max >= tolerance:
        errors.append(f"pac equation failed with max error {eq_pac_max:.2e}")
    
    # Eq from (18.9b) - qac calculation
    qac_calc = -bT * vac**2 + sqrt_38 * am * vdc * vac * bT * np.cos(theta_ac - alpha) \
               - sqrt_38 * am * vdc * vac * gT * np.sin(theta_ac - alpha)
    eq_qac_error = np.abs(qac - qac_calc)
    eq_qac_max = np.max(eq_qac_error)
    print(f"\nEq (18.9b) - qac calculation:")
    print(f"  Max error: {eq_qac_max:.2e}")
    print(f"  Status: {'PASS' if eq_qac_max < tolerance else 'FAIL'}")
    if eq_qac_max >= tolerance:
        errors.append(f"qac equation failed with max error {eq_qac_max:.2e}")
    
    # Eq from (18.10) - DC/AC power balance
    eq10_calc = gT * (sqrt_38 * am * vdc)**2 - sqrt_38 * am * vdc * vac * gT * np.cos(theta_ac - alpha) \
                + sqrt_38 * am * vdc * vac * bT * np.sin(theta_ac - alpha)
    eq10_error = np.abs(eq10_calc)
    eq10_max = np.max(eq10_error)
    print(f"\nEq (18.10) - DC/AC power balance:")
    print(f"  Max error: {eq10_max:.2e}")
    print(f"  Status: {'PASS' if eq10_max < tolerance else 'FAIL'}")
    if eq10_max >= tolerance:
        errors.append(f"DC/AC power balance equation failed with max error {eq10_max:.2e}")
    
    # Eq from (18.11a) - AC current magnitude constraint
    eq11a_error = np.abs(pac**2 + qac**2 - vac * iac)
    eq11a_max = np.max(eq11a_error)
    print(f"\nEq (18.11a) - AC current magnitude:")
    print(f"  Max error: {eq11a_max:.2e}")
    print(f"  Status: {'PASS' if eq11a_max < tolerance else 'FAIL'}")
    if eq11a_max >= tolerance:
        errors.append(f"AC current magnitude equation failed with max error {eq11a_max:.2e}")
    
    # Eq from (18.11b) - AC current angle constraint
    eq11b_error = np.abs(pac * np.sin(theta_ac - phi_ac) - qac * np.cos(theta_ac - phi_ac))
    eq11b_max = np.max(eq11b_error)
    print(f"\nEq (18.11b) - AC current angle:")
    print(f"  Max error: {eq11b_max:.2e}")
    print(f"  Status: {'PASS' if eq11b_max < tolerance else 'FAIL'}")
    if eq11b_max >= tolerance:
        errors.append(f"AC current angle equation failed with max error {eq11b_max:.2e}")
    
    print("\n" + "="*60)
    if errors:
        print(f"VALIDATION FAILED: {len(errors)} equation(s) not satisfied")
        for error in errors:
            print(f"  - {error}")
    else:
        print("VALIDATION PASSED: All equations satisfied within tolerance")
    print("="*60 + "\n")
    
    return len(errors) == 0


def create_test_grid():
    """Create a simple test grid with VSC for validation."""
    grid = gce.MultiCircuit(Sbase=100, fbase=50.0)
    
    # Buses
    bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10)
    bus2 = gce.Bus(name="Bus2", Vnom=10)
    bus_dc = gce.Bus(name="BusDC", Vnom=10, is_dc=True)
    
    grid.add_bus(bus0)
    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus_dc)
    
    # Initialize bus RMS models
    for bus in grid.buses:
        initialize_bus_rms(bus, vf=grid.rms_var_factory)
    
    # Lines
    line0 = gce.Line(name="line 0-1", bus_from=bus0, bus_to=bus1, 
                     r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                     rate=900.0)
    line1 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, 
                     r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                     rate=900.0)
    
    grid.add_line(line0)
    grid.add_line(line1)
    
    # VSC connecting DC bus to AC bus2
    vsc = gce.VSC(name="VSC", bus_from=bus_dc, bus_to=bus2, 
                  control1=ConverterControlType.Qac, control1_val=1.0, 
                  control2=ConverterControlType.Vm_dc, control2_val=1.0)
    grid.add_vsc(vsc)
    
    # Loads
    load1 = gce.Load(P=9.999999, Q=0.999999)
    load_dc = gce.Load(P=0.5, Q=0.0)
    grid.add_load(bus=bus1, api_obj=load1)
    grid.add_load(bus=bus_dc, api_obj=load_dc)
    
    # Generator
    gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom=900,
                         x1=0.86138701, r1=0.3, freq=50.0,
                         M=10.0, D=1.0, omega_ref=1.0,
                         Kp=1.0, Ki=10.0)
    grid.add_generator(bus=bus0, api_obj=gen0)
    
    return grid, vsc, bus0, bus1, bus2, bus_dc


def setup_vsc_model(grid, vsc):
    """Setup the VSC AC2AC model for the validation."""
    # Create dynamic model host for VSC
    vsc_dynhost = DynamicModelHost()
    
    # Build VSC AC2AC model
    vsc_model = VscAc2acModel(grid.rms_var_factory)
    vsc_block = block_deep_copy(vsc_model.block)
    
    # Get bus variables
    bus_dc = vsc.bus_from
    bus_ac = vsc.bus_to
    
    # Connect inputs to bus RMS models
    # vsc_block.in_vars = [vac, theta_ac, vdc]
    vsc_block.connect([vsc_block.in_vars[0]], [bus_ac.rms_model.model.out_vars[0]])  # vac
    vsc_block.connect([vsc_block.in_vars[1]], [bus_ac.rms_model.model.out_vars[1]])  # theta_ac
    vsc_block.connect([vsc_block.in_vars[2]], [bus_dc.rms_model.model.out_vars[0]])  # vdc
    
    vsc_dynhost.model = vsc_block
    vsc.rms_model = vsc_dynhost
    
    return vsc_block


def run_power_flow(grid):
    """Run power flow to initialize the system."""
    options = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    
    res = gce.power_flow(grid, options=options)
    print(f"Power Flow Converged: {res.converged}")
    print("\nBus Results:")
    print(res.get_bus_df())
    print("\nBranch Results:")
    print(res.get_branch_df())
    
    return res


def run_rms_simulation(grid, pf_results):
    """Run RMS simulation."""
    options = RmsOptions(
        time_step=0.001,
        simulation_time=1.0,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=1000,
        verbose=0
    )
    
    problem = RmsProblemDae(grid=grid, options=options, pf_results=pf_results)
    solver = BackEulerImplicitIntegration(
        problem=problem,
        t0=0,
        t_end=options.simulation_time,
        h=options.time_step,
        max_iter=options.max_iter
    )
    
    t, y, well_initialized, converged = solver.simulate()
    
    return t, y, problem


def extract_results(t, y, problem, vsc_block, bus_ac, bus_dc):
    """Extract VSC results from simulation."""
    # Get variable indices
    pac = find_name_in_block('pac', vsc_block)
    qac = find_name_in_block('qac', vsc_block)
    alpha = find_name_in_block('alpha', vsc_block)
    am = find_name_in_block('am', vsc_block)
    iac = find_name_in_block('iac', vsc_block)
    phi_ac = find_name_in_block('phi_ac', vsc_block)
    
    # Get bus voltage indices
    vac_idx = problem.get_var_idx(bus_ac.rms_model.model.out_vars[0])
    theta_ac_idx = problem.get_var_idx(bus_ac.rms_model.model.out_vars[1])
    vdc_idx = problem.get_var_idx(bus_dc.rms_model.model.out_vars[0])
    
    results = {
        't': t,
        'pac': y[:, problem.get_var_idx(pac)],
        'qac': y[:, problem.get_var_idx(qac)],
        'alpha': y[:, problem.get_var_idx(alpha)],
        'am': y[:, problem.get_var_idx(am)],
        'iac': y[:, problem.get_var_idx(iac)],
        'phi_ac': y[:, problem.get_var_idx(phi_ac)],
        'vac': y[:, vac_idx],
        'theta_ac': y[:, theta_ac_idx],
        'vdc': y[:, vdc_idx],
    }
    
    return results


def plot_results(results):
    """Plot simulation results."""
    t = results['t']
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    
    # AC Power
    axes[0, 0].plot(t, results['pac'], label='pac', linewidth=2)
    axes[0, 0].plot(t, results['qac'], label='qac', linewidth=2)
    axes[0, 0].set_xlabel('Time (s)')
    axes[0, 0].set_ylabel('Power (pu)')
    axes[0, 0].legend()
    axes[0, 0].grid(True)
    axes[0, 0].set_title('AC Active and Reactive Power')
    
    # Voltages
    axes[0, 1].plot(t, results['vac'], label='vac (AC)', linewidth=2)
    axes[0, 1].plot(t, results['vdc'], label='vdc (DC)', linewidth=2)
    axes[0, 1].set_xlabel('Time (s)')
    axes[0, 1].set_ylabel('Voltage (pu)')
    axes[0, 1].legend()
    axes[0, 1].grid(True)
    axes[0, 1].set_title('AC and DC Voltages')
    
    # Current
    axes[0, 2].plot(t, results['iac'], label='iac', linewidth=2, color='purple')
    axes[0, 2].set_xlabel('Time (s)')
    axes[0, 2].set_ylabel('Current (pu)')
    axes[0, 2].legend()
    axes[0, 2].grid(True)
    axes[0, 2].set_title('AC Current Magnitude')
    
    # Angles
    axes[1, 0].plot(t, results['theta_ac'], label='theta_ac', linewidth=2)
    axes[1, 0].plot(t, results['phi_ac'], label='phi_ac', linewidth=2)
    axes[1, 0].plot(t, results['alpha'], label='alpha', linewidth=2)
    axes[1, 0].set_xlabel('Time (s)')
    axes[1, 0].set_ylabel('Angle (rad)')
    axes[1, 0].legend()
    axes[1, 0].grid(True)
    axes[1, 0].set_title('Angles')
    
    # Modulation index
    axes[1, 1].plot(t, results['am'], label='am', linewidth=2, color='orange')
    axes[1, 1].set_xlabel('Time (s)')
    axes[1, 1].set_ylabel('Modulation Index')
    axes[1, 1].legend()
    axes[1, 1].grid(True)
    axes[1, 1].set_title('Modulation Index')
    
    # Equation residuals
    rT, xT = 0.01, 0.1
    gT = rT / (rT**2 + xT**2)
    bT = -xT / (rT**2 + xT**2)
    sqrt_38 = np.sqrt(3.0 / 8.0)
    
    # Calculate residuals for (18.9)
    pac_calc = gT * results['vac']**2 - sqrt_38 * results['am'] * results['vdc'] * results['vac'] * gT * np.cos(results['theta_ac'] - results['alpha']) \
               - sqrt_38 * results['am'] * results['vdc'] * results['vac'] * bT * np.sin(results['theta_ac'] - results['alpha'])
    qac_calc = -bT * results['vac']**2 + sqrt_38 * results['am'] * results['vdc'] * results['vac'] * bT * np.cos(results['theta_ac'] - results['alpha']) \
               - sqrt_38 * results['am'] * results['vdc'] * results['vac'] * gT * np.sin(results['theta_ac'] - results['alpha'])
    
    # Calculate residual for (18.10)
    eq10_res = gT * (sqrt_38 * results['am'] * results['vdc'])**2 - sqrt_38 * results['am'] * results['vdc'] * results['vac'] * gT * np.cos(results['theta_ac'] - results['alpha']) \
               + sqrt_38 * results['am'] * results['vdc'] * results['vac'] * bT * np.sin(results['theta_ac'] - results['alpha'])
    
    # Calculate residual for (18.11a)
    eq11a_res = results['pac']**2 + results['qac']**2 - results['vac'] * results['iac']
    
    axes[1, 2].plot(t, results['pac'] - pac_calc, label='Eq 18.9a (pac)', alpha=0.7)
    axes[1, 2].plot(t, results['qac'] - qac_calc, label='Eq 18.9b (qac)', alpha=0.7)
    axes[1, 2].plot(t, eq10_res, label='Eq 18.10 (DC/AC)', alpha=0.7)
    axes[1, 2].plot(t, eq11a_res, label='Eq 18.11a (Iac)', alpha=0.7)
    axes[1, 2].set_xlabel('Time (s)')
    axes[1, 2].set_ylabel('Residual')
    axes[1, 2].legend()
    axes[1, 2].grid(True)
    axes[1, 2].set_title('Equation Residuals')
    
    plt.tight_layout()
    plt.savefig('vsc_ac2ac_validation_results.png', dpi=150)
    plt.show()


def main():
    """Main validation function."""
    print("="*60)
    print("VSC AC2AC MODEL VALIDATION")
    print("Equations: 18.9, 18.10, 18.11")
    print("="*60)
    
    # Create test grid
    print("\n1. Creating test grid...")
    grid, vsc, bus0, bus1, bus2, bus_dc = create_test_grid()
    
    # Setup VSC AC2AC model
    print("2. Setting up VSC AC2AC model...")
    vsc_block = setup_vsc_model(grid, vsc)
    
    # Run power flow
    print("3. Running power flow...")
    pf_results = run_power_flow(grid)
    
    if not pf_results.converged:
        print("ERROR: Power flow did not converge!")
        return False
    
    # Run RMS simulation
    print("4. Running RMS simulation...")
    t, y, problem = run_rms_simulation(grid, pf_results)
    
    # Extract results
    print("5. Extracting results...")
    results = extract_results(t, y, problem, vsc_block, bus2, bus_dc)
    
    # Validate equations
    print("6. Validating equations...")
    validation_passed = validate_equations(results)
    
    # Plot results
    print("7. Generating plots...")
    plot_results(results)
    
    return validation_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
