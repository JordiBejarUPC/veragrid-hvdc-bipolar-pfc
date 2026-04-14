import argparse
import contextlib
import io
import json
import time
from enum import Enum
from typing import Any, List, Sequence, Tuple

from trunk.dynamics_emt.support.benchmark_dependency_stubs import install_optional_dependency_stubs

install_optional_dependency_stubs()

from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import (
    StructuralCompiledEquationGroup,
    _build_full_residual_equations,
    _build_parameter_uid_set,
    _safe_njit,
    _build_backend_cache_token,
    canonicalize_expression,
    _get_runtime_uid,
)
from VeraGridEngine.Utils.Symbolic.jit_compiler import EagerEquationCompiler
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class CompilerBenchmarkCase(Enum):
    """
    Benchmark cases supported by the JIT compiler microbenchmark worker.
    """

    ZIPLOAD = "zipload"
    RLOAD = "rload"
    EVENT = "event"
    VALIDATE = "validate"


class CompilerBenchmarkTarget:
    """
    Structural benchmark target extracted from one EMT problem.
    """

    __slots__ = ["_case_name", "_equations", "_variables", "_parameters", "_group_keys", "_groups", "_method"]

    def __init__(
            self,
            case_name: str,
            equations: List[Expr],
            variables: List[Var],
            parameters: List[Var],
            group_keys: List[str],
            groups: List[StructuralCompiledEquationGroup],
            method: DynamicIntegrationMethod,
    ) -> None:
        """
        Build one compiler benchmark target.

        :param case_name: Benchmark case identifier.
        :type case_name: str
        :param equations: Full residual equations.
        :type equations: List[Expr]
        :param variables: Runtime variables.
        :type variables: List[Var]
        :param parameters: Full parameter list.
        :type parameters: List[Var]
        :param group_keys: Structural group signatures.
        :type group_keys: List[str]
        :param groups: Structural group containers.
        :type groups: List[StructuralCompiledEquationGroup]
        :param method: Integration method.
        :type method: DynamicIntegrationMethod
        :return: None.
        :rtype: None
        """
        self._case_name: str = case_name
        self._equations: List[Expr] = list(equations)
        self._variables: List[Var] = list(variables)
        self._parameters: List[Var] = list(parameters)
        self._group_keys: List[str] = list(group_keys)
        self._groups: List[StructuralCompiledEquationGroup] = list(groups)
        self._method: DynamicIntegrationMethod = method

    def get_case_name(self) -> str:
        """
        Return the benchmark case identifier.

        :return: Benchmark case identifier.
        :rtype: str
        """
        return self._case_name

    def get_equations(self) -> List[Expr]:
        """
        Return the full residual equations.

        :return: Full residual equations.
        :rtype: List[Expr]
        """
        return list(self._equations)

    def get_variables(self) -> List[Var]:
        """
        Return the runtime variables.

        :return: Runtime variables.
        :rtype: List[Var]
        """
        return list(self._variables)

    def get_parameters(self) -> List[Var]:
        """
        Return the full parameter list.

        :return: Full parameter list.
        :rtype: List[Var]
        """
        return list(self._parameters)

    def get_group_keys(self) -> List[str]:
        """
        Return the structural group signatures.

        :return: Structural group signatures.
        :rtype: List[str]
        """
        return list(self._group_keys)

    def get_groups(self) -> List[StructuralCompiledEquationGroup]:
        """
        Return the structural groups.

        :return: Structural groups.
        :rtype: List[StructuralCompiledEquationGroup]
        """
        return list(self._groups)

    def get_method(self) -> DynamicIntegrationMethod:
        """
        Return the integration method.

        :return: Integration method.
        :rtype: DynamicIntegrationMethod
        """
        return self._method


