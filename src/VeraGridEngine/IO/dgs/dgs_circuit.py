# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Type, Optional
import math
from warnings import warn
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
import VeraGridEngine.Devices as dev
from VeraGridEngine.enumerations import ConverterControlType
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

    _CLASS_TO_LIST: Dict[Type[DGSElement], str] = {
        ChaRef: 'charefs',
        ChaVec: 'chavecs',
        ElmAsm: 'elmasms',
        ElmCoup: 'elmcoups',
        ElmFeeder: 'elmfeeders',
        ElmGenstat: 'elmgenstats',
        ElmLne: 'elmlnes',
        ElmLnesec: 'elmlnesecs',
        ElmLod: 'elmlods',
        ElmLodlv: 'elmlodlvs',
        ElmLodlvp: 'elmlodlvps',
        ElmNet: 'elmnets',
        ElmShnt: 'elmshnts',
        ElmSite: 'elmsites',
        ElmSubstat: 'elmsubstats',
        ElmSym: 'elmsyms',
        ElmTerm: 'elmterms',
        ElmTr2: 'elmtr2s',
        ElmTr3: 'elmtr3s',
        ElmXnet: 'elmxnets',
        ElmZone: 'elmzones',
        General: 'generals',
        IntFolder: 'intfolders',
        IntGrf: 'intgrfs',
        IntGrfcon: 'intgrfcons',
        IntGrfnet: 'intgrfnets',
        RelFuse: 'relfuses',
        StaCubic: 'stacubics',
        StaSwitch: 'staswitchs',
        TypAsmo: 'typasmos',
        TypFuse: 'typfuses',
        TypLne: 'typlnes',
        TypLod: 'typlods',
        TypSym: 'typsyms',
        TypTr2: 'typtr2s',
        TypTr3: 'typtr3s',
    }

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
