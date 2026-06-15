from __future__ import annotations

from enum import Enum
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

if str(Path(__file__).resolve().parents[2] / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
else:
    sys.path = sys.path

if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
else:
    sys.path = sys.path

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.pv_emt_template import PvEmtModelLevel, get_pv_grid_following_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_transformer_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    ConverterControlType,
    DynamicEventTransitionType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    SolverType,
)


class PvCaseDefinition:
    """
    Store the EMT validation settings for one PV example.

    :param name: Human-readable case name.
    :param rated_power_mw: PV array rated power on the system base.
    :param reactive_power_mvar: Converter reactive-power target.
    :param initial_irradiance_w_m2: Initial irradiance.
    :param irradiance_reference_w_m2: Irradiance base for the PV availability law.
    :param cell_temperature_c: Fixed cell temperature used by the Level-1 model.
    :param temperature_reference_c: Temperature base for the PV availability law.
    :param temperature_power_coefficient: Active-power temperature coefficient.
    :param dc_voltage_reference_pu: Nominal PV operating voltage passed to the PV source model.
    :param irradiance_drop_time_s: First irradiance event time.
    :param irradiance_drop_w_m2: Irradiance after the first event.
    :param irradiance_rise_time_s: Optional second irradiance event time.
    :param irradiance_rise_w_m2: Irradiance after the second event.
    :param simulation_time_s: EMT simulation horizon.
    :param time_step_s: EMT time step.
    """

    __slots__ = [
        "name",
        "rated_power_mw",
        "reactive_power_mvar",
        "initial_irradiance_w_m2",
        "irradiance_reference_w_m2",
        "cell_temperature_c",
        "temperature_reference_c",
        "temperature_power_coefficient",
        "dc_voltage_reference_pu",
        "irradiance_drop_time_s",
        "irradiance_drop_w_m2",
        "irradiance_rise_time_s",
        "irradiance_rise_w_m2",
        "simulation_time_s",
        "time_step_s",
    ]

    def __init__(
        self,
        name: str,
        rated_power_mw: float,
        reactive_power_mvar: float,
        initial_irradiance_w_m2: float,
        irradiance_reference_w_m2: float,
        cell_temperature_c: float,
        temperature_reference_c: float,
        temperature_power_coefficient: float,
        dc_voltage_reference_pu: float,
        irradiance_drop_time_s: float,
        irradiance_drop_w_m2: float,
        irradiance_rise_time_s: float,
        irradiance_rise_w_m2: float,
        simulation_time_s: float,
        time_step_s: float,
    ) -> None:
        self.name: str = str(name)
        self.rated_power_mw: float = float(rated_power_mw)
        self.reactive_power_mvar: float = float(reactive_power_mvar)
        self.initial_irradiance_w_m2: float = float(initial_irradiance_w_m2)
        self.irradiance_reference_w_m2: float = float(irradiance_reference_w_m2)
        self.cell_temperature_c: float = float(cell_temperature_c)
        self.temperature_reference_c: float = float(temperature_reference_c)
        self.temperature_power_coefficient: float = float(temperature_power_coefficient)
        self.dc_voltage_reference_pu: float = float(dc_voltage_reference_pu)
        self.irradiance_drop_time_s: float = float(irradiance_drop_time_s)
        self.irradiance_drop_w_m2: float = float(irradiance_drop_w_m2)
        self.irradiance_rise_time_s: float = float(irradiance_rise_time_s)
        self.irradiance_rise_w_m2: float = float(irradiance_rise_w_m2)
        self.simulation_time_s: float = float(simulation_time_s)
        self.time_step_s: float = float(time_step_s)


class PvRunObjects:
    """
    Keep the static network objects used by the PV EMT case.

    :param run_name: Unique run identifier used in symbolic names.
    :param display_name: Human-readable run label.
    :param pv_level: Selected PV model level.
    :param scenario: Selected scripted scenario.
    :param pv_model_name: Symbolic name of the attached PV EMT model.
    :param grid: VeraGrid circuit.
    :param bus_grid: Slack/source bus.
    :param bus_pv: PV point of common coupling.
    :param generator: Thevenin source generator.
    :param transformer: Unity-ratio transformer between source and PV PCC.
    :param pv_equivalent: Static PQ carrier used for PF and EMT attachment.
    """

    __slots__ = [
        "run_name",
        "display_name",
        "pv_level",
        "scenario",
        "pv_model_name",
        "grid",
        "bus_grid",
        "bus_pv",
        "generator",
        "transformer",
        "pv_equivalent",
    ]

    def __init__(
        self,
        run_name: str,
        display_name: str,
        pv_level: PvEmtModelLevel,
        scenario: PvScenario,
        pv_model_name: str,
        grid: gce.MultiCircuit,
        bus_grid: gce.Bus,
        bus_pv: gce.Bus,
        generator: gce.Generator,
        transformer: gce.Transformer2W,
        pv_equivalent: gce.Load,
    ) -> None:
        self.run_name: str = run_name
        self.display_name: str = display_name
        self.pv_level: PvEmtModelLevel = pv_level
        self.scenario: PvScenario = scenario
        self.pv_model_name: str = pv_model_name
        self.grid: gce.MultiCircuit = grid
        self.bus_grid: gce.Bus = bus_grid
        self.bus_pv: gce.Bus = bus_pv
        self.generator: gce.Generator = generator
        self.transformer: gce.Transformer2W = transformer
        self.pv_equivalent: gce.Load = pv_equivalent


class PvScenario(Enum):
    """
    Enumerate the scripted example selectors used by the EMT examples.

    The current PV irradiance-step example only executes the ``both`` flow, but
    the enum keeps the shared example selector vocabulary explicit and typed.

    :ivar CHARGE: Charge-only selector.
    :ivar DISCHARGE: Discharge-only selector.
    :ivar BOTH: Combined selector.
    """

    CHARGE = "charge"
    DISCHARGE = "discharge"
    BOTH = "both"


class PvEmtBlocks:
    """
    Keep the EMT blocks attached to the key PV validation devices.

    :param gen_mdl: Thevenin source EMT block.
    :param transformer_mdl: Transformer EMT block.
    :param pv_mdl: Complete PV EMT block.
    """

    __slots__ = ["gen_mdl", "transformer_mdl", "pv_mdl"]

    def __init__(self, gen_mdl: Block, transformer_mdl: Block, pv_mdl: Block) -> None:
        self.gen_mdl: Block = gen_mdl
        self.transformer_mdl: Block = transformer_mdl
        self.pv_mdl: Block = pv_mdl


def get_pv_level_label(pv_level: PvEmtModelLevel) -> str:
    """
    Return the human-readable PV model-level label.

    :param pv_level: Selected PV model level.
    :return: Display label.
    """
    if pv_level == PvEmtModelLevel.LEVEL_1:
        return "PV Level 1"
    if pv_level == PvEmtModelLevel.LEVEL_2:
        return "PV Level 2"

    raise ValueError(f"Unsupported PV model level: {pv_level}")


def build_run_name(case: PvCaseDefinition, pv_level: PvEmtModelLevel, scenario: PvScenario) -> str:
    """
    Build the unique run identifier used in device and symbolic names.

    :param case: PV case definition.
    :param pv_level: Selected PV model level.
    :param scenario: Selected scripted scenario.
    :return: Unique run identifier.
    """
    return f"{case.name}_{scenario.value}_pv_level_{pv_level.value}"


def build_display_name(case: PvCaseDefinition, pv_level: PvEmtModelLevel, scenario: PvScenario) -> str:
    """
    Build the human-readable label used in plots and logs.

    :param case: PV case definition.
    :param pv_level: Selected PV model level.
    :param scenario: Selected scripted scenario.
    :return: Human-readable run label.
    """
    return f"{case.name} | scenario {scenario.value} | {get_pv_level_label(pv_level)}"


def build_pv_model_name(case: PvCaseDefinition, pv_level: PvEmtModelLevel, scenario: PvScenario) -> str:
    """
    Build the symbolic name passed to the PV EMT template.

    :param case: PV case definition.
    :param pv_level: Selected PV model level.
    :param scenario: Selected scripted scenario.
    :return: PV EMT symbolic model name.
    """
    return f"pv_emt_{build_run_name(case, pv_level, scenario)}"


def get_level2_v_mp_ref_pu() -> float:
    """
    Return the Level-2 PV MPP voltage reference used by this example.

    :return: Level-2 MPP voltage reference in pu.
    """
    return 0.80


def get_level2_i_mp_ref_pu(case: PvCaseDefinition, sbase_mva: float) -> float:
    """
    Scale the Level-2 MPP current reference to the requested PV rating.

    The Level-2 template computes available PV power from ``v_mp`` and ``i_mp``.
    This helper keeps the Level-2 irradiance response numerically aligned with
    the example rated power without collapsing the Level-2 model into Level-1
    behaviour.

    :param case: PV case definition.
    :param sbase_mva: System base power.
    :return: Level-2 MPP current reference in pu.
    """
    rated_power_pu: float = case.rated_power_mw / sbase_mva
    return rated_power_pu / max(get_level2_v_mp_ref_pu(), 1.0e-10)


def get_level1_vdc_control_reference_pu(case: PvCaseDefinition) -> float:
    """
    Return the Level-1 Vdc-control reference used by this example.

    The Level-1 PV source initializes slightly below the nominal DC reference
    because the exported operating point includes the source internal droop.

    :param case: PV case definition.
    :return: Level-1 converter Vdc reference in pu.
    """
    return case.dc_voltage_reference_pu


def get_level2_vdc_control_reference_pu(case: PvCaseDefinition) -> float:
    """
    Return the Level-2 Vdc-control reference used by this example.

    The Level-2 averaged boost stage initializes slightly above the nominal DC
    reference at the converter terminal because of the boost-side droop model.

    :param case: PV case definition.
    :return: Level-2 converter Vdc reference in pu.
    """
    return case.dc_voltage_reference_pu


