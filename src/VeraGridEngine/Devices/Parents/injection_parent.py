# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Union, List, TYPE_CHECKING, Tuple
import numpy as np

from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Devices.Associations.association import Associations
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import BuildStatus, DeviceType, SubObjectType, ShuntConnectionType
from VeraGridEngine.basic_structures import CxVec
from VeraGridEngine.Devices.profile import Profile
from VeraGridEngine.Devices.Aggregation.facility import Facility
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Parents.editable_device import get_at, GCProp

if TYPE_CHECKING:
    from VeraGridEngine.Devices.Associations.technology import Technology
    from VeraGridEngine.Devices.types import ALL_DEV_TYPES


class InjectionParent(PhysicalDevice):
    """
    Parent class for Injections
    """

    __slots__ = (
        '_bus',
        'active',
        '_active_prof',
        'mttf',
        'mttr',
        'Cost',
        '_Cost_prof',
        'capex',
        'opex',
        'facility',
        'technologies',
        'scalable',
        'shift_key',
        'longitude',
        'latitude',
        '_shift_key_prof',
        '_use_kw',
        'bus_pos',
        '_conn',
        '_rms_model',
        '_emt_model',
        '_rms_template',
        '_emt_template',
        'color'
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(key='bus', units='', tpe=DeviceType.BusDevice, definition='Connection bus', editable=False),
        GCProp(key='active', units='', tpe=bool, definition='Is the load active?', profile_name='active_prof'),
        GCProp(key='color', units='', tpe=str, definition='Color to paint the element in the map diagram',
               is_color=True),
        GCProp(key='mttf', units='h', tpe=float, definition='Mean time to failure'),
        GCProp(key='mttr', units='h', tpe=float, definition='Mean time to recovery'),
        GCProp(key='capex', units='e/MW', tpe=float,
               definition='Cost of investment. Used in expansion planning.'),
        GCProp(key='opex', units='e/MWh', tpe=float, definition='Cost of operation. Used in expansion planning.'),
        GCProp(key='Cost', units='e/MWh', tpe=float, definition='Cost of not served energy. Used in OPF.',
               profile_name='Cost_prof'),
        GCProp(key='facility', units='', tpe=DeviceType.FacilityDevice,
               definition='Facility where this is located', editable=True),
        GCProp(key='technologies', units='p.u.', tpe=SubObjectType.Associations,
               definition='Technologies associations to injections', display=False),
        GCProp(key='scalable', units='', tpe=bool, definition='Is the injection scalable?'),
        GCProp(key='shift_key', units='', tpe=float, definition='Shift key for net transfer capacity',
               profile_name="shift_key_prof"),
        GCProp(key='longitude', units='deg', tpe=float,
               definition='longitude of the injection.', profile_name=''),
        GCProp(key='latitude', units='deg', tpe=float,
               definition='latitude of the injection.', profile_name=''),
        GCProp(key='use_kw', units='', tpe=bool, definition='Consider the injections in kW and kVAr?'),
        GCProp(key='conn', units='', tpe=ShuntConnectionType,
               definition='Connection type for 3-phase studies'),
        GCProp(key='rms_model', units='', tpe=SubObjectType.DynamicModelHostType,
               definition='RMS dynamic model', display=False),
        GCProp(key='emt_model', units='', tpe=SubObjectType.DaeBlockType,
               definition='EMT dynamic model', display=False),
        GCProp(key='rms_template', units='', tpe=DeviceType.RmsModelTemplateDevice,
               definition='RMS template used', display=True),
        GCProp(key='emt_template', units='', tpe=DeviceType.EmtModelTemplateDevice,
               definition='Emt template used', display=True),
        GCProp(key='bus_pos', units='', tpe=int, definition='Aid to locate devices on a busbar',
               display=False),
    )

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus: Union[Bus, None],
                 active: bool,
                 Cost: float,
                 mttf: float,
                 mttr: float,
                 capex: float,
                 opex: float,
                 build_status: BuildStatus,
                 device_type: DeviceType,
                 longitude=0.0,
                 latitude=0.0,
                 color: str | None = None):
        """
        InjectionTemplate
        :param name: Name of the device
        :param idtag: unique id of the device (if None or "" a new one is generated)
        :param code: secondary code for compatibility
        :param bus: snapshot bus object
        :param active:active state
        :param Cost: cost associated with various actions (dispatch or shedding)
        :param mttf: mean time to failure (h)
        :param mttr: mean time to recovery (h)
        :param capex: capital expenditures (investment cost)
        :param opex: operational expenditures (maintainance cost)
        :param build_status: BuildStatus
        :param device_type: DeviceType
        """

        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type,
                                build_status=build_status)

        self._bus = bus

        self.active = bool(active)
        self._active_prof = Profile(default_value=self.active, data_type=bool)

        self.mttf = mttf

        self.mttr = mttr

        self.Cost = float(Cost)

        self._Cost_prof = Profile(default_value=self.Cost, data_type=float)

        self.capex = capex

        self.opex = opex

        self.facility: Facility | None = None

        self.technologies: Associations = Associations(device_type=DeviceType.Technology)

        self.scalable: bool = True

        self.shift_key: float = 1.0
        self._shift_key_prof = Profile(default_value=self.shift_key, data_type=float)

        self.longitude = float(longitude)
        self.latitude = float(latitude)

        self._use_kw: bool = False

        self._conn: ShuntConnectionType = ShuntConnectionType.GroundedStar

        self._rms_model: Block = Block()
        self._rms_template: RmsModelTemplate | None = None

        self._emt_model: Block = Block()
        self._emt_template: EmtModelTemplate | None = None

        self.bus_pos: int = 0

        self.color = color if color is not None else "#909090"  # light gray

    @property
    def bus(self) -> Bus:
        """
        Bus
        :return: Bus
        """
        return self._bus

    @bus.setter
    def bus(self, val: Bus):
        if val is None:
            self._bus = val
        else:
            if isinstance(val, Bus):
                self._bus = val
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a bus')

    @property
    def active_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._active_prof

    @active_prof.setter
    def active_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._active_prof = val
        elif isinstance(val, np.ndarray):
            self._active_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a active_prof')

    def get_active_at(self, t: int | None) -> float:
        """
        :param t:
        :return:
        """
        return get_at(self.active, self.active_prof, t)

    @property
    def Cost_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Cost_prof

    @Cost_prof.setter
    def Cost_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Cost_prof = val
        elif isinstance(val, np.ndarray):
            self._Cost_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Cost_prof')

    def get_Cost_at(self, t: int | None) -> float:
        """
        :param t:
        :return:
        """
        return get_at(self.Cost, self.Cost_prof, t)

    @property
    def shift_key_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._shift_key_prof

    @shift_key_prof.setter
    def shift_key_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._shift_key_prof = val
        elif isinstance(val, np.ndarray):
            self._shift_key_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a shift_key_prof')

    def get_shift_key_at(self, t: int | None) -> float:
        """
        :param t:
        :return:
        """
        return get_at(self.shift_key, self.shift_key_prof, t)

    @property
    def use_kw(self):
        """

        :return:
        """
        return self._use_kw

    @use_kw.setter
    def use_kw(self, val: bool):
        """
        Setter
        :param val: bool
        """
        if self.auto_update_enabled:
            if val != self._use_kw:
                self._use_kw = val
            else:
                pass
        else:
            self._use_kw = val

    @property
    def conn(self) -> ShuntConnectionType:
        """

        :return:
        """
        return self._conn

    @conn.setter
    def conn(self, val: ShuntConnectionType):
        if isinstance(val, ShuntConnectionType):
            self._conn = val

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
                self.rms_model = val.block.copy()
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
                self.emt_model = val.block.copy()
        else:
            raise ValueError(f"EMT template cannot accept {val}")

    def get_S_with_sign(self) -> complex:
        """

        :return:
        """
        return complex(0.0, 0.0)

    def get_Sprof_with_sign(self) -> CxVec:
        """

        :return:
        """
        return np.zeros(self.active_prof.size(), dtype=complex)

    def associate_technology(self, tech: Technology, val=1.0):
        """
        Associate a technology with this injection device
        :param tech:
        :param val:
        :return:
        """
        self.technologies.add_object(tech, val=val)

    @property
    def tech_list(self) -> List[ALL_DEV_TYPES]:
        """
        Bus
        :return: Bus
        """
        return self.technologies.to_list()

    def get_bus_pos(self, bus: Bus | None = None) -> int:
        """
        Get the bus position
        NOTE: don't remove the void bus argument
        :param bus: Bus
        :return: bus_pos
        """
        return self.bus_pos

    def try_to_find_coordinates(self) -> Tuple[float, float]:
        """
        Get the latitude and
        :return: longitude, latitude
        """
        if self.latitude == 0.0 and self.longitude == 0.0:
            lon, lat = self.bus.get_coordinates()

            if lon == 0.0 and lat == 0.0:
                lon, lat = self.bus.try_to_find_coordinates()

                return lon, lat
            else:
                return lon, lat
        else:
            return self.longitude, self.latitude

    def color_by_main_technology(self):
        """
        Set the color of the dominant technology
        """
        mx = 0.0
        col = self.color
        for _, val in self.technologies.data.items():
            if val.value > mx:
                col = val.api_object.color
        self.color = col

    def color_by_main_owner(self):
        """
        Set the color of the dominant owner
        """
        mx = 0.0
        col = self.color
        for _, val in self.owners.data.items():
            if val.value > mx:
                col = val.api_object.color
        self.color = col
