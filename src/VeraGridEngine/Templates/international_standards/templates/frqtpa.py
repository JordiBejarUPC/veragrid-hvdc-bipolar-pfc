# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""FRQTPA under/overfrequency generator trip relay."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.international_standards.templates._generator_band_trip_relay import build_generator_band_trip_relay


TEMPLATE_KEY: str = "frqtpa"
DISPLAY_NAME: str = "FRQTPA"
SOURCE_XML_NAME: str = "FRQTPA.public_model_description"
WARNING_MESSAGES: tuple[str, ...] = (
    "Independent implementation from the public FRQTPA parameter and timing description; no generated XML payload.",
)
INPUT_NAMES: tuple[str, ...] = ("FHz",)
OUTPUT_NAMES: tuple[str, ...] = ("Trip",)
RECOVERED_RUNTIME_FAMILY_NAMES: tuple[str, ...] = ("pickup_timer", "breaker_timer", "trip_latch")


def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    """Build the default 57.5/61.8 Hz FRQTPA relay instance.

    :param vf: Variable factory used to allocate the relay symbols.
    :type vf: VarFactory
    :param name: Optional instance name.
    :type name: str | None
    :return: Fully assembled FRQTPA dynamic relay template.
    :rtype: EmtModelTemplate
    """
    template_name: str
    if name is None:
        template_name: str = DISPLAY_NAME
    else:
        template_name: str = name

    # Bind the frequency-specific pickup thresholds to the shared procedural
    # relay algorithm while keeping one public construction entry point.
    template: EmtModelTemplate = build_generator_band_trip_relay(
        vf=vf,
        name=template_name,
        measurement_name="FHz",
        lower_name="FL",
        upper_name="FU",
        lower_default=57.5,
        upper_default=61.8,
    )
    return template
