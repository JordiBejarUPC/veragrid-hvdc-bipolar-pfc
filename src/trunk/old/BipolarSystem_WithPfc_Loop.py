import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.enumerations import ResultTypes
import matplotlib.pyplot as plt
import numpy as np

# Params
Ub = 220
Sb = 100
Rb = (Ub ** 2) / Sb

rlin_12 = 0.02
rlin_13 = 0.03
rlin_23 = 0.01

ps_values = np.linspace(0.1, 30, 20)

results_data = {
    "Ps": [],
    "p_line_93": [],
    "p_line_103": [],
    "p_line_0": [],
    "p_line_135": [],
    "p_line_145": [],
}

# Inicialización del contador de convergencia
converged_count = 0
total_cases = len(ps_values)
failed_cases = []

print("Iniciando simulaciones...")

for i in ps_values:
    grid = gce.MultiCircuit(
        name="Bipolar_system",
        Sbase=Sb
    )

    bus1 = gce.Bus(name="Bus1", Vnom=Ub, is_slack=True)
    grid.add_bus(bus1)

    # DC buses
    bus2 = gce.Bus(name="Bus2", Vnom=Ub, is_dc=True)
    grid.add_bus(bus2)

    bus3 = gce.Bus(name="Bus3", Vnom=Ub, is_dc=True)
    grid.add_bus(bus3)

    bus4 = gce.Bus(name="Bus4", Vnom=Ub, is_dc=True, Va0=3.14)
    grid.add_bus(bus4)

    bus5 = gce.Bus(name="Bus5", Vnom=Ub, is_dc=True, Va0=3.14)
    grid.add_bus(bus5)

    bus6 = gce.Bus(name="Bus6", Vnom=Ub, is_dc=True, is_grounded=True, Vm0=0.000000001)
    grid.add_bus(bus6)

    bus7 = gce.Bus(name="Bus7", Vnom=Ub, is_dc=True, Vm0=0.0001)
    grid.add_bus(bus7)

    bus8 = gce.Bus(name="Bus8", Vnom=Ub, is_slack=True)
    grid.add_bus(bus8)

    bus9 = gce.Bus(name="Bus9", Vnom=Ub, is_dc=True)
    grid.add_bus(bus9)

    bus10 = gce.Bus(name="Bus10", Vnom=Ub, is_dc=True)
    grid.add_bus(bus10)

    bus13 = gce.Bus(name="Bus13", Vnom=Ub, is_dc=True, Va0=3.14)
    grid.add_bus(bus13)

    bus14 = gce.Bus(name="Bus14", Vnom=Ub, is_dc=True, Va0=3.14)
    grid.add_bus(bus14)

    # Generators
    grid.add_generator(bus1, gce.Generator(name='g1', vset=1.0))
    grid.add_generator(bus8, gce.Generator(name='g8', vset=1.0))

    # DC_lines
    grid.add_dc_line(gce.DcLine(name="dc_line_93", bus_from=bus9, bus_to=bus3, r=rlin_23 / Rb))
    grid.add_dc_line(gce.DcLine(name="dc_line_103", bus_from=bus10, bus_to=bus3, r=rlin_23 / Rb))
    grid.add_dc_line(gce.DcLine(name="dc_line_0", bus_from=bus6, bus_to=bus7, r=rlin_13 / Rb))
    grid.add_dc_line(gce.DcLine(name="dc_line_135", bus_from=bus13, bus_to=bus5, r=rlin_13 / Rb))
    grid.add_dc_line(gce.DcLine(name="dc_line_145", bus_from=bus14, bus_to=bus5, r=rlin_13 / Rb))

    # PFCs
    grid.add_pfc(gce.PFC(name="PFC_1+", bus_dc_r=bus2, bus_dc_s=bus9, bus_dc_t=bus10, control1=gce.PfcControlType.Ps_dc,
                         control1_val=-i))
    grid.add_pfc(
        gce.PFC(name="PFC_1-", bus_dc_r=bus4, bus_dc_s=bus13, bus_dc_t=bus14, control1=gce.PfcControlType.Ps_dc,
                control1_val=-i))

    # VSCs
    grid.add_vsc(
        gce.VSC(name="VSC_1", bus_from=bus2, bus_to=bus1, bus_dc_n=bus6, alpha1=0.0001, alpha2=0.0001, alpha3=0.0001,
                control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Qac, control1_val=1,
                control2_val=0.0))
    grid.add_vsc(
        gce.VSC(name="VSC_2", bus_from=bus4, bus_to=bus1, bus_dc_n=bus6, alpha1=0.0001, alpha2=0.0001, alpha3=0.0001,
                control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Qac, control1_val=1.01,
                control2_val=0.0))
    grid.add_vsc(
        gce.VSC(name="VSC_3", bus_from=bus3, bus_to=bus8, bus_dc_n=bus7, alpha1=0.0001, alpha2=0.0001, alpha3=0.0001,
                control1=ConverterControlType.Pdc, control2=ConverterControlType.Qac, control1_val=30,
                control2_val=0.0))
    grid.add_vsc(
        gce.VSC(name="VSC_4", bus_from=bus5, bus_to=bus8, bus_dc_n=bus7, alpha1=0.0001, alpha2=0.0001, alpha3=0.0001,
                control1=ConverterControlType.Pdc, control2=ConverterControlType.Qac, control1_val=30,
                control2_val=0.0))

    options_pf = gce.PowerFlowOptions(verbose=0, generate_report=False, retry_with_other_methods=False,
                                      use_stored_guess=True)

    # Ejecutar Power Flow
    results = gce.power_flow(grid, options=options_pf)

    # Comprobar convergencia y extraer datos
    if results.converged:
        converged_count += 1
        branch_df = results.get_branch_df()

        # Guardar la consigna actual
        results_data["Ps"].append(i)

        # Guardar las potencias from (Pf) de las líneas solicitadas
        results_data["p_line_93"].append(branch_df.loc["dc_line_93", "Pf"])
        results_data["p_line_103"].append(branch_df.loc["dc_line_103", "Pf"])
        results_data["p_line_0"].append(branch_df.loc["dc_line_0", "Pf"])
        results_data["p_line_135"].append(branch_df.loc["dc_line_135", "Pf"])
        results_data["p_line_145"].append(branch_df.loc["dc_line_145", "Pf"])
    else:
        failed_cases.append(i)

