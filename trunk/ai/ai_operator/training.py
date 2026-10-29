from __future__ import annotations

from typing import Any

import os

import torch
from torch import nn

import VeraGridEngine.api as gce

from trunk.ai.ai_operator.environment import StepInfo
from trunk.ai.ai_operator.live_plotting import LivePlotConfig
from trunk.ai.ai_operator.live_plotting import SingleAgentLivePlotter
from trunk.ai.ai_operator.environment import VeraGridOperatorEnv
from trunk.ai.ai_operator.network import OperatorPolicyNetwork
from trunk.ai.ai_operator.network import PolicyActionSample
from trunk.ai.ai_operator.network import build_policy_network_from_observation
from trunk.ai.ai_operator.network import sample_action_with_policy
from trunk.ai.ai_operator.observations import ObservationData
from trunk.ai.ai_operator.reward import GridMetricSnapshot
from trunk.ai.ai_operator.reward import GridMetricSummary


class TrainingConfig:
    """
    Training hyperparameter container.

    :param episodes:
        Number of episodes to train.
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
    """

    __slots__ = (
        "_episodes",
        "_max_steps_per_episode",
        "_learning_rate",
        "_gamma",
        "_value_loss_weight",
        "_entropy_weight",
        "_hidden_size",
        "_checkpoint_interval",
        "_checkpoint_dir",
    )

    def __init__(
        self,
        episodes: int = 200,
        max_steps_per_episode: int = 32,
        learning_rate: float = 1.0e-4,
        gamma: float = 0.99,
        value_loss_weight: float = 0.5,
        entropy_weight: float = 0.01,
        hidden_size: int = 256,
        checkpoint_interval: int = 25,
        checkpoint_dir: str = "trunk/ai/ai_operator/checkpoints",
    ) -> None:
        self._episodes: int = episodes
        self._max_steps_per_episode: int = max_steps_per_episode
        self._learning_rate: float = learning_rate
        self._gamma: float = gamma
        self._value_loss_weight: float = value_loss_weight
        self._entropy_weight: float = entropy_weight
        self._hidden_size: int = hidden_size
        self._checkpoint_interval: int = checkpoint_interval
        self._checkpoint_dir: str = checkpoint_dir

    def get_episodes(self) -> int:
        """
        Get the episode count.

        :return:
            Number of training episodes.
        """

        return self._episodes

    def get_max_steps_per_episode(self) -> int:
        """
        Get the per-episode step limit.

        :return:
            Maximum steps per episode.
        """

        return self._max_steps_per_episode

    def get_learning_rate(self) -> float:
        """
        Get the optimizer learning rate.

        :return:
            Learning rate.
        """

        return self._learning_rate

    def get_gamma(self) -> float:
        """
        Get the reward discount factor.

        :return:
            Discount factor.
        """

        return self._gamma

    def get_value_loss_weight(self) -> float:
        """
        Get the value loss coefficient.

        :return:
            Value loss weight.
        """

        return self._value_loss_weight

    def get_entropy_weight(self) -> float:
        """
        Get the entropy regularization coefficient.

        :return:
            Entropy coefficient.
        """

        return self._entropy_weight

    def get_hidden_size(self) -> int:
        """
        Get the policy hidden width.

        :return:
            Hidden layer width.
        """

        return self._hidden_size

    def get_checkpoint_interval(self) -> int:
        """
        Get the checkpoint interval.

        :return:
            Episodes between checkpoints.
        """

        return self._checkpoint_interval

    def get_checkpoint_dir(self) -> str:
        """
        Get the checkpoint directory.

        :return:
            Checkpoint directory path.
        """

        return self._checkpoint_dir


class EpisodeStep:
    """
    One training trajectory step.

    :param observation:
        Observation before the action.
    :param action_sample:
        Sampled policy action metadata.
    :param reward:
        Reward obtained after the action.
    :param terminated:
        Episode termination flag.
    :param truncated:
        Episode truncation flag.
    :param step_info:
        Environment side metadata for inspection.
    """

    __slots__ = (
        "_observation",
        "_action_sample",
        "_reward",
        "_terminated",
        "_truncated",
        "_step_info",
    )

    def __init__(
        self,
        observation: ObservationData,
        action_sample: PolicyActionSample,
        reward: float,
        terminated: bool,
        truncated: bool,
        step_info: StepInfo,
    ) -> None:
        self._observation: ObservationData = observation
        self._action_sample: PolicyActionSample = action_sample
        self._reward: float = reward
        self._terminated: bool = terminated
        self._truncated: bool = truncated
        self._step_info: StepInfo = step_info

    def get_action_sample(self) -> PolicyActionSample:
        """
        Get the sampled action metadata.

        :return:
            Sampled action bundle.
        """

        return self._action_sample

    def get_reward(self) -> float:
        """
        Get the step reward.

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
        Get the environment step metadata.

        :return:
            Step metadata.
        """

        return self._step_info


