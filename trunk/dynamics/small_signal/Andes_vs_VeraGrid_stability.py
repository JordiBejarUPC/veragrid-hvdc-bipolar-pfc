# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# ==============================================================================
# RESULT PATHS
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent

VERAGRID_RESULTS_DIR = BASE_DIR / "kundur_small_signal_rms_results_VeraGrid"
ANDES_RESULTS_DIR = BASE_DIR / "kundur_small_signal_rms_results_Andes"

# VeraGrid writes all modal data to modes.csv.
VERAGRID_EIGENVALUES_CSV = VERAGRID_RESULTS_DIR / "modes.csv"

# stability_andes.py uses this case key for the Kundur case.
ANDES_CASE_KEY = "KUNDUR_no_shunt"
ANDES_EIGENVALUES_CSV = (
    ANDES_RESULTS_DIR / f"Eigenvalues_results_Andes_{ANDES_CASE_KEY}.csv"
)


def load_veragrid_eigenvalues(csv_path: Path) -> np.ndarray:
    """
    Load VeraGrid eigenvalues from the current ``modes.csv`` format.

    Expected columns:
        mode,
        real_rad_per_s,
        imag_rad_per_s,
        damping_ratio,
        oscillation_frequency_hz

    :param csv_path: VeraGrid modes.csv path.
    :return: Complex eigenvalue vector.
    """
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"VeraGrid eigenvalue file was not found:\n{csv_path}"
        )

    data = np.genfromtxt(
        csv_path,
        delimiter=",",
        names=True,
        dtype=None,
        encoding="utf-8",
    )

    if data.size == 0:
        raise ValueError(f"VeraGrid modes file is empty: {csv_path}")

    real_part = np.atleast_1d(data["real_rad_per_s"]).astype(float)
    imag_part = np.atleast_1d(data["imag_rad_per_s"]).astype(float)

    return real_part + 1j * imag_part


def load_andes_eigenvalues(csv_path: Path) -> np.ndarray:
    """
    Load ANDES eigenvalues from stability_andes.py output.

    The ANDES file contains one complex eigenvalue per row and has no header.

    :param csv_path: ANDES eigenvalue CSV path.
    :return: Complex eigenvalue vector.
    """
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"ANDES eigenvalue file was not found:\n{csv_path}"
        )

    values = np.genfromtxt(
        csv_path,
        delimiter=",",
        dtype=complex,
    )

    values = np.asarray(values, dtype=complex).reshape(-1)

    if values.size == 0:
        raise ValueError(f"ANDES eigenvalue file is empty: {csv_path}")

    return values


