# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Substation.substation import Substation
from VeraGridEngine.Devices.Branches.hvdc_line import HvdcLine
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Compilers.Gslv.activation import (
    build_status_dict,
    converter_control_type_dict,
    hvdc_control_mode_dict,
    pg,
)
from VeraGridEngine.Compilers.Gslv.common import fill_profile
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import IntVec
from typing import (
    Dict,
    Union,
)

def convert_vsc(elm: VSC, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                use_time_series: bool, time_indices: IntVec | None) -> "pg.Vsc":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :return:
    """

    vsc = pg.Vsc(
        nt=n_time,
        bus_from=bus_dict[elm.bus_from.idtag],
        bus_to=bus_dict[elm.bus_to.idtag],
        name=elm.name,
        idtag=elm.idtag,
        code=str(elm.code),
        active=elm.active,
        rate=9999.0,
        kdp=elm.control1_val_droop,
        alpha1=elm.alpha1,
        alpha2=elm.alpha2,
        alpha3=elm.alpha3,
        mttf=elm.mttf,
        mttr=elm.mttr,
        overload_cost=elm.Cost,
        contingency_factor=elm.contingency_factor,
        protection_rating_factor=elm.protection_rating_factor,
        monitor_loading=elm.monitor_loading,
        capex=elm.capex,
        opex=elm.opex,
        build_status=build_status_dict[elm.build_status],
        control1=converter_control_type_dict[elm.control1],
        control2=converter_control_type_dict[elm.control2],
        control1_val=elm.control1_val,
        control2_val=elm.control2_val,
        #     TODO: extend the search
        control1_dev=bus_dict.get(elm.control1_dev, None),
        control2_dev=bus_dict.get(elm.control2_dev, None)
    )

    fill_profile(gslv_profile=vsc.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=vsc.rate,
                 gc_profile=elm.rate_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.rate)

    fill_profile(gslv_profile=vsc.contingency_factor,
                 gc_profile=elm.contingency_factor_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.contingency_factor)

    fill_profile(gslv_profile=vsc.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    return vsc

def add_vscs(circuit: MultiCircuit,
             gslv_grid: "pg.MultiCircuit",
             bus_dict: Dict[str, "pg.Bus"],
             time_series: bool,
             n_time: int = 1,
             time_indices: Union[IntVec, None] = None):
    """

    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from VeraGrid? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """
    for i, elm in enumerate(circuit.vsc_devices):
        vsc = convert_vsc(elm=elm, bus_dict=bus_dict, n_time=n_time,
                          use_time_series=time_series, time_indices=time_indices)
        gslv_grid.add_vsc(vsc)

def convert_hvdc_line(elm: HvdcLine, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                      use_time_series: bool, time_indices: IntVec | None) -> "pg.HvdcLine":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :return:
    """

    hvdc = pg.HvdcLine(
        idtag=elm.idtag,
        code=str(elm.code),
        name=elm.name,
        bus_from=bus_dict[elm.bus_from.idtag],
        bus_to=bus_dict[elm.bus_to.idtag],
        nt=n_time,
        active=elm.active,
        rate=elm.rate,
        contingency_factor=elm.contingency_factor,
        # monitor_loading=elm.monitor_loading,
        pset=elm.Pset,
        Vset_f=elm.Vset_f,
        Vset_t=elm.Vset_t,
        r=float(elm.r),
        angle_droop=elm.angle_droop,
        length=elm.length,
        min_firing_angle_f=elm.min_firing_angle_f,
        max_firing_angle_f=elm.max_firing_angle_f,
        min_firing_angle_t=elm.min_firing_angle_t,
        max_firing_angle_t=elm.max_firing_angle_t,
        control_mode=hvdc_control_mode_dict[elm.control_mode]
    )

    fill_profile(gslv_profile=hvdc.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=hvdc.Vset_f,
                 gc_profile=elm.Vset_f_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset_f)

    fill_profile(gslv_profile=hvdc.Vset_f,
                 gc_profile=elm.Vset_f_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset_f)

    fill_profile(gslv_profile=hvdc.Vset_t,
                 gc_profile=elm.Vset_t_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset_t)

    fill_profile(gslv_profile=hvdc.angle_droop,
                 gc_profile=elm.angle_droop_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.angle_droop)

    fill_profile(gslv_profile=hvdc.rate,
                 gc_profile=elm.rate_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.rate)

    fill_profile(gslv_profile=hvdc.contingency_factor,
                 gc_profile=elm.contingency_factor_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.contingency_factor)

    fill_profile(gslv_profile=hvdc.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    return hvdc

def add_hvdcs(circuit: MultiCircuit,
              gslv_grid: "pg.MultiCircuit",
              bus_dict: Dict[str, "pg.Bus"],
              time_series: bool,
              n_time=1,
              time_indices: Union[IntVec, None] = None):
    """

    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from VeraGrid? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """

    for i, elm in enumerate(circuit.hvdc_lines):
        hvdc = convert_hvdc_line(elm=elm, bus_dict=bus_dict, n_time=n_time,
                                 use_time_series=time_series, time_indices=time_indices)
        gslv_grid.add_hvdc_line(hvdc)

