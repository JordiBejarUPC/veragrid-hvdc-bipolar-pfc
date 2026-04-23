# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys
from typing import Any

import numpy as np
import matplotlib.pyplot as plt

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import (
    get_generator_thevenin_rl_emt_template,
)
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.enumerations import ShuntConnectionType

from VeraGridEngine.Templates.Emt.xfmr_emt_template import get_xfmr_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.enumerations import BranchImpedanceMode, SolverType

from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    WindingType,
)
from VeraGridEngine.Utils.Symbolic.block import Block


def find_name_in_block(name: str, block: Block):
    """
    Find a variable by exact name inside one EMT block and its children.

    :param name: Variable name.
    :type name: str
    :param block: Block to search.
    :type block: Block
    :return: Variable object or None.
    :rtype: Any
    """
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

    return None


def get_series(problem: EmtProblemDae, y_values: np.ndarray, var_or_name: Any) -> np.ndarray | None:
    """
    Extract one variable trajectory from the solver output using the init guess table.

    :param problem: EMT problem.
    :type problem: EmtProblemDae
    :param y_values: State/algebraic trajectory matrix.
    :type y_values: np.ndarray
    :param var_or_name: Variable object or variable name.
    :type var_or_name: Any
    :return: Time series if found, else None.
    :rtype: np.ndarray | None
    """
    if var_or_name is None:
        return None

    name = var_or_name.name if hasattr(var_or_name, "name") else str(var_or_name)

    df = problem.get_init_guess_table()
    rows = df[(df["name"] == name) & (df["type"] == "Var")]
    if len(rows) == 0:
        return None

    idx = int(rows.iloc[0]["idx"])
    return y_values[:, idx]


def print_window_metrics(
    label: str,
    time_values: np.ndarray,
    values: np.ndarray | None,
    t0: float,
    t1: float,
) -> None:
    """
    Print simple metrics in a time window.

    :param label: Signal label.
    :type label: str
    :param time_values: Time vector.
    :type time_values: np.ndarray
    :param values: Signal values.
    :type values: np.ndarray | None
    :param t0: Window start.
    :type t0: float
    :param t1: Window end.
    :type t1: float
    :return: None.
    :rtype: None
    """
    if values is None:
        print(f"{label:<32} not found")
        return

    mask = (time_values >= t0) & (time_values <= t1)
    if not np.any(mask):
        print(f"{label:<32} empty window")
        return

    data = values[mask]
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data ** 2)))
    mean = float(np.mean(data))
    print(f"{label:<32} peak={peak:>11.6f}  rms={rms:>11.6f}  mean={mean:>11.6f}")


def plot_if_present(
    time_values: np.ndarray,
    series_list: list[tuple[np.ndarray | None, str]],
    title: str,
    ylabel: str,
    event_time: float,
) -> None:
    """
    Plot all available series.

    :param time_values: Time vector.
    :type time_values: np.ndarray
    :param series_list: List of tuples (series, label).
    :type series_list: list[tuple[np.ndarray | None, str]]
    :param title: Plot title.
    :type title: str
    :param ylabel: Y-axis label.
    :type ylabel: str
    :param event_time: Energization instant.
    :type event_time: float
    :return: None.
    :rtype: None
    """
    n_lines = 0
    for series, label in series_list:
        if series is not None:
            plt.plot(time_values, series, label=label)
            n_lines += 1

    plt.axvline(event_time, color="k", linestyle=":", linewidth=1.0, label="Energization event")
    plt.title(title)
    plt.xlabel("Time [s]")
    plt.ylabel(ylabel)
    plt.grid(True)
    if n_lines > 0:
        plt.legend(loc="best")


######################################################################################################
# Build grid
#
# Test to observe transformer inrush / saturation:
# - same nonlinear transformer during the whole simulation
# - secondary in no-load condition
# - no breaker EMT model available
# - thus, the source is "disconnected" by keeping E_scale = 0.0 initially
# - at event_time, E_scale -> 1.0 and the transformer is energized
######################################################################################################

grid = MultiCircuit(Sbase=100.0, fbase=50.0)

bus_hv = Bus(name="Bus_HV", Vnom=20.0, is_slack=True)
bus_lv = Bus(name="Bus_LV", Vnom=0.69)

grid.add_bus(bus_hv)
grid.add_bus(bus_lv)

