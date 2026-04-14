from __future__ import annotations

from typing import Any

import numpy as np

from trunk.ai.ai_operator.actions import BranchSwitchAction
from trunk.ai.ai_operator.actions import GeneratorRedispatchAction
from trunk.ai.ai_operator.actions import NoOpAction
from trunk.ai.ai_operator.actions import OperatorAction
from trunk.ai.ai_operator.config import RewardWeights


class RewardBreakdown:
    """
    Typed reward breakdown container.

    :param voltage_penalty:
        Voltage violation contribution.
    :param overload_penalty:
        Branch overload contribution.
    :param generator_penalty:
        Generator limit contribution.
    :param action_penalty:
        Action magnitude or topology manipulation contribution.
    :param secure_bonus:
        Positive secure operation contribution.
    :param pf_divergence_penalty:
        Non-convergence contribution.
    """

    __slots__ = (
        "_voltage_penalty",
        "_overload_penalty",
        "_generator_penalty",
        "_action_penalty",
        "_secure_bonus",
        "_pf_divergence_penalty",
    )

    def __init__(
        self,
        voltage_penalty: float,
        overload_penalty: float,
        generator_penalty: float,
        action_penalty: float,
        secure_bonus: float,
        pf_divergence_penalty: float,
    ) -> None:
        self._voltage_penalty: float = voltage_penalty
        self._overload_penalty: float = overload_penalty
        self._generator_penalty: float = generator_penalty
        self._action_penalty: float = action_penalty
        self._secure_bonus: float = secure_bonus
        self._pf_divergence_penalty: float = pf_divergence_penalty

    def get_total_reward(self) -> float:
        """
        Compute the total reward.

        :return:
            Sum of all reward components.
        """

        return (
            self._voltage_penalty
            + self._overload_penalty
            + self._generator_penalty
            + self._action_penalty
            + self._secure_bonus
            + self._pf_divergence_penalty
        )

    def get_voltage_penalty(self) -> float:
        """
        Get the voltage penalty term.

        :return:
            Voltage penalty.
        """

        return self._voltage_penalty

    def get_overload_penalty(self) -> float:
        """
        Get the overload penalty term.

        :return:
            Overload penalty.
        """

        return self._overload_penalty

    def get_generator_penalty(self) -> float:
        """
        Get the generator penalty term.

        :return:
            Generator limit penalty.
        """

        return self._generator_penalty

    def get_action_penalty(self) -> float:
        """
        Get the action penalty term.

        :return:
            Action penalty.
        """

        return self._action_penalty

    def get_secure_bonus(self) -> float:
        """
        Get the secure operation bonus.

        :return:
            Secure bonus.
        """

        return self._secure_bonus

    def get_pf_divergence_penalty(self) -> float:
        """
        Get the PF divergence penalty term.

        :return:
            Divergence penalty.
        """

        return self._pf_divergence_penalty


