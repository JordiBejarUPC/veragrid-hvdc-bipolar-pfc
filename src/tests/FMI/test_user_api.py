from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from VeraGridEngine.IO.fmu.exporter.api import export_fmu
from VeraGridEngine.IO.fmu.exporter.build import host_build_capable
from VeraGridEngine.IO.fmu.exporter.config import ExportConfig as CsExportConfig, detect_target_platform as detect_cs_target_platform
from VeraGridEngine.IO.fmu.exporter.compat import Block, Const, Var
from VeraGridEngine.IO.fmu.importer.bindings import (
    FmiThreeFloat64ConfigurationValue,
    FmiThreeUInt64ConfigurationValue,
    FmuImportConfig,
    FmuRefBinding,
)
from VeraGridEngine.IO.fmu.importer.device_config import (
    FmuCsDeviceConfigRecord,
    FmuMeDeviceConfigRecord,
    load_fmu_cs_device_config,
    load_fmu_me_device_config,
    restore_fmu_cs_spec_from_record,
    restore_fmu_me_spec_from_record,
)
from VeraGridEngine.IO.fmu.importer.device_api import attach_rms_fmu_cs_device
from VeraGridEngine.IO.fmu.importer.errors import FmuImportError, FmuModeError
from VeraGridEngine.IO.fmu.importer.emt_boundary import (
    CompositeEmtBoundaryUpdater,
)
from VeraGridEngine.IO.fmu.importer.co_simulation import (
    FmuCsDeviceAdapter,
    FmuCsDeviceSpec,
    FmuCsDomain,
    build_fmu_cs_device_spec,
)
from VeraGridEngine.IO.fmu.importer.model_exchange import (
    FmuMeDeviceAdapter,
    FmuMeDeviceSpec,
    FmuMeDomain,
    FmuMeIntegrationMethod,
    RmsFmuMeDeviceAdapter,
    build_fmu_me_device_spec,
    get_next_rms_fmu_me_event_time,
    _prepare_rms_fmu_me_state_event_retry,
    resolve_rms_fmu_me_devices,
)
from VeraGridEngine.IO.fmu.importer.model_description import FmuInterfaceMode
from VeraGridEngine.IO.fmu.importer.user_api import (
    FmuDeviceAttachmentRequest,
    FmuDeviceDomain,
    FmuReferenceValue,
)
from VeraGridEngine.IO.fmu.importer.user_api import attach_fmu_to_device
from VeraGridEngine.IO.fmu.importer.runtime_worker_host import (
    FmiThreeWorkerHostLimits,
)
from VeraGridEngine.IO.fmu.importer.runtime_profile import (
    FmiThreeWorkerFloat64Profile,
)
from VeraGridEngine.IO.fmu.exporter_me.api import export_fmu_me
from VeraGridEngine.IO.fmu.exporter_me.config import ExportConfig as MeExportConfig, detect_target_platform as detect_me_target_platform
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


class FakeGrid:
    __slots__ = ("var_factory",)

    def __init__(self) -> None:

        self.var_factory = VarFactory(name="UserApiVarFactory")


def _evaluate_linear_test_event_indicator(
    time_value: float,
    continuous_state_values: tuple[float, ...],
) -> tuple[float, ...]:
    """Evaluate the linear indicator used by the pure localization test.

    :param time_value: Probe time supplied by the localization algorithm.
    :param continuous_state_values: Interpolated continuous-state vector.
    :return: One indicator crossing zero when the state reaches ``2.5``.
    """

    _unused_time: float = time_value
    return (continuous_state_values[0] - 2.5,)


def _tmp_root() -> Path:
    root = Path(__file__).resolve().parent / ".tmp"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def build_cs_output_block() -> Block:
    x = Var("x")
    dx = Var("dx", base_var=x)
    y = Var("y")
    return Block(
        state_vars=[x],
        state_eqs=[Const(1.0)],
        algebraic_vars=[y],
        algebraic_eqs=[y - x],
        diff_vars=[dx],
        init_values={x: Const(0.0), y: Const(0.0)},
        init_eqs={y: Const(0.0)},
        out_vars=[y],
    )


def build_me_output_block() -> Block:
    x = Var("x")
    dx = Var("dx", base_var=x)
    y = Var("y")
    u = Var("u")
    return Block(
        state_vars=[x],
        state_eqs=[Const(1.0) + u],
        algebraic_vars=[y],
        algebraic_eqs=[y - x],
        diff_vars=[dx],
        init_values={x: Const(0.0), y: Const(0.0)},
        init_eqs={y: Const(0.0)},
        in_vars=[u],
        out_vars=[y],
    )


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_user_api_attaches_rms_cs_device() -> None:
    """Persist one public CS attachment request and its worker policy.

    :return: None.
    """

    pytest.importorskip("fmpy")

    output_root = _tmp_root()
    fmu_path = output_root / "user_api_rms_cs.fmu"
    try:
        exported_fmu = export_fmu(
            build_cs_output_block(),
            CsExportConfig(
                model_name="UserApiRmsCs",
                output_path=fmu_path,
                target_platform=detect_cs_target_platform(),
                compile_binary=True,
                keep_build_dir=False,
            ),
        )

        device: SimpleNamespace = SimpleNamespace(
            name="LoadA",
            device_type=DeviceType.LoadDevice,
            rms_model=Block(),
            rms_fmu_import_config="",
        )
        grid: FakeGrid = FakeGrid()
        worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
            maximum_frame_size=65536,
            maximum_float64_values_per_request=128,
            response_timeout_seconds=20.0,
            graceful_join_timeout_seconds=6.0,
            terminate_join_timeout_seconds=3.0,
            kill_join_timeout_seconds=1.0,
        )
        request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
            fmu_path=exported_fmu,
            domain=FmuDeviceDomain.RMS,
            mode=FmuInterfaceMode.CO_SIMULATION,
            input_bindings=tuple(),
            output_bindings=(
                FmuRefBinding(
                    reference=VarPowerFlowReferenceType.P,
                    fmu_variable_name="y",
                ),
            ),
            output_defaults=(FmuReferenceValue(reference=VarPowerFlowReferenceType.P, value=0.0),),
            worker_limits=worker_limits,
        )
        attach_fmu_to_device(device, grid, request)

        assert device.rms_fmu_import_config != ""
        restored_record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
            device.rms_fmu_import_config
        )
        if restored_record is not None:
            restored_limits: FmiThreeWorkerHostLimits | None = (
                restored_record.worker_limits
            )
        else:
            raise AssertionError("Attached CS device config did not reload")
        if restored_limits is not None:
            assert restored_limits.maximum_frame_size == 65536
            assert restored_limits.maximum_float64_values_per_request == 128
        else:
            raise AssertionError("Attached CS device lost its worker limits")
        assert restored_record.output_bindings[0].flat_index is None
        assert restored_record.configuration_float64_values == tuple()
        assert restored_record.configuration_uint64_values == tuple()
    finally:
        fmu_path.unlink(missing_ok=True)


