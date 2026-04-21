from __future__ import annotations

import numpy as np

from trunk.ai.ai_operator.actions import BranchSwitchAction
from trunk.ai.ai_operator.actions import GeneratorRedispatchAction
from trunk.ai.ai_operator.actions import NoOpAction
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
    :param acting_agents:
        Agents that act concurrently at each global turn.
    """

    __slots__ = ("_observation", "_acting_agents")

    def __init__(self, observation: ObservationData, acting_agents: list[AgentSpec]) -> None:
        self._observation: ObservationData = observation
        self._acting_agents: list[AgentSpec] = acting_agents

    def get_observation(self) -> ObservationData:
        """
        Get the initial observation.

        :return:
            Observation object.
        """

        return self._observation

    def get_acting_agents(self) -> list[AgentSpec]:
        """
        Get the concurrently acting agents.

        :return:
            Acting agent descriptions.
        """

        return self._acting_agents


class AgentActionRecord:
    """
    Requested and scoped action record for one agent in a concurrent turn.

    :param agent_spec:
        Acting agent specification.
    :param requested_action:
        Action produced by the policy.
    :param scoped_action:
        Action after scope projection.
    """

    __slots__ = ("_agent_spec", "_requested_action", "_scoped_action")

    def __init__(
        self,
        agent_spec: AgentSpec,
        requested_action: OperatorAction,
        scoped_action: OperatorAction,
    ) -> None:
        self._agent_spec: AgentSpec = agent_spec
        self._requested_action: OperatorAction = requested_action
        self._scoped_action: OperatorAction = scoped_action

    def get_agent_spec(self) -> AgentSpec:
        """
        Get the acting agent specification.

        :return:
            Agent specification.
        """

        return self._agent_spec

    def get_requested_action(self) -> OperatorAction:
        """
        Get the requested action.

        :return:
            Requested action.
        """

        return self._requested_action

    def get_scoped_action(self) -> OperatorAction:
        """
        Get the scope-projected action.

        :return:
            Scoped action.
        """

        return self._scoped_action


class AgentRewardRecord:
    """
    Per-agent reward record for a concurrent turn.

    :param agent_spec:
        Acting agent specification.
    :param aligned_reward:
        Agent-specific aligned reward.
    """

    __slots__ = ("_agent_spec", "_aligned_reward")

    def __init__(self, agent_spec: AgentSpec, aligned_reward: float) -> None:
        self._agent_spec: AgentSpec = agent_spec
        self._aligned_reward: float = aligned_reward

    def get_agent_spec(self) -> AgentSpec:
        """
        Get the acting agent specification.

        :return:
            Agent specification.
        """

        return self._agent_spec

    def get_aligned_reward(self) -> float:
        """
        Get the aligned reward.

        :return:
            Agent-specific aligned reward.
        """

        return self._aligned_reward


class MultiAgentStepInfo:
    """
    Concurrent multi-agent step metadata bundle.

    :param action_records:
        Per-agent requested and scoped actions.
    :param merged_actions:
        Final merged action batch applied to the base environment.
    :param base_reward:
        Raw reward from the base environment.
    :param reward_records:
        Per-agent aligned reward records.
    :param base_step_info:
        Original single-agent step info.
    :param turn_idx:
        Global concurrent turn index.
    """

    __slots__ = (
        "_action_records",
        "_merged_actions",
        "_base_reward",
        "_reward_records",
        "_base_step_info",
        "_turn_idx",
    )

    def __init__(
        self,
        action_records: list[AgentActionRecord],
        merged_actions: list[OperatorAction],
        base_reward: float,
        reward_records: list[AgentRewardRecord],
        base_step_info: StepInfo,
        turn_idx: int,
    ) -> None:
        self._action_records: list[AgentActionRecord] = action_records
        self._merged_actions: list[OperatorAction] = merged_actions
        self._base_reward: float = base_reward
        self._reward_records: list[AgentRewardRecord] = reward_records
        self._base_step_info: StepInfo = base_step_info
        self._turn_idx: int = turn_idx

    def get_action_records(self) -> list[AgentActionRecord]:
        """
        Get the per-agent action records.

        :return:
            Action records.
        """

        return self._action_records

    def get_merged_actions(self) -> list[OperatorAction]:
        """
        Get the merged action batch.

        :return:
            Merged action list.
        """

        return self._merged_actions

    def get_base_reward(self) -> float:
        """
        Get the raw base environment reward.

        :return:
            Base reward.
        """

        return self._base_reward

    def get_reward_records(self) -> list[AgentRewardRecord]:
        """
        Get the per-agent aligned reward records.

        :return:
            Per-agent reward records.
        """

        return self._reward_records

    def get_base_step_info(self) -> StepInfo:
        """
        Get the underlying base environment step info.

        :return:
            Base step info.
        """

        return self._base_step_info

    def get_turn_idx(self) -> int:
        """
        Get the concurrent turn index.

        :return:
            Turn index.
        """

        return self._turn_idx


class MultiAgentOperatorEnv:
    """
    Concurrent multi-agent wrapper around the base operator environment.

    :param base_env:
        Base single-agent operator environment.
    :param multi_agent_config:
        Multi-agent scheduling configuration.
    """

    __slots__ = ("_base_env", "_multi_agent_config", "_turn_idx")

    def __init__(self, base_env: VeraGridOperatorEnv, multi_agent_config: MultiAgentConfig) -> None:
        self._base_env: VeraGridOperatorEnv = base_env
        self._multi_agent_config: MultiAgentConfig = multi_agent_config
        self._turn_idx: int = 0

    def get_base_env(self) -> VeraGridOperatorEnv:
        """
        Get the underlying single-agent environment.

        :return:
            Base environment.
        """

        return self._base_env

    def get_turn_idx(self) -> int:
        """
        Get the current concurrent turn index.

        :return:
            Turn index.
        """

        return self._turn_idx

    def get_acting_agents(self) -> list[AgentSpec]:
        """
        Get the agents that act concurrently at each turn.

        :return:
            Acting agent list.
        """

        return self._multi_agent_config.get_agent_specs()

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
            Reset payload with observation and acting agents.
        """

        self._turn_idx = 0
        observation: ObservationData = self._base_env.reset()
        return MultiAgentReset(
            observation=observation,
            acting_agents=self.get_acting_agents(),
        )

    def step(self, actions: list[OperatorAction]) -> tuple[ObservationData, float, bool, bool, MultiAgentStepInfo]:
        """
        Apply one concurrent action per agent and solve one PF afterwards.

        :param actions:
            Requested action list, one per agent.
        :return:
            Observation, mean positive aligned reward, terminated, truncated, and step metadata.
        """

        acting_agents: list[AgentSpec] = self.get_acting_agents()
        action_records: list[AgentActionRecord] = build_action_records(acting_agents, actions)
        merged_actions: list[OperatorAction] = merge_scoped_actions(action_records)
        observation: ObservationData
        base_reward: float
        terminated: bool
        truncated: bool
        base_step_info: StepInfo
        observation, base_reward, terminated, truncated, base_step_info = self._base_env.step_action_list(
            merged_actions
        )
        reward_records: list[AgentRewardRecord] = build_reward_records(acting_agents, base_reward)
        self._turn_idx += 1
        step_info: MultiAgentStepInfo = MultiAgentStepInfo(
            action_records=action_records,
            merged_actions=merged_actions,
            base_reward=base_reward,
            reward_records=reward_records,
            base_step_info=base_step_info,
            turn_idx=self._turn_idx,
        )
        display_reward: float = compute_mean_positive_reward(reward_records)
        return observation, display_reward, terminated, truncated, step_info

    def sample_action_batch(self, rng: np.random.Generator | None = None) -> list[OperatorAction]:
        """
        Sample one action per agent.

        :param rng:
            Optional NumPy random generator.
        :return:
            Sampled action batch.
        """

        action_batch: list[OperatorAction] = list()
        agent_specs: list[AgentSpec] = self.get_acting_agents()
        agent_idx: int

        for agent_idx in range(len(agent_specs)):
            action_batch.append(self._base_env.sample_action(rng=rng))

        return action_batch


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

    alignment: AgentAlignment = agent_spec.get_alignment()

    if alignment == AgentAlignment.POSITIVE:
        return base_reward
    else:
        if alignment == AgentAlignment.NEGATIVE:
            return -base_reward
        else:
            return base_reward


