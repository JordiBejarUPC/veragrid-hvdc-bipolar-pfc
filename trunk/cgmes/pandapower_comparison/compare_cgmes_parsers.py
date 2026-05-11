from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import zipfile

import pandapower as pp
import pypowsybl as ppb
import VeraGridEngine.api as vg
from pandapower.converter.cim.cim2pp.from_cim import from_cim as pp_from_cim
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesRecoveryMode
from VeraGridEngine.IO.file_open import FileOpen, FileOpenOptions, FileType
from VeraGridEngine.Simulations import PowerFlowOptions
from VeraGridEngine.enumerations import CgmesTopologyMode, SolverType


COUNT_KEYS = (
    "buses",
    "ac_lines",
    "dangling_lines",
    "transformers_2w",
    "transformers_3w",
    "switches",
    "loads",
    "generators",
    "external_grids",
    "shunts",
    "measurements",
)


@dataclass
class ParsedNetworks:
    pp_net: object
    vg_grid: object
    pyp_net: object


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    default_zip = sorted(here.glob("*.zip"))

    parser = argparse.ArgumentParser(
        description="Compare CGMES parsing across pandapower, VeraGrid, and pypowsybl."
    )
    parser.add_argument(
        "--zip",
        dest="zip_path",
        type=Path,
        default=default_zip[0] if default_zip else None,
        help="Path to CGMES zip file (default: first *.zip in this folder).",
    )
    parser.add_argument(
        "--cgmes-version",
        choices=("auto", "2.4.15", "3.0.0"),
        default="auto",
        help="CGMES version for VeraGrid import.",
    )
    parser.add_argument(
        "--max-show",
        type=int,
        default=15,
        help="Max IDs shown in difference samples.",
    )
    parser.add_argument(
        "--skip-powerflow",
        action="store_true",
        help="Skip pandapower and pypowsybl load-flow checks.",
    )
    return parser.parse_args()


