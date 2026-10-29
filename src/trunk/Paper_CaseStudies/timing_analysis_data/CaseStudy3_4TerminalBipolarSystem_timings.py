import math
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import VeraGridEngine.api as gce
from VeraGridEngine import PfcControlType
from VeraGridEngine.enumerations import ConverterControlType, ResultTypes


# ==========================================
# 1. TIMING BENCHMARK FUNCTION
# ==========================================
def run_timing_test(func, iterations=100):
    """Run the power flow function in a loop and collect timing data."""
    times = np.zeros(iterations)

    for i in range(iterations):
        elapsed = func(verbose=0)
        times[i] = elapsed

    return times


# ==========================================
# 2. BASE PARAMETERS & SYSTEM SETUP
# ==========================================
Ub = 525
Sb = 100
Rb = (Ub**2) / Sb
Ib = Sb / Ub  # kA

# Converter Losses Params
a = 0.5515 / Sb
b = 0.887 * (Ib / Sb)
c = 3.77 * ((Ib**2) / Sb)

# Land Cable Params
r_ohm_m_land = 1.7241e-8  # [Ωm]
a_mm2_land = 3000  # [mm2]
d_m_land = 1000  # [m]
a_m2_land = a_mm2_land * 1e-6
r_ohm_km_land = r_ohm_m_land * (d_m_land / a_m2_land)  # ohm/km
r_pu_km_land = r_ohm_km_land / Rb

# Sea Cable Params
r_ohm_m_sea = 1.7241e-8  # [Ωm]
a_mm2_sea = 2500  # [mm2]
d_m_sea = 1000  # [m]
a_m2_sea = a_mm2_sea * 1e-6
r_ohm_km_sea = r_ohm_m_sea * (d_m_sea / a_m2_sea)  # ohm/km
r_pu_km_sea = r_ohm_km_sea / Rb

print("r_pu_km_sea:", r_pu_km_sea)
print("r_pu_km_land:", r_pu_km_land)
print("sea:", r_ohm_km_sea)
print("land:", r_ohm_km_land)

# Distances in Km
d0a = 10
d0c = 10
d1 = 300
d2 = 300
d3 = 400
d4a = 150
d4b = 150
d5 = 300

grid = gce.MultiCircuit(name="4TerminalsBipolarSystem", Sbase=Sb)

# Buses (name, Vnom, is_dc, Grounded, Slack)
d_buses = {
    1: ("Bus1_ac", Ub, False, False, True),
    2: ("Bus2_ac", Ub, False, False, True),
    3: ("Bus3_ac", Ub, False, False, True),
    4: ("Bus4_ac", Ub, False, False, True),
    # Positive pole DC buses
    5: ("Bus0a_dc_+", Ub, True, False, False),
    6: ("Bus0c_dc_+", Ub, True, False, False),
    7: ("Bus1_dc_+", Ub, True, False, False),
    8: ("Bus2_dc_+", Ub, True, False, False),
    9: ("Bus3_dc_+", Ub, True, False, False),
    10: ("Bus4_dc_+", Ub, True, False, False),
    11: ("Bus5_dc_+", Ub, True, False, False),
    # DMR pole DC buses
    12: ("Bus0a_dc_0", Ub, True, False, False),
    13: ("Bus0c_dc_0", Ub, True, False, False),
    14: ("Bus1_dc_0", Ub, True, False, False),
    15: ("Bus2_dc_0", Ub, True, False, False),
    16: ("Bus3_dc_0", Ub, True, True, False),  # grounded bus
    17: ("Bus4_dc_0", Ub, True, False, False),
    18: ("Bus5_dc_0", Ub, True, False, False),
    # Negative pole DC buses
    19: ("Bus0a_dc_-", Ub, True, False, False),
    20: ("Bus0c_dc_-", Ub, True, False, False),
    21: ("Bus1_dc_-", Ub, True, False, False),
    22: ("Bus2_dc_-", Ub, True, False, False),
    23: ("Bus3_dc_-", Ub, True, False, False),
    24: ("Bus4_dc_-", Ub, True, False, False),
    25: ("Bus5_dc_-", Ub, True, False, False),
}

