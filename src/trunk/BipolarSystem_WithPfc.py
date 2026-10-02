import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.enumerations import ResultTypes
import math
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

#Params
Ub = 525 #kV
Sb = 100 #MW
Rb = (Ub ** 2) / Sb #Ohms
Ib = (Sb / Ub) #kA

a = 0.5515/Sb
b = 0.887*(Ib/Sb)
c = 3.77*((Ib**2)/Sb)


dcr_20 = 1.7241*1e-8 #ohm*m
A = 2500*1e-6 #m
r_ohm_km =  (dcr_20/A)*1000   # ohm/km (Extracted from https://cse.cigre.org/cse-n032/enhanced-real-time-multi-terminal-hvdc-power-system-benchmark-models-with-performance-evaluation-strategies.pdf?tx_site_pdfdownload%5BaccessToken%5D=dummyToken&tx_site_pdfdownload%5Baction%5D=download&tx_site_pdfdownload%5Bcontroller%5D=Pdf&tx_site_pdfdownload%5BpdfProject%5D=11954&cHash=1af3d0cbb45897c40b04a67731cbd063)
r_ohm = r_ohm_km*100 # ohm for a 100km line
r = 2*(r_ohm/Rb) #p.u. for a 100km line

Is_set_A = 1400/1000  #kA
Is_set_pu = Is_set_A / Ib


grid = gce.MultiCircuit(
    name="Bipolar_system",
    Sbase=Sb
)

bus1 = gce.Bus(name = "Bus1",
               Vnom = Ub,
               is_slack=True)
grid.add_bus(bus1)

#DC buses
bus2 = gce.Bus(name = "Bus2",
               Vnom=Ub,
               is_dc=True)
grid.add_bus(bus2)

bus_r_pos = gce.Bus(name = "BusR_Pos",
                    Vnom=Ub,
                    is_dc=True)
grid.add_bus(bus_r_pos)

bus_s_pos = gce.Bus(name = "BusS_Pos",
                    Vnom=Ub,
                    is_dc=True)
grid.add_bus(bus_s_pos)


bus3 = gce.Bus(name = "Bus3",
               Vnom=Ub,
               is_dc=True)
grid.add_bus(bus3)

bus4 = gce.Bus(name = "Bus4",
               Vnom=Ub,
               is_dc=True,
               Vm0=1.0,
               Va0=math.pi)
grid.add_bus(bus4)

bus5 = gce.Bus(name = "Bus5",
               Vnom=Ub,
               is_dc=True,
               Vm0=1.0,
               Va0=math.pi)
grid.add_bus(bus5)

bus_r_neg = gce.Bus(name = "BusR_Neg",
                    Vnom=Ub,
                    is_dc=True,
                    Vm0=1.0,
                    Va0=math.pi)
grid.add_bus(bus_r_neg)

bus_s_neg = gce.Bus(name = "BusS_Neg",
                    Vnom=Ub,
                    is_dc=True,
                    Vm0=1.0,
                    Va0=math.pi)
grid.add_bus(bus_s_neg)

bus6 = gce.Bus(name = "Bus6",
               Vnom=Ub,
               is_dc=True,
               is_grounded=True,
               Vm0=0.000000001,
               Va0=0.000000001)
grid.add_bus(bus6)

bus7 = gce.Bus(name = "Bus7",
               Vnom=Ub,
               is_dc=True,
               Vm0=0.000000001,
               Va0=0.000000001)
grid.add_bus(bus7)

bus8 = gce.Bus(name = "Bus8",
               Vnom=Ub,
               is_slack=True)
grid.add_bus(bus8)

#Generators
grid.add_generator(bus1, gce.Generator(name='g1',
                                       vset=1.0))

grid.add_generator(bus8, gce.Generator(name='g8',
                                       vset=1))


