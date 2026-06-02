# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import matplotlib.pyplot as plt


import sys
import os


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from typing import Any, cast

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions

from VeraGridEngine.Utils.Symbolic.block import Block

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref

from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template

from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model

from VeraGridEngine.enumerations import (BranchImpedanceMode, DynamicIntegrationMethod, EmtInitializationMethod,
                                         EmtSolverTypes, ShuntConnectionType, SolverType)
from trunk.GridsForLoads_dynamic.gridsforloads_converter_template import (get_trafo_grid_connection_G4L,
                                                                          get_complete_load_template_G4L)
import VeraGridEngine.api as gce





def get_var_idx(problem: EmtProblemDae, name: str) -> int:
    return problem.get_var_idx(find_name_in_block(name=name, block=problem.sys.block))


def try_get_series(problem: EmtProblemDae, y_arr: np.ndarray, name: str):
    try:
        idx = get_var_idx(problem=problem, name=name)
        return y_arr[:, idx]
    except Exception:
        return None


def plot_if_available(ax, t_arr: np.ndarray, series, label: str):
    if series is not None:
        ax.plot(t_arr, series, label=label)

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


######################################################################################################
# Build grid
######################################################################################################

U       = 33000 / 1000 # V -> kV
Sb      = 2000000 / 1000000 # VA -> MVA
omega   = 2 * np.pi * 50.0

grid = gce.MultiCircuit(Sbase=Sb, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=U, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=U)

grid.add_bus(bus0)
grid.add_bus(bus1)

# Line/transformer equivalent in VeraGrid static units:
# - bus voltage base in kV
# - system base in MVA
# - branch r/x/b in p.u.
R_trf_pu = 0.1 / 10.0
X_trf_pu = 1.0 / 10.0
# The EMT template implements the shunt only on the "to" side, while the
# VeraGrid static line ``b`` is a symmetric pi-line susceptance used for PF
# and EMT initialization. Keep the matching total susceptance here.
B_sh_pu = 2.0 / 15.0
line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, r=R_trf_pu, x=X_trf_pu, b=B_sh_pu, rate=Sb)

# load
load = gce.Load(name="load",P1= Sb/3, P2= Sb/3, P3= Sb/3, Q1= 0.0, Q2= 0.0, Q3= 0.0)
load.conn = ShuntConnectionType.GroundedStar

# Generator
SCR = 3
RL  = 0.1
R_g_pu = RL / SCR
X_g_pu = 1.0 / SCR
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq = 50, r1=R_g_pu, x1=X_g_pu)

grid.add_line(line0)
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_load(bus=bus1, api_obj=load)


for bus in grid.buses:
    get_bus_emt_template(grid, bus)

######################################################################################################
# Build EMT models
######################################################################################################
gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf= grid.var_factory).block

line_mdl = get_trafo_grid_connection_G4L(vf= grid.var_factory).block

load_mdl = get_complete_load_template_G4L(vf= grid.var_factory).block

######################################################################################################
# Add models to devices
######################################################################################################

set_emt_model(device=gen0, model=gen_mdl, var_factory= grid.var_factory)

set_emt_model(device=line0, model=line_mdl, var_factory= grid.var_factory)

set_emt_model(device=load, model=load_mdl, var_factory= grid.var_factory)

######################################################################################################
# PowerFlow
######################################################################################################

pf_options = PowerFlowOptions(
    solver_type=SolverType.NR,
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
    branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
    distributed_slack=False,
    ignore_single_node_islands=False,
    trust_radius=1.0,
    backtracking_parameter=0.05,
    use_stored_guess=False,
    initialize_angles=False,
    generate_report=False,
)
# Balanced powerflow
power_flow = PowerFlowDriver(grid, pf_options)
power_flow.run()
res = power_flow.results
print("Balanced power flow results")
print("res.bus_names = ", res.bus_names)
print("res.branch_names = ", res.branch_names)
print("res.bus_types = ", res.bus_types)
print("res.voltage_A = ", res.voltage)
print("res.Sbus_A = ", res.Sbus)
print("res.Sf_A = ", res.Sf)
print("res.St_A = ", res.St)

print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

######################################################################################################
# EMT options and problem
######################################################################################################


options = EmtOptions(time_step = 5e-6,
                     simulation_time =  0.01, # s
                     tolerance = 1e-6,
                     solver_type = EmtSolverTypes.StructuralAD,
                     initialization_method = EmtInitializationMethod.Explicit,
                     integration_method = DynamicIntegrationMethod.DaeTrapezoidal,
                     verbose = 1)

problem = EmtProblemDae(grid=grid,
                              options=options,
                              pf_results_3ph=None,
                              pf_results=res)

print(problem.initialization_report.method_requested)
print(problem.initialization_report.method_used)
print(problem.initialization_report.status)
print(problem.initialization_report.newton_iterations)
print(problem.initialization_report.pseudo_transient_steps)
print(problem.initialization_report.message)

DENSE_THRESHOLD = 0


if options.solver_type == EmtSolverTypes.Automatic:
    solver = StructuralVectorizedSolver(problem=problem,
                                        t0=0.0,
                                        t_end=options.simulation_time,
                                        h=options.time_step,
                                        method=options.integration_method,
                                        pred_method=DynamicIntegrationMethod.OdeEuler,
                                        dense_threshold=DENSE_THRESHOLD,
                                        verbose=True,
                                        auto_vectorization=False)
