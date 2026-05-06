# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


def ensure_repo_import_paths() -> None:
    repo_root: Path = Path(__file__).resolve().parents[3]
    src_root: Path = repo_root / "src"
    trunk_root: Path = repo_root / "trunk"
    for path in (str(src_root), str(trunk_root), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)


ensure_repo_import_paths()

from VeraGridEngine.Templates.Emt.converter_switched_emt_multilinear_template import get_switched_emt_converter_multilinear
from dynamics_emt.support.switched_converter_handover_case import (
    SwitchedConverterHandoverTrace,
    simulate_switched_converter_handover,
)


def print_sampled_comparison(ref_trace: SwitchedConverterHandoverTrace, ml_trace: SwitchedConverterHandoverTrace) -> None:
    n = min(len(ref_trace.t_arr), len(ml_trace.t_arr))
    sample_idx = np.linspace(0, n - 1, 12, dtype=int)
    print("time_s,ia_ref,ia_ml,ib_ref,ib_ml,ic_ref,ic_ml,vdc_ref,vdc_ml,ga_ref,ga_ml,Pf_ref,Pf_ml,Qf_ref,Qf_ml")
    for idx in sample_idx:
        print(
            f"{ref_trace.t_arr[idx]:.6e},"
            f"{ref_trace.i_a_arr[idx]:.8e},{ml_trace.i_a_arr[idx]:.8e},"
            f"{ref_trace.i_b_arr[idx]:.8e},{ml_trace.i_b_arr[idx]:.8e},"
            f"{ref_trace.i_c_arr[idx]:.8e},{ml_trace.i_c_arr[idx]:.8e},"
            f"{ref_trace.v_dc_arr[idx]:.8e},{ml_trace.v_dc_arr[idx]:.8e},"
            f"{ref_trace.gate_a_arr[idx]:.3f},{ml_trace.gate_a_arr[idx]:.3f},"
            f"{ref_trace.P_f_arr[idx]:.8e},{ml_trace.P_f_arr[idx]:.8e},"
            f"{ref_trace.Q_f_arr[idx]:.8e},{ml_trace.Q_f_arr[idx]:.8e}"
        )


def plot_comparison(ref_trace: SwitchedConverterHandoverTrace, ml_trace: SwitchedConverterHandoverTrace) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(12, 9), sharex=True)

    axes[0, 0].plot(ref_trace.t_arr, ref_trace.i_a_arr, label="iA ref", linewidth=1.8)
    axes[0, 0].plot(ml_trace.t_arr, ml_trace.i_a_arr, "--", label="iA ml", linewidth=1.5)
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].set_title("Phase-A current")
    axes[0, 0].legend()

    axes[0, 1].plot(ref_trace.t_arr, ref_trace.v_dc_arr, label="vdc ref", linewidth=1.8)
    axes[0, 1].plot(ml_trace.t_arr, ml_trace.v_dc_arr, "--", label="vdc ml", linewidth=1.5)
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].set_title("DC voltage")
    axes[0, 1].legend()

    axes[1, 0].plot(ref_trace.t_arr, ref_trace.v_conv_a_arr, label="vconv_a ref", linewidth=1.8)
    axes[1, 0].plot(ml_trace.t_arr, ml_trace.v_conv_a_arr, "--", label="vconv_a ml", linewidth=1.5)
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].set_title("Converter phase-A voltage")
    axes[1, 0].legend()

    axes[1, 1].plot(ref_trace.t_arr, ref_trace.gate_a_arr, label="gate_a ref", linewidth=1.4)
    axes[1, 1].plot(ml_trace.t_arr, ml_trace.gate_a_arr, "--", label="gate_a ml", linewidth=1.2)
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].set_title("Gate-A mode")
    axes[1, 1].legend()

    axes[2, 0].plot(ref_trace.t_arr, ref_trace.P_f_arr, label="P_f ref", linewidth=1.8)
    axes[2, 0].plot(ml_trace.t_arr, ml_trace.P_f_arr, "--", label="P_f ml", linewidth=1.5)
    axes[2, 0].grid(True, alpha=0.3)
    axes[2, 0].set_title("Filtered active power")
    axes[2, 0].set_xlabel("Time [s]")
    axes[2, 0].legend()

    axes[2, 1].plot(ref_trace.t_arr, ref_trace.Q_f_arr, label="Q_f ref", linewidth=1.8)
    axes[2, 1].plot(ml_trace.t_arr, ml_trace.Q_f_arr, "--", label="Q_f ml", linewidth=1.5)
    axes[2, 1].grid(True, alpha=0.3)
    axes[2, 1].set_title("Filtered reactive power")
    axes[2, 1].set_xlabel("Time [s]")
    axes[2, 1].legend()

    fig.suptitle("Switched converter handover: reference vs multilinear bridge", fontsize=12)
    fig.tight_layout()
    out_path = Path(__file__).resolve().parent / "converter_switched_ml_compare.png"
    fig.savefig(out_path, dpi=170)
    print(f"Plot saved to: {out_path}")
    plt.show()


def main() -> None:
    print("Running reference switched converter case...")
    ref_trace = simulate_switched_converter_handover()
    print("Running multilinear switched converter case...")
    ml_trace = simulate_switched_converter_handover(converter_builder=get_switched_emt_converter_multilinear)
    print_sampled_comparison(ref_trace=ref_trace, ml_trace=ml_trace)
    plot_comparison(ref_trace=ref_trace, ml_trace=ml_trace)


if __name__ == "__main__":
    main()
