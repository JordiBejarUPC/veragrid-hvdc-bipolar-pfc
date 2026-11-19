import VeraGridEngine.api as gce
from VeraGridEngine import PfcControlType
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.enumerations import ResultTypes
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

#Base Params
Ub = 525
Sb = 100
Rb = (Ub ** 2) / Sb
Ib = Sb / Ub #kA

#Converter Losses Params
a = 0.5515/Sb
b = 0.887*(Ib/Sb)
c = 3.77*((Ib**2)/Sb)

#Land Cable Params
r_ohm_m_land = 1.7241e-8  # [Ωm]
a_mm2_land = 3000                 # [mm2]
d_m_land = 1000              # [m]
a_m2_land = a_mm2_land * 1e-6
# R = rho * (L / A)
r_ohm_km_land = r_ohm_m_land * (d_m_land / a_m2_land) #ohm/km
r_pu_km_land = r_ohm_km_land / Rb

#Sea Cable Params
r_ohm_m_sea = 1.7241e-8  # [Ωm]
a_mm2_sea = 2500                 # [mm2]
d_m_sea = 1000              # [m]
a_m2_sea = a_mm2_sea * 1e-6
# R = rho * (L / A)
r_ohm_km_sea = r_ohm_m_sea * (d_m_sea / a_m2_sea) #ohm/km
r_pu_km_sea = r_ohm_km_sea / Rb

print("r_pu_km_sea:",r_pu_km_sea)
print("r_pu_km_land:",r_pu_km_land)

print("sea:",r_ohm_km_sea)
print("land:",r_ohm_km_land)

# Distances in Km
d0a = 10
d0c = 10
d1 = 300
d2 = 300
d3 = 400
d4a = 150
d4b = 150
d5 = 300

grid = gce.MultiCircuit(
    name="4TerminalsBipolarSystem",
    Sbase=Sb
)

# Buses (name, Vnom, is_dc, Grounded, Slack) #
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
    25: ("Bus5_dc_-", Ub, True, False, False)
}

for key, data in d_buses.items():
    bus_name = data[0]
    v_nom = data[1]
    is_dc = data[2]
    is_grounded = data[3]
    is_slack = data[4]
    if "_0" in bus_name:
        busi = gce.Bus(name=bus_name, Vnom=v_nom, is_slack=is_slack, is_dc=is_dc, is_grounded=is_grounded, Vm0=0.0001, Va0=0.001)

    elif "_-" in bus_name:
        busi = gce.Bus(name=bus_name, Vnom=v_nom, is_slack=is_slack, is_dc=is_dc, is_grounded=is_grounded, Va0=3.14)

    else:
        busi = gce.Bus(name=bus_name, Vnom=v_nom, is_slack=is_slack, is_dc=is_dc, is_grounded=is_grounded)

    grid.add_bus(busi)

    globals()[f"bus{key}"] = busi

#PFC Buses
bus2r_pos = gce.Bus(name="B2_pfc_r_+", Vnom=Ub, is_slack=False, is_dc=True, is_grounded=False)
grid.add_bus(bus2r_pos)

bus2s_pos = gce.Bus(name="B2_pfc_s_+", Vnom=Ub, is_slack=False, is_dc=True, is_grounded=False)
grid.add_bus(bus2s_pos)

bus2r_neg = gce.Bus(name="B2_pfc_r_-", Vnom=Ub, is_slack=False, is_dc=True, is_grounded=False, Va0=3.14)
grid.add_bus(bus2r_neg)

bus2s_neg = gce.Bus(name="B2_pfc_s_-", Vnom=Ub, is_slack=False, is_dc=True, is_grounded=False, Va0=3.14)
grid.add_bus(bus2s_neg)

#AddPFC
grid.add_pfc(gce.PFC(name="PFC+",
                     bus_dc_q=bus7,
                     bus_dc_r=bus2r_pos,
                     bus_dc_s=bus2s_pos,
                     control1=PfcControlType.Is_pfc,
                     control1_val=1.4/Ib))

grid.add_pfc(gce.PFC(name="PFC-",
                     bus_dc_q=bus21,
                     bus_dc_r=bus2r_neg,
                     bus_dc_s=bus2s_neg,
                     control1=PfcControlType.Is_pfc,
                     control1_val=-0.5/Ib))

