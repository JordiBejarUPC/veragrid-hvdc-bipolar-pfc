# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Set, Tuple
import numpy as np
import numba as nb
import scipy.sparse as sp
import time
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.enumerations import DynamicIntegrationMethod

from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr)
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler

from VeraGridEngine.Utils.Symbolic.diagnostic import (with_newton_diagnostics, NewtonDiagnosticsConfig,
                                                      NewtonSolveContext, dense_lstsq_fallback,
                                                      sparse_lsqr_fallback)
from VeraGridEngine.basic_structures import Vec, Mat


class JitSymbolicSolver:
    def __init__(self,
                 problem: EmtProblemTemplate,
                 t0: float,
                 t_end: float,
                 h: float,
                 method_str: DynamicIntegrationMethod = DynamicIntegrationMethod.Trapezoid,
                 dense_threshold: int = 100,
                 verbose: bool = False):
        """
        :param problem: The DAE problem definition.
        :param t0: Initial time.
        :param t_end: End time.
        :param h: Time step.
        :param method_str: DynamicIntegrationMethod (Trapezoid, BackEuler, BDF2).
        :param dense_threshold: Threshold to switch between dense and sparse linear solvers.
        :param verbose: Print compilation and simulation timings.
        """
        self.problem = problem
        self.t0 = t0
        self.h = h
        self.method_str = method_str
        self.dense_threshold = dense_threshold
        self.verbose = verbose

        self.steps = int(np.ceil((t_end - t0) / h))
        self.t: Vec = np.empty(self.steps + 1)
        self.y: Mat = np.empty((self.steps + 1, self.problem.get_all_vars_number()))

        # Solver specific caches
        self.jit_kernels = {}
        self.jit_jacobian_symbolic = {}

        self.state_vars = self.problem.get_state_vars()
        self.algebraic_vars = self.problem.get_algebraic_vars()
        self.state_eqs = self.problem.get_state_eqs()
        self.algebraic_eqs = self.problem.get_algebraic_eqs()

    # ==============================================================================
    # 2. JIT IMPLICIT ENGINE (Optimized with Batching)
    # ==============================================================================

    def _build_jit_kernel(self, method_str: DynamicIntegrationMethod):
        """
        Compiles the numerical residual function using JIT.
        It uses a batching strategy (splitting equations into chunks) to prevent
        Numba/LLVM from hanging when compiling very large non-linear systems.
        """
        print(f"--- [JIT] Compiling Implicit Kernel ({method_str}) ---")

        if not hasattr(self, 'jit_kernels'):
            self.jit_kernels = {}

        sorted_vars = self.state_vars + self.algebraic_vars
        all_params = self.problem.get_variable_parameters() + self.problem.get_constant_parameters()

        equations = []
        for i, rhs in enumerate(self.state_eqs):
            sv = self.state_vars[i]
            d_term = Var(name=f"d_{sv.name}", base_var=sv)
            equations.append(d_term - rhs)

        equations.extend(self.algebraic_eqs)

        self.jit_compiler = EquationCompiler(variables=sorted_vars, parameters=all_params, method=method_str)

        # Batch compilation strategy
        BATCH_SIZE = 100
        n_eqs = len(equations)
        batched_kernels = []

        for i in range(0, n_eqs, BATCH_SIZE):
            chunk = equations[i: i + BATCH_SIZE]
            f_name = f"jit_step_{method_str}_part_{i}"

            # Compile inplace: the function writes directly to the 'residuals' array
            py_func = self.jit_compiler.compile(chunk, func_name=f_name, use_cse=True, offset=i, inplace=True)
            jit_func = nb.njit(cache=True, fastmath=True)(py_func)
            batched_kernels.append(jit_func)

        self.jit_kernels[method_str] = batched_kernels

    # ==============================================================================
    #  HELPER: SYMBOLIC TOPOLOGY ANALYSIS
    # ==============================================================================

    @staticmethod
    def _get_vars_in_expr(expr: Expr) -> Set[int]:
        """
        Recursively collects UIDs of all variables (Var, DiffVar, LagVar)
        present in an expression using a non-recursive stack traversal.
        """
        found = set()
        stack = [expr]
        visited = set()

        while stack:
            node = stack.pop()
            if id(node) in visited: continue
            visited.add(id(node))

            if isinstance(node, Var):
                if Var.base_var is not None:
                    found.add(node.base_var.uid)
                    found.add(node.uid)
                else:
                    found.add(node.uid)

            if hasattr(node, 'args'):
                stack.extend(node.args)
            elif hasattr(node, 'left'):
                stack.append(node.left)
                stack.append(node.right)
            elif hasattr(node, 'operand'):
                stack.append(node.operand)
            elif hasattr(node, 'arg'):
                stack.append(node.arg)

        return found

    def _build_jit_symbolic_hybrid(self, method_str: str, use_sparse: bool):
        """
        Compiles a Hybrid Symbolic Jacobian.
        It generates a Numba kernel that evaluates the Jacobian entries and
        returns either a Scipy CSC Matrix (Sparse mode) or a Numpy Array (Dense mode).
        """
        cache_key = f"{method_str}_{use_sparse}"
        if hasattr(self, 'jit_jacobian_symbolic') and cache_key in self.jit_jacobian_symbolic:
            return

        print(f"--- [JIT-SD] Compiling Hybrid Symbolic Jacobian ({'SPARSE' if use_sparse else 'DENSE'}) ---")
        t0 = time.time()

        sorted_vars = self.state_vars + self.algebraic_vars
        all_params = self.problem.get_variable_parameters() + self.problem.get_constant_parameters()
        var_uid_to_idx = {v.uid: i for i, v in enumerate(sorted_vars)}

        equations = []
        base_var_uid_to_diff_var = {}
        for i, rhs in enumerate(self.state_eqs):
            sv = self.state_vars[i]
            d_term = Var(name=f"d_{sv.name}", base_var=sv)
            base_var_uid_to_diff_var[sv.uid] = d_term
            equations.append(d_term - rhs)
        equations.extend(self.algebraic_eqs)

        N = len(sorted_vars)
        n_states = len(self.state_vars)
        jac_expression, rows, cols = [], [], []
        alpha_sym = Var("alpha_scaling_factor")

        if use_sparse:
            nnz = 0
            for r, eq in enumerate(equations):
                dependencies = self._get_vars_in_expr(eq)
                if r < n_states: dependencies.add(self.state_vars[r].uid)

                for v in sorted_vars:
                    if v.uid in dependencies:
                        c = var_uid_to_idx[v.uid]
                        d_direct = eq.diff(v)
                        d_diff = Const(0)

                        if v.uid in base_var_uid_to_diff_var:
                            d_diff = eq.diff(base_var_uid_to_diff_var[v.uid])

                        final_expr = (d_direct + alpha_sym * d_diff) if not (
                                isinstance(d_diff, Const) and d_diff.value == 0) else d_direct
                        final_expr = final_expr.simplify()

                        if not (isinstance(final_expr, Const) and final_expr.value == 0):
                            jac_expression.append(final_expr)
                            rows.append(r)
                            cols.append(c)
                            nnz += 1
            print(f"   [JIT-SD] Topology Analysis: {nnz} non-zeros (Sparsity: {1.0 - nnz / (N ** 2):.2%})")
        else:
            for r, eq in enumerate(equations):
                for c, v in enumerate(sorted_vars):
                    d_direct = eq.diff(v)
                    d_diff = Const(0)
                    if v.uid in base_var_uid_to_diff_var:
                        d_diff = eq.diff(base_var_uid_to_diff_var[v.uid])
                    final_expr = d_direct + alpha_sym * d_diff
                    jac_expression.append(final_expr.simplify())

        compile_params = all_params + [alpha_sym]
        compiler = EquationCompiler(variables=sorted_vars, parameters=compile_params, method=method_str)
        func_name = f"jac_eval_{method_str}_{'sparse' if use_sparse else 'dense'}"
        kernel_py = compiler.compile(jac_expression, func_name=func_name, use_cse=True)
        kernel_jit = nb.njit(cache=False, fastmath=True)(kernel_py)

        alpha_mult = 2.0 if method_str == DynamicIntegrationMethod.Trapezoid else (1.5 if method_str == DynamicIntegrationMethod.BDF2 else 1.0)

        np_rows = np.array(rows, dtype=np.int32) if use_sparse else None
        np_cols = np.array(cols, dtype=np.int32) if use_sparse else None

        def jacobian_evaluator(states, params, history, d_history, h, history2=None):
            params_with_alpha = np.empty(len(params) + 1, dtype=np.float64)
            params_with_alpha[:-1] = params
            params_with_alpha[-1] = alpha_mult / h

            data = kernel_jit(states, params_with_alpha, history, d_history, h, history2)

            if use_sparse:
                return sp.csc_matrix((data, (np_rows, np_cols)), shape=(N, N))

            return data.reshape((N, N))

        if not hasattr(self, 'jit_jacobian_symbolic'): self.jit_jacobian_symbolic = {}
        self.jit_jacobian_symbolic[cache_key] = jacobian_evaluator
        print(f"   [JIT-SD] Compilation finished in {time.time() - t0:.4f}s")

    def simulate(self, boundary_update_fn=None) -> Tuple[Vec, Mat]:
        """
        Main JIT simulation loop using the Symbolic Differentiation (SD) backend.
        """
        t_start = time.time()
        method_str = self.method_str

        if not hasattr(self, 'jit_kernels'): self.jit_kernels = {}
        if method_str not in self.jit_kernels: self._build_jit_kernel(method_str)

        kernel_list = self.jit_kernels[method_str]

        n_eqs = self.problem.get_all_vars_number()
        n_states = self.problem.get_states_number()

        use_dense_solver = (n_eqs <= self.dense_threshold)
        self._build_jit_symbolic_hybrid(method_str, use_sparse=not use_dense_solver)
        jac_key = f"{method_str}_{not use_dense_solver}"
        current_jacobian = self.jit_jacobian_symbolic[jac_key]

        if self.verbose:
            mode_str = "DENSE" if use_dense_solver else "SPARSE"
            print(f"   [Config] System N={n_eqs}. Using {mode_str} linear solver (Threshold={self.dense_threshold}).")

        x0 = self.problem.get_x0()
        dx0 = np.zeros(n_eqs, dtype=np.float64)

        self.t[0] = self.t0
        self.y[0, :] = x0.copy()

        x_prev, dx_prev, x_prev2 = x0.copy(), dx0.copy(), x0.copy()
        x_iter = x0.copy()

        static_vals = np.array([c.value for c in self.problem.get_parameters_values()])
        ev_params = np.zeros(self.problem.get_variable_parameter_number(), dtype=np.float64)

        trace_collector = self.problem.get_newton_trace_collector()

        diag_cfg = NewtonDiagnosticsConfig(step_norm_explode=1e6, dense_cond_warn=1e12, compute_dense_cond=True,
                                           enable_fallback=True)
        dense_solve = with_newton_diagnostics(np.linalg.solve, fallback_solve=dense_lstsq_fallback,
                                              collector=trace_collector, config=diag_cfg, solver_name="dense")
        sparse_solve = with_newton_diagnostics(sp.linalg.spsolve, fallback_solve=sparse_lsqr_fallback,
                                               collector=trace_collector, config=diag_cfg, solver_name="sparse")

        if self.verbose: print(f"-> Starting JIT Simulation ({method_str}, {self.steps} steps)...")

        for i in range(self.steps):
            t_curr = self.t0 + (i + 1) * self.h
            self.t[i + 1] = t_curr

            ev_params = self.problem.def_event_params_fn(ev_params, float(t_curr))
            full_params = np.concatenate((ev_params, static_vals))

            if boundary_update_fn:
                boundary_update_fn(t_curr, x_prev, full_params)

            for k in range(15):
                ctx = NewtonSolveContext(t=float(t_curr), step_idx=int(i), newton_iter=int(k), phase="jit",
                                         method=str(method_str))

                res = np.zeros(n_eqs, dtype=np.float64)
                for kn in kernel_list:
                    kn(x_iter, full_params, x_prev, dx_prev, self.h, res, x_prev2)

                if np.linalg.norm(res, np.inf) < 1e-6: break

                J_final = current_jacobian(states=x_iter, params=full_params, history=x_prev, d_history=dx_prev,
                                           h=self.h, history2=x_prev2)

                if use_dense_solver:
                    delta = dense_solve(J_final, -res, ctx)
                else:
                    delta = sparse_solve(J_final, -res, ctx)
                x_iter += delta

            self.y[i + 1, :] = x_iter

            if method_str == DynamicIntegrationMethod.Trapezoid:
                alpha = 2.0 / self.h
                dx_prev[:n_states] = alpha * (x_iter[:n_states] - x_prev[:n_states]) - dx_prev[:n_states]
            elif method_str == DynamicIntegrationMethod.BDF2:
                x_prev2 = x_prev.copy()
            else:
                dx_prev[:n_states] = (x_iter[:n_states] - x_prev[:n_states]) / self.h

            if method_str != DynamicIntegrationMethod.BDF2: x_prev2 = x_prev.copy()
            x_prev = x_iter.copy()

        if self.verbose: print(f"JIT Finished: {time.time() - t_start:.4f}s")
        return self.t, self.y