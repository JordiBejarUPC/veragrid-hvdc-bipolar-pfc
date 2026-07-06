# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import cProfile
import numpy as np

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import matplotlib.pyplot as plt

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions

from VeraGridEngine.Utils.Symbolic.block import Block

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver


from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model

from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import SmallSignalStabilityEmtOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_results import SmallSignalStabilityEmtResults
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import SmallSignalStabilityEmtDriver

from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes, ShuntConnectionType,SmallSignalEmtBuildTypes
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

profiler = cProfile.Profile()
profiler.enable()

RUN_SENSITIVITY_SWEEP = True
SENSITIVITY_H_VALUES = (5e-6, 2.5e-6)
SENSITIVITY_METHODS = (
    DynamicIntegrationMethod.DaeTrapezoidal,
    DynamicIntegrationMethod.DaeBackEuler,
)
SENSITIVITY_TOP_MODES = 3


def print_floquet_debug_summary(driver: SmallSignalStabilityEmtDriver,
                                results: SmallSignalStabilityEmtResults,
                                emt_options: EmtOptions) -> None:
    """Print a compact diagnostic summary for EMT Floquet runs."""
    n_states = driver.problem.get_states_number()
    n_alg = driver.problem.get_algebraic_var_number()
    n_total = driver.problem.get_all_vars_number()
    h = emt_options.time_step
    T = driver.sss_options.target_period
    steps_per_period = int(T / h)

    print("\n================ Floquet Debug Summary ================")
    print(f"build_type = {driver.sss_options.build_type}")
    print(f"integration_method = {emt_options.integration_method}")
    print(f"time_step h = {h}")
    print(f"target_period T = {T}")
    print(f"steps_per_period = {steps_per_period}")
    print(f"ss_assessment_time = {driver.sss_options.ss_assessment_time}")
    print(f"n_states = {n_states}")
    print(f"n_algebraic = {n_alg}")
    print(f"n_total_vars = {n_total}")
    print(f"requested k = {driver.sss_options.k}")
    print(f"prefer_ak_operator = {driver.sss_options.prefer_ak_operator}")
    print(f"use_numba_kernels = {driver.sss_options.use_numba_kernels}")

    mu = np.asarray(results.multipliers, dtype=np.complex128)
    lam = np.asarray(results.eigenvalues, dtype=np.complex128)

    print(f"n_returned_modes = {len(mu)}")
    print(f"mu finite = {np.all(np.isfinite(mu))}")
    print(f"lambda finite = {np.all(np.isfinite(lam))}")
    print(f"all |mu| == 1 (1e-8 tol) = {np.allclose(np.abs(mu), 1.0, atol=1e-8)}")
    print(f"all lambda == 0 (1e-8 tol) = {np.allclose(lam, 0.0, atol=1e-8)}")

    if len(mu) > 0:
        abs_mu = np.abs(mu)
        print(f"|mu| min/max = {abs_mu.min():.12f} / {abs_mu.max():.12f}")
        print(f"max |mu - 1| = {np.max(np.abs(mu - 1.0)):.12e}")
        print(f"max |lambda| = {np.max(np.abs(lam)):.12e}")

    print("Mode table:")
    for i, (mui, lami) in enumerate(zip(mu, lam)):
        print(
            f"  mode {i:02d}: "
            f"mu=({mui.real:+.12e}{mui.imag:+.12e}j) "
            f"|mu|={abs(mui):.12e} "
            f"lambda=({lami.real:+.12e}{lami.imag:+.12e}j) "
            f"freq={results.conjugate_frequencies[i]:.8f}Hz "
            f"zeta={results.damping_ratios[i]:+.8f}"
        )
    print("=======================================================\n")


def print_mode_dominant_states(results: SmallSignalStabilityEmtResults, top_n: int = 5) -> None:
    """Print the dominant participation-factor states for each Floquet mode."""
    pf = np.asarray(results.participation_factors, dtype=np.float64)
    names = [str(v) for v in results.stat_vars]

    print("Dominant states per mode:")
    for mode_idx in range(pf.shape[1]):
        idx = np.argsort(-pf[:, mode_idx])[:top_n]
        entries = ", ".join(f"{names[i]}={pf[i, mode_idx]:.6f}" for i in idx)
        print(f"  mode {mode_idx:02d}: {entries}")
    print()


def make_emt_options(base_h: float, method: DynamicIntegrationMethod, solver_type: EmtSolverTypes) -> EmtOptions:
    return EmtOptions(time_step=base_h,
                      simulation_time=0.04,
                      tolerance=1e-6,
                      solver_type=solver_type,
                      integration_method=method,
                      verbose=1)


