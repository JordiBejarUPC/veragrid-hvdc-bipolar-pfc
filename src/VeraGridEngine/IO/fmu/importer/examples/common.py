# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Any
from pathlib import Path
import uuid
import numpy as np

from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    SolverType,
    VarPowerFlowReferenceType,
)

from VeraGridEngine.IO.fmu.exporter.api import export_fmu
from VeraGridEngine.IO.fmu.exporter.config import ExportConfig as CsExportConfig, detect_target_platform as detect_cs_target_platform
from VeraGridEngine.IO.fmu.exporter.compat import Block, Const, Var
from VeraGridEngine.IO.fmu.importer.experimental_cs import FmuRefBinding
from VeraGridEngine.IO.fmu.importer.experimental_me import FmuMeIntegrationMethod
from VeraGridEngine.IO.fmu.importer.model_description import FmuInterfaceMode
from VeraGridEngine.IO.fmu.importer.user_api import (
    FmuDeviceAttachmentRequest,
    FmuDeviceDomain,
    FmuReferenceValue,
    attach_fmu_to_device,
)
from VeraGridEngine.IO.fmu.exporter_me.api import export_fmu_me
from VeraGridEngine.IO.fmu.exporter_me.config import ExportConfig as MeExportConfig, detect_target_platform as detect_me_target_platform


def get_example_output_dir() -> Path:
    """Return the directory used by the FMU import example scripts.

    :return: Example output directory.
    """

    output_dir: Path = Path(__file__).resolve().parents[1] / "reports" / "examples"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir.resolve()


def _has_fmpy() -> bool:
    """Return whether the current Python environment provides `fmpy`.

    :return: `True` when `fmpy` can be imported.
    """

    try:
        import fmpy

        return fmpy is not None
    except ModuleNotFoundError:
        return False


def write_example_report(report_path: Path, lines: tuple[str, ...]) -> Path:
    """Write a plain-text report for one FMU import example run.

    :param report_path: Report output path.
    :param lines: Lines written to the report.
    :return: Final report path.
    """

    text: str = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    return report_path


def _build_rms_cs_source_block() -> Block:
    """Build the self-contained source block used to export an example RMS CS FMU.

    :return: Example RMS CS FMU block.
    """

    x: Var = Var("x")
    dx: Var = Var("dx", base_var=x)
    p_out: Var = Var("p_out")
    q_out: Var = Var("q_out")
    return Block(
        state_vars=[x],
        state_eqs=[Const(1.0)],
        algebraic_vars=[p_out, q_out],
        algebraic_eqs=[p_out - (Const(-0.1) - Const(0.02) * x), q_out - Const(-0.01)],
        diff_vars=[dx],
        init_values={x: Const(0.0), p_out: Const(-0.1), q_out: Const(-0.01)},
        init_eqs={p_out: Const(-0.1), q_out: Const(-0.01)},
        out_vars=[p_out, q_out],
    )


def _build_rms_me_source_block() -> Block:
    """Build the self-contained source block used to export an example RMS ME FMU.

    :return: Example RMS ME FMU block.
    """

    x: Var = Var("x")
    dx: Var = Var("dx", base_var=x)
    p_out: Var = Var("p_out")
    q_out: Var = Var("q_out")
    u: Var = Var("u")
    return Block(
        state_vars=[x],
        state_eqs=[Const(1.0) + u],
        algebraic_vars=[p_out, q_out],
        algebraic_eqs=[p_out - x, q_out - Const(-0.01)],
        diff_vars=[dx],
        init_values={x: Const(0.0), p_out: Const(0.0), q_out: Const(-0.01)},
        init_eqs={p_out: Const(0.0), q_out: Const(-0.01)},
        in_vars=[u],
        out_vars=[p_out, q_out],
    )