def build_case_definition() -> PvCaseDefinition:
    """
    Create the single PV validation case used by this script.

    :return: Configured PV case definition.
    """
    case: PvCaseDefinition = PvCaseDefinition(
        name="pv_irradiance_step",
        rated_power_mw=10.0,
        reactive_power_mvar=0.0,
        initial_irradiance_w_m2=1000.0,
        irradiance_reference_w_m2=1000.0,
        cell_temperature_c=25.0,
        temperature_reference_c=25.0,
        temperature_power_coefficient=0.0,
        dc_voltage_reference_pu=1.0,
        irradiance_drop_time_s=0.70,
        irradiance_drop_w_m2=600.0,
        irradiance_rise_time_s=1.0,
        irradiance_rise_w_m2=900.0,
        simulation_time_s=1.5,
        time_step_s=2.0e-5,
    )
    return case


def get_expected_initial_available_power_mw(case: PvCaseDefinition) -> float:
    """
    Compute the Level-1 PV available power implied by the initial conditions.

    :param case: PV case definition.
    :return: Expected initial available active power in MW.
    """
    temperature_factor: float = 1.0 + case.temperature_power_coefficient * (
        case.cell_temperature_c - case.temperature_reference_c
    )
    available_power_mw: float = case.rated_power_mw * (
        case.initial_irradiance_w_m2 / case.irradiance_reference_w_m2
    ) * temperature_factor

    if available_power_mw < 0.0:
        available_power_mw = 0.0
    else:
        available_power_mw = min(available_power_mw, case.rated_power_mw)

    return available_power_mw


def get_expected_available_power_mw(case: PvCaseDefinition, irradiance_w_m2: float) -> float:
    """
    Compute the Level-1 PV available power for one irradiance level.

    :param case: PV case definition.
    :param irradiance_w_m2: Irradiance to evaluate.
    :return: Expected available active power in MW.
    """
    temperature_factor: float = 1.0 + case.temperature_power_coefficient * (
        case.cell_temperature_c - case.temperature_reference_c
    )
    available_power_mw: float = case.rated_power_mw * (
        float(irradiance_w_m2) / case.irradiance_reference_w_m2
    ) * temperature_factor

    if available_power_mw < 0.0:
        available_power_mw = 0.0
    else:
        available_power_mw = min(available_power_mw, case.rated_power_mw)

    return available_power_mw


def get_initial_converter_power_schedule_mw(case: PvCaseDefinition) -> float:
    """
    Return the converter active-power schedule consistent with PV export.

    The PV example is initialized so the converter scheduled active power is
    consistent with the steady-state PV export level used by the power flow.

    :param case: PV case definition.
    :return: Initial converter active-power schedule in MW.
    """
    initial_converter_power_schedule_mw: float = get_expected_initial_available_power_mw(case)
    return initial_converter_power_schedule_mw


def get_mppt_model_description(pv_level: PvEmtModelLevel) -> str:
    """
    Describe the MPPT representation used by the selected PV model level.

    :param pv_level: Selected PV model level.
    :return: Human-readable MPPT description.
    """
    if pv_level == PvEmtModelLevel.LEVEL_1:
        return "PV Level 1 MPPT: first-order lag on PV available power inside the PV availability block"
    if pv_level == PvEmtModelLevel.LEVEL_2:
        return "PV Level 2 MPPT: averaged boost-converter duty-cycle control tracking the PV MPP voltage"

    raise ValueError(f"Unsupported PV model level: {pv_level}")


def _converter_control_type_code(control: ConverterControlType) -> float:
    """
    Return the numeric code used internally by the pseudo-EMT converter template.

    :param control: Converter control enum.
    :return: Numeric control code.
    """
    if control == ConverterControlType.Vm_dc:
        return 1.0
    if control == ConverterControlType.Qac:
        return 4.0
    if control == ConverterControlType.Pac:
        return 6.0
    else:
        return 0.0


def build_grid(case: PvCaseDefinition, pv_level: PvEmtModelLevel, scenario: PvScenario) -> PvRunObjects:
    """
    Build an AC-only PF carrier network for the internal-DC PV EMT model.

    :param case: PV case definition.
    :param pv_level: Selected PV model level.
    :param scenario: Selected scripted scenario.
    :return: Static network objects used by the EMT run.
    """
    initial_pv_power_mw: float = get_expected_initial_available_power_mw(case)
    run_name: str = build_run_name(case, pv_level, scenario)
    display_name: str = build_display_name(case, pv_level, scenario)
    pv_model_name: str = build_pv_model_name(case, pv_level, scenario)
    grid: gce.MultiCircuit = gce.MultiCircuit(
        name=f"Grid - AC Thevenin + PV EMT - {display_name}",
        Sbase=100.0,
        fbase=50.0,
    )

    bus_grid: gce.Bus = gce.Bus(name=f"Bus_GRID_{run_name}", Vnom=230.0, is_slack=True)
    bus_pv: gce.Bus = gce.Bus(name=f"Bus_PV_{run_name}", Vnom=230.0)
    grid.add_bus(bus_grid)
    grid.add_bus(bus_pv)

    generator: gce.Generator = gce.Generator(
        name=f"Gen_Thev_{run_name}",
        vset=1.0,
        Snom=grid.Sbase,
        freq=50.0,
        r1=0.001,
        x1=0.04,
    )
    grid.add_generator(bus_grid, generator)

    transformer: gce.Transformer2W = gce.Transformer2W(
        bus_from=bus_grid,
        bus_to=bus_pv,
        name=f"Transformer_GRID_PV_{run_name}",
        rate=grid.Sbase,
        r=1.0e-5,
        x=1.0e-5,
        tap_module=1.0,
        tap_phase=0.0,
    )
    grid.add_transformer2w(transformer)

    # A negative PQ load represents generation in the balanced power flow.
    pv_equivalent: gce.Load = gce.Load(
        name=f"PV_PF_equivalent_{run_name}",
        P=-initial_pv_power_mw,
        Q=-case.reactive_power_mvar,
    )
    grid.add_load(bus_pv, pv_equivalent)

    objects: PvRunObjects = PvRunObjects(
        run_name=run_name,
        display_name=display_name,
        pv_level=pv_level,
        scenario=scenario,
        pv_model_name=pv_model_name,
        grid=grid,
        bus_grid=bus_grid,
        bus_pv=bus_pv,
        generator=generator,
        transformer=transformer,
        pv_equivalent=pv_equivalent,
    )
    return objects


def build_power_flow_options() -> PowerFlowOptions:
    """
    Create the balanced power-flow options for the PV validation case.

    :return: Balanced power-flow options.
    """
    options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=False,
        tolerance=1e-8,
        max_iter=50,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    return options


def run_power_flow(grid: gce.MultiCircuit) -> PowerFlowResults:
    """
    Run the balanced power flow used by the EMT initializer.

    :param grid: VeraGrid circuit.
    :return: Balanced power-flow results.
    """
    results: PowerFlowResults = gce.power_flow(grid=grid, options=build_power_flow_options())
    print(f"Powerflow results: {results}")
    return results


def build_power_flow_options_3ph() -> PowerFlowOptions:
    """
    Create the 3-phase power-flow options used for EMT initialization.

    :return: 3-phase power-flow options.
    """
    options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
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
        branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    return options


def run_power_flow_3ph(grid: gce.MultiCircuit) -> PowerFlowResults3Ph:
    """
    Run the 3-phase power flow used to seed EMT initialization.

    :param grid: VeraGrid circuit.
    :return: 3-phase power-flow results.
    """
    power_flow_driver: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, build_power_flow_options_3ph())
    power_flow_driver.run()
    results: PowerFlowResults3Ph = power_flow_driver.results
    return results


def apply_common_converter_parameters(
    pv_mdl: Block,
    pv_model_name: str,
    grid_sbase_mva: float,
    case: PvCaseDefinition,
    initial_converter_power_schedule_mw: float,
) -> None:
    """
    Apply the imported converter settings shared by both PV levels.

    :param pv_mdl: Full PV EMT block.
    :param pv_model_name: Symbolic PV model name.
    :param grid_sbase_mva: System base power.
    :param case: PV case definition.
    :param initial_converter_power_schedule_mw: Initial Pac schedule.
    :return: None.
    """
    pv_mdl.set_parameter_in_model(var_name=f"sbase_{pv_model_name}", new_value=grid_sbase_mva)
    pv_mdl.set_parameter_in_model(
        var_name=f"control1_{pv_model_name}",
        new_value=_converter_control_type_code(ConverterControlType.Pac),
    )
    pv_mdl.set_parameter_in_model(
        var_name=f"control2_{pv_model_name}",
        new_value=_converter_control_type_code(ConverterControlType.Qac),
    )
    pv_mdl.set_parameter_in_model(var_name=f"control1_val_{pv_model_name}", new_value=initial_converter_power_schedule_mw)
    pv_mdl.set_parameter_in_model(var_name=f"control2_val_{pv_model_name}", new_value=case.reactive_power_mvar)
    pv_mdl.set_parameter_in_model(var_name=f"P0_{pv_model_name}", new_value=initial_converter_power_schedule_mw)
    pv_mdl.set_parameter_in_model(var_name=f"Vdc_nom_{pv_model_name}", new_value=case.dc_voltage_reference_pu)

    # These parameters are kept close to the BESS validation settings so the
    # imported pseudo-EMT converter remains in a familiar and well-conditioned range.
    pv_mdl.set_parameter_in_model(var_name=f"R_eq_{pv_model_name}", new_value=0.05)
    pv_mdl.set_parameter_in_model(var_name=f"L_eq_{pv_model_name}", new_value=0.20)
    pv_mdl.set_parameter_in_model(var_name=f"C_dc_{pv_model_name}", new_value=0.20)
    pv_mdl.set_parameter_in_model(var_name=f"R_dc_{pv_model_name}", new_value=1e6)
    pv_mdl.set_parameter_in_model(var_name=f"R_dc_term_{pv_model_name}", new_value=0.0001)
    pv_mdl.set_parameter_in_model(var_name=f"pll_kp_{pv_model_name}", new_value=10.0)
    pv_mdl.set_parameter_in_model(var_name=f"pll_ki_{pv_model_name}", new_value=100.0)
    pv_mdl.set_parameter_in_model(var_name=f"i_kp_{pv_model_name}", new_value=0.3)
    pv_mdl.set_parameter_in_model(var_name=f"i_ki_{pv_model_name}", new_value=20.0)
    # The corrected dq/abc converter sign convention needs a much lighter Vdc
    # loop here so the PV example starts close to the PF operating point instead
    # of immediately over-correcting the DC-link energy balance.
    pv_mdl.set_parameter_in_model(var_name=f"vdc_kp_{pv_model_name}", new_value=0.01)
    pv_mdl.set_parameter_in_model(var_name=f"vdc_ki_{pv_model_name}", new_value=0.10)
    pv_mdl.set_parameter_in_model(var_name=f"q_kp_{pv_model_name}", new_value=0.02)
    pv_mdl.set_parameter_in_model(var_name=f"q_ki_{pv_model_name}", new_value=0.5)
    pv_mdl.set_parameter_in_model(var_name=f"i_max_{pv_model_name}", new_value=1.3)
    pv_mdl.set_parameter_in_model(var_name=f"m_max_{pv_model_name}", new_value=0.95)
    pv_mdl.set_parameter_in_model(var_name=f"P_loss_i1_{pv_model_name}", new_value=0.01)
    pv_mdl.set_parameter_in_model(var_name=f"P_loss_i2_{pv_model_name}", new_value=0.01)
    pv_mdl.set_parameter_in_model(var_name=f"tau_meas_{pv_model_name}", new_value=0.02)
    pv_mdl.set_parameter_in_model(var_name=f"aw_gain_{pv_model_name}", new_value=0.2)
    pv_mdl.set_parameter_in_model(var_name=f"vdc_floor_{pv_model_name}", new_value=0.05)


