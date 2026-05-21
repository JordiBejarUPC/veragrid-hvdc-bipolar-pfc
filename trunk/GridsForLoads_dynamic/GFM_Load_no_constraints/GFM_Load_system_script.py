# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import cProfile
import pstats
import numpy as np
from time import perf_counter
from typing import Any, cast

import sys
import os

from VeraGridEngine import get_generator_thevenin_rl_emt_template_with_ref

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
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph


from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template

from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes, ShuntConnectionType
import VeraGridEngine.api as gce

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


######################################################################################################
# Build grid
######################################################################################################


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
# TODO: change to almost ideal line (no losses)
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

# Apply line physics
line0.apply_template(tower, grid.Sbase, grid.fBase)

# load
# P=1.0
# Q= 0.999999
R_ph = 100 #ohm
v_ph = vnom / (3**0.5)
P_ph = (v_ph**2) / R_ph # kv*kv/ohm = MW

# load = gce.Load(name="load",P1= P/3, P2= P/3, P3= P/3, Q1= Q/3, Q2= Q/3, Q3= Q/3)
load = gce.Load(name="load",P1= P_ph, P2= P_ph, P3= P_ph, Q1= 0.0, Q2= 0.0, Q3= 0.0)
load.conn = ShuntConnectionType.GroundedStar

# Generator
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq = 50, r1=0.001, x1=1.7, x0 = 0.14)
# r1=Ra, x1=xd'

grid.add_line(line0)
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_load(bus=bus1, api_obj=load)


for bus in grid.buses:
    get_bus_emt_template(grid, bus)

######################################################################################################
# Build EMT models
######################################################################################################
gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf= grid.var_factory).block



# line
# line_mdl = get_pi_line_emt_template(vf=grid.var_factory, line = line0).block
line_mdl = get_pi_line_emt_template(vf = grid.var_factory, phN = False, phA = True, phB = True, phC = True).block

# load
# load_mdl = get_load_ZIP_3ph_emt_template(grid = grid, load = load).block
load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block
# load_mdl.set_parameter_in_model(var_name="Vnom_Shunt_R_3ph", new_value=1.0)
