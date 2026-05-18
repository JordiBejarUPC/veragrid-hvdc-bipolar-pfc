# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
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
        self.debug = os.getenv("RMS_MTI_DEBUG", "0").strip() in ("1", "true", "True", "yes", "on")
        self.compare = os.getenv("RMS_MTI_COMPARE", "0").strip() in ("1", "true", "True", "yes", "on")

    def _newton_step(self, x_new: Vec, x_prev: Vec, dx: Vec, h_eff: float) -> tuple[Vec, float]:
        rhs = self.problem.compute_mti_equalities(x_new, dx, x_prev, h_eff)
        if rhs.size == 0:
            return x_new, 0.0
        residual = float(np.linalg.norm(rhs, np.inf))
        if residual < self.tol:
            return x_new, residual

        jf = self._jacobian_implicit(x_new, dx, h_eff)
        delta = sp.linalg.spsolve(jf, -rhs)
        if not np.all(np.isfinite(delta)):
            delta, *_ = sp.linalg.lsqr(jf, -rhs)
        if not np.all(np.isfinite(delta)):
            return x_new, np.inf

        x_next = x_new + delta
        if not np.all(np.isfinite(x_next)):
            return x_new, np.inf
        return x_next, residual

    def _solve_continuous_for_fixed_boolean(
        self,
        x_seed: Vec,
        x_prev: Vec,
        dx_last: Vec,
        h_eff: float,
        force_zero_dx: bool = False,
    ) -> tuple[bool, Vec, Vec, float]:
        x_new = x_seed.copy()
        residual = np.inf
        dx_out = dx_last.copy()

        for _ in range(self.max_iter_0):
            if force_zero_dx:
                dx = np.zeros_like(dx_last)
            else:
                dx = self.problem.get_dx(x_new, x_prev, dx_last, h_eff)

            rhs = self.problem.compute_mti_equalities(x_new, dx, x_prev, h_eff)
            residual = float(np.linalg.norm(rhs, np.inf)) if rhs.size > 0 else 0.0
            if residual < max(self.tol, 1e-6):
                return True, x_new, dx, residual

            x_new, _ = self._newton_step(x_new=x_new, x_prev=x_prev, dx=dx, h_eff=h_eff)
            if not np.all(np.isfinite(x_new)):
                return False, x_new, dx, np.inf
            dx_out = dx.copy()

        return False, x_new, dx_out, residual

    def _solve_continuous_with_fallback(
        self,
        x_prev: Vec,
        dx_last: Vec,
        h_eff: float,
        force_zero_dx: bool = False,
    ) -> tuple[bool, Vec, Vec, float]:
        seeds = [x_prev.copy()]
        if x_prev.size > 0:
            seeds.append(np.zeros_like(x_prev))
            seeds.append(np.ones_like(x_prev))

        best = (False, x_prev.copy(), dx_last.copy(), np.inf)
        for seed in seeds:
            ok, x_try, dx_try, res = self._solve_continuous_for_fixed_boolean(
                seed,
                x_prev,
                dx_last,
                h_eff,
                force_zero_dx=force_zero_dx,
            )
            if ok:
                return True, x_try, dx_try, res
            if res < best[3]:
                best = (ok, x_try, dx_try, res)
        return best

    def _solve_plain_dae_for_seed(
        self,
        x_seed: Vec,
        x_prev: Vec,
        dx_last: Vec,
        h_eff: float,
        force_zero_dx: bool = False,
    ) -> tuple[bool, Vec, Vec, float]:
        x_new = x_seed.copy()
        residual = np.inf
        dx_out = dx_last.copy()

        for _ in range(self.max_iter_0):
            if force_zero_dx:
                dx = np.zeros_like(dx_last)
            else:
                dx = self.problem.get_dx(x_new, x_prev, dx_last, h_eff)

            rhs = self._rhs_implicit(x_new, dx, x_prev, h_eff)
            residual = float(np.linalg.norm(rhs, np.inf))
            if residual < max(self.tol, 1e-6):
                return True, x_new, dx, residual

            jf = self._jacobian_implicit(x_new, dx, h_eff)
            delta = sp.linalg.spsolve(jf, -rhs)
            if not np.all(np.isfinite(delta)):
                delta, *_ = sp.linalg.lsqr(jf, -rhs)
            if not np.all(np.isfinite(delta)):
                if self.debug:
                    print("[MTI] plain DAE linear solve returned non-finite delta")
                return False, x_new, dx, np.inf

            x_new = x_new + delta
            if not np.all(np.isfinite(x_new)):
                if self.debug:
                    print("[MTI] plain DAE update produced non-finite x")
                return False, x_new, dx, np.inf

            dx_out = dx.copy()

        return False, x_new, dx_out, residual

    def _solve_plain_dae(
        self,
        x_prev: Vec,
        dx_last: Vec,
        h_eff: float,
        force_zero_dx: bool = False,
    ) -> tuple[bool, Vec, Vec, float]:
        # Keep behavior aligned with BackEulerImplicitIntegration:
        # start Newton from previous converged point only.
        return self._solve_plain_dae_for_seed(
            x_prev.copy(),
            x_prev,
            dx_last,
            h_eff,
            force_zero_dx=force_zero_dx,
        )

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

    @staticmethod
    def _merge_boolean_vectors(base_z: Vec, positions: list[int], values: Vec) -> np.ndarray:
        z = np.asarray(base_z, dtype=float).copy()
        for k, pos in enumerate(positions):
            z[pos] = float(values[k])
        return z

    @staticmethod
    def _to_binary_boolean_state(z: Vec) -> np.ndarray:
        z_arr = np.asarray(z, dtype=float)
        if z_arr.size == 0:
            return z_arr.copy()
        return (z_arr >= 0.5).astype(float)

    def _direct_boolean_test_single(self, x_prev: Vec, dx_last: Vec) -> np.ndarray:
        z0 = np.array([0.0], dtype=float)
        self.problem.set_mti_boolean_state(z0)
        guard0 = self.problem.evaluate_boolean_guard(bool_position=0, x=x_prev, dx=dx_last)
        if guard0 is not None:
            if guard0 <= self.inequality_tolerance:
                return np.array([1.0], dtype=float)
            return z0

        g0 = self.problem.compute_mti_inequalities(x_prev, dx_last, x_prev, self.h)
        if g0.size == 0 or float(np.max(g0)) <= self.inequality_tolerance:
            return np.array([1.0], dtype=float)
        return z0

    def _resolve_direct_booleans(self, z_prev: Vec, x_prev: Vec, dx_last: Vec, direct_positions: list[int]) -> np.ndarray:
        z = np.asarray(z_prev, dtype=float).copy()
        for pos in direct_positions:
            g0 = None
            z_try0 = z.copy()
            z_try0[pos] = 0.0
            self.problem.set_mti_boolean_state(z_try0)
            guard0 = self.problem.evaluate_boolean_guard(bool_position=pos, x=x_prev, dx=dx_last)
            if guard0 is None:
                g0 = self.problem.compute_mti_inequalities(x_prev, dx_last, x_prev, self.h)
            if guard0 is not None:
                if guard0 <= self.inequality_tolerance:
                    z[pos] = 1.0
                else:
                    z[pos] = 0.0
            else:
                if g0.size == 0 or float(np.max(g0)) <= self.inequality_tolerance:
                    z[pos] = 1.0
                else:
                    z[pos] = 0.0
        return z

    def simulate(self):
        converged = False
        well_initialized = True

        x0: Vec = self.problem.get_x0()
        dx0: Vec = np.zeros(self.problem.get_diff_var_number(), dtype=float)

        self.t[0] = self.t0
        self.y[0, :] = x0.copy()

        # Initialization quality is assessed from algebraic consistency at t0,
        # not by whether the first dynamic integration step converges.
        try:
            f0_alg = np.asarray(self.problem.rhs_algebraic(x0, dx0), dtype=float)
            if f0_alg.size > 0:
                r0 = float(np.linalg.norm(f0_alg, np.inf))
                well_initialized = bool(np.isfinite(r0) and r0 <= max(self.tol, 1e-6))
        except Exception:
            well_initialized = False

        z0 = self.problem.update_mti_boolean_state(x0, dx0, x0, self.h)
        if z0 is None:
            z0 = np.zeros(0, dtype=float)
        n_bool_from_problem = len(self.problem.get_mti_boolean_parameter_indices())
        if len(z0) == 0 and n_bool_from_problem > 0:
            z0 = np.zeros(n_bool_from_problem, dtype=float)
            if self.problem._variable_parameters_values is not None:
                for k, idx in enumerate(self.problem.get_mti_boolean_parameter_indices()):
                    z0[k] = float(self.problem._variable_parameters_values[idx])
        z0 = self._to_binary_boolean_state(z0)
        self.z = np.full((self.steps + 1, len(z0)), np.nan, dtype=float)
        if len(z0) > 0:
            self.z[0, :] = z0

        dx_last = dx0.copy()
        z_prev = z0.copy()
        last_completed_idx = 0

        for step_idx in range(self.steps):
            self.problem.report_progress2(step_idx, self.steps)

            t_prev = self.t[step_idx]
            t_macro_target = t_prev + self.h

            x_prev = self.y[step_idx, :].copy()
            x_local = x_prev.copy()
            t_local_prev = t_prev
            converged = False
            is_first_local_step = True
            force_zero_dx = bool(step_idx == 0)

            while t_local_prev < (t_macro_target - 1e-15):
                forced_event_time: float | None = self.problem.get_next_forced_event_time(
                    t_local_prev,
                    t_macro_target,
                )
                if forced_event_time is None:
                    t_curr = t_macro_target
                else:
                    t_curr = forced_event_time

                h_eff = t_curr - t_local_prev
                if h_eff <= 0.0:
                    break

                try:
                    self.problem.update_variable_params(t=t_local_prev, x_snapshot=x_local)
                except TypeError:
                    self.problem.update_variable_params(t_local_prev)
                try:
                    self.problem.update(t_curr, x_local, self.problem._variable_parameters_values)
                except Exception:
                    pass

                bool_indices = self.problem.get_mti_boolean_parameter_indices()
                n_bool = len(bool_indices)
                if n_bool == 0:
                    # No-boolean path: use plain DAE solve directly.
                    ok_dae, x_dae, dx_dae, _ = self._solve_plain_dae(
                        x_prev=x_local,
                        dx_last=dx_last,
                        h_eff=h_eff,
                        force_zero_dx=force_zero_dx and is_first_local_step,
                    )
                    if not ok_dae:
                        if self.debug:
                            print(f"[MTI] no-bool plain DAE failed at step={step_idx} t={t_curr:.6f}")
                        break
                    x_local = x_dae
                    dx_last = dx_dae
                    t_local_prev = t_curr
                    is_first_local_step = False
                    converged = True
                    continue
                else:
                    direct_positions, coupled_positions = self.problem.split_direct_and_coupled_booleans()
                    z_direct = self._resolve_direct_booleans(z_prev, x_local, dx_last, direct_positions)

                    if len(coupled_positions) == 0:
                        candidates = [z_direct]
                    else:
                        z_prev_coupled = np.asarray([z_prev[p] for p in coupled_positions], dtype=float)
                        coupled_candidates = self._enumerate_boolean_candidates(z_prev_coupled)
                        candidates = [self._merge_boolean_vectors(z_direct, coupled_positions, c) for c in coupled_candidates]

                accepted_x: Vec | None = None
                accepted_dx: Vec | None = None
                accepted_z: Vec | None = None
                best_fail_res = np.inf
                best_fail_x = x_local.copy()
                best_fail_dx = dx_last.copy()

                for z_candidate in candidates:
                    self.problem.set_mti_boolean_state(z_candidate)

                    ok, x_try, dx_try, res_try = self._solve_continuous_with_fallback(
                        x_prev=x_local,
                        dx_last=dx_last,
                        h_eff=h_eff,
                        force_zero_dx=force_zero_dx and is_first_local_step,
                    )
                    if not ok:
                        if np.isfinite(res_try) and res_try < best_fail_res:
                            best_fail_res = res_try
                            best_fail_x = x_try
                            best_fail_dx = dx_try
                        continue

                    g_try = self.problem.compute_mti_inequalities(x_try, dx_try, x_local, h_eff)
                    if self.problem.inequalities_satisfied(g_try, tol=self.inequality_tolerance):
                        accepted_x = x_try
                        accepted_dx = dx_try
                        accepted_z = z_candidate
                        converged = True
                        break

                if not converged or accepted_x is None or accepted_dx is None:
                    ok_dae, x_dae, dx_dae, res_dae = self._solve_plain_dae(
                        x_prev=x_local,
                        dx_last=dx_last,
                        h_eff=h_eff,
                        force_zero_dx=force_zero_dx and is_first_local_step,
                    )
                    if ok_dae:
                        accepted_x = x_dae
                        accepted_dx = dx_dae
                        accepted_z = self.problem.update_mti_boolean_state(x_dae, dx_dae, x_local, h_eff)
                        if accepted_z is not None:
                            accepted_z = self._to_binary_boolean_state(accepted_z)
                        converged = True
                    if np.isfinite(res_dae) and res_dae < best_fail_res:
                        best_fail_res = res_dae
                        best_fail_x = x_dae
                        best_fail_dx = dx_dae

                if not converged or accepted_x is None or accepted_dx is None:
                    if self.compare:
                        f_mti = self.problem.compute_mti_equalities(best_fail_x, best_fail_dx, x_local, h_eff)
                        f_dae = self._rhs_implicit(best_fail_x, best_fail_dx, x_local, h_eff)
                        n_mti = float(np.linalg.norm(f_mti, np.inf)) if f_mti.size > 0 else 0.0
                        n_dae = float(np.linalg.norm(f_dae, np.inf)) if f_dae.size > 0 else 0.0
                        diff = float(np.linalg.norm(np.asarray(f_mti) - np.asarray(f_dae), np.inf)) if f_mti.size == f_dae.size else np.inf
                        j = self._jacobian_implicit(best_fail_x, best_fail_dx, h_eff)
                        j_dense = j.toarray() if sp.issparse(j) else np.asarray(j)
                        rank = int(np.linalg.matrix_rank(j_dense))
                        cond = float(np.linalg.cond(j_dense)) if j_dense.size > 0 else np.nan
                        print(
                            f"[MTI-COMPARE] step={step_idx} t={t_curr:.6f} "
                            f"||F_mti||inf={n_mti:.3e} ||F_dae||inf={n_dae:.3e} "
                            f"||F_mti-F_dae||inf={diff:.3e} rank(J)={rank}/{j_dense.shape[0]} cond(J)={cond:.3e}"
                        )
                    break

                x_local = accepted_x
                dx_last = accepted_dx
                t_local_prev = t_curr
                is_first_local_step = False
                if accepted_z is not None and len(accepted_z) > 0:
                    z_prev = np.asarray(accepted_z, dtype=float)
                else:
                    z_prev = np.zeros(0, dtype=float)

            if t_local_prev < (t_macro_target - 1e-15):
                break

            self.y[step_idx + 1, :] = x_local
            self.t[step_idx + 1] = t_macro_target
            last_completed_idx = step_idx + 1

            if len(z_prev) > 0:
                self.z[step_idx + 1, :] = z_prev
            else:
                z_prev = np.zeros(0, dtype=float)

        return self.t[: last_completed_idx + 1], self.y[: last_completed_idx + 1, :], well_initialized, converged