def apply_level1_pv_parameters(pv_mdl: Block, pv_model_name: str, case: PvCaseDefinition, rated_power_pu: float) -> None:
    """
    Apply the Level-1 PV-source parameters.

    :param pv_mdl: Full PV EMT block.
    :param pv_model_name: Symbolic PV model name.
    :param case: PV case definition.
    :param rated_power_pu: PV rating on the system base.
    :return: None.
    """
    pv_mdl.set_parameter_in_model(var_name=f"p_rated_l1_{pv_model_name}", new_value=rated_power_pu)
    pv_mdl.set_parameter_in_model(var_name=f"irradiance_l1_{pv_model_name}", new_value=case.initial_irradiance_w_m2)
    pv_mdl.set_parameter_in_model(var_name=f"irradiance_ref_l1_{pv_model_name}", new_value=case.irradiance_reference_w_m2)
    pv_mdl.set_parameter_in_model(var_name=f"t_cell_l1_{pv_model_name}", new_value=case.cell_temperature_c)
    pv_mdl.set_parameter_in_model(var_name=f"t_ref_l1_{pv_model_name}", new_value=case.temperature_reference_c)
    pv_mdl.set_parameter_in_model(var_name=f"temp_coeff_p_l1_{pv_model_name}", new_value=case.temperature_power_coefficient)
    pv_mdl.set_parameter_in_model(var_name=f"t_mppt_l1_{pv_model_name}", new_value=0.05)
    pv_mdl.set_parameter_in_model(var_name=f"v_dc_ref_l1_{pv_model_name}", new_value=case.dc_voltage_reference_pu)
    pv_mdl.set_parameter_in_model(var_name=f"r_pv_l1_{pv_model_name}", new_value=0.02)
    pv_mdl.set_parameter_in_model(var_name=f"k_pv_power_l1_{pv_model_name}", new_value=2.0)
    pv_mdl.set_parameter_in_model(var_name=f"k_vdc_ctrl_l1_{pv_model_name}", new_value=5.0)


def apply_level2_pv_parameters(
    pv_mdl: Block,
    pv_model_name: str,
    case: PvCaseDefinition,
    rated_power_pu: float,
    grid_sbase_mva: float,
) -> None:
    """
    Apply the Level-2 PV plus averaged boost parameters.

    :param pv_mdl: Full PV EMT block.
    :param pv_model_name: Symbolic PV model name.
    :param case: PV case definition.
    :param rated_power_pu: PV rating on the system base.
    :param grid_sbase_mva: System base power.
    :return: None.
    """
    pv_mdl.set_parameter_in_model(var_name=f"p_rated_l2_{pv_model_name}", new_value=rated_power_pu)
    pv_mdl.set_parameter_in_model(var_name=f"irradiance_l2_{pv_model_name}", new_value=case.initial_irradiance_w_m2)
    pv_mdl.set_parameter_in_model(var_name=f"irradiance_ref_l2_{pv_model_name}", new_value=case.irradiance_reference_w_m2)
    pv_mdl.set_parameter_in_model(var_name=f"t_cell_l2_{pv_model_name}", new_value=case.cell_temperature_c)
    pv_mdl.set_parameter_in_model(var_name=f"t_ref_l2_{pv_model_name}", new_value=case.temperature_reference_c)
    pv_mdl.set_parameter_in_model(var_name=f"v_mp_ref_l2_{pv_model_name}", new_value=get_level2_v_mp_ref_pu())
    pv_mdl.set_parameter_in_model(
        var_name=f"i_mp_ref_l2_{pv_model_name}",
        new_value=get_level2_i_mp_ref_pu(case=case, sbase_mva=grid_sbase_mva),
    )
    pv_mdl.set_parameter_in_model(var_name=f"v_dc_ref_l2_{pv_model_name}", new_value=case.dc_voltage_reference_pu)
    pv_mdl.set_parameter_in_model(var_name=f"k_src_l2_{pv_model_name}", new_value=0.5)
    pv_mdl.set_parameter_in_model(var_name=f"k_boost_power_l2_{pv_model_name}", new_value=0.5)
    pv_mdl.set_parameter_in_model(var_name=f"k_vdc_ctrl_l2_{pv_model_name}", new_value=2.0)


def attach_emt_models(objects: PvRunObjects, case: PvCaseDefinition) -> PvEmtBlocks:
    """
    Attach bus, transformer, Thevenin source and PV EMT models.

    :param objects: Static grid objects.
    :param case: PV case definition.
    :return: Attached EMT blocks.
    """
    initial_converter_power_schedule_mw: float = get_initial_converter_power_schedule_mw(case)
    rated_power_pu: float = case.rated_power_mw / objects.grid.Sbase

    bus: gce.Bus
    for bus in objects.grid.buses:
        get_bus_emt_template(objects.grid, bus)

    gen_mdl: Block = get_generator_thevenin_rl_emt_template_with_ref(
        vf=objects.grid.var_factory,
        name=f"gen_thev_{objects.run_name}",
    ).block
    transformer_mdl: Block = get_transformer_emt_template(
        vf=objects.grid.var_factory,
        name=f"transformer_grid_pv_{objects.run_name}",
    ).block
    pv_mdl: Block = get_pv_grid_following_emt_template(
        vf=objects.grid.var_factory,
        level=objects.pv_level,
        name=objects.pv_model_name,
    ).block

    # Both PV levels are driven in Pac/Q mode. The converter follows the known
    # export schedule while the PV-side source model performs the local DC-link
    # regulation through its own internal Vdc feedback.
    apply_common_converter_parameters(
        pv_mdl=pv_mdl,
        pv_model_name=objects.pv_model_name,
        grid_sbase_mva=objects.grid.Sbase,
        case=case,
        initial_converter_power_schedule_mw=initial_converter_power_schedule_mw,
    )

    if objects.pv_level == PvEmtModelLevel.LEVEL_1:
        apply_level1_pv_parameters(
            pv_mdl=pv_mdl,
            pv_model_name=objects.pv_model_name,
            case=case,
            rated_power_pu=rated_power_pu,
        )
    elif objects.pv_level == PvEmtModelLevel.LEVEL_2:
        apply_level2_pv_parameters(
            pv_mdl=pv_mdl,
            pv_model_name=objects.pv_model_name,
            case=case,
            rated_power_pu=rated_power_pu,
            grid_sbase_mva=objects.grid.Sbase,
        )
    else:
        raise ValueError(f"Unsupported PV model level: {objects.pv_level}")

    set_emt_model(device=objects.generator, model=gen_mdl, var_factory=objects.grid.var_factory)
    set_emt_model(device=objects.transformer, model=transformer_mdl, var_factory=objects.grid.var_factory)
    set_emt_model(device=objects.pv_equivalent, model=pv_mdl, var_factory=objects.grid.var_factory)

    blocks: PvEmtBlocks = PvEmtBlocks(gen_mdl=gen_mdl, transformer_mdl=transformer_mdl, pv_mdl=pv_mdl)
    return blocks


def find_event_parameter(block: Block, variable_name: str) -> Var | None:
    """
    Find one runtime parameter in a block event dictionary by exact name.

    :param block: Candidate symbolic block.
    :param variable_name: Full variable name to search for.
    :return: Matching runtime parameter or None.
    """
    event_var: Var
    for event_var in block.event_dict.keys():
        if event_var.name == variable_name:
            return event_var
        else:
            pass

    return None


def get_irradiance_parameter_name(pv_level: PvEmtModelLevel, pv_model_name: str) -> str:
    """
    Return the runtime irradiance parameter name for one PV level.

    :param pv_level: Selected PV model level.
    :param pv_model_name: Symbolic PV model name.
    :return: Full irradiance parameter name.
    """
    if pv_level == PvEmtModelLevel.LEVEL_1:
        return f"irradiance_l1_{pv_model_name}"
    if pv_level == PvEmtModelLevel.LEVEL_2:
        return f"irradiance_l2_{pv_model_name}"

    raise ValueError(f"Unsupported PV model level: {pv_level}")


