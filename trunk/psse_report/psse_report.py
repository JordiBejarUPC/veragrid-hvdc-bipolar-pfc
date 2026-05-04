
import datetime
from typing import Any
import pandas as pd
from VeraGridEngine.IO.raw.raw_parser_writer import read_raw, PsseCircuit
from pathlib import Path


def list_raw_files(folder_path: str | Path) -> list[Path]:
    """
    List all .raw files inside a folder and its subdirectories.

    :param folder_path: Root folder to inspect.
    :return: Sorted list of .raw file paths.
    """

    root_path: Path = Path(folder_path)

    raw_files: list[Path] = list()

    for file_path in root_path.rglob("*"):
        if file_path.is_file():
            if file_path.suffix.lower() == ".raw":
                print(f"Reading {file_path}...")
                raw_files.append(file_path)
            else:
                pass
        else:
            pass

    return raw_files


def get_monthly_psse_circuit_statistics(
        circuits: list[PsseCircuit],
        skip_circuits_without_datetime: bool = True,
) -> dict[str, pd.DataFrame]:
    """
    Build full monthly statistics from a list of PSS/E circuits.

    The function extracts one observation per device and circuit timestamp, then
    computes monthly statistics by device and metric.

    Device identifiers are created as follows:

    - Loads: ``I_ID``
    - Generators: ``I_ID``
    - Branches: ``I_J_CKT``
    - Two-winding transformers: ``I_J_CKT``
    - Three-winding transformers: ``I_J_K_CKT``
    - Buses / nodes: ``I``

    The returned dictionary contains:

    - ``samples``: long-format raw extracted samples.
    - ``statistics``: monthly numeric statistics by device and metric.
    - ``status_statistics``: monthly status-specific statistics for branches
      and transformers.

    :param circuits: List of parsed ``PsseCircuit`` objects.
    :param skip_circuits_without_datetime: If True, circuits without
        ``date_time`` are skipped. If False, they are assigned month
        ``"unknown"``.
    :return: Dictionary of pandas DataFrames.
    """

    rows: list[dict[str, Any]] = list()
    rate_numbers: range = range(1, 13)

    for circuit_index, circuit in enumerate(circuits):
        circuit_datetime: datetime.datetime | None = circuit.date_time

        if circuit_datetime is None:
            if skip_circuits_without_datetime:
                pass
            else:
                month: str = "unknown"
                timestamp: pd.Timestamp | None = None
        else:
            timestamp = pd.Timestamp(circuit_datetime)
            month = timestamp.strftime("%Y-%m")

        if circuit_datetime is not None or not skip_circuits_without_datetime:

            # ------------------------------------------------------------------
            # Load active and reactive power.
            # ------------------------------------------------------------------
            for load in circuit.loads:
                load_id: str = f"{load.I}_{str(load.ID).strip()}"

                rows.append(
                    {
                        "circuit_index": circuit_index,
                        "timestamp": timestamp,
                        "month": month,
                        "element_type": "load",
                        "element_id": load_id,
                        "metric": "P_MW",
                        "value": float(load.PL),
                    }
                )

                rows.append(
                    {
                        "circuit_index": circuit_index,
                        "timestamp": timestamp,
                        "month": month,
                        "element_type": "load",
                        "element_id": load_id,
                        "metric": "Q_MVAr",
                        "value": float(load.QL),
                    }
                )

            # ------------------------------------------------------------------
            # Generator active power.
            # ------------------------------------------------------------------
            for generator in circuit.generators:
                generator_id: str = f"{generator.I}_{str(generator.ID).strip()}"

                rows.append(
                    {
                        "circuit_index": circuit_index,
                        "timestamp": timestamp,
                        "month": month,
                        "element_type": "generator",
                        "element_id": generator_id,
                        "metric": "P_MW",
                        "value": float(generator.PG),
                    }
                )

            # ------------------------------------------------------------------
            # Branch active status and ratings.
            # ------------------------------------------------------------------
            for branch in circuit.branches:
                branch_id: str = f"{branch.I}_{branch.J}_{str(branch.CKT).strip()}"

                rows.append(
                    {
                        "circuit_index": circuit_index,
                        "timestamp": timestamp,
                        "month": month,
                        "element_type": "branch",
                        "element_id": branch_id,
                        "metric": "status",
                        "value": float(branch.ST),
                    }
                )

                for rate_number in rate_numbers:
                    rate_name: str = f"RATE{rate_number}"
                    rate_value: float = float(getattr(branch, rate_name))

                    rows.append(
                        {
                            "circuit_index": circuit_index,
                            "timestamp": timestamp,
                            "month": month,
                            "element_type": "branch",
                            "element_id": branch_id,
                            "metric": rate_name,
                            "value": rate_value,
                        }
                    )

            # ------------------------------------------------------------------
            # Transformer active status and winding ratings.
            # ------------------------------------------------------------------
            for transformer in circuit.transformers:
                if transformer.windings == 3:
                    transformer_id: str = (
                        f"{transformer.I}_"
                        f"{transformer.J}_"
                        f"{transformer.K}_"
                        f"{str(transformer.CKT).strip()}"
                    )
                else:
                    transformer_id = (
                        f"{transformer.I}_"
                        f"{transformer.J}_"
                        f"{str(transformer.CKT).strip()}"
                    )

                rows.append(
                    {
                        "circuit_index": circuit_index,
                        "timestamp": timestamp,
                        "month": month,
                        "element_type": "transformer",
                        "element_id": transformer_id,
                        "metric": "status",
                        "value": float(transformer.STAT),
                    }
                )

                for winding_number in range(1, 4):
                    for rate_number in rate_numbers:
                        rate_name = f"RATE{winding_number}_{rate_number}"

                        if hasattr(transformer, rate_name):
                            rate_value = float(getattr(transformer, rate_name))

                            rows.append(
                                {
                                    "circuit_index": circuit_index,
                                    "timestamp": timestamp,
                                    "month": month,
                                    "element_type": "transformer",
                                    "element_id": transformer_id,
                                    "metric": rate_name,
                                    "value": rate_value,
                                }
                            )
                        else:
                            pass

            # ------------------------------------------------------------------
            # Bus / node voltage magnitude and angle.
            # ------------------------------------------------------------------
            for bus in circuit.buses:
                bus_id: str = str(bus.I)
                bus_name: str = str(bus.NAME).replace("'", "").strip()

                rows.append(
                    {
                        "circuit_index": circuit_index,
                        "timestamp": timestamp,
                        "month": month,
                        "element_type": "bus",
                        "element_id": bus_id,
                        "element_name": bus_name,
                        "metric": "VM_pu",
                        "value": float(bus.VM),
                    }
                )

                rows.append(
                    {
                        "circuit_index": circuit_index,
                        "timestamp": timestamp,
                        "month": month,
                        "element_type": "bus",
                        "element_id": bus_id,
                        "element_name": bus_name,
                        "metric": "VA_deg",
                        "value": float(bus.VA),
                    }
                )
        else:
            pass

    samples: pd.DataFrame = pd.DataFrame(rows)

    if samples.empty:
        statistics: pd.DataFrame = pd.DataFrame()
        status_statistics: pd.DataFrame = pd.DataFrame()
    else:
        statistics = (
            samples
            .groupby(
                [
                    "month",
                    "element_type",
                    "element_id",
                    "element_name",
                    "metric",
                ],
                dropna=False,
            )["value"]
            .agg(
                [
                    "count",
                    "mean",
                    "std",
                    "min",
                    "max",
                    "median",
                    "nunique",
                ]
            )
            .reset_index()
        )

        status_samples: pd.DataFrame = samples[
            (
                    (samples["element_type"] == "branch")
                    | (samples["element_type"] == "transformer")
            )
            & (samples["metric"] == "status")
            ].copy()

        if status_samples.empty:
            status_statistics = pd.DataFrame()
        else:
            status_samples["is_fully_active"] = status_samples["value"] == 1.0
            status_samples["is_out_of_service"] = status_samples["value"] == 0.0

            status_statistics = (
                status_samples
                .groupby(
                    [
                        "month",
                        "element_type",
                        "element_id",
                    ],
                    dropna=False,
                )
                .agg(
                    samples=("value", "count"),
                    status_min=("value", "min"),
                    status_max=("value", "max"),
                    status_mean=("value", "mean"),
                    status_unique_count=("value", "nunique"),
                    fully_active_count=("is_fully_active", "sum"),
                    out_of_service_count=("is_out_of_service", "sum"),
                    fully_active_fraction=("is_fully_active", "mean"),
                    out_of_service_fraction=("is_out_of_service", "mean"),
                )
                .reset_index()
            )

    result: dict[str, pd.DataFrame] = {
        "samples": samples,
        "statistics": statistics,
        "status_statistics": status_statistics,
    }

    return result


