import math
import json
import sys
import types
import unittest
from pathlib import Path
from typing import Dict, List, Sequence, Tuple, Union

import matplotlib
import numpy as np


def install_optional_dependency_stubs() -> None:
    """
    Install lightweight stubs for optional third-party dependencies.

    :return: None.
    :rtype: None
    """
    if "sklearn" not in sys.modules:
        sklearn_module = types.ModuleType("sklearn")
        ensemble_module = types.ModuleType("sklearn.ensemble")
        cluster_module = types.ModuleType("sklearn.cluster")
        preprocessing_module = types.ModuleType("sklearn.preprocessing")
        neighbors_module = types.ModuleType("sklearn.neighbors")

        # The EMT benchmark scripts do not execute the stochastic or clustering
        # workflows during these tests. The placeholders only need to satisfy the
        # import graph reached through package-level initializers.
        class RandomForestRegressor:
            pass

        class DBSCAN:
            pass

        class Normalizer:
            pass

        class KNeighborsRegressor:
            pass

        class KMeans:
            pass

        class SpectralClustering:
            pass

        ensemble_module.RandomForestRegressor = RandomForestRegressor
        cluster_module.DBSCAN = DBSCAN
        cluster_module.KMeans = KMeans
        cluster_module.SpectralClustering = SpectralClustering
        preprocessing_module.Normalizer = Normalizer
        neighbors_module.KNeighborsRegressor = KNeighborsRegressor

        sklearn_module.ensemble = ensemble_module
        sklearn_module.cluster = cluster_module
        sklearn_module.preprocessing = preprocessing_module
        sklearn_module.neighbors = neighbors_module

        sys.modules["sklearn"] = sklearn_module
        sys.modules["sklearn.ensemble"] = ensemble_module
        sys.modules["sklearn.cluster"] = cluster_module
        sys.modules["sklearn.preprocessing"] = preprocessing_module
        sys.modules["sklearn.neighbors"] = neighbors_module
    else:
        pass

    if "chardet" not in sys.modules:
        chardet_module = types.ModuleType("chardet")

        def detect(_data: bytes) -> Dict[str, object]:
            return {"encoding": "utf-8", "confidence": 1.0}

        chardet_module.detect = detect
        sys.modules["chardet"] = chardet_module
    else:
        pass

    if "pyproj" not in sys.modules:
        pyproj_module = types.ModuleType("pyproj")

        class _DummyTransformer:
            @staticmethod
            def from_crs(_src: object, _dst: object, always_xy: bool = False) -> "_DummyTransformer":
                _unused: bool = always_xy
                return _DummyTransformer()

            def transform(self, xx: float, yy: float) -> Tuple[float, float]:
                return float(xx), float(yy)

        pyproj_module.Transformer = _DummyTransformer
        sys.modules["pyproj"] = pyproj_module
    else:
        pass

    if "pulp" not in sys.modules:
        pulp_module = types.ModuleType("pulp")

        class _DummyLpVariable:
            def __init__(self, *args: object, **kwargs: object) -> None:
                _unused_args: Tuple[object, ...] = args
                _unused_kwargs: Dict[str, object] = dict(kwargs)
                self.upBound: object = None
                self.lowBound: object = None

            def value(self) -> float:
                return 0.0

        class _DummyLpConstraint:
            def __init__(self) -> None:
                self.pi: float = 0.0

        class _DummyLpAffineExpression:
            def value(self) -> float:
                return 0.0

        class _DummyLpProblem:
            def __init__(self, *args: object, **kwargs: object) -> None:
                _unused_args: Tuple[object, ...] = args
                _unused_kwargs: Dict[str, object] = dict(kwargs)

            def addVariable(self, _var: object) -> None:
                return None

            def addConstraint(self, constraint: object, name: str = "") -> None:
                _unused_constraint: object = constraint
                _unused_name: str = name
                return None

            def setObjective(self, obj: object) -> None:
                _unused_obj: object = obj
                return None

        class _DummySolver:
            def __init__(self, *args: object, **kwargs: object) -> None:
                _unused_args: Tuple[object, ...] = args
                _unused_kwargs: Dict[str, object] = dict(kwargs)

        def _list_solvers(onlyAvailable: bool = True) -> List[str]:
            _unused: bool = onlyAvailable
            return list()

        def _lp_sum(_items: object) -> float:
            return 0.0

        pulp_module.LpVariable = _DummyLpVariable
        pulp_module.LpConstraint = _DummyLpConstraint
        pulp_module.LpAffineExpression = _DummyLpAffineExpression
        pulp_module.HiGHS = _DummySolver
        pulp_module.CPLEX_CMD = _DummySolver
        pulp_module.LpContinuous = "Continuous"
        pulp_module.LpInteger = "Integer"
        pulp_module.LpStatusOptimal = 1
        pulp_module.LpProblem = _DummyLpProblem
        pulp_module.LpMinimize = 1
        pulp_module.listSolvers = _list_solvers
        pulp_module.lpSum = _lp_sum

        sys.modules["pulp"] = pulp_module
    else:
        pass

    if "pymoo" not in sys.modules:
        pymoo_module = types.ModuleType("pymoo")
        core_module = types.ModuleType("pymoo.core")
        core_problem_module = types.ModuleType("pymoo.core.problem")
        core_mixed_module = types.ModuleType("pymoo.core.mixed")
        core_sampling_module = types.ModuleType("pymoo.core.sampling")
        core_mutation_module = types.ModuleType("pymoo.core.mutation")
        core_variable_module = types.ModuleType("pymoo.core.variable")
        util_module = types.ModuleType("pymoo.util")
        util_ref_dirs_module = types.ModuleType("pymoo.util.ref_dirs")
        optimize_module = types.ModuleType("pymoo.optimize")
        algorithms_module = types.ModuleType("pymoo.algorithms")
        algorithms_moo_module = types.ModuleType("pymoo.algorithms.moo")
        algorithms_nsga2_module = types.ModuleType("pymoo.algorithms.moo.nsga2")
        algorithms_nsga3_module = types.ModuleType("pymoo.algorithms.moo.nsga3")
        operators_module = types.ModuleType("pymoo.operators")
        operators_crossover_module = types.ModuleType("pymoo.operators.crossover")
        operators_crossover_sbx_module = types.ModuleType("pymoo.operators.crossover.sbx")
        operators_repair_module = types.ModuleType("pymoo.operators.repair")
        operators_repair_rounding_module = types.ModuleType("pymoo.operators.repair.rounding")
        operators_sampling_module = types.ModuleType("pymoo.operators.sampling")
        operators_sampling_rnd_module = types.ModuleType("pymoo.operators.sampling.rnd")

        class ElementwiseProblem:
            pass

        class MixedVariableGA:
            pass

        class MixedVariableSampling:
            pass

        class Sampling:
            pass

        class Mutation:
            pass

        class Real:
            pass

        class Integer:
            pass

        class Choice:
            pass

        class Binary:
            pass

        class RankAndCrowding:
            pass

        class NSGA3:
            pass

        class SBX:
            pass

        class RoundingRepair:
            pass

        class IntegerRandomSampling:
            pass

        def get_reference_directions(*args: object, **kwargs: object) -> List[object]:
            _unused_args: Tuple[object, ...] = args
            _unused_kwargs: Dict[str, object] = dict(kwargs)
            return list()

        def minimize(*args: object, **kwargs: object) -> None:
            _unused_args: Tuple[object, ...] = args
            _unused_kwargs: Dict[str, object] = dict(kwargs)
            return None

        core_problem_module.ElementwiseProblem = ElementwiseProblem
        core_mixed_module.MixedVariableGA = MixedVariableGA
        core_mixed_module.MixedVariableSampling = MixedVariableSampling
        core_sampling_module.Sampling = Sampling
        core_mutation_module.Mutation = Mutation
        core_variable_module.Real = Real
        core_variable_module.Integer = Integer
        core_variable_module.Choice = Choice
        core_variable_module.Binary = Binary
        util_ref_dirs_module.get_reference_directions = get_reference_directions
        optimize_module.minimize = minimize
        algorithms_nsga2_module.RankAndCrowding = RankAndCrowding
        algorithms_nsga3_module.NSGA3 = NSGA3
        operators_crossover_sbx_module.SBX = SBX
        operators_repair_rounding_module.RoundingRepair = RoundingRepair
        operators_sampling_rnd_module.IntegerRandomSampling = IntegerRandomSampling

        pymoo_module.core = core_module
        pymoo_module.util = util_module
        pymoo_module.optimize = optimize_module
        pymoo_module.algorithms = algorithms_module
        pymoo_module.operators = operators_module

        sys.modules["pymoo"] = pymoo_module
        sys.modules["pymoo.core"] = core_module
        sys.modules["pymoo.core.problem"] = core_problem_module
        sys.modules["pymoo.core.mixed"] = core_mixed_module
        sys.modules["pymoo.core.sampling"] = core_sampling_module
        sys.modules["pymoo.core.mutation"] = core_mutation_module
        sys.modules["pymoo.core.variable"] = core_variable_module
        sys.modules["pymoo.util"] = util_module
        sys.modules["pymoo.util.ref_dirs"] = util_ref_dirs_module
        sys.modules["pymoo.optimize"] = optimize_module
        sys.modules["pymoo.algorithms"] = algorithms_module
        sys.modules["pymoo.algorithms.moo"] = algorithms_moo_module
        sys.modules["pymoo.algorithms.moo.nsga2"] = algorithms_nsga2_module
        sys.modules["pymoo.algorithms.moo.nsga3"] = algorithms_nsga3_module
        sys.modules["pymoo.operators"] = operators_module
        sys.modules["pymoo.operators.crossover"] = operators_crossover_module
        sys.modules["pymoo.operators.crossover.sbx"] = operators_crossover_sbx_module
        sys.modules["pymoo.operators.repair"] = operators_repair_module
        sys.modules["pymoo.operators.repair.rounding"] = operators_repair_rounding_module
        sys.modules["pymoo.operators.sampling"] = operators_sampling_module
        sys.modules["pymoo.operators.sampling.rnd"] = operators_sampling_rnd_module
    else:
        pass

    if "rdflib" not in sys.modules:
        rdflib_module = types.ModuleType("rdflib")
        rdflib_graph_module = types.ModuleType("rdflib.graph")
        rdflib_namespace_module = types.ModuleType("rdflib.namespace")

        class Graph:
            def __init__(self, *args: object, **kwargs: object) -> None:
                _unused_args: Tuple[object, ...] = args
                _unused_kwargs: Dict[str, object] = dict(kwargs)

        rdflib_module.OWL = object()
        rdflib_graph_module.Graph = Graph
        rdflib_namespace_module.RDF = object()
        rdflib_namespace_module.RDFS = object()

        sys.modules["rdflib"] = rdflib_module
        sys.modules["rdflib.graph"] = rdflib_graph_module
        sys.modules["rdflib.namespace"] = rdflib_namespace_module
    else:
        pass

    if "requests" not in sys.modules:
        requests_module = types.ModuleType("requests")

        class Response:
            def __init__(self) -> None:
                self.status_code: int = 200
                self.text: str = ""

            def json(self) -> Dict[str, object]:
                return dict()

        def get(*args: object, **kwargs: object) -> Response:
            _unused_args: Tuple[object, ...] = args
            _unused_kwargs: Dict[str, object] = dict(kwargs)
            return Response()

        def post(*args: object, **kwargs: object) -> Response:
            _unused_args: Tuple[object, ...] = args
            _unused_kwargs: Dict[str, object] = dict(kwargs)
            return Response()

        requests_module.Response = Response
        requests_module.get = get
        requests_module.post = post
        sys.modules["requests"] = requests_module
    else:
        pass


