from __future__ import annotations

import json
from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets
import pytest

import VeraGridEngine.api as vge
from VeraGridEngine.Devices.Diagrams.diagram_tree import DiagramFolder, DiagramTree
from VeraGridEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from VeraGridEngine.Devices.Diagrams.map_diagram import MapDiagram
from VeraGrid.Gui.Diagrams.diagrams_model import DiagramsTreeModel, DiagramsModel
from VeraGrid.Gui.Main.SubClasses.Model.data_base import DataBaseTableMain


def test_diagrams_tree_model_structure_and_navigation(qt_app: object) -> None:
    del qt_app

    tree = DiagramTree()
    f1 = tree.add_folder("Region North")
    f2 = tree.add_folder("Zone A", parent=f1)
    d_root = SchematicDiagram(name="Root Schematic")
    d_f1 = SchematicDiagram(name="North 220kV")
    d_f2 = MapDiagram(name="Zone A Geo")

    tree.add_diagram(d_root)
    tree.add_diagram(d_f1, folder=f1)
    tree.add_diagram(d_f2, folder=f2)

    model = DiagramsTreeModel(tree=tree)

    # Root level has 1 folder and 1 diagram
    assert model.rowCount(QtCore.QModelIndex()) == 2
    assert model.columnCount(QtCore.QModelIndex()) == 1

    # Row 0 is f1, Row 1 is d_root
    idx_f1 = model.index(0, 0, QtCore.QModelIndex())
    assert idx_f1.isValid()
    assert model.data(idx_f1, QtCore.Qt.ItemDataRole.DisplayRole) == "Region North"
    assert model.get_item(idx_f1) is f1

    idx_root_d = model.index(1, 0, QtCore.QModelIndex())
    assert idx_root_d.isValid()
    assert model.data(idx_root_d, QtCore.Qt.ItemDataRole.DisplayRole) == "Root Schematic"
    assert model.get_item(idx_root_d) is d_root

    # Children of f1: 1 subfolder (f2) and 1 diagram (d_f1)
    assert model.rowCount(idx_f1) == 2
    idx_f2 = model.index(0, 0, idx_f1)
    assert idx_f2.isValid()
    assert model.data(idx_f2, QtCore.Qt.ItemDataRole.DisplayRole) == "Zone A"
    assert model.get_item(idx_f2) is f2

    idx_d_f1 = model.index(1, 0, idx_f1)
    assert idx_d_f1.isValid()
    assert model.data(idx_d_f1, QtCore.Qt.ItemDataRole.DisplayRole) == "North 220kV"
    assert model.get_item(idx_d_f1) is d_f1

    # Children of f2: 1 diagram (d_f2)
    assert model.rowCount(idx_f2) == 1
    idx_d_f2 = model.index(0, 0, idx_f2)
    assert idx_d_f2.isValid()
    assert model.data(idx_d_f2, QtCore.Qt.ItemDataRole.DisplayRole) == "Zone A Geo"
    assert model.get_item(idx_d_f2) is d_f2

    # Verify parent indices
    assert model.parent(idx_f1) == QtCore.QModelIndex()
    assert model.parent(idx_root_d) == QtCore.QModelIndex()
    assert model.parent(idx_f2) == idx_f1
    assert model.parent(idx_d_f1) == idx_f1
    assert model.parent(idx_d_f2) == idx_f2

    # index_for_item
    assert model.index_for_item(f1) == idx_f1
    assert model.index_for_item(f2) == idx_f2
    assert model.index_for_item(d_root) == idx_root_d
    assert model.index_for_item(d_f1) == idx_d_f1
    assert model.index_for_item(d_f2) == idx_d_f2


