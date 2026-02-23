# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import cProfile as profile
import numpy as np
from matplotlib import pyplot as plt

import sys
import os

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults, PowerFlowOptions

from VeraGridEngine import VarPowerFlowRefferenceType, power_flow, DynamicIntegrationMethod
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy
from VeraGridEngine.Utils.Symbolic.block_solver_no_diff import BlockSolverNoDiff
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.load_exponential_template import ExponentialLoadBuild
from VeraGridEngine.Templates.Rms.load_motor_template import MotorLoadBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
import VeraGridEngine.api as gce

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

pr = profile.Profile()
pr.disable()

grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=10)
bus2 = gce.Bus(name="Bus2", Vnom=10)

bus0.initialize_rms()
bus1.initialize_rms()
bus2.initialize_rms()

grid.add_bus(bus0)
grid.add_bus(bus1)
grid.add_bus(bus2)

# Lines
line0 = gce.Line(name="line 0-1", bus_from=bus0, bus_to=bus1, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
line1 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
grid.add_line(line0)
grid.add_line(line1)

# load
load1 = gce.Load(P= 9.999999, Q= 0.999999)
load2 = gce.Load(P= 10.0, Q= 0.0)
grid.add_load(bus=bus1, api_obj=load1)
grid.add_load(bus=bus2, api_obj=load2)

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


# line
line0_mdl = block_deep_copy(get_line_rms_template().block)
line1_mdl = block_deep_copy(get_line_rms_template().block)

# load
load_type = 'zip'
if load_type == 'zip':
    load_mdl = block_deep_copy(ZIPLoadBuild(Pl0 =-0.0999999, Ql0 =-0.00999999).block)
elif load_type == 'exponential':
    load_mdl = block_deep_copy(ExponentialLoadBuild(Pl0 =-0.0999999, Ql0 =-0.00999999).block)
elif load_type == 'motor':
    load_mdl = block_deep_copy(MotorLoadBuild().block)

motor_mdl = block_deep_copy(MotorLoadBuild().block)

genrow_mdl1 = block_deep_copy(get_genrow1_rms_template().block)

genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

line0_mdl.connect([line0_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

line0_mdl.connect([line0_mdl.in_vars[2]], [bus1.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[3]], [bus1.rms_model.model.out_vars[1]])

line1_mdl.connect([line1_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
line1_mdl.connect([line1_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

line1_mdl.connect([line1_mdl.in_vars[2]], [bus2.rms_model.model.out_vars[0]])
line1_mdl.connect([line1_mdl.in_vars[3]], [bus2.rms_model.model.out_vars[1]])

if load_type != 'motor':
    load_mdl.connect([load_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
else:
    motor_mdl.connect([motor_mdl.in_vars[0]], [bus2.rms_model.model.out_vars[0]])
    motor_mdl.connect([motor_mdl.in_vars[1]], [bus2.rms_model.model.out_vars[1]])

motor_mdl.connect([motor_mdl.in_vars[0]], [bus2.rms_model.model.out_vars[0]])
motor_mdl.connect([motor_mdl.in_vars[1]], [bus2.rms_model.model.out_vars[1]])
#load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
#load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])


# attach rms models to Veragrid objects
gen0.rms_model.model = genrow_mdl1
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

line0.rms_model.model = line0_mdl
line1.rms_model.model = line1_mdl

load1.rms_model.model = load_mdl
load2.rms_model.model = motor_mdl
Pl0 = find_name_in_block('Pl0', load_mdl)
u = find_name_in_block('u', motor_mdl)
#Tp0 = find_name_in_block('Tp0', load_mdl)
event = RmsEvent(device=load1, parameter=Pl0, time=.5, value=-0.12)
event = RmsEvent(device=load2, parameter=u, time=-0.01, value=1.0)
grid.add_rms_event(event)
print(Pl0)
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

sim_time, ss, init_guess = initialize_rms(grid, res, use_init_values=False)

slv = BlockSolver(ss, sim_time)
params_mapping = {}
params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector_from_uid(init_guess)
dx0 = np.zeros(len(slv._diff_vars))
Vm = find_name_in_block("Vm", slv.block_system)

xlim = 5.0
t, y, _ = slv.simulate(
    t0=0,
    t_end=xlim,
    h=1e-3,
    x0=x0,
    dx0=dx0,
    params0=params0,
    method=DynamicIntegrationMethod.BackEuler,
    newton_tol=1e-8,
    newton_max_iter=1000,
    followed_vars=None,
    initialized=False,
    verbose=False,
)

Pg = genrow_mdl1.out_vars[0]
Qg = genrow_mdl1.out_vars[1]
delta = find_name_in_block("delta", genrow_mdl1)

plt.plot(t, y[:, slv.get_var_idx(delta)], label="delta (pu)")
plt.plot(t, y[:, slv.get_var_idx(Vm)], label="Vm (pu)")
plt.plot(t, y[:, slv.get_var_idx(Pg)], label="P (pu)")
plt.plot(t, y[:, slv.get_var_idx(Qg)], label="Q (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()

omega = find_name_in_block('omega', motor_mdl)
Vm = bus2.rms_model.model.out_vars[0]
Va = bus2.rms_model.model.out_vars[1]
P = find_name_in_block('Pl', motor_mdl)
Q = find_name_in_block('Ql', motor_mdl)
Te = find_name_in_block('Te', motor_mdl)

plt.plot(t, y[:, slv.get_var_idx(omega)], label="omega (pu)")
#plt.plot(t, y[:, slv.get_var_idx(Vm)], label="Vm (pu)")
plt.plot(t, y[:, slv.get_var_idx(Va)], label="Va (pu)")
plt.plot(t, y[:, slv.get_var_idx(P)], label="P (pu)")
plt.plot(t, y[:, slv.get_var_idx(Q)], label="Q (pu)")
plt.plot(t, y[:, slv.get_var_idx(Te)], label="Te (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()