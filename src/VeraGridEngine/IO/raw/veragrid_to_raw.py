# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math

import numpy as np
from typing import Dict
from itertools import groupby
from scipy.sparse import lil_matrix

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.raw.versioned.base.area import RawArea as RawAreaBase
from VeraGridEngine.IO.raw.versioned.base.zone import RawZone as RawZoneBase
from VeraGridEngine.IO.raw.versioned.base.bus import RawBus as RawBusBase
from VeraGridEngine.IO.raw.versioned.base.load import RawLoad as RawLoadBase
from VeraGridEngine.IO.raw.versioned.base.fixed_shunt import RawFixedShunt as RawFixedShuntBase
from VeraGridEngine.IO.raw.versioned.base.generator import RawGenerator as RawGeneratorBase
from VeraGridEngine.IO.raw.versioned.base.switched_shunt import RawSwitchedShunt as RawSwitchedShuntBase
from VeraGridEngine.IO.raw.versioned.base.transformer import RawTransformer as RawTransformerBase
from VeraGridEngine.IO.raw.versioned.base.branch import RawBranch as RawBranchBase
from VeraGridEngine.IO.raw.versioned.base.vsc_dc_line import RawVscDCLine as RawVscDCLineBase
from VeraGridEngine.IO.raw.versioned.base.two_terminal_dc_line import RawTwoTerminalDCLine as RawTwoTerminalDCLineBase
from VeraGridEngine.IO.raw.versioned.base.facts import RawFACTS as RawFACTSBase
from VeraGridEngine.IO.raw.versioned.base.system_switching_device import RawSystemSwitchingDevice as RawSystemSwitchingDeviceBase
from VeraGridEngine.IO.raw.versioned.v29.area import RawAreaV29
from VeraGridEngine.IO.raw.versioned.v29.zone import RawZoneV29
from VeraGridEngine.IO.raw.versioned.v29.bus import RawBusV29
from VeraGridEngine.IO.raw.versioned.v29.load import RawLoadV29
from VeraGridEngine.IO.raw.versioned.v29.generator import RawGeneratorV29
from VeraGridEngine.IO.raw.versioned.v29.fixed_shunt import RawFixedShuntV29
from VeraGridEngine.IO.raw.versioned.v29.switched_shunt import RawSwitchedShuntV29
from VeraGridEngine.IO.raw.versioned.v29.branch import RawBranchV29
from VeraGridEngine.IO.raw.versioned.v29.system_switching_device import RawSystemSwitchingDeviceV29
from VeraGridEngine.IO.raw.versioned.v29.transformer import RawTransformerV29
from VeraGridEngine.IO.raw.versioned.v29.vsc_dc_line import RawVscDCLineV29
from VeraGridEngine.IO.raw.versioned.v29.two_terminal_dc_line import RawTwoTerminalDCLineV29
from VeraGridEngine.IO.raw.versioned.v29.facts import RawFACTSV29
from VeraGridEngine.IO.raw.versioned.v30.area import RawAreaV30
from VeraGridEngine.IO.raw.versioned.v30.zone import RawZoneV30
from VeraGridEngine.IO.raw.versioned.v30.bus import RawBusV30
from VeraGridEngine.IO.raw.versioned.v30.load import RawLoadV30
from VeraGridEngine.IO.raw.versioned.v30.generator import RawGeneratorV30
from VeraGridEngine.IO.raw.versioned.v30.fixed_shunt import RawFixedShuntV30
from VeraGridEngine.IO.raw.versioned.v30.switched_shunt import RawSwitchedShuntV30
from VeraGridEngine.IO.raw.versioned.v30.branch import RawBranchV30
from VeraGridEngine.IO.raw.versioned.v30.system_switching_device import RawSystemSwitchingDeviceV30
from VeraGridEngine.IO.raw.versioned.v30.transformer import RawTransformerV30
from VeraGridEngine.IO.raw.versioned.v30.vsc_dc_line import RawVscDCLineV30
from VeraGridEngine.IO.raw.versioned.v30.two_terminal_dc_line import RawTwoTerminalDCLineV30
from VeraGridEngine.IO.raw.versioned.v30.facts import RawFACTSV30
from VeraGridEngine.IO.raw.versioned.v31.area import RawAreaV31
from VeraGridEngine.IO.raw.versioned.v31.zone import RawZoneV31
from VeraGridEngine.IO.raw.versioned.v31.bus import RawBusV31
from VeraGridEngine.IO.raw.versioned.v31.load import RawLoadV31
from VeraGridEngine.IO.raw.versioned.v31.generator import RawGeneratorV31
from VeraGridEngine.IO.raw.versioned.v31.fixed_shunt import RawFixedShuntV31
from VeraGridEngine.IO.raw.versioned.v31.switched_shunt import RawSwitchedShuntV31
from VeraGridEngine.IO.raw.versioned.v31.branch import RawBranchV31
from VeraGridEngine.IO.raw.versioned.v31.system_switching_device import RawSystemSwitchingDeviceV31
from VeraGridEngine.IO.raw.versioned.v31.transformer import RawTransformerV31
from VeraGridEngine.IO.raw.versioned.v31.vsc_dc_line import RawVscDCLineV31
from VeraGridEngine.IO.raw.versioned.v31.two_terminal_dc_line import RawTwoTerminalDCLineV31
from VeraGridEngine.IO.raw.versioned.v31.facts import RawFACTSV31
from VeraGridEngine.IO.raw.versioned.v32.area import RawAreaV32
from VeraGridEngine.IO.raw.versioned.v32.zone import RawZoneV32
from VeraGridEngine.IO.raw.versioned.v32.bus import RawBusV32
from VeraGridEngine.IO.raw.versioned.v32.load import RawLoadV32
from VeraGridEngine.IO.raw.versioned.v32.generator import RawGeneratorV32
from VeraGridEngine.IO.raw.versioned.v32.fixed_shunt import RawFixedShuntV32
from VeraGridEngine.IO.raw.versioned.v32.switched_shunt import RawSwitchedShuntV32
from VeraGridEngine.IO.raw.versioned.v32.branch import RawBranchV32
from VeraGridEngine.IO.raw.versioned.v32.system_switching_device import RawSystemSwitchingDeviceV32
from VeraGridEngine.IO.raw.versioned.v32.transformer import RawTransformerV32
from VeraGridEngine.IO.raw.versioned.v32.vsc_dc_line import RawVscDCLineV32
from VeraGridEngine.IO.raw.versioned.v32.two_terminal_dc_line import RawTwoTerminalDCLineV32
from VeraGridEngine.IO.raw.versioned.v32.facts import RawFACTSV32
from VeraGridEngine.IO.raw.versioned.v33.area import RawAreaV33
from VeraGridEngine.IO.raw.versioned.v33.zone import RawZoneV33
from VeraGridEngine.IO.raw.versioned.v33.bus import RawBusV33
from VeraGridEngine.IO.raw.versioned.v33.load import RawLoadV33
from VeraGridEngine.IO.raw.versioned.v33.generator import RawGeneratorV33
from VeraGridEngine.IO.raw.versioned.v33.fixed_shunt import RawFixedShuntV33
from VeraGridEngine.IO.raw.versioned.v33.switched_shunt import RawSwitchedShuntV33
from VeraGridEngine.IO.raw.versioned.v33.branch import RawBranchV33
from VeraGridEngine.IO.raw.versioned.v33.system_switching_device import RawSystemSwitchingDeviceV33
from VeraGridEngine.IO.raw.versioned.v33.transformer import RawTransformerV33
from VeraGridEngine.IO.raw.versioned.v33.vsc_dc_line import RawVscDCLineV33
from VeraGridEngine.IO.raw.versioned.v33.two_terminal_dc_line import RawTwoTerminalDCLineV33
from VeraGridEngine.IO.raw.versioned.v33.facts import RawFACTSV33
from VeraGridEngine.IO.raw.versioned.v34.area import RawAreaV34
from VeraGridEngine.IO.raw.versioned.v34.zone import RawZoneV34
from VeraGridEngine.IO.raw.versioned.v34.bus import RawBusV34
from VeraGridEngine.IO.raw.versioned.v34.load import RawLoadV34
from VeraGridEngine.IO.raw.versioned.v34.generator import RawGeneratorV34
from VeraGridEngine.IO.raw.versioned.v34.fixed_shunt import RawFixedShuntV34
from VeraGridEngine.IO.raw.versioned.v34.switched_shunt import RawSwitchedShuntV34
from VeraGridEngine.IO.raw.versioned.v34.branch import RawBranchV34
from VeraGridEngine.IO.raw.versioned.v34.system_switching_device import RawSystemSwitchingDeviceV34
from VeraGridEngine.IO.raw.versioned.v34.transformer import RawTransformerV34
from VeraGridEngine.IO.raw.versioned.v34.vsc_dc_line import RawVscDCLineV34
from VeraGridEngine.IO.raw.versioned.v34.two_terminal_dc_line import RawTwoTerminalDCLineV34
from VeraGridEngine.IO.raw.versioned.v34.facts import RawFACTSV34
from VeraGridEngine.IO.raw.versioned.v35.area import RawAreaV35
from VeraGridEngine.IO.raw.versioned.v35.zone import RawZoneV35
from VeraGridEngine.IO.raw.versioned.v35.bus import RawBusV35
from VeraGridEngine.IO.raw.versioned.v35.load import RawLoadV35
from VeraGridEngine.IO.raw.versioned.v35.generator import RawGeneratorV35
from VeraGridEngine.IO.raw.versioned.v35.fixed_shunt import RawFixedShuntV35
from VeraGridEngine.IO.raw.versioned.v35.switched_shunt import RawSwitchedShuntV35
from VeraGridEngine.IO.raw.versioned.v35.branch import RawBranchV35
from VeraGridEngine.IO.raw.versioned.v35.system_switching_device import RawSystemSwitchingDeviceV35
from VeraGridEngine.IO.raw.versioned.v35.transformer import RawTransformerV35
from VeraGridEngine.IO.raw.versioned.v35.vsc_dc_line import RawVscDCLineV35
from VeraGridEngine.IO.raw.versioned.v35.two_terminal_dc_line import RawTwoTerminalDCLineV35
from VeraGridEngine.IO.raw.versioned.v35.facts import RawFACTSV35
from VeraGridEngine.IO.raw.versioned.v36.area import RawAreaV36
from VeraGridEngine.IO.raw.versioned.v36.zone import RawZoneV36
from VeraGridEngine.IO.raw.versioned.v36.bus import RawBusV36
from VeraGridEngine.IO.raw.versioned.v36.load import RawLoadV36
from VeraGridEngine.IO.raw.versioned.v36.generator import RawGeneratorV36
from VeraGridEngine.IO.raw.versioned.v36.fixed_shunt import RawFixedShuntV36
from VeraGridEngine.IO.raw.versioned.v36.switched_shunt import RawSwitchedShuntV36
from VeraGridEngine.IO.raw.versioned.v36.branch import RawBranchV36
from VeraGridEngine.IO.raw.versioned.v36.system_switching_device import RawSystemSwitchingDeviceV36
from VeraGridEngine.IO.raw.versioned.v36.transformer import RawTransformerV36
from VeraGridEngine.IO.raw.versioned.v36.vsc_dc_line import RawVscDCLineV36
from VeraGridEngine.IO.raw.versioned.v36.two_terminal_dc_line import RawTwoTerminalDCLineV36
from VeraGridEngine.IO.raw.versioned.v36.facts import RawFACTSV36
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.psse_object import RawObject
from VeraGridEngine.IO.raw.raw_types import RawAreaLike, RawBranchLike, RawBusLike, RawFACTSLike, RawFixedShuntLike, RawGeneratorLike, RawLoadLike, RawSwitchedShuntLike, RawSystemSwitchingDeviceLike, RawTransformerLike, RawTwoTerminalDCLineLike, RawVscDCLineLike, RawZoneLike
import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.types import BRANCH_TYPES
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import (TapChangerTypes,
                                         TapPhaseControl,
                                         TapModuleControl,
                                         SwitchGraphicType)


