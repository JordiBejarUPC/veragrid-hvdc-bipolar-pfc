# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import pandas as pd

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGrid.trunk.dynamics_emt.support.plot_emt_results import plot_ilines, plot_generators, plot_isource, plot_voltages, plot_v_i, plot_itrafo
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver

from VeraGridEngine import WindingType
from VeraGridEngine import ShuntConnectionType


import VeraGridEngine.api as gce
np.set_printoptions(
            precision=10,  # number of digits
            suppress=False,  # DO NOT suppress scientific notation
            formatter={'float_kind': lambda x: f"{x: .3e}"}
        )


grid = MultiCircuit()

Sbase  =160 #MVA
# Vbase = 15/np.sqrt(3)
Vbase = 15 #kV
Zbase = Vbase*Vbase/(Sbase*1e3) # kV*kV / kVA = ohm
Rbase = Zbase.real  # ohm
f = 50 # Hz

grid.Sbase = Sbase #*1e6 # MVA

bus1 = Bus(name="Bus1", Vnom=Vbase, is_slack= True)
bus1.ph_n = False; bus1.ph_a = True; bus1.ph_b = True; bus1.ph_c = True

V2 = Vbase/2
bus2 = Bus(name="Bus2", Vnom=V2)
bus2.ph_n = False; bus2.ph_a = True; bus2.ph_b = True; bus2.ph_c = True

bus1_template = get_bus_emt_template(grid.var_factory)
bus1.emt_model = bus1_template.block
bus2_template = get_bus_emt_template(grid.var_factory)
bus2.emt_model = bus2_template.block

# trafo0 = Transformer2W(name="trafo 1-2", bus_from=bus1, bus_to=bus2, X_leack= 0.1, X_magn=100, R_leack= 0.01, R_magn=100, rate = 300)
# trafo0 = Transformer2W(name="trafo 1-2",
#                        bus_from=bus1,
#                        bus_to=bus2,
#                        HV = Vbase,
#                        LV = V2,
#                        nominal_power= 160,
#                        r = 0.01,
#                        x = 0.1,
#                        # g= 100,
#                        # b = 200,
#                        X_leack= 0.1, X_magn=100, R_leack= 0.01, R_magn=100, rate = 160)
trafo0 = Transformer2W(name="trafo 1-2",
                       bus_from=bus1,
                       bus_to=bus2,
                       HV = Vbase,
                       LV = V2,
                       nominal_power= 160,
                       r = 0.0,
                       x = 0.1,
                       # g= 100,
                       # b = 200,
                       X_leack= 0.1, X_magn=10000, R_leack= 0.0, R_magn=0.0, rate = 160)
trafo0.conn_f = WindingType.GroundedStar
trafo0.conn_t = WindingType.GroundedStar

gen1 = Generator(name="Gen1",freq = 50, Snom=grid.Sbase, vset=1.0 )
gen1_template = get_simple_generator_emt_template()
gen1.emt_model = gen1_template.block

gen1_mdl = gen1.emt_model
bus1_mdl = bus1.emt_model
gen1_mdl.connect(gen1_mdl.in_vars, bus1_mdl.out_vars)

# load
P = 150 # in an ideal trafo P1 = P2
load1 = Load(name="load1", P1 =P/3 , P2 =P/3 , P3 =P/3, Q1= 0.0, Q2= 0.0, Q3= 0.0)
load1.conn = ShuntConnectionType.GroundedStar

grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_transformer2w(trafo0)
grid.add_generator(bus=bus1, api_obj=gen1)

# grid.add_load(bus=bus1, api_obj=load1)
grid.add_load(bus=bus2, api_obj=load1)
#
print("grid.Sbase = ", grid.Sbase)

