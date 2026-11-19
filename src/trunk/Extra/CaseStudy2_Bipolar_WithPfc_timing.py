import math
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, ResultTypes

# ==========================================
# 1. TIMING FUNCTION
# ==========================================
def run_timing_test(func, iterations=100):
    """
    Run the power flow function in a loop and collect timing data
    """
    times = np.zeros(iterations)

    for i in range(iterations):
        elapsed = func(verbose=0)
        times[i] = elapsed

    return times


# ==========================================
# 2. PARAMETERS & SYSTEM SETUP
# ==========================================
Ub = 525 # kV
Sb = 100 # MW
Rb = (Ub ** 2) / Sb # Ohms
Ib = (Sb / Ub) # kA

a = 0.5515 / Sb
b = 0.887 * (Ib / Sb)
c = 3.77 * ((Ib**2) / Sb)

dcr_20 = 1.7241 * 1e-8 # ohm*m
A = 2500 * 1e-6 # m
r_ohm_km = (dcr_20 / A) * 1000   # ohm/km
r_ohm = r_ohm_km * 100 # ohm for a 100km line
r = 2 * (r_ohm / Rb) # p.u. for a 100km line

Is_set_A = 1400 / 1000  # kA
Is_set_pu = Is_set_A / Ib


# ==========================================
# 3. BUILD GRID MODEL
# ==========================================
grid = gce.MultiCircuit(
    name="Bipolar_system",
    Sbase=Sb
)

bus1 = gce.Bus(name="Bus1", Vnom=Ub, is_slack=True)
grid.add_bus(bus1)

bus2 = gce.Bus(name="Bus2", Vnom=Ub, is_dc=True)
grid.add_bus(bus2)

bus_r_pos = gce.Bus(name="BusR_Pos", Vnom=Ub, is_dc=True)
grid.add_bus(bus_r_pos)

bus_s_pos = gce.Bus(name="BusS_Pos", Vnom=Ub, is_dc=True)
grid.add_bus(bus_s_pos)

bus3 = gce.Bus(name="Bus3", Vnom=Ub, is_dc=True)
grid.add_bus(bus3)

bus4 = gce.Bus(name="Bus4", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi)
grid.add_bus(bus4)

bus5 = gce.Bus(name="Bus5", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi)
grid.add_bus(bus5)

bus_r_neg = gce.Bus(name="BusR_Neg", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi)
grid.add_bus(bus_r_neg)

bus_s_neg = gce.Bus(name="BusS_Neg", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi)
grid.add_bus(bus_s_neg)

bus6 = gce.Bus(name="Bus6", Vnom=Ub, is_dc=True, is_grounded=True, Vm0=1e-9, Va0=1e-9)
grid.add_bus(bus6)

bus7 = gce.Bus(name="Bus7", Vnom=Ub, is_dc=True, Vm0=1e-9, Va0=1e-9)
grid.add_bus(bus7)

bus8 = gce.Bus(name="Bus8", Vnom=Ub, is_slack=True)
grid.add_bus(bus8)

# Generators
grid.add_generator(bus1, gce.Generator(name='g1', vset=1.0))
grid.add_generator(bus8, gce.Generator(name='g8', vset=1.0))

# DC Lines
grid.add_dc_line(gce.DcLine(name="dc_line_r3_pos", bus_from=bus_r_pos, bus_to=bus3, r=r))
grid.add_dc_line(gce.DcLine(name="dc_line_s3_pos", bus_from=bus_s_pos, bus_to=bus3, r=r))
grid.add_dc_line(gce.DcLine(name="dc_line_r5_neg", bus_from=bus_r_neg, bus_to=bus5, r=r))
grid.add_dc_line(gce.DcLine(name="dc_line_s5_neg", bus_from=bus_s_neg, bus_to=bus5, r=r))
grid.add_dc_line(gce.DcLine(name="dc_line_0", bus_from=bus6, bus_to=bus7, r=r))

# PFC
grid.add_pfc(gce.PFC(name="PFC_pos", bus_dc_q=bus2, bus_dc_r=bus_r_pos, bus_dc_s=bus_s_pos,
                     control1=gce.PfcControlType.Is_pfc, control1_val=Is_set_pu))

