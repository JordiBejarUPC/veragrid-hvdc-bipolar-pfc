#!/usr/bin/env python
"""
Debug Jacobian differences - identify specific equations and variables
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

import numpy as np
import scipy.sparse as sp

import VeraGridEngine.api as gce
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise, get_expression_vars
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy
from VeraGridEngine.Templates.Rms.generation_tensygrid_ml import get_complete_generator_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
from VeraGridEngine.Utils.Sparse.csc import pack_4_by_4_scipy


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
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=10)
grid.add_bus(bus0)
grid.add_bus(bus1)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.var_factory)

line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus1, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
grid.add_line(line0)

load = gce.Load(P=9.999999, Q=0.999999)
grid.add_load(bus=bus1, api_obj=load)

gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom=900, x1=0.86138701, r1=0.3, freq=50.0, M=10.0, D=1.0, omega_ref=1.0, Kp=1.0, Ki=10.0)
grid.add_generator(bus=bus0, api_obj=gen0)

# Build models
line_dynhost = DynamicModelHost()
load_dynhost = DynamicModelHost()
gen_dynhost = DynamicModelHost()

line0_mdl = get_line_rms_template(grid.var_factory).block
load_mdl = get_load_rms_template(grid.var_factory).block
genqec1_mdl = get_complete_generator_template(grid.var_factory).block

genqec1_mdl.connect([genqec1_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
genqec1_mdl.connect([genqec1_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])
line0_mdl.connect([line0_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])
line0_mdl.connect([line0_mdl.in_vars[2]], [bus1.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[3]], [bus1.rms_model.model.out_vars[1]])
load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

big_gen1 = Block(children=[genqec1_mdl])
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genqec1_mdl.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genqec1_mdl.out_vars[1]})

line_dynhost.model = line0_mdl
load_dynhost.model = load_mdl
gen_dynhost.model = big_gen1

line0.rms_model = line_dynhost
load.rms_model = load_dynhost
gen0.rms_model = gen_dynhost

Pl0 = find_name_in_block('Pl0', load_mdl)
event = RmsEvent(device=load, parameter=Pl0, time=.01, value=-0.12)
grid.add_rms_event(event)

options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=0)
res = gce.power_flow(grid, options=options)

options = RmsOptions(time_step=0.001, simulation_time=0.015, tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.BackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False, max_iter=1000, verbose=0)

problem = RmsProblemDae(grid=grid, options=options, pf_results=res)

# Get initial state
x0 = problem.get_x0()
dx0 = np.zeros(problem.get_diff_var_number(), dtype=float)
h = 0.001

# Update to t=0.01 (when event happens)
problem.update_variable_params(t=0.01)

# Print variable ordering
print("=== Variable Ordering ===")
print(f"\nState variables ({len(problem._state_vars)}):")
for i, v in enumerate(problem._state_vars):
    print(f"  {i}: {v.name} (uid={v.uid})")

print(f"\nAlgebraic variables (first 20 of {len(problem._algebraic_vars)}):")
for i, v in enumerate(problem._algebraic_vars[:20]):
    print(f"  {i+len(problem._state_vars)}: {v.name} (uid={v.uid})")

# Print equation ordering
print(f"\n=== Equation Ordering ===")
print(f"\nState equations ({len(problem._state_eqs)}):")
for i, eq in enumerate(problem._state_eqs):
    print(f"  {i}: {eq}")

print(f"\nAlgebraic equations (first 20 of {len(problem._algebraic_eqs)}):")
for i, eq in enumerate(problem._algebraic_eqs[:20]):
    print(f"  {i+len(problem._state_eqs)}: {eq}")

# Now look at specific problematic equations
print("\n\n=== Problematic Equations ===")

# Row 39, 40 (algebraic eqs 33, 34)
for row_idx in [39, 40, 42, 70]:
    if row_idx < len(problem._state_eqs):
        eq = problem._state_eqs[row_idx]
        eq_type = "state"
    else:
        eq = problem._algebraic_eqs[row_idx - len(problem._state_eqs)]
        eq_type = "algebraic"
    
    print(f"\nRow {row_idx} ({eq_type}):")
    print(f"  Equation: {eq}")
    vars_in_eq = get_expression_vars(eq)
    print(f"  Variables in eq:")
    for v in vars_in_eq:
        base_info = f", base={v.base_var.name}" if v.base_var else ""
        diff_info = f", diff_order={v.diff_order}" if hasattr(v, 'diff_order') else ""
        print(f"    {v.name} (uid={v.uid}{base_info}{diff_info})")

print("\n\n=== Variable x (the base of d_delta) ===")
# Find variable x
x_var = None
for v in problem._algebraic_vars:
    if v.name == 'x':
        x_var = v
        break

if x_var:
    print(f"x variable: uid={x_var.uid}")
    print(f"x is at index: {problem._state_vars.index(x_var) if x_var in problem._state_vars else problem._algebraic_vars.index(x_var) + len(problem._state_vars)}")
    
    # Find which equations involve x
    print("\nEquations involving x:")
    for i, eq in enumerate(problem._state_eqs + problem._algebraic_eqs):
        vars_in_eq = get_expression_vars(eq)
        if any(v.uid == x_var.uid for v in vars_in_eq):
            eq_type = "state" if i < len(problem._state_eqs) else "algebraic"
            print(f"  Row {i} ({eq_type}): {eq}")

print("\nDone!")
