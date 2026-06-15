# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import cProfile
import os
import sys
import matplotlib
import numpy as np
import numpy as np

matplotlib.use("Agg")

from matplotlib import pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.vsc_gfl_emt import VscGflEmtBuild
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_dc_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model

from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
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
        if name == var.name or var.name.startswith(f"{name}_"):
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

    return None


PLOT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "gfl_vsc_emt_validation_plots")


def save_and_show_or_close_plot(filename: str):
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, filename), dpi=150)
    if matplotlib.get_backend().lower() == "agg":
        plt.close()
    else:
        plt.show()


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
    get_bus_emt_template(grid, bus)

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
gen1 = gce.Generator(name='Gen1', P=5.0, vset=1.00, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=1.7)

# Define loads
load1 = gce.Load(name='Load1', P=10, Q=1.0)

# DC source feeding the VSC DC bus.
gen3 = gce.Generator(name='DC Source', P=1.0, vset=1.03)
grid.add_generator(bus=bus3, api_obj=gen3)

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
line12_mdl = get_pi_line_emt_template(vf=grid.var_factory).block
load_type = 'zip'
if load_type == 'zip':
    load_mdl = get_load_ZIP_emt_template(grid.var_factory).block
else:
    raise ValueError(f"Unknown load type: {load_type}")
    
genrow_mdl1 = get_generator_thevenin_rl_emt_template_with_ref(grid.var_factory).block

# Build VSC EMT model with the same control modes used in the VSC device
vsc_mdl = VscGflEmtBuild(grid.var_factory, control1=CONTROL1_MODE, control2=CONTROL2_MODE).block

dc_source = get_dc_voltage_source_emt_template(
    vf=grid.var_factory,
    source_voltage_value=1.03,
    name="dc_voltage_source",
).block

# Attach EMT models and let the current helper create bus/device connections.
set_emt_model(device=line12, model=line12_mdl, var_factory=grid.var_factory)
set_emt_model(device=load1, model=load_mdl, var_factory=grid.var_factory)
set_emt_model(device=gen1, model=genrow_mdl1, var_factory=grid.var_factory)
set_emt_model(device=gen3, model=dc_source, var_factory=grid.var_factory)
set_emt_model(device=vsc1, model=vsc_mdl, var_factory=grid.var_factory)

V_src = find_name_in_block('V_src_dc_voltage_source', gen3.emt_model)

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

event1 = EmtEvent(device=gen3, parameter=V_src, time=.2, value=0.3)
event2 = EmtEvent(device=vsc1, parameter=ref_var, time=.2, value=0.1)
event3 = EmtEvent(device=vsc1, parameter=ref_var, time=.25, value=1.03)
grid.add_emt_event(event1)
grid.add_emt_event(event2)
grid.add_emt_event(event3)

options = EmtOptions(time_step=0.0001,  # EMT requires smaller time step
                     simulation_time=0.3,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     initialization_method=EmtInitializationMethod.Explicit,
                     verbose=0)
print(f"EMT initialization method: {options.initialization_method!r}")

problem = EmtProblemDae(grid=grid,
                        options=options,
                        pf_results=res)


