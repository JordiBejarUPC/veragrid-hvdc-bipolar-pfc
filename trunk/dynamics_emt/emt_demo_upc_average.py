# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Point-to-point HVDC EMT event demo using averaged GFL converters."""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT: Path = Path(__file__).resolve().parents[2]
SRC_ROOT: Path = REPO_ROOT / "src"
TRUNK_ROOT: Path = REPO_ROOT / "trunk"
for import_root in (SRC_ROOT, TRUNK_ROOT, REPO_ROOT):
    import_root_text: str = str(import_root)
    if import_root_text not in sys.path:
        sys.path.insert(0, import_root_text)

from dynamics_emt import scripting_hvdc_vdc_control as hvdc_case


PLOT_DIRECTORY: Path = Path(__file__).with_name("hvdc_vdc_control_plots")
RESPONSE_PLOT: Path = PLOT_DIRECTORY / "hvdc_average_control.png"
AC_VOLTAGE_PLOT: Path = PLOT_DIRECTORY / "hvdc_average_ac_bus_voltages.png"


def plot_average_hvdc_results(results: dict[str, object]) -> None:
    """Save averaged-model response plots without overwriting switched results."""
    time_s = np.asarray(results["time"])
    signals = results["signals"]
    PLOT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    axes[0].plot(time_s, signals["vdc_ref"], "--", label="Vdc ref")
    axes[0].plot(time_s, signals["v_dc_1"], label="Vdc bus 1")
    axes[0].plot(time_s, signals["v_dc_2"], label="Vdc bus 2")
    axes[0].set_ylabel("Voltage [pu]")
    axes[1].plot(time_s, signals["pdc_ref_vsc2"], "--", label="VSC2 Pdc ref")
    axes[1].plot(time_s, signals["p_vsc2"], label="P VSC2")
    axes[1].plot(time_s, signals["p_ctrl"], label="Line PI Pctrl")
    axes[1].set_ylabel("Power [pu]")
    axes[2].plot(time_s, signals["i_f_dc"], label="If dc")
    axes[2].plot(time_s, signals["i_t_dc"], label="It dc")
    axes[2].set_xlabel("Time [s]")
    axes[2].set_ylabel("Current [pu]")
    for axis in axes:
        axis.grid(True)
        axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(RESPONSE_PLOT, dpi=150)
    plt.close(figure)

    ac_figure, ac_axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for phase in ("a", "b", "c"):
        ac_axes[0].plot(time_s, signals[f"v_grid_1_{phase}"], label=f"V{phase} Grid 1")
        ac_axes[1].plot(time_s, signals[f"v_grid_2_{phase}"], label=f"V{phase} Grid 2")
    for grid_index, axis in enumerate(ac_axes, start=1):
        axis.set_ylabel("Voltage [pu]")
        axis.set_title(f"Averaged-model AC bus voltages Grid {grid_index}")
        axis.grid(True)
        axis.legend(loc="best")
    ac_axes[1].set_xlabel("Time [s]")
    ac_figure.tight_layout()
    ac_figure.savefig(AC_VOLTAGE_PLOT, dpi=150)
    plt.close(ac_figure)


def run_emt_demo_upc_average(
        simulation_time_s: float = 0.09,
        time_step_s: float = 5.0e-5,
        plot: bool = True,
        power_event_time_s: float = 0.04,
        vdc_event_time_s: float = 0.08,
        transfer_power_pu: float = 0.20,
        vdc_event_value_pu: float = 1.02,
) -> dict[str, object]:
    """Run the full averaged-GFL HVDC case with its configured control events."""
    results = hvdc_case.run_hvdc_vdc_control_simulation(
        simulation_time_s=simulation_time_s,
        time_step_s=time_step_s,
        enable_vdc_reference_event=True,
        use_line_vdc_control=False,
        power_event_time_s=power_event_time_s,
        vdc_event_time_s=vdc_event_time_s,
        transfer_power_pu=transfer_power_pu,
        vdc_event_value_pu=vdc_event_value_pu,
        plot=False,
        save_grid_filename=str(Path(__file__).with_name("emt_demo_upc_average.veragrid")),
    )
    trajectory = np.asarray(results["trajectory"])
    if not np.all(np.isfinite(trajectory)):
        raise RuntimeError("The averaged-GFL HVDC simulation produced a non-finite trajectory.")
    if plot:
        plot_average_hvdc_results(results)
    return results


def main() -> None:
    """Run the averaged HVDC event demo and print solver status."""
    results = run_emt_demo_upc_average()
    print("UPC two-terminal averaged-GFL HVDC EMT demo")
    print(f"power flow converged = {results['pf_results'].converged}")
    print(f"well initialized     = {results['well_initialized']}")
    print(f"EMT converged        = {results['converged']}")
    print(f"finite trajectory    = {bool(np.all(np.isfinite(results['trajectory'])))}")
    print(f"response plot        = {RESPONSE_PLOT}")
    print(f"AC voltage plot      = {AC_VOLTAGE_PLOT}")


if __name__ == "__main__":
    main()
