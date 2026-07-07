#!/usr/bin/env python3
"""
Script per calcular contingències de xarxa elèctrica.
Desactiva un element (generator/line/load) i recalcula l'estabilitat.
No desa resultats a disc (és temporal).
"""

import sys
import json
import copy
import argparse
import numpy as np
from pathlib import Path
import os

# Redirigir stdout a stderr per evitar contaminació de DEBUG messages
_real_stdout = sys.stdout
sys.stdout = sys.stderr

# Afegir el path del projecte
project_base = Path(__file__).resolve().parents[2]
src_path = project_base / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import VeraGridEngine.api as vge
from small_signal_multilinear import build_problems, run_small_signal_from_driver


def create_contingency_problem(base_problem, element_to_trip):
    """
    Creates a new problem representing a contingency by modifying the Phi matrix
    of a base problem, rather than rebuilding the model from scratch.

    This is much faster than re-parsing and re-building for each case.

    Args:
        base_problem: The fully-built RmsProblemMultilinear for the base case.
        element_to_trip: The grid device object (e.g., a generator or line) to be tripped.

    Returns:
        A new RmsProblemMultilinear instance representing the contingency.
    """
    # 1. Create a copy of the problem to avoid modifying the original.
    contingency_problem = copy.copy(base_problem)  # Shallow copy is enough
    contingency_problem.grid = copy.deepcopy(base_problem.grid)  # Deepcopy grid state

    # Find the corresponding element in the *newly copied* grid and deactivate it there.
    # This is critical to avoid modifying the original `base_problem`'s grid state.
    contingent_element = contingency_problem.grid.get_device_by_id(element_to_trip.idtag)
    if contingent_element:
        contingent_element.active = False
    else:
        # This case should ideally not be reached if deepcopy is successful.
        raise RuntimeError(f"Failed to find element {element_to_trip.idtag} in the copied grid for contingency.")

    # 2. Get the live matrices and maps from the new problem.
    # We will modify a copy of the Phi matrix.
    phi = base_problem._phi.copy().tolil()  # Use LIL format for efficient row-wise changes
    all_vars_map = base_problem._all_vars_map
    all_eqs_map = base_problem._all_eqs_map
    monomial_map = base_problem._monomial_map

    # 3. Identify the algebraic variables that should be forced to zero.
    vars_to_zero = []
    model = element_to_trip.rms_model
    if isinstance(element_to_trip, vge.Generator):
        # A tripped generator has zero output current.
        # These variables are part of the generator's internal model.
        if 'Ir' in model.vars: vars_to_zero.append(str(model.vars['Ir']))
        if 'Ii' in model.vars: vars_to_zero.append(str(model.vars['Ii']))
    elif isinstance(element_to_trip, vge.Line):
        # A tripped line has zero current flow.
        if 'Irf' in model.vars: vars_to_zero.append(str(model.vars['Irf']))
        if 'Iif' in model.vars: vars_to_zero.append(str(model.vars['Iif']))
        if 'Irt' in model.vars: vars_to_zero.append(str(model.vars['Irt']))
        if 'Iit' in model.vars: vars_to_zero.append(str(model.vars['Iit']))

    if not vars_to_zero:
        raise NotImplementedError(f"Contingency logic for device type {type(element_to_trip)} is not implemented.")

    # 4. For each variable, transform its defining equation to `var = 0`.
    for var_name in vars_to_zero:
        # Find the symbolic equation that defines this variable.
        # This relies on the convention that each algebraic variable has one
        # clear defining equation of the form `var - expression = 0`.
        var_sym = model.vars[var_name.split('_')[-1]]  # Get the symbolic object
        defining_eq_sym = None
        for eq in model.algebraic_eqs:
            if eq.has(var_sym):
                # A simple check: does it look like `var - ...`?
                if isinstance(eq, vge.BinOp) and eq.op == '-' and str(eq.a) == str(var_sym):
                    defining_eq_sym = eq
                    break

        if defining_eq_sym is None:
            print(f"Warning: Could not find a simple defining equation for '{var_name}'. Skipping transformation.",
                  file=sys.stderr)
            continue

        # Get the index of this equation in the global DAE system.
        # This is the key step that requires the `_all_eqs_map`.
        if defining_eq_sym not in all_eqs_map:
            print(f"Warning: Equation '{defining_eq_sym}' for '{var_name}' not in map. Skipping.", file=sys.stderr)
            continue
        eq_idx = all_eqs_map[defining_eq_sym]

        # Get the index of the monomial for the single variable `var_name`.
        # The monomial for a single variable `v` is `((v_idx, 1.0),)`.
        var_idx = all_vars_map[var_name]
        var_monomial = ((var_idx, 1.0),)
        if var_monomial not in monomial_map:
            print(f"Warning: Monomial for '{var_name}' not in map. Skipping.", file=sys.stderr)
            continue
        monomial_idx = monomial_map[var_monomial]

        # --- Perform the Matrix Surgery ---
        # a. Zero out the entire row in Phi, erasing the original equation.
        phi[eq_idx, :] = 0.0
        # b. Set the coefficient for the `var_name` monomial to 1.0.
        phi[eq_idx, monomial_idx] = 1.0
        # The equation at this row is now effectively `var_name = 0`.

    # 5. Assign the modified Phi matrix to the new problem object.
    contingency_problem._phi = phi.tocsc()  # Convert back to CSC format for performance

    return contingency_problem


