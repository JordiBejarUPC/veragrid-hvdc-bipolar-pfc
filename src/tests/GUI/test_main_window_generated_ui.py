import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Tuple

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.Main.MainWindow import Ui_mainWindow
from VeraGrid.Gui.Main.SubClasses.base_gui import refresh_translated_splitter_layouts


def build_main_window() -> Tuple[QtWidgets.QMainWindow, Ui_mainWindow]:
    """
    Build the generated main-window UI on a plain Qt main window.

    :return: Main window and configured generated UI object.
    """
    window: QtWidgets.QMainWindow = QtWidgets.QMainWindow()
    ui: Ui_mainWindow = Ui_mainWindow()
    ui.setupUi(window)
    return window, ui


def get_main_window_ui_path() -> Path:
    """
    Return the generated main-window UI source path.

    :return: Main-window UI XML file path.
    """
    return Path(__file__).resolve().parents[2] / "VeraGrid" / "Gui" / "Main" / "MainWindow.ui"


def get_gui_ui_paths() -> list[Path]:
    """
    Return every shipped GUI ``.ui`` file path.

    :return: Sorted GUI UI source paths.
    """
    gui_root: Path = Path(__file__).resolve().parents[2] / "VeraGrid" / "Gui"
    return sorted(gui_root.rglob("*.ui"))


def get_declared_shortcuts_from_ui_file(ui_file_path: Path) -> list[tuple[str, str]]:
    """
    Return action shortcuts declared directly in one UI source file.

    This audit intentionally reads the ``.ui`` file instead of constructing the
    Qt window. The failure mode being guarded is purely declarative: once a
    shortcut sequence such as ``Ctrl+Alt++`` is shipped in the source UI,
    Windows AltGr text entry can collide with it regardless of runtime wiring.
    A static parse is therefore the smallest and safest test.

    :param ui_file_path: UI XML file to inspect.
    :return: ``(action_name, shortcut_text)`` entries from the UI source.
    """
    ui_root: ET.Element = ET.parse(ui_file_path).getroot()
    action_entries: list[tuple[str, str]] = list()
    action_element: ET.Element

    for action_element in ui_root.findall(".//action"):
        action_name: str = str(action_element.get("name", "")).strip()
        shortcut_text: str = ""
        property_element: ET.Element

        for property_element in action_element.findall("property"):
            if property_element.get("name") == "shortcut":
                shortcut_text = "".join(property_element.itertext()).strip()
                break
            else:
                pass

        if len(action_name) > 0 and len(shortcut_text) > 0:
            action_entries.append((action_name, shortcut_text))
        else:
            pass

    return action_entries


def test_generated_main_window_builds_core_tab_widgets(qt_app: object) -> None:
    """
    Check that generated MainWindow UI exposes the tab widgets used by VeraGridMainGUI.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    window: QtWidgets.QMainWindow
    ui: Ui_mainWindow
    window, ui = build_main_window()

    assert ui.mainTabWidget.count() > 0
    assert ui.modelTabWidget.count() > 0
    assert ui.settingsTabWidget.count() > 0
    assert ui.resultsTabWidget.count() > 0
    assert ui.mainTabWidget.currentIndex() >= 0
    assert ui.modelTabWidget.currentIndex() >= 0

    window.close()
    window.deleteLater()


def test_generated_main_window_exposes_splitters_used_by_main_gui(qt_app: object) -> None:
    """
    Check that generated MainWindow UI exposes the splitters configured by VeraGridMainGUI.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    window: QtWidgets.QMainWindow
    ui: Ui_mainWindow
    window, ui = build_main_window()

    assert ui.dataStructuresSplitter.count() >= 2
    assert ui.simulationDataSplitter.count() >= 2
    assert ui.results_splitter.count() >= 2
    assert ui.diagram_selection_splitter.count() >= 2

    window.close()
    window.deleteLater()


def test_generated_main_window_exposes_main_actions(qt_app: object) -> None:
    """
    Check that generated MainWindow UI exposes actions connected by Main subclasses.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    window: QtWidgets.QMainWindow
    ui: Ui_mainWindow
    window, ui = build_main_window()

    assert ui.actionPower_flow.text() != ""
    assert ui.actionPower_flow_3ph.text() != ""
    assert ui.actionLinearAnalysis.text() != ""
    assert ui.actionRun_Dynamic_RMS_Simulation.text() != ""
    assert ui.actionRun_Dynamic_EMT_Simulation.text() != ""
    assert ui.actionRun_Small_Signal_RMS_Simulation.text() != ""
    assert ui.actionRun_Small_Signal_EMT_Simulation.text() != ""
    assert ui.actionDelete_selected.text() != ""
    assert ui.actionSync.text() != ""

    window.close()
    window.deleteLater()


def test_gui_ui_shortcuts_do_not_use_ctrl_alt_prefix(qt_app: object) -> None:
    """
    Check that no shipped GUI ``.ui`` action uses a ``Ctrl+Alt`` shortcut chord.

    On Windows many keyboard layouts report ``AltGr`` as ``Ctrl+Alt``. A
    top-level GUI shortcut beginning with that prefix can therefore steal text
    entry from child widgets such as ``QLineEdit`` when users try to type
    layout-specific characters like ``]``. The safe fix is to remove the
    ``Ctrl+Alt`` shortcut and replace it with a non-conflicting sequence.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    conflicting_shortcuts: list[str] = list()
    source_root: Path = Path(__file__).resolve().parents[2]
    ui_file_path: Path
    action_name: str
    shortcut_text: str

    for ui_file_path in get_gui_ui_paths():
        for action_name, shortcut_text in get_declared_shortcuts_from_ui_file(ui_file_path=ui_file_path):
            if shortcut_text.startswith("Ctrl+Alt+"):
                conflicting_shortcuts.append(
                    f"{ui_file_path.relative_to(source_root)}: {action_name}: {shortcut_text}"
                )
            else:
                pass

    assert conflicting_shortcuts == list(), (
        "GUI shortcuts declared in .ui files must not start with 'Ctrl+Alt+'. On Windows many keyboard layouts "
        "report AltGr as Ctrl+Alt, so these shortcuts collide with text entry in child widgets "
        "such as QLineEdit and can make characters like ']' impossible to type. "
        "Remove the Ctrl+Alt shortcut and replace it with a non-conflicting sequence. "
        f"Conflicting shortcuts: {', '.join(conflicting_shortcuts)}"
    )


def test_refresh_translated_splitter_layouts_respects_updated_widget_hints(qt_app: object) -> None:
    """
    Check that the splitter refresh helper keeps sections large enough for updated hints.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    window: QtWidgets.QWidget = QtWidgets.QWidget()
    layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(window)
    splitter: QtWidgets.QSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
    left_label: QtWidgets.QLabel = QtWidgets.QLabel("Short")
    right_label: QtWidgets.QLabel = QtWidgets.QLabel("Right")
    sizes: list[int]

    splitter.addWidget(left_label)
    splitter.addWidget(right_label)
    layout.addWidget(splitter)
    window.resize(400, 100)
    window.show()
    QtWidgets.QApplication.processEvents()

    left_label.setMinimumWidth(220)
    refresh_translated_splitter_layouts(window)
    QtWidgets.QApplication.processEvents()
    sizes = splitter.sizes()

    assert sizes[0] >= 220

    window.close()
    window.deleteLater()