grid.add_pfc(gce.PFC(name="PFC_neg", bus_dc_q=bus4, bus_dc_r=bus_r_neg, bus_dc_s=bus_s_neg,
                     control1=gce.PfcControlType.Is_pfc, control1_val=-Is_set_pu))

# VSC
grid.add_vsc(gce.VSC(name="VSC_1", bus_to=bus1, bus_from=bus2, bus_dc_n=bus6, rate=30,
                     alpha1=a, alpha2=b, alpha3=c,
                     control1=ConverterControlType.Vm_dc, control1_val=1.1,
                     control2=ConverterControlType.Qac, control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_2", bus_to=bus1, bus_from=bus4, bus_dc_n=bus6, rate=30,
                     alpha1=a, alpha2=b, alpha3=c,
                     control1=ConverterControlType.Vm_dc, control1_val=-1.1,
                     control2=ConverterControlType.Qac, control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_3", bus_from=bus3, bus_to=bus8, bus_dc_n=bus7,
                     alpha1=a, alpha2=b, alpha3=c,
                     control1=ConverterControlType.Pdc, control2=ConverterControlType.Qac,
                     control1_val=-1000, control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_4", bus_from=bus5, bus_to=bus8, bus_dc_n=bus7,
                     alpha1=a, alpha2=b, alpha3=c,
                     control1=ConverterControlType.Pdc, control2=ConverterControlType.Qac,
                     control1_val=-1000, control2_val=0.0))


# ==========================================
# 4. POWER FLOW WRAPPER & TIMING TEST
# ==========================================
def solve_pf(verbose=0):
    """Wrapper function to execute power flow on the grid and return elapsed time."""
    options_pf = gce.PowerFlowOptions(
        verbose=verbose,
        generate_report=False,  # Disabled during timing to avoid disk/print I/O overhead
        retry_with_other_methods=False,
        tolerance=1e-8,
        use_stored_guess=True
    )
    res = gce.power_flow(grid, options=options_pf)
    return res.elapsed

# Run the timing benchmark (100 iterations)
timing_data = run_timing_test(solve_pf, iterations=100)

print("=== TIMING TEST RESULTS ===")
print(f"Mean Time: {timing_data.mean() * 1000:.3f} ms")
print(f"Std Dev:   {timing_data.std() * 1000:.3f} ms")
print(f"Min Time:  {timing_data.min() * 1000:.3f} ms")
print(f"Max Time:  {timing_data.max() * 1000:.3f} ms\n")


# ==========================================
# 5. SINGLE REPORTING RUN & DETAILED PRINTING
# ==========================================
options_pf = gce.PowerFlowOptions(verbose=1,
                                  generate_report=True,
                                  retry_with_other_methods=False,
                                  tolerance=1e-8,
                                  use_stored_guess=True)
results = gce.power_flow(grid, options=options_pf)

print('Converged:', results.converged, 'error:', results.error)
print("Iterations:", results.iterations)
print("Time (s):", results.elapsed)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())

print(results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame())
print(results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()*Ib*1000)

print(results.mdl(result_type=ResultTypes.VscVdc).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPdc).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscIdc).get_data_frame()*Ib*1000)

# PFC results
print(results.mdl(result_type=ResultTypes.PfcVr).get_data_frame()*Ub)
print(results.mdl(result_type=ResultTypes.PfcVs).get_data_frame()*Ub)
print(results.mdl(result_type=ResultTypes.PfcPB).get_data_frame())
print(results.mdl(result_type=ResultTypes.PfcInternalPowerVr_pfc).get_data_frame())
print(results.mdl(result_type=ResultTypes.PfcInternalPowerVs_pfc).get_data_frame())
print(results.mdl(result_type=ResultTypes.PfcCurrentQ).get_data_frame()*Ib*1000)
print(results.mdl(result_type=ResultTypes.PfcCurrentR).get_data_frame()*Ib*1000)
print(results.mdl(result_type=ResultTypes.PfcCurrentS).get_data_frame()*Ib*1000)