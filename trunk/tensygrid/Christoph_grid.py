import numpy as np
import VeraGridEngine.api as vge
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
import pandas as  pd
import pickle

# Configuración base extraída de 'global.csv'
Sbase = 100.0
fbase = 50.0

grid = vge.MultiCircuit(Sbase=Sbase, fbase=fbase)

# 1. Creación de Buses (1 al 6 según el Excel)
buses = {}
for i in range(1, 7):
    # El bus 1 es el Slack (ref_bus: 1 en global.csv)
    is_slack = (i == 1)
    bus = vge.Bus(name=f"Bus{i}", Vnom=230, is_slack=is_slack)
    grid.add_bus(bus)
    # Inicialización para modelos RMS
    vge.initialize_bus_phasor_rms(bus, vf=grid.var_factory)
    buses[i] = bus

# 2. Creación de Líneas (Datos de 'AC-NET.csv')
# Estructura: (bus_from, bus_to, R, X, B)
line_data = [
    (1, 2, 0.0100, 0.085, 0.176),
    (1, 3, 0.0170, 0.092, 0.158),
    (2, 4, 0.0320, 0.161, 0.306),
    (3, 6, 0.0390, 0.170, 0.358),
    (4, 5, 0.0085, 0.072, 0.149),
    (5, 6, 0.0119, 0.1008, 0.209)
]

for i, (bf, bt, r, x, b) in enumerate(line_data, 1):
    line = vge.Line(name=f"Line{i}", bus_from=buses[bf], bus_to=buses[bt],
                    r=r, x=x, b=b, rate=900.0)
    grid.add_line(line)

    # Asignar modelo RMS a la línea
    line_mdl = vge.get_line_phasor_rms_template(grid.var_factory).block
    grid.var_factory.add_connections([line_mdl.in_vars[0]], [buses[bf].rms_model.out_vars[0]])
    grid.var_factory.add_connections([line_mdl.in_vars[1]], [buses[bf].rms_model.out_vars[1]])
    grid.var_factory.add_connections([line_mdl.in_vars[2]], [buses[bt].rms_model.out_vars[0]])
    grid.var_factory.add_connections([line_mdl.in_vars[3]], [buses[bt].rms_model.out_vars[1]])
    set_rms_model(device=line, model=line_mdl, var_factory=grid.var_factory)

# 3. Creación de Cargas (Datos de 'load.csv')
# Estructura: (bus, P, Q)
load_data = [
    (2, 1.25, 0.50),
    (3, 0.90, 0.30),
    (5, 1.00, 0.35)
]

for i, (bus_idx, p, q) in enumerate(load_data, 1):
    load = vge.Load(name=f"Load{i}", P=p, Q=q)
    grid.add_load(bus=buses[bus_idx], api_obj=load)

    # Asignar modelo RMS a la carga (modelo de corriente fasorial)
    load_mdl = vge.get_load_phasor_current_rms_template(grid.var_factory).block
    grid.var_factory.add_connections([load_mdl.in_vars[0]], [buses[bus_idx].rms_model.out_vars[0]])
    grid.var_factory.add_connections([load_mdl.in_vars[1]], [buses[bus_idx].rms_model.out_vars[1]])

    # Inicialización de parámetros de corriente (I = S*/V*, aprox V=1)
    #load_mdl.set_parameter_in_model(var_name="Ir0", new_value=-p)
    #load_mdl.set_parameter_in_model(var_name="Ii0", new_value=-q)
    set_rms_model(device=load, model=load_mdl, var_factory=grid.var_factory)

# 4. Creación del Generador (Datos de 'SG.csv')
gen = vge.Generator(
    name="Gen1",
    P=1.63,  # Columna 'P'
    Q=0.07,  # Columna 'Q'
    vset=1.025,  # Columna 'V'
    Snom=310.0,  # Columna 'Sn'
    Sbase=Sbase,
    Rs=0.0025,  # Columna 'Rs'
    Xs=0.2,  # Columna 'Xl' (Reactancia de dispersión)
    freq=fbase,  # 50 Hz
    tpe=vge.GeneratorType.Synchronous
)
grid.add_generator(bus=buses[1], api_obj=gen)

