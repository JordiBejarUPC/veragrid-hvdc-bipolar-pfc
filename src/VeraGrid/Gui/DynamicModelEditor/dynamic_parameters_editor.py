# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Sequence

from typing import Any
from VeraGridEngine.enumerations import DynamicSimulationMode

def open_dyn_params_editor(api_object: Any, preferred_mode: DynamicSimulationMode | None = None):
    """
    opens the dynamic parameters editor
    :param api_object:
    :type api_object:
    :param preferred_mode:
    :type preferred_mode:
    :return:
    :rtype:
    """
    if preferred_mode == "RMS":
        blk = api_object.rms_model
        
    else:
        blk = api_object.emt_model

