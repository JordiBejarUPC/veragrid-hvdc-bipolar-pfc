from pathlib import Path
import csv
from importlib import import_module


MAT_PATH = Path(__file__).with_name("EXP007.mat")
CSV_PATH = Path(__file__).with_name("EXP007.csv")


def normalize_scalar(value):
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            return str(value)
    return value


def extract_headers_and_rows(mat_data):
    np = import_module("numpy")

    headers = [str(normalize_scalar(item)) for item in np.ravel(mat_data["colNames"]).tolist()]
    rows = np.asarray(mat_data["data"])

    if rows.ndim == 1:
        rows = rows.reshape(-1, len(headers))

    if rows.ndim != 2:
        raise ValueError(f"Unexpected data shape: {rows.shape}")

    if rows.shape[1] != len(headers):
        raise ValueError(
            f"Header count ({len(headers)}) does not match data columns ({rows.shape[1]})"
        )

    return headers, rows


def export_to_csv(headers, rows):
    np = import_module("numpy")

    with CSV_PATH.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(headers)

        for row in np.asarray(rows).tolist():
            writer.writerow([normalize_scalar(item) for item in row])


def main():
    try:
        loadmat = import_module("scipy.io").loadmat
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency: scipy. Install it with `pip install scipy numpy`."
        ) from exc

    data = loadmat(MAT_PATH, squeeze_me=True, struct_as_record=False)
    headers, rows = extract_headers_and_rows(data)

    print(f"File: {MAT_PATH}")
    print(f"Columns: {headers}")
    print(f"Data shape: {rows.shape}")

    export_to_csv(headers, rows)
    print(f"CSV exported to: {CSV_PATH}")


if __name__ == "__main__":
    main()
