from __future__ import annotations

from pathlib import Path

import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_options import JMartiFitOptions
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_bundle import JMartiFitBundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_bundle import build_jmarti_fit_bundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_frequency_samples import build_jmarti_frequency_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_loewner_seed import build_jmarti_mode_loewner_seed
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import build_jmarti_modal_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import estimate_jmarti_mode_delays
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import set_jmarti_block_fit_bundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_vector_fit import build_jmarti_mode_vector_fit
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_workflow import build_jmarti_fit_bundle_from_frequency_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_workflow import build_jmarti_frequency_samples_from_line
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import get_bergeron_line_emt_template
from VeraGridEngine.Templates.Emt.jmarti_line_emt_template import get_jmarti_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicIntegrationMethod, EmtInitializationMethod, EmtLineTypes, EmtSolverTypes, ShuntConnectionType, SolverType, VarPowerFlowRefferenceType


class JMartiLineCaseResult:
    """
    One networked EMT line case used by the Pi/Bergeron/J_Marti comparison demo.
    """

    __slots__ = (
        'model_tpe',
        'time',
        'load_v_a',
        'comparison_i_a',
        'load_i_a',
        'history_runtime_name',
    )

    def __init__(self,
                 model_tpe: EmtLineTypes,
                 time: np.ndarray,
                 load_v_a: np.ndarray,
                 comparison_i_a: np.ndarray,
                 load_i_a: np.ndarray,
                 history_runtime_name: str) -> None:
        """
        Store one line comparison case.

        :param model_tpe: EMT line-model type.
        :param time: Time vector.
        :param load_v_a: Load-bus phase-A voltage trace.
        :param comparison_i_a: Phase-A current trace comparable across all line models.
        :param load_i_a: Load phase-A current trace.
        :param history_runtime_name: Name of the retained runtime companion, if any.
        :return: None.
        """
        self.model_tpe: EmtLineTypes = model_tpe
        self.time: np.ndarray = time
        self.load_v_a: np.ndarray = load_v_a
        self.comparison_i_a: np.ndarray = comparison_i_a
        self.load_i_a: np.ndarray = load_i_a
        self.history_runtime_name: str = history_runtime_name


class JMartiLineComparisonResults:
    """
    Aggregate Pi/Bergeron/J_Marti network comparison results.
    """

    __slots__ = (
        'pi_case',
        'bergeron_case',
        'jmarti_case',
        'event_time_s',
        'voltage_png_path',
        'current_png_path',
        'voltage_delta_png_path',
        'current_delta_png_path',
        'metrics_txt_path',
    )

    def __init__(self,
                 pi_case: JMartiLineCaseResult,
                 bergeron_case: JMartiLineCaseResult,
                 jmarti_case: JMartiLineCaseResult,
                 event_time_s: float,
                 voltage_png_path: Path,
                 current_png_path: Path,
                 voltage_delta_png_path: Path,
                 current_delta_png_path: Path,
                 metrics_txt_path: Path) -> None:
        """
        Store one aggregate comparison result set.

        :param pi_case: Pi-line case result.
        :param bergeron_case: Bergeron-line case result.
        :param jmarti_case: J_Marti-line case result.
        :param event_time_s: Excitation-event time used by all three cases.
        :param voltage_png_path: Exported voltage comparison plot path.
        :param current_png_path: Exported current comparison plot path.
        :param voltage_delta_png_path: Exported voltage-difference plot path.
        :param current_delta_png_path: Exported current-difference plot path.
        :param metrics_txt_path: Exported text report with numerical comparison metrics.
        :return: None.
        """
        self.pi_case: JMartiLineCaseResult = pi_case
        self.bergeron_case: JMartiLineCaseResult = bergeron_case
        self.jmarti_case: JMartiLineCaseResult = jmarti_case
        self.event_time_s: float = float(event_time_s)
        self.voltage_png_path: Path = voltage_png_path
        self.current_png_path: Path = current_png_path
        self.voltage_delta_png_path: Path = voltage_delta_png_path
        self.current_delta_png_path: Path = current_delta_png_path
        self.metrics_txt_path: Path = metrics_txt_path


