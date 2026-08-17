# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import hashlib
import json
import copy

from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple, TYPE_CHECKING
from enum import Enum
from VeraGridEngine.IO.file_system import get_create_veragrid_folder
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice, GCProp
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import duplicate_block
from VeraGridEngine.enumerations import (
    DeviceType,
    PrpCat,
    SubObjectType,
)




class DgsDynamicAssociationTargetDomain(Enum):
    """Define the reusable-template domain of one DGS association."""

    __slots__ = ()

    Rms = "RMS"
    Emt = "EMT"

    def __str__(self) -> str:
        """
        Return the persistent enum value.

        :return: Persistent target-domain value.
        """
        return str(self.value)

    def __repr__(self) -> str:
        """
        Return the persistent enum representation.

        :return: Persistent target-domain representation.
        """
        return str(self)


class DgsDynamicAssociationStatus(Enum):
    """Define the import outcome retained by one DGS association."""

    __slots__ = ()

    Added = "Added"
    Deduplicated = "Deduplicated"
    Renamed = "Renamed"
    Failed = "Failed"
    Skipped = "Skipped"

    def __str__(self) -> str:
        """
        Return the persistent enum value.

        :return: Persistent import-outcome value.
        """
        return str(self.value)

    def __repr__(self) -> str:
        """
        Return the persistent enum representation.

        :return: Persistent import-outcome representation.
        """
        return str(self)


class DgsDynamicAssociationRole(Enum):
    """Define the physical or logical role of one DGS composite relation."""

    __slots__ = ()

    CompositeController = "CompositeController"
    ControllerModel = "ControllerModel"
    PhysicalHost = "PhysicalHost"
    Measurement = "Measurement"
    SwitchActuator = "SwitchActuator"
    ValveActuator = "ValveActuator"
    PassiveActuator = "PassiveActuator"
    Unknown = "Unknown"

    def __str__(self) -> str:
        """
        Return the persistent enum value.

        :return: Persistent association-role value.
        """
        return str(self.value)

    def __repr__(self) -> str:
        """
        Return the persistent enum representation.

        :return: Persistent association-role representation.
        """
        return str(self)


class DgsDynamicAssociationRecord:
    """
    Store one persistent DGS dynamic-model provenance relation.

    One record represents one source catalogue relation, not one physical
    VeraGrid device.  Several records may intentionally reference the same
    final template after structural deduplication.
    """

    __slots__ = (
        "_unique_key",
        "_root_dgs_id",
        "_root_name",
        "_root_typ_id",
        "_slot_dgs_id",
        "_slot_name",
        "_slot_index",
        "_slot_element",
        "_slot_filter",
        "_source_element_dgs_id",
        "_source_element_name",
        "_source_element_class",
        "_final_template_name",
        "_role",
        "_target_domain",
        "_status",
    )

    def __init__(
            self,
            unique_key: str,
            root_dgs_id: str,
            root_name: str,
            root_typ_id: str,
            slot_dgs_id: str | None,
            slot_name: str | None,
            slot_index: int | None,
            slot_element: str | None,
            slot_filter: str | None,
            source_element_dgs_id: str | None,
            source_element_name: str | None,
            source_element_class: str | None,
            final_template_name: str | None,
            target_domain: DgsDynamicAssociationTargetDomain,
            status: DgsDynamicAssociationStatus,
            role: DgsDynamicAssociationRole = DgsDynamicAssociationRole.Unknown,
    ) -> None:
        """
        Build one immutable DGS dynamic association record.

        :param unique_key: Stable source catalogue key.
        :param root_dgs_id: Owning ElmComp FID.
        :param root_name: Owning ElmComp display name.
        :param root_typ_id: Owning ElmComp frame type FID.
        :param slot_dgs_id: Optional direct BlkSlot FID.
        :param slot_name: Optional direct BlkSlot name.
        :param slot_index: Optional pblk/pelm ordinal.
        :param slot_element: Optional raw BlkSlot pointer to its default or prototype element.
        :param slot_filter: Optional raw BlkSlot filter declaring the allowed PowerFactory element classes.
        :param source_element_dgs_id: Optional referenced pElm FID.
        :param source_element_name: Optional referenced pElm name.
        :param source_element_class: Optional referenced pElm PowerFactory class.
        :param final_template_name: Final VeraGrid template name owned by this
            catalogue entry or by its exact physical root-slot association.
        :param role: Typed controller, measurement, host or actuator role.
        :param target_domain: Final reusable-template domain.
        :param status: Final import outcome.
        :return: None.
        """
        self._unique_key: str = unique_key
        self._root_dgs_id: str = root_dgs_id
        self._root_name: str = root_name
        self._root_typ_id: str = root_typ_id
        self._slot_dgs_id: str | None = slot_dgs_id
        self._slot_name: str | None = slot_name
        self._slot_index: int | None = slot_index
        self._slot_element: str | None = slot_element
        self._slot_filter: str | None = slot_filter
        self._source_element_dgs_id: str | None = source_element_dgs_id
        self._source_element_name: str | None = source_element_name
        self._source_element_class: str | None = source_element_class
        self._final_template_name: str | None = final_template_name
        self._role: DgsDynamicAssociationRole = role
        self._target_domain: DgsDynamicAssociationTargetDomain = target_domain
        self._status: DgsDynamicAssociationStatus = status

    def get_unique_key(self) -> str:
        """
        Return the stable source catalogue key.

        :return: Stable source catalogue key.
        """
        return self._unique_key

    def get_root_dgs_id(self) -> str:
        """
        Return the owning ElmComp FID.

        :return: Owning ElmComp FID.
        """
        return self._root_dgs_id

    def get_root_name(self) -> str:
        """
        Return the owning ElmComp display name.

        :return: Owning ElmComp display name.
        """
        return self._root_name

    def get_root_typ_id(self) -> str:
        """
        Return the owning ElmComp frame type FID.

        :return: Owning ElmComp frame type FID.
        """
        return self._root_typ_id

    def get_slot_dgs_id(self) -> str | None:
        """
        Return the optional direct BlkSlot FID.

        :return: BlkSlot FID or ``None``.
        """
        return self._slot_dgs_id

    def get_slot_name(self) -> str | None:
        """
        Return the optional direct BlkSlot display name.

        :return: BlkSlot name or ``None``.
        """
        return self._slot_name

    def get_slot_index(self) -> int | None:
        """
        Return the optional pblk/pelm ordinal.

        :return: Source ordinal or ``None``.
        """
        return self._slot_index

    def get_slot_element(self) -> str | None:
        """
        Return the raw BlkSlot default or prototype element pointer.

        :return: Default/prototype element FID or ``None``.
        """
        return self._slot_element

    def get_slot_filter(self) -> str | None:
        """
        Return the raw BlkSlot allowed-class filter.

        :return: PowerFactory element-class filter or ``None``.
        """
        return self._slot_filter

    def get_source_element_dgs_id(self) -> str | None:
        """
        Return the referenced pElm FID.

        :return: Referenced element FID or ``None``.
        """
        return self._source_element_dgs_id

    def get_source_element_name(self) -> str | None:
        """
        Return the referenced pElm display name.

        :return: Referenced element name or ``None``.
        """
        return self._source_element_name

    def get_source_element_class(self) -> str | None:
        """
        Return the referenced pElm PowerFactory class.

        :return: Referenced element class or ``None``.
        """
        return self._source_element_class

    def get_final_template_name(self) -> str | None:
        """
        Return the final VeraGrid template name.

        :return: Final template name or ``None``.
        """
        return self._final_template_name

    def get_target_domain(self) -> DgsDynamicAssociationTargetDomain:
        """
        Return the final reusable-template domain.

        :return: Final reusable-template domain.
        """
        return self._target_domain

    def get_role(self) -> DgsDynamicAssociationRole:
        """
        Return the typed relation role.

        :return: Controller, host, measurement or actuator role.
        """
        return self._role

    def get_status(self) -> DgsDynamicAssociationStatus:
        """
        Return the final import outcome.

        :return: Final import outcome.
        """
        return self._status

    def to_dict(self) -> Dict[str, object]:
        """
        Serialize the typed record to plain JSON-compatible values.

        :return: JSON-compatible record dictionary.
        """
        payload: Dict[str, object] = dict()
        payload["unique_key"] = self._unique_key
        payload["root_dgs_id"] = self._root_dgs_id
        payload["root_name"] = self._root_name
        payload["root_typ_id"] = self._root_typ_id
        payload["slot_dgs_id"] = self._slot_dgs_id
        payload["slot_name"] = self._slot_name
        payload["slot_index"] = self._slot_index
        payload["slot_element"] = self._slot_element
        payload["slot_filter"] = self._slot_filter
        payload["source_element_dgs_id"] = self._source_element_dgs_id
        payload["source_element_name"] = self._source_element_name
        payload["source_element_class"] = self._source_element_class
        payload["final_template_name"] = self._final_template_name
        payload["role"] = self._role.value
        payload["target_domain"] = self._target_domain.value
        payload["status"] = self._status.value
        return payload


