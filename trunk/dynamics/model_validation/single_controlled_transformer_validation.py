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

# Ensure the library can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

from VeraGridEngine import VarPowerFlowRefferenceType, SimulationTypes
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.transformer_rms_template import initialize_trafo_rms
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
from VeraGridEngine.enumerations import DynamicIntegrationMethod, TapModuleControl, TapPhaseControl, RmsInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.enumerations import WindingType
import VeraGridEngine.api as gce

from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from VeraGridEngine.basic_structures import Logger

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

# Grid instantiation
grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Define buses
bus1 = gce.Bus(name='B1', Vnom=135, is_slack=True)
bus2 = gce.Bus(name='B2', Vnom=135)
bus3 = gce.Bus(name='B3', Vnom=135)

# Define AC lines
line12 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
line13 = gce.Line(name="line 1-3", bus_from=bus1, bus_to=bus3, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)

# Define transformer type
trafo_type = gce.TransformerType(name='TransformerType',
                                 hv_nominal_voltage=135,
                                 lv_nominal_voltage=135,
                                 nominal_power=150,
                                 copper_losses=0.5,
                                 iron_losses=0.01,
                                 no_load_current=0.01,
                                 short_circuit_voltage=12.0)
grid.add_transformer_type(trafo_type)

# Define Transformers
# Transformer 1 (Controllable): Bus 2 -> Bus 3
trafo_1 = gce.Transformer2W(name='Trafo 2-3',
                            bus_from=bus2,
                            bus_to=bus3,
                            template=trafo_type,
                            conn=gce.WindingsConnection.GG,
                            tap_phase_control_mode=TapPhaseControl.Pf,
                            Pset=5.0,  # Regulate through flow to 5 MW
                            tap_phase_min=-np.pi/6,
                            tap_phase_max=np.pi/6)
trafo_1.regulation_bus = bus3

# Define generators
gen1 = gce.Generator(name='Gen1', Snom=100.0, r1=1e-4, x1=0.1)

# Define loads
# Total load 10 MW. Trafo 1 should take 5 MW if it can regulate it.
load1 = gce.Load(name='Load1', P=10.0, Q=2.0)

###############
# Add to the grid
grid.add_bus(bus1)
grid.add_bus(bus2) 
grid.add_bus(bus3)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.rms_var_factory)

grid.add_line(line12)
grid.add_line(line13)
grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_load(bus=bus3, api_obj=load1)
grid.add_transformer2w(trafo_1)

grid.apply_all_branch_types()

#########
# Generalized Power Flow
#########
logger = Logger()
nc = gce.compile_numerical_circuit_at(grid, 
                                      t_idx=None, 
                                      control_taps_modules=True, 
                                      control_taps_phase=True, 
                                      logger=logger)

# Debug numerical circuit
print("Pset from NC:", nc.active_branch_data.Pset)
print("Control modes (Phase):", nc.active_branch_data.tap_phase_control_mode)
print("Branch names in NC:", nc.passive_branch_data.names)

pf_options = PowerFlowOptions(gce.SolverType.NR, 
                           verbose=2, 
                           control_taps_modules=False, 
                           control_taps_phase=False,
                           orthogonalize_controls=False)

# Initial guesses
V0 = nc.bus_data.Vbus
S0 = nc.get_power_injections_pu()
I0 = nc.get_current_injections_pu()
Y0 = nc.get_admittance_injections_pu()
Qmin, Qmax = nc.get_reactive_power_limits()

# Create Generalized Power Flow formulation
pf_form = PfGeneralizedFormulation(V0=V0, S0=S0, I0=I0, Y0=Y0, 
                                   Qmin=Qmin, Qmax=Qmax, 
                                   nc=nc, 
                                   options=pf_options, 
                                   logger=logger)

print("\nSolving using Generalized Power Flow Formulation...")
numeric_results = newton_raphson_fx(problem=pf_form,
                                    tol=pf_options.tolerance,
                                    max_iter=pf_options.max_iter,
                                    trust=pf_options.trust_radius,
                                    verbose=pf_options.verbose,
                                    logger=logger)

if not numeric_results.converged:
    print("Power Flow FAILED to converge.")
    sys.exit(1)

# Convert to PowerFlowResults for RMS compatibility
res = gce.PowerFlowResults(
    n=grid.get_bus_number(),
    m=grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
    n_hvdc=grid.get_hvdc_number(),
    n_vsc=grid.get_vsc_number(),
    n_gen=grid.get_generation_like_number(),
    n_batt=grid.get_batteries_number(),
    n_sh=grid.get_shunt_like_device_number(),
    bus_names=grid.get_bus_names(),
    branch_names=grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
    hvdc_names=grid.get_hvdc_names(),
    vsc_names=grid.get_vsc_names(),
    gen_names=grid.get_generation_like_names(),
    batt_names=grid.get_battery_names(),
    sh_names=grid.get_shunt_like_devices_names(),
    bus_types=np.ones(grid.get_bus_number())
)

