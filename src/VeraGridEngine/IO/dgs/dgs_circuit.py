# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
import sys
import os
from pathlib import Path
from typing import Dict, List, Type, Optional, Tuple
import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
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


def _populate_from_pf_object(pf_obj: DGSElement, dgs_cls: Type[DGSElement]):
    """
    Populate a DGSElement subclass from a PowerFactory API object,
    using the class schema (properties_list).
    Assumes the DGSElement has an explicit __init__.
    """
    elem = dgs_cls()

    for prop in dgs_cls.properties_list:
        name = prop.name

        if hasattr(pf_obj, name):
            try:
                value = getattr(pf_obj, name)
            except Exception:
                value = None
        else:
            value = None

        setattr(elem, name, value)

    return elem


def _ref_id(x):
    if x is None:
        return None
    s = str(x)
    return s.split("\\")[-1] if "\\" in s else s


def get_terminal_ids(element_id: str, cubics_by_objid):
    cbs = cubics_by_objid.get(_ref_id(element_id), [])
    # fold_id suele ser el ID del ElmTerm “padre”
    return [_ref_id(cb.fold_id) for cb in cbs if _ref_id(cb.fold_id) is not None]


def parse_header(line: str) -> Tuple[str, Dict[str, int]]:
    """
    Parse $$ header line and return property -> index map.
    """
    element_type = line[2:].split(";", 1)[0]
    parts = line.strip().split(';')[1:]  # skip $$ElementType
    header_map: Dict[str, int] = {}

    for i, name_stub in enumerate(parts):
        name_stub = parts[i]
        stubs = name_stub.split("(")
        prop_name = stubs[0] if len(stubs) > 0 else name_stub
        header_map[prop_name] = i

    return element_type, header_map


