from __future__ import annotations

from typing import Any

import numpy as np


class ObservationData:
    """
    Typed observation bundle for the operator environment.

    :param step_idx:
        Current control step index.
    :param remaining_steps:
        Remaining number of control steps until truncation.
    :param bus_voltage_magnitude:
        Voltage magnitude per bus in p.u.
    :param bus_voltage_angle:
        Voltage angle per bus in radians.
    :param branch_loading:
        Branch loading ratio per branch.
    :param branch_active:
        Branch active state per branch.
    :param branch_rate:
        Branch thermal or contingency rating per branch.
    :param generator_p:
        Generator active power setpoint per generator.
    :param generator_pmin:
        Generator minimum active power per generator.
    :param generator_pmax:
        Generator maximum active power per generator.
    """

    __slots__ = (
        "_step_idx",
        "_remaining_steps",
        "_bus_voltage_magnitude",
        "_bus_voltage_angle",
        "_branch_loading",
        "_branch_active",
        "_branch_rate",
        "_generator_p",
        "_generator_pmin",
        "_generator_pmax",
    )

    def __init__(
        self,
        step_idx: int,
        remaining_steps: int,
        bus_voltage_magnitude: np.ndarray,
        bus_voltage_angle: np.ndarray,
        branch_loading: np.ndarray,
        branch_active: np.ndarray,
        branch_rate: np.ndarray,
        generator_p: np.ndarray,
        generator_pmin: np.ndarray,
        generator_pmax: np.ndarray,
    ) -> None:
        self._step_idx: int = step_idx
        self._remaining_steps: int = remaining_steps
        self._bus_voltage_magnitude: np.ndarray = bus_voltage_magnitude
        self._bus_voltage_angle: np.ndarray = bus_voltage_angle
        self._branch_loading: np.ndarray = branch_loading
        self._branch_active: np.ndarray = branch_active
        self._branch_rate: np.ndarray = branch_rate
        self._generator_p: np.ndarray = generator_p
        self._generator_pmin: np.ndarray = generator_pmin
        self._generator_pmax: np.ndarray = generator_pmax

    def get_step_idx(self) -> int:
        """
        Get the current step index.

        :return:
            Current step index.
        """

        return self._step_idx

    def get_remaining_steps(self) -> int:
        """
        Get the remaining step count.

        :return:
            Remaining number of steps.
        """

        return self._remaining_steps

    def get_bus_voltage_magnitude(self) -> np.ndarray:
        """
        Get the bus voltage magnitudes.

        :return:
            Voltage magnitude vector.
        """

        return self._bus_voltage_magnitude

    def get_bus_voltage_angle(self) -> np.ndarray:
        """
        Get the bus voltage angles.

        :return:
            Voltage angle vector.
        """

        return self._bus_voltage_angle

    def get_branch_loading(self) -> np.ndarray:
        """
        Get the branch loading vector.

        :return:
            Branch loading ratio vector.
        """

        return self._branch_loading

    def get_branch_active(self) -> np.ndarray:
        """
        Get the branch active state vector.

        :return:
            Branch active mask vector.
        """

        return self._branch_active

    def get_branch_rate(self) -> np.ndarray:
        """
        Get the branch rating vector.

        :return:
            Branch rating vector.
        """

        return self._branch_rate

    def get_generator_p(self) -> np.ndarray:
        """
        Get the generator active powers.

        :return:
            Generator active power vector.
        """

        return self._generator_p

    def get_generator_pmin(self) -> np.ndarray:
        """
        Get the generator minimum active powers.

        :return:
            Generator minimum active power vector.
        """

        return self._generator_pmin

    def get_generator_pmax(self) -> np.ndarray:
        """
        Get the generator maximum active powers.

        :return:
            Generator maximum active power vector.
        """

        return self._generator_pmax


