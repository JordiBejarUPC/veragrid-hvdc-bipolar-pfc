# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sys, os
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))
import matplotlib.pyplot as plt

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import SmallSignalStabilityEmtOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_results import SmallSignalStabilityEmtResults
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import SmallSignalStabilityEmtDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.transformer_rms_template import get_transformer2w_rms
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template_v2 import get_complete_generator_template_rms
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_transformer_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph

from VeraGridEngine.enumerations import (DynamicIntegrationMethod, ShuntConnectionType, RmsInitializationMethod,
                                         EmtSolverTypes, SmallSignalEmtBuildTypes, WindingType)

import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

def plot_s_domain_eigenvalues(
    eigenvalues_1: np.ndarray,
    eigenvalues_2: np.ndarray,
    label_1: str = "Solver 1",
    label_2: str = "Solver 2",
) -> None:
    """Plot and compare two sets of EMT eigenvalues on the complex plane."""

    eigenvalues_1 = np.asarray(eigenvalues_1, dtype=complex).ravel()
    eigenvalues_2 = np.asarray(eigenvalues_2, dtype=complex).ravel()

    # Remove invalid values before calculating limits and plotting.
    valid_1 = np.isfinite(eigenvalues_1.real) & np.isfinite(eigenvalues_1.imag)
    valid_2 = np.isfinite(eigenvalues_2.real) & np.isfinite(eigenvalues_2.imag)

    eigenvalues_1 = eigenvalues_1[valid_1]
    eigenvalues_2 = eigenvalues_2[valid_2]

    if eigenvalues_1.size == 0 and eigenvalues_2.size == 0:
        return

    # Calculate plot limits using both eigenvalue sets.
    all_eigenvalues = np.concatenate((eigenvalues_1, eigenvalues_2))
    all_re = np.real(all_eigenvalues)
    all_im = np.imag(all_eigenvalues)

    data_span_re = np.ptp(all_re)
    data_span_im = np.ptp(all_im)

    margin_x = max(data_span_re * 0.1, 1.0)
    margin_y = max(data_span_im * 0.1, 1.0)

    x_min = all_re.min() - margin_x
    x_max = all_re.max() + margin_x
    y_min = all_im.min() - margin_y
    y_max = all_im.max() + margin_y

    # Constant damping-ratio lines: zeta = 5 %.
    zeta = 0.05
    slope = np.sqrt(1.0 - zeta**2) / zeta

    x_z = np.linspace(min(-200.0, x_min), 0.0, 400)
    y_z = slope * x_z

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.plot(
        x_z,
        y_z,
        "--",
        color="grey",
        linewidth=0.7,
        alpha=0.6,
        label=r"$\zeta = 5\%$",
    )
    ax.plot(
        x_z,
        -y_z,
        "--",
        color="grey",
        linewidth=0.7,
        alpha=0.6,
    )

    if eigenvalues_1.size > 0:
        ax.scatter(
            eigenvalues_1.real,
            eigenvalues_1.imag,
            color="tab:blue",
            marker="o",
            s=100,
            alpha=0.8,
            label=label_1,
        )

    if eigenvalues_2.size > 0:
        ax.scatter(
            eigenvalues_2.real,
            eigenvalues_2.imag,
            color="tab:orange",
            marker="x",
            s=100,
            linewidths=2.0,
            alpha=0.8,
            label=label_2,
        )

    ax.set_title("S-Domain Stability Plot")
    ax.set_xlabel("Real [1/s]")
    ax.set_ylabel("Imaginary [rad/s]")

    ax.axhline(0.0, color="black", linewidth=1.0)
    ax.axvline(0.0, color="black", linewidth=1.0)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)

    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.tight_layout()
    plt.show(block=True)

def _format_complex_value(value: complex, decimals: int = 3) -> str:
    """Format a complex value for display inside a table cell."""
    if np.isclose(value.imag, 0.0):
        return f"{value.real:.{decimals}f}"

    return f"{value.real:.{decimals}f}{value.imag:+.{decimals}f}j"

def _plot_single_participation_factors_table(
    pfactors: np.ndarray,
    title: str,
    decimals: int = 2,
) -> None:
    """
    Plot one participation-factor matrix as a heatmap table.

    Rows: State 1, State 2, ...
    Columns: Mode 1, Mode 2, ...

    Cell text shows the complex participation factor.
    Cell color is based on abs(participation factor).
    """
    pfactors = np.asarray(pfactors, dtype=complex)

    if pfactors.ndim != 2:
        raise ValueError(
            "Each participation-factor set must be a 2D array with shape "
            "(n_states, n_modes)."
        )

    if pfactors.size == 0:
        return

    n_states, n_modes = pfactors.shape

    state_labels = [f"State {i + 1}" for i in range(n_states)]
    mode_labels = [f"Mode {j + 1}" for j in range(n_modes)]

    magnitudes = np.abs(pfactors)
    min_magnitude = magnitudes.min()
    max_magnitude = magnitudes.max()

    # Adaptive figure size:
    # - large enough for screen viewing
    # - cells become visually smaller when there are many rows/columns
    fig_width = min(max(10.0, 0.75 * n_modes + 3.0), 20.0)
    fig_height = min(max(7.0, 0.45 * n_states + 2.5), 14.0)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    try:
        fig.canvas.manager.set_window_title(title)
    except Exception:
        pass

    image = ax.imshow(
        magnitudes,
        cmap="Blues",
        aspect="auto",
        vmin=min_magnitude,
        vmax=max_magnitude if max_magnitude > min_magnitude else min_magnitude + 1.0,
    )

    ax.set_xticks(np.arange(n_modes))
    ax.set_yticks(np.arange(n_states))
    ax.set_xticklabels(mode_labels, fontsize=max(6, min(10, int(220 / max(n_modes, 1)))))
    ax.set_yticklabels(state_labels, fontsize=max(6, min(10, int(220 / max(n_states, 1)))))

    ax.tick_params(
        axis="x",
        top=True,
        bottom=False,
        labeltop=True,
        labelbottom=False,
    )

    ax.set_xlabel("Modes")
    ax.xaxis.set_label_position("top")
    ax.set_ylabel("States")
    ax.set_title(title, pad=25)

    # Cell borders
    ax.set_xticks(np.arange(-0.5, n_modes, 1.0), minor=True)
    ax.set_yticks(np.arange(-0.5, n_states, 1.0), minor=True)
    ax.grid(which="minor", color="black", linestyle="-", linewidth=0.4)
    ax.tick_params(which="minor", bottom=False, left=False)

    # Adaptive text size so cells look less crowded for large matrices
    cell_fontsize = max(5, min(9, int(180 / max(n_states, n_modes, 1))))

    color_range = max_magnitude - min_magnitude

    for i in range(n_states):
        for j in range(n_modes):
            magnitude = magnitudes[i, j]

            if color_range > 0.0:
                normalized = (magnitude - min_magnitude) / color_range
            else:
                normalized = 0.0

            text_color = "white" if normalized > 0.55 else "black"

            ax.text(
                j,
                i,
                _format_complex_value(pfactors[i, j], decimals=decimals),
                ha="center",
                va="center",
                color=text_color,
                fontsize=cell_fontsize,
            )

    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("|Participation factor|")

    fig.tight_layout()


