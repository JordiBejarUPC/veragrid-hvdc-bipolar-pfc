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
from VeraGridEngine.Simulations.EMT.initialization_emt import initialize_emt
from VeraGrid.trunk.dynamics_emt.support.plot_emt_results import plot_results_by_time

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver

from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

import VeraGridEngine.api as gce

emt_opt = EmtOptions(
    time_step = 6.33e-6,
    simulation_time = 0.3
)

grid = MultiCircuit()


bus1 = Bus(name="Bus1", Vnom=230)
bus2 = Bus(name="Bus2", Vnom=230)
bus1.ph_a = True
bus1.ph_b = True
bus1.ph_c = True
bus1.ph_n = False

bus2.ph_a = True
bus2.ph_b = True
bus2.ph_c = True
bus2.ph_n = False
# bus3 = Bus(name="Bus3", Vnom=230)

grid.add_bus(bus1)
grid.add_bus(bus2)
# grid.add_bus(bus3)

r_ = 0 #ohm/m
l_ = 1e-6 #H/m
c_ = 1e-11 #F/m

Sbase  =100e6 #VA
Vbase = 230e3 #V
Zbase = Vbase*Vbase/Sbase
f = 50
l1 = 100 #km
# l2 = 300

R1 = (r_ * l1*1e3)/Zbase
X1 = (l_ * 2 * np.pi * f * l1*1e3)/Zbase
B1 = (c_ * 2 * np.pi * f * l1*1e3)*Zbase

# R2 = (r_ * l2*1e3)/Zbase
# X2 = (l_ * 2 * np.pi * f * l2*1e3)/Zbase
# B2 = (c_ * 2 * np.pi * f * l2*1e3)*Zbase


line0 = grid.add_line(
    Line(name="line 1-2", bus_from=bus1, bus_to=bus2, rate = 500,
         r  = R1, x = X1, b = B1, length= l1,
         r0  = 2 * R1, x0 = 2 * X1, b0 = 0.5 * B1,
         r2  = R1, x2 = X1, b2 = B1))

# three phase
line0.x = [-12.65, 0, 12.65] # Phase conductor x-axis coordinates [m]
line0.y = [27.5, 27.5, 27.5] # Phase conductor heights [m]
line0.R_ac = [0.1363, 0.1363, 0.1363]  # Phase conductor AC resistances [Ohm/km]
line0.radius = [0.0105, 0.0105, 0.0105] # Phase conductor radi [m]
line0.inner_radius = [0.0045, 0.0045, 0.0045] # Phase conductor inner tube radii [m]
line0.rho_e = 100 # Earth resistivity [Ohm.m]

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

# three-phase with neutral
# line0.x = [-12.65, 0, 12.65, 0] # Phase conductor x-axis coordinates [m]
# line0.y = [27.5, 27.5, 27.5, 20] # Phase conductor heights [m]
# line0.R_ac = [0.1363, 0.1363, 0.1363, 0.1363]  # Phase conductor AC resistances [Ohm/km]
# line0.radius = [0.0105, 0.0105, 0.0105, 0.0105] # Phase conductor radi [m]
# line0.inner_radius = [0.0045, 0.0045, 0.0045, 0.0045] # Phase conductor inner tube radii [m]
# line0.rho_e = 100 # Earth resistivity [Ohm.m]

# false voltage source generator todo: temporary
gen1 = Generator(name="Gen1",R=3, V=230,freq = 50, P=17.63)
grid.add_generator(bus=bus1, api_obj=gen1)


#load
load1 = Load(name="load1", R= 5.982e+02, P=17)
grid.add_load(bus=bus2, api_obj=load1)

nc = compile_numerical_circuit_at(
        circuit=grid,
    )

pf_options = PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=0,
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
    initialize_angles=False,
    generate_report=False,
)
power_flow = PowerFlowDriver(grid, pf_options)
power_flow.run()
res = power_flow.results
# print("res.m (branch number)= ", res.m)
# print("res.n (bus number)= ", res.n)
# print("res.n_gen = ", res.n_gen)
# print("res.n_load ", res.n_load)
print("res.bus_names = ", res.bus_names)
print("res.branch_names = ", res.branch_names)
# print("res.load_names = ", res.load_names)
print("res.bus_types = ", res.bus_types)
print("res.voltage = ", res.voltage)
print("res.Sbus = ", res.Sbus)
print("res.Sf = ", res.Sf)
print("res.St = ", res.St)

print(f"Converged: {res.converged}")

