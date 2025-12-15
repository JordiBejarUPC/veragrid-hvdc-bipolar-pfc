import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import SolverType, ShuntConnectionType, WindingType
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def plot_voltage_3ph(df):
    """
    Plot voltage magnitudes and angles for phases N, A, B, C.
    2 rows: magnitudes (top), angles (bottom)
    4 columns: phases N, A, B, C
    """

    phases = ['N', 'A', 'B', 'C']
    mag_cols = [f'Vm_{p}' for p in phases]
    ang_cols = [f'Va_{p}' for p in phases]

    fig, axes = plt.subplots(
        nrows=2,
        ncols=4,
        figsize=(16, 9),
        sharex=True
    )

    x = range(len(df.index))

    # --- Magnitudes (row 0)
    for i, p in enumerate(phases):
        ax = axes[0, i]
        ax.plot(x, df[f'Vm_{p}']  * (U_base / np.sqrt(3)), marker='o')
        ax.set_title(f'Phase {p}')
        ax.set_ylabel('|U| [V]')
        ax.grid(True)

        ax.ticklabel_format(style='plain', axis='y')
        ax.yaxis.get_major_formatter().set_useOffset(False)

    # --- Angles (row 1)
    for i, p in enumerate(phases):
        ax = axes[1, i]
        ax.plot(x, df[f'Va_{p}'], marker='o')
        ax.set_ylabel(r'$\delta$ [$\circ$]')
        ax.set_xlabel('Bus')
        ax.grid(True)

    # X ticks: bus names
    for ax in axes[1, :]:
        ax.set_xticks(x)
        ax.set_xticklabels(df.index, rotation=90)

    fig.suptitle('Three-Phase Voltages', fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    return fig

def plot_current_3ph(df):
    """
    Plot current magnitudes and angles for phases N, A, B, C.
    2 rows: magnitudes (top), angles (bottom)
    4 columns: phases N, A, B, C
    """

    phases = ['N', 'A', 'B', 'C']
    mag_cols = [f'Im_{p}' for p in phases]
    ang_cols = [f'Ia_{p}' for p in phases]

    fig, axes = plt.subplots(
        nrows=2,
        ncols=4,
        figsize=(16, 9),
        sharex=True
    )

    x = range(len(df.index))

    # --- Magnitudes (row 0)
    for i, p in enumerate(phases):
        ax = axes[0, i]
        ax.plot(x, df[f'Im_{p}'] * I_base, marker='o')
        ax.set_title(f'Phase {p}')
        ax.set_ylabel('|I| [A]')
        ax.grid(True)

        ax.ticklabel_format(style='plain', axis='y')
        ax.yaxis.get_major_formatter().set_useOffset(False)

    # --- Angles (row 1)
    for i, p in enumerate(phases):
        ax = axes[1, i]
        ax.plot(x, df[f'Ia_{p}'], marker='o')
        ax.set_ylabel(f'$\delta_{p}$ [$\circ$]')
        ax.set_xlabel('Line')
        ax.grid(True)

    # X ticks: bus names
    for ax in axes[1, :]:
        ax.set_xticks(x)
        ax.set_xticklabels(df.index, rotation=90)

    fig.suptitle('Three-Phase Currents', fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    return fig

def plot_unbalance_factors(df_iuf, df_vuf):
    """
    Plot Current Unbalance Factor (IUF) and Voltage Unbalance Factor (VUF)
    side by side.

    Left  : VUF [%]
    Right : IUF [%]
    """

    fig, axes = plt.subplots(
        nrows=1,
        ncols=2,
        figsize=(16, 5),
        sharey=False
    )

    # ------------------------
    # VUF (left)
    # ------------------------
    ax = axes[0]
    x_v = range(len(df_vuf.index))

    ax.plot(x_v, df_vuf['VUF'], marker='o')
    ax.set_title('Voltage Unbalance Factor (VUF)')
    ax.set_ylabel('VUF [%]')
    ax.set_xlabel('Bus')
    ax.grid(True)

    ax.ticklabel_format(style='plain', axis='y')
    ax.yaxis.get_major_formatter().set_useOffset(False)

    ax.set_xticks(x_v)
    ax.set_xticklabels(df_vuf.index, rotation=90)

    # ------------------------
    # IUF (right)
    # ------------------------
    ax = axes[1]
    x_i = range(len(df_iuf.index))

    ax.plot(x_i, df_iuf['IUF'], marker='o')
    ax.set_title('Current Unbalance Factor (IUF)')
    ax.set_ylabel('IUF [%]')
    ax.set_xlabel('Branch')
    ax.grid(True)

    ax.ticklabel_format(style='plain', axis='y')
    ax.yaxis.get_major_formatter().set_useOffset(False)

    ax.set_xticks(x_i)
    ax.set_xticklabels(df_iuf.index, rotation=90)

    fig.suptitle('Unbalance Factors (Negative / Positive Sequence)', fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.92])

    return fig

logger = gce.Logger()
grid = gce.MultiCircuit()
df_buses_lines = pd.read_csv('C:/Users/alexb/estabanell_grid/linies_bt_eRoots.csv', sep=";")

# Buses que no quieres
buses_to_delete = [
    57573, 57552, 117181, 117182, 57744, 58152, 58173, 58025, 58026, 57723,
    58020, 58039, 58030, 58029, 58028, 58043, 58036, 58027, 58037, 58046
]
buses_to_delete_str = [str(b) for b in buses_to_delete]

df_buses_lines = df_buses_lines[
    ~df_buses_lines["node_start"].astype(str).isin(buses_to_delete_str) &
    ~df_buses_lines["node_end"].astype(str).isin(buses_to_delete_str)
]

# -------------------------------------------------------------------------------------
#   Simplification 58022 -> 58023
# -------------------------------------------------------------------------------------
path = ["58022","58021","58024","58031","58032","58033","58034","58023"]

mask = df_buses_lines.apply(
    lambda row: (str(row["node_start"]) in path and str(row["node_end"]) in path),
    axis=1
)
df_path = df_buses_lines[mask]

# sumar impedancias y longitud
R_eq = df_path["resistencia"].sum()
X_eq = df_path["reactancia"].sum()
L_eq = df_path["longitud_cad"].sum()
Imax_eq = df_path["intensitat_admisible"].min()

# eliminar esas líneas del DataFrame original
df_buses_lines = df_buses_lines.drop(df_path.index)

# añadir la nueva línea equivalente
df_buses_lines = pd.concat([
    df_buses_lines,
    pd.DataFrame([{
        "tram": "58022_58023",
        "num_linia": "Equivalent",
        "node_start": 58022,
        "node_end": 58023,
        "resistencia": R_eq,
        "reactancia": X_eq,
        "longitud_cad": L_eq,
        "intensitat_admisible": Imax_eq
    }])
], ignore_index=True)

# ---------------------------------------------------------------------------------------------------------------------
#   Buses
# ---------------------------------------------------------------------------------------------------------------------
buses = pd.unique(df_buses_lines[["node_start", "node_end"]].values.ravel())
bus_dict = dict()

y9 = 0.0
y11 = 0.0
y13 = 0.0

for bus in buses:

    bus_id = int(bus)

    has_line_9 = (
            (
                (df_buses_lines["node_start"] == bus_id) |
                (df_buses_lines["node_end"] == bus_id)
            ) &
            (df_buses_lines["num_linia"] == 9)
    ).any()

    has_line_11 = (
            (
                (df_buses_lines["node_start"] == bus_id) |
                (df_buses_lines["node_end"] == bus_id)
            ) &
            (df_buses_lines["num_linia"] == 11)
    ).any()

    has_line_13 = (
            (
                (df_buses_lines["node_start"] == bus_id) |
                (df_buses_lines["node_end"] == bus_id)
            ) &
            (df_buses_lines["num_linia"] == 13)
    ).any()

    if has_line_9:
        ypos = y9 + 20.0
        xpos = 0
        y9 += 20
        line_name = '09'
    elif has_line_11:
        ypos = y11 + 20.0
        xpos = 50
        y11 += 20
        line_name = '11'
    elif has_line_13:
        ypos = y13 + 20.0
        xpos = 100
        y13 += 20
        line_name = '13'
    else:
        ypos = 0.0
        xpos = 0.0

    bus = gce.Bus(name=str(bus), Vnom=0.4, xpos=xpos, ypos=ypos, code=line_name)
    if bus.name == str(58022):
        bus.is_slack = True
        gen = gce.Generator()
        grid.add_generator(bus=bus, api_obj=gen)
    grid.add_bus(obj=bus)
    bus_dict[int(float(bus.name))] = bus

# # Slack Bus
# bus_slack = gce.Bus(name='Slack', Vnom=5.125)
# bus_slack.is_slack = True
# grid.add_bus(obj=bus_slack)
# gen = gce.Generator()
# grid.add_generator(bus=bus_slack, api_obj=gen)
#
# # CT
# trafo = gce.Transformer2W(name='CT',
#                           bus_from=bus_slack,
#                           bus_to=bus_dict[58022],
#                           HV=5.125,
#                           LV=0.4,
#                           nominal_power=0.4,
#                           rate=0.4,
#                           x=4.05 * 2.5)
# trafo.conn_f = WindingType.GroundedStar
# trafo.conn_t = WindingType.GroundedStar
# grid.add_transformer2w(trafo)

# ---------------------------------------------------------------------------------------------------------------------
#   Lines
# ---------------------------------------------------------------------------------------------------------------------
rho_Cu = 1.72
rho_Al = 2.82
Al_to_Cu = rho_Cu / rho_Al
last_R, last_X = None, None
for _, row in df_buses_lines.iterrows():

    node_start = row['node_start']
    node_end = row['node_end']

    if row['reactancia'] == 0:
        # usa los valores de la fila anterior guardados
        R_val = last_R * Al_to_Cu
        X_val = last_X
    else:
        # usa los valores de la fila actual
        R_val = row['resistencia']
        X_val = row['reactancia']
        # actualiza memoria
        last_R, last_X = R_val, X_val

    line_type = gce.SequenceLineType(
        name=f'{node_start}_{node_end}',
        Imax=row['intensitat_admisible'] / 1e3,
        Vnom=400,
        R=R_val,
        X=X_val,
        R0=3 * R_val,
        X0=3 * X_val
    )
    grid.add_sequence_line(line_type)

    line = gce.Line(
        bus_from=bus_dict[row['node_start']],
        bus_to=bus_dict[row['node_end']],
        name=f'{node_start}_{node_end}',
        code=row['num_linia'],
        rate=row['intensitat_admisible'] * 400 / 1e6,
        length=row['longitud_cad'] / 1000
    )
    line.apply_template(line_type, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line)

# ---------------------------------------------------------------------------------------------------------------------
#   Loads
# ---------------------------------------------------------------------------------------------------------------------
df_meters = pd.read_csv('C:/Users/alexb/estabanell_grid/cups_eRoots.csv', sep=";")
df_powers = pd.read_csv('C:/Users/alexb/estabanell_grid/Corbes_CUPS_CT-0975.csv', sep=";")

# For now, only the first measurement of each meter
df_first = df_powers.groupby("MeterID").first().reset_index()

S_sum = 0 + 0j
for _, row_meters in df_meters.iterrows():
    row_power = df_first[df_first["MeterID"] == row_meters["comptador"]]

    P = (float(row_power["TotalActiveEnergyConsumed"].values[0]) - float(row_power["TotalActiveEnergyProduced"].values[0])) / 1000
    Q = (float(row_power["TotalReactiveEnergyProduced"].values[0]) - float(row_power["TotalReactiveEnergyConsumed"].values[0])) / 1000

    S_sum = S_sum + (P + 1j * Q)

    # if bus_dict[row_meters['node']].name == '117743':
    #     load = gce.Load(
    #         name=row_meters['comptador'],
    #         P1=P * 100,
    #         Q1=Q * 100,
    #         P2=P * 100,
    #         Q2=Q * 100,
    #         P3=P * 100,
    #         Q3=Q * 100)

    if int(row_meters['tensio']) == 400:
        # Balanced
        load = gce.Load(
            name=row_meters['comptador'],
            P1=P / 3,
            Q1=Q / 3,
            P2=P / 3,
            Q2=Q / 3,
            P3=P / 3,
            Q3=Q / 3)

    elif int(row_meters['tensio']) == 230:
        # Unbalanced
        phase_probs = [1 / 3, 1 / 3, 1 / 3]
        phase = np.random.choice(["A", "B", "C"], p=phase_probs)

        if phase == "A":
            load = gce.Load(
                name=row_meters['comptador'],
                P1=P,
                Q1=Q)
        elif phase == "B":
            load = gce.Load(
                name=row_meters['comptador'],
                P2=P,
                Q2=Q)
        else:
            load = gce.Load(
                name=row_meters['comptador'],
                P3=P,
                Q3=Q)

    else:
        raise Exception("Incorrect load voltage!")

    load.conn = ShuntConnectionType.NeutralStar
    grid.add_load(bus=bus_dict[row_meters['node']], api_obj=load)

# ---------------------------------------------------------------------------------------------------------------------
#   Save Grid
# ---------------------------------------------------------------------------------------------------------------------
# print()
# gce.save_file(grid=grid, filename='estabanell.veragrid')

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = gce.power_flow3ph(grid=grid, options=gce.PowerFlowOptions(solver_type=SolverType.NR,
                                                                retry_with_other_methods=False))
print("\n", res.get_voltage_3ph_df())
print("\nConverged? ", res.converged)
print("\nIterations: ", res.iterations)
print("\n", res.get_current_3ph_df())

S_base = 100 * 10**6
U_base = 0.4 * 10**3
I_base = S_base / (U_base * np.sqrt(3))
df_current_A = res.get_current_3ph_df() * I_base
pd.set_option("display.float_format", "{:.2f}".format)
print("\n", df_current_A)

pd.set_option("display.float_format", "{:.3f}".format)
print("\n", res.get_voltage_unbalance_factor_df())
print("\n", res.get_current_unbalance_factor_df())

df = res.get_voltage_3ph_df()
plot_voltage_3ph(df)
plt.show()

df = res.get_current_3ph_df()
plot_current_3ph(df)
plt.show()

df_vuf = res.get_voltage_unbalance_factor_df()
df_iuf = res.get_current_unbalance_factor_df()
plot_unbalance_factors(df_iuf, df_vuf)
plt.show()