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
    ax.set_xlabel("Real [rad/s]")
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

# The original rms_kundur.py is a positive-sequence benchmark.  Floquet/EMT,
# however, needs a phase-domain network and the 3-phase power flow needs phase
# information on every AC branch.  The 230-kV lines below therefore receive an
# OverheadLineType tower and explicit NABC matrices.
#
# Important modelling choice:
#   * the Kundur R/X/B values remain the authoritative positive-sequence data;
#   * the tower supplies the A/B/C architecture and a physically reasonable
#     zero-sequence ratio, because the original Kundur script contains no
#     zero-sequence line data;
#   * the stored phase-domain matrices are converted to a transposed-equivalent
#     line whose positive sequence is EXACTLY the original Kundur R/X/B.
#
# This keeps the balanced RMS benchmark and the EMT/Floquet network electrically
# consistent instead of replacing the Kundur line impedances by arbitrary tower
# impedances.

grid = gce.MultiCircuit(name="Kundur two-area RMS/EMT", Sbase=100.0, fbase=60.0)

KUNDUR_LINE_VNOM_KV = 230.0
KUNDUR_GEN_VNOM_KV = 20.0
KUNDUR_TRANSFORMER_SN_MVA = 900.0
KUNDUR_TRANSFORMER_X_PU = 0.15 * (grid.Sbase / KUNDUR_TRANSFORMER_SN_MVA)

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
    Build the physical three-phase tower used by all Kundur 230-kV lines.

    The original Kundur data set contains no conductor geometry.  This tower is
    therefore a reference physical architecture, not an attempt to reconstruct a
    historical tower.  Its zero-sequence relationship is used while the published
    positive-sequence R/X/B values are retained exactly.
    """
    wire = gce.Wire(
        name="Kundur 230-kV phase conductor",
        diameter=30.0,          # mm
        diameter_internal=0.0, # solid equivalent conductor
        is_tube=False,
        r=0.040,                # ohm/km; only used to establish physical ratios
        max_current=2.5,        # kA
    )

    tower = gce.OverheadLineType(
        name="Kundur 230-kV reference tower",
        Vnom=KUNDUR_LINE_VNOM_KV,
        earth_resistivity=100.0,
        frequency=grid.fBase,
    )

    # Three-wire overhead line: no explicit neutral conductor.  Carson earth
    # return inside OverheadLineType provides the ground-return contribution.
    tower.add_wire_relationship(wire=wire, xpos=-8.0, ypos=25.0, phase=1)  # A
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=32.0, phase=2)   # B
    tower.add_wire_relationship(wire=wire, xpos=8.0, ypos=25.0, phase=3)   # C
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
    """
    Re-scale one tower-backed line to the Kundur positive-sequence values.

    ``line.apply_template()`` first creates valid NABC phase flags and physical
    matrices from the tower.  We retain the tower-derived zero/positive sequence
    ratios, but rebuild a transposed ABC equivalent so the positive-sequence
    impedance/shunt of the 3-phase network exactly matches the RMS benchmark.
    """
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

    # OverheadLineType stores line.ysh with the historical 1e6 scaling.  Keep
    # that storage convention so both PowerFlow3Ph and the EMT static mapper
    # interpret the matrix exactly as they do for a normal tower-backed line.
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

    # Scalars used by the ordinary positive-sequence PF/RMS path.
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
    tower: gce.OverheadLineType,
) -> gce.Line:
    """Create one Kundur 230-kV tower-backed, three-phase transmission line."""
    zbase_ohm = KUNDUR_LINE_VNOM_KV ** 2 / grid.Sbase
    _, tower_x1_ohm_per_km, _, _ = tower.get_sequence_values(circuit_idx=1, seq=1)

    if tower_x1_ohm_per_km > 1e-12:
        length_km = x * zbase_ohm / tower_x1_ohm_per_km
    else:
        length_km = 1.0

    length_km = max(float(length_km), 1e-3)

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

    line.apply_template(tower, grid.Sbase, grid.fBase)
    _set_transposed_kundur_line_matrices(
        line=line,
        r1=r,
        x1=x,
        b1=b,
        rate=rate,
    )
    return line


def _make_kundur_transformer(
    name: str,
    bus_hv: gce.Bus,
    bus_lv: gce.Bus,
) -> gce.Transformer2W:
    """Create one 230/20-kV Kundur generator step-up transformer."""
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

    # PF3 and EMT need slightly different representations here.
    #
    # The current VeraGrid 3-phase Transformer2W admittance implementation
    # supports grounded/neutral star, delta and zig-zag combinations, but not
    # FloatingStar.  Use GroundedStar/GroundedStar for the STATIC PF3 model so
    # the transformer is stamped into the 3-phase network.
    #
    # The original Kundur benchmark has no zero-sequence/neutral data.  The EMT
    # symbolic model is therefore attached separately as a three-wire ABC model
    # (see the EMT-model section below), avoiding an invented external neutral.
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

        # Undo the OverheadLineType historical shunt-storage factor.
        yabc = np.asarray(line.ysh.values[1:4, 1:4], dtype=complex) / 1e6
        y012 = _T_ABC_TO_012 @ yabc @ _T_012_TO_ABC

        max_z_error = max(max_z_error, abs(z012[1, 1] - complex(line.R, line.X)))
        max_b_error = max(max_b_error, abs(y012[1, 1].imag - line.B))

    if max_z_error > 1e-10 or max_b_error > 1e-10:
        raise RuntimeError(
            "Kundur line ABC conversion is inconsistent with the positive-sequence data: "
            f"max |dZ1|={max_z_error:.3e}, max |dB1|={max_b_error:.3e}."
        )

    print(
        "Kundur 3ph line check: "
        f"max |dZ1|={max_z_error:.3e}, max |dB1|={max_b_error:.3e}"
    )


#####################################################################################
#                    Buses
#####################################################################################

bus1 = gce.Bus(name="Bus1", Vnom=20.0)
bus2 = gce.Bus(name="Bus2", Vnom=20.0)
bus3 = gce.Bus(name="Bus3", Vnom=20.0, is_slack=True)
bus4 = gce.Bus(name="Bus4", Vnom=20.0)
bus5 = gce.Bus(name="Bus5", Vnom=230.0)
bus6 = gce.Bus(name="Bus6", Vnom=230.0)
bus7 = gce.Bus(name="Bus7", Vnom=230.0)
bus8 = gce.Bus(name="Bus8", Vnom=230.0)
bus9 = gce.Bus(name="Bus9", Vnom=230.0)
bus10 = gce.Bus(name="Bus10", Vnom=230.0)
bus11 = gce.Bus(name="Bus11", Vnom=230.0)

for bus in [bus1, bus2, bus3, bus4, bus5, bus6, bus7, bus8, bus9, bus10, bus11]:
    grid.add_bus(bus)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.var_factory)


#####################################################################################
#                    Three-phase overhead-line architecture
#####################################################################################

kundur_tower, kundur_wire = _build_kundur_230kv_tower()
grid.add_wire(kundur_wire)
grid.add_overhead_line(kundur_tower)

line0 = _make_kundur_line("line 5-6-1", bus5, bus6, 0.00500, 0.05000, 0.02187, 750.0, kundur_tower)
line1 = _make_kundur_line("line 5-6-2", bus5, bus6, 0.00500, 0.05000, 0.02187, 750.0, kundur_tower)
line2 = _make_kundur_line("line 6-7-1", bus6, bus7, 0.00300, 0.03000, 0.00583, 700.0, kundur_tower)
line3 = _make_kundur_line("line 6-7-2", bus6, bus7, 0.00300, 0.03000, 0.00583, 700.0, kundur_tower)
line4 = _make_kundur_line("line 6-7-3", bus6, bus7, 0.00300, 0.03000, 0.00583, 700.0, kundur_tower)
line5 = _make_kundur_line("line 7-8-1", bus7, bus8, 0.01100, 0.11000, 0.19250, 400.0, kundur_tower)
line6 = _make_kundur_line("line 7-8-2", bus7, bus8, 0.01100, 0.11000, 0.19250, 400.0, kundur_tower)
line7 = _make_kundur_line("line 8-9-1", bus8, bus9, 0.01100, 0.11000, 0.19250, 400.0, kundur_tower)
line8 = _make_kundur_line("line 8-9-2", bus8, bus9, 0.01100, 0.11000, 0.19250, 400.0, kundur_tower)
line9 = _make_kundur_line("line 9-10-1", bus9, bus10, 0.00300, 0.03000, 0.00583, 700.0, kundur_tower)
line10 = _make_kundur_line("line 9-10-2", bus9, bus10, 0.00300, 0.03000, 0.00583, 700.0, kundur_tower)
line11 = _make_kundur_line("line 9-10-3", bus9, bus10, 0.00300, 0.03000, 0.00583, 700.0, kundur_tower)
line12 = _make_kundur_line("line 10-11-1", bus10, bus11, 0.00500, 0.05000, 0.02187, 750.0, kundur_tower)
line13 = _make_kundur_line("line 10-11-2", bus10, bus11, 0.00500, 0.05000, 0.02187, 750.0, kundur_tower)

transmission_lines = [
    line0, line1, line2, line3, line4, line5, line6,
    line7, line8, line9, line10, line11, line12, line13,
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

load_p = 9.999999
load_q = 0.999999

load1 = gce.Load(
    name="load1",
    P=load_p,
    Q=load_q,
    P1=load_p / 3.0,
    P2=load_p / 3.0,
    P3=load_p / 3.0,
    Q1=load_q / 3.0,
    Q2=load_q / 3.0,
    Q3=load_q / 3.0,
)
load2 = gce.Load(
    name="load2",
    P=load_p,
    Q=load_q,
    P1=load_p / 3.0,
    P2=load_p / 3.0,
    P3=load_p / 3.0,
    Q1=load_q / 3.0,
    Q2=load_q / 3.0,
    Q3=load_q / 3.0,
)
load1.conn = ShuntConnectionType.FloatingStar
load2.conn = ShuntConnectionType.FloatingStar

xd = 0.3 * grid.Sbase / KUNDUR_TRANSFORMER_SN_MVA

gen1 = gce.Generator(name="Gen1", P=10.0, vset=1.03, Snom=900.0, x1=xd, r1=0.0, freq=60.0)
gen2 = gce.Generator(name="Gen2", P=10.0, vset=1.01, Snom=900.0, x1=xd, r1=0.0, freq=60.0)
gen3 = gce.Generator(name="Gen3", P=10.0, vset=1.03, Snom=900.0, x1=xd, r1=0.0, freq=60.0)
gen4 = gce.Generator(name="Gen4", P=10.0, vset=1.01, Snom=900.0, x1=xd, r1=0.0, freq=60.0)

generators = [gen1, gen2, gen3, gen4]
loads = [load1, load2]

grid.add_load(bus=bus7, api_obj=load1)
grid.add_load(bus=bus9, api_obj=load2)

grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_generator(bus=bus2, api_obj=gen2)
grid.add_generator(bus=bus3, api_obj=gen3)
grid.add_generator(bus=bus4, api_obj=gen4)

# EMT bus models must be present before device EMT wiring is created.
for bus in grid.buses:
    get_bus_emt_template(grid, bus)

print(
    "Kundur network built: "
    f"{len(grid.buses)} buses, {len(grid.lines)} 230-kV lines, "
    f"{len(grid.transformers2w)} transformers, {len(grid.generators)} generators, "
    f"{len(grid.loads)} loads."
)

print(
    "Kundur transformer architecture: "
    "PF3=GroundedStar/GroundedStar, EMT=three-wire ABC."
)


#####################################################################################
#                    RMS models
#####################################################################################

for generator in generators:
    generator_rms_model = get_complete_generator_template_rms(grid.var_factory).block
    set_rms_model(device=generator, model=generator_rms_model, var_factory=grid.var_factory)

for line_idx, line in enumerate(transmission_lines):
    line_rms_model = get_line_rms_template(grid.var_factory, name=f"Kundur_line_{line_idx}_rms").block
    set_rms_model(device=line, model=line_rms_model, var_factory=grid.var_factory)

for transformer_idx, transformer in enumerate(transformers):
    transformer_rms_model = get_transformer2w_rms(grid.var_factory).block
    set_rms_model(device=transformer, model=transformer_rms_model, var_factory=grid.var_factory)

for load in loads:
    load_rms_model = get_load_rms_template(grid.var_factory, name=f"{load.name}_rms").block
    set_rms_model(device=load, model=load_rms_model, var_factory=grid.var_factory)


#####################################################################################
#                    EMT models
#####################################################################################

for generator in generators:
    generator_emt_model = get_complete_generator_template_emt(vf=grid.var_factory).block
    set_emt_model(device=generator, model=generator_emt_model, var_factory=grid.var_factory)

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
    # Deliberately decouple the EMT terminal interface from the PF3 winding
    # connection.  PF3 needs GroundedStar to stamp Transformer2W correctly,
    # whereas the Kundur benchmark provides no neutral/zero-sequence network.
    # Passing FloatingStar here makes get_transformer_emt_template expose only
    # vf_A/B/C, vt_A/B/C and their phase currents, which is the intended
    # three-wire EMT interface for the balanced Floquet comparison.
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

gce.save_file(grid=grid, filename="kundur_rms_emt.veragrid")


def _validate_three_wire_emt_interfaces() -> None:
    """
    Verify that the Kundur EMT network exposes only A/B/C terminals externally.

    The source Kundur benchmark contains positive-sequence data only. Its
    phase-domain realization therefore uses a three-wire ABC external network;
    floating star points remain internal to transformer/load models.
    """
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
                    offenders.append(
                        f"{device.name}: {ref_name} -> {mapped_var.name}"
                    )

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
    tolerance=1e-6,
    max_iter=25,
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
print(f"Positive-sequence PF converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

power_flow_3ph = PowerFlowDriver3Ph(grid, options)
power_flow_3ph.run()
res_3ph = power_flow_3ph.results
print(f"3-phase PF converged: {res_3ph.converged}")
print(res_3ph.get_bus_df())
print(res_3ph.get_branch_df())


#####################################################################################
#                    Small-signal options
#####################################################################################

rms_options = RmsOptions(
    time_step=0.001,
    simulation_time=1.0,
    tolerance=1e-6,
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
    time_step=5e-6,
    # Floquet assessment is at 0.1 s; keep enough EMT horizon for at least one
    # complete 60-Hz period after the assessment point.
    simulation_time=0.12,
    tolerance=1e-6,
    solver_type=EmtSolverTypes.Automatic,
    integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
    verbose=1,
)

floquet_options = SmallSignalStabilityEmtOptions(
    k=200,
    target_period=1.0 / grid.fBase,
    ss_assessment_time=0.1,
    build_type=SmallSignalEmtBuildTypes.Arnoldi,
    verbose=1,
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

small_signal_driver.run_small_signal_stability()

rms_eigenvalues = small_signal_driver.results.eigenvalues
rms_PFactors = small_signal_driver.results.participation_factors
print(f"RMS eigenvalues={rms_eigenvalues}")

floquet_driver.run()
emt_eigenvalues = floquet_driver.results.eigenvalues
emt_PFactors = floquet_driver.results.participation_factors
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
