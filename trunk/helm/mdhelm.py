"""
Shared MDHEM business logic for VeraGrid.

This module contains the implementation previously split across the case14
example and query-artifact modules. Legacy entrypoints keep their filenames,
but the actual MDHEM solver and artifact logic lives here.
"""

from __future__ import annotations

import math
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence, TYPE_CHECKING

import numba as nb
import numpy as np
import scipy.optimize
import scipy.sparse
import scipy.sparse.linalg

if TYPE_CHECKING:
    from VeraGridEngine.Devices.Injections.generator import Generator
    from VeraGridEngine.Devices.Injections.load import Load
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


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
    terms_count:
        Total number of coefficient rows.
    active_dim_offsets:
        Prefix offsets into the flat arrays describing the non-zero dimensions
        of each multi-index row.
    active_dims_flat:
        Flat non-zero dimension indices for every row.
    minus_e_flat:
        Flat coefficient positions of ``alpha - e_d`` paired with
        ``active_dims_flat``.
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
        "_terms_count",
        "_order_offsets",
        "_active_dim_offsets",
        "_active_dims_flat",
        "_minus_e_flat",
        "_proper_sub_offsets",
        "_proper_sub_left_flat",
        "_proper_sub_right_flat",
    )

    def __init__(
        self,
        dims: int,
        max_order: int,
        terms_count: int,
        order_offsets: np.ndarray,
        active_dim_offsets: np.ndarray,
        active_dims_flat: np.ndarray,
        minus_e_flat: np.ndarray,
        proper_sub_offsets: np.ndarray,
        proper_sub_left_flat: np.ndarray,
        proper_sub_right_flat: np.ndarray,
    ) -> None:
        self._dims: int = dims
        self._max_order: int = max_order
        self._terms_count: int = terms_count
        self._order_offsets: np.ndarray = order_offsets
        self._active_dim_offsets: np.ndarray = active_dim_offsets
        self._active_dims_flat: np.ndarray = active_dims_flat
        self._minus_e_flat: np.ndarray = minus_e_flat
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
        return build_alpha_array_from_compressed(table=self)

    def get_terms_count(self) -> int:
        """
        Get the total number of coefficient rows.

        Returns
        -------
        int
            Number of coefficient rows.
        """
        return self._terms_count

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

    def get_active_dimension_positions(self, position: int) -> np.ndarray:
        """
        Get the non-zero dimension indices of one multi-index row.

        Parameters
        ----------
        position:
            Current coefficient position.

        Returns
        -------
        numpy.ndarray
            Flat non-zero dimension indices.
        """
        start: int = int(self._active_dim_offsets[position])
        stop: int = int(self._active_dim_offsets[position + 1])
        return self._active_dims_flat[start:stop]

    def get_minus_e_previous_positions(self, position: int) -> np.ndarray:
        """
        Get the ``alpha - e_d`` coefficient positions for one row.

        Parameters
        ----------
        position:
            Current coefficient position.

        Returns
        -------
        numpy.ndarray
            Flat coefficient positions paired with the active dimensions.
        """
        start: int = int(self._active_dim_offsets[position])
        stop: int = int(self._active_dim_offsets[position + 1])
        return self._minus_e_flat[start:stop]

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


