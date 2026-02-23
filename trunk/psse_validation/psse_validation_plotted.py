import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import VeraGridEngine as vg

folder = "data"
plots_folder = os.path.join(folder, "plots")
os.makedirs(plots_folder, exist_ok=True)


def wrap_to_pi(x: np.ndarray) -> np.ndarray:
    """Wrap angle differences to [-pi, pi]."""
    return (x + np.pi) % (2 * np.pi) - np.pi


def plot_hist(err: np.ndarray, title: str, xlabel: str, outpath: str, bins: int = 60):
    err = np.asarray(err).ravel()
    err = err[np.isfinite(err)]

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


for name in [
    "ACTIVSg2000.RAW",
    "AU14GenModel.RAW",
    "ieee9.raw",
    "IEEE14bus.raw",
    "IEEE30bus.raw",
    "NETS-NYPS68Bus.raw",
    "IEEE118Busv2.raw",
    "wecc179.raw",
    "case300.raw",
]:
    # ------------------------------------------------------------------------------------------------------------------
    # Load PSSe results from Excel
    # ------------------------------------------------------------------------------------------------------------------
    excel_name = os.path.join(folder, name + ".xlsx")

    excel_ptr = pd.ExcelFile(excel_name)
    psse_bus_df = pd.read_excel(excel_ptr, "bus")

    Vm_psse = psse_bus_df["Vm"].to_numpy()
    Va_psse = psse_bus_df["Va(rad)"].to_numpy()

    # ------------------------------------------------------------------------------------------------------------------
    # VeraGrid
    # ------------------------------------------------------------------------------------------------------------------
    grid_name = os.path.join(folder, name)
    grid = vg.open_file(grid_name)

    options = vg.PowerFlowOptions(tolerance=1e-5, retry_with_other_methods=False)
    results = vg.power_flow(grid, options=options)

    Vm_vg = np.abs(results.voltage)
    Va_vg = np.angle(results.voltage)

    # ------------------------------------------------------------------------------------------------------------------
    # Compare + plot distributions
    # ------------------------------------------------------------------------------------------------------------------
    dVm = Vm_vg - Vm_psse
    dVa = wrap_to_pi(Va_vg - Va_psse)  # wrapping is important when angles cross ±pi

    Vm_ok = np.allclose(Vm_psse, Vm_vg, atol=1e-3)
    Va_ok = np.allclose(Va_psse, Va_vg, atol=1e-3)

    print("*" * 40)
    print(name)
    print("Vm ok", Vm_ok)
    print("Va ok", Va_ok)
    print_stats("dVm (p.u.)", dVm)
    print_stats("dVa (rad)", dVa)

    safe_stem = name.replace(".", "_")
    vm_plot_path = os.path.join(plots_folder, f"{safe_stem}__dVm_hist.png")
    va_plot_path = os.path.join(plots_folder, f"{safe_stem}__dVa_hist.png")

    plot_hist(
        dVm,
        title=f"{name} | Voltage magnitude error distribution",
        xlabel="dVm = Vm_vg - Vm_psse (p.u.)",
        outpath=vm_plot_path,
        bins=60,
    )

    plot_hist(
        dVa,
        title=f"{name} | Voltage angle error distribution (wrapped)",
        xlabel="dVa = wrap(Va_vg - Va_psse) (rad)",
        outpath=va_plot_path,
        bins=60,
    )

print(f"\nSaved plots to: {plots_folder}")