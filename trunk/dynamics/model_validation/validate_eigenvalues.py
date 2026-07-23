"""
Validate eigenvalues by checking A*v = lambda*v
"""
import numpy as np
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import compute_state_matrix
from VeraGridEngine.Simulations.Rms.problems.rms_problem_phasor import RmsProblemPhasor
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Rms.bus_phasor_rms_template import initialize_bus_phasor_rms
from VeraGridEngine.Templates.Rms.line_phasor_rms_template import get_line_phasor_rms_template
from VeraGridEngine.Templates.Rms.load_phasor_current_rms_template import get_load_phasor_current_rms_template
from VeraGridEngine.Templates.Rms.genqec_phasor_rms_template import get_complete_generator_template_phasor
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model

def validate_eigenvalues():
    """Validate that computed eigenvalues satisfy A*v = lambda*v"""
    print("="*70)
    print("EIGENVALUE VALIDATION")
    print("="*70)
    
    # Create grid
    Sbase = 100.0
    grid = gce.MultiCircuit(Sbase=Sbase, fbase=50.0)
    
    bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10)
    grid.add_bus(bus0)
    grid.add_bus(bus1)
    
    for bus in grid.buses:
        initialize_bus_phasor_rms(bus, vf=grid.var_factory)
    
    line = gce.Line(name="Line", bus_from=bus0, bus_to=bus1,
                    r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
    grid.add_line(line)
    
    load = gce.Load(P=9.999999, Q=0.999999)
    grid.add_load(bus=bus1, api_obj=load)
    
    gen = gce.Generator(name="Gen0", P=10, vset=1.0, Snom=900)
    grid.add_generator(bus=bus0, api_obj=gen)
    
    # Build models
    genqec = get_complete_generator_template_phasor(grid.var_factory, name="Gen0").block
    
    line_mdl = get_line_phasor_rms_template(grid.var_factory).block
    grid.var_factory.add_connections([line_mdl.in_vars[0]], [bus0.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line_mdl.in_vars[1]], [bus0.rms_model.out_vars[1]])
    grid.var_factory.add_connections([line_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])
    set_rms_model(device=line, model=line_mdl, var_factory=grid.var_factory)

    grid.var_factory.add_connections([genqec.in_vars[0]], [bus0.rms_model.out_vars[0]])
    grid.var_factory.add_connections([genqec.in_vars[1]], [bus0.rms_model.out_vars[1]])
    set_rms_model(device=gen, model=genqec, var_factory=grid.var_factory)
    
    load_mdl = get_load_phasor_current_rms_template(grid.var_factory).block
    grid.var_factory.add_connections([load_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
    grid.var_factory.add_connections([load_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])
    load_mdl.set_parameter_in_model(var_name="Ir0", new_value=-0.1)
    load_mdl.set_parameter_in_model(var_name="Ii0", new_value=-0.01)
    set_rms_model(device=load, model=load_mdl, var_factory=grid.var_factory)
    
    # Power flow
    pf_options = gce.PowerFlowOptions()
    pf_results = gce.power_flow(grid, pf_options)
    
    # Create problem
    rms_options = RmsOptions(time_step=0.01, simulation_time=1.0, tolerance=1e-6, max_iter=20)
    phasor_problem = RmsProblemPhasor(grid=grid, options=rms_options, pf_results=pf_results)
    
    print(f"\nProblem has {phasor_problem.get_states_number()} states")
    
    # Compute state matrix
    x = phasor_problem.get_x0()
    dx = np.zeros(phasor_problem.get_diff_var_number())
    A_bal, A = compute_state_matrix(phasor_problem, x, dx)
    
    print(f"State matrix A shape: {A.shape}")
    
    # Compute eigenvalues and eigenvectors
    eigenvalues, eigenvectors = np.linalg.eig(A)
    
    # Get state variable names
    state_vars = phasor_problem.state_vars
    
    # Sort by real part (most positive first)
    sorted_indices = np.argsort(np.real(eigenvalues))[::-1]
    
    print(f"\n{'Mode':<6} {'Real':<12} {'Imag':<12} {'Freq(Hz)':<10} {'Status':<10} {'Dominant State':<25}")
    print("-" * 85)
    
    max_residual = 0.0
    unstable_modes = []
    
    for i, idx in enumerate(sorted_indices, 1):
        lam = eigenvalues[idx]
        v = eigenvectors[:, idx]
        
        real_part = np.real(lam)
        imag_part = np.imag(lam)
        freq = abs(imag_part) / (2 * np.pi)
        
        # Find dominant state for this eigenvector
        max_idx = np.argmax(np.abs(v))
        dominant_state = str(state_vars[max_idx]) if max_idx < len(state_vars) else f"State {max_idx}"
        
        status = "Stable"
        if real_part > 1e-6:
            status = "UNSTABLE"
            unstable_modes.append((i, lam, v, dominant_state))
        elif abs(real_part) < 1e-6:
            status = "Marginal"
        
        print(f"{i:<6} {real_part:<12.6f} {imag_part:<12.6f} {freq:<10.4f} {status:<10} {dominant_state:<25}")
    
    # Print detailed eigenvector info for unstable modes
    if unstable_modes:
        print(f"\n{'='*70}")
        print("UNSTABLE MODE DETAILS (Eigenvectors)")
        print(f"{'='*70}")
        
        for mode_num, lam, v, dom_state in unstable_modes:
            print(f"\nMode {mode_num}: {lam:.6f}")
            print(f"Dominant state: {dom_state}")
            print(f"\nFull eigenvector (showing top 5 components):")
            
            # Get top 5 components by magnitude
            abs_v = np.abs(v)
            top_indices = np.argsort(abs_v)[-5:][::-1]
            
            for j, idx in enumerate(top_indices):
                state_name = str(state_vars[idx]) if idx < len(state_vars) else f"State {idx}"
                print(f"  [{idx:2d}] {state_name:<25}: {v[idx]:15.6f} (|v|={abs_v[idx]:.6f})")
    
    # Validation: Check if A @ v ≈ lambda * v
    print(f"\n{'='*70}")
    print("VALIDATION (A*v = lambda*v)")
    print(f"{'='*70}")
    
    for i in [0, len(eigenvalues)//2, -1]:  # Check first, middle, last
        idx = sorted_indices[i]
        lam = eigenvalues[idx]
        v = eigenvectors[:, idx]
        Av = A @ v
        lv = lam * v
        residual = np.linalg.norm(Av - lv)
        max_residual = max(max_residual, residual)
        status = "VALID" if residual < 1e-8 else "INVALID"
        print(f"Mode {i+1}: residual = {residual:.6e} [{status}]")
    
    print(f"\nMaximum residual: {max_residual:.6e}")
    
    if max_residual < 1e-8:
        print("✓ All eigenvalues are VALID (A*v = lambda*v satisfied)")
    else:
        print("⚠ Some eigenvalues have large residuals - numerical issues present")
    
    print(f"\nEigenvalue magnitude check:")
    print(f"  Max |lambda|: {np.max(np.abs(eigenvalues)):.6f}")
    print(f"  Min |lambda|: {np.min(np.abs(eigenvalues)):.6f}")
    print(f"  Max real part: {np.max(np.real(eigenvalues)):.6f}")
    
    return max_residual < 1e-8

if __name__ == "__main__":
    success = validate_eigenvalues()
    sys.exit(0 if success else 1)