def _set_if_registered(raw_obj: RawObject, property_name: str, value) -> None:
    raw_obj.set_registered_property_value(property_name, value)


def _set_branch_ratings(raw_branch: RawObject,
                        version: int,
                        rate: float,
                        contingency_factor: float,
                        protection_factor: float) -> None:
    rate2 = rate * contingency_factor
    rate3 = rate * protection_factor
    if version <= 33:
        raw_branch.RATEA = rate
        raw_branch.RATEB = rate2
        raw_branch.RATEC = rate3
    else:
        raw_branch.RATE1 = rate
        raw_branch.RATE2 = rate2
        raw_branch.RATE3 = rate3


def _set_transformer_winding_ratings(raw_transformer: RawObject,
                                     version: int,
                                     winding_index: int,
                                     rate: float,
                                     contingency_factor: float,
                                     protection_factor: float) -> None:
    rate2 = rate * contingency_factor
    rate3 = rate * protection_factor
    raw_transformer.set_winding_rating_triplet(winding_index=winding_index,
                                               version=version,
                                               rate_1=rate,
                                               rate_2=rate2,
                                               rate_3=rate3)


def get_area(area: dev.Area, i: int, raw_area_type: type[RawAreaLike] = RawAreaBase) -> RawAreaLike:
    """

    :param area:
    :param i:
    :param raw_area_type:
    :return:
    """
    result = raw_area_type()
    result.ARNAME = area.name
    result.I = i
    return result


