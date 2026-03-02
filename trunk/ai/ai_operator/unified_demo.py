from __future__ import annotations

from enum import Enum
from typing import Union

import numpy as np

from trunk.ai.ai_operator.agents import MultiAgentConfig
from trunk.ai.ai_operator.agents import AgentSpec
from trunk.ai.ai_operator.agents import build_frank_and_jeffry_config
from trunk.ai.ai_operator.agents import build_partitioned_defender_attacker_config
from trunk.ai.ai_operator.environment import VeraGridOperatorEnv
from trunk.ai.ai_operator.live_plotting import LivePlotConfig
from trunk.ai.ai_operator.multi_agent_environment import MultiAgentOperatorEnv
from trunk.ai.ai_operator.multi_agent_environment import MultiAgentStepInfo
from trunk.ai.ai_operator.multi_agent_training import MultiAgentEpisodeSummary
from trunk.ai.ai_operator.multi_agent_training import MultiAgentTrainingConfig
from trunk.ai.ai_operator.multi_agent_training import train_multi_agent_policy_system
from trunk.ai.ai_operator.training import EpisodeSummary
from trunk.ai.ai_operator.training import TrainingConfig
from trunk.ai.ai_operator.training import train_operator_policy

import VeraGridEngine.api as gce


class DemoMode(str, Enum):
    """
    Unified demo operating mode.

    :ivar SINGLE_AGENT_TRAINING:
        Train one operator policy against the base environment.
    :ivar DUAL_AGENT_TRAINING:
        Train the default Frank-versus-Jeffry concurrent system.
    :ivar SCOPED_MULTI_AGENT_TRAINING:
        Train N local defenders against N global attackers.
    :ivar SCOPED_MULTI_AGENT_ROLLOUT:
        Run a non-training scoped rollout for behavior inspection.
    """

    SINGLE_AGENT_TRAINING = "single_agent_training"
    DUAL_AGENT_TRAINING = "dual_agent_training"
    SCOPED_MULTI_AGENT_TRAINING = "scoped_multi_agent_training"
    SCOPED_MULTI_AGENT_ROLLOUT = "scoped_multi_agent_rollout"


