import time
from typing import List

import matplotlib.pyplot as plt

from VeraGridEngine.enumerations import EmtInitializationMethod
from trunk.implicit_solver_test_EMT.initialization_workflow_support import build_two_bus_real_emt_case, evaluate_algebraic_residual_inf


class InitializationBenchmarkResult:
    """
    Timing and quality summary for one EMT initialization workflow.
    """

    __slots__ = [
        "_requested_name",
        "_used_name",
        "_status_name",
        "_problem_build_elapsed_s",
        "_native_stage_elapsed_s",
        "_initial_residual_inf",
        "_final_residual_inf",
        "_newton_iterations",
        "_pseudo_transient_steps",
        "_automatic_dx0_count",
    ]

    def __init__(
            self,
            requested_name: str,
            used_name: str,
            status_name: str,
            problem_build_elapsed_s: float,
            native_stage_elapsed_s: float,
            initial_residual_inf: float,
            final_residual_inf: float,
            newton_iterations: int,
            pseudo_transient_steps: int,
            automatic_dx0_count: int,
    ) -> None:
        self._requested_name: str = requested_name
        self._used_name: str = used_name
        self._status_name: str = status_name
        self._problem_build_elapsed_s: float = float(problem_build_elapsed_s)
        self._native_stage_elapsed_s: float = float(native_stage_elapsed_s)
        self._initial_residual_inf: float = float(initial_residual_inf)
        self._final_residual_inf: float = float(final_residual_inf)
        self._newton_iterations: int = int(newton_iterations)
        self._pseudo_transient_steps: int = int(pseudo_transient_steps)
        self._automatic_dx0_count: int = int(automatic_dx0_count)

    def get_requested_name(self) -> str:
        return self._requested_name

    def get_used_name(self) -> str:
        return self._used_name

    def get_status_name(self) -> str:
        return self._status_name

    def get_problem_build_elapsed_s(self) -> float:
        return self._problem_build_elapsed_s

    def get_native_stage_elapsed_s(self) -> float:
        return self._native_stage_elapsed_s

    def get_initial_residual_inf(self) -> float:
        return self._initial_residual_inf

    def get_final_residual_inf(self) -> float:
        return self._final_residual_inf

    def get_newton_iterations(self) -> int:
        return self._newton_iterations

    def get_pseudo_transient_steps(self) -> int:
        return self._pseudo_transient_steps

    def get_automatic_dx0_count(self) -> int:
        return self._automatic_dx0_count


def measure_initialization_method(method: EmtInitializationMethod) -> InitializationBenchmarkResult:
    """
    Measure one EMT initialization workflow on the ZIP-load real case.

    :param method: Requested initialization workflow.
    :return: Benchmark result.
    """
    t_start: float = time.perf_counter()
    problem, _ = build_two_bus_real_emt_case(zip_load=True, initialization_method=method)
    problem_build_elapsed_s: float = time.perf_counter() - t_start
    residual_inf: float = evaluate_algebraic_residual_inf(problem)
    report = problem.initialization_report

    if report is None:
        used_name: str = "NONE"
        status_name: str = "FAILED"
        native_stage_elapsed_s: float = float("nan")
        initial_residual_inf: float = float("nan")
        final_residual_inf: float = float("nan")
        newton_iterations: int = 0
        pseudo_transient_steps: int = 0
        automatic_dx0_count: int = 0
    else:
        used_name = report.method_used.name
        status_name = report.status.name
        native_stage_elapsed_s = report.elapsed_s
        initial_residual_inf = report.initial_residual_inf
        final_residual_inf = max(residual_inf, report.final_residual_inf)
        newton_iterations = report.newton_iterations
        pseudo_transient_steps = report.pseudo_transient_steps
        automatic_dx0_count = report.automatic_dx0_count

    return InitializationBenchmarkResult(
        requested_name=method.name,
        used_name=used_name,
        status_name=status_name,
        problem_build_elapsed_s=problem_build_elapsed_s,
        native_stage_elapsed_s=native_stage_elapsed_s,
        initial_residual_inf=initial_residual_inf,
        final_residual_inf=final_residual_inf,
        newton_iterations=newton_iterations,
        pseudo_transient_steps=pseudo_transient_steps,
        automatic_dx0_count=automatic_dx0_count,
    )


