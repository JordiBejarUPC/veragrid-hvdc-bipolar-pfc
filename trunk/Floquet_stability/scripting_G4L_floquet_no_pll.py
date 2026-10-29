# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import sys
import os
import matplotlib.pyplot as plt
from matplotlib import cm

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (BranchImpedanceMode, DynamicIntegrationMethod,
                                         EmtInitializationMethod, EmtSolverTypes, ShuntConnectionType, SolverType,
                                         SmallSignalEmtBuildTypes)
# from trunk.GridsForLoads_dynamic.gridsforloads_converter_template import (get_trafo_grid_connection_G4L,
#                                                                           get_complete_load_template_G4L)
from trunk.GridsForLoads_dynamic.gridsforloads_converter_template_no_pll import (get_trafo_grid_connection_G4L,
                                                                          get_complete_load_template_G4L)
import VeraGridEngine.api as gce

from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import SmallSignalStabilityEmtOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_results import SmallSignalStabilityEmtResults
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import SmallSignalStabilityEmtDriver


ASSESSMENT_TIMES = (0.2, 0.5, 1.0, 2.0)


def find_name_in_block(name, block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


def print_floquet_debug_summary(driver: SmallSignalStabilityEmtDriver,
                                results: SmallSignalStabilityEmtResults,
                                emt_options: EmtOptions) -> None:
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
    pf = np.asarray(results.participation_factors, dtype=np.float64)
    names = [str(v) for v in results.stat_vars]

    print("Dominant states per mode:")
    for mode_idx in range(pf.shape[1]):
        idx = np.argsort(-pf[:, mode_idx])[:top_n]
        entries = ", ".join(f"{names[i]}={pf[i, mode_idx]:.6f}" for i in idx)
        print(f"  mode {mode_idx:02d}: {entries}")
    print()


def get_neutral_mode_indices(results: SmallSignalStabilityEmtResults, tol: float = 1e-8) -> list[int]:
    mu = np.asarray(results.multipliers, dtype=np.complex128)
    return [i for i, mui in enumerate(mu) if abs(mui - 1.0) <= tol]


def get_dominant_mode_indices(results: SmallSignalStabilityEmtResults, count: int = 4) -> list[int]:
    mu = np.asarray(results.multipliers, dtype=np.complex128)
    order = np.argsort(-np.abs(mu))
    return list(order[:min(count, len(order))])


def get_unstable_mode_indices(results: SmallSignalStabilityEmtResults, tol: float = 1e-10) -> list[int]:
    lam = np.asarray(results.eigenvalues, dtype=np.complex128)
    return [i for i, lami in enumerate(lam) if np.real(lami) > tol]


def print_selected_mode_pf_table(results: SmallSignalStabilityEmtResults,
                                 mode_indices: list[int],
                                 top_n: int = 8,
                                 title: str = "Selected mode participation factors") -> None:
    pf = np.asarray(results.participation_factors, dtype=np.float64)
    names = [str(v) for v in results.stat_vars]

    print(title)
    for mode_idx in mode_indices:
        idx = np.argsort(-pf[:, mode_idx])[:top_n]
        print(f"  mode {mode_idx:02d}")
        for i in idx:
            print(f"    {names[i]}: {pf[i, mode_idx]:.6f}")
    print()


def plot_selected_mode_pf(results: SmallSignalStabilityEmtResults,
                          mode_indices: list[int],
                          top_n: int = 8,
                          title: str = "Selected mode participation factors") -> None:
    if len(mode_indices) == 0:
        return

    pf = np.asarray(results.participation_factors, dtype=np.float64)
    names = [str(v) for v in results.stat_vars]
    fig, axes = plt.subplots(len(mode_indices), 1, figsize=(12, max(3.0 * len(mode_indices), 4.0)))

    if len(mode_indices) == 1:
        axes = [axes]

    colors = cm.get_cmap('tab10', top_n)
    for ax, mode_idx in zip(axes, mode_indices):
        idx = np.argsort(-pf[:, mode_idx])[:top_n]
        vals = pf[idx, mode_idx]
        labels = [names[i] for i in idx]
        ax.barh(range(len(vals)), vals, color=[colors(i) for i in range(len(vals))])
        ax.set_yticks(range(len(vals)))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlabel('Participation factor')
        ax.set_title(f'Mode {mode_idx:02d}')
        ax.grid(True, axis='x', alpha=0.3)

    fig.suptitle(title)
    plt.tight_layout()
    plt.show(block=True)


def plot_s_domain_eigenvalues(eigenvalues: np.ndarray) -> None:
    """Plot Floquet exponents on the complex plane."""
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
    fig.suptitle('G4L EMT Floquet S-Domain Stability Plot')
    ax.set_xlabel('Real')
    ax.set_ylabel('Imaginary [rad/s]')
    ax.axhline(0.0, color='black', linewidth=1)
    ax.axvline(0.0, color='black', linewidth=1)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show(block=True)


def run_floquet_case(grid,
                     pf_results,
                     emt_options: EmtOptions,
                     ss_assessment_time: float,
                     k: int,
                     label: str):
    floquet_options = SmallSignalStabilityEmtOptions(k=k,
                                                     target_period=1.0 / grid.fBase,
                                                     ss_assessment_time=ss_assessment_time,
                                                     build_type=SmallSignalEmtBuildTypes.Arnoldi,
                                                     verbose=1)

    floquet_driver = SmallSignalStabilityEmtDriver(grid=grid,
                                                   pf_results=pf_results,
                                                   emt_options=emt_options,
                                                   sss_options=floquet_options)

    print(f"\nPreparing EMT Floquet run: {label}")
    print("Selected EMT test = none")
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

    print(f"Floquet multipliers = {floquet_results.multipliers}")
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

    neutral_modes = get_neutral_mode_indices(floquet_results)
    dominant_modes = get_dominant_mode_indices(floquet_results, count=4)
    print_selected_mode_pf_table(floquet_results,
                                 mode_indices=neutral_modes,
                                 top_n=8,
                                 title=f"Neutral mode PF table ({label})")
    print_selected_mode_pf_table(floquet_results,
                                 mode_indices=dominant_modes,
                                 top_n=8,
                                 title=f"Dominant mode PF table ({label})")

    return floquet_results


def print_assessment_time_comparison(reference_label: str,
                                     reference_results: SmallSignalStabilityEmtResults,
                                     sweep_results) -> None:
    ref_mu = np.asarray(reference_results.multipliers, dtype=np.complex128)
    print("================ Assessment-Time Comparison ================")
    print(f"reference = {reference_label}")
    for label, res in sweep_results:
        mu = np.asarray(res.multipliers, dtype=np.complex128)
        compare_n = min(6, len(ref_mu), len(mu))
        print(f"\ncase = {label}")
        for i in range(compare_n):
            print(
                f"  mode {i:02d}: "
                f"ref_mu=({ref_mu[i].real:+.12e}{ref_mu[i].imag:+.12e}j) "
                f"new_mu=({mu[i].real:+.12e}{mu[i].imag:+.12e}j) "
                f"|delta|={abs(mu[i] - ref_mu[i]):.12e}"
            )
    print("============================================================\n")


def plot_unstable_poles(results: SmallSignalStabilityEmtResults) -> None:
    lam = np.asarray(results.eigenvalues, dtype=np.complex128)
    unstable_idx = get_unstable_mode_indices(results)
    if len(unstable_idx) == 0:
        print("No unstable poles found to plot.")
        return

    vals = lam[unstable_idx]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(np.real(vals), np.imag(vals), color='red', s=120, marker='x')
    for idx, val in zip(unstable_idx, vals):
        ax.annotate(f"mode {idx}", (np.real(val), np.imag(val)), textcoords='offset points', xytext=(6, 6))
    ax.axhline(0.0, color='black', linewidth=1)
    ax.axvline(0.0, color='black', linewidth=1)
    ax.set_title('Unstable Floquet Poles')
    ax.set_xlabel('Real [rad/s]')
    ax.set_ylabel('Imaginary [rad/s]')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show(block=True)


U = 33000 / 1000
Sb = 2000000 / 1000000
omega = 2 * np.pi * 50.0

grid = gce.MultiCircuit(Sbase=Sb, fbase=50.0)

bus0 = gce.Bus(name="Bus0", Vnom=U, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=U)
grid.add_bus(bus0)
grid.add_bus(bus1)

R_trf_pu = 0.1 / 10.0
X_trf_pu = 1.0 / 10.0
B_sh_pu = 1.0 / 15.0
line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, r=R_trf_pu, x=X_trf_pu, b=B_sh_pu, rate=Sb)

