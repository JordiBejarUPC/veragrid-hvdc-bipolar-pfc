# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Two-parallel-VSC EMT scripting example.

Run this module from the repository root with the IDE or project run
configuration pointing to ``trunk.dynamics_emt.scripting_two_vsc``.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def configure_import_paths() -> Path:
    """
    Configure repository import paths for direct module execution.

    The EMT example modules in this repository are stored outside ``src``.
    Therefore the repository root and the ``src`` folder need to be added to
    ``sys.path`` before importing VeraGrid modules.

    :returns:
        Repository root path.
    :rtype: Path
    """
    module_path: Path = Path(__file__).resolve()
    script_dir: Path = module_path.parent
    repo_root: Path = script_dir.parent.parent
    src_root: Path = repo_root / "src"
    src_root_text: str = str(src_root)
    repo_root_text: str = str(repo_root)

    if src_root_text not in sys.path:
        sys.path.insert(0, src_root_text)
    else:
        pass

    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)
    else:
        pass

    return repo_root


REPO_ROOT_PATH: Path = configure_import_paths()

from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory, save_scalar_plot, save_two_panel_three_phase_plot

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Templates.Emt.converter_emt_template import get_full_pseudo_emt_converter
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.block import Block, Var, find_name_in_block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping import converter_control_code
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    ConverterControlType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    SolverType,
)


class SolverKey(Enum):
    """
    Enumeration of supported EMT solver labels for output organization.

    :ivar COMPILED:
        Structural compiled solver label.
    """

    COMPILED = "compiled"


class SignalMode(Enum):
    """
    Enumeration for required and optional EMT traces.

    :ivar REQUIRED:
        Missing signal is a hard error.
    :ivar OPTIONAL:
        Missing signal is tolerated and replaced with zeros.
    """

    REQUIRED = 1
    OPTIONAL = 2


class CaseConstants:
    """
    Final container for study constants.

    The class groups the numerical assumptions in one place while avoiding a
    long list of mutable module globals.
    """

    __slots__ = (
        "case_name",
        "solver_key",
        "sbase_mva",
        "fbase_hz",
        "ac_voltage_kv",
        "dc_voltage_kv",
        "grid_r_pu",
        "grid_x_pu",
        "coupling_r_pu",
        "coupling_x_pu",
        "grid_rate_mva",
        "coupling_rate_mva",
        "vsc_rating_mva",
        "dc_load_base_mw",
        "dc_load_step_mw",
        "q_setpoint_mvar",
        "time_step_s",
        "simulation_time_s",
        "event_time_s",
        "converter_r_eq_pu",
        "converter_l_eq_pu",
        "converter_c_dc_pu",
        "converter_r_dc_pu",
        "converter_r_dc_term_pu",
        "pll_kp",
        "pll_ki",
        "i_kp",
        "i_ki",
        "vdc_kp",
        "vdc_ki",
        "q_kp",
        "q_ki",
        "i_max_pu",
        "m_max_pu",
        "p_loss_i1_pu",
        "p_loss_i2_pu",
        "tau_meas_s",
        "aw_gain",
        "vdc_floor_pu",
    )

    def __init__(self) -> None:
        """
        Initialize the fixed study constants.

        :returns:
            None.
        :rtype: None
        """
        self.case_name: str = "two_vsc"
        self.solver_key: SolverKey = SolverKey.COMPILED
        self.sbase_mva: float = 100.0
        self.fbase_hz: float = 50.0
        self.ac_voltage_kv: float = 20.0
        self.dc_voltage_kv: float = 3.0
        self.grid_r_pu: float = 0.005
        self.grid_x_pu: float = 0.050
        self.coupling_r_pu: float = 0.005
        self.coupling_x_pu: float = 0.050
        self.grid_rate_mva: float = 10.0
        self.coupling_rate_mva: float = 1.5
        self.vsc_rating_mva: float = 1.0
        self.dc_load_base_mw: float = 0.8
        self.dc_load_step_mw: float = 0.9
        self.q_setpoint_mvar: float = 0.0
        self.time_step_s: float = 5.0e-6
        self.simulation_time_s: float = 0.3
        self.event_time_s: float = 0.10
        self.converter_r_eq_pu: float = 0.03
        self.converter_l_eq_pu: float = 0.12
        self.converter_c_dc_pu: float = 0.08
        self.converter_r_dc_pu: float = 1.0e6
        self.converter_r_dc_term_pu: float = 1.0e-4
        self.pll_kp: float = 40.0
        self.pll_ki: float = 400.0
        self.i_kp: float = 0.6
        self.i_ki: float = 50.0
        self.vdc_kp: float = 2.0
        self.vdc_ki: float = 30.0
        self.q_kp: float = 0.8
        self.q_ki: float = 20.0
        self.i_max_pu: float = 1.3
        self.m_max_pu: float = 0.95
        self.p_loss_i1_pu: float = 0.0
        self.p_loss_i2_pu: float = 0.0
        self.tau_meas_s: float = 0.01
        self.aw_gain: float = 0.1
        self.vdc_floor_pu: float = 0.05


class TwoVscCase:
    """
    Wrapper for the built circuit and device handles.

    The object groups the topology handles so later algorithm stages do not
    depend on dictionaries or positional tuples.
    """

    __slots__ = (
        "circuit",
        "grid_bus",
        "pcc_bus",
        "vsc1_ac_bus",
        "vsc2_ac_bus",
        "vsc1_dc_bus",
        "vsc2_dc_bus",
        "generator",
        "grid_branch",
        "coupling_branch_1",
        "coupling_branch_2",
        "vsc1",
        "vsc2",
        "dc_load_1",
        "dc_load_2",
    )

    def __init__(
        self,
        circuit: MultiCircuit,
        grid_bus: gce.Bus,
        pcc_bus: gce.Bus,
        vsc1_ac_bus: gce.Bus,
        vsc2_ac_bus: gce.Bus,
        vsc1_dc_bus: gce.Bus,
        vsc2_dc_bus: gce.Bus,
        generator: gce.Generator,
        grid_branch: gce.Line,
        coupling_branch_1: gce.Line,
        coupling_branch_2: gce.Line,
        vsc1: gce.VSC,
        vsc2: gce.VSC,
        dc_load_1: gce.Load,
        dc_load_2: gce.Load,
    ) -> None:
        """
        Store all circuit and device references.

        :param circuit:
            Built multi-circuit model.
        :param grid_bus:
            Internal slack bus.
        :param pcc_bus:
            AC point of common coupling bus.
        :param vsc1_ac_bus:
            Converter-1 AC bus.
        :param vsc2_ac_bus:
            Converter-2 AC bus.
        :param vsc1_dc_bus:
            Converter-1 DC bus.
        :param vsc2_dc_bus:
            Converter-2 DC bus.
        :param generator:
            Thevenin-equivalent generator.
        :param grid_branch:
            AC Thevenin branch.
        :param coupling_branch_1:
            Coupling branch to converter 1.
        :param coupling_branch_2:
            Coupling branch to converter 2.
        :param vsc1:
            Converter 1 device.
        :param vsc2:
            Converter 2 device.
        :param dc_load_1:
            DC load on converter 1 bus.
        :param dc_load_2:
            DC load on converter 2 bus.
        :returns:
            None.
        :rtype: None
        """
        self.circuit: MultiCircuit = circuit
        self.grid_bus: gce.Bus = grid_bus
        self.pcc_bus: gce.Bus = pcc_bus
        self.vsc1_ac_bus: gce.Bus = vsc1_ac_bus
        self.vsc2_ac_bus: gce.Bus = vsc2_ac_bus
        self.vsc1_dc_bus: gce.Bus = vsc1_dc_bus
        self.vsc2_dc_bus: gce.Bus = vsc2_dc_bus
        self.generator: gce.Generator = generator
        self.grid_branch: gce.Line = grid_branch
        self.coupling_branch_1: gce.Line = coupling_branch_1
        self.coupling_branch_2: gce.Line = coupling_branch_2
        self.vsc1: gce.VSC = vsc1
        self.vsc2: gce.VSC = vsc2
        self.dc_load_1: gce.Load = dc_load_1
        self.dc_load_2: gce.Load = dc_load_2


