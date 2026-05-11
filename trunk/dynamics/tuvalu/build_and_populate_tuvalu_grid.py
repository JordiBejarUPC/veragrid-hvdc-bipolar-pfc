import argparse
import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd

this_file = Path(__file__).resolve()
repo_root = this_file.parents[3]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import VeraGridEngine as vg
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.esd1_rms_template import get_esd1_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.pvd1_rms_template import get_pvd1_dc_mppt_rms_template
from VeraGridEngine.Templates.Rms.transformer_rms_template_legacy import initialize_trafo_rms
from VeraGridEngine.Templates.Rms.transformer_rms_template import get_transformer2w_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model


def interpolate_below(x: np.ndarray, threshold: float) -> np.ndarray:
    mask_valid = x >= threshold
    x_interp = x.copy()

    if not np.any(mask_valid):
        return np.full_like(x_interp, threshold, dtype=float)

    if np.any(~mask_valid):
        x_interp[~mask_valid] = np.interp(
            np.flatnonzero(~mask_valid),
            np.flatnonzero(mask_valid),
            x[mask_valid],
        )

    return x_interp


def run_snapshot_power_flow(grid: vg.MultiCircuit, label: str) -> bool:
    print(f"\n--- Running snapshot power flow ({label}) ---")
    pf_options = vg.PowerFlowOptions(solver_type=vg.SolverType.HELM)
    pf_driver = vg.PowerFlowDriver(grid=grid, options=pf_options)
    pf_driver.run()
    converged = bool(pf_driver.results.converged)
    print(f"Snapshot power flow converged: {converged}")
    return converged


def run_short_timeseries_power_flow(grid: vg.MultiCircuit, hours: int) -> bool:
    n_steps = int(grid.get_time_number())
    n_check = min(int(hours), n_steps)
    print(f"\n--- Running time-series power flow check (first {n_check} h) ---")

    if n_check <= 0:
        print("Time-series power flow check skipped (no time steps available).")
        return True

    pf_options = vg.PowerFlowOptions(solver_type=vg.SolverType.HELM)
    ts_driver = vg.PowerFlowTimeSeriesDriver(
        grid=grid,
        options=pf_options,
        time_indices=np.arange(n_check),
    )
    ts_driver.run()

    converged_values = np.asarray(ts_driver.results.converged_values, dtype=bool)
    converged = bool(converged_values.all())
    print(f"Time-series power flow converged for all checked steps: {converged}")
    return converged


def get_technology_names(device) -> list[str]:
    names: list[str] = []
    if hasattr(device, "technologies"):
        for assoc in device.technologies:
            if assoc.api_object is not None:
                names.append(str(assoc.api_object.name))
    return names


def collect_event_var_names(block) -> list[str]:
    names = [var.name for var in block.event_dict.keys()]
    for mdl in block.children:
        names.extend(collect_event_var_names(mdl))
    return names


def has_irradiance_event_var(block) -> bool:
    for var in block.event_dict.keys():
        if var.name.lower() in {"g", "irradiance"}:
            return True
    for mdl in block.children:
        if has_irradiance_event_var(mdl):
            return True
    return False


