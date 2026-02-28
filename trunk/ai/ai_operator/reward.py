from __future__ import annotations

from typing import Any

import numpy as np

from trunk.ai.ai_operator.actions import BranchSwitchAction
from trunk.ai.ai_operator.actions import GeneratorRedispatchAction
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
