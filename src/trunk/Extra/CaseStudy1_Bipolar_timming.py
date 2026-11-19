import math
import numpy as np
import pandas as pd
import VeraGridEngine.api as gce
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
# 2. PARAMETERS & SYSTEM SETUP
# ==========================================
Ub = 525  # kV
Sb = 100  # MW
Rb = (Ub**2) / Sb  # Ohms
Ib = Sb / Ub  # kA

a = 0.5515 / Sb
b = 0.887 * (Ib / Sb)
c = 3.77 * ((Ib**2) / Sb)

dcr_20 = 1.7241e-8  # ohm*m
A = 2.5e-3  # m
r_ohm_km = (dcr_20 / A) * 1000  # ohm/km
r_ohm = r_ohm_km * 100  # ohm for a 100km line
r = r_ohm / Rb  # p.u. for a 100km line

print(f"r_ohm_km: {r_ohm_km}")
print(f"r_ohm: {r_ohm}")


# ==========================================
# 3. BUILD GRID MODEL
# ==========================================
grid = gce.MultiCircuit(name="Bipolar_system", Sbase=Sb)

# AC / DC Buses
bus1 = gce.Bus(name="Bus1", Vnom=Ub, is_slack=True)
grid.add_bus(bus1)

bus2 = gce.Bus(name="Bus2", Vnom=Ub, is_dc=True)
grid.add_bus(bus2)

bus3 = gce.Bus(name="Bus3", Vnom=Ub, is_dc=True)
grid.add_bus(bus3)

bus4 = gce.Bus(name="Bus4", Vnom=Ub, is_dc=True, Vm0=1e-9, Va0=1e-9)
grid.add_bus(bus4)

bus5 = gce.Bus(name="Bus5", Vnom=Ub, is_dc=True, Vm0=1e-9, Va0=1e-9)
grid.add_bus(bus5)

bus6 = gce.Bus(
    name="Bus6", Vnom=Ub, is_dc=True, is_grounded=True, Vm0=1.0, Va0=math.pi
)
grid.add_bus(bus6)

bus7 = gce.Bus(name="Bus7", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi)
grid.add_bus(bus7)

bus8 = gce.Bus(name="Bus8", Vnom=Ub, is_slack=True)
grid.add_bus(bus8)

# Generators
grid.add_generator(bus1, gce.Generator(name="g1", vset=1.0))
grid.add_generator(bus8, gce.Generator(name="g8", vset=1.0))

# DC Lines
grid.add_dc_line(gce.DcLine(name="dc_line_23", bus_from=bus2, bus_to=bus3, r=r))
grid.add_dc_line(gce.DcLine(name="dc_line_45", bus_from=bus4, bus_to=bus5, r=r))
grid.add_dc_line(gce.DcLine(name="dc_line_0", bus_from=bus6, bus_to=bus7, r=r))

# VSCs
grid.add_vsc(
    gce.VSC(
        name="VSC_1",
        bus_to=bus1,
        bus_from=bus2,
        bus_dc_n=bus6,
        rate=30,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Vm_dc,
        control1_val=1.1,
        control2=ConverterControlType.Qac,
        control2_val=0.0,
    )
)

grid.add_vsc(
    gce.VSC(
        name="VSC_2",
        bus_to=bus1,
        bus_from=bus4,
        bus_dc_n=bus6,
        rate=30,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Vm_dc,
        control1_val=-1.1,
        control2=ConverterControlType.Qac,
        control2_val=0.0,
    )
)

grid.add_vsc(
    gce.VSC(
        name="VSC_3",
        bus_from=bus3,
        bus_to=bus8,
        bus_dc_n=bus7,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Pdc,
        control2=ConverterControlType.Qac,
        control1_val=-1000,
        control2_val=0.0,
    )
)

grid.add_vsc(
    gce.VSC(
        name="VSC_4",
        bus_from=bus5,
        bus_to=bus8,
        bus_dc_n=bus7,
        alpha1=a,
        alpha2=b,
        alpha3=c,
        control1=ConverterControlType.Pdc,
        control2=ConverterControlType.Qac,
        control1_val=-500,
        control2_val=0.0,
    )
)


# ==========================================
# 4. TIMING TEST BENCHMARK
# ==========================================
def solve_pf(verbose=0):
    """Wrapper to run power flow for benchmark timing without file I/O overhead."""
    options_pf = gce.PowerFlowOptions(
        verbose=verbose,
        generate_report=False,
        retry_with_other_methods=False,
        tolerance=1e-8,
        use_stored_guess=False,
    )
    res = gce.power_flow(grid, options=options_pf)
    return res.elapsed


