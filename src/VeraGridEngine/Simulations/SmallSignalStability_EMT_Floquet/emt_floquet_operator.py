# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

try:
    from emt_floquet_numba_kernels import NUMBA_AVAILABLE, apply_ak_stack_block_numba
except Exception:
    try:
        from VeraGridEngine.Simulations.SmallSignalStability_EMT_Floquet.emt_floquet_numba_kernels import (
            NUMBA_AVAILABLE, apply_ak_stack_block_numba,
        )
    except Exception:
        NUMBA_AVAILABLE = False
        apply_ak_stack_block_numba = None


class EmtFloquetOperator(spla.LinearOperator):
    """
    HPC Matrix-Free Monodromy Operator for abc-frame EMT systems.

    Optimized with LU Factorization Caching to eliminate redundant computations
    during Krylov subspace iterations (Arnoldi).
    """

    def __init__(self, problem, trajectory, h, n_states, method_str='back_euler',
                 jac_evaluator=None, static_params=None, n_event_params=0,t_trajectory=None):
        self.problem = problem
        self.trajectory = trajectory
        self.h = h
        self.n_states = n_states
        self.method_str = method_str

        if hasattr(problem, 'get_all_vars_number'):
            self.n_total = problem.get_all_vars_number()
        else:
            self.n_total = self.problem.get_states_number() + self.problem.get_algebraic_var_number()

        self.shape = (n_states, n_states)
        self.dtype = np.dtype(np.float64)

        self.lu_solvers = []

        # Pre-computing Router
        if jac_evaluator is not None and t_trajectory is not None:
            self._precompute_from_jit(jac_evaluator, static_params, n_event_params,t_trajectory)
        else:
            self._precompute_lu_factorizations()

    def _precompute_from_jit(self, jac_evaluator, static_params, n_ev_params, t_trajectory):
        full_params = np.empty(n_ev_params + len(static_params), dtype=np.float64)
        if len(static_params) > 0:
            full_params[n_ev_params:] = static_params

        ev_params = np.zeros(n_ev_params, dtype=np.float64)
        dx_dummy = np.zeros(self.n_total, dtype=np.float64)

        for i in range(1, len(self.trajectory)):
            step_k = self.trajectory[i]
            step_prev = self.trajectory[i - 1]
            step_prev2 = self.trajectory[i - 2] if i > 1 else step_prev

            x_k = step_k[0] if isinstance(step_k, tuple) else step_k
            x_prev = step_prev[0] if isinstance(step_prev, tuple) else step_prev
            x_prev2 = step_prev2[0] if isinstance(step_prev2, tuple) else step_prev2
            t_curr = t_trajectory[i] if t_trajectory is not None else (i * self.h)

            if n_ev_params > 0:
                ev_params = self.problem.def_event_params_fn(ev_params, float(t_curr))
                full_params[:n_ev_params] = ev_params

            J_sparse = jac_evaluator(states=x_k, params=full_params, history=x_prev,
                                     d_history=dx_dummy, h=self.h, history2=x_prev2)
            self.lu_solvers.append(spla.splu(J_sparse))

    def _precompute_lu_factorizations(self):
        """
        Pre-calculates SuperLU factorizations for the entire periodic trajectory.
        This reduces the cost of Arnoldi iterations from O(iters * steps * n^3)
        to O(steps * n^3 + iters * steps * n^2), an extreme HPC acceleration.
        """
        for x_k, y_k in self.trajectory:
            fx = self.problem.get_j11(x_k, y_k, self.h)
            fy = self.problem.get_j12(x_k, y_k, self.h)
            gx = self.problem.get_j21(x_k, y_k, self.h)
            gy = self.problem.get_j22(x_k, y_k, self.h)

            J_aug = sp.vstack([
                sp.hstack([fx, fy]),
                sp.hstack([gx, gy])
            ], format='csc')

            # splu requires CSC format and computes the exact LU factorization once
            self.lu_solvers.append(spla.splu(J_aug))

    def _matvec(self, v0):
        v_curr = np.zeros(self.n_total, dtype=np.float64)
        v_curr[:self.n_states] = v0

        v_prev = v_curr.copy()
        v_prev2 = v_curr.copy()
        dv_prev = np.zeros_like(v_curr)
        rhs = np.zeros_like(v_curr)

        for lu in self.lu_solvers:
            if self.method_str in ['back_euler', 'be']:
                rhs[:self.n_states] = v_prev[:self.n_states] / self.h
            elif self.method_str == 'bdf2':
                rhs[:self.n_states] = (2.0 * v_prev[:self.n_states] - 0.5 * v_prev2[:self.n_states]) / self.h
            elif self.method_str == 'trapezoidal':
                rhs[:self.n_states] = (2.0 / self.h) * v_prev[:self.n_states] + dv_prev[:self.n_states]
            else:
                rhs[:self.n_states] = v_prev[:self.n_states] / self.h

            v_curr = lu.solve(rhs)

            if self.method_str == 'trapezoidal':
                dv_prev[:self.n_states] = (2.0 / self.h) * (v_curr[:self.n_states] - v_prev[:self.n_states]) - dv_prev[
                    :self.n_states]

            v_prev2 = v_prev.copy()
            v_prev = v_curr.copy()

        return v_curr[:self.n_states]

    def _rmatvec(self, w0):
        """
        Adjoint (Backward) integration to extract Left Eigenvectors.
        Utilizes the trans='T' flag in SuperLU for zero-cost matrix transposition.
        """
        w_curr = w0.copy()
        rhs = np.zeros(self.n_total)

        # Reverse-time integration using the transposed solvers
        for lu in reversed(self.lu_solvers):
            rhs[:self.n_states] = w_curr

            # Fast back-substitution solving J_aug^T * sol = rhs
            sol = lu.solve(rhs, trans='T')
            w_curr = sol[:self.n_states]

        return w_curr

