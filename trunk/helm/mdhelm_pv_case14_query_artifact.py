"""
Build and query a persistent MDHEM-PV artifact for MATPOWER case14.

This module builds a persistent multidimensional HELM artifact around the
original HELM operating point of MATPOWER case14:

* the embedding dimensions are ``P`` and ``Q`` for each PQ bus and ``P`` for
  each PV bus,
* the external query API uses absolute powers,
* the internal polynomial uses scaled deltas around the base operating point,
* the solved coefficient map is saved as an artifact that can later be queried
  without rebuilding the map.

The artifact query interface accepts absolute per-unit bus powers using
VeraGrid's sign convention:

* PQ buses: ``P`` and ``Q``,
* PV buses: ``P``,
* slack buses: implicit.

The offline build step is intentionally heavier than the online query step.
"""

from __future__ import annotations

import math
import sys
from enum import Enum
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np
import scipy.optimize
import scipy.sparse
import scipy.sparse.linalg

from mdhelm_pv_case14_exaple import MultiIndexTable
from mdhelm_pv_case14_exaple import SparseLinearSolver
from mdhelm_pv_case14_exaple import build_system_matrix
from mdhelm_pv_case14_exaple import calculate_known_qx_convolution
from mdhelm_pv_case14_exaple import calculate_known_reciprocal_convolution
from mdhelm_pv_case14_exaple import calculate_known_voltage_convolution
from mdhelm_pv_case14_exaple import calculate_monomial_weights
from mdhelm_pv_case14_exaple import create_full_to_local_lookup
from mdhelm_pv_case14_exaple import create_multi_index_table

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


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

    def get_multi_index_alphas(self) -> list[tuple[int, ...]]:
        """
        Get the multivariate exponent list.

        Returns
        -------
        list[tuple[int, ...]]
            Multi-index list in coefficient-row order.
        """
        return list(self._table.get_alphas())

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
        pq_active_array: np.ndarray = np.asarray(pq_active_power, dtype=np.float64)
        pq_reactive_array: np.ndarray = np.asarray(pq_reactive_power, dtype=np.float64)
        pv_active_array: np.ndarray = np.asarray(pv_active_power, dtype=np.float64)
        deviation: np.ndarray = np.zeros(self.get_dimensions_count(), dtype=np.complex128)
        pq_index: int

        if pq_active_array.shape == (self._pq.size,):
            for pq_index in range(self._pq.size):
                dimension_index: int = int(self._pq_active_dimension[pq_index])
                local_index: int = int(self._dimension_local[dimension_index])
                active_reference: float = float(self._scheduled_basis[dimension_index, local_index].real)
                germ_pq_active_power: float = float(self._scheduled_power_germ[int(self._pq[pq_index])].real)
                deviation[dimension_index] = (pq_active_array[pq_index] - germ_pq_active_power) / active_reference
        else:
            raise ValueError("pq_active_power must match the PQ bus count")

        if pq_reactive_array.shape == (self._pq.size,):
            for pq_index in range(self._pq.size):
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
            weights: np.ndarray = calculate_monomial_weights(
                alphas=self._table.get_alphas(),
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


def solve_physical_germ(grid: "MultiCircuit", case_data: VeraGridQueryCaseData) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Solve the practical artifact germ for the given case.

    The paper-style zero-PQ continuation was producing a mathematically valid
    but numerically useless branch on case14, with PV reactive powers around
    ``1e10`` at zero order. The artifact is queried around the original case,
    so the robust choice is to use VeraGrid's HELM operating point as the germ
    and expand local deltas around it. This keeps the artifact build free of
    Newton-Raphson so NR is only used later for external validation.

    Parameters
    ----------
    grid:
        VeraGrid circuit used by the HELM solve.
    case_data:
        VeraGrid network data.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray, float]
        Germ voltage, germ scheduled power and residual norm.
    """
    vg: object
    cf: object
    vg, cf = import_veragrid_engine_modules()
    _ = cf

    try:
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
    except TypeError:
        power_flow_options = vg.PowerFlowOptions(vg.SolverType.HELM, verbose=False)

    power_flow_results: object = vg.power_flow(
        grid=grid,
        options=power_flow_options,
    )

    if bool(power_flow_results.converged):
        germ_voltage: np.ndarray = np.asarray(power_flow_results.voltage, dtype=np.complex128)
        germ_power: np.ndarray = compute_power_from_ybus(ybus=case_data.ybus, voltage=germ_voltage)
        germ_error: float = float(power_flow_results.error)
    else:
        raise RuntimeError(f"HELM germ solve failed with error {float(power_flow_results.error):.6e}")

    return germ_voltage, germ_power, germ_error


def solve_mdhelm_query_artifact(
    case_data: VeraGridQueryCaseData,
    germ_voltage: np.ndarray,
    germ_power: np.ndarray,
    max_order: int,
) -> MDHEMPVQueryArtifact:
    """
    Solve the MDHEM coefficients for the persistent query artifact.

    Parameters
    ----------
    case_data:
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
    n_no_slack: int = case_data.no_slack.size
    n_pv: int = case_data.pv.size
    basis: np.ndarray
    dimension_kind_codes: np.ndarray
    dimension_bus: np.ndarray
    dimension_local: np.ndarray
    pq_active_dimension: np.ndarray
    pq_reactive_dimension: np.ndarray
    pv_active_dimension: np.ndarray
    basis, dimension_kind_codes, dimension_bus, dimension_local, pq_active_dimension, pq_reactive_dimension, pv_active_dimension = build_query_basis(
        base_power=case_data.base_power,
        pq=case_data.pq,
        pv=case_data.pv,
        no_slack=case_data.no_slack,
    )
    table: MultiIndexTable = create_multi_index_table(dims=basis.shape[0], max_order=max_order)
    n_terms: int = len(table.get_alphas())
    u_coefficients: np.ndarray = np.zeros((n_terms, n_no_slack), dtype=np.complex128)
    x_coefficients: np.ndarray = np.zeros((n_terms, n_no_slack), dtype=np.complex128)
    q_coefficients: np.ndarray = np.zeros((n_terms, n_pv), dtype=np.float64)
    pv_local: np.ndarray = convert_full_indices_to_local(
        full_to_local=create_full_to_local_lookup(nbus=case_data.ybus.shape[0], no_slack=case_data.no_slack),
        full_indices=case_data.pv,
    )
    yred: scipy.sparse.csc_matrix = case_data.ybus[np.ix_(case_data.no_slack, case_data.no_slack)].tocsc()
    u_zero: np.ndarray = germ_voltage[case_data.no_slack].copy()
    x_zero: np.ndarray = 1.0 / np.conj(u_zero)
    c_germ: np.ndarray = np.conj(germ_power[case_data.no_slack])
    zero_position: int = 0
    u_coefficients[zero_position, :] = u_zero
    x_coefficients[zero_position, :] = x_zero
    pv_index: int

    # The zero-order PV reactive powers come from the physical germ, because
    # that is the point where the multivariate expansion starts.
    for pv_index in range(n_pv):
        q_coefficients[zero_position, pv_index] = germ_power[int(case_data.pv[pv_index])].imag

    system_matrix: scipy.sparse.csc_matrix = build_system_matrix(
        yred=yred,
        c_germ=c_germ,
        u_zero=u_zero,
        x_zero=x_zero,
        pv_local=pv_local,
    )
    linear_solver: SparseLinearSolver = SparseLinearSolver(
        factorization=scipy.sparse.linalg.factorized(system_matrix)
    )
    minus_e_position: np.ndarray = table.get_minus_e_position()
    order_index: int

    # Each coefficient uses the same constant sparse matrix, while only the
    # right-hand side changes through the multivariate convolutions.
    for order_index in range(1, max_order + 1):
        current_order: list[tuple[int, ...]] = table.get_orders()[order_index]
        alpha_index: int

        for alpha_index in range(len(current_order)):
            alpha: tuple[int, ...] = current_order[alpha_index]
            position: int = table.get_alpha_to_position()[alpha]
            rhs_power: np.ndarray = np.zeros(n_no_slack, dtype=np.complex128)
            dimension_index: int

            for dimension_index in range(basis.shape[0]):
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
                local_index: int = int(pv_local[pv_index])
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

    return MDHEMPVQueryArtifact(
        ybus=case_data.ybus,
        yf=case_data.yf,
        yt=case_data.yt,
        slack=case_data.slack,
        pq=case_data.pq,
        pv=case_data.pv,
        no_slack=case_data.no_slack,
        slack_voltage=case_data.slack_voltage,
        voltage_setpoint=case_data.voltage_setpoint,
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
        bus_names=case_data.bus_names,
        branch_from_indices=case_data.branch_from_indices,
        branch_to_indices=case_data.branch_to_indices,
        branch_rates=case_data.branch_rates,
        sbase=case_data.sbase,
    )


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


