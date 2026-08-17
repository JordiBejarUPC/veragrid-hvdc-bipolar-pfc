# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import cmath
import numpy as np
from typing import Callable, Set, Tuple, TypeVar

from VeraGridEngine.enumerations import (
    ExternalGridMode,
    SwitchGraphicType,
    TapChangerTypes,
    TapModuleControl,
    WindingType,
    ShuntControlMode,
    ConverterControlType,
    ConverterFaultControlType,
    GeneratorType,
    GeneratorControlMode,
    ReactivePowerLimitState,
    SynchronousMachineSpeedVariationMode,
    StationControlBusSelection,
    StationControlMode,
    StationReactivePowerDistribution,
    StationTransformerControlSide,
    # ConverterControlBranchSide,
    StationVoltageSetpointMode,
    ShuntConnectionType,
)
import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType, WireInTower
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import *
from VeraGridEngine.IO.dgs.dgs_schematic_import import (build_connections_by_graphic_id,
                                                        extract_dgs_connection_points,
                                                        get_bus_graphic_type_from_dgs_terminal,
                                                        import_dgs_substations_and_schematic_diagrams,
                                                        normalize_dgs_ref_id)
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.IO.dgs.dynamic_models import DynamicModelImportBundle
from VeraGridEngine.IO.dgs.dynamic_models import DynamicModelImportReport
from VeraGridEngine.IO.dgs.dgs_rms_preparation import (
    DgsRmsPreparationReport,
    prepare_dgs_circuit_for_rms,
)
from VeraGridEngine.IO.dgs.dgs_rms_measurement_binding import (
    DgsRmsMeasurementBindingReport,
    bind_dgs_rms_measurements,
)
from VeraGridEngine.IO.dgs.dgs_logical_actuator_binding import (
    bind_dgs_logical_actuator_runtime,
    prepare_dgs_logical_actuator_topology,
    synchronize_dgs_logical_actuator_service_states,
)
from VeraGridEngine.IO.dgs.dynamic_models import add_all_dynamic_import_bundle_to_circuit_with_report
from VeraGridEngine.IO.dgs.dynamic_models import build_dgs_dynamic_model_import_bundle
from VeraGridEngine.IO.dgs.dgs_to_blocks import ElmCompInstanceEntry, extract_elmcomp_direct_instances

TDgsObject = TypeVar("TDgsObject")


class DgsTransformerImpedanceInterpolation(IntEnum):
    """Identify PowerFactory tap-dependent impedance interpolation modes."""

    NaturalSpline = 0
    PiecewiseLinear = 1


class DgsTransformer3WMagnetizingLocation(IntEnum):
    """Identify PowerFactory ``TypTr3.i3loc`` magnetic-branch positions."""

    StarPoint = 0
    HighVoltageSide = 1
    MediumVoltageSide = 2
    LowVoltageSide = 3


class DgsTransformer4WMagnetizingLocation(IntEnum):
    """Identify PowerFactory ``TypTr4.imagloc`` magnetic-branch sides."""

    HighVoltageSide = 0
    LowVoltageSide1 = 1
    LowVoltageSide2 = 2
    LowVoltageSide3 = 3


class DgsCompositeBranchInference(IntEnum):
    """Select the strongest admissible composite branch evidence."""

    MeterOnly = 0
    DirectCompositeBranch = 1
    UniqueTopology = 2


class DgsCircuitImportResult:
    """
    Pair one imported circuit with its optional structured dynamic report.

    :param circuit: Imported static network and dynamic catalogues.
    :param dynamic_report: Massive dynamic-import report, or ``None`` when disabled.
    """

    __slots__: Tuple[str, ...] = ("_circuit", "_dynamic_report")

    def __init__(
            self,
            circuit: dev.MultiCircuit,
            dynamic_report: DynamicModelImportReport | None,
    ) -> None:
        """
        Store one DGS conversion result.

        :param circuit: Imported static network and dynamic catalogues.
        :param dynamic_report: Optional structured dynamic report.
        :return: None.
        """
        self._circuit: dev.MultiCircuit = circuit
        self._dynamic_report: DynamicModelImportReport | None = dynamic_report

    def get_circuit(self) -> dev.MultiCircuit:
        """Return the imported VeraGrid circuit."""
        return self._circuit

    def get_dynamic_report(self) -> DynamicModelImportReport | None:
        """Return the optional structured dynamic-import report."""
        return self._dynamic_report


class _DgsImportProgressReporter:
    """
    Report scaled DGS import progress to the existing file-open callbacks.

    The wrapper keeps phase scaling outside :func:`dgs_to_circuit`, which makes
    the orchestration explicit and avoids defining callback functions inside the
    converter.
    """

    __slots__: Tuple[str, ...] = ("_text_func", "_progress_func")

    def __init__(self,
                 text_func: Callable[[str], None] | None,
                 progress_func: Callable[[float], None] | None) -> None:
        """
        Store the optional file-open progress callbacks.

        :param text_func: Optional user-facing progress-text callback.
        :param progress_func: Optional numeric progress callback.
        :return: None.
        """
        self._text_func: Callable[[str], None] | None = text_func
        self._progress_func: Callable[[float], None] | None = progress_func

    def emit(self, progress_value: int, progress_text: str) -> None:
        """
        Emit one clamped progress update.

        :param progress_value: Integer percentage in ``[0, 100]``.
        :param progress_text: User-facing progress label.
        :return: None.
        """
        clamped_progress_value: int = max(0, min(100, int(progress_value)))

        # Numeric progress is emitted before text so the shared banner always
        # displays a percentage that corresponds to its new phase label.
        if self._progress_func is None:
            pass
        else:
            self._progress_func(float(clamped_progress_value))

        if self._text_func is None:
            pass
        else:
            self._text_func(progress_text)

    def emit_catalog_progress(self, progress_value: int, progress_text: str) -> None:
        """
        Scale dynamic-catalogue progress into the DGS ``55..80`` phase.

        :param progress_value: Dynamic-catalogue percentage.
        :param progress_text: Dynamic-catalogue progress label.
        :return: None.
        """
        scaled_value: int = 55 + int(round(25.0 * float(progress_value) / 100.0))
        self.emit(progress_value=scaled_value, progress_text=progress_text)

    def emit_install_progress(self, progress_value: int, progress_text: str) -> None:
        """
        Scale catalogue-install progress into the DGS ``80..100`` phase.

        :param progress_value: Catalogue-install percentage.
        :param progress_text: Catalogue-install progress label.
        :return: None.
        """
        scaled_value: int = 80 + int(round(20.0 * float(progress_value) / 100.0))
        self.emit(progress_value=scaled_value, progress_text=progress_text)


def _is_element_closed_by_cubicle_switches(
        element_id: str,
        cubics_by_objid: Dict[str, List[StaCubic]],
        switch_by_cubic_id: Dict[str, StaSwitch],
) -> bool:
    """
    Is element closed by cubicle switches.

    :param element_id: element_id parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :return: Function result.
    """
    element_reference: str | None = _ref_id(element_id)
    cubicles: List[StaCubic] = cubics_by_objid.get(element_reference, list())
    element_closed: bool = True
    cubic: StaCubic

    # An absent StaSwitch preserves the historical connected state.  Any
    # explicitly open switch disconnects the element, even if other terminal
    # switches remain closed.
    for cubic in cubicles:
        cubic_reference: str | None = _ref_id(cubic.ID)
        if cubic_reference is None or cubic_reference == "":
            pass
        else:
            cubicle_switch: StaSwitch | None = switch_by_cubic_id.get(cubic_reference, None)
            if cubicle_switch is None:
                pass
            else:
                if int(cubicle_switch.on_off) == 0:
                    element_closed = False
                else:
                    pass

    return element_closed


def _get_two_terminal_closed_states(
        element_id: str,
        cubics_by_objid: Dict[str, List[StaCubic]],
        switch_by_cubic_id: Dict[str, StaSwitch],
) -> tuple[bool, bool]:
    """Return the connection state at each ordered equipment terminal.

    A missing switch means connected, matching the historical DGS contract.
    The ordered states follow ``StaCubic.obj_bus`` and therefore align with
    ``get_branch_buses``.

    :param element_id: DGS equipment identifier.
    :param cubics_by_objid: Cubicles grouped by their connected equipment.
    :param switch_by_cubic_id: Explicit switches keyed by cubicle identifier.
    :return: Closed state for terminal one and terminal two.
    """
    element_reference: str | None = _ref_id(element_id)
    raw_cubicles: List[StaCubic] = cubics_by_objid.get(element_reference, list())
    valid_cubicles: List[StaCubic] = list()
    cubic: StaCubic
    for cubic in raw_cubicles:
        terminal_reference: str | None = _ref_id(cubic.fold_id)
        if terminal_reference is not None and terminal_reference != "":
            valid_cubicles.append(cubic)
        else:
            pass
    if len(valid_cubicles) == 2:
        ordered_cubicles: List[StaCubic] = sorted(
            valid_cubicles,
            key=_stacubic_obj_bus_sort_key,
        )
        closed_states: List[bool] = list([True, True])
        terminal_index: int
        for terminal_index in range(2):
            cubic_reference: str | None = _ref_id(ordered_cubicles[terminal_index].ID)
            if cubic_reference is not None and cubic_reference != "":
                cubicle_switch: StaSwitch | None = switch_by_cubic_id.get(
                    cubic_reference,
                    None,
                )
                if cubicle_switch is not None:
                    closed_states[terminal_index] = int(cubicle_switch.on_off) != 0
                else:
                    pass
            else:
                pass
        result: tuple[bool, bool] = (closed_states[0], closed_states[1])
    else:
        result = (True, True)
    return result


def _get_two_terminal_energized_states(
        element_id: str,
        cubics_by_objid: Dict[str, List[StaCubic]],
        switch_by_cubic_id: Dict[str, StaSwitch],
        bus_by_term_id: Dict[str, dev.Bus],
) -> tuple[bool, bool]:
    """Return whether each equipment terminal is electrically energized.

    PowerFactory keeps the half-line charging connected when an in-service
    line terminates at an out-of-service bus.  The switch state alone is
    therefore insufficient: an endpoint is energized only when its cubicle is
    closed and its referenced ``ElmTerm`` is in service.

    :param element_id: DGS equipment identifier.
    :param cubics_by_objid: Cubicles grouped by their connected equipment.
    :param switch_by_cubic_id: Explicit switches keyed by cubicle identifier.
    :param bus_by_term_id: Imported buses keyed by ``ElmTerm`` identifier.
    :return: Energized state for terminal one and terminal two.
    """
    terminal_from_energized: bool
    terminal_to_energized: bool
    terminal_from_energized, terminal_to_energized = (
        _get_two_terminal_closed_states(
            element_id=element_id,
            cubics_by_objid=cubics_by_objid,
            switch_by_cubic_id=switch_by_cubic_id,
        )
    )
    terminal_ids: List[str] = get_terminal_ids(
        element_id=element_id,
        cubics_by_objid=cubics_by_objid,
    )
    if len(terminal_ids) == 2:
        bus_from: dev.Bus | None = bus_by_term_id.get(terminal_ids[0], None)
        bus_to: dev.Bus | None = bus_by_term_id.get(terminal_ids[1], None)
        if bus_from is None:
            pass
        else:
            terminal_from_energized = bool(
                terminal_from_energized and bus_from.active
            )
        if bus_to is None:
            pass
        else:
            terminal_to_energized = bool(
                terminal_to_energized and bus_to.active
            )
    else:
        pass
    return terminal_from_energized, terminal_to_energized


def _is_topologically_energized(
        terminal_ids: Tuple[str, ...],
        active_terminal_edges: Tuple[Tuple[str, str], ...],
        source_terminal_ids: Tuple[str, ...],
) -> bool:
    """Return whether every terminal is connected to an active source.

    This deliberately uses only the active DGS topology.  Calculated ``m:P``
    and ``m:Q`` values are operating-point results and cannot distinguish a
    zero-flow energized island from an island with no source.

    :param terminal_ids: Terminals whose component must reach a source.
    :param active_terminal_edges: Closed, in-service topology connections.
    :param source_terminal_ids: Terminals of active source devices.
    :return: ``True`` when every requested terminal reaches a source.
    """
    if len(terminal_ids) == 0 or len(source_terminal_ids) == 0:
        return False

    adjacency: Dict[str, Set[str]] = dict()
    edge: Tuple[str, str]
    for edge in active_terminal_edges:
        from_terminal: str = str(edge[0])
        to_terminal: str = str(edge[1])
        adjacency.setdefault(from_terminal, set()).add(to_terminal)
        adjacency.setdefault(to_terminal, set()).add(from_terminal)
    else:
        pass

    reachable: Set[str] = set(str(source) for source in source_terminal_ids)
    pending: List[str] = list(reachable)
    while len(pending) > 0:
        current_terminal: str = pending.pop()
        for adjacent_terminal in adjacency.get(current_terminal, set()):
            if adjacent_terminal in reachable:
                continue
            reachable.add(adjacent_terminal)
            pending.append(adjacent_terminal)
        else:
            pass
    else:
        pass

    return all(str(terminal) in reachable for terminal in terminal_ids)


def _get_active_topology_terminal_ids(
        element_id: str,
        cubics_by_objid: Dict[str, List[StaCubic]],
        switch_by_cubic_id: Dict[str, StaSwitch],
        bus_by_term_id: Dict[str, dev.Bus],
) -> List[str]:
    """Return active bus terminals for one DGS topology object."""
    cubics: List[StaCubic] = list(
        cubics_by_objid.get(_ref_id(element_id), list())
    )
    cubics = [
        cubic
        for cubic in cubics
        if _ref_id(cubic.fold_id) not in (None, "")
    ]
    if len(cubics) >= 2:
        cubics.sort(key=_stacubic_obj_bus_sort_key)
    else:
        pass

    active_terminal_ids: List[str] = list()
    cubic: StaCubic
    for cubic in cubics:
        terminal_id: str | None = _ref_id(cubic.fold_id)
        if terminal_id is None or terminal_id == "":
            continue
        bus: dev.Bus | None = bus_by_term_id.get(terminal_id, None)
        if bus is None or not bus.active:
            continue
        cubic_id: str | None = _ref_id(cubic.ID)
        cubic_switch: StaSwitch | None = (
            None
            if cubic_id is None
            else switch_by_cubic_id.get(cubic_id, None)
        )
        if cubic_switch is not None and int(cubic_switch.on_off) == 0:
            continue
        active_terminal_ids.append(terminal_id)
    else:
        pass
    return active_terminal_ids


def _build_active_topology_for_energization(
        dgs_grid: DgsCircuit,
        cubics_by_objid: Dict[str, List[StaCubic]],
        switch_by_cubic_id: Dict[str, StaSwitch],
        bus_by_term_id: Dict[str, dev.Bus],
) -> Tuple[Tuple[Tuple[str, str], ...], Tuple[str, ...]]:
    """Build active topology edges and active source terminals for DGS lines."""
    active_edges: Set[Tuple[str, str]] = set()

    def add_element_edges(elements: List[object], check_on_off: bool = False) -> None:
        for element in elements:
            if int(getattr(element, "outserv", 0)) != 0:
                continue
            if check_on_off and int(getattr(element, "on_off", 0)) == 0:
                continue
            element_id: str = str(getattr(element, "ID", ""))
            terminal_ids: List[str] = _get_active_topology_terminal_ids(
                element_id=element_id,
                cubics_by_objid=cubics_by_objid,
                switch_by_cubic_id=switch_by_cubic_id,
                bus_by_term_id=bus_by_term_id,
            )
            for from_index in range(len(terminal_ids)):
                for to_index in range(from_index + 1, len(terminal_ids)):
                    active_edges.add(
                        tuple(sorted((
                            terminal_ids[from_index],
                            terminal_ids[to_index],
                        )))
                    )
        else:
            pass

    add_element_edges(dgs_grid.elmlnes)
    add_element_edges(dgs_grid.elmtr2s)
    add_element_edges(dgs_grid.elmtr3s)
    add_element_edges(dgs_grid.elmtr4s)
    add_element_edges(dgs_grid.elmzpus)
    add_element_edges(dgs_grid.elmscaps)
    add_element_edges(dgs_grid.elmsinds)
    add_element_edges(dgs_grid.elmcoups, check_on_off=True)

    source_terminal_ids: Set[str] = set()

    def add_active_source_terminals(sources: List[object]) -> None:
        for source in sources:
            if int(getattr(source, "outserv", 0)) != 0:
                continue
            source_id: str = str(getattr(source, "ID", ""))
            source_terminal_ids.update(
                _get_active_topology_terminal_ids(
                    element_id=source_id,
                    cubics_by_objid=cubics_by_objid,
                    switch_by_cubic_id=switch_by_cubic_id,
                    bus_by_term_id=bus_by_term_id,
                )
            )
        else:
            pass

    add_active_source_terminals(dgs_grid.elmxnets)
    add_active_source_terminals(dgs_grid.elmsyms)
    add_active_source_terminals(dgs_grid.elmgenstats)
    add_active_source_terminals(dgs_grid.elmvscs)
    add_active_source_terminals(dgs_grid.elmvscmonos)

    return tuple(sorted(active_edges)), tuple(sorted(source_terminal_ids))


def _get_tr3_winding_closed_states(
        tr3_id: str,
        cubics_by_objid: Dict[str, List[StaCubic]],
        switch_by_cubic_id: Dict[str, StaSwitch],
        bus_by_term_id: Dict[str, dev.Bus],
        bus_hv: dev.Bus,
        bus_mv: dev.Bus,
        bus_lv: dev.Bus,
) -> tuple[bool, bool, bool]:
    """
    Get tr3 winding closed states.

    :param tr3_id: tr3_id parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param bus_hv: bus_hv parameter.
    :param bus_mv: bus_mv parameter.
    :param bus_lv: bus_lv parameter.
    :return: Function result.
    """
    hv_closed: bool = True
    mv_closed: bool = True
    lv_closed: bool = True
    cubic: StaCubic
    for cubic in cubics_by_objid.get(_ref_id(tr3_id), list()):
        cubic_id: str | None = _ref_id(cubic.ID)
        terminal_id: str | None = _ref_id(cubic.fold_id)
        references_are_valid: bool = (
            cubic_id is not None
            and cubic_id != ""
            and terminal_id is not None
            and terminal_id != ""
        )
        if references_are_valid and cubic_id is not None and terminal_id is not None:
            cubicle_switch: StaSwitch | None = switch_by_cubic_id.get(cubic_id, None)
            if cubicle_switch is None:
                # Missing switch data keeps the historical connected state.
                pass
            else:
                is_closed: bool = int(cubicle_switch.on_off) != 0
                bus: dev.Bus | None = bus_by_term_id.get(terminal_id, None)
                if bus is bus_hv:
                    hv_closed = hv_closed and is_closed
                elif bus is bus_mv:
                    mv_closed = mv_closed and is_closed
                elif bus is bus_lv:
                    lv_closed = lv_closed and is_closed
                else:
                    pass
        else:
            pass
    return hv_closed, mv_closed, lv_closed


def _ref_id(x: str | None) -> str | None:
    """
    Ref id.

    :param x: x parameter.
    :return: Function result.
    """
    if x is None:
        return None
    s = str(x)
    if "\\" in s:
        return s.split("\\")[-1]
    else:
        return s


def _resolve_elmgenstat_rms_model(
        source: ElmGenstat,
        logger: Logger,
) -> DgsElmGenstatRmsModel:
    """Resolve one native static-generator RMS selector without exceptions.

    Legacy DGS files do not contain ``iSimModel``. PowerFactory documents
    their effective default as ``According to connected input signals``; when
    no dynamic controller is installed this becomes a current source initialized
    from the solved load-flow power.

    :param source: Parsed ``ElmGenstat`` row.
    :param logger: Import diagnostics receiving unsupported selector values.
    :return: Valid native RMS model selection.
    """
    raw_model: int | None = source.iSimModel
    if raw_model is None or raw_model == 0:
        model: DgsElmGenstatRmsModel = (
            DgsElmGenstatRmsModel.AccordingToConnectedInputSignals
        )
    elif raw_model == 1:
        model = DgsElmGenstatRmsModel.CurrentSource
    elif raw_model == 2:
        model = DgsElmGenstatRmsModel.VoltageSource
    elif raw_model == 3:
        model = DgsElmGenstatRmsModel.ConstantImpedance
    elif raw_model == 4:
        model = DgsElmGenstatRmsModel.ConstantPower
    else:
        # An unknown future selector must not make a massive import fail. The
        # documented default is deterministic and safer than inventing rotor
        # dynamics or silently treating the device as constant power.
        model = DgsElmGenstatRmsModel.AccordingToConnectedInputSignals
        logger.add_warning(
            msg="Unsupported ElmGenstat RMS model selector",
            device=source.loc_name,
            value=raw_model,
        )
    return model


def _stacubic_obj_bus_sort_key(cubic: StaCubic) -> int:
    """
    Stacubic obj bus sort key.

    :param cubic: cubic parameter.
    :return: Function result.
    """
    return int(cubic.obj_bus)


def _bus_vnom_sort_key(bus: dev.Bus) -> float:
    """
    Bus vnom sort key.

    :param bus: bus parameter.
    :return: Function result.
    """
    return float(bus.Vnom)


def _resolve_pointer_dict_value(key: str | None, mapping: Dict[str, TDgsObject]) -> TDgsObject | None:
    """
    Resolve pointer dict value.

    :param key: key parameter.
    :param mapping: mapping parameter.
    :return: Function result.
    """
    if key is None:
        return None
    value = mapping.get(key, None)
    if value is not None:
        return value
    normalized_key = _ref_id(key)
    if normalized_key is not None:
        return mapping.get(normalized_key, None)
    else:
        return None


def _get_non_empty_name(name: str | None, default_value: str) -> str:
    """
    Get non empty name.

    :param name: name parameter.
    :param default_value: default_value parameter.
    :return: Function result.
    """
    if name is not None and str(name).strip() != "":
        return str(name)
    else:
        return default_value


def _register_api_object_by_dgs_id(dgs_id: str | None,
                                   api_object: ALL_DEV_TYPES,
                                   api_objects_by_dgs_id: Dict[str, List[ALL_DEV_TYPES]]) -> None:
    """
    Register one imported API object under the raw DGS identifier family.

    Diagram reconstruction later needs to resolve graphical rows back to the already
    imported electrical devices. This helper keeps both the raw and normalized DGS
    keys aligned to the same runtime object list.

    :param dgs_id: Source DGS identifier.
    :param api_object: Imported VeraGrid object.
    :param api_objects_by_dgs_id: Mutable registry keyed by DGS id.
    :return: ``None``.
    """
    normalized_dgs_id: str | None = _ref_id(dgs_id)
    existing_objects: List[ALL_DEV_TYPES] | None = None

    if normalized_dgs_id is None or normalized_dgs_id == "":
        normalized_dgs_id = normalized_dgs_id
    else:
        existing_objects = api_objects_by_dgs_id.get(normalized_dgs_id, None)

        if existing_objects is None:
            api_objects: List[ALL_DEV_TYPES] = list()
            api_objects.append(api_object)
            api_objects_by_dgs_id[normalized_dgs_id] = api_objects
        else:
            existing_objects.append(api_object)

    if dgs_id is None or dgs_id == "" or dgs_id == normalized_dgs_id:
        dgs_id = dgs_id
    else:
        existing_objects = api_objects_by_dgs_id.get(dgs_id, None)

        if existing_objects is None:
            api_objects = list()
            api_objects.append(api_object)
            api_objects_by_dgs_id[dgs_id] = api_objects
        else:
            existing_objects.append(api_object)


def _get_source_dgs_id_from_api_idtag(api_idtag: str | None) -> str | None:
    """
    Recover the source DGS identifier from an imported API identifier.

    Parallel DGS devices receive a ``:<number>`` suffix so each runtime
    object remains unique. Diagram rows still reference the source identifier,
    therefore the suffix has to be removed before building the diagram lookup.

    :param api_idtag: Imported VeraGrid identifier.
    :return: Source DGS identifier, or ``None`` when no identifier is available.
    """
    if api_idtag is None or api_idtag == "":
        source_dgs_id: str | None = None
    else:
        identifier_parts: List[str] = api_idtag.rsplit(":", maxsplit=1)

        if len(identifier_parts) == 2 and identifier_parts[1].isdigit():
            source_dgs_id = identifier_parts[0]
        else:
            source_dgs_id = api_idtag

    return source_dgs_id


def _mark_dgs_rms_participation_from_calculated_results(
        dgs_circuit: DgsCircuit,
        circuit: dev.MultiCircuit,
        logger: Logger,
) -> int:
    """Apply calculated DGS participation and terminal-voltage provenance.

    PowerFactory retains an in-service ``ElmSym`` and its composite model in
    project data even when that machine does not participate in the initialized
    RMS calculation. In a calculated DGS, that state is represented by blank
    terminal ``m:P``/``m:Q`` results. The physical VeraGrid device, static data,
    source association and human-readable model therefore remain intact; only
    its device-local runtime block is omitted from temporal compilation.

    A DGS without any calculated synchronous-machine results does not provide
    enough evidence to make this decision, so every imported model remains
    eligible for compilation in that case.

    :param dgs_circuit: Parsed source DGS with optional terminal results.
    :param circuit: Imported circuit containing device-local RMS blocks.
    :param logger: Diagnostic sink for the applied participation contract.
    :return: Number of synchronous-machine runtime blocks excluded from RMS.
    """
    calculated_snapshot_available: bool = False
    source_machine: ElmSym

    # First establish that this export actually carries a calculated ElmSym
    # result set. Blank columns in a definition-only DGS are not an inactivity
    # signal and must never disable user models.
    for source_machine in dgs_circuit.elmsyms:
        source_has_terminal_result: bool = bool(
            source_machine.m_p_bus1 is not None
            and source_machine.m_q_bus1 is not None
            and math.isfinite(float(source_machine.m_p_bus1))
            and math.isfinite(float(source_machine.m_q_bus1))
        )
        if source_has_terminal_result:
            calculated_snapshot_available = True
        else:
            pass
    else:
        pass
    source_static_generator: ElmGenstat
    for source_static_generator in dgs_circuit.elmgenstats:
        static_generator_has_terminal_result: bool = bool(
            source_static_generator.m_p_bus1 is not None
            and source_static_generator.m_q_bus1 is not None
            and math.isfinite(float(source_static_generator.m_p_bus1))
            and math.isfinite(float(source_static_generator.m_q_bus1))
        )
        if static_generator_has_terminal_result:
            calculated_snapshot_available = True
        else:
            pass
    else:
        pass

    excluded_count: int = 0
    if calculated_snapshot_available:
        source_machine_by_id: Dict[str, ElmSym] = dict()
        source_machine_id: str | None
        for source_machine in dgs_circuit.elmsyms:
            source_machine_id = _ref_id(source_machine.ID)
            if source_machine_id is None or source_machine_id == "":
                pass
            else:
                source_machine_by_id[source_machine_id] = source_machine
        else:
            pass

        generator: dev.Generator
        for generator in circuit.get_generators():
            source_machine_id = _get_source_dgs_id_from_api_idtag(
                api_idtag=generator.idtag,
            )
            if source_machine_id is None:
                matched_source_machine: ElmSym | None = None
            else:
                matched_source_machine = source_machine_by_id.get(
                    source_machine_id,
                    None,
                )

            if matched_source_machine is None:
                pass
            else:
                machine_has_terminal_result: bool = bool(
                    matched_source_machine.m_p_bus1 is not None
                    and matched_source_machine.m_q_bus1 is not None
                    and math.isfinite(float(matched_source_machine.m_p_bus1))
                    and math.isfinite(float(matched_source_machine.m_q_bus1))
                )
                if machine_has_terminal_result:
                    generator.rms_model.__dict__[
                        "rms_has_calculated_terminal_power"
                    ] = True
                else:
                    # Runtime blocks are deep-copied per device when a template
                    # is assigned, so this marker cannot affect deduplicated
                    # catalogue templates or another physical machine.
                    generator.rms_model.__dict__["rms_skip_compile"] = True
                    generator.rms_model.__dict__[
                        "rms_skip_compile_reason"
                    ] = "missing calculated ElmSym terminal P/Q in solved DGS"
                    excluded_count += 1
        else:
            pass

        # Controlled static generators and storage devices use the same DGS
        # terminal-result contract. Their calculated voltage can be required
        # when a zero-impedance static partition does not publish an internal
        # terminal phasor into the expanded RMS bus vector.
        source_static_generator_by_id: Dict[str, ElmGenstat] = dict()
        source_static_generator_id: str | None
        for source_static_generator in dgs_circuit.elmgenstats:
            source_static_generator_id = _ref_id(source_static_generator.ID)
            if (
                    source_static_generator_id is None
                    or source_static_generator_id == ""
            ):
                pass
            else:
                source_static_generator_by_id[source_static_generator_id] = (
                    source_static_generator
                )
        else:
            pass

        dynamic_injection: dev.Generator | dev.Battery
        for dynamic_injection in circuit.get_generators():
            source_static_generator_id = _get_source_dgs_id_from_api_idtag(
                api_idtag=dynamic_injection.idtag,
            )
            if source_static_generator_id is None:
                matched_static_generator: ElmGenstat | None = None
            else:
                matched_static_generator = source_static_generator_by_id.get(
                    source_static_generator_id,
                    None,
                )
            if (
                    matched_static_generator is not None
                    and matched_static_generator.m_p_bus1 is not None
                    and matched_static_generator.m_q_bus1 is not None
                    and math.isfinite(float(matched_static_generator.m_p_bus1))
                    and math.isfinite(float(matched_static_generator.m_q_bus1))
            ):
                dynamic_injection.rms_model.__dict__[
                    "rms_has_calculated_terminal_power"
                ] = True
            else:
                pass
        else:
            pass

        for dynamic_injection in circuit.get_batteries():
            source_static_generator_id = _get_source_dgs_id_from_api_idtag(
                api_idtag=dynamic_injection.idtag,
            )
            if source_static_generator_id is None:
                matched_static_generator = None
            else:
                matched_static_generator = source_static_generator_by_id.get(
                    source_static_generator_id,
                    None,
                )
            if (
                    matched_static_generator is not None
                    and matched_static_generator.m_p_bus1 is not None
                    and matched_static_generator.m_q_bus1 is not None
                    and math.isfinite(float(matched_static_generator.m_p_bus1))
                    and math.isfinite(float(matched_static_generator.m_q_bus1))
            ):
                dynamic_injection.rms_model.__dict__[
                    "rms_has_calculated_terminal_power"
                ] = True
            else:
                pass
        else:
            pass
    else:
        pass

    if excluded_count > 0:
        logger.add_info(
            msg="DGS synchronous machines excluded from RMS by calculated participation",
            value=excluded_count,
        )
    else:
        pass
    return excluded_count


def _apply_dgs_physical_astable_integration_selectors(
        dgs_circuit: DgsCircuit,
        circuit: dev.MultiCircuit,
        logger: Logger,
) -> int:
    """Attach exported physical A-stable selectors to device-local RMS blocks.

    PowerFactory exposes ``iAstabint`` independently on physical generators,
    synchronous machines and static-var systems.  DSL-child selectors are
    already retained inside imported composites; this pass preserves the
    equipment-level selector after either an imported composite or a standard
    electrical shell has been assigned to its physical VeraGrid device.

    :param dgs_circuit: Parsed source DGS containing optional native selectors.
    :param circuit: Imported circuit with prepared device-local RMS blocks.
    :param logger: Import logger receiving one aggregate diagnostic.
    :return: Number of physical RMS blocks carrying an explicit selector.
    """
    selector_by_source_id: Dict[str, bool] = dict()
    source_generator: ElmGenstat
    source_machine: ElmSym
    source_svs: ElmSvs
    source_id: str | None

    # Only exported columns are authoritative. Legacy DGS files therefore keep
    # their established solver behaviour instead of receiving an inferred zero.
    for source_generator in dgs_circuit.elmgenstats:
        source_id = _ref_id(source_generator.ID)
        if (
                source_id is None
                or source_id == ""
                or source_generator.iAstabint is None
        ):
            pass
        else:
            selector_by_source_id[source_id] = bool(
                int(source_generator.iAstabint)
            )
    else:
        pass
    for source_machine in dgs_circuit.elmsyms:
        source_id = _ref_id(source_machine.ID)
        if (
                source_id is None
                or source_id == ""
                or source_machine.iAstabint is None
        ):
            pass
        else:
            selector_by_source_id[source_id] = bool(
                int(source_machine.iAstabint)
            )
    else:
        pass
    for source_svs in dgs_circuit.elmsvss:
        source_id = _ref_id(source_svs.ID)
        if (
                source_id is None
                or source_id == ""
                or source_svs.iAstabint is None
        ):
            pass
        else:
            selector_by_source_id[source_id] = bool(int(source_svs.iAstabint))
    else:
        pass

    applied_count: int = 0
    injection_device: object
    for injection_device in circuit.get_injection_devices_iter():
        if isinstance(injection_device, DynamicDevice):
            source_id = _get_source_dgs_id_from_api_idtag(
                api_idtag=injection_device.idtag,
            )
            if source_id is None:
                selector: bool | None = None
            else:
                selector = selector_by_source_id.get(source_id, None)
            if selector is None:
                pass
            else:
                injection_device.rms_model.__dict__[
                    "dgs_powerfactory_astable_integration"
                ] = selector
                applied_count += 1
        else:
            pass
    else:
        pass

    if applied_count > 0:
        logger.add_info(
            msg="Applied physical PowerFactory A-stable RMS selectors",
            value=applied_count,
        )
    else:
        pass
    return applied_count


def _build_diagram_api_objects_by_dgs_id(
        grid: dev.MultiCircuit,
) -> Dict[str, List[ALL_DEV_TYPES]]:
    """
    Index imported electrical devices for DGS schematic reconstruction.

    The electrical importer is intentionally split into small helpers in the
    current ``devel_dynamics`` implementation. Building the diagram index from
    the completed circuit keeps those helpers independent from presentation
    concerns while retaining schematic support for single and parallel devices.

    :param grid: Fully imported VeraGrid circuit.
    :return: Drawable API objects grouped by their source DGS identifier.
    """
    api_objects_by_dgs_id: Dict[str, List[ALL_DEV_TYPES]] = dict()
    api_object: ALL_DEV_TYPES

    # Only electrical objects rendered by the DGS schematic importer belong in
    # this index. Buses and substations are resolved through dedicated mappings.
    for api_object in grid.get_all_elements_iter():
        is_drawable_object: bool = isinstance(
            api_object,
            (
                BranchParent,
                dev.Transformer3W,
                dev.TransformerNW,
                dev.Generator,
                dev.StaticGenerator,
                dev.Battery,
                dev.Load,
                dev.ExternalGrid,
                dev.Shunt,
                dev.ControllableShunt,
                dev.CurrentInjection,
            ),
        )

        if is_drawable_object:
            source_dgs_id: str | None = _get_source_dgs_id_from_api_idtag(api_idtag=api_object.idtag)
            _register_api_object_by_dgs_id(
                dgs_id=source_dgs_id,
                api_object=api_object,
                api_objects_by_dgs_id=api_objects_by_dgs_id,
            )
        else:
            # Non-drawable catalogue and aggregation objects are irrelevant to
            # graphical rows and must not collide with electrical identifiers.
            pass

    return api_objects_by_dgs_id


def _get_parallel_device_count(count: int) -> int:
    """
    Get parallel device count.

    :param count: count parameter.
    :return: Function result.
    """
    if count > 1:
        return int(count)
    else:
        return 1


def _get_parallel_device_name(base_name: str, parallel_index: int, parallel_count: int) -> str:
    """
    Get parallel device name.

    :param base_name: base_name parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """
    if parallel_count <= 1:
        return base_name
    else:
        return f"{base_name} ({parallel_index + 1})"


def _get_parallel_device_idtag(base_id: str | None, parallel_index: int, parallel_count: int) -> str | None:
    """
    Get parallel device idtag.

    :param base_id: base_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """
    if base_id is None or base_id == "":
        return None
    else:
        if parallel_count <= 1:
            return base_id
        else:
            return f"{base_id}:{parallel_index + 1}"


def _get_transformer_tap_changer_type(typtr2: TypTr2) -> TapChangerTypes:
    """
    Get transformer tap changer type.

    :param typtr2: typtr2 parameter.
    :return: Function result.
    """
    if int(typtr2.itapch) == 0:
        return TapChangerTypes.NoRegulation
    else:
        pass

    phase_deg = float(typtr2.phitr)
    phase_mod = math.fmod(abs(phase_deg), 180.0)
    if abs(phase_mod) < 1e-9:
        return TapChangerTypes.VoltageRegulation
    else:
        if abs(phase_mod - 90.0) < 1e-6:
            return TapChangerTypes.Asymmetrical
        else:
            return TapChangerTypes.Symmetrical


def _get_transformer_branch_tap(
        typtr2: TypTr2,
        tap_position: int,
        bus_from_is_hv: bool,
) -> complex:
    """
    Build the PowerFactory two-winding transformer complex tap ratio.

    PowerFactory defines ``dutap`` as the magnitude of one complex voltage
    increment and ``phitr`` as that increment's angle.  ``nt2ag`` supplies the
    fixed vector-group shift.  VeraGrid's balanced branch model expects the
    complete complex ratio in the branch's from-to orientation.

    :param typtr2: Source PowerFactory transformer type.
    :param tap_position: Absolute PowerFactory tap position.
    :param bus_from_is_hv: Whether the VeraGrid from bus is the HV side.
    :return: Complex tap ratio in VeraGrid branch orientation.
    """
    # First reconstruct the complex per-position voltage increment around the
    # neutral position.  This preserves voltage-regulating taps with
    # ``phitr=180`` as well as symmetrical/asymmetrical phase shifters.
    position_offset: int = int(tap_position) - int(typtr2.nntap0)
    voltage_step_pu: float = float(typtr2.dutap) / 100.0
    voltage_step_angle_rad: float = math.radians(float(typtr2.phitr))
    complex_increment: complex = complex(
        math.cos(voltage_step_angle_rad),
        math.sin(voltage_step_angle_rad),
    )
    position_tap: complex = 1.0 + float(position_offset) * voltage_step_pu * complex_increment

    # Degenerate exported steps cannot be represented by a finite branch tap.
    # Falling back to the neutral tap keeps the remaining network importable.
    minimum_tap_magnitude: float = 1e-9
    position_tap_is_finite: bool = (
        math.isfinite(float(position_tap.real))
        and math.isfinite(float(position_tap.imag))
    )
    if position_tap_is_finite and abs(position_tap) > minimum_tap_magnitude:
        pass
    else:
        position_tap = complex(1.0, 0.0)

    # Convert the PowerFactory HV-to-LV definition into the physical complex
    # ratio, taking into account which winding owns the tap changer.
    vector_group_angle_rad: float = math.radians(float(typtr2.nt2ag) * 30.0)
    vector_group_tap: complex = complex(
        math.cos(vector_group_angle_rad),
        math.sin(vector_group_angle_rad),
    )
    if int(typtr2.tap_side) == 0:
        hv_to_lv_tap: complex = vector_group_tap * position_tap
    else:
        hv_to_lv_tap = vector_group_tap / position_tap

    # Finally orient the ratio exactly as VeraGrid stores the branch.  The
    # reciprocal is complex, so both module and phase change consistently.
    if bus_from_is_hv:
        branch_tap: complex = hv_to_lv_tap
    else:
        branch_tap = 1.0 / hv_to_lv_tap

    return branch_tap


def _get_transformer_branch_tap_state(
        typtr2: TypTr2,
        tap_position: int,
        bus_from_is_hv: bool,
) -> Tuple[float, float, float, float, float, float, np.ndarray, np.ndarray]:
    """
    Evaluate the current tap and its complete discrete PowerFactory window.

    :param typtr2: Source PowerFactory transformer type.
    :param tap_position: Absolute PowerFactory tap position.
    :param bus_from_is_hv: Whether the VeraGrid from bus is the HV side.
    :return: Current state, extrema and exact module/phase arrays.
    """
    minimum_position: int = min(int(typtr2.ntpmn), int(typtr2.ntpmx))
    maximum_position: int = max(int(typtr2.ntpmn), int(typtr2.ntpmx))
    position_count: int = maximum_position - minimum_position + 1
    if position_count > 0:
        pass
    else:
        position_count = 1

    # Allocate the exact discrete window once.  Extrema of a complex tap must
    # be evaluated at every allowed position rather than inferred from a
    # scalar ``1 + k*dV`` approximation.
    tap_modules: np.ndarray = np.empty(position_count, dtype=float)
    tap_phases: np.ndarray = np.empty(position_count, dtype=float)
    position_index: int
    for position_index in range(position_count):
        evaluated_position: int = minimum_position + position_index
        evaluated_tap: complex = _get_transformer_branch_tap(
            typtr2=typtr2,
            tap_position=evaluated_position,
            bus_from_is_hv=bus_from_is_hv,
        )
        tap_modules[position_index] = abs(evaluated_tap)
        tap_phases[position_index] = math.atan2(evaluated_tap.imag, evaluated_tap.real)

    # Unwrap the ordered position table before taking extrema.  Plain atan2
    # values jump from +pi to -pi and would otherwise describe a false phase
    # window for a vector group close to that boundary.
    tap_phases = np.unwrap(tap_phases)
    bounded_current_position: int = max(
        minimum_position,
        min(int(tap_position), maximum_position),
    )
    current_index: int = bounded_current_position - minimum_position
    current_module: float = float(tap_modules[current_index])
    current_phase: float = float(tap_phases[current_index])
    minimum_module: float = float(np.min(tap_modules))
    maximum_module: float = float(np.max(tap_modules))
    minimum_phase: float = float(np.min(tap_phases))
    maximum_phase: float = float(np.max(tap_phases))

    return (
        current_module,
        current_phase,
        minimum_module,
        maximum_module,
        minimum_phase,
        maximum_phase,
        tap_modules,
        tap_phases,
    )


def _get_valid_optional_float(
        value: int | float | None,
        allow_zero: bool,
) -> float | None:
    """
    Validate one optional numeric DGS characteristic value.

    :param value: Parsed optional DGS value.
    :param allow_zero: Whether an explicit zero is physically valid.
    :return: Finite validated value, or ``None`` when unusable.
    """
    if value is not None:
        numeric_value: float = float(value)
        value_is_finite: bool = math.isfinite(numeric_value)
        if allow_zero:
            value_is_in_range: bool = numeric_value >= 0.0
        else:
            value_is_in_range = numeric_value > 0.0
        if value_is_finite and value_is_in_range:
            result: float | None = numeric_value
        else:
            result = None
    else:
        result = None
    return result


def _get_transformer_tap_endpoint_copper_loss(
        copper_loss_kw: float | None,
        real_short_circuit_voltage_percent: float | None,
        rated_power_mva: float,
) -> float | None:
    """
    Resolve one endpoint copper loss from either supported PF representation.

    PowerFactory stores both ``Pcu`` in kW and ``Re(uk)`` in percent.  Export
    definitions differ between installed releases, so accepting either keeps
    the ASCII DGS contract version-tolerant.

    :param copper_loss_kw: Endpoint ``Pcu`` in kW, when exported.
    :param real_short_circuit_voltage_percent: Endpoint ``Re(uk)`` in percent.
    :param rated_power_mva: Transformer rated power in MVA.
    :return: Endpoint copper loss in kW, or ``None`` when unavailable.
    """
    direct_loss: float | None = _get_valid_optional_float(
        value=copper_loss_kw,
        allow_zero=True,
    )
    if direct_loss is not None:
        result: float | None = direct_loss
    else:
        real_voltage: float | None = _get_valid_optional_float(
            value=real_short_circuit_voltage_percent,
            allow_zero=True,
        )
        if real_voltage is not None and rated_power_mva > 0.0:
            # Re(uk)[%] = Pcu[MW] / Sn[MVA] * 100.
            result = real_voltage * rated_power_mva * 10.0
        else:
            result = None
    return result


def _get_transformer_impedance_interpolation_mode(
        raw_mode: int | None,
) -> DgsTransformerImpedanceInterpolation:
    """
    Resolve the native interpolation selector with a stable legacy fallback.

    PowerFactory 2025 uses natural splines by default.  Older DGS definitions
    may export all characteristic values without the selector, so missing or
    unknown codes retain that documented native default.

    :param raw_mode: Optional native ``iIntPola`` integer.
    :return: Supported interpolation mode.
    """
    if raw_mode is not None:
        numeric_mode: int = int(raw_mode)
        if numeric_mode == int(
                DgsTransformerImpedanceInterpolation.PiecewiseLinear
        ):
            mode: DgsTransformerImpedanceInterpolation = (
                DgsTransformerImpedanceInterpolation.PiecewiseLinear
            )
        else:
            mode = DgsTransformerImpedanceInterpolation.NaturalSpline
    else:
        mode = DgsTransformerImpedanceInterpolation.NaturalSpline
    return mode


def _interpolate_transformer_tap_characteristic(
        characteristic_positions: np.ndarray,
        characteristic_values: np.ndarray,
        evaluation_positions: np.ndarray,
        mode: DgsTransformerImpedanceInterpolation,
) -> np.ndarray:
    """
    Interpolate a three-point PowerFactory tap characteristic.

    The spline branch is the closed natural-cubic solution for exactly the PF
    minimum/neutral/maximum contract.  Implementing that small system directly
    avoids a new dependency and keeps numerical behaviour auditable.

    :param characteristic_positions: Increasing min/neutral/max positions.
    :param characteristic_values: Values at those three positions.
    :param evaluation_positions: Positions to evaluate within the tap window.
    :param mode: Native interpolation mode.
    :return: Interpolated value for every evaluation position.
    """
    if mode is DgsTransformerImpedanceInterpolation.PiecewiseLinear:
        interpolated_values: np.ndarray = np.interp(
            evaluation_positions,
            characteristic_positions,
            characteristic_values,
        )
    else:
        x0: float = float(characteristic_positions[0])
        x1: float = float(characteristic_positions[1])
        x2: float = float(characteristic_positions[2])
        y0: float = float(characteristic_values[0])
        y1: float = float(characteristic_values[1])
        y2: float = float(characteristic_values[2])
        left_width: float = x1 - x0
        right_width: float = x2 - x1

        # Natural boundary conditions make both endpoint second derivatives
        # zero; only the neutral second derivative remains unknown.
        left_slope: float = (y1 - y0) / left_width
        right_slope: float = (y2 - y1) / right_width
        neutral_second_derivative: float = (
            3.0 * (right_slope - left_slope)
            / (left_width + right_width)
        )
        interpolated_values = np.empty(
            evaluation_positions.shape,
            dtype=float,
        )
        left_mask: np.ndarray = evaluation_positions <= x1
        left_positions: np.ndarray = evaluation_positions[left_mask]
        left_from_minimum: np.ndarray = left_positions - x0
        left_from_neutral: np.ndarray = x1 - left_positions
        interpolated_values[left_mask] = (
            neutral_second_derivative
            * np.power(left_from_minimum, 3)
            / (6.0 * left_width)
            + y0 * left_from_neutral / left_width
            + (
                y1
                - neutral_second_derivative * left_width * left_width / 6.0
            )
            * left_from_minimum
            / left_width
        )

        right_mask: np.ndarray = np.logical_not(left_mask)
        right_positions: np.ndarray = evaluation_positions[right_mask]
        right_from_neutral: np.ndarray = right_positions - x1
        right_from_maximum: np.ndarray = x2 - right_positions
        interpolated_values[right_mask] = (
            neutral_second_derivative
            * np.power(right_from_maximum, 3)
            / (6.0 * right_width)
            + (
                y1
                - neutral_second_derivative * right_width * right_width / 6.0
            )
            * right_from_maximum
            / right_width
            + y2 * right_from_neutral / right_width
        )
    return interpolated_values


def _get_transformer_impedance_correction_tables(
        typtr2: TypTr2,
) -> Tuple[np.ndarray, np.ndarray, bool]:
    """
    Build PowerFactory tap-dependent R/X factors around the neutral data.

    PowerFactory interpolates positive-sequence ``uk`` and ``Pcu`` separately
    from minimum to neutral and from neutral to maximum tap.  The neutral
    values remain the reusable transformer template; the returned tables are
    multiplicative factors for VeraGrid's existing ``TapChanger`` contract.

    :param typtr2: Parsed PowerFactory two-winding transformer type.
    :return: Resistance factors, reactance factors and availability flag.
    """
    minimum_position: int = min(int(typtr2.ntpmn), int(typtr2.ntpmx))
    maximum_position: int = max(int(typtr2.ntpmn), int(typtr2.ntpmx))
    neutral_position: int = int(typtr2.nntap0)
    position_count: int = maximum_position - minimum_position + 1
    if position_count > 0:
        pass
    else:
        position_count = 1
    resistance_factors: np.ndarray = np.ones(position_count, dtype=float)
    reactance_factors: np.ndarray = np.ones(position_count, dtype=float)

    characteristic_is_enabled: bool = (
        typtr2.itapzdep is not None
        and int(typtr2.itapzdep) != 0
    )
    characteristic_positions_are_valid: bool = (
        minimum_position < neutral_position < maximum_position
        and position_count >= 3
    )
    rated_power_mva: float = float(typtr2.strn)
    rated_power_is_valid: bool = (
        math.isfinite(rated_power_mva)
        and rated_power_mva > 0.0
    )

    minimum_uk_percent: float | None = _get_valid_optional_float(
        value=typtr2.uktmn,
        allow_zero=False,
    )
    maximum_uk_percent: float | None = _get_valid_optional_float(
        value=typtr2.uktmx,
        allow_zero=False,
    )
    minimum_copper_loss_kw: float | None = (
        _get_transformer_tap_endpoint_copper_loss(
            copper_loss_kw=typtr2.pcutmn,
            real_short_circuit_voltage_percent=typtr2.ukrtmn,
            rated_power_mva=rated_power_mva,
        )
    )
    maximum_copper_loss_kw: float | None = (
        _get_transformer_tap_endpoint_copper_loss(
            copper_loss_kw=typtr2.pcutmx,
            real_short_circuit_voltage_percent=typtr2.ukrtmx,
            rated_power_mva=rated_power_mva,
        )
    )
    neutral_uk_percent: float | None = _get_valid_optional_float(
        value=typtr2.uktr,
        allow_zero=False,
    )
    neutral_copper_loss_kw: float | None = _get_valid_optional_float(
        value=typtr2.pcutr,
        allow_zero=True,
    )
    characteristic_values_are_complete: bool = (
        minimum_uk_percent is not None
        and maximum_uk_percent is not None
        and minimum_copper_loss_kw is not None
        and maximum_copper_loss_kw is not None
        and neutral_uk_percent is not None
        and neutral_copper_loss_kw is not None
    )
    can_build_characteristic: bool = (
        characteristic_is_enabled
        and characteristic_positions_are_valid
        and rated_power_is_valid
        and characteristic_values_are_complete
    )
    if can_build_characteristic:
        # The guarded values are complete; explicit casts make the numerical
        # array contract evident to both static analysis and human reviewers.
        characteristic_positions: np.ndarray = np.array(
            [minimum_position, neutral_position, maximum_position],
            dtype=float,
        )
        uk_characteristic: np.ndarray = np.array(
            [minimum_uk_percent, neutral_uk_percent, maximum_uk_percent],
            dtype=float,
        )
        copper_loss_characteristic: np.ndarray = np.array(
            [
                minimum_copper_loss_kw,
                neutral_copper_loss_kw,
                maximum_copper_loss_kw,
            ],
            dtype=float,
        )
        absolute_positions: np.ndarray = np.arange(
            minimum_position,
            maximum_position + 1,
            dtype=float,
        )
        interpolation_mode: DgsTransformerImpedanceInterpolation = (
            _get_transformer_impedance_interpolation_mode(
                raw_mode=typtr2.iIntPola,
            )
        )
        interpolated_uk_percent: np.ndarray = (
            _interpolate_transformer_tap_characteristic(
                characteristic_positions=characteristic_positions,
                characteristic_values=uk_characteristic,
                evaluation_positions=absolute_positions,
                mode=interpolation_mode,
            )
        )
        interpolated_copper_loss_kw: np.ndarray = (
            _interpolate_transformer_tap_characteristic(
                characteristic_positions=characteristic_positions,
                characteristic_values=copper_loss_characteristic,
                evaluation_positions=absolute_positions,
                mode=interpolation_mode,
            )
        )

        # Convert each short-circuit point to machine-base R/X.  The later
        # system-base factor is common to every position and cancels in the
        # correction ratios.
        resistance_machine_pu: np.ndarray = (
            interpolated_copper_loss_kw / 1000.0 / rated_power_mva
        )
        impedance_machine_pu: np.ndarray = interpolated_uk_percent / 100.0
        radicand: np.ndarray = (
            np.square(impedance_machine_pu)
            - np.square(resistance_machine_pu)
        )
        radicand_is_valid: bool = bool(np.all(radicand >= 0.0))
        neutral_resistance_pu: float = (
            float(neutral_copper_loss_kw) / 1000.0 / rated_power_mva
        )
        neutral_impedance_pu: float = float(neutral_uk_percent) / 100.0
        neutral_reactance_squared: float = (
            neutral_impedance_pu * neutral_impedance_pu
            - neutral_resistance_pu * neutral_resistance_pu
        )
        neutral_components_are_valid: bool = (
            neutral_resistance_pu > 0.0
            and neutral_reactance_squared > 0.0
        )
        if radicand_is_valid and neutral_components_are_valid:
            reactance_machine_pu: np.ndarray = np.sqrt(radicand)
            neutral_reactance_pu: float = math.sqrt(
                neutral_reactance_squared
            )
            resistance_factors = resistance_machine_pu / neutral_resistance_pu
            reactance_factors = reactance_machine_pu / neutral_reactance_pu
            tables_are_available: bool = True
        else:
            tables_are_available = False
    else:
        tables_are_available = False

    return resistance_factors, reactance_factors, tables_are_available


def _synchronize_transformer_snapshot_profiles(trafo: dev.Transformer2W) -> None:
    """
    Synchronize new transformer profile defaults with imported snapshot state.

    A newly constructed branch creates profiles before the DGS template, exact
    tap and controller state are applied.  Time-indexed compilation reads those
    profiles, so their defaults must be updated after the scalar conversion.

    :param trafo: Newly imported two-winding transformer.
    :return: None.
    """
    trafo.tap_module_prof.default_value = trafo.tap_module
    trafo.tap_phase_prof.default_value = trafo.tap_phase
    trafo.tap_module_control_mode_prof.default_value = trafo.tap_module_control_mode
    trafo.tap_phase_control_mode_prof.default_value = trafo.tap_phase_control_mode
    trafo.vset_prof.default_value = trafo.vset


def _get_safe_tap_value(value: float, fallback_value: float) -> float:
    """
    Get safe tap value.

    :param value: value parameter.
    :param fallback_value: fallback_value parameter.
    :return: Function result.
    """
    minimum_positive_value: float = 1e-6
    fallback: float = float(fallback_value)
    if not math.isfinite(fallback) or fallback <= 0.0:
        fallback = 1.0
    else:
        pass

    candidate: float = float(value)
    if not math.isfinite(candidate):
        return fallback
    else:
        pass

    if candidate <= 0.0:
        return fallback
    else:
        pass

    if candidate < minimum_positive_value:
        return minimum_positive_value
    else:
        return candidate


def _sanitize_tap_window(
        tap_value: float,
        tap_min_value: float,
        tap_max_value: float,
        fallback_tap_value: float,
        fallback_tap_min_value: float,
        fallback_tap_max_value: float,
) -> Tuple[float, float, float]:
    """
    Sanitize tap window.

    :param tap_value: tap_value parameter.
    :param tap_min_value: tap_min_value parameter.
    :param tap_max_value: tap_max_value parameter.
    :param fallback_tap_value: fallback_tap_value parameter.
    :param fallback_tap_min_value: fallback_tap_min_value parameter.
    :param fallback_tap_max_value: fallback_tap_max_value parameter.
    :return: Function result.
    """
    safe_tap_min: float = _get_safe_tap_value(tap_min_value, fallback_tap_min_value)
    safe_tap_max: float = _get_safe_tap_value(tap_max_value, fallback_tap_max_value)

    if safe_tap_min > safe_tap_max:
        original_minimum: float = safe_tap_min
        safe_tap_min = safe_tap_max
        safe_tap_max = original_minimum
    else:
        pass

    safe_tap: float = _get_safe_tap_value(tap_value, fallback_tap_value)
    if safe_tap < safe_tap_min:
        safe_tap = safe_tap_min
    else:
        pass

    if safe_tap > safe_tap_max:
        safe_tap = safe_tap_max
    else:
        pass

    return safe_tap, safe_tap_min, safe_tap_max


def _apply_branch_tap_state(
        branch: dev.Transformer2W,
        tap_value: float,
        tap_phase: float,
        tap_min_value: float,
        tap_max_value: float,
        tap_phase_min: float,
        tap_phase_max: float,
) -> None:
    """
    Apply branch tap state.

    :param branch: branch parameter.
    :param tap_value: tap_value parameter.
    :param tap_phase: tap_phase parameter.
    :param tap_min_value: tap_min_value parameter.
    :param tap_max_value: tap_max_value parameter.
    :param tap_phase_min: tap_phase_min parameter.
    :param tap_phase_max: tap_phase_max parameter.
    :return: Function result.
    """
    branch.tap_module = float(tap_value)
    branch.tap_phase = float(tap_phase)
    branch.tap_module_min = float(tap_min_value)
    branch.tap_module_max = float(tap_max_value)
    branch.tap_phase_min = float(tap_phase_min)
    branch.tap_phase_max = float(tap_phase_max)


def _get_switch_impedance_in_pu(r_ohm: float, x_ohm: float, vnom_kv: float, sbase_mva: float) -> Tuple[float, float]:
    """
    Get switch impedance in pu.

    :param r_ohm: r_ohm parameter.
    :param x_ohm: x_ohm parameter.
    :param vnom_kv: vnom_kv parameter.
    :param sbase_mva: sbase_mva parameter.
    :return: Function result.
    """
    if vnom_kv <= 0.0 or sbase_mva <= 0.0:
        return 1e-20, 1e-20
    else:
        pass

    zbase_ohm = (vnom_kv * vnom_kv) / sbase_mva
    if zbase_ohm <= 0.0:
        return 1e-20, 1e-20
    else:
        pass

    r_pu = float(r_ohm) / zbase_ohm
    x_pu = float(x_ohm) / zbase_ohm

    return r_pu, x_pu


def _line_section_index_sort_key(section: ElmLnesec) -> float:
    """
    Line section index sort key.

    :param section: section parameter.
    :return: Function result.
    """
    return float(section.index)


def _get_unique_name_mapping(lines: List[ElmLne], use_characteristic_name: bool) -> Dict[str, str]:
    """
    Get unique name mapping.

    :param lines: lines parameter.
    :param use_characteristic_name: use_characteristic_name parameter.
    :return: Function result.
    """
    counts: Dict[str, int] = dict()
    values: Dict[str, str] = dict()
    for line in lines:
        if use_characteristic_name:
            name = str(line.chr_name)
        else:
            name = str(line.loc_name)
        if name == "":
            continue
        counts[name] = counts.get(name, 0) + 1
        values[name] = _ref_id(line.ID) or line.ID

    mapping: Dict[str, str] = dict()
    for name, count in counts.items():
        if count == 1:
            mapping[name] = values[name]
        else:
            pass
    return mapping


def _resolve_line_section_owner_id(section: ElmLnesec,
                                   line_ids: Set[str],
                                   folder_parent: Dict[str, str],
                                   line_id_by_loc_name: Dict[str, str],
                                   line_id_by_chr_name: Dict[str, str]) -> str:
    """
    Resolve line section owner id.

    :param section: section parameter.
    :param line_ids: line_ids parameter.
    :param folder_parent: folder_parent parameter.
    :param line_id_by_loc_name: line_id_by_loc_name parameter.
    :param line_id_by_chr_name: line_id_by_chr_name parameter.
    :return: Function result.
    """
    current = _ref_id(section.fold_id) or str(section.fold_id)
    if current != "":
        for _ in range(25):
            if current in line_ids:
                return current
            parent_ptr = folder_parent.get(current, "")
            if parent_ptr == "":
                break
            current = _ref_id(parent_ptr) or parent_ptr
    else:
        pass

    if section.loc_name != "":
        owner_line_id = line_id_by_loc_name.get(section.loc_name, "")
        if owner_line_id != "":
            return owner_line_id
        else:
            pass
    else:
        pass

    if section.chr_name != "":
        return line_id_by_chr_name.get(section.chr_name, "")
    else:
        return ""


def get_terminal_ids(element_id: str, cubics_by_objid: Dict[str, List[StaCubic]]) -> List[str]:
    """
    Get terminal ids.

    :param element_id: element_id parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :return: Function result.
    """
    cbs: List[StaCubic] = list()
    cbs_raw: List[StaCubic] = cubics_by_objid.get(_ref_id(element_id), list())
    for cubic in cbs_raw:
        fold_id = _ref_id(cubic.fold_id)
        if fold_id is not None and fold_id != "":
            cbs.append(cubic)
        else:
            pass

    if len(cbs) >= 2:
        # ``StaCubic.obj_bus`` is PowerFactory's authoritative equipment-side
        # index for every multi-terminal object. File row order is unrelated
        # to electrical side order and can swap equal-voltage transformer
        # windings or converter terminals when FIDs sort differently.
        cbs = sorted(cbs, key=_stacubic_obj_bus_sort_key)
    else:
        pass

    terminal_ids: List[str] = list()
    for cubic in cbs:
        fold_id = _ref_id(cubic.fold_id)
        if fold_id is not None and fold_id != "":
            terminal_ids.append(fold_id)
        else:
            pass

    return terminal_ids


def get_branch_buses(elm_id: str,
                     stacubic_dict: Dict[str, List[int]],
                     buses: List[dev.Bus],
                     cubics_by_objid: Dict[str, List[StaCubic]],
                     bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.Bus]:
    """
    Get branch buses.

    :param elm_id: elm_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    # Prefer robust mapping using StaCubic.fold_id -> ElmTerm.ID -> Bus
    term_ids = get_terminal_ids(element_id=elm_id, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 2:
        return bus_by_term_id[term_ids[0]], bus_by_term_id[term_ids[1]]

    # Legacy fallback (index-based), kept for backward compatibility
    elm_id_ref = _ref_id(elm_id)
    bus_ids = stacubic_dict.get(elm_id_ref, None)
    if bus_ids is None:
        raise ValueError(f"No buses for the line {elm_id}")

    if len(bus_ids) != 2:
        raise ValueError(f"Not exactly 2 buses for the line {elm_id}")

    bus_from = buses[bus_ids[0]]
    bus_to = buses[bus_ids[1]]

    return bus_from, bus_to


def get_injection_bus(elm_id: str,
                      stacubic_dict: Dict[str, List[int]],
                      buses: List[dev.Bus],
                      cubics_by_objid: Dict[str, List[StaCubic]],
                      bus_by_term_id: Dict[str, dev.Bus]) -> dev.Bus:
    """
    Get injection bus.

    :param elm_id: elm_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    # Prefer robust mapping using StaCubic.fold_id -> ElmTerm.ID -> Bus
    term_ids = get_terminal_ids(element_id=elm_id, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 1:
        return bus_by_term_id[term_ids[0]]

    # Legacy fallback (index-based), kept for backward compatibility
    elm_id_ref = _ref_id(elm_id)
    bus_ids = stacubic_dict.get(elm_id_ref, None)
    if bus_ids is None or len(bus_ids) == 0:
        raise ValueError(f"No buses for the element {elm_id}")

    if len(bus_ids) != 1:
        raise ValueError(f"Not exactly 1 bus for the element {elm_id}")

    return buses[bus_ids[0]]


def convert_dgs_to_bus(elmterm: ElmTerm,
                       pos_by_objid: Dict[str, Tuple[float, float]],
                       use_power_flow_snapshot: bool = False) -> dev.Bus:
    """
    Convert dgs to bus.

    :param elmterm: elmterm parameter.
    :param pos_by_objid: pos_by_objid parameter.
    :param use_power_flow_snapshot: Permit solved ``m:u`` and ``m:phiu`` initial values.
    :return: Function result.
    """
    tid = _ref_id(elmterm.ID)
    x, y = pos_by_objid.get(tid, (0.0, 0.0))
    structural_voltage_target: float = float(elmterm.vtarget)
    if structural_voltage_target > 0.0:
        pass
    else:
        structural_voltage_target = 1.0
    voltage_control_priority: int = (
        -1 if elmterm.ivpriority is None else int(elmterm.ivpriority)
    )
    minimum_control_deviation_percent: float = (
        -5.0 if elmterm.dvmin is None else float(elmterm.dvmin)
    )
    maximum_control_deviation_percent: float = (
        5.0 if elmterm.dvmax is None else float(elmterm.dvmax)
    )
    bus = dev.Bus(
        name=elmterm.loc_name or f"Bus_{tid}",
        # The DGS FID is the only stable cross-tool identity.  Keeping it on
        # terminals is required for structural comparison and for resolving
        # dynamic-model provenance back to the physical network.
        idtag=tid,
        Vnom=float(elmterm.uknom),
        vmin=0.9,
        vmax=1.1,
        xpos=float(x) * 5,
        ypos=float(-y) * 5,
        active=(int(elmterm.outserv or 0) == 0),
        # PowerFactory's native ElmTerm system type is the authoritative
        # AC/DC classification. Converter cubicle roles remain a later
        # compatibility fallback for legacy exports that write zero here.
        is_dc=(int(elmterm.systype) == 1),
        # PowerFactory identifies the DC neutral conductor with ``iminus=2``.
        # Preserve that physical voltage reference so RMS assembly can anchor
        # the common mode of bipolar DC grids without project-specific logic.
        is_grounded=(int(elmterm.systype) == 1 and int(elmterm.iminus) == 2),
        voltage_control_target=structural_voltage_target,
        voltage_control_priority=voltage_control_priority,
        voltage_control_min_deviation_percent=minimum_control_deviation_percent,
        voltage_control_max_deviation_percent=maximum_control_deviation_percent,
        graphic_type=get_bus_graphic_type_from_dgs_terminal(elmterm=elmterm),
    )

    snapshot_voltage_is_usable: bool
    if elmterm.m_u is None:
        snapshot_voltage_is_usable = False
    else:
        snapshot_voltage_value: float = float(elmterm.m_u)
        if not math.isfinite(snapshot_voltage_value):
            snapshot_voltage_is_usable = False
        else:
            if int(elmterm.systype) == 1:
                # PowerFactory exports DC pole voltage as a signed real value.
                # A negative pole is therefore valid source data, not an
                # invalid AC voltage magnitude.
                snapshot_voltage_is_usable = True
            else:
                snapshot_voltage_is_usable = snapshot_voltage_value > 0.0

    if use_power_flow_snapshot and snapshot_voltage_is_usable:
        # Solved terminal results are an initial iterate, not a replacement for
        # the network equations.  They materially improve robust convergence
        # for stressed fixed-PQ snapshots while keeping conversion DGS-only.
        bus.Vm0 = float(elmterm.m_u)
    else:
        if int(elmterm.systype) == 1:
            # A bipolar DC Newton iterate must start with the native signed
            # conductor polarity. Initializing both poles at +1 p.u. creates a
            # zero pole-to-pole span against a non-zero converter voltage
            # target and can make the first Jacobian singular. The neutral is
            # the physical common-mode reference exported by PowerFactory.
            dc_polarity: int = int(elmterm.iminus)
            if dc_polarity == 1:
                bus.Vm0 = -structural_voltage_target
            else:
                if dc_polarity == 2:
                    bus.Vm0 = 0.0
                else:
                    bus.Vm0 = structural_voltage_target
        else:
            if float(elmterm.vtarget) > 0.0:
                bus.Vm0 = float(elmterm.vtarget)
            else:
                pass

    if use_power_flow_snapshot and elmterm.m_phiu is not None:
        bus.Va0 = math.radians(float(elmterm.m_phiu))
    else:
        pass

    return bus


def convert_dgs_to_sequence_line(typlne: TypLne) -> dev.SequenceLineType:
    """
    Convert dgs to sequence line.

    :param typlne: typlne parameter.
    :return: Function result.
    """
    # PowerFactory exports the continuous current rating in ``InomAir``.
    # ``sline`` is an apparent-power field in current DGS schemas and can be
    # two orders of magnitude larger, so using it as kA corrupts contingency
    # and thermal-limit studies.  Older DGS files without ``InomAir`` retain
    # the historical fallback instead of losing their rating altogether.
    maximum_current: float
    if float(typlne.InomAir) > 0.0:
        maximum_current = float(typlne.InomAir)
    else:
        maximum_current = float(typlne.sline)

    elm = dev.SequenceLineType(
        name=typlne.loc_name,
        # Preserve the DGS type identity so two imports of the same source do
        # not materialize unrelated user-template UUIDs.
        idtag=_ref_id(typlne.ID),
        R=typlne.rline,
        X=typlne.xline,
        B=typlne.bline,
        G=typlne.gline,
        CnF=typlne.cline * 1000,
        R0=typlne.rline0,
        X0=typlne.xline0,
        B0=typlne.bline0,
        G0=typlne.gline0,
        CnF0=typlne.cline0 * 1000,
        Vnom=typlne.uline,
        Imax=maximum_current,
        use_conductance=typlne.cline != 0.0
    )

    return elm


def _bundle_offsets(n_sub: int, spacing_m: float) -> List[Tuple[float, float]]:
    """
    Bundle offsets.

    :param n_sub: n_sub parameter.
    :param spacing_m: spacing_m parameter.
    :return: Function result.
    """
    if n_sub <= 1:
        default_offsets: List[Tuple[float, float]] = list()
        default_offsets.append((0.0, 0.0))
        return default_offsets
    else:
        pass
    if spacing_m <= 0.0:
        default_offsets = list()
        default_offsets.append((0.0, 0.0))
        return default_offsets
    else:
        pass

    # Radius of the circumcircle for a regular n-gon with side length = spacing.
    # r = s / (2*sin(pi/n))
    radius = spacing_m / (2.0 * math.sin(math.pi / float(n_sub)))

    offsets: List[Tuple[float, float]] = list()
    for k in range(n_sub):
        ang = 2.0 * math.pi * float(k) / float(n_sub)
        dx = radius * math.cos(ang)
        dy = radius * math.sin(ang)
        offsets.append((dx, dy))

    return offsets


def convert_dgs_to_wire(typcon: TypCon) -> Wire:
    """
    Convert dgs to wire.

    :param typcon: typcon parameter.
    :return: Function result.
    """
    tid = _ref_id(typcon.ID)
    if typcon.loc_name is not None and str(typcon.loc_name).strip() != "":
        name = typcon.loc_name
    else:
        name = f"Wire_{tid}"

    # PowerFactory: diatub may be 0/empty for non-tubular conductors.
    diatub = float(typcon.diatub)

    # Conductor Model (Solid or Tubular)
    if typcon.iModel == 1:
        is_tube = True
    else:
        is_tube = False

    # Keep a compact but informative stranding label.
    stranding = f"ncsub={int(typcon.ncsub)}, dsubc={float(typcon.dsubc)}"

    wire = Wire(
        name=name,
        idtag=tid,
        r=float(typcon.rpha),
        max_current=float(typcon.sline),
        stranding=stranding,
        material=str(typcon.mlei),
        diameter=float(typcon.diaco),
        diameter_internal=diatub,
        is_tube=is_tube,
        code=str(typcon.loc_name),
    )

    return wire


def _convert_gearth_us_per_cm_to_resistivity_ohm_m(gearth_us_per_cm: float) -> float:
    """
    Convert gearth us per cm to resistivity ohm m.

    :param gearth_us_per_cm: gearth_us_per_cm parameter.
    :return: Function result.
    """
    # uS/cm -> S/m: 1 uS = 1e-6 S; 1/cm = 100/m
    conductivity_s_per_m = float(gearth_us_per_cm) * 1e-4
    if conductivity_s_per_m <= 0.0:
        return 100.0
    return 1.0 / conductivity_s_per_m


def convert_dgs_to_overhead_line_type_geometrical_parameters(
        typtow: TypTow,
        typcon_by_id: Dict[str, TypCon],
        wire_by_id: Dict[str, Wire],
        default_frequency_hz: float,
) -> dev.OverheadLineType:
    """
    Convert dgs to overhead line type geometrical parameters.

    :param typtow: typtow parameter.
    :param typcon_by_id: typcon_by_id parameter.
    :param wire_by_id: wire_by_id parameter.
    :param default_frequency_hz: default_frequency_hz parameter.
    :return: Function result.
    """

    tid = _ref_id(typtow.ID)
    if typtow.loc_name is not None and str(typtow.loc_name).strip() != "":
        name = typtow.loc_name
    else:
        name = f"Tower_{tid}"

    # Frequency / earth parameters
    if typtow.frnom is not None and float(typtow.frnom) > 0.0:
        freq = float(typtow.frnom)
    else:
        freq = float(default_frequency_hz)

    earth_res = _convert_gearth_us_per_cm_to_resistivity_ohm_m(float(typtow.gearth))

    # Determine nominal voltage from referenced conductor types.
    v_candidates: List[float] = list()
    for ptr in typtow.pcond_c:
        if ptr is not None:
            cid = _ref_id(ptr)
            if cid is not None:
                tc = typcon_by_id.get(cid, None)
                if tc is not None:
                    v_candidates.append(float(tc.uline))

    for ptr in typtow.pcond_e:
        if ptr is not None:
            cid = _ref_id(ptr)
            if cid is not None:
                tc = typcon_by_id.get(cid, None)
                if tc is not None:
                    v_candidates.append(float(tc.uline))

    if len(v_candidates) > 0:
        vnom = max(v_candidates)
    else:
        explicit_matrix_voltage: float = float(typtow.matrix_voltage_kv)
        if explicit_matrix_voltage > 0.0:
            vnom = explicit_matrix_voltage
        else:
            vnom = 0.0

    ohl_type = OverheadLineType(
        name=name,
        idtag=tid,
        Vnom=vnom,
        earth_resistivity=earth_res,
        frequency=freq,
    )

    # Earth wires (phase 0)
    for ew_idx, ptr in enumerate(typtow.pcond_e):
        if ptr is not None:
            cid = _ref_id(ptr)
            if cid is not None:
                wire = wire_by_id.get(cid, None)
                tc = typcon_by_id.get(cid, None)
                if wire is not None and tc is not None:
                    if ew_idx < len(typtow.xy_e) and len(typtow.xy_e[ew_idx]) >= 2:
                        x0 = float(typtow.xy_e[ew_idx][0])
                        y0 = float(typtow.xy_e[ew_idx][1])
                    else:
                        x0 = 0.0
                        y0 = 0.0

                    offsets = _bundle_offsets(n_sub=int(tc.ncsub), spacing_m=float(tc.dsubc))
                    for dx, dy in offsets:
                        ohl_type.wires_in_tower.append(WireInTower(wire=wire, xpos=x0 + dx, ypos=y0 + dy, phase=0))
                else:
                    pass
            else:
                pass
        else:
            pass

    # Phase wires per circuit
    # Expected xy_c row format: [xA, xB, xC, yA, yB, yC]
    for c_idx, ptr in enumerate(typtow.pcond_c):
        if ptr is not None:

            cid = _ref_id(ptr)
            if cid is not None:
                wire = wire_by_id.get(cid, None)
                tc = typcon_by_id.get(cid, None)
                if wire is not None and tc is not None:
                    if c_idx < len(typtow.xy_c) and len(typtow.xy_c[c_idx]) >= 6:
                        row = typtow.xy_c[c_idx]
                        xA, xB, xC = float(row[0]), float(row[1]), float(row[2])
                        yA, yB, yC = float(row[3]), float(row[4]), float(row[5])
                    else:
                        xA, xB, xC = 0.0, 0.0, 0.0
                        yA, yB, yC = 0.0, 0.0, 0.0

                    offsets = _bundle_offsets(n_sub=int(tc.ncsub), spacing_m=float(tc.dsubc))

                    base_phase = 3 * int(c_idx)  # circuit 0 -> 0, circuit 1 -> 3, ...
                    for dx, dy in offsets:
                        ohl_type.wires_in_tower.append(
                            WireInTower(wire=wire, xpos=xA + dx, ypos=yA + dy, phase=base_phase + 1))
                        ohl_type.wires_in_tower.append(
                            WireInTower(wire=wire, xpos=xB + dx, ypos=yB + dy, phase=base_phase + 2))
                        ohl_type.wires_in_tower.append(
                            WireInTower(wire=wire, xpos=xC + dx, ypos=yC + dy, phase=base_phase + 3))
                else:
                    pass
            else:
                pass
        else:
            pass

    return ohl_type


def convert_dgs_to_overhead_line_type_electrical_parameters(
        typtow: TypTow,
        typcon_by_id: Dict[str, TypCon],
        wire_by_id: Dict[str, Wire],
        default_frequency_hz: float,
) -> dev.SequenceLineType:
    """
    Convert dgs to overhead line type electrical parameters.

    :param typtow: typtow parameter.
    :param typcon_by_id: typcon_by_id parameter.
    :param wire_by_id: wire_by_id parameter.
    :param default_frequency_hz: default_frequency_hz parameter.
    :return: Function result.
    """

    tid = _ref_id(typtow.ID)
    if typtow.loc_name is not None and str(typtow.loc_name).strip() != "":
        name = typtow.loc_name
    else:
        name = f"Tower_{tid}"

    # Frequency / earth parameters
    if typtow.frnom is not None and float(typtow.frnom) > 0.0:
        freq = float(typtow.frnom)
    else:
        freq = float(default_frequency_hz)

    earth_res = _convert_gearth_us_per_cm_to_resistivity_ohm_m(float(typtow.gearth))

    # Determine nominal voltage from referenced conductor types.
    v_candidates: List[float] = list()
    for ptr in typtow.pcond_c:
        if ptr is not None:
            cid = _ref_id(ptr)
            if cid is not None:
                tc = typcon_by_id.get(cid, None)
                if tc is not None:
                    v_candidates.append(float(tc.uline))

    for ptr in typtow.pcond_e:
        if ptr is not None:
            cid = _ref_id(ptr)
            if cid is not None:
                tc = typcon_by_id.get(cid, None)
                if tc is not None:
                    v_candidates.append(float(tc.uline))

    if len(v_candidates) > 0:
        vnom = max(v_candidates)
    else:
        explicit_matrix_voltage: float = float(typtow.matrix_voltage_kv)
        if explicit_matrix_voltage > 0.0:
            vnom = explicit_matrix_voltage
        else:
            vnom = 0.0

    ohl_type = dev.SequenceLineType(
        name=name,
        idtag=tid,
        Vnom=vnom,
        R=typtow.R_c1[0][0],
        R0=typtow.R_c0[0][0],
        X=typtow.X_c1[0][0],
        X0=typtow.X_c0[0][0],
        # TypTow electrical matrices store susceptance in uS/km, matching the
        # SequenceLineType contract.  Omitting these diagonal entries removes
        # the entire charging model of long transmission lines.
        B=typtow.B_c1[0][0],
        B0=typtow.B_c0[0][0],
    )

    return ohl_type


def _convert_pf_tr2_connection(code: str) -> WindingType | None:
    """
    Convert pf tr2 connection.

    :param code: code parameter.
    :return: Function result.
    """
    if code is None:
        return None

    c = str(code).strip().upper()
    if c == "":
        return None

    # Common PowerFactory 2-char winding codes in DGS: Y, YN, D, Z, ZN
    conversion_dict: Dict[str, WindingType] = {
        "D": WindingType.Delta,
        "Y": WindingType.NeutralStar,
        "YN": WindingType.GroundedStar,
        "Z": WindingType.ZigZag,
        "ZN": WindingType.ZigZag,
    }

    if c in conversion_dict:
        return conversion_dict[c]
    elif c.startswith("Y"):
        # Defensive fallback: any "Y*" treated as star (prefer grounded if it contains N)
        if "N" in c:
            return WindingType.GroundedStar
        return WindingType.NeutralStar
    else:
        return None


def convert_dgs_to_transformer_type(typtr2: TypTr2) -> dev.TransformerType:
    """
    Convert dgs to transformer type.

    :param typtr2: typtr2 parameter.
    :return: Function result.
    """
    tpe = dev.TransformerType(hv_nominal_voltage=float(typtr2.utrn_h),
                              lv_nominal_voltage=float(typtr2.utrn_l),
                              nominal_power=float(typtr2.strn),
                              copper_losses=float(typtr2.pcutr),
                              iron_losses=float(typtr2.pfe),
                              no_load_current=float(typtr2.curmg),
                              short_circuit_voltage=float(typtr2.uktr),
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              total_positions=max(1, int(typtr2.ntpmx) - int(typtr2.ntpmn) + 1),
                              neutral_position=max(0, int(typtr2.nntap0) - int(typtr2.ntpmn)),
                              dV=float(typtr2.dutap) / 100.0,
                              asymmetry_angle=float(typtr2.phitr),
                              tc_type=_get_transformer_tap_changer_type(typtr2=typtr2),
                              name=typtr2.loc_name,
                              # The source FID is the stable identity of this
                              # reusable static transformer type.
                              idtag=_ref_id(typtr2.ID))

    conn_hv = _convert_pf_tr2_connection(typtr2.tr2cn_h)
    conn_lv = _convert_pf_tr2_connection(typtr2.tr2cn_l)

    if conn_hv is not None:
        tpe.conn_hv = conn_hv

    if conn_lv is not None:
        tpe.conn_lv = conn_lv
    else:
        pass

    vector_group_number = int(round(float(typtr2.nt2ag))) % 12
    tpe.vector_group_number = vector_group_number

    return tpe


def _get_powerfactory_tr2_hv_distribution(
        hv_share: float | None,
        lv_share: float | None,
) -> float:
    """Return one normalized PowerFactory two-winding HV leakage share.

    Legacy DGS definitions omit ``itrdl``/``itrdr`` even though PowerFactory's
    physical T model still uses its documented equal-winding default.  When
    both shares are present they are normalized together so harmless export
    rounding cannot change the electrical contract.

    :param hv_share: Exported HV-side distribution value, when available.
    :param lv_share: Exported LV-side distribution value, when available.
    :return: Finite fraction in the closed interval from zero to one.
    """
    hv_is_usable: bool = bool(
        hv_share is not None
        and math.isfinite(float(hv_share))
        and float(hv_share) >= 0.0
    )
    lv_is_usable: bool = bool(
        lv_share is not None
        and math.isfinite(float(lv_share))
        and float(lv_share) >= 0.0
    )
    if hv_is_usable and lv_is_usable and hv_share is not None and lv_share is not None:
        distribution_total: float = float(hv_share) + float(lv_share)
        if distribution_total > 0.0:
            hv_fraction: float = float(hv_share) / distribution_total
        else:
            hv_fraction = 0.5
    elif hv_is_usable and hv_share is not None:
        hv_fraction = min(max(float(hv_share), 0.0), 1.0)
    elif lv_is_usable and lv_share is not None:
        hv_fraction = 1.0 - min(max(float(lv_share), 0.0), 1.0)
    else:
        hv_fraction = 0.5
    return hv_fraction


def _apply_powerfactory_tr2_t_equivalent(
        transformer: dev.Transformer2W,
        source_transformer: ElmTr2,
        source_type: TypTr2,
        system_base_mva: float,
        logger: Logger,
) -> None:
    """Kron-reduce PowerFactory's magnetic T model to an exact symmetric pi.

    PowerFactory places the no-load branch between the two leakage arms.
    VeraGrid's two-terminal transformer consumes a pi primitive, so the
    internal node must be eliminated before compilation.  Unequal endpoint
    shunts cannot be represented by the current symmetric device and are left
    on the conservative legacy path with an explicit diagnostic.

    :param transformer: Imported VeraGrid two-winding transformer.
    :param source_transformer: Native element carrying calculated winding bases.
    :param source_type: Native TypTr2 definition.
    :param system_base_mva: VeraGrid system power base in MVA.
    :param logger: Import logger receiving unsupported asymmetry diagnostics.
    :return: None.
    """
    transformer_rating_mva: float = float(source_type.strn)
    short_circuit_impedance_pu: float = float(source_type.uktr) / 100.0
    rated_base_is_usable: bool = bool(
        math.isfinite(transformer_rating_mva)
        and transformer_rating_mva > 0.0
        and math.isfinite(system_base_mva)
        and system_base_mva > 0.0
        and math.isfinite(short_circuit_impedance_pu)
        and short_circuit_impedance_pu >= 0.0
    )
    if rated_base_is_usable:
        # TypTr2 positive-sequence parameters live on the transformer rated
        # base. The compiler subsequently applies the two ideal virtual taps
        # that map rated winding voltages to bus nominal voltages. Converting
        # the impedance to the bus bases here as well would apply that voltage
        # transformation twice whenever either nameplate voltage differs.
        short_circuit_resistance_pu: float = max(
            float(source_type.pcutr) / 1000.0 / transformer_rating_mva,
            0.0,
        )
        short_circuit_reactance_pu: float = math.sqrt(max(
            short_circuit_impedance_pu * short_circuit_impedance_pu
            - short_circuit_resistance_pu * short_circuit_resistance_pu,
            0.0,
        ))
        rated_to_system_base: float = (
            system_base_mva / transformer_rating_mva
        )
        series_impedance: complex = complex(
            short_circuit_resistance_pu * rated_to_system_base,
            short_circuit_reactance_pu * rated_to_system_base,
        )
        transformer.R = float(series_impedance.real)
        transformer.X = float(series_impedance.imag)
    else:
        # Preserve legacy deterministic conversion when the type omits a
        # usable power or short-circuit base instead of fabricating one.
        series_impedance = complex(transformer.R, transformer.X)
    magnetic_admittance: complex = complex(transformer.G, transformer.B)
    # ``c:ym`` is PowerFactory's electrically effective magnetising-
    # admittance magnitude on the transformer rated base.  Unlike ``curmg``,
    # it already includes an active load-flow saturation curve at the exported
    # operating point.  Preserve the iron-loss conductance and recover only
    # the reactive component, then refer the magnitude to the system base.
    # Missing or inconsistent calculated data deliberately retains the
    # deterministic no-load-test fallback produced by ``TransformerType``.
    effective_magnetic_module_is_usable: bool = bool(
        source_transformer.c_ym is not None
        and math.isfinite(float(source_transformer.c_ym))
        and float(source_transformer.c_ym) > 0.0
        and transformer_rating_mva > 0.0
        and system_base_mva > 0.0
    )
    if effective_magnetic_module_is_usable and source_transformer.c_ym is not None:
        effective_magnetic_module: float = (
            float(source_transformer.c_ym)
            * transformer_rating_mva
            / system_base_mva
        )
        conductance_module: float = abs(float(magnetic_admittance.real))
        module_contains_conductance: bool = bool(
            effective_magnetic_module + 1.0e-15 >= conductance_module
        )
        if module_contains_conductance:
            susceptance_module: float = math.sqrt(max(
                effective_magnetic_module * effective_magnetic_module
                - conductance_module * conductance_module,
                0.0,
            ))
            susceptance_sign_source: float = (
                float(magnetic_admittance.imag)
                if float(magnetic_admittance.imag) != 0.0
                else -1.0
            )
            magnetic_admittance = complex(
                magnetic_admittance.real,
                math.copysign(susceptance_module, susceptance_sign_source),
            )
        else:
            pass
    else:
        pass
    parameters_are_usable: bool = bool(
        abs(series_impedance) > 0.0 and abs(magnetic_admittance) > 0.0
    )
    if parameters_are_usable:
        resistance_hv_fraction: float = _get_powerfactory_tr2_hv_distribution(
            hv_share=source_type.itrdr,
            lv_share=source_type.itrdr_lv,
        )
        reactance_hv_fraction: float = _get_powerfactory_tr2_hv_distribution(
            hv_share=source_type.itrdl,
            lv_share=source_type.itrdl_lv,
        )
        hv_impedance: complex = complex(
            transformer.R * resistance_hv_fraction,
            transformer.X * reactance_hv_fraction,
        )
        lv_impedance: complex = series_impedance - hv_impedance
        arms_are_usable: bool = bool(
            abs(hv_impedance) > 0.0 and abs(lv_impedance) > 0.0
        )
        if arms_are_usable:
            hv_admittance: complex = 1.0 / hv_impedance
            lv_admittance: complex = 1.0 / lv_impedance
            internal_admittance: complex = (
                hv_admittance + lv_admittance + magnetic_admittance
            )
            internal_is_usable: bool = abs(internal_admittance) > 0.0
            if internal_is_usable:
                equivalent_series_admittance: complex = (
                    hv_admittance * lv_admittance / internal_admittance
                )
                from_self_admittance: complex = (
                    hv_admittance
                    - hv_admittance * hv_admittance / internal_admittance
                )
                to_self_admittance: complex = (
                    lv_admittance
                    - lv_admittance * lv_admittance / internal_admittance
                )
                from_endpoint_shunt: complex = (
                    from_self_admittance - equivalent_series_admittance
                )
                to_endpoint_shunt: complex = (
                    to_self_admittance - equivalent_series_admittance
                )
                shunts_are_symmetric: bool = bool(np.isclose(
                    from_endpoint_shunt,
                    to_endpoint_shunt,
                    rtol=1.0e-10,
                    atol=1.0e-14,
                ))
                if shunts_are_symmetric and abs(equivalent_series_admittance) > 0.0:
                    equivalent_series_impedance: complex = (
                        1.0 / equivalent_series_admittance
                    )
                    transformer.R = float(equivalent_series_impedance.real)
                    transformer.X = float(equivalent_series_impedance.imag)
                    transformer.G = float(2.0 * from_endpoint_shunt.real)
                    transformer.B = float(2.0 * from_endpoint_shunt.imag)
                else:
                    logger.add_warning(
                        msg="Asymmetric PowerFactory TypTr2 T-equivalent retained as legacy pi",
                        device=transformer.name,
                        device_class="Transformer2W",
                        value=(resistance_hv_fraction, reactance_hv_fraction),
                    )
            else:
                pass
        else:
            pass
    else:
        pass

    # PowerFactory refers an LV-side tap transformer's reduced primitive to
    # the calculated no-load winding base.  The ideal tap already transports
    # voltage through ``c:w_0``; the impedance and admittance bases therefore
    # transform contragrediently.  Omitting this second, structural base
    # conversion creates a false phase error even when the vector group is
    # exact.  HV-side and fixed transformers are already expressed on the
    # reference side and must remain unchanged.
    nominal_ratio_is_usable: bool = bool(
        int(source_type.itapch) != 0
        and int(source_type.tap_side) == 1
        and source_transformer.c_w_0 is not None
        and math.isfinite(float(source_transformer.c_w_0))
        and float(source_transformer.c_w_0) > 0.0
    )
    if nominal_ratio_is_usable and source_transformer.c_w_0 is not None:
        impedance_base_factor: float = float(source_transformer.c_w_0) ** 2
        transformer.R = float(transformer.R) * impedance_base_factor
        transformer.X = float(transformer.X) * impedance_base_factor
        transformer.G = float(transformer.G) / impedance_base_factor
        transformer.B = float(transformer.B) / impedance_base_factor
    else:
        pass


def _get_powerfactory_tr2_tap_normalization(
        source_transformer: ElmTr2,
        bus_from_is_hv: bool,
        current_tap_module: float,
) -> float:
    """Return PowerFactory's no-load-normalized winding-ratio correction.

    :param source_transformer: Native ElmTr2 carrying optional calculated ratios.
    :param bus_from_is_hv: Whether the VeraGrid from side is the HV winding.
    :param current_tap_module: Generic discrete-tap magnitude at the selected position.
    :return: Positive multiplier applied to the complete discrete tap table.
    """
    nominal_ratio_is_usable: bool = bool(
        source_transformer.c_w_0 is not None
        and math.isfinite(float(source_transformer.c_w_0))
        and float(source_transformer.c_w_0) > 0.0
    )
    calculated_hv_is_usable: bool = bool(
        source_transformer.c_thv is not None
        and math.isfinite(float(source_transformer.c_thv))
        and float(source_transformer.c_thv) > 0.0
    )
    calculated_lv_is_usable: bool = bool(
        source_transformer.c_tlv is not None
        and math.isfinite(float(source_transformer.c_tlv))
        and float(source_transformer.c_tlv) > 0.0
    )
    if nominal_ratio_is_usable and source_transformer.c_w_0 is not None:
        # ASCII DGS serializes ``c:thv``/``c:tlv`` with six decimals, while
        # ``c:w_0`` retains the full calculated no-load ratio. Prefer the
        # higher-precision structural coefficient when both are available.
        if bus_from_is_hv:
            normalization: float = 1.0 / float(source_transformer.c_w_0)
        else:
            normalization = float(source_transformer.c_w_0)
    elif (
            calculated_hv_is_usable
            and calculated_lv_is_usable
            and source_transformer.c_thv is not None
            and source_transformer.c_tlv is not None
            and current_tap_module > 0.0
    ):
        calculated_hv_to_lv_ratio: float = (
            float(source_transformer.c_thv) / float(source_transformer.c_tlv)
        )
        if bus_from_is_hv:
            effective_branch_ratio: float = calculated_hv_to_lv_ratio
        else:
            effective_branch_ratio = 1.0 / calculated_hv_to_lv_ratio
        # Legacy definitions may expose only the two effective winding
        # coefficients. Their quotient still preserves the physical side and
        # selected tap without inventing a nominal ratio.
        normalization: float = effective_branch_ratio / current_tap_module
    else:
        # Standard legacy DGS files do not expose the calculated nominal
        # winding ratio.  ``curmg`` alone is insufficient: PowerFactory may
        # deliberately keep w_0=1 even for a non-zero no-load current.
        normalization = 1.0
    if math.isfinite(normalization) and normalization > 0.0:
        result: float = normalization
    else:
        result = 1.0
    return result


def _order_hv_lv(bus_a: dev.Bus, bus_b: dev.Bus, logger: Logger, tr_name: str) -> Tuple[dev.Bus, dev.Bus]:
    """
    Order hv lv.

    :param bus_a: bus_a parameter.
    :param bus_b: bus_b parameter.
    :param logger: logger parameter.
    :param tr_name: tr_name parameter.
    :return: Function result.
    """
    va = float(bus_a.Vnom)
    vb = float(bus_b.Vnom)

    if va == 0.0 or vb == 0.0:
        logger.add_warning(f"Transformer '{tr_name}': one or both buses have Vnom=0.0 (va={va}, vb={vb}).")
        return bus_a, bus_b

    if va > vb:
        return bus_a, bus_b
    if vb > va:
        return bus_b, bus_a

    # Equal-Vnom transformers: HV/LV is ambiguous.
    # Use deterministic lexical ordering by bus name to keep import orientation stable.
    name_a: str = str(bus_a.name or "").strip()
    name_b: str = str(bus_b.name or "").strip()

    if name_a != "" and name_b != "":
        if name_a <= name_b:
            logger.add_warning(
                f"Transformer '{tr_name}': HV/LV ambiguous (equal Vnom={va}). Ordered lexically by bus name."
            )
            return bus_a, bus_b
        else:
            logger.add_warning(
                f"Transformer '{tr_name}': HV/LV ambiguous (equal Vnom={va}). Ordered lexically by bus name."
            )
            return bus_b, bus_a
    else:
        pass

    logger.add_warning(f"Transformer '{tr_name}': HV/LV ambiguous (equal Vnom={va}). Keeping original order.")
    return bus_a, bus_b


def _order_hv_mv_lv(bus_a: dev.Bus, bus_b: dev.Bus, bus_c: dev.Bus, logger: Logger, tr_name: str) -> Tuple[
    dev.Bus, dev.Bus, dev.Bus]:
    """
    Order hv mv lv.

    :param bus_a: bus_a parameter.
    :param bus_b: bus_b parameter.
    :param bus_c: bus_c parameter.
    :param logger: logger parameter.
    :param tr_name: tr_name parameter.
    :return: Function result.
    """
    va = float(bus_a.Vnom)
    vb = float(bus_b.Vnom)
    vc = float(bus_c.Vnom)

    if va == 0.0 or vb == 0.0 or vc == 0.0:
        logger.add_warning(
            f"one or more buses have Vnom=0.0",
            device=tr_name,
            device_class="Transformer3W",
            value=f"(va={va}, vb={vb}, vc={vc})"
        )

        return bus_a, bus_b, bus_c

    buses: List[dev.Bus] = list()
    buses.append(bus_a)
    buses.append(bus_b)
    buses.append(bus_c)
    buses_sorted: List[dev.Bus] = sorted(buses, key=_bus_vnom_sort_key, reverse=True)

    v0 = float(buses_sorted[0].Vnom)
    v1 = float(buses_sorted[1].Vnom)
    v2 = float(buses_sorted[2].Vnom)

    if v0 == v1 or v1 == v2:
        logger.add_warning(
            f"HV/MV/LV ambiguous, keeping Vnom-based ordering ",
            device=tr_name,
            device_class="Transformer3W",
            value=f"(va={va}, vb={vb}, vc={vc})"
        )

    return buses_sorted[0], buses_sorted[1], buses_sorted[2]

def _order_tr4(bus_a: dev.Bus,
               bus_b: dev.Bus,
               bus_c: dev.Bus,
               bus_d: dev.Bus,
               logger: Logger,
               tr_name: str) -> Tuple[dev.Bus, dev.Bus, dev.Bus, dev.Bus, List[int]]:
    """
    Order tr4 buses by voltage and return the original DGS-side indices.

    DGS-side indices:
    0 = h0
    1 = l1
    2 = l2
    3 = l3

    :param bus_a: First DGS-side bus.
    :param bus_b: Second DGS-side bus.
    :param bus_c: Third DGS-side bus.
    :param bus_d: Fourth DGS-side bus.
    :param logger: Logger.
    :param tr_name: Transformer name.
    :return: Ordered buses plus original DGS-side indices.
    """
    va: float = float(bus_a.Vnom)
    vb: float = float(bus_b.Vnom)
    vc: float = float(bus_c.Vnom)
    vd: float = float(bus_d.Vnom)

    if va == 0.0 or vb == 0.0 or vc == 0.0 or vd == 0.0:
        logger.add_warning(
            f"one or more buses have Vnom=0.0",
            device=tr_name,
            device_class="Transformer4W",
            value=f"(va={va}, vb={vb}, vc={vc}, vd={vd})"
        )

        return bus_a, bus_b, bus_c, bus_d, [0, 1, 2, 3]
    else:
        pass

    indexed_buses: List[Tuple[dev.Bus, int]] = list()
    indexed_buses.append((bus_a, 0))
    indexed_buses.append((bus_b, 1))
    indexed_buses.append((bus_c, 2))
    indexed_buses.append((bus_d, 3))

    indexed_buses_sorted: List[Tuple[dev.Bus, int]] = sorted(
        indexed_buses,
        key=lambda item: float(item[0].Vnom),
        reverse=True
    )

    v0: float = float(indexed_buses_sorted[0][0].Vnom)
    v1: float = float(indexed_buses_sorted[1][0].Vnom)
    v2: float = float(indexed_buses_sorted[2][0].Vnom)
    v3: float = float(indexed_buses_sorted[3][0].Vnom)

    if v0 == v1 or v1 == v2 or v2 == v3:
        logger.add_warning(
            f"HV/LV1/LV2/LV3 ambiguous, keeping Vnom-based ordering",
            device=tr_name,
            device_class="Transformer4W",
            value=f"(va={va}, vb={vb}, vc={vc}, vd={vd})"
        )
    else:
        pass

    ordered_original_indices: List[int] = list()
    ordered_original_indices.append(indexed_buses_sorted[0][1])
    ordered_original_indices.append(indexed_buses_sorted[1][1])
    ordered_original_indices.append(indexed_buses_sorted[2][1])
    ordered_original_indices.append(indexed_buses_sorted[3][1])

    return (
        indexed_buses_sorted[0][0],
        indexed_buses_sorted[1][0],
        indexed_buses_sorted[2][0],
        indexed_buses_sorted[3][0],
        ordered_original_indices,
    )



def _apply_tr3_winding_connection_data(
        winding: dev.Winding,
        pf_connection_code: str,
        pf_vector_group_angle: float,
) -> None:
    """
    Apply tr3 winding connection data.

    :param winding: winding parameter.
    :param pf_connection_code: pf_connection_code parameter.
    :param pf_vector_group_angle: pf_vector_group_angle parameter.
    :return: Function result.
    """
    external_connection = _convert_pf_tr2_connection(code=pf_connection_code)
    if external_connection is not None:
        winding.conn_f = WindingType.GroundedStar
        winding.conn_t = external_connection
    else:
        pass

    winding.vector_group_number = int(round(float(pf_vector_group_angle))) % 12


def _get_tr3_winding_branch_tap(
        tap_position: int,
        neutral_position: int,
        step_percent: float,
        step_phase_angle_deg: float,
        vector_group_number: float,
        tap_model_at_star_point: bool,
) -> complex:
    """
    Build one PowerFactory three-winding branch tap in external-to-star orientation.

    :param tap_position: Absolute PowerFactory winding tap position.
    :param neutral_position: Absolute neutral tap position.
    :param step_percent: Magnitude of one complex voltage step in percent.
    :param step_phase_angle_deg: Angle of the complex voltage step in degrees.
    :param vector_group_number: Fixed vector-group displacement in 30-degree units.
    :param tap_model_at_star_point: Whether PowerFactory places the tap at the star point.
    :return: Complete complex external-to-star branch tap.
    """
    # Reconstruct the physical complex step exactly as for a two-winding
    # transformer.  The fixed vector-group displacement is independent of the
    # movable tap position and must always enter the balanced branch equation.
    position_offset: int = int(tap_position) - int(neutral_position)
    voltage_step_pu: float = float(step_percent) / 100.0
    voltage_step_angle_rad: float = math.radians(float(step_phase_angle_deg))
    complex_increment: complex = complex(
        math.cos(voltage_step_angle_rad),
        math.sin(voltage_step_angle_rad),
    )
    position_tap: complex = (
        complex(1.0, 0.0)
        + float(position_offset) * voltage_step_pu * complex_increment
    )
    position_tap_is_finite: bool = (
        math.isfinite(float(position_tap.real))
        and math.isfinite(float(position_tap.imag))
        and abs(position_tap) > 1.0e-9
    )
    if position_tap_is_finite:
        pass
    else:
        position_tap = complex(1.0, 0.0)

    # PowerFactory reports the external winding displacement relative to the
    # HV reference.  The VeraGrid branch is oriented external-to-star, hence
    # the fixed angle enters with the opposite sign.  For example group 5
    # maps an exported LV angle near +135 degrees back to an HV/star angle
    # near -15 degrees through a -150-degree branch tap.
    vector_group_angle_rad: float = math.radians(
        -float(vector_group_number) * 30.0
    )
    vector_group_tap: complex = complex(
        math.cos(vector_group_angle_rad),
        math.sin(vector_group_angle_rad),
    )
    # VeraGrid's branch tap is always located at the external ``from`` side.
    # Moving a PowerFactory star-point tap across the winding impedance keeps
    # the same turns ratio; the corresponding impedance referral is installed
    # separately on the tap changer by ``_apply_tr3_winding_tap_data``.
    branch_tap: complex = vector_group_tap * position_tap
    return branch_tap


def _get_tr3_winding_tap_state(
        current_position: int,
        neutral_position: int,
        minimum_position: int,
        maximum_position: int,
        step_percent: float,
        step_phase_angle_deg: float,
        vector_group_number: float,
        tap_model_at_star_point: bool,
) -> Tuple[float, float, float, float, float, float, np.ndarray, np.ndarray]:
    """
    Evaluate the complete discrete tap window of one three-winding branch.

    :param current_position: Absolute current tap position.
    :param neutral_position: Absolute neutral tap position.
    :param minimum_position: Absolute minimum tap position.
    :param maximum_position: Absolute maximum tap position.
    :param step_percent: Magnitude of one complex voltage step in percent.
    :param step_phase_angle_deg: Angle of the complex voltage step in degrees.
    :param vector_group_number: Fixed vector-group displacement in 30-degree units.
    :param tap_model_at_star_point: Whether the movable tap is at the star point.
    :return: Current module/phase, extrema and exact module/phase arrays.
    """
    bounded_minimum: int = min(int(minimum_position), int(maximum_position))
    bounded_maximum: int = max(int(minimum_position), int(maximum_position))
    position_count: int = bounded_maximum - bounded_minimum + 1
    if position_count > 0:
        pass
    else:
        position_count = 1
    tap_modules: np.ndarray = np.empty(position_count, dtype=float)
    tap_phases: np.ndarray = np.empty(position_count, dtype=float)
    position_index: int
    for position_index in range(position_count):
        evaluated_position: int = bounded_minimum + position_index
        evaluated_tap: complex = _get_tr3_winding_branch_tap(
            tap_position=evaluated_position,
            neutral_position=neutral_position,
            step_percent=step_percent,
            step_phase_angle_deg=step_phase_angle_deg,
            vector_group_number=vector_group_number,
            tap_model_at_star_point=tap_model_at_star_point,
        )
        tap_modules[position_index] = abs(evaluated_tap)
        tap_phases[position_index] = math.atan2(
            evaluated_tap.imag,
            evaluated_tap.real,
        )
    else:
        pass
    tap_phases = np.unwrap(tap_phases)
    bounded_current: int = max(
        bounded_minimum,
        min(int(current_position), bounded_maximum),
    )
    current_index: int = bounded_current - bounded_minimum
    return (
        float(tap_modules[current_index]),
        float(tap_phases[current_index]),
        float(np.min(tap_modules)),
        float(np.max(tap_modules)),
        float(np.min(tap_phases)),
        float(np.max(tap_phases)),
        tap_modules,
        tap_phases,
    )


def _apply_tr3_winding_tap_data(
        winding: dev.Winding,
        current_position: int,
        neutral_position: int,
        minimum_position: int,
        maximum_position: int,
        step_percent: float,
        phase_angle_deg: float,
        vector_group_number: float,
        tap_model_at_star_point: bool,
        effective_tap_module: float | None = None,
) -> None:
    """
    Apply tr3 winding tap data.

    :param winding: winding parameter.
    :param current_position: current_position parameter.
    :param neutral_position: neutral_position parameter.
    :param minimum_position: minimum_position parameter.
    :param maximum_position: maximum_position parameter.
    :param step_percent: step_percent parameter.
    :param phase_angle_deg: phase_angle_deg parameter.
    :param vector_group_number: Fixed phase displacement in 30-degree units.
    :param tap_model_at_star_point: Whether the tap is modelled at the star point.
    :param effective_tap_module: Exact PF winding-ratio module when exported.
    :return: Function result.
    """
    total_positions = int(maximum_position) - int(minimum_position) + 1
    if total_positions <= 0:
        return
    else:
        pass

    tc_type = TapChangerTypes.VoltageRegulation
    if abs(float(phase_angle_deg)) > 1e-12:
        tc_type = TapChangerTypes.Symmetrical
        if abs(abs(float(phase_angle_deg)) % 180.0 - 90.0) < 1e-6:
            tc_type = TapChangerTypes.Asymmetrical
        else:
            pass
    else:
        pass

    winding.tap_changer.total_positions = int(total_positions)
    winding.tap_changer.neutral_position = max(0, int(neutral_position) - int(minimum_position))
    winding.tap_changer.dV = float(step_percent) / 100.0
    winding.tap_changer.asymmetry_angle = float(phase_angle_deg)
    winding.tap_changer.tc_type = tc_type

    tap_position = int(current_position) - int(minimum_position)
    if tap_position < 0:
        tap_position = 0
    else:
        pass
    if tap_position >= winding.tap_changer.total_positions:
        tap_position = winding.tap_changer.total_positions - 1
    else:
        pass
    winding.tap_changer.tap_position = tap_position

    tap_value: float
    tap_phase: float
    tap_min_value: float
    tap_max_value: float
    tap_phase_min: float
    tap_phase_max: float
    tap_modules: np.ndarray
    tap_phases: np.ndarray
    (
        tap_value,
        tap_phase,
        tap_min_value,
        tap_max_value,
        tap_phase_min,
        tap_phase_max,
        tap_modules,
        tap_phases,
    ) = _get_tr3_winding_tap_state(
        current_position=current_position,
        neutral_position=neutral_position,
        minimum_position=minimum_position,
        maximum_position=maximum_position,
        step_percent=step_percent,
        step_phase_angle_deg=phase_angle_deg,
        vector_group_number=vector_group_number,
        tap_model_at_star_point=tap_model_at_star_point,
    )
    effective_module_is_usable: bool = bool(
        effective_tap_module is not None
        and math.isfinite(float(effective_tap_module))
        and float(effective_tap_module) > 1.0e-9
        and tap_value > 1.0e-9
    )
    if effective_module_is_usable and effective_tap_module is not None:
        # ``c:t_*`` is an equipment coefficient, not a solved voltage or flow.
        # PF uses it to compensate the no-load voltage drop between a terminal
        # and a star-point magnetic branch. Scale the complete discrete table
        # so later tap controls retain the same physical normalization.
        module_scale: float = float(effective_tap_module) / tap_value
        tap_modules *= module_scale
        tap_value = float(effective_tap_module)
        tap_min_value = float(np.min(tap_modules))
        tap_max_value = float(np.max(tap_modules))
    else:
        pass
    _apply_branch_tap_state(
        branch=winding,
        tap_value=tap_value,
        tap_phase=tap_phase,
        tap_min_value=tap_min_value,
        tap_max_value=tap_max_value,
        tap_phase_min=tap_phase_min,
        tap_phase_max=tap_phase_max,
    )
    exact_table_applied: bool = winding.tap_changer.set_tap_module_phase_values(
        tap_modules=tap_modules,
        tap_phases=tap_phases,
    )
    if exact_table_applied:
        if tap_model_at_star_point:
            # PF places rCu+jxSigma before the ideal (1+t):1 transformer at
            # the star point. VeraGrid places the ideal transformer before
            # the series branch, so Z must be referred through the ideal
            # transformer as Z/|1+t|^2 at every discrete tap position.
            impedance_corrections: np.ndarray = 1.0 / np.square(tap_modules)
        else:
            # A terminal-side PF tap already has the same ordering as the
            # external-to-star VeraGrid branch and needs no impedance referral.
            impedance_corrections = np.ones(total_positions, dtype=float)
        impedance_table_applied: bool = (
            winding.tap_changer.set_impedance_correction_values(
                correction_real=impedance_corrections,
                correction_imag=impedance_corrections,
            )
        )
        if impedance_table_applied:
            pass
        else:
            pass
    else:
        pass


def _recover_tr3_ascii_effective_tap_module(
        winding: dev.Winding,
        exported_module: float | None,
        discrete_tap_module: float,
        magnetizing_admittance_module: float | None,
        reference_power_mva: float,
        system_base_mva: float,
        recovery_is_applicable: bool,
) -> float | None:
    """Recover precision lost from a calculated PF winding-ratio column.

    PowerFactory's ASCII DGS writer can round ``c:t_*`` to six decimal
    places.  For a terminal-side tap and a star-point magnetic branch, the
    unrounded module is a structural transformer coefficient:
    ``tap * |1 - Z_w * (-j * c:ym)|``.  The reconstruction is accepted only
    when the exported value is visibly six-decimal rounded and the calculated
    value falls inside that exact rounding interval.  Consequently, an
    explicit full-precision coefficient or a different transformer contract
    remains untouched.

    :param winding: VeraGrid winding carrying the star-equivalent impedance.
    :param exported_module: Calculated winding-ratio module from ``c:t_*``.
    :param discrete_tap_module: Module obtained from the physical tap table.
    :param magnetizing_admittance_module: PF star-point ``c:ym`` coefficient.
    :param reference_power_mva: PF magnetic-branch reference power.
    :param system_base_mva: VeraGrid system power base.
    :param recovery_is_applicable: Whether PF uses the supported branch order.
    :return: Recovered module, original module, or ``None`` when unavailable.
    """
    recovered_module: float | None = exported_module
    exported_is_usable: bool = bool(
        exported_module is not None
        and math.isfinite(float(exported_module))
        and float(exported_module) > 1.0e-9
    )
    admittance_is_usable: bool = bool(
        magnetizing_admittance_module is not None
        and math.isfinite(float(magnetizing_admittance_module))
        and float(magnetizing_admittance_module) >= 0.0
    )
    bases_are_usable: bool = bool(
        math.isfinite(float(reference_power_mva))
        and float(reference_power_mva) > 0.0
        and math.isfinite(float(system_base_mva))
        and float(system_base_mva) > 0.0
    )
    discrete_tap_is_usable: bool = bool(
        math.isfinite(float(discrete_tap_module))
        and float(discrete_tap_module) > 1.0e-9
    )
    if (
            recovery_is_applicable
            and exported_is_usable
            and admittance_is_usable
            and bases_are_usable
            and discrete_tap_is_usable
            and exported_module is not None
            and magnetizing_admittance_module is not None
    ):
        # Recover only values that actually carry the characteristic
        # six-decimal ASCII signature. Full-precision DGS definitions remain
        # authoritative even if they happen to be numerically nearby.
        rounded_exported_module: float = round(float(exported_module), 6)
        module_is_six_decimal_rounded: bool = bool(
            abs(float(exported_module) - rounded_exported_module) <= 1.0e-12
        )
        if module_is_six_decimal_rounded:
            impedance_base_factor: float = (
                float(reference_power_mva) / float(system_base_mva)
            )
            winding_impedance: complex = complex(
                float(winding.R) * impedance_base_factor,
                float(winding.X) * impedance_base_factor,
            )
            magnetic_test_admittance: complex = complex(
                0.0,
                -float(magnetizing_admittance_module),
            )
            calculated_module: float = float(discrete_tap_module) * abs(
                1.0 - winding_impedance * magnetic_test_admittance
            )
            ascii_rounding_half_interval: float = 0.500001e-6
            calculated_matches_export: bool = bool(
                math.isfinite(calculated_module)
                and abs(calculated_module - float(exported_module))
                <= ascii_rounding_half_interval
            )
            if calculated_matches_export:
                recovered_module = calculated_module
            else:
                pass
        else:
            pass
    else:
        pass
    return recovered_module


def _apply_tr3_tap_dependent_impedance(
        transformer: dev.Transformer3W,
        transformer_element: ElmTr3,
        transformer_type: TypTr3,
        system_base_mva: float,
        logger: Logger,
        use_power_flow_snapshot: bool = False,
) -> bool:
    """Apply the PF three-path impedance characteristic at the active tap.

    PowerFactory stores minimum, neutral and maximum R/X values for every
    pair-test path. The position belongs to one selected winding, but changing
    it modifies the delta-to-star conversion of all three winding impedances.

    :param transformer: Destination VeraGrid three-winding transformer.
    :param transformer_element: Source element carrying current tap positions.
    :param transformer_type: Source type carrying the impedance curves.
    :param system_base_mva: VeraGrid system base in MVA.
    :param logger: Import logger receiving incomplete-contract diagnostics.
    :param use_power_flow_snapshot: Use exported solved winding positions.
    :return: ``True`` when a complete characteristic was applied.
    """
    characteristic_is_enabled: bool = bool(
        transformer_type.itapzdep is not None
        and int(transformer_type.itapzdep) != 0
    )
    dependent_side: int = (
        -1
        if transformer_type.itapzside is None
        else int(transformer_type.itapzside)
    )
    if dependent_side == 0:
        minimum_position: int = int(transformer_type.n3tmn_h)
        neutral_position: int = int(transformer_type.n3tp0_h)
        maximum_position: int = int(transformer_type.n3tmx_h)
        configured_position: int = int(transformer_element.n3tap_h)
        solved_position: float | None = transformer_element.c_n3tap_h
    else:
        if dependent_side == 1:
            minimum_position = int(transformer_type.n3tmn_m)
            neutral_position = int(transformer_type.n3tp0_m)
            maximum_position = int(transformer_type.n3tmx_m)
            configured_position = int(transformer_element.n3tap_m)
            solved_position = transformer_element.c_n3tap_m
        else:
            if dependent_side == 2:
                minimum_position = int(transformer_type.n3tmn_l)
                neutral_position = int(transformer_type.n3tp0_l)
                maximum_position = int(transformer_type.n3tmx_l)
                configured_position = int(transformer_element.n3tap_l)
                solved_position = transformer_element.c_n3tap_l
            else:
                minimum_position = 0
                neutral_position = 0
                maximum_position = 0
                configured_position = 0
                solved_position = None

    solved_position_is_usable: bool = bool(
        use_power_flow_snapshot
        and solved_position is not None
        and math.isfinite(float(solved_position))
    )
    if solved_position_is_usable and solved_position is not None:
        current_position: int = int(round(float(solved_position)))
    else:
        current_position = configured_position

    endpoint_values: tuple[float | None, ...] = (
        transformer_type.r1putmn_h,
        transformer_type.r1putmn_m,
        transformer_type.r1putmn_l,
        transformer_type.r1putmx_h,
        transformer_type.r1putmx_m,
        transformer_type.r1putmx_l,
        transformer_type.x1putmn_h,
        transformer_type.x1putmn_m,
        transformer_type.x1putmn_l,
        transformer_type.x1putmx_h,
        transformer_type.x1putmx_m,
        transformer_type.x1putmx_l,
    )
    endpoint_values_are_complete: bool = all(
        value is not None and math.isfinite(float(value))
        for value in endpoint_values
    )
    positions_are_valid: bool = bool(
        minimum_position < neutral_position < maximum_position
    )
    path_ratings_mva: np.ndarray = np.array(
        [
            min(float(transformer_type.strn3_h), float(transformer_type.strn3_m)),
            min(float(transformer_type.strn3_m), float(transformer_type.strn3_l)),
            min(float(transformer_type.strn3_l), float(transformer_type.strn3_h)),
        ],
        dtype=float,
    )
    ratings_are_valid: bool = bool(np.all(path_ratings_mva > 0.0))
    can_apply_characteristic: bool = bool(
        characteristic_is_enabled
        and dependent_side in (0, 1, 2)
        and positions_are_valid
        and endpoint_values_are_complete
        and ratings_are_valid
        and math.isfinite(float(system_base_mva))
        and float(system_base_mva) > 0.0
    )
    if can_apply_characteristic:
        # Convert every path from its own minimum winding-rating base to the
        # common system base before the delta-to-star transformation.
        base_conversion: np.ndarray = (
            float(system_base_mva) / path_ratings_mva
        )
        minimum_resistance: np.ndarray = np.array(
            [
                float(transformer_type.r1putmn_h),
                float(transformer_type.r1putmn_m),
                float(transformer_type.r1putmn_l),
            ],
            dtype=float,
        ) * base_conversion
        maximum_resistance: np.ndarray = np.array(
            [
                float(transformer_type.r1putmx_h),
                float(transformer_type.r1putmx_m),
                float(transformer_type.r1putmx_l),
            ],
            dtype=float,
        ) * base_conversion
        minimum_reactance: np.ndarray = np.array(
            [
                float(transformer_type.x1putmn_h),
                float(transformer_type.x1putmn_m),
                float(transformer_type.x1putmn_l),
            ],
            dtype=float,
        ) * base_conversion
        maximum_reactance: np.ndarray = np.array(
            [
                float(transformer_type.x1putmx_h),
                float(transformer_type.x1putmx_m),
                float(transformer_type.x1putmx_l),
            ],
            dtype=float,
        ) * base_conversion
        neutral_resistance: np.ndarray = np.array(
            [transformer.r12, transformer.r23, transformer.r31],
            dtype=float,
        )
        neutral_reactance: np.ndarray = np.array(
            [transformer.x12, transformer.x23, transformer.x31],
            dtype=float,
        )
        characteristic_positions: np.ndarray = np.array(
            [minimum_position, neutral_position, maximum_position],
            dtype=float,
        )
        evaluated_position: np.ndarray = np.array(
            [
                max(
                    minimum_position,
                    min(current_position, maximum_position),
                )
            ],
            dtype=float,
        )
        interpolation_mode: DgsTransformerImpedanceInterpolation = (
            _get_transformer_impedance_interpolation_mode(
                raw_mode=transformer_type.iIntPola,
            )
        )
        evaluated_resistance: np.ndarray = np.empty(3, dtype=float)
        evaluated_reactance: np.ndarray = np.empty(3, dtype=float)
        path_index: int
        for path_index in range(3):
            resistance_curve: np.ndarray = np.array(
                [
                    minimum_resistance[path_index],
                    neutral_resistance[path_index],
                    maximum_resistance[path_index],
                ],
                dtype=float,
            )
            reactance_curve: np.ndarray = np.array(
                [
                    minimum_reactance[path_index],
                    neutral_reactance[path_index],
                    maximum_reactance[path_index],
                ],
                dtype=float,
            )
            evaluated_resistance[path_index] = float(
                _interpolate_transformer_tap_characteristic(
                    characteristic_positions=characteristic_positions,
                    characteristic_values=resistance_curve,
                    evaluation_positions=evaluated_position,
                    mode=interpolation_mode,
                )[0]
            )
            evaluated_reactance[path_index] = float(
                _interpolate_transformer_tap_characteristic(
                    characteristic_positions=characteristic_positions,
                    characteristic_values=reactance_curve,
                    evaluation_positions=evaluated_position,
                    mode=interpolation_mode,
                )[0]
            )
        else:
            pass
        transformer.fill_from_pair_values(
            r12=float(evaluated_resistance[0]),
            r23=float(evaluated_resistance[1]),
            r31=float(evaluated_resistance[2]),
            x12=float(evaluated_reactance[0]),
            x23=float(evaluated_reactance[1]),
            x31=float(evaluated_reactance[2]),
        )
        result: bool = True
    else:
        if characteristic_is_enabled:
            logger.add_warning(
                msg="Incomplete three-winding tap-dependent impedance data",
                device=transformer.name,
                device_class="Transformer3W",
                value=dependent_side,
            )
        else:
            pass
        result = False
    return result

def _fill_tr4w_simple_values(trafo4w: dev.TransformerNW,
                            nominal_voltages: Tuple[float, float, float, float],
                            nominal_powers: Tuple[float, float, float, float],
                            short_circuit_voltages: Tuple[float, float, float, float],
                            copper_losses: Tuple[float, float, float, float],
                            Pfe: float,
                            I0: float,
                            Sbase: float) -> None:
    """
    Fill four-winding transformer values from simplified per-winding input data.

    :param trafo4w: Four-winding transformer.
    :param nominal_voltages: DGS-side voltages in h0, l1, l2, l3 order.
    :param nominal_powers: DGS-side powers in h0, l1, l2, l3 order.
    :param short_circuit_voltages: DGS-side short-circuit voltages in h0, l1, l2, l3 order.
    :param copper_losses: DGS-side copper losses in h0, l1, l2, l3 order.
    :param ordered_original_indices: Mapping from transformer winding order to original DGS-side order.
    :param Pfe: Shared iron-core losses in kW.
    :param I0: Shared no-load current in percent.
    :param Sbase: System base power in MVA.
    :return: None.
    """

    for winding_index in range(4):
        winding: dev.Winding = trafo4w.windings[winding_index]

        winding.HV = nominal_voltages[winding_index]
        winding.LV = 1.0

        winding.Sn = nominal_powers[winding_index]
        winding.rate = nominal_powers[winding_index]
        winding.design_rate = nominal_powers[winding_index]

        winding.Pcu = copper_losses[winding_index]
        winding.Vsc = short_circuit_voltages[winding_index]

    trafo4w.Pfe = Pfe
    trafo4w.I0 = I0

    trafo4w.recalculate_windings_from_definition(Sbase=Sbase)

    # PowerFactory owns one magnetic branch at the side selected by
    # ``TypTr4.imagloc``. Remove the symmetric pi branch created by the generic
    # design-value helper; the importer materializes the exact nodal branch
    # after the complete transformer topology has been attached to the grid.
    winding_index: int
    for winding_index in range(len(trafo4w.windings)):
        winding: dev.Winding = trafo4w.windings[winding_index]
        winding.G = 0.0
        winding.B = 0.0
    else:
        pass

def _get_tr4_pair_impedance_on_hv_base(
        short_circuit_voltage_percent: float,
        copper_losses_kw: float,
        high_voltage_rated_power_mva: float,
        first_rated_power_mva: float,
        second_rated_power_mva: float,
) -> complex:
    """Convert one four-winding short-circuit test to the HV power base.

    :param short_circuit_voltage_percent: Pair short-circuit voltage in percent.
    :param copper_losses_kw: Pair copper losses in kW.
    :param high_voltage_rated_power_mva: HV winding rated power in MVA.
    :param first_rated_power_mva: First tested winding rated power in MVA.
    :param second_rated_power_mva: Second tested winding rated power in MVA.
    :return: Complex pair impedance on the HV winding power base.
    """
    pair_rated_power_mva: float = min(
        first_rated_power_mva,
        second_rated_power_mva,
    )
    if pair_rated_power_mva > 0.0 and high_voltage_rated_power_mva > 0.0:
        impedance_magnitude: float = (
            abs(short_circuit_voltage_percent)
            / 100.0
            * high_voltage_rated_power_mva
            / pair_rated_power_mva
        )
        resistance: float = (
            copper_losses_kw
            / 1000.0
            * high_voltage_rated_power_mva
            / (pair_rated_power_mva * pair_rated_power_mva)
        )
        reactance: float = math.sqrt(max(
            impedance_magnitude * impedance_magnitude - resistance * resistance,
            0.0,
        ))
        impedance: complex = complex(resistance, reactance)
    else:
        impedance = complex(0.0, 0.0)
    return impedance


def _set_tr4_terminal_winding_impedance(
        winding: dev.Winding,
        impedance_hv_base: complex,
        nominal_voltage_kv: float,
        nominal_power_mva: float,
        high_voltage_rated_power_mva: float,
        system_base_mva: float,
) -> None:
    """Install one terminal-arm impedance and its human-readable design data.

    :param winding: VeraGrid terminal winding to update.
    :param impedance_hv_base: Arm impedance on the transformer HV power base.
    :param nominal_voltage_kv: Winding rated voltage in kV.
    :param nominal_power_mva: Winding rated power in MVA.
    :param high_voltage_rated_power_mva: Transformer HV rated power in MVA.
    :param system_base_mva: VeraGrid circuit base power in MVA.
    :return: None.
    """
    if high_voltage_rated_power_mva > 0.0:
        impedance_system_base: complex = (
            impedance_hv_base
            * system_base_mva
            / high_voltage_rated_power_mva
        )
    else:
        impedance_system_base = complex(0.0, 0.0)
    if nominal_power_mva > 0.0 and high_voltage_rated_power_mva > 0.0:
        impedance_winding_base: complex = (
            impedance_hv_base
            * nominal_power_mva
            / high_voltage_rated_power_mva
        )
    else:
        impedance_winding_base = complex(0.0, 0.0)

    winding.HV = nominal_voltage_kv
    winding.LV = 1.0
    winding.Sn = nominal_power_mva
    winding.rate = nominal_power_mva
    winding.design_rate = nominal_power_mva
    winding.R = float(impedance_system_base.real)
    winding.X = float(impedance_system_base.imag)
    winding.R2 = float(impedance_system_base.real)
    winding.X2 = float(impedance_system_base.imag)
    winding.Pcu = float(
        impedance_winding_base.real * nominal_power_mva * 1000.0
    )
    winding.Vsc = float(abs(impedance_winding_base) * 100.0)


def _fill_tr4w_complete_values(
        trafo4w: dev.TransformerNW,
        V_h0: float,
        V_l1: float,
        V_l2: float,
        V_l3: float,
        Sn_h0: float,
        Sn_l1: float,
        Sn_l2: float,
        Sn_l3: float,
        Vsc_h0l1: float,
        Vsc_h0l2: float,
        Vsc_h0l3: float,
        Vsc_l1l2: float,
        Vsc_l1l3: float,
        Vsc_l2l3: float,
        Pcu_h0l1: float,
        Pcu_h0l2: float,
        Pcu_h0l3: float,
        Pcu_l1l2: float,
        Pcu_l1l3: float,
        Pcu_l2l3: float,
        Pfe: float,
        I0: float = 0.5,
        Sbase: float = 100.0,
) -> None:
    """Build PowerFactory's exact complete-input four-winding bridge.

    The four terminal arms and the two repeated bridge impedances follow the
    PowerFactory ``TypTr4`` equations directly. The bridge must remain an
    internal sparse network; reducing it to a single star changes its multiport
    behaviour whenever more than two windings carry current.

    :param trafo4w: Four-winding transformer to populate.
    :param V_h0: HV rated voltage in kV.
    :param V_l1: LV1 rated voltage in kV.
    :param V_l2: LV2 rated voltage in kV.
    :param V_l3: LV3 rated voltage in kV.
    :param Sn_h0: HV rated power in MVA.
    :param Sn_l1: LV1 rated power in MVA.
    :param Sn_l2: LV2 rated power in MVA.
    :param Sn_l3: LV3 rated power in MVA.
    :param Vsc_h0l1: HV-LV1 short-circuit voltage in percent.
    :param Vsc_h0l2: HV-LV2 short-circuit voltage in percent.
    :param Vsc_h0l3: HV-LV3 short-circuit voltage in percent.
    :param Vsc_l1l2: LV1-LV2 short-circuit voltage in percent.
    :param Vsc_l1l3: LV1-LV3 short-circuit voltage in percent.
    :param Vsc_l2l3: LV2-LV3 short-circuit voltage in percent.
    :param Pcu_h0l1: HV-LV1 copper losses in kW.
    :param Pcu_h0l2: HV-LV2 copper losses in kW.
    :param Pcu_h0l3: HV-LV3 copper losses in kW.
    :param Pcu_l1l2: LV1-LV2 copper losses in kW.
    :param Pcu_l1l3: LV1-LV3 copper losses in kW.
    :param Pcu_l2l3: LV2-LV3 copper losses in kW.
    :param Pfe: Shared iron losses in kW.
    :param I0: Shared no-load current in percent.
    :param Sbase: VeraGrid circuit base power in MVA.
    :return: None.
    """
    z_h0l1: complex = _get_tr4_pair_impedance_on_hv_base(
        Vsc_h0l1, Pcu_h0l1, Sn_h0, Sn_h0, Sn_l1,
    )
    z_h0l2: complex = _get_tr4_pair_impedance_on_hv_base(
        Vsc_h0l2, Pcu_h0l2, Sn_h0, Sn_h0, Sn_l2,
    )
    z_h0l3: complex = _get_tr4_pair_impedance_on_hv_base(
        Vsc_h0l3, Pcu_h0l3, Sn_h0, Sn_h0, Sn_l3,
    )
    z_l1l2: complex = _get_tr4_pair_impedance_on_hv_base(
        Vsc_l1l2, Pcu_l1l2, Sn_h0, Sn_l1, Sn_l2,
    )
    z_l1l3: complex = _get_tr4_pair_impedance_on_hv_base(
        Vsc_l1l3, Pcu_l1l3, Sn_h0, Sn_l1, Sn_l3,
    )
    z_l2l3: complex = _get_tr4_pair_impedance_on_hv_base(
        Vsc_l2l3, Pcu_l2l3, Sn_h0, Sn_l2, Sn_l3,
    )

    k1: complex = z_h0l2 + z_l1l3 - z_h0l1 - z_l2l3
    k2: complex = z_h0l2 + z_l1l3 - z_h0l3 - z_l1l2
    k: complex = cmath.sqrt(k1 * k2)
    z_internal_i: complex = k1 + k
    z_internal_j: complex = k2 + k
    z_h0: complex = (z_h0l1 + z_h0l3 - z_l1l3 - k) / 2.0
    z_l1: complex = (z_h0l1 + z_l1l2 - z_h0l2 - k) / 2.0
    z_l2: complex = (z_l1l2 + z_l2l3 - z_l1l3 - k) / 2.0
    z_l3: complex = (z_l2l3 + z_h0l3 - z_h0l2 - k) / 2.0

    nominal_voltages: Tuple[float, float, float, float] = (
        V_h0, V_l1, V_l2, V_l3,
    )
    nominal_powers: Tuple[float, float, float, float] = (
        Sn_h0, Sn_l1, Sn_l2, Sn_l3,
    )
    terminal_impedances: Tuple[complex, complex, complex, complex] = (
        z_h0, z_l1, z_l2, z_l3,
    )
    winding_index: int
    for winding_index in range(4):
        _set_tr4_terminal_winding_impedance(
            winding=trafo4w.windings[winding_index],
            impedance_hv_base=terminal_impedances[winding_index],
            nominal_voltage_kv=nominal_voltages[winding_index],
            nominal_power_mva=nominal_powers[winding_index],
            high_voltage_rated_power_mva=Sn_h0,
            system_base_mva=Sbase,
        )
    else:
        pass

    system_base_factor: float
    if Sn_h0 > 0.0:
        system_base_factor = Sbase / Sn_h0
    else:
        system_base_factor = 0.0
    internal_impedances: dev.ImpedanceTripletList = dev.ImpedanceTripletList()
    if abs(z_internal_i) > 1.0e-15 or abs(z_internal_j) > 1.0e-15:
        # Node order is HV-centre, LV1-lower, LV2-middle, LV3-upper,
        # matching the PowerFactory bridge diagram.
        internal_impedances.append(dev.ImpedanceTriplet(
            i=0, j=3, imp=z_internal_i * system_base_factor,
        ))
        internal_impedances.append(dev.ImpedanceTriplet(
            i=2, j=1, imp=z_internal_i * system_base_factor,
        ))
        internal_impedances.append(dev.ImpedanceTriplet(
            i=0, j=1, imp=z_internal_j * system_base_factor,
        ))
        internal_impedances.append(dev.ImpedanceTriplet(
            i=3, j=2, imp=z_internal_j * system_base_factor,
        ))
    else:
        pass
    trafo4w.internal_impedances = internal_impedances
    # The shared magnetic branch is not a symmetric winding pi shunt. It is
    # attached separately to the exact side selected by ``TypTr4.imagloc``.
    winding_index = 0
    for winding_index in range(len(trafo4w.windings)):
        trafo4w.windings[winding_index].G = 0.0
        trafo4w.windings[winding_index].B = 0.0
    else:
        pass


def _get_magnetizing_admittance_voltage_factor(
        connection_bus: dev.Bus,
        rated_winding_voltage_kv: float,
) -> float:
    """Convert a transformer magnetic admittance to the terminal voltage base.

    PowerFactory reports the no-load test on the selected transformer's rated
    winding voltage. VeraGrid fixed-shunt ``G/B`` values, however, express the
    power consumed at the connected bus nominal voltage. Because a physical
    admittance consumes power proportionally to squared voltage, preserving
    the same admittance requires the squared voltage-base ratio.

    :param connection_bus: VeraGrid bus receiving the magnetic branch.
    :param rated_winding_voltage_kv: PowerFactory winding rated voltage in kV.
    :return: Squared bus-to-winding voltage ratio, or unity for legacy data
        without a valid rated voltage.
    """
    bus_nominal_voltage_kv: float = float(connection_bus.Vnom)
    voltage_data_is_valid: bool = bool(
        math.isfinite(bus_nominal_voltage_kv)
        and bus_nominal_voltage_kv > 0.0
        and math.isfinite(rated_winding_voltage_kv)
        and rated_winding_voltage_kv > 0.0
    )
    if voltage_data_is_valid:
        voltage_ratio: float = bus_nominal_voltage_kv / rated_winding_voltage_kv
        result: float = voltage_ratio * voltage_ratio
    else:
        # Old DGS export definitions may omit winding rated voltages. Unity
        # keeps their historical deterministic behaviour instead of guessing.
        result = 1.0
    return result


def _get_transformer4w_saturation_zip_coefficients(
        template: TypTr4,
        connection_bus: dev.Bus,
        rated_winding_voltage_kv: float,
) -> tuple[float, float] | None:
    """Linearize one active PowerFactory saturation-curve segment exactly.

    ``satvol`` contains winding-base voltage in p.u. and ``satcue`` the
    corresponding reactive magnetizing current in percent.  On one linear
    segment, ``I(V) = a + b V`` and therefore the consumed reactive power is
    exactly ``Q(Vbus) = q_current Vbus + q_admittance Vbus**2``.  VeraGrid's
    ZIP load can represent that polynomial without changing Newton equations.

    The conversion is deliberately fail-closed: unsupported interpolation,
    extrapolation, malformed curves, or an initial voltage outside the curve
    retain the legacy fixed-shunt path.

    :param template: PowerFactory four-winding transformer type.
    :param connection_bus: Bus receiving the magnetic branch.
    :param rated_winding_voltage_kv: Selected winding nameplate voltage.
    :return: Reactive current and admittance coefficients in MVAr, or ``None``.
    """
    saturation_is_enabled: bool = bool(
        int(template.ksat) > 0
        and int(template.iInterPol) == 0
        and len(template.satvol) == len(template.satcue)
        and len(template.satvol) >= 2
    )
    if not saturation_is_enabled:
        return None
    else:
        pass

    curve_points: list[tuple[float, float]] = list()
    raw_voltage: float | None
    raw_current_percent: float | None
    for raw_voltage, raw_current_percent in zip(template.satvol, template.satcue):
        point_is_valid: bool = bool(
            raw_voltage is not None
            and raw_current_percent is not None
            and math.isfinite(float(raw_voltage))
            and math.isfinite(float(raw_current_percent))
            and float(raw_voltage) > 0.0
            and float(raw_current_percent) >= 0.0
        )
        if point_is_valid:
            curve_points.append((float(raw_voltage), float(raw_current_percent)))
        else:
            return None
    else:
        pass

    point_index: int
    for point_index in range(len(curve_points) - 1):
        if curve_points[point_index + 1][0] > curve_points[point_index][0]:
            pass
        else:
            return None
    else:
        pass

    bus_nominal_voltage_kv: float = float(connection_bus.Vnom)
    voltage_data_is_valid: bool = bool(
        math.isfinite(bus_nominal_voltage_kv)
        and bus_nominal_voltage_kv > 0.0
        and math.isfinite(rated_winding_voltage_kv)
        and rated_winding_voltage_kv > 0.0
    )
    if voltage_data_is_valid:
        bus_to_winding_voltage_ratio: float = (
            bus_nominal_voltage_kv / rated_winding_voltage_kv
        )
    else:
        bus_to_winding_voltage_ratio = 1.0

    initial_bus_voltage_pu: float = float(connection_bus.Vm0)
    initial_winding_voltage_pu: float = (
        initial_bus_voltage_pu * bus_to_winding_voltage_ratio
    )
    initial_voltage_is_supported: bool = bool(
        math.isfinite(initial_winding_voltage_pu)
        and curve_points[0][0] <= initial_winding_voltage_pu <= curve_points[-1][0]
    )
    if not initial_voltage_is_supported:
        return None
    else:
        pass

    selected_point_index: int = len(curve_points) - 2
    for point_index in range(len(curve_points) - 1):
        if initial_winding_voltage_pu <= curve_points[point_index + 1][0]:
            selected_point_index = point_index
            break
        else:
            pass
    else:
        pass

    voltage_1, current_1_percent = curve_points[selected_point_index]
    voltage_2, current_2_percent = curve_points[selected_point_index + 1]
    current_slope_percent: float = (
        (current_2_percent - current_1_percent) / (voltage_2 - voltage_1)
    )
    current_intercept_percent: float = (
        current_1_percent - current_slope_percent * voltage_1
    )
    rated_power_mva: float = max(float(template.sn_h0), 0.0)
    current_power_coefficient_mvar: float = (
        rated_power_mva
        * current_intercept_percent
        * bus_to_winding_voltage_ratio
        / 100.0
    )
    admittance_power_coefficient_mvar: float = (
        rated_power_mva
        * current_slope_percent
        * bus_to_winding_voltage_ratio
        * bus_to_winding_voltage_ratio
        / 100.0
    )
    return current_power_coefficient_mvar, admittance_power_coefficient_mvar


def _add_transformer4w_magnetizing_shunt(
        grid: dev.MultiCircuit,
        transformer: dev.TransformerNW,
        transformer_element: ElmTr4,
        template: TypTr4,
        system_base_mva: float,
        logger: Logger,
) -> dev.Shunt | dev.Load | None:
    """Materialize one PowerFactory four-winding magnetic branch.

    ``TypTr4.imagloc`` selects one physical transformer terminal. The branch
    cannot be represented by ``Winding.G/B`` because that produces a symmetric
    pi shunt and places half the magnetic current at an internal bridge node.

    :param grid: Destination VeraGrid circuit.
    :param transformer: Imported four-winding transformer.
    :param transformer_element: Source element with effective susceptance.
    :param template: Source PowerFactory four-winding type.
    :param system_base_mva: DGS load-flow system base in MVA.
    :param logger: Import logger receiving unsupported-location diagnostics.
    :return: Added magnetic shunt, or ``None`` when no branch is declared.
    """
    iron_loss_mw: float = max(float(template.pfe) / 1000.0, 0.0)
    effective_susceptance_pu: float = float(transformer_element.bSbasepu)
    effective_susceptance_is_available: bool = bool(
        math.isfinite(effective_susceptance_pu)
        and abs(effective_susceptance_pu) > 0.0
        and system_base_mva > 0.0
    )
    if effective_susceptance_is_available:
        reactive_loss_mvar: float = (
            effective_susceptance_pu * system_base_mva
        )
    else:
        # Legacy DGS definitions may omit the effective element coefficient.
        # Reconstruct the ordinary terminal no-load test deterministically.
        no_load_apparent_power_mva: float = (
            abs(float(template.curmag))
            * max(float(template.sn_h0), 0.0)
            / 100.0
        )
        reactive_loss_mvar = -math.sqrt(max(
            no_load_apparent_power_mva * no_load_apparent_power_mva
            - iron_loss_mw * iron_loss_mw,
            0.0,
        ))
    saturation_curve_is_declared: bool = bool(
        int(template.ksat) > 0
        and len(template.satvol) >= 2
        and len(template.satcue) >= 2
    )
    branch_is_declared: bool = bool(
        iron_loss_mw > 0.0
        or abs(reactive_loss_mvar) > 0.0
        or saturation_curve_is_declared
    )
    location_code: int = int(template.imagloc)
    location_is_supported: bool = bool(
        0 <= location_code < len(transformer.windings)
    )
    if branch_is_declared and location_is_supported:
        selected_winding: dev.Winding = transformer.windings[location_code]
        connection_bus: dev.Bus | None = selected_winding.bus_from
        if connection_bus is not None:
            rated_winding_voltages_kv: tuple[float, float, float, float] = (
                float(template.un_h0),
                float(template.un_l1),
                float(template.un_l2),
                float(template.un_l3),
            )
            # Translate the PF no-load test from the winding nameplate base to
            # the actual terminal bus base used by VeraGrid's fixed shunt.
            admittance_voltage_factor: float = (
                _get_magnetizing_admittance_voltage_factor(
                    connection_bus=connection_bus,
                    rated_winding_voltage_kv=(
                        rated_winding_voltages_kv[location_code]
                    ),
                )
            )
            transformer_idtag: str = str(transformer.idtag)
            saturation_zip_coefficients: tuple[float, float] | None = (
                _get_transformer4w_saturation_zip_coefficients(
                    template=template,
                    connection_bus=connection_bus,
                    rated_winding_voltage_kv=(
                        rated_winding_voltages_kv[location_code]
                    ),
                )
            )
            magnetic_branch_is_active: bool = bool(
                transformer.active and selected_winding.active
            )
            if saturation_zip_coefficients is not None:
                current_coefficient_mvar, admittance_coefficient_mvar = (
                    saturation_zip_coefficients
                )
                magnetic_load: dev.Load = dev.Load(
                    name=f"{transformer.name} magnetizing branch",
                    idtag=f"{transformer_idtag}:magnetizing",
                    code=(
                        f"TypTr4.imagloc={location_code};"
                        "saturation=piecewise-linear"
                    ),
                    G=iron_loss_mw * admittance_voltage_factor,
                    Ii=-current_coefficient_mvar,
                    B=-admittance_coefficient_mvar,
                    active=magnetic_branch_is_active,
                )
                grid.add_load(bus=connection_bus, api_obj=magnetic_load)
                result: dev.Shunt | dev.Load | None = magnetic_load
            else:
                magnetic_shunt: dev.Shunt = dev.Shunt(
                    name=f"{transformer.name} magnetizing branch",
                    idtag=f"{transformer_idtag}:magnetizing",
                    code=f"TypTr4.imagloc={location_code}",
                    G=iron_loss_mw * admittance_voltage_factor,
                    B=reactive_loss_mvar * admittance_voltage_factor,
                    active=magnetic_branch_is_active,
                )
                grid.add_shunt(bus=connection_bus, api_obj=magnetic_shunt)
                result = magnetic_shunt
        else:
            logger.add_warning(
                msg="Disconnected TypTr4 magnetizing impedance side",
                device=transformer.name,
                device_class="Transformer4W",
                value=location_code,
            )
            result = None
    else:
        if branch_is_declared and not location_is_supported:
            logger.add_warning(
                msg="Unsupported TypTr4 magnetizing impedance location",
                device=transformer.name,
                device_class="Transformer4W",
                value=location_code,
            )
        else:
            pass
        result = None
    return result



def _apply_tr4_winding_tap_data(
        windings: Tuple[dev.Winding, ...],
        current_positions: Tuple[int, int, int, int],
        neutral_positions: Tuple[int, int, int, int],
        minimum_positions: Tuple[int, int, int, int],
        maximum_positions: Tuple[int, int, int, int],
        step_percents: Tuple[float, float, float, float],
        phase_angle_degs: Tuple[float, float, float, float],
        vector_group_numbers: Tuple[float, float, float, float],
) -> None:
    """
    Apply tr4 winding tap data.

    :param windings: Four transformer windings.
    :param current_positions: Current tap positions for h0, l1, l2 and l3.
    :param neutral_positions: Neutral tap positions for h0, l1, l2 and l3.
    :param minimum_positions: Minimum tap positions for h0, l1, l2 and l3.
    :param maximum_positions: Maximum tap positions for h0, l1, l2 and l3.
    :param step_percents: Tap step percentages for h0, l1, l2 and l3.
    :param phase_angle_degs: Tap phase angles in degrees for h0, l1, l2 and l3.
    :param vector_group_numbers: Fixed displacements in 30-degree units.
    :return: None.
    """
    for winding_index in range(4):
        winding: dev.Winding = windings[winding_index]

        # A four-winding transformer uses the same external-to-star tap
        # contract as each branch of a three-winding transformer.  Reusing the
        # typed implementation prevents the two multi-winding paths from
        # drifting in fixed phase, complex step and discrete-position logic.
        _apply_tr3_winding_tap_data(
            winding=winding,
            current_position=current_positions[winding_index],
            neutral_position=neutral_positions[winding_index],
            minimum_position=minimum_positions[winding_index],
            maximum_position=maximum_positions[winding_index],
            step_percent=step_percents[winding_index],
            phase_angle_deg=phase_angle_degs[winding_index],
            vector_group_number=vector_group_numbers[winding_index],
            tap_model_at_star_point=False,
        )
    else:
        pass


def convert_dgs_to_transformer(tr2: ElmTr2,
                               buses: List[dev.Bus],
                               stacubic_dict: Dict[str, List[int]],
                               templates_dict: Dict[str, dev.TransformerType],
                               typtr2_dict: Dict[str, TypTr2],
                               freq: float,
                               baseMVA: float,
                               logger: Logger,
                               cubics_by_objid: Dict[str, List[StaCubic]],
                               bus_by_term_id: Dict[str, dev.Bus],
                               switch_by_cubic_id: Dict[str, StaSwitch],
                               parallel_index: int = 0,
                               parallel_count: int = 1,
                               use_power_flow_snapshot: bool = False,
                               use_power_flow_tap_guess: bool = False) -> dev.Transformer2W:
    """
    Convert dgs to transformer.

    :param tr2: tr2 parameter.
    :param buses: buses parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param templates_dict: templates_dict parameter.
    :param typtr2_dict: typtr2_dict parameter.
    :param freq: freq parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param use_power_flow_snapshot: Use the solved ``c:nntap`` snapshot position.
    :param use_power_flow_tap_guess: Seed ``c:nntap`` while retaining controls.
    :return: Function result.
    """
    template = templates_dict.get(tr2.typ_id, None)
    if template is None:
        template = templates_dict.get(_ref_id(tr2.typ_id), None)

    if template is None:
        raise ValueError(f"No template for the transformer {tr2.ID}")

    # Resolve the raw TypTr2 (needed to parse tap settings: step/min/max/neutral)
    typtr2_raw = _resolve_pointer_dict_value(key=tr2.typ_id, mapping=typtr2_dict)
    if typtr2_raw is None:
        raise ValueError(f"No raw TypTr2 data for the transformer {tr2.ID}")
    else:
        pass

    # Check connectivity through robust StaCubic.fold_id mapping first (preferred)
    term_ids = get_terminal_ids(element_id=tr2.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) != 2:
        # Fall back to legacy check only if terminal mapping is not available
        bus_ids = stacubic_dict.get(_ref_id(tr2.ID), None)
        if bus_ids is None:
            raise ValueError(f"No buses for the transformer {tr2.ID}")

        if len(bus_ids) != 2:
            raise ValueError(f"Not exactly 2 buses for the transformer {tr2.ID}")

    bus_from, bus_to = get_branch_buses(elm_id=tr2.ID,
                                        stacubic_dict=stacubic_dict,
                                        buses=buses,
                                        cubics_by_objid=cubics_by_objid,
                                        bus_by_term_id=bus_by_term_id)

    cbs = cubics_by_objid.get(_ref_id(tr2.ID), [])
    has_dgs_from_to = (len(cbs) == 2) and ({int(cb.obj_bus) for cb in cbs} == {0, 1})

    if has_dgs_from_to:
        bus_vg_from, bus_vg_to = bus_from, bus_to
    else:
        bus_vg_from, bus_vg_to = _order_hv_lv(bus_a=bus_from, bus_b=bus_to, logger=logger, tr_name=tr2.loc_name)

    transformer_name = _get_non_empty_name(tr2.loc_name, f"Transformer_{_ref_id(tr2.ID)}")
    transformer_name = _get_parallel_device_name(transformer_name, parallel_index, parallel_count)
    transformer_idtag = _get_parallel_device_idtag(_ref_id(tr2.ID), parallel_index, parallel_count)

    trafo = dev.Transformer2W(bus_from=bus_vg_from,
                              bus_to=bus_vg_to,
                              name=transformer_name,
                              idtag=transformer_idtag,
                              active=not tr2.outserv and _is_element_closed_by_cubicle_switches(element_id=tr2.ID,
                                                                                                cubics_by_objid=cubics_by_objid,
                                                                                                switch_by_cubic_id=switch_by_cubic_id), )

    trafo.apply_template(obj=template, Sbase=baseMVA, logger=logger)
    # PowerFactory solves TypTr2 as a magnetic T circuit.  Eliminate its
    # internal node once during import so every VeraGrid solver consumes the
    # same two-terminal physical primitive.
    _apply_powerfactory_tr2_t_equivalent(
        transformer=trafo,
        source_transformer=tr2,
        source_type=typtr2_raw,
        system_base_mva=baseMVA,
        logger=logger,
    )
    # Keep the physical winding selector because station step-up controls use
    # opposite tap signs for HV-side and LV-side tap changers.
    trafo.tap_changer_on_high_voltage_side = int(typtr2_raw.tap_side) == 0
    trafo.vector_group_number = int(round(float(typtr2_raw.nt2ag))) % 12
    trafo.rate = float(trafo.rate) * float(tr2.ratfac)

    #   - TypTr2.dutap   : tap step in percent (%)
    #   - TypTr2.nntap0  : neutral position (integer)
    #   - TypTr2.ntpmn   : minimum position (integer)
    #   - TypTr2.ntpmx   : maximum position (integer)
    #   - TypTr2.tap_side: side where the tap-changer is located (typically 0=HV, 1=LV)
    #   - ElmTr2.nntap   : current position (integer)

    # PowerFactory stores both taps and vector-group displacement in the HV/LV
    # type definition.  Determine the physical branch orientation once so the
    # same complex conversion is used for the current position and limits.
    if has_dgs_from_to:
        # Complete StaCubic roles are the authoritative PowerFactory winding
        # semantics: obj_bus=0 is the HV terminal and is sorted first by
        # ``get_terminal_ids``.  Voltage is only a legacy fallback.
        bus_from_is_hv: bool = True
    else:
        bus_from_is_hv = float(bus_vg_from.Vnom) >= float(bus_vg_to.Vnom)
    absolute_tap_position: int
    if int(typtr2_raw.itapch) != 0:
        solved_tap_position: int | None = tr2.c_nntap
        solved_tap_is_usable: bool = (
            (use_power_flow_snapshot or use_power_flow_tap_guess)
            and
            solved_tap_position is not None
            and math.isfinite(float(solved_tap_position))
        )
        if solved_tap_is_usable and solved_tap_position is not None:
            # ``c:nntap`` is a solved ComLdf result.  It is authoritative only
            # for the explicit snapshot path; a normal control solve must start
            # from the configured ``nntap`` position and reproduce tap actions.
            absolute_tap_position = int(round(float(solved_tap_position)))
        else:
            absolute_tap_position = int(tr2.nntap)
        minimum_absolute_position: int = min(int(typtr2_raw.ntpmn), int(typtr2_raw.ntpmx))
        maximum_absolute_position: int = max(int(typtr2_raw.ntpmn), int(typtr2_raw.ntpmx))
        absolute_tap_position = max(
            minimum_absolute_position,
            min(absolute_tap_position, maximum_absolute_position),
        )

        # Retain the discrete position in the reusable VeraGrid tap changer so
        # editing and round-trip export keep the original physical state.
        relative_tap_position: int = absolute_tap_position - minimum_absolute_position
        if 0 <= relative_tap_position < trafo.tap_changer.total_positions:
            trafo.tap_changer.tap_position = relative_tap_position
        else:
            pass
    else:
        # A fixed transformer can still have a non-zero vector-group phase.
        absolute_tap_position = int(typtr2_raw.nntap0)

    complex_tap_module: float
    complex_tap_phase: float
    complex_tap_module_min: float
    complex_tap_module_max: float
    complex_tap_phase_min: float
    complex_tap_phase_max: float
    exact_tap_modules: np.ndarray
    exact_tap_phases: np.ndarray
    (
        complex_tap_module,
        complex_tap_phase,
        complex_tap_module_min,
        complex_tap_module_max,
        complex_tap_phase_min,
        complex_tap_phase_max,
        exact_tap_modules,
        exact_tap_phases,
    ) = _get_transformer_branch_tap_state(
        typtr2=typtr2_raw,
        tap_position=absolute_tap_position,
        bus_from_is_hv=bus_from_is_hv,
    )
    # ``curmg`` also normalizes PowerFactory's nominal winding ratio for the
    # no-load drop across the HV leakage arm.  Scale the full discrete table,
    # keeping both the configured position and any automatic controller live.
    tap_normalization: float = _get_powerfactory_tr2_tap_normalization(
        source_transformer=tr2,
        bus_from_is_hv=bus_from_is_hv,
        current_tap_module=complex_tap_module,
    )
    complex_tap_module *= tap_normalization
    complex_tap_module_min *= tap_normalization
    complex_tap_module_max *= tap_normalization
    exact_tap_modules = exact_tap_modules * tap_normalization
    _apply_branch_tap_state(
        branch=trafo,
        tap_value=complex_tap_module,
        tap_phase=complex_tap_phase,
        tap_min_value=complex_tap_module_min,
        tap_max_value=complex_tap_module_max,
        tap_phase_min=complex_tap_phase_min,
        tap_phase_max=complex_tap_phase_max,
    )
    exact_tap_table_applied: bool = trafo.tap_changer.set_tap_module_phase_values(
        tap_modules=exact_tap_modules,
        tap_phases=exact_tap_phases,
    )
    if exact_tap_table_applied:
        pass
    else:
        logger.add_warning(
            msg="PowerFactory transformer exact tap table could not be retained",
            device=trafo.name,
            device_class="Transformer2W",
        )

    # Preserve the independent R/X characteristic in the existing tap
    # changer contract.  Legacy DGS files omit these optional type columns and
    # therefore keep the neutral constant-impedance behaviour explicitly.
    resistance_correction_factors: np.ndarray
    reactance_correction_factors: np.ndarray
    impedance_characteristic_is_available: bool
    (
        resistance_correction_factors,
        reactance_correction_factors,
        impedance_characteristic_is_available,
    ) = _get_transformer_impedance_correction_tables(typtr2=typtr2_raw)
    if impedance_characteristic_is_available:
        impedance_table_applied: bool = (
            trafo.tap_changer.set_impedance_correction_values(
                correction_real=resistance_correction_factors,
                correction_imag=reactance_correction_factors,
            )
        )
        if impedance_table_applied:
            pass
        else:
            logger.add_warning(
                msg="PowerFactory transformer impedance table could not be retained",
                device=trafo.name,
                device_class="Transformer2W",
            )
    else:
        tap_impedance_was_declared: bool = (
            typtr2_raw.itapzdep is not None
            and int(typtr2_raw.itapzdep) != 0
        )
        if tap_impedance_was_declared:
            logger.add_warning(
                msg="PowerFactory tap-dependent impedance data is incomplete",
                device=trafo.name,
                device_class="Transformer2W",
            )
        else:
            pass

    if use_power_flow_snapshot:
        # Snapshot replay uses the solved ``c:nntap`` position exported by
        # PowerFactory. Re-running the automatic tap controller would replace
        # that discrete solved state and invalidate the transported snapshot.
        trafo.tap_module_control_mode = TapModuleControl.fixed
        trafo.regulation_bus = None
    elif int(tr2.ntrcn) != 0:
        # ``cpCtrlNode`` is PowerFactory's calculated effective control node.
        # Prefer that explicit identity whenever the DGS exports it.  ``t2ldc``
        # remains the side fallback for older files without the pointer.
        controlled_node_code: int = int(tr2.t2ldc)
        if bus_from_is_hv:
            hv_bus: dev.Bus = bus_vg_from
            lv_bus: dev.Bus = bus_vg_to
        else:
            hv_bus = bus_vg_to
            lv_bus = bus_vg_from

        explicit_control_bus: dev.Bus | None = None
        control_pointer_candidates: List[str | None] = list((
            tr2.cpCtrlNode,
            tr2.p_rem,
        ))
        control_pointer: str | None
        for control_pointer in control_pointer_candidates:
            if explicit_control_bus is None and control_pointer is not None:
                control_pointer_id: str = _ref_id(control_pointer)
                explicit_control_bus = bus_by_term_id.get(
                    control_pointer_id,
                    None,
                )
            else:
                pass
        else:
            pass

        if explicit_control_bus is not None:
            trafo.tap_module_control_mode = TapModuleControl.Vm
            trafo.regulation_bus = explicit_control_bus
        else:
            if controlled_node_code == 0:
                trafo.tap_module_control_mode = TapModuleControl.Vm
                trafo.regulation_bus = hv_bus
            else:
                if controlled_node_code == 1:
                    trafo.tap_module_control_mode = TapModuleControl.Vm
                    trafo.regulation_bus = lv_bus
                else:
                    trafo.tap_module_control_mode = TapModuleControl.fixed
                    trafo.regulation_bus = None
                    logger.add_warning(
                        msg="External PowerFactory transformer control node is absent from DGS",
                        device=trafo.name,
                        device_class="Transformer2W",
                        value=controlled_node_code,
                    )

        if trafo.tap_module_control_mode == TapModuleControl.Vm:
            use_control_bus_target: bool = (
                tr2.uset_mode is not None
                and int(tr2.uset_mode) == 1
                and trafo.regulation_bus is not None
            )
            if use_control_bus_target and trafo.regulation_bus is not None:
                trafo.vset = float(trafo.regulation_bus.voltage_control_target)
            else:
                if float(tr2.usetp) > 0.0:
                    trafo.vset = float(tr2.usetp)
                else:
                    pass

            lower_voltage_bound: float = float(tr2.usp_low)
            upper_voltage_bound: float = float(tr2.usp_up)
            bounds_are_valid: bool = (
                lower_voltage_bound > 0.0
                and upper_voltage_bound > 0.0
                and lower_voltage_bound <= upper_voltage_bound
            )
            if bounds_are_valid:
                trafo.vset_min = lower_voltage_bound
                trafo.vset_max = upper_voltage_bound
            else:
                pass
        else:
            pass
    else:
        pass

    if float(typtr2_raw.uk0tr) > 0.0:
        nominal_power = float(typtr2_raw.strn)
        if nominal_power > 0.0:
            z0_pu = (float(typtr2_raw.uk0tr) / 100.0) * (float(baseMVA) / nominal_power)
            r0_pu = (float(typtr2_raw.ur0tr) / 100.0) * (float(baseMVA) / nominal_power)
            x0_sq = max(0.0, z0_pu * z0_pu - r0_pu * r0_pu)
            trafo.R0 = r0_pu
            trafo.X0 = math.sqrt(x0_sq)
        else:
            pass
    else:
        pass

    trafo.R2 = trafo.R
    trafo.X2 = trafo.X
    # ---------------------------------------------------------------

    # The explicit TypTr2 rated voltages are electrical data, not cosmetic
    # metadata. PowerFactory legitimately uses ratios beyond ten percent to
    # represent fixed off-nominal transformation (for example 67.5/60 kV).
    # Generic UI consistency repair would erase that physical virtual tap and
    # must therefore never run on a deterministic DGS import.
    _synchronize_transformer_snapshot_profiles(trafo=trafo)

    return trafo


def _add_transformer3w_magnetizing_shunt(
        grid: dev.MultiCircuit,
        transformer: dev.Transformer3W,
        transformer_element: ElmTr3,
        template: TypTr3,
        logger: Logger,
) -> dev.Shunt | None:
    """Materialize the PowerFactory three-winding magnetic branch.

    PowerFactory represents ``Pfe`` and ``curm3`` as ``rFe || xM`` in the
    transformer's T-equivalent. ``i3loc`` selects the electrical node where
    that branch is connected. A dedicated fixed shunt preserves the
    asymmetric placement exactly; assigning ``G/B`` to a winding would create
    a symmetric pi equivalent and distribute half of the branch to the wrong
    node.

    :param grid: Destination VeraGrid circuit.
    :param transformer: Imported three-winding transformer.
    :param transformer_element: Source element carrying effective coefficients.
    :param template: Source PowerFactory three-winding type.
    :param logger: Import logger receiving unsupported-location diagnostics.
    :return: Added magnetic shunt, or ``None`` when no branch is declared.
    """
    reference_power_mva: float = max(float(template.strn3_h), 0.0)
    no_load_current_percent: float = abs(float(template.curm3))
    iron_loss_mw: float = max(float(template.pfe) / 1000.0, 0.0)
    effective_admittance_is_available: bool = bool(
        transformer_element.c_ym is not None
        and math.isfinite(float(transformer_element.c_ym))
        and float(transformer_element.c_ym) >= 0.0
    )
    if effective_admittance_is_available and transformer_element.c_ym is not None:
        # ``curm3`` is the terminal no-load test current. PowerFactory converts
        # that test to the T-equivalent star-node admittance after accounting
        # for the asymmetric leakage arms. The exported ``c:ym`` coefficient
        # is therefore the structural value that belongs at the star node.
        no_load_apparent_power_mva: float = (
            float(transformer_element.c_ym) * reference_power_mva
        )
    else:
        # Legacy DGS definitions do not carry the effective coefficient. The
        # direct no-load test conversion remains exact for ordinary symmetric
        # types and provides a deterministic degradation for older files.
        no_load_apparent_power_mva = (
            no_load_current_percent * reference_power_mva / 100.0
        )
    no_load_reactive_power_mvar: float = math.sqrt(max(
        no_load_apparent_power_mva * no_load_apparent_power_mva
        - iron_loss_mw * iron_loss_mw,
        0.0,
    ))
    branch_is_declared: bool = bool(
        iron_loss_mw > 0.0 or no_load_reactive_power_mvar > 0.0
    )
    location_code: int = int(template.i3loc)
    location_is_supported: bool = location_code in (
        DgsTransformer3WMagnetizingLocation.StarPoint,
        DgsTransformer3WMagnetizingLocation.HighVoltageSide,
        DgsTransformer3WMagnetizingLocation.MediumVoltageSide,
        DgsTransformer3WMagnetizingLocation.LowVoltageSide,
    )
    if branch_is_declared and location_is_supported:
        core_is_energized: bool = bool(
            transformer.active
            and (
                transformer.winding1.active
                or transformer.winding2.active
                or transformer.winding3.active
            )
        )
        location: DgsTransformer3WMagnetizingLocation = (
            DgsTransformer3WMagnetizingLocation(location_code)
        )
        if location == DgsTransformer3WMagnetizingLocation.StarPoint:
            connection_bus: dev.Bus = transformer.bus0
            magnetic_branch_is_active: bool = core_is_energized
            # The internal star point is already represented on the
            # transformer reference base, so it needs no terminal conversion.
            admittance_voltage_factor: float = 1.0
        else:
            if location == DgsTransformer3WMagnetizingLocation.HighVoltageSide:
                selected_winding: dev.Winding = transformer.winding1
                rated_winding_voltage_kv: float = float(template.utrn3_h)
            else:
                if location == DgsTransformer3WMagnetizingLocation.MediumVoltageSide:
                    selected_winding = transformer.winding2
                    rated_winding_voltage_kv = float(template.utrn3_m)
                else:
                    selected_winding = transformer.winding3
                    rated_winding_voltage_kv = float(template.utrn3_l)
            selected_terminal_bus: dev.Bus | None = selected_winding.bus_from
            if (
                    not selected_winding.active
                    and core_is_energized
                    and selected_terminal_bus is not None
            ):
                # A cubicle switch is outside the transformer enclosure. The
                # winding and a magnetic branch located at that side remain
                # connected behind the open switch and are energized through
                # the other windings. A hidden equipment-owned terminal keeps
                # that physical topology without reconnecting the grid bus.
                transformer_idtag_for_bus: str = str(transformer.idtag)
                internal_terminal_bus: dev.Bus = dev.Bus(
                    name=f"{transformer.name} internal magnetic terminal",
                    idtag=f"{transformer_idtag_for_bus}:magnetic_terminal",
                    Vnom=float(selected_terminal_bus.Vnom),
                    xpos=float(selected_terminal_bus.x),
                    ypos=float(selected_terminal_bus.y),
                    is_internal=True,
                )
                grid.add_bus(obj=internal_terminal_bus)
                selected_winding.bus_from = internal_terminal_bus
                selected_winding.active = True
                connection_bus = internal_terminal_bus
                magnetic_branch_is_active = True
            else:
                if selected_terminal_bus is not None:
                    connection_bus = selected_terminal_bus
                    magnetic_branch_is_active = bool(
                        core_is_energized and selected_winding.active
                    )
                else:
                    connection_bus = transformer.bus0
                    magnetic_branch_is_active = False
            # A side-located magnetic branch is a physical admittance. Convert
            # its PF winding-nameplate test power to VeraGrid's bus base.
            admittance_voltage_factor = (
                _get_magnetizing_admittance_voltage_factor(
                    connection_bus=connection_bus,
                    rated_winding_voltage_kv=rated_winding_voltage_kv,
                )
            )
        transformer_idtag: str = str(transformer.idtag)
        magnetic_shunt: dev.Shunt = dev.Shunt(
            name=f"{transformer.name} magnetizing branch",
            idtag=f"{transformer_idtag}:magnetizing",
            code=f"TypTr3.i3loc={location_code}",
            G=iron_loss_mw * admittance_voltage_factor,
            B=-no_load_reactive_power_mvar * admittance_voltage_factor,
            active=magnetic_branch_is_active,
        )
        grid.add_shunt(bus=connection_bus, api_obj=magnetic_shunt)
        result: dev.Shunt | None = magnetic_shunt
    else:
        if branch_is_declared and not location_is_supported:
            logger.add_warning(
                msg="Unsupported TypTr3 magnetizing impedance location",
                device=transformer.name,
                device_class="Transformer3W",
                value=location_code,
            )
        else:
            pass
        result = None
    return result


def convert_dgs_to_transformer3w(tr3: ElmTr3,
                                 buses: List[dev.Bus],
                                 stacubic_dict: Dict[str, List[int]],
                                 templates_dict: Dict[str, TypTr3],
                                 baseMVA: float,
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus],
                                 switch_by_cubic_id: Dict[str, StaSwitch],
                                 parallel_index: int = 0,
                                 parallel_count: int = 1,
                                 use_power_flow_snapshot: bool = False,
                                 use_power_flow_tap_guess: bool = False) -> dev.Transformer3W:
    """
    Convert dgs to transformer3w.

    :param tr3: tr3 parameter.
    :param buses: buses parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param templates_dict: templates_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param use_power_flow_snapshot: Freeze the exported solved tap state.
    :param use_power_flow_tap_guess: Seed solved taps while retaining controls.
    :return: Function result.
    """
    template = _resolve_pointer_dict_value(key=tr3.typ_id, mapping=templates_dict)
    if template is None:
        raise ValueError(f"No TypTr3 data for transformer {tr3.ID}")
    else:
        pass

    # Check connectivity through robust StaCubic.fold_id mapping first (preferred)
    term_ids = get_terminal_ids(element_id=tr3.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 3:
        bus_a = bus_by_term_id[term_ids[0]]
        bus_b = bus_by_term_id[term_ids[1]]
        bus_c = bus_by_term_id[term_ids[2]]
    else:
        bus_ids = stacubic_dict[_ref_id(tr3.ID)]
        bus_a = buses[bus_ids[0]]
        bus_b = buses[bus_ids[1]]
        bus_c = buses[bus_ids[2]]

    bus_hv, bus_mv, bus_lv = _order_hv_mv_lv(bus_a=bus_a,
                                             bus_b=bus_b,
                                             bus_c=bus_c,
                                             logger=logger,
                                             tr_name=tr3.loc_name)

    # Graphic position not working right now
    x = (float(bus_hv.x) + float(bus_mv.x) + float(bus_lv.x)) / 3.0
    y = (float(bus_hv.y) + float(bus_mv.y) + float(bus_lv.y)) / 3.0

    transformer_name = _get_non_empty_name(tr3.loc_name, f"Transformer3W_{_ref_id(tr3.ID)}")
    transformer_name = _get_parallel_device_name(transformer_name, parallel_index, parallel_count)
    transformer_idtag = _get_parallel_device_idtag(_ref_id(tr3.ID), parallel_index, parallel_count)

    transformer_is_active: bool = int(tr3.outserv) == 0
    internal_bus_idtag = f"{transformer_idtag}:bus0" if transformer_idtag else None
    trafo3w = dev.Transformer3W(name=transformer_name,
                                idtag=transformer_idtag,
                                bus0=dev.Bus(name=f"{transformer_name}_bus",
                                             idtag=internal_bus_idtag,
                                             Vnom=1.0,
                                             xpos=x,
                                             ypos=y,
                                             is_internal=True),
                                bus1=bus_hv,
                                bus2=bus_mv,
                                bus3=bus_lv,
                                w1_idtag=f"{transformer_idtag}:W1" if transformer_idtag else None,
                                w2_idtag=f"{transformer_idtag}:W2" if transformer_idtag else None,
                                w3_idtag=f"{transformer_idtag}:W3" if transformer_idtag else None,
                                active=transformer_is_active,
                                x=x,
                                y=y)

    trafo3w.fill_from_design_values(
        V1=float(template.utrn3_h),
        V2=float(template.utrn3_m),
        V3=float(template.utrn3_l),
        Sn1=float(template.strn3_h),
        Sn2=float(template.strn3_m),
        Sn3=float(template.strn3_l),
        Pcu12=float(template.pcut3_h),
        Pcu23=float(template.pcut3_m),
        Pcu31=float(template.pcut3_l),
        Vsc12=float(template.uktr3_h),
        Vsc23=float(template.uktr3_m),
        Vsc31=float(template.uktr3_l),
        Pfe=float(template.pfe),
        I0=float(template.curm3),
        Sbase=float(baseMVA),
    )

    hv_position: int = int(tr3.n3tap_h)
    mv_position: int = int(tr3.n3tap_m)
    lv_position: int = int(tr3.n3tap_l)
    use_solved_tap_positions: bool = bool(
        use_power_flow_snapshot or use_power_flow_tap_guess
    )
    if use_solved_tap_positions:
        # A snapshot uses the three independent solved positions when they
        # were exported. Missing legacy result columns retain the configured
        # positions explicitly instead of fabricating a solved state.
        solved_hv_is_usable: bool = bool(
            tr3.c_n3tap_h is not None
            and math.isfinite(float(tr3.c_n3tap_h))
        )
        solved_mv_is_usable: bool = bool(
            tr3.c_n3tap_m is not None
            and math.isfinite(float(tr3.c_n3tap_m))
        )
        solved_lv_is_usable: bool = bool(
            tr3.c_n3tap_l is not None
            and math.isfinite(float(tr3.c_n3tap_l))
        )
        if solved_hv_is_usable and tr3.c_n3tap_h is not None:
            hv_position = int(round(float(tr3.c_n3tap_h)))
        else:
            pass
        if solved_mv_is_usable and tr3.c_n3tap_m is not None:
            mv_position = int(round(float(tr3.c_n3tap_m)))
        else:
            pass
        if solved_lv_is_usable and tr3.c_n3tap_l is not None:
            lv_position = int(round(float(tr3.c_n3tap_l)))
        else:
            pass
    else:
        pass

    # ``c:t_*`` is structural, but the PF ASCII writer can retain only six
    # decimals for this calculated column.  When its own T-equivalent proves
    # that the rounded value is the no-load winding correction, reconstruct
    # the missing digits before creating the tap tables.  No solved voltage,
    # power or snapshot quantity participates in this calculation.
    recovery_is_applicable: bool = bool(
        int(template.itapos) != 0
        and int(template.i3loc)
        == int(DgsTransformer3WMagnetizingLocation.StarPoint)
    )
    hv_discrete_tap: complex = _get_tr3_winding_branch_tap(
        tap_position=hv_position,
        neutral_position=int(template.n3tp0_h),
        step_percent=float(template.du3tp_h),
        step_phase_angle_deg=float(template.ph3tr_h),
        vector_group_number=float(template.nt3ag_h),
        tap_model_at_star_point=False,
    )
    mv_discrete_tap: complex = _get_tr3_winding_branch_tap(
        tap_position=mv_position,
        neutral_position=int(template.n3tp0_m),
        step_percent=float(template.du3tp_m),
        step_phase_angle_deg=float(template.ph3tr_m),
        vector_group_number=float(template.nt3ag_m),
        tap_model_at_star_point=False,
    )
    lv_discrete_tap: complex = _get_tr3_winding_branch_tap(
        tap_position=lv_position,
        neutral_position=int(template.n3tp0_l),
        step_percent=float(template.du3tp_l),
        step_phase_angle_deg=float(template.ph3tr_l),
        vector_group_number=float(template.nt3ag_l),
        tap_model_at_star_point=False,
    )
    hv_effective_tap_module: float | None = (
        _recover_tr3_ascii_effective_tap_module(
            winding=trafo3w.winding1,
            exported_module=tr3.c_t_h,
            discrete_tap_module=abs(hv_discrete_tap),
            magnetizing_admittance_module=tr3.c_ym,
            reference_power_mva=float(template.strn3_h),
            system_base_mva=baseMVA,
            recovery_is_applicable=recovery_is_applicable,
        )
    )
    mv_effective_tap_module: float | None = (
        _recover_tr3_ascii_effective_tap_module(
            winding=trafo3w.winding2,
            exported_module=tr3.c_t_m,
            discrete_tap_module=abs(mv_discrete_tap),
            magnetizing_admittance_module=tr3.c_ym,
            reference_power_mva=float(template.strn3_h),
            system_base_mva=baseMVA,
            recovery_is_applicable=recovery_is_applicable,
        )
    )
    lv_effective_tap_module: float | None = (
        _recover_tr3_ascii_effective_tap_module(
            winding=trafo3w.winding3,
            exported_module=tr3.c_t_l,
            discrete_tap_module=abs(lv_discrete_tap),
            magnetizing_admittance_module=tr3.c_ym,
            reference_power_mva=float(template.strn3_h),
            system_base_mva=baseMVA,
            recovery_is_applicable=recovery_is_applicable,
        )
    )

    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding1,
        current_position=hv_position,
        neutral_position=int(template.n3tp0_h),
        minimum_position=int(template.n3tmn_h),
        maximum_position=int(template.n3tmx_h),
        step_percent=float(template.du3tp_h),
        phase_angle_deg=float(template.ph3tr_h),
        vector_group_number=float(template.nt3ag_h),
        tap_model_at_star_point=int(template.itapos) == 0,
        effective_tap_module=hv_effective_tap_module,
    )
    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding2,
        current_position=mv_position,
        neutral_position=int(template.n3tp0_m),
        minimum_position=int(template.n3tmn_m),
        maximum_position=int(template.n3tmx_m),
        step_percent=float(template.du3tp_m),
        phase_angle_deg=float(template.ph3tr_m),
        vector_group_number=float(template.nt3ag_m),
        tap_model_at_star_point=int(template.itapos) == 0,
        effective_tap_module=mv_effective_tap_module,
    )
    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding3,
        current_position=lv_position,
        neutral_position=int(template.n3tp0_l),
        minimum_position=int(template.n3tmn_l),
        maximum_position=int(template.n3tmx_l),
        step_percent=float(template.du3tp_l),
        phase_angle_deg=float(template.ph3tr_l),
        vector_group_number=float(template.nt3ag_l),
        tap_model_at_star_point=int(template.itapos) == 0,
        effective_tap_module=lv_effective_tap_module,
    )

    # Evaluate the complete three-path characteristic only after all current
    # tap positions are known. One selected OLTC changes the star conversion
    # of every winding even though its turns ratio belongs to a single side.
    _apply_tr3_tap_dependent_impedance(
        transformer=trafo3w,
        transformer_element=tr3,
        transformer_type=template,
        system_base_mva=baseMVA,
        logger=logger,
        use_power_flow_snapshot=use_solved_tap_positions,
    )

    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding1,
        pf_connection_code=str(template.tr3cn_h),
        pf_vector_group_angle=float(template.nt3ag_h)
    )
    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding2,
        pf_connection_code=str(template.tr3cn_m),
        pf_vector_group_angle=float(template.nt3ag_m)
    )
    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding3,
        pf_connection_code=str(template.tr3cn_l),
        pf_vector_group_angle=float(template.nt3ag_l)
    )

    hv_closed, mv_closed, lv_closed = _get_tr3_winding_closed_states(
        tr3_id=tr3.ID,
        cubics_by_objid=cubics_by_objid,
        switch_by_cubic_id=switch_by_cubic_id,
        bus_by_term_id=bus_by_term_id,
        bus_hv=bus_hv,
        bus_mv=bus_mv,
        bus_lv=bus_lv,
    )
    # A winding is available only when both the parent transformer and its
    # own terminal switch are in service.  Keeping these states independent
    # could otherwise energize one star-equivalent branch of an out-of-service
    # PowerFactory transformer.
    trafo3w.winding1.active = transformer_is_active and hv_closed
    trafo3w.winding2.active = transformer_is_active and mv_closed
    trafo3w.winding3.active = transformer_is_active and lv_closed

    # ElmTr3 stores two independent side selectors: ``ictrlside`` identifies
    # the physical tap winding, while ``t3ldc`` identifies the voltage node
    # regulated by that winding. External control (selector 3) needs an
    # exported terminal pointer and therefore fails closed when unavailable.
    winding_by_side: Tuple[dev.Winding, dev.Winding, dev.Winding] = (
        trafo3w.winding1,
        trafo3w.winding2,
        trafo3w.winding3,
    )
    bus_by_side: Tuple[dev.Bus, dev.Bus, dev.Bus] = (
        bus_hv,
        bus_mv,
        bus_lv,
    )
    automatic_control_requested: bool = bool(
        transformer_is_active
        and int(tr3.ntrcn) != 0
        and not use_power_flow_snapshot
    )
    tap_side_is_supported: bool = bool(
        0 <= int(tr3.ictrlside) < len(winding_by_side)
    )
    controlled_side_is_supported: bool = bool(
        0 <= int(tr3.t3ldc) < len(bus_by_side)
    )
    if automatic_control_requested and tap_side_is_supported and controlled_side_is_supported:
        control_winding: dev.Winding = winding_by_side[int(tr3.ictrlside)]
        if bool(control_winding.active):
            control_winding.tap_module_control_mode = TapModuleControl.Vm
            control_winding.regulation_bus = bus_by_side[int(tr3.t3ldc)]
            if float(tr3.usetp) > 0.0:
                control_winding.vset = float(tr3.usetp)
            else:
                control_winding.vset = 1.0
            # PowerFactory applies the explicit ElmTr3 voltage band before it
            # considers another discrete tap.  Replacing that band with a
            # synthetic half-step band changes valid operating points and can
            # drive a warm-started transformer away from its exported tap.
            lower_voltage_bound: float = float(tr3.usp_low)
            upper_voltage_bound: float = float(tr3.usp_up)
            voltage_bounds_are_valid: bool = bool(
                lower_voltage_bound > 0.0
                and upper_voltage_bound > 0.0
                and lower_voltage_bound <= upper_voltage_bound
            )
            if voltage_bounds_are_valid:
                control_winding.vset_min = lower_voltage_bound
                control_winding.vset_max = upper_voltage_bound
            else:
                # Legacy DGS files may omit the band. Quantize only that
                # incomplete contract with half one physical tap step.
                control_half_step_pu: float = 0.5 * abs(
                    float(control_winding.tap_changer.dV)
                )
                control_winding.vset_min = (
                    float(control_winding.vset) - control_half_step_pu
                )
                control_winding.vset_max = (
                    float(control_winding.vset) + control_half_step_pu
                )
        else:
            pass
    else:
        if automatic_control_requested:
            logger.add_warning(
                "Unsupported ElmTr3 automatic tap control side",
                device=trafo3w.name,
                device_class="Transformer3W",
                value=f"ictrlside={tr3.ictrlside}, t3ldc={tr3.t3ldc}",
            )
        else:
            pass

    return trafo3w

def convert_dgs_to_transformer4w(tr4: ElmTr4,
                                 buses: List[dev.Bus],
                                 stacubic_dict: Dict[str, List[int]],
                                 templates_dict: Dict[str, TypTr4],
                                 baseMVA: float,
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus],
                                 switch_by_cubic_id: Dict[str, StaSwitch],
                                 parallel_index: int = 0,
                                 parallel_count: int = 1,
                                 use_power_flow_snapshot: bool = False,
                                 use_power_flow_tap_guess: bool = False) -> dev.TransformerNW:
    """
    Convert dgs to transformer4w.

    :param tr4: tr4 parameter.
    :param buses: buses parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param templates_dict: templates_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param use_power_flow_snapshot: Freeze the exported solved tap state.
    :param use_power_flow_tap_guess: Seed solved taps while retaining controls.
    :return: Function result.
    """
    template = _resolve_pointer_dict_value(key=tr4.typ_id, mapping=templates_dict)
    if template is None:
        raise ValueError(f"No TypTr4 data for transformer {tr4.ID}")
    else:
        pass

    # Check connectivity through robust StaCubic.fold_id mapping first (preferred)
    term_ids = get_terminal_ids(element_id=tr4.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 4:
        bus_a = bus_by_term_id[term_ids[0]]
        bus_b = bus_by_term_id[term_ids[1]]
        bus_c = bus_by_term_id[term_ids[2]]
        bus_d = bus_by_term_id[term_ids[3]]
    else:
        bus_ids = stacubic_dict[_ref_id(tr4.ID)]
        bus_a = buses[bus_ids[0]]
        bus_b = buses[bus_ids[1]]
        bus_c = buses[bus_ids[2]]
        bus_d = buses[bus_ids[3]]

    # bus_hv, bus_lv1, bus_lv2, bus_lv3, ordered_original_indices = _order_tr4(bus_a=bus_a, bus_b=bus_b, bus_c=bus_c, bus_d=bus_d, logger=logger, tr_name=tr4.loc_name)

    cubic_by_id: Dict[str, StaCubic] = dict()
    for cubic in cubics_by_objid.get(_ref_id(tr4.ID), list()):
        cubic_id: str | None = _ref_id(cubic.ID)
        if cubic_id is not None and cubic_id != "":
            cubic_by_id[cubic_id] = cubic
        else:
            pass

    cubic_hv: StaCubic | None = _resolve_pointer_dict_value(key=tr4.bush0, mapping=cubic_by_id)
    cubic_lv1: StaCubic | None = _resolve_pointer_dict_value(key=tr4.busl1, mapping=cubic_by_id)
    cubic_lv2: StaCubic | None = _resolve_pointer_dict_value(key=tr4.busl2, mapping=cubic_by_id)
    cubic_lv3: StaCubic | None = _resolve_pointer_dict_value(key=tr4.busl3, mapping=cubic_by_id)

    if cubic_hv is None or cubic_lv1 is None or cubic_lv2 is None or cubic_lv3 is None:
        raise ValueError(f"Missing one or more ElmTr4 side cubicles for transformer {tr4.ID}")
    else:
        pass

    term_hv: str | None = _ref_id(cubic_hv.fold_id)
    term_lv1: str | None = _ref_id(cubic_lv1.fold_id)
    term_lv2: str | None = _ref_id(cubic_lv2.fold_id)
    term_lv3: str | None = _ref_id(cubic_lv3.fold_id)

    if term_hv is None or term_lv1 is None or term_lv2 is None or term_lv3 is None:
        raise ValueError(f"Missing one or more ElmTr4 side terminals for transformer {tr4.ID}")
    else:
        pass

    bus_hv: dev.Bus = bus_by_term_id[term_hv]
    bus_lv1: dev.Bus = bus_by_term_id[term_lv1]
    bus_lv2: dev.Bus = bus_by_term_id[term_lv2]
    bus_lv3: dev.Bus = bus_by_term_id[term_lv3]

    # Graphic position not working right now
    x = (float(bus_hv.x) + float(bus_lv1.x) + float(bus_lv2.x) + float(bus_lv3.x)) / 4.0
    y = (float(bus_hv.y) + float(bus_lv1.y) + float(bus_lv2.y) + float(bus_lv3.y)) / 4.0

    transformer_name = _get_non_empty_name(tr4.loc_name, f"Transformer4W_{_ref_id(tr4.ID)}")
    transformer_name = _get_parallel_device_name(transformer_name, parallel_index, parallel_count)
    transformer_idtag = _get_parallel_device_idtag(_ref_id(tr4.ID), parallel_index, parallel_count)

    internal_bus_idtag = f"{transformer_idtag}:bus0" if transformer_idtag else None
    trafo4w = dev.TransformerNW(
        idtag=transformer_idtag,
        code=_ref_id(tr4.ID) or "",
        name=transformer_name,
        bus0=dev.Bus(name=f"{transformer_name}_bus",
                     idtag=internal_bus_idtag,
                     Vnom=1.0,
                     xpos=x,
                     ypos=y,
                     is_internal=True),
        winding_count=4,
        buses=[
            bus_hv,
            bus_lv1,
            bus_lv2,
            bus_lv3,
        ],
        active=(int(tr4.outserv) == 0),
        Pfe=float(template.pfe),
        I0=float(template.curmag),
        x=x,
        y=y,
    )

    if transformer_idtag:
        for winding_index, winding in enumerate(trafo4w.windings):
            winding.idtag = f"{transformer_idtag}:W{winding_index + 1}"

    if template.inputData == 0:
        _fill_tr4w_complete_values(
            trafo4w=trafo4w,
            V_h0=template.un_h0,
            V_l1=template.un_l1,
            V_l2=template.un_l2,
            V_l3=template.un_l3,

            Sn_h0=template.sn_h0,
            Sn_l1=template.sn_l1,
            Sn_l2=template.sn_l2,
            Sn_l3=template.sn_l3,

            Vsc_h0l1=template.uk_h0l1,
            Vsc_h0l2=template.uk_h0l2,
            Vsc_h0l3=template.uk_h0l3,
            Vsc_l1l2=template.uk_l1l2,
            Vsc_l1l3=template.uk_l1l3,
            Vsc_l2l3=template.uk_l2l3,

            Pcu_h0l1=template.pcu_h0l1,
            Pcu_h0l2=template.pcu_h0l2,
            Pcu_h0l3=template.pcu_h0l3,
            Pcu_l1l2=template.pcu_l1l2,
            Pcu_l1l3=template.pcu_l1l3,
            Pcu_l2l3=template.pcu_l2l3,

            Pfe=template.pfe,
            I0=template.curmag,
            Sbase=baseMVA,
        )
    else:
        _fill_tr4w_simple_values(
            trafo4w=trafo4w,
            nominal_voltages=(
                template.un_h0,
                template.un_l1,
                template.un_l2,
                template.un_l3,
            ),
            nominal_powers=(
                template.sn_h0,
                template.sn_l1,
                template.sn_l2,
                template.sn_l3,
            ),
            short_circuit_voltages=(
                template.uk_h0,
                template.uk_l1,
                template.uk_l2,
                template.uk_l3,
            ),
            copper_losses=(
                template.pcu_h0,
                template.pcu_l1,
                template.pcu_l2,
                template.pcu_l3,
            ),
            Pfe=template.pfe,
            I0=template.curmag,
            Sbase=baseMVA,
        )

    current_positions: List[int] = list((
        int(tr4.ntap_h0),
        int(tr4.ntap_l1),
        int(tr4.ntap_l2),
        int(tr4.ntap_l3),
    ))
    use_solved_tap_positions: bool = bool(
        use_power_flow_snapshot or use_power_flow_tap_guess
    )
    if use_solved_tap_positions:
        solved_positions: tuple[float | None, ...] = (
            tr4.c_ntap_h0,
            tr4.c_ntap_l1,
            tr4.c_ntap_l2,
            tr4.c_ntap_l3,
        )
        position_index: int
        for position_index in range(len(current_positions)):
            solved_position: float | None = solved_positions[position_index]
            solved_position_is_usable: bool = bool(
                solved_position is not None
                and math.isfinite(float(solved_position))
            )
            if solved_position_is_usable and solved_position is not None:
                current_positions[position_index] = int(
                    round(float(solved_position))
                )
            else:
                pass
        else:
            pass
    else:
        pass

    _apply_tr4_winding_tap_data(
        windings=trafo4w.windings,
        current_positions=tuple(current_positions),
        neutral_positions=(
            template.ntapneu_h0,
            template.ntapneu_l1,
            template.ntapneu_l2,
            template.ntapneu_l3,
        ),
        minimum_positions=(
            template.ntapmin_h0,
            template.ntapmin_l1,
            template.ntapmin_l2,
            template.ntapmin_l3,
        ),
        maximum_positions=(
            template.ntapmax_h0,
            template.ntapmax_l1,
            template.ntapmax_l2,
            template.ntapmax_l3,
        ),
        step_percents=(
            template.dutap_h0,
            template.dutap_l1,
            template.dutap_l2,
            template.dutap_l3,
        ),
        phase_angle_degs=(
            template.phitr_h0,
            template.phitr_l1,
            template.phitr_l2,
            template.phitr_l3,
        ),
        vector_group_numbers=(
            template.trangle_h0,
            template.trangle_l1,
            template.trangle_l2,
            template.trangle_l3,
        ),
    )

    _apply_tr3_winding_connection_data(
        winding=trafo4w.windings[0],
        pf_connection_code=str(template.trcon_h0),
        pf_vector_group_angle=float(template.trangle_h0),
    )
    _apply_tr3_winding_connection_data(
        winding=trafo4w.windings[1],
        pf_connection_code=str(template.trcon_l1),
        pf_vector_group_angle=float(template.trangle_l1),
    )
    _apply_tr3_winding_connection_data(
        winding=trafo4w.windings[2],
        pf_connection_code=str(template.trcon_l2),
        pf_vector_group_angle=float(template.trangle_l2),
    )
    _apply_tr3_winding_connection_data(
        winding=trafo4w.windings[3],
        pf_connection_code=str(template.trcon_l3),
        pf_vector_group_angle=float(template.trangle_l3),
    )

    # ElmTr4 extends the ElmTr3 control contract to four windings. The tap
    # winding and regulated voltage side are independent selectors.
    winding_by_side: tuple[dev.Winding, ...] = tuple(trafo4w.windings)
    bus_by_side: tuple[dev.Bus, ...] = (
        bus_hv,
        bus_lv1,
        bus_lv2,
        bus_lv3,
    )
    automatic_control_requested: bool = bool(
        trafo4w.active
        and int(tr4.ntrcn) != 0
        and not use_power_flow_snapshot
    )
    tap_side_is_supported: bool = bool(
        0 <= int(tr4.ictrlside) < len(winding_by_side)
    )
    local_control_side_is_supported: bool = bool(
        0 <= int(tr4.t4ldc) < len(bus_by_side)
    )
    if local_control_side_is_supported:
        regulation_bus: dev.Bus | None = bus_by_side[int(tr4.t4ldc)]
    else:
        control_pointer_id: str | None = _ref_id(tr4.cpCtrlNode)
        if int(tr4.t4ldc) == len(bus_by_side) and control_pointer_id is not None:
            regulation_bus = bus_by_term_id.get(control_pointer_id, None)
        else:
            regulation_bus = None
    if automatic_control_requested and tap_side_is_supported and regulation_bus is not None:
        control_winding: dev.Winding = winding_by_side[int(tr4.ictrlside)]
        control_winding.tap_module_control_mode = TapModuleControl.Vm
        control_winding.regulation_bus = regulation_bus
        if float(tr4.usetp) > 0.0:
            control_winding.vset = float(tr4.usetp)
        else:
            control_winding.vset = 1.0
        lower_voltage_bound: float = float(tr4.usp_low)
        upper_voltage_bound: float = float(tr4.usp_up)
        voltage_bounds_are_valid: bool = bool(
            lower_voltage_bound > 0.0
            and upper_voltage_bound > 0.0
            and lower_voltage_bound <= upper_voltage_bound
        )
        if voltage_bounds_are_valid:
            control_winding.vset_min = lower_voltage_bound
            control_winding.vset_max = upper_voltage_bound
        else:
            pass
    else:
        if automatic_control_requested:
            logger.add_warning(
                msg="Unsupported ElmTr4 automatic tap control side",
                device=trafo4w.name,
                device_class="Transformer4W",
                value=(
                    f"ictrlside={tr4.ictrlside}, t4ldc={tr4.t4ldc}, "
                    f"cpCtrlNode={tr4.cpCtrlNode}"
                ),
            )
        else:
            pass


    return trafo4w

    trafoNw.fill_from_design_values(
        V1=float(template.utrn3_h),
        V2=float(template.utrn3_m),
        V3=float(template.utrn3_l),
        Sn1=float(template.strn3_h),
        Sn2=float(template.strn3_m),
        Sn3=float(template.strn3_l),
        Pcu12=float(template.pcut3_h),
        Pcu23=float(template.pcut3_m),
        Pcu31=float(template.pcut3_l),
        Vsc12=float(template.uktr3_h),
        Vsc23=float(template.uktr3_m),
        Vsc31=float(template.uktr3_l),
        Pfe=float(template.pfe),
        I0=float(template.curm3),
        Sbase=float(baseMVA),
    )

    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding1,
        current_position=int(tr3.n3tap_h),
        neutral_position=int(template.n3tp0_h),
        minimum_position=int(template.n3tmn_h),
        maximum_position=int(template.n3tmx_h),
        step_percent=float(template.du3tp_h),
        phase_angle_deg=float(template.ph3tr_h),
        vector_group_number=float(template.nt3ag_h),
        tap_model_at_star_point=int(template.itapos) == 0,
    )
    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding2,
        current_position=int(tr3.n3tap_m),
        neutral_position=int(template.n3tp0_m),
        minimum_position=int(template.n3tmn_m),
        maximum_position=int(template.n3tmx_m),
        step_percent=float(template.du3tp_m),
        phase_angle_deg=float(template.ph3tr_m),
        vector_group_number=float(template.nt3ag_m),
        tap_model_at_star_point=int(template.itapos) == 0,
    )
    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding3,
        current_position=int(tr3.n3tap_l),
        neutral_position=int(template.n3tp0_l),
        minimum_position=int(template.n3tmn_l),
        maximum_position=int(template.n3tmx_l),
        step_percent=float(template.du3tp_l),
        phase_angle_deg=float(template.ph3tr_l),
        vector_group_number=float(template.nt3ag_l),
        tap_model_at_star_point=int(template.itapos) == 0,
    )

    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding1,
        pf_connection_code=str(template.tr3cn_h),
        pf_vector_group_angle=float(template.nt3ag_h)
    )
    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding2,
        pf_connection_code=str(template.tr3cn_m),
        pf_vector_group_angle=float(template.nt3ag_m)
    )
    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding3,
        pf_connection_code=str(template.tr3cn_l),
        pf_vector_group_angle=float(template.nt3ag_l)
    )

    hv_closed, mv_closed, lv_closed = _get_tr3_winding_closed_states(
        tr3_id=tr3.ID,
        cubics_by_objid=cubics_by_objid,
        switch_by_cubic_id=switch_by_cubic_id,
        bus_by_term_id=bus_by_term_id,
        bus_hv=bus_hv,
        bus_mv=bus_mv,
        bus_lv=bus_lv,
    )
    trafo3w.winding1.active = hv_closed
    trafo3w.winding2.active = mv_closed
    trafo3w.winding3.active = lv_closed

    return trafo3w


def build_switch_by_cubic_id(staswitchs: List[StaSwitch]) -> Dict[str, StaSwitch]:
    """
    Build switch by cubic id.

    :param staswitchs: staswitchs parameter.
    :return: Function result.
    """
    d: Dict[str, StaSwitch] = dict()
    for sw in staswitchs:
        cubic_id: str | None = _ref_id(sw.fold_id)
        if cubic_id is None or cubic_id == "":
            continue
        d[cubic_id] = sw
    return d


def convert_dgs_to_switches_from_elmcoup(elmcoups: List[ElmCoup],
                                         cubics_by_objid: Dict[str, List[StaCubic]],
                                         bus_by_term_id: Dict[str, dev.Bus],
                                         switch_by_cubic_id: Dict[str, StaSwitch],
                                         typ_switch_by_id: Dict[str, TypSwitch],
                                         sbase_mva: float,
                                         logger: Logger) -> List[dev.Switch]:
    """
    Convert dgs to switches from elmcoup.

    :param elmcoups: elmcoups parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param typ_switch_by_id: typ_switch_by_id parameter.
    :param sbase_mva: sbase_mva parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    switches: List[dev.Switch] = list()

    for coup in elmcoups:
        coup_id: str | None = _ref_id(coup.ID)
        if coup_id is None or coup_id == "":
            continue

        # Resolve connectivity
        term_ids_raw: List[str] = get_terminal_ids(element_id=coup_id, cubics_by_objid=cubics_by_objid)

        # Deduplicate terminals while preserving order
        term_ids: List[str] = list()
        for tid in term_ids_raw:
            if tid not in term_ids:
                term_ids.append(tid)

        if len(term_ids) != 2:
            logger.add_warning(
                f"Not exactly 2 terminals.",
                device=coup.ID,
                device_class="ElmCoup",
                value=str(len(term_ids)),
                expected_value="2"
            )
            continue

        bus_from: dev.Bus = bus_by_term_id[term_ids[0]]
        bus_to: dev.Bus = bus_by_term_id[term_ids[1]]

        # Skip degenerate cases
        if bus_from is bus_to:
            logger.add_warning(
                f"Both ends connect to the same bus.",
                device=coup.ID,
                device_class="ElmCoup"
            )
            continue

        # ElmCoup.on_off is the authoritative electrical state
        is_closed: bool = (int(coup.on_off) != 0)

        # Validation using StaSwitch on each cubicle
        # (StaSwitch.on_off may represent a cubicle-end representation, not the physical device state)
        cubics: List[StaCubic] = cubics_by_objid.get(coup_id, list())
        for cb in cubics:
            cb_id: str | None = _ref_id(cb.ID)
            if cb_id is None or cb_id == "":
                continue

            stasw: StaSwitch | None = switch_by_cubic_id.get(cb_id, None)
            if stasw is None:
                continue

            stasw_closed: bool = (int(stasw.on_off) != 0)
            if stasw_closed != is_closed:
                logger.add_warning(
                    f"state differs from StaSwitch. Using ElmCoup.on_off as truth.",
                    device=coup.ID,
                    device_class="ElmCoup",
                    value=int(coup.on_off),
                    expected_value=int(stasw.on_off)
                )

        graphic_type: SwitchGraphicType = _convert_pf_switch_graphic_type(iuse=0, ausage=coup.aUsage)
        typ_switch = _resolve_pointer_dict_value(key=coup.typ_id, mapping=typ_switch_by_id)
        rated_current = 0.0
        switch_r = 1e-20
        switch_x = 1e-20

        if typ_switch is not None:
            rated_current = max(float(typ_switch.InomA), float(typ_switch.InomB))
            bus_vnom = max(float(bus_from.Vnom), float(bus_to.Vnom))
            switch_r, switch_x = _get_switch_impedance_in_pu(
                r_ohm=float(typ_switch.Ron),
                x_ohm=float(typ_switch.Xon),
                vnom_kv=bus_vnom,
                sbase_mva=sbase_mva
            )
        else:
            pass

        sw = dev.Switch(
            bus_from=bus_from,
            bus_to=bus_to,
            name=coup.loc_name or f"ElmCoup_{coup_id}",
            idtag=coup_id,
            code=coup.typ_id,
            r=switch_r,
            x=switch_x,
            active=is_closed,
            normal_open=not is_closed,
            retained=False,
            rated_current=rated_current,
            graphic_type=graphic_type
        )

        switches.append(sw)

    return switches


def _convert_pf_switch_graphic_type(iuse: int, ausage: str) -> SwitchGraphicType:
    """
    Convert pf switch graphic type.

    :param iuse: iuse parameter.
    :param ausage: ausage parameter.
    :return: Function result.
    """
    usage = str(ausage).strip().upper()

    usage_to_member: Dict[str, str] = {
        "CB": "CircuitBreaker",
        "BREAKER": "CircuitBreaker",
        "CBK": "CircuitBreaker",
        "DIS": "Disconnector",
        "DISCONNECTOR": "Disconnector",
        "LBS": "LoadBreakSwitch",
        "LOADBREAKSWITCH": "LoadBreakSwitch",
        "FUSE": "Fuse",
    }

    member_name = usage_to_member.get(usage, None)
    if member_name is not None and member_name in SwitchGraphicType.__members__:
        return SwitchGraphicType.__members__[member_name]

    iuse_to_member: Dict[int, str] = {
        0: "CircuitBreaker",
        1: "Disconnector",
        2: "LoadBreakSwitch",
        3: "Fuse",
    }

    member_name = iuse_to_member.get(int(iuse), "CircuitBreaker")
    if member_name in SwitchGraphicType.__members__:
        return SwitchGraphicType.__members__[member_name]

    return SwitchGraphicType.CircuitBreaker


def convert_dgs_to_switch(stasw: StaSwitch,
                          buses: List[dev.Bus],
                          stacubic_dict: Dict[str, List[int]],
                          logger: Logger,
                          cubics_by_objid: Dict[str, List[StaCubic]],
                          bus_by_term_id: Dict[str, dev.Bus]) -> dev.Switch | None:
    """
    Convert dgs to switch.

    :param stasw: stasw parameter.
    :param buses: buses parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    term_ids: List[str] = get_terminal_ids(element_id=stasw.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) != 2:
        logger.add_warning(
            f"not connected to exactly 2 terminals.",
            device=f"'{stasw.loc_name}' (ID={stasw.ID})",
            device_class="StaSwitch",
        )
        return None

    bus_from = bus_by_term_id[term_ids[0]]
    bus_to = bus_by_term_id[term_ids[1]]

    # PowerFactory/DGS state: on_off (int)
    # We interpret on_off != 0 as "closed/connected" (active switch).
    is_closed: bool = (int(stasw.on_off) != 0)
    normal_open: bool = not is_closed

    graphic_type: SwitchGraphicType = _convert_pf_switch_graphic_type(iuse=stasw.iUse,
                                                                      ausage=stasw.aUsage)

    sw = dev.Switch(bus_from=bus_from,
                    bus_to=bus_to,
                    name=stasw.loc_name,
                    idtag=stasw.ID,
                    code=stasw.typ_id,
                    active=is_closed,
                    normal_open=normal_open,
                    retained=False,
                    rated_current=0.0,
                    graphic_type=graphic_type)

    return sw


def _apply_effective_calculated_line_parameters(
        line: dev.Line,
        source: ElmLne,
        base_mva: float,
        parallel_count: int,
        logger: Logger,
) -> bool:
    """
    Apply DGS-exported total line constants to the electrical branch model.

    PowerFactory exposes these values as structural ``c:R1``/``c:X1`` and
    sequence companions. They are independent of the solved terminal P/Q
    snapshot and represent the complete element after PowerFactory has reduced
    its TypLne, TypGeo, TypTow and ElmLnesec structural data.  The source
    template remains attached to the line for catalogue and GUI use.

    :param line: Converted VeraGrid line receiving per-unit parameters.
    :param source: Source DGS line with optional effective constants.
    :param base_mva: VeraGrid system power base in MVA.
    :param parallel_count: Number of explicit parallel branches materialized.
    :param logger: Conversion diagnostics.
    :return: ``True`` when positive-sequence parameters were applied.
    """
    has_positive_sequence: bool = bool(
        source.calculated_R1 is not None
        and source.calculated_X1 is not None
        and source.calculated_B1 is not None
    )
    if has_positive_sequence:
        calculated_r1: float = float(source.calculated_R1)
        calculated_x1: float = float(source.calculated_X1)
        calculated_b1: float = float(source.calculated_B1)
        if source.calculated_G1 is not None:
            calculated_g1: float = float(source.calculated_G1)
        else:
            calculated_g1 = 0.0
        positive_values_are_finite: bool = bool(
            math.isfinite(calculated_r1)
            and math.isfinite(calculated_x1)
            and math.isfinite(calculated_b1)
            and math.isfinite(calculated_g1)
        )
    else:
        calculated_r1 = 0.0
        calculated_x1 = 0.0
        calculated_b1 = 0.0
        calculated_g1 = 0.0
        positive_values_are_finite = False

    # BranchParent.get_virtual_taps() expresses every passive-branch primitive
    # on the ``bus_from`` voltage base.  Using the larger endpoint voltage here
    # would apply that base conversion twice whenever a PF line joins terminals
    # with different nominal voltages (for example, a 220/225 kV corridor).
    line_voltage_kv: float = float(line.bus_from.Vnom)
    values_are_usable: bool = bool(
        positive_values_are_finite
        and line_voltage_kv > 0.0
        and base_mva > 0.0
        and (abs(calculated_r1) > 0.0 or abs(calculated_x1) > 0.0)
    )
    if values_are_usable:
        impedance_base_ohm: float = line_voltage_kv * line_voltage_kv / base_mva
        explicit_parallel_count: int = max(1, int(parallel_count))

        # PowerFactory's calculated series constants represent the equivalent
        # complete ElmLne. VeraGrid materializes ``nlnum`` physical branches,
        # so each branch receives N times the equivalent series impedance and
        # one N-th of the equivalent shunt susceptance.
        line.R = (
            calculated_r1
            * float(explicit_parallel_count)
            / impedance_base_ohm
        )
        line.X = (
            calculated_x1
            * float(explicit_parallel_count)
            / impedance_base_ohm
        )
        line.B = (
            calculated_b1
            * 1.0e-6
            * impedance_base_ohm
            / float(explicit_parallel_count)
        )
        line.G = (
            calculated_g1
            * 1.0e-6
            * impedance_base_ohm
            / float(explicit_parallel_count)
        )
        line.R2 = line.R
        line.X2 = line.X
        line.B2 = line.B
        line.G2 = line.G

        has_zero_sequence: bool = bool(
            source.calculated_R0 is not None
            and source.calculated_X0 is not None
            and source.calculated_B0 is not None
        )
        if has_zero_sequence:
            calculated_r0: float = float(source.calculated_R0)
            calculated_x0: float = float(source.calculated_X0)
            calculated_b0: float = float(source.calculated_B0)
            if source.calculated_G0 is not None:
                calculated_g0: float = float(source.calculated_G0)
            else:
                calculated_g0 = 0.0
            zero_values_are_finite: bool = bool(
                math.isfinite(calculated_r0)
                and math.isfinite(calculated_x0)
                and math.isfinite(calculated_b0)
                and math.isfinite(calculated_g0)
            )
            if zero_values_are_finite:
                line.R0 = (
                    calculated_r0
                    * float(explicit_parallel_count)
                    / impedance_base_ohm
                )
                line.X0 = (
                    calculated_x0
                    * float(explicit_parallel_count)
                    / impedance_base_ohm
                )
                line.B0 = (
                    calculated_b0
                    * 1.0e-6
                    * impedance_base_ohm
                    / float(explicit_parallel_count)
                )
                line.G0 = (
                    calculated_g0
                    * 1.0e-6
                    * impedance_base_ohm
                    / float(explicit_parallel_count)
                )
            else:
                pass
        else:
            pass
        logger.add_info(
            "Applied effective DGS line sequence parameters",
            device=line.name,
            device_class="ElmLne",
        )
        applied: bool = True
    else:
        applied = False
    return applied


def _has_usable_effective_line_parameters(source: ElmLne) -> bool:
    """Report whether one DGS line carries a finite balanced equivalent.

    PowerFactory exports ``c:R1``, ``c:X1`` and ``c:B1`` as the complete
    structural reduction of the physical line.  The values remain independent
    of solved P/Q results and therefore take precedence over a second geometry
    calculation while the geometry itself remains attached for GUI and 3-phase
    studies.

    :param source: Source DGS line to inspect.
    :return: ``True`` when the complete positive-sequence contract is usable.
    """
    complete_contract: bool = bool(
        source.calculated_R1 is not None
        and source.calculated_X1 is not None
        and source.calculated_B1 is not None
    )
    if complete_contract:
        resistance_ohm: float = float(source.calculated_R1)
        reactance_ohm: float = float(source.calculated_X1)
        susceptance_us: float = float(source.calculated_B1)
        conductance_is_finite: bool
        if source.calculated_G1 is None:
            conductance_is_finite = True
        else:
            conductance_is_finite = math.isfinite(float(source.calculated_G1))
        result: bool = bool(
            math.isfinite(resistance_ohm)
            and math.isfinite(reactance_ohm)
            and math.isfinite(susceptance_us)
            and conductance_is_finite
            and (abs(resistance_ohm) > 0.0 or abs(reactance_ohm) > 0.0)
        )
    else:
        result = False
    return result


def _apply_effective_calculated_line_conductance(
        line: dev.Line,
        source: ElmLne,
        base_mva: float,
        parallel_count: int,
) -> bool:
    """Apply the complete-element conductance exported for one line.

    Unlike calculated R/X/B, PowerFactory's resulting ``G1`` and ``G0`` are
    unambiguous total shunt conductances even when TypGeo supplies the series
    and capacitive geometry. Applying them after template reconstruction
    preserves that geometry while retaining dielectric losses.

    :param line: Converted VeraGrid line receiving the conductance.
    :param source: Source DGS line with optional effective conductances.
    :param base_mva: VeraGrid system power base in MVA.
    :param parallel_count: Number of explicit parallel branches materialized.
    :return: ``True`` when a finite positive-sequence conductance was applied.
    """
    has_positive_conductance: bool = source.calculated_G1 is not None
    # Keep the shunt primitive on the same from-side base as the series values
    # and the virtual-tap transformation used by the numerical compiler.
    line_voltage_kv: float = float(line.bus_from.Vnom)
    if has_positive_conductance:
        calculated_g1_us: float = float(source.calculated_G1)
        positive_is_usable: bool = bool(
            math.isfinite(calculated_g1_us)
            and line_voltage_kv > 0.0
            and base_mva > 0.0
        )
    else:
        calculated_g1_us = 0.0
        positive_is_usable = False

    if positive_is_usable:
        impedance_base_ohm: float = (
            line_voltage_kv * line_voltage_kv / base_mva
        )
        explicit_parallel_count: int = max(1, int(parallel_count))
        line.G = (
            calculated_g1_us
            * 1.0e-6
            * impedance_base_ohm
            / float(explicit_parallel_count)
        )
        line.G2 = line.G
        if source.calculated_G0 is not None:
            calculated_g0_us: float = float(source.calculated_G0)
            zero_is_usable: bool = math.isfinite(calculated_g0_us)
        else:
            calculated_g0_us = 0.0
            zero_is_usable = False
        if zero_is_usable:
            line.G0 = (
                calculated_g0_us
                * 1.0e-6
                * impedance_base_ohm
                / float(explicit_parallel_count)
            )
        else:
            pass
    else:
        pass
    return positive_is_usable


def _get_distributed_line_pi_sequence(
        series_impedance_pu: complex,
        total_shunt_admittance_pu: complex,
) -> tuple[complex, complex] | None:
    """Convert physical distributed constants to their exact pi equivalent.

    PowerFactory's exported ``c:R/X/G/B`` values are the physical totals
    ``Z' l`` and ``Y' l``.  For ``ElmLne.i_dist=1``, its load-flow primitive is
    instead the hyperbolic equivalent from the transmission-line equations.
    ``Line.G/B`` store the total shunt admittance, while the compiler places
    half at each terminal.

    :param series_impedance_pu: Physical total ``Z' l`` in p.u.
    :param total_shunt_admittance_pu: Physical total ``Y' l`` in p.u.
    :return: Exact series and total-shunt pi values, or ``None`` if invalid.
    """
    values_are_finite: bool = bool(
        math.isfinite(series_impedance_pu.real)
        and math.isfinite(series_impedance_pu.imag)
        and math.isfinite(total_shunt_admittance_pu.real)
        and math.isfinite(total_shunt_admittance_pu.imag)
    )
    if not values_are_finite:
        return None
    else:
        pass

    propagation_product: complex = (
        series_impedance_pu * total_shunt_admittance_pu
    )
    propagation_argument: complex = cmath.sqrt(propagation_product)
    if abs(propagation_argument) <= 1.0e-12:
        equivalent_series_impedance: complex = series_impedance_pu
        equivalent_total_shunt_admittance: complex = total_shunt_admittance_pu
    else:
        equivalent_series_impedance = (
            series_impedance_pu
            * cmath.sinh(propagation_argument)
            / propagation_argument
        )
        half_argument: complex = 0.5 * propagation_argument
        equivalent_total_shunt_admittance = (
            total_shunt_admittance_pu
            * cmath.tanh(half_argument)
            / half_argument
        )

    result_is_finite: bool = bool(
        math.isfinite(equivalent_series_impedance.real)
        and math.isfinite(equivalent_series_impedance.imag)
        and math.isfinite(equivalent_total_shunt_admittance.real)
        and math.isfinite(equivalent_total_shunt_admittance.imag)
    )
    if result_is_finite:
        return equivalent_series_impedance, equivalent_total_shunt_admittance
    else:
        return None


def _apply_distributed_line_pi_equivalent(
        line: dev.Line,
        source: ElmLne,
        logger: Logger,
) -> bool:
    """Apply PowerFactory's distributed line model only when explicitly set.

    :param line: Converted VeraGrid physical line with physical total R/X/G/B.
    :param source: Source ElmLne carrying the native ``i_dist`` selector.
    :param logger: Conversion diagnostics.
    :return: ``True`` when the distributed positive-sequence model was applied.
    """
    model_is_applicable: bool = bool(
        int(source.i_dist) == 1
        and not line.bus_from.is_dc
        and not line.bus_to.is_dc
    )
    if not model_is_applicable:
        return False
    else:
        pass

    positive_equivalent: tuple[complex, complex] | None = (
        _get_distributed_line_pi_sequence(
            series_impedance_pu=complex(line.R, line.X),
            total_shunt_admittance_pu=complex(line.G, line.B),
        )
    )
    if positive_equivalent is None:
        logger.add_warning(
            msg="Invalid distributed ElmLne positive-sequence parameters",
            device=line.name,
            device_class="ElmLne",
        )
        return False
    else:
        pass

    positive_series, positive_shunt = positive_equivalent
    line.R = float(positive_series.real)
    line.X = float(positive_series.imag)
    line.G = float(positive_shunt.real)
    line.B = float(positive_shunt.imag)
    line.R2 = line.R
    line.X2 = line.X
    line.G2 = line.G
    line.B2 = line.B

    zero_equivalent: tuple[complex, complex] | None = (
        _get_distributed_line_pi_sequence(
            series_impedance_pu=complex(line.R0, line.X0),
            total_shunt_admittance_pu=complex(line.G0, line.B0),
        )
    )
    if zero_equivalent is not None:
        zero_series, zero_shunt = zero_equivalent
        line.R0 = float(zero_series.real)
        line.X0 = float(zero_series.imag)
        line.G0 = float(zero_shunt.real)
        line.B0 = float(zero_shunt.imag)
    else:
        pass

    logger.add_info(
        "Applied distributed DGS line pi equivalent",
        device=line.name,
        device_class="ElmLne",
    )
    return True


def _get_calculated_line_section_values(
        section: ElmLnesec,
        line_voltage_kv: float,
        base_mva: float,
        parallel_count: int,
) -> Tuple[float, float, float, float, float, float] | None:
    """
    Convert an explicit DGS line-section equivalent to per-unit values.

    PowerFactory permits a mixed ``ElmLne`` whose sections do not all point to
    an electrical type.  The calculated section constants are the structural
    equivalent of that untyped geometry and are independent of load-flow P/Q.

    :param section: DGS line section carrying optional calculated constants.
    :param line_voltage_kv: Nominal line voltage in kV.
    :param base_mva: VeraGrid system power base in MVA.
    :param parallel_count: Number of explicit parallel branches materialized.
    :return: Positive- and zero-sequence R/X/B values, or ``None``.
    """
    has_positive_sequence: bool = bool(
        section.calculated_R1 is not None
        and section.calculated_X1 is not None
        and section.calculated_B1 is not None
    )
    if has_positive_sequence and line_voltage_kv > 0.0 and base_mva > 0.0:
        calculated_r1: float = float(section.calculated_R1)
        calculated_x1: float = float(section.calculated_X1)
        calculated_b1: float = float(section.calculated_B1)
        positive_values_are_finite: bool = bool(
            math.isfinite(calculated_r1)
            and math.isfinite(calculated_x1)
            and math.isfinite(calculated_b1)
        )
    else:
        calculated_r1 = 0.0
        calculated_x1 = 0.0
        calculated_b1 = 0.0
        positive_values_are_finite = False

    if positive_values_are_finite:
        impedance_base_ohm: float = line_voltage_kv * line_voltage_kv / base_mva
        explicit_parallel_count: int = max(1, int(parallel_count))
        section_r: float = calculated_r1 * float(explicit_parallel_count) / impedance_base_ohm
        section_x: float = calculated_x1 * float(explicit_parallel_count) / impedance_base_ohm
        section_b: float = (
            calculated_b1 * 1.0e-6 * impedance_base_ohm
            / float(explicit_parallel_count)
        )

        has_zero_sequence: bool = bool(
            section.calculated_R0 is not None
            and section.calculated_X0 is not None
        )
        if has_zero_sequence:
            calculated_r0: float = float(section.calculated_R0)
            calculated_x0: float = float(section.calculated_X0)
            zero_values_are_finite: bool = bool(
                math.isfinite(calculated_r0) and math.isfinite(calculated_x0)
            )
            if zero_values_are_finite:
                section_r0: float = (
                    calculated_r0 * float(explicit_parallel_count) / impedance_base_ohm
                )
                section_x0: float = (
                    calculated_x0 * float(explicit_parallel_count) / impedance_base_ohm
                )
            else:
                section_r0 = 0.0
                section_x0 = 0.0
        else:
            section_r0 = 0.0
            section_x0 = 0.0
        # ElmLnesec does not expose c:B0 in the native PF schema.  Keeping it
        # zero is explicit; the parent line's exported total remains available
        # as an independent audit of the resulting section sum.
        section_b0: float = 0.0
        result: Tuple[float, float, float, float, float, float] | None = (
            section_r, section_x, section_b, section_r0, section_x0, section_b0,
        )
    else:
        result = None
    return result


def _preserve_line_section_template_associations(
        line: dev.Line,
        sections: List[ElmLnesec],
        sequence_templates_dict: Dict[str, dev.SequenceLineType],
        overhead_line_type_dict: Dict[str, dev.OverheadLineType],
) -> None:
    """Preserve every physical template used by a sectioned DGS line.

    ``ElmLnesec`` objects are consecutive parts of one physical ``ElmLne``.
    VeraGrid deliberately keeps that equipment as one :class:`Line`, because
    splitting it would invent intermediate buses and would break switching,
    contingencies and dynamic ownership.  The length-weighted associations
    retain all source geometries for catalogue, GUI and later 3-phase use.  A
    direct ``line.template`` is safe only when one template covers the complete
    line; mixed lines retain their complete association set instead.

    :param line: Destination VeraGrid physical line.
    :param sections: Ordered or unordered source line sections.
    :param sequence_templates_dict: Sequence templates indexed by DGS identity.
    :param overhead_line_type_dict: Geometrical templates indexed by DGS identity.
    :return: None.
    """
    sequence_length_by_id: Dict[str, float] = dict()
    sequence_template_by_id: Dict[str, dev.SequenceLineType] = dict()
    overhead_length_by_id: Dict[str, float] = dict()
    overhead_template_by_id: Dict[str, dev.OverheadLineType] = dict()
    total_length: float = 0.0
    typed_length: float = 0.0

    # Accumulate the physical coverage of each exported template.  Length is
    # the correct weight because PF applies every section type per kilometre.
    section: ElmLnesec
    for section in sections:
        section_length: float = max(0.0, float(section.dline))
        total_length += section_length
        sequence_template: dev.SequenceLineType | None = (
            _resolve_pointer_dict_value(
                key=section.typ_id,
                mapping=sequence_templates_dict,
            )
        )
        overhead_template: dev.OverheadLineType | None = (
            _resolve_pointer_dict_value(
                key=section.typ_id,
                mapping=overhead_line_type_dict,
            )
        )
        if sequence_template is not None:
            template_id: str = str(sequence_template.idtag)
            previous_length: float | None = sequence_length_by_id.get(
                template_id,
                None,
            )
            if previous_length is None:
                sequence_length_by_id[template_id] = section_length
                sequence_template_by_id[template_id] = sequence_template
            else:
                sequence_length_by_id[template_id] = (
                    previous_length + section_length
                )
            typed_length += section_length
        else:
            if overhead_template is not None:
                template_id = str(overhead_template.idtag)
                previous_length = overhead_length_by_id.get(template_id, None)
                if previous_length is None:
                    overhead_length_by_id[template_id] = section_length
                    overhead_template_by_id[template_id] = overhead_template
                else:
                    overhead_length_by_id[template_id] = (
                        previous_length + section_length
                    )
                typed_length += section_length
            else:
                pass
    else:
        pass

    # Store normalized physical coverage so serialization and GUI inspection
    # retain the original section composition without creating fake devices.
    denominator: float = total_length if total_length > 0.0 else 1.0
    template_id: str
    for template_id in sequence_length_by_id:
        line.possible_sequence_line_types.add_object(
            api_object=sequence_template_by_id[template_id],
            val=sequence_length_by_id[template_id] / denominator,
        )
    else:
        pass
    for template_id in overhead_length_by_id:
        line.possible_tower_types.add_object(
            api_object=overhead_template_by_id[template_id],
            val=overhead_length_by_id[template_id] / denominator,
        )
    else:
        pass

    unique_template_count: int = (
        len(sequence_template_by_id) + len(overhead_template_by_id)
    )
    coverage_is_complete: bool = bool(
        total_length > 0.0
        and abs(typed_length - total_length) <= max(1.0e-12, total_length * 1.0e-12)
    )
    if unique_template_count == 1 and coverage_is_complete:
        if len(sequence_template_by_id) == 1:
            primary_template: dev.SequenceLineType | dev.OverheadLineType = next(
                iter(sequence_template_by_id.values())
            )
        else:
            primary_template = next(iter(overhead_template_by_id.values()))
        # The section equivalent has already been calculated explicitly below.
        # Attach identity only; reapplying the template here would double the
        # full line length and would discard exported section constants.
        line.template = primary_template
        line.rms_template = primary_template.rms_template
        line.emt_template = primary_template.emt_template
    else:
        pass


def convert_dgs_to_line(
        lne: ElmLne,
        buses: List[dev.Bus],
        stacubic_dict: Dict[str, List[int]],
        sequence_templates_dict: Dict[str, dev.SequenceLineType],
        overhead_line_type_dict: Dict[str, dev.OverheadLineType],
        line_type_by_line_id: Dict[str, str],
        line_sections_by_line_id: Dict[str, List[ElmLnesec]],
        tower_template_by_line_id: Dict[
            str,
            dev.OverheadLineType | dev.SequenceLineType,
        ],
        freq: float,
        baseMVA: float,
        logger: Logger,
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        parallel_index: int = 0,
        parallel_count: int = 1,
        switch_by_cubic_id: Dict[str, StaSwitch] | None = None,
        active_terminal_edges: Tuple[Tuple[str, str], ...] | None = None,
        source_terminal_ids: Tuple[str, ...] | None = None,
) -> dev.Line:
    """
    Convert dgs to line.

    :param lne: lne parameter.
    :param buses: buses parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param sequence_templates_dict: sequence_templates_dict parameter.
    :param overhead_line_type_dict: overhead_line_type_dict parameter.
    :param line_type_by_line_id: line_type_by_line_id parameter.
    :param line_sections_by_line_id: line_sections_by_line_id parameter.
    :param tower_template_by_line_id: tower_template_by_line_id parameter.
    :param freq: freq parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :param active_terminal_edges: Active DGS topology connections.
    :param source_terminal_ids: Terminals of active DGS source devices.
    :return: Function result.
    """

    # ------------------------------------------------------------
    # Connectivity via StaCubic.fold_id -> ElmTerm.ID (preferred)
    # ------------------------------------------------------------
    term_ids = get_terminal_ids(element_id=lne.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) != 2:
        ref = _ref_id(lne.ID)
        if ref is not None:
            bus_ids = stacubic_dict.get(ref, None)
            if bus_ids is None:
                raise ValueError(f"No buses for the line {lne.ID}")
            if len(bus_ids) != 2:
                raise ValueError(f"Not exactly 2 buses for the line {lne.ID}")
        else:
            pass

    bus_from, bus_to = get_branch_buses(
        elm_id=lne.ID,
        stacubic_dict=stacubic_dict,
        buses=buses,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id
    )

    line_name = _get_non_empty_name(lne.loc_name, f"Line_{_ref_id(lne.ID)}")
    line_name = _get_parallel_device_name(line_name, parallel_index, parallel_count)
    line_idtag = _get_parallel_device_idtag(_ref_id(lne.ID), parallel_index, parallel_count)

    effective_switch_by_cubic_id: Dict[str, StaSwitch]
    if switch_by_cubic_id is None:
        effective_switch_by_cubic_id = dict()
    else:
        effective_switch_by_cubic_id = switch_by_cubic_id
    terminal_from_closed: bool
    terminal_to_closed: bool
    terminal_from_closed, terminal_to_closed = _get_two_terminal_energized_states(
        element_id=lne.ID,
        cubics_by_objid=cubics_by_objid,
        switch_by_cubic_id=effective_switch_by_cubic_id,
        bus_by_term_id=bus_by_term_id,
    )
    line_is_active: bool = bool(
        int(lne.outserv) == 0 and terminal_from_closed and terminal_to_closed
    )
    # Preserve the DGS service and switching state on the imported branch.
    # Source reachability classifies participation in a particular solve; it
    # must not rewrite the persistent topology. This also lets a source added
    # after import energize the existing represented network.

    line = dev.Line(
        bus_from=bus_from,
        bus_to=bus_to,
        name=line_name,
        idtag=line_idtag,
        active=line_is_active,
        length=lne.dline
    )

    line_key = _ref_id(lne.ID)
    if line_key is None or line_key == "":
        line_key = str(lne.ID)
    else:
        pass
    owned_sections = line_sections_by_line_id.get(line_key, list())
    if len(owned_sections) > 0:
        sections_length = 0.0
        for section in owned_sections:
            sections_length += float(section.dline)
        if sections_length > 0.0:
            line.length = sections_length
        else:
            pass
    else:
        pass

    # ------------------------------------------------------------
    # Apply the resolved template
    # ------------------------------------------------------------

    # ------------------------------------------------------------
    # Resolve typ_id (some PF exports store the type in ElmLnesec instead of ElmLne).
    # If the line is part of an ElmTow (tower coupling), it may legitimately have no typ_id.
    # In that case, we defer the template to the tower mapping.
    # ------------------------------------------------------------
    typ_id: str | None = lne.typ_id
    if typ_id is None or typ_id == "":
        # Try raw line ID and normalized pointer ID
        typ_id = line_type_by_line_id.get(lne.ID, None)
        if typ_id is None or typ_id == "":
            lid = _ref_id(lne.ID)
            if lid is not None and lid != "":
                typ_id = line_type_by_line_id.get(lid, None)

    # Tower-derived template (ElmTow -> TypTow). This is used only when typ_id is missing.
    tower_template: dev.OverheadLineType | dev.SequenceLineType | None = None
    if typ_id is None or typ_id == "":
        tower_template = tower_template_by_line_id.get(lne.ID, None)
        if tower_template is None:
            lid = _ref_id(lne.ID)
            if lid is not None and lid != "":
                tower_template = tower_template_by_line_id.get(lid, None)

    # ------------------------------------------------------------
    # Resolve the line template (TypLne or TypTow)
    # ------------------------------------------------------------
    seq_template: dev.SequenceLineType | None = None
    ohl_template: dev.OverheadLineType | None = None

    if typ_id is not None and typ_id != "":
        seq_template = sequence_templates_dict.get(typ_id, None)
        if seq_template is None:
            tid = _ref_id(typ_id)
            if tid is not None and tid != "":
                seq_template = sequence_templates_dict.get(tid, None)

        if seq_template is None:
            ohl_template = overhead_line_type_dict.get(typ_id, None)
            if ohl_template is None:
                tid = _ref_id(typ_id)
                if tid is not None and tid != "":
                    ohl_template = overhead_line_type_dict.get(tid, None)
    else:
        # Tower geometry can contain either physical geometry (i_mode=0) or
        # already calculated sequence parameters (i_mode=1). Preserve that
        # distinction so both DGS representations use their native template.
        if isinstance(tower_template, dev.SequenceLineType):
            seq_template = tower_template
        elif isinstance(tower_template, dev.OverheadLineType):
            ohl_template = tower_template
        else:
            pass

    applied_template = False
    if len(owned_sections) > 0:
        section_r = 0.0
        section_x = 0.0
        section_b = 0.0
        section_g = 0.0
        section_r0 = 0.0
        section_x0 = 0.0
        section_b0 = 0.0
        section_g0 = 0.0
        section_rate: float | None = None
        section_template_found = False
        bus_vnom = line.get_max_bus_nominal_voltage()

        ordered_sections = sorted(owned_sections, key=_line_section_index_sort_key)
        _preserve_line_section_template_associations(
            line=line,
            sections=ordered_sections,
            sequence_templates_dict=sequence_templates_dict,
            overhead_line_type_dict=overhead_line_type_dict,
        )
        for section in ordered_sections:
            seq_section_template = _resolve_pointer_dict_value(key=section.typ_id, mapping=sequence_templates_dict)
            ohl_section_template = _resolve_pointer_dict_value(key=section.typ_id, mapping=overhead_line_type_dict)

            if seq_section_template is not None:
                section_template_found = True
                values = seq_section_template.get_values(
                    Sbase=baseMVA,
                    freq=freq,
                    length=float(section.dline),
                    line_Vnom=bus_vnom,
                    decimals_rounding=16  # basically not rounding
                )
                section_r += float(values[0])
                section_x += float(values[1])
                section_b += float(values[2])
                section_r0 += float(values[3])
                section_x0 += float(values[4])
                section_b0 += float(values[5])
                current_rate = float(values[6])
                section_conductance: Tuple[float, float] = (
                    seq_section_template.get_conductance_values(
                        Sbase=baseMVA,
                        length=float(section.dline),
                        line_Vnom=bus_vnom,
                        decimals_rounding=16,
                    )
                )
                section_g += section_conductance[0]
                section_g0 += section_conductance[1]
            elif ohl_section_template is not None:
                if not ohl_section_template.is_computed():
                    ohl_section_template.compute()
                else:
                    pass
                section_template_found = True
                values = ohl_section_template.get_values(
                    Sbase=baseMVA,
                    length=float(section.dline),
                    circuit_index=1,
                    Vnom=bus_vnom
                )
                section_r += float(values[0])
                section_x += float(values[1])
                section_b += float(values[2])
                section_r0 += float(values[3])
                section_x0 += float(values[4])
                section_b0 += float(values[5])
                current_rate = float(values[6])
            else:
                calculated_values: Tuple[float, float, float, float, float, float] | None = (
                    _get_calculated_line_section_values(
                        section=section,
                        line_voltage_kv=bus_vnom,
                        base_mva=baseMVA,
                        parallel_count=parallel_count,
                    )
                )
                if calculated_values is not None:
                    # Untyped physical sections are still part of the series
                    # path.  Accumulate their exported structural equivalent.
                    section_template_found = True
                    section_r += calculated_values[0]
                    section_x += calculated_values[1]
                    section_b += calculated_values[2]
                    section_r0 += calculated_values[3]
                    section_x0 += calculated_values[4]
                    section_b0 += calculated_values[5]
                    current_rate = 0.0
                else:
                    current_rate = 0.0
                    logger.add_warning(
                        "Line section type and calculated equivalent not found.",
                        device=section.loc_name,
                        device_class="ElmLnesec",
                        value=str(section.typ_id)
                    )

            current_rate = current_rate * float(section.fline)
            if section_rate is None and current_rate > 0.0:
                section_rate = current_rate
            else:
                if section_rate is not None and current_rate > 0.0:
                    section_rate = min(section_rate, current_rate)
                else:
                    pass

        if section_template_found:
            line.R = section_r
            line.X = section_x
            line.B = section_b
            line.G = section_g
            line.R0 = section_r0
            line.X0 = section_x0
            line.B0 = section_b0
            line.G0 = section_g0
            line.G2 = section_g
            if section_rate is not None:
                line.rate = section_rate
            else:
                pass
            applied_template = True
        else:
            applied_template = False
    elif seq_template is not None:
        # DGS already serialises physical line parameters with finite decimal
        # precision.  A second six-decimal rounding after conversion to p.u.
        # creates material angle errors in high-transfer networks, so retain
        # essentially all IEEE-754 precision just as sectioned lines do.
        line.apply_template(
            obj=seq_template,
            Sbase=baseMVA,
            freq=freq,
            logger=logger,
            decimals_rounding=16,
        )
        applied_template = True
    elif ohl_template is not None:
        # OverheadLineType uses a 1-based circuit index. Default to circuit 1 here.
        line.set_circuit_idx(val=1, obj=ohl_template)
        line.apply_template(obj=ohl_template, Sbase=baseMVA, freq=freq, logger=logger)
        applied_template = True
    else:
        pass

    # ``c:R/X/B`` are calculated structural constants of the complete ElmLne,
    # not solved-flow results.  Use them as the balanced/sequence electrical
    # equivalent whenever exported, while retaining the original geometry in
    # ``line.template`` and the MultiCircuit catalogue.  This also makes mixed
    # sections and tower reductions deterministic across PF versions.
    effective_parameters_applied: bool = _apply_effective_calculated_line_parameters(
        line=line,
        source=lne,
        base_mva=baseMVA,
        parallel_count=parallel_count,
        logger=logger,
    )
    if effective_parameters_applied:
        applied_template = True
    else:
        pass

    # Resulting conductance remains structural for every representation,
    # including TypGeo lines whose geometry already supplied R/X/B.
    _apply_effective_calculated_line_conductance(
        line=line,
        source=lne,
        base_mva=baseMVA,
        parallel_count=parallel_count,
    )
    _apply_distributed_line_pi_equivalent(
        line=line,
        source=lne,
        logger=logger,
    )

    if applied_template:
        line.rate = float(line.rate) * float(lne.fline)
    else:
        pass

    # A PowerFactory TypLne can contain positive-sequence AC constants even
    # when ElmLne connects two DC terminals.  PowerFactory's DC load flow uses
    # only the conductor resistance in that topology: the exported xline and
    # bline values describe frequency-domain cable behaviour and must not enter
    # the steady-state DC nodal admittance.  Decide from the connected buses so
    # the rule remains valid when a shared or incomplete type export omits its
    # own system marker.
    if bus_from.is_dc and bus_to.is_dc:
        # TypLne stores X=omega*L and B=omega*C. Preserve the equivalent
        # energy constants before removing X/B from the DC load-flow model.
        # This conversion is entirely DGS-derived and remains valid for every
        # cable type and system frequency exported by PowerFactory.
        angular_frequency: float = 2.0 * np.pi * float(freq)
        if angular_frequency > 0.0:
            line.dc_series_inductance_pu_seconds = float(line.X) / angular_frequency
            line.dc_shunt_capacitance_pu_seconds = float(line.B) / angular_frequency
        else:
            line.dc_series_inductance_pu_seconds = 0.0
            line.dc_shunt_capacitance_pu_seconds = 0.0
        line.X = 0.0
        line.B = 0.0
        line.X0 = 0.0
        line.B0 = 0.0
        line.X2 = 0.0
        line.B2 = 0.0
    else:
        # PowerFactory projects commonly encode a bus-section jumper as a
        # minimum positive line length because ``ElmLne.dline`` cannot be
        # zero.  Solving those sub-micro-p.u. branches explicitly produces an
        # ill-conditioned Jacobian, while PowerFactory contracts them in its
        # topology stage.  Preserve ordinary short cables: all three physical
        # signatures (one metre or less, negligible series impedance and
        # negligible shunt) must identify the connector.
        connector_has_minimum_length: bool = bool(
            0.0 < float(line.length) <= 1.0e-3
        )
        connector_has_negligible_series: bool = bool(
            abs(complex(float(line.R), float(line.X))) <= 1.0e-6
        )
        connector_has_negligible_shunt: bool = bool(
            abs(float(line.B)) <= 1.0e-4
        )
        if (
                connector_has_minimum_length
                and connector_has_negligible_series
                and connector_has_negligible_shunt
        ):
            line.reducible = True
            logger.add_info(
                msg="Imported negligible DGS line as topology connector",
                device=line.name,
                device_class="ElmLne",
                value=(
                    f"length={float(line.length):.12g} km; "
                    f"Z={abs(complex(float(line.R), float(line.X))):.12g} p.u.; "
                    f"B={float(line.B):.12g} p.u."
                ),
            )
        else:
            pass

    return line


def convert_dgs_common_impedance_to_series_reactance(
        element: ElmZpu,
        buses: List[dev.Bus],
        bus_by_terminal_id: Dict[str, dev.Bus],
        stacubic_dict: Dict[str, List[int]],
        cubics_by_obj_id: Dict[str, List[StaCubic]],
        logger: Logger,
        Sbase_vg: float,
        switch_by_cubic_id: Dict[str, StaSwitch] | None = None,
) -> dev.SeriesReactance:
    """
    Convert dgs common impedance to series reactance.

    :param element: element parameter.
    :param buses: buses parameter.
    :param bus_by_terminal_id: bus_by_terminal_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_obj_id: cubics_by_obj_id parameter.
    :param logger: logger parameter.
    :param Sbase_vg: Sbase_vg parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :return: Function result.
    """

    # Resolve buses via StaCubic.fold_id -> ElmTerm.ID -> Bus (same approach as lines/transformers)
    term_ids: List[str] = get_terminal_ids(element_id=element.ID, cubics_by_objid=cubics_by_obj_id)
    if len(term_ids) != 2:
        raise ValueError(
            f"ElmZpu '{element.loc_name}' (ID={element.ID}) is not connected to exactly 2 terminals.")

    bus_from, bus_to = get_branch_buses(
        elm_id=element.ID,
        stacubic_dict=stacubic_dict,
        buses=buses,
        cubics_by_objid=cubics_by_obj_id,
        bus_by_term_id=bus_by_terminal_id
    )

    name: str = element.loc_name

    r1 = element.r_pu * Sbase_vg / element.Sn
    x1 = element.x_pu * Sbase_vg / element.Sn

    effective_switch_by_cubic_id: Dict[str, StaSwitch]
    if switch_by_cubic_id is None:
        effective_switch_by_cubic_id = dict()
    else:
        effective_switch_by_cubic_id = switch_by_cubic_id
    element_is_active: bool = (
        int(element.outserv) == 0
        and _is_element_closed_by_cubicle_switches(
            element_id=element.ID,
            cubics_by_objid=cubics_by_obj_id,
            switch_by_cubic_id=effective_switch_by_cubic_id,
        )
    )

    sr = dev.SeriesReactance(
        bus_from=bus_from,
        bus_to=bus_to,
        name=name,
        idtag=_ref_id(element.ID),
        active=element_is_active,
        r=r1,
        x=x1,
        rate=element.Sn
    )

    return sr


def convert_dgs_series_capacitor_to_reactance(
        element: ElmScap,
        buses: List[dev.Bus],
        bus_by_terminal_id: Dict[str, dev.Bus],
        stacubic_dict: Dict[str, List[int]],
        cubics_by_obj_id: Dict[str, List[StaCubic]],
        logger: Logger,
        sbase_mva: float = 100.0,
        switch_by_cubic_id: Dict[str, StaSwitch] | None = None,
) -> dev.SeriesReactance:
    """
    Convert dgs series capacitor to reactance.

    :param element: element parameter.
    :param buses: buses parameter.
    :param bus_by_terminal_id: bus_by_terminal_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_obj_id: cubics_by_obj_id parameter.
    :param logger: logger parameter.
    :param sbase_mva: sbase_mva parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :return: Function result.
    """

    # Resolve buses via StaCubic.fold_id -> ElmTerm.ID -> Bus (same approach as lines/transformers)
    term_ids: List[str] = get_terminal_ids(element_id=element.ID, cubics_by_objid=cubics_by_obj_id)
    if len(term_ids) != 2:
        raise ValueError(
            f"ElmScap '{element.loc_name}' (ID={element.ID}) is not connected to exactly 2 terminals.")

    bus_pair: Tuple[dev.Bus, dev.Bus] = get_branch_buses(
        elm_id=element.ID,
        stacubic_dict=stacubic_dict,
        buses=buses,
        cubics_by_objid=cubics_by_obj_id,
        bus_by_term_id=bus_by_terminal_id
    )
    bus_from: dev.Bus = bus_pair[0]
    bus_to: dev.Bus = bus_pair[1]

    name: str = element.loc_name

    # Rated power calculation [MVA]
    Ur: float = float(element.ucn)
    Ir: float = float(element.Curn)
    Sr: float = float(np.sqrt(3.0) * Ur * Ir)

    # PowerFactory exports ``ElmScap.xcap`` as the positive magnitude of the
    # capacitive reactance.  VeraGrid's generic series branch uses the signed
    # inductive convention, so capacitance must enter its branch equation with
    # a negative reactance.  ``abs`` also keeps hand-authored DGS variants from
    # accidentally turning the capacitor into an inductor.
    # SeriesReactance inherits BranchParent virtual taps, whose primitive is
    # expressed on the from-terminal voltage base.  ``ucn`` remains the device
    # rating used for thermal power, but the physical ohms must be converted on
    # the branch base to avoid applying a 220/225 kV ratio twice.
    branch_voltage_kv: float = float(bus_from.Vnom)
    Zbase: float = branch_voltage_kv ** 2 / sbase_mva
    x: float = -abs(float(element.xcap)) / Zbase

    effective_switch_by_cubic_id: Dict[str, StaSwitch]
    if switch_by_cubic_id is None:
        effective_switch_by_cubic_id = dict()
    else:
        effective_switch_by_cubic_id = switch_by_cubic_id
    element_is_active: bool = (
        int(element.outserv) == 0
        and _is_element_closed_by_cubicle_switches(
            element_id=element.ID,
            cubics_by_objid=cubics_by_obj_id,
            switch_by_cubic_id=effective_switch_by_cubic_id,
        )
    )

    series_reactance: dev.SeriesReactance = dev.SeriesReactance(
        bus_from=bus_from,
        bus_to=bus_to,
        name=name,
        idtag=_ref_id(element.ID),
        active=element_is_active,
        r=0.0,
        x=x,
        r0=0.0,
        x0=x,
        r2=0.0,
        x2=x,
        rate=Sr
    )

    return series_reactance


def convert_dgs_to_series_reactance(
        element: ElmSind,
        buses: List[dev.Bus],
        bus_by_terminal_id: Dict[str, dev.Bus],
        stacubic_dict: Dict[str, List[int]],
        cubics_by_obj_id: Dict[str, List[StaCubic]],
        typsind_dict: Dict[str, TypSind],
        logger: Logger,
        sbase_mva: float = 100.0,
        switch_by_cubic_id: Dict[str, StaSwitch] | None = None,
) -> dev.SeriesReactance:
    """
    Convert dgs to series reactance.

    :param element: element parameter.
    :param buses: buses parameter.
    :param bus_by_terminal_id: bus_by_terminal_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_obj_id: cubics_by_obj_id parameter.
    :param typsind_dict: typsind_dict parameter.
    :param logger: logger parameter.
    :param sbase_mva: sbase_mva parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :return: Function result.
    """

    # Resolve buses via StaCubic.fold_id -> ElmTerm.ID -> Bus (same approach as lines/transformers)
    term_ids: List[str] = get_terminal_ids(element_id=element.ID, cubics_by_objid=cubics_by_obj_id)
    if len(term_ids) != 2:
        raise ValueError(
            f"ElmSind '{element.loc_name}' (ID={element.ID}) is not connected to exactly 2 terminals.")

    bus_from, bus_to = get_branch_buses(
        elm_id=element.ID,
        stacubic_dict=stacubic_dict,
        buses=buses,
        cubics_by_objid=cubics_by_obj_id,
        bus_by_term_id=bus_by_terminal_id
    )

    name: str = element.loc_name

    # Initialize sequence impedances (p.u.)
    r_pu: float = 1e-20
    x_pu: float = 1e-20
    r0_pu: float = 1e-20
    x0_pu: float = 1e-20
    r2_pu: float = 1e-20
    x2_pu: float = 1e-20

    # --- ElmSind: series reactor / series reactance

    # Prefer the type/template if present (PowerFactory "Type" pattern)
    typ_id: str | None = _ref_id(element.typ_id)
    if typ_id == "":
        typ_id = None

    src: ElmSind | TypSind = element
    if typ_id is not None and typ_id in typsind_dict:
        src = typsind_dict[typ_id]

    # PowerFactory ElmSind (as exported in test_export_v5.dgs):
    # - ucn: rated voltage (kV)
    # - Sn : rated power (MVA)
    # - uk : short-circuit voltage (%), gives |Z| in p.u. on device base (Sn, ucn)
    # - Pcu: copper losses (kW) at rated current, gives R in p.u. on device base
    sn_mva: float = float(src.Sn)
    uk_pu_dev: float = float(src.uk) / 100.0
    p_cu_mw: float = float(src.Pcu) / 1000.0

    r_pu_dev: float = p_cu_mw / sn_mva
    z_pu_dev: float = uk_pu_dev
    x_pu_dev: float = math.sqrt(max(0.0, z_pu_dev * z_pu_dev - r_pu_dev * r_pu_dev))

    # Convert from device base (Sn, ucn) to system base (sbase_mva, Vbase)
    v_dev_kv: float = float(src.ucn)
    v_base_kv: float = float(max(float(bus_from.Vnom), float(bus_to.Vnom)))
    v_ratio: float = v_dev_kv / v_base_kv

    scale: float = (sbase_mva / sn_mva) * (v_ratio * v_ratio)

    r_pu = r_pu_dev * scale
    x_pu = x_pu_dev * scale

    # If no explicit sequence data is exported, keep them consistent with positive sequence
    r0_pu = r_pu
    x0_pu = x_pu
    r2_pu = r_pu
    x2_pu = x_pu

    effective_switch_by_cubic_id: Dict[str, StaSwitch]
    if switch_by_cubic_id is None:
        effective_switch_by_cubic_id = dict()
    else:
        effective_switch_by_cubic_id = switch_by_cubic_id
    element_is_active: bool = (
        int(element.outserv) == 0
        and _is_element_closed_by_cubicle_switches(
            element_id=element.ID,
            cubics_by_objid=cubics_by_obj_id,
            switch_by_cubic_id=effective_switch_by_cubic_id,
        )
    )

    series_reactance = dev.SeriesReactance(
        bus_from=bus_from,
        bus_to=bus_to,
        name=name,
        idtag=_ref_id(element.ID),
        active=element_is_active,
        r=r_pu,
        x=x_pu,
        r0=r0_pu,
        x0=x0_pu,
        r2=r2_pu,
        x2=x2_pu,
        rate=sn_mva
    )

    return series_reactance


def _get_scale_factor(scale0: float, logger: Logger, name: str) -> float:
    """
    Get scale factor.

    :param scale0: scale0 parameter.
    :param logger: logger parameter.
    :param name: name parameter.
    :return: Function result.
    """
    s = scale0
    if s == 0.0:
        return 1.0

    # Heuristic: values > 10 are very likely percentages (e.g., 100 = 100%)
    if s > 10.0:
        logger.add_warning(
            f"looks like percent.",
            device=name,
            device_class="ElmLod",
            value=s,
        )
        return s / 100.0

    return s


def _extract_load_pq(elmlod: ElmLod, logger: Logger) -> Tuple[float, float]:
    """
    Extract load pq.

    :param elmlod: elmlod parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    name = elmlod.loc_name or _ref_id(elmlod.ID) or "Load"

    # Primary: direct P/Q
    p = elmlod.plini
    q = elmlod.qlini

    # Fallback: S + cos(phi)
    if p == 0.0 and q == 0.0:
        s = elmlod.slini
        cosphi = elmlod.coslini

        if s != 0.0 and cosphi != 0.0:
            cosphi = max(min(cosphi, 1.0), -1.0)
            p = s * cosphi
            sinphi = math.sqrt(max(0.0, 1.0 - cosphi * cosphi))
            q = s * sinphi
            logger.add_warning(
                f"P/Q not provided, derived from slini/coslini.",
                device=name,
                device_class="ElmLod",
                value=q,
            )

    # Apply scaling
    scale = _get_scale_factor(scale0=elmlod.scale0, logger=logger, name=name)
    p *= scale
    q *= scale

    return p, q


def convert_dgs_ward_equivalent_to_load(elmvac: ElmVac,
                                        stacubic_dict: Dict[str, List[int]],
                                        buses: List[dev.Bus],
                                        logger: Logger,
                                        cubics_by_objid: Dict[str, List[StaCubic]],
                                        bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.Load]:
    """
    Convert dgs ward equivalent to load.

    :param elmvac: elmvac parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmvac.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    name: str = elmvac.loc_name

    constant_p = elmvac.Pload - elmvac.Pgen  # Net constant P active power [MW]
    constant_q = elmvac.Qload - elmvac.Qgen  # Net constant Q reactive power [Mvar]
    constant_g = elmvac.Pzload  # Constant Z active power [MW]
    constant_b = -1 * elmvac.Qzload  # Constant Z reactive power [Mvar]

    load = dev.Load(
        name=name,
        idtag=_ref_id(elmvac.ID),
        P=constant_p,
        Q=constant_q,
        G=constant_g,
        B=constant_b,
        active=not bool(elmvac.outserv)
    )

    return bus, load


def convert_dgs_to_load(elmlod: ElmLod,
                        stacubic_dict: Dict[str, List[int]],
                        buses: List[dev.Bus],
                        logger: Logger,
                        cubics_by_objid: Dict[str, List[StaCubic]],
                        bus_by_term_id: Dict[str, dev.Bus],
                        switch_by_cubic_id: Dict[str, StaSwitch] | None = None,
                        use_power_flow_snapshot: bool = False) -> Tuple[dev.Bus, dev.Load]:
    """
    Convert dgs to load.

    :param elmlod: elmlod parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :param use_power_flow_snapshot: Use solved terminal P/Q when both are exported.
    :return: Function result.
    """
    effective_switch_by_cubic_id: Dict[str, StaSwitch]
    if switch_by_cubic_id is None:
        effective_switch_by_cubic_id = dict()
    else:
        effective_switch_by_cubic_id = switch_by_cubic_id

    bus = get_injection_bus(elm_id=elmlod.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    has_solved_power: bool = (
        use_power_flow_snapshot
        and elmlod.m_p_bus1 is not None
        and elmlod.m_q_bus1 is not None
    )
    if has_solved_power:
        # ElmLod terminal results use the passive equipment convention, which
        # matches VeraGrid Load positive consumption without a sign reversal.
        p_mw: float = float(elmlod.m_p_bus1)
        q_mvar: float = float(elmlod.m_q_bus1)
    else:
        p_mw, q_mvar = _extract_load_pq(elmlod=elmlod, logger=logger)

    load = dev.Load(
        name=elmlod.loc_name or f"Load_{_ref_id(elmlod.ID)}",
        idtag=_ref_id(elmlod.ID),
        P=p_mw,
        Q=q_mvar,
        # PowerFactory considers an in-service injection disconnected when its
        # cubicle switch is open.  Both states are therefore required.
        active=(
            not bool(elmlod.outserv)
            and _is_element_closed_by_cubicle_switches(
                element_id=elmlod.ID,
                cubics_by_objid=cubics_by_objid,
                switch_by_cubic_id=effective_switch_by_cubic_id,
            )
        )
    )

    return bus, load


def _get_initial_reactive_limit_state(
        source_state: int | None,
        solved_reactive_power_mvar: float | None,
        minimum_reactive_power_mvar: float,
        maximum_reactive_power_mvar: float,
) -> ReactivePowerLimitState:
    """Translate a DGS calculated Q-limit flag into a typed warm start.

    ``c:i_qlim`` identifies whether a native capability axis is active, but its
    sign can reverse for motor-oriented machines.  When ``m:Q`` is available,
    the nearest imported physical bound supplies the unambiguous injection
    orientation.  Unsupported or absent values remain unknown.

    :param source_state: Optional native ``c:i_qlim`` value.
    :param solved_reactive_power_mvar: Optional per-device solved Q injection.
    :param minimum_reactive_power_mvar: Imported physical Qmin.
    :param maximum_reactive_power_mvar: Imported physical Qmax.
    :return: Typed, non-authoritative initial reactive-limit state.
    """
    if source_state is None:
        state: ReactivePowerLimitState = ReactivePowerLimitState.Unknown
    else:
        numeric_state: int = int(source_state)
        if numeric_state == 0:
            state = ReactivePowerLimitState.Free
        else:
            state_is_supported_bound: bool = bool(
                numeric_state == -1 or numeric_state == 1
            )
            solved_q_is_usable: bool = bool(
                solved_reactive_power_mvar is not None
                and math.isfinite(float(solved_reactive_power_mvar))
            )
            if state_is_supported_bound and solved_q_is_usable:
                solved_q: float = float(solved_reactive_power_mvar)
                distance_to_minimum: float = abs(
                    solved_q - minimum_reactive_power_mvar
                )
                distance_to_maximum: float = abs(
                    solved_q - maximum_reactive_power_mvar
                )
                if distance_to_minimum <= distance_to_maximum:
                    state = ReactivePowerLimitState.AtMinimum
                else:
                    state = ReactivePowerLimitState.AtMaximum
            else:
                if numeric_state == -1:
                    state = ReactivePowerLimitState.AtMinimum
                else:
                    if numeric_state == 1:
                        state = ReactivePowerLimitState.AtMaximum
                    else:
                        state = ReactivePowerLimitState.Unknown
    return state


def _select_effective_reactive_limits(
        calculated_minimum_mvar: float | None,
        calculated_maximum_mvar: float | None,
        fallback_minimum_mvar: float,
        fallback_maximum_mvar: float,
        parallel_count: int,
        use_calculated_results: bool = False,
) -> Tuple[float, float]:
    """
    Select configured Q limits, optionally using a solved PowerFactory snapshot.

    PowerFactory calculation attributes describe the aggregate equipment row.
    VeraGrid expands ``ngnum`` parallel rows into individual devices, therefore
    each calculated limit is divided by the explicit parallel count.  Missing
    or invalid calculated values independently retain their operational
    fallback; an inconsistent final interval falls back as one pair.

    :param calculated_minimum_mvar: Optional aggregate ``c:Qmin`` result.
    :param calculated_maximum_mvar: Optional aggregate ``c:Qmax`` result.
    :param fallback_minimum_mvar: Per-device operational lower limit.
    :param fallback_maximum_mvar: Per-device operational upper limit.
    :param parallel_count: Number of expanded parallel devices.
    :param use_calculated_results: Permit solved ``c:Qmin`` and ``c:Qmax`` results.
    :return: Per-device minimum and maximum reactive limits in MVAr.
    """
    effective_parallel_count: int = max(1, int(parallel_count))
    if (
        use_calculated_results
        and calculated_minimum_mvar is not None
        and math.isfinite(calculated_minimum_mvar)
    ):
        selected_minimum_mvar: float = (
            float(calculated_minimum_mvar) / float(effective_parallel_count)
        )
    else:
        selected_minimum_mvar = float(fallback_minimum_mvar)
    if (
        use_calculated_results
        and calculated_maximum_mvar is not None
        and math.isfinite(calculated_maximum_mvar)
    ):
        selected_maximum_mvar: float = (
            float(calculated_maximum_mvar) / float(effective_parallel_count)
        )
    else:
        selected_maximum_mvar = float(fallback_maximum_mvar)

    if selected_minimum_mvar <= selected_maximum_mvar:
        result: Tuple[float, float] = (selected_minimum_mvar, selected_maximum_mvar)
    else:
        result = (float(fallback_minimum_mvar), float(fallback_maximum_mvar))
    return result


def _get_elmgenstat_reactive_limits(
        elmgenstat: ElmGenstat,
        parallel_count: int,
        use_calculated_results: bool = False,
) -> Tuple[float, float]:
    """
    Resolve one ElmGenstat operational/effective reactive capability interval.

    :param elmgenstat: Parsed static-generator row.
    :param parallel_count: Number of expanded parallel devices.
    :param use_calculated_results: Permit solved ``c:Qmin`` and ``c:Qmax`` results.
    :return: Per-device minimum and maximum reactive limits in MVAr.
    """
    rated_power_mva: float = float(elmgenstat.sgn)
    if elmgenstat.cQ_min is None:
        fallback_minimum_mvar: float = -rated_power_mva
    else:
        fallback_minimum_mvar = float(elmgenstat.cQ_min)
    if elmgenstat.cQ_max is None:
        fallback_maximum_mvar: float = rated_power_mva
    else:
        fallback_maximum_mvar = float(elmgenstat.cQ_max)
    return _select_effective_reactive_limits(
        calculated_minimum_mvar=elmgenstat.calculated_qmin_mvar,
        calculated_maximum_mvar=elmgenstat.calculated_qmax_mvar,
        fallback_minimum_mvar=fallback_minimum_mvar,
        fallback_maximum_mvar=fallback_maximum_mvar,
        parallel_count=parallel_count,
        use_calculated_results=use_calculated_results,
    )


def _build_intqlim_q_points(
        capability_curve: IntQlim | None,
        rated_power_mva: float,
        minimum_scale_percent: float | None,
        maximum_scale_percent: float | None,
) -> List[Tuple[float, float, float]] | None:
    """
    Convert one native PowerFactory capability curve to physical MW/MVAr points.

    ``IntQlim.inputmod=1`` stores all three axes per unit on the individual
    machine rated power.  Absolute curves already describe one machine, which
    is also the representation used after VeraGrid expands ``ngnum``.

    :param capability_curve: Referenced native curve or ``None``.
    :param rated_power_mva: Individual machine rated apparent power.
    :param minimum_scale_percent: Configured lower-limit scaling factor.
    :param maximum_scale_percent: Configured upper-limit scaling factor.
    :return: Ordered physical curve points, or ``None`` when incomplete.
    """
    if capability_curve is None:
        result: List[Tuple[float, float, float]] | None = None
    else:
        point_count: int = len(capability_curve.active_power_points)
        vectors_are_aligned: bool = (
            point_count > 0
            and len(capability_curve.minimum_reactive_points) == point_count
            and len(capability_curve.maximum_reactive_points) == point_count
        )
        if vectors_are_aligned:
            if int(capability_curve.inputmod) == 1:
                base_multiplier: float = float(rated_power_mva)
            else:
                base_multiplier = 1.0
            if minimum_scale_percent is None:
                minimum_scale: float = 1.0
            else:
                minimum_scale = float(minimum_scale_percent) / 100.0
            if maximum_scale_percent is None:
                maximum_scale: float = 1.0
            else:
                maximum_scale = float(maximum_scale_percent) / 100.0

            # PowerFactory permits repeated active-power ordinates to close a
            # capability polygon vertically.  VeraGrid's Q(P) characteristic
            # needs one interval per ordinate, so merge those rows into their
            # physical union instead of rejecting the complete native curve.
            points: List[Tuple[float, float, float]] = list()
            previous_active_power_mw: float | None = None
            points_are_ordered: bool = True
            all_points_are_valid: bool = True
            point_index: int
            for point_index in range(point_count):
                active_power_mw: float = (
                    float(capability_curve.active_power_points[point_index])
                    * base_multiplier
                )
                minimum_reactive_power_mvar: float = (
                    float(capability_curve.minimum_reactive_points[point_index])
                    * base_multiplier
                    * minimum_scale
                )
                maximum_reactive_power_mvar: float = (
                    float(capability_curve.maximum_reactive_points[point_index])
                    * base_multiplier
                    * maximum_scale
                )
                point_is_valid: bool = (
                    math.isfinite(active_power_mw)
                    and math.isfinite(minimum_reactive_power_mvar)
                    and math.isfinite(maximum_reactive_power_mvar)
                    and minimum_reactive_power_mvar
                    <= maximum_reactive_power_mvar
                )
                if point_is_valid:
                    if (
                        previous_active_power_mw is None
                        or active_power_mw > previous_active_power_mw
                    ):
                        previous_active_power_mw = active_power_mw
                        points.append((
                            active_power_mw,
                            minimum_reactive_power_mvar,
                            maximum_reactive_power_mvar,
                        ))
                    else:
                        repeated_ordinate: bool = math.isclose(
                            active_power_mw,
                            previous_active_power_mw,
                            rel_tol=1e-12,
                            abs_tol=1e-12,
                        )
                        if repeated_ordinate and len(points) > 0:
                            previous_point: Tuple[float, float, float] = points[-1]
                            points[-1] = (
                                previous_point[0],
                                min(previous_point[1], minimum_reactive_power_mvar),
                                max(previous_point[2], maximum_reactive_power_mvar),
                            )
                        else:
                            points_are_ordered = False
                else:
                    all_points_are_valid = False
            else:
                pass
            if len(points) > 0 and points_are_ordered and all_points_are_valid:
                result = points
            else:
                result = None
        else:
            result = None
    return result


def _validate_intqlim_points_against_structural_limits(
        capability_curve: IntQlim | None,
        capability_points: List[Tuple[float, float, float]] | None,
        structural_minimum_mvar: float,
        structural_maximum_mvar: float,
) -> List[Tuple[float, float, float]] | None:
    """Reject an exported zero placeholder that contradicts physical Q limits.

    Some PowerFactory projects retain an ``IntQlim`` reference whose selected
    vector representation contains several all-zero rows.  Those rows are a
    placeholder, not a zero-capability characteristic, when the same device
    declares a finite non-zero operational Q interval.  Treating the rows as a
    real curve would collapse the actuator and disable its external controller.

    A genuine vertical curve or a real zero-Q constraint is retained because
    rejection requires every configured P, Qmin and Qmax ordinate to be zero
    and an explicit contradictory structural interval.

    :param capability_curve: Referenced native capability curve.
    :param capability_points: Converted physical capability points.
    :param structural_minimum_mvar: Device-level configured minimum Q.
    :param structural_maximum_mvar: Device-level configured maximum Q.
    :return: Validated points, or ``None`` for an incomplete placeholder.
    """
    structural_interval_is_valid: bool = bool(
        math.isfinite(structural_minimum_mvar)
        and math.isfinite(structural_maximum_mvar)
        and structural_minimum_mvar < structural_maximum_mvar
        and not math.isclose(
            structural_minimum_mvar,
            structural_maximum_mvar,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
    )
    if capability_curve is None or capability_points is None:
        result: List[Tuple[float, float, float]] | None = capability_points
    else:
        vector_count: int = len(capability_curve.active_power_points)
        vectors_are_aligned: bool = bool(
            vector_count > 0
            and len(capability_curve.minimum_reactive_points) == vector_count
            and len(capability_curve.maximum_reactive_points) == vector_count
        )
        all_ordinates_are_zero: bool = vectors_are_aligned
        ordinate_index: int
        for ordinate_index in range(vector_count):
            ordinate_is_zero: bool = bool(
                math.isclose(
                    float(capability_curve.active_power_points[ordinate_index]),
                    0.0,
                    rel_tol=0.0,
                    abs_tol=1.0e-12,
                )
                and math.isclose(
                    float(capability_curve.minimum_reactive_points[ordinate_index]),
                    0.0,
                    rel_tol=0.0,
                    abs_tol=1.0e-12,
                )
                and math.isclose(
                    float(capability_curve.maximum_reactive_points[ordinate_index]),
                    0.0,
                    rel_tol=0.0,
                    abs_tol=1.0e-12,
                )
            )
            if ordinate_is_zero:
                pass
            else:
                all_ordinates_are_zero = False
        else:
            pass
        if all_ordinates_are_zero and structural_interval_is_valid:
            result = None
        else:
            result = capability_points
    return result


def _evaluate_qp_characteristic_reactive_power(
        capability_points: List[Tuple[float, float, float]] | None,
        active_power_mw: float,
) -> float | None:
    """
    Evaluate the centre line of one configured PowerFactory Q(P) characteristic.

    PowerFactory's ``ElmGenstat.av_mode=qpchar`` follows the midpoint between
    the lower and upper ordinates of its referenced ``IntQlim`` at the active
    power setpoint. Values outside the tabulated range use the nearest endpoint,
    matching the bounded interpolation used for physical capability curves.

    :param capability_points: Ordered physical ``P,Qmin,Qmax`` curve points.
    :param active_power_mw: Configured active-power setpoint in MW.
    :return: Configured reactive-power target in MVAr, or ``None`` if unavailable.
    """
    points_are_available: bool = bool(
        capability_points is not None
        and len(capability_points) > 0
        and math.isfinite(active_power_mw)
    )
    if points_are_available and capability_points is not None:
        point_count: int = len(capability_points)
        active_power_axis: np.ndarray = np.empty(point_count, dtype=float)
        midpoint_axis: np.ndarray = np.empty(point_count, dtype=float)
        point_index: int
        for point_index in range(point_count):
            point: Tuple[float, float, float] = capability_points[point_index]
            active_power_axis[point_index] = float(point[0])
            midpoint_axis[point_index] = 0.5 * (
                float(point[1]) + float(point[2])
            )
        else:
            pass
        axes_are_finite: bool = bool(
            np.all(np.isfinite(active_power_axis))
            and np.all(np.isfinite(midpoint_axis))
        )
        if axes_are_finite:
            result: float | None = float(np.interp(
                active_power_mw,
                active_power_axis,
                midpoint_axis,
            ))
        else:
            result = None
    else:
        result = None
    return result


def _orient_capability_points_as_network_injection(
        capability_points: List[Tuple[float, float, float]] | None,
        is_motor: bool,
) -> List[Tuple[float, float, float]] | None:
    """
    Orient one synchronous-machine capability curve as network injection.

    PowerFactory stores an ``ElmSym`` motor curve in the equipment convention:
    positive active and reactive axes describe power absorbed by the motor.
    VeraGrid generators use the network-injection convention.  Negating both
    axes reverses the active-power order and exchanges the reactive endpoints,
    therefore the source points must also be traversed backwards.

    :param capability_points: Ordered equipment-oriented ``P,Qmin,Qmax`` points.
    :param is_motor: Whether the source ``ElmSym`` operates as a motor.
    :return: Ordered network-injection curve points, or ``None``.
    """
    if capability_points is None:
        result: List[Tuple[float, float, float]] | None = None
    else:
        if is_motor:
            result = list()
            source_index: int
            for source_index in range(len(capability_points) - 1, -1, -1):
                source_point: Tuple[float, float, float] = capability_points[source_index]
                result.append((
                    -float(source_point[0]),
                    -float(source_point[2]),
                    -float(source_point[1]),
                ))
            else:
                pass
        else:
            result = capability_points
    return result


def _is_elmsym_network_motor(elmsym: ElmSym) -> bool:
    """
    Distinguish consuming synchronous motors from synchronous condensers.

    PowerFactory exports synchronous condensers with ``i_mot=1`` because their
    active-power direction follows the motor convention. Their native
    ``Reactive power compensation`` category keeps generator-oriented
    reactive limits, so reversing Q or its capability curve is incorrect.

    :param elmsym: Parsed synchronous-machine row.
    :return: ``True`` only for a consuming synchronous motor.
    """
    category: str = str(elmsym.cCategory).strip().casefold()
    is_reactive_compensator: bool = category == "reactive power compensation"
    if int(elmsym.i_mot) == 1 and not is_reactive_compensator:
        result: bool = True
    else:
        result = False
    return result


def _resolve_elmgenstat_dq_reference_angle_delay(
        source: ElmGenstat,
        device_name: str,
        logger: Logger,
) -> Tuple[bool, float]:
    """Resolve the native ElmGenstat internal dq-angle delay contract.

    PowerFactory filters the internally calculated terminal-angle sine and
    cosine only when ``iDelay=1``. An enabled delay without a finite positive
    ``Tdelay`` is incomplete source data and remains disabled with a diagnostic
    instead of inventing a project-specific constant.

    :param source: Parsed static-generator DGS row.
    :param device_name: Human-readable device name used by diagnostics.
    :param logger: Import diagnostic sink.
    :return: Enabled flag and validated time constant in seconds.
    """
    raw_enabled: int | None = source.iDelay
    raw_time_constant: float | None = source.Tdelay
    requested_enabled: bool = raw_enabled == 1
    time_constant_is_valid: bool = bool(
        raw_time_constant is not None
        and math.isfinite(float(raw_time_constant))
        and float(raw_time_constant) > 0.0
    )
    if requested_enabled and time_constant_is_valid and raw_time_constant is not None:
        enabled: bool = True
        time_constant: float = float(raw_time_constant)
    else:
        enabled = False
        time_constant = 0.0
        if requested_enabled:
            logger.add_warning(
                msg="Incomplete ElmGenstat dq reference-angle delay",
                device=device_name,
                value=raw_time_constant,
                expected_value="Finite Tdelay > 0 when iDelay=1",
                device_class="ElmGenstat",
            )
        else:
            pass
    return enabled, time_constant


def convert_dgs_staticgen_to_gen(elmgenstat: ElmGenstat,
                                 stacubic_dict: Dict[str, List[int]],
                                 buses: List[dev.Bus],
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus],
                                 parallel_index: int = 0,
                                 parallel_count: int = 1,
                                 use_power_flow_snapshot: bool = False,
                                 external_reactive_control_model: bool = False,
                                 capability_curve: IntQlim | None = None) -> Tuple[dev.Bus, dev.Generator]:
    """
    Convert dgs staticgen to gen.

    :param elmgenstat: elmgenstat parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param use_power_flow_snapshot: Freeze exported solved P/Q when both result columns exist.
    :param external_reactive_control_model: Composite model owns the terminal Q/V control.
    :param capability_curve: Referenced active/reactive capability curve.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmgenstat.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    # Slack/reference machine indicator (PowerFactory exports ip_ctrl=1 on the slack generator)
    if int(elmgenstat.ip_ctrl) == 1:
        bus.set_is_slack_at(t=None, val=True)

    generator_name = _get_non_empty_name(elmgenstat.loc_name, f"{_ref_id(elmgenstat.ID)}")
    generator_name = _get_parallel_device_name(generator_name, parallel_index, parallel_count)
    generator_idtag = _get_parallel_device_idtag(_ref_id(elmgenstat.ID), parallel_index, parallel_count)
    dq_angle_delay_enabled: bool
    dq_angle_delay_time_constant: float
    dq_angle_delay_enabled, dq_angle_delay_time_constant = (
        _resolve_elmgenstat_dq_reference_angle_delay(
            source=elmgenstat,
            device_name=generator_name,
            logger=logger,
        )
    )

    source_control_mode: str = str(elmgenstat.av_mode).strip().lower()
    category_name: str = str(elmgenstat.cCategory).strip().lower()
    composite_model_pointer: str = str(elmgenstat.c_pmod).strip()
    composite_owns_hvdc_reactive_control: bool = bool(
        category_name == "hvdc terminal"
        and (
            external_reactive_control_model
            or composite_model_pointer not in {"", "*", "None"}
            # Legacy PowerFactory DGS definitions omit c_pmod on some HVDC
            # terminals.  Their standard vdroop label describes the converter
            # plant interface; it is not an autonomous ElmGenstat Q/V law.
            or source_control_mode == "vdroop"
        )
    )
    has_solved_power: bool = (
        use_power_flow_snapshot
        and elmgenstat.m_p_bus1 is not None
        and elmgenstat.m_q_bus1 is not None
    )
    generator_control_mode: GeneratorControlMode
    droop_gain: float = 1.0
    rated_power_mva: float = float(elmgenstat.sgn)
    minimum_reactive_power_mvar: float
    maximum_reactive_power_mvar: float

    # Legacy DGS files may omit operational and calculated limits.  The helper
    # retains the finite rated-power fallback only for genuinely absent data.
    minimum_reactive_power_mvar, maximum_reactive_power_mvar = _get_elmgenstat_reactive_limits(
        elmgenstat=elmgenstat,
        parallel_count=parallel_count,
        use_calculated_results=use_power_flow_snapshot,
    )
    capability_points: List[Tuple[float, float, float]] | None = (
        _build_intqlim_q_points(
            capability_curve=capability_curve,
            rated_power_mva=rated_power_mva,
            minimum_scale_percent=elmgenstat.scaleQmin,
            maximum_scale_percent=elmgenstat.scaleQmax,
        )
    )
    capability_points = _validate_intqlim_points_against_structural_limits(
        capability_curve=capability_curve,
        capability_points=capability_points,
        structural_minimum_mvar=minimum_reactive_power_mvar,
        structural_maximum_mvar=maximum_reactive_power_mvar,
    )
    if capability_points is None:
        if capability_curve is None:
            pass
        else:
            logger.add_warning(
                msg="Incomplete ElmGenstat capability curve",
                device=generator_name,
                value=_ref_id(capability_curve.ID),
                expected_value="Aligned finite P, Qmin and Qmax vectors",
                device_class="IntQlim",
            )
    else:
        active_curve_axis: List[float] = list()
        minimum_curve_axis: List[float] = list()
        maximum_curve_axis: List[float] = list()
        curve_point: Tuple[float, float, float]
        for curve_point in capability_points:
            active_curve_axis.append(curve_point[0])
            minimum_curve_axis.append(curve_point[1])
            maximum_curve_axis.append(curve_point[2])
        else:
            pass
        minimum_reactive_power_mvar = float(np.interp(
            float(elmgenstat.pgini),
            active_curve_axis,
            minimum_curve_axis,
        ))
        maximum_reactive_power_mvar = float(np.interp(
            float(elmgenstat.pgini),
            active_curve_axis,
            maximum_curve_axis,
        ))

    # PowerFactory's ``constv`` mode is a classic PV controller.  ``vdroop``
    # instead follows Q = Snom * 100 / ddroop * (Vset - V), clipped by the
    # exported physical MVAr limits.  VeraGrid's generator droop kernel stores
    # the slope relative to Qmax, so the gain below converts that convention
    # without losing the native rated-power basis.
    if composite_owns_hvdc_reactive_control:
        # A PowerFactory HVDC terminal with c_pmod is an actuator of the
        # converter composite, not an autonomous static Q/V controller.  Its
        # configured qgini remains the network injection while the associated
        # composite/SVC owns voltage support.  Treating av_mode=vdroop locally
        # would install a duplicate controller with fictitious reactive range.
        generator_control_mode = GeneratorControlMode.Q
    elif source_control_mode == "constv":
        generator_control_mode = GeneratorControlMode.V
    else:
        if source_control_mode == "vdroop":
            generator_control_mode = GeneratorControlMode.QVDroop
            positive_reactive_limit: float = maximum_reactive_power_mvar
            droop_percent: float = float(elmgenstat.ddroop)
            if droop_percent > 0.0 and positive_reactive_limit > 0.0:
                droop_gain = (
                    100.0 * rated_power_mva
                    / (droop_percent * positive_reactive_limit)
                )
            else:
                # An incomplete droop record remains a fixed-Q source.  This
                # explicit fallback avoids an infinite or sign-reversed gain.
                generator_control_mode = GeneratorControlMode.Q
                logger.add_warning(
                    msg="Incomplete ElmGenstat voltage-droop parameters",
                    device=generator_name,
                    value=f"ddroop={droop_percent}, cQ_max={positive_reactive_limit}",
                    expected_value="ddroop > 0 and cQ_max > 0",
                    device_class="ElmGenstat",
                )
        else:
            generator_control_mode = GeneratorControlMode.Q

    if has_solved_power:
        # Snapshot mode freezes the already solved terminal injection.  Native
        # station-control metadata remains available on StationController.
        generator_control_mode = GeneratorControlMode.Q
        active_power_mw: float = float(elmgenstat.m_p_bus1) / float(parallel_count)
        reactive_power_mvar: float = float(elmgenstat.m_q_bus1) / float(parallel_count)
    else:
        active_power_mw = float(elmgenstat.pgini)
        reactive_power_mvar = float(elmgenstat.qgini)

    gen = dev.Generator(
        name=generator_name,
        idtag=generator_idtag,
        P=active_power_mw,
        Q=reactive_power_mvar,
        vset=float(elmgenstat.usetp),
        control_mode=generator_control_mode,
        k_droop=droop_gain,
        Qmin=minimum_reactive_power_mvar,
        Qmax=maximum_reactive_power_mvar,
        Snom=rated_power_mva,
        rms_dq_reference_angle_delay_enabled=dq_angle_delay_enabled,
        rms_dq_reference_angle_delay_time_constant=(
            dq_angle_delay_time_constant
        ),
        q_points=capability_points,
        use_reactive_power_curve=capability_points is not None,
        active=not bool(elmgenstat.outserv)
    )
    gen.initial_reactive_limit_state = _get_initial_reactive_limit_state(
        source_state=elmgenstat.calculated_q_limit_state,
        solved_reactive_power_mvar=(
            None
            if elmgenstat.m_q_bus1 is None
            else float(elmgenstat.m_q_bus1) / float(parallel_count)
        ),
        minimum_reactive_power_mvar=minimum_reactive_power_mvar,
        maximum_reactive_power_mvar=maximum_reactive_power_mvar,
    )

    return bus, gen


def convert_dgs_staticgen_to_battery(elmgenstat: ElmGenstat,
                                     stacubic_dict: Dict[str, List[int]],
                                     buses: List[dev.Bus],
                                     logger: Logger,
                                     cubics_by_objid: Dict[str, List[StaCubic]],
                                     bus_by_term_id: Dict[str, dev.Bus],
                                     parallel_index: int = 0,
                                     parallel_count: int = 1,
                                     use_power_flow_snapshot: bool = False) -> Tuple[dev.Bus, dev.Battery]:
    """
    Convert dgs staticgen to battery.

    :param elmgenstat: elmgenstat parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param use_power_flow_snapshot: Freeze exported solved P/Q when both result columns exist.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmgenstat.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    name = _get_non_empty_name(elmgenstat.loc_name, f"Storage_{_ref_id(elmgenstat.ID)}")
    name = _get_parallel_device_name(name, parallel_index, parallel_count)
    battery_idtag = _get_parallel_device_idtag(_ref_id(elmgenstat.ID), parallel_index, parallel_count)

    # Preserve the native dispatch on the storage representation.  Power factor
    # is derived by the device when needed, so keeping a redundant local value
    # here would create an unused second source of truth.
    has_solved_power: bool = (
        use_power_flow_snapshot
        and elmgenstat.m_p_bus1 is not None
        and elmgenstat.m_q_bus1 is not None
    )
    if has_solved_power:
        P: float = float(elmgenstat.m_p_bus1) / float(parallel_count)
        Q: float = float(elmgenstat.m_q_bus1) / float(parallel_count)
    else:
        P = float(elmgenstat.pgini)
        Q = float(elmgenstat.qgini)
    minimum_reactive_power_mvar: float
    maximum_reactive_power_mvar: float
    minimum_reactive_power_mvar, maximum_reactive_power_mvar = _get_elmgenstat_reactive_limits(
        elmgenstat=elmgenstat,
        parallel_count=parallel_count,
        use_calculated_results=use_power_flow_snapshot,
    )

    battery = dev.Battery(
        name=name,
        idtag=battery_idtag,
        P=P,
        Q=Q,
        control_mode=GeneratorControlMode.Q,
        Snom=float(elmgenstat.sgn),
        Qmin=minimum_reactive_power_mvar,
        Qmax=maximum_reactive_power_mvar,
        active=not bool(elmgenstat.outserv)
    )

    return bus, battery


def convert_dgs_to_static_gen(elmgenstat: ElmGenstat,
                              stacubic_dict: Dict[str, List[int]],
                              buses: List[dev.Bus],
                              logger: Logger,
                              cubics_by_objid: Dict[str, List[StaCubic]],
                              bus_by_term_id: Dict[str, dev.Bus],
                              parallel_index: int = 0,
                              parallel_count: int = 1,
                              use_power_flow_snapshot: bool = False,
                              configured_reactive_power_mvar: float | None = None) -> Tuple[
    dev.Bus, dev.StaticGenerator]:
    """
    Convert dgs to static gen.

    :param elmgenstat: elmgenstat parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param use_power_flow_snapshot: Freeze exported solved P/Q when both result columns exist.
    :param configured_reactive_power_mvar: Optional DGS-characteristic Q target.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmgenstat.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    # Slack/reference machine indicator (PowerFactory exports ip_ctrl=1 on the slack generator)
    if int(elmgenstat.ip_ctrl) == 1:
        bus.set_is_slack_at(t=None, val=True)

    generator_name = _get_non_empty_name(elmgenstat.loc_name, f"StaticGen_{_ref_id(elmgenstat.ID)}")
    generator_name = _get_parallel_device_name(generator_name, parallel_index, parallel_count)
    generator_idtag = _get_parallel_device_idtag(_ref_id(elmgenstat.ID), parallel_index, parallel_count)

    has_solved_power: bool = (
        use_power_flow_snapshot
        and elmgenstat.m_p_bus1 is not None
        and elmgenstat.m_q_bus1 is not None
    )
    if has_solved_power:
        active_power_mw: float = float(elmgenstat.m_p_bus1) / float(parallel_count)
        reactive_power_mvar: float = float(elmgenstat.m_q_bus1) / float(parallel_count)
    else:
        active_power_mw = float(elmgenstat.pgini)
        if configured_reactive_power_mvar is None:
            reactive_power_mvar = float(elmgenstat.qgini)
        else:
            reactive_power_mvar = float(configured_reactive_power_mvar)

    stagen = dev.StaticGenerator(
        name=generator_name,
        idtag=generator_idtag,
        P=active_power_mw,
        Q=reactive_power_mvar,
        Snom=float(elmgenstat.sgn),
        active=not bool(elmgenstat.outserv)
    )

    return bus, stagen


def _get_powerfactory_vsc_loss_coefficients(
        source: ElmVsc | ElmVscmono,
        system_base_mva: float,
) -> Tuple[float, float, float]:
    """Convert native PWM loss data to VeraGrid's per-unit polynomial.

    PowerFactory represents the internal series-reactor copper loss by ``Pcu``
    at ``Snom`` and adds switching and semiconductor resistance factors. Native
    three-terminal ``ElmVsc`` equipment also dissipates current-squared loss
    through the positive-sequence arm equivalent ``Rarm / 2``. For native
    two-terminal ``ElmVscmono``, PowerFactory's load-flow balance already
    includes the converter copper loss in ``Pcu``; ``Rarm`` remains part of the
    internal series impedance and must not be counted a second time. The
    VeraGrid formulation evaluates
    ``alpha1 + alpha2 * I + alpha3 * I**2`` using AC current on the system
    power base, so every physical coefficient is normalized once during import.

    :param source: Native monopolar or bipolar converter.
    :param system_base_mva: VeraGrid system power base in MVA.
    :return: Idle, linear-current and quadratic-current loss coefficients.
    """
    if system_base_mva > 0.0:
        alpha1: float = float(source.Pnold) / (1000.0 * system_base_mva)
    else:
        alpha1 = 0.0

    nominal_voltage_kv: float = abs(float(source.Unom))
    switching_loss_factor: float = (
        0.0 if source.swtLossFactor is None else float(source.swtLossFactor)
    )
    resistive_loss_factor: float = (
        0.0 if source.resLossFactor is None else float(source.resLossFactor)
    )
    if nominal_voltage_kv > 0.0:
        # At three-phase AC base current Sbase/(sqrt(3)*Unom), kW/A becomes
        # a dimensionless linear loss and ohm becomes a quadratic p.u. loss.
        alpha2: float = switching_loss_factor / (
            math.sqrt(3.0) * nominal_voltage_kv
        )
        alpha3: float = (
            resistive_loss_factor
            * system_base_mva
            / (3.0 * nominal_voltage_kv * nominal_voltage_kv)
        )
    else:
        alpha2 = 0.0
        alpha3 = 0.0

    rated_power_mva: float = (
        0.0 if source.Snom is None else abs(float(source.Snom))
    )
    copper_loss_kw: float = (
        0.0 if source.Pcu is None else float(source.Pcu)
    )
    if rated_power_mva > 0.0 and system_base_mva > 0.0:
        # Pcu is measured at rated apparent current. Scaling its I² law onto
        # Sbase yields Pcu*Sbase/(1000*Snom²).
        alpha3 += (
            copper_loss_kw
            * system_base_mva
            / (1000.0 * rated_power_mva * rated_power_mva)
        )
    else:
        pass

    # The three-terminal positive-sequence MMC model sees the parallel arm
    # equivalent Rarm/2. PowerFactory includes that equivalent explicitly in
    # the ElmVsc load-flow loss balance.
    arm_resistance_ohm: float = (
        0.0 if source.Rarm is None else max(float(source.Rarm), 0.0)
    )
    arm_loss_ready: bool = (
        isinstance(source, ElmVsc)
        and nominal_voltage_kv > 0.0
        and system_base_mva > 0.0
        and arm_resistance_ohm > 0.0
    )
    if arm_loss_ready:
        alpha3 += (
            arm_resistance_ohm
            * system_base_mva
            / (2.0 * nominal_voltage_kv * nominal_voltage_kv)
        )
    else:
        pass

    return alpha1, alpha2, alpha3


def _get_powerfactory_vsc_series_impedance(
        source: ElmVsc | ElmVscmono,
        frequency_hz: float,
) -> Tuple[float, float]:
    """
    Convert the native converter-reactor short-circuit data to per unit.

    ``Pcu`` is the three-phase copper loss at rated current, hence
    ``Pcu[MW] / Snom[MVA]`` is the reactor resistance on the converter base.
    ``uk`` is the magnitude of the same impedance in percent. For a three-port
    MMC ``ElmVsc``, PowerFactory adds half the arm impedance to the series
    reactor. ``ElmVscmono`` already exposes the complete AC reactor through
    ``Pcu`` and ``uk``; its optional arm fields do not enter the modulation-to-
    AC-terminal equation. ``Rarm`` is exported in ohm and ``Larm`` in mH, so
    both are converted on the exact converter voltage/power base when used.

    :param source: Native monopolar or bipolar converter.
    :param frequency_hz: Network nominal frequency in Hz.
    :return: Reactor resistance and reactance on the converter power base.
    """
    rated_power_mva: float = (
        0.0 if source.Snom is None else abs(float(source.Snom))
    )
    copper_loss_kw: float = (
        0.0 if source.Pcu is None else max(float(source.Pcu), 0.0)
    )
    impedance_magnitude_pu: float = (
        0.0 if source.uk is None else max(float(source.uk) / 100.0, 0.0)
    )

    if rated_power_mva > 0.0:
        resistance_pu: float = copper_loss_kw / (1000.0 * rated_power_mva)
    else:
        resistance_pu = 0.0

    reactance_squared: float = max(
        impedance_magnitude_pu * impedance_magnitude_pu
        - resistance_pu * resistance_pu,
        0.0,
    )
    reactance_pu: float = math.sqrt(reactance_squared)

    # The arm parameters are defined only for MMC equipment. A positive arm
    # value is therefore the source-level evidence that the Zarm/2 term exists;
    # older DGS files omit both optional columns and retain the series term.
    arm_resistance_ohm: float = (
        0.0 if source.Rarm is None else max(float(source.Rarm), 0.0)
    )
    arm_inductance_mh: float = (
        0.0 if source.Larm is None else max(float(source.Larm), 0.0)
    )
    nominal_voltage_kv: float = abs(float(source.Unom))
    arm_impedance_ready: bool = (
        isinstance(source, ElmVsc)
        and rated_power_mva > 0.0
        and nominal_voltage_kv > 0.0
        and frequency_hz > 0.0
        and (arm_resistance_ohm > 0.0 or arm_inductance_mh > 0.0)
    )
    if arm_impedance_ready:
        impedance_base_ohm: float = (
            nominal_voltage_kv * nominal_voltage_kv / rated_power_mva
        )
        resistance_pu += arm_resistance_ohm / (2.0 * impedance_base_ohm)
        reactance_pu += (
            2.0
            * math.pi
            * frequency_hz
            * arm_inductance_mh
            * 1.0e-3
            / (2.0 * impedance_base_ohm)
        )
    else:
        pass
    return resistance_pu, reactance_pu


def convert_dgs_to_vsc(
        elmvsc: ElmVsc,
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        switch_by_cubic_id: Dict[str, StaSwitch],
        system_base_mva: float,
        frequency_hz: float,
        use_power_flow_snapshot: bool,
        logger: Logger,
) -> dev.VSC | None:
    """
    Convert one native three-terminal PowerFactory ``ElmVsc``.

    PowerFactory records the converter terminals through ``StaCubic.obj_bus``:
    ``0`` is AC, ``1`` is DC positive and ``2`` is DC negative. The imported
    object remains static; dynamic controls stay in the separate catalogue and
    association manifest until an explicit activation workflow is implemented.

    :param elmvsc: Source converter row.
    :param cubics_by_objid: Cubicles grouped by owning DGS object identifier.
    :param bus_by_term_id: Imported VeraGrid buses keyed by DGS terminal FID.
    :param switch_by_cubic_id: Cubicle switches keyed by DGS cubicle FID.
    :param system_base_mva: VeraGrid system base used to normalize losses.
    :param frequency_hz: Network nominal frequency in Hz.
    :param use_power_flow_snapshot: Whether solved DGS terminal powers are authoritative.
    :param logger: Import diagnostic sink.
    :return: Imported VSC, or ``None`` when its terminal topology is incomplete.
    """
    converter_id: str | None = _ref_id(elmvsc.ID)
    converter_cubics: List[StaCubic]
    buses_by_terminal_role: Dict[int, dev.Bus] = dict()
    cubic: StaCubic

    if converter_id is None or converter_id == "":
        converter_cubics = list()
    else:
        converter_cubics = cubics_by_objid.get(converter_id, list())

    # Resolve explicit roles rather than trusting row order; otherwise a missing
    # cubicle could silently turn an AC terminal into a DC terminal.
    for cubic in converter_cubics:
        terminal_id: str | None = _ref_id(cubic.fold_id)
        terminal_role: int = int(cubic.obj_bus)
        if terminal_id is None or terminal_id == "":
            pass
        else:
            terminal_bus: dev.Bus | None = bus_by_term_id.get(terminal_id, None)
            if terminal_bus is None:
                pass
            else:
                if terminal_role in buses_by_terminal_role:
                    logger.add_warning(
                        msg="Duplicate ElmVsc terminal role ignored",
                        device=elmvsc.loc_name,
                        device_class="ElmVsc",
                        value=f"obj_bus={terminal_role}",
                    )
                else:
                    buses_by_terminal_role[terminal_role] = terminal_bus

    ac_bus: dev.Bus | None = buses_by_terminal_role.get(0, None)
    dc_positive_bus: dev.Bus | None = buses_by_terminal_role.get(1, None)
    dc_negative_bus: dev.Bus | None = buses_by_terminal_role.get(2, None)
    if ac_bus is None or dc_positive_bus is None or dc_negative_bus is None:
        logger.add_warning(
            msg="ElmVsc skipped because AC/DC+/DC- cubicles are incomplete",
            device=elmvsc.loc_name,
            device_class="ElmVsc",
            value=str(sorted(buses_by_terminal_role)),
        )
        return None
    else:
        pass

    # Cubicle roles are authoritative because legacy DGS exports may encode all
    # three associated ElmTerm.systype values as zero.
    dc_positive_bus.is_dc = True
    dc_negative_bus.is_dc = True

    active_power_limit: float = abs(float(elmvsc.P_max))
    rated_power_mva: float = (
        0.0 if elmvsc.Snom is None else abs(float(elmvsc.Snom))
    )
    apparent_setpoint: float = math.hypot(float(elmvsc.psetp), float(elmvsc.qsetp))
    if active_power_limit > 0.0:
        converter_rate: float = max(
            active_power_limit,
            apparent_setpoint,
            rated_power_mva,
        )
    else:
        if apparent_setpoint > 0.0:
            converter_rate = apparent_setpoint
        else:
            converter_rate = 1.0

    converter_name: str = _get_non_empty_name(
        name=elmvsc.loc_name,
        default_value=f"VSC_{converter_id}",
    )
    converter_active: bool = (
        not bool(elmvsc.outserv)
        and _is_element_closed_by_cubicle_switches(
            element_id=elmvsc.ID,
            cubics_by_objid=cubics_by_objid,
            switch_by_cubic_id=switch_by_cubic_id,
        )
    )
    alpha1: float
    alpha2: float
    alpha3: float
    resistance_pu: float
    reactance_pu: float
    alpha1, alpha2, alpha3 = _get_powerfactory_vsc_loss_coefficients(
        source=elmvsc,
        system_base_mva=system_base_mva,
    )
    resistance_pu, reactance_pu = _get_powerfactory_vsc_series_impedance(
        source=elmvsc,
        frequency_hz=frequency_hz,
    )
    control1: ConverterControlType
    control1_value: float
    control2: ConverterControlType
    control2_value: float
    control1, control1_value, control2, control2_value = (
        _get_native_vsc_controls(
            source=elmvsc,
            ac_bus=ac_bus,
            dc_positive_bus=dc_positive_bus,
            dc_negative_bus=dc_negative_bus,
            use_power_flow_snapshot=use_power_flow_snapshot,
            logger=logger,
        )
    )
    # PowerFactory 2025 SP4 exposes ``NmmcSM`` although its technical
    # reference prints ``MmmcSM``. Accept the documented spelling as a legacy
    # alias so DGS files from other releases remain portable.
    if elmvsc.NmmcSM is None:
        if elmvsc.MmmcSM is None:
            mmc_submodules_per_arm: int = 0
        else:
            mmc_submodules_per_arm = int(elmvsc.MmmcSM)
    else:
        mmc_submodules_per_arm = int(elmvsc.NmmcSM)
    converter: dev.VSC = dev.VSC(
        name=converter_name,
        idtag=converter_id,
        code=elmvsc.for_name,
        active=converter_active,
        bus_from=dc_positive_bus,
        bus_to=ac_bus,
        bus_dc_n=dc_negative_bus,
        design_rate=converter_rate,
        rate=converter_rate,
        # PowerFactory exports Pnold in kW, while VeraGrid's IEC loss
        # polynomial is evaluated on the system p.u. power base.
        alpha1=alpha1,
        alpha2=alpha2,
        alpha3=alpha3,
        r_series=resistance_pu,
        x_series=reactance_pu,
        dc_voltage_base=(
            0.0 if elmvsc.Unomdc is None else float(elmvsc.Unomdc)
        ),
        mmc_submodule_capacitance_uf=(
            0.0 if elmvsc.mmcCmod is None else float(elmvsc.mmcCmod)
        ),
        mmc_submodules_per_arm=mmc_submodules_per_arm,
        mmc_consider_arm_reactor_dc=(
            False
            if elmvsc.iZarmDCside is None
            else bool(elmvsc.iZarmDCside)
        ),
        control1=control1,
        control2=control2,
        control1_val=control1_value,
        control2_val=control2_value,
    )
    return converter


def _get_native_vsc_controls(
        source: ElmVsc | ElmVscmono,
        ac_bus: dev.Bus,
        dc_positive_bus: dev.Bus,
        dc_negative_bus: dev.Bus | None,
        use_power_flow_snapshot: bool,
        logger: Logger,
) -> Tuple[ConverterControlType, float, ConverterControlType, float]:
    """Translate one native PowerFactory VSC control pair.

    PowerFactory documents ``i_acdc`` as the ordered selector
    ``Vac-phi, Vdc-phi, PWM-phi, Vdc-Q, P-Vac, P-Q, Vdc-Vac,
    P-cos(phi), Vdc-cos(phi)``. VeraGrid can represent the four voltage,
    active-power and reactive-power pairs directly. Unsupported angle, PWM and
    power-factor pairs remain explicit diagnostics instead of being guessed.

    :param source: Parsed monopolar or bipolar converter.
    :param ac_bus: Imported AC terminal.
    :param dc_positive_bus: Imported positive DC terminal.
    :param dc_negative_bus: Imported negative DC terminal, if present.
    :param use_power_flow_snapshot: Whether solved terminal powers are authoritative.
    :param logger: Import diagnostic sink.
    :return: Two VeraGrid control modes and their targets.
    """
    mode: int = int(source.i_acdc)
    configured_active_power: float = float(source.psetp)
    configured_reactive_power: float = float(source.qsetp)
    if use_power_flow_snapshot and source.m_p_busac is not None:
        # PowerFactory reports terminal injection into the AC bus. VeraGrid's
        # Pt variable is positive from that bus into the converter.
        active_power_target: float = -float(source.m_p_busac)
    else:
        active_power_target = configured_active_power
    if use_power_flow_snapshot and source.m_q_busac is not None:
        reactive_power_target: float = -float(source.m_q_busac)
    else:
        reactive_power_target = configured_reactive_power

    if use_power_flow_snapshot:
        if dc_negative_bus is None:
            dc_voltage_target: float = abs(float(dc_positive_bus.Vm0))
        else:
            dc_voltage_target = abs(
                float(dc_positive_bus.Vm0) - float(dc_negative_bus.Vm0)
            )
        ac_voltage_target: float = abs(float(ac_bus.Vm0))
    else:
        if source.usetpdc is None:
            dc_voltage_target = float(source.usetp)
        else:
            dc_voltage_target = float(source.usetpdc)
        ac_voltage_target = float(source.usetp)

    if mode == 3:
        control1: ConverterControlType = ConverterControlType.Vm_dc
        control1_value: float = dc_voltage_target
        control2: ConverterControlType = ConverterControlType.Qac
        control2_value: float = reactive_power_target
    elif mode == 4:
        control1 = ConverterControlType.Pac
        control1_value = active_power_target
        control2 = ConverterControlType.Vm_ac
        control2_value = ac_voltage_target
    elif mode == 5:
        control1 = ConverterControlType.Pac
        control1_value = active_power_target
        control2 = ConverterControlType.Qac
        control2_value = reactive_power_target
    elif mode == 6:
        control1 = ConverterControlType.Vm_dc
        control1_value = dc_voltage_target
        control2 = ConverterControlType.Vm_ac
        control2_value = ac_voltage_target
    else:
        # Preserve a solvable and inspectable converter shell, while making the
        # unsupported native pair impossible to mistake for an exact mapping.
        control1 = ConverterControlType.Pac
        control1_value = active_power_target
        control2 = ConverterControlType.Qac
        control2_value = reactive_power_target
        logger.add_warning(
            msg="Native VSC control pair is not represented exactly",
            device=source.loc_name,
            device_class=source.element_type,
            value=f"i_acdc={mode}",
        )

    return control1, control1_value, control2, control2_value


def convert_dgs_to_monopolar_vsc(
        source: ElmVscmono,
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        switch_by_cubic_id: Dict[str, StaSwitch],
        system_base_mva: float,
        frequency_hz: float,
        use_power_flow_snapshot: bool,
        logger: Logger,
) -> dev.VSC | None:
    """Convert one native two-terminal PowerFactory ``ElmVscmono``.

    :param source: Source monopolar converter row.
    :param cubics_by_objid: Cubicles grouped by owning DGS object identifier.
    :param bus_by_term_id: Imported buses keyed by DGS terminal FID.
    :param switch_by_cubic_id: Cubicle switches keyed by cubicle FID.
    :param system_base_mva: VeraGrid system base used to normalize losses.
    :param frequency_hz: Network nominal frequency in Hz.
    :param use_power_flow_snapshot: Whether solved DGS terminal powers are authoritative.
    :param logger: Import diagnostic sink.
    :return: Imported VSC, or ``None`` when its topology is incomplete.
    """
    source_id: str | None = _ref_id(source.ID)
    if source_id is None or source_id == "":
        source_cubics: List[StaCubic] = list()
    else:
        source_cubics = cubics_by_objid.get(source_id, list())

    buses_by_role: Dict[int, dev.Bus] = dict()
    cubic: StaCubic
    for cubic in source_cubics:
        terminal_id: str | None = _ref_id(cubic.fold_id)
        terminal_role: int = int(cubic.obj_bus)
        if terminal_id is None or terminal_id == "":
            pass
        else:
            terminal_bus: dev.Bus | None = bus_by_term_id.get(terminal_id, None)
            if terminal_bus is None:
                pass
            else:
                if terminal_role in buses_by_role:
                    logger.add_warning(
                        msg="Duplicate ElmVscmono terminal role ignored",
                        device=source.loc_name,
                        device_class="ElmVscmono",
                        value=f"obj_bus={terminal_role}",
                    )
                else:
                    buses_by_role[terminal_role] = terminal_bus
    else:
        pass

    ac_bus: dev.Bus | None = buses_by_role.get(0, None)
    dc_bus: dev.Bus | None = buses_by_role.get(1, None)
    if ac_bus is None or dc_bus is None:
        logger.add_warning(
            msg="ElmVscmono skipped because AC/DC cubicles are incomplete",
            device=source.loc_name,
            device_class="ElmVscmono",
            value=str(sorted(buses_by_role)),
        )
        converter: dev.VSC | None = None
    else:
        dc_bus.is_dc = True
        control1: ConverterControlType
        control1_value: float
        control2: ConverterControlType
        control2_value: float
        control1, control1_value, control2, control2_value = (
            _get_native_vsc_controls(
                source=source,
                ac_bus=ac_bus,
                dc_positive_bus=dc_bus,
                dc_negative_bus=None,
                use_power_flow_snapshot=use_power_flow_snapshot,
                logger=logger,
            )
        )
        converter_rate: float = max(
            abs(float(source.P_max)),
            0.0 if source.Snom is None else abs(float(source.Snom)),
            math.hypot(float(source.psetp), float(source.qsetp)),
            1.0,
        )
        alpha1: float
        alpha2: float
        alpha3: float
        resistance_pu: float
        reactance_pu: float
        alpha1, alpha2, alpha3 = _get_powerfactory_vsc_loss_coefficients(
            source=source,
            system_base_mva=system_base_mva,
        )
        resistance_pu, reactance_pu = _get_powerfactory_vsc_series_impedance(
            source=source,
            frequency_hz=frequency_hz,
        )
        converter_active: bool = (
            not bool(source.outserv)
            and _is_element_closed_by_cubicle_switches(
                element_id=source.ID,
                cubics_by_objid=cubics_by_objid,
                switch_by_cubic_id=switch_by_cubic_id,
            )
        )
        # Preserve the real 2025 SP4 selector and the spelling documented by
        # older PowerFactory references for portable monopolar DGS files.
        if source.NmmcSM is None:
            if source.MmmcSM is None:
                mmc_submodules_per_arm: int = 0
            else:
                mmc_submodules_per_arm = int(source.MmmcSM)
        else:
            mmc_submodules_per_arm = int(source.NmmcSM)
        converter = dev.VSC(
            name=_get_non_empty_name(
                name=source.loc_name,
                default_value=f"VSC_MONO_{source_id}",
            ),
            idtag=source_id,
            code=source.for_name,
            active=converter_active,
            bus_from=dc_bus,
            bus_to=ac_bus,
            bus_dc_n=None,
            design_rate=converter_rate,
            rate=converter_rate,
            alpha1=alpha1,
            alpha2=alpha2,
            alpha3=alpha3,
            r_series=resistance_pu,
            x_series=reactance_pu,
            dc_voltage_base=(
                0.0 if source.Unomdc is None else float(source.Unomdc)
            ),
            mmc_submodule_capacitance_uf=(
                0.0 if source.mmcCmod is None else float(source.mmcCmod)
            ),
            mmc_submodules_per_arm=mmc_submodules_per_arm,
            mmc_consider_arm_reactor_dc=(
                False
                if source.iZarmDCside is None
                else bool(source.iZarmDCside)
            ),
            control1=control1,
            control1_val=control1_value,
            control2=control2,
            control2_val=control2_value,
        )
    return converter


def _get_unique_composite_dsl_parameter(
        composite: ElmComp,
        dsl_by_id: Dict[str, ElmDsl],
        parameter_name: str,
        logger: Logger,
) -> float | None:
    """
    Resolve one unambiguous numeric parameter from direct composite children.

    PowerFactory stores the steady-state selector of a dynamically controlled
    converter in the same direct ``ElmDsl`` instance that owns the temporal
    controller.  Resolving the parameter through ``ElmComp.pelm`` keeps the
    association structural and avoids matching localized object names.

    :param composite: Composite model associated with one physical device.
    :param dsl_by_id: Dynamic DSL instances indexed by normalized DGS identity.
    :param parameter_name: Exact PowerFactory parameter name to resolve.
    :param logger: Import diagnostic sink.
    :return: Unique finite numeric value, or ``None`` when absent or ambiguous.
    """
    candidate_values: List[float] = list()
    child_pointer: str | None

    # Only direct children belong to this equipment-level initialization
    # contract. Nested controller internals are represented by their parent
    # ElmDsl and therefore must not be searched by display name.
    for child_pointer in composite.pelm:
        child_id: str | None = _ref_id(child_pointer)
        if child_id is None or child_id == "":
            pass
        else:
            child_dsl: ElmDsl | None = dsl_by_id.get(child_id, None)
            if child_dsl is None:
                pass
            else:
                parameter_index: int
                for parameter_index in range(len(child_dsl.parameter_names)):
                    current_name: str = child_dsl.parameter_names[parameter_index]
                    if current_name == parameter_name and parameter_index < len(child_dsl.params):
                        raw_value: float | str | None = child_dsl.params[parameter_index]
                        try:
                            numeric_value: float = float(raw_value)
                            if math.isfinite(numeric_value):
                                candidate_values.append(numeric_value)
                            else:
                                pass
                        except (TypeError, ValueError):
                            pass
                    else:
                        pass
                else:
                    pass
    else:
        pass

    if len(candidate_values) == 0:
        result: float | None = None
    else:
        first_value: float = candidate_values[0]
        values_are_equivalent: bool = True
        candidate_value: float
        for candidate_value in candidate_values:
            if math.isclose(candidate_value, first_value, rel_tol=0.0, abs_tol=1.0e-12):
                pass
            else:
                values_are_equivalent = False
        else:
            pass

        if values_are_equivalent:
            result = first_value
        else:
            logger.add_warning(
                msg="Ambiguous dynamic controller parameter ignored",
                device=composite.loc_name,
                device_class="ElmComp",
                value=f"{parameter_name}={candidate_values}",
            )
            result = None

    return result


def _get_unique_composite_dsl_sibling_parameter(
        composite: ElmComp,
        dsl_by_id: Dict[str, ElmDsl],
        anchor_parameter_name: str,
        parameter_name: str,
        logger: Logger,
) -> float | None:
    """Resolve a parameter from the DSL instance owning an anchor parameter.

    Generic PowerFactory frames often reuse names such as ``poc`` in several
    direct child blocks.  The block that owns the associated mode selector is
    the only authoritative source, so this resolver first identifies children
    containing the anchor and only then reads the sibling value.

    :param composite: Composite model associated with one physical device.
    :param dsl_by_id: Dynamic DSL instances indexed by normalized DGS identity.
    :param anchor_parameter_name: Parameter that identifies the owning block.
    :param parameter_name: Sibling parameter to resolve from that block.
    :param logger: Import diagnostic sink.
    :return: Unique finite numeric sibling value, or ``None`` when unresolved.
    """
    candidate_values: List[float] = list()
    child_pointer: str | None
    for child_pointer in composite.pelm:
        child_id: str | None = _ref_id(child_pointer)
        if child_id is None or child_id == "":
            pass
        else:
            child_dsl: ElmDsl | None = dsl_by_id.get(child_id, None)
            if child_dsl is None:
                pass
            else:
                owns_anchor: bool = anchor_parameter_name in child_dsl.parameter_names
                if owns_anchor:
                    parameter_index: int
                    for parameter_index in range(len(child_dsl.parameter_names)):
                        current_name: str = child_dsl.parameter_names[parameter_index]
                        if current_name == parameter_name and parameter_index < len(child_dsl.params):
                            raw_value: float | str | None = child_dsl.params[parameter_index]
                            try:
                                numeric_value: float = float(raw_value)
                                if math.isfinite(numeric_value):
                                    candidate_values.append(numeric_value)
                                else:
                                    pass
                            except (TypeError, ValueError):
                                pass
                        else:
                            pass
                    else:
                        pass
                else:
                    pass
    else:
        pass

    if len(candidate_values) == 0:
        result: float | None = None
    else:
        first_value: float = candidate_values[0]
        values_are_equivalent: bool = True
        candidate_value: float
        for candidate_value in candidate_values:
            if math.isclose(candidate_value, first_value, rel_tol=0.0, abs_tol=1.0e-12):
                pass
            else:
                values_are_equivalent = False
        else:
            pass

        if values_are_equivalent:
            result = first_value
        else:
            logger.add_warning(
                msg="Ambiguous dynamic controller sibling parameter ignored",
                device=composite.loc_name,
                device_class="ElmComp",
                value=(
                    f"{anchor_parameter_name}->{parameter_name}="
                    f"{candidate_values}"
                ),
            )
            result = None
    return result


def _get_vsc_vdc_control_target(
        converter: dev.VSC,
        composite: ElmComp,
        dsl_by_id: Dict[str, ElmDsl],
        use_power_flow_snapshot: bool,
        configured_voltage_target: float,
        logger: Logger,
) -> float:
    """
    Determine the native DC-voltage target for a monopolar or bipolar VSC.

    The NUACTIS-style DSL controller measures normalized bipolar voltage as
    half of ``Vdc+ - Vdc-``, while VeraGrid's ``Vm_dc`` equation uses the full
    signed pole-to-pole span.  A solved DGS snapshot is authoritative when
    present. Otherwise the controller's symmetric permissible interval gives
    its nominal normalized reference without requiring PowerFactory.

    :param converter: Imported three-terminal VeraGrid converter.
    :param composite: Source composite owning the controller.
    :param dsl_by_id: Dynamic DSL instances indexed by normalized DGS identity.
    :param use_power_flow_snapshot: Whether solved DGS terminal values were requested.
    :param configured_voltage_target: Native single-pole voltage target in p.u.
    :param logger: Import diagnostic sink.
    :return: Positive full pole-to-pole voltage target in p.u.
    """
    target: float | None = None
    negative_bus: dev.Bus | None = converter.bus_dc_n

    if use_power_flow_snapshot and converter.bus_from is not None:
        if negative_bus is None:
            snapshot_target: float = abs(float(converter.bus_from.Vm0))
        else:
            snapshot_target = abs(
                float(converter.bus_from.Vm0 - negative_bus.Vm0)
            )
        if math.isfinite(snapshot_target) and snapshot_target > 1.0e-9:
            target = snapshot_target
        else:
            pass
    else:
        pass

    if target is None and negative_bus is not None:
        minimum_voltage: float | None = _get_unique_composite_dsl_parameter(
            composite=composite,
            dsl_by_id=dsl_by_id,
            parameter_name="Vdc_min",
            logger=logger,
        )
        maximum_voltage: float | None = _get_unique_composite_dsl_parameter(
            composite=composite,
            dsl_by_id=dsl_by_id,
            parameter_name="Vdc_max",
            logger=logger,
        )
        if (
                minimum_voltage is not None
                and maximum_voltage is not None
                and minimum_voltage > 0.0
                and maximum_voltage > minimum_voltage
        ):
            # Twice the midpoint converts the normalized half-span reference
            # into VeraGrid's full bipolar voltage difference.
            target = minimum_voltage + maximum_voltage
        else:
            target = 2.0
            logger.add_warning(
                msg="Bipolar VSC dynamic voltage target defaulted",
                device=converter.name,
                device_class="VSC",
                value=target,
            )
    else:
        pass

    if target is None:
        target = float(configured_voltage_target)
    else:
        pass

    return target


def _resolve_unique_svs_interface_branch(
        circuit: dev.MultiCircuit,
        source_device_id: str,
        control_bus: dev.Bus,
) -> Tuple[BranchParent | None, ConverterControlBranchSide | None]:
    """Resolve a remote SVC's unique local AC interface.

    PowerFactory can apply ``ElmSvs`` droop to the grid-side flow of an
    interfacing transformer even when its equipment frame contains only a
    voltage meter.  In that contract the SVC injection bus has one energized
    AC exit, and the measured side is the terminal opposite the injection.
    Multiple exits are an aggregate boundary and deliberately fail closed.

    :param circuit: Imported VeraGrid circuit containing the physical SVC.
    :param source_device_id: Authoritative source ``ElmSvs`` FID.
    :param control_bus: Resolved remote voltage-control bus.
    :return: Unique interface branch and its grid-side terminal, or two
             ``None`` values when the topology is ambiguous.
    """
    injection_bus: dev.Bus | None = None
    runtime_shunt: dev.ControllableShunt
    for runtime_shunt in circuit.get_controllable_shunts():
        if str(runtime_shunt.idtag) == source_device_id:
            injection_bus = runtime_shunt.bus
        else:
            pass
    else:
        pass

    candidates: List[Tuple[BranchParent, ConverterControlBranchSide]] = list()
    if injection_bus is None or injection_bus is control_bus:
        pass
    else:
        runtime_branch: BranchParent
        for runtime_branch in circuit.get_branches_iter(
            add_vsc=False,
            add_hvdc=False,
            add_switch=True,
        ):
            branch_is_eligible: bool = bool(
                runtime_branch.active
                and runtime_branch.bus_from is not None
                and runtime_branch.bus_to is not None
                and not runtime_branch.bus_from.is_dc
                and not runtime_branch.bus_to.is_dc
            )
            if branch_is_eligible and runtime_branch.bus_from is injection_bus:
                candidates.append((
                    runtime_branch,
                    ConverterControlBranchSide.ToSide,
                ))
            else:
                if branch_is_eligible and runtime_branch.bus_to is injection_bus:
                    candidates.append((
                        runtime_branch,
                        ConverterControlBranchSide.FromSide,
                    ))
                else:
                    pass
        else:
            pass

    if len(candidates) == 1:
        result: Tuple[BranchParent | None, ConverterControlBranchSide | None] = (
            candidates[0]
        )
    else:
        result = (None, None)
    return result


def _resolve_composite_remote_ac_branch(
        dgs_circuit: DgsCircuit,
        circuit: dev.MultiCircuit,
        composite: ElmComp,
        source_device_id: str,
        logger: Logger,
        control_bus: dev.Bus | None = None,
        inference_mode: DgsCompositeBranchInference = (
            DgsCompositeBranchInference.UniqueTopology
        ),
) -> Tuple[BranchParent | None, ConverterControlBranchSide | None]:
    """Resolve a composite's unique non-local AC current measurement branch.

    PowerFactory equipment frames can expose PoC P/Q either through one direct
    ``StaPqmea`` or through paired voltage/current phasors. In both forms the
    measurement cubicle is authoritative: its object FID identifies the
    physical branch and ``obj_bus`` identifies the measured terminal.  An SVC
    frame may instead contain one direct interface transformer; its terminal
    connected to ``cpCtrlNode`` is then the same physical boundary. Duplicate
    candidates are deduplicated, while genuinely different candidates fail
    closed because they represent an aggregate equation.

    :param dgs_circuit: Parsed DGS source network and composite associations.
    :param circuit: Imported VeraGrid circuit containing physical branches.
    :param composite: Converter-owning PowerFactory composite instance.
    :param source_device_id: Authoritative source equipment FID to exclude locally.
    :param logger: Import diagnostic sink.
    :param control_bus: Optional resolved voltage-control bus used to orient a
                        direct interface transformer.
    :param inference_mode: Strongest admissible non-meter branch evidence.
    :return: Unique physical AC branch and measured terminal, or two ``None`` values.
    """
    current_meter_by_id: Dict[str, StaImea] = dict()
    power_meter_by_id: Dict[str, StaPqmea] = dict()
    source_meter: StaImea
    source_power_meter: StaPqmea
    for source_meter in dgs_circuit.staimeas:
        current_meter_by_id[str(source_meter.ID)] = source_meter
    else:
        pass

    for source_power_meter in dgs_circuit.stapqmeas:
        power_meter_by_id[str(source_power_meter.ID)] = source_power_meter
    else:
        pass

    cubicle_by_id: Dict[str, StaCubic] = dict()
    source_cubicle: StaCubic
    for source_cubicle in dgs_circuit.stacubics:
        cubicle_by_id[str(source_cubicle.ID)] = source_cubicle
    else:
        pass

    runtime_branch_by_id: Dict[str, BranchParent] = dict()
    runtime_branch: BranchParent
    for runtime_branch in circuit.get_branches_iter(
        add_vsc=False,
        add_hvdc=False,
        add_switch=True,
    ):
        if (
                runtime_branch.bus_from is not None
                and runtime_branch.bus_to is not None
                and not runtime_branch.bus_from.is_dc
                and not runtime_branch.bus_to.is_dc
        ):
            runtime_branch_by_id[str(runtime_branch.idtag)] = runtime_branch
        else:
            pass
    else:
        pass

    candidates: Dict[Tuple[str, int], Tuple[BranchParent, ConverterControlBranchSide]] = dict()
    entry: ElmCompInstanceEntry
    for entry in extract_elmcomp_direct_instances(
        circuit=dgs_circuit,
        root_element=composite,
    ):
        if entry.element_id is None:
            pass
        else:
            candidate_meter: StaImea | None = current_meter_by_id.get(entry.element_id, None)
            candidate_power_meter: StaPqmea | None = power_meter_by_id.get(
                entry.element_id,
                None,
            )
            if candidate_meter is not None and candidate_meter.outserv == 0:
                candidate_cubicle_id: str | None = str(candidate_meter.pcubic)
            else:
                if candidate_power_meter is not None and candidate_power_meter.outserv == 0:
                    candidate_cubicle_id = str(candidate_power_meter.pcubic)
                else:
                    candidate_cubicle_id = None
            if candidate_cubicle_id is None or candidate_cubicle_id == "":
                pass
            else:
                candidate_cubicle: StaCubic | None = cubicle_by_id.get(
                    candidate_cubicle_id,
                    None,
                )
                if candidate_cubicle is None or str(candidate_cubicle.obj_id) == source_device_id:
                    pass
                else:
                    candidate_branch: BranchParent | None = runtime_branch_by_id.get(
                        str(candidate_cubicle.obj_id),
                        None,
                    )
                    source_terminal_index: int = int(candidate_cubicle.obj_bus)
                    if candidate_branch is None or source_terminal_index not in (0, 1):
                        pass
                    else:
                        if source_terminal_index == 0:
                            measured_side: ConverterControlBranchSide = (
                                ConverterControlBranchSide.FromSide
                            )
                        else:
                            measured_side = ConverterControlBranchSide.ToSide
                        candidates[(str(candidate_branch.idtag), source_terminal_index)] = (
                            candidate_branch,
                            measured_side,
                        )
    else:
        pass

    has_direct_composite_branch_reference: bool = False
    if (
            len(candidates) == 0
            and control_bus is not None
            and inference_mode in (
                DgsCompositeBranchInference.DirectCompositeBranch,
                DgsCompositeBranchInference.UniqueTopology,
            )
    ):
        # Some equipment frames expose their unique interface transformer
        # directly rather than through StaPqmea.  Match the exact DGS branch
        # FID and orient it from the exported cpCtrlNode association.
        for entry in extract_elmcomp_direct_instances(
            circuit=dgs_circuit,
            root_element=composite,
        ):
            if entry.element_id is None or entry.element_id == source_device_id:
                pass
            else:
                direct_branch: BranchParent | None = runtime_branch_by_id.get(
                    entry.element_id,
                    None,
                )
                if direct_branch is None:
                    pass
                else:
                    has_direct_composite_branch_reference = True
                    if direct_branch.bus_from is control_bus:
                        direct_side: ConverterControlBranchSide = (
                            ConverterControlBranchSide.FromSide
                        )
                        candidates[(str(direct_branch.idtag), 0)] = (
                            direct_branch,
                            direct_side,
                        )
                    else:
                        if direct_branch.bus_to is control_bus:
                            direct_side = ConverterControlBranchSide.ToSide
                            candidates[(str(direct_branch.idtag), 1)] = (
                                direct_branch,
                                direct_side,
                            )
                        else:
                            pass
        else:
            pass
    else:
        pass

    if (
            len(candidates) == 0
            and control_bus is not None
            and inference_mode is DgsCompositeBranchInference.UniqueTopology
            and not has_direct_composite_branch_reference
    ):
        inferred_branch: BranchParent | None
        inferred_side: ConverterControlBranchSide | None
        inferred_branch, inferred_side = _resolve_unique_svs_interface_branch(
            circuit=circuit,
            source_device_id=source_device_id,
            control_bus=control_bus,
        )
        if inferred_branch is None or inferred_side is None:
            pass
        else:
            inferred_terminal_index: int
            if inferred_side is ConverterControlBranchSide.FromSide:
                inferred_terminal_index = 0
            else:
                inferred_terminal_index = 1
            candidates[(str(inferred_branch.idtag), inferred_terminal_index)] = (
                inferred_branch,
                inferred_side,
            )
    else:
        pass

    if len(candidates) == 1:
        remote_branch: BranchParent
        remote_side: ConverterControlBranchSide
        remote_branch, remote_side = next(iter(candidates.values()))
        return remote_branch, remote_side
    else:
        if len(candidates) > 1:
            logger.add_warning(
                msg="Dynamic equipment remote P/Q control has multiple measured AC branches",
                device=composite.loc_name,
                device_class="ElmComp",
                value=len(candidates),
            )
        else:
            pass
        return None, None


def _apply_composite_pq_measurement_vsc_controls(
        dgs_circuit: DgsCircuit,
        circuit: dev.MultiCircuit,
        use_power_flow_snapshot: bool,
        logger: Logger,
) -> int:
    """Project native P-Q converter measurements onto physical branch controls.

    A PowerFactory converter in native P-Q mode may place its controller's
    ``StaPqmea`` on the grid side of an interfacing transformer. In that case
    ``psetp`` and ``qsetp`` constrain the measured branch terminal, not the
    converter terminal behind transformer losses. The exact composite ``pelm``
    and cubicle FIDs provide this contract without using solved DGS results.

    :param dgs_circuit: Parsed DGS network and composite instances.
    :param circuit: Imported VeraGrid network containing VSCs and AC branches.
    :param use_power_flow_snapshot: Whether solved local terminal powers are authoritative.
    :param logger: Import diagnostic sink.
    :return: Number of native P-Q converters assigned to a measured AC branch.
    """
    composite_by_id: Dict[str, ElmComp] = dict()
    runtime_vsc_by_id: Dict[str, dev.VSC] = dict()
    source_composite: ElmComp
    runtime_vsc: dev.VSC
    for source_composite in dgs_circuit.elmcomps:
        source_composite_id: str | None = _ref_id(source_composite.ID)
        if source_composite_id is None or source_composite_id == "":
            pass
        else:
            composite_by_id[source_composite_id] = source_composite
    else:
        pass
    for runtime_vsc in circuit.get_vsc():
        runtime_vsc_id: str | None = _ref_id(runtime_vsc.idtag)
        if runtime_vsc_id is None or runtime_vsc_id == "":
            pass
        else:
            runtime_vsc_by_id[runtime_vsc_id] = runtime_vsc
    else:
        pass

    updated_count: int = 0
    source_lists: List[List[ElmVsc] | List[ElmVscmono]] = list()
    source_lists.append(dgs_circuit.elmvscs)
    source_lists.append(dgs_circuit.elmvscmonos)
    source_list: List[ElmVsc] | List[ElmVscmono]
    source_vsc: ElmVsc | ElmVscmono
    for source_list in source_lists:
        for source_vsc in source_list:
            source_vsc_id: str | None = _ref_id(source_vsc.ID)
            composite_id: str | None = _ref_id(source_vsc.c_pmod)
            native_control_mode: int = int(source_vsc.i_acdc)
            if (
                    use_power_flow_snapshot
                    or source_vsc_id is None
                    or source_vsc_id == ""
                    or composite_id is None
                    or composite_id == ""
                    or native_control_mode != 5
            ):
                pass
            else:
                matched_runtime_vsc: dev.VSC | None = runtime_vsc_by_id.get(
                    source_vsc_id,
                    None,
                )
                matched_composite: ElmComp | None = composite_by_id.get(composite_id, None)
                if matched_runtime_vsc is None or matched_composite is None:
                    pass
                else:
                    remote_branch: BranchParent | None
                    remote_side: ConverterControlBranchSide | None
                    remote_branch, remote_side = _resolve_composite_remote_ac_branch(
                        dgs_circuit=dgs_circuit,
                        circuit=circuit,
                        composite=matched_composite,
                        source_device_id=source_vsc_id,
                        logger=logger,
                        inference_mode=DgsCompositeBranchInference.UniqueTopology,
                    )
                    if remote_branch is None or remote_side is None:
                        pass
                    else:
                        # P-Q mode applies both setpoints at the same exact
                        # measurement point. The solver then derives local VSC
                        # power required to cover intervening branch losses.
                        matched_runtime_vsc.control1_dev = remote_branch
                        matched_runtime_vsc.control1_branch_side = remote_side
                        matched_runtime_vsc.control2_dev = remote_branch
                        matched_runtime_vsc.control2_branch_side = remote_side
                        updated_count += 1
        else:
            pass
    else:
        pass
    return updated_count


def _resolve_explicit_ac_measurement_branch(
        dgs_circuit: DgsCircuit,
        circuit: dev.MultiCircuit,
        measurement_cubic_id: str | None,
        source_device_id: str,
        source_device_name: str,
        logger: Logger,
) -> Tuple[BranchParent | None, ConverterControlBranchSide | None]:
    """Resolve one explicitly exported reactive measurement cubicle.

    :param dgs_circuit: Parsed DGS source containing the cubicle.
    :param circuit: Imported VeraGrid circuit containing the measured branch.
    :param measurement_cubic_id: Exported ``ElmSvs.p_cub`` identifier.
    :param source_device_id: Source SVC FID, excluded as a branch candidate.
    :param source_device_name: Human-readable SVC name for diagnostics.
    :param logger: Import diagnostic sink.
    :return: Measured AC branch and terminal side, or two ``None`` values.
    """
    source_cubic: StaCubic | None = None
    candidate_cubic: StaCubic
    if measurement_cubic_id is None or measurement_cubic_id == "":
        pass
    else:
        # Resolve by stable DGS identity; names are never sufficient for a
        # control equation because duplicate equipment names are legal.
        for candidate_cubic in dgs_circuit.stacubics:
            if str(candidate_cubic.ID) == measurement_cubic_id:
                source_cubic = candidate_cubic
            else:
                pass
        else:
            pass

    if source_cubic is None or str(source_cubic.obj_id) == source_device_id:
        result_branch: BranchParent | None = None
        result_side: ConverterControlBranchSide | None = None
    else:
        result_branch = None
        runtime_branch: BranchParent
        for runtime_branch in circuit.get_branches_iter(
            add_vsc=False,
            add_hvdc=False,
            add_switch=True,
        ):
            if str(runtime_branch.idtag) == str(source_cubic.obj_id):
                result_branch = runtime_branch
            else:
                pass
        else:
            pass

        source_terminal_index: int = int(source_cubic.obj_bus)
        if result_branch is not None and source_terminal_index == 0:
            result_side = ConverterControlBranchSide.FromSide
        else:
            if result_branch is not None and source_terminal_index == 1:
                result_side = ConverterControlBranchSide.ToSide
            else:
                result_branch = None
                result_side = None

    if measurement_cubic_id is not None and result_branch is None:
        logger.add_warning(
            msg="ElmSvs reactive measurement cubicle could not be resolved",
            device=source_device_name,
            device_class="ElmSvs",
            value=measurement_cubic_id,
        )
    else:
        pass
    return result_branch, result_side


def _apply_composite_q_measurement_svs_controls(
        dgs_circuit: DgsCircuit,
        circuit: dev.MultiCircuit,
        use_power_flow_snapshot: bool,
        logger: Logger,
) -> int:
    """Project native ElmSvs droop onto its measured boundary branch.

    A populated ``p_cub`` is the authoritative reactive-power measurement
    point.  Some equipment frames instead expose the same physical boundary
    through one unambiguous ``StaPqmea`` or ``StaImea`` while ``p_cub`` remains
    empty; this is required when the SVC compensates filters behind its
    transformer.  A physical transformer slot alone is not a measurement and
    must not replace the native SVC-output Q used by ordinary remote Q/V droop.

    :param dgs_circuit: Parsed DGS network and composite instances.
    :param circuit: Imported VeraGrid network containing SVCs and AC branches.
    :param use_power_flow_snapshot: Whether solved local terminal powers are authoritative.
    :param logger: Import diagnostic sink.
    :return: Number of native SVCs assigned to a measured AC branch.
    """
    composite_by_id: Dict[str, ElmComp] = dict()
    runtime_shunt_by_id: Dict[str, dev.ControllableShunt] = dict()
    source_composite: ElmComp
    runtime_shunt: dev.ControllableShunt
    for source_composite in dgs_circuit.elmcomps:
        source_composite_id: str | None = _ref_id(source_composite.ID)
        if source_composite_id is None or source_composite_id == "":
            pass
        else:
            composite_by_id[source_composite_id] = source_composite
    else:
        pass

    for runtime_shunt in circuit.controllable_shunts:
        runtime_shunt_id: str | None = _ref_id(runtime_shunt.idtag)
        if runtime_shunt_id is None or runtime_shunt_id == "":
            pass
        else:
            runtime_shunt_by_id[runtime_shunt_id] = runtime_shunt
    else:
        pass

    updated_count: int = 0
    source_svs: ElmSvs
    for source_svs in dgs_circuit.elmsvss:
        source_svs_id: str | None = _ref_id(source_svs.ID)
        composite_id: str | None = _ref_id(source_svs.c_pmod)
        explicit_measurement_id: str | None = _ref_id(source_svs.p_cub)
        valid_native_droop: bool = (
            int(source_svs.outserv) == 0
            and int(source_svs.i_droop) != 0
            and float(source_svs.ddroop) > 0.0
            and float(source_svs.Srated) != 0.0
        )
        valid_native_reactive_control: bool = (
            int(source_svs.outserv) == 0
            and int(source_svs.i_ctrl) == 2
        )
        if (
                use_power_flow_snapshot
                or source_svs_id is None
                or source_svs_id == ""
                or not (valid_native_droop or valid_native_reactive_control)
        ):
            pass
        else:
            matched_runtime_shunt: dev.ControllableShunt | None = (
                runtime_shunt_by_id.get(source_svs_id, None)
            )
            if (
                    matched_runtime_shunt is None
                    or matched_runtime_shunt.control_mode not in (
                        ShuntControlMode.QVDroop,
                        ShuntControlMode.ReactivePower,
                    )
            ):
                pass
            else:
                remote_branch: BranchParent | None
                remote_side: ConverterControlBranchSide | None
                if explicit_measurement_id is not None and explicit_measurement_id != "":
                    remote_branch, remote_side = _resolve_explicit_ac_measurement_branch(
                        dgs_circuit=dgs_circuit,
                        circuit=circuit,
                        measurement_cubic_id=explicit_measurement_id,
                        source_device_id=source_svs_id,
                        source_device_name=source_svs.loc_name,
                        logger=logger,
                    )
                else:
                    matched_composite: ElmComp | None = composite_by_id.get(
                        composite_id,
                        None,
                    )
                    if matched_composite is None:
                        remote_branch = None
                        remote_side = None
                    else:
                        remote_branch, remote_side = _resolve_composite_remote_ac_branch(
                            dgs_circuit=dgs_circuit,
                            circuit=circuit,
                            composite=matched_composite,
                            source_device_id=source_svs_id,
                            logger=logger,
                            control_bus=matched_runtime_shunt.control_bus,
                            inference_mode=(
                                DgsCompositeBranchInference.UniqueTopology
                            ),
                        )
                if remote_branch is None or remote_side is None:
                    pass
                else:
                    matched_runtime_shunt.control_branch = remote_branch
                    matched_runtime_shunt.control_branch_side = remote_side
                    updated_count += 1
    else:
        pass
    return updated_count


def _apply_dynamic_vsc_steady_state_controls(
        dgs_circuit: DgsCircuit,
        circuit: dev.MultiCircuit,
        use_power_flow_snapshot: bool,
        logger: Logger,
) -> int:
    """
    Project exact DSL mode selectors onto physical VSC load-flow controls.

    Dynamic models remain separate catalogue objects. This projection only
    supplies the steady-state equations that PowerFactory selects from those
    models before temporal initialization, ensuring that the static solution
    feeding RMS represents the same physical operating mode.

    :param dgs_circuit: Parsed source DGS including composite and DSL instances.
    :param circuit: Imported VeraGrid circuit to configure.
    :param use_power_flow_snapshot: Whether solved DGS terminal values were requested.
    :param logger: Import diagnostic sink.
    :return: Number of converters whose control contract was updated.
    """
    composite_by_id: Dict[str, ElmComp] = dict()
    dsl_by_id: Dict[str, ElmDsl] = dict()
    source_vsc_by_id: Dict[str, ElmVsc | ElmVscmono] = dict()
    runtime_vsc_by_id: Dict[str, dev.VSC] = dict()
    source_composite: ElmComp
    source_dsl: ElmDsl
    source_vsc: ElmVsc | ElmVscmono
    runtime_vsc: dev.VSC

    # Build typed identity indexes once so every physical converter is matched
    # by DGS FID, never by a localized or user-editable display name.
    for source_composite in dgs_circuit.elmcomps:
        composite_id: str | None = _ref_id(source_composite.ID)
        if composite_id is None or composite_id == "":
            pass
        else:
            composite_by_id[composite_id] = source_composite
    else:
        pass

    for source_dsl in dgs_circuit.elmdsls:
        dsl_id: str | None = _ref_id(source_dsl.ID)
        if dsl_id is None or dsl_id == "":
            pass
        else:
            dsl_by_id[dsl_id] = source_dsl
    else:
        pass

    for source_vsc in dgs_circuit.elmvscs:
        source_vsc_id: str | None = _ref_id(source_vsc.ID)
        if source_vsc_id is None or source_vsc_id == "":
            pass
        else:
            source_vsc_by_id[source_vsc_id] = source_vsc
    else:
        pass

    for source_vsc in dgs_circuit.elmvscmonos:
        source_vsc_id = _ref_id(source_vsc.ID)
        if source_vsc_id is None or source_vsc_id == "":
            pass
        else:
            source_vsc_by_id[source_vsc_id] = source_vsc
    else:
        pass

    for runtime_vsc in circuit.get_vsc():
        runtime_vsc_id: str | None = _ref_id(runtime_vsc.idtag)
        if runtime_vsc_id is None or runtime_vsc_id == "":
            pass
        else:
            runtime_vsc_by_id[runtime_vsc_id] = runtime_vsc
    else:
        pass

    updated_count: int = 0
    source_vsc_id: str
    for source_vsc_id, source_vsc in source_vsc_by_id.items():
        runtime_vsc = runtime_vsc_by_id.get(source_vsc_id, None)
        composite_id: str | None = _ref_id(source_vsc.c_pmod)
        if runtime_vsc is None or composite_id is None or composite_id == "":
            pass
        else:
            source_composite = composite_by_id.get(composite_id, None)
            if source_composite is None:
                pass
            else:
                active_mode: float | None = _get_unique_composite_dsl_parameter(
                    composite=source_composite,
                    dsl_by_id=dsl_by_id,
                    parameter_name="Mode_P",
                    logger=logger,
                )
                reactive_mode: float | None = _get_unique_composite_dsl_parameter(
                    composite=source_composite,
                    dsl_by_id=dsl_by_id,
                    parameter_name="Mode_Q",
                    logger=logger,
                )
                changed: bool = False

                # PowerFactory's generic P/Vdc contract defines precisely two
                # modes: zero regulates bipolar Vdc and one regulates AC power.
                if active_mode is None:
                    pass
                else:
                    if active_mode < 0.5:
                        runtime_vsc.control1 = ConverterControlType.Vm_dc
                        runtime_vsc.control1_val = _get_vsc_vdc_control_target(
                            converter=runtime_vsc,
                            composite=source_composite,
                            dsl_by_id=dsl_by_id,
                            use_power_flow_snapshot=use_power_flow_snapshot,
                            configured_voltage_target=(
                                float(source_vsc.usetp)
                                if source_vsc.usetpdc is None
                                else float(source_vsc.usetpdc)
                            ),
                            logger=logger,
                        )
                        changed = True
                    else:
                        if active_mode < 1.5:
                            runtime_vsc.control1 = ConverterControlType.Pac
                            remote_active_mode: float | None = (
                                _get_unique_composite_dsl_sibling_parameter(
                                    composite=source_composite,
                                    dsl_by_id=dsl_by_id,
                                    anchor_parameter_name="Mode_P",
                                    parameter_name="poc",
                                    logger=logger,
                                )
                            )
                            if remote_active_mode is not None and remote_active_mode >= 0.5:
                                remote_active_branch: BranchParent | None
                                remote_active_branch_side: ConverterControlBranchSide | None
                                remote_active_branch, remote_active_branch_side = (
                                    _resolve_composite_remote_ac_branch(
                                        dgs_circuit=dgs_circuit,
                                        circuit=circuit,
                                        composite=source_composite,
                                        source_device_id=source_vsc_id,
                                        logger=logger,
                                    )
                                )
                                if (
                                        remote_active_branch is None
                                        or remote_active_branch_side is None
                                ):
                                    logger.add_warning(
                                        msg="Dynamic VSC remote P control could not resolve one AC branch",
                                        device=runtime_vsc.name,
                                        device_class="VSC",
                                        value=remote_active_mode,
                                    )
                                else:
                                    runtime_vsc.control1_dev = remote_active_branch
                                    runtime_vsc.control1_branch_side = remote_active_branch_side
                                # psetp is the control target at the selected
                                # PoC and is independent of a solved snapshot.
                                runtime_vsc.control1_val = float(source_vsc.psetp)
                            else:
                                runtime_vsc.control1_dev = None
                                if (
                                        use_power_flow_snapshot
                                        and source_vsc.m_p_busac is not None
                                ):
                                    # PF reports injection into the AC bus,
                                    # while VeraGrid uses bus-to-VSC power.
                                    runtime_vsc.control1_val = -float(
                                        source_vsc.m_p_busac
                                    )
                                else:
                                    runtime_vsc.control1_val = float(source_vsc.psetp)
                            changed = True
                        else:
                            logger.add_warning(
                                msg="Unsupported dynamic VSC active-power mode retained",
                                device=runtime_vsc.name,
                                device_class="VSC",
                                value=active_mode,
                            )

                # The generic Q/Vac contract uses zero for voltage, one for Q
                # and two for power factor. Remote Q follows the composite's
                # exact measurement cubicle instead of copying a solved result.
                if reactive_mode is None:
                    pass
                else:
                    if reactive_mode < 0.5:
                        remote_voltage_mode: float | None = (
                            _get_unique_composite_dsl_parameter(
                                composite=source_composite,
                                dsl_by_id=dsl_by_id,
                                parameter_name="poc_Vac",
                                logger=logger,
                            )
                        )
                        if remote_voltage_mode is None or remote_voltage_mode < 0.5:
                            runtime_vsc.control2 = ConverterControlType.Vm_ac
                            runtime_vsc.control2_dev = runtime_vsc.bus_to
                            runtime_vsc.control2_val = float(source_vsc.usetp)
                            changed = True
                        else:
                            logger.add_warning(
                                msg="Remote dynamic VSC voltage control needs an exact PoC target",
                                device=runtime_vsc.name,
                                device_class="VSC",
                                value=remote_voltage_mode,
                            )
                    else:
                        if reactive_mode < 1.5:
                            runtime_vsc.control2 = ConverterControlType.Qac
                            remote_reactive_mode: float | None = (
                                _get_unique_composite_dsl_parameter(
                                    composite=source_composite,
                                    dsl_by_id=dsl_by_id,
                                    parameter_name="poc_Q",
                                    logger=logger,
                                )
                            )
                            if remote_reactive_mode is not None and remote_reactive_mode >= 0.5:
                                remote_branch: BranchParent | None
                                remote_branch_side: ConverterControlBranchSide | None
                                remote_branch, remote_branch_side = (
                                    _resolve_composite_remote_ac_branch(
                                        dgs_circuit=dgs_circuit,
                                        circuit=circuit,
                                        composite=source_composite,
                                        source_device_id=source_vsc_id,
                                        logger=logger,
                                    )
                                )
                                if remote_branch is None or remote_branch_side is None:
                                    logger.add_warning(
                                        msg="Dynamic VSC remote Q control could not resolve one AC branch",
                                        device=runtime_vsc.name,
                                        device_class="VSC",
                                        value=remote_reactive_mode,
                                    )
                                else:
                                    runtime_vsc.control2_dev = remote_branch
                                    runtime_vsc.control2_branch_side = remote_branch_side
                                    # qsetp is the unsolved DGS load-flow target;
                                    # measured terminal Q is only a validation result.
                                    runtime_vsc.control2_val = float(source_vsc.qsetp)
                            else:
                                runtime_vsc.control2_dev = None
                                if (
                                        use_power_flow_snapshot
                                        and source_vsc.m_q_busac is not None
                                ):
                                    # Keep the same terminal orientation as Pac.
                                    runtime_vsc.control2_val = -float(
                                        source_vsc.m_q_busac
                                    )
                                else:
                                    runtime_vsc.control2_val = float(source_vsc.qsetp)
                            changed = True
                        else:
                            logger.add_warning(
                                msg="Dynamic VSC power-factor control retained as fixed Q",
                                device=runtime_vsc.name,
                                device_class="VSC",
                                value=reactive_mode,
                            )

                if changed:
                    updated_count += 1
                else:
                    pass
    else:
        pass

    return updated_count


def convert_dgs_staticgen_to_vsc(elmgenstat: ElmGenstat,
                                 stacubic_dict: Dict[str, List[int]],
                                 buses: List[dev.Bus],
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus],
                                 parallel_index: int = 0,
                                 parallel_count: int = 1,
                                 use_power_flow_snapshot: bool = False) -> Tuple[dev.Bus, dev.VSC]:
    """
    Convert dgs staticgen to vsc.

    :param elmgenstat: elmgenstat parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """
    ac_bus = get_injection_bus(elm_id=elmgenstat.ID,
                               stacubic_dict=stacubic_dict,
                               buses=buses,
                               cubics_by_objid=cubics_by_objid,
                               bus_by_term_id=bus_by_term_id)

    dc_bus = dev.Bus(name=f'{_ref_id(ac_bus.name)}_DC',
                     is_dc=True,
                     is_slack=True,
                     xpos=ac_bus.x,
                     ypos=ac_bus.y - 200, )

    vsc_name = _get_non_empty_name(elmgenstat.loc_name, f"VSC_{_ref_id(elmgenstat.ID)}")
    vsc_name = _get_parallel_device_name(vsc_name, parallel_index, parallel_count)
    vsc_idtag = _get_parallel_device_idtag(_ref_id(elmgenstat.ID), parallel_index, parallel_count)
    minimum_reactive_power_mvar: float
    maximum_reactive_power_mvar: float
    minimum_reactive_power_mvar, maximum_reactive_power_mvar = _get_elmgenstat_reactive_limits(
        elmgenstat=elmgenstat,
        parallel_count=parallel_count,
        use_calculated_results=use_power_flow_snapshot,
    )

    if elmgenstat.av_mode == 'vdroop':
        vsc = dev.VSC(
            name=vsc_name,
            idtag=vsc_idtag,
            active=not bool(elmgenstat.outserv),
            bus_from=dc_bus,
            bus_to=ac_bus,
            rate=float(elmgenstat.sgn),
            alpha1=0.0,
            alpha2=0.0,
            alpha3=0.0,
            control1=ConverterControlType.Pac,
            control2=ConverterControlType.Q_droop,
            control1_val=-1.0 * float(elmgenstat.pgini),
            control2_val=-1.0 * float(elmgenstat.qgini),
            fault_control=ConverterFaultControlType.WECC_WT_Type_4B,
            control2_droop=float(elmgenstat.ddroop),
            control2_droop_val_min=float(elmgenstat.usp_min),
            control2_droop_val_max=float(elmgenstat.usp_max),
            control2_droop_val=float(elmgenstat.usetp),
            control2_val_min=minimum_reactive_power_mvar,
            control2_val_max=maximum_reactive_power_mvar
        )

    elif elmgenstat.av_mode == 'constq':
        vsc = dev.VSC(
            name=vsc_name,
            idtag=vsc_idtag,
            active=not bool(elmgenstat.outserv),
            bus_from=dc_bus,
            bus_to=ac_bus,
            rate=float(elmgenstat.sgn),
            alpha1=0.0,
            alpha2=0.0,
            alpha3=0.0,
            control1=ConverterControlType.Pac,
            control2=ConverterControlType.Qac,
            control1_val=-1.0 * float(elmgenstat.pgini),
            control2_val=-1.0 * float(elmgenstat.qgini),
            fault_control=ConverterFaultControlType.WECC_WT_Type_4B
        )

    else:
        vsc = dev.VSC(
            name=vsc_name,
            idtag=vsc_idtag,
            active=not bool(elmgenstat.outserv),
            bus_from=dc_bus,
            bus_to=ac_bus,
            rate=float(elmgenstat.sgn),
            alpha1=0.0,
            alpha2=0.0,
            alpha3=0.0,
            control1=ConverterControlType.Pac,
            control2=ConverterControlType.Qac,
            control1_val=0.0,
            control2_val=0.0,
            fault_control=ConverterFaultControlType.WECC_WT_Type_4B
        )
        logger.add_warning(
            f"This wind turbine is not Const. Q or Voltage Q-droop.",
            device=vsc_name,
            device_class="ElmGenstat"
        )

    return dc_bus, vsc


def convert_dgs_external_grid_to_generator(elmxnet: ElmXnet,
                                           stacubic_dict: Dict[str, List[int]],
                                           buses: List[dev.Bus],
                                           logger: Logger,
                                           cubics_by_objid: Dict[str, List[StaCubic]],
                                           bus_by_term_id: Dict[str, dev.Bus],
                                           Sbase: float) -> Tuple[dev.Bus, dev.Generator]:
    """
    Convert dgs external grid to generator.

    :param elmxnet: elmxnet parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param Sbase: Sbase parameter.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmxnet.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    bustype = str(elmxnet.bustp).strip().upper()

    k = elmxnet.rntxn  # R/X ratio
    Sk = elmxnet.snss  # Short-circuit power Sk''
    c = elmxnet.cmax  # Maximum voltage factor

    # Synchronous reactances
    xd = elmxnet.xd
    xq = elmxnet.xq
    if xd == xq:
        x = xd
    elif xd <= xq:
        x = xd
    else:
        x = xq

    Snom = x * np.sqrt(1 + k ** 2) * Sk / c  # Nominal Power of the external grid [MVA]
    r1 = x * k * Sbase / Snom  # Positive-sequence equivalent resistance [pu]
    x1 = x * Sbase / Snom  # Positive-sequence equivalent reactance [pu]

    gen = dev.Generator(
        name=elmxnet.loc_name or f"Gen_{_ref_id(elmxnet.ID)}",
        # The generator representation of ElmXnet must retain the same source
        # FID as the native ExternalGrid representation.
        idtag=_ref_id(elmxnet.ID),
        active=not bool(elmxnet.outserv),
        r1=r1,
        x1=x1,
    )

    if bustype == 'SL':
        bus.set_is_slack_at(t=None, val=True)

    elif bustype == 'PV':
        gen.Vset = elmxnet.usetp
        gen.P = elmxnet.pgini

    elif bustype == 'PQ':
        gen.P = elmxnet.pgini
        # A zero-power external grid is valid source data and must not trigger
        # a division-by-zero while constructing the static baseline.
        gen.Pf = _pf_from_pq(
            p_mw=float(elmxnet.pgini),
            q_mvar=float(elmxnet.qgini),
            default=1.0,
        )
    else:
        gen.P = elmxnet.pgini
        gen.Pf = _pf_from_pq(
            p_mw=float(elmxnet.pgini),
            q_mvar=float(elmxnet.qgini),
            default=1.0,
        )

    return bus, gen


def convert_dgs_to_external_grid(elmxnet: ElmXnet,
                                 stacubic_dict: Dict[str, List[int]],
                                 buses: List[dev.Bus],
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.ExternalGrid]:
    """
    Convert dgs to external grid.

    :param elmxnet: elmxnet parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmxnet.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    bustype = str(elmxnet.bustp).strip().upper()

    xgrid = dev.ExternalGrid(
        name=elmxnet.loc_name or f"Load_{_ref_id(elmxnet.ID)}",
        # Retain the physical source identity across static-only and dynamic
        # catalogue imports of the same DGS artifact.
        idtag=_ref_id(elmxnet.ID),
        active=not bool(elmxnet.outserv)
    )

    if bustype == 'SL':
        bus.set_is_slack_at(t=None, val=True)
        xgrid.mode = ExternalGridMode.VD
        xgrid.Vm = elmxnet.usetp
        xgrid.Va = math.radians(float(elmxnet.phiini))

    elif bustype == 'PV':
        xgrid.mode = ExternalGridMode.PV
        xgrid.Vm = elmxnet.usetp
        xgrid.P = elmxnet.pgini

    elif bustype == 'PQ':
        xgrid.mode = ExternalGridMode.PQ
        xgrid.P = elmxnet.pgini
        xgrid.Q = elmxnet.qgini
    else:
        xgrid.mode = ExternalGridMode.PQ
        xgrid.P = elmxnet.pgini
        xgrid.Q = elmxnet.qgini

    return bus, xgrid


def _extract_explicit_shunt_gb(
        elmshnt: ElmShnt,
        frequency_hz: float,
) -> Tuple[float, float] | None:
    """Extract one shunt step from explicit DGS fundamental-frequency data.

    PowerFactory DGS 7.0 exports the capacitor susceptance in micro-siemens
    and the reactor impedance in ohms.  Those values describe the actual
    element used by the load flow and avoid reconstructing a rounded circuit
    from rated reactive power and tuning frequency.

    :param elmshnt: Native PowerFactory shunt record.
    :param frequency_hz: Network fundamental frequency in Hz.
    :return: Conductance in MW and susceptance in MVAr at 1 p.u., or ``None``
        when an older DGS does not expose the physical fields.
    """
    shunt_type: int = int(elmshnt.shtype)
    rated_voltage_kv: float = float(elmshnt.ushnm)
    capacitive_susceptance_si: float = float(elmshnt.bcap) * 1e-6
    reactor_resistance_ohm: float = float(elmshnt.rrea)
    reactor_reactance_ohm: float = float(elmshnt.xrea)
    parallel_conductance_si: float = float(elmshnt.gparac) * 1e-6
    parallel_resistance_ohm: float = float(elmshnt.rpara)
    c1_uf: float = 0.0 if elmshnt.c1 is None else float(elmshnt.c1)
    c2_uf: float = 0.0 if elmshnt.c2 is None else float(elmshnt.c2)
    double_tuned_data_is_available: bool = bool(
        shunt_type == 4
        and frequency_hz > 0.0
        and c1_uf > 0.0
        and c2_uf > 0.0
    )
    physical_data_is_available: bool = bool(
        rated_voltage_kv > 0.0
        and (shunt_type in (0, 1, 2, 3) or double_tuned_data_is_available)
        and (
            double_tuned_data_is_available
            or abs(capacitive_susceptance_si) > 1e-20
            or abs(reactor_resistance_ohm) > 1e-20
            or abs(reactor_reactance_ohm) > 1e-20
            or abs(parallel_conductance_si) > 1e-20
        )
    )
    if physical_data_is_available and int(elmshnt.ncapa) > 0:
        reactor_impedance_ohm: complex = complex(
            reactor_resistance_ohm,
            reactor_reactance_ohm,
        )
        equivalent_admittance_si: complex | None
        if double_tuned_data_is_available:
            # PowerFactory's R-L-C1-C2,Rp topology places C2 in series with
            # the parallel combination of Rp and R-L-C1. The exported xrea
            # is the effective fundamental-frequency reactor reactance used
            # by load flow. Recomputing it from the layout-only rlrea field
            # changes the circuit whenever device and network frequency data
            # differ, so the DGS electrical contract must use rrea+j*xrea.
            angular_frequency: float = 2.0 * math.pi * frequency_hz
            c1_f: float = c1_uf * 1.0e-6
            c2_f: float = c2_uf * 1.0e-6
            c1_impedance_ohm: complex = 1.0 / complex(
                0.0,
                angular_frequency * c1_f,
            )
            c2_impedance_ohm: complex = 1.0 / complex(
                0.0,
                angular_frequency * c2_f,
            )
            inner_impedance_ohm: complex = (
                reactor_impedance_ohm + c1_impedance_ohm
            )
            if parallel_resistance_ohm > 0.0:
                parallel_denominator_ohm: complex = (
                    inner_impedance_ohm + parallel_resistance_ohm
                )
                if abs(parallel_denominator_ohm) > 1.0e-20:
                    damped_inner_impedance_ohm: complex = (
                        inner_impedance_ohm
                        * parallel_resistance_ohm
                        / parallel_denominator_ohm
                    )
                else:
                    damped_inner_impedance_ohm = complex(0.0, 0.0)
            else:
                damped_inner_impedance_ohm = inner_impedance_ohm
            double_tuned_impedance_ohm: complex = (
                c2_impedance_ohm + damped_inner_impedance_ohm
            )
            if abs(double_tuned_impedance_ohm) > 1.0e-20:
                equivalent_admittance_si = 1.0 / double_tuned_impedance_ohm
            else:
                equivalent_admittance_si = None
        else:
            pass
        if double_tuned_data_is_available:
            pass
        elif shunt_type == 1:
            if abs(reactor_impedance_ohm) > 1e-20:
                equivalent_admittance_si = 1.0 / reactor_impedance_ohm
            else:
                equivalent_admittance_si = None
        else:
            if shunt_type == 2:
                dielectric_conductance_si: float
                if abs(parallel_conductance_si) > 1e-20:
                    dielectric_conductance_si = parallel_conductance_si
                else:
                    dielectric_conductance_si = (
                        abs(capacitive_susceptance_si) * abs(float(elmshnt.tandc))
                    )
                equivalent_admittance_si = complex(
                    dielectric_conductance_si,
                    capacitive_susceptance_si,
                )
            else:
                if shunt_type in (0, 3) and abs(capacitive_susceptance_si) > 1e-20:
                    capacitor_impedance_ohm: complex = 1.0 / complex(
                        0.0,
                        capacitive_susceptance_si,
                    )
                    if shunt_type == 3 and parallel_resistance_ohm > 0.0:
                        parallel_denominator_ohm: complex = (
                            reactor_impedance_ohm + parallel_resistance_ohm
                        )
                        if abs(parallel_denominator_ohm) > 1e-20:
                            damped_reactor_impedance_ohm: complex = (
                                reactor_impedance_ohm
                                * parallel_resistance_ohm
                                / parallel_denominator_ohm
                            )
                            total_impedance_ohm: complex = (
                                damped_reactor_impedance_ohm + capacitor_impedance_ohm
                            )
                        else:
                            total_impedance_ohm = complex(0.0, 0.0)
                    else:
                        # Type 0 exposes its equivalent fundamental series
                        # R-L-C branch directly.  Type 4 remains on the
                        # rating-based double-tuned reconstruction below.
                        total_impedance_ohm = reactor_impedance_ohm + capacitor_impedance_ohm
                    if abs(total_impedance_ohm) > 1e-20:
                        equivalent_admittance_si = 1.0 / total_impedance_ohm
                    else:
                        equivalent_admittance_si = None
                else:
                    equivalent_admittance_si = None
        if equivalent_admittance_si is not None:
            if int(elmshnt.ctech) == 0:
                connection_multiplier: float = 3.0
            else:
                connection_multiplier = 1.0
            rated_voltage_squared_kv: float = (
                connection_multiplier * rated_voltage_kv * rated_voltage_kv
            )
            result: Tuple[float, float] | None = (
                rated_voltage_squared_kv * float(equivalent_admittance_si.real),
                rated_voltage_squared_kv * float(equivalent_admittance_si.imag),
            )
        else:
            result = None
    else:
        if physical_data_is_available:
            result = (0.0, 0.0)
        else:
            result = None
    return result


def _extract_legacy_shunt_gb(elmshnt: ElmShnt, f: float, logger: Logger) -> Tuple[float, float]:
    """
    Extract shunt admittance from legacy rating-only DGS fields.

    :param elmshnt: elmshnt parameter.
    :param f: f parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    name = elmshnt.loc_name or _ref_id(elmshnt.ID) or "Shunt"

    shtype: int = elmshnt.shtype
    Q: float = elmshnt.qtotn * 1e6  # Rated Reactive Power [Mvar] -> [var]
    U: float = elmshnt.ushnm * 1e3  # Rated Voltage [kV] -> [V]
    fres: float = elmshnt.fres  # Resonance Frequency [Hz]
    h = fres / f  # Tuning Order
    conn: int = elmshnt.ctech  # Connection
    quality_factor: float = elmshnt.grea  # Quality Factor

    w = 2 * np.pi * f  # Electrical angular speed [rad/s]
    if conn == 0:
        d_y = 3.0  # conn==0 -> 3PH-D
    else:
        d_y = 1.0  # 3PH-Y/YN

    if shtype == 0:  # R-L-C

        C = Q / (d_y * w * U ** 2) * (1 - 1 / h ** 2)
        L = 1 / ((h * w) ** 2 * C)
        if quality_factor == 0.0:
            R = 0.0
        else:
            R = (w * L) / quality_factor

        Z = R + 1j * (w * L - 1 / (w * C))
        S = d_y * U ** 2 / np.conj(Z)

        g_mw = np.real(S) / 1e6
        # PowerFactory's complex power follows the passive sign convention.
        # VeraGrid stores physical susceptance, so B=-Qpassive/|V|².
        b_mvar = -np.imag(S) / 1e6

    elif shtype == 1:  # R-L

        L = d_y * U ** 2 / (w * Q)
        if quality_factor == 0.0:
            R = 0.0
        else:
            R = (w * L) / quality_factor

        Z = R + 1j * w * L
        S = d_y * U ** 2 / np.conj(Z)

        g_mw = np.real(S) / 1e6
        b_mvar = -np.imag(S) / 1e6

    elif shtype == 2:  # C

        C = Q / (d_y * w * U ** 2)
        G = w * C * elmshnt.tandc

        Y = G + 1j * w * C
        S = d_y * U ** 2 * np.conj(Y)

        g_mw = np.real(S) / 1e6
        b_mvar = -np.imag(S) / 1e6

    elif shtype == 3:  # R-L-C,Rp

        C = Q / (d_y * w * U ** 2) * (1 - 1 / h ** 2)
        L = 1 / ((h * w) ** 2 * C)
        if quality_factor == 0.0:
            R = 0.0
        else:
            R = (w * L) / quality_factor
        Rp = elmshnt.rpara

        try:
            Z = ((R + 1j * w * L) * Rp) / ((R + 1j * w * L) + Rp) + 1 / (1j * w * C)
            S = d_y * U ** 2 / np.conj(Z)

            g_mw = np.real(S) / 1e6
            b_mvar = -np.imag(S) / 1e6
        except ZeroDivisionError:
            g_mw = 0.0
            b_mvar = 0.0
            logger.add_warning(
                f"Cannot be computed because of zero division.",
                device=name,
                device_class="ElmShnt"
            )

    elif shtype == 4:  # R-L-C1-C2,Rp

        C2 = Q / (d_y * w * U ** 2)
        C1 = C2 * (h ** 2 - 1)
        L = 1 / (w ** 2 * C1)
        if quality_factor == 0.0:
            R = 0.0
        else:
            R = w * L / quality_factor
        Rp = elmshnt.rpara

        try:
            Z = ((R + 1j * w * L + 1 / (1j * w * C1)) * Rp) / ((R + 1j * w * L + 1 / (1j * w * C1)) + Rp) + 1 / (
                    1j * w * C2)
            S = d_y * U ** 2 / np.conj(Z)

            g_mw = np.real(S) / 1e6
            b_mvar = -np.imag(S) / 1e6
        except ZeroDivisionError:
            g_mw = 0.0
            b_mvar = 0.0
            logger.add_warning(
                f"Cannot be computed because of zero division.",
                device=name,
                device_class="ElmShnt"
            )
    else:
        g_mw = 0.0
        b_mvar = 0.0
        logger.add_warning(
            f"Cannot be computed because of type not recognized.",
            device=name,
            device_class="ElmShnt",
            value=shtype
        )

    if elmshnt.ncapa == 0 and elmshnt.ncapx <= 1:
        g_mw = 0.0
        b_mvar = 0.0

    return g_mw, b_mvar


def _extract_shunt_gb(elmshnt: ElmShnt, f: float, logger: Logger) -> Tuple[float, float]:
    """Extract one PowerFactory shunt step as VeraGrid admittance.

    DGS 7.0 physical circuit fields take precedence because they are the
    values used by PowerFactory's load flow.  The rating-based reconstruction
    remains available for older DGS definitions that omitted those columns.

    :param elmshnt: Native PowerFactory shunt record.
    :param f: System frequency in Hz.
    :param logger: Import diagnostic sink.
    :return: Conductance in MW and susceptance in MVAr at 1 p.u.
    """
    explicit_result: Tuple[float, float] | None = _extract_explicit_shunt_gb(
        elmshnt=elmshnt,
        frequency_hz=f,
    )
    if explicit_result is not None:
        result: Tuple[float, float] = explicit_result
    else:
        result = _extract_legacy_shunt_gb(elmshnt=elmshnt, f=f, logger=logger)
    return result


def _get_shunt_voltage_base_scale(
        bus_nominal_voltage_kv: float,
        device_rated_voltage_kv: float,
) -> float:
    """Convert a physical shunt coefficient to the connected-bus p.u. base.

    PowerFactory exports ``ElmShnt`` admittance data on the device rated
    voltage. VeraGrid stores ``G`` and ``B`` as the MW/MVAr coefficients at
    one p.u. of the connected bus, so a different bus nominal voltage requires
    the squared voltage-base conversion.

    :param bus_nominal_voltage_kv: Connected bus line-line nominal voltage.
    :param device_rated_voltage_kv: Exported shunt rated line-line voltage.
    :return: Multiplier from device-rated coefficient to bus-base coefficient.
    """
    voltage_data_is_valid: bool = bool(
        math.isfinite(bus_nominal_voltage_kv)
        and math.isfinite(device_rated_voltage_kv)
        and bus_nominal_voltage_kv > 0.0
        and device_rated_voltage_kv > 0.0
    )
    if voltage_data_is_valid:
        voltage_ratio: float = bus_nominal_voltage_kv / device_rated_voltage_kv
        scale: float = voltage_ratio * voltage_ratio
    else:
        # Legacy exports can omit the device rating. Keeping unity preserves
        # their historical interpretation while avoiding an invented base.
        scale = 1.0
    return scale


def _convert_pf_shunt_connection(
        connection_code: int,
        shunt_name: str,
        logger: Logger,
) -> ShuntConnectionType:
    """
    Convert one PowerFactory ``ElmShnt.ctech`` code to a shunt connection.

    PowerFactory exports delta, ungrounded star and grounded star as codes
    ``0``, ``1`` and ``2`` respectively.  An ``ElmShnt`` has no separate
    neutral cubicle, so grounded star maps to the bus-ground connection rather
    than VeraGrid's explicit four-wire neutral connection.

    :param connection_code: Native ``ctech`` integer.
    :param shunt_name: Human-readable device name for diagnostics.
    :param logger: Import logger receiving unsupported-code warnings.
    :return: Equivalent VeraGrid shunt connection.
    """
    if connection_code == 0:
        connection: ShuntConnectionType = ShuntConnectionType.Delta
    else:
        if connection_code == 1:
            connection = ShuntConnectionType.FloatingStar
        else:
            if connection_code == 2:
                connection = ShuntConnectionType.GroundedStar
            else:
                # Grounded star preserves a connected balanced shunt when an
                # older export writes a vendor-specific connection code.
                connection = ShuntConnectionType.GroundedStar
                logger.add_warning(
                    msg="Unsupported ElmShnt connection code; using grounded star",
                    device=shunt_name,
                    device_class="ElmShnt",
                    value=connection_code,
                )
    return connection


def convert_dgs_to_shunt(elmshnt: ElmShnt,
                         stacubic_dict: Dict[str, List[int]],
                         buses: List[dev.Bus],
                         logger: Logger,
                         cubics_by_objid: Dict[str, List[StaCubic]],
                         bus_by_term_id: Dict[str, dev.Bus],
                         frequency: float,
                         switch_by_cubic_id: Dict[str, StaSwitch] | None = None) -> Tuple[dev.Bus, dev.Shunt]:
    """
    Convert dgs to shunt.

    :param elmshnt: elmshnt parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param frequency: frequency parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :return: Function result.
    """
    effective_switch_by_cubic_id: Dict[str, StaSwitch]
    if switch_by_cubic_id is None:
        effective_switch_by_cubic_id = dict()
    else:
        effective_switch_by_cubic_id = switch_by_cubic_id

    name = elmshnt.loc_name or f"Shunt_{_ref_id(elmshnt.ID)}"

    bus = get_injection_bus(elm_id=elmshnt.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    g_mw: float
    b_mvar: float
    g_mw, b_mvar = _extract_shunt_gb(elmshnt=elmshnt, f=frequency, logger=logger)
    voltage_base_scale: float = _get_shunt_voltage_base_scale(
        bus_nominal_voltage_kv=float(bus.Vnom),
        device_rated_voltage_kv=float(elmshnt.ushnm),
    )
    # Store the physical admittance on the bus p.u. voltage base. This is
    # essential when a filter rating differs from its terminal nominal voltage.
    g_mw *= voltage_base_scale
    b_mvar *= voltage_base_scale

    shunt = dev.Shunt(
        name=name,
        idtag=_ref_id(elmshnt.ID),
        G=g_mw,
        B=b_mvar,
        # A cubicle isolator is part of the element's actual connectivity.
        active=(
            elmshnt.outserv == 0
            and _is_element_closed_by_cubicle_switches(
                element_id=elmshnt.ID,
                cubics_by_objid=cubics_by_objid,
                switch_by_cubic_id=effective_switch_by_cubic_id,
            )
        ),
    )
    shunt.conn = _convert_pf_shunt_connection(
        connection_code=int(elmshnt.ctech),
        shunt_name=name,
        logger=logger,
    )

    return bus, shunt


def _get_elmshnt_measurement_report_totals(
        elmshnt: ElmShnt,
) -> np.ndarray | None:
    """Read cumulative reactive power from a native shunt measurement table.

    PowerFactory permits measurement reports only for pure capacitive and
    R-L shunts.  The first matrix column is the cumulative capacitive power;
    the second is the cumulative inductive power.  VeraGrid uses positive
    susceptance for capacitors and negative susceptance for reactors.

    :param elmshnt: Parsed native shunt record.
    :return: Signed cumulative MVAr values, or ``None`` when no complete table
        is available.
    """
    report_enabled: bool = int(elmshnt.iTaps) != 0
    shunt_type: int = int(elmshnt.shtype)
    if shunt_type == 2:
        report_column: int = 0
        report_sign: float = 1.0
    else:
        if shunt_type == 1:
            report_column = 1
            report_sign = -1.0
        else:
            report_column = -1
            report_sign = 0.0

    required_row_count: int = max(1, int(elmshnt.ncapx) + 1)
    report_has_required_rows: bool = bool(
        len(elmshnt.measurement_report) >= required_row_count
    )
    if report_enabled and report_column >= 0 and report_has_required_rows:
        cumulative_values: np.ndarray | None = np.empty(
            required_row_count,
            dtype=float,
        )
        row_index: int
        for row_index in range(required_row_count):
            if cumulative_values is not None:
                report_row: List[float] = elmshnt.measurement_report[row_index]
                if len(report_row) > report_column:
                    signed_value: float = report_sign * float(report_row[report_column])
                    if math.isfinite(signed_value):
                        cumulative_values[row_index] = signed_value
                    else:
                        cumulative_values = None
                else:
                    cumulative_values = None
            else:
                pass
        else:
            pass
    else:
        cumulative_values = None
    return cumulative_values


def _build_elmshnt_step_model(elmshnt: ElmShnt, logger: Logger) -> Tuple[np.ndarray, int, float, float]:
    """
    Build elmshnt step model.

    :param elmshnt: elmshnt parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    name: str = elmshnt.loc_name or _ref_id(elmshnt.ID) or "ElmShnt"
    ncapx: int = int(elmshnt.ncapx)
    measurement_report_totals: np.ndarray | None = (
        _get_elmshnt_measurement_report_totals(elmshnt=elmshnt)
    )
    if measurement_report_totals is not None:
        # VeraGrid stores incremental step values, whereas PowerFactory's
        # measurement report stores the cumulative total at every position.
        b_steps: np.ndarray = np.empty(ncapx + 1, dtype=float)
        b_steps[0] = measurement_report_totals[0]
        if ncapx > 0:
            b_steps[1:] = np.diff(measurement_report_totals)
        else:
            pass
        bmin: float = min(0.0, float(np.min(measurement_report_totals)))
        bmax: float = max(0.0, float(np.max(measurement_report_totals)))
    else:
        q_step: float = float(elmshnt.qcapn)
        if q_step == 0.0:
            q_step = -abs(float(elmshnt.qrean))
        else:
            pass

        qtotn: float = float(elmshnt.qtotn)
        if q_step == 0.0 and qtotn != 0.0:
            q_step = qtotn / float(ncapx)
            if int(elmshnt.shtype) == 1:
                q_step = -abs(q_step)
            else:
                pass

            logger.add_warning(
                f"using q_step=qtotn/ncapx.",
                device=name,
                device_class="ElmShnt",
                value=q_step
            )
        else:
            pass

        # Constant native steps become the incremental VeraGrid positions.
        b_steps = np.concatenate(
            (
                np.array([0.0], dtype=float),
                np.full(ncapx, q_step, dtype=float),
            )
        )

        # Bounds follow the complete cumulative constant-step range.
        total: float = q_step * float(ncapx)
        if total >= 0.0:
            bmin = 0.0
            bmax = total
        else:
            bmin = total
            bmax = 0.0

    # Initial step index equals the number of connected steps (ncapa) because b_steps[0] is OFF (0 MVAr).
    initial_step: int = int(elmshnt.ncapa)
    if initial_step < 0:
        initial_step = 0
    else:
        pass
    if initial_step > ncapx:
        initial_step = ncapx
    else:
        pass

    return b_steps, initial_step, bmin, bmax


def convert_dgs_to_controllable_shunt_from_elmshnt(elmshnt: ElmShnt,
                                                   stacubic_dict: Dict[str, List[int]],
                                                   buses: List[dev.Bus],
                                                   logger: Logger,
                                                   cubics_by_objid: Dict[str, List[StaCubic]],
                                                   bus_by_term_id: Dict[str, dev.Bus],
                                                   frequency: float) -> Tuple[
    dev.Bus, dev.ControllableShunt]:
    """
    Convert dgs to controllable shunt from elmshnt.

    :param elmshnt: elmshnt parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param frequency: frequency parameter.
    :return: Function result.
    """
    name: str = elmshnt.loc_name or f"ElmShnt_{_ref_id(elmshnt.ID)}"

    bus: dev.Bus = get_injection_bus(elm_id=elmshnt.ID,
                                     stacubic_dict=stacubic_dict,
                                     buses=buses,
                                     cubics_by_objid=cubics_by_objid,
                                     bus_by_term_id=bus_by_term_id)
    voltage_base_scale: float = _get_shunt_voltage_base_scale(
        bus_nominal_voltage_kv=float(bus.Vnom),
        device_rated_voltage_kv=float(elmshnt.ushnm),
    )

    if elmshnt.i_cont == 1:  # Continuous

        b_steps: np.ndarray
        initial_step: int
        bmin: float
        bmax: float
        b_steps, initial_step, bmin, bmax = _build_elmshnt_step_model(
            elmshnt=elmshnt,
            logger=logger,
        )
        b_steps *= voltage_base_scale
        bmin *= voltage_base_scale
        bmax *= voltage_base_scale

        if int(elmshnt.iswitch) != 0:
            control_mode: ShuntControlMode = ShuntControlMode.Discrete
        else:
            control_mode = ShuntControlMode.Locked

        vset: float = float(elmshnt.usetp)

        cshunt: dev.ControllableShunt = dev.ControllableShunt(
            name=name,
            idtag=_ref_id(elmshnt.ID),
            number_of_steps=int(len(b_steps)),
            step=int(initial_step),
            g_per_step=0.0,
            b_per_step=0.0,
            Bmin=bmin,
            Bmax=bmax,
            Gmin=0.0,
            Gmax=0.0,
            active=(elmshnt.outserv == 0),
            vset=vset,
            control_mode=control_mode,
            control_bus=bus,
        )

        # Override step arrays to match the DGS stepped-bank model (OFF + ncapx identical increments).
        cshunt.b_steps = b_steps
        cshunt.g_steps = np.zeros(len(b_steps), dtype=float)
        cshunt.active_steps = np.ones(len(b_steps), dtype=int)

        # Ensure B/G are coherent with the initial step after overriding arrays
        cshunt.step = int(initial_step)

    elif elmshnt.i_cont == 0:  # Discrete

        # PowerFactory stores ``ncapx`` physical units plus an independent
        # ``ncapa`` count in service.  VeraGrid stores positions, including
        # the zero-unit state, as cumulative step increments.  Allocate the
        # explicit OFF position so a fully connected bank (ncapa == ncapx)
        # remains a valid index instead of silently retaining the default B.
        declared_b_steps: np.ndarray
        initial_step: int
        declared_bmin: float
        declared_bmax: float
        (
            declared_b_steps,
            initial_step,
            declared_bmin,
            declared_bmax,
        ) = _build_elmshnt_step_model(elmshnt=elmshnt, logger=logger)
        declared_b_steps *= voltage_base_scale
        declared_bmin *= voltage_base_scale
        declared_bmax *= voltage_base_scale
        g_per_unit_mw: float
        b_per_unit_mvar: float
        g_per_unit_mw, b_per_unit_mvar = _extract_shunt_gb(
            elmshnt=elmshnt,
            f=frequency,
            logger=logger,
        )
        g_per_unit_mw *= voltage_base_scale
        b_per_unit_mvar *= voltage_base_scale
        physical_b_is_available: bool = bool(
            math.isfinite(b_per_unit_mvar)
            and abs(b_per_unit_mvar) > 1e-20
        )
        measurement_report_totals: np.ndarray | None = (
            _get_elmshnt_measurement_report_totals(elmshnt=elmshnt)
        )
        if physical_b_is_available and measurement_report_totals is None:
            b_steps: np.ndarray = np.concatenate(
                (
                    np.array([0.0], dtype=float),
                    np.full(int(elmshnt.ncapx), b_per_unit_mvar, dtype=float),
                )
            )
            physical_total_b: float = b_per_unit_mvar * float(elmshnt.ncapx)
            bmin: float = min(0.0, physical_total_b)
            bmax: float = max(0.0, physical_total_b)
        else:
            b_steps = declared_b_steps
            bmin = declared_bmin
            bmax = declared_bmax
        g_steps: np.ndarray = np.concatenate(
            (
                np.array([0.0], dtype=float),
                np.full(int(elmshnt.ncapx), g_per_unit_mw, dtype=float),
            )
        )
        automatic_switching_enabled: bool = int(elmshnt.iswitch) != 0
        if automatic_switching_enabled:
            control_mode: ShuntControlMode = ShuntControlMode.Discrete
            control_bus: dev.Bus | None = bus
        else:
            control_mode = ShuntControlMode.Locked
            control_bus = None

        cshunt: dev.ControllableShunt = dev.ControllableShunt(
            name=name,
            idtag=_ref_id(elmshnt.ID),
            number_of_steps=int(len(b_steps)),
            step=0,
            g_per_step=0.0,
            b_per_step=0.0,
            Bmin=bmin,
            Bmax=bmax,
            Gmin=min(0.0, g_per_unit_mw * float(elmshnt.ncapx)),
            Gmax=max(0.0, g_per_unit_mw * float(elmshnt.ncapx)),
            active=(elmshnt.outserv == 0),
            vmax=elmshnt.usetp_mx,
            vmin=elmshnt.usetp_mn,
            control_mode=control_mode,
            control_bus=control_bus,
        )
        cshunt.b_steps = b_steps
        cshunt.g_steps = g_steps
        cshunt.active_steps = np.ones(len(b_steps), dtype=int)
        cshunt.step = int(initial_step)
    else:
        # The DGS schema defines only continuous and discrete native modes.
        # Keep an explicit locked zero-state device for malformed source data.
        cshunt = dev.ControllableShunt(
            name=name,
            idtag=_ref_id(elmshnt.ID),
            number_of_steps=1,
            step=0,
            active=False,
            control_mode=ShuntControlMode.Locked,
        )
        logger.add_warning(
            msg="Unsupported ElmShnt control mode; importing disabled",
            device=name,
            device_class="ElmShnt",
            value=int(elmshnt.i_cont),
        )

    cshunt.conn = _convert_pf_shunt_connection(
        connection_code=int(elmshnt.ctech),
        shunt_name=name,
        logger=logger,
    )

    return bus, cshunt


def convert_dgs_svs_to_vsc(elmsvs: ElmSvs,
                           stacubic_dict: Dict[str, List[int]],
                           buses: List[dev.Bus],
                           logger: Logger,
                           cubics_by_objid: Dict[str, List[StaCubic]],
                           bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.VSC]:
    """
    Convert dgs svs to vsc.

    :param elmsvs: elmsvs parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    name = elmsvs.loc_name or f"ElmSvs_{_ref_id(elmsvs.ID)}"

    ac_bus = get_injection_bus(elm_id=elmsvs.ID,
                               stacubic_dict=stacubic_dict,
                               buses=buses,
                               cubics_by_objid=cubics_by_objid,
                               bus_by_term_id=bus_by_term_id)

    dc_bus = dev.Bus(name=f'{_ref_id(ac_bus.name)}_SVS_DC',
                     is_dc=True,
                     is_slack=True,
                     xpos=ac_bus.x,
                     ypos=ac_bus.y - 200, )

    vsc_name = _get_non_empty_name(elmsvs.loc_name, f"SVS_{_ref_id(elmsvs.ID)}")

    control_mode = elmsvs.i_ctrl

    if control_mode == 2:  # Reactive Power Control

        control1 = ConverterControlType.Pac
        control1_val = 0.0  # Active power injection of the SVS [MW]

        control2 = ConverterControlType.Qac
        control2_val = elmsvs.qsetp  # Reactive power injection of the SVS [MVAr]

        rate = max(np.abs(elmsvs.tcrmax), np.abs(elmsvs.qmin))
        kpd = 0.0  # Droop [%]
        ysvs = 0.0  # Fixed admittance based on 1 MVA / Ub^2
        u_setpoint = 1.0  # Voltage Setpoint [pu]

    elif control_mode == 1:  # Voltage Control
        if elmsvs.i_droop == 0:  # No droop, just sets the voltage to the given setpoint

            control1 = ConverterControlType.Pac
            control1_val = 0.0  # Active power injection of the SVS [MW]

            control2 = ConverterControlType.Vm_ac
            control2_val = elmsvs.usetp  # Voltage setpoint [pu]

            ysvs = 0.0  # Fixed admittance based on 1 MVA / Ub^2
            rate = max(np.abs(elmsvs.tcrmax), np.abs(elmsvs.qmin))
            kpd = 0.0  # Droop [%]
            u_setpoint = 1.0  # Voltage Setpoint [pu]

        else:  # Droop Control

            kpd = elmsvs.ddroop  # Droop [%]
            rate = elmsvs.Srated  # Rated Power [MVA]
            u_setpoint = elmsvs.usetp  # Voltage Setpoint [pu]

            control1 = ConverterControlType.Pac
            control1_val = 0.0  # Active power injection of the SVS [MW]

            control2 = ConverterControlType.Q_droop
            control2_val = 0.0  # Reactive power injection of the SVS [MVAr]

            ysvs = 0.0  # Fixed admittance based on 1 MVA / Ub^2

    else:  # No Control
        control1 = ConverterControlType.Pac
        control2 = ConverterControlType.Qac

        # Fixed admittance based on 1 MVA / Ub^2
        ysvs = elmsvs.qmin * elmsvs.nncap + elmsvs.tcrqact + elmsvs.Qfixcap * elmsvs.nfixcap

        # SVS Range
        ymin = elmsvs.qmin * elmsvs.nxcap + elmsvs.Qfixcap * elmsvs.nfixcap
        ymax = elmsvs.tcrmax + elmsvs.Qfixcap * elmsvs.nfixcap
        ysvs = max(min(ysvs, ymax), ymin)

        control1_val = 0.0  # Active power injection of the SVS [MW]
        control2_val = np.abs(1.0 ** 2) * np.conj(ysvs)  # Reactive power injection of the SVS [MVAr]

        rate = max(np.abs(elmsvs.tcrmax), np.abs(elmsvs.qmin))
        kpd = 0.0  # Droop [%]
        u_setpoint = 1.0  # Voltage Setpoint [pu]

    vsc = dev.VSC(
        name=vsc_name,
        idtag=_ref_id(elmsvs.ID),
        active=not bool(elmsvs.outserv),
        bus_from=dc_bus,
        bus_to=ac_bus,
        rate=rate,
        alpha1=0.0,
        alpha2=0.0,
        alpha3=0.0,
        control1=control1,
        control2=control2,
        control1_val=control1_val,
        control2_val=control2_val,
        ysvs=ysvs,
        control2_droop=kpd,
        control2_droop_val=u_setpoint
    )

    return dc_bus, vsc


def _resolve_svs_control_bus(
        elmsvs: ElmSvs,
        local_bus: dev.Bus,
        cubic_by_id: Dict[str, StaCubic],
        bus_by_term_id: Dict[str, dev.Bus],
        logger: Logger,
) -> dev.Bus | None:
    """
    Resolve the voltage-control terminal of one PowerFactory static-var system.

    ``cpCtrlNode`` points directly to the resolved voltage-control
    ``ElmTerm``.  ``p_cub`` is a reactive-power measurement cubicle and must
    not replace the voltage-control node in a consolidated export.  Legacy DGS
    files that lack ``cpCtrlNode`` may retain the historical cubicle fallback.

    :param elmsvs: Parsed static-var-system row.
    :param local_bus: Bus carrying the physical SVC injection.
    :param cubic_by_id: Imported cubicles keyed by DGS FID.
    :param bus_by_term_id: Imported buses keyed by terminal FID.
    :param logger: Import diagnostic sink.
    :return: Remote/local control bus, or ``None`` for an unresolved declared pointer.
    """
    control_pointer_candidates: List[str | None]
    if elmsvs.cp_ctrl_node_column_present:
        # An explicit empty calculated node means local voltage control; the
        # independent Q-measurement pointer remains handled by the droop law.
        control_pointer_candidates = list((elmsvs.cpCtrlNode,))
    else:
        control_pointer_candidates = list((elmsvs.cpCtrlNode, elmsvs.p_cub))
    control_bus: dev.Bus | None = None
    declared_pointer: str | None = None
    control_pointer: str | None
    for control_pointer in control_pointer_candidates:
        pointer_is_declared: bool = (
            control_pointer is not None
            and str(control_pointer).strip() not in {"", "*"}
        )
        if control_bus is None and pointer_is_declared:
            if declared_pointer is None:
                declared_pointer = str(control_pointer)
            else:
                pass
            pointer_id: str | None = _ref_id(control_pointer)
            if pointer_id is None or pointer_id == "":
                pass
            else:
                # A resolved control-node pointer refers directly to ElmTerm.
                control_bus = bus_by_term_id.get(pointer_id, None)
                if control_bus is None:
                    # A configured measurement pointer refers to StaCubic;
                    # its containing ElmTerm is the electrical control node.
                    control_cubic: StaCubic | None = cubic_by_id.get(pointer_id, None)
                    if control_cubic is None:
                        pass
                    else:
                        terminal_id: str | None = _ref_id(control_cubic.fold_id)
                        if terminal_id is None or terminal_id == "":
                            pass
                        else:
                            control_bus = bus_by_term_id.get(terminal_id, None)
                else:
                    pass
        else:
            pass
    else:
        pass

    if control_bus is not None:
        result: dev.Bus | None = control_bus
    else:
        if declared_pointer is None:
            result = local_bus
        else:
            # A declared but missing remote topology is materially different
            # from a legacy file, so surface it instead of claiming local control.
            logger.add_error(
                msg="PowerFactory ElmSvs control node could not be resolved",
                device=elmsvs.loc_name,
                device_class="ElmSvs",
                value=declared_pointer,
            )
            result = None
    return result


def convert_dgs_to_controllable_shunt_from_svs(elmsvs: ElmSvs,
                                               stacubic_dict: Dict[str, List[int]],
                                               buses: List[dev.Bus],
                                               logger: Logger,
                                               cubics_by_objid: Dict[str, List[StaCubic]],
                                               bus_by_term_id: Dict[str, dev.Bus],
                                               cubic_by_id: Dict[str, StaCubic] | None = None,
                                               external_control_model: bool = False) -> Tuple[
    dev.Bus, dev.ControllableShunt]:
    """
    Convert dgs to controllable shunt from svs.

    :param elmsvs: elmsvs parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param cubic_by_id: Imported cubicles keyed by DGS FID.
    :param external_control_model: Composite-model controller owns the SVC state.
    :return: Function result.
    """
    name: str = elmsvs.loc_name or f"ElmSvs_{_ref_id(elmsvs.ID)}"

    bus: dev.Bus = get_injection_bus(elm_id=elmsvs.ID,
                                     stacubic_dict=stacubic_dict,
                                     buses=buses,
                                     cubics_by_objid=cubics_by_objid,
                                     bus_by_term_id=bus_by_term_id)
    effective_cubic_by_id: Dict[str, StaCubic]
    if cubic_by_id is None:
        effective_cubic_by_id = dict()
    else:
        effective_cubic_by_id = cubic_by_id
    control_bus: dev.Bus | None = _resolve_svs_control_bus(
        elmsvs=elmsvs,
        local_bus=bus,
        cubic_by_id=effective_cubic_by_id,
        bus_by_term_id=bus_by_term_id,
        logger=logger,
    )

    # PowerFactory stores qmin as the negative contribution of one capacitor
    # bank and tcrmax as positive reactor absorption.  VeraGrid uses positive
    # bus injection, so both source limits must be reversed before fixed-bank
    # injection is added.
    fixed_bank_reactive_power: float = -float(elmsvs.Qfixcap) * float(elmsvs.nfixcap)
    if float(elmsvs.tcrmax) != 0.0:
        bmin: float = -float(elmsvs.tcrmax) + fixed_bank_reactive_power
    else:
        bmin = -float(elmsvs.qmax) + fixed_bank_reactive_power
    bmax: float = (
        -float(elmsvs.qmin) * float(elmsvs.nxcap)
        + fixed_bank_reactive_power
    )
    is_qv_droop: bool = int(elmsvs.i_droop) != 0
    has_valid_qv_droop: bool = (
        is_qv_droop
        and float(elmsvs.ddroop) > 0.0
        and float(elmsvs.Srated) != 0.0
    )
    # ``c_pmod`` alone is provenance only because native SVCs also use a
    # composite frame. The caller supplies external ownership only after
    # checking the complete exported pointer schema.
    has_external_controller: bool = bool(external_control_model)

    # PowerFactory retains the configured voltage reference in droop mode:
    # u_control = usetp + Q_measured / Q_droop.  VeraGrid uses the opposite
    # sign for capacitive bus injection, so its equivalent specified-power law
    # is Q_injection = (usetp - u_control) * Q_droop.  An attached composite
    # model owns the controller itself, so the static network must retain only
    # its configured capacitor/reactor state instead of installing a second
    # native droop law.
    is_reactive_power_control: bool = int(elmsvs.i_ctrl) == 2
    is_no_control: bool = int(elmsvs.i_ctrl) == 0 and not is_qv_droop
    if has_external_controller or is_no_control:
        vset: float = float(elmsvs.usetp)
        control_mode: ShuntControlMode = ShuntControlMode.Locked
    else:
        if is_reactive_power_control:
            vset = float(elmsvs.usetp)
            control_mode = ShuntControlMode.ReactivePower
        else:
            if has_valid_qv_droop:
                vset = float(elmsvs.usetp)
                control_mode = ShuntControlMode.QVDroop
            else:
                vset = float(elmsvs.usetp)
                if is_no_control:
                    control_mode = ShuntControlMode.Locked
                else:
                    control_mode = ShuntControlMode.Continuous

    invalid_native_qv_droop: bool = (
        is_qv_droop
        and not has_valid_qv_droop
        and not has_external_controller
    )
    if invalid_native_qv_droop:
        logger.add_warning(
            msg="ElmSvs Q/V droop has invalid slope parameters; using ideal continuous voltage control",
            device=name,
            device_class="ElmSvs",
            value=f"ddroop={float(elmsvs.ddroop)}, Srated={float(elmsvs.Srated)}",
        )
    else:
        pass

    if has_external_controller or is_no_control:
        # These configured fields describe the actual susceptance state without
        # depending on solved m:/c: columns: fixed capacitor contribution,
        # connected switched-capacitor contribution and active TCR absorption.
        configured_reactive_state: float = (
            fixed_bank_reactive_power
            + (-float(elmsvs.qmin) * float(elmsvs.nncap))
            - float(elmsvs.tcrqact)
        )
        # ControllableShunt.B is the physical susceptance coefficient, so a
        # positive configured capacitive state remains positive.
        b_steps: np.ndarray = np.array(
            [configured_reactive_state],
            dtype=float,
        )
        initial_step: int = 0
    elif bmin < 0.0 and bmax > 0.0:
        b_steps: np.ndarray = np.array([bmin, -bmin, bmax], dtype=float)
        initial_step: int = 1
    elif bmin == bmax:
        b_steps = np.array([bmax], dtype=float)
        initial_step = 0
    else:
        b_steps = np.array([bmin, (bmax - bmin)], dtype=float)
        initial_step = 0

    cshunt: dev.ControllableShunt = dev.ControllableShunt(
        name=name,
        idtag=_ref_id(elmsvs.ID),
        number_of_steps=int(len(b_steps)),
        step=int(initial_step),
        g_per_step=0.0,
        b_per_step=0.0,
        Bmin=bmin,
        Bmax=bmax,
        Gmin=0.0,
        Gmax=0.0,
        active=(elmsvs.outserv == 0),
        vset=vset,
        qv_droop=float(elmsvs.ddroop),
        qv_rated_power=float(elmsvs.Srated),
        qset=float(elmsvs.qsetp),
        control_mode=control_mode,
        control_bus=control_bus
    )

    cshunt.b_steps = b_steps
    cshunt.g_steps = np.zeros(len(b_steps), dtype=float)
    cshunt.active_steps = np.ones(len(b_steps), dtype=int)
    cshunt.step = int(initial_step)

    return bus, cshunt


def _pf_from_pq(p_mw: float, q_mvar: float, default: float = 0.8) -> float:
    """
    Pf from pq.

    :param p_mw: p_mw parameter.
    :param q_mvar: q_mvar parameter.
    :param default: default parameter.
    :return: Function result.
    """
    s = math.sqrt(p_mw * p_mw + q_mvar * q_mvar)
    if s <= 0.0:
        return default
    pf = abs(p_mw) / s
    return max(0.0, min(1.0, pf))


def _convert_short_circuit_time_constant_to_open_circuit(
        short_circuit_time_constant: float,
        synchronous_or_transient_reactance: float,
        transient_or_subtransient_reactance: float,
) -> float:
    """Convert one PowerFactory short-circuit time constant.

    PowerFactory's standard ``TypSym`` DGS columns expose the short-circuit
    constants used by its native model.  VeraGrid's existing GENQEC parameter
    contract uses open-circuit constants, so the documented standard
    conversion must be explicit at the importer boundary.

    :param short_circuit_time_constant: Exported short-circuit constant in s.
    :param synchronous_or_transient_reactance: Numerator reactance in p.u.
    :param transient_or_subtransient_reactance: Denominator reactance in p.u.
    :return: Converted open-circuit constant, or zero for an absent rotor loop.
    """
    denominator: float = float(transient_or_subtransient_reactance)
    if short_circuit_time_constant > 0.0 and denominator > 0.0:
        result: float = (
            float(short_circuit_time_constant)
            * float(synchronous_or_transient_reactance)
            / denominator
        )
    else:
        # A zero q-axis transient constant identifies the salient-pole variant
        # and must remain structurally distinguishable from a numerical floor.
        result = 0.0
    return result


def _resolve_typ_sym_acceleration_time_constant(machine_type: TypSym) -> float:
    """Resolve the native acceleration time constant without inventing inertia.

    :param machine_type: Parsed synchronous-machine type.
    :return: Positive acceleration time constant, or zero when not exported.
    """
    if (
            machine_type.calculated_tag is not None
            and math.isfinite(float(machine_type.calculated_tag))
            and float(machine_type.calculated_tag) > 0.0
    ):
        result: float = float(machine_type.calculated_tag)
    else:
        if (
                machine_type.tag is not None
                and math.isfinite(float(machine_type.tag))
                and float(machine_type.tag) > 0.0
        ):
            result = float(machine_type.tag)
        else:
            # Zero is an explicit incomplete-data marker.  The ElmSym runtime
            # adapter refuses activation until a self-contained DGS provides
            # inertia, instead of silently tuning a project-specific fallback.
            result = 0.0
    return result


def _resolve_typ_sym_speed_variation_mode(
        machine_type: TypSym | None,
) -> SynchronousMachineSpeedVariationMode:
    """Translate the native three-state ``i_speedVar`` selector.

    A DGS that omits the optional field cannot prove that speed variation was
    enabled, so it receives the standard RMS simplification that freezes both
    stator-voltage terms at their initial synchronous speed.

    :param machine_type: Optional parsed synchronous-machine type.
    :return: Exact native stator-voltage speed treatment.
    """
    if machine_type is None or machine_type.speed_variation_mode is None:
        result: SynchronousMachineSpeedVariationMode = (
            SynchronousMachineSpeedVariationMode.Neglected
        )
    elif int(machine_type.speed_variation_mode) == 1:
        result = SynchronousMachineSpeedVariationMode.Considered
    elif int(machine_type.speed_variation_mode) == 2:
        result = SynchronousMachineSpeedVariationMode.PartiallyNeglected
    else:
        result = SynchronousMachineSpeedVariationMode.Neglected
    return result


def _resolve_typ_sym_saturation_curve(
        voltage_points: List[float | None],
        excitation_points: List[float | None],
) -> Tuple[np.ndarray, np.ndarray]:
    """Return aligned finite saturation-curve point arrays.

    :param voltage_points: Parsed magnetising-flux or voltage coordinates.
    :param excitation_points: Parsed excitation coordinates.
    :return: Two equal-length finite float arrays.
    """
    candidate_count: int = min(len(voltage_points), len(excitation_points))
    voltage_values: np.ndarray = np.empty(candidate_count, dtype=float)
    excitation_values: np.ndarray = np.empty(candidate_count, dtype=float)
    accepted_count: int = 0
    point_index: int
    for point_index in range(candidate_count):
        voltage_value: float | None = voltage_points[point_index]
        excitation_value: float | None = excitation_points[point_index]
        if voltage_value is not None and excitation_value is not None:
            parsed_voltage: float = float(voltage_value)
            parsed_excitation: float = float(excitation_value)
            if math.isfinite(parsed_voltage) and math.isfinite(parsed_excitation):
                voltage_values[accepted_count] = parsed_voltage
                excitation_values[accepted_count] = parsed_excitation
                accepted_count += 1
            else:
                pass
        else:
            pass
    else:
        pass
    return (
        voltage_values[:accepted_count].copy(),
        excitation_values[:accepted_count].copy(),
    )


def convert_dgs_to_generator(elmsym: ElmSym,
                             stacubic_dict: Dict[str, List[int]],
                             buses: List[dev.Bus],
                             typsym_dict: Dict[str, TypSym],
                             baseMVA: float,
                             logger: Logger,
                             cubics_by_objid: Dict[str, List[StaCubic]],
                             bus_by_term_id: Dict[str, dev.Bus],
                             parallel_index: int = 0,
                             parallel_count: int = 1,
                             use_power_flow_snapshot: bool = False,
                             capability_curve: IntQlim | None = None) -> Tuple[dev.Bus, dev.Generator]:
    """
    Convert dgs to generator.

    :param elmsym: elmsym parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param typsym_dict: typsym_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param use_power_flow_snapshot: Use solved reactive limits when available.
    :param use_power_flow_snapshot: Freeze exported solved P/Q when both result columns exist.
    :param capability_curve: Referenced active/reactive capability curve.
    :return: Function result.
    """
    name: str = _get_non_empty_name(elmsym.loc_name, f"Gen_{_ref_id(elmsym.ID)}")
    name = _get_parallel_device_name(name, parallel_index, parallel_count)
    generator_idtag: str = _get_parallel_device_idtag(
        _ref_id(elmsym.ID),
        parallel_index,
        parallel_count,
    )

    bus: dev.Bus = get_injection_bus(elm_id=elmsym.ID,
                                     stacubic_dict=stacubic_dict,
                                     buses=buses,
                                     cubics_by_objid=cubics_by_objid,
                                     bus_by_term_id=bus_by_term_id)

    # Slack/reference machine indicator (PowerFactory exports ip_ctrl=1 on the slack generator)
    if int(elmsym.ip_ctrl) == 1:
        bus.set_is_slack_at(t=None, val=True)
    else:
        pass

    # Resolve type
    typsym: TypSym | None = typsym_dict.get(elmsym.typ_id, None)
    if typsym is None:
        typsym = typsym_dict.get(_ref_id(elmsym.typ_id), None)
    else:
        pass

    has_solved_power: bool = (
        use_power_flow_snapshot
        and elmsym.m_p_bus1 is not None
        and elmsym.m_q_bus1 is not None
    )
    is_motor: bool = _is_elmsym_network_motor(elmsym=elmsym)
    if has_solved_power:
        # PowerFactory exports the aggregate terminal result.  Divide it only
        # because one native parallel row is expanded into individual devices.
        p_mw: float = float(elmsym.m_p_bus1) / float(parallel_count)
        q_mvar: float = float(elmsym.m_q_bus1) / float(parallel_count)
    else:
        if is_motor:
            # Configured motor schedules use positive equipment consumption,
            # while VeraGrid stores injections into the electrical network.
            p_mw = -float(elmsym.pgini)
            q_mvar = -float(elmsym.qgini)
        else:
            p_mw = float(elmsym.pgini)
            q_mvar = float(elmsym.qgini)

    # Voltage control
    vset: float = float(elmsym.usetp)

    if has_solved_power:
        # Snapshot mode validates the solved DGS operating point.  The native
        # controller is still retained separately as a StationController, but
        # it must not recompute a different Q while reproducing this snapshot.
        control_mode: GeneratorControlMode = GeneratorControlMode.Q
    else:
        if elmsym.av_mode != "":
            if elmsym.av_mode == "constv":
                control_mode = GeneratorControlMode.V
            else:
                control_mode = GeneratorControlMode.Q
        else:
            if elmsym.iv_mode != 0:
                control_mode = GeneratorControlMode.V
            else:
                control_mode = GeneratorControlMode.Q

    # Power factor (used mainly when not controlled)
    pf: float = float(elmsym.cosgini)
    if pf == 0.0 and typsym is not None:
        pf = typsym.cosn
    else:
        pass
    if pf == 0.0:
        pf = _pf_from_pq(p_mw=p_mw, q_mvar=q_mvar, default=0.8)
    else:
        pass

    # ``ElmSym.cosgini`` describes the dispatch operating point, whereas the
    # machine cable ``cosn`` and controller base changes use ``TypSym.cosn``.
    # Preserve both so RMS initialization retains the rated active-power base.
    if (
            typsym is not None
            and math.isfinite(float(typsym.cosn))
            and float(typsym.cosn) > 0.0
    ):
        rated_power_factor: float = float(typsym.cosn)
    else:
        rated_power_factor = pf

    # Nominal power
    snom: float = 9999.0
    if typsym is not None:
        snom = float(typsym.sgn)
    else:
        pass

    # PowerFactory defines ElmSym q_min/q_max in p.u. on the assigned
    # TypSym.sgn of one parallel unit.  Each expanded VeraGrid generator gets
    # one unit's limit; their aggregate therefore scales naturally with ngnum.
    qmin_raw: float = float(elmsym.q_min)
    qmax_raw: float = float(elmsym.q_max)
    if qmin_raw == 0.0 and typsym is not None:
        qmin_raw = float(typsym.q_min)
    else:
        pass
    if qmax_raw == 0.0 and typsym is not None:
        qmax_raw = float(typsym.q_max)
    else:
        pass

    if typsym is None or snom <= 0.0:
        reactive_power_base_mva: float = float(baseMVA)
        if qmin_raw == 0.0 and qmax_raw == 0.0:
            pass
        else:
            logger.add_warning(
                msg="ElmSym reactive limits use circuit base because TypSym.sgn is unavailable",
                device=name,
                device_class="ElmSym",
                value=reactive_power_base_mva,
            )
    else:
        reactive_power_base_mva = snom

    # Resolve a linked characteristic before selecting scalar limits. Some
    # projects reference a native IntQlim whose configured vectors are empty;
    # PowerFactory then exposes only the evaluated c:Qmin/c:Qmax interval in
    # the solved DGS. That explicit interval is the sole non-zero capability
    # contract available to an offline importer at the current dispatch.
    capability_curve_uses_motor_orientation: bool = bool(
        int(elmsym.i_mot) == 1
    )
    unvalidated_native_capability_points: List[Tuple[float, float, float]] | None = (
        _build_intqlim_q_points(
            capability_curve=capability_curve,
            rated_power_mva=reactive_power_base_mva,
            minimum_scale_percent=elmsym.scaleQmin,
            maximum_scale_percent=elmsym.scaleQmax,
        )
    )

    qmin_from_per_unit: float = qmin_raw * reactive_power_base_mva
    qmax_from_per_unit: float = qmax_raw * reactive_power_base_mva

    # PowerFactory's standard DGS monitor rounds q_min/q_max to three decimal
    # places.  On a large aggregate this can shift a physical capability by
    # several MVAr.  cQ_min/cQ_max are configured equipment attributes (no
    # colon), exported at DGS 7 precision, and are therefore the authoritative
    # normal-input limits when both form a valid interval.  They must not be
    # confused with the solved c:Qmin/c:Qmax calculation results.
    configured_qmin_mvar: float | None = elmsym.configured_qmin_mvar
    configured_qmax_mvar: float | None = elmsym.configured_qmax_mvar
    configured_limits_are_valid: bool = (
        configured_qmin_mvar is not None
        and configured_qmax_mvar is not None
        and math.isfinite(configured_qmin_mvar)
        and math.isfinite(configured_qmax_mvar)
        and configured_qmin_mvar <= configured_qmax_mvar
    )
    if configured_limits_are_valid:
        qmin: float = float(configured_qmin_mvar)
        qmax: float = float(configured_qmax_mvar)
    else:
        qmin = qmin_from_per_unit
        qmax = qmax_from_per_unit
    native_capability_points: List[Tuple[float, float, float]] | None = (
        _validate_intqlim_points_against_structural_limits(
            capability_curve=capability_curve,
            capability_points=unvalidated_native_capability_points,
            structural_minimum_mvar=qmin,
            structural_maximum_mvar=qmax,
        )
    )
    capability_points: List[Tuple[float, float, float]] | None = (
        _orient_capability_points_as_network_injection(
            capability_points=native_capability_points,
            is_motor=capability_curve_uses_motor_orientation,
        )
    )
    linked_curve_is_incomplete: bool = bool(
        capability_curve is not None
        and capability_points is None
    )
    configured_interval_is_collapsed: bool = bool(
        math.isclose(qmin, qmax, rel_tol=0.0, abs_tol=1.0e-12)
    )
    calculated_interval_is_valid: bool = bool(
        elmsym.calculated_qmin_mvar is not None
        and elmsym.calculated_qmax_mvar is not None
        and math.isfinite(float(elmsym.calculated_qmin_mvar))
        and math.isfinite(float(elmsym.calculated_qmax_mvar))
        and float(elmsym.calculated_qmin_mvar)
        <= float(elmsym.calculated_qmax_mvar)
    )
    use_evaluated_curve_fallback: bool = bool(
        linked_curve_is_incomplete
        and configured_interval_is_collapsed
        and calculated_interval_is_valid
    )
    qmin, qmax = _select_effective_reactive_limits(
        calculated_minimum_mvar=elmsym.calculated_qmin_mvar,
        calculated_maximum_mvar=elmsym.calculated_qmax_mvar,
        fallback_minimum_mvar=qmin,
        fallback_maximum_mvar=qmax,
        parallel_count=parallel_count,
        use_calculated_results=(
            use_power_flow_snapshot or use_evaluated_curve_fallback
        ),
    )
    # Station MaxReserve uses the native PowerFactory capability coordinate,
    # while Newton and Q-limit switching use network-injection limits.  Retain
    # both before any motor-axis orientation changes the physical interval.
    reserve_qmin: float = qmin
    reserve_qmax: float = qmax
    if is_motor:
        # The equipment-oriented interval [Qmin,Qmax] becomes
        # [-Qmax,-Qmin] when expressed as network injection.
        motor_qmin: float = -qmax
        motor_qmax: float = -qmin
        qmin = motor_qmin
        qmax = motor_qmax
    else:
        pass
    # ``i_mot`` defines the equipment-axis orientation of IntQlim even for a
    # synchronous condenser whose configured P/Q schedule is retained in the
    # generator convention.  Keep those two sign decisions independent.
    uses_native_reserve_coordinate: bool = bool(
        capability_curve_uses_motor_orientation
        and not is_motor
    )
    if capability_points is None:
        if capability_curve is None:
            pass
        else:
            logger.add_warning(
                msg="Incomplete ElmSym capability curve",
                device=name,
                value=_ref_id(capability_curve.ID),
                expected_value="Aligned finite P, Qmin and Qmax vectors",
                device_class="IntQlim",
            )
    else:
        # The linked curve supersedes the rounded scalar q_min/q_max columns.
        # Interpolating the current P keeps the scalar limits and the reusable
        # VeraGrid curve consistent from the first power-flow compilation.
        active_curve_axis: List[float] = list()
        minimum_curve_axis: List[float] = list()
        maximum_curve_axis: List[float] = list()
        curve_point: Tuple[float, float, float]
        for curve_point in capability_points:
            active_curve_axis.append(curve_point[0])
            minimum_curve_axis.append(curve_point[1])
            maximum_curve_axis.append(curve_point[2])
        else:
            pass
        qmin = float(np.interp(
            p_mw,
            active_curve_axis,
            minimum_curve_axis,
        ))
        qmax = float(np.interp(
            p_mw,
            active_curve_axis,
            maximum_curve_axis,
        ))
        if (
                uses_native_reserve_coordinate
                and native_capability_points is not None
        ):
            native_active_axis: List[float] = list()
            native_minimum_axis: List[float] = list()
            native_maximum_axis: List[float] = list()
            native_curve_point: Tuple[float, float, float]
            for native_curve_point in native_capability_points:
                native_active_axis.append(native_curve_point[0])
                native_minimum_axis.append(native_curve_point[1])
                native_maximum_axis.append(native_curve_point[2])
            else:
                pass
            reserve_qmin = float(np.interp(
                p_mw,
                native_active_axis,
                native_minimum_axis,
            ))
            reserve_qmax = float(np.interp(
                p_mw,
                native_active_axis,
                native_maximum_axis,
            ))
        else:
            reserve_qmin = qmin
            reserve_qmax = qmax

    # Active-power limits are declared in MW by the DGS schema.  Absence must
    # retain VeraGrid's permissive defaults, while an explicit zero remains a
    # real zero; applying a p.u. heuristic here corrupts both cases.
    pmin_source: float | None = elmsym.Pmin_uc
    pmax_source: float | None = elmsym.Pmax_uc
    if pmin_source is None:
        pmin: float = 0.0
    else:
        pmin = float(pmin_source)
    if pmax_source is None:
        pmax: float = 9999.0
    else:
        pmax = float(pmax_source)
    if is_motor:
        motor_pmin: float = -pmax
        motor_pmax: float = -pmin
        pmin = motor_pmin
        pmax = motor_pmax
    else:
        pass

    saturation_voltage_points: np.ndarray
    saturation_excitation_points: np.ndarray
    saturation_q_voltage_points: np.ndarray
    saturation_q_excitation_points: np.ndarray
    if typsym is None:
        saturation_voltage_points = np.zeros(0, dtype=float)
        saturation_excitation_points = np.zeros(0, dtype=float)
        saturation_q_voltage_points = np.zeros(0, dtype=float)
        saturation_q_excitation_points = np.zeros(0, dtype=float)
    else:
        saturation_voltage_points, saturation_excitation_points = (
            _resolve_typ_sym_saturation_curve(
                voltage_points=typsym.saturation_voltage_points,
                excitation_points=typsym.saturation_excitation_points,
            )
        )
        saturation_q_voltage_points, saturation_q_excitation_points = (
            _resolve_typ_sym_saturation_curve(
                voltage_points=typsym.saturation_q_voltage_points,
                excitation_points=typsym.saturation_q_excitation_points,
            )
        )

    gen: dev.Generator = dev.Generator(name=name,
                        idtag=generator_idtag,
                        P=p_mw,
                        Q=q_mvar,
                        power_factor=pf,
                        rated_power_factor=rated_power_factor,
                        vset=vset,
                        control_mode=control_mode,
                        Qmin=qmin,
                        Qmax=qmax,
                        Qmin_reserve=reserve_qmin,
                        Qmax_reserve=reserve_qmax,
                        initial_reactive_limit_state=_get_initial_reactive_limit_state(
                            source_state=elmsym.calculated_q_limit_state,
                            solved_reactive_power_mvar=(
                                None
                                if elmsym.m_q_bus1 is None
                                else float(elmsym.m_q_bus1) / float(parallel_count)
                            ),
                            minimum_reactive_power_mvar=qmin,
                            maximum_reactive_power_mvar=qmax,
                        ),
                        Snom=snom,
                        Rs=(0.0 if typsym is None else float(typsym.rstr)),
                        rms_acceleration_time_constant=(
                            0.0
                            if typsym is None
                            else _resolve_typ_sym_acceleration_time_constant(typsym)
                        ),
                        rms_dpu=(
                            0.0
                            if typsym is None or typsym.dpu is None
                            else float(typsym.dpu)
                        ),
                        rms_dkd=(
                            0.0
                            if typsym is None or typsym.dkd is None
                            else float(typsym.dkd)
                        ),
                        rms_dpe=(
                            0.0
                            if typsym is None or typsym.dpe is None
                            else float(typsym.dpe)
                        ),
                        rms_rotor_coupling_reactance_d=(
                            0.0
                            if typsym is None or typsym.xrl is None
                            else float(typsym.xrl)
                        ),
                        rms_rotor_coupling_reactance_q=(
                            0.0
                            if typsym is None
                            else float(typsym.xrlq)
                        ),
                        rms_td_prime_short_circuit=(
                            0.0
                            if typsym is None
                            else float(typsym.tds)
                        ),
                        rms_tq_prime_short_circuit=(
                            0.0
                            if typsym is None
                            else float(typsym.tqs)
                        ),
                        rms_td_2prime_short_circuit=(
                            0.0
                            if typsym is None
                            else float(typsym.tdss)
                        ),
                        rms_tq_2prime_short_circuit=(
                            0.0
                            if typsym is None
                            else float(typsym.tqss)
                        ),
                        rms_excitation_base_mode=(
                            0
                            if elmsym.excitation_base_mode is None
                            else int(elmsym.excitation_base_mode)
                        ),
                        rms_excitation_current_base=(
                            1.0
                            if (
                                elmsym.excitation_current_base is None
                                or float(elmsym.excitation_current_base) <= 0.0
                            )
                            else float(elmsym.excitation_current_base)
                        ),
                        rms_excitation_voltage_base_ratio=(
                            1.0
                            if (
                                elmsym.excitation_voltage_base_ratio is None
                                or float(
                                    elmsym.excitation_voltage_base_ratio
                                ) <= 0.0
                            )
                            else float(elmsym.excitation_voltage_base_ratio)
                        ),
                        rms_constant_field_voltage=(
                            0.0
                            if elmsym.constant_field_voltage is None
                            else float(elmsym.constant_field_voltage)
                        ),
                        rms_excitation_gain=(
                            0.0
                            if elmsym.calculated_excitation_gain is None
                            else float(elmsym.calculated_excitation_gain)
                        ),
                        rms_rated_field_voltage=(
                            0.0
                            if elmsym.calculated_rated_field_voltage is None
                            else float(elmsym.calculated_rated_field_voltage)
                        ),
                        # Preserve ``c:ie`` only as an oracle reference.  The
                        # RMS initializer must solve its own consistent field
                        # voltage from the imported network and model equations.
                        rms_initial_field_voltage=(
                            0.0
                            if elmsym.calculated_initial_field_voltage is None
                            else float(elmsym.calculated_initial_field_voltage)
                        ),
                        rms_saturation_curve_type=(
                            0
                            if typsym is None or typsym.isat is None
                            else int(typsym.isat)
                        ),
                        rms_saturation_axis_mode=(
                            0
                            if typsym is None or typsym.isat_salient is None
                            else int(typsym.isat_salient)
                        ),
                        rms_saturation_data_source=(
                            0
                            if typsym is None or typsym.iusesat is None
                            else int(typsym.iusesat)
                        ),
                        rms_saturation_smoothing_factor=(
                            0.0
                            if (
                                typsym is None
                                or typsym.saturation_smoothing_factor is None
                            )
                            else float(typsym.saturation_smoothing_factor)
                        ),
                        rms_speed_variation_mode=(
                            _resolve_typ_sym_speed_variation_mode(
                                machine_type=typsym,
                            )
                        ),
                        rms_saturation_sg10=(
                            0.0
                            if typsym is None or typsym.sg10 is None
                            else float(typsym.sg10)
                        ),
                        rms_saturation_sg12=(
                            0.0
                            if typsym is None or typsym.sg12 is None
                            else float(typsym.sg12)
                        ),
                        rms_saturation_sg10q=(
                            0.0
                            if typsym is None or typsym.sg10q is None
                            else float(typsym.sg10q)
                        ),
                        rms_saturation_sg12q=(
                            0.0
                            if typsym is None or typsym.sg12q is None
                            else float(typsym.sg12q)
                        ),
                        rms_saturation_voltage_points=saturation_voltage_points,
                        rms_saturation_excitation_points=saturation_excitation_points,
                        rms_saturation_q_voltage_points=saturation_q_voltage_points,
                        rms_saturation_q_excitation_points=saturation_q_excitation_points,
                        Xd=(1.8 if typsym is None else float(typsym.xd)),
                        Xq=(1.7 if typsym is None else float(typsym.xq)),
                        Xd_prime=(0.3 if typsym is None else float(typsym.xds)),
                        Xq_prime=(0.55 if typsym is None else float(typsym.xqs)),
                        Xd_2prime=(0.25 if typsym is None else float(typsym.xdss)),
                        Xq_2prime=(0.35 if typsym is None else float(typsym.xqss)),
                        Xl=(0.15 if typsym is None else float(typsym.xl)),
                        Td0_prime=(
                            8.0
                            if typsym is None
                            else _convert_short_circuit_time_constant_to_open_circuit(
                                short_circuit_time_constant=float(typsym.tds),
                                synchronous_or_transient_reactance=float(typsym.xd),
                                transient_or_subtransient_reactance=float(typsym.xds),
                            )
                        ),
                        Tq0_prime=(
                            0.4
                            if typsym is None
                            else _convert_short_circuit_time_constant_to_open_circuit(
                                short_circuit_time_constant=float(typsym.tqs),
                                synchronous_or_transient_reactance=float(typsym.xq),
                                transient_or_subtransient_reactance=float(typsym.xqs),
                            )
                        ),
                        Td0_2prime=(
                            0.03
                            if typsym is None
                            else _convert_short_circuit_time_constant_to_open_circuit(
                                short_circuit_time_constant=float(typsym.tdss),
                                synchronous_or_transient_reactance=float(typsym.xds),
                                transient_or_subtransient_reactance=float(typsym.xdss),
                            )
                        ),
                        Tq0_2prime=(
                            0.05
                            if typsym is None
                            else _convert_short_circuit_time_constant_to_open_circuit(
                                short_circuit_time_constant=float(typsym.tqss),
                                # For the salient-pole variant PowerFactory's
                                # documented conversion uses Xq because Xq' and
                                # Tq' do not belong to the one-loop model.
                                synchronous_or_transient_reactance=(
                                    float(typsym.xq)
                                    if float(typsym.tqs) <= 0.0
                                    else float(typsym.xqs)
                                ),
                                transient_or_subtransient_reactance=float(typsym.xqss),
                            )
                        ),
                        q_points=capability_points,
                        use_reactive_power_curve=capability_points is not None,
                        active=(elmsym.outserv == 0),
                        Pmin=pmin,
                        Pmax=pmax,
                        Sbase=baseMVA)

    # Optional sequence data from type (best-effort, may not exist in all exports)
    if typsym is not None:
        r1 = typsym.rstr

        # X1 is used by short-circuit calculations.  PowerFactory documents
        # ``xdsss`` as the saturated subtransient reactance, whereas ``xd`` is
        # the much larger synchronous reactance and is not an equivalent.
        if float(typsym.xdsss) != 0.0:
            x1: float = float(typsym.xdsss)
        else:
            if typsym.xstr is None:
                x1 = float(typsym.xd)
            else:
                x1 = float(typsym.xstr)

        if typsym.xstr is None or float(typsym.xstr) == 0.0 or float(typsym.xdsss) == 0.0:
            pass
        else:
            if not math.isclose(float(typsym.xstr), float(typsym.xdsss), rel_tol=1e-6, abs_tol=1e-9):
                logger.add_warning(
                    msg="TypSym xstr differs from documented xdsss; using xdsss for Generator.X1",
                    device=name,
                    device_class="TypSym",
                    value=float(typsym.xstr),
                    expected_value=float(typsym.xdsss),
                )
            else:
                pass

        if r1 != 0.0 or x1 != 0.0:
            gen.R1 = float(r1)
            gen.X1 = float(x1)
        else:
            pass

        if float(typsym.r0sy) != 0.0 or float(typsym.x0sy) != 0.0:
            gen.R0 = float(typsym.r0sy)
            gen.X0 = float(typsym.x0sy)
        else:
            pass

        if float(typsym.r2sy) != 0.0 or float(typsym.x2sy) != 0.0:
            gen.R2 = float(typsym.r2sy)
            gen.X2 = float(typsym.x2sy)
        else:
            pass

    return bus, gen


def convert_dgs_to_asm_generator(elmasm: ElmAsm,
                                 stacubic_dict: Dict[str, List[int]],
                                 buses: List[dev.Bus],
                                 typasmo_dict: Dict[str, TypAsmo],
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus],
                                 parallel_index: int = 0,
                                 parallel_count: int = 1) -> Tuple[dev.Bus, dev.Generator]:
    """
    Convert dgs to asm generator.

    :param elmasm: elmasm parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param typasmo_dict: typasmo_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """

    name = _get_non_empty_name(elmasm.loc_name, f"ElmAsm_{_ref_id(elmasm.ID)}")
    name = _get_parallel_device_name(name, parallel_index, parallel_count)
    generator_idtag = _get_parallel_device_idtag(_ref_id(elmasm.ID), parallel_index, parallel_count)

    # Bus resolution must be StaCubic-based (PowerFactory connectivity)
    bus = get_injection_bus(elm_id=elmasm.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    if elmasm.i_mot == 0:  # Check that the asynchronous machine is a Generator

        if elmasm.idfig == 0:  # Also check that it is a Standard Asynchronous Machine

            if elmasm.bustp == 'AS' and elmasm.pmode == 0:  # Finally, check the bus type and the power input mode

                P: float = float(elmasm.pgini)  # AG active power P

                typasmo: TypAsmo | None = typasmo_dict.get(elmasm.typ_id, None)  # AG type

                if typasmo is not None:

                    Sr = float(typasmo.sgn) * 1e-3  # Rated apparent power [MVA]
                    Rs = float(typasmo.rstr)  # Stator resistance [pu]
                    Xs = float(typasmo.xstr)  # Stator reactance [pu]
                    Xm = float(typasmo.xm)  # Magnetising reactance [pu]
                    Rr = float(typasmo.rrtrA)  # Rotor resistance [pu]
                    Xr = float(typasmo.xrtrA)  # Rotor reactance [pu]

                    gen = dev.Generator(name=name,
                                        idtag=generator_idtag,
                                        P=P,
                                        power_factor=1.0,
                                        control_mode=GeneratorControlMode.Q,
                                        Snom=Sr,
                                        active=(elmasm.outserv == 0),
                                        Rs=Rs,
                                        Xs=Xs,
                                        Xm=Xm,
                                        Rr=Rr,
                                        Xr=Xr,
                                        tpe=GeneratorType.Asynchronous)



                else:
                    logger.add_warning(
                        msg=f"The Asynchronous Generator does not have an assigned type (TypAsmo).",
                        device=name,
                        device_class="ElmAsm",
                        value=typasmo
                    )

                    gen = dev.Generator(name=name,
                                        idtag=generator_idtag,
                                        P=P,
                                        power_factor=1.0,
                                        control_mode=GeneratorControlMode.Q,
                                        Snom=P,
                                        active=(elmasm.outserv == 0),
                                        tpe=GeneratorType.Asynchronous)

            else:
                logger.add_warning(
                    msg=f"Bus type is not AS or the input mode is not Electrical power.",
                    device=name,
                    device_class="ElmAsm",
                    value=elmasm.bustp
                )

                gen = dev.Generator(name=name,
                                    idtag=generator_idtag,
                                    P=0.0,
                                    power_factor=1.0,
                                    control_mode=GeneratorControlMode.Q,
                                    active=(elmasm.outserv == 0),
                                    tpe=GeneratorType.Asynchronous)

        else:
            logger.add_warning(
                msg=f"The AG is not an Standard Asynchronous Machine.",
                device=name,
                device_class="ElmAsm",
                value=elmasm.idfig
            )

            gen = dev.Generator(name=name,
                                idtag=generator_idtag,
                                P=0.0,
                                power_factor=1.0,
                                control_mode=GeneratorControlMode.Q,
                                active=(elmasm.outserv == 0),
                                tpe=GeneratorType.Asynchronous)

    else:
        logger.add_warning(
            msg=f"The asynchronous machine is not a generator, is a motor!",
            device=name,
            device_class="ElmAsm",
            value=elmasm.i_mot
        )

        gen = dev.Generator(name=name,
                            idtag=generator_idtag,
                            P=0.0,
                            power_factor=1.0,
                            control_mode=GeneratorControlMode.Q,
                            active=(elmasm.outserv == 0),
                            tpe=GeneratorType.Asynchronous)

    return bus, gen


def _get_station_control_mode(source_code: int, controller_name: str, logger: Logger) -> StationControlMode:
    """
    Convert one native ``ElmStactrl.i_ctrl`` code without string options.

    :param source_code: Native PowerFactory control-mode code.
    :param controller_name: Controller name used in diagnostics.
    :param logger: Import diagnostic sink.
    :return: Typed station-control mode.
    """
    if source_code == 0:
        result: StationControlMode = StationControlMode.Voltage
    else:
        if source_code == 1:
            result = StationControlMode.ReactivePower
        else:
            if source_code == 2:
                result = StationControlMode.PowerFactor
            else:
                if source_code == 3:
                    result = StationControlMode.TanPhi
                else:
                    result = StationControlMode.Voltage
                    logger.add_warning(
                        msg="Unsupported ElmStactrl control mode",
                        device=controller_name,
                        value=source_code,
                        expected_value="0..3",
                        device_class="ElmStactrl",
                    )
    return result


def _get_station_bus_selection(
        source_code: int,
        controller_name: str,
        logger: Logger,
) -> StationControlBusSelection:
    """Translate one PowerFactory controlled-node selector.

    :param source_code: Native ``selBus`` integer.
    :param controller_name: Controller name used by diagnostics.
    :param logger: Import diagnostic sink.
    :return: Typed VeraGrid controlled-bus selection.
    """
    result: StationControlBusSelection = StationControlBusSelection.Explicit
    if source_code == 0:
        pass
    elif source_code == 1:
        result = StationControlBusSelection.Automatic
    else:
        logger.add_warning(
            msg="Unsupported ElmStactrl controlled-node selector",
            device=controller_name,
            value=source_code,
            expected_value="0..1",
            device_class="ElmStactrl",
        )
    return result


def _get_station_voltage_setpoint_mode(
        source_code: int,
        controller_name: str,
        logger: Logger,
) -> StationVoltageSetpointMode:
    """Translate one PowerFactory station voltage-target selector.

    :param source_code: Native ``uset_mode`` integer.
    :param controller_name: Controller name used by diagnostics.
    :param logger: Import diagnostic sink.
    :return: Typed voltage-target source.
    """
    result: StationVoltageSetpointMode = StationVoltageSetpointMode.StationController
    if source_code == 0:
        pass
    elif source_code == 1:
        result = StationVoltageSetpointMode.BusTargetVoltage
    else:
        logger.add_warning(
            msg="Unsupported ElmStactrl voltage setpoint mode",
            device=controller_name,
            value=source_code,
            expected_value="0..1",
            device_class="ElmStactrl",
        )
    return result


def _get_station_distribution_mode(
        source_code: int,
        controller_name: str,
        logger: Logger,
) -> StationReactivePowerDistribution:
    """
    Preserve one native ``ElmStactrl.imode`` code as a typed selector.

    :param source_code: Native PowerFactory distribution code.
    :param controller_name: Controller name used in diagnostics.
    :param logger: Import diagnostic sink.
    :return: Typed native distribution selector.
    """
    if source_code == 0:
        result: StationReactivePowerDistribution = (
            StationReactivePowerDistribution.AccordingToDispatchedActivePower
        )
    else:
        if source_code == 1:
            result = StationReactivePowerDistribution.AccordingToRatedPower
        else:
            if source_code == 2:
                result = StationReactivePowerDistribution.IndividualReactivePower
            else:
                if source_code == 3:
                    result = StationReactivePowerDistribution.MaximiseReactiveReserve
                else:
                    if source_code == 4:
                        result = StationReactivePowerDistribution.VoltageSetpointAdaption
                    else:
                        result = StationReactivePowerDistribution.AccordingToDispatchedActivePower
                        logger.add_warning(
                            msg="Unsupported ElmStactrl reactive distribution",
                            device=controller_name,
                            value=source_code,
                            expected_value="0..4",
                            device_class="ElmStactrl",
                        )
    return result


def _get_station_transformer_control_side(source_code: int,
                                          controller_name: str,
                                          logger: Logger) -> StationTransformerControlSide:
    """Return the typed transformer-control side for one native code.

    :param source_code: Native ``ElmStactrl.iTrfCtrl`` code.
    :param controller_name: Controller name used in diagnostics.
    :param logger: Import diagnostic sink.
    :return: Typed PowerFactory control-side selector.
    """
    if source_code == 0:
        result: StationTransformerControlSide = StationTransformerControlSide.NoControl
    else:
        if source_code == 1:
            result = StationTransformerControlSide.HighVoltageSide
        else:
            if source_code == 2:
                result = StationTransformerControlSide.LowVoltageSide
            else:
                result = StationTransformerControlSide.NoControl
                logger.add_warning(
                    msg="Unsupported ElmStactrl transformer control side",
                    device=controller_name,
                    value=source_code,
                    expected_value="0..2",
                    device_class="ElmStactrl",
                )
    return result


def _get_station_reactive_change_response(source_code: int,
                                           controller_name: str,
                                           logger: Logger) -> str:
    """Return the localized reactive-change response for one native code.

    :param source_code: Native ``ElmStactrl.iQorient`` code.
    :param controller_name: Controller name used in diagnostics.
    :param logger: Import diagnostic sink.
    :return: Humanized PowerFactory reactive response label.
    """
    if source_code == 0:
        result: str = "same"
    else:
        if source_code == 1:
            result = "opposite"
        else:
            result = f"Unsupported source code {source_code}"
            logger.add_warning(
                msg="Unsupported ElmStactrl reactive change response",
                device=controller_name,
                value=source_code,
                expected_value="0..1",
                device_class="ElmStactrl",
            )
    return result


def _serialize_station_reference_vector(values: List[str | None]) -> str:
    """Serialize one aligned reference vector without compacting empty slots.

    :param values: Native position-preserving DGS references.
    :return: Semicolon-separated references with empty placeholders.
    """
    serialized_values: List[str] = list(("",) * len(values))
    value_index: int
    for value_index in range(len(values)):
        value: str | None = values[value_index]
        if value is None:
            serialized_values[value_index] = ""
        else:
            serialized_values[value_index] = _ref_id(value)
    else:
        pass
    return ";".join(serialized_values)


def _serialize_station_float_vector(values: List[float | None]) -> str:
    """Serialize one aligned numeric vector in stable human-readable form.

    :param values: Native position-preserving optional numeric values.
    :return: Semicolon-separated numbers with empty placeholders.
    """
    serialized_values: List[str] = list(("",) * len(values))
    value_index: int
    for value_index in range(len(values)):
        value: float | None = values[value_index]
        if value is None:
            serialized_values[value_index] = ""
        else:
            serialized_values[value_index] = format(float(value), ".15g")
    else:
        pass
    return ";".join(serialized_values)


def _serialize_station_int_vector(values: List[int | None]) -> str:
    """Serialize one aligned integer vector without compacting empty slots.

    :param values: Native position-preserving optional integer values.
    :return: Semicolon-separated integers with empty placeholders.
    """
    serialized_values: List[str] = list(("",) * len(values))
    value_index: int
    for value_index in range(len(values)):
        value: int | None = values[value_index]
        if value is None:
            serialized_values[value_index] = ""
        else:
            serialized_values[value_index] = str(int(value))
    else:
        pass
    return ";".join(serialized_values)


def _get_station_machine_voltage_target(
        controller: dev.StationController,
        source_machine_id: str,
        default_voltage: float,
) -> float:
    """Resolve one aligned ``cvgen`` target without shifting sparse slots.

    :param controller: Shared controller retaining aligned machine metadata.
    :param source_machine_id: Original DGS equipment FID.
    :param default_voltage: Device-native target used when ``cvgen`` is absent.
    :return: Finite local voltage target in p.u.
    """
    machine_ids: List[str] = controller.machine_device_ids.split(";")
    target_values: List[str] = controller.individual_voltage_targets.split(";")
    selected_voltage: float = float(default_voltage)
    machine_index: int
    for machine_index in range(len(machine_ids)):
        if machine_ids[machine_index].strip() != source_machine_id:
            pass
        elif machine_index >= len(target_values) or target_values[machine_index].strip() == "":
            pass
        else:
            try:
                candidate_voltage: float = float(target_values[machine_index])
                if math.isfinite(candidate_voltage):
                    selected_voltage = candidate_voltage
                else:
                    pass
            except ValueError:
                pass
    else:
        pass
    return selected_voltage


def _build_station_closed_coupler_adjacency(
        dgs_grid: DgsCircuit,
        cubics_by_objid: Dict[str, List[StaCubic]],
) -> Dict[str, List[str]]:
    """Build terminal adjacency using closed physical couplers only.

    Lines and transformers deliberately do not join equipotential areas.  A
    station search may reach their terminal, but must stop at the impedance.

    :param dgs_grid: Parsed DGS circuit.
    :param cubics_by_objid: Equipment cubicles keyed by source FID.
    :return: Closed-coupler terminal adjacency.
    """
    adjacency: Dict[str, List[str]] = dict()
    source_coupler: ElmCoup
    for source_coupler in dgs_grid.elmcoups:
        terminal_ids: List[str] = get_terminal_ids(
            element_id=source_coupler.ID,
            cubics_by_objid=cubics_by_objid,
        )
        is_closed_pair: bool = int(source_coupler.on_off) != 0 and len(terminal_ids) == 2
        if is_closed_pair:
            first_terminal_id: str = terminal_ids[0]
            second_terminal_id: str = terminal_ids[1]
            first_neighbours: List[str] | None = adjacency.get(first_terminal_id, None)
            if first_neighbours is None:
                first_neighbours = list()
                adjacency[first_terminal_id] = first_neighbours
            else:
                pass
            second_neighbours: List[str] | None = adjacency.get(second_terminal_id, None)
            if second_neighbours is None:
                second_neighbours = list()
                adjacency[second_terminal_id] = second_neighbours
            else:
                pass
            first_neighbours.append(second_terminal_id)
            second_neighbours.append(first_terminal_id)
        else:
            pass
    else:
        pass
    return adjacency


def _get_station_equipotential_terminal_ids(
        start_terminal_id: str,
        adjacency: Dict[str, List[str]],
) -> List[str]:
    """Return every terminal connected through closed couplers.

    :param start_terminal_id: First terminal in the equipotential area.
    :param adjacency: Closed-coupler terminal adjacency.
    :return: Deterministically sorted terminal FIDs.
    """
    visited_terminal_ids: Set[str] = set()
    pending_terminal_ids: List[str] = list((start_terminal_id,))
    while len(pending_terminal_ids) > 0:
        terminal_id: str = pending_terminal_ids.pop()
        if terminal_id in visited_terminal_ids:
            pass
        else:
            visited_terminal_ids.add(terminal_id)
            adjacent_terminal_id: str
            for adjacent_terminal_id in adjacency.get(terminal_id, list()):
                if adjacent_terminal_id in visited_terminal_ids:
                    pass
                else:
                    pending_terminal_ids.append(adjacent_terminal_id)
            else:
                pass
    return sorted(visited_terminal_ids)


def _is_better_station_control_terminal(
        candidate: ElmTerm,
        selected: ElmTerm | None,
) -> bool:
    """Compare native priority and busbar status without relying on DGS order.

    :param candidate: Eligible control-terminal candidate.
    :param selected: Current selection, or ``None``.
    :return: Whether the candidate must replace the current selection.
    """
    is_better: bool = selected is None
    if selected is None:
        pass
    else:
        candidate_priority: int = (
            2147483647
            if candidate.ivpriority is None or int(candidate.ivpriority) < 0
            else int(candidate.ivpriority)
        )
        selected_priority: int = (
            2147483647
            if selected.ivpriority is None or int(selected.ivpriority) < 0
            else int(selected.ivpriority)
        )
        if candidate_priority < selected_priority:
            is_better = True
        elif candidate_priority > selected_priority:
            is_better = False
        else:
            candidate_is_busbar: bool = int(candidate.iUsage) == 0
            selected_is_busbar: bool = int(selected.iUsage) == 0
            if candidate_is_busbar and not selected_is_busbar:
                is_better = True
            elif selected_is_busbar and not candidate_is_busbar:
                is_better = False
            else:
                is_better = _ref_id(candidate.ID) < _ref_id(selected.ID)
    return is_better


def _select_station_equipotential_control_terminal(
        terminal_ids: List[str],
        terminal_by_id: Dict[str, ElmTerm],
        minimum_voltage_kv: float,
) -> ElmTerm | None:
    """Select one native-priority bus from an equipotential area.

    :param terminal_ids: Terminal FIDs in one closed-switch component.
    :param terminal_by_id: Parsed terminals keyed by FID.
    :param minimum_voltage_kv: Automatic station-search voltage threshold.
    :return: Selected active terminal, or ``None``.
    """
    selected: ElmTerm | None = None
    terminal_id: str
    for terminal_id in terminal_ids:
        candidate: ElmTerm | None = terminal_by_id.get(terminal_id, None)
        if candidate is None:
            priority_is_eligible: bool = False
        else:
            # A negative voltage-control priority disables this terminal.
            # ``None`` is retained only as the explicit legacy-DGS fallback;
            # the importer emits a warning when that fallback is selected.
            priority_is_eligible = (
                candidate.ivpriority is None
                or int(candidate.ivpriority) >= 0
            )
        is_eligible: bool = (
            candidate is not None
            and priority_is_eligible
            and int(candidate.outserv or 0) == 0
            and int(candidate.iUsage) == 0
            and float(candidate.uknom) + 1e-12 >= minimum_voltage_kv
        )
        if is_eligible and candidate is not None:
            if _is_better_station_control_terminal(candidate=candidate, selected=selected):
                selected = candidate
            else:
                pass
        else:
            pass
    else:
        pass
    return selected


def _build_station_step_up_associations(
        source_controller: ElmStactrl,
        explicit_control_bus_id: str | None,
        transformers_by_terminal_id: Dict[str, List[ElmTr2]],
        terminal_by_id: Dict[str, ElmTerm],
        cubics_by_objid: Dict[str, List[StaCubic]],
        switch_by_cubic_id: Dict[str, StaSwitch],
        closed_coupler_adjacency: Dict[str, List[str]],
        logger: Logger,
) -> Tuple[List[str | None], List[str | None], bool]:
    """Resolve aligned machine-to-step-up-to-control-bus relations.

    :param source_controller: Native station controller.
    :param explicit_control_bus_id: Explicit/calculated controller bus, if present.
    :param transformers_by_terminal_id: Transformer candidates by terminal FID.
    :param terminal_by_id: Native terminals keyed by FID.
    :param cubics_by_objid: Equipment cubicles keyed by source FID.
    :param switch_by_cubic_id: Cubicle switch states keyed by cubic FID.
    :param closed_coupler_adjacency: Closed-coupler equipotential topology.
    :param logger: Import diagnostic sink.
    :return: Aligned transformer IDs, control-bus IDs and metadata completeness.
    """
    transformer_ids: List[str | None] = list()
    control_bus_ids: List[str | None] = list()
    metadata_complete: bool = True
    connection_vector_present: bool = len(source_controller.cconn) > 0
    uses_step_up_control: bool = int(source_controller.iTrfCtrl) != 0
    machine_index: int
    for machine_index in range(len(source_controller.psym)):
        selected_transformer_id: str | None = None
        selected_control_bus_id: str | None = None
        machine_pointer: str | None = source_controller.psym[machine_index]
        machine_is_connected: bool = (
            machine_pointer is not None
            and (
                not connection_vector_present
                or (
                    machine_index < len(source_controller.cconn)
                    and source_controller.cconn[machine_index] == 1
                )
            )
        )
        if machine_is_connected and machine_pointer is not None and uses_step_up_control:
            machine_terminal_ids: List[str] = get_terminal_ids(
                element_id=machine_pointer,
                cubics_by_objid=cubics_by_objid,
            )
            direct_transformers: List[ElmTr2] = list()
            machine_terminal_id: str
            for machine_terminal_id in machine_terminal_ids:
                candidate_transformer: ElmTr2
                for candidate_transformer in transformers_by_terminal_id.get(
                    machine_terminal_id,
                    list(),
                ):
                    candidate_is_active: bool = (
                        int(candidate_transformer.outserv) == 0
                        and _is_element_closed_by_cubicle_switches(
                            element_id=candidate_transformer.ID,
                            cubics_by_objid=cubics_by_objid,
                            switch_by_cubic_id=switch_by_cubic_id,
                        )
                    )
                    if candidate_is_active and candidate_transformer not in direct_transformers:
                        direct_transformers.append(candidate_transformer)
                    else:
                        pass
                else:
                    pass
            else:
                pass

            has_unique_step_up: bool = (
                len(machine_terminal_ids) == 1
                and len(direct_transformers) == 1
            )
            if has_unique_step_up:
                selected_transformer: ElmTr2 = direct_transformers[0]
                selected_transformer_id = _ref_id(selected_transformer.ID)
                transformer_terminal_ids: List[str] = get_terminal_ids(
                    element_id=selected_transformer.ID,
                    cubics_by_objid=cubics_by_objid,
                )
                remote_terminal_id: str | None = None
                transformer_terminal_id: str
                for transformer_terminal_id in transformer_terminal_ids:
                    if transformer_terminal_id == machine_terminal_ids[0]:
                        pass
                    else:
                        remote_terminal_id = transformer_terminal_id
                else:
                    pass

                if explicit_control_bus_id is not None:
                    selected_control_bus_id = explicit_control_bus_id
                elif remote_terminal_id is None:
                    pass
                else:
                    equipotential_terminal_ids: List[str] = _get_station_equipotential_terminal_ids(
                        start_terminal_id=remote_terminal_id,
                        adjacency=closed_coupler_adjacency,
                    )
                    selected_terminal: ElmTerm | None = _select_station_equipotential_control_terminal(
                        terminal_ids=equipotential_terminal_ids,
                        terminal_by_id=terminal_by_id,
                        minimum_voltage_kv=max(0.0, float(source_controller.selAutoUn)),
                    )
                    if selected_terminal is None:
                        logger.add_warning(
                            msg="Station step-up has no eligible equipotential busbar",
                            device=_ref_id(machine_pointer),
                            value=remote_terminal_id,
                            expected_value=(
                                f"Active busbar >= {float(source_controller.selAutoUn):g} kV"
                            ),
                            device_class="ElmStactrl",
                        )
                    else:
                        selected_control_bus_id = _ref_id(selected_terminal.ID)
                        if selected_terminal.ivpriority is None:
                            metadata_complete = False
                        else:
                            pass
            else:
                logger.add_warning(
                    msg="Station machine has no unique active step-up transformer",
                    device=_ref_id(machine_pointer),
                    value=len(direct_transformers),
                    expected_value=1,
                    device_class="ElmStactrl",
                )
        else:
            pass
        transformer_ids.append(selected_transformer_id)
        control_bus_ids.append(selected_control_bus_id)
    else:
        pass
    return transformer_ids, control_bus_ids, metadata_complete


def _resolve_station_controller_bus(
        pointer_candidates: List[str | None],
        bus_by_term_id: Dict[str, dev.Bus],
        cubic_by_id: Dict[str, StaCubic],
) -> dev.Bus | None:
    """Resolve an explicit station pointer to its imported electrical bus.

    PowerFactory can serialize a station node either as an ``ElmTerm`` pointer
    or as a ``StaCubic`` pointer.  Keeping this resolution in one typed helper
    lets the caller preserve the semantic distinction between continuous
    control pointers and structural step-up topology pointers.

    :param pointer_candidates: Ordered native pointers for one semantic role.
    :param bus_by_term_id: Imported buses keyed by source terminal FID.
    :param cubic_by_id: Source cubicles keyed by their FID.
    :return: Resolved bus, or ``None`` when no explicit pointer resolves.
    """
    resolved_bus: dev.Bus | None = None
    pointer: str | None
    for pointer in pointer_candidates:
        if resolved_bus is None and pointer is not None:
            # First try a direct terminal pointer, which is how cpCtrlNode is
            # normally exported after PowerFactory resolves the controller.
            pointer_id: str = _ref_id(pointer)
            resolved_bus = bus_by_term_id.get(pointer_id, None)
            if resolved_bus is None:
                # p_cub and some legacy station fields instead reference the
                # cubicle; its fold_id identifies the electrical terminal.
                source_cubic: StaCubic | None = cubic_by_id.get(pointer_id, None)
                if source_cubic is not None:
                    terminal_id: str = _ref_id(source_cubic.fold_id)
                    resolved_bus = bus_by_term_id.get(terminal_id, None)
                else:
                    pass
            else:
                pass
        else:
            pass
    else:
        pass
    return resolved_bus


def _add_elmstactrl_controllers(
        dgs_grid: DgsCircuit,
        grid: dev.MultiCircuit,
        bus_by_term_id: Dict[str, dev.Bus],
        logger: Logger,
        cubics_by_objid: Dict[str, List[StaCubic]] | None = None,
) -> Dict[str, dev.StationController]:
    """
    Materialize shared station controls and index their equipment associations.

    :param dgs_grid: Parsed DGS source circuit.
    :param grid: Target VeraGrid circuit.
    :param bus_by_term_id: Imported buses keyed by terminal FID.
    :param logger: Import diagnostic sink.
    :param cubics_by_objid: Optional prebuilt equipment-to-cubicle mapping.
    :return: Station controller keyed by every associated equipment FID.
    """
    controller_by_equipment_id: Dict[str, dev.StationController] = dict()
    source_name_by_id: Dict[str, str] = dict()
    target_voltage_by_bus_id: Dict[str, float] = dict()
    effective_cubics_by_objid: Dict[str, List[StaCubic]]
    if cubics_by_objid is None:
        unused_stacubic_map: Dict[str, List[int]]
        unused_stacubic_map, effective_cubics_by_objid = _build_stacubic_mappings(
            stacubics=dgs_grid.stacubics,
        )
    else:
        effective_cubics_by_objid = cubics_by_objid
    terminal_by_id: Dict[str, ElmTerm] = dict()
    transformer_by_terminal_id: Dict[str, List[ElmTr2]] = dict()
    source_terminal: ElmTerm
    for source_terminal in dgs_grid.elmterms:
        terminal_by_id[_ref_id(source_terminal.ID)] = source_terminal
    else:
        pass
    source_transformer: ElmTr2
    for source_transformer in dgs_grid.elmtr2s:
        transformer_terminal_ids: List[str] = get_terminal_ids(
            element_id=source_transformer.ID,
            cubics_by_objid=effective_cubics_by_objid,
        )
        transformer_terminal_id: str
        for transformer_terminal_id in transformer_terminal_ids:
            terminal_transformers: List[ElmTr2] | None = transformer_by_terminal_id.get(
                transformer_terminal_id,
                None,
            )
            if terminal_transformers is None:
                terminal_transformers = list()
                transformer_by_terminal_id[transformer_terminal_id] = terminal_transformers
            else:
                pass
            terminal_transformers.append(source_transformer)
        else:
            pass
    else:
        pass
    closed_coupler_adjacency: Dict[str, List[str]] = _build_station_closed_coupler_adjacency(
        dgs_grid=dgs_grid,
        cubics_by_objid=effective_cubics_by_objid,
    )
    switch_by_cubic_id: Dict[str, StaSwitch] = build_switch_by_cubic_id(
        staswitchs=dgs_grid.staswitchs,
    )
    source_groups: List[List[DGSElement]] = list((
        dgs_grid.elmsyms,
        dgs_grid.elmgenstats,
        dgs_grid.elmsvss,
        dgs_grid.elmshnts,
    ))
    source_group: List[DGSElement]
    source_element: DGSElement
    for source_group in source_groups:
        for source_element in source_group:
            source_name_by_id[_ref_id(source_element.ID)] = source_element.loc_name
        else:
            pass
    else:
        pass

    # ``uset_mode=BusTargetVoltage`` refers to the structural ElmTerm target,
    # not to the solved ``m:u`` value retained separately as an optional warm
    # start.  Indexing the DGS terminals preserves that distinction without
    # expanding the physical Bus device with importer-specific state.
    for source_terminal in dgs_grid.elmterms:
        target_voltage_by_bus_id[_ref_id(source_terminal.ID)] = float(source_terminal.vtarget)
    else:
        pass

    cubic_by_id: Dict[str, StaCubic] = dict()
    source_cubic: StaCubic
    for source_cubic in dgs_grid.stacubics:
        cubic_by_id[_ref_id(source_cubic.ID)] = source_cubic
    else:
        pass

    source_controller: ElmStactrl
    for source_controller in dgs_grid.elmstactrls:
        controller_name: str = _get_non_empty_name(
            source_controller.loc_name,
            f"Station controller {_ref_id(source_controller.ID)}",
        )
        # Only calculated/explicit control-node fields create a continuous
        # remote-voltage equation.  rembar/refbar are structural station
        # references in consolidated DGS exports and must not activate one.
        continuous_control_pointer_candidates: List[str | None] = list((
            source_controller.cpCtrlNode,
            source_controller.p_cub,
        ))
        control_bus: dev.Bus | None = _resolve_station_controller_bus(
            pointer_candidates=continuous_control_pointer_candidates,
            bus_by_term_id=bus_by_term_id,
            cubic_by_id=cubic_by_id,
        )
        structural_pointer_candidates: List[str | None] = list((
            source_controller.rembar,
            source_controller.refbar,
        ))
        structural_control_bus: dev.Bus | None = _resolve_station_controller_bus(
            pointer_candidates=structural_pointer_candidates,
            bus_by_term_id=bus_by_term_id,
            cubic_by_id=cubic_by_id,
        )
        structural_control_bus_id: str | None = (
            None
            if structural_control_bus is None
            else str(structural_control_bus.idtag)
        )
        machine_step_up_transformer_ids: List[str | None]
        machine_control_bus_ids: List[str | None]
        station_topology_metadata_complete: bool
        (
            machine_step_up_transformer_ids,
            machine_control_bus_ids,
            station_topology_metadata_complete,
        ) = _build_station_step_up_associations(
            source_controller=source_controller,
            explicit_control_bus_id=structural_control_bus_id,
            transformers_by_terminal_id=transformer_by_terminal_id,
            terminal_by_id=terminal_by_id,
            cubics_by_objid=effective_cubics_by_objid,
            switch_by_cubic_id=switch_by_cubic_id,
            closed_coupler_adjacency=closed_coupler_adjacency,
            logger=logger,
        )
        # Keep automatic step-up nodes aligned with their individual machines.
        # PowerFactory does not promote a unique member-side node to the
        # ElmStactrl itself when p_cub/cpCtrlNode/rembar are absent.  The
        # distinction is electrical: group Q distribution can remain active
        # while the controller has no global remote-voltage equation.
        if station_topology_metadata_complete:
            pass
        else:
            logger.add_warning(
                msg="Station topology used legacy busbar fallback because ivpriority is absent",
                device=controller_name,
                expected_value="Regenerate DGS with ElmTerm ivpriority/dvmin/dvmax",
                device_class="ElmStactrl",
            )

        associated_ids: List[str] = list()
        associated_id_seen: Set[str] = set()
        connected_equipment_ids: Set[str] = set()
        association_groups: List[List[str | None]] = list((
            source_controller.psym,
            source_controller.pshunts,
        ))
        association_group: List[str | None]
        associated_pointer: str | None
        for association_group in association_groups:
            for associated_pointer in association_group:
                if associated_pointer is None:
                    pass
                else:
                    associated_id: str = _ref_id(associated_pointer)
                    if len(associated_id) > 0 and associated_id not in associated_id_seen:
                        associated_id_seen.add(associated_id)
                        associated_ids.append(associated_id)
                    else:
                        pass
            else:
                pass
        else:
            pass

        # cconn is positional against psym and is the PowerFactory runtime
        # participation contract.  A missing vector denotes an older export;
        # preserve the historical all-connected behavior, but make the data
        # loss visible so users can regenerate with the unified definition.
        connection_vector_present: bool = len(source_controller.cconn) > 0
        machine_index: int
        for machine_index in range(len(source_controller.psym)):
            machine_pointer: str | None = source_controller.psym[machine_index]
            if machine_pointer is None:
                pass
            else:
                machine_id: str = _ref_id(machine_pointer)
                if not connection_vector_present:
                    connected_equipment_ids.add(machine_id)
                elif (
                        machine_index < len(source_controller.cconn)
                        and source_controller.cconn[machine_index] == 1
                ):
                    connected_equipment_ids.add(machine_id)
                else:
                    pass
        else:
            pass
        shunt_pointer: str | None
        for shunt_pointer in source_controller.pshunts:
            if shunt_pointer is None:
                pass
            else:
                connected_equipment_ids.add(_ref_id(shunt_pointer))
        else:
            pass
        if connection_vector_present or len(source_controller.psym) == 0:
            pass
        else:
            logger.add_warning(
                msg="ElmStactrl cconn vector missing; assuming all psym members participate",
                device=controller_name,
                expected_value="Regenerate DGS with the unified Export DGS definition",
                device_class="ElmStactrl",
            )

        associated_names: List[str] = list()
        associated_id: str
        for associated_id in associated_ids:
            associated_names.append(source_name_by_id.get(associated_id, associated_id))
        else:
            pass

        voltage_setpoint_mode: StationVoltageSetpointMode = _get_station_voltage_setpoint_mode(
            source_code=int(source_controller.uset_mode),
            controller_name=controller_name,
            logger=logger,
        )
        if (
                voltage_setpoint_mode is StationVoltageSetpointMode.BusTargetVoltage
                and control_bus is not None
        ):
            source_target_voltage: float | None = target_voltage_by_bus_id.get(
                control_bus.idtag,
                None,
            )
            if (
                    source_target_voltage is not None
                    and math.isfinite(source_target_voltage)
                    and source_target_voltage > 0.0
            ):
                effective_voltage_setpoint: float = source_target_voltage
            else:
                effective_voltage_setpoint = float(source_controller.usetp)
        else:
            effective_voltage_setpoint = float(source_controller.usetp)

        # Station modes can expose their measured cubicle through the legacy
        # ``p_cub`` field or the DGS 7.0 ``pQmeas`` field.  Preserve both the
        # physical equipment and terminal FIDs so the solver can reconstruct
        # the correct branch end after topology reduction without retaining an
        # importer-specific object pointer.
        measurement_device_id: str = ""
        measurement_bus_id: str = ""
        measurement_terminal_index: int = -1
        measurement_cubic_id: str | None = _ref_id(source_controller.p_cub)
        if measurement_cubic_id is None:
            measurement_cubic_id = _ref_id(source_controller.pQmeas)
        else:
            pass
        if measurement_cubic_id is not None:
            measurement_cubic: StaCubic | None = cubic_by_id.get(
                measurement_cubic_id,
                None,
            )
            if measurement_cubic is not None:
                measurement_device_id = _ref_id(measurement_cubic.obj_id)
                measurement_bus_id = _ref_id(measurement_cubic.fold_id)
                measurement_terminal_index = int(measurement_cubic.obj_bus)
            else:
                pass
        else:
            pass

        controller: dev.StationController = dev.StationController(
            name=controller_name,
            idtag=_ref_id(source_controller.ID),
            active=not bool(source_controller.outserv),
            control_mode=_get_station_control_mode(
                source_code=int(source_controller.i_ctrl),
                controller_name=controller_name,
                logger=logger,
            ),
            control_bus_selection=_get_station_bus_selection(
                source_code=int(source_controller.selBus),
                controller_name=controller_name,
                logger=logger,
            ),
            voltage_setpoint_mode=voltage_setpoint_mode,
            reactive_distribution=_get_station_distribution_mode(
                source_code=int(source_controller.imode),
                controller_name=controller_name,
                logger=logger,
            ),
            transformer_control_side=_get_station_transformer_control_side(
                source_code=int(source_controller.iTrfCtrl),
                controller_name=controller_name,
                logger=logger,
            ),
            reactive_change_response=_get_station_reactive_change_response(
                source_code=int(source_controller.iQorient),
                controller_name=controller_name,
                logger=logger,
            ),
            consider_reactive_dispatch=bool(source_controller.consQdisp),
            automatic_bus_voltage_threshold=float(source_controller.selAutoUn),
            use_separate_excitation_droop=bool(source_controller.iopt_tdr),
            overexcited_droop_percent=float(source_controller.ddroopoe),
            underexcited_droop_percent=float(source_controller.ddroopue),
            shunt_reactive_participation_percent=float(source_controller.Kqshnt),
            power_factor_characteristic_code=int(source_controller.cosphi_char),
            control_bus=control_bus,
            vset=effective_voltage_setpoint,
            qset=float(source_controller.qsetp),
            power_factor_set=float(source_controller.pfsetp),
            tan_phi_set=float(source_controller.tansetp),
            voltage_droop_enabled=bool(source_controller.i_droop),
            droop_percent=float(source_controller.ddroop),
            rated_reactive_power=float(source_controller.Srated),
            qmin=float(source_controller.Qmin),
            qmax=float(source_controller.Qmax),
            controlled_device_ids=";".join(associated_ids),
            controlled_device_names=";".join(associated_names),
            measurement_device_id=measurement_device_id,
            measurement_bus_id=measurement_bus_id,
            measurement_terminal_index=measurement_terminal_index,
            machine_device_ids=_serialize_station_reference_vector(source_controller.psym),
            machine_step_up_transformer_ids=_serialize_station_reference_vector(
                machine_step_up_transformer_ids
            ),
            machine_control_bus_ids=_serialize_station_reference_vector(machine_control_bus_ids),
            connected_machine_flags=_serialize_station_int_vector(source_controller.cconn),
            reactive_distribution_percent=_serialize_station_float_vector(source_controller.cvqq),
            individual_voltage_targets=_serialize_station_float_vector(source_controller.cvgen),
            individual_voltage_minimums=_serialize_station_float_vector(source_controller.cvgenmin),
            individual_voltage_maximums=_serialize_station_float_vector(source_controller.cvgenmax),
        )
        grid.add_station_controller(obj=controller)

        for associated_id in associated_ids:
            if associated_id not in connected_equipment_ids:
                pass
            else:
                previous_controller: dev.StationController | None = controller_by_equipment_id.get(
                    associated_id,
                    None,
                )
                if previous_controller is None:
                    controller_by_equipment_id[associated_id] = controller
                else:
                    logger.add_warning(
                        msg="Equipment associated with multiple station controllers",
                        device=associated_names[associated_ids.index(associated_id)],
                        value=controller.name,
                        expected_value=previous_controller.name,
                        device_class="ElmStactrl",
                    )
        else:
            pass
    else:
        pass

    return controller_by_equipment_id


def _deactivate_station_controllers_for_snapshot(grid: dev.MultiCircuit) -> None:
    """Retain station-controller provenance without executing it in snapshot mode.

    Device materialization first needs the native association to select the
    correct VeraGrid injection class.  Once all injections exist, snapshot
    mode disables controller execution so compilation cannot replace exported
    solved P/Q with a fresh voltage-control equation.

    :param grid: Partially materialized DGS circuit containing all injections.
    :return: None.
    """
    station_controller: dev.StationController
    for station_controller in grid.get_station_controllers():
        station_controller.active = False
    else:
        pass


def _add_elmsym_generators(dgs_grid: DgsCircuit,
                           grid: dev.MultiCircuit,
                           stacubic_dict: Dict[str, List[int]],
                           typsym_dict: Dict[str, TypSym],
                           baseMVA: float,
                           logger: Logger,
                           cubics_by_objid: Dict[str, List[StaCubic]],
                           bus_by_term_id: Dict[str, dev.Bus],
                           use_power_flow_snapshot: bool = False,
                           station_controller_by_device_id: Dict[str, dev.StationController] | None = None) -> None:
    """
    Add elmsym generators.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typsym_dict: typsym_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param station_controller_by_device_id: Effective controllers keyed by connected machine FID.
    :return: Function result.
    """
    effective_controller_by_device_id: Dict[str, dev.StationController]
    if station_controller_by_device_id is None:
        effective_controller_by_device_id = dict()
    else:
        effective_controller_by_device_id = station_controller_by_device_id
    capability_curve_by_id: Dict[str, IntQlim] = dict()
    source_capability_curve: IntQlim
    for source_capability_curve in dgs_grid.intqlims:
        source_capability_curve_id: str | None = _ref_id(source_capability_curve.ID)
        if source_capability_curve_id is None:
            pass
        else:
            capability_curve_by_id[source_capability_curve_id] = source_capability_curve
    else:
        pass
    for elmsym in dgs_grid.elmsyms:
        capability_curve_id: str | None = _ref_id(elmsym.pQlimType)
        if capability_curve_id is None:
            capability_curve: IntQlim | None = None
        else:
            capability_curve = capability_curve_by_id.get(capability_curve_id, None)
        parallel_count: int = _get_parallel_device_count(count=int(elmsym.ngnum))
        for parallel_index in range(parallel_count):
            bus, gen = convert_dgs_to_generator(
                elmsym=elmsym,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                typsym_dict=typsym_dict,
                baseMVA=baseMVA,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                parallel_index=parallel_index,
                parallel_count=parallel_count,
                use_power_flow_snapshot=use_power_flow_snapshot,
                capability_curve=capability_curve,
            )
            station_controller: dev.StationController | None = effective_controller_by_device_id.get(
                _ref_id(elmsym.ID),
                None,
            )
            use_local_station_target: bool = (
                not use_power_flow_snapshot
                and station_controller is not None
                and station_controller.active
                and station_controller.control_mode is StationControlMode.Voltage
                and (
                    station_controller.control_bus is None
                    or station_controller.transformer_control_side
                    is not StationTransformerControlSide.NoControl
                )
            )
            if use_local_station_target and station_controller is not None:
                gen.control_mode = GeneratorControlMode.V
                gen.control_bus = None
                gen.Vset = _get_station_machine_voltage_target(
                    controller=station_controller,
                    source_machine_id=_ref_id(elmsym.ID),
                    default_voltage=float(gen.Vset),
                )
            else:
                station_owns_non_voltage_reactive_control: bool = bool(
                    not use_power_flow_snapshot
                    and station_controller is not None
                    and station_controller.active
                    and station_controller.control_mode is not StationControlMode.Voltage
                )
                if station_owns_non_voltage_reactive_control:
                    # An active ElmStactrl Q/cos(phi)/tan(phi) loop owns the
                    # member exciters.  Leaving ElmSym ``constv`` active would
                    # add an unrelated local-voltage equation and replace the
                    # station objective with the machine's dormant ``usetp``.
                    gen.control_mode = GeneratorControlMode.Q
                    gen.control_bus = None
                else:
                    pass
            grid.add_generator(bus=bus, api_obj=gen)


def _add_elmasm_generators(dgs_grid: DgsCircuit,
                           grid: dev.MultiCircuit,
                           stacubic_dict: Dict[str, List[int]],
                           typasmo_dict: Dict[str, TypAsmo],
                           logger: Logger,
                           cubics_by_objid: Dict[str, List[StaCubic]],
                           bus_by_term_id: Dict[str, dev.Bus]) -> None:
    """
    Add elmasm generators.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typasmo_dict: typasmo_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    for elmasm in dgs_grid.elmasms:
        parallel_count = _get_parallel_device_count(count=int(elmasm.ngnum))
        for parallel_index in range(parallel_count):
            bus, gen = convert_dgs_to_asm_generator(
                elmasm=elmasm,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                typasmo_dict=typasmo_dict,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                parallel_index=parallel_index,
                parallel_count=parallel_count,
            )
            grid.add_generator(bus=bus, api_obj=gen)


def _add_elmvac_loads(dgs_grid: DgsCircuit,
                      grid: dev.MultiCircuit,
                      stacubic_dict: Dict[str, List[int]],
                      logger: Logger,
                      cubics_by_objid: Dict[str, List[StaCubic]],
                      bus_by_term_id: Dict[str, dev.Bus]) -> None:
    """
    Add elmvac loads.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    for elmvac in dgs_grid.elmvacs:
        if elmvac.itype == 2:
            bus, load = convert_dgs_ward_equivalent_to_load(
                elmvac=elmvac,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id
            )
            grid.add_load(bus=bus, api_obj=load)


def _add_elmlod_loads(dgs_grid: DgsCircuit,
                      grid: dev.MultiCircuit,
                      stacubic_dict: Dict[str, List[int]],
                      logger: Logger,
                      cubics_by_objid: Dict[str, List[StaCubic]],
                      bus_by_term_id: Dict[str, dev.Bus],
                      switch_by_cubic_id: Dict[str, StaSwitch],
                      use_power_flow_snapshot: bool = False) -> None:
    """
    Add elmlod loads.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param station_controller_by_device_id: Shared controllers keyed by source equipment FID.
    :param use_power_flow_snapshot: Freeze exported solved P/Q instead of re-solving controls.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :param use_power_flow_snapshot: Use solved terminal P/Q when available.
    :return: Function result.
    """
    for elmlod in dgs_grid.elmlods:
        bus, load = convert_dgs_to_load(
            elmlod=elmlod,
            stacubic_dict=stacubic_dict,
            buses=grid.buses,
            logger=logger,
            cubics_by_objid=cubics_by_objid,
            bus_by_term_id=bus_by_term_id,
            switch_by_cubic_id=switch_by_cubic_id,
            use_power_flow_snapshot=use_power_flow_snapshot,
        )
        grid.add_load(bus=bus, api_obj=load)


def _get_composite_owned_equipment_ids(dgs_grid: DgsCircuit) -> Set[str]:
    """Return physical equipment referenced by exported composite slots.

    ``ElmComp.pelm`` is the structural fallback for DGS definitions that do
    not yet export the reverse ``c_pmod`` pointer on the physical equipment.
    Dynamic child references are harmless because callers still validate the
    physical class/category before changing control authority.

    :param dgs_grid: Parsed DGS containing optional composite slot topology.
    :return: Normalized referenced equipment identifiers.
    """
    equipment_ids: Set[str] = set()
    composite: ElmComp
    for composite in dgs_grid.elmcomps:
        element_pointer: str | None
        for element_pointer in composite.pelm:
            if element_pointer is None:
                pass
            else:
                element_id: str = _ref_id(element_pointer)
                if element_id == "":
                    pass
                else:
                    equipment_ids.add(element_id)
        else:
            pass
    else:
        pass
    return equipment_ids


def _add_elmgenstat_devices(dgs_grid: DgsCircuit,
                            grid: dev.MultiCircuit,
                            stacubic_dict: Dict[str, List[int]],
                            use_vsc_for_injections: bool,
                            logger: Logger,
                            cubics_by_objid: Dict[str, List[StaCubic]],
                            bus_by_term_id: Dict[str, dev.Bus],
                            station_controller_by_device_id: Dict[str, dev.StationController] | None = None,
                            use_power_flow_snapshot: bool = False) -> None:
    """
    Add elmgenstat devices.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param use_vsc_for_injections: use_vsc_for_injections parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param station_controller_by_device_id: Shared controllers keyed by source equipment FID.
    :param use_power_flow_snapshot: Freeze exported solved P/Q instead of re-solving controls.
    :return: Function result.
    """
    effective_controller_by_device_id: Dict[str, dev.StationController]
    if station_controller_by_device_id is None:
        effective_controller_by_device_id = dict()
    else:
        effective_controller_by_device_id = station_controller_by_device_id
    composite_owned_equipment_ids: Set[str] = _get_composite_owned_equipment_ids(
        dgs_grid=dgs_grid,
    )
    capability_curve_by_id: Dict[str, IntQlim] = dict()
    source_capability_curve: IntQlim
    for source_capability_curve in dgs_grid.intqlims:
        capability_curve_by_id[_ref_id(source_capability_curve.ID)] = (
            source_capability_curve
        )
    else:
        pass
    for elmgenstat in dgs_grid.elmgenstats:
        parallel_count = _get_parallel_device_count(count=int(elmgenstat.ngnum))
        for parallel_index in range(parallel_count):
            source_control_mode: str = str(elmgenstat.av_mode).strip().lower()
            capability_curve: IntQlim | None
            capability_curve_id: str | None = _ref_id(elmgenstat.pQlimType)
            if capability_curve_id is None:
                capability_curve = None
            else:
                capability_curve = capability_curve_by_id.get(
                    capability_curve_id,
                    None,
                )
            station_controller: dev.StationController | None = effective_controller_by_device_id.get(
                _ref_id(elmgenstat.ID),
                None,
            )
            has_station_voltage_control: bool = (
                station_controller is not None
                and station_controller.active
                and station_controller.control_mode is StationControlMode.Voltage
            )
            has_dynamic_composite: bool = (
                _ref_id(elmgenstat.ID) in composite_owned_equipment_ids
            )

            # Electrical control semantics take precedence over the marketing
            # category.  Otherwise Wind/vdroop and Storage/constv rows become
            # fixed PQ injections before their native controller is inspected.
            if (
                    source_control_mode in {"constv", "vdroop"}
                    or has_station_voltage_control
                    or has_dynamic_composite
            ):
                if (
                    elmgenstat.cCategory == "Wind"
                    and use_vsc_for_injections
                    and not bool(elmgenstat.outserv)
                ):
                    dc_bus: dev.Bus
                    vsc: dev.VSC
                    dc_bus, vsc = convert_dgs_staticgen_to_vsc(
                        elmgenstat=elmgenstat,
                        stacubic_dict=stacubic_dict,
                        buses=grid.buses,
                        logger=logger,
                        cubics_by_objid=cubics_by_objid,
                        bus_by_term_id=bus_by_term_id,
                        parallel_index=parallel_index,
                        parallel_count=parallel_count,
                        use_power_flow_snapshot=use_power_flow_snapshot,
                    )
                    grid.add_bus(dc_bus)
                    grid.add_vsc(vsc)
                else:
                    bus: dev.Bus
                    gen: dev.Generator
                    bus, gen = convert_dgs_staticgen_to_gen(
                        elmgenstat=elmgenstat,
                        stacubic_dict=stacubic_dict,
                        buses=grid.buses,
                        logger=logger,
                        cubics_by_objid=cubics_by_objid,
                        bus_by_term_id=bus_by_term_id,
                        parallel_index=parallel_index,
                        parallel_count=parallel_count,
                        use_power_flow_snapshot=use_power_flow_snapshot,
                        external_reactive_control_model=(
                            _ref_id(elmgenstat.ID) in composite_owned_equipment_ids
                        ),
                        capability_curve=capability_curve,
                    )
                    use_local_station_target: bool = (
                        not use_power_flow_snapshot
                        and station_controller is not None
                        and station_controller.active
                        and station_controller.control_mode is StationControlMode.Voltage
                        and (
                            station_controller.control_bus is None
                            or station_controller.transformer_control_side
                            is not StationTransformerControlSide.NoControl
                        )
                    )
                    use_remote_station_target: bool = bool(
                        not use_power_flow_snapshot
                        and station_controller is not None
                        and station_controller.active
                        and station_controller.control_mode
                        is StationControlMode.Voltage
                        and station_controller.control_bus is not None
                        and station_controller.transformer_control_side
                        is StationTransformerControlSide.NoControl
                    )
                    if use_remote_station_target and station_controller is not None:
                        # A voltage station controller without an owned step-up
                        # transformer acts directly on the aggregate machine Q
                        # degree of freedom at its explicit remote bus.
                        gen.control_mode = GeneratorControlMode.V
                        gen.control_bus = station_controller.control_bus
                        gen.Vset = float(station_controller.vset)
                    elif use_local_station_target and station_controller is not None:
                        gen.control_mode = GeneratorControlMode.V
                        gen.control_bus = None
                        gen.Vset = _get_station_machine_voltage_target(
                            controller=station_controller,
                            source_machine_id=_ref_id(elmgenstat.ID),
                            default_voltage=float(gen.Vset),
                        )
                    else:
                        station_owns_non_voltage_reactive_control: bool = bool(
                            not use_power_flow_snapshot
                            and station_controller is not None
                            and station_controller.active
                            and station_controller.control_mode is not StationControlMode.Voltage
                        )
                        if station_owns_non_voltage_reactive_control:
                            # Aggregate non-voltage station objectives own the
                            # converter or exciter reactive degree of freedom.
                            # The local ``av_mode`` must therefore remain a PQ
                            # starting contract until the station equation is
                            # applied by the power-flow control layer.
                            gen.control_mode = GeneratorControlMode.Q
                            gen.control_bus = None
                        else:
                            pass
                    grid.add_generator(bus=bus, api_obj=gen)
            else:
                if elmgenstat.cCategory == 'Storage':
                    battery: dev.Battery
                    bus, battery = convert_dgs_staticgen_to_battery(
                        elmgenstat=elmgenstat,
                        stacubic_dict=stacubic_dict,
                        buses=grid.buses,
                        logger=logger,
                        cubics_by_objid=cubics_by_objid,
                        bus_by_term_id=bus_by_term_id,
                        parallel_index=parallel_index,
                        parallel_count=parallel_count,
                        use_power_flow_snapshot=use_power_flow_snapshot,
                    )
                    grid.add_battery(bus=bus, api_obj=battery)
                else:
                    # ``constq`` and unsupported characteristic modes remain
                    # fixed PQ injections. A configured ``qpchar`` remains a PQ
                    # device, but its Q target is reconstructed from the centre
                    # line of the referenced IntQlim instead of inventing a PV
                    # controller or consuming solved PowerFactory results.
                    capability_points: List[Tuple[float, float, float]] | None = (
                        _build_intqlim_q_points(
                            capability_curve=capability_curve,
                            rated_power_mva=float(elmgenstat.sgn),
                            minimum_scale_percent=elmgenstat.scaleQmin,
                            maximum_scale_percent=elmgenstat.scaleQmax,
                        )
                    )
                    if source_control_mode == "qpchar":
                        characteristic_reactive_power_mvar: float | None = (
                            _evaluate_qp_characteristic_reactive_power(
                                capability_points=capability_points,
                                active_power_mw=float(elmgenstat.pgini),
                            )
                        )
                    else:
                        characteristic_reactive_power_mvar = None
                    stagen: dev.StaticGenerator
                    bus, stagen = convert_dgs_to_static_gen(
                        elmgenstat=elmgenstat,
                        stacubic_dict=stacubic_dict,
                        buses=grid.buses,
                        logger=logger,
                        cubics_by_objid=cubics_by_objid,
                        bus_by_term_id=bus_by_term_id,
                        parallel_index=parallel_index,
                        parallel_count=parallel_count,
                        use_power_flow_snapshot=use_power_flow_snapshot,
                        configured_reactive_power_mvar=(
                            characteristic_reactive_power_mvar
                        ),
                    )
                    grid.add_static_generator(bus=bus, api_obj=stagen)


def _add_elmvsc_devices(
        dgs_grid: DgsCircuit,
        grid: dev.MultiCircuit,
        logger: Logger,
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        switch_by_cubic_id: Dict[str, StaSwitch],
        frequency_hz: float,
        use_power_flow_snapshot: bool,
) -> None:
    """
    Add every structurally valid native PowerFactory converter.

    One malformed converter is isolated and logged, preserving both the rest of
    the static network and the independent dynamic-model catalogue.

    :param dgs_grid: Parsed DGS circuit.
    :param grid: Target VeraGrid circuit.
    :param logger: Import diagnostic sink.
    :param cubics_by_objid: Cubicles grouped by source object FID.
    :param bus_by_term_id: Imported buses keyed by terminal FID.
    :param switch_by_cubic_id: Cubicle switches keyed by cubicle FID.
    :param frequency_hz: Network nominal frequency in Hz.
    :param use_power_flow_snapshot: Whether solved terminal powers are authoritative.
    :return: None.
    """
    elmvsc: ElmVsc
    for elmvsc in dgs_grid.elmvscs:
        converter: dev.VSC | None = convert_dgs_to_vsc(
            elmvsc=elmvsc,
            cubics_by_objid=cubics_by_objid,
            bus_by_term_id=bus_by_term_id,
            switch_by_cubic_id=switch_by_cubic_id,
            system_base_mva=float(grid.Sbase),
            frequency_hz=frequency_hz,
            use_power_flow_snapshot=use_power_flow_snapshot,
            logger=logger,
        )
        if converter is None:
            pass
        else:
            grid.add_vsc(obj=converter)


def _add_elmvscmono_devices(
        dgs_grid: DgsCircuit,
        grid: dev.MultiCircuit,
        logger: Logger,
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        switch_by_cubic_id: Dict[str, StaSwitch],
        frequency_hz: float,
        use_power_flow_snapshot: bool,
) -> None:
    """Add every structurally valid native monopolar converter.

    :param dgs_grid: Parsed DGS circuit.
    :param grid: Target VeraGrid circuit.
    :param logger: Import diagnostic sink.
    :param cubics_by_objid: Cubicles grouped by source object FID.
    :param bus_by_term_id: Imported buses keyed by terminal FID.
    :param switch_by_cubic_id: Cubicle switches keyed by cubicle FID.
    :param frequency_hz: Network nominal frequency in Hz.
    :param use_power_flow_snapshot: Whether solved terminal powers are authoritative.
    :return: None.
    """
    source: ElmVscmono
    for source in dgs_grid.elmvscmonos:
        converter: dev.VSC | None = convert_dgs_to_monopolar_vsc(
            source=source,
            cubics_by_objid=cubics_by_objid,
            bus_by_term_id=bus_by_term_id,
            switch_by_cubic_id=switch_by_cubic_id,
            system_base_mva=float(grid.Sbase),
            frequency_hz=frequency_hz,
            use_power_flow_snapshot=use_power_flow_snapshot,
            logger=logger,
        )
        if converter is None:
            pass
        else:
            grid.add_vsc(obj=converter)
    else:
        pass


def _add_elmxnet_devices(dgs_grid: DgsCircuit,
                         grid: dev.MultiCircuit,
                         stacubic_dict: Dict[str, List[int]],
                         logger: Logger,
                         cubics_by_objid: Dict[str, List[StaCubic]],
                         bus_by_term_id: Dict[str, dev.Bus]) -> None:
    """
    Add elmxnet devices.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    for elmxnet in dgs_grid.elmxnets:
        short_circuit: bool = True
        if short_circuit:
            bus, gen = convert_dgs_external_grid_to_generator(
                elmxnet=elmxnet,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                Sbase=grid.Sbase,
            )
            grid.add_generator(bus=bus, api_obj=gen)
        else:
            bus, ext_grd = convert_dgs_to_external_grid(
                elmxnet=elmxnet,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id
            )
            grid.add_external_grid(bus=bus, api_obj=ext_grd)


def _promote_unambiguous_pv_external_grid_references(
        dgs_grid: DgsCircuit,
        grid: dev.MultiCircuit,
        stacubic_dict: Dict[str, List[int]],
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        logger: Logger,
) -> int:
    """Provide an angular reference for isolated AC networks with one PV source.

    PowerFactory promotes the sole active ``ElmXnet`` in an AC island to the
    angular reference even when its exported ``bustp`` remains ``PV``. The
    active and reactive powers of that source therefore remain network
    unknowns. Reproducing this topology rule avoids freezing solved snapshots
    or relying on case-specific names. Islands with multiple eligible sources
    remain unchanged because the DGS does not contain enough priority data to
    select one without guessing.

    :param dgs_grid: Parsed source DGS circuit.
    :param grid: Imported VeraGrid circuit.
    :param stacubic_dict: Legacy element-to-terminal lookup.
    :param cubics_by_objid: Cubicles grouped by source object FID.
    :param bus_by_term_id: Imported buses keyed by terminal FID.
    :param logger: Import diagnostic sink.
    :return: Number of PV sources promoted to angular references.
    """
    bus_count: int = len(grid.buses)
    bus_index: Dict[dev.Bus, int] = dict()
    adjacency: List[List[int]] = list()
    bus_position: int
    bus: dev.Bus
    for bus_position, bus in enumerate(grid.buses):
        bus_index[bus] = bus_position
        adjacency.append(list())
    else:
        pass

    # VSC and HVDC devices transfer power but do not couple AC voltage angles.
    # Only active passive branches define one AC reference island.
    branch: BranchParent
    for branch in grid.get_branches(
            add_vsc=False,
            add_hvdc=False,
            add_switch=True,
    ):
        from_bus: dev.Bus = branch.bus_from
        to_bus: dev.Bus = branch.bus_to
        is_active_ac_connection: bool = bool(
            branch.active
            and not from_bus.is_dc
            and not to_bus.is_dc
        )
        if is_active_ac_connection:
            from_index: int = bus_index[from_bus]
            to_index: int = bus_index[to_bus]
            adjacency[from_index].append(to_index)
            adjacency[to_index].append(from_index)
        else:
            pass
    else:
        pass

    component_by_bus: np.ndarray = np.full(bus_count, -1, dtype=int)
    queue: np.ndarray = np.empty(bus_count, dtype=int)
    component_count: int = 0
    root_index: int
    for root_index in range(bus_count):
        root_bus: dev.Bus = grid.buses[root_index]
        if component_by_bus[root_index] < 0 and not root_bus.is_dc:
            queue_start: int = 0
            queue_end: int = 1
            queue[0] = root_index
            component_by_bus[root_index] = component_count
            while queue_start < queue_end:
                current_index: int = int(queue[queue_start])
                queue_start += 1
                adjacent_index: int
                for adjacent_index in adjacency[current_index]:
                    if component_by_bus[adjacent_index] < 0:
                        component_by_bus[adjacent_index] = component_count
                        queue[queue_end] = adjacent_index
                        queue_end += 1
                    else:
                        pass
                else:
                    pass
            component_count += 1
        else:
            pass
    else:
        pass

    has_reference: np.ndarray = np.zeros(component_count, dtype=bool)
    for bus_position, bus in enumerate(grid.buses):
        component_index: int = int(component_by_bus[bus_position])
        if component_index >= 0 and bus.get_is_slack_at(t=None):
            has_reference[component_index] = True
        else:
            pass
    else:
        pass

    candidates_by_component: Dict[int, List[Tuple[ElmXnet, dev.Bus]]] = dict()
    source: ElmXnet
    for source in dgs_grid.elmxnets:
        source_is_candidate: bool = bool(
            not bool(source.outserv)
            and str(source.bustp).strip().upper() == "PV"
        )
        if source_is_candidate:
            source_bus: dev.Bus = get_injection_bus(
                elm_id=source.ID,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
            )
            source_component: int = int(component_by_bus[bus_index[source_bus]])
            component_candidates: List[Tuple[ElmXnet, dev.Bus]] | None = (
                candidates_by_component.get(source_component, None)
            )
            if component_candidates is None:
                component_candidates = list()
                candidates_by_component[source_component] = component_candidates
            else:
                pass
            component_candidates.append((source, source_bus))
        else:
            pass
    else:
        pass

    promoted_count: int = 0
    component_index: int
    component_candidates: List[Tuple[ElmXnet, dev.Bus]]
    for component_index, component_candidates in candidates_by_component.items():
        if not has_reference[component_index] and len(component_candidates) == 1:
            selected_source: ElmXnet = component_candidates[0][0]
            selected_bus: dev.Bus = component_candidates[0][1]
            selected_bus.set_is_slack_at(t=None, val=True)
            promoted_count += 1
            logger.add_info(
                msg="Sole PV external grid promoted to AC island reference",
                device=selected_source.loc_name,
                device_class="ElmXnet",
                value=component_index,
            )
        else:
            if (
                    not has_reference[component_index]
                    and len(component_candidates) > 1
            ):
                logger.add_warning(
                    msg="AC island has multiple PV external-grid reference candidates",
                    device_class="ElmXnet",
                    value=len(component_candidates),
                )
            else:
                pass
    else:
        pass

    return promoted_count


def _add_elmshnt_devices(dgs_grid: DgsCircuit,
                         grid: dev.MultiCircuit,
                         stacubic_dict: Dict[str, List[int]],
                         logger: Logger,
                         cubics_by_objid: Dict[str, List[StaCubic]],
                         bus_by_term_id: Dict[str, dev.Bus],
                         frequency: float,
                         switch_by_cubic_id: Dict[str, StaSwitch]) -> None:
    """
    Add elmshnt devices.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param frequency: frequency parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :return: Function result.
    """
    for elmshnt in dgs_grid.elmshnts:
        if int(elmshnt.ncapx) > 1:
            bus, cshunt = convert_dgs_to_controllable_shunt_from_elmshnt(
                elmshnt=elmshnt,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                frequency=frequency
            )
            cshunt.active = (
                bool(cshunt.active)
                and _is_element_closed_by_cubicle_switches(
                    element_id=elmshnt.ID,
                    cubics_by_objid=cubics_by_objid,
                    switch_by_cubic_id=switch_by_cubic_id,
                )
            )
            grid.add_controllable_shunt(bus=bus, api_obj=cshunt)
        else:
            bus, shunt = convert_dgs_to_shunt(
                elmshnt=elmshnt,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                frequency=frequency,
                switch_by_cubic_id=switch_by_cubic_id,
            )
            grid.add_shunt(bus=bus, api_obj=shunt)


def _get_externally_controlled_svs_ids(dgs_grid: DgsCircuit) -> Set[str]:
    """
    Identify ElmSvs devices governed by an explicitly external model.

    The consolidated export writes ``c_pmod``, ``p_cub`` and ``cpCtrlNode``.
    A model pointer with both control-node pointers explicitly empty means that
    the composite model owns the SVC state.  Column-presence flags prevent an
    old DGS, which cannot express this distinction, from being reclassified.

    :param dgs_grid: Parsed DGS circuit with controller-pointer provenance.
    :return: Normalized ElmSvs FIDs owned by an external HVDC controller.
    """
    externally_controlled_svs_ids: Set[str] = set()
    source_svs: ElmSvs
    for source_svs in dgs_grid.elmsvss:
        model_pointer_is_declared: bool = (
            source_svs.c_pmod is not None
            and str(source_svs.c_pmod).strip() not in {"", "*"}
        )
        pointer_schema_is_complete: bool = (
            source_svs.c_pmod_column_present
            and source_svs.p_cub_column_present
            and source_svs.cp_ctrl_node_column_present
        )
        configured_pointer_is_empty: bool = (
            source_svs.p_cub is None
            or str(source_svs.p_cub).strip() in {"", "*"}
        )
        resolved_pointer_is_empty: bool = (
            source_svs.cpCtrlNode is None
            or str(source_svs.cpCtrlNode).strip() in {"", "*"}
        )
        has_external_controller: bool = (
            pointer_schema_is_complete
            and model_pointer_is_declared
            and configured_pointer_is_empty
            and resolved_pointer_is_empty
        )
        if has_external_controller:
            source_svs_id: str | None = _ref_id(source_svs.ID)
            if source_svs_id is None or source_svs_id == "":
                pass
            else:
                externally_controlled_svs_ids.add(source_svs_id)
        else:
            pass
    else:
        pass
    return externally_controlled_svs_ids


def _add_elmsvs_devices(dgs_grid: DgsCircuit,
                        grid: dev.MultiCircuit,
                        stacubic_dict: Dict[str, List[int]],
                        use_vsc_for_injections: bool,
                        logger: Logger,
                        cubics_by_objid: Dict[str, List[StaCubic]],
                        bus_by_term_id: Dict[str, dev.Bus],
                        use_power_flow_snapshot: bool = False,
                        preserve_dynamic_host: bool = False) -> None:
    """
    Add elmsvs devices.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param use_vsc_for_injections: use_vsc_for_injections parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param use_power_flow_snapshot: Freeze exported solved P/Q instead of re-solving controls.
    :param preserve_dynamic_host: Keep the typed SVC device needed by an imported dynamic model.
    :return: Function result.
    """
    # Remote ElmSvs pointers reference cubicle FIDs, whereas normal equipment
    # connectivity is grouped by object FID. Build the complementary index once
    # for the whole imported section.
    cubic_by_id: Dict[str, StaCubic] = _build_cubic_by_id(
        stacubics=dgs_grid.stacubics,
    )
    externally_controlled_svs_ids: Set[str] = _get_externally_controlled_svs_ids(
        dgs_grid=dgs_grid,
    )
    elmsvs: ElmSvs
    for elmsvs in dgs_grid.elmsvss:
        has_solved_power: bool = (
            use_power_flow_snapshot
            and elmsvs.m_p_bus1 is not None
            and elmsvs.m_q_bus1 is not None
        )
        if has_solved_power and not preserve_dynamic_host:
            # A static-only snapshot can use constant terminal power because no
            # later dynamic association needs the original ElmSvs device type.
            bus: dev.Bus = get_injection_bus(
                elm_id=elmsvs.ID,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
            )
            solved_injection: dev.StaticGenerator = dev.StaticGenerator(
                name=elmsvs.loc_name or f"ElmSvs_{_ref_id(elmsvs.ID)}",
                idtag=_ref_id(elmsvs.ID),
                # PowerFactory terminal results use the passive convention:
                # positive P/Q flows from the bus into ElmSvs. VeraGrid's
                # StaticGenerator stores positive nodal injection, hence both
                # solved powers cross this boundary with the opposite sign.
                P=-float(elmsvs.m_p_bus1),
                Q=-float(elmsvs.m_q_bus1),
                Snom=float(elmsvs.Srated),
                active=(elmsvs.outserv == 0),
            )
            grid.add_static_generator(bus=bus, api_obj=solved_injection)
        else:
            if use_vsc_for_injections:
                dc_bus: dev.Bus
                vsc: dev.VSC
                dc_bus, vsc = convert_dgs_svs_to_vsc(
                    elmsvs=elmsvs,
                    stacubic_dict=stacubic_dict,
                    buses=grid.buses,
                    logger=logger,
                    cubics_by_objid=cubics_by_objid,
                    bus_by_term_id=bus_by_term_id,
                )
                grid.add_bus(dc_bus)
                grid.add_vsc(vsc)
            else:
                cshunt: dev.ControllableShunt
                bus, cshunt = convert_dgs_to_controllable_shunt_from_svs(
                    elmsvs=elmsvs,
                    stacubic_dict=stacubic_dict,
                    buses=grid.buses,
                    logger=logger,
                    cubics_by_objid=cubics_by_objid,
                    bus_by_term_id=bus_by_term_id,
                    cubic_by_id=cubic_by_id,
                    external_control_model=(
                        _ref_id(elmsvs.ID) in externally_controlled_svs_ids
                    ),
                )
                if has_solved_power:
                    # Preserve the exact solved operating point on the physical
                    # susceptance device. Both PowerFactory ``m:Q:bus1`` for an
                    # ElmSvs terminal P/Q is positive into the device, whereas
                    # positive VeraGrid B injects reactive power into the bus.
                    # Convert the passive result before recovering B=Qinj/Vm².
                    snapshot_voltage_magnitude: float = abs(float(bus.Vm0))
                    if snapshot_voltage_magnitude > 1.0e-12:
                        snapshot_susceptance: float = (
                            -float(elmsvs.m_q_bus1)
                            / (
                                snapshot_voltage_magnitude
                                * snapshot_voltage_magnitude
                            )
                        )
                    else:
                        snapshot_susceptance = -float(elmsvs.m_q_bus1)
                    cshunt.b_steps = np.array(
                        [snapshot_susceptance],
                        dtype=float,
                    )
                    cshunt.g_steps = np.zeros(1, dtype=float)
                    cshunt.active_steps = np.ones(1, dtype=int)
                    cshunt.step = 0
                    # Snapshot replay and native Q/V control are mutually
                    # exclusive static contracts.  Keeping QVDroop active here
                    # makes the power-flow formulation discard the solved
                    # susceptance above and recompute another operating point.
                    # Lock only the static host; an associated RMS composite
                    # remains attached to the same typed ElmSvs device and owns
                    # every temporal control action after initialization.
                    cshunt.control_mode = ShuntControlMode.Locked
                else:
                    pass
                grid.add_controllable_shunt(bus=bus, api_obj=cshunt)


def _add_elmcoup_switches(dgs_grid: DgsCircuit,
                          grid: dev.MultiCircuit,
                          cubics_by_objid: Dict[str, List[StaCubic]],
                          bus_by_term_id: Dict[str, dev.Bus],
                          switch_by_cubic_id: Dict[str, StaSwitch],
                          typ_switch_dict: Dict[str, TypSwitch],
                          baseMVA: float,
                          logger: Logger) -> None:
    """
    Add elmcoup switches.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param typ_switch_dict: typ_switch_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    vg_switches: List[dev.Switch] = convert_dgs_to_switches_from_elmcoup(
        elmcoups=dgs_grid.elmcoups,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        typ_switch_by_id=typ_switch_dict,
        sbase_mva=baseMVA,
        logger=logger
    )
    for switch in vg_switches:
        grid.add_switch(obj=switch)


def _add_elmzpu_series_reactances(dgs_grid: DgsCircuit,
                                  grid: dev.MultiCircuit,
                                  bus_by_term_id: Dict[str, dev.Bus],
                                  stacubic_dict: Dict[str, List[int]],
                                  cubics_by_objid: Dict[str, List[StaCubic]],
                                  logger: Logger,
                                  baseMVA: float,
                                  switch_by_cubic_id: Dict[str, StaSwitch],
                                  branch_group_by_id: Dict[str, dev.BranchGroup]) -> None:
    """
    Add elmzpu series reactances.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param logger: logger parameter.
    :param baseMVA: baseMVA parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :param branch_group_by_id: branch_group_by_id parameter.
    :return: Function result.
    """
    for elmzpu in dgs_grid.elmzpus:
        reactance = convert_dgs_common_impedance_to_series_reactance(
            element=elmzpu,
            buses=grid.buses,
            bus_by_terminal_id=bus_by_term_id,
            stacubic_dict=stacubic_dict,
            cubics_by_obj_id=cubics_by_objid,
            logger=logger,
            Sbase_vg=baseMVA,
            switch_by_cubic_id=switch_by_cubic_id,
        )
        fold_id = _ref_id(elmzpu.fold_id)
        if fold_id is not None and fold_id != "":
            branch_group = branch_group_by_id.get(fold_id)
            if branch_group is not None:
                reactance.group = branch_group
        grid.add_series_reactance(reactance)


def _add_elmscap_series_reactances(dgs_grid: DgsCircuit,
                                   grid: dev.MultiCircuit,
                                   bus_by_term_id: Dict[str, dev.Bus],
                                   stacubic_dict: Dict[str, List[int]],
                                   cubics_by_objid: Dict[str, List[StaCubic]],
                                   logger: Logger,
                                   baseMVA: float,
                                   switch_by_cubic_id: Dict[str, StaSwitch],
                                   branch_group_by_id: Dict[str, dev.BranchGroup]) -> None:
    """
    Add elmscap series reactances.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param logger: logger parameter.
    :param baseMVA: baseMVA parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :param branch_group_by_id: branch_group_by_id parameter.
    :return: Function result.
    """
    for elmscap in dgs_grid.elmscaps:
        reactance = convert_dgs_series_capacitor_to_reactance(
            element=elmscap,
            buses=grid.buses,
            bus_by_terminal_id=bus_by_term_id,
            stacubic_dict=stacubic_dict,
            cubics_by_obj_id=cubics_by_objid,
            logger=logger,
            sbase_mva=baseMVA,
            switch_by_cubic_id=switch_by_cubic_id,
        )
        fold_id = _ref_id(elmscap.fold_id)
        if fold_id is not None and fold_id != "":
            branch_group = branch_group_by_id.get(fold_id)
            if branch_group is not None:
                reactance.group = branch_group
        grid.add_series_reactance(obj=reactance)


def _add_elmsind_series_reactances(dgs_grid: DgsCircuit,
                                   grid: dev.MultiCircuit,
                                   bus_by_term_id: Dict[str, dev.Bus],
                                   stacubic_dict: Dict[str, List[int]],
                                   cubics_by_objid: Dict[str, List[StaCubic]],
                                   typsind_raw_dict: Dict[str, TypSind],
                                   logger: Logger,
                                   baseMVA: float,
                                   switch_by_cubic_id: Dict[str, StaSwitch],
                                   branch_group_by_id: Dict[str, dev.BranchGroup]) -> None:
    """
    Add elmsind series reactances.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param typsind_raw_dict: typsind_raw_dict parameter.
    :param logger: logger parameter.
    :param baseMVA: baseMVA parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :param branch_group_by_id: branch_group_by_id parameter.
    :return: Function result.
    """
    for elmsind in dgs_grid.elmsinds:
        reactance = convert_dgs_to_series_reactance(
            element=elmsind,
            buses=grid.buses,
            bus_by_terminal_id=bus_by_term_id,
            stacubic_dict=stacubic_dict,
            cubics_by_obj_id=cubics_by_objid,
            typsind_dict=typsind_raw_dict,
            logger=logger,
            sbase_mva=baseMVA,
            switch_by_cubic_id=switch_by_cubic_id,
        )
        fold_id = _ref_id(elmsind.fold_id)
        if fold_id is not None and fold_id != "":
            branch_group = branch_group_by_id.get(fold_id)
            if branch_group is not None:
                reactance.group = branch_group
        grid.add_series_reactance(obj=reactance)


def _add_elmtr2_transformers(dgs_grid: DgsCircuit,
                             grid: dev.MultiCircuit,
                             stacubic_dict: Dict[str, List[int]],
                             typtr2_dict: Dict[str, dev.TransformerType],
                             typtr2_raw_dict: Dict[str, TypTr2],
                             frequency: float,
                             baseMVA: float,
                             logger: Logger,
                             cubics_by_objid: Dict[str, List[StaCubic]],
                              bus_by_term_id: Dict[str, dev.Bus],
                              switch_by_cubic_id: Dict[str, StaSwitch],
                              branch_group_by_id: Dict[str, dev.BranchGroup],
                              use_power_flow_snapshot: bool = False,
                              use_power_flow_tap_guess: bool = False) -> None:
    """
    Add elmtr2 transformers.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typtr2_dict: typtr2_dict parameter.
    :param typtr2_raw_dict: typtr2_raw_dict parameter.
    :param frequency: frequency parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param branch_group_by_id: branch_group_by_id parameter.
    :param use_power_flow_snapshot: Use solved transformer tap positions.
    :param use_power_flow_tap_guess: Seed solved taps while retaining controls.
    :return: Function result.
    """
    for elmtr2 in dgs_grid.elmtr2s:
        parallel_count = _get_parallel_device_count(count=int(elmtr2.ntnum))
        for parallel_index in range(parallel_count):
            trafo = convert_dgs_to_transformer(
                tr2=elmtr2,
                buses=grid.buses,
                stacubic_dict=stacubic_dict,
                templates_dict=typtr2_dict,
                typtr2_dict=typtr2_raw_dict,
                freq=frequency,
                baseMVA=baseMVA,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                switch_by_cubic_id=switch_by_cubic_id,
                parallel_index=parallel_index,
                parallel_count=parallel_count,
                use_power_flow_snapshot=use_power_flow_snapshot,
                use_power_flow_tap_guess=use_power_flow_tap_guess,
            )
            fold_id = _ref_id(elmtr2.fold_id)
            if fold_id is not None and fold_id != "":
                branch_group = branch_group_by_id.get(fold_id)
                if branch_group is not None:
                    trafo.group = branch_group
            grid.add_transformer2w(obj=trafo)


def _add_elmtr3_transformers(dgs_grid: DgsCircuit,
                             grid: dev.MultiCircuit,
                             stacubic_dict: Dict[str, List[int]],
                             typtr3_dict: Dict[str, TypTr3],
                             baseMVA: float,
                             logger: Logger,
                             cubics_by_objid: Dict[str, List[StaCubic]],
                             bus_by_term_id: Dict[str, dev.Bus],
                             switch_by_cubic_id: Dict[str, StaSwitch],
                             branch_group_by_id: Dict[str, dev.BranchGroup],
                             use_power_flow_snapshot: bool,
                             use_power_flow_tap_guess: bool = False) -> None:
    """
    Add elmtr3 transformers.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typtr3_dict: typtr3_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param branch_group_by_id: branch_group_by_id parameter.
    :param use_power_flow_snapshot: Freeze automatic tap controls for snapshot replay.
    :param use_power_flow_tap_guess: Seed solved taps while retaining controls.
    :return: Function result.
    """
    for elmtr3 in dgs_grid.elmtr3s:
        tr3_typ_id: str | None = _ref_id(elmtr3.typ_id)
        if tr3_typ_id is None or tr3_typ_id == "":
            logger.add_warning(
                f"missing typ_id (no TypTr3 reference in DGS)",
                device=f"{elmtr3.loc_name}' (ID={elmtr3.ID}) ",
                device_class="Transformer3W",
            )
            continue
        if typtr3_dict.get(tr3_typ_id, None) is None:
            logger.add_warning(
                f"referenced TypTr3 not found",
                device=f"{elmtr3.loc_name}' (ID={elmtr3.ID}) ",
                device_class="Transformer3W",
                value=str(elmtr3.typ_id)
            )
            continue
        term_ids: List[str] = get_terminal_ids(element_id=elmtr3.ID, cubics_by_objid=cubics_by_objid)
        if len(term_ids) != 3:
            bus_ids: List[int] | None = stacubic_dict.get(_ref_id(elmtr3.ID), None)
            if bus_ids is None or len(bus_ids) != 3:
                logger.add_warning(
                    f"Not connected to exactly 3 terminals",
                    device=f"{elmtr3.loc_name}' (ID={elmtr3.ID}) ",
                    device_class="Transformer3W",
                )
                continue
        parallel_count = _get_parallel_device_count(count=int(elmtr3.nt3nm))
        for parallel_index in range(parallel_count):
            trafo3w: dev.Transformer3W = convert_dgs_to_transformer3w(
                tr3=elmtr3,
                buses=grid.buses,
                stacubic_dict=stacubic_dict,
                templates_dict=typtr3_dict,
                baseMVA=baseMVA,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                switch_by_cubic_id=switch_by_cubic_id,
                parallel_index=parallel_index,
                parallel_count=parallel_count,
                use_power_flow_snapshot=use_power_flow_snapshot,
                use_power_flow_tap_guess=use_power_flow_tap_guess,
            )
            fold_id = _ref_id(elmtr3.fold_id)
            if fold_id is not None and fold_id != "":
                branch_group = branch_group_by_id.get(fold_id)
                if branch_group is not None:
                    trafo3w.winding1.group = branch_group
                    trafo3w.winding2.group = branch_group
                    trafo3w.winding3.group = branch_group
            # ``add_transformer3w`` owns the synthetic star-point bus and all
            # three windings. Adding that same object separately creates one
            # duplicate isolated bus per transformer and corrupts inventories.
            grid.add_transformer3w(obj=trafo3w)
            template: TypTr3 | None = typtr3_dict.get(tr3_typ_id, None)
            if template is not None:
                _add_transformer3w_magnetizing_shunt(
                    grid=grid,
                    transformer=trafo3w,
                    transformer_element=elmtr3,
                    template=template,
                    logger=logger,
                )
            else:
                # The type was validated before entering the parallel-device
                # loop; this explicit state keeps the importer total.
                pass

def _add_elmtr4_transformers(dgs_grid: DgsCircuit,
                             grid: dev.MultiCircuit,
                             stacubic_dict: Dict[str, List[int]],
                             typtr4_dict: Dict[str, TypTr4],
                             baseMVA: float,
                             logger: Logger,
                             cubics_by_objid: Dict[str, List[StaCubic]],
                             bus_by_term_id: Dict[str, dev.Bus],
                             switch_by_cubic_id: Dict[str, StaSwitch],
                             branch_group_by_id: Dict[str, dev.BranchGroup],
                             use_power_flow_snapshot: bool = False,
                             use_power_flow_tap_guess: bool = False) -> None:
    """
    Add elmtr3 transformers.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typtr3_dict: typtr3_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param branch_group_by_id: branch_group_by_id parameter.
    :param use_power_flow_snapshot: Freeze solved tap positions.
    :param use_power_flow_tap_guess: Seed solved taps while retaining controls.
    :return: Function result.
    """
    for elmtr4 in dgs_grid.elmtr4s:
        tr4_typ_id: str | None = _ref_id(elmtr4.typ_id)
        if tr4_typ_id is None or tr4_typ_id == "":
            logger.add_warning(
                f"missing typ_id (no TypTr4 reference in DGS)",
                device=f"{elmtr4.loc_name}' (ID={elmtr4.ID}) ",
                device_class="Transformer4W",
            )
            continue
        if typtr4_dict.get(tr4_typ_id, None) is None:
            logger.add_warning(
                f"referenced TypTr4 not found",
                device=f"{elmtr4.loc_name}' (ID={elmtr4.ID}) ",
                device_class="Transformer4W",
                value=str(elmtr4.typ_id)
            )
            continue
        term_ids: List[str] = get_terminal_ids(element_id=elmtr4.ID, cubics_by_objid=cubics_by_objid)
        if len(term_ids) != 4:
            bus_ids: List[int] | None = stacubic_dict.get(_ref_id(elmtr4.ID), None)
            if bus_ids is None or len(bus_ids) != 4:
                logger.add_warning(
                    f"Not connected to exactly 4 terminals",
                    device=f"{elmtr4.loc_name}' (ID={elmtr4.ID}) ",
                    device_class="Transformer4W",
                )
                continue
        parallel_count = _get_parallel_device_count(count=int(elmtr4.nt4nm))
        for parallel_index in range(parallel_count):
            trafo4w: dev.TransformerNW = convert_dgs_to_transformer4w(
                tr4=elmtr4,
                buses=grid.buses,
                stacubic_dict=stacubic_dict,
                templates_dict=typtr4_dict,
                baseMVA=baseMVA,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                switch_by_cubic_id=switch_by_cubic_id,
                parallel_index=parallel_index,
                parallel_count=parallel_count,
                use_power_flow_snapshot=use_power_flow_snapshot,
                use_power_flow_tap_guess=use_power_flow_tap_guess,
            )
            grid.add_bus(obj=trafo4w.bus0)
            fold_id = _ref_id(elmtr4.fold_id)
            if fold_id is not None and fold_id != "":
                branch_group = branch_group_by_id.get(fold_id)
                if branch_group is not None:
                    for winding in trafo4w.windings:
                        winding.group = branch_group
            grid.add_transformer_nw(obj=trafo4w)
            template: TypTr4 | None = typtr4_dict.get(tr4_typ_id, None)
            if template is not None:
                _add_transformer4w_magnetizing_shunt(
                    grid=grid,
                    transformer=trafo4w,
                    transformer_element=elmtr4,
                    template=template,
                    system_base_mva=baseMVA,
                    logger=logger,
                )
            else:
                # The type was validated before entering the parallel-device
                # loop; this explicit state keeps the importer total.
                pass


def _build_stacubic_mappings(stacubics: List[StaCubic]) -> Tuple[Dict[str, List[int]], Dict[str, List[StaCubic]]]:
    """
    Build stacubic mappings.

    :param stacubics: stacubics parameter.
    :return: Function result.
    """
    stacubic_dict: Dict[str, List[int]] = dict()
    cubics_by_objid: Dict[str, List[StaCubic]] = dict()
    for cb in stacubics:
        if cb.obj_id is not None:
            obj_id = _ref_id(cb.obj_id)
            if obj_id is not None:
                lst_bus = stacubic_dict.get(obj_id, None)
                if lst_bus is None:
                    stacubic_dict[obj_id] = [cb.obj_bus]
                else:
                    lst_bus.append(cb.obj_bus)

                lst_cubic = cubics_by_objid.get(obj_id, None)
                if lst_cubic is None:
                    cubics_by_objid[obj_id] = [cb]
                else:
                    lst_cubic.append(cb)

                if cb.obj_id != obj_id:
                    lst_bus_raw = stacubic_dict.get(cb.obj_id, None)
                    if lst_bus_raw is None:
                        stacubic_dict[cb.obj_id] = [cb.obj_bus]
                    else:
                        lst_bus_raw.append(cb.obj_bus)

                    lst_cubic_raw = cubics_by_objid.get(cb.obj_id, None)
                    if lst_cubic_raw is None:
                        cubics_by_objid[cb.obj_id] = [cb]
                    else:
                        lst_cubic_raw.append(cb)
                else:
                    pass
            else:
                pass
        else:
            pass
    return stacubic_dict, cubics_by_objid


def _add_graphically_inferred_line_cubicles(
        dgs_grid: DgsCircuit,
        stacubic_dict: Dict[str, List[int]],
        cubics_by_objid: Dict[str, List[StaCubic]],
        logger: Logger,
) -> int:
    """Recover a uniquely drawn line endpoint omitted from ``StaCubic``.

    Some PowerFactory diagrams connect a line to an electrical ``PointTerm``
    while the ASCII export omits that one cubicle row.  The branch-side
    ``IntGrfcon.iDatConNr`` and an exact endpoint/terminal coordinate match are
    structural topology evidence; no solved P/Q value is used.  Recovery is
    fail-closed unless one incomplete line side resolves to exactly one
    ``ElmTerm`` in the same diagram.

    :param dgs_grid: Parsed source circuit containing electrical and schematic rows.
    :param stacubic_dict: Legacy element-side lookup, updated in place.
    :param cubics_by_objid: Equipment cubicles, updated in place.
    :param logger: Import logger receiving one trace per recovered endpoint.
    :return: Number of synthetic connectivity records added.
    """
    line_by_id: Dict[str, ElmLne] = dict()
    source_line: ElmLne
    for source_line in dgs_grid.elmlnes:
        line_id: str = normalize_dgs_ref_id(source_line.ID)
        if line_id != "":
            line_by_id[line_id] = source_line
        else:
            pass
    else:
        pass

    terminal_ids: Set[str] = set()
    source_terminal: ElmTerm
    for source_terminal in dgs_grid.elmterms:
        terminal_id: str = normalize_dgs_ref_id(source_terminal.ID)
        if terminal_id != "":
            terminal_ids.add(terminal_id)
        else:
            pass
    else:
        pass

    line_graphics_by_id: Dict[str, List[IntGrf]] = dict()
    terminal_graphics_by_diagram_id: Dict[str, List[IntGrf]] = dict()
    source_graphic: IntGrf
    for source_graphic in dgs_grid.intgrfs:
        object_id: str = normalize_dgs_ref_id(source_graphic.pDataObj)
        diagram_id: str = normalize_dgs_ref_id(source_graphic.fold_id)
        if object_id in line_by_id:
            line_graphics_by_id.setdefault(object_id, list()).append(source_graphic)
        else:
            pass
        if object_id in terminal_ids and diagram_id != "":
            terminal_graphics_by_diagram_id.setdefault(
                diagram_id,
                list(),
            ).append(source_graphic)
        else:
            pass
    else:
        pass

    connections_by_graphic_id: Dict[str, List[IntGrfcon]] = (
        build_connections_by_graphic_id(dgs_grid=dgs_grid)
    )
    recovered_count: int = 0
    coordinate_tolerance: float = 1.0e-6
    line_id: str
    for line_id in line_by_id:
        existing_cubicles: List[StaCubic] = list()
        candidate_cubic: StaCubic
        for candidate_cubic in cubics_by_objid.get(line_id, list()):
            existing_terminal_id: str = normalize_dgs_ref_id(
                candidate_cubic.fold_id
            )
            if existing_terminal_id != "":
                existing_cubicles.append(candidate_cubic)
            else:
                pass
        else:
            pass

        has_one_structural_endpoint: bool = bool(
            len(existing_cubicles) == 1
            and int(existing_cubicles[0].obj_bus) in (0, 1)
        )
        if has_one_structural_endpoint:
            existing_side: int = int(existing_cubicles[0].obj_bus)
            missing_side: int = 1 - existing_side
            existing_terminal_id = normalize_dgs_ref_id(
                existing_cubicles[0].fold_id
            )
            inferred_terminal_ids: Set[str] = set()
            line_graphic: IntGrf
            for line_graphic in line_graphics_by_id.get(line_id, list()):
                line_graphic_id: str = normalize_dgs_ref_id(line_graphic.ID)
                diagram_id = normalize_dgs_ref_id(line_graphic.fold_id)
                graphical_connection: IntGrfcon
                for graphical_connection in connections_by_graphic_id.get(
                        line_graphic_id,
                        list(),
                ):
                    connection_is_missing_side: bool = bool(
                        int(graphical_connection.iDatConNr) == missing_side
                    )
                    if connection_is_missing_side:
                        connection_points: List[Tuple[float, float]] = (
                            extract_dgs_connection_points(
                                connection=graphical_connection
                            )
                        )
                        if len(connection_points) > 0:
                            endpoint_x: float
                            endpoint_y: float
                            endpoint_x, endpoint_y = connection_points[-1]
                            terminal_graphic: IntGrf
                            for terminal_graphic in (
                                    terminal_graphics_by_diagram_id.get(
                                        diagram_id,
                                        list(),
                                    )
                            ):
                                coordinate_distance: float = math.hypot(
                                    float(terminal_graphic.rCenterX) - endpoint_x,
                                    float(terminal_graphic.rCenterY) - endpoint_y,
                                )
                                matched_terminal_id: str = normalize_dgs_ref_id(
                                    terminal_graphic.pDataObj
                                )
                                is_unique_endpoint_candidate: bool = bool(
                                    coordinate_distance <= coordinate_tolerance
                                    and matched_terminal_id != existing_terminal_id
                                )
                                if is_unique_endpoint_candidate:
                                    inferred_terminal_ids.add(matched_terminal_id)
                                else:
                                    pass
                            else:
                                pass
                        else:
                            pass
                    else:
                        pass
                else:
                    pass
            else:
                pass

            if len(inferred_terminal_ids) == 1:
                inferred_terminal_id: str = next(iter(inferred_terminal_ids))
                inferred_cubic: StaCubic = StaCubic()
                inferred_cubic.ID = f"graphical:{line_id}:{missing_side}"
                inferred_cubic.loc_name = f"Graphically inferred side {missing_side}"
                inferred_cubic.fold_id = inferred_terminal_id
                inferred_cubic.obj_bus = missing_side
                inferred_cubic.obj_id = line_id
                cubics_by_objid.setdefault(line_id, list()).append(inferred_cubic)
                stacubic_dict.setdefault(line_id, list()).append(missing_side)
                recovered_count += 1
                logger.add_info(
                    msg="Recovered missing line cubicle from unique schematic endpoint",
                    device=line_id,
                    value=inferred_terminal_id,
                    expected_value=f"line side {missing_side}",
                )
            else:
                pass
        else:
            pass
    else:
        pass

    return recovered_count


def _build_cubic_by_id(stacubics: List[StaCubic]) -> Dict[str, StaCubic]:
    """
    Index every imported cubicle by its normalized DGS identifier.

    Control pointers such as ``ElmSvs.p_cub`` reference the cubicle itself,
    unlike equipment connectivity which is indexed by ``StaCubic.obj_id``.
    Keeping this as a separate map makes both pointer semantics explicit.

    :param stacubics: Parsed DGS cubicles.
    :return: Cubicle lookup keyed by normalized FID.
    """
    cubic_by_id: Dict[str, StaCubic] = dict()
    cubic: StaCubic
    for cubic in stacubics:
        cubic_id: str | None = _ref_id(cubic.ID)
        if cubic_id is None or cubic_id == "":
            pass
        else:
            cubic_by_id[cubic_id] = cubic
    else:
        pass
    return cubic_by_id


def _build_graphics_positions(intgrfs: List[IntGrf]) -> Dict[str, Tuple[float, float]]:
    """
    Build graphics positions.

    :param intgrfs: intgrfs parameter.
    :return: Function result.
    """
    pos_by_objid: Dict[str, Tuple[float, float]] = dict()
    for graphic in intgrfs:
        pos_by_objid[graphic.pDataObj] = (float(graphic.rCenterX), float(graphic.rCenterY))
    return pos_by_objid


def _add_elmzone_zones(dgs_grid: DgsCircuit, grid: dev.MultiCircuit) -> Dict[str, dev.Zone]:
    """
    Add elmzone zones.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    zone_by_id: Dict[str, dev.Zone] = dict()
    for elmzone in dgs_grid.elmzones:
        zid = _ref_id(elmzone.ID)
        zone_name: str = elmzone.loc_name if elmzone.loc_name != "" else f"Zone_{zid}"
        zone = dev.Zone(name=zone_name, idtag=zid, code="", latitude=0.0, longitude=0.0, area=None)
        grid.add_zone(zone)
        if zid is not None:
            zone_by_id[zid] = zone
    return zone_by_id


def _add_elmarea_areas(dgs_grid: DgsCircuit, grid: dev.MultiCircuit) -> Dict[str, dev.Area]:
    """
    Add elmarea areas.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    area_by_id: Dict[str, dev.Area] = dict()
    for elmarea in dgs_grid.elmareas:
        aid = _ref_id(elmarea.ID)
        area_name: str = elmarea.loc_name if elmarea.loc_name != "" else f"Area_{aid}"
        area = dev.Area(name=area_name, idtag=aid, code="", latitude=0.0, longitude=0.0)
        grid.add_area(area)
        if aid is not None:
            area_by_id[aid] = area
    return area_by_id


def _add_elmbranch_groups(dgs_grid: DgsCircuit, grid: dev.MultiCircuit) -> Dict[str, dev.BranchGroup]:
    """
    Add elmbranch groups.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    branch_group_by_id: Dict[str, dev.BranchGroup] = dict()
    for elmbranch in dgs_grid.elmbranches:
        bid = _ref_id(elmbranch.ID)
        name: str = elmbranch.loc_name if elmbranch.loc_name != "" else f"BranchGroup_{bid}"
        branch_group = dev.BranchGroup(name=name, code="", idtag=bid)
        grid.add_branch_group(obj=branch_group)
        if bid is not None and bid != "":
            branch_group_by_id[bid] = branch_group
    return branch_group_by_id


def _add_elmterm_buses(dgs_grid: DgsCircuit,
                       grid: dev.MultiCircuit,
                       pos_by_objid: Dict[str, Tuple[float, float]],
                       use_power_flow_snapshot: bool = False) -> Dict[str, dev.Bus]:
    """
    Add elmterm buses.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param pos_by_objid: pos_by_objid parameter.
    :param use_power_flow_snapshot: Permit solved terminal initial values.
    :return: Function result.
    """
    bus_by_term_id: Dict[str, dev.Bus] = dict()
    for elmterm in dgs_grid.elmterms:
        bus = convert_dgs_to_bus(
            elmterm=elmterm,
            pos_by_objid=pos_by_objid,
            use_power_flow_snapshot=use_power_flow_snapshot,
        )
        grid.add_bus(obj=bus)
        tid = _ref_id(elmterm.ID)
        if tid is not None:
            bus_by_term_id[tid] = bus
    return bus_by_term_id


def _assign_elmterm_zone_references(dgs_grid: DgsCircuit,
                                    bus_by_term_id: Dict[str, dev.Bus],
                                    zone_by_id: Dict[str, dev.Zone]) -> None:
    """
    Assign elmterm zone references.

    :param dgs_grid: dgs_grid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param zone_by_id: zone_by_id parameter.
    :return: Function result.
    """
    for elmterm in dgs_grid.elmterms:
        tid = _ref_id(elmterm.ID)
        zid = _ref_id(elmterm.cpZone)
        if tid is not None and zid is not None and zid != "":
            bus = bus_by_term_id.get(tid, None)
            zone = zone_by_id.get(zid, None)
            if bus is not None:
                bus.zone = zone


def _assign_elmterm_area_references(dgs_grid: DgsCircuit,
                                    bus_by_term_id: Dict[str, dev.Bus],
                                    area_by_id: Dict[str, dev.Area]) -> None:
    """
    Assign elmterm area references.

    :param dgs_grid: dgs_grid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param area_by_id: area_by_id parameter.
    :return: Function result.
    """
    for elmterm in dgs_grid.elmterms:
        tid = _ref_id(elmterm.ID)
        aid = _ref_id(elmterm.cpArea)
        if tid is not None and aid is not None and aid != "":
            bus = bus_by_term_id.get(tid, None)
            area = area_by_id.get(aid, None)
            if bus is not None:
                bus.area = area


def _build_typsym_dict(dgs_grid: DgsCircuit) -> Dict[str, TypSym]:
    """
    Build typsym dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typsym_dict: Dict[str, TypSym] = dict()
    for typsym in dgs_grid.typsyms:
        typsym_dict[typsym.ID] = typsym
        tid = _ref_id(typsym.ID)
        if tid is not None:
            typsym_dict[tid] = typsym
    return typsym_dict


def _build_typasmo_dict(dgs_grid: DgsCircuit) -> Dict[str, TypAsmo]:
    """
    Build typasmo dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typasmo_dict: Dict[str, TypAsmo] = dict()
    for typasmo in dgs_grid.typasmos:
        typasmo_dict[typasmo.ID] = typasmo
        tid = _ref_id(typasmo.ID)
        if tid is not None:
            typasmo_dict[tid] = typasmo
    return typasmo_dict


def _build_typswitch_dict(dgs_grid: DgsCircuit) -> Dict[str, TypSwitch]:
    """
    Build typswitch dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typ_switch_dict: Dict[str, TypSwitch] = dict()
    for typ_switch in dgs_grid.typswitches:
        typ_switch_dict[typ_switch.ID] = typ_switch
        tid = _ref_id(typ_switch.ID)
        if tid is not None:
            typ_switch_dict[tid] = typ_switch
    return typ_switch_dict


def _build_typlne_templates(dgs_grid: DgsCircuit,
                            grid: dev.MultiCircuit) -> Dict[str, dev.SequenceLineType]:
    """
    Build typlne templates.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    typlne_dict: Dict[str, dev.SequenceLineType] = dict()
    for typlne in dgs_grid.typlnes:
        seq_lne = convert_dgs_to_sequence_line(typlne=typlne)
        grid.add_sequence_line(obj=seq_lne)
        typlne_dict[typlne.ID] = seq_lne
    return typlne_dict


def _build_typcon_catalogues(dgs_grid: DgsCircuit,
                             grid: dev.MultiCircuit) -> Tuple[Dict[str, TypCon], Dict[str, Wire]]:
    """
    Build typcon catalogues.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    typcon_raw_dict: Dict[str, TypCon] = dict()
    wire_type_dict: Dict[str, Wire] = dict()
    for typcon in dgs_grid.typcons:
        cid = _ref_id(typcon.ID)
        if cid is not None:
            typcon_raw_dict[cid] = typcon
            typcon_raw_dict[typcon.ID] = typcon
            wire = convert_dgs_to_wire(typcon=typcon)
            wire_type_dict[cid] = wire
            wire_type_dict[typcon.ID] = wire
            grid.wire_types.append(wire)
        else:
            pass
    return typcon_raw_dict, wire_type_dict


def _add_typtow_templates(dgs_grid: DgsCircuit,
                          grid: dev.MultiCircuit,
                          typcon_raw_dict: Dict[str, TypCon],
                          wire_type_dict: Dict[str, Wire],
                          typlne_dict: Dict[str, dev.SequenceLineType],
                          frequency: float,
                          logger: Logger) -> Dict[str, dev.OverheadLineType]:
    """
    Add typtow templates.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param typcon_raw_dict: typcon_raw_dict parameter.
    :param wire_type_dict: wire_type_dict parameter.
    :param typlne_dict: typlne_dict parameter.
    :param frequency: frequency parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    overhead_line_type_dict: Dict[str, dev.OverheadLineType] = dict()
    for typtow in dgs_grid.typtows:
        tow_id = _ref_id(typtow.ID)
        if tow_id is not None:
            if typtow.i_mode == 0:
                ohl_type = convert_dgs_to_overhead_line_type_geometrical_parameters(
                    typtow=typtow,
                    typcon_by_id=typcon_raw_dict,
                    wire_by_id=wire_type_dict,
                    default_frequency_hz=frequency,
                )
                overhead_line_type_dict[tow_id] = ohl_type
                overhead_line_type_dict[typtow.ID] = ohl_type
                grid.overhead_line_types.append(ohl_type)
            elif typtow.i_mode == 1:
                ohl_type = convert_dgs_to_overhead_line_type_electrical_parameters(
                    typtow=typtow,
                    typcon_by_id=typcon_raw_dict,
                    wire_by_id=wire_type_dict,
                    default_frequency_hz=frequency,
                )
                typlne_dict[tow_id] = ohl_type
                typlne_dict[typtow.ID] = ohl_type
                grid.sequence_line_types.append(ohl_type)
            else:
                logger.add_warning("TypTow i_mode not recognized",
                                   device_class="TypTow",
                                   device_property="i_mode",
                                   value=typtow.i_mode)
        else:
            pass
    return overhead_line_type_dict


def _build_typtr2_templates(dgs_grid: DgsCircuit,
                            grid: dev.MultiCircuit) -> Tuple[Dict[str, dev.TransformerType], Dict[str, TypTr2]]:
    """
    Build typtr2 templates.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    typtr2_dict: Dict[str, dev.TransformerType] = dict()
    typtr2_raw_dict: Dict[str, TypTr2] = dict()
    for typtr2 in dgs_grid.typtr2s:
        transformer_type = convert_dgs_to_transformer_type(typtr2=typtr2)
        grid.add_transformer_type(obj=transformer_type)
        typtr2_dict[typtr2.ID] = transformer_type
        typtr2_raw_dict[typtr2.ID] = typtr2
        tid = _ref_id(typtr2.ID)
        if tid is not None:
            typtr2_dict[tid] = transformer_type
            typtr2_raw_dict[tid] = typtr2
        else:
            pass
    return typtr2_dict, typtr2_raw_dict


def _build_typtr3_dict(dgs_grid: DgsCircuit) -> Dict[str, TypTr3]:
    """
    Build typtr3 dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typtr3_dict: Dict[str, TypTr3] = dict()
    for typtr3 in dgs_grid.typtr3s:
        typtr3_dict[typtr3.ID] = typtr3
        tid = _ref_id(typtr3.ID)
        if tid is not None:
            typtr3_dict[tid] = typtr3
        else:
            pass
    return typtr3_dict

def _build_typtr4_dict(dgs_grid: DgsCircuit) -> Dict[str, TypTr4]:
    """
    Build typtr4 dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typtr4_dict: Dict[str, TypTr4] = dict()
    for typtr4 in dgs_grid.typtr4s:
        typtr4_dict[typtr4.ID] = typtr4
        tid = _ref_id(typtr4.ID)
        if tid is not None:
            typtr4_dict[tid] = typtr4
        else:
            pass
    return typtr4_dict


def _build_typsind_dict(dgs_grid: DgsCircuit) -> Dict[str, TypSind]:
    """
    Build typsind dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typsind_raw_dict: Dict[str, TypSind] = dict()
    for typsind in dgs_grid.typsinds:
        typsind_raw_dict[typsind.ID] = typsind
        tid = _ref_id(typsind.ID)
        if tid is not None:
            typsind_raw_dict[tid] = typsind
        else:
            pass
    return typsind_raw_dict


def _build_line_section_type_maps(dgs_grid: DgsCircuit,
                                  logger: Logger) -> Tuple[Dict[str, str], Dict[str, List[ElmLnesec]]]:
    """
    Build line section type maps.

    :param dgs_grid: dgs_grid parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    line_type_by_line_id: Dict[str, str] = dict()
    line_sections_by_line_id: Dict[str, List[ElmLnesec]] = dict()

    line_ids: Set[str] = set()
    for elmlne in dgs_grid.elmlnes:
        if elmlne.ID != "":
            line_ids.add(elmlne.ID)
            rid = _ref_id(elmlne.ID)
            if rid is not None and rid != "":
                line_ids.add(rid)
            else:
                pass

    folder_parent: Dict[str, str] = dict()
    for folder in dgs_grid.intfolders:
        if folder.ID != "":
            folder_parent[folder.ID] = folder.fold_id
            fid = _ref_id(folder.ID)
            if fid is not None and fid != "":
                folder_parent[fid] = folder.fold_id
            else:
                pass
        else:
            pass

    line_id_by_loc_name: Dict[str, str] = _get_unique_name_mapping(
        lines=dgs_grid.elmlnes,
        use_characteristic_name=False
    )
    line_id_by_chr_name: Dict[str, str] = _get_unique_name_mapping(
        lines=dgs_grid.elmlnes,
        use_characteristic_name=True
    )

    for sec in dgs_grid.elmlnesecs:
        owner_line_id = _resolve_line_section_owner_id(
            section=sec,
            line_ids=line_ids,
            folder_parent=folder_parent,
            line_id_by_loc_name=line_id_by_loc_name,
            line_id_by_chr_name=line_id_by_chr_name
        )
        if owner_line_id != "":
            normalized_owner_id = _ref_id(owner_line_id) or owner_line_id
            owned_sections = line_sections_by_line_id.get(normalized_owner_id, None)
            if owned_sections is None:
                line_sections_by_line_id[normalized_owner_id] = list()
                owned_sections = line_sections_by_line_id[normalized_owner_id]
            else:
                pass
            # Every section belongs in the physical series path.  A type
            # pointer is optional because PF supports calculated untyped parts.
            owned_sections.append(sec)

            if sec.typ_id != "":
                typ_id = _ref_id(sec.typ_id) or sec.typ_id
                line_type_by_line_id[owner_line_id] = typ_id
                line_type_by_line_id[normalized_owner_id] = typ_id
            else:
                pass
        else:
            logger.add_warning(
                "Could not resolve owning line for line section.",
                device=sec.loc_name,
                device_class="ElmLnesec",
                value=str(sec.ID)
            )
    return line_type_by_line_id, line_sections_by_line_id


def _build_tower_template_by_line_id(
        dgs_grid: DgsCircuit,
        overhead_line_type_dict: Dict[str, dev.OverheadLineType],
        sequence_line_type_dict: Dict[str, dev.SequenceLineType],
) -> Dict[str, dev.OverheadLineType | dev.SequenceLineType]:
    """
    Build tower template by line id.

    :param dgs_grid: dgs_grid parameter.
    :param overhead_line_type_dict: overhead_line_type_dict parameter.
    :param sequence_line_type_dict: Electrical tower templates by DGS identity.
    :return: Function result.
    """
    tower_template_by_line_id: Dict[
        str,
        dev.OverheadLineType | dev.SequenceLineType,
    ] = dict()
    for elmtow in dgs_grid.elmtows:
        line_index: int
        for line_index in range(len(elmtow.plines)):
            line_ptr: str | None = elmtow.plines[line_index]
            geometry_ptr: str | None = _get_elmtow_geometry_pointer(
                elmtow=elmtow,
                circuit_index=line_index,
            )
            if (
                    line_ptr is not None
                    and line_ptr != ""
                    and geometry_ptr is not None
                    and geometry_ptr != ""
            ):
                geometry_id: str | None = _ref_id(geometry_ptr)
                if geometry_id is not None:
                    overhead_type: dev.OverheadLineType | None = (
                        overhead_line_type_dict.get(geometry_id, None)
                    )
                    if overhead_type is None:
                        overhead_type = overhead_line_type_dict.get(
                            geometry_ptr,
                            None,
                        )
                    else:
                        pass
                    if overhead_type is not None:
                        tower_template: (
                            dev.OverheadLineType | dev.SequenceLineType | None
                        ) = overhead_type
                    else:
                        sequence_type: dev.SequenceLineType | None = (
                            sequence_line_type_dict.get(geometry_id, None)
                        )
                        if sequence_type is None:
                            sequence_type = sequence_line_type_dict.get(
                                geometry_ptr,
                                None,
                            )
                        else:
                            pass
                        tower_template = sequence_type
                    if tower_template is not None:
                        tower_template_by_line_id[line_ptr] = tower_template
                        line_id: str | None = _ref_id(line_ptr)
                        if line_id is not None and line_id != "":
                            tower_template_by_line_id[line_id] = tower_template
                        else:
                            pass
                    else:
                        pass
                else:
                    pass
            else:
                pass
        else:
            pass
    return tower_template_by_line_id


def _get_elmtow_geometry_pointer(
        elmtow: ElmTow,
        circuit_index: int,
) -> str | None:
    """
    Resolve the geometry pointer governing one coupled-line circuit.

    PowerFactory exports either one shared multi-circuit ``TypTow`` pointer or
    one independent ``TypTow`` pointer per ``plines`` entry. Treating the
    latter form as one shared geometry silently assigns circuit zero's
    conductor arrangement to every line.

    :param elmtow: Source tower-coupling element.
    :param circuit_index: Zero-based index in ``ElmTow.plines``.
    :return: Governing geometry pointer or ``None``.
    """
    geometry_count: int = len(elmtow.pGeo)
    if geometry_count == 1:
        pointer: str | None = elmtow.pGeo[0]
    else:
        if geometry_count == len(elmtow.plines) and circuit_index < geometry_count:
            pointer = elmtow.pGeo[circuit_index]
        else:
            pointer = None
    return pointer


def _calculate_open_line_input_admittance_pu(
        resistance_pu: float,
        reactance_pu: float,
        conductance_pu: float,
        susceptance_pu: float,
) -> complex:
    """Calculate the exact pi-line admittance seen from one open circuit.

    :param resistance_pu: Total series resistance in per unit.
    :param reactance_pu: Total series reactance in per unit.
    :param conductance_pu: Total shunt conductance in per unit.
    :param susceptance_pu: Total shunt susceptance in per unit.
    :return: Open-circuit input admittance in per unit.
    """
    series_impedance_pu: complex = complex(resistance_pu, reactance_pu)
    half_shunt_admittance_pu: complex = 0.5 * complex(
        conductance_pu,
        susceptance_pu,
    )
    if abs(series_impedance_pu) > 1.0e-20:
        series_admittance_pu: complex = 1.0 / series_impedance_pu
        remote_path_denominator_pu: complex = (
            series_admittance_pu + half_shunt_admittance_pu
        )
        if abs(remote_path_denominator_pu) > 1.0e-20:
            remote_path_admittance_pu: complex = (
                series_admittance_pu
                * half_shunt_admittance_pu
                / remote_path_denominator_pu
            )
        else:
            remote_path_admittance_pu = complex(0.0, 0.0)
    else:
        remote_path_admittance_pu = half_shunt_admittance_pu
    return half_shunt_admittance_pu + remote_path_admittance_pu


def _add_open_line_terminal_shunt(
        grid: dev.MultiCircuit,
        line: dev.Line,
        source_line: ElmLne,
        terminal_from_closed: bool,
        terminal_to_closed: bool,
        base_mva: float,
) -> None:
    """Preserve charging at the energized end of a switched-open line.

    PowerFactory keeps the complete open-circuit pi equivalent energized: the
    local half shunt remains connected directly and the remote half shunt is
    reached through the series impedance. VeraGrid has one branch-wide active
    flag, so the exact one-port equivalent is an inactive series branch plus
    the calculated input admittance at the energized bus.

    :param grid: Destination circuit receiving the grounded equivalent.
    :param line: Converted physical line with per-unit shunt data.
    :param source_line: DGS line defining the equipment service state.
    :param terminal_from_closed: Connection state at ``line.bus_from``.
    :param terminal_to_closed: Connection state at ``line.bus_to``.
    :param base_mva: Circuit power base in MVA.
    :return: None.
    """
    exactly_one_terminal_closed: bool = bool(
        terminal_from_closed != terminal_to_closed
    )
    source_is_in_service: bool = int(source_line.outserv) == 0
    if source_is_in_service and exactly_one_terminal_closed:
        if terminal_from_closed:
            connected_bus: dev.Bus = line.bus_from
            terminal_label: str = "from"
        else:
            connected_bus = line.bus_to
            terminal_label = "to"
        input_admittance_pu: complex = _calculate_open_line_input_admittance_pu(
            resistance_pu=float(line.R),
            reactance_pu=float(line.X),
            conductance_pu=float(line.G),
            susceptance_pu=float(line.B),
        )
        input_admittance_zero_pu: complex = _calculate_open_line_input_admittance_pu(
            resistance_pu=float(line.R0),
            reactance_pu=float(line.X0),
            conductance_pu=float(line.G0),
            susceptance_pu=float(line.B0),
        )
        open_circuit_shunt: dev.Shunt = dev.Shunt(
            name=f"{line.name}:energized-end charging",
            idtag=f"{line.idtag}:open-{terminal_label}-shunt",
            code=str(source_line.ID),
            G=float(input_admittance_pu.real) * base_mva,
            B=float(input_admittance_pu.imag) * base_mva,
            G0=float(input_admittance_zero_pu.real) * base_mva,
            B0=float(input_admittance_zero_pu.imag) * base_mva,
            active=True,
        )
        grid.add_shunt(bus=connected_bus, api_obj=open_circuit_shunt)
    else:
        pass


def _add_elmlne_lines(dgs_grid: DgsCircuit,
                      grid: dev.MultiCircuit,
                      stacubic_dict: Dict[str, List[int]],
                      typlne_dict: Dict[str, dev.SequenceLineType],
                      overhead_line_type_dict: Dict[str, dev.OverheadLineType],
                      line_type_by_line_id: Dict[str, str],
                      line_sections_by_line_id: Dict[str, List[ElmLnesec]],
                      tower_template_by_line_id: Dict[
                          str,
                          dev.OverheadLineType | dev.SequenceLineType,
                      ],
                      frequency: float,
                      baseMVA: float,
                      logger: Logger,
                      cubics_by_objid: Dict[str, List[StaCubic]],
                      bus_by_term_id: Dict[str, dev.Bus],
                      switch_by_cubic_id: Dict[str, StaSwitch],
                      branch_group_by_id: Dict[str, dev.BranchGroup]) -> Dict[str, List[dev.Line]]:
    """
    Add elmlne lines.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typlne_dict: typlne_dict parameter.
    :param overhead_line_type_dict: overhead_line_type_dict parameter.
    :param line_type_by_line_id: line_type_by_line_id parameter.
    :param line_sections_by_line_id: line_sections_by_line_id parameter.
    :param tower_template_by_line_id: tower_template_by_line_id parameter.
    :param frequency: frequency parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: Cubicle switches keyed by their DGS FID.
    :param branch_group_by_id: branch_group_by_id parameter.
    :return: Function result.
    """
    line_by_dgs_id: Dict[str, List[dev.Line]] = dict()
    active_terminal_edges, source_terminal_ids = (
        _build_active_topology_for_energization(
            dgs_grid=dgs_grid,
            cubics_by_objid=cubics_by_objid,
            switch_by_cubic_id=switch_by_cubic_id,
            bus_by_term_id=bus_by_term_id,
        )
    )
    for elmlne in dgs_grid.elmlnes:
        term_ids: List[str] = get_terminal_ids(element_id=elmlne.ID, cubics_by_objid=cubics_by_objid)
        if len(term_ids) != 2:
            bus_ids: List[int] | None = stacubic_dict.get(_ref_id(elmlne.ID), None)
            if bus_ids is None or len(bus_ids) != 2:
                logger.add_warning(
                    f"not connected to exactly 2 terminals",
                    device=f"{elmlne.loc_name}' (ID={elmlne.ID}) ",
                    device_class="ElmLne",
                    value=len(term_ids),
                    expected_value="2"
                )
                continue

        terminal_from_closed: bool
        terminal_to_closed: bool
        terminal_from_closed, terminal_to_closed = _get_two_terminal_energized_states(
            element_id=elmlne.ID,
            cubics_by_objid=cubics_by_objid,
            switch_by_cubic_id=switch_by_cubic_id,
            bus_by_term_id=bus_by_term_id,
        )
        parallel_count = _get_parallel_device_count(count=int(elmlne.nlnum))
        for parallel_index in range(parallel_count):
            line = convert_dgs_to_line(
                lne=elmlne,
                buses=grid.buses,
                stacubic_dict=stacubic_dict,
                sequence_templates_dict=typlne_dict,
                overhead_line_type_dict=overhead_line_type_dict,
                line_type_by_line_id=line_type_by_line_id,
                line_sections_by_line_id=line_sections_by_line_id,
                tower_template_by_line_id=tower_template_by_line_id,
                freq=frequency,
                baseMVA=baseMVA,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                parallel_index=parallel_index,
                parallel_count=parallel_count,
                switch_by_cubic_id=switch_by_cubic_id,
                active_terminal_edges=active_terminal_edges,
                source_terminal_ids=source_terminal_ids,
            )
            fold_id = _ref_id(elmlne.fold_id)
            if fold_id is not None and fold_id != "":
                branch_group = branch_group_by_id.get(fold_id)
                if branch_group is not None:
                    line.group = branch_group
            grid.add_line(obj=line, logger=logger)
            _add_open_line_terminal_shunt(
                grid=grid,
                line=line,
                source_line=elmlne,
                terminal_from_closed=terminal_from_closed,
                terminal_to_closed=terminal_to_closed,
                base_mva=baseMVA,
            )

            lid_raw = elmlne.ID
            lid = _ref_id(lid_raw)
            if lid is not None:
                line_by_dgs_id.setdefault(lid, list()).append(line)
            else:
                pass
            if lid_raw is not None and lid_raw != "" and str(lid_raw) != str(lid):
                line_by_dgs_id.setdefault(lid_raw, list()).append(line)
            else:
                pass
    return line_by_dgs_id


def _get_tower_sequence_matrix(
        values: List[List[float]],
        circuit_indices: List[int],
) -> np.ndarray | None:
    """Extract one finite square sequence matrix for active tower circuits.

    :param values: Full matrix exported by PowerFactory.
    :param circuit_indices: Zero-based active circuit indices to retain.
    :return: Dense active-circuit matrix, or ``None`` when unavailable.
    """
    matrix_size: int = len(circuit_indices)
    matrix: np.ndarray = np.zeros((matrix_size, matrix_size), dtype=float)
    valid: bool = matrix_size > 0
    row_position: int
    column_position: int
    for row_position in range(matrix_size):
        source_row: int = circuit_indices[row_position]
        if source_row < len(values):
            source_values: List[float] = values[source_row]
            for column_position in range(matrix_size):
                source_column: int = circuit_indices[column_position]
                if source_column < len(source_values):
                    parsed_value: float = float(source_values[source_column])
                    if np.isfinite(parsed_value):
                        matrix[row_position, column_position] = parsed_value
                    else:
                        valid = False
                else:
                    valid = False
            else:
                pass
        else:
            valid = False
    else:
        pass
    if valid:
        result: np.ndarray | None = matrix
    else:
        result = None
    return result


def _apply_tower_transposition_to_positive_matrix(
        matrix: np.ndarray,
        transposition_flags: List[float],
        circuit_indices: List[int],
) -> np.ndarray:
    """Remove positive-sequence mutual terms cancelled by transposition.

    PowerFactory keeps the geometrical off-diagonal matrices in ``TypTow``
    even when an ``ElmTow`` instance transposes one or more circuits. A full
    phase cycle cancels the positive-sequence mutual term between that circuit
    and every other circuit, while the zero-sequence coupling remains.

    :param matrix: Active-circuit positive-sequence parameter matrix.
    :param transposition_flags: Element-level circuit transposition flags.
    :param circuit_indices: Source ``ElmTow.plines`` indices retained in matrix.
    :return: Matrix with cancelled off-diagonal terms set to zero.
    """
    result: np.ndarray = matrix.copy()
    matrix_size: int = len(circuit_indices)
    row_position: int
    column_position: int
    for row_position in range(matrix_size):
        source_row: int = circuit_indices[row_position]
        row_is_transposed: bool = bool(
            source_row < len(transposition_flags)
            and abs(float(transposition_flags[source_row])) > 0.5
        )
        for column_position in range(matrix_size):
            source_column: int = circuit_indices[column_position]
            column_is_transposed: bool = bool(
                source_column < len(transposition_flags)
                and abs(float(transposition_flags[source_column])) > 0.5
            )
            mutual_term_is_cancelled: bool = bool(
                row_position != column_position
                and (row_is_transposed or column_is_transposed)
            )
            if mutual_term_is_cancelled:
                result[row_position, column_position] = 0.0
            else:
                pass
        else:
            pass
    else:
        pass
    return result


def _get_admittance_from_impedance(impedance: complex) -> complex:
    """Return a numerically safe admittance for one matrix self term.

    :param impedance: Series impedance in p.u.
    :return: Series admittance in p.u.
    """
    if abs(impedance) > 1.0e-14:
        admittance: complex = 1.0 / impedance
    else:
        admittance = complex(1.0e14, 0.0)
    return admittance


def _apply_tower_self_conductance(
        active_lines: List[dev.Line],
        active_indices: List[int],
        typtow: TypTow,
        baseMVA: float,
) -> None:
    """Apply every tower circuit's diagonal shunt conductance to its line.

    PowerFactory stores tower conductance only in the ``TypTow.G_c*``
    matrices. A one-circuit tower therefore needs the diagonal term even
    though no mutual equivalent exists. Multi-circuit towers use the same
    physical self term before their off-diagonal correction is synthesized.

    :param active_lines: Imported physical lines retained from the tower.
    :param active_indices: Source matrix index for each imported line.
    :param typtow: Source PowerFactory tower type.
    :param baseMVA: Circuit power base in MVA.
    :return: None.
    """
    circuit_position: int
    for circuit_position in range(len(active_lines)):
        source_index: int = active_indices[circuit_position]
        physical_line: dev.Line = active_lines[circuit_position]
        has_positive_diagonal: bool = bool(
            source_index < len(typtow.G_c1)
            and source_index < len(typtow.G_c1[source_index])
        )
        has_zero_diagonal: bool = bool(
            source_index < len(typtow.G_c0)
            and source_index < len(typtow.G_c0[source_index])
        )
        if has_positive_diagonal:
            positive_conductance_us_per_km: float = float(
                typtow.G_c1[source_index][source_index]
            )
        else:
            positive_conductance_us_per_km = 0.0
        if has_zero_diagonal:
            zero_conductance_us_per_km: float = float(
                typtow.G_c0[source_index][source_index]
            )
        else:
            zero_conductance_us_per_km = 0.0

        # The tower catalogue primitive is generated on the common maximum
        # corridor base by OverheadLineType.apply_template().  Retain that same
        # base for its diagonal conductance until the complete multi-port is
        # transformed to endpoint bases as one atomic operation.
        nominal_voltage_kv: float = float(
            physical_line.get_max_bus_nominal_voltage()
        )
        values_are_usable: bool = bool(
            baseMVA > 0.0
            and nominal_voltage_kv > 0.0
            and np.isfinite(positive_conductance_us_per_km)
            and np.isfinite(zero_conductance_us_per_km)
        )
        if values_are_usable:
            impedance_base_ohm: float = (
                nominal_voltage_kv * nominal_voltage_kv / baseMVA
            )
            conductance_factor: float = (
                float(physical_line.length) * 1.0e-6 * impedance_base_ohm
            )
            physical_line.G = (
                positive_conductance_us_per_km * conductance_factor
            )
            physical_line.G2 = physical_line.G
            physical_line.G0 = zero_conductance_us_per_km * conductance_factor
        else:
            pass
    else:
        pass


def _apply_elmtow_matrix_equivalent(
        grid: dev.MultiCircuit,
        elmtow: ElmTow,
        typtow: TypTow,
        line_by_dgs_id: Dict[str, List[dev.Line]],
        tower_voltage_kv: float,
        baseMVA: float,
        logger: Logger,
) -> None:
    """Represent one coupled tower without losing its matrix contract.

    The original physical lines remain visible and keep their exported self
    parameters and geometry. Both reciprocal and directional mutual terms use
    one equipment-owned nodal stamp, so internal equivalents never appear as
    fake lines or shunts in the GUI.

    :param grid: Destination VeraGrid circuit.
    :param elmtow: PowerFactory tower-coupling instance.
    :param typtow: PowerFactory tower electrical definition.
    :param line_by_dgs_id: Imported physical lines indexed by DGS identifier.
    :param tower_voltage_kv: Nominal voltage of the referenced tower template.
    :param baseMVA: Circuit power base in MVA.
    :param logger: Import logger.
    :return: None.
    """
    active_lines: List[dev.Line] = list()
    active_indices: List[int] = list()
    source_index: int
    for source_index in range(len(elmtow.plines)):
        line_pointer: str | None = elmtow.plines[source_index]
        if line_pointer is not None:
            line_identifier: str | None = _ref_id(line_pointer)
            imported_lines: List[dev.Line] = line_by_dgs_id.get(
                str(line_identifier),
                list(),
            )
            if len(imported_lines) == 0:
                imported_lines = line_by_dgs_id.get(str(line_pointer), list())
            else:
                pass
            unique_lines: List[dev.Line] = list()
            imported_line: dev.Line
            for imported_line in imported_lines:
                already_present: bool = False
                existing_line: dev.Line
                for existing_line in unique_lines:
                    if existing_line is imported_line:
                        already_present = True
                    else:
                        pass
                else:
                    pass
                if already_present:
                    pass
                else:
                    unique_lines.append(imported_line)
            else:
                pass
            if len(unique_lines) == 1 and bool(unique_lines[0].active):
                active_lines.append(unique_lines[0])
                active_indices.append(source_index)
            else:
                if len(unique_lines) > 1:
                    logger.add_warning(
                        "Tower mutual equivalent requires one physical line per circuit.",
                        device=str(elmtow.loc_name),
                        device_class="ElmTow",
                        value=str(line_pointer),
                    )
                else:
                    pass
        else:
            pass
    else:
        pass

    circuit_count: int = len(active_lines)
    _apply_tower_self_conductance(
        active_lines=active_lines,
        active_indices=active_indices,
        typtow=typtow,
        baseMVA=baseMVA,
    )
    if circuit_count > 1:
        lengths: np.ndarray = np.zeros(circuit_count, dtype=float)
        nominal_voltages: np.ndarray = np.zeros(circuit_count, dtype=float)
        circuit_position: int
        for circuit_position in range(circuit_count):
            lengths[circuit_position] = float(active_lines[circuit_position].length)
            # The visible tower geometry and its matrix correction must use the
            # same common base; mixing endpoint and catalogue bases would leave
            # a false correction even when positive mutual terms cancel.
            nominal_voltages[circuit_position] = float(
                active_lines[circuit_position].get_max_bus_nominal_voltage()
            )
        else:
            pass
        tower_voltage_is_usable: bool = bool(tower_voltage_kv > 0.0)
        lengths_are_usable: bool = bool(np.all(lengths > 0.0))
        if tower_voltage_is_usable and lengths_are_usable:
            resistance_positive: np.ndarray | None = _get_tower_sequence_matrix(
                values=typtow.R_c1,
                circuit_indices=active_indices,
            )
            reactance_positive: np.ndarray | None = _get_tower_sequence_matrix(
                values=typtow.X_c1,
                circuit_indices=active_indices,
            )
            susceptance_positive: np.ndarray | None = _get_tower_sequence_matrix(
                values=typtow.B_c1,
                circuit_indices=active_indices,
            )
            conductance_positive: np.ndarray | None = _get_tower_sequence_matrix(
                values=typtow.G_c1,
                circuit_indices=active_indices,
            )
            resistance_zero: np.ndarray | None = _get_tower_sequence_matrix(
                values=typtow.R_c0,
                circuit_indices=active_indices,
            )
            reactance_zero: np.ndarray | None = _get_tower_sequence_matrix(
                values=typtow.X_c0,
                circuit_indices=active_indices,
            )
            susceptance_zero: np.ndarray | None = _get_tower_sequence_matrix(
                values=typtow.B_c0,
                circuit_indices=active_indices,
            )
            conductance_zero: np.ndarray | None = _get_tower_sequence_matrix(
                values=typtow.G_c0,
                circuit_indices=active_indices,
            )
            matrices_available: bool = bool(
                resistance_positive is not None
                and reactance_positive is not None
                and susceptance_positive is not None
                and conductance_positive is not None
                and resistance_zero is not None
                and reactance_zero is not None
                and susceptance_zero is not None
                and conductance_zero is not None
            )
            if matrices_available:
                # R_c1/X_c1/B_c1/G_c1 are PowerFactory's calculated sequence
                # matrices. They already include the ElmTow transposition
                # arrangement. Applying ``ctransp`` again would erase the
                # remaining physical mutual term of a transposed corridor.
                # The matrix is defined on the tower/conductor rated voltage,
                # not on either study-case terminal nominal voltage.  PF can
                # legitimately connect a 220-kV tower between 217/218/226-kV
                # terminals; those differences are handled afterwards by the
                # branch virtual-tap projection.
                voltage_base: float = float(tower_voltage_kv)
                impedance_base: float = voltage_base * voltage_base / baseMVA
                # Parallel circuits can start or finish at slightly different
                # terminal gantries while sharing the same physical tower for
                # the remainder of the route.  A self term spans its circuit's
                # complete length; a mutual term exists only along the common
                # route, which is the shorter of the two circuit lengths.
                coupled_length: np.ndarray = np.minimum.outer(lengths, lengths)
                positive_impedance: np.ndarray = coupled_length * (
                    resistance_positive + 1j * reactance_positive
                ) / impedance_base
                zero_impedance: np.ndarray = coupled_length * (
                    resistance_zero + 1j * reactance_zero
                ) / impedance_base
                positive_shunt: np.ndarray = coupled_length * 1.0e-6 * impedance_base * (
                    conductance_positive + 1j * susceptance_positive
                )
                zero_shunt: np.ndarray = coupled_length * 1.0e-6 * impedance_base * (
                    conductance_zero + 1j * susceptance_zero
                )

                # Reordered phase bundles can make PF's calculated positive-
                # sequence matrix directional. Never erase that information:
                # only genuinely reciprocal matrices may be decomposed into
                # ordinary two-terminal correction branches.
                matrix_is_directional: bool = bool(
                    not np.allclose(
                        positive_impedance,
                        positive_impedance.transpose(),
                        rtol=1.0e-12,
                        atol=1.0e-14,
                    )
                    or not np.allclose(
                        zero_impedance,
                        zero_impedance.transpose(),
                        rtol=1.0e-12,
                        atol=1.0e-14,
                    )
                    or not np.allclose(
                        positive_shunt,
                        positive_shunt.transpose(),
                        rtol=1.0e-12,
                        atol=1.0e-14,
                    )
                    or not np.allclose(
                        zero_shunt,
                        zero_shunt.transpose(),
                        rtol=1.0e-12,
                        atol=1.0e-14,
                    )
                )
                if matrix_is_directional:
                    pass
                else:
                    positive_impedance = 0.5 * (
                        positive_impedance + positive_impedance.transpose()
                    )
                    zero_impedance = 0.5 * (
                        zero_impedance + zero_impedance.transpose()
                    )
                    positive_shunt = 0.5 * (
                        positive_shunt + positive_shunt.transpose()
                    )
                    zero_shunt = 0.5 * (
                        zero_shunt + zero_shunt.transpose()
                    )

                # Use one matrix contract for both the visible circuit
                # diagonals and every synthesized mutual correction.  A
                # second geometry calculation can differ from PF's exported
                # R_c/X_c matrices through rounding and ground-return options;
                # mixing both representations leaves a false nodal residual.
                original_positive_admittances: np.ndarray = np.zeros(
                    circuit_count,
                    dtype=complex,
                )
                original_zero_admittances: np.ndarray = np.zeros(
                    circuit_count,
                    dtype=complex,
                )
                original_positive_shunts: np.ndarray = np.zeros(
                    circuit_count,
                    dtype=complex,
                )
                original_zero_shunts: np.ndarray = np.zeros(
                    circuit_count,
                    dtype=complex,
                )
                for circuit_position in range(circuit_count):
                    physical_line: dev.Line = active_lines[circuit_position]
                    common_positive_impedance: complex = complex(
                        positive_impedance[circuit_position, circuit_position]
                    )
                    common_zero_impedance: complex = complex(
                        zero_impedance[circuit_position, circuit_position]
                    )
                    original_positive_admittances[circuit_position] = (
                        _get_admittance_from_impedance(common_positive_impedance)
                    )
                    original_zero_admittances[circuit_position] = (
                        _get_admittance_from_impedance(common_zero_impedance)
                    )
                    common_positive_shunt: complex = complex(
                        positive_shunt[circuit_position, circuit_position]
                    )
                    common_zero_shunt: complex = complex(
                        zero_shunt[circuit_position, circuit_position]
                    )
                    original_positive_shunts[circuit_position] = common_positive_shunt
                    original_zero_shunts[circuit_position] = common_zero_shunt

                    # Store the visible line on its from-terminal base.  The
                    # generic virtual tap then performs the remaining terminal
                    # base conversion exactly once during compilation.
                    from_voltage_kv: float = float(physical_line.bus_from.Vnom)
                    common_to_from_impedance: float = (
                        voltage_base / from_voltage_kv
                    ) ** 2
                    common_to_from_admittance: float = (
                        1.0 / common_to_from_impedance
                    )
                    from_positive_impedance: complex = (
                        common_positive_impedance * common_to_from_impedance
                    )
                    from_zero_impedance: complex = (
                        common_zero_impedance * common_to_from_impedance
                    )
                    from_positive_shunt: complex = (
                        common_positive_shunt * common_to_from_admittance
                    )
                    from_zero_shunt: complex = (
                        common_zero_shunt * common_to_from_admittance
                    )
                    physical_line.R = float(from_positive_impedance.real)
                    physical_line.X = float(from_positive_impedance.imag)
                    physical_line.R0 = float(from_zero_impedance.real)
                    physical_line.X0 = float(from_zero_impedance.imag)
                    physical_line.R2 = physical_line.R
                    physical_line.X2 = physical_line.X
                    physical_line.G = float(from_positive_shunt.real)
                    physical_line.B = float(from_positive_shunt.imag)
                    physical_line.G0 = float(from_zero_shunt.real)
                    physical_line.B0 = float(from_zero_shunt.imag)
                    physical_line.G2 = physical_line.G
                    physical_line.B2 = physical_line.B
                else:
                    pass
                try:
                    positive_series: np.ndarray = np.linalg.inv(positive_impedance)
                    zero_series: np.ndarray = np.linalg.inv(zero_impedance)
                except np.linalg.LinAlgError:
                    logger.add_warning(
                        "Singular tower sequence matrix; mutual equivalent was skipped.",
                        device=str(elmtow.loc_name),
                        device_class="ElmTow",
                    )
                else:
                    node_count: int = 2 * circuit_count
                    positive_target: np.ndarray = np.zeros(
                        (node_count, node_count),
                        dtype=complex,
                    )
                    zero_target: np.ndarray = np.zeros(
                        (node_count, node_count),
                        dtype=complex,
                    )
                    positive_target[:circuit_count, :circuit_count] = positive_series
                    positive_target[circuit_count:, circuit_count:] = positive_series
                    positive_target[:circuit_count, circuit_count:] = -positive_series
                    positive_target[circuit_count:, :circuit_count] = -positive_series
                    zero_target[:circuit_count, :circuit_count] = zero_series
                    zero_target[circuit_count:, circuit_count:] = zero_series
                    zero_target[:circuit_count, circuit_count:] = -zero_series
                    zero_target[circuit_count:, :circuit_count] = -zero_series

                    oriented_buses: List[dev.Bus] = list()
                    for circuit_position in range(circuit_count):
                        source_circuit_index: int = active_indices[circuit_position]
                        polarity: float = 0.0
                        if source_circuit_index < len(elmtow.dpolar):
                            polarity = float(elmtow.dpolar[source_circuit_index])
                        else:
                            pass
                        if abs(polarity) > 0.5:
                            oriented_buses.append(active_lines[circuit_position].bus_to)
                        else:
                            oriented_buses.append(active_lines[circuit_position].bus_from)
                    else:
                        pass
                    for circuit_position in range(circuit_count):
                        source_circuit_index = active_indices[circuit_position]
                        polarity = 0.0
                        if source_circuit_index < len(elmtow.dpolar):
                            polarity = float(elmtow.dpolar[source_circuit_index])
                        else:
                            pass
                        if abs(polarity) > 0.5:
                            oriented_buses.append(active_lines[circuit_position].bus_from)
                        else:
                            oriented_buses.append(active_lines[circuit_position].bus_to)
                    else:
                        pass

                    # Remove the original independent line primitives from the
                    # target so that only the mutual correction is synthesized.
                    for circuit_position in range(circuit_count):
                        original_positive_admittance: complex = (
                            original_positive_admittances[circuit_position]
                        )
                        original_zero_admittance: complex = (
                            original_zero_admittances[circuit_position]
                        )
                        from_node: int = circuit_position
                        to_node: int = circuit_count + circuit_position
                        positive_target[from_node, from_node] -= original_positive_admittance
                        positive_target[to_node, to_node] -= original_positive_admittance
                        positive_target[from_node, to_node] += original_positive_admittance
                        positive_target[to_node, from_node] += original_positive_admittance
                        zero_target[from_node, from_node] -= original_zero_admittance
                        zero_target[to_node, to_node] -= original_zero_admittance
                        zero_target[from_node, to_node] += original_zero_admittance
                        zero_target[to_node, from_node] += original_zero_admittance
                    else:
                        pass

                    # Store both directional and symmetric tower coupling as
                    # one internal nodal matrix. The physical circuits remain
                    # the only visible Line objects with geometry/templates.
                    side_index: int
                    for side_index in range(2):
                        side_offset: int = side_index * circuit_count
                        positive_delta_shunt: np.ndarray = (
                            0.5 * positive_shunt.copy()
                        )
                        zero_delta_shunt: np.ndarray = 0.5 * zero_shunt.copy()
                        for circuit_position in range(circuit_count):
                            positive_delta_shunt[circuit_position, circuit_position] -= (
                                0.5 * original_positive_shunts[circuit_position]
                            )
                            zero_delta_shunt[circuit_position, circuit_position] -= (
                                0.5 * original_zero_shunts[circuit_position]
                            )
                        else:
                            pass
                        positive_target[
                            side_offset:side_offset + circuit_count,
                            side_offset:side_offset + circuit_count,
                        ] += positive_delta_shunt
                        zero_target[
                            side_offset:side_offset + circuit_count,
                            side_offset:side_offset + circuit_count,
                        ] += zero_delta_shunt
                    else:
                        pass

                    tower_identifier: str = str(_ref_id(elmtow.ID))
                    if matrix_is_directional:
                        negative_target: np.ndarray = positive_target.transpose()
                    else:
                        negative_target = positive_target.copy()
                    nodal_stamp: dev.NodalAdmittanceStamp = dev.NodalAdmittanceStamp(
                        name=f"{elmtow.loc_name} coupled-line matrix",
                        idtag=f"ElmTow:{tower_identifier}:nodal",
                        buses=oriented_buses,
                        positive_matrix=positive_target,
                        negative_matrix=negative_target,
                        zero_matrix=zero_target,
                        common_voltage_kv=voltage_base,
                        active=True,
                    )
                    grid.add_nodal_admittance_stamp(obj=nodal_stamp)
                    return
            else:
                logger.add_warning(
                    "Incomplete tower sequence matrices; mutual equivalent was skipped.",
                    device=str(elmtow.loc_name),
                    device_class="ElmTow",
                )
        else:
            logger.add_warning(
                "Coupled tower circuits require positive lengths and a tower voltage base.",
                device=str(elmtow.loc_name),
                device_class="ElmTow",
            )
    else:
        pass


def _apply_individual_elmtow_geometries(
        dgs_grid: DgsCircuit,
        elmtow: ElmTow,
        line_by_dgs_id: Dict[str, List[dev.Line]],
        baseMVA: float,
        logger: Logger,
) -> None:
    """
    Apply one independent tower definition to each coupled-line entry.

    This DGS representation is distinct from one shared multi-circuit tower:
    ``pGeo`` and ``plines`` have the same size and every geometry describes its
    corresponding physical line. No mutual matrix may be invented between
    those independent definitions.

    :param dgs_grid: Parsed source circuit containing tower definitions.
    :param elmtow: Source coupling with one geometry per line.
    :param line_by_dgs_id: Imported physical lines indexed by DGS identity.
    :param baseMVA: Circuit power base in MVA.
    :param logger: Import diagnostics.
    :return: None.
    """
    tower_type_by_id: Dict[str, TypTow] = dict()
    source_tower_type: TypTow
    for source_tower_type in dgs_grid.typtows:
        source_type_id: str | None = _ref_id(source_tower_type.ID)
        if source_type_id is not None:
            tower_type_by_id[source_type_id] = source_tower_type
            tower_type_by_id[str(source_tower_type.ID)] = source_tower_type
        else:
            pass
    else:
        pass

    circuit_index: int
    for circuit_index in range(len(elmtow.plines)):
        line_pointer: str | None = elmtow.plines[circuit_index]
        geometry_pointer: str | None = _get_elmtow_geometry_pointer(
            elmtow=elmtow,
            circuit_index=circuit_index,
        )
        if line_pointer is not None and geometry_pointer is not None:
            line_identifier: str | None = _ref_id(line_pointer)
            geometry_identifier: str | None = _ref_id(geometry_pointer)
            imported_lines: List[dev.Line] = line_by_dgs_id.get(
                str(line_identifier),
                list(),
            )
            if len(imported_lines) == 0:
                imported_lines = line_by_dgs_id.get(str(line_pointer), list())
            else:
                pass
            tower_type: TypTow | None = tower_type_by_id.get(
                str(geometry_identifier),
                None,
            )
            if tower_type is None:
                tower_type = tower_type_by_id.get(str(geometry_pointer), None)
            else:
                pass
            if len(imported_lines) == 1 and tower_type is not None:
                _apply_tower_self_conductance(
                    active_lines=list((imported_lines[0],)),
                    active_indices=list((0,)),
                    typtow=tower_type,
                    baseMVA=baseMVA,
                )
            else:
                logger.add_warning(
                    "Independent tower geometry requires one imported line and one TypTow.",
                    device=str(elmtow.loc_name),
                    device_class="ElmTow",
                    value=str(line_pointer),
                )
        else:
            pass
    else:
        pass


def _apply_elmtow_tower_coupling(dgs_grid: DgsCircuit,
                                 line_by_dgs_id: Dict[str, List[dev.Line]],
                                 overhead_line_type_dict: Dict[str, dev.OverheadLineType],
                                 baseMVA: float,
                                 frequency: float,
                                 logger: Logger,
                                 grid: dev.MultiCircuit | None = None) -> None:
    """
    Apply elmtow tower coupling.

    :param dgs_grid: dgs_grid parameter.
    :param line_by_dgs_id: line_by_dgs_id parameter.
    :param overhead_line_type_dict: overhead_line_type_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param frequency: frequency parameter.
    :param logger: logger parameter.
    :param grid: Optional destination circuit receiving mutual equivalents.
    :return: Function result.
    """
    # Keep a deterministic source lookup so the tower pass can distinguish
    # legacy geometry-only lines from lines that already received PF's exact
    # complete-element electrical reduction during their normal conversion.
    source_line_by_id: Dict[str, ElmLne] = dict()
    source_line: ElmLne
    for source_line in dgs_grid.elmlnes:
        source_identifier: str | None = _ref_id(source_line.ID)
        if source_identifier is not None and source_identifier != "":
            source_line_by_id[source_identifier] = source_line
            source_line_by_id[str(source_line.ID)] = source_line
        else:
            pass
    else:
        pass

    for elmtow in dgs_grid.elmtows:
        if int(elmtow.outserv) != 0:
            continue
        uses_individual_geometries: bool = bool(
            len(elmtow.pGeo) > 1
            and len(elmtow.pGeo) == len(elmtow.plines)
        )
        if uses_individual_geometries:
            _apply_individual_elmtow_geometries(
                dgs_grid=dgs_grid,
                elmtow=elmtow,
                line_by_dgs_id=line_by_dgs_id,
                baseMVA=baseMVA,
                logger=logger,
            )
        else:
            pass
        if len(elmtow.pGeo) == 0:
            logger.add_warning(
                f"no pGeo specified, skipping tower binding",
                device=f"{elmtow.loc_name}' (ID={elmtow.ID}) ",
                device_class="ElmTow"
            )
            continue

        if uses_individual_geometries:
            geo_ptr: str | None = None
        else:
            geo_ptr = elmtow.pGeo[0]
        if geo_ptr is None:
            if uses_individual_geometries:
                pass
            else:
                logger.add_warning(
                    f"pGeo[0] is empty, skipping tower binding",
                    device=f"{elmtow.loc_name}' (ID={elmtow.ID}) ",
                    device_class="ElmTow"
                )
            continue

        geo_id = _ref_id(geo_ptr)
        tower_type: TypTow | None = None
        candidate_type: TypTow
        for candidate_type in dgs_grid.typtows:
            if _ref_id(candidate_type.ID) == geo_id:
                tower_type = candidate_type
            else:
                pass
        else:
            pass
        ohl_type = overhead_line_type_dict.get(geo_id)
        if ohl_type is None:
            ohl_type = overhead_line_type_dict.get(geo_ptr)
        else:
            pass
        electrical_matrix_type_is_available: bool = bool(
            tower_type is not None and int(tower_type.i_mode) == 1
        )
        if ohl_type is None and not electrical_matrix_type_is_available:
            logger.add_warning(
                f"referenced tower type not found",
                device=f"{elmtow.loc_name}' (ID={elmtow.ID}) ",
                device_class="ElmTow",
                value=str(geo_ptr)
            )
        elif ohl_type is not None:
            for idx, line_ptr in enumerate(elmtow.plines):
                if line_ptr is not None:
                    line_id = _ref_id(line_ptr)
                    api_lines = line_by_dgs_id.get(line_id, list())
                    if len(api_lines) == 0:
                        api_lines = line_by_dgs_id.get(line_ptr, list())
                    else:
                        pass
                    if len(api_lines) == 0:
                        logger.add_warning(
                            f"referenced line type not found",
                            device=f"{elmtow.loc_name}' (ID={elmtow.ID}) ",
                            device_class="ElmTow",
                            value=str(line_ptr)
                        )
                    else:
                        circuit_idx = int(idx) + 1
                        for api_line in api_lines:
                            try:
                                api_line.set_circuit_idx(val=circuit_idx, obj=ohl_type)
                                matched_source_line: ElmLne | None = (
                                    source_line_by_id.get(str(line_id), None)
                                )
                                effective_parameters_are_available: bool = bool(
                                    matched_source_line is not None
                                    and len(elmtow.plines) == 1
                                    and _has_usable_effective_line_parameters(
                                        source=matched_source_line,
                                    )
                                )
                                if effective_parameters_are_available:
                                    # Preserve the physical catalogue identity
                                    # without replacing the exported complete-
                                    # element electrical equivalent.
                                    api_line.template = ohl_type
                                    api_line.rms_template = ohl_type.rms_template
                                    api_line.emt_template = ohl_type.emt_template
                                else:
                                    api_line.apply_template(
                                        obj=ohl_type,
                                        Sbase=baseMVA,
                                        freq=frequency,
                                        logger=logger,
                                    )
                            except ValueError as e:
                                logger.add_warning(
                                    str(e).strip() or "Failed to apply tower template.",
                                    device_class="ElmLne",
                                    device=api_line.name
                                )
                else:
                    pass
            else:
                pass
        else:
            # Electrical-mode matrix types have already supplied each visible
            # line's diagonal through the normal line conversion.  The matrix
            # correction below adds only the directional mutual contract.
            pass

        tower_voltage_kv: float = 0.0
        if ohl_type is not None:
            tower_voltage_kv = float(ohl_type.Vnom)
        else:
            # Electrical-mode TypTow definitions are imported as sequence
            # templates rather than geometrical OverheadLineType objects.
            # Recover their rated voltage from any associated visible line.
            line_pointer: str | None
            for line_pointer in elmtow.plines:
                if tower_voltage_kv > 0.0 or line_pointer is None:
                    pass
                else:
                    line_identifier: str | None = _ref_id(line_pointer)
                    candidate_lines: List[dev.Line] = line_by_dgs_id.get(
                        str(line_identifier),
                        list(),
                    )
                    candidate_line: dev.Line
                    for candidate_line in candidate_lines:
                        line_template: dev.SequenceLineType | dev.OverheadLineType | None = (
                            candidate_line.template
                        )
                        if isinstance(line_template, dev.SequenceLineType):
                            tower_voltage_kv = float(line_template.Vnom)
                        else:
                            if isinstance(line_template, dev.OverheadLineType):
                                tower_voltage_kv = float(line_template.Vnom)
                            else:
                                pass
                    else:
                        pass
            else:
                pass

        if grid is not None and tower_type is not None:
            _apply_elmtow_matrix_equivalent(
                grid=grid,
                elmtow=elmtow,
                typtow=tower_type,
                line_by_dgs_id=line_by_dgs_id,
                tower_voltage_kv=tower_voltage_kv,
                baseMVA=baseMVA,
                logger=logger,
            )
        else:
            if grid is not None and tower_type is None:
                logger.add_warning(
                    "Referenced TypTow matrix was not found; mutual equivalent was skipped.",
                    device=str(elmtow.loc_name),
                    device_class="ElmTow",
                    value=str(geo_ptr),
                )
            else:
                pass


def dgs_to_circuit_with_report(
        path: str,
        use_vsc_for_injections: bool = False,
        use_dynamic_information: bool = False,
        use_power_flow_snapshot: bool = False,
        use_power_flow_tap_guess: bool = False,
        logger_: Logger | None = None,
        text_func: Callable[[str], None] | None = None,
        progress_func: Callable[[float], None] | None = None,
        dynamic_template_catalog_root_folder: str | None = None,
        persist_dynamic_templates_to_user_catalog: bool = False,
) -> DgsCircuitImportResult:
    """
    Convert one DGS into a circuit plus a structured dynamic-import report.

    :param path: path parameter.
    :param use_vsc_for_injections: use_vsc_for_injections parameter.
    :param use_dynamic_information: use_dynamic_information parameter.
    :param use_power_flow_snapshot: Reproduce solved P/Q result columns when available.
    :param use_power_flow_tap_guess: Seed exported taps without freezing controls.
    :param logger_: logger_ parameter.
    :param text_func: Optional user-facing progress-text callback.
    :param progress_func: Optional numeric progress callback in ``[0, 100]``.
    :param dynamic_template_catalog_root_folder: Optional user-template root override, mainly for tests.
    :param persist_dynamic_templates_to_user_catalog: Persist imported dynamic templates as readable Python modules.
    :return: Circuit and optional massive dynamic-import report.
    """
    logger: Logger = Logger() if logger_ is None else logger_
    progress_reporter: _DgsImportProgressReporter = _DgsImportProgressReporter(
        text_func=text_func,
        progress_func=progress_func,
    )
    dynamic_report: DynamicModelImportReport | None = None

    if use_power_flow_snapshot:
        progress_reporter.emit(0, "Reading PowerFactory DGS snapshot (calculated P/Q and taps)...")
        logger.add_info(msg="DGS power-flow snapshot replay requested")
    else:
        progress_reporter.emit(0, "Reading PowerFactory DGS network...")

    dgs_grid: DgsCircuit = DgsCircuit()
    dgs_grid.parse_dgs(path)
    progress_reporter.emit(10, "Building VeraGrid network from DGS...")

    grid: dev.MultiCircuit = dev.MultiCircuit()

    baseMVA: float = grid.Sbase

    # --- frequency ---
    frequency: float
    if len(dgs_grid.elmnets) > 0:
        frnom = dgs_grid.elmnets[0].frnom
        if frnom is None:
            frequency = 50.0
        else:
            frequency = float(frnom)
    else:
        frequency = 50.0
    grid.fBase = frequency

    # StaCubic dictionaries
    stacubic_dict, cubics_by_objid = _build_stacubic_mappings(stacubics=dgs_grid.stacubics)
    _add_graphically_inferred_line_cubicles(
        dgs_grid=dgs_grid,
        stacubic_dict=stacubic_dict,
        cubics_by_objid=cubics_by_objid,
        logger=logger,
    )

    pos_by_objid: Dict[str, Tuple[float, float]] = _build_graphics_positions(intgrfs=dgs_grid.intgrfs)
    area_by_id: Dict[str, dev.Area] = _add_elmarea_areas(dgs_grid=dgs_grid, grid=grid)
    zone_by_id: Dict[str, dev.Zone] = _add_elmzone_zones(dgs_grid=dgs_grid, grid=grid)
    branch_group_by_id: Dict[str, dev.BranchGroup] = _add_elmbranch_groups(dgs_grid=dgs_grid, grid=grid)
    bus_by_term_id: Dict[str, dev.Bus] = _add_elmterm_buses(
        dgs_grid=dgs_grid,
        grid=grid,
        pos_by_objid=pos_by_objid,
        use_power_flow_snapshot=use_power_flow_snapshot,
    )
    _assign_elmterm_area_references(dgs_grid=dgs_grid, bus_by_term_id=bus_by_term_id, area_by_id=area_by_id)
    _assign_elmterm_zone_references(dgs_grid=dgs_grid, bus_by_term_id=bus_by_term_id, zone_by_id=zone_by_id)
    station_controller_by_device_id: Dict[str, dev.StationController] = _add_elmstactrl_controllers(
        dgs_grid=dgs_grid,
        grid=grid,
        bus_by_term_id=bus_by_term_id,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
    )
    typsym_dict: Dict[str, TypSym] = _build_typsym_dict(dgs_grid=dgs_grid)
    typasmo_dict: Dict[str, TypAsmo] = _build_typasmo_dict(dgs_grid=dgs_grid)
    typ_switch_dict: Dict[str, TypSwitch] = _build_typswitch_dict(dgs_grid=dgs_grid)

    # switches (PowerFactory/DGS: ElmCoup is the real device; StaCubic resolves connectivity)
    switch_by_cubic_id: Dict[str, StaSwitch] = build_switch_by_cubic_id(staswitchs=dgs_grid.staswitchs)

    _add_elmcoup_switches(
        dgs_grid=dgs_grid,
        grid=grid,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        typ_switch_dict=typ_switch_dict,
        baseMVA=baseMVA,
        logger=logger,
    )

    _add_elmsym_generators(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        typsym_dict=typsym_dict,
        baseMVA=baseMVA,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        use_power_flow_snapshot=use_power_flow_snapshot,
        station_controller_by_device_id=station_controller_by_device_id,
    )
    _add_elmasm_generators(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        typasmo_dict=typasmo_dict,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
    )
    _add_elmvac_loads(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
    )
    _add_elmlod_loads(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        use_power_flow_snapshot=use_power_flow_snapshot,
    )
    _add_elmgenstat_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        use_vsc_for_injections=use_vsc_for_injections,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        station_controller_by_device_id=station_controller_by_device_id,
        use_power_flow_snapshot=use_power_flow_snapshot,
    )
    _add_elmvsc_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        frequency_hz=frequency,
        use_power_flow_snapshot=use_power_flow_snapshot,
    )
    _add_elmvscmono_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        frequency_hz=frequency,
        use_power_flow_snapshot=use_power_flow_snapshot,
    )
    _add_elmxnet_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
    )
    _promote_unambiguous_pv_external_grid_references(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        logger=logger,
    )
    _add_elmshnt_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        frequency=frequency,
        switch_by_cubic_id=switch_by_cubic_id,
    )
    _add_elmsvs_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        use_vsc_for_injections=use_vsc_for_injections,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        use_power_flow_snapshot=use_power_flow_snapshot,
        preserve_dynamic_host=use_dynamic_information,
    )

    if use_power_flow_snapshot:
        _deactivate_station_controllers_for_snapshot(grid=grid)
    else:
        pass

    # Loads (LV)
    if len(dgs_grid.elmlodlvs) > 0 or len(dgs_grid.elmlodlvps) > 0:
        logger.add_warning(
            f"ElmLodlv/ElmLodlvp found but no P/Q fields available in DGS schema",
            device_class="ElmLodlv/ElmLodlvp",
        )

    typlne_dict: Dict[str, dev.SequenceLineType] = _build_typlne_templates(dgs_grid=dgs_grid, grid=grid)
    typcon_raw_dict, wire_type_dict = _build_typcon_catalogues(dgs_grid=dgs_grid, grid=grid)
    overhead_line_type_dict: Dict[str, dev.OverheadLineType] = _add_typtow_templates(
        dgs_grid=dgs_grid,
        grid=grid,
        typcon_raw_dict=typcon_raw_dict,
        wire_type_dict=wire_type_dict,
        typlne_dict=typlne_dict,
        frequency=frequency,
        logger=logger,
    )
    typtr2_dict, typtr2_raw_dict = _build_typtr2_templates(dgs_grid=dgs_grid, grid=grid)
    typtr3_dict: Dict[str, TypTr3] = _build_typtr3_dict(dgs_grid=dgs_grid)
    typtr4_dict: Dict[str, TypTr4] = _build_typtr4_dict(dgs_grid=dgs_grid)
    typsind_raw_dict: Dict[str, TypSind] = _build_typsind_dict(dgs_grid=dgs_grid)

    # ------------------------------------------------------------
    # Fallback map: ElmLne.ID -> typ_id from ElmLnesec
    # Some PowerFactory exports omit ElmLne.typ_id and store it in ElmLnesec.typ_id.
    # In some cases, ElmLnesec.fold_id references an IntFolder chain; we climb until we reach an ElmLne.
    # ------------------------------------------------------------
    line_type_by_line_id, line_sections_by_line_id = _build_line_section_type_maps(
        dgs_grid=dgs_grid,
        logger=logger,
    )

    # ------------------------------------------------------------
    # Tower coupling helper: ElmTow may define the line template (TypTow) instead of ElmLne.typ_id.
    # We build a direct mapping Line.ID -> OverheadLineType so convert_dgs_to_line can proceed
    # even when typ_id is missing, and apply the proper template immediately.
    # ------------------------------------------------------------
    tower_template_by_line_id: Dict[
        str,
        dev.OverheadLineType | dev.SequenceLineType,
    ] = _build_tower_template_by_line_id(
        dgs_grid=dgs_grid,
        overhead_line_type_dict=overhead_line_type_dict,
        sequence_line_type_dict=typlne_dict,
    )

    line_by_dgs_id: Dict[str, List[dev.Line]] = _add_elmlne_lines(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        typlne_dict=typlne_dict,
        overhead_line_type_dict=overhead_line_type_dict,
        line_type_by_line_id=line_type_by_line_id,
        line_sections_by_line_id=line_sections_by_line_id,
        tower_template_by_line_id=tower_template_by_line_id,
        frequency=frequency,
        baseMVA=baseMVA,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        branch_group_by_id=branch_group_by_id,
    )
    _apply_elmtow_tower_coupling(
        dgs_grid=dgs_grid,
        line_by_dgs_id=line_by_dgs_id,
        overhead_line_type_dict=overhead_line_type_dict,
        baseMVA=baseMVA,
        frequency=frequency,
        logger=logger,
        grid=grid,
    )

    _add_elmzpu_series_reactances(
        dgs_grid=dgs_grid,
        grid=grid,
        bus_by_term_id=bus_by_term_id,
        stacubic_dict=stacubic_dict,
        cubics_by_objid=cubics_by_objid,
        logger=logger,
        baseMVA=baseMVA,
        switch_by_cubic_id=switch_by_cubic_id,
        branch_group_by_id=branch_group_by_id,
    )
    _add_elmscap_series_reactances(
        dgs_grid=dgs_grid,
        grid=grid,
        bus_by_term_id=bus_by_term_id,
        stacubic_dict=stacubic_dict,
        cubics_by_objid=cubics_by_objid,
        logger=logger,
        baseMVA=baseMVA,
        switch_by_cubic_id=switch_by_cubic_id,
        branch_group_by_id=branch_group_by_id,
    )
    _add_elmsind_series_reactances(
        dgs_grid=dgs_grid,
        grid=grid,
        bus_by_term_id=bus_by_term_id,
        stacubic_dict=stacubic_dict,
        cubics_by_objid=cubics_by_objid,
        typsind_raw_dict=typsind_raw_dict,
        logger=logger,
        baseMVA=baseMVA,
        switch_by_cubic_id=switch_by_cubic_id,
        branch_group_by_id=branch_group_by_id,
    )
    _add_elmtr2_transformers(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        typtr2_dict=typtr2_dict,
        typtr2_raw_dict=typtr2_raw_dict,
        frequency=frequency,
        baseMVA=baseMVA,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        branch_group_by_id=branch_group_by_id,
        use_power_flow_snapshot=use_power_flow_snapshot,
        use_power_flow_tap_guess=use_power_flow_tap_guess,
    )
    _add_elmtr3_transformers(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        typtr3_dict=typtr3_dict,
        baseMVA=baseMVA,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        branch_group_by_id=branch_group_by_id,
        use_power_flow_snapshot=use_power_flow_snapshot,
        use_power_flow_tap_guess=use_power_flow_tap_guess,
    )

    _add_elmtr4_transformers(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=stacubic_dict,
        typtr4_dict=typtr4_dict,
        baseMVA=baseMVA,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        branch_group_by_id=branch_group_by_id,
        use_power_flow_snapshot=use_power_flow_snapshot,
        use_power_flow_tap_guess=use_power_flow_tap_guess,
    )

    # Build the electrical-to-graphical lookup only after all import helpers
    # finish, so schematic reconstruction sees the definitive runtime objects.
    diagram_api_objects_by_dgs_id: Dict[str, List[ALL_DEV_TYPES]] = (
        _build_diagram_api_objects_by_dgs_id(grid=grid)
    )
    import_dgs_substations_and_schematic_diagrams(dgs_grid=dgs_grid,
                                                  grid=grid,
                                                  bus_by_term_id=bus_by_term_id,
                                                  zone_by_id=zone_by_id,
                                                  api_objects_by_dgs_id=diagram_api_objects_by_dgs_id,
                                                  logger=logger)

    # A missing calculated station node is an electrical state, not permission
    # to invent one from proximity.  Machines retained by cconn then keep their
    # aligned cvgen targets as local controls, while cconn-zero equipment stays
    # inactive.  This fail-closed rule matches the PowerFactory runtime oracle.

    # Physical P-Q controls remain part of the static network contract even
    # when catalogue installation is disabled. Resolve their exact composite
    # measurement point before either a plain load flow or RMS preparation.
    composite_measurement_vsc_control_count: int = (
        _apply_composite_pq_measurement_vsc_controls(
            dgs_circuit=dgs_grid,
            circuit=grid,
            use_power_flow_snapshot=use_power_flow_snapshot,
            logger=logger,
        )
    )
    if composite_measurement_vsc_control_count > 0:
        logger.add_info(
            msg="DGS VSC P-Q controls assigned to composite measurement branches",
            value=composite_measurement_vsc_control_count,
        )
    else:
        pass

    composite_measurement_svs_control_count: int = (
        _apply_composite_q_measurement_svs_controls(
            dgs_circuit=dgs_grid,
            circuit=grid,
            use_power_flow_snapshot=use_power_flow_snapshot,
            logger=logger,
        )
    )
    if composite_measurement_svs_control_count > 0:
        logger.add_info(
            msg="DGS SVC Q/V controls assigned to composite measurement branches",
            value=composite_measurement_svs_control_count,
        )
    else:
        pass

    if use_power_flow_snapshot:
        progress_reporter.emit(55, "Static DGS snapshot ready: calculated P/Q and taps replayed")
    else:
        progress_reporter.emit(55, "Static DGS network ready")

    if use_dynamic_information:
        try:
            dynamic_bundle: DynamicModelImportBundle
            dynamic_logger: Logger
            dynamic_bundle, dynamic_logger = build_dgs_dynamic_model_import_bundle(
                dgs_path=path,
                progress_callback=progress_reporter.emit_catalog_progress,
                dgs_circuit=dgs_grid,
            )
            if dynamic_logger.has_logs():
                logger += dynamic_logger
            else:
                pass

            dynamic_report = add_all_dynamic_import_bundle_to_circuit_with_report(
                circuit=grid,
                bundle=dynamic_bundle,
                logger=logger,
                progress_callback=progress_reporter.emit_install_progress,
                user_root_folder=dynamic_template_catalog_root_folder,
                persist_to_user_catalog=persist_dynamic_templates_to_user_catalog,
                consume_bundle_templates=True,
            )
            # PowerFactory selects the physical converter's load-flow equations
            # from exact Mode_P/Mode_Q parameters in the associated composite.
            # Apply that DGS-only contract before building RMS measurements so
            # the temporal model starts from the same operating point.
            dynamic_projected_vsc_control_count: int = (
                _apply_dynamic_vsc_steady_state_controls(
                    dgs_circuit=dgs_grid,
                    circuit=grid,
                    use_power_flow_snapshot=use_power_flow_snapshot,
                    logger=logger,
                )
            )
            projected_vsc_control_count: int = (
                composite_measurement_vsc_control_count
                + dynamic_projected_vsc_control_count
            )
            external_grid_source_ids: Set[str] = set()
            source_external_grid: ElmXnet
            source_external_grid_id: str | None
            for source_external_grid in dgs_grid.elmxnets:
                source_external_grid_id = _ref_id(source_external_grid.ID)
                if source_external_grid_id is None or source_external_grid_id == "":
                    pass
                else:
                    external_grid_source_ids.add(source_external_grid_id)

            elmgenstat_source_ids: Set[str] = set()
            elmgenstat_rms_model_by_source_id: Dict[
                str,
                DgsElmGenstatRmsModel,
            ] = dict()
            source_static_generator: ElmGenstat
            source_static_generator_id: str | None
            for source_static_generator in dgs_grid.elmgenstats:
                source_static_generator_id = _ref_id(source_static_generator.ID)
                if (
                        source_static_generator_id is None
                        or source_static_generator_id == ""
                ):
                    pass
                else:
                    elmgenstat_source_ids.add(source_static_generator_id)
                    elmgenstat_rms_model_by_source_id[
                        source_static_generator_id
                    ] = _resolve_elmgenstat_rms_model(
                        source=source_static_generator,
                        logger=logger,
                    )
            else:
                pass

            elmsym_source_ids: Set[str] = set()
            elmsym_reference_source_ids: Set[str] = set()
            source_synchronous_machine: ElmSym
            source_synchronous_machine_id: str | None
            for source_synchronous_machine in dgs_grid.elmsyms:
                source_synchronous_machine_id = _ref_id(
                    source_synchronous_machine.ID
                )
                if (
                        source_synchronous_machine_id is None
                        or source_synchronous_machine_id == ""
                ):
                    pass
                else:
                    elmsym_source_ids.add(source_synchronous_machine_id)
                    is_active_reference_machine: bool = (
                        int(source_synchronous_machine.outserv) == 0
                        and int(source_synchronous_machine.ip_ctrl) == 1
                    )
                    if is_active_reference_machine:
                        elmsym_reference_source_ids.add(
                            source_synchronous_machine_id
                        )
                    else:
                        pass
            else:
                pass

            typeless_elmlod_source_ids: Set[str] = set()
            source_load: ElmLod
            source_load_id: str | None
            for source_load in dgs_grid.elmlods:
                source_load_id = _ref_id(source_load.ID)
                source_load_has_no_type: bool = bool(
                    _ref_id(source_load.typ_id) in (None, "")
                )
                if (
                        source_load_id is None
                        or source_load_id == ""
                        or not source_load_has_no_type
                ):
                    pass
                else:
                    typeless_elmlod_source_ids.add(source_load_id)
            else:
                pass

            # Exact imported controllers are activated first. The remaining
            # empty physical slots then receive VeraGrid's standard electrical
            # shells, which makes a normal DGS open ready for RMS compilation
            # without replacing any source dynamic model.
            rms_preparation_report: DgsRmsPreparationReport = prepare_dgs_circuit_for_rms(
                circuit=grid,
                external_grid_source_ids=external_grid_source_ids,
                logger=logger,
                elmgenstat_source_ids=elmgenstat_source_ids,
                elmgenstat_rms_model_by_source_id=(
                    elmgenstat_rms_model_by_source_id
                ),
                elmsym_source_ids=elmsym_source_ids,
                elmsym_reference_source_ids=elmsym_reference_source_ids,
                typeless_elmlod_source_ids=typeless_elmlod_source_ids,
            )
            physical_astable_selector_count: int = (
                _apply_dgs_physical_astable_integration_selectors(
                    dgs_circuit=dgs_grid,
                    circuit=grid,
                    logger=logger,
                )
            )
            # A solved DGS explicitly identifies which retained synchronous
            # machines PowerFactory admitted to its initialized RMS system.
            # Apply that device-local contract only after every imported or
            # standard fallback shell has been materialized.
            excluded_rms_machine_count: int = (
                _mark_dgs_rms_participation_from_calculated_results(
                    dgs_circuit=dgs_grid,
                    circuit=grid,
                    logger=logger,
                )
            )
            synchronized_logical_service_count: int = (
                synchronize_dgs_logical_actuator_service_states(
                    circuit=grid,
                    dgs_circuit=dgs_grid,
                    logger=logger,
                )
            )
            # Reconstruct zero-impedance valve placement from the frame roles,
            # then reconnect each prepared standard shell to its resolved rail.
            prepared_logical_actuator_count: int = (
                prepare_dgs_logical_actuator_topology(
                    circuit=grid,
                    dgs_circuit=dgs_grid,
                    logger=logger,
                )
            )
            bound_logical_actuator_count: int = bind_dgs_logical_actuator_runtime(
                circuit=grid,
                logger=logger,
            )
            # Native measurement slots are signal-producing dynamic objects,
            # not physical devices. Bind them only after the exact electrical
            # buses and device RMS shells exist.
            rms_measurement_report: DgsRmsMeasurementBindingReport = (
                bind_dgs_rms_measurements(
                    circuit=grid,
                    dgs_circuit=dgs_grid,
                    logger=logger,
                )
            )
            dynamic_template_count: int = dynamic_report.get_added_count()
            dynamic_association_count: int = grid.get_dgs_dynamic_association_number()
            activated_dynamic_device_count: int = dynamic_report.get_activated_device_model_count()
            prepared_rms_shell_count: int = (
                rms_preparation_report.get_prepared_bus_count()
                + rms_preparation_report.get_prepared_device_count()
            )
            completion_prefix: str
            if use_power_flow_snapshot:
                completion_prefix = "DGS snapshot replay complete: calculated P/Q and taps retained; "
            else:
                completion_prefix = "DGS import complete: "
            progress_reporter.emit(
                100,
                (
                    f"{completion_prefix}{dynamic_template_count} dynamic templates added; "
                    f"{dynamic_association_count} source associations retained; "
                    f"{activated_dynamic_device_count} unambiguous device models activated; "
                    f"{physical_astable_selector_count} physical A-stable selectors retained; "
                    f"{projected_vsc_control_count} VSC load-flow contracts projected; "
                    f"{rms_measurement_report.get_bound_meter_count()} native RMS meters bound; "
                    f"{excluded_rms_machine_count} non-participating synchronous machines retained outside DAE; "
                    f"{synchronized_logical_service_count} logical service states retained; "
                    f"{bound_logical_actuator_count}/{prepared_logical_actuator_count} logical actuators bound; "
                    f"{prepared_rms_shell_count} standard RMS shells prepared"
                ),
            )
        except Exception as exc:
            # Dynamic information is optional.  A malformed model must not discard
            # the static network that was already converted successfully.
            logger.add_warning(
                msg="DGS dynamic information import skipped",
                value=str(exc),
            )
            if use_power_flow_snapshot:
                progress_reporter.emit(
                    100,
                    "DGS snapshot replay complete; dynamic catalogue reported errors",
                )
            else:
                progress_reporter.emit(100, "DGS network loaded; dynamic catalogue reported errors")
    else:
        if use_power_flow_snapshot:
            progress_reporter.emit(100, "DGS snapshot replay complete: calculated P/Q and taps retained")
        else:
            progress_reporter.emit(100, "DGS network import complete")

    result: DgsCircuitImportResult = DgsCircuitImportResult(
        circuit=grid,
        dynamic_report=dynamic_report,
    )
    return result


def dgs_to_circuit(
        path: str,
        use_vsc_for_injections: bool = False,
        use_dynamic_information: bool = False,
        use_power_flow_snapshot: bool = False,
        use_power_flow_tap_guess: bool = False,
        logger_: Logger | None = None,
        text_func: Callable[[str], None] | None = None,
        progress_func: Callable[[float], None] | None = None,
        dynamic_template_catalog_root_folder: str | None = None,
        persist_dynamic_templates_to_user_catalog: bool = False,
) -> dev.MultiCircuit:
    """
    Convert one DGS and return the backward-compatible circuit result.

    :param path: Source DGS path.
    :param use_vsc_for_injections: Convert compatible injections to VSC devices.
    :param use_dynamic_information: Import all supported dynamic model entries.
    :param use_power_flow_snapshot: Reproduce solved P/Q result columns when available.
    :param use_power_flow_tap_guess: Seed exported taps without freezing controls.
    :param logger_: Optional caller-owned logger.
    :param text_func: Optional user-facing progress-text callback.
    :param progress_func: Optional numeric progress callback in ``[0, 100]``.
    :param dynamic_template_catalog_root_folder: Optional user-template root override.
    :param persist_dynamic_templates_to_user_catalog: Persist imported dynamic templates as readable Python modules.
    :return: Imported VeraGrid circuit.
    """
    result: DgsCircuitImportResult = dgs_to_circuit_with_report(
        path=path,
        use_vsc_for_injections=use_vsc_for_injections,
        use_dynamic_information=use_dynamic_information,
        use_power_flow_snapshot=use_power_flow_snapshot,
        use_power_flow_tap_guess=use_power_flow_tap_guess,
        logger_=logger_,
        text_func=text_func,
        progress_func=progress_func,
        dynamic_template_catalog_root_folder=dynamic_template_catalog_root_folder,
        persist_dynamic_templates_to_user_catalog=persist_dynamic_templates_to_user_catalog,
    )
    return result.get_circuit()

# D12 devel_dynamics compatibility surface preserved during integration.
def _interpret_pu_limit(value: float,
                        baseMVA: float,
                        reference_abs: float,
                        logger: Logger,
                        name: str,
                        field: str) -> float:
    """
    Interpret pu limit.

    :param value: value parameter.
    :param baseMVA: baseMVA parameter.
    :param reference_abs: reference_abs parameter.
    :param logger: logger parameter.
    :param name: name parameter.
    :param field: field parameter.
    :return: Function result.
    """
    v = value

    # If reference is small too, do not guess
    if abs(reference_abs) <= 5.0:
        return v

    # Heuristic: if |value| is small while reference magnitude is clearly in MW/MVAr,
    # then it is very likely a p.u. value and we scale by baseMVA.
    if abs(v) <= 5.0 and baseMVA > 0.0:
        logger.add_warning(
            f"Interpreting set point as not in p.u.",
            device=name,
            device_class="Generator",
            value=v * baseMVA
        )

        return v * baseMVA

    return v
