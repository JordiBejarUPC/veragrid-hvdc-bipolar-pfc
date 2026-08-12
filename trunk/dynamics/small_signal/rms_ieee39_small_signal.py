from __future__ import annotations

from pathlib import Path
from typing import List

import andes
from matplotlib import pyplot as plt

from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType
from VeraGridEngine.enumerations import RmsInitializationMethod
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.shunt_template import get_shunt_template
from VeraGridEngine.Templates.Rms.transformer_rms_template import get_transformer2w_rms
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
import VeraGridEngine.api as gce

from trunk.dynamics.small_signal.rms_kundur_small_signal import save_small_signal_results_to_csv
from trunk.dynamics.small_signal.rms_kundur_small_signal import plot_participation_factors
from trunk.dynamics.small_signal.rms_kundur_small_signal import plot_s_domain_eigenvalues
from trunk.dynamics.small_signal.ieee39_network_config import configure_ieee39_static_network
from trunk.dynamics.small_signal.ieee39_rms_model_config import get_ieee39_genrou_rms_template


def _get_base_grid_path() -> Path:
    """Return the IEEE39 base-grid path.

    :return: Base-grid path.
    """
    grid_path: Path = Path(andes.get_case("ieee39/ieee39.raw"))
    return grid_path.resolve()


def _get_output_grid_path() -> Path:
    """Return the RMS-ready IEEE39 output path.

    :return: Output path.
    """
    return Path(__file__).resolve().parent / "ieee39_rms_sss.veragrid"


def _get_results_dir() -> Path:
    """Return the IEEE39 VeraGrid results directory.

    :return: Results directory.
    """
    return Path(__file__).resolve().parent / "ieee39_small_signal_rms_results_VeraGrid"


def _assign_ieee39_rms_models(grid: gce.MultiCircuit) -> None:
    """Assign standard GENROU RMS models to the IEEE39 grid.

    :param grid: VeraGrid network.
    :return: None.
    """
    bus_list: List[object] = list(grid.buses)
    for bus in bus_list:
        initialize_bus_rms(bus, vf=grid.var_factory)

    generator_count: int = len(grid.generators)
    generator_index: int = 0
    while generator_index < generator_count:
        generator = grid.generators[generator_index]
        set_rms_model(
            device=generator,
            model=get_ieee39_genrou_rms_template(
                vfactory=grid.var_factory,
                generator_index=generator_index,
                name=f"ieee39_gen_{generator_index + 1}",
            ).block,
            var_factory=grid.var_factory,
        )
        generator_index += 1

    line_count: int = len(grid.lines)
    line_index: int = 0
    while line_index < line_count:
        line = grid.lines[line_index]
        set_rms_model(device=line, model=get_line_rms_template(grid.var_factory, name=f"ieee39_line_{line_index + 1}").block, var_factory=grid.var_factory)
        line_index += 1

    transformer_count: int = len(grid.transformers2w)
    transformer_index: int = 0
    while transformer_index < transformer_count:
        transformer = grid.transformers2w[transformer_index]
        set_rms_model(
            device=transformer,
            model=get_transformer2w_rms(grid.var_factory).block,
            var_factory=grid.var_factory,
        )
        transformer_index += 1

    load_count: int = len(grid.loads)
    load_index: int = 0
    while load_index < load_count:
        load = grid.loads[load_index]
        set_rms_model(device=load, model=get_load_rms_template(grid.var_factory, name=f"ieee39_load_{load_index + 1}").block, var_factory=grid.var_factory)
        load_index += 1

    shunt_count: int = len(grid.shunts)
    shunt_index: int = 0
    while shunt_index < shunt_count:
        shunt = grid.shunts[shunt_index]
        shunt_model = get_shunt_template(
            grid.var_factory,
            name=f"ieee39_shunt_{shunt_index + 1}",
            phasor=False,
        ).block
        shunt_vm = shunt_model.E(VarPowerFlowReferenceType.Vm)
        shunt_p = shunt_model.E(VarPowerFlowReferenceType.P)
        shunt_q = shunt_model.E(VarPowerFlowReferenceType.Q)
        shunt_g = shunt_model.api_obj_mapping[ParamPowerFlowReferenceType.g]
        shunt_b = shunt_model.api_obj_mapping[ParamPowerFlowReferenceType.b]
        shunt_model.event_dict[shunt_g] = grid.var_factory.add_const(
            value=shunt.G / grid.Sbase,
            name="g",
        )
        shunt_model.event_dict[shunt_b] = grid.var_factory.add_const(
            value=shunt.B / grid.Sbase,
            name="b",
        )
        shunt_model.init_eqs[shunt_p] = -shunt_g * shunt_vm ** 2
        shunt_model.init_eqs[shunt_q] = shunt_b * shunt_vm ** 2
        set_rms_model(
            device=shunt,
            model=shunt_model,
            var_factory=grid.var_factory,
        )
        shunt_index += 1


def _build_power_flow_options() -> PowerFlowOptions:
    """Build the power-flow options for the benchmark.

    :return: Power-flow options.
    """
    options: PowerFlowOptions = PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-12,
        max_iter=25,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=False,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    return options


def _build_rms_options() -> RmsOptions:
    """Build the RMS options for the benchmark.

    :return: RMS options.
    """
    options: RmsOptions = RmsOptions(
        time_step=0.001,
        simulation_time=10.0,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=1000,
        verbose=0,
    )
    return options


def build_ieee39_rms_benchmark_grid() -> gce.MultiCircuit:
    """Build the IEEE39 RMS-ready benchmark grid.

    :return: RMS-ready grid.
    """
    grid_path: Path = _get_base_grid_path()
    grid: gce.MultiCircuit = gce.open_file(str(grid_path))
    configure_ieee39_static_network(grid)
    _assign_ieee39_rms_models(grid)
    output_path: Path = _get_output_grid_path()
    gce.save_file(grid=grid, filename=str(output_path))
    return grid


def run_ieee39_small_signal(show_figures: bool = True) -> None:
    """Run the IEEE39 RMS small-signal benchmark.

    :param show_figures: Display the interactive plots after saving all data.
    :return: None.
    """
    grid: gce.MultiCircuit = build_ieee39_rms_benchmark_grid()
    pf_options: PowerFlowOptions = _build_power_flow_options()
    power_flow: PowerFlowDriver = PowerFlowDriver(grid, pf_options)
    power_flow.run()
    pf_results: PowerFlowResults = power_flow.results

    rms_options: RmsOptions = _build_rms_options()
    ss_options: RmsSmallSignalStabilityOptions = RmsSmallSignalStabilityOptions(ss_assessment_time=0.0)
    driver: SmallSignalStabilityRmsDriver = SmallSignalStabilityRmsDriver(
        grid=grid,
        rms_options=rms_options,
        sss_options=ss_options,
        pf_results=pf_results,
    )
    driver.run()

    # Persist the numerical benchmark before opening interactive figures so a
    # PyCharm plot window can remain open without delaying result generation.
    results_dir: Path = _get_results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    save_small_signal_results_to_csv(driver.results, pf_results, results_dir)

    print("\nEigenvalues:")
    print(driver.results.eigenvalues)
    print("\nParticipation factors:")
    print(driver.results.participation_factors)

    plot_s_domain_eigenvalues(driver.results.eigenvalues)
    plot_participation_factors(driver.results.participation_factors)
    if show_figures:
        plt.show()
    else:
        plt.close("all")


if __name__ == "__main__":
    run_ieee39_small_signal()
else:
    pass
