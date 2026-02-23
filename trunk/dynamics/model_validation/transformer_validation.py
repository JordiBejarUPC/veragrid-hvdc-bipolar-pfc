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


from VeraGridEngine import VarPowerFlowRefferenceType, power_flow, DynamicIntegrationMethod
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.vsc_template import VscControlledPV, VSCShuntBuild, VSCShuntBuild2, PVCellBuild, PVControlBuild2
from VeraGridEngine.Templates.Rms.vsc_gfl import VscGflBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCVoltageSource
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.enumerations import WindingType
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
grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Define buses
bus1 = gce.Bus(name='B1', Vnom=135, is_slack=True)
bus2 = gce.Bus(name='B2', Vnom=135)
bus3 = gce.Bus(name='B3', Vnom=100)

# Define AC lines
line12 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)

# Define transformer type
trafo_type = gce.TransformerType(name='TransformerType',
                                 hv_nominal_voltage=135,
                                 lv_nominal_voltage=100,
                                 nominal_power=150,
                                 copper_losses=0.5,
                                 iron_losses=0.01,
                                 no_load_current=0.01,
                                 short_circuit_voltage=12.0)
grid.add_transformer_type(trafo_type)

trafo_1 = gce.Transformer2W(name='Transformer',
                            bus_from=bus2,
                            bus_to=bus3,
                            template=trafo_type)
# Define generators
gen1 = gce.Generator(name='Gen1', P=10.0, vset=1.00)

# Define loads
load1 = gce.Load(name='Load1', P=1.0, Q=0.1)

###############
# Add to the grid
grid.add_bus(bus1)
grid.add_bus(bus2) 
grid.add_bus(bus3)

bus1.initialize_rms()
bus2.initialize_rms()
bus3.initialize_rms()

grid.add_line(line12)
grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_load(bus=bus3, api_obj=load1)
grid.add_transformer2w(trafo_1)

grid.apply_all_branch_types()

#########
pf_driver = gce.PowerFlowDriver(grid=grid)
pf_driver.run()
res = pf_driver.results
print('Voltage magnitudes (p.u.): ', abs(pf_driver.results.voltage))
print('Voltage angles (deg): ', np.angle(pf_driver.results.voltage, deg=True))

# Print transformer flows
trafo_idx = list(res.branch_names).index(trafo_1.name)
print(f"Trafo flows (PF): Pf={res.Sf[trafo_idx].real:.6f}, Pt={res.St[trafo_idx].real:.6f}")
print(f"Trafo flows (PF): Qf={res.Sf[trafo_idx].imag:.6f}, Qt={res.St[trafo_idx].imag:.6f}")

#Initialise the RMS
line12_mdl = block_deep_copy(get_line_rms_template().block)
trafo_1.initialize_rms()
trafo_mdl = trafo_1.rms_model.model

load_type = 'zip'
if load_type == 'zip':
    load_mdl = block_deep_copy(ZIPLoadBuild(Pl0 =-0.01, Ql0 =-0.001).block)
genrow_mdl1 = block_deep_copy(get_genrow1_rms_template().block)

genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

load_mdl.connect([load_mdl.in_vars[0]], [bus3.rms_model.model.out_vars[0]])

line12_mdl.connect([line12_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

line12_mdl.connect([line12_mdl.in_vars[2]], [bus2.rms_model.model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[3]], [bus2.rms_model.model.out_vars[1]])


line12.rms_model.model   = line12_mdl
gen1.rms_model.model     = genrow_mdl1
load1.rms_model.model    = load_mdl

Pl0 = find_name_in_block('P0', load_mdl)
event = RmsEvent(device=load1, parameter=Pl0, time=.2, value=0.1)
grid.add_rms_event(event)

sim_time, ss, init_guess = initialize_rms(grid, res, use_init_values=False)

slv = BlockSolver(ss, sim_time)
params_mapping = {}
params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector_from_uid(init_guess)
dx0 = np.zeros(len(slv._diff_vars))
Vm = find_name_in_block("Vm", slv.block_system)

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

plt.plot(t, y[:, slv.get_var_idx(delta)], label="delta (pu)")
plt.plot(t, y[:, slv.get_var_idx(Vm)], label="Vm (pu)")
plt.plot(t, y[:, slv.get_var_idx(Pg)], label="P (pu)")
plt.plot(t, y[:, slv.get_var_idx(Qg)], label="Q (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()

Pf_trafo = find_name_in_block('Pf', trafo_1.rms_model.model)
Qf_trafo = find_name_in_block('Qf', trafo_1.rms_model.model)
Pt_trafo = find_name_in_block('Pt', trafo_1.rms_model.model)
Qt_trafo = find_name_in_block('Qt', trafo_1.rms_model.model)

plt.plot(t, y[:, slv.get_var_idx(Pf_trafo)], label="Pf Trafo (pu)")
plt.plot(t, y[:, slv.get_var_idx(Qf_trafo)], label="Qf Trafo (pu)")
plt.plot(t, y[:, slv.get_var_idx(Pt_trafo)], label="Pt Trafo (pu)")
plt.plot(t, y[:, slv.get_var_idx(Qt_trafo)], label="Qt Trafo (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.show()