class JMartiTraceErrorMetrics:
    """
    Scalar error metrics for one trace comparison.
    """

    __slots__ = (
        'label',
        'rmse',
        'max_abs',
    )

    def __init__(self, label: str, rmse: float, max_abs: float) -> None:
        self.label: str = str(label)
        self.rmse: float = float(rmse)
        self.max_abs: float = float(max_abs)


JMARTI_DEMO_VOLTAGE_RMSE_MAX: float = 5.0e-2
JMARTI_DEMO_CURRENT_RMSE_MAX: float = 2.0e-3


def build_trace_error_metrics(label: str,
                              reference_trace: np.ndarray,
                              candidate_trace: np.ndarray) -> JMartiTraceErrorMetrics:
    """
    Build one RMSE/max-absolute error report for one trace pair.

    :param label: Metric label.
    :param reference_trace: Reference signal.
    :param candidate_trace: Candidate signal.
    :return: Error metric bundle.
    """
    error_trace: np.ndarray = np.asarray(candidate_trace - reference_trace, dtype=np.float64)
    return JMartiTraceErrorMetrics(
        label=label,
        rmse=float(np.sqrt(np.mean(error_trace * error_trace))),
        max_abs=float(np.max(np.abs(error_trace))),
    )


def build_metrics_report_lines(results: JMartiLineComparisonResults) -> list[str]:
    """
    Build one plain-text comparison report against Bergeron.

    :param results: Aggregate comparison results.
    :return: Report lines.
    """
    post_event_mask: np.ndarray = results.jmarti_case.time >= results.event_time_s
    pi_full_voltage_metrics = build_trace_error_metrics(
        "Pi full-trace load-bus voltage",
        results.bergeron_case.load_v_a,
        results.pi_case.load_v_a,
    )
    pi_full_load_current_metrics = build_trace_error_metrics(
        "Pi full-trace load current",
        results.bergeron_case.load_i_a,
        results.pi_case.load_i_a,
    )
    pi_full_comparison_current_metrics = build_trace_error_metrics(
        "Pi full-trace comparable current",
        results.bergeron_case.comparison_i_a,
        results.pi_case.comparison_i_a,
    )
    full_voltage_metrics = build_trace_error_metrics(
        "Full-trace load-bus voltage",
        results.bergeron_case.load_v_a,
        results.jmarti_case.load_v_a,
    )
    full_load_current_metrics = build_trace_error_metrics(
        "Full-trace load current",
        results.bergeron_case.load_i_a,
        results.jmarti_case.load_i_a,
    )
    full_comparison_current_metrics = build_trace_error_metrics(
        "Full-trace comparable current",
        results.bergeron_case.comparison_i_a,
        results.jmarti_case.comparison_i_a,
    )
    post_voltage_metrics = build_trace_error_metrics(
        "Post-event load-bus voltage",
        results.bergeron_case.load_v_a[post_event_mask],
        results.jmarti_case.load_v_a[post_event_mask],
    )
    post_load_current_metrics = build_trace_error_metrics(
        "Post-event load current",
        results.bergeron_case.load_i_a[post_event_mask],
        results.jmarti_case.load_i_a[post_event_mask],
    )
    post_comparison_current_metrics = build_trace_error_metrics(
        "Post-event comparable current",
        results.bergeron_case.comparison_i_a[post_event_mask],
        results.jmarti_case.comparison_i_a[post_event_mask],
    )
    acceptance_passed: bool = is_jmarti_demo_internal_acceptance_passed(results)
    report_lines: list[str] = list()
    metrics: JMartiTraceErrorMetrics

    report_lines.append("JMARTI vs Bergeron comparison report")
    report_lines.append(f"Event time [s]: {results.event_time_s:.6e}")
    report_lines.append(f"Samples: {results.jmarti_case.time.size}")
    report_lines.append(f"Voltage PNG: {results.voltage_png_path}")
    report_lines.append(f"Current PNG: {results.current_png_path}")
    report_lines.append(f"Voltage delta PNG: {results.voltage_delta_png_path}")
    report_lines.append(f"Current delta PNG: {results.current_delta_png_path}")
    report_lines.append("")
    report_lines.append(f"Internal acceptance passed: {acceptance_passed}")
    report_lines.append(
        f"Acceptance limits: voltage RMSE <= {JMARTI_DEMO_VOLTAGE_RMSE_MAX:.6e}, current RMSE <= {JMARTI_DEMO_CURRENT_RMSE_MAX:.6e}, and JMARTI must beat Pi on full-trace RMSE."
    )
    report_lines.append("")

    for metrics in (
        pi_full_voltage_metrics,
        pi_full_load_current_metrics,
        pi_full_comparison_current_metrics,
        full_voltage_metrics,
        full_load_current_metrics,
        full_comparison_current_metrics,
        post_voltage_metrics,
        post_load_current_metrics,
        post_comparison_current_metrics,
    ):
        report_lines.append(
            f"{metrics.label}: RMSE={metrics.rmse:.6e}, MAX={metrics.max_abs:.6e}"
        )

    report_lines.append("")
    report_lines.append(
        f"Voltage RMSE improvement vs Pi: {pi_full_voltage_metrics.rmse / max(full_voltage_metrics.rmse, 1.0e-16):.6f}x"
    )
    report_lines.append(
        f"Current RMSE improvement vs Pi: {pi_full_load_current_metrics.rmse / max(full_load_current_metrics.rmse, 1.0e-16):.6f}x"
    )

    return report_lines


