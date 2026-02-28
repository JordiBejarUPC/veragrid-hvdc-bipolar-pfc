from __future__ import annotations

import numpy as np

import VeraGridEngine.api as gce

from trunk.ai.ai_operator.agents import MultiAgentConfig
from trunk.ai.ai_operator.agents import build_partitioned_defender_attacker_config
from trunk.ai.ai_operator.environment import VeraGridOperatorEnv
from trunk.ai.ai_operator.multi_agent_environment import MultiAgentOperatorEnv
from trunk.ai.ai_operator.multi_agent_environment import MultiAgentStepInfo
from trunk.ai.ai_operator.observations import ObservationData


def run_scoped_multi_agent_demo(
    grid_path: str,
    n_defenders: int,
    n_attackers: int,
    turns: int = 200,
    seed: int = 7,
) -> list[MultiAgentStepInfo]:
    """
    Run a scoped multi-agent demo with local defenders and global attackers.

    :param grid_path:
        Path to a VeraGrid-readable grid file.
    :param n_defenders:
        Number of positive agents restricted to grid portions.
    :param n_attackers:
        Number of negative agents allowed to act anywhere.
    :param turns:
        Maximum number of scheduled turns.
    :param seed:
        Random seed for baseline sampling.
    :return:
        Multi-agent step info records.
    """

    # The demo first opens the grid so it can compute the number of controllable assets.
    # Those counts are then used to partition the grid across defender agents.
    grid: object = gce.open_file(grid_path)
    base_env: VeraGridOperatorEnv = VeraGridOperatorEnv(grid=grid)
    branch_count: int = base_env.get_branch_count()
    generator_count: int = base_env.get_generator_count()
    multi_agent_config: MultiAgentConfig = build_partitioned_defender_attacker_config(
        n_defenders=n_defenders,
        n_attackers=n_attackers,
        branch_count=branch_count,
        generator_count=generator_count,
    )
    multi_agent_env: MultiAgentOperatorEnv = MultiAgentOperatorEnv(
        base_env=base_env,
        multi_agent_config=multi_agent_config,
    )
    rng: np.random.Generator = np.random.default_rng(seed)

    reset_payload = multi_agent_env.reset()
    observation: ObservationData = reset_payload.get_observation()
    history: list[MultiAgentStepInfo] = list()
    turn_idx: int

    print("Scoped multi-agent demo setup")
    print(f"defenders={n_defenders} attackers={n_attackers} branches={branch_count} generators={generator_count}")
    print_agent_scope_summary(multi_agent_config)

    for turn_idx in range(turns):
        acting_agent = multi_agent_env.get_active_agent()
        sampled_action = multi_agent_env.sample_action(rng=rng)
        next_observation: ObservationData
        reward: float
        terminated: bool
        truncated: bool
        step_info: MultiAgentStepInfo
        next_observation, reward, terminated, truncated, step_info = multi_agent_env.step(sampled_action)
        history.append(step_info)

        print(
            f"turn={step_info.get_turn_idx()} "
            f"agent={acting_agent.get_display_name()} "
            f"requested={step_info.get_requested_action()} "
            f"applied={step_info.get_applied_action()} "
            f"reward={reward:.3f} "
            f"terminated={terminated} "
            f"truncated={truncated}"
        )
        observation = next_observation

        if terminated or truncated:
            break
        else:
            turn_idx = turn_idx

    return history


def print_agent_scope_summary(multi_agent_config: MultiAgentConfig) -> None:
    """
    Print the scoped access summary for all agents.

    :param multi_agent_config:
        Multi-agent configuration.
    :return:
        ``None``.
    """

    agent_specs = multi_agent_config.get_agent_specs()
    agent_idx: int

    for agent_idx in range(len(agent_specs)):
        agent_spec = agent_specs[agent_idx]
        scope = agent_spec.get_action_scope()
        branch_scope = scope.get_allowed_branch_indices()
        generator_scope = scope.get_allowed_generator_indices()
        branch_scope_label: str = "ALL" if len(branch_scope) == 0 else str(branch_scope)
        generator_scope_label: str = "ALL" if len(generator_scope) == 0 else str(generator_scope)
        print(
            f"agent={agent_spec.get_display_name()} "
            f"alignment={agent_spec.get_alignment().value} "
            f"policy_group={agent_spec.get_policy_group()} "
            f"branches={branch_scope_label} "
            f"generators={generator_scope_label}"
        )


if __name__ == "__main__":
    run_scoped_multi_agent_demo(
        grid_path="files/IEEE 9 Bus.veragrid",
        n_defenders=3,
        n_attackers=2,
        turns=2000,
        seed=7,
    )
