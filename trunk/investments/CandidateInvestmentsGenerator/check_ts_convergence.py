# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Run the AC power flow time series on IEEE39_1month_Jan19 and report which snapshots did not
converge, to check whether the candidate-investment generator's critical-snapshot scan can be
fooled by non-converged (garbage) time steps.
"""
import os

import numpy as np

import VeraGridEngine.api as gce

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GRID_PATH = os.path.join(SCRIPT_DIR, '..', '..', '..', 'Grids_and_profiles', 'grids',
                         'IEEE39_1month_Jan19.veragrid')


def main() -> None:
    """
    Run the time-series AC power flow with the requested solver settings and print the count and
    percentage of snapshots that did not converge, plus their timestamps.
    """
    grid = gce.FileOpen(GRID_PATH).open()

    options = gce.PowerFlowOptions(
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

    results = gce.power_flow_ts(grid=grid, options=options)

    converged = np.asarray(results.converged_values, dtype=bool)
    n_total = len(converged)
    n_converged = int(np.sum(converged))
    n_failed = n_total - n_converged
    failed_pct = 100.0 * n_failed / n_total if n_total > 0 else 0.0

    print(f"Time steps: {n_total}")
    print(f"Converged: {n_converged}")
    print(f"Did not converge: {n_failed} ({failed_pct:.2f}%)")

    if n_failed > 0:
        print("Non-converged snapshots:")
        time_array = results.time_array
        for t in np.where(~converged)[0]:
            print(f"  [{t}] {time_array[t]}")

    vm = np.abs(results.voltage)
    vm_min = vm.min(axis=1)
    vm_max = vm.max(axis=1)

    print("\nPer-snapshot voltage range (pu):")
    time_array = results.time_array
    for t in range(n_total):
        flag = "" if converged[t] else "  <-- NOT CONVERGED"
        print(f"  [{t}] {time_array[t]}  min={vm_min[t]:.4f}  max={vm_max[t]:.4f}{flag}")


if __name__ == '__main__':
    main()
