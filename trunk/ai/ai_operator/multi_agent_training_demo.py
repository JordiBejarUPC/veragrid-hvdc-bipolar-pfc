from __future__ import annotations

from trunk.ai.ai_operator.agents import MultiAgentConfig
from trunk.ai.ai_operator.agents import build_frank_and_jeffry_config
from trunk.ai.ai_operator.live_plotting import LivePlotConfig
from trunk.ai.ai_operator.multi_agent_training import MultiAgentEpisodeSummary
from trunk.ai.ai_operator.multi_agent_training import MultiAgentTrainingConfig
from trunk.ai.ai_operator.multi_agent_training import train_multi_agent_policy_system


def run_multi_agent_training_demo(
    grid_path: str,
    multi_agent_config: MultiAgentConfig | None = None,
    episodes: int = 20,
    max_turns_per_episode: int = 32,
    learning_rate: float = 1.0e-4,
    gamma: float = 0.99,
    value_loss_weight: float = 0.5,
    entropy_weight: float = 0.01,
    hidden_size: int = 256,
    checkpoint_interval: int = 10,
    checkpoint_dir: str = "trunk/ai/ai_operator/checkpoints_multi_agent",
    enable_live_plotting: bool = True,
    plot_refresh_interval: int = 1,
) -> list[MultiAgentEpisodeSummary]:
    """
    Run a compact multi-agent training session.

    :param grid_path:
        Path to a VeraGrid-readable grid file.
    :param multi_agent_config:
        Optional multi-agent scheduling configuration.
    :param episodes:
        Number of training episodes.
    :param max_turns_per_episode:
        Maximum number of turns per episode.
    :param learning_rate:
        Adam optimizer learning rate.
    :param gamma:
        Discount factor.
    :param value_loss_weight:
        Critic loss coefficient.
    :param entropy_weight:
        Entropy coefficient.
    :param hidden_size:
        Policy hidden width.
    :param checkpoint_interval:
        Episodes between checkpoints.
    :param checkpoint_dir:
        Checkpoint directory path.
    :param enable_live_plotting:
        Enable or disable the live plotting monitor.
    :param plot_refresh_interval:
        Number of episodes between plot refreshes.
    :return:
        Multi-agent episode summaries.
    """

    scheduler_config: MultiAgentConfig = (
        build_frank_and_jeffry_config() if multi_agent_config is None else multi_agent_config
    )
    training_config: MultiAgentTrainingConfig = MultiAgentTrainingConfig(
        episodes=episodes,
        max_turns_per_episode=max_turns_per_episode,
        learning_rate=learning_rate,
        gamma=gamma,
        value_loss_weight=value_loss_weight,
        entropy_weight=entropy_weight,
        hidden_size=hidden_size,
        checkpoint_interval=checkpoint_interval,
        checkpoint_dir=checkpoint_dir,
    )
    _, history = train_multi_agent_policy_system(
        grid_path=grid_path,
        multi_agent_config=scheduler_config,
        training_config=training_config,
        live_plot_config=LivePlotConfig(
            enabled=enable_live_plotting,
            refresh_interval=plot_refresh_interval,
            window_title="AI Operator Multi-Agent Training Demo",
        ),
    )
    return history


if __name__ == "__main__":
    run_multi_agent_training_demo(
        grid_path="files/IEEE 9 Bus.veragrid",
        episodes=2000,
        max_turns_per_episode=32,
        enable_live_plotting=True,
        plot_refresh_interval=1,
    )