class GridMetricSnapshot:
    """
    Typed grid-state metric snapshot.

    :param pf_converged:
        ``True`` when the post-action PF converged.
    :param secure_state:
        ``True`` when the state respects all tracked engineering limits.
    :param voltage_violation_sum:
        Summed absolute voltage limit violation.
    :param overload_violation_sum:
        Summed branch overload amount.
    :param generator_violation_sum:
        Summed generator active-power limit violation.
    :param minimum_voltage:
        Minimum bus voltage magnitude.
    :param maximum_voltage:
        Maximum bus voltage magnitude.
    :param maximum_branch_loading:
        Maximum branch loading ratio.
    """

    __slots__ = (
        "_pf_converged",
        "_secure_state",
        "_voltage_violation_sum",
        "_overload_violation_sum",
        "_generator_violation_sum",
        "_minimum_voltage",
        "_maximum_voltage",
        "_maximum_branch_loading",
    )

    def __init__(
        self,
        pf_converged: bool,
        secure_state: bool,
        voltage_violation_sum: float,
        overload_violation_sum: float,
        generator_violation_sum: float,
        minimum_voltage: float,
        maximum_voltage: float,
        maximum_branch_loading: float,
    ) -> None:
        self._pf_converged: bool = pf_converged
        self._secure_state: bool = secure_state
        self._voltage_violation_sum: float = voltage_violation_sum
        self._overload_violation_sum: float = overload_violation_sum
        self._generator_violation_sum: float = generator_violation_sum
        self._minimum_voltage: float = minimum_voltage
        self._maximum_voltage: float = maximum_voltage
        self._maximum_branch_loading: float = maximum_branch_loading

    def get_pf_converged(self) -> bool:
        """
        Get the PF convergence flag.

        :return:
            ``True`` when the PF converged.
        """

        return self._pf_converged

    def get_secure_state(self) -> bool:
        """
        Get the secure-state flag.

        :return:
            ``True`` when all tracked limits are respected.
        """

        return self._secure_state

    def get_voltage_violation_sum(self) -> float:
        """
        Get the summed voltage violation amount.

        :return:
            Summed voltage violation.
        """

        return self._voltage_violation_sum

    def get_overload_violation_sum(self) -> float:
        """
        Get the summed branch overload amount.

        :return:
            Summed overload amount.
        """

        return self._overload_violation_sum

    def get_generator_violation_sum(self) -> float:
        """
        Get the summed generator violation amount.

        :return:
            Summed generator violation.
        """

        return self._generator_violation_sum

    def get_minimum_voltage(self) -> float:
        """
        Get the minimum bus voltage magnitude.

        :return:
            Minimum voltage magnitude.
        """

        return self._minimum_voltage

    def get_maximum_voltage(self) -> float:
        """
        Get the maximum bus voltage magnitude.

        :return:
            Maximum voltage magnitude.
        """

        return self._maximum_voltage

    def get_maximum_branch_loading(self) -> float:
        """
        Get the maximum branch loading ratio.

        :return:
            Maximum branch loading ratio.
        """

        return self._maximum_branch_loading


class GridMetricSummary:
    """
    Episode-level aggregated grid metrics.

    :param pf_convergence_rate:
        Fraction of steps with converged PF.
    :param secure_rate:
        Fraction of steps with a secure operating point.
    :param mean_voltage_violation:
        Mean summed voltage violation per step.
    :param mean_overload_violation:
        Mean summed branch overload per step.
    :param mean_generator_violation:
        Mean summed generator violation per step.
    :param mean_minimum_voltage:
        Mean minimum bus voltage magnitude.
    :param mean_maximum_voltage:
        Mean maximum bus voltage magnitude.
    :param mean_maximum_branch_loading:
        Mean maximum branch loading ratio.
    """

    __slots__ = (
        "_pf_convergence_rate",
        "_secure_rate",
        "_mean_voltage_violation",
        "_mean_overload_violation",
        "_mean_generator_violation",
        "_mean_minimum_voltage",
        "_mean_maximum_voltage",
        "_mean_maximum_branch_loading",
    )

    def __init__(
        self,
        pf_convergence_rate: float,
        secure_rate: float,
        mean_voltage_violation: float,
        mean_overload_violation: float,
        mean_generator_violation: float,
        mean_minimum_voltage: float,
        mean_maximum_voltage: float,
        mean_maximum_branch_loading: float,
    ) -> None:
        self._pf_convergence_rate: float = pf_convergence_rate
        self._secure_rate: float = secure_rate
        self._mean_voltage_violation: float = mean_voltage_violation
        self._mean_overload_violation: float = mean_overload_violation
        self._mean_generator_violation: float = mean_generator_violation
        self._mean_minimum_voltage: float = mean_minimum_voltage
        self._mean_maximum_voltage: float = mean_maximum_voltage
        self._mean_maximum_branch_loading: float = mean_maximum_branch_loading

    def get_pf_convergence_rate(self) -> float:
        """
        Get the PF convergence rate.

        :return:
            PF convergence rate.
        """

        return self._pf_convergence_rate

    def get_secure_rate(self) -> float:
        """
        Get the secure-state rate.

        :return:
            Secure-state rate.
        """

        return self._secure_rate

    def get_mean_voltage_violation(self) -> float:
        """
        Get the mean voltage violation.

        :return:
            Mean summed voltage violation per step.
        """

        return self._mean_voltage_violation

    def get_mean_overload_violation(self) -> float:
        """
        Get the mean overload violation.

        :return:
            Mean summed overload violation per step.
        """

        return self._mean_overload_violation

    def get_mean_generator_violation(self) -> float:
        """
        Get the mean generator violation.

        :return:
            Mean summed generator violation per step.
        """

        return self._mean_generator_violation

    def get_mean_minimum_voltage(self) -> float:
        """
        Get the mean minimum voltage.

        :return:
            Mean minimum voltage magnitude.
        """

        return self._mean_minimum_voltage

    def get_mean_maximum_voltage(self) -> float:
        """
        Get the mean maximum voltage.

        :return:
            Mean maximum voltage magnitude.
        """

        return self._mean_maximum_voltage

    def get_mean_maximum_branch_loading(self) -> float:
        """
        Get the mean maximum branch loading.

        :return:
            Mean maximum branch loading ratio.
        """

        return self._mean_maximum_branch_loading


