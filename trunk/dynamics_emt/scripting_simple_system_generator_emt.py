# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import cProfile
import pstats
import numpy as np

import sys
import os

import matplotlib.pyplot as plt

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Utils.Symbolic.block import Block

from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph


from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_3ph_emt_template
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_generator_emt_template
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template

from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, EmtSolverTypes, ShuntConnectionType
from VeraGridEngine.Devices.Aggregation import RmsEvent
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

profiler = cProfile.Profile()
profiler.enable()

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res




grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=10)

grid.add_bus(bus0)
grid.add_bus(bus1)

# Lines
line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)
line0.emt_model_type = gce.EmtLineTypes.PI

# physical configuration (Overhead line tower)
tower = gce.OverheadLineType(name="Tower", Vnom=10)
wire = gce.Wire(name="Panther 30/7 ACSR",
                diameter=21.0,
                diameter_internal=9.0,
                is_tube=True,
                r=0.1363,
                max_current=1)
tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
tower.compute()

# Aplicar física a la línea
line0.apply_template(tower, grid.Sbase, grid.fBase)

# load
P=1.0
Q= 0.999999
# P = 0.0
# Q = 0.0
load = gce.Load(name="load",P1= P/3, P2= P/3, P3= P/3, Q1= Q/3, Q2= Q/3, Q3= Q/3)
load.conn = ShuntConnectionType.GroundedStar

# Generators
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq = 50, r1=0.001, x1=1.7)
# r1=Ra, x1=xd'

grid.add_line(line0)
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_load(bus=bus1, api_obj=load)


for bus in grid.buses:
    get_bus_emt_template(grid, bus, vf=grid.var_factory)

######################################################################################################
# Build EMT models
######################################################################################################

# Build dynamic_model_host

line_dynhost = DynamicModelHost()
load_dynhost = DynamicModelHost()
gen_dynhost = DynamicModelHost()

# generator
gen_mdl = get_generator_emt_template(grid=grid, gen = gen0).block

# line
line_mdl = get_pi_line_emt_template(grid = grid, line = line0).block

# load
load_mdl = get_load_ZIP_3ph_emt_template(grid = grid, load = load).block

# connection with buses
gen_mdl.connect([gen_mdl.in_vars[0]], [bus0.emt_model.model.out_vars[0]]) # v_A
gen_mdl.connect([gen_mdl.in_vars[1]], [bus0.emt_model.model.out_vars[1]]) # v_B
gen_mdl.connect([gen_mdl.in_vars[2]], [bus0.emt_model.model.out_vars[2]]) # v_C


line_mdl.connect([line_mdl.in_vars[0]], [bus0.emt_model.model.out_vars[0]]) # line vf_A
line_mdl.connect([line_mdl.in_vars[1]], [bus0.emt_model.model.out_vars[1]]) # line vf_B
line_mdl.connect([line_mdl.in_vars[2]], [bus0.emt_model.model.out_vars[2]]) # line vf_C
line_mdl.connect([line_mdl.in_vars[6]], [bus0.emt_model.model.out_vars[3]]) # line d_vf_A
line_mdl.connect([line_mdl.in_vars[7]], [bus0.emt_model.model.out_vars[4]]) # line d_vf_B
line_mdl.connect([line_mdl.in_vars[8]], [bus0.emt_model.model.out_vars[5]]) # line d_vf_C

line_mdl.connect([line_mdl.in_vars[3]], [bus1.emt_model.model.out_vars[0]]) # line vt_A
line_mdl.connect([line_mdl.in_vars[4]], [bus1.emt_model.model.out_vars[1]]) # line vt_B
line_mdl.connect([line_mdl.in_vars[5]], [bus1.emt_model.model.out_vars[2]]) # line vt_C
line_mdl.connect([line_mdl.in_vars[9]], [bus1.emt_model.model.out_vars[3]]) # line d_vt_A
line_mdl.connect([line_mdl.in_vars[10]], [bus1.emt_model.model.out_vars[4]]) # line d_vt_B
line_mdl.connect([line_mdl.in_vars[11]], [bus1.emt_model.model.out_vars[5]]) # line d_vt_C

