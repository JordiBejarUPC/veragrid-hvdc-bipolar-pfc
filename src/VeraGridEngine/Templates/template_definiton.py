# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import inspect
from typing import List, Callable
import VeraGridEngine.Templates.Emt as emt_templates


class TemplateDefinition:

    def __init__(self, fn: Callable):
        self.fn = fn

        # 2. Extract the signature
        self.sig = inspect.signature(fn)

    def print(self):
        """
        Print each argument name and its type
        :return:
        """
        for name, param in self.sig.parameters.items():
            print(f"Argument: {name}")
            print(f"  - Type Hint: {param.annotation}")
            print(f"  - Default Value: {param.default}")
            print(f"  - Kind: {param.kind}\n")


def get_emt_functions_catalogue() -> List[TemplateDefinition]:
    """
    Generate the list of template functions
    :return:
    """
    return [
        TemplateDefinition(fn=emt_templates.get_arbitrary_waveform_voltage_source_emt_template, )
    ]