install_optional_dependency_stubs()

# The benchmark scripts import pyplot at module import time.
# The test suite fixes a non-interactive backend first so imports stay headless.
matplotlib.use("Agg")

import VeraGrid.trunk.dynamics_emt.scripting_emt_event as emt_event_script
import VeraGrid.trunk.dynamics_emt.emt_solver_benchmark_report as benchmark_report
import VeraGrid.trunk.dynamics_emt.emt_solver_process_benchmark as process_benchmark
import VeraGrid.trunk.dynamics_emt.scripting_example_thevequiv_piline_Rload_emt as rload_script
import VeraGrid.trunk.dynamics_emt.scripting_example_thevequiv_piline_ZIPload_emt as zipload_script
import VeraGrid.trunk.dynamics_emt.scripting_example_validate_connections_emt_models as validate_connections_script


RawBenchmarkRow = Union[Dict[str, object], zipload_script.SolverBenchmarkResult]


class BenchmarkRow:
    """
    Normalized view of one benchmark row collected from a dynamics EMT script.
    """

    __slots__ = [
        "_solver_key",
        "_problem_build_s",
        "_solver_init_s",
        "_solver_build_s",
        "_simulate_s",
        "_solver_total_s",
        "_loop_s",
        "_y_max_abs_diff",
        "_dy_max_abs_diff",
        "_steps",
        "_y_shape",
        "_dy_shape",
        "_build_stats",
        "_final_residual_inf",
    ]

    def __init__(
            self,
            solver_key: str,
            problem_build_s: float,
            solver_init_s: float,
            solver_build_s: float,
            simulate_s: float,
            solver_total_s: float,
            loop_s: float,
            y_max_abs_diff: float,
            dy_max_abs_diff: float,
            steps: int,
            y_shape: Tuple[int, ...],
            dy_shape: Tuple[int, ...],
            build_stats: Dict[str, float],
            final_residual_inf: float,
    ) -> None:
        """
        Build one normalized benchmark row.

        :param solver_key: Solver label.
        :type solver_key: str
        :param problem_build_s: Problem build time.
        :type problem_build_s: float
        :param solver_init_s: Solver construction time.
        :type solver_init_s: float
        :param solver_build_s: Backend build time.
        :type solver_build_s: float
        :param simulate_s: Simulation time.
        :type simulate_s: float
        :param solver_total_s: Total benchmark time.
        :type solver_total_s: float
        :param loop_s: Loop-only time when exposed.
        :type loop_s: float
        :param y_max_abs_diff: Maximum state difference against the reference.
        :type y_max_abs_diff: float
        :param dy_max_abs_diff: Maximum differential-state difference against the reference.
        :type dy_max_abs_diff: float
        :param steps: Number of accepted time steps.
        :type steps: int
        :param y_shape: Shape of the state trajectory array.
        :type y_shape: Tuple[int, ...]
        :param dy_shape: Shape of the differential trajectory array.
        :type dy_shape: Tuple[int, ...]
        :param build_stats: Backend build statistics.
        :type build_stats: Dict[str, float]
        :param final_residual_inf: Final residual infinity norm when exposed.
        :type final_residual_inf: float
        :return: None.
        :rtype: None
        """
        self._solver_key: str = solver_key
        self._problem_build_s: float = float(problem_build_s)
        self._solver_init_s: float = float(solver_init_s)
        self._solver_build_s: float = float(solver_build_s)
        self._simulate_s: float = float(simulate_s)
        self._solver_total_s: float = float(solver_total_s)
        self._loop_s: float = float(loop_s)
        self._y_max_abs_diff: float = float(y_max_abs_diff)
        self._dy_max_abs_diff: float = float(dy_max_abs_diff)
        self._steps: int = int(steps)
        self._y_shape: Tuple[int, ...] = tuple(y_shape)
        self._dy_shape: Tuple[int, ...] = tuple(dy_shape)
        self._build_stats: Dict[str, float] = dict(build_stats)
        self._final_residual_inf: float = float(final_residual_inf)

    def get_solver_key(self) -> str:
        """
        Return the solver label.

        :return: Solver label.
        :rtype: str
        """
        return self._solver_key

    def get_problem_build_s(self) -> float:
        """
        Return the problem build time.

        :return: Problem build time.
        :rtype: float
        """
        return self._problem_build_s

    def get_solver_init_s(self) -> float:
        """
        Return the solver construction time.

        :return: Solver construction time.
        :rtype: float
        """
        return self._solver_init_s

    def get_solver_build_s(self) -> float:
        """
        Return the backend build time.

        :return: Backend build time.
        :rtype: float
        """
        return self._solver_build_s

    def get_simulate_s(self) -> float:
        """
        Return the simulation time.

        :return: Simulation time.
        :rtype: float
        """
        return self._simulate_s

    def get_solver_total_s(self) -> float:
        """
        Return the total benchmark time.

        :return: Total benchmark time.
        :rtype: float
        """
        return self._solver_total_s

    def get_loop_s(self) -> float:
        """
        Return the loop-only time.

        :return: Loop-only time.
        :rtype: float
        """
        return self._loop_s

    def get_y_max_abs_diff(self) -> float:
        """
        Return the maximum state difference.

        :return: Maximum state difference.
        :rtype: float
        """
        return self._y_max_abs_diff

    def get_dy_max_abs_diff(self) -> float:
        """
        Return the maximum differential-state difference.

        :return: Maximum differential-state difference.
        :rtype: float
        """
        return self._dy_max_abs_diff

    def get_steps(self) -> int:
        """
        Return the number of accepted time steps.

        :return: Number of accepted time steps.
        :rtype: int
        """
        return self._steps

    def get_y_shape(self) -> Tuple[int, ...]:
        """
        Return the shape of the state trajectory matrix.

        :return: State trajectory shape.
        :rtype: Tuple[int, ...]
        """
        return self._y_shape

    def get_dy_shape(self) -> Tuple[int, ...]:
        """
        Return the shape of the differential trajectory matrix.

        :return: Differential trajectory shape.
        :rtype: Tuple[int, ...]
        """
        return self._dy_shape

    def get_build_stats(self) -> Dict[str, float]:
        """
        Return the backend build statistics.

        :return: Backend build statistics.
        :rtype: Dict[str, float]
        """
        return dict(self._build_stats)

    def get_final_residual_inf(self) -> float:
        """
        Return the final residual infinity norm.

        :return: Final residual infinity norm.
        :rtype: float
        """
        return self._final_residual_inf