def add_irradiance_events(
    grid: gce.MultiCircuit,
    pv_block: Block,
    case: PvCaseDefinition,
    pv_level: PvEmtModelLevel,
    pv_model_name: str,
) -> EmtEventsGroup | None:
    """
    Add irradiance step events to the actual PV runtime parameter.

    :param grid: VeraGrid circuit.
    :param pv_block: Full PV EMT block.
    :param case: PV case definition.
    :param pv_level: Selected PV model level.
    :param pv_model_name: Symbolic PV model name.
    :return: Created EMT events group, or None if the parameter was not found.
    """
    irradiance_var_name: str = get_irradiance_parameter_name(pv_level=pv_level, pv_model_name=pv_model_name)
    irradiance_var: Var | None = find_event_parameter(pv_block, irradiance_var_name)

    if irradiance_var is None:
        print(f"Unable to create irradiance events. Runtime parameter '{irradiance_var_name}' was not found.")
        return None
    else:
        event_group: EmtEventsGroup = EmtEventsGroup(name=f"{case.name}_irradiance_events")
        grid.add_emt_events_group(event_group)

        grid.add_emt_event(
            EmtEvent(
                parameter=irradiance_var,
                time=case.irradiance_drop_time_s,
                value=case.irradiance_drop_w_m2,
                group=event_group,
                force_step_alignment=True,
                transition_type=DynamicEventTransitionType.Step,
                name=f"{case.name}_irradiance_drop",
            )
        )
        grid.add_emt_event(
            EmtEvent(
                parameter=irradiance_var,
                time=case.irradiance_rise_time_s,
                value=case.irradiance_rise_w_m2,
                group=event_group,
                force_step_alignment=True,
                transition_type=DynamicEventTransitionType.Step,
                name=f"{case.name}_irradiance_rise",
            )
        )

        # The Pac/Q example keeps the converter export schedule aligned with the
        # scripted irradiance profile, while the PV-side block regulates the DC
        # voltage internally using its own local feedback.
        active_power_ref_var: Var | None = find_event_parameter(pv_block, f"control1_val_{pv_model_name}")

        if active_power_ref_var is not None:
            grid.add_emt_event(
                EmtEvent(
                    parameter=active_power_ref_var,
                    time=case.irradiance_drop_time_s,
                    value=get_expected_available_power_mw(case, case.irradiance_drop_w_m2),
                    group=event_group,
                    force_step_alignment=True,
                    transition_type=DynamicEventTransitionType.Step,
                    name=f"{case.name}_active_power_drop",
                )
            )
            grid.add_emt_event(
                EmtEvent(
                    parameter=active_power_ref_var,
                    time=case.irradiance_rise_time_s,
                    value=get_expected_available_power_mw(case, case.irradiance_rise_w_m2),
                    group=event_group,
                    force_step_alignment=True,
                    transition_type=DynamicEventTransitionType.Step,
                    name=f"{case.name}_active_power_rise",
                )
            )

        return event_group


def build_problem(
    grid: gce.MultiCircuit,
    pf_results: PowerFlowResults,
    pf_results_3ph: PowerFlowResults3Ph,
    case: PvCaseDefinition,
    event_group: EmtEventsGroup | None,
) -> EmtProblemDae:
    """
    Build the EMT DAE problem for the PV validation case.

    :param grid: VeraGrid circuit.
    :param pf_results: Balanced power-flow results.
    :param pf_results_3ph: 3-phase power-flow results.
    :param case: PV case definition.
    :param event_group: Irradiance event group.
    :return: Configured EMT DAE problem.
    """
    options: EmtOptions = EmtOptions(
        time_step=case.time_step_s,
        simulation_time=case.simulation_time_s,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=1,
    )
    problem: EmtProblemDae = EmtProblemDae(
        grid=grid,
        options=options,
        pf_results_3ph=pf_results_3ph,
        pf_results=pf_results,
    )

    if event_group is not None:
        problem.set_events_group(event_group)
    else:
        print("No EMT events group was attached to the problem.")

    return problem


def build_solver(problem: EmtProblemDae) -> StructuralCompiledSolver:
    """
    Build the structural compiled EMT solver.

    :param problem: EMT DAE problem.
    :return: Configured solver.
    """
    solver: StructuralCompiledSolver = StructuralCompiledSolver(
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
        auto_build=False,
    )
    solver._build_vectorized_backend(problem.options.integration_method)
    return solver


def validate_initialization(problem: EmtProblemDae) -> None:
    """
    Print a compact EMT initialization report.

    :param problem: EMT problem.
    :return: None.
    """
    x0: np.ndarray = problem.get_x0()
    dx0: np.ndarray = problem.get_dx0()

    print("EMT initialization report")
    print(f"  finite x0 : {bool(np.all(np.isfinite(x0)))}")
    print(f"  finite dx0: {bool(np.all(np.isfinite(dx0)))}")

    if problem.initialization_report is not None:
        report: Any = problem.initialization_report
        print(f"  method    : {report.method_used.name}")
        print(f"  status    : {report.status.name}")
        print(f"  residual  : {report.final_residual_inf:.3e}")
        print(f"  succeeded : {report.status.name in {'SUCCESS', 'RESOLVED'}}")
    else:
        print("  report    : not available")


def get_signal_or_none(
    problem: EmtProblemDae,
    root_block: Block,
    variable_name: str,
    y_values: np.ndarray,
    required: bool,
) -> np.ndarray | None:
    """
    Extract one symbolic trajectory while keeping the script robust.

    :param problem: EMT problem with variable indexing.
    :param root_block: Block where the variable will be searched.
    :param variable_name: Symbolic variable name.
    :param y_values: EMT trajectory matrix.
    :param required: Whether the diagnostic is expected to exist.
    :return: Selected trajectory or None.
    """
    variable: Var | None = find_name_in_block(variable_name, root_block)

    if variable is None:
        if required:
            print(f"Required signal '{variable_name}' was not found in block '{root_block.name}'.")
        else:
            print(f"Optional signal '{variable_name}' was not found in block '{root_block.name}'.")
        return None
    else:
        signal_values: np.ndarray = y_values[:, problem.get_var_idx(variable)]
        return signal_values


def get_runtime_parameter_trace(problem: EmtProblemDae, parameter: Var | None, time_values: np.ndarray) -> np.ndarray | None:
    """
    Reconstruct one runtime-parameter trace after EMT events are applied.

    :param problem: EMT problem with runtime-parameter support.
    :param parameter: Runtime parameter variable.
    :param time_values: EMT time vector.
    :return: Runtime-parameter trace or None.
    """
    if parameter is None:
        print("No runtime parameter was provided for trace reconstruction.")
        return None
    else:
        runtime_parameters: list[Var] = problem.get_variable_parameters()

        if parameter in runtime_parameters:
            parameter_index: int = runtime_parameters.index(parameter)
            trace_values: np.ndarray = np.asarray(
                [problem.def_event_params_fn(problem.event_params_values.copy(), float(time_value))[parameter_index] for time_value in time_values],
                dtype=np.float64,
            )
            return trace_values
        else:
            print(f"Runtime parameter '{parameter.name}' is not registered in the EMT problem.")
            return None


def populate_level1_plot_data(
    problem: EmtProblemDae,
    pv_block: Block,
    pv_model_name: str,
    y_values: np.ndarray,
    data: dict[str, np.ndarray | None],
) -> None:
    """
    Populate the Level-1 diagnostic signals used by the plots and checks.

    :param problem: EMT problem.
    :param pv_block: Full PV EMT block.
    :param pv_model_name: Symbolic PV model name.
    :param y_values: EMT solution matrix.
    :param data: Output signal dictionary.
    :return: None.
    """
    data["p_avail_pu"] = get_signal_or_none(problem, pv_block, f"p_avail_l1_{pv_model_name}", y_values, True)
    data["p_mppt_pu"] = get_signal_or_none(problem, pv_block, f"p_mppt_l1_{pv_model_name}", y_values, False)
    data["p_pv_internal_pu"] = get_signal_or_none(problem, pv_block, f"p_pv_l1_{pv_model_name}", y_values, True)
    data["i_pv_internal"] = get_signal_or_none(problem, pv_block, f"i_pv_l1_{pv_model_name}", y_values, True)
    data["v_dc_source_internal"] = get_signal_or_none(problem, pv_block, f"v_dc_bus_pv_l1_{pv_model_name}", y_values, False)
    data["p_curt_internal_pu"] = get_signal_or_none(problem, pv_block, f"p_curt_l1_{pv_model_name}", y_values, False)
    data["p_to_vsc_pu"] = None
    data["v_pv_internal"] = None
    data["duty"] = None


def populate_level2_plot_data(
    problem: EmtProblemDae,
    pv_block: Block,
    pv_model_name: str,
    y_values: np.ndarray,
    data: dict[str, np.ndarray | None],
) -> None:
    """
    Populate the Level-2 diagnostic signals used by the plots and checks.

    :param problem: EMT problem.
    :param pv_block: Full PV EMT block.
    :param pv_model_name: Symbolic PV model name.
    :param y_values: EMT solution matrix.
    :param data: Output signal dictionary.
    :return: None.
    """
    data["p_avail_pu"] = get_signal_or_none(problem, pv_block, f"p_avail_l2_{pv_model_name}", y_values, True)
    data["p_mppt_pu"] = None
    data["p_pv_internal_pu"] = get_signal_or_none(problem, pv_block, f"p_src_l2_{pv_model_name}", y_values, True)
    data["i_pv_internal"] = get_signal_or_none(problem, pv_block, f"i_pv_l2_{pv_model_name}", y_values, True)
    data["v_dc_source_internal"] = get_signal_or_none(problem, pv_block, f"v_dc_bus_pv_l2_{pv_model_name}", y_values, False)
    data["p_curt_internal_pu"] = get_signal_or_none(problem, pv_block, f"p_curt_l2_{pv_model_name}", y_values, False)
    data["p_to_vsc_pu"] = get_signal_or_none(problem, pv_block, f"p_to_vsc_l2_{pv_model_name}", y_values, False)
    data["v_pv_internal"] = get_signal_or_none(problem, pv_block, f"v_pv_l2_{pv_model_name}", y_values, False)
    data["duty"] = get_signal_or_none(problem, pv_block, f"duty_l2_{pv_model_name}", y_values, False)


