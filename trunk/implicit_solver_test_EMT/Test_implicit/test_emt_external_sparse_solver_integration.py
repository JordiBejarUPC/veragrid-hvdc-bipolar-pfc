import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from VeraGrid.trunk.dynamics_emt.support.benchmark_dependency_stubs import install_optional_dependency_stubs

install_optional_dependency_stubs()

import VeraGrid.trunk.dynamics_emt.scripting_example_thevequiv_piline_Rload_emt as rload_script
from VeraGridEngine.IO.external_sparse_solvers.install_external_sparse_solver_plugin import install_sparse_solver_plugin
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_solver_loader import load_sparse_solver_backend_provider
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_solver_registry import resolve_emt_sparse_solver_backend_provider
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes, SparseSolver


def configure_short_rload_case() -> None:
    """
    Configure the R-load demo for a short regression-scale run.

    :return: None.
    :rtype: None
    """
    rload_script.options.time_step = 5e-5
    rload_script.options.simulation_time = 5e-4
    rload_script.SOLVER_VERBOSE = False
    rload_script.ENABLE_NEWTON_TRACE = False


def write_dummy_pardiso_plugin(plugin_root: Path) -> str:
    """
    Write a dummy external sparse-solver plugin that wraps the internal SuperLU backend.

    :param plugin_root: Root directory where the plugin will be written.
    :type plugin_root: Path
    :return: Plugin name.
    :rtype: str
    """
    plugin_name: str = "dummy_pardiso"
    plugin_directory: Path = plugin_root / plugin_name
    plugin_directory.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": plugin_name,
        "solver_type": "Pardiso",
        "module": "backend",
        "class_name": "DummyPardisoProvider",
        "version": "1.0",
    }
    backend_source: str = "\n".join([
        "from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import SparseLinearSolverBackendProvider",
        "from VeraGridEngine.Utils.NumericalMethods.emt_sparse_superlu_backend import SuperLUSparseBackendProvider",
        "from VeraGridEngine.enumerations import SparseSolver",
        "",
        "class DummyPardisoProvider(SparseLinearSolverBackendProvider):",
        "    __slots__ = []",
        "",
        "    def get_name(self) -> str:",
        "        return 'dummy_pardiso'",
        "",
        "    def get_solver_type(self) -> SparseSolver:",
        "        return SparseSolver.Pardiso",
        "",
        "    def is_available(self) -> bool:",
        "        return True",
        "",
        "    def create_backend(self, base_matrix, base_data):",
        "        provider = SuperLUSparseBackendProvider()",
        "        return provider.create_backend(base_matrix, base_data)",
    ])

    with open(plugin_directory / "plugin.json", "w", encoding="utf-8") as json_file:
        json.dump(manifest, json_file, indent=2)

    with open(plugin_directory / "backend.py", "w", encoding="utf-8") as python_file:
        python_file.write(backend_source + "\n")

    return plugin_name


def build_compiled_solver_with_options(options: EmtOptions):
    """
    Build one compiled EMT solver for the configured R-load case.

    :param options: EMT options.
    :type options: EmtOptions
    :return: Pair ``(problem, solver)``.
    :rtype: tuple
    """
    problem = rload_script.create_problem()
    solver = build_emt_solver(
        options=options,
        problem=problem,
        t0=0.0,
        t_end=options.simulation_time,
        h=options.time_step,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        newton_diag_config=None,
    )
    return problem, solver