def match_eigenvalues(
    reference: np.ndarray,
    candidate: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Match each ANDES eigenvalue to the nearest unused VeraGrid eigenvalue.

    Matching by nearest point in the complex s-plane is more robust than sorting
    only by eigenvalue magnitude, particularly for conjugate modes and modes with
    similar absolute value.

    ANDES is treated as the reference set.

    :param reference: ANDES eigenvalues.
    :param candidate: VeraGrid eigenvalues.
    :return: Tuple with matched ANDES values, matched VeraGrid values and errors.
    """
    reference = np.asarray(reference, dtype=complex).reshape(-1)
    candidate = np.asarray(candidate, dtype=complex).reshape(-1)

    if candidate.size < reference.size:
        print(
            "Warning: VeraGrid has fewer eigenvalues than ANDES. "
            f"VeraGrid={candidate.size}, ANDES={reference.size}. "
            "Only the available VeraGrid modes will be matched."
        )

    available = list(range(candidate.size))
    matched_reference: list[complex] = []
    matched_candidate: list[complex] = []
    absolute_errors: list[float] = []

    for ref_value in reference:
        if len(available) == 0:
            break

        distances = np.asarray(
            [abs(candidate[idx] - ref_value) for idx in available],
            dtype=float,
        )

        local_idx = int(np.argmin(distances))
        candidate_idx = available.pop(local_idx)

        matched_reference.append(ref_value)
        matched_candidate.append(candidate[candidate_idx])
        absolute_errors.append(float(distances[local_idx]))

    return (
        np.asarray(matched_reference, dtype=complex),
        np.asarray(matched_candidate, dtype=complex),
        np.asarray(absolute_errors, dtype=float),
    )


def andes_vs_veragrid_stability(
    veragrid_csv: Path,
    andes_csv: Path,
) -> None:
    """
    Compare VeraGrid and ANDES small-signal eigenvalues.

    :param veragrid_csv: VeraGrid modes.csv.
    :param andes_csv: ANDES eigenvalue CSV.
    :return: None.
    """
    veragrid_eig = load_veragrid_eigenvalues(veragrid_csv)
    andes_eig = load_andes_eigenvalues(andes_csv)

    # Remove non-finite values before matching.
    veragrid_valid = (
        np.isfinite(veragrid_eig.real)
        & np.isfinite(veragrid_eig.imag)
    )
    andes_valid = (
        np.isfinite(andes_eig.real)
        & np.isfinite(andes_eig.imag)
    )

    veragrid_eig = veragrid_eig[veragrid_valid]
    andes_eig = andes_eig[andes_valid]

    print(f"VeraGrid eigenvalue file: {veragrid_csv}")
    print(f"ANDES eigenvalue file:    {andes_csv}")

    print(f"\nVeraGrid modes loaded: {len(veragrid_eig)}")
    print(f"ANDES modes loaded:    {len(andes_eig)}")

    andes_matched, veragrid_matched, absolute_error = match_eigenvalues(
        reference=andes_eig,
        candidate=veragrid_eig,
    )

    denominator = np.abs(andes_matched)

    relative_error = np.full(
        andes_matched.shape,
        np.inf,
        dtype=float,
    )

    nonzero = denominator > 1e-10
    relative_error[nonzero] = (
        absolute_error[nonzero] / denominator[nonzero] * 100.0
    )

    print("\nMatched modes:")
    print(
        f"{'Mode':>5}  "
        f"{'ANDES eigenvalue':>32}  "
        f"{'VeraGrid eigenvalue':>32}  "
        f"{'|Δλ|':>14}  "
        f"{'Rel. err [%]':>14}"
    )
    print("-" * 108)

    for idx, (
        andes_value,
        veragrid_value,
        abs_error,
        rel_error,
    ) in enumerate(
        zip(
            andes_matched,
            veragrid_matched,
            absolute_error,
            relative_error,
        ),
        start=1,
    ):
        print(
            f"{idx:5d}  "
            f"{andes_value.real:+14.7e}{andes_value.imag:+14.7e}j  "
            f"{veragrid_value.real:+14.7e}{veragrid_value.imag:+14.7e}j  "
            f"{abs_error:14.7e}  "
            f"{rel_error:14.7e}"
        )

    finite_relative_error = relative_error[np.isfinite(relative_error)]

    if finite_relative_error.size > 0:
        print("\nComparison summary:")
        print(
            f"  Mean relative eigenvalue error: "
            f"{np.mean(finite_relative_error):.6f} %"
        )
        print(
            f"  Maximum relative eigenvalue error: "
            f"{np.max(finite_relative_error):.6f} %"
        )
        print(
            f"  Mean absolute eigenvalue error: "
            f"{np.mean(absolute_error):.6e} rad/s"
        )

    # --------------------------------------------------------------------------
    # S-domain comparison plot
    # --------------------------------------------------------------------------

    fig, ax = plt.subplots(figsize=(9, 7))

    # Correct 5% damping-ratio lines.
    zeta = 0.05
    slope = np.sqrt(1.0 - zeta ** 2) / zeta

    all_values = np.concatenate(
        (andes_matched, veragrid_matched)
    )

    real_values = all_values.real
    imag_values = all_values.imag

    real_span = float(np.ptp(real_values))
    imag_span = float(np.ptp(imag_values))

    margin_x = max(real_span * 0.10, 0.1)
    margin_y = max(imag_span * 0.10, 0.1)

    x_min = float(real_values.min() - margin_x)
    x_max = float(real_values.max() + margin_x)
    y_min = float(imag_values.min() - margin_y)
    y_max = float(imag_values.max() + margin_y)

    x_z = np.linspace(min(-200.0, x_min), 0.0, 500)
    y_z = slope * x_z

    ax.plot(
        x_z,
        y_z,
        "--",
        linewidth=0.8,
        label=r"$\zeta = 5\%$",
    )
    ax.plot(
        x_z,
        -y_z,
        "--",
        linewidth=0.8,
    )

    ax.scatter(
        andes_matched.real,
        andes_matched.imag,
        marker="o",
        label="ANDES",
    )
    ax.scatter(
        veragrid_matched.real,
        veragrid_matched.imag,
        marker="x",
        label="VeraGrid",
    )

    # Connect each matched pair so discrepancies are visible.
    for andes_value, veragrid_value in zip(
        andes_matched,
        veragrid_matched,
    ):
        ax.plot(
            [andes_value.real, veragrid_value.real],
            [andes_value.imag, veragrid_value.imag],
            linewidth=0.5,
            alpha=0.5,
        )

    ax.set_xlabel("Real [rad/s]")
    ax.set_ylabel("Imaginary [rad/s]")
    ax.set_title("Kundur small-signal stability: ANDES vs VeraGrid")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.axhline(0.0, linewidth=1.0)
    ax.axvline(0.0, linewidth=1.0)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    plt.show()


if __name__ == "__main__":
    andes_vs_veragrid_stability(
        veragrid_csv=VERAGRID_EIGENVALUES_CSV,
        andes_csv=ANDES_EIGENVALUES_CSV,
    )