def test_diagrams_tree_model_rename_and_decorations(qt_app: object) -> None:
    del qt_app

    tree = DiagramTree()
    folder = tree.add_folder("Substations")
    diag = SchematicDiagram(name="Main Station")
    tree.add_diagram(diag, folder=folder)

    model = DiagramsTreeModel(tree=tree)
    idx_folder = model.index(0, 0, QtCore.QModelIndex())
    idx_diag = model.index(0, 0, idx_folder)

    # Decoration role check
    folder_icon = model.data(idx_folder, QtCore.Qt.ItemDataRole.DecorationRole)
    assert isinstance(folder_icon, QtGui.QIcon)
    diag_icon = model.data(idx_diag, QtCore.Qt.ItemDataRole.DecorationRole)
    assert isinstance(diag_icon, QtGui.QIcon)

    # Rename folder
    renamed = model.setData(idx_folder, "Grid Substations", QtCore.Qt.ItemDataRole.EditRole)
    assert renamed is True
    assert folder.name == "Grid Substations"
    assert model.data(idx_folder, QtCore.Qt.ItemDataRole.DisplayRole) == "Grid Substations"

    # Rename diagram
    renamed_diag = model.setData(idx_diag, "Station 400kV", QtCore.Qt.ItemDataRole.EditRole)
    assert renamed_diag is True
    assert diag.name == "Station 400kV"
    assert model.data(idx_diag, QtCore.Qt.ItemDataRole.DisplayRole) == "Station 400kV"

    # Empty name rejected
    assert model.setData(idx_folder, "   ", QtCore.Qt.ItemDataRole.EditRole) is False
    assert folder.name == "Grid Substations"


def test_diagrams_tree_model_drag_and_drop(qt_app: object) -> None:
    del qt_app

    tree = DiagramTree()
    folder_a = tree.add_folder("Folder A")
    folder_b = tree.add_folder("Folder B")
    diag = SchematicDiagram(name="Diagram 1")
    tree.add_diagram(diag, folder=folder_a)

    model = DiagramsTreeModel(tree=tree)
    idx_fa = model.index(0, 0, QtCore.QModelIndex())
    idx_fb = model.index(1, 0, QtCore.QModelIndex())
    idx_diag = model.index(0, 0, idx_fa)

    # Mime data serialization
    mime = model.mimeData([idx_diag])
    assert mime.hasFormat(DiagramsTreeModel.MIME_TYPE)
    payload = json.loads(bytes(mime.data(DiagramsTreeModel.MIME_TYPE)).decode("utf-8"))
    assert payload["type"] == "diagram"
    assert payload["idtag"] == diag.idtag

    # Drop into Folder B
    success = model.dropMimeData(mime, QtCore.Qt.DropAction.MoveAction, -1, -1, idx_fb)
    assert success is True
    assert diag in folder_b.diagrams
    assert diag not in folder_a.diagrams
    assert diag.group is folder_b

    # Drag Folder A into Folder B
    mime_fa = model.mimeData([idx_fa])
    success_fa = model.dropMimeData(mime_fa, QtCore.Qt.DropAction.MoveAction, -1, -1, idx_fb)
    assert success_fa is True
    assert folder_a in folder_b.folders
    assert folder_a.parent is folder_b


def test_main_gui_diagram_tree_operations(qt_app: object) -> None:
    del qt_app

    gui = DataBaseTableMain()
    gui.hide()
    gui.circuit = vge.MultiCircuit()
    gui.remove_all_diagrams()

    # Add folders programmatically
    f_north = gui.add_diagram_folder(folder_name="North")
    assert f_north is not None
    assert f_north in gui.circuit.diagrams.folders

    f_sub = gui.add_diagram_folder(parent_folder=f_north, folder_name="Substation 1")
    assert f_sub is not None
    assert f_sub in f_north.folders
    assert f_sub.parent is f_north

    # Add a schematic diagram
    diag = SchematicDiagram(name="Overview")
    gui.circuit.add_diagram(diag, folder=f_sub)
    gui.create_circuit_stored_diagrams()

    assert len(gui.circuit.diagrams) == 1
    assert len(gui.diagram_widgets_list) == 1
    assert gui.diagram_widgets_list[0].diagram is diag
    assert diag.group is f_sub

    # Selected widget is the schematic
    selected_widget = gui.get_selected_diagram_widget()
    assert selected_widget is gui.diagram_widgets_list[0]

    # Delete folder f_north should delete f_sub and diag
    model = gui.ui.diagramsTreeView.model()
    idx_north = model.index_for_item(f_north)
    assert idx_north.isValid()

    # Select f_north
    gui.ui.diagramsTreeView.selectionModel().select(
        idx_north,
        QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect | QtCore.QItemSelectionModel.SelectionFlag.Rows
    )

    # Test removing folder f_north programmatically (bypassing confirmation prompt)
    folders_to_delete = {f_north}
    diagrams_to_delete = set(f_north.get_all_diagrams())
    assert diag in diagrams_to_delete

    gui.circuit.diagrams.remove_folder(f_north)
    gui.set_diagrams_list_view()

    assert len(gui.circuit.diagrams.folders) == 0
    assert len(gui.circuit.diagrams) == 0

    gui.remove_all_diagrams()