gen = Generator(name="gen_test", vset=0.000001, Snom=100.0, freq=50.0, r1=0.002, x1=0.25)
grid.add_generator(bus=bus_hv, api_obj=gen)

xfmr = Transformer2W(
    bus_from=bus_hv,
    bus_to=bus_lv,
    name="Transformer",
    HV=20.0,
    LV=0.69,
    nominal_power=100.0,
    copper_losses=120.0,
    iron_losses=35.0,
    no_load_current=0.20,
    short_circuit_voltage=10.0,
    rate=100.0,
    tap_module=1.0,
    tap_phase=0.0,
)

xfmr.conn_f = WindingType.GroundedStar
xfmr.conn_t = WindingType.GroundedStar
xfmr.vector_group_number = 0
xfmr.tap_module = 1.0

grid.add_transformer2w(xfmr)

# Secondary kept almost open-circuit through a very large resistance.
# This is needed so the EMT workflow still has a load model and a PF point.
vnom_lv = 0.69
vph_lv = vnom_lv / np.sqrt(3.0)

R_open_ohm = 1e9
P_ph = (vph_lv ** 2) / R_open_ohm
Q_ph = 0.0

load = Load(
    name="load_open_test",
    P1=P_ph,
    P2=P_ph,
    P3=P_ph,
    Q1=Q_ph,
    Q2=Q_ph,
    Q3=Q_ph,
)
load.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_lv, api_obj=load)


for bus in grid.buses:
    get_bus_emt_template(grid, bus)

######################################################################################################
# EMT models
######################################################################################################

xfmr_mdl = get_xfmr_emt_template(vf=grid.var_factory, name="xfmr_sat_test").block
gen_mdl = get_generator_thevenin_rl_emt_template(vf=grid.var_factory, name="gen_sat_test").block
load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

set_emt_model(device=xfmr, model=xfmr_mdl, var_factory=grid.var_factory)
set_emt_model(device=gen, model=gen_mdl, var_factory=grid.var_factory)
set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

######################################################################################################
# Configure transformer:
# - nonlinear core active from t = 0
# - same Frohlich curve during the whole test
# - same transformer before and after energization
######################################################################################################

xfmr_mdl.set_parameter_in_model(var_name="xfmr_use_linear_core_xfmr_sat_test", new_value=0.0)
xfmr_mdl.set_parameter_in_model(var_name="xfmr_c_term_xfmr_sat_test", new_value=1e-6)

xfmr_mdl.set_parameter_in_model(var_name="xfmr_core_topology_code_xfmr_sat_test", new_value=3.0)
xfmr_mdl.set_parameter_in_model(var_name="xfmr_yoke_area_rel_xfmr_sat_test", new_value=1.0)
xfmr_mdl.set_parameter_in_model(var_name="xfmr_yoke_length_rel_xfmr_sat_test", new_value=1.0)
xfmr_mdl.set_parameter_in_model(var_name="xfmr_outer_leg_area_rel_xfmr_sat_test", new_value=1.0)
xfmr_mdl.set_parameter_in_model(var_name="xfmr_outer_leg_length_rel_xfmr_sat_test", new_value=1.0)

# Fixed Frohlich coefficients of the SAME transformer.
xfmr_mdl.set_parameter_in_model(var_name="xfmr_core_a_prime_xfmr_sat_test", new_value=0.0018)
xfmr_mdl.set_parameter_in_model(var_name="xfmr_core_b_prime_xfmr_sat_test", new_value=0.35)

# resistance start at a super high value.
load_mdl.set_parameter_in_model(var_name="R_A_Shunt_R_3ph", new_value=1e9)
load_mdl.set_parameter_in_model(var_name="R_B_Shunt_R_3ph", new_value=1e9)
load_mdl.set_parameter_in_model(var_name="R_C_Shunt_R_3ph", new_value=1e9)

######################################################################################################
# Configure generator for breaker-less energization
#
# We emulate "open breaker" by setting the internal source scaling to zero.
# Then, at event_time, E_scale is switched to 1.0.
#
# The initial phase is chosen so that closing occurs at approximately a phase-A
# zero-voltage crossing, which is the classical severe point-on-wave for inrush.
######################################################################################################