def print_benchmark_table(results: List[InitializationBenchmarkResult]) -> None:
    """
    Print the EMT initialization benchmark table.

    :param results: Initialization benchmark results.
    :return: None
    """
    print("\n" + "=" * 120)
    print("EMT INITIALIZATION METHOD BENCHMARK (ZIP LOAD CASE)")
    print("=" * 120)
    print(
        f"{'requested':<18}{'used':<18}{'status':<12}{'build[s]':>14}{'native[s]':>14}{'res0':>14}{'resf':>14}"
        f"{'newton':>10}{'ptc':>10}{'auto_dx0':>12}"
    )
    print("-" * 120)

    for result in results:
        print(
            f"{result.get_requested_name():<18}{result.get_used_name():<18}{result.get_status_name():<12}"
            f"{result.get_problem_build_elapsed_s():>14.6f}{result.get_native_stage_elapsed_s():>14.6f}"
            f"{result.get_initial_residual_inf():>14.3e}{result.get_final_residual_inf():>14.3e}"
            f"{result.get_newton_iterations():>10d}{result.get_pseudo_transient_steps():>10d}"
            f"{result.get_automatic_dx0_count():>12d}"
        )


def choose_best_result(results: List[InitializationBenchmarkResult]) -> InitializationBenchmarkResult:
    """
    Choose the best compromise between quality and cost.

    :param results: Initialization benchmark results.
    :return: Best benchmark result.
    """
    best_result: InitializationBenchmarkResult = results[0]
    idx: int = 1

    while idx < len(results):
        candidate_result: InitializationBenchmarkResult = results[idx]
        better_residual: bool = candidate_result.get_final_residual_inf() < best_result.get_final_residual_inf() - 1.0e-12
        same_residual: bool = abs(candidate_result.get_final_residual_inf() - best_result.get_final_residual_inf()) <= 1.0e-12
        simpler_method: bool = candidate_result.get_pseudo_transient_steps() < best_result.get_pseudo_transient_steps()
        faster_time: bool = candidate_result.get_native_stage_elapsed_s() < best_result.get_native_stage_elapsed_s()

        if better_residual:
            best_result = candidate_result
        elif same_residual and simpler_method:
            best_result = candidate_result
        elif same_residual and (not simpler_method) and faster_time:
            best_result = candidate_result
        else:
            best_result = best_result

        idx += 1

    return best_result


def plot_pareto(results: List[InitializationBenchmarkResult]) -> None:
    """
    Plot a speed-versus-quality Pareto view of the initialization benchmark.

    :param results: Initialization benchmark results.
    :return: None
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    ax_residual = axes[0]
    ax_complexity = axes[1]

    for result in results:
        elapsed_value: float = max(result.get_native_stage_elapsed_s(), 1.0e-12)
        residual_value: float = max(result.get_final_residual_inf(), 1.0e-18)
        pseudo_steps_value: float = float(result.get_pseudo_transient_steps() + 1)
        label_text: str = result.get_requested_name()

        ax_residual.scatter(elapsed_value, residual_value, s=90)
        ax_residual.annotate(label_text, (elapsed_value, residual_value), textcoords="offset points", xytext=(6, 6))

        ax_complexity.scatter(elapsed_value, pseudo_steps_value, s=90)
        ax_complexity.annotate(label_text, (elapsed_value, pseudo_steps_value), textcoords="offset points", xytext=(6, 6))

    ax_residual.set_xlabel("native init elapsed [s]")
    ax_residual.set_ylabel("final residual inf")
    ax_residual.set_yscale("log")
    ax_residual.set_title("Speed vs residual quality")
    ax_residual.grid(True)

    ax_complexity.set_xlabel("native init elapsed [s]")
    ax_complexity.set_ylabel("pseudo-transient steps + 1")
    ax_complexity.set_yscale("log")
    ax_complexity.set_title("Speed vs fallback complexity")
    ax_complexity.grid(True)
    fig.tight_layout()


def main() -> None:
    """
    Run the ZIP-load EMT initialization benchmark.

    :return: None
    """
    methods: List[EmtInitializationMethod] = [
        EmtInitializationMethod.Explicit,
        EmtInitializationMethod.ConsistentNewton,
        EmtInitializationMethod.PseudoTransient,
        EmtInitializationMethod.Auto,
    ]
    results: List[InitializationBenchmarkResult] = list()

    for method in methods:
        results.append(measure_initialization_method(method))

    print_benchmark_table(results)
    best_result: InitializationBenchmarkResult = choose_best_result(results)
    print("-" * 120)
    print(
        f"Best compromise: requested={best_result.get_requested_name()} | used={best_result.get_used_name()} | "
        f"status={best_result.get_status_name()} | build={best_result.get_problem_build_elapsed_s():.6f}s | "
        f"native={best_result.get_native_stage_elapsed_s():.6f}s | final_res={best_result.get_final_residual_inf():.3e}"
    )
    plot_pareto(results)
    plt.show()


if __name__ == "__main__":
    main()