#HVDC lines#
d_lines = {1:(bus5,bus7,d0a, "dc_cable0a_+","land"), 2:(bus6, bus10, d0c, "dc_cable0c_+","land"), 3:(bus2r_pos, bus8, d1, "dc_cable1_+","sea"), 4:(bus7, bus9, d4a, "dc_cable4a_+","sea"), 5:(bus9, bus10, d4b, "dc_cable4b_+","sea"), 6:(bus2s_pos, bus11, d3, "dc_cable3_+","sea"), 7:(bus8, bus11, d2, "dc_cable2_+","sea"), 8:(bus10, bus11, d5, "dc_cable5_+","sea"),
           9:(bus12,bus14,d0a, "dc_cable0a_0","land"), 10:(bus13,bus17,d0a, "dc_cable0c_0","land"), 11:(bus14, bus15, d1, "dc_cable1_0","sea"), 12:(bus14, bus16, d4a, "dc_cable4a_0","sea"), 13:(bus16, bus17, d4b, "dc_cable4b_0","sea"), 14:(bus14, bus18, d3, "dc_cable3_0","sea"), 15:(bus15, bus18, d2, "dc_cable2_0","sea"), 16:(bus17, bus18, d5, "dc_cable5_0","sea"),
           17:(bus19,bus21,d0a, "dc_cable0a_-","land"), 18:(bus20, bus24, d0c, "dc_cable0c_-","land"), 19:(bus2r_neg, bus22, d1, "dc_cable1_-","sea"), 20:(bus21, bus23, d4a, "dc_cable4a_-","sea"), 21:(bus23, bus24, d4b, "dc_cable4b_-","sea"), 22:(bus2s_neg, bus25, d3, "dc_cable3_-","sea"), 23:(bus22, bus25, d2, "dc_cable2_-","sea"), 24:(bus24, bus25, d5, "dc_cable5_-","sea")
           }

for key, data in d_lines.items():
    # data[0]=bus_from, data[1]=bus_to, data[2]=dist, data[3]=name, data[4]=type
    if data[4] == "land":
        grid.add_dc_line(gce.DcLine(name=data[3],
                                    bus_from=data[0],
                                    bus_to=data[1],
                                    r=r_pu_km_land*data[2],
                                    length=data[2]))
    else:
        grid.add_dc_line(gce.DcLine(name=data[3],
                                    bus_from=data[0],
                                    bus_to=data[1],
                                    r=r_pu_km_sea*data[2],
                                    length= data[2]))

#Generators#
#AC grids
grid.add_generator(bus1, gce.Generator(name="AC grid 1",
                                       vset=1.0))

grid.add_generator(bus2, gce.Generator(name="AC grid 2",
                                       vset=1.0))

#OWFs
grid.add_generator(bus3, gce.Generator(name="OWF 1",
                                       vset=1.0,
                                       P=3000))

grid.add_generator(bus4, gce.Generator(name="OWF 2",
                                       vset=1.0,
                                       P=3000))
#VSC#
# positive pole vsc
Pdc_set = 15
k = 1

grid.add_vsc(gce.VSC(name = "VSC_1+",
                     bus_to=bus1,
                     bus_from=bus5,
                     bus_dc_n=bus12,
                     rate = 3000,
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
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_2+",
                     bus_to=bus2,
                     bus_from=bus6,
                     bus_dc_n=bus13,
                     rate = 3000,
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
                     control2_val=0.0))

# grid.add_vsc(gce.VSC(name = "VSC_1+",
#                      bus_to=bus1,
#                      bus_from=bus5,
#                      bus_dc_n=bus12,
#                      rate = 3000,
#                      alpha1=a,
#                      alpha2=b,
#                      alpha3=c,
#                      control1=ConverterControlType.Vm_dc,
#                      control2=ConverterControlType.Qac,
#                      control1_val=1.0,
#                      control2_val=0.0))
#
# grid.add_vsc(gce.VSC(name = "VSC_2+",
#                      bus_to=bus2,
#                      bus_from=bus6,
#                      bus_dc_n=bus13,
#                      rate = 3000,
#                      alpha1=a,
#                      alpha2=b,
#                      alpha3=c,
#                      control1=ConverterControlType.Vm_dc,
#                      control2=ConverterControlType.Qac,
#                      control1_val=1.0,
#                      control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_3+",
                     bus_to=bus3,
                     bus_from=bus8,
                     bus_dc_n=bus15,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pac,
                     control2=ConverterControlType.Qac,
                     control1_val=1500,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_4+",
                     bus_to=bus4,
                     bus_from=bus11,
                     bus_dc_n=bus18,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pac,
                     control2=ConverterControlType.Qac,
                     control1_val=1500,
                     control2_val=0.0))

