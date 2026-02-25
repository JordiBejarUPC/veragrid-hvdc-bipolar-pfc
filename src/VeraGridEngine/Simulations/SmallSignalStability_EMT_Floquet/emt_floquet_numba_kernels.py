# SPDX-License-Identifier: MPL-2.0
"""
Numba kernels for EMT Floquet block methods.

This module is optional and degrades gracefully if Numba is unavailable.
It includes:
- A dense A_k sequence block propagator (monodromy application in block form).
- A block MGS + optional second pass kernel for Arnoldi orthogonalisation.

Notes
-----
* The kernels operate on real-valued arrays (float64). Complex Ritz handling remains
  in Python/Numpy and is split into real/imag operator applications upstream.
* In some environments Numba fails to import because of coverage package API changes.
  A small compatibility shim is applied automatically before importing Numba.
"""

from __future__ import annotations

from typing import Tuple
import typing as _typing
import numpy as np

NUMBA_AVAILABLE = False
NUMBA_IMPORT_ERROR = None


def _patch_coverage_for_numba() -> None:
    """Best-effort compatibility shim for coverage>=7.5 + numba import."""
    try:
        import coverage  # type: ignore
    except Exception:
        return

    ct = getattr(coverage, "types", None)
    if ct is None:
        return

    if (not hasattr(ct, "Tracer")) and hasattr(ct, "TracerCore"):
        # Numba <=0.63 expects coverage.types.Tracer (older coverage API).
        setattr(ct, "Tracer", getattr(ct, "TracerCore"))

    # Newer coverage releases removed a couple of aliases used by Numba type hints.
    for name in ("TShouldTraceFn", "TShouldStartContextFn"):
        if not hasattr(ct, name):
            setattr(ct, name, _typing.Any)


try:
    _patch_coverage_for_numba()
    from numba import njit, prange  # type: ignore
    NUMBA_AVAILABLE = True
except Exception as _exc:  # pragma: no cover - optional path
    NUMBA_IMPORT_ERROR = _exc
    njit = None  # type: ignore
    prange = range  # type: ignore


