from __future__ import annotations

from trunk.dynamics_emt.scripting_transient_source_emt import run_transient_source_emt_demos
from trunk.dynamics_emt.support.transient_source_emt_demo_support import TransientSourceEmtCaseResult


def run_demo(enable_plots: bool = True) -> dict[str, TransientSourceEmtCaseResult]:
    """
    Run the transient EMT source demo bundle.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Case results keyed by case name.
    """
    return run_transient_source_emt_demos(enable_plots=enable_plots)
