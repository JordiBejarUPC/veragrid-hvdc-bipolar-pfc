# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import json
import csv
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import List
from typing import Any

from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
import scipy.sparse as sp

from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType
from VeraGridEngine.enumerations import RmsInitializationMethod
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.shunt import Shunt
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.shunt_template import get_shunt_template
from VeraGridEngine.Templates.Rms.transformer_rms_template import get_transformer2w_rms
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
import VeraGridEngine.api as gce

from trunk.dynamics.small_signal.ieee14_rms_model_config import get_ieee14_genrou_rms_template
from trunk.dynamics.small_signal.rms_kundur_small_signal import save_small_signal_results_to_csv
from trunk.dynamics.small_signal.rms_kundur_small_signal import plot_s_domain_eigenvalues


def _format_complex(value: complex, decimals: int = 12) -> str:
    """Return one complex number in CSV-friendly format.

    :param value: Complex value.
    :param decimals: Number of decimals.
    :return: Formatted string.
    """
    complex_value: complex = complex(value)
    return f"{complex_value.real:.{decimals}e}{complex_value.imag:+.{decimals}e}j"


def _to_builtin(value: Any) -> Any:
    """Convert a NumPy or container value into JSON-compatible built-ins.

    :param value: Value to convert.
    :return: JSON-compatible value.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    elif isinstance(value, np.generic):
        return value.item()
    elif isinstance(value, dict):
        return {str(key): _to_builtin(val) for key, val in value.items()}
    elif isinstance(value, (list, tuple)):
        return [_to_builtin(item) for item in value]
    else:
        return str(value)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write deterministic diagnostic JSON data.

    :param path: Destination path.
    :param data: Serializable diagnostic mapping.
    :return: None.
    """
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


