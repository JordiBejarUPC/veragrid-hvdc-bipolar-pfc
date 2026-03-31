from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Tuple

import numpy as np

from trunk.dynamics_emt.support.benchmark_dependency_stubs import install_optional_dependency_stubs

install_optional_dependency_stubs()

import trunk.dynamics_emt.scripting_emt_event as event_script
import trunk.dynamics_emt.scripting_example_thevequiv_piline_Rload_emt as rload_script
import trunk.dynamics_emt.scripting_example_thevequiv_piline_ZIPload_emt as zipload_script
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_solver_registry import resolve_emt_sparse_solver_backend_provider
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes, SparseSolver


class SparseBenchmarkCase(Enum):
    """
    EMT cases supported by the sparse backend benchmark.
    """

    ZIPLOAD = "zipload"
    RLOAD = "rload"
    EVENT = "event"


class SparseBenchmarkProfile(Enum):
    """
    Benchmark profiles supported by the sparse backend benchmark.
    """

    RegressionShort = "regression_short"
    PaperLong = "paper_long"


class SparseBackendBenchmarkResult:
    """
    One sparse-backend benchmark row.
    """

    __slots__ = ["_payload"]

    def __init__(self, payload: Dict[str, object]) -> None:
        """
        Build one sparse-backend benchmark row.

        :param payload: JSON-serializable benchmark payload.
        :type payload: Dict[str, object]
        :return: None.
        :rtype: None
        """
        self._payload: Dict[str, object] = dict(payload)

    def get_payload(self) -> Dict[str, object]:
        """
        Return the benchmark payload.

        :return: Benchmark payload.
        :rtype: Dict[str, object]
        """
        return dict(self._payload)


def get_results_directory() -> Path:
    """
    Return the EMT benchmark-results directory.

    :return: Benchmark-results directory.
    :rtype: Path
    """
    output_dir: Path = Path(__file__).resolve().parents[1] / "benchmark_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def resolve_case_module(case_name: SparseBenchmarkCase) -> Any:
    """
    Resolve the script module for one EMT case.

    :param case_name: Benchmark case.
    :type case_name: SparseBenchmarkCase
    :return: Script module.
    :rtype: Any
    """
    if case_name == SparseBenchmarkCase.ZIPLOAD:
        return zipload_script
    elif case_name == SparseBenchmarkCase.RLOAD:
        return rload_script
    else:
        return event_script


def configure_case_profile(case_name: SparseBenchmarkCase, profile: SparseBenchmarkProfile) -> None:
    """
    Configure one case module for the requested benchmark profile.

    :param case_name: Benchmark case.
    :type case_name: SparseBenchmarkCase
    :param profile: Benchmark profile.
    :type profile: SparseBenchmarkProfile
    :return: None.
    :rtype: None
    """
    module_obj: Any = resolve_case_module(case_name)
    module_obj.SOLVER_VERBOSE = False

    if hasattr(module_obj, "ENABLE_NEWTON_TRACE"):
        module_obj.ENABLE_NEWTON_TRACE = False
    else:
        pass

    if profile == SparseBenchmarkProfile.RegressionShort:
        if case_name == SparseBenchmarkCase.EVENT:
            module_obj.options.time_step = 1e-3
            module_obj.options.simulation_time = 5e-2
        else:
            module_obj.options.time_step = 5e-5
            module_obj.options.simulation_time = 5e-4
    else:
        pass


def build_problem(case_name: SparseBenchmarkCase) -> Any:
    """
    Build one EMT problem for the requested case.

    :param case_name: Benchmark case.
    :type case_name: SparseBenchmarkCase
    :return: EMT problem instance.
    :rtype: Any
    """
    module_obj: Any = resolve_case_module(case_name)

    if case_name == SparseBenchmarkCase.ZIPLOAD:
        return module_obj.create_problem(enable_trace=False)
    else:
        return module_obj.create_problem()