def initialize_tuvalu_rms_models(grid: vg.MultiCircuit) -> None:
    print("\n--- Populating RMS models for Tuvalu grid ---")

    vf = grid.var_factory

    for bus in grid.buses:
        initialize_bus_rms(bus=bus, vf=vf)

    branch_models = grid.get_lines_number()
    for line in grid.get_lines():
        line_model = get_line_rms_template(vfactory=vf, name=f"Line_{line.name}").block
        set_rms_model(device=line, model=line_model, var_factory=vf)

    transformer_models = grid.get_transformers2w_number()
    for trafo in grid.get_transformers2w():
        # initialize_trafo_rms(trafo=trafo, vf=vf, Sbase=grid.Sbase)
        trafo_model = get_transformer2w_rms(vf).block
        set_rms_model(device=trafo, model=trafo_model, var_factory=vf)

    diesel_models = 0
    pv_models = 0
    pv_irradiance_ready = 0
    for gen in grid.get_generators():
        tech_names = [name.lower() for name in get_technology_names(gen)]
        if any("pv" in name for name in tech_names):
            gen_model = get_pvd1_dc_mppt_rms_template(vfactory=vf, name=f"PVD1_{gen.name}").block
            pv_models += 1
        else:
            gen_model = get_complete_generator_template_rms(vfactory=vf, name=f"GENQEC_{gen.name}").block
            diesel_models += 1

        set_rms_model(device=gen, model=gen_model, var_factory=vf)
        if any("pv" in name for name in tech_names):
            if has_irradiance_event_var(gen.rms_model):
                pv_irradiance_ready += 1
            else:
                event_names = collect_event_var_names(gen.rms_model)
                preview = ", ".join(event_names[:10]) if event_names else "<none>"
                raise RuntimeError(
                    f"PV generator '{gen.name}' RMS model has no irradiance event variable. "
                    f"Found event vars: {preview}"
                )

    battery_models = grid.get_batteries_number()
    for batt in grid.get_batteries():
        batt_model = get_esd1_rms_template(vfactory=vf, name=f"ESD1_{batt.name}").block
        set_rms_model(device=batt, model=batt_model, var_factory=vf)

    for load in grid.get_loads():
        load_model = get_load_rms_template(vfactory=vf, name=f"Load_{load.name}").block
        set_rms_model(device=load, model=load_model, var_factory=vf)

    print(
        "RMS models connected: "
        f"buses={len(grid.buses)}, "
        f"lines={branch_models}, "
        f"transformers={transformer_models}, "
        f"diesel(genqec)={diesel_models}, "
        f"pv(pvd1_dc_mppt)={pv_models}, "
        f"pv_irradiance_ready={pv_irradiance_ready}, "
        f"batteries(esd1)={battery_models}"
    )


class TuvaluGridPopulator:
    def __init__(
        self,
        grid: vg.MultiCircuit,
        profiles_and_scenarios_excel: Path,
        demand_excel: Path,
        start_year: int = 2024,
        profile_steps: int = 1,
    ):
        self.grid = grid
        self.profiles_and_scenarios_excel = Path(profiles_and_scenarios_excel)
        self.demand_excel = Path(demand_excel)
        self.share_types = [
            "House with AC",
            "House without AC",
            "Shop",
            "Industry",
            "Hotel",
            "Office",
            "School",
        ]

        self.grid.delete_profiles()
        self.grid.create_profiles(
            steps=profile_steps,
            step_unit="h",
            step_length=1,
            time_base=datetime.datetime(start_year, 1, 1),
        )

        excel_ptr = pd.ExcelFile(self.profiles_and_scenarios_excel)
        self.shares_per_feeder_df = pd.read_excel(excel_ptr, sheet_name="Shares_per_feeder").fillna(0)
        self.pv_profiles_df = pd.read_excel(excel_ptr, sheet_name="PV profiles")
        self.typical_profile_df = pd.read_excel(excel_ptr, sheet_name="Typical_profiles")

        self.pu_pv_gen = self.pv_profiles_df["electricity (p.u.)"].values

        self.nt = self.grid.get_time_number()
        self.nl = self.grid.get_loads_number()
        self.bottom_up_loads = np.zeros((self.nt, self.nl))
        self.total_pv = np.zeros(self.nt)
        self.total_diesel = np.zeros(self.nt)

    def _fit_to_nt(self, arr: np.ndarray) -> np.ndarray:
        arr = np.asarray(arr, dtype=float)
        n = arr.shape[0]

        if n == self.nt:
            return arr
        if n > self.nt:
            return arr[: self.nt]

        reps = int(np.ceil(self.nt / n))
        return np.tile(arr, reps)[: self.nt]

    def add_diesel_profiles(self) -> None:
        diesel_df = pd.read_excel(self.demand_excel)
        diesel_df = diesel_df[["Gen1 (kWh)", "Gen2 (kWh)", "Gen3 (kWh)"]]

        idx = 0
        self.total_diesel = np.zeros(self.nt)
        for gen in self.grid.generators:
            if "diesel" in gen.tech_list[0].name.lower():
                p = self._fit_to_nt(diesel_df.values[:, idx] / 1000.0)
                gen.P_prof = p
                self.total_diesel += p
                idx += 1

    def add_solar_profiles(self) -> None:
        self.total_pv = np.zeros(self.nt)
        for gen in self.grid.generators:
            if "pv" in gen.tech_list[0].name.lower():
                p = self._fit_to_nt(self.pu_pv_gen * gen.Pmax)
                gen.P_prof = p
                self.total_pv += p * gen.active

    def add_bottom_up_demand(self) -> None:
        typical_profile_df2 = self.typical_profile_df[self.share_types]

        for i, load in enumerate(self.grid.loads):
            row = self.shares_per_feeder_df[
                self.shares_per_feeder_df["Load_idtag"] == load.idtag
            ][self.share_types]

            unscaled_p = np.zeros(typical_profile_df2.shape[0])
            for j in range(typical_profile_df2.shape[1]):
                if row.values[0, j] != 0.0:
                    unscaled_p += typical_profile_df2.values[:, j] * row.values[0, j]

            scaled_p = unscaled_p / np.max(unscaled_p)
            day_profile = scaled_p * load.contract_power
            p = self._fit_to_nt(day_profile)

            load.P_prof = p
            if abs(load.P) > 1e-12:
                load.Q_prof = p * load.Q / load.P

            self.bottom_up_loads[:, i] = p

    def calibrate_demand(self) -> None:
        top_down_demand = self.total_diesel + self.total_pv
        top_down_demand = interpolate_below(top_down_demand, 0.5)

        scale = self.bottom_up_loads.sum(axis=1) / (top_down_demand + 1e-20)
        for i, load in enumerate(self.grid.loads):
            load.P_prof = self.bottom_up_loads[:, i] / scale

    def populate(self) -> None:
        self.add_diesel_profiles()
        self.add_solar_profiles()
        self.add_bottom_up_demand()
        self.calibrate_demand()


