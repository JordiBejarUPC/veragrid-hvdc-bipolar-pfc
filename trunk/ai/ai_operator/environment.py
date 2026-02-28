from __future__ import annotations

from typing import Any

import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc

from trunk.ai.ai_operator.actions import BranchSwitchAction
from trunk.ai.ai_operator.actions import GeneratorRedispatchAction
from trunk.ai.ai_operator.actions import OperatorAction
from trunk.ai.ai_operator.config import OperatorEnvConfig
from trunk.ai.ai_operator.observations import ObservationData
from trunk.ai.ai_operator.observations import build_observation
from trunk.ai.ai_operator.observations import flatten_observation
from trunk.ai.ai_operator.reward import RewardBreakdown
from trunk.ai.ai_operator.reward import compute_reward


class StepInfo:
    """
    Step metadata bundle.

    :param pf_converged:
        ``True`` when the post-action power flow converged.
    :param reward_breakdown:
        Reward term breakdown for inspection.
    :param flat_observation:
        Dense vector representation of the observation.
    :param action_applied:
        ``True`` when the control command was accepted by the environment.
    """

    __slots__ = ("_pf_converged", "_reward_breakdown", "_flat_observation", "_action_applied")

    def __init__(
        self,
        pf_converged: bool,
        reward_breakdown: RewardBreakdown,
        flat_observation: np.ndarray,
        action_applied: bool,
    ) -> None:
        self._pf_converged: bool = pf_converged
        self._reward_breakdown: RewardBreakdown = reward_breakdown
        self._flat_observation: np.ndarray = flat_observation
        self._action_applied: bool = action_applied

    def get_pf_converged(self) -> bool:
        """
        Get the convergence flag.

        :return:
            ``True`` when the PF converged.
        """

        return self._pf_converged

    def get_reward_breakdown(self) -> RewardBreakdown:
        """
        Get the reward breakdown.

        :return:
            Reward breakdown object.
        """

        return self._reward_breakdown

    def get_flat_observation(self) -> np.ndarray:
        """
        Get the flattened observation.

        :return:
            Flat observation vector.
        """

        return self._flat_observation

    def get_action_applied(self) -> bool:
        """
        Get the action application flag.

        :return:
            ``True`` when the command was applied.
        """

        return self._action_applied


