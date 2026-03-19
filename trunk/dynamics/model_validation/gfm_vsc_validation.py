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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.vsc_template import PVCellBuild
from VeraGridEngine.Templates.Rms.vsc_gfm import VscGfmBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCVoltageSource
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration

from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
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

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.rms_var_factory)

grid.add_line(line12)
grid.add_vsc(vsc1)
grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_load(bus=bus2, api_obj=load1)


#########
# Use generalized power flow for better VSC support
print("Running generalized power flow...")
nc = compile_numerical_circuit_at(circuit=grid)
islands = nc.split_into_islands(consider_hvdc_as_island_links=True)
print(f"Base: nbus {nc.nbus}, nbr: {nc.nbr}, nvsc: {nc.nvsc}, nhvdc: {nc.nhvdc}")

pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, tolerance=1e-11, verbose=2)
logger = Logger()
island = islands[0]

# Get power injections and other data from the island
S0 = island.get_power_injections_pu()
I0 = island.get_current_injections_pu()
Y0 = island.get_admittance_injections_pu()
Qmin, Qmax = island.get_reactive_power_limits()

problem = PfGeneralizedFormulation(V0=island.bus_data.Vbus,
                                   S0=S0,
                                   I0=I0,
                                   Y0=Y0,
                                   Qmin=Qmin,
                                   Qmax=Qmax,
                                   nc=island,
                                   options=pf_options,
                                   logger=logger)

solution = newton_raphson_fx(problem=problem,
                             tol=pf_options.tolerance,
                             max_iter=pf_options.max_iter,
                             trust=pf_options.trust_radius,
                             verbose=pf_options.verbose,
                             logger=logger)

print("Solution converged:", solution.converged)
print("Solution iterations:", solution.iterations)
print("Solution error:", solution.norm_f)
print("Solution voltage:", solution.V)

# Create proper PowerFlowResults object from generalized power flow solution
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults

# Calculate power flows for branches
Sf = np.zeros(nc.nbr, dtype=complex)
St = np.zeros(nc.nbr, dtype=complex)
V = solution.V

for i in range(nc.nbr):
    f = nc.passive_branch_data.F[i]
    t = nc.passive_branch_data.T[i]
    
    r = nc.passive_branch_data.R[i]
    x = nc.passive_branch_data.X[i]
    b = nc.passive_branch_data.B[i]
    
    if r != 0 or x != 0:
        y_series = 1.0 / complex(r, x)
        I_from = y_series * (V[f] - V[t]) + complex(0, b/2) * V[f]
        I_to = y_series * (V[t] - V[f]) + complex(0, b/2) * V[t]
        
        Sf[i] = V[f] * np.conj(I_from)
        St[i] = V[t] * np.conj(I_to)

# Get bus power injections
Sbus = nc.get_power_injections_pu()

# Create PowerFlowResults with required attributes
bus_names = np.array([bus.name for bus in grid.buses])
branch_names = np.array([br.name for br in grid.get_branches_iter()])
hvdc_names = np.array([hvdc.name for hvdc in grid.hvdc_lines])
vsc_names = np.array([vsc.name for vsc in grid.vsc_devices])
gen_names = np.array([gen.name for gen in grid.generators])
batt_names = np.array([batt.name for batt in grid.batteries])
sh_names = np.array([sh.name for sh in grid.shunts])

# Determine bus types (1=slack, 2=PV, 3=PQ)
bus_types = np.zeros(nc.nbus, dtype=int)
for i, bus in enumerate(grid.buses):
    if bus.is_slack:
        bus_types[i] = 1
    else:
        bus_types[i] = 3  # Assume PQ for now

res = PowerFlowResults(
    n=nc.nbus,
    m=nc.nbr,
    n_hvdc=nc.nhvdc,
    n_vsc=nc.nvsc,
    n_gen=len(grid.generators),
    n_batt=len(grid.batteries),
    n_sh=len(grid.shunts),
    bus_names=bus_names,
    branch_names=branch_names,
    hvdc_names=hvdc_names,
    vsc_names=vsc_names,
    gen_names=gen_names,
    batt_names=batt_names,
    sh_names=sh_names,
    bus_types=bus_types
)