class DgsDynamicAssociation(EditableDevice):
    """Represent one non-physical DGS root-slot-``pElm`` association."""

    __slots__ = (
        "_source_path",
        "_unique_key",
        "_root_dgs_id",
        "_root_name",
        "_root_typ_id",
        "_slot_dgs_id",
        "_slot_name",
        "_slot_index",
        "_slot_element",
        "_slot_filter",
        "_source_element_dgs_id",
        "_source_element_name",
        "_source_element_class",
        "_final_template_name",
        "_role",
        "_target_domain",
        "_status",
        "_optional_field_mask",
        "_active",
        "_var_factory",
        "_rms_model",
        "_rms_template",
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp("active", "", bool, "Whether this logical dynamic host participates in simulation.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp(
            "rms_model",
            "",
            SubObjectType.DaeBlockType,
            "Executable logical RMS model.",
            display=False,
            cat=[PrpCat.RMS],
        ),
        GCProp(
            "rms_template",
            "",
            DeviceType.RmsModelTemplateDevice,
            "Reusable RMS template assigned to the logical DGS root.",
            display=True,
            cat=[PrpCat.RMS],
        ),
        GCProp("source_path", "", str, "Original DGS source path.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp("unique_key", "", str, "Stable source association key.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp("root_dgs_id", "", str, "Owning ElmComp FID.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp("root_name", "", str, "Owning ElmComp display name.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp("root_typ_id", "", str, "Owning ElmComp frame FID.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp("slot_dgs_id", "", str, "Direct BlkSlot FID when present.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp("slot_name", "", str, "Direct BlkSlot name when present.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp("slot_index", "", int, "Source pblk/pelm ordinal when present.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp("slot_element", "", str, "Raw BlkSlot default element pointer.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp("slot_filter", "", str, "Raw BlkSlot allowed-class filter.", cat=[PrpCat.RMS, PrpCat.EMT]),
        GCProp(
            "source_element_dgs_id",
            "",
            str,
            "Referenced pElm FID when present.",
            cat=[PrpCat.RMS, PrpCat.EMT],
        ),
        GCProp(
            "source_element_name",
            "",
            str,
            "Referenced pElm display name when present.",
            cat=[PrpCat.RMS, PrpCat.EMT],
        ),
        GCProp(
            "source_element_class",
            "",
            str,
            "Referenced pElm PowerFactory class when present.",
            cat=[PrpCat.RMS, PrpCat.EMT],
        ),
        GCProp(
            "final_template_name",
            "",
            str,
            "Final reusable VeraGrid template name when present.",
            cat=[PrpCat.RMS, PrpCat.EMT],
        ),
        GCProp(
            "role",
            "",
            DgsDynamicAssociationRole,
            "Physical or logical role in the DGS composite.",
            cat=[PrpCat.RMS, PrpCat.EMT],
        ),
        GCProp(
            "target_domain",
            "",
            DgsDynamicAssociationTargetDomain,
            "Reusable-template target domain.",
            cat=[PrpCat.RMS, PrpCat.EMT],
        ),
        GCProp(
            "status",
            "",
            DgsDynamicAssociationStatus,
            "Dynamic import outcome.",
            cat=[PrpCat.RMS, PrpCat.EMT],
        ),
        # The mask is loaded after the raw optional values.  This retains the
        # distinction between absent values and valid empty strings because
        # VeraGrid primitive columns cannot deserialize ``None`` losslessly.
        GCProp(
            "optional_field_mask",
            "",
            int,
            "Presence bits for optional DGS provenance fields.",
            cat=[PrpCat.RMS, PrpCat.EMT],
        ),
    )

    def __init__(
            self,
            name: str = "",
            code: str = "",
            idtag: str | None = None,
            source_path: str = "",
            unique_key: str = "",
            root_dgs_id: str = "",
            root_name: str = "",
            root_typ_id: str = "",
            slot_dgs_id: str | None = None,
            slot_name: str | None = None,
            slot_index: int | None = None,
            slot_element: str | None = None,
            slot_filter: str | None = None,
            source_element_dgs_id: str | None = None,
            source_element_name: str | None = None,
            source_element_class: str | None = None,
            final_template_name: str | None = None,
            role: DgsDynamicAssociationRole = DgsDynamicAssociationRole.Unknown,
            target_domain: DgsDynamicAssociationTargetDomain = DgsDynamicAssociationTargetDomain.Rms,
            status: DgsDynamicAssociationStatus = DgsDynamicAssociationStatus.Skipped,
    ) -> None:
        """
        Build one persistable dynamic association without physical semantics.

        :param name: Human-readable association name.
        :param code: Optional secondary code.
        :param idtag: Stable VeraGrid object identifier.
        :param source_path: Original DGS source path.
        :param unique_key: Stable source association key.
        :param root_dgs_id: Owning ElmComp FID.
        :param root_name: Owning ElmComp display name.
        :param root_typ_id: Owning ElmComp frame FID.
        :param slot_dgs_id: Optional direct BlkSlot FID.
        :param slot_name: Optional direct BlkSlot name.
        :param slot_index: Optional pblk/pelm ordinal.
        :param slot_element: Optional raw BlkSlot element pointer.
        :param slot_filter: Optional raw BlkSlot allowed-class filter.
        :param source_element_dgs_id: Optional referenced pElm FID.
        :param source_element_name: Optional referenced pElm display name.
        :param source_element_class: Optional referenced pElm class.
        :param final_template_name: Optional final VeraGrid template name.
        :param role: Typed controller, measurement, host or actuator role.
        :param target_domain: Reusable-template target domain.
        :param status: Dynamic import outcome.
        :return: None.
        """
        EditableDevice.__init__(
            self,
            name=name,
            code=code,
            idtag=idtag,
            device_type=DeviceType.DgsDynamicAssociationDevice,
        )

        # Association records remain non-physical, while root records may own
        # one executable composite controller shared by several actuators.
        self._active: bool = True
        self._var_factory: VarFactory | None = None
        self._rms_model: Block = Block()
        self._rms_template: RmsModelTemplate | None = None

        # Preserve required source identity as ordinary primitive properties so
        # it remains directly inspectable in the database and saved project.
        self._source_path: str = str(source_path)
        self._unique_key: str = str(unique_key)
        self._root_dgs_id: str = str(root_dgs_id)
        self._root_name: str = str(root_name)
        self._root_typ_id: str = str(root_typ_id)

        # Store optional values in primitive columns and track their presence
        # separately.  A zero raw integer or empty string may still be a valid
        # source value, so neither is used as a null sentinel.
        self._optional_field_mask: int = 0
        self._slot_dgs_id: str = ""
        self._slot_name: str = ""
        self._slot_index: int = 0
        self._slot_element: str = ""
        self._slot_filter: str = ""
        self._source_element_dgs_id: str = ""
        self._source_element_name: str = ""
        self._source_element_class: str = ""
        self._final_template_name: str = ""
        self.set_slot_dgs_id(value=slot_dgs_id)
        self.set_slot_name(value=slot_name)
        self.set_slot_index(value=slot_index)
        self.set_slot_element(value=slot_element)
        self.set_slot_filter(value=slot_filter)
        self.set_source_element_dgs_id(value=source_element_dgs_id)
        self.set_source_element_name(value=source_element_name)
        self.set_source_element_class(value=source_element_class)
        self.set_final_template_name(value=final_template_name)

        if isinstance(role, DgsDynamicAssociationRole):
            self._role: DgsDynamicAssociationRole = role
        else:
            self._role = DgsDynamicAssociationRole.Unknown

        # Invalid external enum values are handled deterministically instead of
        # leaving the entity in a partially initialized state.
        if isinstance(target_domain, DgsDynamicAssociationTargetDomain):
            self._target_domain: DgsDynamicAssociationTargetDomain = target_domain
        else:
            self._target_domain = DgsDynamicAssociationTargetDomain.Rms

        if isinstance(status, DgsDynamicAssociationStatus):
            self._status: DgsDynamicAssociationStatus = status
        else:
            self._status = DgsDynamicAssociationStatus.Skipped

    @property
    def active(self) -> bool:
        """
        Return whether this logical dynamic host participates in simulation.

        :return: Active state.
        """
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        """
        Set whether this logical dynamic host participates in simulation.

        :param value: New active state.
        :return: None.
        """
        self._active = bool(value)

    def set_var_factory(self, var_factory: VarFactory) -> None:
        """
        Attach the circuit-owned symbolic variable factory.

        :param var_factory: Shared circuit variable factory.
        :return: None.
        """
        self._var_factory = var_factory
        if self._rms_template is None or not self._rms_model.empty():
            pass
        else:
            # Pointer columns are resolved before the loaded entity joins the
            # circuit. Rebuild only when no persisted executable block exists.
            self.rms_template = self._rms_template

    @property
    def rms_model(self) -> Block:
        """
        Return the executable logical RMS block.

        :return: Logical RMS block.
        """
        return self._rms_model

    @rms_model.setter
    def rms_model(self, value: Block) -> None:
        """Restore one persisted executable logical RMS block.

        :param value: Deserialized RMS block.
        :return: None.
        """
        if isinstance(value, Block):
            self._rms_model = value
        else:
            raise ValueError("Logical RMS model assignment requires Block")

    @property
    def rms_template(self) -> RmsModelTemplate | None:
        """
        Return the reusable template assigned to this logical root.

        :return: Assigned RMS template or ``None``.
        """
        return self._rms_template

    @rms_template.setter
    def rms_template(self, value: RmsModelTemplate | None) -> None:
        """
        Assign one reusable template without physical bus semantics.

        :param value: Reusable logical RMS template or ``None``.
        :return: None.
        """
        if isinstance(value, RmsModelTemplate):
            if self._var_factory is None:
                # During project loading the template pointer is resolved before
                # the entity receives the circuit VarFactory. Retain both the
                # pointer and the already parsed rms_model without rebuilding.
                self._rms_template = value
            else:
                runtime_block: Block = copy.deepcopy(value.block)
                runtime_block.unify_blocks()
                self._rms_model = duplicate_block(runtime_block, self._var_factory)
                self._rms_model.name = value.name
                self._rms_template = value
        else:
            if value is None:
                self._rms_template = None
                self._rms_model = Block()
            else:
                raise ValueError("Logical RMS template assignment requires RmsModelTemplate or None")

    @property
    def source_path(self) -> str:
        """
        Return the original DGS source path.

        :return: Original DGS source path.
        """
        return self._source_path

    @source_path.setter
    def source_path(self, value: str) -> None:
        """
        Set the original DGS source path.

        :param value: Original DGS source path.
        :return: None.
        """
        self._source_path = str(value)

    @property
    def unique_key(self) -> str:
        """
        Return the stable source association key.

        :return: Stable source association key.
        """
        return self._unique_key

    @unique_key.setter
    def unique_key(self, value: str) -> None:
        """
        Set the stable source association key.

        :param value: Stable source association key.
        :return: None.
        """
        self._unique_key = str(value)

    @property
    def root_dgs_id(self) -> str:
        """
        Return the owning ElmComp FID.

        :return: Owning ElmComp FID.
        """
        return self._root_dgs_id

    @root_dgs_id.setter
    def root_dgs_id(self, value: str) -> None:
        """
        Set the owning ElmComp FID.

        :param value: Owning ElmComp FID.
        :return: None.
        """
        self._root_dgs_id = str(value)

    @property
    def root_name(self) -> str:
        """
        Return the owning ElmComp display name.

        :return: Owning ElmComp display name.
        """
        return self._root_name

    @root_name.setter
    def root_name(self, value: str) -> None:
        """
        Set the owning ElmComp display name.

        :param value: Owning ElmComp display name.
        :return: None.
        """
        self._root_name = str(value)

    @property
    def root_typ_id(self) -> str:
        """
        Return the owning ElmComp frame FID.

        :return: Owning ElmComp frame FID.
        """
        return self._root_typ_id

    @root_typ_id.setter
    def root_typ_id(self, value: str) -> None:
        """
        Set the owning ElmComp frame FID.

        :param value: Owning ElmComp frame FID.
        :return: None.
        """
        self._root_typ_id = str(value)

    @property
    def slot_dgs_id(self) -> str:
        """
        Return the serializable raw BlkSlot FID.

        :return: Raw BlkSlot FID or an empty placeholder.
        """
        return self._slot_dgs_id

    @slot_dgs_id.setter
    def slot_dgs_id(self, value: str) -> None:
        """
        Set a present raw BlkSlot FID during editing or deserialization.

        :param value: Raw BlkSlot FID.
        :return: None.
        """
        self._slot_dgs_id = str(value)
        self._optional_field_mask |= 1

    def get_slot_dgs_id(self) -> str | None:
        """
        Return the semantic optional BlkSlot FID.

        :return: BlkSlot FID or ``None``.
        """
        result: str | None
        if self._optional_field_mask & 1:
            result = self._slot_dgs_id
        else:
            result = None
        return result

    def set_slot_dgs_id(self, value: str | None) -> None:
        """
        Set or clear the semantic optional BlkSlot FID.

        :param value: BlkSlot FID or ``None``.
        :return: None.
        """
        if value is None:
            self._slot_dgs_id = ""
            self._optional_field_mask &= ~1
        else:
            self._slot_dgs_id = str(value)
            self._optional_field_mask |= 1

    @property
    def slot_name(self) -> str:
        """
        Return the serializable raw BlkSlot name.

        :return: Raw BlkSlot name or an empty placeholder.
        """
        return self._slot_name

    @slot_name.setter
    def slot_name(self, value: str) -> None:
        """
        Set a present raw BlkSlot name during editing or deserialization.

        :param value: Raw BlkSlot name.
        :return: None.
        """
        self._slot_name = str(value)
        self._optional_field_mask |= 2

    def get_slot_name(self) -> str | None:
        """
        Return the semantic optional BlkSlot name.

        :return: BlkSlot name or ``None``.
        """
        result: str | None
        if self._optional_field_mask & 2:
            result = self._slot_name
        else:
            result = None
        return result

    def set_slot_name(self, value: str | None) -> None:
        """
        Set or clear the semantic optional BlkSlot name.

        :param value: BlkSlot name or ``None``.
        :return: None.
        """
        if value is None:
            self._slot_name = ""
            self._optional_field_mask &= ~2
        else:
            self._slot_name = str(value)
            self._optional_field_mask |= 2

    @property
    def slot_index(self) -> int:
        """
        Return the serializable raw pblk/pelm ordinal.

        :return: Raw ordinal or a zero placeholder.
        """
        return self._slot_index

    @slot_index.setter
    def slot_index(self, value: int) -> None:
        """
        Set a present raw pblk/pelm ordinal during editing or deserialization.

        :param value: Raw pblk/pelm ordinal.
        :return: None.
        """
        self._slot_index = int(value)
        self._optional_field_mask |= 4

    def get_slot_index(self) -> int | None:
        """
        Return the semantic optional pblk/pelm ordinal.

        :return: Source ordinal or ``None``.
        """
        result: int | None
        if self._optional_field_mask & 4:
            result = self._slot_index
        else:
            result = None
        return result

    def set_slot_index(self, value: int | None) -> None:
        """
        Set or clear the semantic optional pblk/pelm ordinal.

        :param value: Source ordinal or ``None``.
        :return: None.
        """
        if value is None:
            self._slot_index = 0
            self._optional_field_mask &= ~4
        else:
            self._slot_index = int(value)
            self._optional_field_mask |= 4

    @property
    def slot_element(self) -> str:
        """
        Return the serializable raw BlkSlot element pointer.

        :return: Raw element pointer or an empty placeholder.
        """
        return self._slot_element

    @slot_element.setter
    def slot_element(self, value: str) -> None:
        """
        Set a present raw BlkSlot element pointer.

        :param value: Raw element pointer.
        :return: None.
        """
        self._slot_element = str(value)
        self._optional_field_mask |= 8

    def get_slot_element(self) -> str | None:
        """
        Return the semantic optional BlkSlot element pointer.

        :return: Element pointer or ``None``.
        """
        result: str | None
        if self._optional_field_mask & 8:
            result = self._slot_element
        else:
            result = None
        return result

    def set_slot_element(self, value: str | None) -> None:
        """
        Set or clear the semantic optional BlkSlot element pointer.

        :param value: Element pointer or ``None``.
        :return: None.
        """
        if value is None:
            self._slot_element = ""
            self._optional_field_mask &= ~8
        else:
            self._slot_element = str(value)
            self._optional_field_mask |= 8

    @property
    def slot_filter(self) -> str:
        """
        Return the serializable raw BlkSlot class filter.

        :return: Raw class filter or an empty placeholder.
        """
        return self._slot_filter

    @slot_filter.setter
    def slot_filter(self, value: str) -> None:
        """
        Set a present raw BlkSlot class filter.

        :param value: Raw class filter.
        :return: None.
        """
        self._slot_filter = str(value)
        self._optional_field_mask |= 16

    def get_slot_filter(self) -> str | None:
        """
        Return the semantic optional BlkSlot class filter.

        :return: Class filter or ``None``.
        """
        result: str | None
        if self._optional_field_mask & 16:
            result = self._slot_filter
        else:
            result = None
        return result

    def set_slot_filter(self, value: str | None) -> None:
        """
        Set or clear the semantic optional BlkSlot class filter.

        :param value: Class filter or ``None``.
        :return: None.
        """
        if value is None:
            self._slot_filter = ""
            self._optional_field_mask &= ~16
        else:
            self._slot_filter = str(value)
            self._optional_field_mask |= 16

    @property
    def source_element_dgs_id(self) -> str:
        """
        Return the serializable raw referenced pElm FID.

        :return: Raw pElm FID or an empty placeholder.
        """
        return self._source_element_dgs_id

    @source_element_dgs_id.setter
    def source_element_dgs_id(self, value: str) -> None:
        """
        Set a present raw referenced pElm FID.

        :param value: Raw pElm FID.
        :return: None.
        """
        self._source_element_dgs_id = str(value)
        self._optional_field_mask |= 32

    def get_source_element_dgs_id(self) -> str | None:
        """
        Return the semantic optional referenced pElm FID.

        :return: Referenced pElm FID or ``None``.
        """
        result: str | None
        if self._optional_field_mask & 32:
            result = self._source_element_dgs_id
        else:
            result = None
        return result

    def set_source_element_dgs_id(self, value: str | None) -> None:
        """
        Set or clear the semantic optional referenced pElm FID.

        :param value: Referenced pElm FID or ``None``.
        :return: None.
        """
        if value is None:
            self._source_element_dgs_id = ""
            self._optional_field_mask &= ~32
        else:
            self._source_element_dgs_id = str(value)
            self._optional_field_mask |= 32

    @property
    def source_element_name(self) -> str:
        """
        Return the serializable raw referenced pElm name.

        :return: Raw pElm name or an empty placeholder.
        """
        return self._source_element_name

    @source_element_name.setter
    def source_element_name(self, value: str) -> None:
        """
        Set a present raw referenced pElm name.

        :param value: Raw pElm name.
        :return: None.
        """
        self._source_element_name = str(value)
        self._optional_field_mask |= 64

    def get_source_element_name(self) -> str | None:
        """
        Return the semantic optional referenced pElm name.

        :return: Referenced pElm name or ``None``.
        """
        result: str | None
        if self._optional_field_mask & 64:
            result = self._source_element_name
        else:
            result = None
        return result

    def set_source_element_name(self, value: str | None) -> None:
        """
        Set or clear the semantic optional referenced pElm name.

        :param value: Referenced pElm name or ``None``.
        :return: None.
        """
        if value is None:
            self._source_element_name = ""
            self._optional_field_mask &= ~64
        else:
            self._source_element_name = str(value)
            self._optional_field_mask |= 64

    @property
    def source_element_class(self) -> str:
        """
        Return the serializable raw referenced pElm class.

        :return: Raw pElm class or an empty placeholder.
        """
        return self._source_element_class

    @source_element_class.setter
    def source_element_class(self, value: str) -> None:
        """
        Set a present raw referenced pElm class.

        :param value: Raw pElm class.
        :return: None.
        """
        self._source_element_class = str(value)
        self._optional_field_mask |= 128

    def get_source_element_class(self) -> str | None:
        """
        Return the semantic optional referenced pElm class.

        :return: Referenced pElm class or ``None``.
        """
        result: str | None
        if self._optional_field_mask & 128:
            result = self._source_element_class
        else:
            result = None
        return result

    def set_source_element_class(self, value: str | None) -> None:
        """
        Set or clear the semantic optional referenced pElm class.

        :param value: Referenced pElm class or ``None``.
        :return: None.
        """
        if value is None:
            self._source_element_class = ""
            self._optional_field_mask &= ~128
        else:
            self._source_element_class = str(value)
            self._optional_field_mask |= 128

    @property
    def final_template_name(self) -> str:
        """
        Return the serializable raw final template name.

        :return: Raw template name or an empty placeholder.
        """
        return self._final_template_name

    @final_template_name.setter
    def final_template_name(self, value: str) -> None:
        """
        Set a present raw final template name.

        :param value: Raw final template name.
        :return: None.
        """
        self._final_template_name = str(value)
        self._optional_field_mask |= 256

    def get_final_template_name(self) -> str | None:
        """
        Return the semantic optional final template name.

        :return: Final template name or ``None``.
        """
        result: str | None
        if self._optional_field_mask & 256:
            result = self._final_template_name
        else:
            result = None
        return result

    def set_final_template_name(self, value: str | None) -> None:
        """
        Set or clear the semantic optional final template name.

        :param value: Final template name or ``None``.
        :return: None.
        """
        if value is None:
            self._final_template_name = ""
            self._optional_field_mask &= ~256
        else:
            self._final_template_name = str(value)
            self._optional_field_mask |= 256

    @property
    def target_domain(self) -> DgsDynamicAssociationTargetDomain:
        """
        Return the reusable-template target domain.

        :return: Reusable-template target domain.
        """
        return self._target_domain

    @property
    def role(self) -> DgsDynamicAssociationRole:
        """
        Return the typed DGS composite relation role.

        :return: Controller, host, measurement or actuator role.
        """
        return self._role

    @role.setter
    def role(self, value: DgsDynamicAssociationRole) -> None:
        """
        Set the relation role when valid.

        :param value: Typed relation role.
        :return: None.
        """
        if isinstance(value, DgsDynamicAssociationRole):
            self._role = value
        else:
            self._role = DgsDynamicAssociationRole.Unknown

    @target_domain.setter
    def target_domain(self, value: DgsDynamicAssociationTargetDomain) -> None:
        """
        Set the reusable-template target domain when valid.

        :param value: Reusable-template target domain.
        :return: None.
        """
        if isinstance(value, DgsDynamicAssociationTargetDomain):
            self._target_domain = value
        else:
            self._target_domain = DgsDynamicAssociationTargetDomain.Rms

    @property
    def status(self) -> DgsDynamicAssociationStatus:
        """
        Return the retained dynamic import outcome.

        :return: Dynamic import outcome.
        """
        return self._status

    @status.setter
    def status(self, value: DgsDynamicAssociationStatus) -> None:
        """
        Set the retained dynamic import outcome when valid.

        :param value: Dynamic import outcome.
        :return: None.
        """
        if isinstance(value, DgsDynamicAssociationStatus):
            self._status = value
        else:
            self._status = DgsDynamicAssociationStatus.Skipped

    @property
    def optional_field_mask(self) -> int:
        """
        Return the persistent optional-field presence mask.

        :return: Optional-field presence mask.
        """
        return self._optional_field_mask

    @optional_field_mask.setter
    def optional_field_mask(self, value: int) -> None:
        """
        Restore the persistent optional-field presence mask.

        :param value: Optional-field presence mask.
        :return: None.
        """
        # Only the nine declared bits are meaningful.  Masking corrupt or
        # future values keeps the current entity state explicit and bounded.
        self._optional_field_mask = int(value) & 511

    def get_manifest_identity(self) -> Tuple[str, str]:
        """
        Return the idempotent source-manifest identity.

        :return: Original source path and stable association key.
        """
        return self._source_path, self._unique_key


def infer_dgs_dynamic_association_role(
        slot_index: int | None,
        source_element_class: str | None,
        slot_filter: str | None,
) -> DgsDynamicAssociationRole:
    """
    Infer a general composite relation role from exported DGS contracts.

    The inference deliberately ignores project and object names. PowerFactory
    class identities and ``BlkSlot.filtmod`` are stable export contracts that
    can be applied to unrelated projects.

    :param slot_index: Optional pblk/pelm ordinal; absence identifies the root.
    :param source_element_class: Referenced pElm PowerFactory class.
    :param slot_filter: Raw allowed-class filter from the direct BlkSlot.
    :return: Typed logical or physical association role.
    """
    if slot_index is None:
        return DgsDynamicAssociationRole.CompositeController
    else:
        pass

    if source_element_class is None:
        source_class_text: str = ""
    else:
        source_class_text = source_element_class.strip()
    if slot_filter is None:
        slot_filter_text: str = ""
    else:
        slot_filter_text = slot_filter.strip()
    contract_text: str = f"{source_class_text};{slot_filter_text}"

    measurement_classes: Set[str] = set([
        "StaVmea",
        "StaImea",
        "StaPqmea",
        "StaExtdatmea",
        "ElmPhi",
    ])
    measurement_class: str
    measurement_match: bool = False
    for measurement_class in measurement_classes:
        if not measurement_match and measurement_class in contract_text:
            measurement_match = True
        else:
            pass

    if "ElmDsl" in contract_text or "ElmComp" in contract_text:
        role: DgsDynamicAssociationRole = DgsDynamicAssociationRole.ControllerModel
    else:
        if measurement_match:
            role = DgsDynamicAssociationRole.Measurement
        else:
            if "StaSwitch" in contract_text or "ElmCoup" in contract_text:
                role = DgsDynamicAssociationRole.SwitchActuator
            else:
                if "ElmValve" in contract_text:
                    role = DgsDynamicAssociationRole.ValveActuator
                else:
                    if "ElmSind" in contract_text or "ElmRes" in contract_text:
                        role = DgsDynamicAssociationRole.PassiveActuator
                    else:
                        if (
                                source_class_text.startswith("Elm")
                                or source_class_text.startswith("Sta")
                        ):
                            role = DgsDynamicAssociationRole.PhysicalHost
                        else:
                            role = DgsDynamicAssociationRole.Unknown
    return role


class DgsDynamicAssociationManifest:
    """
    Store all separate dynamic associations imported from one DGS source.
    """

    __slots__ = ("_source_path", "_records")

    def __init__(
            self,
            source_path: str,
            records: Sequence[DgsDynamicAssociationRecord],
    ) -> None:
        """
        Build one fixed-size association manifest.

        :param source_path: Original DGS source path.
        :param records: Ordered DGS association records.
        :return: None.
        """
        self._source_path: str = source_path
        self._records: List[DgsDynamicAssociationRecord] = list(records)

    def get_source_path(self) -> str:
        """
        Return the original DGS source path.

        :return: Original DGS source path.
        """
        return self._source_path

    def get_records(self) -> List[DgsDynamicAssociationRecord]:
        """
        Return a defensive copy of the ordered association records.

        :return: Ordered association records.
        """
        return list(self._records)

    def get_direct_source_association_count(self) -> int:
        """
        Count exact root-slot-pElm relations in this manifest.

        :return: Number of records with a slot index and referenced element FID.
        """
        count: int = 0
        record: DgsDynamicAssociationRecord

        for record in self._records:
            if record.get_slot_index() is not None and record.get_source_element_dgs_id() is not None:
                count += 1
            else:
                pass

        return count

    def to_dict(self) -> Dict[str, object]:
        """
        Serialize the manifest to plain JSON-compatible values.

        :return: JSON-compatible manifest dictionary.
        """
        payload: Dict[str, object] = dict()
        association_payloads: List[Dict[str, object]] = list()
        record: DgsDynamicAssociationRecord

        for record in self._records:
            association_payloads.append(record.to_dict())

        payload["schema"] = "veragrid-dgs-dynamic-associations"
        payload["version"] = 1
        payload["source_path"] = self._source_path
        payload["associations"] = association_payloads
        return payload


def install_dgs_dynamic_association_manifest_in_circuit(
        circuit: MultiCircuit,
        manifest: DgsDynamicAssociationManifest,
) -> int:
    """
    Install one typed manifest as non-physical ``MultiCircuit`` entities.

    Reinstalling the same source path and unique record key is idempotent.  A
    structurally deduplicated template may still have several distinct source
    associations because the source record key, rather than template name, is
    the entity identity.

    :param circuit: Destination VeraGrid circuit.
    :param manifest: Typed DGS association manifest.
    :return: Number of newly installed association entities.
    """
    existing_identities: Set[Tuple[str, str]] = set()
    existing_association: DgsDynamicAssociation
    source_path: str = manifest.get_source_path()
    record: DgsDynamicAssociationRecord
    association_identity: Tuple[str, str]
    slot_name: str | None
    association_name: str
    association: DgsDynamicAssociation
    added_count: int = 0

    # Snapshot the existing semantic identities once so massive imports remain
    # linear and repeated manifest installation cannot grow duplicate objects.
    for existing_association in circuit.get_dgs_dynamic_associations():
        existing_identities.add(existing_association.get_manifest_identity())

    # Materialize every source relation independently.  The entity records
    # provenance only; it deliberately does not activate a runtime controller.
    for record in manifest.get_records():
        association_identity = source_path, record.get_unique_key()
        if association_identity in existing_identities:
            pass
        else:
            slot_name = record.get_slot_name()
            if slot_name is None or len(slot_name) == 0:
                association_name = record.get_root_name()
            else:
                association_name = f"{record.get_root_name()} :: {slot_name}"

            association = DgsDynamicAssociation(
                name=association_name,
                code=record.get_unique_key(),
                source_path=source_path,
                unique_key=record.get_unique_key(),
                root_dgs_id=record.get_root_dgs_id(),
                root_name=record.get_root_name(),
                root_typ_id=record.get_root_typ_id(),
                slot_dgs_id=record.get_slot_dgs_id(),
                slot_name=slot_name,
                slot_index=record.get_slot_index(),
                slot_element=record.get_slot_element(),
                slot_filter=record.get_slot_filter(),
                source_element_dgs_id=record.get_source_element_dgs_id(),
                source_element_name=record.get_source_element_name(),
                source_element_class=record.get_source_element_class(),
                final_template_name=record.get_final_template_name(),
                role=record.get_role(),
                target_domain=record.get_target_domain(),
                status=record.get_status(),
            )
            circuit.add_dgs_dynamic_association(obj=association)
            existing_identities.add(association_identity)
            added_count += 1

    return added_count


def _read_required_string(payload: Dict[str, object], key: str) -> str | None:
    """
    Read one required non-empty string from a JSON object.

    :param payload: Parsed JSON record.
    :param key: Field name.
    :return: String value or ``None`` when invalid.
    """
    raw_value: object | None = payload.get(key, None)
    result: str | None

    if isinstance(raw_value, str) and len(raw_value) > 0:
        result = raw_value
    else:
        result = None

    return result


def _read_optional_string(payload: Dict[str, object], key: str) -> str | None:
    """
    Read one optional string from a JSON object.

    :param payload: Parsed JSON record.
    :param key: Field name.
    :return: String value or ``None`` when absent.
    """
    raw_value: object | None = payload.get(key, None)
    result: str | None

    if raw_value is None:
        result = None
    else:
        if isinstance(raw_value, str):
            result = raw_value
        else:
            result = None

    return result


def _read_optional_int(payload: Dict[str, object], key: str) -> int | None:
    """
    Read one optional integer from a JSON object.

    :param payload: Parsed JSON record.
    :param key: Field name.
    :return: Integer value or ``None`` when absent or invalid.
    """
    raw_value: object | None = payload.get(key, None)
    result: int | None

    if raw_value is None:
        result = None
    else:
        if isinstance(raw_value, int) and not isinstance(raw_value, bool):
            result = raw_value
        else:
            result = None

    return result


def _has_valid_optional_string(payload: Dict[str, object], key: str) -> bool:
    """
    Check that one optional JSON field is absent, null or textual.

    :param payload: Parsed JSON record.
    :param key: Field name.
    :return: ``True`` when the optional string field is losslessly readable.
    """
    raw_value: object | None = payload.get(key, None)
    is_valid: bool

    if raw_value is None or isinstance(raw_value, str):
        is_valid = True
    else:
        is_valid = False

    return is_valid


def _has_valid_optional_int(payload: Dict[str, object], key: str) -> bool:
    """
    Check that one optional JSON field is absent, null or an integer.

    :param payload: Parsed JSON record.
    :param key: Field name.
    :return: ``True`` when the optional integer field is losslessly readable.
    """
    raw_value: object | None = payload.get(key, None)
    is_valid: bool

    if raw_value is None:
        is_valid = True
    else:
        if isinstance(raw_value, int) and not isinstance(raw_value, bool):
            is_valid = True
        else:
            is_valid = False

    return is_valid


def _parse_target_domain(raw_value: object) -> DgsDynamicAssociationTargetDomain | None:
    """
    Parse one persistent target-domain value.

    :param raw_value: Raw JSON field value.
    :return: Parsed target domain or ``None``.
    """
    result: DgsDynamicAssociationTargetDomain | None

    if raw_value == DgsDynamicAssociationTargetDomain.Rms.value:
        result = DgsDynamicAssociationTargetDomain.Rms
    else:
        if raw_value == DgsDynamicAssociationTargetDomain.Emt.value:
            result = DgsDynamicAssociationTargetDomain.Emt
        else:
            result = None

    return result


def _parse_role(raw_value: object) -> DgsDynamicAssociationRole | None:
    """
    Parse one persistent association-role value.

    :param raw_value: Raw JSON field value.
    :return: Parsed role or ``None``.
    """
    result: DgsDynamicAssociationRole | None = None
    candidate_role: DgsDynamicAssociationRole

    for candidate_role in DgsDynamicAssociationRole:
        if result is None and raw_value == candidate_role.value:
            result = candidate_role
        else:
            pass
    return result


def _parse_status(raw_value: object) -> DgsDynamicAssociationStatus | None:
    """
    Parse one persistent import-outcome value.

    :param raw_value: Raw JSON field value.
    :return: Parsed import outcome or ``None``.
    """
    result: DgsDynamicAssociationStatus | None = None
    candidate_status: DgsDynamicAssociationStatus

    for candidate_status in DgsDynamicAssociationStatus:
        if result is None and raw_value == candidate_status.value:
            result = candidate_status
        else:
            pass

    return result


def _parse_record(payload: Dict[str, object]) -> DgsDynamicAssociationRecord | None:
    """
    Parse one typed association record from JSON-compatible values.

    :param payload: Parsed JSON record.
    :return: Typed record or ``None`` when required fields are invalid.
    """
    unique_key: str | None = _read_required_string(payload=payload, key="unique_key")
    root_dgs_id: str | None = _read_required_string(payload=payload, key="root_dgs_id")
    root_name: str | None = _read_required_string(payload=payload, key="root_name")
    root_typ_id: str | None = _read_required_string(payload=payload, key="root_typ_id")
    target_domain: DgsDynamicAssociationTargetDomain | None = _parse_target_domain(
        payload.get("target_domain", None)
    )
    role: DgsDynamicAssociationRole | None = _parse_role(payload.get("role", None))
    status: DgsDynamicAssociationStatus | None = _parse_status(payload.get("status", None))
    optional_fields_valid: bool = (
        _has_valid_optional_string(payload=payload, key="slot_dgs_id") and
        _has_valid_optional_string(payload=payload, key="slot_name") and
        _has_valid_optional_int(payload=payload, key="slot_index") and
        _has_valid_optional_string(payload=payload, key="slot_element") and
        _has_valid_optional_string(payload=payload, key="slot_filter") and
        _has_valid_optional_string(payload=payload, key="source_element_dgs_id") and
        _has_valid_optional_string(payload=payload, key="source_element_name") and
        _has_valid_optional_string(payload=payload, key="source_element_class") and
        _has_valid_optional_string(payload=payload, key="final_template_name")
    )
    if role is None and optional_fields_valid:
        # Manifests written before typed actuator roles were introduced remain
        # readable because the role is reproducible from their DGS class data.
        role = infer_dgs_dynamic_association_role(
            slot_index=_read_optional_int(payload=payload, key="slot_index"),
            source_element_class=_read_optional_string(
                payload=payload,
                key="source_element_class",
            ),
            slot_filter=_read_optional_string(payload=payload, key="slot_filter"),
        )
    else:
        pass
    result: DgsDynamicAssociationRecord | None

    if (unique_key is None or root_dgs_id is None or root_name is None or
            root_typ_id is None or target_domain is None or status is None or
            role is None or not optional_fields_valid):
        result = None
    else:
        result = DgsDynamicAssociationRecord(
            unique_key=unique_key,
            root_dgs_id=root_dgs_id,
            root_name=root_name,
            root_typ_id=root_typ_id,
            slot_dgs_id=_read_optional_string(payload=payload, key="slot_dgs_id"),
            slot_name=_read_optional_string(payload=payload, key="slot_name"),
            slot_index=_read_optional_int(payload=payload, key="slot_index"),
            slot_element=_read_optional_string(payload=payload, key="slot_element"),
            slot_filter=_read_optional_string(payload=payload, key="slot_filter"),
            source_element_dgs_id=_read_optional_string(payload=payload, key="source_element_dgs_id"),
            source_element_name=_read_optional_string(payload=payload, key="source_element_name"),
            source_element_class=_read_optional_string(payload=payload, key="source_element_class"),
            final_template_name=_read_optional_string(payload=payload, key="final_template_name"),
            role=role,
            target_domain=target_domain,
            status=status,
        )

    return result


def build_dgs_dynamic_association_manifest_output_path(
        source_path: str,
        catalog_root_folder: str | None = None,
) -> Path:
    """
    Build a collision-safe persistent path for one DGS association manifest.

    :param source_path: Original DGS source path.
    :param catalog_root_folder: Optional explicit VeraGrid user root.
    :return: Manifest JSON path under the separate association catalogue.
    """
    root_folder: Path
    source_file_path: Path = Path(source_path)
    safe_stem_chars: List[str] = list()
    char: str
    safe_stem: str
    source_key: str

    if catalog_root_folder is None:
        root_folder = Path(get_create_veragrid_folder())
    else:
        root_folder = Path(catalog_root_folder)

    for char in source_file_path.stem:
        if char.isalnum() or char in {"_", "-"}:
            safe_stem_chars.append(char)
        else:
            safe_stem_chars.append("_")

    safe_stem = "".join(safe_stem_chars).strip("_")
    if len(safe_stem) == 0:
        safe_stem = "dgs_dynamic_models"
    else:
        pass

    # Hash the normalized source path so equal file names from different
    # projects retain independent association manifests on Windows.
    source_key = hashlib.sha256(str(source_file_path).casefold().encode("utf-8")).hexdigest()[:12]
    return root_folder / "user_defined_models" / "associations" / f"{safe_stem}_{source_key}.associations.json"


def save_dgs_dynamic_association_manifest(
        manifest: DgsDynamicAssociationManifest,
        output_path: str,
) -> Path:
    """
    Persist one typed DGS dynamic association manifest.

    :param manifest: Typed manifest to persist.
    :param output_path: Destination JSON path.
    :return: Written manifest path.
    """
    destination_path: Path = Path(output_path)
    temporary_path: Path = destination_path.with_name(f"{destination_path.name}.tmp")
    manifest_payload: Dict[str, object] = manifest.to_dict()

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    # Write beside the destination and replace only after serialization
    # succeeds, so a prior valid manifest survives an interrupted refresh.
    temporary_path.write_text(
        json.dumps(manifest_payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(destination_path)
    return destination_path


def load_dgs_dynamic_association_manifest(
        input_path: str,
        logger: Logger | None = None,
) -> DgsDynamicAssociationManifest | None:
    """
    Load and validate one persistent DGS dynamic association manifest.

    Invalid records make the whole manifest invalid because silently dropping
    one relation would break the many-to-one provenance contract.

    :param input_path: Source JSON path.
    :param logger: Optional diagnostic logger.
    :return: Typed manifest or ``None`` when validation fails.
    """
    source_path: Path = Path(input_path)
    payload_obj: object
    source_dgs_path: str | None
    associations_obj: object | None
    records: List[DgsDynamicAssociationRecord] = list()
    record_obj: object
    parsed_record: DgsDynamicAssociationRecord | None
    load_failed: bool = False

    try:
        payload_obj = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if logger is None:
            pass
        else:
            logger.add_warning(
                msg="DGS dynamic association manifest could not be read",
                value=f"{source_path}: {exc}",
            )
        return None

    if isinstance(payload_obj, dict):
        schema_obj: object | None = payload_obj.get("schema", None)
        version_obj: object | None = payload_obj.get("version", None)
        source_dgs_path = _read_required_string(payload=payload_obj, key="source_path")
        associations_obj = payload_obj.get("associations", None)
        if schema_obj == "veragrid-dgs-dynamic-associations" and version_obj == 1:
            pass
        else:
            load_failed = True
    else:
        source_dgs_path = None
        associations_obj = None
        load_failed = True

    if isinstance(associations_obj, list):
        for record_obj in associations_obj:
            if isinstance(record_obj, dict):
                parsed_record = _parse_record(payload=record_obj)
            else:
                parsed_record = None

            if parsed_record is None:
                load_failed = True
            else:
                records.append(parsed_record)
    else:
        load_failed = True

    if load_failed or source_dgs_path is None:
        if logger is None:
            pass
        else:
            logger.add_warning(
                msg="DGS dynamic association manifest has an invalid schema",
                value=str(source_path),
            )
        return None
    else:
        return DgsDynamicAssociationManifest(source_path=source_dgs_path, records=records)


def load_user_dgs_dynamic_association_manifests(
        catalog_root_folder: str | None = None,
        logger: Logger | None = None,
) -> List[DgsDynamicAssociationManifest]:
    """
    Load every valid association manifest from the separate user catalogue.

    :param catalog_root_folder: Optional explicit VeraGrid user root.
    :param logger: Optional diagnostic logger.
    :return: Valid manifests in deterministic file-name order.
    """
    root_folder: Path
    associations_folder: Path
    manifests: List[DgsDynamicAssociationManifest] = list()
    manifest_path: Path
    manifest: DgsDynamicAssociationManifest | None

    if catalog_root_folder is None:
        root_folder = Path(get_create_veragrid_folder())
    else:
        root_folder = Path(catalog_root_folder)

    associations_folder = root_folder / "user_defined_models" / "associations"
    if associations_folder.exists():
        for manifest_path in sorted(associations_folder.glob("*.associations.json")):
            manifest = load_dgs_dynamic_association_manifest(
                input_path=str(manifest_path),
                logger=logger,
            )
            if manifest is None:
                pass
            else:
                manifests.append(manifest)
    else:
        pass

    return manifests