def get_branch_voltage_count_tables(
    circuits: list[PsseCircuit],
    file_paths: list[str | Path] | None = None,
    voltage_round_digits: int = 0,
) -> dict[str, pd.DataFrame]:
    """
    Build branch voltage-level count tables per RAW snapshot.

    The voltage level of each branch is inferred from the nominal voltage of
    its terminal buses. For each branch, the voltage is computed as:

    ``max(BASKV_from_bus, BASKV_to_bus)``

    This is suitable for counting lines by voltage level, for example 220 kV
    and 400 kV branches.

    The returned dictionary contains:

    - ``branch_voltage_count``:
        Number of all branches per file and voltage level.

    - ``inactive_branch_voltage_count``:
        Number of inactive branches per file and voltage level.

    :param circuits: List of parsed ``PsseCircuit`` objects.
    :param file_paths: Optional list of RAW file paths matching ``circuits``.
        If provided, file names are used as row labels.
    :param voltage_round_digits: Number of decimals used when grouping voltage
        levels.
    :return: Dictionary with two pivot tables.
    """

    rows: list[dict[str, Any]] = list()

    for circuit_index, circuit in enumerate(circuits):
        if file_paths is None:
            file_label: str = f"snapshot_{circuit_index}"
        else:
            file_label = Path(file_paths[circuit_index]).name

        if circuit.date_time is None:
            timestamp: pd.Timestamp | None = None
            month: str | None = None
        else:
            timestamp = pd.Timestamp(circuit.date_time)
            month = timestamp.strftime("%Y-%m")

        bus_voltage_by_id: dict[int, float] = dict()

        for bus in circuit.buses:
            bus_voltage_by_id[int(bus.I)] = float(bus.BASKV)

        for branch in circuit.branches:
            from_bus_voltage: float | None = bus_voltage_by_id.get(int(branch.I))
            to_bus_voltage: float | None = bus_voltage_by_id.get(int(branch.J))

            if from_bus_voltage is not None and to_bus_voltage is not None:
                branch_voltage: float = max(from_bus_voltage, to_bus_voltage)
                branch_voltage = round(branch_voltage, voltage_round_digits)

                rows.append(
                    {
                        "file": file_label,
                        "timestamp": timestamp,
                        "month": month,
                        "branch_id": f"{branch.I}_{branch.J}_{str(branch.CKT).strip()}",
                        "voltage_kv": branch_voltage,
                        "status": int(branch.ST),
                        "is_inactive": int(branch.ST) == 0,
                    }
                )
            else:
                pass

    branch_voltage_samples: pd.DataFrame = pd.DataFrame(rows)

    if branch_voltage_samples.empty:
        branch_voltage_count: pd.DataFrame = pd.DataFrame()
        inactive_branch_voltage_count: pd.DataFrame = pd.DataFrame()
    else:
        branch_voltage_count = (
            branch_voltage_samples
            .pivot_table(
                index="file",
                columns="voltage_kv",
                values="branch_id",
                aggfunc="count",
                fill_value=0,
            )
            .reset_index()
        )

        inactive_branch_voltage_count = (
            branch_voltage_samples[
                branch_voltage_samples["is_inactive"]
            ]
            .pivot_table(
                index="file",
                columns="voltage_kv",
                values="branch_id",
                aggfunc="count",
                fill_value=0,
            )
            .reset_index()
        )

    result: dict[str, pd.DataFrame] = {
        "branch_voltage_samples": branch_voltage_samples,
        "branch_voltage_count": branch_voltage_count,
        "inactive_branch_voltage_count": inactive_branch_voltage_count,
    }

    return result