def plot_two_participation_factors_tables(
    pfactors_1: np.ndarray,
    pfactors_2: np.ndarray,
    title_1: str = "Participation Factors - Set 1",
    title_2: str = "Participation Factors - Set 2",
    decimals: int = 2,
) -> None:
    """
    Plot two participation-factor matrices in two separate figures,
    so they can be visually compared at the same time.
    """
    _plot_single_participation_factors_table(
        pfactors=pfactors_1,
        title=title_1,
        decimals=decimals,
    )

    _plot_single_participation_factors_table(
        pfactors=pfactors_2,
        title=title_2,
        decimals=decimals,
    )

    plt.show(block=True)




#####################################################################################
#                    Kundur two-area grid
#####################################################################################

# This case follows the classical Kundur two-area benchmark as closely as the
# current VeraGrid RMS and EMT templates allow while keeping ONE common static
# operating point for both analyses.
#
# Deliberate modelling choices / limitations:
#   * no discrete shunt capacitor banks are added at buses 7 and 9, as requested;
#   * the published transmission-line charging B is retained (it is part of each
#     nominal-pi transmission line, not an additional bus shunt);
#   * the canonical 900-MVA synchronous-machine data are converted to the common
#     100-MVA system base before they are written into the VeraGrid templates;
#   * the RMS template represents the loads as constant PQ while the available EMT
#     load used here is a balanced RL (constant-impedance at the fundamental)
#     realization.  They share the same P/Q operating point, but their incremental
#     load characteristics are therefore not exactly identical;
#   * the complete generator templates contain AVR/governor/PSS blocks.  The PSS is
#     disabled and the governor is decoupled from speed as far as the current
#     templates permit.  Exact reproduction of every controller from Kundur would
#     require dedicated RMS and EMT controller templates with identical structure;
#   * the benchmark data do not define zero-sequence line/machine information.
#     The EMT network is therefore kept three-wire externally, and the synthetic
#     tower is used only to obtain physically sensible zero-sequence ratios.  The
#     positive-sequence R/X/B values are restored exactly after applying the tower.

GRID_SBASE_MVA = 100.0
KUNDUR_FBASE_HZ = 60.0
KUNDUR_PERIOD_S = 1.0 / KUNDUR_FBASE_HZ

KUNDUR_LINE_VNOM_KV = 230.0
KUNDUR_GEN_VNOM_KV = 20.0
KUNDUR_TRANSFORMER_SN_MVA = 900.0
KUNDUR_TRANSFORMER_X_MACHINE_PU = 0.15

# Original synchronous-machine base and per-unit data.
KUNDUR_MACHINE_SN_MVA = 900.0
KUNDUR_MACHINE_TO_SYSTEM_Z = GRID_SBASE_MVA / KUNDUR_MACHINE_SN_MVA
KUNDUR_MACHINE_TO_SYSTEM_H = KUNDUR_MACHINE_SN_MVA / GRID_SBASE_MVA

KUNDUR_RA_MACHINE_PU = 0.0025
KUNDUR_XD_MACHINE_PU = 1.80
KUNDUR_XQ_MACHINE_PU = 1.70
KUNDUR_XDP_MACHINE_PU = 0.30
KUNDUR_XQP_MACHINE_PU = 0.55
KUNDUR_XDPP_MACHINE_PU = 0.25
KUNDUR_XQPP_MACHINE_PU = 0.25
KUNDUR_XL_MACHINE_PU = 0.20
KUNDUR_TD0P_S = 8.0
KUNDUR_TQ0P_S = 0.4
KUNDUR_TD0PP_S = 0.03
KUNDUR_TQ0PP_S = 0.05

# Convert impedances from 900-MVA machine base to 100-MVA system base.
KUNDUR_RA_SYS_PU = KUNDUR_RA_MACHINE_PU * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XD_SYS_PU = KUNDUR_XD_MACHINE_PU * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XQ_SYS_PU = KUNDUR_XQ_MACHINE_PU * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XDP_SYS_PU = KUNDUR_XDP_MACHINE_PU * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XQP_SYS_PU = KUNDUR_XQP_MACHINE_PU * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XDPP_SYS_PU = KUNDUR_XDPP_MACHINE_PU * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XQPP_SYS_PU = KUNDUR_XQPP_MACHINE_PU * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XL_SYS_PU = KUNDUR_XL_MACHINE_PU * KUNDUR_MACHINE_TO_SYSTEM_Z

KUNDUR_TRANSFORMER_X_PU = (
    KUNDUR_TRANSFORMER_X_MACHINE_PU
    * GRID_SBASE_MVA
    / KUNDUR_TRANSFORMER_SN_MVA
)

# Classical inertia constants on the 900-MVA machine base.
KUNDUR_H_MACHINE_S = [6.50, 6.50, 6.175, 6.175]

# The RMS generator template uses M in the swing equation while the EMT Sauer-Pai
# template uses 2H.  Both values below are expressed on the 100-MVA system base.
KUNDUR_RMS_M = [
    2.0 * h * KUNDUR_MACHINE_TO_SYSTEM_H for h in KUNDUR_H_MACHINE_S
]
KUNDUR_EMT_H = [
    h * KUNDUR_MACHINE_TO_SYSTEM_H for h in KUNDUR_H_MACHINE_S
]

# No explicit damping torque in the canonical machine data.
KUNDUR_D_SYS_PU = 0.0

# Operating point used by the classical two-area benchmark.
# G3 is the slack and therefore its final P is determined by the power flow.
KUNDUR_GENERATOR_P_MW = [700.0, 700.0, 719.0, 700.0]
KUNDUR_GENERATOR_VSET_PU = [1.03, 1.01, 1.03, 1.01]
KUNDUR_LOAD_PQ_MVA = [(967.0, 100.0), (1767.0, 100.0)]

