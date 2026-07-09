"""
VeraGrid-integrated multidimensional HELM example with PV buses.

This module builds a local multidimensional holomorphic embedding map for a
MATPOWER case loaded through VeraGrid. The map uses one independent dimension
per non-slack bus, without region modes or alternative basis modes.

The implementation keeps PV buses as PV buses:

* active power at each PV bus is part of the per-bus active-power map,
* reactive power at each PV bus is represented by a multivariate series Q(s),
* the voltage magnitude constraint is enforced coefficient-by-coefficient.

The polynomial is built around a physical germ obtained from a VeraGrid Newton
power flow of the original case. A user-facing multiplier lambda is converted to
an internal deviation s = lambda - 1. Therefore, lambda = 1 reproduces the germ
case, lambda = 0 removes the mapped injection at that bus, and other values map
local injection changes around the germ.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Optional, Sequence

import numba as nb
import numpy as np
import scipy.sparse
import scipy.sparse.linalg


class MultiIndexTable:
    """
    Store and index the multivariate polynomial exponents.

    Parameters
    ----------
    dims:
        Number of independent embedding dimensions.
    max_order:
        Maximum total polynomial order.
    order_offsets:
        Prefix offsets such that rows of order ``k`` occupy
        ``[order_offsets[k], order_offsets[k + 1])``.
    alphas_array:
        Dense integer exponent matrix with shape ``(n_terms, dims)``.
    minus_e_position:
        Matrix whose row ``k`` and column ``d`` stores the coefficient position
        of ``alpha_k - e_d``. A value of ``-1`` means that subtraction is not
        possible because the corresponding exponent is zero.
    proper_sub_offsets:
        Prefix offsets into the flat convolution index arrays.
    proper_sub_left_flat:
        Flat left indices used in known convolution sums.
    proper_sub_right_flat:
        Flat right indices paired with ``proper_sub_left_flat``.
    """

    __slots__ = (
        "_dims",
        "_max_order",
        "_order_offsets",
        "_alphas_array",
        "_minus_e_position",
        "_proper_sub_offsets",
        "_proper_sub_left_flat",
        "_proper_sub_right_flat",
    )

    def __init__(
        self,
        dims: int,
        max_order: int,
        order_offsets: np.ndarray,
        alphas_array: np.ndarray,
        minus_e_position: np.ndarray,
        proper_sub_offsets: np.ndarray,
        proper_sub_left_flat: np.ndarray,
        proper_sub_right_flat: np.ndarray,
    ) -> None:
        self._dims: int = dims
        self._max_order: int = max_order
        self._order_offsets: np.ndarray = order_offsets
        self._alphas_array: np.ndarray = alphas_array
        self._minus_e_position: np.ndarray = minus_e_position
        self._proper_sub_offsets: np.ndarray = proper_sub_offsets
        self._proper_sub_left_flat: np.ndarray = proper_sub_left_flat
        self._proper_sub_right_flat: np.ndarray = proper_sub_right_flat

    def get_dims(self) -> int:
        """
        Get the number of embedding dimensions.

        Returns
        -------
        int
            Number of dimensions.
        """
        return self._dims

    def get_max_order(self) -> int:
        """
        Get the maximum total polynomial order.

        Returns
        -------
        int
            Maximum total order.
        """
        return self._max_order

    def get_order_offsets(self) -> np.ndarray:
        """
        Get the prefix offsets of each total-order block.

        Returns
        -------
        numpy.ndarray
            Prefix offsets with shape ``(max_order + 2,)``.
        """
        return self._order_offsets

    def get_alphas_array(self) -> np.ndarray:
        """
        Get the flat list of multi-indices as a dense integer array.

        Returns
        -------
        numpy.ndarray
            Integer exponent array with shape ``(n_terms, dims)``.
        """
        return self._alphas_array

    def get_terms_count(self) -> int:
        """
        Get the total number of coefficient rows.

        Returns
        -------
        int
            Number of coefficient rows.
        """
        return int(self._alphas_array.shape[0])

    def get_order_start(self, order_index: int) -> int:
        """
        Get the first coefficient position for one total order.

        Parameters
        ----------
        order_index:
            Total order.

        Returns
        -------
        int
            First coefficient position.
        """
        return int(self._order_offsets[order_index])

    def get_order_stop(self, order_index: int) -> int:
        """
        Get the exclusive stop coefficient position for one total order.

        Parameters
        ----------
        order_index:
            Total order.

        Returns
        -------
        int
            Exclusive stop coefficient position.
        """
        return int(self._order_offsets[order_index + 1])

    def get_minus_e_position(self) -> np.ndarray:
        """
        Get the ``alpha - e_d`` lookup matrix.

        Returns
        -------
        numpy.ndarray
            Lookup matrix with shape ``(n_terms, dims)``.
        """
        return self._minus_e_position

    def get_left_convolution_positions(self, position: int) -> np.ndarray:
        """
        Get left positions for known convolution sums.

        Parameters
        ----------
        position:
            Current coefficient position.

        Returns
        -------
        numpy.ndarray
            Left coefficient positions.
        """
        start: int = int(self._proper_sub_offsets[position])
        stop: int = int(self._proper_sub_offsets[position + 1])
        return self._proper_sub_left_flat[start:stop]

    def get_right_convolution_positions(self, position: int) -> np.ndarray:
        """
        Get right positions for known convolution sums.

        Parameters
        ----------
        position:
            Current coefficient position.

        Returns
        -------
        numpy.ndarray
            Right coefficient positions.
        """
        start: int = int(self._proper_sub_offsets[position])
        stop: int = int(self._proper_sub_offsets[position + 1])
        return self._proper_sub_right_flat[start:stop]


class MDHEMPVMap:
    """
    Multidimensional HELM coefficient map with PQ and PV buses.

    Parameters
    ----------
    ybus:
        Complete bus admittance matrix.
    slack:
        Slack bus indices in the full bus order.
    pq:
        PQ bus indices in the full bus order.
    pv:
        PV bus indices in the full bus order.
    no_slack:
        Non-slack bus indices in the full bus order.
    pv_local:
        PV bus indices in the non-slack local order.
    dimension_bus:
        Full bus index associated with each embedding dimension.
    dimension_local:
        Local non-slack index associated with each embedding dimension.
    dimension_is_pv:
        Boolean vector identifying dimensions associated with PV buses.
    slack_voltage:
        Fixed slack voltage vector.
    voltage_setpoint:
        Voltage magnitude target for every full bus index.
    scheduled_power_germ:
        Full complex bus injection at the physical germ.
    scheduled_basis:
        Per-dimension scheduled power basis in local non-slack order. PQ rows
        contain complex fixed-power-factor injections. PV rows contain active
        power only.
    table:
        Multi-index lookup table.
    u_coefficients:
        Voltage coefficients in local non-slack order.
    x_coefficients:
        Reciprocal-voltage coefficients in local non-slack order.
    q_coefficients:
        PV reactive-power coefficients in PV local order.
    bus_names:
        Bus names from VeraGrid.
    """

    __slots__ = (
        "_ybus",
        "_slack",
        "_pq",
        "_pv",
        "_no_slack",
        "_pv_local",
        "_dimension_bus",
        "_dimension_local",
        "_dimension_is_pv",
        "_slack_voltage",
        "_voltage_setpoint",
        "_scheduled_power_germ",
        "_scheduled_basis",
        "_table",
        "_u_coefficients",
        "_x_coefficients",
        "_q_coefficients",
        "_bus_names",
    )

    def __init__(
        self,
        ybus: scipy.sparse.csc_matrix,
        slack: np.ndarray,
        pq: np.ndarray,
        pv: np.ndarray,
        no_slack: np.ndarray,
        pv_local: np.ndarray,
        dimension_bus: np.ndarray,
        dimension_local: np.ndarray,
        dimension_is_pv: np.ndarray,
        slack_voltage: np.ndarray,
        voltage_setpoint: np.ndarray,
        scheduled_power_germ: np.ndarray,
        scheduled_basis: np.ndarray,
        table: MultiIndexTable,
        u_coefficients: np.ndarray,
        x_coefficients: np.ndarray,
        q_coefficients: np.ndarray,
        bus_names: np.ndarray,
    ) -> None:
        self._ybus: scipy.sparse.csc_matrix = ybus
        self._slack: np.ndarray = slack
        self._pq: np.ndarray = pq
        self._pv: np.ndarray = pv
        self._no_slack: np.ndarray = no_slack
        self._pv_local: np.ndarray = pv_local
        self._dimension_bus: np.ndarray = dimension_bus
        self._dimension_local: np.ndarray = dimension_local
        self._dimension_is_pv: np.ndarray = dimension_is_pv
        self._slack_voltage: np.ndarray = slack_voltage
        self._voltage_setpoint: np.ndarray = voltage_setpoint
        self._scheduled_power_germ: np.ndarray = scheduled_power_germ
        self._scheduled_basis: np.ndarray = scheduled_basis
        self._table: MultiIndexTable = table
        self._u_coefficients: np.ndarray = u_coefficients
        self._x_coefficients: np.ndarray = x_coefficients
        self._q_coefficients: np.ndarray = q_coefficients
        self._bus_names: np.ndarray = bus_names

    def get_dimensions_count(self) -> int:
        """
        Get the number of embedding dimensions.

        Returns
        -------
        int
            Number of dimensions.
        """
        return int(self._dimension_bus.size)

    def get_coefficients_count(self) -> int:
        """
        Get the number of multivariate coefficients per bus.

        Returns
        -------
        int
            Number of coefficients.
        """
        return int(self._u_coefficients.shape[0])

    def get_max_order(self) -> int:
        """
        Get the maximum total order.

        Returns
        -------
        int
            Maximum total order.
        """
        return self._table.get_max_order()

    def get_slack(self) -> np.ndarray:
        """
        Get the slack bus indices.

        Returns
        -------
        numpy.ndarray
            Slack bus indices.
        """
        return self._slack

    def get_pq(self) -> np.ndarray:
        """
        Get the PQ bus indices.

        Returns
        -------
        numpy.ndarray
            PQ bus indices.
        """
        return self._pq

    def get_pv(self) -> np.ndarray:
        """
        Get the PV bus indices.

        Returns
        -------
        numpy.ndarray
            PV bus indices.
        """
        return self._pv

    def get_no_slack(self) -> np.ndarray:
        """
        Get the non-slack bus indices.

        Returns
        -------
        numpy.ndarray
            Non-slack bus indices.
        """
        return self._no_slack

    def get_voltage_coefficients(self) -> np.ndarray:
        """
        Get the voltage coefficient matrix.

        Returns
        -------
        numpy.ndarray
            Coefficient matrix with shape ``(n_terms, n_no_slack)``.
        """
        return self._u_coefficients

    def get_reactive_power_coefficients(self) -> np.ndarray:
        """
        Get the PV reactive-power coefficient matrix.

        Returns
        -------
        numpy.ndarray
            Coefficient matrix with shape ``(n_terms, n_pv)``.
        """
        return self._q_coefficients

    def get_dimension_bus_indices(self) -> np.ndarray:
        """
        Get the full bus index associated with each coefficient dimension.

        Returns
        -------
        numpy.ndarray
            Full bus indices, zero-based.
        """
        return self._dimension_bus

    def get_bus_names(self) -> np.ndarray:
        """
        Get bus names.

        Returns
        -------
        numpy.ndarray
            Bus names.
        """
        return self._bus_names

    def evaluate_multipliers(self, multipliers: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Evaluate the map using per-bus injection multipliers.

        Parameters
        ----------
        multipliers:
            Vector with one multiplier per non-slack bus. ``1`` reproduces the
            physical germ. ``0`` removes the mapped injection of the bus.

        Returns
        -------
        tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]
            Voltage vector, scheduled bus power vector and PV reactive powers.
        """
        deviation: np.ndarray = np.asarray(multipliers, dtype=np.complex128) - np.ones(
            self.get_dimensions_count(), dtype=np.complex128
        )
        voltage: np.ndarray
        scheduled_power: np.ndarray
        pv_reactive_power: np.ndarray
        voltage, scheduled_power, pv_reactive_power = self.evaluate_deviation(deviation=deviation)
        return voltage, scheduled_power, pv_reactive_power

    def evaluate_deviation(self, deviation: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Evaluate the map using internal deviation variables.

        Parameters
        ----------
        deviation:
            Vector of internal embedding variables. It is normally calculated as
            ``multipliers - 1``.

        Returns
        -------
        tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]
            Voltage vector, scheduled bus power vector and PV reactive powers.
        """
        deviation_array: np.ndarray = np.asarray(deviation, dtype=np.complex128)
        expected_shape: tuple[int, ...] = (self.get_dimensions_count(),)
        if deviation_array.shape == expected_shape:
            # The online query path is dominated by monomial evaluation, so the
            # Python tuple-based multi-index list is replaced here by the dense
            # integer matrix precomputed in ``MultiIndexTable`` and consumed by
            # a compiled Numba kernel.
            weights: np.ndarray = calculate_monomial_weights(
                alphas=self._table.get_alphas_array(),
                values=deviation_array,
            )
            voltage: np.ndarray = np.zeros(self._ybus.shape[0], dtype=np.complex128)
            voltage[self._slack] = self._slack_voltage
            voltage[self._no_slack] = weights @ self._u_coefficients
            pv_reactive_power: np.ndarray = weights @ self._q_coefficients
            scheduled_power: np.ndarray = self.calculate_scheduled_power(
                deviation=deviation_array,
                pv_reactive_power=pv_reactive_power,
            )
        else:
            voltage = np.zeros(self._ybus.shape[0], dtype=np.complex128)
            scheduled_power = np.zeros(self._ybus.shape[0], dtype=np.complex128)
            pv_reactive_power = np.zeros(self._pv.size, dtype=np.float64)
        return voltage, scheduled_power, pv_reactive_power

    def calculate_scheduled_power(self, deviation: np.ndarray, pv_reactive_power: np.ndarray) -> np.ndarray:
        """
        Calculate the scheduled complex power represented by an evaluation point.

        Parameters
        ----------
        deviation:
            Internal deviation vector.
        pv_reactive_power:
            Evaluated PV reactive powers.

        Returns
        -------
        numpy.ndarray
            Scheduled complex power vector in per unit.
        """
        scheduled_power: np.ndarray = np.array(self._scheduled_power_germ, dtype=np.complex128)
        local_power: np.ndarray = scheduled_power[self._no_slack].copy()
        dimension_index: int
        for dimension_index in range(self.get_dimensions_count()):
            local_index: int = int(self._dimension_local[dimension_index])
            local_power[local_index] = local_power[local_index] + (
                deviation[dimension_index] * self._scheduled_basis[dimension_index, local_index]
            )
        scheduled_power[self._no_slack] = local_power
        pv_index: int
        for pv_index in range(self._pv.size):
            full_bus_index: int = int(self._pv[pv_index])
            scheduled_power[full_bus_index] = scheduled_power[full_bus_index].real + 1j * pv_reactive_power[pv_index]
        return scheduled_power


class MDHEMRunResult:
    """
    Result of one MDHEM map evaluation.

    Parameters
    ----------
    multipliers:
        Per-bus injection multipliers.
    voltage:
        Complex bus voltage vector.
    scheduled_power:
        Scheduled complex bus power vector in per unit.
    calculated_power:
        Calculated complex bus power vector in per unit.
    pv_reactive_power:
        PV reactive powers in per unit.
    mismatch_norm:
        Infinity norm of the power-flow mismatch.
    pv_voltage_error:
        Maximum absolute PV voltage-magnitude error.
    converged_like:
        True when the mismatch and PV voltage error are below tolerance.
    branch_from_power:
        Optional branch-from complex powers.
    branch_to_power:
        Optional branch-to complex powers.
    branch_loading:
        Optional branch loading vector.
    branch_losses:
        Optional branch losses vector.
    """

    __slots__ = (
        "multipliers",
        "voltage",
        "scheduled_power",
        "calculated_power",
        "pv_reactive_power",
        "mismatch_norm",
        "pv_voltage_error",
        "converged_like",
        "branch_from_power",
        "branch_to_power",
        "branch_loading",
        "branch_losses",
    )

    def __init__(
        self,
        multipliers: np.ndarray,
        voltage: np.ndarray,
        scheduled_power: np.ndarray,
        calculated_power: np.ndarray,
        pv_reactive_power: np.ndarray,
        mismatch_norm: float,
        pv_voltage_error: float,
        converged_like: bool,
        branch_from_power: Optional[np.ndarray],
        branch_to_power: Optional[np.ndarray],
        branch_loading: Optional[np.ndarray],
        branch_losses: Optional[np.ndarray],
    ) -> None:
        self.multipliers: np.ndarray = multipliers
        self.voltage: np.ndarray = voltage
        self.scheduled_power: np.ndarray = scheduled_power
        self.calculated_power: np.ndarray = calculated_power
        self.pv_reactive_power: np.ndarray = pv_reactive_power
        self.mismatch_norm: float = mismatch_norm
        self.pv_voltage_error: float = pv_voltage_error
        self.converged_like: bool = converged_like
        self.branch_from_power: Optional[np.ndarray] = branch_from_power
        self.branch_to_power: Optional[np.ndarray] = branch_to_power
        self.branch_loading: Optional[np.ndarray] = branch_loading
        self.branch_losses: Optional[np.ndarray] = branch_losses


class SparseLinearSolver:
    """
    Wrapper around a sparse factorization with an explicit solve method.

    Parameters
    ----------
    factorization:
        SciPy sparse LU factorization object.
    """

    __slots__ = ("_factorization",)

    def __init__(self, factorization: object) -> None:
        self._factorization: object = factorization

    def solve(self, rhs: np.ndarray) -> np.ndarray:
        """
        Solve the sparse linear system for one or many right-hand sides.

        Parameters
        ----------
        rhs:
            Right-hand-side vector or dense right-hand-side matrix.

        Returns
        -------
        numpy.ndarray
            Solution vector or dense solution matrix.
        """
        solution: np.ndarray = np.asarray(self._factorization.solve(rhs), dtype=np.float64)
        return solution


class VeraGridCaseData:
    """
    VeraGrid numerical data required by the MDHEM example.

    Parameters
    ----------
    grid:
        VeraGrid grid object.
    numerical_circuit:
        VeraGrid numerical circuit.
    admittance:
        VeraGrid admittance matrices object.
    base_power:
        Scheduled base power injections in per unit.
    germ_voltage:
        Physical-germ voltage vector from VeraGrid Newton power flow.
    germ_calculated_power:
        Complex power calculated at the germ voltage.
    slack:
        Slack bus indices.
    pq:
        PQ bus indices.
    pv:
        PV bus indices.
    no_slack:
        Non-slack bus indices.
    bus_names:
        VeraGrid bus names.
    voltage_setpoint:
        Voltage magnitudes used as PV targets.
    newton_error:
        VeraGrid Newton-Raphson error at the germ.
    """

    __slots__ = (
        "grid",
        "numerical_circuit",
        "admittance",
        "base_power",
        "germ_voltage",
        "germ_calculated_power",
        "slack",
        "pq",
        "pv",
        "no_slack",
        "bus_names",
        "voltage_setpoint",
        "newton_error",
    )

    def __init__(
        self,
        grid: object,
        numerical_circuit: object,
        admittance: object,
        base_power: np.ndarray,
        germ_voltage: np.ndarray,
        germ_calculated_power: np.ndarray,
        slack: np.ndarray,
        pq: np.ndarray,
        pv: np.ndarray,
        no_slack: np.ndarray,
        bus_names: np.ndarray,
        voltage_setpoint: np.ndarray,
        newton_error: float,
    ) -> None:
        self.grid: object = grid
        self.numerical_circuit: object = numerical_circuit
        self.admittance: object = admittance
        self.base_power: np.ndarray = base_power
        self.germ_voltage: np.ndarray = germ_voltage
        self.germ_calculated_power: np.ndarray = germ_calculated_power
        self.slack: np.ndarray = slack
        self.pq: np.ndarray = pq
        self.pv: np.ndarray = pv
        self.no_slack: np.ndarray = no_slack
        self.bus_names: np.ndarray = bus_names
        self.voltage_setpoint: np.ndarray = voltage_setpoint
        self.newton_error: float = newton_error


def create_binomial_table(max_n: int, max_k: int) -> np.ndarray:
    """
    Create a dense Pascal-triangle table used by the rank kernels.

    Parameters
    ----------
    max_n:
        Largest ``n`` needed in ``C(n, k)``.
    max_k:
        Largest ``k`` needed in ``C(n, k)``.

    Returns
    -------
    numpy.ndarray
        Dense ``int64`` binomial table.
    """
    binomial_table: np.ndarray = np.zeros((max_n + 1, max_k + 1), dtype=np.int64)
    n_index: int

    # The table is built once per multi-index structure so every later rank
    # lookup becomes a direct array access instead of a Python ``math.comb``
    # call inside the inner loops.
    for n_index in range(max_n + 1):
        upper_k: int = min(n_index, max_k)
        binomial_table[n_index, 0] = 1
        k_index: int
        for k_index in range(1, upper_k + 1):
            if k_index == n_index:
                binomial_table[n_index, k_index] = 1
            else:
                binomial_table[n_index, k_index] = (
                    binomial_table[n_index - 1, k_index - 1]
                    + binomial_table[n_index - 1, k_index]
                )

    return binomial_table


def format_byte_count(byte_count: int) -> str:
    """
    Format a byte count with binary prefixes.

    Parameters
    ----------
    byte_count:
        Raw byte count.

    Returns
    -------
    str
        Human-readable byte count.
    """
    units: tuple[str, ...] = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB")
    value: float = float(byte_count)
    unit_index: int = 0

    while value >= 1024.0 and unit_index < len(units) - 1:
        value = value / 1024.0
        unit_index = unit_index + 1

    return f"{value:.2f} {units[unit_index]}"


def get_physical_memory_bytes() -> Optional[int]:
    """
    Read the host physical memory size when the platform exposes it.

    Returns
    -------
    Optional[int]
        Physical memory in bytes, or ``None`` when unavailable.
    """
    try:
        page_size: int = int(os.sysconf("SC_PAGE_SIZE"))
        page_count: int = int(os.sysconf("SC_PHYS_PAGES"))
        if page_size > 0 and page_count > 0:
            return page_size * page_count
        else:
            return None
    except (ValueError, OSError, AttributeError):
        return None


def estimate_multi_index_table_bytes(total_terms: int, dims: int) -> int:
    """
    Estimate the minimum dense storage required by the multi-index table.

    Parameters
    ----------
    total_terms:
        Number of coefficient rows.
    dims:
        Number of embedding dimensions.

    Returns
    -------
    int
        Lower-bound byte estimate for the mandatory dense integer arrays.
    """
    alpha_bytes: int = total_terms * dims * np.dtype(np.int64).itemsize
    minus_e_bytes: int = total_terms * dims * np.dtype(np.int64).itemsize
    count_bytes: int = total_terms * np.dtype(np.int64).itemsize
    offset_bytes: int = (total_terms + 1) * np.dtype(np.int64).itemsize

    # This is intentionally a lower bound. If even the mandatory arrays do not
    # fit, the full table is already impossible before counting convolution
    # pair storage or any coefficient tensors built on top of it.
    return alpha_bytes + minus_e_bytes + count_bytes + offset_bytes


def should_use_parallel_table_build(total_terms: int, dims: int) -> bool:
    """
    Decide whether the multi-index table build is large enough for threading.

    Parameters
    ----------
    total_terms:
        Number of coefficient rows.
    dims:
        Number of embedding dimensions.

    Returns
    -------
    bool
        ``True`` when the table build should use Numba parallel kernels.
    """
    operation_scale: int = total_terms * max(dims, 1)

    # ponytail: thread startup is pure overhead on small cases like IEEE14, so
    # only switch to the parallel kernels when the dense table work is clearly
    # large enough to amortize it.
    if operation_scale >= 200_000:
        return True
    else:
        return False


def should_use_parallel_monomial_weights(term_count: int, dimension_count: int) -> bool:
    """
    Decide whether monomial evaluation is large enough for threaded execution.

    Parameters
    ----------
    term_count:
        Number of polynomial terms.
    dimension_count:
        Number of embedding dimensions.

    Returns
    -------
    bool
        ``True`` when the parallel monomial kernel should be used.
    """
    operation_scale: int = term_count * max(dimension_count, 1)

    # The online query path is latency-sensitive. Small artifacts should stay
    # on one thread, while large ones benefit from splitting the term loop.
    if operation_scale >= 100_000:
        return True
    else:
        return False


def should_use_parallel_convolution(pair_count: int, vector_width: int) -> bool:
    """
    Decide whether one dense convolution accumulation should use threading.

    Parameters
    ----------
    pair_count:
        Number of beta/gamma pairs in the convolution sum.
    vector_width:
        Number of buses or PV buses updated by the sum.

    Returns
    -------
    bool
        ``True`` when the parallel convolution kernel should be used.
    """
    operation_scale: int = pair_count * max(vector_width, 1)

    # The HELM training loop calls these kernels many times. A low threshold
    # would slow the small recurring calls, so the gate is deliberately higher.
    if operation_scale >= 20_000:
        return True
    else:
        return False


def determine_rhs_block_columns(unknown_count: int, target_block_bytes: int) -> int:
    """
    Choose a dense multi-RHS block width for the repeated sparse solves.

    Parameters
    ----------
    unknown_count:
        Number of rows in the constant MDHEM linear system.
    target_block_bytes:
        Approximate memory budget for one dense RHS block and its solution.

    Returns
    -------
    int
        Number of RHS columns to solve together.
    """
    bytes_per_column: int

    # Each column exists twice during the block solve: once in the RHS matrix
    # and once in the solution matrix. Both are dense float64 arrays.
    if unknown_count > 0:
        bytes_per_column = 16 * unknown_count
        return max(1, target_block_bytes // bytes_per_column)
    else:
        return 1


@nb.njit(cache=True)
def fill_compositions_array(total: int, dims: int, output: np.ndarray, row_start: int) -> int:
    """
    Fill one dense alpha-array block with all compositions of one total order.

    Parameters
    ----------
    total:
        Total order to distribute.
    dims:
        Number of dimensions.
    output:
        Dense alpha matrix receiving the filled rows.
    row_start:
        First row of the block.

    Returns
    -------
    int
        First row after the filled block.
    """
    row_index: int = row_start

    if dims == 1:
        output[row_index, 0] = total
        row_index = row_index + 1
    else:
        separator_count: int = dims - 1
        separator_slots: int = total + dims - 1
        separators: np.ndarray = np.arange(separator_count, dtype=np.int64)

        # The stars-and-bars representation generates the same lexicographic
        # order as the old composition builder, but it writes
        # directly into the preallocated dense alpha array.
        while True:
            previous_separator: int = -1
            separator_index: int
            for separator_index in range(separator_count):
                current_separator: int = int(separators[separator_index])
                output[row_index, separator_index] = current_separator - previous_separator - 1
                previous_separator = current_separator
            output[row_index, dims - 1] = separator_slots - previous_separator - 1
            row_index = row_index + 1

            separator_index = separator_count - 1
            while separator_index >= 0:
                max_value: int = separator_slots - separator_count + separator_index
                if separators[separator_index] < max_value:
                    separators[separator_index] = separators[separator_index] + 1
                    next_index: int = separator_index + 1
                    while next_index < separator_count:
                        separators[next_index] = separators[next_index - 1] + 1
                        next_index = next_index + 1
                    break
                separator_index = separator_index - 1

            if separator_index < 0:
                break

    return row_index


@nb.njit(cache=True)
def compute_alpha_rank_numba(alpha: np.ndarray, binomial_table: np.ndarray) -> int:
    """
    Compute the lexicographic rank of one composition inside its order block.

    Parameters
    ----------
    alpha:
        Dense multi-index row.
    binomial_table:
        Dense lookup table for binomial coefficients.

    Returns
    -------
    int
        Zero-based rank in the fixed-total-order block.
    """
    remaining_total: int = 0
    rank: int = 0
    dimension_count: int = int(alpha.size)
    dimension_index: int

    # The rank is the number of compositions that would appear before the
    # current one in the stars-and-bars order generated above.
    for dimension_index in range(dimension_count):
        remaining_total = remaining_total + int(alpha[dimension_index])

    for dimension_index in range(dimension_count - 1):
        current_value: int = int(alpha[dimension_index])
        suffix_dims: int = dimension_count - dimension_index - 2
        candidate_value: int
        for candidate_value in range(current_value):
            rank = rank + int(
                binomial_table[remaining_total - candidate_value + suffix_dims, suffix_dims]
            )
        remaining_total = remaining_total - current_value

    return rank


@nb.njit(cache=True)
def compute_alpha_position_numba(
    alpha: np.ndarray,
    order_offsets: np.ndarray,
    binomial_table: np.ndarray,
) -> int:
    """
    Compute the global coefficient position of one dense multi-index.

    Parameters
    ----------
    alpha:
        Dense multi-index row.
    order_offsets:
        Prefix offsets of the total-order blocks.
    binomial_table:
        Dense lookup table for binomial coefficients.

    Returns
    -------
    int
        Global coefficient position.
    """
    total_order: int = 0
    dimension_index: int

    for dimension_index in range(alpha.size):
        total_order = total_order + int(alpha[dimension_index])

    return int(order_offsets[total_order] + compute_alpha_rank_numba(alpha, binomial_table))


@nb.njit(cache=True)
def fill_minus_e_position_numba(
    alphas_array: np.ndarray,
    order_offsets: np.ndarray,
    binomial_table: np.ndarray,
    minus_e_position: np.ndarray,
) -> None:
    """
    Fill the ``alpha - e_d`` lookup matrix in compiled code.

    Parameters
    ----------
    alphas_array:
        Dense exponent matrix.
    order_offsets:
        Prefix offsets of the total-order blocks.
    binomial_table:
        Dense lookup table for binomial coefficients.
    minus_e_position:
        Output lookup matrix.

    Returns
    -------
    None
        The output array is filled in place.
    """
    term_count: int = int(alphas_array.shape[0])
    dimension_count: int = int(alphas_array.shape[1])
    position: int

    # Each ``alpha - e_d`` position can be ranked directly from the current row
    # without materializing a copied temporary vector for every dimension.
    for position in range(term_count):
        total_order: int = 0
        dimension_index: int
        for dimension_index in range(dimension_count):
            total_order = total_order + int(alphas_array[position, dimension_index])

        for dimension_index in range(dimension_count):
            exponent: int = int(alphas_array[position, dimension_index])
            if exponent > 0:
                shifted_total: int = total_order - 1
                remaining_total: int = shifted_total
                rank: int = 0
                alpha_index: int
                for alpha_index in range(dimension_count - 1):
                    current_value: int = int(alphas_array[position, alpha_index])
                    if alpha_index == dimension_index:
                        current_value = current_value - 1
                    else:
                        current_value = current_value
                    suffix_dims: int = dimension_count - alpha_index - 2
                    candidate_value: int
                    for candidate_value in range(current_value):
                        rank = rank + int(
                            binomial_table[remaining_total - candidate_value + suffix_dims, suffix_dims]
                        )
                    remaining_total = remaining_total - current_value
                minus_e_position[position, dimension_index] = int(order_offsets[shifted_total] + rank)
            else:
                minus_e_position[position, dimension_index] = -1


@nb.njit(cache=True, parallel=True)
def fill_minus_e_position_parallel_numba(
    alphas_array: np.ndarray,
    order_offsets: np.ndarray,
    binomial_table: np.ndarray,
    minus_e_position: np.ndarray,
) -> None:
    """
    Fill the ``alpha - e_d`` lookup matrix with parallel row updates.

    Parameters
    ----------
    alphas_array:
        Dense exponent matrix.
    order_offsets:
        Prefix offsets of the total-order blocks.
    binomial_table:
        Dense lookup table for binomial coefficients.
    minus_e_position:
        Output lookup matrix.

    Returns
    -------
    None
        The output array is filled in place.
    """
    term_count: int = int(alphas_array.shape[0])
    dimension_count: int = int(alphas_array.shape[1])
    position: int

    # Each row writes to a disjoint slice of ``minus_e_position``, so the
    # outer loop is embarrassingly parallel across coefficient rows.
    for position in nb.prange(term_count):
        total_order: int = 0
        dimension_index: int
        for dimension_index in range(dimension_count):
            total_order = total_order + int(alphas_array[position, dimension_index])

        for dimension_index in range(dimension_count):
            exponent: int = int(alphas_array[position, dimension_index])
            if exponent > 0:
                shifted_total: int = total_order - 1
                remaining_total: int = shifted_total
                rank: int = 0
                alpha_index: int
                for alpha_index in range(dimension_count - 1):
                    current_value: int = int(alphas_array[position, alpha_index])
                    if alpha_index == dimension_index:
                        current_value = current_value - 1
                    else:
                        current_value = current_value
                    suffix_dims: int = dimension_count - alpha_index - 2
                    candidate_value: int
                    for candidate_value in range(current_value):
                        rank = rank + int(
                            binomial_table[remaining_total - candidate_value + suffix_dims, suffix_dims]
                        )
                    remaining_total = remaining_total - current_value
                minus_e_position[position, dimension_index] = int(order_offsets[shifted_total] + rank)
            else:
                minus_e_position[position, dimension_index] = -1


@nb.njit(cache=True)
def count_proper_sub_counts_numba(alphas_array: np.ndarray) -> np.ndarray:
    """
    Count non-trivial ``beta + gamma = alpha`` pairs for every coefficient row.

    Parameters
    ----------
    alphas_array:
        Dense exponent matrix.

    Returns
    -------
    numpy.ndarray
        Flat counts per coefficient row.
    """
    term_count: int = int(alphas_array.shape[0])
    dimension_count: int = int(alphas_array.shape[1])
    proper_sub_counts: np.ndarray = np.zeros(term_count, dtype=np.int64)
    position: int

    # The mixed-radix product gives the number of ways to split each exponent
    # coordinate independently. Removing the all-zero and all-alpha splits
    # leaves the non-trivial convolution pairs.
    for position in range(term_count):
        pair_count: int = 1
        has_nonzero: bool = False
        dimension_index: int
        for dimension_index in range(dimension_count):
            exponent: int = int(alphas_array[position, dimension_index])
            if exponent > 0:
                has_nonzero = True
                pair_count = pair_count * (exponent + 1)
            else:
                pair_count = pair_count * 1

        if has_nonzero and pair_count >= 2:
            proper_sub_counts[position] = pair_count - 2
        else:
            proper_sub_counts[position] = 0

    return proper_sub_counts


@nb.njit(cache=True, parallel=True)
def count_proper_sub_counts_parallel_numba(alphas_array: np.ndarray) -> np.ndarray:
    """
    Count non-trivial ``beta + gamma = alpha`` pairs with parallel row updates.

    Parameters
    ----------
    alphas_array:
        Dense exponent matrix.

    Returns
    -------
    numpy.ndarray
        Flat counts per coefficient row.
    """
    term_count: int = int(alphas_array.shape[0])
    dimension_count: int = int(alphas_array.shape[1])
    proper_sub_counts: np.ndarray = np.zeros(term_count, dtype=np.int64)
    position: int

    # Every row count is independent, which makes this pass a clean threading
    # target once the table grows beyond the small test cases.
    for position in nb.prange(term_count):
        pair_count: int = 1
        has_nonzero: bool = False
        dimension_index: int
        for dimension_index in range(dimension_count):
            exponent: int = int(alphas_array[position, dimension_index])
            if exponent > 0:
                has_nonzero = True
                pair_count = pair_count * (exponent + 1)
            else:
                pair_count = pair_count * 1

        if has_nonzero and pair_count >= 2:
            proper_sub_counts[position] = pair_count - 2
        else:
            proper_sub_counts[position] = 0

    return proper_sub_counts


@nb.njit(cache=True)
def fill_proper_sub_arrays_numba(
    alphas_array: np.ndarray,
    order_offsets: np.ndarray,
    binomial_table: np.ndarray,
    proper_sub_offsets: np.ndarray,
    left_positions: np.ndarray,
    right_positions: np.ndarray,
) -> None:
    """
    Fill the flat beta/gamma convolution lookup arrays in compiled code.

    Parameters
    ----------
    alphas_array:
        Dense exponent matrix.
    order_offsets:
        Prefix offsets of the total-order blocks.
    binomial_table:
        Dense lookup table for binomial coefficients.
    proper_sub_offsets:
        Prefix offsets into the flat outputs.
    left_positions:
        Flat output array receiving left positions.
    right_positions:
        Flat output array receiving right positions.

    Returns
    -------
    None
        The output arrays are filled in place.
    """
    term_count: int = int(alphas_array.shape[0])
    dimension_count: int = int(alphas_array.shape[1])
    position: int

    # The same mixed-radix counter used by the Python version is kept, but the
    # heavy enumeration and ranking now stay inside one compiled kernel.
    for position in range(term_count):
        output_position: int = int(proper_sub_offsets[position])
        combination_count: int = 1
        dimension_index: int
        for dimension_index in range(dimension_count):
            combination_count = combination_count * (int(alphas_array[position, dimension_index]) + 1)

        beta_values: np.ndarray = np.zeros(dimension_count, dtype=np.int64)
        gamma_values: np.ndarray = np.zeros(dimension_count, dtype=np.int64)
        radix_sizes: np.ndarray = np.zeros(dimension_count, dtype=np.int64)
        for dimension_index in range(dimension_count):
            radix_sizes[dimension_index] = int(alphas_array[position, dimension_index]) + 1

        combination_index: int
        for combination_index in range(combination_count):
            remainder: int = combination_index
            any_beta: bool = False
            all_equal: bool = True
            reverse_index: int

            for reverse_index in range(dimension_count - 1, -1, -1):
                radix: int = int(radix_sizes[reverse_index])
                digit: int = remainder % radix
                remainder = remainder // radix
                beta_values[reverse_index] = digit
                gamma_values[reverse_index] = int(alphas_array[position, reverse_index]) - digit
                if digit != 0:
                    any_beta = True
                else:
                    any_beta = any_beta
                if digit != int(alphas_array[position, reverse_index]):
                    all_equal = False
                else:
                    all_equal = all_equal

            if any_beta:
                if all_equal:
                    pass
                else:
                    left_positions[output_position] = compute_alpha_position_numba(
                        alpha=beta_values,
                        order_offsets=order_offsets,
                        binomial_table=binomial_table,
                    )
                    right_positions[output_position] = compute_alpha_position_numba(
                        alpha=gamma_values,
                        order_offsets=order_offsets,
                        binomial_table=binomial_table,
                    )
                    output_position = output_position + 1
            else:
                pass


@nb.njit(cache=True, parallel=True)
def fill_proper_sub_arrays_parallel_numba(
    alphas_array: np.ndarray,
    order_offsets: np.ndarray,
    binomial_table: np.ndarray,
    proper_sub_offsets: np.ndarray,
    left_positions: np.ndarray,
    right_positions: np.ndarray,
) -> None:
    """
    Fill the flat beta/gamma convolution arrays with parallel row updates.

    Parameters
    ----------
    alphas_array:
        Dense exponent matrix.
    order_offsets:
        Prefix offsets of the total-order blocks.
    binomial_table:
        Dense lookup table for binomial coefficients.
    proper_sub_offsets:
        Prefix offsets into the flat outputs.
    left_positions:
        Flat output array receiving left positions.
    right_positions:
        Flat output array receiving right positions.

    Returns
    -------
    None
        The output arrays are filled in place.
    """
    term_count: int = int(alphas_array.shape[0])
    dimension_count: int = int(alphas_array.shape[1])
    position: int

    # Each coefficient row owns a disjoint slice in the flat output arrays, so
    # the outer loop can be threaded without synchronization.
    for position in nb.prange(term_count):
        output_position: int = int(proper_sub_offsets[position])
        combination_count: int = 1
        dimension_index: int
        for dimension_index in range(dimension_count):
            combination_count = combination_count * (int(alphas_array[position, dimension_index]) + 1)

        beta_values: np.ndarray = np.zeros(dimension_count, dtype=np.int64)
        gamma_values: np.ndarray = np.zeros(dimension_count, dtype=np.int64)
        radix_sizes: np.ndarray = np.zeros(dimension_count, dtype=np.int64)
        for dimension_index in range(dimension_count):
            radix_sizes[dimension_index] = int(alphas_array[position, dimension_index]) + 1

        combination_index: int
        for combination_index in range(combination_count):
            remainder: int = combination_index
            any_beta: bool = False
            all_equal: bool = True
            reverse_index: int

            for reverse_index in range(dimension_count - 1, -1, -1):
                radix: int = int(radix_sizes[reverse_index])
                digit: int = remainder % radix
                remainder = remainder // radix
                beta_values[reverse_index] = digit
                gamma_values[reverse_index] = int(alphas_array[position, reverse_index]) - digit
                if digit != 0:
                    any_beta = True
                else:
                    any_beta = any_beta
                if digit != int(alphas_array[position, reverse_index]):
                    all_equal = False
                else:
                    all_equal = all_equal

            if any_beta:
                if all_equal:
                    pass
                else:
                    left_positions[output_position] = compute_alpha_position_numba(
                        alpha=beta_values,
                        order_offsets=order_offsets,
                        binomial_table=binomial_table,
                    )
                    right_positions[output_position] = compute_alpha_position_numba(
                        alpha=gamma_values,
                        order_offsets=order_offsets,
                        binomial_table=binomial_table,
                    )
                    output_position = output_position + 1
            else:
                pass


def compute_alpha_rank(alpha: np.ndarray) -> int:
    """
    Compute the lexicographic rank of one composition within its total-order block.

    Parameters
    ----------
    alpha:
        Dense multi-index row.

    Returns
    -------
    int
        Zero-based rank within the block of fixed total order.
    """
    alpha_array: np.ndarray = np.asarray(alpha, dtype=np.int64)
    total_order: int = int(np.sum(alpha_array))
    dimension_count: int = int(alpha_array.size)
    binomial_table: np.ndarray = create_binomial_table(
        max_n=total_order + dimension_count,
        max_k=dimension_count,
    )

    # The public wrapper keeps a simple Python API while delegating the actual
    # combinatorial counting to the compiled kernel used by the artifact build.
    return int(compute_alpha_rank_numba(alpha=alpha_array, binomial_table=binomial_table))


def compute_alpha_position(alpha: np.ndarray, order_offsets: np.ndarray) -> int:
    """
    Compute the global row position of one dense multi-index.

    Parameters
    ----------
    alpha:
        Dense multi-index row.
    order_offsets:
        Prefix offsets of the total-order blocks.

    Returns
    -------
    int
        Global coefficient row position.
    """
    alpha_array: np.ndarray = np.asarray(alpha, dtype=np.int64)
    order_offsets_array: np.ndarray = np.asarray(order_offsets, dtype=np.int64)
    total_order: int = int(np.sum(alpha_array))
    dimension_count: int = int(alpha_array.size)
    binomial_table: np.ndarray = create_binomial_table(
        max_n=total_order + dimension_count,
        max_k=dimension_count,
    )
    return int(
        compute_alpha_position_numba(
            alpha=alpha_array,
            order_offsets=order_offsets_array,
            binomial_table=binomial_table,
        )
    )


def create_multi_index_table(dims: int, max_order: int) -> MultiIndexTable:
    """
    Create the multi-index table needed by the MDHEM coefficient recurrence.

    Parameters
    ----------
    dims:
        Number of embedding dimensions.
    max_order:
        Maximum total order.

    Returns
    -------
    MultiIndexTable
        Multi-index table and convolution lookup structure.
    """
    order_offsets: np.ndarray = np.zeros(max_order + 2, dtype=np.int64)
    total_terms: int
    if dims > 0 and max_order >= 0:
        for order_index in range(max_order + 1):
            order_count: int = math.comb(order_index + dims - 1, dims - 1)
            order_offsets[order_index + 1] = order_offsets[order_index] + order_count
    else:
        order_offsets[1] = 1

    total_terms = int(order_offsets[max_order + 1])
    binomial_table: np.ndarray = create_binomial_table(
        max_n=max_order + dims,
        max_k=dims,
    )
    alphas_array: np.ndarray = np.zeros((total_terms, dims), dtype=np.int64)
    order_index: int

    if dims > 0 and max_order >= 0:
        for order_index in range(max_order + 1):
            next_row: int = fill_compositions_array(
                total=order_index,
                dims=dims,
                output=alphas_array,
                row_start=int(order_offsets[order_index]),
            )
            if next_row == int(order_offsets[order_index + 1]):
                pass
            else:
                raise RuntimeError("Composition fill count mismatch")
    else:
        pass

    minus_e_position: np.ndarray = -np.ones((total_terms, dims), dtype=np.int64)
    use_parallel_table_build: bool = should_use_parallel_table_build(total_terms=total_terms, dims=dims)

    if use_parallel_table_build:
        fill_minus_e_position_parallel_numba(
            alphas_array=alphas_array,
            order_offsets=order_offsets,
            binomial_table=binomial_table,
            minus_e_position=minus_e_position,
        )
        proper_sub_counts: np.ndarray = count_proper_sub_counts_parallel_numba(alphas_array=alphas_array)
    else:
        fill_minus_e_position_numba(
            alphas_array=alphas_array,
            order_offsets=order_offsets,
            binomial_table=binomial_table,
            minus_e_position=minus_e_position,
        )
        proper_sub_counts = count_proper_sub_counts_numba(alphas_array=alphas_array)

    proper_sub_offsets: np.ndarray = np.zeros(total_terms + 1, dtype=np.int64)
    proper_sub_offsets[1:] = np.cumsum(proper_sub_counts)
    proper_sub_left_flat: np.ndarray = np.zeros(int(proper_sub_offsets[-1]), dtype=np.int64)
    proper_sub_right_flat: np.ndarray = np.zeros(int(proper_sub_offsets[-1]), dtype=np.int64)
    if use_parallel_table_build:
        fill_proper_sub_arrays_parallel_numba(
            alphas_array=alphas_array,
            order_offsets=order_offsets,
            binomial_table=binomial_table,
            proper_sub_offsets=proper_sub_offsets,
            left_positions=proper_sub_left_flat,
            right_positions=proper_sub_right_flat,
        )
    else:
        fill_proper_sub_arrays_numba(
            alphas_array=alphas_array,
            order_offsets=order_offsets,
            binomial_table=binomial_table,
            proper_sub_offsets=proper_sub_offsets,
            left_positions=proper_sub_left_flat,
            right_positions=proper_sub_right_flat,
        )

    return MultiIndexTable(
        dims=dims,
        max_order=max_order,
        order_offsets=order_offsets,
        alphas_array=alphas_array,
        minus_e_position=minus_e_position,
        proper_sub_offsets=proper_sub_offsets,
        proper_sub_left_flat=proper_sub_left_flat,
        proper_sub_right_flat=proper_sub_right_flat,
    )


@nb.njit(cache=True)
def calculate_monomial_weights_numba(alphas_array: np.ndarray, values: np.ndarray) -> np.ndarray:
    """
    Evaluate all monomials of the multivariate series at one query point.

    Parameters
    ----------
    alphas_array:
        Dense exponent matrix.
    values:
        Complex evaluation point.

    Returns
    -------
    numpy.ndarray
        Complex monomial weights.
    """
    term_count: int = alphas_array.shape[0]
    dimension_count: int = alphas_array.shape[1]
    weights: np.ndarray = np.ones(term_count, dtype=np.complex128)
    term_index: int

    # Each row in ``alphas_array`` describes one monomial. The compiled kernel
    # walks all exponents explicitly so query evaluation avoids Python loops.
    for term_index in range(term_count):
        weight_value: complex = complex(1.0, 0.0)
        dimension_index: int
        for dimension_index in range(dimension_count):
            exponent: int = int(alphas_array[term_index, dimension_index])
            power_index: int
            for power_index in range(exponent):
                weight_value = weight_value * values[dimension_index]
        weights[term_index] = weight_value

    return weights


@nb.njit(cache=True, parallel=True)
def calculate_monomial_weights_parallel_numba(alphas_array: np.ndarray, values: np.ndarray) -> np.ndarray:
    """
    Evaluate all monomials with threaded term-wise updates.

    Parameters
    ----------
    alphas_array:
        Dense exponent matrix.
    values:
        Complex evaluation point.

    Returns
    -------
    numpy.ndarray
        Complex monomial weights.
    """
    term_count: int = alphas_array.shape[0]
    dimension_count: int = alphas_array.shape[1]
    weights: np.ndarray = np.ones(term_count, dtype=np.complex128)
    term_index: int

    # Each monomial row is independent, so the outer loop can be distributed
    # across threads for large artifacts without changing the recurrence logic.
    for term_index in nb.prange(term_count):
        weight_value: complex = complex(1.0, 0.0)
        dimension_index: int
        for dimension_index in range(dimension_count):
            exponent: int = int(alphas_array[term_index, dimension_index])
            power_index: int
            for power_index in range(exponent):
                weight_value = weight_value * values[dimension_index]
        weights[term_index] = weight_value

    return weights


def calculate_monomial_weights(alphas: np.ndarray, values: np.ndarray) -> np.ndarray:
    """
    Calculate monomial weights for a multivariate polynomial evaluation.

    Parameters
    ----------
    alphas:
        Dense integer exponent matrix of the polynomial terms.
    values:
        Evaluation point.

    Returns
    -------
    numpy.ndarray
        Complex monomial weights.
    """
    alpha_array: np.ndarray = np.asarray(alphas, dtype=np.int64)
    value_array: np.ndarray = np.asarray(values, dtype=np.complex128)

    # The conversion to dense NumPy arrays is kept in Python because the table
    # construction phase is object-heavy, but the inner numerical work is
    # delegated to the compiled kernel above.
    if should_use_parallel_monomial_weights(
        term_count=int(alpha_array.shape[0]),
        dimension_count=int(alpha_array.shape[1]),
    ):
        return calculate_monomial_weights_parallel_numba(alphas_array=alpha_array, values=value_array)
    else:
        return calculate_monomial_weights_numba(alphas_array=alpha_array, values=value_array)


def count_coefficients(dims: int, max_order: int) -> int:
    """
    Count multivariate coefficients up to total order ``max_order``.

    Parameters
    ----------
    dims:
        Number of dimensions.
    max_order:
        Maximum total order.

    Returns
    -------
    int
        Number of coefficients, equal to ``C(max_order + dims, dims)``.
    """
    coefficient_total: int
    if dims >= 0 and max_order >= 0:
        coefficient_total = math.comb(max_order + dims, dims)
    else:
        coefficient_total = 0
    return coefficient_total


def create_full_to_local_lookup(nbus: int, no_slack: np.ndarray) -> np.ndarray:
    """
    Create a full-bus to local non-slack lookup vector.

    Parameters
    ----------
    nbus:
        Number of buses.
    no_slack:
        Non-slack bus indices.

    Returns
    -------
    numpy.ndarray
        Lookup vector. Slack or absent buses have value ``-1``.
    """
    # This helper is called repeatedly while building the artifact, so even
    # this small indexing loop is compiled to remove Python overhead.
    return create_full_to_local_lookup_numba(nbus=nbus, no_slack=no_slack)


@nb.njit(cache=True)
def create_full_to_local_lookup_numba(nbus: int, no_slack: np.ndarray) -> np.ndarray:
    """
    Build the full-bus to local-bus lookup with compiled loops.

    Parameters
    ----------
    nbus:
        Number of buses.
    no_slack:
        Non-slack bus indices.

    Returns
    -------
    numpy.ndarray
        Lookup vector.
    """
    full_to_local: np.ndarray = -np.ones(nbus, dtype=np.int64)
    local_index: int
    for local_index in range(no_slack.size):
        full_to_local[int(no_slack[local_index])] = local_index
    return full_to_local


def create_local_pv_lookup(no_slack: np.ndarray, pv: np.ndarray) -> np.ndarray:
    """
    Create local non-slack PV positions.

    Parameters
    ----------
    no_slack:
        Non-slack full bus indices.
    pv:
        PV full bus indices.

    Returns
    -------
    numpy.ndarray
        PV positions in the local non-slack order.
    """
    full_to_local: np.ndarray = create_full_to_local_lookup(nbus=int(np.max(no_slack)) + 1, no_slack=no_slack)

    # The lookup stage itself is simple but repeated often enough during HELM
    # preparation that compiling it is still worthwhile.
    return create_local_pv_lookup_numba(full_to_local=full_to_local, pv=pv)


@nb.njit(cache=True)
def create_local_pv_lookup_numba(full_to_local: np.ndarray, pv: np.ndarray) -> np.ndarray:
    """
    Translate PV full indices into local non-slack indices.

    Parameters
    ----------
    full_to_local:
        Full-bus to local-bus lookup.
    pv:
        PV full bus indices.

    Returns
    -------
    numpy.ndarray
        PV positions in local non-slack order.
    """
    pv_local: np.ndarray = np.zeros(pv.size, dtype=np.int64)
    pv_index: int
    for pv_index in range(pv.size):
        full_bus: int = int(pv[pv_index])
        if full_bus < full_to_local.size:
            pv_local[pv_index] = full_to_local[full_bus]
        else:
            pv_local[pv_index] = -1
    return pv_local


def create_per_bus_basis(
    base_power: np.ndarray,
    germ_power: np.ndarray,
    no_slack: np.ndarray,
    pv: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Create one embedding dimension per non-slack bus.

    PQ buses receive their complex base injection as fixed-power-factor basis.
    PV buses receive only their active-power basis because reactive power is an
    unknown PV-control series.

    Parameters
    ----------
    base_power:
        Scheduled base complex power from VeraGrid.
    germ_power:
        Calculated physical-germ complex power.
    no_slack:
        Non-slack full bus indices.
    pv:
        PV full bus indices.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray]
        Basis matrix, dimension bus indices, dimension local indices and PV
        dimension flags.
    """
    n_dimensions: int = no_slack.size
    n_no_slack: int = no_slack.size
    basis: np.ndarray = np.zeros((n_dimensions, n_no_slack), dtype=np.complex128)
    dimension_bus: np.ndarray = np.zeros(n_dimensions, dtype=np.int64)
    dimension_local: np.ndarray = np.zeros(n_dimensions, dtype=np.int64)
    dimension_is_pv: np.ndarray = np.zeros(n_dimensions, dtype=np.bool_)
    local_index: int
    for local_index in range(n_no_slack):
        full_bus: int = int(no_slack[local_index])
        dimension_bus[local_index] = full_bus
        dimension_local[local_index] = local_index
        is_pv: bool = bool(np.any(pv == full_bus))
        dimension_is_pv[local_index] = is_pv
        if is_pv:
            basis[local_index, local_index] = germ_power[full_bus].real
        else:
            basis[local_index, local_index] = base_power[full_bus]
    return basis, dimension_bus, dimension_local, dimension_is_pv