def get_zone(zone: dev.Zone, i: int, raw_zone_type: type[RawZoneLike] = RawZoneBase) -> RawZoneLike:
    """

    :param zone:
    :param i:
    :param raw_zone_type:
    :return:
    """
    result = raw_zone_type()
    result.ZONAME = zone.name
    result.I = i
    return result


def get_psse_bus(bus: dev.Bus,
                 area_dict: Dict[dev.Area, int],
                 zones_dict: Dict[dev.Zone, int],
                 suggested_psse_number: int,
                 raw_bus_type: type[RawBusLike] = RawBusBase) -> RawBusLike:
    """

    :param bus:
    :param area_dict: 
    :param zones_dict:
    :param suggested_psse_number:
    :param raw_bus_type:
    :return:
    """
    psse_bus = raw_bus_type()
    psse_bus.NAME = str(bus.name)
    psse_bus.BASKV = bus.Vnom

    psse_bus.I = suggested_psse_number

    psse_bus.EVLO = bus.Vmin
    psse_bus.EVHI = bus.Vmax

    psse_bus.AREA = area_dict.get(bus.area, 0)
    psse_bus.ZONE = zones_dict.get(bus.zone, 0)
    psse_bus.VM = bus.Vm0
    psse_bus.VA = np.rad2deg(bus.Va0)

    psse_bus.IDE = bus._bus_type.value

    return psse_bus


def get_psse_load(load: dev.Load,
                  bus_dict: Dict[dev.Bus, int],
                  id_number: int,
                  version: int,
                  raw_load_type: type[RawLoadLike] = RawLoadBase) -> RawLoadLike:
    """

    :param load:
    :param bus_dict:
    :param id_number:
    :return:
    """
    psse_load = raw_load_type()

    psse_load.I = bus_dict[load.bus]
    psse_load.ID = id_number

    psse_load.YP = load.G
    psse_load.YQ = load.B
    psse_load.IP = load.Ir
    psse_load.IQ = -load.Ii
    psse_load.PL = load.P
    psse_load.QL = load.Q
    psse_load.STATUS = 1 if load.active else 0
    psse_load.SCALE = 1.0 if load.scalable else 0.0
    if version >= 36:
        _set_if_registered(psse_load, "NAME", str(load.name))

    return psse_load


def get_psse_load_from_external_grid(load: dev.ExternalGrid,
                                     bus_dict: Dict[dev.Bus, int],
                                     id_number: int,
                                     version: int,
                                     raw_load_type: type[RawLoadLike] = RawLoadBase) -> RawLoadLike:
    """

    :param load:
    :param bus_dict:
    :param id_number:
    :return:
    """
    psse_load = raw_load_type()

    psse_load.I = bus_dict[load.bus]
    psse_load.ID = id_number

    psse_load.PL = load.P
    psse_load.QL = load.Q
    psse_load.STATUS = 1 if load.active else 0
    if version >= 36:
        _set_if_registered(psse_load, "NAME", str(load.name))

    return psse_load


def get_psse_fixed_shunt(shunt: dev.Shunt,
                         bus_dict: Dict[dev.Bus, int],
                         id_number: int,
                         version: int,
                         raw_fixed_shunt_type: type[RawFixedShuntLike] = RawFixedShuntBase) -> RawFixedShuntLike:
    """

    :param shunt:
    :param bus_dict:
    :param id_number:
    :return:
    """
    psse_shunt = raw_fixed_shunt_type()

    psse_shunt.I = bus_dict[shunt.bus]
    psse_shunt.ID = id_number

    psse_shunt.GL = shunt.G
    psse_shunt.BL = shunt.B

    psse_shunt.STATUS = 1 if shunt.active else 0
    if version >= 36:
        _set_if_registered(psse_shunt, "NAME", str(shunt.name))

    return psse_shunt


