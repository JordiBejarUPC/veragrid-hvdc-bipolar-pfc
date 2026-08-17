# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# SPDX-License-Identifier: MPL-2.0
"""IEEL IEEE voltage- and frequency-dependent load."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.international_standards.templates._ree_dynamic_models import build_ieel

TEMPLATE_KEY: str = "ieel"
DISPLAY_NAME: str = "IEEL"
SOURCE_XML_NAME: str = "IEEL.public_equations"
WARNING_MESSAGES: tuple[str, ...] = (
    "Independent implementation of the published IEEL voltage-exponent and frequency-factor equations.",
)
INPUT_NAMES: tuple[str, ...] = ("VPu", "FPu", "P0Pu", "Q0Pu")
OUTPUT_NAMES: tuple[str, ...] = ("PLoadPu", "QLoadPu")
RECOVERED_RUNTIME_FAMILY_NAMES: tuple[str, ...] = ("exponential_load", "frequency_dependent_load")


def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    """Build the maintainable IEEL runtime template.

    :param vf: Variable factory used to allocate the symbolic model variables.
    :type vf: VarFactory
    :param name: Optional instance name.
    :type name: str | None
    :return: Fully assembled IEEL dynamic template.
    :rtype: EmtModelTemplate
    """
    template_name: str
    if name is None:
        template_name: str = DISPLAY_NAME
    else:
        template_name: str = name
    template: EmtModelTemplate = build_ieel(vf=vf, name=template_name)
    return template
