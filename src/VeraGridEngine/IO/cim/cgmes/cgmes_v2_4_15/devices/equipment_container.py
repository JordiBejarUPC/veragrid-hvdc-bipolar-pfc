# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node_container import ConnectivityNodeContainer
if TYPE_CHECKING:
	from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment import Equipment


class EquipmentContainer(ConnectivityNodeContainer):
	def __init__(self, rdfid='', tpe='EquipmentContainer'):
		ConnectivityNodeContainer.__init__(self, rdfid, tpe)

		self.Equipments: Equipment | None = None

		self.register_property(
			name='Equipments',
			class_type=Equipment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Contained equipment.''',
			profiles=[]
		)
