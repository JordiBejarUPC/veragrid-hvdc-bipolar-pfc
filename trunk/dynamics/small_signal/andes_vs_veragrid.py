# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def compare_rms_results(veragrid_csv: Path, andes_csv: Path) -> None:
    """Compare ANDES and VeraGrid RMS trajectory CSV files.

    :param veragrid_csv: VeraGrid RMS CSV file.
    :param andes_csv: ANDES RMS CSV file.
    :return: None.
    """
    # Stage 1: load both tabular trajectories without assuming a signal layout.
    veragrid_data: np.ndarray = np.genfromtxt(
        veragrid_csv,
        delimiter=",",
        names=True,
        dtype=None,
        encoding="utf-8",
    )
    andes_data: np.ndarray = np.genfromtxt(
        andes_csv,
        delimiter=",",
        names=True,
        dtype=None,
        encoding="utf-8",
    )

    # Stage 2: retain only signals that can be compared by a human directly.
    veragrid_columns: list[str] = list(veragrid_data.dtype.names)
    andes_columns: list[str] = list(andes_data.dtype.names)
    common_columns: list[str] = list()

    column_name: str
    for column_name in andes_columns:
        if column_name in veragrid_columns:
            common_columns.append(column_name)
        else:
            pass

    print("Common RMS result columns:")
    print(common_columns)

    # Stage 3: display one shared trajectory when a non-time signal exists.
    if len(common_columns) > 1:
        signal_name: str = common_columns[1]
        fig_rms: Any
        ax_rms: Any
        fig_rms, ax_rms = plt.subplots(figsize=(10, 7))
        ax_rms.plot(andes_data["time_s"], andes_data[signal_name], label=f"ANDES {signal_name}")
        ax_rms.plot(veragrid_data["time_s"], veragrid_data[signal_name], label=f"VeraGrid {signal_name}")
        ax_rms.set_xlabel("Time [s]")
        ax_rms.set_ylabel(signal_name)
        ax_rms.set_title("IEEE14 RMS trajectory comparison")
        ax_rms.grid(True, alpha=0.3)
        ax_rms.legend()
        fig_rms.tight_layout()
        plt.show()
    else:
        print("No common RMS columns were found to plot.")


def main() -> None:
    """Compare the repository-default IEEE14 RMS result folders.

    :return: None.
    """
    script_dir: Path = Path(__file__).resolve().parent
    veragrid_csv: Path = script_dir / "ieee14_rms_results_VeraGrid" / "rms_results_VeraGrid_IEEE14.csv"
    andes_csv: Path = script_dir / "IEEE14_rms_results_Andes" / "rms_results_Andes_IEEE14.csv"
    compare_rms_results(veragrid_csv=veragrid_csv, andes_csv=andes_csv)


if __name__ == "__main__":
    main()
else:
    pass
