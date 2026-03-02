# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import cProfile
import pstats
import numpy as np

import sys
import os

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




grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=10)

grid.add_bus(bus0)
grid.add_bus(bus1)

# Lines
line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)
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
tower.add_wire_relationship(wire=wire, xpos=0, ypos=27.5, phase=2)
tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
tower.compute()

# Aplicar física a la línea
line0.apply_template(tower, grid.Sbase, grid.fBase)

# load
P= 9.999999
Q= 0.999999
load = gce.Load(name="load",P1= P/3, P2= P/3, P3= P/3, Q1= Q/3, Q2= Q/3, Q3= Q/3)
load.conn = ShuntConnectionType.GroundedStar

# Generators
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=900)

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
gen_mdl = get_generator_emt_template(grid.var_factory).block

# line
line_mdl = get_pi_line_emt_template(grid = grid, line = line0).block

# load
load_mdl = get_load_ZIP_3ph_emt_template(vf = grid.var_factory).block

# connection with buses
gen_mdl.connect([gen_mdl.in_vars[0]], [bus0.emt_model.model.out_vars[0]]) # v_A
gen_mdl.connect([gen_mdl.in_vars[1]], [bus0.emt_model.model.out_vars[1]]) # v_B
gen_mdl.connect([gen_mdl.in_vars[2]], [bus0.emt_model.model.out_vars[2]]) # v_C


line_mdl.connect([line_mdl.in_vars[0]], [bus0.emt_model.model.out_vars[0]]) # line vf_A
line_mdl.connect([line_mdl.in_vars[1]], [bus0.emt_model.model.out_vars[1]]) # line vf_B
line_mdl.connect([line_mdl.in_vars[2]], [bus0.emt_model.model.out_vars[2]]) # line vf_C

line_mdl.connect([line_mdl.in_vars[3]], [bus1.emt_model.model.out_vars[0]]) # line vt_A
line_mdl.connect([line_mdl.in_vars[4]], [bus1.emt_model.model.out_vars[1]]) # line vt_B
line_mdl.connect([line_mdl.in_vars[5]], [bus1.emt_model.model.out_vars[2]]) # line vt_C

# u_gov = find_name_in_block("u_gov1", gov1_mdl)

load_mdl.connect([load_mdl.in_vars[0]], [bus1.emt_model.model.out_vars[0]]) # v_A
load_mdl.connect([load_mdl.in_vars[1]], [bus1.emt_model.model.out_vars[1]]) # v_B
load_mdl.connect([load_mdl.in_vars[2]], [bus1.emt_model.model.out_vars[2]]) # v_C

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

options = EmtOptions(time_step = 5e-6,
                     simulation_time =  0.01,  #5e-6*10, # s
                     tolerance = 1e-6,
                     solver = EmtSolverTypes.Symbolic,
                     integration_method = DynamicIntegrationMethod.DaeTrapezoidal)


problem = EmtProblemDae(grid=grid,
                        options=options,
                        pf_results=res)
problem.set_newton_trace_collector(NewtonTraceCollector())

vars = problem.get_state_vars() + problem.get_algebraic_vars()
print(vars)

df = problem.get_init_guess_table()
print(df)


solver = JitSymbolicSolver(problem = problem,
                           t0 = 0.0,
                           t_end = options.simulation_time,
                           h = options.time_step,
                           method=options.integration_method,
                           verbose = True)

x0 = problem.get_x0()
print("len(x0) =", len(x0))
print("nans =", np.isnan(x0).sum())
print("infs =", np.isinf(x0).sum())
print("nonzeros =", np.count_nonzero(x0))
print("len(init_guess) =", len(problem.init_guess))

# solver = JitAdSolver(problem = problem,
#                      t0 = 0.0,
#                      t_end = options.simulation_time,
#                      h = options.time_step,
#                      method_str=options.integration_method,
#                      verbose = True)
#
# solver = StructuralVectorizedSolver(problem = problem,
#                                     t0 = 0.0,
#                                     t_end = options.simulation_time,
#                                     h = options.time_step,
#                                     method_str=options.integration_method,
#                                     verbose = True)

t, y = solver.simulate()

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

# xlim = options.simulation_time
#
# omega = find_name_in_block("omega", gen_mdl)
# Pg = gen_mdl.out_vars[0]
# Qg = gen_mdl.out_vars[1]
# Ir = find_name_in_block("Ir", gen_mdl)
# Efd = find_name_in_block("Efd", gen_mdl)
# Te = find_name_in_block("Te", gen_mdl)
# Vm = find_name_in_block("Vm", gen_mdl)
#
# u_gov1 = find_name_in_block("u_gov1", gen_mdl)
# y_subexciter = find_name_in_block("y_subexciter1", gen_mdl)
# y_exciter1 = find_name_in_block("y_exciter1", gen_mdl)
# y_exciter4 = find_name_in_block("y_exciter4", gen_mdl)
# Efe = find_name_in_block("Efe", gen_mdl)
# delta = find_name_in_block("delta", gen_mdl)
#
#
# # Generator state variables
# plt.plot(t, y[:, problem.get_var_idx(omega)], label="omega (pu)")
# plt.plot(t, y[:, problem.get_var_idx(delta)], label="delta (pu)")
# # plt.plot(t, y[:, problem.get_var_idx(Vm)], label="Vm (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Pg)], label="P (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Qg)], label="Q (pu)")
# # plt.plot(t, y[:, solver.get_var_idx(Ir)], label="Ir (pu)")
#
# plt.legend(loc='upper right', ncol=2)
# plt.xlabel("Time (s)")
# plt.ylabel("Values (pu)")
# plt.xlim([0, xlim])
# # plt.ylim([0.85, 1.15])
# plt.grid(True)
# plt.tight_layout()
# plt.show()



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