# Floquet discretisation.  Use an integer number of EMT steps per 60-Hz period so
# that one monodromy period closes on the discrete integration grid exactly.
EMT_STEPS_PER_PERIOD = 4000
EMT_TIME_STEP_S = KUNDUR_PERIOD_S / EMT_STEPS_PER_PERIOD
FLOQUET_ASSESSMENT_TIME_S = 0.20  # 12 power-frequency cycles
EMT_SIMULATION_TIME_S = FLOQUET_ASSESSMENT_TIME_S + 2.0 * KUNDUR_PERIOD_S

# Console-output controls.
PRINT_FULL_POWER_FLOW_TABLES = True
PRINT_RAW_EIGENVALUES = False
MAX_EIGENVALUES_IN_SUMMARY = 24


grid = gce.MultiCircuit(
    name="Kundur two-area RMS/EMT - realistic no bus shunts",
    Sbase=GRID_SBASE_MVA,
    fbase=KUNDUR_FBASE_HZ,
)

# Symmetrical-component transform, sequence order [0, 1, 2].
_a = np.exp(1j * 2.0 * np.pi / 3.0)
_T_012_TO_ABC = np.array(
    [
        [1.0, 1.0, 1.0],
        [1.0, _a ** 2, _a],
        [1.0, _a, _a ** 2],
    ],
    dtype=complex,
)
_T_ABC_TO_012 = np.linalg.inv(_T_012_TO_ABC)


def _safe_positive_ratio(numerator: float, denominator: float, default: float) -> float:
    """Return a finite positive ratio, otherwise a conservative fallback."""
    if abs(denominator) <= 1e-14:
        return default

    value = float(numerator / denominator)
    if not np.isfinite(value) or value <= 0.0:
        return default

    return value


def _build_kundur_230kv_tower() -> tuple[gce.OverheadLineType, gce.Wire]:
    """
    Build the three-phase architecture used by all Kundur 230-kV lines.

    The classical Kundur data set specifies positive-sequence line parameters but
    not conductor geometry or zero-sequence data.  The tower is therefore used only
    to create a physically meaningful ABC/zero-sequence architecture; the published
    positive-sequence R/X/B values are restored exactly afterwards.
    """
    wire = gce.Wire(
        name="Kundur 230-kV phase conductor",
        diameter=30.0,
        diameter_internal=0.0,
        is_tube=False,
        r=0.040,
        max_current=2.5,
    )

    tower = gce.OverheadLineType(
        name="Kundur 230-kV reference tower",
        Vnom=KUNDUR_LINE_VNOM_KV,
        earth_resistivity=100.0,
        frequency=grid.fBase,
    )

    tower.add_wire_relationship(wire=wire, xpos=-8.0, ypos=25.0, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=32.0, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=8.0, ypos=25.0, phase=3)
    tower.compute()

    if not tower.is_computed():
        raise RuntimeError("The Kundur 230-kV overhead-line tower could not be computed.")

    return tower, wire


def _set_transposed_kundur_line_matrices(
    line: gce.Line,
    r1: float,
    x1: float,
    b1: float,
    rate: float,
) -> None:
    """Rebuild a transposed ABC line whose positive sequence is exactly R1/X1/B1."""
    tower_r1 = float(line.R)
    tower_x1 = float(line.X)
    tower_b1 = float(line.B)
    tower_r0 = float(line.R0)
    tower_x0 = float(line.X0)
    tower_b0 = float(line.B0)

    r0_ratio = _safe_positive_ratio(tower_r0, tower_r1, default=3.0)
    x0_ratio = _safe_positive_ratio(tower_x0, tower_x1, default=3.0)
    b0_ratio = _safe_positive_ratio(tower_b0, tower_b1, default=1.0)

    r0 = r1 * r0_ratio
    x0 = x1 * x0_ratio
    b0 = b1 * b0_ratio

    # Passive transposed line: negative sequence equals positive sequence.
    z012 = np.diag(
        np.array(
            [
                complex(r0, x0),
                complex(r1, x1),
                complex(r1, x1),
            ],
            dtype=complex,
        )
    )
    zabc = _T_012_TO_ABC @ z012 @ _T_ABC_TO_012
    yabc_series = np.linalg.inv(zabc)

    # OverheadLineType stores line.ysh with the historical 1e6 scaling.
    y012_shunt_stored = np.diag(
        1j * 1e6 * np.array([b0, b1, b1], dtype=float)
    )
    yabc_shunt_stored = _T_012_TO_ABC @ y012_shunt_stored @ _T_ABC_TO_012

    ys_nabc = np.zeros((4, 4), dtype=complex)
    ysh_nabc = np.zeros((4, 4), dtype=complex)
    ys_nabc[1:4, 1:4] = yabc_series
    ysh_nabc[1:4, 1:4] = yabc_shunt_stored

    line.ys.values = ys_nabc
    line.ysh.values = ysh_nabc

    for admittance_matrix in (line.ys, line.ysh):
        admittance_matrix.phN = False
        admittance_matrix.phA = True
        admittance_matrix.phB = True
        admittance_matrix.phC = True

    # Scalars used by the positive-sequence PF/RMS path.
    line.R = r1
    line.X = x1
    line.B = b1
    line.R0 = r0
    line.X0 = x0
    line.B0 = b0
    line.R2 = r1
    line.X2 = x1
    line.B2 = b1
    line.rate = rate


def _make_kundur_line(
    name: str,
    bus_from: gce.Bus,
    bus_to: gce.Bus,
    r: float,
    x: float,
    b: float,
    rate: float,
    length_km: float,
    tower: gce.OverheadLineType,
) -> gce.Line:
    """Create one physical Kundur 230-kV line circuit with explicit length."""
    line = gce.Line(
        name=name,
        bus_from=bus_from,
        bus_to=bus_to,
        r=r,
        x=x,
        b=b,
        rate=rate,
        length=length_km,
    )

    # Create valid phase-domain flags/matrices first, then overwrite the matrices
    # with an exactly positive-sequence-consistent transposed equivalent.
    line.apply_template(tower, grid.Sbase, grid.fBase)
    _set_transposed_kundur_line_matrices(
        line=line,
        r1=r,
        x1=x,
        b1=b,
        rate=rate,
    )
    line.length = length_km
    return line


