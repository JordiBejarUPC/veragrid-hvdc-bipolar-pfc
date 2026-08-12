# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Run and export ANDES small-signal benchmarks for VeraGrid comparisons."""

from __future__ import annotations

import argparse
import csv
from enum import Enum
import hashlib
from pathlib import Path
import time
from typing import Any

import andes
import numpy as np
import pandas as pd

from trunk.dynamics.small_signal.small_signal_benchmark_timing import elapsed_seconds
from trunk.dynamics.small_signal.small_signal_benchmark_timing import save_benchmark_timings


class AndesBenchmarkCase(Enum):
    """Cases with repository-standard result folders."""

    KUNDUR = 1
    IEEE14 = 2
    IEEE39 = 3
    NPCC140 = 4
    WECC179 = 5


def _parse_case_name(case_name: str) -> AndesBenchmarkCase:
    """Convert one command-line case name to its enum.

    :param case_name: User-supplied case name.
    :return: Matching benchmark-case enum.
    :raises argparse.ArgumentTypeError: If the name is unsupported.
    """
    normalized_name: str = case_name.strip().lower()
    if normalized_name in ("kundur", "kundur_no_shunt", "kundur-no-shunt"):
        return AndesBenchmarkCase.KUNDUR
    elif normalized_name == "ieee14":
        return AndesBenchmarkCase.IEEE14
    elif normalized_name == "ieee39":
        return AndesBenchmarkCase.IEEE39
    elif normalized_name in ("npcc140", "npcc_140", "npcc-140"):
        return AndesBenchmarkCase.NPCC140
    elif normalized_name in ("wecc179", "wecc_179", "wecc-179"):
        return AndesBenchmarkCase.WECC179
    else:
        raise argparse.ArgumentTypeError(
            "Supported presets are: kundur, ieee14, ieee39, npcc140 and wecc179. "
            "Use --case-file and --label for another ANDES case."
        )


def _case_label(case_tpe: AndesBenchmarkCase) -> str:
    """Return the result-folder label for a preset case.

    :param case_tpe: Selected benchmark case.
    :return: Stable result label.
    """
    if case_tpe is AndesBenchmarkCase.KUNDUR:
        return "KUNDUR_no_shunt"
    elif case_tpe is AndesBenchmarkCase.IEEE14:
        return "IEEE14"
    elif case_tpe is AndesBenchmarkCase.IEEE39:
        return "IEEE39"
    elif case_tpe is AndesBenchmarkCase.NPCC140:
        return "NPCC140"
    else:
        return "WECC179"


def _resolve_case_path(case_tpe: AndesBenchmarkCase, script_dir: Path) -> Path:
    """Resolve the physical file for a preset case.

    :param case_tpe: Selected benchmark case.
    :param script_dir: Directory containing this script.
    :return: Absolute ANDES case path.
    """
    if case_tpe is AndesBenchmarkCase.KUNDUR:
        case_path: Path = script_dir / "kundur_ieee_no_shunt.json"
    elif case_tpe is AndesBenchmarkCase.IEEE14:
        case_path = Path(andes.get_case("ieee14/ieee14_full.xlsx"))
    elif case_tpe is AndesBenchmarkCase.IEEE39:
        case_path = Path(andes.get_case("ieee39/ieee39_full.xlsx"))
    elif case_tpe is AndesBenchmarkCase.NPCC140:
        case_path = Path(andes.get_case("npcc/npcc.xlsx"))
    else:
        case_path = Path(andes.get_case("wecc/wecc_full.xlsx"))
    return case_path.resolve()


def _power_flow_tolerance(case_tpe: AndesBenchmarkCase) -> float:
    """Return the strictest convergent ANDES tolerance for one preset.

    The WECC 179 starting point converges in ANDES 2.0 down to ``1e-10`` but
    not to ``1e-13``.  The other repository benchmarks retain the tighter
    common tolerance.

    :param case_tpe: Selected benchmark case.
    :return: ANDES power-flow tolerance.
    """
    if case_tpe is AndesBenchmarkCase.WECC179:
        return 1.0e-10
    else:
        return 1.0e-13


