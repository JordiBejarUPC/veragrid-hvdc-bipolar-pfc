# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import sys, os
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))
from matplotlib import pyplot as plt

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent


from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod, DynamicEventTransitionType
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


def evaluate_rms_runtime_parameter_trace(problem: RmsProblemDae,
                                         parameter,
                                         time_values: np.ndarray) -> np.ndarray:
    """
    Evaluate one RMS runtime event parameter over explicit time samples.

    This diagnostic trace is needed to distinguish whether the ramp is already
    broken in the runtime event-parameter updater or later in the algebraic load
    equations that consume that parameter.

    :param problem: Prepared RMS problem.
    :param parameter: Runtime parameter to inspect.
    :param time_values: Time samples.
    :return: Runtime parameter trace.
    """
    runtime_index: int = problem.uid2idx_event_params[parameter.uid]
    trace: np.ndarray = np.zeros(len(time_values), dtype=float)
    sample_index: int = 0

    while sample_index < len(time_values):
        runtime_values: np.ndarray = problem._variable_parameters_values.copy()
        runtime_values = problem.def_event_params_fn(runtime_values, float(time_values[sample_index]))
        trace[sample_index] = float(runtime_values[runtime_index])
        sample_index += 1

    return trace


#####################################################################################
#                    Grid
#####################################################################################

grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

#####################################################################################
#                    Devices
#####################################################################################

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=10)

grid.add_bus(bus0)
grid.add_bus(bus1)


for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.var_factory)


# Lines
line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus1, r=0.029585, x=0.071005, b=0.03,
                 rate=900.0)
grid.add_line(line0)

# load
load = gce.Load(P=9.999999, Q=0.999999)
grid.add_load(bus=bus1, api_obj=load)

# Generators
gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom=900,
                     x1=0.86138701, r1=0.3, freq=50.0
                     )
grid.add_generator(bus=bus0, api_obj=gen0)

######################################################################################################
# Build Rms models
######################################################################################################


# generator
genqec_mdl = get_complete_generator_template_rms(grid.var_factory).block

# line
line_mdl = get_line_rms_template(grid.var_factory).block

# load
load_mdl = get_load_rms_template(grid.var_factory).block

# set models parameters
# load_mdl.set_parameter_in_model(var_name="Pl0", new_value=-0.0999999)
# load_mdl.set_parameter_in_model(var_name="Ql0", new_value=-0.009999999862208533)

######################################################################################################
# Add models to devices
######################################################################################################

set_rms_model(device=gen0, model=genqec_mdl, var_factory= grid.var_factory)

set_rms_model(device=line0, model=line_mdl, var_factory= grid.var_factory)

set_rms_model(device=load, model=load_mdl, var_factory= grid.var_factory)

######################################################################################################
# Add event
######################################################################################################
Pl0 = find_name_in_block("Pl0", load_mdl)
events_group = RmsEventsGroup("simulation1")
grid.add_rms_events_group(events_group)
# event = RmsEvent(device=load, parameter=Pl0, time=0.1,  value=-0.06, group=events_group, transition_type=DynamicEventTransitionType.Step)
event = RmsEvent(device=load, parameter=Pl0, time=0.1, end_time = 0.2, value=-0.06, group=events_group, transition_type=DynamicEventTransitionType.Ramp)
grid.add_rms_event(event)


######################################################################################################
# Power flow
######################################################################################################

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
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=1000,
                     verbose=0)

######################################################################################################
# Prepare and run simulation
######################################################################################################


problem = RmsProblemDae(grid=grid,
                        options=options,
                        pf_results=res)

problem.set_events_group(events_group)
problem.reset_boundary_update_state(0.0)


solver = BackEulerImplicitIntegration(
    problem=problem,
    t0=0,
    t_end=options.simulation_time,
    h=options.time_step,
    max_iter=options.max_iter,
)

t, y, well_initialized, converged = solver.simulate()

# results = RmsResults(
#             time_array=pd.DatetimeIndex(pd.to_datetime(solver.t * 1e9)),
#             rms_events_group_names = rms_events_group_names,
#             variables=problem.state_and_algebraic_vars,
#             uid2idx=problem.uid2idx_vars,
#             vars_glob_name2uid=problem.vars_glob_name2uid,
#             devices_vars_info=problem.get_device_vars_dict()
#             )



