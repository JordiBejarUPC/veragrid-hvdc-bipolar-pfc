#!/usr/bin/env python
"""
Debug script to find zero rows in Jacobian
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
                     simulation_time=0.015,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.BackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=1000,
                     verbose=0)

problem = RmsProblemDae(grid=grid,
                        options=options,
                        pf_results=res)

# Simulate first 10 steps manually
x0 = problem.get_x0()
dx0 = np.zeros(problem.get_diff_var_number(), dtype=float)
h = options.time_step

t = [0.0]
y = [x0.copy()]
dx = dx0.copy()

for step_idx in range(11):
    current_time = t[-1]
    problem.update_variable_params(t=current_time)
    
    xn = y[-1]
    x_new = xn.copy()
    
    # Converge this step
    converged = False
    for n_iter in range(50):
        if step_idx == 0:
            dx = dx0.copy()
        else:
            dx = (x_new - xn) / h
        
        # Compute RHS
        f_algeb = problem.rhs_algebraic(x_new, dx)
        if problem.get_states_number() > 0:
            f_state = problem.rhs_state(x_new, dx)
            f_state_update = x_new[:problem.get_states_number()] - xn[:problem.get_states_number()] - h * f_state
            rhs = np.r_[f_state_update, f_algeb]
        else:
            rhs = f_algeb
        
        residual = np.linalg.norm(rhs, np.inf)
        
        if residual < 1e-7:
            converged = True
            break
        
        # Compute Jacobian
        if problem.get_states_number() > 0:
            j11_val = problem.get_j11(x_new, dx, h)
            j12_val = problem.get_j12(x_new, dx, h)
            j21_val = problem.get_j21(x_new, dx, h)
            j22_val = problem.get_j22(x_new, dx, h)
            
            I = sp.eye(m=problem.get_states_number(), n=problem.get_states_number())
            j11 = (I - h * j11_val).tocsc()
            j12 = -h * j12_val
            j21 = j21_val
            j22 = j22_val
            
            Jf = pack_4_by_4_scipy(j11, j12, j21, j22)
        else:
            Jf = problem.get_j22(x_new, dx, h)
        
        # Check for zero rows
        if step_idx == 10 and n_iter == 0:
            Jf_dense = Jf.toarray()
            row_norms = np.sum(np.abs(Jf_dense), axis=1)
            zero_rows = np.where(row_norms < 1e-10)[0]
            print(f"\nStep {step_idx}, iter {n_iter}:")
            print(f"  Zero rows found: {zero_rows}")
            print(f"  Total equations: {len(problem._state_eqs) + len(problem._algebraic_eqs)}")
            print(f"  State equations: {len(problem._state_eqs)}")
            print(f"  Algebraic equations: {len(problem._algebraic_eqs)}")
            
            # Print the equations for zero rows
            all_eqs = problem._state_eqs + problem._algebraic_eqs
            for row_idx in zero_rows[:5]:  # Show first 5
                eq = all_eqs[row_idx]
                print(f"\n  Zero row {row_idx}:")
                print(f"    Equation: {eq}")
                print(f"    RHS value: {rhs[row_idx]:.6e}")
                
                # Find which variables this equation depends on
                from VeraGridEngine.Utils.Symbolic.symbolic import get_expression_vars
                vars_in_eq = get_expression_vars(eq)
                print(f"    Variables in eq: {[v.name for v in vars_in_eq][:10]}")
            
            # Also check for zero columns
            col_norms = np.sum(np.abs(Jf_dense), axis=0)
            zero_cols = np.where(col_norms < 1e-10)[0]
            print(f"\n  Zero columns found: {zero_cols}")
            
            break
        
        try:
            delta = sp.linalg.spsolve(Jf, -rhs)
            if not np.all(np.isfinite(delta)):
                break
            x_new += delta
        except Exception as e:
            break
    
    if not converged and step_idx == 10:
        print(f"Step {step_idx}: Did not converge (expected)")
    
    t.append(current_time + h)
    y.append(x_new.copy())

print("\nTest completed!")
