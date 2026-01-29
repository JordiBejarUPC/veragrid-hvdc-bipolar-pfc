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
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import GenqecBuild, GovernorBuild, ExciterBuild, \
    StabilizerBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

pr = profile.Profile()
pr.disable()


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=10)

bus0.initialize_rms()
bus1.initialize_rms()

grid.add_bus(bus0)
grid.add_bus(bus1)

# Lines
line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus1, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)

grid.add_line(line0)

# load
load = gce.Load(P= 9.999999, Q= 0.999999)

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
genqec1_mdl = block_deep_copy(GenqecBuild().block)

exc1_mdl = block_deep_copy(ExciterBuild().block)

gov1_mdl = block_deep_copy(GovernorBuild().block)

stabil1_mdl = block_deep_copy(StabilizerBuild().block)

# line
line0_mdl = block_deep_copy(get_line_rms_template().block)

# load
load_mdl = block_deep_copy(get_load_rms_template().block)

## Build big generators by connecting elements

genqec1_mdl.connect([genqec1_mdl.in_vars[3]], [exc1_mdl.out_vars[0]])
exc1_mdl.connect([exc1_mdl.in_vars[0]], [genqec1_mdl.out_vars[3]])

stabil1_mdl.connect([stabil1_mdl.in_vars[0]], [genqec1_mdl.out_vars[2]])

exc1_mdl.connect([exc1_mdl.in_vars[2]], [stabil1_mdl.out_vars[0]])

genqec1_mdl.connect([genqec1_mdl.in_vars[2]], [gov1_mdl.out_vars[0]])

gov1_mdl.connect([gov1_mdl.in_vars[0]], [genqec1_mdl.out_vars[2]])

# Te connection
gov1_mdl.connect([gov1_mdl.in_vars[1]], [genqec1_mdl.out_vars[4]])

# connection with buses

genqec1_mdl.connect([genqec1_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
genqec1_mdl.connect([genqec1_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

exc1_mdl.connect([exc1_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[0]])


line0_mdl.connect([line0_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

line0_mdl.connect([line0_mdl.in_vars[2]], [bus1.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[3]], [bus1.rms_model.model.out_vars[1]])

u_gov = find_name_in_block("u_gov1", gov1_mdl)

load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

# external mapping

big_gen1 = Block(children=[genqec1_mdl, exc1_mdl, gov1_mdl, stabil1_mdl])

big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genqec1_mdl.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genqec1_mdl.out_vars[1]})

# attach rms models to Veragrid objects
gen0.rms_model.model = big_gen1

line0.rms_model.model = line0_mdl

load.rms_model.model = load_mdl

Pl0 = find_name_in_block('Pl0', load_mdl)
event = RmsEvent(device=load, parameter=Pl0, time=.5, value=-0.12)
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
print(res.get_bus_df())
print(res.get_branch_df())

params_mapping = dict()

pr.enable()

sim_time, ss, init_guess = initialize_rms(grid, res, use_init_values=False)

slv = BlockSolver(ss, sim_time)

params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector_from_uid(init_guess)

dx0 = np.zeros(len(slv.diff_vars))
Vm = find_name_in_block("Vm", slv.block_system)

xlim = 15.0
t, y, _ = slv.simulate(
    t0=0,
    t_end=xlim,
    h=0.001,
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

pr.disable()

omega = genqec1_mdl.out_vars[2]
Pg = genqec1_mdl.out_vars[0]
Qg = genqec1_mdl.out_vars[1]
Ir = genqec1_mdl.out_vars[3]
Efd = genqec1_mdl.in_vars[3]
Te = genqec1_mdl.out_vars[4]

u_gov1 = find_name_in_block("u_gov1", gov1_mdl)
y_subexciter = find_name_in_block("y_subexciter1", exc1_mdl)
y_exciter1 = find_name_in_block("y_exciter1", exc1_mdl)
y_exciter4 = find_name_in_block("y_exciter4", exc1_mdl)
Efe = find_name_in_block("Efe", exc1_mdl)
delta = find_name_in_block("delta", genqec1_mdl)


# Generator state variables
plt.plot(t, y[:, slv.get_var_idx(omega)], label="omega (pu)")
plt.plot(t, y[:, slv.get_var_idx(delta)], label="delta (pu)")
plt.plot(t, y[:, slv.get_var_idx(Vm)], label="Vm (pu)")
plt.plot(t, y[:, slv.get_var_idx(Pg)], label="P (pu)")
plt.plot(t, y[:, slv.get_var_idx(Qg)], label="Q (pu)")
plt.plot(t, y[:, slv.get_var_idx(Ir)], label="Ir (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()

pr.dump_stats('profile.pstat')



Eq_prime = find_name_in_block("Eq_prime", genqec1_mdl)
Ed_prime = find_name_in_block("Ed_prime", genqec1_mdl)
Psiq_prime = find_name_in_block("Psiq_prime", genqec1_mdl)
Psid_prime = find_name_in_block("Psid_prime", genqec1_mdl)

Ed1 = find_name_in_block("Ed1", genqec1_mdl)
Eq1 = find_name_in_block("Eq1", genqec1_mdl)

# Generator state variables
plt.plot(t, y[:, slv.get_var_idx(Eq_prime)], label="Eq_prime (pu)")
plt.plot(t, y[:, slv.get_var_idx(Ed_prime)], label="Ed_prime (pu)")
plt.plot(t, y[:, slv.get_var_idx(Psiq_prime)], label="Eq_2prime (pu)")
plt.plot(t, y[:, slv.get_var_idx(Psid_prime)], label="Ed_2prime (pu)")

plt.plot(t, y[:, slv.get_var_idx(Ed1)], label="Ed1 (pu)")
plt.plot(t, y[:, slv.get_var_idx(Eq1)], label="Eq1 (pu)")
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()

Tm = gov1_mdl.out_vars[0]
# Generator state variables
plt.plot(t, y[:, slv.get_var_idx(u_gov1)], label="u_gov1 (pu)")
plt.plot(t, y[:, slv.get_var_idx(y_subexciter)], label="y_subexciter (pu)")
plt.plot(t, y[:, slv.get_var_idx(Efe)], label="Efe (pu)")
plt.plot(t, y[:, slv.get_var_idx(y_exciter1)], label="y_exciter1 (pu)")
plt.plot(t, y[:, slv.get_var_idx(y_exciter4)], label="y_exciter4 (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()
