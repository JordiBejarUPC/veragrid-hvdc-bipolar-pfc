# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

import VeraGridEngine.api as vge
import numpy as np
import matplotlib.pyplot as plt
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.pvd1_rms_template import get_pvd1_complete_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.templates_common_functions import set_rms_model
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Simulations.Rms.rms_problem_factory import build_rms_problem
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + list(block.mode_dict.keys()):
        if var.name == name:
            return var
    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res
    return None


def build_constant_pq_generator_model(vf, name: str) -> Block:
    vm = vf.add_var(f"Vm_{name}", VarPowerFlowRefferenceType.Vm)
    va = vf.add_var(f"Va_{name}", VarPowerFlowRefferenceType.Va)
    p = vf.add_var(f"P_{name}")
    q = vf.add_var(f"Q_{name}")
    p0 = vf.add_var(f"P0_{name}")
    q0 = vf.add_var(f"Q0_{name}")

    return Block(
        algebraic_eqs=[p - p0, q - q0],
        algebraic_vars=[p, q],
        in_vars=[vm, va],
        init_eqs={p0: p, q0: q},
        event_dict={p0: vf.add_const(None), q0: vf.add_const(None)},
        external_mapping={
            VarPowerFlowRefferenceType.Vm: vm,
            VarPowerFlowRefferenceType.Va: va,
            VarPowerFlowRefferenceType.P: p,
            VarPowerFlowRefferenceType.Q: q,
        },
        out_vars=[p, q],
    )


def create_grid() -> vge.MultiCircuit:
    grid = vge.MultiCircuit(name="PVD1 RMS validation", Sbase=100.0)

    bus_slack = vge.Bus(name="B1", Vnom=230.0, is_slack=True)
    bus_pv = vge.Bus(name="B2", Vnom=230.0)

    grid.add_bus(bus_slack)
    grid.add_bus(bus_pv)

    line = vge.Line(name="L12", bus_from=bus_slack, bus_to=bus_pv, r=0.02, x=0.08, b=0.02, rate=200.0)
    grid.add_line(line)

    gen_slack = vge.Generator(name="G_slack", P=80.0, vset=1.0)
    grid.add_generator(bus=bus_slack, api_obj=gen_slack)

    gen_pv = vge.Generator(name="PV_PVD1", P=80.0, vset=1.01)
    grid.add_generator(bus=bus_pv, api_obj=gen_pv)

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
        line_model.connect([line_model.in_vars[0], line_model.in_vars[1]], [line.bus_from.rms_model.out_vars[0], line.bus_from.rms_model.out_vars[1]])
        line_model.connect([line_model.in_vars[2], line_model.in_vars[3]], [line.bus_to.rms_model.out_vars[0], line.bus_to.rms_model.out_vars[1]])
        line_model.unify_blocks()
        line.rms_model = line_model

    slack_gen = grid.generators[0]
    slack_model = get_complete_generator_template_rms(vfactory=vf, name=slack_gen.name).block
    set_rms_model(device=slack_gen, model=slack_model, var_factory=vf)

    pv_gen = grid.generators[1]
    pvd1_model = get_pvd1_complete_rms_template(vfactory=vf, name=f"PVD1_{pv_gen.name}").block
    pvd1_model.connect([pvd1_model.in_vars[0], pvd1_model.in_vars[1]], [pv_gen.bus.rms_model.out_vars[0], pv_gen.bus.rms_model.out_vars[1]])
    pvd1_model.unify_blocks()
    pv_gen.rms_model = pvd1_model