def get_branch_buses(elm_id: str,
                     stacubic_dict: Dict[str, List[int]],
                     buses: List[dev.Bus],
                     cubics_by_objid: Dict[str, List[StaCubic]],
                     bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.bus, dev.Bus]:
    """
    Function to get the buses from a branch element
    :param elm_id:
    :param stacubic_dict:
    :param buses:
    :return:
    """
    # Prefer robust mapping using StaCubic.fold_id -> ElmTerm.ID -> Bus
    term_ids = get_terminal_ids(element_id=elm_id, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 2:
        try:
            return bus_by_term_id[term_ids[0]], bus_by_term_id[term_ids[1]]
        except KeyError:
            # Fall back to legacy obj_bus indexing if terminal mapping is incomplete
            pass

    # Legacy fallback (index-based), kept for backward compatibility
    bus_ids = stacubic_dict.get(elm_id, None)
    if bus_ids is None:
        raise ValueError(f"No buses for the line {elm_id}")

    if len(bus_ids) != 2:
        raise ValueError(f"Not exactly 2 buses for the line {elm_id}")

    bus_from = buses[bus_ids[0]]
    bus_to = buses[bus_ids[1]]

    return bus_from, bus_to


def get_injection_bus(elm_id: str,
                      stacubic_dict: Dict[str, List[int]],
                      buses: List[dev.Bus],
                      cubics_by_objid: Dict[str, List[StaCubic]],
                      bus_by_term_id: Dict[str, dev.Bus]) -> dev.bus:
    """
    Function to get the bus from a injection element
    :param elm_id:
    :param stacubic_dict:
    :param buses:
    :return:
    """
    # Prefer robust mapping using StaCubic.fold_id -> ElmTerm.ID -> Bus
    term_ids = get_terminal_ids(element_id=elm_id, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 1:
        try:
            return bus_by_term_id[term_ids[0]]
        except KeyError:
            # Fall back to legacy obj_bus indexing if terminal mapping is incomplete
            pass

    # Legacy fallback (index-based), kept for backward compatibility
    bus_ids = stacubic_dict.get(elm_id, None)
    if bus_ids is None:
        raise ValueError(f"No buses for the element {elm_id}")

    if len(bus_ids) != 1:
        raise ValueError(f"Not exactly 1 bus for the element {elm_id}")

    return buses[bus_ids[0]]


def convert_dgs_to_bus(elmterm: ElmTerm,
                       pos_by_objid: Dict[str, Tuple[float, float]]) -> dev.Bus:
    """
    Convert ElmTerm to Bus
    :param elmterm: ElmTerm
    :param pos_by_objid: dictionary of graphical positions
    :return: Bus
    """
    tid = _ref_id(elmterm.ID)
    x, y = pos_by_objid.get(tid, (0.0, 0.0))
    bus = dev.Bus(
        name=elmterm.loc_name or f"Bus_{tid}",
        Vnom=float(elmterm.uknom or 0.0),
        vmin=0.9,
        vmax=1.1,
        xpos=float(x),
        ypos=float(-y),
        active=(int(elmterm.outserv or 0) == 0),
    )

    return bus


def convert_dgs_from_bus(bus: dev.Bus) -> ElmTerm:
    elm = ElmTerm()

    # TODO: implement conversion

    return elm


def convert_dgs_to_sequence_line(typlne: TypLne) -> dev.SequenceLineType:
    """
    Convert a TypLne to SequenceLineType
    :param typlne: TypLne
    :return: SequenceLineType
    """
    elm = dev.SequenceLineType(
        name=typlne.loc_name,
        R=typlne.rline,
        X=typlne.xline,
        B=typlne.bline,
        CnF=typlne.cline,
        R0=typlne.rline0,
        X0=typlne.xline0,
        B0=typlne.bline0,
        CnF0=typlne.cline0,
        Vnom=typlne.uline,
        Imax=typlne.sline,
        use_conductance=typlne.cline != 0.0
    )

    return elm


def _convert_pf_tr2_connection(code: str):
    """
    Convert a PowerFactory 2-character transformer connection code to VeraGrid enum when available.
    If the enum is not available or the code is unknown, return None and let defaults apply.
    """
    try:
        from VeraGridEngine.enumerations import WindingsConnection
    except Exception:
        return None

    if code is None:
        return None

    c = str(code).strip().upper()
    if c == "":
        return None

    # Common PowerFactory 2-char winding codes in DGS: Y, YN, D, Z, ZN
    try:
        return getattr(WindingsConnection, c)
    except AttributeError:
        return None


def convert_dgs_to_transformer_type(typtr2: TypTr2) -> dev.TransformerType:
    """
    Convert a TypTr2 to TransformerType
    :param typtr2: TypTr2
    :return: TransformerType
    """
    tpe = dev.TransformerType(hv_nominal_voltage=float(typtr2.utrn_h or 0.0),
                              lv_nominal_voltage=float(typtr2.utrn_l or 0.0),
                              nominal_power=float(typtr2.strn or 0.0),
                              copper_losses=float(typtr2.pcutr or 0.0),
                              iron_losses=float(typtr2.pfe or 0.0),
                              no_load_current=float(typtr2.curmg or 0.0),
                              short_circuit_voltage=float(typtr2.uktr or 0.0),
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              name=typtr2.loc_name)

    conn_hv = _convert_pf_tr2_connection(getattr(typtr2, "tr2cn_h", None))
    conn_lv = _convert_pf_tr2_connection(getattr(typtr2, "tr2cn_l", None))

    if conn_hv is not None and hasattr(tpe, "conn_hv"):
        tpe.conn_hv = conn_hv

    if conn_lv is not None and hasattr(tpe, "conn_lv"):
        tpe.conn_lv = conn_lv

    return tpe


def _order_hv_lv(bus_a: dev.Bus, bus_b: dev.Bus, logger: Logger, tr_name: str) -> Tuple[dev.Bus, dev.Bus]:
    """
    Order two buses as (HV, LV) based on nominal voltage.
    If voltages are equal or undefined, keep the original order and warn.
    """
    va = float(getattr(bus_a, "Vnom", 0.0) or 0.0)
    vb = float(getattr(bus_b, "Vnom", 0.0) or 0.0)

    if va == 0.0 or vb == 0.0:
        logger.add_warning(f"Transformer '{tr_name}': one or both buses have Vnom=0.0 (va={va}, vb={vb}).")
        return bus_a, bus_b

    if va > vb:
        return bus_a, bus_b
    if vb > va:
        return bus_b, bus_a

    logger.add_warning(f"Transformer '{tr_name}': HV/LV ambiguous (equal Vnom={va}). Keeping original order.")
    return bus_a, bus_b


def convert_dgs_to_transformer(tr2: ElmTr2,
                               buses: List[dev.Bus],
                               stacubic_dict: Dict[str, List[int]],
                               templates_dict: Dict[str, dev.TransformerType],
                               freq: float,
                               baseMVA: float,
                               logger: Logger,
                               cubics_by_objid: Dict[str, List[StaCubic]],
                               bus_by_term_id: Dict[str, dev.Bus]) -> dev.Transformer2W:
    """
    Convert ElmTr2 to Transformer2W
    :param tr2: ElmTr2
    :param buses:
    :param stacubic_dict:
    :param templates_dict:
    :param freq:
    :param baseMVA:
    :param logger:
    :param cubics_by_objid:
    :param bus_by_term_id:
    :return: Transformer2W
    """
    template = templates_dict.get(tr2.typ_id, None)
    if template is None:
        template = templates_dict.get(_ref_id(tr2.typ_id), None)

    if template is None:
        raise ValueError(f"No template for the transformer {tr2.ID}")

    # Check connectivity through robust StaCubic.fold_id mapping first (preferred)
    term_ids = get_terminal_ids(element_id=tr2.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) != 2:
        # Fall back to legacy check only if terminal mapping is not available
        bus_ids = stacubic_dict.get(tr2.ID, None)
        if bus_ids is None:
            raise ValueError(f"No buses for the transformer {tr2.ID}")

        if len(bus_ids) != 2:
            raise ValueError(f"Not exactly 2 buses for the transformer {tr2.ID}")

    bus_from, bus_to = get_branch_buses(elm_id=tr2.ID,
                                        stacubic_dict=stacubic_dict,
                                        buses=buses,
                                        cubics_by_objid=cubics_by_objid,
                                        bus_by_term_id=bus_by_term_id)

    bus_hv, bus_lv = _order_hv_lv(bus_a=bus_from,
                                  bus_b=bus_to,
                                  logger=logger,
                                  tr_name=tr2.loc_name)

    trafo = dev.Transformer2W(bus_from=bus_hv,
                              bus_to=bus_lv,
                              name=tr2.loc_name,
                              active=not tr2.outserv,
                              HV=max(bus_hv.Vnom, bus_lv.Vnom),
                              LV=min(bus_hv.Vnom, bus_lv.Vnom),
                              nominal_power=float(getattr(template, "Sn", getattr(template, "nominal_power", 0.001)) or 0.001),
                              copper_losses=float(getattr(template, "Pcu", getattr(template, "copper_losses", 0.0)) or 0.0),
                              iron_losses=float(getattr(template, "Pfe", getattr(template, "iron_losses", 0.0)) or 0.0),
                              no_load_current=float(getattr(template, "I0", getattr(template, "no_load_current", 0.0)) or 0.0),
                              short_circuit_voltage=float(getattr(template, "Vsc", getattr(template, "short_circuit_voltage", 0.0)) or 0.0),
                              template=template)

    trafo.apply_template(obj=template, Sbase=baseMVA, logger=logger)

    return trafo


def convert_dgs_to_line(lne: ElmLne,
                        buses: List[dev.Bus],
                        stacubic_dict: Dict[str, List[int]],
                        templates_dict: Dict[str, dev.SequenceLineType],
                        freq: float,
                        baseMVA: float,
                        logger: Logger,
                        cubics_by_objid: Dict[str, List[StaCubic]],
                        bus_by_term_id: Dict[str, dev.Bus]) -> dev.Line:
    """

    :param lne:
    :param buses:
    :param stacubic_dict:
    :param templates_dict:
    :param freq:
    :param baseMVA:
    :param logger:
    :return:
    """

    template = templates_dict.get(lne.typ_id, None)
    if template is None:
        raise ValueError(f"No template for the line {lne.ID}")

    # Check connectivity through robust StaCubic.fold_id mapping first (preferred)
    term_ids = get_terminal_ids(element_id=lne.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) != 2:
        # Fall back to legacy check only if terminal mapping is not available
        bus_ids = stacubic_dict.get(lne.ID, None)
        if bus_ids is None:
            raise ValueError(f"No buses for the line {lne.ID}")

        if len(bus_ids) != 2:
            raise ValueError(f"Not exactly 2 buses for the line {lne.ID}")

    bus_from, bus_to = get_branch_buses(elm_id=lne.ID,
                                        stacubic_dict=stacubic_dict,
                                        buses=buses,
                                        cubics_by_objid=cubics_by_objid,
                                        bus_by_term_id=bus_by_term_id)

    line = dev.Line(bus_from=bus_from,
                    bus_to=bus_to,
                    name=lne.loc_name,
                    active=not lne.outserv,
                    length=lne.dline)

    line.apply_template(obj=template, Sbase=baseMVA, freq=freq, logger=logger)

    return line


class DgsCircuit:
    """Strongly-typed container for a PowerFactory DGS file."""

    _ELEMENT_CLASSES: List[Type[DGSElement]] = [
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
        TypTr3,
    ]

    _REGISTRY: Dict[str, Type[DGSElement]] = {cls.element_type: cls for cls in _ELEMENT_CLASSES}

    def __init__(self) -> None:
        self.charefs: List[ChaRef] = list()
        self.chavecs: List[ChaVec] = list()
        self.elmasms: List[ElmAsm] = list()
        self.elmcoups: List[ElmCoup] = list()
        self.elmfeeders: List[ElmFeeder] = list()
        self.elmgenstats: List[ElmGenstat] = list()
        self.elmlnes: List[ElmLne] = list()
        self.elmlnesecs: List[ElmLnesec] = list()
        self.elmlods: List[ElmLod] = list()
        self.elmlodlvs: List[ElmLodlv] = list()
        self.elmlodlvps: List[ElmLodlvp] = list()
        self.elmnets: List[ElmNet] = list()
        self.elmshnts: List[ElmShnt] = list()
        self.elmsites: List[ElmSite] = list()
        self.elmsubstats: List[ElmSubstat] = list()
        self.elmsyms: List[ElmSym] = list()
        self.elmterms: List[ElmTerm] = list()
        self.elmtr2s: List[ElmTr2] = list()
        self.elmtr3s: List[ElmTr3] = list()
        self.elmxnets: List[ElmXnet] = list()
        self.elmzones: List[ElmZone] = list()
        self.generals: List[General] = list()
        self.intfolders: List[IntFolder] = list()
        self.intgrfs: List[IntGrf] = list()
        self.intgrfcons: List[IntGrfcon] = list()
        self.intgrfnets: List[IntGrfnet] = list()
        self.relfuses: List[RelFuse] = list()
        self.stacubics: List[StaCubic] = list()
        self.staswitchs: List[StaSwitch] = list()
        self.typasmos: List[TypAsmo] = list()
        self.typfuses: List[TypFuse] = list()
        self.typlnes: List[TypLne] = list()
        self.typlods: List[TypLod] = list()
        self.typsyms: List[TypSym] = list()
        self.typtr2s: List[TypTr2] = list()
        self.typtr3s: List[TypTr3] = list()

        self._CLASS_TO_LIST: Dict[Type[DGSElement], List[DGSElement]] = {
            ChaRef: self.charefs,
            ChaVec: self.chavecs,
            ElmAsm: self.elmasms,
            ElmCoup: self.elmcoups,
            ElmFeeder: self.elmfeeders,
            ElmGenstat: self.elmgenstats,
            ElmLne: self.elmlnes,
            ElmLnesec: self.elmlnesecs,
            ElmLod: self.elmlods,
            ElmLodlv: self.elmlodlvs,
            ElmLodlvp: self.elmlodlvps,
            ElmNet: self.elmnets,
            ElmShnt: self.elmshnts,
            ElmSite: self.elmsites,
            ElmSubstat: self.elmsubstats,
            ElmSym: self.elmsyms,
            ElmTerm: self.elmterms,
            ElmTr2: self.elmtr2s,
            ElmTr3: self.elmtr3s,
            ElmXnet: self.elmxnets,
            ElmZone: self.elmzones,
            General: self.generals,
            IntFolder: self.intfolders,
            IntGrf: self.intgrfs,
            IntGrfcon: self.intgrfcons,
            IntGrfnet: self.intgrfnets,
            RelFuse: self.relfuses,
            StaCubic: self.stacubics,
            StaSwitch: self.staswitchs,
            TypAsmo: self.typasmos,
            TypFuse: self.typfuses,
            TypLne: self.typlnes,
            TypLod: self.typlods,
            TypSym: self.typsyms,
            TypTr2: self.typtr2s,
            TypTr3: self.typtr3s,
        }

    def parse_dgs(self, path: str):
        """
        Parse a DGS file and populate the typed lists.
        """
        path = Path(path)
        current_cls: Optional[Type[DGSElement]] = None
        header_map: Dict[str, int] | None = None

        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line = raw_line.strip()

                if line == "" or line.startswith("*"):
                    # Empty line or comment
                    pass

                elif line.startswith("$$"):
                    # Header line
                    element_type, header_map = parse_header(line)
                    current_cls = self._REGISTRY.get(element_type)

                else:
                    # Data line
                    if current_cls is not None:
                        try:
                            obj = current_cls.parse_line(line=line, header_map=header_map)
                        except (ValueError, IndexError):
                            # Legitimate parse failure (bad data line)
                            obj = None

                        if obj is not None:
                            try:
                                objects_lst = self._CLASS_TO_LIST[current_cls]
                                objects_lst.append(obj)
                            except KeyError:
                                # Programming/configuration error → re-raise
                                raise

    def write_dgs(self, path: str):
        """
        Write the circuit back to a DGS file.
        """
        path = Path(path)

        with path.open("w", encoding="utf-8") as f:
            for cls in self._ELEMENT_CLASSES:
                objects: List[DGSElement] = self._CLASS_TO_LIST[cls]

                if objects:
                    header = "$$" + cls.element_type + ";" + ";".join(
                        f"{p.name}({p.dgs_type})" for p in cls.properties_list
                    )
                    f.write(header + "\n")

                    for obj in objects:
                        f.write(obj.to_dgs_line() + "\n")

                    f.write("\n")

    def from_api(self, study_case_name: str | None = None, pf_path: str = "") -> None:
        """
        Populate this (empty) PfCircuit from an active PowerFactory application.
        Assumes:
        - self is empty (no existing elements)
        - schema registries (_ELEMENT_CLASSES, _CLASS_TO_LIST) are complete
        :param study_case_name: case name if any
        :param pf_path: PowerFactory path
        :return:
        """
        if pf_path == "":
            pf_path = r"C:\Program Files\DIgSILENT\PowerFactory 2025 SP1"
        python_folder = f"{sys.version_info.major}.{sys.version_info.minor}"
        module_folder = os.path.join(pf_path, "Python", python_folder)

        if not os.path.exists(module_folder):
            print(f"PowerFactory path for the compatible module not found: {module_folder}")

        # add the pf path to the system path
        sys.path.append(pf_path)
        sys.path.append(module_folder)

        # Obtain PowerFactory application ------------------------------------------------------------------------------
        try:
            import powerfactory as pf
            print(f"loaded PowerFactory version {pf.__version__}")
        except ImportError as e:
            print("PowerFactory Python module not available. "
                  "Ensure this is executed inside a PowerFactory Python environment.", str(e))
            return None

        try:
            app = pf.GetApplicationExt()
        except pf.ExitError as error:
            print(error)
            print('error.code = %d' % error.code)
            return None

        except RuntimeError as e:
            print("Failed to obtain PowerFactory application. "
                  "Ensure PowerFactory is running and a project is open.", str(e))
            return None

        # Activate study case  -----------------------------------------------------------------------------------------

        try:
            project = app.GetActiveProject()
        except RuntimeError as e:
            print("No active PowerFactory project.", str(e))
            return None

        if project is None:
            print("No active PowerFactory project.")
            return None

        # Fetch all study cases
        try:
            cases = project.GetContents("*.IntCase", recursive=True)
        except RuntimeError as e:
            print("Failed to retrieve study cases.", str(e))
            return None

        if not cases:
            print("No study cases found in the project.")
            return None

        active_case = None

        if study_case_name is not None:
            for case in cases:
                if case.loc_name == study_case_name:
                    active_case = case
                    break

            if active_case is None:
                print(f"Study case '{study_case_name}' not found in project.")
                return None

        else:
            # Use currently active case, if any
            try:
                active_case = app.GetActiveStudyCase()
            except RuntimeError:
                active_case = None

            if active_case is None:
                print("No study case is active. Please specify study_case_name explicitly.")
                return None

        # Activate selected case
        try:
            active_case.Activate()
        except RuntimeError as e:
            print(f"Failed to activate study case '{active_case.loc_name}'.", str(e))
            return None

        # Iterate over all known DGSElement subclasses
        for dgs_cls in self._ELEMENT_CLASSES:
            pf_class_name = dgs_cls.element_type

            try:
                pf_objects = app.GetCalcRelevantObjects(f"*.{pf_class_name}")
            except (RuntimeError, AttributeError):
                pf_objects = list()

            if pf_objects:
                target_list = self._CLASS_TO_LIST[dgs_cls]

                for pf_obj in pf_objects:
                    elem = _populate_from_pf_object(pf_obj, dgs_cls)
                    target_list.append(elem)



    def to_veragrid(self, logger: Logger | None = None) -> dev.MultiCircuit:
        """

        :return:
        """
        if logger is None:
            logger = Logger()

        grid = dev.MultiCircuit()

        baseMVA = 100.0

        # --- frequency ---
        if len(self.elmnets) > 0:
            frequency = float(self.elmnets[0].frnom or 50.0)
        else:
            frequency = 50.0

        # StaCubic dictionary
        stacubic_dict: Dict[str, List[int]] = dict()
        for elm in self.stacubics:
            lst = stacubic_dict.get(elm.obj_id, None)
            if lst is None:
                stacubic_dict[elm.obj_id] = [elm.obj_bus]
            else:
                lst.append(elm.obj_bus)

        # StaCubic dictionary (robust)
        cubics_by_objid: Dict[str, List[StaCubic]] = dict()
        for cb in self.stacubics:
            oid = _ref_id(cb.obj_id)
            if oid is None:
                continue
            lst = cubics_by_objid.get(oid, None)
            if lst is None:
                cubics_by_objid[oid] = [cb]
            else:
                lst.append(cb)

        # graphics dictioary
        pos_by_objid: Dict[str, Tuple[float, float]] = dict()
        for g in self.intgrfs:
            pos_by_objid[g.pDataObj] = (float(g.rCenterX or 0.0), float(g.rCenterY or 0.0))

        # Buses
        bus_by_term_id: Dict[str, dev.Bus] = dict()
        for elmterm in self.elmterms:
            bus = convert_dgs_to_bus(elmterm=elmterm, pos_by_objid=pos_by_objid)
            grid.add_bus(obj=bus)
            tid = _ref_id(elmterm.ID)
            if tid is not None:
                bus_by_term_id[tid] = bus

        # Line types
        typlne_dict: Dict[str, dev.SequenceLineType] = dict()
        for typlne in self.typlnes:
            seq_lne = convert_dgs_to_sequence_line(typlne=typlne)
            grid.add_sequence_line(obj=seq_lne)
            typlne_dict[typlne.ID] = seq_lne

        # Transformer types
        typtr2_dict: Dict[str, dev.TransformerType] = dict()
        for typtr2 in self.typtr2s:
            tpe = convert_dgs_to_transformer_type(typtr2=typtr2)
            if hasattr(grid, "add_transformer_type"):
                grid.add_transformer_type(obj=tpe)
            elif hasattr(grid, "add_transformer2w_type"):
                grid.add_transformer2w_type(obj=tpe)
            typtr2_dict[typtr2.ID] = tpe
            tid = _ref_id(typtr2.ID)
            if tid is not None:
                typtr2_dict[tid] = tpe

        # lines
        for elmlne in self.elmlnes:
            line = convert_dgs_to_line(lne=elmlne,
                                       buses=grid.buses,
                                       stacubic_dict=stacubic_dict,
                                       templates_dict=typlne_dict,
                                       freq=frequency,
                                       baseMVA=baseMVA,
                                       logger=logger,
                                       cubics_by_objid=cubics_by_objid,
                                       bus_by_term_id=bus_by_term_id)
            grid.add_line(obj=line, logger=logger)

        # Transformers 2W
        for elmtr2 in self.elmtr2s:
            trafo = convert_dgs_to_transformer(tr2=elmtr2,
                                               buses=grid.buses,
                                               stacubic_dict=stacubic_dict,
                                               templates_dict=typtr2_dict,
                                               freq=frequency,
                                               baseMVA=baseMVA,
                                               logger=logger,
                                               cubics_by_objid=cubics_by_objid,
                                               bus_by_term_id=bus_by_term_id)

            grid.add_transformer2w(obj=trafo)


        return grid

def _new_id(counter=[1]):
    v = counter[0]
    counter[0] += 1
    return str(v)


def dgs_to_circuit(path: str) -> dev.MultiCircuit:
    """
    Entry point: read a DGS and return a VeraGrid MultiCircuit.
    """
    dgs = DgsCircuit()
    dgs.parse_dgs(path)
    return dgs.to_veragrid()























def from_veragrid(self, grid: dev.MultiCircuit):
        # 0) limpiar listas
        for cls, list_name in self._CLASS_TO_LIST.items():
            getattr(self, list_name).clear()

        def _new_id(counter=[1]):
            v = counter[0];
            counter[0] += 1
            return str(v)

        # 1) ElmNet
        net = ElmNet()
        net.ID = _new_id()
        net.loc_name = "Grid"
        net.frnom = 50.0
        self.elmnets.append(net)

        # 2) ElmTerm por bus
        term_id_by_bus = {}
        for bus in grid.buses:
            t = ElmTerm()
            t.ID = _new_id()
            t.loc_name = bus.name
            t.uknom = float(bus.Vnom)
            t.outserv = 0 if bus.active else 1
            self.elmterms.append(t)
            term_id_by_bus[bus] = t.ID

            # opcional: IntGrf para posición
            g = IntGrf()
            g.ID = _new_id()
            g.pDataObj = t.ID
            g.rCenterX = float(getattr(bus, "xpos", 0.0))
            g.rCenterY = float(-getattr(bus, "ypos", 0.0))
            self.intgrfs.append(g)

        # 3) helper para crear cubicles y “conectar” un elemento a buses
        def add_cubicles_for_element(element_id: str, buses: list):
            for b in buses:
                c = StaCubic()
                c.ID = _new_id()
                c.obj_id = element_id
                c.fold_id = term_id_by_bus[b]  # esta es la clave
                self.stacubics.append(c)

        # 4) Loads
        for bus in grid.buses:
            for ld in getattr(bus, "loads", []):  # depende de cómo VeraGrid guarde loads
                e = ElmLod()
                e.ID = _new_id()
                e.loc_name = ld.name
                e.plini = float(ld.P)
                e.qlini = float(ld.Q)
                e.scale0 = 1.0
                e.outserv = 0
                self.elmlods.append(e)
                add_cubicles_for_element(e.ID, [bus])

        # 5) Lines (+ type)
        for line in grid.lines:
            tpe = TypLne()
            tpe.ID = _new_id()
            self.typlnes.append(tpe)

            e = ElmLne()
            e.ID = _new_id()
            e.loc_name = line.name
            e.typ_id = tpe.ID
            e.dline = 1.0
            e.outserv = 0 if line.active else 1
            self.elmlnes.append(e)
            add_cubicles_for_element(e.ID, [line.bus_from, line.bus_to])

        # 6) Transformers 2W (+ type)
        for tr in grid.transformers2w:
            tpe = TypTr2()
            tpe.ID = _new_id()

            self.typtr2s.append(tpe)

            e = ElmTr2()
            e.ID = _new_id()
            e.loc_name = tr.name
            e.typ_id = tpe.ID
            e.outserv = 0 if tr.active else 1
            self.elmtr2s.append(e)
            add_cubicles_for_element(e.ID, [tr.bus_from, tr.bus_to])

        # 7) Slack / external grid (ElmXnet)
        for bus in grid.buses:
            if getattr(bus, "is_slack", False):
                x = ElmXnet()
                x.ID = _new_id()
                x.loc_name = f"Slack_{bus.name}"
                x.bustp = "SL"
                x.usetp = 1.0
                self.elmxnets.append(x)
                add_cubicles_for_element(x.ID, [bus])



 # def to_veragrid_old(self) -> dev.MultiCircuit:
    #     """
    #
    #     :return:
    #     """
    #     grid = dev.MultiCircuit()
    #
    #     baseMVA = 100.0
    #
    #     # --- frequency ---
    #     if self.elmnets:
    #         frequency = float(self.elmnets[0].frnom or 50.0)
    #     else:
    #         frequency = 50.0
    #     w = 2.0 * math.pi * frequency
    #
    #     # StaCubic dictionary
    #     stacubic_dict: Dict[str, List[int]] = dict()
    #     for elm in self.stacubics:
    #         lst = stacubic_dict.get(elm.obj_id, None)
    #         if lst is None:
    #             stacubic_dict[elm.obj_id] = [elm.obj_bus]
    #         else:
    #             lst.append(elm.obj_bus)
    #
    #     # --- positions from IntGrf (optional) ---
    #     pos_by_objid: Dict[str, Tuple[float, float]] = dict()
    #     for g in self.intgrfs:
    #         obj = _ref_id(g.pDataObj)
    #         if obj:
    #             pos_by_objid[obj] = (float(g.rCenterX or 0.0), float(g.rCenterY or 0.0))
    #
    #     # --- dictionaries ---
    #     term_by_id = {_ref_id(t.ID): t for t in self.elmterms if _ref_id(t.ID) is not None}
    #     typlne_by_id = {_ref_id(t.ID): t for t in self.typlnes if _ref_id(t.ID) is not None}
    #     typtr2_by_id = {_ref_id(t.ID): t for t in self.typtr2s if _ref_id(t.ID) is not None}
    #     typsym_by_id = {_ref_id(t.ID): t for t in self.typsyms if _ref_id(t.ID) is not None}
    #
    #     cubics_by_objid = {}
    #     for c in self.stacubics:
    #         obj = _ref_id(c.obj_id)
    #         if not obj:
    #             continue
    #         cubics_by_objid.setdefault(obj, []).append(c)
    #
    #     # --- add buses ---
    #     busobj_by_termid = {}
    #     for t in self.elmterms:
    #         tid = _ref_id(t.ID)
    #         if not tid:
    #             continue
    #
    #         x, y = pos_by_objid.get(tid, (0.0, 0.0))
    #         bus = dev.Bus(
    #             name=t.loc_name or f"Bus_{tid}",
    #             Vnom=float(t.uknom or 0.0),
    #             vmin=0.9,
    #             vmax=1.1,
    #             xpos=float(x),
    #             ypos=float(-y),
    #             active=(int(t.outserv or 0) == 0),
    #         )
    #         grid.add_bus(bus)
    #         busobj_by_termid[tid] = bus
    #
    #     # --- ElmXnet (external grid) ---
    #     for xnet in self.elmxnets:
    #         eid = _ref_id(xnet.ID)
    #         terms = get_terminal_ids(eid)
    #         if not terms:
    #             warn(f"ElmXnet {eid} has no StaCubic -> cannot connect")
    #             continue
    #         bus = busobj_by_termid.get(terms[0])
    #         if bus is None:
    #             warn(f"ElmXnet {eid} terminal {terms[0]} not found in ElmTerm")
    #             continue
    #
    #         bustp = (xnet.bustp or "").strip()
    #         # a veces viene como bytes en otros loaders; aquí debería ser str
    #         if bustp == "SL":
    #             bus.is_slack = True
    #         elif bustp == "PV":
    #             gen = dev.ExternalGrid(
    #                 name=xnet.loc_name or f"PV_{eid}",
    #                 P=float(xnet.pgini or 0.0),
    #                 vset=float(xnet.usetp or 1.0),
    #                 Qmin=-9999, Qmax=9999,
    #                 Snom=9999,
    #             )
    #             grid.add_generator(bus, gen)
    #         elif bustp == "PQ":
    #             load = dev.Load(
    #                 name=xnet.loc_name or f"PQ_{eid}",
    #                 P=float(xnet.pgini or 0.0),
    #                 Q=float(xnet.qgini or 0.0),
    #             )
    #             grid.add_load(bus, load)
    #
    #     # --- lines ---
    #     for l in self.elmlnes:
    #         eid = _ref_id(l.ID)
    #         type_id = _ref_id(l.typ_id)
    #         tpe = typlne_by_id.get(type_id)
    #         if tpe is None:
    #             warn(f"Line {eid} type {type_id} not found")
    #             continue
    #
    #         terms = get_terminal_ids(eid)
    #         if len(terms) < 2:
    #             warn(f"Line {eid} has <2 terminals via StaCubic")
    #             continue
    #
    #         bus_from = busobj_by_termid.get(terms[0])
    #         bus_to = busobj_by_termid.get(terms[1])
    #         if bus_from is None or bus_to is None:
    #             warn(f"Line {eid} terminals not found in buses: {terms}")
    #             continue
    #
    #         length_km = float(l.dline or 0.0)
    #
    #         R = float(tpe.rline or 0.0) * length_km
    #         X = float(tpe.xline or 0.0) * length_km
    #
    #         # susceptance in Siemens
    #         B_S = 0.0
    #         if getattr(tpe, "cline", None) is not None:
    #             B_S = float(tpe.cline or 0.0) * length_km * w * 1e-6
    #         elif getattr(tpe, "bline", None) is not None:
    #             B_S = float(tpe.bline or 0.0) * length_km * 1e-6
    #
    #         Vbase = float(tpe.uline or bus_from.Vnom or 0.0)
    #         if Vbase <= 0:
    #             warn(f"Line {eid} has invalid Vbase")
    #             continue
    #
    #         zbase = (Vbase ** 2) / baseMVA
    #         ybase = 1.0 / zbase
    #
    #         r_pu = R / zbase
    #         x_pu = X / zbase
    #         b_pu = B_S / ybase
    #
    #         Irated = float(tpe.sline or 0.0)  # kA
    #         Smax = Irated * Vbase  # MVA
    #
    #         line = dev.Line(
    #             bus_from=bus_from,
    #             bus_to=bus_to,
    #             name=l.loc_name or f"Line_{eid}",
    #             r=r_pu,
    #             x=x_pu,
    #             b=b_pu,
    #             rate=Smax,
    #             active=(int(l.outserv or 0) == 0),
    #             mttf=0,
    #             mttr=0,
    #         )
    #         grid.add_line(line)
    #
    #     # --- transformers 2W ---
    #     for tr in self.elmtr2s:
    #         eid = _ref_id(tr.ID)
    #         type_id = _ref_id(tr.typ_id)
    #         tpe = typtr2_by_id.get(type_id)
    #         if tpe is None:
    #             warn(f"Transformer {eid} type {type_id} not found")
    #             continue
    #
    #         terms = get_terminal_ids(eid)
    #         if len(terms) < 2:
    #             warn(f"Transformer {eid} has <2 terminals via StaCubic")
    #             continue
    #
    #         bus_from = busobj_by_termid.get(terms[0])
    #         bus_to = busobj_by_termid.get(terms[1])
    #         if bus_from is None or bus_to is None:
    #             warn(f"Transformer {eid} terminals not found in buses: {terms}")
    #             continue
    #
    #         Snom = float(tpe.strn or 0.0)
    #         if Snom <= 0:
    #             Snom = 9999.0
    #
    #         tr_type = dev.TransformerType(
    #             hv_nominal_voltage=float(tpe.utrn_h or 0.0),
    #             lv_nominal_voltage=float(tpe.utrn_l or 0.0),
    #             nominal_power=Snom,
    #             copper_losses=float(tpe.pcutr or 0.0),
    #             iron_losses=float(tpe.pfe or 0.0),
    #             no_load_current=float(tpe.curmg or 0.0),
    #             short_circuit_voltage=float(tpe.uktr or 0.0),
    #             gr_hv1=0.5,
    #             gx_hv1=0.5,
    #         )
    #
    #         Zs, Zsh = tr_type.get_impedances(
    #             VH=float(tpe.utrn_h or 0.0),
    #             VL=float(tpe.utrn_l or 0.0),
    #             Sbase=baseMVA,
    #         )
    #
    #         Ysh = (1.0 / Zsh) if Zsh not in (0, 0j) else 0j
    #
    #         trafo = dev.Transformer2W(
    #             bus_from=bus_from,
    #             bus_to=bus_to,
    #             name=tr.loc_name or f"Tr2_{eid}",
    #             r=Zs.real,
    #             x=Zs.imag,
    #             g=Ysh.real,
    #             b=Ysh.imag,
    #             rate=Snom,
    #             tap_module=1.0,
    #             tap_phase=0.0,
    #             active=(int(tr.outserv or 0) == 0),
    #             mttf=0,
    #             mttr=0,
    #         )
    #         grid.add_transformer2w(trafo)
    #
    #     # --- loads ---
    #     for ld in self.elmlods:
    #         eid = _ref_id(ld.ID)
    #         terms = get_terminal_ids(eid)
    #         if not terms:
    #             warn(f"Load {eid} has no terminal via StaCubic")
    #             continue
    #         bus = busobj_by_termid.get(terms[0])
    #         if bus is None:
    #             warn(f"Load {eid} terminal {terms[0]} not found in ElmTerm")
    #             continue
    #
    #         scale = float(ld.scale0 or 1.0)
    #         load = dev.Load(
    #             name=ld.loc_name or f"Load_{eid}",
    #             P=float(ld.plini or 0.0) * scale,
    #             Q=float(ld.qlini or 0.0) * scale,
    #         )
    #         grid.add_load(bus, load)
    #
    #     # --- shunts ---
    #     for sh in self.elmshnts:
    #         eid = _ref_id(sh.ID)
    #         terms = get_terminal_ids(eid)
    #         if not terms:
    #             warn(f"Shunt {eid} has no terminal via StaCubic")
    #             continue
    #         bus = busobj_by_termid.get(terms[0])
    #         if bus is None:
    #             warn(f"Shunt {eid} terminal {terms[0]} not found in ElmTerm")
    #             continue
    #
    #         # replico tu dgs_parser: b = qcapn o qtotn "tal cual"
    #         b_val = float(sh.qcapn or sh.qtotn or 0.0)
    #         shunt = dev.Shunt(name=sh.loc_name or f"Shunt_{eid}", B=b_val)
    #         grid.add_shunt(bus, shunt)
    #
    #
    #     return grid