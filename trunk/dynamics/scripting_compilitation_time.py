# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math

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

from VeraGridEngine import VarPowerFlowRefferenceType, power_flow
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver_no_diff import BlockSolverNoDiff
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import GenqecBuild, GovernorBuild, ExciterBuild, StabilizerBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
from VeraGridEngine.enumerations import DynamicIntegrationMethod
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars:
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
line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus1, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)

grid.add_line(line0)



# load
load = gce.Load(P= 9.999999, Q= 0.999999)
grid.add_load(bus=bus1, api_obj=load)

# Generators
gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom = 900,
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
sim_time = Var("global_time")
genqec1_mdl = GenqecBuild().block.copy()
exc1_mdl = ExciterBuild().block.copy()
gov1_mdl = GovernorBuild().block.copy()
stabil1_mdl = StabilizerBuild().block.copy()
line0_mdl = get_line_rms_template().block.copy()
load_mdl = get_load_rms_template().block.copy()

import time

start_time = time.time()
genqec1_mdl.algebraic_vars.extend(genqec1_mdl.in_vars)
slv = BlockSolver(genqec1_mdl, sim_time)
end_time = time.time()
gen_time = end_time - start_time

start_time = time.time()
exc1_mdl.algebraic_vars.extend(exc1_mdl.in_vars)
for key, val in exc1_mdl.event_dict.items():
    exc1_mdl.event_dict[key] = Const(0)
slv = BlockSolver(exc1_mdl, sim_time)
end_time = time.time()
exc_time = end_time - start_time


start_time = time.time()
gov1_mdl.algebraic_vars.extend(gov1_mdl.in_vars)
for key, val in gov1_mdl.event_dict.items():
    gov1_mdl.event_dict[key] = Const(0)
slv = BlockSolver(gov1_mdl, sim_time)
end_time = time.time()
gov_time = end_time - start_time


#line
start_time = time.time()
stabil1_mdl.algebraic_vars.extend(stabil1_mdl.in_vars)
slv = BlockSolver(stabil1_mdl, sim_time)
end_time = time.time()
stabil1_mdl_time = end_time - start_time

times = [("Generator", gen_time), ("Exciter", exc_time), ("Governor", gov_time), ("Stabilizer", stabil1_mdl_time)]
for name, t in times:
    print(f"{name} RMS model compilation time: {t} seconds")