def get_psse_switched_shunt(shunt: dev.ControllableShunt,
                            bus_dict: Dict[dev.Bus, int],
                            version: int,
                            raw_switched_shunt_type: type[RawSwitchedShuntLike] = RawSwitchedShuntBase) -> RawSwitchedShuntLike:
    """

    :param shunt:
    :param bus_dict:
    :return:
    """
    psse_switched_shunt = raw_switched_shunt_type()

    psse_switched_shunt.I = bus_dict[shunt.bus]

    psse_switched_shunt.BINIT = shunt.B
    psse_switched_shunt.STAT = int(shunt.active)
    if version >= 36:
        _set_if_registered(psse_switched_shunt, "NAME", str(shunt.name))

    if shunt.control_bus is not None and shunt.control_bus != shunt.bus:
        psse_switched_shunt.SWREG = bus_dict.get(shunt.control_bus, 0)

    if len(shunt.b_steps) > 0:
        diff_list = np.insert(np.diff(shunt.b_steps), 0, shunt.b_steps[0])
        aggregated_steps = [(sum(1 for _ in group), key) for key, group in groupby(diff_list)]

        for index, aggregated_step in enumerate(aggregated_steps):
            if index < 8:
                psse_switched_shunt.set_block(index + 1, 1, aggregated_step[0], aggregated_step[1])

    return psse_switched_shunt


def get_psse_generator(generator: dev.Generator,
                       bus_dict: Dict[dev.Bus, int],
                       id_number: int,
                       version: int,
                       raw_generator_type: type[RawGeneratorLike] = RawGeneratorBase) -> RawGeneratorLike:
    """

    :param generator:
    :param bus_dict:
    :param id_number:
    :return:
    """
    psse_generator = raw_generator_type()

    psse_generator.I = bus_dict[generator.bus]
    psse_generator.ID = id_number

    if generator.control_bus is not None and generator.control_bus != generator.bus:
        psse_generator.IREG = bus_dict.get(generator.control_bus, 0)

    psse_generator.PG = generator.P
    psse_generator.VS = generator.Vset
    psse_generator.QB = generator.Qmin
    psse_generator.QT = generator.Qmax
    psse_generator.MBASE = generator.Snom
    psse_generator.PT = generator.Pmax
    psse_generator.PB = generator.Pmin
    psse_generator.STAT = 1 if generator.active else 0
    psse_generator.WPF = generator.Pf
    psse_generator.QG = generator.Q
    if version >= 36:
        _set_if_registered(psse_generator, "DROOPNAME", "")
        _set_if_registered(psse_generator, "NAME", str(generator.name))

    return psse_generator


def get_psse_transformer2w(transformer: dev.Transformer2W,
                           bus_dict: Dict[dev.Bus, int],
                           ckt: int,
                           version: int,
                           raw_transformer_type: type[RawTransformerLike] = RawTransformerBase) -> RawTransformerLike:
    """

    :param transformer:
    :param bus_dict:
    :param ckt:
    :return:
    """
    psse_transformer = raw_transformer_type()
    psse_transformer.windings = 2

    psse_transformer.idtag = transformer.idtag
    psse_transformer.STAT = 1 if transformer.active else 0

    psse_transformer.SBASE1_2 = transformer.Sn
    _set_transformer_winding_ratings(psse_transformer, version, 1,
                                     transformer.rate,
                                     transformer.contingency_factor,
                                     transformer.protection_rating_factor)

    # i, j, ckt = transformer.code.split("_", 2)
    psse_transformer.I = bus_dict[transformer.bus_from]
    psse_transformer.J = bus_dict[transformer.bus_to]
    psse_transformer.CKT = ckt

    psse_transformer.CW = 1
    # WINDV1 is the Winding 1 off-nominal turns ratio in pu of Winding1 bus base voltage
    mf, mt = transformer.get_virtual_taps()
    psse_transformer.WINDV1 = transformer.tap_module * mf / mt
    psse_transformer.WINDV2 = 1.0

    V1, V2, _ = transformer.get_from_to_nominal_voltages()
    psse_transformer.NOMV1 = V1
    psse_transformer.NOMV2 = V2 if V2 != V1 else 0.0

    psse_transformer.CZ = 1
    # 1 for resistance and reactance in pu on system MVA base and winding voltage base
    # translating: impedances in the system base, do noting
    psse_transformer.R1_2 = transformer.R
    psse_transformer.X1_2 = transformer.X

    psse_transformer.CM = 1
    # 1 for complex  admittance  in pu  on  system  MVA  base  and Winding 1 bus voltage base
    psse_transformer.MAG1 = transformer.G
    psse_transformer.MAG2 = transformer.B

    # tap changer values
    psse_transformer.NTP1 = transformer.tap_changer.total_positions
    psse_transformer.VMA1 = transformer.tap_changer.get_tap_module_max()
    psse_transformer.VMI1 = transformer.tap_changer.get_tap_module_min()

    psse_transformer.ANG1 = np.rad2deg(transformer.tap_phase)

    # Control types
    if transformer.tap_changer.tc_type == TapChangerTypes.NoRegulation:

        psse_transformer.COD1 = 0

    elif transformer.tap_changer.tc_type == TapChangerTypes.VoltageRegulation:

        if transformer.tap_module_control_mode == TapModuleControl.fixed:
            psse_transformer.COD1 = -1
        else:
            psse_transformer.COD1 = 1

    elif transformer.tap_changer.tc_type == TapChangerTypes.Symmetrical:

        if transformer.tap_phase_control_mode == TapPhaseControl.fixed:
            psse_transformer.COD1 = -3
        else:
            psse_transformer.COD1 = 3

        # RMA - Phase shift angle in degrees when |COD1| is 3 or 5. No default is allowed
        number_of_symmetrical_step = (transformer.tap_changer.total_positions - 1) / 2
        psse_transformer.RMA1 = 2 * math.degrees(math.atan(
             number_of_symmetrical_step * transformer.tap_changer.dV / 2
        ))

    elif transformer.tap_changer.tc_type == TapChangerTypes.Asymmetrical:

        if (transformer.tap_module_control_mode == TapModuleControl.fixed or
                transformer.tap_phase_control_mode == TapPhaseControl.fixed):
            psse_transformer.COD1 = -5
        else:
            psse_transformer.COD1 = 5
        psse_transformer.CNXA1 = transformer.tap_changer.asymmetry_angle

    else:
        pass

    return psse_transformer


