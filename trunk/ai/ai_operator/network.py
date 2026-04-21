from __future__ import annotations

from typing import Any

import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical
from torch.distributions import Normal

from trunk.ai.ai_operator.actions import ActionCategory
from trunk.ai.ai_operator.actions import BranchSwitchAction
from trunk.ai.ai_operator.actions import GeneratorRedispatchAction
from trunk.ai.ai_operator.actions import OperatorAction
from trunk.ai.ai_operator.config import OperatorEnvConfig
from trunk.ai.ai_operator.observations import ObservationData
from trunk.ai.ai_operator.observations import flatten_observation


class OperatorPolicyOutput:
    """
    Structured neural network output for one operator decision.

    :param category_logits:
        Logits over action categories.
    :param branch_idx_logits:
        Logits over branch target indices.
    :param branch_command_logits:
        Logits over branch commands, where index ``0`` is open and ``1`` is close.
    :param generator_idx_logits:
        Logits over generator target indices.
    :param generator_delta:
        Continuous redispatch amount prediction in MW.
    :param value:
        State value estimate used by actor-critic algorithms.
    """

    __slots__ = (
        "_category_logits",
        "_branch_idx_logits",
        "_branch_command_logits",
        "_generator_idx_logits",
        "_generator_delta",
        "_value",
    )

    def __init__(
        self,
        category_logits: torch.Tensor,
        branch_idx_logits: torch.Tensor,
        branch_command_logits: torch.Tensor,
        generator_idx_logits: torch.Tensor,
        generator_delta: torch.Tensor,
        value: torch.Tensor,
    ) -> None:
        self._category_logits: torch.Tensor = category_logits
        self._branch_idx_logits: torch.Tensor = branch_idx_logits
        self._branch_command_logits: torch.Tensor = branch_command_logits
        self._generator_idx_logits: torch.Tensor = generator_idx_logits
        self._generator_delta: torch.Tensor = generator_delta
        self._value: torch.Tensor = value

    def get_category_logits(self) -> torch.Tensor:
        """
        Get the category logits.

        :return:
            Category logits tensor.
        """

        return self._category_logits

    def get_branch_idx_logits(self) -> torch.Tensor:
        """
        Get the branch index logits.

        :return:
            Branch index logits tensor.
        """

        return self._branch_idx_logits

    def get_branch_command_logits(self) -> torch.Tensor:
        """
        Get the branch command logits.

        :return:
            Branch command logits tensor.
        """

        return self._branch_command_logits

    def get_generator_idx_logits(self) -> torch.Tensor:
        """
        Get the generator index logits.

        :return:
            Generator index logits tensor.
        """

        return self._generator_idx_logits

    def get_generator_delta(self) -> torch.Tensor:
        """
        Get the generator redispatch output.

        :return:
            Generator redispatch tensor in MW.
        """

        return self._generator_delta

    def get_value(self) -> torch.Tensor:
        """
        Get the state value estimate.

        :return:
            Value tensor.
        """

        return self._value


class PolicyActionSample:
    """
    Structured sampled policy action information.

    :param action:
        Concrete environment action decoded from the policy.
    :param log_prob:
        Joint log probability of the sampled action.
    :param value:
        Value prediction for the sampled state.
    :param entropy:
        Entropy proxy for the sampled decision.
    """

    __slots__ = ("_action", "_log_prob", "_value", "_entropy")

    def __init__(
        self,
        action: OperatorAction,
        log_prob: torch.Tensor,
        value: torch.Tensor,
        entropy: torch.Tensor,
    ) -> None:
        self._action: OperatorAction = action
        self._log_prob: torch.Tensor = log_prob
        self._value: torch.Tensor = value
        self._entropy: torch.Tensor = entropy

    def get_action(self) -> OperatorAction:
        """
        Get the sampled environment action.

        :return:
            Concrete operator action.
        """

        return self._action

    def get_log_prob(self) -> torch.Tensor:
        """
        Get the sampled joint log probability.

        :return:
            Scalar log probability tensor.
        """

        return self._log_prob

    def get_value(self) -> torch.Tensor:
        """
        Get the state value prediction.

        :return:
            Scalar value tensor.
        """

        return self._value

    def get_entropy(self) -> torch.Tensor:
        """
        Get the policy entropy contribution.

        :return:
            Scalar entropy tensor.
        """

        return self._entropy