@nb.njit(cache=True)
def calculate_rhs_power_numba(
    minus_e_row: np.ndarray,
    basis_conjugate: np.ndarray,
    x_coefficients: np.ndarray,
    pv_local: np.ndarray,
    qx_known: np.ndarray,
) -> np.ndarray:
    """
    Assemble the complex power-balance RHS contribution for one coefficient.

    Parameters
    ----------
    minus_e_row:
        One row of the ``alpha - e_d`` lookup table.
    basis_conjugate:
        Conjugated scheduled-power basis.
    x_coefficients:
        Reciprocal-voltage coefficients.
    pv_local:
        PV positions in local non-slack order.
    qx_known:
        Known ``Q * X`` convolution term for the PV buses.

    Returns
    -------
    numpy.ndarray
        Complex RHS-power vector in local non-slack order.
    """
    dimension_count: int = int(basis_conjugate.shape[0])
    n_no_slack: int = int(basis_conjugate.shape[1])
    rhs_power: np.ndarray = np.zeros(n_no_slack, dtype=np.complex128)
    dimension_index: int

    # The MDHEM power RHS is a sum over dimensions. Keeping the whole loop in
    # compiled code avoids allocating one temporary dense vector per dimension.
    for dimension_index in range(dimension_count):
        previous_position: int = int(minus_e_row[dimension_index])
        if previous_position >= 0:
            local_index: int
            for local_index in range(n_no_slack):
                rhs_power[local_index] = rhs_power[local_index] + (
                    basis_conjugate[dimension_index, local_index] * x_coefficients[previous_position, local_index]
                )
        else:
            pass

    # The PV unknowns enter the power equation through the known ``Q * X``
    # convolution term, which only touches the PV local rows.
    pv_index: int
    for pv_index in range(pv_local.size):
        local_index = int(pv_local[pv_index])
        rhs_power[local_index] = rhs_power[local_index] - 1j * qx_known[pv_index]

    return rhs_power


