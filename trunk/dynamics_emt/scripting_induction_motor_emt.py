from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


def _ensure_repo_paths() -> None:
    """Add the repository source folders to ``sys.path``.

    :return: None.
    """
    current_file: Path = Path(__file__).resolve()
    repo_root: Path = current_file.parents[2]
    src_root: Path = repo_root / "src"

    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    else:
        pass

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    else:
        pass


_ensure_repo_paths()

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_balanced_3ph_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.induction_motor_emt_template import get_induction_motor_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    ShuntConnectionType,
    SolverType,
)


class MechanicalTorqueStepUpdater:
    """Apply one piecewise-constant step to the motor nominal load torque.

    :ivar _parameter_index: Runtime parameter slot of ``t_load_nom``.
    :ivar _step_time_s: Event time in seconds.
    :ivar _initial_value: Torque coefficient before the event.
    :ivar _final_value: Torque coefficient after the event.
    """

    __slots__ = ("_parameter_index", "_step_time_s", "_initial_value", "_final_value")

    def __init__(self, parameter_index: int, step_time_s: float, initial_value: float, final_value: float) -> None:
        """Build one mechanical-torque step updater.

        :param parameter_index: Runtime parameter index in ``full_params``.
        :param step_time_s: Event time in seconds.
        :param initial_value: Value before the step.
        :param final_value: Value after the step.
        :return: None.
        """
        self._parameter_index = int(parameter_index)
        self._step_time_s = float(step_time_s)
        self._initial_value = float(initial_value)
        self._final_value = float(final_value)

    def update(self, t_curr: float, _x_prev: np.ndarray, full_params: np.ndarray) -> None:
        """Update the runtime torque parameter.

        :param t_curr: Current simulation time.
        :param _x_prev: Previous state vector.
        :param full_params: Mutable runtime parameter vector.
        :return: None.
        """
        if t_curr < self._step_time_s:
            full_params[self._parameter_index] = self._initial_value
        else:
            full_params[self._parameter_index] = self._final_value

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """Return the next event time inside the current solver step.

        :param t_prev: Previous accepted time.
        :param t_target: Tentative target time.
        :return: Step time when it lies inside ``(t_prev, t_target]``.
        """
        if t_prev < self._step_time_s <= t_target:
            return self._step_time_s
        else:
            return None

    @property
    def step_time_s(self) -> float:
        """Return the configured event time.

        :return: Torque-step time in seconds.
        """
        return self._step_time_s


@dataclass(frozen=True)
class InductionMotorDemoConfig:
    """Configuration for one induction-motor EMT demo case."""

    level: int
    label: str
    model_name: str
    output_folder_name: str


@dataclass
class InductionMotorDiagnostics:
    """Key cycle-averaged diagnostics collected from one demo run."""

    p_cycle_initial: float
    p_cycle_pre_event: float
    q_cycle_initial: float
    q_cycle_pre_event: float
    te_cycle_pre_event: float
    tm_cycle_pre_event: float
    omega_cycle_pre_event: float
    slip_cycle_pre_event: float


@dataclass
class InductionMotorDemoResult:
    """Outcome summary for one induction-motor EMT demo case."""

    config: InductionMotorDemoConfig
    plot_path: Path
    converged: bool
    diagnostics: Optional[InductionMotorDiagnostics]
    failure_reason: Optional[str]


def _build_demo_configs() -> list[InductionMotorDemoConfig]:
    """Return the ordered induction-motor EMT demo cases."""
    return [
        InductionMotorDemoConfig(
            level=2,
            label="single-cage EMT model",
            model_name="induction_motor_level_2",
            output_folder_name="level_2_single_cage",
        ),
        InductionMotorDemoConfig(
            level=3,
            label="double-cage EMT model",
            model_name="induction_motor_level_3",
            output_folder_name="level_3_double_cage",
        ),
    ]


def _motor_var_name(base_name: str, motor_name: str) -> str:
    """Return one motor-scoped symbolic variable name."""
    return f"{base_name}_{motor_name}"


def _get_output_directory(config: InductionMotorDemoConfig) -> Path:
    """Return the per-level plot output directory."""
    return Path(__file__).resolve().parent / "plot_results" / "induction_motor_emt" / config.output_folder_name


def _set_common_motor_parameters(motor_block: Block, motor_name: str, motor_parameters: Dict[str, float]) -> None:
    """Apply the parameters shared by all motor template levels."""
    shared_parameter_name: str

    for shared_parameter_name in ["r_s", "x_ls", "x_m", "H", "D", "slip_init", "slip_min", "slip_max", "speed_eps"]:
        motor_block.set_parameter_in_model(
            var_name=_motor_var_name(shared_parameter_name, motor_name),
            new_value=motor_parameters[shared_parameter_name],
        )


def _set_level_specific_motor_parameters(
    motor_block: Block,
    motor_level: int,
    motor_name: str,
    motor_parameters: Dict[str, float],
) -> None:
    """Apply the rotor parameters required by the selected model level."""
    if motor_level == 3:
        motor_block.set_parameter_in_model(var_name=_motor_var_name("r_r1", motor_name), new_value=motor_parameters["r_r1"])
        motor_block.set_parameter_in_model(var_name=_motor_var_name("x_lr1", motor_name), new_value=motor_parameters["x_lr1"])
        motor_block.set_parameter_in_model(var_name=_motor_var_name("r_r2", motor_name), new_value=motor_parameters["r_r2"])
        motor_block.set_parameter_in_model(var_name=_motor_var_name("x_lr2", motor_name), new_value=motor_parameters["x_lr2"])
    else:
        motor_block.set_parameter_in_model(var_name=_motor_var_name("r_r", motor_name), new_value=motor_parameters["r_r"])
        motor_block.set_parameter_in_model(var_name=_motor_var_name("x_lr", motor_name), new_value=motor_parameters["x_lr"])


