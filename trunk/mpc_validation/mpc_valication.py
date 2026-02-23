import os
import pandas as pd
import VeraGridEngine as gce

base_dir = os.path.dirname(os.path.abspath(__file__))
folder = os.path.join(base_dir, "data")


def run_grid(fname):
    name = os.path.basename(fname)

    try:
        grid = gce.open_file(fname)
    except Exception as e:
        # keep going, but record the failure
        return {
            "name": name,
            "file": fname,
            "n_buses": None,
            "n_branches": None,
            "P imbalance (%)": None,
            "Flat start": None,
            "converged": False,
            "error (p.u.)": None,
            "iterations": None,
            "time (ms)": None,
            "load_ok": False,
            "exception": repr(e),
        }

    if grid.get_bus_number() <= 0:
        return {
            "name": name,
            "file": fname,
            "n_buses": grid.get_bus_number(),
            "n_branches": grid.get_branch_number(),
            "P imbalance (%)": 0.0,
            "Flat start": True,
            "converged": True,
            "error (p.u.)": 0.0,
            "iterations": 0,
            "time (ms)": 0.0,
            "load_ok": True,
            "exception": "",
        }

    # Solve
    res = gce.power_flow(
        grid=grid,
        options=gce.PowerFlowOptions(
            solver_type=gce.SolverType.NR,
            retry_with_other_methods=False,
            use_stored_guess=False,
        )
    )
    flat_start = True

    if not res.converged:
        res = gce.power_flow(
            grid=grid,
            options=gce.PowerFlowOptions(
                solver_type=gce.SolverType.NR,
                retry_with_other_methods=False,
                use_stored_guess=True,
            )
        )
        flat_start = False

    return {
        "name": name,
        "file": fname,
        "n_buses": grid.get_bus_number(),
        "n_branches": grid.get_branch_number(),
        "P imbalance (%)": grid.get_imbalance() * 100.0,
        "Flat start": flat_start,
        "converged": bool(res.converged),
        "error (p.u.)": float(res.error),
        "iterations": int(res.iterations),
        "time (ms)": float(res.elapsed) * 1000.0,
        "load_ok": True,
        "exception": "",
    }


# Compile JIT routines for fair timing (wrap in try in case case missing)
try:
    gce.power_flow(gce.open_file(os.path.join(folder, "case_ieee30.m")))
except Exception:
    pass

files_list = []
for root, _, files in os.walk(folder):
    for file in files:
        if file.endswith(".m"):
            files_list.append(os.path.join(root, file))

data = []
for f in files_list:
    print(f"Running {os.path.basename(f)}")
    data.append(run_grid(f))

df = pd.DataFrame(data).sort_values(by="n_buses", ascending=False, na_position="last")
df.to_excel("All matpower grids.xlsx", index=False)

# Optional: save failures separately
fail_df = df[df["load_ok"] == False]
if not fail_df.empty:
    fail_df.to_excel("All matpower grids_failures.xlsx", index=False)

print("Finished.")