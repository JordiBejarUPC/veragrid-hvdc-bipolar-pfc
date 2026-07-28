# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import gfl_vsc_emt_internal_filter_validation as base_validation
import gfl_vsc_emt_soft_pwm_bridge_validation as soft_validation
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes


SIM_TIME = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_SOFT_PWM_SIM_TIME", "2e-4"))
TIME_STEP = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_SOFT_PWM_TIME_STEP", "1e-6"))
SOFT_SIGN_LAMDA = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_SOFT_PWM_LAMDA", "1e-4"))
HANDOVER_TIME = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_SOFT_PWM_HANDOVER_TIME", "1e-4"))
SWITCHING_FREQUENCY = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_SOFT_PWM_FSW", "1000.0"))
SOLVER_TYPE = os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_SOFT_PWM_SOLVER", "StructuralAD")


def main() -> None:
    soft_validation.SOFT_SIGN_LAMDA = SOFT_SIGN_LAMDA
    soft_validation.HANDOVER_TIME = HANDOVER_TIME
    soft_validation.SWITCHING_FREQUENCY = SWITCHING_FREQUENCY

    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = base_validation.build_grid()
    pf_results = base_validation.run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")

    vsc_mdl, _line23_mdl, _gen_mdl, dc_source_mdl, _vsc_filter_l, _p_ref0, _q_ref0, theta_ref = base_validation.build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3
    )
    soft_validation.install_soft_pwm_bridge(grid, vsc_mdl)

    options = EmtOptions(
        time_step=TIME_STEP,
        simulation_time=SIM_TIME,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        solver_type=EmtSolverTypes[SOLVER_TYPE],
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results=pf_results)
    base_validation.seed_internal_filter_guess(problem, grid, pf_results, vsc_mdl, dc_source_mdl, line23, bus_dc, bus2, theta_ref)
    soft_validation.seed_soft_pwm_bridge(problem, vsc_mdl)

    print(f"GFL internal-filter soft PWM lambda: {SOFT_SIGN_LAMDA:.9e}")
    print(f"GFL internal-filter soft PWM solver: {SOLVER_TYPE}")
    print(f"GFL internal-filter soft PWM handover: {HANDOVER_TIME:.9e} s")
    print(f"GFL internal-filter soft PWM dt/t_end: {TIME_STEP:.9e} / {SIM_TIME:.9e}")
    base_validation.print_problem_structure(problem)

    try:
        t, _y, _dy, well_initialized, converged = base_validation.run_emt(
            problem=problem,
            options=options,
            t_end=options.simulation_time,
        )
    except (np.linalg.LinAlgError, RuntimeError) as exc:
        print(f"GFL internal-filter soft PWM solve failed during Newton iteration: {exc}")
        return

    print(f"GFL internal-filter soft PWM well initialized: {well_initialized}")
    print(f"GFL internal-filter soft PWM converged: {converged}")
    print(f"Solved samples: {len(t)}")


if __name__ == "__main__":
    main()
