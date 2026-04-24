from __future__ import annotations

import sys

import pytest
from PySide6 import QtCore, QtWidgets
from PySide6.QtTest import QTest

import VeraGrid.Gui.DynamicModelEditor.dynamic_block_editor as dynamic_block_editor_module
from VeraGrid.Gui.DynamicModelEditor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGrid.Gui.DynamicModelEditor.lookup_table_dialog import LookupArrayLinearDialog
from VeraGrid.Gui.DynamicModelEditor.lookup_table_dialog import LookupMatrixLinearDialog
from VeraGrid.Gui.DynamicModelEditor.lookup_table_dialog import _parse_clipboard_grid
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.BasicBlockCatalog import BasicBlockTemplateDescriptor
from VeraGridEngine.Templates.BasicBlockCatalog import get_basic_block_catalog_descriptor_by_key
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DynamicSimulationMode

pytestmark = pytest.mark.filterwarnings("error")


class _ApiStub:
    """
    Minimal API object accepted by the dynamic block editor tests.
    """

    __slots__ = ("name", "rms_template", "emt_template")

    def __init__(self) -> None:
        self.name = "Stub"
        self.rms_template = None
        self.emt_template = None


def _get_app() -> QtWidgets.QApplication:
    """
    Get or create the Qt application used by GUI tests.
    """

    app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if app is None:
        return QtWidgets.QApplication(sys.argv)
    else:
        return app