def compute_grid_metric_snapshot(
    nc: Any,
    pf_results: Any,
    pf_converged: bool,
) -> GridMetricSnapshot:
    """
    Compute one compact grid-state metric snapshot from a PF state.

    :param nc:
        Numerical circuit for the current grid state.
    :param pf_results:
        Power flow results for the current grid state.
    :param pf_converged:
        ``True`` when the PF converged.
    :return:
        Grid metric snapshot.
    """

    if pf_converged:
        bus_voltage_magnitude: np.ndarray = np.abs(pf_results.voltage)
        bus_voltage_max: np.ndarray = nc.bus_data.Vmax
        bus_voltage_min: np.ndarray = nc.bus_data.Vmin
        branch_loading: np.ndarray = np.abs(pf_results.loading)
        branch_limits: np.ndarray = nc.passive_branch_data.contingency_rates
        generator_p: np.ndarray = nc.generator_data.p
        generator_pmax: np.ndarray = nc.generator_data.pmax
        generator_pmin: np.ndarray = nc.generator_data.pmin

        voltage_violation: np.ndarray = np.maximum(bus_voltage_magnitude - bus_voltage_max, 0.0)
        voltage_violation += np.maximum(bus_voltage_min - bus_voltage_magnitude, 0.0)
        overload_violation: np.ndarray = np.maximum(branch_loading - branch_limits, 0.0)
        generator_violation: np.ndarray = np.maximum(generator_p - generator_pmax, 0.0)
        generator_violation += np.maximum(generator_pmin - generator_p, 0.0)

        secure_state: bool = bool(
            np.all(bus_voltage_magnitude <= bus_voltage_max)
            and np.all(bus_voltage_magnitude >= bus_voltage_min)
            and np.all(branch_loading <= branch_limits)
            and np.all(generator_p <= generator_pmax)
            and np.all(generator_p >= generator_pmin)
        )
        return GridMetricSnapshot(
            pf_converged=True,
            secure_state=secure_state,
            voltage_violation_sum=float(np.sum(voltage_violation)),
            overload_violation_sum=float(np.sum(overload_violation)),
            generator_violation_sum=float(np.sum(generator_violation)),
            minimum_voltage=float(np.min(bus_voltage_magnitude)) if bus_voltage_magnitude.size > 0 else 0.0,
            maximum_voltage=float(np.max(bus_voltage_magnitude)) if bus_voltage_magnitude.size > 0 else 0.0,
            maximum_branch_loading=float(np.max(branch_loading)) if branch_loading.size > 0 else 0.0,
        )
    else:
        return GridMetricSnapshot(
            pf_converged=False,
            secure_state=False,
            voltage_violation_sum=0.0,
            overload_violation_sum=0.0,
            generator_violation_sum=0.0,
            minimum_voltage=0.0,
            maximum_voltage=0.0,
            maximum_branch_loading=0.0,
        )


