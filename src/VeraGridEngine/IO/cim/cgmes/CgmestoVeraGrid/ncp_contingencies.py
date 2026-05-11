# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Dict, List

import VeraGridEngine.Devices as gcdev
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_typing import CGMES_ASSETS
from VeraGridEngine.IO.cim.cgmes.cgmes_utils import normalize_cgmes_reference_uuid
from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.enumerations import ContingencyOperationTypes


def parse_contingency_equipment_status(contingent_status: str | None,
                                       logger: DataLogger,
                                       contingency_equipment: CGMES_ASSETS) -> float | None:
    """
    Convert NCP ``contingentStatus`` into VeraGrid contingency ``Active`` value.

    :param contingent_status: NCP contingent status URI/text.
    :param logger: Data logger.
    :param contingency_equipment: Source NCP ContingencyEquipment object.
    :return: Target ``Active`` value:
             - 0.0 means outage (outOfService)
             - 1.0 means explicit in-service
             - None means unsupported status
    """
    if contingent_status is None:
        return 0.0
    else:
        pass

    status_text: str = str(contingent_status).lower()
    if "outofservice" in status_text:
        return 0.0
    elif "inservice" in status_text:
        return 1.0
    else:
        logger.add_warning(
            msg='Unsupported contingency equipment status',
            device=contingency_equipment.rdfid,
            device_class=contingency_equipment.tpe,
            device_property='contingentStatus',
            value=contingent_status,
            expected_value='outOfService or inService'
        )
        return None


def build_contingency_device_lookup(gcdev_model: MultiCircuit) -> Dict[str, object]:
    """
    Build lookup table for devices that can be targeted by contingencies.

    :param gcdev_model: VeraGrid model.
    :return: Dictionary keyed by canonical/normalized device idtag.
    """
    contingency_device_lookup: Dict[str, object] = dict()
    contingency_devices: List[object] = list()

    for branch_device in gcdev_model.get_branches(add_vsc=True, add_hvdc=True, add_switch=True):
        contingency_devices.append(branch_device)
    for injection_device in gcdev_model.get_injection_devices():
        contingency_devices.append(injection_device)

    for contingency_device in contingency_devices:
        contingency_device_idtag: str = contingency_device.idtag
        if len(contingency_device_idtag) > 0:
            if contingency_device_idtag in contingency_device_lookup:
                pass
            else:
                contingency_device_lookup[contingency_device_idtag] = contingency_device

            normalized_idtag: str | None = normalize_cgmes_reference_uuid(contingency_device_idtag)
            if normalized_idtag is not None:
                if normalized_idtag in contingency_device_lookup:
                    pass
                else:
                    contingency_device_lookup[normalized_idtag] = contingency_device
            else:
                pass
        else:
            pass

    return contingency_device_lookup


def get_ncp_contingency_objects(cgmes_model: CgmesCircuit) -> List[CGMES_ASSETS]:
    """
    Collect NCP contingency objects from all supported contingency subclasses.

    :param cgmes_model: CGMES model.
    :return: De-duplicated contingency object list.
    """
    contingency_objects: List[CGMES_ASSETS] = list()
    contingency_by_uuid: Dict[str, CGMES_ASSETS] = dict()
    contingency_lists: List[List[CGMES_ASSETS]] = list()

    contingency_lists.append(cgmes_model.cgmes_assets.Contingency_list)
    contingency_lists.append(cgmes_model.cgmes_assets.OrdinaryContingency_list)
    contingency_lists.append(cgmes_model.cgmes_assets.ExceptionalContingency_list)
    contingency_lists.append(cgmes_model.cgmes_assets.OutOfRangeContingency_list)

    for contingency_list in contingency_lists:
        for contingency_obj in contingency_list:
            contingency_uuid: str = contingency_obj.uuid
            if contingency_uuid in contingency_by_uuid:
                pass
            else:
                contingency_by_uuid[contingency_uuid] = contingency_obj

    for contingency_obj in contingency_by_uuid.values():
        contingency_objects.append(contingency_obj)

    return contingency_objects


