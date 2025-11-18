# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union

from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Devices.Parents.pointer_device_parent import PointerDeviceParent
from VeraGridEngine.enumerations import DeviceType, FaultType


class ShortCircuitDefinition(PointerDeviceParent):
    """
    Investment
    """
    __slots__ = (
        'fault_type',
        'active',
    )

    def __init__(self,
                 device: EditableDevice | None = None,
                 idtag: Union[str, None] = None,
                 name="Fault",
                 code='',
                 active: bool = True,
                 fault_type: FaultType = FaultType.ph3,
                 comment: str = ""):
        """
        Investment
        :param device: Some device to point at
        :param idtag: String. Element unique identifier
        :param name: String. Contingency name
        :param code: String. Contingency code name
        :param active: If true the investment activates when applied, otherwise is deactivated
        :param comment: Comment
        """

        PointerDeviceParent.__init__(self,
                                     idtag=idtag,
                                     device=device,
                                     code=code,
                                     name=name,
                                     device_type=DeviceType.ShortCircuitDefinition,
                                     comment=comment)

        self.fault_type: FaultType = fault_type
        self.active: bool = active

        self.register(key='fault_type', units='', tpe=FaultType,
                      definition='Type of short circuit')
        self.register(key='active', units='', tpe=bool,
                      definition='If true the short-circuit activates when calculated, otherwise is deactivated.')
