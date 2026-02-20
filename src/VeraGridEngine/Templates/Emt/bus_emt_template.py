# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Templates.Emt.emt_model_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


def get_bus_emt_template(var_factory: VarFactory) -> EmtModelTemplate:
    """
    Get the EMT template of a bus
    :return: EmtModelTemplate
    """
    templ = EmtModelTemplate()

    v_a = var_factory.add_var("v_a")
    v_b = var_factory.add_var("v_b")
    v_c = var_factory.add_var("v_c")

    templ.block = Block(
        alter_params=[v_a, v_b, v_c],
        out_vars=[v_a, v_b, v_c],
    )

    return templ
