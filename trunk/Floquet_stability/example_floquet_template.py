# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from VeraGridEngine.Templates.Emt.emt_model_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block import Var, DiffVar, Const
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType


def get_generator_emt_template() -> EmtModelTemplate:
    """
    Get the EMT template of a generator
    :return: EmtModelTemplate
    """

    templ = EmtModelTemplate()

    # vars
    x = Var("x")
    d_x = DiffVar('d_x', base_var=x)

    theta = Var("theta")
    d_theta = DiffVar('d_theta', base_var=theta)


    # params
    freq = Var("Freq")


    templ.block = Block(
        state_eqs=[
            (-1 +0.5 * sym.sin(theta)) * x,
            2 * np.pi * freq,
        ],
        state_vars=[x, theta],  # 6

        algebraic_eqs=[ ],
        algebraic_vars=[],
    )

    templ.block.diff_vars = [d_x, d_theta]

    templ.block.external_mapping = { }

    templ.block.event_dict = {freq: Const(50.0)}


    templ.block.init_eqs = {
        theta: 0.0,
        x: ,

    }

    return templ

