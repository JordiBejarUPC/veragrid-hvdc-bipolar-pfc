from __future__ import annotations

from pathlib import Path

import pytest

from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.fmu.exporter.build import host_build_capable
from VeraGridEngine.IO.fmu.exporter.compat import Block, Var
from VeraGridEngine.IO.fmu.importer.examples.common import (
    _build_emt_demo_grid,
    _build_power_flow_options,
    export_example_emt_cs_fmu,
    export_example_emt_me_fmu,
    run_emt_cs_example,
    run_emt_me_example,
)
from VeraGridEngine.IO.fmu.importer.experimental_cs import FmuRefBinding, _build_template_block
from VeraGridEngine.IO.fmu.importer.experimental_me import FmuMeIntegrationMethod
from VeraGridEngine.IO.fmu.importer.model_description import FmuInterfaceMode
from VeraGridEngine.IO.fmu.importer.user_api import (
    FmuDeviceAttachmentRequest,
    FmuDeviceDomain,
    FmuReferenceValue,
    attach_fmu_to_device,
)
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    VarPowerFlowReferenceType,
)


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_emt_cs_example_runs_end_to_end(tmp_path: Path) -> None:
    """Run the native EMT Co-Simulation example through the real driver.

    :param tmp_path: Isolated FMU, staging, and report directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    report_path: Path = run_emt_cs_example(tmp_path)
    report_text: str = report_path.read_text(encoding="utf-8")

    assert report_path.exists()
    assert "mode = CoSimulation" in report_text
    assert "event_group_count = 1" in report_text
    assert "well_initialized = True" in report_text
    assert "converged = True" in report_text
    assert "final_time_seconds = 0.001000000000" in report_text
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_emt_me_example_runs_end_to_end(tmp_path: Path) -> None:
    """Run the native EMT Model Exchange example through the real driver.

    :param tmp_path: Isolated FMU, staging, and report directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    inspection_fmu_path: Path = export_example_emt_me_fmu(tmp_path)
    inspection_grid: MultiCircuit
    inspection_load: Load
    inspection_grid, inspection_load = _build_emt_demo_grid()
    inspection_request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=inspection_fmu_path,
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
        extraction_root=tmp_path,
        integration_method=FmuMeIntegrationMethod.EXPLICIT_EULER,
    )
    attached_block: Block = attach_fmu_to_device(
        inspection_load,
        inspection_grid,
        inspection_request,
    )
    copied_block: Block = attached_block.copy()
    candidate_block: Block
    reference: VarPowerFlowReferenceType
    for candidate_block in (attached_block, copied_block):
        for reference in (
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
        ):
            input_var: Var | None = candidate_block.external_mapping.get(reference, None)
            matching_input_vars: list[Var] = [
                candidate_var
                for candidate_var in candidate_block.in_vars
                if candidate_var.ref == reference
            ]
            assert input_var is not None
            assert len(matching_input_vars) == 1
            assert input_var is matching_input_vars[0]
            assert input_var.ref == reference

    report_path: Path = run_emt_me_example(tmp_path)
    report_text: str = report_path.read_text(encoding="utf-8")

    assert report_path.exists()
    assert "mode = ModelExchange" in report_text
    assert "event_group_count = 1" in report_text
    assert "well_initialized = True" in report_text
    assert "converged = True" in report_text
    assert "final_time_seconds = 0.001000000000" in report_text
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_emt_driver_releases_native_runtime_after_failed_solve(tmp_path: Path) -> None:
    """Prove driver-owned native runtimes close after a failed EMT solve.

    :param tmp_path: Isolated FMU and staging directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    collision_factory: VarFactory = VarFactory(name="EmtFmuCollisionFactory")
    variable_count_before: int = len(collision_factory.get_vars_dict())
    with pytest.raises(ValueError, match="cannot be both an input and an output"):
        _build_template_block(
            vfactory=collision_factory,
            name="emt_fmu_collision",
            output_bindings=(
                FmuRefBinding(VarPowerFlowReferenceType.v_A, "voltage_output"),
            ),
            output_defaults=None,
            input_bindings=(
                FmuRefBinding(VarPowerFlowReferenceType.v_A, "voltage_input"),
            ),
        )
    assert len(collision_factory.get_vars_dict()) == variable_count_before

    fmu_path: Path = export_example_emt_cs_fmu(tmp_path)
    grid: MultiCircuit
    load: Load
    grid, load = _build_emt_demo_grid()
    grid.add_emt_events_group(EmtEventsGroup(name="failed_native_cleanup_group"))

    # Solve the static operating point before replacing the load's dynamic
    # model with the declarative FMU attachment.
    pf_driver: PowerFlowDriver = PowerFlowDriver(grid=grid, options=_build_power_flow_options())
    pf_driver.run()
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
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
        extraction_root=tmp_path,
    )
    attached_block: Block = attach_fmu_to_device(load, grid, request)
    copied_block: Block = attached_block.copy()
    candidate_block: Block
    reference: VarPowerFlowReferenceType
    for candidate_block in (attached_block, copied_block):
        for reference in (
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
        ):
            input_var: Var | None = candidate_block.external_mapping.get(reference, None)
            matching_input_vars: list[Var] = [
                candidate_var
                for candidate_var in candidate_block.in_vars
                if candidate_var.ref == reference
            ]
            assert input_var is not None
            assert len(matching_input_vars) == 1
            assert input_var is matching_input_vars[0]
            assert input_var.ref == reference

    # Zero initialization iterations deliberately produces a failed status
    # after the real boundary runtime has been opened by simulate().
    emt_driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=EmtOptions(
            time_step=5.0e-6,
            simulation_time=1.0e-3,
            tolerance=1.0e-6,
            solver_type=EmtSolverTypes.Symbolic,
            integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
            initialization_method=EmtInitializationMethod.ConsistentNewton,
            init_newton_max_iter=0,
            verbose=0,
        ),
        pf_results=pf_driver.results,
        pf_results_3ph=None,
    )
    emt_driver.run()

    if emt_driver.results is None:
        raise AssertionError("The failed EMT solve did not publish its status")
    else:
        assert not bool(emt_driver.results.well_initialized[0])
        assert not bool(emt_driver.results.converged[0])
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()
