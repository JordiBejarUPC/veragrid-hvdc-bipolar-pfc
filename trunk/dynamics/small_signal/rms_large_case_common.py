# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Shared network-model assignment and execution for large RMS benchmarks."""

from __future__ import annotations

from matplotlib import pyplot as plt

from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType
from VeraGridEngine.enumerations import RmsInitializationMethod
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.shunt_template import get_shunt_template
from VeraGridEngine.Templates.Rms.transformer_rms_template import get_transformer2w_rms
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
import VeraGridEngine.api as gce


def assign_standard_network_rms_models(grid: gce.MultiCircuit, prefix: str) -> None:
    """Assign standard RMS models to all non-generator network devices.

    :param grid: VeraGrid network whose generators are configured separately.
    :param prefix: Stable model-name prefix.
    :return: None.
    """
    bus_index: int
    for bus_index, bus in enumerate(grid.buses):
        initialize_bus_rms(bus, vf=grid.var_factory)

    line_index: int
    for line_index, line in enumerate(grid.lines):
        set_rms_model(
            device=line,
            model=get_line_rms_template(
                grid.var_factory,
                name=f"{prefix}_line_{line_index + 1}",
            ).block,
            var_factory=grid.var_factory,
        )

    transformer_index: int
    for transformer_index, transformer in enumerate(grid.transformers2w):
        set_rms_model(
            device=transformer,
            model=get_transformer2w_rms(grid.var_factory).block,
            var_factory=grid.var_factory,
        )

    load_index: int
    for load_index, load in enumerate(grid.loads):
        set_rms_model(
            device=load,
            model=get_load_rms_template(
                grid.var_factory,
                name=f"{prefix}_load_{load_index + 1}",
            ).block,
            var_factory=grid.var_factory,
        )

    shunt_index: int
    for shunt_index, shunt in enumerate(grid.shunts):
        shunt_model = get_shunt_template(
            grid.var_factory,
            name=f"{prefix}_shunt_{shunt_index + 1}",
            phasor=False,
        ).block
        shunt_vm = shunt_model.E(VarPowerFlowReferenceType.Vm)
        shunt_p = shunt_model.E(VarPowerFlowReferenceType.P)
        shunt_q = shunt_model.E(VarPowerFlowReferenceType.Q)
        shunt_g = shunt_model.api_obj_mapping[ParamPowerFlowReferenceType.g]
        shunt_b = shunt_model.api_obj_mapping[ParamPowerFlowReferenceType.b]
        shunt_model.event_dict[shunt_g] = grid.var_factory.add_const(
            value=shunt.G / grid.Sbase,
            name="g",
        )
        shunt_model.event_dict[shunt_b] = grid.var_factory.add_const(
            value=shunt.B / grid.Sbase,
            name="b",
        )
        shunt_model.init_eqs[shunt_p] = -shunt_g * shunt_vm ** 2
        shunt_model.init_eqs[shunt_q] = shunt_b * shunt_vm ** 2
        set_rms_model(
            device=shunt,
            model=shunt_model,
            var_factory=grid.var_factory,
        )


def build_large_case_power_flow_options(tolerance: float) -> PowerFlowOptions:
    """Build deterministic Newton options for a large benchmark case.

    :param tolerance: Newton convergence tolerance.
    :return: VeraGrid power-flow options.
    """
    return PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=tolerance,
        max_iter=50,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=True,
        apply_temperature_correction=False,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )


def build_large_case_rms_options() -> RmsOptions:
    """Build common RMS options used only to initialize the small-signal DAE.

    :return: VeraGrid RMS options.
    """
    return RmsOptions(
        time_step=0.001,
        simulation_time=10.0,
        tolerance=1.0e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=1000,
        verbose=0,
    )


def run_power_flow(grid: gce.MultiCircuit, tolerance: float) -> PowerFlowDriver:
    """Run and validate one large-case VeraGrid power flow.

    :param grid: Configured static network.
    :param tolerance: Newton convergence tolerance.
    :return: Completed power-flow driver.
    """
    options: PowerFlowOptions = build_large_case_power_flow_options(tolerance)
    driver: PowerFlowDriver = PowerFlowDriver(grid, options)
    driver.run()
    if bool(driver.results.converged):
        pass
    else:
        raise RuntimeError("VeraGrid power flow did not converge for the benchmark case.")
    return driver


def finish_benchmark_figures(show_figures: bool) -> None:
    """Show or close all small-signal figures after result persistence.

    :param show_figures: Keep interactive PyCharm figures open.
    :return: None.
    """
    if show_figures:
        plt.show()
    else:
        plt.close("all")