# u_gov = find_name_in_block("u_gov1", gov1_mdl)

load_mdl.connect([load_mdl.in_vars[0]], [bus1.emt_model.model.out_vars[0]]) # v_A
load_mdl.connect([load_mdl.in_vars[1]], [bus1.emt_model.model.out_vars[1]]) # v_B
load_mdl.connect([load_mdl.in_vars[2]], [bus1.emt_model.model.out_vars[2]]) # v_C
load_mdl.connect([load_mdl.in_vars[3]], [bus1.emt_model.model.out_vars[3]]) # d_v_A
load_mdl.connect([load_mdl.in_vars[4]], [bus1.emt_model.model.out_vars[4]]) # d_v_B
load_mdl.connect([load_mdl.in_vars[5]], [bus1.emt_model.model.out_vars[5]]) # d_v_C

# external mapping
big_gen1 = Block(children=[gen_mdl])

big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: gen_mdl.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: gen_mdl.out_vars[1]})

# add models to dyn_host
line_dynhost.model = line_mdl
load_dynhost.model = load_mdl
gen_dynhost.model = big_gen1

# attach rms models to Veragrid objects
line0.emt_model= line_dynhost
load.emt_model= load_dynhost
gen0.emt_model= gen_dynhost

# apply event
# Pl0 = find_name_in_block('Pl0', load_mdl)
# event = RmsEvent(device=load, parameter=Pl0, time=0.1, value=-0.09)
# grid.add_rms_event(event)


# gce.save_file(grid=grid, filename="grid_save_event.veragrid")

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

# res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True))
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

print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

options = EmtOptions(time_step = 5e-7, # 5e-7,
                     simulation_time =  0.01,  #5e-6*10, # s
                     tolerance = 1e-6,
                     solver = EmtSolverTypes.Symbolic,
                     integration_method = DynamicIntegrationMethod.DaeTrapezoidal,
                     verbose = 1)

problem = EmtProblemDae(grid=grid,
                        options=options,
                        pf_results=res)
problem.set_newton_trace_collector(NewtonTraceCollector())

# sv = problem.get_state_vars()
# dv = problem.get_diff_vars()
#
# assert len(sv) == len(dv)


df = problem.get_init_guess_table()
print(f"init_guess_table{df}")

# print(f"state_vars = {problem.get_state_vars()}")
# print(f"diff_vars = {problem.get_diff_vars()}")

# x0 = problem.get_x0()
# print("x0 =", x0)
# print("len(x0) =", len(x0))
# print("nans =", np.isnan(x0).sum())
# print("infs =", np.isinf(x0).sum())
# print("nonzeros =", np.count_nonzero(x0))
# print("len(init_guess) =", len(problem.init_guess))
#
# dx0 = problem.get_dx0()
# print("dx0 =",dx0)
# print("len(dx0) =", len(dx0))
# print("nans =", np.isnan(dx0).sum())
# print("infs =", np.isinf(dx0).sum())
# print("nonzeros =", np.count_nonzero(dx0))
# print("len(diff_init_guess) =", len(problem.diff_init_guess))


solver = JitSymbolicSolver(problem = problem,
                           t0 = 0.0,
                           t_end = options.simulation_time,
                           h = options.time_step,
                           method=options.integration_method,
                           pred_method=DynamicIntegrationMethod.OdeEuler,
                           # pred_method=None,
                           verbose = True)

# solver = StructuralVectorizedSolver(problem = problem,
#                            t0 = 0.0,
#                            t_end = options.simulation_time,
#                            h = options.time_step,
#                            method=options.integration_method,
#                            pred_method=DynamicIntegrationMethod.OdeEuler,
#                            # pred_method=None,
#                            verbose = True)
# solver = JitAdSolver(problem = problem,
#                            t0 = 0.0,
#                            t_end = options.simulation_time,
#                            h = options.time_step,
#                            method=options.integration_method,
#                            pred_method=DynamicIntegrationMethod.OdeEuler,
#                            # pred_method=None,
#                            verbose = True)

