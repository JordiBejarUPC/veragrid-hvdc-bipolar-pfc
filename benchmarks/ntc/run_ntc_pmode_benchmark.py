# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
NTC Pmode1 vs Pmode3 benchmark on large time-series grids.

Runs the OptimalNetTransferCapacityTimeSeriesDriver over an identical subset of
time steps for two grids that only differ in the VSC control mode of the FR
converters (P_dc set-point vs P_dc_angle_droop), and reports wall times,
droop-region passes, lazy-contingency rounds and the exchange results.

Example:
    python benchmarks/ntc/run_ntc_pmode_benchmark.py \
        --pmode1 ~/Downloads/6000h_pmode1_vsc_link.veragrid \
        --pmode3 ~/Downloads/6000h_pmode3_vsc_link.veragrid \
        --steps 24
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import List, Dict, Any

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', 'src'))

import VeraGridEngine as gce  # noqa: E402


def summarize_logger(logger: gce.Logger) -> Dict[str, int]:
    """
    Count the NTC-relevant log messages so solve behaviour can be compared
    before / after formulation changes.
    """
    counts = {
        "region_converged_msgs": 0,
        "region_unstable_msgs": 0,
        "lazy_groups_added_msgs": 0,
        "errors": 0,
    }
    for entry in logger.entries:
        text = str(entry.msg)
        sev = str(entry.severity)
        if "Pmode3 region iteration converged" in text:
            counts["region_converged_msgs"] += 1
        elif "Lazy contingency formulation" in text:
            counts["lazy_groups_added_msgs"] += 1
        elif "Pmode3 region iteration did not stabilize" in text:
            counts["region_unstable_msgs"] += 1
        elif sev == "Error":
            counts["errors"] += 1
    return counts


def run_case(grid_path: str,
             steps: int,
             consider_contingencies: bool,
             corrective_contingencies: bool,
             label: str) -> Dict[str, Any]:
    """
    Open the grid and run the NTC time series driver for the first `steps` hours.
    Returns a metrics dictionary.
    """
    t0 = time.time()
    grid = gce.open_file(grid_path)
    t_open = time.time() - t0

    areas = list(grid.get_areas())
    if len(areas) < 2:
        raise RuntimeError(f"{grid_path}: need at least 2 areas for the exchange, found {len(areas)}")

    info = grid.get_inter_aggregation_info(objects_from=[areas[0]], objects_to=[areas[1]])

    n_ctg_groups = len([e for e in grid.get_contingency_groups_active()])

    opf_options = gce.OptimalPowerFlowOptions(
        contingency_groups_used=grid.get_contingency_groups_active())

    options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        skip_generation_limits=True,
        use_branch_exchange_sensitivity=False,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=consider_contingencies,
        corrective_contingencies=corrective_contingencies,
        opf_options=opf_options,
        lin_options=gce.LinearAnalysisOptions())

    time_indices = list(range(min(steps, len(grid.time_profile)))) if grid.time_profile is not None \
        else list(range(steps))

    drv = gce.OptimalNetTransferCapacityTimeSeriesDriver(
        grid=grid,
        options=options,
        time_indices=time_indices)

    t1 = time.time()
    drv.run()
    t_run = time.time() - t1

    res = drv.results
    converged = int(np.sum(res.converged)) if res.converged is not None else 0
    exchange = res.inter_area_flows[:len(time_indices)]

    per_step = np.array(drv.per_step_s) if drv.per_step_s else np.zeros(0)
    slowest_idx = np.argsort(per_step)[::-1][:3] if len(per_step) else []

    out: Dict[str, Any] = {
        "label": label,
        "grid": os.path.basename(grid_path),
        "steps": len(time_indices),
        "open_s": round(t_open, 2),
        "run_s": round(t_run, 2),
        "s_per_step": round(t_run / max(len(time_indices), 1), 3),
        "step_min_s": round(float(np.min(per_step)), 3) if len(per_step) else None,
        "step_med_s": round(float(np.median(per_step)), 3) if len(per_step) else None,
        "step_max_s": round(float(np.max(per_step)), 3) if len(per_step) else None,
        "slowest_steps": {int(i): round(float(per_step[i]), 2) for i in sorted(slowest_idx)},
        "contingency_groups": n_ctg_groups,
        "consider_contingencies": consider_contingencies,
        "corrective_contingencies": corrective_contingencies,
        "converged_steps": f"{converged}/{len(time_indices)}",
        "exchange_min_MW": float(np.min(exchange)),
        "exchange_max_MW": float(np.max(exchange)),
        "exchange_mean_MW": float(np.mean(exchange)),
    }
    out.update(summarize_logger(drv.logger))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pmode1", type=str, required=True, help="Path to the Pmode1 .veragrid file")
    parser.add_argument("--pmode3", type=str, required=True, help="Path to the Pmode3 .veragrid file")
    parser.add_argument("--steps", type=int, default=24, help="Number of time steps to simulate")
    parser.add_argument("--no-contingencies", action="store_true",
                        help="Disable N-1 contingencies (much faster)")
    parser.add_argument("--corrective", action="store_true",
                        help="Enable corrective contingency formulation")
    parser.add_argument("--only", choices=["pmode1", "pmode3"], default=None,
                        help="Run only one of the two cases")
    parser.add_argument("--json-out", type=str, default=None,
                        help="Optional path to save the results as JSON")
    args = parser.parse_args()

    results: List[Dict[str, Any]] = []
    if args.only in (None, "pmode1"):
        results.append(run_case(args.pmode1, args.steps,
                                not args.no_contingencies, args.corrective, "Pmode1"))
    if args.only in (None, "pmode3"):
        results.append(run_case(args.pmode3, args.steps,
                                not args.no_contingencies, args.corrective, "Pmode3"))

    keys = ["label", "grid", "steps", "converged_steps", "open_s", "run_s", "s_per_step",
            "step_min_s", "step_med_s", "step_max_s",
            "region_converged_msgs", "region_unstable_msgs", "lazy_groups_added_msgs",
            "errors", "contingency_groups",
            "exchange_min_MW", "exchange_max_MW", "exchange_mean_MW"]

    hdr = [k.replace("_MW", "").replace("msgs", "") for k in keys]
    widths = [max(len(h), *(len(str(r[k])) for r in results)) for h, k in zip(hdr, keys)]
    line = " | ".join(h.ljust(w) for h, w in zip(hdr, widths))
    print("\n" + line)
    print("-" * len(line))
    for r in results:
        print(" | ".join(str(r[k]).ljust(w) for k, w in zip(keys, widths)))

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved JSON results to {args.json_out}")


if __name__ == "__main__":
    main()