def build_action_records(
    acting_agents: list[AgentSpec],
    actions: list[OperatorAction],
) -> list[AgentActionRecord]:
    """
    Build per-agent action records for a concurrent turn.

    :param acting_agents:
        Acting agent list.
    :param actions:
        Requested action list.
    :return:
        Action records.
    """

    action_records: list[AgentActionRecord] = list()
    agent_idx: int

    for agent_idx in range(len(acting_agents)):
        agent_spec: AgentSpec = acting_agents[agent_idx]
        if agent_idx < len(actions):
            requested_action: OperatorAction = actions[agent_idx]
        else:
            requested_action = BranchSwitchAction(branch_idx=0, closed=False)
        scoped_action: OperatorAction = project_action_to_agent_scope(requested_action, agent_spec)
        action_records.append(
            AgentActionRecord(
                agent_spec=agent_spec,
                requested_action=requested_action,
                scoped_action=scoped_action,
            )
        )

    return action_records


def build_reward_records(acting_agents: list[AgentSpec], base_reward: float) -> list[AgentRewardRecord]:
    """
    Build per-agent aligned reward records.

    :param acting_agents:
        Acting agent list.
    :param base_reward:
        Raw base reward.
    :return:
        Per-agent reward records.
    """

    reward_records: list[AgentRewardRecord] = list()
    agent_idx: int

    for agent_idx in range(len(acting_agents)):
        agent_spec: AgentSpec = acting_agents[agent_idx]
        reward_records.append(
            AgentRewardRecord(
                agent_spec=agent_spec,
                aligned_reward=align_reward_for_agent(agent_spec, base_reward),
            )
        )

    return reward_records