def test_user_api_persists_fmi_three_array_declarations(
    compiled_fmi_three_configurable_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Persist indexed bindings and structural values from a real FMI 3 FMU.

    :param compiled_fmi_three_configurable_array_co_simulation_fmu: Generated
        configurable-array FMI 3 fixture.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    device: SimpleNamespace = SimpleNamespace(
        name="FmiThreeArrayLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=Block(),
        rms_fmu_import_config="",
    )
    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_configurable_array_co_simulation_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.CO_SIMULATION,
        input_bindings=tuple(),
        output_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.P,
                fmu_variable_name="array_output",
                flat_index=1,
            ),
        ),
        output_defaults=(
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.P,
                value=0.0,
            ),
        ),
        extraction_root=tmp_path,
        worker_limits=worker_limits,
        configuration_uint64_values=(
            FmiThreeUInt64ConfigurationValue(
                variable_name="structural_size",
                value=2,
            ),
        ),
    )
    attach_fmu_to_device(device, FakeGrid(), request)

    restored_record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        device.rms_fmu_import_config
    )
    if restored_record is not None:
        pass
    else:
        raise AssertionError("FMI 3 array attachment did not reload")
    assert restored_record.output_bindings[0].flat_index == 1
    assert restored_record.configuration_uint64_values[0].value == 2
    restored_spec: FmuCsDeviceSpec = restore_fmu_cs_spec_from_record(
        record=restored_record,
        block=device.rms_model,
        device_tpe=device.device_type,
    )
    assert (
        restored_spec.float64_profile
        == FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
    )
    adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=device,
        spec=restored_spec,
        output_param_indices=dict(),
    )
    try:
        initial_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.initialize_outputs(
                time_value=0.0,
                x_snapshot=np.zeros(0, dtype=float),
            )
        )
        assert initial_outputs[VarPowerFlowReferenceType.P] == pytest.approx(0.0)
        stepped_outputs: dict[VarPowerFlowReferenceType, float] = adapter.advance(
            current_time=0.0,
            step_size=0.25,
            x_snapshot=np.zeros(0, dtype=float),
        )
        assert stepped_outputs[VarPowerFlowReferenceType.P] == pytest.approx(
            0.35
        )
    finally:
        adapter.close()
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmu_device_attachment_preserves_existing_state_on_invalid_configuration(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Leave the destination untouched when provider validation fails.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated scalar FMI 3
        fixture.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    original_model: Block = Block()
    device: SimpleNamespace = SimpleNamespace(
        name="AtomicFmiThreeLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=original_model,
        rms_fmu_import_config="original-provider",
    )
    float64_configuration: FmiThreeFloat64ConfigurationValue = (
        FmiThreeFloat64ConfigurationValue(
            variable_name="structural_gain",
            values=(2.0,),
        )
    )
    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    with pytest.raises(
        ValueError,
        match="Duplicate FMI 3 Configuration Mode variable name",
    ):
        attach_rms_fmu_cs_device(
            device=device,
            vfactory=FakeGrid().var_factory,
            config=FmuImportConfig(
                fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
                preferred_mode=FmuInterfaceMode.CO_SIMULATION,
                extraction_root=tmp_path,
            ),
            input_bindings=tuple(),
            output_bindings=tuple(),
            name="invalid-atomic-attachment",
            worker_limits=worker_limits,
            configuration_float64_values=(float64_configuration,),
            configuration_uint64_values=(
                FmiThreeUInt64ConfigurationValue(
                    variable_name="structural_gain",
                    value=2,
                ),
            ),
        )
    assert device.rms_model is original_model
    assert device.rms_fmu_import_config == "original-provider"

    accepted_bound: int
    for accepted_bound in (1, 1024):
        accepted_request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
            fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
            domain=FmuDeviceDomain.RMS,
            mode=FmuInterfaceMode.MODEL_EXCHANGE,
            input_bindings=tuple(),
            output_bindings=tuple(),
            maximum_event_iterations=accepted_bound,
        )
        assert accepted_request.maximum_event_iterations == accepted_bound

    rejected_bound: object
    for rejected_bound in (True, False, 0, 1025):
        with pytest.raises(ValueError, match="maximum Event Mode iterations"):
            FmuDeviceAttachmentRequest(
                fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
                domain=FmuDeviceDomain.RMS,
                mode=FmuInterfaceMode.MODEL_EXCHANGE,
                input_bindings=tuple(),
                output_bindings=tuple(),
                maximum_event_iterations=rejected_bound,
            )


def test_indexed_bindings_fail_before_any_runtime() -> None:
    """Reject indexed CS and ME bindings before FMI-version dispatch.

    :return: None.
    """

    indexed_binding: FmuRefBinding = FmuRefBinding(
        reference=VarPowerFlowReferenceType.P,
        fmu_variable_name="scalar_output",
        flat_index=0,
    )
    unopened_config: FmuImportConfig = FmuImportConfig(
        fmu_path="runtime-must-not-open.fmu",
    )
    cs_spec: FmuCsDeviceSpec = FmuCsDeviceSpec(
        domain=FmuCsDomain.RMS,
        config=unopened_config,
        device_tpe=DeviceType.LoadDevice,
        input_bindings=tuple(),
        output_bindings=(indexed_binding,),
        output_defaults=dict(),
        output_param_uids=dict(),
        worker_limits=None,
        float64_profile=None,
    )
    cs_adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=cs_spec,
        output_param_indices=dict(),
    )
    with pytest.raises(FmuModeError, match="indexed device bindings"):
        cs_adapter.initialize_outputs(
            time_value=0.0,
            x_snapshot=np.zeros(0, dtype=float),
        )

    fmi_two_configuration_spec: FmuCsDeviceSpec = FmuCsDeviceSpec(
        domain=FmuCsDomain.RMS,
        config=unopened_config,
        device_tpe=DeviceType.LoadDevice,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_uids=dict(),
        worker_limits=None,
        float64_profile=None,
        configuration_float64_values=(
            FmiThreeFloat64ConfigurationValue(
                variable_name="structural_gain",
                values=(2.0,),
            ),
        ),
    )
    fmi_two_configuration_adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=fmi_two_configuration_spec,
        output_param_indices=dict(),
    )
    with pytest.raises(FmuModeError, match="require FMI 3"):
        fmi_two_configuration_adapter.initialize_outputs(
            time_value=0.0,
            x_snapshot=np.zeros(0, dtype=float),
        )

    me_spec: FmuMeDeviceSpec = FmuMeDeviceSpec(
        domain=FmuMeDomain.RMS,
        config=unopened_config,
        device_tpe=DeviceType.LoadDevice,
        input_variable_names=tuple(),
        output_variable_names=("scalar_output",),
        state_variable_names=tuple(),
        derivative_variable_names=tuple(),
        integration_method=FmuMeIntegrationMethod.EXPLICIT_EULER,
        worker_limits=None,
        float64_profile=None,
        input_bindings=tuple(),
        output_bindings=(indexed_binding,),
        output_defaults=dict(),
        output_param_uids=dict(),
    )
    me_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(me_spec)
    with pytest.raises(FmuModeError, match="indexed device bindings"):
        me_adapter.initialize(start_time=0.0)