def _build_equivalent_point_for_double_cage(
    voltage_phasors: Tuple[complex, complex, complex],
    p_targets_pu: Tuple[float, float, float],
    q_targets_pu: Tuple[float, float, float],
    motor_parameters: Dict[str, float],
) -> Dict[str, float | complex | Tuple[complex, complex, complex]]:
    """Compute an approximate steady-state point for the Level-3 double-cage model."""
    v_a: complex = voltage_phasors[0]
    v_b: complex = voltage_phasors[1]
    v_c: complex = voltage_phasors[2]
    s_a_target: complex = complex(p_targets_pu[0], q_targets_pu[0])
    s_b_target: complex = complex(p_targets_pu[1], q_targets_pu[1])
    s_c_target: complex = complex(p_targets_pu[2], q_targets_pu[2])
    i_a_target: complex = np.conj(s_a_target / (v_a + 1e-12))
    i_b_target: complex = np.conj(s_b_target / (v_b + 1e-12))
    i_c_target: complex = np.conj(s_c_target / (v_c + 1e-12))
    v_pos: complex = (v_a + np.exp(1j * 2.0 * np.pi / 3.0) * v_b + np.exp(-1j * 2.0 * np.pi / 3.0) * v_c) / 3.0
    i_pos_target: complex = (i_a_target + np.exp(1j * 2.0 * np.pi / 3.0) * i_b_target + np.exp(-1j * 2.0 * np.pi / 3.0) * i_c_target) / 3.0
    z_s: complex = complex(motor_parameters["r_s"], motor_parameters["x_ls"])
    z_m: complex = complex(0.0, motor_parameters["x_m"])
    v_airgap_target: complex = v_pos - z_s * i_pos_target
    y_m: complex = 1.0 / (z_m + 1e-12)
    y_rot_total: complex = i_pos_target / (v_airgap_target + 1e-12) - y_m
    z_rot_total: complex = 1.0 / (y_rot_total + 1e-12)
    slip_estimate: float = float(np.clip(
        motor_parameters["r_r1"] / max(np.real(z_rot_total), motor_parameters["r_r1"] / motor_parameters["slip_max"]),
        motor_parameters["slip_min"],
        motor_parameters["slip_max"],
    ))
    z_r1: complex = complex(motor_parameters["r_r1"] / max(slip_estimate, 1e-9), motor_parameters["x_lr1"])
    z_r2: complex = complex(motor_parameters["r_r2"] / max(slip_estimate, 1e-9), motor_parameters["x_lr2"])
    z_r: complex = (z_r1 * z_r2) / (z_r1 + z_r2 + 1e-12)
    z_parallel: complex = (z_m * z_r) / (z_m + z_r + 1e-12)
    z_in: complex = z_s + z_parallel
    i_pos_model: complex = v_pos / (z_in + 1e-12)
    i_a_model: complex = i_pos_model
    i_b_model: complex = np.exp(-1j * 2.0 * np.pi / 3.0) * i_pos_model
    i_c_model: complex = np.exp(1j * 2.0 * np.pi / 3.0) * i_pos_model
    s_total_model: complex = v_a * np.conj(i_a_model) + v_b * np.conj(i_b_model) + v_c * np.conj(i_c_model)
    return dict({
        "slip": slip_estimate,
        "omega": 1.0 - slip_estimate,
        "p_total": float(np.real(s_total_model)),
        "q_total": float(np.imag(s_total_model)),
        "currents": (i_a_model, i_b_model, i_c_model),
        "phase_lag_rad": float(np.angle(v_a) - np.angle(i_a_model)),
    })


