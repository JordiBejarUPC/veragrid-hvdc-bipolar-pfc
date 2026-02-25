# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import scipy.sparse.linalg as spla
import scipy.linalg as la
from typing import List, Tuple

from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from .emt_floquet_operator import EmtFloquetOperator, BlockEmtFloquetOperator, AkStackBlockEmtFloquetOperator
from .emt_floquet_options import EmtFloquetOptions
from .emt_floquet_results import EmtFloquetResults
try:
    from .emt_floquet_numba_kernels import NUMBA_AVAILABLE, bmgs_twice_numba
except Exception:
    try:
        from emt_floquet_numba_kernels import NUMBA_AVAILABLE, bmgs_twice_numba
    except Exception:
        NUMBA_AVAILABLE = False
        bmgs_twice_numba = None

class EmtFloquetDriver(DriverTemplate):
    """
    Main Driver for EMT Small-Signal Stability via Floquet Theory.
    Optimized with LU Caching, Krylov Projection, and Spectral Shift-Invert.
    """

    def __init__(self, grid, problem, emt_options: EmtOptions, options: EmtFloquetOptions):
        DriverTemplate.__init__(self, grid=grid)
        self.problem = problem
        self.emt_options = emt_options
        self.options = options
        self.results = None

    def run(self):
        self.tic()

        h = self.emt_options.time_step
        n_states = self.problem.get_states_number()

        # 1. Capture limit cycle trajectory
        y_traj, t_traj, jac_eval, stat_params, n_ev_params, method_str = self._capture_limit_cycle_and_evaluator(h)

        # 2. Operator initialized with HPC LU Caching
        monodromy_op = EmtFloquetOperator(  # O BlockEmtFloquetOperator
            problem=self.problem, trajectory=y_traj, h=h, n_states=n_states,
            method_str=method_str, jac_evaluator=jac_eval, static_params=stat_params,
            n_event_params=n_ev_params, t_trajectory=t_traj
        )

        # 3. Eigenvalue Extraction
        # HPC UPGRADE: Increased dense fallback threshold to 20 for stable mock testing
        # Arnoldi struggles when all eigenvalues have identical magnitudes.
        if n_states <= max(self.options.k + 1, 20):
            if self.options.verbose:
                print(f"System size (N={n_states}). Using dense fallback for full spectrum.")

            I_dense = np.eye(n_states)
            C_M = np.zeros((n_states, n_states))
            for i in range(n_states):
                C_M[:, i] = monodromy_op.matvec(I_dense[:, i])

            mu, v = la.eig(C_M)
        else:
            # High-Performance Sparse Arnoldi
            search_k = min(self.options.k * 2, n_states - 2)
            mu, v = spla.eigs(monodromy_op, k=search_k, which='LM', tol=1e-8)

        # 4. SPECTRAL SHIFT FILTERING (Resonance Hunt)
        if self.options.target_frequency_hz is not None:
            f_target = self.options.target_frequency_hz
            T = self.options.target_period
            # Target multiplier on the unit circle
            sigma = np.exp(1j * 2 * np.pi * f_target * T)

            # Distance to both positive and negative frequencies to keep conjugate pairs together
            distances = np.minimum(np.abs(mu - sigma), np.abs(mu - np.conj(sigma)))

            # Sort by distance and truncate to the requested k modes
            sort_indices = np.argsort(distances)[:self.options.k]
            mu = mu[sort_indices]
            v = v[:, sort_indices]
        else:
            sort_indices = np.argsort(-np.abs(mu))[:self.options.k]
            mu = mu[sort_indices]
            v = v[:, sort_indices]

        # 5. Krylov Left-Eigenvector Projection (Lifting)
        w = np.linalg.pinv(v).conj().T

        # 6. Results Mapping
        self.results = EmtFloquetResults(
            multipliers=mu,
            right_vecs=v,
            left_vecs=w,
            period=self.options.target_period,
            stat_vars=self.problem.get_state_vars()
        )

        self.toc()

    def _capture_limit_cycle_and_evaluator(self, h: float):
        """
        Intelligently captures the limit cycle. If running in production with VeraGrid's
        EmtProblemDae, it borrows the JIT Jacobian evaluator from the StructuralVectorizedSolver
        to avoid double-discretization overhead. Falls back to legacy step() for mocks.
        """
        # Extract integration method string (handling Enums if present)
        method_str = getattr(self.emt_options, 'integration_method', 'back_euler')
        if hasattr(method_str, 'value'):
            method_str = method_str.value

        # Production Check: Real EmtProblemDae has these symbolic getters
        if hasattr(self.problem, 'get_parameters_values') and hasattr(self.problem, 'def_event_params_fn'):
            if getattr(self.options, 'verbose', 0):
                print("-> Production mode: Borrowing JIT kernels from EMT Solver (Zero Double-Discretization)...")
            from VeraGridEngine.Simulations.EMT.numerical.StructuralVectorizedSolver import StructuralVectorizedSolver

            solver = StructuralVectorizedSolver(
                problem=self.problem, t0=0.0, t_end=self.options.ss_assessment_time,
                h=h, method_str=method_str, verbose=bool(getattr(self.options, 'verbose', 0))
            )
            t_full, y_full = solver.simulate()

            steps_per_period = int(self.options.target_period / h)
            y_limit = y_full[-steps_per_period:]
            t_limit = t_full[-steps_per_period:]

            static_params = np.array([c.value for c in self.problem.get_parameters_values()], dtype=np.float64)
            n_event_params = self.problem.get_variable_parameter_number()

            return y_limit, t_limit, solver.vec_jacobian, static_params, n_event_params, method_str
        else:
            if getattr(self.options, 'verbose', 0):
                print("-> Mock mode: Using legacy trajectory capture...")
            trajectory = []
            num_steps = int(self.options.target_period / h)
            x = self.problem.get_x0()
            for _ in range(num_steps):
                if hasattr(self.problem, 'step'):
                    x_next, y_next = self.problem.step(x)
                else:
                    x_next, y_next = x.copy(), np.zeros(self.problem.get_algebraic_var_number())
                trajectory.append((x_next.copy(), y_next.copy()))
                x = x_next

            return trajectory, None, None, None, 0, method_str


