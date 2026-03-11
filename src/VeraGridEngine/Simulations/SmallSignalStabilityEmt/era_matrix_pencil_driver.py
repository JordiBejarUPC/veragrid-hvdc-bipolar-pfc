# SPDX-License-Identifier: MPL-2.0

import numpy as np
import scipy.linalg as la
from numpy.lib.stride_tricks import sliding_window_view

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.basic_structures import CxVec

from VeraGridEngine.Simulations.SmallSignalStabilityEmt.era_matrix_pencil_options import EraMatrixPencilOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.era_matrix_pencil_results import EraMatrixPencilResults


def select_dominant_observable(y_data: np.ndarray) -> np.ndarray:
    """
    Selects the most excited state variable trajectory during the ringdown.
    The variance acts as a proxy for observability.

    :param y_data: Real matrix of shape (n_samples, n_states).
    :return: 1D array of the most dominant state's trajectory.
    """
    variances: np.ndarray = np.var(y_data, axis=0)
    best_idx: int = int(np.argmax(variances))
    return y_data[:, best_idx]


def build_hankel_zero_copy(y_signal: np.ndarray, window_length: int) -> np.ndarray:
    """
    Constructs the Hankel matrix using memory strides.
    Complexity: O(1) in time and memory footprint.

    :param y_signal: 1D array of the temporal signal.
    :param window_length: Number of columns (L) for the Matrix Pencil.
    :return: 2D view of the Hankel matrix.
    """
    # sliding_window_view gives shape (M - L + 1, L)
    h_view: np.ndarray = sliding_window_view(y_signal, window_shape=window_length)
    return h_view


def extract_matrix_pencil_poles(y_signal: np.ndarray, dt: float, max_modes: int, tol_deflation: float) -> CxVec:
    """
    Executes the Matrix Pencil mathematical algorithm over a single time-series.

    :param y_signal: 1D array of the measured ringdown transient.
    :param dt: Time step between samples.
    :param max_modes: Maximum number of physical poles to extract.
    :param tol_deflation: Singular value tolerance for noise deflation.
    :return: 1D complex array of continuous-time S-domain eigenvalues.
    """
    # 1. Normalize the signal to prevent numerical ill-conditioning
    mu: float = float(np.mean(y_signal))
    y_centered: np.ndarray = y_signal - mu
    sigma: float = float(np.std(y_centered))

    if sigma > 1e-12:
        y_norm: np.ndarray = y_centered / sigma
    else:
        y_norm: np.ndarray = y_centered

    # 2. Setup Pencil Window (Hua and Sarkar rule of thumb: L = M/3)
    n_samples: int = y_norm.shape[0]
    window_length: int = n_samples // 3

    if window_length < 2:
        return np.zeros(0, dtype=np.complex128)
    else:
        pass

    # 3. Assemble O(1) Zero-Copy Hankel Matrix
    H: np.ndarray = build_hankel_zero_copy(y_norm, window_length)

    # 4. Singular Value Decomposition
    # H = U * S * Vh
    U: np.ndarray
    S: np.ndarray
    Vh: np.ndarray
    U, S, Vh = la.svd(H, full_matrices=False)

    # 5. Deflation (Determine the effective mathematical rank)
    rank: int = 0
    for i in range(S.shape[0]):
        if S[i] > tol_deflation:
            rank += 1
        else:
            pass

    rank = min(rank, max_modes)

    if rank == 0:
        return np.zeros(0, dtype=np.complex128)
    else:
        pass

    # V_n shape becomes (window_length, rank)
    V_n: np.ndarray = Vh[:rank, :].T

    # 6. Shift Invariance (Matrix Pencil)
    V1: np.ndarray = V_n[:-1, :]
    V2: np.ndarray = V_n[1:, :]

    # 7. Solve Least Squares: V1 * Z = V2
    Z_mat: np.ndarray
    residuals: np.ndarray
    rank_lstsq: int
    s_lstsq: np.ndarray
    Z_mat, residuals, rank_lstsq, s_lstsq = la.lstsq(V1, V2)

    # 8. Extract discrete multipliers
    z_poles: np.ndarray = la.eigvals(Z_mat)

    # 9. Map Z-domain to continuous S-domain
    s_poles: np.ndarray = np.log(z_poles) / dt

    return s_poles.astype(np.complex128)


class EraMatrixPencilDriver(DriverTemplate):
    """
    Driver responsible for simulating the grid transient and extracting
    broadband (sub and supersynchronous) modes via the ERA/Matrix Pencil algorithm.
    """
    __slots__ = (
        '_grid',
        '_problem',
        '_emt_options',
        '_era_options',
        '_results'
    )

    def __init__(self,
                 grid: MultiCircuit,
                 problem: EmtProblemTemplate,
                 emt_options: EmtOptions,
                 era_options: EraMatrixPencilOptions) -> None:
        """
        Initializes the driver and validates the provided options.
        """
        DriverTemplate.__init__(self, grid=grid)
        self._grid: MultiCircuit = grid
        self._problem: EmtProblemTemplate = problem
        self._emt_options: EmtOptions = emt_options
        self._era_options: EraMatrixPencilOptions = era_options
        self._results: EraMatrixPencilResults | None = None

    def get_results(self) -> EraMatrixPencilResults | None:
        return self._results

    def run(self) -> None:
        """
        Executes the full pipeline: EMT Ringdown Simulation -> Data Decimation -> ERA Extraction.
        """
        self.tic()

        h_step: float = self._emt_options.time_step
        t_end: float = self._era_options.get_t_ringdown()

        if self._era_options.get_verbose() > 0:
            print("-> Executing EMT Transient for ERA Ringdown Analysis...")
        else:
            pass

        # 1. Run the vectorized EMT solver to generate ringdown data
        solver: StructuralVectorizedSolver = StructuralVectorizedSolver(
            problem=self._problem,
            t0=0.0,
            t_end=t_end,
            h=h_step,
            method=self._emt_options.integration_method,
            verbose=self._era_options.get_verbose() > 0
        )

        t_full: np.ndarray
        y_full_tuples: list
        t_full, y_full_tuples = solver.simulate()

        # Unpack tuple states into a pure dense Numpy array
        n_samples: int = len(y_full_tuples)
        n_states: int = self._problem.get_states_number()
        y_dense: np.ndarray = np.zeros((n_samples, n_states), dtype=np.float64)

        for i in range(n_samples):
            step_data = y_full_tuples[i]
            if isinstance(step_data, tuple):
                y_dense[i, :] = step_data[0]
            else:
                y_dense[i, :] = step_data

        # 2. Decimation (Anti-aliasing downsampling for performance)
        dec_factor: int = self._era_options.get_decimation_factor()
        if dec_factor > 1:
            y_decimated: np.ndarray = y_dense[::dec_factor, :]
            dt_effective: float = h_step * dec_factor
        else:
            y_decimated: np.ndarray = y_dense
            dt_effective: float = h_step

        # 3. Choose the most observable trajectory for mode extraction
        y_target: np.ndarray = select_dominant_observable(y_decimated)

        if self._era_options.get_verbose() > 0:
            print("-> Assembling Hankel Matrix and computing Matrix Pencil Poles...")
        else:
            pass

        # 4. Extract mathematical poles
        s_poles: CxVec = extract_matrix_pencil_poles(
            y_signal=y_target,
            dt=dt_effective,
            max_modes=self._era_options.get_max_modes(),
            tol_deflation=self._era_options.get_tol_deflation()
        )

        # 5. Store cleanly in the results structure
        self._results = EraMatrixPencilResults(eigenvalues_s=s_poles)

        self.toc()