# Set the solution data
res.voltage = solution.V
res.Sf = Sf
res.St = St
res.Sbus = Sbus

# Calculate VSC power flow results from the generalized formulation solution
# VSC power at the DC side (from bus) and AC side (to bus)
res.Pfp_vsc = np.zeros(nc.nvsc, dtype=float)
res.Pfn_vsc = np.zeros(nc.nvsc, dtype=float)
res.St_vsc = np.zeros(nc.nvsc, dtype=complex)

for i, vsc in enumerate(grid.vsc_devices):
    # Get bus indices
    dc_bus_idx = grid.buses.index(vsc.bus_from)
    ac_bus_idx = grid.buses.index(vsc.bus_to)
    
    # Calculate power at AC side (St_vsc) from the solution
    # This comes from the VSC's control values and the solution
    V_ac = solution.V[ac_bus_idx]
    V_dc = solution.V[dc_bus_idx]
    
    # Get control values (these are the setpoints from power flow)
    P_set = vsc.control1_val if vsc.control1 in [ConverterControlType.Pac, ConverterControlType.Pdc] else 0.0
    Q_set = vsc.control2_val if vsc.control2 == ConverterControlType.Qac else 0.0
    
    # For now, use the control setpoints as the power flow results
    # In a real scenario, these would come from the power flow solution
    res.St_vsc[i] = complex(-P_set, -Q_set)  # Negative because VSC injects power
    res.Pfp_vsc[i] = P_set  # DC side power
    res.Pfn_vsc[i] = 0.0  # Not used for 2-terminal VSC

res.St = solution.St
res.Sf = solution.Sf
res.St_vsc = solution.St_vsc
res.Pfn_vsc = solution.Pfn_vsc
res.Pfp_vsc = solution.Pfp_vsc
res.Sbus = solution.Scalc
print('Voltage magnitudes (p.u.): ', abs(res.voltage))
print('Voltage angles (deg): ', np.angle(res.voltage, deg=True))



#Initialise the RMS
line12_mdl = get_line_rms_template(grid.rms_var_factory).block
load_type = 'zip'
if load_type == 'zip':
    load_mdl = ZIPLoadBuild(grid.rms_var_factory, Pl0 =-0.1, Ql0 =-0.01).block
else:
    raise ValueError(f"Unknown load type: {load_type}")
    
genrow_mdl1 = get_genrow1_rms_template(grid.rms_var_factory).block
genrow_mdl1 = get_complete_generator_template(grid.rms_var_factory).block

# Initialize the RMS
line12_mdl = (get_line_rms_template(grid.rms_var_factory).block)
load_mdl = (ZIPLoadBuild(grid.rms_var_factory, Pl0 =-0.1, Ql0 =-0.01).block)
vsc_mdl = (VscGfmBuild(grid.rms_var_factory).block)

# DEBUG: Check all blocks and their init_eqs
print("\n=== VSC MODEL STRUCTURE ===")
for i, b in enumerate(vsc_mdl.get_all_blocks()):
    print(f"\nBlock {i}: {getattr(b, 'name', 'unnamed')}")
    print(f"  algebraic_vars: {[v.name for v in b.algebraic_vars]}")
    print(f"  state_vars: {[v.name for v in b.state_vars]}")
    print(f"  diff_vars: {[v.name for v in b.diff_vars]}")
    print(f"  init_eqs keys: {[v.name for v in b.init_eqs.keys()]}")

dc_source = (DCVoltageSource(grid.rms_var_factory, bus3.rms_model.out_vars[0]).block)



# Connections
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

# external mapping
big_gen1 = Block(children=[genrow_mdl1])
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl1.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl1.out_vars[1]})

# attach rms models to Veragrid objects
line12.rms_model = line12_mdl
load1.rms_model = load_mdl
gen1.rms_model = big_gen1
vsc1.rms_model = vsc_mdl
gen3.rms_model = dc_source

# Event: Change P_ref of GFM at t=0.5
Pref = find_name_in_block('P_ref', vsc_mdl)
event_time = 0.05
event_value = -0.214

print(f"\n=== DEBUG: Setting up RMS Event ===")
print(f"Event target: P_ref (uid={Pref.uid})")
print(f"Event time: {event_time} s")
print(f"Event value: {event_value} pu")
print(f"Device: {vsc1.name}")