def _build_emt_cs_source_block() -> Block:
    """Build the self-contained source block used to export an example EMT CS FMU.

    :return: Example EMT CS FMU block.
    """

    x: Var = Var("x")
    dx: Var = Var("dx", base_var=x)
    i_a: Var = Var("i_a_out")
    i_b: Var = Var("i_b_out")
    i_c: Var = Var("i_c_out")
    v_a: Var = Var("v_a_in")
    v_b: Var = Var("v_b_in")
    v_c: Var = Var("v_c_in")
    return Block(
        state_vars=[x],
        state_eqs=[Const(1.0)],
        algebraic_vars=[i_a, i_b, i_c],
        algebraic_eqs=[i_a - (Const(-0.01) * x), i_b - (Const(0.005) * x), i_c - (Const(0.005) * x)],
        diff_vars=[dx],
        init_values={x: Const(0.0), i_a: Const(0.0), i_b: Const(0.0), i_c: Const(0.0)},
        init_eqs={i_a: Const(0.0), i_b: Const(0.0), i_c: Const(0.0)},
        in_vars=[v_a, v_b, v_c],
        out_vars=[i_a, i_b, i_c],
    )


def _build_emt_me_source_block() -> Block:
    """Build the self-contained source block used to export an example EMT ME FMU.

    :return: Example EMT ME FMU block.
    """

    x: Var = Var("x")
    dx: Var = Var("dx", base_var=x)
    i_a: Var = Var("i_a_out")
    i_b: Var = Var("i_b_out")
    i_c: Var = Var("i_c_out")
    u: Var = Var("u")
    v_b: Var = Var("v_b_in")
    v_c: Var = Var("v_c_in")
    return Block(
        state_vars=[x],
        state_eqs=[Const(1.0) + u],
        algebraic_vars=[i_a, i_b, i_c],
        algebraic_eqs=[i_a - x, i_b - (Const(-0.5) * x), i_c - (Const(-0.5) * x)],
        diff_vars=[dx],
        init_values={x: Const(0.0), i_a: Const(0.0), i_b: Const(0.0), i_c: Const(0.0)},
        init_eqs={i_a: Const(0.0), i_b: Const(0.0), i_c: Const(0.0)},
        in_vars=[u, v_b, v_c],
        out_vars=[i_a, i_b, i_c],
    )


def export_example_rms_cs_fmu(output_dir: Path) -> Path:
    """Export the self-contained RMS CS device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :return: Generated FMU path.
    """

    unique_name: str = f"ExampleRmsCsDevice_{uuid.uuid4().hex[:8]}"
    return export_fmu(
        _build_rms_cs_source_block(),
        CsExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_cs_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
        ),
    )


def export_example_rms_me_fmu(output_dir: Path) -> Path:
    """Export the self-contained RMS ME device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :return: Generated FMU path.
    """

    unique_name: str = f"ExampleRmsMeDevice_{uuid.uuid4().hex[:8]}"
    return export_fmu_me(
        _build_rms_me_source_block(),
        MeExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_me_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
        ),
    )


def export_example_emt_cs_fmu(output_dir: Path) -> Path:
    """Export the self-contained EMT CS device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :return: Generated FMU path.
    """

    unique_name: str = f"ExampleEmtCsDevice_{uuid.uuid4().hex[:8]}"
    return export_fmu(
        _build_emt_cs_source_block(),
        CsExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_cs_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
        ),
    )


def export_example_emt_me_fmu(output_dir: Path) -> Path:
    """Export the self-contained EMT ME device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :return: Generated FMU path.
    """

    unique_name: str = f"ExampleEmtMeDevice_{uuid.uuid4().hex[:8]}"
    return export_fmu_me(
        _build_emt_me_source_block(),
        MeExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_me_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
        ),
    )


def _build_power_flow_options() -> PowerFlowOptions:
    """Build the power-flow options reused by the FMU import examples.

    :return: Power-flow options.
    """

    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=True,
        apply_temperature_correction=False,
        branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )


