# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import sys

import numpy as np
from scipy.linalg import qr, svd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import gfl_vsc_emt_internal_filter_validation as base_validation
import gfl_vsc_emt_soft_pwm_bridge_validation as soft_validation
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import resolve_solver_boundary_updater
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import (
    JitSymbolicSolver,
    evaluate_batched_residual,
    fill_full_parameter_buffer,
)
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes


H = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_SOFT_PWM_DIAG_H", "1e-6"))
SOFT_SIGN_LAMDA = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_SOFT_PWM_DIAG_LAMDA", "1e-4"))
TOP_K = int(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_SOFT_PWM_DIAG_TOP_K", "25"))


def build_problem() -> EmtProblemDae:
    soft_validation.SOFT_SIGN_LAMDA = SOFT_SIGN_LAMDA
    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = base_validation.build_grid()
    pf_results = base_validation.run_power_flow(grid)
    vsc_mdl, _line23_mdl, _gen_mdl, dc_source_mdl, _vsc_filter_l, _p_ref0, _q_ref0, theta_ref = base_validation.build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3
    )
    soft_validation.install_soft_pwm_bridge(grid, vsc_mdl)
    options = EmtOptions(
        time_step=H,
        simulation_time=H,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results=pf_results)
    base_validation.seed_internal_filter_guess(problem, grid, pf_results, vsc_mdl, dc_source_mdl, line23, bus_dc, bus2, theta_ref)
    soft_validation.seed_soft_pwm_bridge(problem, vsc_mdl)
    return problem


def main() -> None:
    problem = build_problem()
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=H,
        h=H,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=100000,
        newton_max_iter=1,
    )
    solver.build_jit_kernel(DynamicIntegrationMethod.DaeBackEuler)
    solver._build_jit_symbolic_hybrid(DynamicIntegrationMethod.DaeBackEuler, use_sparse=False)

    x0 = problem.get_x0()
    dx0 = problem.get_dx0()
    x_iter = x0.copy()
    n_states = problem.get_states_number()
    x_iter[:n_states] = x0[:n_states] + H * dx0[:n_states]

    ev_params = problem.event_params_values.copy()
    full_params = solver._full_parameter_buffer
    fill_full_parameter_buffer(ev_params, solver._static_parameter_buffer, full_params)
    boundary_updater = resolve_solver_boundary_updater(problem, None, 0.0)
    if boundary_updater is not None:
        boundary_updater.update(H, x0, full_params)
        ev_params[:] = full_params[:len(ev_params)]

    residual = np.zeros(problem.get_all_vars_number())
    res_inf = evaluate_batched_residual(
        kernel_list=solver.jit_kernels[DynamicIntegrationMethod.DaeBackEuler],
        x_iter=x_iter,
        full_params=full_params,
        x_prev=x0,
        dx_prev=dx0,
        h_eff=H,
        x_prev2=x0,
        residual_out=residual,
    )
    jac = solver.jit_jacobian_symbolic[f"{DynamicIntegrationMethod.DaeBackEuler}_False"].evaluate(
        states=x_iter,
        params=full_params,
        history=x0,
        d_history=dx0,
        h=H,
        history2=x0,
    )

    rank = int(np.linalg.matrix_rank(jac, tol=1.0e-10))
    cond = float(np.linalg.cond(jac))
    _u, svals, vh = svd(jac, full_matrices=False)
    q_mat, r_mat, piv = qr(jac, pivoting=True, mode="economic")
    del q_mat

    vars_ordered = list(solver.state_vars) + list(solver.algebraic_vars)
    print(f"lambda={SOFT_SIGN_LAMDA:.9e}, h={H:.9e}")
    print(f"shape={jac.shape}, rank={rank}, deficiency={jac.shape[1] - rank}, cond={cond:.9e}, res_inf={res_inf:.9e}")
    print("Smallest singular values:")
    for value in svals[-min(TOP_K, len(svals)):]:
        print(f"  {value:.9e}")

    print("Weak pivot columns:")
    for col in piv[rank:rank + TOP_K]:
        var = vars_ordered[int(col)]
        print(f"  col={int(col):4d} name={var.name}")

    print("Smallest QR diagonal pivots:")
    diag = np.abs(np.diag(r_mat))
    for idx in np.argsort(diag)[:min(TOP_K, len(diag))]:
        print(f"  pivot_order={int(idx):4d} diag={diag[int(idx)]:.9e} col={int(piv[int(idx)]):4d} name={vars_ordered[int(piv[int(idx)])].name}")

    print("Largest residual rows:")
    for row in np.argsort(np.abs(residual))[-TOP_K:][::-1]:
        info = solver._residual_debug_info[int(row)]
        print(f"  row={int(row):4d} residual={residual[int(row)]: .9e} label={info['label']}")

    if jac.shape[1] > rank:
        null_vec = vh[-1, :]
        print("Dominant entries in smallest right singular vector:")
        for col in np.argsort(np.abs(null_vec))[-TOP_K:][::-1]:
            var = vars_ordered[int(col)]
            print(f"  col={int(col):4d} coeff={null_vec[int(col)]: .9e} name={var.name}")


if __name__ == "__main__":
    main()
