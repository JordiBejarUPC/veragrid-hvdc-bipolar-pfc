#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt

import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model

from emt_gfm_aggregated_model import build_emt_gfm_aggregated_model
from emt_gfm_model import find_name_in_block


PLOT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "emt_gfm_combinedmodels_validation_plots")


def create_grid() -> tuple[vge.MultiCircuit, vge.Generator, vge.Generator, vge.Load]:
    grid = vge.MultiCircuit(name="EMT GFM aggregated validation", Sbase=100.0, fbase=50.0)

    # Exactly the same grid as rms_gfm_combinedmodels.py
    bus1_ac = vge.Bus(name="Bus 1 (AC)", Vnom=230.0, is_slack=True)
    bus3_ac = vge.Bus(name="Bus 1_1 (AC)", Vnom=230.0)
    bus4_ac = vge.Bus(name="Bus 4 (AC)", Vnom=230.0)
    grid.add_bus(bus1_ac)
    grid.add_bus(bus3_ac)
    grid.add_bus(bus4_ac)

    gen_slack = vge.Generator(name="Generator", vset=0.98)
    gen_gfm = vge.Generator(name="GFM Generator", P=4.0, vset=1.00)
    ac_load = vge.Load(name="AC Load", P=3.0, Q=0.0)

    line13 = vge.Line(
        name="Line13",
        bus_from=bus3_ac,
        bus_to=bus1_ac,
        rate=100.0,
        r=0.01,
        x=0.05,
        b=0.0,
    )
    line34 = vge.Line(
        name="Line 3-4",
        bus_from=bus3_ac,
        bus_to=bus4_ac,
        rate=100.0,
        r=0.02,
        x=0.08,
        b=0.0,
    )

    grid.add_generator(bus=bus1_ac, api_obj=gen_slack)
    grid.add_generator(bus=bus3_ac, api_obj=gen_gfm)
    grid.add_load(bus=bus4_ac, api_obj=ac_load)
    grid.add_line(line13)
    grid.add_line(line34)
    grid.apply_all_branch_types()
    grid.add_emt_events_group(EmtEventsGroup(name="emt_gfm_combined_validation"))

    return grid, gen_slack, gen_gfm, ac_load


def trace(problem, y: np.ndarray, var_name: str, block) -> np.ndarray:
    var = find_name_in_block(var_name, block)
    if var is None or var.uid not in problem._uid2idx_vars:
        raise RuntimeError(f"Variable {var_name} is not in the solved EMT vector")
    return np.asarray(y[:, problem.get_var_idx(var)], dtype=float)


def save_plot(filename: str) -> None:
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, filename), dpi=150)
    plt.close()


def plot_results(driver: EmtSimulationDriver, gfm_model) -> None:
    results = driver.results
    problem = driver.problem
    if results is None or problem is None:
        print("Skipping plots: EMT driver did not produce results")
        return

    active_groups = np.flatnonzero(results.has_event_group_results)
    if active_groups.size == 0:
        print("Skipping plots: no active EMT event-group results")
        return

    group_idx = int(active_groups[0])
    y = np.asarray(results.values[:, :, group_idx], dtype=float)
    t = np.arange(y.shape[0], dtype=float) * driver.options.time_step

    plt.figure(figsize=(10, 6))
    plt.plot(t, trace(problem, y, "P", gfm_model), label="P")
    plt.plot(t, trace(problem, y, "Q", gfm_model), label="Q")
    plt.xlabel("Time (s)")
    plt.ylabel("Power (pu)")
    plt.title("EMT GFM Combined Model Power")
    plt.grid(True)
    plt.legend(loc="upper right")
    plt.tight_layout()
    save_plot("gfm_power.png")

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(t, trace(problem, y, "v_A", gfm_model), label="v_A")
    axes[0].plot(t, trace(problem, y, "v_B", gfm_model), label="v_B")
    axes[0].plot(t, trace(problem, y, "v_C", gfm_model), label="v_C")
    axes[0].set_ylabel("Voltage")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")

    axes[1].plot(t, trace(problem, y, "i_g_A", gfm_model), label="i_g_A")
    axes[1].plot(t, trace(problem, y, "i_g_B", gfm_model), label="i_g_B")
    axes[1].plot(t, trace(problem, y, "i_g_C", gfm_model), label="i_g_C")
    axes[1].set_ylabel("Grid current")
    axes[1].grid(True)
    axes[1].legend(loc="upper right")

    axes[2].plot(t, trace(problem, y, "i_c_A", gfm_model), label="i_c_A")
    axes[2].plot(t, trace(problem, y, "i_c_B", gfm_model), label="i_c_B")
    axes[2].plot(t, trace(problem, y, "i_c_C", gfm_model), label="i_c_C")
    axes[2].set_xlabel("Time (s)")
    axes[2].set_ylabel("Converter current")
    axes[2].grid(True)
    axes[2].legend(loc="upper right")
    fig.suptitle("EMT GFM Combined Model abc Signals")
    fig.tight_layout()
    save_plot("gfm_abc_signals.png")

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(t, trace(problem, y, "omega", gfm_model), label="omega")
    axes[0].plot(t, trace(problem, y, "V", gfm_model), label="V")
    axes[0].set_ylabel("Control states")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")

    axes[1].plot(t, trace(problem, y, "vd_g", gfm_model), label="vd_g")
    axes[1].plot(t, trace(problem, y, "vq_g", gfm_model), label="vq_g")
    axes[1].plot(t, trace(problem, y, "vd_f", gfm_model), "--", label="vd_f")
    axes[1].plot(t, trace(problem, y, "vq_f", gfm_model), "--", label="vq_f")
    axes[1].set_ylabel("dq voltage")
    axes[1].grid(True)
    axes[1].legend(loc="upper right")

    axes[2].plot(t, trace(problem, y, "id_g", gfm_model), label="id_g")
    axes[2].plot(t, trace(problem, y, "iq_g", gfm_model), label="iq_g")
    axes[2].plot(t, trace(problem, y, "id_c", gfm_model), "--", label="id_c")
    axes[2].plot(t, trace(problem, y, "iq_c", gfm_model), "--", label="iq_c")
    axes[2].set_xlabel("Time (s)")
    axes[2].set_ylabel("dq current")
    axes[2].grid(True)
    axes[2].legend(loc="upper right")
    fig.suptitle("EMT GFM Combined Model dq Signals")
    fig.tight_layout()
    save_plot("gfm_dq_signals.png")

    print(f"Saved EMT GFM combined-model plots to {PLOT_OUTPUT_DIR}")


