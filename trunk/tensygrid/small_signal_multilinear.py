# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys
import pickle
import hashlib
from pathlib import Path

from matplotlib import pyplot as plt
import numpy as np

project_base = Path(__file__).resolve().parents[2]
src_path = project_base / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import VeraGridEngine.api as vge
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model


def ensure_unique_device_names(grid) -> None:
    def _rename(devices, prefix: str) -> None:
        seen: dict[str, int] = {}
        for i, dev in enumerate(devices):
            base = str(dev.name).strip() if getattr(dev, "name", None) else f"{prefix}_{i}"
            if base not in seen:
                seen[base] = 0
                dev.name = base
            else:
                seen[base] += 1
                dev.name = f"{base}_{seen[base]}"

    _rename(list(grid.generators), "gen")
    _rename(list(grid.lines), "line")
    _rename(list(grid.transformers2w), "trafo")
    _rename(list(grid.loads), "load")
    _rename(list(grid.shunts), "shunt")


def sanitize_runtime_parameter_names(grid) -> None:
    def _sanitize_block(block, tag: str) -> None:
        block.unify_blocks()
        all_syms = list(block.algebraic_vars) + list(block.state_vars) + list(block.diff_vars)
        all_syms += list(block.event_dict.keys()) + list(block.mode_dict.keys())
        seen: dict[str, int] = {}
        for k, sym in enumerate(all_syms):
            name = str(sym.name)
            if name not in seen:
                seen[name] = 0
                continue
            seen[name] += 1
            sym.name = f"{name}__{tag}_{seen[name]}_{k}"

    for i, dev in enumerate(grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True)):
        if not dev.rms_model.empty():
            _sanitize_block(dev.rms_model, f"br{i}")

    for i, dev in enumerate(grid.get_injection_devices_iter()):
        if not dev.rms_model.empty():
            _sanitize_block(dev.rms_model, f"inj{i}")


def _compare_eigen_sets(ref_eigs: np.ndarray, test_eigs: np.ndarray, tol: float = 1e-6) -> tuple[int, int, int, float]:
    if len(ref_eigs) == 0 or len(test_eigs) == 0:
        return 0, len(ref_eigs), len(test_eigs), float("nan")

    candidates: list[tuple[float, int, int]] = []
    for i, ev in enumerate(ref_eigs):
        d = np.abs(test_eigs - ev)
        valid = np.where(d <= tol)[0]
        for j in valid:
            candidates.append((float(d[j]), i, int(j)))

    candidates.sort(key=lambda t: t[0])

    used_ref: set[int] = set()
    used_test: set[int] = set()
    errs: list[float] = []
    for err, i, j in candidates:
        if i in used_ref or j in used_test:
            continue
        used_ref.add(i)
        used_test.add(j)
        errs.append(err)

    matches = len(errs)

    mean_err = float(np.mean(errs)) if errs else float("nan")
    return matches, len(ref_eigs) - matches, len(test_eigs) - matches, mean_err


def _compute_unmatched(ref_eigs: np.ndarray, test_eigs: np.ndarray, tol: float = 1e-6) -> tuple[list[tuple[complex, float]], list[tuple[complex, float]]]:
    if len(ref_eigs) == 0 or len(test_eigs) == 0:
        return [], []

    candidates: list[tuple[float, int, int]] = []
    for i, ev in enumerate(ref_eigs):
        d = np.abs(test_eigs - ev)
        for j, dist in enumerate(d):
            if dist <= tol:
                candidates.append((float(dist), i, j))

    candidates.sort(key=lambda t: t[0])
    used_ref: set[int] = set()
    used_test: set[int] = set()
    for _, i, j in candidates:
        if i in used_ref or j in used_test:
            continue
        used_ref.add(i)
        used_test.add(j)

    ref_unmatched: list[tuple[complex, float]] = []
    for i, ev in enumerate(ref_eigs):
        if i in used_ref:
            continue
        nearest = float(np.min(np.abs(test_eigs - ev)))
        ref_unmatched.append((complex(ev), nearest))

    test_unmatched: list[tuple[complex, float]] = []
    for j, ev in enumerate(test_eigs):
        if j in used_test:
            continue
        nearest = float(np.min(np.abs(ref_eigs - ev)))
        test_unmatched.append((complex(ev), nearest))

    ref_unmatched.sort(key=lambda x: x[1])
    test_unmatched.sort(key=lambda x: x[1])
    return ref_unmatched, test_unmatched


