# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import cProfile as profile
import numpy as np
from matplotlib import pyplot as plt

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.vsc_template import PVCellBuild
from VeraGridEngine.Templates.Rms.vsc_gfl import VscGflBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCVoltageSource
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
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
    initialize_bus_rms(bus, vf=grid.var_factory)

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
line12_mdl = get_line_rms_template(grid.var_factory).block
load_type = 'zip'
if load_type == 'zip':
    load_mdl = ZIPLoadBuild(grid.var_factory, Pl0 =-0.1, Ql0 =-0.01).block
else:
    raise ValueError(f"Unknown load type: {load_type}")
    
genrow_mdl1 = get_genrow1_rms_template(grid.var_factory).block
genrow_mdl1 = get_complete_generator_template_rms(grid.var_factory).block

# Build VSC model with the same control modes used in the VSC device
vsc_mdl = VscGflBuild(grid.var_factory, control1=CONTROL1_MODE, control2=CONTROL2_MODE).block

pv_cell_block  =  PVCellBuild(grid.var_factory).block
dc_source = DCVoltageSource(grid.var_factory, bus3.rms_model.out_vars[0]).block

genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.rms_model.out_vars[0]])
genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.rms_model.out_vars[1]])

load_mdl.connect([load_mdl.in_vars[0]], [bus2.rms_model.out_vars[0]])

line12_mdl.connect([line12_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])

line12_mdl.connect([line12_mdl.in_vars[2]], [bus2.rms_model.out_vars[0]])
line12_mdl.connect([line12_mdl.in_vars[3]], [bus2.rms_model.out_vars[1]]) 

# Updated connections for new VSC model with 3 inputs: [Vm, Va, Vdc]
print("\nDEBUG: Before connect:")
print(f"  VSC in_vars[0] (Vm): {vsc_mdl.in_vars[0].name} (uid={vsc_mdl.in_vars[0].uid})")
print(f"  Bus2 out_vars[0]: {bus2.rms_model.out_vars[0].name} (uid={bus2.rms_model.out_vars[0].uid})")

vsc_mdl.connect([vsc_mdl.in_vars[0]], [bus2.rms_model.out_vars[0]])  # Vm
vsc_mdl.connect([vsc_mdl.in_vars[1]], [bus2.rms_model.out_vars[1]])  # Va
vsc_mdl.connect([vsc_mdl.in_vars[2]], [bus3.rms_model.out_vars[0]])  # Vdc

print("\nDEBUG: After connect:")
print(f"  VSC in_vars[0] (Vm): {vsc_mdl.in_vars[0].name} (uid={vsc_mdl.in_vars[0].uid})")

#vsc_mdl.connect([vsc_mdl.in_vars[3]], [bus3.rms_model.out_vars[1]]) 
#pv_cell_block.connect([pv_cell_block.in_vars[0]], [bus3.rms_model.out_vars[0]])

# external mapping
big_gen1 = Block(children=[genrow_mdl1])
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl1.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl1.out_vars[1]})

# attach rms models to Veragrid objects
line12.rms_model = line12_mdl
load1.rms_model = load_mdl
gen1.rms_model = big_gen1
gen3.rms_model = dc_source
gen3.rms_model.unify_blocks()
vsc1.rms_model = vsc_mdl

# Check init_eqs BEFORE unify_blocks
print("\nDEBUG: Before unify_blocks - checking child blocks init_eqs:")
for i, child in enumerate(vsc_mdl.children):
    print(f"  Child {i}: {len(child.init_eqs)} init_eqs")
    for var, expr in list(child.init_eqs.items())[:3]:  # Show first 3
        print(f"    {var.name} = {expr}")

vsc1.rms_model.unify_blocks()  # Merge init_eqs from child blocks

# Debug: Check the external mapping of the VSC model
print("\nDEBUG: VSC Model External Mapping:")
for ref_type, var in vsc1.rms_model.external_mapping.items():
    print(f"  {ref_type.value}: {var.name} (uid={var.uid})")

print("\nDEBUG: VSC Model init_eqs:")
for var, expr in vsc1.rms_model.init_eqs.items():
    expr_vars = []
    if hasattr(expr, 'free_symbols'):
        expr_vars = [str(s) for s in expr.free_symbols]
    elif hasattr(expr, 'name'):
        expr_vars = [expr.name]
    print(f"  {var.name} (uid={var.uid}) = {expr} [vars: {expr_vars}]")

