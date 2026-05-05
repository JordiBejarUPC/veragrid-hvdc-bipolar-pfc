from __future__ import annotations

from trunk.dynamics_emt.scripting_dc_source_emt import run_dc_source_emt_demos
from trunk.dynamics_emt.support.dc_source_emt_demo_support import DcSourceEmtCaseResult


def run_demo(enable_plots: bool = True) -> dict[str, DcSourceEmtCaseResult]:
    """
    Run the EMT DC source demo bundle.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Case results keyed by case name.
    """
    return run_dc_source_emt_demos(enable_plots=enable_plots)
