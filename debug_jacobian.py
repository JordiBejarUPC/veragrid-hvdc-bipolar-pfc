#!/usr/bin/env python
"""
Debug script for Jacobian calculation in multilinear_models_validation
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

import numpy as np
import cProfile as profile

import VeraGridEngine.api as gce
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy
from VeraGridEngine.Templates.Rms.generation_tensygrid_ml import GenqecBuild, GovernorBuild, ExciterBuild, \
    StabilizerBuild, get_complete_generator_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


# Build grid
grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=10)

grid.add_bus(bus0)
grid.add_bus(bus1)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.var_factory)

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

# Build dynamic_model_host
line_dynhost = DynamicModelHost()
load_dynhost = DynamicModelHost()
gen_dynhost = DynamicModelHost()

# line
line0_mdl = get_line_rms_template(grid.var_factory).block

# load
load_mdl = get_load_rms_template(grid.var_factory).block

# generator
genqec1_mdl = get_complete_generator_template(grid.var_factory).block

# connection with buses
genqec1_mdl.connect([genqec1_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
genqec1_mdl.connect([genqec1_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

line0_mdl.connect([line0_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

line0_mdl.connect([line0_mdl.in_vars[2]], [bus1.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[3]], [bus1.rms_model.model.out_vars[1]])

u_gov = find_name_in_block("u_gov1", genqec1_mdl)

load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

# external mapping
big_gen1 = Block(children=[genqec1_mdl])
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genqec1_mdl.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genqec1_mdl.out_vars[1]})

# add models to dyn_host
line_dynhost.model = line0_mdl
load_dynhost.model = load_mdl
gen_dynhost.model = big_gen1

# attach rms models to Veragrid objects
line0.rms_model = line_dynhost
load.rms_model = load_dynhost
gen0.rms_model = gen_dynhost

Pl0 = find_name_in_block('Pl0', load_mdl)
event = RmsEvent(device=load, parameter=Pl0, time=.01, value=-0.12)
grid.add_rms_event(event)

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

options = RmsOptions(time_step=0.001,
                     simulation_time=0.015,  # Just run until the event
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.BackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=1000,
                     verbose=0)

problem = RmsProblemDae(grid=grid,
                        options=options,
                        pf_results=res)

# Debug: Check the dt parameter value
print(f"\nDebug: Variable parameters count: {problem.get_variable_parameter_number()}")
print(f"Debug: dt value from problem: {problem.get_dt_value()}")

# Debug: Check compiler names dict for dt
dt_var = problem._dt
print(f"Debug: dt var uid: {dt_var.uid}")
print(f"Debug: dt in compiler_names_dict: {problem._compiler_names_dict.get(dt_var.uid, 'NOT FOUND')}")

# Get initial state
x0 = problem.get_x0()
dx0 = np.zeros(problem.get_diff_var_number(), dtype=float)

# Update variable params at t=0.01 (when event happens)
problem.update_variable_params(t=0.01)
print(f"Debug: dt value after update at t=0.01: {problem.get_dt_value()}")

# Now compute Jacobian
h = 0.001
j11 = problem.get_j11(x0, dx0, h)
j12 = problem.get_j12(x0, dx0, h)
j21 = problem.get_j21(x0, dx0, h)
j22 = problem.get_j22(x0, dx0, h)

print(f"\nDebug: J11 shape: {j11.shape}, max: {np.max(np.abs(j11.data)):.6e}")
print(f"Debug: J12 shape: {j12.shape}, max: {np.max(np.abs(j12.data)):.6e}")
print(f"Debug: J21 shape: {j21.shape}, max: {np.max(np.abs(j21.data)):.6e}")
print(f"Debug: J22 shape: {j22.shape}, max: {np.max(np.abs(j22.data)):.6e}")

# Check for any extreme values
print(f"\nDebug: J11 data sample: {j11.data[:10] if len(j11.data) > 0 else 'empty'}")
print(f"Debug: J12 data sample: {j12.data[:10] if len(j12.data) > 0 else 'empty'}")
print(f"Debug: J21 data sample: {j21.data[:10] if len(j21.data) > 0 else 'empty'}")
print(f"Debug: J22 data sample: {j22.data[:10] if len(j22.data) > 0 else 'empty'}")

# Look for the problematic values
large_threshold = 1e10
for name, jac in [('J11', j11), ('J12', j12), ('J21', j21), ('J22', j22)]:
    if len(jac.data) > 0:
        large_mask = np.abs(jac.data) > large_threshold
        if np.any(large_mask):
            large_indices = np.where(large_mask)[0]
            print(f"\nDebug: {name} has {len(large_indices)} values > {large_threshold:.0e}")
            print(f"Debug: Large values in {name}: {jac.data[large_indices][:5]}")

print("\nTest completed successfully!")
