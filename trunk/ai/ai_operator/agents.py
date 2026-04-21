from __future__ import annotations

from enum import Enum


class AgentAlignment(str, Enum):
    """
    Agent alignment enumeration.

    :ivar POSITIVE:
        Agent tries to improve the grid security objective.
    :ivar NEGATIVE:
        Agent tries to worsen the grid security objective.
    :ivar NEUTRAL:
        Agent reward follows the raw environment score.
    """

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class AgentSpec:
    """
    Agent description for multi-agent scheduling.

    :param agent_id:
        Stable agent identifier.
    :param display_name:
        Human-readable agent name.
    :param alignment:
        Alignment with respect to the base grid reward.
    :param policy_group:
        Logical policy grouping used later for shared or separate policies.
    :param action_scope:
        Asset scope restriction for the agent actions.
    """

    __slots__ = ("_agent_id", "_display_name", "_alignment", "_policy_group", "_action_scope")

    def __init__(
        self,
        agent_id: str,
        display_name: str,
        alignment: AgentAlignment,
        policy_group: str,
        action_scope: "AgentActionScope | None" = None,
    ) -> None:
        self._agent_id: str = agent_id
        self._display_name: str = display_name
        self._alignment: AgentAlignment = alignment
        self._policy_group: str = policy_group
        self._action_scope: AgentActionScope = AgentActionScope() if action_scope is None else action_scope

    def get_agent_id(self) -> str:
        """
        Get the stable agent identifier.

        :return:
            Agent identifier.
        """

        return self._agent_id

    def get_display_name(self) -> str:
        """
        Get the display name.

        :return:
            Human-readable agent name.
        """

        return self._display_name

    def get_alignment(self) -> AgentAlignment:
        """
        Get the reward alignment.

        :return:
            Agent alignment enumeration.
        """

        return self._alignment

    def get_policy_group(self) -> str:
        """
        Get the logical policy group.

        :return:
            Policy group name.
        """

        return self._policy_group

    def get_action_scope(self) -> "AgentActionScope":
        """
        Get the action scope restriction.

        :return:
            Action scope object.
        """

        return self._action_scope


class AgentActionScope:
    """
    Allowed controllable asset scope for one agent.

    :param allowed_branch_indices:
        Allowed branch indices. An empty list means unrestricted branch access.
    :param allowed_generator_indices:
        Allowed generator indices. An empty list means unrestricted generator access.
    """

    __slots__ = ("_allowed_branch_indices", "_allowed_generator_indices")

    def __init__(
        self,
        allowed_branch_indices: list[int] | None = None,
        allowed_generator_indices: list[int] | None = None,
    ) -> None:
        branch_indices: list[int] = list() if allowed_branch_indices is None else allowed_branch_indices
        generator_indices: list[int] = list() if allowed_generator_indices is None else allowed_generator_indices
        self._allowed_branch_indices: list[int] = branch_indices
        self._allowed_generator_indices: list[int] = generator_indices

    def get_allowed_branch_indices(self) -> list[int]:
        """
        Get the allowed branch indices.

        :return:
            Allowed branch indices.
        """

        return self._allowed_branch_indices

    def get_allowed_generator_indices(self) -> list[int]:
        """
        Get the allowed generator indices.

        :return:
            Allowed generator indices.
        """

        return self._allowed_generator_indices

    def has_branch_restriction(self) -> bool:
        """
        Check whether branch access is restricted.

        :return:
            ``True`` when branch actions are restricted.
        """

        return len(self._allowed_branch_indices) > 0

    def has_generator_restriction(self) -> bool:
        """
        Check whether generator access is restricted.

        :return:
            ``True`` when generator actions are restricted.
        """

        return len(self._allowed_generator_indices) > 0


