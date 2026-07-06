# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

import VeraGridEngine.api as vge
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.esd1_rms_template import get_esd1_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Utils.Symbolic.block import Block


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + list(block.mode_dict.keys()):
        if var.name == name:
            return var
    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res
    return None


def create_grid() -> vge.MultiCircuit:
    grid = vge.MultiCircuit(name="ESD1 RMS validation", Sbase=100.0)

    bus_slack = vge.Bus(name="B1", Vnom=230.0, is_slack=True)
    bus_bess = vge.Bus(name="B2", Vnom=230.0)
    grid.add_bus(bus_slack)
    grid.add_bus(bus_bess)

    line = vge.Line(name="L12", bus_from=bus_slack, bus_to=bus_bess, r=0.02, x=0.08, b=0.02, rate=200.0)
    grid.add_line(line)

    gen_slack = vge.Generator(name="G_slack", P=90.0, vset=1.0)
    grid.add_generator(bus=bus_slack, api_obj=gen_slack)

    batt = vge.Battery(
        name="BESS_ESD1",
        P=20.0,
        vset=1.01,
        Enom=200.0,
        Pmin=-50.0,
        Pmax=50.0,
        min_soc=0.15,
        max_soc=0.95,
        soc=0.65,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
    )
    grid.add_battery(bus=bus_bess, api_obj=batt)

    return grid


def run_pf(grid: vge.MultiCircuit):
    pf_options = vge.PowerFlowOptions(
        solver_type=vge.SolverType.NR,
        tolerance=1e-8,
        max_iter=100,
        verbose=False,
    )
    return vge.power_flow(grid=grid, options=pf_options)


def initialize_rms_models(grid: vge.MultiCircuit):
    vf = grid.var_factory

    for bus in grid.buses:
        initialize_bus_rms(bus=bus, vf=vf)

    for line in grid.lines:
        line_model = get_line_rms_template(vfactory=vf, name=f"Line_{line.name}").block
        grid.var_factory.add_connections([line_model.in_vars[0], line_model.in_vars[1]], [line.bus_from.rms_model.out_vars[0], line.bus_from.rms_model.out_vars[1]])
        grid.var_factory.add_connections([line_model.in_vars[2], line_model.in_vars[3]], [line.bus_to.rms_model.out_vars[0], line.bus_to.rms_model.out_vars[1]])
        line_model.unify_blocks()
        line.rms_model = line_model

    slack_gen = grid.generators[0]
    slack_model = get_complete_generator_template_rms(vfactory=vf, name=slack_gen.name).block
    set_rms_model(device=slack_gen, model=slack_model, var_factory=vf)

    batt = grid.batteries[0]
    batt_model = get_esd1_rms_template(vfactory=vf, name=f"ESD1_{batt.name}").block
    set_rms_model(device=batt, model=batt_model, var_factory=vf)


def run_rms(grid: vge.MultiCircuit, pf_results):
    events_group = RmsEventsGroup(name="esd1_case")
    grid.add_rms_events_group(events_group)

    batt = grid.batteries[0]
    if batt.rms_model is not None:
        pext0_var = find_name_in_block("pext0", batt.rms_model)
        if pext0_var is not None:
            evt = RmsEvent(
                device=batt,
                parameter=pext0_var,
                time=1.0,
                value=-0.10,
                group=events_group,
            )
            grid.add_rms_event(evt)
            print("Added event: pext0 step 0.000 -> -0.200 pu at t=1.00 s")

    rms_options = vge.RmsOptions(
        simulation_time=6.0,
        time_step=0.01,
        max_iter=40,
        tolerance=1e-6,
        integration_method=vge.DynamicIntegrationMethod.DaeBackEuler,
    )

    rms_driver = vge.RmsSimulationDriver(
        grid=grid,
        options=rms_options,
        pf_results=pf_results,
        engine=vge.EngineType.VeraGrid,
    )
    rms_driver.run()
    return rms_driver.results


def plot_results(grid: vge.MultiCircuit, results, file_name: str = "esd1_rms_validation_results.png"):
    if results is None or results.values is None or len(results.time_array) == 0:
        print("No RMS samples available for plotting")
        return

    t_raw = np.array(results.time_array)
    if np.issubdtype(t_raw.dtype, np.datetime64):
        t = (t_raw - t_raw[0]) / np.timedelta64(1, "s")
        t = t.astype(float)
    else:
        t = t_raw.astype(float)

    y = results.values[:, :, 0]
    n_samples = min(len(t), y.shape[0])
    if n_samples == 0:
        print("No aligned samples available for plotting")
        return

    t_plot = t[:n_samples]
    y_plot = y[:n_samples, :]
    uid2idx = results.uid2idx

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    ax_pq, ax_soc, ax_bus = axes

    def plot_var(ax, block: Block, var_name: str, label: str) -> bool:
        var = find_name_in_block(var_name, block)
        if var is None:
            return False
        idx = uid2idx.get(var.uid)
        if idx is None:
            return False
        ax.plot(t_plot, y_plot[:, idx], label=label, linewidth=1.6)
        return True

    batt = grid.batteries[0]
    if batt.rms_model is not None:
        plot_var(ax_pq, batt.rms_model, "P_esd1", "P_esd1")
        plot_var(ax_pq, batt.rms_model, "Q_esd1", "Q_esd1")
        plot_var(ax_pq, batt.rms_model, "P_sum", "P_sum")
        plot_var(ax_soc, batt.rms_model, "Soc", "Soc")
        plot_var(ax_soc, batt.rms_model, "P_dis_av", "P_dis_av")
        plot_var(ax_soc, batt.rms_model, "P_ch_av", "P_ch_av")

    for bus in grid.buses:
        if bus.rms_model is not None:
            plot_var(ax_bus, bus.rms_model, "Vm", f"{bus.name}:Vm")

    ax_pq.set_title("ESD1 Battery Power")
    ax_pq.set_ylabel("pu")
    ax_pq.grid(True)
    ax_pq.legend(loc="upper right")

    ax_soc.set_title("ESD1 State of Charge")
    ax_soc.set_ylabel("pu")
    ax_soc.grid(True)
    ax_soc.legend(loc="upper right")

    ax_bus.set_title("Bus Voltage Magnitudes")
    ax_bus.set_xlabel("Time (s)")
    ax_bus.set_ylabel("pu")
    ax_bus.grid(True)
    ax_bus.legend(loc="upper right")

    for ax in axes:
        ax.axvline(x=1.0, color="red", linestyle=":", alpha=0.7)
        ax.set_xlim([t_plot[0], t_plot[-1]])

    plt.tight_layout()
    plt.savefig(file_name, dpi=150)
    plt.close(fig)
    print(f"Saved plot to {file_name}")


def main() -> int:
    grid = create_grid()

    pf_results = run_pf(grid=grid)
    print(f"Power flow converged: {pf_results.converged}")
    if not pf_results.converged:
        return 1

    initialize_rms_models(grid=grid)
    results = run_rms(grid=grid, pf_results=pf_results)
    well_init = bool(results.well_initialized.size > 0 and results.well_initialized.all())
    converged = bool(results.converged.size > 0 and results.converged.all())
    print(f"RMS well initialized: {results.well_initialized}")
    print(f"RMS converged: {results.converged}")

    plot_results(grid=grid, results=results)

    return 0 if (well_init and converged) else 1


if __name__ == "__main__":
    raise SystemExit(main())