res.apply_from_island(numeric_results, 
                      b_idx=np.arange(grid.get_bus_number()), 
                      br_idx=np.arange(grid.get_branch_number()),
                      hvdc_idx=np.arange(grid.get_hvdc_number()),
                      vsc_idx=np.arange(grid.get_vsc_number()))

print('Voltage magnitudes (p.u.): ', abs(res.voltage))
print('Voltage angles (deg): ', np.angle(res.voltage, deg=True))

# Update transformer taps from PF results
# Find indices in the numerical circuit
trafo_idx_1 = list(res.branch_names).index(trafo_1.name)

# Update the transformer attributes
trafo_1.tap_module = float(numeric_results.tap_module[trafo_idx_1])
trafo_1.tap_phase = float(numeric_results.tap_angle[trafo_idx_1])

print(f"Trafo flows (PF): Pf={res.Sf[trafo_idx_1].real:.6f}, Pt={res.St[trafo_idx_1].real:.6f}")
print(f"Trafo flows (PF): Qf={res.Sf[trafo_idx_1].imag:.6f}, Qt={res.St[trafo_idx_1].imag:.6f}")
print(f"Trafo 1 Tap Module: {trafo_1.tap_module:.6f}, Phase: {np.degrees(trafo_1.tap_phase):.6f} deg")

# Build dynamic_model_host
line12_dynhost = DynamicModelHost()
line13_dynhost = DynamicModelHost()
load_dynhost = DynamicModelHost()
gen_dynhost = DynamicModelHost()

#Initialise the RMS
line12_mdl = (get_line_rms_template(grid.rms_var_factory).block)
line13_mdl = (get_line_rms_template(grid.rms_var_factory).block)
initialize_trafo_rms(trafo_1, grid.rms_var_factory, Sbase=grid.Sbase)
trafo_mdl = trafo_1.rms_model.model
load_type = 'zip'
if load_type == 'zip':
    load_mdl = (ZIPLoadBuild(grid.rms_var_factory, Pl0 =-0.1, Ql0 =-0.02).block) # Match load 10MW (0.1 pu)
else:
    raise ValueError(f"Unknown load type: {load_type}")

genrow_mdl1 = (get_complete_generator_template(grid.rms_var_factory).block)

genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

load_mdl.connect([load_mdl.in_vars[0]], [bus3.rms_model.model.out_vars[0]])