def _abc_to_alpha_beta_samples(abc_matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Transform one sampled ABC waveform to alpha-beta coordinates.

    :param abc_matrix: Sample matrix with shape ``(n_samples, 3)``.
    :return: Alpha and beta sample vectors.
    """
    alpha_vector: np.ndarray = (2.0 / 3.0) * (abc_matrix[:, 0] - 0.5 * abc_matrix[:, 1] - 0.5 * abc_matrix[:, 2])
    beta_vector: np.ndarray = (1.0 / np.sqrt(3.0)) * (abc_matrix[:, 1] - abc_matrix[:, 2])
    return alpha_vector, beta_vector


def _estimate_peak_phasor(time_values: np.ndarray, sample_values: np.ndarray, frequency_hz: float) -> complex:
    """Estimate one sinusoidal peak phasor from sampled data.

    :param time_values: Time vector.
    :param sample_values: Sampled waveform over one cycle.
    :param frequency_hz: Fundamental frequency.
    :return: Estimated peak phasor.
    """
    omega_base: float = 2.0 * np.pi * frequency_hz
    dt: float = float(np.mean(np.diff(time_values)))
    kernel: np.ndarray = np.exp(-1j * omega_base * time_values)
    return complex((2.0j / max(sample_values.size, 1)) * np.sum(sample_values * kernel))


def _extract_cycle_window(time_values: np.ndarray, frequency_hz: float, start_time_s: float) -> np.ndarray:
    """Return the boolean mask for one electrical cycle.

    :param time_values: Time vector.
    :param frequency_hz: Fundamental frequency.
    :param start_time_s: Window start time.
    :return: Boolean mask selecting one cycle.
    """
    cycle_duration_s: float = 1.0 / frequency_hz
    return np.logical_and(time_values >= start_time_s, time_values < start_time_s + cycle_duration_s)


def _cycle_mean(time_values: np.ndarray, sample_values: np.ndarray, frequency_hz: float, start_time_s: float) -> float:
    """Return the mean value over one electrical cycle.

    :param time_values: Time vector.
    :param sample_values: Sample vector.
    :param frequency_hz: Fundamental frequency.
    :param start_time_s: Cycle start time.
    :return: Mean over the selected cycle.
    """
    cycle_mask: np.ndarray = _extract_cycle_window(time_values=time_values, frequency_hz=frequency_hz, start_time_s=start_time_s)
    return float(np.mean(sample_values[cycle_mask]))


def _cycle_average_trace(time_values: np.ndarray, sample_values: np.ndarray, frequency_hz: float) -> np.ndarray:
    """Return one centered moving average over one electrical cycle.

    :param time_values: Time vector.
    :param sample_values: Sample vector.
    :param frequency_hz: Fundamental frequency.
    :return: One-cycle averaged trace.
    """
    dt: float = float(np.mean(np.diff(time_values)))
    samples_per_cycle: int = max(int(round((1.0 / frequency_hz) / max(dt, 1e-12))), 1)
    kernel: np.ndarray = np.ones(samples_per_cycle, dtype=np.float64) / float(samples_per_cycle)
    return np.convolve(sample_values, kernel, mode="same")


def _compute_equivalent_circuit_initialization(
    voltage_phasors: Tuple[complex, complex, complex],
    p_targets_pu: Tuple[float, float, float],
    q_targets_pu: Tuple[float, float, float],
    motor_parameters: Dict[str, float],
) -> Dict[str, float | complex | Tuple[complex, complex, complex]]:
    """Compute the single-cage positive-sequence steady-state used by the demo.

    :param voltage_phasors: Terminal phase-voltage RMS phasors in per unit.
    :param p_targets_pu: Per-phase active-power targets in per unit.
    :param q_targets_pu: Per-phase reactive-power targets in per unit.
    :param motor_parameters: Demo motor parameter dictionary.
    :return: Dictionary with initialized current, power and slip values.
    """
    v_a: complex = voltage_phasors[0]
    v_b: complex = voltage_phasors[1]
    v_c: complex = voltage_phasors[2]
    s_a_target: complex = complex(p_targets_pu[0], q_targets_pu[0])
    s_b_target: complex = complex(p_targets_pu[1], q_targets_pu[1])
    s_c_target: complex = complex(p_targets_pu[2], q_targets_pu[2])
    i_a_target: complex = np.conj(s_a_target / (v_a + 1e-12))
    i_b_target: complex = np.conj(s_b_target / (v_b + 1e-12))
    i_c_target: complex = np.conj(s_c_target / (v_c + 1e-12))
    v_pos: complex = (v_a + np.exp(1j * 2.0 * np.pi / 3.0) * v_b + np.exp(-1j * 2.0 * np.pi / 3.0) * v_c) / 3.0
    i_pos_target: complex = (i_a_target + np.exp(1j * 2.0 * np.pi / 3.0) * i_b_target + np.exp(-1j * 2.0 * np.pi / 3.0) * i_c_target) / 3.0
    z_s: complex = complex(motor_parameters["r_s"], motor_parameters["x_ls"])
    z_m: complex = complex(0.0, motor_parameters["x_m"])
    v_airgap_target: complex = v_pos - z_s * i_pos_target
    i_mag_target: complex = v_airgap_target / (z_m + 1e-12j)
    i_rotor_target: complex = i_pos_target - i_mag_target
    z_rotor_est: complex = v_airgap_target / (i_rotor_target + 1e-12)
    slip_estimate: float = float(np.clip(
        motor_parameters["r_r"] / max(np.real(z_rotor_est), motor_parameters["r_r"] / motor_parameters["slip_max"]),
        motor_parameters["slip_min"],
        motor_parameters["slip_max"],
    ))
    z_r: complex = complex(motor_parameters["r_r"] / slip_estimate, motor_parameters["x_lr"])
    z_parallel: complex = (z_m * z_r) / (z_m + z_r + 1e-12)
    z_in: complex = z_s + z_parallel
    i_pos_model: complex = v_pos / (z_in + 1e-12)
    i_a_model: complex = i_pos_model
    i_b_model: complex = np.exp(-1j * 2.0 * np.pi / 3.0) * i_pos_model
    i_c_model: complex = np.exp(1j * 2.0 * np.pi / 3.0) * i_pos_model
    s_total_model: complex = v_a * np.conj(i_a_model) + v_b * np.conj(i_b_model) + v_c * np.conj(i_c_model)
    return dict({
        "slip": slip_estimate,
        "omega": 1.0 - slip_estimate,
        "p_total": float(np.real(s_total_model)),
        "q_total": float(np.imag(s_total_model)),
        "currents": (i_a_model, i_b_model, i_c_model),
        "phase_lag_rad": float(np.angle(v_a) - np.angle(i_a_model)),
    })


def _build_pf_options() -> PowerFlowOptions:
    """Build one compact three-phase power-flow option set.

    :return: Power-flow options.
    """
    return PowerFlowOptions(
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


def _build_emt_options() -> EmtOptions:
    """Build one EMT option set for the induction-motor demo.

    :return: EMT options.
    """
    return EmtOptions(
        time_step=2.0e-5,
        simulation_time=0.60,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=0,
    )


def _build_demo_grid(
    motor_level: int,
    motor_name: str,
) -> Tuple[MultiCircuit, Bus, Bus, Line, Generator, Load, Block, Dict[str, float]]:
    """Build one simple EMT-ready network with a source, a line and one motor.

    The load object supplies the power-flow operating point, while the EMT model
    attached to it is the new induction-motor template.

    :return: Tuple with the grid, buses, line, generator, load, motor block and motor parameters.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=2.0, fbase=50.0)
    vnom_kv: float = 10.0

    bus_slack: Bus = Bus(name="Bus_Slack", Vnom=vnom_kv, is_slack=True)
    bus_motor: Bus = Bus(name="Bus_Motor", Vnom=vnom_kv)
    grid.add_bus(bus_slack)
    grid.add_bus(bus_motor)

    line: Line = Line(name="Line_Motor", bus_from=bus_slack, bus_to=bus_motor, length=1.0, rate=900.0)
    tower: OverheadLineType = OverheadLineType(name="Tower_Motor", Vnom=vnom_kv)
    wire: Wire = Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1.0,
    )
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line.apply_template(tower, grid.Sbase, grid.fBase)
    grid.add_line(line)

    generator: Generator = Generator(name="Gen_Thevenin", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=1.7)
    grid.add_generator(bus=bus_slack, api_obj=generator)

    # The power-flow load is only the steady-state anchor used to initialize the
    # EMT bus phasors. The actual EMT dynamics come from the induction-motor block.
    load: Load = Load(name="Motor_Load", P1=0.18, P2=0.18, P3=0.18, Q1=0.08, Q2=0.08, Q3=0.08)
    load.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_motor, api_obj=load)

    motor_parameters: Dict[str, float] = dict({
        "r_s": 0.03,
        "x_ls": 0.04,
        "x_m": 25.0,
        "r_r": 0.02,
        "x_lr": 0.04,
        "r_r1": 0.025,
        "x_lr1": 0.10,
        "r_r2": 0.08,
        "x_lr2": 0.35,
        "H": 0.45,
        "D": 0.01,
        "slip_init": 0.02,
        "slip_min": 1e-3,
        "slip_max": 1.0,
        "speed_eps": 1e-3,
    })

    get_bus_emt_template(grid, bus_slack)
    get_bus_emt_template(grid, bus_motor)

    generator_block: Block = get_balanced_3ph_voltage_source_emt_template(
        vf=grid.var_factory,
        amplitude_value=np.sqrt(2.0),
        frequency_hz=50.0,
        phase_a_deg=0.0,
        offset_value=0.0,
        source_conductance_value=500.0,
        name="gen_motor_demo",
    ).block
    line_block: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name="Pi_Motor_Demo").block
    motor_block: Block = get_induction_motor_emt_template(vf=grid.var_factory, level=motor_level, name=motor_name).block

    set_emt_model(device=generator, model=generator_block, var_factory=grid.var_factory)
    set_emt_model(device=line, model=line_block, var_factory=grid.var_factory)
    set_emt_model(device=load, model=motor_block, var_factory=grid.var_factory)

    _set_common_motor_parameters(motor_block=motor_block, motor_name=motor_name, motor_parameters=motor_parameters)
    _set_level_specific_motor_parameters(
        motor_block=motor_block,
        motor_level=motor_level,
        motor_name=motor_name,
        motor_parameters=motor_parameters,
    )

    return grid, bus_slack, bus_motor, line, generator, load, motor_block, motor_parameters


def _get_series(problem: EmtProblemDae, block: Block, variable_name: str, y_values: np.ndarray) -> np.ndarray:
    """Extract one variable trajectory from the global EMT state matrix.

    :param problem: EMT problem.
    :param block: Block that owns the variable.
    :param variable_name: Variable name inside the block tree.
    :param y_values: Global EMT trajectory matrix.
    :return: Variable time series.
    :raises ValueError: If the variable cannot be located.
    """
    variable: Optional[Var] = find_name_in_block(variable_name, block)

    if variable is None:
        raise ValueError(f"Variable '{variable_name}' was not found in block '{block.name}'.")
    else:
        return y_values[:, problem.get_var_idx(variable)]


