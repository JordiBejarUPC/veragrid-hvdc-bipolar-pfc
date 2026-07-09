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
    orders:
        Multi-indices grouped by total order.
    alphas:
        Flat list of all multi-indices up to ``max_order``.
    alpha_to_position:
        Lookup table from multi-index to row position in coefficient arrays.
    minus_e_position:
        Matrix whose row ``k`` and column ``d`` stores the coefficient position
        of ``alpha_k - e_d``. A value of ``-1`` means that subtraction is not
        possible because the corresponding exponent is zero.
    proper_sub_index_left:
        For each coefficient position, left indices used in known convolution
        sums. These exclude the zero term and the current term.
    proper_sub_index_right:
        For each coefficient position, right indices paired with
        ``proper_sub_index_left``.
    """

    __slots__ = (
        "_dims",
        "_max_order",
        "_orders",
        "_alphas",
        "_alphas_array",
        "_alpha_to_position",
        "_minus_e_position",
        "_proper_sub_index_left",
        "_proper_sub_index_right",
    )

    def __init__(
        self,
        dims: int,
        max_order: int,
        orders: list[list[tuple[int, ...]]],
        alphas: list[tuple[int, ...]],
        alpha_to_position: dict[tuple[int, ...], int],
        minus_e_position: np.ndarray,
        proper_sub_index_left: list[np.ndarray],
        proper_sub_index_right: list[np.ndarray],
    ) -> None:
        self._dims: int = dims
        self._max_order: int = max_order
        self._orders: list[list[tuple[int, ...]]] = orders
        self._alphas: list[tuple[int, ...]] = alphas
        self._alphas_array: np.ndarray = build_alpha_array(dims=dims, alphas=alphas)
        self._alpha_to_position: dict[tuple[int, ...], int] = alpha_to_position
        self._minus_e_position: np.ndarray = minus_e_position
        self._proper_sub_index_left: list[np.ndarray] = proper_sub_index_left
        self._proper_sub_index_right: list[np.ndarray] = proper_sub_index_right

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

    def get_orders(self) -> list[list[tuple[int, ...]]]:
        """
        Get the multi-indices grouped by total order.

        Returns
        -------
        list[list[tuple[int, ...]]]
            Multi-indices grouped by order.
        """
        return self._orders

    def get_alphas(self) -> list[tuple[int, ...]]:
        """
        Get the flat list of multi-indices.

        Returns
        -------
        list[tuple[int, ...]]
            Flat multi-index list.
        """
        return self._alphas

    def get_alphas_array(self) -> np.ndarray:
        """
        Get the flat list of multi-indices as a dense integer array.

        Returns
        -------
        numpy.ndarray
            Integer exponent array with shape ``(n_terms, dims)``.
        """
        return self._alphas_array

    def get_alpha_to_position(self) -> dict[tuple[int, ...], int]:
        """
        Get the multi-index lookup table.

        Returns
        -------
        dict[tuple[int, ...], int]
            Lookup table from multi-index to coefficient row.
        """
        return self._alpha_to_position

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
        return self._proper_sub_index_left[position]

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
        return self._proper_sub_index_right[position]


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
        Callable object returned by SciPy sparse factorization.
    """

    __slots__ = ("_factorization",)

    def __init__(self, factorization: object) -> None:
        self._factorization: object = factorization

    def solve(self, rhs: np.ndarray) -> np.ndarray:
        """
        Solve the sparse linear system for one right-hand side.

        Parameters
        ----------
        rhs:
            Right-hand-side vector.

        Returns
        -------
        numpy.ndarray
            Solution vector.
        """
        solution: np.ndarray = np.asarray(self._factorization(rhs), dtype=np.float64)
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


def append_compositions(total: int, dims: int, prefix: tuple[int, ...], output: list[tuple[int, ...]]) -> None:
    """
    Append all non-negative compositions of ``total`` into ``dims`` parts.

    Parameters
    ----------
    total:
        Total order to distribute.
    dims:
        Remaining number of dimensions.
    prefix:
        Prefix already assigned by the recursion.
    output:
        Output list receiving the generated multi-indices.

    Returns
    -------
    None
        The function mutates ``output`` in place.
    """
    if dims == 1:
        output.append(prefix + (total,))
    else:
        value: int
        for value in range(total + 1):
            append_compositions(total=total - value, dims=dims - 1, prefix=prefix + (value,), output=output)