elif options.solver_type == EmtSolverTypes.StructuralCompiled:
    solver = StructuralCompiledSolver(problem=problem,
                                      t0=0.0,
                                      t_end=options.simulation_time,
                                      h=options.time_step,
                                      method=options.integration_method,
                                      pred_method=DynamicIntegrationMethod.OdeEuler,
                                      dense_threshold=DENSE_THRESHOLD,
                                      verbose=True)
elif options.solver_type == EmtSolverTypes.Symbolic:
    solver = JitSymbolicSolver(problem=problem,
                               t0=0.0,
                               t_end=options.simulation_time,
                               h=options.time_step,
                               method=options.integration_method,
                               pred_method=DynamicIntegrationMethod.OdeEuler,
                               verbose=True)
elif options.solver_type == EmtSolverTypes.StructuralAD:
    solver = JitAdSolver(problem=problem,
                         t0=0.0,
                         t_end=options.simulation_time,
                         h=options.time_step,
                         method=options.integration_method,
                         pred_method=DynamicIntegrationMethod.OdeEuler,
                         verbose=True)
else:
    raise ValueError(f"Unknown options.solver_type '{options.solver_type}'")
boundary_updater = cast(Any, problem)
t_arr: np.ndarray
y_arr: np.ndarray
dy_arr: np.ndarray
t_arr, y_arr, dy_arr, well_initialized , converged= solver.simulate(boundary_updater=boundary_updater)

print(f"EMT well initialized: {well_initialized}")
print(f"EMT converged: {converged}")
if hasattr(solver, "get_last_runtime_stats"):
    print(solver.get_last_runtime_stats())


# Core diagnostics for the GFM-load system.
fig, axes = plt.subplots(4, 2, figsize=(14, 12), sharex=True)
axes = axes.ravel()

# 1) PCC voltages and currents
for name in ["v_A_Bus1_emt_template", "v_B_Bus1_emt_template", "v_C_Bus1_emt_template"]:
    plot_if_available(axes[0], t_arr, try_get_series(problem, y_arr, name), name)
axes[0].set_title("Grid-Side AC Voltages")
axes[0].grid(True)
if axes[0].lines:
    axes[0].legend(loc="best")

for name in ["i_f_A_G4L_grid_side_converter", "i_f_B_G4L_grid_side_converter", "i_f_C_G4L_grid_side_converter"]:
    plot_if_available(axes[1], t_arr, try_get_series(problem, y_arr, name), name)
axes[1].set_title("Grid-Side AC Currents")
axes[1].grid(True)
if axes[1].lines:
    axes[1].legend(loc="best")

# 2) DC-link behavior
for name in ["v_dc_G4L_load_side_converter", "i_dc_G4L_grid_side_converter", "i_dc_L_G4L_load_side_converter_control"]:
    plot_if_available(axes[2], t_arr, try_get_series(problem, y_arr, name), name)
axes[2].set_title("DC-Link Variables")
axes[2].grid(True)
if axes[2].lines:
    axes[2].legend(loc="best")

for name in ["Pac_bus_G4L_grid_side_converter", "Pac_G4L_grid_side_converter", "p_dc_G4L_load_side_converter_control"]:
    plot_if_available(axes[3], t_arr, try_get_series(problem, y_arr, name), name)
axes[3].set_title("Power Variables")
axes[3].grid(True)
if axes[3].lines:
    axes[3].legend(loc="best")

# 3) Synchronization variables
for name in ["phase_pll_G4L_PLL", "theta_pll_G4L_PLL"]:
    plot_if_available(axes[4], t_arr, try_get_series(problem, y_arr, name), name)
axes[4].set_title("PLL / VSM Angles")
axes[4].grid(True)
if axes[4].lines:
    axes[4].legend(loc="best")

for name in ["omega_pll_G4L_PLL", "w_pll_G4L_PLL", "y_G4L_PLL"]:
    plot_if_available(axes[5], t_arr, try_get_series(problem, y_arr, name), name)
axes[5].set_title("PLL / VSM Frequencies")
axes[5].grid(True)
if axes[5].lines:
    axes[5].legend(loc="best")

# 4) Controller internals and branch states
for name in ["i_q_lim_G4L_current_limiter", "i_d_lim_G4L_current_limiter", "v_q_G4L_clark_park_transforms_qd", "v_d_G4L_clark_park_transforms_qd"]:
    plot_if_available(axes[6], t_arr, try_get_series(problem, y_arr, name), name)
axes[6].set_title("Current Limits and dq Voltages")
axes[6].grid(True)
if axes[6].lines:
    axes[6].legend(loc="best")

for name in ["i_cap_t_A_G4L_transformer", "q_t_A_G4L_transformer", "i_ser_A_G4L_transformer"]:
    plot_if_available(axes[7], t_arr, try_get_series(problem, y_arr, name), name)
axes[7].set_title("Transformer/Filter Branch A")
axes[7].grid(True)
if axes[7].lines:
    axes[7].legend(loc="best")

for ax in axes:
    ax.set_xlabel("Time [s]")

fig.tight_layout()
plt.show()