#New Implementation System for Blocks calc.
class BlockEmtFloquetOperator(spla.LinearOperator):
    """
    Advanced HPC Block Monodromy Operator for EMT Small-Signal Stability.

    This class is specifically designed to support Randomized Numerical Linear
    Algebra (RandNLA) and Block Krylov subspace methods. Unlike standard operators
    that process a single column vector at a time (BLAS Level 2), this operator
    accepts a dense block matrix (N x p) of vectors simultaneously.

    By processing multiple perturbation vectors at once, it forces the underlying
    SciPy/SuperLU backend to utilize BLAS Level 3 routines (Matrix-Matrix
    multiplication and Block Forward/Backward Substitution). This maximizes CPU
    L1/L2 cache utilization, drastically reducing the memory-bound bottlenecks
    inherent to large-scale sparse electrical networks.

    Attributes:
        problem: The underlying EMT DAE problem instance.
        trajectory: List of pre-captured steady-state tuples (x, y) over one period T.
        h (float): Integration time step.
        n_states (int): Number of differential state variables.
        lu_solvers (list): Cached SuperLU factorizations for the entire trajectory.
    """

    def __init__(self, problem, trajectory, h, n_states, method_str='back_euler',
                 jac_evaluator=None, static_params=None, n_event_params=0, t_trajectory=None):
        self.problem = problem
        self.trajectory = trajectory
        self.h = h
        self.n_states = n_states
        self.method_str = method_str

        if hasattr(problem, 'get_all_vars_number'):
            self.n_total = problem.get_all_vars_number()
        else:
            self.n_total = self.problem.get_states_number() + self.problem.get_algebraic_var_number()

        self.shape = (n_states, n_states)
        self.dtype = np.dtype(np.float64)

        self.lu_solvers = []

        if jac_evaluator is not None:
            self._precompute_from_jit(jac_evaluator, static_params, n_event_params, t_trajectory)
        else:
            self._precompute_lu_factorizations()

    def _precompute_from_jit(self, jac_evaluator, static_params, n_ev_params, t_trajectory=None):
        full_params = np.empty(n_ev_params + len(static_params), dtype=np.float64)
        if len(static_params) > 0:
            full_params[n_ev_params:] = static_params

        ev_params = np.zeros(n_ev_params, dtype=np.float64)
        dx_dummy = np.zeros(self.n_total, dtype=np.float64)

        for i in range(1, len(self.trajectory)):
            step_k = self.trajectory[i]
            step_prev = self.trajectory[i - 1]
            step_prev2 = self.trajectory[i - 2] if i > 1 else step_prev

            x_k = step_k[0] if isinstance(step_k, tuple) else step_k
            x_prev = step_prev[0] if isinstance(step_prev, tuple) else step_prev
            x_prev2 = step_prev2[0] if isinstance(step_prev2, tuple) else step_prev2
            t_curr = t_trajectory[i] if t_trajectory is not None else (i * self.h)

            if n_ev_params > 0:
                ev_params = self.problem.def_event_params_fn(ev_params, float(t_curr))
                full_params[:n_ev_params] = ev_params

            J_sparse = jac_evaluator(states=x_k, params=full_params, history=x_prev,
                                     d_history=dx_dummy, h=self.h, history2=x_prev2)

            self.lu_solvers.append(spla.splu(J_sparse))

    def _precompute_lu_factorizations(self):
        """
        Pre-calculates and caches the Sparse LU factorizations for the Jacobian
        at every time step of the periodic limit cycle.
        """
        for x_k, y_k in self.trajectory:
            # Extract discrete DAE Jacobians from the exact analytical/AD backend
            fx = self.problem.get_j11(x_k, y_k, self.h)
            fy = self.problem.get_j12(x_k, y_k, self.h)
            gx = self.problem.get_j21(x_k, y_k, self.h)
            gy = self.problem.get_j22(x_k, y_k, self.h)

            # Assemble the full augmented Jacobian block matrix
            J_aug = sp.vstack([
                sp.hstack([fx, fy]),
                sp.hstack([gx, gy])
            ], format='csc')

            # splu requires CSC format and caches the exact LU decomposition
            self.lu_solvers.append(spla.splu(J_aug))

    def _matmat(self, X):
        p_cols = X.shape[1]
        X_curr = np.zeros((self.n_total, p_cols), dtype=X.dtype)
        X_curr[:self.n_states, :] = X

        X_prev = X_curr.copy()
        X_prev2 = X_curr.copy()
        dX_prev = np.zeros_like(X_curr)
        rhs_block = np.zeros_like(X_curr)

        for lu in self.lu_solvers:
            if self.method_str in ['back_euler', 'be']:
                rhs_block[:self.n_states, :] = X_prev[:self.n_states, :] / self.h
            elif self.method_str == 'bdf2':
                rhs_block[:self.n_states, :] = (2.0 * X_prev[:self.n_states, :] - 0.5 * X_prev2[
                    :self.n_states, :]) / self.h
            elif self.method_str == 'trapezoidal':
                rhs_block[:self.n_states, :] = (2.0 / self.h) * X_prev[:self.n_states, :] + dX_prev[:self.n_states, :]
            else:
                rhs_block[:self.n_states, :] = X_prev[:self.n_states, :] / self.h

            X_curr = lu.solve(rhs_block)

            if self.method_str == 'trapezoidal':
                dX_prev[:self.n_states, :] = (2.0 / self.h) * (X_curr[:self.n_states, :] - X_prev[:self.n_states, :]) - \
                                             dX_prev[:self.n_states, :]

            X_prev2 = X_prev.copy()
            X_prev = X_curr.copy()

        return X_curr[:self.n_states, :]

    def _matvec(self, v0):
        """
        Fallback routine: If a standard solver (like scipy.sparse.linalg.eigs)
        calls this operator with a single 1D vector, it wraps it into a 2D matrix
        and routes it through the high-performance _matmat implementation.
        """
        # Reshape to (N, 1), compute via block logic, and flatten back to 1D
        return self._matmat(v0.reshape(-1, 1)).flatten()


