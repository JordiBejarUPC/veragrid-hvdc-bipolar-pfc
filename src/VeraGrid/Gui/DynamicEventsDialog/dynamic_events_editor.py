# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_editor_dialog import Ui_DynamicEventDialogue
from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_editor_support import (
    DynamicEventsGroupsDialog,
    collect_block_runtime_event_parameters,
)
from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_models import DynamicEventGroupDraft
from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_models import DynamicEventsDraftSession
from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_tree import DynamicEventsPage
from VeraGrid.Gui.Widgets.dynamic_device_tree import DynamicDeviceTreeWidget
from VeraGrid.Gui.toast_widget import ToastManager
from VeraGrid.Session.dynamic_editor_entries import DynamicEditorEntry
from VeraGrid.Session.dynamic_editor_entries import build_dynamic_editor_entry
from VeraGrid.Session.dynamic_editor_entries import build_dynamic_editor_title
from VeraGrid.Session.dynamic_editor_entries import get_block_for_entry
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DynamicSimulationMode


def collect_dynamic_events_page_parameters(
        entry: DynamicEditorEntry,
        mode: DynamicSimulationMode,
) -> tuple[list[Var], set[int], bool]:
    """Collect editable runtime parameters for one device/mode page.

    An absent or structurally empty dynamic block deliberately yields empty
    collections. The page remains open so existing events can still be
    inspected or removed, but it cannot create new events.

    :param entry: Device entry represented by the page.
    :param mode: RMS or EMT model requested for that device.
    :return: Event parameters, mode-parameter UID set and whether the block is empty.
    """
    block: object = get_block_for_entry(entry, mode)
    if isinstance(block, Block):
        parameters: list[Var]
        mode_parameter_uids: set[int]
        parameters, mode_parameter_uids = collect_block_runtime_event_parameters(block)
        model_is_empty: bool = block.empty()
        return list(parameters), set(mode_parameter_uids), model_is_empty
    else:
        return list(), set(), True