def main():
    parser = argparse.ArgumentParser(description='Compute network contingencies')
    parser.add_argument('--grid', required=True, help='Nom del fitxer de xarxa')
    parser.add_argument('--type', required=True, choices=['generator', 'line', 'transformer'],
                        help='Element type to disconnect')
    parser.add_argument('--element', required=True, help='Element index (e.g., gen_0, line_2)')

    args = parser.parse_args()

    try:
        # Carregar la xarxa des de disc
        # --- New Workflow: Build the base problem ONCE ---
        print(f"Building base case problem for {args.grid}...", file=sys.stderr)
        base_problem_ml, _, base_pf_results, base_rms_options_ml, _ = build_problems(
            grid_filename=args.grid,
        )
        print("Base case built. Starting contingency analysis.", file=sys.stderr)

        # --- Identify the element to trip from the base grid ---
        element_idx = int(args.element.split("_")[1])
        element_map = {
            "generator": list(base_problem_ml.grid.generators),
            "line": list(base_problem_ml.grid.lines),
            "load": list(base_problem_ml.grid.loads),
            "transformer": list(base_problem_ml.grid.transformers2w),
        }

        if args.type not in element_map:
            raise ValueError(f"Invalid element type: {args.type}")

        elements = element_map[args.type]
        if not (0 <= element_idx < len(elements)):
            raise ValueError(f"{args.type.capitalize()} index {element_idx} out of range ({len(elements)} elements)")

        element_to_trip = elements[element_idx]
        print(f"Identified contingency: Trip {args.type} '{element_to_trip.name}'", file=sys.stderr)

        # --- Create the contingency problem by modifying the base matrices ---
        print("Creating contingency problem via matrix surgery...", file=sys.stderr)
        problem_ml = create_contingency_problem(base_problem_ml, element_to_trip)

        # The power flow of the base case is no longer valid for the post-contingency state.
        # We must re-solve the power flow for the new topology.
        print("Re-solving power flow for N-1 topology...", file=sys.stderr)
        pf_results = vge.PowerFlow.calculate(problem_ml.grid)

        # Use the options from the base build
        rms_options_ml = base_rms_options_ml

        # --- Run the analysis on the modified problem ---
        print("Running small-signal analysis on contingency problem...", file=sys.stderr)
        eig_driver_ml, _, state_var_names_ml = run_small_signal_from_driver(
            problem=problem_ml,
            pf_results=pf_results,
            rms_options=rms_options_ml
        )

        # Filtrar eigenvalues vàlids
        fin_drv_ml = eig_driver_ml[np.isfinite(eig_driver_ml) & (np.abs(eig_driver_ml) < 1e6)]

        # Calcular estabilitat
        stable_ml = bool(np.all(np.real(fin_drv_ml) <= 0.0)) if len(fin_drv_ml) > 0 else False
        margin_ml = float(np.max(np.real(fin_drv_ml))) if len(fin_drv_ml) > 0 else float("nan")

        # Convertir eigenvalues a llista
        eigenvalues_list = [
            {"re": float(np.real(ev)), "im": float(np.imag(ev))}
            for ev in fin_drv_ml
        ]

        # Funcions auxiliars
        def _damping(re, im):
            mag = np.sqrt(re * re + im * im)
            return -re / mag if mag > 1e-12 else 0.0

        def _freq_hz(im):
            return abs(im) / (2 * np.pi)

        # Calcular modes crítics (sense participation factors)
        critical_modes = []
        for i, ev in enumerate(fin_drv_ml):
            re, im = float(np.real(ev)), float(np.imag(ev))
            if abs(im) > 0.1:
                damping = float(_damping(re, im))
                critical_modes.append({
                    "mode": i,
                    "re": re,
                    "im": im,
                    "damping": damping,
                    "freq_hz": float(_freq_hz(im)),
                    "critical": bool(abs(damping) < 0.05),
                })
        critical_modes.sort(key=lambda m: m["damping"])

        # Preparar resultat
        result = {
            "grid_name": args.grid,
            "stable": stable_ml,
            "margin": margin_ml,
            "n_eigenvalues": len(fin_drv_ml),
            "n_state_vars": len(problem_ml.get_x0()),
            "eigenvalues": eigenvalues_list,
            "critical_modes": critical_modes[:10],
            "grid_info": {
                "n_buses": len(list(problem_ml.grid.buses)),
                "n_generators": len([g for g in problem_ml.grid.generators if g.active]),
                "n_lines": len([l for l in problem_ml.grid.lines if l.active]),
                "n_loads": len([l for l in problem_ml.grid.loads if l.active]),
                "n_transformers": len(list(problem_ml.grid.transformers2w)),
            },
        }

        # Determinar status
        if result["stable"]:
            result["status"] = "STABLE"
        elif result["margin"] < 0.001:
            result["status"] = "MARGINAL"
        else:
            result["status"] = "UNSTABLE"

        # Restaurar stdout i imprimir JSON
        sys.stdout = _real_stdout
        print(json.dumps(result))

    except Exception as e:
        sys.stdout = _real_stdout
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
