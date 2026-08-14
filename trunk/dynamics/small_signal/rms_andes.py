# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path

import andes
import numpy as np
import pandas as pd


def _get_results_dir() -> Path:
    """Return the ANDES RMS results directory.

    :return: Results directory.
    """
    return Path(__file__).resolve().parent / "IEEE14_rms_results_Andes"


def run_andes_ieee14_rms() -> None:
    """Run one second of ANDES IEEE14 RMS simulation and export CSV results.

    :return: None.
    """
    case_path = andes.get_case("ieee14/ieee14_full.xlsx")
    system = andes.load(case_path, default_config=True)

    system.files.no_output = True
    system.PQ.config.p2p = 1.0
    system.PQ.config.p2i = 0
    system.PQ.config.p2z = 0
    system.PQ.config.q2q = 1.0
    system.PQ.config.q2i = 0
    system.PQ.config.q2z = 0
    system.PFlow.config.tol = 1e-13
    system.PFlow.run()

    system.TDS.config.tf = 1.0
    system.TDS.config.tstep = 0.001
    system.TDS.config.store_f = 1
    system.TDS.config.store_h = 1
    system.TDS.run()

    time_array = np.array(system.dae.ts.t)
    x_array = np.array(system.dae.ts.x)
    y_array = np.array(system.dae.ts.y)
    state_names = list(system.dae.x_name_output)
    algebraic_names = list(system.dae.y_name_output)

    data_dict = dict()
    data_dict["time_s"] = time_array

    state_count = len(state_names)
    state_index = 0
    while state_index < state_count:
        data_dict[str(state_names[state_index])] = x_array[:, state_index]
        state_index += 1

    algebraic_count = len(algebraic_names)
    algebraic_index = 0
    while algebraic_index < algebraic_count:
        data_dict[str(algebraic_names[algebraic_index])] = y_array[:, algebraic_index]
        algebraic_index += 1

    results_dir = _get_results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(data_dict).to_csv(
        results_dir / "rms_results_Andes_IEEE14.csv",
        index=False,
        float_format="%.10f",
    )


if __name__ == "__main__":
    run_andes_ieee14_rms()
else:
    pass
