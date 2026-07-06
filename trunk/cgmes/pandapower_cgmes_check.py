from __future__ import annotations

from pathlib import Path
from typing import Dict
import numpy as np
import VeraGridEngine.api as vg

# Compatibility shim for older pandapower versions expecting numpy.Inf
if not hasattr(np, "Inf"):
    np.Inf = np.inf

from pandapower.converter.cim.cim2pp.from_cim import from_cim as pp_from_cim

CGMES_FILES = [
    "19700101T0000Z_.zip",
    # "20250605T1315Z_RT_SmallGridTestConfiguration_.zip",
]


def _zip_paths() -> list[str]:
    base = Path(__file__).resolve().parent
    paths = [base / name for name in CGMES_FILES]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing CGMES fixtures: {missing}")
    return [str(p) for p in paths]



def _pp_counts(pp_net) -> Dict[str, int]:
    return {
        "buses": len(pp_net.bus),
        "ac_lines": len(pp_net.line),
        "transformers_2w": len(pp_net.trafo),
        "transformers_3w": len(pp_net.trafo3w),
        "switches": len(pp_net.switch),
        "loads": len(pp_net.load),
        "generators": len(pp_net.gen) + len(pp_net.sgen),
        "external_grids": len(pp_net.ext_grid),
        "shunts": len(pp_net.shunt),
    }


def _vg_counts(vg_grid) -> Dict[str, int]:
    return {
        "buses": len(vg_grid.buses),
        "ac_lines": len(vg_grid.lines),
        "transformers_2w": len(vg_grid.transformers2w),
        "transformers_3w": len(vg_grid.transformers3w),
        "switches": len(vg_grid.switch_devices),
        "loads": len(vg_grid.loads),
        "generators": len(vg_grid.generators),
        "external_grids": len(vg_grid.external_grids),
        "shunts": len(vg_grid.shunts) + len(vg_grid.controllable_shunts),
    }


def check_parsers_can_load() -> tuple[object, object]:
    paths = _zip_paths()

    pp_net = pp_from_cim(file_list=paths, cgmes_version="2.4.15")
    vg_grid = vg.open_cgmes(filenames=paths,
                            cgmes_version=vg.CGMESVersions.v2_4_15)

    if pp_net is None:
        raise RuntimeError("pandapower returned None while importing CGMES")
    if vg_grid is None:
        raise RuntimeError("VeraGrid returned None while importing CGMES")

    return pp_net, vg_grid


def compare_counts(pp_net, vg_grid) -> list[tuple[str, int, int]]:
    pp_counts = _pp_counts(pp_net=pp_net)
    vg_counts = _vg_counts(vg_grid=vg_grid)

    mismatches = []
    for key, pp_count in pp_counts.items():
        vg_count = vg_counts[key]
        if vg_count != pp_count:
            mismatches.append((key, vg_count, pp_count))

    return mismatches


def main() -> int:
    print("CGMES parser parity check (pandapower vs VeraGrid)")
    print(f"Using files: {', '.join(CGMES_FILES)}")

    try:
        pp_net, vg_grid = check_parsers_can_load()
    except Exception as exc:
        print(f"[ERROR] Import step failed: {exc}")
        return 2

    print("[OK] Both parsers loaded the CGMES package pair.")
    pp_counts = _pp_counts(pp_net=pp_net)
    vg_counts = _vg_counts(vg_grid=vg_grid)

    print("\nCounts:")
    for key in pp_counts:
        print(f" - {key}: VeraGrid={vg_counts[key]} | pandapower={pp_counts[key]}")

    mismatches = compare_counts(pp_net=pp_net, vg_grid=vg_grid)
    if mismatches:
        print("\n[FAIL] Differences found:")
        for name, vg_value, pp_value in mismatches:
            print(f" - {name}: VeraGrid={vg_value}, pandapower={pp_value}")
        return 1

    print("\n[PASS] No differences found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