def run_rms(grid: vge.MultiCircuit, pf_results):
    events_group = RmsEventsGroup(name="pvd1_base_case")
    grid.add_rms_events_group(events_group)

    pv_gen = grid.generators[1]
    if pv_gen.rms_model is not None:
        pmx_var = find_name_in_block('pmx', pv_gen.rms_model)
        if pmx_var is not None:
            p0 = 9999.0
            p1 = 0.79
            evt = RmsEvent(
                device=pv_gen,
                parameter=pmx_var,
                time=0.20,
                value=p1,
                group=events_group,
            )
            grid.add_rms_event(evt)
            print(f"Added event: pmx step {p0:.3f} -> {p1:.3f} pu at t=0.20 s")

    rms_options = vge.RmsOptions(
        simulation_time=1.0,
        time_step=0.001,
        max_iter=30,
        tolerance=1e-6,
        integration_method=vge.DynamicIntegrationMethod.DaeBackEuler,
    )

    def compare_jacobian(tag: str, t_eval: float):
        problem = build_rms_problem(grid=grid, options=rms_options, pf_results=pf_results, progress_signal=None)
        problem.set_events_group(rms_events_group=events_group)
        problem.reset_boundary_update_state(0.0)

        x = problem.get_x0()
        xn = x.copy()
        dx_last = np.zeros(problem.get_diff_var_number(), dtype=float)
        h = rms_options.time_step

        if t_eval > 0.0:
            problem.update_variable_params(t_eval)
            problem.update(t_eval, x, problem._variable_parameters_values)

        be = BackEulerImplicitIntegration(problem=problem, t0=0.0, t_end=rms_options.simulation_time, h=h, max_iter=rms_options.max_iter)

        dx = problem.get_dx(x, xn, dx_last, h)
        jc = be._jacobian_implicit(x=x, dx=dx, h=h)
        jc_dense = jc.toarray() if hasattr(jc, "toarray") else np.array(jc)

        n = x.size
        jn = np.zeros_like(jc_dense)
        eps = 1e-7

        def rhs_with_consistent_dx(x_eval: np.ndarray) -> np.ndarray:
            dx_eval = problem.get_dx(x_eval, xn, dx_last, h)
            return be._rhs_implicit(x=x_eval, dx=dx_eval, xn=xn, h=h)

        for j in range(n):
            xp = x.copy()
            xm = x.copy()
            xp[j] += eps
            xm[j] -= eps
            fp = rhs_with_consistent_dx(xp)
            fm = rhs_with_consistent_dx(xm)
            jn[:, j] = (fp - fm) / (2.0 * eps)

        diff = jc_dense - jn
        abs_diff = np.abs(diff)
        max_abs = float(np.max(abs_diff))
        rel = float(max_abs / (np.max(np.abs(jn)) + 1e-12))
        i_max, j_max = np.unravel_index(int(np.argmax(abs_diff)), abs_diff.shape)
        row_eqs = problem._state_eqs + problem._algebraic_eqs
        col_vars = problem._state_vars + problem._algebraic_vars

        print(f"Jacobian check [{tag}] at t={t_eval:.3f}s: max_abs_diff={max_abs:.3e}, rel={rel:.3e}")
        print(
            "  worst entry: "
            f"row={i_max} ({row_eqs[i_max]}), "
            f"col={j_max} ({col_vars[j_max].name}), "
            f"compiled={jc_dense[i_max, j_max]:.3e}, fd={jn[i_max, j_max]:.3e}, "
            f"abs_diff={abs_diff[i_max, j_max]:.3e}"
        )

        top_n = 8
        print(f"  top {top_n} |compiled-fd| entries:")
        flat_idx = np.argsort(abs_diff.ravel())[::-1][:top_n]
        for flat_k in flat_idx:
            i, j = np.unravel_index(int(flat_k), abs_diff.shape)
            print(
                "    "
                f"[{i:3d},{j:3d}] eq=({row_eqs[i]}) var=({col_vars[j].name}) "
                f"compiled={jc_dense[i, j]: .3e} fd={jn[i, j]: .3e} "
                f"abs_diff={abs_diff[i, j]: .3e}"
            )

    #compare_jacobian(tag="pre-event", t_eval=0.0)
    #compare_jacobian(tag="at-event", t_eval=0.2)

    rms_driver = vge.RmsSimulationDriver(
        grid=grid,
        options=rms_options,
        pf_results=pf_results,
        engine=vge.EngineType.VeraGrid,
    )
    rms_driver.run()
    return rms_driver.results


def plot_pvd1_and_bus_results(grid: vge.MultiCircuit, results, file_name: str = "pvd1_rms_validation_results.png"):
    if results is None or results.values is None or len(results.time_array) == 0:
        print("No RMS samples available for plotting")
        return

    t_raw = np.array(results.time_array)
    if np.issubdtype(t_raw.dtype, np.datetime64):
        t = (t_raw - t_raw[0]) / np.timedelta64(1, 's')
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

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    ax_pvd1, ax_bus = axes

    def plot_var(ax, block: Block, var_name: str, label: str) -> bool:
        if block is None:
            return False
        var = find_name_in_block(var_name, block)
        if var is None:
            return False
        idx = uid2idx.get(var.uid)
        if idx is None:
            return False
        ax.plot(t_plot, y_plot[:, idx], label=label, linewidth=1.6)
        return True

    plotted_pvd1 = False
    pv_gen = grid.generators[1] if len(grid.generators) > 1 else None
    if pv_gen is not None and pv_gen.rms_model is not None:
        plotted_pvd1 |= plot_var(ax_pvd1, pv_gen.rms_model, 'P_pvd1', 'P_pvd1')
        plotted_pvd1 |= plot_var(ax_pvd1, pv_gen.rms_model, 'Q_pvd1', 'Q_pvd1')
        plotted_pvd1 |= plot_var(ax_pvd1, pv_gen.rms_model, 'P_sum', 'P_sum')
        plotted_pvd1 |= plot_var(ax_pvd1, pv_gen.rms_model, 'Q_sum', 'Q_sum')
        plotted_pvd1 |= plot_var(ax_pvd1, pv_gen.rms_model, 'Ip_cmd', 'Ip_cmd')
        plotted_pvd1 |= plot_var(ax_pvd1, pv_gen.rms_model, 'Iq_cmd', 'Iq_cmd')
        plotted_pvd1 |= plot_var(ax_pvd1, pv_gen.rms_model, 'F_trip', 'F_trip')
        plotted_pvd1 |= plot_var(ax_pvd1, pv_gen.rms_model, 'V_trip', 'V_trip')

    plotted_bus = False
    for bus in grid.buses:
        if bus.rms_model is None:
            continue
        plotted_bus |= plot_var(ax_bus, bus.rms_model, 'Vm', f'{bus.name}:Vm')
        plotted_bus |= plot_var(ax_bus, bus.rms_model, 'Va', f'{bus.name}:Va')

    if plotted_pvd1:
        ax_pvd1.set_title('PVD1 Dynamic Variables')
        ax_pvd1.set_ylabel('pu')
        ax_pvd1.grid(True)
        ax_pvd1.legend(loc='upper right', ncol=2)

    if plotted_bus:
        ax_bus.set_title('Bus Variables')
        ax_bus.set_ylabel('pu / rad')
        ax_bus.set_xlabel('Time (s)')
        ax_bus.grid(True)
        ax_bus.legend(loc='upper right', ncol=2)

    for ax in axes:
        ax.axvline(x=0.2, color='red', linestyle=':', alpha=0.7)
        ax.set_xlim([t_plot[0], t_plot[-1]])

    plt.tight_layout()
    plt.show()
    plt.close(fig)


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
    plot_pvd1_and_bus_results(grid=grid, results=results)

    return 0 if (well_init and converged) else 1


if __name__ == "__main__":
    raise SystemExit(main())
