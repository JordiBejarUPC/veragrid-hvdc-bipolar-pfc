# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# SPDX-License-Identifier: MPL-2.0
"""CIMTR1 induction generator with rotor-flux transients."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.international_standards.templates._ree_dynamic_models import (
    InductionMachineRole,
    build_induction_machine,
)

TEMPLATE_KEY: str = "cimtr1"
DISPLAY_NAME: str = "CIMTR1"
SOURCE_XML_NAME: str = "CIMTR1.public_block_equations"
WARNING_MESSAGES: tuple[str, ...] = (
    "Independent five-state induction-generator implementation from the published "
    "CIMTR1/CIM5 block equations.",
)
INPUT_NAMES: tuple[str, ...] = ("VdPu", "VqPu", "TmPu")
OUTPUT_NAMES: tuple[str, ...] = ("PGenPu", "QGenPu", "OmegaPu", "TePu")
RECOVERED_RUNTIME_FAMILY_NAMES: tuple[str, ...] = ("double_cage_induction_machine",)


def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    """Build the CIMTR1 induction-generator template.

    :param vf: Variable factory used to allocate the symbolic model variables.
    :type vf: VarFactory
    :param name: Optional instance name for the returned template.
    :type name: str | None
    :returns: Fully assembled CIMTR1 dynamic template.
    :rtype: EmtModelTemplate
    """
    # Resolve the optional name before building the model so the shared
    # induction-machine implementation always receives an explicit identity.
    template_name: str
    if name is None:
        template_name: str = DISPLAY_NAME
    else:
        template_name: str = name

    # Select the generator equations explicitly; the Enum prevents a string
    # option from silently choosing the wrong active-power sign convention.
    template: EmtModelTemplate = build_induction_machine(
        vf=vf,
        name=template_name,
        role=InductionMachineRole.GENERATOR,
    )
    return template