class BenchmarkCaseExecution:
    """
    Typed container for one complete benchmark-script execution.
    """

    __slots__ = ["_case_name", "_rows"]

    def __init__(self, case_name: str, rows: Sequence[BenchmarkRow]) -> None:
        """
        Build one benchmark case execution.

        :param case_name: Human-readable case label.
        :type case_name: str
        :param rows: Normalized benchmark rows.
        :type rows: Sequence[BenchmarkRow]
        :return: None.
        :rtype: None
        """
        self._case_name: str = case_name
        self._rows: List[BenchmarkRow] = list(rows)

    def get_case_name(self) -> str:
        """
        Return the case label.

        :return: Case label.
        :rtype: str
        """
        return self._case_name

    def get_rows(self) -> List[BenchmarkRow]:
        """
        Return the normalized benchmark rows.

        :return: Normalized benchmark rows.
        :rtype: List[BenchmarkRow]
        """
        return list(self._rows)


class SolverTrajectoryBundle:
    """
    Cached solver trajectory for one real EMT script.
    """

    __slots__ = ["_problem", "_solver", "_time_values", "_y_values", "_dy_values"]

    def __init__(self, problem: object, solver: object, time_values: object, y_values: object, dy_values: object) -> None:
        """
        Build one cached solver trajectory bundle.

        :param problem: EMT problem instance.
        :type problem: object
        :param solver: Solver instance.
        :type solver: object
        :param time_values: Time vector.
        :type time_values: object
        :param y_values: State trajectory.
        :type y_values: object
        :param dy_values: Differential trajectory.
        :type dy_values: object
        :return: None.
        :rtype: None
        """
        self._problem = problem
        self._solver = solver
        self._time_values = time_values
        self._y_values = y_values
        self._dy_values = dy_values

    def get_problem(self) -> object:
        """
        Return the EMT problem instance.

        :return: EMT problem instance.
        :rtype: object
        """
        return self._problem

    def get_solver(self) -> object:
        """
        Return the solver instance.

        :return: Solver instance.
        :rtype: object
        """
        return self._solver

    def get_time_values(self) -> object:
        """
        Return the time vector.

        :return: Time vector.
        :rtype: object
        """
        return self._time_values

    def get_y_values(self) -> object:
        """
        Return the state trajectory.

        :return: State trajectory.
        :rtype: object
        """
        return self._y_values

    def get_dy_values(self) -> object:
        """
        Return the differential trajectory.

        :return: Differential trajectory.
        :rtype: object
        """
        return self._dy_values


class TemporalTraceSeries:
    """
    One temporal trace extracted from a solver trajectory.
    """

    __slots__ = ["_label", "_values", "_abs_tolerance"]

    def __init__(self, label: str, values: object, abs_tolerance: float) -> None:
        """
        Build one temporal trace series.

        :param label: Trace label.
        :type label: str
        :param values: Trace values.
        :type values: object
        :param abs_tolerance: Absolute tolerance.
        :type abs_tolerance: float
        :return: None.
        :rtype: None
        """
        self._label = label
        self._values = values
        self._abs_tolerance = float(abs_tolerance)

    def get_label(self) -> str:
        """
        Return the trace label.

        :return: Trace label.
        :rtype: str
        """
        return self._label

    def get_values(self) -> object:
        """
        Return the trace values.

        :return: Trace values.
        :rtype: object
        """
        return self._values

    def get_abs_tolerance(self) -> float:
        """
        Return the absolute tolerance.

        :return: Absolute tolerance.
        :rtype: float
        """
        return self._abs_tolerance


