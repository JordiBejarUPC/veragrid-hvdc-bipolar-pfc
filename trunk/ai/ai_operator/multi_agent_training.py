from __future__ import annotations

from typing import Any

import os

import torch
from torch import nn

import VeraGridEngine.api as gce

from trunk.ai.ai_operator.agents import AgentSpec
from trunk.ai.ai_operator.agents import MultiAgentConfig
from trunk.ai.ai_operator.agents import build_frank_and_jeffry_config
from trunk.ai.ai_operator.environment import VeraGridOperatorEnv
from trunk.ai.ai_operator.live_plotting import LivePlotConfig
from trunk.ai.ai_operator.live_plotting import MultiAgentLivePlotter
from trunk.ai.ai_operator.multi_agent_environment import MultiAgentOperatorEnv
from trunk.ai.ai_operator.multi_agent_environment import MultiAgentStepInfo
from trunk.ai.ai_operator.network import OperatorPolicyNetwork
from trunk.ai.ai_operator.network import PolicyActionSample
from trunk.ai.ai_operator.network import build_policy_network_from_observation
from trunk.ai.ai_operator.network import sample_action_with_policy
from trunk.ai.ai_operator.observations import ObservationData


class MultiAgentTrainingConfig:
    """
    Multi-agent training hyperparameter container.

    :param episodes:
        Number of multi-agent episodes to train.
    :param max_turns_per_episode:
        Maximum number of scheduled turns per episode.
    :param learning_rate:
        Adam optimizer learning rate used for every policy group.
    :param gamma:
        Discount factor for future rewards.
    :param value_loss_weight:
        Coefficient applied to the critic loss.
    :param entropy_weight:
        Coefficient applied to the entropy bonus.
    :param hidden_size:
        Shared hidden width for every policy network.
    :param checkpoint_interval:
        Save multi-agent checkpoints every this many episodes.
    :param checkpoint_dir:
        Directory where checkpoints are stored.
    """

    __slots__ = (
        "_episodes",
        "_max_turns_per_episode",
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
        max_turns_per_episode: int = 64,
        learning_rate: float = 1.0e-4,
        gamma: float = 0.99,
        value_loss_weight: float = 0.5,
        entropy_weight: float = 0.01,
        hidden_size: int = 256,
        checkpoint_interval: int = 25,
        checkpoint_dir: str = "trunk/ai/ai_operator/checkpoints_multi_agent",
    ) -> None:
        self._episodes: int = episodes
        self._max_turns_per_episode: int = max_turns_per_episode
        self._learning_rate: float = learning_rate
        self._gamma: float = gamma
        self._value_loss_weight: float = value_loss_weight
        self._entropy_weight: float = entropy_weight
        self._hidden_size: int = hidden_size
        self._checkpoint_interval: int = checkpoint_interval
        self._checkpoint_dir: str = checkpoint_dir

    def get_episodes(self) -> int:
        """
        Get the number of episodes.

        :return:
            Episode count.
        """

        return self._episodes

    def get_max_turns_per_episode(self) -> int:
        """
        Get the per-episode turn limit.

        :return:
            Maximum scheduled turns per episode.
        """

        return self._max_turns_per_episode

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
        Get the value loss weight.

        :return:
            Value loss coefficient.
        """

        return self._value_loss_weight

    def get_entropy_weight(self) -> float:
        """
        Get the entropy weight.

        :return:
            Entropy bonus coefficient.
        """

        return self._entropy_weight

    def get_hidden_size(self) -> int:
        """
        Get the policy hidden width.

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