#DC_lines
# grid.add_dc_line(gce.DcLine(name = "dc_line_23",
#                             bus_from=bus2,
#                             bus_to=bus3,
#                             r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_r3_pos",
                            bus_from=bus_r_pos,
                            bus_to=bus3,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_s3_pos",
                            bus_from=bus_s_pos,
                            bus_to=bus3,
                            r=r))

# grid.add_dc_line(gce.DcLine(name = "dc_line_45",
#                             bus_from=bus4,
#                             bus_to=bus5,
#                             r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_r5_neg",
                            bus_from=bus_r_neg,
                            bus_to=bus5,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_s5_neg",
                            bus_from=bus_s_neg,
                            bus_to=bus5,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_0",
                            bus_from=bus6,
                            bus_to=bus7,
                            r=r))

#PFC
grid.add_pfc(gce.PFC(name = "PFC_pos",
                     bus_dc_q = bus2,
                     bus_dc_r = bus_r_pos,
                     bus_dc_s = bus_s_pos,
                     control1 = gce.PfcControlType.Is_pfc,
                     control1_val= Is_set_pu))

grid.add_pfc(gce.PFC(name = "PFC_neg",
                     bus_dc_q = bus4,
                     bus_dc_r = bus_r_neg,
                     bus_dc_s = bus_s_neg,
                     control1 = gce.PfcControlType.Is_pfc,
                     control1_val= -Is_set_pu))
#VSC
grid.add_vsc(gce.VSC(name="VSC_1",
                     bus_to=bus1,
                     bus_from=bus2,
                     bus_dc_n=bus6,
                     rate = 30,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_dc,
                     control1_val=1.1,
                     control2=ConverterControlType.Qac,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_2",
                     bus_to=bus1,
                     bus_from=bus4,
                     bus_dc_n=bus6,
                     rate = 30,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_dc,
                     control1_val=-1.1,
                     control2=ConverterControlType.Qac,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_3",
                     bus_from=bus3,
                     bus_to=bus8,
                     bus_dc_n=bus7,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pdc,
                     control2=ConverterControlType.Qac,
                     control1_val=-1000,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_4",
                     bus_from=bus5,
                     bus_to=bus8,
                     bus_dc_n=bus7,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pdc,
                     control2=ConverterControlType.Qac,
                     control1_val=-1000,
                     control2_val=0.0))

options_pf = gce.PowerFlowOptions(verbose=1,
                                  generate_report=True,
                                  retry_with_other_methods=False,
                                  tolerance=1e-8,
                                  use_stored_guess=True)
results = gce.power_flow(grid, options=options_pf)

#gce.save_file(grid=grid, filename="old/BipolarSystem_Times.veragrid")

print('Converged:', results.converged, 'error:', results.error)
print("Iterations:",results.iterations)
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

#PFC results
print(results.mdl(result_type=ResultTypes.PfcVr).get_data_frame()*Ub)
print(results.mdl(result_type=ResultTypes.PfcVs).get_data_frame()*Ub)

print(results.mdl(result_type=ResultTypes.PfcPB).get_data_frame())

print(results.mdl(result_type=ResultTypes.PfcInternalPowerVr_pfc).get_data_frame())

print(results.mdl(result_type=ResultTypes.PfcInternalPowerVs_pfc).get_data_frame())

print(results.mdl(result_type=ResultTypes.PfcCurrentQ).get_data_frame()*Ib*1000)
print(results.mdl(result_type=ResultTypes.PfcCurrentR).get_data_frame()*Ib*1000)
print(results.mdl(result_type=ResultTypes.PfcCurrentS).get_data_frame()*Ib*1000)