# Asignar modelo RMS al generador
gen_mdl = vge.get_complete_generator_template_phasor(grid.var_factory, name="Gen1").block
grid.var_factory.add_connections([gen_mdl.in_vars[0]], [buses[1].rms_model.out_vars[0]])
grid.var_factory.add_connections([gen_mdl.in_vars[1]], [buses[1].rms_model.out_vars[1]])
set_rms_model(device=gen, model=gen_mdl, var_factory=grid.var_factory)

print("  ✓ Grid created with data from Excel")

# 5. Ejecución del Power Flow
print("\n[2] Running power flow...")
pf_options = vge.PowerFlowOptions()
pf_results = vge.power_flow(grid, pf_options)

vge.save_file(grid, "IEEE_9_Christoph.gridcal")

if pf_results.converged:
    print(f"  ✓ Power flow converged")
    for bus_name, v_complex in zip(grid.get_bus_names(), pf_results.voltage):
        print(f"    {bus_name}: Vm={abs(v_complex):.4f} pu, Angle={np.angle(v_complex, deg=True):.2f}°")
else:
    print("  ✗ Power flow failed")

# Define la ruta a tu archivo de Excel
excel_path = "WSCC_SG_GFOR_GFOL.xlsx"

# 1. Leer las hojas de datos necesarias empleando pandas
df_pf = pd.read_excel(excel_path, sheet_name="PF")
df_ac = pd.read_excel(excel_path, sheet_name="AC-NET")
df_sg = pd.read_excel(excel_path, sheet_name="SG")
df_vsc = pd.read_excel(excel_path, sheet_name="VSC")

# Hojas que podrían estar vacías (con manejo de excepciones defensivo)
try:
    df_dc = pd.read_excel(excel_path, sheet_name="DC-NET")
    n_hvdc = len(df_dc)
    hvdc_names = df_dc["number"].astype(str).values if n_hvdc > 0 else np.array([], dtype=str)
except Exception:
    n_hvdc = 0
    hvdc_names = np.array([], dtype=str)

try:
    df_shunt = pd.read_excel(excel_path, sheet_name="SHUNT")
    n_sh = len(df_shunt)
    sh_names = df_shunt["number"].astype(str).values if n_sh > 0 else np.array([], dtype=str)
except Exception:
    n_sh = 0
    sh_names = np.array([], dtype=str)

# Elementos no presentes en el Excel (inicializados a cero)
n_batt = 0
batt_names = np.array([], dtype=str)

# 2. Extraer dinámicamente los tamaños y nombres
bus_names = df_pf["bus"].astype(str).values
n = len(bus_names)

branch_names = df_ac["number"].astype(str).values
m = len(branch_names)

gen_names = df_sg["number"].astype(str).values
n_gen = len(gen_names)

vsc_names = df_vsc["number"].astype(str).values
n_vsc = len(vsc_names)

# Asignación simple de tipos de barra (puedes adaptarla según tu convención)
bus_types = np.zeros(n, dtype=int)

# 3. Crear el objeto con las dimensiones y vectores reales de tu red
resultados = vge.PowerFlowResults(
    n=n, m=m, n_hvdc=n_hvdc, n_vsc=n_vsc, n_gen=n_gen, n_batt=n_batt, n_sh=n_sh,
    bus_names=bus_names,
    branch_names=branch_names,
    hvdc_names=hvdc_names,
    vsc_names=vsc_names,
    gen_names=gen_names,
    batt_names=batt_names,
    sh_names=sh_names,
    bus_types=bus_types
)

# 4. Inyectar los voltajes complejos calculados (de la pestaña PF)
theta_rad = np.radians(df_pf["theta"].values)
resultados.voltage = df_pf["Vm"].values * np.exp(1j * theta_rad)

# 5. Extraer y asignar datos de generación que también venían en las pestañas
resultados.gen_p = df_sg["P"].values  # Potencia activa del generador síncrono
resultados.gen_q = df_sg["Q"].values  # Potencia reactiva del generador síncrono

# Opcional: Verificar los dataframes generados por tu propia clase
print("Resultados por Barra:")
print(resultados.get_bus_df())

pf_results = resultados
for bus_name, v_complex in zip(grid.get_bus_names(), resultados.voltage):
    print(f"    {bus_name}: Vm={abs(v_complex):.4f} pu, Angle={np.angle(v_complex, deg=True):.2f}°")

with open("Christoph_PF.pkl", "wb") as f:
    pickle.dump(resultados, f)

print("¡Objeto guardado correctamente!")