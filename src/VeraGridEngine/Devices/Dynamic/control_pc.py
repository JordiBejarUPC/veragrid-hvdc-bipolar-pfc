# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Union
from VeraGridEngine.enumerations import BuildStatus, DeviceType
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice


class ControlPc(DynamicDevice):
    """
    This class serves as a place where to put global controls
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 build_status: BuildStatus ):
        """

        :param name: name of the branch
        :param idtag: UUID code
        :param code: secondary id
        :param build_status: Branch build status. Used in expansion planning.
        :param device_type: device_type (passed on)
        """

        DynamicDevice.__init__(self,
                               name=name,
                               idtag=idtag,
                               code=code,
                               device_type=DeviceType.ControlPc,
                               build_status=build_status)