# def create_grid(is_set_pu):
#     grid = gce.MultiCircuit(name="Bipolar_system", Sbase=Sb)
#
#     bus1 = gce.Bus(name="Bus1", Vnom=Ub, is_slack=True)
#     grid.add_bus(bus1)
#
#     bus2 = gce.Bus(name="Bus2", Vnom=Ub, is_dc=True)
#     grid.add_bus(bus2)
#
#     bus_r_pos = gce.Bus(name="BusR_Pos", Vnom=Ub, is_dc=True)
#     grid.add_bus(bus_r_pos)
#
#     bus_s_pos = gce.Bus(name="BusS_Pos", Vnom=Ub, is_dc=True)
#     grid.add_bus(bus_s_pos)
#
#     bus3 = gce.Bus(name="Bus3", Vnom=Ub, is_dc=True)
#     grid.add_bus(bus3)
#
#     bus4 = gce.Bus(
#         name="Bus4", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi
#     )
#     grid.add_bus(bus4)
#
#     bus5 = gce.Bus(
#         name="Bus5", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi
#     )
#     grid.add_bus(bus5)
#
#     bus_r_neg = gce.Bus(
#         name="BusR_Neg", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi
#     )
#     grid.add_bus(bus_r_neg)
#
#     bus_s_neg = gce.Bus(
#         name="BusS_Neg", Vnom=Ub, is_dc=True, Vm0=1.0, Va0=math.pi
#     )
#     grid.add_bus(bus_s_neg)
#
#     bus6 = gce.Bus(
#         name="Bus6",
#         Vnom=Ub,
#         is_dc=True,
#         is_grounded=True,
#         Vm0=1e-9,
#         Va0=1e-9,
#     )
#     grid.add_bus(bus6)
#
#     bus7 = gce.Bus(
#         name="Bus7", Vnom=Ub, is_dc=True, Vm0=1e-9, Va0=1e-9
#     )
#     grid.add_bus(bus7)
#
#     bus8 = gce.Bus(name="Bus8", Vnom=Ub, is_slack=True)
#     grid.add_bus(bus8)
#
#     grid.add_generator(bus1, gce.Generator(name="g1", vset=1.0))
#     grid.add_generator(bus8, gce.Generator(name="g8", vset=1.0))
#
#     grid.add_dc_line(
#         gce.DcLine(name="dc_line_r3_pos", bus_from=bus_r_pos, bus_to=bus3, r=r)
#     )
#     grid.add_dc_line(
#         gce.DcLine(name="dc_line_s3_pos", bus_from=bus_s_pos, bus_to=bus3, r=r)
#     )
#     grid.add_dc_line(
#         gce.DcLine(name="dc_line_r5_neg", bus_from=bus_r_neg, bus_to=bus5, r=r)
#     )
#     grid.add_dc_line(
#         gce.DcLine(name="dc_line_s5_neg", bus_from=bus_s_neg, bus_to=bus5, r=r)
#     )
#     grid.add_dc_line(
#         gce.DcLine(name="dc_line_0", bus_from=bus6, bus_to=bus7, r=r)
#     )
#
#     grid.add_pfc(
#         gce.PFC(
#             name="PFC_pos",
#             bus_dc_q=bus2,
#             bus_dc_r=bus_r_pos,
#             bus_dc_s=bus_s_pos,
#             control1=gce.PfcControlType.Is_pfc,
#             control1_val=is_set_pu,
#         )
#     )
#
#     grid.add_pfc(
#         gce.PFC(
#             name="PFC_neg",
#             bus_dc_q=bus4,
#             bus_dc_r=bus_r_neg,
#             bus_dc_s=bus_s_neg,
#             control1=gce.PfcControlType.Is_pfc,
#             control1_val=-is_set_pu,
#         )
#     )
#
#     grid.add_vsc(
#         gce.VSC(
#             name="VSC_1",
#             bus_to=bus1,
#             bus_from=bus2,
#             bus_dc_n=bus6,
#             rate=30,
#             alpha1=a,
#             alpha2=b,
#             alpha3=c,
#             control1=ConverterControlType.Vm_dc,
#             control1_val=1.1,
#             control2=ConverterControlType.Qac,
#             control2_val=0.0,
#         )
#     )
#
#     grid.add_vsc(
#         gce.VSC(
#             name="VSC_2",
#             bus_to=bus1,
#             bus_from=bus4,
#             bus_dc_n=bus6,
#             rate=30,
#             alpha1=a,
#             alpha2=b,
#             alpha3=c,
#             control1=ConverterControlType.Vm_dc,
#             control1_val=-1.1,
#             control2=ConverterControlType.Qac,
#             control2_val=0.0,
#         )
#     )
#
#     grid.add_vsc(
#         gce.VSC(
#             name="VSC_3",
#             bus_from=bus3,
#             bus_to=bus8,
#             bus_dc_n=bus7,
#             alpha1=a,
#             alpha2=b,
#             alpha3=c,
#             control1=ConverterControlType.Pdc,
#             control2=ConverterControlType.Qac,
#             control1_val=-1000,
#             control2_val=0.0,
#         )
#     )
#
#     grid.add_vsc(
#         gce.VSC(
#             name="VSC_4",
#             bus_from=bus5,
#             bus_to=bus8,
#             bus_dc_n=bus7,
#             alpha1=a,
#             alpha2=b,
#             alpha3=c,
#             control1=ConverterControlType.Pdc,
#             control2=ConverterControlType.Qac,
#             control1_val=-1000,
#             control2_val=0.0,
#         )
#     )
#
#     return grid
#
#
# options_pf = gce.PowerFlowOptions(
#     verbose=0,
#     generate_report=False,
#     retry_with_other_methods=False,
#     tolerance=1e-8,
#     use_stored_guess=True,
# )
#
#
# # Current rank 0.01 A to 1730 A
# i_control_A = np.linspace(0.01, 1730.0, 150)
#
# vr_pos_kV = []
# vs_pos_kV = []
# i_valid_A = []
#
# options_pf = gce.PowerFlowOptions(
#     verbose=0,
#     generate_report=False,
#     retry_with_other_methods=False,
#     tolerance=1e-8,
#     use_stored_guess=True,
# )
#
# # Current sweep array
# i_control_A = np.linspace(0.01, 1730.0, 150)
#
# i_valid_A = []
# total_losses_MW = []
# vr_pos_kV = []
# vs_pos_kV = []
#
# for i_A in i_control_A:
#     i_pu = (i_A / 1000.0) / Ib
#     grid = create_grid(i_pu)
#     results = gce.power_flow(grid, options=options_pf)
#
#     if results.converged:
#         # Extract branch active currents (p.u.)
#         i_lines_pu = results.mdl(
#             ResultTypes.BranchActiveCurrentFrom
#         ).get_data_frame()
#
#         # Calculate P = sum(R * I^2) for all lines in MW
#         losses_pu = (r * (i_lines_pu.iloc[:, 0] ** 2)).sum()
#         losses_MW = losses_pu * Sb
#
#         # Extract PFC voltages to locate Vr = Vs = 0
#         vr_val = (
#             results.mdl(ResultTypes.PfcVr)
#             .get_data_frame()
#             .loc["PFC_pos"]
#             .iloc[0]
#             * Ub
#         )
#         vs_val = (
#             results.mdl(ResultTypes.PfcVs)
#             .get_data_frame()
#             .loc["PFC_pos"]
#             .iloc[0]
#             * Ub
#         )
#
#         i_valid_A.append(i_A)
#         total_losses_MW.append(losses_MW)
#         vr_pos_kV.append(vr_val)
#         vs_pos_kV.append(vs_val)
#
# # Find point where |Vr| + |Vs| is closest to 0
# zero_idx = np.argmin(np.abs(vr_pos_kV) + np.abs(vs_pos_kV))
# i_zero = i_valid_A[zero_idx]
# loss_zero = total_losses_MW[zero_idx]
#
# # --- Plotting ---
# plt.figure(figsize=(8.5, 5.2))
# plt.plot(
#     i_valid_A,
#     total_losses_MW,
#     label=r"Total Line Losses ($P = \sum R I^2$)",
#     color="navy",
#     linewidth=2,
# )
#
# # Highlight Vr = Vs = 0 point with a red dot
# plt.plot(
#     i_zero,
#     loss_zero,
#     "ro",
#     markersize=8,
#     zorder=5,
#     label=f"$V_r = V_s = 0$ kV ($I_s = {i_zero:.1f}$ A)",
# )
#
# plt.axvline(x=i_zero, color="red", linestyle=":", alpha=0.6)
# plt.xlabel("Controlled Line Current $I_s$ [A]", fontsize=11)
# plt.ylabel("Total Line Losses [MW]", fontsize=11)
# plt.title(
#     "Total DC Line Losses vs. PFC Controlled Current ($I_s$)",
#     fontsize=12,
#     pad=10,
# )
# plt.grid(True, linestyle=":", alpha=0.6)
# plt.legend(loc="best")
# plt.tight_layout()
#
# plt.show()
#
# # Current sweep array
# i_control_A = np.linspace(0.01, 1730.0, 150)
#
# i_valid_A = []
# total_losses_MW = []
# vr_pos_kV = []
# vs_pos_kV = []
#
# for i_A in i_control_A:
#     i_pu = (i_A / 1000.0) / Ib
#     grid = create_grid(i_pu)
#     results = gce.power_flow(grid, options=options_pf)
#
#     if results.converged:
#         # Extract branch active currents (p.u.)
#         i_lines_pu = results.mdl(
#             ResultTypes.BranchActiveCurrentFrom
#         ).get_data_frame()
#
#         # Calculate P = sum(R * I^2) for all lines in MW
#         losses_pu = (r_pu * (i_lines_pu.iloc[:, 0] ** 2)).sum()
#         losses_MW = losses_pu * Sb
#
#         # Extract PFC voltages to locate Vr = Vs = 0
#         vr_val = (
#             results.mdl(ResultTypes.PfcVr)
#             .get_data_frame()
#             .loc["PFC_pos"]
#             .iloc[0]
#             * Ub
#         )
#         vs_val = (
#             results.mdl(ResultTypes.PfcVs)
#             .get_data_frame()
#             .loc["PFC_pos"]
#             .iloc[0]
#             * Ub
#         )
#
#         i_valid_A.append(i_A)
#         total_losses_MW.append(losses_MW)
#         vr_pos_kV.append(vr_val)
#         vs_pos_kV.append(vs_val)
#
# # Find point where |Vr| + |Vs| is closest to 0
# zero_idx = np.argmin(np.abs(vr_pos_kV) + np.abs(vs_pos_kV))
# i_zero = i_valid_A[zero_idx]
# loss_zero = total_losses_MW[zero_idx]
#
# # --- Plotting ---
# plt.figure(figsize=(8.5, 5.2))
# plt.plot(
#     i_valid_A,
#     total_losses_MW,
#     label=r"Total Line Losses ($P = \sum R I^2$)",
#     color="navy",
#     linewidth=2,
# )
#
# # Highlight Vr = Vs = 0 point with a red dot
# plt.plot(
#     i_zero,
#     loss_zero,
#     "ro",
#     markersize=8,
#     zorder=5,
#     label=f"$V_r = V_s = 0$ kV ($I_s = {i_zero:.1f}$ A)",
# )
#
# plt.axvline(x=i_zero, color="red", linestyle=":", alpha=0.6)
# plt.xlabel("Controlled Line Current $I_s$ [A]", fontsize=11)
# plt.ylabel("Total Line Losses [MW]", fontsize=11)
# plt.title(
#     "Total DC Line Losses vs. PFC Controlled Current ($I_s$)",
#     fontsize=12,
#     pad=10,
# )
# plt.grid(True, linestyle=":", alpha=0.6)
# plt.legend(loc="best")
# plt.tight_layout()
#
# plt.show()
#
# # Save to CSV
# # df_pfc_results.to_csv("pfc_voltages_vs_current.csv", index=False)