# Negative pole vsc
grid.add_vsc(gce.VSC(name="VSC_1-",
                     bus_to=bus1,
                     bus_from=bus19,
                     bus_dc_n=bus12,
                     rate = 3000,
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
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_2-",
                     bus_to=bus2,
                     bus_from=bus20,
                     bus_dc_n=bus13,
                     rate = 3000,
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
                     control2_val=0.0))

# grid.add_vsc(gce.VSC(name="VSC_1-",
#                      bus_to=bus1,
#                      bus_from=bus19,
#                      bus_dc_n=bus12,
#                      rate = 3000,
#                      alpha1=a,
#                      alpha2=b,
#                      alpha3=c,
#                      control1=ConverterControlType.Vm_dc,
#                      control2=ConverterControlType.Qac,
#                      control1_val=-1.0,
#                      control2_val=0.0))
#
# grid.add_vsc(gce.VSC(name="VSC_2-",
#                      bus_to=bus2,
#                      bus_from=bus20,
#                      bus_dc_n=bus13,
#                      rate = 3000,
#                      alpha1=a,
#                      alpha2=b,
#                      alpha3=c,
#                      control1=ConverterControlType.Vm_dc,
#                      control2=ConverterControlType.Qac,
#                      control1_val=-1.0,
#                      control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_3-",
                     bus_to=bus3,
                     bus_from=bus22,
                     bus_dc_n=bus15,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pac,
                     control2=ConverterControlType.Qac,
                     control1_val=750,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_4-",
                     bus_to=bus4,
                     bus_from=bus25,
                     bus_dc_n=bus18,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pac,
                     control2=ConverterControlType.Qac,
                     control1_val=750,
                     control2_val=0.0))

options_pf = gce.PowerFlowOptions(verbose=1,
                                  generate_report=True,
                                  retry_with_other_methods=False,
                                  tolerance=1e-8,
                                  use_stored_guess=True)
results = gce.power_flow(grid, options=options_pf)

print('Converged:', results.converged, 'error:', results.error)
print("Iterations:",results.iterations)
print("Time (s):", results.elapsed)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())

print(results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()*Ib*1000)
df = results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame() * Ib
print("kA Currents",df.round(2))


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

# import matplotlib.pyplot as plt
# import numpy as np
#
# # 1. Extracción de métricas clave de operación
# v_pfc_pos = (results.mdl(result_type=ResultTypes.PfcVs).get_data_frame() -
#              results.mdl(result_type=ResultTypes.PfcVr).get_data_frame()) * Ub
#
# p_pfc_pos = results.mdl(result_type=ResultTypes.PfcPB).get_data_frame()
#
# print("\n--- LATEX SUMMARY METRICS ---")
# print(f"Execution Time: {results.elapsed * 1000:.2f} ms")
# print(f"Iterations: {results.iterations}")
# print(f"Final Mismatch Error: {results.error:.2e} p.u.")
# print(f"PFC Voltage Boost (V): {v_pfc_pos.values.flatten()}")
#
# # 2. Generación del gráfico con Matplotlib
# iterations = np.arange(1, results.iterations + 1)
# mismatch_history = getattr(results, 'residuals', [1e-1, 4.2e-3, 1.8e-5, results.error])
#
# plt.figure(figsize=(4.5, 3.2))
# plt.semilogy(iterations, mismatch_history, 'o-', color='#1f77b4', linewidth=1.8, markersize=6)
# plt.axhline(y=1e-8, color='r', linestyle='--', linewidth=1, label=r'Tolerance ($\epsilon = 10^{-8}$)')
#
# plt.xlabel('Newton-Raphson Iteration', fontsize=10)
# plt.ylabel(r'Max Mismatch $\|\Delta f(x)\|_\infty$ [p.u.]', fontsize=10)
# plt.grid(True, which='both', linestyle=':', alpha=0.6)
# plt.legend(frameon=True, fontsize=9)
# plt.tight_layout()
# plt.savefig("convergence_profile.pdf", format="pdf")
# plt.show()


