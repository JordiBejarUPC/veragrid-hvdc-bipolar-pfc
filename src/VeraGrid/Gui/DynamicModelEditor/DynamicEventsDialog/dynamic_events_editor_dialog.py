# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from PySide6 import QtCore, QtWidgets

# Importing the compiled resource module registers every ``:/Icons`` path even
# when this dialog is created independently from the main VeraGrid window.
from VeraGrid.Gui.Icons import icons_rc


class Ui_DynamicEventDialogue:
    """Build the general, tabbed dynamic-events dialog shell."""

    def setupUi(self, dialog: QtWidgets.QDialog) -> None:
        """Create the widgets owned by the dynamic-events dialog.

        :param dialog: Dialog that owns the generated widget tree.
        :return: None.
        """
        dialog.setObjectName("DynamicEventDialogue")
        dialog.resize(1050, 650)
        dialog.setMinimumSize(QtCore.QSize(760, 480))
        self.mainLayout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(dialog)
        self.mainLayout.setContentsMargins(6, 6, 6, 6)
        self.mainLayout.setSpacing(4)

        # The tree toggle and device/mode tabs intentionally share one bar,
        # mirroring the dynamic-model editor navigation structure.
        self.navigationLayout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        self.navigationLayout.setContentsMargins(0, 0, 0, 0)
        self.treeButton: QtWidgets.QToolButton = QtWidgets.QToolButton(dialog)
        self.treeButton.setObjectName("treeButton")
        self.treeButton.setCheckable(True)
        self.treeButton.setAutoRaise(True)
        self.navigationLayout.addWidget(self.treeButton)
        self.tabBar: QtWidgets.QTabBar = QtWidgets.QTabBar(dialog)
        self.tabBar.setObjectName("tabBar")
        self.tabBar.setTabsClosable(True)
        self.tabBar.setMovable(False)
        self.tabBar.setExpanding(False)
        self.navigationLayout.addWidget(self.tabBar, 1)
        self.mainLayout.addLayout(self.navigationLayout)

        self.splitter: QtWidgets.QSplitter = QtWidgets.QSplitter(dialog)
        self.splitter.setObjectName("splitter")
        self.splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.treeFrame: QtWidgets.QFrame = QtWidgets.QFrame(self.splitter)
        self.treeFrame.setObjectName("treeFrame")
        self.treeFrame.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.treeFrameLayout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self.treeFrame)
        self.treeFrameLayout.setContentsMargins(0, 0, 0, 0)
        self.pagesStack: QtWidgets.QStackedWidget = QtWidgets.QStackedWidget(self.splitter)
        self.pagesStack.setObjectName("pagesStack")
        self.emptyPage: QtWidgets.QWidget = QtWidgets.QWidget(self.pagesStack)
        self.emptyPageLayout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self.emptyPage)
        self.emptyPageLayout.addStretch(1)
        self.emptyLabel: QtWidgets.QLabel = QtWidgets.QLabel(self.emptyPage)
        self.emptyLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.emptyLabel.setWordWrap(True)
        self.emptyPageLayout.addWidget(self.emptyLabel)
        self.emptyPageLayout.addStretch(1)
        self.pagesStack.addWidget(self.emptyPage)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 8)
        self.mainLayout.addWidget(self.splitter, 1)

        # Keep the persisted-group workflow visually separate from the final
        # transaction controls, as in the previous event editor.
        self.groupsLayout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        self.groupsLayout.addStretch(1)
        self.newGroupButton: QtWidgets.QPushButton = QtWidgets.QPushButton(dialog)
        self.newGroupButton.setObjectName("newGroupButton")
        self.groupsLayout.addWidget(self.newGroupButton)
        self.mainLayout.addLayout(self.groupsLayout)

        self.dialogButtonBox: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(dialog)
        self.dialogButtonBox.setObjectName("dialogButtonBox")
        self.dialogButtonBox.setStandardButtons(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.mainLayout.addWidget(self.dialogButtonBox)

        self.retranslateUi(dialog)
        QtCore.QMetaObject.connectSlotsByName(dialog)

    def retranslateUi(self, dialog: QtWidgets.QDialog) -> None:
        """Apply translated strings to the dialog shell.

        :param dialog: Dialog whose visible strings are refreshed.
        :return: None.
        """
        dialog.setWindowTitle(QtCore.QCoreApplication.translate("DynamicEventDialogue", "Dynamic events"))
        self.treeButton.setText(QtCore.QCoreApplication.translate("DynamicEventDialogue", "Devices"))
        self.treeButton.setToolTip(
            QtCore.QCoreApplication.translate("DynamicEventDialogue", "Show or hide the device tree")
        )
        self.emptyLabel.setText(
            QtCore.QCoreApplication.translate(
                "DynamicEventDialogue",
                "Choose RMS events or EMT events for a device from the device tree.",
            )
        )
        self.newGroupButton.setText(
            QtCore.QCoreApplication.translate("DynamicEventDialogue", "➕ New Event Group")
        )
