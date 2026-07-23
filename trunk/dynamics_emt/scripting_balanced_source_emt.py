from __future__ import annotations

from trunk.dynamics_emt.support.balanced_source_emt_demo_support import BalancedSourceEmtCaseResult
from trunk.dynamics_emt.support.balanced_source_emt_demo_support import run_all_balanced_source_cases


def run_balanced_source_emt_demos(enable_plots: bool = True) -> dict[str, BalancedSourceEmtCaseResult]:
    """
    Run the balanced three-phase EMT source demos.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Exported case results keyed by case name.
    """
    return run_all_balanced_source_cases(enable_plots=enable_plots)


if __name__ == "__main__":
    run_balanced_source_emt_demos(enable_plots=True)
