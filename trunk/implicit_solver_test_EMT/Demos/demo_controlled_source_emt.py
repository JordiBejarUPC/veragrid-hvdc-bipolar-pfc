from __future__ import annotations

from trunk.dynamics_emt.scripting_controlled_source_emt import run_controlled_source_emt_demos
from trunk.dynamics_emt.support.controlled_source_emt_demo_support import ControlledSourceEmtCaseResult


def run_demo(enable_plots: bool = True) -> dict[str, ControlledSourceEmtCaseResult]:
    """
    Run the controlled EMT source demo bundle.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Case results keyed by case name.
    """
    return run_controlled_source_emt_demos(enable_plots=enable_plots)