def parse_args() -> argparse.Namespace:
    eroots_root = repo_root.parent

    parser = argparse.ArgumentParser(
        description="Build Tuvalu base grid, verify PF, then populate time-series profiles."
    )
    parser.add_argument(
        "--base-grid",
        type=Path,
        default=repo_root / "trunk" / "tuvalu" / "funafuti_base.veragrid",
        help="Path to the Tuvalu base .veragrid file",
    )
    parser.add_argument(
        "--profiles-excel",
        type=Path,
        default=eroots_root / "Tuvalu" / "data" / "profiles_and_scenarios.xlsx",
        help="Path to profiles_and_scenarios.xlsx",
    )
    parser.add_argument(
        "--demand-excel",
        type=Path,
        default=eroots_root / "Tuvalu" / "data" / "plant_data" / "combined_output_hand_corrected.xlsx",
        help="Path to diesel production Excel file",
    )
    parser.add_argument(
        "--output-grid",
        type=Path,
        default=repo_root / "trunk" / "dynamics" / "tuvalu" / "funafuti_ts_base.veragrid",
        help="Output .veragrid path after profile population",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2024,
        help="Time-series start year",
    )
    parser.add_argument(
        "--profile-steps",
        type=int,
        default=1,
        help="Number of profile steps to create (default: 1)",
    )
    parser.add_argument(
        "--pf-hours-check",
        type=int,
        default=1,
        help="Number of initial time steps checked with time-series power flow",
    )
    parser.add_argument(
        "--skip-rms-models",
        action="store_true",
        help="Skip RMS model population step",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print(f"Loading base Tuvalu grid: {args.base_grid}")
    grid = vg.open_file(str(args.base_grid))

    if not run_snapshot_power_flow(grid, "base grid"):
        print("Base grid power flow did not converge. Stopping.")
        return 1

    populator = TuvaluGridPopulator(
        grid=grid,
        profiles_and_scenarios_excel=args.profiles_excel,
        demand_excel=args.demand_excel,
        start_year=args.start_year,
        profile_steps=args.profile_steps,
    )

    print("\nPopulating Tuvalu time-series profiles...")
    populator.populate()

    if not args.skip_rms_models:
        initialize_tuvalu_rms_models(grid)

    if args.pf_hours_check > 0:
        if not run_short_timeseries_power_flow(grid, args.pf_hours_check):
            print("Time-series power flow check failed after population.")
            return 2

    print("\nSkipping grid save.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
