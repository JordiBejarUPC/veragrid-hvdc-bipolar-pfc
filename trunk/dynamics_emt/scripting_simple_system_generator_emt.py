# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import cProfile
import pstats
import numpy as np
from matplotlib import pyplot as plt

import sys
import os

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults, PowerFlowOptions

from VeraGridEngine import VarPowerFlowRefferenceType, power_flow, DynamicIntegrationMethod
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy

from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph


from VeraGridEngine.Utils.Symbolic.block_solver_no_diff import BlockSolverNoDiff
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_generator_emt_template

from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD_VEC import AdVecSolver
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver


from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, RmsInitializationMethod
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


grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=10)

# this could be an emt_model from a template but since buses will not have "templates", the default one is used
bus0.initialize_emt()
bus1.initialize_emt()

grid.add_bus(bus0)
grid.add_bus(bus1)

# Lines
line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus1, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)

# load
P= 9.999999
Q= 0.999999
load = gce.Load(name="load",P1= P/3, P2= P/3, P3= P/3, Q1= Q/3, Q2= Q/3, Q3= Q/3)

# Generators
gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom=900,
                     x1=0.86138701, r1=0.3, freq=50.0,
                     M=10.0,
                     D=1.0,
                     omega_ref=1.0,
                     Kp=1.0,
                     Ki=10.0,
                     )

######################################################################################################
# Build EMT models
######################################################################################################

# Build dynamic_model_host

line_dynhost = DynamicModelHost()
load_dynhost = DynamicModelHost()
gen_dynhost = DynamicModelHost()

# generator
gen_mdl = get_generator_emt_template(grid.var_factory).block

# line
line_mdl = get_line_rms_template(grid.var_factory).block # TODO

# load
load_mdl = get_load_rms_template(grid.var_factory).block # TODO

# connection with buses

gen_mdl.connect([gen_mdl.in_vars[0]], [bus0.emt_model.model.out_vars[0]])
gen_mdl.connect([gen_mdl.in_vars[1]], [bus0.emt_model.model.out_vars[1]])


line_mdl.connect([line_mdl.in_vars[0]], [bus0.emt_model.model.out_vars[0]])
line_mdl.connect([line_mdl.in_vars[1]], [bus0.emt_model.model.out_vars[1]])

line_mdl.connect([line_mdl.in_vars[2]], [bus1.emt_model.model.out_vars[0]])
line_mdl.connect([line_mdl.in_vars[3]], [bus1.emt_model.model.out_vars[1]])

# u_gov = find_name_in_block("u_gov1", gov1_mdl)

load_mdl.connect([load_mdl.in_vars[0]], [bus1.emt_model.model.out_vars[0]])
load_mdl.connect([load_mdl.in_vars[1]], [bus1.emt_model.model.out_vars[1]])

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
Pl0 = find_name_in_block('Pl0', load_mdl)
event = RmsEvent(device=load, parameter=Pl0, time=0.1, value=-0.09)
grid.add_rms_event(event)

grid.add_line(line0)
grid.add_load(bus=bus1, api_obj=load)
grid.add_generator(bus=bus0, api_obj=gen0)

gce.save_file(grid=grid, filename="grid_save_event.veragrid")

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

params_mapping = dict()


options = EmtOptions(time_step = 5e-6,
                     simulation_time =  0.01, #5e-6*10, # s
                     tolerance = 1e-6,
                     integration_method = "implicit_euler")

# options = RmsOptions(time_step=0.001,
#                  simulation_time=1,
#                  tolerance=1e-6,
#                  integration_method=DynamicIntegrationMethod.BackEuler,
#                  initialization_method=RmsInitializationMethod.Explicit,
#                  use_init_values=False,
#                  max_iter=1000,
#                  verbose=0)

problem = EmtProblemDae(grid=grid,
                        options=options,
                        pf_results=res)

# solver = BackEulerImplicitIntegration(
#     problem=problem,
#     t0=0,
#     t_end=options.simulation_time,
#     h=options.time_step,
#     max_iter=options.max_iter
# )

solver = AdVecSolver(problem = problem,
                     t0 = 0.0,
                     t_end = options.simulation_time,
                     h = options.time_step,
                     method_str="trapezoidal",
                     verbose = False)

t, y = solver.simulate()

# t, y, well_initialized, converged = solver.simulate()

profiler.disable()
profiler.dump_stats("profiling_stats.prof")

xlim = options.simulation_time

omega = find_name_in_block("omega", gen_mdl)
Pg = gen_mdl.out_vars[0]
Qg = gen_mdl.out_vars[1]
Ir = find_name_in_block("Ir", gen_mdl)
Efd = find_name_in_block("Efd", gen_mdl)
Te = find_name_in_block("Te", gen_mdl)
Vm = find_name_in_block("Vm", gen_mdl)

u_gov1 = find_name_in_block("u_gov1", gen_mdl)
y_subexciter = find_name_in_block("y_subexciter1", gen_mdl)
y_exciter1 = find_name_in_block("y_exciter1", gen_mdl)
y_exciter4 = find_name_in_block("y_exciter4", gen_mdl)
Efe = find_name_in_block("Efe", gen_mdl)
delta = find_name_in_block("delta", gen_mdl)


# Generator state variables
plt.plot(t, y[:, problem.get_var_idx(omega)], label="omega (pu)")
plt.plot(t, y[:, problem.get_var_idx(delta)], label="delta (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Vm)], label="Vm (pu)")
plt.plot(t, y[:, problem.get_var_idx(Pg)], label="P (pu)")
plt.plot(t, y[:, problem.get_var_idx(Qg)], label="Q (pu)")
# plt.plot(t, y[:, solver.get_var_idx(Ir)], label="Ir (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()



#
# Eq_prime = find_name_in_block("Eq_prime", gen_mdl)
# Ed_prime = find_name_in_block("Ed_prime", gen_mdl)
# Psiq_prime = find_name_in_block("Psiq_prime", gen_mdl)
# Psid_prime = find_name_in_block("Psid_prime", gen_mdl)
#
# Ed1 = find_name_in_block("Ed1", gen_mdl)
# Eq1 = find_name_in_block("Eq1", gen_mdl)

# Generator state variables
# plt.plot(t, y[:, problem.get_var_idx(Eq_prime)], label="Eq_prime (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Ed_prime)], label="Ed_prime (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Psiq_prime)], label="Eq_2prime (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Psid_prime)], label="Ed_2prime (pu)")
#
# plt.plot(t, y[:, problem.get_var_idx(Ed1)], label="Ed1 (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Eq1)], label="Eq1 (pu)")
# plt.legend(loc='upper right', ncol=2)
# plt.xlabel("Time (s)")
# plt.ylabel("Values (pu)")
# plt.xlim([0, xlim])
# # plt.ylim([0.85, 1.15])
# plt.grid(True)
# plt.tight_layout()
# plt.show()

# Generator state variables
# plt.plot(t, y[:, problem.get_var_idx(u_gov1)], label="u_gov1 (pu)")
# plt.plot(t, y[:, problem.get_var_idx(y_subexciter)], label="y_subexciter (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Efe)], label="Efe (pu)")
# plt.plot(t, y[:, problem.get_var_idx(y_exciter1)], label="y_exciter1 (pu)")
# plt.plot(t, y[:, problem.get_var_idx(y_exciter4)], label="y_exciter4 (pu)")

# plt.legend(loc='upper right', ncol=2)
# plt.xlabel("Time (s)")
# plt.ylabel("Values (pu)")
# plt.xlim([0, xlim])
# # plt.ylim([0.85, 1.15])
# plt.grid(True)
# plt.tight_layout()
# plt.show()