class UnifiedDemoConfig:
    """
    Parameter bundle for the unified AI operator demo.

    :param grid_path:
        Path to a VeraGrid-readable case file.
    :param demo_mode:
        Selected demo mode.
    :param episodes:
        Number of training episodes for training modes.
    :param max_steps_per_episode:
        Maximum single-agent steps per episode.
    :param max_turns_per_episode:
        Maximum concurrent turns per episode.
    :param rollout_turns:
        Number of turns for rollout-only inspection mode.
    :param learning_rate:
        Optimizer learning rate.
    :param gamma:
        Discount factor.
    :param value_loss_weight:
        Critic loss coefficient.
    :param entropy_weight:
        Entropy regularization coefficient.
    :param hidden_size:
        Policy trunk hidden width.
    :param checkpoint_interval:
        Checkpoint frequency in episodes.
    :param checkpoint_dir:
        Checkpoint directory.
    :param enable_live_plotting:
        Enable live plotting when training.
    :param plot_refresh_interval:
        Plot refresh interval in episodes.
    :param n_defenders:
        Number of scoped defender agents.
    :param n_attackers:
        Number of attacker agents.
    :param seed:
        Random seed for rollout sampling.
    :param attacker_aggression_enabled:
        Enable attacker aggression adaptation.
    :param initial_attacker_aggression:
        Initial attacker aggression scale.
    :param minimum_attacker_aggression:
        Lower aggression clamp.
    :param maximum_attacker_aggression:
        Upper aggression clamp.
    :param attacker_stagnation_threshold:
        Stagnation threshold for aggression increase.
    :param attacker_effective_reward_threshold:
        Excessive-effectiveness threshold for aggression decrease.
    :param attacker_aggression_increase_factor:
        Multiplicative aggression increase factor.
    :param attacker_aggression_decrease_factor:
        Multiplicative aggression decrease factor.
    :param attacker_reward_window:
        Moving reward window used by the aggression scheduler.
    :param attacker_randomness_enabled:
        Enable attacker-side random action injection.
    :param initial_attacker_random_action_probability:
        Initial attacker random action probability.
    :param minimum_attacker_random_action_probability:
        Lower clamp for attacker random action probability.
    :param maximum_attacker_random_action_probability:
        Upper clamp for attacker random action probability.
    :param attacker_randomness_increase_factor:
        Multiplicative increase factor for attacker random action probability.
    :param attacker_randomness_decrease_factor:
        Multiplicative decrease factor for attacker random action probability.
    """

    __slots__ = (
        "_grid_path",
        "_demo_mode",
        "_episodes",
        "_max_steps_per_episode",
        "_max_turns_per_episode",
        "_rollout_turns",
        "_learning_rate",
        "_gamma",
        "_value_loss_weight",
        "_entropy_weight",
        "_hidden_size",
        "_checkpoint_interval",
        "_checkpoint_dir",
        "_enable_live_plotting",
        "_plot_refresh_interval",
        "_n_defenders",
        "_n_attackers",
        "_seed",
        "_attacker_aggression_enabled",
        "_initial_attacker_aggression",
        "_minimum_attacker_aggression",
        "_maximum_attacker_aggression",
        "_attacker_stagnation_threshold",
        "_attacker_effective_reward_threshold",
        "_attacker_aggression_increase_factor",
        "_attacker_aggression_decrease_factor",
        "_attacker_reward_window",
        "_attacker_randomness_enabled",
        "_initial_attacker_random_action_probability",
        "_minimum_attacker_random_action_probability",
        "_maximum_attacker_random_action_probability",
        "_attacker_randomness_increase_factor",
        "_attacker_randomness_decrease_factor",
    )

    def __init__(
        self,
        grid_path: str = "files/IEEE 9 Bus.veragrid",
        demo_mode: DemoMode = DemoMode.SCOPED_MULTI_AGENT_TRAINING,
        episodes: int = 200,
        max_steps_per_episode: int = 64,
        max_turns_per_episode: int = 32,
        rollout_turns: int = 20,
        learning_rate: float = 1.0e-4,
        gamma: float = 0.99,
        value_loss_weight: float = 0.5,
        entropy_weight: float = 0.01,
        hidden_size: int = 256,
        checkpoint_interval: int = 25,
        checkpoint_dir: str = "trunk/ai/ai_operator/checkpoints_unified_demo",
        enable_live_plotting: bool = True,
        plot_refresh_interval: int = 1,
        n_defenders: int = 3,
        n_attackers: int = 2,
        seed: int = 7,
        attacker_aggression_enabled: bool = True,
        initial_attacker_aggression: float = 1.0,
        minimum_attacker_aggression: float = 0.25,
        maximum_attacker_aggression: float = 3.0,
        attacker_stagnation_threshold: float = 0.05,
        attacker_effective_reward_threshold: float = 10.0,
        attacker_aggression_increase_factor: float = 1.15,
        attacker_aggression_decrease_factor: float = 0.90,
        attacker_reward_window: int = 5,
        attacker_randomness_enabled: bool = True,
        initial_attacker_random_action_probability: float = 0.05,
        minimum_attacker_random_action_probability: float = 0.0,
        maximum_attacker_random_action_probability: float = 0.35,
        attacker_randomness_increase_factor: float = 1.20,
        attacker_randomness_decrease_factor: float = 0.90,
    ) -> None:
        self._grid_path: str = grid_path
        self._demo_mode: DemoMode = demo_mode
        self._episodes: int = episodes
        self._max_steps_per_episode: int = max_steps_per_episode
        self._max_turns_per_episode: int = max_turns_per_episode
        self._rollout_turns: int = rollout_turns
        self._learning_rate: float = learning_rate
        self._gamma: float = gamma
        self._value_loss_weight: float = value_loss_weight
        self._entropy_weight: float = entropy_weight
        self._hidden_size: int = hidden_size
        self._checkpoint_interval: int = checkpoint_interval
        self._checkpoint_dir: str = checkpoint_dir
        self._enable_live_plotting: bool = enable_live_plotting
        self._plot_refresh_interval: int = plot_refresh_interval
        self._n_defenders: int = n_defenders
        self._n_attackers: int = n_attackers
        self._seed: int = seed
        self._attacker_aggression_enabled: bool = attacker_aggression_enabled
        self._initial_attacker_aggression: float = initial_attacker_aggression
        self._minimum_attacker_aggression: float = minimum_attacker_aggression
        self._maximum_attacker_aggression: float = maximum_attacker_aggression
        self._attacker_stagnation_threshold: float = attacker_stagnation_threshold
        self._attacker_effective_reward_threshold: float = attacker_effective_reward_threshold
        self._attacker_aggression_increase_factor: float = attacker_aggression_increase_factor
        self._attacker_aggression_decrease_factor: float = attacker_aggression_decrease_factor
        self._attacker_reward_window: int = attacker_reward_window
        self._attacker_randomness_enabled: bool = attacker_randomness_enabled
        self._initial_attacker_random_action_probability: float = initial_attacker_random_action_probability
        self._minimum_attacker_random_action_probability: float = minimum_attacker_random_action_probability
        self._maximum_attacker_random_action_probability: float = maximum_attacker_random_action_probability
        self._attacker_randomness_increase_factor: float = attacker_randomness_increase_factor
        self._attacker_randomness_decrease_factor: float = attacker_randomness_decrease_factor

    def get_grid_path(self) -> str:
        """
        Get the grid path.

        :return:
            Grid path.
        """

        return self._grid_path

    def get_demo_mode(self) -> DemoMode:
        """
        Get the selected demo mode.

        :return:
            Demo mode.
        """

        return self._demo_mode

    def get_episodes(self) -> int:
        """
        Get the episode count.

        :return:
            Episode count.
        """

        return self._episodes

    def get_max_steps_per_episode(self) -> int:
        """
        Get the single-agent step limit.

        :return:
            Single-agent step limit.
        """

        return self._max_steps_per_episode

    def get_max_turns_per_episode(self) -> int:
        """
        Get the concurrent turn limit.

        :return:
            Concurrent turn limit.
        """

        return self._max_turns_per_episode

    def get_rollout_turns(self) -> int:
        """
        Get the rollout turn count.

        :return:
            Rollout turn count.
        """

        return self._rollout_turns

    def get_learning_rate(self) -> float:
        """
        Get the learning rate.

        :return:
            Learning rate.
        """

        return self._learning_rate

    def get_gamma(self) -> float:
        """
        Get the discount factor.

        :return:
            Discount factor.
        """

        return self._gamma

    def get_value_loss_weight(self) -> float:
        """
        Get the value loss coefficient.

        :return:
            Value loss coefficient.
        """

        return self._value_loss_weight

    def get_entropy_weight(self) -> float:
        """
        Get the entropy coefficient.

        :return:
            Entropy coefficient.
        """

        return self._entropy_weight

    def get_hidden_size(self) -> int:
        """
        Get the hidden width.

        :return:
            Hidden width.
        """

        return self._hidden_size

    def get_checkpoint_interval(self) -> int:
        """
        Get the checkpoint interval.

        :return:
            Checkpoint interval.
        """

        return self._checkpoint_interval

    def get_checkpoint_dir(self) -> str:
        """
        Get the checkpoint directory.

        :return:
            Checkpoint directory.
        """

        return self._checkpoint_dir

    def get_enable_live_plotting(self) -> bool:
        """
        Get the live plotting flag.

        :return:
            ``True`` when plotting is enabled.
        """

        return self._enable_live_plotting

    def get_plot_refresh_interval(self) -> int:
        """
        Get the plot refresh interval.

        :return:
            Plot refresh interval.
        """

        return self._plot_refresh_interval

    def get_n_defenders(self) -> int:
        """
        Get the number of defender agents.

        :return:
            Number of defenders.
        """

        return self._n_defenders

    def get_n_attackers(self) -> int:
        """
        Get the number of attacker agents.

        :return:
            Number of attackers.
        """

        return self._n_attackers

    def get_seed(self) -> int:
        """
        Get the rollout seed.

        :return:
            Rollout seed.
        """

        return self._seed

    def get_attacker_aggression_enabled(self) -> bool:
        """
        Get the attacker aggression scheduler flag.

        :return:
            ``True`` when adaptive aggression is enabled.
        """

        return self._attacker_aggression_enabled

    def get_initial_attacker_aggression(self) -> float:
        """
        Get the initial attacker aggression.

        :return:
            Initial aggression scale.
        """

        return self._initial_attacker_aggression

    def get_minimum_attacker_aggression(self) -> float:
        """
        Get the minimum attacker aggression.

        :return:
            Minimum aggression scale.
        """

        return self._minimum_attacker_aggression

    def get_maximum_attacker_aggression(self) -> float:
        """
        Get the maximum attacker aggression.

        :return:
            Maximum aggression scale.
        """

        return self._maximum_attacker_aggression

    def get_attacker_stagnation_threshold(self) -> float:
        """
        Get the stagnation threshold.

        :return:
            Stagnation threshold.
        """

        return self._attacker_stagnation_threshold

    def get_attacker_effective_reward_threshold(self) -> float:
        """
        Get the excessive-effectiveness threshold.

        :return:
            Excessive-effectiveness threshold.
        """

        return self._attacker_effective_reward_threshold

    def get_attacker_aggression_increase_factor(self) -> float:
        """
        Get the aggression increase factor.

        :return:
            Aggression increase factor.
        """

        return self._attacker_aggression_increase_factor

    def get_attacker_aggression_decrease_factor(self) -> float:
        """
        Get the aggression decrease factor.

        :return:
            Aggression decrease factor.
        """

        return self._attacker_aggression_decrease_factor

    def get_attacker_reward_window(self) -> int:
        """
        Get the attacker reward window.

        :return:
            Reward window size.
        """

        return self._attacker_reward_window

    def get_attacker_randomness_enabled(self) -> bool:
        """
        Get the attacker randomness flag.

        :return:
            ``True`` when attacker random action injection is enabled.
        """

        return self._attacker_randomness_enabled

    def get_initial_attacker_random_action_probability(self) -> float:
        """
        Get the initial attacker random action probability.

        :return:
            Initial random action probability.
        """

        return self._initial_attacker_random_action_probability

    def get_minimum_attacker_random_action_probability(self) -> float:
        """
        Get the minimum attacker random action probability.

        :return:
            Minimum random action probability.
        """

        return self._minimum_attacker_random_action_probability

    def get_maximum_attacker_random_action_probability(self) -> float:
        """
        Get the maximum attacker random action probability.

        :return:
            Maximum random action probability.
        """

        return self._maximum_attacker_random_action_probability

    def get_attacker_randomness_increase_factor(self) -> float:
        """
        Get the attacker randomness increase factor.

        :return:
            Randomness increase factor.
        """

        return self._attacker_randomness_increase_factor

    def get_attacker_randomness_decrease_factor(self) -> float:
        """
        Get the attacker randomness decrease factor.

        :return:
            Randomness decrease factor.
        """

        return self._attacker_randomness_decrease_factor


