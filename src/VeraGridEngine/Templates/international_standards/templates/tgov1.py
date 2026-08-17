# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# SPDX-License-Identifier: MPL-2.0
"""TGOV1 two-state steam turbine governor."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.international_standards.templates._ree_dynamic_models import build_tgov1

TEMPLATE_KEY: str = "tgov1"
DISPLAY_NAME: str = "TGOV1"
SOURCE_XML_NAME: str = "TGOV1.public_block_equations"
WARNING_MESSAGES: tuple[str, ...] = (
    "Independent implementation of the published TGOV1 lag, valve limiter, lead-lag and damping equations.",
)
INPUT_NAMES: tuple[str, ...] = ("OmegaPu", "PRefPu")
OUTPUT_NAMES: tuple[str, ...] = ("PmPu", "ValvePu")
RECOVERED_RUNTIME_FAMILY_NAMES: tuple[str, ...] = ("limited_first_order", "lead_lag")


def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    """Build the maintainable TGOV1 runtime template.

    :param vf: Variable factory used to allocate the symbolic model variables.
    :type vf: VarFactory
    :param name: Optional instance name.
    :type name: str | None
    :return: Fully assembled TGOV1 dynamic template.
    :rtype: EmtModelTemplate
    """
    template_name: str
    if name is None:
        template_name: str = DISPLAY_NAME
    else:
        template_name: str = name
    template: EmtModelTemplate = build_tgov1(vf=vf, name=template_name)
    return template