def _normalize_dict_row(raw_row: Dict[str, object]) -> BenchmarkRow:
    """
    Convert one dictionary-backed row into the normalized benchmark view.

    :param raw_row: Raw benchmark row.
    :type raw_row: Dict[str, object]
    :return: Normalized benchmark row.
    :rtype: BenchmarkRow
    """
    build_stats_any: object = raw_row["build_stats"]

    if isinstance(build_stats_any, dict):
        build_stats: Dict[str, float] = dict()

        for key, value in build_stats_any.items():
            build_stats[str(key)] = float(value)
    else:
        build_stats = dict()

    shape_any: object = raw_row["shape"]
    dy_shape_any: object = raw_row["dy_shape"]

    if isinstance(shape_any, tuple):
        y_shape: Tuple[int, ...] = tuple(int(value) for value in shape_any)
    else:
        raise TypeError("Expected tuple shape in benchmark row")

    if isinstance(dy_shape_any, tuple):
        dy_shape: Tuple[int, ...] = tuple(int(value) for value in dy_shape_any)
    else:
        raise TypeError("Expected tuple differential shape in benchmark row")

    return BenchmarkRow(
        solver_key=str(raw_row["solver"]),
        problem_build_s=float(raw_row["problem_build_s"]),
        solver_init_s=float(raw_row["solver_init_s"]),
        solver_build_s=float(raw_row["solver_build_s"]),
        simulate_s=float(raw_row["simulate_s"]),
        solver_total_s=float(raw_row["solver_total_s"]),
        loop_s=float(raw_row["loop_s"]),
        y_max_abs_diff=float(raw_row["max_abs_diff"]),
        dy_max_abs_diff=float(raw_row["max_abs_diff"]),
        steps=int(raw_row["steps"]),
        y_shape=y_shape,
        dy_shape=dy_shape,
        build_stats=build_stats,
        final_residual_inf=math.nan,
    )


def _normalize_zipload_row(raw_row: zipload_script.SolverBenchmarkResult) -> BenchmarkRow:
    """
    Convert one typed ZIP-load benchmark row into the normalized benchmark view.

    :param raw_row: Raw ZIP-load benchmark row.
    :type raw_row: zipload_script.SolverBenchmarkResult
    :return: Normalized benchmark row.
    :rtype: BenchmarkRow
    """
    trace_summary: zipload_script.SolverTraceSummary = raw_row.get_trace_summary()

    return BenchmarkRow(
        solver_key=raw_row.get_solver_key(),
        problem_build_s=raw_row.get_problem_build_s(),
        solver_init_s=raw_row.get_solver_init_s(),
        solver_build_s=raw_row.get_solver_build_s(),
        simulate_s=raw_row.get_simulate_s(),
        solver_total_s=raw_row.get_solver_total_s(),
        loop_s=raw_row.get_loop_s(),
        y_max_abs_diff=raw_row.get_y_max_abs_diff(),
        dy_max_abs_diff=raw_row.get_dy_max_abs_diff(),
        steps=int(raw_row._steps),
        y_shape=tuple(int(value) for value in raw_row._y_shape),
        dy_shape=tuple(int(value) for value in raw_row._dy_shape),
        build_stats=raw_row.get_build_stats(),
        final_residual_inf=trace_summary.get_final_residual_inf(),
    )


def normalize_benchmark_rows(raw_rows: Sequence[RawBenchmarkRow]) -> List[BenchmarkRow]:
    """
    Convert script-specific benchmark rows into one normalized representation.

    :param raw_rows: Script-specific benchmark rows.
    :type raw_rows: Sequence[RawBenchmarkRow]
    :return: Normalized benchmark rows.
    :rtype: List[BenchmarkRow]
    """
    normalized_rows: List[BenchmarkRow] = list()
    row_index: int = 0

    while row_index < len(raw_rows):
        raw_row: RawBenchmarkRow = raw_rows[row_index]

        if isinstance(raw_row, dict):
            normalized_rows.append(_normalize_dict_row(raw_row))
        elif isinstance(raw_row, zipload_script.SolverBenchmarkResult):
            normalized_rows.append(_normalize_zipload_row(raw_row))
        else:
            raise TypeError(f"Unsupported benchmark row type: {type(raw_row)}")

        row_index += 1

    return normalized_rows


def run_case(case_name: str, raw_rows: Sequence[RawBenchmarkRow]) -> BenchmarkCaseExecution:
    """
    Build one benchmark execution bundle from raw script rows.

    :param case_name: Human-readable case label.
    :type case_name: str
    :param raw_rows: Script-specific benchmark rows.
    :type raw_rows: Sequence[RawBenchmarkRow]
    :return: Normalized execution bundle.
    :rtype: BenchmarkCaseExecution
    """
    normalized_rows: List[BenchmarkRow] = normalize_benchmark_rows(raw_rows)
    return BenchmarkCaseExecution(case_name=case_name, rows=normalized_rows)


def build_solver_trajectory_bundle(problem: object, solver: object, time_values: object, y_values: object, dy_values: object) -> SolverTrajectoryBundle:
    """
    Build one cached solver trajectory bundle.

    :param problem: EMT problem instance.
    :type problem: object
    :param solver: Solver instance.
    :type solver: object
    :param time_values: Time vector.
    :type time_values: object
    :param y_values: State trajectory.
    :type y_values: object
    :param dy_values: Differential trajectory.
    :type dy_values: object
    :return: Cached solver trajectory bundle.
    :rtype: SolverTrajectoryBundle
    """
    return SolverTrajectoryBundle(problem=problem, solver=solver, time_values=time_values, y_values=y_values, dy_values=dy_values)


def run_zipload_trajectory_bundle(solver_key: str) -> SolverTrajectoryBundle:
    """
    Run one ZIP-load solver trajectory with the short regression configuration.

    :param solver_key: Solver identifier.
    :type solver_key: str
    :return: Cached solver trajectory bundle.
    :rtype: SolverTrajectoryBundle
    """
    problem, solver, time_values, y_values, dy_values = zipload_script.run_single_solver_trajectory(solver_key, False)
    return build_solver_trajectory_bundle(problem, solver, time_values, y_values, dy_values)


def run_rload_trajectory_bundle(solver_key: str) -> SolverTrajectoryBundle:
    """
    Run one R-load solver trajectory with the short regression configuration.

    :param solver_key: Solver identifier.
    :type solver_key: str
    :return: Cached solver trajectory bundle.
    :rtype: SolverTrajectoryBundle
    """
    problem, solver, time_values, y_values, dy_values = rload_script.run_single_solver_trajectory(solver_key, False)
    return build_solver_trajectory_bundle(problem, solver, time_values, y_values, dy_values)


def run_event_trajectory_bundle(solver_key: str) -> SolverTrajectoryBundle:
    """
    Run one event-case solver trajectory with the short regression configuration.

    :param solver_key: Solver identifier.
    :type solver_key: str
    :return: Cached solver trajectory bundle.
    :rtype: SolverTrajectoryBundle
    """
    problem, solver, time_values, y_values, dy_values = emt_event_script.run_single_solver_trajectory(solver_key, False)
    return build_solver_trajectory_bundle(problem, solver, time_values, y_values, dy_values)


def build_three_phase_trace(problem: object, y_values: np.ndarray, variable_triplet: Tuple[object, object, object]) -> np.ndarray:
    """
    Extract one three-phase trace matrix from a solver trajectory.

    :param problem: EMT problem instance.
    :type problem: object
    :param y_values: State trajectory.
    :type y_values: np.ndarray
    :param variable_triplet: Three symbolic variables.
    :type variable_triplet: Tuple[object, object, object]
    :return: Extracted three-phase trace matrix.
    :rtype: np.ndarray
    """
    matrix: np.ndarray = np.zeros((y_values.shape[0], 3), dtype=np.float64)
    phase_index: int = 0

    while phase_index < 3:
        matrix[:, phase_index] = y_values[:, problem.get_var_idx(variable_triplet[phase_index])]
        phase_index += 1

    return matrix


