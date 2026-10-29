from __future__ import annotations


class RewardWeights:
    """
    Reward coefficient container.

    :param voltage_violation:
        Penalty weight for bus voltage limit violations.
    :param branch_overload:
        Penalty weight for branch overload violations.
    :param generator_limit:
        Penalty weight for generator active power limit violations.
    :param switching_cost:
        Penalty weight for each switching action.
    :param redispatch_cost:
        Penalty weight for each MW of redispatch magnitude.
    :param pf_divergence:
        Penalty weight applied when the power flow does not converge.
    :param secure_operation_bonus:
        Positive bonus when the resulting state has no violations.
    """

    __slots__ = (
        "_voltage_violation",
        "_branch_overload",
        "_generator_limit",
        "_switching_cost",
        "_redispatch_cost",
        "_pf_divergence",
        "_secure_operation_bonus",
    )

    def __init__(
        self,
        voltage_violation: float = 20.0,
        branch_overload: float = 15.0,
        generator_limit: float = 10.0,
        switching_cost: float = 0.5,
        redispatch_cost: float = 0.05,
        pf_divergence: float = 200.0,
        secure_operation_bonus: float = 5.0,
    ) -> None:
        self._voltage_violation: float = voltage_violation
        self._branch_overload: float = branch_overload
        self._generator_limit: float = generator_limit
        self._switching_cost: float = switching_cost
        self._redispatch_cost: float = redispatch_cost
        self._pf_divergence: float = pf_divergence
        self._secure_operation_bonus: float = secure_operation_bonus

    def get_voltage_violation(self) -> float:
        """
        Get the voltage violation weight.

        :return:
            Voltage violation penalty weight.
        """

        return self._voltage_violation

    def get_branch_overload(self) -> float:
        """
        Get the branch overload weight.

        :return:
            Branch overload penalty weight.
        """

        return self._branch_overload

    def get_generator_limit(self) -> float:
        """
        Get the generator limit weight.

        :return:
            Generator limit penalty weight.
        """

        return self._generator_limit

    def get_switching_cost(self) -> float:
        """
        Get the switching action weight.

        :return:
            Switching cost penalty weight.
        """

        return self._switching_cost

    def get_redispatch_cost(self) -> float:
        """
        Get the redispatch action weight.

        :return:
            Redispatch cost penalty weight.
        """

        return self._redispatch_cost

    def get_pf_divergence(self) -> float:
        """
        Get the PF divergence weight.

        :return:
            PF divergence penalty weight.
        """

        return self._pf_divergence

    def get_secure_operation_bonus(self) -> float:
        """
        Get the secure operation bonus.

        :return:
            Positive secure-state reward.
        """

        return self._secure_operation_bonus


class OperatorEnvConfig:
    """
    Environment configuration container.

    :param max_steps:
        Maximum number of control iterations before truncation.
    :param generator_delta_mw:
        Maximum absolute redispatch magnitude used by the baseline sampler.
    :param clip_generator_to_limits:
        Clip generator redispatch commands to the device active power limits.
    :param terminate_on_divergence:
        End the episode when the PF solver does not converge.
    :param terminate_on_security_violation:
        End the episode when the resulting state violates security limits.
    :param reward_weights:
        Reward coefficient bundle.
    """

    __slots__ = (
        "_max_steps",
        "_generator_delta_mw",
        "_clip_generator_to_limits",
        "_terminate_on_divergence",
        "_terminate_on_security_violation",
        "_reward_weights",
    )

    def __init__(
        self,
        max_steps: int = 50,
        generator_delta_mw: float = 10.0,
        clip_generator_to_limits: bool = True,
        terminate_on_divergence: bool = True,
        terminate_on_security_violation: bool = False,
        reward_weights: RewardWeights | None = None,
    ) -> None:
        reward_weights_obj: RewardWeights
        if reward_weights is None:
            reward_weights_obj = RewardWeights()
        else:
            reward_weights_obj = reward_weights

        self._max_steps: int = max_steps
        self._generator_delta_mw: float = generator_delta_mw
        self._clip_generator_to_limits: bool = clip_generator_to_limits
        self._terminate_on_divergence: bool = terminate_on_divergence
        self._terminate_on_security_violation: bool = terminate_on_security_violation
        self._reward_weights: RewardWeights = reward_weights_obj

    def get_max_steps(self) -> int:
        """
        Get the maximum number of steps.

        :return:
            Episode length limit.
        """

        return self._max_steps

    def get_generator_delta_mw(self) -> float:
        """
        Get the baseline redispatch amplitude.

        :return:
            Maximum absolute redispatch amount.
        """

        return self._generator_delta_mw

    def get_clip_generator_to_limits(self) -> bool:
        """
        Get the generator clipping flag.

        :return:
            ``True`` when redispatch commands must be clipped.
        """

        return self._clip_generator_to_limits

    def get_terminate_on_divergence(self) -> bool:
        """
        Get the divergence termination flag.

        :return:
            ``True`` when divergence ends the episode.
        """

        return self._terminate_on_divergence

    def get_terminate_on_security_violation(self) -> bool:
        """
        Get the security termination flag.

        :return:
            ``True`` when a violation ends the episode.
        """

        return self._terminate_on_security_violation

    def get_reward_weights(self) -> RewardWeights:
        """
        Get the reward weights.

        :return:
            Reward weight bundle.
        """

        return self._reward_weights
