# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import List
import VeraGridEngine.Templates.Emt as emt_templates


class ParamDef:

    def __init__(self, name, tpe):
        pass


class TemplateDefinition:

    def __init__(self, fn, params: List[ParamDef]):
        self.fn = fn
        self.params = params


# CATALOGUE = [
#     TemplateDefinition(
#         fn=emt_templates.get_arbitrary_waveform_voltage_source_emt_template,
#         params=[
#             ParamDef("vf", VarFactory),
#             ParamDef("phN", bool),
#             ParamDef("phA", bool),
#             ParamDef("phB", bool),
#             ParamDef("phC", bool),
#             ParamDef("time_points", Sequence[float]),
#             ParamDef("value_points", Sequence[float]),
#             ParamDef("source_conductance_value", float),
#         ]
#     )
# ]