def _write_records_csv(path: Path, records: list[dict[str, Any]]) -> None:
    """Write a homogeneous record collection to CSV.

    :param path: Destination path.
    :param records: Records with a common field layout.
    :return: None.
    """
    if not records:
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write("")
        return
    else:
        pass

    fieldnames = list(records[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow({key: _to_builtin(row.get(key)) for key in fieldnames})


def _assert_unique_labels(labels: List[str], label_type: str) -> None:
    """Reject duplicate compiled-variable labels.

    :param labels: Labels to validate.
    :param label_type: Human-readable label category.
    :return: None.
    """
    seen: set[str] = set()
    duplicates: list[str] = list()
    for label in labels:
        if label in seen:
            duplicates.append(label)
        else:
            seen.add(label)
    if duplicates:
        raise ValueError(f"Duplicate {label_type} labels found: {duplicates}")
    else:
        pass


def _compiled_var_labels(problem: RmsProblemDae, vars_list: List[Any], prefix: str) -> List[str]:
    """Build stable owner-qualified labels for compiled variables.

    :param problem: Compiled RMS DAE problem.
    :param vars_list: Variables to label.
    :param prefix: Variable-family prefix.
    :return: Unique compiled labels.
    """
    labels: List[str] = list()
    uid_to_device_vars = problem.get_device_vars_dict()
    owner_by_uid: dict[int, str] = dict()
    for device, device_vars in uid_to_device_vars.items():
        for device_var in device_vars:
            owner_by_uid[device_var.uid] = f"{device.device_type.value}[{device.name}]"

    for var in vars_list:
        owner = owner_by_uid.get(var.uid, "UnknownDevice")
        labels.append(f"{prefix}:{owner}:{var.name}:uid={var.uid}")

    _assert_unique_labels(labels, prefix)
    return labels


def _write_real_matrix_csv(path: Path, matrix: Any, row_labels: List[str], column_labels: List[str]) -> None:
    """Write one real-valued matrix with labeled axes.

    :param path: Destination CSV path.
    :param matrix: Dense or sparse matrix.
    :param row_labels: Row labels.
    :param column_labels: Column labels.
    :return: None.
    """
    dense: np.ndarray = matrix.toarray() if sp.issparse(matrix) else np.asarray(matrix)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("row," + ",".join(column_labels) + "\n")
        row_index = 0
        while row_index < len(row_labels):
            values = ",".join(f"{float(dense[row_index, col_index]):.12e}" for col_index in range(len(column_labels)))
            handle.write(f"{row_labels[row_index]},{values}\n")
            row_index += 1


def _save_veragrid_compiled_manifest(problem: RmsProblemDae, results: Any, output_dir: Path) -> None:
    """Export the compiled IEEE14 DAE manifest used for ANDES auditing.

    :param problem: Compiled RMS DAE problem.
    :param results: Small-signal results object.
    :param output_dir: Destination folder.
    :return: None.
    """
    x0 = problem.get_x0()
    dx0 = problem.get_dx0()
    h = problem.get_dt_value()

    state_vars = list(problem.state_vars)
    algebraic_vars = list(problem.algebraic_vars)
    diff_vars = list(problem.get_diff_vars())

    state_labels = _compiled_var_labels(problem=problem, vars_list=state_vars, prefix="x")
    algebraic_labels = _compiled_var_labels(problem=problem, vars_list=algebraic_vars, prefix="y")
    diff_labels = [f"xdot:{var.name}:uid={var.uid}:base_uid={var.base_var.uid if var.base_var is not None else 'none'}" for var in diff_vars]
    _assert_unique_labels(diff_labels, "xdot")

    fx = problem.get_fx_ct(x0, dx0)
    fy = problem.get_fy_ct(x0, dx0)
    gx = problem.get_gx_ct(x0, dx0)
    gy = problem.get_gy_ct(x0, dx0)
    e_matrix = problem.get_E_matrix(x0, dx0)
    static_matrix = problem.get_static_state_matrix(x0, dx0)
    f_values = problem.rhs_state(x0, dx0)
    g_values = problem.rhs_algebraic(x0, dx0)
    fx_dense: np.ndarray = fx.toarray() if sp.issparse(fx) else np.asarray(fx, dtype=float)
    fy_dense: np.ndarray = fy.toarray() if sp.issparse(fy) else np.asarray(fy, dtype=float)
    gx_dense: np.ndarray = gx.toarray() if sp.issparse(gx) else np.asarray(gx, dtype=float)
    gy_dense: np.ndarray = gy.toarray() if sp.issparse(gy) else np.asarray(gy, dtype=float)
    as_ct = fx_dense - fy_dense @ np.linalg.solve(gy_dense, gx_dense)

    owner_records: list[dict[str, Any]] = list()
    uid_to_device_vars = problem.get_device_vars_dict()
    for device, device_vars in uid_to_device_vars.items():
        for device_var in device_vars:
            owner_records.append(
                dict(
                    uid=int(device_var.uid),
                    var_name=str(device_var.name),
                    device_name=str(device.name),
                    device_type=str(device.device_type.value),
                )
            )

    diff_uid_set: set[int] = set(int(var.uid) for var in diff_vars)
    state_records = list()
    for index, var in enumerate(state_vars):
        state_records.append(
            dict(
                index=index,
                label=state_labels[index],
                uid=int(var.uid),
                name=str(var.name),
                initial_value=float(x0[index]),
                residual=float(f_values[index]),
                equation=str(problem.state_eqs[index]),
                is_diff_var=int(var.uid) in diff_uid_set,
            )
        )

    algebraic_records = list()
    for index, var in enumerate(algebraic_vars):
        algebraic_records.append(
            dict(
                index=index,
                label=algebraic_labels[index],
                uid=int(var.uid),
                name=str(var.name),
                initial_value=float(x0[len(state_vars) + index]),
                residual=float(g_values[index]),
                equation=str(problem.algebraic_eqs[index]),
            )
        )

    manifest: dict[str, object] = dict(
        compiled_counts=dict(
            state_count=len(state_vars),
            algebraic_count=len(algebraic_vars),
            diff_var_count=len(diff_vars),
            state_matrix_size=list(results.state_matrix.shape),
        ),
        compiled_labels=dict(
            state_labels=state_labels,
            algebraic_labels=algebraic_labels,
            diff_labels=diff_labels,
            results_stat_vars_array=[_to_builtin(item) for item in list(results.stat_vars_array)],
            results_algebraic_vars_array=[_to_builtin(item) for item in list(results.algebraic_vars_array)],
        ),
        residuals=dict(
            f_inf_norm=float(max(abs(float(value)) for value in f_values)) if len(f_values) else 0.0,
            g_inf_norm=float(max(abs(float(value)) for value in g_values)) if len(g_values) else 0.0,
        ),
    )

    _write_json(output_dir / "manifest_VeraGrid_IEEE14.json", manifest)
    _write_records_csv(output_dir / "compiled_state_records_VeraGrid_IEEE14.csv", state_records)
    _write_records_csv(output_dir / "compiled_algebraic_records_VeraGrid_IEEE14.csv", algebraic_records)
    _write_records_csv(output_dir / "compiled_owner_records_VeraGrid_IEEE14.csv", owner_records)
    with (output_dir / "reduced_state_labels_VeraGrid_IEEE14.csv").open("w", encoding="utf-8", newline="") as handle:
        handle.write("index,label\n")
        for index, label in enumerate(state_labels):
            handle.write(f"{index},{label}\n")
    _write_real_matrix_csv(output_dir / "fx_VeraGrid_IEEE14.csv", fx, state_labels, state_labels)
    _write_real_matrix_csv(output_dir / "fy_VeraGrid_IEEE14.csv", fy, state_labels, algebraic_labels)
    _write_real_matrix_csv(output_dir / "gx_VeraGrid_IEEE14.csv", gx, algebraic_labels, state_labels)
    _write_real_matrix_csv(output_dir / "gy_VeraGrid_IEEE14.csv", gy, algebraic_labels, algebraic_labels)
    _write_real_matrix_csv(output_dir / "E_VeraGrid_IEEE14.csv", e_matrix, state_labels + algebraic_labels, state_labels + algebraic_labels)
    _write_real_matrix_csv(output_dir / "J_static_VeraGrid_IEEE14.csv", static_matrix, state_labels + algebraic_labels, state_labels + algebraic_labels)
    _write_real_matrix_csv(output_dir / "As_ct_VeraGrid_IEEE14.csv", as_ct, state_labels, state_labels)
    with (output_dir / "state_matrix_compiled_labeled_VeraGrid_IEEE14.csv").open("w", encoding="utf-8", newline="") as handle:
        handle.write("equation," + ",".join(state_labels) + "\n")
        matrix = as_ct
        row_index = 0
        while row_index < matrix.shape[0]:
            row_values = ",".join(_format_complex(matrix[row_index, column_index]) for column_index in range(matrix.shape[1]))
            handle.write(f"{state_labels[row_index]},{row_values}\n")
            row_index += 1


def _collect_state_labels_from_block(block: Any, labels: List[str]) -> None:
    """Collect state labels recursively from one benchmark block.

    :param block: Symbolic block.
    :param labels: Mutable label list.
    :return: None.
    """
    state_var_count = len(block.state_vars)
    state_var_index = 0
    while state_var_index < state_var_count:
        labels.append(str(block.state_vars[state_var_index]))
        state_var_index += 1

    child_count = len(block.children)
    child_index = 0
    while child_index < child_count:
        _collect_state_labels_from_block(block.children[child_index], labels)
        child_index += 1


def _build_benchmark_state_labels(grid: gce.MultiCircuit) -> List[str]:
    """Build benchmark state labels from the attached generator wrappers.

    :param grid: Benchmark grid.
    :return: State labels.
    """
    labels: List[str] = list()

    generator_count = len(grid.generators)
    generator_index = 0
    while generator_index < generator_count:
        generator = grid.generators[generator_index]
        _collect_state_labels_from_block(generator.rms_model, labels)
        generator_index += 1

    return labels


def _save_benchmark_state_matrix_and_participation(
    grid: gce.MultiCircuit,
    results: Any,
    output_dir: Path,
) -> None:
    """Save benchmark-specific labeled state matrix and participation factors.

    :param grid: Benchmark grid.
    :param results: Small-signal results object.
    :param output_dir: Destination directory.
    :return: None.
    """
    state_labels = _build_benchmark_state_labels(grid)
    state_count = len(state_labels)

    state_matrix = results.state_matrix
    with (output_dir / "state_matrix_benchmark_labeled.csv").open("w", encoding="utf-8", newline="") as csv_file:
        csv_file.write("equation," + ",".join(state_labels) + "\n")

        row_count = int(state_matrix.shape[0])
        row_index = 0
        while row_index < row_count:
            if row_index < state_count:
                row_label = state_labels[row_index]
            else:
                row_label = f"Equation {row_index + 1}"

            row_values = list()
            column_count = int(state_matrix.shape[1])
            column_index = 0
            while column_index < column_count:
                row_values.append(_format_complex(state_matrix[row_index, column_index]))
                column_index += 1

            csv_file.write(row_label + "," + ",".join(row_values) + "\n")
            row_index += 1

    participation = results.participation_factors
    participation_row_count = int(participation.shape[0])

    if participation_row_count > state_count:
        participation = participation[:state_count, :]
    else:
        pass

    with (output_dir / "participation_factors_benchmark_labeled.csv").open("w", encoding="utf-8", newline="") as csv_file:
        mode_count = int(participation.shape[1])
        mode_labels = list()
        mode_index = 0
        while mode_index < mode_count:
            mode_labels.append(f"Mode {mode_index + 1}")
            mode_index += 1

        csv_file.write("state," + ",".join(mode_labels) + "\n")

        row_count = int(participation.shape[0])
        row_index = 0
        while row_index < row_count:
            if row_index < state_count:
                row_label = state_labels[row_index]
            else:
                row_label = f"State {row_index + 1}"

            row_values = list()
            column_count = int(participation.shape[1])
            column_index = 0
            while column_index < column_count:
                row_values.append(f"{float(participation[row_index, column_index]):.12e}")
                column_index += 1

            csv_file.write(row_label + "," + ",".join(row_values) + "\n")
            row_index += 1


def _get_base_grid_path() -> Path:
    """Return the IEEE14 base-grid path.

    :return: Base-grid path.
    """
    base_dir: Path = Path(__file__).resolve().parents[3]
    grid_path: Path = base_dir / "Grids_and_profiles" / "grids" / "IEEE14_from_raw.gridcal"
    return grid_path.resolve()


def _get_andes_ieee14_json_path() -> Path:
    """Return the ANDES IEEE14 source-case path."""
    return Path("C:/Users/maria/PycharmProjects/andes/andes/cases/ieee14/ieee14.json")


def _get_andes_ieee14_full_xlsx_path() -> Path:
    """Return the ANDES IEEE14 full benchmark workbook path."""
    return Path("C:/Users/maria/PycharmProjects/andes/andes/cases/ieee14/ieee14_full.xlsx")


def _load_andes_ieee14_case() -> dict[str, Any]:
    """Load the ANDES IEEE14 JSON case used as benchmark source of truth."""
    with _get_andes_ieee14_json_path().open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_ieee14_network_from_andes_case() -> gce.MultiCircuit:
    """Build the IEEE14 network explicitly from the ANDES full benchmark workbook."""
    workbook_path: Path = _get_andes_ieee14_full_xlsx_path()
    workbook: pd.ExcelFile = pd.ExcelFile(workbook_path)
    grid: gce.MultiCircuit = gce.MultiCircuit()

    bus_df: pd.DataFrame = pd.read_excel(workbook, sheet_name="Bus")
    slack_df: pd.DataFrame = pd.read_excel(workbook, sheet_name="Slack")
    pv_df: pd.DataFrame = pd.read_excel(workbook, sheet_name="PV")
    pq_df: pd.DataFrame = pd.read_excel(workbook, sheet_name="PQ")
    shunt_df: pd.DataFrame = pd.read_excel(workbook, sheet_name="Shunt")
    line_df: pd.DataFrame = pd.read_excel(workbook, sheet_name="Line")

    slack_bus_numbers: set[int] = set()
    slack_row_count: int = len(slack_df.index)
    slack_row_index: int = 0
    while slack_row_index < slack_row_count:
        slack_bus_numbers.add(int(slack_df.iloc[slack_row_index]["bus"]))
        slack_row_index += 1

    bus_map: dict[int, Bus] = dict()
    bus_row_count: int = len(bus_df.index)
    bus_row_index: int = 0
    while bus_row_index < bus_row_count:
        bus_row = bus_df.iloc[bus_row_index]
        bus_number: int = int(bus_row["idx"])
        bus = Bus(
            name=str(bus_row["name"]),
            Vnom=float(bus_row["Vn"]),
            vmin=float(bus_row["vmin"]),
            vmax=float(bus_row["vmax"]),
            Vm0=float(bus_row["v0"]),
            Va0=float(bus_row["a0"]),
            is_slack=bus_number in slack_bus_numbers,
        )
        grid.add_bus(bus)
        bus_map[bus_number] = bus
        bus_row_index += 1

    slack_generator_count: int = len(slack_df.index)
    slack_generator_index: int = 0
    while slack_generator_index < slack_generator_count:
        slack_row = slack_df.iloc[slack_generator_index]
        generator = Generator(
            name=str(slack_row["name"]),
            P=float(slack_row["p0"]) * 100.0,
            Q=float(slack_row["q0"]) * 100.0,
            vset=float(slack_row["v0"]),
            Snom=float(slack_row["Sn"]),
            Pmax=float(slack_row["pmax"]) * 100.0,
            Pmin=float(slack_row["pmin"]) * 100.0,
            # ANDES PFlow does not enforce the static-generator Q limits in this
            # benchmark. Wide limits prevent VeraGrid's result allocator from
            # clipping the Q value later consumed by GENROU initialization.
            Qmax=999900.0,
            Qmin=-999900.0,
            r1=float(slack_row["ra"]),
            x1=float(slack_row["xs"]),
            freq=60.0,
        )
        grid.add_generator(bus=bus_map[int(slack_row["bus"])], api_obj=generator)
        slack_generator_index += 1

    pv_generator_count: int = len(pv_df.index)
    pv_generator_index: int = 0
    while pv_generator_index < pv_generator_count:
        pv_row = pv_df.iloc[pv_generator_index]
        generator = Generator(
            name=str(pv_row["name"]),
            P=float(pv_row["p0"]) * 100.0,
            Q=float(pv_row["q0"]) * 100.0,
            vset=float(pv_row["v0"]),
            Snom=float(pv_row["Sn"]),
            Pmax=float(pv_row["pmax"]) * 100.0,
            Pmin=float(pv_row["pmin"]) * 100.0,
            # Match the effective ANDES PFlow configuration (no Q-limit
            # enforcement) so the dynamic seed uses the solved generator Q.
            Qmax=999900.0,
            Qmin=-999900.0,
            r1=float(pv_row["ra"]),
            x1=float(pv_row["xs"]),
            freq=60.0,
        )
        grid.add_generator(bus=bus_map[int(pv_row["bus"])], api_obj=generator)
        pv_generator_index += 1

    load_count: int = len(pq_df.index)
    load_index: int = 0
    while load_index < load_count:
        load_row = pq_df.iloc[load_index]
        load = Load(
            name=str(load_row["name"]),
            P=float(load_row["p0"]) * 100.0,
            Q=float(load_row["q0"]) * 100.0,
        )
        grid.add_load(bus=bus_map[int(load_row["bus"])], api_obj=load)
        load_index += 1

    shunt_count: int = len(shunt_df.index)
    shunt_index: int = 0
    while shunt_index < shunt_count:
        shunt_row = shunt_df.iloc[shunt_index]
        shunt = Shunt(
            name=str(shunt_row["name"]),
            G=float(shunt_row["g"]) * 100.0,
            B=float(shunt_row["b"]) * 100.0,
        )
        grid.add_shunt(bus=bus_map[int(shunt_row["bus"])], api_obj=shunt)
        shunt_index += 1

    line_count: int = len(line_df.index)
    line_index: int = 0
    while line_index < line_count:
        line_row = line_df.iloc[line_index]
        if float(line_row["trans"]) != 0.0:
            transformer = Transformer2W(
                name=str(line_row["name"]),
                bus_from=bus_map[int(line_row["bus1"])],
                bus_to=bus_map[int(line_row["bus2"])],
                HV=float(line_row["Vn1"]),
                LV=float(line_row["Vn2"]),
                nominal_power=float(line_row["Sn"]),
                rate=float(line_row["Sn"]),
                r=float(line_row["r"]),
                x=float(line_row["x"]),
                g=float(line_row["g"]),
                b=float(line_row["b"]),
                tap_module=float(line_row["tap"]),
                tap_phase=float(line_row["phi"]),
            )
            grid.add_transformer2w(transformer)
        else:
            line = Line(
                name=str(line_row["name"]),
                bus_from=bus_map[int(line_row["bus1"])],
                bus_to=bus_map[int(line_row["bus2"])],
                r=float(line_row["r"]),
                x=float(line_row["x"]),
                b=float(line_row["b"]),
                rate=float(line_row["Sn"]),
            )
            grid.add_line(line)
        line_index += 1

    return grid


def _get_output_grid_path() -> Path:
    """Return the RMS-ready IEEE14 output path.

    :return: Output path.
    """
    return Path(__file__).resolve().parent / "ieee14_rms_sss.veragrid"


def _get_results_dir() -> Path:
    """Return the IEEE14 VeraGrid results directory.

    :return: Results directory.
    """
    return Path(__file__).resolve().parent / "ieee14_small_signal_rms_results_VeraGrid"


def _assign_ieee14_rms_models(grid: gce.MultiCircuit) -> None:
    """Assign ANDES-aligned RMS models to the IEEE14 grid.

    :param grid: VeraGrid network.
    :return: None.
    """
    bus_list: List[object] = list(grid.buses)
    for bus in bus_list:
        initialize_bus_rms(bus, vf=grid.var_factory)

    generator_count: int = len(grid.generators)
    generator_index: int = 0
    while generator_index < generator_count:
        generator = grid.generators[generator_index]
        generator_block = get_ieee14_genrou_rms_template(
            vfactory=grid.var_factory,
            generator_index=generator_index,
            name=f"ieee14_gen_{generator_index + 1}",
        ).block

        grid.var_factory.add_connections(
            list((generator_block.in_vars[0],)),
            list((generator.bus.rms_model.out_vars[0],)),
        )
        grid.var_factory.add_connections(
            list((generator_block.in_vars[1],)),
            list((generator.bus.rms_model.out_vars[1],)),
        )

        generator_wrapper = generator_block

        generator.rms_model = generator_wrapper
        generator_index += 1

    line_count: int = len(grid.lines)
    line_index: int = 0
    while line_index < line_count:
        line = grid.lines[line_index]
        line_model = get_line_rms_template(grid.var_factory, name=f"ieee14_line_{line_index + 1}").block
        set_rms_model(device=line, model=line_model, var_factory=grid.var_factory)
        line_index += 1

    transformer_count: int = len(grid.transformers2w)
    transformer_index: int = 0
    while transformer_index < transformer_count:
        transformer = grid.transformers2w[transformer_index]
        # IEEE14 has non-unity taps, so its RMS network needs the transformer
        # equations rather than the symmetric line approximation used by Kundur.
        transformer_model = get_transformer2w_rms(grid.var_factory).block
        transformer_model.name = f"ieee14_transformer_{transformer_index + 1}"
        set_rms_model(device=transformer, model=transformer_model, var_factory=grid.var_factory)
        transformer_index += 1

    load_count: int = len(grid.loads)
    load_index: int = 0
    while load_index < load_count:
        load = grid.loads[load_index]
        load_model = get_load_rms_template(grid.var_factory, name=f"ieee14_load_{load_index + 1}").block
        set_rms_model(device=load, model=load_model, var_factory=grid.var_factory)
        load_index += 1

    shunt_count: int = len(grid.shunts)
    shunt_index: int = 0
    while shunt_index < shunt_count:
        shunt = grid.shunts[shunt_index]
        shunt_model = get_shunt_template(
            grid.var_factory,
            name=f"ieee14_shunt_{shunt_index + 1}",
            phasor=False,
        ).block
        shunt_vm = shunt_model.E(VarPowerFlowReferenceType.Vm)
        shunt_p = shunt_model.E(VarPowerFlowReferenceType.P)
        shunt_q = shunt_model.E(VarPowerFlowReferenceType.Q)
        shunt_g = shunt_model.api_obj_mapping[ParamPowerFlowReferenceType.g]
        shunt_b = shunt_model.api_obj_mapping[ParamPowerFlowReferenceType.b]
        shunt_model.event_dict[shunt_g] = grid.var_factory.add_const(
            value=shunt.G / grid.Sbase,
            name="g",
        )
        shunt_model.event_dict[shunt_b] = grid.var_factory.add_const(
            value=shunt.B / grid.Sbase,
            name="b",
        )
        shunt_model.init_eqs[shunt_p] = -shunt_g * shunt_vm ** 2
        shunt_model.init_eqs[shunt_q] = shunt_b * shunt_vm ** 2
        set_rms_model(device=shunt, model=shunt_model, var_factory=grid.var_factory)
        shunt_index += 1



def _build_power_flow_options() -> PowerFlowOptions:
    """Build the power-flow options for the benchmark.

    :return: Power-flow options.
    """
    options: PowerFlowOptions = PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-14,
        max_iter=25,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=False,
        apply_temperature_correction=False,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=True,
        initialize_angles=False,
        generate_report=False,
    )
    return options


def _build_rms_options() -> RmsOptions:
    """Build the RMS options for the benchmark.

    :return: RMS options.
    """
    options: RmsOptions = RmsOptions(
        time_step=0.001,
        simulation_time=10.0,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=1000,
        verbose=0,
    )
    return options


def build_ieee14_rms_benchmark_grid() -> gce.MultiCircuit:
    """Build the IEEE14 RMS-ready benchmark grid.

    :return: RMS-ready grid.
    """
    grid: gce.MultiCircuit = _build_ieee14_network_from_andes_case()
    _assign_ieee14_rms_models(grid)
    output_path: Path = _get_output_grid_path()
    gce.save_file(grid=grid, filename=str(output_path))
    return grid


def run_ieee14_small_signal() -> None:
    """Run the IEEE14 RMS small-signal benchmark.

    :return: None.
    """
    grid: gce.MultiCircuit = build_ieee14_rms_benchmark_grid()
    pf_options: PowerFlowOptions = _build_power_flow_options()
    power_flow: PowerFlowDriver = PowerFlowDriver(grid, pf_options)
    power_flow.run()
    pf_results: PowerFlowResults = power_flow.results

    rms_options: RmsOptions = _build_rms_options()
    ss_options: RmsSmallSignalStabilityOptions = RmsSmallSignalStabilityOptions(ss_assessment_time=0.0)
    # The current working tree contains temporary initialization diagnostics in
    # shared engine code. Keep this benchmark's public output concise without
    # changing that engine file or its behavior.
    initialization_output: StringIO = StringIO()
    with redirect_stdout(initialization_output):
        driver: SmallSignalStabilityRmsDriver = SmallSignalStabilityRmsDriver(
            grid=grid,
            rms_options=rms_options,
            sss_options=ss_options,
            pf_results=pf_results,
        )
        driver.run()

    results_dir: Path = _get_results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)

    # Save a non-blocking diagnostic plot so the script is suitable for direct
    # execution from an IDE or terminal without requiring GUI interaction.
    plot_s_domain_eigenvalues(driver.results.eigenvalues)
    figure_path: Path = results_dir / "IEEE14_eigenvalues_VeraGrid.png"
    plt.savefig(figure_path, dpi=160)
    plt.close()

    save_small_signal_results_to_csv(driver.results, pf_results, results_dir)
    _save_veragrid_compiled_manifest(problem=driver.problem, results=driver.results, output_dir=results_dir)
    _save_benchmark_state_matrix_and_participation(grid=grid, results=driver.results, output_dir=results_dir)

    eigenvalue_count: int = int(np.asarray(driver.results.eigenvalues).size)
    print(f"IEEE14 VeraGrid completed: {eigenvalue_count} modes written to {results_dir}")


if __name__ == "__main__":
    run_ieee14_small_signal()
else:
    pass