def build_solver_options(
        case_name: SparseBenchmarkCase,
        solver_type: EmtSolverTypes,
        sparse_solver: SparseSolver,
        plugin_name: str,
        allow_internal_fallback: bool,
) -> EmtOptions:
    """
    Build one EMT options object for sparse-backend benchmarking.

    :param case_name: Benchmark case.
    :type case_name: SparseBenchmarkCase
    :param solver_type: EMT solver family.
    :type solver_type: EmtSolverTypes
    :param sparse_solver: Sparse solver selection.
    :type sparse_solver: SparseSolver
    :param plugin_name: External plugin name.
    :type plugin_name: str
    :param allow_internal_fallback: Whether internal fallback is allowed.
    :type allow_internal_fallback: bool
    :return: EMT options.
    :rtype: EmtOptions
    """
    module_obj: Any = resolve_case_module(case_name)
    return EmtOptions(
        time_step=module_obj.options.time_step,
        simulation_time=module_obj.options.simulation_time,
        solver_type=solver_type,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        sparse_solver=sparse_solver,
        external_sparse_solver_plugin_name=plugin_name,
        allow_internal_sparse_fallback=allow_internal_fallback,
    )


def build_solver(
        case_name: SparseBenchmarkCase,
        solver_type: EmtSolverTypes,
        sparse_solver: SparseSolver,
        plugin_name: str,
        allow_internal_fallback: bool,
) -> Tuple[Any, Any, EmtOptions]:
    """
    Build one EMT problem and solver for sparse-backend benchmarking.

    :param case_name: Benchmark case.
    :type case_name: SparseBenchmarkCase
    :param solver_type: EMT solver family.
    :type solver_type: EmtSolverTypes
    :param sparse_solver: Sparse solver selection.
    :type sparse_solver: SparseSolver
    :param plugin_name: External plugin name.
    :type plugin_name: str
    :param allow_internal_fallback: Whether internal fallback is allowed.
    :type allow_internal_fallback: bool
    :return: Tuple ``(problem, solver, options)``.
    :rtype: Tuple[Any, Any, EmtOptions]
    """
    problem = build_problem(case_name)
    options: EmtOptions = build_solver_options(case_name, solver_type, sparse_solver, plugin_name, allow_internal_fallback)
    solver = build_emt_solver(
        options=options,
        problem=problem,
        t0=0.0,
        t_end=options.simulation_time,
        h=options.time_step,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        newton_diag_config=None,
    )
    return problem, solver, options


def resolve_solver_family_label(solver_type: EmtSolverTypes) -> str:
    """
    Return the human-readable solver-family label.

    :param solver_type: EMT solver family.
    :type solver_type: EmtSolverTypes
    :return: Solver-family label.
    :rtype: str
    """
    if solver_type == EmtSolverTypes.StructuralCompiled:
        return "COMPILED"
    elif solver_type == EmtSolverTypes.StructuralAD:
        return "VECTORIZED"
    else:
        raise ValueError(f"Unsupported sparse benchmark solver family: {solver_type}")