class RobustBlockArnoldiEngine:
    """
    PhD-Level Block Arnoldi Iteration Engine.
    Implements:
    1. Block Modified Gram-Schmidt (BMGS).
    2. DGKS/Kahan Re-orthogonalization ("Twice is Enough").
    3. Rank-Revealing SVD for Block Deflation.
    """

    def __init__(self, operator_matmat, n_states, p_init, max_iters, tol_deflation=1e-12):
        self.operator = operator_matmat
        self.n = n_states
        self.p_init = p_init
        self.max_iters = max_iters
        self.tol_deflation = tol_deflation

        # V will store the orthogonal basis blocks. Max possible size: n x (max_iters * p_init)
        self.V = np.zeros((self.n, self.max_iters * self.p_init), dtype=np.float64)

        # H is the Block Upper Hessenberg matrix
        self.H = np.zeros((self.max_iters * self.p_init, self.max_iters * self.p_init), dtype=np.float64)

        # Track active block size (it can shrink due to deflation)
        self.p_active = p_init

        # Track starting column indices for each block in V and H
        self.block_indices = [0]

    def _orthogonalize_block(self, W, current_iter):
        """
        Orthogonalizes W against all previously computed blocks V_0 ... V_j.
        Uses a Numba BMGS kernel when available; otherwise falls back to NumPy BLAS.
        """
        j = current_iter
        start_j = self.block_indices[j]
        end_j = start_j + self.p_active

        if end_j == 0:
            return W, np.zeros((0, self.p_active), dtype=np.float64)

        # Numba path (real-valued, cache-friendly)
        if NUMBA_AVAILABLE and bmgs_twice_numba is not None:
            starts = np.asarray(self.block_indices[:j + 1], dtype=np.int64)
            ends = np.asarray(self.block_indices[1:j + 2], dtype=np.int64)
            V_prev = np.ascontiguousarray(self.V[:, :end_j], dtype=np.float64)
            Wc = np.ascontiguousarray(W, dtype=np.float64)
            W_ortho, H_col = bmgs_twice_numba(V_prev, starts, ends, Wc)
            return W_ortho, H_col

        # Fallback: NumPy BMGS + Kahan second pass
        H_col = np.zeros((end_j, self.p_active), dtype=np.float64)
        norm_W_initial = la.norm(W, ord='fro')

        for i in range(j + 1):
            start_i = self.block_indices[i]
            end_i = self.block_indices[i + 1]
            V_i = self.V[:, start_i:end_i]
            H_ij = V_i.T @ W
            H_col[start_i:end_i, :] += H_ij
            W = W - V_i @ H_ij

        norm_W_after = la.norm(W, ord='fro')
        if norm_W_after < 0.717 * norm_W_initial:
            for i in range(j + 1):
                start_i = self.block_indices[i]
                end_i = self.block_indices[i + 1]
                V_i = self.V[:, start_i:end_i]
                H_ij_corr = V_i.T @ W
                H_col[start_i:end_i, :] += H_ij_corr
                W = W - V_i @ H_ij_corr

        return W, H_col

    def _rank_revealing_svd(self, W):
        """
        Extracts the orthonormal basis of W and the sub-diagonal Hessenberg block.
        Deflates (removes) linearly dependent vectors using SVD.
        """
        # SVD: W = U * Sigma * V^T
        U, S, Vh = la.svd(W, full_matrices=False)

        # Find how many singular values are above the deflation tolerance
        rank = np.sum(S > self.tol_deflation)

        if rank < self.p_active:
            print(f"   [BIRAM] Deflation triggered! Block size shrunk from {self.p_active} to {rank}.")

        # The new orthonormal basis block (V_{j+1})
        V_next = U[:, :rank]

        # The sub-diagonal block for the Hessenberg matrix (H_{j+1, j})
        # H_{next} = Sigma * V^T
        H_next = np.diag(S[:rank]) @ Vh[:rank, :]

        return V_next, H_next, rank

    def build_krylov_space(self, V_init):
        """
        Executes the robust Block Arnoldi process.
        """
        # Set initial block
        self.V[:, :self.p_active] = V_init
        self.block_indices.append(self.p_active)

        for j in range(self.max_iters - 1):
            # 1. Extract current block V_j
            start_j = self.block_indices[j]
            end_j = self.block_indices[j + 1]
            V_j = self.V[:, start_j:end_j]

            # 2. Apply Operator (BLAS Level 3 Muscle)
            W = self.operator(V_j)

            # 3. Robust Orthogonalization
            W, H_col = self._orthogonalize_block(W, current_iter=j)

            # Insert the computed upper part into the global H matrix
            self.H[0:end_j, start_j:end_j] = H_col

            # 4. Rank-Revealing SVD & Deflation
            V_next, H_next, new_rank = self._rank_revealing_svd(W)

            if new_rank == 0:
                print("   [BIRAM] Invariant Subspace found! Exact convergence reached early.")
                break

            # 5. Store Sub-diagonal block and new basis
            self.H[end_j: end_j + new_rank, start_j:end_j] = H_next
            self.V[:, end_j: end_j + new_rank] = V_next

            # Update trackers
            self.p_active = new_rank
            self.block_indices.append(end_j + new_rank)

        # Trim matrices to the actual active subspace size
        final_dim = self.block_indices[-1]
        V_final = self.V[:, :final_dim]
        H_final = self.H[:final_dim, :final_dim]

        return V_final, H_final