def _find_event_var_by_name(block: Block, variable_name: str) -> Var | None:
    """Find one event-parameter variable by name in a block tree.

    :param block: Root block.
    :param variable_name: Requested variable name.
    :return: Matching variable or ``None``.
    """
    parameter_var: Var

    for parameter_var in block.event_dict.keys():
        if parameter_var.name == variable_name:
            return parameter_var
        else:
            pass

    child_block: Block
    for child_block in block.children:
        nested_var: Var | None = _find_event_var_by_name(child_block, variable_name)

        if nested_var is not None:
            return nested_var
        else:
            pass

    return None


def _get_runtime_event_value(problem: EmtProblemDae, parameter_var: Var) -> float:
    """Return one initialized runtime event-parameter value.

    :param problem: EMT problem with initialized runtime parameters.
    :param parameter_var: Event-parameter symbolic variable.
    :return: Initialized runtime value.
    :raises ValueError: If the runtime parameter index is not available.
    """
    runtime_index: int | None = problem.uid2idx_event_params.get(parameter_var.uid, None)

    if runtime_index is None:
        raise ValueError(f"The runtime index for parameter '{parameter_var.name}' was not found.")
    else:
        return float(problem._event_params_values[runtime_index])


def _extract_three_phase_matrix(problem: EmtProblemDae, y_values: np.ndarray, variables: Tuple[Var, Var, Var]) -> np.ndarray:
    """Extract one three-phase matrix from the global EMT trajectory.

    :param problem: EMT problem.
    :param y_values: Global EMT trajectory matrix.
    :param variables: Three symbolic variables in A-B-C order.
    :return: Matrix with shape ``(n_steps, 3)``.
    """
    out_matrix: np.ndarray = np.zeros((y_values.shape[0], 3), dtype=np.float64)
    phase_index: int = 0

    while phase_index < 3:
        out_matrix[:, phase_index] = y_values[:, problem.get_var_idx(variables[phase_index])]
        phase_index += 1

    return out_matrix


def _run_power_flow(grid: MultiCircuit) -> object:
    """Run the three-phase power flow used by EMT initialization.

    :param grid: Demo grid.
    :return: Three-phase power-flow results.
    :raises RuntimeError: If the power flow does not converge.
    """
    # driver: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, _build_pf_options())
    # driver.run()
    # print(f"Powerflow results: {driver.results}")

    power_flow = PowerFlowDriver3Ph(grid, _build_pf_options())
    power_flow.run()
    res = power_flow.results
    print("res.m (branch number)= ", res.m)
    print("res.n (bus number)= ", res.n)
    print("res.n_gen = ", res.n_gen)
    print("res.n_load ", res.n_load)
    print("res.bus_names = ", res.bus_names)
    print("res.branch_names = ", res.branch_names)
    print("res.load_names = ", res.load_names)
    print("res.bus_types = ", res.bus_types)
    print("res.voltage_A = ", res.voltage_A)
    print("res.voltage_B = ", res.voltage_B)
    print("res.voltage_C = ", res.voltage_C)
    print("res.Sbus_A = ", res.Sbus_A)
    print("res.Sbus_B = ", res.Sbus_B)
    print("res.Sbus_C = ", res.Sbus_C)
    print("res.Sf_A = ", res.Sf_A)
    print("res.Sf_B = ", res.Sf_B)
    print("res.Sf_C = ", res.Sf_C)
    print("res.St_A = ", res.St_A)
    print("res.St_B = ", res.St_B)
    print("res.St_C = ", res.St_C)

    print(f"Converged: {res.converged}")
    print(res.get_bus_df())
    print(res.get_branch_df())

    if not res.converged:
        raise RuntimeError("The induction-motor demo power flow did not converge.")
    else:
        return res


def _build_problem(grid: MultiCircuit, pf_results_3ph: object) -> EmtProblemDae:
    """Build the EMT problem.

    :param grid: Demo grid.
    :param pf_results_3ph: Three-phase power-flow results.
    :return: EMT problem.
    """
    return EmtProblemDae(grid=grid, options=_build_emt_options(), pf_results=None, pf_results_3ph=pf_results_3ph)


def _compute_equivalent_point(
    config: InductionMotorDemoConfig,
    voltage_phasors: Tuple[complex, complex, complex],
    load: Load,
    grid: MultiCircuit,
    motor_parameters: Dict[str, float],
) -> Dict[str, float | complex | Tuple[complex, complex, complex]]:
    """Compute the analytical reference point used by the diagnostics."""
    if config.level == 3:
        return _build_equivalent_point_for_double_cage(
            voltage_phasors=voltage_phasors,
            p_targets_pu=(load.Pa / grid.Sbase, load.Pb / grid.Sbase, load.Pc / grid.Sbase),
            q_targets_pu=(load.Qa / grid.Sbase, load.Qb / grid.Sbase, load.Qc / grid.Sbase),
            motor_parameters=motor_parameters,
        )
    return _compute_equivalent_circuit_initialization(
        voltage_phasors=voltage_phasors,
        p_targets_pu=(load.Pa / grid.Sbase, load.Pb / grid.Sbase, load.Pc / grid.Sbase),
        q_targets_pu=(load.Qa / grid.Sbase, load.Qb / grid.Sbase, load.Qc / grid.Sbase),
        motor_parameters=motor_parameters,
    )


def _run_simulation(problem: EmtProblemDae, boundary_updater: object | None) -> Tuple[np.ndarray, np.ndarray, bool, bool]:
    """Run one short EMT simulation.

    :param problem: EMT problem.
    :return: Time vector, state trajectory, initialization flag and convergence flag.
    """
    options: EmtOptions = _build_emt_options()
    solver: JitSymbolicSolver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=options.simulation_time,
        h=options.time_step,
        method=options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=True,
    )
    solver.build_jit_kernel(options.integration_method)
    solver._build_jit_symbolic_hybrid(options.integration_method, use_sparse=True)

    if options.integration_method == DynamicIntegrationMethod.DaeTrapezoidal:
        solver.build_jit_kernel(DynamicIntegrationMethod.DaeBackEuler)
        solver._build_jit_symbolic_hybrid(DynamicIntegrationMethod.DaeBackEuler, use_sparse=True)
    else:
        pass

    time_values, y_values, _dy_values, well_initialized, converged = solver.simulate(boundary_updater=boundary_updater)
    return time_values, y_values, well_initialized, converged