DemoResult = Union[list[EpisodeSummary], list[MultiAgentEpisodeSummary], list[object]]


def run_unified_demo(config: UnifiedDemoConfig | None = None) -> DemoResult:
    """
    Run the selected experiment mode from one explicit configuration object.

    :param config:
        Optional unified demo configuration.
    :return:
        Training summaries or rollout step records, depending on the selected mode.
    """

    config_obj: UnifiedDemoConfig = UnifiedDemoConfig() if config is None else config
    print_unified_demo_header(config_obj)
    demo_mode: DemoMode = config_obj.get_demo_mode()

    if demo_mode == DemoMode.SINGLE_AGENT_TRAINING:
        return run_single_agent_training_demo(config_obj)
    else:
        if demo_mode == DemoMode.DUAL_AGENT_TRAINING:
            return run_dual_agent_training_demo(config_obj)
        else:
            if demo_mode == DemoMode.SCOPED_MULTI_AGENT_TRAINING:
                return run_scoped_multi_agent_training_demo(config_obj)
            else:
                if demo_mode == DemoMode.SCOPED_MULTI_AGENT_ROLLOUT:
                    return run_scoped_rollout_demo(config_obj)
                else:
                    return list()


def print_unified_demo_header(config: UnifiedDemoConfig) -> None:
    """
    Print the selected experiment parameters.

    :param config:
        Unified demo configuration.
    :return:
        ``None``.
    """

    print("AI operator unified demo")
    print(f"mode={config.get_demo_mode().value}")
    print(f"grid_path={config.get_grid_path()}")
    print(f"episodes={config.get_episodes()} max_steps={config.get_max_steps_per_episode()}")
    print(f"max_turns={config.get_max_turns_per_episode()} rollout_turns={config.get_rollout_turns()}")
    print(f"n_defenders={config.get_n_defenders()} n_attackers={config.get_n_attackers()}")
    print(
        "attacker_aggression="
        f"{config.get_attacker_aggression_enabled()} "
        f"range=[{config.get_minimum_attacker_aggression():.3f}, "
        f"{config.get_maximum_attacker_aggression():.3f}] "
        f"initial={config.get_initial_attacker_aggression():.3f}"
    )
    print(
        "attacker_randomness="
        f"{config.get_attacker_randomness_enabled()} "
        f"range=[{config.get_minimum_attacker_random_action_probability():.3f}, "
        f"{config.get_maximum_attacker_random_action_probability():.3f}] "
        f"initial={config.get_initial_attacker_random_action_probability():.3f}"
    )