def _get_bus_power_default(grid: MultiCircuit, pf_results: Any, bus: Bus) -> tuple[float, float]:
    """
    Return the exact active and reactive power injection solved at one bus.

    The FMU examples use these values as output defaults so the imported FMU shell
    starts from the same operating point that the static network used during the
    power-flow initialization.

    :param grid: Solved grid.
    :param pf_results: Finished power-flow results.
    :param bus: Bus where the imported FMU device is connected.
    :return: Active and reactive bus injections.
    """

    bus_index: int = grid.buses.index(bus)
    bus_power: complex = complex(pf_results.Sbus[bus_index] / grid.Sbase)
    return float(bus_power.real), float(bus_power.imag)


def _build_rms_demo_grid() -> tuple[MultiCircuit, Load]:
    """Build the minimal RMS demo grid used by the RMS FMU import examples.

    :return: Grid and imported device.
    """

    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)
    bus_slack: Bus = Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus_load: Bus = Bus(name="Bus1", Vnom=10.0)
    grid.add_bus(bus_slack)
    grid.add_bus(bus_load)

    # RMS buses need their symbolic shell before attaching dynamic devices.
    initialize_bus_rms(bus_slack, vf=grid.var_factory)
    initialize_bus_rms(bus_load, vf=grid.var_factory)

    line: Line = Line(name="line_0_1", bus_from=bus_slack, bus_to=bus_load, r=0.03, x=0.07, b=0.03, rate=900.0)
    generator: Generator = Generator(
        name="Gen0",
        P=10.0,
        vset=1.0,
        Snom=900.0,
        x1=0.86138701,
        r1=0.3,
        freq=50.0,
    )
    load: Load = Load(name="ImportedLoad", P=10.0, Q=1.0)

    grid.add_line(line)
    grid.add_generator(bus=bus_slack, api_obj=generator)
    grid.add_load(bus=bus_load, api_obj=load)
    line.rms_template = get_line_rms_template(grid.var_factory)
    generator.rms_template = get_complete_generator_template_rms(grid.var_factory)
    grid.add_rms_events_group(RmsEventsGroup(name="default_rms_example_group"))
    return grid, load


def _build_emt_demo_grid() -> tuple[MultiCircuit, Load]:
    """Build the minimal EMT demo grid used by the EMT FMU import examples.

    :return: Grid and imported device.
    """

    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)
    bus: Bus = Bus(name="Bus0", Vnom=10.0, is_slack=True)
    grid.add_bus(bus)

    generator: Generator = Generator(name="Gen0", P=0.0, vset=1.0, Snom=900.0, x1=0.2, r1=0.01)
    generator_template = get_generator_thevenin_rl_emt_template_with_ref(
        vf=grid.var_factory,
        name="emt_thevenin_source",
    )
    load: Load = Load(name="ImportedLoad", P=0.0, Q=0.0)

    grid.add_generator(bus=bus, api_obj=generator)
    grid.add_load(bus=bus, api_obj=load)

    # Materialize the canonical ABC bus shell after the complete one-bus
    # topology is known, matching the established EMT scripting lifecycle.
    get_bus_emt_template(grid=grid, bus=bus)

    # The public setter propagates the bus voltage identities into the source
    # model before the real EMT problem compiles its equations.
    set_emt_model(
        device=generator,
        model=generator_template.block,
        var_factory=grid.var_factory,
    )
    return grid, load


def _build_rms_results_summary(driver: RmsSimulationDriver, load: Load) -> tuple[str, ...]:
    """Build a human-readable summary for one RMS FMU import example.

    :param driver: Finished RMS simulation driver.
    :param load: Imported FMU load device.
    :return: Summary lines.
    """

    if driver.results is None:
        raise RuntimeError("The RMS simulation did not produce results")
    else:
        p_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.P]
        q_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
        p_final = _try_get_result_value(driver.results.values, driver.results.uid2idx.get(p_var.uid, None))
        q_final = _try_get_result_value(driver.results.values, driver.results.uid2idx.get(q_var.uid, None))
        p_text: str
        q_text: str
        if p_final is None:
            p_text = "not recorded"
        else:
            p_text = f"{p_final:.8f}"
        if q_final is None:
            q_text = "not recorded"
        else:
            q_text = f"{q_final:.8f}"
        return (
            f"final_time = {driver.results.time_array[-1]}",
            f"P_final = {p_text}",
            f"Q_final = {q_text}",
        )