def get_psse_transformer3w(transformer: dev.Transformer3W,
                           bus_dict: Dict[dev.Bus, int],
                           version: int,
                           raw_transformer_type: type[RawTransformerLike] = RawTransformerBase) -> RawTransformerLike:
    """

    :param transformer:
    :param bus_dict:
    :return:
    """
    psse_transformer = raw_transformer_type()
    psse_transformer.windings = 3

    psse_transformer.NOMV1 = transformer.V1
    psse_transformer.NOMV2 = transformer.V2
    psse_transformer.NOMV3 = transformer.V3

    psse_transformer.idtag = transformer.idtag
    psse_transformer.STAT = 1 if transformer.active else 0

    psse_transformer.NAME = transformer.name
    _set_transformer_winding_ratings(psse_transformer, version, 1,
                                     transformer.rate1,
                                     transformer.winding1.contingency_factor,
                                     transformer.winding1.protection_rating_factor)
    _set_transformer_winding_ratings(psse_transformer, version, 2,
                                     transformer.rate2,
                                     transformer.winding2.contingency_factor,
                                     transformer.winding2.protection_rating_factor)
    _set_transformer_winding_ratings(psse_transformer, version, 3,
                                     transformer.rate3,
                                     transformer.winding3.contingency_factor,
                                     transformer.winding3.protection_rating_factor)

    psse_transformer.CW = 1
    psse_transformer.WINDV1 = transformer.winding1.tap_module
    psse_transformer.WINDV2 = transformer.winding2.tap_module
    psse_transformer.WINDV3 = transformer.winding3.tap_module

    psse_transformer.ANG1 = np.rad2deg(transformer.winding1.tap_phase)
    psse_transformer.ANG2 = np.rad2deg(transformer.winding2.tap_phase)
    psse_transformer.ANG3 = np.rad2deg(transformer.winding3.tap_phase)

    i, j, k, ckt = transformer.code.split("_", 3)

    psse_transformer.I = bus_dict[transformer.bus1]
    psse_transformer.J = bus_dict[transformer.bus2]
    psse_transformer.K = bus_dict[transformer.bus3]
    psse_transformer.CKT = ckt

    psse_transformer.R1_2 = transformer.r12
    psse_transformer.X1_2 = transformer.x12
    psse_transformer.R2_3 = transformer.r23
    psse_transformer.X2_3 = transformer.x23
    psse_transformer.R3_1 = transformer.r31
    psse_transformer.X3_1 = transformer.x31
    psse_transformer.VMSTAR = transformer.bus0.Vm0
    psse_transformer.ANSTAR = np.rad2deg(transformer.bus0.Va0)

    return psse_transformer


def get_psse_branch(branch: dev.Line,
                    bus_dict: Dict[dev.Bus, int],
                    ckt: int,
                    version: int,
                    raw_branch_type: type[RawBranchLike] = RawBranchBase) -> RawBranchLike:
    """

    :param branch:
    :param bus_dict:
    :param ckt:
    :return:
    """
    psse_branch = raw_branch_type()

    # i, j, ckt = line.code.split("_", 2)

    psse_branch.I = bus_dict[branch.bus_from]
    psse_branch.J = bus_dict[branch.bus_to]

    psse_branch.CKT = ckt

    psse_branch.NAME = branch.name
    psse_branch.R = branch.R
    psse_branch.X = branch.X
    psse_branch.B = branch.B
    psse_branch.ST = 1 if branch.active else 0
    psse_branch.idtag = branch.idtag
    psse_branch.LEN = branch.length
    _set_branch_ratings(psse_branch, version, branch.rate, branch.contingency_factor, branch.protection_rating_factor)

    return psse_branch


def get_vsc_dc_line(hvdc_line: dev.HvdcLine,
                    bus_dict: Dict[dev.Bus, int],
                    version: int,
                    raw_vsc_dc_line_type: type[RawVscDCLineLike] = RawVscDCLineBase) -> RawVscDCLineLike:
    """

    :param hvdc_line:
    :param bus_dict:
    :return:
    """
    psse_vsc_dc_line = raw_vsc_dc_line_type()
    psse_vsc_dc_line.NAME = hvdc_line.name
    psse_vsc_dc_line.MDC = 1
    psse_vsc_dc_line.IBUS1 = bus_dict[hvdc_line.bus_from]
    psse_vsc_dc_line.IBUS2 = bus_dict[hvdc_line.bus_to]
    psse_vsc_dc_line.TYPE1 = 1
    psse_vsc_dc_line.TYPE2 = 2
    psse_vsc_dc_line.MODE1 = 1
    psse_vsc_dc_line.MODE2 = 1
    psse_vsc_dc_line.ACSET1 = hvdc_line.Vset_f
    psse_vsc_dc_line.ACSET2 = hvdc_line.Vset_t
    psse_vsc_dc_line.DCSET1 = hvdc_line.Pset
    psse_vsc_dc_line.DCSET2 = -hvdc_line.Pset
    psse_vsc_dc_line.SMAX1 = hvdc_line.rate
    psse_vsc_dc_line.SMAX2 = hvdc_line.rate
    if version >= 35:
        psse_vsc_dc_line.VSREG1 = psse_vsc_dc_line.IBUS1
        psse_vsc_dc_line.VSREG2 = psse_vsc_dc_line.IBUS2
    else:
        _set_if_registered(psse_vsc_dc_line, "REMOT1", psse_vsc_dc_line.IBUS1)
        _set_if_registered(psse_vsc_dc_line, "REMOT2", psse_vsc_dc_line.IBUS2)
    psse_vsc_dc_line.RMPCT1 = 100.0
    psse_vsc_dc_line.RMPCT2 = 100.0

    V1 = hvdc_line.bus_from.Vnom * psse_vsc_dc_line.ACSET1
    V2 = hvdc_line.bus_to.Vnom * psse_vsc_dc_line.ACSET2
    dV = (V1 - V2) * 1000.0
    P = hvdc_line.Pset / 1e-6
    psse_vsc_dc_line.RDC = dV * dV / P if P != 0 else 0

    return psse_vsc_dc_line