def build_system_matrix(
    yred: scipy.sparse.csc_matrix,
    c_germ: np.ndarray,
    u_zero: np.ndarray,
    x_zero: np.ndarray,
    pv_local: np.ndarray,
) -> scipy.sparse.csc_matrix:
    """
    Build the constant MDHEM linear system matrix.

    Parameters
    ----------
    yred:
        Reduced bus admittance matrix for non-slack buses.
    c_germ:
        Germ coefficient ``P - jQ`` for every non-slack bus.
    u_zero:
        Germ voltage coefficient for every non-slack bus.
    x_zero:
        Germ reciprocal-voltage coefficient for every non-slack bus.
    pv_local:
        PV bus positions in local non-slack order.

    Returns
    -------
    scipy.sparse.csc_matrix
        Constant sparse matrix for all non-zero coefficients.
    """
    n_no_slack: int = yred.shape[0]
    n_pv: int = pv_local.size
    unknown_count: int = 4 * n_no_slack + n_pv
    max_entries: int = 4 * int(yred.nnz) + 12 * n_no_slack + 4 * n_pv
    row_indices: np.ndarray = np.zeros(max_entries, dtype=np.int64)
    column_indices: np.ndarray = np.zeros(max_entries, dtype=np.int64)
    data: np.ndarray = np.zeros(max_entries, dtype=np.float64)
    entry_count: int = 0

    yred_coo: scipy.sparse.coo_matrix = yred.tocoo()
    entry_index: int
    for entry_index in range(yred_coo.data.size):
        row_index: int = int(yred_coo.row[entry_index])
        column_index: int = int(yred_coo.col[entry_index])
        value: complex = complex(yred_coo.data[entry_index])
        entry_count = append_sparse_value(row_indices, column_indices, data, entry_count, row_index, column_index, value.real)
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, row_index, n_no_slack + column_index, -value.imag
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, n_no_slack + row_index, column_index, value.imag
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, n_no_slack + row_index, n_no_slack + column_index, value.real
        )

    local_index: int
    for local_index in range(n_no_slack):
        c_value: complex = complex(c_germ[local_index])
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, local_index, 2 * n_no_slack + local_index, -c_value.real
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, local_index, 3 * n_no_slack + local_index, c_value.imag
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, n_no_slack + local_index, 2 * n_no_slack + local_index, -c_value.imag
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, n_no_slack + local_index, 3 * n_no_slack + local_index, -c_value.real
        )

    pv_index: int
    for pv_index in range(n_pv):
        local_index = int(pv_local[pv_index])
        x_value: complex = complex(x_zero[local_index])
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, local_index, 4 * n_no_slack + pv_index, -x_value.imag
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, n_no_slack + local_index, 4 * n_no_slack + pv_index, x_value.real
        )

    for local_index in range(n_no_slack):
        x_value = complex(x_zero[local_index])
        u_value: complex = complex(u_zero[local_index])
        reciprocal_real_row: int = 2 * n_no_slack + local_index
        reciprocal_imag_row: int = 3 * n_no_slack + local_index
        entry_count = append_sparse_value(row_indices, column_indices, data, entry_count, reciprocal_real_row, local_index, x_value.real)
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, reciprocal_real_row, n_no_slack + local_index, x_value.imag
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, reciprocal_real_row, 2 * n_no_slack + local_index, u_value.real
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, reciprocal_real_row, 3 * n_no_slack + local_index, u_value.imag
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, reciprocal_imag_row, local_index, x_value.imag
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, reciprocal_imag_row, n_no_slack + local_index, -x_value.real
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, reciprocal_imag_row, 2 * n_no_slack + local_index, -u_value.imag
        )
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, reciprocal_imag_row, 3 * n_no_slack + local_index, u_value.real
        )

    for pv_index in range(n_pv):
        local_index = int(pv_local[pv_index])
        u_value = complex(u_zero[local_index])
        voltage_row: int = 4 * n_no_slack + pv_index
        entry_count = append_sparse_value(row_indices, column_indices, data, entry_count, voltage_row, local_index, 2.0 * u_value.real)
        entry_count = append_sparse_value(
            row_indices, column_indices, data, entry_count, voltage_row, n_no_slack + local_index, 2.0 * u_value.imag
        )

    matrix_coo: scipy.sparse.coo_matrix = scipy.sparse.coo_matrix(
        (data[0:entry_count], (row_indices[0:entry_count], column_indices[0:entry_count])),
        shape=(unknown_count, unknown_count),
    )
    matrix_csc: scipy.sparse.csc_matrix = matrix_coo.tocsc()
    return matrix_csc


