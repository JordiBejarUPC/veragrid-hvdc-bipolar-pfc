# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from typing import Any, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    SolverType,
    WindingType,
)
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import (
    get_generator_thevenin_rl_emt_template,
)
from VeraGridEngine.Templates.Emt.xfmr_emt_template import get_xfmr_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block


def find_name_in_block(name: str, block: Block):
    """Depth-first search for one variable by exact name."""
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if var.name == name:
            return var

    for child in block.children:
        res = find_name_in_block(name, child)
        if res is not None:
            return res

    return None


def get_series(problem: EmtProblemDae, y: np.ndarray, var) -> np.ndarray | None:
    """Return the trajectory of one symbolic variable if it exists."""
    if var is None:
        return None
    return y[:, problem.get_var_idx(var)]


# =====================================================================
# BUILD A SIMPLE, CONSISTENT NETWORK
# =====================================================================
# Network under test:
#   slack generator (230 kV) -> 2W transformer (230/66 kV) -> load (66 kV)
#
# The goal is to test the XFMR EMT template in a clean balanced operating point.
# No VSC and no DC side are used here.
# =====================================================================

circuit = gce.MultiCircuit(name='Grid - Generator + XFMR + Load EMT Test', Sbase=100.0, fbase=50.0)

bus_hv = gce.Bus(name='Bus_HV', Vnom=230.0, is_slack=True)
bus_lv = gce.Bus(name='Bus_LV', Vnom=66.0)
circuit.add_bus(bus_hv)
circuit.add_bus(bus_lv)

# Slack machine providing the AC source.
gen = gce.Generator(
    name='Generator',
    vset=1.0,
    Snom=200.0,
    freq=50.0,
    r1=0.002,
    x1=0.25,
)
circuit.add_generator(bus_hv, gen)

# Transformer static data.
# The electrical R/X/G/B used in PF are derived from the nameplate test values.
xfmr = gce.Transformer2W(
    name='Transformer',
    bus_from=bus_hv,
    bus_to=bus_lv,
    HV=230.0,
    LV=66.0,
    nominal_power=100.0,
    copper_losses=120.0,       # kW
    iron_losses=35.0,          # kW
    no_load_current=0.20,      # %
    short_circuit_voltage=10.0,# %
    rate=100.0,
    tap_module=1.0,
    tap_phase=0.0,
)
xfmr.conn_f = WindingType.GroundedStar
xfmr.conn_t = WindingType.GroundedStar
xfmr.vector_group_number = 0
xfmr.fill_design_properties(
    Pcu=120.0,
    Pfe=35.0,
    I0=0.20,
    Vsc=10.0,
    Sbase=circuit.Sbase,
)
circuit.add_transformer2w(xfmr)

# Load chosen so the operating point is moderate and PF converges easily.
# The EMT model used below is a pure shunt resistor, so the static load is kept
# purely active and its per-phase powers are populated explicitly. The resistor
# EMT template maps ``Pa/Pb/Pc`` rather than the positive-sequence ``P`` field.
load = gce.Load(
    name='Load',
    P=40.0,
    Q=0.0,
    P1=40.0 / 3.0,
    P2=40.0 / 3.0,
    P3=40.0 / 3.0,
    Q1=0.0,
    Q2=0.0,
    Q3=0.0,
)
circuit.add_load(bus_lv, load)


# =====================================================================
# EMT MODELS
# =====================================================================
for bus in circuit.buses:
    get_bus_emt_template(grid=circuit, bus=bus)

gen_mdl = get_generator_thevenin_rl_emt_template(vf=circuit.var_factory, name='gen_test').block
xfmr_mdl = get_xfmr_emt_template(vf=circuit.var_factory, name='xfmr_test').block
load_mdl = get_shunt_r_emt_template(vf=circuit.var_factory, phA=True, phB=True, phC=True).block

set_emt_model(device=gen, model=gen_mdl, var_factory=circuit.var_factory)
set_emt_model(device=xfmr, model=xfmr_mdl, var_factory=circuit.var_factory)
set_emt_model(device=load, model=load_mdl, var_factory=circuit.var_factory)

# ---------------------------------------------------------------------
# Template-owned XFMR parameters: set them explicitly through event_dict.
# These names follow the XFMR template naming convention.
# ---------------------------------------------------------------------
xfmr_mdl.set_parameter_in_model(var_name='xfmr_use_linear_core_xfmr_test', new_value=1.0)
xfmr_mdl.set_parameter_in_model(var_name='xfmr_c_term_xfmr_test', new_value=0.0)
xfmr_mdl.set_parameter_in_model(var_name='xfmr_core_topology_code_xfmr_test', new_value=3.0)
xfmr_mdl.set_parameter_in_model(var_name='xfmr_yoke_area_rel_xfmr_test', new_value=1.0)
xfmr_mdl.set_parameter_in_model(var_name='xfmr_yoke_length_rel_xfmr_test', new_value=1.0)
xfmr_mdl.set_parameter_in_model(var_name='xfmr_outer_leg_area_rel_xfmr_test', new_value=1.0)
xfmr_mdl.set_parameter_in_model(var_name='xfmr_outer_leg_length_rel_xfmr_test', new_value=1.0)

