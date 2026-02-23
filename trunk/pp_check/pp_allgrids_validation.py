import os
import numpy as np
import matplotlib.pyplot as plt

import pandas as pd
import pandapower as pp
from pandapower.networks import power_system_test_cases as tc
from pandapower.powerflow import LoadflowNotConverged

import VeraGridEngine as vg
from VeraGridEngine.enumerations import BranchImpedanceMode, SolverType

folder = "data"
plots_folder = os.path.join(folder, "plots_pp_to_vg")
os.makedirs(plots_folder, exist_ok=True)


def wrap_to_pi(x: np.ndarray) -> np.ndarray:
    return (x + np.pi) % (2 * np.pi) - np.pi


def plot_hist(err: np.ndarray, title: str, xlabel: str, outpath: str, bins: int = 60):
    err = np.asarray(err).ravel()
    err = err[np.isfinite(err)]
    if err.size == 0:
        return

    fig = plt.figure(figsize=(8, 4.5))
    plt.hist(err, bins=bins)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Count")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(outpath, dpi=160)
    plt.close(fig)


def print_stats(label: str, err: np.ndarray):
    err = np.asarray(err).ravel()
    err = err[np.isfinite(err)]
    if err.size == 0:
        print(f"  {label}: no finite samples")
        return

    abs_err = np.abs(err)
    p50 = np.percentile(abs_err, 50)
    p95 = np.percentile(abs_err, 95)
    p99 = np.percentile(abs_err, 99)

    print(
        f"  {label}: max|e|={abs_err.max():.6g}, "
        f"p50|e|={p50:.6g}, p95|e|={p95:.6g}, p99|e|={p99:.6g}"
    )


def run_pandapower_pf(net: "pp.pandapowerNet", max_iter: int = 30):
    """
    Reference PF in pandapower.
    Many large cases need >10 iterations, so increase max_iteration.
    """
    pp.runpp(
        net,
        algorithm="nr",
        init="flat",
        calculate_voltage_angles=True,
        trafo_model="t",
        max_iteration=max_iter,
    )
    Vm = net.res_bus.vm_pu.to_numpy()
    Va = np.deg2rad(net.res_bus.va_degree.to_numpy())
    return Vm, Va


def _fill_if_exists(df: pd.DataFrame, col: str, value):
    if df is None or len(df) == 0 or col not in df.columns:
        return
    if df[col].isna().any():
        df[col] = df[col].fillna(value)


def sanitize_for_veragrid(net: "pp.pandapowerNet"):
    """
    Workaround for VeraGrid pandapower importer:
    pandapower uses NaN in several integer-like columns (tap/parallel, etc.).
    VeraGrid importer likely casts them to int -> ValueError on NaN.

    This sanitizes the most common columns while keeping semantics reasonable.
    """

    # Integer-like columns where NaN means "not set"
    # tap_pos: if no OLTC, should be 0
    # parallel: default 1
    if hasattr(net, "trafo"):
        _fill_if_exists(net.trafo, "tap_pos", 0)
        _fill_if_exists(net.trafo, "tap_neutral", 0)
        _fill_if_exists(net.trafo, "tap_min", 0)
        _fill_if_exists(net.trafo, "tap_max", 0)
        _fill_if_exists(net.trafo, "parallel", 1)

    if hasattr(net, "trafo3w"):
        _fill_if_exists(net.trafo3w, "tap_pos", 0)
        _fill_if_exists(net.trafo3w, "tap_neutral", 0)
        _fill_if_exists(net.trafo3w, "tap_min", 0)
        _fill_if_exists(net.trafo3w, "tap_max", 0)
        _fill_if_exists(net.trafo3w, "parallel", 1)

    if hasattr(net, "line"):
        _fill_if_exists(net.line, "parallel", 1)

    # These should never be NaN. If they are, fail early with a readable error.
    bus_ref_specs = [
        ("line", ["from_bus", "to_bus"]),
        ("trafo", ["hv_bus", "lv_bus"]),
        ("trafo3w", ["hv_bus", "mv_bus", "lv_bus"]),
        ("switch", ["bus", "element"]),
        ("load", ["bus"]),
        ("gen", ["bus"]),
        ("sgen", ["bus"]),
        ("ext_grid", ["bus"]),
        ("shunt", ["bus"]),
        ("ward", ["bus"]),
        ("xward", ["bus"]),
    ]
    for table, cols in bus_ref_specs:
        if not hasattr(net, table):
            continue
        df = getattr(net, table)
        if df is None or len(df) == 0:
            continue
        for c in cols:
            if c in df.columns and df[c].isna().any():
                bad = df.index[df[c].isna()].tolist()[:10]
                raise ValueError(f"pandapower net has NaN in {table}.{c} at rows {bad}")

    return net