def make_floquet_options(k: int,
                         grid_frequency_hz: float,
                         build_type: SmallSignalEmtBuildTypes) -> SmallSignalStabilityEmtOptions:
    return SmallSignalStabilityEmtOptions(k=k,
                                          target_period=1.0 / grid_frequency_hz,
                                          ss_assessment_time=0.1,
                                          build_type=build_type,
                                          verbose=1)


def classify_mode_shift(mu_ref: complex, mu_new: complex) -> str:
    delta = abs(mu_new - mu_ref)
    mag_delta = abs(abs(mu_new) - abs(mu_ref))

    if delta < 1e-6 and mag_delta < 1e-6:
        return "very stable numerically"
    if delta < 1e-4 and mag_delta < 1e-4:
        return "stable numerically"
    if delta < 1e-2 and mag_delta < 1e-2:
        return "moderately sensitive"
    return "highly sensitive"


def print_sensitivity_comparison(reference_label: str,
                                 reference_results: SmallSignalStabilityEmtResults,
                                 sweep_results,
                                 top_modes: int) -> None:
    ref_mu = np.asarray(reference_results.multipliers, dtype=np.complex128)
    n_compare = min(top_modes, len(ref_mu))

    print("================ Floquet Sensitivity Sweep ================")
    print(f"reference = {reference_label}")
    for label, res in sweep_results:
        mu = np.asarray(res.multipliers, dtype=np.complex128)
        print(f"\ncase = {label}")
        for i in range(min(n_compare, len(mu))):
            verdict = classify_mode_shift(ref_mu[i], mu[i])
            print(
                f"  mode {i:02d}: "
                f"ref_mu=({ref_mu[i].real:+.12e}{ref_mu[i].imag:+.12e}j) "
                f"new_mu=({mu[i].real:+.12e}{mu[i].imag:+.12e}j) "
                f"|delta|={abs(mu[i] - ref_mu[i]):.12e} "
                f"verdict={verdict}"
            )
    print("===========================================================\n")


def run_floquet_case(grid,
                     pf_results,
                     h: float,
                     method: DynamicIntegrationMethod,
                     solver_type: EmtSolverTypes,
                     k: int,
                     build_type: SmallSignalEmtBuildTypes,
                     label: str,
                     print_setup: bool = False,
                     print_full_results: bool = False):
    emt_options = make_emt_options(base_h=h, method=method, solver_type=solver_type)
    floquet_options = make_floquet_options(k=k, grid_frequency_hz=grid.fBase, build_type=build_type)

    floquet_driver = SmallSignalStabilityEmtDriver(grid=grid,
                                                   pf_results=pf_results,
                                                   emt_options=emt_options,
                                                   sss_options=floquet_options)

    if print_setup:
        print(f"\nPreparing EMT Floquet run: {label}")
        print(f"EMT h = {emt_options.time_step}")
        print(f"EMT simulation_time = {emt_options.simulation_time}")
        print(f"integration_method = {emt_options.integration_method}")
        print(f"Floquet target_period = {floquet_options.target_period}")
        print(f"Floquet ss_assessment_time = {floquet_options.ss_assessment_time}")
        print(f"Floquet requested k = {floquet_options.k}")
        print(f"Grid fBase = {grid.fBase}")
        print(f"Power flow converged = {pf_results.converged}")

        emt_problem_preview = floquet_driver.problem
        print(f"EMT problem states = {emt_problem_preview.get_states_number()}")
        print(f"EMT problem algebraic vars = {emt_problem_preview.get_algebraic_var_number()}")
        print(f"EMT problem total vars = {emt_problem_preview.get_all_vars_number()}")

    floquet_driver.run()
    floquet_results = floquet_driver.results

    if print_full_results:
        print(f"Floquet multipliers = {floquet_results.multipliers}")
        print(f"Floquet right_vecs = {floquet_results.right_vecs}")
        print(f"Floquet left_vecs = {floquet_results.left_vecs}")
        print(f"Floquet period = {floquet_results.period}")
        print(f"Floquet stat_vars = {floquet_results.stat_vars}")
        print(f"Floquet eigenvalues = {floquet_results.eigenvalues}")
        print(f"Floquet damping_ratios = {floquet_results.damping_ratios}")
        print(f"Floquet conjugate_frequencies = {floquet_results.conjugate_frequencies}")
        print(f"Floquet participation_factors = {floquet_results.participation_factors}")

    print_floquet_debug_summary(driver=floquet_driver,
                                results=floquet_results,
                                emt_options=emt_options)
    print_mode_dominant_states(results=floquet_results, top_n=5)

    return floquet_driver, floquet_results


