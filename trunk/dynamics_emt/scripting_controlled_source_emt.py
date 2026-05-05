from __future__ import annotations

from trunk.dynamics_emt.support.controlled_source_emt_demo_support import ControlledSourceEmtCaseResult
from trunk.dynamics_emt.support.controlled_source_emt_demo_support import run_all_controlled_source_cases


def run_controlled_source_emt_demos(enable_plots: bool = True) -> dict[str, ControlledSourceEmtCaseResult]:
    """
    Run the controlled EMT source demos with one minimal control loop.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Exported case results keyed by case name.
    """
    return run_all_controlled_source_cases(enable_plots=enable_plots)


if __name__ == "__main__":
    run_controlled_source_emt_demos(enable_plots=True)
