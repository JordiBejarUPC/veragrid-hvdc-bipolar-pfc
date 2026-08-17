# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""VTGTPA under/overvoltage generator trip relay."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.international_standards.templates._generator_band_trip_relay import build_generator_band_trip_relay


TEMPLATE_KEY: str = "vtgtpa"
DISPLAY_NAME: str = "VTGTPA"
SOURCE_XML_NAME: str = "VTGTPA.public_model_description"
WARNING_MESSAGES: tuple[str, ...] = (
    "Independent implementation from the public VTGTPA parameter and timing description; no generated XML payload.",
)
INPUT_NAMES: tuple[str, ...] = ("UPu",)
OUTPUT_NAMES: tuple[str, ...] = ("Trip",)
RECOVERED_RUNTIME_FAMILY_NAMES: tuple[str, ...] = ("pickup_timer", "breaker_timer", "trip_latch")


def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    """Build the default 0.45/1.20 pu VTGTPA relay instance.

    :param vf: Variable factory used to allocate the relay symbols.
    :type vf: VarFactory
    :param name: Optional instance name.
    :type name: str | None
    :return: Fully assembled VTGTPA dynamic relay template.
    :rtype: EmtModelTemplate
    """
    template_name: str
    if name is None:
        template_name: str = DISPLAY_NAME
    else:
        template_name: str = name

    # Bind the voltage-specific pickup thresholds to the shared procedural
    # relay algorithm while keeping one public construction entry point.
    template: EmtModelTemplate = build_generator_band_trip_relay(
        vf=vf,
        name=template_name,
        measurement_name="UPu",
        lower_name="VL",
        upper_name="VU",
        lower_default=0.45,
        upper_default=1.2,
    )
    return template