def _build_mechanical_torque_step_updater(
    problem: EmtProblemDae,
    motor_block: Block,
    motor_name: str,
) -> MechanicalTorqueStepUpdater:
    """Build one runtime torque-step updater for the demo motor.

    :param problem: EMT problem.
    :param motor_block: Motor symbolic block.
    :return: Configured boundary updater.
    :raises ValueError: If the motor torque parameter cannot be located.
    """
    torque_parameter: Optional[Var] = _find_event_var_by_name(motor_block, _motor_var_name("t_load_nom", motor_name))

    if torque_parameter is None:
        raise ValueError("The motor nominal load torque parameter was not found in the EMT block.")
    else:
        parameter_index: int = int(problem.uid2idx_event_params[torque_parameter.uid])
        initial_value: float = _get_runtime_event_value(problem=problem, parameter_var=torque_parameter)
        final_value: float = 1.2 * initial_value
        return MechanicalTorqueStepUpdater(
            parameter_index=parameter_index,
            step_time_s=0.35,
            initial_value=initial_value,
            final_value=final_value,
        )


def _collect_diagnostics(
    grid: MultiCircuit,
    time_values: np.ndarray,
    active_power: np.ndarray,
    reactive_power: np.ndarray,
    speed: np.ndarray,
    slip: np.ndarray,
    torque_e: np.ndarray,
    torque_m: np.ndarray,
    step_time_s: float,
) -> InductionMotorDiagnostics:
    """Collect the key cycle-averaged diagnostics used for the final summary."""
    cycle_duration_s: float = 1.0 / grid.fBase
    initial_cycle_start_s: float = 0.0
    pre_event_cycle_start_s: float = max(step_time_s - cycle_duration_s - 0.005, 0.0)
    return InductionMotorDiagnostics(
        p_cycle_initial=_cycle_mean(time_values=time_values, sample_values=active_power, frequency_hz=grid.fBase, start_time_s=initial_cycle_start_s),
        p_cycle_pre_event=_cycle_mean(time_values=time_values, sample_values=active_power, frequency_hz=grid.fBase, start_time_s=pre_event_cycle_start_s),
        q_cycle_initial=_cycle_mean(time_values=time_values, sample_values=reactive_power, frequency_hz=grid.fBase, start_time_s=initial_cycle_start_s),
        q_cycle_pre_event=_cycle_mean(time_values=time_values, sample_values=reactive_power, frequency_hz=grid.fBase, start_time_s=pre_event_cycle_start_s),
        te_cycle_pre_event=_cycle_mean(time_values=time_values, sample_values=torque_e, frequency_hz=grid.fBase, start_time_s=pre_event_cycle_start_s),
        tm_cycle_pre_event=_cycle_mean(time_values=time_values, sample_values=torque_m, frequency_hz=grid.fBase, start_time_s=pre_event_cycle_start_s),
        omega_cycle_pre_event=_cycle_mean(time_values=time_values, sample_values=speed, frequency_hz=grid.fBase, start_time_s=pre_event_cycle_start_s),
        slip_cycle_pre_event=_cycle_mean(time_values=time_values, sample_values=slip, frequency_hz=grid.fBase, start_time_s=pre_event_cycle_start_s),
    )