def build_alpha_array_from_compressed(table: MultiIndexTable) -> np.ndarray:
    """
    Reconstruct the dense exponent matrix from the compressed table storage.

    Parameters
    ----------
    table:
        Compressed multi-index table.

    Returns
    -------
    numpy.ndarray
        Dense integer exponent matrix.
    """
    terms_count: int = table.get_terms_count()
    dims: int = table.get_dims()
    alphas_array: np.ndarray = np.zeros((terms_count, dims), dtype=np.int64)
    position: int

    # Each row stores the valid ``alpha - e_d`` predecessors for the non-zero
    # coordinates only. Reusing any one predecessor is enough to reconstruct
    # the row because all paths lead to the same multi-index.
    for position in range(1, terms_count):
        active_dims: np.ndarray = table.get_active_dimension_positions(position)
        previous_positions: np.ndarray = table.get_minus_e_previous_positions(position)
        previous_position: int = int(previous_positions[0])
        active_dimension: int = int(active_dims[0])
        alphas_array[position, :] = alphas_array[previous_position, :]
        alphas_array[position, active_dimension] = alphas_array[position, active_dimension] + 1

    return alphas_array


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
            weights: np.ndarray = calculate_monomial_weights_from_table(
                table=self._table,
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


def count_total_active_entries(dims: int, max_order: int) -> int:
    """
    Count the stored non-zero exponent coordinates across all term rows.

    Parameters
    ----------
    dims:
        Number of embedding dimensions.
    max_order:
        Maximum total order.

    Returns
    -------
    int
        Total number of non-zero coordinates over all rows.
    """
    total_active_entries: int = 0
    order_index: int

    for order_index in range(1, max_order + 1):
        total_active_entries = total_active_entries + (
            order_index * math.comb(order_index + dims - 1, dims - 1)
        )

    return total_active_entries


def estimate_compressed_multi_index_table_bytes(total_terms: int, total_active_entries: int) -> int:
    """
    Estimate the compressed persistent storage required by the table.

    Parameters
    ----------
    total_terms:
        Number of coefficient rows.
    total_active_entries:
        Total stored non-zero coordinates across all rows.

    Returns
    -------
    int
        Lower-bound byte estimate for the compressed table.
    """
    offset_bytes: int = (total_terms + 1) * np.dtype(np.int64).itemsize
    flat_bytes: int = total_active_entries * np.dtype(np.int64).itemsize
    proper_offset_bytes: int = (total_terms + 1) * np.dtype(np.int64).itemsize

    # The convolution pair arrays are not included here. This is still enough
    # to reject impossible full-space tables because the term-count explosion
    # dominates long before those arrays are added.
    return offset_bytes + flat_bytes + flat_bytes + proper_offset_bytes


def validate_multi_index_table_shape(
    dims: int,
    max_order: int,
    total_terms: int,
) -> None:
    """
    Reject impossible multi-index tables before any dense allocation happens.

    Parameters
    ----------
    dims:
        Number of embedding dimensions.
    max_order:
        Maximum total order.
    total_terms:
        Number of coefficient rows.

    Returns
    -------
    None
        The function raises when the table is clearly impossible.
    """
    total_active_entries: int = count_total_active_entries(dims=dims, max_order=max_order)
    dense_build_bytes: int = estimate_multi_index_table_bytes(total_terms=total_terms, dims=dims)
    compressed_table_bytes: int = estimate_compressed_multi_index_table_bytes(
        total_terms=total_terms,
        total_active_entries=total_active_entries,
    )
    physical_memory_bytes: Optional[int] = get_physical_memory_bytes()

    # Full-space per-bus embeddings can explode combinatorially. Failing here
    # is better than overflowing int64 or asking NumPy for petabytes.
    if compressed_table_bytes > (1 << 40):
        raise MemoryError(
            "MDHEM multi-index table is too large for compressed storage: "
            f"dims={dims}, max_order={max_order}, terms={total_terms}, "
            f"compressed_lower_bound={format_byte_count(compressed_table_bytes)}"
        )
    else:
        pass

    if physical_memory_bytes is not None:
        if dense_build_bytes > physical_memory_bytes // 2:
            raise MemoryError(
                "MDHEM multi-index build would exceed practical host memory: "
                f"dims={dims}, max_order={max_order}, terms={total_terms}, "
                f"dense_build_estimate={format_byte_count(dense_build_bytes)}, "
                f"host_memory={format_byte_count(physical_memory_bytes)}"
            )
        else:
            pass
    else:
        pass


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
    validate_multi_index_table_shape(dims=dims, max_order=max_order, total_terms=total_terms)

    # The linear artifact used by the compressed 2000-bus path only needs the
    # zero and first-order rows. Building the full Pascal table for thousands
    # of dimensions is pure overhead there, and it also triggers int64
    # overflow warnings despite the final term count being tiny.
    if max_order == 0:
        return MultiIndexTable(
            dims=dims,
            max_order=max_order,
            terms_count=1,
            order_offsets=order_offsets,
            active_dim_offsets=np.zeros(2, dtype=np.int64),
            active_dims_flat=np.zeros(0, dtype=np.int64),
            minus_e_flat=np.zeros(0, dtype=np.int64),
            proper_sub_offsets=np.zeros(2, dtype=np.int64),
            proper_sub_left_flat=np.zeros(0, dtype=np.int64),
            proper_sub_right_flat=np.zeros(0, dtype=np.int64),
        )
    else:
        pass

    if max_order == 1 and dims > 0:
        active_dim_offsets: np.ndarray = np.zeros(total_terms + 1, dtype=np.int64)
        active_dim_offsets[0] = 0
        active_dim_offsets[1] = 0
        active_dim_offsets[2:] = np.arange(1, dims + 1, dtype=np.int64)
        active_dims_flat: np.ndarray = np.arange(dims - 1, -1, -1, dtype=np.int64)
        minus_e_flat: np.ndarray = np.zeros(dims, dtype=np.int64)
        proper_sub_offsets: np.ndarray = np.zeros(total_terms + 1, dtype=np.int64)
        return MultiIndexTable(
            dims=dims,
            max_order=max_order,
            terms_count=total_terms,
            order_offsets=order_offsets,
            active_dim_offsets=active_dim_offsets,
            active_dims_flat=active_dims_flat,
            minus_e_flat=minus_e_flat,
            proper_sub_offsets=proper_sub_offsets,
            proper_sub_left_flat=np.zeros(0, dtype=np.int64),
            proper_sub_right_flat=np.zeros(0, dtype=np.int64),
        )
    else:
        pass

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

    active_counts: np.ndarray = np.count_nonzero(alphas_array, axis=1).astype(np.int64)
    active_dim_offsets: np.ndarray = np.zeros(total_terms + 1, dtype=np.int64)
    active_dim_offsets[1:] = np.cumsum(active_counts)
    active_dims_flat: np.ndarray = np.zeros(int(active_dim_offsets[-1]), dtype=np.int64)
    minus_e_flat: np.ndarray = np.zeros(int(active_dim_offsets[-1]), dtype=np.int64)
    position: int

    for position in range(total_terms):
        start: int = int(active_dim_offsets[position])
        stop: int = int(active_dim_offsets[position + 1])
        if stop > start:
            active_dimensions: np.ndarray = np.nonzero(alphas_array[position, :])[0].astype(np.int64)
            active_dims_flat[start:stop] = active_dimensions
            minus_e_flat[start:stop] = minus_e_position[position, active_dimensions]
        else:
            pass

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
        terms_count=total_terms,
        order_offsets=order_offsets,
        active_dim_offsets=active_dim_offsets,
        active_dims_flat=active_dims_flat,
        minus_e_flat=minus_e_flat,
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


@nb.njit(cache=True)
def calculate_monomial_weights_from_table_numba(
    terms_count: int,
    active_dim_offsets: np.ndarray,
    active_dims_flat: np.ndarray,
    minus_e_flat: np.ndarray,
    values: np.ndarray,
) -> np.ndarray:
    """
    Evaluate all monomials directly from the compressed table storage.

    Parameters
    ----------
    terms_count:
        Number of coefficient rows.
    active_dim_offsets:
        Prefix offsets into the non-zero dimension data.
    active_dims_flat:
        Flat non-zero dimension indices.
    minus_e_flat:
        Flat predecessor positions paired with ``active_dims_flat``.
    values:
        Complex evaluation point.

    Returns
    -------
    numpy.ndarray
        Complex monomial weights.
    """
    weights: np.ndarray = np.ones(terms_count, dtype=np.complex128)
    position: int

    # Each non-zero term can be reached from any one of its ``alpha - e_d``
    # predecessors. Using the first stored predecessor yields the same monomial
    # value with no need to reconstruct the full exponent vector.
    for position in range(1, terms_count):
        start: int = int(active_dim_offsets[position])
        previous_position: int = int(minus_e_flat[start])
        active_dimension: int = int(active_dims_flat[start])
        weights[position] = weights[previous_position] * values[active_dimension]

    return weights


def calculate_monomial_weights_from_table(table: MultiIndexTable, values: np.ndarray) -> np.ndarray:
    """
    Evaluate all monomials directly from the compressed multi-index table.

    Parameters
    ----------
    table:
        Compressed multi-index table.
    values:
        Complex evaluation point.

    Returns
    -------
    numpy.ndarray
        Complex monomial weights.
    """
    value_array: np.ndarray = np.asarray(values, dtype=np.complex128)
    return calculate_monomial_weights_from_table_numba(
        terms_count=table.get_terms_count(),
        active_dim_offsets=table._active_dim_offsets,
        active_dims_flat=table._active_dims_flat,
        minus_e_flat=table._minus_e_flat,
        values=value_array,
    )


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
    active_dims_row: np.ndarray,
    minus_e_previous_row: np.ndarray,
    basis_conjugate: np.ndarray,
    x_coefficients: np.ndarray,
    pv_local: np.ndarray,
    qx_known: np.ndarray,
) -> np.ndarray:
    """
    Assemble the complex power-balance RHS contribution for one coefficient.

    Parameters
    ----------
    active_dims_row:
        Non-zero dimension indices of the current coefficient row.
    minus_e_previous_row:
        ``alpha - e_d`` coefficient positions paired with ``active_dims_row``.
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
    n_no_slack: int = int(basis_conjugate.shape[1])
    rhs_power: np.ndarray = np.zeros(n_no_slack, dtype=np.complex128)
    entry_index: int

    # The MDHEM power RHS is a sum over dimensions. Keeping the whole loop in
    # compiled code avoids allocating one temporary dense vector per dimension.
    for entry_index in range(active_dims_row.size):
        dimension_index: int = int(active_dims_row[entry_index])
        previous_position: int = int(minus_e_previous_row[entry_index])
        local_index: int
        for local_index in range(n_no_slack):
            rhs_power[local_index] = rhs_power[local_index] + (
                basis_conjugate[dimension_index, local_index] * x_coefficients[previous_position, local_index]
            )

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
                active_dims_row: np.ndarray = table.get_active_dimension_positions(position)
                minus_e_previous_row: np.ndarray = table.get_minus_e_previous_positions(position)
                qx_known: np.ndarray = calculate_known_qx_convolution(
                    table=table,
                    position=position,
                    q_coefficients=q_coefficients,
                    x_coefficients=x_coefficients,
                    pv_local=pv_local,
                )
                rhs_power: np.ndarray = calculate_rhs_power_numba(
                    active_dims_row=active_dims_row,
                    minus_e_previous_row=minus_e_previous_row,
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

class DimensionKind(Enum):
    """
    Enumerate the supported embedding dimensions.

    The enum is stored in the artifact as integer codes to avoid fragile string
    comparisons when the artifact is loaded again later.
    """

    PQ_ACTIVE = 1
    PQ_REACTIVE = 2
    PV_ACTIVE = 3


class VeraGridQueryCaseData:
    """
    Store the VeraGrid network data required to build the artifact.

    Parameters
    ----------
    ybus:
        Full bus admittance matrix.
    yf:
        Branch-from admittance matrix.
    yt:
        Branch-to admittance matrix.
    slack_voltage:
        Fixed slack voltage vector in full bus order.
    base_power:
        Original scheduled complex bus powers in per unit.
    slack:
        Slack bus indices.
    pq:
        PQ bus indices.
    pv:
        PV bus indices.
    no_slack:
        Non-slack bus indices.
    bus_names:
        Bus names in full bus order.
    voltage_setpoint:
        Voltage magnitude setpoints in full bus order.
    branch_from_indices:
        Branch-from bus indices.
    branch_to_indices:
        Branch-to bus indices.
    branch_rates:
        Branch MVA ratings.
    sbase:
        System base power in MVA.
    """

    __slots__ = (
        "ybus",
        "yf",
        "yt",
        "slack_voltage",
        "base_power",
        "slack",
        "pq",
        "pv",
        "no_slack",
        "bus_names",
        "voltage_setpoint",
        "branch_from_indices",
        "branch_to_indices",
        "branch_rates",
        "sbase",
    )

    def __init__(
        self,
        ybus: scipy.sparse.csc_matrix,
        yf: scipy.sparse.csc_matrix,
        yt: scipy.sparse.csc_matrix,
        slack_voltage: np.ndarray,
        base_power: np.ndarray,
        slack: np.ndarray,
        pq: np.ndarray,
        pv: np.ndarray,
        no_slack: np.ndarray,
        bus_names: np.ndarray,
        voltage_setpoint: np.ndarray,
        branch_from_indices: np.ndarray,
        branch_to_indices: np.ndarray,
        branch_rates: np.ndarray,
        sbase: float,
    ) -> None:
        self.ybus: scipy.sparse.csc_matrix = ybus
        self.yf: scipy.sparse.csc_matrix = yf
        self.yt: scipy.sparse.csc_matrix = yt
        self.slack_voltage: np.ndarray = slack_voltage
        self.base_power: np.ndarray = base_power
        self.slack: np.ndarray = slack
        self.pq: np.ndarray = pq
        self.pv: np.ndarray = pv
        self.no_slack: np.ndarray = no_slack
        self.bus_names: np.ndarray = bus_names
        self.voltage_setpoint: np.ndarray = voltage_setpoint
        self.branch_from_indices: np.ndarray = branch_from_indices
        self.branch_to_indices: np.ndarray = branch_to_indices
        self.branch_rates: np.ndarray = branch_rates
        self.sbase: float = sbase


class PhysicalGermContext:
    """
    Group the data required by the physical-germ nonlinear equations.

    Parameters
    ----------
    ybus:
        Full bus admittance matrix.
    slack:
        Slack bus indices.
    pq:
        PQ bus indices.
    pv:
        PV bus indices.
    no_slack:
        Non-slack bus indices.
    slack_voltage:
        Fixed slack voltage vector.
    voltage_setpoint:
        Voltage magnitude targets.
    pv_active_power:
        Fixed active powers at PV buses for the germ.
    """

    __slots__ = (
        "ybus",
        "slack",
        "pq",
        "pv",
        "no_slack",
        "slack_voltage",
        "voltage_setpoint",
        "pv_active_power",
        "full_to_local",
        "full_to_pq_position",
        "pq_local",
        "pv_local",
    )

    def __init__(
        self,
        ybus: scipy.sparse.csc_matrix,
        slack: np.ndarray,
        pq: np.ndarray,
        pv: np.ndarray,
        no_slack: np.ndarray,
        slack_voltage: np.ndarray,
        voltage_setpoint: np.ndarray,
        pv_active_power: np.ndarray,
    ) -> None:
        self.ybus: scipy.sparse.csc_matrix = ybus
        self.slack: np.ndarray = slack
        self.pq: np.ndarray = pq
        self.pv: np.ndarray = pv
        self.no_slack: np.ndarray = no_slack
        self.slack_voltage: np.ndarray = slack_voltage
        self.voltage_setpoint: np.ndarray = voltage_setpoint
        self.pv_active_power: np.ndarray = pv_active_power
        self.full_to_local: np.ndarray = create_full_to_local_lookup(nbus=ybus.shape[0], no_slack=no_slack)
        self.full_to_pq_position: np.ndarray = -np.ones(ybus.shape[0], dtype=np.int64)
        self.pq_local: np.ndarray = convert_full_indices_to_local(full_to_local=self.full_to_local, full_indices=pq)
        self.pv_local: np.ndarray = convert_full_indices_to_local(full_to_local=self.full_to_local, full_indices=pv)
        pq_index: int
        for pq_index in range(pq.size):
            self.full_to_pq_position[int(pq[pq_index])] = pq_index


class MDHEMQueryResult:
    """
    Store the online query result returned by the artifact.

    Parameters
    ----------
    pq_active_power:
        Queried active powers for PQ buses.
    pq_reactive_power:
        Queried reactive powers for PQ buses.
    pv_active_power:
        Queried active powers for PV buses.
    voltage:
        Complex bus voltage vector.
    scheduled_power:
        Scheduled complex bus powers represented by the query.
    calculated_power:
        Power computed from ``Ybus`` and ``voltage``.
    pv_reactive_power:
        Reactive powers solved by the PV series.
    mismatch_norm:
        Infinity norm of the power-flow mismatch.
    pv_voltage_error:
        Maximum absolute PV voltage-magnitude error.
    converged_like:
        True when the mismatch and PV voltage error are below tolerance.
    branch_from_power:
        Branch-from complex powers in MVA.
    branch_to_power:
        Branch-to complex powers in MVA.
    branch_loading:
        Branch loading ratio, using VeraGrid's ``Sf / rate`` convention.
    branch_losses:
        Branch losses in MVA.
    """

    __slots__ = (
        "pq_active_power",
        "pq_reactive_power",
        "pv_active_power",
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
        pq_active_power: np.ndarray,
        pq_reactive_power: np.ndarray,
        pv_active_power: np.ndarray,
        voltage: np.ndarray,
        scheduled_power: np.ndarray,
        calculated_power: np.ndarray,
        pv_reactive_power: np.ndarray,
        mismatch_norm: float,
        pv_voltage_error: float,
        converged_like: bool,
        branch_from_power: np.ndarray,
        branch_to_power: np.ndarray,
        branch_loading: np.ndarray,
        branch_losses: np.ndarray,
    ) -> None:
        self.pq_active_power: np.ndarray = pq_active_power
        self.pq_reactive_power: np.ndarray = pq_reactive_power
        self.pv_active_power: np.ndarray = pv_active_power
        self.voltage: np.ndarray = voltage
        self.scheduled_power: np.ndarray = scheduled_power
        self.calculated_power: np.ndarray = calculated_power
        self.pv_reactive_power: np.ndarray = pv_reactive_power
        self.mismatch_norm: float = mismatch_norm
        self.pv_voltage_error: float = pv_voltage_error
        self.converged_like: bool = converged_like
        self.branch_from_power: np.ndarray = branch_from_power
        self.branch_to_power: np.ndarray = branch_to_power
        self.branch_loading: np.ndarray = branch_loading
        self.branch_losses: np.ndarray = branch_losses


class MDHEMPVQueryArtifact:
    """
    Store the persistent coefficient artifact and expose absolute-power queries.

    Parameters
    ----------
    ybus:
        Full bus admittance matrix.
    yf:
        Branch-from admittance matrix.
    yt:
        Branch-to admittance matrix.
    slack:
        Slack bus indices.
    pq:
        PQ bus indices.
    pv:
        PV bus indices.
    no_slack:
        Non-slack bus indices.
    slack_voltage:
        Fixed slack voltage vector.
    voltage_setpoint:
        Voltage magnitude targets.
    scheduled_power_germ:
        Scheduled germ power vector.
    scheduled_basis:
        Basis matrix for the absolute-power query variables.
    table:
        Multi-index lookup table.
    u_coefficients:
        Voltage coefficients.
    x_coefficients:
        Reciprocal-voltage coefficients.
    q_coefficients:
        PV reactive-power coefficients.
    dimension_kind_codes:
        Integer codes from :class:`DimensionKind`.
    dimension_bus:
        Full bus index for each dimension.
    dimension_local:
        Local non-slack index for each dimension.
    pq_active_dimension:
        Dimension positions for PQ active-power variables.
    pq_reactive_dimension:
        Dimension positions for PQ reactive-power variables.
    pv_active_dimension:
        Dimension positions for PV active-power variables.
    bus_names:
        Bus names.
    branch_from_indices:
        Branch-from bus indices.
    branch_to_indices:
        Branch-to bus indices.
    branch_rates:
        Branch MVA ratings.
    sbase:
        System base power in MVA.
    """

    __slots__ = (
        "_ybus",
        "_yf",
        "_yt",
        "_slack",
        "_pq",
        "_pv",
        "_no_slack",
        "_slack_voltage",
        "_voltage_setpoint",
        "_scheduled_power_germ",
        "_scheduled_basis",
        "_table",
        "_u_coefficients",
        "_x_coefficients",
        "_q_coefficients",
        "_dimension_kind_codes",
        "_dimension_bus",
        "_dimension_local",
        "_pq_active_dimension",
        "_pq_reactive_dimension",
        "_pv_active_dimension",
        "_bus_names",
        "_branch_from_indices",
        "_branch_to_indices",
        "_branch_rates",
        "_sbase",
    )

    def __init__(
        self,
        ybus: scipy.sparse.csc_matrix,
        yf: scipy.sparse.csc_matrix,
        yt: scipy.sparse.csc_matrix,
        slack: np.ndarray,
        pq: np.ndarray,
        pv: np.ndarray,
        no_slack: np.ndarray,
        slack_voltage: np.ndarray,
        voltage_setpoint: np.ndarray,
        scheduled_power_germ: np.ndarray,
        scheduled_basis: np.ndarray,
        table: MultiIndexTable,
        u_coefficients: np.ndarray,
        x_coefficients: np.ndarray,
        q_coefficients: np.ndarray,
        dimension_kind_codes: np.ndarray,
        dimension_bus: np.ndarray,
        dimension_local: np.ndarray,
        pq_active_dimension: np.ndarray,
        pq_reactive_dimension: np.ndarray,
        pv_active_dimension: np.ndarray,
        bus_names: np.ndarray,
        branch_from_indices: np.ndarray,
        branch_to_indices: np.ndarray,
        branch_rates: np.ndarray,
        sbase: float,
    ) -> None:
        self._ybus: scipy.sparse.csc_matrix = ybus
        self._yf: scipy.sparse.csc_matrix = yf
        self._yt: scipy.sparse.csc_matrix = yt
        self._slack: np.ndarray = slack
        self._pq: np.ndarray = pq
        self._pv: np.ndarray = pv
        self._no_slack: np.ndarray = no_slack
        self._slack_voltage: np.ndarray = slack_voltage
        self._voltage_setpoint: np.ndarray = voltage_setpoint
        self._scheduled_power_germ: np.ndarray = scheduled_power_germ
        self._scheduled_basis: np.ndarray = scheduled_basis
        self._table: MultiIndexTable = table
        self._u_coefficients: np.ndarray = u_coefficients
        self._x_coefficients: np.ndarray = x_coefficients
        self._q_coefficients: np.ndarray = q_coefficients
        self._dimension_kind_codes: np.ndarray = dimension_kind_codes
        self._dimension_bus: np.ndarray = dimension_bus
        self._dimension_local: np.ndarray = dimension_local
        self._pq_active_dimension: np.ndarray = pq_active_dimension
        self._pq_reactive_dimension: np.ndarray = pq_reactive_dimension
        self._pv_active_dimension: np.ndarray = pv_active_dimension
        self._bus_names: np.ndarray = bus_names
        self._branch_from_indices: np.ndarray = branch_from_indices
        self._branch_to_indices: np.ndarray = branch_to_indices
        self._branch_rates: np.ndarray = branch_rates
        self._sbase: float = sbase

    def get_pq_bus_indices(self) -> np.ndarray:
        """
        Get the PQ bus indices.

        Returns
        -------
        numpy.ndarray
            PQ full bus indices.
        """
        return self._pq

    def get_pv_bus_indices(self) -> np.ndarray:
        """
        Get the PV bus indices.

        Returns
        -------
        numpy.ndarray
            PV full bus indices.
        """
        return self._pv

    def get_bus_names(self) -> np.ndarray:
        """
        Get the bus names.

        Returns
        -------
        numpy.ndarray
            Bus names in full bus order.
        """
        return self._bus_names

    def get_max_order(self) -> int:
        """
        Get the maximum total polynomial order.

        Returns
        -------
        int
            Maximum total order.
        """
        return self._table.get_max_order()

    def get_dimensions_count(self) -> int:
        """
        Get the number of embedding dimensions.

        Returns
        -------
        int
            Number of dimensions.
        """
        return int(self._scheduled_basis.shape[0])

    def get_voltage_coefficients(self) -> np.ndarray:
        """
        Get the stored voltage coefficient tensor.

        Returns
        -------
        numpy.ndarray
            Voltage coefficients with shape ``(n_terms, n_no_slack)``.
        """
        return np.asarray(self._u_coefficients, dtype=np.complex128)

    def get_reciprocal_voltage_coefficients(self) -> np.ndarray:
        """
        Get the stored reciprocal-voltage coefficient tensor.

        Returns
        -------
        numpy.ndarray
            Reciprocal-voltage coefficients with shape ``(n_terms, n_no_slack)``.
        """
        return np.asarray(self._x_coefficients, dtype=np.complex128)

    def get_pv_reactive_power_coefficients(self) -> np.ndarray:
        """
        Get the stored PV reactive-power coefficient tensor.

        Returns
        -------
        numpy.ndarray
            PV reactive-power coefficients with shape ``(n_terms, n_pv)``.
        """
        return np.asarray(self._q_coefficients, dtype=np.float64)

    def get_scheduled_basis(self) -> np.ndarray:
        """
        Get the internal scheduled-power basis matrix.

        Returns
        -------
        numpy.ndarray
            Scheduled-power basis with shape ``(n_dims, n_no_slack)``.
        """
        return np.asarray(self._scheduled_basis, dtype=np.complex128)

    def get_multi_index_alphas(self) -> np.ndarray:
        """
        Get the multivariate exponent matrix.

        Returns
        -------
        numpy.ndarray
            Integer exponent matrix with shape ``(n_terms, n_dims)``.
        """
        return np.asarray(self._table.get_alphas_array(), dtype=np.int64)

    def split_sbus_input(self, s_bus: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Split a full complex bus-power vector into artifact query arrays.

        Parameters
        ----------
        s_bus:
            Full complex bus-power vector in per unit.

        Returns
        -------
        tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]
            ``(pq_active_power, pq_reactive_power, pv_active_power)``.
        """
        s_bus_array: np.ndarray = np.asarray(s_bus, dtype=np.complex128)

        if s_bus_array.shape == (self._ybus.shape[0],):
            pq_active_power: np.ndarray = s_bus_array[self._pq].real.copy()
            pq_reactive_power: np.ndarray = s_bus_array[self._pq].imag.copy()
            pv_active_power: np.ndarray = s_bus_array[self._pv].real.copy()
        else:
            raise ValueError("s_bus must match the full bus count")

        return pq_active_power, pq_reactive_power, pv_active_power

    def build_deviation_vector(
        self,
        pq_active_power: np.ndarray,
        pq_reactive_power: np.ndarray,
        pv_active_power: np.ndarray,
    ) -> np.ndarray:
        """
        Convert absolute query powers to the internal deviation variables.

        Parameters
        ----------
        pq_active_power:
            Active powers for the PQ buses in the order returned by
            :meth:`get_pq_bus_indices`.
        pq_reactive_power:
            Reactive powers for the PQ buses in the order returned by
            :meth:`get_pq_bus_indices`.
        pv_active_power:
            Active powers for the PV buses in the order returned by
            :meth:`get_pv_bus_indices`.

        Returns
        -------
        numpy.ndarray
            Internal deviation vector used by the multivariate series.
        """
        # The public API speaks in absolute bus powers because that is how the
        # VeraGrid integration layer naturally thinks about scenarios. The
        # polynomial, however, is built around a germ point, so each input must
        # be translated into the scaled local coordinate used by the series.
        pq_active_array: np.ndarray = np.asarray(pq_active_power, dtype=np.float64)
        pq_reactive_array: np.ndarray = np.asarray(pq_reactive_power, dtype=np.float64)
        pv_active_array: np.ndarray = np.asarray(pv_active_power, dtype=np.float64)
        deviation: np.ndarray = np.zeros(self.get_dimensions_count(), dtype=np.complex128)
        pq_index: int

        if pq_active_array.shape == (self._pq.size,):
            for pq_index in range(self._pq.size):
                # Each PQ active-power dimension uses the difference from the
                # germ power, normalized by the basis scaling stored in the
                # artifact. That is what keeps the polynomial coordinates small
                # even when the physical power values are not.
                dimension_index: int = int(self._pq_active_dimension[pq_index])
                local_index: int = int(self._dimension_local[dimension_index])
                active_reference: float = float(self._scheduled_basis[dimension_index, local_index].real)
                germ_pq_active_power: float = float(self._scheduled_power_germ[int(self._pq[pq_index])].real)
                deviation[dimension_index] = (pq_active_array[pq_index] - germ_pq_active_power) / active_reference
        else:
            raise ValueError("pq_active_power must match the PQ bus count")

        if pq_reactive_array.shape == (self._pq.size,):
            for pq_index in range(self._pq.size):
                # The reactive-power coordinates follow the same logic as the
                # active ones, but their scaling is stored on the imaginary part
                # of the basis row because that is the physical component the
                # corresponding dimension controls.
                dimension_index = int(self._pq_reactive_dimension[pq_index])
                local_index = int(self._dimension_local[dimension_index])
                reactive_reference: float = float(self._scheduled_basis[dimension_index, local_index].imag)
                germ_pq_reactive_power: float = float(self._scheduled_power_germ[int(self._pq[pq_index])].imag)
                deviation[dimension_index] = (pq_reactive_array[pq_index] - germ_pq_reactive_power) / reactive_reference
        else:
            raise ValueError("pq_reactive_power must match the PQ bus count")

        if pv_active_array.shape == (self._pv.size,):
            pv_index: int
            for pv_index in range(self._pv.size):
                # PV buses only expose active power at the query boundary. The
                # missing reactive component is later reconstructed by the Q
                # series when the multivariate polynomial is evaluated.
                dimension_index = int(self._pv_active_dimension[pv_index])
                local_index = int(self._dimension_local[dimension_index])
                pv_active_reference: float = float(self._scheduled_basis[dimension_index, local_index].real)
                germ_pv_active_power: float = float(self._scheduled_power_germ[int(self._pv[pv_index])].real)
                deviation[dimension_index] = (pv_active_array[pv_index] - germ_pv_active_power) / pv_active_reference
        else:
            raise ValueError("pv_active_power must match the PV bus count")

        return deviation

    def evaluate_deviation(self, deviation: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Evaluate the artifact at one internal deviation point.

        Parameters
        ----------
        deviation:
            Internal embedding-variable vector.

        Returns
        -------
        tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]
            Voltage vector, scheduled power vector and PV reactive powers.
        """
        deviation_array: np.ndarray = np.asarray(deviation, dtype=np.complex128)
        expected_shape: tuple[int, ...] = (self.get_dimensions_count(),)

        if deviation_array.shape == expected_shape:
            # The multivariate series is evaluated by the precomputed monomial
            # weights so the online step is a dense dot product instead of a
            # fresh power-flow solve.
            weights: np.ndarray = calculate_monomial_weights_from_table(
                table=self._table,
                values=deviation_array,
            )
            voltage: np.ndarray = np.zeros(self._ybus.shape[0], dtype=np.complex128)
            voltage[self._slack] = extract_slack_voltage_values(
                slack_voltage=self._slack_voltage,
                slack=self._slack,
                nbus=self._ybus.shape[0],
            )
            voltage[self._no_slack] = weights @ self._u_coefficients
            pv_reactive_power: np.ndarray = weights @ self._q_coefficients
            scheduled_power: np.ndarray = self.calculate_scheduled_power(
                deviation=deviation_array,
                pv_reactive_power=pv_reactive_power,
            )
        else:
            raise ValueError("deviation has an unexpected shape")

        return voltage, scheduled_power, pv_reactive_power

    def calculate_scheduled_power(self, deviation: np.ndarray, pv_reactive_power: np.ndarray) -> np.ndarray:
        """
        Rebuild the scheduled complex powers represented by one query point.

        Parameters
        ----------
        deviation:
            Internal embedding-variable vector.
        pv_reactive_power:
            Evaluated PV reactive powers.

        Returns
        -------
        numpy.ndarray
            Full scheduled complex power vector in per unit.
        """
        scheduled_power: np.ndarray = np.array(self._scheduled_power_germ, dtype=np.complex128)
        local_power: np.ndarray = scheduled_power[self._no_slack].copy()
        dimension_index: int

        # Each dimension contributes one physical power component to one bus.
        # The basis row carries the physical scaling of that dimension, while
        # the evaluated deviation carries the scenario-specific coordinate.
        for dimension_index in range(self.get_dimensions_count()):
            local_index: int = int(self._dimension_local[dimension_index])
            local_power[local_index] = local_power[local_index] + (
                deviation[dimension_index] * self._scheduled_basis[dimension_index, local_index]
            )

        scheduled_power[self._no_slack] = local_power
        pv_index: int

        # The PV reactive powers are not direct query inputs. They are instead
        # supplied by the evaluated Q-series so the PV voltage magnitudes stay
        # on their constraint surface.
        for pv_index in range(self._pv.size):
            full_bus_index: int = int(self._pv[pv_index])
            scheduled_power[full_bus_index] = scheduled_power[full_bus_index].real + 1j * pv_reactive_power[pv_index]

        return scheduled_power

    def query(
        self,
        pq_active_power: np.ndarray,
        pq_reactive_power: np.ndarray,
        pv_active_power: np.ndarray,
        tolerance: float,
    ) -> MDHEMQueryResult:
        """
        Query the artifact with absolute PQ and PV power inputs.

        Parameters
        ----------
        pq_active_power:
            Active powers for the PQ buses in per unit.
        pq_reactive_power:
            Reactive powers for the PQ buses in per unit.
        pv_active_power:
            Active powers for the PV buses in per unit.
        tolerance:
            Convergence-like tolerance used for the result flags.

        Returns
        -------
        MDHEMQueryResult
            Query result with voltages, flows and mismatch metrics.
        """
        deviation: np.ndarray = self.build_deviation_vector(
            pq_active_power=pq_active_power,
            pq_reactive_power=pq_reactive_power,
            pv_active_power=pv_active_power,
        )
        voltage: np.ndarray
        scheduled_power: np.ndarray
        pv_reactive_power: np.ndarray
        voltage, scheduled_power, pv_reactive_power = self.evaluate_deviation(deviation=deviation)
        calculated_power: np.ndarray = compute_power_from_ybus(ybus=self._ybus, voltage=voltage)
        mismatch_norm: float = calculate_query_mismatch_norm(
            calculated_power=calculated_power,
            scheduled_power=scheduled_power,
            no_slack=self._no_slack,
            pq=self._pq,
        )
        pv_voltage_error: float = calculate_pv_voltage_error(
            voltage=voltage,
            pv=self._pv,
            voltage_setpoint=self._voltage_setpoint,
        )
        branch_from_power: np.ndarray
        branch_to_power: np.ndarray
        branch_loading: np.ndarray
        branch_losses: np.ndarray
        branch_from_power, branch_to_power, branch_loading, branch_losses = calculate_branch_results(
            voltage=voltage,
            yf=self._yf,
            yt=self._yt,
            branch_from_indices=self._branch_from_indices,
            branch_to_indices=self._branch_to_indices,
            branch_rates=self._branch_rates,
            sbase=self._sbase,
        )
        converged_like: bool = bool(mismatch_norm <= tolerance and pv_voltage_error <= tolerance)

        return MDHEMQueryResult(
            pq_active_power=np.asarray(pq_active_power, dtype=np.float64),
            pq_reactive_power=np.asarray(pq_reactive_power, dtype=np.float64),
            pv_active_power=np.asarray(pv_active_power, dtype=np.float64),
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

    def query_from_sbus(self, s_bus: np.ndarray, tolerance: float) -> MDHEMQueryResult:
        """
        Query the artifact from a full complex bus-power vector.

        Parameters
        ----------
        s_bus:
            Full complex bus-power vector in per unit.
        tolerance:
            Convergence-like tolerance used for the result flags.

        Returns
        -------
        MDHEMQueryResult
            Query result with voltages, flows and mismatch metrics.
        """
        pq_active_power: np.ndarray
        pq_reactive_power: np.ndarray
        pv_active_power: np.ndarray
        pq_active_power, pq_reactive_power, pv_active_power = self.split_sbus_input(s_bus=s_bus)
        return self.query(
            pq_active_power=pq_active_power,
            pq_reactive_power=pq_reactive_power,
            pv_active_power=pv_active_power,
            tolerance=tolerance,
        )

    def validate_grid(self, grid: "MultiCircuit") -> None:
        """
        Validate that a VeraGrid circuit matches the stored artifact layout.

        Parameters
        ----------
        grid:
            VeraGrid circuit to validate.

        Returns
        -------
        None
            The method raises on mismatch.
        """
        bus_names: np.ndarray = np.asarray(grid.get_bus_names(), dtype=str)
        branch_count: int = int(grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True))

        if bus_names.shape == self._bus_names.shape and branch_count == self._branch_from_indices.size:
            if np.array_equal(bus_names, self._bus_names):
                pass
            else:
                raise ValueError("grid bus names do not match the artifact")
        else:
            raise ValueError("grid size does not match the artifact")

    def to_veragrid_power_flow_results(
        self,
        grid: "MultiCircuit",
        query_result: MDHEMQueryResult,
    ) -> "PowerFlowResults":
        """
        Convert one artifact query into a VeraGrid ``PowerFlowResults`` object.

        Parameters
        ----------
        grid:
            VeraGrid circuit associated with the artifact.
        query_result:
            Artifact query result to translate.

        Returns
        -------
        PowerFlowResults
            VeraGrid-like power-flow results object.
        """
        self.validate_grid(grid=grid)
        vg: object
        cf: object
        vg, cf = import_veragrid_engine_modules()
        _ = cf
        from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
        from VeraGridEngine.basic_structures import ConvergenceReport

        numerical_circuit: object = vg.compile_numerical_circuit_at(circuit=grid, t_idx=None)
        branch_from_current: np.ndarray = np.asarray(self._yf @ query_result.voltage, dtype=np.complex128)
        branch_to_current: np.ndarray = np.asarray(self._yt @ query_result.voltage, dtype=np.complex128)
        branch_voltage: np.ndarray = (
            query_result.voltage[self._branch_from_indices] - query_result.voltage[self._branch_to_indices]
        )
        results: PowerFlowResults = PowerFlowResults(
            n=grid.get_bus_number(),
            m=grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
            n_hvdc=grid.get_hvdc_number(),
            n_vsc=grid.get_vsc_number(),
            n_gen=grid.get_generation_like_number(),
            n_batt=grid.get_batteries_number(),
            n_sh=grid.get_shunt_like_device_number(),
            bus_names=grid.get_bus_names(),
            branch_names=grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
            hvdc_names=grid.get_hvdc_names(),
            vsc_names=grid.get_vsc_names(),
            gen_names=grid.get_generation_like_names(),
            batt_names=grid.get_battery_names(),
            sh_names=grid.get_shunt_like_devices_names(),
            bus_types=np.asarray(numerical_circuit.bus_data.bus_types),
        )
        results.voltage = np.asarray(query_result.voltage, dtype=np.complex128)
        results.Sbus = np.asarray(query_result.calculated_power, dtype=np.complex128)
        results.Sf = np.asarray(query_result.branch_from_power, dtype=np.complex128)
        results.St = np.asarray(query_result.branch_to_power, dtype=np.complex128)
        results.If = branch_from_current
        results.It = branch_to_current
        results.Vbranch = branch_voltage
        results.loading = np.asarray(query_result.branch_loading, dtype=np.complex128)
        results.losses = np.asarray(query_result.branch_losses, dtype=np.complex128)
        results.fill_circuit_info(grid=grid)
        report: ConvergenceReport = ConvergenceReport()
        report.add(
            method="MDHEM",
            converged=bool(query_result.converged_like),
            error=float(max(query_result.mismatch_norm, query_result.pv_voltage_error)),
            elapsed=0.0,
            iterations=0,
        )
        results.convergence_reports.append(report)
        return results

    def power_flow(
        self,
        grid: "MultiCircuit",
        pq_active_power: np.ndarray,
        pq_reactive_power: np.ndarray,
        pv_active_power: np.ndarray,
        tolerance: float,
    ) -> "PowerFlowResults":
        """
        Run an artifact-backed power-flow query with a VeraGrid-like result.

        Parameters
        ----------
        grid:
            VeraGrid circuit associated with the artifact.
        pq_active_power:
            Active powers for the PQ buses in per unit.
        pq_reactive_power:
            Reactive powers for the PQ buses in per unit.
        pv_active_power:
            Active powers for the PV buses in per unit.
        tolerance:
            Convergence-like tolerance used for the result flags.

        Returns
        -------
        PowerFlowResults
            VeraGrid-like power-flow results object.
        """
        query_result: MDHEMQueryResult = self.query(
            pq_active_power=pq_active_power,
            pq_reactive_power=pq_reactive_power,
            pv_active_power=pv_active_power,
            tolerance=tolerance,
        )
        return self.to_veragrid_power_flow_results(grid=grid, query_result=query_result)

    def power_flow_from_sbus(
        self,
        grid: "MultiCircuit",
        s_bus: np.ndarray,
        tolerance: float,
    ) -> "PowerFlowResults":
        """
        Run an artifact-backed power-flow query from a full bus-power vector.

        Parameters
        ----------
        grid:
            VeraGrid circuit associated with the artifact.
        s_bus:
            Full complex bus-power vector in per unit.
        tolerance:
            Convergence-like tolerance used for the result flags.

        Returns
        -------
        PowerFlowResults
            VeraGrid-like power-flow results object.
        """
        query_result: MDHEMQueryResult = self.query_from_sbus(s_bus=s_bus, tolerance=tolerance)
        return self.to_veragrid_power_flow_results(grid=grid, query_result=query_result)


def import_veragrid_engine_modules() -> tuple[object, object]:
    """
    Import VeraGridEngine and its common power-flow helpers.

    Returns
    -------
    tuple[object, object]
        ``(VeraGridEngine, common_functions_module)``.
    """
    try:
        import VeraGridEngine as vg
        import VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
    except ModuleNotFoundError:
        # The examples in ``trunk/helm`` are usually executed from the repo root.
        # In that layout the source tree is not installed, so the local ``src``
        # directory is added explicitly for this one script.
        repo_root: Path = Path(__file__).resolve().parents[2]
        src_path: str = str(repo_root / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        else:
            pass
        import VeraGridEngine as vg
        import VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf

    return vg, cf


def convert_full_indices_to_local(full_to_local: np.ndarray, full_indices: np.ndarray) -> np.ndarray:
    """
    Convert full bus indices to local non-slack positions.

    Parameters
    ----------
    full_to_local:
        Full-to-local lookup vector.
    full_indices:
        Full bus indices.

    Returns
    -------
    numpy.ndarray
        Local non-slack positions.
    """
    local_indices: np.ndarray = np.zeros(full_indices.size, dtype=np.int64)
    item_index: int
    for item_index in range(full_indices.size):
        local_indices[item_index] = int(full_to_local[int(full_indices[item_index])])
    return local_indices


def compute_power_from_ybus(ybus: scipy.sparse.csc_matrix, voltage: np.ndarray) -> np.ndarray:
    """
    Compute the bus powers from ``Ybus`` and the complex bus voltages.

    Parameters
    ----------
    ybus:
        Full bus admittance matrix.
    voltage:
        Complex bus voltage vector.

    Returns
    -------
    numpy.ndarray
        Complex bus power vector in per unit.
    """
    return voltage * np.conj(ybus @ voltage)


def calculate_query_mismatch_norm(
    calculated_power: np.ndarray,
    scheduled_power: np.ndarray,
    no_slack: np.ndarray,
    pq: np.ndarray,
) -> float:
    """
    Calculate the infinity norm of the MDHEM query mismatch.

    Parameters
    ----------
    calculated_power:
        Power computed from the queried voltages.
    scheduled_power:
        Scheduled power represented by the query.
    no_slack:
        Non-slack bus indices.
    pq:
        PQ bus indices.

    Returns
    -------
    float
        Infinity norm of ``[dP(no_slack), dQ(pq)]``.
    """
    power_mismatch: np.ndarray = calculated_power[no_slack].real - scheduled_power[no_slack].real
    reactive_mismatch: np.ndarray = calculated_power[pq].imag - scheduled_power[pq].imag
    full_mismatch: np.ndarray = np.concatenate((power_mismatch, reactive_mismatch))
    return float(np.linalg.norm(full_mismatch, np.inf))


def calculate_pv_voltage_error(voltage: np.ndarray, pv: np.ndarray, voltage_setpoint: np.ndarray) -> float:
    """
    Calculate the maximum PV voltage-magnitude error.

    Parameters
    ----------
    voltage:
        Complex bus voltage vector.
    pv:
        PV bus indices.
    voltage_setpoint:
        Voltage magnitude targets.

    Returns
    -------
    float
        Maximum absolute PV voltage-magnitude error.
    """
    if pv.size > 0:
        pv_voltage_error: float = float(np.max(np.abs(np.abs(voltage[pv]) - voltage_setpoint[pv])))
    else:
        pv_voltage_error = 0.0
    return pv_voltage_error


def calculate_branch_results(
    voltage: np.ndarray,
    yf: scipy.sparse.csc_matrix,
    yt: scipy.sparse.csc_matrix,
    branch_from_indices: np.ndarray,
    branch_to_indices: np.ndarray,
    branch_rates: np.ndarray,
    sbase: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate branch flows directly from the stored branch admittance matrices.

    Parameters
    ----------
    voltage:
        Complex bus voltage vector.
    yf:
        Branch-from admittance matrix.
    yt:
        Branch-to admittance matrix.
    branch_from_indices:
        Branch-from bus indices.
    branch_to_indices:
        Branch-to bus indices.
    branch_rates:
        Branch MVA ratings.
    sbase:
        System base power in MVA.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray]
        ``(Sf, St, loading, losses)`` in MVA except ``loading``.
    """
    branch_from_current: np.ndarray = np.asarray(yf @ voltage, dtype=np.complex128)
    branch_to_current: np.ndarray = np.asarray(yt @ voltage, dtype=np.complex128)
    branch_from_voltage: np.ndarray = voltage[branch_from_indices]
    branch_to_voltage: np.ndarray = voltage[branch_to_indices]
    branch_from_power_pu: np.ndarray = branch_from_voltage * np.conj(branch_from_current)
    branch_to_power_pu: np.ndarray = branch_to_voltage * np.conj(branch_to_current)
    branch_from_power: np.ndarray = branch_from_power_pu * sbase
    branch_to_power: np.ndarray = branch_to_power_pu * sbase
    branch_losses: np.ndarray = branch_from_power + branch_to_power
    branch_loading: np.ndarray = branch_from_power / (branch_rates + 1e-9)
    return branch_from_power, branch_to_power, branch_loading, branch_losses


