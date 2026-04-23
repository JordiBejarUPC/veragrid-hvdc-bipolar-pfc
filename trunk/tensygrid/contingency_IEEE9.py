# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Small Signal Analysis for Phasor-based RMS Grid.

This script creates the phasor problem manually and injects it into the SmallSignalStabilityRmsDriver.
"""

import sys
from pathlib import Path
import scienceplots


project_base = Path(__file__).resolve().parents[2]
src_path = project_base / "src"
if src_path.exists():
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
else:
    print(f"[ERROR] Engine not found: {src_path}")
    sys.exit(1)

import time, pickle, os
from typing import Tuple, Any, List
import numpy as np
from memory_profiler import profile, LineProfiler, show_results
# from cryptography.x509 import name
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
    check_shunt_pf_currents,
    print_buses_with_many_injections,
    print_bus_current_balance,
)
from scipy.optimize import linear_sum_assignment
plt.style.use(['science', 'ieee', 'no-latex'])
# GRID = "Texas 2000 + VSC"
# GRID = "IEEE 14.xlsx"
# GRID = "case_ACTIVSg2000.matpower"
"""GRIDS: 
    "IEEE 14.xlsx"
    "case_ACTIVSg2000.matpower"
    "Texas 2000 + VSC"
    "IEEE 118.xlsx"
