#!/usr/bin/env python3
"""
Script per calcular contingències de xarxa elèctrica.
Desactiva un element (generator/line/load) i recalcula l'estabilitat.
No desa resultats a disc (és temporal).
"""

import sys
import json
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


def main():
    parser = argparse.ArgumentParser(description='Calcula contingències de xarxa')
    parser.add_argument('--grid', required=True, help='Nom del fitxer de xarxa')
    parser.add_argument('--type', required=True, choices=['generator', 'line', 'load'],
                       help='Tipus d\'element a desconnectar')
    parser.add_argument('--element', required=True, help='Índex de l\'element (ex: gen_0, line_2)')
    
    args = parser.parse_args()
    
    try:
        # Carregar la xarxa
        problem_ml, problem_ph, pf_results, rms_options_ml, rms_options_ph = build_problems(
            grid_filename=args.grid
        )
        
        # Extreure l'índex de l'element
        element_idx = int(args.element.split("_")[1])
        
        # Desactivar l'element especificat
        if args.type == "generator":
            gens = list(problem_ml.grid.generators)
            if element_idx < len(gens):
                gens[element_idx].active = False
        elif args.type == "line":
            lines = list(problem_ml.grid.lines)
            if element_idx < len(lines):
                lines[element_idx].active = False
        elif args.type == "load":
            loads = list(problem_ml.grid.loads)
            if element_idx < len(loads):
                loads[element_idx].active = False
        
        # Recalcular power flow
        pf_results = vge.power_flow(problem_ml.grid, vge.PowerFlowOptions(tolerance=1e-5))
        if not pf_results.converged:
            raise RuntimeError("Power flow did not converge after contingency")
        
        # Calcular eigenvalues (desempaquetar correctament la tupla de 3)
        eig_driver_ml, pf_ml, state_var_names_ml = run_small_signal_from_driver(
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
