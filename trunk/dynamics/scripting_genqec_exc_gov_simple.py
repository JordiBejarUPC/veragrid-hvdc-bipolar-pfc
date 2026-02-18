# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import cProfile as profile
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


from VeraGridEngine.Utils.Symbolic.block_solver_no_diff import BlockSolverNoDiff
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import GenqecBuild, GovernorBuild, ExciterBuild, \
    StabilizerBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template


from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

pr = profile.Profile()
pr.disable()


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

bus0.initialize_rms()
bus1.initialize_rms()

grid.add_bus(bus0)
grid.add_bus(bus1)

# Lines
line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus1, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)

# load
load = gce.Load(P= 9.999999, Q= 0.999999)

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
# Build Rms models
######################################################################################################

# Build dynamic_model_host

line_dynhost = DynamicModelHost()
load_dynhost = DynamicModelHost()
gen_dynhost = DynamicModelHost()

# generator
genqec_mdl = block_deep_copy(get_complete_generator_template().block)

# line
line_mdl = block_deep_copy(get_line_rms_template().block)

# load
load_mdl = block_deep_copy(get_load_rms_template().block)

# connection with buses

genqec_mdl.connect([genqec_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
genqec_mdl.connect([genqec_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])


line_mdl.connect([line_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
line_mdl.connect([line_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

line_mdl.connect([line_mdl.in_vars[2]], [bus1.rms_model.model.out_vars[0]])
line_mdl.connect([line_mdl.in_vars[3]], [bus1.rms_model.model.out_vars[1]])

# u_gov = find_name_in_block("u_gov1", gov1_mdl)

load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

# external mapping

big_gen1 = Block(children=[genqec_mdl])

big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genqec_mdl.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genqec_mdl.out_vars[1]})

# add models to dyn_host
line_dynhost.model = line_mdl
load_dynhost.model = load_mdl
gen_dynhost.model = big_gen1


# attach rms models to Veragrid objects
line0.rms_model= line_dynhost
load.rms_model= load_dynhost
gen0.rms_model= gen_dynhost

# apply event
Pl0 = find_name_in_block('Pl0', load_mdl)
event = RmsEvent(device=load, parameter=Pl0, time=0.1, value=-0.09)
grid.add_rms_event(event)

grid.add_line(line0)
grid.add_load(bus=bus1, api_obj=load)
grid.add_generator(bus=bus0, api_obj=gen0)

options = gce.PowerFlowOptions(
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
res = gce.power_flow(grid, options=options)


print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

params_mapping = dict()

pr.enable()

options = RmsOptions(time_step=0.001,
                 simulation_time=1,
                 tolerance=1e-6,
                 integration_method=DynamicIntegrationMethod.BackEuler,
                 initialization_method=RmsInitializationMethod.Explicit,
                 use_init_values=False,
                 max_iter=1000,
                 verbose=0)

problem = RmsProblemDae(grid=grid,
                        options=options,
                        pf_results=res)

solver = BackEulerImplicitIntegration(
    problem=problem,
    t0=0,
    t_end=options.simulation_time,
    h=options.time_step,
    max_iter=options.max_iter
)

t, y, well_initialized, converged = solver.simulate()

pr.disable()

xlim = options.simulation_time

omega = find_name_in_block("omega", genqec_mdl)
Pg = genqec_mdl.out_vars[0]
Qg = genqec_mdl.out_vars[1]
Ir = find_name_in_block("Ir", genqec_mdl)
Efd = find_name_in_block("Efd", genqec_mdl)
Te = find_name_in_block("Te", genqec_mdl)
Vm = find_name_in_block("Vm", genqec_mdl)

u_gov1 = find_name_in_block("u_gov1", genqec_mdl)
y_subexciter = find_name_in_block("y_subexciter1", genqec_mdl)
y_exciter1 = find_name_in_block("y_exciter1", genqec_mdl)
y_exciter4 = find_name_in_block("y_exciter4", genqec_mdl)
Efe = find_name_in_block("Efe", genqec_mdl)
delta = find_name_in_block("delta", genqec_mdl)


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

pr.dump_stats('profile.pstat')


#
# Eq_prime = find_name_in_block("Eq_prime", genqec_mdl)
# Ed_prime = find_name_in_block("Ed_prime", genqec_mdl)
# Psiq_prime = find_name_in_block("Psiq_prime", genqec_mdl)
# Psid_prime = find_name_in_block("Psid_prime", genqec_mdl)
#
# Ed1 = find_name_in_block("Ed1", genqec_mdl)
# Eq1 = find_name_in_block("Eq1", genqec_mdl)

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
