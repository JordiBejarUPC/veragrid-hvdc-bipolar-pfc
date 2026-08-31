# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Optional

import numpy as np

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.enumerations import DeviceType, FmiVersion, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var

from VeraGridEngine.IO.fmu.importer.bindings import (
    FmiThreeConfigurationSessionValues,
    FmiThreeFloat64ConfigurationValue,
    FmiThreeFloat64SessionValueSelector,
    FmiThreeUInt64ConfigurationValue,
    FmuImportConfig,
    FmuRefBinding,
    _build_fmi_three_configuration_session_values,
    _reject_indexed_fmu_ref_bindings,
    _validate_fmi_three_configuration_values,
    resolve_fmi_three_float64_session_value_selectors,
)
from VeraGridEngine.IO.fmu.importer.device_config import load_fmu_me_device_config, restore_fmu_me_spec_from_record
from VeraGridEngine.IO.fmu.importer.errors import FmuModeError
from VeraGridEngine.IO.fmu.importer.experimental_cs import (
    _build_template_block,
    _ensure_emt_external_mapping_keys,
)
from VeraGridEngine.IO.fmu.importer.model_description import FmuInterfaceMode, FmuModelDescription, FmuVariableDescription, read_fmu_model_description
from VeraGridEngine.IO.fmu.importer.runtime_host import FmuRuntimeHost, open_fmu_runtime_host
from VeraGridEngine.IO.fmu.importer.runtime_profile import (
    FmiThreeWorkerFloat64Profile,
    resolve_fmi_three_worker_float64_profile,
    validate_fmi_three_model_exchange_worker_profile,
)
from VeraGridEngine.IO.fmu.importer.runtime_coordinator import (
    FmiThreeModelExchangeCoordinator,
)
from VeraGridEngine.IO.fmu.importer.runtime_session import (
    FmiThreeFloat64Session,
    open_fmi_three_float64_session,
)
from VeraGridEngine.IO.fmu.importer.runtime_worker_host import (
    FmiThreeWorkerHostLimits,
)


class FmuMeDomain(str, Enum):
    """Enumerate the VeraGrid domains that may host FMU ME devices.

    :return: None.
    """

    RMS = "rms"
    EMT = "emt"


class FmuMeIntegrationMethod(str, Enum):
    """Enumerate the internal predictor methods available for FMU ME devices.

    :return: None.
    """

    EXPLICIT_EULER = "explicit_euler"


class FmuMeDeviceSpec:
    """Store the runtime metadata required to execute one FMU ME device.

    :param domain: VeraGrid domain that will consume the FMU.
    :param config: FMU runtime configuration.
    :param device_tpe: VeraGrid device type.
    :param input_variable_names: Ordered FMU input names.
    :param output_variable_names: Ordered FMU output names.
    :param state_variable_names: Ordered FMU continuous-state names.
    :param derivative_variable_names: Ordered FMU derivative names.
    :param integration_method: Internal predictor used by the adapter.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param float64_profile: Derived FMI 3 worker shape profile, when used.
    :param maximum_event_iterations: Positive Event Mode convergence bound.
    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    """

    __slots__ = (
        "domain",
        "config",
        "device_tpe",
        "input_variable_names",
        "output_variable_names",
        "state_variable_names",
        "derivative_variable_names",
        "integration_method",
        "worker_limits",
        "float64_profile",
        "maximum_event_iterations",
        "input_bindings",
        "output_bindings",
        "output_defaults",
        "output_param_uids",
        "configuration_float64_values",
        "configuration_uint64_values",
    )

    def __init__(
        self,
        domain: FmuMeDomain,
        config: FmuImportConfig,
        device_tpe: DeviceType,
        input_variable_names: tuple[str, ...],
        output_variable_names: tuple[str, ...],
        state_variable_names: tuple[str, ...],
        derivative_variable_names: tuple[str, ...],
        integration_method: FmuMeIntegrationMethod,
        worker_limits: FmiThreeWorkerHostLimits | None,
        float64_profile: FmiThreeWorkerFloat64Profile | None,
        input_bindings: tuple[FmuRefBinding, ...],
        output_bindings: tuple[FmuRefBinding, ...],
        output_defaults: dict[VarPowerFlowReferenceType, float],
        output_param_uids: dict[VarPowerFlowReferenceType, int],
        maximum_event_iterations: int = 32,
        configuration_float64_values: tuple[
            FmiThreeFloat64ConfigurationValue, ...
        ] = tuple(),
        configuration_uint64_values: tuple[
            FmiThreeUInt64ConfigurationValue, ...
        ] = tuple(),
    ) -> None:
        """Store the runtime FMU ME specification.

        :param domain: VeraGrid domain that consumes the FMU.
        :param config: Source and runtime import configuration.
        :param device_tpe: VeraGrid device type receiving the adapter.
        :param input_variable_names: Ordered FMU input names.
        :param output_variable_names: Ordered FMU output names.
        :param state_variable_names: Ordered continuous-state names.
        :param derivative_variable_names: Ordered continuous-derivative names.
        :param integration_method: Predictor selected by the current adapter.
        :param worker_limits: Explicit FMI 3 worker supervision policy.
        :param float64_profile: Derived FMI 3 worker shape profile.
        :param maximum_event_iterations: Positive Event Mode convergence bound.
        :param input_bindings: Ordered VeraGrid-to-FMU bindings.
        :param output_bindings: Ordered FMU-to-VeraGrid bindings.
        :param output_defaults: Output fallbacks used before the first sample.
        :param output_param_uids: Runtime output-parameter identifiers.
        :param configuration_float64_values: Structural Float64 declarations.
        :param configuration_uint64_values: Structural UInt64 declarations.
        :return: None.
        """

        self.domain: FmuMeDomain = domain
        self.config: FmuImportConfig = config
        self.device_tpe: DeviceType = device_tpe
        self.input_variable_names: tuple[str, ...] = input_variable_names
        self.output_variable_names: tuple[str, ...] = output_variable_names
        self.state_variable_names: tuple[str, ...] = state_variable_names
        self.derivative_variable_names: tuple[str, ...] = derivative_variable_names
        self.integration_method: FmuMeIntegrationMethod = integration_method
        self.worker_limits: FmiThreeWorkerHostLimits | None = worker_limits
        self.float64_profile: FmiThreeWorkerFloat64Profile | None = float64_profile
        if (
            isinstance(maximum_event_iterations, int)
            and not isinstance(maximum_event_iterations, bool)
            and 1 <= maximum_event_iterations <= 1024
        ):
            self.maximum_event_iterations: int = maximum_event_iterations
        else:
            raise ValueError(
                "FMI ME maximum Event Mode iterations must be an integer between 1 and 1024"
            )
        self.input_bindings: tuple[FmuRefBinding, ...] = input_bindings
        self.output_bindings: tuple[FmuRefBinding, ...] = output_bindings
        self.output_defaults: dict[VarPowerFlowReferenceType, float] = output_defaults
        self.output_param_uids: dict[VarPowerFlowReferenceType, int] = output_param_uids
        _validate_fmi_three_configuration_values(
            configuration_float64_values=configuration_float64_values,
            configuration_uint64_values=configuration_uint64_values,
        )
        self.configuration_float64_values: tuple[
            FmiThreeFloat64ConfigurationValue, ...
        ] = tuple(configuration_float64_values)
        self.configuration_uint64_values: tuple[
            FmiThreeUInt64ConfigurationValue, ...
        ] = tuple(configuration_uint64_values)


