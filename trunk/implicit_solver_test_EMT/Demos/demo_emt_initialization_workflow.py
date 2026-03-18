import time
from typing import List

import matplotlib.pyplot as plt

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.initialization_emt import run_emt_explicit_initialization, run_emt_native_initialization
from VeraGridEngine.enumerations import EmtInitializationMethod
from trunk.implicit_solver_test_EMT.initialization_workflow_support import (
    build_single_state_single_algebraic_problem,
    build_two_bus_real_emt_case,
    build_unresolved_state_problem,
    evaluate_algebraic_residual_inf,
)


class InitializationBenchmarkRecord:
    """
    Store one initialization benchmark measurement.
    """

    __slots__ = ["_case_name", "_method_name", "_status_name", "_residual_inf", "_dx0_inf", "_elapsed_s"]

    def __init__(
            self,
            case_name: str,
            method_name: str,
            status_name: str,
            residual_inf: float,
            dx0_inf: float,
            elapsed_s: float,
    ) -> None:
        """
        Build one initialization benchmark record.

        :param case_name: Benchmark case identifier.
        :param method_name: Initialization method name.
        :param status_name: Initialization status text.
        :param residual_inf: Algebraic residual infinity norm.
        :param dx0_inf: Differential initialization infinity norm.
        :param elapsed_s: Wall-clock time in seconds.
        :return: None
        """
        self._case_name: str = case_name
        self._method_name: str = method_name
        self._status_name: str = status_name
        self._residual_inf: float = float(residual_inf)
        self._dx0_inf: float = float(dx0_inf)
        self._elapsed_s: float = float(elapsed_s)

    def get_case_name(self) -> str:
        """
        Return the case identifier.

        :return: Case identifier.
        """
        return self._case_name

    def get_method_name(self) -> str:
        """
        Return the initialization method name.

        :return: Method name.
        """
        return self._method_name

    def get_status_name(self) -> str:
        """
        Return the initialization status.

        :return: Status text.
        """
        return self._status_name

    def get_residual_inf(self) -> float:
        """
        Return the algebraic residual infinity norm.

        :return: Residual infinity norm.
        """
        return self._residual_inf

    def get_dx0_inf(self) -> float:
        """
        Return the differential initialization infinity norm.

        :return: Differential initialization infinity norm.
        """
        return self._dx0_inf

    def get_elapsed_s(self) -> float:
        """
        Return the wall-clock time.

        :return: Wall-clock time in seconds.
        """
        return self._elapsed_s


def _build_initialization_options(method: EmtInitializationMethod) -> EmtOptions:
    """
    Build one EMT initialization option set for the benchmark demo.

    :param method: Requested initialization workflow.
    :return: Configured EMT options.
    """
    return EmtOptions(initialization_method=method, init_ptc_max_iter=80)


def _measure_synthetic_case(case_name: str, method: EmtInitializationMethod) -> InitializationBenchmarkRecord:
    """
    Benchmark one synthetic EMT initialization case.

    :param case_name: Synthetic case identifier.
    :param method: Requested initialization workflow.
    :return: Benchmark measurement.
    """
    if case_name == "single_algebraic":
        problem, _ = build_single_state_single_algebraic_problem()
    else:
        problem, _ = build_unresolved_state_problem()

    options: EmtOptions = _build_initialization_options(method)

    # First run the explicit layer because it is the deterministic first stage
    # of the EMT-native workflow and reduces the nonlinear work that follows.
    run_emt_explicit_initialization(problem)

    t_start: float = time.perf_counter()
    report = run_emt_native_initialization(problem, options)
    elapsed_s: float = time.perf_counter() - t_start
    residual_inf: float = evaluate_algebraic_residual_inf(problem)
    dx0_inf: float = float(max(abs(problem.get_dx0())))

    return InitializationBenchmarkRecord(
        case_name=case_name,
        method_name=method.name,
        status_name=report.status.name,
        residual_inf=residual_inf,
        dx0_inf=dx0_inf,
        elapsed_s=elapsed_s,
    )


