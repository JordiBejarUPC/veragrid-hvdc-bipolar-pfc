# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Point-to-point HVDC RMS validation case using explicit-state VSCs."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from typing import Optional

import VeraGridEngine.api as vge
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Injections.generator import Generator
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
    ConverterControlType,
    DynamicIntegrationMethod,
    RmsInitializationMethod,
    SolverType,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict):
        if var.name == name:
            return var
    for child in block.children:
        result = find_name_in_block(name, child)
        if result is not None:
            return result
    return None

def save_plots(grid, results, output_dir: str, p_event_time: float) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    t = np.asarray(results.time_array)
    if np.issubdtype(t.dtype, np.datetime64):
        t = ((t - t[0]) / np.timedelta64(1, "s")).astype(float)
    else:
        t = t.astype(float)

    paths = []
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for bus, label in ((grid.dc_lines[0].bus_from, "Vdc bus 1"), (grid.dc_lines[0].bus_to, "Vdc bus 2")):
        trace = values_for(results, bus.rms_model, "Vdc")
        if trace is not None:
            axes[0].plot(t, trace, label=label)
    axes[0].set_ylabel("Voltage [pu]")

    for vsc in grid.vsc_devices:
        for name in ("Pf_vsc", "Pt"):
            trace = values_for(results, vsc.rms_model, name)
            if trace is not None:
                axes[1].plot(t, trace, label=f"{vsc.name} {name}")
    dc_line = grid.dc_lines[0]
    vdc_from = values_for(results, dc_line.bus_from.rms_model, "Vdc")
    vdc_to = values_for(results, dc_line.bus_to.rms_model, "Vdc")
    idc = values_for(results, dc_line.rms_model, "If_dc")
    if vdc_from is not None and vdc_to is not None and idc is not None:
        axes[1].plot(t, vdc_from * idc, "--", linewidth=1.8, label="Pdc sending = Vdc1·Idc")
        axes[1].plot(t, vdc_to * idc, "--", linewidth=1.8, label="Pdc receiving = Vdc2·Idc")
    axes[1].axvline(p_event_time, color="k", linestyle=":", label="VSC2 Pdc step")
    axes[1].set_ylabel("Power [pu]")

    line = grid.dc_lines[0]
    for name in ("If_dc", "Pf", "Pt"):
        trace = values_for(results, line.rms_model, name)
        if trace is not None:
            axes[2].plot(t, trace, label=name)
    axes[2].set_ylabel("DC line [pu]")
    axes[2].set_xlabel("Time [s]")
    for ax in axes:
        ax.grid(True)
        ax.legend(loc="best")
    fig.tight_layout()
    path = os.path.join(output_dir, "hvdc_vdc_control_rms.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    paths.append(path)

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for ax, bus, title in zip(axes, (grid.buses[0], grid.buses[-1]), ("Grid 1", "Grid 2")):
        for name in ("Vm", "Va"):
            trace = values_for(results, bus.rms_model, name)
            if trace is not None:
                ax.plot(t, trace, label=name)
        ax.set_title(f"{title} RMS bus voltage")
        ax.grid(True)
        ax.legend(loc="best")
    axes[-1].set_xlabel("Time [s]")
    fig.tight_layout()
    path = os.path.join(output_dir, "hvdc_ac_bus_voltages_rms.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    paths.append(path)
    return paths

def values_for(results, block: Block, name: str) -> Optional[np.ndarray]:
    var = find_name_in_block(name, block)
    idx = None if var is None else results.uid2idx.get(var.uid)
    return None if idx is None else np.asarray(results.values[:, idx, 0], dtype=float)


# editable parameters of the simulation
simulation_time: float = 30.0
time_step: float = 0.002
p_event_time: float = 5.0
p_step_pu: float = -0.01

# ----------------------------------------------------------------------------------------------------------------------
# CREATE GRID
# ----------------------------------------------------------------------------------------------------------------------

sbase = 100.0
ac_kv = 90.0
dc_kv = 145.0
zbase_ac = ac_kv * ac_kv / sbase
omega = 2.0 * np.pi * 50.0

grid = vge.MultiCircuit(name="Point-to-point HVDC RMS Vdc-control example", Sbase=sbase, fbase=50.0)
ac_grid_1 = vge.Bus(name="Bus_Grid_1", Vnom=ac_kv, is_slack=True)
ac_vsc_1 = vge.Bus(name="Bus_VSC_1", Vnom=ac_kv)
dc_1 = vge.Bus(name="Bus_DC_1", Vnom=dc_kv, is_dc=True)
dc_2 = vge.Bus(name="Bus_DC_2", Vnom=dc_kv, is_dc=True)
ac_vsc_2 = vge.Bus(name="Bus_VSC_2", Vnom=ac_kv)
ac_grid_2 = vge.Bus(name="Bus_Grid_2", Vnom=ac_kv, is_slack=True)
for bus in (ac_grid_1, ac_vsc_1, dc_1, dc_2, ac_vsc_2, ac_grid_2):
    grid.add_bus(bus)

grid_r_pu = (4.8 * 0.669) / zbase_ac
grid_x_pu = omega * (0.052 * 0.669) / zbase_ac
for idx, bus in enumerate((ac_grid_1, ac_grid_2), 1):
    grid.add_generator(bus, vge.Generator(
        name=f"Generator_Grid_{idx}", P=0.0, vset=1.0, Snom=sbase,
        freq=50.0, r1=grid_r_pu, x1=grid_x_pu,
    ))

# TrafoGFL is the RMS converter control/electrical interface.
for idx, bus_vsc, bus_grid in ((1, ac_vsc_1, ac_grid_1), (2, ac_vsc_2, ac_grid_2)):
    grid.add_transformer2w(vge.Transformer2W(
        name=f"TrafoGFL_{idx}", bus_from=bus_vsc, bus_to=bus_grid,
        rate=sbase, r=0.01, x=0.05,
    ))

vsc_1 = vge.VSC(
    name="VSC_1", bus_from=dc_1, bus_to=ac_vsc_1, rate=sbase,
    control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Qac,
    control1_val=1.0, control2_val=0.0,
)
vsc_2 = vge.VSC(
    name="VSC_2", bus_from=dc_2, bus_to=ac_vsc_2, rate=sbase,
    control1=ConverterControlType.Pdc, control2=ConverterControlType.Qac,
    # RMS DC buses are algebraic (no EMT capacitor state), so initialize
    # the link at a non-zero transfer to avoid the I_dc=0 singular point.
    control1_val=20.0, control2_val=0.0,
)
grid.add_vsc(vsc_1)
grid.add_vsc(vsc_2)
for vsc in (vsc_1, vsc_2):
    vsc.alpha1 = 0.0
    vsc.alpha2 = 0.0
    vsc.alpha3 = 0.0

zbase_dc = dc_kv * dc_kv / sbase
grid.add_dc_line(vge.DcLine(
    name="HVDC_Line", bus_from=dc_1, bus_to=dc_2,
    r=(0.5 + 0.25 + 0.4) / zbase_dc, rate=sbase,
))

# ----------------------------------------------------------------------------------------------------------------------
# RUN POWERFLOW
# ----------------------------------------------------------------------------------------------------------------------

options = vge.PowerFlowOptions(
    solver_type=SolverType.NR, retry_with_other_methods=True, verbose=False,
    tolerance=1.0e-8, max_iter=100, control_q=False,
    control_taps_modules=False, control_taps_phase=False,
    orthogonalize_controls=False,
)
power_flow_results: PowerFlowResults = vge.power_flow(grid=grid, options=options)
if power_flow_results.converged:
    pass
else:
    raise RuntimeError("RMS HVDC power flow did not converge")

# ----------------------------------------------------------------------------------------------------------------------
# ADD RMS MODELS
# ----------------------------------------------------------------------------------------------------------------------
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
).block
# Inductance is a runtime/event parameter, so configure the case value only
# after the model structure and its event interface have been created.
dc_line_model.set_parameter_in_model(var_name="l_dc", new_value=0.05)
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

# ----------------------------------------------------------------------------------------------------------------------
# ADD RMS EVENT
# ----------------------------------------------------------------------------------------------------------------------

event_group: RmsEventsGroup = RmsEventsGroup(name="HVDC RMS Vdc control")
grid.add_rms_events_group(event_group)
active_power_reference: Var | None = find_name_in_block(
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

# ----------------------------------------------------------------------------------------------------------------------
# RUN RMS SIMULATION
# ----------------------------------------------------------------------------------------------------------------------

rms_options: vge.RmsOptions = vge.RmsOptions(
    simulation_time=simulation_time,
    time_step=time_step,
    max_iter=80,
    tolerance=1.0e-6,
    integration_method=DynamicIntegrationMethod.DaeBackEuler,
    initialization_method=RmsInitializationMethod.Explicit,
)
driver: vge.RmsSimulationDriver = vge.RmsSimulationDriver(
    grid=grid,
    options=rms_options,
    pf_results=power_flow_results,
)
driver.run()
if driver.results is None:
    raise RuntimeError("RMS simulation did not produce results")
else:
    rms_results: RmsResults = driver.results

# ----------------------------------------------------------------------------------------------------------------------
# SAVE PLOT RESULTS
# ----------------------------------------------------------------------------------------------------------------------
script_directory: Path = Path(__file__).resolve().parent
output_directory: Path = script_directory / "LFE_HVDC_system_plots"
plot_paths: list[str] = save_plots(
    grid=grid,
    results=rms_results,
    output_dir=str(output_directory),
    p_event_time=p_event_time,
)
grid_path: Path = script_directory / "LFE_HVDC_system.veragrid"
vge.save_file(grid=grid, filename=str(grid_path))

print(f"Power flow converged: {power_flow_results.converged}")
print(f"RMS converged: {rms_results.converged}")
print(f"Grid saved to: {str(grid_path)}")
for plot_path in plot_paths:
    print(f"Plot saved to: {plot_path}")

# ----------------------------------------------------------------------------------------------------------------------
# RUN RMS SMALL-SIGNAL STABILITY ANALYSIS
# ----------------------------------------------------------------------------------------------------------------------
sss_options = RmsSmallSignalStabilityOptions(k=0,
                                             ss_assessment_time=0,
                                             verbose=1)
small_signal_driver = SmallSignalStabilityRmsDriver(grid=grid,
                                                        rms_options=rms_options,
                                                        sss_options=sss_options,
                                                        pf_results=power_flow_results)
small_signal_driver.run()
eigenvalues = small_signal_driver.results.eigenvalues
PFactors = small_signal_driver.results.participation_factors
damping_ratios = small_signal_driver.results.damping_ratios

print(f"eigenvalues = {eigenvalues}")
print(f"PFactors = {PFactors}")
print(f"damping_ratios = {damping_ratios}")