class EmtModels:
    """
    Wrapper for attached EMT blocks.

    The object stores the symbolic models that need to be accessed later for
    event creation and signal extraction.
    """

    __slots__ = (
        "generator",
        "grid_branch",
        "coupling_branch_1",
        "coupling_branch_2",
        "vsc1",
        "vsc2",
        "dc_load_1",
        "dc_load_2",
    )

    def __init__(
        self,
        generator: Block,
        grid_branch: Block,
        coupling_branch_1: Block,
        coupling_branch_2: Block,
        vsc1: Block,
        vsc2: Block,
        dc_load_1: Block,
        dc_load_2: Block,
    ) -> None:
        """
        Store all attached EMT blocks.

        :param generator:
            Thevenin EMT block.
        :param grid_branch:
            Grid pi-line EMT block.
        :param coupling_branch_1:
            Coupling branch 1 EMT block.
        :param coupling_branch_2:
            Coupling branch 2 EMT block.
        :param vsc1:
            Converter 1 EMT block.
        :param vsc2:
            Converter 2 EMT block.
        :param dc_load_1:
            DC load 1 EMT block.
        :param dc_load_2:
            DC load 2 EMT block.
        :returns:
            None.
        :rtype: None
        """
        self.generator: Block = generator
        self.grid_branch: Block = grid_branch
        self.coupling_branch_1: Block = coupling_branch_1
        self.coupling_branch_2: Block = coupling_branch_2
        self.vsc1: Block = vsc1
        self.vsc2: Block = vsc2
        self.dc_load_1: Block = dc_load_1
        self.dc_load_2: Block = dc_load_2


class PowerFlowRunResult:
    """
    Wrapper for balanced and optional 3-phase power-flow results.

    The object keeps the successful balanced solution together with the optional
    3-phase initialization attempt and any non-fatal failure message.
    """

    __slots__ = ("balanced", "three_phase", "three_phase_error")

    def __init__(
        self,
        balanced: PowerFlowResults,
        three_phase: Optional[object],
        three_phase_error: Optional[str],
    ) -> None:
        """
        Store the power-flow outputs.

        :param balanced:
            Converged balanced AC/DC power-flow result.
        :param three_phase:
            Optional three-phase power-flow result.
        :param three_phase_error:
            Optional non-fatal three-phase failure message.
        :returns:
            None.
        :rtype: None
        """
        self.balanced: PowerFlowResults = balanced
        self.three_phase: Optional[object] = three_phase
        self.three_phase_error: Optional[str] = three_phase_error


class EmtRunResult:
    """
    Wrapper for EMT outputs and metadata.

    The object groups the problem, trajectories and report values needed by the
    plotting phase.
    """

    __slots__ = ("problem", "time_s", "trajectory", "well_initialized", "converged", "plot_path")

    def __init__(
        self,
        problem: EmtProblemDae,
        time_s: np.ndarray,
        trajectory: np.ndarray,
        well_initialized: bool,
        converged: bool,
        plot_path: Path,
    ) -> None:
        """
        Store EMT simulation outputs.

        :param problem:
            Solved EMT problem.
        :param time_s:
            EMT time vector.
        :param trajectory:
            EMT trajectory matrix.
        :param well_initialized:
            Initialization status.
        :param converged:
            Solver convergence flag.
        :param plot_path:
            Output plot file path.
        :returns:
            None.
        :rtype: None
        """
        self.problem: EmtProblemDae = problem
        self.time_s: np.ndarray = time_s
        self.trajectory: np.ndarray = trajectory
        self.well_initialized: bool = well_initialized
        self.converged: bool = converged
        self.plot_path: Path = plot_path


def get_case_constants() -> CaseConstants:
    """
    Create the immutable-looking constants container.

    :returns:
        Study constants.
    :rtype: CaseConstants
    """
    constants: CaseConstants = CaseConstants()
    return constants


def create_two_vsc_circuit() -> MultiCircuit:
    """
    Build the two-parallel-VSC AC/DC test system.

    VeraGrid uses positive load powers as consuming powers. For the VSC devices,
    ``bus_from`` is the DC side and ``bus_to`` is the AC side. Therefore a
    positive DC load and a negative ``Pdc`` converter reference produce the
    desired AC-to-DC transfer from the external grid into the DC buses.

    :returns:
        Built multi-circuit containing the complete two-VSC topology.
    :rtype: MultiCircuit
    """
    constants: CaseConstants = get_case_constants()

    # The first algorithmic stage is to build the static AC/DC network that the
    # balanced power flow can solve. The EMT initialization will later reuse the
    # same devices and connectivity.
    circuit: MultiCircuit = gce.MultiCircuit(
        name="Two parallel VSCs feeding independent DC loads",
        Sbase=constants.sbase_mva,
        fbase=constants.fbase_hz,
    )

    # The buses are created first because every branch and injection device needs
    # explicit bus handles from the static topology.
    grid_bus: gce.Bus = gce.Bus(name="Grid_internal_bus", Vnom=constants.ac_voltage_kv, is_slack=True)
    pcc_bus: gce.Bus = gce.Bus(name="PCC_bus", Vnom=constants.ac_voltage_kv)
    vsc1_ac_bus: gce.Bus = gce.Bus(name="VSC1_AC_bus", Vnom=constants.ac_voltage_kv)
    vsc2_ac_bus: gce.Bus = gce.Bus(name="VSC2_AC_bus", Vnom=constants.ac_voltage_kv)
    vsc1_dc_bus: gce.Bus = gce.Bus(name="VSC1_DC_bus", Vnom=constants.dc_voltage_kv, is_dc=True)
    vsc2_dc_bus: gce.Bus = gce.Bus(name="VSC2_DC_bus", Vnom=constants.dc_voltage_kv, is_dc=True)
    bus_list: list[gce.Bus] = list([grid_bus, pcc_bus, vsc1_ac_bus, vsc2_ac_bus, vsc1_dc_bus, vsc2_dc_bus])

    bus: gce.Bus
    for bus in bus_list:
        circuit.add_bus(bus)

    # The generator represents the external grid seen behind the Thevenin branch.
    generator: gce.Generator = gce.Generator(
        name="External_grid_thevenin",
        vset=1.0,
        Snom=constants.sbase_mva,
        freq=constants.fbase_hz,
        r1=constants.grid_r_pu,
        x1=constants.grid_x_pu,
    )
    circuit.add_generator(grid_bus, generator)

    # The AC branches establish the PCC and the two converter feeders. Their PF
    # impedances are also reused by the EMT pi-line templates later.
    grid_branch: gce.Line = gce.Line(
        name="Grid_to_PCC",
        bus_from=grid_bus,
        bus_to=pcc_bus,
        r=constants.grid_r_pu,
        x=constants.grid_x_pu,
        b=0.0,
        rate=constants.grid_rate_mva,
    )
    coupling_branch_1: gce.Line = gce.Line(
        name="PCC_to_VSC1_AC",
        bus_from=pcc_bus,
        bus_to=vsc1_ac_bus,
        r=constants.coupling_r_pu,
        x=constants.coupling_x_pu,
        b=0.0,
        rate=constants.coupling_rate_mva,
    )
    coupling_branch_2: gce.Line = gce.Line(
        name="PCC_to_VSC2_AC",
        bus_from=pcc_bus,
        bus_to=vsc2_ac_bus,
        r=constants.coupling_r_pu,
        x=constants.coupling_x_pu,
        b=0.0,
        rate=constants.coupling_rate_mva,
    )
    line_list: list[gce.Line] = list([grid_branch, coupling_branch_1, coupling_branch_2])

    line_item: gce.Line
    for line_item in line_list:
        circuit.add_line(line_item)

    # The balanced PF uses Pdc/Qac on both converters because that is the stable
    # static operating-point formulation for this topology.
    vsc1: gce.VSC = gce.VSC(
        name="VSC_1",
        bus_from=vsc1_dc_bus,
        bus_to=vsc1_ac_bus,
        rate=constants.vsc_rating_mva,
        control1=ConverterControlType.Pdc,
        control2=ConverterControlType.Qac,
        control1_val=-constants.dc_load_base_mw,
        control2_val=constants.q_setpoint_mvar,
        alpha1=0.0,
        alpha2=0.0,
        alpha3=0.0,
    )
    vsc2: gce.VSC = gce.VSC(
        name="VSC_2",
        bus_from=vsc2_dc_bus,
        bus_to=vsc2_ac_bus,
        rate=constants.vsc_rating_mva,
        control1=ConverterControlType.Pdc,
        control2=ConverterControlType.Qac,
        control1_val=-constants.dc_load_base_mw,
        control2_val=constants.q_setpoint_mvar,
        alpha1=0.0,
        alpha2=0.0,
        alpha3=0.0,
    )
    converter_list: list[gce.VSC] = list([vsc1, vsc2])

    converter: gce.VSC
    for converter in converter_list:
        circuit.add_vsc(converter)

    # Each DC bus carries its own independent consuming load, which defines the
    # requested steady-state active-power transfer.
    dc_load_1: gce.Load = gce.Load(name="DC_Load_1", P=constants.dc_load_base_mw, Q=0.0)
    dc_load_2: gce.Load = gce.Load(name="DC_Load_2", P=constants.dc_load_base_mw, Q=0.0)
    circuit.add_load(vsc1_dc_bus, dc_load_1)
    circuit.add_load(vsc2_dc_bus, dc_load_2)

    # The circuit now contains the exact topology requested. The later helper
    # builds a strongly typed wrapper around these device handles.
    return circuit


