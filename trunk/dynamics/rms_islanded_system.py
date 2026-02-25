# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import cProfile
from matplotlib import pyplot as plt

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy

from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.load1_rms_template import get_load1_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms

from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
import VeraGridEngine.api as gce

###########################################################################################################################
# System with two different islands gen0-bus0-line0-bus1-load0 and gen1-bus2-line1-bus3-load1 .
# The system becomes two sets of DAEs not interconnected but solved together.
# It works since there still are n equations and n variables so the system of equations is determined.
###########################################################################################################################

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
bus2 = gce.Bus(name="Bus2", Vnom=10)
bus3 = gce.Bus(name="Bus3", Vnom=10)

grid.add_bus(bus0)
grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_bus(bus3)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.var_factory)

# Lines
line0 = gce.Line(name="line 0-1", bus_from=bus0, bus_to=bus1, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
line1 = gce.Line(name="line 2-3", bus_from=bus2, bus_to=bus3, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)

# load
load0 = gce.Load(name="load1", P=9.999999, Q=0.999999)
load1 = gce.Load(name="load2", P=9.999999, Q=0.999999)

# Generators
gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom=900,
                     x1=0.86138701, r1=0.3, freq=50.0,
                     M=10.0,
                     D=1.0,
                     omega_ref=1.0,
                     Kp=1.0,
                     Ki=10.0,
                     )
gen1 = gce.Generator(name="Gen1", P=10, vset=1.0, Snom=900,
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

line0_dynhost = DynamicModelHost()
load0_dynhost = DynamicModelHost()
gen0_dynhost = DynamicModelHost()

line1_dynhost = DynamicModelHost()
load1_dynhost = DynamicModelHost()
gen1_dynhost = DynamicModelHost()

# generator
genqec0_mdl = get_complete_generator_template(grid.var_factory).block
genqec1_mdl = get_complete_generator_template(grid.var_factory).block

# line
line0_mdl = get_line_rms_template(grid.var_factory).block
line1_mdl = get_line_rms_template(grid.var_factory).block

# load
load0_mdl = get_load_rms_template(grid.var_factory).block
load1_mdl = get_load_rms_template(grid.var_factory).block
# load1_mdl = get_load1_rms_template(grid.var_factory).block


# connection with buses

genqec0_mdl.connect([genqec0_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
genqec0_mdl.connect([genqec0_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

genqec1_mdl.connect([genqec1_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
genqec1_mdl.connect([genqec1_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

line0_mdl.connect([line0_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

line0_mdl.connect([line0_mdl.in_vars[2]], [bus1.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[3]], [bus1.rms_model.model.out_vars[1]])

line1_mdl.connect([line1_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
line1_mdl.connect([line1_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

line1_mdl.connect([line1_mdl.in_vars[2]], [bus1.rms_model.model.out_vars[0]])
line1_mdl.connect([line1_mdl.in_vars[3]], [bus1.rms_model.model.out_vars[1]])

# u_gov = find_name_in_block("u_gov1", gov1_mdl)

load0_mdl.connect([load0_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
load0_mdl.connect([load0_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

load1_mdl.connect([load1_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
load1_mdl.connect([load1_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

# external mapping

big_gen0 = Block(children=[genqec0_mdl])
big_gen1 = Block(children=[genqec1_mdl])

big_gen0.external_mapping.update({VarPowerFlowRefferenceType.P: genqec0_mdl.out_vars[0]})
big_gen0.external_mapping.update({VarPowerFlowRefferenceType.Q: genqec0_mdl.out_vars[1]})

big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genqec1_mdl.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genqec1_mdl.out_vars[1]})

# add models to dyn_host
line0_dynhost.model = line0_mdl
load0_dynhost.model = load0_mdl
gen0_dynhost.model = big_gen0

line1_dynhost.model = line1_mdl
load1_dynhost.model = load1_mdl
gen1_dynhost.model = big_gen1

# attach rms models to Veragrid objects
line0.rms_model = line0_dynhost
load0.rms_model = load0_dynhost
gen0.rms_model = gen0_dynhost

line1.rms_model = line1_dynhost
load1.rms_model = load1_dynhost
gen1.rms_model = gen1_dynhost

# apply event
# Pl0 = find_name_in_block('Pl0', load0_mdl)
# event = RmsEvent(device=load0, parameter=Pl0, time=0.1, value=-0.09)
# grid.add_rms_event(event)

grid.add_line(line0)
grid.add_load(bus=bus1, api_obj=load0)
grid.add_generator(bus=bus0, api_obj=gen0)

grid.add_line(line1)
grid.add_load(bus=bus3, api_obj=load1)
grid.add_generator(bus=bus2, api_obj=gen1)

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

profiler.disable()
profiler.dump_stats("profiling_stats.prof")

xlim = options.simulation_time

omega0 = find_name_in_block("omega", genqec0_mdl)
Pg0 = genqec0_mdl.out_vars[0]
Qg0 = genqec0_mdl.out_vars[1]
Ir0 = find_name_in_block("Ir", genqec0_mdl)
Efd0 = find_name_in_block("Efd", genqec0_mdl)
Te0 = find_name_in_block("Te", genqec0_mdl)
Vm0 = find_name_in_block("Vm", genqec0_mdl)

u_gov10 = find_name_in_block("u_gov1", genqec0_mdl)
y_subexciter0 = find_name_in_block("y_subexciter1", genqec0_mdl)
y_exciter10 = find_name_in_block("y_exciter1", genqec0_mdl)
y_exciter40 = find_name_in_block("y_exciter4", genqec0_mdl)
Efe0 = find_name_in_block("Efe", genqec0_mdl)
delta0 = find_name_in_block("delta", genqec0_mdl)

# Generator state variables
plt.plot(t, y[:, problem.get_var_idx(omega0)], label="omega (pu)")
plt.plot(t, y[:, problem.get_var_idx(delta0)], label="delta (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Vm)], label="Vm (pu)")
plt.plot(t, y[:, problem.get_var_idx(Pg0)], label="P (pu)")
plt.plot(t, y[:, problem.get_var_idx(Qg0)], label="Q (pu)")
# plt.plot(t, y[:, solver.get_var_idx(Ir)], label="Ir (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()

omega1 = find_name_in_block("omega", genqec1_mdl)
Pg1 = genqec1_mdl.out_vars[0]
Qg1 = genqec1_mdl.out_vars[1]
Ir1 = find_name_in_block("Ir", genqec1_mdl)
Efd1 = find_name_in_block("Efd", genqec1_mdl)
Te1 = find_name_in_block("Te", genqec1_mdl)
Vm1 = find_name_in_block("Vm", genqec1_mdl)

u_gov11 = find_name_in_block("u_gov1", genqec1_mdl)
y_subexciter1 = find_name_in_block("y_subexciter1", genqec1_mdl)
y_exciter11 = find_name_in_block("y_exciter1", genqec1_mdl)
y_exciter41 = find_name_in_block("y_exciter4", genqec1_mdl)
Efe1 = find_name_in_block("Efe", genqec1_mdl)
delta1 = find_name_in_block("delta", genqec1_mdl)

# Generator state variables
plt.plot(t, y[:, problem.get_var_idx(omega1)], label="omega (pu)")
plt.plot(t, y[:, problem.get_var_idx(delta1)], label="delta (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Vm)], label="Vm (pu)")
plt.plot(t, y[:, problem.get_var_idx(Pg1)], label="P (pu)")
plt.plot(t, y[:, problem.get_var_idx(Qg1)], label="Q (pu)")
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
