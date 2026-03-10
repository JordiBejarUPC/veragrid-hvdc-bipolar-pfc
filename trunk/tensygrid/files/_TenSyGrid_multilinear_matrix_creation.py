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
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy
import VeraGridEngine.Utils.Symbolic.symbolic_ml as sym_ml
from VeraGridEngine.Templates.Rms.generation_tensygrid_ml import GenqecBuild, GovernorBuild, ExciterBuild, \
    StabilizerBuild, get_complete_generator_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.problems.rms_problem_tensygrid import RmsProblemTensygrid
from VeraGridEngine.Simulations.Rms.numerical.back_euler_ts import BackEulerImplicitTensygrid
from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
import VeraGridEngine.api as gce
from trunk.tensygrid.files._PolynomialMatrixBuilder_class import PolynomialMatrixBuilder
from typing import List, Dict, Any, Optional, Tuple, Final
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

######################################################################################################
# Build Rms models
######################################################################################################

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
event = RmsEvent(device=load, parameter=Pl0, time=.01, value=-0.9)
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

params_mapping = dict()

pr.enable()

options = RmsOptions(time_step=0.001,
                     simulation_time=0.1,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=1000,
                     verbose=0)

problem = RmsProblemTensygrid(grid=grid,
                        options=options,
                        pf_results=res)


algebraic_eqs: List[str] = list([str(expression) for expression in problem._algebraic_eqs])
state_eqs: List[str] = list([str(expression) for expression in problem._state_eqs])
algebraic_vars: List[str] = list([str(expression) for expression in problem._algebraic_vars])
state_vars: List[str] = list([str(expression) for expression in problem._state_vars])
print(f"\nState variables ({len(state_vars)}): {state_vars}")
print(f"\nAlgebraic variables ({len(algebraic_vars)}): {algebraic_vars}")

eqs: List[str] = algebraic_eqs + state_eqs
print(f"\nNumber of equations: {len(eqs)}")
print(f"\nEquation 1: {eqs[0]}")
builder = PolynomialMatrixBuilder(
    eqs=eqs,
    ineqs=[],
    state_vars=state_vars,
    algebraic_vars=algebraic_vars,
    verbose=True
)