def _print_debug_values(
    config: InductionMotorDemoConfig,
    load: Load,
    grid: MultiCircuit,
    bus_voltages: np.ndarray,
    time_values: np.ndarray,
    motor_currents: np.ndarray,
    active_power: np.ndarray,
    reactive_power: np.ndarray,
    speed: np.ndarray,
    slip: np.ndarray,
    torque_e: np.ndarray,
    torque_m: np.ndarray,
    equivalent_point: Dict[str, float | complex | Tuple[complex, complex, complex]],
    motor_parameters: Dict[str, float],
    step_time_s: float,
) -> InductionMotorDiagnostics:
    """Print initialization and final-value debug checks for the demo motor.

    :param load: Power-flow load object.
    :param grid: Demo grid.
    :param bus_voltages: Three-phase terminal voltages.
    :param time_values: Simulation time vector.
    :param motor_currents: Three-phase absorbed motor currents.
    :param active_power: Motor active-power series in pu.
    :param reactive_power: Motor reactive-power series in pu.
    :param speed: Rotor speed series.
    :param slip: Rotor slip series.
    :param torque_e: Electromagnetic torque series.
    :param torque_m: Mechanical torque series.
    :param equivalent_point: Analytical motor steady-state operating point.
    :param motor_parameters: Demo motor parameter dictionary.
    :param step_time_s: Torque-step time.
    :return: None.
    """
    diagnostics: InductionMotorDiagnostics = _collect_diagnostics(
        grid=grid,
        time_values=time_values,
        active_power=active_power,
        reactive_power=reactive_power,
        speed=speed,
        slip=slip,
        torque_e=torque_e,
        torque_m=torque_m,
        step_time_s=step_time_s,
    )
    p0_target: float = float((load.Pa + load.Pb + load.Pc) / grid.Sbase)
    q0_target: float = float((load.Qa + load.Qb + load.Qc) / grid.Sbase)
    cycle_duration_s: float = 1.0 / grid.fBase
    initial_cycle_start_s: float = 0.0
    pre_event_cycle_start_s: float = max(step_time_s - cycle_duration_s - 0.005, 0.0)
    final_cycle_start_s: float = max(time_values[-1] - cycle_duration_s, 0.0)
    pre_event_mask: np.ndarray = _extract_cycle_window(
        time_values=time_values,
        frequency_hz=grid.fBase,
        start_time_s=pre_event_cycle_start_s,
    )
    post_event_mask: np.ndarray = time_values >= max(step_time_s + 0.02, step_time_s)
    initial_cycle_mask: np.ndarray = _extract_cycle_window(time_values=time_values, frequency_hz=grid.fBase, start_time_s=initial_cycle_start_s)
    p_pre_event: float = float(np.mean(active_power[pre_event_mask]))
    q_pre_event: float = float(np.mean(reactive_power[pre_event_mask]))
    p_post_event: float = float(np.mean(active_power[post_event_mask]))
    q_post_event: float = float(np.mean(reactive_power[post_event_mask]))
    te_pre_event: float = float(np.mean(torque_e[pre_event_mask]))
    tm_pre_event: float = float(np.mean(torque_m[pre_event_mask]))
    omega_pre_event: float = float(np.mean(speed[pre_event_mask]))
    slip_pre_event: float = float(np.mean(slip[pre_event_mask]))
    i_rms_initial: np.ndarray = np.sqrt(np.mean(motor_currents[initial_cycle_mask, :] ** 2.0, axis=0))
    voltage_a_peak: complex = _estimate_peak_phasor(time_values[initial_cycle_mask], bus_voltages[initial_cycle_mask, 0], grid.fBase)
    current_a_peak: complex = _estimate_peak_phasor(time_values[initial_cycle_mask], motor_currents[initial_cycle_mask, 0], grid.fBase)
    phase_lag_initial_deg: float = float(np.degrees(np.angle(voltage_a_peak) - np.angle(current_a_peak)))
    voltage_alpha, voltage_beta = _abc_to_alpha_beta_samples(bus_voltages[initial_cycle_mask, :])
    current_alpha, current_beta = _abc_to_alpha_beta_samples(motor_currents[initial_cycle_mask, :])
    p_abc_cycle: float = float(np.mean(np.sum(bus_voltages[initial_cycle_mask, :] * motor_currents[initial_cycle_mask, :], axis=1)))
    p_alpha_beta_cycle: float = float(np.mean(1.5 * (voltage_alpha * current_alpha + voltage_beta * current_beta)))
    q_alpha_beta_cycle: float = float(np.mean(1.5 * (voltage_beta * current_alpha - voltage_alpha * current_beta)))
    p_cycle_initial: float = diagnostics.p_cycle_initial
    q_cycle_initial: float = diagnostics.q_cycle_initial
    te_cycle_initial: float = _cycle_mean(time_values=time_values, sample_values=torque_e, frequency_hz=grid.fBase, start_time_s=initial_cycle_start_s)
    tm_cycle_initial: float = _cycle_mean(time_values=time_values, sample_values=torque_m, frequency_hz=grid.fBase, start_time_s=initial_cycle_start_s)
    omega_cycle_initial: float = _cycle_mean(time_values=time_values, sample_values=speed, frequency_hz=grid.fBase, start_time_s=initial_cycle_start_s)
    slip_cycle_initial: float = _cycle_mean(time_values=time_values, sample_values=slip, frequency_hz=grid.fBase, start_time_s=initial_cycle_start_s)
    p_cycle_pre_event: float = diagnostics.p_cycle_pre_event
    q_cycle_pre_event: float = diagnostics.q_cycle_pre_event
    te_cycle_pre_event: float = diagnostics.te_cycle_pre_event
    tm_cycle_pre_event: float = diagnostics.tm_cycle_pre_event
    omega_cycle_pre_event: float = diagnostics.omega_cycle_pre_event
    slip_cycle_pre_event: float = diagnostics.slip_cycle_pre_event
    p_cycle_final: float = _cycle_mean(time_values=time_values, sample_values=active_power, frequency_hz=grid.fBase, start_time_s=final_cycle_start_s)
    q_cycle_final: float = _cycle_mean(time_values=time_values, sample_values=reactive_power, frequency_hz=grid.fBase, start_time_s=final_cycle_start_s)
    te_cycle_final: float = _cycle_mean(time_values=time_values, sample_values=torque_e, frequency_hz=grid.fBase, start_time_s=final_cycle_start_s)
    tm_cycle_final: float = _cycle_mean(time_values=time_values, sample_values=torque_m, frequency_hz=grid.fBase, start_time_s=final_cycle_start_s)
    omega_cycle_final: float = _cycle_mean(time_values=time_values, sample_values=speed, frequency_hz=grid.fBase, start_time_s=final_cycle_start_s)
    slip_cycle_final: float = _cycle_mean(time_values=time_values, sample_values=slip, frequency_hz=grid.fBase, start_time_s=final_cycle_start_s)

    print(f"--- Diagnostics: level {config.level} ({config.label}) ---")
    print(f"P0_target [pu]: {p0_target:.6f}")
    print(f"Q0_target [pu]: {q0_target:.6f}")
    print(f"P_eq_init [pu]: {float(equivalent_point['p_total']):.6f}")
    print(f"Q_eq_init [pu]: {float(equivalent_point['q_total']):.6f}")
    print(f"P_initial [pu]: {active_power[0]:.6f}")
    print(f"Q_initial [pu]: {reactive_power[0]:.6f}")
    print(f"P_cycle_initial [pu]: {p_cycle_initial:.6f}")
    print(f"Q_cycle_initial [pu]: {q_cycle_initial:.6f}")
    print(f"P_pre_event [pu]: {p_pre_event:.6f}")
    print(f"Q_pre_event [pu]: {q_pre_event:.6f}")
    print(f"P_cycle_pre_event [pu]: {p_cycle_pre_event:.6f}")
    print(f"Q_cycle_pre_event [pu]: {q_cycle_pre_event:.6f}")
    print(f"P_post_event [pu]: {p_post_event:.6f}")
    print(f"Q_post_event [pu]: {q_post_event:.6f}")
    print(f"P_cycle_final [pu]: {p_cycle_final:.6f}")
    print(f"Q_cycle_final [pu]: {q_cycle_final:.6f}")
    print(
        "iabc_initial [pu]: "
        f"[{motor_currents[0, 0]:.6f}, {motor_currents[0, 1]:.6f}, {motor_currents[0, 2]:.6f}]"
    )
    print(
        "iabc_rms_initial [pu]: "
        f"[{i_rms_initial[0]:.6f}, {i_rms_initial[1]:.6f}, {i_rms_initial[2]:.6f}]"
    )
    print(f"Current phase lag initial [deg]: {phase_lag_initial_deg:.6f}")
    print(f"Cycle P_abc initial [pu]: {p_abc_cycle:.6f}")
    print(f"Cycle P_alpha_beta initial [pu]: {p_alpha_beta_cycle:.6f}")
    print(f"Cycle Q_alpha_beta initial [pu]: {q_alpha_beta_cycle:.6f}")
    print(f"Te_initial [pu]: {torque_e[0]:.6f}")
    print(f"Tm_initial [pu]: {torque_m[0]:.6f}")
    print(f"Te_cycle_initial [pu]: {te_cycle_initial:.6f}")
    print(f"Tm_cycle_initial [pu]: {tm_cycle_initial:.6f}")
    print(f"Te_pre_event [pu]: {te_pre_event:.6f}")
    print(f"Tm_pre_event [pu]: {tm_pre_event:.6f}")
    print(f"Te_cycle_pre_event [pu]: {te_cycle_pre_event:.6f}")
    print(f"Tm_cycle_pre_event [pu]: {tm_cycle_pre_event:.6f}")
    print(f"Te_cycle_final [pu]: {te_cycle_final:.6f}")
    print(f"Tm_cycle_final [pu]: {tm_cycle_final:.6f}")
    print(f"omega_initial [pu]: {speed[0]:.6f}")
    print(f"slip_initial [pu]: {slip[0]:.6f}")
    print(f"omega_cycle_initial [pu]: {omega_cycle_initial:.6f}")
    print(f"slip_cycle_initial [pu]: {slip_cycle_initial:.6f}")
    print(f"omega_pre_event [pu]: {omega_pre_event:.6f}")
    print(f"slip_pre_event [pu]: {slip_pre_event:.6f}")
    print(f"omega_cycle_pre_event [pu]: {omega_cycle_pre_event:.6f}")
    print(f"slip_cycle_pre_event [pu]: {slip_cycle_pre_event:.6f}")
    print(f"omega_cycle_final [pu]: {omega_cycle_final:.6f}")
    print(f"slip_cycle_final [pu]: {slip_cycle_final:.6f}")
    print(
        f"Torque balance pre-event [pu]: "
        f"{te_cycle_pre_event - (tm_cycle_pre_event + motor_parameters['D'] * (omega_cycle_pre_event - 1.0)):.6f}"
    )
    return diagnostics