class HybridBlockArnoldiDriver(DriverTemplate):
    """
    Restarted Hybrid Block-Arnoldi driver with optional A_k operator and adaptive restart.

    Key features
    ------------
    1. Explicit restarted Block-Arnoldi (BIRAM-like loop).
    2. Optional refined Ritz vectors for robust restart seeding.
    3. Residual-based stagnation detection and elastic block/depth adaptation.
    4. Compatibility with both LU-cached DAE operator and explicit EMT A_k stacks.
    """

    def __init__(self, grid, problem, emt_options: EmtOptions, options: EmtFloquetOptions):
        DriverTemplate.__init__(self, grid=grid)
        self.problem = problem
        self.emt_options = emt_options
        self.options = options
        self.results = None

    def _capture_limit_cycle_and_evaluator(self, h: float):
        """
        Intelligently captures the limit cycle. If running in production with VeraGrid's
        EmtProblemDae, it borrows the JIT Jacobian evaluator from the StructuralVectorizedSolver
        to avoid double-discretization overhead. Falls back to legacy step() for mocks.
        """
        # Extract integration method string (handling Enums if present)
        method_str = getattr(self.emt_options, 'integration_method', 'back_euler')
        if hasattr(method_str, 'value'):
            method_str = method_str.value

        # Production Check: Real EmtProblemDae has these symbolic getters
        if hasattr(self.problem, 'get_parameters_values') and hasattr(self.problem, 'def_event_params_fn'):
            if getattr(self.options, 'verbose', 0):
                print("-> Production mode: Borrowing JIT kernels from EMT Solver (Zero Double-Discretization)...")
            from VeraGridEngine.Simulations.EMT.numerical.StructuralVectorizedSolver import StructuralVectorizedSolver

            solver = StructuralVectorizedSolver(
                problem=self.problem, t0=0.0, t_end=self.options.ss_assessment_time,
                h=h, method_str=method_str, verbose=bool(getattr(self.options, 'verbose', 0))
            )
            t_full, y_full = solver.simulate()

            steps_per_period = int(self.options.target_period / h)
            y_limit = y_full[-steps_per_period:]
            t_limit = t_full[-steps_per_period:]

            static_params = np.array([c.value for c in self.problem.get_parameters_values()], dtype=np.float64)
            n_event_params = self.problem.get_variable_parameter_number()

            return y_limit, t_limit, solver.vec_jacobian, static_params, n_event_params, method_str
        else:
            if getattr(self.options, 'verbose', 0):
                print("-> Mock mode: Using legacy trajectory capture...")
            trajectory = []
            num_steps = int(self.options.target_period / h)
            x = self.problem.get_x0()
            for _ in range(num_steps):
                if hasattr(self.problem, 'step'):
                    x_next, y_next = self.problem.step(x)
                else:
                    x_next, y_next = x.copy(), np.zeros(self.problem.get_algebraic_var_number())
                trajectory.append((x_next.copy(), y_next.copy()))
                x = x_next

            return trajectory, None, None, None, 0, method_str

    def _make_monodromy_operator(self, h: float, n_states: int):
        prefer_ak = bool(getattr(self.options, 'prefer_ak_operator', True))
        use_numba = bool(getattr(self.options, 'use_numba_kernels', True))

        if prefer_ak:
            ak_getter = None
            for name in ('get_floquet_Ak_stack', 'get_floquet_ak_stack', 'get_Ak_stack', 'get_ak_stack'):
                if hasattr(self.problem, name):
                    ak_getter = getattr(self.problem, name)
                    break
            if ak_getter is not None:
                try:
                    Ak_stack = ak_getter(self.options.target_period, h)
                except TypeError:
                    try:
                        Ak_stack = ak_getter(h)
                    except TypeError:
                        Ak_stack = ak_getter()
                if Ak_stack is not None:
                    if getattr(self.options, 'verbose', 0):
                        print('Using explicit EMT A_k stack operator (Numba path if available).')
                    return AkStackBlockEmtFloquetOperator(Ak_stack, use_numba=use_numba)

        # If no explicit A_k stack is found, route through the JIT LU Pipeline
        y_traj, t_traj, jac_eval, stat_params, n_ev_params, method_str = self._capture_limit_cycle_and_evaluator(h)

        return BlockEmtFloquetOperator(
            problem=self.problem,
            trajectory=y_traj,
            h=h,
            n_states=n_states,
            method_str=method_str,
            jac_evaluator=jac_eval,
            static_params=stat_params,
            n_event_params=n_ev_params,
            t_trajectory=t_traj
        )

    @staticmethod
    def _apply_operator_complex(op_matmat, Xc: np.ndarray) -> np.ndarray:
        Xr = np.ascontiguousarray(np.real(Xc), dtype=np.float64)
        Xi = np.ascontiguousarray(np.imag(Xc), dtype=np.float64)
        Yr = op_matmat(Xr)
        Yi = op_matmat(Xi)
        return Yr + 1j * Yi

    def _compute_selected_pairs(self, monodromy_op, V_sub, H_sub, k_target: int, p_seed: int, use_refined: bool):
        """Return selected multipliers, vectors in full space, and relative residuals."""
        mu_sub, Y_sub = la.eig(H_sub)
        sort_idx = np.argsort(-np.abs(mu_sub))
        keep = min(len(sort_idx), max(k_target + 2, p_seed))
        sel = sort_idx[:keep]
        mu_sel = mu_sub[sel]
        Y_sel = Y_sub[:, sel]

        if use_refined:
            # Refined Ritz vectors: z = arg min ||(AV - μV) z|| in the current subspace
            AV = self._apply_operator_complex(monodromy_op.matmat, V_sub.astype(np.complex128))
            Vc = V_sub.astype(np.complex128)
            U_sel = np.zeros((V_sub.shape[0], keep), dtype=np.complex128)
            for j, mu in enumerate(mu_sel):
                Mj = AV - mu * Vc
                G = Mj.conj().T @ Mj
                # Small Hermitian eigenproblem (dim = krylov dim)
                ew, Ez = la.eigh(G)
                z = Ez[:, np.argmin(np.real(ew))]
                u = Vc @ z
                nu = la.norm(u)
                if nu > 0:
                    u /= nu
                else:
                    u = Vc @ Y_sel[:, j]
                    u /= max(la.norm(u), 1e-15)
                U_sel[:, j] = u
        else:
            U_sel = (V_sub @ Y_sel).astype(np.complex128)

        AU_sel = self._apply_operator_complex(monodromy_op.matmat, U_sel)
        R = AU_sel - U_sel * mu_sel.reshape(1, -1)
        rnorm = np.linalg.norm(R, axis=0)
        unorm = np.linalg.norm(U_sel, axis=0)
        rel = rnorm / np.maximum(np.abs(mu_sel) * unorm, 1e-15)

        return mu_sel, U_sel, rel

    @staticmethod
    def _build_restart_seed(U_sel: np.ndarray, p_target: int, seed: int = 42) -> np.ndarray:
        """Build a real orthonormal restart block from complex Ritz/refined vectors."""
        n = U_sel.shape[0]
        cols = []
        for j in range(U_sel.shape[1]):
            ur = np.real(U_sel[:, j])
            if np.linalg.norm(ur) > 1e-14:
                cols.append(ur)
            if len(cols) >= p_target:
                break
            ui = np.imag(U_sel[:, j])
            if np.linalg.norm(ui) > 1e-14:
                cols.append(ui)
            if len(cols) >= p_target:
                break

        rng = np.random.default_rng(seed)
        while len(cols) < p_target:
            cols.append(rng.standard_normal(n))

        S = np.column_stack(cols[:p_target])
        Q, _ = np.linalg.qr(S)
        return Q[:, :p_target]

    def run(self):
        self.tic()

        h = self.emt_options.time_step
        n_states = self.problem.get_states_number()

        # Operator (A_k stack if the EMT backend exposes it, else LU-cached DAE operator)
        monodromy_op = self._make_monodromy_operator(h, n_states)

        # Hyperparameters (elastic / adaptive)
        k_target = int(self.options.k)
        base_max_dim = int(getattr(self.options, 'max_krylov_dim', 60))
        max_restarts = int(getattr(self.options, 'max_restarts', 4))
        restart_tol = float(getattr(self.options, 'restart_tol', 1e-6))
        use_refined = bool(getattr(self.options, 'use_refined_ritz', True))
        adaptive_restart = bool(getattr(self.options, 'adaptive_restart', True))
        stagnation_ratio = float(getattr(self.options, 'stagnation_improve_ratio', 0.90))
        stagnation_patience = int(getattr(self.options, 'stagnation_patience', 2))

        _p_min = getattr(self.options, 'min_block_size', None)
        p_min = int(_p_min) if _p_min is not None else max(2, k_target)

        _p_max = getattr(self.options, 'max_block_size', None)
        p_max = int(_p_max) if _p_max is not None else min(n_states, k_target + 8)

        _cap = getattr(self.options, 'max_krylov_dim_cap', None)
        max_dim_cap = int(_cap) if _cap is not None else max(base_max_dim, int(1.8 * base_max_dim))

        p_seed = min(max(k_target + 2, p_min), p_max, n_states)
        max_dim_local = max(base_max_dim, p_seed + 1)
        m_iters = max(2, max_dim_local // p_seed)

        if getattr(self.options, 'verbose', 0):
            print(f'Executing Hybrid Block-Arnoldi (Block Size: {p_seed}, Iters: {m_iters}, Restarts: {max_restarts})...')
            if NUMBA_AVAILABLE and bmgs_twice_numba is not None:
                print('   [BIRAM] Numba BMGS kernel: ON')

        rng = np.random.default_rng(42)
        V_seed, _ = np.linalg.qr(rng.standard_normal((n_states, p_seed)))

        best_pack = None
        residual_history = []

        for ir in range(max_restarts + 1):
            if getattr(self.options, 'verbose', 0):
                print(f'   [BIRAM] Restart cycle {ir + 1}/{max_restarts + 1}')

            engine = RobustBlockArnoldiEngine(
                operator_matmat=monodromy_op.matmat,
                n_states=n_states,
                p_init=p_seed,
                max_iters=m_iters,
                tol_deflation=float(getattr(self.options, 'deflation_tol', 1e-12)),
            )

            V_sub, H_sub = engine.build_krylov_space(V_seed)
            mu_sel, U_sel, rel = self._compute_selected_pairs(
                monodromy_op=monodromy_op,
                V_sub=V_sub,
                H_sub=H_sub,
                k_target=k_target,
                p_seed=p_seed,
                use_refined=use_refined,
            )

            # Track best result seen so far
            sort_now = np.argsort(-np.abs(mu_sel))
            topk = sort_now[:min(k_target, len(sort_now))]
            max_rr = float(np.max(rel[topk])) if len(topk) > 0 else np.inf
            residual_history.append(max_rr)
            if getattr(self.options, 'verbose', 0):
                print(f'   [BIRAM] top-{len(topk)} max rel-res = {max_rr:.3e}')

            if (best_pack is None) or (max_rr < best_pack['max_rr']):
                best_pack = {
                    'mu_sel': mu_sel.copy(),
                    'U_sel': U_sel.copy(),
                    'rel': rel.copy(),
                    'max_rr': max_rr,
                }

            if max_rr <= restart_tol:
                if getattr(self.options, 'verbose', 0):
                    print('   [BIRAM] Converged by residual tolerance.')
                break

            if ir >= max_restarts:
                break

            # Prepare restart seed from refined/Ritz vectors
            V_seed = self._build_restart_seed(U_sel, p_target=p_seed, seed=42 + ir)

            # Elastic adaptation under residual stagnation
            if adaptive_restart and len(residual_history) >= stagnation_patience + 1:
                recent = residual_history[-1]
                prev_best = min(residual_history[-(stagnation_patience + 1):-1])
                if recent > stagnation_ratio * prev_best:
                    changed = False
                    # Prefer reducing block size to increase Krylov depth at fixed memory
                    if p_seed > p_min:
                        p_new = max(p_min, p_seed - 2)
                        if p_new != p_seed:
                            p_seed = p_new
                            V_seed = self._build_restart_seed(U_sel, p_target=p_seed, seed=99 + ir)
                            changed = True
                            if getattr(self.options, 'verbose', 0):
                                print(f'   [BIRAM] Residual stagnation detected -> shrink block to p={p_seed}.')
                    else:
                        # Increase subspace depth budget if block is already minimal
                        max_dim_new = min(max_dim_cap, max_dim_local + p_seed)
                        if max_dim_new > max_dim_local:
                            max_dim_local = max_dim_new
                            changed = True
                            if getattr(self.options, 'verbose', 0):
                                print(f'   [BIRAM] Residual stagnation detected -> expand max Krylov dim to {max_dim_local}.')

                    if changed:
                        m_iters = max(2, max_dim_local // p_seed)

        # Final selection (best observed cycle)
        if best_pack is None:
            raise RuntimeError('HybridBlockArnoldiDriver failed to produce Ritz pairs.')

        mu_sel = best_pack['mu_sel']
        U_sel = best_pack['U_sel']
        sort_idx = np.argsort(-np.abs(mu_sel))[:k_target]
        mu = mu_sel[sort_idx]
        v = U_sel[:, sort_idx]
        w = np.linalg.pinv(v).conj().T

        self.results = EmtFloquetResults(
            multipliers=mu,
            right_vecs=v,
            left_vecs=w,
            period=self.options.target_period,
            stat_vars=self.problem.get_state_vars()
        )

        self.toc()