def compute_reward(
    nc: Any,
    pf_results: Any,
    action: OperatorAction,
    weights: RewardWeights,
    pf_converged: bool,
) -> RewardBreakdown:
    """
    Compute the reward breakdown for the post-action PF state.

    :param nc:
        Numerical circuit for the current grid state.
    :param pf_results:
        Power flow results for the current grid state.
    :param action:
        Action applied before solving the PF.
    :param weights:
        Reward weight bundle.
    :param pf_converged:
        ``True`` when the power flow converged.
    :return:
        Structured reward breakdown.
    """

    if pf_converged:
        # The converged path computes all engineering violations from the PF state
        # so the agent learns to prefer feasible and secure operating points.
        bus_voltage_magnitude: np.ndarray = np.abs(pf_results.voltage)
        bus_voltage_max: np.ndarray = nc.bus_data.Vmax
        bus_voltage_min: np.ndarray = nc.bus_data.Vmin
        branch_loading: np.ndarray = np.abs(pf_results.loading)
        branch_limits: np.ndarray = nc.passive_branch_data.contingency_rates
        generator_p: np.ndarray = nc.generator_data.p
        generator_pmax: np.ndarray = nc.generator_data.pmax
        generator_pmin: np.ndarray = nc.generator_data.pmin

        voltage_violation: np.ndarray = np.maximum(bus_voltage_magnitude - bus_voltage_max, 0.0)
        voltage_violation += np.maximum(bus_voltage_min - bus_voltage_magnitude, 0.0)
        overload_violation: np.ndarray = np.maximum(branch_loading - branch_limits, 0.0)
        generator_violation: np.ndarray = np.maximum(generator_p - generator_pmax, 0.0)
        generator_violation += np.maximum(generator_pmin - generator_p, 0.0)

        voltage_penalty: float = -weights.get_voltage_violation() * float(np.sum(voltage_violation))
        overload_penalty: float = -weights.get_branch_overload() * float(np.sum(overload_violation))
        generator_penalty: float = -weights.get_generator_limit() * float(np.sum(generator_violation))

        action_penalty: float
        if isinstance(action, BranchSwitchAction):
            action_penalty = -weights.get_switching_cost()
        else:
            if isinstance(action, GeneratorRedispatchAction):
                action_penalty = -weights.get_redispatch_cost() * abs(action.get_delta_mw())
            else:
                action_penalty = 0.0

        secure_state: bool = bool(
            np.all(bus_voltage_magnitude <= bus_voltage_max)
            and np.all(bus_voltage_magnitude >= bus_voltage_min)
            and np.all(branch_loading <= branch_limits)
            and np.all(generator_p <= generator_pmax)
            and np.all(generator_p >= generator_pmin)
        )
        secure_bonus: float
        if secure_state:
            secure_bonus = weights.get_secure_operation_bonus()
        else:
            secure_bonus = 0.0

        return RewardBreakdown(
            voltage_penalty=voltage_penalty,
            overload_penalty=overload_penalty,
            generator_penalty=generator_penalty,
            action_penalty=action_penalty,
            secure_bonus=secure_bonus,
            pf_divergence_penalty=0.0,
        )
    else:
        # The non-converged path gives a dominant negative signal because the action
        # moved the system into a state that the solver cannot validate as operable.
        return RewardBreakdown(
            voltage_penalty=0.0,
            overload_penalty=0.0,
            generator_penalty=0.0,
            action_penalty=0.0,
            secure_bonus=0.0,
            pf_divergence_penalty=-weights.get_pf_divergence(),
        )