class DynamicEventEditor(QtWidgets.QDialog):
    """General transactional workspace for RMS and EMT dynamic events."""

    __slots__ = (
        "circuit",
        "preferred_mode",
        "session",
        "ui",
        "toast_manager",
        "device_tree_widget",
        "pages",
        "page_keys",
    )

    def __init__(
            self,
            circuit: MultiCircuit,
            preferred_mode: DynamicSimulationMode,
            initial_device: EditableDevice | None = None,
            parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Build the device-tree and tab-based dynamic-events workspace.

        :param circuit: Circuit whose RMS and EMT event assets are edited.
        :param preferred_mode: Mode requested by the action that opened the dialog.
        :param initial_device: Optional selected device to open immediately.
        :param parent: Optional owning widget.
        :return: None.
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.circuit: MultiCircuit = circuit
        self.preferred_mode: DynamicSimulationMode = preferred_mode
        self.session: DynamicEventsDraftSession = DynamicEventsDraftSession(circuit=circuit, parent=self)
        self.ui: Ui_DynamicEventDialogue = Ui_DynamicEventDialogue()
        self.ui.setupUi(self)
        # Match the Block Editor save feedback: the dialog owns a bottom-centred
        # toast manager so confirmations remain above this modal workspace.
        self.toast_manager: ToastManager = ToastManager(parent=self, position_top=False)
        self.pages: list[DynamicEventsPage] = list()
        self.page_keys: list[str] = list()

        # The device widget is the same reusable navigation component used by
        # DynamicEditor, with event-specific context-menu captions enabled.
        self.device_tree_widget: DynamicDeviceTreeWidget = DynamicDeviceTreeWidget(
            events_context=True,
            parent=self.ui.treeFrame,
        )
        self.device_tree_widget.set_preferred_double_click_mode(preferred_mode)
        self.device_tree_widget.set_circuit(circuit)
        self.ui.treeFrameLayout.addWidget(self.device_tree_widget)
        self.ui.treeButton.setIcon(QtGui.QIcon(":/Icons/icons/tree.png"))
        self.ui.treeButton.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)

        self._configure_buttons()
        self._connect_signals()

        # A valid single selection opens its requested page directly with the
        # navigation tree collapsed. With no usable selection, the dialog opens
        # as a general workspace and exposes the tree for device choice.
        initial_entry: DynamicEditorEntry | None = None
        if initial_device is not None:
            initial_entry = build_dynamic_editor_entry(initial_device, circuit)
        else:
            pass
        if initial_entry is not None and preferred_mode in initial_entry.available_modes:
            self.open_entry(initial_entry, preferred_mode)
            self._set_tree_visible(False)
        else:
            self._set_tree_visible(True)
            self._ensure_event_group_exists(preferred_mode)

    def _configure_buttons(self) -> None:
        """Apply the explicit transaction-control button captions.

        :return: None.
        """
        save_button: QtWidgets.QPushButton | None = self.ui.dialogButtonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        close_button: QtWidgets.QPushButton | None = self.ui.dialogButtonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        if save_button is not None:
            # Keep the compact Dynamic Editor action: the icon communicates the
            # action visually while tooltip and accessibility text preserve it.
            save_button.setText("")
            save_button.setIcon(QtGui.QIcon(":/Icons/icons/accept.png"))
            save_button.setToolTip(self.tr("Save"))
            save_button.setAccessibleName(self.tr("Save"))
        else:
            pass
        if close_button is not None:
            close_button.setText(self.tr("Close"))
        else:
            pass

    def _connect_signals(self) -> None:
        """Connect dialog navigation and transaction actions.

        :return: None.
        """
        self.ui.treeButton.toggled.connect(self._set_tree_visible)
        self.ui.tabBar.currentChanged.connect(self._on_current_tab_changed)
        self.ui.tabBar.tabCloseRequested.connect(self.close_tab)
        self.device_tree_widget.entryModeRequested.connect(self._open_tree_entry)
        self.ui.newGroupButton.clicked.connect(self.create_event_group)
        self.ui.dialogButtonBox.accepted.connect(self.accept_changes)
        self.ui.dialogButtonBox.rejected.connect(self.reject)

    def changeEvent(self, event: QtCore.QEvent) -> None:
        """Refresh dialog-shell strings after a runtime language change.

        :param event: Incoming Qt change event.
        :return: None.
        """
        QtWidgets.QDialog.changeEvent(self, event)
        if event.type() == QtCore.QEvent.Type.LanguageChange:
            self.ui.retranslateUi(self)
            self._configure_buttons()
        else:
            pass

    @QtCore.Slot(bool)
    def _set_tree_visible(self, visible: bool) -> None:
        """Show or collapse the device navigation pane.

        :param visible: Whether the tree pane must be visible.
        :return: None.
        """
        self.ui.treeButton.blockSignals(True)
        self.ui.treeButton.setChecked(visible)
        self.ui.treeButton.blockSignals(False)
        self.ui.treeFrame.setVisible(visible)
        if visible:
            self.ui.splitter.setSizes(list((250, 800)))
        else:
            self.ui.splitter.setSizes(list((0, 1050)))

    @QtCore.Slot(object, object)
    def _open_tree_entry(self, entry: object, mode: object) -> None:
        """Open a page requested by the shared device tree.

        :param entry: Dynamic-device entry emitted by the tree widget.
        :param mode: RMS or EMT mode emitted by the tree widget.
        :return: None.
        """
        if isinstance(entry, DynamicEditorEntry) and isinstance(mode, DynamicSimulationMode):
            self.open_entry(entry, mode)
        else:
            pass

    def open_entry(
            self,
            entry: DynamicEditorEntry,
            mode: DynamicSimulationMode,
    ) -> DynamicEventsPage | None:
        """Open or focus one unique device/mode events page.

        :param entry: Device entry whose complete event collection is displayed.
        :param mode: RMS or EMT events family to display.
        :return: Open page, or ``None`` when the request is unsupported.
        """
        if mode not in entry.available_modes or not isinstance(entry.api_object, EditableDevice):
            return None
        else:
            pass
        page_key: str = entry.session_key(mode)
        existing_index: int = self._find_page_index(page_key)
        if existing_index >= 0:
            self.ui.tabBar.setCurrentIndex(existing_index)
            return self.pages[existing_index]
        else:
            # A mode needs at least one global group before any device event
            # can reference it. Run this guard before building the page so its
            # initial tree immediately includes a group accepted by the user.
            self._ensure_event_group_exists(mode)
            parameters: list[Var]
            mode_parameter_uids: set[int]
            model_is_empty: bool
            parameters, mode_parameter_uids, model_is_empty = collect_dynamic_events_page_parameters(entry, mode)

        # Every page shares the same draft session. Edits, group activity and
        # global removals therefore stay coherent across all open device tabs.
        page: DynamicEventsPage = DynamicEventsPage(
            session=self.session,
            entry=entry,
            mode=mode,
            parameters=parameters,
            mode_parameter_uids=mode_parameter_uids,
            model_is_empty=model_is_empty,
            parent=self.ui.pagesStack,
        )
        self.pages.append(page)
        self.page_keys.append(page_key)
        self.ui.pagesStack.addWidget(page)
        tab_index: int = self.ui.tabBar.addTab(build_dynamic_editor_title(entry.api_object, mode))
        self.ui.tabBar.setTabToolTip(tab_index, entry.display_name)
        self.ui.tabBar.setCurrentIndex(tab_index)
        self.ui.pagesStack.setCurrentWidget(page)
        return page

    def _find_page_index(self, page_key: str) -> int:
        """Find an open page by its stable device/mode session key.

        :param page_key: Stable page key to locate.
        :return: Zero-based page index, or ``-1`` when absent.
        """
        page_index: int
        for page_index in range(len(self.page_keys)):
            if self.page_keys[page_index] == page_key:
                return page_index
            else:
                pass
        return -1

    @QtCore.Slot(int)
    def _on_current_tab_changed(self, index: int) -> None:
        """Display the page associated with the selected top-bar tab.

        :param index: Current tab index, or ``-1`` when no tab is open.
        :return: None.
        """
        if 0 <= index < len(self.pages):
            self.ui.pagesStack.setCurrentWidget(self.pages[index])
        else:
            self.ui.pagesStack.setCurrentWidget(self.ui.emptyPage)

    @QtCore.Slot(int)
    def close_tab(self, index: int) -> None:
        """Close one view without discarding its shared transaction edits.

        :param index: Tab and page index requested by the close button.
        :return: None.
        """
        if index < 0 or index >= len(self.pages):
            return
        else:
            page: DynamicEventsPage = self.pages.pop(index)
            self.page_keys.pop(index)
        self.ui.tabBar.removeTab(index)
        self.ui.pagesStack.removeWidget(page)
        page.deleteLater()
        if len(self.pages) == 0:
            self.ui.pagesStack.setCurrentWidget(self.ui.emptyPage)
        else:
            current_index: int = self.ui.tabBar.currentIndex()
            self._on_current_tab_changed(current_index)

    def _current_page(self) -> DynamicEventsPage | None:
        """Return the page selected in the top tab bar.

        :return: Current device/mode page, or ``None`` when no page is open.
        """
        current_index: int = self.ui.tabBar.currentIndex()
        if 0 <= current_index < len(self.pages):
            return self.pages[current_index]
        else:
            return None

    @QtCore.Slot()
    def create_event_group(self) -> None:
        """Create a transaction-only event group for the current mode.

        :return: None.
        """
        current_page: DynamicEventsPage | None = self._current_page()
        if current_page is None:
            group_mode: DynamicSimulationMode = self.preferred_mode
        else:
            group_mode = current_page.mode
        self._request_event_group(group_mode)

    def _ensure_event_group_exists(self, mode: DynamicSimulationMode) -> None:
        """Require an RMS or EMT event group before editing that mode.

        The warning and name request reproduce the pre-refactor entry flow.
        Cancelling the name dialog still leaves the general workspace open,
        where ``New Event Group`` remains available.

        :param mode: Dynamic simulation family about to be displayed.
        :return: None.
        """
        existing_groups: list[DynamicEventGroupDraft] = self.session.get_groups(mode)
        if len(existing_groups) == 0:
            message_title: str
            message_body: str
            if mode == DynamicSimulationMode.RMS:
                message_title = self.tr("No RMS Events Group")
                message_body = self.tr(
                    "No RMS Events Group found, please create one before adding an event."
                )
            elif mode == DynamicSimulationMode.EMT:
                message_title = self.tr("No EMT Events Group")
                message_body = self.tr(
                    "No EMT Events Group found, please create one before adding an event."
                )
            else:
                return

            QtWidgets.QMessageBox.information(self, message_title, message_body)
            self._request_event_group(mode)
        else:
            pass

    def _request_event_group(
            self,
            mode: DynamicSimulationMode,
    ) -> DynamicEventGroupDraft | None:
        """Ask for and append one transaction-only event group.

        :param mode: RMS or EMT family that will own the new group.
        :return: Created group draft, or ``None`` when cancelled or invalid.
        """
        group_dialog: DynamicEventsGroupsDialog = DynamicEventsGroupsDialog(
            mode=mode,
            parent=self,
        )
        if group_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            created_group: DynamicEventGroupDraft | None = self.session.add_group(
                mode,
                group_dialog.get_name(),
            )
            if created_group is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("Invalid event group"),
                    self.tr("The event group name must be non-empty and unique in this simulation mode."),
                )
            else:
                return created_group
        else:
            pass
        return None

    @QtCore.Slot()
    def accept_changes(self) -> None:
        """Validate and atomically persist the draft without closing the editor.

        A successful save establishes a new transaction baseline so subsequent
        edits can be saved again or discarded by closing the dialog.

        :return: None.
        """
        validation_error: str | None = self.session.validate()
        if validation_error is not None:
            QtWidgets.QMessageBox.warning(self, self.tr("Invalid dynamic events"), validation_error)
        else:
            self.session.commit()
            self.toast_manager.show_info_toast(self.tr("Events saved"))
