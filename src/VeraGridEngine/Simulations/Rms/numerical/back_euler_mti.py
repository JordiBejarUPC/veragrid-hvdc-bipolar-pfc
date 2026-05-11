# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from itertools import product

import numpy as np
import scipy.sparse as sp

from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.problems.rms_problem_MTI import RmsProblemMTI
from VeraGridEngine.basic_structures import Mat, Vec


class BackEulerImplicitIntegrationMTI(BackEulerImplicitIntegration):
    """
    Backward Euler variant with MTI inequality/mode checks.

    This solver keeps the same Newton/Jacobian structure as
    ``BackEulerImplicitIntegration`` and adds a post-Newton MTI feasibility
    gate based on inequality residuals ``G <= tol``.
    """

    def __init__(
        self,
        problem: RmsProblemMTI,
        t0: float,
        t_end: float,
        h: float,
        max_iter: int,
        tolerance: float = 1e-7,
        inequality_tolerance: float = 1e-9,
    ):
        super().__init__(
            problem=problem,
            t0=t0,
            t_end=t_end,
            h=h,
            max_iter=max_iter,
            tolerance=tolerance,
        )
        self.problem: RmsProblemMTI = problem
        self.inequality_tolerance = inequality_tolerance
        self.z: Mat = np.empty((self.steps + 1, 0), dtype=float)

    def _newton_step(self, x_new: Vec, x_prev: Vec, dx: Vec, h_eff: float) -> tuple[Vec, float]:
        rhs = self.problem.compute_mti_equalities(x_new, dx, x_prev, h_eff)
        residual = float(np.linalg.norm(rhs, np.inf))
        if residual < self.tol:
            return x_new, residual

        jf = self._jacobian_implicit(x_new, dx, h_eff)
        delta = sp.linalg.spsolve(jf, -rhs)
        if not np.all(np.isfinite(delta)):
            delta, *_ = sp.linalg.lsqr(jf, -rhs)
        if not np.all(np.isfinite(delta)):
            raise ValueError("Failed to compute a finite Newton update for MTI step.")

        return x_new + delta, residual

    def _solve_continuous_for_fixed_boolean(self, x_seed: Vec, x_prev: Vec, dx_last: Vec) -> tuple[bool, Vec, Vec, float]:
        x_new = x_seed.copy()
        residual = np.inf
        dx_out = dx_last.copy()

        for _ in range(self.max_iter_0):
            if np.allclose(dx_last, 0.0):
                dx = np.zeros_like(dx_last)
            else:
                dx = self.problem.get_dx(x_new, x_prev, dx_last, self.h)

            x_new, residual = self._newton_step(x_new=x_new, x_prev=x_prev, dx=dx, h_eff=self.h)
            dx_out = dx.copy()
            if residual < self.tol:
                return True, x_new, dx_out, residual

        return False, x_new, dx_out, residual

    @staticmethod
    def _hamming_distance(a: Vec, b: Vec) -> int:
        return int(np.sum(np.asarray(a, dtype=int) != np.asarray(b, dtype=int)))

    def _enumerate_boolean_candidates(self, z_prev: Vec) -> list[np.ndarray]:
        n_bool = len(z_prev)
        if n_bool == 0:
            return [np.zeros(0, dtype=float)]
        if n_bool == 1:
            return [np.array([0.0]), np.array([1.0])]

        candidates = [np.asarray(bits, dtype=float) for bits in product((0.0, 1.0), repeat=n_bool)]
        candidates.sort(key=lambda zc: self._hamming_distance(zc, z_prev))
        return candidates

    def _direct_boolean_test_single(self, x_prev: Vec, dx_last: Vec) -> np.ndarray:
        z0 = np.array([0.0], dtype=float)
        self.problem.set_mti_boolean_state(z0)
        g0 = self.problem.compute_mti_inequalities(x_prev, dx_last, x_prev, self.h)
        if g0.size == 0:
            return z0
        if float(np.max(g0)) <= self.inequality_tolerance:
            return z0
        return np.array([1.0], dtype=float)

    def simulate(self):
        converged = False
        well_initialized = True

        x0: Vec = self.problem.get_x0()
        dx0: Vec = np.zeros(self.problem.get_diff_var_number(), dtype=float)

        self.t[0] = self.t0
        self.y[0, :] = x0.copy()

        z0 = self.problem.update_mti_boolean_state(x0, dx0, x0, self.h)
        if z0 is None:
            z0 = np.zeros(0, dtype=float)
        self.z = np.empty((self.steps + 1, len(z0)), dtype=float)
        if len(z0) > 0:
            self.z[0, :] = z0

        dx_last = dx0.copy()
        z_prev = z0.copy()

        for step_idx in range(self.steps):
            self.problem.report_progress2(step_idx, self.steps)

            t_prev = self.t[step_idx]
            t_curr = t_prev + self.h

            x_prev = self.y[step_idx, :].copy()
            converged = False
            try:
                self.problem.update_variable_params(t=t_prev, x_snapshot=x_prev)
            except TypeError:
                self.problem.update_variable_params(t_prev)
            try:
                self.problem.update(t_curr, x_prev, self.problem._variable_parameters_values)
            except Exception:
                pass

            bool_indices = self.problem.get_mti_boolean_parameter_indices()
            if len(bool_indices) == 1:
                candidates = [self._direct_boolean_test_single(x_prev=x_prev, dx_last=dx_last)]
            else:
                candidates = self._enumerate_boolean_candidates(z_prev)

            accepted_x: Vec | None = None
            accepted_dx: Vec | None = None
            accepted_z: Vec | None = None

            for z_candidate in candidates:
                self.problem.set_mti_boolean_state(z_candidate)

                ok, x_try, dx_try, _ = self._solve_continuous_for_fixed_boolean(
                    x_seed=x_prev,
                    x_prev=x_prev,
                    dx_last=dx_last,
                )
                if not ok:
                    continue

                g_try = self.problem.compute_mti_inequalities(x_try, dx_try, x_prev, self.h)
                if self.problem.inequalities_satisfied(g_try, tol=self.inequality_tolerance):
                    accepted_x = x_try
                    accepted_dx = dx_try
                    accepted_z = z_candidate
                    converged = True
                    break

            if not converged or accepted_x is None or accepted_dx is None:
                if step_idx == 0:
                    well_initialized = False
                break

            self.y[step_idx + 1, :] = accepted_x
            self.t[step_idx + 1] = t_curr
            dx_last = accepted_dx

            if accepted_z is not None and len(accepted_z) > 0:
                self.z[step_idx + 1, :] = accepted_z
                z_prev = np.asarray(accepted_z, dtype=float)
            else:
                z_prev = np.zeros(0, dtype=float)

        return self.t, self.y, well_initialized, converged
