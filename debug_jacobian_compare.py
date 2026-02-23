#!/usr/bin/env python
"""
Compare symbolic Jacobian with numerical Jacobian
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
from VeraGridEngine.Utils.Sparse.csc import pack_4_by_4_scipy


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var
    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


def compute_numerical_jacobian(problem, x, dx, h, epsilon=1e-8):
    """
    Compute Jacobian numerically using finite differences
    """
    n_vars = len(x)
    
    # Compute RHS at current point
    f_algeb = problem.rhs_algebraic(x, dx)
    if problem.get_states_number() > 0:
        f_state = problem.rhs_state(x, dx)
        f_state_update = x[:problem.get_states_number()] - x[:problem.get_states_number()] - h * f_state
        rhs = np.r_[f_state_update, f_algeb]
    else:
        rhs = f_algeb
    
    # Numerical Jacobian
    J_num = np.zeros((len(rhs), n_vars))
    
    for j in range(n_vars):
        x_plus = x.copy()
        x_plus[j] += epsilon
        
        # Compute dx for perturbed state
        if problem.get_states_number() > 0:
            dx_plus = (x_plus - x) / h
        else:
            dx_plus = dx
        
        # Compute RHS at perturbed point
        f_algeb_plus = problem.rhs_algebraic(x_plus, dx_plus)
        if problem.get_states_number() > 0:
            f_state_plus = problem.rhs_state(x_plus, dx_plus)
            f_state_update_plus = x_plus[:problem.get_states_number()] - x[:problem.get_states_number()] - h * f_state_plus
            rhs_plus = np.r_[f_state_update_plus, f_algeb_plus]
        else:
            rhs_plus = f_algeb_plus
        
        # Finite difference
        J_num[:, j] = (rhs_plus - rhs) / epsilon
    
    return J_num


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

print("Computing symbolic Jacobian...")
# Compute symbolic Jacobian
if problem.get_states_number() > 0:
    j11_val = problem.get_j11(x0, dx0, h)
    j12_val = problem.get_j12(x0, dx0, h)
    j21_val = problem.get_j21(x0, dx0, h)
    j22_val = problem.get_j22(x0, dx0, h)
    
    I = sp.eye(m=problem.get_states_number(), n=problem.get_states_number())
    j11 = (I - h * j11_val).tocsc()
    j12 = -h * j12_val
    j21 = j21_val
    j22 = j22_val
    
    J_sym = pack_4_by_4_scipy(j11, j12, j21, j22)
else:
    J_sym = problem.get_j22(x0, dx0, h)

J_sym_dense = J_sym.toarray()

print("Computing numerical Jacobian...")
# Compute numerical Jacobian
J_num_dense = compute_numerical_jacobian(problem, x0, dx0, h)

print(f"\nJacobian shape: {J_sym_dense.shape}")
print(f"Symbolic Jacobian nnz: {J_sym.nnz}")

# Compare
print("\n=== Comparison ===")
print(f"Symbolic max abs: {np.max(np.abs(J_sym_dense)):.6e}")
print(f"Numerical max abs: {np.max(np.abs(J_num_dense)):.6e}")

# Compute difference
diff = J_sym_dense - J_num_dense
max_diff = np.max(np.abs(diff))
mean_diff = np.mean(np.abs(diff))

print(f"\nMax absolute difference: {max_diff:.6e}")
print(f"Mean absolute difference: {mean_diff:.6e}")

# Find locations of large differences
threshold = 1e-3
large_diff_mask = np.abs(diff) > threshold
large_diff_indices = np.argwhere(large_diff_mask)

print(f"\nNumber of entries with |diff| > {threshold}: {len(large_diff_indices)}")

if len(large_diff_indices) > 0:
    print("\nTop 10 largest differences:")
    flat_diff = np.abs(diff).flatten()
    top_indices = np.argsort(flat_diff)[-10:][::-1]
    
    for idx in top_indices:
        row = idx // diff.shape[1]
        col = idx % diff.shape[1]
        print(f"  J[{row}, {col}]: sym={J_sym_dense[row, col]:.6e}, num={J_num_dense[row, col]:.6e}, diff={diff[row, col]:.6e}")
    
    # Show row/column names if possible
    print("\nVariable indices with large differences:")
    unique_rows = np.unique(large_diff_indices[:, 0])
    unique_cols = np.unique(large_diff_indices[:, 1])
    
    all_vars = problem._state_vars + problem._algebraic_vars
    print(f"Problematic rows (equations): {unique_rows[:10]}")
    print(f"Problematic columns (variables): {unique_cols[:10]}")
    
    print("\nVariable names for problematic columns:")
    for col_idx in unique_cols[:5]:
        if col_idx < len(all_vars):
            print(f"  col {col_idx}: {all_vars[col_idx].name}")

print("\nDone!")
