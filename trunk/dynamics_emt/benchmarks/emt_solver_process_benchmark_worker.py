import argparse
import contextlib
import io
import json
from enum import Enum
from typing import Any, Dict, List

from trunk.dynamics_emt.support.benchmark_dependency_stubs import install_optional_dependency_stubs

install_optional_dependency_stubs()


class BenchmarkCase(Enum):
    """
    EMT benchmark cases supported by the subprocess worker.
    """

    ZIPLOAD = "zipload"
    RLOAD = "rload"
    EVENT = "event"
    VALIDATE = "validate"


class BenchmarkProfile(Enum):
    """
    Benchmark profiles available to the subprocess worker.
    """

    REGRESSION_SHORT = "regression_short"
    PAPER_LONG = "paper_long"


class BenchmarkMode(Enum):
    """
    Benchmark execution modes available to the subprocess worker.
    """

    STANDARD = "standard"
    COLD_WARM = "cold_warm"


def build_argument_parser() -> argparse.ArgumentParser:
    """
    Build the subprocess-worker argument parser.

    :return: Configured argument parser.
    :rtype: argparse.ArgumentParser
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="EMT subprocess benchmark worker")
    parser.add_argument("--case", required=True, choices=[item.value for item in BenchmarkCase])
    parser.add_argument("--profile", required=True, choices=[item.value for item in BenchmarkProfile])
    parser.add_argument("--mode", required=True, choices=[item.value for item in BenchmarkMode])
    parser.add_argument("--solver", required=True)
    return parser


def resolve_case_module(case_name: BenchmarkCase) -> Any:
    """
    Resolve the benchmark script module for one case.

    :param case_name: Benchmark case.
    :type case_name: BenchmarkCase
    :return: Script module.
    :rtype: Any
    """
    if case_name == BenchmarkCase.ZIPLOAD:
        import trunk.dynamics_emt.scripting_example_thevequiv_piline_ZIPload_emt as scripting_example_thevequiv_piline_ZIPload_emt

        return scripting_example_thevequiv_piline_ZIPload_emt
    elif case_name == BenchmarkCase.RLOAD:
        import trunk.dynamics_emt.scripting_example_thevequiv_piline_Rload_emt as scripting_example_thevequiv_piline_Rload_emt

        return scripting_example_thevequiv_piline_Rload_emt
    elif case_name == BenchmarkCase.EVENT:
        import trunk.dynamics_emt.scripting_emt_event as scripting_emt_event

        return scripting_emt_event
    else:
        import VeraGrid.trunk.dynamics_emt.scripting_example_validate_connections_emt_models as scripting_example_validate_connections_emt_models

        return scripting_example_validate_connections_emt_models


def configure_module_profile(module_obj: Any, profile: BenchmarkProfile) -> None:
    """
    Configure one benchmark module for the selected profile.

    :param module_obj: Benchmark script module.
    :type module_obj: Any
    :param profile: Benchmark profile.
    :type profile: BenchmarkProfile
    :return: None.
    :rtype: None
    """
    module_obj.SOLVER_VERBOSE = False

    if hasattr(module_obj, "ENABLE_NEWTON_TRACE"):
        module_obj.ENABLE_NEWTON_TRACE = False
    else:
        pass

    if profile == BenchmarkProfile.REGRESSION_SHORT:
        if case_name_is_event_module(module_obj):
            module_obj.options.time_step = 1e-3
            module_obj.options.simulation_time = 5e-2
        else:
            module_obj.options.time_step = 5e-5
            module_obj.options.simulation_time = 5e-4
    else:
        pass


def normalize_result_payload(raw_result: Any) -> Dict[str, object]:
    """
    Convert one script-specific benchmark result into a JSON-serializable row.

    :param raw_result: Script-specific benchmark result.
    :type raw_result: Any
    :return: JSON-serializable result row.
    :rtype: Dict[str, object]
    """
    if hasattr(raw_result, "get_solver_key") and hasattr(raw_result, "get_cold_trace_summary"):
        cold_trace_summary: Any = raw_result.get_cold_trace_summary()
        warm_trace_summary: Any = raw_result.get_warm_trace_summary()
        return dict(
            solver=str(raw_result.get_solver_key()),
            problem_build_s=float(raw_result.get_problem_build_s()),
            solver_init_s=float(raw_result.get_solver_init_s()),
            cold_build_s=float(raw_result.get_cold_build_s()),
            cold_sim_s=float(raw_result.get_cold_sim_s()),
            warm_sim_s=float(raw_result.get_warm_sim_s()),
            speedup=float(raw_result.get_speedup()),
            y_max_abs_diff=float(raw_result.get_y_max_abs_diff()),
            dy_max_abs_diff=float(raw_result.get_dy_max_abs_diff()),
            cold_final_residual_inf=float(cold_trace_summary.get_final_residual_inf()),
            warm_final_residual_inf=float(warm_trace_summary.get_final_residual_inf()),
            cold_maximum_residual_inf=float(cold_trace_summary.get_maximum_residual_inf()),
            warm_maximum_residual_inf=float(warm_trace_summary.get_maximum_residual_inf()),
            cold_total_newton_iterations=int(cold_trace_summary.get_total_newton_iterations()),
            warm_total_newton_iterations=int(warm_trace_summary.get_total_newton_iterations()),
            cold_last_step_newton_iterations=int(cold_trace_summary.get_last_step_newton_iterations()),
            warm_last_step_newton_iterations=int(warm_trace_summary.get_last_step_newton_iterations()),
            build_stats=dict(raw_result.get_build_stats()),
        )
    elif hasattr(raw_result, "get_solver_key"):
        trace_summary: Any = raw_result.get_trace_summary()
        return dict(
            solver=str(raw_result.get_solver_key()),
            problem_build_s=float(raw_result.get_problem_build_s()),
            solver_init_s=float(raw_result.get_solver_init_s()),
            solver_build_s=float(raw_result.get_solver_build_s()),
            simulate_s=float(raw_result.get_simulate_s()),
            solver_total_s=float(raw_result.get_solver_total_s()),
            loop_s=float(raw_result.get_loop_s()),
            y_max_abs_diff=float(raw_result.get_y_max_abs_diff()),
            dy_max_abs_diff=float(raw_result.get_dy_max_abs_diff()),
            final_residual_inf=float(trace_summary.get_final_residual_inf()),
            maximum_residual_inf=float(trace_summary.get_maximum_residual_inf()),
            total_newton_iterations=int(trace_summary.get_total_newton_iterations()),
            last_step_newton_iterations=int(trace_summary.get_last_step_newton_iterations()),
            build_stats=dict(raw_result.get_build_stats()),
            steps=int(raw_result.get_steps()),
            y_shape=list(raw_result.get_y_shape()),
            dy_shape=list(raw_result.get_dy_shape()),
        )
    else:
        json_row: Dict[str, object] = dict(raw_result)

        if "y" in json_row:
            json_row.pop("y")
        else:
            pass

        return json_row


def case_name_is_event_module(module_obj: Any) -> bool:
    """
    Return whether one module object is the event benchmark script.

    :param module_obj: Benchmark script module.
    :type module_obj: Any
    :return: ``True`` when the module is the event benchmark script.
    :rtype: bool
    """
    return bool(str(getattr(module_obj, "__name__", "")).endswith("scripting_emt_event"))


def run_worker(case_name: BenchmarkCase, profile: BenchmarkProfile, mode: BenchmarkMode, solver_key: str) -> Dict[str, object]:
    """
    Run one benchmark payload inside the subprocess worker.

    :param case_name: Benchmark case.
    :type case_name: BenchmarkCase
    :param profile: Benchmark profile.
    :type profile: BenchmarkProfile
    :param mode: Benchmark mode.
    :type mode: BenchmarkMode
    :param solver_key: Solver identifier.
    :type solver_key: str
    :return: JSON-serializable benchmark row.
    :rtype: Dict[str, object]
    """
    module_obj: Any = resolve_case_module(case_name)
    configure_module_profile(module_obj, profile)

    if mode == BenchmarkMode.STANDARD:
        if case_name == BenchmarkCase.ZIPLOAD:
            raw_result = module_obj.run_single_solver_benchmark(solver_key, None, None)[0]
        else:
            raw_result = module_obj.run_single_solver_benchmark(solver_key, None)
    else:
        raw_result = module_obj.run_single_solver_cold_warm_benchmark(solver_key)

    return normalize_result_payload(raw_result)


def main() -> None:
    """
    Execute the subprocess benchmark worker.

    :return: None.
    :rtype: None
    """
    parser: argparse.ArgumentParser = build_argument_parser()
    args: argparse.Namespace = parser.parse_args()
    case_name: BenchmarkCase = BenchmarkCase(args.case)
    profile: BenchmarkProfile = BenchmarkProfile(args.profile)
    mode: BenchmarkMode = BenchmarkMode(args.mode)
    stdout_buffer: io.StringIO = io.StringIO()
    stderr_buffer: io.StringIO = io.StringIO()

    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        payload: Dict[str, object] = run_worker(case_name, profile, mode, args.solver)

    print(json.dumps(payload))


if __name__ == "__main__":
    main()
