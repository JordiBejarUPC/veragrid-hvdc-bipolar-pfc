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
from VeraGridEngine.Templates.Rms.vsc_template import VscControlledPV, VSCShuntBuild, VSCShuntBuild2, PVCellBuild, PVControlBuild2
from VeraGridEngine.Templates.Rms.vsc_gfl import VscGflBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCVoltageSource
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.enumerations import ConverterControlType
import VeraGridEngine.api as gce

def block_dimensions(block:Block):
    res_vars = 0
    res_eqs = 0
    for b in block.get_all_blocks():
        res_vars += len(b.algebraic_vars) 
        res_eqs += len(b.algebraic_eqs)
    print(f"Block has {res_vars} vars and res_eqs {res_eqs}")
    return 

def find_name_in_block(name: str, block: Block):
    """Recursively find a variable by name in the block and all its children."""
    # Check in the current block's variables
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var
    
    # Recursively search in children
    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res
    
    return None

pr = profile.Profile()
pr.disable()


# Grid instantiation
grid = gce.MultiCircuit()

# Define buses
bus1 = gce.Bus(name='B1', Vnom=135, is_slack=True)
bus2 = gce.Bus(name='B2', Vnom=135)
bus3 = gce.Bus(name='B3', Vnom=100, is_dc=True)

# Define AC lines
line12 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)

# Select control modes for the VSC
# Options for control1: ConverterControlType.Pac, ConverterControlType.Pdc, ConverterControlType.Vm_dc
# Options for control2: ConverterControlType.Qac, ConverterControlType.Vm_ac
CONTROL1_MODE = ConverterControlType.Vm_dc
CONTROL2_MODE = ConverterControlType.Vm_ac

# Define VSCs with the selected control modes
vsc1 = gce.VSC(name='VSC1', bus_from=bus3, bus_to=bus2, rate=100, alpha1=0.0, alpha2=0.0, alpha3=0.0,
               control1=CONTROL1_MODE, control2=CONTROL2_MODE,
               control1_val=1.03, control2_val=1.001)

# Define generators
gen1 = gce.Generator(name='Gen1', P=5.0, vset=1.00)

# Define loads
load1 = gce.Load(name='Load1', P=10, Q=1.0)
#load2 = gce.Load(name='Load2', P=2.0, Q=0.5)


#Grid modifications
#grid.add_load(bus = bus3, api_obj=load3)
injection = 'load'
gen3 = gce.Load(name='Load1', P=-1.0, Q =-0.1)
grid.add_load(bus=bus3, api_obj=gen3)

###############
# Add to the grid
grid.add_bus(bus1)
grid.add_bus(bus2) 
grid.add_bus(bus3)

bus1.initialize_rms()
bus2.initialize_rms()
bus3.initialize_rms()

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
line12_mdl = block_deep_copy(get_line_rms_template().block)
load_type = 'zip'
if load_type == 'zip':
    load_mdl = block_deep_copy(ZIPLoadBuild(Pl0 =-0.1, Ql0 =-0.01).block)
else:
    raise ValueError(f"Unknown load type: {load_type}")
    
genrow_mdl1 = block_deep_copy(get_genrow1_rms_template().block)

# Build VSC model with the same control modes used in the VSC device
vsc_mdl = block_deep_copy(VscGflBuild(control1=CONTROL1_MODE, control2=CONTROL2_MODE).block)

pv_cell_block  =  block_deep_copy(PVCellBuild().block)
dc_source = block_deep_copy(DCVoltageSource(bus3.rms_model.model.out_vars[0]).block)

genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

load_mdl.connect([load_mdl.in_vars[0]], [bus2.rms_model.model.out_vars[0]])

