# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import math
import numpy as np
import sys
import os
from pathlib import Path
from typing import Dict, List, Type, Optional, Tuple
import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import *


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
    elm_term.uknom = float(bus.Vnom)
    elm_term.outserv = not bus.get_active_at(t)

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
    e.outserv = not load.get_active_at(t)

    return e


def convert_generator(gen: dev.Generator, new_id: str, Sbase, t: int | None) -> ElmSym:
    """

    :param gen:
    :param new_id:
    :param Sbase:
    :param t:
    :return:
    """
    e = ElmSym()
    e.ID = new_id
    e.loc_name = gen.name
    e.ngnum = 1
    e.outserv = not gen.get_active_at(t)
    e.pgini = gen.get_P_at(t)
    e.qgini = gen.get_Q_at(t)
    e.q_min = gen.get_Qmin_at(t) / Sbase
    e.q_max = gen.get_Qmax_at(t) / Sbase
    e.usetp = gen.get_Vset_at(t)

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


def veragrid_to_dgs(grid: dev.MultiCircuit, t: int | None = None) -> DgsCircuit:
    """

    :param grid:
    :param t: time step (None for snapshot)
    :return:
    """
    dgs_grid = DgsCircuit()

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
        int_grf = convert_bus_graphic(elm_term, bus, new_id=dgs_grid.new_id())
        dgs_grid.elmterms.append(elm_term)
        dgs_grid.intgrfs.append(int_grf)
        bus2term_dict[bus] = elm_term

    # Loads
    for load in grid.loads:
        e = convert_load(load, new_id=dgs_grid.new_id(), t=t)
        term = bus2term_dict[load.bus]
        dgs_grid.elmlods.append(e)
        dgs_grid.add_element_cubicles(element_id=e.ID, dgs_buses=[term])

    # generators
    for gen in grid.generators:
        e = convert_generator(gen=gen, new_id=dgs_grid.new_id(), Sbase=grid.Sbase, t=t)
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
            # produce a new tamplate
            typtr2 = convert_sequence_line(seq=line.get_line_type(), new_id=dgs_grid.new_id())
            dgs_grid.typlnes.append(typtr2)

        e = ElmLne()
        e.ID = dgs_grid.new_id()
        e.loc_name = line.name
        e.typ_id = tpe.ID
        e.dline = line.length
        e.outserv = not line.get_active_at(t)

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
            # produce a new tamplate
            typtr2 = convert_transformer_type(tr=tr.get_transformer_type(),
                                              new_id=dgs_grid.new_id())
            dgs_grid.typtr2s.append(typtr2)

        e = ElmTr2()
        e.ID = dgs_grid.new_id()
        e.loc_name = tr.name
        e.typ_id = tpe.ID
        e.outserv = not tr.get_active_at(t)

        dgs_grid.elmtr2s.append(e)
        dgs_grid.add_element_cubicles(
            element_id=e.ID,
            dgs_buses=[bus2term_dict[tr.bus_from],
                       bus2term_dict[tr.bus_to]]
        )
    
    return dgs_grid