def _format_complex(value: complex, decimals: int = 15) -> str:
    """Format one complex matrix value without discarding precision.

    :param value: Complex value to serialize.
    :param decimals: Scientific-notation decimal places.
    :return: CSV-safe complex representation.
    """
    number: complex = complex(value)
    return f"{number.real:.{decimals}e}{number.imag:+.{decimals}e}j"


def _write_state_matrix(
    output_path: Path,
    state_matrix: np.ndarray,
    state_names: list[str],
) -> None:
    """Write a square state matrix with state names on both axes.

    :param output_path: Destination CSV path.
    :param state_matrix: Reduced ANDES state matrix.
    :param state_names: Reduced ANDES state labels.
    :return: None.
    """
    matrix: np.ndarray = np.asarray(state_matrix, dtype=complex)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer: Any = csv.writer(csv_file)
        writer.writerow(list(("equation", *state_names)))
        row_index: int
        for row_index in range(matrix.shape[0]):
            row_values: list[str] = list()
            column_index: int
            for column_index in range(matrix.shape[1]):
                row_values.append(_format_complex(matrix[row_index, column_index]))
            writer.writerow(list((state_names[row_index], *row_values)))


def _write_static_tables(system: Any, results_dir: Path, case_label: str) -> None:
    """Write solved static-device tables for operating-point auditing.

    :param system: Solved ANDES system.
    :param results_dir: Destination result directory.
    :param case_label: Filename-safe case label.
    :return: None.
    """
    table_names: tuple[str, ...] = ("Bus", "Slack", "PV", "PQ", "Shunt", "Line")
    table_name: str
    for table_name in table_names:
        model: Any = system.models[table_name]
        table: pd.DataFrame = model.as_df().reset_index(drop=True)
        table.to_csv(
            results_dir / f"{table_name.lower()}_table_Andes_{case_label}.csv",
            index=False,
        )

    # Bus.as_df() contains workbook guesses.  The DAE variables below contain
    # the actual solved voltage operating point used by EIG.
    bus_model: Any = system.models["Bus"]
    solved_bus_table: pd.DataFrame = pd.DataFrame(
        dict(
            name=np.asarray(bus_model.name.v, dtype=str),
            Vm=np.asarray(bus_model.v.v, dtype=float),
            Va_rad=np.asarray(bus_model.a.v, dtype=float),
        )
    )
    solved_bus_table.to_csv(
        results_dir / f"solved_bus_Andes_{case_label}.csv",
        index=False,
    )


def _fold_zero_ieeest_input_filter_states(system: Any) -> list[str]:
    """Reclassify exact IEEEST input-filter pass-through states as algebraic.

    ANDES represents the second-order ``F1`` and ``F2`` blocks with two state
    variables even when every denominator and numerator coefficient is zero.
    One state per block already has a zero mass coefficient; the other must be
    folded as well to obtain the exact algebraic pass-through used by the
    physical reduced model.

    :param system: Initialized ANDES system with populated DAE state names.
    :return: Names of the additional states assigned a zero mass coefficient.
    """
    ieeest_model: Any | None = system.models.get("IEEEST", None)
    folded_state_names: list[str] = list()
    if ieeest_model is None or int(ieeest_model.n) == 0:
        pass
    else:
        device_index: int
        for device_index in range(int(ieeest_model.n)):
            coefficients: np.ndarray = np.asarray(
                (
                    ieeest_model.A1.v[device_index],
                    ieeest_model.A2.v[device_index],
                    ieeest_model.A3.v[device_index],
                    ieeest_model.A4.v[device_index],
                    ieeest_model.A5.v[device_index],
                    ieeest_model.A6.v[device_index],
                ),
                dtype=float,
            )
            if bool(np.all(np.abs(coefficients) <= 1.0e-15)):
                device_ordinal: int = device_index + 1
                folded_state_names.append(f"F1_y IEEEST {device_ordinal}")
                folded_state_names.append(f"F2_x2 IEEEST {device_ordinal}")
            else:
                pass

    dae_state_names: np.ndarray = np.asarray(system.dae.x_name, dtype=str)
    folded_state_name: str
    for folded_state_name in folded_state_names:
        state_indexes: np.ndarray = np.flatnonzero(dae_state_names == folded_state_name)
        if state_indexes.size == 1:
            system.dae.Tf[int(state_indexes[0])] = 0.0
        else:
            raise ValueError(
                f"Expected one ANDES state named {folded_state_name!r}; "
                f"found {state_indexes.size}."
            )
    return folded_state_names