t, y, dy = solver.simulate()

collector = problem.get_newton_trace_collector()
if collector:
    print(f"Newton iters : {len(collector.records)}")

#  Convert collected diagnostics to DataFrame
df = collector.to_dataframe()  # o pd.DataFrame(collector.records)

# Save full diagnostics
df.to_csv("newton_diagnostics_demo.csv", index=False)
print("Diagnostics written to newton_diagnostics_demo.csv")

# profiler.disable()
# profiler.dump_stats("profiling_stats.prof")

xlim = options.simulation_time

t_end = options.simulation_time
h = options.time_step
steps: int = int(t_end / h)
tme: np.ndarray = np.linspace(0, t_end, steps)

#
v_A_0 = find_name_in_block("v_ABus0_emt_template", bus0.emt_model.model)
v_B_0 = find_name_in_block("v_BBus0_emt_template", bus0.emt_model.model)
v_C_0 = find_name_in_block("v_CBus0_emt_template", bus0.emt_model.model)
v_A_0_plt = y[:, problem.get_var_idx(v_A_0)]
v_B_0_plt = y[:, problem.get_var_idx(v_B_0)]
v_C_0_plt = y[:, problem.get_var_idx(v_C_0)]

v_A_1 = find_name_in_block("v_ABus1_emt_template", bus1.emt_model.model)
v_B_1 = find_name_in_block("v_BBus1_emt_template", bus1.emt_model.model)
v_C_1 = find_name_in_block("v_CBus1_emt_template", bus1.emt_model.model)
v_A_1_plt = y[:, problem.get_var_idx(v_A_1)]
v_B_1_plt = y[:, problem.get_var_idx(v_B_1)]
v_C_1_plt = y[:, problem.get_var_idx(v_C_1)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 1, 1)
plt.plot(tme, v_A_0_plt[:len(tme)], label='Voltage phase A bus 0', color='blue')
plt.plot(tme, v_B_0_plt[:len(tme)], label='Voltage phase B bus 0', color='red')
plt.plot(tme, v_C_0_plt[:len(tme)], label='Voltage phase C bus 0', color='green')
plt.title("Voltage bus 0")
plt.xlabel("Time")
plt.ylabel("Voltage [p.u.]")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(tme, v_A_1_plt[:len(tme)], label='Voltage phase A bus 1', color='blue')
plt.plot(tme, v_B_1_plt[:len(tme)], label='Voltage phase B bus 1', color='red')
plt.plot(tme, v_C_1_plt[:len(tme)], label='Voltage phase C bus 1', color='green')
plt.title("Voltage bus 1")
plt.xlabel("Time")
plt.ylabel("Voltage [p.u.]")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()

theta = find_name_in_block("theta_emt_type_generator_template", gen_mdl)
omega_gen = find_name_in_block("omega_emt_type_generator_template", gen_mdl)
theta_plt = y[:, problem.get_var_idx(theta)]
omega_plt = y[:, problem.get_var_idx(omega_gen)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 1, 1)
plt.plot(tme, theta_plt[:len(tme)], label='Theta generator [rad]', color='blue')
plt.title("Theta generator")
plt.xlabel("Time")
plt.ylabel("Theta generator")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(tme, omega_plt[:len(tme)], label='Speed generator [rad/s]', color='blue')
plt.title("Omega generator")
plt.xlabel("Time")
plt.ylabel("Omega generator [rad/s]")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()

