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

from pathlib import Path
from typing import List, Dict

from trunk.dynamics_emt.support.emt_plot_exports import (
    get_plot_results_directory,
    save_scalar_step_plot,
    save_two_panel_three_phase_plot,
    )

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

################################################################################################
# Energization test for the transformer, open circuit
################################################################################################

EVENT_TIMES = [0.020005, 0.023, 0.026, 0.029]
PLOT_CASE_NAME = "xfmr_transformer_energizing_saturation"
OUTPUT_ROOT_NAME = "plot_results"
ENABLE_PLOTS = True


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


def plot_case(ax, time_values: np.ndarray, series_list: list[tuple[np.ndarray | None, str]], title: str, ylabel: str,
              event_time: float) -> None:
    """
    Plot one case in one subplot.
    """
    n_lines = 0
    for series, label in series_list:
        if series is not None:
            ax.plot(time_values, series, label=label)
            n_lines += 1

    ax.axvline(event_time, color="k", linestyle=":", linewidth=1.0, label="Energization event")
    ax.set_title(f"{title}\n(event_time = {event_time:.6f} s)")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel(ylabel)
    ax.grid(True)
    if n_lines > 0:
        ax.legend(loc="best")

def export_comparison_plots(results: list[dict[str, Any]]) -> List[Path]:
    """
    Export comparison plots for all event times using the same output style
    as the EMT event demo.

    :param results: Simulation result dictionaries.
    :type results: list[dict[str, Any]]
    :return: Generated plot file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_plot_results_directory(
        PLOT_CASE_NAME,
        "COMPARISON",
        OUTPUT_ROOT_NAME,
    )
    generated_paths: List[Path] = list()

    result_index: int = 0
    while result_index < len(results):
        result: dict[str, Any] = results[result_index]
        event_time: float = float(result["event_time"])
        suffix: str = f"evt_{str(event_time).replace('.', 'p')}"

        time_values: np.ndarray = result["t"]

        # 1) Bus voltages
        voltage_path: Path = output_dir / f"{suffix}_bus_voltages.png"
        save_two_panel_three_phase_plot(
            file_path=voltage_path,
            time_values=time_values,
            top_triplet=(result["vA_hv"], result["vB_hv"], result["vC_hv"]),
            top_title=f"Primary-side bus voltages | event_time = {event_time:.6f} s",
            top_ylabel="Voltage [p.u.]",
            top_legend_prefix="HV",
            bottom_triplet=(result["vA_lv"], result["vB_lv"], result["vC_lv"]),
            bottom_title=f"Secondary-side bus voltages (no-load) | event_time = {event_time:.6f} s",
            bottom_ylabel="Voltage [p.u.]",
            bottom_legend_prefix="LV",
        )
        generated_paths.append(voltage_path)

        # 2) Transformer terminal currents
        current_path: Path = output_dir / f"{suffix}_xfmr_terminal_currents.png"
        save_two_panel_three_phase_plot(
            file_path=current_path,
            time_values=time_values,
            top_triplet=(result["ifA"], result["ifB"], result["ifC"]),
            top_title=f"Transformer from-side terminal currents | event_time = {event_time:.6f} s",
            top_ylabel="Current [p.u.]",
            top_legend_prefix="if",
            bottom_triplet=(result["itA"], result["itB"], result["itC"]),
            bottom_title=f"Transformer to-side terminal currents (no-load) | event_time = {event_time:.6f} s",
            bottom_ylabel="Current [p.u.]",
            bottom_legend_prefix="it",
        )
        generated_paths.append(current_path)

        # 3) Generator currents
        gen_current_path: Path = output_dir / f"{suffix}_generator_currents.png"
        save_scalar_step_plot(
            file_path=gen_current_path,
            time_values=time_values,
            values_triplet=(result["iA_gen"], result["iB_gen"], result["iC_gen"]),
            title=f"Generator terminal currents during energization | event_time = {event_time:.6f} s",
            y_label="Current [p.u.]",
            legend_prefix="i_gen",
        )
        generated_paths.append(gen_current_path)

        # 4) Flux-linkage variables
        flux_path: Path = output_dir / f"{suffix}_flux_linkages.png"
        save_scalar_step_plot(
            file_path=flux_path,
            time_values=time_values,
            values_triplet=(result["lam_A"], result["lam_B"], result["lam_C"]),
            title=f"Transformer flux-linkage variables | event_time = {event_time:.6f} s",
            y_label="Internal value",
            legend_prefix="lam",
        )
        generated_paths.append(flux_path)

        # 5) Core currents
        core_current_path: Path = output_dir / f"{suffix}_core_currents.png"
        save_scalar_step_plot(
            file_path=core_current_path,
            time_values=time_values,
            values_triplet=(result["i_leg_core_A"], result["i_leg_core_B"], result["i_leg_core_C"]),
            title=f"Transformer core currents | event_time = {event_time:.6f} s",
            y_label="Current / internal value",
            legend_prefix="i_leg_core",
        )
        generated_paths.append(core_current_path)

        # 6) Magnetizing currents
        mag_current_path: Path = output_dir / f"{suffix}_magnetizing_currents.png"
        save_scalar_step_plot(
            file_path=mag_current_path,
            time_values=time_values,
            values_triplet=(result["i_mag_A"], result["i_mag_B"], result["i_mag_C"]),
            title=f"Transformer magnetizing currents | event_time = {event_time:.6f} s",
            y_label="Current / internal value",
            legend_prefix="i_mag",
        )
        generated_paths.append(mag_current_path)

        result_index += 1

    return generated_paths

def export_combined_comparison_figures(results: list[dict[str, Any]]) -> List[Path]:
    """
    Export the 2x2 comparison figures that are also shown interactively.

    :param results: Simulation result dictionaries.
    :type results: list[dict[str, Any]]
    :return: Generated plot file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_plot_results_directory(
        PLOT_CASE_NAME,
        "COMPARISON",
        OUTPUT_ROOT_NAME,
    )
    generated_paths: List[Path] = list()

    figure_specs = [
        (
            "comparison_primary_voltages.png",
            "Primary-side bus voltages",
            lambda r: [(r["vA_hv"], "HV bus - phase A"), (r["vB_hv"], "HV bus - phase B"), (r["vC_hv"], "HV bus - phase C")],
            "Voltage [p.u.]",
        ),
        (
            "comparison_secondary_voltages.png",
            "Secondary-side bus voltages (no-load)",
            lambda r: [(r["vA_lv"], "LV bus - phase A"), (r["vB_lv"], "LV bus - phase B"), (r["vC_lv"], "LV bus - phase C")],
            "Voltage [p.u.]",
        ),
        (
            "comparison_primary_currents.png",
            "Transformer from-side terminal currents (primary)",
            lambda r: [(r["ifA"], "if_A"), (r["ifB"], "if_B"), (r["ifC"], "if_C")],
            "Current [p.u.]",
        ),
        (
            "comparison_secondary_currents.png",
            "Transformer to-side terminal currents (secondary, no-load)",
            lambda r: [(r["itA"], "it_A"), (r["itB"], "it_B"), (r["itC"], "it_C")],
            "Current [p.u.]",
        ),
        (
            "comparison_generator_currents.png",
            "Generator terminal currents during energization",
            lambda r: [(r["iA_gen"], "i_A_gen"), (r["iB_gen"], "i_B_gen"), (r["iC_gen"], "i_C_gen")],
            "Current [p.u.]",
        ),
        (
            "comparison_flux_linkages.png",
            "Transformer flux-linkage variables",
            lambda r: [(r["lam_A"], "lam_leg_A"), (r["lam_B"], "lam_leg_B"), (r["lam_C"], "lam_leg_C"), (r["lam_sum"], "lam_sum")],
            "Internal value",
        ),
        (
            "comparison_core_currents.png",
            "Transformer core currents",
            lambda r: [
                (r["i_leg_core_A"], "i_leg_core_A"),
                (r["i_leg_core_B"], "i_leg_core_B"),
                (r["i_leg_core_C"], "i_leg_core_C"),
                (r["i_return"], "i_return_total"),
            ],
            "Current / internal value",
        ),
        (
            "comparison_magnetizing_currents.png",
            "Transformer magnetizing currents",
            lambda r: [(r["i_mag_A"], "i_mag_A"), (r["i_mag_B"], "i_mag_B"), (r["i_mag_C"], "i_mag_C")],
            "Current / internal value",
        ),
    ]

    spec_index: int = 0
    while spec_index < len(figure_specs):
        filename, super_title, series_builder, ylabel = figure_specs[spec_index]

        fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=False)
        fig.suptitle(super_title)

        for ax, result in zip(axes.flatten(), results):
            plot_case(
                ax,
                result["t"],
                series_builder(result),
                title="",
                ylabel=ylabel,
                event_time=result["event_time"],
            )
            ax.set_title(f"event_time = {result['event_time']:.6f} s")

        plt.tight_layout()
        out_path: Path = output_dir / filename
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated_paths.append(out_path)

        spec_index += 1

    # lambda-i combined figure
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Phase-A Frohlich magnetic curve traversal during energization")

    for ax, result in zip(axes.flatten(), results):
        t = result["t"]
        lam_A = result["lam_A"]
        i_leg_core_A = result["i_leg_core_A"]
        event_time = result["event_time"]

        if lam_A is not None and i_leg_core_A is not None:
            early_mask = (t >= event_time) & (t <= event_time + 0.02)
            late_mask = (t >= max(event_time + 0.06, 0.08)) & (t <= min(event_time + 0.095, t[-1]))

            if np.any(early_mask):
                ax.plot(lam_A[early_mask], i_leg_core_A[early_mask], label="Early inrush lambda-i curve")
            if np.any(late_mask):
                ax.plot(lam_A[late_mask], i_leg_core_A[late_mask], label="Late lambda-i curve")

        ax.set_title(f"event_time = {event_time:.6f} s")
        ax.set_xlabel("lam_leg_A")
        ax.set_ylabel("i_leg_core_A")
        ax.grid(True)
        ax.legend(loc="best")

    plt.tight_layout()
    lambda_i_path: Path = output_dir / "comparison_lambda_i.png"
    fig.savefig(lambda_i_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    generated_paths.append(lambda_i_path)

    return generated_paths

def build_grid_and_run(event_time: float) -> dict[str, Any]:
    """
    Build the full case, run PF + EMT, and return all relevant trajectories.

    :param event_time: Energization instant.
    :type event_time: float
    :return: Result dictionary.
    :rtype: dict[str, Any]
    """
    grid = MultiCircuit(Sbase=100.0, fbase=50.0)

    bus_hv = Bus(name="Bus_HV", Vnom=20.0, is_slack=True)
    bus_lv = Bus(name="Bus_LV", Vnom=0.69)

    grid.add_bus(bus_hv)
    grid.add_bus(bus_lv)

    gen = Generator(name="gen_test", vset=0.000001, Snom=100.0, freq=50.0, r1=0.05, x1=0.25)
    grid.add_generator(bus=bus_hv, api_obj=gen)

    xfmr = Transformer2W(
        bus_from=bus_hv,
        bus_to=bus_lv,
        name="Transformer",
        HV=20.0,
        LV=0.69,
        nominal_power=100.0,
        copper_losses=1000.0,
        iron_losses=150.0, # smaller than 200
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

    xfmr_mdl = get_xfmr_emt_template(vf=grid.var_factory, name="xfmr_sat_test").block
    gen_mdl = get_generator_thevenin_rl_emt_template(vf=grid.var_factory, name="gen_sat_test").block
    load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

    set_emt_model(device=xfmr, model=xfmr_mdl, var_factory=grid.var_factory)
    set_emt_model(device=gen, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    ##################################################################################################
    # Transformer setup
    ##################################################################################################
    xfmr_mdl.set_parameter_in_model(var_name="xfmr_use_linear_core_xfmr_sat_test", new_value=0.0) # using frohlich
    xfmr_mdl.set_parameter_in_model(var_name="xfmr_c_term_xfmr_sat_test", new_value=1e-6)

    xfmr_mdl.set_parameter_in_model(var_name="xfmr_core_topology_code_xfmr_sat_test", new_value=3.0)
    xfmr_mdl.set_parameter_in_model(var_name="xfmr_yoke_area_rel_xfmr_sat_test", new_value=1.0)
    xfmr_mdl.set_parameter_in_model(var_name="xfmr_yoke_length_rel_xfmr_sat_test", new_value=1.0)
    xfmr_mdl.set_parameter_in_model(var_name="xfmr_outer_leg_area_rel_xfmr_sat_test", new_value=1.0)
    xfmr_mdl.set_parameter_in_model(var_name="xfmr_outer_leg_length_rel_xfmr_sat_test", new_value=1.0)

    # Fixed Frohlich coefficients
    xfmr_mdl.set_parameter_in_model(var_name="xfmr_core_a_prime_xfmr_sat_test", new_value=0.00197) # 0.00197
    xfmr_mdl.set_parameter_in_model(var_name="xfmr_core_b_prime_xfmr_sat_test", new_value=0.15) # 0.25

    # Secondary almost open.
    load_mdl.set_parameter_in_model(var_name="R_A_Shunt_R_3ph", new_value=1e9)
    load_mdl.set_parameter_in_model(var_name="R_B_Shunt_R_3ph", new_value=1e9)
    load_mdl.set_parameter_in_model(var_name="R_C_Shunt_R_3ph", new_value=1e9)

    ##################################################################################################
    # Generator breaker-less energization
    ##################################################################################################
    gen_mdl.set_parameter_in_model(var_name="E_scale_gen_sat_test", new_value=1.0)

    gen_escale = find_name_in_block("E_scale_gen_sat_test", gen_mdl)
    if gen_escale is None:
        raise ValueError(
            "The generator EMT template does not expose E_scale_gen_sat_test. "
            "Add a local event_dict parameter E_scale to the Thevenin EMT generator template "
            "and multiply Epk_expr by E_scale in e_A/e_B/e_C."
        )

    events_group = EmtEventsGroup(name=f"xfmr_inrush_demo_{event_time:.6f}")
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

    ##################################################################################################
    # Power Flow
    ##################################################################################################
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
    print(f"3Ph POWER FLOW RESULTS | event_time = {event_time:.6f} s")
    print("=" * 70)
    print(f"Converged: {res.converged}")
    print(res.get_bus_df())
    print(res.get_branch_df())

    ##################################################################################################
    # EMT
    ##################################################################################################
    options = EmtOptions(
        time_step=5e-6,
        simulation_time=0.8,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        initialization_method=EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=1,
    )

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

    ##################################################################################################
    # Extract trajectories
    ##################################################################################################
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

    return {
        "event_time": event_time,
        "t": t,
        "vA_hv": vA_hv, "vB_hv": vB_hv, "vC_hv": vC_hv,
        "vA_lv": vA_lv, "vB_lv": vB_lv, "vC_lv": vC_lv,
        "ifA": ifA, "ifB": ifB, "ifC": ifC,
        "itA": itA, "itB": itB, "itC": itC,
        "iA_gen": iA_gen, "iB_gen": iB_gen, "iC_gen": iC_gen,
        "lam_A": lam_A, "lam_B": lam_B, "lam_C": lam_C, "lam_sum": lam_sum,
        "i_leg_core_A": i_leg_core_A, "i_leg_core_B": i_leg_core_B, "i_leg_core_C": i_leg_core_C,
        "i_mag_A": i_mag_A, "i_mag_B": i_mag_B, "i_mag_C": i_mag_C,
        "i_return": i_return,
    }


def make_2x2_figure(results: list[dict[str, Any]], title: str, builder) -> None:
    """
    Create one 2x2 figure, one event_time per subplot.
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=False)
    fig.suptitle(title)

    for ax, result in zip(axes.flatten(), results):
        builder(ax, result)

    plt.tight_layout()
    plt.show()


def plot_all_results(results: list[dict[str, Any]]) -> None:
    """
    Create all comparison figures.
    """

    make_2x2_figure(
        results,
        "Primary-side bus voltages",
        lambda ax, r: plot_case(
            ax,
            r["t"],
            [(r["vA_hv"], "HV bus - phase A"), (r["vB_hv"], "HV bus - phase B"), (r["vC_hv"], "HV bus - phase C")],
            "Primary-side bus voltages",
            "Voltage [p.u.]",
            r["event_time"],
        ),
    )

    make_2x2_figure(
        results,
        "Secondary-side bus voltages (no-load)",
        lambda ax, r: plot_case(
            ax,
            r["t"],
            [(r["vA_lv"], "LV bus - phase A"), (r["vB_lv"], "LV bus - phase B"), (r["vC_lv"], "LV bus - phase C")],
            "Secondary-side bus voltages (no-load)",
            "Voltage [p.u.]",
            r["event_time"],
        ),
    )

    make_2x2_figure(
        results,
        "Transformer from-side terminal currents (primary)",
        lambda ax, r: plot_case(
            ax,
            r["t"],
            [(r["ifA"], "if_A"), (r["ifB"], "if_B"), (r["ifC"], "if_C")],
            "Transformer from-side terminal currents (primary)",
            "Current [p.u.]",
            r["event_time"],
        ),
    )

    make_2x2_figure(
        results,
        "Transformer to-side terminal currents (secondary, no-load)",
        lambda ax, r: plot_case(
            ax,
            r["t"],
            [(r["itA"], "it_A"), (r["itB"], "it_B"), (r["itC"], "it_C")],
            "Transformer to-side terminal currents (secondary, no-load)",
            "Current [p.u.]",
            r["event_time"],
        ),
    )

    make_2x2_figure(
        results,
        "Generator terminal currents during energization",
        lambda ax, r: plot_case(
            ax,
            r["t"],
            [(r["iA_gen"], "i_A_gen"), (r["iB_gen"], "i_B_gen"), (r["iC_gen"], "i_C_gen")],
            "Generator terminal currents during energization",
            "Current [p.u.]",
            r["event_time"],
        ),
    )

    make_2x2_figure(
        results,
        "Transformer flux-linkage variables",
        lambda ax, r: plot_case(
            ax,
            r["t"],
            [(r["lam_A"], "lam_leg_A"), (r["lam_B"], "lam_leg_B"), (r["lam_C"], "lam_leg_C"), (r["lam_sum"], "lam_sum")],
            "Transformer flux-linkage variables",
            "Internal value",
            r["event_time"],
        ),
    )

    make_2x2_figure(
        results,
        "Transformer core currents",
        lambda ax, r: plot_case(
            ax,
            r["t"],
            [
                (r["i_leg_core_A"], "i_leg_core_A"),
                (r["i_leg_core_B"], "i_leg_core_B"),
                (r["i_leg_core_C"], "i_leg_core_C"),
                (r["i_return"], "i_return_total"),
            ],
            "Transformer core currents",
            "Current / internal value",
            r["event_time"],
        ),
    )

    make_2x2_figure(
        results,
        "Transformer magnetizing currents",
        lambda ax, r: plot_case(
            ax,
            r["t"],
            [(r["i_mag_A"], "i_mag_A"), (r["i_mag_B"], "i_mag_B"), (r["i_mag_C"], "i_mag_C")],
            "Transformer magnetizing currents",
            "Current / internal value",
            r["event_time"],
        ),
    )

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Phase-A Frohlich magnetic curve traversal during energization")

    for ax, result in zip(axes.flatten(), results):
        t = result["t"]
        lam_A = result["lam_A"]
        i_leg_core_A = result["i_leg_core_A"]
        event_time = result["event_time"]

        if lam_A is not None and i_leg_core_A is not None:
            early_mask = (t >= event_time) & (t <= event_time + 0.02)
            late_mask = (t >= max(event_time + 0.06, 0.08)) & (t <= min(event_time + 0.095, t[-1]))

            if np.any(early_mask):
                ax.plot(lam_A[early_mask], i_leg_core_A[early_mask], label="Early inrush lambda-i curve")
            if np.any(late_mask):
                ax.plot(lam_A[late_mask], i_leg_core_A[late_mask], label="Late lambda-i curve")

        ax.set_title(f"event_time = {event_time:.6f} s")
        ax.set_xlabel("lam_leg_A")
        ax.set_ylabel("i_leg_core_A")
        ax.grid(True)
        ax.legend(loc="best")

    plt.tight_layout()
    plt.show()


##################################################################################################
# Main
##################################################################################################

if __name__ == "__main__":
    all_results = []
    for evt in EVENT_TIMES:
        all_results.append(build_grid_and_run(event_time=evt))

    if ENABLE_PLOTS:
        plot_all_results(all_results)
        exported_individual = export_comparison_plots(all_results)
        exported_combined = export_combined_comparison_figures(all_results)
        print(f"Plots written to {exported_individual[0].parent}")
    else:
        print("Plotting disabled.")