def load_veragrid_case_data(grid: "MultiCircuit") -> VeraGridQueryCaseData:
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


def build_artifact_from_case(grid: "MultiCircuit", max_order: int) -> tuple[VeraGridQueryCaseData, MDHEMPVQueryArtifact, float]:
    """
    Build the persistent MDHEM artifact from one VeraGrid ``MultiCircuit``.

    Parameters
    ----------
    grid:
        VeraGrid grid object.
    max_order:
        Maximum total polynomial order.

    Returns
    -------
    tuple[VeraGridQueryCaseData, MDHEMPVQueryArtifact, float]
        Case data, built artifact and the physical-germ residual norm.
    """
    case_data: VeraGridQueryCaseData = load_veragrid_case_data(grid=grid)
    germ_voltage: np.ndarray
    germ_power: np.ndarray
    germ_error: float
    germ_voltage, germ_power, germ_error = solve_physical_germ(grid=grid, case_data=case_data)
    artifact: MDHEMPVQueryArtifact = solve_mdhelm_query_artifact(
        case_data=case_data,
        germ_voltage=germ_voltage,
        germ_power=germ_power,
        max_order=max_order,
    )
    return case_data, artifact, germ_error


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

    # The sparse matrices are expanded into raw CSC arrays so the artifact can
    # be restored without pickle or custom serializers.
    store_csc_matrix(entries=entries, prefix="ybus", matrix=artifact._ybus)
    store_csc_matrix(entries=entries, prefix="yf", matrix=artifact._yf)
    store_csc_matrix(entries=entries, prefix="yt", matrix=artifact._yt)
    entries["slack"] = artifact._slack
    entries["pq"] = artifact._pq
    entries["pv"] = artifact._pv
    entries["no_slack"] = artifact._no_slack
    entries["slack_voltage"] = artifact._slack_voltage
    entries["voltage_setpoint"] = artifact._voltage_setpoint
    entries["scheduled_power_germ"] = artifact._scheduled_power_germ
    entries["scheduled_basis"] = artifact._scheduled_basis
    entries["u_coefficients"] = artifact._u_coefficients
    entries["x_coefficients"] = artifact._x_coefficients
    entries["q_coefficients"] = artifact._q_coefficients
    entries["dimension_kind_codes"] = artifact._dimension_kind_codes
    entries["dimension_bus"] = artifact._dimension_bus
    entries["dimension_local"] = artifact._dimension_local
    entries["pq_active_dimension"] = artifact._pq_active_dimension
    entries["pq_reactive_dimension"] = artifact._pq_reactive_dimension
    entries["pv_active_dimension"] = artifact._pv_active_dimension
    entries["bus_names"] = artifact._bus_names
    entries["branch_from_indices"] = artifact._branch_from_indices
    entries["branch_to_indices"] = artifact._branch_to_indices
    entries["branch_rates"] = artifact._branch_rates
    entries["sbase"] = np.asarray([artifact._sbase], dtype=np.float64)
    entries["max_order"] = np.asarray([artifact._table.get_max_order()], dtype=np.int64)
    entries["dims"] = np.asarray([artifact.get_dimensions_count()], dtype=np.int64)
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
        ybus: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix="ybus")
        yf: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix="yf")
        yt: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix="yt")
        dims: int = int(data["dims"][0])
        max_order: int = int(data["max_order"][0])
        table: MultiIndexTable = create_multi_index_table(dims=dims, max_order=max_order)

        artifact: MDHEMPVQueryArtifact = MDHEMPVQueryArtifact(
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


if __name__ == "__main__":
    run_case14_artifact_demo()
else:
    pass