for key, data in d_buses.items():
    bus_name = data[0]
    v_nom = data[1]
    is_dc = data[2]
    is_grounded = data[3]
    is_slack = data[4]
    if "_0" in bus_name:
        busi = gce.Bus(
            name=bus_name,
            Vnom=v_nom,
            is_slack=is_slack,
            is_dc=is_dc,
            is_grounded=is_grounded,
            Vm0=0.0001,
            Va0=0.001,
        )
    elif "_-" in bus_name:
        busi = gce.Bus(
            name=bus_name,
            Vnom=v_nom,
            is_slack=is_slack,
            is_dc=is_dc,
            is_grounded=is_grounded,
            Va0=3.14,
        )
    else:
        busi = gce.Bus(
            name=bus_name,
            Vnom=v_nom,
            is_slack=is_slack,
            is_dc=is_dc,
            is_grounded=is_grounded,
        )

    grid.add_bus(busi)
    globals()[f"bus{key}"] = busi

# PFC Buses
bus2r_pos = gce.Bus(
    name="B2_pfc_r_+", Vnom=Ub, is_slack=False, is_dc=True, is_grounded=False
)
grid.add_bus(bus2r_pos)

bus2s_pos = gce.Bus(
    name="B2_pfc_s_+", Vnom=Ub, is_slack=False, is_dc=True, is_grounded=False
)
grid.add_bus(bus2s_pos)

bus2r_neg = gce.Bus(
    name="B2_pfc_r_-",
    Vnom=Ub,
    is_slack=False,
    is_dc=True,
    is_grounded=False,
    Va0=3.14,
)
grid.add_bus(bus2r_neg)

bus2s_neg = gce.Bus(
    name="B2_pfc_s_-",
    Vnom=Ub,
    is_slack=False,
    is_dc=True,
    is_grounded=False,
    Va0=3.14,
)
grid.add_bus(bus2s_neg)

# Add PFC
grid.add_pfc(
    gce.PFC(
        name="PFC+",
        bus_dc_q=bus7,
        bus_dc_r=bus2r_pos,
        bus_dc_s=bus2s_pos,
        control1=PfcControlType.Is_pfc,
        control1_val=1.4 / Ib,
    )
)

grid.add_pfc(
    gce.PFC(
        name="PFC-",
        bus_dc_q=bus21,
        bus_dc_r=bus2r_neg,
        bus_dc_s=bus2s_neg,
        control1=PfcControlType.Is_pfc,
        control1_val=-0.5 / Ib,
    )
)

# HVDC lines
d_lines = {
    1: (bus5, bus7, d0a, "dc_cable0a_+", "land"),
    2: (bus6, bus10, d0c, "dc_cable0c_+", "land"),
    3: (bus2r_pos, bus8, d1, "dc_cable1_+", "sea"),
    4: (bus7, bus9, d4a, "dc_cable4a_+", "sea"),
    5: (bus9, bus10, d4b, "dc_cable4b_+", "sea"),
    6: (bus2s_pos, bus11, d3, "dc_cable3_+", "sea"),
    7: (bus8, bus11, d2, "dc_cable2_+", "sea"),
    8: (bus10, bus11, d5, "dc_cable5_+", "sea"),
    9: (bus12, bus14, d0a, "dc_cable0a_0", "land"),
    10: (bus13, bus17, d0a, "dc_cable0c_0", "land"),
    11: (bus14, bus15, d1, "dc_cable1_0", "sea"),
    12: (bus14, bus16, d4a, "dc_cable4a_0", "sea"),
    13: (bus16, bus17, d4b, "dc_cable4b_0", "sea"),
    14: (bus14, bus18, d3, "dc_cable3_0", "sea"),
    15: (bus15, bus18, d2, "dc_cable2_0", "sea"),
    16: (bus17, bus18, d5, "dc_cable5_0", "sea"),
    17: (bus19, bus21, d0a, "dc_cable0a_-", "land"),
    18: (bus20, bus24, d0c, "dc_cable0c_-", "land"),
    19: (bus2r_neg, bus22, d1, "dc_cable1_-", "sea"),
    20: (bus21, bus23, d4a, "dc_cable4a_-", "sea"),
    21: (bus23, bus24, d4b, "dc_cable4b_-", "sea"),
    22: (bus2s_neg, bus25, d3, "dc_cable3_-", "sea"),
    23: (bus22, bus25, d2, "dc_cable2_-", "sea"),
    24: (bus24, bus25, d5, "dc_cable5_-", "sea"),
}