def _fold_unused_bus_frequency_states(system: Any) -> list[str]:
    """Fold BusFreq devices that no enabled controller consumes.

    Some published workbooks instantiate one BusFreq device per generator even
    though every stabilizer is configured for rotor speed or electrical power.
    Their decoupled filter poles are measurement-implementation modes, not
    physical network modes. Folding them before EIG makes the exported spectrum
    exactly the common physical model while retaining every consumed BusFreq.

    :param system: Initialized ANDES system.
    :return: Folded BusFreq state names.
    """
    busfreq_model: Any | None = system.models.get("BusFreq", None)
    folded_state_names: list[str] = list()
    if busfreq_model is None or int(busfreq_model.n) == 0:
        return folded_state_names
    else:
        pass
    referenced_indexes: set[str] = set()
    controller_name: str
    for controller_name in ("IEEEST", "ST2CUT"):
        controller: Any | None = system.models.get(controller_name, None)
        if controller is None or int(controller.n) == 0:
            pass
        else:
            device_index: int
            for device_index in range(int(controller.n)):
                if int(controller.MODE.v[device_index]) == 2:
                    referenced_indexes.add(str(controller.busf.v[device_index]))
                else:
                    pass
                if controller_name == "ST2CUT" and int(controller.MODE2.v[device_index]) == 2:
                    referenced_indexes.add(str(controller.busf2.v[device_index]))
                else:
                    pass
    busfreq_index: int
    for busfreq_index in range(int(busfreq_model.n)):
        model_index: str = str(busfreq_model.idx.v[busfreq_index])
        if model_index in referenced_indexes:
            pass
        else:
            device_ordinal: int = busfreq_index + 1
            folded_state_names.append(f"L_y BusFreq {device_ordinal}")
            folded_state_names.append(f"WO_x BusFreq {device_ordinal}")
    dae_state_names: np.ndarray = np.asarray(system.dae.x_name, dtype=str)
    state_name: str
    for state_name in folded_state_names:
        state_indexes: np.ndarray = np.flatnonzero(dae_state_names == state_name)
        if state_indexes.size == 1:
            system.dae.Tf[int(state_indexes[0])] = 0.0
        else:
            raise ValueError(
                f"Expected one ANDES state named {state_name!r}; found {state_indexes.size}."
            )
    return folded_state_names


