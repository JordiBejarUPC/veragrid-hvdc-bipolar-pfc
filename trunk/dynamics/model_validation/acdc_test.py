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
from VeraGridEngine.Templates.Rms.vsc_template import VscControlledPV, VSCShuntBuild, VSCShunt2Build
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
from VeraGridEngine.enumerations import DynamicIntegrationMethod
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
vsc1 = gce.VSC(name='VSC1', bus_from=bus3, bus_to=bus2, rate=100, alpha1=0.001, alpha2=0.015, alpha3=0.01,
               control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Qac,
               control1_val=1.0333, control2_val=0.02)

# vsc2 = gce.VSC(name='VSC2', bus_from=bus4, bus_to=bus5, rate=100, alpha1=0.001, alpha2=0.015, alpha3=0.01,
#                control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Qac,
#                control1_val=1.05, control2_val=-0.21)

# Define generators
gen1 = gce.Generator(name='Gen1', P=1.0, vset=1.01)
#gen2 = gce.Generator(name='Gen2', P=1.0, vset=1.02)

# Define loads
load1 = gce.Load(name='Load1', P=3.0, Q=0.3)
load2 = gce.Load(name='Load2', P=2.0, Q=0.5)
load3 = gce.Load(name='Load3', G=0.5, B=0.3)  # DC load


#Grid modifications
#grid.add_load(bus = bus3, api_obj=load3)
gen3 = gce.CurrentInjection(name='Gen3', Ir =0.2)
grid.add_current_injection(bus=bus3, api_obj=gen3)


###############
# Add to the grid
grid.add_bus(bus1)
grid.add_bus(bus2) 
grid.add_bus(bus3)

grid.add_line(line12)
grid.add_vsc(vsc1)

grid.add_generator(bus=bus1, api_obj=gen1)

grid.add_load(bus=bus2, api_obj=load1)


#########
pf_driver = gce.PowerFlowDriver(grid=grid)
pf_driver.run()
print('Voltage magnitudes (p.u.): ', abs(pf_driver.results.voltage))
print('Voltage angles (deg): ', np.angle(pf_driver.results.voltage, deg=True))

#Initialise the RMS
line12_mdl = block_deep_copy(get_line_rms_template().block)
load_type = 'zip'
if load_type == 'zip':
    load_mdl = block_deep_copy(ZIPLoadBuild(Pl0 =-0.0999999, Ql0 =-0.00999999).block)

genrow_mdl1 = block_deep_copy(get_genrow1_rms_template().block)
vsc_mdl   = block_deep_copy(VSCShunt2Build().block)
injection_mdl = block_deep_copy(get_load_rms_template().block)

genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

line12_mdl.connect([line12_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

line12_mdl.connect([line12_mdl.in_vars[2]], [bus2.rms_model.model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[3]], [bus2.rms_model.model.out_vars[1]]) 

vsc_mdl.connect([vsc_mdl.in_vars[0]], [bus2.rms_model.model.out_vars[0]])
vsc_mdl.connect([vsc_mdl.in_vars[1]], [bus2.rms_model.model.out_vars[1]])

vsc_mdl.connect([vsc_mdl.in_vars[2]], [bus3.rms_model.model.out_vars[0]])
vsc_mdl.connect([vsc_mdl.in_vars[3]], [bus3.rms_model.model.out_vars[1]]) 


line12.rms_model.model   = line12_mdl
gen1.rms_model.model     = genrow_mdl1
load1.rms_model.model    = load_mdl
vsc1.rms_model.model     = vsc_mdl
gen3.rms_model.model     = injection_mdl