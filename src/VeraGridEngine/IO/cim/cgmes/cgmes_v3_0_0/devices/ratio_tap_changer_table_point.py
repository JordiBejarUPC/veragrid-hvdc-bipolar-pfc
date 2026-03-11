# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tap_changer_table_point import TapChangerTablePoint
from VeraGridEngine.IO.cim.cgmes.cgmes_property import CgmesProperty
if TYPE_CHECKING:
	from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ratio_tap_changer_table import RatioTapChangerTable

class RatioTapChangerTablePoint(TapChangerTablePoint):
	LOCAL_CGMES_PROPERTIES: tuple[CgmesProperty, ...] = (
		CgmesProperty(property_name='RatioTapChangerTable', class_type='RatioTapChangerTable', multiplier=UnitMultiplier.none, unit=UnitSymbol.none, description='''Table of this point.''', profiles=[]),
	)
	__slots__ = ('RatioTapChangerTable',)
	def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
		TapChangerTablePoint.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		self.RatioTapChangerTable: RatioTapChangerTable | None = None
