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
from VeraGridEngine.IO.dgs.dgs_objects import (DGSElement,
                                               ChaRef,
                                               ChaVec,
                                               ElmAsm,
                                               ElmCoup,
                                               ElmFeeder,
                                               ElmGenstat,
                                               ElmLne,
                                               ElmLnesec,
                                               ElmLod,
                                               ElmLodlv,
                                               ElmLodlvp,
                                               ElmNet,
                                               ElmShnt,
                                               ElmSite,
                                               ElmSubstat,
                                               ElmSym,
                                               ElmTerm,
                                               ElmTr2,
                                               ElmTr3,
                                               ElmXnet,
                                               ElmZone,
                                               General,
                                               IntFolder,
                                               IntGrf,
                                               IntGrfcon,
                                               IntGrfnet,
                                               RelFuse,
                                               StaCubic,
                                               StaSwitch,
                                               TypAsmo,
                                               TypFuse,
                                               TypLne,
                                               TypLod,
                                               TypSym,
                                               TypTr2,
                                               TypTr3)


def veragrid_to_dgs(grid: dev.MultiCircuit) -> DgsCircuit:
    """

    :param grid:
    :return:
    """
    dgs_grid = DgsCircuit()

    # 1) ElmNet
    net = ElmNet()
    net.ID = dgs_grid.new_id()
    net.loc_name = grid.name
    net.frnom = grid.fBase
    dgs_grid.elmnets.append(net)

    # 2) ElmTerm por bus
    term_id_by_bus = {}
    for i, bus in enumerate(grid.buses):
        elm_term = ElmTerm()
        elm_term.ID = dgs_grid.new_id()
        elm_term.loc_name = bus.name
        elm_term.uknom = float(bus.Vnom)
        elm_term.outserv = 0 if bus.active else 1
        dgs_grid.elmterms.append(elm_term)
        term_id_by_bus[bus] = elm_term.ID
        
        if bus.is_slack:
            elm_term.bustp = "SL"

        # opcional: IntGrf para posición
        int_grf = IntGrf()
        int_grf.ID = dgs_grid.new_id()
        int_grf.pDataObj = elm_term.ID
        int_grf.rCenterX = bus.x
        int_grf.rCenterY = bus.y
        dgs_grid.intgrfs.append(int_grf)

    # 3) helper para crear cubicles y “conectar” un elemento a buses

    # 4) Loads
    for bus in grid.buses:
        for ld in getattr(bus, "loads", []):  # depende de cómo VeraGrid guarde loads
            e = ElmLod()
            e.ID = dgs_grid.new_id()
            e.loc_name = ld.name
            e.plini = float(ld.P)
            e.qlini = float(ld.Q)
            e.scale0 = 1.0
            e.outserv = 0
            dgs_grid.elmlods.append(e)
            dgs_grid.add_cubicles_for_element(e.ID, [bus])

    # 5) Lines (+ type)
    for line in grid.lines:
        tpe = TypLne()
        tpe.ID = dgs_grid.new_id()
        dgs_grid.typlnes.append(tpe)

        e = ElmLne()
        e.ID = dgs_grid.new_id()
        e.loc_name = line.name
        e.typ_id = tpe.ID
        e.dline = 1.0
        e.outserv = 0 if line.active else 1
        dgs_grid.elmlnes.append(e)
        dgs_grid.add_cubicles_for_element(e.ID, [line.bus_from, line.bus_to])

    # 6) Transformers 2W (+ type)
    for tr in grid.transformers2w:
        tpe = TypTr2()
        tpe.ID = dgs_grid.new_id()

        dgs_grid.typtr2s.append(tpe)

        e = ElmTr2()
        e.ID = dgs_grid.new_id()
        e.loc_name = tr.name
        e.typ_id = tpe.ID
        e.outserv = 0 if tr.active else 1
        dgs_grid.elmtr2s.append(e)
        dgs_grid.add_cubicles_for_element(e.ID, [tr.bus_from, tr.bus_to])

 

    return dgs_grid
