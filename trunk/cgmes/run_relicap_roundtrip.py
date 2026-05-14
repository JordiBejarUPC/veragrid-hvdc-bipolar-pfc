import argparse
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType
from VeraGridEngine.IO.file_open import FileOpen, FileOpenOptions, FileType
from VeraGridEngine.IO.file_save import FileSave, FileSavingOptions
from VeraGridEngine.enumerations import CGMESVersions

SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR in sys.path:
    pass
else:
    sys.path.insert(0, SCRIPT_DIR)
from run_relicap_grids import FOLDER, SUBFOLDERS


def create_open_options() -> FileOpenOptions:
    """
    Build file-open options for Relicap CGMES 3.0 roundtrip execution.

    :return: File-open options.
    :rtype: FileOpenOptions
    """
    return FileOpenOptions(
        file_type=FileType.CGMES,
        cgmes_version=CGMESVersions.v3_0_0,
        cgmes_try_to_map_dc_to_hvdc_line=True,
    )


def create_save_options(boundary_zip_path: str) -> FileSavingOptions:
    """
    Build file-save options for CGMES 3.0 export.

    :param boundary_zip_path: Boundary ZIP path.
    :type boundary_zip_path: str
    :return: Save options.
    :rtype: FileSavingOptions
    """
    save_options: FileSavingOptions = FileSavingOptions(file_type=FileType.CGMES)
    save_options.cgmes_version = CGMESVersions.v3_0_0
    save_options.cgmes_boundary_set = boundary_zip_path
    save_options.cgmes_one_file_per_profile = False
    save_options.cgmes_profiles = list([
        CgmesProfileType.EQ,
        CgmesProfileType.OP,
        CgmesProfileType.SC,
        CgmesProfileType.TP,
        CgmesProfileType.SV,
        CgmesProfileType.SSH,
        CgmesProfileType.GL,
        CgmesProfileType.CO,
    ])
    return save_options