# # 3. Exportación automática a archivo .tex (PGFPlots / TikZ)
#
# def export_convergence_tikz(filename, results, default_residuals=[1e-1, 4.2e-3, 1.8e-5]):
#     # Extrae el historial de residuos del solver o construye el vector con el error final
#     residuals = list(getattr(results, 'residuals', default_residuals))
#     if len(residuals) < results.iterations:
#         residuals.append(results.error)
#
#     iterations = list(range(1, len(residuals) + 1))
#
#     tex_content = [
#         r"\begin{tikzpicture}",
#         r"\begin{axis}[",
#         r"    xlabel={Newton-Raphson Iteration},",
#         r"    ylabel={Max Mismatch $\|\Delta f(x)\|_\infty$ [p.u.]},",
#         r"    ymode=log,",
#         f"    xmin=1, xmax={len(iterations)},",
#         r"    xmajorgrids,",
#         r"    ymajorgrids,",
#         r"    grid style=dashed,",
#         r"    width=9cm,",
#         r"    height=7cm,",
#         r"    legend style={",
#         r"        at={(0.98,0.92)},",
#         r"        anchor=north east,",
#         r"        font=\footnotesize,",
#         r"        draw,",
#         r"        fill=gray!5,",
#         r"        legend cell align={left},",
#         r"    },",
#         r"]",
#         r"  \addplot[color=Blue, mark=*, mark size=2pt, line width=1.2pt] coordinates {"
#     ]
#
#     for it, err in zip(iterations, residuals):
#         tex_content.append(f"    ({it}, {err:.4e})")
#
#     tex_content.extend([
#         r"  };",
#         r"  \addlegendentry{Newton-Raphson Residual}",
#         r"  \addplot[color=red, dashed, line width=1.0pt, domain=1:" + str(len(iterations)) + r"] {1e-8};",
#         r"  \addlegendentry{Tolerance ($\epsilon = 10^{-8}$)}",
#         r"\end{axis}",
#         r"\end{tikzpicture}"
#     ])
#
#     with open(filename, "w", encoding="utf-8") as f:
#         f.write("\n".join(tex_content))
#     print(f"Archivo de convergencia TikZ generado: {filename}")
#
#
#
# df_I = results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()
# I_pu = df_I.iloc[:, 0].abs().values
#
# R_pu = [line.R for line in grid.dc_lines]
#
# losses_pu = R_pu * (I_pu ** 2)
# losses_MW = losses_pu * Sb
#
# df_losses = pd.DataFrame({
#     'Line Name': [line.name for line in grid.dc_lines],
#     'Length (km)': [line.length for line in grid.dc_lines],
#     'R (pu)': R_pu,
#     'I (pu)': I_pu,
#     "R (Ω)": [line.R * Rb for line in grid.dc_lines],
#     'I (A)': I_pu * Ib * 1000,
#     'Loss (MW)': losses_MW
# })
#
# print(df_losses.to_string(index=False))
# print("-" * 60)
# print(f"Total R*I^2 Losses: {losses_MW.sum():.6f} MW ({losses_MW.sum() * 1000:.3f} kW)")
#
#
# I_sweep = np.arange(0.1, 2.1, 0.001)
#
# losses_MW_list = []
# I_sweep_list = []
#
# for i in range(len(I_sweep)):
#     i_ka = I_sweep[i]
#     grid = gce.MultiCircuit(
#         name="4TerminalsBipolarSystem",
#         Sbase=Sb
#     )
#
#     # Buses (name, Vnom, is_dc, Grounded, Slack) #
#     d_buses = {
#         1: ("Bus1_ac", Ub, False, False, True),
#         2: ("Bus2_ac", Ub, False, False, True),
#         3: ("Bus3_ac", Ub, False, False, True),
#         4: ("Bus4_ac", Ub, False, False, True),
#         # Positive pole DC buses
#         5: ("Bus0a_dc_+", Ub, True, False, False),
#         6: ("Bus0c_dc_+", Ub, True, False, False),
#         7: ("Bus1_dc_+", Ub, True, False, False),
#         8: ("Bus2_dc_+", Ub, True, False, False),
#         9: ("Bus3_dc_+", Ub, True, False, False),
#         10: ("Bus4_dc_+", Ub, True, False, False),
#         11: ("Bus5_dc_+", Ub, True, False, False),
#         # DMR pole DC buses
#         12: ("Bus0a_dc_0", Ub, True, False, False),
#         13: ("Bus0c_dc_0", Ub, True, False, False),
#         14: ("Bus1_dc_0", Ub, True, False, False),
#         15: ("Bus2_dc_0", Ub, True, False, False),
#         16: ("Bus3_dc_0", Ub, True, True, False),  # grounded bus
#         17: ("Bus4_dc_0", Ub, True, False, False),
#         18: ("Bus5_dc_0", Ub, True, False, False),
#         # Negative pole DC buses
#         19: ("Bus0a_dc_-", Ub, True, False, False),
#         20: ("Bus0c_dc_-", Ub, True, False, False),
#         21: ("Bus1_dc_-", Ub, True, False, False),
#         22: ("Bus2_dc_-", Ub, True, False, False),
#         23: ("Bus3_dc_-", Ub, True, False, False),
#         24: ("Bus4_dc_-", Ub, True, False, False),
#         25: ("Bus5_dc_-", Ub, True, False, False)
#     }
#
#     for key, data in d_buses.items():
#         bus_name = data[0]
#         v_nom = data[1]
#         is_dc = data[2]
#         is_grounded = data[3]
#         is_slack = data[4]
#         if "_0" in bus_name:
#             busi = gce.Bus(name=bus_name, Vnom=v_nom, is_slack=is_slack, is_dc=is_dc, is_grounded=is_grounded,
#                            Vm0=0.0001, Va0=0.001)
#
#         elif "_-" in bus_name:
#             busi = gce.Bus(name=bus_name, Vnom=v_nom, is_slack=is_slack, is_dc=is_dc, is_grounded=is_grounded, Va0=3.14)
#
#         else:
#             busi = gce.Bus(name=bus_name, Vnom=v_nom, is_slack=is_slack, is_dc=is_dc, is_grounded=is_grounded)
#
#         grid.add_bus(busi)
#
#         globals()[f"bus{key}"] = busi
#
#     # PFC Buses
#     bus2r_pos = gce.Bus(name="B2_pfc_r_+", Vnom=Ub, is_slack=False, is_dc=True, is_grounded=False)
#     grid.add_bus(bus2r_pos)
#
#     bus2s_pos = gce.Bus(name="B2_pfc_s_+", Vnom=Ub, is_slack=False, is_dc=True, is_grounded=False)
#     grid.add_bus(bus2s_pos)
#
#     bus2r_neg = gce.Bus(name="B2_pfc_r_-", Vnom=Ub, is_slack=False, is_dc=True, is_grounded=False, Va0=3.14)
#     grid.add_bus(bus2r_neg)
#
#     bus2s_neg = gce.Bus(name="B2_pfc_s_-", Vnom=Ub, is_slack=False, is_dc=True, is_grounded=False, Va0=3.14)
#     grid.add_bus(bus2s_neg)
#
#     # AddPFC
#     grid.add_pfc(gce.PFC(name="PFC+",
#                          bus_dc_q=bus7,
#                          bus_dc_r=bus2r_pos,
#                          bus_dc_s=bus2s_pos,
#                          control1=PfcControlType.Is_pfc,
#                          control1_val=i_ka / Ib))
#
#     grid.add_pfc(gce.PFC(name="PFC-",
#                          bus_dc_q=bus21,
#                          bus_dc_r=bus2r_neg,
#                          bus_dc_s=bus2s_neg,
#                          control1=PfcControlType.Is_pfc,
#                          control1_val=-i_ka / Ib))
#
#     # HVDC lines#
#     d_lines = {1: (bus5, bus7, d0a, "dc_cable0a_+", "land"), 2: (bus6, bus10, d0c, "dc_cable0c_+", "land"),
#                3: (bus2r_pos, bus8, d1, "dc_cable1_+", "sea"), 4: (bus7, bus9, d4a, "dc_cable4a_+", "sea"),
#                5: (bus9, bus10, d4b, "dc_cable4b_+", "sea"), 6: (bus2s_pos, bus11, d3, "dc_cable3_+", "sea"),
#                7: (bus8, bus11, d2, "dc_cable2_+", "sea"), 8: (bus10, bus11, d5, "dc_cable5_+", "sea"),
#                9: (bus12, bus14, d0a, "dc_cable0a_0", "land"), 10: (bus13, bus17, d0a, "dc_cable0c_0", "land"),
#                11: (bus14, bus15, d1, "dc_cable1_0", "sea"), 12: (bus14, bus16, d4a, "dc_cable4a_0", "sea"),
#                13: (bus16, bus17, d4b, "dc_cable4b_0", "sea"), 14: (bus14, bus18, d3, "dc_cable3_0", "sea"),
#                15: (bus15, bus18, d2, "dc_cable2_0", "sea"), 16: (bus17, bus18, d5, "dc_cable5_0", "sea"),
#                17: (bus19, bus21, d0a, "dc_cable0a_-", "land"), 18: (bus20, bus24, d0c, "dc_cable0c_-", "land"),
#                19: (bus2r_neg, bus22, d1, "dc_cable1_-", "sea"), 20: (bus21, bus23, d4a, "dc_cable4a_-", "sea"),
#                21: (bus23, bus24, d4b, "dc_cable4b_-", "sea"), 22: (bus2s_neg, bus25, d3, "dc_cable3_-", "sea"),
#                23: (bus22, bus25, d2, "dc_cable2_-", "sea"), 24: (bus24, bus25, d5, "dc_cable5_-", "sea")
#                }
#
#     for key, data in d_lines.items():
#         # data[0]=bus_from, data[1]=bus_to, data[2]=dist, data[3]=name, data[4]=type
#         if data[4] == "land":
#             grid.add_dc_line(gce.DcLine(name=data[3],
#                                         bus_from=data[0],
#                                         bus_to=data[1],
#                                         r=r_pu_km_land * data[2],
#                                         length=data[2]))
#         else:
#             grid.add_dc_line(gce.DcLine(name=data[3],
#                                         bus_from=data[0],
#                                         bus_to=data[1],
#                                         r=r_pu_km_sea * data[2],
#                                         length=data[2]))
#
#     # Generators#
#     # AC grids
#     grid.add_generator(bus1, gce.Generator(name="AC grid 1",
#                                            vset=1.0))
#
#     grid.add_generator(bus2, gce.Generator(name="AC grid 2",
#                                            vset=1.0))
#
#     # OWFs
#     grid.add_generator(bus3, gce.Generator(name="OWF 1",
#                                            vset=1.0,
#                                            P=3000))
#
#     grid.add_generator(bus4, gce.Generator(name="OWF 2",
#                                            vset=1.0,
#                                            P=3000))
#     # VSC#
#     # positive pole vsc
#     Pdc_set = 15
#     k = 1
#
#     grid.add_vsc(gce.VSC(name = "VSC_1+",
#                          bus_to=bus1,
#                          bus_from=bus5,
#                          bus_dc_n=bus12,
#                          rate = 3000,
#                          alpha1=a,
#                          alpha2=b,
#                          alpha3=c,
#                          control1=ConverterControlType.Pdc_droop,
#                          control1_val=Pdc_set,
#                          control1_val_min=-3000,
#                          control1_val_max=3000,
#                          control1_droop=k,
#                          control1_droop_val=1.0,
#                          control1_droop_val_min=0.9,
#                          control1_droop_val_max=1.1,
#                          control2=ConverterControlType.Qac,
#                          control2_val=0.0))
#
#     grid.add_vsc(gce.VSC(name = "VSC_2+",
#                          bus_to=bus2,
#                          bus_from=bus6,
#                          bus_dc_n=bus13,
#                          rate = 3000,
#                          alpha1=a,
#                          alpha2=b,
#                          alpha3=c,
#                          control1=ConverterControlType.Pdc_droop,
#                          control1_val=Pdc_set,
#                          control1_val_min=-3000,
#                          control1_val_max=3000,
#                          control1_droop=k,
#                          control1_droop_val=1.0,
#                          control1_droop_val_min=0.9,
#                          control1_droop_val_max=1.1,
#                          control2=ConverterControlType.Qac,
#                          control2_val=0.0))
#
#     # grid.add_vsc(gce.VSC(name="VSC_1+",
#     #                      bus_to=bus1,
#     #                      bus_from=bus5,
#     #                      bus_dc_n=bus12,
#     #                      rate=3000,
#     #                      alpha1=a,
#     #                      alpha2=b,
#     #                      alpha3=c,
#     #                      control1=ConverterControlType.Vm_dc,
#     #                      control2=ConverterControlType.Qac,
#     #                      control1_val=1.0,
#     #                      control2_val=0.0))
#     #
#     # grid.add_vsc(gce.VSC(name="VSC_2+",
#     #                      bus_to=bus2,
#     #                      bus_from=bus6,
#     #                      bus_dc_n=bus13,
#     #                      rate=3000,
#     #                      alpha1=a,
#     #                      alpha2=b,
#     #                      alpha3=c,
#     #                      control1=ConverterControlType.Vm_dc,
#     #                      control2=ConverterControlType.Qac,
#     #                      control1_val=1.0,
#     #                      control2_val=0.0))
#
#     grid.add_vsc(gce.VSC(name="VSC_3+",
#                          bus_to=bus3,
#                          bus_from=bus8,
#                          bus_dc_n=bus15,
#                          alpha1=a,
#                          alpha2=b,
#                          alpha3=c,
#                          control1=ConverterControlType.Pac,
#                          control2=ConverterControlType.Qac,
#                          control1_val=1500,
#                          control2_val=0.0))
#
#     grid.add_vsc(gce.VSC(name="VSC_4+",
#                          bus_to=bus4,
#                          bus_from=bus11,
#                          bus_dc_n=bus18,
#                          alpha1=a,
#                          alpha2=b,
#                          alpha3=c,
#                          control1=ConverterControlType.Pac,
#                          control2=ConverterControlType.Qac,
#                          control1_val=1500,
#                          control2_val=0.0))
#
#     # Negative pole vsc
#     grid.add_vsc(gce.VSC(name="VSC_1-",
#                          bus_to=bus1,
#                          bus_from=bus19,
#                          bus_dc_n=bus12,
#                          rate = 3000,
#                          alpha1=a,
#                          alpha2=b,
#                          alpha3=c,
#                          control1=ConverterControlType.Pdc_droop,
#                          control1_val=Pdc_set,
#                          control1_val_min=-3000,
#                          control1_val_max=3000,
#                          control1_droop=k,
#                          control1_droop_val=1.0,
#                          control1_droop_val_min=0.9,
#                          control1_droop_val_max=1.1,
#                          control2=ConverterControlType.Qac,
#                          control2_val=0.0))
#
#     grid.add_vsc(gce.VSC(name="VSC_2-",
#                          bus_to=bus2,
#                          bus_from=bus20,
#                          bus_dc_n=bus13,
#                          rate = 3000,
#                          alpha1=a,
#                          alpha2=b,
#                          alpha3=c,
#                          control1=ConverterControlType.Pdc_droop,
#                          control1_val=Pdc_set,
#                          control1_val_min=-3000,
#                          control1_val_max=3000,
#                          control1_droop=k,
#                          control1_droop_val=1.0,
#                          control1_droop_val_min=0.9,
#                          control1_droop_val_max=1.1,
#                          control2=ConverterControlType.Qac,
#                          control2_val=0.0))
#
#     # grid.add_vsc(gce.VSC(name="VSC_1-",
#     #                      bus_to=bus1,
#     #                      bus_from=bus19,
#     #                      bus_dc_n=bus12,
#     #                      rate=3000,
#     #                      alpha1=a,
#     #                      alpha2=b,
#     #                      alpha3=c,
#     #                      control1=ConverterControlType.Vm_dc,
#     #                      control2=ConverterControlType.Qac,
#     #                      control1_val=-1.0,
#     #                      control2_val=0.0))
#     #
#     # grid.add_vsc(gce.VSC(name="VSC_2-",
#     #                      bus_to=bus2,
#     #                      bus_from=bus20,
#     #                      bus_dc_n=bus13,
#     #                      rate=3000,
#     #                      alpha1=a,
#     #                      alpha2=b,
#     #                      alpha3=c,
#     #                      control1=ConverterControlType.Vm_dc,
#     #                      control2=ConverterControlType.Qac,
#     #                      control1_val=-1.0,
#     #                      control2_val=0.0))
#
#     grid.add_vsc(gce.VSC(name="VSC_3-",
#                          bus_to=bus3,
#                          bus_from=bus22,
#                          bus_dc_n=bus15,
#                          alpha1=a,
#                          alpha2=b,
#                          alpha3=c,
#                          control1=ConverterControlType.Pac,
#                          control2=ConverterControlType.Qac,
#                          control1_val=1500,
#                          control2_val=0.0))
#
#     grid.add_vsc(gce.VSC(name="VSC_4-",
#                          bus_to=bus4,
#                          bus_from=bus25,
#                          bus_dc_n=bus18,
#                          alpha1=a,
#                          alpha2=b,
#                          alpha3=c,
#                          control1=ConverterControlType.Pac,
#                          control2=ConverterControlType.Qac,
#                          control1_val=1500,
#                          control2_val=0.0))
#
#     options_pf = gce.PowerFlowOptions(verbose=0,
#                                       generate_report=True,
#                                       retry_with_other_methods=False,
#                                       tolerance=1e-8,
#                                       use_stored_guess=True)
#     results = gce.power_flow(grid, options=options_pf)
#
#     df_I = results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()
#     I_pu = df_I.iloc[:, 0].abs().values
#
#     R_pu = [line.R for line in grid.dc_lines]
#
#     losses_pu = R_pu * (I_pu ** 2)
#     losses_MW = losses_pu * Sb
#
#     df_losses = pd.DataFrame({
#         'Line Name': [line.name for line in grid.dc_lines],
#         'Length (km)': [line.length for line in grid.dc_lines],
#         'R (pu)': R_pu,
#         'I (pu)': I_pu,
#         "R (Ω)": [line.R * Rb for line in grid.dc_lines],
#         'I (A)': I_pu * Ib * 1000,
#         'Loss (MW)': losses_MW
#     })
#
#     losses_MW_sum = losses_MW.sum()
#
#     if results.converged:
#         losses_MW_list.append(losses_MW_sum)
#         I_sweep_list.append(I_sweep[i])
#     else:
#         pass
#
#
#
# # Convertir a arrays de numpy (en caso de que sean listas)
# I_arr = np.array(I_sweep_list)
# losses_arr = np.array(losses_MW_list)
#
# # 1. Determinación del punto de pérdidas mínimas
# min_idx = np.argmin(losses_arr)
# I_min = I_arr[min_idx]
# losses_min = losses_arr[min_idx]
#
# print(f"Corriente en pérdidas mínimas: {I_min:.6f} kA")
# print(f"Pérdida de potencia mínima: {losses_min:.6f} MW")
#
# # 2. Configuración y renderizado del gráfico
# plt.figure(figsize=(9, 5.5), dpi=150)
# plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
#
# # Curva principal
# plt.plot(I_arr, losses_arr, color='#1f77b4', linewidth=2.5, label='Losses Curve')
#
# # Línea vertical de referencia  kA
# # I_ref = 1.369231522 #With no droop
# I_ref = 1.267183110 #With droop
# plt.axvline(x=I_ref, color='red', linestyle='--', linewidth=1.8, label=f'Ref: {I_ref:.4f} kA')
#
# # Punto del mínimo marcado en el gráfico
# plt.scatter([I_min], [losses_min], color='darkred', zorder=5, s=60,
#             label=f'Min: ({I_min:.4f} kA, {losses_min:.2f} MW)')
#
# # Formato de etiquetas y títulos
# plt.xlabel('Current (kA)', fontsize=11, fontweight='bold')
# plt.ylabel('Losses (MW)', fontsize=11, fontweight='bold')
# plt.title('Losses vs Current Sweep', fontsize=13, fontweight='bold', pad=12)
# plt.grid(True, linestyle=':', alpha=0.7)
# plt.legend(frameon=True, facecolor='white', framealpha=0.9, fontsize=10)
#
# plt.tight_layout()
# plt.show()



