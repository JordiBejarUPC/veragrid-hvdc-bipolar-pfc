#!/usr/bin/env python
"""
Test SymbolicJacobian vs RMSCompiler
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

import numpy as np
import scipy.sparse as sp

import VeraGridEngine.api as gce
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
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
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian
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

print("Building compiler names dict for SymbolicJacobian...")
# Build compiler names dict
compiler_names_dict = problem._compiler_names_dict.copy()
alias_names_dict = problem._alias_names_dict.copy()

# Add h
dt_var = problem._dt
h_var = Var('h')
compiler_names_dict[h_var.uid] = 'h'
alias_names_dict[h_var.uid] = 'h'

# Add diff vars
for i, dv in enumerate(problem._diff_vars):
    compiler_names_dict[dv.uid] = f"diff[{i}]"
    alias_names_dict[dv.uid] = f"diff_{i}"

print("Testing SymbolicJacobian for J21...")
# Test SymbolicJacobian for J21 (algebraic eqs w.r.t. state vars)
j21_legacy = SymbolicJacobian(
    eqs=problem._algebraic_eqs,
    variables=problem._state_vars,
    compiler_names_dict=compiler_names_dict,
    alias_names_dict=alias_names_dict,
    VARS_NAME="vars",
    DIFF_NAME="diff",
    EVENT_PARAMS_NAME="vprms",
    PARAMS_NAME="cprms",
    dt=dt_var,
    use_jit=False  # Disable JIT for testing
)

# Evaluate
# Need to build full param arrays
cprms = problem._constant_params
vprms = problem._variable_parameters_values

# Call legacy jacobian
j21_legacy_val = j21_legacy(x0, dx0, vprms, cprms, h)
j21_legacy_dense = j21_legacy_val.toarray()

# Compare with RMSCompiler J21
j21_rms = problem.get_j21(x0, dx0, h)
j21_rms_dense = j21_rms.toarray()

print(f"\nLegacy J21 shape: {j21_legacy_dense.shape}")
print(f"RMS J21 shape: {j21_rms_dense.shape}")

# Find non-zero rows in legacy but not in RMS
print("\n=== Checking row 39 (index 33 in algebraic eqs) ===")
row_idx = 33  # This is row 39 in full Jacobian
print(f"Legacy row {row_idx}: {j21_legacy_dense[row_idx, :]}")
print(f"RMS row {row_idx}: {j21_rms_dense[row_idx, :]}")

print("\n=== Comparison ===")
diff = j21_legacy_dense - j21_rms_dense
max_diff = np.max(np.abs(diff))
print(f"Max difference: {max_diff:.6e}")

# Find locations of differences
threshold = 1e-6
rows, cols = np.where(np.abs(diff) > threshold)
if len(rows) > 0:
    print(f"\nLocations with |diff| > {threshold}:")
    for r, c in zip(rows[:10], cols[:10]):
        print(f"  [{r}, {c}]: legacy={j21_legacy_dense[r, c]:.6e}, rms={j21_rms_dense[r, c]:.6e}, diff={diff[r, c]:.6e}")

print("\nDone!")
