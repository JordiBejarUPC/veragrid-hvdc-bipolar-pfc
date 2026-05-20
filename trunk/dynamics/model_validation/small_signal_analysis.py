# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Small Signal Analysis for Phasor-based RMS Grid.

This script creates the phasor problem manually and injects it into the SmallSignalStabilityRmsDriver.
"""

import numpy as np
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

from matplotlib import pyplot as plt

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions
from VeraGridEngine.Simulations.Rms.problems.rms_problem_phasor import RmsProblemPhasor
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Rms.bus_phasor_rms_template import initialize_bus_phasor_rms
from VeraGridEngine.Templates.Rms.line_phasor_rms_template import get_line_phasor_rms_template
from VeraGridEngine.Templates.Rms.load_phasor_current_rms_template import get_load_phasor_current_rms_template
from VeraGridEngine.Templates.Rms.genqec_phasor_rms_template import get_complete_generator_template_phasor
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model


def small_signal_analysis():
    """Perform small signal analysis on the phasor grid."""
    print("="*60)
    print("SMALL SIGNAL ANALYSIS - PHASOR RMS")
    print("="*60)
    
    # ===================================================================
    # CREATE GRID (Same as phasor validation)
    # ===================================================================
    print("\n[1] Creating phasor grid...")
    
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
    
    # Build RMS models
    genqec = get_complete_generator_template_phasor(grid.var_factory, name="Gen0").block
    
    line_mdl = get_line_phasor_rms_template(grid.var_factory).block
    grid_phasor.var_factory.add_connections([line_mdl.in_vars[0]], [bus0.rms_model.out_vars[0]])
    grid_phasor.var_factory.add_connections([line_mdl.in_vars[1]], [bus0.rms_model.out_vars[1]])
    grid_phasor.var_factory.add_connections([line_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
    grid_phasor.var_factory.add_connections([line_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])
    
    # Attach line model to the line device
    set_rms_model(device=line, model=line_mdl, var_factory=grid.var_factory)

    grid_phasor.var_factory.add_connections([genqec.in_vars[0]], [bus0.rms_model.out_vars[0]])
    grid_phasor.var_factory.add_connections([genqec.in_vars[1]], [bus0.rms_model.out_vars[1]])
    
    set_rms_model(device=gen, model=genqec, var_factory=grid.var_factory)
    
    load_mdl = get_load_phasor_current_rms_template(grid.var_factory).block
    grid_phasor.var_factory.add_connections([load_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
    grid_phasor.var_factory.add_connections([load_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])
    # Convert power to current: I = S* / V* (approximation for initialization)
    # For V ≈ 1.0, Ir ≈ P, Ii ≈ Q
    load_mdl.set_parameter_in_model(var_name="Ir0", new_value=-0.1)
    load_mdl.set_parameter_in_model(var_name="Ii0", new_value=-0.01)
    set_rms_model(device=load, model=load_mdl, var_factory=grid.var_factory)
    
    print("  ✓ Grid created with multilinear generator")
    
    # ===================================================================
    # POWER FLOW
    # ===================================================================
    print("\n[2] Running power flow...")
    pf_options = gce.PowerFlowOptions()
    pf_results = gce.power_flow(grid, pf_options)
    
    if pf_results.converged:
        print(f"  ✓ Power flow converged")
        for i, bus in enumerate(grid.buses):
            v = pf_results.voltage[i]
            print(f"    {bus.name}: Vm={abs(v):.4f} pu")
    else:
        print("  ✗ Power flow failed")
        return False
    
    # ===================================================================
    # CREATE PHASOR PROBLEM
    # ===================================================================
    print("\n[3] Creating phasor problem...")
    
    rms_options = RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        tolerance=1e-6,
        max_iter=20
    )
    
    phasor_problem = RmsProblemPhasor(grid=grid, options=rms_options, pf_results=pf_results)
    print(f"  ✓ Phasor problem created with {phasor_problem.get_states_number()} states")
    
    # ===================================================================
    # CREATE DRIVER AND SWAP PROBLEM
    # ===================================================================
    print("\n[4] Setting up small signal driver...")
    
    ss_options = RmsSmallSignalStabilityOptions(ss_assessment_time=0)
    
    # Create driver with dummy grid (it will create RmsProblemDae internally)
    dummy_grid = gce.MultiCircuit(Sbase=Sbase)
    driver = SmallSignalStabilityRmsDriver(
        grid=dummy_grid,
        rms_options=rms_options,
        sss_options=ss_options,
        pf_results=pf_results
    )
    
    # Swap in the actual phasor problem
    driver.problem = phasor_problem
    driver.k = phasor_problem.get_states_number()  # Update state count
    
    print("  ✓ Driver configured with phasor problem")
    
    # ===================================================================
    # INSPECT JACOBIAN
    # ===================================================================
    print("\n[4.5] Inspecting Jacobian...")
    import scipy.sparse as sp
    import scipy.linalg as la
    
    def inspect_gy(gy: sp.spmatrix, problem, tol: float = 1e-12) -> None:
        """Inspect Jacobian matrix to identify singularities."""
        gy_csc = gy.tocsc()
        gy_csr = gy.tocsr()
        m, n = gy_csc.shape
        print(f"gy shape: {m} x {n}, nnz={gy_csc.nnz}")
        if m != n:
            print("gy is not square")
            return
        zero_rows = np.flatnonzero(np.diff(gy_csr.indptr) == 0)
        zero_cols = np.flatnonzero(np.diff(gy_csc.indptr) == 0)
        print(f"zero rows: {zero_rows.tolist()}")
        print(f"zero cols: {zero_cols.tolist()}")
        
        # Print details of zero rows
        if len(zero_rows) > 0:
            print("\n=== Zero Row Details ===")
            for idx in zero_rows:
                if idx < len(problem._algebraic_vars):
                    print(f"\nRow {idx}:")
                    print(f"  Variable: {problem._algebraic_vars[idx]}")
                    if idx < len(problem._algebraic_eqs):
                        eq = problem._algebraic_eqs[idx]
                        print(f"  Equation: {eq}")
                        vars_in_eq = eq.get_vars() if hasattr(eq, 'get_vars') else []
                        print(f"  Variables in eq ({len(vars_in_eq)}): {[str(v) for v in vars_in_eq]}")
                        
                        # Check if variables are actually in algebraic_vars by UID
                        print(f"  Variable UID check:")
                        for v in vars_in_eq:
                            in_alg = any(av.uid == v.uid for av in problem._algebraic_vars)
                            print(f"    {v.name} (uid={v.uid}) in algebraic_vars: {in_alg}")
        
        # Print details of zero columns
        if len(zero_cols) > 0:
            print("\n=== Zero Column Details ===")
            for idx in zero_cols:
                if idx < len(problem._algebraic_vars):
                    print(f"\nCol {idx}: {problem._algebraic_vars[idx]}")
        
        dense = gy_csc.toarray()
        s = la.svdvals(dense)
        smin = s[-1]
        smax = s[0]
        cond = np.inf if smin < tol else smax / smin
        print(f"\nsigma_min = {smin:.3e}")
        print(f"sigma_max = {smax:.3e}")
        print(f"cond      = {cond:.3e}")
        if smin < tol:
            ns = la.null_space(dense)
            print(f"nullity ≈ {ns.shape[1]}")
            
            # Analyze null space to find problematic variables
            print("\n=== Null Space Analysis ===")
            for i in range(ns.shape[1]):
                vec = ns[:, i]
                # Find largest components
                abs_vec = np.abs(vec)
                top_indices = np.argsort(abs_vec)[-5:][::-1]
                print(f"\nNull vector {i} (top 5 components):")
                for idx in top_indices:
                    if abs_vec[idx] > 1e-6:
                        if idx < len(problem._algebraic_vars):
                            var_name = str(problem._algebraic_vars[idx])
                            print(f"  [{idx}] {var_name}: {vec[idx]:.4f}")
                        else:
                            print(f"  [{idx}] (no var): {vec[idx]:.4f}")
    
    try:
        problem = driver.problem
        x = problem.get_x0()
        dx = np.zeros(problem.get_diff_var_number())
        h = 0.001
        gy = problem.get_j22(x, dx, h)
        inspect_gy(gy, problem)
    except Exception as e:
        print(f"Error inspecting Jacobian: {e}")
    
    # ===================================================================
    # RUN ANALYSIS
    # ===================================================================
    print("\n[5] Running small signal analysis...")
    driver.run()
    
    # ===================================================================
    # DISPLAY RESULTS
    # ===================================================================
    print("\n[6] Analysis complete!")
    
    eigenvalues = driver.results.eigenvalues
    participation_factors = driver.results.participation_factors
    damping_ratios = driver.results.damping_ratios
    frequencies = driver.results.conjugate_frequencies
    
    # Filter out infinite eigenvalues (algebraic constraints)
    finite_mask = np.isfinite(eigenvalues) & (np.abs(eigenvalues) < 1e6)
    eigenvalues = eigenvalues[finite_mask]
    if participation_factors is not None:
        participation_factors = participation_factors[:, finite_mask]
    if damping_ratios is not None and len(damping_ratios) == len(finite_mask):
        damping_ratios = damping_ratios[finite_mask]
    if frequencies is not None and len(frequencies) == len(finite_mask):
        frequencies = frequencies[finite_mask]
    
    print(f"  Found {len(eigenvalues)} finite eigenvalues")
    
    # Display dominant modes
    print(f"\n  Dominant eigenvalues (top 10):")
    print(f"  {'Mode':<6} {'Real':<15} {'Imag':<15} {'Freq (Hz)':<12} {'Damping':<12} {'Status'}")
    print(f"  {'-'*80}")
    
    for i in range(min(10, len(eigenvalues))):
        lam = eigenvalues[i]
        real_part = np.real(lam)
        imag_part = np.imag(lam)
        
        # Calculate frequency and damping from eigenvalue directly
        freq = abs(imag_part) / (2 * np.pi)
        # Damping ratio: -Real / |lambda| for oscillatory modes, sign(Real) for real modes
        magnitude = np.sqrt(real_part**2 + imag_part**2)
        if magnitude > 1e-12:
            damping = -real_part / magnitude
        else:
            damping = 0.0
        
        status = "Stable" if real_part < -1e-6 else "UNSTABLE" if real_part > 1e-6 else "Marginal"
        print(f"  {i+1:<6} {real_part:<15.6f} {imag_part:<15.6f} {freq:<12.4f} {damping:<12.4f} {status}")
    
    # Check for unstable eigenvalues
    unstable = [(i, ev) for i, ev in enumerate(eigenvalues) if np.real(ev) > 1e-6]
    if unstable:
        print(f"\n  ⚠️  Found {len(unstable)} unstable eigenvalues:")
        print(f"  {'Mode':<6} {'Real':<15} {'Imag':<15} {'Dominant State'}")
        print(f"  {'-'*80}")
        
        # Get state variable names
        state_vars = driver.problem.state_vars
        
        for i, ev in unstable:
            # Find the state with highest participation for this mode
            if participation_factors is not None and i < participation_factors.shape[1]:
                pf = participation_factors[:, i]
                max_pf_idx = np.argmax(pf)
                dominant_state = str(state_vars[max_pf_idx]) if max_pf_idx < len(state_vars) else f"State {max_pf_idx}"
                pf_val = pf[max_pf_idx]
            else:
                dominant_state = "N/A"
                pf_val = 0.0
            
            print(f"  {i+1:<6} {np.real(ev):<15.6f} {np.imag(ev):<15.6f} {dominant_state:<30} (PF={pf_val:.3f})")
    
    # Stability
    max_real = np.max(np.real(eigenvalues))
    print(f"\n  Stability: {'STABLE' if max_real < -1e-6 else 'UNSTABLE' if max_real > 1e-6 else 'MARGINAL'}")
    
    # ===================================================================
    # PLOT
    # ===================================================================
    print("\n[7] Generating plots...")
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Eigenvalue map
    ax1 = axes[0]
    real_parts = np.real(eigenvalues)
    imag_parts = np.imag(eigenvalues)
    colors = ['red' if r > 0 else 'blue' for r in real_parts]
    ax1.scatter(real_parts, imag_parts, c=colors, alpha=0.6, s=50)
    ax1.axvline(x=0, color='k', linestyle='--', linewidth=1)
    ax1.set_xlabel('Real Part')
    ax1.set_ylabel('Imaginary Part')
    ax1.set_title('Eigenvalue Map (Phasor RMS with Multilinear Generator)')
    ax1.grid(True, alpha=0.3)
    
    # Participation factors
    ax2 = axes[1]
    if participation_factors is not None and len(participation_factors) > 0:
        n_modes = min(3, participation_factors.shape[1])
        n_states = min(10, participation_factors.shape[0])
        x = np.arange(n_states)
        width = 0.25
        
        for mode_idx in range(n_modes):
            pf = participation_factors[:n_states, mode_idx]
            pf = pf / np.sum(pf) if np.sum(pf) > 0 else pf
            ax2.bar(x + mode_idx*width, pf, width, 
                    label=f'Mode {mode_idx+1} ({np.real(eigenvalues[mode_idx]):.3f})')
        
        ax2.set_xlabel('State Variable')
        ax2.set_ylabel('Participation Factor')
        ax2.set_title('Participation Factors (Dominant Modes)')
        ax2.set_xticks(x + width)
        ax2.set_xticklabels([f'State {i}' for i in range(n_states)])
        ax2.legend()
        ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.show()
    
    return True


if __name__ == "__main__":
    success = small_signal_analysis()
    sys.exit(0 if success else 1)