def build_plot_data(
    problem: EmtProblemDae,
    objects: PvRunObjects,
    blocks: PvEmtBlocks,
    y_values: np.ndarray,
    time_values: np.ndarray,
    case: PvCaseDefinition,
) -> dict[str, np.ndarray | None]:
    """
    Collect the PV and converter signals needed for validation plots.

    :param problem: EMT problem.
    :param objects: Static network objects.
    :param blocks: Attached EMT blocks.
    :param y_values: EMT solution matrix.
    :param time_values: EMT time vector.
    :param case: PV case definition.
    :return: Named signal dictionary.
    """
    data: dict[str, np.ndarray | None] = dict()
    pv_model_name: str = objects.pv_model_name

    data["v_ac_a"] = get_signal_or_none(
        problem,
        objects.bus_pv.emt_model,
        f"v_A_{objects.bus_pv.name}_emt_template",
        y_values,
        True,
    )
    data["v_ac_b"] = get_signal_or_none(
        problem,
        objects.bus_pv.emt_model,
        f"v_B_{objects.bus_pv.name}_emt_template",
        y_values,
        True,
    )
    data["v_ac_c"] = get_signal_or_none(
        problem,
        objects.bus_pv.emt_model,
        f"v_C_{objects.bus_pv.name}_emt_template",
        y_values,
        True,
    )

    data["i_a"] = get_signal_or_none(problem, blocks.pv_mdl, f"i_A_{pv_model_name}", y_values, True)
    data["i_b"] = get_signal_or_none(problem, blocks.pv_mdl, f"i_B_{pv_model_name}", y_values, True)
    data["i_c"] = get_signal_or_none(problem, blocks.pv_mdl, f"i_C_{pv_model_name}", y_values, True)
    data["p_ac_internal_pu"] = get_signal_or_none(problem, blocks.pv_mdl, f"P_{pv_model_name}", y_values, True)
    data["q_ac_pu"] = get_signal_or_none(problem, blocks.pv_mdl, f"Q_{pv_model_name}", y_values, True)
    data["v_dc_internal"] = get_signal_or_none(problem, blocks.pv_mdl, f"v_dc_{pv_model_name}", y_values, True)
    data["i_dc"] = get_signal_or_none(problem, blocks.pv_mdl, f"i_dc_{pv_model_name}", y_values, True)

    if objects.pv_level == PvEmtModelLevel.LEVEL_1:
        populate_level1_plot_data(problem, blocks.pv_mdl, pv_model_name, y_values, data)
    elif objects.pv_level == PvEmtModelLevel.LEVEL_2:
        populate_level2_plot_data(problem, blocks.pv_mdl, pv_model_name, y_values, data)
    else:
        raise ValueError(f"Unsupported PV model level: {objects.pv_level}")

    if data["p_mppt_pu"] is not None:
        data["p_pv_pu"] = np.array(data["p_mppt_pu"], copy=True)
    else:
        data["p_pv_pu"] = data["p_pv_internal_pu"]

    if objects.pv_level == PvEmtModelLevel.LEVEL_1:
        data["v_dc_source"] = np.full_like(time_values, case.dc_voltage_reference_pu, dtype=np.float64)
    else:
        data["v_dc_source"] = data["v_pv_internal"]

    if objects.pv_level == PvEmtModelLevel.LEVEL_1 and data["p_pv_pu"] is not None:
        data["i_pv"] = data["p_pv_pu"] / max(case.dc_voltage_reference_pu, 1.0e-10)
    else:
        data["i_pv"] = data["i_pv_internal"]

    if data["p_avail_pu"] is not None and data["p_pv_pu"] is not None:
        data["p_curt_pu"] = np.maximum(data["p_avail_pu"] - data["p_pv_pu"], 0.0)
    else:
        data["p_curt_pu"] = data["p_curt_internal_pu"]

    irradiance_parameter: Var | None = find_event_parameter(
        blocks.pv_mdl,
        get_irradiance_parameter_name(pv_level=objects.pv_level, pv_model_name=pv_model_name),
    )
    data["irradiance"] = get_runtime_parameter_trace(problem, irradiance_parameter, time_values)

    if data["p_ac_internal_pu"] is not None:
        data["p_grid_export_pu"] = data["p_ac_internal_pu"]
    else:
        data["p_grid_export_pu"] = None

    if data["v_ac_a"] is not None and data["v_ac_b"] is not None and data["v_ac_c"] is not None and data["i_a"] is not None and data["i_b"] is not None and data["i_c"] is not None:
        data["p_abc_pu"] = data["v_ac_a"] * data["i_a"] + data["v_ac_b"] * data["i_b"] + data["v_ac_c"] * data["i_c"]
    else:
        data["p_abc_pu"] = None

    return data


def compute_fundamental_phase_shift_deg(
    time_values: np.ndarray,
    voltage_values: np.ndarray | None,
    current_values: np.ndarray | None,
    time_start_s: float,
    time_end_s: float,
    frequency_hz: float,
) -> float | None:
    """
    Estimate the fundamental current-minus-voltage phase shift.

    :param time_values: EMT time vector.
    :param voltage_values: Phase-voltage trajectory.
    :param current_values: Phase-current trajectory.
    :param time_start_s: Window start time.
    :param time_end_s: Window end time.
    :param frequency_hz: Fundamental frequency.
    :return: Phase shift in degrees, or None.
    """
    if voltage_values is None or current_values is None:
        return None
    else:
        mask: np.ndarray = np.logical_and(time_values >= time_start_s, time_values <= time_end_s)

        if bool(np.any(mask)):
            omega: float = 2.0 * np.pi * float(frequency_hz)
            time_window: np.ndarray = time_values[mask]
            sine_basis: np.ndarray = np.sin(omega * time_window)
            cosine_basis: np.ndarray = np.cos(omega * time_window)
            basis_matrix: np.ndarray = np.column_stack((sine_basis, cosine_basis))
            voltage_coeffs: np.ndarray = np.linalg.lstsq(basis_matrix, voltage_values[mask], rcond=None)[0]
            current_coeffs: np.ndarray = np.linalg.lstsq(basis_matrix, current_values[mask], rcond=None)[0]
            voltage_angle_rad: float = float(np.arctan2(voltage_coeffs[1], voltage_coeffs[0]))
            current_angle_rad: float = float(np.arctan2(current_coeffs[1], current_coeffs[0]))
            angle_shift_deg: float = float((current_angle_rad - voltage_angle_rad) * 180.0 / np.pi)

            while angle_shift_deg > 180.0:
                angle_shift_deg -= 360.0

            while angle_shift_deg < -180.0:
                angle_shift_deg += 360.0

            return angle_shift_deg
        else:
            return None


def compute_signal_value_at_time(
    time_values: np.ndarray,
    signal_values: np.ndarray | None,
    target_time_s: float,
    scale: float,
) -> float | None:
    """
    Return one signal sample nearest to the requested time.

    :param time_values: EMT time vector.
    :param signal_values: Signal trajectory.
    :param target_time_s: Requested sample time.
    :param scale: Multiplicative scaling applied to the returned value.
    :return: Scaled sample value or None.
    """
    if signal_values is None:
        return None
    else:
        sample_index: int = int(np.argmin(np.abs(time_values - target_time_s)))
        sample_value: float = float(signal_values[sample_index] * scale)
        return sample_value


def compute_window_mean(
    time_values: np.ndarray,
    signal_values: np.ndarray | None,
    time_start_s: float,
    time_end_s: float,
    scale: float,
) -> float | None:
    """
    Compute one mean value over a selected time window.

    :param time_values: EMT time vector.
    :param signal_values: Signal trajectory.
    :param time_start_s: Start of the averaging window.
    :param time_end_s: End of the averaging window.
    :param scale: Multiplicative scaling applied before averaging.
    :return: Mean value or None.
    """
    if signal_values is None:
        return None
    else:
        mask: np.ndarray = np.logical_and(time_values >= time_start_s, time_values <= time_end_s)

        if bool(np.any(mask)):
            mean_value: float = float(np.mean(signal_values[mask] * scale))
            return mean_value
        else:
            print(f"No samples were found between {time_start_s:.3f} s and {time_end_s:.3f} s.")
            return None


def print_power_flow_diagnostics(
    case: PvCaseDefinition,
    objects: PvRunObjects,
    pf_results: PowerFlowResults,
    pf_results_3ph: PowerFlowResults3Ph,
) -> None:
    """
    Print the steady-state diagnostics required for the PV validation case.

    :param case: PV case definition.
    :param objects: Static network objects.
    :param pf_results: Balanced power-flow results.
    :param pf_results_3ph: 3-phase power-flow results.
    :return: None.
    """
    initial_pv_power_mw: float = -float(objects.pv_equivalent.P)
    expected_initial_available_power_mw: float = get_expected_initial_available_power_mw(case)

    print("\n" + "=" * 90)
    print(f"Balanced power flow results | {objects.display_name}")
    print("=" * 90)
    print(f"  converged                         : {pf_results.converged}")
    print(f"  3ph converged                     : {pf_results_3ph.converged}")
    print(f"  MPPT model                        : {get_mppt_model_description(objects.pv_level)}")
    print(f"  initial PV power from power flow  : {initial_pv_power_mw:.6f} MW")
    print(f"  initial irradiance                : {case.initial_irradiance_w_m2:.3f} W/m^2")
    print(f"  expected initial PV available P   : {expected_initial_available_power_mw:.6f} MW")
    print(f"  initial converter P0 schedule     : {get_initial_converter_power_schedule_mw(case):.6f} MW")
    print("  active-power sign note            : this PV example reports positive P for grid export")
    print(f"  irradiance event 1                : t = {case.irradiance_drop_time_s:.3f} s -> {case.irradiance_drop_w_m2:.3f} W/m^2")
    print(f"  irradiance event 2                : t = {case.irradiance_rise_time_s:.3f} s -> {case.irradiance_rise_w_m2:.3f} W/m^2")
    print()
    print(pf_results.get_bus_df())
    print(pf_results.get_branch_df())


