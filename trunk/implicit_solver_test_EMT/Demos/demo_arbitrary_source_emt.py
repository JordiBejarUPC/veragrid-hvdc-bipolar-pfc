from __future__ import annotations

from trunk.dynamics_emt.scripting_arbitrary_source_emt import run_arbitrary_source_emt_demos
from trunk.dynamics_emt.support.arbitrary_source_emt_demo_support import ArbitrarySourceEmtCaseResult


def run_demo(enable_plots: bool = True) -> dict[str, ArbitrarySourceEmtCaseResult]:
    """
    Run the arbitrary-waveform EMT source demo bundle.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Case results keyed by case name.
    """
    return run_arbitrary_source_emt_demos(enable_plots=enable_plots)