def run_single_agent_training_demo(config: UnifiedDemoConfig) -> list[EpisodeSummary]:
    """
    Run the single-agent training mode.

    :param config:
        Unified demo configuration.
    :return:
        Single-agent training summaries.
    """

    training_config: TrainingConfig = TrainingConfig(
        episodes=config.get_episodes(),
        max_steps_per_episode=config.get_max_steps_per_episode(),
        learning_rate=config.get_learning_rate(),
        gamma=config.get_gamma(),
        value_loss_weight=config.get_value_loss_weight(),
        entropy_weight=config.get_entropy_weight(),
        hidden_size=config.get_hidden_size(),
        checkpoint_interval=config.get_checkpoint_interval(),
        checkpoint_dir=config.get_checkpoint_dir(),
    )
    live_plot_config: LivePlotConfig = LivePlotConfig(
        enabled=config.get_enable_live_plotting(),
        refresh_interval=config.get_plot_refresh_interval(),
        window_title="AI Operator Unified Demo - Single Agent",
    )
    history: list[EpisodeSummary]
    _, history = train_operator_policy(
        grid_path=config.get_grid_path(),
        training_config=training_config,
        live_plot_config=live_plot_config,
    )
    return history


def run_dual_agent_training_demo(config: UnifiedDemoConfig) -> list[MultiAgentEpisodeSummary]:
    """
    Run the default Frank-versus-Jeffry training mode.

    :param config:
        Unified demo configuration.
    :return:
        Multi-agent training summaries.
    """

    multi_agent_config: MultiAgentConfig = build_frank_and_jeffry_config()
    return run_multi_agent_training_demo_with_config(config, multi_agent_config)