for key, data in d_lines.items():
    r_val = r_pu_km_land if data[4] == "land" else r_pu_km_sea
    grid.add_dc_line(
        gce.DcLine(
            name=data[3],
            bus_from=data[0],
            bus_to=data[1],
            r=r_val * data[2],
            length=data[2],
        )
    )

# Generators
grid.add_generator(bus1, gce.Generator(name="AC grid 1", vset=1.0))
grid.add_generator(bus2, gce.Generator(name="AC grid 2", vset=1.0))

# External AC-network configuration for case study execution
CASE_STUDIES_DIR = Path(__file__).resolve().parent.parent   # .../Paper_CaseStudies
DEFAULT_EXTERNAL_AC_MODEL = CASE_STUDIES_DIR / "grids" / "case300.m"
DEFAULT_TARGET_POI_BUS = "7049"  # Default POI bus for case300 study


def prompt_external_ac_model(network_name: str) -> Path:
    """Request a MATPOWER (.m) or VeraGrid (.veragrid) AC-network file."""
    response = (
        input(
            f"Path for {network_name} (.m or .veragrid) "
            f"[Enter for {DEFAULT_EXTERNAL_AC_MODEL.name}]: "
        )
        .strip()
    )
    file_path = (
        Path(response).expanduser() if response else DEFAULT_EXTERNAL_AC_MODEL
    )

    if file_path.suffix.lower() not in {".m", ".veragrid"}:
        raise ValueError(
            f"{network_name} must be a .m or .veragrid file: {file_path}"
        )
    if not file_path.is_file():
        raise FileNotFoundError(
            f"{network_name} file does not exist: {file_path}"
        )

    return file_path


def select_external_poi(
    external_grid: gce.MultiCircuit, network_name: str
) -> gce.Bus:
    """Choose the imported bus connected to the HVDC POI (defaulting to Bus 7049)."""
    if not external_grid.buses:
        raise ValueError(f"{network_name} contains no buses")

    has_target = any(
        str(bus.name) == DEFAULT_TARGET_POI_BUS for bus in external_grid.buses
    )
    default_name = (
        DEFAULT_TARGET_POI_BUS
        if has_target
        else str(external_grid.buses[0].name)
    )

    response = (
        input(
            f"Bus name in {network_name} to connect to the HVDC POI "
            f"[Enter for {default_name}]: "
        )
        .strip()
    )
    requested_name = response or default_name

    for bus in external_grid.buses:
        if str(bus.name) == str(requested_name):
            return bus

    raise ValueError(f"No bus named {requested_name!r} in {network_name}")


def attach_external_ac_network(poi_bus: gce.Bus, network_name: str) -> None:
    """Import one AC network, connect it at `poi_bus`, and keep `poi_bus` slack."""
    file_path = prompt_external_ac_model(network_name)
    external_grid = gce.open_file(filename=str(file_path))

    if not np.isclose(external_grid.Sbase, grid.Sbase):
        raise ValueError(
            f"{network_name} has Sbase={external_grid.Sbase} MVA, but the HVDC grid uses "
            f"Sbase={grid.Sbase} MVA. Convert the model to a common base before connecting it."
        )

    external_poi = select_external_poi(external_grid, network_name)

    for bus in external_grid.buses:
        bus.is_slack = False

    for obj in external_grid.items():
        obj.action = gce.ActionType.Add

    grid.add_circuit(external_grid, re_id_new_grid=True)
    grid.add_transformer2w(
        gce.Transformer2W(
            name=f"{network_name}_POI_transformer",
            bus_from=poi_bus,
            bus_to=external_poi,
            HV=max(poi_bus.Vnom, external_poi.Vnom),
            LV=min(poi_bus.Vnom, external_poi.Vnom),
            r=0.002,
            x=0.10,
            rate=3000,
        )
    )
    print(
        f"Connected {network_name} from {file_path.name} at imported bus {external_poi.name}"
    )


