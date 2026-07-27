# -*- coding: utf-8 -*-

from PySide6.QtCore import QCoreApplication, QMetaObject
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QSizePolicy, QSpacerItem, QTableView, QVBoxLayout


class Ui_AdmittanceMatrixEditorWidget(object):
    def setupUi(self, AdmittanceMatrixEditorWidget):
        if not AdmittanceMatrixEditorWidget.objectName():
            AdmittanceMatrixEditorWidget.setObjectName(u"AdmittanceMatrixEditorWidget")
        AdmittanceMatrixEditorWidget.resize(640, 360)
        self.mainLayout = QVBoxLayout(AdmittanceMatrixEditorWidget)
        self.mainLayout.setObjectName(u"mainLayout")
        self.titleLabel = QLabel(AdmittanceMatrixEditorWidget)
        self.titleLabel.setObjectName(u"titleLabel")
        self.titleLabel.setWordWrap(True)
        self.mainLayout.addWidget(self.titleLabel)
        self.phaseLayout = QHBoxLayout()
        self.phaseLayout.setObjectName(u"phaseLayout")
        self.phasesLabel = QLabel(AdmittanceMatrixEditorWidget)
        self.phasesLabel.setObjectName(u"phasesLabel")
        self.phaseLayout.addWidget(self.phasesLabel)
        self.phaseNCheckBox = QCheckBox(AdmittanceMatrixEditorWidget)
        self.phaseNCheckBox.setObjectName(u"phaseNCheckBox")
        self.phaseLayout.addWidget(self.phaseNCheckBox)
        self.phaseACheckBox = QCheckBox(AdmittanceMatrixEditorWidget)
        self.phaseACheckBox.setObjectName(u"phaseACheckBox")
        self.phaseLayout.addWidget(self.phaseACheckBox)
        self.phaseBCheckBox = QCheckBox(AdmittanceMatrixEditorWidget)
        self.phaseBCheckBox.setObjectName(u"phaseBCheckBox")
        self.phaseLayout.addWidget(self.phaseBCheckBox)
        self.phaseCCheckBox = QCheckBox(AdmittanceMatrixEditorWidget)
        self.phaseCCheckBox.setObjectName(u"phaseCCheckBox")
        self.phaseLayout.addWidget(self.phaseCCheckBox)
        self.phaseSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.phaseLayout.addItem(self.phaseSpacer)
        self.mainLayout.addLayout(self.phaseLayout)
        self.matrixTableView = QTableView(AdmittanceMatrixEditorWidget)
        self.matrixTableView.setObjectName(u"matrixTableView")
        self.mainLayout.addWidget(self.matrixTableView)
        self.retranslateUi(AdmittanceMatrixEditorWidget)
        QMetaObject.connectSlotsByName(AdmittanceMatrixEditorWidget)

    def retranslateUi(self, AdmittanceMatrixEditorWidget):
        AdmittanceMatrixEditorWidget.setWindowTitle(QCoreApplication.translate("AdmittanceMatrixEditorWidget", u"Form", None))
        self.titleLabel.setText(QCoreApplication.translate("AdmittanceMatrixEditorWidget", u"Admittance matrix", None))
        self.phasesLabel.setText(QCoreApplication.translate("AdmittanceMatrixEditorWidget", u"Phases:", None))
        self.phaseNCheckBox.setText(QCoreApplication.translate("AdmittanceMatrixEditorWidget", u"N", None))
        self.phaseACheckBox.setText(QCoreApplication.translate("AdmittanceMatrixEditorWidget", u"A", None))
        self.phaseBCheckBox.setText(QCoreApplication.translate("AdmittanceMatrixEditorWidget", u"B", None))
        self.phaseCCheckBox.setText(QCoreApplication.translate("AdmittanceMatrixEditorWidget", u"C", None))
