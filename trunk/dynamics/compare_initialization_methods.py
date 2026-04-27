import argparse
import contextlib
import io
import os
import sys
from typing import Dict, List

import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
import VeraGridEngine.Simulations.Rms.problems.rms_problem_dae as dae_mod
import VeraGridEngine.Simulations.Rms.initialization as init_mod
from trunk.dynamics.scripting_pseudo_transient import build_grid


def build_problem(init_method: gce.RmsInitializationMethod, silent: bool) -> RmsProblemDae:
    grid = build_grid()

    pf_options = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        distributed_slack=False,
    )
    pf_results = gce.power_flow(grid, options=pf_options)

    rms_options = gce.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        integration_method=gce.DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=init_method,
        max_iter=1000,
        tolerance=1e-8,
        verbose=0,
    )

    if silent:
        with contextlib.redirect_stdout(io.StringIO()):
            problem = RmsProblemDae(grid=grid, options=rms_options, pf_results=pf_results)
            problem.set_events_group(grid.rms_events_groups[0])
    else:
        problem = RmsProblemDae(grid=grid, options=rms_options, pf_results=pf_results)
        problem.set_events_group(grid.rms_events_groups[0])

    return problem


def build_pseudo_problem_with_tol_override(silent: bool, tol_override: float | None) -> RmsProblemDae:
    orig = dae_mod.init_pseudo_transient
    try:
        if tol_override is not None:
            def patched_init_pseudo_transient(*p_args, **p_kwargs):
                p_kwargs["tol"] = float(tol_override)
                return init_mod.init_pseudo_transient(*p_args, **p_kwargs)

            dae_mod.init_pseudo_transient = patched_init_pseudo_transient

        return build_problem(gce.RmsInitializationMethod.PseudoTransient, silent=silent)
    finally:
        dae_mod.init_pseudo_transient = orig


def get_residual(problem: RmsProblemDae) -> tuple[np.ndarray, np.ndarray, float]:
    x0 = problem.get_x0()
    dx0 = np.zeros(problem.get_diff_var_number(), dtype=float)
    residual = np.r_[problem.rhs_state(x0, dx0), problem.rhs_algebraic(x0, dx0)]
    return x0, residual, float(np.linalg.norm(residual, np.inf))


def top_residual_lines(problem: RmsProblemDae, residual: np.ndarray, top_k: int) -> List[str]:
    idx = np.argsort(np.abs(residual))[::-1][:top_k]
    n_states = len(problem._state_vars)
    lines: List[str] = []
    for i in idx:
        val = float(residual[i])
        if i < n_states:
            name = problem._state_vars[i].name
            lines.append(f"state {name}: {val:.6e}")
        else:
            j = i - n_states
            name = problem._algebraic_vars[j].name
            lines.append(f"alg {name}: {val:.6e}")
    return lines


def values_by_name(problem: RmsProblemDae, x0: np.ndarray) -> Dict[str, List[float]]:
    result: Dict[str, List[float]] = {}
    all_vars = list(problem._state_vars) + list(problem._algebraic_vars)
    for i, var in enumerate(all_vars):
        result.setdefault(var.name, []).append(float(x0[i]))
    return result


def event_values_by_name(problem: RmsProblemDae, names: List[str]) -> Dict[str, List[float]]:
    result: Dict[str, List[float]] = {name: [] for name in names}
    for i, var in enumerate(problem._variable_parameters):
        if var.name in result:
            result[var.name].append(float(problem._variable_parameters_values[i]))
    return result


