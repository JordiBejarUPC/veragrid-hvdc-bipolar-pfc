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
from VeraGridEngine.enumerations import WindingType
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
            value = pf_obj.name

        else:
            value = None

        setattr(elem, name, value)

    return elem


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
                        obj = current_cls.parse_line(line=line, header_map=header_map)

                        if obj is not None:
                            objects_lst = self._CLASS_TO_LIST[current_cls]
                            objects_lst.append(obj)

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
        os.environ["PATH"] = pf_path + ";" + os.environ["PATH"]
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
        from VeraGridEngine.IO.dgs.dgs_to_veragrid import to_veragrid
        return to_veragrid(self, logger=logger)


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
            g.rCenterX = float(bus.xpos)
            g.rCenterY = float(-(bus.ypos))
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
            for ld in bus.loads:  # depends on how VeraGrid stores loads
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
            if bus.is_slack:
                x = ElmXnet()
                x.ID = _new_id()
                x.loc_name = f"Slack_{bus.name}"
                x.bustp = "SL"
                x.usetp = 1.0
                self.elmxnets.append(x)
                add_cubicles_for_element(x.ID, [bus])