def plot_initial_guess(problem, gfm_model) -> None:
    y = np.asarray(problem.get_x0(), dtype=float).reshape(1, -1)
    t = np.asarray([0.0], dtype=float)

    plt.figure(figsize=(8, 5))
    plt.plot(t, trace(problem, y, "P", gfm_model), "o", label="P")
    plt.plot(t, trace(problem, y, "Q", gfm_model), "o", label="Q")
    plt.xlabel("Time (s)")
    plt.ylabel("Power (pu)")
    plt.title("EMT GFM Combined Model Initial Power")
    plt.grid(True)
    plt.legend(loc="upper right")
    plt.tight_layout()
    save_plot("gfm_initial_power.png")

    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    axes[0].plot(t, trace(problem, y, "v_A", gfm_model), "o", label="v_A")
    axes[0].plot(t, trace(problem, y, "v_B", gfm_model), "o", label="v_B")
    axes[0].plot(t, trace(problem, y, "v_C", gfm_model), "o", label="v_C")
    axes[0].set_ylabel("Voltage")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")

    axes[1].plot(t, trace(problem, y, "id_g", gfm_model), "o", label="id_g")
    axes[1].plot(t, trace(problem, y, "iq_g", gfm_model), "o", label="iq_g")
    axes[1].plot(t, trace(problem, y, "id_c", gfm_model), "o", label="id_c")
    axes[1].plot(t, trace(problem, y, "iq_c", gfm_model), "o", label="iq_c")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("dq current")
    axes[1].grid(True)
    axes[1].legend(loc="upper right")
    fig.suptitle("EMT GFM Combined Model Initial Conditions")
    fig.tight_layout()
    save_plot("gfm_initial_conditions.png")

    print(f"Saved EMT GFM initialization plots to {PLOT_OUTPUT_DIR}")


def main() -> None:
    grid, gen_slack, gen_gfm, load_pcc = create_grid()

    pf_opts = vge.PowerFlowOptions(solver_type=vge.SolverType.NR, tolerance=1e-6, max_iter=30, verbose=0)
    pf = vge.power_flow(grid, pf_opts)
    print(f"Power flow converged: {pf.converged}")
    pf_for_emt = pf if pf.converged else None

    for bus in grid.buses:
        get_bus_emt_template(grid=grid, bus=bus)

    gfm_model = build_emt_gfm_aggregated_model(vf=grid.var_factory, name="vsc_gfm_park")
    set_emt_model(gen_gfm, gfm_model, grid.var_factory)

    for ln in grid.lines:
        line_model = get_pi_line_emt_template(vf=grid.var_factory).block
        set_emt_model(ln, line_model, grid.var_factory)

    gen_model = get_simple_generator_emt_template(vf=grid.var_factory).block
    set_emt_model(gen_slack, gen_model, grid.var_factory)

    load_model = get_load_ZIP_emt_template(vf=grid.var_factory).block
    set_emt_model(load_pcc, load_model, grid.var_factory)

    emt_opts = EmtOptions(
        time_step=1e-4,
        simulation_time=0.2,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=EmtInitializationMethod.Auto,
        init_newton_max_iter=40,
        verbose=1,
    )

    driver = EmtSimulationDriver(grid=grid, options=emt_opts, pf_results=pf_for_emt)
    try:
        driver.run()
        plot_results(driver=driver, gfm_model=gfm_model)
    except RuntimeError as exc:
        print(f"EMT run failed before producing time-series plots: {exc}")
        if driver.problem is not None:
            plot_initial_guess(problem=driver.problem, gfm_model=gfm_model)
        else:
            raise
    print("EMT run finished")


if __name__ == "__main__":
    main()