line12_mdl.connect([line12_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

line12_mdl.connect([line12_mdl.in_vars[2]], [bus2.rms_model.model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[3]], [bus2.rms_model.model.out_vars[1]]) 

# Updated connections for new VSC model with 3 inputs: [Vm, Va, Vdc]
vsc_mdl.connect([vsc_mdl.in_vars[0]], [bus2.rms_model.model.out_vars[0]])  # Vm
vsc_mdl.connect([vsc_mdl.in_vars[1]], [bus2.rms_model.model.out_vars[1]])  # Va
vsc_mdl.connect([vsc_mdl.in_vars[2]], [bus3.rms_model.model.out_vars[0]])  # Vdc

#vsc_mdl.connect([vsc_mdl.in_vars[3]], [bus3.rms_model.model.out_vars[1]]) 
#pv_cell_block.connect([pv_cell_block.in_vars[0]], [bus3.rms_model.model.out_vars[0]])


line12.rms_model.model   = line12_mdl
gen1.rms_model.model     = genrow_mdl1
load1.rms_model.model    = load_mdl
vsc1.rms_model.model     = vsc_mdl
gen3.rms_model.model     = dc_source
gen3.rms_model.model.unify_blocks()

block_dimensions(vsc_mdl)
block_dimensions(gen3.rms_model.model)
Vpv0 = find_name_in_block('Vpv0', gen3.rms_model.model)

# Find appropriate reference variable based on control mode
if CONTROL1_MODE == ConverterControlType.Vm_dc:
    ref_var = find_name_in_block('Vdc_ref', vsc_mdl)
    print(f"Using Vdc_ref for control mode {CONTROL1_MODE}")
elif CONTROL1_MODE in [ConverterControlType.Pac, ConverterControlType.Pdc]:
    ref_var = find_name_in_block('P_ref', vsc_mdl)
    print(f"Using P_ref for control mode {CONTROL1_MODE}")
else:
    ref_var = find_name_in_block('P_ref', vsc_mdl)
    print(f"Using P_ref for control mode {CONTROL1_MODE}")

event1 = RmsEvent(device=gen3, parameter=Vpv0, time=.2, value=0.3)
event2 = RmsEvent(device=vsc1, parameter=ref_var, time=.2, value=0.1)
grid.add_rms_event(event1)
grid.add_rms_event(event2)

sim_time, ss, init_guess = initialize_rms(grid, res, use_init_values=False)

slv = BlockSolver(ss, sim_time)
params_mapping = {}
params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector_from_uid(init_guess)
dx0 = np.zeros(len(slv._diff_vars))
Vm_var = find_name_in_block("Vm", slv.block_system)

xlim = 0.3
t, y, _ = slv.simulate(
    t0=0,
    t_end=xlim,
    h=1e-3,
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

Pg = genrow_mdl1.out_vars[0]
Qg = genrow_mdl1.out_vars[1]
delta = find_name_in_block("delta", genrow_mdl1)

plt.figure(figsize=(10, 6))
plt.plot(t, y[:, slv.get_var_idx(delta)], label="delta (pu)")
plt.plot(t, y[:, slv.get_var_idx(Vm_var)], label="Vm (pu)")
plt.plot(t, y[:, slv.get_var_idx(Pg)], label="P (pu)")
plt.plot(t, y[:, slv.get_var_idx(Qg)], label="Q (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC GFL Control: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
plt.show()

pv_all = gen3.rms_model.model 
vdc = find_name_in_block('Vdc', bus3.rms_model.model)
v_d = find_name_in_block('vd', vsc_mdl)
v_q = find_name_in_block('vq', vsc_mdl)
v_d_c = find_name_in_block('v_d_c', vsc_mdl)
v_q_c = find_name_in_block('v_q_c', vsc_mdl)
P = find_name_in_block('P', vsc_mdl)
Q = find_name_in_block('Q', vsc_mdl)
i_d = find_name_in_block('i_d', vsc_mdl)
i_q = find_name_in_block('i_q', vsc_mdl)
Idc = find_name_in_block('Idc', gen3.rms_model.model)
Vdc = find_name_in_block('Vdc', bus3.rms_model.model)
Pdc = find_name_in_block('Pdc', dc_source)

plt.figure(figsize=(10, 6))
plt.plot(t, y[:, slv.get_var_idx(Vdc)], label="vdc (pu)")
plt.plot(t, y[:, slv.get_var_idx(Pdc)], label="Pdc (pu)")
#plt.plot(t, y[:, slv.get_var_idx(v_d_c)], label="vd converter (pu)")
#plt.plot(t, y[:, slv.get_var_idx(v_q_c)], label="vq converter (pu)")
#plt.plot(t, y[:, slv.get_var_idx(v_d)], label="vd grid (pu)")
#plt.plot(t, y[:, slv.get_var_idx(v_q)], label="vq grid (pu)")
#plt.plot(t, y[:, slv.get_var_idx(P)], label="P (pu)")
plt.plot(t, y[:, slv.get_var_idx(Q)], label="Q (pu)")
plt.plot(t, y[:, slv.get_var_idx(Idc)], label="Idc (pu)")
#plt.plot(t, y[:, slv.get_var_idx(i_d)], label="id (pu)")
#plt.plot(t, y[:, slv.get_var_idx(i_q)], label="iq (pu)")
#plt.plot(t, y[:, slv.get_var_idx(Vm)], label="Vm (pu)")
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC DC Side: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
plt.show()

print(f"\nSimulation completed with control modes: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}")
print("Supported combinations:")
print("  - Pac + Qac: Active and reactive power control")
print("  - Pac + Vm_ac: Active power and AC voltage control")
print("  - Pdc + Qac: DC power and reactive power control")
print("  - Pdc + Vm_ac: DC power and AC voltage control")
print("  - Vm_dc + Qac: DC voltage and reactive power control")
print("  - Vm_dc + Vm_ac: DC voltage and AC voltage control")