# Required by the generator EMT template when no PF initialization is used.
# gen_mdl.set_parameter_in_model(var_name="phi_v_gen_sat_test", new_value=0.0)
# gen_mdl.set_parameter_in_model(var_name="phi_gen_sat_test", new_value=0.0)
# gen_mdl.set_parameter_in_model(var_name="Vpk_gen_sat_test", new_value=np.sqrt(2.0))
# gen_mdl.set_parameter_in_model(var_name="Ipk_gen_sat_test", new_value=0.0)

# Start de-energized.
gen_mdl.set_parameter_in_model(var_name="E_scale_gen_sat_test", new_value=1.0)

######################################################################################################
# Energization event
######################################################################################################

# Use a point-on-wave close to zero voltage.
event_time = 0.020005

gen_escale = find_name_in_block("E_scale_gen_sat_test", gen_mdl)
if gen_escale is None:
    raise ValueError(
        "The generator EMT template does not expose E_scale_gen_sat_test. "
        "Add a local event_dict parameter E_scale to the Thevenin EMT generator template "
        "and multiply Epk_expr by E_scale in e_A/e_B/e_C."
    )

events_group = EmtEventsGroup(name="xfmr_inrush_demo")
grid.add_emt_events_group(events_group)

grid.add_emt_event(
    EmtEvent(
        device=gen,
        parameter=gen_escale,
        time=event_time,
        value=1.0 / 0.000001,
        group=events_group,
    )
)

######################################################################################################
# Power Flow
######################################################################################################
pf_options = PowerFlowOptions(
    solver_type=SolverType.NR,
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
    branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
    distributed_slack=False,
    ignore_single_node_islands=False,
    trust_radius=1.0,
    backtracking_parameter=0.05,
    use_stored_guess=False,
    initialize_angles=False,
    generate_report=False,
)

power_flow = PowerFlowDriver3Ph(grid, pf_options)
power_flow.run()
res = power_flow.results

print("\n" + "=" * 70)
print("3Ph POWER FLOW RESULTS")
print("=" * 70)
print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

######################################################################################################
# EMT setup
######################################################################################################

options = EmtOptions(
    time_step=5e-6,
    simulation_time=0.12,
    tolerance=1e-6,
    solver_type=EmtSolverTypes.StructuralCompiled,
    initialization_method=EmtInitializationMethod.Auto,
    integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
    verbose=1,
)

# No power flow is used here on purpose.
# The initial operating point is the de-energized network with E_scale = 0.
problem = EmtProblemDae(
    grid=grid,
    options=options,
    pf_results_3ph=res,
    pf_results=None,
)

solver = StructuralCompiledSolver(
    problem=problem,
    t0=0.0,
    t_end=options.simulation_time,
    h=options.time_step,
    method=options.integration_method,
    pred_method=DynamicIntegrationMethod.OdeEuler,
    dense_threshold=0,
    verbose=True,
    auto_build=False,
)
solver._build_vectorized_backend(options.integration_method)

boundary_updater = problem
t, y, dy, well_initialized, converged = solver.simulate(boundary_updater=boundary_updater)

print(f"well_initialized = {well_initialized}")
print(f"converged = {converged}")

######################################################################################################
# Extract trajectories
######################################################################################################

vA_hv = get_series(problem, y, "v_A_Bus_HV_emt_template")
vB_hv = get_series(problem, y, "v_B_Bus_HV_emt_template")
vC_hv = get_series(problem, y, "v_C_Bus_HV_emt_template")

vA_lv = get_series(problem, y, "v_A_Bus_LV_emt_template")
vB_lv = get_series(problem, y, "v_B_Bus_LV_emt_template")
vC_lv = get_series(problem, y, "v_C_Bus_LV_emt_template")

ifA = get_series(problem, y, "if_A_xfmr_sat_test")
ifB = get_series(problem, y, "if_B_xfmr_sat_test")
ifC = get_series(problem, y, "if_C_xfmr_sat_test")

itA = get_series(problem, y, "it_A_xfmr_sat_test")
itB = get_series(problem, y, "it_B_xfmr_sat_test")
itC = get_series(problem, y, "it_C_xfmr_sat_test")

iA_gen = get_series(problem, y, "i_A_gen_sat_test")
iB_gen = get_series(problem, y, "i_B_gen_sat_test")
iC_gen = get_series(problem, y, "i_C_gen_sat_test")

lam_A = get_series(problem, y, "lam_leg_A_xfmr_sat_test")
lam_B = get_series(problem, y, "lam_leg_B_xfmr_sat_test")
lam_C = get_series(problem, y, "lam_leg_C_xfmr_sat_test")