def _make_kundur_transformer(
    name: str,
    bus_hv: gce.Bus,
    bus_lv: gce.Bus,
) -> gce.Transformer2W:
    """Create one 900-MVA, 230/20-kV Kundur generator step-up transformer."""
    trafo = gce.Transformer2W(
        name=name,
        bus_from=bus_hv,
        bus_to=bus_lv,
        HV=KUNDUR_LINE_VNOM_KV,
        LV=KUNDUR_GEN_VNOM_KV,
        nominal_power=KUNDUR_TRANSFORMER_SN_MVA,
        design_rate=KUNDUR_TRANSFORMER_SN_MVA,
        rate=KUNDUR_TRANSFORMER_SN_MVA,
        r=0.0,
        x=KUNDUR_TRANSFORMER_X_PU,
        g=0.0,
        b=0.0,
        r0=0.0,
        x0=KUNDUR_TRANSFORMER_X_PU,
        b0=0.0,
        r2=0.0,
        x2=KUNDUR_TRANSFORMER_X_PU,
        b2=0.0,
    )

    # PF3 currently needs a supported winding connection to stamp Transformer2W.
    # Clock-0 grounded-star / grounded-star adds no artificial phase displacement.
    # The EMT symbolic transformer is attached separately as a three-wire ABC
    # floating-star interface below because the benchmark provides no neutral data.
    trafo.conn_f = WindingType.GroundedStar
    trafo.conn_t = WindingType.GroundedStar
    trafo.vector_group_number = 0
    trafo.phases = np.array([1, 2, 3], dtype=int)
    return trafo


def _validate_kundur_line_positive_sequence(lines: list[gce.Line]) -> None:
    """Verify that each stored ABC matrix reproduces its scalar Kundur R/X/B."""
    max_z_error = 0.0
    max_b_error = 0.0

    for line in lines:
        zabc = np.linalg.inv(np.asarray(line.ys.values[1:4, 1:4], dtype=complex))
        z012 = _T_ABC_TO_012 @ zabc @ _T_012_TO_ABC

        yabc = np.asarray(line.ysh.values[1:4, 1:4], dtype=complex) / 1e6
        y012 = _T_ABC_TO_012 @ yabc @ _T_012_TO_ABC

        max_z_error = max(max_z_error, abs(z012[1, 1] - complex(line.R, line.X)))
        max_b_error = max(max_b_error, abs(y012[1, 1].imag - line.B))

    if max_z_error > 1e-10 or max_b_error > 1e-10:
        raise RuntimeError(
            "Kundur line ABC conversion is inconsistent with positive-sequence data: "
            f"max |dZ1|={max_z_error:.3e}, max |dB1|={max_b_error:.3e}."
        )

    print(
        "Kundur 3ph line check: "
        f"max |dZ1|={max_z_error:.3e}, max |dB1|={max_b_error:.3e}"
    )


def _available_model_parameter_names(block: Block) -> set[str]:
    """Return all recursively available event/parameter names in a DAE block."""
    names: set[str] = set()
    for child in block.get_all_blocks():
        names.update(var.name for var in child.event_dict.keys())
        names.update(var.name for var in child.parameters)
    return names


def _set_model_parameters(
    block: Block,
    values: dict[str, float],
    model_label: str,
) -> None:
    """Set model parameters and report names that are unavailable in this template."""
    available = _available_model_parameter_names(block)
    missing: list[str] = []

    for name, value in values.items():
        if name in available:
            block.set_parameter_in_model(var_name=name, new_value=value)
        else:
            missing.append(name)

    if missing:
        print(f"{model_label}: parameters not exposed by this template: {missing}")


def _patch_emt_governor_to_constant_mechanical_torque(generator_model: Block) -> bool:
    """
    Remove speed/electrical-torque feedback from the EMT governor as far as possible.

    The complete EMT template currently contains a governor block.  The classical
    Kundur benchmark operating case does not require primary governor dynamics for
    the small-signal electromechanical benchmark.  Replacing the first governor
    state equation by a stable decay keeps the initialized Pm_ref as the mechanical
    torque command while avoiding Te feedback into the governor.
    """
    for block in generator_model.get_all_blocks():
        if "governor" not in block.name.lower():
            continue

        y_gov0 = next((var for var in block.state_vars if var.name == "y_gov0"), None)
        t1_gov = next((var for var in block.event_dict.keys() if var.name == "T1_gov"), None)

        if y_gov0 is None or t1_gov is None or len(block.state_eqs) == 0:
            continue

        block.state_eqs[0] = -y_gov0 / t1_gov
        return True

    return False


def _set_generator_sequence_fallbacks(generator: gce.Generator) -> None:
    """Set benign sequence-data fallbacks when those properties exist."""
    # These values are not part of the positive-sequence Kundur benchmark.  They
    # should remain dynamically dormant in the balanced, external three-wire case.
    fallback_pairs = {
        "R0": KUNDUR_RA_SYS_PU,
        "X0": KUNDUR_XDPP_SYS_PU,
        "R2": KUNDUR_RA_SYS_PU,
        "X2": KUNDUR_XDPP_SYS_PU,
        "r0": KUNDUR_RA_SYS_PU,
        "x0": KUNDUR_XDPP_SYS_PU,
        "r2": KUNDUR_RA_SYS_PU,
        "x2": KUNDUR_XDPP_SYS_PU,
    }
    for attribute, value in fallback_pairs.items():
        if hasattr(generator, attribute):
            setattr(generator, attribute, value)


