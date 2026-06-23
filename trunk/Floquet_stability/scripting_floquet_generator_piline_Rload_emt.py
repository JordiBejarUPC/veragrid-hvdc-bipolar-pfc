# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import cProfile
import numpy as np

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import matplotlib.pyplot as plt

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions

from VeraGridEngine.Utils.Symbolic.block import Block

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver


from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model

from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import SmallSignalStabilityEmtOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_results import SmallSignalStabilityEmtResults
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import SmallSignalStabilityEmtDriver

from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes, ShuntConnectionType,SmallSignalEmtBuildTypes
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

profiler = cProfile.Profile()
profiler.enable()


def plot_s_domain_eigenvalues(eigenvalues: np.ndarray) -> None:
    """Plot EMT eigenvalues on the complex plane."""
    if eigenvalues.size == 0:
        return

    re = np.real(eigenvalues)
    im = np.imag(eigenvalues)
    data_span_re = re.max() - re.min()
    data_span_im = im.max() - im.min()
    margin_x = max(data_span_re * 0.1, 1.0)
    margin_y = max(data_span_im * 0.1, 1.0)
    x_min = re.min() - margin_x
    x_max = re.max() + margin_x
    y_min = im.min() - margin_y
    y_max = im.max() + margin_y

    d = np.abs(np.nan_to_num(re))
    max_d = d.max()
    colors = -d / max_d if max_d > 0.0 else np.zeros_like(d)

    slope = 1.0 / 0.05
    x_z = np.linspace(min(-200.0, x_min), 0.0, 400)
    y_z = slope * x_z

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot(x_z, y_z, '--', color='grey', linewidth=0.7, alpha=0.6, label='zeta = 5%')
    ax.plot(x_z, -y_z, '--', color='grey', linewidth=0.7, alpha=0.6)
    ax.scatter(re, im, c=colors, cmap='winter', s=120, alpha=0.8)
    fig.suptitle('EMT S-Domain Stability plot')
    ax.set_xlabel('Real')
    ax.set_ylabel('Imaginary [rad/s]')
    ax.axhline(0.0, color='black', linewidth=1)
    ax.axvline(0.0, color='black', linewidth=1)
    # ax.set_xlim([x_min, x_max])
    # ax.set_ylim([y_min, y_max])
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show(block=True)

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

# Buses
vnom = 10 #kV
bus0 = gce.Bus(name="Bus0", Vnom=vnom, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=vnom)

grid.add_bus(bus0)
grid.add_bus(bus1)

# Lines
line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)


# physical configuration (Overhead line tower)
tower = gce.OverheadLineType(name="Tower", Vnom=vnom)
wire = gce.Wire(name="Panther 30/7 ACSR",
                diameter=21.0,
                diameter_internal=9.0,
                is_tube=True,
                r=0.1363,
                max_current=1)
tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
tower.compute()

# Aplicar física a la línea
line0.apply_template(tower, grid.Sbase, grid.fBase)

# load
# P=1.0
# Q= 0.999999
R_ph =100 #ohm
v_ph = vnom / (3**0.5)
P_ph = (v_ph**2) / R_ph # kv*kv/ohm = MW
print("P_ph=", P_ph)

# load = gce.Load(name="load",P1= P/3, P2= P/3, P3= P/3, Q1= Q/3, Q2= Q/3, Q3= Q/3)
load = gce.Load(name="load",P1= P_ph, P2= P_ph, P3= P_ph, Q1= 0.0, Q2= 0.0, Q3= 0.0)
load.conn = ShuntConnectionType.GroundedStar

# Generator
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq = 50, r1=0.001, x1=1.7)
# r1=Ra, x1=xd'

grid.add_line(line0)
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_load(bus=bus1, api_obj=load)


for bus in grid.buses:
    get_bus_emt_template(grid, bus)

######################################################################################################
# Build EMT models
######################################################################################################

# generator
gen_mdl = get_complete_generator_template_emt(vf = grid.var_factory).block

# line
line_mdl = get_pi_line_emt_template(vf=grid.var_factory, phN = False, phA = True, phB = True, phC = True).block
# line_mdl = get_pi_line_emt_template(grid = grid, line = line0).block

# load
load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

######################################################################################################
# Add models to devices
######################################################################################################

set_emt_model(device=gen0, model=gen_mdl, var_factory= grid.var_factory)

set_emt_model(device=line0, model=line_mdl, var_factory= grid.var_factory)

set_emt_model(device=load, model=load_mdl, var_factory= grid.var_factory)

