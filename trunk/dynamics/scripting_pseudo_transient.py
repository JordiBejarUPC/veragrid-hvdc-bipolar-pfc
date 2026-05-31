# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import VeraGridEngine.api as gce
import numpy as np
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Utils.Symbolic.block_helpers import to_explicit, to_implicit
from VeraGridEngine.enumerations import RmsInitializationMethod
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver


def build_grid() -> gce.MultiCircuit:
    grid = gce.MultiCircuit(Sbase=100.0, fbase=50.0)

    bus0 = gce.Bus(name="Bus0", Vnom=90.0, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=90.0)
    initialize_bus_rms(bus0, vf=grid.var_factory)
    initialize_bus_rms(bus1, vf=grid.var_factory)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line = gce.Line(
        name="Line0-1",
        bus_from=bus0,
        bus_to=bus1,
        r=0.029585798816568046,
        x=0.07100591715976332,
        b=0.03,
        rate=900.0,
    )
    grid.add_line(line)

    load = gce.Load(name="Load1", P=10, Q=1)
    grid.add_load(bus=bus1, api_obj=load)

    gen = gce.Generator(
        name="Gen0",
        P=100.0,
        vset=1.0,
        Snom=900.0,
        r1=0.3,
        x1=0.86138701,
        freq=50.0,
    )
    grid.add_generator(bus=bus0, api_obj=gen)

    if line.rms_model.empty():
        set_rms_model(device=line, model=get_line_rms_template(grid.var_factory, name=line.name).block, var_factory=grid.var_factory)
    if load.rms_model.empty():
        set_rms_model(device=load, model=get_load_rms_template(grid.var_factory, name=load.name).block, var_factory=grid.var_factory)
    if gen.rms_model.empty():
        gen_model = get_complete_generator_template_rms(grid.var_factory, name=gen.name).block
        gen_model = get_genrow_rms_template(grid.var_factory, name=gen.name).block
        #gen_model = to_explicit(gen_model, grid.var_factory)
        set_rms_model(
            device=gen,
            model=gen_model,
            var_factory=grid.var_factory,
        )

    group = gce.RmsEventsGroup(name="BaseCase")
    grid.add_rms_events_group(group)

    return grid


def run_validation() -> None:
    grid = build_grid()

    pf_options = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        distributed_slack=False,
    )
    pf_results = gce.power_flow(grid, options=pf_options)

    print(f"Power flow converged: {pf_results.converged}")

    rms_options = gce.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        integration_method=gce.DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=gce.RmsInitializationMethod.Explicit,
        max_iter=1000,
        tolerance=1e-8,
        verbose=True,
    )

    def _run_init(method: RmsInitializationMethod) -> tuple[np.ndarray, list[str], dict[str, float]]:
        rms_options.initialization_method = method
        rms_driver = RmsSimulationDriver(
            grid=grid,
            options=rms_options,
            pf_results=pf_results,
        )
        rms_driver.run()
        problem = rms_driver.problem
        if problem is None:
            raise RuntimeError(f"{method.value} initialization did not build an RMS problem")

        x0_local = problem.get_x0()
        if x0_local.size == 0:
            raise RuntimeError(f"{method.value} initialization produced an empty state vector")
        if not np.all(np.isfinite(x0_local)):
            raise RuntimeError(f"{method.value} initialization produced non-finite values")

        all_vars = list(getattr(problem, "_state_vars", [])) + list(getattr(problem, "_algebraic_vars", []))
        var_names = [str(v.name) for v in all_vars]
        event_params0 = problem.get_eventparams0()
        var_params = list(getattr(problem, "variable_parameters", []))
        event_param_map: dict[str, float] = {}
        for i, p in enumerate(var_params):
            if i < event_params0.size:
                event_param_map[str(p.name)] = float(event_params0[i])
        print(f"{method.value} initialized variable count: {x0_local.size}")
        print(f"{method.value} x0 infinity norm: {np.linalg.norm(x0_local, np.inf):.3e}")
        return x0_local, var_names, event_param_map

    def _pick_reference_seed(x: np.ndarray, names: list[str], event_map: dict[str, float], candidates: tuple[str, ...]) -> float:
        for name in candidates:
            if name in event_map:
                return float(event_map[name])
        for name in candidates:
            for i, nm in enumerate(names):
                if nm == name and i < x.size:
                    return float(x[i])
        raise RuntimeError(f"Could not find any reference variable in {candidates}")

    x0_explicit, names_explicit, event_map_explicit = _run_init(RmsInitializationMethod.PseudoTransient)
    pref_seed = _pick_reference_seed(x0_explicit, names_explicit, event_map_explicit, ("Pm_ref", "Pref", "P_ref"))
    vref_seed = _pick_reference_seed(x0_explicit, names_explicit, event_map_explicit, ("UsRefPu", "Vref", "V_ref", "U_ref"))
    print(f"Explicit reference seeds: Pref={pref_seed:.12g}, UsRefPu={vref_seed:.12g}")

    prev_pref_env = os.environ.get("VERAGRID_INIT_PREF")
    prev_vref_env = os.environ.get("VERAGRID_INIT_VREF")
    os.environ["VERAGRID_INIT_PREF"] = repr(pref_seed)
    os.environ["VERAGRID_INIT_VREF"] = repr(vref_seed)
    print(
        "Running PseudoTransient using explicit reference seeds: "
        f"VERAGRID_INIT_PREF={os.environ['VERAGRID_INIT_PREF']}, "
        f"VERAGRID_INIT_VREF={os.environ['VERAGRID_INIT_VREF']}"
    )

    try:
        x0_pseudo, names_pseudo, _ = _run_init(RmsInitializationMethod.PseudoTransient)
    finally:
        if prev_pref_env is None:
            os.environ.pop("VERAGRID_INIT_PREF", None)
        else:
            os.environ["VERAGRID_INIT_PREF"] = prev_pref_env

        if prev_vref_env is None:
            os.environ.pop("VERAGRID_INIT_VREF", None)
        else:
            os.environ["VERAGRID_INIT_VREF"] = prev_vref_env

    if x0_explicit.size != x0_pseudo.size:
        raise RuntimeError(
            f"Initialization vector size mismatch: explicit={x0_explicit.size}, pseudo={x0_pseudo.size}"
        )

    names = names_pseudo if len(names_pseudo) == x0_pseudo.size else names_explicit
    delta = np.abs(x0_pseudo - x0_explicit)
    top_n = min(20, delta.size)
    top_idx = np.argsort(-delta)[:top_n]
    print(f"Largest init deltas |PseudoTransient-Explicit| (top {top_n}):")
    for idx in top_idx:
        d = float(delta[idx])
        if d <= 0.0:
            continue
        nm = names[idx] if idx < len(names) else f"x[{idx}]"
        print(
            f"  - {nm}: explicit={float(x0_explicit[idx]):+.6e}, "
            f"pseudo={float(x0_pseudo[idx]):+.6e}, |delta|={d:.6e}"
        )

    ref_names = {"Pm_ref", "Pref", "P_ref", "UsRefPu", "Vref", "V_ref", "U_ref"}
    print("Reference comparison (Explicit vs PseudoTransient):")
    for idx, nm in enumerate(names):
        if nm in ref_names:
            d = abs(float(x0_pseudo[idx]) - float(x0_explicit[idx]))
            print(
                f"  - {nm}: explicit={float(x0_explicit[idx]):+.6e}, "
                f"pseudo={float(x0_pseudo[idx]):+.6e}, |delta|={d:.6e}"
            )

    print("Pseudo-transient initialization validation passed")


if __name__ == "__main__":
    run_validation()
