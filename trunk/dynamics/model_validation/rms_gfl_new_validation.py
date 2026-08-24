#!/usr/bin/env python3
"""
Validation case for the experimental ``vsc_gfl_new`` RMS template.

This script intentionally keeps the original ``rms_gfl_validation`` case
structure, but swaps the transformer-coupled GFL builder to the experimental
implementation and applies the matching reactive-power sign convention.
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

import VeraGridEngine.api as vge
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.enumerations import DynamicIntegrationMethod, VarPowerFlowReferenceType
from VeraGridEngine.Templates.Rms.vsc_gfl_new import TrafoGflBuild

import rms_gfl_validation as base_validation


def apply_new_gfl_reactive_convention(grid: vge.MultiCircuit, pf_results: object) -> None:
    """
    Apply the ``vsc_gfl_new`` reactive-power sign convention.

    ``vsc_gfl_new`` uses ``Qt_vsc - Q = 0``. Therefore the transformer GFL
    controller reference must be initialized as ``Q_ref = +Qt`` instead of the
    legacy ``Q_ref = -Qt`` convention used by ``vsc_gfl``.

    :param grid: Circuit with RMS models already assigned.
    :param pf_results: Power-flow result object used for RMS initialization.
    :return: None.
    """
    trafo = grid.transformers2w[0]
    branch_list = list(grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True))

    if trafo in branch_list:
        branch_idx: int = branch_list.index(trafo)
        qt_pf: float = float(pf_results.St[branch_idx].imag / grid.Sbase)
        qt_var = trafo.rms_model.external_mapping[VarPowerFlowReferenceType.Qt]
        trafo.rms_model.init_eqs[qt_var] = grid.var_factory.add_const(qt_pf)

        q_ref_var = base_validation.find_name_in_block('Q_ref', trafo.rms_model)
        if q_ref_var is not None:
            base_validation.set_event_in_block(q_ref_var, qt_pf, grid.var_factory, trafo.rms_model)
        else:
            pass
    else:
        raise RuntimeError("Transformer was not found in the branch list")


def add_small_irradiance_dip(grid: vge.MultiCircuit) -> None:
    """
    Add a small temporary PV irradiance dip and recovery event.

    :param grid: Circuit with the DC source RMS model already assigned.
    :return: None.
    """
    events_group = RmsEventsGroup(name="vsc_gfl_new_validation")
    grid.add_rms_events_group(events_group)

    dc_gen = None
    for gen in grid.generators:
        if gen.bus.is_dc:
            dc_gen = gen
        else:
            pass

    if dc_gen is not None and dc_gen.rms_model is not None:
        g_var = base_validation.find_name_in_block('G', dc_gen.rms_model)
        if g_var is not None:
            ramp_times: list[float] = [0.10, 0.12, 0.14, 0.16, 0.18, 0.20]
            ramp_values: list[float] = [990.0, 970.0, 950.0, 970.0, 990.0, 1000.0]
            for event_idx in range(len(ramp_times)):
                event = RmsEvent(
                    device=dc_gen,
                    parameter=g_var,
                    time=ramp_times[event_idx],
                    value=ramp_values[event_idx],
                    group=events_group,
                )
                grid.add_rms_event(event)
        else:
            pass
    else:
        pass


def run_rms_simulation(grid: vge.MultiCircuit, pf_results: object) -> object:
    """
    Run the RMS validation simulation without reusing the legacy event builder.

    :param grid: Circuit with initialized RMS models and events.
    :param pf_results: Power-flow results used by the RMS driver.
    :return: RMS results object produced by the driver.
    """
    rms_options = vge.RmsOptions(
        simulation_time=10,
        time_step=0.01,
        max_iter=30,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
    )
    rms_driver = vge.RmsSimulationDriver(
        grid=grid,
        options=rms_options,
        pf_results=pf_results,
        engine=vge.EngineType.VeraGrid,
    )
    rms_driver.run()
    return rms_driver.results


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line options for the validation scenario.

    :return: Parsed command-line namespace.
    """
    parser = argparse.ArgumentParser(description="Validate the experimental vsc_gfl_new RMS template")
    parser.add_argument(
        "--dip",
        action="store_true",
        help="Apply a small temporary irradiance dip and recovery event",
    )
    return parser.parse_args()


def main() -> None:
    """
    Execute the ``vsc_gfl_new`` validation scenario.

    :return: None.
    """
    base_validation.TrafoGflBuild = TrafoGflBuild

    grid = base_validation.create_grid_2()
    pf_results = base_validation.run_power_flow(grid, "Grid 2 - vsc_gfl_new")

    base_validation.print_vsc_pf_loss_consistency(grid, pf_results)
    base_validation.initialize_grid2_rms_models(grid, pf_results)
    apply_new_gfl_reactive_convention(grid, pf_results)
    base_validation.print_gfl_init_consistency(grid, pf_results)
    base_validation.print_trafo_powerflow_equation_consistency(grid, pf_results)

    args = parse_arguments()
    if bool(args.dip):
        add_small_irradiance_dip(grid)
    else:
        grid.add_rms_events_group(RmsEventsGroup(name="vsc_gfl_new_validation_no_event"))

    results = run_rms_simulation(grid, pf_results)
    print(f"  vsc_gfl_new RMS simulation complete (converged={results.converged})")
    base_validation.plot_rms_results(grid, results)


if __name__ == "__main__":
    main()