def build_query_basis(
    base_power: np.ndarray,
    pq: np.ndarray,
    pv: np.ndarray,
    no_slack: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build the paper-style query basis ``[PQ_P, PQ_Q, PV_P]``.

    Parameters
    ----------
    base_power:
        Base scheduled complex bus powers in per unit.
    pq:
        PQ bus indices.
    pv:
        PV bus indices.
    no_slack:
        Non-slack bus indices.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray]
        Basis matrix, kind codes, full bus indices, local bus indices and the
        dimension-position lookups for ``PQ_P``, ``PQ_Q`` and ``PV_P``.
    """
    full_to_local: np.ndarray = create_full_to_local_lookup(nbus=int(np.max(no_slack)) + 1, no_slack=no_slack)
    n_dimensions: int = 2 * pq.size + pv.size
    n_no_slack: int = no_slack.size
    basis: np.ndarray = np.zeros((n_dimensions, n_no_slack), dtype=np.complex128)
    dimension_kind_codes: np.ndarray = np.zeros(n_dimensions, dtype=np.int64)
    dimension_bus: np.ndarray = np.zeros(n_dimensions, dtype=np.int64)
    dimension_local: np.ndarray = np.zeros(n_dimensions, dtype=np.int64)
    pq_active_dimension: np.ndarray = np.zeros(pq.size, dtype=np.int64)
    pq_reactive_dimension: np.ndarray = np.zeros(pq.size, dtype=np.int64)
    pv_active_dimension: np.ndarray = np.zeros(pv.size, dtype=np.int64)
    dimension_index: int = 0
    pq_index: int

    # PQ dimensions are scaled with the corresponding base powers so the online
    # series is evaluated in loading-scale coordinates instead of raw power
    # coordinates. Together with the germ subtraction in the query path, that
    # keeps the internal evaluation point close to zero around the base case.
    for pq_index in range(pq.size):
        full_bus: int = int(pq[pq_index])
        local_bus: int = int(full_to_local[full_bus])
        pq_active_reference: float = float(base_power[full_bus].real)
        pq_reactive_reference: float = float(base_power[full_bus].imag)

        if abs(pq_active_reference) > 1.0e-12:
            pass
        else:
            pq_active_reference = 1.0

        if abs(pq_reactive_reference) > 1.0e-12:
            pass
        else:
            pq_reactive_reference = 1.0

        pq_active_dimension[pq_index] = dimension_index
        dimension_kind_codes[dimension_index] = int(DimensionKind.PQ_ACTIVE.value)
        dimension_bus[dimension_index] = full_bus
        dimension_local[dimension_index] = local_bus
        basis[dimension_index, local_bus] = pq_active_reference + 0.0j
        dimension_index = dimension_index + 1

        pq_reactive_dimension[pq_index] = dimension_index
        dimension_kind_codes[dimension_index] = int(DimensionKind.PQ_REACTIVE.value)
        dimension_bus[dimension_index] = full_bus
        dimension_local[dimension_index] = local_bus
        basis[dimension_index, local_bus] = 1j * pq_reactive_reference
        dimension_index = dimension_index + 1

    pv_index: int

    # PV active powers are queried as absolute values too, but the embedded
    # variable represents a scaled delta around the physical germ.
    for pv_index in range(pv.size):
        full_bus = int(pv[pv_index])
        local_bus = int(full_to_local[full_bus])
        pv_active_reference: float = float(base_power[full_bus].real)

        if abs(pv_active_reference) > 1.0e-12:
            pass
        else:
            pv_active_reference = 1.0

        pv_active_dimension[pv_index] = dimension_index
        dimension_kind_codes[dimension_index] = int(DimensionKind.PV_ACTIVE.value)
        dimension_bus[dimension_index] = full_bus
        dimension_local[dimension_index] = local_bus
        basis[dimension_index, local_bus] = pv_active_reference + 0.0j
        dimension_index = dimension_index + 1

    return (
        basis,
        dimension_kind_codes,
        dimension_bus,
        dimension_local,
        pq_active_dimension,
        pq_reactive_dimension,
        pv_active_dimension,
    )


def create_empty_dimension_position_array(length: int) -> np.ndarray:
    """
    Create one explicit "not present" dimension-position array.

    Parameters
    ----------
    length:
        Target array length.

    Returns
    -------
    numpy.ndarray
        Integer array filled with ``-1``.
    """
    return -np.ones(length, dtype=np.int64)


def build_subset_query_basis(
    basis: np.ndarray,
    dimension_kind_codes: np.ndarray,
    dimension_bus: np.ndarray,
    dimension_local: np.ndarray,
    pq_active_dimension: np.ndarray,
    pq_reactive_dimension: np.ndarray,
    pv_active_dimension: np.ndarray,
    selected_dimension_indices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build one subset query basis from the full ``[PQ_P, PQ_Q, PV_P]`` basis.

    Parameters
    ----------
    basis:
        Full query basis.
    dimension_kind_codes:
        Full dimension kind codes.
    dimension_bus:
        Full dimension bus indices.
    dimension_local:
        Full dimension local indices.
    pq_active_dimension:
        Full PQ active-power dimension map.
    pq_reactive_dimension:
        Full PQ reactive-power dimension map.
    pv_active_dimension:
        Full PV active-power dimension map.
    selected_dimension_indices:
        Selected full-dimension indices kept in the subset basis.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray]
        Subset basis and its metadata arrays.
    """
    selected_array: np.ndarray = np.asarray(selected_dimension_indices, dtype=np.int64)
    subset_basis: np.ndarray = np.asarray(basis[selected_array, :], dtype=np.complex128)
    subset_kind_codes: np.ndarray = np.asarray(dimension_kind_codes[selected_array], dtype=np.int64)
    subset_dimension_bus: np.ndarray = np.asarray(dimension_bus[selected_array], dtype=np.int64)
    subset_dimension_local: np.ndarray = np.asarray(dimension_local[selected_array], dtype=np.int64)
    subset_pq_active_dimension: np.ndarray = create_empty_dimension_position_array(pq_active_dimension.size)
    subset_pq_reactive_dimension: np.ndarray = create_empty_dimension_position_array(pq_reactive_dimension.size)
    subset_pv_active_dimension: np.ndarray = create_empty_dimension_position_array(pv_active_dimension.size)
    subset_lookup: np.ndarray = create_empty_dimension_position_array(basis.shape[0])
    subset_index: int

    # The lookup translates one full query dimension into its new compact
    # position. That lets the compressed artifact reuse the same metadata shape
    # as the full artifact without carrying absent dimensions ambiguously.
    for subset_index in range(selected_array.size):
        subset_lookup[int(selected_array[subset_index])] = subset_index

    pq_index: int
    for pq_index in range(pq_active_dimension.size):
        full_dimension: int = int(pq_active_dimension[pq_index])
        subset_pq_active_dimension[pq_index] = int(subset_lookup[full_dimension])

    for pq_index in range(pq_reactive_dimension.size):
        full_dimension = int(pq_reactive_dimension[pq_index])
        subset_pq_reactive_dimension[pq_index] = int(subset_lookup[full_dimension])

    pv_index: int
    for pv_index in range(pv_active_dimension.size):
        full_dimension = int(pv_active_dimension[pv_index])
        subset_pv_active_dimension[pv_index] = int(subset_lookup[full_dimension])

    return (
        subset_basis,
        subset_kind_codes,
        subset_dimension_bus,
        subset_dimension_local,
        subset_pq_active_dimension,
        subset_pq_reactive_dimension,
        subset_pv_active_dimension,
    )