def append_sparse_value(
    row_indices: np.ndarray,
    column_indices: np.ndarray,
    data: np.ndarray,
    entry_count: int,
    row_index: int,
    column_index: int,
    value: float,
) -> int:
    """
    Append a sparse matrix entry when it is numerically non-zero.

    Parameters
    ----------
    row_indices:
        Preallocated sparse row index array.
    column_indices:
        Preallocated sparse column index array.
    data:
        Preallocated sparse value array.
    entry_count:
        Next free entry position.
    row_index:
        Row index.
    column_index:
        Column index.
    value:
        Matrix value.

    Returns
    -------
    int
        Updated free-entry position.
    """
    if value != 0.0:
        row_indices[entry_count] = row_index
        column_indices[entry_count] = column_index
        data[entry_count] = value
        entry_count = entry_count + 1
    else:
        pass
    return entry_count


def calculate_known_reciprocal_convolution(
    table: MultiIndexTable,
    position: int,
    u_coefficients: np.ndarray,
    x_coefficients: np.ndarray,
) -> np.ndarray:
    """
    Calculate known terms of ``conj(U) * X`` for one coefficient.

    Parameters
    ----------
    table:
        Multi-index lookup table.
    position:
        Coefficient position.
    u_coefficients:
        Voltage coefficients.
    x_coefficients:
        Reciprocal-voltage coefficients.

    Returns
    -------
    numpy.ndarray
        Known convolution vector for every non-slack bus.
    """
    left_positions: np.ndarray = table.get_left_convolution_positions(position)
    right_positions: np.ndarray = table.get_right_convolution_positions(position)

    # The table object stays in Python, but once the index lists are extracted
    # the dense coefficient accumulation becomes a pure numerical kernel.
    if should_use_parallel_convolution(
        pair_count=int(left_positions.size),
        vector_width=int(u_coefficients.shape[1]),
    ):
        return calculate_known_reciprocal_convolution_parallel_numba(
            left_positions=left_positions,
            right_positions=right_positions,
            u_coefficients=u_coefficients,
            x_coefficients=x_coefficients,
        )
    else:
        return calculate_known_reciprocal_convolution_numba(
            left_positions=left_positions,
            right_positions=right_positions,
            u_coefficients=u_coefficients,
            x_coefficients=x_coefficients,
        )


