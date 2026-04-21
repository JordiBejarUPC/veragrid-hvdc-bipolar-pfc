# SPDX-License-Identifier: MPL-2.0
"""
Critical EMT demo for the refactored frequency-zooming Matrix Pencil engine.

The demo no longer shows only one aliasing anecdote. It now runs several
independent numerical checks that stress the new EMT engine in the exact ways
that motivated the refactor: Floquet aliasing, fundamental masking, MIMO
observability, noise robustness, and irregular sampling.
"""

from __future__ import annotations

import sys
from typing import List, Tuple
from pathlib import Path

import numpy as np
import scipy.linalg as la
from numpy.lib.stride_tricks import sliding_window_view

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
SRC_ROOT: Path = PROJECT_ROOT / 'src'

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
else:
    pass

from VeraGridEngine.Simulations.SmallSignalStabilityEmt.era_matrix_pencil_core import (
    extract_matrix_pencil_results_from_data,
)
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.era_matrix_pencil_options import EraMatrixPencilOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.era_matrix_pencil_results import EraMatrixPencilResults


class CriticalCheckResult:
    """
    Small report object for one critical numerical scenario.

    The demo stores the final status in a typed object so the summary phase can
    stay explicit and easy to inspect.
    """

    __slots__ = (
        '_title',
        '_passed',
        '_details',
    )

    def __init__(self, title: str, passed: bool, details: List[str]) -> None:
        """
        Build one scenario report.

        :param title: Scenario title.
        :param passed: Final pass/fail status.
        :param details: Human-readable detail lines.
        :return: None.
        """
        self._title: str = title
        self._passed: bool = passed
        self._details: List[str] = list(details)

    def get_title(self) -> str:
        """
        Return the scenario title.

        :return: Scenario title.
        """
        return self._title

    def get_passed(self) -> bool:
        """
        Return the scenario status.

        :return: ``True`` when the scenario passed.
        """
        return self._passed

    def get_details(self) -> List[str]:
        """
        Return the scenario detail lines.

        :return: List of detail lines.
        """
        return list(self._details)


class AliasingBenchmark:
    """
    Encapsulate the decoupled aliasing benchmark.

    The benchmark compares Floquet theory with the new EMT zooming engine on a
    simple linear system with known pole locations.
    """

    __slots__ = (
        '_f_grid_hz',
        '_period_s',
        '_time_step_s',
        '_system_matrix',
    )

    def __init__(self, f_grid_hz: float = 50.0, time_step_s: float = 100.0e-6) -> None:
        """
        Build the aliasing benchmark.

        :param f_grid_hz: Fundamental grid frequency in Hz.
        :param time_step_s: EMT time step in seconds.
        :return: None.
        """
        self._f_grid_hz: float = float(f_grid_hz)
        self._period_s: float = 1.0 / self._f_grid_hz
        self._time_step_s: float = float(time_step_s)
        self._system_matrix: np.ndarray = build_aliasing_system_matrix()

    def run_floquet_analysis(self) -> np.ndarray:
        """
        Compute Floquet frequencies over the fundamental period.

        :return: Unique Floquet frequencies in Hz.
        """
        monodromy_matrix: np.ndarray = la.expm(self._system_matrix * self._period_s)
        multipliers: np.ndarray = la.eigvals(monodromy_matrix)
        s_poles: np.ndarray = np.log(multipliers) / self._period_s
        return compute_unique_frequencies_hz(s_poles, merge_tolerance_hz=1.0)

    def run_legacy_scalar_analysis(self, simulation_time_s: float) -> np.ndarray:
        """
        Run the old scalar matrix-pencil baseline.

        :param simulation_time_s: Simulation horizon in seconds.
        :return: Unique recovered frequencies in Hz.
        """
        time_data: np.ndarray
        observation_matrix: np.ndarray
        time_data, observation_matrix = simulate_linear_state_record(
            system_matrix=self._system_matrix,
            time_step_s=self._time_step_s,
            simulation_time_s=simulation_time_s,
        )
        scalar_signal: np.ndarray = np.sum(observation_matrix, axis=1).astype(np.float64)
        s_poles: np.ndarray = legacy_extract_matrix_pencil_poles(scalar_signal, self._time_step_s)
        return compute_unique_frequencies_hz(s_poles, merge_tolerance_hz=1.0)

    def run_modern_era_analysis(self, simulation_time_s: float) -> np.ndarray:
        """
        Run the refactored EMT zooming engine.

        :param simulation_time_s: Simulation horizon in seconds.
        :return: Unique recovered frequencies in Hz.
        """
        time_data: np.ndarray
        observation_matrix: np.ndarray
        time_data, observation_matrix = simulate_linear_state_record(
            system_matrix=self._system_matrix,
            time_step_s=self._time_step_s,
            simulation_time_s=simulation_time_s,
        )
        options: EraMatrixPencilOptions = build_zoom_options(
            band_limits=((0.0, 30.0), (30.0, 250.0), (250.0, 2000.0)),
            nominal_frequency_hz=0.0,
            use_notch_filtering=False,
            use_exponential_detrending=False,
        )
        observable_names: List[str] = list()
        observable_index: int = 0

        while observable_index < observation_matrix.shape[1]:
            observable_names.append(f'x_{observable_index}')
            observable_index += 1

        results: EraMatrixPencilResults = extract_matrix_pencil_results_from_data(
            time_data=time_data,
            y_data=observation_matrix,
            era_options=options,
            nominal_frequency_hz=0.0,
            observable_names=observable_names,
        )
        return compute_unique_frequencies_hz(results.eigenvalues_s, merge_tolerance_hz=1.0)