P_dc_pu = 0.8
R_f_pu = 0.1 / 10.0
i_A0 = 0.030786800783117237
i_B0 = 0.31277189836412106
i_C0 = -0.34355869914723824
P_loss_f_pu = R_f_pu * (i_A0 * i_A0 + i_B0 * i_B0 + i_C0 * i_C0)
P_load_pu = P_dc_pu + P_loss_f_pu
P_target = 1.6
load = gce.Load(name="load", P=P_target, P1=P_target / 3, P2=P_target / 3, P3=P_target / 3,
                Q=0.0, Q1=0.0, Q2=0.0, Q3=0.0)
load.conn = ShuntConnectionType.GroundedStar

SCR = 3
RL = 0.1
R_g_pu = RL / SCR
X_g_pu = 1.0 / SCR
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq=50, r1=R_g_pu, x1=X_g_pu)

grid.add_line(line0)
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_load(bus=bus1, api_obj=load)

for bus in grid.buses:
    get_bus_emt_template(grid, bus)

gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
line_mdl = get_trafo_grid_connection_G4L(vf=grid.var_factory).block
load_mdl = get_complete_load_template_G4L(vf=grid.var_factory).block

set_emt_model(device=gen0, model=gen_mdl, var_factory=grid.var_factory)
set_emt_model(device=line0, model=line_mdl, var_factory=grid.var_factory)
set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

