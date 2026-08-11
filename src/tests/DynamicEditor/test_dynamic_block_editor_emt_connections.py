from __future__ import annotations

import sys

import pytest
from PySide6 import QtWidgets
import VeraGridEngine.api as gce
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Injections.load import Load

from VeraGrid.Gui.DynamicModelEditor.dynamic_block_editor import DynamicBlockEditorGUI
import VeraGrid.Gui.DynamicModelEditor.dynamic_editor_models as dialog_models
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block, find_connections
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DeviceType, DynamicSimulationMode, VarPowerFlowReferenceType

pytestmark = pytest.mark.filterwarnings("error")


class _BusStub:
    __slots__ = ("name", "is_dc", "emt_model", "_connected_emt_models", "_pending_emt_devices")

    def __init__(self, name: str, is_dc: bool, emt_model: Block) -> None:
        self.name = name
        self.is_dc = is_dc
        self.emt_model = emt_model
        self._connected_emt_models: list[object] = list()
        self._pending_emt_devices: list[object] = list()

    def add_or_replace_emt_model_connected(self,
                                           device: object,
                                           emt_model: Block,
                                           side: object,
                                           device_tpe: DeviceType) -> None:
        """
        Store one connected EMT model record for the stub bus.

        :param device: Device being registered.
        :param emt_model: EMT model block connected to the bus.
        :param side: Side identifier used by branch-like devices.
        :param device_tpe: Device type of the connected object.
        :return: None.
        """
        self.remove_emt_model_connected_for_device(device=device, side=side)
        record: _ConnectedModelRecord = _ConnectedModelRecord(device=device,
                                                              model=emt_model,
                                                              side=side,
                                                              device_tpe=device_tpe)
        self._connected_emt_models.append(record)

    def remove_emt_model_connected_for_device(self, device: object, side: object | None = None) -> None:
        """
        Remove matching connected EMT model records from the stub bus.

        :param device: Device to remove.
        :param side: Optional side filter.
        :return: None.
        """
        self._connected_emt_models = [
            record for record in self._connected_emt_models
            if not (record.get_device() is device and (side is None or record.get_side() == side))
        ]

    def get_emt_models_connected(self) -> list[object]:
        """
        Return a shallow copy of the connected EMT model records.

        :return: Connected model record list.
        """
        return list(self._connected_emt_models)

    def get_pending_emt_devices(self) -> list[object]:
        """
        Return the pending EMT device list.

        :return: Pending device list copy.
        """
        return list(self._pending_emt_devices)

    def remove_pending_emt_device(self, device: object) -> None:
        """
        Remove one pending EMT device from the stub bus.

        :param device: Pending device to remove.
        :return: None.
        """
        self._pending_emt_devices = [pending for pending in self._pending_emt_devices if pending is not device]


class _ConnectedModelRecord:
    __slots__ = ("_device", "_model", "_side", "_device_tpe")

    def __init__(self, device: object, model: Block, side: object, device_tpe: DeviceType) -> None:
        """
        Build one connected EMT model record.

        :param device: Registered device.
        :param model: Registered EMT block.
        :param side: Side identifier for branch-like devices.
        :param device_tpe: Device type of the registered object.
        :return: None.
        """
        self._device = device
        self._model = model
        self._side = side
        self._device_tpe = device_tpe

    def get_device(self) -> object:
        """
        Return the registered device.

        :return: Registered device.
        """
        return self._device

    def get_model(self) -> Block:
        """
        Return the registered EMT model block.

        :return: Registered EMT block.
        """
        return self._model

    def get_side(self) -> object:
        """
        Return the registered side marker.

        :return: Side marker.
        """
        return self._side

    def get_device_tpe(self) -> DeviceType:
        """
        Return the registered device type.

        :return: Device type.
        """
        return self._device_tpe