def is_jmarti_demo_internal_acceptance_passed(results: JMartiLineComparisonResults) -> bool:
    """
    Return whether the internal JMARTI demo acceptance criteria pass.

    :param results: Aggregate comparison results.
    :return: Boolean acceptance state.
    """
    pi_voltage_metrics = build_trace_error_metrics(
        "Pi full-trace load-bus voltage",
        results.bergeron_case.load_v_a,
        results.pi_case.load_v_a,
    )
    pi_current_metrics = build_trace_error_metrics(
        "Pi full-trace load current",
        results.bergeron_case.load_i_a,
        results.pi_case.load_i_a,
    )
    jmarti_voltage_metrics = build_trace_error_metrics(
        "JMARTI full-trace load-bus voltage",
        results.bergeron_case.load_v_a,
        results.jmarti_case.load_v_a,
    )
    jmarti_current_metrics = build_trace_error_metrics(
        "JMARTI full-trace load current",
        results.bergeron_case.load_i_a,
        results.jmarti_case.load_i_a,
    )

    return (
        jmarti_voltage_metrics.rmse <= JMARTI_DEMO_VOLTAGE_RMSE_MAX
        and jmarti_current_metrics.rmse <= JMARTI_DEMO_CURRENT_RMSE_MAX
        and jmarti_voltage_metrics.rmse <= pi_voltage_metrics.rmse
        and jmarti_current_metrics.rmse <= pi_current_metrics.rmse
    )


def _find_block_runtime_parameter_by_prefix(block, name_prefix: str):
    """
    Return the first runtime parameter whose name starts with one prefix.

    :param block: Symbolic block.
    :param name_prefix: Required name prefix.
    :return: Matching runtime parameter variable.
    :raises ValueError: If no variable matches.
    """
    runtime_parameter = None
    for runtime_parameter in block.event_dict.keys():
        if runtime_parameter.name.startswith(name_prefix):
            return runtime_parameter
        else:
            pass

    raise ValueError(f"Unable to find one runtime parameter starting with '{name_prefix}'")


def _evaluate_scalar_rational_response(frequency_hz: np.ndarray,
                                       poles_s: np.ndarray,
                                       residues: np.ndarray,
                                       constant_term: complex = 0.0 + 0.0j) -> np.ndarray:
    """
    Evaluate one scalar rational response on the imaginary axis.

    :param frequency_hz: Frequency grid in Hz.
    :param poles_s: Continuous-time poles.
    :param residues: Residues paired with ``poles_s``.
    :param constant_term: Optional constant term.
    :return: Complex response samples.
    """
    angular_frequency: np.ndarray = 2.0 * np.pi * frequency_hz
    response: np.ndarray = np.zeros(frequency_hz.size, dtype=np.complex128)
    sample_index: int = 0
    pole_index: int
    s_value: complex

    while sample_index < frequency_hz.size:
        s_value = 1j * angular_frequency[sample_index]
        response[sample_index] = complex(constant_term)
        pole_index = 0

        while pole_index < poles_s.size:
            response[sample_index] = response[sample_index] + residues[pole_index] / (s_value - poles_s[pole_index])
            pole_index += 1

        sample_index += 1

    return response