def run_scoped_multi_agent_training_demo(config: UnifiedDemoConfig) -> list[MultiAgentEpisodeSummary]:
    """
    Run the scoped defender-versus-attacker training mode.

    :param config:
        Unified demo configuration.
    :return:
        Multi-agent training summaries.
    """

    multi_agent_config: MultiAgentConfig = build_scoped_multi_agent_config(config)
    return run_multi_agent_training_demo_with_config(config, multi_agent_config)


def run_multi_agent_training_demo_with_config(
    config: UnifiedDemoConfig,
    multi_agent_config: MultiAgentConfig,
) -> list[MultiAgentEpisodeSummary]:
    """
    Run one multi-agent training mode with a prebuilt agent configuration.

    :param config:
        Unified demo configuration.
    :param multi_agent_config:
        Agent configuration to train.
    :return:
        Multi-agent episode summaries.
    """

    training_config: MultiAgentTrainingConfig = MultiAgentTrainingConfig(
        episodes=config.get_episodes(),
        max_turns_per_episode=config.get_max_turns_per_episode(),
        learning_rate=config.get_learning_rate(),
        gamma=config.get_gamma(),
        value_loss_weight=config.get_value_loss_weight(),
        entropy_weight=config.get_entropy_weight(),
        hidden_size=config.get_hidden_size(),
        checkpoint_interval=config.get_checkpoint_interval(),
        checkpoint_dir=config.get_checkpoint_dir(),
        attacker_aggression_enabled=config.get_attacker_aggression_enabled(),
        initial_attacker_aggression=config.get_initial_attacker_aggression(),
        minimum_attacker_aggression=config.get_minimum_attacker_aggression(),
        maximum_attacker_aggression=config.get_maximum_attacker_aggression(),
        attacker_stagnation_threshold=config.get_attacker_stagnation_threshold(),
        attacker_effective_reward_threshold=config.get_attacker_effective_reward_threshold(),
        attacker_aggression_increase_factor=config.get_attacker_aggression_increase_factor(),
        attacker_aggression_decrease_factor=config.get_attacker_aggression_decrease_factor(),
        attacker_reward_window=config.get_attacker_reward_window(),
        attacker_randomness_enabled=config.get_attacker_randomness_enabled(),
        initial_attacker_random_action_probability=config.get_initial_attacker_random_action_probability(),
        minimum_attacker_random_action_probability=config.get_minimum_attacker_random_action_probability(),
        maximum_attacker_random_action_probability=config.get_maximum_attacker_random_action_probability(),
        attacker_randomness_increase_factor=config.get_attacker_randomness_increase_factor(),
        attacker_randomness_decrease_factor=config.get_attacker_randomness_decrease_factor(),
    )
    live_plot_config: LivePlotConfig = LivePlotConfig(
        enabled=config.get_enable_live_plotting(),
        refresh_interval=config.get_plot_refresh_interval(),
        window_title="AI Operator Unified Demo - Multi Agent",
    )
    history: list[MultiAgentEpisodeSummary]
    _, history = train_multi_agent_policy_system(
        grid_path=config.get_grid_path(),
        multi_agent_config=multi_agent_config,
        training_config=training_config,
        live_plot_config=live_plot_config,
    )
    return history