line12_mdl.connect([line12_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

line12_mdl.connect([line12_mdl.in_vars[2]], [bus2.rms_model.model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[3]], [bus2.rms_model.model.out_vars[1]])

line13_mdl.connect([line13_mdl.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
line13_mdl.connect([line13_mdl.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

line13_mdl.connect([line13_mdl.in_vars[2]], [bus3.rms_model.model.out_vars[0]])
line13_mdl.connect([line13_mdl.in_vars[3]], [bus3.rms_model.model.out_vars[1]])

trafo_mdl.connect([trafo_mdl.in_vars[0]], [bus2.rms_model.model.out_vars[0]])
trafo_mdl.connect([trafo_mdl.in_vars[1]], [bus2.rms_model.model.out_vars[1]])

trafo_mdl.connect([trafo_mdl.in_vars[2]], [bus3.rms_model.model.out_vars[0]])
trafo_mdl.connect([trafo_mdl.in_vars[3]], [bus3.rms_model.model.out_vars[1]])

# external mapping
big_gen1 = Block(children=[genrow_mdl1])
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl1.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl1.out_vars[1]})

# add models to dyn_host
line12_dynhost.model = line12_mdl
line13_dynhost.model = line13_mdl
load_dynhost.model = load_mdl
gen_dynhost.model = big_gen1

# attach rms models to Veragrid objects
line12.rms_model = line12_dynhost
line13.rms_model = line13_dynhost
gen1.rms_model = gen_dynhost
load1.rms_model = load_dynhost

Pl0 = find_name_in_block('P0', load_mdl)
event = RmsEvent(device=load1, parameter=Pl0, time=.2, value=0.1) # Step load from 0.1 to 0.2 pu (20MW)
grid.add_rms_event(event)

options = RmsOptions(time_step=0.001,
                     simulation_time=0.3,
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

plt.figure(figsize=(10, 6))
plt.subplot(2, 1, 1)
plt.plot(t, y[:, problem.get_var_idx(delta)], label="delta (pu)")
plt.plot(t, y[:, problem.get_var_idx(omega)], label="omega (pu)")
plt.plot(t, y[:, problem.get_var_idx(Pg)], label="P (pu)")
plt.plot(t, y[:, problem.get_var_idx(Qg)], label="Q (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
plt.grid(True)

plt.subplot(2, 1, 2)
Pf1 = find_name_in_block('Pf', trafo_1.rms_model.model)
Qf1 = find_name_in_block('Qf', trafo_1.rms_model.model)

plt.plot(t, y[:, problem.get_var_idx(Pf1)], label="Pf Trafo 1 (pu)")
plt.plot(t, y[:, problem.get_var_idx(Qf1)], label="Qf Trafo 1 (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.show()

#########
# Generalized Power Flow
#########
logger = Logger()
nc = gce.compile_numerical_circuit_at(grid, 
                                      t_idx=None, 
                                      control_taps_modules=True, 
                                      control_taps_phase=True, 
                                      logger=logger)

# Debug numerical circuit
print("Pset from NC:", nc.active_branch_data.Pset)
print("Control modes (Phase):", nc.active_branch_data.tap_phase_control_mode)
print("Branch names in NC:", nc.passive_branch_data.names)

options = PowerFlowOptions(gce.SolverType.NR, 
                           verbose=2, 
                           control_taps_modules=True, 
                           control_taps_phase=True)

# Initial guesses
V0 = nc.bus_data.Vbus
S0 = nc.get_power_injections_pu()
I0 = nc.get_current_injections_pu()
Y0 = nc.get_admittance_injections_pu()
Qmin, Qmax = nc.get_reactive_power_limits()

# Create Generalized Power Flow formulation
pf_form = PfGeneralizedFormulation(V0=V0, S0=S0, I0=I0, Y0=Y0, 
                                   Qmin=Qmin, Qmax=Qmax, 
                                   nc=nc, 
                                   options=options, 
                                   logger=logger)

print("\nSolving using Generalized Power Flow Formulation...")
numeric_results = newton_raphson_fx(problem=pf_form,
                                    tol=options.tolerance,
                                    max_iter=options.max_iter,
                                    trust=options.trust_radius,
                                    verbose=options.verbose,
                                    logger=logger)

if not numeric_results.converged:
    print("Power Flow FAILED to converge.")
    sys.exit(1)

# Convert to PowerFlowResults for RMS compatibility
res = gce.PowerFlowResults(
    n=grid.get_bus_number(),
    m=grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
    n_hvdc=grid.get_hvdc_number(),
    n_vsc=grid.get_vsc_number(),
    n_gen=grid.get_generation_like_number(),
    n_batt=grid.get_batteries_number(),
    n_sh=grid.get_shunt_like_device_number(),
    bus_names=grid.get_bus_names(),
    branch_names=grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
    hvdc_names=grid.get_hvdc_names(),
    vsc_names=grid.get_vsc_names(),
    gen_names=grid.get_generation_like_names(),
    batt_names=grid.get_battery_names(),
    sh_names=grid.get_shunt_like_devices_names(),
    bus_types=np.ones(grid.get_bus_number())
)

res.apply_from_island(numeric_results, 
                      b_idx=np.arange(grid.get_bus_number()), 
                      br_idx=np.arange(grid.get_branch_number()),
                      hvdc_idx=np.arange(grid.get_hvdc_number()),
                      vsc_idx=np.arange(grid.get_vsc_number()))

print('Voltage magnitudes (p.u.): ', abs(res.voltage))
print('Voltage angles (deg): ', np.angle(res.voltage, deg=True))

# Update transformer taps from PF results
# Find indices in the numerical circuit
trafo_idx_1 = list(res.branch_names).index(trafo_1.name)

# Update the transformer attributes
trafo_1.tap_module = float(numeric_results.tap_module[trafo_idx_1])
trafo_1.tap_phase = float(numeric_results.tap_angle[trafo_idx_1])

print(f"Trafo flows (PF): Pf={res.Sf[trafo_idx_1].real:.6f}, Pt={res.St[trafo_idx_1].real:.6f}")
print(f"Trafo flows (PF): Qf={res.Sf[trafo_idx_1].imag:.6f}, Qt={res.St[trafo_idx_1].imag:.6f}")
print(f"Trafo 1 Tap Module: {trafo_1.tap_module:.6f}, Phase: {np.degrees(trafo_1.tap_phase):.6f} deg")
