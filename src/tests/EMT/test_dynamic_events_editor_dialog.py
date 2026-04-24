from __future__ import annotations

import sys

from PySide6 import QtWidgets

from VeraGrid.Gui.dynamic_events_editor_dialog import DynamicEventDialogue
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DynamicSimulationMode


def _get_app() -> QtWidgets.QApplication:
    """
    Return the shared Qt application used by dialog tests.

    :return: Qt application instance.
    """
    app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()

    if app is None:
        return QtWidgets.QApplication(sys.argv)
    else:
        return app


def test_emt_event_dialog_enables_force_step_alignment_for_mode_parameters() -> None:
    """
    Ensure EMT mode parameters expose force-step alignment in the dialog.

    :return: None.
    """
    _get_app()
    circuit = MultiCircuit()
    group = EmtEventsGroup(name="group")
    circuit.add_emt_events_group(group)

    vf = VarFactory()
    event_var = vf.add_var("event_param")
    mode_var = vf.add_var("mode_param")

    dialog = DynamicEventDialogue(
        circuit=circuit,
        parameters_list=[event_var, mode_var],
        target_device_name="Device",
        mode=DynamicSimulationMode.EMT,
        mode_parameter_uids={mode_var.uid},
    )
    dialog.add_row()
    row = dialog.rows[0]

    row.param_combo.setCurrentIndex(1)
    QtWidgets.QApplication.processEvents()

    assert row.force_alignment_check is not None
    assert row.force_alignment_check.isEnabled()
    assert row.force_alignment_check.isChecked()

    dialog.accept_dialog()
    data = dialog.get_data()

    assert data["parameters"] == [mode_var]
    assert data["force_step_alignment"] == [True]
    dialog.close()


def test_emt_event_dialog_disables_force_step_alignment_for_event_parameters() -> None:
    """
    Ensure continuous EMT event parameters do not expose force-step alignment.

    :return: None.
    """
    _get_app()
    circuit = MultiCircuit()
    group = EmtEventsGroup(name="group")
    circuit.add_emt_events_group(group)

    vf = VarFactory()
    event_var = vf.add_var("event_param")
    mode_var = vf.add_var("mode_param")

    dialog = DynamicEventDialogue(
        circuit=circuit,
        parameters_list=[event_var, mode_var],
        target_device_name="Device",
        mode=DynamicSimulationMode.EMT,
        mode_parameter_uids={mode_var.uid},
    )
    dialog.add_row()
    row = dialog.rows[0]

    row.param_combo.setCurrentIndex(0)
    QtWidgets.QApplication.processEvents()

    assert row.force_alignment_check is not None
    assert not row.force_alignment_check.isEnabled()
    assert not row.force_alignment_check.isChecked()

    dialog.accept_dialog()
    data = dialog.get_data()

    assert data["parameters"] == [event_var]
    assert data["force_step_alignment"] == [False]
    dialog.close()