# Optional nonlinear-core tuning defaults. These do not affect the run while
# xfmr_use_linear_core_xfmr_test = 1, but setting them keeps the example explicit.
xfmr_mdl.set_parameter_in_model(var_name='xfmr_core_knee_flux_mult_xfmr_test', new_value=1.05)
xfmr_mdl.set_parameter_in_model(var_name='xfmr_core_knee_current_mult_xfmr_test', new_value=8.0)


# =====================================================================
# BALANCED POWER FLOW FOR EMT INITIALIZATION
# =====================================================================
pf_options = PowerFlowOptions(
    solver_type=SolverType.NR,
    verbose=False,
    retry_with_other_methods=True,
    max_iter=50,
    tolerance=1e-8,
    control_q=False,
    control_taps_modules=False,
    control_taps_phase=False,
    distributed_slack=False,
)

pf_results = gce.power_flow(grid=circuit, options=pf_options)

print('\n' + '=' * 70)
print('BALANCED POWER FLOW RESULTS')
print('=' * 70)
print(f'Converged: {pf_results.converged}')
if not pf_results.converged:
    raise RuntimeError('Power flow did not converge. The EMT initialization would not be reliable.')

print(pf_results.get_bus_df())
print(pf_results.get_branch_df())


# =====================================================================
# EMT PROBLEM + SOLVER
# =====================================================================
options = EmtOptions(
    time_step=10e-6,
    simulation_time=0.06,
    tolerance=1e-6,
    solver_type=EmtSolverTypes.Symbolic,
    integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
    initialization_method=EmtInitializationMethod.Explicit,
    verbose=1,
)

problem = EmtProblemDae(
    grid=circuit,
    options=options,
    pf_results_3Ph=None,
    pf_results=pf_results,
)

print('\n' + '=' * 70)
print('INITIAL GUESS TABLE')
print('=' * 70)
print(problem.get_init_guess_table())

solver = JitSymbolicSolver(
    problem=problem,
    t0=0.0,
    t_end=options.simulation_time,
    h=options.time_step,
    method=options.integration_method,
    pred_method=DynamicIntegrationMethod.OdeEuler,
    dense_threshold=0,
    verbose=True,
)

solver.build_jit_kernel(options.integration_method)
solver._build_jit_symbolic_hybrid(options.integration_method, use_sparse=True)

if options.integration_method == DynamicIntegrationMethod.DaeTrapezoidal:
    solver.build_jit_kernel(DynamicIntegrationMethod.DaeBackEuler)
    solver._build_jit_symbolic_hybrid(DynamicIntegrationMethod.DaeBackEuler, use_sparse=True)

boundary_updater = cast(Any, problem)
t, y, dy, _, _ = solver.simulate(boundary_updater=boundary_updater)

print('\nSimulation completed successfully!')


# =====================================================================
# PLOTS
# =====================================================================
# Use solver-returned time vector directly.
t_sim = np.asarray(t).reshape(-1)

# Bus voltages
vA_hv = get_series(problem, y, find_name_in_block('v_A_Bus_HV_emt_template', bus_hv.emt_model))
vB_hv = get_series(problem, y, find_name_in_block('v_B_Bus_HV_emt_template', bus_hv.emt_model))
vC_hv = get_series(problem, y, find_name_in_block('v_C_Bus_HV_emt_template', bus_hv.emt_model))

vA_lv = get_series(problem, y, find_name_in_block('v_A_Bus_LV_emt_template', bus_lv.emt_model))
vB_lv = get_series(problem, y, find_name_in_block('v_B_Bus_LV_emt_template', bus_lv.emt_model))
vC_lv = get_series(problem, y, find_name_in_block('v_C_Bus_LV_emt_template', bus_lv.emt_model))

# Transformer terminal currents
ifA = get_series(problem, y, find_name_in_block('if_A_xfmr_test', xfmr_mdl))
ifB = get_series(problem, y, find_name_in_block('if_B_xfmr_test', xfmr_mdl))
ifC = get_series(problem, y, find_name_in_block('if_C_xfmr_test', xfmr_mdl))

