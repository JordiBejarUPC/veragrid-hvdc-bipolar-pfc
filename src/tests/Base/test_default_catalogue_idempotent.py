from __future__ import annotations

from VeraGrid.Gui.Main.SubClasses import io as io_module
from VeraGrid.Gui.Main.SubClasses.io import IoMain
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType


class _CircuitStub:
    """
    Minimal circuit stub used to validate default-catalogue loading.
    """

    __slots__ = (
        "transformer_types",
        "underground_cable_types",
        "wire_types",
        "sequence_line_types",
        "rms_models",
        "emt_models",
        "lazy_rms_calls",
        "lazy_emt_calls",
    )

    def __init__(self) -> None:
        self.transformer_types: list[object] = list()
        self.underground_cable_types: list[object] = list()
        self.wire_types: list[object] = list()
        self.sequence_line_types: list[object] = list()
        self.rms_models: list[object] = list()
        self.emt_models: list[object] = list()
        self.lazy_rms_calls: int = 0
        self.lazy_emt_calls: int = 0

    def add_transformer_type(self, obj: object) -> None:
        self.transformer_types.append(obj)

    def add_underground_line(self, obj: object) -> None:
        self.underground_cable_types.append(obj)

    def add_wire(self, obj: object) -> None:
        self.wire_types.append(obj)

    def add_sequence_line(self, obj: object) -> None:
        self.sequence_line_types.append(obj)

    def add_rms_model_catalogue(self) -> None:
        self.rms_models.extend(list([object(), object()]))

    def add_emt_model_catalogue(self) -> None:
        self.emt_models.extend(list([object(), object(), object()]))

    def get_rms_models_number(self) -> int:
        return len(self.rms_models)

    def get_emt_models_number(self) -> int:
        return len(self.emt_models)

    def enable_default_rms_model_catalogue_lazy_loading(self) -> None:
        self.lazy_rms_calls += 1

    def enable_default_emt_model_catalogue_lazy_loading(self) -> None:
        self.lazy_emt_calls += 1


class _IoStub:
    """
    Minimal object exposing the attributes used by `IoMain.add_default_catalogue`.
    """

    __slots__ = ("circuit", "messages")

    def __init__(self) -> None:
        self.circuit: _CircuitStub = _CircuitStub()
        self.messages: list[str] = list()

    def show_info_toast(self, message: str) -> None:
        self.messages.append(message)


def test_add_default_catalogue_is_idempotent(monkeypatch) -> None:
    """
    Ensure repeated default-catalogue loads do not duplicate cached entries.

    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None.
    """
    stub = _IoStub()

    monkeypatch.setattr(io_module, "get_transformer_catalogue", lambda: list(["t1", "t2"]))
    monkeypatch.setattr(io_module, "get_cables_catalogue", lambda: list(["c1"]))
    monkeypatch.setattr(io_module, "get_wires_catalogue", lambda: list(["w1", "w2", "w3"]))
    monkeypatch.setattr(io_module, "get_sequence_lines_catalogue", lambda: list(["s1"]))

    IoMain.add_default_catalogue(stub)
    first_counts: dict[str, int] = dict(
        transformer_types=len(stub.circuit.transformer_types),
        underground_cable_types=len(stub.circuit.underground_cable_types),
        wire_types=len(stub.circuit.wire_types),
        sequence_line_types=len(stub.circuit.sequence_line_types),
        rms_models=len(stub.circuit.rms_models),
        emt_models=len(stub.circuit.emt_models),
    )

    IoMain.add_default_catalogue(stub)
    second_counts: dict[str, int] = dict(
        transformer_types=len(stub.circuit.transformer_types),
        underground_cable_types=len(stub.circuit.underground_cable_types),
        wire_types=len(stub.circuit.wire_types),
        sequence_line_types=len(stub.circuit.sequence_line_types),
        rms_models=len(stub.circuit.rms_models),
        emt_models=len(stub.circuit.emt_models),
    )

    assert second_counts == first_counts
    assert stub.messages == list(["Catalogue added!", "Catalogue added!"])
    assert stub.circuit.lazy_rms_calls == 2
    assert stub.circuit.lazy_emt_calls == 2


def test_get_dictionary_of_lists_does_not_force_lazy_dynamic_catalogue_load() -> None:
    """
    Ensure generic GUI dependency lookups do not materialize the lazy dynamic catalogue.

    :return: None.
    """

    class _RealCircuitIoStub:
        __slots__ = ("circuit",)

        def __init__(self) -> None:
            self.circuit = MultiCircuit()

        def show_info_toast(self, message: str) -> None:
            _unused = message

    stub = _RealCircuitIoStub()
    IoMain.add_default_catalogue(stub)

    assert stub.circuit.get_rms_models_number() == 0
    assert stub.circuit.get_emt_models_number() == 0

    _ = stub.circuit.get_dictionary_of_lists(DeviceType.LoadDevice)

    assert stub.circuit.get_rms_models_number() == 0
    assert stub.circuit.get_emt_models_number() == 0