def get_gcdev_contingencies(cgmes_model: CgmesCircuit,
                            gcdev_model: MultiCircuit,
                            logger: DataLogger) -> None:
    """
    Convert NCP contingencies to VeraGrid ContingencyGroup/Contingency objects.

    :param cgmes_model: CGMES model.
    :param gcdev_model: VeraGrid model.
    :param logger: Data logger.
    :return: Nothing.
    """
    contingency_objects: List[CGMES_ASSETS] = get_ncp_contingency_objects(cgmes_model=cgmes_model)
    contingency_equipment_list: List[CGMES_ASSETS] = cgmes_model.cgmes_assets.ContingencyEquipment_list

    if len(contingency_objects) == 0:
        return
    else:
        pass

    contingency_device_lookup: Dict[str, object] = build_contingency_device_lookup(gcdev_model=gcdev_model)
    contingency_group_lookup: Dict[str, gcdev.ContingencyGroup] = dict()
    contingency_equipment_by_contingency: Dict[str, List[CGMES_ASSETS]] = dict()
    imported_contingency_count: int = 0
    skipped_contingency_count: int = 0
    skipped_empty_group_count: int = 0

    for contingency_equipment in contingency_equipment_list:
        contingency_obj: object = contingency_equipment.Contingency
        if contingency_obj is None or isinstance(contingency_obj, str):
            logger.add_warning(
                msg='ContingencyEquipment without resolved Contingency reference',
                device=contingency_equipment.rdfid,
                device_class=contingency_equipment.tpe,
                device_property='Contingency',
                value=contingency_obj,
                expected_value='resolved object'
            )
        else:
            contingency_uuid: str = contingency_obj.uuid
            lst: List[CGMES_ASSETS] | None = contingency_equipment_by_contingency.get(contingency_uuid, None)
            if lst is None:
                contingency_equipment_by_contingency[contingency_uuid] = [contingency_equipment]
            else:
                lst.append(contingency_equipment)

    for contingency_obj in contingency_objects:
        contingency_uuid: str = contingency_obj.uuid
        contingency_elements: List[CGMES_ASSETS] | None = contingency_equipment_by_contingency.get(contingency_uuid, None)
        if contingency_elements is None:
            pass
        else:
            contingency_name: str = contingency_obj.name
            if len(contingency_name) > 0:
                pass
            else:
                contingency_name = contingency_uuid

            normal_must_study: bool | None = contingency_obj.normalMustStudy
            must_study: bool | None = contingency_obj.mustStudy
            if isinstance(normal_must_study, bool):
                contingency_group_active: bool = normal_must_study
            elif isinstance(must_study, bool):
                contingency_group_active = must_study
            else:
                contingency_group_active = True

            # Defer group creation until we import at least one valid contingency element.
            # This avoids orphan groups that later break contingency analyses expecting group->contingency mapping.
            contingency_imported_for_group: bool = False

            for contingency_equipment in contingency_elements:
                equipment_obj: object = contingency_equipment.Equipment
                if equipment_obj is None or isinstance(equipment_obj, str):
                    skipped_contingency_count += 1
                    logger.add_warning(
                        msg='ContingencyEquipment without resolved Equipment reference',
                        device=contingency_equipment.rdfid,
                        device_class=contingency_equipment.tpe,
                        device_property='Equipment',
                        value=equipment_obj,
                        expected_value='resolved object'
                    )
                else:
                    equipment_uuid: str = equipment_obj.uuid
                    target_device: object | None = contingency_device_lookup.get(equipment_uuid, None)
                    if target_device is None:
                        skipped_contingency_count += 1
                        logger.add_warning(
                            msg='Contingency target equipment not imported as a contingency-capable VeraGrid device',
                            device=contingency_equipment.rdfid,
                            device_class=contingency_equipment.tpe,
                            device_property='Equipment.uuid',
                            value=equipment_uuid
                        )
                    else:
                        contingency_active_value: float | None = parse_contingency_equipment_status(
                            contingent_status=contingency_equipment.contingentStatus,
                            logger=logger,
                            contingency_equipment=contingency_equipment
                        )
                        if contingency_active_value is None:
                            skipped_contingency_count += 1
                        else:
                            contingency_group: gcdev.ContingencyGroup | None = contingency_group_lookup.get(
                                contingency_uuid, None
                            )
                            if contingency_group is None:
                                contingency_group = gcdev.ContingencyGroup(
                                    idtag=contingency_uuid,
                                    name=contingency_name,
                                    category=contingency_obj.tpe,
                                    active=contingency_group_active
                                )
                                gcdev_model.add_contingency_group(contingency_group)
                                contingency_group_lookup[contingency_uuid] = contingency_group
                            else:
                                pass

                            contingency_description: object = contingency_obj.description
                            if isinstance(contingency_description, str):
                                contingency_comment: str = contingency_description
                            else:
                                contingency_comment = ""

                            target_code_raw: object = target_device.code
                            if isinstance(target_code_raw, str):
                                target_code: str = target_code_raw
                            else:
                                target_code = ""

                            target_name_raw: str = target_device.name
                            if isinstance(target_name_raw, str):
                                target_name: str = target_name_raw
                            else:
                                target_name = "device"

                            gcdev_contingency = gcdev.Contingency(
                                device=target_device,
                                idtag=contingency_equipment.uuid,
                                name=f"{contingency_name}::{target_name}",
                                code=target_code,
                                prop=ContingencyOperationTypes.Active,
                                value=contingency_active_value,
                                group=contingency_group,
                                comment=contingency_comment
                            )
                            gcdev_model.add_contingency(gcdev_contingency)
                            imported_contingency_count += 1
                            contingency_imported_for_group = True

            if contingency_imported_for_group:
                pass
            else:
                skipped_empty_group_count += 1
                logger.add_warning(
                    msg='Skipped NCP contingency group because no valid contingency equipment could be imported',
                    device=contingency_obj.rdfid,
                    device_class=contingency_obj.tpe,
                    device_property='Contingency',
                    value=contingency_uuid
                )

    if imported_contingency_count > 0:
        logger.add_info(
            msg='Imported NCP contingencies',
            value=imported_contingency_count,
            expected_value=len(contingency_equipment_list),
            comment=f"Skipped={skipped_contingency_count}; EmptyGroups={skipped_empty_group_count}"
        )
    else:
        if skipped_empty_group_count > 0:
            logger.add_warning(
                msg='No NCP contingencies imported',
                value=skipped_contingency_count,
                expected_value=len(contingency_equipment_list),
                comment=f"EmptyGroups={skipped_empty_group_count}"
            )
        else:
            pass