def build_zipload_temporal_series(bundle: SolverTrajectoryBundle) -> List[TemporalTraceSeries]:
    """
    Build the selected ZIP-load temporal traces used for cross-backend checks.

    :param bundle: Cached solver trajectory bundle.
    :type bundle: SolverTrajectoryBundle
    :return: Selected temporal traces.
    :rtype: List[TemporalTraceSeries]
    """
    problem = bundle.get_problem()
    y_values: np.ndarray = np.asarray(bundle.get_y_values(), dtype=np.float64)
    traces: List[TemporalTraceSeries] = list()
    traces.append(TemporalTraceSeries("bus0_voltages", build_three_phase_trace(problem, y_values, tuple(zipload_script.bus0.emt_model.out_vars)), 8.0e-2))
    traces.append(TemporalTraceSeries("bus1_voltages", build_three_phase_trace(problem, y_values, tuple(zipload_script.bus1.emt_model.out_vars)), 8.5e-2))
    traces.append(TemporalTraceSeries("generator_currents", build_three_phase_trace(problem, y_values, tuple(zipload_script.gen_mdl.out_vars)), 9.0e-2))
    traces.append(
        TemporalTraceSeries(
            "zip_load_currents",
            build_three_phase_trace(
                problem,
                y_values,
                (
                    zipload_script.find_name_in_block("i_A_ZIP_Load_EMT_3ph", zipload_script.load_mdl),
                    zipload_script.find_name_in_block("i_B_ZIP_Load_EMT_3ph", zipload_script.load_mdl),
                    zipload_script.find_name_in_block("i_C_ZIP_Load_EMT_3ph", zipload_script.load_mdl),
                ),
            ),
            9.0e-2,
        )
    )
    traces.append(
        TemporalTraceSeries(
            "generator_theta",
            y_values[:, problem.get_var_idx(zipload_script.find_name_in_block("theta_emt_thevenin_eq_generator_template", zipload_script.gen_mdl))],
            8.0e-2,
        )
    )
    return traces


def build_rload_temporal_series(bundle: SolverTrajectoryBundle) -> List[TemporalTraceSeries]:
    """
    Build the selected R-load temporal traces used for cross-backend checks.

    :param bundle: Cached solver trajectory bundle.
    :type bundle: SolverTrajectoryBundle
    :return: Selected temporal traces.
    :rtype: List[TemporalTraceSeries]
    """
    problem = bundle.get_problem()
    y_values: np.ndarray = np.asarray(bundle.get_y_values(), dtype=np.float64)
    traces: List[TemporalTraceSeries] = list()
    traces.append(TemporalTraceSeries("bus0_voltages", build_three_phase_trace(problem, y_values, tuple(rload_script.bus0.emt_model.out_vars)), 4.5e-2))
    traces.append(TemporalTraceSeries("bus1_voltages", build_three_phase_trace(problem, y_values, tuple(rload_script.bus1.emt_model.out_vars)), 4.5e-2))
    traces.append(TemporalTraceSeries("generator_currents", build_three_phase_trace(problem, y_values, tuple(rload_script.gen_mdl.out_vars)), 5.0e-2))
    traces.append(
        TemporalTraceSeries(
            "r_load_currents",
            build_three_phase_trace(
                problem,
                y_values,
                (
                    rload_script.find_name_in_block("i_A_Shunt_R_3ph", rload_script.load_mdl),
                    rload_script.find_name_in_block("i_B_Shunt_R_3ph", rload_script.load_mdl),
                    rload_script.find_name_in_block("i_C_Shunt_R_3ph", rload_script.load_mdl),
                ),
            ),
            5.0e-2,
        )
    )
    return traces


def build_event_temporal_series(bundle: SolverTrajectoryBundle) -> List[TemporalTraceSeries]:
    """
    Build the selected event-case temporal traces used for cross-backend checks.

    :param bundle: Cached solver trajectory bundle.
    :type bundle: SolverTrajectoryBundle
    :return: Selected temporal traces.
    :rtype: List[TemporalTraceSeries]
    """
    problem = bundle.get_problem()
    y_values: np.ndarray = np.asarray(bundle.get_y_values(), dtype=np.float64)
    traces: List[TemporalTraceSeries] = list()
    traces.append(TemporalTraceSeries("bus0_voltages", build_three_phase_trace(problem, y_values, tuple(emt_event_script.bus0.emt_model.out_vars)), 6.5e-2))
    traces.append(TemporalTraceSeries("bus1_voltages", build_three_phase_trace(problem, y_values, tuple(emt_event_script.bus1.emt_model.out_vars)), 6.5e-2))
    traces.append(TemporalTraceSeries("generator_currents", build_three_phase_trace(problem, y_values, tuple(emt_event_script.gen_mdl.out_vars)), 7.0e-2))
    traces.append(
        TemporalTraceSeries(
            "event_load_currents",
            build_three_phase_trace(
                problem,
                y_values,
                (
                    emt_event_script.find_name_in_block("i_A_Shunt_R_3ph", emt_event_script.load_mdl),
                    emt_event_script.find_name_in_block("i_B_Shunt_R_3ph", emt_event_script.load_mdl),
                    emt_event_script.find_name_in_block("i_C_Shunt_R_3ph", emt_event_script.load_mdl),
                ),
            ),
            7.0e-2,
        )
    )
    return traces


def assert_temporal_series_close(
        test_case: unittest.TestCase,
        reference_bundle: SolverTrajectoryBundle,
        candidate_bundle: SolverTrajectoryBundle,
        trace_builder: object,
        case_name: str,
        solver_key: str,
) -> None:
    """
    Assert that selected temporal traces remain close between two solvers.

    :param test_case: Active unittest instance.
    :type test_case: unittest.TestCase
    :param reference_bundle: Reference solver trajectory.
    :type reference_bundle: SolverTrajectoryBundle
    :param candidate_bundle: Candidate solver trajectory.
    :type candidate_bundle: SolverTrajectoryBundle
    :param trace_builder: Trace-builder function.
    :type trace_builder: object
    :param case_name: Human-readable case label.
    :type case_name: str
    :param solver_key: Candidate solver key.
    :type solver_key: str
    :return: None.
    :rtype: None
    """
    reference_time: np.ndarray = np.asarray(reference_bundle.get_time_values(), dtype=np.float64)
    candidate_time: np.ndarray = np.asarray(candidate_bundle.get_time_values(), dtype=np.float64)
    test_case.assertEqual(reference_time.shape, candidate_time.shape)
    test_case.assertLess(float(np.max(np.abs(reference_time - candidate_time))), 1.0e-14)

    reference_traces: List[TemporalTraceSeries] = trace_builder(reference_bundle)
    candidate_traces: List[TemporalTraceSeries] = trace_builder(candidate_bundle)
    trace_index: int = 0

    while trace_index < len(reference_traces):
        reference_trace: TemporalTraceSeries = reference_traces[trace_index]
        candidate_trace: TemporalTraceSeries = candidate_traces[trace_index]
        reference_values: np.ndarray = np.asarray(reference_trace.get_values(), dtype=np.float64)
        candidate_values: np.ndarray = np.asarray(candidate_trace.get_values(), dtype=np.float64)
        max_abs_diff: float = float(np.max(np.abs(reference_values - candidate_values)))

        with test_case.subTest(case=case_name, solver=solver_key, trace=reference_trace.get_label()):
            test_case.assertEqual(reference_trace.get_label(), candidate_trace.get_label())
            test_case.assertEqual(reference_values.shape, candidate_values.shape)
            test_case.assertLess(max_abs_diff, reference_trace.get_abs_tolerance())

        trace_index += 1


