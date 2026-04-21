from __future__ import annotations

from typing import Any, Dict


def normalize_problem_build_report(problem: Any) -> Dict[str, float]:
    """
    Return the EMT problem build report as a plain float dictionary.

    :param problem: EMT problem instance.
    :type problem: Any
    :return: Normalized problem build report.
    :rtype: Dict[str, float]
    """
    if hasattr(problem, "get_build_report"):
        raw_report: Any = problem.get_build_report()
    else:
        raw_report = dict()

    normalized_report: Dict[str, float] = dict()

    if isinstance(raw_report, dict):
        for key, value in raw_report.items():
            normalized_report[str(key)] = float(value)
    else:
        normalized_report = normalized_report

    return normalized_report


def normalize_initialization_report(problem: Any) -> Dict[str, object]:
    """
    Return the EMT initialization report as a plain JSON-serializable dictionary.

    :param problem: EMT problem instance.
    :type problem: Any
    :return: Normalized initialization report.
    :rtype: Dict[str, object]
    """
    report_obj: Any = getattr(problem, "initialization_report", None)

    if report_obj is None:
        return dict()
    else:
        pass

    return dict(
        status=str(report_obj.status.name),
        method_requested=str(report_obj.method_requested.name),
        method_used=str(report_obj.method_used.name),
        initial_residual_inf=float(report_obj.initial_residual_inf),
        final_residual_inf=float(report_obj.final_residual_inf),
        newton_iterations=int(report_obj.newton_iterations),
        pseudo_transient_steps=int(report_obj.pseudo_transient_steps),
        unknown_var_count=int(report_obj.unknown_var_count),
        unresolved_state_count=int(report_obj.unresolved_state_count),
        automatic_dx0_count=int(report_obj.automatic_dx0_count),
        reduced_system_build_s=float(report_obj.reduced_system_build_s),
        runtime_param_build_s=float(report_obj.runtime_param_build_s),
        constant_param_build_s=float(report_obj.constant_param_build_s),
        initial_residual_eval_s=float(report_obj.initial_residual_eval_s),
        newton_elapsed_s=float(report_obj.newton_elapsed_s),
        pseudo_transient_elapsed_s=float(report_obj.pseudo_transient_elapsed_s),
        dx0_completion_s=float(report_obj.dx0_completion_s),
        x0_rebuild_s=float(report_obj.x0_rebuild_s),
        dx0_seed_build_s=float(report_obj.dx0_seed_build_s),
        state_rhs_vector_build_s=float(report_obj.state_rhs_vector_build_s),
        state_rhs_vector_cache_hit=bool(report_obj.state_rhs_vector_cache_hit),
        solution_apply_s=float(report_obj.solution_apply_s),
        missing_dx_problem_collect_s=float(report_obj.missing_dx_problem_collect_s),
        state_rhs_eval_s=float(report_obj.state_rhs_eval_s),
        missing_dx_scatter_s=float(report_obj.missing_dx_scatter_s),
        persistent_cache_hit=bool(report_obj.persistent_cache_hit),
        persistent_cache_load_s=float(report_obj.persistent_cache_load_s),
        persistent_cache_store_s=float(report_obj.persistent_cache_store_s),
        elapsed_s=float(report_obj.elapsed_s),
        message=str(report_obj.message),
    )
