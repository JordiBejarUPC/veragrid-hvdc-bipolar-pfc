# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# SPDX-License-Identifier: MPL-2.0
"""GGOV1 GE general-purpose turbine governor."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.international_standards.templates._ree_dynamic_models import build_ggov1

TEMPLATE_KEY: str = "ggov1"
DISPLAY_NAME: str = "GGOV1"
SOURCE_XML_NAME: str = "GGOV1.public_block_equations"
WARNING_MESSAGES: tuple[str, ...] = (
    "Independent continuous GGOV1 implementation of the published governor, load, acceleration and "
    "temperature selectors; the optional pure transport delay Teng is exposed but not discretized as a "
    "production delay buffer.",
)
INPUT_NAMES: tuple[str, ...] = ("OmegaPu", "PePu", "PRefPu", "AccelPuPerS", "TempLimitPu")
OUTPUT_NAMES: tuple[str, ...] = ("PmPu", "ActuatorPu", "LowValueSelectPu")
RECOVERED_RUNTIME_FAMILY_NAMES: tuple[str, ...] = ("pid", "low_value_select", "rate_limiter", "lead_lag")


def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    """Build the maintainable GGOV1 runtime template.

    :param vf: Variable factory used to allocate the symbolic model variables.
    :type vf: VarFactory
    :param name: Optional instance name.
    :type name: str | None
    :return: Fully assembled GGOV1 dynamic template.
    :rtype: EmtModelTemplate
    """
    template_name: str
    if name is None:
        template_name: str = DISPLAY_NAME
    else:
        template_name: str = name
    template: EmtModelTemplate = build_ggov1(vf=vf, name=template_name)
    return template
