# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.templates_common_functions import set_rms_model
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod
import VeraGridEngine.api as gce


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + list(block.mode_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

    return None


def run_case(threshold: float, include_selfix: bool):
    p_branch_true = -0.08
    p_branch_false = -0.12
    q_scale = 0.2
    p_target = p_branch_false
    q_target = q_scale * p_target

    grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

    bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    for bus in grid.buses:
        initialize_bus_rms(bus, vf=grid.rms_var_factory)

    line0 = gce.Line(
        name="line 0-2",
        bus_from=bus0,
        bus_to=bus1,
        r=0.029585798816568046,
        x=0.07100591715976332,
        b=0.03,
        rate=900.0,
    )
    grid.add_line(line0)

    load = gce.Load(P=-100.0 * p_target, Q=-100.0 * q_target)
    grid.add_load(bus=bus1, api_obj=load)

    gen0 = gce.Generator(
        name="Gen0",
        P=10,
        vset=1.0,
        Snom=900,
        x1=0.86138701,
        r1=0.3,
        freq=50.0,
        M=10.0,
        D=1.0,
        omega_ref=1.0,
        Kp=1.0,
        Ki=10.0,
    )
    grid.add_generator(bus=bus0, api_obj=gen0)

    genqec_mdl = get_complete_generator_template_rms(grid.rms_var_factory).block
    line_mdl = get_line_rms_template(grid.rms_var_factory).block
    load_mdl = get_load_rms_template(grid.rms_var_factory).block

    load_mdl.set_parameter_in_model(var_name="Pl0", new_value=p_target)
    load_mdl.set_parameter_in_model(var_name="Ql0", new_value=q_target)

    omega_proc = find_name_in_block("omega", genqec_mdl)
    pl0 = find_name_in_block("Pl0", load_mdl)
    ql0 = find_name_in_block("Ql0", load_mdl)
    proc_select = Var(name="proc_select_load")

    if omega_proc is not None and pl0 is not None and ql0 is not None:
        proc_condition = (omega_proc > Const(threshold)).to_expression()
        load_mdl.mode_dict[proc_select] = Const(0.0)
        if include_selfix:
            load_mdl.procedural_logic.append(selfix(boolexpr=proc_condition, output=proc_select))
        load_mdl.event_dict[pl0] = proc_select * Const(p_branch_true) + (Const(1.0) - proc_select) * Const(p_branch_false)
        load_mdl.event_dict[ql0] = Const(q_scale) * pl0

    set_rms_model(device=gen0, model=genqec_mdl, var_factory=grid.rms_var_factory)
    set_rms_model(device=line0, model=line_mdl, var_factory=grid.rms_var_factory)
    set_rms_model(device=load, model=load_mdl, var_factory=grid.rms_var_factory)

    pf_options = gce.PowerFlowOptions(
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
    pf_results = gce.power_flow(grid, options=pf_options)

    options = RmsOptions(
        time_step=0.01,
        simulation_time=0.02,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=1000,
        verbose=0,
    )

    problem = RmsProblemDae(grid=grid, options=options, pf_results=pf_results)
    events_group = RmsEventsGroup(name=f"procedural_threshold_{threshold}")
    grid.add_rms_events_group(events_group)
    problem.set_events_group(events_group)
    solver = BackEulerImplicitIntegration(
        problem=problem,
        t0=0,
        t_end=options.simulation_time,
        h=options.time_step,
        max_iter=options.max_iter,
    )

    _, y, well_initialized, converged = solver.simulate()

    pl_var = find_name_in_block("Pl", load_mdl)
    ql_var = find_name_in_block("Ql", load_mdl)
    if pl_var is None or ql_var is None:
        raise RuntimeError("Could not find load variables Pl/Ql")

    pl_final = float(y[-1, problem.get_var_idx(pl_var)])
    ql_final = float(y[-1, problem.get_var_idx(ql_var)])
    return well_initialized, converged, pl_final, ql_final


print("RMS mode/procedural smoke test without RmsEvent")

w_a1, c_a1, pl_a1, ql_a1 = run_case(threshold=0.999, include_selfix=True)
w_a2, c_a2, pl_a2, ql_a2 = run_case(threshold=1.001, include_selfix=True)
w_b1, c_b1, pl_b1, ql_b1 = run_case(threshold=0.999, include_selfix=False)
w_b2, c_b2, pl_b2, ql_b2 = run_case(threshold=1.001, include_selfix=False)

print(f"With selfix    (omega > 0.999): well_initialized={w_a1}, converged={c_a1}, Pl={pl_a1:.6f}, Ql={ql_a1:.6f}")
print(f"With selfix    (omega > 1.001): well_initialized={w_a2}, converged={c_a2}, Pl={pl_a2:.6f}, Ql={ql_a2:.6f}")
print(f"Without selfix (omega > 0.999): well_initialized={w_b1}, converged={c_b1}, Pl={pl_b1:.6f}, Ql={ql_b1:.6f}")
print(f"Without selfix (omega > 1.001): well_initialized={w_b2}, converged={c_b2}, Pl={pl_b2:.6f}, Ql={ql_b2:.6f}")

if not (w_a1 and c_a1 and w_a2 and c_a2 and w_b1 and c_b1 and w_b2 and c_b2):
    raise RuntimeError("One RMS case failed to initialize or converge")

if np.isclose(pl_a1, pl_a2, atol=1e-6):
    raise RuntimeError("Pl did not change across thresholds with selfix enabled")

if not np.isclose(pl_b1, pl_b2, atol=1e-6):
    raise RuntimeError("Pl changed across thresholds without selfix; expected default-latched behavior")

if not np.isclose(ql_a1, 0.2 * pl_a1, atol=1e-6) or not np.isclose(ql_a2, 0.2 * pl_a2, atol=1e-6):
    raise RuntimeError("Ql did not follow Pl coupling in selfix path")

if not np.isclose(ql_b1, 0.2 * pl_b1, atol=1e-6) or not np.isclose(ql_b2, 0.2 * pl_b2, atol=1e-6):
    raise RuntimeError("Ql did not follow Pl coupling in no-selfix path")

same_threshold_true = np.isclose(pl_a1, pl_b1, atol=1e-9) and np.isclose(ql_a1, ql_b1, atol=1e-9)
same_threshold_false = np.isclose(pl_a2, pl_b2, atol=1e-9) and np.isclose(ql_a2, ql_b2, atol=1e-9)

print(f"Selfix changes result at threshold 0.999: {not same_threshold_true}")
print(f"Selfix changes result at threshold 1.001: {not same_threshold_false}")

if (not same_threshold_true) and same_threshold_false:
    print("Conclusion: selfix is active in RMS and changes retained mode values as expected.")
elif same_threshold_true and same_threshold_false:
    print("Conclusion: RMS behavior here is driven by mode_dict/event_dict only; selfix is inert.")
else:
    print("Conclusion: mixed behavior observed; inspect procedural-mode wiring.")
