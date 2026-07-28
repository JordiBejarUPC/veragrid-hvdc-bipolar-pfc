# -*- coding: utf-8 -*-

from PySide6.QtCore import QCoreApplication, QMetaObject
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QSpacerItem, QTableView, QVBoxLayout


class Ui_LineLocationsEditorWidget(object):
    def setupUi(self, LineLocationsEditorWidget):
        if not LineLocationsEditorWidget.objectName():
            LineLocationsEditorWidget.setObjectName(u"LineLocationsEditorWidget")
        LineLocationsEditorWidget.resize(720, 420)
        self.mainLayout = QVBoxLayout(LineLocationsEditorWidget)
        self.mainLayout.setObjectName(u"mainLayout")
        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setObjectName(u"buttonLayout")
        self.addButton = QPushButton(LineLocationsEditorWidget)
        self.addButton.setObjectName(u"addButton")
        self.buttonLayout.addWidget(self.addButton)
        self.removeButton = QPushButton(LineLocationsEditorWidget)
        self.removeButton.setObjectName(u"removeButton")
        self.buttonLayout.addWidget(self.removeButton)
        self.importButton = QPushButton(LineLocationsEditorWidget)
        self.importButton.setObjectName(u"importButton")
        self.buttonLayout.addWidget(self.importButton)
        self.exportButton = QPushButton(LineLocationsEditorWidget)
        self.exportButton.setObjectName(u"exportButton")
        self.buttonLayout.addWidget(self.exportButton)
        self.copyButton = QPushButton(LineLocationsEditorWidget)
        self.copyButton.setObjectName(u"copyButton")
        self.buttonLayout.addWidget(self.copyButton)
        self.pasteButton = QPushButton(LineLocationsEditorWidget)
        self.pasteButton.setObjectName(u"pasteButton")
        self.buttonLayout.addWidget(self.pasteButton)
        self.buttonSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.buttonLayout.addItem(self.buttonSpacer)
        self.mainLayout.addLayout(self.buttonLayout)
        self.tableView = QTableView(LineLocationsEditorWidget)
        self.tableView.setObjectName(u"tableView")
        self.mainLayout.addWidget(self.tableView)
        self.retranslateUi(LineLocationsEditorWidget)
        QMetaObject.connectSlotsByName(LineLocationsEditorWidget)

    def retranslateUi(self, LineLocationsEditorWidget):
        LineLocationsEditorWidget.setWindowTitle(QCoreApplication.translate("LineLocationsEditorWidget", u"Form", None))
        self.addButton.setText(QCoreApplication.translate("LineLocationsEditorWidget", u"Add point", None))
        self.removeButton.setText(QCoreApplication.translate("LineLocationsEditorWidget", u"Remove selected", None))
        self.importButton.setText(QCoreApplication.translate("LineLocationsEditorWidget", u"Import CSV", None))
        self.exportButton.setText(QCoreApplication.translate("LineLocationsEditorWidget", u"Export CSV", None))
        self.copyButton.setText(QCoreApplication.translate("LineLocationsEditorWidget", u"Copy", None))
        self.pasteButton.setText(QCoreApplication.translate("LineLocationsEditorWidget", u"Paste", None))