def get_psse_two_terminal_dc_line(hvdc_line: dev.HvdcLine,
                                  bus_dict: Dict[dev.Bus, int],
                                  raw_two_terminal_dc_line_type: type[RawTwoTerminalDCLineLike] = RawTwoTerminalDCLineBase) -> RawTwoTerminalDCLineLike:
    """

    :param hvdc_line:
    :param bus_dict:
    :return:
    """
    psse_two_terminal_dc_line = raw_two_terminal_dc_line_type()
    psse_two_terminal_dc_line.NAME = hvdc_line.name

    psse_two_terminal_dc_line.IPR = bus_dict[hvdc_line.bus_from]
    psse_two_terminal_dc_line.IPI = bus_dict[hvdc_line.bus_to]

    psse_two_terminal_dc_line.RDC = hvdc_line.r
    psse_two_terminal_dc_line.ANMNR = np.rad2deg(hvdc_line.min_firing_angle_f)
    psse_two_terminal_dc_line.ANMXR = np.rad2deg(hvdc_line.max_firing_angle_f)
    psse_two_terminal_dc_line.ANMNI = np.rad2deg(hvdc_line.min_firing_angle_t)
    psse_two_terminal_dc_line.ANMXI = np.rad2deg(hvdc_line.max_firing_angle_t)

    return psse_two_terminal_dc_line


def get_psse_facts(upfc: dev.UPFC,
                   bus_dict: Dict[dev.Bus, int],
                   version: int,
                   raw_facts_type: type[RawFACTSLike] = RawFACTSBase) -> RawFACTSLike:
    """

    :param upfc:
    :param bus_dict:
    :return:
    """
    psse_facts = raw_facts_type()
    psse_facts.NAME = upfc.name

    id_tag = upfc.idtag[:-2] if upfc.idtag.endswith("_1") else upfc.idtag
    # i, j = id_tag.split("_", 2)

    psse_facts.I = bus_dict[upfc.bus_from]
    psse_facts.J = bus_dict[upfc.bus_to]
    psse_facts.SET1 = upfc.R
    psse_facts.SHMX = 1 / upfc.Xsh if upfc.Xsh > 0 else 0.0
    psse_facts.VSET = upfc.Vsh
    psse_facts.PDES = upfc.Pfset
    psse_facts.QDES = upfc.Qfset
    psse_facts.IMX = upfc.rate - 1e-20
    if version <= 34:
        _set_if_registered(psse_facts, "REMOT", psse_facts.I)
    else:
        _set_if_registered(psse_facts, "FCREG", psse_facts.I)
        _set_if_registered(psse_facts, "NREG", 0)

    return psse_facts


def get_psse_switch(switch: dev.Switch,
                    bus_dict: Dict[dev.Bus, int],
                    ckt: int,
                    version: int,
                    raw_switch_type: type[RawSystemSwitchingDeviceLike] = RawSystemSwitchingDeviceBase) -> RawSystemSwitchingDeviceLike:
    """
    Convert VeraGrid Switch to PSSE system switching device.
    """
    psse_switch = raw_switch_type()

    psse_switch.I = bus_dict[switch.bus_from]
    psse_switch.J = bus_dict[switch.bus_to]
    psse_switch.CKT = str(ckt)
    psse_switch.X = switch.X
    if version <= 35:
        psse_switch.RATE1 = switch.rate
    psse_switch.STATUS = 1 if switch.active else 0
    psse_switch.NSTATUS = 0 if switch.normal_open else 1
    psse_switch.METERED = 1
    psse_switch.STYPE = 3 if switch.graphic_type == SwitchGraphicType.Disconnector else 2
    psse_switch.NAME = str(switch.name)
    if version >= 36:
        _set_if_registered(psse_switch, "RSETNAM", "")

    return psse_switch