class MultiAgentEpisodeStep:
    """
    One multi-agent trajectory step.

    :param acting_agent:
        Agent that acted on this turn.
    :param observation:
        Observation before the action.
    :param action_sample:
        Stochastic policy sample.
    :param reward:
        Aligned reward seen by the acting agent.
    :param terminated:
        Episode termination flag.
    :param truncated:
        Episode truncation flag.
    :param step_info:
        Multi-agent step metadata.
    """

    __slots__ = (
        "_acting_agent",
        "_observation",
        "_action_sample",
        "_reward",
        "_terminated",
        "_truncated",
        "_step_info",
    )

    def __init__(
        self,
        acting_agent: AgentSpec,
        observation: ObservationData,
        action_sample: PolicyActionSample,
        reward: float,
        terminated: bool,
        truncated: bool,
        step_info: MultiAgentStepInfo,
    ) -> None:
        self._acting_agent: AgentSpec = acting_agent
        self._observation: ObservationData = observation
        self._action_sample: PolicyActionSample = action_sample
        self._reward: float = reward
        self._terminated: bool = terminated
        self._truncated: bool = truncated
        self._step_info: MultiAgentStepInfo = step_info

    def get_acting_agent(self) -> AgentSpec:
        """
        Get the acting agent.

        :return:
            Acting agent specification.
        """

        return self._acting_agent

    def get_action_sample(self) -> PolicyActionSample:
        """
        Get the stochastic policy sample.

        :return:
            Policy action sample.
        """

        return self._action_sample

    def get_reward(self) -> float:
        """
        Get the aligned reward.

        :return:
            Step reward.
        """

        return self._reward


class PolicyGroupTrainer:
    """
    Per-policy-group optimizer bundle.

    :param policy_group:
        Logical policy group name.
    :param policy_network:
        Policy network used by the group.
    :param optimizer:
        Optimizer attached to the policy network.
    """

    __slots__ = ("_policy_group", "_policy_network", "_optimizer")

    def __init__(
        self,
        policy_group: str,
        policy_network: OperatorPolicyNetwork,
        optimizer: torch.optim.Optimizer,
    ) -> None:
        self._policy_group: str = policy_group
        self._policy_network: OperatorPolicyNetwork = policy_network
        self._optimizer: torch.optim.Optimizer = optimizer

    def get_policy_group(self) -> str:
        """
        Get the logical policy group name.

        :return:
            Policy group name.
        """

        return self._policy_group

    def get_policy_network(self) -> OperatorPolicyNetwork:
        """
        Get the policy network.

        :return:
            Policy network.
        """

        return self._policy_network

    def get_optimizer(self) -> torch.optim.Optimizer:
        """
        Get the optimizer.

        :return:
            Optimizer.
        """

        return self._optimizer


class PolicyGroupSummary:
    """
    Summary of one policy group update.

    :param policy_group:
        Logical policy group name.
    :param step_count:
        Number of turns attributed to that group in the episode.
    :param total_reward:
        Sum of aligned rewards for the group.
    :param actor_loss:
        Actor loss after the group update.
    :param value_loss:
        Value loss after the group update.
    :param entropy:
        Entropy bonus value after the group update.
    """

    __slots__ = (
        "_policy_group",
        "_step_count",
        "_total_reward",
        "_actor_loss",
        "_value_loss",
        "_entropy",
    )

    def __init__(
        self,
        policy_group: str,
        step_count: int,
        total_reward: float,
        actor_loss: float,
        value_loss: float,
        entropy: float,
    ) -> None:
        self._policy_group: str = policy_group
        self._step_count: int = step_count
        self._total_reward: float = total_reward
        self._actor_loss: float = actor_loss
        self._value_loss: float = value_loss
        self._entropy: float = entropy

    def get_policy_group(self) -> str:
        """
        Get the policy group name.

        :return:
            Policy group name.
        """

        return self._policy_group

    def get_step_count(self) -> int:
        """
        Get the number of turns assigned to the group.

        :return:
            Turn count.
        """

        return self._step_count

    def get_total_reward(self) -> float:
        """
        Get the total aligned reward for the group.

        :return:
            Total reward.
        """

        return self._total_reward

    def get_actor_loss(self) -> float:
        """
        Get the actor loss.

        :return:
            Actor loss.
        """

        return self._actor_loss

    def get_value_loss(self) -> float:
        """
        Get the value loss.

        :return:
            Value loss.
        """

        return self._value_loss

    def get_entropy(self) -> float:
        """
        Get the entropy value.

        :return:
            Entropy value.
        """

        return self._entropy