events_group = RmsEventsGroup("simulation1")
event = RmsEvent(device=vsc1, parameter=Pref, time=event_time, value=event_value, group=events_group)
grid.add_rms_event(event)

# Verify event was added
print(f"Total events in grid: {len(grid.rms_events)}")
for i, ev in enumerate(grid.rms_events):
    print(f"  Event {i}: time={ev.time}, value={ev.value}, param_uid={ev.parameter.uid}")

# Initialize RMS simulation
options = RmsOptions(time_step=0.001,
                     simulation_time=0.2,  # Extended to see event effect
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=100,
                     verbose=0)

problem = RmsProblemDae(grid=grid,
                        options=options,
                        pf_results=res)

problem.set_events_group(events_group)

# Debug: Check variable parameters
print("\n=== DEBUG: Variable Parameters ===")
for i, param in enumerate(problem._variable_parameters):
    print(f"  Param {i}: {param.name} (uid={param.uid})")
print(f"Total variable parameters: {len(problem._variable_parameters)}")

# Check if P_ref appears multiple times
pref_indices = [i for i, p in enumerate(problem._variable_parameters) if p.name == 'P_ref']
print(f"\nP_ref appears {len(pref_indices)} times at indices: {pref_indices}")
if len(pref_indices) > 1:
    print("WARNING: P_ref appears multiple times - this could cause issues!")
    for idx in pref_indices:
        print(f"  Index {idx}: uid={problem._variable_parameters[idx].uid}")
        print(f"  Initial eq: {problem._event_parameters_eqs[idx]}")

# Debug: Check if P_ref is in variable parameters
pref_in_params = any(p.name == 'P_ref' for p in problem._variable_parameters)
print(f"P_ref in variable parameters: {pref_in_params}")
if pref_in_params:
    pref_param = next(p for p in problem._variable_parameters if p.name == 'P_ref')
    print(f"  P_ref uid: {pref_param.uid}")
    print(f"  Event Pref uid: {Pref.uid}")
    print(f"  UIDs match: {pref_param.uid == Pref.uid}")

solver = BackEulerImplicitIntegration(
    problem=problem,
    t0=0,
    t_end=options.simulation_time,
    h=options.time_step,
    max_iter=options.max_iter
)

print("\n=== DEBUG: Before simulation ===")
print(f"P_ref initial value: {Pref.value if hasattr(Pref, 'value') else 'N/A'}")
print(f"Starting simulation from t=0 to t={options.simulation_time}s")
print(f"Event scheduled at t={event_time}s")

# Check initial variable parameters
print("\n=== DEBUG: Initial variable parameter values ===")
problem.update_variable_params(t=0.0)
for i, param in enumerate(problem._variable_parameters):
    if param.name in ['P_ref', 'Q_ref', 'Kdp', 'Kdq']:
        print(f"  {param.name} = {problem._variable_parameters_values[i]:.6f}")

# Check values at event time
print(f"\n=== DEBUG: Variable parameter values at t={event_time}s ===")
problem.update_variable_params(t=event_time)
for i, param in enumerate(problem._variable_parameters):
    if param.name in ['P_ref', 'Q_ref']:
        print(f"  {param.name} = {problem._variable_parameters_values[i]:.6f}")

t, y, well_initialized, converged = solver.simulate()

# === DEBUG: Check event effect ===
print("\n=== DEBUG: Event Verification ===")
print(f"Simulation completed: converged={converged}, well_initialized={well_initialized}")
print(f"Final time: {t[-1]:.3f}s")

# Check if we passed the event time
if t[-1] > event_time:
    print(f"Event at t={event_time}s should have triggered")
    
    # Find indices around event time
    idx_before = np.where(t < event_time)[0]
    idx_after = np.where(t > event_time)[0]
    
    if len(idx_before) > 0 and len(idx_after) > 0:
        idx_event = idx_before[-1]  # Last point before event
        print(f"Data points: {len(idx_before)} before, {len(idx_after)} after event")
        print(f"Time around event: t={t[idx_event]:.3f}s (before), t={t[idx_after[0]]:.3f}s (after)")
else:
    print(f"Warning: Simulation ended at t={t[-1]:.3f}s before event at t={event_time}s")

