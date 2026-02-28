from __future__ import annotations

from trunk.ai.ai_operator.live_plotting import LivePlotConfig
from trunk.ai.ai_operator.training import EpisodeSummary
from trunk.ai.ai_operator.training import TrainingConfig
from trunk.ai.ai_operator.training import train_operator_policy


def run_training_demo(
    grid_path: str,
    episodes: int = 20,
    max_steps_per_episode: int = 16,
    learning_rate: float = 1.0e-4,
    gamma: float = 0.99,
    value_loss_weight: float = 0.5,
    entropy_weight: float = 0.01,
    hidden_size: int = 256,
    checkpoint_interval: int = 10,
    checkpoint_dir: str = "trunk/ai/ai_operator/checkpoints",
    enable_live_plotting: bool = True,
    plot_refresh_interval: int = 1,
) -> list[EpisodeSummary]:
    """
    Run a compact training session for the operator policy.

    :param grid_path:
        Path to a VeraGrid-readable grid file.
    :param episodes:
        Number of training episodes.
    :param max_steps_per_episode:
        Maximum number of environment steps per episode.
    :param learning_rate:
        Adam optimizer learning rate.
    :param gamma:
        Discount factor for future rewards.
    :param value_loss_weight:
        Coefficient applied to the value loss.
    :param entropy_weight:
        Coefficient applied to the entropy bonus.
    :param hidden_size:
        Shared policy network hidden width.
    :param checkpoint_interval:
        Save a checkpoint every this many episodes.
    :param checkpoint_dir:
        Directory where checkpoints are stored.
    :param enable_live_plotting:
        Enable or disable the live plotting monitor.
    :param plot_refresh_interval:
        Number of episodes between plot refreshes.
    :return:
        Episode summaries collected during training.
    """

    # This wrapper exists so a developer can trigger a small end-to-end learning run
    # from Python code without mixing the concern with the non-training rollout demo.
    training_config: TrainingConfig = TrainingConfig(
        episodes=episodes,
        max_steps_per_episode=max_steps_per_episode,
        learning_rate=learning_rate,
        gamma=gamma,
        value_loss_weight=value_loss_weight,
        entropy_weight=entropy_weight,
        hidden_size=hidden_size,
        checkpoint_interval=checkpoint_interval,
        checkpoint_dir=checkpoint_dir,
    )

    _, history = train_operator_policy(
        grid_path=grid_path,
        training_config=training_config,
        live_plot_config=LivePlotConfig(
            enabled=enable_live_plotting,
            refresh_interval=plot_refresh_interval,
            window_title="AI Operator Training Demo",
        ),
    )

    return history


if __name__ == "__main__":
    run_training_demo(
        grid_path="files/IEEE 9 Bus.veragrid",
        episodes=200,
        max_steps_per_episode=160,
        enable_live_plotting=True,
        plot_refresh_interval=1,
    )
