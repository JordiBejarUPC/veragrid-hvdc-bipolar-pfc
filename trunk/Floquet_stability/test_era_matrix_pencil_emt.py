from __future__ import annotations

import sys
from typing import List, Tuple
from pathlib import Path

import numpy as np

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
SRC_ROOT: Path = PROJECT_ROOT / 'src'

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
else:
    pass

from VeraGridEngine.Simulations.SmallSignalStabilityEmt.era_matrix_pencil_core import (
    extract_matrix_pencil_results_from_data,
)
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.era_matrix_pencil_driver import (
    extract_matrix_pencil_poles,
)
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.era_matrix_pencil_options import EraMatrixPencilOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.era_matrix_pencil_results import EraMatrixPencilResults
from VeraGridEngine.enumerations import ResultTypes


def build_zoom_options(band_limits: Tuple[Tuple[float, float], ...],
                       nominal_frequency_hz: float = 50.0,
                       use_notch_filtering: bool = True,
                       use_forward_backward: bool = True,
                       use_exponential_detrending: bool = True,
                       maximum_observables: int = 0) -> EraMatrixPencilOptions:
    """
    Build one consistent options object for the EMT zooming tests.

    :param band_limits: Tuple of analysis bands.
    :param nominal_frequency_hz: Nominal frequency used by the notch stage.
    :param use_notch_filtering: Enable the fundamental notch.
    :param use_forward_backward: Enable forward-backward symmetry.
    :param use_exponential_detrending: Enable exponential DC detrending.
    :param maximum_observables: Optional cap on the number of channels.
    :return: Configured options object.
    """
    options: EraMatrixPencilOptions = EraMatrixPencilOptions(
        max_modes=12,
        tol_deflation=1.0e-8,
        nominal_frequency_hz=nominal_frequency_hz,
        notch_quality_factor=55.0,
        minimum_samples_per_band=96,
        min_mode_energy_ratio=0.001,
        block_rows_ratio=0.22,
        use_notch_filtering=use_notch_filtering,
        use_forward_backward=use_forward_backward,
        use_exponential_detrending=use_exponential_detrending,
        maximum_observables=maximum_observables,
    )
    options.set_analysis_bands(band_limits)
    return options


def build_synthetic_multiband_signal() -> Tuple[np.ndarray, np.ndarray]:
    """
    Build one deterministic multichannel EMT-like record.

    :return: Tuple ``(time_data, observation_matrix)``.
    """
    time_step: float = 1.0e-4
    time_data: np.ndarray = np.arange(0.0, 0.45, time_step, dtype=np.float64)
    rng = np.random.default_rng(7)

    # The synthetic signal places one mode in the super-synchronous band and
    # another mode in the inverter-ripple band while also injecting a dominant
    # 50 Hz carrier and a decaying DC term.
    mode_super: np.ndarray = np.exp((-2.0 + 1j * 2.0 * np.pi * 120.0) * time_data)
    mode_ripple: np.ndarray = np.exp((-8.0 + 1j * 2.0 * np.pi * 850.0) * time_data)
    fundamental: np.ndarray = 6.0 * np.cos(2.0 * np.pi * 50.0 * time_data)
    decaying_offset: np.ndarray = 1.2 * np.exp(-18.0 * time_data)
    noise_a: np.ndarray = 0.0015 * rng.standard_normal(time_data.shape[0])
    noise_b: np.ndarray = 0.0015 * rng.standard_normal(time_data.shape[0])

    channel_a: np.ndarray = (
        fundamental
        + decaying_offset
        + 0.35 * np.real(mode_super)
        + 0.09 * np.real((0.8 + 0.1j) * mode_ripple)
        + noise_a
    )
    channel_b: np.ndarray = (
        0.65 * fundamental
        - 0.55 * decaying_offset
        + 0.18 * np.real((0.4 - 0.9j) * mode_super)
        + 0.14 * np.real((0.2 + 0.7j) * mode_ripple)
        + noise_b
    )
    observation_matrix: np.ndarray = np.column_stack((channel_a, channel_b)).astype(np.float64)
    return time_data, observation_matrix


