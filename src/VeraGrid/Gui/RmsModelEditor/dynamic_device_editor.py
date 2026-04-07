from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.RmsModelEditor.dynamic_block_editor import DynamicBlockEditorGUI, DynamicEditorMode
from VeraGrid.Gui.RmsModelEditor.dynamic_device_editor_dialog import Ui_DynamicDeviceEditorDialog
from VeraGridEngine.enumerations import FmuTemplateDomain


def choose_initial_dynamic_editor_mode(api_object: Any) -> DynamicEditorMode:
    """
    Choose the most relevant initial tab for one dynamic device editor.

    The editor prefers the domain that already has an explicit template or a non-empty
    model so that the first tab reflects the current user work.

    :param api_object: Dynamic device API object.
    :return: Initial editor mode.
    """

    if api_object.emt_template is not None or api_object.emt_fmu_template is not None:
        if api_object.rms_template is None and api_object.rms_fmu_template is None:
            return DynamicEditorMode.EMT
        else:
            pass
    else:
        pass

    if api_object.emt_model.empty():
        return DynamicEditorMode.RMS
    else:
        if api_object.rms_model.empty():
            return DynamicEditorMode.EMT
        else:
            return DynamicEditorMode.RMS


class DynamicDeviceEditorDialog(QtWidgets.QDialog):
    """
    Two-tab dynamic editor for devices that own both RMS and EMT models.

    The wrapper keeps the current ``Do it!`` interaction pattern and clears the
    domain template link only when the user actually changed that domain model.
    """

    __slots__ = (
        "ui",
        "_circuit",
        "_api_object",
        "_rms_editor",
        "_emt_editor",
        "_rms_snapshot",
        "_emt_snapshot",
    )

    def __init__(self,
                 circuit: Any,
                 api_object: Any,
                 initial_mode: DynamicEditorMode,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """
        Build the tabbed dynamic device editor.

        :param circuit: Active circuit.
        :param api_object: Device being edited.
        :param initial_mode: Initially selected editor mode.
        :param parent: Parent Qt widget.
        """

        super().__init__(parent)
        self.ui = Ui_DynamicDeviceEditorDialog()
        self.ui.setupUi(self)
        self._circuit = circuit
        self._api_object = api_object
        self._rms_snapshot = self._api_object.rms_model.copy()
        self._emt_snapshot = self._api_object.emt_model.copy()
        self._rms_editor = DynamicBlockEditorGUI(
            var_factory=self._circuit.rms_var_factory,
            block=self._api_object.rms_model,
            api_object=self._api_object,
            mode=DynamicEditorMode.RMS,
            templates_list=self._circuit.get_dynamic_templates_by_device_type_and_domain(
                self._api_object.device_type,
                FmuTemplateDomain.RMS,
            ),
            circuit=self._circuit,
            embedded=True,
            main_editor=True,
            modal=False,
        )
        self._emt_editor = DynamicBlockEditorGUI(
            var_factory=self._circuit.emt_var_factory,
            block=self._api_object.emt_model,
            api_object=self._api_object,
            mode=DynamicEditorMode.EMT,
            templates_list=self._circuit.get_dynamic_templates_by_device_type_and_domain(
                self._api_object.device_type,
                FmuTemplateDomain.EMT,
            ),
            circuit=self._circuit,
            embedded=True,
            main_editor=True,
            modal=False,
        )
        self._build_ui(initial_mode)

    def _build_ui(self, initial_mode: DynamicEditorMode) -> None:
        """
        Build the dialog layout and select the requested initial tab.

        :param initial_mode: Initially selected editor mode.
        :return: None.
        """

        self.setWindowTitle(f"Dynamic Device Editor [{self._api_object.name}]")
        self.resize(1600, 1000)
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.ui.deviceNameLabel.setText(self._api_object.name)
        self.ui.rmsTabLayout.addWidget(self._rms_editor)
        self.ui.emtTabLayout.addWidget(self._emt_editor)

        if initial_mode == DynamicEditorMode.EMT:
            self.ui.domainTabWidget.setCurrentIndex(1)
        else:
            self.ui.domainTabWidget.setCurrentIndex(0)

        self.ui.doItButton.clicked.connect(self._apply_changes)
        self.ui.cancelButton.clicked.connect(self.reject)

    def _domain_changed(self, mode: DynamicEditorMode) -> bool:
        """
        Return whether one domain block changed relative to the snapshot captured when the dialog opened.

        :param mode: Domain being checked.
        :return: True when the edited domain differs from the original snapshot.
        """

        if mode == DynamicEditorMode.RMS:
            return not self._rms_snapshot.compare(self._rms_editor.main_block)
        else:
            if mode == DynamicEditorMode.EMT:
                return not self._emt_snapshot.compare(self._emt_editor.main_block)
            else:
                raise ValueError(f"Unsupported dynamic editor mode {mode}")

    def _break_template_links_for_mode(self, mode: DynamicEditorMode) -> None:
        """
        Break the reusable template link for one edited domain.

        This preserves the edited block while making it explicit that the device is no
        longer a clean instance of the reusable template after manual changes.

        :param mode: Edited domain.
        :return: None.
        """

        if mode == DynamicEditorMode.RMS:
            self._api_object.rms_template = None
            self._api_object.rms_fmu_template = None
        else:
            if mode == DynamicEditorMode.EMT:
                self._api_object.emt_template = None
                self._api_object.emt_fmu_template = None
            else:
                raise ValueError(f"Unsupported dynamic editor mode {mode}")

    def _apply_changes(self) -> None:
        """
        Commit both domain editors and close the dialog.

        :return: None.
        """

        if self._domain_changed(DynamicEditorMode.RMS):
            self._break_template_links_for_mode(DynamicEditorMode.RMS)
        else:
            pass

        if self._domain_changed(DynamicEditorMode.EMT):
            self._break_template_links_for_mode(DynamicEditorMode.EMT)
        else:
            pass

        self._rms_editor.commit_changes(close_window=False)
        self._emt_editor.commit_changes(close_window=False)
        self.accept()