"""
grid_folder = project_base / "Grids_and_profiles" / "grids"
GRID = "IEEE 9 Bus.gridcal"
USE_CACHED_BUILDER = False
BUILDER_CACHE_FILE = f'../trunk/tensygrid/precomputed_builds/{GRID}.pkl'

REPORT_TIME = False

FAST_MODE = False
LOGS = False
FULL_GRID_PATH = str(grid_folder / GRID)
FAST_GRID_PATH = FULL_GRID_PATH
PRINT_ALL_BUSES = LOGS
ENABLE_POST_COMPARE_PLOT = LOGS
RUN_DYNAMIC_STEP = False
RUN_CONSISTENCY_CHECK = False
RUN_PF_LINE_EQ_CHECK = False
RUN_EXCITER_DIAGNOSTICS = False
PF_LINE_FOCUS_INDEX = 0
DYNAMIC_SIM_TIME_FAST = 0.05
DYNAMIC_SIM_TIME_FULL = 0.20

EXEC_METRICS = {
    "n_vars": 0,
    "t_builder": 0.0,
    "t_solve": 0.0,
    "is_sparse": False,
    "stops": 0
}


def debug_input(input_bool):
    """
    Function to debug
    """
    EXEC_METRICS["stops"] = EXEC_METRICS["stops"] + 1
    if input_bool:
        input(f"Hola, ens quedem parats {EXEC_METRICS['stops']} vegades")
    else:
        print(f"Hola, ens quedem parats {EXEC_METRICS['stops']} vegades")


def define_problems_with_path(grid_path):
    """Creates the grid, runs the power flow, and returns the phasor problem."""
    print("\n[1] Creating phasor grid_path...")
    grid = vge.open_file(grid_path)

    # Build RMS models
    ## BUSES:
    for bus in grid.buses:
        busec = vge.initialize_bus_phasor_rms(bus, vf=grid.var_factory)

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

    ## -SHUNTS (load like):
    for shunt in grid.shunts:
        shuntec = vge.get_shunt_template(grid.var_factory, name=shunt.name, phasor=True).block
        shuntec.connect([shuntec.in_vars[0]], [shunt.bus.rms_model.out_vars[0]])
        shuntec.connect([shuntec.in_vars[1]], [shunt.bus.rms_model.out_vars[1]])
        shuntec = vge.to_implicit(shuntec, grid.var_factory)
        vge.set_rms_model(device=shunt, model=shuntec, var_factory=grid.var_factory)

    print("  ✓ Grid with path loaded")

    contingencies = [
        vge.Contingency(name="Fallo_Gen0", device=grid.generators[0]),
        vge.Contingency(name="Fallo_Gen1", device=grid.generators[1]),
        vge.Contingency(name="Fallo_Gen2", device=grid.generators[2])
    ]

    phasor_problems = []

    for ct in contingencies:
        print(f"\n" + "=" * 50)
        print(f"--- Evaluando contingencia: {ct.name} ---")
        print("=" * 50)

        target_device = ct.device
        original_state = target_device.active

        # Aplicamos la contingencia (desconectamos)
        target_device.active = False

        print("\n[2] Running power flow...")
        pf_options = vge.PowerFlowOptions(tolerance=1e-5)
        pf_results = vge.power_flow(grid, pf_options)

        if pf_results.converged:
            print(f"  ✓ Power flow converged")

            print("\n[3] Creating phasor problem...")
            rms_options = vge.RmsOptions(
                time_step=0.01,
                simulation_time=1.0,
                tolerance=1e-6,
                max_iter=20,
                verbose=False,
            )

            phasor_problem = vge.RmsProblemPhasor(grid=grid, options=rms_options, pf_results=pf_results)
            print(f"  ✓ Phasor problem created with {phasor_problem.get_states_number()} states")

            # CORRECT APPEND: Appends the tuple containing the problem AND the name
            phasor_problems.append((phasor_problem, ct.name))
        else:
            print(f"  ✗ Power flow failed para {ct.name}. El sistema colapsa en régimen permanente.")

        # --- FUNDAMENTAL: RESTAURAR EL SISTEMA ---
        target_device.active = original_state

    # Return the correctly formatted list of tuples
    return phasor_problems



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


def solve_problem(problem: Any = None) -> Any:
    builder = None

    print("\n[4] Rebuilding equations and extracting exact physics...")
    builder = PolynomialMatrixBuilder(problem=problem, verbose=True)
    v_dict: dict = op_extraction(problem=problem)

    print("\n[*] Linearizing model with real parameters...")
    builder.linearize(v_dict=v_dict)


    # Continue with the normal stability analysis
    # Use automatic routing: sparse for large systems, dense fallback otherwise.
    res = builder.compute_stability()

    eigenvalues = res[0]
    print(eigenvalues)
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


def plot_eigenvalues(eigenvalue_dict: dict):
    """
    Plots a scatter plot of eigenvalues for multiple scenarios.
    """
    print("\n[5] Generating Eigenvalue Scatter Plot...")
    plt.figure(figsize=(10, 8))

    markers = ['o', 's', '^', 'D', 'v', 'p', '*']
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple']

    for i, (name, evs) in enumerate(eigenvalue_dict.items()):
        if evs is None or len(evs) == 0:
            continue

        # Extract real and imaginary parts
        reals = np.real(evs)
        imags = np.imag(evs)
        mask_stable = reals <= 0
        plt.scatter(reals[mask_stable], imags[mask_stable],
                    marker=markers[i % len(markers)],
                    color="green",
                    label=name,
                    alpha=0.7,
                    s=60)
        mask_unstable = reals > 0
        plt.scatter(reals[mask_unstable], imags[mask_unstable],
                    marker=markers[i % len(markers)],
                    color="red",
                    label=f"{name} (Unstable)",
                    alpha=0.7,
                    s=60)

    # Draw axes lines
    plt.axvline(x=0, color='red', linestyle='--', linewidth=1.5, label='Stability Limit')
    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.8)

    # Plot formatting
    plt.title("Small Signal Stability - Eigenvalues Map", fontsize=14)
    plt.xlabel("Real Part (Neper/s)", fontsize=12)
    plt.ylabel("Imaginary Part (Rad/s)", fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.legend(loc='best', fontsize=10)
    plt.tight_layout()

    # Show plot
    plt.show()


def main():
    # --- START CHRONO ---
    start_time = time.perf_counter()

    grid_path = FAST_GRID_PATH if FAST_MODE else FULL_GRID_PATH
    print(f"[FAST_MODE={FAST_MODE}] Using grid: {grid_path}")

    # Dictionary to store eigenvalues linked to their contingency names
    all_eigenvalues = {}

    problems_with_names = define_problems_with_path(grid_path)

    if problems_with_names:
        # Unpack the problem and its name
        for problem, ct_name in problems_with_names:
            print(f"\n>>> Solving Small Signal for: {ct_name}")

            # solve_problem returns the eigenvalues array
            eigenvalues = solve_problem(problem)

            # Save them into the dictionary
            all_eigenvalues[ct_name] = eigenvalues

    # --- END CHRONO ---
    end_time = time.perf_counter()
    total_duration = end_time - start_time

    print(f"\n========================================")
    print(f"EXECUTION TIME: {total_duration:.4f} seconds")
    print(f"========================================")

    # Finally, plot the eigenvalues if we collected any
    if all_eigenvalues:
        plot_eigenvalues(all_eigenvalues)


if __name__ == "__main__":
    try:
        if REPORT_TIME:
            lp = LineProfiler()
            lp.add_function(main)
            lp.add_function(solve_problem)
            lp.add_function(define_problems_with_path)
            lp(main)()
        else:
            main()
    except SystemExit:
        print("Error during execution")
    finally:
        if REPORT_TIME:
            print("\n" + "=" * 80)
            print("      DETAILED MEMORY PROFILE REPORT (VeraGrid Analysis)")
            print("=" * 80)
            show_results(lp)
            print(
                f"N_variables: {EXEC_METRICS['n_vars']}, "
                f"exec_time_builder: {EXEC_METRICS['t_builder']:.4f} sec, "
                f"exec_time_solve: {EXEC_METRICS['t_solve']:.4f} sec, "
                f"sparse: {EXEC_METRICS['is_sparse']}"
            )
