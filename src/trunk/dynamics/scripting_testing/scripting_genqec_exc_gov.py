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


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import GenqecBuild, GovernorBuild, ExciterBuild, StabilizerBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid
###########################################################################################################################

grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=10)
bus2 = gce.Bus(name="Bus2", Vnom=10)
grid.add_bus(bus0)
grid.add_bus(bus1)
grid.add_bus(bus2)

# Lines
line0 = grid.add_line(gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0))
line1 = grid.add_line(gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0))



# load
load_grid = grid.add_load(bus=bus2, api_obj=gce.Load(P= 10, Q= 10))

# Generators
gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom = 900,
                    x1=0.86138701, r1=0.3, freq=50.0,
                    M=10.0,
                    D=1.0,
                    omega_ref=1.0,
                    Kp=1.0,
                    Ki=10.0,
                    )

gen1 = gce.Generator(name="Gen1", P=10, vset=1.0, Snom = 900,
                    x1=0.86138701, r1=0.3, freq=50.0,
                    M=10.0,
                    D=1.0,
                    omega_ref=1.0,
                    Kp=1.0,
                    Ki=10.0)

grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_generator(bus=bus1, api_obj=gen1)

######################################################################################################
# Build Rms models
######################################################################################################
# generator
genqec1_mdl = GenqecBuild().block.copy()
genqec2_mdl = GenqecBuild().block.copy()

exc1_mdl = ExciterBuild().block.copy()
exc2_mdl = ExciterBuild().block.copy()

gov1_mdl = GovernorBuild().block.copy()
gov2_mdl = GovernorBuild().block.copy()

stabil1_mdl = StabilizerBuild().block.copy()
stabil2_mdl = StabilizerBuild().block.copy()



#line
line1_mdl = get_line_rms_template().block.copy()
line2_mdl = get_line_rms_template().block.copy()

#load
load_mdl = get_load_rms_template().block.copy()

## Build big generators

genqec1_mdl.connect(genqec1_mdl.in_vars[3], exc1_mdl.out_vars[0])
exc1_mdl.connect(exc1_mdl.in_vars[0], genqec1_mdl.out_vars[3])

genqec2_mdl.connect(genqec2_mdl.in_vars[3], exc2_mdl.out_vars[0])
exc2_mdl.connect(exc2_mdl.in_vars[0], genqec2_mdl.out_vars[3])

stabil1_mdl.connect(stabil1_mdl.in_vars[0], genqec1_mdl.out_vars[2])
stabil2_mdl.connect(stabil2_mdl.in_vars[0], genqec2_mdl.out_vars[2])

exc1_mdl.connect(exc1_mdl.in_vars[2], stabil1_mdl.out_vars[0])
exc2_mdl.connect(exc2_mdl.in_vars[2], stabil2_mdl.out_vars[0])

genqec1_mdl.connect(genqec1_mdl.in_vars[2], gov1_mdl.out_vars[0])
genqec2_mdl.connect(genqec2_mdl.in_vars[2], gov2_mdl.out_vars[0])

gov1_mdl.connect(gov1_mdl.in_vars[0], genqec1_mdl.out_vars[2])
gov2_mdl.connect(gov2_mdl.in_vars[0], genqec2_mdl.out_vars[2])

# connection with buses

genqec1_mdl.connect(genqec1_mdl.in_vars[0], bus0.rms_model.model.out_vars[0])
genqec1_mdl.connect(genqec1_mdl.in_vars[1], bus0.rms_model.model.out_vars[1])

genqec2_mdl.connect(genqec2_mdl.in_vars[0], bus1.rms_model.model.out_vars[0])
genqec2_mdl.connect(genqec2_mdl.in_vars[1], bus1.rms_model.model.out_vars[1])

exc1_mdl.connect(exc1_mdl.in_vars[1], bus0.rms_model.model.out_vars[1])
exc2_mdl.connect(exc2_mdl.in_vars[1], bus1.rms_model.model.out_vars[1])

big_gen1 = Block(children = [genqec1_mdl, exc1_mdl, gov1_mdl, stabil1_mdl])
big_gen2 = Block(children = [genqec2_mdl, exc2_mdl, gov2_mdl, stabil2_mdl])

# attach rms models to Veragrid objects
gen0.rms_model.model = big_gen1
gen1.rms_model.model = big_gen2

load_grid


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