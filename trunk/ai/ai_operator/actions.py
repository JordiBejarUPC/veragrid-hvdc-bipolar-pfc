from __future__ import annotations

from enum import Enum
from typing import Union


class ActionCategory(str, Enum):
    """
    Action category selector.

    :ivar BRANCH_SWITCH:
        Branch topology action.
    :ivar GENERATOR_REDISPATCH:
        Generator active power action.
    """

    BRANCH_SWITCH = "branch_switch"
    GENERATOR_REDISPATCH = "generator_redispatch"
    NO_OP = "no_op"


class NoOpAction:
    """
    No-operation action description.

    This action leaves the grid unchanged and is useful as a neutral concurrent
    merge outcome when an aggression scheduler needs to damp one agent.
    """

    __slots__ = tuple()

    def get_category(self) -> ActionCategory:
        """
        Get the action category.

        :return:
            The no-op action category.
        """

        return ActionCategory.NO_OP

    def __repr__(self) -> str:
        """
        Build a readable action representation.

        :return:
            String representation for logs.
        """

        return "NoOpAction()"


class BranchSwitchAction:
    """
    Branch switching action description.

    :param branch_idx:
        Index of the target branch in the grid branch collection.
    :param closed:
        ``True`` means close the branch and ``False`` means open it.
    """

    __slots__ = ("_branch_idx", "_closed")

    def __init__(self, branch_idx: int, closed: bool) -> None:
        self._branch_idx: int = branch_idx
        self._closed: bool = closed

    def get_branch_idx(self) -> int:
        """
        Get the branch index.

        :return:
            Target branch index.
        """

        return self._branch_idx

    def get_closed(self) -> bool:
        """
        Get the desired target state.

        :return:
            ``True`` when the branch must be closed.
        """

        return self._closed

    def get_category(self) -> ActionCategory:
        """
        Get the action category.

        :return:
            The branch switching category.
        """

        return ActionCategory.BRANCH_SWITCH

    def __repr__(self) -> str:
        """
        Build a readable action representation.

        :return:
            String representation for logs.
        """

        return f"BranchSwitchAction(branch_idx={self._branch_idx}, closed={self._closed})"


class GeneratorRedispatchAction:
    """
    Generator redispatch action description.

    :param generator_idx:
        Index of the target generator in the grid generator collection.
    :param delta_mw:
        Active power delta in MW to add to the current generator setpoint.
    """

    __slots__ = ("_generator_idx", "_delta_mw")

    def __init__(self, generator_idx: int, delta_mw: float) -> None:
        self._generator_idx: int = generator_idx
        self._delta_mw: float = delta_mw

    def get_generator_idx(self) -> int:
        """
        Get the generator index.

        :return:
            Target generator index.
        """

        return self._generator_idx

    def get_delta_mw(self) -> float:
        """
        Get the redispatch amount.

        :return:
            Active power delta in MW.
        """

        return self._delta_mw

    def get_category(self) -> ActionCategory:
        """
        Get the action category.

        :return:
            The generator redispatch category.
        """

        return ActionCategory.GENERATOR_REDISPATCH

    def __repr__(self) -> str:
        """
        Build a readable action representation.

        :return:
            String representation for logs.
        """

        return (
            "GeneratorRedispatchAction("
            f"generator_idx={self._generator_idx}, delta_mw={self._delta_mw})"
        )


OperatorAction = Union[BranchSwitchAction, GeneratorRedispatchAction, NoOpAction]