def test_fmi_three_cs_device_spec_owns_derived_worker_profile(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
    compiled_fmi_three_configurable_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Restore one attached FMI 3 CS spec without opening its worker.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture.
    :param compiled_fmi_three_constant_array_co_simulation_fmu: Generated
        constant-array native fixture.
    :param compiled_fmi_three_configurable_array_co_simulation_fmu: Generated
        configurable-array native fixture.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        preferred_mode=FmuInterfaceMode.CO_SIMULATION,
        extraction_root=tmp_path,
    )
    input_bindings: tuple[FmuRefBinding, ...] = (
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.Vm,
            fmu_variable_name="control_input",
        ),
    )
    output_bindings: tuple[FmuRefBinding, ...] = (
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.P,
            fmu_variable_name="observed_output",
        ),
    )
    with pytest.raises(ValueError, match="require explicit worker limits"):
        build_fmu_cs_device_spec(
            domain=FmuCsDomain.RMS,
            config=config,
            device_tpe=DeviceType.LoadDevice,
            input_bindings=input_bindings,
            output_bindings=output_bindings,
        )
    indexed_spec: FmuCsDeviceSpec = build_fmu_cs_device_spec(
        domain=FmuCsDomain.RMS,
        config=config,
        device_tpe=DeviceType.LoadDevice,
        input_bindings=tuple(),
        output_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.P,
                fmu_variable_name="observed_output",
                flat_index=0,
            ),
        ),
        worker_limits=worker_limits,
    )
    indexed_adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=indexed_spec,
        output_param_indices=dict(),
    )
    try:
        indexed_outputs: dict[VarPowerFlowReferenceType, float] = (
            indexed_adapter.initialize_outputs(
                time_value=0.0,
                x_snapshot=np.zeros(0, dtype=float),
            )
        )
        assert indexed_outputs[VarPowerFlowReferenceType.P] == pytest.approx(
            0.0
        )
    finally:
        indexed_adapter.close()

    with pytest.raises(FmuModeError, match="complete value provider"):
        build_fmu_cs_device_spec(
            domain=FmuCsDomain.RMS,
            config=FmuImportConfig(
                fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
                preferred_mode=FmuInterfaceMode.CO_SIMULATION,
                extraction_root=tmp_path,
            ),
            device_tpe=DeviceType.LoadDevice,
            input_bindings=(
                FmuRefBinding(
                    reference=VarPowerFlowReferenceType.Vm,
                    fmu_variable_name="array_input",
                    flat_index=0,
                ),
            ),
            output_bindings=tuple(),
            worker_limits=worker_limits,
        )

    device: SimpleNamespace = SimpleNamespace(
        name="FmiThreeCsLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=Block(),
        rms_fmu_import_config="",
    )
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.CO_SIMULATION,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
        output_defaults=(
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.P,
                value=0.0,
            ),
        ),
        extraction_root=tmp_path,
        worker_limits=worker_limits,
    )
    attach_fmu_to_device(device, FakeGrid(), request)

    restored_record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        device.rms_fmu_import_config
    )
    if restored_record is not None:
        restored_spec: FmuCsDeviceSpec = restore_fmu_cs_spec_from_record(
            record=restored_record,
            block=device.rms_model,
            device_tpe=device.device_type,
        )
    else:
        raise AssertionError("Attached FMI 3 CS device config did not reload")
    assert restored_spec.float64_profile == FmiThreeWorkerFloat64Profile.SCALAR
    assert restored_spec.worker_limits is not None
    assert restored_spec.worker_limits.maximum_frame_size == 262144

    constant_array_spec: FmuCsDeviceSpec = build_fmu_cs_device_spec(
        domain=FmuCsDomain.RMS,
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
            preferred_mode=FmuInterfaceMode.CO_SIMULATION,
            extraction_root=tmp_path,
        ),
        device_tpe=DeviceType.LoadDevice,
        input_bindings=tuple(),
        output_bindings=tuple(),
        worker_limits=worker_limits,
    )
    assert (
        constant_array_spec.float64_profile
        == FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY
    )
    constant_array_adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=constant_array_spec,
        output_param_indices=dict(),
    )
    try:
        constant_array_outputs: dict[VarPowerFlowReferenceType, float] = (
            constant_array_adapter.initialize_outputs(
                time_value=0.0,
                x_snapshot=np.zeros(0, dtype=float),
            )
        )
        assert constant_array_outputs == dict()
    finally:
        constant_array_adapter.close()
    assert constant_array_adapter.fmi_three_session is None
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()

    configurable_array_spec: FmuCsDeviceSpec = build_fmu_cs_device_spec(
        domain=FmuCsDomain.RMS,
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_configurable_array_co_simulation_fmu,
            preferred_mode=FmuInterfaceMode.CO_SIMULATION,
            extraction_root=tmp_path,
        ),
        device_tpe=DeviceType.LoadDevice,
        input_bindings=tuple(),
        output_bindings=tuple(),
        worker_limits=worker_limits,
    )
    assert (
        configurable_array_spec.float64_profile
        == FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
    )


def test_fmi_three_cs_device_adapter_uses_isolated_session(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Run a scalar CS device lifecycle without native code in the parent.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated worker staging parent supplied by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "cs-device-adapter-session"
    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    input_binding: FmuRefBinding = FmuRefBinding(
        reference=VarPowerFlowReferenceType.Vm,
        fmu_variable_name="control_input",
    )
    output_binding: FmuRefBinding = FmuRefBinding(
        reference=VarPowerFlowReferenceType.P,
        fmu_variable_name="observed_output",
    )
    voltage_variable: Var = Var("device_voltage")
    bus_external_mapping: dict[VarPowerFlowReferenceType, Var] = dict()
    bus_external_mapping[VarPowerFlowReferenceType.Vm] = voltage_variable
    bus_block: Block = Block(external_mapping=bus_external_mapping)
    device: SimpleNamespace = SimpleNamespace(
        name="FmiThreeCsLifecycleLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=Block(),
        rms_fmu_import_config="",
        bus=SimpleNamespace(rms_model=bus_block),
    )
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.CO_SIMULATION,
        input_bindings=(input_binding,),
        output_bindings=(output_binding,),
        output_defaults=(
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.P,
                value=0.0,
            ),
        ),
        extraction_root=staging_parent,
        worker_limits=worker_limits,
    )
    attach_fmu_to_device(device, FakeGrid(), request)
    record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        device.rms_fmu_import_config
    )
    if record is not None:
        pass
    else:
        raise AssertionError("Attached FMI 3 CS device config did not reload")
    spec: FmuCsDeviceSpec = restore_fmu_cs_spec_from_record(
        record=record,
        block=device.rms_model,
        device_tpe=device.device_type,
    )
    assert spec.float64_profile == FmiThreeWorkerFloat64Profile.SCALAR
    assert spec.worker_limits is not None
    assert spec.worker_limits.maximum_frame_size == 262144

    variable_indices: dict[int, int] = dict()
    variable_indices[voltage_variable.uid] = 0
    problem: SimpleNamespace = SimpleNamespace(uid2idx_vars=variable_indices)
    output_param_indices: dict[VarPowerFlowReferenceType, int] = dict()
    output_param_indices[VarPowerFlowReferenceType.P] = 0
    adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=problem,
        device=device,
        spec=spec,
        output_param_indices=output_param_indices,
    )

    try:
        initial_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.initialize_outputs(
                time_value=0.0,
                x_snapshot=np.array((2.0,), dtype=float),
            )
        )
        assert adapter.runtime_host is None
        assert adapter.fmi_three_session is not None
        assert initial_outputs[VarPowerFlowReferenceType.P] == pytest.approx(0.0)

        stepped_outputs: dict[VarPowerFlowReferenceType, float] = adapter.advance(
            current_time=0.0,
            step_size=0.25,
            x_snapshot=np.array((2.0,), dtype=float),
        )
        assert adapter.last_time == pytest.approx(0.25)
        assert stepped_outputs[VarPowerFlowReferenceType.P] == pytest.approx(2.25)
        target: np.ndarray = np.zeros(1, dtype=float)
        adapter.apply_outputs(target, stepped_outputs)
        assert target.tolist() == pytest.approx([2.25])

        with pytest.raises(FmuImportError, match="requested simulation termination"):
            adapter.advance(
                current_time=0.25,
                step_size=0.25,
                x_snapshot=np.array((9.0,), dtype=float),
            )
        assert adapter.last_time == pytest.approx(0.5)
        assert adapter.last_outputs[VarPowerFlowReferenceType.P] == pytest.approx(
            9.5
        )
    finally:
        adapter.close()
        adapter.close()

    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_me_selects_constant_array_device_outputs(
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Evaluate two selected elements from one constant ME output array.

    :param compiled_fmi_three_constant_array_co_simulation_fmu: Generated
        dual-interface constant-array FMI 3 fixture.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    output_bindings: tuple[FmuRefBinding, ...] = (
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.P,
            fmu_variable_name="array_output",
            flat_index=5,
        ),
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.Q,
            fmu_variable_name="array_output",
            flat_index=2,
        ),
    )
    spec: FmuMeDeviceSpec = build_fmu_me_device_spec(
        domain=FmuMeDomain.RMS,
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
            preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
            extraction_root=tmp_path / "me-constant-array-session",
        ),
        device_tpe=DeviceType.LoadDevice,
        input_variable_names=tuple(),
        output_variable_names=("array_output", "array_output"),
        worker_limits=worker_limits,
        output_bindings=output_bindings,
    )
    assert spec.float64_profile == FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY
    adapter: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=spec,
        output_param_indices={
            VarPowerFlowReferenceType.P: 0,
            VarPowerFlowReferenceType.Q: 1,
        },
    )
    second_adapter: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=spec,
        output_param_indices={
            VarPowerFlowReferenceType.P: 2,
            VarPowerFlowReferenceType.Q: 3,
        },
    )
    try:
        initial_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.initialize_outputs(
                time_value=0.5,
                x_snapshot=np.zeros(0, dtype=float),
            )
        )
        assert initial_outputs[VarPowerFlowReferenceType.P] == pytest.approx(2.6)
        assert initial_outputs[VarPowerFlowReferenceType.Q] == pytest.approx(1.5)
        second_adapter.initialize_outputs(
            time_value=0.5,
            x_snapshot=np.zeros(0, dtype=float),
        )
        stepped_outputs: dict[VarPowerFlowReferenceType, float] = adapter.advance(
            current_time=0.5,
            step_size=0.25,
            x_snapshot=np.zeros(0, dtype=float),
        )
        assert stepped_outputs[VarPowerFlowReferenceType.P] == pytest.approx(2.85)
        assert stepped_outputs[VarPowerFlowReferenceType.Q] == pytest.approx(1.75)
        second_adapter.advance(
            current_time=0.5,
            step_size=0.25,
            x_snapshot=np.zeros(0, dtype=float),
        )
        problem: SimpleNamespace = SimpleNamespace(
            _fmu_me_adapters=[adapter, second_adapter],
            _variable_parameters_values=np.zeros(4, dtype=float),
            _last_variable_parameters_values=None,
        )
        resolve_rms_fmu_me_devices(problem=problem, accepted=True)
        assert problem._variable_parameters_values.tolist() == pytest.approx(
            [2.85, 1.75, 2.85, 1.75]
        )
        assert adapter.runtime_adapter.fmi_three_coordinator is not None
        assert not adapter.runtime_adapter.fmi_three_coordinator.has_pending_candidate()
        assert second_adapter.runtime_adapter.fmi_three_coordinator is not None
        assert not second_adapter.runtime_adapter.fmi_three_coordinator.has_pending_candidate()
    finally:
        adapter.close()
        adapter.close()
        second_adapter.close()
        second_adapter.close()