# connection with buses
# gen_mdl.connect([gen_mdl.in_vars[0]], [bus0.emt_model.out_vars[0]]) # v_A
# gen_mdl.connect([gen_mdl.in_vars[1]], [bus0.emt_model.out_vars[1]]) # v_B
# gen_mdl.connect([gen_mdl.in_vars[2]], [bus0.emt_model.out_vars[2]]) # v_C
#
#
# line_mdl.connect([line_mdl.in_vars[0]], [bus0.emt_model.out_vars[0]]) # line vf_A
# line_mdl.connect([line_mdl.in_vars[1]], [bus0.emt_model.out_vars[1]]) # line vf_B
# line_mdl.connect([line_mdl.in_vars[2]], [bus0.emt_model.out_vars[2]]) # line vf_C
#
# line_mdl.connect([line_mdl.in_vars[3]], [bus1.emt_model.out_vars[0]]) # line vt_A
# line_mdl.connect([line_mdl.in_vars[4]], [bus1.emt_model.out_vars[1]]) # line vt_B
# line_mdl.connect([line_mdl.in_vars[5]], [bus1.emt_model.out_vars[2]]) # line vt_C
#
# load_mdl.connect([load_mdl.in_vars[0]], [bus1.emt_model.out_vars[0]]) # v_A
# load_mdl.connect([load_mdl.in_vars[1]], [bus1.emt_model.out_vars[1]]) # v_B
# load_mdl.connect([load_mdl.in_vars[2]], [bus1.emt_model.out_vars[2]]) # v_C
#
# # external mapping
# big_gen1 = Block(children=[gen_mdl])
#
# big_gen1.external_mapping.update({VarPowerFlowReferenceType.P: gen_mdl.out_vars[0]})
# big_gen1.external_mapping.update({VarPowerFlowReferenceType.Q: gen_mdl.out_vars[1]})
#
# # attach emt models to Veragrid objects
# line0.emt_model= line_mdl
# load.emt_model= load_mdl
# gen0.emt_model= big_gen1

# gce.save_file(grid=grid, filename="grid_save_event.veragrid")

pf_options = PowerFlowOptions(
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

# res = gce.power_flow(grid=grid, options=pf_options)
# power_flow = PowerFlowDriver(grid=grid, options=pf_options)
power_flow = PowerFlowDriver3Ph(grid, pf_options)
power_flow.run()
res = power_flow.results
print("res.m (branch number)= ", res.m)
print("res.n (bus number)= ", res.n)
print("res.n_gen = ", res.n_gen)
print("res.n_load ", res.n_load)
print("res.bus_names = ", res.bus_names)
print("res.branch_names = ", res.branch_names)
print("res.load_names = ", res.load_names)
print("res.bus_types = ", res.bus_types)
print("res.voltage_A = ", res.voltage_A)
print("res.voltage_B = ", res.voltage_B)
print("res.voltage_C = ", res.voltage_C)
print("res.Sbus_A = ", res.Sbus_A)
print("res.Sbus_B = ", res.Sbus_B)
print("res.Sbus_C = ", res.Sbus_C)
print("res.Sf_A = ", res.Sf_A)
print("res.Sf_B = ", res.Sf_B)
print("res.Sf_C = ", res.Sf_C)
print("res.St_A = ", res.St_A)
print("res.St_B = ", res.St_B)
print("res.St_C = ", res.St_C)

print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())


CHOSEN_SOLVER = "AD"
ENABLE_PLOTS = True
ENABLE_NEWTON_TRACE = False
DENSE_THRESHOLD = 0
SOLVER_VERBOSE = True

SOLVER_TYPE_MAP = {
    "SYMBOLIC": EmtSolverTypes.Symbolic,
    "AD": EmtSolverTypes.Automatic,
    "VECTORIZED": EmtSolverTypes.StructuralAD,
    "COMPILED": EmtSolverTypes.StructuralCompiled,
}

ALL_SOLVER_KEYS = ["SYMBOLIC", "AD", "VECTORIZED", "COMPILED"]

if CHOSEN_SOLVER not in SOLVER_TYPE_MAP:
    raise ValueError(f"Solver '{CHOSEN_SOLVER}' no reconocido. Usa SYMBOLIC, AD, VECTORIZED o COMPILED.")

options = EmtOptions(time_step = 5e-6, # 5e-7,
                     simulation_time =  0.04,  #5e-6*10, # s
                     tolerance = 1e-6,
                     solver_type = SOLVER_TYPE_MAP[CHOSEN_SOLVER],
                     integration_method = DynamicIntegrationMethod.DaeTrapezoidal,
                     verbose = 1)


floquet_options = SmallSignalStabilityEmtOptions(k=29,
                                                 ss_assessment_time=0,
                                                 build_type = SmallSignalEmtBuildTypes.Arnoldi)
                                                 # build_type = SmallSignalEmtBuildTypes.HybridArnoldi)

floquet_driver = SmallSignalStabilityEmtDriver(grid=grid,
                                              pf_results=res,
                                              emt_options = options,
                                              sss_options = floquet_options)
floquet_driver.run()

floquet_results = floquet_driver.results
print(f"Floquet multipliers = {floquet_results.multipliers}")
print(f"Floquet right_vecs = {floquet_results.right_vecs}")
print(f"Floquet left_vecs = {floquet_results.left_vecs}")
print(f"Floquet period = {floquet_results.period}")
print(f"Floquet stat_vars = {floquet_results.stat_vars}")
print(f"Floquet eigenvalues = {floquet_results.eigenvalues}")
print(f"Floquet damping_ratios = {floquet_results.damping_ratios}")
print(f"Floquet conjugate_frequencies = {floquet_results.conjugate_frequencies}")
print(f"Floquet participation_factors = {floquet_results.participation_factors}")

if ENABLE_PLOTS:
    plot_s_domain_eigenvalues(np.asarray(floquet_results.eigenvalues, dtype=np.complex128))






