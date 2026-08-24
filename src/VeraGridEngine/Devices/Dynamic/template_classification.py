# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DynamicTemplateCategory, VarPowerFlowReferenceType


def block_declares_physical_device_contract(block: Block) -> bool:
    """Return whether a template root declares a physical network boundary.

    A physical template must be bindable to one network object. Native and
    GUI-authored templates express that through power-flow references, while
    imported RMS equipment may use typed terminal-power contributions. Both
    representations belong to the canonical block and are source-independent.

    :param block: Reusable template root block.
    :return: Whether the block can represent one complete physical device.
    """
    if len(block.dynamic_model_contract.rms_terminal_power_contributions) > 0:
        return True
    else:
        pass

    if len(block.external_mapping) > 0:
        return True
    else:
        pass

    interface_var: Var
    interface_var_reference: VarPowerFlowReferenceType | None
    for interface_var in block.in_vars:
        interface_var_reference = interface_var.ref
        if (
                interface_var_reference is not None
                and interface_var_reference is not VarPowerFlowReferenceType.NOTHING
        ):
            return True
        else:
            pass
    for interface_var in block.out_vars:
        interface_var_reference = interface_var.ref
        if (
                interface_var_reference is not None
                and interface_var_reference is not VarPowerFlowReferenceType.NOTHING
        ):
            return True
        else:
            pass
    return False


def classify_dynamic_template_block(block: Block) -> DynamicTemplateCategory:
    """Classify a reusable model from its canonical typed contracts.

    Physical-device identity takes precedence because a complete imported
    device may also own local measurement children. A standalone measurement
    is recognized through its immutable physical-measurement point. Every
    remaining template is an internal control or computational component.

    :param block: Reusable template root block.
    :return: Typed template category.
    """
    if block_declares_physical_device_contract(block=block):
        return DynamicTemplateCategory.DEVICE
    else:
        pass

    if block_declares_physical_measurement_contract(block=block):
        return DynamicTemplateCategory.MEASUREMENT
    else:
        pass
    return DynamicTemplateCategory.COMPONENT


def block_declares_physical_measurement_contract(block: Block) -> bool:
    """Return whether a block tree contains a physical measurement contract.

    The walk examines the canonical tree directly so classification does not
    allocate a flattened block collection. It stops at the first declared
    measurement point because one point is sufficient to classify the reusable
    template as a measurement.

    :param block: Reusable template root or child block.
    :return: Whether the block tree declares a physical measurement point.
    """
    # Check the current node before descending so shallow contracts finish in
    # constant work and do not inspect unrelated control descendants.
    if block.dynamic_model_contract.rms_physical_measurement_point is not None:
        return True
    else:
        pass

    # Walk existing children without constructing Blocks, Vars, or an
    # intermediate flattened representation of the model tree.
    child_block: Block
    for child_block in block.children:
        if block_declares_physical_measurement_contract(block=child_block):
            return True
        else:
            pass
    return False
