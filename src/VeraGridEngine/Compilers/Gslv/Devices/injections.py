# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from VeraGridEngine.Devices.Injections.battery import Battery
from VeraGridEngine.Devices.Injections.controllable_shunt import ControllableShunt
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.shunt import Shunt
from VeraGridEngine.Devices.Injections.static_generator import StaticGenerator
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Compilers.Gslv.activation import (
    build_status_dict,
    pg,
)
from VeraGridEngine.Compilers.Gslv.common import apply_three_phase_load_data, apply_three_phase_shunt_data, fill_profile, fill_profile_with_array, get_single_three_phase_snapshot_index
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import IntVec
from VeraGridEngine.enumerations import ShuntControlMode
import numpy as np
from typing import (
    Dict,
    TYPE_CHECKING,
    Union,
)

if TYPE_CHECKING:
    from VeraGridEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults

def convert_load(k: int, elm: Load, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                 use_time_series: bool, time_indices: IntVec | None = None,
                 opf_results: OptimalPowerFlowResults | None = None,
                 add_three_phase_data: bool = False) -> "pg.Load":
    """
    Convert one VeraGrid load into one GSLV load.

    :param k: Load index.
    :param elm: VeraGrid load.
    :param bus_dict: Bus lookup by VeraGrid id tag.
    :param n_time: Number of exported time steps.
    :param use_time_series: Whether the export is time-series based.
    :param time_indices: Optional time-series selection.
    :param opf_results: Optional OPF results.
    :param add_three_phase_data: Export explicit three-phase fields when available.
    :return: GSLV load.
    """

    load = pg.Load(
        nt=n_time,
        bus=None if elm.bus is None else bus_dict[elm.bus.idtag],
        name=elm.name,
        idtag=elm.idtag,
        code=str(elm.code),
        G=elm.G,
        B=elm.B,
        Ir=elm.Ir,
        Ii=elm.Ii,
        P=elm.P if opf_results is None else elm.P - opf_results.load_shedding[k],
        Q=elm.Q,
        Cost=elm.Cost,
        active=elm.active,
        mttf=elm.mttf,
        mttr=elm.mttr,
        capex=elm.capex,
        opex=elm.opex,
        build_status=build_status_dict[elm.build_status],
    )

    fill_profile(gslv_profile=load.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    if opf_results is None:
        fill_profile(gslv_profile=load.P,
                     gc_profile=elm.P_prof,
                     use_time_series=use_time_series,
                     time_indices=time_indices,
                     n_time=n_time,
                     default_val=elm.P)
    else:
        fill_profile_with_array(gslv_profile=load.P,
                                arr=elm.P_prof.toarray() - opf_results.load_shedding[:, k],
                                use_time_series=use_time_series,
                                time_indices=time_indices,
                                n_time=n_time,
                                default_val=elm.P)

    fill_profile(gslv_profile=load.Q,
                 gc_profile=elm.Q_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Q)

    fill_profile(gslv_profile=load.G,
                 gc_profile=elm.G_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.G)

    fill_profile(gslv_profile=load.B,
                 gc_profile=elm.B_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.B)

    fill_profile(gslv_profile=load.Ir,
                 gc_profile=elm.Ir_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Ir)

    fill_profile(gslv_profile=load.Ii,
                 gc_profile=elm.Ii_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Ii)

    fill_profile(gslv_profile=load.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    if add_three_phase_data:
        # Native three-phase GSLV studies need the explicit per-phase payload.
        snapshot_time_index: int | None = get_single_three_phase_snapshot_index(
            use_time_series=use_time_series,
            time_indices=time_indices,
            n_time=n_time,
        )
        apply_three_phase_load_data(gslv_load=load, elm=elm, time_index=snapshot_time_index)
    else:
        pass

    return load

def add_loads(circuit: MultiCircuit,
              gslv_grid: "pg.MultiCircuit",
              bus_dict: Dict[str, "pg.Bus"],
              use_time_series: bool,
              n_time: int = 1,
              time_indices: IntVec | None = None,
              opf_results: OptimalPowerFlowResults | None = None,
              add_three_phase_data: bool = False) -> None:
    """
    Add every VeraGrid load to the target GSLV grid.

    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV circuit
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param use_time_series: compile the time series from VeraGrid? otherwise just the snapshot
    :param n_time: number of time steps
    :param time_indices:
    :param opf_results:
    :param add_three_phase_data: Export explicit three-phase fields when available.
    :return: None.
    """
    devices = circuit.get_loads()
    for k, elm in enumerate(devices):
        load = convert_load(k=k, elm=elm, bus_dict=bus_dict,
                            n_time=n_time, use_time_series=use_time_series,
                            time_indices=time_indices, opf_results=opf_results,
                            add_three_phase_data=add_three_phase_data)
        gslv_grid.add_load(load)

def convert_static_generator(elm: StaticGenerator,
                             bus_dict: Dict[str, "pg.Bus"],
                             n_time: int,
                             use_time_series: bool,
                             time_indices: IntVec | None = None, ) -> "pg.StaticGenerator":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :return:
    """

    pe_inj = pg.StaticGenerator(
        idtag=elm.idtag,
        code=str(elm.code),
        name=elm.name,
        bus=None if elm.bus is None else bus_dict[elm.bus.idtag],
        nt=n_time,
        P=elm.P,
        power_factor=elm.Pf,
        build_status=elm.build_status,
    )

    fill_profile(gslv_profile=pe_inj.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=pe_inj.P,
                 gc_profile=elm.P_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.P)

    fill_profile(gslv_profile=pe_inj.Q,
                 gc_profile=elm.Q_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Q)

    fill_profile(gslv_profile=pe_inj.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    return pe_inj

def add_static_generators(circuit: MultiCircuit, gslv_grid: "pg.MultiCircuit",
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
    devices = circuit.get_static_generators()
    for k, elm in enumerate(devices):
        pe_inj = convert_static_generator(elm=elm, bus_dict=bus_dict, n_time=n_time,
                                          use_time_series=time_series, time_indices=time_indices)
        gslv_grid.add_static_generator(pe_inj)

def convert_shunt(elm: Shunt, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                  use_time_series: bool, time_indices: IntVec | None = None,
                  add_three_phase_data: bool = False) -> "pg.Shunt":
    """
    Convert one VeraGrid shunt into one GSLV shunt.

    :param elm: VeraGrid shunt.
    :param bus_dict: Bus lookup by VeraGrid id tag.
    :param n_time: Number of exported time steps.
    :param use_time_series: Whether the export is time-series based.
    :param time_indices: Optional time-series selection.
    :param add_three_phase_data: Export explicit three-phase fields when available.
    :return: GSLV shunt.
    """
    sh = pg.Shunt(
        nt=n_time,
        bus=None if elm.bus is None else bus_dict[elm.bus.idtag],
        name=elm.name,
        idtag=elm.idtag,
        code=str(elm.code),
        G=elm.G,
        B=elm.B,
        build_status=build_status_dict[elm.build_status],
    )

    fill_profile(gslv_profile=sh.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=sh.G,
                 gc_profile=elm.G_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.G)

    fill_profile(gslv_profile=sh.B,
                 gc_profile=elm.B_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.B)

    fill_profile(gslv_profile=sh.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    if add_three_phase_data:
        snapshot_time_index: int | None = get_single_three_phase_snapshot_index(
            use_time_series=use_time_series,
            time_indices=time_indices,
            n_time=n_time,
        )
        apply_three_phase_shunt_data(gslv_shunt=sh, elm=elm, time_index=snapshot_time_index)
    else:
        pass

    return sh

def add_shunts(circuit: MultiCircuit,
               gslv_grid: "pg.MultiCircuit",
               bus_dict: Dict[str, "pg.Bus"],
               time_series: bool,
               n_time: int = 1,
               time_indices: Union[IntVec, None] = None,
               add_three_phase_data: bool = False) -> None:
    """

    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from VeraGrid? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param add_three_phase_data: Export explicit three-phase fields when available.
    :return: None.
    """
    devices = circuit.get_shunts()
    for k, elm in enumerate(devices):
        sh = convert_shunt(elm=elm, bus_dict=bus_dict, n_time=n_time,
                           use_time_series=time_series, time_indices=time_indices,
                           add_three_phase_data=add_three_phase_data)
        gslv_grid.add_shunt(sh)

def convert_controllable_shunt(elm: ControllableShunt, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                               use_time_series: bool,
                               shunt_control_mode_dict: Dict[ShuntControlMode, "pg.ShuntControlMode"],
                               time_indices: IntVec | None = None,
                               add_three_phase_data: bool = False) -> "pg.ControllableShunt":
    """
    Convert one VeraGrid controllable shunt into one GSLV controllable shunt.

    :param elm: VeraGrid controllable shunt.
    :param bus_dict: Bus lookup by VeraGrid id tag.
    :param n_time: Number of exported time steps.
    :param use_time_series: Whether the export is time-series based.
    :param shunt_control_mode_dict: Shunt-control enum translator.
    :param time_indices: Optional time-series selection.
    :param add_three_phase_data: Export explicit three-phase fields when available.
    :return: GSLV controllable shunt.
    """
    if not isinstance(elm.g_steps, np.ndarray):
        raise TypeError(f"ControllableShunt.g_steps must be np.ndarray, got {type(elm.g_steps)}")
    if not isinstance(elm.b_steps, np.ndarray):
        raise TypeError(f"ControllableShunt.b_steps must be np.ndarray, got {type(elm.b_steps)}")

    g_steps = np.asarray(elm.g_steps, dtype=float).reshape(-1)
    b_steps = np.asarray(elm.b_steps, dtype=float).reshape(-1)

    number_of_steps = max(int(g_steps.size), int(b_steps.size), 1)
    if g_steps.size == 0:
        g_steps = np.zeros(number_of_steps, dtype=float)
    elif b_steps.size not in (0, g_steps.size):
        raise ValueError(f"ControllableShunt {elm.name} has mismatched step arrays")
    else:
        pass

    if b_steps.size == 0:
        b_steps = np.zeros(number_of_steps, dtype=float)
    elif g_steps.size != b_steps.size:
        raise ValueError(f"ControllableShunt {elm.name} has mismatched step arrays")
    else:
        pass

    step = min(max(int(elm.step), 0), number_of_steps - 1)

    sh = pg.ControllableShunt(
        nt=n_time,
        bus=None if elm.bus is None else bus_dict[elm.bus.idtag],
        name=elm.name,
        idtag=elm.idtag,
        code=str(elm.code),
        number_of_steps=number_of_steps,
        step=step,
        g_per_step=0.0,
        b_per_step=0.0,
        Cost=elm.Cost,
        active=elm.active,
        G=elm.G,
        B=elm.B,
        G0=elm.G0,
        B0=elm.B0,
        vset=elm.Vset,
        vmin=elm.Vmin,
        vmax=elm.Vmax,
        mttf=elm.mttf,
        mttr=elm.mttr,
        capex=elm.capex,
        opex=elm.opex,
        control_bus=None if elm.control_bus is None else bus_dict[elm.control_bus.idtag],
        control_mode=shunt_control_mode_dict[elm.control_mode],
        build_status=build_status_dict[elm.build_status],
    )

    sh.g_steps = g_steps.tolist()
    sh.b_steps = b_steps.tolist()

    if add_three_phase_data:
        snapshot_time_index: int | None = get_single_three_phase_snapshot_index(
            use_time_series=use_time_series,
            time_indices=time_indices,
            n_time=n_time,
        )
        apply_three_phase_shunt_data(gslv_shunt=sh, elm=elm, time_index=snapshot_time_index)
    else:
        pass

    fill_profile(gslv_profile=sh.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=sh.G,
                 gc_profile=elm.G_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.G)

    fill_profile(gslv_profile=sh.B,
                 gc_profile=elm.B_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.B)

    fill_profile(gslv_profile=sh.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    fill_profile(gslv_profile=sh.Vset,
                 gc_profile=elm.Vset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset)

    return sh

def add_controllable_shunts(circuit: MultiCircuit,
                            gslv_grid: "pg.MultiCircuit",
                            bus_dict: Dict[str, "pg.Bus"],
                            time_series: bool,
                            n_time: int = 1,
                            time_indices: Union[IntVec, None] = None,
                            add_three_phase_data: bool = False) -> None:
    """

    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from VeraGrid? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param add_three_phase_data: Export explicit three-phase fields when available.
    :return: None.
    """

    shunt_control_mode_dict = {
        ShuntControlMode.Locked: pg.ShuntControlMode.Locked,
        ShuntControlMode.Continuous: pg.ShuntControlMode.Continuous,
        ShuntControlMode.Discrete: pg.ShuntControlMode.Discrete,
    }

    devices = circuit.get_controllable_shunts()
    for k, elm in enumerate(devices):
        sh = convert_controllable_shunt(elm=elm,
                                        bus_dict=bus_dict,
                                        n_time=n_time,
                                        use_time_series=time_series,
                                        time_indices=time_indices,
                                        shunt_control_mode_dict=shunt_control_mode_dict,
                                        add_three_phase_data=add_three_phase_data)
        gslv_grid.add_controllable_shunt(sh)

def convert_generator(k: int, elm: Generator, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                      use_time_series: bool, time_indices: IntVec | None = None,
                      opf_results: OptimalPowerFlowResults | None = None,
                      add_three_phase_data: bool = False) -> "pg.Generator":
    """
    Convert one VeraGrid generator into one GSLV generator.

    :param k: Generator index.
    :param elm: VeraGrid generator.
    :param bus_dict: Bus lookup by VeraGrid id tag.
    :param n_time: Number of exported time steps.
    :param use_time_series: Whether the export is time-series based.
    :param time_indices: Optional time-series selection.
    :param opf_results: Optional OPF results.
    :param add_three_phase_data: Export sequence impedances needed by three-phase studies.
    :return: GSLV generator.
    """
    generator_r0: float
    generator_x0: float
    generator_r2: float
    generator_x2: float

    if add_three_phase_data:
        generator_r0 = float(elm.R0)
        generator_x0 = float(elm.X0)
        generator_r2 = float(elm.R2)
        generator_x2 = float(elm.X2)
    else:
        generator_r0 = 1e-20
        generator_x0 = 1e-20
        generator_r2 = 1e-20
        generator_x2 = 1e-20

    gen = pg.Generator(
        nt=n_time,
        bus=None if elm.bus is None else bus_dict[elm.bus.idtag],
        name=elm.name,
        idtag=elm.idtag,
        active=elm.active,
        P=elm.P,
        Q=elm.Q,
        vset=elm.Vset,
        Pmin=elm.Pmin,
        Pmax=elm.Pmax,
        Qmin=elm.Qmin,
        Qmax=elm.Qmax,
        Snom=elm.Snom,
        is_controlled=elm.is_controlled,
        enabled_dispatch=elm.enabled_dispatch,  # TODO: pass to profile
        q_points=elm.q_curve.get_data().tolist(),
        use_reactive_power_curve=elm.use_reactive_power_curve,
        r0=generator_r0,
        x0=generator_x0,
        r2=generator_r2,
        x2=generator_x2,
    )

    fill_profile(gslv_profile=gen.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    if opf_results is None:
        fill_profile(gslv_profile=gen.P,
                     gc_profile=elm.P_prof,
                     use_time_series=use_time_series,
                     time_indices=time_indices,
                     n_time=n_time,
                     default_val=elm.P)
    else:
        fill_profile_with_array(gslv_profile=gen.P,
                                arr=opf_results.generator_power[:, k] - opf_results.generator_shedding[:, k],
                                use_time_series=use_time_series,
                                time_indices=time_indices,
                                n_time=n_time,
                                default_val=elm.P)

    fill_profile(gslv_profile=gen.Q,
                 gc_profile=elm.Q_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Q)

    fill_profile(gslv_profile=gen.Vset,
                 gc_profile=elm.Vset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset)

    fill_profile(gslv_profile=gen.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    fill_profile(gslv_profile=gen.Cost0,
                 gc_profile=elm.Cost0_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost0)

    fill_profile(gslv_profile=gen.Cost2,
                 gc_profile=elm.Cost2_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost2)

    return gen

def add_generators(circuit: MultiCircuit,
                   gslv_grid: "pg.MultiCircuit",
                   bus_dict: Dict[str, "pg.Bus"],
                   time_series: bool,
                   n_time: int = 1,
                   time_indices: Union[IntVec, None] = None,
                   opf_results: Union[None, OptimalPowerFlowResults] = None,
                   add_three_phase_data: bool = False) -> None:
    """

    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from VeraGrid? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param opf_results: OptimalPowerFlowResults (optional)
    :param add_three_phase_data: Export sequence impedances needed by three-phase studies.
    :return: None.
    """
    devices = circuit.get_generators()

    for k, elm in enumerate(devices):
        gen = convert_generator(k=k, elm=elm, bus_dict=bus_dict,
                                n_time=n_time, use_time_series=time_series,
                                time_indices=time_indices, opf_results=opf_results,
                                add_three_phase_data=add_three_phase_data)

        gslv_grid.add_generator(gen)

def convert_battery(k: int, elm: Battery, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                    use_time_series: bool, time_indices: IntVec | None = None,
                    opf_results: OptimalPowerFlowResults | None = None,
                    add_three_phase_data: bool = False) -> "pg.Battery":
    """
    Convert one VeraGrid battery into one GSLV battery.

    :param k: Battery index.
    :param elm: VeraGrid battery.
    :param bus_dict: Bus lookup by VeraGrid id tag.
    :param n_time: Number of exported time steps.
    :param use_time_series: Whether the export is time-series based.
    :param time_indices: Optional time-series selection.
    :param opf_results: Optional OPF results.
    :param add_three_phase_data: Export sequence impedances needed by three-phase studies.
    :return: GSLV battery.
    """
    battery_r0: float
    battery_x0: float
    battery_r2: float
    battery_x2: float

    if add_three_phase_data:
        battery_r0 = float(elm.R0)
        battery_x0 = float(elm.X0)
        battery_r2 = float(elm.R2)
        battery_x2 = float(elm.X2)
    else:
        battery_r0 = 1e-20
        battery_x0 = 1e-20
        battery_r2 = 1e-20
        battery_x2 = 1e-20

    gen = pg.Battery(
        nt=n_time,
        bus=None if elm.bus is None else bus_dict[elm.bus.idtag],
        name=elm.name,
        idtag=elm.idtag,
        P=elm.P,
        power_factor=elm.Pf,
        vset=elm.Vset,
        max_soc=elm.max_soc,
        min_soc=elm.min_soc,
        Qmin=elm.Qmin,
        Qmax=elm.Qmax,
        Pmin=elm.Pmin,
        Pmax=elm.Pmax,
        Snom=elm.Snom,
        Enom=elm.Enom,
        charge_efficiency=elm.charge_efficiency,
        discharge_efficiency=elm.discharge_efficiency,
        is_controlled=elm.is_controlled,
        r0=battery_r0,
        x0=battery_x0,
        r2=battery_r2,
        x2=battery_x2,
    )

    fill_profile(gslv_profile=gen.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    if opf_results is None:
        fill_profile(gslv_profile=gen.P,
                     gc_profile=elm.P_prof,
                     use_time_series=use_time_series,
                     time_indices=time_indices,
                     n_time=n_time,
                     default_val=elm.P)
    else:
        fill_profile_with_array(gslv_profile=gen.P,
                                arr=opf_results.battery_power[:, k],
                                use_time_series=use_time_series,
                                time_indices=time_indices,
                                n_time=n_time,
                                default_val=elm.P)

    fill_profile(gslv_profile=gen.Q,
                 gc_profile=elm.Q_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Q)

    fill_profile(gslv_profile=gen.Vset,
                 gc_profile=elm.Vset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset)

    fill_profile(gslv_profile=gen.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    fill_profile(gslv_profile=gen.Cost0,
                 gc_profile=elm.Cost0_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost0)

    fill_profile(gslv_profile=gen.Cost2,
                 gc_profile=elm.Cost2_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost2)

    return gen

def add_battery_data(circuit: MultiCircuit,
                     gslv_grid: "pg.MultiCircuit",
                     bus_dict: Dict[str, "pg.Bus"],
                     time_series: bool,
                     n_time: int = 1,
                     time_indices: Union[IntVec, None] = None,
                     opf_results: Union[None, OptimalPowerFlowResults] = None,
                     add_three_phase_data: bool = False) -> None:
    """

    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from VeraGrid? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param opf_results: OptimelPowerFlowResults (optional)
    :param add_three_phase_data: Export sequence impedances needed by three-phase studies.
    :return: None.
    """
    devices = circuit.get_batteries()

    for k, elm in enumerate(devices):
        batt = convert_battery(k=k, elm=elm, bus_dict=bus_dict,
                               n_time=n_time, use_time_series=time_series,
                               time_indices=time_indices, opf_results=opf_results,
                               add_three_phase_data=add_three_phase_data)

        gslv_grid.add_battery(batt)