@nb.njit(cache=True)
def calculate_known_reciprocal_convolution_numba(
    left_positions: np.ndarray,
    right_positions: np.ndarray,
    u_coefficients: np.ndarray,
    x_coefficients: np.ndarray,
) -> np.ndarray:
    """
    Accumulate the known ``conj(U) * X`` convolution terms with compiled loops.

    Parameters
    ----------
    left_positions:
        Left coefficient positions.
    right_positions:
        Right coefficient positions.
    u_coefficients:
        Voltage coefficients.
    x_coefficients:
        Reciprocal-voltage coefficients.

    Returns
    -------
    numpy.ndarray
        Known convolution vector.
    """
    known: np.ndarray = np.zeros(u_coefficients.shape[1], dtype=np.complex128)
    pair_index: int
    for pair_index in range(left_positions.size):
        left_position: int = int(left_positions[pair_index])
        right_position: int = int(right_positions[pair_index])
        local_index: int
        for local_index in range(u_coefficients.shape[1]):
            known[local_index] = known[local_index] + (
                np.conj(u_coefficients[left_position, local_index]) * x_coefficients[right_position, local_index]
            )
    return known


@nb.njit(cache=True, parallel=True)
def calculate_known_reciprocal_convolution_parallel_numba(
    left_positions: np.ndarray,
    right_positions: np.ndarray,
    u_coefficients: np.ndarray,
    x_coefficients: np.ndarray,
) -> np.ndarray:
    """
    Accumulate the known ``conj(U) * X`` convolution terms with parallel buses.

    Parameters
    ----------
    left_positions:
        Left coefficient positions.
    right_positions:
        Right coefficient positions.
    u_coefficients:
        Voltage coefficients.
    x_coefficients:
        Reciprocal-voltage coefficients.

    Returns
    -------
    numpy.ndarray
        Known convolution vector.
    """
    local_count: int = int(u_coefficients.shape[1])
    known: np.ndarray = np.zeros(local_count, dtype=np.complex128)
    local_index: int

    # Each local bus accumulates into its own output slot, so threading across
    # buses avoids any reduction conflict between worker threads.
    for local_index in nb.prange(local_count):
        pair_index: int
        value: complex = complex(0.0, 0.0)
        for pair_index in range(left_positions.size):
            left_position: int = int(left_positions[pair_index])
            right_position: int = int(right_positions[pair_index])
            value = value + (np.conj(u_coefficients[left_position, local_index]) * x_coefficients[right_position, local_index])
        known[local_index] = value

    return known