def _get_app() -> QtWidgets.QApplication:
    """
    Return the shared Qt application used by GUI tests.

    :return: Existing or newly created Qt application.
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        return QtWidgets.QApplication(sys.argv)
    else:
        return app


def _make_var(name: str, reference: VarPowerFlowReferenceType) -> Var:
    """
    Build one symbolic variable with the requested power-flow reference.

    :param name: Variable name.
    :param reference: Power-flow reference tag.
    :return: Symbolic variable.
    """
    return Var(name=name, reference=reference)


def _make_ac_bus(name: str,
                 *,
                 include_neutral: bool = False,
                 include_a: bool = True,
                 include_b: bool = True,
                 include_c: bool = True) -> _BusStub:
    """
    Build one AC bus stub with only the requested phase voltages.

    :param name: Bus name.
    :param include_neutral: Whether to expose the neutral voltage.
    :param include_a: Whether to expose phase A voltage.
    :param include_b: Whether to expose phase B voltage.
    :param include_c: Whether to expose phase C voltage.
    :return: AC bus stub.
    """
    mapping: dict[VarPowerFlowReferenceType, Var] = dict()

    # Build exactly the phase-voltage mapping required by the test case so the
    # editor must derive its connection ports from the bus mask and nothing else.
    if include_neutral:
        mapping[VarPowerFlowReferenceType.v_N] = _make_var(f"v_N_{name}", VarPowerFlowReferenceType.v_N)
    else:
        pass
    if include_a:
        mapping[VarPowerFlowReferenceType.v_A] = _make_var(f"v_A_{name}", VarPowerFlowReferenceType.v_A)
    else:
        pass
    if include_b:
        mapping[VarPowerFlowReferenceType.v_B] = _make_var(f"v_B_{name}", VarPowerFlowReferenceType.v_B)
    else:
        pass
    if include_c:
        mapping[VarPowerFlowReferenceType.v_C] = _make_var(f"v_C_{name}", VarPowerFlowReferenceType.v_C)
    else:
        pass

    return _BusStub(
        name=name,
        is_dc=False,
        emt_model=Block(external_mapping=mapping),
    )


def _make_dc_bus(name: str) -> _BusStub:
    """
    Build one DC bus stub exposing only the DC voltage.

    :param name: Bus name.
    :return: DC bus stub.
    """
    return _BusStub(
        name=name,
        is_dc=True,
        emt_model=Block(external_mapping={
            VarPowerFlowReferenceType.Vdc: _make_var(f"Vdc_{name}", VarPowerFlowReferenceType.Vdc),
        }),
    )


def _make_template(mapping_refs: list[VarPowerFlowReferenceType]) -> EmtModelTemplate:
    """
    Build one minimal EMT template exposing the requested references.

    :param mapping_refs: References to include in the template mapping.
    :return: EMT template.
    """
    template = EmtModelTemplate(name="stub_template")
    template.block = Block(external_mapping={
        reference: _make_var(f"templ_{reference.value}", reference)
        for reference in mapping_refs
    })
    return template


def _build_editor(api_object: ALL_DEV_TYPES) -> DynamicBlockEditorGUI:
    """
    Build one detached EMT editor around the provided API object.

    :param api_object: Device or template object under test.
    :return: Dynamic block editor instance.
    """
    _get_app()
    editor = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
        current_block=Block(),
        api_object=api_object,
        current_theme="Light",
        circuit=MultiCircuit(),
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        is_root_editor=False,
        modal=False,
    )
    return editor


def _build_real_injection_editor(bus_model: Block) -> tuple[DynamicBlockEditorGUI, Load]:
    """
    Build one real EMT load editor backed by a controlled bus EMT model.

    :param bus_model: EMT bus block to expose to the editor.
    :return: Tuple with the editor and the owned load object.
    """
    circuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    circuit.add_bus(bus)
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=bus, api_obj=load)

    # Inject the desired EMT bus shell directly so the editor under test reads
    # only the selected phase set from the bus helper model.
    load.bus.emt_model = bus_model
    load.emt_model = Block()
    load.emt_template = _make_template(list())

    editor = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
        current_block=Block(),
        api_object=load,
        current_theme="Light",
        circuit=circuit,
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        is_root_editor=True,
        modal=False,
    )
    return editor, load


def _build_real_injection_device(bus_model: Block) -> tuple[Load, MultiCircuit, VarFactory]:
    """
    Build one real EMT load device with a controlled bus EMT model.

    :param bus_model: EMT bus block to expose to the device.
    :return: Tuple with the device, circuit and variable factory.
    """
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    circuit.add_bus(bus)
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=bus, api_obj=load)
    load.bus.emt_model = bus_model
    load.emt_model = Block()
    load.emt_template = _make_template(list())
    var_factory: VarFactory = VarFactory()
    return load, circuit, var_factory


def _dispose_editor(editor: DynamicBlockEditorGUI) -> None:
    """
    Dispose one editor window using the same teardown path as production tabs.

    :param editor: Editor instance to release.
    :return: None.
    """
    editor.prepare_to_delete()
    editor.close()


def _build_real_branch_editor(bus_from_model: Block, bus_to_model: Block) -> tuple[DynamicBlockEditorGUI, Line]:
    """
    Build one real EMT line editor backed by controlled bus EMT models.

    :param bus_from_model: EMT bus block for the from side.
    :param bus_to_model: EMT bus block for the to side.
    :return: Tuple with the editor and the owned line object.
    """
    circuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line = gce.Line(name="Line 1", bus_from=bus_from, bus_to=bus_to)
    circuit.add_line(line)

    # Fix the side-specific bus shells before opening the editor so the branch
    # interface must follow the actual phase availability of each terminal.
    line.bus_from.emt_model = bus_from_model
    line.bus_to.emt_model = bus_to_model
    line.emt_model = Block()
    line.emt_template = _make_template(list())

    editor = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
        current_block=Block(),
        api_object=line,
        current_theme="Light",
        circuit=circuit,
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        is_root_editor=True,
        modal=False,
    )
    return editor, line


def _build_real_branch_device(bus_from_model: Block, bus_to_model: Block) -> tuple[Line, MultiCircuit, VarFactory]:
    """
    Build one real EMT line device with controlled terminal bus EMT models.

    :param bus_from_model: EMT bus block for the from side.
    :param bus_to_model: EMT bus block for the to side.
    :return: Tuple with the device, circuit and variable factory.
    """
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line = gce.Line(name="Line 1", bus_from=bus_from, bus_to=bus_to)
    circuit.add_line(line)
    line.bus_from.emt_model = bus_from_model
    line.bus_to.emt_model = bus_to_model
    line.emt_model = Block()
    line.emt_template = _make_template(list())
    var_factory = VarFactory()
    return line, circuit, var_factory


def test_add_connection_vars_emt_injection_uses_only_present_bus_phases() -> None:
    """
    Verify that an EMT injection exposes only the AC phases present in its bus.

    :return: None.
    """
    load, circuit, var_factory = _build_real_injection_device(
        _make_ac_bus("Gen Bus", include_neutral=False, include_a=True, include_b=False, include_c=True).emt_model
    )

    dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=load,
                                                                        circuit=circuit,
                                                                        var_factory=var_factory,
                                                                        mode=DynamicSimulationMode.EMT)

    bus_mapping: dict[VarPowerFlowReferenceType, Var | None] = load.bus.emt_model.external_mapping

    assert bus_mapping.get(VarPowerFlowReferenceType.v_N, None) is None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_A, None) is not None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_B, None) is None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_C, None) is not None


def test_add_connection_vars_emt_injection_keeps_neutral_only_when_bus_has_it() -> None:
    """
    Verify that the neutral connection ports appear only when the bus exposes neutral.

    :return: None.
    """
    load, circuit, var_factory = _build_real_injection_device(
        _make_ac_bus("Load Bus", include_neutral=True, include_a=True, include_b=False, include_c=False).emt_model
    )

    dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=load,
                                                                        circuit=circuit,
                                                                        var_factory=var_factory,
                                                                        mode=DynamicSimulationMode.EMT)

    bus_mapping: dict[VarPowerFlowReferenceType, Var | None] = load.bus.emt_model.external_mapping

    assert bus_mapping.get(VarPowerFlowReferenceType.v_N, None) is not None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_A, None) is not None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_B, None) is None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_C, None) is None


def test_add_connection_vars_emt_branch_uses_only_present_phases_per_side() -> None:
    """
    Verify that each EMT branch side exposes only the phases present in its own bus.

    :return: None.
    """
    line, circuit, var_factory = _build_real_branch_device(
        _make_ac_bus("Bus From", include_neutral=False, include_a=True, include_b=True, include_c=False).emt_model,
        _make_ac_bus("Bus To", include_neutral=True, include_a=False, include_b=True, include_c=True).emt_model,
    )

    dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=line,
                                                                        circuit=circuit,
                                                                        var_factory=var_factory,
                                                                        mode=DynamicSimulationMode.EMT)

    from_mapping: dict[VarPowerFlowReferenceType, Var | None] = line.bus_from.emt_model.external_mapping
    to_mapping: dict[VarPowerFlowReferenceType, Var | None] = line.bus_to.emt_model.external_mapping

    assert from_mapping.get(VarPowerFlowReferenceType.v_N, None) is None
    assert from_mapping.get(VarPowerFlowReferenceType.v_A, None) is not None
    assert from_mapping.get(VarPowerFlowReferenceType.v_B, None) is not None
    assert from_mapping.get(VarPowerFlowReferenceType.v_C, None) is None

    assert to_mapping.get(VarPowerFlowReferenceType.v_N, None) is not None
    assert to_mapping.get(VarPowerFlowReferenceType.v_A, None) is None
    assert to_mapping.get(VarPowerFlowReferenceType.v_B, None) is not None
    assert to_mapping.get(VarPowerFlowReferenceType.v_C, None) is not None


def test_find_connections_matches_vsc_dc_input_with_generic_dc_port() -> None:
    """
    Verify that generic DC voltage references still match power-flow connections.

    :return: None.
    """
    bus_connection_block = Block(out_vars=list([
        _make_var("Vdc_DC_Bus", VarPowerFlowReferenceType.Vdc),
    ]))
    converter_block = Block(in_vars=list([
        _make_var("v_dc_pseudo_converter_emt", VarPowerFlowReferenceType.Vdc),
    ]))

    pairs, power_flow_pairs = find_connections(bus_connection_block, converter_block)

    assert len(pairs) == 0
    assert len(power_flow_pairs) == 1
    assert power_flow_pairs[0][0].ref == VarPowerFlowReferenceType.Vdc
    assert power_flow_pairs[0][1].ref == VarPowerFlowReferenceType.Vdc


def test_attach_editor_assigned_emt_branch_model_preserves_side_specific_root_mapping() -> None:
    """
    Verify that EMT branch attach keeps side-specific root refs on the saved model.

    :return: None.
    """
    line, circuit, var_factory = _build_real_branch_device(
        _make_ac_bus("Bus From", include_neutral=False, include_a=True, include_b=True, include_c=True).emt_model,
        _make_ac_bus("Bus To", include_neutral=False, include_a=True, include_b=True, include_c=True).emt_model,
    )

    vf_a: Var = _make_var("vf_A_root", VarPowerFlowReferenceType.vf_A)
    vf_b: Var = _make_var("vf_B_root", VarPowerFlowReferenceType.vf_B)
    vt_a: Var = _make_var("vt_A_root", VarPowerFlowReferenceType.vt_A)
    vt_b: Var = _make_var("vt_B_root", VarPowerFlowReferenceType.vt_B)
    if_a: Var = _make_var("if_A_root", VarPowerFlowReferenceType.if_A)
    if_b: Var = _make_var("if_B_root", VarPowerFlowReferenceType.if_B)
    it_a: Var = _make_var("it_A_root", VarPowerFlowReferenceType.it_A)
    it_b: Var = _make_var("it_B_root", VarPowerFlowReferenceType.it_B)

    line.emt_model.in_vars = list([vf_a, vf_b, vt_a, vt_b])
    line.emt_model.out_vars = list([if_a, if_b, it_a, it_b])
    line.emt_model.external_mapping = dict({
        VarPowerFlowReferenceType.vf_A: vf_a,
        VarPowerFlowReferenceType.vf_B: vf_b,
        VarPowerFlowReferenceType.vt_A: vt_a,
        VarPowerFlowReferenceType.vt_B: vt_b,
        VarPowerFlowReferenceType.if_A: if_a,
        VarPowerFlowReferenceType.if_B: if_b,
        VarPowerFlowReferenceType.it_A: it_a,
        VarPowerFlowReferenceType.it_B: it_b,
    })

    dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=line,
                                                                        circuit=circuit,
                                                                        var_factory=var_factory,
                                                                        mode=DynamicSimulationMode.EMT)
    dialog_models.attach_editor_assigned_emt_branch_model(api_object=line,
                                                           var_factory=var_factory)

    mapping: dict[VarPowerFlowReferenceType, Var | None] = line.emt_model.external_mapping

    assert mapping.get(VarPowerFlowReferenceType.vf_A, None) is not None
    assert mapping.get(VarPowerFlowReferenceType.vf_B, None) is not None
    assert mapping.get(VarPowerFlowReferenceType.vt_A, None) is not None
    assert mapping.get(VarPowerFlowReferenceType.vt_B, None) is not None
    assert mapping.get(VarPowerFlowReferenceType.v_A, None) is None
    assert mapping.get(VarPowerFlowReferenceType.v_B, None) is None

