# SPDX-License-Identifier: MPL-2.0
"""
Demo: ERA/Matrix Pencil vs Floquet Theory (Supersynchronous Aliasing)
=====================================================================

This script mathematically proves why Floquet theory is insufficient for
Super-Synchronous Resonance (SSR) or High-Frequency Control interactions
in EMT simulations, and why the Eigensystem Realization Algorithm (ERA)
is required.
"""

import numpy as np
import scipy.linalg as la
from numpy.lib.stride_tricks import sliding_window_view
from typing import Tuple, List


class AliasingBenchmark:
    """
    Encapsulates the mathematical comparison between Floquet and ERA.
    """
    __slots__ = (
        '_f_grid',
        '_t_period',
        '_h_step',
        '_a_matrix'
    )

    def __init__(self, f_grid: float = 50.0, h_step: float = 50e-6) -> None:
        self._f_grid: float = f_grid
        self._t_period: float = 1.0 / f_grid
        self._h_step: float = h_step
        self._a_matrix: np.ndarray = self._build_system_matrix()

    def _build_system_matrix(self) -> np.ndarray:
        """
        Builds a 6x6 continuous-time state matrix A with 3 specific complex
        conjugate pole pairs perfectly decoupled.
        """
        poles: List[Tuple[float, float]] = list([
            (-0.5, 15.0),  # Mode 1: Subsynchronous
            (-1.0, 120.0),  # Mode 2: Supersynchronous
            (-5.0, 850.0)  # Mode 3: High Frequency
        ])

        n_states: int = len(poles) * 2
        a_mat: np.ndarray = np.zeros((n_states, n_states), dtype=np.float64)

        for i in range(len(poles)):
            sigma: float = poles[i][0]
            omega: float = 2.0 * np.pi * poles[i][1]
            idx: int = i * 2

            a_mat[idx, idx] = sigma
            a_mat[idx, idx + 1] = omega
            a_mat[idx + 1, idx] = -omega
            a_mat[idx + 1, idx + 1] = sigma

        return a_mat

    def run_floquet_analysis(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Executes Floquet Theory by computing the exact Monodromy Matrix.
        """
        monodromy_matrix: np.ndarray = la.expm(self._a_matrix * self._t_period)
        multipliers: np.ndarray = la.eigvals(monodromy_matrix)
        s_poles: np.ndarray = np.log(multipliers) / self._t_period

        real_parts: np.ndarray = s_poles.real
        frequencies_hz: np.ndarray = np.abs(s_poles.imag) / (2.0 * np.pi)

        return real_parts, frequencies_hz

    def run_era_analysis(self, t_sim: float = 0.5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Executes ERA / Matrix Pencil by simulating a ringdown transient.
        """
        n_steps: int = int(t_sim / self._h_step)
        discrete_a: np.ndarray = la.expm(self._a_matrix * self._h_step)

        x_k: np.ndarray = np.ones(6, dtype=np.float64)
        y_signal: np.ndarray = np.zeros(n_steps, dtype=np.float64)

        for k in range(n_steps):
            x_k = discrete_a @ x_k
            # FIX: Sum all states to ensure Observability of all decoupled modes
            y_signal[k] = np.sum(x_k)

        s_poles: np.ndarray = self._extract_matrix_pencil_poles(y_signal, self._h_step)

        real_parts: np.ndarray = s_poles.real
        frequencies_hz: np.ndarray = np.abs(s_poles.imag) / (2.0 * np.pi)

        return real_parts, frequencies_hz

    def _extract_matrix_pencil_poles(self, y_signal: np.ndarray, dt: float) -> np.ndarray:
        """
        Core Matrix Pencil algorithm (Zero-Copy Hankel + SVD).
        """
        mu: float = float(np.mean(y_signal))
        y_norm: np.ndarray = y_signal - mu

        window_length: int = y_norm.shape[0] // 3
        h_matrix: np.ndarray = sliding_window_view(y_norm, window_shape=window_length)

        U: np.ndarray
        S: np.ndarray
        Vh: np.ndarray
        U, S, Vh = la.svd(h_matrix, full_matrices=False)

        # Robust relative deflation
        tol: float = float(S[0]) * 1e-8
        rank: int = int(np.sum(S > tol))

        V_n: np.ndarray = Vh[:rank, :].T
        V1: np.ndarray = V_n[:-1, :]
        V2: np.ndarray = V_n[1:, :]

        Z_mat: np.ndarray
        residuals: np.ndarray
        rank_lstsq: int
        s_lstsq: np.ndarray
        Z_mat, residuals, rank_lstsq, s_lstsq = la.lstsq(V1, V2)

        z_poles: np.ndarray = la.eigvals(Z_mat)
        s_poles: np.ndarray = np.log(z_poles) / dt

        return s_poles


def print_formatted_poles(real_parts: np.ndarray, frequencies: np.ndarray) -> None:
    unique_freqs: List[float] = list()
    for i in range(len(real_parts)):
        f: float = frequencies[i]
        r: float = real_parts[i]

        is_unique: bool = True
        for uf in unique_freqs:
            if abs(f - uf) < 1.0:
                is_unique = False
            else:
                pass

        if is_unique:
            unique_freqs.append(f)
            print(f"  -> Pole: {r:6.2f} + j {f:6.2f} Hz")
        else:
            pass


def run_demo() -> None:
    print("=" * 80)
    print("  ERA vs Floquet: Supersynchronous Aliasing Demonstration")
    print("=" * 80)

    benchmark: AliasingBenchmark = AliasingBenchmark(f_grid=50.0, h_step=50e-6)

    print("\n[Injected Physical Modes (Ground Truth)]")
    print("  -> Mode 1:  -0.50 + j  15.00 Hz (Subsynchronous)")
    print("  -> Mode 2:  -1.00 + j 120.00 Hz (Supersynchronous)")
    print("  -> Mode 3:  -5.00 + j 850.00 Hz (High Frequency Control)")

    print("\n" + "-" * 80)
    print("[1] Floquet Analysis Results (Limit Cycle T = 0.02s)")
    print("Mathematical Limit: Maximum observable frequency is 1 / (2T) = 25 Hz")
    floq_real, floq_freq = benchmark.run_floquet_analysis()
    print_formatted_poles(floq_real, floq_freq)

    print("\n" + "-" * 80)
    print("[2] ERA / Matrix Pencil Results (Ringdown h = 50 us)")
    print("Mathematical Limit: Maximum observable frequency is 1 / (2h) = 10,000 Hz")
    era_real, era_freq = benchmark.run_era_analysis(t_sim=0.5)
    print_formatted_poles(era_real, era_freq)

    print("\n" + "=" * 80)
    print("CONCLUSION:")
    print("Floquet suffers from Nyquist Aliasing on the fundamental cycle.")
    print("- 120 Hz folded into 20 Hz  [ 120 - 2*(50) = 20 ]")
    print("- 850 Hz folded into  0 Hz  [ 850 / 50 = 17 exactly ]")
    print("ERA successfully extracts the true supersynchronous frequencies.")
    print("=" * 80)


if __name__ == '__main__':
    run_demo()