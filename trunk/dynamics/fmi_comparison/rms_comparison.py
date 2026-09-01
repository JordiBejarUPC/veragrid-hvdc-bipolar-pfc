# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile

import matplotlib
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

from VeraGridEngine.IO.fmu.exporter.validate import (
    simulate_fmu_with_fmpy as simulate_cs_fmu_with_fmpy,
    validate_fmu_with_fmpy as validate_cs_fmu_with_fmpy,
)
from VeraGridEngine.IO.fmu.exporter_me.validate import (
    simulate_fmu_with_fmpy as simulate_me_fmu_with_fmpy,
    validate_fmu_with_fmpy as validate_me_fmu_with_fmpy,
)
from trunk.dynamics.fmi_comparison.fmi_example_runner import (
    RmsFmiExampleExecution,
    execute_rms_fmi_example,
)
from VeraGridEngine.IO.fmu.importer.model_description import FmuInterfaceMode


class RmsFmiComparisonConfig:
    """Own the explicit inputs of one RMS FMI comparison package."""

    __slots__ = (
        "_output_dir",
        "_source_revision",
        "_source_tree_sha256",
        "_absolute_tolerance",
        "_relative_tolerance",
    )

    def __init__(
            self,
            output_dir: Path,
            source_revision: str,
            source_tree_sha256: str,
            absolute_tolerance: float = 1.0e-12,
            relative_tolerance: float = 1.0e-10,
    ) -> None:
        """Validate and retain the caller-declared comparison configuration.

        :param output_dir: Final package directory, which must not exist.
        :param source_revision: Caller-declared source revision.
        :param source_tree_sha256: Caller-declared SHA-256 of the complete source tree.
        :param absolute_tolerance: Floating-point absolute comparison term.
        :param relative_tolerance: Floating-point relative comparison term.
        :return: None.
        """

        revision_is_valid: bool = bool(source_revision.strip())
        tree_hash_is_valid: bool = bool(
            len(source_tree_sha256) == 64
            and source_tree_sha256 == source_tree_sha256.lower()
            and all(
                character in "0123456789abcdef"
                for character in source_tree_sha256
            )
        )
        tolerances_are_valid: bool = bool(
            math.isfinite(absolute_tolerance)
            and absolute_tolerance > 0.0
            and math.isfinite(relative_tolerance)
            and relative_tolerance >= 0.0
        )
        if revision_is_valid:
            pass
        else:
            raise ValueError("Source revision must be a non-empty caller declaration")
        if tree_hash_is_valid:
            pass
        else:
            raise ValueError("Source tree identity must be a lowercase SHA-256")
        if tolerances_are_valid:
            pass
        else:
            raise ValueError("Comparison tolerances must be finite and non-negative")

        self._output_dir: Path = output_dir.resolve()
        self._source_revision: str = source_revision.strip()
        self._source_tree_sha256: str = source_tree_sha256
        self._absolute_tolerance: float = float(absolute_tolerance)
        self._relative_tolerance: float = float(relative_tolerance)

    def get_output_dir(self) -> Path:
        """Return the final package destination.

        :return: Resolved final directory.
        """

        return self._output_dir

    def get_source_revision(self) -> str:
        """Return the caller-declared source revision.

        :return: Source revision text.
        """

        return self._source_revision

    def get_source_tree_sha256(self) -> str:
        """Return the caller-declared source-tree SHA-256.

        :return: Lowercase SHA-256 text.
        """

        return self._source_tree_sha256

    def get_absolute_tolerance(self) -> float:
        """Return the floating-point absolute comparison term.

        :return: Absolute tolerance.
        """

        return self._absolute_tolerance

    def get_relative_tolerance(self) -> float:
        """Return the floating-point relative comparison term.

        :return: Relative tolerance.
        """

        return self._relative_tolerance


