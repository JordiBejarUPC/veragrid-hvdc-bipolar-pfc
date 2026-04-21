# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys
from typing import List, Tuple

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

from VeraGridEngine.enumerations import ValveEmtType
from dc_branch_demo_support import (
    ValveDemoResult,
    build_valve_demo_boundary_updater,
    build_valve_demo_problem,
    create_symbolic_solver,
    extract_trace,
)


def run_valve_demo_case(valve_tpe: ValveEmtType, enable_plots: bool = False) -> ValveDemoResult:
    """
    Run one standalone EMT valve demo case and optionally display the result figures.

    Expected behaviour:

    - ``Diode``: load voltage rises automatically from zero and the retained mode settles to ``+1``.
    - ``IGBT``: load voltage is low while the gate is ``0``, rises while the gate is ``1`` and drops again when the gate returns to ``0``.
    - ``Thyristor``: a short gate pulse turns the valve on and the retained mode stays at ``+1`` after the gate returns to ``0``.

    :param valve_tpe: Valve physical type.
    :param enable_plots: Display matplotlib figures when ``True``.
    :return: Recorded EMT valve traces for the selected case.
    """
    problem, _, gate_idx, mode_idx, tracked_vars = build_valve_demo_problem(valve_tpe=valve_tpe)
    solver = create_symbolic_solver(problem=problem, t_end=1.0e-2, h=1.0e-5)
    boundary_updater = build_valve_demo_boundary_updater(problem=problem, gate_idx=gate_idx, mode_idx=mode_idx, valve_tpe=valve_tpe)

    time_s, state_traj, _ = solver.simulate(boundary_updater=boundary_updater)
    result = ValveDemoResult(
        time_s=time_s,
        v_source_pu=extract_trace(problem, state_traj, tracked_vars["v_source"]),
        v_load_pu=extract_trace(problem, state_traj, tracked_vars["v_load"]),
        i_branch_pu=extract_trace(problem, state_traj, tracked_vars["i_branch"]),
        v_valve_pu=extract_trace(problem, state_traj, tracked_vars["v_valve"]),
        control_time_s=boundary_updater.get_record_time_s(),
        gate_trace=boundary_updater.get_record_value(),
        mode_trace=boundary_updater.get_record_aux(),
    )

    if enable_plots:
        plot_valve_demo_result(valve_tpe, result)
    else:
        pass

    return result


def run_all_valve_demo_cases(enable_plots: bool = False) -> List[Tuple[ValveEmtType, ValveDemoResult]]:
    """
    Run all standalone EMT valve demo cases.

    :param enable_plots: Display matplotlib figures when ``True``.
    :return: List of ``(valve_type, result)`` pairs.
    """
    result_pairs: List[Tuple[ValveEmtType, ValveDemoResult]] = list()
    valve_tpe: ValveEmtType

    for valve_tpe in [ValveEmtType.Diode, ValveEmtType.Igbt, ValveEmtType.Thyristor]:
        result_pairs.append((valve_tpe, run_valve_demo_case(valve_tpe=valve_tpe, enable_plots=enable_plots)))

    return result_pairs


def plot_valve_demo_result(valve_tpe: ValveEmtType, result: ValveDemoResult) -> None:
    """
    Plot the traces produced by one standalone EMT valve demo case.

    :param valve_tpe: Valve physical type.
    :param result: Recorded EMT valve traces.
    :return: None.
    """
    time_s: np.ndarray = result.get_time_s()
    control_time_s: np.ndarray = result.get_control_time_s()
    fig, axes = plt.subplots(4, 1, figsize=(12.0, 10.0), sharex=False)

    # The source voltage should stay fixed while the load voltage reflects the conduction state.
    axes[0].plot(time_s, result.get_v_source_pu(), label="V source", color="tab:blue")
    axes[0].plot(time_s, result.get_v_load_pu(), label="V load", color="tab:orange")
    axes[0].set_ylabel("Voltage [p.u.]")
    axes[0].set_title(f"{valve_tpe.value} EMT Demo - Bus Voltages")
    axes[0].grid(True)
    axes[0].legend(loc="best")

    # The electrical-response subplot shows when the branch actually conducts.
    axes[1].plot(time_s, result.get_i_branch_pu(), label="I branch", color="tab:green")
    axes[1].plot(time_s, result.get_v_valve_pu(), label="Valve voltage", color="tab:red")
    axes[1].set_ylabel("Current / Voltage [p.u.]")
    axes[1].set_title(f"{valve_tpe.value} EMT Demo - Electrical Response")
    axes[1].grid(True)
    axes[1].legend(loc="best")

    # The gate subplot is flat for the diode, pulsed for the IGBT and briefly pulsed for the thyristor.
    axes[2].step(control_time_s, result.get_gate_trace(), where="post", label="Gate", color="black")
    axes[2].set_ylabel("Gate [-]")
    axes[2].set_title(f"{valve_tpe.value} EMT Demo - Gate Command")
    axes[2].grid(True)
    axes[2].legend(loc="best")

    # The retained mode should expose the key behavioural difference between the valve types.
    axes[3].step(control_time_s, result.get_mode_trace(), where="post", label="Path mode", color="tab:purple")
    axes[3].set_xlabel("Time [s]")
    axes[3].set_ylabel("Mode [-]")
    axes[3].set_title(f"{valve_tpe.value} EMT Demo - Retained Conduction Mode")
    axes[3].grid(True)
    axes[3].legend(loc="best")

    fig.tight_layout()
    plt.show()


def main() -> None:
    """
    Run all standalone EMT valve demo cases as a script.

    :return: None.
    """
    result_pair: Tuple[ValveEmtType, ValveDemoResult]

    for result_pair in run_all_valve_demo_cases(enable_plots=True):
        valve_tpe: ValveEmtType = result_pair[0]
        result: ValveDemoResult = result_pair[1]
        print("=" * 72)
        print(f"{valve_tpe.value.upper()} EMT DEMO SUMMARY")
        print("=" * 72)
        print(f"Final source voltage    : {result.get_v_source_pu()[-1]: .6f} p.u.")
        print(f"Final load voltage      : {result.get_v_load_pu()[-1]: .6f} p.u.")
        print(f"Final branch current    : {result.get_i_branch_pu()[-1]: .6f} p.u.")
        print(f"Final retained mode     : {result.get_mode_trace()[-1]: .6f}")


if __name__ == "__main__":
    main()