# Set initial value for Vpv0 in the DC source to avoid None values
# Get the DC voltage from bus3 power flow results
Vdc_bus3 = abs(res.voltage[2])  # Bus 3 is the DC bus
Vpv0_var = find_name_in_block('Vpv0', gen3.rms_model)
# Set the value in the event_dict (where Vpv0 is stored as a parameter)
from VeraGridEngine.Utils.Symbolic.symbolic import Const
gen3.rms_model.event_dict[Vpv0_var] = Const(Vdc_bus3 + 0.001)  # Slightly higher than Vdc

Vpv0 = find_name_in_block('Vpv0', gen3.rms_model)

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

events_group = RmsEventsGroup("simulation1")
event1 = RmsEvent(device=gen3, parameter=Vpv0, time=.2, value=0.3, group=events_group)
event2 = RmsEvent(device=vsc1, parameter=ref_var, time=.2, value=0.1, group=events_group)
grid.add_rms_event(event1)
grid.add_rms_event(event2)

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

problem.set_events_group(events_group)

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
delta = find_name_in_block("deltagenqec", big_gen1)

plt.figure(figsize=(10, 6))
if delta is not None:
    plt.plot(t, y[:, problem.get_var_idx(delta)], label="delta (pu)")
plt.plot(t, y[:, problem.get_var_idx(Pg)], label="P (pu)")
plt.plot(t, y[:, problem.get_var_idx(Qg)], label="Q (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC GFL Control: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
# plt.show()  # Disabled to prevent hanging

pv_all = gen3.rms_model 
vdc = find_name_in_block('Vdc', bus3.rms_model)
v_d = find_name_in_block('vd', vsc_mdl)
v_q = find_name_in_block('vq', vsc_mdl)
v_d_c = find_name_in_block('v_d_c', vsc_mdl)
v_q_c = find_name_in_block('v_q_c', vsc_mdl)
P = find_name_in_block('P', vsc_mdl)
Q = find_name_in_block('Q', vsc_mdl)
i_d = find_name_in_block('i_d', vsc_mdl)
i_q = find_name_in_block('i_q', vsc_mdl)
Idc = find_name_in_block('Idc', gen3.rms_model)
Vdc = find_name_in_block('Vdc', bus3.rms_model)
Pdc = find_name_in_block('Pdc', dc_source)

plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(Vdc)], label="vdc (pu)")
plt.plot(t, y[:, problem.get_var_idx(Pdc)], label="Pdc (pu)")
#plt.plot(t, y[:, problem.get_var_idx(v_d_c)], label="vd converter (pu)")
#plt.plot(t, y[:, problem.get_var_idx(v_q_c)], label="vq converter (pu)")
#plt.plot(t, y[:, problem.get_var_idx(v_d)], label="vd grid (pu)")
#plt.plot(t, y[:, problem.get_var_idx(v_q)], label="vq grid (pu)")
#plt.plot(t, y[:, problem.get_var_idx(P)], label="P (pu)")
plt.plot(t, y[:, problem.get_var_idx(Q)], label="Q (pu)")
plt.plot(t, y[:, problem.get_var_idx(Idc)], label="Idc (pu)")
#plt.plot(t, y[:, problem.get_var_idx(i_d)], label="id (pu)")
#plt.plot(t, y[:, problem.get_var_idx(i_q)], label="iq (pu)")
#plt.plot(t, y[:, problem.get_var_idx(Vm)], label="Vm (pu)")
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC DC Side: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
plt.show()  # Disabled to prevent hanging

print(f"\nSimulation completed with control modes: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}")
print("Supported combinations:")
print("  - Pac + Qac: Active and reactive power control")
print("  - Pac + Vm_ac: Active power and AC voltage control")
print("  - Pdc + Qac: DC power and reactive power control")
print("  - Pdc + Vm_ac: DC power and AC voltage control")
print("  - Vm_dc + Qac: DC voltage and reactive power control")
print("  - Vm_dc + Vm_ac: DC voltage and AC voltage control")