def _read_rms_fmu_output(problem: Any, device: Load, reference: VarPowerFlowReferenceType) -> float | None:
    """
    Read one FMU-backed RMS output directly from the registered runtime adapters.

    The helper prefers adapter indices over symbolic-name reconstruction because the
    runtime adapters already own the authoritative mapping from VeraGrid references
    to the parameter vector updated during the simulation.

    :param problem: Finished RMS problem instance.
    :param device: Device hosting the imported FMU.
    :param reference: VeraGrid output reference to recover.
    :return: Runtime output value when available.
    """

    adapter = None
    for adapter in problem._fmu_cs_adapters:
        if adapter.device == device:
            if reference in adapter.last_outputs:
                return adapter.last_outputs[reference]
            else:
                if problem._last_variable_parameters_values is None:
                    return None
                else:
                    if reference in adapter.output_param_indices:
                        output_index: int = adapter.output_param_indices[reference]
                        return float(problem._last_variable_parameters_values[output_index])
                    else:
                        return None
        else:
            pass

    for adapter in problem._fmu_me_adapters:
        if adapter.device == device:
            if reference in adapter.last_outputs:
                return adapter.last_outputs[reference]
            else:
                if problem._last_variable_parameters_values is None:
                    return None
                else:
                    if reference in adapter.output_param_indices:
                        output_index = adapter.output_param_indices[reference]
                        return float(problem._last_variable_parameters_values[output_index])
                    else:
                        return None
        else:
            pass

    return None


def _build_final_rms_snapshot(driver: RmsSimulationDriver) -> np.ndarray:
    """
    Build the final RMS state snapshot from the finished results matrix.

    :param driver: Finished RMS simulation driver.
    :return: Final RMS state/algebraic snapshot.
    """

    final_values: np.ndarray = np.asarray(driver.results.values[-1, :, 0], dtype=float)
    return np.ravel(final_values)


def _refresh_rms_fmu_outputs_from_final_snapshot(problem: Any,
                                                 device: Load,
                                                 final_snapshot: np.ndarray,
                                                 final_time: float) -> None:
    """
    Re-evaluate FMU outputs from the final RMS network snapshot when the runtime cache is empty.

    The fallback is used only by the example report helpers. It keeps the example
    informative even when the solver lifecycle closes the FMU before the report is
    assembled.

    :param problem: Finished RMS problem instance.
    :param device: Device hosting the imported FMU.
    :param final_snapshot: Final RMS state/algebraic snapshot.
    :param final_time: Final simulation time.
    :return: None.
    """

    adapter = None
    for adapter in problem._fmu_cs_adapters:
        if adapter.device == device:
            try:
                if len(adapter.last_outputs) == 0:
                    outputs = adapter.initialize_outputs(final_time, final_snapshot)
                    adapter.last_outputs = dict(outputs)
                else:
                    pass
            finally:
                # The report owns the last use of the example adapter. Native
                # resources must be released even when outputs were cached.
                adapter.close()
        else:
            pass

    for adapter in problem._fmu_me_adapters:
        if adapter.device == device:
            try:
                if len(adapter.last_outputs) == 0:
                    outputs = adapter.initialize_outputs(final_time, final_snapshot)
                    adapter.last_outputs = dict(outputs)
                else:
                    pass
            finally:
                # Model Exchange uses the same report-owned final lifecycle.
                adapter.close()
        else:
            pass


