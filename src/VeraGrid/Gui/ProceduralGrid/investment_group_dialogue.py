# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List, TYPE_CHECKING

from PySide6 import QtWidgets

import VeraGridEngine.Devices as dev
from VeraGrid.Gui.ProceduralGrid.investment_group_dialogue_ui import Ui_Dialog

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit

_NEW_GROUP_LABEL = "(New group)"


class InvestmentGroupDialogue(QtWidgets.QDialog):
    """
    Dialog that asks whether the newly generated objects should be assigned
    to an investment group. The user can pick an existing group or create a
    new one by selecting "(New group)" and providing a name.
    """

    def __init__(self,
                 circuit: MultiCircuit,
                 new_buses: List[dev.Bus],
                 new_lines: List[dev.Line],
                 new_transformers: List[dev.Transformer2W],
                 parent: QtWidgets.QWidget = None):
        """
        :param circuit: The MultiCircuit that owns the newly generated objects.
        :param new_buses: Newly generated Bus objects.
        :param new_lines: Newly generated Line objects.
        :param new_transformers: Newly generated Transformer2W objects.
        :param parent: Parent widget.
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Assign to investment group')

        self._circuit: MultiCircuit = circuit
        self._new_buses: List[dev.Bus] = new_buses
        self._new_lines: List[dev.Line] = new_lines
        self._new_transformers: List[dev.Transformer2W] = new_transformers

        # Populate combo box: "(New group)" first, then existing groups
        self.ui.groupComboBox.addItem(_NEW_GROUP_LABEL)
        for group in self._circuit.investments_groups:
            self.ui.groupComboBox.addItem(group.name)

        # Show/hide the new-name row based on the current selection
        self._on_combo_changed(self.ui.groupComboBox.currentText())
        self.ui.groupComboBox.currentTextChanged.connect(self._on_combo_changed)

        self.ui.buttonBox.accepted.connect(self._on_accept)
        self.ui.buttonBox.rejected.connect(self.reject)

    def _on_combo_changed(self, text: str) -> None:
        """
        Show the new-group name row only when "(New group)" is selected.

        :param text: Currently selected combo box text.
        """
        is_new: bool = (text == _NEW_GROUP_LABEL)
        self.ui.newGroupLabel.setVisible(is_new)
        self.ui.groupNameLineEdit.setVisible(is_new)

    def _on_accept(self) -> None:
        """
        Resolve the target investment group, then create one Investment per
        generated device and add everything to the circuit.
        """
        selected_text: str = self.ui.groupComboBox.currentText()

        if selected_text == _NEW_GROUP_LABEL:
            # Create a new investment group using the provided name
            group_name: str = self.ui.groupNameLineEdit.text().strip()
            if group_name == '':
                QtWidgets.QMessageBox.warning(self, 'Missing name',
                                              'Please enter a name for the new investment group.')
                return

            inv_group: dev.InvestmentsGroup = dev.InvestmentsGroup(name=group_name)
            self._circuit.add_investments_group(inv_group)
        else:
            # Find the existing group by name
            inv_group = None
            for group in self._circuit.investments_groups:
                if group.name == selected_text:
                    inv_group = group
                    break

            if inv_group is None:
                QtWidgets.QMessageBox.warning(self, 'Group not found',
                                              f'Investment group "{selected_text}" was not found.')
                return

        # Create one Investment per generated device
        for bus in self._new_buses:
            self._circuit.add_investment(dev.Investment(device=bus,
                                                        name=f'Inv_{bus.name}',
                                                        group=inv_group))

        for line in self._new_lines:
            self._circuit.add_investment(dev.Investment(device=line,
                                                        name=f'Inv_{line.name}',
                                                        group=inv_group))

        for transformer in self._new_transformers:
            self._circuit.add_investment(dev.Investment(device=transformer,
                                                        name=f'Inv_{transformer.name}',
                                                        group=inv_group))

        self.accept()