def compute_mean_positive_reward(reward_records: list[AgentRewardRecord]) -> float:
    """
    Compute the mean positive-agent aligned reward.

    :param reward_records:
        Per-agent reward records.
    :return:
        Mean positive-agent reward, or mean all-agent reward if there are no positive agents.
    """

    positive_reward_sum: float = 0.0
    positive_count: int = 0
    total_reward_sum: float = 0.0
    record_idx: int

    for record_idx in range(len(reward_records)):
        reward_record: AgentRewardRecord = reward_records[record_idx]
        reward_value: float = reward_record.get_aligned_reward()
        total_reward_sum += reward_value
        if reward_record.get_agent_spec().get_alignment() == AgentAlignment.POSITIVE:
            positive_reward_sum += reward_value
            positive_count += 1
        else:
            record_idx = record_idx

    if positive_count > 0:
        return positive_reward_sum / positive_count
    else:
        if len(reward_records) > 0:
            return total_reward_sum / len(reward_records)
        else:
            return 0.0


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


def merge_scoped_actions(action_records: list[AgentActionRecord]) -> list[OperatorAction]:
    """
    Merge scoped concurrent actions by asset.

    Boolean branch states are combined with OR.
    Continuous generator redispatch values are added.

    :param action_records:
        Per-agent action records.
    :return:
        Merged action list.
    """

    branch_indices: list[int] = list()
    branch_states: list[bool] = list()
    generator_indices: list[int] = list()
    generator_deltas: list[float] = list()
    record_idx: int

    for record_idx in range(len(action_records)):
        scoped_action: OperatorAction = action_records[record_idx].get_scoped_action()
        if isinstance(scoped_action, BranchSwitchAction):
            merge_branch_action(branch_indices, branch_states, scoped_action)
        else:
            if isinstance(scoped_action, GeneratorRedispatchAction):
                merge_generator_action(generator_indices, generator_deltas, scoped_action)
            else:
                if isinstance(scoped_action, NoOpAction):
                    record_idx = record_idx
                else:
                    record_idx = record_idx

    merged_actions: list[OperatorAction] = list()
    branch_idx: int
    for branch_idx in range(len(branch_indices)):
        merged_actions.append(
            BranchSwitchAction(
                branch_idx=branch_indices[branch_idx],
                closed=branch_states[branch_idx],
            )
        )

    generator_idx: int
    for generator_idx in range(len(generator_indices)):
        merged_actions.append(
            GeneratorRedispatchAction(
                generator_idx=generator_indices[generator_idx],
                delta_mw=generator_deltas[generator_idx],
            )
        )

    return merged_actions


def merge_branch_action(
    branch_indices: list[int],
    branch_states: list[bool],
    action: BranchSwitchAction,
) -> None:
    """
    Merge one branch action into the branch accumulator.

    :param branch_indices:
        Accumulated branch indices.
    :param branch_states:
        Accumulated branch target states.
    :param action:
        Branch action to merge.
    :return:
        ``None``.
    """

    target_idx: int = action.get_branch_idx()
    existing_idx: int = find_index_in_int_list(branch_indices, target_idx)

    if existing_idx >= 0:
        branch_states[existing_idx] = branch_states[existing_idx] or action.get_closed()
    else:
        branch_indices.append(target_idx)
        branch_states.append(action.get_closed())


def merge_generator_action(
    generator_indices: list[int],
    generator_deltas: list[float],
    action: GeneratorRedispatchAction,
) -> None:
    """
    Merge one generator action into the generator accumulator.

    :param generator_indices:
        Accumulated generator indices.
    :param generator_deltas:
        Accumulated redispatch values.
    :param action:
        Generator action to merge.
    :return:
        ``None``.
    """

    target_idx: int = action.get_generator_idx()
    existing_idx: int = find_index_in_int_list(generator_indices, target_idx)

    if existing_idx >= 0:
        generator_deltas[existing_idx] += action.get_delta_mw()
    else:
        generator_indices.append(target_idx)
        generator_deltas.append(action.get_delta_mw())


def find_index_in_int_list(values: list[int], target_value: int) -> int:
    """
    Find one integer inside a list.

    :param values:
        Integer list.
    :param target_value:
        Integer to find.
    :return:
        Index or ``-1`` when missing.
    """

    idx: int

    for idx in range(len(values)):
        if values[idx] == target_value:
            return idx
        else:
            idx = idx

    return -1