def build_order1_term_position_lookup(table: MultiIndexTable, dims: int) -> np.ndarray:
    """
    Build the coefficient-row position of each first-order dimension.

    Parameters
    ----------
    table:
        Multi-index table with at least first order.
    dims:
        Number of embedding dimensions.

    Returns
    -------
    numpy.ndarray
        Lookup from dimension index to coefficient-row position.
    """
    order1_positions: np.ndarray = create_empty_dimension_position_array(dims)
    order1_start: int = table.get_order_start(1)
    order1_stop: int = table.get_order_stop(1)
    position: int

    # Order-1 rows are one-hot multi-indices. Reading the stored active
    # dimension is enough to recover which embedding variable each row belongs
    # to, without reconstructing the dense exponent table.
    for position in range(order1_start, order1_stop):
        active_dims: np.ndarray = table.get_active_dimension_positions(position)
        dimension_index: int = int(active_dims[0])
        order1_positions[dimension_index] = position

    return order1_positions


def calculate_dimension_scores_from_linear_artifact(
    artifact: MDHEMPVQueryArtifact,
    reactive_weight: float,
) -> np.ndarray:
    """
    Score the full query dimensions by their first-order response magnitude.

    Parameters
    ----------
    artifact:
        Full query artifact solved only to first order.
    reactive_weight:
        Relative weight applied to the PV reactive-power sensitivity.

    Returns
    -------
    numpy.ndarray
        Non-negative per-dimension scores.
    """
    dims: int = artifact.get_dimensions_count()
    order1_positions: np.ndarray = build_order1_term_position_lookup(table=artifact._table, dims=dims)
    scores: np.ndarray = np.zeros(dims, dtype=np.float64)
    dimension_index: int

    # The compressed quadratic stage should spend its dimensions where the
    # first-order map already says the network is most sensitive. That is the
    # smallest defensible heuristic before introducing heavier basis learning.
    for dimension_index in range(dims):
        position: int = int(order1_positions[dimension_index])
        voltage_score: float = float(np.sum(np.abs(artifact._u_coefficients[position, :]) ** 2))
        reactive_score: float

        if artifact._q_coefficients.shape[1] > 0:
            reactive_score = float(np.sum(np.abs(artifact._q_coefficients[position, :]) ** 2))
        else:
            reactive_score = 0.0

        scores[dimension_index] = voltage_score + reactive_weight * reactive_score

    return scores


def select_top_dimensions(scores: np.ndarray, retained_dimensions: int) -> np.ndarray:
    """
    Select the highest-scoring embedding dimensions.

    Parameters
    ----------
    scores:
        Per-dimension scores.
    retained_dimensions:
        Requested number of retained dimensions.

    Returns
    -------
    numpy.ndarray
        Sorted full-dimension indices kept by the compressed artifact.
    """
    score_array: np.ndarray = np.asarray(scores, dtype=np.float64)
    available_dimensions: int = score_array.size

    if retained_dimensions > 0:
        kept_dimensions: int = min(retained_dimensions, available_dimensions)
    else:
        raise ValueError("retained_dimensions must be positive")

    sorted_indices: np.ndarray = np.argsort(score_array)[::-1]
    selected_indices: np.ndarray = np.asarray(sorted_indices[0:kept_dimensions], dtype=np.int64)
    selected_indices.sort()
    return selected_indices


def select_top_dimensions_balanced(
    scores: np.ndarray,
    dimension_kind_codes: np.ndarray,
    retained_dimensions: int,
) -> np.ndarray:
    """
    Select high-scoring dimensions while preserving input-kind coverage.

    Parameters
    ----------
    scores:
        Per-dimension scores.
    dimension_kind_codes:
        Per-dimension kind codes.
    retained_dimensions:
        Requested retained dimension count.

    Returns
    -------
    numpy.ndarray
        Sorted retained dimension indices.
    """
    score_array: np.ndarray = np.asarray(scores, dtype=np.float64)
    kind_array: np.ndarray = np.asarray(dimension_kind_codes, dtype=np.int64)
    available_dimensions: int = score_array.size

    if retained_dimensions > 0:
        kept_dimensions: int = min(retained_dimensions, available_dimensions)
    else:
        raise ValueError("retained_dimensions must be positive")

    kind_codes: np.ndarray = np.asarray(
        [
            int(DimensionKind.PQ_ACTIVE.value),
            int(DimensionKind.PQ_REACTIVE.value),
            int(DimensionKind.PV_ACTIVE.value),
        ],
        dtype=np.int64,
    )
    present_mask: np.ndarray = np.zeros(kind_codes.size, dtype=bool)
    kind_index: int
    for kind_index in range(kind_codes.size):
        present_mask[kind_index] = bool(np.any(kind_array == int(kind_codes[kind_index])))

    present_kind_count: int = int(np.count_nonzero(present_mask))
    selected_mask: np.ndarray = np.zeros(available_dimensions, dtype=bool)

    if present_kind_count > 0:
        base_quota: int = kept_dimensions // present_kind_count
        remainder: int = kept_dimensions % present_kind_count
        carried_slots: int = 0

        # The first pass guarantees that every present query kind contributes
        # some retained quadratic variables before the remaining slots go to
        # the globally strongest responses.
        for kind_index in range(kind_codes.size):
            if present_mask[kind_index]:
                target_count: int = base_quota
                if remainder > 0:
                    target_count = target_count + 1
                    remainder = remainder - 1
                else:
                    target_count = target_count

                candidate_indices: np.ndarray = np.where(kind_array == int(kind_codes[kind_index]))[0]
                candidate_scores: np.ndarray = score_array[candidate_indices]
                candidate_order: np.ndarray = np.argsort(candidate_scores)[::-1]
                actual_count: int = min(target_count, candidate_indices.size)
                carried_slots = carried_slots + (target_count - actual_count)
                candidate_position: int
                for candidate_position in range(actual_count):
                    selected_mask[int(candidate_indices[int(candidate_order[candidate_position])])] = True
            else:
                pass

        selected_count: int = int(np.count_nonzero(selected_mask))
        remaining_count: int = kept_dimensions - selected_count + carried_slots
    else:
        remaining_count = kept_dimensions

    if remaining_count > 0:
        global_order: np.ndarray = np.argsort(score_array)[::-1]
        global_position: int = 0
        while global_position < global_order.size and remaining_count > 0:
            dimension_index: int = int(global_order[global_position])
            if selected_mask[dimension_index]:
                pass
            else:
                selected_mask[dimension_index] = True
                remaining_count = remaining_count - 1
            global_position = global_position + 1
    else:
        pass

    selected_indices: np.ndarray = np.where(selected_mask)[0].astype(np.int64)
    selected_indices.sort()
    return selected_indices