class VeraGridOperatorEnv:
    """
    Sequential operator environment for reinforcement learning experiments.

    :param grid:
        VeraGrid grid object to be controlled by the agent.
    :param config:
        Environment configuration bundle. When ``None``, defaults are used.
    """

    __slots__ = (
        "_grid",
        "_config",
        "_pf_options",
        "_step_idx",
        "_latest_nc",
        "_latest_pf_results",
    )

    def __init__(self, grid: Any, config: OperatorEnvConfig | None = None) -> None:
        config_obj: OperatorEnvConfig
        if config is None:
            config_obj = OperatorEnvConfig()
        else:
            config_obj = config

        self._grid: Any = grid
        self._config: OperatorEnvConfig = config_obj
        self._pf_options: Any = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
        self._step_idx: int = 0
        self._latest_nc: Any = None
        self._latest_pf_results: Any = None

    def get_branch_count(self) -> int:
        """
        Get the number of branches.

        :return:
            Number of branches in the current grid.
        """

        branches: Any = self._grid.get_branches()
        return len(branches)

    def get_generator_count(self) -> int:
        """
        Get the number of generators.

        :return:
            Number of generators in the current grid.
        """

        generators: Any = self._grid.get_generators()
        return len(generators)

    def get_step_idx(self) -> int:
        """
        Get the current environment step index.

        :return:
            Current step index.
        """

        return self._step_idx

    def get_config(self) -> OperatorEnvConfig:
        """
        Get the environment configuration bundle.

        :return:
            Environment configuration object.
        """

        return self._config

    def reset(self) -> ObservationData:
        """
        Reset the environment to the current grid initial state.

        :return:
            Initial observation after solving the base PF.
        """

        # The reset starts a new episode by clearing the loop counter and solving
        # the PF for the current grid state before the first control decision.
        self._step_idx = 0
        nc: Any
        pf_results: Any
        nc, pf_results = run_power_flow(self._grid, self._pf_options)
        self._latest_nc = nc
        self._latest_pf_results = pf_results

        return build_observation(
            nc=nc,
            pf_results=pf_results,
            step_idx=self._step_idx,
            max_steps=self._config.get_max_steps(),
        )

    def step(self, action: OperatorAction) -> tuple[ObservationData, float, bool, bool, StepInfo]:
        """
        Apply one operator action and solve the next power flow.

        :param action:
            Operator action to apply at the current iteration.
        :return:
            Observation, reward, terminated, truncated, and step metadata.
        """

        # The action application stage changes one actuator in the physical model.
        # The PF stage then propagates that action into the network electrical state.
        action_applied: bool = apply_action_to_grid(self._grid, action, self._config)
        nc: Any
        pf_results: Any
        nc, pf_results = run_power_flow(self._grid, self._pf_options)
        self._latest_nc = nc
        self._latest_pf_results = pf_results
        self._step_idx += 1

        # The reward and termination are computed on the post-action state so the agent
        # learns the true impact of each control move on network security.
        pf_converged: bool = power_flow_converged(pf_results)
        observation: ObservationData = build_observation(
            nc=nc,
            pf_results=pf_results,
            step_idx=self._step_idx,
            max_steps=self._config.get_max_steps(),
        )
        reward_breakdown: RewardBreakdown = compute_reward(
            nc=nc,
            pf_results=pf_results,
            action=action,
            weights=self._config.get_reward_weights(),
            pf_converged=pf_converged,
        )
        reward_value: float = reward_breakdown.get_total_reward()
        terminated: bool = compute_terminated(nc, pf_results, pf_converged, self._config)
        truncated: bool = self._step_idx >= self._config.get_max_steps()
        flat_observation: np.ndarray = flatten_observation(observation)
        step_info: StepInfo = StepInfo(
            pf_converged=pf_converged,
            reward_breakdown=reward_breakdown,
            flat_observation=flat_observation,
            action_applied=action_applied,
        )

        return observation, reward_value, terminated, truncated, step_info

    def sample_action(self, rng: np.random.Generator | None = None) -> OperatorAction:
        """
        Sample a baseline random action.

        :param rng:
            Optional NumPy random generator.
        :return:
            Random branch switch or generator redispatch action.
        """

        rng_obj: np.random.Generator
        if rng is None:
            rng_obj = np.random.default_rng()
        else:
            rng_obj = rng

        branch_count: int = self.get_branch_count()
        generator_count: int = self.get_generator_count()

        if generator_count == 0:
            branch_idx: int = int(rng_obj.integers(0, max(branch_count, 1)))
            closed: bool = bool(rng_obj.integers(0, 2))
            return BranchSwitchAction(branch_idx=branch_idx, closed=closed)
        else:
            if branch_count > 0 and rng_obj.random() < 0.5:
                branch_idx = int(rng_obj.integers(0, branch_count))
                closed = bool(rng_obj.integers(0, 2))
                return BranchSwitchAction(branch_idx=branch_idx, closed=closed)
            else:
                generator_idx: int = int(rng_obj.integers(0, generator_count))
                delta_mw: float = float(
                    rng_obj.uniform(
                        -self._config.get_generator_delta_mw(),
                        self._config.get_generator_delta_mw(),
                    )
                )
                return GeneratorRedispatchAction(generator_idx=generator_idx, delta_mw=delta_mw)


def run_power_flow(grid: Any, pf_options: Any) -> tuple[Any, Any]:
    """
    Compile the current grid state and solve its power flow.

    :param grid:
        VeraGrid grid object.
    :param pf_options:
        Power flow options object.
    :return:
        Numerical circuit and PF results.
    """

    # The environment solves from the mutable grid model each step because actions
    # modify the device state directly and the compiled circuit must match it exactly.
    nc: Any = gce.compile_numerical_circuit_at(grid)
    pf_results: Any = multi_island_pf_nc(nc=nc, options=pf_options)
    return nc, pf_results


def power_flow_converged(pf_results: Any) -> bool:
    """
    Inspect the PF result convergence flag.

    :param pf_results:
        Power flow result object.
    :return:
        ``True`` when the solver converged or the flag is absent.
    """

    # Some VeraGrid result objects expose convergence as a scalar and others may
    # expose an array per island, so this function normalizes both cases.
    if hasattr(pf_results, "converged"):
        converged_value: Any = pf_results.converged
        if isinstance(converged_value, np.ndarray):
            return bool(np.all(converged_value))
        else:
            return bool(converged_value)
    else:
        return True


