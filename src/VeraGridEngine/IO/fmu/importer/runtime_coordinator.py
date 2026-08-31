# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Solver-agnostic FMI 3 Model Exchange lifecycle coordination."""

from __future__ import annotations

import math

from VeraGridEngine.IO.fmu.importer.errors import FmuImportError, FmuModeError
from VeraGridEngine.IO.fmu.importer.runtime_protocol import (
    FmiThreeWorkerCompletedIntegratorStepResult,
    FmiThreeWorkerDiscreteStatesResult,
)
from VeraGridEngine.IO.fmu.importer.runtime_session import (
    FmiThreeFloat64Session,
)


class FmiThreeModelExchangeCoordinator:
    """Own accepted/candidate FMI state without choosing a numerical method.

    The coordinator takes ownership of one initialized-or-new FMI 3 session.
    It manages FMI lifecycle, event convergence, and native rollback while the
    caller retains integration, step-size, and event-localization policy.

    :param session: Isolated Model Exchange session transferred to this owner.
    :param maximum_event_iterations: Positive bound for one Event Mode fixpoint.
    """

    __slots__ = (
        "_session",
        "_maximum_event_iterations",
        "_initialized",
        "_has_checkpoint",
        "_accepted_time",
        "_accepted_states",
        "_accepted_inputs",
        "_accepted_readable_values",
        "_accepted_event_indicators",
        "_accepted_nominals",
        "_next_event_time",
        "_candidate_time",
        "_candidate_states",
        "_candidate_inputs",
        "_candidate_derivatives",
        "_candidate_readable_values",
        "_candidate_event_indicators",
    )

    def __init__(
        self,
        session: FmiThreeFloat64Session,
        maximum_event_iterations: int,
    ) -> None:
        """Store one session and an explicit finite event-iteration bound.

        :param session: Isolated Model Exchange session transferred to this owner.
        :param maximum_event_iterations: Positive Event Mode iteration limit.
        :return: None.
        """

        if (
            isinstance(maximum_event_iterations, int)
            and not isinstance(maximum_event_iterations, bool)
            and 1 <= maximum_event_iterations <= 1024
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 maximum Event Mode iterations must be an integer between 1 and 1024"
            )
        # Solver-coupled candidate rejection and localization must restore the
        # complete native FMU state.  Visible values cannot reconstruct hidden
        # event, integrator, or vendor state after an uncommitted evaluation.
        if session.supports_fmu_state_checkpoint():
            pass
        else:
            raise FmuModeError(
                "FMI 3 solver-coupled Model Exchange requires native FMU state checkpoints"
            )
        self._session: FmiThreeFloat64Session = session
        self._maximum_event_iterations: int = maximum_event_iterations
        self._initialized: bool = False
        self._has_checkpoint: bool = False
        self._accepted_time: float | None = None
        self._accepted_states: tuple[float, ...] | None = None
        self._accepted_inputs: tuple[float, ...] | None = None
        self._accepted_readable_values: tuple[float, ...] | None = None
        self._accepted_event_indicators: tuple[float, ...] | None = None
        self._accepted_nominals: tuple[float, ...] | None = None
        self._next_event_time: float | None = None
        self._candidate_time: float | None = None
        self._candidate_states: tuple[float, ...] | None = None
        self._candidate_inputs: tuple[float, ...] | None = None
        self._candidate_derivatives: tuple[float, ...] | None = None
        self._candidate_readable_values: tuple[float, ...] | None = None
        self._candidate_event_indicators: tuple[float, ...] | None = None

    def supports_rollback(self) -> bool:
        """Return whether native accepted-point rollback is available.

        :return: ``True`` when the FMU declared Get/Set/FreeFMUState.
        """

        return self._session.supports_fmu_state_checkpoint()

    def has_pending_candidate(self) -> bool:
        """Return whether one candidate awaits acceptance or rejection.

        :return: ``True`` after evaluation and before its resolution.
        """

        return self._candidate_time is not None

    def get_next_event_time(self) -> float | None:
        """Return the latest accepted FMI time-event request.

        :return: Absolute next event time or ``None`` when undefined.
        """

        return self._next_event_time

    def get_accepted_point(
        self,
    ) -> tuple[
        float,
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
    ]:
        """Return immutable accepted time, states, inputs, outputs, and scales.

        :return: Time, states, inputs, readable values, event indicators, and
            continuous-state nominals.
        :raises FmuModeError: If initialization has not established a point.
        """

        if (
            self._initialized
            and self._accepted_time is not None
            and self._accepted_states is not None
            and self._accepted_inputs is not None
            and self._accepted_readable_values is not None
            and self._accepted_event_indicators is not None
            and self._accepted_nominals is not None
        ):
            return (
                self._accepted_time,
                self._accepted_states,
                self._accepted_inputs,
                self._accepted_readable_values,
                self._accepted_event_indicators,
                self._accepted_nominals,
            )
        else:
            raise FmuModeError(
                "FMI 3 coordinator has no initialized accepted point"
            )

    def _clear_candidate(self) -> None:
        """Clear the bounded candidate snapshot without changing native state.

        :return: None.
        """

        self._candidate_time = None
        self._candidate_states = None
        self._candidate_inputs = None
        self._candidate_derivatives = None
        self._candidate_readable_values = None
        self._candidate_event_indicators = None

    def _settle_event_mode(
        self,
        entry_time: float,
    ) -> tuple[
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
    ]:
        """Converge one bounded Event Mode and return its continuous snapshot.

        :param entry_time: Exact finite time at which Event Mode was entered.
        :return: States, readable values, event indicators, and state nominals.
        :raises FmuImportError: If the FMU requests simulation termination.
        :raises FmuModeError: If the discrete-state fixpoint exceeds its bound.
        """

        normalized_entry_time: float = float(entry_time)
        if math.isfinite(normalized_entry_time):
            pass
        else:
            raise ValueError("FMI 3 Event Mode entry time must be finite")

        converged: bool = False
        event_iteration: int
        for event_iteration in range(self._maximum_event_iterations):
            discrete_result: FmiThreeWorkerDiscreteStatesResult = (
                self._session.update_model_exchange_discrete_states()
            )
            if discrete_result.terminate_simulation:
                raise FmuImportError(
                    "FMI 3 Model Exchange requested termination in Event Mode"
                )
            else:
                pass
            if discrete_result.next_event_time_defined:
                normalized_next_event_time: float = float(
                    discrete_result.next_event_time
                )
                if (
                    math.isfinite(normalized_next_event_time)
                    and normalized_next_event_time > normalized_entry_time
                ):
                    self._next_event_time = normalized_next_event_time
                else:
                    raise FmuModeError(
                        "FMI 3 nextEventTime must be finite and follow Event Mode entry"
                    )
            else:
                self._next_event_time = None
            if discrete_result.discrete_states_need_update:
                pass
            else:
                converged = True
                break
        if converged:
            pass
        else:
            raise FmuModeError(
                "FMI 3 Model Exchange Event Mode exceeded its iteration bound"
            )
        # Only a converged discrete state may return to continuous evaluation.
        self._session.enter_model_exchange_continuous_time_mode()
        state_values: tuple[float, ...]
        readable_values: tuple[float, ...]
        state_values, readable_values = (
            self._session.read_model_exchange_state_and_values()
        )
        event_indicators: tuple[float, ...] = (
            self._session.get_model_exchange_event_indicators()
        )
        nominal_values: tuple[float, ...] = (
            self._session.get_model_exchange_continuous_state_nominals()
        )
        return state_values, readable_values, event_indicators, nominal_values

    def initialize(
        self,
        start_time: float,
        stop_time: float | None,
        relative_tolerance: float | None,
        initial_writable_values: tuple[float, ...],
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Initialize, settle initial Event Mode, and establish acceptance.

        :param start_time: Finite simulation start time.
        :param stop_time: Optional finite stop time greater than the start.
        :param relative_tolerance: Optional finite positive relative tolerance.
        :param initial_writable_values: Complete bound FMI input vector.
        :return: Accepted continuous states and readable values.
        """

        if self._initialized:
            raise FmuModeError("FMI 3 coordinator is already initialized")
        else:
            pass
        self._session.initialize_model_exchange(
            start_time=start_time,
            stop_time=stop_time,
            relative_tolerance=relative_tolerance,
            initial_writable_float64_values=initial_writable_values,
        )
        state_values: tuple[float, ...]
        readable_values: tuple[float, ...]
        event_indicators: tuple[float, ...]
        nominal_values: tuple[float, ...]
        (
            state_values,
            readable_values,
            event_indicators,
            nominal_values,
        ) = self._settle_event_mode(entry_time=float(start_time))
        # The mandatory native checkpoint mirrors the accepted continuous-time
        # point before any solver-owned candidate can mutate the FMU.
        self._session.save_checkpoint()
        self._has_checkpoint = True
        self._accepted_time = float(start_time)
        self._accepted_states = state_values
        self._accepted_inputs = tuple(initial_writable_values)
        self._accepted_readable_values = readable_values
        self._accepted_event_indicators = event_indicators
        self._accepted_nominals = nominal_values
        self._clear_candidate()
        self._initialized = True
        return state_values, readable_values

    def evaluate_candidate(
        self,
        time_value: float,
        continuous_state_values: tuple[float, ...],
        writable_values: tuple[float, ...],
    ) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
        """Evaluate one candidate without accepting or integrating it.

        :param time_value: Candidate time not earlier than the accepted time.
        :param continuous_state_values: Complete solver-provided candidate state.
        :param writable_values: Complete bound FMI input vector at the candidate.
        :return: Derivatives, readable values, and event indicators.
        """

        accepted_time: float | None = self._accepted_time
        accepted_states: tuple[float, ...] | None = self._accepted_states
        if (
            self._initialized
            and accepted_time is not None
            and accepted_states is not None
            and not self.has_pending_candidate()
        ):
            pass
        else:
            raise FmuModeError(
                "FMI 3 candidate evaluation requires one free initialized slot"
            )
        normalized_time: float = float(time_value)
        if math.isfinite(normalized_time) and normalized_time >= accepted_time:
            pass
        else:
            raise ValueError(
                "FMI 3 candidate time must be finite and not precede acceptance"
            )
        if len(continuous_state_values) == len(accepted_states):
            pass
        else:
            raise ValueError(
                "FMI 3 candidate state cardinality differs from acceptance"
            )
        derivative_values: tuple[float, ...]
        readable_values: tuple[float, ...]
        derivative_values, readable_values = (
            self._session.evaluate_model_exchange(
                time_value=normalized_time,
                continuous_state_values=continuous_state_values,
                writable_float64_values=writable_values,
            )
        )
        event_indicators: tuple[float, ...] = (
            self._session.get_model_exchange_event_indicators()
        )
        self._candidate_time = normalized_time
        self._candidate_states = tuple(continuous_state_values)
        self._candidate_inputs = tuple(writable_values)
        self._candidate_derivatives = derivative_values
        self._candidate_readable_values = readable_values
        self._candidate_event_indicators = event_indicators
        return derivative_values, readable_values, event_indicators

    def evaluate_probe(
        self,
        time_value: float,
        continuous_state_values: tuple[float, ...],
        writable_values: tuple[float, ...],
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Evaluate a temporary continuous point without creating a candidate.

        The mandatory native checkpoint is restored after the probe so hidden
        FMU state cannot escape an uncommitted solver evaluation.

        :param time_value: Finite probe time not earlier than acceptance.
        :param continuous_state_values: Complete solver-provided probe state.
        :param writable_values: Complete bound FMI input vector.
        :return: Derivatives and readable values at the probe point.
        """

        accepted_time: float | None = self._accepted_time
        accepted_states: tuple[float, ...] | None = self._accepted_states
        if (
            self._initialized
            and accepted_time is not None
            and accepted_states is not None
            and not self.has_pending_candidate()
        ):
            pass
        else:
            raise FmuModeError(
                "FMI 3 probe evaluation requires one free initialized slot"
            )
        normalized_time: float = float(time_value)
        if math.isfinite(normalized_time) and normalized_time >= accepted_time:
            pass
        else:
            raise ValueError(
                "FMI 3 probe time must be finite and not precede acceptance"
            )
        if len(continuous_state_values) == len(accepted_states):
            pass
        else:
            raise ValueError(
                "FMI 3 probe state cardinality differs from acceptance"
            )
        derivative_values: tuple[float, ...]
        readable_values: tuple[float, ...]
        derivative_values, readable_values = (
            self._session.evaluate_model_exchange(
                time_value=normalized_time,
                continuous_state_values=continuous_state_values,
                writable_float64_values=writable_values,
            )
        )
        # Probes must never displace the native accepted point.
        self._session.restore_checkpoint()
        return derivative_values, readable_values

    def evaluate_event_indicators_probe(
        self,
        time_value: float,
        continuous_state_values: tuple[float, ...],
    ) -> tuple[float, ...]:
        """Evaluate event indicators inside the current candidate interval.

        The caller supplies an interpolated continuous state while this
        coordinator preserves the already prepared candidate.  Restoring that
        candidate after every probe keeps ``accept_candidate()`` independent
        while native checkpoint restoration preserves hidden FMU state.

        :param time_value: Probe time inside the accepted-candidate interval.
        :param continuous_state_values: Interpolated complete state vector.
        :return: Event indicators at the probe point.
        :raises FmuModeError: If no complete candidate interval is available.
        """

        accepted_time: float | None = self._accepted_time
        accepted_states: tuple[float, ...] | None = self._accepted_states
        candidate_time: float | None = self._candidate_time
        candidate_states: tuple[float, ...] | None = self._candidate_states
        candidate_inputs: tuple[float, ...] | None = self._candidate_inputs
        if (
            self._initialized
            and accepted_time is not None
            and accepted_states is not None
            and candidate_time is not None
            and candidate_states is not None
            and candidate_inputs is not None
        ):
            pass
        else:
            raise FmuModeError(
                "FMI 3 event-indicator probe requires a complete candidate interval"
            )

        normalized_time: float = float(time_value)
        if (
            math.isfinite(normalized_time)
            and accepted_time <= normalized_time <= candidate_time
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 event-indicator probe must remain inside its candidate interval"
            )
        if len(continuous_state_values) == len(accepted_states):
            pass
        else:
            raise ValueError(
                "FMI 3 event-indicator probe state cardinality differs from acceptance"
            )

        # Evaluate only an uncommitted continuous point; Event Mode remains
        # frozen until the owning solver has selected the global first event.
        self._session.evaluate_model_exchange(
            time_value=normalized_time,
            continuous_state_values=continuous_state_values,
            writable_float64_values=candidate_inputs,
        )
        probe_event_indicators: tuple[float, ...] = (
            self._session.get_model_exchange_event_indicators()
        )

        # The native instance must again represent the prepared endpoint before
        # it can be accepted or rejected by the surrounding transaction.
        self._session.restore_checkpoint()
        self._session.evaluate_model_exchange(
            time_value=candidate_time,
            continuous_state_values=candidate_states,
            writable_float64_values=candidate_inputs,
        )
        return probe_event_indicators

    def reject_candidate(self) -> None:
        """Restore the accepted native point and clear the candidate.

        :return: None.
        :raises FmuModeError: If no complete candidate or acceptance exists.
        """

        accepted_time: float | None = self._accepted_time
        if (
            self.has_pending_candidate()
            and accepted_time is not None
        ):
            # Native restoration is the only accepted rollback mechanism
            # because complete hidden state is not representable in VeraGrid.
            self._session.restore_checkpoint()
            self._clear_candidate()
        else:
            raise FmuModeError(
                "FMI 3 candidate rejection requires complete accepted and candidate points"
            )

    def accept_candidate(
        self,
        importer_detected_event: bool,
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Accept one candidate and settle Event Mode when requested.

        :param importer_detected_event: Whether the solver localized an event at
            the candidate point.
        :return: Accepted continuous states and readable values after events.
        :raises FmuImportError: If the FMU requests simulation termination.
        """

        candidate_time: float | None = self._candidate_time
        candidate_states: tuple[float, ...] | None = self._candidate_states
        candidate_inputs: tuple[float, ...] | None = self._candidate_inputs
        candidate_readable_values: tuple[float, ...] | None = (
            self._candidate_readable_values
        )
        candidate_event_indicators: tuple[float, ...] | None = (
            self._candidate_event_indicators
        )
        previous_nominals: tuple[float, ...] | None = self._accepted_nominals
        if (
            self.has_pending_candidate()
            and candidate_time is not None
            and candidate_states is not None
            and candidate_inputs is not None
            and candidate_readable_values is not None
            and candidate_event_indicators is not None
            and previous_nominals is not None
        ):
            pass
        else:
            raise FmuModeError(
                "FMI 3 candidate acceptance requires a complete candidate"
            )
        completed_result: FmiThreeWorkerCompletedIntegratorStepResult = (
            self._session.complete_model_exchange_integrator_step(
                no_set_fmu_state_prior_to_current_point=False
            )
        )
        if completed_result.terminate_simulation:
            raise FmuImportError(
                "FMI 3 Model Exchange requested simulation termination"
            )
        else:
            pass
        event_is_required: bool = (
            bool(importer_detected_event) or completed_result.enter_event_mode
        )
        accepted_states: tuple[float, ...]
        accepted_readable_values: tuple[float, ...]
        accepted_event_indicators: tuple[float, ...]
        accepted_nominals: tuple[float, ...]
        if event_is_required:
            self._session.enter_model_exchange_event_mode()
            (
                accepted_states,
                accepted_readable_values,
                accepted_event_indicators,
                accepted_nominals,
            ) = self._settle_event_mode(entry_time=candidate_time)
        else:
            accepted_states = candidate_states
            accepted_readable_values = candidate_readable_values
            accepted_event_indicators = candidate_event_indicators
            accepted_nominals = previous_nominals
        # Replacing the checkpoint commits the new accepted FMI internal state.
        self._session.save_checkpoint()
        self._has_checkpoint = True
        self._accepted_time = candidate_time
        self._accepted_states = accepted_states
        self._accepted_inputs = candidate_inputs
        self._accepted_readable_values = accepted_readable_values
        self._accepted_event_indicators = accepted_event_indicators
        self._accepted_nominals = accepted_nominals
        self._clear_candidate()
        return accepted_states, accepted_readable_values

    def close(self) -> None:
        """Release the owned session and clear all coordinator snapshots.

        :return: None.
        """

        self._session.close()
        self._initialized = False
        self._has_checkpoint = False
        self._accepted_time = None
        self._accepted_states = None
        self._accepted_inputs = None
        self._accepted_readable_values = None
        self._accepted_event_indicators = None
        self._accepted_nominals = None
        self._next_event_time = None
        self._clear_candidate()