# Attach external AC networks (case300.m at bus 7049 for both AC side 1 and 2)
attach_external_ac_network(bus1, "AC network 1")
attach_external_ac_network(bus2, "AC network 2")

# OWFs
grid.add_generator(bus3, gce.Generator(name="OWF 1", vset=1.0, P=3000))
grid.add_generator(bus4, gce.Generator(name="OWF 2", vset=1.0, P=3000))

# VSC setup
Pdc_set = 15
k = 1

# Positive pole VSCs
grid.add_vsc(
    gce.VSC(
        name="VSC_1+",
        bus_to=bus1,
        bus_from=bus5,
        bus_dc_n=bus12,
        rate=3000,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Pdc_droop,
        control1_val=Pdc_set,
        control1_val_min=-3000,
        control1_val_max=3000,
        control1_droop=k,
        control1_droop_val=1.0,
        control1_droop_val_min=0.9,
        control1_droop_val_max=1.1,
        control2=ConverterControlType.Qac,
        control2_val=0.0,
    )
)

grid.add_vsc(
    gce.VSC(
        name="VSC_2+",
        bus_to=bus2,
        bus_from=bus6,
        bus_dc_n=bus13,
        rate=3000,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Pdc_droop,
        control1_val=Pdc_set,
        control1_val_min=-3000,
        control1_val_max=3000,
        control1_droop=k,
        control1_droop_val=1.0,
        control1_droop_val_min=0.9,
        control1_droop_val_max=1.1,
        control2=ConverterControlType.Qac,
        control2_val=0.0,
    )
)

grid.add_vsc(
    gce.VSC(
        name="VSC_3+",
        bus_to=bus3,
        bus_from=bus8,
        bus_dc_n=bus15,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Pac,
        control2=ConverterControlType.Qac,
        control1_val=1500,
        control2_val=0.0,
    )
)

grid.add_vsc(
    gce.VSC(
        name="VSC_4+",
        bus_to=bus4,
        bus_from=bus11,
        bus_dc_n=bus18,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Pac,
        control2=ConverterControlType.Qac,
        control1_val=1500,
        control2_val=0.0,
    )
)

# Negative pole VSCs
grid.add_vsc(
    gce.VSC(
        name="VSC_1-",
        bus_to=bus1,
        bus_from=bus19,
        bus_dc_n=bus12,
        rate=3000,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Pdc_droop,
        control1_val=Pdc_set,
        control1_val_min=-3000,
        control1_val_max=3000,
        control1_droop=k,
        control1_droop_val=1.0,
        control1_droop_val_min=0.9,
        control1_droop_val_max=1.1,
        control2=ConverterControlType.Qac,
        control2_val=0.0,
    )
)

grid.add_vsc(
    gce.VSC(
        name="VSC_2-",
        bus_to=bus2,
        bus_from=bus20,
        bus_dc_n=bus13,
        rate=3000,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Pdc_droop,
        control1_val=Pdc_set,
        control1_val_min=-3000,
        control1_val_max=3000,
        control1_droop=k,
        control1_droop_val=1.0,
        control1_droop_val_min=0.9,
        control1_droop_val_max=1.1,
        control2=ConverterControlType.Qac,
        control2_val=0.0,
    )
)

grid.add_vsc(
    gce.VSC(
        name="VSC_3-",
        bus_to=bus3,
        bus_from=bus22,
        bus_dc_n=bus15,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Pac,
        control2=ConverterControlType.Qac,
        control1_val=750,
        control2_val=0.0,
    )
)

grid.add_vsc(
    gce.VSC(
        name="VSC_4-",
        bus_to=bus4,
        bus_from=bus25,
        bus_dc_n=bus18,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Pac,
        control2=ConverterControlType.Qac,
        control1_val=750,
        control2_val=0.0,
    )
)

# Save assembled grid model
output_file = Path(__file__).with_name(
    "4TerminalBipolarSystem_case300_bus7049.veragrid"
)
gce.save_file(grid=grid, filename=str(output_file))
print(f"Saved VeraGrid model: {output_file}")