def _build_emt_results_summary(driver: EmtSimulationDriver, load: Load) -> tuple[str, ...]:
    """Build a human-readable summary for one EMT FMU import example.

    :param driver: Finished EMT simulation driver.
    :param load: Imported FMU load device.
    :return: Summary lines.
    """

    if driver.results is None:
        raise RuntimeError("The EMT simulation did not produce results")
    else:
        # A report represents one conclusive run, not the placeholder storage
        # allocated for inactive or failed event groups.
        active_group_count: int = 0
        event_group: EmtEventsGroup
        for event_group in driver.grid.emt_events_groups:
            if event_group.active:
                active_group_count += 1
            else:
                pass
        available_group_indices: np.ndarray = np.flatnonzero(driver.results.has_event_group_results)
        if active_group_count == 1 and available_group_indices.size == 1:
            group_index: int = int(available_group_indices[0])
        else:
            raise RuntimeError(
                "The EMT example requires exactly one active and available event group"
            )

        # Solver status must be affirmative before any preallocated numerical
        # value can be presented as a successful native FMI result.
        well_initialized: bool = bool(driver.results.well_initialized[group_index])
        converged: bool = bool(driver.results.converged[group_index])
        if well_initialized and converged:
            pass
        else:
            raise RuntimeError(
                "The EMT example did not initialize and converge successfully"
            )

        final_time_seconds: float = float(driver.results.time_array[-1].value) * 1.0e-9
        final_time_matches: bool = bool(
            np.isclose(
                final_time_seconds,
                driver.options.simulation_time,
                rtol=0.0,
                atol=1.0e-12,
            )
        )
        if final_time_matches:
            pass
        else:
            raise RuntimeError("The EMT example did not reach its configured terminal time")

        i_a_var: Var = load.emt_model.external_mapping[VarPowerFlowReferenceType.i_A]
        i_b_var: Var = load.emt_model.external_mapping[VarPowerFlowReferenceType.i_B]
        i_c_var: Var = load.emt_model.external_mapping[VarPowerFlowReferenceType.i_C]
        i_a_final: float | None = _try_get_result_value(
            driver.results.values, driver.results.uid2idx.get(i_a_var.uid, None)
        )
        i_b_final: float | None = _try_get_result_value(
            driver.results.values, driver.results.uid2idx.get(i_b_var.uid, None)
        )
        i_c_final: float | None = _try_get_result_value(
            driver.results.values, driver.results.uid2idx.get(i_c_var.uid, None)
        )
        if i_a_final is not None and i_b_final is not None and i_c_final is not None:
            currents: np.ndarray = np.array([i_a_final, i_b_final, i_c_final], dtype=float)
        else:
            raise RuntimeError("The EMT example did not record all three phase currents")

        currents_are_finite: bool = bool(np.all(np.isfinite(currents)))
        max_abs_current: float = float(np.max(np.abs(currents)))
        current_balance: float = float(np.sum(currents))
        if currents_are_finite and max_abs_current >= 1.0e-8 and abs(current_balance) <= 1.0e-6:
            pass
        else:
            raise RuntimeError(
                "The EMT example currents are non-finite, placeholders, or unbalanced"
            )

        return (
            f"event_group_count = {active_group_count}",
            f"well_initialized = {well_initialized}",
            f"converged = {converged}",
            f"final_time_seconds = {final_time_seconds:.12f}",
            f"iA_final = {i_a_final:.8f}",
            f"iB_final = {i_b_final:.8f}",
            f"iC_final = {i_c_final:.8f}",
            f"current_balance = {current_balance:.8e}",
        )


def _try_get_result_value(values: np.ndarray, column_index: int | None) -> float | None:
    """Try to recover one scalar value from a VeraGrid results matrix.

    :param values: Results matrix.
    :param column_index: Candidate variable column index.
    :return: Final scalar value when available.
    """

    if column_index is None:
        return None
    else:
        flat_values: np.ndarray = np.ravel(values[-1, column_index])
        if flat_values.size > 0:
            return float(flat_values[0])
        else:
            return None