def _print_case_definition() -> None:
    """Print the key benchmark and numerical assumptions used by this script."""
    print("\n=== Kundur two-area RMS/EMT benchmark definition ===")
    print(f"System base: {grid.Sbase:.1f} MVA, frequency: {grid.fBase:.1f} Hz")
    print(
        "Generators P set-points [MW]: "
        + ", ".join(f"G{i + 1}={p:.1f}" for i, p in enumerate(KUNDUR_GENERATOR_P_MW))
        + " (G3 is slack)"
    )
    print(
        "Generator V set-points [pu]: "
        + ", ".join(f"G{i + 1}={v:.3f}" for i, v in enumerate(KUNDUR_GENERATOR_VSET_PU))
    )
    print(
        "Loads [MW + jMVAr]: "
        f"Bus7={KUNDUR_LOAD_PQ_MVA[0][0]:.1f}+j{KUNDUR_LOAD_PQ_MVA[0][1]:.1f}, "
        f"Bus9={KUNDUR_LOAD_PQ_MVA[1][0]:.1f}+j{KUNDUR_LOAD_PQ_MVA[1][1]:.1f}"
    )
    print("Bus shunt capacitor banks: NONE (requested). Line-charging B is retained.")
    print(
        "Machine data (900 -> 100 MVA base): "
        f"Ra={KUNDUR_RA_SYS_PU:.7f}, Xd={KUNDUR_XD_SYS_PU:.6f}, "
        f"Xq={KUNDUR_XQ_SYS_PU:.6f}, Xd'={KUNDUR_XDP_SYS_PU:.6f}, "
        f"Xq'={KUNDUR_XQP_SYS_PU:.6f}, Xd''={KUNDUR_XDPP_SYS_PU:.6f}, "
        f"Xq''={KUNDUR_XQPP_SYS_PU:.6f}, Xl={KUNDUR_XL_SYS_PU:.6f}"
    )
    print(
        "Inertia: H(machine)="
        + str(KUNDUR_H_MACHINE_S)
        + f" s; RMS M(system)={KUNDUR_RMS_M}; EMT H(system)={KUNDUR_EMT_H}"
    )
    print("Damping D=0; PSS disabled (Ks=0).")
    print(
        "Load-model limitation: RMS uses constant PQ; EMT uses balanced RL. "
        "The equilibrium P/Q is shared, but the incremental characteristic differs."
    )
    print(
        "Controller limitation: complete VeraGrid generator templates are retained for "
        "RMS/EMT structural compatibility; PSS is disabled and governor feedback is "
        "suppressed as far as the current templates permit."
    )
    print(
        f"Floquet: T={KUNDUR_PERIOD_S:.9f} s, dt={EMT_TIME_STEP_S:.12g} s, "
        f"steps/period={KUNDUR_PERIOD_S / EMT_TIME_STEP_S:.0f}, "
        f"assessment={FLOQUET_ASSESSMENT_TIME_S:.3f} s "
        f"({FLOQUET_ASSESSMENT_TIME_S / KUNDUR_PERIOD_S:.1f} cycles)."
    )


def _print_eigenvalue_summary(
    label: str,
    eigenvalues: np.ndarray,
    period: float | None = None,
    max_rows: int = MAX_EIGENVALUES_IN_SUMMARY,
) -> None:
    """Print the most critical finite eigenvalues with control-relevant metrics."""
    eig = np.asarray(eigenvalues, dtype=complex).ravel()
    valid = np.isfinite(eig.real) & np.isfinite(eig.imag)
    eig = eig[valid]

    if eig.size == 0:
        print(f"\n{label}: no finite eigenvalues.")
        return

    stability_tol = 1e-6
    n_unstable = int(np.sum(eig.real > stability_tol))
    n_neutral = int(np.sum(np.abs(eig.real) <= stability_tol))
    n_stable = int(np.sum(eig.real < -stability_tol))

    order = np.argsort(eig.real)[::-1]
    eig = eig[order]

    print(f"\n=== {label} eigenvalue summary ===")
    print(
        f"finite={eig.size}, stable={n_stable}, near-neutral={n_neutral}, "
        f"unstable={n_unstable} (Re tolerance={stability_tol:.1e} 1/s)"
    )
    print("Most critical modes (largest real part first):")

    header = " idx       Re[1/s]       Im[rad/s]       f[Hz]       zeta       tau[s]"
    if period is not None:
        header += "       |mu|"
    print(header)

    for idx, value in enumerate(eig[:max_rows]):
        magnitude = abs(value)
        frequency_hz = abs(value.imag) / (2.0 * np.pi)
        zeta = -value.real / magnitude if magnitude > 1e-14 else np.nan
        tau = 1.0 / abs(value.real) if abs(value.real) > 1e-12 else np.inf

        row = (
            f"{idx:4d}  {value.real:13.6e}  {value.imag:13.6e}  "
            f"{frequency_hz:10.6f}  {zeta:9.5f}  {tau:11.4g}"
        )
        if period is not None:
            row += f"  {np.exp(value.real * period):11.8f}"
        print(row)


def _print_floquet_multiplier_summary(results: SmallSignalStabilityEmtResults) -> None:
    """Print Floquet-multiplier diagnostics when exposed by the result object."""
    multipliers = getattr(results, "multipliers", None)
    if multipliers is None:
        multipliers = getattr(results, "floquet_multipliers", None)

    if multipliers is None:
        print("Floquet multiplier array is not exposed by this result object.")
        return

    mu = np.asarray(multipliers, dtype=complex).ravel()
    valid = np.isfinite(mu.real) & np.isfinite(mu.imag)
    mu = mu[valid]
    if mu.size == 0:
        print("Floquet multiplier array contains no finite values.")
        return

    abs_mu = np.abs(mu)
    print("\n=== Floquet multiplier diagnostics ===")
    print(f"finite multipliers: {mu.size}")
    print(f"max |mu|: {abs_mu.max():.10f}")
    print(f"min |mu|: {abs_mu.min():.10f}")
    print(f"multipliers with |mu| > 1+1e-6: {int(np.sum(abs_mu > 1.0 + 1e-6))}")
    print(f"closest multiplier to +1: {mu[np.argmin(np.abs(mu - 1.0))]}")


#####################################################################################
#                    Buses
#####################################################################################

# Use Generator 3 as the angular/reference machine, matching the VeraGrid Kundur
# benchmark convention.  Its final active power is therefore determined by the
# solved load flow while G1, G2 and G4 retain their scheduled active powers.
bus1 = gce.Bus(name="Bus1", Vnom=KUNDUR_GEN_VNOM_KV)
bus2 = gce.Bus(name="Bus2", Vnom=KUNDUR_GEN_VNOM_KV)
bus3 = gce.Bus(name="Bus3", Vnom=KUNDUR_GEN_VNOM_KV, is_slack=True)
bus4 = gce.Bus(name="Bus4", Vnom=KUNDUR_GEN_VNOM_KV)
bus5 = gce.Bus(name="Bus5", Vnom=KUNDUR_LINE_VNOM_KV)
bus6 = gce.Bus(name="Bus6", Vnom=KUNDUR_LINE_VNOM_KV)
bus7 = gce.Bus(name="Bus7", Vnom=KUNDUR_LINE_VNOM_KV)
bus8 = gce.Bus(name="Bus8", Vnom=KUNDUR_LINE_VNOM_KV)
bus9 = gce.Bus(name="Bus9", Vnom=KUNDUR_LINE_VNOM_KV)
bus10 = gce.Bus(name="Bus10", Vnom=KUNDUR_LINE_VNOM_KV)
bus11 = gce.Bus(name="Bus11", Vnom=KUNDUR_LINE_VNOM_KV)

for bus in [bus1, bus2, bus3, bus4, bus5, bus6, bus7, bus8, bus9, bus10, bus11]:
    grid.add_bus(bus)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.var_factory)


