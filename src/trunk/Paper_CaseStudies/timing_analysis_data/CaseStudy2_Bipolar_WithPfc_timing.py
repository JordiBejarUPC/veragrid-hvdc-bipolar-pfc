"""
Case Study 2 (timing): Bipolar HVDC link with a PFC in each pole and a DMR
- Builds the same system as CaseStudy2_Bipolar_WithPfc.py (balanced scenario by default).
- Solves the power flow 100 times and reports the mean, standard deviation,
  minimum and maximum solution times.
- Runs one detailed power flow and exports the results and the raw timings to Excel.
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd

import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, ResultTypes

OUT_DIR = Path(__file__).resolve().parent


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
Ub = 525  # kV
Sb = 100  # MW
Rb = (Ub**2) / Sb  # Ohm
Ib = Sb / Ub  # kA

# Converter losses parameters
a = 0.5515 / Sb
b = 0.887 * (Ib / Sb)
c = 3.77 * ((Ib**2) / Sb)

# Cable parameters
dcr_20 = 1.7241e-8  # Ohm·m
A = 2500e-6  # m² (2500 mm²)
r_ohm_km = (dcr_20 / A) * 1000  # Ohm/km
r_ohm = r_ohm_km * 100  # Ohm for a 100 km line
r = 2 * (r_ohm / Rb)  # p.u.; each pole is split into two parallel paths (R and S) of 2r -> equivalent r

# PFC set-point
Is_set_A = 1400  # A
Is_set_kA = Is_set_A / 1000  # kA
Is_set_pu = Is_set_kA / Ib  # p.u.

# VSC control parameters
Vdc_vsc = 1.1  # p.u.
Pdc_vsc3 = -1000  # MW
Pdc_vsc4 = -1000  # MW

grid = gce.MultiCircuit(name="Bipolar_system", Sbase=Sb)

# AC / DC buses
bus1 = gce.Bus(name="Bus1", Vnom=Ub, is_slack=True)
grid.add_bus(bus1)

# Positive pole
bus2 = gce.Bus(name="Bus2", Vnom=Ub, is_dc=True)
grid.add_bus(bus2)

bus_r_pos = gce.Bus(name="BusR_Pos", Vnom=Ub, is_dc=True)
grid.add_bus(bus_r_pos)

bus_s_pos = gce.Bus(name="BusS_Pos", Vnom=Ub, is_dc=True)
grid.add_bus(bus_s_pos)

bus3 = gce.Bus(name="Bus3", Vnom=Ub, is_dc=True)
grid.add_bus(bus3)

# Negative pole
bus4 = gce.Bus(name="Bus4", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi)
grid.add_bus(bus4)

bus5 = gce.Bus(name="Bus5", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi)
grid.add_bus(bus5)

bus_r_neg = gce.Bus(name="BusR_Neg", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi)
grid.add_bus(bus_r_neg)

bus_s_neg = gce.Bus(name="BusS_Neg", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi)
grid.add_bus(bus_s_neg)

# DMR
bus6 = gce.Bus(name="Bus6", Vnom=Ub, is_dc=True, is_grounded=True, Vm0=1e-9, Va0=1e-9)
grid.add_bus(bus6)

bus7 = gce.Bus(name="Bus7", Vnom=Ub, is_dc=True, Vm0=1e-9, Va0=1e-9)
grid.add_bus(bus7)

bus8 = gce.Bus(name="Bus8", Vnom=Ub, is_slack=True)
grid.add_bus(bus8)

# Generators
grid.add_generator(bus1, gce.Generator(name="g1", vset=1.0))
grid.add_generator(bus8, gce.Generator(name="g8", vset=1.0))

# DC lines
grid.add_dc_line(gce.DcLine(name="dc_line_r3_pos", bus_from=bus_r_pos, bus_to=bus3, r=r))
grid.add_dc_line(gce.DcLine(name="dc_line_s3_pos", bus_from=bus_s_pos, bus_to=bus3, r=r))
grid.add_dc_line(gce.DcLine(name="dc_line_r5_neg", bus_from=bus_r_neg, bus_to=bus5, r=r))
grid.add_dc_line(gce.DcLine(name="dc_line_s5_neg", bus_from=bus_s_neg, bus_to=bus5, r=r))
grid.add_dc_line(gce.DcLine(name="dc_line_0", bus_from=bus6, bus_to=bus7, r=r))

# PFCs
grid.add_pfc(
    gce.PFC(
        name="PFC_pos",
        bus_dc_q=bus2,
        bus_dc_r=bus_r_pos,
        bus_dc_s=bus_s_pos,
        control1=gce.PfcControlType.Is_pfc,
        control1_val=Is_set_pu,
    )
)

grid.add_pfc(
    gce.PFC(
        name="PFC_neg",
        bus_dc_q=bus4,
        bus_dc_r=bus_r_neg,
        bus_dc_s=bus_s_neg,
        control1=gce.PfcControlType.Is_pfc,
        control1_val=-Is_set_pu,
    )
)

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
        control1_val=Vdc_vsc,
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
        control1_val=-Vdc_vsc,
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
        control1_val=Pdc_vsc3,
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
        control1_val=Pdc_vsc4,
        control2_val=0.0,
    )
)

# Save assembled grid model
output_file = OUT_DIR / "BipolarSystem_WithPfc_case2.veragrid"
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
print(results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())

df_currents = (
    results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame() * Ib
)
print("kA Currents:\n", df_currents.round(2))

print("VSC Vdc:\n", results.mdl(result_type=ResultTypes.VscVdc).get_data_frame())
print("VSC Pdc:\n", results.mdl(result_type=ResultTypes.VscPdc).get_data_frame())
print(
    "VSC Idc (A):\n",
    results.mdl(result_type=ResultTypes.VscIdc).get_data_frame() * Ib * 1000,
)

# PFC results
print("PFC Vr (kV):\n", results.mdl(result_type=ResultTypes.PfcVr).get_data_frame() * Ub)
print("PFC Vs (kV):\n", results.mdl(result_type=ResultTypes.PfcVs).get_data_frame() * Ub)
print("PFC PB:\n", results.mdl(result_type=ResultTypes.PfcPB).get_data_frame())
print(
    "PFC internal power Vr:\n",
    results.mdl(result_type=ResultTypes.PfcInternalPowerVr_pfc).get_data_frame(),
)
print(
    "PFC internal power Vs:\n",
    results.mdl(result_type=ResultTypes.PfcInternalPowerVs_pfc).get_data_frame(),
)
print(
    "PFC Current Q (A):\n",
    results.mdl(result_type=ResultTypes.PfcCurrentQ).get_data_frame() * Ib * 1000,
)
print(
    "PFC Current R (A):\n",
    results.mdl(result_type=ResultTypes.PfcCurrentR).get_data_frame() * Ib * 1000,
)
print(
    "PFC Current S (A):\n",
    results.mdl(result_type=ResultTypes.PfcCurrentS).get_data_frame() * Ib * 1000,
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

excel_filename = OUT_DIR / "veragrid_case2_timing_results.xlsx"
with pd.ExcelWriter(excel_filename, engine="openpyxl") as writer:
    summary_df.to_excel(writer, sheet_name="Summary", index=False)
    results.get_bus_df().to_excel(writer, sheet_name="Bus_Voltages")
    pd.DataFrame(
        {"Iteration": range(1, iterations + 1), "Elapsed_s": timing_data}
    ).to_excel(writer, sheet_name="Timing_Raw_Data", index=False)

print(f"\nExcel report saved as: {excel_filename}")