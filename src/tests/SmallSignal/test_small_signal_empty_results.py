from __future__ import annotations

import numpy as np

from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_results import (
    SmallSignalStabilityRmsResults,
)
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.enumerations import ResultTypes


def build_empty_small_signal_results() -> SmallSignalStabilityRmsResults:
    """
    Build the historical empty result shell used before an RMS study finishes.

    :return: Empty RMS small-signal result object.
    """
    results: SmallSignalStabilityRmsResults = SmallSignalStabilityRmsResults(
        eigenvalues=np.empty(0),
        right_eigenvectors=np.empty(0),
        participation_factors=np.empty(0),
        damping_ratios=np.empty(0),
        conjugate_frequencies=np.empty(0),
        state_matrix=np.empty(0),
        stat_vars=list(),
        algebraic_vars=list(),
    )
    return results


def test_empty_small_signal_result_shell_has_matrix_dimensions() -> None:
    """
    Verify historical one-dimensional placeholders normalize to empty matrices.

    :return: None.
    """
    results: SmallSignalStabilityRmsResults = build_empty_small_signal_results()

    assert results.eigenvalues.shape == (0,)
    assert results.right_eigenvectors.shape == (0, 0)
    assert results.participation_factors.shape == (0, 0)
    assert results.state_matrix.shape == (0, 0)


def test_all_empty_small_signal_views_return_valid_tables() -> None:
    """
    Verify every available result view handles a study with no calculated modes.

    :return: None.
    """
    results: SmallSignalStabilityRmsResults = build_empty_small_signal_results()
    expected_shapes: dict[ResultTypes, tuple[int, int]] = dict({
        ResultTypes.StateMatrix: (0, 0),
        ResultTypes.RightEigenvectors: (0, 0),
        ResultTypes.Modes: (0, 4),
        ResultTypes.ParticipationFactors: (0, 0),
        ResultTypes.SDomainPlot: (0, 2),
        ResultTypes.SDomainPlotHz: (0, 2),
    })

    for result_type, expected_shape in expected_shapes.items():
        table: ResultsTable = results.mdl(result_type=result_type)
        assert table.data_c.shape == expected_shape


def test_single_imaginary_mode_domain_views_do_not_divide_by_zero() -> None:
    """
    Verify domain views handle modes whose real components are all zero.

    :return: None.
    """
    results: SmallSignalStabilityRmsResults = SmallSignalStabilityRmsResults(
        eigenvalues=np.array([1.0j], dtype=complex),
        right_eigenvectors=np.array([[1.0 + 0.0j]], dtype=complex),
        participation_factors=np.array([[1.0]], dtype=float),
        damping_ratios=np.array([0.0], dtype=float),
        conjugate_frequencies=np.array([1.0 / (2.0 * np.pi)], dtype=float),
        state_matrix=np.array([[0.0]], dtype=float),
        stat_vars=list(),
        algebraic_vars=list(),
    )

    with np.errstate(all="raise"):
        radians_table: ResultsTable = results.mdl(result_type=ResultTypes.SDomainPlot)
        hertz_table: ResultsTable = results.mdl(result_type=ResultTypes.SDomainPlotHz)

    assert radians_table.data_c.shape == (1, 2)
    assert hertz_table.data_c.shape == (1, 2)


def test_loading_consolidation_restores_empty_matrix_contract() -> None:
    """
    Verify disk-loaded legacy placeholders are normalized after parsing.

    :return: None.
    """
    results: SmallSignalStabilityRmsResults = build_empty_small_signal_results()
    results.right_eigenvectors = np.empty(0)
    results.participation_factors = np.empty(0)
    results.state_matrix = np.empty(0)

    results.consolidate_after_loading()

    assert results.right_eigenvectors.shape == (0, 0)
    assert results.participation_factors.shape == (0, 0)
    assert results.state_matrix.shape == (0, 0)


def test_sparse_results_expose_absent_state_matrix_as_empty_table() -> None:
    """
    Verify sparse modal results do not invent a state matrix or fail while displaying it.

    :return: None.
    """
    results: SmallSignalStabilityRmsResults = SmallSignalStabilityRmsResults(
        eigenvalues=np.array([-1.0 + 1.0j], dtype=complex),
        right_eigenvectors=np.array([[1.0 + 0.0j]], dtype=complex),
        participation_factors=np.array([[1.0]], dtype=float),
        damping_ratios=np.array([1.0 / np.sqrt(2.0)], dtype=float),
        conjugate_frequencies=np.array([1.0 / (2.0 * np.pi)], dtype=float),
        state_matrix=np.empty(0),
        stat_vars=list(),
        algebraic_vars=list(),
    )

    table: ResultsTable = results.mdl(result_type=ResultTypes.StateMatrix)

    assert table.data_c.shape == (0, 0)
    assert table.index_c.shape == (0,)
    assert table.cols_c.shape == (0,)