class EpisodeSummary:
    """
    Episode summary record.

    :param episode_idx:
        Episode index starting at one.
    :param total_reward:
        Sum of rewards over the episode.
    :param step_count:
        Number of executed steps.
    :param actor_loss:
        Policy loss scalar.
    :param value_loss:
        Value loss scalar.
    :param entropy:
        Mean entropy scalar.
    :param grid_metric_summary:
        Aggregated episode-level grid metrics.
    """

    __slots__ = (
        "_episode_idx",
        "_total_reward",
        "_step_count",
        "_actor_loss",
        "_value_loss",
        "_entropy",
        "_grid_metric_summary",
    )

    def __init__(
        self,
        episode_idx: int,
        total_reward: float,
        step_count: int,
        actor_loss: float,
        value_loss: float,
        entropy: float,
        grid_metric_summary: GridMetricSummary,
    ) -> None:
        self._episode_idx: int = episode_idx
        self._total_reward: float = total_reward
        self._step_count: int = step_count
        self._actor_loss: float = actor_loss
        self._value_loss: float = value_loss
        self._entropy: float = entropy
        self._grid_metric_summary: GridMetricSummary = grid_metric_summary

    def get_episode_idx(self) -> int:
        """
        Get the episode index.

        :return:
            Episode index.
        """

        return self._episode_idx

    def get_total_reward(self) -> float:
        """
        Get the total episode reward.

        :return:
            Total reward.
        """

        return self._total_reward

    def get_step_count(self) -> int:
        """
        Get the episode length.

        :return:
            Number of steps.
        """

        return self._step_count

    def get_actor_loss(self) -> float:
        """
        Get the actor loss.

        :return:
            Actor loss scalar.
        """

        return self._actor_loss

    def get_value_loss(self) -> float:
        """
        Get the value loss.

        :return:
            Value loss scalar.
        """

        return self._value_loss

    def get_entropy(self) -> float:
        """
        Get the mean entropy.

        :return:
            Entropy scalar.
        """

        return self._entropy

    def get_grid_metric_summary(self) -> GridMetricSummary:
        """
        Get the aggregated episode-level grid metrics.

        :return:
            Grid metric summary.
        """

        return self._grid_metric_summary


