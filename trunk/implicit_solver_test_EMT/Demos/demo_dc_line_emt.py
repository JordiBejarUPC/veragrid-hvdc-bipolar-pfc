# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR: str = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT: str = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
SRC_ROOT: str = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
else:
    pass

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
else:
    pass

from dc_branch_demo_support import (
    DcLineDemoResult,
    build_dc_line_demo_boundary_updater,
    build_dc_line_demo_problem,
    create_symbolic_solver,
    extract_trace,
)


def run_dc_line_demo(enable_plots: bool = False) -> DcLineDemoResult:
    """
    Run the standalone EMT DC line demo and optionally display the result figures.

    Expected behaviour:

    - the source-side voltage remains essentially constant,
    - the load-side voltage settles to one steady-state value before the load step,
    - at the load-conductance step the load-side voltage drops smoothly,
    - the branch current and source power increase to a new bounded plateau.

    :param enable_plots: Display matplotlib figures when ``True``.
    :return: Recorded DC line demo traces.
    """
    problem, _, load_step_idx, tracked_vars = build_dc_line_demo_problem()
    solver = create_symbolic_solver(problem=problem, t_end=1.5e-2, h=1.0e-5)
    boundary_updater = build_dc_line_demo_boundary_updater(load_param_idx=load_step_idx)

    time_s, state_traj, _ = solver.simulate(boundary_updater=boundary_updater)
    result = DcLineDemoResult(
        time_s=time_s,
        v_source_pu=extract_trace(problem, state_traj, tracked_vars["v_source"]),
        v_load_pu=extract_trace(problem, state_traj, tracked_vars["v_load"]),
        i_branch_pu=extract_trace(problem, state_traj, tracked_vars["i_branch"]),
        p_source_pu=extract_trace(problem, state_traj, tracked_vars["p_source"]),
        p_load_pu=extract_trace(problem, state_traj, tracked_vars["p_load"]),
        g_load_time_s=boundary_updater.get_record_time_s(),
        g_load_trace=boundary_updater.get_record_value(),
    )

    if enable_plots:
        plot_dc_line_demo_result(result)
    else:
        pass

    return result


def plot_dc_line_demo_result(result: DcLineDemoResult) -> None:
    """
    Plot the traces produced by the standalone EMT DC line demo.

    :param result: DC line demo result container.
    :return: None.
    """
    time_s: np.ndarray = result.get_time_s()
    fig, axes = plt.subplots(3, 1, figsize=(12.0, 9.0), sharex=True)

    # The voltage subplot should show one bounded first-order response after the load step.
    axes[0].plot(time_s, result.get_v_source_pu(), label="V source", color="tab:blue")
    axes[0].plot(time_s, result.get_v_load_pu(), label="V load", color="tab:orange")
    axes[0].set_ylabel("Voltage [p.u.]")
    axes[0].set_title("DC Line EMT Demo - Voltages")
    axes[0].grid(True)
    axes[0].legend(loc="best")

    # The current subplot should stay positive and move between two finite plateaus.
    axes[1].plot(time_s, result.get_i_branch_pu(), label="I branch", color="tab:green")
    axes[1].set_ylabel("Current [p.u.]")
    axes[1].set_title("DC Line EMT Demo - Current")
    axes[1].grid(True)
    axes[1].legend(loc="best")

    # The power subplot overlays the branch power with the applied load-conductance step.
    axes[2].plot(time_s, result.get_p_source_pu(), label="P source", color="tab:purple")
    axes[2].plot(time_s, result.get_p_load_pu(), label="P load-side branch", color="tab:brown")
    axes[2].step(result.get_g_load_time_s(), result.get_g_load_trace(), where="post", label="Load conductance", color="black")
    axes[2].set_xlabel("Time [s]")
    axes[2].set_ylabel("Power / Conductance [p.u.]")
    axes[2].set_title("DC Line EMT Demo - Power Transfer")
    axes[2].grid(True)
    axes[2].legend(loc="best")

    fig.tight_layout()
    plt.show()


def main() -> None:
    """
    Run the standalone EMT DC line demo as a script.

    :return: None.
    """
    result: DcLineDemoResult = run_dc_line_demo(enable_plots=True)

    print("=" * 72)
    print("DC LINE EMT DEMO SUMMARY")
    print("=" * 72)
    print(f"Final source voltage  : {result.get_v_source_pu()[-1]: .6f} p.u.")
    print(f"Final load voltage    : {result.get_v_load_pu()[-1]: .6f} p.u.")
    print(f"Final branch current  : {result.get_i_branch_pu()[-1]: .6f} p.u.")
    print(f"Final source power    : {result.get_p_source_pu()[-1]: .6f} p.u.")


if __name__ == "__main__":
    main()