class OperatorPolicyNetwork(nn.Module):
    """
    Split-head policy network for sequential grid operator actions.

    :param observation_size:
        Flattened observation vector size.
    :param branch_count:
        Number of controllable branches.
    :param generator_count:
        Number of controllable generators.
    :param hidden_size:
        Width of the shared multilayer perceptron trunk.
    :param generator_delta_mw:
        Maximum redispatch magnitude represented by the policy output.
    """

    __slots__ = (
        "_observation_size",
        "_branch_count",
        "_generator_count",
        "_hidden_size",
        "_generator_delta_mw",
        "_input_layer",
        "_hidden_layer",
        "_category_head",
        "_branch_idx_head",
        "_branch_command_head",
        "_generator_idx_head",
        "_generator_delta_head",
        "_generator_delta_log_std",
        "_value_head",
    )

    def __init__(
        self,
        observation_size: int,
        branch_count: int,
        generator_count: int,
        hidden_size: int = 256,
        generator_delta_mw: float = 10.0,
    ) -> None:
        super().__init__()

        self._observation_size: int = observation_size
        self._branch_count: int = max(branch_count, 1)
        self._generator_count: int = max(generator_count, 1)
        self._hidden_size: int = hidden_size
        self._generator_delta_mw: float = generator_delta_mw

        # The shared trunk builds one latent state embedding from the full PF observation.
        # The separate heads then specialize that shared embedding into the structured
        # decisions required by the operator control problem.
        self._input_layer: nn.Linear = nn.Linear(self._observation_size, self._hidden_size)
        self._hidden_layer: nn.Linear = nn.Linear(self._hidden_size, self._hidden_size)
        self._category_head: nn.Linear = nn.Linear(self._hidden_size, 2)
        self._branch_idx_head: nn.Linear = nn.Linear(self._hidden_size, self._branch_count)
        self._branch_command_head: nn.Linear = nn.Linear(self._hidden_size, 2)
        self._generator_idx_head: nn.Linear = nn.Linear(self._hidden_size, self._generator_count)
        self._generator_delta_head: nn.Linear = nn.Linear(self._hidden_size, 1)
        self._generator_delta_log_std: nn.Parameter = nn.Parameter(torch.zeros(1, dtype=torch.float32))
        self._value_head: nn.Linear = nn.Linear(self._hidden_size, 1)

    def forward(self, observation_tensor: torch.Tensor) -> OperatorPolicyOutput:
        """
        Compute the policy heads for a batch of observations.

        :param observation_tensor:
            Dense observation tensor with shape ``[batch, observation_size]``.
        :return:
            Structured output bundle with policy logits and value estimate.
        """

        # The first affine stage projects the dense PF features into a latent space
        # where the network can mix voltage, loading, topology, and generation signals.
        hidden_state: torch.Tensor = self._input_layer(observation_tensor)
        hidden_state = torch.relu(hidden_state)

        # The second affine stage deepens the shared representation so the downstream
        # heads can specialize without having to relearn the basic grid state encoding.
        hidden_state = self._hidden_layer(hidden_state)
        hidden_state = torch.relu(hidden_state)

        # Each head predicts one part of the structured operator action.
        category_logits: torch.Tensor = self._category_head(hidden_state)
        branch_idx_logits: torch.Tensor = self._branch_idx_head(hidden_state)
        branch_command_logits: torch.Tensor = self._branch_command_head(hidden_state)
        generator_idx_logits: torch.Tensor = self._generator_idx_head(hidden_state)
        generator_delta_raw: torch.Tensor = self._generator_delta_head(hidden_state)
        generator_delta: torch.Tensor = torch.tanh(generator_delta_raw) * self._generator_delta_mw
        value: torch.Tensor = self._value_head(hidden_state)

        return OperatorPolicyOutput(
            category_logits=category_logits,
            branch_idx_logits=branch_idx_logits,
            branch_command_logits=branch_command_logits,
            generator_idx_logits=generator_idx_logits,
            generator_delta=generator_delta,
            value=value,
        )


def build_policy_network_from_observation(
    observation: ObservationData,
    branch_count: int,
    generator_count: int,
    config: OperatorEnvConfig,
    hidden_size: int = 256,
) -> OperatorPolicyNetwork:
    """
    Build a policy network sized for a concrete operator environment.

    :param observation:
        Example observation used to infer the flattened observation size.
    :param branch_count:
        Number of controllable branches.
    :param generator_count:
        Number of controllable generators.
    :param config:
        Environment configuration bundle.
    :param hidden_size:
        Shared hidden layer width.
    :return:
        Policy network instance.
    """

    # The network size is inferred from a real observation so the policy architecture
    # always matches the exact grid state vector assembled by the environment.
    observation_vector: np.ndarray = flatten_observation(observation)
    observation_size: int = int(observation_vector.size)
    return OperatorPolicyNetwork(
        observation_size=observation_size,
        branch_count=branch_count,
        generator_count=generator_count,
        hidden_size=hidden_size,
        generator_delta_mw=config.get_generator_delta_mw(),
    )