def create_multi_index_table(dims: int, max_order: int) -> MultiIndexTable:
    """
    Create the multi-index table needed by the MDHEM coefficient recursion.

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
    orders: list[list[tuple[int, ...]]] = list()
    alphas: list[tuple[int, ...]] = list()
    order_index: int
    if dims > 0 and max_order >= 0:
        for order_index in range(max_order + 1):
            current_order: list[tuple[int, ...]] = list()
            append_compositions(total=order_index, dims=dims, prefix=tuple(), output=current_order)
            orders.append(current_order)
            alphas.extend(current_order)
    else:
        current_order = list()
        current_order.append(tuple())
        orders.append(current_order)
        alphas.extend(current_order)

    alpha_to_position: dict[tuple[int, ...], int] = dict()
    position: int
    for position in range(len(alphas)):
        alpha_to_position[alphas[position]] = position

    minus_e_position: np.ndarray = -np.ones((len(alphas), dims), dtype=np.int64)
    for position in range(len(alphas)):
        alpha: tuple[int, ...] = alphas[position]
        dimension_index: int
        for dimension_index in range(dims):
            if alpha[dimension_index] > 0:
                previous_alpha_list: list[int] = list(alpha)
                previous_alpha_list[dimension_index] = previous_alpha_list[dimension_index] - 1
                minus_e_position[position, dimension_index] = alpha_to_position[tuple(previous_alpha_list)]
            else:
                minus_e_position[position, dimension_index] = -1

    proper_left: list[np.ndarray] = list()
    proper_right: list[np.ndarray] = list()
    zero_alpha: tuple[int, ...] = tuple(0 for _ in range(dims))
    for position in range(len(alphas)):
        alpha = alphas[position]
        left_positions: list[int] = list()
        right_positions: list[int] = list()
        append_proper_sub_indices(
            alpha=alpha,
            current_dimension=0,
            current_values=list(),
            zero_alpha=zero_alpha,
            alpha_to_position=alpha_to_position,
            left_positions=left_positions,
            right_positions=right_positions,
        )
        proper_left.append(np.asarray(left_positions, dtype=np.int64))
        proper_right.append(np.asarray(right_positions, dtype=np.int64))

    return MultiIndexTable(
        dims=dims,
        max_order=max_order,
        orders=orders,
        alphas=alphas,
        alpha_to_position=alpha_to_position,
        minus_e_position=minus_e_position,
        proper_sub_index_left=proper_left,
        proper_sub_index_right=proper_right,
    )


def append_proper_sub_indices(
    alpha: tuple[int, ...],
    current_dimension: int,
    current_values: list[int],
    zero_alpha: tuple[int, ...],
    alpha_to_position: dict[tuple[int, ...], int],
    left_positions: list[int],
    right_positions: list[int],
) -> None:
    """
    Append non-trivial beta/gamma pairs satisfying ``beta + gamma = alpha``.

    Parameters
    ----------
    alpha:
        Current multi-index.
    current_dimension:
        Recursive dimension counter.
    current_values:
        Current beta under construction.
    zero_alpha:
        Zero multi-index.
    alpha_to_position:
        Lookup table from multi-index to coefficient position.
    left_positions:
        Left coefficient positions receiving beta.
    right_positions:
        Right coefficient positions receiving gamma.

    Returns
    -------
    None
        The function mutates ``left_positions`` and ``right_positions``.
    """
    if current_dimension == len(alpha):
        beta: tuple[int, ...] = tuple(current_values)
        if beta != zero_alpha:
            if beta != alpha:
                gamma: tuple[int, ...] = tuple(alpha[index] - beta[index] for index in range(len(alpha)))
                left_positions.append(alpha_to_position[beta])
                right_positions.append(alpha_to_position[gamma])
            else:
                pass
        else:
            pass
    else:
        value: int
        for value in range(alpha[current_dimension] + 1):
            current_values.append(value)
            append_proper_sub_indices(
                alpha=alpha,
                current_dimension=current_dimension + 1,
                current_values=current_values,
                zero_alpha=zero_alpha,
                alpha_to_position=alpha_to_position,
                left_positions=left_positions,
                right_positions=right_positions,
            )
            current_values.pop()


def build_alpha_array(dims: int, alphas: list[tuple[int, ...]]) -> np.ndarray:
    """
    Build a dense integer exponent matrix from the Python tuple list.

    Parameters
    ----------
    dims:
        Number of embedding dimensions.
    alphas:
        Multi-index list.

    Returns
    -------
    numpy.ndarray
        Integer exponent matrix with shape ``(n_terms, dims)``.
    """
    alpha_array: np.ndarray = np.zeros((len(alphas), dims), dtype=np.int64)
    position: int
    for position in range(len(alphas)):
        dimension_index: int
        for dimension_index in range(dims):
            alpha_array[position, dimension_index] = int(alphas[position][dimension_index])
    return alpha_array


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
    row_indices: list[int] = list()
    column_indices: list[int] = list()
    data: list[float] = list()

    yred_coo: scipy.sparse.coo_matrix = yred.tocoo()
    entry_index: int
    for entry_index in range(yred_coo.data.size):
        row_index: int = int(yred_coo.row[entry_index])
        column_index: int = int(yred_coo.col[entry_index])
        value: complex = complex(yred_coo.data[entry_index])
        append_sparse_value(row_indices, column_indices, data, row_index, column_index, value.real)
        append_sparse_value(row_indices, column_indices, data, row_index, n_no_slack + column_index, -value.imag)
        append_sparse_value(row_indices, column_indices, data, n_no_slack + row_index, column_index, value.imag)
        append_sparse_value(row_indices, column_indices, data, n_no_slack + row_index, n_no_slack + column_index, value.real)

    local_index: int
    for local_index in range(n_no_slack):
        c_value: complex = complex(c_germ[local_index])
        append_sparse_value(row_indices, column_indices, data, local_index, 2 * n_no_slack + local_index, -c_value.real)
        append_sparse_value(row_indices, column_indices, data, local_index, 3 * n_no_slack + local_index, c_value.imag)
        append_sparse_value(row_indices, column_indices, data, n_no_slack + local_index, 2 * n_no_slack + local_index, -c_value.imag)
        append_sparse_value(row_indices, column_indices, data, n_no_slack + local_index, 3 * n_no_slack + local_index, -c_value.real)

    pv_index: int
    for pv_index in range(n_pv):
        local_index = int(pv_local[pv_index])
        x_value: complex = complex(x_zero[local_index])
        append_sparse_value(row_indices, column_indices, data, local_index, 4 * n_no_slack + pv_index, -x_value.imag)
        append_sparse_value(row_indices, column_indices, data, n_no_slack + local_index, 4 * n_no_slack + pv_index, x_value.real)

    for local_index in range(n_no_slack):
        x_value = complex(x_zero[local_index])
        u_value: complex = complex(u_zero[local_index])
        reciprocal_real_row: int = 2 * n_no_slack + local_index
        reciprocal_imag_row: int = 3 * n_no_slack + local_index
        append_sparse_value(row_indices, column_indices, data, reciprocal_real_row, local_index, x_value.real)
        append_sparse_value(row_indices, column_indices, data, reciprocal_real_row, n_no_slack + local_index, x_value.imag)
        append_sparse_value(row_indices, column_indices, data, reciprocal_real_row, 2 * n_no_slack + local_index, u_value.real)
        append_sparse_value(row_indices, column_indices, data, reciprocal_real_row, 3 * n_no_slack + local_index, u_value.imag)
        append_sparse_value(row_indices, column_indices, data, reciprocal_imag_row, local_index, x_value.imag)
        append_sparse_value(row_indices, column_indices, data, reciprocal_imag_row, n_no_slack + local_index, -x_value.real)
        append_sparse_value(row_indices, column_indices, data, reciprocal_imag_row, 2 * n_no_slack + local_index, -u_value.imag)
        append_sparse_value(row_indices, column_indices, data, reciprocal_imag_row, 3 * n_no_slack + local_index, u_value.real)

    for pv_index in range(n_pv):
        local_index = int(pv_local[pv_index])
        u_value = complex(u_zero[local_index])
        voltage_row: int = 4 * n_no_slack + pv_index
        append_sparse_value(row_indices, column_indices, data, voltage_row, local_index, 2.0 * u_value.real)
        append_sparse_value(row_indices, column_indices, data, voltage_row, n_no_slack + local_index, 2.0 * u_value.imag)

    matrix_coo: scipy.sparse.coo_matrix = scipy.sparse.coo_matrix(
        (np.asarray(data, dtype=np.float64), (np.asarray(row_indices, dtype=np.int64), np.asarray(column_indices, dtype=np.int64))),
        shape=(unknown_count, unknown_count),
    )
    matrix_csc: scipy.sparse.csc_matrix = matrix_coo.tocsc()
    return matrix_csc


def append_sparse_value(
    row_indices: list[int],
    column_indices: list[int],
    data: list[float],
    row_index: int,
    column_index: int,
    value: float,
) -> None:
    """
    Append a sparse matrix entry when it is numerically non-zero.

    Parameters
    ----------
    row_indices:
        Sparse row index list.
    column_indices:
        Sparse column index list.
    data:
        Sparse value list.
    row_index:
        Row index.
    column_index:
        Column index.
    value:
        Matrix value.

    Returns
    -------
    None
        The function mutates the sparse-entry lists in place.
    """
    if value != 0.0:
        row_indices.append(row_index)
        column_indices.append(column_index)
        data.append(value)
    else:
        pass


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
    n_terms: int = len(table.get_alphas())
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
    linear_solver: SparseLinearSolver = SparseLinearSolver(factorization=scipy.sparse.linalg.factorized(system_matrix))
    minus_e_position: np.ndarray = table.get_minus_e_position()

    order_index: int
    for order_index in range(1, max_order + 1):
        current_order: list[tuple[int, ...]] = table.get_orders()[order_index]
        alpha_index: int
        for alpha_index in range(len(current_order)):
            alpha: tuple[int, ...] = current_order[alpha_index]
            position: int = table.get_alpha_to_position()[alpha]
            rhs_power: np.ndarray = np.zeros(n_no_slack, dtype=np.complex128)
            dimension_index: int
            for dimension_index in range(n_no_slack):
                previous_position: int = int(minus_e_position[position, dimension_index])
                if previous_position >= 0:
                    rhs_power = rhs_power + np.conj(basis[dimension_index, :]) * x_coefficients[previous_position, :]
                else:
                    pass

            qx_known: np.ndarray = calculate_known_qx_convolution(
                table=table,
                position=position,
                q_coefficients=q_coefficients,
                x_coefficients=x_coefficients,
                pv_local=pv_local,
            )
            for pv_index in range(n_pv):
                local_index = int(pv_local[pv_index])
                rhs_power[local_index] = rhs_power[local_index] - 1j * qx_known[pv_index]

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
            rhs: np.ndarray = np.zeros(4 * n_no_slack + n_pv, dtype=np.float64)
            rhs[0:n_no_slack] = rhs_power.real
            rhs[n_no_slack:2 * n_no_slack] = rhs_power.imag
            rhs[2 * n_no_slack:3 * n_no_slack] = -reciprocal_known.real
            rhs[3 * n_no_slack:4 * n_no_slack] = -reciprocal_known.imag
            rhs[4 * n_no_slack:4 * n_no_slack + n_pv] = -voltage_known

            solution: np.ndarray = linear_solver.solve(rhs=rhs)
            u_coefficients[position, :] = solution[0:n_no_slack] + 1j * solution[n_no_slack:2 * n_no_slack]
            x_coefficients[position, :] = solution[2 * n_no_slack:3 * n_no_slack] + 1j * solution[3 * n_no_slack:4 * n_no_slack]
            q_coefficients[position, :] = solution[4 * n_no_slack:4 * n_no_slack + n_pv]

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