def _print_unmatched(ref_unmatched: list[tuple[complex, float]],
                     test_unmatched: list[tuple[complex, float]],
                     n_show: int = 8) -> None:
    print("Unmatched modes (nearest-neighbor distance)")
    print(f"  ML-only (showing up to {n_show})")
    for ev, dist in ref_unmatched[:n_show]:
        print(f"    ev={ev.real:+.9e}{ev.imag:+.9e}j  nearest={dist:.3e}")

    print(f"  Phasor-only (showing up to {n_show})")
    for ev, dist in test_unmatched[:n_show]:
        print(f"    ev={ev.real:+.9e}{ev.imag:+.9e}j  nearest={dist:.3e}")


def _plot_eigen_comparison(ml_eigs: np.ndarray, ph_eigs: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(np.real(ml_eigs), np.imag(ml_eigs), s=40, alpha=0.7, c="tab:blue", label="ML driver")
    ax.scatter(np.real(ph_eigs), np.imag(ph_eigs), s=40, alpha=0.7, c="tab:orange", marker="x", label="Phasor driver")
    ax.axvline(x=0.0, color="k", linestyle="--", linewidth=1)
    ax.set_xlabel("Real Part")
    ax.set_ylabel("Imaginary Part")
    ax.set_title("IEEE9 Eigenvalue Map (ML vs Phasor)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    plt.tight_layout()
    plt.show()


def build_problems(grid_filename: str) -> tuple[vge.RmsProblemMultilinear, vge.RmsProblemPhasor, vge.PowerFlowResults, vge.RmsOptions, vge.RmsOptions]:
    grid_path = project_base / "Grids_and_profiles" / "grids" / grid_filename
    grid = vge.open_file(str(grid_path))
    ensure_unique_device_names(grid)

    for bus in grid.buses:
        if bus.rms_model.empty():
            vge.initialize_bus_phasor_rms(bus, vf=grid.var_factory)

    for igen, gen in enumerate(grid.generators):
        if not gen.rms_model.empty():
            continue
        gen_mdl = vge.get_complete_generator_template_phasor(grid.var_factory, name=f"Gen{igen}").block
        grid.var_factory.add_connections([gen_mdl.in_vars[0]], [gen.bus.rms_model.out_vars[0]])
        grid.var_factory.add_connections([gen_mdl.in_vars[1]], [gen.bus.rms_model.out_vars[1]])
        gen_mdl = vge.to_implicit(gen_mdl, grid.var_factory)
        set_rms_model(device=gen, model=gen_mdl, var_factory=grid.var_factory)

    for line in grid.lines:
        if not line.rms_model.empty():
            continue
        line_mdl = vge.get_line_phasor_rms_template(grid.var_factory, name=line.name).block
        grid.var_factory.add_connections([line_mdl.in_vars[0]], [line.bus_from.rms_model.out_vars[0]])
        grid.var_factory.add_connections([line_mdl.in_vars[1]], [line.bus_from.rms_model.out_vars[1]])
        grid.var_factory.add_connections([line_mdl.in_vars[2]], [line.bus_to.rms_model.out_vars[0]])
        grid.var_factory.add_connections([line_mdl.in_vars[3]], [line.bus_to.rms_model.out_vars[1]])
        line_mdl = vge.to_implicit(line_mdl, grid.var_factory)
        set_rms_model(device=line, model=line_mdl, var_factory=grid.var_factory)

    for load in grid.loads:
        if not load.rms_model.empty():
            continue
        load_mdl = vge.get_load_phasor_current_rms_template(grid.var_factory, name=load.name).block
        grid.var_factory.add_connections([load_mdl.in_vars[0]], [load.bus.rms_model.out_vars[0]])
        grid.var_factory.add_connections([load_mdl.in_vars[1]], [load.bus.rms_model.out_vars[1]])
        set_rms_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    for trafo in grid.transformers2w:
        if not trafo.rms_model.empty():
            continue
        trafo_mdl = vge.initialize_trafo_rms(trafo, grid.var_factory, use_phasor_template=True).block
        grid.var_factory.add_connections([trafo_mdl.in_vars[0]], [trafo.bus_from.rms_model.out_vars[0]])
        grid.var_factory.add_connections([trafo_mdl.in_vars[1]], [trafo.bus_from.rms_model.out_vars[1]])
        grid.var_factory.add_connections([trafo_mdl.in_vars[2]], [trafo.bus_to.rms_model.out_vars[0]])
        grid.var_factory.add_connections([trafo_mdl.in_vars[3]], [trafo.bus_to.rms_model.out_vars[1]])
        trafo_mdl = vge.to_implicit(trafo_mdl, grid.var_factory)
        set_rms_model(device=trafo, model=trafo_mdl, var_factory=grid.var_factory)

    for shunt in grid.shunts:
        if not shunt.rms_model.empty():
            continue
        shunt_mdl = vge.get_shunt_template(grid.var_factory, name=shunt.name, phasor=True).block
        grid.var_factory.add_connections([shunt_mdl.in_vars[0]], [shunt.bus.rms_model.out_vars[0]])
        grid.var_factory.add_connections([shunt_mdl.in_vars[1]], [shunt.bus.rms_model.out_vars[1]])
        shunt_mdl = vge.to_implicit(shunt_mdl, grid.var_factory)
        set_rms_model(device=shunt, model=shunt_mdl, var_factory=grid.var_factory)

    pf_results = vge.power_flow(grid, vge.PowerFlowOptions(tolerance=1e-5))
    if not pf_results.converged:
        raise RuntimeError("Power flow did not converge")

    rms_options_ml = vge.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        tolerance=1e-6,
        max_iter=20,
        problem_type=vge.RmsProblemTypes.Multilinear,
    )
    rms_options_ph = vge.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        tolerance=1e-6,
        max_iter=20,
    )
    problem_ml = vge.RmsProblemMultilinear(grid=grid, options=rms_options_ml, pf_results=pf_results)
    problem_ph = vge.RmsProblemPhasor(grid=grid, options=rms_options_ph, pf_results=pf_results)
    return problem_ml, problem_ph, pf_results, rms_options_ml, rms_options_ph