# ----------------------------------------------------------------------
# All cases listed in your message
# ----------------------------------------------------------------------
PANDAPOWER_CASES = [
    ("case4gs", tc.case4gs, {}),
    ("case5", tc.case5, {}),
    ("case6ww", tc.case6ww, {}),
    ("case9", tc.case9, {}),
    ("case14", tc.case14, {}),
    ("case24_ieee_rts", tc.case24_ieee_rts, {}),
    ("case30", tc.case30, {}),
    ("case_ieee30", tc.case_ieee30, {}),
    ("case33bw", tc.case33bw, {}),
    ("case39", tc.case39, {}),
    ("case57", tc.case57, {}),
    ("case89pegase", tc.case89pegase, {}),
    ("case118", tc.case118, {}),
    ("case145", tc.case145, {}),
    ("case_illinois200", tc.case_illinois200, {}),
    ("case300", tc.case300, {}),
    ("case1354pegase", tc.case1354pegase, {}),
    ("case1888rte", tc.case1888rte, {}),
    ("case2848rte", tc.case2848rte, {}),
    ("case2869pegase", tc.case2869pegase, {}),
    ("case3120sp", tc.case3120sp, {}),
    ("case6470rte", tc.case6470rte, {}),
    ("case6495rte", tc.case6495rte, {}),
    ("case6515rte", tc.case6515rte, {}),
    ("case9241pegase", tc.case9241pegase, {}),
    ("GBnetwork", tc.GBnetwork, {}),
    ("GBreducednetwork", tc.GBreducednetwork, {}),
    ("iceland", tc.iceland, {}),
]

for case_name, case_fn, case_kwargs in PANDAPOWER_CASES:
    print("*" * 60)
    print(case_name)

    # ----------------------------------------------------------------------
    # 1) Build pandapower net + sanitize + run PF (reference)
    # ----------------------------------------------------------------------
    try:
        pp_net = case_fn(**case_kwargs)
        pp_net = sanitize_for_veragrid(pp_net)

        try:
            Vm_pp, Va_pp = run_pandapower_pf(pp_net, max_iter=30)
        except LoadflowNotConverged as e:
            # Some big cases need a better init than flat
            print("Pandapower NR did not converge with flat init, retrying with 'auto':", repr(e))
            Vm_pp, Va_pp = run_pandapower_pf(pp_net, max_iter=50)  # keep same init call below? handled in run
            # If you want a true init switch, do it explicitly:
            # pp.runpp(pp_net, algorithm="nr", init="auto", calculate_voltage_angles=True, trafo_model="t", max_iteration=50)
            # Vm_pp, Va_pp = pp_net.res_bus.vm_pu.to_numpy(), np.deg2rad(pp_net.res_bus.va_degree.to_numpy())

    except Exception as e:
        print("Pandapower build/runpp failed:", repr(e))
        continue

    # ----------------------------------------------------------------------
    # 2) Save pandapower net to .p (always overwrite)
    # ----------------------------------------------------------------------
    pp_path = os.path.join(folder, f"{case_name}.p")
    try:
        pp.to_pickle(pp_net, pp_path)
        print("Pandapower pickle overwritten:", pp_path)
    except Exception as e:
        print("Saving pandapower pickle failed:", repr(e))
        continue

    # ----------------------------------------------------------------------
    # 3) Load in VeraGrid and run PF (skip if it fails)
    # ----------------------------------------------------------------------
    try:
        grid = vg.open_file(pp_path)
    except Exception as e:
        print("VeraGrid import failed, skipping:", repr(e))
        continue

    try:
        options = vg.PowerFlowOptions(tolerance=1e-5, solver_type=SolverType.NR, retry_with_other_methods=False)
        results = vg.power_flow(grid, options=options)
        Vm_vg = np.abs(results.voltage)
        Va_vg = np.angle(results.voltage)
    except Exception as e:
        print("VeraGrid power flow failed, skipping:", repr(e))
        continue

    # ----------------------------------------------------------------------
    # 4) Compare + plot
    # ----------------------------------------------------------------------
    if len(Vm_pp) != len(Vm_vg):
        print(
            f"Bus count mismatch, skipping: pandapower={len(Vm_pp)} vs veragrid={len(Vm_vg)}"
        )
        continue

    dVm = Vm_vg - Vm_pp
    dVa = wrap_to_pi(Va_vg - Va_pp)

    Vm_ok = np.allclose(Vm_pp, Vm_vg, atol=1e-3)
    Va_ok = np.allclose(Va_pp, Va_vg, atol=1e-3)

    print("Vm ok", Vm_ok)
    print("Va ok", Va_ok)
    print_stats("dVm (p.u.)", dVm)
    print_stats("dVa (rad)", dVa)

    plot_hist(
        dVm,
        title=f"{case_name} | Vm error (VeraGrid - pandapower)",
        xlabel="dVm = Vm_vg - Vm_pp (p.u.)",
        outpath=os.path.join(plots_folder, f"{case_name}__dVm_hist.png"),
        bins=60,
    )

    plot_hist(
        dVa,
        title=f"{case_name} | Va error wrapped (VeraGrid - pandapower)",
        xlabel="dVa = wrap(Va_vg - Va_pp) (rad)",
        outpath=os.path.join(plots_folder, f"{case_name}__dVa_hist.png"),
        bins=60,
    )

print(f"\nSaved plots to: {plots_folder}")