print("Selected EMT test: none (steady-state Floquet)")

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

power_flow = PowerFlowDriver(grid, pf_options)
power_flow.run()
res = power_flow.results
print("Balanced power flow results")
print("res.bus_names = ", res.bus_names)
print("res.branch_names = ", res.branch_names)
print("res.bus_types = ", res.bus_types)
print("res.voltage_A = ", res.voltage)
print("res.Sbus_A = ", res.Sbus)
print("res.Sf_A = ", res.Sf)
print("res.St_A = ", res.St)
print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

emt_options = EmtOptions(time_step=1e-6,
                         simulation_time=2.0,
                         tolerance=1e-6,
                         solver_type=EmtSolverTypes.Automatic,
                         initialization_method=EmtInitializationMethod.Explicit,
                         integration_method=DynamicIntegrationMethod.DaeBackEuler,
                         verbose=1)

preview_driver = SmallSignalStabilityEmtDriver(grid=grid,
                                               pf_results=res,
                                               emt_options=emt_options,
                                               sss_options=SmallSignalStabilityEmtOptions(k=6,
                                                                                          target_period=1.0 / grid.fBase,
                                                                                          ss_assessment_time=ASSESSMENT_TIMES[0],
                                                                                          build_type=SmallSignalEmtBuildTypes.Arnoldi,
                                                                                          verbose=1))

actual_n_states = preview_driver.problem.get_states_number()
actual_n_alg = preview_driver.problem.get_algebraic_var_number()
actual_n_total = preview_driver.problem.get_all_vars_number()

print("Template-derived dynamic states in G4L stack before bus/network coupling = 24")
print(f"Actual EMT problem states = {actual_n_states}")
print(f"Actual EMT problem algebraic vars = {actual_n_alg}")
print(f"Actual EMT problem total vars = {actual_n_total}")

reference_label = f"ss_assessment_time={ASSESSMENT_TIMES[0]}"
floquet_results = run_floquet_case(grid=grid,
                                   pf_results=res,
                                   emt_options=emt_options,
                                   ss_assessment_time=ASSESSMENT_TIMES[0],
                                   k=actual_n_states,
                                   label=reference_label)

sweep_results = []
for assessment_time in ASSESSMENT_TIMES[1:]:
    label = f"ss_assessment_time={assessment_time}"
    sweep_res = run_floquet_case(grid=grid,
                                 pf_results=res,
                                 emt_options=emt_options,
                                 ss_assessment_time=assessment_time,
                                 k=actual_n_states,
                                 label=label)
    sweep_results.append((label, sweep_res))

print_assessment_time_comparison(reference_label=reference_label,
                                 reference_results=floquet_results,
                                 sweep_results=sweep_results)

neutral_modes = get_neutral_mode_indices(floquet_results)
dominant_modes = get_dominant_mode_indices(floquet_results, count=4)
unstable_modes = get_unstable_mode_indices(floquet_results)

plot_s_domain_eigenvalues(np.asarray(floquet_results.eigenvalues, dtype=np.complex128))
plot_unstable_poles(floquet_results)
plot_selected_mode_pf(floquet_results,
                      mode_indices=unstable_modes,
                      top_n=8,
                      title='Unstable mode participation factors')
plot_selected_mode_pf(floquet_results,
                      mode_indices=neutral_modes,
                      top_n=8,
                      title='Neutral mode participation factors')
plot_selected_mode_pf(floquet_results,
                      mode_indices=dominant_modes,
                      top_n=8,
                      title='Dominant mode participation factors')