def run_andes_stability(
    case_path: Path,
    case_label: str,
    output_dir: Path | None = None,
    power_flow_tolerance: float = 1.0e-13,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Solve and export one ANDES small-signal case.

    :param case_path: ANDES-readable case file.
    :param case_label: Filename-safe label used for exported artifacts.
    :param output_dir: Optional explicit destination directory.
    :param power_flow_tolerance: Newton power-flow convergence tolerance.
    :return: State matrix, eigenvalues, right vectors, left vectors and factors.
    """
    total_start: float = time.perf_counter()
    timings: dict[str, float] = dict()

    # Stage 1: identify the exact source and prepare a deterministic destination.
    resolved_case_path: Path = case_path.resolve()
    source_hash: str = hashlib.sha256(resolved_case_path.read_bytes()).hexdigest()
    script_dir: Path = Path(__file__).resolve().parent
    if output_dir is None:
        results_dir: Path = script_dir / f"{case_label}_small_signal_rms_results_Andes"
    else:
        results_dir = output_dir.resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    np.set_printoptions(precision=15, suppress=False)
    print(f"Loading case: {resolved_case_path}")
    print(f"ANDES package: {Path(andes.__file__).resolve()}")
    print(f"ANDES version: {andes.__version__}")
    print(f"Case SHA-256: {source_hash}")

    # Stage 2: solve a constant-power operating point using a strict tolerance.
    model_start: float = time.perf_counter()
    system: Any = andes.load(
        str(resolved_case_path),
        default_config=True,
        setup=False,
    )
    system.files.no_output = True
    system.PQ.config.p2p = 1.0
    system.PQ.config.p2i = 0
    system.PQ.config.p2z = 0
    system.PQ.config.q2q = 1.0
    system.PQ.config.q2i = 0
    system.PQ.config.q2z = 0
    system.PFlow.config.tol = power_flow_tolerance
    timings["case_and_model_build"] = elapsed_seconds(model_start)
    setup_start: float = time.perf_counter()
    setup_success: bool = bool(system.setup())
    timings["symbolic_to_numeric"] = elapsed_seconds(setup_start)
    if setup_success:
        pass
    else:
        raise RuntimeError(
            f"ANDES symbolic-to-numeric setup failed for {resolved_case_path}."
        )
    power_flow_start: float = time.perf_counter()
    power_flow_success: bool = bool(system.PFlow.run())
    timings["power_flow"] = elapsed_seconds(power_flow_start)
    if power_flow_success:
        pass
    else:
        raise RuntimeError(
            f"ANDES power flow did not converge for {resolved_case_path} "
            f"with tolerance {power_flow_tolerance:.3e}."
        )

    # Stage 3: initialize the DAE, canonicalize exact zero-parameter IEEEST
    # pass-throughs, then let ANDES fold all zero-mass states and calculate EIG.
    eig: Any = system.EIG
    initialization_start: float = time.perf_counter()
    system.TDS.init()
    system.TDS.itm_step()
    timings["dynamic_initialization"] = elapsed_seconds(initialization_start)
    preprocessing_start: float = time.perf_counter()
    folded_ieeest_states: list[str] = _fold_zero_ieeest_input_filter_states(system)
    folded_bus_frequency_states: list[str] = _fold_unused_bus_frequency_states(system)
    timings["benchmark_preprocessing"] = elapsed_seconds(preprocessing_start)
    small_signal_start: float = time.perf_counter()
    eig.run()
    timings["small_signal_total"] = elapsed_seconds(small_signal_start)

    # Repeat the numerical kernels once after initialization. These isolated
    # warm measurements match the VeraGrid diagnostic repeats and are excluded
    # from both ``small_signal_total`` and ``end_to_end``.
    state_matrix_repeat_start: float = time.perf_counter()
    eig.calc_As()
    timings["state_matrix_isolated_repeat"] = elapsed_seconds(state_matrix_repeat_start)
    eigenanalysis_repeat_start: float = time.perf_counter()
    eig.mu, eig.pfactors, eig.N, eig.W = eig.calc_pfactor()
    timings["eigenanalysis_isolated_repeat"] = elapsed_seconds(eigenanalysis_repeat_start)
    state_names: list[str] = list(eig.x_name)
    state_matrix: np.ndarray = np.asarray(eig.As, dtype=complex)
    eigenvalues: np.ndarray = np.asarray(eig.mu, dtype=complex)
    right_eigenvectors: np.ndarray = np.asarray(eig.N, dtype=complex)
    left_eigenvectors: np.ndarray = np.asarray(eig.W, dtype=complex)
    participation_factors: np.ndarray = np.asarray(eig.pfactors, dtype=float)

    print(f"\nReduced differential states: {len(state_names)}")
    print(f"Zero-time-constant states folded as constraints: {len(eig.zstate_idx)}")
    if len(folded_ieeest_states) > 0:
        print("Canonical zero-parameter IEEEST states folded as constraints:")
        folded_ieeest_state: str
        for folded_ieeest_state in folded_ieeest_states:
            print(f"  - {folded_ieeest_state}")
    else:
        pass
    if len(folded_bus_frequency_states) > 0:
        print("Unused BusFreq states folded as constraints:")
        folded_bus_frequency_state: str
        for folded_bus_frequency_state in folded_bus_frequency_states:
            print(f"  - {folded_bus_frequency_state}")
    else:
        pass

    # Stage 4: export the common inputs consumed by the visual comparator.
    export_start: float = time.perf_counter()
    pd.DataFrame(eigenvalues).to_csv(
        results_dir / f"Eigenvalues_results_Andes_{case_label}.csv",
        index=False,
        header=False,
    )
    pd.DataFrame(participation_factors.T).to_csv(
        results_dir / f"pfactors_results_Andes_{case_label}.csv",
        index=False,
        header=False,
        float_format="%.10f",
    )
    _write_state_matrix(
        output_path=results_dir / f"state_matrix_results_Andes_{case_label}.csv",
        state_matrix=state_matrix,
        state_names=state_names,
    )
    pd.DataFrame(
        list(enumerate(state_names)),
        columns=list(("index", "state")),
    ).to_csv(results_dir / f"state_names_Andes_{case_label}.csv", index=False)
    _write_static_tables(system=system, results_dir=results_dir, case_label=case_label)
    timings["result_export"] = elapsed_seconds(export_start)
    timings["end_to_end"] = elapsed_seconds(total_start) - (
        timings["state_matrix_isolated_repeat"]
        + timings["eigenanalysis_isolated_repeat"]
    )
    save_benchmark_timings(
        output_directory=results_dir,
        engine_label="Andes",
        case_label=case_label,
        timings=timings,
        state_count=len(state_names),
        mode_count=int(eigenvalues.size),
    )

    print("\nEigenvalues:")
    print(eigenvalues)
    print(f"\nANDES {case_label} results written to: {results_dir}")
    return state_matrix, eigenvalues, right_eigenvectors, left_eigenvectors, participation_factors


def _build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line interface for preset and custom ANDES cases.

    :return: Configured argument parser.
    """
    # PyCharm Run selector: change only this enum member. A command-line
    # --case argument, when supplied, still overrides it.
    pycharm_default_case: AndesBenchmarkCase = AndesBenchmarkCase.NPCC140

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Run ANDES EIG for Kundur, IEEE14, IEEE39, NPCC140, WECC179 or "
            "an explicit case file."
        )
    )
    parser.add_argument("--case", type=_parse_case_name, default=pycharm_default_case)
    parser.add_argument("--case-file", type=Path, default=None)
    parser.add_argument("--label", type=str, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main() -> None:
    """Parse command-line options and run the selected ANDES case.

    :return: None.
    """
    parser: argparse.ArgumentParser = _build_argument_parser()
    arguments: argparse.Namespace = parser.parse_args()
    script_dir: Path = Path(__file__).resolve().parent

    if arguments.case_file is None:
        selected_case: AndesBenchmarkCase = arguments.case
        case_path: Path = _resolve_case_path(case_tpe=selected_case, script_dir=script_dir)
        default_label: str = _case_label(case_tpe=selected_case)
        power_flow_tolerance: float = _power_flow_tolerance(case_tpe=selected_case)
    else:
        case_path = arguments.case_file
        default_label = case_path.stem
        power_flow_tolerance = 1.0e-13

    if arguments.label is None:
        case_label: str = default_label
    else:
        case_label = str(arguments.label)

    run_andes_stability(
        case_path=case_path,
        case_label=case_label,
        output_dir=arguments.output_dir,
        power_flow_tolerance=power_flow_tolerance,
    )


if __name__ == "__main__":
    main()
else:
    pass