def train_operator_policy(
    grid_path: str,
    training_config: TrainingConfig | None = None,
    device: torch.device | None = None,
    live_plot_config: LivePlotConfig | None = None,
) -> tuple[OperatorPolicyNetwork, list[EpisodeSummary]]:
    """
    Train the operator policy with a simple actor-critic update.

    :param grid_path:
        Path to a VeraGrid grid file.
    :param training_config:
        Optional training hyperparameter bundle.
    :param device:
        Optional Torch device.
    :param live_plot_config:
        Optional live plotting configuration bundle.
    :return:
        Trained policy network and episode summaries.
    """

    # The training driver creates one environment and repeatedly collects complete
    # trajectories so the value head can estimate returns and the policy can improve.
    config_obj: TrainingConfig = TrainingConfig() if training_config is None else training_config
    device_obj: torch.device = torch.device("cpu") if device is None else device

    grid: Any = gce.open_file(grid_path)
    env: VeraGridOperatorEnv = VeraGridOperatorEnv(grid=grid)
    initial_observation: ObservationData = env.reset()
    policy_network: OperatorPolicyNetwork = build_policy_network_from_observation(
        observation=initial_observation,
        branch_count=env.get_branch_count(),
        generator_count=env.get_generator_count(),
        config=env.get_config(),
        hidden_size=config_obj.get_hidden_size(),
    )
    policy_network.to(device_obj)

    optimizer: torch.optim.Optimizer = torch.optim.Adam(
        policy_network.parameters(),
        lr=config_obj.get_learning_rate(),
    )
    history: list[EpisodeSummary] = list()
    live_plotter: SingleAgentLivePlotter = SingleAgentLivePlotter(plot_config=live_plot_config)
    episode_idx: int

    ensure_checkpoint_dir(config_obj.get_checkpoint_dir())

    for episode_idx in range(config_obj.get_episodes()):
        trajectory: list[EpisodeStep] = collect_training_episode(
            env=env,
            policy_network=policy_network,
            max_steps=config_obj.get_max_steps_per_episode(),
            device=device_obj,
        )
        actor_loss: torch.Tensor
        value_loss: torch.Tensor
        entropy_bonus: torch.Tensor
        actor_loss, value_loss, entropy_bonus = compute_actor_critic_losses(
            trajectory=trajectory,
            gamma=config_obj.get_gamma(),
            value_loss_weight=config_obj.get_value_loss_weight(),
            entropy_weight=config_obj.get_entropy_weight(),
            device=device_obj,
        )

        # The backward pass updates the policy and value heads from the same shared trunk,
        # which is why both losses are optimized together in one gradient step.
        optimizer.zero_grad()
        total_loss: torch.Tensor = actor_loss + value_loss - entropy_bonus
        total_loss.backward()
        optimizer.step()

        summary: EpisodeSummary = build_episode_summary(
            episode_idx=episode_idx + 1,
            trajectory=trajectory,
            actor_loss=actor_loss,
            value_loss=value_loss,
            entropy_bonus=entropy_bonus,
        )
        history.append(summary)
        live_plotter.update(summary)

        print(
            f"episode={summary.get_episode_idx()} "
            f"steps={summary.get_step_count()} "
            f"reward={summary.get_total_reward():.3f} "
            f"actor_loss={summary.get_actor_loss():.6f} "
            f"value_loss={summary.get_value_loss():.6f} "
            f"entropy={summary.get_entropy():.6f} "
            f"secure_rate={summary.get_grid_metric_summary().get_secure_rate():.3f} "
            f"pf_convergence_rate={summary.get_grid_metric_summary().get_pf_convergence_rate():.3f} "
            f"max_loading={summary.get_grid_metric_summary().get_mean_maximum_branch_loading():.3f}"
        )

        if should_save_checkpoint(summary.get_episode_idx(), config_obj.get_checkpoint_interval()):
            save_policy_checkpoint(
                policy_network=policy_network,
                optimizer=optimizer,
                training_config=config_obj,
                episode_idx=summary.get_episode_idx(),
                checkpoint_dir=config_obj.get_checkpoint_dir(),
            )
        else:
            episode_idx = episode_idx

    live_plotter.close()
    return policy_network, history


def collect_training_episode(
    env: VeraGridOperatorEnv,
    policy_network: OperatorPolicyNetwork,
    max_steps: int,
    device: torch.device,
) -> list[EpisodeStep]:
    """
    Collect one policy-driven training episode.

    :param env:
        Operator environment.
    :param policy_network:
        Operator policy network.
    :param max_steps:
        Maximum number of environment steps.
    :param device:
        Torch device.
    :return:
        Trajectory steps.
    """

    # Each episode starts from a fresh environment reset so the training update is
    # based on a clean trajectory from the current policy.
    observation: ObservationData = env.reset()
    trajectory: list[EpisodeStep] = list()
    step_idx: int

    for step_idx in range(max_steps):
        action_sample: PolicyActionSample
        action_sample, _ = sample_action_with_policy(
            policy_network=policy_network,
            observation=observation,
            branch_count=env.get_branch_count(),
            generator_count=env.get_generator_count(),
            device=device,
        )

        next_observation: ObservationData
        reward: float
        terminated: bool
        truncated: bool
        step_info: StepInfo
        next_observation, reward, terminated, truncated, step_info = env.step(action_sample.get_action())

        trajectory.append(
            EpisodeStep(
                observation=observation,
                action_sample=action_sample,
                reward=reward,
                terminated=terminated,
                truncated=truncated,
                step_info=step_info,
            )
        )
        observation = next_observation

        if terminated or truncated:
            break
        else:
            step_idx = step_idx

    return trajectory


def compute_discounted_returns(trajectory: list[EpisodeStep], gamma: float, device: torch.device) -> torch.Tensor:
    """
    Compute discounted returns for one trajectory.

    :param trajectory:
        Episode trajectory.
    :param gamma:
        Reward discount factor.
    :param device:
        Torch device.
    :return:
        Return tensor with one entry per trajectory step.
    """

    # Returns are computed backwards so each state sees the full discounted future
    # reward that followed the action chosen at that step.
    step_count: int = len(trajectory)
    returns_tensor: torch.Tensor = torch.empty(step_count, dtype=torch.float32, device=device)
    running_return: float = 0.0
    reverse_idx: int

    for reverse_idx in range(step_count - 1, -1, -1):
        running_return = trajectory[reverse_idx].get_reward() + gamma * running_return
        returns_tensor[reverse_idx] = running_return

    return returns_tensor