def apply_action_to_grid(grid: Any, action: OperatorAction, config: OperatorEnvConfig) -> bool:
    """
    Apply one operator action to the mutable grid state.

    :param grid:
        VeraGrid grid object.
    :param action:
        Action chosen by the agent.
    :param config:
        Environment configuration bundle.
    :return:
        ``True`` when the action was applied successfully.
    """

    # Invalid actions are handled as no-ops instead of exceptions because RL training
    # needs the environment to stay alive and punish bad actions through reward.
    if isinstance(action, BranchSwitchAction):
        return apply_branch_switch_action(grid, action)
    else:
        if isinstance(action, GeneratorRedispatchAction):
            return apply_generator_redispatch_action(grid, action, config)
        else:
            return False


def apply_branch_switch_action(grid: Any, action: BranchSwitchAction) -> bool:
    """
    Apply a branch open or close command.

    :param grid:
        VeraGrid grid object.
    :param action:
        Branch switching command.
    :return:
        ``True`` when the command was applied.
    """

    branches: Any = grid.get_branches()
    branch_count: int = len(branches)
    branch_idx: int = action.get_branch_idx()

    if 0 <= branch_idx < branch_count:
        branch: Any = branches[branch_idx]

        if hasattr(branch, "active"):
            branch.active = action.get_closed()
            return True
        else:
            if hasattr(branch, "enabled"):
                branch.enabled = action.get_closed()
                return True
            else:
                return False
    else:
        return False


def apply_generator_redispatch_action(
    grid: Any,
    action: GeneratorRedispatchAction,
    config: OperatorEnvConfig,
) -> bool:
    """
    Apply a generator active power setpoint move.

    :param grid:
        VeraGrid grid object.
    :param action:
        Generator redispatch command.
    :param config:
        Environment configuration bundle.
    :return:
        ``True`` when the command was applied.
    """

    generators: Any = grid.get_generators()
    generator_count: int = len(generators)
    generator_idx: int = action.get_generator_idx()

    if 0 <= generator_idx < generator_count:
        generator: Any = generators[generator_idx]

        if hasattr(generator, "P"):
            current_p: float = float(generator.P)
            new_p: float = current_p + action.get_delta_mw()

            if config.get_clip_generator_to_limits():
                if hasattr(generator, "Pmin") and hasattr(generator, "Pmax"):
                    pmin: float = float(generator.Pmin)
                    pmax: float = float(generator.Pmax)
                    new_p = max(pmin, min(pmax, new_p))
                else:
                    new_p = new_p
            else:
                new_p = new_p

            generator.P = new_p
            return True
        else:
            return False
    else:
        return False


def compute_terminated(
    nc: Any,
    pf_results: Any,
    pf_converged: bool,
    config: OperatorEnvConfig,
) -> bool:
    """
    Compute the episode termination flag.

    :param nc:
        Numerical circuit for the current grid state.
    :param pf_results:
        Power flow results.
    :param pf_converged:
        ``True`` when the PF converged.
    :param config:
        Environment configuration bundle.
    :return:
        ``True`` when the episode must terminate.
    """

    # Divergence is optionally terminal because some experiments want strict invalid-state
    # rejection, while others prefer to keep exploring after penalized solver failures.
    if (not pf_converged) and config.get_terminate_on_divergence():
        return True
    else:
        if config.get_terminate_on_security_violation():
            bus_voltage_magnitude: np.ndarray = np.abs(pf_results.voltage)
            bus_voltage_max: np.ndarray = nc.bus_data.Vmax
            bus_voltage_min: np.ndarray = nc.bus_data.Vmin
            branch_loading: np.ndarray = np.abs(pf_results.loading)
            branch_limits: np.ndarray = nc.passive_branch_data.contingency_rates
            return bool(
                np.any(bus_voltage_magnitude > bus_voltage_max)
                or np.any(bus_voltage_magnitude < bus_voltage_min)
                or np.any(branch_loading > branch_limits)
            )
        else:
            return False