def test_fmi_three_me_selects_configurable_array_device_outputs(
    compiled_fmi_three_configurable_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Restore and evaluate selected ME array elements in binding order.

    :param compiled_fmi_three_configurable_array_co_simulation_fmu: Generated
        dual-interface configurable-array FMI 3 fixture.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "me-configurable-array-session"
    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    device: SimpleNamespace = SimpleNamespace(
        name="FmiThreeMeArrayLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=Block(),
        rms_fmu_me_import_config="",
    )
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_configurable_array_co_simulation_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.MODEL_EXCHANGE,
        input_bindings=tuple(),
        output_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.P,
                fmu_variable_name="array_output",
                flat_index=1,
            ),
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.Q,
                fmu_variable_name="array_output",
                flat_index=0,
            ),
        ),
        output_defaults=(
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.P,
                value=0.0,
            ),
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.Q,
                value=0.0,
            ),
        ),
        extraction_root=staging_parent,
        worker_limits=worker_limits,
        configuration_uint64_values=(
            FmiThreeUInt64ConfigurationValue(
                variable_name="structural_size",
                value=2,
            ),
        ),
    )
    attach_fmu_to_device(device, FakeGrid(), request)
    record: FmuMeDeviceConfigRecord | None = load_fmu_me_device_config(
        device.rms_fmu_me_import_config
    )
    if record is not None:
        pass
    else:
        raise AssertionError("Attached FMI 3 ME array config did not reload")
    spec: FmuMeDeviceSpec = restore_fmu_me_spec_from_record(
        record=record,
        block=device.rms_model,
        device_tpe=device.device_type,
    )
    assert spec.output_bindings == record.output_bindings
    assert spec.configuration_uint64_values[0].value == 2

    adapter: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=device,
        spec=spec,
        output_param_indices=dict(),
    )
    try:
        initial_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.initialize_outputs(
                time_value=0.25,
                x_snapshot=np.zeros(0, dtype=float),
            )
        )
        assert initial_outputs[VarPowerFlowReferenceType.P] == pytest.approx(0.35)
        assert initial_outputs[VarPowerFlowReferenceType.Q] == pytest.approx(0.25)
        stepped_outputs: dict[VarPowerFlowReferenceType, float] = adapter.advance(
            current_time=0.25,
            step_size=0.25,
            x_snapshot=np.zeros(0, dtype=float),
        )
        assert stepped_outputs[VarPowerFlowReferenceType.P] == pytest.approx(0.6)
        assert stepped_outputs[VarPowerFlowReferenceType.Q] == pytest.approx(0.5)
        resolved_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.resolve_step(accepted=True)
        )
        assert resolved_outputs[VarPowerFlowReferenceType.P] == pytest.approx(0.6)
        assert resolved_outputs[VarPowerFlowReferenceType.Q] == pytest.approx(0.5)
        assert adapter.runtime_adapter.get_state_vector().size == 0
    finally:
        adapter.close()
        adapter.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_user_api_attaches_emt_me_device() -> None:
    pytest.importorskip("fmpy")

    output_root = _tmp_root()
    fmu_path = output_root / "user_api_emt_me.fmu"
    try:
        exported_fmu = export_fmu_me(
            build_me_output_block(),
            MeExportConfig(
                model_name="UserApiEmtMe",
                output_path=fmu_path,
                target_platform=detect_me_target_platform(),
                compile_binary=True,
                keep_build_dir=False,
            ),
        )

        device = SimpleNamespace(name="LoadB", device_type=DeviceType.LoadDevice, emt_model=Block(), emt_fmu_me_import_config="")
        grid = FakeGrid()
        worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
            maximum_frame_size=65536,
            maximum_float64_values_per_request=128,
            response_timeout_seconds=20.0,
            graceful_join_timeout_seconds=6.0,
            terminate_join_timeout_seconds=3.0,
            kill_join_timeout_seconds=1.0,
        )
        request = FmuDeviceAttachmentRequest(
            fmu_path=exported_fmu,
            domain=FmuDeviceDomain.EMT,
            mode=FmuInterfaceMode.MODEL_EXCHANGE,
            input_bindings=tuple(),
            output_bindings=(FmuRefBinding(reference=VarPowerFlowReferenceType.i_A, fmu_variable_name="y"),),
            output_defaults=(FmuReferenceValue(reference=VarPowerFlowReferenceType.i_A, value=0.0),),
            integration_method=FmuMeIntegrationMethod.EXPLICIT_EULER,
            worker_limits=worker_limits,
            maximum_event_iterations=19,
        )
        attach_fmu_to_device(device, grid, request)

        assert device.emt_fmu_me_import_config != ""
        restored_record: FmuMeDeviceConfigRecord | None = load_fmu_me_device_config(
            device.emt_fmu_me_import_config
        )
        if restored_record is not None:
            restored_limits: FmiThreeWorkerHostLimits | None = (
                restored_record.worker_limits
            )
        else:
            raise AssertionError("Attached ME device config did not reload")
        if restored_limits is not None:
            assert restored_limits.maximum_frame_size == 65536
            assert restored_limits.maximum_float64_values_per_request == 128
            assert restored_limits.response_timeout_seconds == 20.0
            assert restored_limits.graceful_join_timeout_seconds == 6.0
            assert restored_limits.terminate_join_timeout_seconds == 3.0
            assert restored_limits.kill_join_timeout_seconds == 1.0
        else:
            raise AssertionError("Attached ME device lost its FMI 3 worker limits")
        assert restored_record.maximum_event_iterations == 19
        restored_spec: FmuMeDeviceSpec = restore_fmu_me_spec_from_record(
            record=restored_record,
            block=device.emt_model,
            device_tpe=device.device_type,
        )
        runtime_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(restored_spec)
        try:
            runtime_adapter.initialize(start_time=0.0, input_values=dict())
            runtime_adapter._explicit_euler_bound_step(
                current_time=0.0,
                step_size=1.0,
                input_values=dict(),
            )
            assert runtime_adapter.get_state_vector().tolist() == pytest.approx(
                [1.0]
            )
            restored_values: tuple[float, ...] = (
                runtime_adapter.prepare_state_event_retry(event_time=None)
            )
            assert restored_values == pytest.approx((0.0,), abs=1.0e-9)
            assert runtime_adapter.get_state_vector().tolist() == pytest.approx(
                [0.0]
            )
        finally:
            runtime_adapter.close()
    finally:
        fmu_path.unlink(missing_ok=True)