def save_monthly_psse_circuit_statistics_xlsx(
    circuits: list[PsseCircuit],
    file_path: str | Path,
    file_paths: list[str | Path] | None = None,
    include_raw_samples: bool = False,
) -> None:
    """
    Save monthly PSS/E circuit statistics into an XLSX file.

    Each device category is written into a different Excel sheet. The function
    also adds branch voltage-level count tables per RAW file.
    """

    output_path: Path = Path(file_path)

    stats: dict[str, pd.DataFrame] = get_monthly_psse_circuit_statistics(
        circuits=circuits,
        skip_circuits_without_datetime=True,
    )

    branch_voltage_tables: dict[str, pd.DataFrame] = get_branch_voltage_count_tables(
        circuits=circuits,
        file_paths=file_paths,
        voltage_round_digits=0,
    )

    statistics: pd.DataFrame = stats["statistics"]
    status_statistics: pd.DataFrame = stats["status_statistics"]
    samples: pd.DataFrame = stats["samples"]

    branch_voltage_samples: pd.DataFrame = branch_voltage_tables["branch_voltage_samples"]
    branch_voltage_count: pd.DataFrame = branch_voltage_tables["branch_voltage_count"]
    inactive_branch_voltage_count: pd.DataFrame = branch_voltage_tables["inactive_branch_voltage_count"]

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        if statistics.empty:
            empty_sheet: pd.DataFrame = pd.DataFrame(
                {
                    "message": [
                        "No monthly statistics were generated. Check that circuits are not empty and have date_time assigned."
                    ]
                }
            )

            empty_sheet.to_excel(
                writer,
                sheet_name="empty",
                index=False,
            )

        else:
            load_statistics: pd.DataFrame = statistics[
                statistics["element_type"] == "load"
            ].copy()

            generator_statistics: pd.DataFrame = statistics[
                statistics["element_type"] == "generator"
            ].copy()

            branch_statistics: pd.DataFrame = statistics[
                statistics["element_type"] == "branch"
            ].copy()

            transformer_statistics: pd.DataFrame = statistics[
                statistics["element_type"] == "transformer"
            ].copy()

            bus_statistics: pd.DataFrame = statistics[
                statistics["element_type"] == "bus"
            ].copy()

            load_statistics.to_excel(
                writer,
                sheet_name="loads",
                index=False,
            )

            generator_statistics.to_excel(
                writer,
                sheet_name="generators",
                index=False,
            )

            branch_statistics.to_excel(
                writer,
                sheet_name="branches",
                index=False,
            )

            transformer_statistics.to_excel(
                writer,
                sheet_name="transformers",
                index=False,
            )

            bus_statistics.to_excel(
                writer,
                sheet_name="buses",
                index=False,
            )

            if not status_statistics.empty:
                branch_status_statistics: pd.DataFrame = status_statistics[
                    status_statistics["element_type"] == "branch"
                ].copy()

                transformer_status_statistics: pd.DataFrame = status_statistics[
                    status_statistics["element_type"] == "transformer"
                ].copy()

                branch_status_statistics.to_excel(
                    writer,
                    sheet_name="branch_status",
                    index=False,
                )

                transformer_status_statistics.to_excel(
                    writer,
                    sheet_name="xfmr_status",
                    index=False,
                )
            else:
                pass

            if include_raw_samples:
                samples.to_excel(
                    writer,
                    sheet_name="raw_samples",
                    index=False,
                )
            else:
                pass

        branch_voltage_count.to_excel(
            writer,
            sheet_name="branch_voltage_count",
            index=False,
        )

        inactive_branch_voltage_count.to_excel(
            writer,
            sheet_name="inactive_branch_v",
            index=False,
        )

        if include_raw_samples:
            branch_voltage_samples.to_excel(
                writer,
                sheet_name="branch_voltage_samples",
                index=False,
            )
        else:
            pass


def main(folder: str = "", stats_file="psse_monthly_statistics.xlsx"):
    """
    Main function
    :return:
    """
    if folder == "":
        current_file_directory: Path = Path(__file__).resolve().parent
    else:
        current_file_directory = Path(folder)

    # Read te files
    filenames = list_raw_files(current_file_directory)

    # read the thing
    grids = list()
    for i, file_path in enumerate(filenames):
        psse_grid = read_raw(file_path)
        grids.append(psse_grid)

    # Sort grids
    grids.sort(key=lambda obj: obj.date_time)

    print("Making stats...")
    save_monthly_psse_circuit_statistics_xlsx(
        circuits=grids,
        file_path=stats_file,
        include_raw_samples=False,
    )
    print(f"Saved to {stats_file}")


if __name__ == "__main__":
    main("/home/santi/Escritorio/Redes/Canarias/Análisis automatizado de la red/Casos/19",
         stats_file="stats.xlsx")