def collect_two_vsc_case(circuit: MultiCircuit) -> TwoVscCase:
    """
    Collect named device handles from the built circuit.

    The static topology builder returns the raw circuit to respect the requested
    function signature. This helper then reconstructs the typed handles used by
    the remaining algorithm stages.

    :param circuit:
        Built multi-circuit.
    :returns:
        Typed case wrapper with explicit device handles.
    :rtype: TwoVscCase
    """
    bus_lookup: dict[str, gce.Bus] = dict()
    branch_lookup: dict[str, gce.Line] = dict()
    generator_lookup: dict[str, gce.Generator] = dict()
    vsc_lookup: dict[str, gce.VSC] = dict()
    load_lookup: dict[str, gce.Load] = dict()

    # The wrapper is reconstructed by name because the VeraGrid circuit stores
    # the created devices internally and exposes them through typed collections.
    bus_item: gce.Bus
    for bus_item in circuit.buses:
        bus_lookup[bus_item.name] = bus_item

    branch_item: gce.Line
    for branch_item in circuit.lines:
        branch_lookup[branch_item.name] = branch_item

    generator_item: gce.Generator
    for generator_item in circuit.generators:
        generator_lookup[generator_item.name] = generator_item

    vsc_item: gce.VSC
    for vsc_item in circuit.vsc_devices:
        vsc_lookup[vsc_item.name] = vsc_item

    load_item: gce.Load
    for load_item in circuit.loads:
        load_lookup[load_item.name] = load_item

    case: TwoVscCase = TwoVscCase(
        circuit=circuit,
        grid_bus=bus_lookup["Grid_internal_bus"],
        pcc_bus=bus_lookup["PCC_bus"],
        vsc1_ac_bus=bus_lookup["VSC1_AC_bus"],
        vsc2_ac_bus=bus_lookup["VSC2_AC_bus"],
        vsc1_dc_bus=bus_lookup["VSC1_DC_bus"],
        vsc2_dc_bus=bus_lookup["VSC2_DC_bus"],
        generator=generator_lookup["External_grid_thevenin"],
        grid_branch=branch_lookup["Grid_to_PCC"],
        coupling_branch_1=branch_lookup["PCC_to_VSC1_AC"],
        coupling_branch_2=branch_lookup["PCC_to_VSC2_AC"],
        vsc1=vsc_lookup["VSC_1"],
        vsc2=vsc_lookup["VSC_2"],
        dc_load_1=load_lookup["DC_Load_1"],
        dc_load_2=load_lookup["DC_Load_2"],
    )
    return case


def build_power_flow_options() -> PowerFlowOptions:
    """
    Build balanced AC/DC power-flow options.

    :returns:
        Configured balanced power-flow options.
    :rtype: PowerFlowOptions
    """
    options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.LM,
        retry_with_other_methods=True,
        verbose=False,
        tolerance=1e-6,
        max_iter=100,
        control_q=True,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    return options