def configure_rload_script_for_tests() -> None:
    """
    Shrink the resistive-load demo horizon so it stays suitable for regression tests.

    :return: None.
    :rtype: None
    """
    rload_script.options.time_step = 5e-5
    rload_script.options.simulation_time = 5e-4
    rload_script.SOLVER_VERBOSE = False
    rload_script.ENABLE_NEWTON_TRACE = False


def configure_zipload_script_for_tests() -> None:
    """
    Shrink the ZIP-load demo horizon so it stays suitable for regression tests.

    :return: None.
    :rtype: None
    """
    zipload_script.options.time_step = 5e-5
    zipload_script.options.simulation_time = 5e-4
    zipload_script.SOLVER_VERBOSE = False
    zipload_script.ENABLE_NEWTON_TRACE = False


def configure_event_script_for_tests() -> None:
    """
    Shrink the event demo horizon and step count while still crossing both events.

    :return: None.
    :rtype: None
    """
    emt_event_script.options.time_step = 1e-3
    emt_event_script.options.simulation_time = 5e-2
    emt_event_script.SOLVER_VERBOSE = False
    emt_event_script.ENABLE_NEWTON_TRACE = False


def configure_validate_connections_script_for_tests() -> None:
    """
    Shrink the connection-validation demo horizon for the regression suite.

    :return: None.
    :rtype: None
    """
    validate_connections_script.options.time_step = 5e-5
    validate_connections_script.options.simulation_time = 5e-4
    validate_connections_script.SOLVER_VERBOSE = False
    validate_connections_script.ENABLE_NEWTON_TRACE = False


def assert_positive_time(test_case: unittest.TestCase, value: float, label: str) -> None:
    """
    Assert that one timing metric is finite and strictly positive.

    :param test_case: Active unittest instance.
    :type test_case: unittest.TestCase
    :param value: Timing value.
    :type value: float
    :param label: Human-readable metric name.
    :type label: str
    :return: None.
    :rtype: None
    """
    test_case.assertTrue(math.isfinite(value), msg=f"Expected finite {label}, got {value}")
    test_case.assertGreater(value, 0.0, msg=f"Expected positive {label}, got {value}")


def assert_common_case_contract(test_case: unittest.TestCase, execution: BenchmarkCaseExecution) -> None:
    """
    Validate the common benchmark contract shared by all selected scripts.

    :param test_case: Active unittest instance.
    :type test_case: unittest.TestCase
    :param execution: Benchmark execution bundle.
    :type execution: BenchmarkCaseExecution
    :return: None.
    :rtype: None
    """
    rows: List[BenchmarkRow] = execution.get_rows()
    expected_solver_order: Tuple[str, ...] = ("SYMBOLIC", "AD", "VECTORIZED", "COMPILED")

    # The case must benchmark all four research backends in a stable order.
    test_case.assertEqual(len(rows), len(expected_solver_order))
    test_case.assertEqual(tuple(row.get_solver_key() for row in rows), expected_solver_order)

    # All rows must describe the same time horizon and state-space dimensions.
    reference_steps: int = rows[0].get_steps()
    reference_y_shape: Tuple[int, ...] = rows[0].get_y_shape()
    reference_dy_shape: Tuple[int, ...] = rows[0].get_dy_shape()

    row_index: int = 0
    while row_index < len(rows):
        row: BenchmarkRow = rows[row_index]

        assert_positive_time(test_case, row.get_problem_build_s(), f"{execution.get_case_name()} problem_build_s")
        assert_positive_time(test_case, row.get_solver_init_s(), f"{execution.get_case_name()} solver_init_s")
        assert_positive_time(test_case, row.get_solver_build_s(), f"{execution.get_case_name()} solver_build_s")
        assert_positive_time(test_case, row.get_simulate_s(), f"{execution.get_case_name()} simulate_s")
        assert_positive_time(test_case, row.get_solver_total_s(), f"{execution.get_case_name()} solver_total_s")

        test_case.assertEqual(row.get_steps(), reference_steps)
        test_case.assertEqual(row.get_y_shape(), reference_y_shape)
        test_case.assertEqual(row.get_dy_shape(), reference_dy_shape)
        test_case.assertGreater(row.get_steps(), 0)

        test_case.assertGreaterEqual(row.get_y_max_abs_diff(), 0.0)
        test_case.assertGreaterEqual(row.get_dy_max_abs_diff(), 0.0)

        if math.isnan(row.get_loop_s()):
            test_case.assertTrue(math.isnan(row.get_loop_s()))
        else:
            assert_positive_time(test_case, row.get_loop_s(), f"{execution.get_case_name()} {row.get_solver_key()} loop_s")

        if row.get_solver_key() in expected_solver_order:
            test_case.assertGreater(len(row.get_build_stats()), 0)
        else:
            test_case.assertGreaterEqual(len(row.get_build_stats()), 0)

        row_index += 1