i_A_gen = find_name_in_block("i_A_emt_type_generator_template", gen_mdl)
i_B_gen = find_name_in_block("i_B_emt_type_generator_template", gen_mdl)
i_C_gen = find_name_in_block("i_C_emt_type_generator_template", gen_mdl)
i_A_gen_plt = y[:, problem.get_var_idx(i_A_gen)]
i_B_gen_plt = y[:, problem.get_var_idx(i_B_gen)]
i_C_gen_plt = y[:, problem.get_var_idx(i_C_gen)]

i_A_load = find_name_in_block("i_A_ZIP_Load_EMT_3ph", load_mdl)
i_B_load = find_name_in_block("i_B_ZIP_Load_EMT_3ph", load_mdl)
i_C_load = find_name_in_block("i_C_ZIP_Load_EMT_3ph", load_mdl)
i_A_load_plt = y[:, problem.get_var_idx(i_A_load)]
i_B_load_plt = y[:, problem.get_var_idx(i_B_load)]
i_C_load_plt = y[:, problem.get_var_idx(i_C_load)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 2, 1)
plt.plot(tme, i_A_gen_plt[:len(tme)], label='Current phase A from generator', color='blue')
plt.plot(tme, i_B_gen_plt[:len(tme)], label='Current phase B from generator', color='red')
plt.plot(tme, i_C_gen_plt[:len(tme)], label='Current phase C from generator', color='green')
plt.title("Current generator")
plt.xlabel("Time")
plt.ylabel("Current generator")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 2)
plt.plot(tme, i_A_load_plt[:len(tme)], label='Current phase A from load', color='blue')
plt.plot(tme, i_B_load_plt[:len(tme)], label='Current phase B from load', color='red')
plt.plot(tme, i_C_load_plt[:len(tme)], label='Current phase C from load', color='green')
plt.title("Current load")
plt.xlabel("Time")
plt.ylabel("Current load")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()

Pm_gen = find_name_in_block("Pm_emt_type_generator_template", gen_mdl)
Qe_gen = find_name_in_block("Qe_emt_type_generator_template", gen_mdl)
Pe_gen = find_name_in_block("Pe_emt_type_generator_template", gen_mdl)
Tm_gen = find_name_in_block("Tm_emt_type_generator_template", gen_mdl)
Te_gen = find_name_in_block("Te_emt_type_generator_template", gen_mdl)
et_gen = find_name_in_block("et_emt_type_generator_template", gen_mdl)
Pm_gen_plt = y[:, problem.get_var_idx(Pm_gen)]
Qe_gen_plt = y[:, problem.get_var_idx(Qe_gen)]
Pe_gen_plt = y[:, problem.get_var_idx(Pe_gen)]
Tm_gen_plt = y[:, problem.get_var_idx(Tm_gen)]
Te_gen_plt = y[:, problem.get_var_idx(Te_gen)]
et_gen_plt = y[:, problem.get_var_idx(et_gen)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 2, 1)
plt.plot(tme, Pm_gen_plt[:len(tme)], label='Mechanical power Pm from generator', color='blue')
plt.plot(tme, Pe_gen_plt[:len(tme)], label='Electrical power Pe from generator', color='red')
plt.plot(tme, Qe_gen_plt[:len(tme)], label='Electrical reactive power Qe from generator', color='purple')
plt.title("power generator")
plt.xlabel("Time")
plt.ylabel("power generator")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 2)
plt.plot(tme, Tm_gen_plt[:len(tme)], label='Mechanical torque Tm from generator', color='blue')
plt.plot(tme, Te_gen_plt[:len(tme)], label='Electrical torque Te from generator', color='red')
plt.title("torque generator")
plt.xlabel("Time")
plt.ylabel("torque generator")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 3)
plt.plot(tme, et_gen_plt[:len(tme)], label='PI error at generator', color='blue')
plt.title("et generator")
plt.xlabel("Time")
plt.ylabel("et generator")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()