def run_rms_cs_example(output_dir: Path) -> Path:
    """Run the full RMS Co-Simulation FMU device example.

    :param output_dir: Output directory used for the FMU and the report.
    :return: Generated report path.
    """

    fmu_path: Path = export_example_rms_cs_fmu(output_dir)
    report_path: Path = output_dir / "rms_cs_example_report.txt"
    if _has_fmpy():
        pass
    else:
        lines: tuple[str, ...] = (
            f"fmu_path = {fmu_path}",
            "mode = CoSimulation",
            "status = skipped",
            "reason = fmpy not installed in this Python environment",
        )
        return write_example_report(report_path, lines)

    grid: MultiCircuit
    load: Load
    grid, load = _build_rms_demo_grid()
    pf_driver: PowerFlowDriver = PowerFlowDriver(grid=grid, options=_build_power_flow_options())
    pf_driver.run()
    p_default: float
    q_default: float
    p_default, q_default = _get_bus_power_default(grid, pf_driver.results, load.bus)

    request = FmuDeviceAttachmentRequest(
        fmu_path=fmu_path,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.CO_SIMULATION,
        input_bindings=tuple(),
        output_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.P, "p_out"),
            FmuRefBinding(VarPowerFlowReferenceType.Q, "q_out"),
        ),
        output_defaults=(
            FmuReferenceValue(VarPowerFlowReferenceType.P, p_default),
            FmuReferenceValue(VarPowerFlowReferenceType.Q, q_default),
        ),
        extraction_root=output_dir,
    )

    # The imported FMU is attached as a normal load device shell before running the RMS driver.
    attach_fmu_to_device(load, grid, request)

    rms_driver: RmsSimulationDriver = RmsSimulationDriver(
        grid=grid,
        options=RmsOptions(time_step=1e-3, simulation_time=5e-3, tolerance=1e-6, integration_method=DynamicIntegrationMethod.DaeBackEuler, max_iter=50),
        pf_results=pf_driver.results,
    )
    rms_driver.run()

    if rms_driver.problem is None:
        raise RuntimeError("The RMS example did not keep a reference to the simulation problem")
    else:
        final_snapshot: np.ndarray = _build_final_rms_snapshot(rms_driver)
        final_time_seconds: float = float(rms_driver.results.time_array[-1].value) * 1e-9
        _refresh_rms_fmu_outputs_from_final_snapshot(rms_driver.problem, load, final_snapshot, final_time_seconds)
        p_value = _read_rms_fmu_output(rms_driver.problem, load, VarPowerFlowReferenceType.P)
        q_value = _read_rms_fmu_output(rms_driver.problem, load, VarPowerFlowReferenceType.Q)
        p_text: str = "not available" if p_value is None else f"{p_value:.8f}"
        q_text: str = "not available" if q_value is None else f"{q_value:.8f}"

    lines: tuple[str, ...] = (
        f"fmu_path = {fmu_path}",
        f"mode = {request.mode.value}",
        f"final_time = {rms_driver.results.time_array[-1]}",
        f"P_final = {p_text}",
        f"Q_final = {q_text}",
    )
    return write_example_report(report_path, lines)