class MultiAgentEpisodeSummary:
    """
    Summary of one multi-agent training episode.

    :param episode_idx:
        Episode index starting at one.
    :param turn_count:
        Total number of scheduled turns.
    :param group_summaries:
        One summary per policy group.
    """

    __slots__ = ("_episode_idx", "_turn_count", "_group_summaries")

    def __init__(
        self,
        episode_idx: int,
        turn_count: int,
        group_summaries: list[PolicyGroupSummary],
    ) -> None:
        self._episode_idx: int = episode_idx
        self._turn_count: int = turn_count
        self._group_summaries: list[PolicyGroupSummary] = group_summaries

    def get_episode_idx(self) -> int:
        """
        Get the episode index.

        :return:
            Episode index.
        """

        return self._episode_idx

    def get_turn_count(self) -> int:
        """
        Get the total number of turns.

        :return:
            Turn count.
        """

        return self._turn_count

    def get_group_summaries(self) -> list[PolicyGroupSummary]:
        """
        Get the policy group summaries.

        :return:
            List of group summaries.
        """

        return self._group_summaries


def train_multi_agent_policy_system(
    grid_path: str,
    multi_agent_config: MultiAgentConfig | None = None,
    training_config: MultiAgentTrainingConfig | None = None,
    device: torch.device | None = None,
    live_plot_config: LivePlotConfig | None = None,
) -> tuple[list[PolicyGroupTrainer], list[MultiAgentEpisodeSummary]]:
    """
    Train a policy system with one policy per logical agent group.

    :param grid_path:
        Path to a VeraGrid grid file.
    :param multi_agent_config:
        Optional multi-agent scheduling configuration.
    :param training_config:
        Optional multi-agent training hyperparameter bundle.
    :param device:
        Optional Torch device.
    :param live_plot_config:
        Optional live plotting configuration bundle.
    :return:
        Policy group trainers and episode summaries.
    """

    config_obj: MultiAgentTrainingConfig = (
        MultiAgentTrainingConfig() if training_config is None else training_config
    )
    scheduler_config: MultiAgentConfig = (
        build_frank_and_jeffry_config() if multi_agent_config is None else multi_agent_config
    )
    device_obj: torch.device = torch.device("cpu") if device is None else device

    grid: Any = gce.open_file(grid_path)
    base_env: VeraGridOperatorEnv = VeraGridOperatorEnv(grid=grid)
    multi_agent_env: MultiAgentOperatorEnv = MultiAgentOperatorEnv(
        base_env=base_env,
        multi_agent_config=scheduler_config,
    )
    reset_payload = multi_agent_env.reset()
    initial_observation: ObservationData = reset_payload.get_observation()
    group_trainers: list[PolicyGroupTrainer] = build_policy_group_trainers(
        multi_agent_env=multi_agent_env,
        observation=initial_observation,
        training_config=config_obj,
        device=device_obj,
    )
    ensure_multi_agent_checkpoint_dir(config_obj.get_checkpoint_dir())

    history: list[MultiAgentEpisodeSummary] = list()
    live_plotter: MultiAgentLivePlotter = MultiAgentLivePlotter(plot_config=live_plot_config)
    episode_idx: int

    for episode_idx in range(config_obj.get_episodes()):
        trajectory: list[MultiAgentEpisodeStep] = collect_multi_agent_episode(
            multi_agent_env=multi_agent_env,
            group_trainers=group_trainers,
            max_turns=config_obj.get_max_turns_per_episode(),
            device=device_obj,
        )
        group_summaries: list[PolicyGroupSummary] = update_all_policy_groups(
            trajectory=trajectory,
            group_trainers=group_trainers,
            gamma=config_obj.get_gamma(),
            value_loss_weight=config_obj.get_value_loss_weight(),
            entropy_weight=config_obj.get_entropy_weight(),
            device=device_obj,
        )
        episode_summary: MultiAgentEpisodeSummary = MultiAgentEpisodeSummary(
            episode_idx=episode_idx + 1,
            turn_count=len(trajectory),
            group_summaries=group_summaries,
        )
        history.append(episode_summary)
        live_plotter.update(episode_summary)
        print_multi_agent_episode_summary(episode_summary)

        if should_save_multi_agent_checkpoint(
            episode_idx=episode_summary.get_episode_idx(),
            checkpoint_interval=config_obj.get_checkpoint_interval(),
        ):
            save_multi_agent_checkpoint(
                group_trainers=group_trainers,
                episode_idx=episode_summary.get_episode_idx(),
                checkpoint_dir=config_obj.get_checkpoint_dir(),
            )
        else:
            episode_idx = episode_idx

    live_plotter.close()
    return group_trainers, history