def _measure_real_case(method: EmtInitializationMethod) -> InitializationBenchmarkRecord:
    """
    Benchmark the two-bus EMT real case with one initialization workflow.

    :param method: Requested initialization workflow.
    :return: Benchmark measurement.
    """
    t_start: float = time.perf_counter()
    problem, _ = build_two_bus_real_emt_case(zip_load=False, initialization_method=method)
    elapsed_s: float = time.perf_counter() - t_start
    residual_inf: float = evaluate_algebraic_residual_inf(problem)
    dx0_inf: float = float(max(abs(problem.get_dx0())))

    status_name: str
    if problem.initialization_report is None:
        status_name = "FAILED"
    else:
        status_name = problem.initialization_report.status.name

    return InitializationBenchmarkRecord(
        case_name="two_bus_real",
        method_name=method.name,
        status_name=status_name,
        residual_inf=residual_inf,
        dx0_inf=dx0_inf,
        elapsed_s=elapsed_s,
    )


def _print_case_table(records: List[InitializationBenchmarkRecord], title: str) -> None:
    """
    Print one benchmark table.

    :param records: Benchmark records.
    :param title: Table title.
    :return: None
    """
    print("=" * 108)
    print(title)
    print("=" * 108)
    print(f"{'case':<22} {'method':<18} {'status':<12} {'alg_res_inf':>16} {'dx0_inf':>16} {'elapsed_s':>16}")

    for record in records:
        print(
            f"{record.get_case_name():<22} {record.get_method_name():<18} {record.get_status_name():<12} "
            f"{record.get_residual_inf():>16.6e} {record.get_dx0_inf():>16.6e} {record.get_elapsed_s():>16.6e}"
        )

    print("")


def _plot_pareto(records: List[InitializationBenchmarkRecord], title: str) -> None:
    """
    Plot a Pareto-style comparison of initialization speed versus residual quality.

    :param records: Benchmark records.
    :param title: Figure title prefix.
    :return: None
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    ax_residual = axes[0]
    ax_dx0 = axes[1]

    for record in records:
        method_name: str = record.get_method_name()
        elapsed_s: float = record.get_elapsed_s()
        residual_inf: float = max(record.get_residual_inf(), 1.0e-18)
        dx0_inf: float = max(record.get_dx0_inf(), 1.0e-18)

        ax_residual.scatter(elapsed_s, residual_inf, s=90)
        ax_residual.annotate(method_name, (elapsed_s, residual_inf), textcoords="offset points", xytext=(6, 6))

        ax_dx0.scatter(elapsed_s, dx0_inf, s=90)
        ax_dx0.annotate(method_name, (elapsed_s, dx0_inf), textcoords="offset points", xytext=(6, 6))

    ax_residual.set_xlabel("elapsed [s]")
    ax_residual.set_ylabel("algebraic residual inf")
    ax_residual.set_yscale("log")
    ax_residual.set_title(f"{title} | speed vs residual")
    ax_residual.grid(True)

    ax_dx0.set_xlabel("elapsed [s]")
    ax_dx0.set_ylabel("dx0 inf")
    ax_dx0.set_yscale("log")
    ax_dx0.set_title(f"{title} | speed vs dx0 scale")
    ax_dx0.grid(True)
    fig.tight_layout()


def main() -> None:
    """
    Run the EMT initialization workflow benchmark demo.

    :return: None
    """
    synthetic_records: List[InitializationBenchmarkRecord] = list()
    real_records: List[InitializationBenchmarkRecord] = list()
    methods: List[EmtInitializationMethod] = [
        EmtInitializationMethod.Explicit,
        EmtInitializationMethod.ConsistentNewton,
        EmtInitializationMethod.PseudoTransient,
    ]

    for method in methods:
        synthetic_records.append(_measure_synthetic_case("single_algebraic", method))
        real_records.append(_measure_real_case(method))

    _print_case_table(synthetic_records, "Synthetic EMT initialization benchmark")
    _print_case_table(real_records, "Real two-bus EMT initialization benchmark")

    _plot_pareto(synthetic_records, "Synthetic")
    _plot_pareto(real_records, "Two-bus real EMT")
    plt.show()


if __name__ == "__main__":
    main()