def observation_to_tensor(observation: ObservationData, device: torch.device | None = None) -> torch.Tensor:
    """
    Convert one observation into a batch tensor.

    :param observation:
        Structured observation object.
    :param device:
        Optional Torch device.
    :return:
        Tensor with shape ``[1, observation_size]``.
    """

    # The network consumes dense tensors, so the typed observation must be flattened
    # and wrapped in a batch dimension before inference.
    observation_vector: np.ndarray = flatten_observation(observation)
    batch_array: np.ndarray = observation_vector.reshape(1, observation_vector.size)

    if device is None:
        tensor_device: torch.device = torch.device("cpu")
    else:
        tensor_device = device

    return torch.as_tensor(batch_array, dtype=torch.float32, device=tensor_device)


def decode_policy_output_to_action(
    policy_output: OperatorPolicyOutput,
    branch_count: int,
    generator_count: int,
) -> OperatorAction:
    """
    Decode one policy output into a concrete operator action.

    :param policy_output:
        Neural network output bundle.
    :param branch_count:
        Number of controllable branches.
    :param generator_count:
        Number of controllable generators.
    :return:
        Decoded operator action.
    """

    # The category head first chooses the control family. The corresponding target head
    # and parameter head then produce the final actuator command.
    category_idx_tensor: torch.Tensor = torch.argmax(policy_output.get_category_logits(), dim=1)
    category_idx: int = int(category_idx_tensor[0].item())

    if category_idx == 0:
        if branch_count > 0:
            branch_idx_tensor: torch.Tensor = torch.argmax(policy_output.get_branch_idx_logits(), dim=1)
            branch_idx: int = int(branch_idx_tensor[0].item())
            branch_idx = min(max(branch_idx, 0), branch_count - 1)

            branch_command_tensor: torch.Tensor = torch.argmax(policy_output.get_branch_command_logits(), dim=1)
            branch_command_idx: int = int(branch_command_tensor[0].item())
            closed: bool
            if branch_command_idx == 1:
                closed = True
            else:
                closed = False

            return BranchSwitchAction(branch_idx=branch_idx, closed=closed)
        else:
            if generator_count > 0:
                generator_idx_tensor = torch.argmax(policy_output.get_generator_idx_logits(), dim=1)
                generator_idx: int = int(generator_idx_tensor[0].item())
                generator_idx = min(max(generator_idx, 0), generator_count - 1)
                delta_value: float = float(policy_output.get_generator_delta()[0, 0].item())
                return GeneratorRedispatchAction(generator_idx=generator_idx, delta_mw=delta_value)
            else:
                return BranchSwitchAction(branch_idx=0, closed=False)
    else:
        if generator_count > 0:
            generator_idx_tensor = torch.argmax(policy_output.get_generator_idx_logits(), dim=1)
            generator_idx = int(generator_idx_tensor[0].item())
            generator_idx = min(max(generator_idx, 0), generator_count - 1)
            delta_value = float(policy_output.get_generator_delta()[0, 0].item())
            return GeneratorRedispatchAction(generator_idx=generator_idx, delta_mw=delta_value)
        else:
            if branch_count > 0:
                branch_idx_tensor = torch.argmax(policy_output.get_branch_idx_logits(), dim=1)
                branch_idx = int(branch_idx_tensor[0].item())
                branch_idx = min(max(branch_idx, 0), branch_count - 1)
                branch_command_tensor = torch.argmax(policy_output.get_branch_command_logits(), dim=1)
                branch_command_idx = int(branch_command_tensor[0].item())
                closed = True if branch_command_idx == 1 else False
                return BranchSwitchAction(branch_idx=branch_idx, closed=closed)
            else:
                return BranchSwitchAction(branch_idx=0, closed=False)


def select_action_with_policy(
    policy_network: OperatorPolicyNetwork,
    observation: ObservationData,
    branch_count: int,
    generator_count: int,
    device: torch.device | None = None,
) -> tuple[OperatorAction, OperatorPolicyOutput]:
    """
    Run one policy inference step and decode the resulting operator action.

    :param policy_network:
        Operator policy network.
    :param observation:
        Structured environment observation.
    :param branch_count:
        Number of controllable branches.
    :param generator_count:
        Number of controllable generators.
    :param device:
        Optional Torch device.
    :return:
        Decoded operator action and raw policy output.
    """

    # The tensor conversion keeps inference separate from the environment logic,
    # which makes it easier to replace the policy backend later.
    observation_tensor: torch.Tensor = observation_to_tensor(observation, device=device)

    # Gradients are not needed for action selection during rollout, so inference runs
    # under no_grad to reduce overhead and keep the code path explicit.
    with torch.no_grad():
        policy_output: OperatorPolicyOutput = policy_network(observation_tensor)

    action: OperatorAction = decode_policy_output_to_action(
        policy_output=policy_output,
        branch_count=branch_count,
        generator_count=generator_count,
    )
    return action, policy_output


