# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Callable, Any, Dict, List
from typing import Callable, Any, Dict, List


# =========================================================
# PfProperty
# =========================================================

def _default_converter(dgs_type: str):
    if dgs_type.startswith("a"):
        return str
    if dgs_type == "i":
        return int
    if dgs_type == "r":
        return float
    if dgs_type == "b":
        return lambda x: bool(int(x))
    return str  # p, unknown, references


class DgsProperty:
    """
    DgsProperty
    """
    def __init__(
        self,
        name: str,
        dgs_type: str,
        description: str,
        converter: Callable[[str], Any] | None = None,
    ):
        self.name = name
        self.dgs_type = dgs_type
        self.description = description
        self.converter = converter or _default_converter(dgs_type)

    def parse(self, value: str):
        """

        :param value:
        :return:
        """
        if value == "" or value is None:
            return None
        return self.converter(value)

    def format(self, value) -> str:
        """

        :param value:
        :return:
        """
        if value is None:
            return ""
        if self.dgs_type == "b":
            return "1" if value else "0"
        return str(value)


# =========================================================
# Base class
# =========================================================

class DGSElement:
    """
    DGS element
    """
    element_type: str
    properties_list: List[DgsProperty]
    properties: Dict[str, DgsProperty]

    def __init_subclass__(cls):
        cls.properties = {p.name: p for p in cls.properties_list}

    @classmethod
    def parse_line(cls, line: str):
        """

        :param line:
        :return:
        """
        parts = line.rstrip().split(";")
        obj = cls.__new__(cls)

        for prop, raw in zip(cls.properties_list, parts):
            setattr(obj, prop.name, prop.parse(raw))

        for prop in cls.properties_list[len(parts):]:
            setattr(obj, prop.name, None)

        return obj

    def to_dgs_line(self) -> str:
        """

        :return:
        """
        return ";".join(
            prop.format(getattr(self, prop.name))
            for prop in self.properties_list
        )


# =========================================================
# GENERAL / INFRASTRUCTURE
# =========================================================

class General(DGSElement):
    element_type = "General"
    properties_list = [
        DgsProperty("ID", "a:40", "Unique object identifier"),
        DgsProperty("Descr", "a:40", "General description field"),
        DgsProperty("Val", "a:40", "General value field"),
    ]