def detect_cgmes_version(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        names = [n.lower() for n in zf.namelist()]
    return "3.0.0" if any("_300" in n for n in names) else "2.4.15"


def normalize_id(value: object) -> str:
    if value is None:
        return ""
    txt = str(value).strip()
    if not txt:
        return ""
    return txt.replace("-", "").replace("_", "").lower()


def parse_networks(zip_path: Path, cgmes_version: str) -> ParsedNetworks:
    vg_version = vg.CGMESVersions.v3_0_0 if cgmes_version == "3.0.0" else vg.CGMESVersions.v2_4_15

    pp_net = pp_from_cim(file_list=[str(zip_path)])
    vg_open_options = FileOpenOptions(
        file_type=FileType.CGMES,
        cgmes_version=vg_version,
        cgmes_topology_mode=CgmesTopologyMode.ConnectivityNode,
        cgmes_try_to_map_dc_to_hvdc_line=True,
        cgmes_map_areas_like_raw=True,
        psse_adjust_taps_to_discrete_positions=True,
        cgmes_recovery_mode=CgmesRecoveryMode.Recover,
    )
    vg_grid = FileOpen(file_name=[str(zip_path)], options=vg_open_options).open()
    pyp_net = ppb.network.load(str(zip_path))

    if pp_net is None:
        raise RuntimeError("pandapower returned None.")
    if vg_grid is None:
        raise RuntimeError("VeraGrid returned None.")
    if pyp_net is None:
        raise RuntimeError("pypowsybl returned None.")

    return ParsedNetworks(pp_net=pp_net, vg_grid=vg_grid, pyp_net=pyp_net)


def counts_pandapower(pp_net) -> dict[str, int | None]:
    return {
        "buses": len(pp_net.bus),
        "ac_lines": len(pp_net.line),
        "dangling_lines": None,
        "transformers_2w": len(pp_net.trafo),
        "transformers_3w": len(pp_net.trafo3w),
        "switches": len(pp_net.switch),
        "loads": len(pp_net.load),
        "generators": len(pp_net.gen) + len(pp_net.sgen),
        "external_grids": len(pp_net.ext_grid),
        "shunts": len(pp_net.shunt),
        "measurements": len(pp_net.measurement) if "measurement" in pp_net else 0,
    }


def counts_veragrid(vg_grid) -> dict[str, int | None]:
    vg_measurements = (
        len(vg_grid.pi_measurements)
        + len(vg_grid.qi_measurements)
        + len(vg_grid.vm_measurements)
        + len(vg_grid.pf_measurements)
        + len(vg_grid.qf_measurements)
        + len(vg_grid.if_measurements)
    )
    return {
        "buses": len(vg_grid.buses),
        "ac_lines": len(vg_grid.lines),
        "dangling_lines": None,
        "transformers_2w": len(vg_grid.transformers2w),
        "transformers_3w": len(vg_grid.transformers3w),
        "switches": len(vg_grid.switch_devices),
        "loads": len(vg_grid.loads),
        "generators": len(vg_grid.generators) + len(vg_grid.static_generators),
        "external_grids": len(vg_grid.external_grids),
        "shunts": len(vg_grid.shunts) + len(vg_grid.controllable_shunts),
        "measurements": vg_measurements,
    }


def counts_pypowsybl(pyp_net) -> dict[str, int | None]:
    return {
        "buses": None,  # pypowsybl buses are topological buses, not directly comparable here
        "ac_lines": len(pyp_net.get_lines()),
        "dangling_lines": len(pyp_net.get_dangling_lines()),
        "transformers_2w": len(pyp_net.get_2_windings_transformers()),
        "transformers_3w": len(pyp_net.get_3_windings_transformers()),
        "switches": len(pyp_net.get_switches()),
        "loads": len(pyp_net.get_loads()),
        "generators": len(pyp_net.get_generators()),
        "external_grids": None,
        "shunts": len(pyp_net.get_shunt_compensators()),
        "measurements": None,
    }


def get_column_id_set(df, candidate_cols: Iterable[str]) -> set[str]:
    for col in candidate_cols:
        if col in df.columns:
            return {normalize_id(v) for v in df[col].tolist() if normalize_id(v)}
    return set()


def get_vg_id_set(items: Iterable[object]) -> set[str]:
    out: set[str] = set()
    for item in items:
        raw = getattr(item, "rdfid", None) or getattr(item, "idtag", None)
        v = normalize_id(raw)
        if v:
            out.add(v)
    return out


def compare_line_ids(pp_net, vg_grid, pyp_net) -> tuple[set[str], set[str], set[str]]:
    pp_lines = get_column_id_set(pp_net.line, ("uuid", "rdfid", "cim_id", "origin_id"))
    vg_lines = get_vg_id_set(vg_grid.lines)
    pyp_lines = {normalize_id(v) for v in pyp_net.get_lines().index.tolist() if normalize_id(v)}
    return pp_lines, vg_lines, pyp_lines


def pyp_dangling_ids(pyp_net) -> set[str]:
    return {normalize_id(v) for v in pyp_net.get_dangling_lines().index.tolist() if normalize_id(v)}


def run_pandapower_flow(pp_net) -> tuple[bool, str]:
    try:
        pp.runpp(pp_net)
        return bool(getattr(pp_net, "converged", False)), "ok"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def run_pypowsybl_flow(pyp_net) -> tuple[bool, str]:
    try:
        res = ppb.loadflow.run_ac(pyp_net)
        first = res[0] if res else None
        if first is None:
            return False, "no component result returned"
        return str(first.status).endswith("CONVERGED"), (
            f"status={first.status}, text={first.status_text}, iterations={first.iteration_count}"
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def run_veragrid_flow(vg_grid) -> tuple[bool, str]:
    pf_options = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=True,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        ignore_single_node_islands=True,
        initialize_angles=True,
    )
    try:
        res = vg.power_flow(vg_grid, options=pf_options)
        return bool(getattr(res, "converged", False)), (
            f"converged={bool(getattr(res, 'converged', False))}, "
            f"error={getattr(res, 'error', 'n/a')}, iterations={getattr(res, 'iterations', 'n/a')}"
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def as_txt(v: int | None) -> str:
    return f"{v:6d}" if isinstance(v, int) else "   n/a"


def main() -> int:
    args = parse_args()
    if args.zip_path is None:
        print("[ERROR] No zip found. Pass --zip /path/to/file.zip")
        return 2
    if not args.zip_path.exists():
        print(f"[ERROR] Zip not found: {args.zip_path}")
        return 2

    cgmes_version = detect_cgmes_version(args.zip_path) if args.cgmes_version == "auto" else args.cgmes_version
    print("CGMES parser comparison: pandapower vs VeraGrid vs pypowsybl")
    print(f"ZIP: {args.zip_path}")
    print(f"CGMES version: {cgmes_version}")

    try:
        parsed = parse_networks(args.zip_path, cgmes_version)
    except Exception as exc:
        print(f"[ERROR] Parse failed: {exc}")
        return 2

    pp_counts = counts_pandapower(parsed.pp_net)
    vg_counts = counts_veragrid(parsed.vg_grid)
    pyp_counts = counts_pypowsybl(parsed.pyp_net)

    print("\nCounts:")
    count_mismatch = 0
    for key in COUNT_KEYS:
        pp_v = pp_counts.get(key)
        vg_v = vg_counts.get(key)
        pyp_v = pyp_counts.get(key)
        comparable = isinstance(pp_v, int) and isinstance(vg_v, int)
        tag = "OK" if comparable and pp_v == vg_v else ("INFO" if not comparable else "DIFF")
        if tag == "DIFF":
            count_mismatch += 1
        print(
            f" - {key:16s} VeraGrid={as_txt(vg_v)} | pandapower={as_txt(pp_v)} | "
            f"pypowsybl={as_txt(pyp_v)} [{tag}]"
        )

    pp_line_ids, vg_line_ids, pyp_line_ids = compare_line_ids(parsed.pp_net, parsed.vg_grid, parsed.pyp_net)
    pyp_dang_ids = pyp_dangling_ids(parsed.pyp_net)

    only_pp_vs_vg = sorted(pp_line_ids - vg_line_ids)
    only_vg_vs_pp = sorted(vg_line_ids - pp_line_ids)
    only_pp_vs_pyp_lines = sorted(pp_line_ids - pyp_line_ids)

    print("\nAC line ID differences (normalized):")
    print(
        f" - pp vs vg: only_pp={len(only_pp_vs_vg)} | only_vg={len(only_vg_vs_pp)} | "
        f"pp={len(pp_line_ids)} vg={len(vg_line_ids)}"
    )
    if only_pp_vs_vg:
        print(f"   only_pp sample ({min(args.max_show, len(only_pp_vs_vg))}): {only_pp_vs_vg[:args.max_show]}")
    if only_vg_vs_pp:
        print(f"   only_vg sample ({min(args.max_show, len(only_vg_vs_pp))}): {only_vg_vs_pp[:args.max_show]}")

    print(
        f" - pp extra line IDs covered by pypowsybl dangling IDs: "
        f"{len(set(only_pp_vs_pyp_lines) & pyp_dang_ids)}/{len(only_pp_vs_pyp_lines)}"
    )

    pf_mismatch = 0
    if not args.skip_powerflow:
        print("\nLoad-flow checks:")
        pp_ok, pp_msg = run_pandapower_flow(parsed.pp_net)
        vg_ok, vg_msg = run_veragrid_flow(parsed.vg_grid)
        pyp_ok, pyp_msg = run_pypowsybl_flow(parsed.pyp_net)
        print(f" - veragrid : {'OK' if vg_ok else 'FAIL'} | {vg_msg}")
        print(f" - pandapower: {'OK' if pp_ok else 'FAIL'} | {pp_msg}")
        print(f" - pypowsybl: {'OK' if pyp_ok else 'FAIL'} | {pyp_msg}")
        if not pp_ok:
            pf_mismatch += 1
        if not vg_ok:
            pf_mismatch += 1

    id_mismatch = 1 if (only_pp_vs_vg or only_vg_vs_pp) else 0
    if count_mismatch == 0 and id_mismatch == 0 and pf_mismatch == 0:
        print("\n[PASS] No differences found.")
        return 0

    print(
        "\n[FAIL] "
        f"Count mismatches={count_mismatch}, ID mismatches={id_mismatch}, PF mismatches={pf_mismatch}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