#####################################################################################
#                    Three-phase transmission lines
#####################################################################################

kundur_tower, kundur_wire = _build_kundur_230kv_tower()
grid.add_wire(kundur_wire)
grid.add_overhead_line(kundur_tower)

# Classical Kundur line data are usually expressed per kilometre as approximately
# r=0.0001 pu/km, x=0.001 pu/km and b=0.00175 pu/km on 100 MVA, 230 kV.
# Use the actual physical circuits instead of splitting the short sections into
# several artificial parallel branches.  This preserves the same benchmark
# equivalent while making EMT electromagnetic energy storage more physical.
line_56 = _make_kundur_line(
    "line 5-6", bus5, bus6,
    r=0.00250, x=0.02500, b=0.04375,
    rate=1500.0, length_km=25.0, tower=kundur_tower,
)
line_67 = _make_kundur_line(
    "line 6-7", bus6, bus7,
    r=0.00100, x=0.01000, b=0.01750,
    rate=2100.0, length_km=10.0, tower=kundur_tower,
)
line_78_1 = _make_kundur_line(
    "line 7-8-1", bus7, bus8,
    r=0.01100, x=0.11000, b=0.19250,
    rate=400.0, length_km=110.0, tower=kundur_tower,
)
line_78_2 = _make_kundur_line(
    "line 7-8-2", bus7, bus8,
    r=0.01100, x=0.11000, b=0.19250,
    rate=400.0, length_km=110.0, tower=kundur_tower,
)
line_89_1 = _make_kundur_line(
    "line 8-9-1", bus8, bus9,
    r=0.01100, x=0.11000, b=0.19250,
    rate=400.0, length_km=110.0, tower=kundur_tower,
)
line_89_2 = _make_kundur_line(
    "line 8-9-2", bus8, bus9,
    r=0.01100, x=0.11000, b=0.19250,
    rate=400.0, length_km=110.0, tower=kundur_tower,
)
line_910 = _make_kundur_line(
    "line 9-10", bus9, bus10,
    r=0.00100, x=0.01000, b=0.01750,
    rate=2100.0, length_km=10.0, tower=kundur_tower,
)
line_1011 = _make_kundur_line(
    "line 10-11", bus10, bus11,
    r=0.00250, x=0.02500, b=0.04375,
    rate=1500.0, length_km=25.0, tower=kundur_tower,
)

transmission_lines = [
    line_56,
    line_67,
    line_78_1,
    line_78_2,
    line_89_1,
    line_89_2,
    line_910,
    line_1011,
]

_validate_kundur_line_positive_sequence(transmission_lines)

for line in transmission_lines:
    grid.add_line(line)


#####################################################################################
#                    Generator step-up transformers
#####################################################################################

trafo_G1 = _make_kundur_transformer("trafo 5-1", bus5, bus1)
trafo_G2 = _make_kundur_transformer("trafo 6-2", bus6, bus2)
trafo_G3 = _make_kundur_transformer("trafo 11-3", bus11, bus3)
trafo_G4 = _make_kundur_transformer("trafo 10-4", bus10, bus4)
transformers = [trafo_G1, trafo_G2, trafo_G3, trafo_G4]

for transformer in transformers:
    grid.add_transformer2w(transformer)


#####################################################################################
#                    Loads and generators
#####################################################################################

load1_p, load1_q = KUNDUR_LOAD_PQ_MVA[0]
load2_p, load2_q = KUNDUR_LOAD_PQ_MVA[1]

load1 = gce.Load(
    name="Load Bus7",
    P=load1_p,
    Q=load1_q,
    P1=load1_p / 3.0,
    P2=load1_p / 3.0,
    P3=load1_p / 3.0,
    Q1=load1_q / 3.0,
    Q2=load1_q / 3.0,
    Q3=load1_q / 3.0,
)
load2 = gce.Load(
    name="Load Bus9",
    P=load2_p,
    Q=load2_q,
    P1=load2_p / 3.0,
    P2=load2_p / 3.0,
    P3=load2_p / 3.0,
    Q1=load2_q / 3.0,
    Q2=load2_q / 3.0,
    Q3=load2_q / 3.0,
)
load1.conn = ShuntConnectionType.FloatingStar
load2.conn = ShuntConnectionType.FloatingStar

# Static generator X1/R1 are deliberately the synchronous d-axis reactance and
# stator resistance on the *system* base because the EMT Sauer-Pai mapper uses
# Generator.X1 -> machine xd and Generator.R1 -> machine ra.
gen1 = gce.Generator(
    name="Gen1", P=KUNDUR_GENERATOR_P_MW[0], vset=KUNDUR_GENERATOR_VSET_PU[0],
    Snom=KUNDUR_MACHINE_SN_MVA, x1=KUNDUR_XD_SYS_PU, r1=KUNDUR_RA_SYS_PU,
    freq=KUNDUR_FBASE_HZ,
)
gen2 = gce.Generator(
    name="Gen2", P=KUNDUR_GENERATOR_P_MW[1], vset=KUNDUR_GENERATOR_VSET_PU[1],
    Snom=KUNDUR_MACHINE_SN_MVA, x1=KUNDUR_XD_SYS_PU, r1=KUNDUR_RA_SYS_PU,
    freq=KUNDUR_FBASE_HZ,
)
gen3 = gce.Generator(
    name="Gen3", P=KUNDUR_GENERATOR_P_MW[2], vset=KUNDUR_GENERATOR_VSET_PU[2],
    Snom=KUNDUR_MACHINE_SN_MVA, x1=KUNDUR_XD_SYS_PU, r1=KUNDUR_RA_SYS_PU,
    freq=KUNDUR_FBASE_HZ,
)
gen4 = gce.Generator(
    name="Gen4", P=KUNDUR_GENERATOR_P_MW[3], vset=KUNDUR_GENERATOR_VSET_PU[3],
    Snom=KUNDUR_MACHINE_SN_MVA, x1=KUNDUR_XD_SYS_PU, r1=KUNDUR_RA_SYS_PU,
    freq=KUNDUR_FBASE_HZ,
)

generators = [gen1, gen2, gen3, gen4]
loads = [load1, load2]

for generator in generators:
    _set_generator_sequence_fallbacks(generator)

grid.add_load(bus=bus7, api_obj=load1)
grid.add_load(bus=bus9, api_obj=load2)

grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_generator(bus=bus2, api_obj=gen2)
grid.add_generator(bus=bus3, api_obj=gen3)
grid.add_generator(bus=bus4, api_obj=gen4)