# ==========================================
# REPORTE DE CONVERGENCIA
# ==========================================
print("\n--- Resultados de Convergencia ---")
print(f"Total de casos: {total_cases}")
print(f"Casos convergidos: {converged_count}")
print(f"Tasa de éxito: {(converged_count / total_cases) * 100:.1f}%")
if failed_cases:
    print(f"Casos fallidos (valores de Ps): {failed_cases}")
print("----------------------------------\n")

# ==========================================
# GENERACIÓN DE GRÁFICOS SEPARADOS
# ==========================================
if converged_count > 0:
    fig, axs = plt.subplots(3, 1, figsize=(10, 12), sharex=True)

    # 1. Gráfico del Polo Positivo
    axs[0].plot(results_data["Ps"], results_data["p_line_93"], color='blue', linestyle='-', marker='o',
                label='Line 93')
    axs[0].plot(results_data["Ps"], results_data["p_line_103"], color='dodgerblue', linestyle='--', marker='^',
                label='Line 103')
    axs[0].set_title('Positive Pole DC Lines')
    axs[0].set_ylabel('Power (P) [MW]')
    axs[0].grid(True, linestyle='--', alpha=0.6)
    axs[0].legend(loc='best')

    # 2. Gráfico del Polo Negativo
    axs[1].plot(results_data["Ps"], results_data["p_line_135"], color='red', linestyle='-', marker='s',
                label='Line 135')
    axs[1].plot(results_data["Ps"], results_data["p_line_145"], color='salmon', linestyle='--', marker='d',
                label='Line 145')
    axs[1].set_title('Negative Pole DC Lines')
    axs[1].set_ylabel('Power (P) [MW]')
    axs[1].grid(True, linestyle='--', alpha=0.6)
    axs[1].legend(loc='best')

    # 3. Gráfico del Retorno Metálico
    axs[2].plot(results_data["Ps"], results_data["p_line_0"], color='green', linestyle='-', linewidth=2, marker='x',
                label='Line 0')
    axs[2].set_title('Metallic Return')
    axs[2].set_xlabel('PFC Set-point Ps [MW]')
    axs[2].set_ylabel('Power (P) [MW]')
    axs[2].grid(True, linestyle='--', alpha=0.6)
    axs[2].legend(loc='best')

    # --> CORRECCIÓN DE ESCALA AQUÍ <--
    # Fijamos los límites de Y para que el ruido numérico se vea plano en 0 MW
    axs[2].set_ylim(-1, 1)

    plt.tight_layout()
    plt.show()
else:
    print("No hay datos para graficar debido a fallos de convergencia en todos los casos.")