def calculate_known_voltage_convolution(
    table: MultiIndexTable,
    position: int,
    u_coefficients: np.ndarray,
    pv_local: np.ndarray,
) -> np.ndarray:
    """
    Calculate known terms of ``U * conj(U)`` for PV voltage constraints.

    Parameters
    ----------
    table:
        Multi-index lookup table.
    position:
        Coefficient position.
    u_coefficients:
        Voltage coefficients.
    pv_local:
        PV positions in local non-slack order.

    Returns
    -------
    numpy.ndarray
        Known real convolution vector for PV buses.
    """
    left_positions: np.ndarray = table.get_left_convolution_positions(position)
    right_positions: np.ndarray = table.get_right_convolution_positions(position)

    # The PV magnitude constraint only depends on dense coefficient slices and
    # the local PV positions, so it is also a good Numba target.
    if should_use_parallel_convolution(
        pair_count=int(left_positions.size),
        vector_width=int(pv_local.size),
    ):
        return calculate_known_voltage_convolution_parallel_numba(
            left_positions=left_positions,
            right_positions=right_positions,
            u_coefficients=u_coefficients,
            pv_local=pv_local,
        )
    else:
        return calculate_known_voltage_convolution_numba(
            left_positions=left_positions,
            right_positions=right_positions,
            u_coefficients=u_coefficients,
            pv_local=pv_local,
        )


@nb.njit(cache=True)
def calculate_known_voltage_convolution_numba(
    left_positions: np.ndarray,
    right_positions: np.ndarray,
    u_coefficients: np.ndarray,
    pv_local: np.ndarray,
) -> np.ndarray:
    """
    Accumulate the known ``U * conj(U)`` PV-magnitude terms with compiled loops.

    Parameters
    ----------
    left_positions:
        Left coefficient positions.
    right_positions:
        Right coefficient positions.
    u_coefficients:
        Voltage coefficients.
    pv_local:
        PV positions in local non-slack order.

    Returns
    -------
    numpy.ndarray
        Known real convolution vector.
    """
    known: np.ndarray = np.zeros(pv_local.size, dtype=np.float64)
    pair_index: int
    for pair_index in range(left_positions.size):
        left_position: int = int(left_positions[pair_index])
        right_position: int = int(right_positions[pair_index])
        pv_index: int
        for pv_index in range(pv_local.size):
            local_index: int = int(pv_local[pv_index])
            known[pv_index] = known[pv_index] + (
                u_coefficients[left_position, local_index] * np.conj(u_coefficients[right_position, local_index])
            ).real
    return known


@nb.njit(cache=True, parallel=True)
def calculate_known_voltage_convolution_parallel_numba(
    left_positions: np.ndarray,
    right_positions: np.ndarray,
    u_coefficients: np.ndarray,
    pv_local: np.ndarray,
) -> np.ndarray:
    """
    Accumulate the known ``U * conj(U)`` PV terms with parallel PV updates.

    Parameters
    ----------
    left_positions:
        Left coefficient positions.
    right_positions:
        Right coefficient positions.
    u_coefficients:
        Voltage coefficients.
    pv_local:
        PV positions in local non-slack order.

    Returns
    -------
    numpy.ndarray
        Known real convolution vector.
    """
    pv_count: int = int(pv_local.size)
    known: np.ndarray = np.zeros(pv_count, dtype=np.float64)
    pv_index: int

    # Each PV constraint writes to its own output slot, so the outer PV loop is
    # the safe way to expose parallelism without cross-thread reductions.
    for pv_index in nb.prange(pv_count):
        local_index: int = int(pv_local[pv_index])
        pair_index: int
        value: float = 0.0
        for pair_index in range(left_positions.size):
            left_position: int = int(left_positions[pair_index])
            right_position: int = int(right_positions[pair_index])
            value = value + (
                u_coefficients[left_position, local_index] * np.conj(u_coefficients[right_position, local_index])
            ).real
        known[pv_index] = value

    return known