class RmsFmiComparisonMetrics:
    """Own errors and per-sample budgets from one aligned FMI comparison."""

    __slots__ = (
        "_absolute_active_power_error",
        "_absolute_reactive_power_error",
        "_active_power_budget",
        "_reactive_power_budget",
        "_max_active_power_error",
        "_max_reactive_power_error",
        "_rms_active_power_error",
        "_rms_reactive_power_error",
    )

    def __init__(
            self,
            absolute_active_power_error: np.ndarray,
            absolute_reactive_power_error: np.ndarray,
            active_power_budget: np.ndarray,
            reactive_power_budget: np.ndarray,
    ) -> None:
        """Store one comparison result after all samples have passed.

        :param absolute_active_power_error: Absolute active-power errors in p.u.
        :param absolute_reactive_power_error: Absolute reactive-power errors in p.u.
        :param active_power_budget: Active-power acceptance budget per sample.
        :param reactive_power_budget: Reactive-power acceptance budget per sample.
        :return: None.
        """

        arrays_match: bool = bool(
            absolute_active_power_error.ndim == 1
            and absolute_reactive_power_error.shape
            == absolute_active_power_error.shape
            and active_power_budget.shape == absolute_active_power_error.shape
            and reactive_power_budget.shape == absolute_active_power_error.shape
            and absolute_active_power_error.size > 0
        )
        if arrays_match:
            pass
        else:
            raise ValueError("Comparison metric arrays must be aligned and non-empty")

        self._absolute_active_power_error: np.ndarray = np.array(
            absolute_active_power_error,
            dtype=float,
            copy=True,
        )
        self._absolute_reactive_power_error: np.ndarray = np.array(
            absolute_reactive_power_error,
            dtype=float,
            copy=True,
        )
        self._active_power_budget: np.ndarray = np.array(
            active_power_budget,
            dtype=float,
            copy=True,
        )
        self._reactive_power_budget: np.ndarray = np.array(
            reactive_power_budget,
            dtype=float,
            copy=True,
        )
        self._max_active_power_error: float = float(
            np.max(self._absolute_active_power_error)
        )
        self._max_reactive_power_error: float = float(
            np.max(self._absolute_reactive_power_error)
        )
        self._rms_active_power_error: float = float(
            np.sqrt(np.mean(np.square(self._absolute_active_power_error)))
        )
        self._rms_reactive_power_error: float = float(
            np.sqrt(np.mean(np.square(self._absolute_reactive_power_error)))
        )

    def get_absolute_active_power_error(self) -> np.ndarray:
        """Return a defensive copy of active-power errors.

        :return: Absolute active-power error by sample.
        """

        return self._absolute_active_power_error.copy()

    def get_absolute_reactive_power_error(self) -> np.ndarray:
        """Return a defensive copy of reactive-power errors.

        :return: Absolute reactive-power error by sample.
        """

        return self._absolute_reactive_power_error.copy()

    def get_max_active_power_error(self) -> float:
        """Return the maximum absolute active-power error.

        :return: Maximum active-power error in p.u.
        """

        return self._max_active_power_error

    def get_max_reactive_power_error(self) -> float:
        """Return the maximum absolute reactive-power error.

        :return: Maximum reactive-power error in p.u.
        """

        return self._max_reactive_power_error

    def get_rms_active_power_error(self) -> float:
        """Return the root-mean-square active-power error.

        :return: RMS active-power error in p.u.
        """

        return self._rms_active_power_error

    def get_rms_reactive_power_error(self) -> float:
        """Return the root-mean-square reactive-power error.

        :return: RMS reactive-power error in p.u.
        """

        return self._rms_reactive_power_error


def _hash_file(path: Path) -> str:
    """Compute the SHA-256 identity of one retained artifact.

    :param path: File to hash.
    :return: Lowercase SHA-256 text.
    """

    with path.open("rb") as file_handle:
        return hashlib.file_digest(file_handle, "sha256").hexdigest()


def _build_me_input_signal(
        time_seconds: np.ndarray,
        voltage_magnitude: np.ndarray,
) -> np.ndarray:
    """Build the direct FMPy ME input from accepted RMS voltage samples.

    :param time_seconds: Exact accepted RMS time lattice.
    :param voltage_magnitude: Exact accepted bus-voltage samples.
    :return: Structured FMPy input signal with time and voltage fields.
    """

    inputs_are_valid: bool = bool(
        time_seconds.ndim == 1
        and voltage_magnitude.shape == time_seconds.shape
        and time_seconds.size > 0
        and np.all(np.isfinite(time_seconds))
        and np.all(np.isfinite(voltage_magnitude))
    )
    if inputs_are_valid:
        pass
    else:
        raise ValueError("ME input time and voltage traces must be finite and aligned")

    input_signal: np.ndarray = np.empty(
        time_seconds.size,
        dtype=np.dtype([("time", np.float64), ("u", np.float64)]),
    )
    input_signal["time"] = time_seconds
    input_signal["u"] = voltage_magnitude
    return input_signal