def compute_reward_for_action_list(
    nc: Any,
    pf_results: Any,
    actions: list[OperatorAction],
    weights: RewardWeights,
    pf_converged: bool,
) -> RewardBreakdown:
    """
    Compute the reward breakdown for a concurrent action batch.

    :param nc:
        Numerical circuit for the current grid state.
    :param pf_results:
        Power flow results for the current grid state.
    :param actions:
        Concurrent action batch applied before solving the PF.
    :param weights:
        Reward weight bundle.
    :param pf_converged:
        ``True`` when the power flow converged.
    :return:
        Structured reward breakdown.
    """

    if pf_converged:
        bus_voltage_magnitude: np.ndarray = np.abs(pf_results.voltage)
        bus_voltage_max: np.ndarray = nc.bus_data.Vmax
        bus_voltage_min: np.ndarray = nc.bus_data.Vmin
        branch_loading: np.ndarray = np.abs(pf_results.loading)
        branch_limits: np.ndarray = nc.passive_branch_data.contingency_rates
        generator_p: np.ndarray = nc.generator_data.p
        generator_pmax: np.ndarray = nc.generator_data.pmax
        generator_pmin: np.ndarray = nc.generator_data.pmin

        voltage_violation: np.ndarray = np.maximum(bus_voltage_magnitude - bus_voltage_max, 0.0)
        voltage_violation += np.maximum(bus_voltage_min - bus_voltage_magnitude, 0.0)
        overload_violation: np.ndarray = np.maximum(branch_loading - branch_limits, 0.0)
        generator_violation: np.ndarray = np.maximum(generator_p - generator_pmax, 0.0)
        generator_violation += np.maximum(generator_pmin - generator_p, 0.0)

        voltage_penalty: float = -weights.get_voltage_violation() * float(np.sum(voltage_violation))
        overload_penalty: float = -weights.get_branch_overload() * float(np.sum(overload_violation))
        generator_penalty: float = -weights.get_generator_limit() * float(np.sum(generator_violation))
        action_penalty: float = compute_action_penalty_for_action_list(actions=actions, weights=weights)

        secure_state: bool = bool(
            np.all(bus_voltage_magnitude <= bus_voltage_max)
            and np.all(bus_voltage_magnitude >= bus_voltage_min)
            and np.all(branch_loading <= branch_limits)
            and np.all(generator_p <= generator_pmax)
            and np.all(generator_p >= generator_pmin)
        )
        secure_bonus: float = weights.get_secure_operation_bonus() if secure_state else 0.0

        return RewardBreakdown(
            voltage_penalty=voltage_penalty,
            overload_penalty=overload_penalty,
            generator_penalty=generator_penalty,
            action_penalty=action_penalty,
            secure_bonus=secure_bonus,
            pf_divergence_penalty=0.0,
        )
    else:
        return RewardBreakdown(
            voltage_penalty=0.0,
            overload_penalty=0.0,
            generator_penalty=0.0,
            action_penalty=0.0,
            secure_bonus=0.0,
            pf_divergence_penalty=-weights.get_pf_divergence(),
        )


def compute_action_penalty_for_action_list(actions: list[OperatorAction], weights: RewardWeights) -> float:
    """
    Compute the summed action penalty for a concurrent action batch.

    :param actions:
        Concurrent action batch.
    :param weights:
        Reward weight bundle.
    :return:
        Summed action penalty.
    """

    action_penalty: float = 0.0
    action_idx: int

    for action_idx in range(len(actions)):
        action_penalty += compute_action_penalty_for_action(actions[action_idx], weights)

    return action_penalty


def compute_action_penalty_for_action(action: OperatorAction, weights: RewardWeights) -> float:
    """
    Compute the action penalty for one action.

    :param action:
        Action object.
    :param weights:
        Reward weight bundle.
    :return:
        Action penalty contribution.
    """

    if isinstance(action, BranchSwitchAction):
        return -weights.get_switching_cost()
    else:
        if isinstance(action, GeneratorRedispatchAction):
            return -weights.get_redispatch_cost() * abs(action.get_delta_mw())
        else:
            if isinstance(action, NoOpAction):
                return 0.0
            else:
                return 0.0