def print_selected_diffs(
    selected_names: List[str],
    explicit_values: Dict[str, List[float]],
    pseudo_values: Dict[str, List[float]],
) -> None:
    for name in selected_names:
        ex = explicit_values.get(name, [])
        ps = pseudo_values.get(name, [])
        if not ex and not ps:
            continue
        m = min(len(ex), len(ps))
        if m == 0:
            print(f"- {name}: explicit={ex} pseudo={ps}")
            continue
        for i in range(m):
            d = abs(ex[i] - ps[i])
            print(f"- {name}[{i}]: explicit={ex[i]:.6e}, pseudo={ps[i]:.6e}, diff={d:.6e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare RMS Explicit vs PseudoTransient initialization")
    parser.add_argument("--top", type=int, default=10, help="number of largest residual entries to print")
    parser.add_argument(
        "--pseudo-tol-override",
        type=float,
        default=None,
        help="override pseudo-transient internal residual check (e.g. 1.0) to force problem build for comparison",
    )
    parser.add_argument("--verbose-build", action="store_true", help="show raw initialization prints")
    args = parser.parse_args()

    silent = not args.verbose_build

    explicit_error = None
    explicit = None
    x_exp = None
    r_exp = None
    r_exp_inf = None

    pseudo_error = None
    pseudo = None
    x_ps = None
    r_ps = None
    r_ps_inf = None

    pseudo_diag_error = None
    pseudo_diag = None
    x_ps_diag = None
    r_ps_diag = None
    r_ps_diag_inf = None

    try:
        explicit = build_problem(gce.RmsInitializationMethod.Explicit, silent=silent)
        x_exp, r_exp, r_exp_inf = get_residual(explicit)
    except Exception as e:
        explicit_error = str(e)

    try:
        pseudo = build_pseudo_problem_with_tol_override(silent=silent, tol_override=args.pseudo_tol_override)
        x_ps, r_ps, r_ps_inf = get_residual(pseudo)
    except Exception as e:
        pseudo_error = str(e)

    # Always print pseudo-transient run details even when strict pseudo init fails.
    # If no override was provided and strict run fails, do a diagnostic pseudo run.
    if pseudo_error is not None and args.pseudo_tol_override is None:
        try:
            pseudo_diag = build_pseudo_problem_with_tol_override(silent=silent, tol_override=1.0)
            x_ps_diag, r_ps_diag, r_ps_diag_inf = get_residual(pseudo_diag)
        except Exception as e:
            pseudo_diag_error = str(e)

    print("Residual infinity norms")
    if explicit_error is not None:
        print(f"- explicit: <failed> {explicit_error}")
    else:
        assert r_exp_inf is not None
        print(f"- explicit: {r_exp_inf:.6e}")
    if pseudo_error is not None:
        print(f"- pseudo:   <failed> {pseudo_error}")
    else:
        assert r_ps_inf is not None
        print(f"- pseudo:   {r_ps_inf:.6e}")

    if explicit_error is None:
        assert explicit is not None and r_exp is not None
        print("\nTop explicit residual entries")
        for line in top_residual_lines(explicit, r_exp, args.top):
            print(f"- {line}")

    if pseudo_error is None:
        assert pseudo is not None and r_ps is not None and x_ps is not None
        print("\nTop pseudo residual entries")
        for line in top_residual_lines(pseudo, r_ps, args.top):
            print(f"- {line}")

    if pseudo_error is not None and r_ps_diag is not None:
        assert pseudo_diag is not None and x_ps_diag is not None and r_ps_diag_inf is not None
        print("\nPseudo-transient diagnostic run (tol override = 1.0)")
        print(f"- residual_inf: {r_ps_diag_inf:.6e}")
        print("- top residual entries")
        for line in top_residual_lines(pseudo_diag, r_ps_diag, args.top):
            print(f"  - {line}")

    if pseudo_error is not None and r_ps_diag is None and pseudo_diag_error is not None:
        print("\nPseudo-transient diagnostic run (tol override = 1.0)")
        print(f"- <failed> {pseudo_diag_error}")

    if explicit_error is None and pseudo_error is None:
        assert explicit is not None and x_exp is not None and pseudo is not None and x_ps is not None
        selected = ["Pm_ref", "UsRefPu", "Tm", "Vf", "Efe"]
        exp_vals = values_by_name(explicit, x_exp)
        ps_vals = values_by_name(pseudo, x_ps)

        print("\nSelected variable values")
        print_selected_diffs(selected, exp_vals, ps_vals)

        exp_evt = event_values_by_name(explicit, ["Pm_ref", "UsRefPu"])
        ps_evt = event_values_by_name(pseudo, ["Pm_ref", "UsRefPu"])
        print("\nEvent parameter values")
        print_selected_diffs(["Pm_ref", "UsRefPu"], exp_evt, ps_evt)

    if explicit_error is None and pseudo_error is not None and r_ps_diag is not None:
        assert explicit is not None and x_exp is not None and pseudo_diag is not None and x_ps_diag is not None
        selected = ["Pm_ref", "UsRefPu", "Tm", "Vf", "Efe"]
        exp_vals = values_by_name(explicit, x_exp)
        ps_vals = values_by_name(pseudo_diag, x_ps_diag)
        print("\nSelected variable values (explicit vs pseudo diagnostic)")
        print_selected_diffs(selected, exp_vals, ps_vals)

        exp_evt = event_values_by_name(explicit, ["Pm_ref", "UsRefPu"])
        ps_evt = event_values_by_name(pseudo_diag, ["Pm_ref", "UsRefPu"])
        print("\nEvent parameter values (explicit vs pseudo diagnostic)")
        print_selected_diffs(["Pm_ref", "UsRefPu"], exp_evt, ps_evt)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