def test_fmi_three_me_device_spec_owns_derived_worker_profile(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Build one FMI 3 ME device spec without opening its isolated worker.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture.
    :param compiled_fmi_three_constant_array_co_simulation_fmu: Generated
        constant-array dual-interface fixture.
    :param tmp_path: Isolated future staging parent provided by pytest.
    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
        extraction_root=tmp_path,
    )
    with pytest.raises(ValueError, match="require explicit worker limits"):
        build_fmu_me_device_spec(
            domain=FmuMeDomain.RMS,
            config=config,
            device_tpe=DeviceType.LoadDevice,
            input_variable_names=("control_input",),
            output_variable_names=("observed_output",),
        )
    output_binding: FmuRefBinding = FmuRefBinding(
        reference=VarPowerFlowReferenceType.P,
        fmu_variable_name="observed_output",
        flat_index=0,
    )
    spec: FmuMeDeviceSpec = build_fmu_me_device_spec(
        domain=FmuMeDomain.RMS,
        config=config,
        device_tpe=DeviceType.LoadDevice,
        input_variable_names=("control_input",),
        output_variable_names=("observed_output",),
        worker_limits=worker_limits,
        output_bindings=(output_binding,),
    )

    assert spec.float64_profile == FmiThreeWorkerFloat64Profile.SCALAR
    assert spec.worker_limits is worker_limits
    assert spec.state_variable_names == ("continuous_state",)
    assert spec.derivative_variable_names == ("state_derivative",)
    assert spec.output_bindings == (output_binding,)
    assert spec.maximum_event_iterations == 32

    accepted_event_bound: int
    for accepted_event_bound in (1, 1024):
        accepted_spec: FmuMeDeviceSpec = build_fmu_me_device_spec(
            domain=FmuMeDomain.RMS,
            config=config,
            device_tpe=DeviceType.LoadDevice,
            input_variable_names=("control_input",),
            output_variable_names=("observed_output",),
            worker_limits=worker_limits,
            maximum_event_iterations=accepted_event_bound,
        )
        assert accepted_spec.maximum_event_iterations == accepted_event_bound

    rejected_event_bound: object
    for rejected_event_bound in (True, False, 0, 1025):
        with pytest.raises(ValueError, match="maximum Event Mode iterations"):
            build_fmu_me_device_spec(
                domain=FmuMeDomain.RMS,
                config=config,
                device_tpe=DeviceType.LoadDevice,
                input_variable_names=("control_input",),
                output_variable_names=("observed_output",),
                worker_limits=worker_limits,
                maximum_event_iterations=rejected_event_bound,
            )

    with pytest.raises(FmuModeError, match="array inputs require a complete"):
        build_fmu_me_device_spec(
            domain=FmuMeDomain.RMS,
            config=FmuImportConfig(
                fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
                preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
                extraction_root=tmp_path / "rejected-me-array-input",
            ),
            device_tpe=DeviceType.LoadDevice,
            input_variable_names=("array_input",),
            output_variable_names=("array_output",),
            worker_limits=worker_limits,
            output_bindings=(
                FmuRefBinding(
                    reference=VarPowerFlowReferenceType.P,
                    fmu_variable_name="array_output",
                    flat_index=0,
                ),
            ),
        )


def test_fmi_three_me_device_adapter_uses_isolated_session(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Evaluate one FMI 3 ME device without loading native code in the parent.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "device-adapter-session"
    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    device: SimpleNamespace = SimpleNamespace(
        name="FmiThreeLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=Block(),
        rms_fmu_me_import_config="",
    )
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.MODEL_EXCHANGE,
        input_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.Vm,
                fmu_variable_name="control_input",
            ),
        ),
        output_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.P,
                fmu_variable_name="observed_output",
            ),
        ),
        output_defaults=(
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.P,
                value=0.0,
            ),
        ),
        extraction_root=staging_parent,
        worker_limits=worker_limits,
        maximum_event_iterations=11,
        configuration_float64_values=(
            FmiThreeFloat64ConfigurationValue(
                variable_name="structural_gain",
                values=(2.0,),
            ),
        ),
    )
    attach_fmu_to_device(device, FakeGrid(), request)
    record: FmuMeDeviceConfigRecord | None = load_fmu_me_device_config(
        device.rms_fmu_me_import_config
    )
    if record is not None:
        pass
    else:
        raise AssertionError("Attached FMI 3 ME device config did not reload")
    spec: FmuMeDeviceSpec = restore_fmu_me_spec_from_record(
        record=record,
        block=device.rms_model,
        device_tpe=device.device_type,
    )
    assert spec.float64_profile == FmiThreeWorkerFloat64Profile.SCALAR
    assert spec.worker_limits is not None
    assert spec.worker_limits.maximum_frame_size == 262144
    assert spec.maximum_event_iterations == 11
    assert spec.configuration_float64_values[0].values == (2.0,)
    adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(spec)
    with pytest.raises(ValueError, match="unbound input"):
        adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=2.0),
            start_values=dict(unbound_parameter=1.0),
        )
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


    try:
        adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=2.0),
        )
        assert adapter.runtime_host is None
        assert adapter.fmi_three_coordinator is not None
        assert adapter.get_state_vector().tolist() == pytest.approx([1.0])
        derivative_values: list[float] = adapter.evaluate_derivatives(
            time_value=0.25,
            input_values=dict(control_input=2.0),
        ).tolist()
        assert derivative_values == pytest.approx([1.0])
        output_values: dict[str, float] = adapter.evaluate_outputs(
            time_value=0.25,
            input_values=dict(control_input=2.0),
        )
        assert output_values == pytest.approx(dict(observed_output=0.0))
        prepared_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter._explicit_euler_bound_step(
                current_time=0.0,
                step_size=0.25,
                input_values=dict(control_input=2.0),
            )
        )
        assert prepared_outputs == pytest.approx(
            {VarPowerFlowReferenceType.P: 0.0}
        )
        assert adapter.fmi_three_coordinator.has_pending_candidate()
        assert adapter.get_state_vector().tolist() == pytest.approx([1.25])
        rejected_values: tuple[float, ...] | None = (
            adapter.resolve_pending_step(accepted=False)
        )
        assert rejected_values == pytest.approx((0.0,))
        assert not adapter.fmi_three_coordinator.has_pending_candidate()
        assert adapter.get_state_vector().tolist() == pytest.approx([1.0])
        stepped_outputs: dict[str, float] = adapter.explicit_euler_step(
            current_time=0.0,
            step_size=0.25,
            input_values=dict(control_input=2.0),
        )
        assert adapter.get_state_vector().tolist() == pytest.approx([1.25])
        assert stepped_outputs == pytest.approx(dict(observed_output=0.0))
        assert not adapter.fmi_three_coordinator.has_pending_candidate()
    finally:
        adapter.close()
        adapter.close()

    direct_state_event_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(spec)
    try:
        direct_state_event_adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=4.0),
        )
        with pytest.raises(
            FmuModeError,
            match="solver-owned localization path",
        ):
            direct_state_event_adapter.explicit_euler_step(
                current_time=0.0,
                step_size=1.0,
                input_values=dict(control_input=4.0),
            )
        assert direct_state_event_adapter.get_state_vector().tolist() == pytest.approx(
            [1.0]
        )
        assert not direct_state_event_adapter.fmi_three_coordinator.has_pending_candidate()
    finally:
        direct_state_event_adapter.close()

    time_event_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(spec)
    try:
        time_event_adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=7.0),
        )
        assert time_event_adapter.get_next_event_time() == pytest.approx(0.25)
        time_event_problem: SimpleNamespace = SimpleNamespace(
            _fmu_me_adapters=[
                SimpleNamespace(runtime_adapter=time_event_adapter)
            ]
        )
        assert get_next_rms_fmu_me_event_time(
            problem=time_event_problem,
            t_prev=0.0,
            t_target=0.5,
        ) == pytest.approx(0.25)
        time_event_adapter.explicit_euler_step(
            current_time=0.0,
            step_size=0.25,
            input_values=dict(control_input=7.0),
        )
        assert time_event_adapter.get_next_event_time() is None
        assert time_event_adapter.get_state_vector().tolist() == pytest.approx(
            [2.5]
        )
    finally:
        time_event_adapter.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_me_state_event_bisection_is_bounded_without_native_fmu() -> None:
    """Verify precise linear root localization independently of a C toolchain."""

    coordinator: Mock = Mock()
    coordinator.has_pending_candidate.return_value = True
    coordinator.get_accepted_point.return_value = (
        0.0,
        (1.0,),
        (4.0,),
        (1.0,),
        (-1.5,),
        (1.0,),
    )
    coordinator.evaluate_event_indicators_probe.side_effect = (
        _evaluate_linear_test_event_indicator
    )
    adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    adapter.fmi_three_coordinator = coordinator
    adapter.pending_time = 1.0
    adapter.pending_candidate_state_values = (4.0,)
    adapter.pending_candidate_event_indicators = (1.5,)

    localized_time: float | None = adapter.get_pending_state_event_time(
        time_tolerance=1.0e-9,
        maximum_iterations=40,
    )
    assert localized_time == pytest.approx(0.5, abs=1.0e-9)
    assert coordinator.evaluate_event_indicators_probe.call_count <= 40

    coordinator.evaluate_event_indicators_probe.reset_mock()
    with pytest.raises(
        FmuModeError,
        match="localization bound cannot meet its tolerance",
    ):
        adapter.get_pending_state_event_time(
            time_tolerance=1.0e-12,
            maximum_iterations=1,
        )