def sample_action_with_policy(
    policy_network: OperatorPolicyNetwork,
    observation: ObservationData,
    branch_count: int,
    generator_count: int,
    device: torch.device | None = None,
) -> tuple[PolicyActionSample, OperatorPolicyOutput]:
    """
    Sample one stochastic operator action from the policy.

    :param policy_network:
        Operator policy network.
    :param observation:
        Structured environment observation.
    :param branch_count:
        Number of controllable branches.
    :param generator_count:
        Number of controllable generators.
    :param device:
        Optional Torch device.
    :return:
        Sampled action bundle and raw policy output.
    """

    # The stochastic sampler is used during training so the algorithm can explore
    # the control space rather than following a deterministic greedy decoder.
    observation_tensor: torch.Tensor = observation_to_tensor(observation, device=device)
    policy_output: OperatorPolicyOutput = policy_network(observation_tensor)
    category_distribution: Categorical = Categorical(logits=policy_output.get_category_logits())
    category_tensor: torch.Tensor = category_distribution.sample()
    category_idx: int = int(category_tensor[0].item())

    log_prob: torch.Tensor = category_distribution.log_prob(category_tensor)[0]
    entropy: torch.Tensor = category_distribution.entropy()[0]
    value: torch.Tensor = policy_output.get_value()[0, 0]

    if category_idx == 0 and branch_count > 0:
        branch_distribution: Categorical = Categorical(logits=policy_output.get_branch_idx_logits()[:, :branch_count])
        branch_idx_tensor: torch.Tensor = branch_distribution.sample()
        branch_idx: int = int(branch_idx_tensor[0].item())
        log_prob = log_prob + branch_distribution.log_prob(branch_idx_tensor)[0]
        entropy = entropy + branch_distribution.entropy()[0]

        command_distribution: Categorical = Categorical(logits=policy_output.get_branch_command_logits())
        command_tensor: torch.Tensor = command_distribution.sample()
        command_idx: int = int(command_tensor[0].item())
        log_prob = log_prob + command_distribution.log_prob(command_tensor)[0]
        entropy = entropy + command_distribution.entropy()[0]

        closed: bool = True if command_idx == 1 else False
        action: OperatorAction = BranchSwitchAction(branch_idx=branch_idx, closed=closed)
    else:
        if generator_count > 0:
            generator_distribution: Categorical = Categorical(
                logits=policy_output.get_generator_idx_logits()[:, :generator_count]
            )
            generator_idx_tensor: torch.Tensor = generator_distribution.sample()
            generator_idx: int = int(generator_idx_tensor[0].item())
            log_prob = log_prob + generator_distribution.log_prob(generator_idx_tensor)[0]
            entropy = entropy + generator_distribution.entropy()[0]

            delta_mean: torch.Tensor = policy_output.get_generator_delta()[0, 0]
            delta_std: torch.Tensor = torch.exp(policy_network._generator_delta_log_std)[0]
            delta_distribution: Normal = Normal(delta_mean, delta_std)
            delta_tensor: torch.Tensor = delta_distribution.rsample()
            delta_limit: float = float(policy_network._generator_delta_mw)
            delta_value: float = float(torch.clamp(delta_tensor, -delta_limit, delta_limit).item())
            log_prob = log_prob + delta_distribution.log_prob(delta_tensor)
            entropy = entropy + delta_distribution.entropy()

            action = GeneratorRedispatchAction(generator_idx=generator_idx, delta_mw=delta_value)
        else:
            # This fallback keeps the training loop alive even for degenerate grids
            # that expose no controllable equipment.
            action = BranchSwitchAction(branch_idx=0, closed=False)

    sample: PolicyActionSample = PolicyActionSample(
        action=action,
        log_prob=log_prob,
        value=value,
        entropy=entropy,
    )
    return sample, policy_output


def category_from_index(category_idx: int) -> ActionCategory:
    """
    Translate a category index into the action category enum.

    :param category_idx:
        Category index from the policy logits.
    :return:
        Action category enum value.
    """

    if category_idx == 0:
        return ActionCategory.BRANCH_SWITCH
    else:
        return ActionCategory.GENERATOR_REDISPATCH
