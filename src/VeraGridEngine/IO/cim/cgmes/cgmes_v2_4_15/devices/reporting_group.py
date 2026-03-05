# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
if TYPE_CHECKING:
	from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.bus_name_marker import BusNameMarker
	from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode



class ReportingGroup(IdentifiedObject):
	def __init__(self, rdfid='', tpe='ReportingGroup'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		self.BusNameMarker: BusNameMarker | None = None
		self.TopologicalNode: TopologicalNode | None = None

		self.register_property(
			name='BusNameMarker',
			class_type=BusNameMarker,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The reporting group to which this bus name marker belongs.''',
			profiles=[]
		)
		self.register_property(
			name='TopologicalNode',
			class_type=TopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The reporting group to which the topological node belongs.''',
			profiles=[]
		)