def run_single_sparse_backend_benchmark(
        case_name: SparseBenchmarkCase,
        solver_type: EmtSolverTypes,
        sparse_solver: SparseSolver,
        plugin_name: str,
        allow_internal_fallback: bool,
        reference_y: np.ndarray | None,
        reference_dy: np.ndarray | None,
) -> Tuple[SparseBackendBenchmarkResult, np.ndarray, np.ndarray]:
    """
    Run one sparse-backend benchmark row.

    :param case_name: Benchmark case.
    :type case_name: SparseBenchmarkCase
    :param solver_type: EMT solver family.
    :type solver_type: EmtSolverTypes
    :param sparse_solver: Sparse solver selection.
    :type sparse_solver: SparseSolver
    :param plugin_name: External plugin name.
    :type plugin_name: str
    :param allow_internal_fallback: Whether internal fallback is allowed.
    :type allow_internal_fallback: bool
    :param reference_y: Reference state trajectory or ``None``.
    :type reference_y: np.ndarray | None
    :param reference_dy: Reference derivative trajectory or ``None``.
    :type reference_dy: np.ndarray | None
    :return: Tuple ``(result, y, dy)``.
    :rtype: Tuple[SparseBackendBenchmarkResult, np.ndarray, np.ndarray]
    """
    problem_build_t0: float = perf_counter()
    problem, solver, options = build_solver(case_name, solver_type, sparse_solver, plugin_name, allow_internal_fallback)
    problem_build_s: float = perf_counter() - problem_build_t0

    # The solver is built inside ``build_emt_solver``. The benchmark reports that
    # end-to-end cost as initialization because it is exactly what a user pays.
    solver_init_s: float = 0.0
    solver_build_s: float = 0.0

    if solver_type == EmtSolverTypes.StructuralCompiled:
        backend_build_stats: Dict[str, float] = solver.get_backend_build_stats()
    else:
        backend_build_stats = solver.get_backend_build_stats()

    if "total_s" in backend_build_stats:
        solver_build_s = float(backend_build_stats["total_s"])
    else:
        solver_build_s = 0.0

    boundary_updater = problem
    sim_t0: float = perf_counter()
    t_arr, y_arr, dy_arr = solver.simulate(boundary_updater=boundary_updater)
    simulate_s: float = perf_counter() - sim_t0

    if reference_y is None:
        y_max_abs_diff: float = 0.0
    else:
        y_max_abs_diff = float(np.max(np.abs(y_arr - reference_y)))

    if reference_dy is None:
        dy_max_abs_diff: float = 0.0
    else:
        dy_max_abs_diff = float(np.max(np.abs(dy_arr - reference_dy)))

    result_payload: Dict[str, object] = dict(
        case=case_name.value,
        solver_family=resolve_solver_family_label(solver_type),
        sparse_solver=str(sparse_solver),
        external_plugin_name=plugin_name,
        allow_internal_fallback=allow_internal_fallback,
        time_step=options.time_step,
        simulation_time=options.simulation_time,
        problem_build_s=problem_build_s,
        solver_init_s=solver_init_s,
        solver_build_s=solver_build_s,
        simulate_s=simulate_s,
        solver_total_s=problem_build_s + solver_init_s + simulate_s,
        loop_s=float(solver.get_last_sim_loop_time()),
        y_max_abs_diff=y_max_abs_diff,
        dy_max_abs_diff=dy_max_abs_diff,
        build_stats=backend_build_stats,
        runtime_stats=solver.get_last_runtime_stats(),
        steps=int(len(t_arr) - 1),
    )
    return SparseBackendBenchmarkResult(result_payload), y_arr, dy_arr