def build_fundamental_masking_signal() -> Tuple[np.ndarray, np.ndarray]:
    """
    Build one record where the 50 Hz component intentionally dominates.

    :return: Tuple ``(time_data, observation_matrix)``.
    """
    time_step: float = 1.0e-4
    time_data: np.ndarray = np.arange(0.0, 0.50, time_step, dtype=np.float64)
    rng = np.random.default_rng(19)

    # This scenario stresses the notch filter because the fundamental is much
    # larger than the target control modes and would otherwise monopolize the SVD.
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
    Build one record where each mode is visible on a different channel.

    :return: Tuple ``(time_data, observation_matrix)``.
    """
    time_step: float = 1.0e-4
    time_data: np.ndarray = np.arange(0.0, 0.40, time_step, dtype=np.float64)

    # The first channel contains only the low-frequency mode and the second
    # channel contains only the high-frequency mode. A scalar method cannot see both.
    mode_low: np.ndarray = np.exp((-1.2 + 1j * 2.0 * np.pi * 90.0) * time_data)
    mode_high: np.ndarray = np.exp((-5.0 + 1j * 2.0 * np.pi * 320.0) * time_data)

    channel_a: np.ndarray = np.real(mode_low).astype(np.float64)
    channel_b: np.ndarray = (0.9 * np.real((0.3 + 0.8j) * mode_high)).astype(np.float64)
    observation_matrix: np.ndarray = np.column_stack((channel_a, channel_b)).astype(np.float64)
    return time_data, observation_matrix


def build_single_pair_signal() -> Tuple[np.ndarray, np.ndarray]:
    """
    Build one real signal generated by a single oscillatory pole pair.

    :return: Tuple ``(time_data, scalar_signal)``.
    """
    time_step: float = 1.0e-4
    time_data: np.ndarray = np.arange(0.0, 0.35, time_step, dtype=np.float64)
    mode_pair: np.ndarray = np.exp((-1.8 + 1j * 2.0 * np.pi * 140.0) * time_data)
    scalar_signal: np.ndarray = np.real((0.8 + 0.2j) * mode_pair).astype(np.float64)
    return time_data, scalar_signal.reshape(-1, 1)


def build_irregular_time_signal() -> Tuple[np.ndarray, np.ndarray]:
    """
    Build one signal on a slightly irregular time grid.

    :return: Tuple ``(time_data, observation_matrix)``.
    """
    base_step: float = 1.0e-4
    n_samples: int = 4200
    sample_index: np.ndarray = np.arange(n_samples, dtype=np.float64)
    adaptive_step: np.ndarray = base_step * (1.0 + 0.03 * np.sin(0.01 * sample_index))
    time_data: np.ndarray = np.cumsum(adaptive_step).astype(np.float64)
    time_data -= time_data[0]

    # The signal stays linear but the time grid is not exactly uniform, so the
    # spline re-sampling stage must reconstruct a shift-invariant grid before the pencil.
    mode_super: np.ndarray = np.exp((-1.6 + 1j * 2.0 * np.pi * 120.0) * time_data)
    mode_ripple: np.ndarray = np.exp((-6.0 + 1j * 2.0 * np.pi * 420.0) * time_data)
    channel_a: np.ndarray = (0.45 * np.real(mode_super) + 0.12 * np.real(mode_ripple)).astype(np.float64)
    channel_b: np.ndarray = (0.25 * np.real((0.4 + 0.7j) * mode_super) + 0.15 * np.real((0.3 - 0.2j) * mode_ripple)).astype(np.float64)
    observation_matrix: np.ndarray = np.column_stack((channel_a, channel_b)).astype(np.float64)
    return time_data, observation_matrix


def compute_unique_frequencies_hz(eigenvalues_s: np.ndarray, merge_tolerance_hz: float = 1.0) -> np.ndarray:
    """
    Convert poles into a compact sorted list of unique frequencies.

    :param eigenvalues_s: Continuous-time poles.
    :param merge_tolerance_hz: Frequency merge tolerance.
    :return: Sorted vector of unique frequencies.
    """
    raw_frequencies_hz: np.ndarray = np.abs(np.imag(eigenvalues_s)) / (2.0 * np.pi)
    sorted_frequencies_hz: np.ndarray = np.sort(raw_frequencies_hz.astype(np.float64))
    unique_list: List[float] = list()
    frequency_index: int = 0
    n_freq: int = int(sorted_frequencies_hz.shape[0])

    while frequency_index < n_freq:
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


def has_frequency_near(frequencies_hz: np.ndarray,
                       target_frequency_hz: float,
                       tolerance_hz: float) -> bool:
    """
    Check whether one detected frequency is close to the target.

    :param frequencies_hz: Detected frequencies.
    :param target_frequency_hz: Target frequency.
    :param tolerance_hz: Absolute tolerance.
    :return: ``True`` when a match exists.
    """
    if frequencies_hz.shape[0] > 0:
        return bool(np.any(np.abs(frequencies_hz - target_frequency_hz) <= tolerance_hz))
    else:
        return False


def count_frequencies_near(frequencies_hz: np.ndarray,
                           target_frequency_hz: float,
                           tolerance_hz: float) -> int:
    """
    Count how many detected frequencies are close to the target.

    :param frequencies_hz: Detected frequencies.
    :param target_frequency_hz: Target frequency.
    :param tolerance_hz: Absolute tolerance.
    :return: Number of matches.
    """
    if frequencies_hz.shape[0] > 0:
        return int(np.sum(np.abs(frequencies_hz - target_frequency_hz) <= tolerance_hz))
    else:
        return 0


def has_conjugate_partner(eigenvalues_s: np.ndarray,
                          reference_index: int,
                          real_tolerance: float,
                          frequency_tolerance_hz: float) -> bool:
    """
    Check whether the reference pole has its conjugate partner.

    :param eigenvalues_s: Continuous-time poles.
    :param reference_index: Reference index.
    :param real_tolerance: Real-part tolerance.
    :param frequency_tolerance_hz: Frequency tolerance in Hz.
    :return: ``True`` when the conjugate is found.
    """
    reference_pole: complex = complex(eigenvalues_s[reference_index])
    conjugate_target: complex = np.conjugate(reference_pole)
    mode_index: int = 0
    n_modes: int = int(eigenvalues_s.shape[0])

    while mode_index < n_modes:
        if mode_index != reference_index:
            candidate_pole: complex = complex(eigenvalues_s[mode_index])
            real_delta: float = abs(float(np.real(candidate_pole - conjugate_target)))
            frequency_delta_hz: float = abs(float(np.imag(candidate_pole - conjugate_target)) / (2.0 * np.pi))

            if real_delta <= real_tolerance and frequency_delta_hz <= frequency_tolerance_hz:
                return True
            else:
                pass
        else:
            pass

        mode_index += 1

    return False


def test_frequency_zooming_matrix_pencil_recovers_multi_band_modes() -> None:
    """
    Validate recovery of both super-synchronous and ripple modes.

    :return: None.
    """
    time_data: np.ndarray
    observation_matrix: np.ndarray
    time_data, observation_matrix = build_synthetic_multiband_signal()
    options: EraMatrixPencilOptions = build_zoom_options(((25.0, 250.0), (250.0, 1400.0)))

    # The extracted poles must contain one mode in each configured zoom band.
    results: EraMatrixPencilResults = extract_matrix_pencil_results_from_data(
        time_data=time_data,
        y_data=observation_matrix,
        era_options=options,
        nominal_frequency_hz=50.0,
        observable_names=list(['ia', 'ib']),
    )
    unique_frequencies_hz: np.ndarray = compute_unique_frequencies_hz(results.eigenvalues_s)

    assert results.eigenvalues_s.shape[0] >= 2
    assert has_frequency_near(unique_frequencies_hz, 120.0, 5.0)
    assert has_frequency_near(unique_frequencies_hz, 850.0, 35.0)
    assert float(np.max(results.modal_energy)) > 0.001


def test_notch_filter_suppresses_dominant_fundamental() -> None:
    """
    Validate that the notch stage removes the 50 Hz dominant component.

    :return: None.
    """
    time_data: np.ndarray
    observation_matrix: np.ndarray
    time_data, observation_matrix = build_fundamental_masking_signal()
    options: EraMatrixPencilOptions = build_zoom_options(((25.0, 250.0), (250.0, 1400.0)), use_notch_filtering=True)

    # The band plan still includes the 50 Hz region, so the absence of a strong
    # 50 Hz pole after extraction is a direct consequence of the notch filter.
    results: EraMatrixPencilResults = extract_matrix_pencil_results_from_data(
        time_data=time_data,
        y_data=observation_matrix,
        era_options=options,
        nominal_frequency_hz=50.0,
        observable_names=list(['ia', 'ib']),
    )
    unique_frequencies_hz: np.ndarray = compute_unique_frequencies_hz(results.eigenvalues_s)

    assert has_frequency_near(unique_frequencies_hz, 120.0, 6.0)
    assert has_frequency_near(unique_frequencies_hz, 900.0, 45.0)
    assert count_frequencies_near(unique_frequencies_hz, 50.0, 4.0) == 0


def test_mimo_observability_recovers_split_modes() -> None:
    """
    Validate that the MIMO Hankel matrix recovers modes split across channels.

    :return: None.
    """
    time_data: np.ndarray
    observation_matrix: np.ndarray
    time_data, observation_matrix = build_split_observability_signal()
    options: EraMatrixPencilOptions = build_zoom_options(((40.0, 140.0), (200.0, 420.0)))

    # The modern engine sees both channels simultaneously, while a scalar call
    # on the first channel cannot recover the high-frequency mode that is absent there.
    mimo_results: EraMatrixPencilResults = extract_matrix_pencil_results_from_data(
        time_data=time_data,
        y_data=observation_matrix,
        era_options=options,
        nominal_frequency_hz=50.0,
        observable_names=list(['mode_low', 'mode_high']),
    )
    scalar_poles_s: np.ndarray = extract_matrix_pencil_poles(
        y_signal=observation_matrix[:, 0],
        dt=float(time_data[1] - time_data[0]),
        max_modes=6,
        tol_deflation=1.0e-8,
    )
    mimo_frequencies_hz: np.ndarray = compute_unique_frequencies_hz(mimo_results.eigenvalues_s)
    scalar_frequencies_hz: np.ndarray = compute_unique_frequencies_hz(scalar_poles_s)

    assert has_frequency_near(mimo_frequencies_hz, 90.0, 5.0)
    assert has_frequency_near(mimo_frequencies_hz, 320.0, 15.0)
    assert not has_frequency_near(scalar_frequencies_hz, 320.0, 15.0)


def test_forward_backward_enforces_conjugate_pairs() -> None:
    """
    Validate that the forward-backward solver preserves conjugate symmetry.

    :return: None.
    """
    time_data: np.ndarray
    observation_matrix: np.ndarray
    time_data, observation_matrix = build_single_pair_signal()
    options: EraMatrixPencilOptions = build_zoom_options(((60.0, 220.0),), use_forward_backward=True)

    # For a real-valued observation channel every oscillatory mode must appear
    # together with its conjugate partner in the identified spectrum.
    results: EraMatrixPencilResults = extract_matrix_pencil_results_from_data(
        time_data=time_data,
        y_data=observation_matrix,
        era_options=options,
        nominal_frequency_hz=50.0,
        observable_names=list(['x']),
    )
    poles_s: np.ndarray = results.eigenvalues_s
    positive_index_list: List[int] = list()
    mode_index: int = 0

    while mode_index < poles_s.shape[0]:
        if float(np.imag(poles_s[mode_index])) > 1.0:
            positive_index_list.append(mode_index)
        else:
            pass

        mode_index += 1

    assert len(positive_index_list) >= 1

    pair_index: int = 0
    n_positive: int = len(positive_index_list)

    while pair_index < n_positive:
        reference_index: int = positive_index_list[pair_index]
        assert has_conjugate_partner(poles_s, reference_index, 1.0, 5.0)
        pair_index += 1


def test_irregular_time_grid_is_resampled_before_extraction() -> None:
    """
    Validate that slight time-grid irregularity is repaired before extraction.

    :return: None.
    """
    time_data: np.ndarray
    observation_matrix: np.ndarray
    time_data, observation_matrix = build_irregular_time_signal()
    options: EraMatrixPencilOptions = build_zoom_options(((40.0, 180.0), (180.0, 520.0)))

    # The uniform-grid reconstruction is essential because the discrete-time pole
    # model requires one fixed time step for the logarithmic mapping.
    results: EraMatrixPencilResults = extract_matrix_pencil_results_from_data(
        time_data=time_data,
        y_data=observation_matrix,
        era_options=options,
        nominal_frequency_hz=50.0,
        observable_names=list(['xa', 'xb']),
    )
    frequencies_hz: np.ndarray = compute_unique_frequencies_hz(results.eigenvalues_s)

    assert has_frequency_near(frequencies_hz, 120.0, 6.0)
    assert has_frequency_near(frequencies_hz, 420.0, 20.0)


def test_results_metadata_and_tables_are_consistent() -> None:
    """
    Validate public metadata, table export and plotting-safe access.

    :return: None.
    """
    poles_s: np.ndarray = np.array([
        -1.0 + 1j * 2.0 * np.pi * 120.0,
        -1.0 - 1j * 2.0 * np.pi * 120.0,
    ], dtype=np.complex128)
    residues: np.ndarray = np.array([
        [1.0 + 0.2j, 0.5 - 0.1j],
        [1.0 - 0.2j, 0.5 + 0.1j],
    ], dtype=np.complex128)
    modal_energy: np.ndarray = np.array([0.6, 0.6], dtype=np.float64)
    reconstruction_errors: np.ndarray = np.array([0.01, 0.01], dtype=np.float64)
    band_low_hz: np.ndarray = np.array([25.0, 25.0], dtype=np.float64)
    band_high_hz: np.ndarray = np.array([250.0, 250.0], dtype=np.float64)
    selected_orders: np.ndarray = np.array([4, 4], dtype=np.int_)
    observable_count: np.ndarray = np.array([2, 2], dtype=np.int_)

    # This direct construction validates that the result container stays usable
    # even when loaded from persisted arrays instead of a live extraction run.
    results: EraMatrixPencilResults = EraMatrixPencilResults(
        eigenvalues_s=poles_s,
        residues=residues,
        modal_energy=modal_energy,
        reconstruction_errors=reconstruction_errors,
        band_low_hz=band_low_hz,
        band_high_hz=band_high_hz,
        selected_orders=selected_orders,
        observable_count_per_mode=observable_count,
        observable_names=list(['ia', 'ib']),
    )
    results.deactivate_plotting()
    modes_table = results.mdl(ResultTypes.Modes)
    plot_table = results.mdl(ResultTypes.SDomainPlotHz)

    assert modes_table.data_c.shape == (2, 11)
    assert plot_table.data_c.shape == (2, 2)
    assert results.get_observable_names() == list(['ia', 'ib'])


def test_legacy_extract_matrix_pencil_poles_remains_callable() -> None:
    """
    Validate the legacy scalar wrapper over the refactored EMT core.

    :return: None.
    """
    time_step: float = 2.0e-4
    time_data: np.ndarray = np.arange(0.0, 0.5, time_step, dtype=np.float64)

    # The wrapper must still recover the dominant scalar mode because old demos
    # and notebooks may still call the historic API directly.
    scalar_signal: np.ndarray = (
        0.8 * np.real(np.exp((-1.5 + 1j * 2.0 * np.pi * 80.0) * time_data))
        + 0.2 * np.real(np.exp((-4.0 + 1j * 2.0 * np.pi * 160.0) * time_data))
    ).astype(np.float64)
    poles_s: np.ndarray = extract_matrix_pencil_poles(
        y_signal=scalar_signal,
        dt=time_step,
        max_modes=6,
        tol_deflation=1.0e-8,
    )
    frequencies_hz: np.ndarray = compute_unique_frequencies_hz(poles_s)

    assert poles_s.shape[0] >= 1
    assert has_frequency_near(frequencies_hz, 80.0, 5.0)
