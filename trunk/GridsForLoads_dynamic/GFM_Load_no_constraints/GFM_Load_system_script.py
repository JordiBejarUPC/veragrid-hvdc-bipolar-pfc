# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np


import sys
import os

from VeraGridEngine import get_generator_thevenin_rl_emt_template_with_ref

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import matplotlib.pyplot as plt
from typing import Any, Dict, List, Tuple, cast

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions

from VeraGridEngine.Utils.Symbolic.block import Block

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver

from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template

from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.enumerations import (BranchImpedanceMode, DynamicIntegrationMethod, EmtInitializationMethod,
                                         EmtSolverTypes, ShuntConnectionType, SolverType)
from trunk.GridsForLoads_dynamic.gridsforloads_converter_template import (get_trafo_grid_connection_G4L,
                                                                          get_complete_load_template_G4L)
import VeraGridEngine.api as gce

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
Vdc_ref = 1200 / 1000 # V -> kV

grid = gce.MultiCircuit(Sbase=Sb, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=U, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=U)

grid.add_bus(bus0)
grid.add_bus(bus1)

# Lines
Zbase = U*U/Sb
L_trf = Zbase/(10*omega)
R_trf = (Zbase/10)*0.1
C_f  = 1 / (15*U*U/(Sb*omega))
X = omega * L_trf
B =1 / (omega * C_f)
line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, r=R_trf, x= X, b=B , rate=900.0)

# load
load = gce.Load(name="load",P1= Sb/3, P2= Sb/3, P3= Sb/3, Q1= 0.0, Q2= 0.0, Q3= 0.0)
load.conn = ShuntConnectionType.GroundedStar

# Generator
SCR = 3
RL  = 0.1
L_g = Zbase/(SCR*omega)
R_g = (Zbase/SCR)*RL
Xl_g = omega * L_g
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq = 50, r1=R_g, x1=Xl_g)

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
                     initialization_method = EmtInitializationMethod.Auto,
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
solver = StructuralVectorizedSolver(problem = problem,
                                          t0 = 0.0,
                                          t_end = options.simulation_time,
                                          h = options.time_step,
                                          method=options.integration_method,
                                          pred_method=DynamicIntegrationMethod.OdeEuler,
                                          dense_threshold=DENSE_THRESHOLD,
                                          verbose = True,
                                          auto_vectorization=False)
boundary_updater = cast(Any, problem)
t_arr: np.ndarray
y_arr: np.ndarray
dy_arr: np.ndarray
t_arr, y_arr, dy_arr, well_initialized , converged= solver.simulate(boundary_updater=boundary_updater)