P_A_load = find_name_in_block("P_A_ZIP_Load_EMT_3ph", load_mdl)
P_B_load = find_name_in_block("P_B_ZIP_Load_EMT_3ph", load_mdl)
P_C_load = find_name_in_block("P_C_ZIP_Load_EMT_3ph", load_mdl)
P_A_load_plt = y[:, problem.get_var_idx(P_A_load)]
P_B_load_plt = y[:, problem.get_var_idx(P_B_load)]
P_C_load_plt = y[:, problem.get_var_idx(P_C_load)]
P_tot_load = P_A_load_plt +  P_B_load_plt + P_C_load_plt

Q_A_load = find_name_in_block("Q_A_ZIP_Load_EMT_3ph", load_mdl)
Q_B_load = find_name_in_block("Q_B_ZIP_Load_EMT_3ph", load_mdl)
Q_C_load = find_name_in_block("Q_C_ZIP_Load_EMT_3ph", load_mdl)
Q_A_load_plt = y[:, problem.get_var_idx(Q_A_load)]
Q_B_load_plt = y[:, problem.get_var_idx(Q_B_load)]
Q_C_load_plt = y[:, problem.get_var_idx(Q_C_load)]
Q_tot_load = Q_A_load_plt +  Q_B_load_plt + Q_C_load_plt

plt.figure(figsize=(12, 8))

plt.subplot(2, 1, 1)
plt.plot(tme, P_A_load_plt[:len(tme)], label='Active power phase A load', color='blue')
plt.plot(tme, P_B_load_plt[:len(tme)], label='Active power phase B load', color='red')
plt.plot(tme, P_C_load_plt[:len(tme)], label='Active power phase C load', color='green')
# plt.plot(tme, P_tot_load[:len(tme)], label='Active power total load', color='black')
plt.title("Active power load")
plt.xlabel("Time")
plt.ylabel("power load")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(tme, Q_A_load_plt[:len(tme)], label='Reactive power phase A load', color='blue')
plt.plot(tme, Q_B_load_plt[:len(tme)], label='Reactive power phase B load', color='red')
plt.plot(tme, Q_C_load_plt[:len(tme)], label='Reactive power phase C load', color='green')
# plt.plot(tme, Q_tot_load[:len(tme)], label='Reactive power total load', color='black')
plt.title("Reactive power load")
plt.xlabel("Time")
plt.ylabel("power load")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()

i_f_A_line = find_name_in_block("if_line0_0", load_mdl)
i_f_B_line = find_name_in_block("if_line0_1", load_mdl)
i_f_C_line = find_name_in_block("if_line0_2", load_mdl)
i_f_A_line_plt = y[:, problem.get_var_idx(i_f_A_line)]
i_f_B_line_plt = y[:, problem.get_var_idx(i_f_B_line)]
i_f_C_line_plt = y[:, problem.get_var_idx(i_f_C_line)]

i_t_A_line = find_name_in_block("it_line0_0", load_mdl)
i_t_B_line = find_name_in_block("it_line0_1", load_mdl)
i_t_C_line = find_name_in_block("it_line0_2", load_mdl)
i_t_A_line_plt = y[:, problem.get_var_idx(i_t_A_line)]
i_t_B_line_plt = y[:, problem.get_var_idx(i_t_B_line)]
i_t_C_line_plt = y[:, problem.get_var_idx(i_t_C_line)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 2, 1)
plt.plot(tme, i_A_gen_plt[:len(tme)], label='Current phase A from generator', color='blue')
plt.plot(tme, i_B_gen_plt[:len(tme)], label='Current phase B from generator', color='red')
plt.plot(tme, i_C_gen_plt[:len(tme)], label='Current phase C from generator', color='green')
plt.title("Current generator")
plt.xlabel("Time")
plt.ylabel("Current generator")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 2)
plt.plot(tme, i_A_load_plt[:len(tme)], label='Current phase A from load', color='blue')
plt.plot(tme, i_B_load_plt[:len(tme)], label='Current phase B from load', color='red')
plt.plot(tme, i_C_load_plt[:len(tme)], label='Current phase C from load', color='green')
plt.title("Current load")
plt.xlabel("Time")
plt.ylabel("Current load")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 1, 1)
plt.plot(tme, i_f_A_line_plt[:len(tme)], label='Current FROM phase A from line', color='blue')
plt.plot(tme, i_f_B_line_plt[:len(tme)], label='Current FROM phase B from line', color='red')
plt.plot(tme, i_f_C_line_plt[:len(tme)], label='Current FROM phase C from line', color='green')
plt.title("Current from line")
plt.xlabel("Time")
plt.ylabel("Current from")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(tme, i_t_A_line_plt[:len(tme)], label='Current TO phase A from line', color='blue')
plt.plot(tme, i_t_B_line_plt[:len(tme)], label='Current TO phase B from line', color='red')
plt.plot(tme, i_t_C_line_plt[:len(tme)], label='Current TO phase C from line', color='green')
plt.title("Current to line")
plt.xlabel("Time")
plt.ylabel("Current to")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()

