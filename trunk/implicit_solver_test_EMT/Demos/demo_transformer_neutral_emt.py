from __future__ import annotations

from typing import Dict

from trunk.dynamics_emt.scripting_transformer_neutral_emt import run_transformer_neutral_case


def run_demo(enable_plots: bool = True) -> Dict[str, object]:
    """
    Run the Transformer EMT explicit-neutral demo.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Demo traces and artifact paths.
    """
    return run_transformer_neutral_case(enable_plots=enable_plots)


if __name__ == "__main__":
    run_demo(enable_plots=True)
