from __future__ import annotations

from trunk.dynamics_emt.support.transient_source_emt_demo_support import TransientSourceEmtCaseResult
from trunk.dynamics_emt.support.transient_source_emt_demo_support import run_all_transient_source_cases


def run_transient_source_emt_demos(enable_plots: bool = True) -> dict[str, TransientSourceEmtCaseResult]:
    """
    Run the transient EMT source demos.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Exported case results keyed by case name.
    """
    return run_all_transient_source_cases(enable_plots=enable_plots)


if __name__ == "__main__":
    run_transient_source_emt_demos(enable_plots=True)