i_ser_A = find_name_in_block("i_ser_line0_0", line_mdl)
i_ser_B = find_name_in_block("i_ser_line0_1", line_mdl)
i_ser_C = find_name_in_block("i_ser_line0_2", line_mdl)
i_ser_A_plt = y[:, problem.get_var_idx(i_ser_A)]
i_ser_B_plt = y[:, problem.get_var_idx(i_ser_B)]
i_ser_C_plt = y[:, problem.get_var_idx(i_ser_C)]

i_f_cap_A = find_name_in_block("i_cap_f_line0_0", line_mdl)
i_f_cap_B = find_name_in_block("i_cap_f_line0_1", line_mdl)
i_f_cap_C = find_name_in_block("i_cap_f_line0_2", line_mdl)
i_f_cap_A_plt = y[:, problem.get_var_idx(i_f_cap_A)]
i_f_cap_B_plt = y[:, problem.get_var_idx(i_f_cap_B)]
i_f_cap_C_plt = y[:, problem.get_var_idx(i_f_cap_C)]

i_t_cap_A = find_name_in_block("i_cap_t_line0_0", line_mdl)
i_t_cap_B = find_name_in_block("i_cap_t_line0_1", line_mdl)
i_t_cap_C = find_name_in_block("i_cap_t_line0_2", line_mdl)
i_t_cap_A_plt = y[:, problem.get_var_idx(i_t_cap_A)]
i_t_cap_B_plt = y[:, problem.get_var_idx(i_t_cap_B)]
i_t_cap_C_plt = y[:, problem.get_var_idx(i_t_cap_C)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 2, 1)
plt.plot(tme, i_ser_A_plt[:len(tme)], label='Phase A series current line', color='blue')
plt.plot(tme, i_ser_B_plt[:len(tme)], label='Phase B series current line', color='red')
plt.plot(tme, i_ser_C_plt[:len(tme)], label='Phase C series current line', color='green')
plt.title("Series current in line")
plt.xlabel("Time")
plt.ylabel("Current")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 3)
plt.plot(tme, i_f_cap_A_plt[:len(tme)], label='Shunt current at from line phase A', color='blue')
plt.plot(tme, i_f_cap_B_plt[:len(tme)], label='Shunt current at from line phase B', color='red')
plt.plot(tme, i_f_cap_C_plt[:len(tme)], label='Shunt current at from line phase C', color='green')
plt.title("From shunt currents in line")
plt.xlabel("Time")
plt.ylabel("Current")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 4)
plt.plot(tme, i_t_cap_A_plt[:len(tme)], label='Shunt current at to line phase A', color='blue')
plt.plot(tme, i_t_cap_B_plt[:len(tme)], label='Shunt current at to line phase B', color='red')
plt.plot(tme, i_t_cap_C_plt[:len(tme)], label='Shunt current at to line phase C', color='green')
plt.title("To shunt currents in line")
plt.xlabel("Time")
plt.ylabel("Current")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()