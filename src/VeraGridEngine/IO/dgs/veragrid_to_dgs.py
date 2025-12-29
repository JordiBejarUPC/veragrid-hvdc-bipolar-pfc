# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Dict, List, Type, Optional, Tuple

import numpy as np

import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import *
from VeraGridEngine.enumerations import DiagramType


SQRT3 = np.sqrt(3)


def convert_bus(bus: dev.Bus, new_id: str, t: int | None = None) -> ElmTerm:
    """

    :param bus:
    :param new_id:
    :param t:
    :return:
    """
    elm_term = ElmTerm()
    elm_term.ID = new_id
    elm_term.loc_name = bus.name
    elm_term.uknom = bus.Vnom
    elm_term.unknom = bus.Vnom / SQRT3
    elm_term.outserv = 0 if bus.get_active_at(t) else 1

    if bus.is_slack:
        elm_term.bustp = "SL"

    return elm_term


def convert_bus_graphic(elm_term, bus: dev.Bus, new_id: str) -> IntGrf:
    """

    :param elm_term:
    :param bus:
    :param new_id:
    :return:
    """
    # opcional: IntGrf para posición
    int_grf = IntGrf()
    int_grf.ID = new_id
    int_grf.pDataObj = elm_term.ID
    int_grf.rCenterX = bus.x
    int_grf.rCenterY = bus.y

    return int_grf


def convert_load(load: dev.Load, new_id: str, t: int | None = None) -> ElmLod:
    """

    :param load:
    :param new_id:
    :param t:
    :return:
    """
    e = ElmLod()
    e.ID = new_id
    e.loc_name = load.name
    e.plini = float(load.get_P_at(t))
    e.qlini = float(load.get_Q_at(t))
    e.scale0 = 1.0
    e.outserv = 0 if load.get_active_at(t) else 1

    return e


def convert_generator(gen: dev.Generator, tpe: TypSym, new_id: str, Sbase, t: int | None) -> ElmSym:
    """

    :param gen:
    :param tpe:
    :param new_id:
    :param Sbase:
    :param t:
    :return:
    """

    e = ElmSym()
    e.ID = new_id
    e.loc_name = gen.name
    e.ngnum = 1
    e.outserv = 0 if gen.get_active_at(t) else 1
    e.pgini = gen.get_P_at(t)
    e.qgini = gen.get_Q_at(t)
    e.q_min = gen.get_Qmin_at(t) / Sbase
    e.q_max = gen.get_Qmax_at(t) / Sbase
    e.usetp = gen.get_Vset_at(t)
    e.ip_ctrl = 1 if gen.bus.is_slack else 0
    e.typ_id = tpe.ID
    e.Pmin_uc = gen.get_Pmin_at(t)
    e.Pmax_uc = gen.get_Pmax_at(t)

    return e


def convert_sequence_line(seq: dev.SequenceLineType, new_id: str) -> TypLne:
    """

    :param seq:
    :param new_id:
    :return:
    """
    typlne = TypLne()
    typlne.ID = new_id

    typlne.loc_name = seq.name
    typlne.rline = seq.R
    typlne.xline = seq.X
    typlne.bline = seq.B
    typlne.cline = seq.Cnf

    typlne.rline0 = seq.R0
    typlne.xline0 = seq.X0
    typlne.bline0 = seq.B0
    typlne.cline0 = seq.Cnf0

    typlne.uline = seq.Vnom
    typlne.sline = seq.Imax
    typlne.InomAir = seq.Imax
    typlne.aohl_ = "cab"

    return typlne


def convert_transformer_type(tr: dev.TransformerType, new_id: str) -> TypTr2:
    """

    :param tr:
    :param new_id:
    :return:
    """
    typtr2 = TypTr2()
    typtr2.ID = new_id

    typtr2.utrn_h = tr.HV
    typtr2.utrn_l = tr.LV
    typtr2.strn = tr.Sn
    typtr2.pcutr = tr.Pcu
    typtr2.pfe = tr.Pfe
    typtr2.curmg = tr.I0
    typtr2.uktr = tr.Vsc
    typtr2.loc_name = tr.name

    return typtr2


