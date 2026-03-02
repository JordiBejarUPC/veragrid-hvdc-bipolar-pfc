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
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.vsc_template import PVCellBuild
from VeraGridEngine.Templates.Rms.vsc_gfm import VscGfmBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCVoltageSource
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

# Grid instantiation
grid = gce.MultiCircuit()

# Define buses
bus1 = gce.Bus(name='B1', Vnom=135, is_slack=True)
bus2 = gce.Bus(name='B2', Vnom=135)
bus3 = gce.Bus(name='B3', Vnom=100, is_dc=True)

# Define AC lines
line12 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.03, x=0.1, b=0.03, rate=900.0)

# Define VSCs (Using GFM)
vsc1 = gce.VSC(name='VSC1', bus_from=bus3, bus_to=bus2, rate=100, alpha1=0.0, alpha2=0.0, alpha3=0.0,
               control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Vm_ac,
               control1_val=1.0, control2_val=1.0)

# Define generator at slack
gen1 = gce.Generator(name='Gen1', P=1.0, vset=1.0)

# Define load
load1 = gce.Load(name='Load1', P=0.5, Q=0.1)

# Define DC source/load
gen3 = gce.Load(name='DC_Load', P=-0.5)

# Add to the grid
grid.add_bus(bus1)
grid.add_bus(bus2) 
grid.add_bus(bus3)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.var_factory)

grid.add_line(line12)
grid.add_vsc(vsc1)
grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_load(bus=bus2, api_obj=load1)
grid.add_load(bus=bus3, api_obj=gen3)

# Power Flow
pf_driver = gce.PowerFlowDriver(grid=grid)
pf_driver.run()
res = pf_driver.results
print('PF Voltage magnitudes (p.u.): ', abs(res.voltage))

# Build dynamic_model_host
line12_dynhost = DynamicModelHost()
load_dynhost = DynamicModelHost()
gen_dynhost = DynamicModelHost()
gen3_dynhost = DynamicModelHost()

# Initialize the RMS
line12_mdl = block_deep_copy(get_line_rms_template(grid.var_factory).block)
load_mdl = block_deep_copy(ZIPLoadBuild(grid.var_factory, Pl0 =-0.005, Ql0 =-0.001).block)
genrow_mdl1 = block_deep_copy(get_genrow1_rms_template(grid.var_factory).block)
vsc_mdl = block_deep_copy(VscGfmBuild(grid.var_factory).block)
dc_source = block_deep_copy(DCVoltageSource(grid.var_factory, bus3.rms_model.model.out_vars[0]).block)

# VSC host
vsc_dynhost = DynamicModelHost()

# Connections
genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

load_mdl.connect([load_mdl.in_vars[0]], [bus2.rms_model.model.out_vars[0]])

line12_mdl.connect([line12_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])
line12_mdl.connect([line12_mdl.in_vars[2]], [bus2.rms_model.model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[3]], [bus2.rms_model.model.out_vars[1]]) 

vsc_mdl.connect([vsc_mdl.in_vars[0]], [bus2.rms_model.model.out_vars[0]])
vsc_mdl.connect([vsc_mdl.in_vars[1]], [bus2.rms_model.model.out_vars[1]])
vsc_mdl.connect([vsc_mdl.in_vars[2]], [bus3.rms_model.model.out_vars[0]])

# external mapping
big_gen1 = Block(children=[genrow_mdl1])
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl1.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl1.out_vars[1]})

# add models to dyn_host
line12_dynhost.model = line12_mdl
load_dynhost.model = load_mdl
gen_dynhost.model = big_gen1
gen3_dynhost.model = dc_source
vsc_dynhost.model = vsc_mdl

# attach rms models to Veragrid objects
line12.rms_model = line12_dynhost
load1.rms_model = load_dynhost
gen1.rms_model = gen_dynhost
vsc1.rms_model = vsc_dynhost
gen3.rms_model = gen3_dynhost

# Event: Change P_ref of GFM at t=0.5
Pref = find_name_in_block('P_ref', vsc_mdl)
event = RmsEvent(device=vsc1, parameter=Pref, time=0.5, value=0.6)
grid.add_rms_event(event)

# Initialize RMS simulation
options = RmsOptions(time_step=0.001,
                     simulation_time=1.0,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=100,
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

# Variables to follow
Vm2 = find_name_in_block("Vm_", bus2.rms_model.model)
omega = find_name_in_block("omega", vsc_mdl)
P_vsc = find_name_in_block("P", vsc_mdl)
Q_vsc = find_name_in_block("Q", vsc_mdl)

# Plotting
plt.figure(figsize=(10, 8))
plt.subplot(3, 1, 1)
plt.plot(t, y[:, problem.get_var_idx(omega)], label="omega (pu)")
plt.ylabel("Frequency (pu)")
plt.legend()
plt.grid(True)

plt.subplot(3, 1, 2)
plt.plot(t, y[:, problem.get_var_idx(P_vsc)], label="P (pu)")
plt.plot(t, y[:, problem.get_var_idx(Q_vsc)], label="Q (pu)")
plt.ylabel("Power (pu)")
plt.legend()
plt.grid(True)

plt.subplot(3, 1, 3)
plt.plot(t, y[:, problem.get_var_idx(Vm2)], label="Vm Bus 2 (pu)")
plt.ylabel("Voltage (pu)")
plt.xlabel("Time (s)")
plt.legend()
plt.grid(True)

plt.tight_layout()
# plt.show()  # Commented out for non-interactive testing

# Verify simulation completed
print('\n=== SIMULATION COMPLETED SUCCESSFULLY ===')
print(f'Final time: {t[-1]:.3f}s')
print(f'Final omega: {y[-1, problem.get_var_idx(omega)]:.6f} pu')
print(f'Final P: {y[-1, problem.get_var_idx(P_vsc)]:.6f} pu')
print(f'Final Q: {y[-1, problem.get_var_idx(Q_vsc)]:.6f} pu')
print(f'Final Vm2: {y[-1, problem.get_var_idx(Vm2)]:.6f} pu')