class FmuMeDeviceAdapter:
    """Execute one FMU ME device with a light internal predictor.

    :param spec: Runtime specification of the FMU ME device.
    """

    __slots__ = (
        "spec",
        "runtime_host",
        "fmi_three_coordinator",
        "state_vector",
        "pending_time",
        "pending_candidate_state_values",
        "pending_candidate_event_indicators",
        "pending_accepted_time",
        "pending_accepted_state_values",
        "pending_accepted_input_values",
        "localized_state_event_time",
        "initialized",
    )

    def __init__(self, spec: FmuMeDeviceSpec) -> None:
        """Store the FMU ME runtime adapter.

        :return: None.
        """

        self.spec: FmuMeDeviceSpec = spec
        self.runtime_host: Optional[FmuRuntimeHost] = None
        self.fmi_three_coordinator: FmiThreeModelExchangeCoordinator | None = None
        self.state_vector: Optional[np.ndarray] = None
        self.pending_time: float | None = None
        self.pending_candidate_state_values: tuple[float, ...] | None = None
        self.pending_candidate_event_indicators: tuple[float, ...] | None = None
        self.pending_accepted_time: float | None = None
        self.pending_accepted_state_values: tuple[float, ...] | None = None
        self.pending_accepted_input_values: tuple[float, ...] | None = None
        self.localized_state_event_time: float | None = None
        self.initialized: bool = False

    def _clear_pending_state_event_data(self) -> None:
        """Clear candidate data used only by state-event localization.

        :return: None.
        """

        self.pending_time = None
        self.pending_candidate_state_values = None
        self.pending_candidate_event_indicators = None
        self.pending_accepted_time = None
        self.pending_accepted_state_values = None
        self.pending_accepted_input_values = None

    def _build_ordered_writable_values(
        self,
        input_values: dict[str, float],
    ) -> tuple[float, ...]:
        """Order a complete scalar input vector for one bound ME runtime.

        :param input_values: Scalar values indexed by the bound FMU input names.
        :return: Values ordered exactly like ``spec.input_variable_names``.
        :raises KeyError: If one required bound input is absent.
        :raises ValueError: If an unbound input name is present.
        """

        ordered_values: list[float] = [0.0] * len(self.spec.input_variable_names)
        input_index: int
        for input_index in range(len(self.spec.input_variable_names)):
            input_name: str = self.spec.input_variable_names[input_index]
            input_value: float | None = input_values.get(input_name, None)
            if input_value is not None:
                ordered_values[input_index] = float(input_value)
            else:
                raise KeyError(
                    f"FMI Model Exchange input {input_name!r} has no value"
                )
        if len(input_values) == len(self.spec.input_variable_names):
            pass
        else:
            raise ValueError(
                "FMI Model Exchange initialization contains an unbound input"
            )
        return tuple(ordered_values)

    def _map_named_output_values(
        self,
        readable_values: tuple[float, ...],
    ) -> dict[str, float]:
        """Map ordered readings to the adapter's existing named API.

        :param readable_values: Values ordered like ``spec.output_variable_names``.
        :return: Scalar readings indexed by bound FMU output name.
        """

        if len(readable_values) == len(self.spec.output_variable_names):
            pass
        else:
            raise RuntimeError(
                "Model Exchange readings do not match the declared output names"
            )
        unique_output_names: set[str] = set(self.spec.output_variable_names)
        if len(unique_output_names) == len(self.spec.output_variable_names):
            pass
        else:
            raise FmuModeError(
                "The named ME output API cannot represent repeated "
                "array-variable bindings"
            )
        mapped_values: dict[str, float] = dict()
        output_index: int
        for output_index in range(len(self.spec.output_variable_names)):
            mapped_values[self.spec.output_variable_names[output_index]] = float(
                readable_values[output_index]
            )
        return mapped_values

    def _map_bound_output_values(
        self,
        output_values: tuple[float, ...],
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Map ordered runtime values onto the declared VeraGrid references.

        :param output_values: Values ordered exactly like ``spec.output_bindings``.
        :return: Scalar readings indexed by VeraGrid output reference.
        :raises RuntimeError: If runtime and binding cardinalities differ.
        """

        if len(output_values) == len(self.spec.output_bindings):
            pass
        else:
            raise RuntimeError(
                "FMU Model Exchange readings do not match the output bindings"
            )
        mapped_values: dict[VarPowerFlowReferenceType, float] = dict()
        binding_index: int
        for binding_index in range(len(self.spec.output_bindings)):
            binding: FmuRefBinding = self.spec.output_bindings[binding_index]
            mapped_values[binding.reference] = float(output_values[binding_index])
        return mapped_values

    def _evaluate_ordered_output_values(
        self,
        time_value: float,
        input_values: dict[str, float],
    ) -> tuple[float, ...]:
        """Evaluate outputs while preserving their declared binding order.

        :param time_value: Current evaluation time.
        :param input_values: Complete scalar FMU input values.
        :return: Output values aligned with names or selected device bindings.
        """

        if self.runtime_host is not None:
            self.runtime_host.set_time(time_value)
            self._apply_inputs(input_values)
            if self.state_vector is not None:
                self.runtime_host.set_continuous_states(self.state_vector.tolist())
            else:
                pass
            named_values: dict[str, float] = self.runtime_host.get_real(
                list(self.spec.output_variable_names)
            )
            ordered_values: list[float] = [0.0] * len(
                self.spec.output_variable_names
            )
            output_index: int
            for output_index in range(len(self.spec.output_variable_names)):
                output_name: str = self.spec.output_variable_names[output_index]
                ordered_values[output_index] = float(named_values[output_name])
            return tuple(ordered_values)
        else:
            if self.fmi_three_coordinator is not None:
                state_values: tuple[float, ...] = self._get_fmi_three_state_values()
                derivative_values: tuple[float, ...]
                readable_values: tuple[float, ...]
                derivative_values, readable_values = (
                    self.fmi_three_coordinator.evaluate_probe(
                        time_value=time_value,
                        continuous_state_values=state_values,
                        writable_values=(
                            self._build_ordered_writable_values(input_values)
                        ),
                    )
                )
                return readable_values
            else:
                raise RuntimeError(
                    "FMU ME adapter must be initialized before output evaluation"
                )

    def _get_fmi_three_state_values(self) -> tuple[float, ...]:
        """Copy the accepted NumPy state into the isolated session format.

        :return: Complete continuous-state vector owned by the adapter.
        :raises RuntimeError: If initialized FMI 3 state ownership was lost.
        """

        if self.state_vector is not None:
            pass
        else:
            raise RuntimeError("FMI 3 ME adapter lost its state vector")
        state_values: list[float] = [0.0] * self.state_vector.size
        state_index: int
        for state_index in range(self.state_vector.size):
            state_values[state_index] = float(self.state_vector[state_index])
        return tuple(state_values)

    def initialize(
        self,
        start_time: float,
        input_values: dict[str, float] | None = None,
        start_values: dict[str, float] | None = None,
    ) -> None:
        """Open and initialize the FMU ME runtime.

        :param start_time: Initial simulation time.
        :param input_values: FMU input values applied during initialization.
        :param start_values: Additional FMU start values.
        :return: None.
        """

        start_values_payload: dict[str, float] = dict()
        if start_values is not None:
            start_values_payload.update(start_values)
        else:
            pass
        if input_values is not None:
            start_values_payload.update(input_values)
        else:
            pass

        if self.initialized:
            raise RuntimeError("FMU ME adapter is already initialized")
        else:
            pass
        if self.spec.float64_profile is None:
            has_fmi_three_configuration: bool = (
                len(self.spec.configuration_float64_values) > 0
                or len(self.spec.configuration_uint64_values) > 0
            )
            if has_fmi_three_configuration:
                raise FmuModeError(
                    "FMI 3 Configuration Mode declarations require FMI 3"
                )
            else:
                pass
            _reject_indexed_fmu_ref_bindings(
                input_bindings=self.spec.input_bindings,
                output_bindings=self.spec.output_bindings,
            )
            # FMI 2 keeps the established in-process runtime until its own
            # isolation increment is explicitly designed.
            self.runtime_host = open_fmu_runtime_host(self.spec.config)
            self.runtime_host.initialize(
                start_time=start_time,
                start_values=start_values_payload,
            )
            self.state_vector = np.array(
                self.runtime_host.get_continuous_states(),
                dtype=float,
            )
        else:
            # A device scalar cannot provide an incomplete native input array.
            # Output arrays are safe because the session reads their complete
            # vectors before selecting device-bound row-major elements.
            _reject_indexed_fmu_ref_bindings(
                input_bindings=self.spec.input_bindings,
                output_bindings=tuple(),
            )
            if self.spec.worker_limits is not None:
                worker_limits: FmiThreeWorkerHostLimits = self.spec.worker_limits
            else:
                raise RuntimeError("FMI 3 ME device spec lost its worker limits")

            readable_variable_names: tuple[str, ...]
            readable_value_selectors: tuple[
                FmiThreeFloat64SessionValueSelector, ...
            ]
            if len(self.spec.output_bindings) > 0:
                (
                    readable_variable_names,
                    readable_value_selectors,
                ) = resolve_fmi_three_float64_session_value_selectors(
                    self.spec.output_bindings
                )
            else:
                # Preserve the established direct adapter API when no device
                # bindings exist; this path remains scalar-name based.
                readable_variable_names = self.spec.output_variable_names
                readable_value_selectors = tuple()

            configuration_session_values: (
                FmiThreeConfigurationSessionValues
            ) = _build_fmi_three_configuration_session_values(
                configuration_float64_values=(
                    self.spec.configuration_float64_values
                ),
                configuration_uint64_values=(
                    self.spec.configuration_uint64_values
                ),
            )
            initial_writable_values: tuple[float, ...] = (
                self._build_ordered_writable_values(start_values_payload)
            )
            session: FmiThreeFloat64Session = open_fmi_three_float64_session(
                config=self.spec.config,
                instance_name="veragrid-fmi-three-me-device",
                readable_variable_names=readable_variable_names,
                writable_variable_names=self.spec.input_variable_names,
                limits=worker_limits,
                float64_profile=self.spec.float64_profile,
                configuration_variable_names=(
                    configuration_session_values.float64_variable_names
                ),
                configuration_uint64_variable_names=(
                    configuration_session_values.uint64_variable_names
                ),
                readable_value_selectors=readable_value_selectors,
            )
            try:
                # Dimension controllers settle before row-major Float64
                # declarations and output selectors are validated.
                session.configure_uint64(
                    configuration_uint64_values=(
                        configuration_session_values.uint64_values
                    )
                )
                session.configure(
                    configuration_float64_values=(
                        configuration_session_values.float64_values
                    )
                )
                coordinator: FmiThreeModelExchangeCoordinator = (
                    FmiThreeModelExchangeCoordinator(
                        session=session,
                        maximum_event_iterations=(
                            self.spec.maximum_event_iterations
                        ),
                    )
                )
                state_values: tuple[float, ...]
                readable_values: tuple[float, ...]
                state_values, readable_values = coordinator.initialize(
                    start_time=start_time,
                    stop_time=None,
                    relative_tolerance=self.spec.config.relative_tolerance,
                    initial_writable_values=initial_writable_values,
                )
            except Exception:
                session.close()
                raise
            self.fmi_three_coordinator = coordinator
            self.state_vector = np.array(state_values, dtype=float)
        self.initialized = True

    def get_state_vector(self) -> np.ndarray:
        """Return a copy of the current continuous-state vector.

        :return: Copy of the current state vector.
        """

        if self.state_vector is None:
            return np.zeros(0, dtype=float)
        else:
            return np.array(self.state_vector, dtype=float)

    def set_state_vector(self, values: np.ndarray) -> None:
        """Replace the adapter continuous-state vector and propagate it to the FMU.

        FMI 2 propagates the vector immediately. The isolated FMI 3 session
        receives it with time and inputs at the next evaluation point.

        :param values: New continuous-state vector.
        :return: None.
        """

        if self.runtime_host is not None:
            state_values: np.ndarray = np.array(values, dtype=float)
            self.runtime_host.set_continuous_states(state_values.tolist())
            self.state_vector = state_values
        else:
            if self.fmi_three_coordinator is not None:
                # The isolated session receives the complete accepted state at
                # the next evaluation point, together with time and inputs.
                self.state_vector = np.array(values, dtype=float)
            else:
                raise RuntimeError(
                    "FMU ME adapter must be initialized before setting states"
                )

    def _apply_inputs(self, input_values: dict[str, float]) -> None:
        """Apply one input vector to the FMU runtime.

        :param input_values: FMU input values.
        :return: None.
        """

        if self.runtime_host is None:
            raise RuntimeError("FMU ME adapter must be initialized before applying inputs")
        else:
            if len(input_values) > 0:
                self.runtime_host.set_real(input_values)
            else:
                pass

    def evaluate_derivatives(self, time_value: float, input_values: dict[str, float]) -> np.ndarray:
        """Evaluate the FMU derivative vector at the provided time and inputs.

        :param time_value: Current evaluation time.
        :param input_values: FMU input values.
        :return: Derivative vector.
        """

        if self.runtime_host is not None:
            self.runtime_host.set_time(time_value)
            self._apply_inputs(input_values)
            if self.state_vector is not None:
                self.runtime_host.set_continuous_states(self.state_vector.tolist())
            else:
                pass
            derivative_values: list[float] = self.runtime_host.get_derivatives()
            return np.array(derivative_values, dtype=float)
        else:
            if self.fmi_three_coordinator is not None:
                state_values: tuple[float, ...] = (
                    self._get_fmi_three_state_values()
                )
                derivative_values_tuple: tuple[float, ...]
                readable_values: tuple[float, ...]
                derivative_values_tuple, readable_values = (
                    self.fmi_three_coordinator.evaluate_probe(
                        time_value=time_value,
                        continuous_state_values=state_values,
                        writable_values=(
                            self._build_ordered_writable_values(input_values)
                        ),
                    )
                )
                return np.array(derivative_values_tuple, dtype=float)
            else:
                raise RuntimeError(
                    "FMU ME adapter must be initialized before derivative evaluation"
                )

    def evaluate_outputs(self, time_value: float, input_values: dict[str, float]) -> dict[str, float]:
        """Evaluate the FMU output vector at the provided time and inputs.

        :param time_value: Current evaluation time.
        :param input_values: FMU input values.
        :return: Output values indexed by FMU variable name.
        """

        ordered_values: tuple[float, ...] = self._evaluate_ordered_output_values(
            time_value=time_value,
            input_values=input_values,
        )
        return self._map_named_output_values(ordered_values)

    def _evaluate_bound_outputs(
        self,
        time_value: float,
        input_values: dict[str, float],
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Evaluate outputs aligned with the owning device bindings.

        Unlike the compatibility API keyed by FMU name, this path can retain
        multiple selected elements from the same FMU array.

        :param time_value: Current evaluation time.
        :param input_values: Complete scalar FMU input values.
        :return: Output values indexed by VeraGrid reference.
        """

        ordered_values: tuple[float, ...] = self._evaluate_ordered_output_values(
            time_value=time_value,
            input_values=input_values,
        )
        return self._map_bound_output_values(ordered_values)

    def _advance_explicit_euler_state(
        self,
        current_time: float,
        step_size: float,
        input_values: dict[str, float],
    ) -> tuple[float, ...] | None:
        """Advance only the externally owned explicit-Euler state vector.

        :param current_time: Current accepted integration time.
        :param step_size: Positive integration step length.
        :param input_values: Complete scalar FMU input values.
        :return: Candidate readable values for FMI 3, otherwise ``None``.
        """

        if self.fmi_three_coordinator is not None:
            state_values: tuple[float, ...] = self._get_fmi_three_state_values()
            writable_values: tuple[float, ...] = (
                self._build_ordered_writable_values(input_values)
            )
            start_probe: tuple[tuple[float, ...], tuple[float, ...]] = (
                self.fmi_three_coordinator.evaluate_probe(
                    time_value=current_time,
                    continuous_state_values=state_values,
                    writable_values=writable_values,
                )
            )
            derivative_values: tuple[float, ...] = start_probe[0]
            candidate_state: np.ndarray = np.array(state_values, dtype=float)
            if candidate_state.size > 0:
                candidate_state += step_size * np.array(
                    derivative_values,
                    dtype=float,
                )
            else:
                pass
            candidate_result: tuple[
                tuple[float, ...],
                tuple[float, ...],
                tuple[float, ...],
            ] = self.fmi_three_coordinator.evaluate_candidate(
                time_value=current_time + step_size,
                continuous_state_values=tuple(candidate_state.tolist()),
                writable_values=writable_values,
            )
            candidate_readable_values: tuple[float, ...] = candidate_result[1]
            candidate_event_indicators: tuple[float, ...] = candidate_result[2]
            self.state_vector = candidate_state
            self.pending_time = current_time + step_size
            self.pending_candidate_state_values = tuple(candidate_state.tolist())
            self.pending_candidate_event_indicators = candidate_event_indicators

            # A previously localized source event is processed before the
            # coupled Newton solve at that exact target.  Its post-event
            # outputs therefore participate in the same-time algebraic solve.
            localized_event_time: float | None = self.localized_state_event_time
            candidate_time: float = current_time + step_size
            event_time_scale: float = max(
                abs(candidate_time),
                abs(localized_event_time) if localized_event_time is not None else 0.0,
                1.0,
            )
            machine_time_tolerance: float = 16.0 * math.ulp(event_time_scale)
            if (
                localized_event_time is not None
                and abs(candidate_time - localized_event_time)
                <= machine_time_tolerance
            ):
                resolved_states: tuple[float, ...]
                resolved_readable_values: tuple[float, ...]
                resolved_states, resolved_readable_values = (
                    self.fmi_three_coordinator.accept_candidate(
                        importer_detected_event=True
                    )
                )
                self.state_vector = np.array(resolved_states, dtype=float)
                self.localized_state_event_time = None
                self._clear_pending_state_event_data()
                return resolved_readable_values
            else:
                return candidate_readable_values
        else:
            # FMI 2 has no coordinator transaction, so retain only the accepted
            # continuous point needed when another FMI 3 device localizes an
            # earlier global event in the same coupled substep.
            accepted_state_values: tuple[float, ...] = tuple(
                self.get_state_vector().tolist()
            )
            self.pending_accepted_time = float(current_time)
            self.pending_accepted_state_values = accepted_state_values
            self.pending_accepted_input_values = (
                self._build_ordered_writable_values(input_values)
            )
            derivatives: np.ndarray = self.evaluate_derivatives(
                current_time,
                input_values,
            )
            state_vector: np.ndarray = self.get_state_vector()
            if state_vector.size > 0:
                state_vector = state_vector + step_size * derivatives
                self.set_state_vector(state_vector)
            else:
                pass
            self.pending_time = current_time + step_size
            return None

    def _restore_fmi_two_pending_point(self) -> tuple[float, ...]:
        """Restore one FMI 2 ME point after a coupled substep is rejected.

        :return: Readable values recomputed at the restored accepted point.
        :raises FmuModeError: If the minimal pending snapshot is incomplete.
        """

        accepted_time: float | None = self.pending_accepted_time
        accepted_states: tuple[float, ...] | None = (
            self.pending_accepted_state_values
        )
        accepted_inputs: tuple[float, ...] | None = (
            self.pending_accepted_input_values
        )
        if (
            self.runtime_host is not None
            and accepted_time is not None
            and accepted_states is not None
            and accepted_inputs is not None
            and len(accepted_inputs) == len(self.spec.input_variable_names)
        ):
            pass
        else:
            raise FmuModeError(
                "FMI 2 ME rollback requires a complete accepted point"
            )

        restored_inputs: dict[str, float] = dict()
        input_index: int
        for input_index in range(len(self.spec.input_variable_names)):
            restored_inputs[self.spec.input_variable_names[input_index]] = (
                accepted_inputs[input_index]
            )
        self.state_vector = np.array(accepted_states, dtype=float)
        restored_values: tuple[float, ...] = self._evaluate_ordered_output_values(
            time_value=accepted_time,
            input_values=restored_inputs,
        )
        self._clear_pending_state_event_data()
        return restored_values

    def resolve_pending_step(
        self,
        accepted: bool,
        importer_detected_event: bool = False,
    ) -> tuple[float, ...] | None:
        """Accept or reject one prepared Model Exchange candidate.

        :param accepted: Whether the owning numerical solver accepted the step.
        :param importer_detected_event: Whether an event was localized here.
        :return: Restored FMI 2 or resolved FMI 3 readings when applicable.
        """

        coordinator: FmiThreeModelExchangeCoordinator | None = (
            self.fmi_three_coordinator
        )
        if coordinator is not None and coordinator.has_pending_candidate():
            resolved_states: tuple[float, ...]
            resolved_readable_values: tuple[float, ...]
            if accepted:
                next_event_time: float | None = coordinator.get_next_event_time()
                time_event_is_due: bool = (
                    next_event_time is not None
                    and self.pending_time is not None
                    and self.pending_time >= next_event_time
                )
                resolved_states, resolved_readable_values = (
                    coordinator.accept_candidate(
                        importer_detected_event=(
                            importer_detected_event or time_event_is_due
                        )
                    )
                )
            else:
                coordinator.reject_candidate()
                accepted_point: tuple[
                    float,
                    tuple[float, ...],
                    tuple[float, ...],
                    tuple[float, ...],
                    tuple[float, ...],
                    tuple[float, ...],
                ] = coordinator.get_accepted_point()
                resolved_states = accepted_point[1]
                resolved_readable_values = accepted_point[3]
            self.state_vector = np.array(resolved_states, dtype=float)
            self._clear_pending_state_event_data()
            return resolved_readable_values
        else:
            if (
                self.runtime_host is not None
                and self.pending_accepted_time is not None
            ):
                if accepted:
                    self._clear_pending_state_event_data()
                    return None
                else:
                    return self._restore_fmi_two_pending_point()
            else:
                return None

    def get_pending_state_event_time(
        self,
        time_tolerance: float,
        maximum_iterations: int,
    ) -> float | None:
        """Locate the first domain change inside the pending ME candidate.

        The current explicit-Euler predictor is linear in the continuous state,
        so midpoint states are interpolated consistently with that predictor.
        A shared bracket is reduced to the earliest indicator event without
        entering Event Mode.

        :param time_tolerance: Positive absolute event-time tolerance in seconds.
        :param maximum_iterations: Positive bisection iteration bound.
        :return: Earliest localized event time, or ``None`` without a crossing.
        """

        normalized_tolerance: float = float(time_tolerance)
        if math.isfinite(normalized_tolerance) and normalized_tolerance > 0.0:
            pass
        else:
            raise ValueError(
                "FMI ME state-event time tolerance must be finite and positive"
            )
        if (
            isinstance(maximum_iterations, int)
            and not isinstance(maximum_iterations, bool)
            and maximum_iterations > 0
        ):
            pass
        else:
            raise ValueError(
                "FMI ME state-event iteration bound must be a positive integer"
            )

        coordinator: FmiThreeModelExchangeCoordinator | None = (
            self.fmi_three_coordinator
        )
        candidate_time: float | None = self.pending_time
        candidate_states: tuple[float, ...] | None = (
            self.pending_candidate_state_values
        )
        candidate_indicators: tuple[float, ...] | None = (
            self.pending_candidate_event_indicators
        )
        if (
            coordinator is not None
            and coordinator.has_pending_candidate()
            and candidate_time is not None
            and candidate_states is not None
            and candidate_indicators is not None
        ):
            pass
        else:
            return None

        accepted_point: tuple[
            float,
            tuple[float, ...],
            tuple[float, ...],
            tuple[float, ...],
            tuple[float, ...],
            tuple[float, ...],
        ] = coordinator.get_accepted_point()
        accepted_time: float = accepted_point[0]
        accepted_states: tuple[float, ...] = accepted_point[1]
        accepted_indicators: tuple[float, ...] = accepted_point[4]
        interval_width: float = candidate_time - accepted_time
        if (
            len(accepted_states) == len(candidate_states)
            and len(accepted_indicators) == len(candidate_indicators)
            and math.isfinite(accepted_time)
            and math.isfinite(candidate_time)
            and math.isfinite(interval_width)
            and interval_width > 0.0
        ):
            pass
        else:
            raise FmuModeError(
                "FMI ME state-event localization requires a finite positive-width "
                "candidate interval"
            )

        time_scale: float = max(abs(accepted_time), abs(candidate_time), 1.0)
        effective_tolerance: float = max(
            normalized_tolerance,
            16.0 * math.ulp(time_scale),
        )
        if math.isfinite(effective_tolerance) and effective_tolerance > 0.0:
            pass
        else:
            raise ValueError(
                "FMI ME effective state-event tolerance must be finite and positive"
            )

        # Determine the exact binary bisection count without forming a width to
        # tolerance ratio that could overflow or underflow.  Insufficient
        # bounds fail before any worker probe changes native state.
        required_iterations: int = 0
        if interval_width > effective_tolerance:
            width_mantissa: float
            width_exponent: int
            tolerance_mantissa: float
            tolerance_exponent: int
            width_mantissa, width_exponent = math.frexp(interval_width)
            tolerance_mantissa, tolerance_exponent = math.frexp(
                effective_tolerance
            )
            required_iterations = width_exponent - tolerance_exponent
            if width_mantissa > tolerance_mantissa:
                required_iterations += 1
            else:
                pass
        else:
            pass
        if required_iterations <= maximum_iterations:
            pass
        else:
            raise FmuModeError(
                "FMI ME state-event localization bound cannot meet its tolerance"
            )

        crossing_indices: tuple[int, ...] = (
            self._get_pending_state_event_crossing_indices(
                accepted_indicators=accepted_indicators,
                candidate_indicators=candidate_indicators,
            )
        )
        crossing_count: int = len(crossing_indices)
        if crossing_count == 0:
            return None
        else:
            pass

        # One shared bracket locates the earliest crossing among every indicator
        # whose endpoint domain differs.  This keeps the worker traffic bounded
        # by the configured iteration cap rather than multiplying it by the
        # number of event indicators in one FMU.
        lower_time: float = accepted_time
        upper_time: float = candidate_time
        midpoint_states_list: list[float] = [0.0] * len(accepted_states)
        iteration_index: int = 0
        while iteration_index < required_iterations:
            bracket_width: float = upper_time - lower_time
            midpoint_time: float = lower_time + bracket_width * 0.5
            if lower_time < midpoint_time < upper_time:
                pass
            else:
                # Adjacent binary floats are already at the numerical floor;
                # the finite upper endpoint is the conservative event bracket.
                return upper_time
            interpolation_fraction: float = (
                (midpoint_time - accepted_time)
                / interval_width
            )
            state_index: int
            for state_index in range(len(accepted_states)):
                midpoint_states_list[state_index] = (
                    accepted_states[state_index]
                    + interpolation_fraction
                    * (
                        candidate_states[state_index]
                        - accepted_states[state_index]
                    )
                )
            midpoint_indicators: tuple[float, ...] = (
                coordinator.evaluate_event_indicators_probe(
                    time_value=midpoint_time,
                    continuous_state_values=tuple(midpoint_states_list),
                )
            )
            if len(midpoint_indicators) == len(accepted_indicators):
                pass
            else:
                raise FmuModeError(
                    "FMI ME event-indicator cardinality changed during localization"
                )

            crossing_reached: bool = False
            crossing_position: int = 0
            while crossing_position < crossing_count and not crossing_reached:
                event_indicator_index: int = crossing_indices[crossing_position]
                accepted_is_positive: bool = (
                    accepted_indicators[event_indicator_index] > 0.0
                )
                midpoint_is_positive: bool = (
                    midpoint_indicators[event_indicator_index] > 0.0
                )
                if midpoint_is_positive != accepted_is_positive:
                    crossing_reached = True
                else:
                    crossing_position += 1
            if crossing_reached:
                upper_time = midpoint_time
            else:
                lower_time = midpoint_time
            iteration_index += 1
        if (upper_time - lower_time) <= effective_tolerance:
            return upper_time
        else:
            raise FmuModeError(
                "FMI ME state-event localization exceeded its iteration bound"
            )

    def _get_pending_state_event_crossing_indices(
        self,
        accepted_indicators: tuple[float, ...] | None = None,
        candidate_indicators: tuple[float, ...] | None = None,
    ) -> tuple[int, ...]:
        """Return indicators whose FMI sign domains differ at the endpoints.

        :param accepted_indicators: Optional accepted indicators already read by
            the localization caller.
        :param candidate_indicators: Optional candidate indicators already read
            by the localization caller.
        :return: Ordered indices changing between ``z > 0`` and ``z <= 0``.
        """

        coordinator: FmiThreeModelExchangeCoordinator | None = (
            self.fmi_three_coordinator
        )
        if coordinator is not None and coordinator.has_pending_candidate():
            pass
        else:
            return tuple()
        if accepted_indicators is None:
            accepted_indicators = coordinator.get_accepted_point()[4]
        else:
            pass
        if candidate_indicators is None:
            candidate_indicators = self.pending_candidate_event_indicators
        else:
            pass
        if candidate_indicators is not None:
            pass
        else:
            raise FmuModeError(
                "FMI ME state-event detection lost its candidate indicators"
            )
        if len(accepted_indicators) == len(candidate_indicators):
            pass
        else:
            raise FmuModeError(
                "FMI ME event-indicator cardinality changed inside one step"
            )

        crossing_indices: list[int] = [0] * len(accepted_indicators)
        crossing_count: int = 0
        indicator_index: int
        for indicator_index in range(len(accepted_indicators)):
            accepted_is_positive: bool = accepted_indicators[indicator_index] > 0.0
            candidate_is_positive: bool = candidate_indicators[indicator_index] > 0.0
            if accepted_is_positive != candidate_is_positive:
                crossing_indices[crossing_count] = indicator_index
                crossing_count += 1
            else:
                pass
        return tuple(crossing_indices[:crossing_count])

    def prepare_state_event_retry(
        self,
        event_time: float | None,
    ) -> tuple[float, ...]:
        """Reject the pending endpoint and optionally arm a localized event.

        :param event_time: Global retry time for a source event, or ``None``
            when this FMU only participates in the global rollback.
        :return: Readable values restored from the accepted point.
        """

        coordinator: FmiThreeModelExchangeCoordinator | None = (
            self.fmi_three_coordinator
        )
        restored_readable_values: tuple[float, ...] | None
        if coordinator is not None and coordinator.has_pending_candidate():
            restored_readable_values = self.resolve_pending_step(accepted=False)
        else:
            if self.runtime_host is not None and event_time is None:
                restored_readable_values = self._restore_fmi_two_pending_point()
            else:
                raise FmuModeError(
                    "FMI ME state-event retry requires a pending candidate"
                )
        if restored_readable_values is not None:
            pass
        else:
            raise FmuModeError(
                "FMI ME state-event retry did not restore readable values"
            )
        if event_time is None:
            self.localized_state_event_time = None
        else:
            normalized_event_time: float = float(event_time)
            accepted_time: float = coordinator.get_accepted_point()[0]
            if (
                math.isfinite(normalized_event_time)
                and normalized_event_time > accepted_time
            ):
                self.localized_state_event_time = normalized_event_time
            else:
                raise ValueError(
                    "FMI ME localized state event must follow the accepted time"
                )
        return restored_readable_values

    def get_next_event_time(self) -> float | None:
        """Return the next accepted FMI time-event request.

        :return: Absolute FMI event time or ``None`` when undefined.
        """

        if self.fmi_three_coordinator is not None:
            scheduled_event_time: float | None = (
                self.fmi_three_coordinator.get_next_event_time()
            )
            localized_event_time: float | None = self.localized_state_event_time
            if scheduled_event_time is None:
                return localized_event_time
            else:
                if (
                    localized_event_time is not None
                    and localized_event_time < scheduled_event_time
                ):
                    return localized_event_time
                else:
                    return scheduled_event_time
        else:
            return None

    def explicit_euler_step(self, current_time: float, step_size: float, input_values: dict[str, float]) -> dict[str, float]:
        """Advance the FMU one explicit-Euler predictor step.

        :param current_time: Current integration time.
        :param step_size: Step length.
        :param input_values: FMU input values.
        :return: Output values after the step.
        """

        if self.spec.integration_method == FmuMeIntegrationMethod.EXPLICIT_EULER:
            readable_values: tuple[float, ...] | None = (
                self._advance_explicit_euler_state(
                    current_time=current_time,
                    step_size=step_size,
                    input_values=input_values,
                )
            )
            if readable_values is None:
                outputs: dict[str, float] = self.evaluate_outputs(
                    current_time + step_size,
                    input_values,
                )
                self.resolve_pending_step(accepted=True)
            else:
                crossing_indices: tuple[int, ...] = (
                    self._get_pending_state_event_crossing_indices()
                )
                if len(crossing_indices) == 0:
                    resolved_readable_values: tuple[float, ...] | None = (
                        self.resolve_pending_step(accepted=True)
                    )
                    if resolved_readable_values is not None:
                        outputs = self._map_named_output_values(
                            resolved_readable_values
                        )
                    else:
                        outputs = self._map_named_output_values(readable_values)
                else:
                    self.resolve_pending_step(accepted=False)
                    raise FmuModeError(
                        "Direct FMI ME stepping cannot accept a state event; "
                        "use the RMS or EMT solver-owned localization path"
                    )
            return outputs
        else:
            raise ValueError(f"Unsupported FMU ME integration method {self.spec.integration_method.value}")

    def _explicit_euler_bound_step(
        self,
        current_time: float,
        step_size: float,
        input_values: dict[str, float],
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Advance one step and retain every selected device output element.

        :param current_time: Current accepted integration time.
        :param step_size: Integration step length.
        :param input_values: Complete scalar FMU input values.
        :return: Output values indexed by VeraGrid reference.
        """

        if self.spec.integration_method == FmuMeIntegrationMethod.EXPLICIT_EULER:
            readable_values: tuple[float, ...] | None = (
                self._advance_explicit_euler_state(
                    current_time=current_time,
                    step_size=step_size,
                    input_values=input_values,
                )
            )
            if readable_values is None:
                outputs: dict[VarPowerFlowReferenceType, float] = (
                    self._evaluate_bound_outputs(
                    time_value=current_time + step_size,
                    input_values=input_values,
                )
                )
            else:
                outputs = self._map_bound_output_values(readable_values)
            return outputs
        else:
            raise ValueError(
                "Unsupported FMU ME integration method "
                f"{self.spec.integration_method.value}"
            )

    def close(self) -> None:
        """Release the FMU runtime used by the adapter.

        :return: None.
        """

        if self.runtime_host is not None:
            self.runtime_host.close()
            self.runtime_host = None
        else:
            pass
        if self.fmi_three_coordinator is not None:
            self.fmi_three_coordinator.close()
            self.fmi_three_coordinator = None
        else:
            pass
        self.initialized = False
        self.localized_state_event_time = None
        self._clear_pending_state_event_data()


def _build_state_variable_names(metadata: FmuModelDescription) -> tuple[str, ...]:
    """Recover the ordered continuous-state variable names from derivative metadata.

    :param metadata: Parsed FMU metadata.
    :return: Ordered continuous-state variable names.
    """

    state_variable_names: list[str] = list()
    if metadata.fmi_version_family == FmiVersion.FMI_3_0:
        state_variable: FmuVariableDescription
        for state_variable in metadata.get_state_variables():
            # FMI 3 resolves the derivative relationship through the state's
            # value reference while parsing the authoritative metadata.
            state_variable_names.append(state_variable.name)
    else:
        derivative_variable: FmuVariableDescription
        for derivative_variable in metadata.get_derivative_variables():
            derivative_index: int | None = derivative_variable.derivative_index
            if derivative_index is not None:
                # FMI 1/2 derivative indices are 1-based positions in the
                # ordered model-variable sequence.
                state_variable_names.append(
                    metadata.variables[derivative_index - 1].name
                )
            else:
                pass
    return tuple(state_variable_names)


def build_fmu_me_device_spec(
    domain: FmuMeDomain,
    config: FmuImportConfig,
    device_tpe: DeviceType,
    input_variable_names: tuple[str, ...],
    output_variable_names: tuple[str, ...],
    integration_method: FmuMeIntegrationMethod = FmuMeIntegrationMethod.EXPLICIT_EULER,
    worker_limits: FmiThreeWorkerHostLimits | None = None,
    maximum_event_iterations: int = 32,
    input_bindings: tuple[FmuRefBinding, ...] | None = None,
    output_bindings: tuple[FmuRefBinding, ...] | None = None,
    output_defaults: dict[VarPowerFlowReferenceType, float] | None = None,
    output_param_uids: dict[VarPowerFlowReferenceType, int] | None = None,
    configuration_float64_values: tuple[
        FmiThreeFloat64ConfigurationValue, ...
    ] = tuple(),
    configuration_uint64_values: tuple[
        FmiThreeUInt64ConfigurationValue, ...
    ] = tuple(),
) -> FmuMeDeviceSpec:
    """Build the validated runtime specification for one FMU ME device.

    :param domain: VeraGrid domain that will consume the FMU.
    :param config: FMU runtime configuration.
    :param device_tpe: VeraGrid device type.
    :param input_variable_names: Ordered FMU input names.
    :param output_variable_names: Ordered FMU output names.
    :param integration_method: Predictor used by the adapter.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param maximum_event_iterations: Positive Event Mode convergence bound.
    :param input_bindings: Optional typed bindings aligned with input names.
    :param output_bindings: Optional typed bindings aligned with output names.
    :param output_defaults: Optional output fallbacks before the first sample.
    :param output_param_uids: Optional runtime output-parameter identifiers.
    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    :return: Runtime FMU ME device specification.
    """

    resolved_input_bindings: tuple[FmuRefBinding, ...]
    if input_bindings is None:
        resolved_input_bindings = tuple()
    else:
        resolved_input_bindings = tuple(input_bindings)
        bound_input_names_list: list[str] = [""] * len(resolved_input_bindings)
        binding_index: int
        for binding_index in range(len(resolved_input_bindings)):
            bound_input_names_list[binding_index] = (
                resolved_input_bindings[binding_index].fmu_variable_name
            )
        bound_input_names: tuple[str, ...] = tuple(bound_input_names_list)
        if bound_input_names == input_variable_names:
            pass
        else:
            raise ValueError(
                "FMU ME input bindings do not match the declared variable names"
            )
    resolved_output_bindings: tuple[FmuRefBinding, ...]
    if output_bindings is None:
        resolved_output_bindings = tuple()
    else:
        resolved_output_bindings = tuple(output_bindings)
        bound_output_names_list: list[str] = [""] * len(
            resolved_output_bindings
        )
        for binding_index in range(len(resolved_output_bindings)):
            bound_output_names_list[binding_index] = (
                resolved_output_bindings[binding_index].fmu_variable_name
            )
        bound_output_names: tuple[str, ...] = tuple(bound_output_names_list)
        if bound_output_names == output_variable_names:
            pass
        else:
            raise ValueError(
                "FMU ME output bindings do not match the declared variable names"
            )
    resolved_output_defaults: dict[VarPowerFlowReferenceType, float]
    if output_defaults is None:
        resolved_output_defaults = dict()
    else:
        resolved_output_defaults = dict(output_defaults)
    resolved_output_param_uids: dict[VarPowerFlowReferenceType, int]
    if output_param_uids is None:
        resolved_output_param_uids = dict()
    else:
        resolved_output_param_uids = dict(output_param_uids)

    metadata: FmuModelDescription = read_fmu_model_description(config.fmu_path)
    float64_profile: FmiThreeWorkerFloat64Profile | None
    if metadata.fmi_version_family == FmiVersion.FMI_2_0:
        resolved_mode: FmuInterfaceMode = config.resolve_execution_mode(metadata)
        float64_profile = None
        has_fmi_three_configuration: bool = (
            len(configuration_float64_values) > 0
            or len(configuration_uint64_values) > 0
        )
        if has_fmi_three_configuration:
            raise FmuModeError(
                "FMI 3 Configuration Mode declarations require FMI 3"
            )
        else:
            pass
    else:
        if metadata.fmi_version_family == FmiVersion.FMI_3_0:
            resolved_mode = metadata.select_declared_interface(config.preferred_mode)
            float64_profile = resolve_fmi_three_worker_float64_profile(metadata)
            validate_fmi_three_model_exchange_worker_profile(
                metadata=metadata,
                preferred_mode=resolved_mode,
                float64_profile=float64_profile,
            )
            if worker_limits is not None:
                pass
            else:
                raise ValueError(
                    "FMI 3 Model Exchange devices require explicit worker limits"
                )
        else:
            raise ValueError(
                f"FMI {metadata.fmi_version} execution is not supported yet"
            )
    if resolved_mode == FmuInterfaceMode.MODEL_EXCHANGE:
        available_variables: set[str] = set(metadata.get_variable_names())
        input_variable_name: str
        for input_variable_name in input_variable_names:
            if input_variable_name in available_variables:
                if float64_profile is not None:
                    input_variable: FmuVariableDescription = metadata.get_variable(
                        input_variable_name
                    )
                    if len(input_variable.dimensions) == 0:
                        pass
                    else:
                        raise FmuModeError(
                            "FMI 3 ME device array inputs require a complete "
                            "value provider"
                        )
                else:
                    pass
            else:
                raise KeyError(f"FMU variable {input_variable_name!r} was not found in {config.fmu_path}")
        output_variable_name: str
        for output_variable_name in output_variable_names:
            if output_variable_name in available_variables:
                if float64_profile is not None:
                    output_variable: FmuVariableDescription = metadata.get_variable(
                        output_variable_name
                    )
                    if len(output_variable.dimensions) == 0:
                        pass
                    else:
                        has_typed_output_bindings: bool = (
                            len(resolved_output_bindings) > 0
                        )
                        if has_typed_output_bindings:
                            pass
                        else:
                            raise FmuModeError(
                                "FMI 3 ME array outputs require typed device "
                                "bindings"
                            )
                else:
                    pass
            else:
                raise KeyError(f"FMU variable {output_variable_name!r} was not found in {config.fmu_path}")

        state_variable_names: tuple[str, ...] = _build_state_variable_names(metadata)
        derivative_variables: list[FmuVariableDescription] = (
            metadata.get_derivative_variables()
        )
        derivative_variable_names_list: list[str] = [""] * len(
            derivative_variables
        )
        derivative_index: int
        for derivative_index in range(len(derivative_variables)):
            derivative_variable_names_list[derivative_index] = (
                derivative_variables[derivative_index].name
            )
        derivative_variable_names: tuple[str, ...] = tuple(
            derivative_variable_names_list
        )
        return FmuMeDeviceSpec(
            domain=domain,
            config=config,
            device_tpe=device_tpe,
            input_variable_names=input_variable_names,
            output_variable_names=output_variable_names,
            state_variable_names=state_variable_names,
            derivative_variable_names=derivative_variable_names,
            integration_method=integration_method,
            worker_limits=worker_limits,
            float64_profile=float64_profile,
            maximum_event_iterations=maximum_event_iterations,
            input_bindings=resolved_input_bindings,
            output_bindings=resolved_output_bindings,
            output_defaults=resolved_output_defaults,
            output_param_uids=resolved_output_param_uids,
            configuration_float64_values=configuration_float64_values,
            configuration_uint64_values=configuration_uint64_values,
        )
    else:
        raise ValueError(f"FMU ME device specs require a Model Exchange FMU, got {resolved_mode.value}")


def build_rms_fmu_me_injection_template(
    vfactory: VarFactory,
    config: FmuImportConfig,
    input_bindings: tuple[FmuRefBinding, ...],
    output_bindings: tuple[FmuRefBinding, ...],
    name: str,
    device_tpe: DeviceType = DeviceType.LoadDevice,
    output_defaults: dict[VarPowerFlowReferenceType, float] | None = None,
    integration_method: FmuMeIntegrationMethod = FmuMeIntegrationMethod.EXPLICIT_EULER,
    worker_limits: FmiThreeWorkerHostLimits | None = None,
    maximum_event_iterations: int = 32,
) -> RmsModelTemplate:
    """Build the symbolic RMS shell for an imported FMU ME device.

    :param vfactory: Variable factory used by the owning grid.
    :param config: FMU runtime configuration.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param name: Template name.
    :param device_tpe: VeraGrid device type.
    :param output_defaults: Default output values before the first FMU step.
    :param integration_method: Internal ME predictor method.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param maximum_event_iterations: Positive Event Mode convergence bound.
    :return: RMS template wrapping the FMU shell block.
    """

    input_variable_names: list[str] = [""] * len(input_bindings)
    binding_index: int
    for binding_index in range(len(input_bindings)):
        input_variable_names[binding_index] = (
            input_bindings[binding_index].fmu_variable_name
        )
    output_variable_names: list[str] = [""] * len(output_bindings)
    for binding_index in range(len(output_bindings)):
        output_variable_names[binding_index] = (
            output_bindings[binding_index].fmu_variable_name
        )

    # The FMU metadata is validated before the symbolic shell block is created.
    build_fmu_me_device_spec(
        domain=FmuMeDomain.RMS,
        config=config,
        device_tpe=device_tpe,
        input_variable_names=tuple(input_variable_names),
        output_variable_names=tuple(output_variable_names),
        integration_method=integration_method,
        worker_limits=worker_limits,
        maximum_event_iterations=maximum_event_iterations,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
    )

    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = device_tpe
    template.block = _build_template_block(vfactory, name, output_bindings, output_defaults)
    return template


def build_emt_fmu_me_injection_template(
    vfactory: VarFactory,
    config: FmuImportConfig,
    input_bindings: tuple[FmuRefBinding, ...],
    output_bindings: tuple[FmuRefBinding, ...],
    name: str,
    device_tpe: DeviceType = DeviceType.LoadDevice,
    output_defaults: dict[VarPowerFlowReferenceType, float] | None = None,
    integration_method: FmuMeIntegrationMethod = FmuMeIntegrationMethod.EXPLICIT_EULER,
    worker_limits: FmiThreeWorkerHostLimits | None = None,
    maximum_event_iterations: int = 32,
) -> EmtModelTemplate:
    """Build the symbolic EMT shell for an imported FMU ME device.

    :param vfactory: Variable factory used by the owning grid.
    :param config: FMU runtime configuration.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param name: Template name.
    :param device_tpe: VeraGrid device type.
    :param output_defaults: Default output values before the first FMU step.
    :param integration_method: Internal ME predictor method.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param maximum_event_iterations: Positive Event Mode convergence bound.
    :return: EMT template wrapping the FMU shell block.
    """

    input_variable_names: list[str] = [""] * len(input_bindings)
    binding_index: int
    for binding_index in range(len(input_bindings)):
        input_variable_names[binding_index] = (
            input_bindings[binding_index].fmu_variable_name
        )
    output_variable_names: list[str] = [""] * len(output_bindings)
    for binding_index in range(len(output_bindings)):
        output_variable_names[binding_index] = (
            output_bindings[binding_index].fmu_variable_name
        )

    build_fmu_me_device_spec(
        domain=FmuMeDomain.EMT,
        config=config,
        device_tpe=device_tpe,
        input_variable_names=tuple(input_variable_names),
        output_variable_names=tuple(output_variable_names),
        integration_method=integration_method,
        worker_limits=worker_limits,
        maximum_event_iterations=maximum_event_iterations,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
    )

    template: EmtModelTemplate = EmtModelTemplate(name=name)
    template.tpe = device_tpe
    template.block = _build_template_block(
        vfactory=vfactory,
        name=name,
        output_bindings=output_bindings,
        output_defaults=output_defaults,
        input_bindings=input_bindings,
    )
    _ensure_emt_external_mapping_keys(template.block)
    template.block.api_obj_mapping = dict()
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0_A] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0_B] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0_C] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Ql0_A] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Ql0_B] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Ql0_C] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.omega_base] = None
    return template


def _read_rms_me_device_config(device: Any) -> Any | None:
    """Read the serialized FMU ME configuration stored on one device.

    :param device: VeraGrid device instance.
    :return: Parsed device configuration when available.
    """

    try:
        config_text: str = device.rms_fmu_me_import_config
    except AttributeError:
        if isinstance(device, InjectionParent) or isinstance(device, BranchParent):
            raise
        else:
            return None
    return load_fmu_me_device_config(config_text)


def _read_emt_me_device_config(device: Any) -> Any | None:
    """Read the serialized FMU ME configuration stored on one EMT device.

    :param device: VeraGrid device instance.
    :return: Parsed device configuration when available.
    """

    try:
        config_text: str = device.emt_fmu_me_import_config
    except AttributeError:
        if isinstance(device, InjectionParent) or isinstance(device, BranchParent):
            raise
        else:
            return None
    return load_fmu_me_device_config(config_text)


def _build_rms_me_runtime_spec(device: Any, block: Block) -> Any | None:
    """Rebuild the FMU ME runtime specification from the stored device config.

    :param device: VeraGrid device instance.
    :param block: Device block used in the active RMS problem.
    :return: Runtime FMU ME specification when available.
    """

    record = _read_rms_me_device_config(device)
    if record is None:
        return None
    else:
        if record.domain == FmuMeDomain.RMS:
            return restore_fmu_me_spec_from_record(record, block, device.device_type)
        else:
            return None


def _build_emt_me_runtime_spec(device: Any, block: Block) -> Any | None:
    """Rebuild the FMU ME runtime specification from the stored EMT device config.

    :param device: VeraGrid device instance.
    :param block: Device block used in the active EMT problem.
    :return: Runtime FMU ME specification when available.
    """

    record = _read_emt_me_device_config(device)
    if record is None:
        return None
    else:
        if record.domain == FmuMeDomain.EMT:
            return restore_fmu_me_spec_from_record(record, block, device.device_type)
        else:
            return None


def _get_event_param_index_map(problem: Any) -> dict[int, int]:
    """
    Return the runtime event-parameter index map exposed by the active problem.

    :param problem: Runtime problem wrapper.
    :return: UID-to-index event-parameter map.
    """

    try:
        return problem._uid2idx_event_params
    except AttributeError:
        return problem.uid2idx_event_params


def _get_rms_me_input_value(problem: Any, device: Any, reference: VarPowerFlowReferenceType, x_snapshot: np.ndarray) -> float:
    """Read one RMS FMU ME input from the current network snapshot.

    :param problem: RMS problem instance.
    :param device: VeraGrid device instance.
    :param reference: Requested VeraGrid external reference.
    :param x_snapshot: Current accepted state snapshot.
    :return: Numeric input value.
    """

    if reference in {VarPowerFlowReferenceType.Vm, VarPowerFlowReferenceType.Va, VarPowerFlowReferenceType.Vdc}:
        bus_model: Block = device.bus.rms_model
        variable: Var = bus_model.external_mapping[reference]
        return float(x_snapshot[problem.uid2idx_vars[variable.uid]])
    else:
        raise KeyError(f"Unsupported RMS FMU ME input reference {reference.value!r}")


def _get_emt_me_input_value(problem: Any, device: Any, reference: VarPowerFlowReferenceType, x_snapshot: np.ndarray) -> float:
    """Read one EMT FMU ME input from the current network snapshot.

    :param problem: EMT problem instance.
    :param device: VeraGrid device instance.
    :param reference: Requested VeraGrid external reference.
    :param x_snapshot: Current accepted state snapshot.
    :return: Numeric input value.
    """

    if reference in {
        VarPowerFlowReferenceType.v_N,
        VarPowerFlowReferenceType.v_A,
        VarPowerFlowReferenceType.v_B,
        VarPowerFlowReferenceType.v_C,
        VarPowerFlowReferenceType.Vdc,
    }:
        bus_model: Block = device.bus.emt_model
        variable: Var = bus_model.external_mapping[reference]
        return float(x_snapshot[problem.uid2idx_vars[variable.uid]])
    else:
        raise KeyError(f"Unsupported EMT FMU ME input reference {reference.value!r}")


class RmsFmuMeDeviceAdapter:
    """Adapt one imported FMU ME device to the RMS communication-step loop.

    :param problem: RMS problem instance.
    :param device: VeraGrid device instance.
    :param spec: Runtime FMU ME specification.
    :param output_param_indices: Runtime-parameter indices receiving FMU outputs.
    """

    __slots__ = ("problem", "device", "spec", "output_param_indices", "runtime_adapter", "last_outputs")

    def __init__(
        self,
        problem: Any,
        device: Any,
        spec: FmuMeDeviceSpec,
        output_param_indices: dict[VarPowerFlowReferenceType, int],
    ) -> None:
        """Store the RMS FMU ME runtime adapter.

        :return: None.
        """

        self.problem: Any = problem
        self.device: Any = device
        self.spec: FmuMeDeviceSpec = spec
        self.output_param_indices: dict[VarPowerFlowReferenceType, int] = output_param_indices
        self.runtime_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(spec)
        self.last_outputs: dict[VarPowerFlowReferenceType, float] = dict()

    def _build_input_values(self, x_snapshot: np.ndarray) -> dict[str, float]:
        """Collect the FMU ME input values from the current RMS snapshot.

        :param x_snapshot: Current accepted state snapshot.
        :return: FMU input values.
        """

        input_values: dict[str, float] = dict()
        binding: FmuRefBinding
        for binding in self.spec.input_bindings:
            input_values[binding.fmu_variable_name] = _get_rms_me_input_value(self.problem, self.device, binding.reference, x_snapshot)
        return input_values

    def initialize_outputs(self, time_value: float, x_snapshot: np.ndarray) -> dict[VarPowerFlowReferenceType, float]:
        """Initialize the FMU ME runtime and return its first output sample.

        :param time_value: Current simulation time.
        :param x_snapshot: Current accepted state snapshot.
        :return: FMU outputs indexed by VeraGrid reference.
        """

        self.runtime_adapter.initialize(start_time=time_value, input_values=self._build_input_values(x_snapshot))
        outputs: dict[VarPowerFlowReferenceType, float] = (
            self.runtime_adapter._evaluate_bound_outputs(
                time_value,
                self._build_input_values(x_snapshot),
            )
        )
        self.last_outputs = dict(outputs)
        return outputs

    def advance(self, current_time: float, step_size: float, x_snapshot: np.ndarray) -> dict[VarPowerFlowReferenceType, float]:
        """Advance the FMU ME runtime for one RMS communication step.

        :param current_time: Current simulation time.
        :param step_size: RMS communication step.
        :param x_snapshot: Current accepted state snapshot.
        :return: FMU outputs indexed by VeraGrid reference.
        """

        outputs: dict[VarPowerFlowReferenceType, float] = (
            self.runtime_adapter._explicit_euler_bound_step(
                current_time=current_time,
                step_size=step_size,
                input_values=self._build_input_values(x_snapshot),
            )
        )
        self.last_outputs = dict(outputs)
        return outputs

    def resolve_step(
        self,
        accepted: bool,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Resolve the pending FMI 3 candidate after the RMS solve.

        :param accepted: Whether the RMS numerical step converged.
        :return: Outputs belonging to the resolved accepted point.
        """

        readable_values: tuple[float, ...] | None = (
            self.runtime_adapter.resolve_pending_step(accepted=accepted)
        )
        if readable_values is not None:
            resolved_outputs: dict[VarPowerFlowReferenceType, float] = (
                self.runtime_adapter._map_bound_output_values(readable_values)
            )
            self.last_outputs = dict(resolved_outputs)
        else:
            resolved_outputs = dict(self.last_outputs)
        return resolved_outputs

    def apply_outputs(self, target: np.ndarray, outputs: dict[VarPowerFlowReferenceType, float]) -> None:
        """Write the FMU ME outputs into VeraGrid runtime-parameter storage.

        :param target: Runtime-parameter array.
        :param outputs: FMU outputs indexed by VeraGrid reference.
        :return: None.
        """

        reference: VarPowerFlowReferenceType
        for reference, value in outputs.items():
            target[self.output_param_indices[reference]] = float(value)

    def close(self) -> None:
        """Release the FMU ME runtime used by the adapter.

        :return: None.
        """

        if len(self.last_outputs) == 0:
            if self.runtime_adapter.initialized:
                self.last_outputs = dict(
                    self.runtime_adapter._evaluate_bound_outputs(0.0, dict())
                )
            else:
                pass
        else:
            pass
        self.runtime_adapter.close()


class EmtFmuMeDeviceAdapter:
    """Adapt one imported FMU ME device to the EMT boundary-update loop.

    :param problem: EMT problem instance.
    :param device: VeraGrid device instance.
    :param spec: Runtime FMU ME specification.
    :param output_param_indices: Runtime-parameter indices receiving FMU outputs.
    """

    __slots__ = (
        "problem",
        "device",
        "spec",
        "output_param_indices",
        "runtime_adapter",
        "last_time",
        "initialized",
        "last_outputs",
        "pending_previous_time",
    )

    def __init__(
        self,
        problem: Any,
        device: Any,
        spec: FmuMeDeviceSpec,
        output_param_indices: dict[VarPowerFlowReferenceType, int],
    ) -> None:
        """Store the EMT FMU ME runtime adapter.

        :return: None.
        """

        self.problem: Any = problem
        self.device: Any = device
        self.spec: FmuMeDeviceSpec = spec
        self.output_param_indices: dict[VarPowerFlowReferenceType, int] = output_param_indices
        self.runtime_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(spec)
        self.last_time: float = 0.0
        self.initialized: bool = False
        self.last_outputs: dict[VarPowerFlowReferenceType, float] = dict()
        self.pending_previous_time: float | None = None

    def _build_input_values(self, x_snapshot: np.ndarray) -> dict[str, float]:
        """Collect the FMU ME input values from the current EMT snapshot.

        :param x_snapshot: Current accepted state snapshot.
        :return: FMU input values.
        """

        input_values: dict[str, float] = dict()
        binding: FmuRefBinding
        for binding in self.spec.input_bindings:
            input_values[binding.fmu_variable_name] = _get_emt_me_input_value(self.problem, self.device, binding.reference, x_snapshot)
        return input_values

    def initialize_outputs(self, time_value: float, x_snapshot: np.ndarray) -> dict[VarPowerFlowReferenceType, float]:
        """Initialize the FMU ME runtime and return its first output sample.

        :param time_value: Current simulation time.
        :param x_snapshot: Current accepted state snapshot.
        :return: FMU outputs indexed by VeraGrid reference.
        """

        self.runtime_adapter.initialize(start_time=time_value, input_values=self._build_input_values(x_snapshot))
        self.initialized = True
        self.last_time = time_value
        outputs: dict[VarPowerFlowReferenceType, float] = (
            self.runtime_adapter._evaluate_bound_outputs(
            time_value,
            self._build_input_values(x_snapshot),
        )
        )
        self.last_outputs = dict(outputs)
        return outputs

    def advance(self, current_time: float, step_size: float, x_snapshot: np.ndarray) -> dict[VarPowerFlowReferenceType, float]:
        """Advance the FMU ME runtime for one EMT communication step.

        :param current_time: Current simulation time.
        :param step_size: EMT communication step.
        :param x_snapshot: Current accepted state snapshot.
        :return: FMU outputs indexed by VeraGrid reference.
        """

        outputs: dict[VarPowerFlowReferenceType, float] = (
            self.runtime_adapter._explicit_euler_bound_step(
                current_time=current_time,
                step_size=step_size,
                input_values=self._build_input_values(x_snapshot),
            )
        )
        self.pending_previous_time = current_time
        self.last_time = current_time + step_size
        self.last_outputs = dict(outputs)
        return outputs

    def resolve_step(
        self,
        accepted: bool,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Resolve the pending FMI 3 candidate after the EMT solve.

        :param accepted: Whether the EMT numerical step converged.
        :return: Outputs belonging to the resolved accepted point.
        """

        readable_values: tuple[float, ...] | None = (
            self.runtime_adapter.resolve_pending_step(accepted=accepted)
        )
        if readable_values is not None:
            resolved_outputs: dict[VarPowerFlowReferenceType, float] = (
                self.runtime_adapter._map_bound_output_values(readable_values)
            )
            self.last_outputs = dict(resolved_outputs)
        else:
            resolved_outputs = dict(self.last_outputs)
        if readable_values is not None and not accepted:
            if self.pending_previous_time is not None:
                self.last_time = self.pending_previous_time
            else:
                pass
        else:
            pass
        self.pending_previous_time = None
        return resolved_outputs

    def apply_outputs(self, target: np.ndarray, outputs: dict[VarPowerFlowReferenceType, float]) -> None:
        """Write the FMU ME outputs into VeraGrid runtime-parameter storage.

        :param target: Runtime-parameter array.
        :param outputs: FMU outputs indexed by VeraGrid reference.
        :return: None.
        """

        reference: VarPowerFlowReferenceType
        for reference, value in outputs.items():
            target[self.output_param_indices[reference]] = float(value)

    def close(self) -> None:
        """Release the FMU ME runtime used by the adapter.

        :return: None.
        """

        self.runtime_adapter.close()


def register_rms_fmu_me_device(problem: Any, device: Any, block: Block) -> None:
    """Register one imported FMU ME device in the active RMS problem.

    :param problem: RMS problem instance.
    :param device: VeraGrid device instance.
    :param block: Device RMS block used in the active problem.
    :return: None.
    """

    spec: Optional[FmuMeDeviceSpec] = _build_rms_me_runtime_spec(device, block)
    if spec is None:
        return
    else:
        adapter: RmsFmuMeDeviceAdapter
        for adapter in problem._fmu_me_adapters:
            if adapter.device.idtag == device.idtag:
                return
            else:
                pass

        output_param_indices: dict[VarPowerFlowReferenceType, int] = dict()
        uid_to_index = _get_event_param_index_map(problem)
        reference: VarPowerFlowReferenceType
        for reference, uid in spec.output_param_uids.items():
            output_param_indices[reference] = uid_to_index[uid]

        problem._fmu_me_adapters.append(
            RmsFmuMeDeviceAdapter(problem=problem, device=device, spec=spec, output_param_indices=output_param_indices)
        )
        problem._fmu_me_initialized = False


def initialize_rms_fmu_me_devices(problem: Any, x_snapshot: np.ndarray, time_value: float = 0.0) -> None:
    """Initialize all imported FMU ME devices before the RMS loop starts.

    :param problem: RMS problem instance.
    :param x_snapshot: Initial accepted state snapshot.
    :param time_value: Initial simulation time.
    :return: None.
    """

    if len(problem._fmu_me_adapters) > 0:
        adapter: RmsFmuMeDeviceAdapter
        for adapter in problem._fmu_me_adapters:
            outputs = adapter.initialize_outputs(time_value, x_snapshot)
            adapter.apply_outputs(problem._variable_parameters_values, outputs)
            if problem._variable_parameters_values is None:
                problem._last_variable_parameters_values = None
            else:
                problem._last_variable_parameters_values = np.array(problem._variable_parameters_values, copy=True)
        problem._fmu_me_initialized = True
    else:
        problem._fmu_me_initialized = True


def advance_rms_fmu_me_devices(problem: Any, time_value: float, x_snapshot: np.ndarray, step_size: float) -> None:
    """Advance all imported FMU ME devices for one RMS communication step.

    :param problem: RMS problem instance.
    :param time_value: Current simulation time.
    :param x_snapshot: Current accepted state snapshot.
    :param step_size: RMS communication step.
    :return: None.
    """

    if len(problem._fmu_me_adapters) > 0:
        if problem._fmu_me_initialized:
            pass
        else:
            initialize_rms_fmu_me_devices(problem=problem, x_snapshot=x_snapshot, time_value=time_value)

        adapter: RmsFmuMeDeviceAdapter
        for adapter in problem._fmu_me_adapters:
            outputs = adapter.advance(current_time=time_value, step_size=step_size, x_snapshot=x_snapshot)
            adapter.apply_outputs(problem._variable_parameters_values, outputs)
            if problem._variable_parameters_values is None:
                problem._last_variable_parameters_values = None
            else:
                problem._last_variable_parameters_values = np.array(problem._variable_parameters_values, copy=True)
    else:
        pass


def resolve_rms_fmu_me_devices(
    problem: Any,
    accepted: bool,
) -> float | None:
    """Accept or reject every prepared RMS FMU ME step in registration order.

    :param problem: RMS problem owning the imported FMU adapters.
    :param accepted: Whether the owning RMS numerical step converged.
    :return: Always ``None`` because localization happens before Co-Simulation.
    """

    adapter: RmsFmuMeDeviceAdapter
    for adapter in problem._fmu_me_adapters:
        outputs: dict[VarPowerFlowReferenceType, float] = adapter.resolve_step(
            accepted=accepted
        )
        adapter.apply_outputs(problem._variable_parameters_values, outputs)
    if problem._variable_parameters_values is None:
        problem._last_variable_parameters_values = None
    else:
        problem._last_variable_parameters_values = np.array(
            problem._variable_parameters_values,
            copy=True,
        )
    return None


def _prepare_rms_fmu_me_state_event_retry(
    problem: Any,
    state_event_time_tolerance: float,
    state_event_max_iterations: int,
) -> float | None:
    """Localize the global first ME event before any CS device advances.

    Every ME candidate is inspected before the solver mutates a Co-Simulation
    FMU.  When a crossing exists, all ME candidates return to the accepted
    point and only simultaneous sources are armed for the shortened retry.

    :param problem: RMS problem owning the imported FMU adapters.
    :param state_event_time_tolerance: Positive event-time tolerance in seconds.
    :param state_event_max_iterations: Positive bisection iteration bound.
    :return: Global retry time when a state event precedes the candidate end.
    """

    adapter_count: int = len(problem._fmu_me_adapters)
    localized_times: list[float | None] = [None] * adapter_count
    earliest_event_time: float | None = None
    adapter_index: int
    for adapter_index in range(adapter_count):
        adapter: RmsFmuMeDeviceAdapter = problem._fmu_me_adapters[
            adapter_index
        ]
        localized_time: float | None = (
            adapter.runtime_adapter.get_pending_state_event_time(
                time_tolerance=state_event_time_tolerance,
                maximum_iterations=state_event_max_iterations,
            )
        )
        localized_times[adapter_index] = localized_time
        if (
            localized_time is not None
            and (
                earliest_event_time is None
                or localized_time < earliest_event_time
            )
        ):
            earliest_event_time = localized_time
        else:
            pass

    if earliest_event_time is not None:
        # A shortened retry must start from one coherent accepted system point.
        for adapter_index in range(adapter_count):
            adapter = problem._fmu_me_adapters[adapter_index]
            adapter_event_time: float | None = localized_times[adapter_index]
            source_is_simultaneous: bool = (
                adapter_event_time is not None
                and (adapter_event_time - earliest_event_time)
                <= state_event_time_tolerance
            )
            if source_is_simultaneous:
                retry_event_time: float | None = earliest_event_time
            else:
                retry_event_time = None
            restored_values: tuple[float, ...] = (
                adapter.runtime_adapter.prepare_state_event_retry(
                    event_time=retry_event_time
                )
            )
            restored_outputs: dict[VarPowerFlowReferenceType, float] = (
                adapter.runtime_adapter._map_bound_output_values(restored_values)
            )
            adapter.last_outputs = dict(restored_outputs)
            adapter.apply_outputs(
                problem._variable_parameters_values,
                restored_outputs,
            )
        if problem._variable_parameters_values is None:
            problem._last_variable_parameters_values = None
        else:
            problem._last_variable_parameters_values = np.array(
                problem._variable_parameters_values,
                copy=True,
            )
    else:
        pass
    return earliest_event_time


def get_next_rms_fmu_me_event_time(
    problem: Any,
    t_prev: float,
    t_target: float,
) -> float | None:
    """Return the earliest FMI ME time event inside one RMS interval.

    :param problem: RMS problem owning the imported FMU adapters.
    :param t_prev: Previous accepted RMS time.
    :param t_target: Candidate RMS target time.
    :return: Earliest FMI event in ``(t_prev, t_target]`` or ``None``.
    """

    next_event_time: float | None = None
    adapter: RmsFmuMeDeviceAdapter
    for adapter in problem._fmu_me_adapters:
        adapter_event_time: float | None = (
            adapter.runtime_adapter.get_next_event_time()
        )
        if (
            adapter_event_time is not None
            and t_prev < adapter_event_time <= t_target
        ):
            if next_event_time is None or adapter_event_time < next_event_time:
                next_event_time = adapter_event_time
            else:
                pass
        else:
            pass
    return next_event_time


def close_rms_fmu_me_devices(problem: Any) -> None:
    """Close all imported FMU ME devices.

    :param problem: RMS problem instance.
    :return: None.
    """

    adapter: RmsFmuMeDeviceAdapter
    for adapter in problem._fmu_me_adapters:
        adapter.close()


def register_emt_fmu_me_device(problem: Any, device: Any, block: Block) -> None:
    """Register one imported FMU ME device in the active EMT problem.

    :param problem: EMT problem instance.
    :param device: VeraGrid device instance.
    :param block: Device EMT block used in the active problem.
    :return: None.
    """

    spec: Optional[FmuMeDeviceSpec] = _build_emt_me_runtime_spec(device, block)
    if spec is None:
        return
    else:
        adapter: EmtFmuMeDeviceAdapter
        for adapter in problem._fmu_me_adapters:
            if adapter.device.idtag == device.idtag:
                return
            else:
                pass

        output_param_indices: dict[VarPowerFlowReferenceType, int] = dict()
        uid_to_index = _get_event_param_index_map(problem)
        reference: VarPowerFlowReferenceType
        for reference, uid in spec.output_param_uids.items():
            output_param_indices[reference] = uid_to_index[uid]

        problem._fmu_me_adapters.append(
            EmtFmuMeDeviceAdapter(problem=problem, device=device, spec=spec, output_param_indices=output_param_indices)
        )


def queue_emt_fmu_me_device(problem: Any, device: Any, block: Block) -> None:
    """Queue one EMT device for FMU ME restoration after problem repartitioning.

    :param problem: EMT problem instance.
    :param device: VeraGrid device instance.
    :param block: Device EMT block used in the active problem.
    :return: None.
    """

    record = _read_emt_me_device_config(device)
    if record is None:
        return
    else:
        problem._pending_fmu_me_devices.append((device, block))


def finalize_emt_fmu_me_devices(problem: Any) -> None:
    """Restore all queued EMT FMU ME devices after the EMT problem is assembled.

    :param problem: EMT problem instance.
    :return: None.
    """

    pending_device: tuple[Any, Block]
    for pending_device in problem._pending_fmu_me_devices:
        register_emt_fmu_me_device(problem, pending_device[0], pending_device[1])
