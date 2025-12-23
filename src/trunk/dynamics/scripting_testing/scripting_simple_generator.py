# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math

import numpy as np
from matplotlib import pyplot as plt

import sys
import os

from VeraGridEngine import VarPowerFlowRefferenceType, power_flow
from VeraGridEngine.Utils.Symbolic.block_solver_comb import DiffBlockSolver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import GenqecBuild, GovernorBuild, ExciterBuild, StabilizerBuild
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

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
load = gce.Load(P= 10, Q= 10)
grid.add_load(bus=bus1, api_obj=load)

# Generators
gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom = 900,
                    x1=0.86138701, r1=0.3, freq=50.0,
                    M=4.0,
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
genrow_mdl = get_genrow_rms_template().block.copy()

#line
line0_mdl = get_line_rms_template().block.copy()


#load
load_mdl = get_load_rms_template().block.copy()


# connection with buses

genrow_mdl.connect([genrow_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
genrow_mdl.connect([genrow_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])



line0_mdl.connect([line0_mdl.in_vars[0]], [bus0.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[1]], [bus0.rms_model.model.out_vars[1]])

line0_mdl.connect([line0_mdl.in_vars[2]], [bus1.rms_model.model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[3]], [bus1.rms_model.model.out_vars[1]])




load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

# external mapping


big_gen1 = Block(children = [genrow_mdl])


big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl.out_vars[1]})




# attach rms models to Veragrid objects
gen0.rms_model.model = big_gen1


line0.rms_model.model = line0_mdl


load.rms_model.model = load_mdl

import os
print(os.environ.get("PYDEVD_DISABLE_SYS_MONITORING"))
print(os.environ.get("PYDEVD_DISABLE_GUI_EVENT_LOOP"))


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

sim_time, ss, init_guess = initialize_rms(grid, res, use_init_values=False)

slv = BlockSolver(ss, sim_time)

params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector_from_uid(init_guess)

t, y = slv.simulate(
    t0=0,
    t_end=20,
    h=0.001,
    x0=x0,
    params0=params0,
    method="implicit_euler",
)