def export_sparse_backend_benchmark(rows: List[SparseBackendBenchmarkResult], file_stem: str) -> List[Path]:
    """
    Export the sparse-backend benchmark summary.

    :param rows: Benchmark rows.
    :type rows: List[SparseBackendBenchmarkResult]
    :param file_stem: Output file stem without extension.
    :type file_stem: str
    :return: Exported file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_results_directory()
    csv_path: Path = output_dir / f"{file_stem}.csv"
    json_path: Path = output_dir / f"{file_stem}.json"
    markdown_path: Path = output_dir / f"{file_stem}.md"
    csv_lines: List[str] = list()
    json_rows: List[Dict[str, object]] = list()
    markdown_lines: List[str] = list()
    row_index: int = 0

    csv_lines.append(
        "case,solver_family,sparse_solver,problem_build_s,solver_build_s,simulate_s,solver_total_s,loop_s,y_max_abs_diff,dy_max_abs_diff"
    )
    markdown_lines.append(
        "| Case | Solver Family | Sparse Solver | Build [s] | Sim [s] | Total [s] | Loop [s] | y Max Diff | dy Max Diff |"
    )
    markdown_lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")

    while row_index < len(rows):
        payload: Dict[str, object] = rows[row_index].get_payload()
        csv_lines.append(
            f"{payload['case']},{payload['solver_family']},{payload['sparse_solver']},{float(payload['problem_build_s']):.9f},"
            f"{float(payload['solver_build_s']):.9f},{float(payload['simulate_s']):.9f},{float(payload['solver_total_s']):.9f},"
            f"{float(payload['loop_s']):.9f},{float(payload['y_max_abs_diff']):.9e},{float(payload['dy_max_abs_diff']):.9e}"
        )
        json_rows.append(payload)
        markdown_lines.append(
            f"| {payload['case']} | {payload['solver_family']} | {payload['sparse_solver']} | "
            f"{float(payload['solver_build_s']):.6f} | {float(payload['simulate_s']):.6f} | {float(payload['solver_total_s']):.6f} | "
            f"{float(payload['loop_s']):.6f} | {float(payload['y_max_abs_diff']):.3e} | {float(payload['dy_max_abs_diff']):.3e} |"
        )
        row_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def build_sparse_solver_benchmark_targets() -> List[Tuple[SparseSolver, str, bool]]:
    """
    Build the sparse solver targets to benchmark.

    :return: Sparse solver targets as ``(solver, plugin_name, allow_fallback)``.
    :rtype: List[Tuple[SparseSolver, str, bool]]
    """
    targets: List[Tuple[SparseSolver, str, bool]] = list()
    targets.append((SparseSolver.SuperLU, "", True))

    pardiso_provider = resolve_emt_sparse_solver_backend_provider(
        solver_type=SparseSolver.Pardiso,
        external_plugin_name="pardiso_pypardiso",
        external_plugin_directory="",
        allow_internal_fallback=True,
    )

    if pardiso_provider.get_solver_type() == SparseSolver.Pardiso:
        targets.append((SparseSolver.Pardiso, "pardiso_pypardiso", False))
    else:
        pass

    klu_provider = resolve_emt_sparse_solver_backend_provider(
        solver_type=SparseSolver.KLU,
        external_plugin_name="klu_vcpkg_native",
        external_plugin_directory="",
        allow_internal_fallback=True,
    )

    if klu_provider.get_solver_type() == SparseSolver.KLU:
        targets.append((SparseSolver.KLU, "klu_vcpkg_native", False))
    else:
        pass

    return targets


def build_sparse_backend_benchmark_file_stem(profile: SparseBenchmarkProfile) -> str:
    """
    Build the output file stem for one sparse backend benchmark profile.

    :param profile: Benchmark profile.
    :type profile: SparseBenchmarkProfile
    :return: Output file stem.
    :rtype: str
    """
    if profile == SparseBenchmarkProfile.RegressionShort:
        return "emt_sparse_backend_ab"
    else:
        return "emt_sparse_backend_ab_paper_long"


def benchmark_sparse_backends(profile: SparseBenchmarkProfile = SparseBenchmarkProfile.RegressionShort) -> List[SparseBackendBenchmarkResult]:
    """
    Benchmark `SuperLU` against external `Pardiso` for the compiled and vectorized EMT backends.

    :param profile: Benchmark profile.
    :type profile: SparseBenchmarkProfile
    :return: Benchmark rows.
    :rtype: List[SparseBackendBenchmarkResult]
    """
    cases: List[SparseBenchmarkCase] = [SparseBenchmarkCase.ZIPLOAD, SparseBenchmarkCase.RLOAD, SparseBenchmarkCase.EVENT]
    solver_types: List[EmtSolverTypes] = [EmtSolverTypes.StructuralCompiled, EmtSolverTypes.StructuralAD]
    sparse_targets: List[Tuple[SparseSolver, str, bool]] = build_sparse_solver_benchmark_targets()
    rows: List[SparseBackendBenchmarkResult] = list()
    case_index: int = 0

    while case_index < len(cases):
        case_name: SparseBenchmarkCase = cases[case_index]
        configure_case_profile(case_name, profile)
        solver_index: int = 0

        while solver_index < len(solver_types):
            solver_type: EmtSolverTypes = solver_types[solver_index]
            target_index: int = 0
            reference_y: np.ndarray | None = None
            reference_dy: np.ndarray | None = None

            while target_index < len(sparse_targets):
                sparse_solver, plugin_name, allow_internal_fallback = sparse_targets[target_index]
                result, current_y, current_dy = run_single_sparse_backend_benchmark(
                    case_name=case_name,
                    solver_type=solver_type,
                    sparse_solver=sparse_solver,
                    plugin_name=plugin_name,
                    allow_internal_fallback=allow_internal_fallback,
                    reference_y=reference_y,
                    reference_dy=reference_dy,
                )
                rows.append(result)

                if reference_y is None:
                    reference_y = current_y
                    reference_dy = current_dy
                else:
                    reference_y = reference_y
                    reference_dy = reference_dy

                target_index += 1

            solver_index += 1

        case_index += 1

    export_sparse_backend_benchmark(rows, build_sparse_backend_benchmark_file_stem(profile))
    return rows


if __name__ == "__main__":
    benchmark_sparse_backends()
