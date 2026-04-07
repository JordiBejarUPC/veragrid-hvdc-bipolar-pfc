import sys
import types
from typing import Dict, List, Tuple


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