def run_rms_me_example(output_dir: Path) -> Path:
    """Run the full RMS Model Exchange FMU device example.

    :param output_dir: Output directory used for the FMU and the report.
    :return: Generated report path.
    """

    fmu_path: Path = export_example_rms_me_fmu(output_dir)
    report_path: Path = output_dir / "rms_me_example_report.txt"
    if _has_fmpy():
        pass
    else:
        lines: tuple[str, ...] = (
            f"fmu_path = {fmu_path}",
            "mode = ModelExchange",
            "status = skipped",
            "reason = fmpy not installed in this Python environment",
        )
        return write_example_report(report_path, lines)

    grid: MultiCircuit
    load: Load
    grid, load = _build_rms_demo_grid()
    pf_driver: PowerFlowDriver = PowerFlowDriver(grid=grid, options=_build_power_flow_options())
    pf_driver.run()
    p_default, q_default = _get_bus_power_default(grid, pf_driver.results, load.bus)

    request = FmuDeviceAttachmentRequest(
        fmu_path=fmu_path,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.MODEL_EXCHANGE,
        input_bindings=(FmuRefBinding(VarPowerFlowReferenceType.Vm, "u"),),
        output_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.P, "p_out"),
            FmuRefBinding(VarPowerFlowReferenceType.Q, "q_out"),
        ),
        output_defaults=(
            FmuReferenceValue(VarPowerFlowReferenceType.P, p_default),
            FmuReferenceValue(VarPowerFlowReferenceType.Q, q_default),
        ),
        extraction_root=output_dir,
        integration_method=FmuMeIntegrationMethod.EXPLICIT_EULER,
    )

    attach_fmu_to_device(load, grid, request)

    rms_driver: RmsSimulationDriver = RmsSimulationDriver(
        grid=grid,
        options=RmsOptions(time_step=1e-3, simulation_time=5e-3, tolerance=1e-6, integration_method=DynamicIntegrationMethod.DaeBackEuler, max_iter=50),
        pf_results=pf_driver.results,
    )
    rms_driver.run()

    if rms_driver.problem is None:
        raise RuntimeError("The RMS example did not keep a reference to the simulation problem")
    else:
        final_snapshot = _build_final_rms_snapshot(rms_driver)
        final_time_seconds = float(rms_driver.results.time_array[-1].value) * 1e-9
        _refresh_rms_fmu_outputs_from_final_snapshot(rms_driver.problem, load, final_snapshot, final_time_seconds)
        p_value = _read_rms_fmu_output(rms_driver.problem, load, VarPowerFlowReferenceType.P)
        q_value = _read_rms_fmu_output(rms_driver.problem, load, VarPowerFlowReferenceType.Q)
        p_text = "not available" if p_value is None else f"{p_value:.8f}"
        q_text = "not available" if q_value is None else f"{q_value:.8f}"

    lines: tuple[str, ...] = (
        f"fmu_path = {fmu_path}",
        f"mode = {request.mode.value}",
        f"final_time = {rms_driver.results.time_array[-1]}",
        f"P_final = {p_text}",
        f"Q_final = {q_text}",
    )
    return write_example_report(report_path, lines)


def run_emt_cs_example(output_dir: Path) -> Path:
    """Run the full EMT Co-Simulation FMU device example.

    :param output_dir: Output directory used for the FMU and the report.
    :return: Generated report path.
    """

    fmu_path: Path = export_example_emt_cs_fmu(output_dir)
    report_path: Path = output_dir / "emt_cs_example_report.txt"
    if _has_fmpy():
        pass
    else:
        lines: tuple[str, ...] = (
            f"fmu_path = {fmu_path}",
            "mode = CoSimulation",
            "status = skipped",
            "reason = fmpy not installed in this Python environment",
        )
        return write_example_report(report_path, lines)

    grid: MultiCircuit
    load: Load
    grid, load = _build_emt_demo_grid()
    grid.add_emt_events_group(EmtEventsGroup(name="default_emt_cs_example_group"))
    pf_driver: PowerFlowDriver = PowerFlowDriver(grid=grid, options=_build_power_flow_options())
    pf_driver.run()

    request = FmuDeviceAttachmentRequest(
        fmu_path=fmu_path,
        domain=FmuDeviceDomain.EMT,
        mode=FmuInterfaceMode.CO_SIMULATION,
        input_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.v_A, "v_a_in"),
            FmuRefBinding(VarPowerFlowReferenceType.v_B, "v_b_in"),
            FmuRefBinding(VarPowerFlowReferenceType.v_C, "v_c_in"),
        ),
        output_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.i_A, "i_a_out"),
            FmuRefBinding(VarPowerFlowReferenceType.i_B, "i_b_out"),
            FmuRefBinding(VarPowerFlowReferenceType.i_C, "i_c_out"),
        ),
        output_defaults=(
            FmuReferenceValue(VarPowerFlowReferenceType.i_A, 0.0),
            FmuReferenceValue(VarPowerFlowReferenceType.i_B, 0.0),
            FmuReferenceValue(VarPowerFlowReferenceType.i_C, 0.0),
        ),
        extraction_root=output_dir,
    )

    # The public attachment stores the declarative device configuration. The
    # real EMT problem reconstructs and registers the native adapter from it.
    attach_fmu_to_device(load, grid, request)
    emt_driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=EmtOptions(
            time_step=5.0e-6,
            simulation_time=1.0e-3,
            tolerance=1.0e-6,
            solver_type=EmtSolverTypes.Symbolic,
            integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
            initialization_method=EmtInitializationMethod.Auto,
            verbose=0,
        ),
        pf_results=pf_driver.results,
        pf_results_3ph=None,
    )
    emt_driver.run()

    lines: tuple[str, ...] = (
        f"fmu_path = {fmu_path}",
        f"mode = {request.mode.value}",
    ) + _build_emt_results_summary(emt_driver, load)
    return write_example_report(report_path, lines)