#
#
#
#
xlim = options.simulation_time

# The complete generator model stores the machine variables with the
# ``Genqec_rms_template`` suffix because they come from the nested generator
# block. We therefore query the real exposed variable names here.
omega = find_name_in_block("omegaGenqec_rms_template", genqec_mdl)
Pg = genqec_mdl.out_vars[0]
Qg = genqec_mdl.out_vars[1]
Ir = find_name_in_block("IRPuGenqec_rms_template", genqec_mdl)
Efd = find_name_in_block("Vf", genqec_mdl)
Te = find_name_in_block("TeGenqec_rms_template", genqec_mdl)
Vm = genqec_mdl.in_vars[0]

u_gov1 = find_name_in_block("u_gov1", genqec_mdl)
y_subexciter = find_name_in_block("y_subexciter1", genqec_mdl)
y_exciter1 = find_name_in_block("y_exciter1", genqec_mdl)
y_exciter4 = find_name_in_block("y_exciter4", genqec_mdl)
Efe = find_name_in_block("Efe", genqec_mdl)
delta = find_name_in_block("deltaGenqec_rms_template", genqec_mdl)



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


Eq_prime = find_name_in_block("Eq_primeGenqec_rms_template", genqec_mdl)
Ed_prime = find_name_in_block("Ed_primeGenqec_rms_template", genqec_mdl)
Psiq_prime = find_name_in_block("Psiq_primeGenqec_rms_template", genqec_mdl)
Psid_prime = find_name_in_block("Psid_primeGenqec_rms_template", genqec_mdl)

Ed1 = find_name_in_block("Ed1Genqec_rms_template", genqec_mdl)
Eq1 = find_name_in_block("Eq1Genqec_rms_template", genqec_mdl)

# Generator state variables
plt.plot(t, y[:, problem.get_var_idx(Eq_prime)], label="Eq_prime (pu)")
plt.plot(t, y[:, problem.get_var_idx(Ed_prime)], label="Ed_prime (pu)")
plt.plot(t, y[:, problem.get_var_idx(Psiq_prime)], label="Eq_2prime (pu)")
plt.plot(t, y[:, problem.get_var_idx(Psid_prime)], label="Ed_2prime (pu)")

plt.plot(t, y[:, problem.get_var_idx(Ed1)], label="Ed1 (pu)")
plt.plot(t, y[:, problem.get_var_idx(Eq1)], label="Eq1 (pu)")
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()

# Generator state variables
plt.plot(t, y[:, problem.get_var_idx(u_gov1)], label="u_gov1 (pu)")
plt.plot(t, y[:, problem.get_var_idx(y_subexciter)], label="y_subexciter (pu)")
plt.plot(t, y[:, problem.get_var_idx(Efe)], label="Efe (pu)")
plt.plot(t, y[:, problem.get_var_idx(y_exciter1)], label="y_exciter1 (pu)")
plt.plot(t, y[:, problem.get_var_idx(y_exciter4)], label="y_exciter4 (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()

# load P and Q
P_load_runtime = evaluate_rms_runtime_parameter_trace(problem=problem,
                                                      parameter=Pl0,
                                                      time_values=t)
P_load = find_name_in_block("Pl", load_mdl)
Q_load = find_name_in_block("Ql", load_mdl)

debug_times = np.array([0.0, 0.1, 0.125, 0.15, 0.175, 0.2, 0.25], dtype=float)
debug_trace = evaluate_rms_runtime_parameter_trace(problem=problem,
                                                   parameter=Pl0,
                                                   time_values=debug_times)
print("Pl0 debug samples:")
for debug_index in range(len(debug_times)):
    print(float(debug_times[debug_index]), float(debug_trace[debug_index]))

# Generator state variables
plt.plot(t, P_load_runtime, label="Pl0 runtime (pu)", linestyle='--')
plt.plot(t, y[:, problem.get_var_idx(P_load)], label="P load (pu)")
plt.plot(t, y[:, problem.get_var_idx(Q_load)], label="Q load (pu)")


plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Load powers (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()