class TestDynamicsEmtBenchmarkScripts(unittest.TestCase):
    """
    Validate the benchmark contracts of the selected real EMT demo scripts.
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Run the selected real-demo benchmarks once and cache their results.

        :return: None.
        :rtype: None
        """
        # The selected scripts are benchmark demos, so the regression suite
        # shortens their horizons while preserving the same model topology.
        configure_rload_script_for_tests()
        configure_zipload_script_for_tests()
        configure_event_script_for_tests()
        configure_validate_connections_script_for_tests()

        cls.rload_execution = run_case(
            case_name="thevenin_pi_rload",
            raw_rows=rload_script.benchmark_all_solvers(),
        )
        cls.zipload_execution = run_case(
            case_name="thevenin_pi_zipload",
            raw_rows=zipload_script.benchmark_all_solvers(),
        )
        cls.event_execution = run_case(
            case_name="emt_event",
            raw_rows=emt_event_script.benchmark_all_solvers(),
        )
        cls.validate_connections_execution = run_case(
            case_name="validate_connections_models",
            raw_rows=validate_connections_script.benchmark_all_solvers(),
        )
        cls.zipload_trajectory_bundles = dict()
        cls.rload_trajectory_bundles = dict()
        cls.event_trajectory_bundles = dict()

        for solver_key in ("SYMBOLIC", "AD", "VECTORIZED", "COMPILED"):
            cls.zipload_trajectory_bundles[solver_key] = run_zipload_trajectory_bundle(solver_key)
            cls.rload_trajectory_bundles[solver_key] = run_rload_trajectory_bundle(solver_key)
            cls.event_trajectory_bundles[solver_key] = run_event_trajectory_bundle(solver_key)

        rload_script.benchmark_all_solvers_cold_and_warm()
        zipload_script.benchmark_all_solvers_cold_and_warm()
        emt_event_script.benchmark_all_solvers_cold_and_warm()
        benchmark_report.export_solver_comparison_summary()
        process_benchmark.export_regression_short_process_cold_summary()

    def test_real_demo_benchmarks_expose_the_common_contract(self) -> None:
        """
        Every selected script must expose the same minimum benchmark contract.

        :return: None.
        :rtype: None
        """
        executions: Tuple[BenchmarkCaseExecution, ...] = (
            self.rload_execution,
            self.zipload_execution,
            self.event_execution,
            self.validate_connections_execution,
        )
        execution_index: int = 0

        while execution_index < len(executions):
            execution: BenchmarkCaseExecution = executions[execution_index]
            with self.subTest(case=execution.get_case_name()):
                assert_common_case_contract(self, execution)
            execution_index += 1

    def test_real_demo_benchmarks_keep_cross_backend_differences_bounded(self) -> None:
        """
        The selected demos must remain numerically close across the four backends.

        :return: None.
        :rtype: None
        """
        # The real demos are benchmark-style runs, so each case gets its own
        # tolerance envelope derived from the current backend spread. This keeps
        # the regression gate informative without pretending these demos are the
        # same as the tighter snapshot-verification suite.
        case_tolerances: Dict[str, Tuple[float, float]] = dict(
            thevenin_pi_rload=(3.5e-2, 1.0e-1),
            emt_event=(6.5e-2, 1.0e-1),
            validate_connections_models=(3.5e-2, 1.0e-1),
        )
        zip_case_tolerances: Tuple[float, float] = (8.5e-2, 2.0e2)

        executions: Tuple[BenchmarkCaseExecution, ...] = (
            self.rload_execution,
            self.event_execution,
            self.validate_connections_execution,
        )
        execution_index: int = 0

        while execution_index < len(executions):
            execution: BenchmarkCaseExecution = executions[execution_index]
            rows: List[BenchmarkRow] = execution.get_rows()
            y_tol: float = case_tolerances[execution.get_case_name()][0]
            dy_tol: float = case_tolerances[execution.get_case_name()][1]
            row_index: int = 1

            while row_index < len(rows):
                row: BenchmarkRow = rows[row_index]
                with self.subTest(case=execution.get_case_name(), solver=row.get_solver_key()):
                    self.assertLess(row.get_y_max_abs_diff(), y_tol)
                    self.assertLess(row.get_dy_max_abs_diff(), dy_tol)
                row_index += 1

            execution_index += 1

        zip_rows: List[BenchmarkRow] = self.zipload_execution.get_rows()
        zip_row_index: int = 1

        while zip_row_index < len(zip_rows):
            zip_row: BenchmarkRow = zip_rows[zip_row_index]
            with self.subTest(case=self.zipload_execution.get_case_name(), solver=zip_row.get_solver_key()):
                self.assertLess(zip_row.get_y_max_abs_diff(), zip_case_tolerances[0])
                self.assertTrue(math.isfinite(zip_row.get_dy_max_abs_diff()))
                self.assertLess(zip_row.get_dy_max_abs_diff(), zip_case_tolerances[1])
                self.assertTrue(math.isfinite(zip_row.get_final_residual_inf()) or math.isnan(zip_row.get_final_residual_inf()))
            zip_row_index += 1

    def test_real_demo_benchmarks_export_structured_files_inside_dynamics_emt(self) -> None:
        """
        The benchmark scripts must export their CSV/JSON artifacts inside the EMT demo tree.

        :return: None.
        :rtype: None
        """
        output_dir: Path = Path(__file__).resolve().parents[2] / "dynamics_emt" / "benchmark_results"
        expected_files: Tuple[str, ...] = (
            "thevequiv_piline_rload.csv",
            "thevequiv_piline_rload.json",
            "thevequiv_piline_zipload.csv",
            "thevequiv_piline_zipload.json",
            "emt_event_benchmark.csv",
            "emt_event_benchmark.json",
            "validate_connections_emt_models.csv",
            "validate_connections_emt_models.json",
        )
        file_index: int = 0

        self.assertTrue(output_dir.is_dir())

        while file_index < len(expected_files):
            expected_path: Path = output_dir / expected_files[file_index]
            with self.subTest(file=str(expected_path)):
                self.assertTrue(expected_path.is_file())
            file_index += 1

    def test_real_demo_cold_warm_exports_and_summary_exist(self) -> None:
        """
        The cold/warm exports and unified summary must exist inside the benchmark directory.

        :return: None.
        :rtype: None
        """
        output_dir: Path = Path(__file__).resolve().parents[2] / "dynamics_emt" / "benchmark_results"
        expected_files: Tuple[str, ...] = (
            "thevequiv_piline_zipload_all_solvers_cold_warm.csv",
            "thevequiv_piline_zipload_all_solvers_cold_warm.json",
            "thevequiv_piline_rload_all_solvers_cold_warm.csv",
            "thevequiv_piline_rload_all_solvers_cold_warm.json",
            "emt_event_all_solvers_cold_warm.csv",
            "emt_event_all_solvers_cold_warm.json",
            "emt_solver_comparison_summary.csv",
            "emt_solver_comparison_summary.json",
            "emt_solver_comparison_summary.md",
        )
        file_index: int = 0

        while file_index < len(expected_files):
            expected_path: Path = output_dir / expected_files[file_index]
            with self.subTest(file=str(expected_path)):
                self.assertTrue(expected_path.is_file())
            file_index += 1

    def test_real_demo_unified_summary_contains_expected_rows(self) -> None:
        """
        The unified summary must contain the expected case/solver combinations.

        :return: None.
        :rtype: None
        """
        summary_path: Path = Path(__file__).resolve().parents[2] / "dynamics_emt" / "benchmark_results" / "emt_solver_comparison_summary.json"

        with open(summary_path, "r", encoding="utf-8") as json_file:
            raw_rows: object = json.load(json_file)

        self.assertIsInstance(raw_rows, list)
        rows: List[Dict[str, object]] = list(raw_rows)
        expected_case_names: Tuple[str, ...] = ("ZIPload", "Rload", "Event", "ValidateConnections")
        expected_solver_order: Tuple[str, ...] = ("SYMBOLIC", "AD", "VECTORIZED", "COMPILED")
        expected_pairs: set[Tuple[str, str]] = set()

        for case_name in expected_case_names:
            for solver_key in expected_solver_order:
                expected_pairs.add((case_name, solver_key))

        observed_pairs: set[Tuple[str, str]] = set()
        row_index: int = 0

        while row_index < len(rows):
            row: Dict[str, object] = rows[row_index]
            case_name: str = str(row["case"])
            solver_key: str = str(row["solver"])
            observed_pairs.add((case_name, solver_key))

            with self.subTest(case=case_name, solver=solver_key):
                self.assertIn(case_name, expected_case_names)
                self.assertIn(solver_key, expected_solver_order)
                self.assertGreaterEqual(int(row["build_stats_count"]), 0)

                if case_name in ("ZIPload", "Rload", "Event"):
                    self.assertTrue(math.isfinite(float(row["cold_build_s"])))
                    self.assertTrue(math.isfinite(float(row["cold_sim_s"])))
                    self.assertTrue(math.isfinite(float(row["warm_sim_s"])))
                    self.assertTrue(math.isfinite(float(row["speedup"])))
                else:
                    self.assertTrue(math.isnan(float(row["cold_build_s"])))
                    self.assertTrue(math.isnan(float(row["cold_sim_s"])))
                    self.assertTrue(math.isnan(float(row["warm_sim_s"])))
                    self.assertTrue(math.isnan(float(row["speedup"])))

            row_index += 1

        self.assertEqual(observed_pairs, expected_pairs)

    def test_process_cold_regression_summary_exists_and_has_expected_rows(self) -> None:
        """
        The subprocess-isolated regression summary must exist and contain all expected rows.

        :return: None.
        :rtype: None
        """
        output_dir: Path = Path(__file__).resolve().parents[2] / "dynamics_emt" / "benchmark_results"
        summary_path: Path = output_dir / "emt_solver_process_cold_regression_short.json"
        expected_files: Tuple[str, ...] = (
            "emt_solver_process_cold_regression_short.csv",
            "emt_solver_process_cold_regression_short.json",
            "emt_solver_process_cold_regression_short.md",
            "emt_solver_regression_short_standard_process_cold.csv",
            "emt_solver_regression_short_standard_process_cold.json",
            "emt_solver_regression_short_standard_process_cold.md",
            "emt_solver_regression_short_cold_warm_process.csv",
            "emt_solver_regression_short_cold_warm_process.json",
            "emt_solver_regression_short_cold_warm_process.md",
        )
        file_index: int = 0

        while file_index < len(expected_files):
            expected_path: Path = output_dir / expected_files[file_index]
            with self.subTest(file=str(expected_path)):
                self.assertTrue(expected_path.is_file())
            file_index += 1

        with open(summary_path, "r", encoding="utf-8") as json_file:
            raw_rows: object = json.load(json_file)

        self.assertIsInstance(raw_rows, list)
        rows: List[Dict[str, object]] = list(raw_rows)
        expected_cases: Tuple[str, ...] = ("zipload", "rload", "event")
        expected_modes: Tuple[str, ...] = ("standard", "cold_warm")
        expected_solver_order: Tuple[str, ...] = ("SYMBOLIC", "AD", "VECTORIZED", "COMPILED")
        expected_row_count: int = len(expected_cases) * len(expected_modes) * len(expected_solver_order)
        observed_triplets: set[Tuple[str, str, str]] = set()
        row_index: int = 0

        self.assertEqual(len(rows), expected_row_count)

        while row_index < len(rows):
            row: Dict[str, object] = rows[row_index]
            case_name: str = str(row["case"])
            mode_name: str = str(row["mode"])
            solver_key: str = str(row["solver"])
            observed_triplets.add((case_name, mode_name, solver_key))

            with self.subTest(case=case_name, mode=mode_name, solver=solver_key):
                self.assertIn(case_name, expected_cases)
                self.assertIn(mode_name, expected_modes)
                self.assertIn(solver_key, expected_solver_order)
                self.assertTrue(math.isfinite(float(row["problem_build_s"])))
                self.assertTrue(math.isfinite(float(row["solver_init_s"])))

                if mode_name == "standard":
                    self.assertTrue(math.isfinite(float(row["solver_build_s"])))
                    self.assertTrue(math.isfinite(float(row["simulate_s"])))
                else:
                    self.assertTrue(math.isfinite(float(row["cold_build_s"])))
                    self.assertTrue(math.isfinite(float(row["cold_sim_s"])))
                    self.assertTrue(math.isfinite(float(row["warm_sim_s"])))
                    self.assertTrue(math.isfinite(float(row["speedup"])))

            row_index += 1

        expected_triplets: set[Tuple[str, str, str]] = set()

        for case_name in expected_cases:
            for mode_name in expected_modes:
                for solver_key in expected_solver_order:
                    expected_triplets.add((case_name, mode_name, solver_key))

        self.assertEqual(observed_triplets, expected_triplets)

    def test_zipload_temporal_traces_remain_close_across_solvers(self) -> None:
        """
        The ZIP-load temporal traces must remain close across the four backends.

        :return: None.
        :rtype: None
        """
        reference_bundle: SolverTrajectoryBundle = self.zipload_trajectory_bundles["SYMBOLIC"]

        for solver_key in ("AD", "VECTORIZED", "COMPILED"):
            assert_temporal_series_close(
                test_case=self,
                reference_bundle=reference_bundle,
                candidate_bundle=self.zipload_trajectory_bundles[solver_key],
                trace_builder=build_zipload_temporal_series,
                case_name="ZIPload",
                solver_key=solver_key,
            )

    def test_rload_temporal_traces_remain_close_across_solvers(self) -> None:
        """
        The R-load temporal traces must remain close across the four backends.

        :return: None.
        :rtype: None
        """
        reference_bundle: SolverTrajectoryBundle = self.rload_trajectory_bundles["SYMBOLIC"]

        for solver_key in ("AD", "VECTORIZED", "COMPILED"):
            assert_temporal_series_close(
                test_case=self,
                reference_bundle=reference_bundle,
                candidate_bundle=self.rload_trajectory_bundles[solver_key],
                trace_builder=build_rload_temporal_series,
                case_name="Rload",
                solver_key=solver_key,
            )

    def test_event_temporal_traces_remain_close_across_solvers(self) -> None:
        """
        The event-case temporal traces must remain close across the four backends.

        :return: None.
        :rtype: None
        """
        reference_bundle: SolverTrajectoryBundle = self.event_trajectory_bundles["SYMBOLIC"]

        for solver_key in ("AD", "VECTORIZED", "COMPILED"):
            assert_temporal_series_close(
                test_case=self,
                reference_bundle=reference_bundle,
                candidate_bundle=self.event_trajectory_bundles[solver_key],
                trace_builder=build_event_temporal_series,
                case_name="Event",
                solver_key=solver_key,
            )

    def test_demo_plot_exports_create_pngs_inside_dynamics_emt(self) -> None:
        """
        The regression plot exports must create PNG files in a dedicated folder.

        :return: None.
        :rtype: None
        """
        zip_paths: List[Path] = zipload_script.export_demo_plots(
            self.zipload_trajectory_bundles["COMPILED"].get_problem(),
            np.asarray(self.zipload_trajectory_bundles["COMPILED"].get_time_values(), dtype=np.float64),
            np.asarray(self.zipload_trajectory_bundles["COMPILED"].get_y_values(), dtype=np.float64),
            "COMPILED",
            output_root_name="plot_results_regression",
        )
        rload_paths: List[Path] = rload_script.export_demo_plots(
            self.rload_trajectory_bundles["COMPILED"].get_problem(),
            np.asarray(self.rload_trajectory_bundles["COMPILED"].get_time_values(), dtype=np.float64),
            np.asarray(self.rload_trajectory_bundles["COMPILED"].get_y_values(), dtype=np.float64),
            "COMPILED",
            output_root_name="plot_results_regression",
        )
        event_paths: List[Path] = emt_event_script.export_demo_plots(
            self.event_trajectory_bundles["COMPILED"].get_problem(),
            np.asarray(self.event_trajectory_bundles["COMPILED"].get_time_values(), dtype=np.float64),
            np.asarray(self.event_trajectory_bundles["COMPILED"].get_y_values(), dtype=np.float64),
            "COMPILED",
            output_root_name="plot_results_regression",
        )
        expected_paths: List[Path] = list()
        expected_paths.extend(zip_paths)
        expected_paths.extend(rload_paths)
        expected_paths.extend(event_paths)
        path_index: int = 0

        while path_index < len(expected_paths):
            expected_path: Path = expected_paths[path_index]
            with self.subTest(file=str(expected_path)):
                self.assertTrue(expected_path.is_file())
                self.assertGreater(expected_path.stat().st_size, 0)
            path_index += 1


if __name__ == "__main__":
    unittest.main()
