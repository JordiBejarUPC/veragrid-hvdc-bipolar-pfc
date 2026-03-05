# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment_container import EquipmentContainer
if TYPE_CHECKING:
	from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_node import DCNode
	from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_topological_node import DCTopologicalNode


class DCEquipmentContainer(EquipmentContainer):
	def __init__(self, rdfid='', tpe='DCEquipmentContainer'):
		EquipmentContainer.__init__(self, rdfid, tpe)

		self.DCNodes: DCNode | None = None
		self.DCTopologicalNode: DCTopologicalNode | None = None

		self.register_property(
			name='DCNodes',
			class_type=DCNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
		self.register_property(
			name='DCTopologicalNode',
			class_type=DCTopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
