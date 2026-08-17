# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# SPDX-License-Identifier: MPL-2.0
"""CIMW WECC induction motor."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.international_standards.templates._ree_dynamic_models import (
    InductionMachineRole,
    build_induction_machine,
)

TEMPLATE_KEY: str = "cimw"
DISPLAY_NAME: str = "CIMW"
SOURCE_XML_NAME: str = "CIMW.public_block_equations"
WARNING_MESSAGES: tuple[str, ...] = (
    "Independent five-state CIMW implementation from the published CIM5 "
    "electrical dynamics and CIMW torque law.",
)
INPUT_NAMES: tuple[str, ...] = ("VdPu", "VqPu", "TLoad0Pu")
OUTPUT_NAMES: tuple[str, ...] = ("PLoadPu", "QLoadPu", "OmegaPu", "TePu")
RECOVERED_RUNTIME_FAMILY_NAMES: tuple[str, ...] = (
    "double_cage_induction_machine",
    "speed_dependent_torque",
)


def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    """Build the CIMW induction-motor template.

    :param vf: Variable factory used to allocate the symbolic model variables.
    :type vf: VarFactory
    :param name: Optional instance name for the returned template.
    :type name: str | None
    :returns: Fully assembled CIMW dynamic template.
    :rtype: EmtModelTemplate
    """
    # Resolve the instance name before entering the shared machine equations so
    # that the returned dynamic model always has a stable public identity.
    template_name: str
    if name is None:
        template_name: str = DISPLAY_NAME
    else:
        template_name: str = name

    # Select the motor equations explicitly to activate the CIMW load-torque
    # law and its consumption-oriented active-power sign convention.
    template: EmtModelTemplate = build_induction_machine(
        vf=vf,
        name=template_name,
        role=InductionMachineRole.MOTOR,
    )
    return template
