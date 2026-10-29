from __future__ import annotations

from typing import Any

import numpy as np

from trunk.ai.ai_operator.environment import StepInfo
from trunk.ai.ai_operator.environment import VeraGridOperatorEnv
from trunk.ai.ai_operator.network import OperatorPolicyNetwork
from trunk.ai.ai_operator.network import OperatorPolicyOutput
from trunk.ai.ai_operator.network import select_action_with_policy
from trunk.ai.ai_operator.observations import ObservationData


class RolloutRecord:
    """
    Single rollout step record.

    :param action:
        Action applied at the step.
    :param reward:
        Reward observed after the action.
    :param terminated:
        Episode termination flag.
    :param truncated:
        Episode truncation flag.
    :param step_info:
        Extra metadata from the environment.
    :param observation:
        Observation before the action.
    :param next_observation:
        Observation after the action.
    """

    __slots__ = (
        "_action",
        "_reward",
        "_terminated",
        "_truncated",
        "_step_info",
        "_observation",
        "_next_observation",
    )

    def __init__(
        self,
        action: Any,
        reward: float,
        terminated: bool,
        truncated: bool,
        step_info: StepInfo,
        observation: ObservationData,
        next_observation: ObservationData,
    ) -> None:
        self._action: Any = action
        self._reward: float = reward
        self._terminated: bool = terminated
        self._truncated: bool = truncated
        self._step_info: StepInfo = step_info
        self._observation: ObservationData = observation
        self._next_observation: ObservationData = next_observation

    def get_action(self) -> Any:
        """
        Get the action.

        :return:
            Action object.
        """

        return self._action

    def get_reward(self) -> float:
        """
        Get the reward.

        :return:
            Scalar reward.
        """

        return self._reward

    def get_terminated(self) -> bool:
        """
        Get the termination flag.

        :return:
            ``True`` when the episode terminated.
        """

        return self._terminated

    def get_truncated(self) -> bool:
        """
        Get the truncation flag.

        :return:
            ``True`` when the episode truncated.
        """

        return self._truncated

    def get_step_info(self) -> StepInfo:
        """
        Get the step metadata.

        :return:
            Step metadata object.
        """

        return self._step_info


class PolicyRolloutRecord:
    """
    Single policy rollout step record.

    :param action:
        Action selected by the neural policy.
    :param reward:
        Reward observed after the action.
    :param terminated:
        Episode termination flag.
    :param truncated:
        Episode truncation flag.
    :param step_info:
        Extra metadata from the environment.
    :param observation:
        Observation before the action.
    :param next_observation:
        Observation after the action.
    :param policy_output:
        Raw network output used to decode the action.
    """

    __slots__ = (
        "_action",
        "_reward",
        "_terminated",
        "_truncated",
        "_step_info",
        "_observation",
        "_next_observation",
        "_policy_output",
    )

    def __init__(
        self,
        action: Any,
        reward: float,
        terminated: bool,
        truncated: bool,
        step_info: StepInfo,
        observation: ObservationData,
        next_observation: ObservationData,
        policy_output: OperatorPolicyOutput,
    ) -> None:
        self._action: Any = action
        self._reward: float = reward
        self._terminated: bool = terminated
        self._truncated: bool = truncated
        self._step_info: StepInfo = step_info
        self._observation: ObservationData = observation
        self._next_observation: ObservationData = next_observation
        self._policy_output: OperatorPolicyOutput = policy_output

    def get_action(self) -> Any:
        """
        Get the action.

        :return:
            Action object.
        """

        return self._action

    def get_reward(self) -> float:
        """
        Get the reward.

        :return:
            Scalar reward.
        """

        return self._reward

    def get_terminated(self) -> bool:
        """
        Get the termination flag.

        :return:
            ``True`` when the episode terminated.
        """

        return self._terminated

    def get_truncated(self) -> bool:
        """
        Get the truncation flag.

        :return:
            ``True`` when the episode truncated.
        """

        return self._truncated

    def get_step_info(self) -> StepInfo:
        """
        Get the step metadata.

        :return:
            Step metadata object.
        """

        return self._step_info

    def get_policy_output(self) -> OperatorPolicyOutput:
        """
        Get the raw network output.

        :return:
            Policy output bundle.
        """

        return self._policy_output


def run_random_rollout(
    env: VeraGridOperatorEnv,
    steps: int,
    seed: int | None = None,
) -> list[RolloutRecord]:
    """
    Run a baseline random rollout for smoke testing.

    :param env:
        Operator environment instance.
    :param steps:
        Maximum number of rollout steps.
    :param seed:
        Optional RNG seed.
    :return:
        Rollout step records.
    """

    # This baseline rollout is intentionally simple and is used to validate the control
    # loop mechanics before integrating a real learning algorithm.
    rng: np.random.Generator = np.random.default_rng(seed)
    history: list[RolloutRecord] = list()
    observation: ObservationData = env.reset()
    step_idx: int

    for step_idx in range(steps):
        action: Any = env.sample_action(rng=rng)
        next_observation: ObservationData
        reward: float
        terminated: bool
        truncated: bool
        step_info: StepInfo
        next_observation, reward, terminated, truncated, step_info = env.step(action)
        history.append(
            RolloutRecord(
                action=action,
                reward=reward,
                terminated=terminated,
                truncated=truncated,
                step_info=step_info,
                observation=observation,
                next_observation=next_observation,
            )
        )
        observation = next_observation

        if terminated or truncated:
            break
        else:
            step_idx = step_idx

    return history


def run_policy_rollout(
    env: VeraGridOperatorEnv,
    policy_network: OperatorPolicyNetwork,
    steps: int,
) -> list[PolicyRolloutRecord]:
    """
    Run a rollout driven by the neural operator policy.

    :param env:
        Operator environment instance.
    :param policy_network:
        Neural operator policy.
    :param steps:
        Maximum number of rollout steps.
    :return:
        Policy rollout step records.
    """

    # This rollout uses the policy network rather than the random sampler, which is
    # the direct path needed for later RL training and evaluation loops.
    history: list[PolicyRolloutRecord] = list()
    observation: ObservationData = env.reset()
    step_idx: int

    for step_idx in range(steps):
        action: Any
        policy_output: OperatorPolicyOutput
        action, policy_output = select_action_with_policy(
            policy_network=policy_network,
            observation=observation,
            branch_count=env.get_branch_count(),
            generator_count=env.get_generator_count(),
        )

        next_observation: ObservationData
        reward: float
        terminated: bool
        truncated: bool
        step_info: StepInfo
        next_observation, reward, terminated, truncated, step_info = env.step(action)

        history.append(
            PolicyRolloutRecord(
                action=action,
                reward=reward,
                terminated=terminated,
                truncated=truncated,
                step_info=step_info,
                observation=observation,
                next_observation=next_observation,
                policy_output=policy_output,
            )
        )
        observation = next_observation

        if terminated or truncated:
            break
        else:
            step_idx = step_idx

    return history