def run_small_signal_from_driver(problem, pf_results: vge.PowerFlowResults, rms_options: vge.RmsOptions):
    ss_options = vge.RmsSmallSignalStabilityOptions(ss_assessment_time=0, verbose=0)
    driver = vge.SmallSignalStabilityRmsDriver(
        grid=vge.MultiCircuit(Sbase=problem.grid.Sbase),
        rms_options=rms_options,
        sss_options=ss_options,
        pf_results=pf_results,
    )
    driver.problem = problem
    driver.k = problem.get_states_number()
    driver.run()
    return driver.results.eigenvalues


def _hash_operating_point(x: np.ndarray) -> str:
    return hashlib.sha256(x.tobytes()).hexdigest()


def main() -> None:
    grid_filename = sys.argv[1] if len(sys.argv) > 1 else "IEEE 9 Bus.gridcal"
    problem_ml, problem_ph, pf_results, rms_options_ml, rms_options_ph = build_problems(grid_filename=grid_filename)
    x = problem_ml.get_x0()

    eig_driver_ml = run_small_signal_from_driver(problem=problem_ml,
                                                 pf_results=pf_results,
                                                 rms_options=rms_options_ml)
    eig_driver_ph = run_small_signal_from_driver(problem=problem_ph,
                                                 pf_results=pf_results,
                                                 rms_options=rms_options_ph)

    fin_drv_ml = eig_driver_ml[np.isfinite(eig_driver_ml) & (np.abs(eig_driver_ml) < 1e6)]
    fin_drv_ph = eig_driver_ph[np.isfinite(eig_driver_ph) & (np.abs(eig_driver_ph) < 1e6)]

    stable_ml = bool(np.all(np.real(fin_drv_ml) <= 0.0)) if len(fin_drv_ml) > 0 else False
    margin_ml = float(np.max(np.real(fin_drv_ml))) if len(fin_drv_ml) > 0 else float("nan")

    matches, ml_only, ph_only, mean_err = _compare_eigen_sets(fin_drv_ml, fin_drv_ph, tol=1e-6)
    ml_unmatched, ph_unmatched = _compute_unmatched(fin_drv_ml, fin_drv_ph, tol=1e-6)

    print(f"{grid_filename} small-signal (RmsProblemMultilinear)")
    print(f"  modes_driver_ml={len(fin_drv_ml)} stable_ml={stable_ml} margin_ml={margin_ml:.6e}")
    print(f"{grid_filename} small-signal (RmsProblemPhasor via driver)")
    print(f"  modes_driver_ph={len(fin_drv_ph)}")
    print("Driver eigen comparison (ML vs Phasor)")
    print(f"  matches={matches} ml_only={ml_only} ph_only={ph_only} mean_err={mean_err:.3e}")
    _print_unmatched(ml_unmatched, ph_unmatched, n_show=8)
    _plot_eigen_comparison(fin_drv_ml, fin_drv_ph)

    results = {
        'grid_name': grid_filename,
        'stable': stable_ml,
        'margin': margin_ml,
        'matches': matches,
        'op_hash': _hash_operating_point(x),
    }
    
    output_dir = Path('precomputed_builds')
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{Path(grid_filename).stem}_{results['op_hash'][:6]}.tensygrid"
    with open(output_path, 'wb') as f:
        pickle.dump(results, f)
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
