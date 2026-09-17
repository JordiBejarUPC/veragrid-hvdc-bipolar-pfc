# -*- coding: utf-8 -*-

# Form generated from reading UI file 'dynamic_plots_page_ui.ui'.
# Changes belong in the .ui file and must be regenerated with update_gui_file.py.

from PySide6.QtCore import QCoreApplication, QMetaObject, QSize, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLineEdit, QPushButton,
                               QSizePolicy, QSpacerItem, QSplitter, QToolBar,
                               QTreeView, QVBoxLayout, QWidget)
from VeraGrid.Gui.Icons.icons_rc import *


class Ui_DynamicPlotsPage(object):
    """Generated Qt widget tree for the global dynamic plots page."""

    def setupUi(self, DynamicPlotsPage):
        """Create the widgets declared in ``dynamic_plots_page_ui.ui``.

        :param DynamicPlotsPage: Widget receiving the generated controls.
        :return: None.
        """
        if not DynamicPlotsPage.objectName():
            DynamicPlotsPage.setObjectName(u"DynamicPlotsPage")
        else:
            pass
        DynamicPlotsPage.resize(900, 560)
        self.actionAddPlot = QAction(DynamicPlotsPage)
        self.actionAddPlot.setObjectName(u"actionAddPlot")
        add_icon = QIcon()
        add_icon.addFile(u":/Icons/icons/plus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionAddPlot.setIcon(add_icon)
        self.actionRemove = QAction(DynamicPlotsPage)
        self.actionRemove.setObjectName(u"actionRemove")
        remove_icon = QIcon()
        remove_icon.addFile(u":/Icons/icons/minus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionRemove.setIcon(remove_icon)
        self.mainLayout = QVBoxLayout(DynamicPlotsPage)
        self.mainLayout.setSpacing(0)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.plotsToolBar = QToolBar(DynamicPlotsPage)
        self.plotsToolBar.setObjectName(u"plotsToolBar")
        self.plotsToolBar.setMovable(False)
        self.plotsToolBar.setIconSize(QSize(24, 24))
        self.plotsToolBar.setFloatable(False)
        self.plotsToolBar.addAction(self.actionAddPlot)
        self.plotsToolBar.addAction(self.actionRemove)
        self.mainLayout.addWidget(self.plotsToolBar)
        self.searchFrame = QFrame(DynamicPlotsPage)
        self.searchFrame.setObjectName(u"searchFrame")
        search_size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        search_size_policy.setHorizontalStretch(0)
        search_size_policy.setVerticalStretch(0)
        search_size_policy.setHeightForWidth(self.searchFrame.sizePolicy().hasHeightForWidth())
        self.searchFrame.setSizePolicy(search_size_policy)
        self.searchFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.searchLayout = QHBoxLayout(self.searchFrame)
        self.searchLayout.setObjectName(u"searchLayout")
        self.searchLayout.setContentsMargins(0, 4, 0, 4)
        self.searchLineEdit = QLineEdit(self.searchFrame)
        self.searchLineEdit.setObjectName(u"searchLineEdit")
        self.searchLineEdit.setMinimumSize(QSize(240, 0))
        self.searchLineEdit.setMaximumSize(QSize(240, 16777215))
        self.searchLayout.addWidget(self.searchLineEdit)
        self.searchButton = QPushButton(self.searchFrame)
        self.searchButton.setObjectName(u"searchButton")
        self.searchButton.setMinimumSize(QSize(32, 0))
        self.searchButton.setMaximumSize(QSize(32, 16777215))
        search_icon = QIcon()
        search_icon.addFile(u":/Icons/icons/magnifying_glass.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.searchButton.setIcon(search_icon)
        self.searchButton.setFlat(True)
        self.searchLayout.addWidget(self.searchButton)
        self.searchHorizontalSpacer = QSpacerItem(
            40,
            20,
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self.searchLayout.addItem(self.searchHorizontalSpacer)
        self.mainLayout.addWidget(self.searchFrame)
        self.plotsSplitter = QSplitter(DynamicPlotsPage)
        self.plotsSplitter.setObjectName(u"plotsSplitter")
        self.plotsSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.availableVariablesTreeView = QTreeView(self.plotsSplitter)
        self.availableVariablesTreeView.setObjectName(u"availableVariablesTreeView")
        self.plotsSplitter.addWidget(self.availableVariablesTreeView)
        self.plotsTreeView = QTreeView(self.plotsSplitter)
        self.plotsTreeView.setObjectName(u"plotsTreeView")
        self.plotsSplitter.addWidget(self.plotsTreeView)
        self.mainLayout.addWidget(self.plotsSplitter)
        self.retranslateUi(DynamicPlotsPage)
        QMetaObject.connectSlotsByName(DynamicPlotsPage)

    def retranslateUi(self, DynamicPlotsPage):
        """Translate user-visible strings.

        :param DynamicPlotsPage: Widget receiving translated strings.
        :return: None.
        """
        DynamicPlotsPage.setWindowTitle(QCoreApplication.translate("DynamicPlotsPage", u"Dynamic Plots", None))
        self.actionAddPlot.setText(QCoreApplication.translate("DynamicPlotsPage", u"Add plot", None))
        self.actionAddPlot.setToolTip(QCoreApplication.translate("DynamicPlotsPage", u"Create a persistent dynamic plot", None))
        self.actionRemove.setText(QCoreApplication.translate("DynamicPlotsPage", u"Remove", None))
        self.actionRemove.setToolTip(QCoreApplication.translate("DynamicPlotsPage", u"Remove the selected plot or variable", None))
        self.searchLineEdit.setPlaceholderText(QCoreApplication.translate("DynamicPlotsPage", u"Type to search devices or variables", None))
        self.searchButton.setToolTip(QCoreApplication.translate("DynamicPlotsPage", u"Filter devices and variables", None))
        self.searchButton.setText("")
        self.availableVariablesTreeView.setToolTip(QCoreApplication.translate("DynamicPlotsPage", u"Drag a variable or parameter to a dynamic plot", None))
        self.plotsTreeView.setToolTip(QCoreApplication.translate("DynamicPlotsPage", u"Persistent dynamic plots for this simulation family", None))