def plot_s_domain_eigenvalues(eigenvalues: np.ndarray) -> None:
    """Plot EMT eigenvalues on the complex plane."""
    if eigenvalues.size == 0:
        return

    re = np.real(eigenvalues)
    im = np.imag(eigenvalues)
    data_span_re = re.max() - re.min()
    data_span_im = im.max() - im.min()
    margin_x = max(data_span_re * 0.1, 1.0)
    margin_y = max(data_span_im * 0.1, 1.0)
    x_min = re.min() - margin_x
    x_max = re.max() + margin_x
    y_min = im.min() - margin_y
    y_max = im.max() + margin_y

    d = np.abs(np.nan_to_num(re))
    max_d = d.max()
    colors = -d / max_d if max_d > 0.0 else np.zeros_like(d)

    slope = 1.0 / 0.05
    x_z = np.linspace(min(-200.0, x_min), 0.0, 400)
    y_z = slope * x_z

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot(x_z, y_z, '--', color='grey', linewidth=0.7, alpha=0.6, label='zeta = 5%')
    ax.plot(x_z, -y_z, '--', color='grey', linewidth=0.7, alpha=0.6)
    ax.scatter(re, im, c=colors, cmap='winter', s=120, alpha=0.8)
    fig.suptitle('EMT S-Domain Stability plot')
    ax.set_xlabel('Real')
    ax.set_ylabel('Imaginary [rad/s]')
    ax.axhline(0.0, color='black', linewidth=1)
    ax.axvline(0.0, color='black', linewidth=1)
    # ax.set_xlim([x_min, x_max])
    # ax.set_ylim([y_min, y_max])
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show(block=True)

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

# Buses
vnom = 10 #kV
bus0 = gce.Bus(name="Bus0", Vnom=vnom, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=vnom)

grid.add_bus(bus0)
grid.add_bus(bus1)

# Lines
line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)


# physical configuration (Overhead line tower)
tower = gce.OverheadLineType(name="Tower", Vnom=vnom)
wire = gce.Wire(name="Panther 30/7 ACSR",
                diameter=21.0,
                diameter_internal=9.0,
                is_tube=True,
                r=0.1363,
                max_current=1)
tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
tower.compute()

# Aplicar física a la línea
line0.apply_template(tower, grid.Sbase, grid.fBase)

# load
# P=1.0
# Q= 0.999999
R_ph =100 #ohm
v_ph = vnom / (3**0.5)
P_ph = (v_ph**2) / R_ph # kv*kv/ohm = MW
print("P_ph=", P_ph)

# load = gce.Load(name="load",P1= P/3, P2= P/3, P3= P/3, Q1= Q/3, Q2= Q/3, Q3= Q/3)
load = gce.Load(name="load",P1= P_ph, P2= P_ph, P3= P_ph, Q1= 0.0, Q2= 0.0, Q3= 0.0)
load.conn = ShuntConnectionType.GroundedStar

# Generator
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq = 50, r1=0.001, x1=1.7)
# r1=Ra, x1=xd'

grid.add_line(line0)
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_load(bus=bus1, api_obj=load)


for bus in grid.buses:
    get_bus_emt_template(grid, bus)

######################################################################################################
# Build EMT models
######################################################################################################

# generator
gen_mdl = get_complete_generator_template_emt(vf = grid.var_factory).block

# line
line_mdl = get_pi_line_emt_template(vf=grid.var_factory, phN = False, phA = True, phB = True, phC = True).block
# line_mdl = get_pi_line_emt_template(grid = grid, line = line0).block

# load
load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

######################################################################################################
# Add models to devices
######################################################################################################

set_emt_model(device=gen0, model=gen_mdl, var_factory= grid.var_factory)

set_emt_model(device=line0, model=line_mdl, var_factory= grid.var_factory)

set_emt_model(device=load, model=load_mdl, var_factory= grid.var_factory)

# connection with buses
# gen_mdl.connect([gen_mdl.in_vars[0]], [bus0.emt_model.out_vars[0]]) # v_A
# gen_mdl.connect([gen_mdl.in_vars[1]], [bus0.emt_model.out_vars[1]]) # v_B
# gen_mdl.connect([gen_mdl.in_vars[2]], [bus0.emt_model.out_vars[2]]) # v_C
#
#
# line_mdl.connect([line_mdl.in_vars[0]], [bus0.emt_model.out_vars[0]]) # line vf_A
# line_mdl.connect([line_mdl.in_vars[1]], [bus0.emt_model.out_vars[1]]) # line vf_B
# line_mdl.connect([line_mdl.in_vars[2]], [bus0.emt_model.out_vars[2]]) # line vf_C
#
# line_mdl.connect([line_mdl.in_vars[3]], [bus1.emt_model.out_vars[0]]) # line vt_A
# line_mdl.connect([line_mdl.in_vars[4]], [bus1.emt_model.out_vars[1]]) # line vt_B
# line_mdl.connect([line_mdl.in_vars[5]], [bus1.emt_model.out_vars[2]]) # line vt_C
#
# load_mdl.connect([load_mdl.in_vars[0]], [bus1.emt_model.out_vars[0]]) # v_A
# load_mdl.connect([load_mdl.in_vars[1]], [bus1.emt_model.out_vars[1]]) # v_B
# load_mdl.connect([load_mdl.in_vars[2]], [bus1.emt_model.out_vars[2]]) # v_C
#
# # external mapping
# big_gen1 = Block(children=[gen_mdl])
#
# big_gen1.external_mapping.update({VarPowerFlowReferenceType.P: gen_mdl.out_vars[0]})
# big_gen1.external_mapping.update({VarPowerFlowReferenceType.Q: gen_mdl.out_vars[1]})
#
# # attach emt models to Veragrid objects
# line0.emt_model= line_mdl
# load.emt_model= load_mdl
# gen0.emt_model= big_gen1

