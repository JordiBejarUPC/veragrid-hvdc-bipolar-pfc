from __future__ import annotations

from trunk.dynamics_emt.scripting_jmarti_line_emt import run_jmarti_line_comparison
from trunk.dynamics_emt.support.jmarti_demo_support import JMartiLineComparisonResults


def run_demo(enable_plots: bool = True) -> JMartiLineComparisonResults:
    """
    Run the minimal Pi/Bergeron/J_Marti EMT comparison demo.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Aggregated comparison results.
    """
    return run_jmarti_line_comparison(enable_plots=enable_plots)


if __name__ == "__main__":
    run_demo(enable_plots=True)
