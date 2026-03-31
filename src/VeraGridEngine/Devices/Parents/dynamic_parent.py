# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import Tuple
from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice, GCProp
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.enumerations import DeviceType, BuildStatus, SubObjectType
from VeraGridEngine.Utils.Symbolic.symbolic_io import duplicate_block


class DynamicDevice(PhysicalDevice):
    """
    Parent class for devices with dynamic models
    """
    __slots__ = (
        '_rms_var_factory',
        '_emt_var_factory',
        '_rms_model',
        '_emt_model',
        '_rms_template',
        '_emt_template',
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(key='rms_model', units='', tpe=SubObjectType.DaeBlockType,
               definition='RMS dynamic model', display=False),
        GCProp(key='emt_model', units='', tpe=SubObjectType.DaeBlockType,
               definition='EMT dynamic model', display=False),
        GCProp(key='rms_template', units='', tpe=DeviceType.RmsModelTemplateDevice,
               definition='RMS template used', display=True),
        GCProp(key='emt_template', units='', tpe=DeviceType.EmtModelTemplateDevice,
               definition='Emt template used', display=True),
    )

    def __init__(self,
                 name: str,
                 idtag: str | None,
                 code: str,
                 device_type: DeviceType,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """

        :param name:
        :param idtag:
        :param code:
        :param device_type:
        :param build_status:
        """
        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type,
                                build_status=build_status)

        self._rms_var_factory: VarFactory | None = None
        self._emt_var_factory: VarFactory | None = None

        self._rms_model: Block = Block()
        self._rms_template: RmsModelTemplate | None = None

        self._emt_model: Block = Block()
        self._emt_template: EmtModelTemplate | None = None

    def set_rms_var_factory(self, val: VarFactory):
        """
        Set the var factory pointer
        :param val: VarFactory
        """
        if isinstance(val, VarFactory):
            self._rms_var_factory = val
        else:
            raise ValueError(f"VarFactory cannot accept {val}")

    def set_emt_var_factory(self, val: VarFactory):
        """
        Set the var factory pointer
        :param val: VarFactory
        """
        if isinstance(val, VarFactory):
            self._emt_var_factory = val
        else:
            raise ValueError(f"VarFactory cannot accept {val}")

    @property
    def rms_model(self) -> Block:
        """
        Get the RMS model
        """
        return self._rms_model

    @rms_model.setter
    def rms_model(self, val: Block):
        if isinstance(val, Block):
            self._rms_model = val
        else:
            raise ValueError(f"RMS model cannot accept {val}")

    @property
    def emt_model(self) -> Block:
        """
        Get the EMT model
        """
        return self._emt_model

    @emt_model.setter
    def emt_model(self, val: Block):
        if isinstance(val, Block):
            self._emt_model = val
        else:
            raise ValueError(f"EMT model cannot accept {val}")

    @property
    def rms_template(self) -> RmsModelTemplate | None:
        """
        Get the RMS model
        """
        return self._rms_template

    @rms_template.setter
    def rms_template(self, val: RmsModelTemplate):
        if isinstance(val, RmsModelTemplate):
            self._rms_template = val

            if self.auto_update_enabled:
                val.block.unify_blocks()
                # self.rms_model = duplicate_block(val.block, self._rms_var_factory)
                self.rms_model = val.block
        elif val is None:
            self._rms_template = None
        else:
            raise ValueError(f"RMS template cannot accept {val}")

    @property
    def emt_template(self) -> EmtModelTemplate | None:
        """
        Get the EMT template
        """
        return self._emt_template

    @emt_template.setter
    def emt_template(self, val: EmtModelTemplate):
        if isinstance(val, EmtModelTemplate):
            self._emt_template = val

            if self.auto_update_enabled:
                self.emt_model = duplicate_block(val.block, self._emt_var_factory)
        elif val is None:
            self._emt_template = None
        else:
            raise ValueError(f"EMT template cannot accept {val}")