# === DEBUG: Check values around event ===
print("\n=== DEBUG: Checking values around event ===")

# Droop control variables
omega = find_name_in_block("omega", vsc_mdl)
theta = find_name_in_block("theta", vsc_mdl)
P = find_name_in_block("P", vsc_mdl)
P_lowpass = find_name_in_block("y_P_loop", vsc_mdl)  # Low-pass filter output

omega_idx = problem.get_var_idx(omega)
theta_idx = problem.get_var_idx(theta)
P_idx = problem.get_var_idx(P)
P_lowpass_idx = problem.get_var_idx(P_lowpass)

if t[-1] > event_time:
    idx_before = np.where(t < event_time)[0]
    idx_after = np.where(t > event_time)[0]
    
    if len(idx_before) > 0 and len(idx_after) > 0:
        idx_event = idx_before[-1]
        idx_later = idx_after[50] if len(idx_after) > 50 else idx_after[-1]
        
        print(f"Values BEFORE event (t={t[idx_event]:.3f}s):")
        print(f"  theta = {y[idx_event, theta_idx]:.6f} rad")
        print(f"  omega = {y[idx_event, omega_idx]:.6f} pu")
        print(f"  P = {y[idx_event, P_idx]:.6f} pu")
        print(f"  P_lowpass = {y[idx_event, P_lowpass_idx]:.6f} pu")
        
        print(f"Values AFTER event (t={t[idx_later]:.3f}s):")
        print(f"  theta = {y[idx_later, theta_idx]:.6f} rad")
        print(f"  omega = {y[idx_later, omega_idx]:.6f} pu")
        print(f"  P = {y[idx_later, P_idx]:.6f} pu")
        print(f"  P_lowpass = {y[idx_later, P_lowpass_idx]:.6f} pu")
        
        delta_theta = y[idx_later, theta_idx] - y[idx_event, theta_idx]
        delta_omega = y[idx_later, omega_idx] - y[idx_event, omega_idx]
        delta_P = y[idx_later, P_idx] - y[idx_event, P_idx]
        delta_P_lowpass = y[idx_later, P_lowpass_idx] - y[idx_event, P_lowpass_idx]
        print(f"Changes:")
        print(f"  delta_theta = {delta_theta:.6f} rad ({delta_theta * 180 / 3.14159:.2f} deg)")
        print(f"  delta_omega = {delta_omega:.6f} pu")
        print(f"  delta_P = {delta_P:.6f} pu")
        print(f"  delta_P_lowpass = {delta_P_lowpass:.6f} pu")
        
        # Check droop equation residual
        Kdp = 0.02  # From event_dict
        omega_ref = 1.0
        droop_error_before = y[idx_event, omega_idx] - (omega_ref - Kdp * (y[idx_event, P_lowpass_idx] - 0.01))  # Initial P_ref was 0.01
        droop_error_after = y[idx_later, omega_idx] - (omega_ref - Kdp * (y[idx_later, P_lowpass_idx] - (-0.214)))  # New P_ref is -0.214
        print(f"\nDroop equation check (omega = omega_ref - Kdp*(P_lowpass - P_ref)):")
        print(f"  BEFORE: omega_calc = {omega_ref - Kdp * (y[idx_event, P_lowpass_idx] - 0.01):.6f}, omega_actual = {y[idx_event, omega_idx]:.6f}, error = {droop_error_before:.6f}")
        print(f"  AFTER:  omega_calc = {omega_ref - Kdp * (y[idx_later, P_lowpass_idx] - (-0.214)):.6f}, omega_actual = {y[idx_later, omega_idx]:.6f}, error = {droop_error_after:.6f}")

# === DEBUG: Find VSC internal variables ===
print("\n=== DEBUG: Finding VSC internal variables ===")

# Power variables
Q = find_name_in_block("Q", vsc_mdl)
Q = find_name_in_block("Q", vsc_mdl)

# Converter currents
id_c = find_name_in_block("id_c", vsc_mdl)
iq_c = find_name_in_block("iq_c", vsc_mdl)

# Current references
id_c_ref = find_name_in_block("id_c_ref", vsc_mdl)
iq_c_ref = find_name_in_block("iq_c_ref", vsc_mdl)

