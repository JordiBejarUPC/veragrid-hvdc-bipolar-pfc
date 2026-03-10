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
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import SmallSignalStabilityRmsOptions
from VeraGridEngine.Simulations.Rms.problems.rms_problem_phasor import RmsProblemPhasor
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Rms.bus_phasor_rms_template import initialize_bus_phasor_rms
from VeraGridEngine.Templates.Rms.line_phasor_rms_template import get_line_phasor_rms_template
from VeraGridEngine.Templates.Rms.load_phasor_rms_template import get_load_phasor_rms_template
from VeraGridEngine.Templates.Rms.genqec_phasor_rms_template import get_complete_generator_template_phasor
from VeraGridEngine.Templates.templates_common_functions import set_rms_model


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
    line_mdl.connect([line_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])
    line_mdl.connect([line_mdl.in_vars[2]], [bus1.rms_model.model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[3]], [bus1.rms_model.model.out_vars[1]])
    
    # Attach line model to the line device
    set_rms_model(device=line, model=line_mdl)
    
    genqec.connect([genqec.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
    genqec.connect([genqec.in_vars[1]], [bus0.rms_model.model.out_vars[1]])
    
    set_rms_model(device=gen, model=genqec)
    
    load_mdl = get_load_phasor_rms_template(grid.var_factory).block
    load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
    load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])
    load_mdl.set_parameter_in_model(var_name="Pl0", new_value=-0.0999999)
    load_mdl.set_parameter_in_model(var_name="Ql0", new_value=-0.009999999862208533)
    set_rms_model(device=load, model=load_mdl)
    
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
    
    ss_options = SmallSignalStabilityRmsOptions(ss_assessment_time=0)
    
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
    
    def inspect_gy(gy: sp.spmatrix, tol: float = 1e-12) -> None:
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
        dense = gy_csc.toarray()
        s = la.svdvals(dense)
        smin = s[-1]
        smax = s[0]
        cond = np.inf if smin < tol else smax / smin
        print(f"sigma_min = {smin:.3e}")
        print(f"sigma_max = {smax:.3e}")
        print(f"cond      = {cond:.3e}")
        if smin < tol:
            ns = la.null_space(dense)
            print(f"nullity ≈ {ns.shape[1]}")
    
    try:
        problem = driver.problem
        x = problem.get_x0()
        dx = np.zeros(problem.get_diff_var_number())
        h = 0.001
        gy = problem.get_j22(x, dx, h)
        inspect_gy(gy)
        
        # Check algebraic variables and equations count
        print(f"\nAlgebraic vars: {problem.get_algebraic_var_number()}")
        print(f"Algebraic eqs: {len(problem._algebraic_eqs)}")
        
        # Print details of zero rows and columns
        # Compute actual zero rows and columns
        gy_csc = gy.tocsc()
        gy_csr = gy.tocsr()
        zero_rows = np.flatnonzero(np.diff(gy_csr.indptr) == 0).tolist()
        zero_cols = np.flatnonzero(np.diff(gy_csc.indptr) == 0).tolist()
        
        print(f"\n=== Zero Row Details ===")
        print(f"Actual zero rows: {zero_rows}")
        for idx in zero_rows:
            if idx < len(problem._algebraic_vars):
                print(f"\nRow {idx} (zero row):")
                print(f"  Variable: {problem._algebraic_vars[idx]}")
                if idx < len(problem._algebraic_eqs):
                    print(f"  Equation: {problem._algebraic_eqs[idx]}")
                    eq = problem._algebraic_eqs[idx]
                    vars_in_eq = eq.get_vars() if hasattr(eq, 'get_vars') else []
                    print(f"  Variables: {[str(v) for v in vars_in_eq]}")
                    # Check if any of these variables are in algebraic_vars
                    for v in vars_in_eq:
                        if v in problem._algebraic_vars:
                            col_idx = problem._algebraic_vars.index(v)
                            print(f"    -> {v} is algebraic at index {col_idx}")
                        elif v in problem._state_vars:
                            print(f"    -> {v} is a STATE variable")
        
        print(f"\n=== Zero Column Details ===")
        for idx in zero_cols:
            if idx < len(problem._algebraic_vars):
                print(f"\nCol {idx} (zero col):")
                print(f"  Variable: {problem._algebraic_vars[idx]}")
        
        # Also print some context around these indices
        print(f"\n=== Context around problematic indices ===")
        print("Algebraic variables [30-36]:")
        for i in range(30, min(37, len(problem._algebraic_vars))):
            print(f"  [{i}] {problem._algebraic_vars[i]}")
        
        print("\nAlgebraic variables [85-91]:")
        for i in range(85, min(92, len(problem._algebraic_vars))):
            print(f"  [{i}] {problem._algebraic_vars[i]}")
        
        print("\nAlgebraic variables [0-20]:")
        for i in range(0, min(21, len(problem._algebraic_vars))):
            print(f"  [{i}] {problem._algebraic_vars[i]}")
        
        # Print state variables to check if dependencies are there
        print("\n=== State Variables ===")
        print(f"Number of state vars: {len(problem._state_vars)}")
        print("State variables [0-10]:")
        for i in range(0, min(11, len(problem._state_vars))):
            print(f"  [{i}] {problem._state_vars[i]}")
        
        # Check if u_gov0, omegaGen0 are state vars
        print("\nSearching for u_gov0, omegaGen0, _aux, y_subexciter1...")
        for i, sv in enumerate(problem._state_vars):
            if 'u_gov0' in str(sv) or 'omegaGen0' in str(sv) or '_aux' in str(sv) or 'y_subexciter1' in str(sv):
                print(f"  Found in state_vars[{i}]: {sv}")
        
        # Check if Vr/Vi at index 2,3 appear in any equations
        print("\n=== Checking if duplicate Vr/Vi are used ===")
        print("Algebraic variable [0]:", problem._algebraic_vars[0])
        print("Algebraic variable [1]:", problem._algebraic_vars[1])
        print("Algebraic variable [2]:", problem._algebraic_vars[2])
        print("Algebraic variable [3]:", problem._algebraic_vars[3])
        
        # Count occurrences of Vr/Vi in equations
        v0_uid = problem._algebraic_vars[0].uid
        v1_uid = problem._algebraic_vars[1].uid
        v2_uid = problem._algebraic_vars[2].uid
        v3_uid = problem._algebraic_vars[3].uid
        
        print(f"\nUIDs: Vr[0]={v0_uid}, Vi[1]={v1_uid}, Vr[2]={v2_uid}, Vi[3]={v3_uid}")
        print(f"Are they the same? Vr[0]==Vr[2]: {v0_uid == v2_uid}")
        print(f"Are they the same? Vi[1]==Vi[3]: {v1_uid == v3_uid}")
        
        # Check if Bus1's Vr/Vi (from the bus model) match indices 2,3
        print(f"\nBus1 Vr uid: {bus1.rms_model.model.out_vars[0].uid}")
        print(f"Bus1 Vi uid: {bus1.rms_model.model.out_vars[1].uid}")
        print(f"Bus1 Vr == alg_var[2]: {bus1.rms_model.model.out_vars[0].uid == v2_uid}")
        print(f"Bus1 Vi == alg_var[3]: {bus1.rms_model.model.out_vars[1].uid == v3_uid}")
        
        # Print ALL equations to see which use Vr/Vi at indices 2,3
        print("\n=== ALL ALGEBRAIC EQUATIONS ===")
        v2_var = problem._algebraic_vars[2]
        v3_var = problem._algebraic_vars[3]
        for i in range(min(30, len(problem._algebraic_eqs))):
            eq = problem._algebraic_eqs[i]
            vars_in_eq = eq.get_vars() if hasattr(eq, 'get_vars') else []
            has_v2 = v2_var in vars_in_eq
            has_v3 = v3_var in vars_in_eq
            if has_v2 or has_v3:
                print(f"Eq[{i}]: {eq}")
                print(f"         -> uses Vr[2]={has_v2}, Vi[3]={has_v3}")
        
        # Check a few equations to see which Vr/Vi they use
        print("\n=== Sample equations ===")
        for i in [0, 1, 6, 7, 8]:
            if i < len(problem._algebraic_eqs):
                eq = problem._algebraic_eqs[i]
                vars_in_eq = eq.get_vars() if hasattr(eq, 'get_vars') else []
                uids = [v.uid for v in vars_in_eq]
                has_v0 = v0_uid in uids
                has_v1 = v1_uid in uids
                has_v2 = v2_uid in uids
                has_v3 = v3_uid in uids
                print(f"Eq[{i}]: uses Vr[0]={has_v0}, Vi[1]={has_v1}, Vr[2]={has_v2}, Vi[3]={has_v3}")
        
        # Check equations 33 and 88 to see what variables they contain
        print("\n=== Equations with zero rows ===")
        for i in [33, 88]:
            if i < len(problem._algebraic_eqs):
                eq = problem._algebraic_eqs[i]
                print(f"\nEq[{i}]:")
                print(f"  Expression: {eq}")
                vars_in_eq = eq.get_vars() if hasattr(eq, 'get_vars') else []
                print(f"  Variables ({len(vars_in_eq)}): {vars_in_eq}")
        
        # Check state equations
        print("\n=== State equations ===")
        print(f"Number of state equations: {len(problem._state_eqs)}")
        for i in range(min(10, len(problem._state_eqs))):
            print(f"\nState Eq[{i}]:")
            print(f"  Expression: {problem._state_eqs[i]}")
            vars_in_eq = problem._state_eqs[i].get_vars() if hasattr(problem._state_eqs[i], 'get_vars') else []
            print(f"  Variables: {vars_in_eq}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
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
    
    print(f"  Found {len(eigenvalues)} eigenvalues")
    
    # Display dominant modes
    print(f"\n  Dominant eigenvalues (top 10):")
    print(f"  {'Mode':<6} {'Real':<15} {'Imag':<15} {'Freq (Hz)':<12} {'Damping':<12} {'Status'}")
    print(f"  {'-'*80}")
    
    for i in range(min(10, len(eigenvalues))):
        lam = eigenvalues[i]
        real_part = np.real(lam)
        imag_part = np.imag(lam)
        freq = frequencies[i] if i < len(frequencies) else abs(imag_part) / (2 * np.pi)
        damping = damping_ratios[i] if i < len(damping_ratios) else 0.0
        
        status = "Stable" if real_part < -1e-6 else "UNSTABLE" if real_part > 1e-6 else "Marginal"
        print(f"  {i+1:<6} {real_part:<15.6f} {imag_part:<15.6f} {freq:<12.4f} {damping:<12.4f} {status}")
    
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
    plt.savefig('small_signal_phasor.png', dpi=150, bbox_inches='tight')
    print(f"  ✓ Plot saved to small_signal_phasor.png")
    plt.show()
    
    return True


if __name__ == "__main__":
    success = small_signal_analysis()
    sys.exit(0 if success else 1)