print(f"initial timestep:{emt_opt.time_step}s")

ss, init_guess, h, N_delay, G0, binary_bus_mask, branch_lookup, bus_idx_lookup = initialize_emt(grid, emt_opt, res, nc)

print("G:", G0.toarray())
print("N_delay:", N_delay)

emt_simulation = EmtSimulationDriver(grid, emt_opt, res)
temps, V, hist, Ilines, hist_lines, Is = emt_simulation.simulate_emt(simulation_time = emt_opt.simulation_time,
                                                                     nc = nc,
                                                                     grid = grid,
                                                                     syst_block = ss,
                                                                     init_guess = init_guess,
                                                                     time_step = h,
                                                                     N_delay = N_delay,
                                                                     G0 = G0,
                                                                     binary_bus_mask = binary_bus_mask,
                                                                     branch_lookup = branch_lookup,
                                                                     bus_idx_lookup = bus_idx_lookup,
                                                                     )

# plot and save results
def make_bus_columns(grid, phases_per_bus):
    cols = []
    for bus in grid.buses:
        for ph in phases_per_bus[bus]:
            cols.append(f"bus{bus}_{ph}")
    return cols


def make_line_columns(grid, phases_per_bus):
    cols = []
    # for i, line in enumerate(grid.get_lines()):
    #     bus_f = line.bus_from
    #     bus_t = line.bus_to
    #
    #     # Phases that exist at both ends
    #     active = []
    #     if bus_f.ph_a and bus_t.ph_a: active.append("A")
    #     if bus_f.ph_b and bus_t.ph_b: active.append("B")
    #     if bus_f.ph_c and bus_t.ph_c: active.append("C")
    #     if bus_f.ph_n and bus_t.ph_n: active.append("N")
    #
    #     for ph in active:
    #         cols.append(f"line{i+1}_from_{ph}")
    #     for ph in active:
    #         cols.append(f"line{i+1}_to_{ph}")
    for line in grid.get_lines():
        name = line.name.replace(" ", "")  # or use line.idx

        # phases present on both ends (same mask used by solver)
        phases = [p for p in ["n", "a", "b", "c"]
                  if getattr(line.bus_from, f"ph_{p}") and getattr(line.bus_to, f"ph_{p}")]

        for ph in phases:
            cols.append(f"{name}_from_{ph.upper()}")
            cols.append(f"{name}_to_{ph.upper()}")

    return cols

phases = ["ph_n", "ph_a", "ph_b", "ph_c" ]
ph_labels = ["N", "A", "B", "C" ]

phases_per_bus = {}

for bus in grid.buses:
    active = []
    for flag, label in zip(phases, ph_labels):
        if getattr(bus, flag):
            active.append(label)
    phases_per_bus[bus] = active

#I_s
Is_cols = make_bus_columns(grid, phases_per_bus)
df = pd.DataFrame(Is, columns=Is_cols)
df.insert(0, "Time [s]", temps)
df.to_csv("Is_results.csv", index=False)
print("Saved Is_results.csv")


#V
V_cols = make_bus_columns(grid, phases_per_bus)
df = pd.DataFrame(V, columns=V_cols)
df.insert(0, "Time [s]", temps)
df.to_csv("V_results.csv", index=False)
print("Saved V_results.csv")

#history
hist_cols = make_bus_columns(grid, phases_per_bus)
df = pd.DataFrame(hist, columns=hist_cols)
df.insert(0, "Time [s]", temps)
df.to_csv("hist_results.csv", index=False)
print("Saved hist_results.csv")

Ilines_cols = make_line_columns(grid, phases_per_bus)
expected_cols = len(Ilines_cols)

if Ilines.shape[1] > expected_cols:
    Ilines = Ilines[:, :expected_cols]
    hist_lines = hist_lines[:, :expected_cols]

# I_lines
df = pd.DataFrame(Ilines, columns=Ilines_cols)
df.insert(0, "Time [s]", temps)
df.to_csv("I_lines_results.csv", index=False)
print("Saved I_lines_results.csv")


#hist lines
hist_line_cols = Ilines_cols
df = pd.DataFrame(hist_lines, columns=hist_line_cols)
df.insert(0, "Time [s]", temps)
df.to_csv("hist_lines_results.csv", index=False)
print("Saved hist_lines_results.csv")

#
plot_results_by_time("V_results.csv", what_to_plot="v")
plot_results_by_time("Is_results.csv", what_to_plot="i_s")
plot_results_by_time("I_lines_results.csv", what_to_plot="i_line")
#