class AkStackBlockEmtFloquetOperator(spla.LinearOperator):
    """
    Monodromy operator from an explicit stack of state-transition matrices A_k.

    This is the preferred path for EMT/Floquet benchmarking when the EMT engine can
    expose the per-step linearised state map

        x_{k+1} = A_k x_k

    for one limit-cycle period. The operator applies

        \Phi = A_{M-1} \cdots A_1 A_0

    on vectors or blocks. When Numba is available and ``use_numba=True``, the block
    path is JIT-compiled to reduce Python overhead in repeated Arnoldi calls.
    """

    def __init__(self, Ak_stack: np.ndarray, use_numba: bool = True):
        Ak = np.asarray(Ak_stack, dtype=np.float64, order='C')
        if Ak.ndim != 3 or Ak.shape[1] != Ak.shape[2]:
            raise ValueError(
                f"Ak_stack must have shape (n_steps, n, n); got {Ak.shape}"
            )
        self.Ak_stack = Ak
        self.n_steps = int(Ak.shape[0])
        self.n_states = int(Ak.shape[1])
        self.use_numba = bool(use_numba and NUMBA_AVAILABLE and apply_ak_stack_block_numba is not None)
        super().__init__(dtype=np.float64, shape=(self.n_states, self.n_states))

    def _matvec(self, x: np.ndarray) -> np.ndarray:
        X = np.asarray(x, dtype=np.float64).reshape(-1, 1)
        Y = self._matmat(X)
        return Y[:, 0]

    def _matmat(self, X: np.ndarray) -> np.ndarray:
        Xf = np.asarray(X, dtype=np.float64, order='C')
        if self.use_numba:
            return apply_ak_stack_block_numba(self.Ak_stack, Xf)

        Y = Xf
        for k in range(self.n_steps):
            Y = self.Ak_stack[k] @ Y
        return np.asarray(Y, dtype=np.float64, order='C')

    def matmat(self, X: np.ndarray) -> np.ndarray:
        return self._matmat(X)