# gce.save_file(grid=grid, filename="grid_save_event.veragrid")

pf_options = PowerFlowOptions(
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

# res = gce.power_flow(grid=grid, options=pf_options)
# power_flow = PowerFlowDriver(grid=grid, options=pf_options)
power_flow = PowerFlowDriver3Ph(grid, pf_options)
power_flow.run()
res = power_flow.results
print("res.m (branch number)= ", res.m)
print("res.n (bus number)= ", res.n)
print("res.n_gen = ", res.n_gen)
print("res.n_load ", res.n_load)
print("res.bus_names = ", res.bus_names)
print("res.branch_names = ", res.branch_names)
print("res.load_names = ", res.load_names)
print("res.bus_types = ", res.bus_types)
print("res.voltage_A = ", res.voltage_A)
print("res.voltage_B = ", res.voltage_B)
print("res.voltage_C = ", res.voltage_C)
print("res.Sbus_A = ", res.Sbus_A)
print("res.Sbus_B = ", res.Sbus_B)
print("res.Sbus_C = ", res.Sbus_C)
print("res.Sf_A = ", res.Sf_A)
print("res.Sf_B = ", res.Sf_B)
print("res.Sf_C = ", res.Sf_C)
print("res.St_A = ", res.St_A)
print("res.St_B = ", res.St_B)
print("res.St_C = ", res.St_C)

print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())


CHOSEN_SOLVER = "AD"
ENABLE_PLOTS = True
ENABLE_NEWTON_TRACE = False
DENSE_THRESHOLD = 0
SOLVER_VERBOSE = True

SOLVER_TYPE_MAP = {
    "SYMBOLIC": EmtSolverTypes.Symbolic,
    "AD": EmtSolverTypes.Automatic,
    "VECTORIZED": EmtSolverTypes.StructuralAD,
    "COMPILED": EmtSolverTypes.StructuralCompiled,
}

ALL_SOLVER_KEYS = ["SYMBOLIC", "AD", "VECTORIZED", "COMPILED"]

if CHOSEN_SOLVER not in SOLVER_TYPE_MAP:
    raise ValueError(f"Solver '{CHOSEN_SOLVER}' no reconocido. Usa SYMBOLIC, AD, VECTORIZED o COMPILED.")

base_h = 5e-6
base_method = DynamicIntegrationMethod.DaeTrapezoidal
base_build_type = SmallSignalEmtBuildTypes.Arnoldi
base_k = 29

floquet_driver, floquet_results = run_floquet_case(
    grid=grid,
    pf_results=res,
    h=base_h,
    method=base_method,
    solver_type=SOLVER_TYPE_MAP[CHOSEN_SOLVER],
    k=base_k,
    build_type=base_build_type,
    label="base",
    print_setup=True,
    print_full_results=True,
)

if RUN_SENSITIVITY_SWEEP:
    sweep_results = []
    for h_value in SENSITIVITY_H_VALUES:
        for method_value in SENSITIVITY_METHODS:
            if h_value == base_h and method_value == base_method:
                continue

            label = f"h={h_value}, method={method_value}"
            _, sweep_res = run_floquet_case(
                grid=grid,
                pf_results=res,
                h=h_value,
                method=method_value,
                solver_type=SOLVER_TYPE_MAP[CHOSEN_SOLVER],
                k=base_k,
                build_type=base_build_type,
                label=label,
                print_setup=True,
                print_full_results=False,
            )
            sweep_results.append((label, sweep_res))

    print_sensitivity_comparison(reference_label=f"h={base_h}, method={base_method}",
                                 reference_results=floquet_results,
                                 sweep_results=sweep_results,
                                 top_modes=SENSITIVITY_TOP_MODES)

if ENABLE_PLOTS:
    plot_s_domain_eigenvalues(np.asarray(floquet_results.eigenvalues, dtype=np.complex128))






