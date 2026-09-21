# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Any

import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.IO.veragrid.pack_unpack import parse_object_type_from_json, veragrid_object_to_json


def test_native_legacy_cable_vectors_load_as_scalar_properties() -> None:
    """Preserve old cable records while preferring explicitly saved scalar inputs.

    :return: None.
    """
    # These lists reproduce the former native JSON representation, including
    # third entries which were never used by the core/sheath calculation.
    legacy: dict[str, Any] = dict(
        idtag='legacy-cable',
        thIns=list((7.0, 1.6, 9.0)),
        crho=list((2.8, 1.7, 9.0)),
        Cf=list((100.0, 99.4, 90.0)),
        my=list((1.0, 0.99999, 9.0)),
        cepsr=list((2.3, 2.5, 9.0)),
        ctand=list((0.0, 0.01, 0.9)),
    )
    old_scalar: dict[str, Any] = dict(
        idtag='old-scalar-cable', Vnom=15.0, rpha=0.22,
        diaCon=12.0, diaTube=0.0, diaCab=31.0, thSht=0.2, thIns=8.0,
        crho_core=2.82, crho_sheath=1.72, Cf_core=98.0, Cf_sheath=99.0,
        cepsr_core_sheath=2.4, cepsr_outer=2.7, ctand_core_sheath=0.001, ctand_outer=0.002,
        my_core=0.999, my_sheath=0.998, ks=0.8, kp=0.9,
    )
    current: dict[str, float] = dict(
        nominal_voltage=15.0, core_dc_resistance=0.22,
        core_diameter=12.0, core_internal_diameter=0.0, cable_diameter=31.0,
        sheath_thickness=0.2, main_insulation_thickness=8.0,
        core_resistivity=2.82, sheath_resistivity=1.72,
        core_filling_factor=98.0, sheath_filling_factor=99.0,
        main_insulation_permittivity=2.4, outer_insulation_permittivity=2.7,
        main_insulation_loss_tangent=0.001, outer_insulation_loss_tangent=0.002,
        core_relative_permeability=0.999, sheath_relative_permeability=0.998,
        skin_effect_factor=0.8, proximity_effect_factor=0.9,
    )
    mixed: dict[str, Any] = legacy.copy()
    mixed.update(idtag='mixed-cable', thIns=8.0, Cf_core=97.0, cepsr_outer=2.6)
    mixed.update(current)
    logger: Logger = Logger()
    parsed: list[ALL_DEV_TYPES]
    parsed_by_id: dict[str, ALL_DEV_TYPES]
    parsed, parsed_by_id = parse_object_type_from_json(
        template_elm=dev.UndergroundCableType(),
        data_list=list((legacy, old_scalar, mixed)),
        elements_dict_by_type=dict(),
        time_profile=None,
        block_parser=None,
        logger=logger,
    )
    restored: dev.UndergroundCableType = parsed_by_id['legacy-cable']
    assert restored.main_insulation_thickness == 7.0
    assert (restored.core_resistivity, restored.sheath_resistivity) == (2.8, 1.7)
    assert (restored.core_filling_factor, restored.sheath_filling_factor) == (100.0, 99.4)
    assert (restored.core_relative_permeability, restored.sheath_relative_permeability) == (1.0, 0.99999)
    assert (restored.main_insulation_permittivity, restored.outer_insulation_permittivity) == (2.3, 2.5)
    assert (restored.main_insulation_loss_tangent, restored.outer_insulation_loss_tangent) == (0.0, 0.01)
    assert len(logger) == 0
    assert legacy['thIns'] == list((7.0, 1.6, 9.0))

    # Saving the migrated cable must emit the current scalar format only.
    saved: dict[str, Any] = veragrid_object_to_json(elm=restored, block_saver=None)
    assert saved['main_insulation_thickness'] == 7.0
    assert saved['sheath_filling_factor'] == 99.4
    assert 'crho' not in saved
    assert 'Cf' not in saved
    assert 'my' not in saved
    assert 'cepsr' not in saved
    assert 'ctand' not in saved

    # Both scalar generations load identically; new names override vector and
    # previous scalar names when multiple generations coexist in one record.
    record_id: str
    for record_id in ('old-scalar-cable', 'mixed-cable'):
        saved = veragrid_object_to_json(elm=parsed_by_id[record_id], block_saver=None)
        property_name: str
        expected_value: float
        for property_name, expected_value in current.items():
            assert saved[property_name] == expected_value
        for property_name in old_scalar:
            if property_name != 'idtag':
                assert property_name not in saved
            else:
                pass