# ==========================================
# 3. TIMING BENCHMARK EXECUTION
# ==========================================
def solve_pf(verbose=0):
    """Wrapper function for benchmarking power flow timing without file report overhead."""
    options_pf = gce.PowerFlowOptions(
        verbose=verbose,
        generate_report=False,
        retry_with_other_methods=False,
        tolerance=1e-8,
        use_stored_guess=True,
    )
    res = gce.power_flow(grid, options=options_pf)
    return res.elapsed


iterations = 100
print(f"\n=== RUNNING TIMING BENCHMARK ({iterations} ITERATIONS) ===")
timing_data = run_timing_test(solve_pf, iterations=iterations)

mean_time_ms = timing_data.mean() * 1000
std_time_ms = timing_data.std() * 1000
min_time_ms = timing_data.min() * 1000
max_time_ms = timing_data.max() * 1000

print("=== TIMING BENCHMARK RESULTS ===")
print(f"Mean Time: {mean_time_ms:.3f} ms")
print(f"Std Dev:   {std_time_ms:.3f} ms")
print(f"Min Time:  {min_time_ms:.3f} ms")
print(f"Max Time:  {max_time_ms:.3f} ms\n")


# ==========================================
# 4. DETAILED POWER FLOW & REPORTING
# ==========================================
options_pf = gce.PowerFlowOptions(
    verbose=1,
    generate_report=True,
    retry_with_other_methods=False,
    tolerance=1e-8,
    use_stored_guess=True,
)
results = gce.power_flow(grid, options=options_pf)

print("Converged:", results.converged, "error:", results.error)
print("Iterations:", results.iterations)
print("Time (s):", results.elapsed)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(
    results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame()
)
print(
    results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame()
)
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())

df_currents = (
    results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()
    * Ib
)
print("kA Currents:\n", df_currents.round(2))

print("VSC Vdc:\n", results.mdl(result_type=ResultTypes.VscVdc).get_data_frame())
print("VSC Pdc:\n", results.mdl(result_type=ResultTypes.VscPdc).get_data_frame())
print(
    "VSC Idc (A):\n",
    results.mdl(result_type=ResultTypes.VscIdc).get_data_frame() * Ib * 1000,
)

# PFC results
print(
    "PFC Vr (kV):\n",
    results.mdl(result_type=ResultTypes.PfcVr).get_data_frame() * Ub,
)
print(
    "PFC Vs (kV):\n",
    results.mdl(result_type=ResultTypes.PfcVs).get_data_frame() * Ub,
)
print("PFC PB:\n", results.mdl(result_type=ResultTypes.PfcPB).get_data_frame())
print(
    "PFC Current Q (A):\n",
    results.mdl(result_type=ResultTypes.PfcCurrentQ).get_data_frame()
    * Ib
    * 1000,
)
print(
    "PFC Current R (A):\n",
    results.mdl(result_type=ResultTypes.PfcCurrentR).get_data_frame()
    * Ib
    * 1000,
)
print(
    "PFC Current S (A):\n",
    results.mdl(result_type=ResultTypes.PfcCurrentS).get_data_frame()
    * Ib
    * 1000,
)


# ==========================================
# 5. DATA EXPORT WITH TIMING SUMMARY
# ==========================================
summary_df = pd.DataFrame(
    [
        {
            "Converged": results.converged,
            "Error": results.error,
            "Iterations": results.iterations,
            "Single_Run_Elapsed_s": results.elapsed,
            "Benchmark_Mean_ms": mean_time_ms,
            "Benchmark_Std_ms": std_time_ms,
            "Benchmark_Min_ms": min_time_ms,
            "Benchmark_Max_ms": max_time_ms,
        }
    ]
)

excel_filename = Path(__file__).resolve().parent / "veragrid_4terminal_case300_timing_results.xlsx"
with pd.ExcelWriter(excel_filename, engine="openpyxl") as writer:
    summary_df.to_excel(writer, sheet_name="Summary", index=False)
    results.get_bus_df().to_excel(writer, sheet_name="Bus_Voltages")
    pd.DataFrame(
        {"Iteration": range(1, iterations + 1), "Elapsed_s": timing_data}
    ).to_excel(writer, sheet_name="Timing_Raw_Data", index=False)

print(f"\nExcel report saved as: {excel_filename}")