def build_scoped_multi_agent_config(config: UnifiedDemoConfig) -> MultiAgentConfig:
    """
    Build the scoped defender-versus-attacker configuration.

    :param config:
        Unified demo configuration.
    :return:
        Scoped multi-agent configuration.
    """

    grid: object = gce.open_file(config.get_grid_path())
    base_env: VeraGridOperatorEnv = VeraGridOperatorEnv(grid=grid)
    branch_count: int = base_env.get_branch_count()
    generator_count: int = base_env.get_generator_count()
    multi_agent_config: MultiAgentConfig = build_partitioned_defender_attacker_config(
        n_defenders=config.get_n_defenders(),
        n_attackers=config.get_n_attackers(),
        branch_count=branch_count,
        generator_count=generator_count,
    )
    return multi_agent_config


def run_scoped_rollout_demo(config: UnifiedDemoConfig) -> list[object]:
    """
    Run the scoped rollout-only inspection mode.

    :param config:
        Unified demo configuration.
    :return:
        Rollout step records as an opaque list.
    """

    # This rollout mode mirrors the training agent partitioning logic but keeps the
    # system in inspection mode so a developer can understand the concurrent action
    # merging behavior before running optimization.
    multi_agent_config: MultiAgentConfig = build_scoped_multi_agent_config(config)
    grid: object = gce.open_file(config.get_grid_path())
    base_env: VeraGridOperatorEnv = VeraGridOperatorEnv(grid=grid)
    multi_agent_env: MultiAgentOperatorEnv = MultiAgentOperatorEnv(
        base_env=base_env,
        multi_agent_config=multi_agent_config,
    )
    rng: np.random.Generator = np.random.default_rng(config.get_seed())
    multi_agent_env.reset()
    history: list[object] = list()
    turn_idx: int

    print("Scoped rollout demo setup")
    print(
        f"defenders={config.get_n_defenders()} "
        f"attackers={config.get_n_attackers()} "
        f"branches={base_env.get_branch_count()} "
        f"generators={base_env.get_generator_count()}"
    )
    print_agent_scope_summary(multi_agent_config)

    for turn_idx in range(config.get_rollout_turns()):
        sampled_actions = multi_agent_env.sample_action_batch(rng=rng)
        reward: float
        terminated: bool
        truncated: bool
        step_info: MultiAgentStepInfo
        _, reward, terminated, truncated, step_info = multi_agent_env.step(sampled_actions)
        history.append(step_info)
        print(
            f"turn={step_info.get_turn_idx()} "
            f"reward_mean_positive={reward:.3f} "
            f"terminated={terminated} "
            f"truncated={truncated}"
        )
        print_turn_action_summary(step_info)

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

    agent_specs: list[AgentSpec] = multi_agent_config.get_agent_specs()
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


