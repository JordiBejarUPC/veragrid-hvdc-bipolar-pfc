import pandas as pd
import numpy as np
import VeraGridEngine.api as vge

# ------------------------------
# 1. Loading and cleaning data
# ------------------------------

# Load network topology
df_net = pd.read_excel('all_stations_anon_T.xlsx', dtype=str, header=0)
df_net['from'] = df_net['from'].astype(str).str.strip()
df_net['to'] = df_net['to'].astype(str).str.strip()

# Convert numerical columns properly
num_cols = ['length', 'ratedCurrent', 'Irmax_hoch', 'X', 'R', 'X0', 'R0', 'C', 'G', 'C0']
for col in num_cols:
    if col in df_net.columns:
        df_net[col] = pd.to_numeric(df_net[col].str.replace(',', '.', regex=False), errors='coerce')

df_station = df_net[df_net['station'] == 'station_380'].copy()

# Load Profiles (Only the first 24 hours at 15-min resolution)
rows_needed = 96
df_base = pd.read_excel('250806_All_Profiles_EDIH.xlsx', sheet_name='base_consumption', header=0, nrows=rows_needed)
df_pv   = pd.read_excel('250806_All_Profiles_EDIH.xlsx', sheet_name='pv_profiles', header=0, nrows=rows_needed)
df_ev   = pd.read_excel('250806_All_Profiles_EDIH.xlsx', sheet_name='ev_profiles', header=0, nrows=rows_needed)
df_hp   = pd.read_excel('250806_All_Profiles_EDIH.xlsx', sheet_name='hp_profiles', header=0, nrows=rows_needed)

def strip_dots_and_sum_validated(df, sheet_name="Sheet"):
    df_clean = df.copy()
    if 'timestamp' in df_clean.columns:
        df_clean = df_clean.drop(columns=['timestamp'])

    # initial_count = len(df_clean.columns)

    # 1. Strip the dots
    # df_clean.columns = [str(col).split('.')[0] for col in df_clean.columns]

    # 2.Grouping
    # Transpose -> Group by Index -> Sum -> Transpose back
    # df_grouped = df_clean.T.groupby(level=0).sum().T

    # final_count = len(df_grouped.columns)

    # print(f"[{sheet_name}] Processed {initial_count} columns -> Merged into {final_count} unique nodes.")

    return df_clean / 1000.0

# Apply with sheet names for the log
df_base_mw = strip_dots_and_sum_validated(df_base, "Base")
df_pv_mw = strip_dots_and_sum_validated(df_pv, "PV")
df_ev_mw = strip_dots_and_sum_validated(df_ev, "EV")
df_hp_mw = strip_dots_and_sum_validated(df_hp, "HP")

# ------------------------------
# 2. Building the 400 V grid
# ------------------------------

grid = vge.MultiCircuit()

# Create Buses (Everything is 0.4kV)
unique_nodes = pd.unique(df_station[['from', 'to']].values.ravel('K'))
for node in unique_nodes:
    bus = vge.Bus(name=node, Vnom=0.4, xpos=0)
    grid.add_bus(obj=bus)

# Identify 0.4kV Nodes mathematically
cables = df_station[df_station['clazz'] == 'ACLineSegment']
lv_nodes = set(cables['from']).union(set(cables['to']))

slack_injection_nodes = [] # We will store our 400V power plant locations here

Ubase = 0.4
Sbase = 100
Zbase = Ubase**2 / Sbase

# Create Equipment
for _, row in df_station.iterrows():

    bus_by_name = grid.get_bus_dict()
    from_bus = bus_by_name[row['from']]
    to_bus = bus_by_name[row['to']]

    if row['clazz'] == 'ACLineSegment':
        length_km = row['length'] / 1000.0 if pd.notna(row['length']) and row['length'] > 0 else 0.001
        abs_r = row['R'] if pd.notna(row['R']) and row['R'] > 0 else 1e-6
        abs_x = row['X'] if pd.notna(row['X']) and row['X'] > 0 else 1e-6
        imax = row['Irmax_hoch'] if pd.notna(row['Irmax_hoch']) and row['Irmax_hoch'] > 0 else 0.1

        line = vge.Line(name=row['name'], bus_from=from_bus, bus_to=to_bus,
                              length=length_km, r=abs_r/Zbase, x=abs_x/Zbase, b=row['C'] * 2e-9 * np.pi * 50 * Zbase,
                              rate=np.sqrt(3) * imax * 400 / 10**6)
        grid.add_line(line)


    elif row['clazz'] in ['Fuse', 'Jumper']:

        switch = vge.Switch(name=f"{row['name']} ({row['clazz']})",
                            bus_from=from_bus, bus_to=to_bus,
                            rated_current=999)
        grid.add_switch(switch)

    elif row['clazz'] == 'PowerTransformer':
        if 'Netztransformator' in str(row['name']):
            # It's a real substation! Find where it touches the 400V street.
            if from_bus.Vnom >= to_bus.Vnom:
                from_bus.is_slack = True
            else:
                to_bus.is_slack = True
            transformer = vge.Transformer2W(name=row['name'], bus_from=from_bus, bus_to=to_bus,
                                            nominal_power=0.4, rate=0.4,
                                            r=row['R']/Zbase, x=row['X']/Zbase)
            grid.add_transformer2w(transformer)
        else:
            # It's a fake transformer. Bypass it with a switch.
            switch = vge.Switch(name=f"Bypass_{row['name']}",
                                bus_from=from_bus, bus_to=to_bus,
                                rated_current=999)
            grid.add_switch(switch)


vge.save_file(grid, 'bkt.veragrid')