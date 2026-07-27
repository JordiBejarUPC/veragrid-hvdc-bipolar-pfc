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
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Utils.Symbolic.block import Block
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes


SIM_TIME = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_DIRECT_BRIDGE_SIM_TIME", "2e-5"))
TIME_STEP = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_DIRECT_BRIDGE_TIME_STEP", "1e-6"))
SOLVER_TYPE = os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_DIRECT_BRIDGE_SOLVER", "StructuralAD")


def replace_with_direct_bridge(grid, vsc_mdl: Block) -> None:
    vf = grid.var_factory
    for block in vsc_mdl.get_all_blocks():
        block.algebraic_eqs = [
            eq for eq in block.algebraic_eqs
            if not (str(eq).startswith("(va_v) - ") or str(eq).startswith("(vb_v) - ") or str(eq).startswith("(vc_v) - "))
        ]

    theta = base_validation.find_name_in_block("theta", vsc_mdl)
    v_d_c = base_validation.find_name_in_block("v_d_c", vsc_mdl)
    v_q_c = base_validation.find_name_in_block("v_q_c", vsc_mdl)
    va_v = base_validation.find_name_in_block("va_v", vsc_mdl)
    vb_v = base_validation.find_name_in_block("vb_v", vsc_mdl)
    vc_v = base_validation.find_name_in_block("vc_v", vsc_mdl)
    sqrt3 = vf.add_const(np.sqrt(3.0))
    half = vf.add_const(0.5)
    park_theta = vf.add_const(0.0) - theta
    va_expr = v_d_c * sym.cos(park_theta) + v_q_c * sym.sin(park_theta)
    vb_expr = v_d_c * (-half * sym.cos(park_theta) - half * sqrt3 * sym.sin(park_theta)) + v_q_c * (-half * sym.sin(park_theta) + half * sqrt3 * sym.cos(park_theta))
    vc_expr = v_d_c * (-half * sym.cos(park_theta) + half * sqrt3 * sym.sin(park_theta)) + v_q_c * (-half * sym.sin(park_theta) - half * sqrt3 * sym.cos(park_theta))
    vsc_mdl.add(Block(
        algebraic_eqs=[va_v - va_expr, vb_v - vb_expr, vc_v - vc_expr],
        name="gfl_direct_bridge_replacement",
    ))
    vsc_mdl.unify_blocks()


def main() -> None:
    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = base_validation.build_grid()
    pf_results = base_validation.run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")
    vsc_mdl, _line23_mdl, _gen_mdl, dc_source_mdl, _vsc_filter_l, _p_ref0, _q_ref0, theta_ref = base_validation.build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3
    )
    replace_with_direct_bridge(grid, vsc_mdl)
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
    print(f"GFL internal-filter direct bridge solver: {SOLVER_TYPE}")
    base_validation.print_problem_structure(problem)
    try:
        t, _y, _dy, well_initialized, converged = base_validation.run_emt(problem=problem, options=options, t_end=options.simulation_time)
    except (np.linalg.LinAlgError, RuntimeError) as exc:
        print(f"GFL internal-filter direct bridge solve failed during Newton iteration: {exc}")
        return
    print(f"GFL internal-filter direct bridge well initialized: {well_initialized}")
    print(f"GFL internal-filter direct bridge converged: {converged}")
    print(f"Solved samples: {len(t)}")


if __name__ == "__main__":
    main()