def seed_gfl_vsc_initial_guess(problem, vsc, pf_results):
    bus_names = [bus.name for bus in grid.buses]

    def value_of(var):
        return problem.get_x0()[problem.get_var_idx(var)]

    v_a_var = find_name_in_block('v_A', vsc.bus_to.emt_model)
    v_b_var = find_name_in_block('v_B', vsc.bus_to.emt_model)
    v_c_var = find_name_in_block('v_C', vsc.bus_to.emt_model)
    va0 = value_of(v_a_var)
    vb0 = value_of(v_b_var)
    vc0 = value_of(v_c_var)

    best_theta = 0.0
    best_abs_d = None
    best_q = 1.0
    for theta_candidate in np.linspace(-np.pi, np.pi, 40001):
        vd_candidate = (1.0 / 3.0) * (
            2.0 * np.cos(theta_candidate) * va0
            + (-np.cos(theta_candidate) - np.sqrt(3.0) * np.sin(theta_candidate)) * vb0
            + (-np.cos(theta_candidate) + np.sqrt(3.0) * np.sin(theta_candidate)) * vc0
        )
        vq_candidate = (1.0 / 3.0) * (
            2.0 * np.sin(theta_candidate) * va0
            + (-np.sin(theta_candidate) + np.sqrt(3.0) * np.cos(theta_candidate)) * vb0
            + (-np.sin(theta_candidate) - np.sqrt(3.0) * np.cos(theta_candidate)) * vc0
        )
        if vq_candidate > 0.0 and (best_abs_d is None or abs(vd_candidate) < best_abs_d):
            best_abs_d = abs(vd_candidate)
            best_theta = theta_candidate
            best_q = vq_candidate

    vpk = float(best_q)

    p0 = -float(np.real(pf_results.St_vsc[0]) / grid.Sbase)
    q0 = -float(np.imag(pf_results.St_vsc[0]) / grid.Sbase)
    theta0 = float(best_theta)
    vd0 = 0.0
    vq0 = vpk
    iq0 = (2.0 / 3.0) * p0 / vq0
    id0 = (2.0 / 3.0) * q0 / vq0

    r0 = 0.1
    l0 = 0.1
    omega0 = 1.0
    vd_c0 = vd0 + (r0 * id0 - omega0 * l0 * iq0)
    vq_c0 = vq0 + (r0 * iq0 - omega0 * l0 * id0)
    vd_hat0 = vd_c0 - (vd0 + l0 * omega0 * iq0)
    vq_hat0 = vq_c0 - (vq0 - l0 * omega0 * id0)

    values = {
        'P': p0,
        'Q': q0,
        'Pt_vsc': -p0,
        'Qt_vsc': -q0,
        'theta': theta0,
        'omega': omega0,
        'vg_d': vd0,
        'vg_q': vq0,
        'i_d': id0,
        'i_q': iq0,
        'i_d_ref': id0,
        'i_q_ref': iq0,
        'v_d_c': vd_c0,
        'v_q_c': vq_c0,
        'y_vd_hat': vd_hat0,
        'y_vq_hat': vq_hat0,
        'Vdc_ref': float(abs(pf_results.voltage[bus_names.index(vsc.bus_from.name)])),
        'Vm_ac_ref': vq0,
        'u_Vdc_ctrl': 0.0,
        'u_Vac_ctrl': 0.0,
        'u_vd_hat': 0.0,
        'u_vq_hat': 0.0,
    }
    for name, value in values.items():
        var = find_name_in_block(name, vsc.emt_model)
        if var is not None:
            problem.init_guess[var.uid] = float(value)


seed_gfl_vsc_initial_guess(problem, vsc1, res)

solver = build_emt_solver(
    options=options,
    problem=problem,
    t0=0.0,
    t_end=options.simulation_time,
    h=options.time_step,
    method=options.integration_method,
)

t, y, dy, well_initialized, converged = solver.simulate()

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
Vdc = bus3.emt_model.out_vars[0]
theta_vsc = find_name_in_block('theta', vsc_mdl)
omega_vsc = find_name_in_block('omega', vsc_mdl)
v_d_g = find_name_in_block('vg_d', vsc_mdl)
v_q_g = find_name_in_block('vg_q', vsc_mdl)

pre_event = t < 0.19
if np.any(pre_event):
    for label, var in [("Vdc", Vdc), ("P", P), ("Q", Q), ("theta", theta_vsc), ("omega", omega_vsc), ("v_d_g", v_d_g), ("v_q_g", v_q_g)]:
        trace = y[pre_event, problem.get_var_idx(var)]
        print(f"Pre-event max |Delta {label}|: {np.max(np.abs(trace - trace[0])):.6e}")
        print(f"  {label}: t0={trace[0]:.6e}, min={np.min(trace):.6e}, max={np.max(trace):.6e}")

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
save_and_show_or_close_plot("bus1_voltages.png")

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
save_and_show_or_close_plot("bus2_voltages.png")

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
save_and_show_or_close_plot("vsc_currents.png")

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
save_and_show_or_close_plot("vsc_power.png")

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
save_and_show_or_close_plot("dc_voltage.png")

print(f"\nEMT Simulation completed with control modes: {CONTROL1_MODE.value} + {CONTROL2_MODE.value}")
print("Supported combinations:")
print("  - Pac + Qac: Active and reactive power control")
print("  - Pac + Vm_ac: Active power and AC voltage control")
print("  - Pdc + Qac: DC power and reactive power control")
print("  - Pdc + Vm_ac: DC power and AC voltage control")
print("  - Vm_dc + Qac: DC voltage and reactive power control")
print("  - Vm_dc + Vm_ac: DC voltage and AC voltage control")
