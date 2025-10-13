# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List, Dict

from VeraGridEngine.Devices.types import ALL_RMS_TEMPLATES_TYPE
from VeraGridEngine.enumerations import DeviceType

from VeraGridEngine.Templates.Rms.bus_rms_template import BusRmsTemplate
from VeraGridEngine.Templates.Rms.generator_rms_template import GeneratorRmsTemplate
from VeraGridEngine.Templates.Rms.line_rms_template import LineRmsTemplate
from VeraGridEngine.Templates.Rms.load_rms_template import LoadRmsTemplate

Templates: List[ALL_RMS_TEMPLATES_TYPE] = [BusRmsTemplate(), GeneratorRmsTemplate(), LineRmsTemplate(),
                                           LoadRmsTemplate()]


def get_generator_catalogue() -> tuple[List[str], Dict[str, ALL_RMS_TEMPLATES_TYPE]]:
    generator_templ_catalogue = dict()
    generator_templ_list = []
    for templ in Templates:
        if templ.device_type == DeviceType.GeneratorDevice:
            generator_templ_list.append(templ.name)
            generator_templ_catalogue[templ.name] = templ

    return generator_templ_list, generator_templ_catalogue


def get_bus_catalogue() -> tuple[List[str], Dict[str, ALL_RMS_TEMPLATES_TYPE]]:
    bus_templ_catalogue = dict()
    bus_templ_list = []
    for templ in Templates:
        if templ.device_type == DeviceType.BusDevice:
            bus_templ_list.append(templ.name)
            bus_templ_catalogue[templ.name] = templ

    return bus_templ_list, bus_templ_catalogue


def get_line_catalogue() -> tuple[List[str], Dict[str, ALL_RMS_TEMPLATES_TYPE]]:
    line_templ_catalogue = dict()
    line_templ_list = []
    for templ in Templates:
        if templ.device_type == DeviceType.LineDevice:
            line_templ_list.append(templ.name)
            line_templ_catalogue[templ.name] = templ

    return line_templ_list, line_templ_catalogue


def get_load_catalogue() -> tuple[List[str], Dict[str, ALL_RMS_TEMPLATES_TYPE]]:
    load_templ_catalogue = dict()
    load_templ_list = []
    for templ in Templates:
        if templ.device_type == DeviceType.LoadDevice:
            load_templ_list.append(templ.name)
            load_templ_catalogue[templ.name] = templ

    return load_templ_list, load_templ_catalogue