class IntFolder(DGSElement):
    element_type = "IntFolder"
    properties_list = [
        DgsProperty("ID", "a:40", "Folder object identifier"),
        DgsProperty("loc_name", "a", "Folder name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("iopt_typ", "i", "Folder option type"),
    ]


# =========================================================
# NETWORK ELEMENTS
# =========================================================

class ElmNet(DGSElement):
    element_type = "ElmNet"
    properties_list = [
        DgsProperty("ID", "a:40", "Network object identifier"),
        DgsProperty("loc_name", "a", "Network name"),
        DgsProperty("for_name", "a", "Formatted name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("frnom", "r", "Nominal system frequency"),
        DgsProperty("pDiagram", "p", "Diagram reference"),
    ]


class ElmTerm(DGSElement):
    element_type = "ElmTerm"
    properties_list = [
        DgsProperty("ID", "a:40", "Terminal object identifier"),
        DgsProperty("loc_name", "a", "Terminal name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("typ_id", "p", "Terminal type reference"),
        DgsProperty("iUsage", "i", "Terminal usage flag"),
        DgsProperty("uknom", "r", "Nominal voltage"),
        DgsProperty("chr_name", "a", "Characteristic reference name"),
        DgsProperty("outserv", "i", "Out-of-service flag"),
    ]


class ElmSubstat(DGSElement):
    element_type = "ElmSubstat"
    properties_list = [
        DgsProperty("ID", "a:40", "Substation object identifier"),
        DgsProperty("loc_name", "a", "Substation name"),
        DgsProperty("for_name", "a", "Formatted name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("Unom", "r", "Nominal voltage"),
        DgsProperty("sShort", "a", "Short name"),
        DgsProperty("sType", "a", "Substation type"),
        DgsProperty("GPSlat", "r", "Latitude"),
        DgsProperty("GPSlon", "r", "Longitude"),
        DgsProperty("pRA", "p", "Regional area reference"),
    ]


class ElmSite(DGSElement):
    element_type = "ElmSite"
    properties_list = [
        DgsProperty("ID", "a:40", "Site object identifier"),
        DgsProperty("loc_name", "a", "Site name"),
        DgsProperty("for_name", "a", "Formatted name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("sType", "a", "Site type"),
        DgsProperty("GPSlat", "r", "Latitude"),
        DgsProperty("GPSlon", "r", "Longitude"),
    ]


class ElmCoup(DGSElement):
    element_type = "ElmCoup"
    properties_list = [
        DgsProperty("ID", "a:40", "Coupler object identifier"),
        DgsProperty("loc_name", "a", "Coupler name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("bus1", "p", "First terminal reference"),
        DgsProperty("bus2", "p", "Second terminal reference"),
        DgsProperty("on_off", "i", "Switching state"),
    ]


class ElmXnet(DGSElement):
    element_type = "ElmXnet"
    properties_list = [
        DgsProperty("ID", "a:40", "External network identifier"),
        DgsProperty("loc_name", "a", "External network name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
    ]


# =========================================================
# BRANCHES / LOADS / MACHINES
# =========================================================

class ElmLne(DGSElement):
    element_type = "ElmLne"
    properties_list = [
        DgsProperty("ID", "a:40", "Line object identifier"),
        DgsProperty("loc_name", "a", "Line name"),
        DgsProperty("for_name", "a", "Formatted name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("typ_id", "p", "Line type reference"),
        DgsProperty("chr_name", "a", "Characteristic name"),
        DgsProperty("dline", "r", "Line length"),
        DgsProperty("fline", "r", "Frequency factor"),
        DgsProperty("outserv", "i", "Out-of-service flag"),
        DgsProperty("nlnum", "i", "Number of parallel lines"),
        DgsProperty("inAir", "i", "Overhead/underground flag"),
    ]


class ElmLnesec(DGSElement):
    element_type = "ElmLnesec"
    properties_list = [
        DgsProperty("ID", "a:40", "Line section identifier"),
        DgsProperty("loc_name", "a", "Line section name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("typ_id", "p", "Line section type reference"),
        DgsProperty("chr_name", "a", "Characteristic name"),
    ]


class ElmLod(DGSElement):
    element_type = "ElmLod"
    properties_list = [
        DgsProperty("ID", "a:40", "Load object identifier"),
        DgsProperty("loc_name", "a", "Load name"),
        DgsProperty("for_name", "a", "Formatted name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("typ_id", "p", "Load type reference"),
        DgsProperty("chr_name", "a", "Characteristic name"),
        DgsProperty("plini", "r", "Initial active power"),
        DgsProperty("qlini", "r", "Initial reactive power"),
        DgsProperty("scale0", "r", "Scaling factor"),
        DgsProperty("outserv", "i", "Out-of-service flag"),
        DgsProperty("classif", "a", "Load classification"),
    ]


class ElmLodlv(DGSElement):
    element_type = "ElmLodlv"
    properties_list = [
        DgsProperty("ID", "a:40", "Low-voltage load identifier"),
        DgsProperty("loc_name", "a", "Load name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("plini", "r", "Initial active power"),
        DgsProperty("qlini", "r", "Initial reactive power"),
    ]


class ElmLodlvp(DGSElement):
    element_type = "ElmLodlvp"
    properties_list = [
        DgsProperty("ID", "a:40", "LV load (phase) identifier"),
        DgsProperty("loc_name", "a", "Load name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("plini", "r", "Initial active power"),
        DgsProperty("qlini", "r", "Initial reactive power"),
    ]


class ElmSym(DGSElement):
    element_type = "ElmSym"
    properties_list = [
        DgsProperty("ID", "a:40", "Synchronous machine identifier"),
        DgsProperty("loc_name", "a", "Machine name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("typ_id", "p", "Machine type reference"),
        DgsProperty("ngnum", "i", "Number of generators"),
        DgsProperty("outserv", "i", "Out-of-service flag"),
        DgsProperty("pgini", "r", "Initial active power"),
        DgsProperty("qgini", "r", "Initial reactive power"),
        DgsProperty("usetp", "r", "Voltage setpoint"),
        DgsProperty("iv_mode", "i", "Voltage control mode"),
        DgsProperty("q_min", "r", "Minimum reactive power"),
        DgsProperty("q_max", "r", "Maximum reactive power"),
    ]


class ElmGenstat(DGSElement):
    element_type = "ElmGenstat"
    properties_list = [
        DgsProperty("ID", "a:40", "Static generator identifier"),
        DgsProperty("loc_name", "a", "Generator name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("pgini", "r", "Initial active power"),
        DgsProperty("qgini", "r", "Initial reactive power"),
        DgsProperty("cosn", "r", "Power factor"),
        DgsProperty("av_mode", "a", "Voltage control mode"),
        DgsProperty("ip_ctrl", "i", "Power control flag"),
    ]


class ElmFeeder(DGSElement):
    element_type = "ElmFeeder"
    properties_list = [
        DgsProperty("ID", "a:40", "Feeder identifier"),
        DgsProperty("loc_name", "a", "Feeder name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("obj_id", "p", "Referenced object"),
        DgsProperty("Iset", "r", "Current setting"),
        DgsProperty("i_scale", "i", "Scaling flag"),
        DgsProperty("icolor", "i", "Color index"),
        DgsProperty("iorient", "i", "Orientation flag"),
        DgsProperty("outserv", "i", "Out-of-service flag"),
    ]


# =========================================================
# GRAPHICS / CHARACTERISTICS
# =========================================================

class StaSwitch(DGSElement):
    element_type = "StaSwitch"
    properties_list = [
        DgsProperty("ID", "a:40", "Graphical switch identifier"),
        DgsProperty("loc_name", "a", "Switch name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("on_off", "i", "Switch state"),
        DgsProperty("typ_id", "p", "Switch type reference"),
        DgsProperty("iUse", "i", "Usage flag"),
    ]


class StaCubic(DGSElement):
    element_type = "StaCubic"
    properties_list = [
        DgsProperty("ID", "a:40", "Graphical cube identifier"),
        DgsProperty("loc_name", "a", "Cube name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("chr_name", "a", "Characteristic name"),
        DgsProperty("obj_bus", "p", "Bus reference"),
        DgsProperty("obj_id", "p", "Object reference"),
    ]


class ChaRef(DGSElement):
    element_type = "ChaRef"
    properties_list = [
        DgsProperty("ID", "a:40", "Characteristic reference identifier"),
        DgsProperty("loc_name", "a", "Characteristic name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
    ]


class ChaVec(DGSElement):
    element_type = "ChaVec"
    properties_list = [
        DgsProperty("ID", "a:40", "Characteristic vector identifier"),
        DgsProperty("loc_name", "a", "Vector name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("scale", "p", "Scale reference"),
        DgsProperty("prox", "i", "Interpolation flag"),
        DgsProperty("vector_size", "i", "Vector length"),
        DgsProperty("v0", "r", "Vector value 0"),
        DgsProperty("v1", "r", "Vector value 1"),
        DgsProperty("v2", "r", "Vector value 2"),
    ]


class IntGrf(DGSElement):
    element_type = "IntGrf"
    properties_list = [
        DgsProperty("ID", "a:40", "Graphic object identifier"),
        DgsProperty("loc_name", "a", "Graphic object name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
    ]


class IntGrfnet(DGSElement):
    element_type = "IntGrfnet"
    properties_list = [
        DgsProperty("ID", "a:40", "Graphic network identifier"),
        DgsProperty("loc_name", "a", "Graphic network name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
    ]


class IntGrfcon(DGSElement):
    element_type = "IntGrfcon"
    properties_list = [
        DgsProperty("ID", "a:40", "Graphic connection identifier"),
        DgsProperty("loc_name", "a", "Graphic connection name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("rX0", "r", "X coordinate 0"),
        DgsProperty("rX1", "r", "X coordinate 1"),
        DgsProperty("rX2", "r", "X coordinate 2"),
        DgsProperty("rY0", "r", "Y coordinate 0"),
        DgsProperty("rY1", "r", "Y coordinate 1"),
        DgsProperty("rY2", "r", "Y coordinate 2"),
    ]


# =========================================================
# TYPES
# =========================================================

class TypAsmo(DGSElement):
    element_type = "TypAsmo"
    properties_list = [
        DgsProperty("ID", "a:40", "Asynchronous machine type identifier"),
        DgsProperty("loc_name", "a", "Type name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("i_mode", "i", "Operating mode"),
        DgsProperty("frequ", "r", "Nominal frequency"),
        DgsProperty("i_cage", "i", "Rotor cage flag"),
        DgsProperty("nppol", "i", "Number of pole pairs"),
        DgsProperty("pgn", "r", "Nominal power"),
        DgsProperty("ugn", "r", "Nominal voltage"),
        DgsProperty("xmrtr", "r", "Magnetizing reactance"),
        DgsProperty("xstr", "r", "Stator reactance"),
    ]


class TypFuse(DGSElement):
    element_type = "TypFuse"
    properties_list = [
        DgsProperty("ID", "a:40", "Fuse type identifier"),
        DgsProperty("loc_name", "a", "Fuse type name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("frq", "r", "Nominal frequency"),
        DgsProperty("irat", "r", "Rated current"),
        DgsProperty("urat", "r", "Rated voltage"),
    ]


class TypLne(DGSElement):
    element_type = "TypLne"
    properties_list = [
        DgsProperty("ID", "a:40", "Line type identifier"),
        DgsProperty("loc_name", "a", "Line type name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("uline", "r", "Nominal voltage"),
        DgsProperty("sline", "r", "Rated power"),
        DgsProperty("_unused", "a", "Unused placeholder field"),
        DgsProperty("rline0", "r", "Zero-sequence resistance"),
        DgsProperty("xline0", "r", "Zero-sequence reactance"),
        DgsProperty("cline0", "r", "Zero-sequence capacitance"),
        DgsProperty("rtemp", "r", "Temperature resistance"),
        DgsProperty("Ithr", "r", "Thermal current limit"),
        DgsProperty("chr_name", "a", "Characteristic name"),
    ]


class TypSym(DGSElement):
    element_type = "TypSym"
    properties_list = [
        DgsProperty("ID", "a:40", "Synchronous machine type identifier"),
        DgsProperty("loc_name", "a", "Type name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("sgn", "r", "Nominal apparent power"),
        DgsProperty("ugn", "r", "Nominal voltage"),
        DgsProperty("cosn", "r", "Nominal power factor"),
        DgsProperty("xd", "r", "Direct-axis reactance"),
        DgsProperty("xq", "r", "Quadrature-axis reactance"),
        DgsProperty("xdsss", "r", "Sub-subtransient reactance"),
        DgsProperty("rstr", "r", "Stator resistance"),
        DgsProperty("xdsat", "r", "Saturated reactance"),
        DgsProperty("satur", "r", "Saturation factor"),
    ]


class TypTr2(DGSElement):
    element_type = "TypTr2"
    properties_list = [
        DgsProperty("ID", "a:40", "Two-winding transformer type identifier"),
        DgsProperty("loc_name", "a", "Type name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("strn", "r", "Rated power"),
        DgsProperty("frnom", "r", "Nominal frequency"),
        DgsProperty("utr", "r", "Rated voltage"),
        DgsProperty("phitr", "r", "Phase shift"),
        DgsProperty("nntap0", "i", "Neutral tap position"),
        DgsProperty("ntpmn", "i", "Minimum tap"),
        DgsProperty("ntpmx", "i", "Maximum tap"),
        DgsProperty("manuf", "a", "Manufacturer"),
        DgsProperty("chr_name", "a", "Characteristic name"),
    ]


class TypTr3(DGSElement):
    element_type = "TypTr3"
    properties_list = [
        DgsProperty("ID", "a:40", "Three-winding transformer type identifier"),
        DgsProperty("loc_name", "a", "Type name"),
        DgsProperty("fold_id", "p", "Parent folder reference"),
        DgsProperty("strn", "r", "Rated power"),
        DgsProperty("frnom", "r", "Nominal frequency"),
        DgsProperty("utr", "r", "Rated voltage"),
        DgsProperty("phitr", "r", "Phase shift"),
        DgsProperty("nt3tap0", "i", "Neutral tap position"),
        DgsProperty("nt3pmn", "i", "Minimum tap"),
        DgsProperty("nt3pmx", "i", "Maximum tap"),
        DgsProperty("manuf", "a", "Manufacturer"),
        DgsProperty("chr_name", "a", "Characteristic name"),
    ]