def calculate_known_qx_convolution(
    table: MultiIndexTable,
    position: int,
    q_coefficients: np.ndarray,
    x_coefficients: np.ndarray,
    pv_local: np.ndarray,
) -> np.ndarray:
    """
    Calculate known terms of ``Q * X`` for PV power equations.

    Parameters
    ----------
    table:
        Multi-index lookup table.
    position:
        Coefficient position.
    q_coefficients:
        PV reactive-power coefficients.
    x_coefficients:
        Reciprocal-voltage coefficients.
    pv_local:
        PV positions in local non-slack order.

    Returns
    -------
    numpy.ndarray
        Known complex convolution vector for PV buses.
    """
    left_positions: np.ndarray = table.get_left_convolution_positions(position)
    right_positions: np.ndarray = table.get_right_convolution_positions(position)

    # The PV power balance uses a dense Q/X accumulation, so this wrapper hands
    # the raw arrays to a compiled kernel for the expensive inner loops.
    if should_use_parallel_convolution(
        pair_count=int(left_positions.size),
        vector_width=int(pv_local.size),
    ):
        return calculate_known_qx_convolution_parallel_numba(
            left_positions=left_positions,
            right_positions=right_positions,
            q_coefficients=q_coefficients,
            x_coefficients=x_coefficients,
            pv_local=pv_local,
        )
    else:
        return calculate_known_qx_convolution_numba(
            left_positions=left_positions,
            right_positions=right_positions,
            q_coefficients=q_coefficients,
            x_coefficients=x_coefficients,
            pv_local=pv_local,
        )


@nb.njit(cache=True)
def calculate_known_qx_convolution_numba(
    left_positions: np.ndarray,
    right_positions: np.ndarray,
    q_coefficients: np.ndarray,
    x_coefficients: np.ndarray,
    pv_local: np.ndarray,
) -> np.ndarray:
    """
    Accumulate the known ``Q * X`` PV terms with compiled loops.

    Parameters
    ----------
    left_positions:
        Left coefficient positions.
    right_positions:
        Right coefficient positions.
    q_coefficients:
        PV reactive-power coefficients.
    x_coefficients:
        Reciprocal-voltage coefficients.
    pv_local:
        PV positions in local non-slack order.

    Returns
    -------
    numpy.ndarray
        Known complex convolution vector.
    """
    known: np.ndarray = np.zeros(pv_local.size, dtype=np.complex128)
    pair_index: int
    for pair_index in range(left_positions.size):
        left_position: int = int(left_positions[pair_index])
        right_position: int = int(right_positions[pair_index])
        pv_index: int
        for pv_index in range(pv_local.size):
            local_index: int = int(pv_local[pv_index])
            known[pv_index] = known[pv_index] + (
                q_coefficients[left_position, pv_index] * x_coefficients[right_position, local_index]
            )
    return known


@nb.njit(cache=True, parallel=True)
def calculate_known_qx_convolution_parallel_numba(
    left_positions: np.ndarray,
    right_positions: np.ndarray,
    q_coefficients: np.ndarray,
    x_coefficients: np.ndarray,
    pv_local: np.ndarray,
) -> np.ndarray:
    """
    Accumulate the known ``Q * X`` PV terms with parallel PV updates.

    Parameters
    ----------
    left_positions:
        Left coefficient positions.
    right_positions:
        Right coefficient positions.
    q_coefficients:
        PV reactive-power coefficients.
    x_coefficients:
        Reciprocal-voltage coefficients.
    pv_local:
        PV positions in local non-slack order.

    Returns
    -------
    numpy.ndarray
        Known complex convolution vector.
    """
    pv_count: int = int(pv_local.size)
    known: np.ndarray = np.zeros(pv_count, dtype=np.complex128)
    pv_index: int

    # Each PV equation contributes to one independent output slot, which is
    # the natural grain for threading this dense accumulation.
    for pv_index in nb.prange(pv_count):
        local_index: int = int(pv_local[pv_index])
        pair_index: int
        value: complex = complex(0.0, 0.0)
        for pair_index in range(left_positions.size):
            left_position: int = int(left_positions[pair_index])
            right_position: int = int(right_positions[pair_index])
            value = value + (q_coefficients[left_position, pv_index] * x_coefficients[right_position, local_index])
        known[pv_index] = value

    return known


def solve_mdhelm_pv(
    ybus: scipy.sparse.csc_matrix,
    germ_voltage: np.ndarray,
    base_power: np.ndarray,
    germ_calculated_power: np.ndarray,
    slack: np.ndarray,
    pq: np.ndarray,
    pv: np.ndarray,
    no_slack: np.ndarray,
    voltage_setpoint: np.ndarray,
    max_order: int,
    bus_names: np.ndarray,
) -> MDHEMPVMap:
    """
    Solve the multidimensional HELM coefficients with PV buses.

    Parameters
    ----------
    ybus:
        Full bus admittance matrix.
    germ_voltage:
        Physical-germ voltage vector.
    base_power:
        Scheduled base complex bus power in per unit.
    germ_calculated_power:
        Calculated complex bus power at the germ voltage in per unit.
    slack:
        Slack bus indices.
    pq:
        PQ bus indices.
    pv:
        PV bus indices.
    no_slack:
        Non-slack bus indices.
    voltage_setpoint:
        Voltage magnitude setpoint vector.
    max_order:
        Maximum total polynomial order.
    bus_names:
        Bus names.

    Returns
    -------
    MDHEMPVMap
        Solved multidimensional HELM map.
    """
    ybus_csc: scipy.sparse.csc_matrix = scipy.sparse.csc_matrix(ybus)
    nbus: int = ybus_csc.shape[0]
    n_no_slack: int = no_slack.size
    n_pv: int = pv.size
    table: MultiIndexTable = create_multi_index_table(dims=n_no_slack, max_order=max_order)
    n_terms: int = table.get_terms_count()
    u_coefficients: np.ndarray = np.zeros((n_terms, n_no_slack), dtype=np.complex128)
    x_coefficients: np.ndarray = np.zeros((n_terms, n_no_slack), dtype=np.complex128)
    q_coefficients: np.ndarray = np.zeros((n_terms, n_pv), dtype=np.float64)

    basis: np.ndarray
    dimension_bus: np.ndarray
    dimension_local: np.ndarray
    dimension_is_pv: np.ndarray
    basis, dimension_bus, dimension_local, dimension_is_pv = create_per_bus_basis(
        base_power=base_power,
        germ_power=germ_calculated_power,
        no_slack=no_slack,
        pv=pv,
    )

    full_to_local: np.ndarray = create_full_to_local_lookup(nbus=nbus, no_slack=no_slack)
    pv_local: np.ndarray = np.zeros(n_pv, dtype=np.int64)
    pv_index: int
    for pv_index in range(n_pv):
        pv_local[pv_index] = full_to_local[int(pv[pv_index])]

    yred: scipy.sparse.csc_matrix = ybus_csc[np.ix_(no_slack, no_slack)].tocsc()
    u_zero: np.ndarray = germ_voltage[no_slack].copy()
    x_zero: np.ndarray = 1.0 / np.conj(u_zero)
    scheduled_power_germ: np.ndarray = np.array(germ_calculated_power, dtype=np.complex128)
    c_germ: np.ndarray = np.conj(scheduled_power_germ[no_slack])
    basis_conjugate: np.ndarray = np.conj(basis)
    zero_position: int = 0
    u_coefficients[zero_position, :] = u_zero
    x_coefficients[zero_position, :] = x_zero
    for pv_index in range(n_pv):
        q_coefficients[zero_position, pv_index] = scheduled_power_germ[int(pv[pv_index])].imag

    system_matrix: scipy.sparse.csc_matrix = build_system_matrix(
        yred=yred,
        c_germ=c_germ,
        u_zero=u_zero,
        x_zero=x_zero,
        pv_local=pv_local,
    )
    linear_solver: SparseLinearSolver = SparseLinearSolver(factorization=scipy.sparse.linalg.splu(system_matrix))
    minus_e_position: np.ndarray = table.get_minus_e_position()
    unknown_count: int = 4 * n_no_slack + n_pv
    rhs_block_columns: int = determine_rhs_block_columns(
        unknown_count=unknown_count,
        target_block_bytes=64 * 1024 * 1024,
    )

    order_index: int
    for order_index in range(1, max_order + 1):
        order_start: int = table.get_order_start(order_index)
        order_stop: int = table.get_order_stop(order_index)
        block_start: int = order_start

        # All coefficients of the same total order depend only on already
        # solved lower orders, so one sparse LU factorization can solve a whole
        # block of right-hand sides together.
        while block_start < order_stop:
            block_stop: int = min(order_stop, block_start + rhs_block_columns)
            block_size: int = block_stop - block_start
            rhs_block: np.ndarray = np.zeros((unknown_count, block_size), dtype=np.float64)
            block_offset: int

            for block_offset in range(block_size):
                position: int = block_start + block_offset
                qx_known: np.ndarray = calculate_known_qx_convolution(
                    table=table,
                    position=position,
                    q_coefficients=q_coefficients,
                    x_coefficients=x_coefficients,
                    pv_local=pv_local,
                )
                rhs_power: np.ndarray = calculate_rhs_power_numba(
                    minus_e_row=minus_e_position[position, :],
                    basis_conjugate=basis_conjugate,
                    x_coefficients=x_coefficients,
                    pv_local=pv_local,
                    qx_known=qx_known,
                )
                reciprocal_known: np.ndarray = calculate_known_reciprocal_convolution(
                    table=table,
                    position=position,
                    u_coefficients=u_coefficients,
                    x_coefficients=x_coefficients,
                )
                voltage_known: np.ndarray = calculate_known_voltage_convolution(
                    table=table,
                    position=position,
                    u_coefficients=u_coefficients,
                    pv_local=pv_local,
                )
                rhs_block[0:n_no_slack, block_offset] = rhs_power.real
                rhs_block[n_no_slack:2 * n_no_slack, block_offset] = rhs_power.imag
                rhs_block[2 * n_no_slack:3 * n_no_slack, block_offset] = -reciprocal_known.real
                rhs_block[3 * n_no_slack:4 * n_no_slack, block_offset] = -reciprocal_known.imag
                rhs_block[4 * n_no_slack:4 * n_no_slack + n_pv, block_offset] = -voltage_known

            solution_block: np.ndarray = linear_solver.solve(rhs=rhs_block)

            for block_offset in range(block_size):
                position = block_start + block_offset
                u_coefficients[position, :] = (
                    solution_block[0:n_no_slack, block_offset]
                    + 1j * solution_block[n_no_slack:2 * n_no_slack, block_offset]
                )
                x_coefficients[position, :] = (
                    solution_block[2 * n_no_slack:3 * n_no_slack, block_offset]
                    + 1j * solution_block[3 * n_no_slack:4 * n_no_slack, block_offset]
                )
                q_coefficients[position, :] = solution_block[
                    4 * n_no_slack:4 * n_no_slack + n_pv,
                    block_offset,
                ]

            block_start = block_stop

    return MDHEMPVMap(
        ybus=ybus_csc,
        slack=slack,
        pq=pq,
        pv=pv,
        no_slack=no_slack,
        pv_local=pv_local,
        dimension_bus=dimension_bus,
        dimension_local=dimension_local,
        dimension_is_pv=dimension_is_pv,
        slack_voltage=germ_voltage[slack].copy(),
        voltage_setpoint=voltage_setpoint,
        scheduled_power_germ=scheduled_power_germ,
        scheduled_basis=basis,
        table=table,
        u_coefficients=u_coefficients,
        x_coefficients=x_coefficients,
        q_coefficients=q_coefficients,
        bus_names=bus_names,
    )


