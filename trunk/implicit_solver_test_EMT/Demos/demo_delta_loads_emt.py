from __future__ import annotations

from typing import Dict

from trunk.dynamics_emt.scripting_delta_loads_emt import run_delta_load_cases


def run_demo(enable_plots: bool = True) -> Dict[str, object]:
    """
    Run the EMT delta exponential/ZIP load demos.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Demo traces and artifact paths.
    """
    return run_delta_load_cases(enable_plots=enable_plots)


if __name__ == "__main__":
    run_demo(enable_plots=True)