# Converter voltages
vd_c = find_name_in_block("vd_c", vsc_mdl)
vq_c = find_name_in_block("vq_c", vsc_mdl)

# Voltage references
vd_c_ref = find_name_in_block("vd_c_ref", vsc_mdl)
vq_c_ref = find_name_in_block("vq_c_ref", vsc_mdl)

# Filter voltages
vd_f = find_name_in_block("vd_f", vsc_mdl)
vq_f = find_name_in_block("vq_f", vsc_mdl)

# Grid currents
id_g = find_name_in_block("id_g", vsc_mdl)
iq_g = find_name_in_block("iq_g", vsc_mdl)

# Debug: Print variable indices
print(f"omega idx: {problem.get_var_idx(omega)}")
print(f"id_c idx: {problem.get_var_idx(id_c)}, iq_c idx: {problem.get_var_idx(iq_c)}")
print(f"id_c_ref idx: {problem.get_var_idx(id_c_ref)}, iq_c_ref idx: {problem.get_var_idx(iq_c_ref)}")
print(f"vd_c idx: {problem.get_var_idx(vd_c)}, vq_c idx: {problem.get_var_idx(vq_c)}")
print(f"P idx: {problem.get_var_idx(P)}, Q idx: {problem.get_var_idx(Q)}")

# === PLOTTING: VSC Internal Variables ===
plt.figure(figsize=(12, 10))

# Plot 1: Droop control (omega)
plt.subplot(4, 1, 1)
plt.plot(t, y[:, problem.get_var_idx(omega)], 'b-', label="omega (pu)", linewidth=2)
plt.ylabel("Frequency (pu)")
plt.legend(loc='upper left')
plt.grid(True)
plt.title('GFM VSC Internal Variables')

# Plot 2: Converter currents vs references
plt.subplot(4, 1, 2)
plt.plot(t, y[:, problem.get_var_idx(id_c)], 'b-', label="id_c (actual)", linewidth=2)
plt.plot(t, y[:, problem.get_var_idx(id_c_ref)], 'b--', label="id_c_ref", linewidth=1.5)
plt.plot(t, y[:, problem.get_var_idx(iq_c)], 'r-', label="iq_c (actual)", linewidth=2)
plt.plot(t, y[:, problem.get_var_idx(iq_c_ref)], 'r--', label="iq_c_ref", linewidth=1.5)
plt.ylabel("Current (pu)")
plt.legend()
plt.grid(True)

# Plot 3: Converter voltages (vd_c, vq_c) and filter voltages
plt.subplot(4, 1, 3)
plt.plot(t, y[:, problem.get_var_idx(vd_c)], 'b-', label="vd_c (converter)", linewidth=2)
plt.plot(t, y[:, problem.get_var_idx(vq_c)], 'r-', label="vq_c (converter)", linewidth=2)
plt.plot(t, y[:, problem.get_var_idx(vd_f)], 'b--', label="vd_f (filter)", linewidth=1.5, alpha=0.7)
plt.plot(t, y[:, problem.get_var_idx(vq_f)], 'r--', label="vq_f (filter)", linewidth=1.5, alpha=0.7)
plt.ylabel("Voltage (pu)")
plt.legend()
plt.grid(True)

# Plot 4: Terminal power
plt.subplot(4, 1, 4)
plt.plot(t, y[:, problem.get_var_idx(P)], 'b-', label="P (terminal)", linewidth=2)
plt.plot(t, y[:, problem.get_var_idx(Q)], 'r-', label="Q (terminal)", linewidth=2)
plt.ylabel("Power (pu)")
plt.xlabel("Time (s)")
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.show()  

# Verify simulation completed
print('\n=== SIMULATION COMPLETED SUCCESSFULLY ===')
print(f'Final time: {t[-1]:.3f}s')
print(f'Final omega: {y[-1, problem.get_var_idx(omega)]:.6f} pu')
print(f'Final P: {y[-1, problem.get_var_idx(P)]:.6f} pu')
print(f'Final Q: {y[-1, problem.get_var_idx(Q)]:.6f} pu')
print(f'Final id_c: {y[-1, problem.get_var_idx(id_c)]:.6f} pu')
print(f'Final iq_c: {y[-1, problem.get_var_idx(iq_c)]:.6f} pu')