def build_observation(nc: Any, pf_results: Any, step_idx: int, max_steps: int) -> ObservationData:
    """
    Build a typed observation from the latest PF state.

    :param nc:
        Numerical circuit produced by the VeraGrid compiler.
    :param pf_results:
        Power flow results computed for the current grid state.
    :param step_idx:
        Current control step index.
    :param max_steps:
        Episode maximum number of steps.
    :return:
        Structured observation object.
    """

    # The observation extracts the state variables that an operator policy can use
    # to judge security and choose the next corrective control.
    bus_voltage_complex: np.ndarray = pf_results.voltage
    bus_voltage_magnitude: np.ndarray = np.abs(bus_voltage_complex).astype(np.float64, copy=False)
    bus_voltage_angle: np.ndarray = np.angle(bus_voltage_complex).astype(np.float64, copy=False)
    branch_loading: np.ndarray = np.abs(pf_results.loading).astype(np.float64, copy=False)
    branch_active: np.ndarray = nc.passive_branch_data.active.astype(np.int8, copy=False)
    branch_rate: np.ndarray = nc.passive_branch_data.rates.astype(np.float64, copy=False)
    generator_p: np.ndarray = nc.generator_data.p.astype(np.float64, copy=False)
    generator_pmin: np.ndarray = nc.generator_data.pmin.astype(np.float64, copy=False)
    generator_pmax: np.ndarray = nc.generator_data.pmax.astype(np.float64, copy=False)
    remaining_steps: int = max_steps - step_idx

    return ObservationData(
        step_idx=step_idx,
        remaining_steps=remaining_steps,
        bus_voltage_magnitude=bus_voltage_magnitude,
        bus_voltage_angle=bus_voltage_angle,
        branch_loading=branch_loading,
        branch_active=branch_active,
        branch_rate=branch_rate,
        generator_p=generator_p,
        generator_pmin=generator_pmin,
        generator_pmax=generator_pmax,
    )


def flatten_observation(observation: ObservationData) -> np.ndarray:
    """
    Flatten the observation to a single numeric vector.

    :param observation:
        Structured observation object.
    :return:
        One-dimensional ``float32`` vector.
    """

    # The flattened vector is useful for a first baseline policy and keeps a stable
    # memory layout for RL tooling that expects dense tensors.
    vector_size: int = (
        observation.get_bus_voltage_magnitude().size
        + observation.get_bus_voltage_angle().size
        + observation.get_branch_loading().size
        + observation.get_branch_active().size
        + observation.get_branch_rate().size
        + observation.get_generator_p().size
        + observation.get_generator_pmin().size
        + observation.get_generator_pmax().size
        + 2
    )
    flat_vector: np.ndarray = np.empty(vector_size, dtype=np.float32)
    start_idx: int = 0
    end_idx: int = start_idx + observation.get_bus_voltage_magnitude().size
    flat_vector[start_idx:end_idx] = observation.get_bus_voltage_magnitude().astype(np.float32, copy=False)

    start_idx = end_idx
    end_idx = start_idx + observation.get_bus_voltage_angle().size
    flat_vector[start_idx:end_idx] = observation.get_bus_voltage_angle().astype(np.float32, copy=False)

    start_idx = end_idx
    end_idx = start_idx + observation.get_branch_loading().size
    flat_vector[start_idx:end_idx] = observation.get_branch_loading().astype(np.float32, copy=False)

    start_idx = end_idx
    end_idx = start_idx + observation.get_branch_active().size
    flat_vector[start_idx:end_idx] = observation.get_branch_active().astype(np.float32, copy=False)

    start_idx = end_idx
    end_idx = start_idx + observation.get_branch_rate().size
    flat_vector[start_idx:end_idx] = observation.get_branch_rate().astype(np.float32, copy=False)

    start_idx = end_idx
    end_idx = start_idx + observation.get_generator_p().size
    flat_vector[start_idx:end_idx] = observation.get_generator_p().astype(np.float32, copy=False)

    start_idx = end_idx
    end_idx = start_idx + observation.get_generator_pmin().size
    flat_vector[start_idx:end_idx] = observation.get_generator_pmin().astype(np.float32, copy=False)

    start_idx = end_idx
    end_idx = start_idx + observation.get_generator_pmax().size
    flat_vector[start_idx:end_idx] = observation.get_generator_pmax().astype(np.float32, copy=False)

    start_idx = end_idx
    flat_vector[start_idx] = float(observation.get_step_idx())
    flat_vector[start_idx + 1] = float(observation.get_remaining_steps())

    return flat_vector
