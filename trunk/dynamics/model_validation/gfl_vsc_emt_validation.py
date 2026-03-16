# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import cProfile
import numpy as np
from matplotlib import pyplot as plt

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.vsc_gfl_emt import VscGflEmtBuild
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Rms.vsc_template import PVCellBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCVoltageSource
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions

from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, EmtInitializationMethod
from VeraGridEngine.Devices.Aggregation import RmsEvent
from VeraGridEngine.enumerations import ConverterControlType
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

profiler = cProfile.Profile()
profiler.enable()


def find_name_in_block(name: str, block: Block):
    """Recursively find a variable by name in the block and all its children."""
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

    return None


# Grid instantiation
grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Define buses
bus1 = gce.Bus(name='B1', Vnom=135, is_slack=True)
bus2 = gce.Bus(name='B2', Vnom=135)
bus3 = gce.Bus(name='B3', Vnom=100, is_dc=True)

grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_bus(bus3)

# Initialize EMT models for buses
for bus in grid.buses:
    get_bus_emt_template(grid, bus, vf=grid.rms_var_factory)

# Define AC lines
line12 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)

# Select control modes for the VSC
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
gen3 = gce.Load(name='Load1', P=-1.0, Q=-0.1)
grid.add_load(bus=bus3, api_obj=gen3)

###############
# Add to the grid
grid.add_line(line12)
grid.add_vsc(vsc1)
grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_load(bus=bus2, api_obj=load1)

#########
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

######################################################################################################
# Build EMT models
######################################################################################################



#Initialise the EMT
line12_mdl = get_pi_line_emt_template(grid.rms_var_factory).block
load_type = 'zip'
if load_type == 'zip':
    load_mdl = ZIPLoadEmtBuild(grid.rms_var_factory, Pl0=-0.1, Ql0=-0.01).block
else:
    raise ValueError(f"Unknown load type: {load_type}")
    
genrow_mdl1 = get_simple_generator_emt_template(grid.rms_var_factory).block

# Build VSC EMT model with the same control modes used in the VSC device
vsc_mdl = VscGflEmtBuild(grid.rms_var_factory, control1=CONTROL1_MODE, control2=CONTROL2_MODE).block

pv_cell_block = PVCellBuild(grid.rms_var_factory).block
dc_source = DCVoltageSource(grid.rms_var_factory, bus3.emt_model.out_vars[0]).block

# Connect generator to bus1 (three-phase voltages)
genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.emt_model.out_vars[0]])  # v_A
genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.emt_model.out_vars[1]])  # v_B
genrow_mdl1.connect([genrow_mdl1.in_vars[2]], [bus1.emt_model.out_vars[2]])  # v_C

# Connect load to bus2 (three-phase voltages)
load_mdl.connect([load_mdl.in_vars[0]], [bus2.emt_model.out_vars[0]])  # v_A
load_mdl.connect([load_mdl.in_vars[1]], [bus2.emt_model.out_vars[1]])  # v_B
load_mdl.connect([load_mdl.in_vars[2]], [bus2.emt_model.out_vars[2]])  # v_C

# Connect line12 between bus1 and bus2 (three-phase voltages)
line12_mdl.connect([line12_mdl.in_vars[0]], [bus1.emt_model.out_vars[0]])  # v_A from
line12_mdl.connect([line12_mdl.in_vars[1]], [bus1.emt_model.out_vars[1]])  # v_B from
line12_mdl.connect([line12_mdl.in_vars[2]], [bus1.emt_model.out_vars[2]])  # v_C from

line12_mdl.connect([line12_mdl.in_vars[3]], [bus2.emt_model.out_vars[0]])  # v_A to
line12_mdl.connect([line12_mdl.in_vars[4]], [bus2.emt_model.out_vars[1]])  # v_B to
line12_mdl.connect([line12_mdl.in_vars[5]], [bus2.emt_model.out_vars[2]])  # v_C to

# Updated connections for new VSC EMT model with 4 inputs: [Va, Vb, Vc, Vdc]
vsc_mdl.connect([vsc_mdl.in_vars[0]], [bus2.emt_model.out_vars[0]])  # Va
vsc_mdl.connect([vsc_mdl.in_vars[1]], [bus2.emt_model.out_vars[1]])  # Vb
vsc_mdl.connect([vsc_mdl.in_vars[2]], [bus2.emt_model.out_vars[2]])  # Vc
vsc_mdl.connect([vsc_mdl.in_vars[3]], [bus3.emt_model.out_vars[0]])  # Vdc

