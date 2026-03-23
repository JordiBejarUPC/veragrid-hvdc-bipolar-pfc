# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


from VeraGridEngine.Devices.multi_circuit import MultiCircuit

class Scenario:

    def __init__(self, parent: MultiCircuit, name):

        self.parent = parent

        self.grid = MultiCircuit(name=name)

class MultiVerse:

    def __init__(self):

        self._scenarios