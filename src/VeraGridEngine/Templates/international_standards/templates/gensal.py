# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# SPDX-License-Identifier: MPL-2.0
"""GENSAL salient-pole synchronous generator."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.international_standards.templates._ree_dynamic_models import build_gensal

TEMPLATE_KEY: str = "gensal"
DISPLAY_NAME: str = "GENSAL"
SOURCE_XML_NAME: str = "GENSAL.OpenIPSL_public_equations"
WARNING_MESSAGES: tuple[str, ...] = (
    "Independent implementation of the published GENSAL flux-linkage equations; no generated XML payload.",
)
INPUT_NAMES: tuple[str, ...] = ("IdPu", "IqPu", "EfdPu", "PmPu")
OUTPUT_NAMES: tuple[str, ...] = ("UdPu", "UqPu", "PePu", "OmegaPu")
RECOVERED_RUNTIME_FAMILY_NAMES: tuple[str, ...] = ("synchronous_machine", "quadratic_saturation")


def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    """Build the maintainable GENSAL runtime template.

    :param vf: Variable factory used to allocate the symbolic model variables.
    :type vf: VarFactory
    :param name: Optional instance name.
    :type name: str | None
    :return: Fully assembled GENSAL dynamic template.
    :rtype: EmtModelTemplate
    """
    template_name: str
    if name is None:
        template_name: str = DISPLAY_NAME
    else:
        template_name: str = name
    template: EmtModelTemplate = build_gensal(vf=vf, name=template_name)
    return template