def build_demo_jmarti_fit_bundle() -> JMartiFitBundle:
    """
    Build one synthetic three-phase JMARTI fit bundle for demos and tests.

    :return: Offline JMARTI fit bundle.
    """
    frequency_hz: np.ndarray = np.asarray([10.0, 40.0, 80.0, 160.0, 320.0, 640.0], dtype=np.float64)
    z_per_length: np.ndarray = np.zeros((frequency_hz.size, 3, 3), dtype=np.complex128)
    y_per_length: np.ndarray = np.zeros((frequency_hz.size, 3, 3), dtype=np.complex128)
    sample_index: int = 0
    mode_index: int
    options: JMartiFitOptions = JMartiFitOptions(forced_model_order=1, vf_max_iterations=6)
    yc_mode_responses = list([
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-50.0 + 0.0j], dtype=np.complex128), np.asarray([0.30 + 0.0j], dtype=np.complex128), constant_term=0.10 + 0.0j),
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-120.0 + 0.0j], dtype=np.complex128), np.asarray([0.15 + 0.0j], dtype=np.complex128), constant_term=0.08 + 0.0j),
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-200.0 + 0.0j], dtype=np.complex128), np.asarray([0.10 + 0.0j], dtype=np.complex128), constant_term=0.07 + 0.0j),
    ])
    hres_mode_responses = list([
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-80.0 + 0.0j], dtype=np.complex128), np.asarray([0.020 + 0.0j], dtype=np.complex128), constant_term=0.85 + 0.0j),
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-160.0 + 0.0j], dtype=np.complex128), np.asarray([0.010 + 0.0j], dtype=np.complex128), constant_term=0.75 + 0.0j),
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-240.0 + 0.0j], dtype=np.complex128), np.asarray([0.008 + 0.0j], dtype=np.complex128), constant_term=0.65 + 0.0j),
    ])
    samples = None
    modal_samples = None
    mode_delays = None
    yc_fits: list = list()
    hres_fits: list = list()

    while sample_index < frequency_hz.size:
        z_per_length[sample_index, :, :] = np.diag(np.asarray([
            1.0 + 0.2j * float(sample_index + 1),
            2.0 + 0.3j * float(sample_index + 1),
            3.0 + 0.4j * float(sample_index + 1),
        ], dtype=np.complex128))
        y_per_length[sample_index, :, :] = np.diag(np.asarray([
            yc_mode_responses[0][sample_index] * yc_mode_responses[0][sample_index],
            yc_mode_responses[1][sample_index] * yc_mode_responses[1][sample_index],
            yc_mode_responses[2][sample_index] * yc_mode_responses[2][sample_index],
        ], dtype=np.complex128))
        sample_index += 1

    samples = build_jmarti_frequency_samples(
        frequency_hz=frequency_hz,
        z_per_length=z_per_length,
        y_per_length=y_per_length,
        line_length_m=1000.0,
        phase_labels=("A", "B", "C"),
    )
    modal_samples = build_jmarti_modal_samples(samples=samples, options=options)
    mode_delays = estimate_jmarti_mode_delays(modal_samples, options=options)

    mode_index = 0
    while mode_index < 3:
        yc_fits.append(
            build_jmarti_mode_vector_fit(
                frequency_hz=frequency_hz,
                response_values=modal_samples.get_yc_modal()[:, mode_index],
                loewner_seed=build_jmarti_mode_loewner_seed(
                    frequency_hz,
                    modal_samples.get_yc_modal()[:, mode_index],
                    "Yc",
                    mode_index,
                    options,
                ),
                options=options,
            )
        )
        hres_fits.append(
            build_jmarti_mode_vector_fit(
                frequency_hz=frequency_hz,
                response_values=hres_mode_responses[mode_index],
                loewner_seed=build_jmarti_mode_loewner_seed(
                    frequency_hz,
                    hres_mode_responses[mode_index],
                    "Hres",
                    mode_index,
                    options,
                ),
                options=options,
            )
        )
        mode_index += 1

    return build_jmarti_fit_bundle(
        modal_samples=modal_samples,
        mode_delays=mode_delays,
        yc_fits=yc_fits,
        hres_fits=hres_fits,
    )


