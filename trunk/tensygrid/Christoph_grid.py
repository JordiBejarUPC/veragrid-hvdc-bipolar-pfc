import numpy as np
import VeraGridEngine.api as vge
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model

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
    line_mdl.connect([line_mdl.in_vars[0]], [buses[bf].rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[1]], [buses[bf].rms_model.out_vars[1]])
    line_mdl.connect([line_mdl.in_vars[2]], [buses[bt].rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[3]], [buses[bt].rms_model.out_vars[1]])
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
    load_mdl.connect([load_mdl.in_vars[0]], [buses[bus_idx].rms_model.out_vars[0]])
    load_mdl.connect([load_mdl.in_vars[1]], [buses[bus_idx].rms_model.out_vars[1]])

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
gen_mdl.connect([gen_mdl.in_vars[0]], [buses[1].rms_model.out_vars[0]])
gen_mdl.connect([gen_mdl.in_vars[1]], [buses[1].rms_model.out_vars[1]])
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