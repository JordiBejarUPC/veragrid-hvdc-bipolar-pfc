# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""VeraGrid-specific isolated numerical timings for RMS benchmarks."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp

from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import compute_participation_factors
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import compute_participation_factors_generalized
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import compute_state_matrix
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from trunk.dynamics.small_signal.small_signal_benchmark_timing import elapsed_seconds


def benchmark_veragrid_isolated_numerical_phases(
    driver: SmallSignalStabilityRmsDriver,
) -> dict[str, float]:
    """Repeat the matrix and modal phases independently after a completed run.

    These warm repeats expose phase-level timings without modifying the engine.
    The normal ``small_signal_total`` value remains the authoritative driver
    time and excludes these diagnostic repeats.

    :param driver: Completed VeraGrid small-signal driver.
    :return: Isolated timing samples keyed by common benchmark phase.
    """
    problem: RmsProblemTemplate = driver.problem
    state_values: np.ndarray = np.asarray(problem.get_x0(), dtype=float)
    derivative_values: np.ndarray = np.zeros_like(state_values)
    differential_variable_count: int = int(problem.get_diff_var_number())

    # Build the reduced state matrix alone to expose the DAE reduction cost.
    matrix_start: float = time.perf_counter()
    mass_matrix: np.ndarray | None
    balanced_matrix: np.ndarray
    if differential_variable_count == 0:
        balanced_matrix, _ = compute_state_matrix(
            problem=problem,
            x=state_values,
            dx=derivative_values,
        )
        mass_matrix = None
    else:
        raw_mass_matrix: Any = problem.get_E_matrix(
            state_values,
            derivative_values,
        )
        if sp.issparse(raw_mass_matrix):
            mass_matrix = raw_mass_matrix.toarray()
        else:
            mass_matrix = np.asarray(raw_mass_matrix, dtype=float)
        raw_state_matrix: Any = problem.get_static_state_matrix(
            state_values,
            derivative_values,
        )
        if sp.issparse(raw_state_matrix):
            balanced_matrix = raw_state_matrix.toarray()
        else:
            balanced_matrix = np.asarray(raw_state_matrix, dtype=float)
        balanced_matrix += np.eye(balanced_matrix.shape[0]) * 1.0e-7
    matrix_seconds: float = elapsed_seconds(matrix_start)

    # Repeat eigensolution and participation-factor construction together.
    eigen_start: float = time.perf_counter()
    eigenvalues: np.ndarray
    left_raw: np.ndarray
    right_vectors: np.ndarray
    if mass_matrix is None:
        eigenvalues, left_raw, right_vectors = la.eig(
            balanced_matrix,
            left=True,
            right=True,
        )
        left_vectors: np.ndarray = np.asarray(left_raw, dtype=complex).conj()
        factors: np.ndarray = compute_participation_factors(
            v=np.asarray(right_vectors, dtype=complex),
            w=left_vectors,
        )
    else:
        eigenvalues, left_raw, right_vectors = la.eig(
            balanced_matrix,
            -mass_matrix,
            left=True,
            right=True,
        )
        left_vectors = np.asarray(left_raw, dtype=complex).conj()
        factors = compute_participation_factors_generalized(
            v=np.asarray(right_vectors, dtype=complex),
            w=left_vectors,
            E=mass_matrix,
        )
    eigen_seconds: float = elapsed_seconds(eigen_start)

    # A timing repeat is valid only if it retains the complete modal inventory.
    expected_mode_count: int = int(np.asarray(driver.results.eigenvalues).size)
    obtained_mode_count: int = int(np.asarray(eigenvalues).size)
    if (
        obtained_mode_count == expected_mode_count
        and factors.shape[1] == expected_mode_count
    ):
        pass
    else:
        raise ValueError(
            "The isolated VeraGrid timing repeat did not retain every mode: "
            f"expected {expected_mode_count}, obtained {obtained_mode_count}."
        )
    timings: dict[str, float] = dict()
    timings["diagnostic_state_matrix_warm_repeat"] = matrix_seconds
    timings["diagnostic_eigenanalysis_pf_warm_repeat"] = eigen_seconds
    return timings
