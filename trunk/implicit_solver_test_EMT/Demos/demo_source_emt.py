from __future__ import annotations

from trunk.dynamics_emt.scripting_source_emt import run_source_emt_demos
from trunk.dynamics_emt.support.source_emt_demo_support import SourceEmtCaseResult


def run_demo(enable_plots: bool = True) -> dict[str, SourceEmtCaseResult]:
    """
    Run the minimal EMT source demo bundle.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Source case results keyed by case name.
    """
    return run_source_emt_demos(enable_plots=enable_plots)
