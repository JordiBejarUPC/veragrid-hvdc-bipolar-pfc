# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Type, Optional
import VeraGridEngine.Devices as dev
from VeraGridEngine.IO.dgs.dgs_objects import (
    DGSElement,

    # General / infra
    General,
    IntFolder,

    # Network
    ElmNet,
    ElmTerm,
    ElmSubstat,
    ElmSite,
    ElmCoup,
    ElmXnet,

    # Branches / loads / machines
    ElmLne,
    ElmLnesec,
    ElmLod,
    ElmLodlv,
    ElmLodlvp,
    ElmSym,
    ElmGenstat,
    ElmFeeder,

    # Graphics / characteristics
    StaSwitch,
    StaCubic,
    ChaRef,
    ChaVec,
    IntGrf,
    IntGrfnet,
    IntGrfcon,

    # Types
    TypAsmo,
    TypFuse,
    TypLne,
    TypSym,
    TypTr2,
    TypTr3,
)


class PfCircuit:
    """
    Strongly typed container for a PowerFactory DGS circuit.
    Owns the schema registry and supports parse / write.
    """

    # ======================================================
    # Internal registry (single source of truth)
    # ======================================================

    _ELEMENT_CLASSES: List[Type[DGSElement]] = [
        # General / infra
        General,
        IntFolder,

        # Network
        ElmNet,
        ElmTerm,
        ElmSubstat,
        ElmSite,
        ElmCoup,
        ElmXnet,

        # Branches / loads / machines
        ElmLne,
        ElmLnesec,
        ElmLod,
        ElmLodlv,
        ElmLodlvp,
        ElmSym,
        ElmGenstat,
        ElmFeeder,

        # Graphics / characteristics
        StaSwitch,
        StaCubic,
        ChaRef,
        ChaVec,
        IntGrf,
        IntGrfnet,
        IntGrfcon,

        # Types
        TypAsmo,
        TypFuse,
        TypLne,
        TypSym,
        TypTr2,
        TypTr3,
    ]

    _REGISTRY: dict[str, Type[DGSElement]] = {
        cls.element_type: cls for cls in _ELEMENT_CLASSES
    }

    _CLASS_TO_LIST: dict[Type[DGSElement], str] = {
        # General / infra
        General: "general",
        IntFolder: "int_folders",

        # Network
        ElmNet: "elm_nets",
        ElmTerm: "elm_terms",
        ElmSubstat: "elm_substats",
        ElmSite: "elm_sites",
        ElmCoup: "elm_coups",
        ElmXnet: "elm_xnets",

        # Branches / loads / machines
        ElmLne: "elm_lnes",
        ElmLnesec: "elm_lnesecs",
        ElmLod: "elm_lods",
        ElmLodlv: "elm_lodlvs",
        ElmLodlvp: "elm_lodlvps",
        ElmSym: "elm_syms",
        ElmGenstat: "elm_genstats",
        ElmFeeder: "elm_feeders",

        # Graphics / characteristics
        StaSwitch: "sta_switches",
        StaCubic: "sta_cubics",
        ChaRef: "cha_refs",
        ChaVec: "cha_vecs",
        IntGrf: "int_grfs",
        IntGrfnet: "int_grfnets",
        IntGrfcon: "int_grfcons",

        # Types
        TypAsmo: "typ_asmos",
        TypFuse: "typ_fuses",
        TypLne: "typ_lnes",
        TypSym: "typ_syms",
        TypTr2: "typ_tr2s",
        TypTr3: "typ_tr3s",
    }

    # ======================================================
    # Construction
    # ======================================================

    def __init__(self):
        # General / infra
        self.general: List[General] = list()
        self.int_folders: List[IntFolder] = list()

        # Network
        self.elm_nets: List[ElmNet] = list()
        self.elm_terms: List[ElmTerm] = list()
        self.elm_substats: List[ElmSubstat] = list()
        self.elm_sites: List[ElmSite] = list()
        self.elm_coups: List[ElmCoup] = list()
        self.elm_xnets: List[ElmXnet] = list()

        # Branches / loads / machines
        self.elm_lnes: List[ElmLne] = list()
        self.elm_lnesecs: List[ElmLnesec] = list()
        self.elm_lods: List[ElmLod] = list()
        self.elm_lodlvs: List[ElmLodlv] = list()
        self.elm_lodlvps: List[ElmLodlvp] = list()
        self.elm_syms: List[ElmSym] = list()
        self.elm_genstats: List[ElmGenstat] = list()
        self.elm_feeders: List[ElmFeeder] = list()

        # Graphics / characteristics
        self.sta_switches: List[StaSwitch] = list()
        self.sta_cubics: List[StaCubic] = list()
        self.cha_refs: List[ChaRef] = list()
        self.cha_vecs: List[ChaVec] = list()
        self.int_grfs: List[IntGrf] = list()
        self.int_grfnets: List[IntGrfnet] = list()
        self.int_grfcons: List[IntGrfcon] = list()

        # Types
        self.typ_asmos: List[TypAsmo] = list()
        self.typ_fuses: List[TypFuse] = list()
        self.typ_lnes: List[TypLne] = list()
        self.typ_syms: List[TypSym] = list()
        self.typ_tr2s: List[TypTr2] = list()
        self.typ_tr3s: List[TypTr3] = list()

    def parse(self, path: str):
        """
        Parse a DGS file and populate the typed lists.
        """
        path = Path(path)
        current_cls: Optional[Type[DGSElement]] = None

        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line = raw_line.strip()

                if line == "" or line.startswith("*"):
                    # Empty line or comment
                    pass

                elif line.startswith("$$"):
                    # Header line
                    element_type = line[2:].split(";", 1)[0]
                    current_cls = self._REGISTRY.get(element_type)

                else:
                    # Data line
                    if current_cls is not None:
                        try:
                            obj = current_cls.parse_line(line)
                        except (ValueError, IndexError):
                            # Legitimate parse failure (bad data line)
                            obj = None

                        if obj is not None:
                            try:
                                list_name = self._CLASS_TO_LIST[current_cls]
                                getattr(self, list_name).append(obj)
                            except KeyError:
                                # Programming/configuration error → re-raise
                                raise

    def write(self, path: str):
        """
        Write the circuit back to a DGS file.
        """
        path = Path(path)

        with path.open("w", encoding="utf-8") as f:
            for cls in self._ELEMENT_CLASSES:
                list_name = self._CLASS_TO_LIST[cls]
                objects: List[DGSElement] = getattr(self, list_name)

                if objects:
                    header = "$$" + cls.element_type + ";" + ";".join(
                        f"{p.name}({p.dgs_type})" for p in cls.properties_list
                    )
                    f.write(header + "\n")

                    for obj in objects:
                        f.write(obj.to_dgs_line() + "\n")

                    f.write("\n")

    def to_veragrid(self) -> dev.MultiCircuit:
        """

        :return:
        """
        grid = dev.MultiCircuit()

        # TODO: implement conversion

        return grid