def create_boundary_zip(base_folder: str, out_dir: Path) -> str:
    """
    Create a boundary ZIP from Relicap boundaryData Grid CIMXML files.

    :param base_folder: Relicap base folder.
    :type base_folder: str
    :param out_dir: Output directory.
    :type out_dir: Path
    :return: Boundary ZIP path.
    :rtype: str
    """
    boundary_folder: str = os.path.join(base_folder, "boundaryData", "Grid", "cimxml")
    xml_files: list[str] = list()
    file_name: str
    for file_name in sorted(os.listdir(boundary_folder)):
        if file_name.lower().endswith(".xml"):
            xml_files.append(os.path.join(boundary_folder, file_name))
        else:
            pass

    boundary_zip_path: str = str(out_dir / "relicap_boundary.zip")
    with zipfile.ZipFile(boundary_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        xml_file: str
        for xml_file in xml_files:
            arc_name: str = os.path.relpath(xml_file, base_folder)
            zip_file.write(xml_file, arcname=arc_name)
    return boundary_zip_path


def load_cgmes_to_veragrid(file_paths: list[str]) -> object:
    """
    Load CGMES files and return the parsed VeraGrid object.

    :param file_paths: CGMES input files.
    :type file_paths: list[str]
    :return: Parsed VeraGrid model.
    :rtype: object
    """
    handler: FileOpen = FileOpen(file_name=file_paths, options=create_open_options())
    grid: object = handler.open()
    if grid is not None:
        return grid
    else:
        raise RuntimeError("CGMES import returned None grid")


def collect_normalized_ids(items: Iterable[object]) -> set[str]:
    """
    Collect lower-cased idtags from a VeraGrid object iterable.

    :param items: Iterable of device objects.
    :type items: Iterable[object]
    :return: Normalized idtag set.
    :rtype: set[str]
    """
    ids: set[str] = set()
    item: object
    for item in items:
        raw_id: object = item.idtag
        if isinstance(raw_id, str) and len(raw_id) > 0:
            ids.add(raw_id.lower())
        else:
            pass
    return ids


def compare_id_sets(label: str, left: set[str], right: set[str], divergences: list[str]) -> None:
    """
    Compare two ID sets and append divergence lines.

    :param label: Collection label.
    :type label: str
    :param left: First ID set.
    :type left: set[str]
    :param right: Second ID set.
    :type right: set[str]
    :param divergences: Output divergence buffer.
    :type divergences: list[str]
    :return: Nothing.
    :rtype: None
    """
    if left == right:
        pass
    else:
        missing: list[str] = sorted(left - right)
        added: list[str] = sorted(right - left)
        divergences.append(f"{label}: original={len(left)} roundtrip={len(right)}")
        if len(missing) > 0:
            divergences.append(f"{label}: missing={missing[:25]}")
        else:
            pass
        if len(added) > 0:
            divergences.append(f"{label}: added={added[:25]}")
        else:
            pass


def get_contingency_signatures(grid: object) -> set[str]:
    """
    Build contingency signatures ``group|contingency|device``.

    :param grid: VeraGrid model.
    :type grid: object
    :return: Signature set.
    :rtype: set[str]
    """
    signatures: set[str] = set()
    contingency_obj: object
    for contingency_obj in grid.contingencies:
        group_obj: object = contingency_obj.group
        device_obj: object = contingency_obj.device
        group_id: str = ""
        device_id: str = ""
        if group_obj is not None:
            group_id = str(group_obj.idtag)
        else:
            pass
        if device_obj is not None:
            device_id = str(device_obj.idtag).lower()
        else:
            pass
        contingency_id: str = str(contingency_obj.idtag).lower()
        signatures.add(f"{group_id}|{contingency_id}|{device_id}")
    return signatures


def get_roundtrip_divergences(original_grid: object, roundtrip_grid: object) -> list[str]:
    """
    Compute roundtrip divergence lines from VeraGrid object collections.

    :param original_grid: Grid from first import.
    :type original_grid: object
    :param roundtrip_grid: Grid after export and re-import.
    :type roundtrip_grid: object
    :return: Divergence lines.
    :rtype: list[str]
    """
    divergences: list[str] = list()

    original_bus_ids: set[str] = collect_normalized_ids(original_grid.buses)
    roundtrip_bus_ids: set[str] = collect_normalized_ids(roundtrip_grid.buses)
    compare_id_sets("buses", original_bus_ids, roundtrip_bus_ids, divergences)

    original_branch_ids: set[str] = collect_normalized_ids(
        original_grid.get_branches(add_vsc=True, add_hvdc=True, add_switch=True)
    )
    roundtrip_branch_ids: set[str] = collect_normalized_ids(
        roundtrip_grid.get_branches(add_vsc=True, add_hvdc=True, add_switch=True)
    )
    compare_id_sets("branches", original_branch_ids, roundtrip_branch_ids, divergences)

    original_inj_ids: set[str] = collect_normalized_ids(original_grid.get_injection_devices())
    roundtrip_inj_ids: set[str] = collect_normalized_ids(roundtrip_grid.get_injection_devices())
    compare_id_sets("injections", original_inj_ids, roundtrip_inj_ids, divergences)

    original_cont: set[str] = get_contingency_signatures(original_grid)
    roundtrip_cont: set[str] = get_contingency_signatures(roundtrip_grid)
    compare_id_sets("contingencies", original_cont, roundtrip_cont, divergences)

    return divergences


def run_case(case_name: str,
             case_files: list[str],
             boundary_zip_path: str,
             out_dir: Path) -> tuple[bool, list[str]]:
    """
    Execute one roundtrip case and return success plus divergence text.

    :param case_name: Case name.
    :type case_name: str
    :param case_files: Input CGMES files.
    :type case_files: list[str]
    :param boundary_zip_path: Boundary ZIP path.
    :type boundary_zip_path: str
    :param out_dir: Export output directory.
    :type out_dir: Path
    :return: Success flag and divergence lines.
    :rtype: tuple[bool, list[str]]
    """
    original_grid: object = load_cgmes_to_veragrid(case_files)
    export_path: str = str(out_dir / f"{case_name.replace(' ', '_')}_roundtrip_v3.zip")
    save_options: FileSavingOptions = create_save_options(boundary_zip_path)
    save_handler: FileSave = FileSave(circuit=original_grid, file_name=export_path, options=save_options)
    save_handler.save()

    if os.path.isfile(export_path):
        roundtrip_grid: object = load_cgmes_to_veragrid([export_path, boundary_zip_path])
        divergences: list[str] = get_roundtrip_divergences(original_grid, roundtrip_grid)
        if len(divergences) == 0:
            return True, list()
        else:
            return False, divergences
    else:
        raise RuntimeError(f"Exported CGMES ZIP not found: {export_path}")


def parse_args() -> argparse.Namespace:
    """
    Parse script arguments.

    :return: Parsed args.
    :rtype: argparse.Namespace
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Run Relicap CGMES v3 roundtrip and compare VeraGrid objects."
    )
    parser.add_argument(
        "--cases",
        nargs="*",
        default=list(["Belgovia", "Svedala", "Espheim + DC-Espheim-Svedala"]),
        help="Case names from SUBFOLDERS. Default runs 3 representative cases.",
    )
    parser.add_argument(
        "--out-dir",
        default="trunk/cgmes/test_outputs/roundtrip",
        help="Output directory for exported roundtrip ZIP files.",
    )
    return parser.parse_args()


def main() -> int:
    """
    Script entry point.

    :return: Process exit code.
    :rtype: int
    """
    args: argparse.Namespace = parse_args()
    selected_cases: list[str] = list(args.cases)
    out_dir: Path = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    temp_dir_path: str = tempfile.mkdtemp(prefix="relicap_roundtrip_")
    temp_dir: Path = Path(temp_dir_path)
    boundary_zip_path: str = create_boundary_zip(base_folder=FOLDER, out_dir=temp_dir)

    failures: int = 0
    case_name: str
    for case_name in selected_cases:
        if case_name in SUBFOLDERS:
            case_files: list[str] = list(SUBFOLDERS[case_name])
        else:
            print(f"[FAIL] Unknown case: {case_name}")
            failures = failures + 1
            continue

        missing_files: list[str] = list()
        file_path: str
        for file_path in case_files:
            if os.path.isfile(file_path):
                pass
            else:
                missing_files.append(file_path)
        if len(missing_files) > 0:
            print(f"[FAIL] {case_name}: missing files ({len(missing_files)})")
            missing_file: str
            for missing_file in missing_files[:10]:
                print(f"  - {missing_file}")
            failures = failures + 1
            continue
        else:
            pass

        print(f"[RUN ] {case_name}")
        try:
            ok, divergences = run_case(case_name, case_files, boundary_zip_path, out_dir)
            if ok:
                print(f"[PASS] {case_name}")
            else:
                print(f"[FAIL] {case_name}: divergences found")
                divergence_line: str
                for divergence_line in divergences:
                    print(f"  - {divergence_line}")
                failures = failures + 1
        except Exception as exc:
            print(f"[FAIL] {case_name}: {exc}")
            failures = failures + 1

    print()
    if failures == 0:
        print("Roundtrip completed with no divergences.")
        return 0
    else:
        print(f"Roundtrip completed with {failures} failing case(s).")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
