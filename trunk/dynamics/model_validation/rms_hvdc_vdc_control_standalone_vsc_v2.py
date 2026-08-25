#!/usr/bin/env python3
"""Point-to-point HVDC RMS validation case using explicit-state VSCs."""

from __future__ import annotations

from pathlib import Path

import numpy as np

import VeraGridEngine.api as vge
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Templates.Rms.dc_line_rms_template_v2 import build_dc_line_rms_v2
from VeraGridEngine.Templates.Rms.hvdc_vsc_gfl_rms_template_v2 import build_hvdc_vsc_gfl_rms
from VeraGridEngine.Templates.Rms.transformer_rms_template import get_transformer2w_rms
from VeraGridEngine.Templates.Rms.voltage_source_template import VoltageSourceBuild
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    RmsInitializationMethod,
    VarPowerFlowReferenceType,
)
from trunk.dynamics.model_validation import rms_hvdc_vdc_control_standalone_vsc as base_case


def initialize_rms_models(grid: MultiCircuit) -> None:
    """Assign the explicit-state RMS models used by the v2 HVDC case.

    :param grid: Static HVDC circuit whose buses and devices receive RMS models.
    :return: None.
    """
    var_factory: VarFactory = grid.var_factory

    # Bus shells provide the external voltage variables consumed by every
    # device model. They must exist before device-to-bus connections are added.
    bus: Bus
    for bus in grid.buses:
        initialize_bus_rms(bus=bus, vf=var_factory)

    # The two AC systems are represented by stiff voltage sources.
    generator: Generator
    for generator in grid.generators:
        generator_model: Block = VoltageSourceBuild(var_factory, name=generator.name).block
        set_rms_model(device=generator, model=generator_model, var_factory=var_factory)

    # Each VSC owns one complete explicit-state converter model. The DC and AC
    # terminal mappings are connected explicitly because the branch helper is
    # intended primarily for symmetric AC branches.
    vsc: VSC
    for vsc in grid.vsc_devices:
        vsc_model: Block = build_hvdc_vsc_gfl_rms(
            vfactory=var_factory,
            name=vsc.name,
            control1=vsc.control1,
            control2=vsc.control2,
        ).block
        vsc.rms_model = vsc_model
        var_factory.add_connections(
            list((
                vsc_model.external_mapping[VarPowerFlowReferenceType.Vmt],
                vsc_model.external_mapping[VarPowerFlowReferenceType.Vat],
                vsc_model.external_mapping[VarPowerFlowReferenceType.Vdc],
            )),
            list((
                vsc.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Vm],
                vsc.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Va],
                vsc.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc],
            )),
        )

    # Coupling transformers remain passive; all converter controls stay on the
    # VSC device and are therefore editable independently in the GUI.
    transformer: Transformer2W
    for transformer in grid.transformers2w:
        transformer_model: Block = get_transformer2w_rms(vf=var_factory).block
        transformer.rms_model = transformer_model
        transformer_mapping: dict[VarPowerFlowReferenceType, Var | None] = transformer_model.external_mapping
        var_factory.add_connections(
            list((
                transformer_mapping[VarPowerFlowReferenceType.Vmf],
                transformer_mapping[VarPowerFlowReferenceType.Vaf],
                transformer_mapping[VarPowerFlowReferenceType.Vmt],
                transformer_mapping[VarPowerFlowReferenceType.Vat],
            )),
            list((
                transformer.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Vm],
                transformer.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Va],
                transformer.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Vm],
                transformer.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Va],
            )),
        )

    # The DC line uses an ordinary current state. If_dc, Pf and Pt are left to
    # the power-flow initializer and are intentionally absent from init_eqs.
    dc_line: DcLine = grid.dc_lines[0]
    dc_line_model: Block = build_dc_line_rms_v2(
        vfactory=var_factory,
        name=dc_line.name,
        resistance=dc_line.R,
        inductance=0.05,
    ).block
    dc_line.rms_model = dc_line_model
    set_rms_model(device=dc_line, model=dc_line_model, var_factory=var_factory)
    var_factory.add_connections(
        list((
            dc_line_model.external_mapping[VarPowerFlowReferenceType.Vmf],
            dc_line_model.external_mapping[VarPowerFlowReferenceType.Vmt],
        )),
        list((
            dc_line.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc],
            dc_line.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc],
        )),
    )


def run_simulation(
        simulation_time: float = 30.0,
        time_step: float = 0.002,
        p_event_time: float = 5.0,
        p_step_pu: float = -0.01,
) -> tuple[MultiCircuit, PowerFlowResults, RmsResults, list[str], str]:
    """Build, simulate, plot and serialize the explicit-state HVDC case.

    The tolerance matches the practical-session requirement. Keeping it at
    ``1e-6`` prevents the explicit PI states from appearing numerically frozen.

    :param simulation_time: RMS simulation duration in seconds.
    :param time_step: Backward-Euler step in seconds.
    :param p_event_time: Time of the VSC2 active-power-reference step.
    :param p_step_pu: Increment applied to the initialized VSC2 reference.
    :return: Grid, power-flow results, RMS results, plot paths and grid path.
    """
    grid: MultiCircuit = base_case.create_grid()
    power_flow_results: PowerFlowResults = base_case.run_power_flow(grid)
    if power_flow_results.converged:
        pass
    else:
        raise RuntimeError("RMS HVDC power flow did not converge")

    initialize_rms_models(grid=grid)
    event_group: RmsEventsGroup = RmsEventsGroup(name="HVDC RMS Vdc control")
    grid.add_rms_events_group(event_group)
    active_power_reference: Var | None = base_case.find_name_in_block(
        name="P_ref",
        block=grid.vsc_devices[1].rms_model,
    )
    if active_power_reference is None:
        raise RuntimeError("Could not find the VSC2 P_ref event variable")
    else:
        pass

    initial_active_power: float = -float(np.real(power_flow_results.St_vsc[1]) / grid.Sbase)
    grid.add_rms_event(RmsEvent(
        device=grid.vsc_devices[1],
        parameter=active_power_reference,
        time=p_event_time,
        value=initial_active_power + p_step_pu,
        group=event_group,
    ))

    options: vge.RmsOptions = vge.RmsOptions(
        simulation_time=simulation_time,
        time_step=time_step,
        max_iter=80,
        tolerance=1.0e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
    )
    driver: vge.RmsSimulationDriver = vge.RmsSimulationDriver(
        grid=grid,
        options=options,
        pf_results=power_flow_results,
    )
    driver.run()
    if driver.results is None:
        raise RuntimeError("RMS simulation did not produce results")
    else:
        rms_results: RmsResults = driver.results

    script_directory: Path = Path(__file__).resolve().parent
    output_directory: Path = script_directory / "rms_hvdc_vdc_control_standalone_vsc_v2_plots"
    plot_paths: list[str] = base_case.save_plots(
        grid=grid,
        results=rms_results,
        output_dir=str(output_directory),
        p_event_time=p_event_time,
    )
    grid_path: Path = script_directory / "rms_hvdc_vdc_control_standalone_vsc_v2.veragrid"
    vge.save_file(grid=grid, filename=str(grid_path))
    return grid, power_flow_results, rms_results, plot_paths, str(grid_path)


if __name__ == "__main__":
    _, power_flow, rms, plots, saved_grid = run_simulation()
    print(f"Power flow converged: {power_flow.converged}")
    print(f"RMS converged: {rms.converged}")
    print(f"Grid saved to: {saved_grid}")
    for plot_path in plots:
        print(f"Plot saved to: {plot_path}")
else:
    pass