# external mapping
big_gen1 = Block(children=[genrow_mdl1])
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl1.out_vars[0]})
big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl1.out_vars[1]})

# attach emt models to Veragrid objects
line12.emt_model = line12_mdl
load1.emt_model = load_mdl
gen1.emt_model = big_gen1
gen3.emt_model = dc_source
gen3.emt_model.unify_blocks()

Vpv0 = find_name_in_block('Vpv0', gen3.emt_model)

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

options = EmtOptions(time_step=0.0001,  # EMT requires smaller time step
                     simulation_time=0.3,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.BackEuler,
                     initialization_method=EmtInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=1000,
                     verbose=0)

problem = EmtProblemDae(grid=grid,
                        options=options,
                        pf_results=res)

solver = BackEulerImplicitIntegrationEmt(
    problem=problem,
    t0=0,
    t_end=options.simulation_time,
    h=options.time_step,
    max_iter=options.max_iter
)

t, y, well_initialized, converged = solver.simulate()

profiler.disable()
profiler.dump_stats("profiling_stats_emt.prof")

xlim = options.simulation_time

# Find variables for plotting
v_A_bus1 = find_name_in_block("v_A", bus1.emt_model)
v_B_bus1 = find_name_in_block("v_B", bus1.emt_model)
v_C_bus1 = find_name_in_block("v_C", bus1.emt_model)

v_A_bus2 = find_name_in_block("v_A", bus2.emt_model)
v_B_bus2 = find_name_in_block("v_B", bus2.emt_model)
v_C_bus2 = find_name_in_block("v_C", bus2.emt_model)

i_A_vsc = find_name_in_block("i_a", vsc_mdl)
i_B_vsc = find_name_in_block("i_b", vsc_mdl)
i_C_vsc = find_name_in_block("i_c", vsc_mdl)

P = find_name_in_block('P', vsc_mdl)
Q = find_name_in_block('Q', vsc_mdl)
Vdc = find_name_in_block('Vdc', bus3.emt_model)

# Plot 1: Bus 1 Three-phase voltages
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(v_A_bus1)], label="v_A (pu)", color='r')
plt.plot(t, y[:, problem.get_var_idx(v_B_bus1)], label="v_B (pu)", color='g')
plt.plot(t, y[:, problem.get_var_idx(v_C_bus1)], label="v_C (pu)", color='b')
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Voltage (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'Bus 1 Voltages (EMT): {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
plt.show()

# Plot 2: Bus 2 Three-phase voltages
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(v_A_bus2)], label="v_A (pu)", color='r')
plt.plot(t, y[:, problem.get_var_idx(v_B_bus2)], label="v_B (pu)", color='g')
plt.plot(t, y[:, problem.get_var_idx(v_C_bus2)], label="v_C (pu)", color='b')
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Voltage (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'Bus 2 Voltages (EMT): {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
plt.show()

# Plot 3: VSC Three-phase currents
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(i_A_vsc)], label="i_A (pu)", color='r')
plt.plot(t, y[:, problem.get_var_idx(i_B_vsc)], label="i_B (pu)", color='g')
plt.plot(t, y[:, problem.get_var_idx(i_C_vsc)], label="i_C (pu)", color='b')
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Current (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC GFL Currents (EMT): {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
plt.show()

# Plot 4: VSC P and Q
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(P)], label="P (pu)", color='r')
plt.plot(t, y[:, problem.get_var_idx(Q)], label="Q (pu)", color='b')
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Power (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC GFL Power (EMT): {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
plt.show()

# Plot 5: DC Voltage
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, problem.get_var_idx(Vdc)], label="Vdc (pu)", color='b')
plt.legend(loc='upper right')
plt.xlabel("Time (s)")
plt.ylabel("Voltage (pu)")
plt.xlim([0, xlim])
plt.grid(True)
plt.tight_layout()
plt.title(f'VSC DC Voltage (EMT): {CONTROL1_MODE.value} + {CONTROL2_MODE.value}')
plt.show()

print(f"\nEMT Simulation completed with control modes: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}")
print("Supported combinations:")
print("  - Pac + Qac: Active and reactive power control")
print("  - Pac + Vm_ac: Active power and AC voltage control")
print("  - Pdc + Qac: DC power and reactive power control")
print("  - Pdc + Vm_ac: DC power and AC voltage control")
print("  - Vm_dc + Qac: DC voltage and reactive power control")
print("  - Vm_dc + Vm_ac: DC voltage and AC voltage control")
