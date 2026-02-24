# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import sys
# GUI imports
from VeraGrid.Gui.gui_functions import *
from VeraGrid.Gui.TreeModelViewer.MainWindow import *


########################################################################################################################
# Main Window
########################################################################################################################

class TreeModelViewerGUI(QMainWindow):

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        QMainWindow.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Roseta Explorer')
        self.setAcceptDrops(True)

        self.open_file_thread_object = None

        self.accepted_extensions = ['.zip', '.xml']
        self.project_directory = ''
        self.lock_ui = True

        # search proxy model
        self.current_model = None
        self.proxyModel = QtCore.QSortFilterProxyModel(self.ui.mainTreeView)
        self.proxyModel.setRecursiveFilteringEnabled(True)
        self.proxyModel.setFilterKeyColumn(0)
        self.ui.mainTreeView.setSortingEnabled(True)

        self.ui.filterComboBox.setModel(get_list_model(['Class', 'Property', 'Value']))
        self.ui.filterComboBox.setCurrentIndex(0)

        # Connections --------------------------------------------------------------------------------------------------
        # self.ui.actionOpen.triggered.connect(self.open_file)

        self.ui.filterButton.clicked.connect(self.filter_main_tree)

        self.ui.mainTreeView.clicked.connect(self.update_main_tree_on_click)
        self.ui.mainTreeView.expanded.connect(self.on_tree_expanded)

        self.ui.filterComboBox.currentTextChanged.connect(self.on_filter_combobox_changed)

        self.UNLOCK()

    def LOCK(self, val=True):
        """
        Lock the interface to prevent new simulation launches
        :param val:
        :return:
        """
        self.lock_ui = val
        QtGui.QGuiApplication.processEvents()

    def UNLOCK(self):
        """
        Unlock the interface
        """
        if not self.any_thread_running():
            self.LOCK(False)

    def filter_main_tree(self):
        self.proxyModel.setFilterRegularExpression(self.ui.filterLineEdit.text())

    def update_main_tree_on_click(self, index):
        # ix = self.proxyModel.mapToSource(index)
        # parent = self.current_model.itemFromIndex(ix)
        # for text in ['Object class', 'Property', 'Value']:
        #     children = QtGui.QStandardItem("{}_{}".format(parent.text(), text))
        #     parent.appendRow(children)
        # self.ui.mainTreeView.expand(index)
        pass

    def on_tree_expanded(self, index):
        if self.current_model is None:
            return
        src_index = self.proxyModel.mapToSource(index)
        item = self.current_model.itemFromIndex(src_index)
        if item is None:
            return
        populate_cim_item_children(item, editable=False)

    def on_filter_combobox_changed(self):

        idx = self.ui.filterComboBox.currentIndex()

        if idx > -1:
            self.proxyModel.setFilterKeyColumn(idx)

    def get_process_threads(self):
        """
        Get all threads that has to do with processing
        :return: list of process threads
        """
        all_threads = [self.open_file_thread_object]
        return all_threads

    def get_all_threads(self):
        """
        Get all threads
        :return: list of all threads
        """
        all_threads = self.get_process_threads()
        return all_threads

    def any_thread_running(self):
        """
        Checks if any thread is running
        :return: True/False
        """
        val = False

        # this list cannot be created only once, because the None will be copied
        # instead of being a pointer to the future value like it would in a typed language
        all_threads = self.get_all_threads()

        for thr in all_threads:
            if thr is not None:
                if thr.isRunning():
                    return True
        return val

    def set_circuit(self, mdl):

        if mdl is not None:
            self.current_model = get_cim_tree_model(mdl)

            self.proxyModel.setSourceModel(self.current_model)
            self.ui.mainTreeView.setModel(self.proxyModel)



def runTreeModelViewerGUI(use_native_dialogues=False):
    """
    Main function to run the GUI
    :return:
    """
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # ['Breeze', 'Oxygen', 'QtCurve', 'Windows', 'Fusion']

    # dark = QDarkPalette(None)
    # dark.set_app(app)

    window = TreeModelViewerGUI()
    h = 740
    window.resize(int(1.61 * h), h)  # golden ratio :)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    runTreeModelViewerGUI()
