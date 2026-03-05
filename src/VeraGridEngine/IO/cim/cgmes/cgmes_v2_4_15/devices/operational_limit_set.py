# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject

if TYPE_CHECKING:
    from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.acdc_terminal import ACDCTerminal
    from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment import Equipment
    from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit import OperationalLimit


class OperationalLimitSet(IdentifiedObject):
    def __init__(self, rdfid='', tpe='OperationalLimitSet'):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.Terminal: ACDCTerminal | None = None
        self.Equipment: Equipment | None = None
        self.OperationalLimitValue: OperationalLimit | None = None

        self.register_property(
            name='Terminal',
            class_type=ACDCTerminal,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description='''None''',
            profiles=[]
        )
        self.register_property(
            name='Equipment',
            class_type=Equipment,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description='''The equipment to which the limit set applies.''',
            profiles=[]
        )
        self.register_property(
            name='OperationalLimitValue',
            class_type=OperationalLimit,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description='''The limit set to which the limit values belong.''',
            profiles=[]
        )
