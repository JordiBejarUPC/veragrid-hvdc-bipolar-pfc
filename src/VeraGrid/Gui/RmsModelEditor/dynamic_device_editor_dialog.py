# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dynamic_device_editor_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QTabWidget, QVBoxLayout, QWidget)
from VeraGrid.Gui.Icons.icons_rc import *

class Ui_DynamicDeviceEditorDialog(object):
    def setupUi(self, DynamicDeviceEditorDialog):
        if not DynamicDeviceEditorDialog.objectName():
            DynamicDeviceEditorDialog.setObjectName(u"DynamicDeviceEditorDialog")
        DynamicDeviceEditorDialog.resize(1600, 1000)
        self.verticalLayout = QVBoxLayout(DynamicDeviceEditorDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(6, 6, 6, 6)
        self.headerFrame = QFrame(DynamicDeviceEditorDialog)
        self.headerFrame.setObjectName(u"headerFrame")
        self.headerFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.horizontalLayout = QHBoxLayout(self.headerFrame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.deviceCaptionLabel = QLabel(self.headerFrame)
        self.deviceCaptionLabel.setObjectName(u"deviceCaptionLabel")

        self.horizontalLayout.addWidget(self.deviceCaptionLabel)

        self.deviceNameLabel = QLabel(self.headerFrame)
        self.deviceNameLabel.setObjectName(u"deviceNameLabel")

        self.horizontalLayout.addWidget(self.deviceNameLabel)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)


        self.verticalLayout.addWidget(self.headerFrame)

        self.domainTabWidget = QTabWidget(DynamicDeviceEditorDialog)
        self.domainTabWidget.setObjectName(u"domainTabWidget")
        self.domainTabWidget.setDocumentMode(True)
        self.rmsTab = QWidget()
        self.rmsTab.setObjectName(u"rmsTab")
        self.rmsTabLayout = QVBoxLayout(self.rmsTab)
        self.rmsTabLayout.setObjectName(u"rmsTabLayout")
        self.rmsTabLayout.setContentsMargins(0, 0, 0, 0)
        self.domainTabWidget.addTab(self.rmsTab, "")
        self.emtTab = QWidget()
        self.emtTab.setObjectName(u"emtTab")
        self.emtTabLayout = QVBoxLayout(self.emtTab)
        self.emtTabLayout.setObjectName(u"emtTabLayout")
        self.emtTabLayout.setContentsMargins(0, 0, 0, 0)
        self.domainTabWidget.addTab(self.emtTab, "")

        self.verticalLayout.addWidget(self.domainTabWidget)

        self.footerFrame = QFrame(DynamicDeviceEditorDialog)
        self.footerFrame.setObjectName(u"footerFrame")
        self.footerFrame.setMaximumSize(QSize(16777215, 40))
        self.footerFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.footerLayout = QHBoxLayout(self.footerFrame)
        self.footerLayout.setObjectName(u"footerLayout")
        self.footerLayout.setContentsMargins(0, 0, 0, 0)
        self.footerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.footerLayout.addItem(self.footerSpacer)

        self.cancelButton = QPushButton(self.footerFrame)
        self.cancelButton.setObjectName(u"cancelButton")

        self.footerLayout.addWidget(self.cancelButton)

        self.doItButton = QPushButton(self.footerFrame)
        self.doItButton.setObjectName(u"doItButton")

        self.footerLayout.addWidget(self.doItButton)


        self.verticalLayout.addWidget(self.footerFrame)


        self.retranslateUi(DynamicDeviceEditorDialog)

        self.domainTabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(DynamicDeviceEditorDialog)
    # setupUi

    def retranslateUi(self, DynamicDeviceEditorDialog):
        DynamicDeviceEditorDialog.setWindowTitle(QCoreApplication.translate("DynamicDeviceEditorDialog", u"Dynamic Device Editor", None))
        self.deviceCaptionLabel.setText(QCoreApplication.translate("DynamicDeviceEditorDialog", u"Device:", None))
        self.deviceNameLabel.setText(QCoreApplication.translate("DynamicDeviceEditorDialog", u"device", None))
        self.domainTabWidget.setTabText(self.domainTabWidget.indexOf(self.rmsTab), QCoreApplication.translate("DynamicDeviceEditorDialog", u"RMS", None))
        self.domainTabWidget.setTabText(self.domainTabWidget.indexOf(self.emtTab), QCoreApplication.translate("DynamicDeviceEditorDialog", u"EMT", None))
        self.cancelButton.setText(QCoreApplication.translate("DynamicDeviceEditorDialog", u"Cancel", None))
        self.doItButton.setText(QCoreApplication.translate("DynamicDeviceEditorDialog", u"Do it!", None))
    # retranslateUi