def format_query_dimension_name(kind_code: int, bus_name: str) -> str:
    """
    Format one human-readable query dimension label.

    Parameters
    ----------
    kind_code:
        Stored :class:`DimensionKind` integer code.
    bus_name:
        Bus name associated with the dimension.

    Returns
    -------
    str
        Human-readable dimension label.
    """
    if kind_code == int(DimensionKind.PQ_ACTIVE.value):
        return f"PQ_P:{bus_name}"
    else:
        if kind_code == int(DimensionKind.PQ_REACTIVE.value):
            return f"PQ_Q:{bus_name}"
        else:
            if kind_code == int(DimensionKind.PV_ACTIVE.value):
                return f"PV_P:{bus_name}"
            else:
                raise ValueError(f"Unsupported dimension kind code {kind_code}")


def create_selected_dimension_names(
    bus_names: np.ndarray,
    dimension_kind_codes: np.ndarray,
    dimension_bus: np.ndarray,
    selected_dimension_indices: np.ndarray,
) -> np.ndarray:
    """
    Create labels for the retained compressed-query dimensions.

    Parameters
    ----------
    bus_names:
        Full bus names.
    dimension_kind_codes:
        Full dimension kind codes.
    dimension_bus:
        Full dimension bus indices.
    selected_dimension_indices:
        Retained full query dimensions.

    Returns
    -------
    numpy.ndarray
        String labels for the retained dimensions.
    """
    selected_array: np.ndarray = np.asarray(selected_dimension_indices, dtype=np.int64)
    names: np.ndarray = np.empty(selected_array.size, dtype=object)
    item_index: int

    for item_index in range(selected_array.size):
        dimension_index: int = int(selected_array[item_index])
        kind_code: int = int(dimension_kind_codes[dimension_index])
        bus_index: int = int(dimension_bus[dimension_index])
        names[item_index] = format_query_dimension_name(
            kind_code=kind_code,
            bus_name=str(bus_names[bus_index]),
        )

    return np.asarray(names, dtype=str)


def extract_slack_voltage_values(slack_voltage: np.ndarray, slack: np.ndarray, nbus: int) -> np.ndarray:
    """
    Extract slack-bus voltage values from either supported storage layout.

    Parameters
    ----------
    slack_voltage:
        Stored slack-voltage data. It may contain one value per bus or one
        value per slack bus.
    slack:
        Slack bus indices.
    nbus:
        Total number of buses.

    Returns
    -------
    numpy.ndarray
        Complex voltage values for the slack buses only.
    """
    slack_voltage_array: np.ndarray = np.asarray(slack_voltage, dtype=np.complex128)

    if slack_voltage_array.shape == (slack.size,):
        return slack_voltage_array
    else:
        if slack_voltage_array.shape == (nbus,):
            return slack_voltage_array[slack]
        else:
            raise ValueError("slack_voltage has an unexpected shape")


def solve_initial_passive_voltage(
    ybus: scipy.sparse.csc_matrix,
    slack: np.ndarray,
    no_slack: np.ndarray,
    slack_voltage: np.ndarray,
) -> np.ndarray:
    """
    Solve the passive zero-injection network used to initialize the germ.

    Parameters
    ----------
    ybus:
        Full bus admittance matrix.
    slack:
        Slack bus indices.
    no_slack:
        Non-slack bus indices.
    slack_voltage:
        Full slack-voltage vector.

    Returns
    -------
    numpy.ndarray
        Initial complex voltage vector.
    """
    slack_voltage_values: np.ndarray = extract_slack_voltage_values(
        slack_voltage=slack_voltage,
        slack=slack,
        nbus=ybus.shape[0],
    )
    voltage_guess: np.ndarray = np.zeros(ybus.shape[0], dtype=np.complex128)
    voltage_guess[slack] = slack_voltage_values
    reduced_ybus: scipy.sparse.csc_matrix = ybus[np.ix_(no_slack, no_slack)].tocsc()
    slack_coupling: scipy.sparse.csc_matrix = ybus[np.ix_(no_slack, slack)].tocsc()
    rhs: np.ndarray = -np.asarray(slack_coupling @ slack_voltage_values, dtype=np.complex128)
    voltage_guess[no_slack] = scipy.sparse.linalg.spsolve(reduced_ybus, rhs)
    return voltage_guess


def assemble_germ_voltage_from_state(state: np.ndarray, context: PhysicalGermContext) -> tuple[np.ndarray, np.ndarray]:
    """
    Reconstruct the complex germ voltage vector from the nonlinear state vector.

    Parameters
    ----------
    state:
        Nonlinear state vector.
    context:
        Physical-germ context.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        Full voltage vector and PV reactive powers.
    """
    n_no_slack: int = context.no_slack.size
    n_pq: int = context.pq.size
    n_pv: int = context.pv.size
    voltage: np.ndarray = np.zeros(context.ybus.shape[0], dtype=np.complex128)
    voltage[context.slack] = extract_slack_voltage_values(
        slack_voltage=context.slack_voltage,
        slack=context.slack,
        nbus=context.ybus.shape[0],
    )

    angle_vector: np.ndarray = state[0:n_no_slack]
    pq_magnitude_vector: np.ndarray = state[n_no_slack:n_no_slack + n_pq]
    pv_reactive_power: np.ndarray = state[n_no_slack + n_pq:n_no_slack + n_pq + n_pv]
    local_index: int

    # The state uses polar variables because that makes the PV magnitude
    # constraints explicit and keeps the unknown count minimal.
    for local_index in range(n_no_slack):
        full_index: int = int(context.no_slack[local_index])
        angle: float = float(angle_vector[local_index])
        magnitude: float

        pq_position: int = int(context.full_to_pq_position[full_index])
        if pq_position >= 0:
            magnitude = float(pq_magnitude_vector[pq_position])
        else:
            magnitude = float(context.voltage_setpoint[full_index])

        voltage[full_index] = magnitude * np.exp(1j * angle)

    return voltage, pv_reactive_power


def evaluate_physical_germ_residual(state: np.ndarray, context: PhysicalGermContext) -> np.ndarray:
    """
    Evaluate the physical-germ nonlinear equations.

    Parameters
    ----------
    state:
        Nonlinear state vector.
    context:
        Physical-germ context.

    Returns
    -------
    numpy.ndarray
        Residual vector.
    """
    voltage: np.ndarray
    pv_reactive_power: np.ndarray
    voltage, pv_reactive_power = assemble_germ_voltage_from_state(state=state, context=context)
    scheduled_power: np.ndarray = np.zeros(context.ybus.shape[0], dtype=np.complex128)
    scheduled_power[context.pv] = context.pv_active_power + 1j * pv_reactive_power
    calculated_power: np.ndarray = compute_power_from_ybus(ybus=context.ybus, voltage=voltage)
    power_residual: np.ndarray = calculated_power[context.no_slack].real - scheduled_power[context.no_slack].real
    reactive_residual: np.ndarray = calculated_power[context.pq].imag - scheduled_power[context.pq].imag
    voltage_residual: np.ndarray = np.abs(voltage[context.pv]) - context.voltage_setpoint[context.pv]
    residual: np.ndarray = np.concatenate((power_residual, reactive_residual, voltage_residual))
    return residual


def build_initial_germ_state(
    passive_voltage: np.ndarray,
    pq: np.ndarray,
    pv: np.ndarray,
    no_slack: np.ndarray,
    base_power: np.ndarray,
) -> np.ndarray:
    """
    Build the initial nonlinear state vector for the physical germ.

    Parameters
    ----------
    passive_voltage:
        Passive-network initial voltage vector.
    pq:
        PQ bus indices.
    pv:
        PV bus indices.
    no_slack:
        Non-slack bus indices.
    base_power:
        Original scheduled complex bus powers.

    Returns
    -------
    numpy.ndarray
        Initial state vector.
    """
    angle_guess: np.ndarray = np.angle(passive_voltage[no_slack])
    pq_magnitude_guess: np.ndarray = np.abs(passive_voltage[pq])
    # The passive zero-injection network is the start of the continuation path,
    # so the PV reactive-power guess starts at zero instead of the final-case
    # dispatch.
    pv_reactive_guess: np.ndarray = np.zeros(pv.size, dtype=np.float64)
    state_guess: np.ndarray = np.concatenate((angle_guess, pq_magnitude_guess, pv_reactive_guess))
    return state_guess


def solve_physical_germ_step(state_guess: np.ndarray, context: PhysicalGermContext) -> scipy.optimize.OptimizeResult:
    """
    Solve one continuation step of the physical-germ equations.

    Parameters
    ----------
    state_guess:
        Initial state vector for the step.
    context:
        Physical-germ context at the current continuation point.

    Returns
    -------
    scipy.optimize.OptimizeResult
        Nonlinear solve result.
    """
    # ``hybr`` is fast when the step is already close. ``lm`` is slower but
    # more forgiving, so it is only used as a fallback.
    root_result: scipy.optimize.OptimizeResult = scipy.optimize.root(
        fun=evaluate_physical_germ_residual,
        x0=state_guess,
        args=(context,),
        method="hybr",
        tol=1e-12,
    )

    if root_result.success:
        return root_result

    root_result = scipy.optimize.root(
        fun=evaluate_physical_germ_residual,
        x0=state_guess,
        args=(context,),
        method="lm",
        tol=1e-12,
    )
    return root_result