class RawCounter:
    """
    Items to count stuff for the raw files
    """

    def __init__(self, grid: MultiCircuit):
        """
        Constructor
        :param grid: MultiCircuit
        """
        n = grid.get_bus_number()
        self._bus_int_dict = {bus: i + 1 for i, bus in enumerate(grid.get_buses())}
        self._bus_2_psseI_dict = dict()
        self._bus_dev_count_dict = {bus: 0 for bus in grid.get_buses()}
        self._ckt_counter = lil_matrix((n + 1, n + 1), dtype=int)

        self._max_bus_number = 1

    @property
    def psse_numbers_dict(self) -> Dict[dev.Bus, int]:
        """

        :return:
        """
        return self._bus_2_psseI_dict

    def register_psse_number(self, bus: dev.Bus, psse_I: int):
        """

        :param bus:
        :param psse_I:
        :return:
        """
        self._max_bus_number = max(self._max_bus_number, psse_I)

        if psse_I in self._bus_2_psseI_dict.keys():
            print("Repeated PSSe bus!!!")

        self._bus_2_psseI_dict[bus] = psse_I

    def get_next_psse_number(self):
        """

        :return:
        """
        return self._max_bus_number + 1

    def get_suggested_psse_number(self, bus: dev.Bus, logger: Logger) -> int:
        """

        :param bus:
        :param logger:
        :return:
        """
        try:
            psse_I = int(bus.code)

            if psse_I in self._bus_2_psseI_dict.keys():
                psse_I_pre = psse_I
                # repeated number, get a new one
                psse_I = self.get_next_psse_number()
                logger.add_error("Repeated PSSe number",
                                 device=bus.name,
                                 value=psse_I_pre,
                                 expected_value=psse_I)

        except ValueError:
            psse_I = self.get_next_psse_number()
            logger.add_error("Invalid PSSe number stored in bus.code",
                             device=bus.name,
                             value=str(bus.code),
                             expected_value=psse_I)

        self.register_psse_number(bus, psse_I)

        return psse_I

    def get_id(self, bus: dev.Bus) -> int:
        """
        Query the dictionary for the internal number and increase that number for the next time
        :param bus: Bus
        :return: integer
        """
        id_number = self._bus_dev_count_dict[bus] + 1
        self._bus_dev_count_dict[bus] = id_number
        return id_number

    def get_ckt(self, branch: BRANCH_TYPES) -> int:
        """
        Count the circuit number in the PSSe sense
        :param branch: some branch
        :return: CKT
        """
        i = self._bus_int_dict[branch.bus_from]
        j = self._bus_int_dict[branch.bus_to]
        ckt = self._ckt_counter[i, j]
        ckt2 = ckt + 1
        self._ckt_counter[i, j] = ckt2
        self._ckt_counter[j, i] = ckt2
        return ckt2


