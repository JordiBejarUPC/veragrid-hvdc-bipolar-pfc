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

    def __init__(self, problem, trajectory, h, n_states):
        """
        :param problem: The EmtProblemDae instance.
        :param trajectory: A list of (x, y) tuples representing the pre-captured limit cycle.
        :param h: The integration time step used in the simulation.
        :param n_states: Number of differential state variables (x).
        """
        self.problem = problem
        self.trajectory = trajectory
        self.h = h
        self.n_states = n_states
        self.n_total = self.problem.get_states_number() + self.problem.get_algebraic_var_number()

        self.shape = (n_states, n_states)
        self.dtype = np.dtype(np.float64)

        self.lu_solvers = []
        self._precompute_lu_factorizations()

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
        """
        Forward integration using pre-computed LU solvers.
        """
        v_curr = v0.copy()
        rhs = np.zeros(self.n_total)

        # Step-by-step integration through the periodic limit cycle using cache
        for lu in self.lu_solvers:
            rhs[:self.n_states] = v_curr

            # Fast back-substitution solving J_aug * sol = rhs
            sol = lu.solve(rhs)
            v_curr = sol[:self.n_states]

        return v_curr

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

#New Implementation System for Floquet_stochastic.
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

    def __init__(self, problem, trajectory, h, n_states):
        self.problem = problem
        self.trajectory = trajectory
        self.h = h
        self.n_states = n_states

        # Total size of the DAE system (Differential + Algebraic)
        self.n_total = self.problem.get_states_number() + self.problem.get_algebraic_var_number()

        # The operator strictly maps the differential states (x) back to themselves
        self.shape = (n_states, n_states)
        self.dtype = np.dtype(np.float64)

        # Cache for the exact LU factorizations
        self.lu_solvers = []
        self._precompute_lu_factorizations()

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
        """
        The HPC Core: Forward integration for MULTIPLE tangent vectors simultaneously.

        Args:
            X (np.ndarray): A dense block matrix of shape (n_states, p), where 'p'
                            is the number of simultaneous perturbation vectors.

        Returns:
            np.ndarray: The mapped block matrix after one full period integration.
        """
        p_cols = X.shape[1]
        X_curr = X.copy()

        # Pre-allocate a contiguous matrix for the right-hand sides to avoid memory reallocation
        rhs_block = np.zeros((self.n_total, p_cols), dtype=X.dtype)

        # Step-by-step block integration through the periodic limit cycle
        for lu in self.lu_solvers:
            # Load the current block of differential states into the RHS
            rhs_block[:self.n_states, :] = X_curr

            # Fast block back-substitution (BLAS Level 3: A * X_next = B)
            sol_block = lu.solve(rhs_block)

            # Extract the updated differential states for the next time step
            X_curr = sol_block[:self.n_states, :]

        return X_curr

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

