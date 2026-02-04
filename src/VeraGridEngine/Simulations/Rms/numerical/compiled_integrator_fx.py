# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import scipy.sparse as sp
import time
from scipy.sparse import csc_matrix
from VeraGridEngine.basic_structures import Vec, Mat
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Utils.Symbolic.symbolic import DiffVar
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.Utils.Symbolic.diagnostic import (with_newton_diagnostics, NewtonDiagnosticsConfig,
                                                      NewtonSolveContext, dense_lstsq_fallback,
                                                      sparse_lsqr_fallback)
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Utils.Sparse.csc import pack_4_by_4_scipy


class CompiledIntegration:

    def __init__(self,
                 problem: EmtProblemTemplate,
                 t0: float,
                 t_end: float,
                 h: float,
                 max_iter: int):
        """

        :param problem:
        """

        self.problem = problem
        self.t0 = t0
        self.h = h
        self.max_iter_0 = max_iter
        self.steps = int(np.ceil((t_end - t0) / h))
        self.t: Vec = np.empty(self.steps + 1)
        self.y: Mat = np.empty((self.steps + 1, self.problem.get_all_vars_number()))

        self.newton_trace_collector: NewtonTraceCollector | None = None

    def simulate_unified(self,
                         t0: float,
                         t_end: float,
                         h: float,
                         x0: Vec,
                         dx0: Vec,
                         params0: Vec,
                         method: DynamicIntegrationMethod = DynamicIntegrationMethod.Trapezoid,
                         boundary_update_fn=None,
                         verbose: bool = False,
                         dense_threshold: int = 100):
        """
        Main simulation entry point. Dispatches the simulation to the appropriate engine
        (Implicit JIT or Explicit Legacy) based on the solver configuration.

        :param t0: Start time of the simulation.
        :param t_end: End time of the simulation.
        :param h: Time step size (fixed).
        :param x0: Initial state vector (includes algebraic variables).
        :param dx0: Initial derivative vector (optional, for implicit methods).
        :param params0: Initial parameters vector (optional).
        :param method: Integration scheme (e.g., Trapezoid, BDF2).
        :param boundary_update_fn: Callback function for boundary/control updates per step.
        :param verbose: If True, prints simulation progress and stats.
        :param dense_threshold: Threshold N. Systems with N <= threshold use dense linear algebra.
        :return: Tuple (time_array, trajectory_array).
        """

        # Implicit-by-design engine
        if method not in {
            DynamicIntegrationMethod.Trapezoid,
            DynamicIntegrationMethod.BDF2,
            DynamicIntegrationMethod.BackEuler
        }:
            raise ValueError(f"Method {method} not supported by totally implicit engine.")

        return self._simulate_jit(
            t0, t_end, h, x0, dx0, params0,
            method_str=method.value,
            boundary_update_fn=boundary_update_fn,
            verbose=verbose,
            dense_threshold=dense_threshold
        )

    def _build_jit_kernel(self, method_str: str):
        """
        Compiles the numerical residual function using the JIT compiler and caches it.
        It maps symbolic variables to the compiled array indices.
        """
        print(f"--- [JIT] Compiling Implicit Kernel ({method_str}) ---")

        if not hasattr(self, 'jit_kernels'):
            self.jit_kernels = {}

        # Use actual variable (Objects) for the compiler mapping
        sorted_vars = self.problem.get_state_vars() + self.problem.get_algebraic_vars()
        all_params = self.problem.get_variable_parameters() + self.problem.get_constant_parameters()

        # Build residual equations: DiffVar - RHS = 0
        equations = []
        for i, rhs in enumerate(self.problem.get_state_eqs()):
            sv = self.problem.get_state_vars()[i]
            d_term = DiffVar(name=f"d_{sv.name}", base_var=sv)
            equations.append(d_term - rhs)
        equations.extend(self.problem.get_algebraic_eqs())

        # Compile and cache
        self.jit_compiler = EquationCompiler(variables=sorted_vars, parameters=all_params, method=method_str)
        kernel = self.jit_compiler.compile(equations, func_name=f"jit_step_{method_str}", use_cse=True)

        self.jit_kernels[method_str] = kernel

    def _simulate_jit(self, t0, t_end, h, x0, dx0, params0, method_str, boundary_update_fn, verbose,
                      dense_threshold):
        """
        Optimized internal simulation loop using JIT-compiled kernels and hybrid linear solvers.
        """

        _n_vars = self.problem.get_all_vars_number()

        # 1. Kernel Retrieval
        if not hasattr(self, 'jit_kernels'):
            self.jit_kernels = {}
        if method_str not in self.jit_kernels:
            self._build_jit_kernel(method_str)
        current_kernel = self.jit_kernels[method_str]

        # 2. Linear Solver Strategy Configuration
        use_dense_solver = (_n_vars <= dense_threshold)

        if verbose:
            mode_str = "DENSE" if use_dense_solver else "SPARSE"
            print(
                f"   [Config] System N={_n_vars}. Using {mode_str} linear solver (Threshold={dense_threshold}).")

        # 3. Initialization
        steps = int(np.ceil((t_end - t0) / h))
        t = np.linspace(t0, t_end, steps + 1)
        y = np.zeros((steps + 1, _n_vars))
        y[0] = x0.copy()

        x_prev = x0.copy()
        dx_prev = dx0.copy() if dx0 is not None else np.zeros(self.problem.get_all_vars_number())
        x_prev2 = x0.copy()

        static_vals = np.array([c.value for c in self.problem.get_parameters_values()])
        if params0 is not None and len(params0) == len(self.problem.get_variable_parameters()):
            ev_params = params0
        else:
            ev_params = np.zeros(len(self.problem.get_variable_parameters()))

        # Integration Coefficients
        if method_str == DynamicIntegrationMethod.Trapezoid.value:
            alpha = 2.0 / h
            h_eff = h / 2.0
        elif method_str == DynamicIntegrationMethod.BDF2.value:
            alpha = 1.5 / h
            h_eff = h * (2.0 / 3.0)
        else:
            alpha = 1.0 / h
            h_eff = h

        # Jacobian Scaling Factors
        row_scale = np.ones(_n_vars)
        row_scale[:self.problem.get_states_number()] = alpha

        row_scaler_dense = None
        row_scaler_sparse = None

        if use_dense_solver:
            row_scaler_dense = row_scale[:, None]  # Broadcasting for dense arrays
        else:
            row_scaler_sparse = sp.diags(row_scale, format='csc')

        x_iter = x0.copy()
        t_start = time.time()

        if verbose:
            print(f"-> Starting JIT Simulation ({method_str}, {steps} steps)...")

        diag_cfg = NewtonDiagnosticsConfig(
            step_norm_explode=1e6,
            dense_cond_warn=1e12,
            compute_dense_cond=True,
            enable_fallback=True,
        )

        dense_solve = with_newton_diagnostics(
            np.linalg.solve,
            fallback_solve=dense_lstsq_fallback,
            collector=self.newton_trace_collector,
            config=diag_cfg,
            solver_name="dense",
        )

        sparse_solve = with_newton_diagnostics(
            sp.linalg.spsolve,
            fallback_solve=sparse_lsqr_fallback,
            collector=self.newton_trace_collector,
            config=diag_cfg,
            solver_name="sparse",
        )

        # 4. Main Time Loop
        for i in range(steps):
            t_curr = t[i + 1]

            # Update dynamic parameters
            ev_params = self.problem.def_event_params_fn(ev_params, float(t_curr))
            ev_params = self.problem.def_event_params_fn(ev_params, float(t_curr))
            full_params = np.concatenate((ev_params, static_vals))

            # External Control / Boundary Update
            if boundary_update_fn:
                boundary_update_fn(t_curr, x_prev, full_params)

            # Newton-Raphson Iteration
            for k in range(15):
                # Linear Solve (diagnostics wrapper)
                ctx = NewtonSolveContext(
                    t=float(t_curr),
                    step_idx=int(i),
                    newton_iter=int(k),
                    phase="jit",
                    method=str(method_str),
                )
                # Evaluate Residuals (JIT)
                res = current_kernel(x_iter, full_params, x_prev, dx_prev, h, x_prev2)

                res_norm_inf = float(np.linalg.norm(res, np.inf))
                ctx.res_norm_inf = res_norm_inf

                if np.linalg.norm(res, np.inf) < 1e-6:
                    break

                # Jacobian Evaluation
                dx_guess = (x_iter - x_prev) * alpha - dx_prev
                J_base = self._jacobian_implicit(x=x_iter, dx=dx_guess, h=h_eff)

                if use_dense_solver:
                    J_dense = J_base.toarray()
                    J_final = J_dense * row_scaler_dense
                    delta = dense_solve(J_final, -res, ctx)
                else:
                    J_final = row_scaler_sparse @ J_base
                    delta = sparse_solve(J_final, -res, ctx)

                x_iter += delta

            # Update History
            y[i + 1] = x_iter

            if method_str == DynamicIntegrationMethod.Trapezoid.value:
                dx_new = np.zeros_like(dx_prev)
                mask = slice(0, self.problem.get_states_number())
                dx_new[mask] = alpha * (x_iter[mask] - x_prev[mask]) - dx_prev[mask]
                dx_prev = dx_new
            elif method_str == DynamicIntegrationMethod.BDF2.value:
                x_prev2 = x_prev.copy()

            x_prev = x_iter.copy()

        if verbose:
            print(f"JIT Finished: {time.time() - t_start:.4f}s")
        return t, y

    def _jacobian_implicit(self,
                           x: Vec,
                           dx: Vec,
                           h: float) -> sp.csc_matrix:
        """
        :param x: vector or variables' values
        :param dx: vector of diff values
        :param h: step
        :return:
        """

        """
                  state Var    algeb var
        state eq |I - h * J11 | - h* J12  |    | ∆ state var|    | ∆ state eq |
                 |            |           |    |            |    |            |
                 -------------------------- x  |------------|  = |------------|
        algeb eq |J21         | J22       |    | ∆ algeb var|    | ∆ algeb eq |
                 |            |           |    |            |    |            |
        """

        # returns only j22 if no states, returns J if states
        if self.problem.get_states_number() == 0:
            j22: sp.csc_matrix = self.problem.get_j22(x, dx, h)
            return j22

        j11_val: csc_matrix = self.problem.get_j11(x, dx, h)
        j12_val: csc_matrix = self.problem.get_j12(x, dx, h)
        j21_val: csc_matrix = self.problem.get_j21(x, dx, h)
        j22_val: csc_matrix = self.problem.get_j22(x, dx, h)

        I = sp.eye(m=self.problem.get_states_number(), n=self.problem.get_states_number())
        j11: sp.csc_matrix = (I - h * j11_val).tocsc()
        j12: sp.csc_matrix = - h * j12_val
        j21: sp.csc_matrix = j21_val
        j22: sp.csc_matrix = j22_val

        J = pack_4_by_4_scipy(j11, j12, j21, j22)

        return J