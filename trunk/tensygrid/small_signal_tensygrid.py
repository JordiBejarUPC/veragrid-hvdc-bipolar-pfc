# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Small Signal Analysis for Phasor-based RMS Grid.

This script creates the phasor problem manually and injects it into the SmallSignalStabilityRmsDriver.
"""
from typing import Tuple, Any, List
import numpy as np
from cryptography.x509 import name

from PolynomialMatrixBuilder import PolynomialMatrixBuilder
from matplotlib import pyplot as plt
import VeraGridEngine.api as vge
from VeraGridEngine.Templates.Rms.genqec_phasor_rms_template import get_genqec_phasor
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from phasor_diagnostics import (
    check_pf_line_equations,
    check_equation_consistency,
    debug_exciter_equations,
    check_generator_current_residuals as compare_generator_bus_currents,
)
#from scipy.optimize import linear_sum_assignment


FAST_MODE = True
FAST_GRID_PATH = 'trunk/tensygrid/grids/IEEE_14-2.gridcal'
FULL_GRID_PATH = 'trunk/tensygrid/grids/IEEE118_opf.gridcal'
PRINT_ALL_BUSES = not FAST_MODE
ENABLE_POST_COMPARE_PLOT = not FAST_MODE
RUN_DYNAMIC_STEP = True
RUN_CONSISTENCY_CHECK = False
RUN_PF_LINE_EQ_CHECK = False
RUN_EXCITER_DIAGNOSTICS = False
PF_LINE_FOCUS_INDEX = 0
DYNAMIC_SIM_TIME_FAST = 0.05
DYNAMIC_SIM_TIME_FULL = 0.20

def define_problem_with_path(grid_path):
    """Creates the grid, runs the power flow, and returns the phasor problem."""
    print("\n[1] Creating phasor grid_path...")
    grid = vge.open_file(grid_path)

    # Build RMS models
    # Coses que hem d'afegir: bus, branches, generators, trafos, loads, shunts

    ## BUSES:
    for bus in grid.buses:
        busec = vge.initialize_bus_phasor_rms(bus, vf=grid.var_factory)
        busec = vge.to_implicit(busec, grid.var_factory)
        vge.set_rms_model(device=busec, model=busec, var_factory=grid.var_factory)
    ## -GENERATORS
    for igen, gen in enumerate(grid.generators):    
        genqec = vge.get_complete_generator_template_phasor(grid.var_factory, name=f"Gen{igen}").block
        genqec.connect([genqec.in_vars[0]], [gen.bus.rms_model.out_vars[0]])
        genqec.connect([genqec.in_vars[1]], [gen.bus.rms_model.out_vars[1]])
        vge.set_rms_model(device=gen, model=genqec, var_factory=grid.var_factory)
    ## -LINES:
    for line in grid.lines:
        lineec = vge.get_line_phasor_rms_template(grid.var_factory, name=line.name).block
        lineec.connect([lineec.in_vars[0]], [line.bus_from.rms_model.out_vars[0]])
        lineec.connect([lineec.in_vars[1]], [line.bus_from.rms_model.out_vars[1]])
        lineec.connect([lineec.in_vars[2]], [line.bus_to.rms_model.out_vars[0]])
        lineec.connect([lineec.in_vars[3]], [line.bus_to.rms_model.out_vars[1]])
        lineec = vge.to_implicit(lineec, grid.var_factory)
        vge.set_rms_model(device=line, model=lineec, var_factory=grid.var_factory)
    ## -LOADS:
    for load in grid.loads:
        loadec = vge.get_load_phasor_current_rms_template(grid.var_factory, name=load.name).block
        loadec.connect([loadec.in_vars[0]], [load.bus.rms_model.out_vars[0]])
        loadec.connect([loadec.in_vars[1]], [load.bus.rms_model.out_vars[1]])
        vge.set_rms_model(device=load, model=loadec, var_factory=grid.var_factory)
    ## -TRANSFORMERS 2w:
    for trafo in grid.transformers2w:
        trafoec = vge.initialize_trafo_rms(trafo, grid.var_factory, use_phasor_template=True).block
        trafoec.connect([trafoec.in_vars[0]], [trafo.bus_from.rms_model.out_vars[0]])
        trafoec.connect([trafoec.in_vars[1]], [trafo.bus_from.rms_model.out_vars[1]])
        trafoec.connect([trafoec.in_vars[2]], [trafo.bus_to.rms_model.out_vars[0]])
        trafoec.connect([trafoec.in_vars[3]], [trafo.bus_to.rms_model.out_vars[1]])
        trafoec = vge.to_implicit(trafoec, grid.var_factory)
        vge.set_rms_model(device=trafo, model=trafoec, var_factory=grid.var_factory)


    print("  ✓ Grid with path loaded")

    # ===================================================================
    # POWER FLOW
    # ===================================================================

    print("\n[2] Running power flow...")
    pf_options = vge.PowerFlowOptions()
    pf_results = vge.power_flow(grid, pf_options)

    if pf_results.converged:
        print(f"  ✓ Power flow converged")
        if PRINT_ALL_BUSES:
            for i, bus in enumerate(grid.buses):
                v = pf_results.voltage[i]
                print(f"    {bus.name}: Vm={abs(v):.4f} pu")
        else:
            vm = np.abs(pf_results.voltage)
            print(f"    Buses: {len(grid.buses)}, Vm[min/avg/max]=({vm.min():.4f}/{vm.mean():.4f}/{vm.max():.4f}) pu")
    else:
        print("  ✗ Power flow failed")
        return False

    if RUN_PF_LINE_EQ_CHECK:
        check_pf_line_equations(grid=grid, pf_results=pf_results)

    # ===================================================================
    # CREATE PHASOR PROBLEM
    # ===================================================================
    print("\n[3] Creating phasor problem...")

    rms_options = vge.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        tolerance=1e-6,
        max_iter=20,
    )
    phasor_problem = vge.RmsProblemPhasor(grid=grid, options=rms_options, pf_results=pf_results)
    print(f"  ✓ Phasor problem created with {phasor_problem.get_states_number()} states")

    if RUN_CONSISTENCY_CHECK:
        check_equation_consistency(phasor_problem)
    if RUN_EXCITER_DIAGNOSTICS:
        debug_exciter_equations(phasor_problem)
        compare_generator_bus_currents(grid=grid, problem=phasor_problem, pf_results=pf_results)
    # ===================================================================
    # DYNAMIC VALIDATION
    # ===================================================================
    if RUN_DYNAMIC_STEP:
        print("\n[3.1] Running dynamic simulation...")
        dyn_t_end = DYNAMIC_SIM_TIME_FAST if FAST_MODE else DYNAMIC_SIM_TIME_FULL
        solver = BackEulerImplicitIntegration(
            problem=phasor_problem,
            t0=0,
            t_end=dyn_t_end,
            h=rms_options.time_step,
            max_iter=rms_options.max_iter
        )
        t_dyn, y_dyn, well_initialized, converged = solver.simulate()
        print(
            f"  ✓ Dynamic simulation finished: steps={len(t_dyn)}, "
            f"well_initialized={well_initialized}, converged={converged}, "
            f"final|x|={np.linalg.norm(y_dyn[-1, :]):.4e}"
        )

    return phasor_problem

def define_problem():
    """Creates the grid, runs the power flow, and returns the phasor problem."""
    print("\n[1] Creating phasor grid...")
    Sbase = 100.0
    grid = vge.MultiCircuit(Sbase=Sbase, fbase=50.0)

    bus0 = vge.Bus(name="Bus0", Vnom=10, is_slack=True)
    bus1 = vge.Bus(name="Bus1", Vnom=10)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    for bus in grid.buses:
        vge.initialize_bus_phasor_rms(bus, vf=grid.var_factory)

    line = vge.Line(name="Line", bus_from=bus0, bus_to=bus1,
                    r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
    grid.add_line(line)

    load = vge.Load(P=9.999999, Q=0.999999)
    grid.add_load(bus=bus1, api_obj=load)

    gen = vge.Generator(name="Gen0", P=10, vset=1.0, Snom=900)
    grid.add_generator(bus=bus0, api_obj=gen)

    # Build RMS models
    genqec = vge.get_complete_generator_template_phasor(grid.var_factory, name="Gen0").block
    genqec = vge.to_implicit(genqec, grid.var_factory)

    line_mdl = vge.get_line_phasor_rms_template(grid.var_factory).block
    line_mdl.connect([line_mdl.in_vars[0]], [bus0.rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[1]], [bus0.rms_model.out_vars[1]])
    line_mdl.connect([line_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])

    # Attach line model to the line device
    vge.set_rms_model(device=line, model=line_mdl, var_factory=grid.var_factory)

    genqec.connect([genqec.in_vars[0]], [bus0.rms_model.out_vars[0]])
    genqec.connect([genqec.in_vars[1]], [bus0.rms_model.out_vars[1]])

    vge.set_rms_model(device=gen, model=genqec, var_factory=grid.var_factory)

    load_mdl = vge.get_load_phasor_current_rms_template(grid.var_factory).block
    load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
    load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])
    # Convert power to current: I = S* / V* (approximation for initialization)
    # For V ≈ 1.0, Ir ≈ P, Ii ≈ Q
    load_mdl.set_parameter_in_model(var_name="Ir0", new_value=-0.1)
    load_mdl.set_parameter_in_model(var_name="Ii0", new_value=-0.01)
    vge.set_rms_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    print("  ✓ Grid created with multilinear generator")

    # ===================================================================
    # POWER FLOW
    # ===================================================================
    print("\n[2] Running power flow...")
    pf_options = vge.PowerFlowOptions()
    pf_results = vge.power_flow(grid, pf_options)

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

    rms_options = vge.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        tolerance=1e-6,
        max_iter=20,
    )

    phasor_problem = vge.RmsProblemPhasor(grid=grid, options=rms_options, pf_results=pf_results)
    print(f"  ✓ Phasor problem created with {phasor_problem.get_states_number()} states")

    return phasor_problem

def op_extraction(problem: vge.RmsProblemPhasor) -> dict:
    """
    Returns the operating point dictionary from a defined VeraGrid problem.
    """
    v_dict: dict = dict()
    def safe_get_value(val):
        try:
            return float(val)
        except:
            if hasattr(val, 'value'):
                try:
                    return float(val.value)
                except:
                    pass
        return None

    # 3. EXTRACT x0 (Equilibrium point)
    try:
        x0 = problem.get_x0()
        for i, sym in enumerate(problem.state_and_algebraic_vars):
            v_dict[str(sym.name)] = float(x0[i])
    except Exception:
        pass

    # 4. EXTRACTION FROM THE PHOTO PATHS
    if hasattr(problem, '_variable_parameters') and hasattr(problem, '_variable_parameters_values'):
        names = problem._variable_parameters
        values = problem._variable_parameters_values
        if names is not None and values is not None:
            # If values is a list/array and names contains the symbols
            for name_obj, val_obj in zip(names, values):
                s_name = str(name_obj.name) if hasattr(name_obj, 'name') else str(name_obj)
                val = safe_get_value(val_obj)
                if val is not None:
                    v_dict[s_name] = val

    # Backup just in case there are also fixed constants
    if hasattr(problem, '_constant_parameters') and hasattr(problem, '_constant_params'):
        for n, v in zip(problem._constant_parameters, problem._constant_params):
            s_name = str(n.name) if hasattr(n, 'name') else str(n)
            val = safe_get_value(v)
            if val is not None:
                v_dict[s_name] = val

    return v_dict


def solve_problem(problem: Any) -> Any:
    print("\n[4] Rebuilding equations and extracting exact physics...")
    builder = PolynomialMatrixBuilder(problem=problem, verbose=True)
    v_dict: dict = op_extraction(problem=problem)

    print("\n[*] Linearizing model with real parameters...")
    builder.linearize(v_dict=v_dict)
    res = builder.compute_stability()

    eigenvalues = res[0]
    stable = res[4]
    margin = res[5] if res[5] is not None else 0.0
    participation_matrix = res[3] if res[3] is not None else None

    print("\n" + "=" * 80)
    print("SMALL SIGNAL ANALYSIS COMPLETE - POLYNOMIAL BUILDER")
    print("=" * 80)
    print(f"  Found {len(eigenvalues)} finite eigenvalues")
    print(f"  System is stable: {stable}")
    print(f"  Stability margin: {margin:.4f}")
    print("=" * 80)

    # Extract the mapping using the class's corrected function
    pf_map: dict = builder.get_participation_mapping(eigenvalues, participation_matrix)

    print("\n" + "!" * 80)
    print("!!! UNSTABLE MODE ANALYSIS (Re > 0)")
    print("!" * 80)

    unstable_found = False
    for ev, participations in pf_map.items():
        # Strictly filter poles in the right half-plane
        if ev.real > 1e-6:
            unstable_found = True
            print(f"\n🚨 Critical mode: {ev.real:.4f} + {ev.imag:.4f}j")
            if not participations:
                print("  -> [!] No dominant physical variables (check structural patch)")
            for var_name, pf in participations:
                print(f"  -> {var_name}: {pf * 100:.1f}%")

    if not unstable_found:
        print("\n✅ The system is stable! There is no real part greater than 0.")

    return eigenvalues

if __name__ == "__main__":
    # problem = define_problem()
    grid_path = FAST_GRID_PATH if FAST_MODE else FULL_GRID_PATH
    print(f"[FAST_MODE={FAST_MODE}] Using grid: {grid_path}")
    problem = define_problem_with_path(grid_path)
    calculated_evs = []
    if problem:
        calculated_evs = solve_problem(problem)

    if not ENABLE_POST_COMPARE_PLOT:
        print("[FAST_MODE] Skipping eigenvalue reference matching and plotting")
        raise SystemExit(0)



    reference_evs = [complex(x) for x in
                     ["(-20.000000001+0j)", "(-10.000000001+0j)", "(-50.00000013636582+0j)", "(-49.9999998638391+0j)",
                      "(-12.168789431034414+0j)", "(-10.142655446318065+0j)", "(-6.854035294550814+0j)",
                      "(-5.029702766536969+0j)", "(-3.6156680497265823+0j)", "(0.7258649757244431+0j)",
                      "(-1.8851882786542178+0j)", "(-1.719135993985083+0.32085026247445086j)",
                      "(-1.7191359939850832-0.3208502624744508j)", "(-0.49201422052160765+0.8707873679911879j)",
                      "(-0.49201422052160765-0.870787367991188j)", "(-0.48381848641530006+0.465928959924564j)",
                      "(-0.48381848641530006-0.46592895992456396j)", "(-0.10000000099999705+0j)",
                      "(-0.11161483998140341+0j)", "(-0.9999999991690246+0j)", "(-1.0000000028309748+0j)",
                      "(-0.39635072300328184+0j)", "(-10.00000000099956+0j)", "(-1.0000000000000023e-09+0j)",
                      "(-9.999999999999996e-10+0j)", "(-9.999999999999992e-10+0j)"]]


    # --- MATCHING LOGIC (Hungarian Algorithm) ---
    finite_evs = calculated_evs[np.isfinite(calculated_evs) & (np.abs(calculated_evs) < 1e6)] if len(
        calculated_evs) > 0 else []

    tol = 0.06  # Tolerance to consider eigenvalues as matching
    matched_calc = []
    unmatched_calc = []
    unmatched_ref = list(reference_evs)

    if len(finite_evs) > 0 and len(reference_evs) > 0:
        # 1. Build distance (cost) matrix
        cost_matrix = np.zeros((len(finite_evs), len(reference_evs)))
        for i, c_ev in enumerate(finite_evs):
            for j, r_ev in enumerate(reference_evs):
                cost_matrix[i, j] = np.abs(c_ev - r_ev)

        # 2. Optimal assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        # 3. Filter by tolerance
        for i, j in zip(row_ind, col_ind):
            if cost_matrix[i, j] < tol:
                matched_calc.append(finite_evs[i])
                unmatched_ref[j] = None  # Mark as matched
            else:
                unmatched_calc.append(finite_evs[i])

        # 4. Clean unmatched lists
        unmatched_ref = [x for x in unmatched_ref if x is not None]

        # Add computed eigenvalues that were not assigned at all
        for i in range(len(finite_evs)):
            if i not in row_ind:
                unmatched_calc.append(finite_evs[i])
    else:
        unmatched_calc = list(finite_evs)

    n_matches = len(matched_calc)
    n_unmatched_calc = len(unmatched_calc)
    n_unmatched_ref = len(unmatched_ref)

    # --- PLOT: Create 1x2 figure ---
    # Use wider spacing and reserve more room for the scatter plot (2:1 ratio)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={'width_ratios': [2.5, 1]})

    # --- SUBPLOT 1: SCATTER (Original plot adapted to ax1) ---
    ax1.scatter(np.real(reference_evs), np.imag(reference_evs),
                color='gray', marker='x', alpha=0.5, label="Pablo's computation")

    if len(finite_evs) > 0:
        ax1.scatter(np.real(finite_evs), np.imag(finite_evs),
                    c=(np.real(finite_evs) > 1e-6), cmap='coolwarm',
                    marker='+', s=100, linewidths=2, label="TenSyGrid's computation")

    ax1.axvline(0, color='k', linestyle='--')
    ax1.axhline(0, color='k', alpha=0.3)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='lower left')

    # Note: Added 'r' prefix to avoid SyntaxWarning for '\R' and '\I'
    ax1.set_xlabel(r'$\Re({\lambda})$', fontsize=12)
    ax1.set_ylabel(r'$\Im({\lambda})$', fontsize=12)
    ax1.set_title("Eigenvalue comparison")

    # --- SUBPLOT 2: BARS AND RESULTS ---
    labels = ['Matching', 'Exceeding\n(TenSyGrid)', 'Missing\n(Pablo)']
    counts = [n_matches, n_unmatched_calc, n_unmatched_ref]
    colors = ['#4CAF50', '#F44336', '#FFC107']  # Green, Red, Yellow

    bars = ax2.bar(labels, counts, color=colors, edgecolor='black', alpha=0.8)
    ax2.set_title(f"Coincidence\n(Tolerance: {tol})")
    ax2.set_ylabel("Amount")

    # Add the number above each bar
    for bar in bars:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2, yval + 0.1, int(yval), ha='center', va='bottom', fontweight='bold')

    # Hide top and right spines for a cleaner bar chart
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig("scatter_and_bars.png", dpi=300, bbox_inches='tight')
    plt.show()

    # --- CONSOLE OUTPUT (So you can see the exact values) ---
    print("=== EIGENVALUE REPORT ===")
    print(f"Total computed (TenSyGrid): {len(finite_evs)}")
    print(f"Total reference (Pablo): {len(reference_evs)}")
    print("-" * 30)
    print(f"✅ Matches: {n_matches}")

    print(f"\n❌ EXTRA POLES (Computed by TenSyGrid, not in Pablo's reference): {n_unmatched_calc}")
    for ev in unmatched_calc:
        print(f"   {ev.real:.4f} + {ev.imag:.4f}j")


    print(f"\n⚠️ MISSING POLES (In Pablo's reference, not found by TenSyGrid): {n_unmatched_ref}")
    for ev in unmatched_ref:
        print(f"   {ev.real:.4f} + {ev.imag:.4f}j")