class TestEmtExternalSparseSolverIntegration(unittest.TestCase):
    """
    Validate external sparse solver integration for the EMT compiled backend.
    """

    def test_registry_falls_back_to_internal_superlu_when_plugin_is_missing(self) -> None:
        """
        Missing external plugins must fall back to internal SuperLU when allowed.

        :return: None.
        :rtype: None
        """
        provider = resolve_emt_sparse_solver_backend_provider(
            solver_type=SparseSolver.Pardiso,
            external_plugin_name="missing_plugin",
            external_plugin_directory="",
            allow_internal_fallback=True,
        )
        self.assertEqual(provider.get_solver_type(), SparseSolver.SuperLU)

    def test_registry_raises_when_plugin_is_missing_and_fallback_is_disabled(self) -> None:
        """
        Missing external plugins must raise when fallback is disabled.

        :return: None.
        :rtype: None
        """
        with self.assertRaises(FileNotFoundError):
            resolve_emt_sparse_solver_backend_provider(
                solver_type=SparseSolver.Pardiso,
                external_plugin_name="missing_plugin",
                external_plugin_directory="",
                allow_internal_fallback=False,
            )

    def test_compiled_solver_runs_with_external_plugin_and_matches_internal_solution(self) -> None:
        """
        The compiled backend must accept an external sparse plugin and preserve trajectories.

        :return: None.
        :rtype: None
        """
        configure_short_rload_case()

        internal_options = EmtOptions(
            time_step=rload_script.options.time_step,
            simulation_time=rload_script.options.simulation_time,
            solver_type=EmtSolverTypes.StructuralCompiled,
            sparse_solver=SparseSolver.SuperLU,
        )
        internal_problem, internal_solver = build_compiled_solver_with_options(internal_options)
        internal_t, internal_y, _internal_dy = internal_solver.simulate(boundary_updater=internal_problem)

        with tempfile.TemporaryDirectory() as temporary_directory_string:
            plugin_root: Path = Path(temporary_directory_string)
            plugin_name: str = write_dummy_pardiso_plugin(plugin_root)
            plugin_options = EmtOptions(
                time_step=rload_script.options.time_step,
                simulation_time=rload_script.options.simulation_time,
                solver_type=EmtSolverTypes.StructuralCompiled,
                sparse_solver=SparseSolver.Pardiso,
                external_sparse_solver_directory=str(plugin_root),
                external_sparse_solver_plugin_name=plugin_name,
                allow_internal_sparse_fallback=False,
            )
            plugin_problem, plugin_solver = build_compiled_solver_with_options(plugin_options)
            plugin_t, plugin_y, _plugin_dy = plugin_solver.simulate(boundary_updater=plugin_problem)

        self.assertEqual(internal_t.shape, plugin_t.shape)
        self.assertEqual(internal_y.shape, plugin_y.shape)
        self.assertLess(float(np.max(np.abs(internal_t - plugin_t))), 1.0e-14)
        self.assertLess(float(np.max(np.abs(internal_y - plugin_y))), 1.0e-9)

    def test_repository_pardiso_plugin_template_loads(self) -> None:
        """
        The repository PARDISO plugin template must load through the EMT plugin loader.

        :return: None.
        :rtype: None
        """
        with tempfile.TemporaryDirectory() as temporary_directory_string:
            plugin_root: Path = Path(temporary_directory_string)
            install_sparse_solver_plugin("pardiso_pypardiso", str(plugin_root))
            provider = load_sparse_solver_backend_provider(
                plugin_name="pardiso_pypardiso",
                plugin_directory_override=str(plugin_root),
            )

        self.assertEqual(provider.get_name(), "pardiso_pypardiso")
        self.assertEqual(provider.get_solver_type(), SparseSolver.Pardiso)
        self.assertIsInstance(provider.is_available(), bool)

    def test_repository_pardiso_plugin_falls_back_to_superlu_when_unavailable(self) -> None:
        """
        The repository PARDISO plugin template must fall back to SuperLU when unavailable.

        :return: None.
        :rtype: None
        """
        with tempfile.TemporaryDirectory() as temporary_directory_string:
            plugin_root: Path = Path(temporary_directory_string)
            install_sparse_solver_plugin("pardiso_pypardiso", str(plugin_root))
            provider = resolve_emt_sparse_solver_backend_provider(
                solver_type=SparseSolver.Pardiso,
                external_plugin_name="pardiso_pypardiso",
                external_plugin_directory=str(plugin_root),
                allow_internal_fallback=True,
            )

        if provider.get_solver_type() == SparseSolver.Pardiso:
            self.assertEqual(provider.get_name(), "pardiso_pypardiso")
        else:
            self.assertEqual(provider.get_solver_type(), SparseSolver.SuperLU)

    def test_repository_klu_plugin_template_loads(self) -> None:
        """
        The repository KLU plugin template must load through the EMT plugin loader.

        :return: None.
        :rtype: None
        """
        with tempfile.TemporaryDirectory() as temporary_directory_string:
            plugin_root: Path = Path(temporary_directory_string)
            install_sparse_solver_plugin("klu_cvxoptklu", str(plugin_root))
            provider = load_sparse_solver_backend_provider(
                plugin_name="klu_cvxoptklu",
                plugin_directory_override=str(plugin_root),
            )

        self.assertEqual(provider.get_name(), "klu_cvxoptklu")
        self.assertEqual(provider.get_solver_type(), SparseSolver.KLU)
        self.assertIsInstance(provider.is_available(), bool)

    def test_repository_direct_klu_plugin_template_loads(self) -> None:
        """
        The repository direct KLU plugin template must load through the EMT plugin loader.

        :return: None.
        :rtype: None
        """
        with tempfile.TemporaryDirectory() as temporary_directory_string:
            plugin_root: Path = Path(temporary_directory_string)
            install_sparse_solver_plugin("klu_vcpkg_native", str(plugin_root))
            provider = load_sparse_solver_backend_provider(
                plugin_name="klu_vcpkg_native",
                plugin_directory_override=str(plugin_root),
            )

        self.assertEqual(provider.get_name(), "klu_vcpkg_native")
        self.assertEqual(provider.get_solver_type(), SparseSolver.KLU)
        self.assertIsInstance(provider.is_available(), bool)

    def test_repository_klu_plugin_falls_back_to_superlu_when_unavailable(self) -> None:
        """
        The repository KLU plugin template must fall back to SuperLU when unavailable.

        :return: None.
        :rtype: None
        """
        with tempfile.TemporaryDirectory() as temporary_directory_string:
            plugin_root: Path = Path(temporary_directory_string)
            install_sparse_solver_plugin("klu_cvxoptklu", str(plugin_root))
            provider = resolve_emt_sparse_solver_backend_provider(
                solver_type=SparseSolver.KLU,
                external_plugin_name="klu_cvxoptklu",
                external_plugin_directory=str(plugin_root),
                allow_internal_fallback=True,
            )

        if provider.get_solver_type() == SparseSolver.KLU:
            self.assertEqual(provider.get_name(), "klu_cvxoptklu")
        else:
            self.assertEqual(provider.get_solver_type(), SparseSolver.SuperLU)

    def test_repository_direct_klu_plugin_loads_from_default_plugin_folder(self) -> None:
        """
        The direct KLU plugin installed in the default VeraGrid plugin folder must load.

        :return: None.
        :rtype: None
        """
        provider = load_sparse_solver_backend_provider(
            plugin_name="klu_vcpkg_native",
            plugin_directory_override="",
        )
        self.assertEqual(provider.get_solver_type(), SparseSolver.KLU)

    def test_compiled_solver_runs_with_direct_klu_plugin_when_runtime_is_installed(self) -> None:
        """
        The compiled EMT backend must run with the direct KLU plugin when the native runtime is installed.

        :return: None.
        :rtype: None
        """
        provider = load_sparse_solver_backend_provider(
            plugin_name="klu_vcpkg_native",
            plugin_directory_override="",
        )

        if provider.is_available():
            pass
        else:
            self.skipTest("Direct KLU runtime not installed for this environment")

        configure_short_rload_case()

        internal_options = EmtOptions(
            time_step=rload_script.options.time_step,
            simulation_time=rload_script.options.simulation_time,
            solver_type=EmtSolverTypes.StructuralCompiled,
            sparse_solver=SparseSolver.SuperLU,
        )
        internal_problem, internal_solver = build_compiled_solver_with_options(internal_options)
        internal_t, internal_y, _internal_dy = internal_solver.simulate(boundary_updater=internal_problem)

        plugin_options = EmtOptions(
            time_step=rload_script.options.time_step,
            simulation_time=rload_script.options.simulation_time,
            solver_type=EmtSolverTypes.StructuralCompiled,
            sparse_solver=SparseSolver.KLU,
            external_sparse_solver_plugin_name="klu_vcpkg_native",
            allow_internal_sparse_fallback=False,
        )
        plugin_problem, plugin_solver = build_compiled_solver_with_options(plugin_options)
        plugin_t, plugin_y, _plugin_dy = plugin_solver.simulate(boundary_updater=plugin_problem)

        self.assertEqual(internal_t.shape, plugin_t.shape)
        self.assertEqual(internal_y.shape, plugin_y.shape)
        self.assertLess(float(np.max(np.abs(internal_t - plugin_t))), 1.0e-14)
        self.assertLess(float(np.max(np.abs(internal_y - plugin_y))), 1.0e-8)

    def test_repository_pardiso_plugin_uses_external_runtime_when_installed(self) -> None:
        """
        The repository PARDISO plugin must become available when the runtime is installed externally.

        :return: None.
        :rtype: None
        """
        provider = load_sparse_solver_backend_provider(
            plugin_name="pardiso_pypardiso",
            plugin_directory_override="",
        )

        if provider.is_available():
            pass
        else:
            self.skipTest("External pypardiso runtime not installed for this environment")

        with tempfile.TemporaryDirectory() as temporary_plugins_dir:
            plugin_root: Path = Path(temporary_plugins_dir)
            install_sparse_solver_plugin("pardiso_pypardiso", str(plugin_root))
            provider = load_sparse_solver_backend_provider(
                plugin_name="pardiso_pypardiso",
                plugin_directory_override=str(plugin_root),
            )

        self.assertEqual(provider.get_solver_type(), SparseSolver.Pardiso)
        self.assertTrue(provider.is_available())

    def test_compiled_solver_runs_with_repository_pardiso_plugin_when_runtime_is_installed(self) -> None:
        """
        The compiled EMT backend must run with the repository PARDISO plugin when the runtime is installed.

        :return: None.
        :rtype: None
        """
        provider = load_sparse_solver_backend_provider(
            plugin_name="pardiso_pypardiso",
            plugin_directory_override="",
        )

        if provider.is_available():
            pass
        else:
            self.skipTest("External pypardiso runtime not installed for this environment")

        configure_short_rload_case()

        internal_options = EmtOptions(
            time_step=rload_script.options.time_step,
            simulation_time=rload_script.options.simulation_time,
            solver_type=EmtSolverTypes.StructuralCompiled,
            sparse_solver=SparseSolver.SuperLU,
        )
        internal_problem, internal_solver = build_compiled_solver_with_options(internal_options)
        internal_t, internal_y, _internal_dy = internal_solver.simulate(boundary_updater=internal_problem)

        plugin_options = EmtOptions(
            time_step=rload_script.options.time_step,
            simulation_time=rload_script.options.simulation_time,
            solver_type=EmtSolverTypes.StructuralCompiled,
            sparse_solver=SparseSolver.Pardiso,
            external_sparse_solver_plugin_name="pardiso_pypardiso",
            allow_internal_sparse_fallback=False,
        )
        plugin_problem, plugin_solver = build_compiled_solver_with_options(plugin_options)
        plugin_t, plugin_y, _plugin_dy = plugin_solver.simulate(boundary_updater=plugin_problem)

        self.assertEqual(internal_t.shape, plugin_t.shape)
        self.assertEqual(internal_y.shape, plugin_y.shape)
        self.assertLess(float(np.max(np.abs(internal_t - plugin_t))), 1.0e-14)
        self.assertLess(float(np.max(np.abs(internal_y - plugin_y))), 1.0e-8)

    def test_vectorized_solver_runs_with_external_dummy_sparse_plugin_and_matches_internal_solution(self) -> None:
        """
        The vectorized EMT backend must accept an external sparse plugin and preserve trajectories.

        :return: None.
        :rtype: None
        """
        configure_short_rload_case()

        internal_options = EmtOptions(
            time_step=rload_script.options.time_step,
            simulation_time=rload_script.options.simulation_time,
            solver_type=EmtSolverTypes.StructuralAD,
            sparse_solver=SparseSolver.SuperLU,
        )
        internal_problem, internal_solver = build_compiled_solver_with_options(internal_options)
        internal_t, internal_y, _internal_dy = internal_solver.simulate(boundary_updater=internal_problem)

        with tempfile.TemporaryDirectory() as temporary_directory_string:
            plugin_root: Path = Path(temporary_directory_string)
            plugin_name: str = write_dummy_pardiso_plugin(plugin_root)
            plugin_options = EmtOptions(
                time_step=rload_script.options.time_step,
                simulation_time=rload_script.options.simulation_time,
                solver_type=EmtSolverTypes.StructuralAD,
                sparse_solver=SparseSolver.Pardiso,
                external_sparse_solver_directory=str(plugin_root),
                external_sparse_solver_plugin_name=plugin_name,
                allow_internal_sparse_fallback=False,
            )
            plugin_problem, plugin_solver = build_compiled_solver_with_options(plugin_options)
            plugin_t, plugin_y, _plugin_dy = plugin_solver.simulate(boundary_updater=plugin_problem)

        self.assertEqual(internal_t.shape, plugin_t.shape)
        self.assertEqual(internal_y.shape, plugin_y.shape)
        self.assertLess(float(np.max(np.abs(internal_t - plugin_t))), 1.0e-14)
        self.assertLess(float(np.max(np.abs(internal_y - plugin_y))), 1.0e-8)


if __name__ == "__main__":
    unittest.main()
