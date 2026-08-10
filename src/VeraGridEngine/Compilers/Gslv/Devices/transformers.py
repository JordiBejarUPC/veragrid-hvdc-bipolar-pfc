# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from VeraGridEngine.Devices.Aggregation.branch_group import BranchGroup
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Branches.transformer3w import Transformer3W
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Compilers.Gslv.activation import (
    pg,
    tap_module_control_mode_dict,
    tap_phase_control_mode_dict,
    winding_type_dict,
    windings_connection_dict,
)
from VeraGridEngine.Compilers.Gslv.common import fill_profile
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import IntVec
from typing import (
    Dict,
    Union,
)


def convert_transformer(elm: Transformer2W,
                        bus_dict: Dict[str, "pg.Bus"],
                        branch_groups_dict: Dict[BranchGroup, "pg.BranchGroup"],
                        n_time: int,
                        use_time_series: bool, time_indices: IntVec | None,
                        override_controls: bool,
                        add_three_phase_data: bool = False) -> "pg.Transformer2W":
    """
    Convert one VeraGrid two-winding transformer into one GSLV transformer.

    :param elm: VeraGrid transformer.
    :param bus_dict: Bus lookup by VeraGrid id tag.
    :param branch_groups_dict: Branch-group lookup.
    :param n_time: Number of exported time steps.
    :param use_time_series: Whether the export is time-series based.
    :param time_indices: Optional time-series selection.
    :param override_controls: Whether transformer control modes must be forced to fixed.
    :param add_three_phase_data: Export sequence parameters and winding connections.
    :return: GSLV transformer.
    """
    transformer_r0: float
    transformer_x0: float
    transformer_g0: float
    transformer_b0: float
    transformer_r2: float
    transformer_x2: float
    transformer_g2: float
    transformer_b2: float
    transformer_conn: "pg.WindingsConnection"

    if add_three_phase_data:
        transformer_r0 = float(elm.R0)
        transformer_x0 = float(elm.X0)
        transformer_g0 = float(elm.G0)
        transformer_b0 = float(elm.B0)
        transformer_r2 = float(elm.R2)
        transformer_x2 = float(elm.X2)
        transformer_g2 = float(elm.G2)
        transformer_b2 = float(elm.B2)
        transformer_conn = windings_connection_dict[elm.conn]
    else:
        transformer_r0 = 1e-20
        transformer_x0 = 1e-20
        transformer_g0 = 1e-20
        transformer_b0 = 1e-20
        transformer_r2 = 1e-20
        transformer_x2 = 1e-20
        transformer_g2 = 1e-20
        transformer_b2 = 1e-20
        transformer_conn = pg.WindingsConnection.GG

    branch_rate: float = elm.rate if elm.rate > 0 else 9999
    tr2 = pg.Transformer2W(n_time, branch_rate, True)

    # The installed wrapper only accepts the short constructor overload, so the
    # remaining constructor fields are copied through the exposed C++ properties.
    tr2.set_idtag(elm.idtag)
    tr2.set_code(str(elm.code))
    tr2.set_name(elm.name)
    tr2.bus_from = bus_dict[elm.bus_from.idtag]
    tr2.bus_to = bus_dict[elm.bus_to.idtag]
    tr2.HV = elm.HV
    tr2.LV = elm.LV
    tr2.nominal_power = elm.Sn
    tr2.copper_losses = elm.Pcu
    tr2.iron_losses = elm.Pfe
    tr2.no_load_current = elm.I0
    tr2.short_circuit_voltage = elm.Vsc
    tr2.R = elm.R
    tr2.X = elm.X
    tr2.G = elm.G
    tr2.B = elm.B
    tr2.R0 = transformer_r0
    tr2.X0 = transformer_x0
    tr2.G0 = transformer_g0
    tr2.B0 = transformer_b0
    tr2.R2 = transformer_r2
    tr2.X2 = transformer_x2
    tr2.G2 = transformer_g2
    tr2.B2 = transformer_b2
    tr2.tap_module_max = elm.tap_module_max
    tr2.tap_module_min = elm.tap_module_min
    tr2.tap_phase_max = elm.tap_phase_max
    tr2.tap_phase_min = elm.tap_phase_min
    tr2.tolerance = elm.tolerance
    tr2.mttf = elm.mttf
    tr2.mttr = elm.mttr
    tr2.temp_base = elm.temp_base
    tr2.alpha = elm.alpha
    tr2.conn = transformer_conn
    tr2.protection_rating_factor = elm.protection_rating_factor
    tr2.monitor_loading = elm.monitor_loading

    if add_three_phase_data:
        tr2.conn_f = winding_type_dict[elm.conn_f]
        tr2.conn_t = winding_type_dict[elm.conn_t]
    else:
        pass

    tr2.tap_phase_min = elm.tap_phase_min
    tr2.tap_phase_max = elm.tap_phase_max
    tr2.tap_module_min = elm.tap_module_min
    tr2.tap_module_max = elm.tap_module_max

    if elm.regulation_bus is not None:
        tr2.regulation_bus = bus_dict[elm.regulation_bus.idtag]

    fill_profile(gslv_profile=tr2.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=tr2.rate,
                 gc_profile=elm.rate_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.rate)

    fill_profile(gslv_profile=tr2.contingency_factor,
                 gc_profile=elm.contingency_factor_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.contingency_factor)

    fill_profile(gslv_profile=tr2.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    fill_profile(gslv_profile=tr2.Pset,
                 gc_profile=elm.Pset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Pset)

    fill_profile(gslv_profile=tr2.Qset,
                 gc_profile=elm.Qset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Qset)

    fill_profile(gslv_profile=tr2.vset,
                 gc_profile=elm.vset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.vset)

    fill_profile(gslv_profile=tr2.temp_oper,
                 gc_profile=elm.temp_oper_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.temp_oper)

    fill_profile(gslv_profile=tr2.tap_phase,
                 gc_profile=elm.tap_phase_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.tap_phase)

    fill_profile(gslv_profile=tr2.tap_phase_control_mode,
                 gc_profile=elm.tap_phase_control_mode_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.tap_phase_control_mode)

    fill_profile(gslv_profile=tr2.tap_module,
                 gc_profile=elm.tap_module_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.tap_module)

    fill_profile(gslv_profile=tr2.tap_module_control_mode,
                 gc_profile=elm.tap_module_control_mode_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.tap_module_control_mode)

    # control vars
    if override_controls:
        tr2.tap_module_control_mode.fill(pg.TapModuleControl.fixed)
        tr2.tap_phase_control_mode.fill(pg.TapPhaseControl.fixed)
    else:
        pass

    return tr2

def add_transformers(circuit: MultiCircuit,
                     gslv_grid: "pg.MultiCircuit",
                     bus_dict: Dict[str, "pg.Bus"],
                     branch_groups_dict: Dict[BranchGroup, "pg.BranchGroup"],
                     time_series: bool,
                     n_time: int = 1,
                     time_indices: Union[IntVec, None] = None,
                     override_controls: bool = False,
                     add_three_phase_data: bool = False) -> None:
    """

    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from VeraGrid? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param branch_groups_dict: dictionary of branch grous converetd
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param override_controls: If true the controls are set to Fix
    :param add_three_phase_data: Export sequence parameters and winding connections.
    :return: None.
    """

    for i, elm in enumerate(circuit.transformers2w):
        tr2 = convert_transformer(elm=elm,
                                  bus_dict=bus_dict,
                                  branch_groups_dict=branch_groups_dict,
                                  n_time=n_time,
                                  use_time_series=time_series,
                                  time_indices=time_indices,
                                  override_controls=override_controls,
                                  add_three_phase_data=add_three_phase_data)
        gslv_grid.add_transformer(tr2)

def convert_transformer3w(elm: Transformer3W,
                          bus_dict: Dict[str, "pg.Bus"],
                          n_time: int,
                          use_time_series: bool,
                          time_indices: IntVec | None,
                          override_controls: bool) -> "pg.Transformer3W":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :param override_controls:
    :return:
    """

    tr3 = pg.Transformer3W(idtag=elm.idtag,
                           code=str(elm.code),
                           name=elm.name,
                           nt=n_time,
                           active=elm.active,
                           bus1=bus_dict[elm.bus1.idtag] if elm.bus1 else None,
                           bus2=bus_dict[elm.bus2.idtag] if elm.bus2 else None,
                           bus3=bus_dict[elm.bus3.idtag] if elm.bus3 else None,
                           V1=elm.V1,
                           V2=elm.V2,
                           V3=elm.V3,
                           r12=elm.r12, r23=elm.r23, r31=elm.r31,
                           x12=elm.x12, x23=elm.x23, x31=elm.x31,
                           rate12=elm.rate1, rate23=elm.rate2, rate31=elm.rate3)

    # this is because the central node is in the buses list already from VeraGrid
    tr3.central_node = bus_dict[elm.bus0.idtag]

    return tr3

def add_transformers3w(circuit: MultiCircuit,
                       gslv_grid: "pg.MultiCircuit",
                       bus_dict: Dict[str, "pg.Bus"],
                       time_series: bool,
                       n_time=1,
                       time_indices: Union[IntVec, None] = None,
                       override_controls=False):
    """

    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from VeraGrid? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param override_controls: If true the controls are set to Fix
    """
    for i, elm in enumerate(circuit.transformers3w):
        tr3 = convert_transformer3w(elm=elm, bus_dict=bus_dict, n_time=n_time,
                                    use_time_series=time_series, time_indices=time_indices,
                                    override_controls=override_controls)

        # because the central bus was added already, do not add it here
        gslv_grid.add_transformer_3w(tr3)