i_leg_core_A = get_series(problem, y, "i_leg_core_A_xfmr_sat_test")
i_leg_core_B = get_series(problem, y, "i_leg_core_B_xfmr_sat_test")
i_leg_core_C = get_series(problem, y, "i_leg_core_C_xfmr_sat_test")

i_mag_A = get_series(problem, y, "i_mag_A_xfmr_sat_test")
i_mag_B = get_series(problem, y, "i_mag_B_xfmr_sat_test")
i_mag_C = get_series(problem, y, "i_mag_C_xfmr_sat_test")

i_return = get_series(problem, y, "i_return_total_xfmr_sat_test")

lam_sum = None
if lam_A is not None and lam_B is not None and lam_C is not None:
    lam_sum = lam_A + lam_B + lam_C

######################################################################################################
# Prints useful to assess inrush / saturation
######################################################################################################

print("\n" + "=" * 80)
print("TRANSFORMER ENERGIZATION / INRUSH METRICS")
print("=" * 80)
print("Test description:")
print("  - Transformer in no-load condition")
print("  - Same Frohlich curve during the whole simulation")
print("  - Source de-energized initially through E_scale = 0.0")
print(f"  - Energization event at t = {event_time:.6f} s with E_scale -> 1.0")
print("  - Point-on-wave chosen close to phase-A zero crossing")
print("")
print("Useful windows:")
print("  - Pre-event    : [0.000, 0.018] s")
print("  - Inrush early : [0.020, 0.040] s")
print("  - Inrush later : [0.080, 0.115] s")

print("\nPRE-EVENT")
print_window_metrics("HV voltage A", t, vA_hv, 0.000, 0.018)
print_window_metrics("if_A (primary current)", t, ifA, 0.000, 0.018)
print_window_metrics("it_A (secondary current)", t, itA, 0.000, 0.018)
print_window_metrics("i_leg_core_A", t, i_leg_core_A, 0.000, 0.018)
print_window_metrics("lam_leg_A", t, lam_A, 0.000, 0.018)

print("\nINRUSH EARLY WINDOW")
print_window_metrics("HV voltage A", t, vA_hv, 0.020, 0.040)
print_window_metrics("if_A (primary current)", t, ifA, 0.020, 0.040)
print_window_metrics("it_A (secondary current)", t, itA, 0.020, 0.040)
print_window_metrics("Generator current A", t, iA_gen, 0.020, 0.040)
print_window_metrics("i_leg_core_A", t, i_leg_core_A, 0.020, 0.040)
print_window_metrics("i_mag_A", t, i_mag_A, 0.020, 0.040)
print_window_metrics("lam_leg_A", t, lam_A, 0.020, 0.040)
print_window_metrics("lam_sum", t, lam_sum, 0.020, 0.040)

print("\nINRUSH LATER WINDOW")
print_window_metrics("HV voltage A", t, vA_hv, 0.080, 0.115)
print_window_metrics("if_A (primary current)", t, ifA, 0.080, 0.115)
print_window_metrics("it_A (secondary current)", t, itA, 0.080, 0.115)
print_window_metrics("Generator current A", t, iA_gen, 0.080, 0.115)
print_window_metrics("i_leg_core_A", t, i_leg_core_A, 0.080, 0.115)
print_window_metrics("i_mag_A", t, i_mag_A, 0.080, 0.115)
print_window_metrics("lam_leg_A", t, lam_A, 0.080, 0.115)
print_window_metrics("lam_sum", t, lam_sum, 0.080, 0.115)

if ifA is not None:
    early_mask = (t >= 0.020) & (t <= 0.040)
    late_mask = (t >= 0.080) & (t <= 0.115)

    if np.any(early_mask) and np.any(late_mask):
        early_peak = float(np.max(np.abs(ifA[early_mask])))
        late_peak = float(np.max(np.abs(ifA[late_mask])))
        if late_peak > 0.0:
            print("\nPrimary inrush decay ratio")
            print(f"  early peak |if_A| = {early_peak:.6f}")
            print(f"  late  peak |if_A| = {late_peak:.6f}")
            print(f"  early/late ratio   = {early_peak / late_peak:.6f}")