def _plot_results(
    config: InductionMotorDemoConfig,
    output_directory: Path,
    time_values: np.ndarray,
    bus_voltages: np.ndarray,
    motor_currents: np.ndarray,
    active_power: np.ndarray,
    reactive_power: np.ndarray,
    speed: np.ndarray,
    slip: np.ndarray,
    torque_e: np.ndarray,
    torque_m: np.ndarray,
    step_time_s: float,
    frequency_hz: float,
) -> None:
    """Write the requested demo plots.

    :param output_directory: Target directory.
    :param time_values: Simulation time vector.
    :param bus_voltages: Three-phase voltage matrix.
    :param motor_currents: Three-phase motor-current matrix.
    :param active_power: Motor active power series.
    :param reactive_power: Motor reactive power series.
    :param speed: Rotor speed series.
    :param slip: Rotor slip series.
    :param torque_e: Electromagnetic torque series.
    :param torque_m: Mechanical torque series.
    :param step_time_s: Torque-step time.
    :param frequency_hz: Fundamental frequency.
    :return: None.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    active_power_average: np.ndarray = _cycle_average_trace(time_values=time_values, sample_values=active_power, frequency_hz=frequency_hz)
    reactive_power_average: np.ndarray = _cycle_average_trace(time_values=time_values, sample_values=reactive_power, frequency_hz=frequency_hz)

    fig, axes = plt.subplots(5, 1, figsize=(11.0, 16.0), sharex=True)
    fig.suptitle(f"Induction Motor EMT Level {config.level}: {config.label}")

    axes[0].plot(time_values, bus_voltages[:, 0], label="vA")
    axes[0].plot(time_values, bus_voltages[:, 1], label="vB")
    axes[0].plot(time_values, bus_voltages[:, 2], label="vC")
    axes[0].set_ylabel("Voltage [pu]")
    axes[0].set_title(f"Level {config.level} Motor Bus Voltages abc")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")

    axes[1].plot(time_values, motor_currents[:, 0], label="iA")
    axes[1].plot(time_values, motor_currents[:, 1], label="iB")
    axes[1].plot(time_values, motor_currents[:, 2], label="iC")
    axes[1].set_ylabel("Current [pu]")
    axes[1].set_title(f"Level {config.level} Motor Absorbed Currents abc")
    axes[1].grid(True)
    axes[1].legend(loc="upper right")

    axes[2].plot(time_values, active_power, label="P")
    axes[2].plot(time_values, reactive_power, label="Q")
    axes[2].plot(time_values, active_power_average, linestyle="--", linewidth=1.0, label="P avg")
    axes[2].plot(time_values, reactive_power_average, linestyle="--", linewidth=1.0, label="Q avg")
    axes[2].set_ylabel("Power [pu]")
    axes[2].set_title(f"Level {config.level} Motor Active and Reactive Power")
    axes[2].grid(True)
    axes[2].legend(loc="upper right")

    axes[3].plot(time_values, speed, label="speed")
    axes[3].plot(time_values, slip, label="slip")
    axes[3].set_ylabel("pu")
    axes[3].set_title(f"Level {config.level} Rotor Speed and Slip")
    axes[3].grid(True)
    axes[3].legend(loc="upper right")

    axes[4].plot(time_values, torque_e, label="Te")
    axes[4].plot(time_values, torque_m, label="Tm")
    axes[4].set_xlabel("Time [s]")
    axes[4].set_ylabel("Torque [pu]")
    axes[4].set_title(f"Level {config.level} Electrical and Mechanical Torque")
    axes[4].grid(True)
    axes[4].legend(loc="upper right")

    axis_item: plt.Axes
    for axis_item in axes:
        axis_item.axvline(step_time_s, color="k", linestyle="--", linewidth=1.0)

    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.98))
    fig.savefig(output_directory / "induction_motor_emt_summary.png", dpi=150)
    plt.close(fig)


def _print_physical_checks(
    config: InductionMotorDemoConfig,
    motor_currents: np.ndarray,
    active_power: np.ndarray,
    reactive_power: np.ndarray,
    speed: np.ndarray,
) -> None:
    """Print compact physical-sense checks for the demo response.

    :param motor_currents: Three-phase motor currents.
    :param active_power: Motor active power.
    :param reactive_power: Motor reactive power.
    :param speed: Rotor speed.
    :return: None.
    """
    current_magnitude: np.ndarray = np.sqrt(np.sum(motor_currents * motor_currents, axis=1))
    final_window: int = max(int(0.05 * current_magnitude.size), 10)
    final_current_mean: float = float(np.mean(current_magnitude[-final_window:]))
    peak_current: float = float(np.max(current_magnitude))
    speed_excursion: float = float(np.max(speed) - np.min(speed))
    current_reduces: bool = bool(peak_current < 1.2 * final_current_mean)
    inductive_q: bool = bool(np.mean(reactive_power[-final_window:]) > 0.0)
    positive_p: bool = bool(np.mean(active_power[-final_window:]) > 0.0)

    print(f"--- Physical checks: level {config.level} ({config.label}) ---")
    print(f"Peak current magnitude: {peak_current:.3f} pu")
    print(f"Final current magnitude: {final_current_mean:.3f} pu")
    print(f"Final speed: {speed[-1]:.3f} pu")
    print(f"Speed excursion after torque event: {speed_excursion:.4f} pu")
    print(f"No artificial startup inrush: {current_reduces}")
    print(f"Positive active-power absorption: {positive_p}")
    print(f"Inductive reactive-power absorption: {inductive_q}")


def _run_induction_motor_emt_demo_case(config: InductionMotorDemoConfig) -> InductionMotorDemoResult:
    """Run one configured induction-motor EMT demo case and collect diagnostics."""
    grid, _bus_slack, bus_motor, _line, _generator, load, motor_block, motor_parameters = _build_demo_grid(
        motor_level=config.level,
        motor_name=config.model_name,
    )
    pf_results_3ph: object = _run_power_flow(grid)
    bus_index: int = grid.buses.index(bus_motor)
    voltage_phasors: Tuple[complex, complex, complex] = (
        complex(pf_results_3ph.voltage_A[bus_index]),
        complex(pf_results_3ph.voltage_B[bus_index]),
        complex(pf_results_3ph.voltage_C[bus_index]),
    )
    equivalent_point: Dict[str, float | complex | Tuple[complex, complex, complex]] = _compute_equivalent_point(
        config=config,
        voltage_phasors=voltage_phasors,
        load=load,
        grid=grid,
        motor_parameters=motor_parameters,
    )
    problem: EmtProblemDae = _build_problem(grid=grid, pf_results_3ph=pf_results_3ph)
    torque_step_updater: MechanicalTorqueStepUpdater = _build_mechanical_torque_step_updater(
        problem=problem,
        motor_block=motor_block,
        motor_name=config.model_name,
    )
    time_values, y_values, well_initialized, converged = _run_simulation(problem=problem, boundary_updater=torque_step_updater)

    if not well_initialized:
        raise RuntimeError(f"The induction-motor EMT demo for level {config.level} did not initialize successfully.")

    if not converged:
        raise RuntimeError(f"The induction-motor EMT demo for level {config.level} did not converge during simulation.")

    bus_voltages: np.ndarray = np.column_stack((
        _get_series(problem, bus_motor.emt_model, "v_A_Bus_Motor_emt_template", y_values),
        _get_series(problem, bus_motor.emt_model, "v_B_Bus_Motor_emt_template", y_values),
        _get_series(problem, bus_motor.emt_model, "v_C_Bus_Motor_emt_template", y_values),
    ))
    motor_currents: np.ndarray = np.column_stack((
        -_get_series(problem, motor_block, _motor_var_name("i_A", config.model_name), y_values),
        -_get_series(problem, motor_block, _motor_var_name("i_B", config.model_name), y_values),
        -_get_series(problem, motor_block, _motor_var_name("i_C", config.model_name), y_values),
    ))
    active_power: np.ndarray = _get_series(problem, motor_block, _motor_var_name("P_motor", config.model_name), y_values)
    reactive_power: np.ndarray = _get_series(problem, motor_block, _motor_var_name("Q_motor", config.model_name), y_values)
    speed: np.ndarray = _get_series(problem, motor_block, _motor_var_name("omega_r", config.model_name), y_values)
    slip: np.ndarray = _get_series(problem, motor_block, _motor_var_name("slip", config.model_name), y_values)
    torque_e: np.ndarray = _get_series(problem, motor_block, _motor_var_name("T_e", config.model_name), y_values)
    torque_m: np.ndarray = _get_series(problem, motor_block, _motor_var_name("T_m", config.model_name), y_values)

    output_directory: Path = _get_output_directory(config)
    _plot_results(
        config=config,
        output_directory=output_directory,
        time_values=time_values,
        bus_voltages=bus_voltages,
        motor_currents=motor_currents,
        active_power=active_power,
        reactive_power=reactive_power,
        speed=speed,
        slip=slip,
        torque_e=torque_e,
        torque_m=torque_m,
        step_time_s=torque_step_updater.step_time_s,
        frequency_hz=grid.fBase,
    )
    diagnostics: InductionMotorDiagnostics = _print_debug_values(
        config=config,
        load=load,
        grid=grid,
        bus_voltages=bus_voltages,
        time_values=time_values,
        motor_currents=motor_currents,
        active_power=active_power,
        reactive_power=reactive_power,
        speed=speed,
        slip=slip,
        torque_e=torque_e,
        torque_m=torque_m,
        equivalent_point=equivalent_point,
        motor_parameters=motor_parameters,
        step_time_s=torque_step_updater.step_time_s,
    )
    _print_physical_checks(config=config, motor_currents=motor_currents, active_power=active_power, reactive_power=reactive_power, speed=speed)
    return InductionMotorDemoResult(
        config=config,
        plot_path=output_directory / "induction_motor_emt_summary.png",
        converged=True,
        diagnostics=diagnostics,
        failure_reason=None,
    )


def _format_summary_float(value: Optional[float]) -> str:
    """Format one optional summary metric for compact tabular printing."""
    if value is None:
        return "n/a"
    return f"{value:.6f}"


def _build_failure_result(config: InductionMotorDemoConfig, reason: str) -> InductionMotorDemoResult:
    """Build a failed case result without stopping the remaining runs."""
    return InductionMotorDemoResult(
        config=config,
        plot_path=_get_output_directory(config) / "induction_motor_emt_summary.png",
        converged=False,
        diagnostics=None,
        failure_reason=reason,
    )


def _print_final_summary(results: list[InductionMotorDemoResult]) -> None:
    """Print the compact multi-case induction-motor EMT summary table."""
    print("\n=== Induction Motor EMT Summary ===")
    header_columns: list[str] = [
        "level",
        "label",
        "plot path",
        "converged / failed",
        "P_cycle_initial",
        "P_cycle_pre_event",
        "Q_cycle_initial",
        "Q_cycle_pre_event",
        "Te_cycle_pre_event",
        "Tm_cycle_pre_event",
        "omega_cycle_pre_event",
        "slip_cycle_pre_event",
    ]
    print(" | ".join(header_columns))
    print("-" * 240)

    result: InductionMotorDemoResult
    for result in results:
        diagnostics: Optional[InductionMotorDiagnostics] = result.diagnostics
        status_text: str = "converged" if result.converged else "failed"
        print(" | ".join([
            str(result.config.level),
            result.config.label,
            str(result.plot_path),
            status_text,
            _format_summary_float(None if diagnostics is None else diagnostics.p_cycle_initial),
            _format_summary_float(None if diagnostics is None else diagnostics.p_cycle_pre_event),
            _format_summary_float(None if diagnostics is None else diagnostics.q_cycle_initial),
            _format_summary_float(None if diagnostics is None else diagnostics.q_cycle_pre_event),
            _format_summary_float(None if diagnostics is None else diagnostics.te_cycle_pre_event),
            _format_summary_float(None if diagnostics is None else diagnostics.tm_cycle_pre_event),
            _format_summary_float(None if diagnostics is None else diagnostics.omega_cycle_pre_event),
            _format_summary_float(None if diagnostics is None else diagnostics.slip_cycle_pre_event),
        ]))
        if result.failure_reason is not None:
            print(f"Failure reason (level {result.config.level}): {result.failure_reason}")


def run_induction_motor_emt_demo(config: InductionMotorDemoConfig) -> Path:
    """Run one induction-motor EMT demo case.

    :param config: Per-level demo configuration.
    :return: Output plot path.
    :raises RuntimeError: If EMT initialization or simulation fails.
    """
    return _run_induction_motor_emt_demo_case(config).plot_path


def run_all_induction_motor_emt_demos() -> list[Path]:
    """Run all induction-motor EMT demo levels independently.

    :return: Plot paths for the cases that completed successfully.
    """
    plot_paths: list[Path] = []
    results: list[InductionMotorDemoResult] = []
    config: InductionMotorDemoConfig

    for config in _build_demo_configs():
        print(f"\n=== Running induction motor EMT level {config.level}: {config.label} ===")
        try:
            case_result: InductionMotorDemoResult = _run_induction_motor_emt_demo_case(config)
            plot_paths.append(case_result.plot_path)
            results.append(case_result)
            print(f"Saved induction-motor EMT plot to: {case_result.plot_path}")
        except Exception as exc:
            failure_result: InductionMotorDemoResult = _build_failure_result(config=config, reason=str(exc))
            results.append(failure_result)
            print(f"Level {config.level} failed: {exc}")

    _print_final_summary(results)
    return plot_paths


if __name__ == "__main__":
    run_all_induction_motor_emt_demos()
