# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Compare classical sigma and DPR sigma on simple Matpower grids.

These cases have standard PQ/PV/slack bus types, so the DPR sigma path should be numerically equivalent to the
classical sigma result. If it is not, the comparison exposes the maximum bus-wise differences.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    """
    Run the sigma comparison for a small Matpower case set.

    :return: None.
    """

    # Make the checkout ``src`` directory importable when the script is executed directly.
    root: Path = Path(__file__).resolve().parents[2]
    src_path: str = str(root / "src")

    if src_path in sys.path:
        src_path = src_path
    else:
        sys.path.insert(0, src_path)

    from VeraGridEngine.IO.file_open import FileOpen
    from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
    from VeraGridEngine.Simulations.SigmaAnalysis.sigma_analysis_driver import multi_island_sigma
    from VeraGridEngine.basic_structures import Logger

    grid_dir: Path = root / "src" / "tests" / "data" / "grids" / "Matpower"
    cases: list[str] = list()
    cases.append("case9.matpower")
    cases.append("case14.matpower")
    cases.append("case_ieee30.matpower")

    options: PowerFlowOptions = PowerFlowOptions(tolerance=1e-8, max_iter=40)
    logger: Logger = Logger()
    rows: list[dict[str, object]] = list()

    for case_name in cases:
        # Run both sigma variants through the same public island path.
        grid = FileOpen(file_name=str(grid_dir / case_name)).open()
        classical = multi_island_sigma(multi_circuit=grid,
                                       options=options,
                                       logger=logger,
                                       classical_sigma=True)
        dpr = multi_island_sigma(multi_circuit=grid,
                                 options=options,
                                 logger=logger,
                                 classical_sigma=False)

        sigma_re_diff: np.ndarray = np.abs(classical.sigma_re - dpr.sigma_re)
        sigma_im_diff: np.ndarray = np.abs(classical.sigma_im - dpr.sigma_im)
        distance_diff: np.ndarray = np.abs(classical.distances - dpr.distances)
        worst_bus: int = int(np.argmax(sigma_re_diff + sigma_im_diff + distance_diff))

        rows.append({
            "grid": case_name,
            "classical_ok": bool(classical.converged),
            "dpr_ok": bool(dpr.converged),
            "max_d_sigma_re": float(np.max(sigma_re_diff)),
            "max_d_sigma_im": float(np.max(sigma_im_diff)),
            "max_d_distance": float(np.max(distance_diff)),
            "worst_bus": worst_bus,
            "classical_dist": float(classical.distances[worst_bus]),
            "dpr_dist": float(dpr.distances[worst_bus]),
        })

    report: pd.DataFrame = pd.DataFrame(rows)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 240)
    pd.set_option("display.float_format", "{:.3e}".format)
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
