# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import cProfile
import copy

import time
import sys, os
import numpy as np
import scipy.sparse as sp
import scipy.linalg as la

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))


def inspect_gy(gy: sp.spmatrix, tol: float = 1e-12) -> None:
    """Inspect Jacobian matrix to identify singularities."""
    gy_csc = gy.tocsc()
    gy_csr = gy.tocsr()

    m, n = gy_csc.shape
    print(f"gy shape: {m} x {n}, nnz={gy_csc.nnz}")

    if m != n:
        print("gy is not square")
        return

    zero_rows = np.flatnonzero(np.diff(gy_csr.indptr) == 0)
    zero_cols = np.flatnonzero(np.diff(gy_csc.indptr) == 0)

    print(f"zero rows: {zero_rows.tolist()}")
    print(f"zero cols: {zero_cols.tolist()}")

    dense = gy_csc.toarray()
    s = la.svdvals(dense)
    smin = s[-1]
    smax = s[0]
    cond = np.inf if smin < tol else smax / smin

    print(f"sigma_min = {smin:.3e}")
    print(f"sigma_max = {smax:.3e}")
    print(f"cond      = {cond:.3e}")

    if smin < tol:
        ns = la.null_space(dense)
        print(f"nullity ≈ {ns.shape[1]}")
        if ns.shape[1] > 0:
            print("first right-null vector:")
            print(ns[:, 0])

from matplotlib import pyplot as plt
from VeraGridEngine.Simulations import SmallSignalStabilityRmsDriver, SmallSignalStabilityRmsOptions

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.templates_common_functions import set_rms_model

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
genqec_mdl = get_complete_generator_template(grid.rms_var_factory).block

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

set_rms_model(device=gen0, model=genqec_mdl)

set_rms_model(device=line0, model=line_mdl)

set_rms_model(device=load, model=load_mdl)


######################################################################################################
# Create event
######################################################################################################

Pl0 = find_name_in_block('Pl0', load_mdl)
event = RmsEvent(device=load, parameter=Pl0, time=0.1, value=-0.098)
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
                     simulation_time=20,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=1000,
                     verbose=0)

######################################################################################################
# Prepare and run simulation
######################################################################################################


ss_options = SmallSignalStabilityRmsOptions(ss_assessment_time=0)

# Create driver with dummy grid (it will create RmsProblemDae internally)
driver = SmallSignalStabilityRmsDriver(
    grid=grid,
    rms_options=options,
    sss_options=ss_options,
    pf_results=res
)

print("  ✓ Driver configured with phasor problem")

# ===================================================================
# INSPECT JACOBIAN (J22 = ∂g/∂y)
# ===================================================================
print("\n[4.5] Inspecting J22 (algebraic Jacobian)...")
try:
    # Get the problem and compute J22 at initial state (like BackEulerSolver does)
    problem = driver.problem
    n_states = problem.get_states_number()
    x = problem.get_x0()  # Use proper initial state
    
    print(f"\nDebug: x array size = {len(x)}")
    print(f"Debug: n_states = {n_states}")
    print(f"Debug: n_algebraic = {problem.get_algebraic_var_number()}")
    print(f"Debug: expected total = {n_states + problem.get_algebraic_var_number()}")
    
    # Compute J22 = ∂g/∂y (requires dx and h parameters)
    n_alg = problem.get_algebraic_var_number()
    dx = np.zeros(problem.get_diff_var_number())  # zero derivative (size matches diff vars)
    h = 0.001  # time step
    gy = problem.get_j22(x, dx, h)
    print(f"\nJ22 shape: {gy.shape}")
    print(f"Number of algebraic variables: {n_alg}")
    
    # Inspect the matrix
    inspect_gy(gy)
    
    # Print algebraic variable names to identify the problematic one
    print("\nAlgebraic variable names (index 0-62):")
    alg_vars = problem._algebraic_vars  # It's a list with underscore
    for i in range(min(len(alg_vars), 62)):
        print(f"  [{i}] {alg_vars[i]}")
    
    # Print the equation for V_qag (index 26)
    print(f"\nEquation for V_qag (index 26):")
    print(f"  {problem._algebraic_eqs[26]}")
    
    # Print dependencies (variables in the equation)
    from VeraGridEngine.Utils.Symbolic.symbolic import get_expression_vars
    deps = get_expression_vars(problem._algebraic_eqs[26])
    print(f"\nDependencies:")
    for v in deps:
        print(f"  {v}")
    
    # Also print state variables
    print("\nState variable names:")
    state_vars = problem._state_vars
    for i, sv in enumerate(state_vars):
        print(f"  [{i}] {sv}")
    
except Exception as e:
    print(f"Error inspecting J22: {e}")
    import traceback
    traceback.print_exc()

# ===================================================================
# RUN ANALYSIS
# ===================================================================
print("\n[5] Running small signal analysis...")
print(f"Number of states: {driver.problem.get_states_number()}")
print(f"Number of algebraic vars: {driver.problem.get_algebraic_var_number()}")
print("Starting analysis...")
import traceback
try:
    driver.run()
    print("Analysis completed successfully!")
    
    # Print eigenvalues
    if driver.results is not None:
        print(f"\n{'='*60}")
        print("EIGENVALUE ANALYSIS RESULTS")
        print(f"{'='*60}")
        print(f"Found {len(driver.results.eigenvalues)} eigenvalues:\n")
        
        for i, ev in enumerate(driver.results.eigenvalues[:10]):
            real = ev.real
            imag = ev.imag
            freq = abs(imag) / (2 * 3.14159)
            if abs(real) > 1e-6:
                damping = -real / np.sqrt(real**2 + imag**2)
            else:
                damping = 0.0
            status = "STABLE" if real < -1e-6 else "UNSTABLE" if real > 1e-6 else "MARGINAL"
            print(f"Mode {i+1}: {real:10.4f} + {imag:10.4f}j | Freq: {freq:8.3f} Hz | Damping: {damping:8.4f} | {status}")
    
except Exception as e:
    print(f"Error during analysis: {e}")
    traceback.print_exc()

#