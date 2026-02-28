from __future__ import annotations

from typing import Any

import numpy as np

from trunk.ai.ai_operator.actions import BranchSwitchAction
from trunk.ai.ai_operator.actions import GeneratorRedispatchAction
from trunk.ai.ai_operator.actions import OperatorAction
from trunk.ai.ai_operator.agents import AgentAlignment
from trunk.ai.ai_operator.agents import AgentActionScope
from trunk.ai.ai_operator.agents import AgentSpec
from trunk.ai.ai_operator.agents import MultiAgentConfig
from trunk.ai.ai_operator.environment import StepInfo
from trunk.ai.ai_operator.environment import VeraGridOperatorEnv
from trunk.ai.ai_operator.observations import ObservationData


class MultiAgentReset:
    """
    Multi-agent reset payload.

    :param observation:
        Initial observation.
    :param active_agent:
        Agent that must act first.
    """

    __slots__ = ("_observation", "_active_agent")

    def __init__(self, observation: ObservationData, active_agent: AgentSpec) -> None:
        self._observation: ObservationData = observation
        self._active_agent: AgentSpec = active_agent

    def get_observation(self) -> ObservationData:
        """
        Get the initial observation.

        :return:
            Observation object.
        """

        return self._observation

    def get_active_agent(self) -> AgentSpec:
        """
        Get the first active agent.

        :return:
            Active agent description.
        """

        return self._active_agent


class MultiAgentStepInfo:
    """
    Multi-agent step metadata bundle.

    :param acting_agent:
        Agent that just acted.
    :param next_agent:
        Agent that acts next.
    :param base_reward:
        Raw reward from the base environment.
    :param aligned_reward:
        Reward after agent alignment transformation.
    :param base_step_info:
        Original single-agent step info.
    :param turn_idx:
        Global multi-agent turn index.
    :param requested_action:
        Action requested by the agent policy before scope projection.
    :param applied_action:
        Action applied after scope projection.
    """

    __slots__ = (
        "_acting_agent",
        "_next_agent",
        "_base_reward",
        "_aligned_reward",
        "_base_step_info",
        "_turn_idx",
        "_requested_action",
        "_applied_action",
    )

    def __init__(
        self,
        acting_agent: AgentSpec,
        next_agent: AgentSpec,
        base_reward: float,
        aligned_reward: float,
        base_step_info: StepInfo,
        turn_idx: int,
        requested_action: OperatorAction,
        applied_action: OperatorAction,
    ) -> None:
        self._acting_agent: AgentSpec = acting_agent
        self._next_agent: AgentSpec = next_agent
        self._base_reward: float = base_reward
        self._aligned_reward: float = aligned_reward
        self._base_step_info: StepInfo = base_step_info
        self._turn_idx: int = turn_idx
        self._requested_action: OperatorAction = requested_action
        self._applied_action: OperatorAction = applied_action

    def get_acting_agent(self) -> AgentSpec:
        """
        Get the acting agent.

        :return:
            Acting agent description.
        """

        return self._acting_agent

    def get_next_agent(self) -> AgentSpec:
        """
        Get the next scheduled agent.

        :return:
            Next agent description.
        """

        return self._next_agent

    def get_base_reward(self) -> float:
        """
        Get the raw environment reward.

        :return:
            Base reward value.
        """

        return self._base_reward

    def get_aligned_reward(self) -> float:
        """
        Get the alignment-transformed reward.

        :return:
            Per-agent reward value.
        """

        return self._aligned_reward

    def get_base_step_info(self) -> StepInfo:
        """
        Get the underlying single-agent step info.

        :return:
            Base step info object.
        """

        return self._base_step_info

    def get_turn_idx(self) -> int:
        """
        Get the global turn index.

        :return:
            Turn index.
        """

        return self._turn_idx

    def get_requested_action(self) -> OperatorAction:
        """
        Get the action requested by the acting agent.

        :return:
            Requested action.
        """

        return self._requested_action

    def get_applied_action(self) -> OperatorAction:
        """
        Get the action applied after scope projection.

        :return:
            Applied action.
        """

        return self._applied_action