# Run 100 benchmark iterations
iterations = 100
times = run_timing_test(solve_pf, iterations=iterations)

timing_summary = {
    "Iterations": iterations,
    "Mean_Time_ms": times.mean() * 1000,
    "Std_Time_ms": times.std() * 1000,
    "Min_Time_ms": times.min() * 1000,
    "Max_Time_ms": times.max() * 1000,
}

print("\n=== TIMING BENCHMARK RESULTS ===")
print(f"Mean Time : {timing_summary['Mean_Time_ms']:.3f} ms")
print(f"Std Dev   : {timing_summary['Std_Time_ms']:.3f} ms")
print(f"Min Time  : {timing_summary['Min_Time_ms']:.3f} ms")
print(f"Max Time  : {timing_summary['Max_Time_ms']:.3f} ms\n")


# ==========================================
# 5. DETAILED SINGLE POWER FLOW RUN
# ==========================================
options_pf = gce.PowerFlowOptions(
    verbose=1,
    generate_report=True,
    retry_with_other_methods=False,
    tolerance=1e-8,
    use_stored_guess=False,
)
results = gce.power_flow(grid, options=options_pf)

print("Converged:", results.converged, "error:", results.error)
print("Iterations:", results.iterations)
print("Time (s):", results.elapsed)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())
print(
    results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame()
)
print(
    results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame()
)

print(
    results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()
)
print(
    results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()
    * Ib
    * 1000
)

print(results.mdl(result_type=ResultTypes.VscVdc).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPdc).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscIdc).get_data_frame() * Ib * 1000)


# ==========================================
# 6. PROCESS DATA & EXPORT RESULTS
# ==========================================
# Performance & Timing Metrics Summary
summary_df = pd.DataFrame(
    [
        {
            "Converged": results.converged,
            "Error": results.error,
            "Iterations": results.iterations,
            "Elapsed_Time_s": results.elapsed,
            "Mean_Timing_ms": timing_summary["Mean_Time_ms"],
            "Min_Timing_ms": timing_summary["Min_Time_ms"],
            "Max_Timing_ms": timing_summary["Max_Timing_ms"],
            "Std_Timing_ms": timing_summary["Std_Time_ms"],
        }
    ]
)

# Bus Voltages DataFrame
bus_df = results.get_bus_df()

# VSC Detailed Results
vsc_vdc = results.mdl(result_type=ResultTypes.VscVdc).get_data_frame()
vsc_pdc = results.mdl(result_type=ResultTypes.VscPdc).get_data_frame()
vsc_idc_mA = (
    results.mdl(result_type=ResultTypes.VscIdc).get_data_frame() * Ib * 1000
)

vsc_df = pd.DataFrame(
    {
        "Vdc_pu": vsc_vdc.iloc[:, 0] if not vsc_vdc.empty else None,
        "Pdc_MW": vsc_pdc.iloc[:, 0] if not vsc_pdc.empty else None,
        "Idc_mA": vsc_idc_mA.iloc[:, 0] if not vsc_idc_mA.empty else None,
    }
)

# Line Currents DataFrame (mA)
branch_currents_df = (
    results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()
    * Ib
    * 1000
)
branch_currents_df.columns = ["Current_mA"]

# All timing raw samples
timing_raw_df = pd.DataFrame({"Iteration": range(1, iterations + 1), "Elapsed_s": times})

# Excel Export
excel_filename = "veragrid_results_case2.xlsx"
with pd.ExcelWriter(excel_filename, engine="openpyxl") as writer:
    summary_df.to_excel(writer, sheet_name="Summary", index=False)
    bus_df.to_excel(writer, sheet_name="Bus_Voltages")
    vsc_df.to_excel(writer, sheet_name="VSC_Results")
    branch_currents_df.to_excel(writer, sheet_name="Branch_Currents")
    timing_raw_df.to_excel(writer, sheet_name="Timing_Raw_Data", index=False)

print(f"Excel report saved as: {excel_filename}")

# CSV Exports
bus_df.to_csv("veragrid_buses.csv")
vsc_df.to_csv("veragrid_vscs.csv")
branch_currents_df.to_csv("veragrid_branch_currents.csv")
summary_df.to_csv("veragrid_summary.csv", index=False)
timing_raw_df.to_csv("veragrid_timing_raw.csv", index=False)

print("CSV files successfully exported.")