if lam_A is not None and i_leg_core_A is not None:
    early_mask = (t >= 0.020) & (t <= 0.040)
    late_mask = (t >= 0.080) & (t <= 0.115)

    if np.any(early_mask) and np.any(late_mask):
        lam_peak_early = float(np.max(np.abs(lam_A[early_mask])))
        i_peak_early = float(np.max(np.abs(i_leg_core_A[early_mask])))
        lam_peak_late = float(np.max(np.abs(lam_A[late_mask])))
        i_peak_late = float(np.max(np.abs(i_leg_core_A[late_mask])))

        print("\nMagnetic curve indicators")
        print(f"  early |lam_leg_A| peak = {lam_peak_early:.6f}")
        print(f"  early |i_leg_core_A| peak = {i_peak_early:.6f}")
        print(f"  late  |lam_leg_A| peak = {lam_peak_late:.6f}")
        print(f"  late  |i_leg_core_A| peak = {i_peak_late:.6f}")

######################################################################################################
# Plots
######################################################################################################

plt.figure(figsize=(13, 9))
plt.subplot(2, 1, 1)
plot_if_present(
    t,
    [(vA_hv, "HV bus - phase A"), (vB_hv, "HV bus - phase B"), (vC_hv, "HV bus - phase C")],
    "Primary-side bus voltages",
    "Voltage [p.u.]",
    event_time,
)
plt.subplot(2, 1, 2)
plot_if_present(
    t,
    [(vA_lv, "LV bus - phase A"), (vB_lv, "LV bus - phase B"), (vC_lv, "LV bus - phase C")],
    "Secondary-side bus voltages (no-load)",
    "Voltage [p.u.]",
    event_time,
)
plt.tight_layout()
plt.show()

plt.figure(figsize=(13, 10))
plt.subplot(2, 1, 1)
plot_if_present(
    t,
    [(ifA, "if_A"), (ifB, "if_B"), (ifC, "if_C")],
    "Transformer from-side terminal currents (primary)",
    "Current [p.u.]",
    event_time,
)
plt.subplot(2, 1, 2)
plot_if_present(
    t,
    [(itA, "it_A"), (itB, "it_B"), (itC, "it_C")],
    "Transformer to-side terminal currents (secondary, no-load)",
    "Current [p.u.]",
    event_time,
)
plt.tight_layout()
plt.show()

plt.figure(figsize=(13, 5))
plot_if_present(
    t,
    [(iA_gen, "i_A_gen"), (iB_gen, "i_B_gen"), (iC_gen, "i_C_gen")],
    "Generator terminal currents during energization",
    "Current [p.u.]",
    event_time,
)
plt.tight_layout()
plt.show()

plt.figure(figsize=(13, 10))
plot_if_present(
    t,
    [
        (lam_A, "lam_leg_A"),
        (lam_B, "lam_leg_B"),
        (lam_C, "lam_leg_C"),
        (lam_sum, "lam_sum"),
    ],
    "Transformer flux-linkage variables",
    "Internal value",
    event_time,
)
plt.tight_layout()
plt.show()

plt.figure(figsize=(13, 10))
plot_if_present(
    t,
    [
        (i_leg_core_A, "i_leg_core_A"),
        (i_leg_core_B, "i_leg_core_B"),
        (i_leg_core_C, "i_leg_core_C"),
        (i_return, "i_return_total"),
    ],
    "Transformer core currents",
    "Current / internal value",
    event_time,
)
plt.tight_layout()
plt.show()

plt.figure(figsize=(13, 8))
plot_if_present(
    t,
    [
        (i_mag_A, "i_mag_A"),
        (i_mag_B, "i_mag_B"),
        (i_mag_C, "i_mag_C"),
    ],
    "Transformer magnetizing currents",
    "Current / internal value",
    event_time,
)
plt.tight_layout()
plt.show()

if lam_A is not None and i_leg_core_A is not None:
    early_mask = (t >= 0.020) & (t <= 0.040)
    late_mask = (t >= 0.080) & (t <= 0.115)

    plt.figure(figsize=(12, 5))
    if np.any(early_mask):
        plt.plot(lam_A[early_mask], i_leg_core_A[early_mask], label="Early inrush lambda-i curve")
    if np.any(late_mask):
        plt.plot(lam_A[late_mask], i_leg_core_A[late_mask], label="Late lambda-i curve")
    plt.title("Phase-A Frohlich magnetic curve traversal during energization")
    plt.xlabel("lam_leg_A")
    plt.ylabel("i_leg_core_A")
    plt.grid(True)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.show()