def _get_direct_fmpy_trace(
        execution: RmsFmiExampleExecution,
        extraction_root: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Execute the exact retained FMU directly through its FMPy backend.

    :param execution: Native RMS execution that owns the exact FMU and lattice.
    :param extraction_root: Owned directory used for temporary FMPy extraction.
    :return: Direct time, active-power and reactive-power trajectories.
    """

    time_seconds: np.ndarray = execution.get_time_seconds()
    stop_time: float = float(time_seconds[-1])
    output_names: list[str] = list(("p_out", "q_out"))
    mode: FmuInterfaceMode = execution.get_mode()
    if mode == FmuInterfaceMode.CO_SIMULATION:
        simulation_result: np.ndarray = simulate_cs_fmu_with_fmpy(
            execution.get_fmu_path(),
            stop_time=stop_time,
            output=output_names,
            extraction_root=extraction_root,
            output_interval=1.0e-3,
        )
    elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
        voltage_magnitude: np.ndarray | None = execution.get_voltage_magnitude()
        if voltage_magnitude is None:
            raise RuntimeError("The RMS ME execution did not retain its voltage input")
        else:
            input_signal: np.ndarray = _build_me_input_signal(
                time_seconds,
                voltage_magnitude,
            )
        simulation_result = simulate_me_fmu_with_fmpy(
            execution.get_fmu_path(),
            stop_time=stop_time,
            output=output_names,
            input_signal=input_signal,
            extraction_root=extraction_root,
            step_size=1.0e-3,
        )
    else:
        raise ValueError(f"Unsupported RMS FMI comparison mode: {mode.value}")

    result_names: tuple[str, ...] | None = simulation_result.dtype.names
    required_names_are_present: bool = bool(
        result_names is not None
        and "time" in result_names
        and "p_out" in result_names
        and "q_out" in result_names
    )
    if required_names_are_present:
        direct_time: np.ndarray = np.asarray(
            simulation_result["time"],
            dtype=float,
        ).copy()
        direct_active_power: np.ndarray = np.asarray(
            simulation_result["p_out"],
            dtype=float,
        ).copy()
        direct_reactive_power: np.ndarray = np.asarray(
            simulation_result["q_out"],
            dtype=float,
        ).copy()
    else:
        raise RuntimeError("Direct FMPy result omitted a required comparison field")

    direct_values_are_finite: bool = bool(
        direct_time.ndim == 1
        and direct_active_power.shape == direct_time.shape
        and direct_reactive_power.shape == direct_time.shape
        and direct_time.size > 0
        and np.all(np.isfinite(direct_time))
        and np.all(np.isfinite(direct_active_power))
        and np.all(np.isfinite(direct_reactive_power))
    )
    if direct_values_are_finite:
        return direct_time, direct_active_power, direct_reactive_power
    else:
        raise RuntimeError("Direct FMPy result is incomplete or non-finite")


def _compare_aligned_trajectories(
        rms_time_seconds: np.ndarray,
        rms_active_power: np.ndarray,
        rms_reactive_power: np.ndarray,
        direct_time_seconds: np.ndarray,
        direct_active_power: np.ndarray,
        direct_reactive_power: np.ndarray,
        rms_solver_tolerance: float,
        power_flow_residual: float,
        absolute_tolerance: float,
        relative_tolerance: float,
) -> RmsFmiComparisonMetrics:
    """Compare exact-lattice trajectories under the two proven error regimes.

    The initial row is the projected RMS operating point and therefore includes
    the actual converged power-flow residual. Later rows use only the accepted
    RMS output-shell residual. Both regimes include the declared floating terms.

    :param rms_time_seconds: Accepted RMS time lattice.
    :param rms_active_power: Accepted RMS active-power trajectory.
    :param rms_reactive_power: Accepted RMS reactive-power trajectory.
    :param direct_time_seconds: Direct FMPy time lattice.
    :param direct_active_power: Direct FMPy active-power trajectory.
    :param direct_reactive_power: Direct FMPy reactive-power trajectory.
    :param rms_solver_tolerance: Actual RMS algebraic residual tolerance.
    :param power_flow_residual: Actual converged power-flow infinity residual.
    :param absolute_tolerance: Floating-point absolute term.
    :param relative_tolerance: Floating-point relative term.
    :return: Conclusive comparison metrics.
    """

    expected_time_seconds: np.ndarray = np.arange(6, dtype=float) * 1.0e-3
    shapes_are_valid: bool = bool(
        rms_time_seconds.shape == expected_time_seconds.shape
        and rms_active_power.shape == expected_time_seconds.shape
        and rms_reactive_power.shape == expected_time_seconds.shape
        and direct_time_seconds.shape == expected_time_seconds.shape
        and direct_active_power.shape == expected_time_seconds.shape
        and direct_reactive_power.shape == expected_time_seconds.shape
    )
    if shapes_are_valid:
        pass
    else:
        raise ValueError("RMS FMI comparison requires exactly six aligned samples")

    values_are_finite: bool = bool(
        np.all(np.isfinite(rms_time_seconds))
        and np.all(np.isfinite(rms_active_power))
        and np.all(np.isfinite(rms_reactive_power))
        and np.all(np.isfinite(direct_time_seconds))
        and np.all(np.isfinite(direct_active_power))
        and np.all(np.isfinite(direct_reactive_power))
        and math.isfinite(rms_solver_tolerance)
        and rms_solver_tolerance > 0.0
        and math.isfinite(power_flow_residual)
        and power_flow_residual >= 0.0
        and math.isfinite(absolute_tolerance)
        and absolute_tolerance > 0.0
        and math.isfinite(relative_tolerance)
        and relative_tolerance >= 0.0
    )
    if values_are_finite:
        pass
    else:
        raise ValueError("RMS FMI comparison inputs and tolerances must be finite")

    expected_lattice_matches: bool = bool(
        np.all(np.abs(rms_time_seconds - expected_time_seconds) <= 1.0e-12)
    )
    direct_lattice_matches: bool = bool(
        np.all(np.abs(direct_time_seconds - rms_time_seconds) <= 1.0e-12)
    )
    if expected_lattice_matches and direct_lattice_matches:
        pass
    else:
        raise ValueError(
            "RMS and direct FMPy trajectories must share the exact six-sample lattice"
        )

    absolute_active_power_error: np.ndarray = np.abs(
        rms_active_power - direct_active_power
    )
    absolute_reactive_power_error: np.ndarray = np.abs(
        rms_reactive_power - direct_reactive_power
    )
    active_power_budget: np.ndarray = (
        absolute_tolerance
        + relative_tolerance * np.abs(direct_active_power)
        + rms_solver_tolerance
    )
    reactive_power_budget: np.ndarray = (
        absolute_tolerance
        + relative_tolerance * np.abs(direct_reactive_power)
        + rms_solver_tolerance
    )
    # Only row zero inherits the calculated-versus-specified power-flow
    # mismatch before the RMS algebraic projection stores its accepted x0.
    active_power_budget[0] += power_flow_residual
    reactive_power_budget[0] += power_flow_residual

    active_power_passes: bool = bool(
        np.all(absolute_active_power_error <= active_power_budget)
    )
    reactive_power_passes: bool = bool(
        np.all(absolute_reactive_power_error <= reactive_power_budget)
    )
    if active_power_passes and reactive_power_passes:
        return RmsFmiComparisonMetrics(
            absolute_active_power_error=absolute_active_power_error,
            absolute_reactive_power_error=absolute_reactive_power_error,
            active_power_budget=active_power_budget,
            reactive_power_budget=reactive_power_budget,
        )
    else:
        active_excess: float = float(
            np.max(absolute_active_power_error - active_power_budget)
        )
        reactive_excess: float = float(
            np.max(absolute_reactive_power_error - reactive_power_budget)
        )
        raise RuntimeError(
            "RMS FMI trajectory exceeds its derived comparison budget: "
            f"active excess={active_excess:.16e}, "
            f"reactive excess={reactive_excess:.16e}"
        )


def _write_trace_csv(
        csv_path: Path,
        execution: RmsFmiExampleExecution,
        direct_time_seconds: np.ndarray,
        direct_active_power: np.ndarray,
        direct_reactive_power: np.ndarray,
        metrics: RmsFmiComparisonMetrics,
        absolute_tolerance: float,
        relative_tolerance: float,
) -> Path:
    """Write the complete aligned trace and both error budgets as CSV.

    :param csv_path: Destination CSV path.
    :param execution: Native RMS execution evidence.
    :param direct_time_seconds: Direct FMPy time lattice.
    :param direct_active_power: Direct active-power trace.
    :param direct_reactive_power: Direct reactive-power trace.
    :param metrics: Passed comparison metrics and per-sample budgets.
    :param absolute_tolerance: Floating absolute comparison term.
    :param relative_tolerance: Floating relative comparison term.
    :return: Written CSV path.
    """

    rms_time_seconds: np.ndarray = execution.get_time_seconds()
    rms_active_power: np.ndarray = execution.get_active_power()
    rms_reactive_power: np.ndarray = execution.get_reactive_power()
    absolute_active_power_error: np.ndarray = (
        metrics.get_absolute_active_power_error()
    )
    absolute_reactive_power_error: np.ndarray = (
        metrics.get_absolute_reactive_power_error()
    )
    active_power_budget: np.ndarray = metrics._active_power_budget.copy()
    reactive_power_budget: np.ndarray = metrics._reactive_power_budget.copy()
    rms_solver_tolerance: float = execution.get_solver_tolerance()
    power_flow_residual: float = execution.get_power_flow_residual()

    header: tuple[str, ...] = (
        "sample_index",
        "time_seconds",
        "regime",
        "rms_active_power_pu",
        "fmpy_active_power_pu",
        "absolute_active_power_error_pu",
        "active_power_budget_pu",
        "rms_reactive_power_pu",
        "fmpy_reactive_power_pu",
        "absolute_reactive_power_error_pu",
        "reactive_power_budget_pu",
        "power_flow_residual_term_pu",
        "rms_residual_term_pu",
        "floating_absolute_term_pu",
        "floating_relative_active_term_pu",
        "floating_relative_reactive_term_pu",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer: csv.writer = csv.writer(csv_file)
        writer.writerow(header)
        sample_index: int
        for sample_index in range(rms_time_seconds.size):
            if sample_index == 0:
                regime: str = "initial_projection"
                power_flow_term: float = power_flow_residual
            else:
                regime = "accepted_step"
                power_flow_term = 0.0
            row: tuple[object, ...] = (
                sample_index,
                f"{direct_time_seconds[sample_index]:.16e}",
                regime,
                f"{rms_active_power[sample_index]:.16e}",
                f"{direct_active_power[sample_index]:.16e}",
                f"{absolute_active_power_error[sample_index]:.16e}",
                f"{active_power_budget[sample_index]:.16e}",
                f"{rms_reactive_power[sample_index]:.16e}",
                f"{direct_reactive_power[sample_index]:.16e}",
                f"{absolute_reactive_power_error[sample_index]:.16e}",
                f"{reactive_power_budget[sample_index]:.16e}",
                f"{power_flow_term:.16e}",
                f"{rms_solver_tolerance:.16e}",
                f"{absolute_tolerance:.16e}",
                f"{relative_tolerance * abs(direct_active_power[sample_index]):.16e}",
                f"{relative_tolerance * abs(direct_reactive_power[sample_index]):.16e}",
            )
            writer.writerow(row)
    return csv_path


def _configure_scientific_axis(axis: Axes, y_label: str) -> None:
    """Apply restrained scientific styling to one comparison axis.

    :param axis: Matplotlib axes to configure.
    :param y_label: Physical quantity and unit shown on the vertical axis.
    :return: None.
    """

    axis.set_ylabel(y_label)
    axis.set_axisbelow(True)
    axis.grid(
        visible=True,
        which="major",
        axis="both",
        color="#d9d9d9",
        linewidth=0.6,
    )
    axis.tick_params(direction="out", width=0.8, length=3.5)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_linewidth(0.8)
    axis.spines["bottom"].set_linewidth(0.8)
    axis.ticklabel_format(
        axis="y",
        style="sci",
        scilimits=(-3, 3),
        useMathText=True,
    )


def _save_figure_formats(figure: Figure, output_base: Path) -> tuple[Path, ...]:
    """Save PDF/SVG vector masters and a 300 dpi PNG review raster.

    :param figure: Fully composed Matplotlib figure.
    :param output_base: Output path without an extension.
    :return: Written PDF, SVG and PNG paths.
    """

    pdf_path: Path = output_base.with_suffix(".pdf")
    svg_path: Path = output_base.with_suffix(".svg")
    png_path: Path = output_base.with_suffix(".png")
    with matplotlib.rc_context():
        # These scoped settings preserve editable SVG text and portable PDF
        # fonts without leaking state into VeraGrid or another imported module.
        matplotlib.rcParams["svg.fonttype"] = "none"
        matplotlib.rcParams["pdf.fonttype"] = 42
        matplotlib.rcParams["ps.fonttype"] = 42
        figure.savefig(pdf_path, format="pdf", bbox_inches="tight")
        figure.savefig(svg_path, format="svg", bbox_inches="tight")
        figure.savefig(png_path, format="png", dpi=300, bbox_inches="tight")
    return pdf_path, svg_path, png_path


def _render_trajectory_figure(
        output_base: Path,
        mode: FmuInterfaceMode,
        time_seconds: np.ndarray,
        rms_active_power: np.ndarray,
        rms_reactive_power: np.ndarray,
        direct_active_power: np.ndarray,
        direct_reactive_power: np.ndarray,
) -> tuple[Path, ...]:
    """Render aligned P/Q trajectories without validation decoration.

    :param output_base: Output path without an extension.
    :param mode: FMI interface mode represented by the trajectories.
    :param time_seconds: Exact common time lattice.
    :param rms_active_power: VeraGrid RMS active power in p.u.
    :param rms_reactive_power: VeraGrid RMS reactive power in p.u.
    :param direct_active_power: Direct FMPy active power in p.u.
    :param direct_reactive_power: Direct FMPy reactive power in p.u.
    :return: Written PDF, SVG and PNG paths.
    """

    if mode == FmuInterfaceMode.CO_SIMULATION:
        interface_label: str = "Co-Simulation"
    elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
        interface_label = "Model Exchange"
    else:
        raise ValueError(f"Unsupported RMS FMI figure mode: {mode.value}")

    figure: Figure = Figure(figsize=(7.2, 4.8), constrained_layout=True)
    canvas: FigureCanvasAgg = FigureCanvasAgg(figure)
    active_axis: Axes = figure.add_subplot(2, 1, 1)
    reactive_axis: Axes = figure.add_subplot(2, 1, 2, sharex=active_axis)
    active_axis.plot(
        time_seconds,
        rms_active_power,
        color="#222222",
        linestyle="-",
        linewidth=1.5,
        label="VeraGrid RMS",
    )
    active_axis.plot(
        time_seconds,
        direct_active_power,
        color="#0072B2",
        linestyle="--",
        linewidth=1.4,
        label="Direct FMPy backend",
    )
    reactive_axis.plot(
        time_seconds,
        rms_reactive_power,
        color="#222222",
        linestyle="-",
        linewidth=1.5,
    )
    reactive_axis.plot(
        time_seconds,
        direct_reactive_power,
        color="#0072B2",
        linestyle="--",
        linewidth=1.4,
    )
    _configure_scientific_axis(active_axis, "Active power (p.u.)")
    _configure_scientific_axis(reactive_axis, "Reactive power (p.u.)")
    active_axis.tick_params(labelbottom=False)
    reactive_axis.set_xlabel("Time (s)")
    active_axis.legend(loc="best", frameon=False, ncol=2)
    figure.suptitle(
        f"RMS FMI 2 {interface_label} trajectories",
        fontsize=11,
        fontweight="normal",
    )
    canvas.draw()
    output_paths: tuple[Path, ...] = _save_figure_formats(figure, output_base)
    figure.clear()
    return output_paths


def _render_error_figure(
        output_base: Path,
        mode: FmuInterfaceMode,
        time_seconds: np.ndarray,
        metrics: RmsFmiComparisonMetrics,
) -> tuple[Path, ...]:
    """Render absolute P/Q error against each per-sample derived budget.

    :param output_base: Output path without an extension.
    :param mode: FMI interface mode represented by the errors.
    :param time_seconds: Exact common time lattice.
    :param metrics: Passed errors and per-sample acceptance budgets.
    :return: Written PDF, SVG and PNG paths.
    """

    if mode == FmuInterfaceMode.CO_SIMULATION:
        interface_label: str = "Co-Simulation"
    elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
        interface_label = "Model Exchange"
    else:
        raise ValueError(f"Unsupported RMS FMI figure mode: {mode.value}")

    absolute_active_power_error: np.ndarray = (
        metrics.get_absolute_active_power_error()
    )
    absolute_reactive_power_error: np.ndarray = (
        metrics.get_absolute_reactive_power_error()
    )
    active_power_budget: np.ndarray = metrics._active_power_budget.copy()
    reactive_power_budget: np.ndarray = metrics._reactive_power_budget.copy()
    figure: Figure = Figure(figsize=(7.2, 4.8), constrained_layout=True)
    canvas: FigureCanvasAgg = FigureCanvasAgg(figure)
    active_axis: Axes = figure.add_subplot(2, 1, 1)
    reactive_axis: Axes = figure.add_subplot(2, 1, 2, sharex=active_axis)
    active_axis.plot(
        time_seconds,
        absolute_active_power_error,
        color="#222222",
        linestyle="-",
        linewidth=1.5,
        label="Absolute error",
    )
    active_axis.plot(
        time_seconds,
        active_power_budget,
        color="#0072B2",
        linestyle="--",
        linewidth=1.4,
        label="Derived budget",
    )
    reactive_axis.plot(
        time_seconds,
        absolute_reactive_power_error,
        color="#222222",
        linestyle="-",
        linewidth=1.5,
    )
    reactive_axis.plot(
        time_seconds,
        reactive_power_budget,
        color="#0072B2",
        linestyle="--",
        linewidth=1.4,
    )
    _configure_scientific_axis(active_axis, "Absolute P error (p.u.)")
    _configure_scientific_axis(reactive_axis, "Absolute Q error (p.u.)")
    active_axis.tick_params(labelbottom=False)
    reactive_axis.set_xlabel("Time (s)")
    active_axis.legend(loc="best", frameon=False, ncol=2)
    figure.suptitle(
        f"RMS FMI 2 {interface_label} absolute error",
        fontsize=11,
        fontweight="normal",
    )
    canvas.draw()
    output_paths: tuple[Path, ...] = _save_figure_formats(figure, output_base)
    figure.clear()
    return output_paths


def _artifact_record(path: Path, staging_dir: Path) -> dict[str, object]:
    """Build one relative content-identity record for the package manifest.

    :param path: Retained artifact file.
    :param staging_dir: Package staging root.
    :return: Relative path, SHA-256 and byte size.
    """

    relative_path: str = path.relative_to(staging_dir).as_posix()
    return dict(
        path=relative_path,
        sha256=_hash_file(path),
        size_bytes=path.stat().st_size,
    )


def _write_staged_manifest(
        staging_dir: Path,
        config: RmsFmiComparisonConfig,
        cs_execution: RmsFmiExampleExecution,
        me_execution: RmsFmiExampleExecution,
        cs_metrics: RmsFmiComparisonMetrics,
        me_metrics: RmsFmiComparisonMetrics,
        cs_fmu_sha256: str,
        me_fmu_sha256: str,
) -> Path:
    """Write the package manifest last, after every retained artifact exists.

    :param staging_dir: Complete owned staging directory.
    :param config: Caller-declared source identity and floating tolerances.
    :param cs_execution: Conclusive RMS Co-Simulation execution.
    :param me_execution: Conclusive RMS Model Exchange execution.
    :param cs_metrics: Passed Co-Simulation comparison metrics.
    :param me_metrics: Passed Model Exchange comparison metrics.
    :param cs_fmu_sha256: FMU identity recorded before either CS consumer ran.
    :param me_fmu_sha256: FMU identity recorded before either ME consumer ran.
    :return: Written manifest path.
    """

    # Byte identity must remain unchanged after native and direct consumers have
    # both executed the archive.
    if _hash_file(cs_execution.get_fmu_path()) == cs_fmu_sha256:
        pass
    else:
        raise RuntimeError("Co-Simulation FMU bytes changed during comparison")
    if _hash_file(me_execution.get_fmu_path()) == me_fmu_sha256:
        pass
    else:
        raise RuntimeError("Model Exchange FMU bytes changed during comparison")

    artifact_paths: list[Path] = list()
    candidate_path: Path
    for candidate_path in sorted(staging_dir.rglob("*")):
        if candidate_path.is_file():
            artifact_paths.append(candidate_path)
        else:
            pass
    artifact_records: list[dict[str, object]] = list()
    for candidate_path in artifact_paths:
        artifact_records.append(_artifact_record(candidate_path, staging_dir))

    absolute_tolerance: float = config.get_absolute_tolerance()
    relative_tolerance: float = config.get_relative_tolerance()
    cs_mode_record: dict[str, object] = dict(
        mode=FmuInterfaceMode.CO_SIMULATION.value,
        fmu_path=cs_execution.get_fmu_path().relative_to(staging_dir).as_posix(),
        fmu_sha256=cs_fmu_sha256,
        report_path=(
            cs_execution.get_report_path().relative_to(staging_dir).as_posix()
        ),
        validation_issues=list(),
        sample_count=cs_execution.get_time_seconds().size,
        power_flow_residual=cs_execution.get_power_flow_residual(),
        rms_solver_tolerance=cs_execution.get_solver_tolerance(),
        max_active_power_error=cs_metrics.get_max_active_power_error(),
        max_reactive_power_error=cs_metrics.get_max_reactive_power_error(),
        rms_active_power_error=cs_metrics.get_rms_active_power_error(),
        rms_reactive_power_error=cs_metrics.get_rms_reactive_power_error(),
    )
    me_mode_record: dict[str, object] = dict(
        mode=FmuInterfaceMode.MODEL_EXCHANGE.value,
        fmu_path=me_execution.get_fmu_path().relative_to(staging_dir).as_posix(),
        fmu_sha256=me_fmu_sha256,
        report_path=(
            me_execution.get_report_path().relative_to(staging_dir).as_posix()
        ),
        validation_issues=list(),
        sample_count=me_execution.get_time_seconds().size,
        power_flow_residual=me_execution.get_power_flow_residual(),
        rms_solver_tolerance=me_execution.get_solver_tolerance(),
        max_active_power_error=me_metrics.get_max_active_power_error(),
        max_reactive_power_error=me_metrics.get_max_reactive_power_error(),
        rms_active_power_error=me_metrics.get_rms_active_power_error(),
        rms_reactive_power_error=me_metrics.get_rms_reactive_power_error(),
    )
    manifest_payload: dict[str, object] = dict(
        schema="veragrid.rms-fmi-comparison/1",
        status="CANDIDATE_EVIDENCE",
        claim_scope=(
            "VeraGrid RMS FMI 2 integration and orchestration compared with "
            "direct execution through the same FMPy backend"
        ),
        backend_disclosure=(
            "FMPy is the FMI 2 runtime backend used by VeraGrid in this lane; "
            "this is not an independent-runtime interoperability claim"
        ),
        source_identity=dict(
            revision=config.get_source_revision(),
            source_tree_sha256=config.get_source_tree_sha256(),
            provenance="caller_declared",
            verification="UNVERIFIED_BY_GENERATOR",
        ),
        configuration=dict(
            time_step_seconds=1.0e-3,
            stop_time_seconds=5.0e-3,
            sample_count=6,
            time_alignment_tolerance_seconds=1.0e-12,
            floating_absolute_term=absolute_tolerance,
            floating_relative_coefficient=relative_tolerance,
            initial_budget_formula=(
                "power_flow_residual + rms_solver_tolerance + "
                "absolute_term + relative_coefficient*abs(direct_fmpy)"
            ),
            accepted_step_budget_formula=(
                "rms_solver_tolerance + absolute_term + "
                "relative_coefficient*abs(direct_fmpy)"
            ),
            initial_sample_indices=list((0,)),
            accepted_step_indices=list((1, 2, 3, 4, 5)),
        ),
        modes=list((cs_mode_record, me_mode_record)),
        runtime=dict(
            python=platform.python_version(),
            platform=platform.platform(),
            numpy=importlib.metadata.version("numpy"),
            matplotlib=importlib.metadata.version("matplotlib"),
            fmpy=importlib.metadata.version("fmpy"),
            byte_order=sys.byteorder,
        ),
        artifacts=artifact_records,
    )
    manifest_path: Path = staging_dir / "manifest.json"
    manifest_text: str = json.dumps(
        manifest_payload,
        indent=2,
        sort_keys=True,
    ) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    return manifest_path


def _verify_staged_package(staging_dir: Path) -> None:
    """Parse the staged manifest and rehash every declared artifact.

    :param staging_dir: Complete package staging directory.
    :return: None.
    """

    manifest_path: Path = staging_dir / "manifest.json"
    if manifest_path.is_file() and not manifest_path.is_symlink():
        pass
    else:
        raise RuntimeError("Staged RMS FMI package lacks a regular manifest")
    manifest_payload: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(manifest_payload, dict):
        pass
    else:
        raise RuntimeError("Staged RMS FMI manifest root must be an object")

    schema_value: object = manifest_payload.get("schema", None)
    status_value: object = manifest_payload.get("status", None)
    artifact_records_value: object = manifest_payload.get("artifacts", None)
    if (
        schema_value == "veragrid.rms-fmi-comparison/1"
        and status_value == "CANDIDATE_EVIDENCE"
        and isinstance(artifact_records_value, list)
    ):
        artifact_records: list[object] = artifact_records_value
    else:
        raise RuntimeError("Staged RMS FMI manifest contract is incomplete")

    staging_root: Path = staging_dir.resolve()
    declared_paths: set[str] = set()
    artifact_record_value: object
    for artifact_record_value in artifact_records:
        if isinstance(artifact_record_value, dict):
            relative_value: object = artifact_record_value.get("path", None)
            hash_value: object = artifact_record_value.get("sha256", None)
            size_value: object = artifact_record_value.get("size_bytes", None)
        else:
            raise RuntimeError("Staged artifact record must be an object")
        record_is_typed: bool = bool(
            isinstance(relative_value, str)
            and isinstance(hash_value, str)
            and isinstance(size_value, int)
        )
        if record_is_typed:
            relative_path: str = relative_value
            declared_hash: str = hash_value
            declared_size: int = size_value
        else:
            raise RuntimeError("Staged artifact record fields have invalid types")

        relative_candidate: Path = Path(relative_path)
        path_is_relative: bool = bool(
            not relative_candidate.is_absolute()
            and ".." not in relative_candidate.parts
            and relative_path not in declared_paths
        )
        if path_is_relative:
            artifact_path: Path = (staging_root / relative_candidate).resolve()
            declared_paths.add(relative_path)
        else:
            raise RuntimeError("Manifest artifact path is unsafe or duplicated")
        try:
            artifact_path.relative_to(staging_root)
        except ValueError as path_error:
            raise RuntimeError("Manifest artifact escapes the staging directory") from path_error

        artifact_is_valid: bool = bool(
            artifact_path.is_file()
            and not artifact_path.is_symlink()
            and artifact_path.stat().st_size == declared_size
            and _hash_file(artifact_path) == declared_hash
        )
        if artifact_is_valid:
            pass
        else:
            raise RuntimeError(f"Staged artifact failed identity check: {relative_path}")

    actual_paths: set[str] = set()
    actual_path: Path
    for actual_path in staging_root.rglob("*"):
        if actual_path.is_file() and actual_path != manifest_path:
            actual_paths.add(actual_path.relative_to(staging_root).as_posix())
        else:
            pass
    if actual_paths == declared_paths:
        pass
    else:
        raise RuntimeError("Staged manifest does not cover the complete artifact tree")


def _publish_staged_package(staging_dir: Path, final_dir: Path) -> Path:
    """Verify and atomically rename one owned sibling staging directory.

    :param staging_dir: Owned complete staging directory.
    :param final_dir: Nonexistent final package destination.
    :return: Published final directory.
    """

    same_parent: bool = bool(
        staging_dir.resolve().parent == final_dir.resolve().parent
    )
    if same_parent and not final_dir.exists():
        pass
    else:
        raise FileExistsError(
            "Atomic publication requires sibling staging and a nonexistent destination"
        )
    _verify_staged_package(staging_dir)
    os.replace(staging_dir, final_dir)
    return final_dir


def generate_rms_fmi_comparison(config: RmsFmiComparisonConfig) -> Path:
    """Generate and atomically publish the complete RMS FMI comparison package.

    :param config: Validated destination, provenance and floating tolerances.
    :return: Published package directory.
    """

    final_dir: Path = config.get_output_dir()
    if final_dir.exists():
        raise FileExistsError(f"RMS FMI comparison destination exists: {final_dir}")
    else:
        final_dir.parent.mkdir(parents=True, exist_ok=True)

    staging_dir: Path = Path(
        tempfile.mkdtemp(
            prefix=f".{final_dir.name}.stage-",
            dir=str(final_dir.parent),
        )
    ).resolve()
    published: bool = False
    try:
        cs_dir: Path = staging_dir / "co_simulation"
        me_dir: Path = staging_dir / "model_exchange"
        figures_dir: Path = staging_dir / "figures"
        cs_dir.mkdir()
        me_dir.mkdir()
        figures_dir.mkdir()

        # Each mode exports once. The same exact archive path then feeds native
        # RMS execution, direct FMPy execution, artifact hashing and publication.
        cs_execution: RmsFmiExampleExecution = execute_rms_fmi_example(
            cs_dir,
            FmuInterfaceMode.CO_SIMULATION,
        )
        cs_fmu_sha256: str = _hash_file(cs_execution.get_fmu_path())
        cs_validation_issues: list[str] = validate_cs_fmu_with_fmpy(
            cs_execution.get_fmu_path(),
            extraction_root=cs_dir,
        )
        if len(cs_validation_issues) == 0:
            pass
        else:
            raise RuntimeError(
                f"Co-Simulation FMU validation issues: {cs_validation_issues}"
            )
        cs_direct_time: np.ndarray
        cs_direct_active_power: np.ndarray
        cs_direct_reactive_power: np.ndarray
        (
            cs_direct_time,
            cs_direct_active_power,
            cs_direct_reactive_power,
        ) = _get_direct_fmpy_trace(cs_execution, cs_dir)
        cs_metrics: RmsFmiComparisonMetrics = _compare_aligned_trajectories(
            rms_time_seconds=cs_execution.get_time_seconds(),
            rms_active_power=cs_execution.get_active_power(),
            rms_reactive_power=cs_execution.get_reactive_power(),
            direct_time_seconds=cs_direct_time,
            direct_active_power=cs_direct_active_power,
            direct_reactive_power=cs_direct_reactive_power,
            rms_solver_tolerance=cs_execution.get_solver_tolerance(),
            power_flow_residual=cs_execution.get_power_flow_residual(),
            absolute_tolerance=config.get_absolute_tolerance(),
            relative_tolerance=config.get_relative_tolerance(),
        )

        me_execution: RmsFmiExampleExecution = execute_rms_fmi_example(
            me_dir,
            FmuInterfaceMode.MODEL_EXCHANGE,
        )
        me_fmu_sha256: str = _hash_file(me_execution.get_fmu_path())
        me_validation_issues: list[str] = validate_me_fmu_with_fmpy(
            me_execution.get_fmu_path(),
            extraction_root=me_dir,
        )
        if len(me_validation_issues) == 0:
            pass
        else:
            raise RuntimeError(
                f"Model Exchange FMU validation issues: {me_validation_issues}"
            )
        me_direct_time: np.ndarray
        me_direct_active_power: np.ndarray
        me_direct_reactive_power: np.ndarray
        (
            me_direct_time,
            me_direct_active_power,
            me_direct_reactive_power,
        ) = _get_direct_fmpy_trace(me_execution, me_dir)
        me_metrics: RmsFmiComparisonMetrics = _compare_aligned_trajectories(
            rms_time_seconds=me_execution.get_time_seconds(),
            rms_active_power=me_execution.get_active_power(),
            rms_reactive_power=me_execution.get_reactive_power(),
            direct_time_seconds=me_direct_time,
            direct_active_power=me_direct_active_power,
            direct_reactive_power=me_direct_reactive_power,
            rms_solver_tolerance=me_execution.get_solver_tolerance(),
            power_flow_residual=me_execution.get_power_flow_residual(),
            absolute_tolerance=config.get_absolute_tolerance(),
            relative_tolerance=config.get_relative_tolerance(),
        )

        _write_trace_csv(
            staging_dir / "co_simulation_trace.csv",
            cs_execution,
            cs_direct_time,
            cs_direct_active_power,
            cs_direct_reactive_power,
            cs_metrics,
            config.get_absolute_tolerance(),
            config.get_relative_tolerance(),
        )
        _write_trace_csv(
            staging_dir / "model_exchange_trace.csv",
            me_execution,
            me_direct_time,
            me_direct_active_power,
            me_direct_reactive_power,
            me_metrics,
            config.get_absolute_tolerance(),
            config.get_relative_tolerance(),
        )
        _render_trajectory_figure(
            figures_dir / "co_simulation_trajectories",
            FmuInterfaceMode.CO_SIMULATION,
            cs_execution.get_time_seconds(),
            cs_execution.get_active_power(),
            cs_execution.get_reactive_power(),
            cs_direct_active_power,
            cs_direct_reactive_power,
        )
        _render_error_figure(
            figures_dir / "co_simulation_absolute_error",
            FmuInterfaceMode.CO_SIMULATION,
            cs_execution.get_time_seconds(),
            cs_metrics,
        )
        _render_trajectory_figure(
            figures_dir / "model_exchange_trajectories",
            FmuInterfaceMode.MODEL_EXCHANGE,
            me_execution.get_time_seconds(),
            me_execution.get_active_power(),
            me_execution.get_reactive_power(),
            me_direct_active_power,
            me_direct_reactive_power,
        )
        _render_error_figure(
            figures_dir / "model_exchange_absolute_error",
            FmuInterfaceMode.MODEL_EXCHANGE,
            me_execution.get_time_seconds(),
            me_metrics,
        )

        _write_staged_manifest(
            staging_dir=staging_dir,
            config=config,
            cs_execution=cs_execution,
            me_execution=me_execution,
            cs_metrics=cs_metrics,
            me_metrics=me_metrics,
            cs_fmu_sha256=cs_fmu_sha256,
            me_fmu_sha256=me_fmu_sha256,
        )
        published_dir: Path = _publish_staged_package(staging_dir, final_dir)
        published = True
        return published_dir
    finally:
        # Cleanup is restricted to the unique staging directory created above.
        # A failed run never writes or removes the requested final destination.
        if not published and staging_dir.exists():
            shutil.rmtree(staging_dir)
        else:
            pass