class MultiAgentConfig:
    """
    Multi-agent environment configuration.

    :param agent_specs:
        Ordered list of agent descriptions that defines the turn cycle.
    :param cycle_length:
        Number of agent actions in one cycle. When zero, the list length is used.
    """

    __slots__ = ("_agent_specs", "_cycle_length")

    def __init__(self, agent_specs: list[AgentSpec], cycle_length: int = 0) -> None:
        cycle_length_value: int = len(agent_specs) if cycle_length == 0 else cycle_length
        self._agent_specs: list[AgentSpec] = agent_specs
        self._cycle_length: int = cycle_length_value

    def get_agent_specs(self) -> list[AgentSpec]:
        """
        Get the ordered agent specification list.

        :return:
            Ordered agent specifications.
        """

        return self._agent_specs

    def get_cycle_length(self) -> int:
        """
        Get the number of turns in one cycle.

        :return:
            Cycle length.
        """

        return self._cycle_length


def build_frank_and_jeffry_config() -> MultiAgentConfig:
    """
    Build the initial two-agent configuration for Frank and Jeffry.

    :return:
        Multi-agent configuration with one positive and one negative agent.
    """

    # Frank is the corrective operator and Jeffry is the malicious perturbing agent.
    # The turn order is explicit here so later experiments can extend it to N agents.
    agent_specs: list[AgentSpec] = list()
    agent_specs.append(
        AgentSpec(
            agent_id="frank",
            display_name="Frank",
            alignment=AgentAlignment.POSITIVE,
            policy_group="defender",
            action_scope=AgentActionScope(),
        )
    )
    agent_specs.append(
        AgentSpec(
            agent_id="jeffry",
            display_name="Jeffry",
            alignment=AgentAlignment.NEGATIVE,
            policy_group="attacker",
            action_scope=AgentActionScope(),
        )
    )
    return MultiAgentConfig(agent_specs=agent_specs)


def build_partitioned_defender_attacker_config(
    n_defenders: int,
    n_attackers: int,
    branch_count: int,
    generator_count: int,
) -> MultiAgentConfig:
    """
    Build a scoped multi-agent configuration with local defenders and global attackers.

    :param n_defenders:
        Number of positive agents, each limited to a portion of the grid.
    :param n_attackers:
        Number of negative agents with unrestricted access.
    :param branch_count:
        Number of controllable branches.
    :param generator_count:
        Number of controllable generators.
    :return:
        Multi-agent configuration.
    """

    # Defender agents receive disjoint contiguous partitions of branch and generator
    # indices so each one is responsible for one portion of the controllable grid.
    agent_specs: list[AgentSpec] = list()
    defender_idx: int

    for defender_idx in range(n_defenders):
        branch_partition: list[int] = compute_partition_indices(branch_count, n_defenders, defender_idx)
        generator_partition: list[int] = compute_partition_indices(generator_count, n_defenders, defender_idx)
        agent_specs.append(
            AgentSpec(
                agent_id=f"frank_{defender_idx + 1}",
                display_name=f"Frank {defender_idx + 1}",
                alignment=AgentAlignment.POSITIVE,
                policy_group=f"defender_{defender_idx + 1}",
                action_scope=AgentActionScope(
                    allowed_branch_indices=branch_partition,
                    allowed_generator_indices=generator_partition,
                ),
            )
        )

    attacker_idx: int
    unrestricted_scope: AgentActionScope = AgentActionScope()
    for attacker_idx in range(n_attackers):
        agent_specs.append(
            AgentSpec(
                agent_id=f"jeffry_{attacker_idx + 1}",
                display_name=f"Jeffry {attacker_idx + 1}",
                alignment=AgentAlignment.NEGATIVE,
                policy_group=f"attacker_{attacker_idx + 1}",
                action_scope=unrestricted_scope,
            )
        )

    return MultiAgentConfig(agent_specs=agent_specs)


def compute_partition_indices(asset_count: int, partition_count: int, partition_idx: int) -> list[int]:
    """
    Compute one contiguous asset partition.

    :param asset_count:
        Total number of assets.
    :param partition_count:
        Number of partitions.
    :param partition_idx:
        Zero-based partition index.
    :return:
        Asset indices assigned to the partition.
    """

    assigned_indices: list[int] = list()

    if partition_count > 0:
        start_idx: int = (asset_count * partition_idx) // partition_count
        end_idx: int = (asset_count * (partition_idx + 1)) // partition_count
        asset_idx: int
        for asset_idx in range(start_idx, end_idx):
            assigned_indices.append(asset_idx)
    else:
        partition_idx = partition_idx

    return assigned_indices