def solve_physical_germ(
    grid: "MultiCircuit",
    case_data: VeraGridQueryCaseData,
    germ_seed_results: Optional["PowerFlowResults"],
) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Solve the practical artifact germ for the given case.

    The paper-style zero-PQ continuation was producing a mathematically valid
    but numerically useless branch on case14, with PV reactive powers around
    ``1e10`` at zero order. The artifact is queried around the original case,
    so the robust choice is to use a physically meaningful operating point as
    the germ and expand local deltas around it. By default that operating point
    is obtained internally with VeraGrid HELM. If the caller provides a
    converged ``PowerFlowResults`` object, that operating point is used
    instead.

    :param grid:
        VeraGrid circuit used by the internal HELM solve when no external seed
        is provided.
    :param case_data:
        VeraGrid network data.
    :param germ_seed_results:
        Optional converged VeraGrid power-flow result used as the artifact
        germ. When ``None``, the germ is obtained internally with VeraGrid
        HELM.
    :return:
        Germ voltage, germ scheduled power and residual norm.
    """
    power_flow_results: object

    if germ_seed_results is None:
        # The default path keeps artifact training HELM-only. No Newton-Raphson
        # enters the artifact construction unless the caller explicitly injects
        # an external seed result.
        vg: object
        cf: object
        vg, cf = import_veragrid_engine_modules()
        _ = cf
        power_flow_options: object = vg.PowerFlowOptions(
            solver_type=vg.SolverType.HELM,
            retry_with_other_methods=False,
            control_q=True,
            control_taps_phase=False,
            control_taps_modules=False,
            apply_temperature_correction=False,
            use_stored_guess=False,
            tolerance=1e-10,
        )
        power_flow_results = vg.power_flow(
            grid=grid,
            options=power_flow_options,
        )
    else:
        # This optional input is the only sanctioned path to center the
        # artifact around an externally computed solution such as NR.
        power_flow_results = germ_seed_results

    if bool(power_flow_results.converged):
        voltage_shape: tuple[int, ...] = (case_data.ybus.shape[0],)

        if np.asarray(power_flow_results.voltage).shape == voltage_shape:
            # The artifact stores the operating point as voltage plus the
            # corresponding power implied by the artifact admittance matrix.
            # Recomputing the power here keeps the internal state independent
            # from the exact source of the seed result.
            germ_voltage: np.ndarray = np.asarray(power_flow_results.voltage, dtype=np.complex128)
            germ_power: np.ndarray = compute_power_from_ybus(ybus=case_data.ybus, voltage=germ_voltage)
            germ_error: float = float(power_flow_results.error)
        else:
            raise ValueError("germ_seed_results voltage shape does not match the case bus count")
    else:
        # The failure text stays neutral because the seed may come either from
        # the internal HELM path or from an explicitly supplied external
        # ``PowerFlowResults`` object such as a Newton-Raphson solution.
        raise RuntimeError(f"Artifact germ seed solve failed with error {float(power_flow_results.error):.6e}")

    return germ_voltage, germ_power, germ_error


def solve_mdhelm_query_artifact(
    input_data: VeraGridQueryCaseData,
    germ_voltage: np.ndarray,
    germ_power: np.ndarray,
    max_order: int,
) -> MDHEMPVQueryArtifact:
    """
    Solve the MDHEM coefficients for the persistent query artifact.

    Parameters
    ----------
    input_data:
        VeraGrid network data.
    germ_voltage:
        Physical-germ voltage vector.
    germ_power:
        Physical-germ scheduled power vector.
    max_order:
        Maximum total polynomial order.

    Returns
    -------
    MDHEMPVQueryArtifact
        Persistent query artifact.
    """
    basis: np.ndarray
    dimension_kind_codes: np.ndarray
    dimension_bus: np.ndarray
    dimension_local: np.ndarray
    pq_active_dimension: np.ndarray
    pq_reactive_dimension: np.ndarray
    pv_active_dimension: np.ndarray
    basis, dimension_kind_codes, dimension_bus, dimension_local, pq_active_dimension, pq_reactive_dimension, pv_active_dimension = build_query_basis(
        base_power=input_data.base_power,
        pq=input_data.pq,
        pv=input_data.pv,
        no_slack=input_data.no_slack,
    )
    return solve_mdhelm_query_artifact_from_basis(
        input_data=input_data,
        germ_voltage=germ_voltage,
        germ_power=germ_power,
        basis=basis,
        dimension_kind_codes=dimension_kind_codes,
        dimension_bus=dimension_bus,
        dimension_local=dimension_local,
        pq_active_dimension=pq_active_dimension,
        pq_reactive_dimension=pq_reactive_dimension,
        pv_active_dimension=pv_active_dimension,
        max_order=max_order,
    )


def solve_mdhelm_query_artifact_from_basis(
    input_data: VeraGridQueryCaseData,
    germ_voltage: np.ndarray,
    germ_power: np.ndarray,
    basis: np.ndarray,
    dimension_kind_codes: np.ndarray,
    dimension_bus: np.ndarray,
    dimension_local: np.ndarray,
    pq_active_dimension: np.ndarray,
    pq_reactive_dimension: np.ndarray,
    pv_active_dimension: np.ndarray,
    max_order: int,
) -> MDHEMPVQueryArtifact:
    """
    Solve one MDHEM artifact for an explicitly supplied scheduled-power basis.

    Parameters
    ----------
    input_data:
        VeraGrid network data.
    germ_voltage:
        Physical-germ voltage vector.
    germ_power:
        Physical-germ scheduled power vector.
    basis:
        Scheduled-power basis in local non-slack order.
    dimension_kind_codes:
        Integer kind code of each basis row.
    dimension_bus:
        Full bus index of each basis row.
    dimension_local:
        Local non-slack index of each basis row.
    pq_active_dimension:
        PQ active-power dimension lookup.
    pq_reactive_dimension:
        PQ reactive-power dimension lookup.
    pv_active_dimension:
        PV active-power dimension lookup.
    max_order:
        Maximum total polynomial order.

    Returns
    -------
    MDHEMPVQueryArtifact
        Built MDHEM artifact.
    """
    n_no_slack: int = input_data.no_slack.size
    n_pv: int = input_data.pv.size
    voltage_setpoint: np.ndarray = np.asarray(input_data.voltage_setpoint, dtype=np.float64).copy()

    # The artifact is a local expansion around the chosen germ. Storing the PV
    # targets from that exact germ keeps the convergence-like voltage check
    # aligned with the surface actually represented by the coefficients,
    # especially on large public cases where the imported setpoint vector and
    # the solved operating point are not numerically identical.
    if input_data.pv.size > 0:
        voltage_setpoint[input_data.pv] = np.abs(germ_voltage[input_data.pv])
    else:
        pass

    table: MultiIndexTable = create_multi_index_table(dims=basis.shape[0], max_order=max_order)
    n_terms: int = table.get_terms_count()
    u_coefficients: np.ndarray = np.zeros((n_terms, n_no_slack), dtype=np.complex128)
    x_coefficients: np.ndarray = np.zeros((n_terms, n_no_slack), dtype=np.complex128)
    q_coefficients: np.ndarray = np.zeros((n_terms, n_pv), dtype=np.float64)
    pv_local: np.ndarray = convert_full_indices_to_local(
        full_to_local=create_full_to_local_lookup(nbus=input_data.ybus.shape[0], no_slack=input_data.no_slack),
        full_indices=input_data.pv,
    )
    yred: scipy.sparse.csc_matrix = input_data.ybus[np.ix_(input_data.no_slack, input_data.no_slack)].tocsc()
    u_zero: np.ndarray = germ_voltage[input_data.no_slack].copy()
    x_zero: np.ndarray = 1.0 / np.conj(u_zero)
    c_germ: np.ndarray = np.conj(germ_power[input_data.no_slack])
    basis_conjugate: np.ndarray = np.conj(basis)
    zero_position: int = 0
    u_coefficients[zero_position, :] = u_zero
    x_coefficients[zero_position, :] = x_zero
    pv_index: int

    # The zero-order PV reactive powers come from the physical germ, because
    # that is the point where the multivariate expansion starts.
    for pv_index in range(n_pv):
        q_coefficients[zero_position, pv_index] = germ_power[int(input_data.pv[pv_index])].imag

    system_matrix: scipy.sparse.csc_matrix = build_system_matrix(
        yred=yred,
        c_germ=c_germ,
        u_zero=u_zero,
        x_zero=x_zero,
        pv_local=pv_local,
    )
    linear_solver: SparseLinearSolver = SparseLinearSolver(
        factorization=scipy.sparse.linalg.splu(system_matrix)
    )
    unknown_count: int = 4 * n_no_slack + n_pv
    rhs_block_columns: int = determine_rhs_block_columns(
        unknown_count=unknown_count,
        target_block_bytes=64 * 1024 * 1024,
    )
    order_index: int

    # Each coefficient uses the same constant sparse matrix, while only the
    # right-hand side changes through the multivariate convolutions.
    for order_index in range(1, max_order + 1):
        order_start: int = table.get_order_start(order_index)
        order_stop: int = table.get_order_stop(order_index)
        block_start: int = order_start

        while block_start < order_stop:
            block_stop: int = min(order_stop, block_start + rhs_block_columns)
            block_size: int = block_stop - block_start
            rhs_block: np.ndarray = np.zeros((unknown_count, block_size), dtype=np.float64)
            block_offset: int

            for block_offset in range(block_size):
                position: int = block_start + block_offset
                active_dims_row: np.ndarray = table.get_active_dimension_positions(position)
                minus_e_previous_row: np.ndarray = table.get_minus_e_previous_positions(position)
                qx_known: np.ndarray = calculate_known_qx_convolution(
                    table=table,
                    position=position,
                    q_coefficients=q_coefficients,
                    x_coefficients=x_coefficients,
                    pv_local=pv_local,
                )
                rhs_power: np.ndarray = calculate_rhs_power_numba(
                    active_dims_row=active_dims_row,
                    minus_e_previous_row=minus_e_previous_row,
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

    return MDHEMPVQueryArtifact(
        ybus=input_data.ybus,
        yf=input_data.yf,
        yt=input_data.yt,
        slack=input_data.slack,
        pq=input_data.pq,
        pv=input_data.pv,
        no_slack=input_data.no_slack,
        slack_voltage=input_data.slack_voltage,
        voltage_setpoint=voltage_setpoint,
        scheduled_power_germ=germ_power,
        scheduled_basis=basis,
        table=table,
        u_coefficients=u_coefficients,
        x_coefficients=x_coefficients,
        q_coefficients=q_coefficients,
        dimension_kind_codes=dimension_kind_codes,
        dimension_bus=dimension_bus,
        dimension_local=dimension_local,
        pq_active_dimension=pq_active_dimension,
        pq_reactive_dimension=pq_reactive_dimension,
        pv_active_dimension=pv_active_dimension,
        bus_names=input_data.bus_names,
        branch_from_indices=input_data.branch_from_indices,
        branch_to_indices=input_data.branch_to_indices,
        branch_rates=input_data.branch_rates,
        sbase=input_data.sbase,
    )


def evaluate_artifact_higher_order_terms(
    artifact: MDHEMPVQueryArtifact,
    deviation: np.ndarray,
    minimum_order: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Evaluate only the higher-order voltage and PV-Q contributions.

    Parameters
    ----------
    artifact:
        Artifact to evaluate.
    deviation:
        Internal deviation coordinates of the artifact.
    minimum_order:
        First total order that must be included in the returned sum.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        Local non-slack voltage contribution and PV reactive-power
        contribution.
    """
    if minimum_order <= artifact._table.get_max_order():
        weights: np.ndarray = calculate_monomial_weights_from_table(
            table=artifact._table,
            values=np.asarray(deviation, dtype=np.complex128),
        )
        start: int = artifact._table.get_order_start(minimum_order)
        voltage_contribution: np.ndarray = weights[start:] @ artifact._u_coefficients[start:, :]
        reactive_contribution: np.ndarray = weights[start:] @ artifact._q_coefficients[start:, :]
    else:
        voltage_contribution = np.zeros(artifact._no_slack.size, dtype=np.complex128)
        reactive_contribution = np.zeros(artifact._pv.size, dtype=np.float64)

    return voltage_contribution, reactive_contribution


class MDHEMOrder2CompressedArtifact:
    """
    Store the exact linear map plus a compressed quadratic correction.

    Parameters
    ----------
    linear_artifact:
        Full per-bus query artifact solved to first order.
    quadratic_artifact:
        Reduced query artifact solved to second order on the retained
        dimensions only.
    selected_dimension_indices:
        Full query dimension indices retained by the quadratic stage.
    selected_dimension_scores:
        First-order sensitivity scores of the retained dimensions.
    selected_dimension_names:
        Human-readable labels of the retained dimensions.
    """

    __slots__ = (
        "_linear_artifact",
        "_quadratic_artifact",
        "_selected_dimension_indices",
        "_selected_dimension_scores",
        "_selected_dimension_names",
    )

    def __init__(
        self,
        linear_artifact: MDHEMPVQueryArtifact,
        quadratic_artifact: MDHEMPVQueryArtifact,
        selected_dimension_indices: np.ndarray,
        selected_dimension_scores: np.ndarray,
        selected_dimension_names: np.ndarray,
    ) -> None:
        self._linear_artifact: MDHEMPVQueryArtifact = linear_artifact
        self._quadratic_artifact: MDHEMPVQueryArtifact = quadratic_artifact
        self._selected_dimension_indices: np.ndarray = np.asarray(selected_dimension_indices, dtype=np.int64)
        self._selected_dimension_scores: np.ndarray = np.asarray(selected_dimension_scores, dtype=np.float64)
        self._selected_dimension_names: np.ndarray = np.asarray(selected_dimension_names, dtype=str)

    def get_pq_bus_indices(self) -> np.ndarray:
        """
        Get the PQ bus indices.

        Returns
        -------
        numpy.ndarray
            PQ full bus indices.
        """
        return self._linear_artifact.get_pq_bus_indices()

    def get_pv_bus_indices(self) -> np.ndarray:
        """
        Get the PV bus indices.

        Returns
        -------
        numpy.ndarray
            PV full bus indices.
        """
        return self._linear_artifact.get_pv_bus_indices()

    def get_bus_names(self) -> np.ndarray:
        """
        Get the bus names.

        Returns
        -------
        numpy.ndarray
            Full bus names.
        """
        return self._linear_artifact.get_bus_names()

    def get_dimensions_count(self) -> int:
        """
        Get the full per-bus query dimension count.

        Returns
        -------
        int
            Full query dimension count.
        """
        return self._linear_artifact.get_dimensions_count()

    def get_max_order(self) -> int:
        """
        Get the maximum total order represented online.

        Returns
        -------
        int
            Maximum total order.
        """
        return 2

    def get_quadratic_dimensions_count(self) -> int:
        """
        Get the retained quadratic dimension count.

        Returns
        -------
        int
            Number of retained quadratic dimensions.
        """
        return int(self._selected_dimension_indices.size)

    def get_quadratic_dimension_indices(self) -> np.ndarray:
        """
        Get the retained full query dimensions.

        Returns
        -------
        numpy.ndarray
            Full-dimension indices kept by the quadratic stage.
        """
        return np.asarray(self._selected_dimension_indices, dtype=np.int64)

    def get_quadratic_dimension_scores(self) -> np.ndarray:
        """
        Get the retained full query dimension scores.

        Returns
        -------
        numpy.ndarray
            Per-dimension scores.
        """
        return np.asarray(self._selected_dimension_scores, dtype=np.float64)

    def get_quadratic_dimension_names(self) -> np.ndarray:
        """
        Get the retained full query dimension names.

        Returns
        -------
        numpy.ndarray
            Human-readable dimension labels.
        """
        return np.asarray(self._selected_dimension_names, dtype=str)

    def split_sbus_input(self, s_bus: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Split a full complex bus-power vector into artifact query arrays.

        Parameters
        ----------
        s_bus:
            Full complex bus-power vector in per unit.

        Returns
        -------
        tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]
            ``(pq_active_power, pq_reactive_power, pv_active_power)``.
        """
        return self._linear_artifact.split_sbus_input(s_bus=s_bus)

    def build_deviation_vector(
        self,
        pq_active_power: np.ndarray,
        pq_reactive_power: np.ndarray,
        pv_active_power: np.ndarray,
    ) -> np.ndarray:
        """
        Convert absolute query powers to the internal full deviation vector.

        Parameters
        ----------
        pq_active_power:
            PQ active powers in per unit.
        pq_reactive_power:
            PQ reactive powers in per unit.
        pv_active_power:
            PV active powers in per unit.

        Returns
        -------
        numpy.ndarray
            Full deviation vector.
        """
        return self._linear_artifact.build_deviation_vector(
            pq_active_power=pq_active_power,
            pq_reactive_power=pq_reactive_power,
            pv_active_power=pv_active_power,
        )

    def evaluate_deviation(self, deviation: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Evaluate the compressed artifact at one full deviation point.

        Parameters
        ----------
        deviation:
            Full per-bus deviation vector.

        Returns
        -------
        tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]
            Voltage vector, scheduled power vector and PV reactive powers.
        """
        deviation_array: np.ndarray = np.asarray(deviation, dtype=np.complex128)
        expected_shape: tuple[int, ...] = (self.get_dimensions_count(),)

        if deviation_array.shape == expected_shape:
            linear_voltage: np.ndarray
            linear_scheduled_power: np.ndarray
            linear_pv_reactive_power: np.ndarray
            linear_voltage, linear_scheduled_power, linear_pv_reactive_power = self._linear_artifact.evaluate_deviation(
                deviation=deviation_array
            )
            _ = linear_scheduled_power
            quadratic_deviation: np.ndarray = deviation_array[self._selected_dimension_indices]
            quadratic_voltage_local: np.ndarray
            quadratic_pv_reactive_power: np.ndarray
            quadratic_voltage_local, quadratic_pv_reactive_power = evaluate_artifact_higher_order_terms(
                artifact=self._quadratic_artifact,
                deviation=quadratic_deviation,
                minimum_order=2,
            )
            voltage: np.ndarray = np.asarray(linear_voltage, dtype=np.complex128).copy()
            voltage[self._linear_artifact._no_slack] = (
                voltage[self._linear_artifact._no_slack] + quadratic_voltage_local
            )
            pv_reactive_power_complex: np.ndarray = (
                np.asarray(linear_pv_reactive_power, dtype=np.complex128) + quadratic_pv_reactive_power
            )
            pv_reactive_power = np.asarray(pv_reactive_power_complex.real, dtype=np.float64)
            scheduled_power: np.ndarray = self._linear_artifact.calculate_scheduled_power(
                deviation=deviation_array,
                pv_reactive_power=pv_reactive_power,
            )
        else:
            raise ValueError("deviation has an unexpected shape")

        return voltage, scheduled_power, pv_reactive_power

    def query(
        self,
        pq_active_power: np.ndarray,
        pq_reactive_power: np.ndarray,
        pv_active_power: np.ndarray,
        tolerance: float,
    ) -> MDHEMQueryResult:
        """
        Query the compressed artifact with absolute PQ and PV powers.

        Parameters
        ----------
        pq_active_power:
            PQ active powers in per unit.
        pq_reactive_power:
            PQ reactive powers in per unit.
        pv_active_power:
            PV active powers in per unit.
        tolerance:
            Convergence-like tolerance used for the result flags.

        Returns
        -------
        MDHEMQueryResult
            Query result with voltages, flows and mismatch metrics.
        """
        deviation: np.ndarray = self.build_deviation_vector(
            pq_active_power=pq_active_power,
            pq_reactive_power=pq_reactive_power,
            pv_active_power=pv_active_power,
        )
        voltage: np.ndarray
        scheduled_power: np.ndarray
        pv_reactive_power_values: np.ndarray
        voltage, scheduled_power, pv_reactive_power_values = self.evaluate_deviation(deviation=deviation)
        calculated_power: np.ndarray = compute_power_from_ybus(ybus=self._linear_artifact._ybus, voltage=voltage)
        mismatch_norm: float = calculate_query_mismatch_norm(
            calculated_power=calculated_power,
            scheduled_power=scheduled_power,
            no_slack=self._linear_artifact._no_slack,
            pq=self._linear_artifact._pq,
        )
        pv_voltage_error: float = calculate_pv_voltage_error(
            voltage=voltage,
            pv=self._linear_artifact._pv,
            voltage_setpoint=self._linear_artifact._voltage_setpoint,
        )
        branch_from_power: np.ndarray
        branch_to_power: np.ndarray
        branch_loading: np.ndarray
        branch_losses: np.ndarray
        branch_from_power, branch_to_power, branch_loading, branch_losses = calculate_branch_results(
            voltage=voltage,
            yf=self._linear_artifact._yf,
            yt=self._linear_artifact._yt,
            branch_from_indices=self._linear_artifact._branch_from_indices,
            branch_to_indices=self._linear_artifact._branch_to_indices,
            branch_rates=self._linear_artifact._branch_rates,
            sbase=self._linear_artifact._sbase,
        )
        converged_like: bool = bool(mismatch_norm <= tolerance and pv_voltage_error <= tolerance)

        return MDHEMQueryResult(
            pq_active_power=np.asarray(pq_active_power, dtype=np.float64),
            pq_reactive_power=np.asarray(pq_reactive_power, dtype=np.float64),
            pv_active_power=np.asarray(pv_active_power, dtype=np.float64),
            voltage=voltage,
            scheduled_power=scheduled_power,
            calculated_power=calculated_power,
            pv_reactive_power=pv_reactive_power_values,
            mismatch_norm=mismatch_norm,
            pv_voltage_error=pv_voltage_error,
            converged_like=converged_like,
            branch_from_power=branch_from_power,
            branch_to_power=branch_to_power,
            branch_loading=branch_loading,
            branch_losses=branch_losses,
        )

    def query_from_sbus(self, s_bus: np.ndarray, tolerance: float) -> MDHEMQueryResult:
        """
        Query the compressed artifact from a full complex bus-power vector.

        Parameters
        ----------
        s_bus:
            Full complex bus-power vector in per unit.
        tolerance:
            Convergence-like tolerance used for the result flags.

        Returns
        -------
        MDHEMQueryResult
            Query result with voltages, flows and mismatch metrics.
        """
        pq_active_power: np.ndarray
        pq_reactive_power: np.ndarray
        pv_active_power: np.ndarray
        pq_active_power, pq_reactive_power, pv_active_power = self.split_sbus_input(s_bus=s_bus)
        return self.query(
            pq_active_power=pq_active_power,
            pq_reactive_power=pq_reactive_power,
            pv_active_power=pv_active_power,
            tolerance=tolerance,
        )

    def validate_grid(self, grid: "MultiCircuit") -> None:
        """
        Validate that a VeraGrid circuit matches the artifact layout.

        Parameters
        ----------
        grid:
            VeraGrid circuit to validate.

        Returns
        -------
        None
            The method raises on mismatch.
        """
        self._linear_artifact.validate_grid(grid=grid)

    def to_veragrid_power_flow_results(
        self,
        grid: "MultiCircuit",
        query_result: MDHEMQueryResult,
    ) -> "PowerFlowResults":
        """
        Convert one compressed-artifact query into VeraGrid results.

        Parameters
        ----------
        grid:
            VeraGrid circuit associated with the artifact.
        query_result:
            Query result to translate.

        Returns
        -------
        PowerFlowResults
            VeraGrid-like power-flow result object.
        """
        return self._linear_artifact.to_veragrid_power_flow_results(grid=grid, query_result=query_result)

    def power_flow(
        self,
        grid: "MultiCircuit",
        pq_active_power: np.ndarray,
        pq_reactive_power: np.ndarray,
        pv_active_power: np.ndarray,
        tolerance: float,
    ) -> "PowerFlowResults":
        """
        Run one compressed-artifact power-flow query.

        Parameters
        ----------
        grid:
            VeraGrid circuit associated with the artifact.
        pq_active_power:
            PQ active powers in per unit.
        pq_reactive_power:
            PQ reactive powers in per unit.
        pv_active_power:
            PV active powers in per unit.
        tolerance:
            Convergence-like tolerance used for the result flags.

        Returns
        -------
        PowerFlowResults
            VeraGrid-like power-flow result.
        """
        query_result: MDHEMQueryResult = self.query(
            pq_active_power=pq_active_power,
            pq_reactive_power=pq_reactive_power,
            pv_active_power=pv_active_power,
            tolerance=tolerance,
        )
        return self.to_veragrid_power_flow_results(grid=grid, query_result=query_result)

    def power_flow_from_sbus(
        self,
        grid: "MultiCircuit",
        s_bus: np.ndarray,
        tolerance: float,
    ) -> "PowerFlowResults":
        """
        Run one compressed-artifact power flow from a full ``Sbus`` vector.

        Parameters
        ----------
        grid:
            VeraGrid circuit associated with the artifact.
        s_bus:
            Full complex bus-power vector in per unit.
        tolerance:
            Convergence-like tolerance used for the result flags.

        Returns
        -------
        PowerFlowResults
            VeraGrid-like power-flow result.
        """
        query_result: MDHEMQueryResult = self.query_from_sbus(s_bus=s_bus, tolerance=tolerance)
        return self.to_veragrid_power_flow_results(grid=grid, query_result=query_result)


