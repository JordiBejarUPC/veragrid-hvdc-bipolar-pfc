# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

class PfProperty:
    def __init__(
        self,
        name: str,
        dgs_type: str,
        description: str,
        py_name: str | None = None,
        converter: Callable[[str], Any] | None = None,
    ):
        self.name = name
        self.py_name = py_name or name
        self.dgs_type = dgs_type
        self.description = description
        self.converter = converter or self._default_converter(dgs_type)

    @staticmethod
    def _default_converter(dgs_type: str):
        if dgs_type.startswith('a'):
            return str
        if dgs_type == 'i':
            return int
        if dgs_type == 'r':
            return float
        if dgs_type == 'b':
            return lambda x: bool(int(x))
        return str

    def parse(self, value: str):
        if value is None or value == '':
            return None
        return self.converter(value)

    def format(self, value: Any) -> str:
        if value is None:
            return ''
        if self.dgs_type == 'b':
            return '1' if bool(value) else '0'
        return str(value)


class DGSElement:
    element_type: str
    properties_list: List[PfProperty]
    properties: Dict[str, PfProperty]

    def __init_subclass__(cls):
        cls.properties = {p.name: p for p in cls.properties_list}

    @classmethod
    def parse_line(cls, line: str):
        parts = line.rstrip('\n').split(';')
        obj = cls()
        for prop, raw in zip(cls.properties_list, parts):
            setattr(obj, prop.py_name, prop.parse(raw))
        return obj

    def to_dgs_line(self) -> str:
        return ';'.join(p.format(getattr(self, p.py_name)) for p in self.properties_list)


# NOTE: Header type conflicts observed across input DGS files.
# First-seen type was kept; later differing types are listed below.
# - ElmLne.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - ElmLne.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - ElmLod.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - ElmLod.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - ElmNet.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - ElmShnt.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - ElmShnt.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - ElmSym.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - ElmSym.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - ElmTerm.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - ElmTerm.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - ElmTr2.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - ElmTr2.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - ElmTr2.sernum: kept(a:20) vs seen(a) in Example1.dgs
# - ElmTr3.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - ElmTr3.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - ElmXnet.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - ElmXnet.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - ElmXnet.bustp: kept(a:2) vs seen(a) in Example1.dgs
# - IntGrf.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - IntGrf.sSymNam: kept(a:40) vs seen(a) in Example1.dgs
# - IntGrfcon.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - IntGrfnet.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - StaCubic.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - StaCubic.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - StaSwitch.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - TypLne.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - TypLne.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - TypLne.aohl_: kept(a:3) vs seen(a) in Example1.dgs
# - TypLod.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - TypSym.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - TypTr2.loc_name: kept(a:40) vs seen(a) in Example1.dgs
# - TypTr2.chr_name: kept(a:20) vs seen(a) in Example1.dgs
# - TypTr2.manuf: kept(a:20) vs seen(a) in Example1.dgs
# - TypTr2.tr2cn_h: kept(a:2) vs seen(a) in Example1.dgs
# - TypTr2.tr2cn_l: kept(a:2) vs seen(a) in Example1.dgs
# - ElmLne.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - ElmLne.chr_name: kept(a:20) vs seen(a) in Example2.dgs
# - ElmLod.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - ElmLod.chr_name: kept(a:20) vs seen(a) in Example2.dgs
# - ElmNet.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - ElmShnt.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - ElmShnt.chr_name: kept(a:20) vs seen(a) in Example2.dgs
# - ElmSym.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - ElmSym.chr_name: kept(a:20) vs seen(a) in Example2.dgs
# - ElmTerm.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - ElmTerm.chr_name: kept(a:20) vs seen(a) in Example2.dgs
# - ElmTr2.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - ElmTr2.chr_name: kept(a:20) vs seen(a) in Example2.dgs
# - ElmTr2.sernum: kept(a:20) vs seen(a) in Example2.dgs
# - ElmTr3.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - ElmTr3.chr_name: kept(a:20) vs seen(a) in Example2.dgs
# - ElmXnet.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - ElmXnet.chr_name: kept(a:20) vs seen(a) in Example2.dgs
# - ElmXnet.bustp: kept(a:2) vs seen(a) in Example2.dgs
# - IntGrf.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - IntGrf.sSymNam: kept(a:40) vs seen(a) in Example2.dgs
# - IntGrfcon.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - IntGrfnet.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - StaCubic.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - StaCubic.chr_name: kept(a:20) vs seen(a) in Example2.dgs
# - StaSwitch.loc_name: kept(a:40) vs seen(a) in Example2.dgs
# - ElmFeeder.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - ElmLne.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - ElmLne.chr_name: kept(a:20) vs seen(a) in Example4.dgs
# - ElmNet.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - ElmTerm.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - ElmTerm.chr_name: kept(a:20) vs seen(a) in Example4.dgs
# - ElmTr2.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - ElmTr2.chr_name: kept(a:20) vs seen(a) in Example4.dgs
# - ElmXnet.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - ElmXnet.chr_name: kept(a:20) vs seen(a) in Example4.dgs
# - ElmXnet.bustp: kept(a:2) vs seen(a) in Example4.dgs
# - IntGrf.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - IntGrf.sSymNam: kept(a:40) vs seen(a) in Example4.dgs
# - IntGrfcon.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - IntGrfnet.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - StaCubic.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - StaCubic.chr_name: kept(a:20) vs seen(a) in Example4.dgs
# - TypLne.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - TypLne.chr_name: kept(a:20) vs seen(a) in Example4.dgs
# - TypLne.aohl_: kept(a:3) vs seen(a) in Example4.dgs
# - TypTr2.loc_name: kept(a:40) vs seen(a) in Example4.dgs
# - TypTr2.chr_name: kept(a:20) vs seen(a) in Example4.dgs
# - TypTr2.manuf: kept(a:20) vs seen(a) in Example4.dgs
# - TypTr2.tr2cn_h: kept(a:2) vs seen(a) in Example4.dgs
# - TypTr2.tr2cn_l: kept(a:2) vs seen(a) in Example4.dgs
# - ElmLodlv.loc_name: kept(a) vs seen(a:40) in PLATOS grid 3.dgs
# - ElmLodlv.for_name: kept(a) vs seen(a:40) in PLATOS grid 3.dgs
# - ElmLodlv.chr_name: kept(a) vs seen(a:20) in PLATOS grid 3.dgs
# - ElmCoup.loc_name: kept(a) vs seen(a:40) in Switches-missing-voltage.dgs
# - ElmCoup.aUsage: kept(a) vs seen(a:4) in Switches-missing-voltage.dgs
# - ElmCoup.loc_name: kept(a) vs seen(a:40) in Switches-negative-voltage.dgs
# - ElmCoup.aUsage: kept(a) vs seen(a:4) in Switches-negative-voltage.dgs
# - ElmSubstat.loc_name: kept(a) vs seen(a:40) in VoltageLevelsAndSubstations.dgs
# - TypTr3.loc_name: kept(a) vs seen(a:40) in ThreeMIB_T3W_phase_winding12.dgs
# - TypTr3.tr3cn_h: kept(a) vs seen(a:2) in ThreeMIB_T3W_phase_winding12.dgs
# - TypTr3.tr3cn_m: kept(a) vs seen(a:2) in ThreeMIB_T3W_phase_winding12.dgs
# - TypTr3.tr3cn_l: kept(a) vs seen(a:2) in ThreeMIB_T3W_phase_winding12.dgs


class ChaRef(DGSElement):
    element_type = 'ChaRef'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""


