"""
Compare MDHEM artifact training seed options on IEEE 14.

This script builds several artifacts for the same MATPOWER case and compares
their queried operating points against an external Newton-Raphson reference on
the same randomized scenario batch.

The comparison is intentionally split into two independent roles:

* artifact training and querying,
* external Newton-Raphson validation.

The artifact query path never calls Newton-Raphson. Newton-Raphson is used only
as an optional seed for artifact training when explicitly requested, and as the
external reference used to measure the artifact error.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

from mdhelm_pv_case14_fire_test import DeviceBusMapping
from mdhelm_pv_case14_fire_test import FireTestMetrics
from mdhelm_pv_case14_fire_test import FireTestScenario
from mdhelm_pv_case14_fire_test import build_device_bus_mapping
from mdhelm_pv_case14_fire_test import create_fire_test_scenarios
from mdhelm_pv_case14_fire_test import create_nr_options
from mdhelm_pv_case14_fire_test import evaluate_scenario
from mdhelm_pv_case14_query_artifact import MDHEMPVQueryArtifact
from mdhelm_pv_case14_query_artifact import VeraGridQueryCaseData
from mdhelm_pv_case14_query_artifact import build_artifact_from_case
from mdhelm_pv_case14_query_artifact import create_mdhelm_inputs
from mdhelm_pv_case14_query_artifact import import_veragrid_engine_modules
from mdhelm_pv_case14_query_artifact import load_multicircuit_from_file
from mdhelm_pv_case14_query_artifact import load_query_artifact
from mdhelm_pv_case14_query_artifact import save_query_artifact

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


class ArtifactSeedMode(Enum):
    """
    Enumerate the supported artifact training seed modes.

    :cvar INTERNAL_HELM:
        Build the artifact with the internal HELM germ solve.
    :cvar EXPLICIT_HELM:
        Build the artifact from an explicitly supplied HELM solution.
    :cvar EXPLICIT_NR:
        Build the artifact from an explicitly supplied Newton-Raphson solution.
    """

    INTERNAL_HELM = 1
    EXPLICIT_HELM = 2
    EXPLICIT_NR = 3


class ArtifactSeedInput:
    """
    Store the seed information passed to the artifact builder.

    :param mode:
        Selected seed mode.
    :param power_flow_results:
        Optional VeraGrid power-flow result used as the explicit germ.
    :param seed_converged:
        Convergence flag for the explicit seed solve. For the internal mode the
        value is ``True`` because the builder will solve its own germ.
    :param seed_error:
        Error reported by the explicit seed solve. For the internal mode the
        value is ``None`` because there is no external seed solve.
    """

    __slots__ = (
        "mode",
        "power_flow_results",
        "seed_converged",
        "seed_error",
    )

    def __init__(
        self,
        mode: ArtifactSeedMode,
        power_flow_results: Optional["PowerFlowResults"],
        seed_converged: bool,
        seed_error: Optional[float],
    ) -> None:
        self.mode: ArtifactSeedMode = mode
        self.power_flow_results: Optional["PowerFlowResults"] = power_flow_results
        self.seed_converged: bool = seed_converged
        self.seed_error: Optional[float] = seed_error


class ArtifactSeedModeReport:
    """
    Store the evaluation report for one seed mode.

    :param mode:
        Selected seed mode.
    :param mode_name:
        Human-readable mode name.
    :param artifact_path:
        Saved artifact path.
    :param external_nr_seed_used:
        Whether Newton-Raphson was used as the artifact germ seed.
    :param seed_converged:
        Convergence flag for the explicit seed solve.
    :param seed_error:
        Error reported by the explicit seed solve, or ``None``.
    :param germ_error:
        Residual/error returned by artifact germ construction, or ``None`` when
        artifact construction failed.
    :param failure_message:
        Failure text when the artifact build or evaluation failed.
    :param metrics_list:
        Per-scenario comparison metrics.
    :param passed_count:
        Number of passed scenarios.
    :param scenario_count:
        Number of evaluated scenarios.
    :param worst_voltage_diff:
        Worst voltage mismatch in per unit.
    :param worst_flow_diff_mva:
        Worst branch-flow mismatch in MVA.
    :param worst_loading_diff:
        Worst loading mismatch.
    :param worst_write_error:
        Worst injection write error in per unit.
    """

    __slots__ = (
        "mode",
        "mode_name",
        "artifact_path",
        "external_nr_seed_used",
        "seed_converged",
        "seed_error",
        "germ_error",
        "failure_message",
        "metrics_list",
        "passed_count",
        "scenario_count",
        "worst_voltage_diff",
        "worst_flow_diff_mva",
        "worst_loading_diff",
        "worst_write_error",
    )

    def __init__(
        self,
        mode: ArtifactSeedMode,
        mode_name: str,
        artifact_path: Path,
        external_nr_seed_used: bool,
        seed_converged: bool,
        seed_error: Optional[float],
        germ_error: Optional[float],
        failure_message: Optional[str],
        metrics_list: list[FireTestMetrics],
        passed_count: int,
        scenario_count: int,
        worst_voltage_diff: float,
        worst_flow_diff_mva: float,
        worst_loading_diff: float,
        worst_write_error: float,
    ) -> None:
        self.mode: ArtifactSeedMode = mode
        self.mode_name: str = mode_name
        self.artifact_path: Path = artifact_path
        self.external_nr_seed_used: bool = external_nr_seed_used
        self.seed_converged: bool = seed_converged
        self.seed_error: Optional[float] = seed_error
        self.germ_error: Optional[float] = germ_error
        self.failure_message: Optional[str] = failure_message
        self.metrics_list: list[FireTestMetrics] = metrics_list
        self.passed_count: int = passed_count
        self.scenario_count: int = scenario_count
        self.worst_voltage_diff: float = worst_voltage_diff
        self.worst_flow_diff_mva: float = worst_flow_diff_mva
        self.worst_loading_diff: float = worst_loading_diff
        self.worst_write_error: float = worst_write_error


def create_helm_options(vg: object) -> object:
    """
    Create VeraGrid HELM power-flow options for explicit seed generation.

    :param vg:
        Imported VeraGridEngine module.
    :return:
        VeraGrid ``PowerFlowOptions`` configured for HELM.
    """
    try:
        options: object = vg.PowerFlowOptions(
            solver_type=vg.SolverType.HELM,
            retry_with_other_methods=False,
            control_q=True,
            control_taps_phase=False,
            control_taps_modules=False,
            apply_temperature_correction=False,
            use_stored_guess=False,
            tolerance=1e-10,
        )
    except TypeError:
        options = vg.PowerFlowOptions(vg.SolverType.HELM, verbose=False)

    return options


def describe_seed_mode(seed_mode: ArtifactSeedMode) -> tuple[str, str, bool]:
    """
    Describe one seed mode for reporting and file naming.

    :param seed_mode:
        Seed mode being evaluated.
    :return:
        Tuple ``(human_name, file_slug, uses_external_nr_seed)``.
    """
    mode_name: str
    file_slug: str
    external_nr_seed_used: bool

    if seed_mode is ArtifactSeedMode.INTERNAL_HELM:
        mode_name = "internal HELM germ"
        file_slug = "internal_helm"
        external_nr_seed_used = False
    else:
        if seed_mode is ArtifactSeedMode.EXPLICIT_HELM:
            mode_name = "explicit HELM seed"
            file_slug = "explicit_helm"
            external_nr_seed_used = False
        else:
            if seed_mode is ArtifactSeedMode.EXPLICIT_NR:
                mode_name = "explicit NR seed"
                file_slug = "explicit_nr"
                external_nr_seed_used = True
            else:
                raise ValueError(f"Unsupported seed mode {seed_mode}")

    return mode_name, file_slug, external_nr_seed_used


def build_seed_input(base_grid: "MultiCircuit", seed_mode: ArtifactSeedMode) -> ArtifactSeedInput:
    """
    Build the optional explicit seed for one artifact training mode.

    :param base_grid:
        Base VeraGrid grid.
    :param seed_mode:
        Selected artifact training seed mode.
    :return:
        Seed input container for the artifact builder.
    """
    power_flow_results: Optional["PowerFlowResults"] = None
    seed_converged: bool = True
    seed_error: Optional[float] = None

    # The internal mode leaves the builder fully responsible for selecting and
    # solving its HELM germ. The other modes create an explicit operating point
    # first and pass it into the builder as a ``PowerFlowResults`` object.
    if seed_mode is ArtifactSeedMode.INTERNAL_HELM:
        pass
    else:
        vg: object
        cf: object
        vg, cf = import_veragrid_engine_modules()
        _ = cf
        options: object

        if seed_mode is ArtifactSeedMode.EXPLICIT_HELM:
            options = create_helm_options(vg=vg)
        else:
            if seed_mode is ArtifactSeedMode.EXPLICIT_NR:
                options = create_nr_options(vg=vg)
            else:
                raise ValueError(f"Unsupported seed mode {seed_mode}")

        power_flow_results = vg.power_flow(grid=base_grid, options=options)
        seed_converged = bool(power_flow_results.converged)
        seed_error = float(power_flow_results.error)

    return ArtifactSeedInput(
        mode=seed_mode,
        power_flow_results=power_flow_results,
        seed_converged=seed_converged,
        seed_error=seed_error,
    )


def summarize_seed_mode_report(
    mode: ArtifactSeedMode,
    mode_name: str,
    artifact_path: Path,
    external_nr_seed_used: bool,
    seed_input: ArtifactSeedInput,
    germ_error: Optional[float],
    failure_message: Optional[str],
    metrics_list: list[FireTestMetrics],
) -> ArtifactSeedModeReport:
    """
    Summarize one seed-mode evaluation into fixed report fields.

    :param mode:
        Selected seed mode.
    :param mode_name:
        Human-readable seed mode name.
    :param artifact_path:
        Saved artifact path.
    :param external_nr_seed_used:
        Whether Newton-Raphson was used as the artifact germ seed.
    :param seed_input:
        Explicit seed information passed to the builder.
    :param germ_error:
        Germ error returned by the builder, or ``None`` when unavailable.
    :param failure_message:
        Failure message for the mode, or ``None``.
    :param metrics_list:
        Per-scenario metrics for the mode.
    :return:
        Frozen report structure for the mode.
    """
    passed_count: int = 0
    scenario_count: int = len(metrics_list)
    worst_voltage_diff: float = 0.0
    worst_flow_diff_mva: float = 0.0
    worst_loading_diff: float = 0.0
    worst_write_error: float = 0.0
    metrics: FireTestMetrics

    # The summary stores the maxima that matter for comparing seed choices
    # without hiding the full scenario-level data kept in ``metrics_list``.
    for metrics in metrics_list:
        if metrics.passed:
            passed_count = passed_count + 1
        else:
            passed_count = passed_count + 0
        worst_voltage_diff = max(worst_voltage_diff, metrics.max_voltage_diff)
        worst_flow_diff_mva = max(worst_flow_diff_mva, metrics.max_flow_diff_mva)
        worst_loading_diff = max(worst_loading_diff, metrics.max_loading_diff)
        worst_write_error = max(worst_write_error, metrics.injection_write_error)

    return ArtifactSeedModeReport(
        mode=mode,
        mode_name=mode_name,
        artifact_path=artifact_path,
        external_nr_seed_used=external_nr_seed_used,
        seed_converged=seed_input.seed_converged,
        seed_error=seed_input.seed_error,
        germ_error=germ_error,
        failure_message=failure_message,
        metrics_list=metrics_list,
        passed_count=passed_count,
        scenario_count=scenario_count,
        worst_voltage_diff=worst_voltage_diff,
        worst_flow_diff_mva=worst_flow_diff_mva,
        worst_loading_diff=worst_loading_diff,
        worst_write_error=worst_write_error,
    )


def evaluate_seed_mode(
    base_grid: "MultiCircuit",
    case_data: VeraGridQueryCaseData,
    mapping: DeviceBusMapping,
    scenarios: list[FireTestScenario],
    output_dir: Path,
    seed_mode: ArtifactSeedMode,
    max_order: int,
    artifact_tolerance: float,
    voltage_threshold: float,
    branch_flow_threshold_mva: float,
    loading_threshold: float,
    injection_write_threshold: float,
) -> ArtifactSeedModeReport:
    """
    Build and evaluate one artifact seed mode.

    :param base_grid:
        Base VeraGrid grid.
    :param case_data:
        Base case data.
    :param mapping:
        Device-to-bus mapping for the scenario replay.
    :param scenarios:
        Scenario batch used for every seed mode.
    :param output_dir:
        Directory where the artifact file will be stored.
    :param seed_mode:
        Selected artifact training seed mode.
    :param max_order:
        Artifact maximum total order.
    :param artifact_tolerance:
        Internal artifact tolerance for query evaluation.
    :param voltage_threshold:
        Voltage pass threshold.
    :param branch_flow_threshold_mva:
        Branch-flow pass threshold.
    :param loading_threshold:
        Loading pass threshold.
    :param injection_write_threshold:
        Injection write pass threshold.
    :return:
        Report structure for the evaluated seed mode.
    """
    mode_name: str
    file_slug: str
    external_nr_seed_used: bool
    mode_name, file_slug, external_nr_seed_used = describe_seed_mode(seed_mode=seed_mode)
    seed_input: ArtifactSeedInput = build_seed_input(base_grid=base_grid, seed_mode=seed_mode)
    artifact_path: Path = output_dir / f"mdhelm_pv_case14_{file_slug}_artifact.npz"
    germ_error: Optional[float] = None
    failure_message: Optional[str] = None
    metrics_list: list[FireTestMetrics] = list()

    try:
        built_case_data: VeraGridQueryCaseData
        artifact: MDHEMPVQueryArtifact
        built_case_data, artifact, built_germ_error = build_artifact_from_case(
            grid=base_grid,
            max_order=max_order,
            germ_seed_results=seed_input.power_flow_results,
        )
        germ_error = float(built_germ_error)
        save_query_artifact(path=artifact_path, artifact=artifact)
        restored_artifact: MDHEMPVQueryArtifact = load_query_artifact(path=artifact_path)
        scenario: FireTestScenario

        # The reloaded artifact is used so the report validates the serialized
        # artifact path, not only the in-memory object returned by training.
        for scenario in scenarios:
            metrics: FireTestMetrics = evaluate_scenario(
                base_grid=base_grid,
                case_data=case_data,
                mapping=mapping,
                artifact=restored_artifact,
                scenario=scenario,
                artifact_tolerance=artifact_tolerance,
                voltage_threshold=voltage_threshold,
                branch_flow_threshold_mva=branch_flow_threshold_mva,
                loading_threshold=loading_threshold,
                injection_write_threshold=injection_write_threshold,
            )
            metrics_list.append(metrics)

        # The compiled inputs should be invariant across the seed mode because
        # they come from the same static network model. The check protects the
        # comparison from accidental training on a different circuit.
        if built_case_data.ybus.shape == case_data.ybus.shape:
            pass
        else:
            raise RuntimeError("Built case data does not match the base case bus count")
    except Exception as exc:
        failure_message = str(exc)

    return summarize_seed_mode_report(
        mode=seed_mode,
        mode_name=mode_name,
        artifact_path=artifact_path,
        external_nr_seed_used=external_nr_seed_used,
        seed_input=seed_input,
        germ_error=germ_error,
        failure_message=failure_message,
        metrics_list=metrics_list,
    )


def append_report_settings(
    lines: list[str],
    case_path: Path,
    report_path: Path,
    max_order: int,
    scenario_count: int,
    random_seed: int,
    artifact_tolerance: float,
    voltage_threshold: float,
    branch_flow_threshold_mva: float,
    loading_threshold: float,
    injection_write_threshold: float,
) -> None:
    """
    Append the global report settings to the markdown buffer.

    :param lines:
        Mutable markdown line buffer.
    :param case_path:
        MATPOWER case path.
    :param report_path:
        Output report path.
    :param max_order:
        Artifact maximum order.
    :param scenario_count:
        Number of evaluated scenarios.
    :param random_seed:
        Random seed used to create scenarios.
    :param artifact_tolerance:
        Artifact mismatch threshold.
    :param voltage_threshold:
        Voltage pass threshold.
    :param branch_flow_threshold_mva:
        Branch-flow pass threshold.
    :param loading_threshold:
        Loading pass threshold.
    :param injection_write_threshold:
        Injection write threshold.
    :return:
        None.
    """
    timestamp_text: str = datetime.now().isoformat(timespec="seconds")
    lines.append("# MDHEM IEEE14 Seed-Mode Report")
    lines.append("")
    lines.append(f"Generated: `{timestamp_text}`")
    lines.append(f"Case file: `{case_path}`")
    lines.append(f"Report file: `{report_path}`")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("This report compares three artifact training modes on the same IEEE 14 scenarios.")
    lines.append("Newton-Raphson is never used to answer artifact queries.")
    lines.append("Newton-Raphson appears only in two places:")
    lines.append("")
    lines.append("1. as an optional explicit germ seed when that mode is selected,")
    lines.append("2. as the external reference used to score the artifact outputs.")
    lines.append("")
    lines.append("## Settings")
    lines.append("")
    lines.append(f"- `max_order = {max_order}`")
    lines.append(f"- `scenario_count = {scenario_count}`")
    lines.append(f"- `random_seed = {random_seed}`")
    lines.append(f"- `artifact_tolerance = {artifact_tolerance:.4e}`")
    lines.append(f"- `voltage_threshold = {voltage_threshold:.4e}`")
    lines.append(f"- `branch_flow_threshold_mva = {branch_flow_threshold_mva:.4f}`")
    lines.append(f"- `loading_threshold = {loading_threshold:.4e}`")
    lines.append(f"- `injection_write_threshold = {injection_write_threshold:.4e}`")
    lines.append("")


def append_summary_table(lines: list[str], mode_reports: list[ArtifactSeedModeReport]) -> None:
    """
    Append the seed-mode summary table to the markdown buffer.

    :param lines:
        Mutable markdown line buffer.
    :param mode_reports:
        Report entries for all seed modes.
    :return:
        None.
    """
    lines.append("## Summary")
    lines.append("")
    lines.append("| mode | explicit seed | external NR seed | seed converged | seed error | germ error | passed | worst dV | worst dSf | worst dloading | worst write err | status |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    report: ArtifactSeedModeReport

    for report in mode_reports:
        explicit_seed_text: str = "yes"
        seed_error_text: str = "n/a"
        germ_error_text: str = "n/a"
        status_text: str = "ok"

        if report.mode is ArtifactSeedMode.INTERNAL_HELM:
            explicit_seed_text = "no"
        else:
            explicit_seed_text = "yes"

        if report.seed_error is None:
            seed_error_text = "n/a"
        else:
            seed_error_text = f"{report.seed_error:.4e}"

        if report.germ_error is None:
            germ_error_text = "n/a"
        else:
            germ_error_text = f"{report.germ_error:.4e}"

        if report.failure_message is None:
            status_text = "ok"
        else:
            status_text = f"failed: {report.failure_message}"

        lines.append(
            f"| {report.mode_name} | "
            f"{explicit_seed_text} | "
            f"{'yes' if report.external_nr_seed_used else 'no'} | "
            f"{report.seed_converged} | "
            f"{seed_error_text} | "
            f"{germ_error_text} | "
            f"{report.passed_count}/{report.scenario_count} | "
            f"{report.worst_voltage_diff:.4e} | "
            f"{report.worst_flow_diff_mva:.4e} | "
            f"{report.worst_loading_diff:.4e} | "
            f"{report.worst_write_error:.4e} | "
            f"{status_text} |"
        )

    lines.append("")


def append_detailed_sections(
    lines: list[str],
    scenarios: list[FireTestScenario],
    mode_reports: list[ArtifactSeedModeReport],
) -> None:
    """
    Append one detailed section per seed mode.

    :param lines:
        Mutable markdown line buffer.
    :param scenarios:
        Scenario list used in the evaluation.
    :param mode_reports:
        Report entries for all seed modes.
    :return:
        None.
    """
    report: ArtifactSeedModeReport

    for report in mode_reports:
        lines.append(f"## {report.mode_name}")
        lines.append("")
        lines.append(f"- artifact: `{report.artifact_path}`")
        lines.append(f"- external NR seed used during training: `{'yes' if report.external_nr_seed_used else 'no'}`")
        lines.append(f"- explicit seed converged: `{report.seed_converged}`")

        if report.seed_error is None:
            lines.append("- explicit seed error: `n/a`")
        else:
            lines.append(f"- explicit seed error: `{report.seed_error:.4e}`")

        if report.germ_error is None:
            lines.append("- artifact germ error: `n/a`")
        else:
            lines.append(f"- artifact germ error: `{report.germ_error:.4e}`")

        if report.failure_message is None:
            lines.append(f"- passed scenarios: `{report.passed_count}/{report.scenario_count}`")
            lines.append("")
            lines.append("| scenario | dP sum | dQ sum | nr conv | art conv | write err | nr err | art err | max dV | max dSf | max dloading | passed |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
            scenario_index: int

            for scenario_index in range(len(report.metrics_list)):
                scenario: FireTestScenario = scenarios[scenario_index]
                metrics: FireTestMetrics = report.metrics_list[scenario_index]
                lines.append(
                    f"| {scenario.name} | "
                    f"{scenario.active_delta_sum:+.3e} | "
                    f"{scenario.reactive_delta_sum:+.3e} | "
                    f"{metrics.nr_converged} | "
                    f"{metrics.artifact_converged} | "
                    f"{metrics.injection_write_error:.3e} | "
                    f"{metrics.nr_error:.3e} | "
                    f"{metrics.artifact_error:.3e} | "
                    f"{metrics.max_voltage_diff:.3e} | "
                    f"{metrics.max_flow_diff_mva:.3e} | "
                    f"{metrics.max_loading_diff:.3e} | "
                    f"{metrics.passed} |"
                )
        else:
            lines.append(f"- status: `failed`")
            lines.append(f"- failure: `{report.failure_message}`")

        lines.append("")


def write_markdown_report(
    report_path: Path,
    case_path: Path,
    scenarios: list[FireTestScenario],
    mode_reports: list[ArtifactSeedModeReport],
    max_order: int,
    random_seed: int,
    artifact_tolerance: float,
    voltage_threshold: float,
    branch_flow_threshold_mva: float,
    loading_threshold: float,
    injection_write_threshold: float,
) -> None:
    """
    Write the final markdown report to disk.

    :param report_path:
        Output markdown path.
    :param case_path:
        MATPOWER case path used for the evaluation.
    :param scenarios:
        Scenario list used for the evaluation.
    :param mode_reports:
        Report entries for all seed modes.
    :param max_order:
        Artifact maximum order.
    :param random_seed:
        Random seed used to create scenarios.
    :param artifact_tolerance:
        Artifact mismatch threshold.
    :param voltage_threshold:
        Voltage pass threshold.
    :param branch_flow_threshold_mva:
        Branch-flow pass threshold.
    :param loading_threshold:
        Loading pass threshold.
    :param injection_write_threshold:
        Injection write threshold.
    :return:
        None.
    """
    lines: list[str] = list()
    append_report_settings(
        lines=lines,
        case_path=case_path,
        report_path=report_path,
        max_order=max_order,
        scenario_count=len(scenarios),
        random_seed=random_seed,
        artifact_tolerance=artifact_tolerance,
        voltage_threshold=voltage_threshold,
        branch_flow_threshold_mva=branch_flow_threshold_mva,
        loading_threshold=loading_threshold,
        injection_write_threshold=injection_write_threshold,
    )
    append_summary_table(lines=lines, mode_reports=mode_reports)
    append_detailed_sections(lines=lines, scenarios=scenarios, mode_reports=mode_reports)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def run_case14_seed_options_report() -> None:
    """
    Build IEEE14 artifacts for several seed modes and write a comparison report.

    :return:
        None.
    """
    case_path: Path = Path(__file__).resolve().with_name("case14.matpower")
    report_path: Path = Path(__file__).resolve().with_name("mdhelm_pv_case14_seed_options_report.md")
    output_dir: Path = report_path.parent
    max_order: int = 4
    scenario_count: int = 10
    random_seed: int = 14
    artifact_tolerance: float = 1.0e-5
    voltage_threshold: float = 2.0e-2
    branch_flow_threshold_mva: float = 10.0
    loading_threshold: float = 1.0e-1
    injection_write_threshold: float = 2.0e-6
    base_grid: "MultiCircuit" = load_multicircuit_from_file(matpower_path=case_path)
    case_data: VeraGridQueryCaseData = create_mdhelm_inputs(grid=base_grid)
    mapping: DeviceBusMapping = build_device_bus_mapping(grid=base_grid, case_data=case_data)
    scenarios: list[FireTestScenario] = create_fire_test_scenarios(
        case_data=case_data,
        mapping=mapping,
        scenario_count=scenario_count,
        seed=random_seed,
    )
    seed_modes: list[ArtifactSeedMode] = list()
    seed_modes.append(ArtifactSeedMode.INTERNAL_HELM)
    seed_modes.append(ArtifactSeedMode.EXPLICIT_HELM)
    seed_modes.append(ArtifactSeedMode.EXPLICIT_NR)
    mode_reports: list[ArtifactSeedModeReport] = list()
    seed_mode: ArtifactSeedMode

    for seed_mode in seed_modes:
        report: ArtifactSeedModeReport = evaluate_seed_mode(
            base_grid=base_grid,
            case_data=case_data,
            mapping=mapping,
            scenarios=scenarios,
            output_dir=output_dir,
            seed_mode=seed_mode,
            max_order=max_order,
            artifact_tolerance=artifact_tolerance,
            voltage_threshold=voltage_threshold,
            branch_flow_threshold_mva=branch_flow_threshold_mva,
            loading_threshold=loading_threshold,
            injection_write_threshold=injection_write_threshold,
        )
        mode_reports.append(report)

    write_markdown_report(
        report_path=report_path,
        case_path=case_path,
        scenarios=scenarios,
        mode_reports=mode_reports,
        max_order=max_order,
        random_seed=random_seed,
        artifact_tolerance=artifact_tolerance,
        voltage_threshold=voltage_threshold,
        branch_flow_threshold_mva=branch_flow_threshold_mva,
        loading_threshold=loading_threshold,
        injection_write_threshold=injection_write_threshold,
    )
    print(f"Seed-mode report written to: {report_path}")
    report: ArtifactSeedModeReport
    for report in mode_reports:
        print(
            f"{report.mode_name}: "
            f"passed {report.passed_count}/{report.scenario_count}, "
            f"worst_dV={report.worst_voltage_diff:.4e}, "
            f"worst_dSf={report.worst_flow_diff_mva:.4e}, "
            f"status={'ok' if report.failure_message is None else 'failed'}"
        )


if __name__ == "__main__":
    run_case14_seed_options_report()