itA = get_series(problem, y, find_name_in_block('it_A_xfmr_test', xfmr_mdl))
itB = get_series(problem, y, find_name_in_block('it_B_xfmr_test', xfmr_mdl))
itC = get_series(problem, y, find_name_in_block('it_C_xfmr_test', xfmr_mdl))

# Transformer internal variables useful to check the model behavior.
i_leak_A = get_series(problem, y, find_name_in_block('i_leak_A_xfmr_test', xfmr_mdl))
i_mag_A = get_series(problem, y, find_name_in_block('i_mag_A_xfmr_test', xfmr_mdl))
lam_A = get_series(problem, y, find_name_in_block('lam_leg_A_xfmr_test', xfmr_mdl))

plt.figure(figsize=(13, 9))
plt.subplot(2, 1, 1)
if vA_hv is not None:
    plt.plot(t_sim, vA_hv, label='HV bus - phase A', color='tab:blue')
if vB_hv is not None:
    plt.plot(t_sim, vB_hv, label='HV bus - phase B', color='tab:red')
if vC_hv is not None:
    plt.plot(t_sim, vC_hv, label='HV bus - phase C', color='tab:green')
plt.title('Primary-side bus voltages')
plt.xlabel('Time [s]')
plt.ylabel('Voltage [p.u.]')
plt.grid(True)
plt.legend(loc='upper right')

plt.subplot(2, 1, 2)
if vA_lv is not None:
    plt.plot(t_sim, vA_lv, label='LV bus - phase A', color='tab:blue')
if vB_lv is not None:
    plt.plot(t_sim, vB_lv, label='LV bus - phase B', color='tab:red')
if vC_lv is not None:
    plt.plot(t_sim, vC_lv, label='LV bus - phase C', color='tab:green')
plt.title('Secondary-side bus voltages')
plt.xlabel('Time [s]')
plt.ylabel('Voltage [p.u.]')
plt.grid(True)
plt.legend(loc='upper right')
plt.tight_layout()
plt.show()

plt.figure(figsize=(13, 10))
plt.subplot(2, 1, 1)
if ifA is not None:
    plt.plot(t_sim, ifA, label='if_A', color='tab:blue')
if ifB is not None:
    plt.plot(t_sim, ifB, label='if_B', color='tab:red')
if ifC is not None:
    plt.plot(t_sim, ifC, label='if_C', color='tab:green')
plt.title('Transformer from-side terminal currents')
plt.xlabel('Time [s]')
plt.ylabel('Current [p.u.]')
plt.grid(True)
plt.legend(loc='upper right')

plt.subplot(2, 1, 2)
if itA is not None:
    plt.plot(t_sim, itA, label='it_A', color='tab:blue')
if itB is not None:
    plt.plot(t_sim, itB, label='it_B', color='tab:red')
if itC is not None:
    plt.plot(t_sim, itC, label='it_C', color='tab:green')
plt.title('Transformer to-side terminal currents')
plt.xlabel('Time [s]')
plt.ylabel('Current [p.u.]')
plt.grid(True)
plt.legend(loc='upper right')
plt.tight_layout()
plt.show()

plt.figure(figsize=(13, 9))
if i_leak_A is not None:
    plt.plot(t_sim, i_leak_A, label='Leakage current A', color='tab:blue')
if i_mag_A is not None:
    plt.plot(t_sim, i_mag_A, label='Magnetizing current A', color='tab:orange')
if lam_A is not None:
    plt.plot(t_sim, lam_A, label='Leg flux linkage A', color='tab:purple')
plt.title('Transformer internal phase-A variables')
plt.xlabel('Time [s]')
plt.ylabel('Per-unit / state value')
plt.grid(True)
plt.legend(loc='upper right')
plt.tight_layout()
plt.show()

vcm_hv = (vA_hv + vB_hv + vC_hv) / 3.0
vab_hv = vA_hv - vB_hv
vbc_hv = vB_hv - vC_hv
vca_hv = vC_hv - vA_hv

plt.figure(figsize=(12, 8))

plt.subplot(2, 1, 1)
plt.plot(t_sim, vcm_hv, label='HV common-mode voltage')
plt.title('HV bus common-mode voltage')
plt.xlabel('Time [s]')
plt.ylabel('Voltage [p.u.]')
plt.grid(True)
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(t_sim, vab_hv, label='Vab')
plt.plot(t_sim, vbc_hv, label='Vbc')
plt.plot(t_sim, vca_hv, label='Vca')
plt.title('HV bus line-to-line voltages')
plt.xlabel('Time [s]')
plt.ylabel('Voltage [p.u.]')
plt.grid(True)
plt.legend()

plt.tight_layout()
plt.show()
