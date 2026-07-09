"""
Build and fire-test the compressed order-2 MDHEM artifact.

The artifact keeps the full per-bus query API:

* PQ buses: active and reactive power,
* PV buses: active power.

The compression happens only in the quadratic correction:

1. a full first-order artifact is solved for every query dimension,
2. the strongest dimensions are retained,
3. an exact order-2 artifact is solved only on that retained subset,
4. the online query returns the exact linear response plus the retained
   quadratic correction,
5. Newton-Raphson is used only as the external validation reference.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from mdhelm import MDHEMOrder2CompressedArtifact
from mdhelm import VeraGridQueryCaseData
from mdhelm import build_order2_compressed_artifact_from_case
from mdhelm import import_veragrid_engine_modules
from mdhelm import load_multicircuit_from_file
from mdhelm import load_order2_compressed_artifact
from mdhelm import save_order2_compressed_artifact
from mdhelm_pv_case14_fire_test import DeviceBusMapping
from mdhelm_pv_case14_fire_test import FireTestMetrics
from mdhelm_pv_case14_fire_test import FireTestScenario
from mdhelm_pv_case14_fire_test import build_device_bus_mapping
from mdhelm_pv_case14_fire_test import create_fire_test_scenarios
from mdhelm_pv_case14_fire_test import evaluate_scenario

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


def resolve_case_path() -> Path:
    """
    Resolve the MATPOWER case used by the report script.

    Returns
    -------
    pathlib.Path
        Existing MATPOWER case path.
    """
    script_dir: Path = Path(__file__).resolve().parent
    activsg_path: Path = script_dir / "case_ACTIVSg2000.matpower"
    case14_path: Path = script_dir / "case14.matpower"

    if activsg_path.exists():
        return activsg_path
    else:
        if case14_path.exists():
            return case14_path
        else:
            raise FileNotFoundError("Neither case_ACTIVSg2000.matpower nor case14.matpower was found")


def create_optional_nr_seed(grid: "MultiCircuit", enabled: bool) -> Optional["PowerFlowResults"]:
    """
    Optionally create a Newton-Raphson seed for artifact training.

    Parameters
    ----------
    grid:
        VeraGrid grid used by the seed solve.
    enabled:
        Whether the explicit Newton-Raphson seed should be created.

    Returns
    -------
    Optional[PowerFlowResults]
        Converged seed result or ``None``.
    """
    if enabled:
        vg: object
        cf: object
        vg, cf = import_veragrid_engine_modules()
        _ = cf
        try:
            options: object = vg.PowerFlowOptions(
                solver_type=vg.SolverType.NR,
                retry_with_other_methods=False,
                control_q=True,
                control_taps_phase=False,
                control_taps_modules=False,
                apply_temperature_correction=False,
                use_stored_guess=False,
                tolerance=1e-10,
            )
        except TypeError:
            options = vg.PowerFlowOptions(vg.SolverType.NR, verbose=False)
        power_flow_results: "PowerFlowResults" = vg.power_flow(grid=grid, options=options)

        if bool(power_flow_results.converged):
            return power_flow_results
        else:
            raise RuntimeError(f"NR seed solve failed with error {float(power_flow_results.error):.6e}")
    else:
        return None


def determine_run_settings(case_path: Path) -> tuple[int, int, bool]:
    """
    Determine practical default settings for the selected case.

    Parameters
    ----------
    case_path:
        MATPOWER case path.

    Returns
    -------
    tuple[int, int, bool]
        ``(retained_dimensions, scenario_count, use_nr_seed)``.
    """
    case_name: str = case_path.stem.lower()

    if "activsg2000" in case_name:
        return 8, 2, True
    else:
        return 12, 4, False


def build_markdown_report(
    case_path: Path,
    artifact_path: Path,
    retained_dimensions: int,
    scenario_count: int,
    use_nr_seed: bool,
    germ_error: float,
    artifact: MDHEMOrder2CompressedArtifact,
    metrics_list: list[FireTestMetrics],
) -> str:
    """
    Build the markdown validation report.

    Parameters
    ----------
    case_path:
        MATPOWER case path.
    artifact_path:
        Saved artifact path.
    retained_dimensions:
        Requested retained quadratic dimension count.
    scenario_count:
        Number of evaluated scenarios.
    use_nr_seed:
        Whether NR was used as the artifact germ seed.
    germ_error:
        Reported germ-solve error.
    artifact:
        Restored compressed artifact.
    metrics_list:
        Scenario metrics.

    Returns
    -------
    str
        Markdown report text.
    """
    passed_count: int = 0
    worst_voltage_diff: float = 0.0
    worst_flow_diff_mva: float = 0.0
    worst_loading_diff: float = 0.0
    worst_write_error: float = 0.0
    metric: FireTestMetrics

    for metric in metrics_list:
        if metric.passed:
            passed_count = passed_count + 1
        else:
            passed_count = passed_count

        if metric.max_voltage_diff > worst_voltage_diff:
            worst_voltage_diff = metric.max_voltage_diff
        else:
            worst_voltage_diff = worst_voltage_diff

        if metric.max_flow_diff_mva > worst_flow_diff_mva:
            worst_flow_diff_mva = metric.max_flow_diff_mva
        else:
            worst_flow_diff_mva = worst_flow_diff_mva

        if metric.max_loading_diff > worst_loading_diff:
            worst_loading_diff = metric.max_loading_diff
        else:
            worst_loading_diff = worst_loading_diff

        if metric.injection_write_error > worst_write_error:
            worst_write_error = metric.injection_write_error
        else:
            worst_write_error = worst_write_error

    lines: list[str] = list()
    lines.append("# MDHEM compressed order-2 report")
    lines.append("")
    lines.append(f"- Timestamp: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"- Case: `{case_path}`")
    lines.append(f"- Artifact: `{artifact_path}`")
    lines.append(f"- Requested retained dimensions: `{retained_dimensions}`")
    lines.append(f"- Retained dimensions in artifact: `{artifact.get_quadratic_dimensions_count()}`")
    lines.append(f"- Scenario count: `{scenario_count}`")
    lines.append(f"- NR seed used for training: `{use_nr_seed}`")
    lines.append(f"- Germ error: `{germ_error:.6e}`")
    lines.append(f"- Passed scenarios: `{passed_count}/{len(metrics_list)}`")
    lines.append(f"- Worst voltage diff: `{worst_voltage_diff:.6e}` p.u.")
    lines.append(f"- Worst branch flow diff: `{worst_flow_diff_mva:.6e}` MVA")
    lines.append(f"- Worst loading diff: `{worst_loading_diff:.6e}`")
    lines.append(f"- Worst injection write error: `{worst_write_error:.6e}` p.u.")
    lines.append("")
    lines.append("## Retained quadratic dimensions")
    lines.append("")

    retained_names: list[str] = list(artifact.get_quadratic_dimension_names())
    retained_scores: list[float] = list(artifact.get_quadratic_dimension_scores())
    item_index: int
    for item_index in range(len(retained_names)):
        lines.append(f"- `{retained_names[item_index]}` score `{retained_scores[item_index]:.6e}`")

    lines.append("")
    lines.append("## Scenario metrics")
    lines.append("")
    lines.append("| Scenario | Passed | NR converged | Artifact converged | Voltage diff | Flow diff MVA | Loading diff | Write error |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: |")

    for metric in metrics_list:
        lines.append(
            "| "
            f"{metric.scenario_name} | "
            f"{metric.passed} | "
            f"{metric.nr_converged} | "
            f"{metric.artifact_converged} | "
            f"{metric.max_voltage_diff:.6e} | "
            f"{metric.max_flow_diff_mva:.6e} | "
            f"{metric.max_loading_diff:.6e} | "
            f"{metric.injection_write_error:.6e} |"
        )

    lines.append("")
    return "\n".join(lines)


def run_order2_compressed_report() -> None:
    """
    Build, save, reload and fire-test the compressed order-2 artifact.

    Returns
    -------
    None
        The report is printed and saved to disk.
    """
    case_path: Path = resolve_case_path()
    retained_dimensions: int
    scenario_count: int
    use_nr_seed: bool
    retained_dimensions, scenario_count, use_nr_seed = determine_run_settings(case_path=case_path)
    scenario_seed: int = 14
    artifact_tolerance: float = 1.0e-6
    voltage_threshold: float = 2.0e-4
    branch_flow_threshold_mva: float = 2.0e-1
    loading_threshold: float = 2.0e-3
    injection_write_threshold: float = 1.0e-9
    grid: "MultiCircuit" = load_multicircuit_from_file(matpower_path=case_path)
    seed_results: Optional["PowerFlowResults"] = create_optional_nr_seed(grid=grid, enabled=use_nr_seed)
    case_data: VeraGridQueryCaseData
    artifact: MDHEMOrder2CompressedArtifact
    germ_error: float
    case_data, artifact, germ_error = build_order2_compressed_artifact_from_case(
        grid=grid,
        retained_dimensions=retained_dimensions,
        germ_seed_results=seed_results,
    )
    artifact_path: Path = Path(__file__).resolve().with_name(f"{case_path.stem}_order2_compressed_artifact.npz")
    save_order2_compressed_artifact(path=artifact_path, artifact=artifact)
    restored_artifact: MDHEMOrder2CompressedArtifact = load_order2_compressed_artifact(path=artifact_path)
    mapping: DeviceBusMapping = build_device_bus_mapping(grid=grid, case_data=case_data)
    scenarios: list[FireTestScenario] = create_fire_test_scenarios(
        case_data=case_data,
        mapping=mapping,
        scenario_count=scenario_count,
        seed=scenario_seed,
    )
    metrics_list: list[FireTestMetrics] = list()
    scenario: FireTestScenario

    for scenario in scenarios:
        metrics_list.append(
            evaluate_scenario(
                base_grid=grid,
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
        )

    report_text: str = build_markdown_report(
        case_path=case_path,
        artifact_path=artifact_path,
        retained_dimensions=retained_dimensions,
        scenario_count=scenario_count,
        use_nr_seed=use_nr_seed,
        germ_error=germ_error,
        artifact=restored_artifact,
        metrics_list=metrics_list,
    )
    report_path: Path = Path(__file__).resolve().with_name(f"{case_path.stem}_order2_compressed_report.md")
    report_path.write_text(report_text, encoding="utf-8")
    print(report_text)
    print(f"\nSaved report to {report_path}")


if __name__ == "__main__":
    run_order2_compressed_report()
