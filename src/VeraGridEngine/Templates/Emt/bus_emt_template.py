# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Templates.Emt.emt_model_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


def get_bus_emt_template(var_factory: VarFactory) -> EmtModelTemplate:
    """
    Get the EMT template of a bus
    :return: EmtModelTemplate
    """
    templ = EmtModelTemplate()

    v_A = var_factory.add_var("v_A")
    v_B = var_factory.add_var("v_B")
    v_C = var_factory.add_var("v_C")

    P = var_factory.add_var("P")
    Q = var_factory.add_var("Q")

    templ.block = Block(
        alter_params=[v_A, v_B, v_C],
        out_vars=[v_A, v_B, v_C],
    )

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: v_B,
        VarPowerFlowRefferenceType.v_C: v_C,
        VarPowerFlowRefferenceType.P: P,
        VarPowerFlowRefferenceType.Q: Q
    }

    return templ