# No bus shunts are created anywhere in this script.

# EMT bus models must be present before device EMT wiring is created.
for bus in grid.buses:
    get_bus_emt_template(grid, bus)

_print_case_definition()

print(
    "Kundur network built: "
    f"{len(grid.buses)} buses, {len(grid.lines)} physical 230-kV circuits, "
    f"{len(grid.transformers2w)} transformers, {len(grid.generators)} generators, "
    f"{len(grid.loads)} loads."
)
print(
    "Kundur transformer architecture: "
    "PF3=GroundedStar/GroundedStar clock-0; EMT=floating three-wire ABC."
)


#####################################################################################
#                    RMS models
#####################################################################################

rms_generator_models: list[Block] = []

for gen_idx, generator in enumerate(generators):
    generator_rms_model = get_complete_generator_template_rms(grid.var_factory).block

    rms_parameters = {
        "fn": KUNDUR_FBASE_HZ,
        "ws": 2.0 * np.pi * KUNDUR_FBASE_HZ,
        "M": KUNDUR_RMS_M[gen_idx],
        "D": KUNDUR_D_SYS_PU,
        "Rs": KUNDUR_RA_SYS_PU,
        "Ra": KUNDUR_RA_SYS_PU,
        "Xd": KUNDUR_XD_SYS_PU,
        "Xq": KUNDUR_XQ_SYS_PU,
        "Xd_prime": KUNDUR_XDP_SYS_PU,
        "Xq_prime": KUNDUR_XQP_SYS_PU,
        "Xd_2prime": KUNDUR_XDPP_SYS_PU,
        "Xq_2prime": KUNDUR_XQPP_SYS_PU,
        "Xl": KUNDUR_XL_SYS_PU,
        "Td0_prime": KUNDUR_TD0P_S,
        "Tq0_prime": KUNDUR_TQ0P_S,
        "Td0_2prime": KUNDUR_TD0PP_S,
        "Tq0_2prime": KUNDUR_TQ0PP_S,
        # The RMS and EMT generator templates do not expose the same magnetic
        # saturation law.  Disable RMS-only saturation for a cleaner comparison.
        "A": 0.0,
        "B": 1.0,
        # Disable PSS output and primary speed feedback.
        "Ks": 0.0,
        "K": 0.0,
        "Kp": 0.0,
        "Ki": 0.0,
        "omega_ref": 1.0,
    }
    _set_model_parameters(generator_rms_model, rms_parameters, f"RMS {generator.name}")
    set_rms_model(device=generator, model=generator_rms_model, var_factory=grid.var_factory)
    rms_generator_models.append(generator_rms_model)

for line_idx, line in enumerate(transmission_lines):
    line_rms_model = get_line_rms_template(
        grid.var_factory,
        name=f"Kundur_line_{line_idx}_rms",
    ).block
    set_rms_model(device=line, model=line_rms_model, var_factory=grid.var_factory)

for transformer_idx, transformer in enumerate(transformers):
    transformer_rms_model = get_transformer2w_rms(grid.var_factory).block
    set_rms_model(device=transformer, model=transformer_rms_model, var_factory=grid.var_factory)

for load in loads:
    load_rms_model = get_load_rms_template(
        grid.var_factory,
        name=f"{load.name}_rms",
    ).block
    set_rms_model(device=load, model=load_rms_model, var_factory=grid.var_factory)


#####################################################################################
#                    EMT models
#####################################################################################

emt_generator_models: list[Block] = []

for gen_idx, generator in enumerate(generators):
    generator_emt_model = get_complete_generator_template_emt(vf=grid.var_factory).block

    emt_parameters = {
        "xq": KUNDUR_XQ_SYS_PU,
        "xdp": KUNDUR_XDP_SYS_PU,
        "xqp": KUNDUR_XQP_SYS_PU,
        "xdpp": KUNDUR_XDPP_SYS_PU,
        "xqpp": KUNDUR_XQPP_SYS_PU,
        "xl": KUNDUR_XL_SYS_PU,
        "Td0p": KUNDUR_TD0P_S,
        "Tq0p": KUNDUR_TQ0P_S,
        "Td0pp": KUNDUR_TD0PP_S,
        "Tq0pp": KUNDUR_TQ0PP_S,
        "H": KUNDUR_EMT_H[gen_idx],
        "D": KUNDUR_D_SYS_PU,
        "omega_s": 1.0,
        # Disable PSS and governor frequency loop.
        "Ks": 0.0,
        "K": 0.0,
        "Kp": 0.0,
        "Ki": 0.0,
        "omega_ref": 1.0,
    }
    _set_model_parameters(generator_emt_model, emt_parameters, f"EMT {generator.name}")

    governor_patched = _patch_emt_governor_to_constant_mechanical_torque(generator_emt_model)
    print(
        f"EMT {generator.name}: constant-mechanical-torque governor patch "
        f"{'applied' if governor_patched else 'NOT applied'}"
    )

    set_emt_model(device=generator, model=generator_emt_model, var_factory=grid.var_factory)
    emt_generator_models.append(generator_emt_model)

for line_idx, line in enumerate(transmission_lines):
    line_emt_model = get_pi_line_emt_template(
        vf=grid.var_factory,
        phN=False,
        phA=True,
        phB=True,
        phC=True,
        name=f"Pi_kundur_line_{line_idx}",
    ).block
    set_emt_model(device=line, model=line_emt_model, var_factory=grid.var_factory)

for transformer_idx, transformer in enumerate(transformers):
    transformer_emt_model = get_transformer_emt_template(
        vf=grid.var_factory,
        conn_f=WindingType.FloatingStar,
        conn_t=WindingType.FloatingStar,
        name=f"Kundur_transformer_{transformer_idx}_emt",
    ).block
    set_emt_model(device=transformer, model=transformer_emt_model, var_factory=grid.var_factory)

for load in loads:
    load_emt_model = get_shunt_rlc_combo_emt_template(
        vf=grid.var_factory,
        include_r=True,
        include_l=True,
        include_c=False,
        phA=True,
        phB=True,
        phC=True,
        connection_type=ShuntConnectionType.FloatingStar,
        name=f"{load.name}_RL_emt",
    ).block
    set_emt_model(device=load, model=load_emt_model, var_factory=grid.var_factory)

gce.save_file(grid=grid, filename="kundur_rms_emt_v2.veragrid")