pf_options = PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=True,
    initialize_with_existing_solution=True,
    tolerance=1e-6,
    max_iter=25,
    control_q=False,
    control_taps_modules=True,
    control_taps_phase=True,
    control_remote_voltage=True,
    orthogonalize_controls=True,
    apply_temperature_correction=True,
    branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
    distributed_slack=False,
    ignore_single_node_islands=False,
    trust_radius=1.0,
    backtracking_parameter=0.05,
    use_stored_guess=False,
    initialize_angles=True,
    generate_report=False,
)
power_flow = PowerFlowDriver3Ph(grid, pf_options)
power_flow.run()
res = power_flow.results
print("res.m (branch number)= ", res.m)
print("res.n (bus number)= ", res.n)
print("res.n_gen = ", res.n_gen)
print("res.n_load ", res.n_load)
print("res.bus_names = ", res.bus_names)
print("res.branch_names = ", res.branch_names)
print("res.load_names = ", res.load_names)
print("res.bus_types = ", res.bus_types)
print("res.voltage_A = ", res.voltage_A)
print("res.voltage_B = ", res.voltage_B)
print("res.voltage_C = ", res.voltage_C)
print("res.Sbus_A = ", res.Sbus_A)
print("res.Sbus_B = ", res.Sbus_B)
print("res.Sbus_C = ", res.Sbus_C)
print("res.Sf_A = ", res.Sf_A)
print("res.Sf_B = ", res.Sf_B)
print("res.Sf_C = ", res.Sf_C)
print("res.St_A = ", res.St_A)
print("res.St_B = ", res.St_B)
print("res.St_C = ", res.St_C)
print("res.If_A = ", res.If_A)
print("res.If_B = ", res.If_B)
print("res.If_C = ", res.If_C)
print("res.It_A = ", res.It_A)
print("res.It_B = ", res.It_B)
print("res.It_C = ", res.It_C)

print(f"Converged: {res.converged}")
print(f"res:{res}")
emt_opt = EmtOptions(time_step = 1e-5,
                     simulation_time = 0.03, # s
                     tolerance = 1e-6,
                     integration_method = "implicit_euler")

print(f"initial timestep:{emt_opt.time_step}s")
drv = EmtSimulationDriver(grid, emt_opt, res)
t, V, hist, Ilines, hist_lines, Is, x, dx = drv.run()

print("dx=", dx)

t = np.asarray(t).reshape(-1)
time_df = pd.DataFrame({"time_s": t})

# ============================================================
# 1) V -> V_results.csv
# ============================================================
V_cols = []
for bus in grid.get_buses():

    if bus.ph_n: V_cols.append(f"v_n_{bus.name}")
    if bus.ph_a: V_cols.append(f"v_a_{bus.name}")
    if bus.ph_b: V_cols.append(f"v_b_{bus.name}")
    if bus.ph_c: V_cols.append(f"v_c_{bus.name}")

df_V = pd.concat([time_df, pd.DataFrame(V, columns=V_cols)], axis=1)
df_V.to_csv("V_results.csv", index=False)

# ============================================================
# 2) Is -> Is_results.csv
# ============================================================
Is_cols = []
for bus in grid.get_buses():

    if bus.ph_n: Is_cols.append(f"Is_n_{bus.name}")
    if bus.ph_a: Is_cols.append(f"Is_a_{bus.name}")
    if bus.ph_b: Is_cols.append(f"Is_b_{bus.name}")
    if bus.ph_c: Is_cols.append(f"Is_c_{bus.name}")

df_Is = pd.concat([time_df, pd.DataFrame(Is, columns=Is_cols)], axis=1)
df_Is.to_csv("Is_results.csv", index=False)

# ============================================================
# 3) Ilines -> Ilines_results.csv
# ============================================================
# Il_cols = []

# for line in grid.get_lines():
#
#     bf = line.bus_from
#     bt = line.bus_to
#
#     if bf.ph_n:
#         Il_cols += [f"Ifrom_n_{line.name}", f"Ito_n_{line.name}"]
#     if bf.ph_a:
#         Il_cols += [f"Ifrom_a_{line.name}", f"Ito_a_{line.name}"]
#     if bf.ph_b:
#         Il_cols += [f"Ifrom_b_{line.name}", f"Ito_b_{line.name}"]
#     if bf.ph_c:
#         Il_cols += [f"Ifrom_c_{line.name}", f"Ito_c_{line.name}"]
#
# df_Il = pd.concat([time_df, pd.DataFrame(Ilines, columns=Il_cols)], axis=1)
# df_Il.to_csv("I_lines_results.csv", index=False)
Il_cols = []
for trafo in grid.get_transformers2w():

    bf = trafo.bus_from
    bt = trafo.bus_to

    if bf.ph_n:
        Il_cols += [f"Ifrom_n_{trafo.name}", f"Ito_n_{trafo.name}"]
    if bf.ph_a:
        Il_cols += [f"Ifrom_a_{trafo.name}", f"Ito_a_{trafo.name}"]
    if bf.ph_b:
        Il_cols += [f"Ifrom_b_{trafo.name}", f"Ito_b_{trafo.name}"]
    if bf.ph_c:
        Il_cols += [f"Ifrom_c_{trafo.name}", f"Ito_c_{trafo.name}"]