def load_multicircuit_from_file(matpower_path: Path) -> "MultiCircuit":
    """
    Load a MATPOWER case file into a VeraGrid ``MultiCircuit``.

    Parameters
    ----------
    matpower_path:
        Path to the MATPOWER file.

    Returns
    -------
    MultiCircuit
        Loaded VeraGrid grid object.
    """
    vg: object
    cf: object
    vg, cf = import_veragrid_engine_modules()
    _ = cf
    grid: "MultiCircuit" = vg.open_file(str(matpower_path))
    return grid


def create_mdhelm_inputs(grid: "MultiCircuit") -> VeraGridQueryCaseData:
    """
    Load the VeraGrid numerical data required by the artifact builder.

    Parameters
    ----------
    grid:
        VeraGrid grid object.

    Returns
    -------
    VeraGridQueryCaseData
        Extracted VeraGrid network data.
    """
    vg: object
    cf: object
    vg, cf = import_veragrid_engine_modules()
    _ = cf
    numerical_circuit: object = vg.compile_numerical_circuit_at(circuit=grid, t_idx=None)
    admittance: object = numerical_circuit.get_admittance_matrices()
    base_power: np.ndarray = np.asarray(numerical_circuit.get_power_injections_pu(), dtype=np.complex128)
    indices: object = numerical_circuit.get_simulation_indices(Sbus=base_power, force_only_pq_pv_vd_types=True)
    slack: np.ndarray = np.asarray(indices.vd, dtype=np.int64)
    pq: np.ndarray = np.asarray(indices.pq, dtype=np.int64)
    pv: np.ndarray = np.asarray(indices.pv, dtype=np.int64)
    no_slack: np.ndarray = np.asarray(indices.no_slack, dtype=np.int64)
    slack_voltage: np.ndarray = np.asarray(numerical_circuit.bus_data.Vbus, dtype=np.complex128)
    bus_names: np.ndarray = np.asarray(numerical_circuit.bus_data.names, dtype=str)
    voltage_setpoint: np.ndarray = np.abs(np.asarray(numerical_circuit.bus_data.Vbus, dtype=np.complex128))
    branch_from_indices: np.ndarray = np.asarray(numerical_circuit.passive_branch_data.F, dtype=np.int64)
    branch_to_indices: np.ndarray = np.asarray(numerical_circuit.passive_branch_data.T, dtype=np.int64)
    branch_rates: np.ndarray = np.asarray(numerical_circuit.passive_branch_data.rates, dtype=np.float64)

    return VeraGridQueryCaseData(
        ybus=scipy.sparse.csc_matrix(admittance.Ybus),
        yf=scipy.sparse.csc_matrix(admittance.Yf),
        yt=scipy.sparse.csc_matrix(admittance.Yt),
        slack_voltage=slack_voltage,
        base_power=base_power,
        slack=slack,
        pq=pq,
        pv=pv,
        no_slack=no_slack,
        bus_names=bus_names,
        voltage_setpoint=voltage_setpoint,
        branch_from_indices=branch_from_indices,
        branch_to_indices=branch_to_indices,
        branch_rates=branch_rates,
        sbase=float(numerical_circuit.Sbase),
    )


def build_artifact_from_case(
    grid: "MultiCircuit",
    max_order: int,
    germ_seed_results: Optional["PowerFlowResults"] = None,
) -> tuple[VeraGridQueryCaseData, MDHEMPVQueryArtifact, float]:
    """
    Build the persistent MDHEM artifact from one VeraGrid ``MultiCircuit``.

    :param grid:
        VeraGrid grid object.
    :param max_order:
        Maximum total polynomial order.
    :param germ_seed_results:
        Optional converged VeraGrid ``PowerFlowResults`` used as the artifact
        germ. When omitted, the germ is obtained internally with VeraGrid
        HELM.
    :return:
        Case data, built artifact and the physical-germ residual norm.
    """
    input_data: VeraGridQueryCaseData = create_mdhelm_inputs(grid=grid)
    germ_voltage: np.ndarray
    germ_power: np.ndarray
    germ_error: float

    germ_voltage, germ_power, germ_error = solve_physical_germ(
        grid=grid,
        case_data=input_data,
        germ_seed_results=germ_seed_results,
    )

    artifact: MDHEMPVQueryArtifact = solve_mdhelm_query_artifact(
        input_data=input_data,
        germ_voltage=germ_voltage,
        germ_power=germ_power,
        max_order=max_order,
    )
    return input_data, artifact, germ_error


def build_order2_compressed_artifact_from_case(
    grid: "MultiCircuit",
    retained_dimensions: int,
    germ_seed_results: Optional["PowerFlowResults"] = None,
    reactive_score_weight: float = 1.0,
) -> tuple[VeraGridQueryCaseData, MDHEMOrder2CompressedArtifact, float]:
    """
    Build the exact-linear plus compressed-quadratic artifact.

    Parameters
    ----------
    grid:
        VeraGrid grid object.
    retained_dimensions:
        Number of full query dimensions kept by the quadratic stage.
    germ_seed_results:
        Optional converged VeraGrid power-flow result used as the artifact
        germ. When omitted, the germ is obtained internally with VeraGrid
        HELM.
    reactive_score_weight:
        Relative weight applied to PV reactive-power sensitivity while ranking
        retained quadratic dimensions.

    Returns
    -------
    tuple[VeraGridQueryCaseData, MDHEMOrder2CompressedArtifact, float]
        Case data, built compressed artifact and the physical-germ residual
        norm.
    """
    input_data: VeraGridQueryCaseData = create_mdhelm_inputs(grid=grid)
    germ_voltage: np.ndarray
    germ_power: np.ndarray
    germ_error: float
    germ_voltage, germ_power, germ_error = solve_physical_germ(
        grid=grid,
        case_data=input_data,
        germ_seed_results=germ_seed_results,
    )
    basis: np.ndarray
    dimension_kind_codes: np.ndarray
    dimension_bus: np.ndarray
    dimension_local: np.ndarray
    pq_active_dimension: np.ndarray
    pq_reactive_dimension: np.ndarray
    pv_active_dimension: np.ndarray
    basis, dimension_kind_codes, dimension_bus, dimension_local, pq_active_dimension, pq_reactive_dimension, pv_active_dimension = build_query_basis(
        base_power=input_data.base_power,
        pq=input_data.pq,
        pv=input_data.pv,
        no_slack=input_data.no_slack,
    )
    linear_artifact: MDHEMPVQueryArtifact = solve_mdhelm_query_artifact_from_basis(
        input_data=input_data,
        germ_voltage=germ_voltage,
        germ_power=germ_power,
        basis=basis,
        dimension_kind_codes=dimension_kind_codes,
        dimension_bus=dimension_bus,
        dimension_local=dimension_local,
        pq_active_dimension=pq_active_dimension,
        pq_reactive_dimension=pq_reactive_dimension,
        pv_active_dimension=pv_active_dimension,
        max_order=1,
    )
    dimension_scores: np.ndarray = calculate_dimension_scores_from_linear_artifact(
        artifact=linear_artifact,
        reactive_weight=reactive_score_weight,
    )
    selected_dimension_indices: np.ndarray = select_top_dimensions_balanced(
        scores=dimension_scores,
        dimension_kind_codes=dimension_kind_codes,
        retained_dimensions=retained_dimensions,
    )
    quadratic_dimension_scores: np.ndarray = np.asarray(
        dimension_scores[selected_dimension_indices],
        dtype=np.float64,
    )
    quadratic_dimension_names: np.ndarray = create_selected_dimension_names(
        bus_names=input_data.bus_names,
        dimension_kind_codes=dimension_kind_codes,
        dimension_bus=dimension_bus,
        selected_dimension_indices=selected_dimension_indices,
    )
    subset_basis: np.ndarray
    subset_kind_codes: np.ndarray
    subset_dimension_bus: np.ndarray
    subset_dimension_local: np.ndarray
    subset_pq_active_dimension: np.ndarray
    subset_pq_reactive_dimension: np.ndarray
    subset_pv_active_dimension: np.ndarray
    subset_basis, subset_kind_codes, subset_dimension_bus, subset_dimension_local, subset_pq_active_dimension, subset_pq_reactive_dimension, subset_pv_active_dimension = build_subset_query_basis(
        basis=basis,
        dimension_kind_codes=dimension_kind_codes,
        dimension_bus=dimension_bus,
        dimension_local=dimension_local,
        pq_active_dimension=pq_active_dimension,
        pq_reactive_dimension=pq_reactive_dimension,
        pv_active_dimension=pv_active_dimension,
        selected_dimension_indices=selected_dimension_indices,
    )
    quadratic_artifact: MDHEMPVQueryArtifact = solve_mdhelm_query_artifact_from_basis(
        input_data=input_data,
        germ_voltage=germ_voltage,
        germ_power=germ_power,
        basis=subset_basis,
        dimension_kind_codes=subset_kind_codes,
        dimension_bus=subset_dimension_bus,
        dimension_local=subset_dimension_local,
        pq_active_dimension=subset_pq_active_dimension,
        pq_reactive_dimension=subset_pq_reactive_dimension,
        pv_active_dimension=subset_pv_active_dimension,
        max_order=2,
    )
    artifact: MDHEMOrder2CompressedArtifact = MDHEMOrder2CompressedArtifact(
        linear_artifact=linear_artifact,
        quadratic_artifact=quadratic_artifact,
        selected_dimension_indices=selected_dimension_indices,
        selected_dimension_scores=quadratic_dimension_scores,
        selected_dimension_names=quadratic_dimension_names,
    )
    return input_data, artifact, germ_error


def store_csc_matrix(entries: dict[str, np.ndarray], prefix: str, matrix: scipy.sparse.csc_matrix) -> None:
    """
    Store one CSC matrix into the ``np.savez`` entry dictionary.

    Parameters
    ----------
    entries:
        Storage dictionary for ``numpy.savez_compressed``.
    prefix:
        Prefix used for the matrix fields.
    matrix:
        Sparse CSC matrix to store.

    Returns
    -------
    None
        The dictionary is mutated in place.
    """
    csc_matrix: scipy.sparse.csc_matrix = matrix.tocsc()
    entries[f"{prefix}_data"] = csc_matrix.data
    entries[f"{prefix}_indices"] = csc_matrix.indices
    entries[f"{prefix}_indptr"] = csc_matrix.indptr
    entries[f"{prefix}_shape"] = np.asarray(csc_matrix.shape, dtype=np.int64)


def restore_csc_matrix(data: np.lib.npyio.NpzFile, prefix: str) -> scipy.sparse.csc_matrix:
    """
    Restore one CSC matrix from the ``np.savez`` entry dictionary.

    Parameters
    ----------
    data:
        Loaded ``npz`` archive.
    prefix:
        Prefix used for the matrix fields.

    Returns
    -------
    scipy.sparse.csc_matrix
        Restored sparse matrix.
    """
    shape_tuple: tuple[int, int] = (
        int(data[f"{prefix}_shape"][0]),
        int(data[f"{prefix}_shape"][1]),
    )
    restored: scipy.sparse.csc_matrix = scipy.sparse.csc_matrix(
        (data[f"{prefix}_data"], data[f"{prefix}_indices"], data[f"{prefix}_indptr"]),
        shape=shape_tuple,
    )
    return restored


