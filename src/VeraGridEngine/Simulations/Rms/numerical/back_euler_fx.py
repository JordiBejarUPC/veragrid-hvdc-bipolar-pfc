# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import scipy.sparse as sp
import time
import scipy.sparse as sp
from scipy.sparse import csc_matrix

from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Utils.Sparse.csc import pack_4_by_4_scipy
from VeraGridEngine.basic_structures import Vec, Mat
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate


class BackEulerImplicitIntegration:

    def __init__(self,
                 problem: RmsProblemDae,
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

    def _rhs_implicit(self,
                      x: Vec,
                      dx: Vec,
                      xn: Vec,
                      h: float) -> Vec:
        """
        Return 𝑑x/dt given the current *state* vector.
        :param x: get the right-hand-side give a state vector
        :param dx:
        :param xn:
        :return f_state_update or f_algeb
        """
        f_algeb = self.problem.rhs_algebraic(x, dx)

        if self.problem.get_states_number() > 0:
            f_state = self.problem.rhs_state(x, dx)
            f_state_update = x[:self.problem.get_states_number()] - xn[:self.problem.get_states_number()] - h * f_state
            return np.r_[f_state_update, f_algeb]

        else:
            return f_algeb

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

    def simulate(self):
        """

        :return:
        """
        x0: Vec = self.problem.get_x0()

        # we assume steady state
        dx0: Vec = np.zeros(self.problem.get_diff_var_number(), dtype=float)


        # timing accumulators
        timings = {
            "jacobian_time": 0.0,
            "rhs_time": 0.0,
            "lag_update_time": 0.0,
            "linear_solver_time": 0.0,
            "initial_step_time": 0.0,
        }

        self.t[0] = self.t0
        self.y[0, :] = x0.copy()
        dx = dx0.copy()
        dx_last = dx0.copy()
        x_new = x0.copy()
        residual = 0.0

        for step_idx in range(self.steps):

            discontinuity = False
            converged = False
            n_iter = 0
            current_time = self.t[step_idx]

            self.problem.update_variable_params(t=current_time)

            if step_idx > 4998:
                print("")

            if step_idx == 0:
                tol = 1e-7
                xn = x0.copy()
            else:
                xn = self.y[step_idx, :]
                tol = 1e-7

            while not converged and n_iter < 1e5:
                if step_idx == 0:
                    dx = dx0.copy()
                else:
                    dx = self.problem.get_dx(x_new, xn, dx_last, self.h)

                # ---------------- lag update ----------------
                lag_update_start = time.time()
                lag_update_end = time.time()
                timings["lag_update_time"] += lag_update_end - lag_update_start
                # ------------------------------------------------

                if discontinuity:
                    tol = 1e-8
                    max_iter = 5e5


                # ---------------- rhs calculation ----------------
                rhs_start = time.time()
                rhs = self._rhs_implicit(x_new, dx, xn, self.h)

                # print(rhs)
                rhs_end = time.time()
                timings["rhs_time"] += rhs_end - rhs_start
                # -------------------------------------------------

                # recompute Jacobian for next iteration
                jac_start = time.time()

                # Jf = self.jacobian_implicit(xnew_lags, params_current, h)
                jac_end = time.time()

                if step_idx == 0:
                    _ = 0
                #     # print(f'jacobian time is {(jac_end - jac_start)}')

                timings["jacobian_time"] += jac_end - jac_start

                residual = np.linalg.norm(rhs, np.inf)
                converged = residual < tol
                Jf = self._jacobian_implicit(x_new, dx, self.h)

                if step_idx == 0:
                    Jf = self._jacobian_implicit(x_new, dx, self.h)
                    delta = sp.linalg.spsolve(Jf, -rhs)
                    if converged:
                        print("System well initialized.")
                        print(f"x is {x_new}")
                    else:
                        print(f"System bad initialized. DAE resiudal is {residual}.")
                        print(f'rhs is {rhs}')
                        non_zero_indexes = np.where(np.abs(rhs) > 1e-7)[0]
                        all_eq = self.problem._state_eqs + self.problem._algebraic_eqs
                        print("eqs are")
                        for i in non_zero_indexes:
                            eq = all_eq[i]
                            print(f"eq {eq} with error {rhs[i]}")
                        exit()
                else:
                    max_iter = 1e5

                if converged:
                    break
                solved = False
                linear_start = time.time()
                delta = sp.linalg.spsolve(Jf, -rhs)
                linear_end = time.time()
                timings["linear_solver_time"] += linear_end - linear_start
                solved = np.all(np.isfinite(delta))

                if not solved:
                    delta, *_ = sp.linalg.lsqr(Jf, -rhs)
                    solved = np.all(np.isfinite(delta))
                    u, s, vh = np.linalg.svd(Jf.toarray() if sp.issparse(Jf) else Jf)
                    singular_dirs = np.where(s < tol)[0]
                    for i in singular_dirs:
                        v = vh.T[:, i]  # variable-space vector
                        abs_v = np.abs(v)
                        dominant_idx = np.argsort(abs_v)[::-1][:5]  # top 5 vars
                        print(f"\nSingular direction {i}, σ={s[i]:.3e}")
                        for j in dominant_idx:
                            if j < self.problem.get_algebraic_var_number():
                                algeb_vars = self.problem.get_algebraic_vars
                                var_name = algeb_vars[j].name
                                print(f"  {var_name:20s} {v[j]:+.3e}")
                    print("Using LSQR")

                if not solved:
                    nan_indices = np.where(np.isnan(rhs))[0]
                    # nan_indices = np.where(np.abs(rhs) > 1e-2)[0]
                    nan_eqs = [self.problem._algebraic_eqs[i] for i in nan_indices]
                    print(f'Jf is {Jf}')
                    raise ValueError(
                        f"spsolve returned non-finite values (NaN or Inf).\n"
                        f"delta = {delta}\n"
                        f"rhs = {rhs}\n"
                        f"Jacobian shape = {Jf.shape}\n"
                        f"NaNs found at indices {nan_indices.tolist()} in equations:\n{nan_eqs}",
                    )

                if not solved:
                    raise RuntimeError("Failed to solve linear system even with regularization.")

                x_new += delta
                n_iter += 1

            if converged:
                # if step_idx == 0:
                #     initial_step_end = time.time()
                #     timings['initial_step_time'] = initial_step_end - initial_step_end
                #     print(f'diff residual is {np.linalg.norm(x0[:self._n_alg] - x_new[:self._n_alg])}')

                lag_update_start = time.time()
                print(f'converged is {converged} at step {step_idx} and iter {n_iter}')

                if discontinuity:
                    _ = 0
                    self.y[step_idx + 1, :] = x_new
                else:
                    self.y[step_idx + 1, :] = x_new

                self.t[step_idx + 1] = self.t[step_idx] + self.h

                dx_last = dx.copy()
                lag_update_end = time.time()
                timings["lag_update_time"] += lag_update_end - lag_update_start

            else:
                print(f"Failed to converge at step {step_idx} and n_iter is {n_iter}")
                print(f'Residual is {residual}')
                break

        return self.t, self.y


