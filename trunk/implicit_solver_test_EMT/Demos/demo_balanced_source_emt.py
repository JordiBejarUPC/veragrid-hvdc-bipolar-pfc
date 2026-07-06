from __future__ import annotations

from trunk.dynamics_emt.scripting_balanced_source_emt import run_balanced_source_emt_demos
from trunk.dynamics_emt.support.balanced_source_emt_demo_support import BalancedSourceEmtCaseResult


def run_demo(enable_plots: bool = True) -> dict[str, BalancedSourceEmtCaseResult]:
    """
    Run the balanced three-phase EMT source demo bundle.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Case results keyed by case name.
    """
    return run_balanced_source_emt_demos(enable_plots=enable_plots)