def print_turn_action_summary(step_info: MultiAgentStepInfo) -> None:
    """
    Print a concurrent turn summary.

    :param step_info:
        Multi-agent step info.
    :return:
        ``None``.
    """

    action_records = step_info.get_action_records()
    reward_records = step_info.get_reward_records()
    record_idx: int

    for record_idx in range(len(action_records)):
        action_record = action_records[record_idx]
        reward_record = reward_records[record_idx]
        print(
            f"agent={action_record.get_agent_spec().get_display_name()} "
            f"requested={action_record.get_requested_action()} "
            f"scoped={action_record.get_scoped_action()} "
            f"reward={reward_record.get_aligned_reward():.3f}"
        )

    print(f"merged_actions={step_info.get_merged_actions()}")


if __name__ == "__main__":
    # Edit this block directly when exploring behavior. The goal of this file is
    # to keep all important experiment controls in one visible place.
    demo_config: UnifiedDemoConfig = UnifiedDemoConfig(
        grid_path="files/IEEE 9 Bus.veragrid",
        demo_mode=DemoMode.SCOPED_MULTI_AGENT_TRAINING,
        episodes=2000,
        max_turns_per_episode=32,
        n_defenders=3,
        n_attackers=2,
        enable_live_plotting=True,
        attacker_aggression_enabled=True,
        initial_attacker_aggression=1.0,
        minimum_attacker_aggression=0.25,
        maximum_attacker_aggression=3.0,
        attacker_stagnation_threshold=0.05,
        attacker_effective_reward_threshold=10.0,
        attacker_randomness_enabled=True,
        initial_attacker_random_action_probability=0.05,
        maximum_attacker_random_action_probability=0.35,
    )
    run_unified_demo(demo_config)
