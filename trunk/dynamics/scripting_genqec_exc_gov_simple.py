# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import cProfile
import copy

import time
import sys, os
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))
import pandas as pd
from matplotlib import pyplot as plt

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.templates_common_functions import set_rms_model
from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup

from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
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
    initialize_bus_rms(bus, vf=grid.rms_var_factory)


# Lines
line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus1, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
grid.add_line(line0)

# load
load = gce.Load(P=9.999999, Q=0.999999)
grid.add_load(bus=bus1, api_obj=load)

# Generators
gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom=900,
                     x1=0.86138701, r1=0.3, freq=50.0,
                     M=10.0,
                     D=1.0,
                     omega_ref=1.0,
                     Kp=1.0,
                     Ki=10.0,
                     )
grid.add_generator(bus=bus0, api_obj=gen0)

######################################################################################################
# Build Rms models
######################################################################################################


# generator
genqec_mdl = get_complete_generator_template_rms(grid.rms_var_factory).block

# line
line_mdl = get_line_rms_template(grid.rms_var_factory).block

# load
load_mdl = get_load_rms_template(grid.rms_var_factory).block

# set models parameters
load_mdl.set_parameter_in_model(var_name="Pl0", new_value=-0.0999999)
load_mdl.set_parameter_in_model(var_name="Ql0", new_value=-0.009999999862208533)

######################################################################################################
# Add models to devices
######################################################################################################

set_rms_model(device=gen0, model=genqec_mdl, var_factory= grid.rms_var_factory)

set_rms_model(device=line0, model=line_mdl, var_factory= grid.rms_var_factory)

set_rms_model(device=load, model=load_mdl, var_factory= grid.rms_var_factory)


######################################################################################################
# Create event
######################################################################################################

Pl0 = find_name_in_block('Pl0', load_mdl)
events_group = RmsEventsGroup(name="simulation1")
grid.add_rms_events_group(events_group)
event = RmsEvent(device=load, parameter=Pl0, time=0.1, value=-0.098, group=events_group)
grid.add_rms_event(event)

rms_events_group_names = np.array([events_group.name], dtype=str)

# choose variables to save values
# vars_to_save = list()
# vars_to_save.extend(grid.var_factory.get_vars_to_save(gen0, ["delta", "omega"]))
# vars_to_save.extend(grid.var_factory.get_vars_to_save(load, ["Pl", "Ql"]))
#
#
# uid_save = [var.uid for var in vars_to_save]



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


solver = BackEulerImplicitIntegration(
    problem=problem,
    t0=0,
    t_end=options.simulation_time,
    h=options.time_step,
    max_iter=options.max_iter,
)

t, y, well_initialized, converged = solver.simulate()

results = RmsResults(
            time_array=pd.DatetimeIndex(pd.to_datetime(solver.t * 1e9)),
            rms_events_group_names = rms_events_group_names,
            variables=problem.state_and_algebraic_vars,
            uid2idx=problem.uid2idx_vars,
            vars_glob_name2uid=problem.vars_glob_name2uid,
            devices_vars_info=problem.get_device_vars_dict()
            )

xlim = options.simulation_time


def series_from_var(var_name: str, block: Block):
    var = find_name_in_block(var_name, block)
    if var is None:
        return None
    return y[:, problem.get_var_idx(var)]


omega = series_from_var("omega", genqec_mdl)
delta = series_from_var("delta", genqec_mdl)
pg = y[:, problem.get_var_idx(genqec_mdl.out_vars[0])]
qg = y[:, problem.get_var_idx(genqec_mdl.out_vars[1])]
pl = series_from_var("Pl", load_mdl)
ql = series_from_var("Ql", load_mdl)

fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

if omega is not None:
    axes[0].plot(t, omega, label="omega")
if delta is not None:
    axes[0].plot(t, delta, label="delta")
axes[0].set_ylabel("Rotor")
axes[0].grid(True)

axes[1].plot(t, pg, label="Pg")
axes[1].plot(t, qg, label="Qg")
axes[1].set_ylabel("Generator (pu)")
axes[1].grid(True)

if pl is not None:
    axes[2].plot(t, pl, label="Pl")
if ql is not None:
    axes[2].plot(t, ql, label="Ql")
axes[2].set_ylabel("Load (pu)")
axes[2].set_xlabel("Time (s)")
axes[2].grid(True)

for ax in axes:
    ax.axvline(x=event.time, color="tab:red", linestyle="--", linewidth=1.0, label="event")
    ax.set_xlim([0, xlim])

for ax in axes:
    ax.legend(loc="best")

plt.tight_layout()
plt.show()