def compute_actor_critic_losses(
    trajectory: list[EpisodeStep],
    gamma: float,
    value_loss_weight: float,
    entropy_weight: float,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Compute actor, value, and entropy loss terms for one trajectory.

    :param trajectory:
        Episode trajectory.
    :param gamma:
        Reward discount factor.
    :param value_loss_weight:
        Coefficient for the value loss.
    :param entropy_weight:
        Coefficient for the entropy bonus.
    :param device:
        Torch device.
    :return:
        Actor loss, weighted value loss, and weighted entropy bonus.
    """

    # The actor loss uses advantage estimates from returns minus the critic values.
    # The critic loss uses mean squared error so the value head learns to fit returns.
    returns_tensor: torch.Tensor = compute_discounted_returns(trajectory, gamma, device)
    step_count: int = len(trajectory)
    log_prob_tensor: torch.Tensor = torch.empty(step_count, dtype=torch.float32, device=device)
    value_tensor: torch.Tensor = torch.empty(step_count, dtype=torch.float32, device=device)
    entropy_tensor: torch.Tensor = torch.empty(step_count, dtype=torch.float32, device=device)
    step_idx: int

    for step_idx in range(step_count):
        log_prob_tensor[step_idx] = trajectory[step_idx].get_action_sample().get_log_prob()
        value_tensor[step_idx] = trajectory[step_idx].get_action_sample().get_value()
        entropy_tensor[step_idx] = trajectory[step_idx].get_action_sample().get_entropy()

    advantage_tensor: torch.Tensor = returns_tensor - value_tensor.detach()
    actor_loss: torch.Tensor = -(log_prob_tensor * advantage_tensor).mean()
    value_loss: torch.Tensor = value_loss_weight * nn.functional.mse_loss(value_tensor, returns_tensor)
    entropy_bonus: torch.Tensor = entropy_weight * entropy_tensor.mean()
    return actor_loss, value_loss, entropy_bonus


def build_episode_summary(
    episode_idx: int,
    trajectory: list[EpisodeStep],
    actor_loss: torch.Tensor,
    value_loss: torch.Tensor,
    entropy_bonus: torch.Tensor,
) -> EpisodeSummary:
    """
    Build a compact summary for one finished episode.

    :param episode_idx:
        Episode index starting at one.
    :param trajectory:
        Episode trajectory.
    :param actor_loss:
        Actor loss tensor.
    :param value_loss:
        Value loss tensor.
    :param entropy_bonus:
        Entropy bonus tensor.
    :return:
        Episode summary record.
    """

    total_reward: float = 0.0
    step_count: int = len(trajectory)
    grid_metric_summary: GridMetricSummary = build_grid_metric_summary_from_episode_steps(trajectory)
    step_idx: int

    for step_idx in range(step_count):
        total_reward += trajectory[step_idx].get_reward()

    return EpisodeSummary(
        episode_idx=episode_idx,
        total_reward=total_reward,
        step_count=step_count,
        actor_loss=float(actor_loss.detach().cpu().item()),
        value_loss=float(value_loss.detach().cpu().item()),
        entropy=float(entropy_bonus.detach().cpu().item()),
        grid_metric_summary=grid_metric_summary,
    )


def build_grid_metric_summary_from_episode_steps(trajectory: list[EpisodeStep]) -> GridMetricSummary:
    """
    Aggregate episode-level grid metrics from a single-agent trajectory.

    :param trajectory:
        Episode trajectory.
    :return:
        Episode-level grid metric summary.
    """

    step_count: int = len(trajectory)

    if step_count > 0:
        convergence_sum: float = 0.0
        secure_sum: float = 0.0
        voltage_violation_sum: float = 0.0
        overload_violation_sum: float = 0.0
        generator_violation_sum: float = 0.0
        minimum_voltage_sum: float = 0.0
        maximum_voltage_sum: float = 0.0
        maximum_branch_loading_sum: float = 0.0
        step_idx: int

        for step_idx in range(step_count):
            grid_metrics: GridMetricSnapshot = trajectory[step_idx].get_step_info().get_grid_metrics()
            convergence_sum += 1.0 if grid_metrics.get_pf_converged() else 0.0
            secure_sum += 1.0 if grid_metrics.get_secure_state() else 0.0
            voltage_violation_sum += grid_metrics.get_voltage_violation_sum()
            overload_violation_sum += grid_metrics.get_overload_violation_sum()
            generator_violation_sum += grid_metrics.get_generator_violation_sum()
            minimum_voltage_sum += grid_metrics.get_minimum_voltage()
            maximum_voltage_sum += grid_metrics.get_maximum_voltage()
            maximum_branch_loading_sum += grid_metrics.get_maximum_branch_loading()

        denominator: float = float(step_count)
        return GridMetricSummary(
            pf_convergence_rate=convergence_sum / denominator,
            secure_rate=secure_sum / denominator,
            mean_voltage_violation=voltage_violation_sum / denominator,
            mean_overload_violation=overload_violation_sum / denominator,
            mean_generator_violation=generator_violation_sum / denominator,
            mean_minimum_voltage=minimum_voltage_sum / denominator,
            mean_maximum_voltage=maximum_voltage_sum / denominator,
            mean_maximum_branch_loading=maximum_branch_loading_sum / denominator,
        )
    else:
        return GridMetricSummary(
            pf_convergence_rate=0.0,
            secure_rate=0.0,
            mean_voltage_violation=0.0,
            mean_overload_violation=0.0,
            mean_generator_violation=0.0,
            mean_minimum_voltage=0.0,
            mean_maximum_voltage=0.0,
            mean_maximum_branch_loading=0.0,
        )


def ensure_checkpoint_dir(checkpoint_dir: str) -> None:
    """
    Ensure that the checkpoint directory exists.

    :param checkpoint_dir:
        Directory path.
    :return:
        ``None``.
    """

    # The training loop writes periodic checkpoints so the directory is created once
    # before the first episode rather than checked on every save.
    if os.path.isdir(checkpoint_dir):
        checkpoint_dir = checkpoint_dir
    else:
        os.makedirs(checkpoint_dir, exist_ok=True)


def should_save_checkpoint(episode_idx: int, checkpoint_interval: int) -> bool:
    """
    Decide whether the current episode should trigger a checkpoint save.

    :param episode_idx:
        Episode index starting at one.
    :param checkpoint_interval:
        Episodes between checkpoints.
    :return:
        ``True`` when a checkpoint should be saved.
    """

    if checkpoint_interval > 0:
        return episode_idx % checkpoint_interval == 0
    else:
        return False


def save_policy_checkpoint(
    policy_network: OperatorPolicyNetwork,
    optimizer: torch.optim.Optimizer,
    training_config: TrainingConfig,
    episode_idx: int,
    checkpoint_dir: str,
) -> str:
    """
    Save a policy checkpoint to disk.

    :param policy_network:
        Operator policy network.
    :param optimizer:
        Optimizer state to persist.
    :param training_config:
        Training configuration bundle.
    :param episode_idx:
        Episode index starting at one.
    :param checkpoint_dir:
        Directory where checkpoints are stored.
    :return:
        Checkpoint file path.
    """

    # The checkpoint contains enough information to resume optimization or evaluate
    # a previously trained policy later in the workflow.
    checkpoint_path: str = os.path.join(checkpoint_dir, f"operator_policy_episode_{episode_idx:05d}.pt")
    checkpoint_data: dict[str, Any] = dict()
    checkpoint_data["episode_idx"] = episode_idx
    checkpoint_data["model_state_dict"] = policy_network.state_dict()
    checkpoint_data["optimizer_state_dict"] = optimizer.state_dict()
    checkpoint_data["learning_rate"] = training_config.get_learning_rate()
    checkpoint_data["gamma"] = training_config.get_gamma()
    torch.save(checkpoint_data, checkpoint_path)
    return checkpoint_path


def load_policy_checkpoint(
    checkpoint_path: str,
    policy_network: OperatorPolicyNetwork,
    optimizer: torch.optim.Optimizer | None = None,
    map_location: str | torch.device = "cpu",
) -> int:
    """
    Load a saved policy checkpoint from disk.

    :param checkpoint_path:
        Path to the checkpoint file.
    :param policy_network:
        Policy network instance to populate.
    :param optimizer:
        Optional optimizer instance to populate.
    :param map_location:
        Torch checkpoint loading device.
    :return:
        Loaded episode index.
    """

    checkpoint_data: dict[str, Any] = torch.load(checkpoint_path, map_location=map_location)
    policy_network.load_state_dict(checkpoint_data["model_state_dict"])

    if optimizer is None:
        optimizer = optimizer
    else:
        optimizer.load_state_dict(checkpoint_data["optimizer_state_dict"])

    episode_idx: int = int(checkpoint_data["episode_idx"])
    return episode_idx