def build_demo_line_case_grid(model_tpe: EmtLineTypes) -> tuple[MultiCircuit, Line, Bus, Load]:
    """
    Build one minimal two-bus EMT network for line-model comparison.

    :param model_tpe: Requested EMT line-model type.
    :return: Grid, line, load bus, and load.
    """
    grid: MultiCircuit = gce.MultiCircuit(Sbase=2.0, fbase=50.0)
    bus0: Bus = gce.Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus1: Bus = gce.Bus(name="Bus1", Vnom=10.0)
    generator: Generator = gce.Generator(name="Gen", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=0.2)
    line_template = gce.create_known_abc_overhead_template(
        name="JMartiDemoLine",
        z_nabc=np.array([
            [0.01 + 1j * 0.03, 0.0 + 0.0j, 0.0 + 0.0j],
            [0.0 + 0.0j, 0.01 + 1j * 0.03, 0.0 + 0.0j],
            [0.0 + 0.0j, 0.0 + 0.0j, 0.01 + 1j * 0.03],
        ], dtype=complex),
        ysh_nabc=np.array([
            [1j * 1.0e-6, 0.0 + 0.0j, 0.0 + 0.0j],
            [0.0 + 0.0j, 1j * 1.0e-6, 0.0 + 0.0j],
            [0.0 + 0.0j, 0.0 + 0.0j, 1j * 1.0e-6],
        ], dtype=complex),
        phases=np.array([1, 2, 3]),
        Vnom=10.0,
        frequency=50.0,
    )
    line: Line = gce.Line(name="Line", bus_from=bus0, bus_to=bus1, length=50.0)
    load: Load = gce.Load(name="Load", P1=0.05, P2=0.05, P3=0.05, Q1=0.0, Q2=0.0, Q3=0.0)
    load.conn = ShuntConnectionType.FloatingStar
    bus: Bus
    generator_model = None
    line_model = None
    load_model = None
    event_group: EmtEventsGroup = EmtEventsGroup(name="jmarti_line_demo_events")
    generator_voltage_scale_var = None

    # Stage 1: static network topology.
    grid.add_bus(bus0)
    grid.add_bus(bus1)
    grid.add_generator(bus=bus0, api_obj=generator)
    grid.add_overhead_line(line_template)
    grid.add_emt_events_group(event_group)
    line.apply_template(line_template, grid.Sbase, grid.fBase, gce.Logger())

    grid.add_line(obj=line)
    grid.add_load(bus=bus1, api_obj=load)

    # Stage 2: EMT models.
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    generator_model = get_generator_thevenin_rl_emt_template(vf=grid.var_factory, name="Gen").block

    if model_tpe == EmtLineTypes.PI:
        line_model = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name="Line").block
    else:
        if model_tpe == EmtLineTypes.Bergeron:
            line_model = get_bergeron_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name="Line").block
        else:
            if model_tpe == EmtLineTypes.J_Marti:
                line_model = get_jmarti_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name="Line").block
            else:
                raise ValueError(f"Unsupported EMT line model type '{model_tpe}'")

    load_model = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True, name="Load_R_demo").block

    if model_tpe == EmtLineTypes.J_Marti:
        set_jmarti_block_fit_bundle(
            line_model,
            build_jmarti_fit_bundle_from_frequency_samples(
                samples=build_jmarti_frequency_samples_from_line(
                    line=line,
                    phase_n=False,
                    phase_a=True,
                    phase_b=True,
                    phase_c=True,
                    low_hz=10.0,
                    high_hz=5000.0,
                    sample_count=48,
                    nominal_frequency_hz=50.0,
                    sbase_mva=float(grid.Sbase),
                ),
                options=JMartiFitOptions(forced_model_order=1, vf_max_iterations=6),
            ),
        )
    else:
        pass

    set_emt_model(device=generator, model=generator_model, var_factory=grid.var_factory)
    set_emt_model(device=line, model=line_model, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_model, var_factory=grid.var_factory)

    generator_voltage_scale_var = _find_block_runtime_parameter_by_prefix(generator_model, "E_scale_")
    grid.add_emt_event(
        EmtEvent(
            parameter=generator_voltage_scale_var,
            time=get_demo_event_time_s(),
            value=1.05,
            group=event_group,
            force_step_alignment=True,
            transition_type=DynamicEventTransitionType.Step,
            name="jmarti_line_demo_source_step",
        )
    )
    return grid, line, bus1, load