def print_dynamic_diagnostics(
    case: PvCaseDefinition,
    objects: PvRunObjects,
    time_values: np.ndarray,
    data: dict[str, np.ndarray | None],
) -> None:
    """
    Print the dynamic validation metrics before and after the irradiance step.

    :param case: PV case definition.
    :param objects: Static network objects.
    :param time_values: EMT time vector.
    :param data: Collected signal dictionary.
    :return: None.
    """
    power_scale_mw: float = objects.grid.Sbase
    expected_drop_power_mw: float = get_expected_available_power_mw(case, case.irradiance_drop_w_m2)
    expected_rise_power_mw: float = get_expected_available_power_mw(case, case.irradiance_rise_w_m2)
    before_export_mw: float | None = compute_window_mean(
        time_values,
        data.get("p_grid_export_pu", None),
        0.10,
        case.irradiance_drop_time_s - 0.02,
        power_scale_mw,
    )
    after_drop_export_mw: float | None = compute_window_mean(
        time_values,
        data.get("p_grid_export_pu", None),
        case.irradiance_drop_time_s + 0.05,
        case.irradiance_rise_time_s - 0.02,
        power_scale_mw,
    )
    after_rise_export_mw: float | None = compute_window_mean(
        time_values,
        data.get("p_grid_export_pu", None),
        case.irradiance_rise_time_s + 0.05,
        case.simulation_time_s - 0.02,
        power_scale_mw,
    )
    initial_export_mw: float | None = compute_signal_value_at_time(time_values, data.get("p_grid_export_pu", None), 0.0, power_scale_mw)
    initial_pv_dc_power_mw: float | None = compute_signal_value_at_time(time_values, data.get("p_pv_pu", None), 0.0, power_scale_mw)
    initial_available_power_mw: float | None = compute_signal_value_at_time(time_values, data.get("p_avail_pu", None), 0.0, power_scale_mw)
    initial_mppt_power_mw: float | None = compute_signal_value_at_time(time_values, data.get("p_mppt_pu", None), 0.0, power_scale_mw)
    initial_q_mvar: float | None = compute_signal_value_at_time(time_values, data.get("q_ac_pu", None), 0.0, power_scale_mw)
    drop_export_mw: float | None = compute_signal_value_at_time(
        time_values,
        data.get("p_grid_export_pu", None),
        case.irradiance_drop_time_s + 0.12,
        power_scale_mw,
    )
    rise_export_mw: float | None = compute_signal_value_at_time(
        time_values,
        data.get("p_grid_export_pu", None),
        case.irradiance_rise_time_s + 0.12,
        power_scale_mw,
    )
    pre_event_p_abc_mw: float | None = compute_window_mean(
        time_values,
        data.get("p_abc_pu", None),
        0.10,
        case.irradiance_drop_time_s - 0.02,
        power_scale_mw,
    )
    pre_event_phase_shift_deg: float | None = compute_fundamental_phase_shift_deg(
        time_values,
        data.get("v_ac_a", None),
        data.get("i_a", None),
        0.10,
        case.irradiance_drop_time_s - 0.02,
        50.0,
    )
    pre_event_p_avail_mw: float | None = compute_window_mean(time_values, data.get("p_avail_pu", None), 0.10, case.irradiance_drop_time_s - 0.02, power_scale_mw)
    pre_event_p_mppt_mw: float | None = compute_window_mean(time_values, data.get("p_mppt_pu", None), 0.10, case.irradiance_drop_time_s - 0.02, power_scale_mw)
    pre_event_p_pv_mw: float | None = compute_window_mean(time_values, data.get("p_pv_pu", None), 0.10, case.irradiance_drop_time_s - 0.02, power_scale_mw)
    drop_p_pv_mw: float | None = compute_window_mean(time_values, data.get("p_pv_pu", None), case.irradiance_drop_time_s + 0.05, case.irradiance_rise_time_s - 0.02, power_scale_mw)
    rise_p_pv_mw: float | None = compute_window_mean(time_values, data.get("p_pv_pu", None), case.irradiance_rise_time_s + 0.05, case.simulation_time_s - 0.02, power_scale_mw)

    print("\n" + "=" * 90)
    print(f"PV EMT dynamic metrics | {objects.display_name}")
    print("=" * 90)
    print(f"  expected initial available power  : {get_expected_initial_available_power_mw(case):.6f} MW")
    print(f"  PF initial active injection       : {-float(objects.pv_equivalent.P):.6f} MW")

    if initial_available_power_mw is not None:
        print(f"  EMT initial available PV power    : {initial_available_power_mw:.6f} MW")
    else:
        print("  EMT initial available PV power    : unavailable")

    if initial_mppt_power_mw is not None:
        print(f"  EMT initial MPPT target power     : {initial_mppt_power_mw:.6f} MW")
    else:
        print("  EMT initial MPPT target power     : unavailable")

    if initial_pv_dc_power_mw is not None:
        print(f"  EMT initial PV DC power           : {initial_pv_dc_power_mw:.6f} MW")
    else:
        print("  EMT initial PV DC power           : unavailable")

    if initial_export_mw is not None:
        print(f"  EMT initial AC export             : {initial_export_mw:.6f} MW")
    else:
        print("  EMT initial AC export             : unavailable")

    if initial_q_mvar is not None:
        print(f"  EMT initial Q AC                  : {initial_q_mvar:.6f} MVAr")
    else:
        print("  EMT initial Q AC                  : unavailable")

    if before_export_mw is not None:
        print(f"  mean AC export before drop        : {before_export_mw:.6f} MW")
    else:
        print("  mean AC export before drop        : unavailable")

    if after_drop_export_mw is not None:
        print(f"  mean AC export after drop         : {after_drop_export_mw:.6f} MW")
    else:
        print("  mean AC export after drop         : unavailable")

    if after_rise_export_mw is not None:
        print(f"  mean AC export after rise         : {after_rise_export_mw:.6f} MW")
    else:
        print("  mean AC export after rise         : unavailable")

    if pre_event_p_abc_mw is not None:
        print(f"  mean abc instantaneous power      : {pre_event_p_abc_mw:.6f} MW")
    else:
        print("  mean abc instantaneous power      : unavailable")

    if pre_event_phase_shift_deg is not None:
        print(f"  phase-A current minus voltage     : {pre_event_phase_shift_deg:.6f} deg")
    else:
        print("  phase-A current minus voltage     : unavailable")

    if pre_event_p_avail_mw is not None and pre_event_p_mppt_mw is not None and pre_event_p_pv_mw is not None:
        print(f"  pre-event Pavail/Pmppt/Ppv        : {pre_event_p_avail_mw:.6f} / {pre_event_p_mppt_mw:.6f} / {pre_event_p_pv_mw:.6f} MW")
    else:
        print("  pre-event Pavail/Pmppt/Ppv        : unavailable")

    if drop_p_pv_mw is not None and rise_p_pv_mw is not None:
        print(f"  post-step Ppv drop/rise           : {drop_p_pv_mw:.6f} / {rise_p_pv_mw:.6f} MW")
    else:
        print("  post-step Ppv drop/rise           : unavailable")

    if drop_export_mw is not None:
        print(f"  export near drop final level      : {drop_export_mw:.6f} MW (target {expected_drop_power_mw:.6f} MW)")
    else:
        print("  export near drop final level      : unavailable")

    if rise_export_mw is not None:
        print(f"  export near rise final level      : {rise_export_mw:.6f} MW (target {expected_rise_power_mw:.6f} MW)")
    else:
        print("  export near rise final level      : unavailable")

    p_avail_signal: np.ndarray | None = data.get("p_avail_pu", None)
    p_ac_signal: np.ndarray | None = data.get("p_ac_internal_pu", None)
    p_grid_export_signal: np.ndarray | None = data.get("p_grid_export_pu", None)
    i_pv_signal: np.ndarray | None = data.get("i_pv", None)
    i_a_signal: np.ndarray | None = data.get("i_a", None)
    v_dc_signal: np.ndarray | None = data.get("v_dc_internal", None)

    if p_avail_signal is not None:
        print(f"  min/max available PV power        : {float(np.min(p_avail_signal) * power_scale_mw):.6f} / {float(np.max(p_avail_signal) * power_scale_mw):.6f} MW")
    else:
        print("  min/max available PV power        : unavailable")

    if p_ac_signal is not None:
        print(f"  initial/final P AC internal       : {float(p_ac_signal[0] * power_scale_mw):.6f} / {float(p_ac_signal[-1] * power_scale_mw):.6f} MW")
    else:
        print("  initial/final P AC internal       : unavailable")

    if p_grid_export_signal is not None:
        print(f"  initial/final P grid export       : {float(p_grid_export_signal[0] * power_scale_mw):.6f} / {float(p_grid_export_signal[-1] * power_scale_mw):.6f} MW")
    else:
        print("  initial/final P grid export       : unavailable")

    if i_pv_signal is not None:
        print(f"  min/max PV DC current             : {float(np.min(i_pv_signal)):.6f} / {float(np.max(i_pv_signal)):.6f} pu")
    else:
        print("  min/max PV DC current             : unavailable")

    if i_a_signal is not None:
        print(f"  min/max converter phase-A current : {float(np.min(i_a_signal)):.6f} / {float(np.max(i_a_signal)):.6f} pu")
    else:
        print("  min/max converter phase-A current : unavailable")

    if v_dc_signal is not None:
        print(f"  min/max internal DC-link voltage  : {float(np.min(v_dc_signal)):.6f} / {float(np.max(v_dc_signal)):.6f} pu")
    else:
        print("  min/max internal DC-link voltage  : unavailable")