if NUMBA_AVAILABLE:

    @njit(cache=True, fastmath=True)
    def _fro_norm_numba(X: np.ndarray) -> float:
        s = 0.0
        n, m = X.shape
        for i in range(n):
            for j in range(m):
                v = X[i, j]
                s += v * v
        return np.sqrt(s)


    @njit(cache=True, fastmath=True)
    def _gemm_left_t_numba(Vi: np.ndarray, W: np.ndarray) -> np.ndarray:
        """Compute H = Vi.T @ W (real) using cache-friendly loops."""
        n, r = Vi.shape
        _, p = W.shape
        H = np.zeros((r, p), dtype=np.float64)
        for k in range(n):
            # row-wise accumulation (good locality for Vi[k,:] and W[k,:])
            for i in range(r):
                vik = Vi[k, i]
                if vik == 0.0:
                    continue
                for j in range(p):
                    H[i, j] += vik * W[k, j]
        return H


    @njit(cache=True, fastmath=True)
    def _gemm_sub_numba(W: np.ndarray, Vi: np.ndarray, H: np.ndarray) -> None:
        """In-place W -= Vi @ H using an outer-product micro-kernel."""
        n, r = Vi.shape
        _, p = H.shape
        for i in range(n):
            for t in range(r):
                a = Vi[i, t]
                if a == 0.0:
                    continue
                for j in range(p):
                    W[i, j] -= a * H[t, j]


    @njit(cache=True, fastmath=True)
    def bmgs_twice_numba(
        V_all: np.ndarray,
        starts: np.ndarray,
        ends: np.ndarray,
        W_in: np.ndarray,
        reorth_factor: float = 0.717,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Block Modified Gram-Schmidt over previously computed blocks.

        Parameters
        ----------
        V_all : (n, m_prev) float64
            Concatenated basis blocks.
        starts, ends : int64 arrays
            Block boundaries for V_all.
        W_in : (n, p) float64
            Candidate block to orthogonalise.

        Returns
        -------
        W_out : (n, p)
        H_col : (m_prev, p)
        """
        W = W_in.copy()
        n = W.shape[0]
        p = W.shape[1]
        m_prev = ends[-1] if ends.size > 0 else 0
        H_col = np.zeros((m_prev, p), dtype=np.float64)

        norm0 = _fro_norm_numba(W)

        # First pass
        for b in range(starts.size):
            s = starts[b]
            e = ends[b]
            Vi = V_all[:, s:e]
            H = _gemm_left_t_numba(Vi, W)
            H_col[s:e, :] += H
            _gemm_sub_numba(W, Vi, H)

        norm1 = _fro_norm_numba(W)

        # Kahan / DGKS style second pass if needed
        if norm1 < reorth_factor * norm0:
            for b in range(starts.size):
                s = starts[b]
                e = ends[b]
                Vi = V_all[:, s:e]
                Hc = _gemm_left_t_numba(Vi, W)
                H_col[s:e, :] += Hc
                _gemm_sub_numba(W, Vi, Hc)

        return W, H_col


    @njit(cache=True, fastmath=True, parallel=True)
    def apply_ak_stack_block_numba(Ak_stack: np.ndarray, X0: np.ndarray) -> np.ndarray:
        """
        Apply Φ = A_{M-1}...A_0 to a block X0 using a dense 3D A_k stack.

        Ak_stack shape: (M, n, n)
        X0 shape: (n, p)
        """
        M = Ak_stack.shape[0]
        n = Ak_stack.shape[1]
        p = X0.shape[1]
        Y = X0.copy()
        T = np.zeros((n, p), dtype=np.float64)

        for k in range(M):
            A = Ak_stack[k]
            # T = A @ Y (outer-product style for cache reuse)
            for i in prange(n):
                for j in range(p):
                    T[i, j] = 0.0
                for t in range(n):
                    a = A[i, t]
                    if a == 0.0:
                        continue
                    for j in range(p):
                        T[i, j] += a * Y[t, j]
            # swap buffers
            tmp = Y
            Y = T
            T = tmp

        return Y



    @njit(cache=True, fastmath=True)
    def solve_lu_dense_block_numba(
        L: np.ndarray,
        U: np.ndarray,
        perm_r: np.ndarray,
        perm_c: np.ndarray,
        B: np.ndarray,
    ) -> np.ndarray:
        """
        Solve A X = B using dense LU factors and SuperLU-style permutations.

        Assumes P_r A P_c = L U, where perm_r / perm_c encode the row/column
        permutations used by SuperLU. This kernel is intended for integration
        in a future LU-factor JIT path when the EMT backend exports raw factors.
        """
        n = L.shape[0]
        p = B.shape[1]

        # Apply row permutation: Bp = P_r B
        Bp = np.zeros((n, p), dtype=np.float64)
        for i in range(n):
            Bp[i, :] = B[perm_r[i], :]

        # Forward substitution L Y = Bp (unit lower triangular)
        Y = np.zeros((n, p), dtype=np.float64)
        for i in range(n):
            for j in range(p):
                s = Bp[i, j]
                for k in range(i):
                    s -= L[i, k] * Y[k, j]
                # unit diagonal assumed
                Y[i, j] = s

        # Back substitution U Z = Y
        Z = np.zeros((n, p), dtype=np.float64)
        for i in range(n - 1, -1, -1):
            for j in range(p):
                s = Y[i, j]
                for k in range(i + 1, n):
                    s -= U[i, k] * Z[k, j]
                Z[i, j] = s / U[i, i]

        # Undo column permutation: X = P_c Z  (SuperLU convention-dependent)
        X = np.zeros((n, p), dtype=np.float64)
        for i in range(n):
            X[perm_c[i], :] = Z[i, :]

        return X
else:

    def bmgs_twice_numba(*args, **kwargs):  # pragma: no cover - optional path
        raise RuntimeError(f"Numba unavailable: {NUMBA_IMPORT_ERROR}")

    def solve_lu_dense_block_numba(*args, **kwargs):
        raise RuntimeError(f"Numba unavailable: {NUMBA_IMPORT_ERROR}")

    def apply_ak_stack_block_numba(*args, **kwargs):  # pragma: no cover - optional path
        raise RuntimeError(f"Numba unavailable: {NUMBA_IMPORT_ERROR}")


__all__ = [
    "NUMBA_AVAILABLE",
    "NUMBA_IMPORT_ERROR",
    "bmgs_twice_numba",
    "solve_lu_dense_block_numba",
    "apply_ak_stack_block_numba",
]
