# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
from typing import List, Tuple, TYPE_CHECKING
from VeraGridEngine.Devices.Profiles import ProfileDevice, ProfileEnum, ProfileFloat
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import BuildStatus, PfcControlType
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.editable_device import DeviceType, GCProp
from VeraGridEngine.Devices.Parents.editable_device import get_at

if TYPE_CHECKING:
    from VeraGridEngine.Devices.types import BRANCH_TYPES


class PFC(BranchParent):
    __slots__ = (
        '_control1',
        '_control1_prof',
        '_control1_dev',
        '_control1_dev_prof',
        '_control1_val',
        '_control1_val_prof',
        '_control1_val_min',
        '_control1_val_max',
        '_bus_dc_q',
        '_bus_dc_r',
        '_bus_dc_s',
        '_x',
        '_y'
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(key='bus_dc_q', units="", tpe=DeviceType.BusDevice,
               definition='DC Q bus', editable=False),
        GCProp(key='bus_dc_r', units="", tpe=DeviceType.BusDevice,
               definition='DC R bus', editable=False),
        GCProp(key='bus_dc_s', units="", tpe=DeviceType.BusDevice,
               definition='DC S bus', editable=False),
        GCProp(key='control1', units='', tpe=PfcControlType, profile_name="control1_prof",
               definition='Control mode 1.'),
        GCProp(key='control1_dev', units="", tpe=DeviceType.BusOrBranch, profile_name="control1_dev_prof",
               definition='Controlled device, None to apply to this converter', editable=False),
        GCProp(key='control1_val', units='', tpe=float, profile_name="control1_val_prof",
               definition='Control value 1.'
                          'p.u. for voltage\n'
                          'rad for angles\n'
                          'MW for P\n'
                          'MVAr for Q'),
        GCProp(key='control1_val_min', units='', tpe=float, ),
        GCProp(key='control1_val_max', units='', tpe=float, ),
        GCProp(key='x', units='px', tpe=float, definition='x position'),
        GCProp(key='y', units='px', tpe=float, definition='y position'),
    )

    def __init__(self,
                 bus_dc_q: Bus | None = None,
                 bus_dc_r: Bus | None = None,
                 bus_dc_s: Bus | None = None,
                 name='PFC',
                 idtag: str | None = None,
                 code='',
                 active=True,
                 design_rate: float = 9999.0,
                 rate: float = 100.0,
                 mttf=0.0,
                 mttr=0.0,
                 cost=100,
                 contingency_factor=1.0,
                 protection_rating_factor: float = 1.4,
                 contingency_enabled=True,
                 monitor_loading=True,
                 capex=0.0,
                 opex=0.0,
                 build_status: BuildStatus = BuildStatus.Commissioned,

                 control1: PfcControlType = PfcControlType.Ps_pfc,
                 control1_dev: Bus | BRANCH_TYPES | None = None,
                 control1_val: float = 10.0,
                 control1_val_min: float = -9999.0,
                 control1_val_max: float = 9999.0,

                 x: float = 0.0,
                 y: float = 0.0):
        """
        Power Flow Controller (PFC)
        :param bus_dc_q: bus_dc_q
        :param bus_dc_r: bus_dc_r
        :param bus_dc_s: bus_dc_s
        :param name:
        :param idtag:
        :param code:
        :param active:
        :param design_rate: Design rate (MVA)
        :param rate:
        :param mttf:
        :param mttr:
        :param cost:
        :param contingency_factor:
        :param protection_rating_factor:
        :param contingency_enabled:
        :param monitor_loading:
        :param capex:
        :param opex:
        :param build_status:
        :param control1:
        :param x: graphical x position (px)
        :param y: graphical y position (px)
        """

        BranchParent.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=None,
                              bus_to=None,
                              active=active,
                              reducible=False,
                              rate=rate,
                              design_rate=design_rate,
                              cost=cost,
                              mttf=mttf,
                              mttr=mttr,
                              contingency_factor=contingency_factor,
                              protection_rating_factor=protection_rating_factor,
                              contingency_enabled=contingency_enabled,
                              monitor_loading=monitor_loading,
                              capex=capex,
                              opex=opex,
                              build_status=build_status,
                              temp_base=25,
                              temp_oper=25,
                              alpha=0.0033,
                              device_type=DeviceType.PfcDevice)

        self._bus_dc_q = bus_dc_q
        self._bus_dc_r = bus_dc_r
        self._bus_dc_s = bus_dc_s

        self._control1: PfcControlType = control1
        self._control1_prof: ProfileEnum = ProfileEnum(default_value=control1, enum_type=PfcControlType)
        self._control1_dev: Bus | BRANCH_TYPES | None = control1_dev
        self._control1_dev_prof: ProfileDevice = ProfileDevice(default_value=control1_dev,
                                                               device_type=DeviceType.BusOrBranch)
        self._control1_val = float(control1_val)
        self._control1_val_prof: ProfileFloat = ProfileFloat(default_value=self._control1_val)
        self._control1_val_min = float(control1_val_min)
        self._control1_val_max = float(control1_val_max)


        self.x = float(x)
        self.y = float(y)


    @property
    def bus_dc_q(self) -> Bus:
        """
        Get the PFC DC q bus
        """
        return self._bus_dc_q

    @bus_dc_q.setter
    def bus_dc_q(self, value: Bus):
        if value is None:
            self._bus_dc_q = value
        else:
            if isinstance(value, Bus):
                if value.is_dc:
                    self._bus_dc_q = value
                else:
                    raise Exception('This should be a DC bus')
            else:
                raise Exception(str(type(value)) + 'not supported to be set into a _bus_dc_q')

    @property
    def bus_dc_r(self) -> Bus:
        """
        Get the PFC DC r bus
        """
        return self._bus_dc_r

    @bus_dc_r.setter
    def bus_dc_r(self, value: Bus):
        if value is None:
            self._bus_dc_r = value
        else:
            if isinstance(value, Bus):
                if value.is_dc:
                    self._bus_dc_r = value
                else:
                    raise Exception('This should be a DC bus')
            else:
                raise Exception(str(type(value)) + 'not supported to be set into a _bus_dc_r')

    @property
    def bus_dc_s(self) -> Bus:
        """
        Get the PFC DC s bus
        """
        return self._bus_dc_s

    @bus_dc_s.setter
    def bus_dc_s(self, value: Bus):
        if value is None:
            self._bus_dc_s = value
        else:
            if isinstance(value, Bus):
                if value.is_dc:
                    self._bus_dc_s = value
                else:
                    raise Exception('This should be a DC bus')
            else:
                raise Exception(str(type(value)) + 'not supported to be set into a _bus_dc_s')

    @property
    def control1(self):
        """

        :return:
        """
        return self._control1

    @control1.setter
    def control1(self, value: PfcControlType):
        self._control1 = value

    @property
    def control1_prof(self) -> ProfileEnum:
        """
        Cost profile
        :return: Profile
        """
        return self._control1_prof

    @control1_prof.setter
    def control1_prof(self, val: ProfileEnum | np.ndarray):
        if isinstance(val, ProfileEnum):
            self._control1_prof = val
        elif isinstance(val, np.ndarray):
            self._control1_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a profile')

    def get_control1_at(self, t: int | None) -> PfcControlType:
        """
        :param t:
        :return:
        """
        return get_at(self.control1, self.control1_prof, t)

    @property
    def control1_val(self):
        """

        :return:
        """
        return self._control1_val

    @control1_val.setter
    def control1_val(self, value: float):
        value=float(value)
        self._control1_val = value

    @property
    def control1_val_prof(self) -> ProfileFloat:
        """
        Cost profile
        :return: Profile
        """
        return self._control1_val_prof

    @control1_val_prof.setter
    def control1_val_prof(self, val: ProfileFloat | np.ndarray):
        if isinstance(val, ProfileFloat):
            self._control1_val_prof = val
        elif isinstance(val, np.ndarray):
            self._control1_val_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a profile')

    def get_control1_val_at(self, t: int | None) -> float:
        """
        :param t:
        :return:
        """
        return get_at(self.control1_val, self.control1_val_prof, t)

    @property
    def control1_val_min(self) -> float:
        """
        Get ``control1_val_min``.

        :return: float
        """
        return self._control1_val_min

    @control1_val_min.setter
    def control1_val_min(self, val: float) -> None:
        """
        Set ``control1_val_min``.

        :param val: Value to assign.
        :return: None
        """
        self._control1_val_min = float(val)

    @property
    def control1_val_max(self) -> float:
        """
        Get ``control1_val_max``.

        :return: float
        """
        return self._control1_val_max

    @control1_val_max.setter
    def control1_val_max(self, val: float) -> None:
        """
        Set ``control1_val_max``.

        :param val: Value to assign.
        :return: None
        """
        self._control1_val_max = float(val)

    @property
    def control1_dev(self):
        """

        :return:
        """
        return self._control1_dev

    @control1_dev.setter
    def control1_dev(self, value: Bus | BranchParent | None = None):
        self._control1_dev = value

    @property
    def control1_dev_prof(self) -> ProfileDevice:
        """
        Cost profile
        :return: Profile
        """
        return self._control1_dev_prof

    @control1_dev_prof.setter
    def control1_dev_prof(self, val: ProfileDevice | np.ndarray):
        if isinstance(val, ProfileDevice):
            self._control1_dev_prof = val
        elif isinstance(val, np.ndarray):
            self._control1_dev_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a profile')

    def get_control1_dev_at(self, t: int | None) -> Bus | BranchParent | None:
        """
        :param t:
        :return:
        """
        return get_at(self.control1_dev, self.control1_dev_prof, t)

    def get_coordinates(self) -> List[Tuple[float, float]]:
        """
        Get the line defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]


    def plot_profiles(self, time_series=None, my_index=0, show_fig=True):
        """
        Plot the time series results of this object
        :param time_series: TimeSeries Instance
        :param my_index: index of this object in the simulation
        :param show_fig: Show the figure?
        """

        if time_series is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212, sharex=ax_1)

            x = time_series.results.time_array

            # loading
            y = time_series.results.loading.real * 100.0
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = np.abs(time_series.results.losses)
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_2.set_title('Losses', fontsize=14)
            ax_2.set_ylabel('Losses [MVA]', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

        if show_fig:
            plt.show()

    def is_3term(self):
        """
        Is this a 3-terminal PFC?
        """
        return self._bus_dc_q is not None and self._bus_dc_r is not None and self._bus_dc_s is not None

    @property
    def x(self) -> float:
        """
        Get ``x``.

        :return: float
        """
        return self._x

    @x.setter
    def x(self, val: float) -> None:
        """
        Set ``x``.

        :param val: Value to assign.
        :return: None
        """
        self._x = float(val)

    @property
    def y(self) -> float:
        """
        Get ``y``.

        :return: float
        """
        return self._y

    @y.setter
    def y(self, val: float) -> None:
        """
        Set ``y``.

        :param val: Value to assign.
        :return: None
        """
        self._y = float(val)