def get_demo_pf_options() -> PowerFlowOptions:
    """
    Return one lightweight three-phase power-flow option set for the line demo.

    :return: Power-flow options.
    """
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1.0e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=False,
        generate_report=False,
    )


def get_demo_emt_options() -> EmtOptions:
    """
    Return one short EMT option set for the line-model comparison demo.

    :return: EMT options.
    """
    return EmtOptions(
        time_step=1.0e-5,
        simulation_time=2.0e-3,
        tolerance=1.0e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=0,
    )


def get_demo_event_time_s() -> float:
    """
    Return the common excitation-event time used by the line comparison demo.

    :return: Event time in seconds.
    """
    return 8.0e-4


def run_demo_line_case(model_tpe: EmtLineTypes) -> JMartiLineCaseResult:
    """
    Run one minimal networked EMT line case.

    :param model_tpe: Requested EMT line-model type.
    :return: One line-case result.
    """
    grid: MultiCircuit
    line: Line
    load_bus: Bus
    load: Load
    power_flow: PowerFlowDriver3Ph
    problem: EmtProblemDae
    solver: JitSymbolicSolver
    time_vector: np.ndarray
    state_history: np.ndarray
    history_runtime_name: str = ""
    load_v_a_index: int
    load_i_a_index: int
    comparison_i_a_trace: np.ndarray
    line_if_a_var = None

    grid, line, load_bus, load = build_demo_line_case_grid(model_tpe=model_tpe)
    power_flow = PowerFlowDriver3Ph(grid, get_demo_pf_options())
    power_flow.run()
    problem = EmtProblemDae(grid=grid, options=get_demo_emt_options(), pf_results=None, pf_results_3ph=power_flow.results)

    if len(problem.history_models) > 0:
        history_runtime_name = type(problem.history_models[0]).__name__
    else:
        history_runtime_name = ""

    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
        verbose=False,
    )
    time_vector, state_history, _diff_history, _converged, _diag = solver.simulate(boundary_updater=problem)
    load_v_a_index = problem.get_var_idx(load_bus.emt_model.external_mapping[VarPowerFlowRefferenceType.v_A])
    load_i_a_index = problem.get_var_idx(load.emt_model.external_mapping[VarPowerFlowRefferenceType.i_A])

    if VarPowerFlowRefferenceType.if_A in line.emt_model.external_mapping:
        line_if_a_var = line.emt_model.external_mapping[VarPowerFlowRefferenceType.if_A]
    else:
        line_if_a_var = None

    if line_if_a_var is not None:
        comparison_i_a_trace = np.asarray(state_history[:, problem.get_var_idx(line_if_a_var)], dtype=np.float64)
    else:
        # Bergeron and JMARTI inject currents through retained history sources rather
        # than through explicit external current outputs. In this minimal source-line-
        # load network, the load current is therefore the common phase-domain current
        # trace available across all three line formulations.
        comparison_i_a_trace = np.asarray(state_history[:, load_i_a_index], dtype=np.float64)

    return JMartiLineCaseResult(
        model_tpe=model_tpe,
        time=np.asarray(time_vector, dtype=np.float64),
        load_v_a=np.asarray(state_history[:, load_v_a_index], dtype=np.float64),
        comparison_i_a=comparison_i_a_trace,
        load_i_a=np.asarray(state_history[:, load_i_a_index], dtype=np.float64),
        history_runtime_name=history_runtime_name,
    )