class ChaVec(DGSElement):
    element_type = 'ChaVec'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('scale', 'p', 'DGS field scale (p)', py_name='scale'),
        PfProperty('usage', 'i', 'DGS field usage (i)', py_name='usage'),
        PfProperty('approx', 'i', 'DGS field approx (i)', py_name='approx'),
        PfProperty('vector:SIZEROW', 'i', 'DGS field vector:SIZEROW (i)', py_name='vector_SIZEROW'),
        PfProperty('vector:0', 'r', 'DGS field vector:0 (r)', py_name='vector_0'),
        PfProperty('vector:1', 'r', 'DGS field vector:1 (r)', py_name='vector_1'),
        PfProperty('vector:2', 'r', 'DGS field vector:2 (r)', py_name='vector_2'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.scale: str = ""
        self.usage: int = 0
        self.approx: int = 0
        self.vector_SIZEROW: int = 0
        self.vector_0: float = 0.0
        self.vector_1: float = 0.0
        self.vector_2: float = 0.0


class ElmAsm(DGSElement):
    element_type = 'ElmAsm'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('chr_name', 'a', 'DGS field chr_name (a)', py_name='chr_name'),
        PfProperty('i_mot', 'i', 'DGS field i_mot (i)', py_name='i_mot'),
        PfProperty('ngnum', 'i', 'DGS field ngnum (i)', py_name='ngnum'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('pgini', 'r', 'DGS field pgini (r)', py_name='pgini'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.i_mot: int = 0
        self.ngnum: int = 0
        self.outserv: int = 0
        self.pgini: float = 0.0


class ElmCoup(DGSElement):
    element_type = 'ElmCoup'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('chr_name', 'a', 'DGS field chr_name (a)', py_name='chr_name'),
        PfProperty('aUsage', 'a', 'DGS field aUsage (a)', py_name='aUsage'),
        PfProperty('nneutral', 'i', 'DGS field nneutral (i)', py_name='nneutral'),
        PfProperty('nphase', 'i', 'DGS field nphase (i)', py_name='nphase'),
        PfProperty('on_off', 'i', 'DGS field on_off (i)', py_name='on_off'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.aUsage: str = ""
        self.nneutral: int = 0
        self.nphase: int = 0
        self.on_off: int = 0
        self.for_name: str = ""


class ElmFeeder(DGSElement):
    element_type = 'ElmFeeder'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('obj_id', 'p', 'DGS field obj_id (p)', py_name='obj_id'),
        PfProperty('iorient', 'i', 'DGS field iorient (i)', py_name='iorient'),
        PfProperty('i_scale', 'i', 'DGS field i_scale (i)', py_name='i_scale'),
        PfProperty('Iset', 'r', 'DGS field Iset (r)', py_name='Iset'),
        PfProperty('icolor', 'i', 'DGS field icolor (i)', py_name='icolor'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.obj_id: str = ""
        self.iorient: int = 0
        self.i_scale: int = 0
        self.Iset: float = 0.0
        self.icolor: int = 0
        self.outserv: int = 0


class ElmGenstat(DGSElement):
    element_type = 'ElmGenstat'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('bus1', 'p', 'DGS field bus1 (p)', py_name='bus1'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('sgn', 'r', 'DGS field sgn (r)', py_name='sgn'),
        PfProperty('cosn', 'r', 'DGS field cosn (r)', py_name='cosn'),
        PfProperty('ngnum', 'i', 'DGS field ngnum (i)', py_name='ngnum'),
        PfProperty('pgini', 'r', 'DGS field pgini (r)', py_name='pgini'),
        PfProperty('qgini', 'r', 'DGS field qgini (r)', py_name='qgini'),
        PfProperty('av_mode', 'a', 'DGS field av_mode (a)', py_name='av_mode'),
        PfProperty('ip_ctrl', 'i', 'DGS field ip_ctrl (i)', py_name='ip_ctrl'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.bus1: str = ""
        self.outserv: int = 0
        self.sgn: float = 0.0
        self.cosn: float = 0.0
        self.ngnum: int = 0
        self.pgini: float = 0.0
        self.qgini: float = 0.0
        self.av_mode: str = ""
        self.ip_ctrl: int = 0


class ElmLne(DGSElement):
    element_type = 'ElmLne'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('dline', 'r', 'DGS field dline (r)', py_name='dline'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('fline', 'r', 'DGS field fline (r)', py_name='fline'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('pStoch', 'p', 'DGS field pStoch (p)', py_name='pStoch'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('GPScoords:SIZEROW', 'i', 'DGS field GPScoords:SIZEROW (i)', py_name='GPScoords_SIZEROW'),
        PfProperty('GPScoords:SIZECOL', 'i', 'DGS field GPScoords:SIZECOL (i)', py_name='GPScoords_SIZECOL'),
        PfProperty('nlnum', 'i', 'DGS field nlnum (i)', py_name='nlnum'),
        PfProperty('inAir', 'i', 'DGS field inAir (i)', py_name='inAir'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.dline: float = 0.0
        self.chr_name: str = ""
        self.fline: float = 0.0
        self.outserv: int = 0
        self.pStoch: str = ""
        self.for_name: str = ""
        self.GPScoords_SIZEROW: int = 0
        self.GPScoords_SIZECOL: int = 0
        self.nlnum: int = 0
        self.inAir: int = 0


class ElmLnesec(DGSElement):
    element_type = 'ElmLnesec'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('chr_name', 'a', 'DGS field chr_name (a)', py_name='chr_name'),
        PfProperty('dline', 'r', 'DGS field dline (r)', py_name='dline'),
        PfProperty('fline', 'r', 'DGS field fline (r)', py_name='fline'),
        PfProperty('index', 'r', 'DGS field index (r)', py_name='index'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.dline: float = 0.0
        self.fline: float = 0.0
        self.index: float = 0.0


class ElmLod(DGSElement):
    element_type = 'ElmLod'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('plini', 'r', 'DGS field plini (r)', py_name='plini'),
        PfProperty('qlini', 'r', 'DGS field qlini (r)', py_name='qlini'),
        PfProperty('scale0', 'r', 'DGS field scale0 (r)', py_name='scale0'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('mode_inp', 'a:3', 'DGS field mode_inp (a:3)', py_name='mode_inp'),
        PfProperty('slini', 'r', 'DGS field slini (r)', py_name='slini'),
        PfProperty('coslini', 'r', 'DGS field coslini (r)', py_name='coslini'),
        PfProperty('pf_recap', 'i', 'DGS field pf_recap (i)', py_name='pf_recap'),
        PfProperty('i_scale', 'i', 'DGS field i_scale (i)', py_name='i_scale'),
        PfProperty('classif', 'a:20', 'DGS field classif (a:20)', py_name='classif'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.plini: float = 0.0
        self.qlini: float = 0.0
        self.scale0: float = 0.0
        self.outserv: int = 0
        self.for_name: str = ""
        self.mode_inp: str = ""
        self.slini: float = 0.0
        self.coslini: float = 0.0
        self.pf_recap: int = 0
        self.i_scale: int = 0
        self.classif: str = ""


class ElmLodlv(DGSElement):
    element_type = 'ElmLodlv'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('chr_name', 'a', 'DGS field chr_name (a)', py_name='chr_name'),
        PfProperty('for_name', 'a', 'DGS field for_name (a)', py_name='for_name'),
        PfProperty('ulini', 'r', 'DGS field ulini (r)', py_name='ulini'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.for_name: str = ""
        self.ulini: float = 0.0


class ElmLodlvp(DGSElement):
    element_type = 'ElmLodlvp'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('chr_name', 'a', 'DGS field chr_name (a)', py_name='chr_name'),
        PfProperty('for_name', 'a', 'DGS field for_name (a)', py_name='for_name'),
        PfProperty('lneposkm', 'r', 'DGS field lneposkm (r)', py_name='lneposkm'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('ulini', 'r', 'DGS field ulini (r)', py_name='ulini'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.for_name: str = ""
        self.lneposkm: float = 0.0
        self.outserv: int = 0
        self.ulini: float = 0.0


class ElmNet(DGSElement):
    element_type = 'ElmNet'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('frnom', 'r', 'DGS field frnom (r)', py_name='frnom'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('pDiagram', 'p', 'DGS field pDiagram (p)', py_name='pDiagram'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.frnom: float = 0.0
        self.for_name: str = ""
        self.pDiagram: str = ""


class ElmShnt(DGSElement):
    element_type = 'ElmShnt'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('shtype', 'i', 'DGS field shtype (i)', py_name='shtype'),
        PfProperty('ushnm', 'r', 'DGS field ushnm (r)', py_name='ushnm'),
        PfProperty('qcapn', 'r', 'DGS field qcapn (r)', py_name='qcapn'),
        PfProperty('ncapx', 'i', 'DGS field ncapx (i)', py_name='ncapx'),
        PfProperty('ncapa', 'i', 'DGS field ncapa (i)', py_name='ncapa'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('ctech', 'i', 'DGS field ctech (i)', py_name='ctech'),
        PfProperty('fres', 'r', 'DGS field fres (r)', py_name='fres'),
        PfProperty('greaf0', 'r', 'DGS field greaf0 (r)', py_name='greaf0'),
        PfProperty('iswitch', 'i', 'DGS field iswitch (i)', py_name='iswitch'),
        PfProperty('qtotn', 'r', 'DGS field qtotn (r)', py_name='qtotn'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.chr_name: str = ""
        self.shtype: int = 0
        self.ushnm: float = 0.0
        self.qcapn: float = 0.0
        self.ncapx: int = 0
        self.ncapa: int = 0
        self.outserv: int = 0
        self.ctech: int = 0
        self.fres: float = 0.0
        self.greaf0: float = 0.0
        self.iswitch: int = 0
        self.qtotn: float = 0.0


class ElmSite(DGSElement):
    element_type = 'ElmSite'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('sType', 'a:80', 'DGS field sType (a:80)', py_name='sType'),
        PfProperty('GPSlat', 'r', 'DGS field GPSlat (r)', py_name='GPSlat'),
        PfProperty('GPSlon', 'r', 'DGS field GPSlon (r)', py_name='GPSlon'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""
        self.sType: str = ""
        self.GPSlat: float = 0.0
        self.GPSlon: float = 0.0


class ElmSubstat(DGSElement):
    element_type = 'ElmSubstat'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('Unom', 'r', 'DGS field Unom (r)', py_name='Unom'),
        PfProperty('pRA', 'p', 'DGS field pRA (p)', py_name='pRA'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('sShort', 'a:6', 'DGS field sShort (a:6)', py_name='sShort'),
        PfProperty('sType', 'a:80', 'DGS field sType (a:80)', py_name='sType'),
        PfProperty('GPSlat', 'r', 'DGS field GPSlat (r)', py_name='GPSlat'),
        PfProperty('GPSlon', 'r', 'DGS field GPSlon (r)', py_name='GPSlon'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.Unom: float = 0.0
        self.pRA: str = ""
        self.for_name: str = ""
        self.sShort: str = ""
        self.sType: str = ""
        self.GPSlat: float = 0.0
        self.GPSlon: float = 0.0


class ElmSym(DGSElement):
    element_type = 'ElmSym'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('ngnum', 'i', 'DGS field ngnum (i)', py_name='ngnum'),
        PfProperty('i_mot', 'i', 'DGS field i_mot (i)', py_name='i_mot'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('pgini', 'r', 'DGS field pgini (r)', py_name='pgini'),
        PfProperty('qgini', 'r', 'DGS field qgini (r)', py_name='qgini'),
        PfProperty('usetp', 'r', 'DGS field usetp (r)', py_name='usetp'),
        PfProperty('iv_mode', 'i', 'DGS field iv_mode (i)', py_name='iv_mode'),
        PfProperty('q_min', 'r', 'DGS field q_min (r)', py_name='q_min'),
        PfProperty('q_max', 'r', 'DGS field q_max (r)', py_name='q_max'),
        PfProperty('Pmin_uc', 'r', 'DGS field Pmin_uc (r)', py_name='Pmin_uc'),
        PfProperty('Pmax_uc', 'r', 'DGS field Pmax_uc (r)', py_name='Pmax_uc'),
        PfProperty('iqtype', 'i', 'DGS field iqtype (i)', py_name='iqtype'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('cCategory', 'a', 'DGS field cCategory (a)', py_name='cCategory'),
        PfProperty('cosgini', 'r', 'DGS field cosgini (r)', py_name='cosgini'),
        PfProperty('pf_recap', 'i', 'DGS field pf_recap (i)', py_name='pf_recap'),
        PfProperty('av_mode', 'a', 'DGS field av_mode (a)', py_name='av_mode'),
        PfProperty('phtech', 'i', 'DGS field phtech (i)', py_name='phtech'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.ngnum: int = 0
        self.i_mot: int = 0
        self.chr_name: str = ""
        self.outserv: int = 0
        self.pgini: float = 0.0
        self.qgini: float = 0.0
        self.usetp: float = 0.0
        self.iv_mode: int = 0
        self.q_min: float = 0.0
        self.q_max: float = 0.0
        self.Pmin_uc: float = 0.0
        self.Pmax_uc: float = 0.0
        self.iqtype: int = 0
        self.for_name: str = ""
        self.cCategory: str = ""
        self.cosgini: float = 0.0
        self.pf_recap: int = 0
        self.av_mode: str = ""
        self.phtech: int = 0


class ElmTerm(DGSElement):
    element_type = 'ElmTerm'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('iUsage', 'i', 'DGS field iUsage (i)', py_name='iUsage'),
        PfProperty('uknom', 'r', 'DGS field uknom (r)', py_name='uknom'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('phtech', 'i', 'DGS field phtech (i)', py_name='phtech'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('systype', 'i', 'DGS field systype (i)', py_name='systype'),
        PfProperty('unknom', 'r', 'DGS field unknom (r)', py_name='unknom'),
        PfProperty('iminus', 'i', 'DGS field iminus (i)', py_name='iminus'),
        PfProperty('GPSlat', 'r', 'DGS field GPSlat (r)', py_name='GPSlat'),
        PfProperty('GPSlon', 'r', 'DGS field GPSlon (r)', py_name='GPSlon'),
        PfProperty('vtarget', 'r', 'DGS field vtarget (r)', py_name='vtarget'),
        PfProperty('m:u', 'r', 'DGS field m:u (r)', py_name='m_u'),
        PfProperty('m:phiu', 'r', 'DGS field m:phiu (r)', py_name='m_phiu'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.iUsage: int = 0
        self.uknom: float = 0.0
        self.chr_name: str = ""
        self.outserv: int = 0
        self.phtech: int = 0
        self.for_name: str = ""
        self.systype: int = 0
        self.unknom: float = 0.0
        self.iminus: int = 0
        self.GPSlat: float = 0.0
        self.GPSlon: float = 0.0
        self.vtarget: float = 0.0
        self.m_u: float = 0.0
        self.m_phiu: float = 0.0


class ElmTr2(DGSElement):
    element_type = 'ElmTr2'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('nntap', 'i', 'DGS field nntap (i)', py_name='nntap'),
        PfProperty('sernum', 'a:20', 'DGS field sernum (a:20)', py_name='sernum'),
        PfProperty('constr', 'i', 'DGS field constr (i)', py_name='constr'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('cgnd_h', 'i', 'DGS field cgnd_h (i)', py_name='cgnd_h'),
        PfProperty('cgnd_l', 'i', 'DGS field cgnd_l (i)', py_name='cgnd_l'),
        PfProperty('i_auto', 'i', 'DGS field i_auto (i)', py_name='i_auto'),
        PfProperty('ntrcn', 'i', 'DGS field ntrcn (i)', py_name='ntrcn'),
        PfProperty('ratfac', 'r', 'DGS field ratfac (r)', py_name='ratfac'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('ntnum', 'i', 'DGS field ntnum (i)', py_name='ntnum'),
        PfProperty('usetp', 'r', 'DGS field usetp (r)', py_name='usetp'),
        PfProperty('usp_low', 'r', 'DGS field usp_low (r)', py_name='usp_low'),
        PfProperty('usp_up', 'r', 'DGS field usp_up (r)', py_name='usp_up'),
        PfProperty('t2ldc', 'i', 'DGS field t2ldc (i)', py_name='t2ldc'),
        PfProperty('mTaps:SIZEROW', 'i', 'DGS field mTaps:SIZEROW (i)', py_name='mTaps_SIZEROW'),
        PfProperty('mTaps:SIZECOL', 'i', 'DGS field mTaps:SIZECOL (i)', py_name='mTaps_SIZECOL'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.outserv: int = 0
        self.nntap: int = 0
        self.sernum: str = ""
        self.constr: int = 0
        self.chr_name: str = ""
        self.cgnd_h: int = 0
        self.cgnd_l: int = 0
        self.i_auto: int = 0
        self.ntrcn: int = 0
        self.ratfac: float = 0.0
        self.for_name: str = ""
        self.ntnum: int = 0
        self.usetp: float = 0.0
        self.usp_low: float = 0.0
        self.usp_up: float = 0.0
        self.t2ldc: int = 0
        self.mTaps_SIZEROW: int = 0
        self.mTaps_SIZECOL: int = 0


class ElmTr3(DGSElement):
    element_type = 'ElmTr3'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('nt3nm', 'i', 'DGS field nt3nm (i)', py_name='nt3nm'),
        PfProperty('n3tap_h', 'i', 'DGS field n3tap_h (i)', py_name='n3tap_h'),
        PfProperty('n3tap_m', 'i', 'DGS field n3tap_m (i)', py_name='n3tap_m'),
        PfProperty('n3tap_l', 'i', 'DGS field n3tap_l (i)', py_name='n3tap_l'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('i_auto_hl', 'i', 'DGS field i_auto_hl (i)', py_name='i_auto_hl'),
        PfProperty('ictrlside', 'i', 'DGS field ictrlside (i)', py_name='ictrlside'),
        PfProperty('ntrcn', 'i', 'DGS field ntrcn (i)', py_name='ntrcn'),
        PfProperty('t3ldc', 'i', 'DGS field t3ldc (i)', py_name='t3ldc'),
        PfProperty('usetp', 'r', 'DGS field usetp (r)', py_name='usetp'),
        PfProperty('usp_low', 'r', 'DGS field usp_low (r)', py_name='usp_low'),
        PfProperty('usp_up', 'r', 'DGS field usp_up (r)', py_name='usp_up'),
        PfProperty('mTaps:SIZEROW', 'i', 'DGS field mTaps:SIZEROW (i)', py_name='mTaps_SIZEROW'),
        PfProperty('mTaps:SIZECOL', 'i', 'DGS field mTaps:SIZECOL (i)', py_name='mTaps_SIZECOL'),
        PfProperty('mTaps:0:0', 'r', 'DGS field mTaps:0:0 (r)', py_name='mTaps_0_0'),
        PfProperty('mTaps:0:1', 'r', 'DGS field mTaps:0:1 (r)', py_name='mTaps_0_1'),
        PfProperty('mTaps:0:2', 'r', 'DGS field mTaps:0:2 (r)', py_name='mTaps_0_2'),
        PfProperty('mTaps:0:3', 'r', 'DGS field mTaps:0:3 (r)', py_name='mTaps_0_3'),
        PfProperty('mTaps:0:4', 'r', 'DGS field mTaps:0:4 (r)', py_name='mTaps_0_4'),
        PfProperty('mTaps:0:5', 'r', 'DGS field mTaps:0:5 (r)', py_name='mTaps_0_5'),
        PfProperty('mTaps:0:6', 'r', 'DGS field mTaps:0:6 (r)', py_name='mTaps_0_6'),
        PfProperty('mTaps:0:7', 'r', 'DGS field mTaps:0:7 (r)', py_name='mTaps_0_7'),
        PfProperty('mTaps:1:0', 'r', 'DGS field mTaps:1:0 (r)', py_name='mTaps_1_0'),
        PfProperty('mTaps:1:1', 'r', 'DGS field mTaps:1:1 (r)', py_name='mTaps_1_1'),
        PfProperty('mTaps:1:2', 'r', 'DGS field mTaps:1:2 (r)', py_name='mTaps_1_2'),
        PfProperty('mTaps:1:3', 'r', 'DGS field mTaps:1:3 (r)', py_name='mTaps_1_3'),
        PfProperty('mTaps:1:4', 'r', 'DGS field mTaps:1:4 (r)', py_name='mTaps_1_4'),
        PfProperty('mTaps:1:5', 'r', 'DGS field mTaps:1:5 (r)', py_name='mTaps_1_5'),
        PfProperty('mTaps:1:6', 'r', 'DGS field mTaps:1:6 (r)', py_name='mTaps_1_6'),
        PfProperty('mTaps:1:7', 'r', 'DGS field mTaps:1:7 (r)', py_name='mTaps_1_7'),
        PfProperty('mTaps:2:0', 'r', 'DGS field mTaps:2:0 (r)', py_name='mTaps_2_0'),
        PfProperty('mTaps:2:1', 'r', 'DGS field mTaps:2:1 (r)', py_name='mTaps_2_1'),
        PfProperty('mTaps:2:2', 'r', 'DGS field mTaps:2:2 (r)', py_name='mTaps_2_2'),
        PfProperty('mTaps:2:3', 'r', 'DGS field mTaps:2:3 (r)', py_name='mTaps_2_3'),
        PfProperty('mTaps:2:4', 'r', 'DGS field mTaps:2:4 (r)', py_name='mTaps_2_4'),
        PfProperty('mTaps:2:5', 'r', 'DGS field mTaps:2:5 (r)', py_name='mTaps_2_5'),
        PfProperty('mTaps:2:6', 'r', 'DGS field mTaps:2:6 (r)', py_name='mTaps_2_6'),
        PfProperty('mTaps:2:7', 'r', 'DGS field mTaps:2:7 (r)', py_name='mTaps_2_7'),
        PfProperty('iMeasTap', 'i', 'DGS field iMeasTap (i)', py_name='iMeasTap'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.outserv: int = 0
        self.nt3nm: int = 0
        self.n3tap_h: int = 0
        self.n3tap_m: int = 0
        self.n3tap_l: int = 0
        self.chr_name: str = ""
        self.for_name: str = ""
        self.i_auto_hl: int = 0
        self.ictrlside: int = 0
        self.ntrcn: int = 0
        self.t3ldc: int = 0
        self.usetp: float = 0.0
        self.usp_low: float = 0.0
        self.usp_up: float = 0.0
        self.mTaps_SIZEROW: int = 0
        self.mTaps_SIZECOL: int = 0
        self.mTaps_0_0: float = 0.0
        self.mTaps_0_1: float = 0.0
        self.mTaps_0_2: float = 0.0
        self.mTaps_0_3: float = 0.0
        self.mTaps_0_4: float = 0.0
        self.mTaps_0_5: float = 0.0
        self.mTaps_0_6: float = 0.0
        self.mTaps_0_7: float = 0.0
        self.mTaps_1_0: float = 0.0
        self.mTaps_1_1: float = 0.0
        self.mTaps_1_2: float = 0.0
        self.mTaps_1_3: float = 0.0
        self.mTaps_1_4: float = 0.0
        self.mTaps_1_5: float = 0.0
        self.mTaps_1_6: float = 0.0
        self.mTaps_1_7: float = 0.0
        self.mTaps_2_0: float = 0.0
        self.mTaps_2_1: float = 0.0
        self.mTaps_2_2: float = 0.0
        self.mTaps_2_3: float = 0.0
        self.mTaps_2_4: float = 0.0
        self.mTaps_2_5: float = 0.0
        self.mTaps_2_6: float = 0.0
        self.mTaps_2_7: float = 0.0
        self.iMeasTap: int = 0


class ElmXnet(DGSElement):
    element_type = 'ElmXnet'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        PfProperty('snss', 'r', 'DGS field snss (r)', py_name='snss'),
        PfProperty('rntxn', 'r', 'DGS field rntxn (r)', py_name='rntxn'),
        PfProperty('z2tz1', 'r', 'DGS field z2tz1 (r)', py_name='z2tz1'),
        PfProperty('snssmin', 'r', 'DGS field snssmin (r)', py_name='snssmin'),
        PfProperty('rntxnmin', 'r', 'DGS field rntxnmin (r)', py_name='rntxnmin'),
        PfProperty('z2tz1min', 'r', 'DGS field z2tz1min (r)', py_name='z2tz1min'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('bustp', 'a:2', 'DGS field bustp (a:2)', py_name='bustp'),
        PfProperty('pgini', 'r', 'DGS field pgini (r)', py_name='pgini'),
        PfProperty('qgini', 'r', 'DGS field qgini (r)', py_name='qgini'),
        PfProperty('phiini', 'r', 'DGS field phiini (r)', py_name='phiini'),
        PfProperty('usetp', 'r', 'DGS field usetp (r)', py_name='usetp'),
        PfProperty('cgnd', 'i', 'DGS field cgnd (i)', py_name='cgnd'),
        PfProperty('iintgnd', 'i', 'DGS field iintgnd (i)', py_name='iintgnd'),
        PfProperty('ikssmin', 'r', 'DGS field ikssmin (r)', py_name='ikssmin'),
        PfProperty('r0tx0', 'r', 'DGS field r0tx0 (r)', py_name='r0tx0'),
        PfProperty('r0tx0min', 'r', 'DGS field r0tx0min (r)', py_name='r0tx0min'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.outserv: int = 0
        self.snss: float = 0.0
        self.rntxn: float = 0.0
        self.z2tz1: float = 0.0
        self.snssmin: float = 0.0
        self.rntxnmin: float = 0.0
        self.z2tz1min: float = 0.0
        self.chr_name: str = ""
        self.bustp: str = ""
        self.pgini: float = 0.0
        self.qgini: float = 0.0
        self.phiini: float = 0.0
        self.usetp: float = 0.0
        self.cgnd: int = 0
        self.iintgnd: int = 0
        self.ikssmin: float = 0.0
        self.r0tx0: float = 0.0
        self.r0tx0min: float = 0.0


class ElmZone(DGSElement):
    element_type = 'ElmZone'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('icolor', 'i', 'DGS field icolor (i)', py_name='icolor'),
        PfProperty('curscale', 'r', 'DGS field curscale (r)', py_name='curscale'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""
        self.icolor: int = 0
        self.curscale: float = 0.0


class General(DGSElement):
    element_type = 'General'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('Descr', 'a:40', 'DGS field Descr (a:40)', py_name='Descr'),
        PfProperty('Val', 'a:40', 'DGS field Val (a:40)', py_name='Val'),
        PfProperty('FID', 'a:40', 'DGS field FID (a:40)', py_name='FID'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.Descr: str = ""
        self.Val: str = ""
        self.FID: str = ""


class IntFolder(DGSElement):
    element_type = 'IntFolder'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('iopt_typ', 'i', 'DGS field iopt_typ (i)', py_name='iopt_typ'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.iopt_typ: int = 0


class IntGrf(DGSElement):
    element_type = 'IntGrf'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('iCol', 'i', 'DGS field iCol (i)', py_name='iCol'),
        PfProperty('iVis', 'i', 'DGS field iVis (i)', py_name='iVis'),
        PfProperty('iLevel', 'i', 'DGS field iLevel (i)', py_name='iLevel'),
        PfProperty('rCenterX', 'r', 'DGS field rCenterX (r)', py_name='rCenterX'),
        PfProperty('rCenterY', 'r', 'DGS field rCenterY (r)', py_name='rCenterY'),
        PfProperty('sSymNam', 'a:40', 'DGS field sSymNam (a:40)', py_name='sSymNam'),
        PfProperty('pDataObj', 'p', 'DGS field pDataObj (p)', py_name='pDataObj'),
        PfProperty('iRot', 'i', 'DGS field iRot (i)', py_name='iRot'),
        PfProperty('rSizeX', 'r', 'DGS field rSizeX (r)', py_name='rSizeX'),
        PfProperty('rSizeY', 'r', 'DGS field rSizeY (r)', py_name='rSizeY'),
        PfProperty('sAttr:SIZEROW', 'i', 'DGS field sAttr:SIZEROW (i)', py_name='sAttr_SIZEROW'),
        PfProperty('sAttr:0', 'a', 'DGS field sAttr:0 (a)', py_name='sAttr_0'),
        PfProperty('sAttr:1', 'a', 'DGS field sAttr:1 (a)', py_name='sAttr_1'),
        PfProperty('sAttr:2', 'a', 'DGS field sAttr:2 (a)', py_name='sAttr_2'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.iCol: int = 0
        self.iVis: int = 0
        self.iLevel: int = 0
        self.rCenterX: float = 0.0
        self.rCenterY: float = 0.0
        self.sSymNam: str = ""
        self.pDataObj: str = ""
        self.iRot: int = 0
        self.rSizeX: float = 0.0
        self.rSizeY: float = 0.0
        self.sAttr_SIZEROW: int = 0
        self.sAttr_0: str = ""
        self.sAttr_1: str = ""
        self.sAttr_2: str = ""


class IntGrfcon(DGSElement):
    element_type = 'IntGrfcon'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('rX:SIZEROW', 'i', 'DGS field rX:SIZEROW (i)', py_name='rX_SIZEROW'),
        PfProperty('rX:0', 'r', 'DGS field rX:0 (r)', py_name='rX_0'),
        PfProperty('rX:1', 'r', 'DGS field rX:1 (r)', py_name='rX_1'),
        PfProperty('rX:2', 'r', 'DGS field rX:2 (r)', py_name='rX_2'),
        PfProperty('rX:3', 'r', 'DGS field rX:3 (r)', py_name='rX_3'),
        PfProperty('rY:SIZEROW', 'i', 'DGS field rY:SIZEROW (i)', py_name='rY_SIZEROW'),
        PfProperty('rY:0', 'r', 'DGS field rY:0 (r)', py_name='rY_0'),
        PfProperty('rY:1', 'r', 'DGS field rY:1 (r)', py_name='rY_1'),
        PfProperty('rY:2', 'r', 'DGS field rY:2 (r)', py_name='rY_2'),
        PfProperty('rY:3', 'r', 'DGS field rY:3 (r)', py_name='rY_3'),
        PfProperty('rX:4', 'r', 'DGS field rX:4 (r)', py_name='rX_4'),
        PfProperty('rX:5', 'r', 'DGS field rX:5 (r)', py_name='rX_5'),
        PfProperty('rX:6', 'r', 'DGS field rX:6 (r)', py_name='rX_6'),
        PfProperty('rX:7', 'r', 'DGS field rX:7 (r)', py_name='rX_7'),
        PfProperty('rX:8', 'r', 'DGS field rX:8 (r)', py_name='rX_8'),
        PfProperty('rX:9', 'r', 'DGS field rX:9 (r)', py_name='rX_9'),
        PfProperty('rY:4', 'r', 'DGS field rY:4 (r)', py_name='rY_4'),
        PfProperty('rY:5', 'r', 'DGS field rY:5 (r)', py_name='rY_5'),
        PfProperty('rY:6', 'r', 'DGS field rY:6 (r)', py_name='rY_6'),
        PfProperty('rY:7', 'r', 'DGS field rY:7 (r)', py_name='rY_7'),
        PfProperty('rY:8', 'r', 'DGS field rY:8 (r)', py_name='rY_8'),
        PfProperty('rY:9', 'r', 'DGS field rY:9 (r)', py_name='rY_9'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.rX_SIZEROW: int = 0
        self.rX_0: float = 0.0
        self.rX_1: float = 0.0
        self.rX_2: float = 0.0
        self.rX_3: float = 0.0
        self.rY_SIZEROW: int = 0
        self.rY_0: float = 0.0
        self.rY_1: float = 0.0
        self.rY_2: float = 0.0
        self.rY_3: float = 0.0
        self.rX_4: float = 0.0
        self.rX_5: float = 0.0
        self.rX_6: float = 0.0
        self.rX_7: float = 0.0
        self.rX_8: float = 0.0
        self.rX_9: float = 0.0
        self.rY_4: float = 0.0
        self.rY_5: float = 0.0
        self.rY_6: float = 0.0
        self.rY_7: float = 0.0
        self.rY_8: float = 0.0
        self.rY_9: float = 0.0


class IntGrfnet(DGSElement):
    element_type = 'IntGrfnet'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('snap_on', 'i', 'DGS field snap_on (i)', py_name='snap_on'),
        PfProperty('grid_on', 'i', 'DGS field grid_on (i)', py_name='grid_on'),
        PfProperty('ortho_on', 'i', 'DGS field ortho_on (i)', py_name='ortho_on'),
        PfProperty('pDataFolder', 'p', 'DGS field pDataFolder (p)', py_name='pDataFolder'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.snap_on: int = 0
        self.grid_on: int = 0
        self.ortho_on: int = 0
        self.pDataFolder: str = ""


class RelFuse(DGSElement):
    element_type = 'RelFuse'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('chr_name', 'a', 'DGS field chr_name (a)', py_name='chr_name'),
        PfProperty('aUsage', 'a', 'DGS field aUsage (a)', py_name='aUsage'),
        PfProperty('nphase', 'i', 'DGS field nphase (i)', py_name='nphase'),
        PfProperty('on_off', 'i', 'DGS field on_off (i)', py_name='on_off'),
        PfProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.aUsage: str = ""
        self.nphase: int = 0
        self.on_off: int = 0
        self.outserv: int = 0


class StaCubic(DGSElement):
    element_type = 'StaCubic'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('obj_bus', 'i', 'DGS field obj_bus (i)', py_name='obj_bus'),
        PfProperty('obj_id', 'p', 'DGS field obj_id (p)', py_name='obj_id'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('it2p1', 'i', 'DGS field it2p1 (i)', py_name='it2p1'),
        PfProperty('it2p2', 'i', 'DGS field it2p2 (i)', py_name='it2p2'),
        PfProperty('it2p3', 'i', 'DGS field it2p3 (i)', py_name='it2p3'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.chr_name: str = ""
        self.obj_bus: int = 0
        self.obj_id: str = ""
        self.for_name: str = ""
        self.it2p1: int = 0
        self.it2p2: int = 0
        self.it2p3: int = 0


class StaSwitch(DGSElement):
    element_type = 'StaSwitch'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('on_off', 'i', 'DGS field on_off (i)', py_name='on_off'),
        PfProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        PfProperty('iUse', 'i', 'DGS field iUse (i)', py_name='iUse'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('aUsage', 'a', 'DGS field aUsage (a)', py_name='aUsage'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.on_off: int = 0
        self.typ_id: str = ""
        self.iUse: int = 0
        self.for_name: str = ""
        self.aUsage: str = ""


class TypAsmo(DGSElement):
    element_type = 'TypAsmo'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('i_mode', 'i', 'DGS field i_mode (i)', py_name='i_mode'),
        PfProperty('aiazn', 'r', 'DGS field aiazn (r)', py_name='aiazn'),
        PfProperty('amazn', 'r', 'DGS field amazn (r)', py_name='amazn'),
        PfProperty('amkzn', 'r', 'DGS field amkzn (r)', py_name='amkzn'),
        PfProperty('anend', 'r', 'DGS field anend (r)', py_name='anend'),
        PfProperty('cosn', 'r', 'DGS field cosn (r)', py_name='cosn'),
        PfProperty('effic', 'r', 'DGS field effic (r)', py_name='effic'),
        PfProperty('frequ', 'r', 'DGS field frequ (r)', py_name='frequ'),
        PfProperty('i_cage', 'i', 'DGS field i_cage (i)', py_name='i_cage'),
        PfProperty('nppol', 'i', 'DGS field nppol (i)', py_name='nppol'),
        PfProperty('pgn', 'r', 'DGS field pgn (r)', py_name='pgn'),
        PfProperty('ugn', 'r', 'DGS field ugn (r)', py_name='ugn'),
        PfProperty('xmrtr', 'r', 'DGS field xmrtr (r)', py_name='xmrtr'),
        PfProperty('xstr', 'r', 'DGS field xstr (r)', py_name='xstr'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.i_mode: int = 0
        self.aiazn: float = 0.0
        self.amazn: float = 0.0
        self.amkzn: float = 0.0
        self.anend: float = 0.0
        self.cosn: float = 0.0
        self.effic: float = 0.0
        self.frequ: float = 0.0
        self.i_cage: int = 0
        self.nppol: int = 0
        self.pgn: float = 0.0
        self.ugn: float = 0.0
        self.xmrtr: float = 0.0
        self.xstr: float = 0.0


class TypFuse(DGSElement):
    element_type = 'TypFuse'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('frq', 'r', 'DGS field frq (r)', py_name='frq'),
        PfProperty('irat', 'r', 'DGS field irat (r)', py_name='irat'),
        PfProperty('urat', 'r', 'DGS field urat (r)', py_name='urat'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.frq: float = 0.0
        self.irat: float = 0.0
        self.urat: float = 0.0


class TypLne(DGSElement):
    element_type = 'TypLne'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('uline', 'r', 'DGS field uline (r)', py_name='uline'),
        PfProperty('sline', 'r', 'DGS field sline (r)', py_name='sline'),
        PfProperty('aohl_', 'a:3', 'DGS field aohl_ (a:3)', py_name='aohl_'),
        PfProperty('rline', 'r', 'DGS field rline (r)', py_name='rline'),
        PfProperty('xline', 'r', 'DGS field xline (r)', py_name='xline'),
        PfProperty('cline', 'r', 'DGS field cline (r)', py_name='cline'),
        PfProperty('rline0', 'r', 'DGS field rline0 (r)', py_name='rline0'),
        PfProperty('xline0', 'r', 'DGS field xline0 (r)', py_name='xline0'),
        PfProperty('cline0', 'r', 'DGS field cline0 (r)', py_name='cline0'),
        PfProperty('rtemp', 'r', 'DGS field rtemp (r)', py_name='rtemp'),
        PfProperty('Ithr', 'r', 'DGS field Ithr (r)', py_name='Ithr'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('nlnph', 'i', 'DGS field nlnph (i)', py_name='nlnph'),
        PfProperty('nneutral', 'i', 'DGS field nneutral (i)', py_name='nneutral'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('InomAir', 'r', 'DGS field InomAir (r)', py_name='InomAir'),
        PfProperty('cohl_', 'i', 'DGS field cohl_ (i)', py_name='cohl_'),
        PfProperty('tmax', 'r', 'DGS field tmax (r)', py_name='tmax'),
        PfProperty('systp', 'i', 'DGS field systp (i)', py_name='systp'),
        PfProperty('frnom', 'r', 'DGS field frnom (r)', py_name='frnom'),
        PfProperty('mlei', 'a:2', 'DGS field mlei (a:2)', py_name='mlei'),
        PfProperty('bline', 'r', 'DGS field bline (r)', py_name='bline'),
        PfProperty('bline0', 'r', 'DGS field bline0 (r)', py_name='bline0'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.uline: float = 0.0
        self.sline: float = 0.0
        self.aohl_: str = ""
        self.rline: float = 0.0
        self.xline: float = 0.0
        self.cline: float = 0.0
        self.rline0: float = 0.0
        self.xline0: float = 0.0
        self.cline0: float = 0.0
        self.rtemp: float = 0.0
        self.Ithr: float = 0.0
        self.chr_name: str = ""
        self.nlnph: int = 0
        self.nneutral: int = 0
        self.for_name: str = ""
        self.InomAir: float = 0.0
        self.cohl_: int = 0
        self.tmax: float = 0.0
        self.systp: int = 0
        self.frnom: float = 0.0
        self.mlei: str = ""
        self.bline: float = 0.0
        self.bline0: float = 0.0


class TypLod(DGSElement):
    element_type = 'TypLod'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('kpu', 'r', 'DGS field kpu (r)', py_name='kpu'),
        PfProperty('kqu', 'r', 'DGS field kqu (r)', py_name='kqu'),
        PfProperty('systp', 'i', 'DGS field systp (i)', py_name='systp'),
        PfProperty('phtech', 'i', 'DGS field phtech (i)', py_name='phtech'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('aP', 'r', 'DGS field aP (r)', py_name='aP'),
        PfProperty('bP', 'r', 'DGS field bP (r)', py_name='bP'),
        PfProperty('kpu0', 'r', 'DGS field kpu0 (r)', py_name='kpu0'),
        PfProperty('kpu1', 'r', 'DGS field kpu1 (r)', py_name='kpu1'),
        PfProperty('aQ', 'r', 'DGS field aQ (r)', py_name='aQ'),
        PfProperty('bQ', 'r', 'DGS field bQ (r)', py_name='bQ'),
        PfProperty('kqu0', 'r', 'DGS field kqu0 (r)', py_name='kqu0'),
        PfProperty('kqu1', 'r', 'DGS field kqu1 (r)', py_name='kqu1'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.kpu: float = 0.0
        self.kqu: float = 0.0
        self.systp: int = 0
        self.phtech: int = 0
        self.for_name: str = ""
        self.aP: float = 0.0
        self.bP: float = 0.0
        self.kpu0: float = 0.0
        self.kpu1: float = 0.0
        self.aQ: float = 0.0
        self.bQ: float = 0.0
        self.kqu0: float = 0.0
        self.kqu1: float = 0.0


class TypSym(DGSElement):
    element_type = 'TypSym'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('sgn', 'r', 'DGS field sgn (r)', py_name='sgn'),
        PfProperty('ugn', 'r', 'DGS field ugn (r)', py_name='ugn'),
        PfProperty('cosn', 'r', 'DGS field cosn (r)', py_name='cosn'),
        PfProperty('xd', 'r', 'DGS field xd (r)', py_name='xd'),
        PfProperty('xq', 'r', 'DGS field xq (r)', py_name='xq'),
        PfProperty('xdsss', 'r', 'DGS field xdsss (r)', py_name='xdsss'),
        PfProperty('rstr', 'r', 'DGS field rstr (r)', py_name='rstr'),
        PfProperty('xdsat', 'r', 'DGS field xdsat (r)', py_name='xdsat'),
        PfProperty('satur', 'i', 'DGS field satur (i)', py_name='satur'),
        PfProperty('Q_min', 'r', 'DGS field Q_min (r)', py_name='Q_min'),
        PfProperty('Q_max', 'r', 'DGS field Q_max (r)', py_name='Q_max'),
        PfProperty('q_min', 'r', 'DGS field q_min (r)', py_name='q_min'),
        PfProperty('q_max', 'r', 'DGS field q_max (r)', py_name='q_max'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('nphase', 'i', 'DGS field nphase (i)', py_name='nphase'),
        PfProperty('nslty', 'i', 'DGS field nslty (i)', py_name='nslty'),
        PfProperty('x0sy', 'r', 'DGS field x0sy (r)', py_name='x0sy'),
        PfProperty('r0sy', 'r', 'DGS field r0sy (r)', py_name='r0sy'),
        PfProperty('x2sy', 'r', 'DGS field x2sy (r)', py_name='x2sy'),
        PfProperty('r2sy', 'r', 'DGS field r2sy (r)', py_name='r2sy'),
        PfProperty('iopt_data', 'i', 'DGS field iopt_data (i)', py_name='iopt_data'),
        PfProperty('xds', 'r', 'DGS field xds (r)', py_name='xds'),
        PfProperty('xqs', 'r', 'DGS field xqs (r)', py_name='xqs'),
        PfProperty('xl', 'r', 'DGS field xl (r)', py_name='xl'),
        PfProperty('xdss', 'r', 'DGS field xdss (r)', py_name='xdss'),
        PfProperty('xqss', 'r', 'DGS field xqss (r)', py_name='xqss'),
        PfProperty('xrlq', 'r', 'DGS field xrlq (r)', py_name='xrlq'),
        PfProperty('tds', 'r', 'DGS field tds (r)', py_name='tds'),
        PfProperty('tqs', 'r', 'DGS field tqs (r)', py_name='tqs'),
        PfProperty('tdss', 'r', 'DGS field tdss (r)', py_name='tdss'),
        PfProperty('tqss', 'r', 'DGS field tqss (r)', py_name='tqss'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.sgn: float = 0.0
        self.ugn: float = 0.0
        self.cosn: float = 0.0
        self.xd: float = 0.0
        self.xq: float = 0.0
        self.xdsss: float = 0.0
        self.rstr: float = 0.0
        self.xdsat: float = 0.0
        self.satur: int = 0
        self.Q_min: float = 0.0
        self.Q_max: float = 0.0
        self.q_min: float = 0.0
        self.q_max: float = 0.0
        self.for_name: str = ""
        self.nphase: int = 0
        self.nslty: int = 0
        self.x0sy: float = 0.0
        self.r0sy: float = 0.0
        self.x2sy: float = 0.0
        self.r2sy: float = 0.0
        self.iopt_data: int = 0
        self.xds: float = 0.0
        self.xqs: float = 0.0
        self.xl: float = 0.0
        self.xdss: float = 0.0
        self.xqss: float = 0.0
        self.xrlq: float = 0.0
        self.tds: float = 0.0
        self.tqs: float = 0.0
        self.tdss: float = 0.0
        self.tqss: float = 0.0


class TypTr2(DGSElement):
    element_type = 'TypTr2'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('strn', 'r', 'DGS field strn (r)', py_name='strn'),
        PfProperty('frnom', 'r', 'DGS field frnom (r)', py_name='frnom'),
        PfProperty('utrn_h', 'r', 'DGS field utrn_h (r)', py_name='utrn_h'),
        PfProperty('utrn_l', 'r', 'DGS field utrn_l (r)', py_name='utrn_l'),
        PfProperty('uktr', 'r', 'DGS field uktr (r)', py_name='uktr'),
        PfProperty('pcutr', 'r', 'DGS field pcutr (r)', py_name='pcutr'),
        PfProperty('uk0tr', 'r', 'DGS field uk0tr (r)', py_name='uk0tr'),
        PfProperty('ur0tr', 'r', 'DGS field ur0tr (r)', py_name='ur0tr'),
        PfProperty('tr2cn_h', 'a:2', 'DGS field tr2cn_h (a:2)', py_name='tr2cn_h'),
        PfProperty('tr2cn_l', 'a:2', 'DGS field tr2cn_l (a:2)', py_name='tr2cn_l'),
        PfProperty('nt2ag', 'r', 'DGS field nt2ag (r)', py_name='nt2ag'),
        PfProperty('curmg', 'r', 'DGS field curmg (r)', py_name='curmg'),
        PfProperty('pfe', 'r', 'DGS field pfe (r)', py_name='pfe'),
        PfProperty('zx0hl_n', 'r', 'DGS field zx0hl_n (r)', py_name='zx0hl_n'),
        PfProperty('tap_side', 'i', 'DGS field tap_side (i)', py_name='tap_side'),
        PfProperty('dutap', 'r', 'DGS field dutap (r)', py_name='dutap'),
        PfProperty('phitr', 'r', 'DGS field phitr (r)', py_name='phitr'),
        PfProperty('nntap0', 'i', 'DGS field nntap0 (i)', py_name='nntap0'),
        PfProperty('ntpmn', 'i', 'DGS field ntpmn (i)', py_name='ntpmn'),
        PfProperty('ntpmx', 'i', 'DGS field ntpmx (i)', py_name='ntpmx'),
        PfProperty('manuf', 'a:20', 'DGS field manuf (a:20)', py_name='manuf'),
        PfProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('nt2ph', 'i', 'DGS field nt2ph (i)', py_name='nt2ph'),
        PfProperty('itapch', 'i', 'DGS field itapch (i)', py_name='itapch'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.strn: float = 0.0
        self.frnom: float = 0.0
        self.utrn_h: float = 0.0
        self.utrn_l: float = 0.0
        self.uktr: float = 0.0
        self.pcutr: float = 0.0
        self.uk0tr: float = 0.0
        self.ur0tr: float = 0.0
        self.tr2cn_h: str = ""
        self.tr2cn_l: str = ""
        self.nt2ag: float = 0.0
        self.curmg: float = 0.0
        self.pfe: float = 0.0
        self.zx0hl_n: float = 0.0
        self.tap_side: int = 0
        self.dutap: float = 0.0
        self.phitr: float = 0.0
        self.nntap0: int = 0
        self.ntpmn: int = 0
        self.ntpmx: int = 0
        self.manuf: str = ""
        self.chr_name: str = ""
        self.for_name: str = ""
        self.nt2ph: int = 0
        self.itapch: int = 0


class TypTr3(DGSElement):
    element_type = 'TypTr3'
    properties_list = [
        PfProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        PfProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        PfProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        PfProperty('curm3', 'r', 'DGS field curm3 (r)', py_name='curm3'),
        PfProperty('du3tp_h', 'r', 'DGS field du3tp_h (r)', py_name='du3tp_h'),
        PfProperty('du3tp_l', 'r', 'DGS field du3tp_l (r)', py_name='du3tp_l'),
        PfProperty('du3tp_m', 'r', 'DGS field du3tp_m (r)', py_name='du3tp_m'),
        PfProperty('n3tmn_h', 'i', 'DGS field n3tmn_h (i)', py_name='n3tmn_h'),
        PfProperty('n3tmn_l', 'i', 'DGS field n3tmn_l (i)', py_name='n3tmn_l'),
        PfProperty('n3tmn_m', 'i', 'DGS field n3tmn_m (i)', py_name='n3tmn_m'),
        PfProperty('n3tmx_h', 'i', 'DGS field n3tmx_h (i)', py_name='n3tmx_h'),
        PfProperty('n3tmx_l', 'i', 'DGS field n3tmx_l (i)', py_name='n3tmx_l'),
        PfProperty('n3tmx_m', 'i', 'DGS field n3tmx_m (i)', py_name='n3tmx_m'),
        PfProperty('n3tp0_h', 'i', 'DGS field n3tp0_h (i)', py_name='n3tp0_h'),
        PfProperty('n3tp0_l', 'i', 'DGS field n3tp0_l (i)', py_name='n3tp0_l'),
        PfProperty('n3tp0_m', 'i', 'DGS field n3tp0_m (i)', py_name='n3tp0_m'),
        PfProperty('nt3ag_h', 'r', 'DGS field nt3ag_h (r)', py_name='nt3ag_h'),
        PfProperty('nt3ag_l', 'r', 'DGS field nt3ag_l (r)', py_name='nt3ag_l'),
        PfProperty('nt3ag_m', 'r', 'DGS field nt3ag_m (r)', py_name='nt3ag_m'),
        PfProperty('pcut3_h', 'r', 'DGS field pcut3_h (r)', py_name='pcut3_h'),
        PfProperty('pcut3_l', 'r', 'DGS field pcut3_l (r)', py_name='pcut3_l'),
        PfProperty('pcut3_m', 'r', 'DGS field pcut3_m (r)', py_name='pcut3_m'),
        PfProperty('pfe', 'r', 'DGS field pfe (r)', py_name='pfe'),
        PfProperty('ph3tr_h', 'r', 'DGS field ph3tr_h (r)', py_name='ph3tr_h'),
        PfProperty('ph3tr_l', 'r', 'DGS field ph3tr_l (r)', py_name='ph3tr_l'),
        PfProperty('ph3tr_m', 'r', 'DGS field ph3tr_m (r)', py_name='ph3tr_m'),
        PfProperty('strn3_h', 'r', 'DGS field strn3_h (r)', py_name='strn3_h'),
        PfProperty('strn3_l', 'r', 'DGS field strn3_l (r)', py_name='strn3_l'),
        PfProperty('strn3_m', 'r', 'DGS field strn3_m (r)', py_name='strn3_m'),
        PfProperty('tr3cn_h', 'a', 'DGS field tr3cn_h (a)', py_name='tr3cn_h'),
        PfProperty('tr3cn_l', 'a', 'DGS field tr3cn_l (a)', py_name='tr3cn_l'),
        PfProperty('tr3cn_m', 'a', 'DGS field tr3cn_m (a)', py_name='tr3cn_m'),
        PfProperty('uk0hl', 'r', 'DGS field uk0hl (r)', py_name='uk0hl'),
        PfProperty('uk0hm', 'r', 'DGS field uk0hm (r)', py_name='uk0hm'),
        PfProperty('uk0ml', 'r', 'DGS field uk0ml (r)', py_name='uk0ml'),
        PfProperty('uktr3_h', 'r', 'DGS field uktr3_h (r)', py_name='uktr3_h'),
        PfProperty('uktr3_l', 'r', 'DGS field uktr3_l (r)', py_name='uktr3_l'),
        PfProperty('uktr3_m', 'r', 'DGS field uktr3_m (r)', py_name='uktr3_m'),
        PfProperty('ur0hl', 'r', 'DGS field ur0hl (r)', py_name='ur0hl'),
        PfProperty('ur0hm', 'r', 'DGS field ur0hm (r)', py_name='ur0hm'),
        PfProperty('ur0ml', 'r', 'DGS field ur0ml (r)', py_name='ur0ml'),
        PfProperty('utrn3_h', 'r', 'DGS field utrn3_h (r)', py_name='utrn3_h'),
        PfProperty('utrn3_l', 'r', 'DGS field utrn3_l (r)', py_name='utrn3_l'),
        PfProperty('utrn3_m', 'r', 'DGS field utrn3_m (r)', py_name='utrn3_m'),
        PfProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        PfProperty('itapos', 'i', 'DGS field itapos (i)', py_name='itapos'),
        PfProperty('i3loc', 'i', 'DGS field i3loc (i)', py_name='i3loc'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.curm3: float = 0.0
        self.du3tp_h: float = 0.0
        self.du3tp_l: float = 0.0
        self.du3tp_m: float = 0.0
        self.n3tmn_h: int = 0
        self.n3tmn_l: int = 0
        self.n3tmn_m: int = 0
        self.n3tmx_h: int = 0
        self.n3tmx_l: int = 0
        self.n3tmx_m: int = 0
        self.n3tp0_h: int = 0
        self.n3tp0_l: int = 0
        self.n3tp0_m: int = 0
        self.nt3ag_h: float = 0.0
        self.nt3ag_l: float = 0.0
        self.nt3ag_m: float = 0.0
        self.pcut3_h: float = 0.0
        self.pcut3_l: float = 0.0
        self.pcut3_m: float = 0.0
        self.pfe: float = 0.0
        self.ph3tr_h: float = 0.0
        self.ph3tr_l: float = 0.0
        self.ph3tr_m: float = 0.0
        self.strn3_h: float = 0.0
        self.strn3_l: float = 0.0
        self.strn3_m: float = 0.0
        self.tr3cn_h: str = ""
        self.tr3cn_l: str = ""
        self.tr3cn_m: str = ""
        self.uk0hl: float = 0.0
        self.uk0hm: float = 0.0
        self.uk0ml: float = 0.0
        self.uktr3_h: float = 0.0
        self.uktr3_l: float = 0.0
        self.uktr3_m: float = 0.0
        self.ur0hl: float = 0.0
        self.ur0hm: float = 0.0
        self.ur0ml: float = 0.0
        self.utrn3_h: float = 0.0
        self.utrn3_l: float = 0.0
        self.utrn3_m: float = 0.0
        self.for_name: str = ""
        self.itapos: int = 0
        self.i3loc: int = 0