def _find_index_by_label(model: QtCore.QAbstractItemModel,
                         label: str,
                         parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> QtCore.QModelIndex:
    """
    Find one recursive model index by visible label.
    """

    row_count: int = model.rowCount(parent)
    row: int
    for row in range(row_count):
        index = model.index(row, 0, parent)
        if str(model.data(index, QtCore.Qt.ItemDataRole.DisplayRole)) == label:
            return index

        child = _find_index_by_label(model, label, index)
        if child.isValid():
            return child
        else:
            pass

    return QtCore.QModelIndex()


def _collect_leaf_labels(model: QtCore.QAbstractItemModel,
                         parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> list[str]:
    """
    Collect all visible leaf labels from one recursive model.
    """

    labels: list[str] = list()
    row_count: int = model.rowCount(parent)
    row: int

    for row in range(row_count):
        index = model.index(row, 0, parent)
        if model.rowCount(index) == 0:
            labels.append(str(model.data(index, QtCore.Qt.ItemDataRole.DisplayRole)))
        else:
            labels.extend(_collect_leaf_labels(model, index))

    return labels


def _count_descriptor_leaves(editor: DynamicBlockEditorGUI,
                             parent_item) -> int:
    """
    Count basic block descriptor leaves below one source-model item.
    """

    count: int = 0
    row: int
    for row in range(parent_item.rowCount()):
        child = parent_item.child(row)
        if child.hasChildren():
            count += _count_descriptor_leaves(editor, child)
        else:
            payload = child.data(editor.block_role)
            if isinstance(payload, BasicBlockTemplateDescriptor):
                count += 1
            else:
                pass

    return count


def _build_editor(mode: DynamicSimulationMode = DynamicSimulationMode.EMT) -> DynamicBlockEditorGUI:
    """
    Build one dynamic block editor instance for GUI tests.
    """

    _get_app()
    editor = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
        block=Block(),
        api_object=_ApiStub(),
        mode=mode,
        templates_list=list(),
        main_editor=False,
        modal=False,
    )
    editor.show()
    editor.activateWindow()
    return editor


def _build_catalog_block_item(editor: DynamicBlockEditorGUI, template_key: str):
    """
    Materialize one catalog block on the editor canvas.
    """

    descriptor = get_basic_block_catalog_descriptor_by_key()[template_key]
    block_item = editor.create_library_payload_item(descriptor, 10.0, 20.0)
    assert block_item is not None
    return block_item


def _label_texts(label_items) -> list[str]:
    """
    Collect plain-text labels from one graphics label list.
    """

    return [item.toPlainText() for item in label_items]


def _port_name_prefixes(block_item) -> list[str]:
    """
    Extract stable name prefixes from one block item input port list.
    """

    prefixes: list[str] = list()
    for port in block_item.inputs:
        assert port.base_var is not None
        full_name = port.base_var.name
        if full_name.startswith("grd_up_"):
            prefixes.append("grd_up")
        elif full_name.startswith("grd_down_"):
            prefixes.append("grd_down")
        elif full_name.startswith("y_max_"):
            prefixes.append("y_max")
        elif full_name.startswith("y_min_"):
            prefixes.append("y_min")
        elif full_name.startswith("yi_"):
            prefixes.append("yi")
        else:
            prefixes.append(full_name)

    return prefixes


def test_emt_editor_exposes_basic_block_catalog_under_basic() -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    source_model = editor.library_model
    basic_item = source_model.invisibleRootItem().child(0)
    native_item = basic_item.child(0)

    assert basic_item.text() == "Basic"
    assert basic_item.rowCount() == 1
    assert native_item.text() == "Native"
    assert native_item.child(0).text() == "Arithmetic"
    assert _find_index_by_label(editor.library_model, "Scaling and Products").isValid()
    assert not _find_index_by_label(editor.library_model, "Arithmetic and Products").isValid()
    assert _count_descriptor_leaves(editor, native_item) == 545

    editor.close()


def test_rms_editor_exposes_basic_block_catalog_under_basic() -> None:
    editor = _build_editor(DynamicSimulationMode.RMS)
    source_model = editor.library_model
    basic_item = source_model.invisibleRootItem().child(0)
    native_item = basic_item.child(0)

    assert basic_item.text() == "Basic"
    assert basic_item.rowCount() == 1
    assert native_item.text() == "Native"
    assert _count_descriptor_leaves(editor, native_item) == 545

    editor.close()


def test_library_search_button_and_shortcut_filter_basic_catalog() -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    descriptor_by_key = get_basic_block_catalog_descriptor_by_key()
    park_label = descriptor_by_key["park_transform_dq"].display_label
    limit_label = descriptor_by_key["limit"].display_label

    assert editor.ui.librarySearchLineEdit.isVisible()

    QTest.mouseClick(editor.ui.librarySearchButton, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents()
    assert editor.ui.librarySearchLineEdit.hasFocus()

    editor.ui.librarySearchLineEdit.clearFocus()
    QTest.keyClick(editor, QtCore.Qt.Key.Key_F, QtCore.Qt.KeyboardModifier.ControlModifier)
    QtWidgets.QApplication.processEvents()
    assert editor.ui.librarySearchLineEdit.hasFocus()

    editor.ui.librarySearchLineEdit.setText("park transform")
    QtWidgets.QApplication.processEvents()

    visible_leaf_labels = _collect_leaf_labels(editor.library_proxy_model)
    assert park_label in visible_leaf_labels
    assert limit_label not in visible_leaf_labels

    editor.close()


def test_proxy_drag_payload_materializes_catalog_template() -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    park_descriptor = get_basic_block_catalog_descriptor_by_key()["park_transform_dq"]
    park_label = park_descriptor.display_label
    source_index = _find_index_by_label(editor.library_model, park_label)

    assert source_index.isValid()

    proxy_index = editor.library_proxy_model.mapFromSource(source_index)
    assert proxy_index.isValid()

    mime_data = editor.library_proxy_model.mimeData([proxy_index])
    payload = editor.get_library_payload_from_mime_data(mime_data)

    assert payload is not None
    assert isinstance(payload, BasicBlockTemplateDescriptor)
    assert payload.template_key == "park_transform_dq"

    block_item = editor.create_library_payload_item(payload, 10.0, 20.0)
    assert block_item is not None
    assert len(editor.main_block.children) == 1

    editor.has_unapplied_changes = False
    editor.close()


def test_limit_signal_variant_exposes_signal_ports_while_parameter_variant_does_not() -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    signal_block = _build_catalog_block_item(editor, "limit_s_form_b")
    parameter_block = _build_catalog_block_item(editor, "limit_p_form_c")

    assert len(signal_block.inputs) == 3
    assert _port_name_prefixes(signal_block) == ["yi", "y_max", "y_min"]

    assert len(parameter_block.inputs) == 1
    assert _port_name_prefixes(parameter_block) == ["yi"]
    assert {const.name for const in parameter_block.subsys.event_dict.values()} == {"y_max", "y_min"}

    editor.has_unapplied_changes = False
    editor.close()


def test_rate_limiter_signal_variant_exposes_gradient_ports_while_parameter_variant_keeps_parameter_table() -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    signal_block = _build_catalog_block_item(editor, "rate_limiter_s")
    parameter_block = _build_catalog_block_item(editor, "rate_limiter_p_form_c")

    assert len(signal_block.inputs) == 3
    assert _port_name_prefixes(signal_block) == ["yi", "grd_up", "grd_down"]

    assert len(parameter_block.inputs) == 1
    assert _port_name_prefixes(parameter_block) == ["yi"]
    assert {const.name for const in parameter_block.subsys.event_dict.values()} == {"grd"}

    editor.has_unapplied_changes = False
    editor.close()


def test_side_panel_loads_only_the_visible_table_for_selected_block() -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    block_item = _build_catalog_block_item(editor, "pulse")

    editor.ui.toolBox.setCurrentWidget(editor.ui.page_7)
    editor.scene.clearSelection()
    block_item.setSelected(True)
    QtWidgets.QApplication.processEvents()

    assert editor.variables_table_model.rowCount() == 0
    assert editor.parameters_table_model.rowCount() == 0
    assert editor.equations_table_model.rowCount() == 0

    editor.ui.toolBox.setCurrentWidget(editor.ui.page_2)
    QtWidgets.QApplication.processEvents()

    assert editor.parameters_table_model.rowCount() > 0
    assert editor.variables_table_model.rowCount() == 0
    assert editor.equations_table_model.rowCount() == 0

    editor.has_unapplied_changes = False
    editor.close()


def test_parameter_edit_does_not_rebuild_scene_for_non_structural_change() -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    block_item = _build_catalog_block_item(editor, "pulse")
    rebuild_calls: list[str] = list()

    editor.scene.clearSelection()
    block_item.setSelected(True)
    editor.ui.toolBox.setCurrentWidget(editor.ui.page_2)
    QtWidgets.QApplication.processEvents()

    assert editor.parameters_table_model.rowCount() > 0

    def _record_rebuild() -> None:
        rebuild_calls.append("rebuild")

    editor.rebuild_scene_from_diagram = _record_rebuild
    value_index = editor.parameters_table_model.index(0, 2)

    assert editor.parameters_table_model.setData(value_index, 1.0, QtCore.Qt.ItemDataRole.EditRole)
    QtWidgets.QApplication.processEvents()
    assert rebuild_calls == list()

    editor.has_unapplied_changes = False
    editor.close()


def test_parameter_panel_includes_mode_parameters_for_pulse_block() -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    block_item = _build_catalog_block_item(editor, "pulse")

    editor.scene.clearSelection()
    block_item.setSelected(True)
    editor.ui.toolBox.setCurrentWidget(editor.ui.page_2)
    QtWidgets.QApplication.processEvents()

    row_types: list[str] = list()
    row_index: int
    for row_index in range(editor.parameters_table_model.rowCount()):
        index = editor.parameters_table_model.index(row_index, 0)
        row_types.append(str(editor.parameters_table_model.data(index, QtCore.Qt.ItemDataRole.DisplayRole)))

    assert "Event Parameter" in row_types
    assert "Mode Parameter" in row_types

    editor.has_unapplied_changes = False
    editor.close()


def test_lookup_array_linear_dialog_parses_clipboard_rows() -> None:
    _get_app()
    dialog = LookupArrayLinearDialog(block_label="Lookup array (linear)")
    clipboard = QtWidgets.QApplication.clipboard()
    clipboard.setText("0\t0\n1\t10\n2\t20")

    dialog.paste_from_clipboard()
    dialog.accept_dialog()
    x_points, y_points = dialog.get_points()

    assert x_points == [0.0, 1.0, 2.0]
    assert y_points == [0.0, 10.0, 20.0]
    dialog.close()


def test_lookup_array_linear_dialog_supports_copy_paste_and_delete_shortcuts() -> None:
    _get_app()
    dialog = LookupArrayLinearDialog(block_label="Lookup array (linear)")
    dialog.show()
    dialog.activateWindow()
    clipboard = QtWidgets.QApplication.clipboard()

    dialog._table_widget.clearSelection()
    selection = QtWidgets.QTableWidgetSelectionRange(0, 0, 0, 1)
    dialog._table_widget.setRangeSelected(selection, True)
    dialog._table_widget.setFocus()
    QTest.keyClick(dialog._table_widget, QtCore.Qt.Key.Key_C, QtCore.Qt.KeyboardModifier.ControlModifier)
    QtWidgets.QApplication.processEvents()
    assert clipboard.text().strip() == "0.0\t0.0"

    clipboard.setText("3\t30\n4\t40")
    QTest.keyClick(dialog._table_widget, QtCore.Qt.Key.Key_V, QtCore.Qt.KeyboardModifier.ControlModifier)
    QtWidgets.QApplication.processEvents()
    x_points, y_points = dialog._read_points_from_table()
    assert x_points == [3.0, 4.0, 2.0]
    assert y_points == [30.0, 40.0, 20.0]

    dialog._table_widget.clearSelection()
    selection = QtWidgets.QTableWidgetSelectionRange(0, 0, 0, 1)
    dialog._table_widget.setRangeSelected(selection, True)
    QTest.keyClick(dialog._table_widget, QtCore.Qt.Key.Key_Delete)
    QtWidgets.QApplication.processEvents()
    assert dialog._table_widget.rowCount() == 2
    dialog.close()


def test_lookup_array_linear_dialog_header_click_selects_full_column() -> None:
    _get_app()
    dialog = LookupArrayLinearDialog(block_label="Lookup array (linear)")

    dialog.select_column_by_header(0)
    QtWidgets.QApplication.processEvents()
    selected_indexes = dialog._table_widget.selectionModel().selectedIndexes()

    assert len(selected_indexes) == dialog._table_widget.rowCount()
    assert all(index.column() == 0 for index in selected_indexes)
    dialog.close()


def test_lookup_array_linear_descriptor_uses_modal_points_to_build_block(monkeypatch) -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    descriptor = get_basic_block_catalog_descriptor_by_key()["lookup_array_linear"]

    class _DialogStub:
        def __init__(self, block_label: str, initial_points=None, parent=None) -> None:
            _unused = (block_label, initial_points, parent)

        def exec(self) -> int:
            return int(QtWidgets.QDialog.DialogCode.Accepted)

        def get_points(self) -> tuple[list[float], list[float]]:
            return [0.0, 2.0, 4.0], [0.0, 20.0, 40.0]

    monkeypatch.setattr(dynamic_block_editor_module, "LookupArrayLinearDialog", _DialogStub)
    block_item = editor.create_library_payload_item(descriptor, 10.0, 20.0)

    assert block_item is not None
    assert any(var.name.startswith("arr_x3_") for var in block_item.subsys.event_dict.keys())
    assert any(var.name.startswith("arr_y3_") for var in block_item.subsys.event_dict.keys())

    editor.has_unapplied_changes = False
    editor.close()


def test_lookup_matrix_linear_dialog_parses_clipboard_matrix() -> None:
    _get_app()
    dialog = LookupMatrixLinearDialog(block_label="Lookup matrix (linear)")
    clipboard = QtWidgets.QApplication.clipboard()
    clipboard.setText("\t0\t1\n0\t0\t10\n2\t20\t30")

    dialog.paste_from_clipboard()
    dialog.accept_dialog()
    x_points, y_points, z_matrix = dialog.get_matrix_data()

    assert x_points == [0.0, 1.0]
    assert y_points == [0.0, 2.0]
    assert z_matrix == [[0.0, 10.0], [20.0, 30.0]]
    dialog.close()


def test_lookup_matrix_linear_dialog_supports_copy_paste_and_delete_shortcuts() -> None:
    _get_app()
    dialog = LookupMatrixLinearDialog(block_label="Lookup matrix (linear)")
    dialog.show()
    dialog.activateWindow()
    clipboard = QtWidgets.QApplication.clipboard()

    dialog._table_widget.clearSelection()
    selection = QtWidgets.QTableWidgetSelectionRange(0, 0, 2, 2)
    dialog._table_widget.setRangeSelected(selection, True)
    dialog.setFocus()
    QTest.keyClick(dialog, QtCore.Qt.Key.Key_C, QtCore.Qt.KeyboardModifier.ControlModifier)
    QtWidgets.QApplication.processEvents()
    copied_grid = _parse_clipboard_grid(clipboard.text())
    assert copied_grid == [["", "0.0", "1.0"], ["0.0", "0.0", "10.0"], ["2.0", "20.0", "30.0"]] or copied_grid == [["", "0", "1"], ["0", "0", "10"], ["2", "20", "30"]]

    clipboard.setText("\t5\t6\n7\t8\t9\n10\t11\t12\n13\t14\t15")
    QTest.keyClick(dialog, QtCore.Qt.Key.Key_V, QtCore.Qt.KeyboardModifier.ControlModifier)
    QtWidgets.QApplication.processEvents()
    x_points, y_points, z_matrix = dialog._read_matrix_from_table()
    assert x_points == [5.0, 6.0]
    assert y_points == [7.0, 10.0, 13.0]
    assert z_matrix == [[8.0, 9.0], [11.0, 12.0], [14.0, 15.0]]

    dialog._table_widget.clearSelection()
    selection = QtWidgets.QTableWidgetSelectionRange(1, 0, 1, 2)
    dialog._table_widget.setRangeSelected(selection, True)
    QTest.keyClick(dialog, QtCore.Qt.Key.Key_Delete)
    QtWidgets.QApplication.processEvents()
    x_points, y_points, z_matrix = dialog._read_matrix_from_table()
    assert x_points == [5.0, 6.0]
    assert y_points == [10.0, 13.0]
    assert z_matrix == [[11.0, 12.0], [14.0, 15.0]]
    dialog.close()


def test_lookup_matrix_linear_dialog_axis_click_selects_full_column_or_row() -> None:
    _get_app()
    dialog = LookupMatrixLinearDialog(block_label="Lookup matrix (linear)")

    dialog.on_matrix_cell_pressed(0, 1)
    QtWidgets.QApplication.processEvents()
    selected_indexes = dialog._table_widget.selectionModel().selectedIndexes()
    assert len(selected_indexes) == dialog._table_widget.rowCount()
    assert all(index.column() == 1 for index in selected_indexes)

    dialog.on_matrix_cell_pressed(1, 0)
    QtWidgets.QApplication.processEvents()
    selected_indexes = dialog._table_widget.selectionModel().selectedIndexes()
    assert len(selected_indexes) == dialog._table_widget.columnCount()
    assert all(index.row() == 1 for index in selected_indexes)
    dialog.close()


def test_lookup_matrix_linear_dialog_supports_row_copy_and_row_paste() -> None:
    _get_app()
    dialog = LookupMatrixLinearDialog(block_label="Lookup matrix (linear)")
    dialog.show()
    dialog.activateWindow()
    clipboard = QtWidgets.QApplication.clipboard()

    dialog.on_matrix_cell_pressed(1, 0)
    QtWidgets.QApplication.processEvents()
    dialog.setFocus()
    QTest.keyClick(dialog, QtCore.Qt.Key.Key_C, QtCore.Qt.KeyboardModifier.ControlModifier)
    QtWidgets.QApplication.processEvents()
    assert clipboard.text().rstrip() == "0.0\t0.0\t10.0"

    dialog.on_matrix_cell_pressed(2, 0)
    QtWidgets.QApplication.processEvents()
    QTest.keyClick(dialog, QtCore.Qt.Key.Key_V, QtCore.Qt.KeyboardModifier.ControlModifier)
    QtWidgets.QApplication.processEvents()
    x_points, y_points, z_matrix = dialog._read_matrix_from_table()
    assert x_points == [0.0, 1.0]
    assert y_points == [0.0, 0.0]
    assert z_matrix == [[0.0, 10.0], [0.0, 10.0]]
    dialog.close()


def test_lookup_matrix_linear_descriptor_uses_modal_matrix_to_build_block(monkeypatch) -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    descriptor = get_basic_block_catalog_descriptor_by_key()["lookup_matrix_linear"]

    class _MatrixDialogStub:
        def __init__(self, block_label: str, initial_x_points=None, initial_y_points=None, initial_z_matrix=None, parent=None) -> None:
            _unused = (block_label, initial_x_points, initial_y_points, initial_z_matrix, parent)

        def exec(self) -> int:
            return int(QtWidgets.QDialog.DialogCode.Accepted)

        def get_matrix_data(self) -> tuple[list[float], list[float], list[list[float]]]:
            return [0.0, 1.0], [0.0, 2.0], [[0.0, 10.0], [20.0, 30.0]]

    monkeypatch.setattr(dynamic_block_editor_module, "LookupMatrixLinearDialog", _MatrixDialogStub)
    block_item = editor.create_library_payload_item(descriptor, 10.0, 20.0)

    assert block_item is not None
    assert any(var.name.startswith("arr_x2_") for var in block_item.subsys.event_dict.keys())
    assert any(var.name.startswith("arr_y2_") for var in block_item.subsys.event_dict.keys())
    assert any(var.name.startswith("arr_z2_2_") for var in block_item.subsys.event_dict.keys())

    editor.has_unapplied_changes = False
    editor.close()


def test_inverse_lookup_array_linear_descriptor_uses_modal_points_to_build_block(monkeypatch) -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    descriptor = get_basic_block_catalog_descriptor_by_key()["inverse_lookup_array_linear"]

    class _DialogStub:
        def __init__(self, block_label: str, initial_points=None, parent=None) -> None:
            _unused = (block_label, initial_points, parent)

        def exec(self) -> int:
            return int(QtWidgets.QDialog.DialogCode.Accepted)

        def get_points(self) -> tuple[list[float], list[float]]:
            return [0.0, 1.0, 2.0], [0.0, 10.0, 20.0]

    monkeypatch.setattr(dynamic_block_editor_module, "LookupArrayLinearDialog", _DialogStub)
    block_item = editor.create_library_payload_item(descriptor, 10.0, 20.0)

    assert block_item is not None
    assert any(var.name.startswith("arr_x3_") for var in block_item.subsys.event_dict.keys())
    assert any(var.name.startswith("arr_y3_") for var in block_item.subsys.event_dict.keys())

    editor.has_unapplied_changes = False
    editor.close()


def test_lookup_array_spline_descriptor_uses_modal_points_to_build_block(monkeypatch) -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    descriptor = get_basic_block_catalog_descriptor_by_key()["lookup_array_spline"]

    class _DialogStub:
        def __init__(self, block_label: str, initial_points=None, parent=None) -> None:
            _unused = (block_label, initial_points, parent)

        def exec(self) -> int:
            return int(QtWidgets.QDialog.DialogCode.Accepted)

        def get_points(self) -> tuple[list[float], list[float]]:
            return [0.0, 1.0, 2.0], [0.0, 10.0, 20.0]

    monkeypatch.setattr(dynamic_block_editor_module, "LookupArrayLinearDialog", _DialogStub)
    block_item = editor.create_library_payload_item(descriptor, 10.0, 20.0)

    assert block_item is not None
    assert any(var.name.startswith("arr_x3_") for var in block_item.subsys.event_dict.keys())
    assert any(var.name.startswith("arr_y3_") for var in block_item.subsys.event_dict.keys())

    editor.has_unapplied_changes = False
    editor.close()


def test_lookup_matrix_spline_descriptor_uses_modal_matrix_to_build_block(monkeypatch) -> None:
    editor = _build_editor(DynamicSimulationMode.EMT)
    descriptor = get_basic_block_catalog_descriptor_by_key()["lookup_matrix_spline"]

    class _MatrixDialogStub:
        def __init__(self, block_label: str, initial_x_points=None, initial_y_points=None, initial_z_matrix=None, parent=None) -> None:
            _unused = (block_label, initial_x_points, initial_y_points, initial_z_matrix, parent)

        def exec(self) -> int:
            return int(QtWidgets.QDialog.DialogCode.Accepted)

        def get_matrix_data(self) -> tuple[list[float], list[float], list[list[float]]]:
            return [0.0, 1.0], [0.0, 2.0], [[0.0, 10.0], [20.0, 30.0]]

    monkeypatch.setattr(dynamic_block_editor_module, "LookupMatrixLinearDialog", _MatrixDialogStub)
    block_item = editor.create_library_payload_item(descriptor, 10.0, 20.0)

    assert block_item is not None
    assert any(var.name.startswith("arr_z2_2_") for var in block_item.subsys.event_dict.keys())

    editor.has_unapplied_changes = False
    editor.close()