def store_query_artifact_entries(entries: dict[str, np.ndarray], prefix: str, artifact: MDHEMPVQueryArtifact) -> None:
    """
    Store one query artifact into a ``numpy.savez`` entry dictionary.

    Parameters
    ----------
    entries:
        Storage dictionary for ``numpy.savez_compressed``.
    prefix:
        Prefix used for the artifact fields.
    artifact:
        Query artifact to store.

    Returns
    -------
    None
        The dictionary is mutated in place.
    """
    store_csc_matrix(entries=entries, prefix=f"{prefix}_ybus", matrix=artifact._ybus)
    store_csc_matrix(entries=entries, prefix=f"{prefix}_yf", matrix=artifact._yf)
    store_csc_matrix(entries=entries, prefix=f"{prefix}_yt", matrix=artifact._yt)
    entries[f"{prefix}_slack"] = artifact._slack
    entries[f"{prefix}_pq"] = artifact._pq
    entries[f"{prefix}_pv"] = artifact._pv
    entries[f"{prefix}_no_slack"] = artifact._no_slack
    entries[f"{prefix}_slack_voltage"] = artifact._slack_voltage
    entries[f"{prefix}_voltage_setpoint"] = artifact._voltage_setpoint
    entries[f"{prefix}_scheduled_power_germ"] = artifact._scheduled_power_germ
    entries[f"{prefix}_scheduled_basis"] = artifact._scheduled_basis
    entries[f"{prefix}_u_coefficients"] = artifact._u_coefficients
    entries[f"{prefix}_x_coefficients"] = artifact._x_coefficients
    entries[f"{prefix}_q_coefficients"] = artifact._q_coefficients
    entries[f"{prefix}_dimension_kind_codes"] = artifact._dimension_kind_codes
    entries[f"{prefix}_dimension_bus"] = artifact._dimension_bus
    entries[f"{prefix}_dimension_local"] = artifact._dimension_local
    entries[f"{prefix}_pq_active_dimension"] = artifact._pq_active_dimension
    entries[f"{prefix}_pq_reactive_dimension"] = artifact._pq_reactive_dimension
    entries[f"{prefix}_pv_active_dimension"] = artifact._pv_active_dimension
    entries[f"{prefix}_bus_names"] = artifact._bus_names
    entries[f"{prefix}_branch_from_indices"] = artifact._branch_from_indices
    entries[f"{prefix}_branch_to_indices"] = artifact._branch_to_indices
    entries[f"{prefix}_branch_rates"] = artifact._branch_rates
    entries[f"{prefix}_sbase"] = np.asarray([artifact._sbase], dtype=np.float64)
    entries[f"{prefix}_max_order"] = np.asarray([artifact._table.get_max_order()], dtype=np.int64)
    entries[f"{prefix}_dims"] = np.asarray([artifact.get_dimensions_count()], dtype=np.int64)


def load_query_artifact_from_entries(data: np.lib.npyio.NpzFile, prefix: str) -> MDHEMPVQueryArtifact:
    """
    Restore one query artifact from a ``numpy.savez`` entry dictionary.

    Parameters
    ----------
    data:
        Loaded ``npz`` archive.
    prefix:
        Prefix used for the artifact fields.

    Returns
    -------
    MDHEMPVQueryArtifact
        Restored artifact.
    """
    ybus: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix=f"{prefix}_ybus")
    yf: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix=f"{prefix}_yf")
    yt: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix=f"{prefix}_yt")
    dims: int = int(data[f"{prefix}_dims"][0])
    max_order: int = int(data[f"{prefix}_max_order"][0])
    table: MultiIndexTable = create_multi_index_table(dims=dims, max_order=max_order)
    artifact: MDHEMPVQueryArtifact = MDHEMPVQueryArtifact(
        ybus=ybus,
        yf=yf,
        yt=yt,
        slack=np.asarray(data[f"{prefix}_slack"], dtype=np.int64),
        pq=np.asarray(data[f"{prefix}_pq"], dtype=np.int64),
        pv=np.asarray(data[f"{prefix}_pv"], dtype=np.int64),
        no_slack=np.asarray(data[f"{prefix}_no_slack"], dtype=np.int64),
        slack_voltage=np.asarray(data[f"{prefix}_slack_voltage"], dtype=np.complex128),
        voltage_setpoint=np.asarray(data[f"{prefix}_voltage_setpoint"], dtype=np.float64),
        scheduled_power_germ=np.asarray(data[f"{prefix}_scheduled_power_germ"], dtype=np.complex128),
        scheduled_basis=np.asarray(data[f"{prefix}_scheduled_basis"], dtype=np.complex128),
        table=table,
        u_coefficients=np.asarray(data[f"{prefix}_u_coefficients"], dtype=np.complex128),
        x_coefficients=np.asarray(data[f"{prefix}_x_coefficients"], dtype=np.complex128),
        q_coefficients=np.asarray(data[f"{prefix}_q_coefficients"], dtype=np.float64),
        dimension_kind_codes=np.asarray(data[f"{prefix}_dimension_kind_codes"], dtype=np.int64),
        dimension_bus=np.asarray(data[f"{prefix}_dimension_bus"], dtype=np.int64),
        dimension_local=np.asarray(data[f"{prefix}_dimension_local"], dtype=np.int64),
        pq_active_dimension=np.asarray(data[f"{prefix}_pq_active_dimension"], dtype=np.int64),
        pq_reactive_dimension=np.asarray(data[f"{prefix}_pq_reactive_dimension"], dtype=np.int64),
        pv_active_dimension=np.asarray(data[f"{prefix}_pv_active_dimension"], dtype=np.int64),
        bus_names=np.asarray(data[f"{prefix}_bus_names"], dtype=str),
        branch_from_indices=np.asarray(data[f"{prefix}_branch_from_indices"], dtype=np.int64),
        branch_to_indices=np.asarray(data[f"{prefix}_branch_to_indices"], dtype=np.int64),
        branch_rates=np.asarray(data[f"{prefix}_branch_rates"], dtype=np.float64),
        sbase=float(data[f"{prefix}_sbase"][0]),
    )
    return artifact


def save_query_artifact(path: Path, artifact: MDHEMPVQueryArtifact) -> None:
    """
    Save the persistent artifact to one compressed ``npz`` file.

    Parameters
    ----------
    path:
        Output artifact path.
    artifact:
        Artifact to save.

    Returns
    -------
    None
        The file is written to disk.
    """
    entries: dict[str, np.ndarray] = dict()
    store_query_artifact_entries(entries=entries, prefix="artifact", artifact=artifact)
    np.savez_compressed(path, **entries)


def load_query_artifact(path: Path) -> MDHEMPVQueryArtifact:
    """
    Load the persistent artifact from disk.

    Parameters
    ----------
    path:
        Artifact file path.

    Returns
    -------
    MDHEMPVQueryArtifact
        Restored artifact.
    """
    with np.load(path, allow_pickle=False) as data:
        if "artifact_dims" in data.files:
            artifact = load_query_artifact_from_entries(data=data, prefix="artifact")
        else:
            ybus: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix="ybus")
            yf: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix="yf")
            yt: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix="yt")
            dims: int = int(data["dims"][0])
            max_order: int = int(data["max_order"][0])
            table: MultiIndexTable = create_multi_index_table(dims=dims, max_order=max_order)
            artifact = MDHEMPVQueryArtifact(
                ybus=ybus,
                yf=yf,
                yt=yt,
                slack=np.asarray(data["slack"], dtype=np.int64),
                pq=np.asarray(data["pq"], dtype=np.int64),
                pv=np.asarray(data["pv"], dtype=np.int64),
                no_slack=np.asarray(data["no_slack"], dtype=np.int64),
                slack_voltage=np.asarray(data["slack_voltage"], dtype=np.complex128),
                voltage_setpoint=np.asarray(data["voltage_setpoint"], dtype=np.float64),
                scheduled_power_germ=np.asarray(data["scheduled_power_germ"], dtype=np.complex128),
                scheduled_basis=np.asarray(data["scheduled_basis"], dtype=np.complex128),
                table=table,
                u_coefficients=np.asarray(data["u_coefficients"], dtype=np.complex128),
                x_coefficients=np.asarray(data["x_coefficients"], dtype=np.complex128),
                q_coefficients=np.asarray(data["q_coefficients"], dtype=np.float64),
                dimension_kind_codes=np.asarray(data["dimension_kind_codes"], dtype=np.int64),
                dimension_bus=np.asarray(data["dimension_bus"], dtype=np.int64),
                dimension_local=np.asarray(data["dimension_local"], dtype=np.int64),
                pq_active_dimension=np.asarray(data["pq_active_dimension"], dtype=np.int64),
                pq_reactive_dimension=np.asarray(data["pq_reactive_dimension"], dtype=np.int64),
                pv_active_dimension=np.asarray(data["pv_active_dimension"], dtype=np.int64),
                bus_names=np.asarray(data["bus_names"], dtype=str),
                branch_from_indices=np.asarray(data["branch_from_indices"], dtype=np.int64),
                branch_to_indices=np.asarray(data["branch_to_indices"], dtype=np.int64),
                branch_rates=np.asarray(data["branch_rates"], dtype=np.float64),
                sbase=float(data["sbase"][0]),
            )
    return artifact


def save_order2_compressed_artifact(path: Path, artifact: MDHEMOrder2CompressedArtifact) -> None:
    """
    Save the compressed order-2 artifact to one compressed ``npz`` file.

    Parameters
    ----------
    path:
        Output artifact path.
    artifact:
        Compressed artifact to save.

    Returns
    -------
    None
        The file is written to disk.
    """
    entries: dict[str, np.ndarray] = dict()
    store_query_artifact_entries(entries=entries, prefix="linear", artifact=artifact._linear_artifact)
    store_query_artifact_entries(entries=entries, prefix="quadratic", artifact=artifact._quadratic_artifact)
    entries["selected_dimension_indices"] = artifact._selected_dimension_indices
    entries["selected_dimension_scores"] = artifact._selected_dimension_scores
    entries["selected_dimension_names"] = artifact._selected_dimension_names
    np.savez_compressed(path, **entries)


def load_order2_compressed_artifact(path: Path) -> MDHEMOrder2CompressedArtifact:
    """
    Load the compressed order-2 artifact from disk.

    Parameters
    ----------
    path:
        Artifact file path.

    Returns
    -------
    MDHEMOrder2CompressedArtifact
        Restored compressed artifact.
    """
    with np.load(path, allow_pickle=False) as data:
        linear_artifact: MDHEMPVQueryArtifact = load_query_artifact_from_entries(data=data, prefix="linear")
        quadratic_artifact: MDHEMPVQueryArtifact = load_query_artifact_from_entries(data=data, prefix="quadratic")
        artifact: MDHEMOrder2CompressedArtifact = MDHEMOrder2CompressedArtifact(
            linear_artifact=linear_artifact,
            quadratic_artifact=quadratic_artifact,
            selected_dimension_indices=np.asarray(data["selected_dimension_indices"], dtype=np.int64),
            selected_dimension_scores=np.asarray(data["selected_dimension_scores"], dtype=np.float64),
            selected_dimension_names=np.asarray(data["selected_dimension_names"], dtype=str),
        )

    return artifact


def mdhelm_power_flow(
    grid: "MultiCircuit",
    artifact: MDHEMPVQueryArtifact,
    pq_active_power: np.ndarray,
    pq_reactive_power: np.ndarray,
    pv_active_power: np.ndarray,
    tolerance: float = 1e-8,
) -> "PowerFlowResults":
    """
    Run one artifact-backed power flow with a VeraGrid-like API.

    Parameters
    ----------
    grid:
        VeraGrid circuit associated with the artifact.
    artifact:
        Pre-built MDHEM artifact.
    pq_active_power:
        Active powers for the PQ buses in per unit.
    pq_reactive_power:
        Reactive powers for the PQ buses in per unit.
    pv_active_power:
        Active powers for the PV buses in per unit.
    tolerance:
        Convergence-like tolerance used for the result flags.

    Returns
    -------
    PowerFlowResults
        VeraGrid-like power-flow results object.
    """
    return artifact.power_flow(
        grid=grid,
        pq_active_power=pq_active_power,
        pq_reactive_power=pq_reactive_power,
        pv_active_power=pv_active_power,
        tolerance=tolerance,
    )


def mdhelm_power_flow_from_sbus(
    grid: "MultiCircuit",
    artifact: MDHEMPVQueryArtifact,
    s_bus: np.ndarray,
    tolerance: float = 1e-8,
) -> "PowerFlowResults":
    """
    Run one artifact-backed power flow from a full complex bus-power vector.

    Parameters
    ----------
    grid:
        VeraGrid circuit associated with the artifact.
    artifact:
        Pre-built MDHEM artifact.
    s_bus:
        Full complex bus-power vector in per unit.
    tolerance:
        Convergence-like tolerance used for the result flags.

    Returns
    -------
    PowerFlowResults
        VeraGrid-like power-flow results object.
    """
    return artifact.power_flow_from_sbus(
        grid=grid,
        s_bus=s_bus,
        tolerance=tolerance,
    )


def print_bus_layout(artifact: MDHEMPVQueryArtifact) -> None:
    """
    Print the query-bus layout used by the artifact.

    Parameters
    ----------
    artifact:
        Loaded artifact.

    Returns
    -------
    None
        The function prints to standard output.
    """
    pq_bus_indices: np.ndarray = artifact.get_pq_bus_indices()
    pv_bus_indices: np.ndarray = artifact.get_pv_bus_indices()
    bus_names: np.ndarray = artifact.get_bus_names()
    pq_index: int
    print("PQ query buses")
    for pq_index in range(pq_bus_indices.size):
        full_bus: int = int(pq_bus_indices[pq_index])
        print(f"  PQ bus {full_bus + 1}: {bus_names[full_bus]}")
    pv_index: int
    print("PV query buses")
    for pv_index in range(pv_bus_indices.size):
        full_bus = int(pv_bus_indices[pv_index])
        print(f"  PV bus {full_bus + 1}: {bus_names[full_bus]}")


def run_case14_artifact_demo() -> None:
    """
    Build, save, load and query the case14 artifact.

    Returns
    -------
    None
        The function prints the build and query summary.
    """
    case_path: Path = Path(__file__).resolve().with_name("case14.matpower")
    artifact_path: Path = Path(__file__).resolve().with_name("mdhelm_pv_case14_query_artifact.npz")
    max_order: int = 4
    tolerance: float = 1e-8
    grid: "MultiCircuit" = load_multicircuit_from_file(matpower_path=case_path)
    case_data: VeraGridQueryCaseData
    artifact: MDHEMPVQueryArtifact
    germ_error: float
    case_data, artifact, germ_error = build_artifact_from_case(grid=grid, max_order=max_order)
    save_query_artifact(path=artifact_path, artifact=artifact)
    restored_artifact: MDHEMPVQueryArtifact = load_query_artifact(path=artifact_path)
    pq_active_power: np.ndarray = case_data.base_power[case_data.pq].real.copy()
    pq_reactive_power: np.ndarray = case_data.base_power[case_data.pq].imag.copy()
    pv_active_power: np.ndarray = case_data.base_power[case_data.pv].real.copy()
    result: MDHEMQueryResult = restored_artifact.query(
        pq_active_power=pq_active_power,
        pq_reactive_power=pq_reactive_power,
        pv_active_power=pv_active_power,
        tolerance=tolerance,
    )

    print("\nPersistent MDHEM-PV query artifact built from case14")
    print("-----------------------------------------------------")
    print(f"Artifact path:                 {artifact_path}")
    print(f"Maximum order:                 {restored_artifact.get_max_order()}")
    print(f"Embedding dimensions:          {restored_artifact.get_dimensions_count()}")
    print(f"PQ buses:                      {list((case_data.pq + 1).astype(int))}")
    print(f"PV buses:                      {list((case_data.pv + 1).astype(int))}")
    print(f"Artifact germ residual:        {germ_error:.4e}")
    print(f"Base-case query mismatch:      {result.mismatch_norm:.4e}")
    print(f"Base-case PV voltage error:    {result.pv_voltage_error:.4e}")
    print(f"Base-case converged-like:      {result.converged_like}")
    print_bus_layout(artifact=restored_artifact)
    print("\nFirst 5 branch flows from artifact query, MVA")
    branch_count: int = min(5, result.branch_from_power.size)
    branch_index: int
    for branch_index in range(branch_count):
        branch_power: complex = complex(result.branch_from_power[branch_index])
        print(f"branch {branch_index:>2}: Sf = {branch_power.real: .4f} MW {branch_power.imag:+.4f} MVAr")
