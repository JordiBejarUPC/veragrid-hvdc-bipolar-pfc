from pathlib import Path
import cProfile
import sys

import numpy as np
from matplotlib import pyplot as plt

this_file = Path(__file__).resolve()
repo_root = this_file.parents[3]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import VeraGridEngine as vg
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.rms_problem_factory import build_rms_problem
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from build_and_populate_tuvalu_grid import TuvaluGridPopulator, get_technology_names, initialize_tuvalu_rms_models


def find_name_in_block(name: str, block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + list(block.mode_dict.keys()):
        if var.name == name:
            return var
    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res
    return None


def find_event_var_in_block(names: tuple[str, ...], block):
    names_l = {n.lower() for n in names}

    for var in block.event_dict.keys():
        vname = var.name.lower()
        if vname in names_l:
            return var
        if any(vname.startswith(f"{n}_") for n in names_l):
            return var

    for mdl in block.children:
        res = find_event_var_in_block(names, mdl)
        if res is not None:
            return res

    return None


def collect_event_var_names(block) -> list[str]:
    names = [var.name for var in block.event_dict.keys()]
    for mdl in block.children:
        names.extend(collect_event_var_names(mdl))
    return names


def collect_event_vars(block) -> list:
    vars_list = list(block.event_dict.keys())
    for mdl in block.children:
        vars_list.extend(collect_event_vars(mdl))
    return vars_list


def add_pv_irradiance_events(grid: vg.MultiCircuit, events_group: RmsEventsGroup) -> int:
    added = 0
    for gen in grid.get_generators():
        tech_names = [name.lower() for name in get_technology_names(gen)]
        is_pv = any("pv" in name for name in tech_names)
        if not is_pv or gen.rms_model is None:
            continue

        g_var = find_event_var_in_block(("G", "g"), gen.rms_model)
        if g_var is None:
            for candidate in collect_event_vars(gen.rms_model):
                cname = candidate.name.lower()
                if ("irr" in cname) or (cname.startswith("g") and not cname.startswith("gref")):
                    g_var = candidate
                    break

        if g_var is None:
            event_names = collect_event_var_names(gen.rms_model)
            event_names_preview = ", ".join(event_names[:10]) if event_names else "<none>"
            print(
                f"Skipping PV '{gen.name}': no irradiance event variable found. "
                f"Event vars: {event_names_preview}"
            )
            continue

        g0 = 1.0
        try:
            g0 = float(gen.rms_model.event_dict[g_var].value)
        except (TypeError, ValueError, AttributeError):
            pass

        g_target = 0.10 * g0
        for k, t_evt in enumerate([0.10, 0.12, 0.14, 0.16], start=1):
            alpha = k / 4.0
            val = (1.0 - alpha) * g0 + alpha * g_target
            grid.add_rms_event(
                RmsEvent(
                    device=gen,
                    parameter=g_var,
                    time=t_evt,
                    value=val,
                    group=events_group,
                    force_step_alignment=True,
                )
            )
            added += 1

        grid.add_rms_event(
            RmsEvent(
                device=gen,
                parameter=g_var,
                time=0.60,
                value=g0,
                group=events_group,
                force_step_alignment=True,
            )
        )
        added += 1

        print(
            f"Added irradiance events for PV '{gen.name}': G {g0:.3f} -> {g_target:.3f} pu "
            f"(0.10s-0.16s), restore at 0.60s"
        )

    return added


def plot_bus_vm_va(grid: vg.MultiCircuit, problem, t, y, output_file: Path) -> None:
    t_arr = np.asarray(t, dtype=float)
    y_arr = np.asarray(y)

    fig, (ax_vm, ax_va) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    plotted_vm = False
    plotted_va = False

    for bus in grid.buses:
        if bus.rms_model is None:
            continue

        mapping = getattr(bus.rms_model, "external_mapping", None)
        if mapping is None:
            continue

        vm_var = mapping.get(VarPowerFlowRefferenceType.Vm)
        va_var = mapping.get(VarPowerFlowRefferenceType.Va)

        if vm_var is not None:
            ax_vm.plot(t_arr, y_arr[:, problem.get_var_idx(vm_var)], label=bus.name, linewidth=1.4)
            plotted_vm = True

        if va_var is not None:
            ax_va.plot(t_arr, np.rad2deg(y_arr[:, problem.get_var_idx(va_var)]), label=bus.name, linewidth=1.4)
            plotted_va = True

    if not (plotted_vm or plotted_va):
        plt.close(fig)
        print("No AC bus Vm/Va variables found for plotting")
        return

    ax_vm.set_title("Bus voltage magnitude (Vm)")
    ax_vm.set_ylabel("Vm [pu]")
    ax_vm.grid(True, alpha=0.3)
    if plotted_vm:
        ax_vm.legend(loc="best", fontsize=8)

    ax_va.set_title("Bus voltage angle (Va)")
    ax_va.set_xlabel("Time [s]")
    ax_va.set_ylabel("Va [deg]")
    ax_va.grid(True, alpha=0.3)
    if plotted_va:
        ax_va.legend(loc="best", fontsize=8)

    fig.tight_layout()
    fig.savefig(output_file, dpi=150)
    plt.close(fig)
    print(f"Saved bus Vm/Va plot: {output_file}")


def main() -> int:
    base_grid_path = repo_root / "trunk" / "tuvalu" / "funafuti_base.veragrid"
    profiles_excel = repo_root.parent / "Tuvalu" / "data" / "profiles_and_scenarios.xlsx"
    demand_excel = repo_root.parent / "Tuvalu" / "data" / "plant_data" / "combined_output_hand_corrected.xlsx"

    print(f"Loading Tuvalu base grid: {base_grid_path}")
    grid = vg.open_file(str(base_grid_path))

    print("Populating one-step time-series profiles...")
    populator = TuvaluGridPopulator(
        grid=grid,
        profiles_and_scenarios_excel=profiles_excel,
        demand_excel=demand_excel,
        start_year=2024,
        profile_steps=1,
    )
    populator.populate()

    initialize_tuvalu_rms_models(grid)

    print("Running snapshot power flow...")
    pf_driver = vg.PowerFlowDriver(
        grid=grid,
        options=vg.PowerFlowOptions(solver_type=vg.SolverType.HELM),
    )
    pf_driver.run()
    pf_results = pf_driver.results
    print(f"Power flow converged: {pf_results.converged}")
    if not pf_results.converged:
        return 1

    if not grid.rms_events_groups:
        grid.add_rms_events_group(RmsEventsGroup(name="tuvalu_base_case"))

    events_group = grid.rms_events_groups[0]
    n_events = add_pv_irradiance_events(grid=grid, events_group=events_group)
    print(f"Total irradiance RMS events added: {n_events}")

    print("Running RMS dynamic simulation...")
    rms_options = vg.RmsOptions(
        simulation_time=1.0,
        time_step=0.01,
        max_iter=60,
        tolerance=1e-6,
        integration_method=vg.DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=vg.RmsInitializationMethod.Explicit,
    )
    problem = build_rms_problem(
        grid=grid,
        options=rms_options,
        pf_results=pf_results,
        progress_signal=None,
    )
    problem.set_events_group(rms_events_group=events_group)
    problem.reset_boundary_update_state(0.0)

    solver = BackEulerImplicitIntegration(
        problem=problem,
        t0=0.0,
        t_end=rms_options.simulation_time,
        h=rms_options.time_step,
        max_iter=rms_options.max_iter,
    )
    profile_path = this_file.parent / "profile.pstat"
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        t, y, well_init, converged = solver.simulate()
    finally:
        profiler.disable()
        profiler.dump_stats(str(profile_path))
        print(f"Saved simulation profiling stats: {profile_path}")

    print(f"RMS well initialized: {well_init}")
    print(f"RMS converged: {converged}")
    print(f"Computed RMS time samples: {len(t)}")

    if len(t) > 0 and y is not None:
        plot_path = this_file.parent / "tuvalu_rms_bus_vm_va.png"
        plot_bus_vm_va(grid=grid, problem=problem, t=t, y=y, output_file=plot_path)

    return 0 if bool(well_init and converged) else 3


if __name__ == "__main__":
    raise SystemExit(main())