def test_fmi_three_me_localization_preflights_iteration_bound() -> None:
    """Preflight binary bounds and keep every supported extreme probe finite."""

    extreme_coordinator: Mock = Mock()
    extreme_coordinator.has_pending_candidate.return_value = True
    extreme_coordinator.get_accepted_point.return_value = (
        1.6e308,
        (1.0,),
        tuple(),
        tuple(),
        (-1.5,),
        (1.0,),
    )
    extreme_coordinator.evaluate_event_indicators_probe.side_effect = (
        _evaluate_linear_test_event_indicator
    )
    extreme_adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    extreme_adapter.fmi_three_coordinator = extreme_coordinator
    extreme_adapter.pending_time = 1.7e308
    extreme_adapter.pending_candidate_state_values = (4.0,)
    extreme_adapter.pending_candidate_event_indicators = (1.5,)
    extreme_time: float | None = extreme_adapter.get_pending_state_event_time(
        time_tolerance=1.0e290,
        maximum_iterations=64,
    )
    if extreme_time is not None:
        assert math.isfinite(extreme_time)
        assert 1.6e308 < extreme_time < 1.7e308
    else:
        raise AssertionError("Supported extreme interval did not localize")
    extreme_call: object
    for extreme_call in extreme_coordinator.evaluate_event_indicators_probe.call_args_list:
        extreme_probe_time: float = float(extreme_call.kwargs["time_value"])
        assert math.isfinite(extreme_probe_time)
        assert 1.6e308 < extreme_probe_time < 1.7e308

    overflow_coordinator: Mock = Mock()
    overflow_coordinator.has_pending_candidate.return_value = True
    overflow_coordinator.get_accepted_point.return_value = (
        -1.0e308,
        (1.0,),
        tuple(),
        tuple(),
        (-1.5,),
        (1.0,),
    )
    overflow_adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    overflow_adapter.fmi_three_coordinator = overflow_coordinator
    overflow_adapter.pending_time = 1.0e308
    overflow_adapter.pending_candidate_state_values = (4.0,)
    overflow_adapter.pending_candidate_event_indicators = (1.5,)
    with pytest.raises(FmuModeError, match="finite positive-width"):
        overflow_adapter.get_pending_state_event_time(
            time_tolerance=1.0e-9,
            maximum_iterations=64,
        )
    overflow_coordinator.evaluate_event_indicators_probe.assert_not_called()

    power_coordinator: Mock = Mock()
    power_coordinator.has_pending_candidate.return_value = True
    power_coordinator.get_accepted_point.return_value = (
        0.0,
        (1.0,),
        tuple(),
        tuple(),
        (-1.5,),
        (1.0,),
    )
    power_coordinator.evaluate_event_indicators_probe.side_effect = (
        _evaluate_linear_test_event_indicator
    )
    power_adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    power_adapter.fmi_three_coordinator = power_coordinator
    power_adapter.pending_time = 1.0
    power_adapter.pending_candidate_state_values = (4.0,)
    power_adapter.pending_candidate_event_indicators = (1.5,)
    power_adapter.get_pending_state_event_time(
        time_tolerance=0.125,
        maximum_iterations=3,
    )
    assert power_coordinator.evaluate_event_indicators_probe.call_count == 3

    adjacent_coordinator: Mock = Mock()
    adjacent_coordinator.has_pending_candidate.return_value = True
    adjacent_time: float = math.nextafter(1.0, math.inf)
    adjacent_coordinator.get_accepted_point.return_value = (
        1.0,
        (1.0,),
        tuple(),
        tuple(),
        (1.0,),
        (1.0,),
    )
    adjacent_adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    adjacent_adapter.fmi_three_coordinator = adjacent_coordinator
    adjacent_adapter.pending_time = adjacent_time
    adjacent_adapter.pending_candidate_state_values = (1.0,)
    adjacent_adapter.pending_candidate_event_indicators = (0.0,)
    assert adjacent_adapter.get_pending_state_event_time(
        time_tolerance=math.ulp(1.0),
        maximum_iterations=1,
    ) == adjacent_time
    adjacent_coordinator.evaluate_event_indicators_probe.assert_not_called()


def test_fmi_three_me_endpoint_domain_event_envelope() -> None:
    """Cover exact zero, simultaneous indicators, and repeated-transition scope."""

    zero_coordinator: Mock = Mock()
    zero_coordinator.has_pending_candidate.return_value = True
    zero_coordinator.get_accepted_point.return_value = (
        0.0,
        tuple(),
        tuple(),
        tuple(),
        (1.0,),
        tuple(),
    )
    zero_adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    zero_adapter.fmi_three_coordinator = zero_coordinator
    zero_adapter.pending_time = 1.0
    zero_adapter.pending_candidate_state_values = tuple()
    zero_adapter.pending_candidate_event_indicators = (0.0,)
    assert zero_adapter.get_pending_state_event_time(
        time_tolerance=1.0,
        maximum_iterations=1,
    ) == pytest.approx(1.0)

    simultaneous_coordinator: Mock = Mock()
    simultaneous_coordinator.has_pending_candidate.return_value = True
    simultaneous_coordinator.get_accepted_point.return_value = (
        0.0,
        tuple(),
        tuple(),
        tuple(),
        (1.0, 2.0),
        tuple(),
    )
    simultaneous_coordinator.evaluate_event_indicators_probe.return_value = (
        0.0,
        0.0,
    )
    simultaneous_adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    simultaneous_adapter.fmi_three_coordinator = simultaneous_coordinator
    simultaneous_adapter.pending_time = 1.0
    simultaneous_adapter.pending_candidate_state_values = tuple()
    simultaneous_adapter.pending_candidate_event_indicators = (-1.0, -2.0)
    assert simultaneous_adapter.get_pending_state_event_time(
        time_tolerance=0.5,
        maximum_iterations=1,
    ) == pytest.approx(0.5)
    assert simultaneous_coordinator.evaluate_event_indicators_probe.call_count == 1

    repeated_coordinator: Mock = Mock()
    repeated_coordinator.has_pending_candidate.return_value = True
    repeated_coordinator.get_accepted_point.return_value = (
        0.0,
        tuple(),
        tuple(),
        tuple(),
        (-1.0,),
        tuple(),
    )
    repeated_coordinator.evaluate_event_indicators_probe.side_effect = (
        (-1.0,),
        (-1.0,),
        (1.0,),
        (1.0,),
    )
    repeated_adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    repeated_adapter.fmi_three_coordinator = repeated_coordinator
    repeated_adapter.pending_time = 1.0
    repeated_adapter.pending_candidate_state_values = tuple()
    repeated_adapter.pending_candidate_event_indicators = (1.0,)
    later_event_time: float | None = repeated_adapter.get_pending_state_event_time(
        time_tolerance=0.0625,
        maximum_iterations=4,
    )

    smaller_coordinator: Mock = Mock()
    smaller_coordinator.has_pending_candidate.return_value = True
    smaller_coordinator.get_accepted_point.return_value = (
        0.0,
        tuple(),
        tuple(),
        tuple(),
        (-1.0,),
        tuple(),
    )
    smaller_coordinator.evaluate_event_indicators_probe.side_effect = (
        (-1.0,),
        (1.0,),
        (-1.0,),
        (1.0,),
    )
    smaller_adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    smaller_adapter.fmi_three_coordinator = smaller_coordinator
    smaller_adapter.pending_time = 0.3
    smaller_adapter.pending_candidate_state_values = tuple()
    smaller_adapter.pending_candidate_event_indicators = (1.0,)
    earlier_event_time: float | None = smaller_adapter.get_pending_state_event_time(
        time_tolerance=0.01875,
        maximum_iterations=4,
    )
    if earlier_event_time is not None and later_event_time is not None:
        assert earlier_event_time < later_event_time
    else:
        raise AssertionError("Repeated-transition envelope test did not localize")


