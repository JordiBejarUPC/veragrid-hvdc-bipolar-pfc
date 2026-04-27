from __future__ import annotations

from trunk.dynamics_emt.scripting_nonlinear_resistor_emt import NonlinearResistorEmtCaseResults
from trunk.dynamics_emt.scripting_nonlinear_resistor_emt import run_nonlinear_resistor_case


def run_demo(enable_plots: bool = True) -> NonlinearResistorEmtCaseResults:
    """
    Run the EMT nonlinear-resistor network demo.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Demo traces and artifact paths.
    """
    return run_nonlinear_resistor_case(enable_plots=enable_plots)


if __name__ == "__main__":
    run_demo(enable_plots=True)