def load_veragrid_case_data(matpower_path: Path) -> VeraGridCaseData:
    """
    Load a MATPOWER case through VeraGrid and solve the physical germ.

    Parameters
    ----------
    matpower_path:
        Path to the MATPOWER file.

    Returns
    -------
    VeraGridCaseData
        VeraGrid numerical data and physical-germ solution.
    """
    import VeraGridEngine as vg
    import VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf

    grid: object = vg.open_file(str(matpower_path))
    numerical_circuit: object = vg.compile_numerical_circuit_at(circuit=grid, t_idx=None)
    admittance: object = numerical_circuit.get_admittance_matrices()
    base_power: np.ndarray = numerical_circuit.get_power_injections_pu()
    indices: object = numerical_circuit.get_simulation_indices(Sbus=base_power, force_only_pq_pv_vd_types=True)
    slack: np.ndarray = np.asarray(indices.vd, dtype=np.int64)
    pq: np.ndarray = np.asarray(indices.pq, dtype=np.int64)
    pv: np.ndarray = np.asarray(indices.pv, dtype=np.int64)
    no_slack: np.ndarray = np.asarray(indices.no_slack, dtype=np.int64)
    voltage_setpoint: np.ndarray = np.abs(np.asarray(numerical_circuit.bus_data.Vbus, dtype=np.complex128))
    bus_names: np.ndarray = np.asarray(numerical_circuit.bus_data.names, dtype=object)

    power_flow_options: object = vg.PowerFlowOptions(
        solver_type=vg.SolverType.NR,
        retry_with_other_methods=False,
        control_q=True,
        control_taps_phase=False,
        control_taps_modules=False,
        apply_temperature_correction=False,
        use_stored_guess=False,
        tolerance=1e-10,
    )
    power_flow_results: object = vg.power_flow(grid=grid, options=power_flow_options)
    germ_voltage: np.ndarray = np.asarray(power_flow_results.voltage, dtype=np.complex128)
    newton_error: float = float(power_flow_results.error)
    germ_calculated_power: np.ndarray = np.asarray(cf.compute_power(admittance.Ybus, germ_voltage), dtype=np.complex128)

    return VeraGridCaseData(
        grid=grid,
        numerical_circuit=numerical_circuit,
        admittance=admittance,
        base_power=base_power,
        germ_voltage=germ_voltage,
        germ_calculated_power=germ_calculated_power,
        slack=slack,
        pq=pq,
        pv=pv,
        no_slack=no_slack,
        bus_names=bus_names,
        voltage_setpoint=voltage_setpoint,
        newton_error=newton_error,
    )


def build_mdhelm_map_from_veragrid_case(matpower_path: Path, max_order: int) -> tuple[VeraGridCaseData, MDHEMPVMap]:
    """
    Build a per-bus MDHEM map from a VeraGrid-loaded MATPOWER case.

    Parameters
    ----------
    matpower_path:
        Path to the MATPOWER case.
    max_order:
        Maximum total polynomial order.

    Returns
    -------
    tuple[VeraGridCaseData, MDHEMPVMap]
        VeraGrid data and the solved MDHEM map.
    """
    case_data: VeraGridCaseData = load_veragrid_case_data(matpower_path=matpower_path)
    mdhelm_map: MDHEMPVMap = solve_mdhelm_pv(
        ybus=case_data.admittance.Ybus,
        germ_voltage=case_data.germ_voltage,
        base_power=case_data.base_power,
        germ_calculated_power=case_data.germ_calculated_power,
        slack=case_data.slack,
        pq=case_data.pq,
        pv=case_data.pv,
        no_slack=case_data.no_slack,
        voltage_setpoint=case_data.voltage_setpoint,
        max_order=max_order,
        bus_names=case_data.bus_names,
    )
    return case_data, mdhelm_map


def evaluate_mdhelm_with_veragrid_postprocess(
    case_data: VeraGridCaseData,
    mdhelm_map: MDHEMPVMap,
    multipliers: np.ndarray,
    tolerance: float,
) -> MDHEMRunResult:
    """
    Evaluate the MDHEM map and compute VeraGrid-style mismatch and flows.

    Parameters
    ----------
    case_data:
        VeraGrid numerical data.
    mdhelm_map:
        Solved MDHEM map.
    multipliers:
        Per-bus injection multipliers.
    tolerance:
        Numerical tolerance used for the convergence-like flag.

    Returns
    -------
    MDHEMRunResult
        Evaluation result.
    """
    import VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf

    voltage: np.ndarray
    scheduled_power: np.ndarray
    pv_reactive_power: np.ndarray
    voltage, scheduled_power, pv_reactive_power = mdhelm_map.evaluate_multipliers(multipliers=multipliers)
    calculated_power: np.ndarray = np.asarray(cf.compute_power(case_data.admittance.Ybus, voltage), dtype=np.complex128)
    mismatch_vector: np.ndarray = cf.compute_fx(
        Scalc=calculated_power,
        Sbus=scheduled_power,
        idx_dP=mdhelm_map.get_no_slack(),
        idx_dQ=mdhelm_map.get_pq(),
    )
    mismatch_norm: float = float(cf.compute_fx_error(mismatch_vector))
    pv_voltage_error: float
    if mdhelm_map.get_pv().size > 0:
        pv_voltage_error = float(np.max(np.abs(np.abs(voltage[mdhelm_map.get_pv()]) - case_data.voltage_setpoint[mdhelm_map.get_pv()])))
    else:
        pv_voltage_error = 0.0

    branch_from_power: Optional[np.ndarray] = None
    branch_to_power: Optional[np.ndarray] = None
    branch_loading: Optional[np.ndarray] = None
    branch_losses: Optional[np.ndarray] = None
    try:
        post_process_result: tuple[np.ndarray, ...] = cf.power_flow_post_process_nonlinear(
            Sbus=calculated_power,
            V=voltage,
            F=case_data.numerical_circuit.passive_branch_data.F,
            T=case_data.numerical_circuit.passive_branch_data.T,
            pv=mdhelm_map.get_pv(),
            vd=mdhelm_map.get_slack(),
            Ybus=case_data.admittance.Ybus,
            Yf=case_data.admittance.Yf,
            Yt=case_data.admittance.Yt,
            Yshunt_bus=case_data.admittance.Yshunt_bus,
            branch_rates=case_data.numerical_circuit.passive_branch_data.rates,
            Sbase=case_data.numerical_circuit.Sbase,
        )
        branch_from_power = post_process_result[0]
        branch_to_power = post_process_result[1]
        branch_loading = post_process_result[5]
        branch_losses = post_process_result[6]
    except Exception:
        branch_from_power = None
        branch_to_power = None
        branch_loading = None
        branch_losses = None

    converged_like: bool = bool(mismatch_norm <= tolerance and pv_voltage_error <= tolerance)
    return MDHEMRunResult(
        multipliers=multipliers,
        voltage=voltage,
        scheduled_power=scheduled_power,
        calculated_power=calculated_power,
        pv_reactive_power=pv_reactive_power,
        mismatch_norm=mismatch_norm,
        pv_voltage_error=pv_voltage_error,
        converged_like=converged_like,
        branch_from_power=branch_from_power,
        branch_to_power=branch_to_power,
        branch_loading=branch_loading,
        branch_losses=branch_losses,
    )


def print_dimension_summary(mdhelm_map: MDHEMPVMap) -> None:
    """
    Print the bus associated with every MDHEM dimension.

    Parameters
    ----------
    mdhelm_map:
        Solved MDHEM map.

    Returns
    -------
    None
        The function prints to standard output.
    """
    dimension_bus: np.ndarray = mdhelm_map.get_dimension_bus_indices()
    bus_names: np.ndarray = mdhelm_map.get_bus_names()
    dimension_index: int
    for dimension_index in range(dimension_bus.size):
        full_bus: int = int(dimension_bus[dimension_index])
        bus_label: str = str(bus_names[full_bus])
        print(f"  s{dimension_index + 1}: bus {full_bus + 1} - {bus_label}")


def print_voltage_summary(case_data: VeraGridCaseData, result: MDHEMRunResult) -> None:
    """
    Print bus voltage results.

    Parameters
    ----------
    case_data:
        VeraGrid numerical data.
    result:
        MDHEM evaluation result.

    Returns
    -------
    None
        The function prints to standard output.
    """
    bus_index: int
    print("bus, name, |V|, angle_deg, V_complex")
    for bus_index in range(result.voltage.size):
        voltage: complex = complex(result.voltage[bus_index])
        bus_name: str = str(case_data.bus_names[bus_index])
        print(
            f"{bus_index + 1:>3}, {bus_name:<20}, {abs(voltage):.6f}, "
            f"{np.angle(voltage, deg=True): .6f}, {voltage.real:.6f}{voltage.imag:+.6f}j"
        )


def run_case14_demo() -> None:
    """
    Run the self-contained case14 per-bus PV MDHEM example.

    Returns
    -------
    None
        The function prints build and evaluation information.
    """
    case_path: Path = Path(__file__).resolve().with_name("case14.matpower")
    max_order: int = 4
    tolerance: float = 1e-8
    case_data: VeraGridCaseData
    mdhelm_map: MDHEMPVMap
    case_data, mdhelm_map = build_mdhelm_map_from_veragrid_case(matpower_path=case_path, max_order=max_order)
    multipliers: np.ndarray = np.ones(mdhelm_map.get_dimensions_count(), dtype=np.complex128)
    result: MDHEMRunResult = evaluate_mdhelm_with_veragrid_postprocess(
        case_data=case_data,
        mdhelm_map=mdhelm_map,
        multipliers=multipliers,
        tolerance=tolerance,
    )

    print("\nMDHEM-PV per-bus map built from VeraGrid/MATPOWER case")
    print("-------------------------------------------------------")
    print(f"Buses:                 {case_data.numerical_circuit.nbus}")
    print(f"Branches:              {case_data.numerical_circuit.nbr}")
    print(f"Sbase:                 {case_data.numerical_circuit.Sbase} MVA")
    print(f"Dimensions:            {mdhelm_map.get_dimensions_count()} = one per non-slack bus")
    print(f"Maximum order:         {mdhelm_map.get_max_order()}")
    print(f"Coefficients per bus:  {mdhelm_map.get_coefficients_count()}")
    print(f"Expected coefficient count: {count_coefficients(mdhelm_map.get_dimensions_count(), mdhelm_map.get_max_order())}")
    print(f"Slack buses:           {[int(index) + 1 for index in mdhelm_map.get_slack()]}")
    print(f"PQ buses:              {[int(index) + 1 for index in mdhelm_map.get_pq()]}")
    print(f"PV buses:              {[int(index) + 1 for index in mdhelm_map.get_pv()]}")
    print(f"VeraGrid NR germ error: {case_data.newton_error:.4e}")
    print("\nDimensions")
    print_dimension_summary(mdhelm_map=mdhelm_map)
    print("\nEvaluation at multipliers = ones(D)")
    print(f"Power-flow mismatch ||f||_inf: {result.mismatch_norm:.4e}")
    print(f"PV voltage max error:          {result.pv_voltage_error:.4e}")
    print(f"Converged-like:                {result.converged_like}")
    print("\nVoltage samples")
    print_voltage_summary(case_data=case_data, result=result)

    if result.branch_from_power is None:
        print("\nBranch post-processing was not available in this VeraGrid version.")
    else:
        print("\nFirst 5 branch flows from VeraGrid post-process, MVA")
        branch_index: int
        branch_count: int = min(5, result.branch_from_power.size)
        for branch_index in range(branch_count):
            branch_power: complex = complex(result.branch_from_power[branch_index])
            print(f"branch {branch_index:>2}: Sf = {branch_power.real: .4f} MW {branch_power.imag:+.4f} MVAr")


if __name__ == "__main__":
    run_case14_demo()
else:
    pass