def test_fmi_three_me_localization_worker_call_bound() -> None:
    """Verify exact participant formulas, tuple arguments, and buffer placement."""

    participant_count: int
    for participant_count in (1, 4, 16):
        crossing_count: int
        for crossing_count in (0, 1, participant_count):
            total_probe_count: int = 0
            retained_state_tuples: list[tuple[float, ...]] = list()
            participant_index: int
            for participant_index in range(participant_count):
                coordinator: Mock = Mock()
                coordinator.has_pending_candidate.return_value = True
                coordinator.get_accepted_point.return_value = (
                    0.0,
                    (1.0,),
                    tuple(),
                    tuple(),
                    (-1.5,),
                    (1.0,),
                )
                adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
                adapter.fmi_three_coordinator = coordinator
                adapter.pending_time = 1.0
                adapter.pending_candidate_state_values = (4.0,)
                if participant_index < crossing_count:
                    adapter.pending_candidate_event_indicators = (1.5,)
                    coordinator.evaluate_event_indicators_probe.side_effect = (
                        _evaluate_linear_test_event_indicator
                    )
                    adapter.get_pending_state_event_time(
                        time_tolerance=1.0 / 1024.0,
                        maximum_iterations=10,
                    )
                    assert coordinator.evaluate_event_indicators_probe.call_count == 10
                else:
                    adapter.pending_candidate_event_indicators = (-1.0,)
                    assert adapter.get_pending_state_event_time(
                        time_tolerance=1.0 / 1024.0,
                        maximum_iterations=10,
                    ) is None
                total_probe_count += (
                    coordinator.evaluate_event_indicators_probe.call_count
                )
                retained_call: object
                for retained_call in (
                    coordinator.evaluate_event_indicators_probe.call_args_list
                ):
                    retained_state_tuples.append(
                        retained_call.kwargs["continuous_state_values"]
                    )
            observed_worker_calls: int = (
                2 * participant_count
                + 4 * total_probe_count
                + (participant_count if crossing_count > 0 else 0)
            )
            if crossing_count == 0:
                expected_worker_calls: int = 2 * participant_count
            else:
                expected_worker_calls = (
                    3 * participant_count + 4 * total_probe_count
                )
            assert observed_worker_calls == expected_worker_calls
            assert len(retained_state_tuples) == total_probe_count
            assert len({id(values) for values in retained_state_tuples}) == (
                total_probe_count
            )

    zero_state_coordinator: Mock = Mock()
    zero_state_coordinator.has_pending_candidate.return_value = True
    zero_state_coordinator.get_accepted_point.return_value = (
        0.0,
        tuple(),
        tuple(),
        tuple(),
        (-1.0,),
        tuple(),
    )
    zero_state_coordinator.evaluate_event_indicators_probe.side_effect = (
        (0.0,),
        (1.0,),
    )
    zero_state_adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    zero_state_adapter.fmi_three_coordinator = zero_state_coordinator
    zero_state_adapter.pending_time = 1.0
    zero_state_adapter.pending_candidate_state_values = tuple()
    zero_state_adapter.pending_candidate_event_indicators = (1.0,)
    zero_state_adapter.get_pending_state_event_time(
        time_tolerance=0.25,
        maximum_iterations=2,
    )
    zero_state_call: object
    for zero_state_call in (
        zero_state_coordinator.evaluate_event_indicators_probe.call_args_list
    ):
        assert zero_state_call.kwargs["continuous_state_values"] == tuple()

    source_path: Path = (
        Path(__file__).resolve().parents[2]
        / "VeraGridEngine"
        / "IO"
        / "fmu"
        / "importer"
        / "model_exchange.py"
    )
    syntax_tree: ast.Module = ast.parse(source_path.read_text(encoding="utf-8"))
    adapter_class: ast.ClassDef | None = None
    syntax_node: ast.AST
    for syntax_node in syntax_tree.body:
        if isinstance(syntax_node, ast.ClassDef) and syntax_node.name == (
            "FmuMeDeviceAdapter"
        ):
            adapter_class = syntax_node
        else:
            pass
    if adapter_class is not None:
        pass
    else:
        raise AssertionError("FmuMeDeviceAdapter AST owner was not found")
    localization_method: ast.FunctionDef | None = None
    class_node: ast.stmt
    for class_node in adapter_class.body:
        if isinstance(class_node, ast.FunctionDef) and class_node.name == (
            "get_pending_state_event_time"
        ):
            localization_method = class_node
        else:
            pass
    if localization_method is not None:
        pass
    else:
        raise AssertionError("Localization AST method was not found")
    buffer_allocations: list[ast.AnnAssign] = list()
    localization_while: ast.While | None = None
    method_node: ast.AST
    for method_node in ast.walk(localization_method):
        if (
            isinstance(method_node, ast.AnnAssign)
            and isinstance(method_node.target, ast.Name)
            and method_node.target.id == "midpoint_states_list"
        ):
            buffer_allocations.append(method_node)
        else:
            pass
        if (
            isinstance(method_node, ast.While)
            and (
                localization_while is None
                or method_node.lineno < localization_while.lineno
            )
        ):
            localization_while = method_node
        else:
            pass
    assert len(buffer_allocations) == 1
    if localization_while is not None:
        assert buffer_allocations[0].lineno < localization_while.lineno
    else:
        raise AssertionError("Localization while loop was not found")
    indexed_mutation_count: int = 0
    while_node: ast.AST
    for while_node in ast.walk(localization_while):
        if isinstance(while_node, ast.Assign):
            assignment_target: ast.expr
            for assignment_target in while_node.targets:
                assert not (
                    isinstance(assignment_target, ast.Name)
                    and assignment_target.id == "midpoint_states_list"
                )
                if (
                    isinstance(assignment_target, ast.Subscript)
                    and isinstance(assignment_target.value, ast.Name)
                    and assignment_target.value.id == "midpoint_states_list"
                ):
                    indexed_mutation_count += 1
                else:
                    pass
        else:
            pass
    assert indexed_mutation_count == 1


def test_fmi_three_me_global_retry_restores_all_participants_without_native_fmu() -> None:
    """Verify earliest-event selection and simultaneous-source coordination."""

    localized_times: tuple[float, float, float] = (
        0.5,
        0.5000000001,
        0.75,
    )
    wrappers: list[SimpleNamespace] = [SimpleNamespace()] * 3
    wrapper_index: int
    for wrapper_index in range(3):
        runtime_adapter: Mock = Mock()
        runtime_adapter.get_pending_state_event_time.return_value = (
            localized_times[wrapper_index]
        )
        runtime_adapter.prepare_state_event_retry.return_value = (1.0,)
        mapped_outputs: dict[VarPowerFlowReferenceType, float] = dict()
        mapped_outputs[VarPowerFlowReferenceType.P] = 1.0
        runtime_adapter._map_bound_output_values.return_value = mapped_outputs
        wrappers[wrapper_index] = SimpleNamespace(
            runtime_adapter=runtime_adapter,
            last_outputs=dict(),
            apply_outputs=Mock(),
        )
    problem: SimpleNamespace = SimpleNamespace(
        _fmu_me_adapters=wrappers,
        _variable_parameters_values=np.zeros(1, dtype=float),
        _last_variable_parameters_values=None,
    )

    retry_time: float | None = _prepare_rms_fmu_me_state_event_retry(
        problem=problem,
        state_event_time_tolerance=1.0e-9,
        state_event_max_iterations=40,
    )

    assert retry_time == pytest.approx(0.5)
    wrappers[0].runtime_adapter.prepare_state_event_retry.assert_called_once_with(
        event_time=0.5
    )
    wrappers[1].runtime_adapter.prepare_state_event_retry.assert_called_once_with(
        event_time=0.5
    )
    wrappers[2].runtime_adapter.prepare_state_event_retry.assert_called_once_with(
        event_time=None
    )
    wrapper: SimpleNamespace
    for wrapper in wrappers:
        wrapper.apply_outputs.assert_called_once()