def _validate_three_wire_emt_interfaces() -> None:
    """Verify that all externally connected EMT devices expose only A/B/C terminals."""
    neutral_ref_names = {
        "v_N", "i_N",
        "vf_N", "if_N",
        "vt_N", "it_N",
    }
    offenders: list[str] = []

    devices = list(transformers) + list(loads) + list(transmission_lines) + list(generators)

    for device in devices:
        model = device.emt_model
        for block in model.get_all_blocks():
            mapping = block.external_mapping
            if mapping is None:
                continue

            for ref, mapped_var in mapping.items():
                if mapped_var is None:
                    continue

                ref_name = getattr(ref, "value", str(ref))
                if ref_name in neutral_ref_names:
                    offenders.append(f"{device.name}: {ref_name} -> {mapped_var.name}")

    if offenders:
        raise RuntimeError(
            "Kundur EMT three-wire interface validation failed:\n  - "
            + "\n  - ".join(offenders)
        )

    print("Kundur EMT interface check: three-wire ABC, no external neutral ports.")


_validate_three_wire_emt_interfaces()


#####################################################################################
#                    Positive-sequence and 3-phase power flow
#####################################################################################

options = gce.PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=0,
    initialize_with_existing_solution=True,
    tolerance=1e-8,
    max_iter=50,
    control_q=False,
    control_taps_modules=True,
    control_taps_phase=True,
    control_remote_voltage=True,
    orthogonalize_controls=True,
    apply_temperature_correction=True,
    branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
    distributed_slack=False,
    ignore_single_node_islands=False,
    trust_radius=1.0,
    backtracking_parameter=0.05,
    use_stored_guess=False,
    initialize_angles=False,
    generate_report=False,
)

res = gce.power_flow(grid, options=options)
print(f"\nPositive-sequence PF converged: {res.converged}")
if not res.converged:
    raise RuntimeError("Positive-sequence Kundur power flow did not converge.")

bus_df = res.get_bus_df()
branch_df = res.get_branch_df()
print("\nPositive-sequence bus operating point:")
print(bus_df)
if PRINT_FULL_POWER_FLOW_TABLES:
    print("\nPositive-sequence branch operating point:")
    print(branch_df)

# Useful operating-point checks for this benchmark.
print("\nPositive-sequence voltage range:")
if "Vm" in bus_df.columns:
    print(f"  min Vm={bus_df['Vm'].min():.6f} pu, max Vm={bus_df['Vm'].max():.6f} pu")
print("Requested total load:")
print(f"  P={load1_p + load2_p:.3f} MW, Q={load1_q + load2_q:.3f} MVAr")

power_flow_3ph = PowerFlowDriver3Ph(grid, options)
power_flow_3ph.run()
res_3ph = power_flow_3ph.results
print(f"\n3-phase PF converged: {res_3ph.converged}")
if not res_3ph.converged:
    raise RuntimeError("Three-phase Kundur power flow did not converge.")

if PRINT_FULL_POWER_FLOW_TABLES:
    print("\n3-phase bus operating point:")
    print(res_3ph.get_bus_df())
    print("\n3-phase branch operating point:")
    print(res_3ph.get_branch_df())


#####################################################################################
#                    Small-signal options
#####################################################################################

rms_options = RmsOptions(
    time_step=0.001,
    simulation_time=1.0,
    tolerance=1e-7,
    integration_method=DynamicIntegrationMethod.DaeBackEuler,
    initialization_method=RmsInitializationMethod.Explicit,
    use_init_values=False,
    max_iter=1000,
    verbose=0,
)

sss_options = RmsSmallSignalStabilityOptions(
    k=0,
    ss_assessment_time=0.0,
)

emt_options = EmtOptions(
    time_step=EMT_TIME_STEP_S,
    simulation_time=EMT_SIMULATION_TIME_S,
    tolerance=1e-6,
    solver_type=EmtSolverTypes.Automatic,
    integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
    verbose=1,
)

floquet_options = SmallSignalStabilityEmtOptions(
    k=200,
    target_period=KUNDUR_PERIOD_S,
    ss_assessment_time=FLOQUET_ASSESSMENT_TIME_S,
    build_type=SmallSignalEmtBuildTypes.Arnoldi,
    verbose=1,
)

print("\n=== Numerical small-signal configuration ===")
print(f"RMS: dt={rms_options.time_step:.6g} s, tolerance={rms_options.tolerance:.1e}")
print(
    f"EMT: dt={emt_options.time_step:.12g} s, "
    f"T/dt={KUNDUR_PERIOD_S / emt_options.time_step:.0f}, "
    f"simulation_time={emt_options.simulation_time:.6f} s, "
    f"Floquet assessment={floquet_options.ss_assessment_time:.6f} s"
)


#####################################################################################
#                    Drivers
#####################################################################################

small_signal_driver = SmallSignalStabilityRmsDriver(
    grid=grid,
    rms_options=rms_options,
    sss_options=sss_options,
    pf_results=res,
)

floquet_driver = SmallSignalStabilityEmtDriver(
    grid=grid,
    pf_results=res_3ph,
    emt_options=emt_options,
    sss_options=floquet_options,
)


#####################################################################################
#                    Run RMS and EMT/Floquet small-signal analyses
#####################################################################################

print("\nRunning RMS small-signal analysis...")
small_signal_driver.run_small_signal_stability()

rms_eigenvalues = small_signal_driver.results.eigenvalues
rms_PFactors = small_signal_driver.results.participation_factors
_print_eigenvalue_summary("RMS", rms_eigenvalues)

if PRINT_RAW_EIGENVALUES:
    print(f"RMS eigenvalues={rms_eigenvalues}")

print("\nRunning EMT/Floquet small-signal analysis...")
floquet_driver.run()

emt_eigenvalues = floquet_driver.results.eigenvalues
emt_PFactors = floquet_driver.results.participation_factors
_print_eigenvalue_summary("EMT/Floquet", emt_eigenvalues, period=KUNDUR_PERIOD_S)
_print_floquet_multiplier_summary(floquet_driver.results)

if PRINT_RAW_EIGENVALUES:
    print(f"EMT/Floquet eigenvalues={emt_eigenvalues}")


#####################################################################################
#                    Plot results
#####################################################################################

plot_s_domain_eigenvalues(
    eigenvalues_1=rms_eigenvalues,
    eigenvalues_2=emt_eigenvalues,
    label_1="RMS eigenvalues",
    label_2="EMT/Floquet eigenvalues",
)

plot_two_participation_factors_tables(
    pfactors_1=rms_PFactors,
    pfactors_2=emt_PFactors,
    title_1="RMS participation factors",
    title_2="EMT/Floquet participation factors",
)