def build_policy_group_trainers(
    multi_agent_env: MultiAgentOperatorEnv,
    observation: ObservationData,
    training_config: MultiAgentTrainingConfig,
    device: torch.device,
) -> list[PolicyGroupTrainer]:
    """
    Build one trainable policy bundle per unique policy group.

    :param multi_agent_env:
        Multi-agent environment.
    :param observation:
        Example observation for network sizing.
    :param training_config:
        Multi-agent training configuration.
    :param device:
        Torch device.
    :return:
        Policy group trainers.
    """

    group_names: list[str] = collect_unique_policy_groups(multi_agent_env.get_agent_specs())
    group_trainers: list[PolicyGroupTrainer] = list()
    group_idx: int

    for group_idx in range(len(group_names)):
        group_name: str = group_names[group_idx]
        policy_network: OperatorPolicyNetwork = build_policy_network_from_observation(
            observation=observation,
            branch_count=multi_agent_env.get_base_env().get_branch_count(),
            generator_count=multi_agent_env.get_base_env().get_generator_count(),
            config=multi_agent_env.get_base_env().get_config(),
            hidden_size=training_config.get_hidden_size(),
        )
        policy_network.to(device)
        optimizer: torch.optim.Optimizer = torch.optim.Adam(
            policy_network.parameters(),
            lr=training_config.get_learning_rate(),
        )
        group_trainers.append(
            PolicyGroupTrainer(
                policy_group=group_name,
                policy_network=policy_network,
                optimizer=optimizer,
            )
        )

    return group_trainers


def collect_unique_policy_groups(agent_specs: list[AgentSpec]) -> list[str]:
    """
    Collect unique policy group names while preserving first appearance order.

    :param agent_specs:
        Ordered agent specification list.
    :return:
        Ordered unique policy group names.
    """

    group_names: list[str] = list()
    group_name_set: set[str] = set()
    agent_idx: int

    for agent_idx in range(len(agent_specs)):
        group_name: str = agent_specs[agent_idx].get_policy_group()
        if group_name in group_name_set:
            agent_idx = agent_idx
        else:
            group_name_set.add(group_name)
            group_names.append(group_name)

    return group_names