def build_aliasing_system_matrix() -> np.ndarray:
    """
    Build the decoupled system used in the aliasing benchmark.

    :return: Continuous-time state matrix.
    """
    poles: List[Tuple[float, float]] = list([
        (-0.5, 15.0),
        (-1.0, 120.0),
        (-5.0, 850.0),
    ])
    n_states: int = len(poles) * 2
    system_matrix: np.ndarray = np.zeros((n_states, n_states), dtype=np.float64)
    pole_index: int = 0

    while pole_index < len(poles):
        sigma_value: float = float(poles[pole_index][0])
        frequency_hz: float = float(poles[pole_index][1])
        omega_value: float = 2.0 * np.pi * frequency_hz
        state_index: int = 2 * pole_index

        system_matrix[state_index, state_index] = sigma_value
        system_matrix[state_index, state_index + 1] = omega_value
        system_matrix[state_index + 1, state_index] = -omega_value
        system_matrix[state_index + 1, state_index + 1] = sigma_value
        pole_index += 1

    return system_matrix


def simulate_linear_state_record(system_matrix: np.ndarray,
                                 time_step_s: float,
                                 simulation_time_s: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    Simulate one discrete-time linear state trajectory.

    :param system_matrix: Continuous-time state matrix.
    :param time_step_s: Time step in seconds.
    :param simulation_time_s: Simulation horizon in seconds.
    :return: Tuple ``(time_data, state_record)``.
    """
    n_steps: int = int(simulation_time_s / time_step_s)
    n_states: int = int(system_matrix.shape[0])
    time_data: np.ndarray = time_step_s * np.arange(n_steps, dtype=np.float64)
    discrete_matrix: np.ndarray = la.expm(system_matrix * time_step_s)
    state_record: np.ndarray = np.zeros((n_steps, n_states), dtype=np.float64)
    state_vector: np.ndarray = np.ones(n_states, dtype=np.float64)
    step_index: int = 0

    # The full state record is used so the modern engine can exploit MIMO
    # observability instead of collapsing the benchmark into one scalar trace.
    while step_index < n_steps:
        state_vector = discrete_matrix @ state_vector
        state_record[step_index, :] = state_vector
        step_index += 1

    return time_data, state_record


def legacy_extract_matrix_pencil_poles(y_signal: np.ndarray, time_step_s: float) -> np.ndarray:
    """
    Reproduce the historical scalar Matrix Pencil baseline.

    :param y_signal: Scalar observation signal.
    :param time_step_s: Sampling time step.
    :return: Continuous-time poles.
    """
    centered_signal: np.ndarray = y_signal - float(np.mean(y_signal))
    window_length: int = centered_signal.shape[0] // 3

    if window_length >= 2:
        hankel_matrix: np.ndarray = sliding_window_view(centered_signal, window_shape=window_length)
        u_matrix: np.ndarray
        singular_values: np.ndarray
        vh_matrix: np.ndarray
        u_matrix, singular_values, vh_matrix = la.svd(hankel_matrix, full_matrices=False)
        tolerance: float = float(singular_values[0]) * 1.0e-8
        rank_value: int = int(np.sum(singular_values > tolerance))

        if rank_value >= 1:
            right_vectors: np.ndarray = vh_matrix[:rank_value, :].T
            v1_matrix: np.ndarray = right_vectors[:-1, :]
            v2_matrix: np.ndarray = right_vectors[1:, :]
            transition_matrix: np.ndarray
            residuals: np.ndarray
            lstsq_rank: int
            lstsq_singular_values: np.ndarray
            transition_matrix, residuals, lstsq_rank, lstsq_singular_values = la.lstsq(v1_matrix, v2_matrix)
            z_poles: np.ndarray = la.eigvals(transition_matrix)
            s_poles: np.ndarray = np.log(z_poles) / time_step_s
        else:
            s_poles = np.zeros(0, dtype=np.complex128)
    else:
        s_poles = np.zeros(0, dtype=np.complex128)

    return s_poles


def build_zoom_options(band_limits: Tuple[Tuple[float, float], ...],
                       nominal_frequency_hz: float,
                       use_notch_filtering: bool,
                       use_exponential_detrending: bool) -> EraMatrixPencilOptions:
    """
    Build one consistent options object for the critical demo.

    :param band_limits: Tuple of analysis bands.
    :param nominal_frequency_hz: Nominal frequency used by the notch stage.
    :param use_notch_filtering: Enable the fundamental notch.
    :param use_exponential_detrending: Enable exponential DC detrending.
    :return: Configured options object.
    """
    options: EraMatrixPencilOptions = EraMatrixPencilOptions(
        max_modes=10,
        tol_deflation=1.0e-8,
        nominal_frequency_hz=nominal_frequency_hz,
        notch_quality_factor=55.0,
        minimum_samples_per_band=64,
        min_mode_energy_ratio=0.001,
        block_rows_ratio=0.18,
        use_notch_filtering=use_notch_filtering,
        use_forward_backward=True,
        use_exponential_detrending=use_exponential_detrending,
        maximum_observables=0,
    )
    options.set_analysis_bands(band_limits)
    return options


def build_fundamental_masking_signal() -> Tuple[np.ndarray, np.ndarray]:
    """
    Build one signal dominated by the nominal-frequency carrier.

    :return: Tuple ``(time_data, observation_matrix)``.
    """
    time_step_s: float = 1.0e-4
    time_data: np.ndarray = np.arange(0.0, 0.50, time_step_s, dtype=np.float64)
    rng = np.random.default_rng(19)
    mode_super: np.ndarray = np.exp((-1.5 + 1j * 2.0 * np.pi * 120.0) * time_data)
    mode_ripple: np.ndarray = np.exp((-6.5 + 1j * 2.0 * np.pi * 900.0) * time_data)
    dominant_fundamental: np.ndarray = 14.0 * np.cos(2.0 * np.pi * 50.0 * time_data)
    noise: np.ndarray = 0.001 * rng.standard_normal(time_data.shape[0])
    channel_a: np.ndarray = dominant_fundamental + 0.30 * np.real(mode_super) + 0.08 * np.real(mode_ripple) + noise
    channel_b: np.ndarray = 0.75 * dominant_fundamental + 0.22 * np.real((0.5 - 0.6j) * mode_super) + 0.10 * np.real((0.2 + 0.4j) * mode_ripple)
    observation_matrix: np.ndarray = np.column_stack((channel_a, channel_b)).astype(np.float64)
    return time_data, observation_matrix


def build_split_observability_signal() -> Tuple[np.ndarray, np.ndarray]:
    """
    Build one MIMO observability stress case.

    :return: Tuple ``(time_data, observation_matrix)``.
    """
    time_step_s: float = 1.0e-4
    time_data: np.ndarray = np.arange(0.0, 0.30, time_step_s, dtype=np.float64)
    mode_low: np.ndarray = np.exp((-1.2 + 1j * 2.0 * np.pi * 90.0) * time_data)
    mode_high: np.ndarray = np.exp((-5.0 + 1j * 2.0 * np.pi * 320.0) * time_data)
    channel_a: np.ndarray = np.real(mode_low).astype(np.float64)
    channel_b: np.ndarray = (0.9 * np.real((0.3 + 0.8j) * mode_high)).astype(np.float64)
    observation_matrix: np.ndarray = np.column_stack((channel_a, channel_b)).astype(np.float64)
    return time_data, observation_matrix


def build_noisy_offset_signal() -> Tuple[np.ndarray, np.ndarray]:
    """
    Build one noisy EMT-like signal with a decaying DC component.

    :return: Tuple ``(time_data, observation_matrix)``.
    """
    time_step_s: float = 1.0e-4
    time_data: np.ndarray = np.arange(0.0, 0.32, time_step_s, dtype=np.float64)
    rng = np.random.default_rng(31)
    mode_super: np.ndarray = np.exp((-1.8 + 1j * 2.0 * np.pi * 125.0) * time_data)
    mode_ripple: np.ndarray = np.exp((-7.0 + 1j * 2.0 * np.pi * 760.0) * time_data)
    decaying_offset: np.ndarray = 2.0 * np.exp(-14.0 * time_data)
    white_noise_a: np.ndarray = 0.003 * rng.standard_normal(time_data.shape[0])
    white_noise_b: np.ndarray = 0.003 * rng.standard_normal(time_data.shape[0])
    channel_a: np.ndarray = decaying_offset + 0.25 * np.real(mode_super) + 0.07 * np.real(mode_ripple) + white_noise_a
    channel_b: np.ndarray = -0.6 * decaying_offset + 0.18 * np.real((0.4 - 0.3j) * mode_super) + 0.10 * np.real((0.2 + 0.7j) * mode_ripple) + white_noise_b
    observation_matrix: np.ndarray = np.column_stack((channel_a, channel_b)).astype(np.float64)
    return time_data, observation_matrix


def build_irregular_sampling_signal() -> Tuple[np.ndarray, np.ndarray]:
    """
    Build one signal on a slightly irregular time grid.

    :return: Tuple ``(time_data, observation_matrix)``.
    """
    base_step_s: float = 1.0e-4
    n_samples: int = 2800
    sample_index: np.ndarray = np.arange(n_samples, dtype=np.float64)
    adaptive_step: np.ndarray = base_step_s * (1.0 + 0.03 * np.sin(0.01 * sample_index))
    time_data: np.ndarray = np.cumsum(adaptive_step).astype(np.float64)
    time_data -= time_data[0]
    mode_super: np.ndarray = np.exp((-1.6 + 1j * 2.0 * np.pi * 120.0) * time_data)
    mode_high: np.ndarray = np.exp((-6.0 + 1j * 2.0 * np.pi * 420.0) * time_data)
    channel_a: np.ndarray = (0.45 * np.real(mode_super) + 0.12 * np.real(mode_high)).astype(np.float64)
    channel_b: np.ndarray = (0.25 * np.real((0.4 + 0.7j) * mode_super) + 0.15 * np.real((0.3 - 0.2j) * mode_high)).astype(np.float64)
    observation_matrix: np.ndarray = np.column_stack((channel_a, channel_b)).astype(np.float64)
    return time_data, observation_matrix


def run_modern_engine(time_data: np.ndarray,
                      observation_matrix: np.ndarray,
                      nominal_frequency_hz: float,
                      band_limits: Tuple[Tuple[float, float], ...],
                      use_notch_filtering: bool,
                      use_exponential_detrending: bool,
                      observable_names: List[str]) -> np.ndarray:
    """
    Execute the refactored EMT engine and return unique frequencies.

    :param time_data: Time vector.
    :param observation_matrix: Observation matrix.
    :param nominal_frequency_hz: Nominal system frequency.
    :param band_limits: Analysis bands.
    :param use_notch_filtering: Enable the notch filter.
    :param use_exponential_detrending: Enable exponential DC detrending.
    :param observable_names: Channel labels.
    :return: Unique recovered frequencies in Hz.
    """
    options: EraMatrixPencilOptions = build_zoom_options(
        band_limits=band_limits,
        nominal_frequency_hz=nominal_frequency_hz,
        use_notch_filtering=use_notch_filtering,
        use_exponential_detrending=use_exponential_detrending,
    )
    results: EraMatrixPencilResults = extract_matrix_pencil_results_from_data(
        time_data=time_data,
        y_data=observation_matrix,
        era_options=options,
        nominal_frequency_hz=nominal_frequency_hz,
        observable_names=observable_names,
    )
    return compute_unique_frequencies_hz(results.eigenvalues_s, merge_tolerance_hz=1.0)


def compute_unique_frequencies_hz(eigenvalues_s: np.ndarray, merge_tolerance_hz: float) -> np.ndarray:
    """
    Convert poles into a sorted compact frequency list.

    :param eigenvalues_s: Continuous-time poles.
    :param merge_tolerance_hz: Frequency merge tolerance.
    :return: Sorted vector of unique frequencies in Hz.
    """
    raw_frequencies_hz: np.ndarray = np.abs(np.imag(eigenvalues_s)) / (2.0 * np.pi)
    sorted_frequencies_hz: np.ndarray = np.sort(raw_frequencies_hz.astype(np.float64))
    unique_list: List[float] = list()
    frequency_index: int = 0
    n_frequencies: int = int(sorted_frequencies_hz.shape[0])

    while frequency_index < n_frequencies:
        candidate_frequency_hz: float = float(sorted_frequencies_hz[frequency_index])

        if len(unique_list) == 0:
            unique_list.append(candidate_frequency_hz)
        else:
            last_frequency_hz: float = unique_list[-1]

            if abs(candidate_frequency_hz - last_frequency_hz) > merge_tolerance_hz:
                unique_list.append(candidate_frequency_hz)
            else:
                pass

        frequency_index += 1

    return np.asarray(unique_list, dtype=np.float64)


def has_frequency_near(frequencies_hz: np.ndarray, target_frequency_hz: float, tolerance_hz: float) -> bool:
    """
    Check whether a recovered frequency is close to the target.

    :param frequencies_hz: Detected frequencies.
    :param target_frequency_hz: Target frequency.
    :param tolerance_hz: Absolute tolerance.
    :return: ``True`` when a match exists.
    """
    if frequencies_hz.shape[0] > 0:
        return bool(np.any(np.abs(frequencies_hz - target_frequency_hz) <= tolerance_hz))
    else:
        return False


def format_frequency_vector(frequencies_hz: np.ndarray) -> str:
    """
    Format one frequency vector for terminal output.

    :param frequencies_hz: Frequency vector.
    :return: Formatted string.
    """
    if frequencies_hz.shape[0] > 0:
        formatted_list: List[str] = list()
        frequency_index: int = 0
        n_frequencies: int = int(frequencies_hz.shape[0])

        while frequency_index < n_frequencies:
            formatted_list.append(f'{float(frequencies_hz[frequency_index]):7.2f} Hz')
            frequency_index += 1

        return '[' + ', '.join(formatted_list) + ']'
    else:
        return '[]'


def build_status_label(passed: bool) -> str:
    """
    Build the status label used by the summary printer.

    :param passed: Scenario status.
    :return: Label string.
    """
    if passed:
        return 'PASS'
    else:
        return 'FAIL'


def print_check_result(result: CriticalCheckResult) -> None:
    """
    Print one scenario report.

    :param result: Scenario report.
    :return: None.
    """
    print('\n' + '-' * 100)
    print(result.get_title())
    print('-' * 100)
    detail_index: int = 0
    details: List[str] = result.get_details()

    while detail_index < len(details):
        print(details[detail_index])
        detail_index += 1

    print(f"Result: {build_status_label(result.get_passed())}")


def run_aliasing_check() -> CriticalCheckResult:
    """
    Demonstrate that Floquet aliases super-synchronous and high-frequency modes.

    :return: Scenario report.
    """
    benchmark: AliasingBenchmark = AliasingBenchmark(f_grid_hz=50.0, time_step_s=100.0e-6)
    ground_truth_hz: np.ndarray = np.asarray([15.0, 120.0, 850.0], dtype=np.float64)
    floquet_frequencies_hz: np.ndarray = benchmark.run_floquet_analysis()
    legacy_frequencies_hz: np.ndarray = benchmark.run_legacy_scalar_analysis(simulation_time_s=0.24)
    modern_frequencies_hz: np.ndarray = benchmark.run_modern_era_analysis(simulation_time_s=0.24)

    # The scenario passes only if Floquet aliases the fast content and the new
    # EMT engine recovers the true modes from the ringdown record.
    floquet_misses_120: bool = not has_frequency_near(floquet_frequencies_hz, 120.0, 5.0)
    floquet_misses_850: bool = not has_frequency_near(floquet_frequencies_hz, 850.0, 20.0)
    modern_finds_120: bool = has_frequency_near(modern_frequencies_hz, 120.0, 5.0)
    modern_finds_850: bool = has_frequency_near(modern_frequencies_hz, 850.0, 30.0)
    passed: bool = floquet_misses_120 and floquet_misses_850 and modern_finds_120 and modern_finds_850

    details: List[str] = list()
    details.append(f'Ground truth          : {format_frequency_vector(ground_truth_hz)}')
    details.append(f'Floquet frequencies   : {format_frequency_vector(floquet_frequencies_hz)}')
    details.append(f'Legacy scalar ERA     : {format_frequency_vector(legacy_frequencies_hz)}')
    details.append(f'Refactored EMT ERA    : {format_frequency_vector(modern_frequencies_hz)}')
    details.append('Expectation           : Floquet folds 120 Hz and 850 Hz, while the EMT engine keeps them visible.')
    return CriticalCheckResult('Check 1 - Floquet Aliasing vs EMT Zooming', passed, details)


def run_fundamental_masking_check() -> CriticalCheckResult:
    """
    Demonstrate the need for the nominal-frequency notch filter.

    :return: Scenario report.
    """
    time_data: np.ndarray
    observation_matrix: np.ndarray
    time_data, observation_matrix = build_fundamental_masking_signal()
    scalar_signal: np.ndarray = np.sum(observation_matrix, axis=1).astype(np.float64)
    legacy_poles_s: np.ndarray = legacy_extract_matrix_pencil_poles(scalar_signal, float(time_data[1] - time_data[0]))
    legacy_frequencies_hz: np.ndarray = compute_unique_frequencies_hz(legacy_poles_s, merge_tolerance_hz=1.0)
    modern_frequencies_hz: np.ndarray = run_modern_engine(
        time_data=time_data,
        observation_matrix=observation_matrix,
        nominal_frequency_hz=50.0,
        band_limits=((25.0, 250.0), (250.0, 1400.0)),
        use_notch_filtering=True,
        use_exponential_detrending=True,
        observable_names=list(['ia', 'ib']),
    )
    passed: bool = (
        has_frequency_near(modern_frequencies_hz, 120.0, 6.0)
        and has_frequency_near(modern_frequencies_hz, 900.0, 45.0)
        and not has_frequency_near(modern_frequencies_hz, 50.0, 4.0)
    )

    details: List[str] = list()
    details.append(f'Legacy scalar baseline: {format_frequency_vector(legacy_frequencies_hz)}')
    details.append(f'Refactored EMT ERA    : {format_frequency_vector(modern_frequencies_hz)}')
    details.append('Expectation           : the 50 Hz carrier must be rejected so the 120 Hz and 900 Hz modes become visible.')
    return CriticalCheckResult('Check 2 - Fundamental Masking and Notch Filtering', passed, details)


def run_mimo_observability_check() -> CriticalCheckResult:
    """
    Demonstrate that a MIMO Hankel matrix preserves split observability.

    :return: Scenario report.
    """
    time_data: np.ndarray
    observation_matrix: np.ndarray
    time_data, observation_matrix = build_split_observability_signal()
    scalar_low_poles_s: np.ndarray = legacy_extract_matrix_pencil_poles(observation_matrix[:, 0], float(time_data[1] - time_data[0]))
    scalar_high_poles_s: np.ndarray = legacy_extract_matrix_pencil_poles(observation_matrix[:, 1], float(time_data[1] - time_data[0]))
    scalar_low_frequencies_hz: np.ndarray = compute_unique_frequencies_hz(scalar_low_poles_s, merge_tolerance_hz=1.0)
    scalar_high_frequencies_hz: np.ndarray = compute_unique_frequencies_hz(scalar_high_poles_s, merge_tolerance_hz=1.0)
    modern_frequencies_hz: np.ndarray = run_modern_engine(
        time_data=time_data,
        observation_matrix=observation_matrix,
        nominal_frequency_hz=50.0,
        band_limits=((40.0, 140.0), (200.0, 420.0)),
        use_notch_filtering=False,
        use_exponential_detrending=False,
        observable_names=list(['mode_low', 'mode_high']),
    )
    passed: bool = (
        has_frequency_near(modern_frequencies_hz, 90.0, 5.0)
        and has_frequency_near(modern_frequencies_hz, 320.0, 15.0)
        and not has_frequency_near(scalar_low_frequencies_hz, 320.0, 15.0)
        and not has_frequency_near(scalar_high_frequencies_hz, 90.0, 5.0)
    )

    details: List[str] = list()
    details.append(f'Scalar channel A      : {format_frequency_vector(scalar_low_frequencies_hz)}')
    details.append(f'Scalar channel B      : {format_frequency_vector(scalar_high_frequencies_hz)}')
    details.append(f'Refactored EMT ERA    : {format_frequency_vector(modern_frequencies_hz)}')
    details.append('Expectation           : no single scalar channel sees both modes, while the MIMO extraction does.')
    return CriticalCheckResult('Check 3 - MIMO Observability vs Scalar Selection', passed, details)


def run_noise_and_offset_check() -> CriticalCheckResult:
    """
    Demonstrate robustness against decaying DC offsets and additive noise.

    :return: Scenario report.
    """
    time_data: np.ndarray
    observation_matrix: np.ndarray
    time_data, observation_matrix = build_noisy_offset_signal()
    modern_frequencies_hz: np.ndarray = run_modern_engine(
        time_data=time_data,
        observation_matrix=observation_matrix,
        nominal_frequency_hz=50.0,
        band_limits=((25.0, 250.0), (250.0, 1200.0)),
        use_notch_filtering=False,
        use_exponential_detrending=True,
        observable_names=list(['noisy_a', 'noisy_b']),
    )
    passed: bool = has_frequency_near(modern_frequencies_hz, 125.0, 6.0) and has_frequency_near(modern_frequencies_hz, 760.0, 35.0)

    details: List[str] = list()
    details.append(f'Refactored EMT ERA    : {format_frequency_vector(modern_frequencies_hz)}')
    details.append('Expectation           : the decaying offset must not bury the oscillatory modes when detrending is enabled.')
    return CriticalCheckResult('Check 4 - Noise and Exponential DC Offset Robustness', passed, details)


def run_irregular_sampling_check() -> CriticalCheckResult:
    """
    Demonstrate the spline re-sampling stage on a slightly adaptive time grid.

    :return: Scenario report.
    """
    time_data: np.ndarray
    observation_matrix: np.ndarray
    time_data, observation_matrix = build_irregular_sampling_signal()
    modern_frequencies_hz: np.ndarray = run_modern_engine(
        time_data=time_data,
        observation_matrix=observation_matrix,
        nominal_frequency_hz=50.0,
        band_limits=((40.0, 180.0), (180.0, 520.0)),
        use_notch_filtering=False,
        use_exponential_detrending=False,
        observable_names=list(['irregular_a', 'irregular_b']),
    )
    passed: bool = has_frequency_near(modern_frequencies_hz, 120.0, 6.0) and has_frequency_near(modern_frequencies_hz, 420.0, 20.0)

    details: List[str] = list()
    details.append(f'Refactored EMT ERA    : {format_frequency_vector(modern_frequencies_hz)}')
    details.append('Expectation           : the uniform-grid reconstruction must preserve both injected modal bands.')
    return CriticalCheckResult('Check 5 - Irregular Sampling and Spline Re-Sampling', passed, details)


def run_demo() -> None:
    """
    Execute the full critical demo suite.

    :return: None.
    """
    print('=' * 100)
    print('Critical Demo - EMT Frequency-Zooming Matrix Pencil')
    print('=' * 100)
    print('The demo evaluates aliasing, fundamental masking, MIMO observability, noise robustness, and irregular sampling.')

    results_list: List[CriticalCheckResult] = list()
    results_list.append(run_aliasing_check())
    results_list.append(run_fundamental_masking_check())
    results_list.append(run_mimo_observability_check())
    results_list.append(run_noise_and_offset_check())
    results_list.append(run_irregular_sampling_check())

    result_index: int = 0
    n_results: int = len(results_list)
    passed_counter: int = 0

    while result_index < n_results:
        current_result: CriticalCheckResult = results_list[result_index]
        print_check_result(current_result)

        if current_result.get_passed():
            passed_counter += 1
        else:
            pass

        result_index += 1

    print('\n' + '=' * 100)
    print(f'Summary: {passed_counter}/{n_results} critical checks passed.')
    print('=' * 100)


if __name__ == '__main__':
    run_demo()
