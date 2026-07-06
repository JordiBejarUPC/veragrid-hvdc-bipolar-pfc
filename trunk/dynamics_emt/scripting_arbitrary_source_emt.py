from __future__ import annotations

from trunk.dynamics_emt.support.arbitrary_source_emt_demo_support import ArbitrarySourceEmtCaseResult
from trunk.dynamics_emt.support.arbitrary_source_emt_demo_support import run_all_arbitrary_source_cases


def run_arbitrary_source_emt_demos(enable_plots: bool = True) -> dict[str, ArbitrarySourceEmtCaseResult]:
    """
    Run the arbitrary-waveform EMT source demos.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Exported case results keyed by case name.
    """
    return run_all_arbitrary_source_cases(enable_plots=enable_plots)


if __name__ == "__main__":
    run_arbitrary_source_emt_demos(enable_plots=True)