def validate_signal_window(
    signal_name: str,
    actual_value: float | None,
    expected_value: float,
    tolerance: float,
) -> None:
    """
    Validate one scalar metric against an expected value.

    :param signal_name: Human-readable metric name.
    :param actual_value: Measured value.
    :param expected_value: Target value.
    :param tolerance: Allowed absolute error.
    :return: None.
    """
    if actual_value is None:
        raise RuntimeError(f"Validation metric '{signal_name}' is unavailable.")
    else:
        if abs(actual_value - expected_value) <= tolerance:
            return
        else:
            raise RuntimeError(
                f"Validation failed for '{signal_name}': value = {actual_value:.6f}, "
                f"expected = {expected_value:.6f} +/- {tolerance:.6f}."
            )


def validate_dynamic_response(
    case: PvCaseDefinition,
    objects: PvRunObjects,
    time_values: np.ndarray,
    data: dict[str, np.ndarray | None],
) -> None:
    """
    Run the acceptance checks required by the PV EMT example.

    :param case: PV case definition.
    :param objects: Static network objects.
    :param time_values: EMT time vector.
    :param data: Collected signal dictionary.
    :return: None.
    """
    power_scale_mw: float = objects.grid.Sbase
    pre_event_export_mw: float | None = compute_window_mean(
        time_values,
        data.get("p_grid_export_pu", None),
        0.10,
        case.irradiance_drop_time_s - 0.02,
        power_scale_mw,
    )
    post_drop_export_mw: float | None = compute_window_mean(
        time_values,
        data.get("p_grid_export_pu", None),
        case.irradiance_drop_time_s + 0.05,
        case.irradiance_rise_time_s - 0.02,
        power_scale_mw,
    )
    post_rise_export_mw: float | None = compute_window_mean(
        time_values,
        data.get("p_grid_export_pu", None),
        case.irradiance_rise_time_s + 0.05,
        case.simulation_time_s - 0.02,
        power_scale_mw,
    )
    mean_q_mvar: float | None = compute_window_mean(
        time_values,
        data.get("q_ac_pu", None),
        0.10,
        case.simulation_time_s - 0.02,
        power_scale_mw,
    )
    p_grid_export_signal: np.ndarray | None = data.get("p_grid_export_pu", None)
    p_curt_signal: np.ndarray | None = data.get("p_curt_pu", None)
    v_dc_signal: np.ndarray | None = data.get("v_dc_internal", None)
    i_a_signal: np.ndarray | None = data.get("i_a", None)
    i_b_signal: np.ndarray | None = data.get("i_b", None)
    i_c_signal: np.ndarray | None = data.get("i_c", None)

    validate_signal_window("pre-event AC export", pre_event_export_mw, get_expected_initial_available_power_mw(case), 0.35)
    validate_signal_window(
        "post-drop AC export",
        post_drop_export_mw,
        get_expected_available_power_mw(case, case.irradiance_drop_w_m2),
        0.40,
    )
    validate_signal_window(
        "post-rise AC export",
        post_rise_export_mw,
        get_expected_available_power_mw(case, case.irradiance_rise_w_m2),
        0.75,
    )
    validate_signal_window("mean AC reactive power", mean_q_mvar, case.reactive_power_mvar, 0.20)

    if v_dc_signal is None:
        raise RuntimeError("Validation metric 'internal DC voltage' is unavailable.")
    else:
        if float(np.min(v_dc_signal)) < 0.90 or float(np.max(v_dc_signal)) > 1.10:
            raise RuntimeError(
                f"Validation failed for internal DC voltage bounds: min = {float(np.min(v_dc_signal)):.6f}, "
                f"max = {float(np.max(v_dc_signal)):.6f}."
            )

    if p_grid_export_signal is None:
        raise RuntimeError("Validation metric 'AC export sign' is unavailable.")
    else:
        if float(np.min(p_grid_export_signal)) < -1.0e-3:
            raise RuntimeError(
                f"Validation failed because AC export became negative: min = {float(np.min(p_grid_export_signal) * power_scale_mw):.6f} MW."
            )

    if p_curt_signal is None:
        raise RuntimeError("Validation metric 'PV curtailment' is unavailable.")
    else:
        if float(np.min(p_curt_signal)) < -1.0e-8:
            raise RuntimeError(
                f"Validation failed because PV curtailment became negative: min = {float(np.min(p_curt_signal)):.6e} pu."
            )

    phase_shift_deg: float | None = compute_fundamental_phase_shift_deg(
        time_values,
        data.get("v_ac_a", None),
        data.get("i_a", None),
        0.10,
        case.irradiance_drop_time_s - 0.02,
        50.0,
    )
    validate_signal_window("pre-event phase displacement", phase_shift_deg, 0.0, 10.0)

    if i_a_signal is None or i_b_signal is None or i_c_signal is None:
        raise RuntimeError("Validation metric 'phase-current balance' is unavailable.")
    else:
        pre_mask: np.ndarray = np.logical_and(time_values >= 0.10, time_values <= case.irradiance_drop_time_s - 0.02)
        mean_i_a: float = float(np.mean(i_a_signal[pre_mask]))
        mean_i_b: float = float(np.mean(i_b_signal[pre_mask]))
        mean_i_c: float = float(np.mean(i_c_signal[pre_mask]))
        max_neutral_sum: float = float(np.max(np.abs(i_a_signal[pre_mask] + i_b_signal[pre_mask] + i_c_signal[pre_mask])))

        if max(abs(mean_i_a), abs(mean_i_b), abs(mean_i_c)) > 2.0e-3 or max_neutral_sum > 2.0e-3:
            raise RuntimeError(
                f"Validation failed for phase-current balance: means = {mean_i_a:.6e}, {mean_i_b:.6e}, {mean_i_c:.6e}; "
                f"max |iA+iB+iC| = {max_neutral_sum:.6e}."
            )


def plot_signal_if_available(
    axis: Any,
    time_values: np.ndarray,
    signal_values: np.ndarray | None,
    label: str,
    color: str,
) -> bool:
    """
    Plot one trace if the underlying signal exists.

    :param axis: Matplotlib axis.
    :param time_values: EMT time vector.
    :param signal_values: Signal trajectory.
    :param label: Trace label.
    :param color: Matplotlib color string.
    :return: True if the trace was plotted.
    """
    if signal_values is None:
        return False
    else:
        axis.plot(time_values, signal_values, color=color, label=label)
        return True


def finalize_axis(axis: Any, title: str, ylabel: str, show_legend: bool) -> None:
    """
    Apply the common axis formatting used by the validation plots.

    :param axis: Matplotlib axis.
    :param title: Axis title.
    :param ylabel: Axis y-label.
    :param show_legend: Whether to show a legend.
    :return: None.
    """
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(True)

    if show_legend:
        axis.legend(loc="upper right")
    else:
        axis.text(0.02, 0.5, "Signal unavailable", transform=axis.transAxes)