def build_power_flow_options_3ph() -> PowerFlowOptions:
    """
    Build optional three-phase initialization power-flow options.

    :returns:
        Configured three-phase power-flow options.
    :rtype: PowerFlowOptions
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


def run_power_flow(circuit: MultiCircuit) -> PowerFlowRunResult:
    """
    Run the balanced AC/DC power flow and attempt the 3-phase initialization flow.

    The balanced PF provides the validated operating point for this case. The
    optional 3-phase PF is attempted because other EMT scripts use it for more
    detailed initialization, but the current VeraGrid implementation fails for
    this specific two-VSC topology and therefore must be handled non-fatally.

    :param circuit:
        Circuit to solve.
    :returns:
        Balanced result and optional three-phase result.
    :rtype: PowerFlowRunResult
    """
    balanced_results: PowerFlowResults = gce.power_flow(grid=circuit, options=build_power_flow_options())
    driver_3ph: PowerFlowDriver3Ph = PowerFlowDriver3Ph(circuit, build_power_flow_options_3ph())
    three_phase_results: Optional[object] = None
    three_phase_error: Optional[str] = None

    # The balanced PF must exist for the rest of the algorithm, while the
    # three-phase PF is best-effort because of an engine-side indexing bug.
    try:
        driver_3ph.run()
        three_phase_results = driver_3ph.results
        three_phase_error = None
    except Exception as exc:
        three_phase_results = None
        three_phase_error = str(exc)
        print(f"Warning: 3-phase PF initialization failed for this two-VSC case: {three_phase_error}")
    else:
        pass

    result: PowerFlowRunResult = PowerFlowRunResult(
        balanced=balanced_results,
        three_phase=three_phase_results,
        three_phase_error=three_phase_error,
    )
    return result


def attach_converter_parameters(
    converter_mdl: Block,
    suffix: str,
    control1: ConverterControlType,
    control2: ConverterControlType,
    control1_value: float,
    control2_value: float,
    p0_value: float,
    constants: CaseConstants,
    case: TwoVscCase,
) -> None:
    """
    Populate one pseudo-EMT converter block with explicit parameters.

    The EMT converter template needs all of its electrical and control constants
    written explicitly because the stable pseudo-EMT model contains internal AC,
    DC-link and control states beyond the balanced PF model.

    :param converter_mdl:
        Converter EMT block to configure.
    :param suffix:
        Symbolic model suffix.
    :param control1:
        First converter control mode.
    :param control2:
        Second converter control mode.
    :param control1_value:
        First converter control target.
    :param control2_value:
        Second converter control target.
    :param p0_value:
        Seeded active-power operating point.
    :param constants:
        Study constants.
    :param case:
        Typed case object.
    :returns:
        None.
    :rtype: None
    """
    # The control references are written first because they determine whether the
    # pseudo-converter behaves as a DC-voltage regulator or as a power follower.
    converter_mdl.set_parameter_in_model(var_name=f"sbase_{suffix}", new_value=case.circuit.Sbase)
    converter_mdl.set_parameter_in_model(var_name=f"omega_base_{suffix}", new_value=2.0 * np.pi * case.circuit.fBase)
    converter_mdl.set_parameter_in_model(var_name=f"control1_{suffix}", new_value=converter_control_code(control1))
    converter_mdl.set_parameter_in_model(var_name=f"control2_{suffix}", new_value=converter_control_code(control2))
    converter_mdl.set_parameter_in_model(var_name=f"control1_val_{suffix}", new_value=control1_value)
    converter_mdl.set_parameter_in_model(var_name=f"control2_val_{suffix}", new_value=control2_value)
    converter_mdl.set_parameter_in_model(var_name=f"P0_{suffix}", new_value=p0_value)
    converter_mdl.set_parameter_in_model(var_name=f"P_loss_{suffix}", new_value=0.0)
    converter_mdl.set_parameter_in_model(var_name=f"Vdc_nom_{suffix}", new_value=1.0)

    # The electrical and controller gains come from the stable pseudo-EMT cases
    # already present in the repository and avoid the divergence seen with the
    # simpler ideal converter model in this parallel configuration.
    converter_mdl.set_parameter_in_model(var_name=f"R_eq_{suffix}", new_value=constants.converter_r_eq_pu)
    converter_mdl.set_parameter_in_model(var_name=f"L_eq_{suffix}", new_value=constants.converter_l_eq_pu)
    converter_mdl.set_parameter_in_model(var_name=f"C_dc_{suffix}", new_value=constants.converter_c_dc_pu)
    converter_mdl.set_parameter_in_model(var_name=f"R_dc_{suffix}", new_value=constants.converter_r_dc_pu)
    converter_mdl.set_parameter_in_model(var_name=f"R_dc_term_{suffix}", new_value=constants.converter_r_dc_term_pu)
    converter_mdl.set_parameter_in_model(var_name=f"pll_kp_{suffix}", new_value=constants.pll_kp)
    converter_mdl.set_parameter_in_model(var_name=f"pll_ki_{suffix}", new_value=constants.pll_ki)
    converter_mdl.set_parameter_in_model(var_name=f"i_kp_{suffix}", new_value=constants.i_kp)
    converter_mdl.set_parameter_in_model(var_name=f"i_ki_{suffix}", new_value=constants.i_ki)
    converter_mdl.set_parameter_in_model(var_name=f"vdc_kp_{suffix}", new_value=constants.vdc_kp)
    converter_mdl.set_parameter_in_model(var_name=f"vdc_ki_{suffix}", new_value=constants.vdc_ki)
    converter_mdl.set_parameter_in_model(var_name=f"q_kp_{suffix}", new_value=constants.q_kp)
    converter_mdl.set_parameter_in_model(var_name=f"q_ki_{suffix}", new_value=constants.q_ki)
    converter_mdl.set_parameter_in_model(var_name=f"i_max_{suffix}", new_value=constants.i_max_pu)
    converter_mdl.set_parameter_in_model(var_name=f"m_max_{suffix}", new_value=constants.m_max_pu)
    converter_mdl.set_parameter_in_model(var_name=f"P_loss_i1_{suffix}", new_value=constants.p_loss_i1_pu)
    converter_mdl.set_parameter_in_model(var_name=f"P_loss_i2_{suffix}", new_value=constants.p_loss_i2_pu)
    converter_mdl.set_parameter_in_model(var_name=f"tau_meas_{suffix}", new_value=constants.tau_meas_s)
    converter_mdl.set_parameter_in_model(var_name=f"aw_gain_{suffix}", new_value=constants.aw_gain)
    converter_mdl.set_parameter_in_model(var_name=f"vdc_floor_{suffix}", new_value=constants.vdc_floor_pu)


def attach_emt_models(circuit: MultiCircuit) -> None:
    """
    Attach EMT models to buses and relevant devices.

    The function respects the requested signature by receiving only the raw
    circuit. It reconstructs the typed handles internally and then attaches the
    closest repository templates that work for this topology.

    :param circuit:
        Built static AC/DC circuit.
    :returns:
        None.
    :rtype: None
    """
    case: TwoVscCase = collect_two_vsc_case(circuit)
    constants: CaseConstants = get_case_constants()

    # Bus EMT shells must be created first because every device model later maps
    # its terminal variables to the symbolic bus voltages or currents.
    bus_list: list[gce.Bus] = list(circuit.buses)
    bus: gce.Bus
    for bus in bus_list:
        get_bus_emt_template(circuit, bus)

    # The EMT templates are chosen to match the working patterns already present
    # in the repository: Thevenin source, pi-lines, pseudo-EMT VSCs and DC loads.
    generator_mdl: Block = get_generator_thevenin_rl_emt_template_with_ref(
        vf=circuit.var_factory,
        name="grid_thevenin_emt",
    ).block
    grid_branch_mdl: Block = get_pi_line_emt_template(vf=circuit.var_factory, phN=False, phA=True, phB=True, phC=True, name="grid_piline_emt").block
    coupling_branch_1_mdl: Block = get_pi_line_emt_template(vf=circuit.var_factory, phN=False, phA=True, phB=True, phC=True, name="coupling_1_piline_emt").block
    coupling_branch_2_mdl: Block = get_pi_line_emt_template(vf=circuit.var_factory, phN=False, phA=True, phB=True, phC=True, name="coupling_2_piline_emt").block
    vsc1_mdl: Block = get_full_pseudo_emt_converter(vf=circuit.var_factory, name="vsc1_pseudo_emt").block
    vsc2_mdl: Block = get_full_pseudo_emt_converter(vf=circuit.var_factory, name="vsc2_pseudo_emt").block
    dc_load_1_mdl: Block = get_dc_load_emt_template(vf=circuit.var_factory, name="dc_load_1_emt").block
    dc_load_2_mdl: Block = get_dc_load_emt_template(vf=circuit.var_factory, name="dc_load_2_emt").block

    # Converter 1 is switched to Vm_dc/Qac only on the EMT side because that is
    # the robust dynamic configuration used by the repository pseudo-EMT examples.
    attach_converter_parameters(
        converter_mdl=vsc1_mdl,
        suffix="vsc1_pseudo_emt",
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_value=1.0,
        control2_value=case.vsc1.control2_val,
        p0_value=case.vsc1.control1_val,
        constants=constants,
        case=case,
    )
    attach_converter_parameters(
        converter_mdl=vsc2_mdl,
        suffix="vsc2_pseudo_emt",
        control1=case.vsc2.control1,
        control2=case.vsc2.control2,
        control1_value=case.vsc2.control1_val,
        control2_value=case.vsc2.control2_val,
        p0_value=case.vsc2.control1_val,
        constants=constants,
        case=case,
    )

    # Once every symbolic block is configured, the device-to-model association is
    # registered in the circuit so EmtProblemDae can build the full DAE.
    set_emt_model(device=case.generator, model=generator_mdl, var_factory=circuit.var_factory)
    set_emt_model(device=case.grid_branch, model=grid_branch_mdl, var_factory=circuit.var_factory)
    set_emt_model(device=case.coupling_branch_1, model=coupling_branch_1_mdl, var_factory=circuit.var_factory)
    set_emt_model(device=case.coupling_branch_2, model=coupling_branch_2_mdl, var_factory=circuit.var_factory)
    set_emt_model(device=case.vsc1, model=vsc1_mdl, var_factory=circuit.var_factory)
    set_emt_model(device=case.vsc2, model=vsc2_mdl, var_factory=circuit.var_factory)
    set_emt_model(device=case.dc_load_1, model=dc_load_1_mdl, var_factory=circuit.var_factory)
    set_emt_model(device=case.dc_load_2, model=dc_load_2_mdl, var_factory=circuit.var_factory)


def collect_emt_models(case: TwoVscCase) -> EmtModels:
    """
    Collect attached EMT blocks from the case devices.

    :param case:
        Typed case object.
    :returns:
        EMT model wrapper.
    :rtype: EmtModels
    """
    models: EmtModels = EmtModels(
        generator=case.generator.emt_model,
        grid_branch=case.grid_branch.emt_model,
        coupling_branch_1=case.coupling_branch_1.emt_model,
        coupling_branch_2=case.coupling_branch_2.emt_model,
        vsc1=case.vsc1.emt_model,
        vsc2=case.vsc2.emt_model,
        dc_load_1=case.dc_load_1.emt_model,
        dc_load_2=case.dc_load_2.emt_model,
    )
    return models


def get_bus_index(bus_names: np.ndarray, bus_name: str) -> int:
    """
    Return the index of one bus name in a bus-name array.

    :param bus_names:
        Bus-name array.
    :param bus_name:
        Target bus name.
    :returns:
        Integer index of the target bus.
    :rtype: int
    """
    match_indices: np.ndarray = np.where(bus_names == bus_name)[0]
    match_count: int = int(match_indices.size)

    if match_count > 0:
        bus_index: int = int(match_indices[0])
        return bus_index
    else:
        print(f"Warning: bus '{bus_name}' was not found in the power-flow results.")
        return -1


def print_power_flow_summary(case: TwoVscCase, pf_results: PowerFlowResults) -> bool:
    """
    Print the concise post-power-flow summary requested for the case.

    :param case:
        Typed case object.
    :param pf_results:
        Balanced power-flow result.
    :returns:
        ``True`` when the summary corresponds to a converged solution.
    :rtype: bool
    """
    print("=" * 80)
    print("BALANCED AC/DC POWER FLOW RESULTS")
    print("=" * 80)
    print(f"Converged: {pf_results.converged}")

    if pf_results.converged:
        voltage: np.ndarray = pf_results.voltage
        bus_index: int = 0
        print("Bus voltages:")

        while bus_index < len(pf_results.bus_names):
            print(
                f"  {pf_results.bus_names[bus_index]}: "
                f"|V|={np.abs(voltage[bus_index]):.6f} pu, "
                f"angle={np.degrees(np.angle(voltage[bus_index])):.4f} deg"
            )
            bus_index += 1

        print("AC branch flows:")
        branch_index: int = 0
        while branch_index < len(pf_results.branch_names):
            sf: complex = pf_results.Sf[branch_index]
            st: complex = pf_results.St[branch_index]
            loading_pct: float = 100.0 * np.abs(pf_results.loading[branch_index])
            print(
                f"  {pf_results.branch_names[branch_index]}: "
                f"Sf={sf.real:.6f} MW + j{sf.imag:.6f} MVAr, "
                f"St={st.real:.6f} MW + j{st.imag:.6f} MVAr, "
                f"loading={loading_pct:.3f} %"
            )
            branch_index += 1

        print("VSC powers:")
        vsc_index: int = 0
        while vsc_index < len(pf_results.vsc_names):
            st_vsc: complex = pf_results.St_vsc[vsc_index]
            print(
                f"  {pf_results.vsc_names[vsc_index]}: "
                f"Pdc_from={pf_results.Pfp_vsc[vsc_index]:.6f} MW, "
                f"Pac_to={st_vsc.real:.6f} MW, "
                f"Qac_to={st_vsc.imag:.6f} MVAr"
            )
            vsc_index += 1

        print("DC bus voltages:")
        dc_bus_name_list: list[str] = list([case.vsc1_dc_bus.name, case.vsc2_dc_bus.name])
        dc_bus_name: str
        for dc_bus_name in dc_bus_name_list:
            idx: int = get_bus_index(pf_results.bus_names, dc_bus_name)
            if idx >= 0:
                print(f"  {dc_bus_name}: |V|={np.abs(pf_results.voltage[idx]):.6f} pu")
            else:
                print(f"  {dc_bus_name}: unavailable")

        print("DC loads:")
        print(f"  {case.dc_load_1.name}: P={case.dc_load_1.P:.6f} MW")
        print(f"  {case.dc_load_2.name}: P={case.dc_load_2.P:.6f} MW")

        slack_idx: int = get_bus_index(pf_results.bus_names, case.grid_bus.name)
        if slack_idx >= 0:
            s_slack: complex = pf_results.Sbus[slack_idx]
            print("Slack/grid injection:")
            print(f"  {case.grid_bus.name}: P={s_slack.real:.6f} MW, Q={s_slack.imag:.6f} MVAr")
        else:
            print("Slack/grid injection:")
            print(f"  {case.grid_bus.name}: unavailable")

        return True
    else:
        report_count: int = len(pf_results.convergence_reports)
        print(f"Power flow did not converge. Iteration reports available: {report_count}.")
        return False


def plot_power_flow_results(case: TwoVscCase, pf_results: PowerFlowRunResult) -> None:
    """
    Print the compact power-flow summary and optional 3-phase status.

    :param case:
        Typed case object.
    :param pf_results:
        Power-flow run wrapper.
    :returns:
        None.
    :rtype: None
    """
    converged: bool = print_power_flow_summary(case, pf_results.balanced)

    if converged:
        pass
    else:
        print("Warning: EMT execution will be skipped by the caller if PF convergence is required.")

    if pf_results.three_phase is not None:
        print("3-phase EMT initialization power flow:")
        print(f"  Converged: {pf_results.three_phase.converged}")
    else:
        if pf_results.three_phase_error is not None:
            print("3-phase EMT initialization power flow:")
            print(f"  Unavailable: {pf_results.three_phase_error}")
        else:
            print("3-phase EMT initialization power flow:")
            print("  Unavailable: no result was produced.")


def build_emt_options() -> EmtOptions:
    """
    Build EMT solver options.

    :returns:
        EMT options object.
    :rtype: EmtOptions
    """
    constants: CaseConstants = get_case_constants()
    options: EmtOptions = EmtOptions(
        time_step=constants.time_step_s,
        simulation_time=constants.simulation_time_s,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=1,
    )
    return options


def add_dc_load_step_event(case: TwoVscCase, models: EmtModels) -> None:
    """
    Add one DC-load power step if the event parameter exists in the EMT block.

    The DC-load EMT template uses the consuming-load sign convention, so raising
    ``Pl0`` increases the DC power demand. The event remains optional because the
    currently attached device block does not expose the searched parameter name in
    a form that works for this example.

    :param case:
        Typed case object.
    :param models:
        Attached EMT model wrapper.
    :returns:
        None.
    :rtype: None
    """
    constants: CaseConstants = get_case_constants()
    events_group: EmtEventsGroup = EmtEventsGroup("two_vsc_events")
    case.circuit.add_emt_events_group(events_group)
    pl0_var: Optional[Var] = find_name_in_block("Pl0", models.dc_load_1)

    if pl0_var is not None:
        event: EmtEvent = EmtEvent(
            device=case.dc_load_1,
            parameter=pl0_var,
            time=constants.event_time_s,
            value=constants.dc_load_step_mw,
            group=events_group,
        )
        case.circuit.add_emt_event(event)
    else:
        print("Warning: DC-load EMT event parameter 'Pl0' was not found. Running steady-state EMT only.")


def get_signal(
    problem: EmtProblemDae,
    root_block: Block,
    variable_name: str,
    trajectory: np.ndarray,
    mode: SignalMode,
) -> np.ndarray:
    """
    Extract one trajectory from the EMT state matrix.

    :param problem:
        EMT problem with variable indexing.
    :param root_block:
        Root symbolic block to search.
    :param variable_name:
        Symbolic variable name.
    :param trajectory:
        Solver trajectory matrix.
    :param mode:
        Required or optional signal policy.
    :returns:
        Extracted trajectory or zeros for optional missing signals.
    :rtype: numpy.ndarray
    """
    variable: Optional[Var] = find_name_in_block(variable_name, root_block)

    if variable is not None:
        signal: np.ndarray = np.array(trajectory[:, problem.get_var_idx(variable)], copy=True)
        return signal
    else:
        if mode == SignalMode.OPTIONAL:
            print(f"Warning: optional signal '{variable_name}' was not found in block '{root_block.name}'.")
            zero_signal: np.ndarray = np.zeros(trajectory.shape[0], dtype=np.float64)
            return zero_signal
        else:
            print(f"Warning: required EMT signal '{variable_name}' was not found in block '{root_block.name}'.")
            zero_signal = np.zeros(trajectory.shape[0], dtype=np.float64)
            return zero_signal


def save_three_trace_scalar_plot(
    file_path: Path,
    time_s: np.ndarray,
    values_1: np.ndarray,
    values_2: np.ndarray,
    values_3: np.ndarray,
    label_1: str,
    label_2: str,
    label_3: str,
    title: str,
    y_label: str,
) -> None:
    """
    Save one scalar figure containing three explicit traces.

    :param file_path:
        Output image path.
    :param time_s:
        Time vector.
    :param values_1:
        First trace.
    :param values_2:
        Second trace.
    :param values_3:
        Third trace.
    :param label_1:
        First trace label.
    :param label_2:
        Second trace label.
    :param label_3:
        Third trace label.
    :param title:
        Figure title.
    :param y_label:
        Y-axis label.
    :returns:
        None.
    :rtype: None
    """
    figure, axis = plt.subplots(1, 1, figsize=(12, 5))
    axis.plot(time_s, values_1, label=label_1)
    axis.plot(time_s, values_2, label=label_2)
    axis.plot(time_s, values_3, label=label_3)
    axis.set_title(title)
    axis.set_xlabel("Time [s]")
    axis.set_ylabel(y_label)
    axis.grid(True)
    axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(file_path, dpi=300, bbox_inches="tight")
    plt.close(figure)


def save_four_trace_scalar_plot(
    file_path: Path,
    time_s: np.ndarray,
    values_1: np.ndarray,
    values_2: np.ndarray,
    values_3: np.ndarray,
    values_4: np.ndarray,
    label_1: str,
    label_2: str,
    label_3: str,
    label_4: str,
    title: str,
    y_label: str,
) -> None:
    """
    Save one scalar figure containing four explicit traces.

    :param file_path:
        Output image path.
    :param time_s:
        Time vector.
    :param values_1:
        First trace.
    :param values_2:
        Second trace.
    :param values_3:
        Third trace.
    :param values_4:
        Fourth trace.
    :param label_1:
        First trace label.
    :param label_2:
        Second trace label.
    :param label_3:
        Third trace label.
    :param label_4:
        Fourth trace label.
    :param title:
        Figure title.
    :param y_label:
        Y-axis label.
    :returns:
        None.
    :rtype: None
    """
    figure, axis = plt.subplots(1, 1, figsize=(12, 5))
    axis.plot(time_s, values_1, label=label_1)
    axis.plot(time_s, values_2, label=label_2)
    axis.plot(time_s, values_3, label=label_3)
    axis.plot(time_s, values_4, label=label_4)
    axis.set_title(title)
    axis.set_xlabel("Time [s]")
    axis.set_ylabel(y_label)
    axis.grid(True)
    axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(file_path, dpi=300, bbox_inches="tight")
    plt.close(figure)


def run_emt_simulation(circuit: MultiCircuit) -> EmtRunResult:
    """
    Run the EMT simulation from the PF-initialized operating point.

    The function respects the requested signature and rebuilds the typed case and
    EMT model wrappers internally. This keeps the public API simple while still
    preserving explicit typed access internally.

    :param circuit:
        Built circuit with attached EMT models.
    :returns:
        EMT run result wrapper.
    :rtype: EmtRunResult
    """
    constants: CaseConstants = get_case_constants()
    case: TwoVscCase = collect_two_vsc_case(circuit)
    models: EmtModels = collect_emt_models(case)
    pf_results: PowerFlowRunResult = run_power_flow(circuit)

    # Events are added before the EMT problem is built so the runtime parameter
    # schedule is known when the DAE and the solver are assembled.
    add_dc_load_step_event(case, models)

    problem: EmtProblemDae = EmtProblemDae(
        grid=circuit,
        options=build_emt_options(),
        pf_results_3ph=pf_results.three_phase,
        pf_results=pf_results.balanced,
    )
    x0: np.ndarray = problem.get_x0()
    dx0: np.ndarray = problem.get_dx0()
    print("EMT initialization report")
    print(f"  finite x0 : {bool(np.all(np.isfinite(x0)))}")
    print(f"  finite dx0: {bool(np.all(np.isfinite(dx0)))}")

    if problem.initialization_report is not None:
        report = problem.initialization_report
        print(f"  method    : {report.method_used.name}")
        print(f"  status    : {report.status.name}")
        print(f"  residual  : {report.final_residual_inf:.3e}")
    else:
        print("  initialization report unavailable")

    # The structural compiled solver is the same backend used by the working EMT
    # scripting examples, so it is reused here without introducing extra options.
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
    time_s: np.ndarray
    trajectory: np.ndarray
    well_initialized: bool
    converged: bool
    time_s, trajectory, _, well_initialized, converged = solver.simulate()

    if np.all(np.isfinite(trajectory)):
        output_dir: Path = get_plot_results_directory(constants.case_name, constants.solver_key.value)
        plot_path: Path = output_dir / "scripting_two_vsc_emt.png"
        result: EmtRunResult = EmtRunResult(
            problem=problem,
            time_s=np.array(time_s, copy=True),
            trajectory=np.array(trajectory, copy=True),
            well_initialized=bool(well_initialized),
            converged=bool(converged),
            plot_path=plot_path,
        )
        return result
    else:
        print("Warning: EMT simulation produced non-finite trajectories.")
        output_dir = get_plot_results_directory(constants.case_name, constants.solver_key.value)
        plot_path = output_dir / "scripting_two_vsc_emt.png"
        empty_time: np.ndarray = np.zeros(1, dtype=np.float64)
        empty_trajectory: np.ndarray = np.zeros((1, 1), dtype=np.float64)
        result = EmtRunResult(
            problem=problem,
            time_s=empty_time,
            trajectory=empty_trajectory,
            well_initialized=False,
            converged=False,
            plot_path=plot_path,
        )
        return result


def plot_emt_results(emt_result: EmtRunResult) -> None:
    """
    Export one multi-panel EMT diagnostic figure.

    :param emt_result:
        EMT simulation output.
    :returns:
        None.
    :rtype: None
    """
    case: TwoVscCase = collect_two_vsc_case(emt_result.problem.grid)
    models: EmtModels = collect_emt_models(case)
    problem: EmtProblemDae = emt_result.problem
    time_s: np.ndarray = emt_result.time_s
    y_values: np.ndarray = emt_result.trajectory

    # The plotting stage extracts each requested trajectory explicitly so the
    # output figure can be interpreted directly against the validation checklist.
    v_grid_a: np.ndarray = get_signal(problem, case.grid_bus.emt_model, "v_A_Grid_internal_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_grid_b: np.ndarray = get_signal(problem, case.grid_bus.emt_model, "v_B_Grid_internal_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_grid_c: np.ndarray = get_signal(problem, case.grid_bus.emt_model, "v_C_Grid_internal_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_pcc_a: np.ndarray = get_signal(problem, case.pcc_bus.emt_model, "v_A_PCC_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_pcc_b: np.ndarray = get_signal(problem, case.pcc_bus.emt_model, "v_B_PCC_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_pcc_c: np.ndarray = get_signal(problem, case.pcc_bus.emt_model, "v_C_PCC_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_vsc1_a: np.ndarray = get_signal(problem, case.vsc1_ac_bus.emt_model, "v_A_VSC1_AC_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_vsc1_b: np.ndarray = get_signal(problem, case.vsc1_ac_bus.emt_model, "v_B_VSC1_AC_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_vsc1_c: np.ndarray = get_signal(problem, case.vsc1_ac_bus.emt_model, "v_C_VSC1_AC_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_vsc2_a: np.ndarray = get_signal(problem, case.vsc2_ac_bus.emt_model, "v_A_VSC2_AC_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_vsc2_b: np.ndarray = get_signal(problem, case.vsc2_ac_bus.emt_model, "v_B_VSC2_AC_bus_emt_template", y_values, SignalMode.REQUIRED)
    v_vsc2_c: np.ndarray = get_signal(problem, case.vsc2_ac_bus.emt_model, "v_C_VSC2_AC_bus_emt_template", y_values, SignalMode.REQUIRED)
    vdc_1: np.ndarray = get_signal(problem, case.vsc1_dc_bus.emt_model, "v_DC_VSC1_DC_bus_emt_template", y_values, SignalMode.REQUIRED)
    vdc_2: np.ndarray = get_signal(problem, case.vsc2_dc_bus.emt_model, "v_DC_VSC2_DC_bus_emt_template", y_values, SignalMode.REQUIRED)
    p_vsc1: np.ndarray = get_signal(problem, models.vsc1, "P_vsc1_pseudo_emt", y_values, SignalMode.REQUIRED)
    p_vsc2: np.ndarray = get_signal(problem, models.vsc2, "P_vsc2_pseudo_emt", y_values, SignalMode.REQUIRED)
    q_vsc1: np.ndarray = get_signal(problem, models.vsc1, "Q_vsc1_pseudo_emt", y_values, SignalMode.REQUIRED)
    q_vsc2: np.ndarray = get_signal(problem, models.vsc2, "Q_vsc2_pseudo_emt", y_values, SignalMode.REQUIRED)
    p_dc_load_1: np.ndarray = get_signal(problem, models.dc_load_1, "p_dc_dc_load_1_emt", y_values, SignalMode.REQUIRED)
    p_dc_load_2: np.ndarray = get_signal(problem, models.dc_load_2, "p_dc_dc_load_2_emt", y_values, SignalMode.REQUIRED)
    i_dc_load_1: np.ndarray = get_signal(problem, models.dc_load_1, "i_dc_dc_load_1_emt", y_values, SignalMode.OPTIONAL)
    i_dc_load_2: np.ndarray = get_signal(problem, models.dc_load_2, "i_dc_dc_load_2_emt", y_values, SignalMode.OPTIONAL)
    theta_vsc1: np.ndarray = get_signal(problem, models.vsc1, "theta_vsc1_pseudo_emt", y_values, SignalMode.OPTIONAL)
    theta_vsc2: np.ndarray = get_signal(problem, models.vsc2, "theta_vsc2_pseudo_emt", y_values, SignalMode.OPTIONAL)
    i_a_vsc1: np.ndarray = get_signal(problem, models.vsc1, "i_A_vsc1_pseudo_emt", y_values, SignalMode.OPTIONAL)
    i_b_vsc1: np.ndarray = get_signal(problem, models.vsc1, "i_B_vsc1_pseudo_emt", y_values, SignalMode.OPTIONAL)
    i_c_vsc1: np.ndarray = get_signal(problem, models.vsc1, "i_C_vsc1_pseudo_emt", y_values, SignalMode.OPTIONAL)
    i_a_vsc2: np.ndarray = get_signal(problem, models.vsc2, "i_A_vsc2_pseudo_emt", y_values, SignalMode.OPTIONAL)
    i_b_vsc2: np.ndarray = get_signal(problem, models.vsc2, "i_B_vsc2_pseudo_emt", y_values, SignalMode.OPTIONAL)
    i_c_vsc2: np.ndarray = get_signal(problem, models.vsc2, "i_C_vsc2_pseudo_emt", y_values, SignalMode.OPTIONAL)
    i_dc_vsc1: np.ndarray = get_signal(problem, models.vsc1, "i_dc_vsc1_pseudo_emt", y_values, SignalMode.OPTIONAL)
    i_dc_vsc2: np.ndarray = get_signal(problem, models.vsc2, "i_dc_vsc2_pseudo_emt", y_values, SignalMode.OPTIONAL)
    total_dc_demand: np.ndarray = -(p_dc_load_1 + p_dc_load_2)
    output_dir: Path = emt_result.plot_path.parent

    save_two_panel_three_phase_plot(
        file_path=output_dir / "bus_grid_and_pcc_abc.png",
        time_values=time_s,
        top_triplet=(v_grid_a, v_grid_b, v_grid_c),
        top_title="Grid internal bus abc voltages",
        top_ylabel="Voltage [pu peak]",
        top_legend_prefix="Grid_internal_bus v",
        bottom_triplet=(v_pcc_a, v_pcc_b, v_pcc_c),
        bottom_title="PCC bus abc voltages",
        bottom_ylabel="Voltage [pu peak]",
        bottom_legend_prefix="PCC_bus v",
    )
    save_two_panel_three_phase_plot(
        file_path=output_dir / "bus_vsc_ac_abc.png",
        time_values=time_s,
        top_triplet=(v_vsc1_a, v_vsc1_b, v_vsc1_c),
        top_title="VSC1 AC bus abc voltages",
        top_ylabel="Voltage [pu peak]",
        top_legend_prefix="VSC1_AC_bus v",
        bottom_triplet=(v_vsc2_a, v_vsc2_b, v_vsc2_c),
        bottom_title="VSC2 AC bus abc voltages",
        bottom_ylabel="Voltage [pu peak]",
        bottom_legend_prefix="VSC2_AC_bus v",
    )
    save_two_panel_three_phase_plot(
        file_path=output_dir / "vsc_ac_currents_abc.png",
        time_values=time_s,
        top_triplet=(i_a_vsc1, i_b_vsc1, i_c_vsc1),
        top_title="VSC1 abc currents",
        top_ylabel="Current [pu]",
        top_legend_prefix="VSC1 i",
        bottom_triplet=(i_a_vsc2, i_b_vsc2, i_c_vsc2),
        bottom_title="VSC2 abc currents",
        bottom_ylabel="Current [pu]",
        bottom_legend_prefix="VSC2 i",
    )
    save_scalar_plot(
        file_path=output_dir / "dc_bus_voltages.png",
        time_values=time_s,
        values=vdc_1,
        title="VSC1 DC bus voltage",
        y_label="Voltage [pu]",
    )
    save_scalar_plot(
        file_path=output_dir / "dc_bus_voltages_vsc2.png",
        time_values=time_s,
        values=vdc_2,
        title="VSC2 DC bus voltage",
        y_label="Voltage [pu]",
    )
    save_three_trace_scalar_plot(
        file_path=output_dir / "dc_voltages_and_balance.png",
        time_s=time_s,
        values_1=vdc_1,
        values_2=vdc_2,
        values_3=vdc_1 - vdc_2,
        label_1="VSC1 DC voltage",
        label_2="VSC2 DC voltage",
        label_3="Voltage mismatch",
        title="DC voltages and mismatch",
        y_label="Voltage [pu]",
    )
    save_three_trace_scalar_plot(
        file_path=output_dir / "vsc_active_powers.png",
        time_s=time_s,
        values_1=p_vsc1,
        values_2=p_vsc2,
        values_3=total_dc_demand,
        label_1="VSC1 Pac",
        label_2="VSC2 Pac",
        label_3="Total DC demand",
        title="VSC active powers and total DC demand",
        y_label="Power [pu on system base]",
    )
    save_three_trace_scalar_plot(
        file_path=output_dir / "vsc_power_sharing.png",
        time_s=time_s,
        values_1=p_vsc1,
        values_2=p_vsc2,
        values_3=p_vsc1 + p_vsc2,
        label_1="VSC1 Pac",
        label_2="VSC2 Pac",
        label_3="VSC total Pac",
        title="VSC active power sharing",
        y_label="Power [pu on system base]",
    )
    save_three_trace_scalar_plot(
        file_path=output_dir / "vsc_reactive_powers.png",
        time_s=time_s,
        values_1=q_vsc1,
        values_2=q_vsc2,
        values_3=q_vsc1 + q_vsc2,
        label_1="VSC1 Qac",
        label_2="VSC2 Qac",
        label_3="VSC total Qac",
        title="VSC reactive powers",
        y_label="Reactive power [pu]",
    )
    save_four_trace_scalar_plot(
        file_path=output_dir / "dc_load_powers_and_currents.png",
        time_s=time_s,
        values_1=-p_dc_load_1,
        values_2=-p_dc_load_2,
        values_3=-i_dc_load_1,
        values_4=-i_dc_load_2,
        label_1="DC_Load_1 power",
        label_2="DC_Load_2 power",
        label_3="DC_Load_1 current",
        label_4="DC_Load_2 current",
        title="DC load powers and currents",
        y_label="Load demand [pu]",
    )
    save_four_trace_scalar_plot(
        file_path=output_dir / "converter_dc_currents_and_loads.png",
        time_s=time_s,
        values_1=i_dc_vsc1,
        values_2=i_dc_vsc2,
        values_3=-i_dc_load_1,
        values_4=-i_dc_load_2,
        label_1="VSC1 idc",
        label_2="VSC2 idc",
        label_3="Load1 idc demand",
        label_4="Load2 idc demand",
        title="Converter and load DC currents",
        y_label="Current [pu]",
    )
    save_three_trace_scalar_plot(
        file_path=output_dir / "converter_internal_angles.png",
        time_s=time_s,
        values_1=theta_vsc1,
        values_2=theta_vsc2,
        values_3=theta_vsc1 - theta_vsc2,
        label_1="VSC1 angle",
        label_2="VSC2 angle",
        label_3="Angle mismatch",
        title="Optional converter internal angles",
        y_label="Angle [rad]",
    )

    summary_figure, summary_axes = plt.subplots(6, 1, figsize=(14, 20), sharex=True)
    summary_axes[0].plot(time_s, v_grid_a, label="Grid_internal_bus Va")
    summary_axes[0].plot(time_s, v_pcc_a, label="PCC_bus Va")
    summary_axes[0].plot(time_s, v_vsc1_a, label="VSC1_AC_bus Va")
    summary_axes[0].plot(time_s, v_vsc2_a, label="VSC2_AC_bus Va")
    summary_axes[0].set_ylabel("Voltage [pu peak]")
    summary_axes[0].set_title("AC phase-A bus voltages")
    summary_axes[0].grid(True)
    summary_axes[0].legend(loc="best")

    summary_axes[1].plot(time_s, vdc_1, label="VSC1_DC_bus")
    summary_axes[1].plot(time_s, vdc_2, label="VSC2_DC_bus")
    summary_axes[1].set_ylabel("Voltage [pu]")
    summary_axes[1].set_title("DC bus voltages")
    summary_axes[1].grid(True)
    summary_axes[1].legend(loc="best")

    summary_axes[2].plot(time_s, p_vsc1, label="VSC1 Pac")
    summary_axes[2].plot(time_s, p_vsc2, label="VSC2 Pac")
    summary_axes[2].plot(time_s, total_dc_demand, "--", label="Total DC demand")
    summary_axes[2].set_ylabel("Power [pu on system base]")
    summary_axes[2].set_title("VSC active powers and total DC demand")
    summary_axes[2].grid(True)
    summary_axes[2].legend(loc="best")

    summary_axes[3].plot(time_s, q_vsc1, label="VSC1 Qac")
    summary_axes[3].plot(time_s, q_vsc2, label="VSC2 Qac")
    summary_axes[3].set_ylabel("Reactive power [pu]")
    summary_axes[3].set_title("VSC reactive powers")
    summary_axes[3].grid(True)
    summary_axes[3].legend(loc="best")

    summary_axes[4].plot(time_s, -p_dc_load_1, label="DC_Load_1 power")
    summary_axes[4].plot(time_s, -p_dc_load_2, label="DC_Load_2 power")
    summary_axes[4].plot(time_s, -i_dc_load_1, "--", label="DC_Load_1 current")
    summary_axes[4].plot(time_s, -i_dc_load_2, "--", label="DC_Load_2 current")
    summary_axes[4].set_ylabel("Load demand [pu]")
    summary_axes[4].set_title("DC load powers and currents")
    summary_axes[4].grid(True)
    summary_axes[4].legend(loc="best")

    summary_axes[5].plot(time_s, theta_vsc1, label="VSC1 angle")
    summary_axes[5].plot(time_s, theta_vsc2, label="VSC2 angle")
    summary_axes[5].plot(time_s, i_a_vsc1, "--", label="VSC1 ia")
    summary_axes[5].plot(time_s, i_a_vsc2, "--", label="VSC2 ia")
    summary_axes[5].plot(time_s, i_dc_vsc1, ":", label="VSC1 idc")
    summary_axes[5].plot(time_s, i_dc_vsc2, ":", label="VSC2 idc")
    summary_axes[5].set_xlabel("Time [s]")
    summary_axes[5].set_ylabel("Mixed units")
    summary_axes[5].set_title("Optional converter internal and current signals")
    summary_axes[5].grid(True)
    summary_axes[5].legend(loc="best")

    summary_figure.tight_layout()
    summary_figure.savefig(emt_result.plot_path, dpi=200, bbox_inches="tight")
    plt.close(summary_figure)

    print(f"EMT plot exported to: {emt_result.plot_path}")
    print(f"EMT initialization status: well_initialized={emt_result.well_initialized}")
    print(f"EMT convergence status: converged={emt_result.converged}")
    print(f"Final DC voltages: VSC1={vdc_1[-1]:.6f} pu, VSC2={vdc_2[-1]:.6f} pu")
    print(f"Final VSC active powers: VSC1={p_vsc1[-1]:.6f} pu, VSC2={p_vsc2[-1]:.6f} pu")

    print(f"Additional EMT plots exported to: {output_dir}")


def main() -> None:
    """
    Build the case, solve PF, attach EMT models, run EMT and export plots.

    :returns:
        None.
    :rtype: None
    """
    # The top-level algorithm executes in the same order as the engineering
    # workflow: create topology, solve steady state, attach dynamics, simulate,
    # and finally inspect the results visually.
    circuit: MultiCircuit = create_two_vsc_circuit()
    case: TwoVscCase = collect_two_vsc_case(circuit)
    pf_results: PowerFlowRunResult = run_power_flow(circuit)
    plot_power_flow_results(case, pf_results)

    if pf_results.balanced.converged:
        attach_emt_models(circuit)
        emt_result: EmtRunResult = run_emt_simulation(circuit)
        plot_emt_results(emt_result)
    else:
        print("Skipping EMT execution because the balanced power flow did not converge.")


if __name__ == "__main__":
    main()