def veragrid_to_raw(grid: MultiCircuit, version: int, logger: Logger) -> PsseCircuit:
    """
    Convert MultiCircuit to PSSeCircuit
    :param grid: MultiCircuit
    :param version: Target PSSE RAW version
    :param logger: Logger
    :return: PsseCircuit
    """
    if version > 36:
        version = 36
    elif version < 29:
        version = 33
    else:
        version = version

    if version == 29:
        RawAreaT = RawAreaV29
        RawZoneT = RawZoneV29
        RawBusT = RawBusV29
        RawLoadT = RawLoadV29
        RawGeneratorT = RawGeneratorV29
        RawFixedShuntT = RawFixedShuntV29
        RawSwitchedShuntT = RawSwitchedShuntV29
        RawBranchT = RawBranchV29
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV29
        RawTransformerT = RawTransformerV29
        RawVscDCLineT = RawVscDCLineV29
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV29
        RawFACTST = RawFACTSV29
    elif version == 30:
        RawAreaT = RawAreaV30
        RawZoneT = RawZoneV30
        RawBusT = RawBusV30
        RawLoadT = RawLoadV30
        RawGeneratorT = RawGeneratorV30
        RawFixedShuntT = RawFixedShuntV30
        RawSwitchedShuntT = RawSwitchedShuntV30
        RawBranchT = RawBranchV30
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV30
        RawTransformerT = RawTransformerV30
        RawVscDCLineT = RawVscDCLineV30
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV30
        RawFACTST = RawFACTSV30
    elif version == 31:
        RawAreaT = RawAreaV31
        RawZoneT = RawZoneV31
        RawBusT = RawBusV31
        RawLoadT = RawLoadV31
        RawGeneratorT = RawGeneratorV31
        RawFixedShuntT = RawFixedShuntV31
        RawSwitchedShuntT = RawSwitchedShuntV31
        RawBranchT = RawBranchV31
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV31
        RawTransformerT = RawTransformerV31
        RawVscDCLineT = RawVscDCLineV31
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV31
        RawFACTST = RawFACTSV31
    elif version == 32:
        RawAreaT = RawAreaV32
        RawZoneT = RawZoneV32
        RawBusT = RawBusV32
        RawLoadT = RawLoadV32
        RawGeneratorT = RawGeneratorV32
        RawFixedShuntT = RawFixedShuntV32
        RawSwitchedShuntT = RawSwitchedShuntV32
        RawBranchT = RawBranchV32
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV32
        RawTransformerT = RawTransformerV32
        RawVscDCLineT = RawVscDCLineV32
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV32
        RawFACTST = RawFACTSV32
    elif version == 33:
        RawAreaT = RawAreaV33
        RawZoneT = RawZoneV33
        RawBusT = RawBusV33
        RawLoadT = RawLoadV33
        RawGeneratorT = RawGeneratorV33
        RawFixedShuntT = RawFixedShuntV33
        RawSwitchedShuntT = RawSwitchedShuntV33
        RawBranchT = RawBranchV33
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV33
        RawTransformerT = RawTransformerV33
        RawVscDCLineT = RawVscDCLineV33
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV33
        RawFACTST = RawFACTSV33
    elif version == 34:
        RawAreaT = RawAreaV34
        RawZoneT = RawZoneV34
        RawBusT = RawBusV34
        RawLoadT = RawLoadV34
        RawGeneratorT = RawGeneratorV34
        RawFixedShuntT = RawFixedShuntV34
        RawSwitchedShuntT = RawSwitchedShuntV34
        RawBranchT = RawBranchV34
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV34
        RawTransformerT = RawTransformerV34
        RawVscDCLineT = RawVscDCLineV34
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV34
        RawFACTST = RawFACTSV34
    elif version == 35:
        RawAreaT = RawAreaV35
        RawZoneT = RawZoneV35
        RawBusT = RawBusV35
        RawLoadT = RawLoadV35
        RawGeneratorT = RawGeneratorV35
        RawFixedShuntT = RawFixedShuntV35
        RawSwitchedShuntT = RawSwitchedShuntV35
        RawBranchT = RawBranchV35
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV35
        RawTransformerT = RawTransformerV35
        RawVscDCLineT = RawVscDCLineV35
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV35
        RawFACTST = RawFACTSV35
    else:
        RawAreaT = RawAreaV36
        RawZoneT = RawZoneV36
        RawBusT = RawBusV36
        RawLoadT = RawLoadV36
        RawGeneratorT = RawGeneratorV36
        RawFixedShuntT = RawFixedShuntV36
        RawSwitchedShuntT = RawSwitchedShuntV36
        RawBranchT = RawBranchV36
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV36
        RawTransformerT = RawTransformerV36
        RawVscDCLineT = RawVscDCLineV36
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV36
        RawFACTST = RawFACTSV36

    psse_circuit = PsseCircuit()
    psse_circuit.REV = version

    # create dictionaries
    area_dict: Dict[dev.Area, int] = dict()
    zones_dict: Dict[dev.Zone, int] = dict()

    counter = RawCounter(grid=grid)

    for i, area in enumerate(grid.areas):
        psse_circuit.areas.append(get_area(area=area, i=i + 1, raw_area_type=RawAreaT))
        area_dict[area] = i + 1

    for i, zone in enumerate(grid.zones):
        psse_circuit.zones.append(get_zone(zone=zone, i=i + 1, raw_zone_type=RawZoneT))
        zones_dict[zone] = i + 1

    for i, bus in enumerate(grid.buses):
        if not bus.internal:
            psse_bus = get_psse_bus(bus=bus,
                                    area_dict=area_dict,
                                    zones_dict=zones_dict,
                                    suggested_psse_number=counter.get_suggested_psse_number(bus=bus, logger=logger),
                                    raw_bus_type=RawBusT)
            psse_circuit.buses.append(psse_bus)
        else:
            logger.add_info(msg="Internal bus skipped at RAW export",
                            device=bus.name)

    for load in grid.loads:
        psse_circuit.loads.append(get_psse_load(load=load,
                                                bus_dict=counter.psse_numbers_dict,
                                                id_number=counter.get_id(load.bus),
                                                version=version,
                                                raw_load_type=RawLoadT))

    for load in grid.external_grids:
        psse_circuit.loads.append(get_psse_load_from_external_grid(load=load,
                                                                   bus_dict=counter.psse_numbers_dict,
                                                                   id_number=counter.get_id(load.bus),
                                                                   version=version,
                                                                   raw_load_type=RawLoadT))

    for generator in grid.generators:
        psse_circuit.generators.append(get_psse_generator(generator=generator,
                                                          bus_dict=counter.psse_numbers_dict,
                                                          id_number=counter.get_id(generator.bus),
                                                          version=version,
                                                          raw_generator_type=RawGeneratorT))

    for shunt in grid.shunts:
        psse_circuit.fixed_shunts.append(get_psse_fixed_shunt(shunt=shunt,
                                                              bus_dict=counter.psse_numbers_dict,
                                                              id_number=counter.get_id(shunt.bus),
                                                              version=version,
                                                              raw_fixed_shunt_type=RawFixedShuntT))

    for controllable_shunt in grid.controllable_shunts:
        psse_circuit.switched_shunts.append(get_psse_switched_shunt(shunt=controllable_shunt,
                                                                    bus_dict=counter.psse_numbers_dict,
                                                                    version=version,
                                                                    raw_switched_shunt_type=RawSwitchedShuntT))

    for line in grid.lines:
        psse_circuit.branches.append(get_psse_branch(branch=line,
                                                     bus_dict=counter.psse_numbers_dict,
                                                     ckt=counter.get_ckt(branch=line),
                                                     version=version,
                                                     raw_branch_type=RawBranchT))

    for switch in grid.get_switches():
        psse_circuit.switches.append(get_psse_switch(switch=switch,
                                                     bus_dict=counter.psse_numbers_dict,
                                                     ckt=counter.get_ckt(branch=switch),
                                                     version=version,
                                                     raw_switch_type=RawSystemSwitchingDeviceT))

    for transformer in grid.transformers2w:
        psse_circuit.transformers.append(get_psse_transformer2w(transformer=transformer,
                                                                bus_dict=counter.psse_numbers_dict,
                                                                ckt=counter.get_ckt(branch=transformer),
                                                                version=version,
                                                                raw_transformer_type=RawTransformerT))

    for transformer in grid.transformers3w:
        psse_circuit.transformers.append(get_psse_transformer3w(transformer=transformer,
                                                                bus_dict=counter.psse_numbers_dict,
                                                                version=version,
                                                                raw_transformer_type=RawTransformerT))

    for hvdc_line in grid.hvdc_lines:
        if abs(hvdc_line.Vset_f - 1.0) > 1e-9 or abs(hvdc_line.Vset_t - 1.0) > 1e-9:
            psse_circuit.vsc_dc_lines.append(get_vsc_dc_line(hvdc_line,
                                                             bus_dict=counter.psse_numbers_dict,
                                                             version=version,
                                                             raw_vsc_dc_line_type=RawVscDCLineT))
        else:
            psse_circuit.two_terminal_dc_lines.append(get_psse_two_terminal_dc_line(
                hvdc_line,
                bus_dict=counter.psse_numbers_dict,
                raw_two_terminal_dc_line_type=RawTwoTerminalDCLineT
            ))

    for upfc_device in grid.upfc_devices:
        psse_circuit.facts.append(get_psse_facts(upfc_device,
                                                 bus_dict=counter.psse_numbers_dict,
                                                 version=version,
                                                 raw_facts_type=RawFACTST))

    return psse_circuit