class MultiAgentOperatorEnv:
    """
    Multi-agent wrapper around the base operator environment.

    :param base_env:
        Base single-agent operator environment.
    :param multi_agent_config:
        Multi-agent scheduling configuration.
    """

    __slots__ = ("_base_env", "_multi_agent_config", "_turn_idx", "_active_agent_idx")

    def __init__(self, base_env: VeraGridOperatorEnv, multi_agent_config: MultiAgentConfig) -> None:
        self._base_env: VeraGridOperatorEnv = base_env
        self._multi_agent_config: MultiAgentConfig = multi_agent_config
        self._turn_idx: int = 0
        self._active_agent_idx: int = 0

    def get_base_env(self) -> VeraGridOperatorEnv:
        """
        Get the underlying single-agent environment.

        :return:
            Base environment.
        """

        return self._base_env

    def get_turn_idx(self) -> int:
        """
        Get the current multi-agent turn index.

        :return:
            Turn index.
        """

        return self._turn_idx

    def get_active_agent(self) -> AgentSpec:
        """
        Get the currently scheduled agent.

        :return:
            Active agent description.
        """

        agent_specs: list[AgentSpec] = self._multi_agent_config.get_agent_specs()
        return agent_specs[self._active_agent_idx]

    def get_agent_specs(self) -> list[AgentSpec]:
        """
        Get the ordered agent specification list.

        :return:
            Ordered agent list.
        """

        return self._multi_agent_config.get_agent_specs()

    def reset(self) -> MultiAgentReset:
        """
        Reset the multi-agent environment.

        :return:
            Reset payload with first observation and first active agent.
        """

        # The wrapper reset delegates electrical state reset to the base environment
        # and then resets the turn scheduler so the multi-agent protocol starts cleanly.
        self._turn_idx = 0
        self._active_agent_idx = 0
        observation: ObservationData = self._base_env.reset()
        active_agent: AgentSpec = self.get_active_agent()
        return MultiAgentReset(observation=observation, active_agent=active_agent)

    def step(self, action: OperatorAction) -> tuple[ObservationData, float, bool, bool, MultiAgentStepInfo]:
        """
        Apply one action for the currently scheduled agent.

        :param action:
            Action chosen by the active agent.
        :return:
            Observation, aligned reward, terminated, truncated, and multi-agent step info.
        """

        # The base environment advances the electrical simulation. The wrapper then
        # transforms the raw reward according to agent alignment and rotates the turn.
        acting_agent: AgentSpec = self.get_active_agent()
        scoped_action: OperatorAction = project_action_to_agent_scope(action, acting_agent)
        observation: ObservationData
        base_reward: float
        terminated: bool
        truncated: bool
        base_step_info: StepInfo
        observation, base_reward, terminated, truncated, base_step_info = self._base_env.step(scoped_action)
        aligned_reward: float = align_reward_for_agent(acting_agent, base_reward)
        self._turn_idx += 1
        self._advance_turn()
        next_agent: AgentSpec = self.get_active_agent()
        step_info: MultiAgentStepInfo = MultiAgentStepInfo(
            acting_agent=acting_agent,
            next_agent=next_agent,
            base_reward=base_reward,
            aligned_reward=aligned_reward,
            base_step_info=base_step_info,
            turn_idx=self._turn_idx,
            requested_action=action,
            applied_action=scoped_action,
        )
        return observation, aligned_reward, terminated, truncated, step_info

    def sample_action(self, rng: np.random.Generator | None = None) -> OperatorAction:
        """
        Sample an action from the base environment helper.

        :param rng:
            Optional NumPy random generator.
        :return:
            Sampled operator action.
        """

        return self._base_env.sample_action(rng=rng)

    def _advance_turn(self) -> None:
        """
        Advance the active agent index to the next scheduled agent.

        :return:
            ``None``.
        """

        agent_count: int = len(self._multi_agent_config.get_agent_specs())

        if agent_count > 0:
            self._active_agent_idx = (self._active_agent_idx + 1) % agent_count
        else:
            self._active_agent_idx = 0


def align_reward_for_agent(agent_spec: AgentSpec, base_reward: float) -> float:
    """
    Align the base reward with the given agent objective.

    :param agent_spec:
        Agent description.
    :param base_reward:
        Raw base environment reward.
    :return:
        Agent-specific aligned reward.
    """

    # Positive agents maximize security, negative agents maximize disruption,
    # and neutral agents observe the environment score without sign inversion.
    alignment: AgentAlignment = agent_spec.get_alignment()

    if alignment == AgentAlignment.POSITIVE:
        return base_reward
    else:
        if alignment == AgentAlignment.NEGATIVE:
            return -base_reward
        else:
            return base_reward


def project_action_to_agent_scope(action: OperatorAction, agent_spec: AgentSpec) -> OperatorAction:
    """
    Project an action into the allowed scope of an agent.

    :param action:
        Requested agent action.
    :param agent_spec:
        Acting agent specification.
    :return:
        Scope-compatible action.
    """

    scope: AgentActionScope = agent_spec.get_action_scope()

    if isinstance(action, BranchSwitchAction):
        return project_branch_action_to_scope(action, scope)
    else:
        if isinstance(action, GeneratorRedispatchAction):
            return project_generator_action_to_scope(action, scope)
        else:
            return action


def project_branch_action_to_scope(action: BranchSwitchAction, scope: AgentActionScope) -> BranchSwitchAction:
    """
    Project a branch action into the allowed branch set.

    :param action:
        Requested branch action.
    :param scope:
        Agent scope restriction.
    :return:
        Scope-compatible branch action.
    """

    if scope.has_branch_restriction():
        allowed_indices: list[int] = scope.get_allowed_branch_indices()
        allowed_count: int = len(allowed_indices)
        if allowed_count > 0:
            projected_idx: int = allowed_indices[action.get_branch_idx() % allowed_count]
            return BranchSwitchAction(branch_idx=projected_idx, closed=action.get_closed())
        else:
            return action
    else:
        return action


def project_generator_action_to_scope(
    action: GeneratorRedispatchAction,
    scope: AgentActionScope,
) -> GeneratorRedispatchAction:
    """
    Project a generator action into the allowed generator set.

    :param action:
        Requested generator action.
    :param scope:
        Agent scope restriction.
    :return:
        Scope-compatible generator action.
    """

    if scope.has_generator_restriction():
        allowed_indices: list[int] = scope.get_allowed_generator_indices()
        allowed_count: int = len(allowed_indices)
        if allowed_count > 0:
            projected_idx: int = allowed_indices[action.get_generator_idx() % allowed_count]
            return GeneratorRedispatchAction(
                generator_idx=projected_idx,
                delta_mw=action.get_delta_mw(),
            )
        else:
            return action
    else:
        return action
