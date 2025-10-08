# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType, SubObjectType


class RmsModelTemplate(EditableDevice):
    """
    This class serves to give flexible access to either a template or a custom model
    """

    __slots__ = (
        '_block',
        '_device_type')

    def __init__(self, name: str = ""):
        super().__init__(name=name,
                         idtag=None,
                         code="",
                         device_type=DeviceType.RmsModelTemplateDevice)

        self._device_type: DeviceType = DeviceType.NoDevice
        self._block: Block = Block()

        self.register('device_type', units="p.u.", tpe=DeviceType,
                      definition='Device type', editable=False, display=True)

        self.register('block', units="p.u.", tpe=SubObjectType.DaeBlockType,
                      definition='DAE block', editable=False, display=False)

    @property
    def block(self):
        """

        :return:
        """
        return self._block

    @block.setter
    def block(self, obj: Block):
        self._block = obj

    @property
    def device_type(self):
        """

        :return:
        """
        return self._device_type

    @device_type.setter
    def device_type(self, obj: DeviceType):
        self._device_type = obj
