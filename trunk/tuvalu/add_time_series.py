import os
import datetime
import numpy as np
import pandas as pd
import VeraGridEngine as vg
from matplotlib import pyplot as plt

current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)

# open base excel file
profiles_and_scenarios_ptr = pd.ExcelFile("/home/santi/Documentos/Git/eRoots/Tuvalu/data/profiles_and_scenarios.xlsx")

# open the base grid
grid = vg.open_file("funafuti_base.veragrid")

grid.create_profiles(steps=8760,
                     step_unit="h",
                     step_length=1,
                     time_base=datetime.datetime(2024, 1, 1))

# ----------------------------------------------------------------------------------------------------------------------
# Add Diesel profiles
# ----------------------------------------------------------------------------------------------------------------------
diesel_df = pd.read_excel("/home/santi/Documentos/Git/eRoots/Tuvalu/data/plant_data/combined_output_hand_corrected.xlsx")
diesel_df = diesel_df[["Gen1 (kWh)", "Gen2 (kWh)", "Gen3 (kWh)"]]

i = 0
total_diesel = 0
for gen in grid.generators:
    if "diesel" in gen.tech_list[0].name.lower():
        p = diesel_df.values[:, i] / 1000.0
        gen.P_prof = p
        total_diesel += p
        i += 1

# ----------------------------------------------------------------------------------------------------------------------
# compose Solar profiles
# ----------------------------------------------------------------------------------------------------------------------

pv_profiles_df = pd.read_excel(profiles_and_scenarios_ptr, sheet_name="PV profiles")
pv_pv_gen = pv_profiles_df["electricity (p.u.)"].values
total_pv = 0
for gen in grid.generators:
    if "pv" in gen.tech_list[0].name.lower():
        p = pv_pv_gen * gen.Pmax
        gen.P_prof = p
        total_pv += p * gen.active

# ----------------------------------------------------------------------------------------------------------------------
# Balance: Demand - Solar = Diesel, Demand = Diesel + Solar
# ----------------------------------------------------------------------------------------------------------------------

complete_demand = total_diesel + total_pv

# ----------------------------------------------------------------------------------------------------------------------
# Compose matching demand
# ----------------------------------------------------------------------------------------------------------------------

typical_profile_df = pd.read_excel(profiles_and_scenarios_ptr, sheet_name="Typical_profiles")
typical_consumption_df = pd.read_excel(profiles_and_scenarios_ptr, sheet_name="Typical_consumption")
shares_per_feeder_df = pd.read_excel(profiles_and_scenarios_ptr, sheet_name="Shares_per_feeder").fillna(0)

# compose primitive profiles
share_types = ["House with AC", "House without AC", "Shop", "Industry", "Hotel", "Office", "School"]
typical_profile_df2 = typical_profile_df[share_types]

nt = grid.get_time_number()
nl = grid.get_loads_number()
all_loads = np.zeros((nt, nl))
for i, load in enumerate(grid.loads):
    row = shares_per_feeder_df[shares_per_feeder_df["Load_idtag"] == load.idtag][share_types]
    unscaled_values = (typical_profile_df2.values * row.values).sum(axis=1)
    unscaled_values = unscaled_values / np.max(unscaled_values)
    day_profile = unscaled_values * load.contract_power
    p = np.tile(day_profile, 365)
    load.P_prof = p
    all_loads[:, i] = p

# ----------------------------------------------------------------------------------------------------------------------
# Re-calibrate demand
# ----------------------------------------------------------------------------------------------------------------------

scale = all_loads.sum(axis=1) / (complete_demand + 1e-20)


for t in range(nt):
    for i in range(nl):
        all_loads[t, i] /= scale[t]

scale_b = all_loads.sum(axis=1) / (complete_demand + 1e-20)


vg.save_file(grid, "funafuti_ts.veragrid")

plt.plot(all_loads.sum(axis=1), label="Bottom up demand")
plt.plot(complete_demand, label="Top down demand", linestyle="dotted")
plt.legend()
plt.show()