def collect_multi_agent_episode(
    multi_agent_env: MultiAgentOperatorEnv,
    group_trainers: list[PolicyGroupTrainer],
    max_turns: int,
    device: torch.device,
) -> list[MultiAgentEpisodeStep]:
    """
    Collect one multi-agent trajectory.

    :param multi_agent_env:
        Multi-agent environment.
    :param group_trainers:
        Policy group trainers.
    :param max_turns:
        Maximum number of turns in the episode.
    :param device:
        Torch device.
    :return:
        Multi-agent trajectory.
    """

    reset_payload = multi_agent_env.reset()
    observation: ObservationData = reset_payload.get_observation()
    trajectory: list[MultiAgentEpisodeStep] = list()
    turn_idx: int

    for turn_idx in range(max_turns):
        acting_agent: AgentSpec = multi_agent_env.get_active_agent()
        group_trainer: PolicyGroupTrainer = find_group_trainer(
            group_trainers=group_trainers,
            policy_group=acting_agent.get_policy_group(),
        )
        action_sample: PolicyActionSample
        action_sample, _ = sample_action_with_policy(
            policy_network=group_trainer.get_policy_network(),
            observation=observation,
            branch_count=multi_agent_env.get_base_env().get_branch_count(),
            generator_count=multi_agent_env.get_base_env().get_generator_count(),
            device=device,
        )
        next_observation: ObservationData
        reward: float
        terminated: bool
        truncated: bool
        step_info: MultiAgentStepInfo
        next_observation, reward, terminated, truncated, step_info = multi_agent_env.step(action_sample.get_action())
        trajectory.append(
            MultiAgentEpisodeStep(
                acting_agent=acting_agent,
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
            turn_idx = turn_idx

    return trajectory


def find_group_trainer(group_trainers: list[PolicyGroupTrainer], policy_group: str) -> PolicyGroupTrainer:
    """
    Find the trainer bundle for one logical policy group.

    :param group_trainers:
        Available policy group trainers.
    :param policy_group:
        Logical policy group name.
    :return:
        Matching trainer bundle.
    """

    trainer_idx: int

    for trainer_idx in range(len(group_trainers)):
        if group_trainers[trainer_idx].get_policy_group() == policy_group:
            return group_trainers[trainer_idx]
        else:
            trainer_idx = trainer_idx

    raise ValueError(f"Missing policy group trainer for policy_group={policy_group}")


def update_all_policy_groups(
    trajectory: list[MultiAgentEpisodeStep],
    group_trainers: list[PolicyGroupTrainer],
    gamma: float,
    value_loss_weight: float,
    entropy_weight: float,
    device: torch.device,
) -> list[PolicyGroupSummary]:
    """
    Update every policy group from the turns attributed to that group.

    :param trajectory:
        Full multi-agent trajectory.
    :param group_trainers:
        Policy group trainers.
    :param gamma:
        Discount factor.
    :param value_loss_weight:
        Critic loss coefficient.
    :param entropy_weight:
        Entropy coefficient.
    :param device:
        Torch device.
    :return:
        One summary per policy group.
    """

    group_summaries: list[PolicyGroupSummary] = list()
    trainer_idx: int

    for trainer_idx in range(len(group_trainers)):
        group_trainer: PolicyGroupTrainer = group_trainers[trainer_idx]
        group_steps: list[MultiAgentEpisodeStep] = filter_steps_for_policy_group(
            trajectory=trajectory,
            policy_group=group_trainer.get_policy_group(),
        )
        group_summary: PolicyGroupSummary = update_single_policy_group(
            group_steps=group_steps,
            group_trainer=group_trainer,
            gamma=gamma,
            value_loss_weight=value_loss_weight,
            entropy_weight=entropy_weight,
            device=device,
        )
        group_summaries.append(group_summary)

    return group_summaries


def filter_steps_for_policy_group(
    trajectory: list[MultiAgentEpisodeStep],
    policy_group: str,
) -> list[MultiAgentEpisodeStep]:
    """
    Filter a trajectory down to the turns taken by one policy group.

    :param trajectory:
        Full multi-agent trajectory.
    :param policy_group:
        Logical policy group name.
    :return:
        Filtered trajectory steps.
    """

    group_steps: list[MultiAgentEpisodeStep] = list()
    step_idx: int

    for step_idx in range(len(trajectory)):
        step_policy_group: str = trajectory[step_idx].get_acting_agent().get_policy_group()
        if step_policy_group == policy_group:
            group_steps.append(trajectory[step_idx])
        else:
            step_idx = step_idx

    return group_steps


def update_single_policy_group(
    group_steps: list[MultiAgentEpisodeStep],
    group_trainer: PolicyGroupTrainer,
    gamma: float,
    value_loss_weight: float,
    entropy_weight: float,
    device: torch.device,
) -> PolicyGroupSummary:
    """
    Update one policy group from its own turns.

    :param group_steps:
        Steps attributed to the policy group.
    :param group_trainer:
        Trainable policy bundle.
    :param gamma:
        Discount factor.
    :param value_loss_weight:
        Critic loss coefficient.
    :param entropy_weight:
        Entropy coefficient.
    :param device:
        Torch device.
    :return:
        Policy group update summary.
    """

    step_count: int = len(group_steps)

    if step_count > 0:
        returns_tensor: torch.Tensor = compute_group_discounted_returns(group_steps, gamma, device)
        log_prob_tensor: torch.Tensor = torch.empty(step_count, dtype=torch.float32, device=device)
        value_tensor: torch.Tensor = torch.empty(step_count, dtype=torch.float32, device=device)
        entropy_tensor: torch.Tensor = torch.empty(step_count, dtype=torch.float32, device=device)
        total_reward: float = 0.0
        step_idx: int

        for step_idx in range(step_count):
            log_prob_tensor[step_idx] = group_steps[step_idx].get_action_sample().get_log_prob()
            value_tensor[step_idx] = group_steps[step_idx].get_action_sample().get_value()
            entropy_tensor[step_idx] = group_steps[step_idx].get_action_sample().get_entropy()
            total_reward += group_steps[step_idx].get_reward()

        advantage_tensor: torch.Tensor = returns_tensor - value_tensor.detach()
        actor_loss: torch.Tensor = -(log_prob_tensor * advantage_tensor).mean()
        value_loss: torch.Tensor = value_loss_weight * nn.functional.mse_loss(value_tensor, returns_tensor)
        entropy_bonus: torch.Tensor = entropy_weight * entropy_tensor.mean()

        optimizer: torch.optim.Optimizer = group_trainer.get_optimizer()
        optimizer.zero_grad()
        total_loss: torch.Tensor = actor_loss + value_loss - entropy_bonus
        total_loss.backward()
        optimizer.step()

        return PolicyGroupSummary(
            policy_group=group_trainer.get_policy_group(),
            step_count=step_count,
            total_reward=total_reward,
            actor_loss=float(actor_loss.detach().cpu().item()),
            value_loss=float(value_loss.detach().cpu().item()),
            entropy=float(entropy_bonus.detach().cpu().item()),
        )
    else:
        return PolicyGroupSummary(
            policy_group=group_trainer.get_policy_group(),
            step_count=0,
            total_reward=0.0,
            actor_loss=0.0,
            value_loss=0.0,
            entropy=0.0,
        )


def compute_group_discounted_returns(
    group_steps: list[MultiAgentEpisodeStep],
    gamma: float,
    device: torch.device,
) -> torch.Tensor:
    """
    Compute discounted returns for one policy group trajectory.

    :param group_steps:
        Filtered policy group trajectory.
    :param gamma:
        Discount factor.
    :param device:
        Torch device.
    :return:
        Discounted return tensor.
    """

    step_count: int = len(group_steps)
    returns_tensor: torch.Tensor = torch.empty(step_count, dtype=torch.float32, device=device)
    running_return: float = 0.0
    reverse_idx: int

    for reverse_idx in range(step_count - 1, -1, -1):
        running_return = group_steps[reverse_idx].get_reward() + gamma * running_return
        returns_tensor[reverse_idx] = running_return

    return returns_tensor


def ensure_multi_agent_checkpoint_dir(checkpoint_dir: str) -> None:
    """
    Ensure that the multi-agent checkpoint directory exists.

    :param checkpoint_dir:
        Checkpoint directory path.
    :return:
        ``None``.
    """

    if os.path.isdir(checkpoint_dir):
        checkpoint_dir = checkpoint_dir
    else:
        os.makedirs(checkpoint_dir, exist_ok=True)


def should_save_multi_agent_checkpoint(episode_idx: int, checkpoint_interval: int) -> bool:
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


def save_multi_agent_checkpoint(
    group_trainers: list[PolicyGroupTrainer],
    episode_idx: int,
    checkpoint_dir: str,
) -> str:
    """
    Save a multi-agent checkpoint containing every policy group.

    :param group_trainers:
        Policy group trainers.
    :param episode_idx:
        Episode index starting at one.
    :param checkpoint_dir:
        Checkpoint directory path.
    :return:
        Saved checkpoint path.
    """

    checkpoint_path: str = os.path.join(checkpoint_dir, f"multi_agent_episode_{episode_idx:05d}.pt")
    checkpoint_data: dict[str, Any] = dict()
    checkpoint_data["episode_idx"] = episode_idx
    checkpoint_data["policy_groups"] = list()
    trainer_idx: int

    for trainer_idx in range(len(group_trainers)):
        trainer: PolicyGroupTrainer = group_trainers[trainer_idx]
        group_state: dict[str, Any] = dict()
        group_state["policy_group"] = trainer.get_policy_group()
        group_state["model_state_dict"] = trainer.get_policy_network().state_dict()
        group_state["optimizer_state_dict"] = trainer.get_optimizer().state_dict()
        checkpoint_data["policy_groups"].append(group_state)

    torch.save(checkpoint_data, checkpoint_path)
    return checkpoint_path


def print_multi_agent_episode_summary(episode_summary: MultiAgentEpisodeSummary) -> None:
    """
    Print a compact episode summary for all policy groups.

    :param episode_summary:
        Episode summary to print.
    :return:
        ``None``.
    """

    print(f"episode={episode_summary.get_episode_idx()} turns={episode_summary.get_turn_count()}")
    group_summaries: list[PolicyGroupSummary] = episode_summary.get_group_summaries()
    group_idx: int

    for group_idx in range(len(group_summaries)):
        group_summary: PolicyGroupSummary = group_summaries[group_idx]
        print(
            f"policy_group={group_summary.get_policy_group()} "
            f"steps={group_summary.get_step_count()} "
            f"reward={group_summary.get_total_reward():.3f} "
            f"actor_loss={group_summary.get_actor_loss():.6f} "
            f"value_loss={group_summary.get_value_loss():.6f} "
            f"entropy={group_summary.get_entropy():.6f}"
        )