def run_emt_me_example(output_dir: Path) -> Path:
    """Run the full EMT Model Exchange FMU device example.

    :param output_dir: Output directory used for the FMU and the report.
    :return: Generated report path.
    """

    fmu_path: Path = export_example_emt_me_fmu(output_dir)
    report_path: Path = output_dir / "emt_me_example_report.txt"
    if _has_fmpy():
        pass
    else:
        lines: tuple[str, ...] = (
            f"fmu_path = {fmu_path}",
            "mode = ModelExchange",
            "status = skipped",
            "reason = fmpy not installed in this Python environment",
        )
        return write_example_report(report_path, lines)

    grid: MultiCircuit
    load: Load
    grid, load = _build_emt_demo_grid()
    grid.add_emt_events_group(EmtEventsGroup(name="default_emt_me_example_group"))
    pf_driver: PowerFlowDriver = PowerFlowDriver(grid=grid, options=_build_power_flow_options())
    pf_driver.run()

    request = FmuDeviceAttachmentRequest(
        fmu_path=fmu_path,
        domain=FmuDeviceDomain.EMT,
        mode=FmuInterfaceMode.MODEL_EXCHANGE,
        input_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.v_A, "u"),
            FmuRefBinding(VarPowerFlowReferenceType.v_B, "v_b_in"),
            FmuRefBinding(VarPowerFlowReferenceType.v_C, "v_c_in"),
        ),
        output_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.i_A, "i_a_out"),
            FmuRefBinding(VarPowerFlowReferenceType.i_B, "i_b_out"),
            FmuRefBinding(VarPowerFlowReferenceType.i_C, "i_c_out"),
        ),
        output_defaults=(
            FmuReferenceValue(VarPowerFlowReferenceType.i_A, 0.0),
            FmuReferenceValue(VarPowerFlowReferenceType.i_B, 0.0),
            FmuReferenceValue(VarPowerFlowReferenceType.i_C, 0.0),
        ),
        extraction_root=output_dir,
        integration_method=FmuMeIntegrationMethod.EXPLICIT_EULER,
    )

    # The bus template already exposes the real phase-A voltage reference used
    # by the Model Exchange input binding.
    attach_fmu_to_device(load, grid, request)
    emt_driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=EmtOptions(
            time_step=5.0e-6,
            simulation_time=1.0e-3,
            tolerance=1.0e-6,
            solver_type=EmtSolverTypes.Symbolic,
            integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
            initialization_method=EmtInitializationMethod.Auto,
            verbose=0,
        ),
        pf_results=pf_driver.results,
        pf_results_3ph=None,
    )
    emt_driver.run()

    lines: tuple[str, ...] = (
        f"fmu_path = {fmu_path}",
        f"mode = {request.mode.value}",
    ) + _build_emt_results_summary(emt_driver, load)
    return write_example_report(report_path, lines)
