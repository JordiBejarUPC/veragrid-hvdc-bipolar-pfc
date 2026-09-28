# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
End-to-end check that the Candidate Investments Generator produces investments that actually
help: load IEEE39_1month_Jan19, run a time series power flow, generate and add candidate
investments, extract the critical snapshot into its own grid file, run Investments Evaluation
(PowerFlow objective) on that snapshot, and report the resulting Pareto front plus the
overloaded branches before/after the investments.
"""
import os
from typing import List

import numpy as np
from matplotlib import pyplot as plt

import VeraGridEngine.api as gce
import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Simulations.InvestmentsEvaluation.CandidateGeneration.candidate_generation_driver import (
    CandidateGenerationDriver,
)
from VeraGridEngine.Simulations.InvestmentsEvaluation.CandidateGeneration.candidate_generation_options import (
    CandidateGenerationOptions,
)
from VeraGridEngine.Simulations.InvestmentsEvaluation.investments_evaluation_driver import (
    InvestmentsEvaluationDriver,
)
from VeraGridEngine.Simulations.InvestmentsEvaluation.Problems.power_flow_problem import (
    PowerFlowInvestmentProblem,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GRID_PATH = os.path.join(SCRIPT_DIR, '..', '..', '..', 'Grids_and_profiles', 'grids',
                         'IEEE39_1month_Jan19.veragrid')
SNAPSHOT_PATH = os.path.join(SCRIPT_DIR, 'IEEE39_critical_snapshot.veragrid')

CORRIDORS_PER_VIOLATION = 10 # 25 # 5
CANDIDATES_TO_VERIFY = 30 # 15 # 1
OVERLOAD_THRESHOLD = 1.0


def build_pf_options() -> gce.PowerFlowOptions:
    """
    Power flow options matching check_ts_convergence.py: NR, tolerance 1e-5, 40 iterations,
    single-node islands ignored, every other toggle off.
    """
    return gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=False,
        tolerance=1e-5,
        max_iter=40,
        limit_i_vsc=False,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=False,
        apply_temperature_correction=False,
        distributed_slack=False,
        ignore_single_node_islands=True,
        use_stored_guess=False,
        initialize_angles=False,
        use_autodiff_jacobian=False,
        generate_report=False,
    )


def list_overloaded_branches(grid: gce.MultiCircuit,
                             pf_options: gce.PowerFlowOptions,
                             threshold: float,
                             label: str) -> None:
    """
    Run a single-snapshot AC power flow and print every branch loaded above threshold.
    """
    driver = gce.PowerFlowDriver(grid=grid, options=pf_options)
    driver.run()

    print(f"\n{label} (converged: {'yes' if driver.results.converged else 'no'})")
    loading = np.abs(driver.results.loading)
    names = driver.results.branch_names
    overloaded = np.where(loading > threshold)[0]
    if len(overloaded) == 0:
        print("  No overloaded branches.")
    else:
        for i in overloaded:
            print(f"  {names[i]}: {loading[i] * 100.0:.1f}%")


def main() -> None:
    """
    Run the full candidate-investments-generator success check and display its results.
    """
    grid = gce.FileOpen(GRID_PATH).open()
    pf_options = build_pf_options()

    # --- Step 2: time series power flow (sanity check, same parameters as check_ts_convergence) ---
    print("=== Step 2: time series power flow ===")
    ts_results = gce.power_flow_ts(grid=grid, options=pf_options)
    converged = np.asarray(ts_results.converged_values, dtype=bool)
    print(f"Converged: {int(converged.sum())}/{len(converged)} "
         f"({100.0 * converged.mean():.2f}%)")

    # --- Step 3: candidate investments generator ---
    print("\n=== Step 3: candidate investments generator ===")
    time_indices = grid.get_all_time_indices()
    gen_options = CandidateGenerationOptions(top_n_corridors=CORRIDORS_PER_VIOLATION,
                                             verify_top_k=CANDIDATES_TO_VERIFY,
                                             use_time_series=True,
                                             time_indices=time_indices)
    gen_driver = CandidateGenerationDriver(grid=grid, options=gen_options, pf_options=pf_options)
    gen_driver.run()
    gen_results = gen_driver.results
    print(gen_results.summary_text())

    critical_t_idx = gen_results.critical_time_idx
    if critical_t_idx is None:
        raise RuntimeError("Candidate generator did not run in time-series mode; aborting.")

    # Line/upgrade, injection (static generator/battery) and voltage-relief (shunt reactor)
    # candidates are three independently ranked/verified tracks - combine all three here so
    # static-gen/battery/shunt-reactor investments actually get materialised, not just generated.
    verified = (gen_results.verified_candidates + gen_results.verified_injection_candidates
               + gen_results.verified_voltage_candidates)
    print(f"\nVerified candidates: {len(verified)} "
         f"({len(gen_results.verified_candidates)} line/upgrade, "
         f"{len(gen_results.verified_injection_candidates)} injection (static gen/battery), "
         f"{len(gen_results.verified_voltage_candidates)} voltage-relief)")
    if len(verified) == 0:
        print("No verified candidates were produced; nothing to evaluate.")
        return

    # "Add investments": materialise every verified candidate in its own investments group.
    logger = Logger()
    for candidate in verified:
        group = dev.InvestmentsGroup(idtag=None, name=candidate.group_name(), category="single")
        grid.add_investments_group(group)
        candidate.apply(circuit=grid, group=group, logger=logger)
    if logger.has_logs():
        print(logger)

    print("\n=== Investments generated ===")
    for inv in grid.investments:
        print(f"  {inv.name} | group: {inv.group.name} | CAPEX: {inv.CAPEX:.2f} | status: {inv.status}")

    # --- Extract the critical snapshot (with the investments now on the grid) into its own file ---
    print("\n=== Extracting the critical snapshot ===")
    snapshot_grid = grid.copy()
    snapshot_grid.set_state(critical_t_idx)
    snapshot_grid.delete_profiles()
    gce.FileSave(snapshot_grid, SNAPSHOT_PATH).save()
    print(f"Saved: {SNAPSHOT_PATH}")

    # --- Step 4: investments evaluation on the snapshot, PowerFlow objective ---
    print("\n=== Step 4: investments evaluation (PowerFlow objective) ===")
    problem = PowerFlowInvestmentProblem(grid=snapshot_grid, pf_options=pf_options)
    n_groups = len(snapshot_grid.investments_groups)
    eval_options = gce.InvestmentsEvaluationOptions(
        max_eval=50 * n_groups,
        pf_options=pf_options,
        solver=gce.InvestmentEvaluationMethod.NSGA3,
        obj_tpe=gce.InvestmentsEvaluationObjectives.PowerFlow,
    )
    eval_driver = InvestmentsEvaluationDriver(grid=snapshot_grid, options=eval_options, problem=problem)
    eval_driver.run()
    eval_results = eval_driver.results

    # --- Step 5: display the plot: pareto front in green, pre-investment point in red ---
    f_names = eval_results.f_names
    x_idx = problem.plot_x_idx  # financial score
    y_idx = problem.plot_y_idx  # technical score
    f = eval_results.f

    # objective_function(x=zeros) is always evaluated first, so row 0 is "before investments".
    baseline_f = f[0, :]
    pareto_idx = [i for i in eval_results.sorting_indices if i != 0]
    non_pareto_idx = [i for i in range(f.shape[0]) if i != 0 and i not in set(eval_results.sorting_indices)]

    plt.figure(figsize=(8, 6))
    plt.scatter(f[non_pareto_idx, x_idx], f[non_pareto_idx, y_idx],
               color='lightgreen', label='Dominated evaluations', zorder=2)
    plt.scatter(f[pareto_idx, x_idx], f[pareto_idx, y_idx],
               color='green', label='Pareto front', zorder=3)
    plt.scatter([baseline_f[x_idx]], [baseline_f[y_idx]],
               color='red', label='Before investments', zorder=4, s=80)
    plt.xlabel(f_names[x_idx])
    plt.ylabel(f_names[y_idx])
    plt.title('Investments evaluation - critical snapshot')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # --- Step 6: overloaded branches before / after the investments ---
    print("\n=== Step 6: overloaded branches ===")
    list_overloaded_branches(snapshot_grid, pf_options, OVERLOAD_THRESHOLD, "Before investments")

    inv_list: List[dev.Investment] = snapshot_grid.investments
    snapshot_grid.set_investments_status(investments_list=inv_list, apply_investment=True,
                                         all_elements_dict=None)
    list_overloaded_branches(snapshot_grid, pf_options, OVERLOAD_THRESHOLD, "After investments")
    snapshot_grid.set_investments_status(investments_list=inv_list, apply_investment=False,
                                         all_elements_dict=None)


if __name__ == '__main__':
    main()