def test_emt_state_event_retry_precedes_co_simulation_without_native_fmu() -> None:
    """Verify that EMT localizes and restores ME before advancing CS."""

    problem: SimpleNamespace = SimpleNamespace(
        emt_boundary_update=Mock(),
        options=SimpleNamespace(
            fmi_state_event_time_tolerance=1.0e-9,
            fmi_state_event_max_iterations=40,
        ),
    )
    cs_outputs: dict[VarPowerFlowReferenceType, float] = dict()
    cs_outputs[VarPowerFlowReferenceType.P] = 2.0
    cs_adapter: Mock = Mock()
    cs_adapter.last_time = 0.0
    cs_adapter.advance.return_value = cs_outputs

    me_outputs: dict[VarPowerFlowReferenceType, float] = dict()
    me_outputs[VarPowerFlowReferenceType.P] = 1.0
    me_runtime_adapter: Mock = Mock()
    me_runtime_adapter.get_pending_state_event_time.return_value = 0.5
    me_runtime_adapter.prepare_state_event_retry.return_value = (1.0,)
    me_runtime_adapter._map_bound_output_values.return_value = me_outputs
    me_adapter: Mock = Mock()
    me_adapter.last_time = 0.0
    me_adapter.pending_previous_time = 0.0
    me_adapter.runtime_adapter = me_runtime_adapter
    me_adapter.advance.return_value = me_outputs

    updater: CompositeEmtBoundaryUpdater = CompositeEmtBoundaryUpdater(
        problem=problem,
        cs_adapters=[cs_adapter],
        me_adapters=[me_adapter],
    )
    updater.initialized = True
    params: np.ndarray = np.zeros(1, dtype=float)

    retry_time: float | None = updater.update(
        time_value=1.0,
        x_snapshot=np.zeros(1, dtype=float),
        full_params=params,
    )

    assert retry_time == pytest.approx(0.5)
    me_adapter.advance.assert_called_once()
    cs_adapter.advance.assert_not_called()
    me_runtime_adapter.prepare_state_event_retry.assert_called_once_with(
        event_time=0.5
    )

    me_runtime_adapter.get_pending_state_event_time.return_value = None
    updater.update(
        time_value=0.5,
        x_snapshot=np.zeros(1, dtype=float),
        full_params=params,
    )
    cs_adapter.advance.assert_called_once()


def test_fmi_three_me_state_events_use_global_earliest_retry(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Localize three crossings, group simultaneous roots, and retry the first.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture with one continuous state and one event indicator.
    :param tmp_path: Isolated worker staging parent provided by pytest.
    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    output_binding: FmuRefBinding = FmuRefBinding(
        reference=VarPowerFlowReferenceType.P,
        fmu_variable_name="observed_output",
    )
    spec: FmuMeDeviceSpec = build_fmu_me_device_spec(
        domain=FmuMeDomain.RMS,
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
            preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
            extraction_root=tmp_path / "state-event-global-retry",
        ),
        device_tpe=DeviceType.LoadDevice,
        input_variable_names=("control_input",),
        output_variable_names=("observed_output",),
        worker_limits=worker_limits,
        output_bindings=(output_binding,),
    )
    first_output_indices: dict[VarPowerFlowReferenceType, int] = dict()
    first_output_indices[VarPowerFlowReferenceType.P] = 0
    second_output_indices: dict[VarPowerFlowReferenceType, int] = dict()
    second_output_indices[VarPowerFlowReferenceType.P] = 1
    third_output_indices: dict[VarPowerFlowReferenceType, int] = dict()
    third_output_indices[VarPowerFlowReferenceType.P] = 2
    first_wrapper: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=spec,
        output_param_indices=first_output_indices,
    )
    second_wrapper: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=spec,
        output_param_indices=second_output_indices,
    )
    third_wrapper: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=spec,
        output_param_indices=third_output_indices,
    )
    problem: SimpleNamespace = SimpleNamespace(
        _fmu_me_adapters=[first_wrapper, second_wrapper, third_wrapper],
        _variable_parameters_values=np.zeros(3, dtype=float),
        _last_variable_parameters_values=None,
    )

    try:
        first_wrapper.runtime_adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=4.0),
        )
        assert first_wrapper.runtime_adapter.fmi_three_coordinator.supports_rollback()
        second_wrapper.runtime_adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=3.9999999994),
        )
        third_wrapper.runtime_adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=3.0),
        )
        first_wrapper.last_outputs = (
            first_wrapper.runtime_adapter._explicit_euler_bound_step(
                current_time=0.0,
                step_size=1.0,
                input_values=dict(control_input=4.0),
            )
        )
        second_wrapper.last_outputs = (
            second_wrapper.runtime_adapter._explicit_euler_bound_step(
                current_time=0.0,
                step_size=1.0,
                input_values=dict(control_input=3.9999999994),
            )
        )
        third_wrapper.last_outputs = (
            third_wrapper.runtime_adapter._explicit_euler_bound_step(
                current_time=0.0,
                step_size=1.0,
                input_values=dict(control_input=3.0),
            )
        )

        with pytest.raises(
            FmuModeError,
            match="localization bound cannot meet its tolerance",
        ):
            first_wrapper.runtime_adapter.get_pending_state_event_time(
                time_tolerance=1.0e-12,
                maximum_iterations=1,
            )

        retry_time: float | None = _prepare_rms_fmu_me_state_event_retry(
            problem=problem,
            state_event_time_tolerance=1.0e-9,
            state_event_max_iterations=40,
        )
        assert retry_time == pytest.approx(0.5, abs=1.0e-9)
        assert first_wrapper.runtime_adapter.get_next_event_time() == pytest.approx(
            0.5,
            abs=1.0e-9,
        )
        assert second_wrapper.runtime_adapter.get_next_event_time() == pytest.approx(
            float(retry_time),
            abs=1.0e-12,
        )
        assert third_wrapper.runtime_adapter.get_next_event_time() is None
        assert first_wrapper.runtime_adapter.get_state_vector().tolist() == pytest.approx(
            [1.0]
        )
        assert second_wrapper.runtime_adapter.get_state_vector().tolist() == pytest.approx(
            [1.0]
        )
        assert third_wrapper.runtime_adapter.get_state_vector().tolist() == pytest.approx(
            [1.0]
        )

        post_event_outputs: dict[VarPowerFlowReferenceType, float] = (
            first_wrapper.runtime_adapter._explicit_euler_bound_step(
                current_time=0.0,
                step_size=float(retry_time),
                input_values=dict(control_input=4.0),
            )
        )
        expected_post_event_outputs: dict[VarPowerFlowReferenceType, float] = dict()
        expected_post_event_outputs[VarPowerFlowReferenceType.P] = 0.0
        assert post_event_outputs == pytest.approx(expected_post_event_outputs)
        assert not first_wrapper.runtime_adapter.fmi_three_coordinator.has_pending_candidate()
        assert first_wrapper.runtime_adapter.get_next_event_time() is None
        assert first_wrapper.runtime_adapter.get_state_vector().tolist() == pytest.approx(
            [2.5],
            abs=4.0e-9,
        )
    finally:
        first_wrapper.close()
        second_wrapper.close()
        third_wrapper.close()
    staging_parent: Path = tmp_path / "state-event-global-retry"
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()
