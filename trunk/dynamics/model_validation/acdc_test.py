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
from VeraGridEngine.Templates.Rms.vsc_template import VscControlledPV, VSCShuntBuild, VSCShuntBuild2, PVCellBuild, PVControlBuild2
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
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


# Grid instantiation
grid = gce.MultiCircuit()

# Define buses
bus1 = gce.Bus(name='B1', Vnom=135, is_slack=True)
bus2 = gce.Bus(name='B2', Vnom=135)
bus3 = gce.Bus(name='B3', Vnom=100, is_dc=True)
#bus4 = gce.Bus(name='B4', Vnom=100, is_dc=True)
#bus5 = gce.Bus(name='B5', Vnom=135)
#bus6 = gce.Bus(name='B6', Vnom=135)

# Define AC lines
line12 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
#line25 = gce.Line(name='L25', bus_from=bus2, bus_to=bus5, r=1.05, x=0.5)
#line56 = gce.Line(name='L56', bus_from=bus5, bus_to=bus6, r=0.001, x=0.1)

# Define DC lines
#line34 = gce.DcLine(name='L34', bus_from=bus3, bus_to=bus4, r=2.05)

# Define VSCs
vsc1 = gce.VSC(name='VSC1', bus_from=bus3, bus_to=bus2, rate=100, alpha1=0.0, alpha2=0.0, alpha3=0.00,
               control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Vm_ac,
               control1_val=1.00, control2_val=1.02)

# vsc2 = gce.VSC(name='VSC2', bus_from=bus4, bus_to=bus5, rate=100, alpha1=0.001, alpha2=0.015, alpha3=0.01,
#                control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Qac,
#                control1_val=1.05, control2_val=-0.21)

# Define generators
gen1 = gce.Generator(name='Gen1', P=1.0, vset=1.00)
#gen2 = gce.Generator(name='Gen2', P=1.0, vset=1.02)

# Define loads
load1 = gce.Load(name='Load1', P=3.0, Q=0.3)
#load2 = gce.Load(name='Load2', P=2.0, Q=0.5)
#load3 = gce.Load(name='Load3', G=0.5, B=0.3)  # DC load



#Grid modifications
#grid.add_load(bus = bus3, api_obj=load3)
gen3 = gce.CurrentInjection(name='Gen3', Ir =0.2)
grid.add_current_injection(bus=bus3, api_obj=gen3)


###############
# Add to the grid
grid.add_bus(bus1)
grid.add_bus(bus2) 
grid.add_bus(bus3)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.rms_var_factory)

grid.add_line(line12)
grid.add_vsc(vsc1)
grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_load(bus=bus2, api_obj=load1)


#########
pf_driver = gce.PowerFlowDriver(grid=grid)
pf_driver.run()
res = pf_driver.results
print('Voltage magnitudes (p.u.): ', abs(pf_driver.results.voltage))
print('Voltage angles (deg): ', np.angle(pf_driver.results.voltage, deg=True))

#Initialise the RMS
line12_mdl = block_deep_copy(get_line_rms_template(grid.rms_var_factory).block, grid.rms_var_factory)
load_type = 'zip'
if load_type == 'zip':
    load_mdl = block_deep_copy(ZIPLoadBuild(Pl0 =-0.0999999, Ql0 =-0.00999999).block, grid.rms_var_factory)

genrow_mdl1 = block_deep_copy(get_genrow1_rms_template(grid.rms_var_factory).block, grid.rms_var_factory)
#vsc_mdl   = block_deep_copy(VSCShuntBuild2().block)
#injection_mdl = block_deep_copy(get_load_rms_template().block)
vsc_mdl        =  block_deep_copy(VSCShuntBuild2().block, grid.rms_var_factory)
pv_control_block       =  block_deep_copy(PVControlBuild2().block, grid.rms_var_factory)
pv_cell_block  =  block_deep_copy(PVCellBuild().block, grid.rms_var_factory)

genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.rms_model.out_vars[0]])
genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.rms_model.out_vars[1]])

load_mdl.connect([load_mdl.in_vars[0]], [bus2.rms_model.out_vars[0]])

line12_mdl.connect([line12_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])

line12_mdl.connect([line12_mdl.in_vars[2]], [bus2.rms_model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[3]], [bus2.rms_model.out_vars[1]]) 

vsc_mdl.connect([vsc_mdl.in_vars[0]], [bus2.rms_model.out_vars[0]])
vsc_mdl.connect([vsc_mdl.in_vars[1]], [bus2.rms_model.out_vars[1]])

vsc_mdl.connect([vsc_mdl.in_vars[2]], [bus3.rms_model.out_vars[0]])

#vsc_mdl.connect([vsc_mdl.in_vars[3]], [bus3.rms_model.out_vars[1]]) 

pv_cell_block.connect([pv_cell_block.in_vars[0]], [bus3.rms_model.out_vars[0]])

pv_control_block.connect([pv_control_block.in_vars[0]], [bus2.rms_model.out_vars[0]])
pv_control_block.connect([pv_control_block.in_vars[1]], [bus3.rms_model.out_vars[0]])
pv_control_block.connect([pv_control_block.in_vars[2]], [vsc_mdl.out_vars[2]])
pv_control_block.connect([pv_control_block.in_vars[3]], [vsc_mdl.out_vars[3]])
pv_control_block.connect([pv_control_block.in_vars[4]], [pv_cell_block.out_vars[0]])

# external mapping
big_gen1 = Block(children=[genrow_mdl1])
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl1.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl1.out_vars[1]})

# add models to dyn_host
line12_dynhost.model = line12_mdl
load_dynhost.model = load_mdl
gen_dynhost.model = big_gen1
gen3_dynhost.model = Block(children=[pv_cell_block, pv_control_block], external_mapping= pv_cell_block.external_mapping)
vsc_dynhost.model = vsc_mdl

# attach rms models to Veragrid objects
line12.rms_model = line12_dynhost
load1.rms_model = load_dynhost
gen1.rms_model = gen_dynhost
vsc1.rms_model = vsc_dynhost
gen3.rms_model = gen3_dynhost

options = RmsOptions(time_step=0.001,
                     simulation_time=0.5,
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
Vm = find_name_in_block("Vm", genrow_mdl1)

plt.plot(t, y[:, problem.get_var_idx(delta)], label="delta (pu)")
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

pv_all = gen3.rms_model 
vdc = find_name_in_block('Vdc', bus3.rms_model)
vhs = vsc_mdl.out_vars[2]
ahs = vsc_mdl.out_vars[3]

plt.plot(t, y[:, problem.get_var_idx(vdc)], label="vdc (pu)")
plt.plot(t, y[:, problem.get_var_idx(vhs)], label="vhs (pu)")
plt.plot(t, y[:, problem.get_var_idx(ahs)], label="ahs (pu)")
#plt.plot(t, y[:, problem.get_var_idx(Vm)], label="Vm (pu)")
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()