def build_argument_parser() -> argparse.ArgumentParser:
    """
    Build the subprocess-worker argument parser.

    :return: Configured argument parser.
    :rtype: argparse.ArgumentParser
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="EMT JIT compiler microbenchmark worker")
    parser.add_argument("--case", required=True, choices=[item.value for item in CompilerBenchmarkCase])
    return parser


def resolve_case_module(case_name: CompilerBenchmarkCase) -> Any:
    """
    Resolve the benchmark script module for one case.

    :param case_name: Benchmark case.
    :type case_name: CompilerBenchmarkCase
    :return: Script module.
    :rtype: Any
    """
    if case_name == CompilerBenchmarkCase.ZIPLOAD:
        import trunk.dynamics_emt.scripting_example_thevequiv_piline_ZIPload_emt as module_obj

        return module_obj
    elif case_name == CompilerBenchmarkCase.RLOAD:
        import trunk.dynamics_emt.scripting_example_thevequiv_piline_Rload_emt as module_obj

        return module_obj
    elif case_name == CompilerBenchmarkCase.EVENT:
        import trunk.dynamics_emt.scripting_emt_event as module_obj

        return module_obj
    else:
        import VeraGrid.trunk.dynamics_emt.scripting_example_validate_connections_emt_models as module_obj

        return module_obj


def build_problem_from_case(case_name: CompilerBenchmarkCase) -> Any:
    """
    Build the EMT problem corresponding to one compiler benchmark case.

    :param case_name: Benchmark case.
    :type case_name: CompilerBenchmarkCase
    :return: EMT problem instance.
    :rtype: Any
    """
    module_obj: Any = resolve_case_module(case_name)

    if case_name == CompilerBenchmarkCase.ZIPLOAD:
        return module_obj.create_problem(enable_trace=False)
    else:
        return module_obj.create_problem()


def build_compiler_benchmark_target(case_name: CompilerBenchmarkCase) -> CompilerBenchmarkTarget:
    """
    Extract the structural target used by the compiled backend from one EMT problem.

    :param case_name: Benchmark case.
    :type case_name: CompilerBenchmarkCase
    :return: Compiler benchmark target.
    :rtype: CompilerBenchmarkTarget
    """
    problem: Any = build_problem_from_case(case_name)
    state_vars: List[Var] = problem.get_state_vars()
    algebraic_vars: List[Var] = problem.get_algebraic_vars()
    state_eqs: List[Expr] = problem.get_state_eqs()
    algebraic_eqs: List[Expr] = problem.get_algebraic_eqs()
    event_parameters: List[Var] = problem.get_variable_parameters()
    constant_parameters: List[Var] = problem.get_constant_parameters()
    variables: List[Var] = list()
    parameters: List[Var] = list()
    uid_to_index: dict[int, int] = dict()
    runtime_uids: set[int] = set()
    parameter_uids: set[int] = _build_parameter_uid_set(event_parameters, constant_parameters)
    equations: List[Expr] = _build_full_residual_equations(state_vars, state_eqs, algebraic_eqs)
    groups_by_key: dict[str, StructuralCompiledEquationGroup] = dict()
    equation_index: int = 0
    method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal

    variables.extend(state_vars)
    variables.extend(algebraic_vars)
    parameters.extend(event_parameters)
    parameters.extend(constant_parameters)

    while equation_index < len(variables):
        uid_to_index[variables[equation_index].uid] = equation_index
        runtime_uids.add(variables[equation_index].uid)
        equation_index += 1

    equation_index = 0
    while equation_index < len(equations):
        equation: Expr = equations[equation_index]
        signature_str: str
        runtime_vars: List[Var]
        variable_indices: List[int] = list()
        runtime_var_index: int = 0

        signature_str, runtime_vars = canonicalize_expression(equation, runtime_uids, parameter_uids)

        if signature_str in groups_by_key:
            group: StructuralCompiledEquationGroup = groups_by_key[signature_str]
        else:
            group = StructuralCompiledEquationGroup()
            groups_by_key[signature_str] = group
        if group.get_template_eq() is None:
            group.set_template(equation, runtime_vars)
        else:
            pass

        while runtime_var_index < len(runtime_vars):
            variable_indices.append(uid_to_index[_get_runtime_uid(runtime_vars[runtime_var_index])])
            runtime_var_index += 1

        group.add_indices(variable_indices, equation_index)
        equation_index += 1

    group_keys: List[str] = sorted(list(groups_by_key.keys()))
    groups: List[StructuralCompiledEquationGroup] = list()
    equation_index = 0

    while equation_index < len(group_keys):
        groups.append(groups_by_key[group_keys[equation_index]])
        equation_index += 1

    return CompilerBenchmarkTarget(
        case_name=case_name.value,
        equations=equations,
        variables=variables,
        parameters=parameters,
        group_keys=group_keys,
        groups=groups,
        method=method,
    )


def measure_residual_compile(target: CompilerBenchmarkTarget, use_cse: bool) -> Tuple[float, float, float, float]:
    """
    Measure residual source generation and eager machine compilation.

    :param target: Compiler benchmark target.
    :type target: CompilerBenchmarkTarget
    :param use_cse: Whether residual CSE is enabled.
    :type use_cse: bool
    :return: Tuple ``(first_source_s, first_njit_s, cached_source_s, cached_njit_s)``.
    :rtype: Tuple[float, float, float, float]
    """
    compiler: EagerEquationCompiler = EagerEquationCompiler(
        variables=target.get_variables(),
        parameters=target.get_parameters(),
        method=target.get_method(),
    )
    cache_token: str = _build_backend_cache_token(
        target.get_method(),
        len(target.get_equations()),
        len(target.get_variables()),
        target.get_group_keys(),
    )
    func_name: str = f"jit_compiler_residual_bench_{target.get_case_name()}_{'cse' if use_cse else 'nocse'}_{cache_token}"
    py_func: Any
    signature_tpe: Any
    first_source_t0: float = time.perf_counter()
    py_func, signature_tpe = compiler.compile(
        equations=target.get_equations(),
        func_name=func_name,
        use_cse=use_cse,
        offset=0,
        inplace=True,
    )
    first_source_s: float = time.perf_counter() - first_source_t0
    first_njit_t0: float = time.perf_counter()
    _compiled_kernel: Any = _safe_njit(py_func, signature_tpe=signature_tpe, fastmath=True, cache=True)
    first_njit_s: float = time.perf_counter() - first_njit_t0

    cached_source_t0: float = time.perf_counter()
    py_func_cached, signature_tpe_cached = compiler.compile(
        equations=target.get_equations(),
        func_name=func_name,
        use_cse=use_cse,
        offset=0,
        inplace=True,
    )
    cached_source_s: float = time.perf_counter() - cached_source_t0
    cached_njit_t0: float = time.perf_counter()
    _compiled_kernel_cached: Any = _safe_njit(py_func_cached, signature_tpe=signature_tpe_cached, fastmath=True, cache=True)
    cached_njit_s: float = time.perf_counter() - cached_njit_t0
    return first_source_s, first_njit_s, cached_source_s, cached_njit_s


def measure_ad_compile(target: CompilerBenchmarkTarget, use_cse: bool) -> Tuple[float, float, float, float]:
    """
    Measure AD source generation and eager machine compilation.

    :param target: Compiler benchmark target.
    :type target: CompilerBenchmarkTarget
    :param use_cse: Whether AD CSE is enabled.
    :type use_cse: bool
    :return: Tuple ``(first_source_s, first_njit_s, cached_source_s, cached_njit_s)``.
    :rtype: Tuple[float, float, float, float]
    """
    compiler: EagerEquationCompiler = EagerEquationCompiler(
        variables=target.get_variables(),
        parameters=target.get_parameters(),
        method=target.get_method(),
    )
    cache_token: str = _build_backend_cache_token(
        target.get_method(),
        len(target.get_equations()),
        len(target.get_variables()),
        target.get_group_keys(),
    )
    func_name: str = f"jit_compiler_ad_bench_{target.get_case_name()}_{'cse' if use_cse else 'nocse'}_{cache_token}"
    py_func: Any
    signature_tpe: Any
    first_source_t0: float = time.perf_counter()
    py_func, signature_tpe = compiler.compile_ad_kernel(
        equations=target.get_equations(),
        func_name=func_name,
        use_cse=use_cse,
        active_indices=None,
    )
    first_source_s: float = time.perf_counter() - first_source_t0
    first_njit_t0: float = time.perf_counter()
    _compiled_kernel: Any = _safe_njit(py_func, signature_tpe=signature_tpe, fastmath=True, cache=True)
    first_njit_s: float = time.perf_counter() - first_njit_t0

    cached_source_t0: float = time.perf_counter()
    py_func_cached, signature_tpe_cached = compiler.compile_ad_kernel(
        equations=target.get_equations(),
        func_name=func_name,
        use_cse=use_cse,
        active_indices=None,
    )
    cached_source_s: float = time.perf_counter() - cached_source_t0
    cached_njit_t0: float = time.perf_counter()
    _compiled_kernel_cached: Any = _safe_njit(py_func_cached, signature_tpe=signature_tpe_cached, fastmath=True, cache=True)
    cached_njit_s: float = time.perf_counter() - cached_njit_t0
    return first_source_s, first_njit_s, cached_source_s, cached_njit_s


def measure_matrix_group_compile(target: CompilerBenchmarkTarget) -> Tuple[float, float, float, float, int, float]:
    """
    Measure grouped matrix-kernel generation and eager machine compilation.

    :param target: Compiler benchmark target.
    :type target: CompilerBenchmarkTarget
    :return: Tuple ``(first_source_s, first_njit_s, cached_source_s, cached_njit_s, group_count, avg_group_rows)``.
    :rtype: Tuple[float, float, float, float, int, float]
    """
    compiler: EagerEquationCompiler = EagerEquationCompiler(
        variables=target.get_variables(),
        parameters=target.get_parameters(),
        method=target.get_method(),
    )
    cache_token: str = _build_backend_cache_token(
        target.get_method(),
        len(target.get_equations()),
        len(target.get_variables()),
        target.get_group_keys(),
    )
    first_source_s: float = 0.0
    first_njit_s: float = 0.0
    cached_source_s: float = 0.0
    cached_njit_s: float = 0.0
    group_count: int = len(target.get_groups())
    total_group_rows: int = 0
    group_index: int = 0
    groups: List[StructuralCompiledEquationGroup] = target.get_groups()

    while group_index < len(groups):
        group: StructuralCompiledEquationGroup = groups[group_index]
        template_eq: Expr | None = group.get_template_eq()
        template_vars: List[Var] | None = group.get_template_vars()

        if template_eq is None or template_vars is None:
            raise RuntimeError("Invalid structural group without template information")
        else:
            pass

        func_name: str = f"jit_compiler_matrix_bench_{target.get_case_name()}_{group_index}_{cache_token}"
        py_func: Any
        signature_tpe: Any
        first_source_t0: float = time.perf_counter()
        py_func, signature_tpe = compiler.compile_matrix_kernel(
            template_eq=template_eq,
            func_name=func_name,
            template_vars=template_vars,
        )
        first_source_s += time.perf_counter() - first_source_t0
        first_njit_t0: float = time.perf_counter()
        _compiled_kernel: Any = _safe_njit(py_func, signature_tpe=signature_tpe, fastmath=True, cache=True)
        first_njit_s += time.perf_counter() - first_njit_t0

        cached_source_t0: float = time.perf_counter()
        py_func_cached, signature_tpe_cached = compiler.compile_matrix_kernel(
            template_eq=template_eq,
            func_name=func_name,
            template_vars=template_vars,
        )
        cached_source_s += time.perf_counter() - cached_source_t0
        cached_njit_t0: float = time.perf_counter()
        _compiled_kernel_cached: Any = _safe_njit(py_func_cached, signature_tpe=signature_tpe_cached, fastmath=True, cache=True)
        cached_njit_s += time.perf_counter() - cached_njit_t0
        total_group_rows += len(group.get_row_indices())
        group_index += 1

    if group_count > 0:
        avg_group_rows: float = float(total_group_rows) / float(group_count)
    else:
        avg_group_rows = 0.0

    return first_source_s, first_njit_s, cached_source_s, cached_njit_s, group_count, avg_group_rows


def run_microbenchmark(case_name: CompilerBenchmarkCase) -> dict[str, object]:
    """
    Run the compiler microbenchmark for one EMT case.

    :param case_name: Benchmark case.
    :type case_name: CompilerBenchmarkCase
    :return: JSON-serializable benchmark payload.
    :rtype: dict[str, object]
    """
    target: CompilerBenchmarkTarget = build_compiler_benchmark_target(case_name)
    residual_cse_on: Tuple[float, float, float, float] = measure_residual_compile(target, True)
    residual_cse_off: Tuple[float, float, float, float] = measure_residual_compile(target, False)
    ad_cse_on: Tuple[float, float, float, float] = measure_ad_compile(target, True)
    ad_cse_off: Tuple[float, float, float, float] = measure_ad_compile(target, False)
    matrix_group_metrics: Tuple[float, float, float, float, int, float] = measure_matrix_group_compile(target)

    return dict(
        case=case_name.value,
        equation_count=len(target.get_equations()),
        variable_count=len(target.get_variables()),
        parameter_count=len(target.get_parameters()),
        structural_group_count=matrix_group_metrics[4],
        average_group_rows=matrix_group_metrics[5],
        residual_source_cse_on_s=residual_cse_on[0],
        residual_njit_cse_on_s=residual_cse_on[1],
        residual_cached_source_cse_on_s=residual_cse_on[2],
        residual_cached_njit_cse_on_s=residual_cse_on[3],
        residual_source_cse_off_s=residual_cse_off[0],
        residual_njit_cse_off_s=residual_cse_off[1],
        residual_cached_source_cse_off_s=residual_cse_off[2],
        residual_cached_njit_cse_off_s=residual_cse_off[3],
        ad_source_cse_on_s=ad_cse_on[0],
        ad_njit_cse_on_s=ad_cse_on[1],
        ad_cached_source_cse_on_s=ad_cse_on[2],
        ad_cached_njit_cse_on_s=ad_cse_on[3],
        ad_source_cse_off_s=ad_cse_off[0],
        ad_njit_cse_off_s=ad_cse_off[1],
        ad_cached_source_cse_off_s=ad_cse_off[2],
        ad_cached_njit_cse_off_s=ad_cse_off[3],
        matrix_source_total_s=matrix_group_metrics[0],
        matrix_njit_total_s=matrix_group_metrics[1],
        matrix_cached_source_total_s=matrix_group_metrics[2],
        matrix_cached_njit_total_s=matrix_group_metrics[3],
    )


def main() -> None:
    """
    Execute the compiler microbenchmark worker.

    :return: None.
    :rtype: None
    """
    parser: argparse.ArgumentParser = build_argument_parser()
    args: argparse.Namespace = parser.parse_args()
    case_name: CompilerBenchmarkCase = CompilerBenchmarkCase(args.case)
    stdout_buffer: io.StringIO = io.StringIO()
    stderr_buffer: io.StringIO = io.StringIO()

    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        payload: dict[str, object] = run_microbenchmark(case_name)

    print(json.dumps(payload))


if __name__ == "__main__":
    main()