def plot_results(
    case: PvCaseDefinition,
    objects: PvRunObjects,
    time_values: np.ndarray,
    data: dict[str, np.ndarray | None],
) -> None:
    """
    Generate the PV validation plots requested for the EMT example.

    :param case: PV case definition.
    :param objects: Static network objects.
    :param time_values: EMT time vector.
    :param data: Collected signal dictionary.
    :return: None.
    """
    power_scale_mw: float = objects.grid.Sbase
    figure, axes = plt.subplots(9, 1, figsize=(14, 27), sharex=True)
    figure.suptitle(f"PV EMT example | {objects.display_name}")

    show_legend: bool = False
    show_legend = plot_signal_if_available(axes[0], time_values, data.get("irradiance", None), "Irradiance", "tab:orange")
    axes[0].axvline(case.irradiance_drop_time_s, color="black", linestyle="--", linewidth=1.0)
    axes[0].axvline(case.irradiance_rise_time_s, color="black", linestyle=":", linewidth=1.0)
    finalize_axis(axes[0], "Irradiance versus time", "W/m^2", show_legend)

    show_legend = False
    p_avail_mw: np.ndarray | None = None
    p_pv_mw: np.ndarray | None = None
    p_mppt_mw: np.ndarray | None = None
    p_ac_internal_mw: np.ndarray | None = None
    p_grid_export_mw: np.ndarray | None = None
    q_ac_mvar: np.ndarray | None = None
    p_curt_mw: np.ndarray | None = None
    p_to_vsc_mw: np.ndarray | None = None

    if data.get("p_avail_pu", None) is not None:
        p_avail_mw = data.get("p_avail_pu", None) * power_scale_mw
    else:
        p_avail_mw = None

    if data.get("p_pv_pu", None) is not None:
        p_pv_mw = data.get("p_pv_pu", None) * power_scale_mw
    else:
        p_pv_mw = None

    if data.get("p_mppt_pu", None) is not None:
        p_mppt_mw = data.get("p_mppt_pu", None) * power_scale_mw
    else:
        p_mppt_mw = None

    if data.get("p_ac_internal_pu", None) is not None:
        p_ac_internal_mw = data.get("p_ac_internal_pu", None) * power_scale_mw
    else:
        p_ac_internal_mw = None

    if data.get("p_grid_export_pu", None) is not None:
        p_grid_export_mw = data.get("p_grid_export_pu", None) * power_scale_mw
    else:
        p_grid_export_mw = None

    if data.get("q_ac_pu", None) is not None:
        q_ac_mvar = data.get("q_ac_pu", None) * power_scale_mw
    else:
        q_ac_mvar = None

    if data.get("p_curt_pu", None) is not None:
        p_curt_mw = data.get("p_curt_pu", None) * power_scale_mw
    else:
        p_curt_mw = None

    if data.get("p_to_vsc_pu", None) is not None:
        p_to_vsc_mw = data.get("p_to_vsc_pu", None) * power_scale_mw
    else:
        p_to_vsc_mw = None

    if plot_signal_if_available(axes[1], time_values, p_avail_mw, "P available", "tab:green"):
        show_legend = True
    else:
        show_legend = show_legend
    if plot_signal_if_available(axes[1], time_values, p_pv_mw, "P PV DC diagnostic", "tab:blue"):
        show_legend = True
    else:
        show_legend = show_legend
    if plot_signal_if_available(axes[1], time_values, p_mppt_mw, "P MPPT", "tab:red"):
        show_legend = True
    else:
        show_legend = show_legend

    if objects.pv_level == PvEmtModelLevel.LEVEL_2:
        if plot_signal_if_available(axes[1], time_values, p_to_vsc_mw, "P to VSC", "tab:red"):
            show_legend = True
        else:
            show_legend = show_legend
        finalize_axis(axes[1], "PV available, source and boost-output power", "MW", show_legend)
    else:
        finalize_axis(axes[1], "PV available power and PV DC power", "MW", show_legend)

    show_legend = plot_signal_if_available(axes[2], time_values, data.get("i_pv", None), "I PV DC diagnostic", "tab:purple")
    finalize_axis(axes[2], "PV DC current versus time", "pu", show_legend)

    show_legend = False
    if plot_signal_if_available(axes[3], time_values, data.get("v_dc_internal", None), "Internal Vdc", "tab:blue"):
        show_legend = True
    else:
        show_legend = show_legend
    source_voltage_label: str = "PV source Vdc ref"

    if objects.pv_level == PvEmtModelLevel.LEVEL_2:
        source_voltage_label = "PV-side voltage"
    else:
        source_voltage_label = source_voltage_label

    if plot_signal_if_available(axes[3], time_values, data.get("v_dc_source", None), source_voltage_label, "tab:orange"):
        show_legend = True
    else:
        show_legend = show_legend

    if objects.pv_level == PvEmtModelLevel.LEVEL_2:
        finalize_axis(axes[3], "DC-link and PV-side voltage versus time", "pu", show_legend)
    else:
        finalize_axis(axes[3], "DC-link voltage versus time", "pu", show_legend)

    show_legend = False
    if plot_signal_if_available(axes[4], time_values, p_ac_internal_mw, "P AC internal", "tab:blue"):
        show_legend = True
    else:
        show_legend = show_legend
    if plot_signal_if_available(axes[4], time_values, p_grid_export_mw, "P grid export", "tab:green"):
        show_legend = True
    else:
        show_legend = show_legend
    if plot_signal_if_available(axes[4], time_values, q_ac_mvar, "Q AC", "tab:red"):
        show_legend = True
    else:
        show_legend = show_legend
    finalize_axis(axes[4], "Converter AC active and reactive power", "MW / MVAr", show_legend)

    show_legend = False
    if plot_signal_if_available(axes[5], time_values, data.get("i_a", None), "iA", "tab:blue"):
        show_legend = True
    else:
        show_legend = show_legend
    if plot_signal_if_available(axes[5], time_values, data.get("i_b", None), "iB", "tab:orange"):
        show_legend = True
    else:
        show_legend = show_legend
    if plot_signal_if_available(axes[5], time_values, data.get("i_c", None), "iC", "tab:green"):
        show_legend = True
    else:
        show_legend = show_legend
    finalize_axis(axes[5], "Three-phase AC currents at the converter terminal", "pu", show_legend)

    show_legend = False
    if plot_signal_if_available(axes[6], time_values, data.get("v_ac_a", None), "vA", "tab:blue"):
        show_legend = True
    else:
        show_legend = show_legend
    if plot_signal_if_available(axes[6], time_values, data.get("v_ac_b", None), "vB", "tab:orange"):
        show_legend = True
    else:
        show_legend = show_legend
    if plot_signal_if_available(axes[6], time_values, data.get("v_ac_c", None), "vC", "tab:green"):
        show_legend = True
    else:
        show_legend = show_legend
    finalize_axis(axes[6], "Three-phase AC voltages at the converter terminal", "pu", show_legend)

    show_legend = False
    p_abc_mw: np.ndarray | None = None

    if data.get("p_abc_pu", None) is not None:
        p_abc_mw = data.get("p_abc_pu", None) * power_scale_mw
    else:
        p_abc_mw = None

    if plot_signal_if_available(axes[7], time_values, p_ac_internal_mw, "P AC internal", "tab:blue"):
        show_legend = True
    else:
        show_legend = show_legend
    if plot_signal_if_available(axes[7], time_values, p_abc_mw, "P abc", "tab:orange"):
        show_legend = True
    else:
        show_legend = show_legend
    if plot_signal_if_available(axes[7], time_values, p_grid_export_mw, "P grid export", "tab:green"):
        show_legend = True
    else:
        show_legend = show_legend
    finalize_axis(axes[7], "Power-sign consistency check", "MW", show_legend)

    show_legend = False
    if objects.pv_level == PvEmtModelLevel.LEVEL_1:
        if plot_signal_if_available(axes[8], time_values, p_mppt_mw, "P MPPT target", "tab:red"):
            show_legend = True
        else:
            show_legend = show_legend
    else:
        if plot_signal_if_available(axes[8], time_values, data.get("duty", None), "Boost duty cycle", "tab:red"):
            show_legend = True
        else:
            show_legend = show_legend
    if plot_signal_if_available(axes[8], time_values, p_curt_mw, "P curtailed", "tab:gray"):
        show_legend = True
    else:
        show_legend = show_legend

    if objects.pv_level == PvEmtModelLevel.LEVEL_2:
        finalize_axis(axes[8], "Boost duty cycle and curtailed PV power", "MW / pu", show_legend)
    else:
        finalize_axis(axes[8], "MPPT target and curtailed PV power", "MW", show_legend)
    axes[8].set_xlabel("Time [s]")

    figure.tight_layout()
    plt.show()


def run_pv_emt_case(case: PvCaseDefinition, pv_level: PvEmtModelLevel, scenario: PvScenario) -> None:
    """
    Build, initialize, simulate and plot one PV EMT validation run.

    :param case: PV case definition.
    :param pv_level: Selected PV model level.
    :param scenario: Selected scripted scenario.
    :return: None.
    """
    objects: PvRunObjects = build_grid(case=case, pv_level=pv_level, scenario=scenario)
    pf_results: PowerFlowResults = run_power_flow(objects.grid)
    pf_results_3ph: PowerFlowResults3Ph = run_power_flow_3ph(objects.grid)
    print_power_flow_diagnostics(case, objects, pf_results, pf_results_3ph)

    if pf_results.converged:
        pass
    else:
        print(f"Power flow did not converge for PV case '{objects.display_name}'.")
        return

    if pf_results_3ph.converged:
        pass
    else:
        print(f"3-phase power flow did not converge for PV case '{objects.display_name}'.")
        return

    blocks: PvEmtBlocks = attach_emt_models(objects, case)
    event_group: EmtEventsGroup | None = add_irradiance_events(
        grid=objects.grid,
        pv_block=blocks.pv_mdl,
        case=case,
        pv_level=objects.pv_level,
        pv_model_name=objects.pv_model_name,
    )
    problem: EmtProblemDae = build_problem(objects.grid, pf_results, pf_results_3ph, case, event_group)
    validate_initialization(problem)

    solver: StructuralCompiledSolver = build_solver(problem)
    time_values: np.ndarray
    y_values: np.ndarray
    _dx_values: np.ndarray
    well_initialized: bool
    converged: bool
    time_values, y_values, _dx_values, well_initialized, converged = solver.simulate()

    print(f"well_initialized = {well_initialized}")
    print(f"converged = {converged}")

    if converged:
        data: dict[str, np.ndarray | None] = build_plot_data(problem, objects, blocks, y_values, time_values, case)
        print_dynamic_diagnostics(case, objects, time_values, data)
        try:
            validate_dynamic_response(case, objects, time_values, data)
            print(f"Validation checks: passed | {objects.display_name}")
        except RuntimeError as exc:
            print(f"Validation checks: failed | {objects.display_name} -> {exc}")
        plot_results(case, objects, time_values, data)
    else:
        print(f"EMT simulation did not converge, so validation plots were not produced for {objects.display_name}.")


def run_selected_pv_examples(case: PvCaseDefinition, scenario: PvScenario) -> None:
    """
    Run the selected PV EMT example flow.

    The current PV irradiance-step script only defines the ``both`` example. In
    that flow, the same scenario is executed twice: once with PV Level 1 and
    once with PV Level 2.

    :param case: PV case definition.
    :param scenario: Selected scripted scenario.
    :return: None.
    :raises ValueError: If an unsupported scenario is requested.
    """
    if scenario == PvScenario.BOTH:
        run_pv_emt_case(case=case, pv_level=PvEmtModelLevel.LEVEL_1, scenario=scenario)
        run_pv_emt_case(case=case, pv_level=PvEmtModelLevel.LEVEL_2, scenario=scenario)
        return

    raise ValueError(
        "The current PV EMT irradiance-step script does not define standalone charge or discharge scenarios. "
        f"Requested scenario: {scenario.value}."
    )


def main() -> None:
    """
    Run the PV EMT validation example.

    :return: None.
    """
    case: PvCaseDefinition = build_case_definition()
    run_selected_pv_examples(case=case, scenario=PvScenario.BOTH)


if __name__ == "__main__":
    main()
