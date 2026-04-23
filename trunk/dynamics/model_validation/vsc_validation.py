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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.load_exponential_template import ExponentialLoadBuild
from VeraGridEngine.Templates.Rms.load_motor_template import MotorLoadBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.vsc_template import VscControlledPV, VSCShuntBuild
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration

from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.enumerations import ConverterControlType
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
bus_dc = gce.Bus(name="BusDC", Vnom=10, is_dc=True)

grid.add_bus(bus0)
grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_bus(bus_dc)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.var_factory)

# Lines
from VeraGridEngine.enumerations import ConverterControlType
line0 = gce.Line(name="line 0-1", bus_from=bus0, bus_to=bus1, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
line1 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
line_vsc = gce.VSC(name="Vsc", bus_from=bus_dc, bus_to=bus2, control1=ConverterControlType.Qac, control1_val=1.0, control2=ConverterControlType.Vm_dc, control2_val=1.0)

grid.add_line(line0)
grid.add_line(line1)
grid.add_vsc(line_vsc)
# load
load1 = gce.Load(P= 9.999999, Q= 0.999999)
load_dc = gce.Load(P=0.5, Q=0.0)
grid.add_load(bus=bus1, api_obj=load1)
grid.add_load(bus=bus_dc, api_obj=load_dc)
#grid.add_load(bus=bus2, api_obj=load2)


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



# line
line0_mdl = block_deep_copy(get_line_rms_template(grid.var_factory).block)
line1_mdl = block_deep_copy(get_line_rms_template(grid.var_factory).block)
vsc_line_mdl = block_deep_copy(VSCShuntBuild(grid.var_factory).block)

# Others
#vsc_solar_mdl = block_deep_copy(VscControlledPV().block)
load_mdl = block_deep_copy(ZIPLoadBuild(grid.var_factory, Pl0 =-0.0999999, Ql0 =-0.00999999).block)
genrow_mdl1 = block_deep_copy(get_genrow1_rms_template(grid.var_factory).block)

genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.rms_model.out_vars[0]])
genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.rms_model.out_vars[1]])

line0_mdl.connect([line0_mdl.in_vars[0]], [bus0.rms_model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[1]], [bus0.rms_model.out_vars[1]])

line0_mdl.connect([line0_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
line0_mdl.connect([line0_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])

line1_mdl.connect([line1_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
line1_mdl.connect([line1_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])

line1_mdl.connect([line1_mdl.in_vars[2]], [bus2.rms_model.out_vars[0]])
line1_mdl.connect([line1_mdl.in_vars[3]], [bus2.rms_model.out_vars[1]])

# vsc_line_mdl.connect([vsc_line_mdl.in_vars[0]], [bus_dc.rms_model.out_vars[0]])
# vsc_line_mdl.connect([vsc_line_mdl.in_vars[1]], [bus_dc.rms_model.out_vars[1]])
# vsc_line_mdl.connect([vsc_line_mdl.in_vars[2]], [bus2.rms_model.out_vars[0]])
# vsc_line_mdl.connect([vsc_line_mdl.in_vars[3]], [bus2.rms_model.out_vars[1]])

#vsc_solar_mdl.connect([vsc_solar_mdl.in_vars[0]], [bus2.rms_model.out_vars[0]])
#vsc_solar_mdl.connect([vsc_solar_mdl.in_vars[1]], [bus2.rms_model.out_vars[1]])
load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
#load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])

# external mapping
big_gen1 = Block(children=[genrow_mdl1])
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl1.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl1.out_vars[1]})

# attach rms models to Veragrid objects
line0.rms_model = line0_mdl
line1.rms_model = line1_mdl
load1.rms_model = load_mdl
gen0.rms_model = big_gen1
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

options = RmsOptions(time_step=0.001,
                     simulation_time=1.0,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=1000,
                     verbose=0)

problem = RmsProblemDae(grid=grid,
                        options=options,
                        pf_results=res)

solver = BackEulerImplicitIntegration(
    problem=problem,
    t0=0,
    t_end=options.simulation_time,
    h=options.time_step,
    max_iter=options.max_iter
)

t, y, well_initialized, converged = solver.simulate()

xlim = options.simulation_time

Pg = genrow_mdl1.out_vars[0]
Qg = genrow_mdl1.out_vars[1]
delta = find_name_in_block("delta", genrow_mdl1)
omega = find_name_in_block("omega", genrow_mdl1)
Vm = find_name_in_block("Vm", genrow_mdl1)

plt.plot(t, y[:, problem.get_var_idx(delta)], label="delta (pu)")
plt.plot(t, y[:, problem.get_var_idx(omega)], label="omega (pu)")
plt.plot(t, y[:, problem.get_var_idx(Vm)], label="Vm (pu)")
plt.plot(t, y[:, problem.get_var_idx(Pg)], label="P (pu)")
plt.plot(t, y[:, problem.get_var_idx(Qg)], label="Q (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()