df_Il = pd.concat([time_df, pd.DataFrame(Ilines, columns=Il_cols)], axis=1)
df_Il.to_csv("I_trafos_results.csv", index=False)

# ============================================================
# 4) x -> x_gen_results.csv
# ============================================================
x_cols = []
offset = 0

for gen_idx, gen in enumerate(grid.get_generators(), start=1):

    model = gen.emt_model
    state_vars     = model.state_vars        # list of names
    algebraic_vars = model.algebraic_vars    # list of names

    var_names = state_vars + algebraic_vars  # in correct order

    # assign names with Gen index
    for name in var_names:
        x_cols.append(f"{name}_Gen{gen_idx}")

df_x = pd.concat([time_df, pd.DataFrame(x, columns=x_cols)], axis=1)
df_x.to_csv("x_gen_results.csv", index=False)


# ============================================================
# 5) dx -> dx_gen_results.csv (ONLY state vars)
# ============================================================
dx_cols = []

offset = 0
for gen_idx, gen in enumerate(grid.get_generators(), start=1):

    model = gen.emt_model
    state_vars = model.state_vars  # only variables with derivative

    for name in state_vars:
        dx_cols.append(f"d{name}_Gen{gen_idx}")

df_dx = pd.concat([time_df, pd.DataFrame(dx, columns=dx_cols)], axis=1)
df_dx.to_csv("dx_gen_results.csv", index=False)

plot_voltages("V_results.csv")
# plot_ilines("I_lines_results.csv")
plot_itrafo("I_trafos_results.csv")
# plot_generators("x_gen_results.csv","dx_gen_results.csv" )
plot_isource("Is_results.csv")
# plot_v_i("V_results.csv", "x_gen_results.csv")

# two phase
# line0.x = [-12.65, 12.65] # Phase conductor x-axis coordinates [m]
# line0.y = [27.5, 27.5] # Phase conductor heights [m]
# line0.R_ac = [0.1363, 0.1363]  # Phase conductor AC resistances [Ohm/km]
# line0.radius = [0.0105, 0.0105] # Phase conductor radi [m]
# line0.inner_radius = [0.0045, 0.0045] # Phase conductor inner tube radii [m]
# line0.rho_e = 100 # Earth resistivity [Ohm.m]

# one phase
# line0.x = [-12.65] # Phase conductor x-axis coordinates [m]
# line0.y = [27.5] # Phase conductor heights [m]
# line0.R_ac = [0.1363]  # Phase conductor AC resistances [Ohm/km]
# line0.radius = [0.0105] # Phase conductor radi [m]
# line0.inner_radius = [0.0045] # Phase conductor inner tube radii [m]
# line0.rho_e = 100 # Earth resistivity [Ohm.m]

# one phase with neutral
# line0.x = [-12.65, 0] # Phase conductor x-axis coordinates [m]
# line0.y = [27.5,  20] # Phase conductor heights [m]
# line0.R_ac = [0.1363,  0.1363]  # Phase conductor AC resistances [Ohm/km]
# line0.radius = [0.0105,  0.0105] # Phase conductor radi [m]
# line0.inner_radius = [0.0045, 0.0045] # Phase conductor inner tube radii [m]
# line0.rho_e = 100 # Earth resistivity [Ohm.m]

# three phase with neutral
# line0.x = [-12.65, 0, 12.65, 0] # Phase conductor x-axis coordinates [m]
# line0.y = [27.5, 27.5, 27.5, 20] # Phase conductor heights [m]
# line0.R_ac = [0.1363, 0.1363, 0.1363, 0.1363]  # Phase conductor AC resistances [Ohm/km]
# line0.radius = [0.0105, 0.0105, 0.0105, 0.0105] # Phase conductor radi [m]
# line0.inner_radius = [0.0045, 0.0045, 0.0045, 0.0045] # Phase conductor inner tube radii [m]
# line0.rho_e = 100 # Earth resistivity [Ohm.m]



