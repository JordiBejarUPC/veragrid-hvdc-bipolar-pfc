#!/usr/bin/env python
"""
Debug script to check aux_block addition
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

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

# Build grid (simplified)
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

Pl0 = None
for var in load_mdl.algebraic_vars + load_mdl.state_vars + list(load_mdl.event_dict.keys()):
    if var.name == 'Pl0':
        Pl0 = var
        break

event = RmsEvent(device=load, parameter=Pl0, time=.01, value=-0.12)
grid.add_rms_event(event)

options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=0)
res = gce.power_flow(grid, options=options)

options = RmsOptions(time_step=0.001, simulation_time=0.015, tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.BackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False, max_iter=1000, verbose=0)

problem = RmsProblemDae(grid=grid, options=options, pf_results=res)

# Find the x variable (should be an algebraic variable with name 'x')
print("Looking for 'x' variable in algebraic equations...")
x_var = None
for i, eq in enumerate(problem._algebraic_eqs):
    vars_in_eq = get_expression_vars(eq)
    for v in vars_in_eq:
        if v.name == 'x':
            print(f"Found 'x' in equation {i}: {eq}")
            x_var = v
            break
    if x_var:
        break

if x_var:
    print(f"\nx variable found: uid={x_var.uid}")
    # Check if x is in algebraic vars
    in_alg = any(v.uid == x_var.uid for v in problem._algebraic_vars)
    print(f"x in algebraic_vars: {in_alg}")
    
    # Find all equations involving x
    print("\nAll equations involving x:")
    for i, eq in enumerate(problem._algebraic_eqs):
        vars_in_eq = get_expression_vars(eq)
        if any(v.uid == x_var.uid for v in vars_in_eq):
            print(f"  Eq {i}: {eq}")
else:
    print("x variable NOT FOUND!")

# Check which equations have the pattern x - (Vm - delta)
print("\n\nSearching for equation with pattern involving x...")
for i, eq in enumerate(problem._algebraic_eqs):
    eq_str = str(eq)
    if 'x' in eq_str and ('delta' in eq_str or 'Delta' in eq_str or 'Vm' in eq_str):
        print(f"Eq {i}: {eq}")

print("\nDone!")