def circuit_to_dgs(grid: dev.MultiCircuit, t: int | None = None) -> DgsCircuit:
    """

    :param grid:
    :param t: time step (None for snapshot)
    :return:
    """
    dgs_grid = DgsCircuit()

    # general
    general = General()
    general.ID = dgs_grid.new_id()
    general.Descr = "Version"
    general.Val = "5.0"
    dgs_grid.generals.append(general)

    # grid
    net = ElmNet()
    net.ID = dgs_grid.new_id()
    net.loc_name = grid.name
    net.frnom = grid.fBase
    dgs_grid.elmnets.append(net)

    # buses
    bus2term_dict: Dict[dev.Bus, ElmTerm] = dict()
    for bus in grid.buses:
        elm_term = convert_bus(bus, new_id=dgs_grid.new_id(), t=t)
        dgs_grid.elmterms.append(elm_term)
        bus2term_dict[bus] = elm_term

        # int_grf = convert_bus_graphic(elm_term, bus, new_id=dgs_grid.new_id())
        # dgs_grid.intgrfs.append(int_grf)

    # Loads
    for load in grid.loads:
        e = convert_load(load, new_id=dgs_grid.new_id(), t=t)
        term = bus2term_dict[load.bus]
        dgs_grid.elmlods.append(e)
        dgs_grid.add_element_cubicles(element_id=e.ID, dgs_buses=[term])

    # generators
    for gen in grid.generators:

        # Generate a fake TypSym
        tpe = TypSym()
        tpe.ID = dgs_grid.new_id()
        tpe.loc_name = gen.name
        tpe.ugn = gen.bus.Vnom
        tpe.cosn = gen.get_Pf_at(t)
        tpe.nphase = 3
        tpe.sgn = 0.01 if gen.Snom == 0 else gen.Snom
        dgs_grid.typsyms.append(tpe)

        # generate the actual generator
        e = convert_generator(gen=gen,
                              tpe=tpe,
                              new_id=dgs_grid.new_id(),
                              Sbase=grid.Sbase,
                              t=t)
        term = bus2term_dict[gen.bus]
        dgs_grid.elmsyms.append(e)
        dgs_grid.add_element_cubicles(element_id=e.ID, dgs_buses=[term])

    # sequence lines
    seq2typlne_dict: Dict[dev.SequenceLineType, TypLne] = dict()
    for seq in grid.sequence_line_types:
        typtr2 = convert_sequence_line(seq=seq, new_id=dgs_grid.new_id())
        dgs_grid.typlnes.append(typtr2)
        seq2typlne_dict[seq] = typtr2

    # transformer types
    tr2typtr2_dict: Dict[dev.TransformerType, TypTr2] = dict()
    for tr in grid.transformer_types:
        typtr2 = convert_transformer_type(tr=tr, new_id=dgs_grid.new_id())
        dgs_grid.typtr2s.append(typtr2)
        tr2typtr2_dict[tr] = typtr2

    # lines
    for line in grid.lines:

        # try search for the template
        tpe = seq2typlne_dict.get(line.template, None)

        if tpe is None:
            # produce a new template
            tpe = convert_sequence_line(seq=line.get_line_type(), new_id=dgs_grid.new_id())
            dgs_grid.typlnes.append(tpe)

        e = ElmLne()
        e.ID = dgs_grid.new_id()
        e.loc_name = line.name
        e.typ_id = tpe.ID
        e.dline = line.length
        e.fline = 1.0
        e.nlnum = 1
        e.outserv = 0 if line.get_active_at(t) else 1

        dgs_grid.elmlnes.append(e)
        dgs_grid.add_element_cubicles(
            element_id=e.ID,
            dgs_buses=[bus2term_dict[line.bus_from],
                       bus2term_dict[line.bus_to]]
        )

    # 2W transformers
    for tr in grid.transformers2w:
        # try search for the template
        tpe = tr2typtr2_dict.get(tr.template, None)

        if tpe is None:
            # produce a new template
            tpe = convert_transformer_type(tr=tr.get_transformer_type(),
                                           new_id=dgs_grid.new_id())
            dgs_grid.typtr2s.append(tpe)

        e = ElmTr2()
        e.ID = dgs_grid.new_id()
        e.loc_name = tr.name
        e.typ_id = tpe.ID

        e.outserv = 0 if tr.get_active_at(t) else 1

        dgs_grid.elmtr2s.append(e)
        dgs_grid.add_element_cubicles(
            element_id=e.ID,
            dgs_buses=[bus2term_dict[tr.bus_from],
                       bus2term_dict[tr.bus_to]]
        )

    # diagrams
    # for dia in grid.diagrams:
    #     if dia.diagram_type == DiagramType.Schematic:
    #         intgrfnet = IntGrfnet()
    #         intgrfnet.loc_name = dia.name
    #         intgrfnet.pDataFolder = net.ID
    #         dgs_grid.intgrfnets.append(intgrfnet)
    #
    #         for dtype, point_group in dia.data.items():
    #             for idtag, point in point_group.locations.items():
    #                 point.x
    #                 point.y
    #                 point.api_object.

    return dgs_grid
