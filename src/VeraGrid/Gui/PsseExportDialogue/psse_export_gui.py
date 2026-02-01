# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'psse_export_gui.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)
from VeraGrid.Gui.Icons.icons_rc import *

class Ui_CgmesExportDialog(object):
    def setupUi(self, CgmesExportDialog):
        if not CgmesExportDialog.objectName():
            CgmesExportDialog.setObjectName(u"CgmesExportDialog")
        CgmesExportDialog.resize(343, 239)
        self.verticalLayout_2 = QVBoxLayout(CgmesExportDialog)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.frame_77 = QFrame(CgmesExportDialog)
        self.frame_77.setObjectName(u"frame_77")
        self.frame_77.setMinimumSize(QSize(300, 0))
        self.frame_77.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_77.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_11 = QGridLayout(self.frame_77)
        self.gridLayout_11.setObjectName(u"gridLayout_11")
        self.label_112 = QLabel(self.frame_77)
        self.label_112.setObjectName(u"label_112")

        self.gridLayout_11.addWidget(self.label_112, 2, 0, 1, 1)

        self.label_145 = QLabel(self.frame_77)
        self.label_145.setObjectName(u"label_145")
        self.label_145.setMinimumSize(QSize(24, 24))
        self.label_145.setMaximumSize(QSize(24, 24))
        self.label_145.setPixmap(QPixmap(u":/Icons/icons/new2c.png"))
        self.label_145.setScaledContents(True)

        self.gridLayout_11.addWidget(self.label_145, 0, 0, 1, 1)

        self.line_33 = QFrame(self.frame_77)
        self.line_33.setObjectName(u"line_33")
        palette = QPalette()
        brush = QBrush(QColor(186, 189, 182, 255))
        brush.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText, brush)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.WindowText, brush)
        brush1 = QBrush(QColor(190, 190, 190, 255))
        brush1.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, brush1)
        self.line_33.setPalette(palette)
        self.line_33.setFrameShadow(QFrame.Shadow.Plain)
        self.line_33.setLineWidth(4)
        self.line_33.setFrameShape(QFrame.Shape.HLine)

        self.gridLayout_11.addWidget(self.line_33, 1, 0, 1, 2)

        self.label_131 = QLabel(self.frame_77)
        self.label_131.setObjectName(u"label_131")
        palette1 = QPalette()
        brush2 = QBrush(QColor(85, 87, 83, 255))
        brush2.setStyle(Qt.BrushStyle.SolidPattern)
        palette1.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText, brush2)
        brush3 = QBrush(QColor(0, 0, 0, 255))
        brush3.setStyle(Qt.BrushStyle.SolidPattern)
        palette1.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.WindowText, brush3)
        palette1.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, brush1)
        self.label_131.setPalette(palette1)
        font = QFont()
        font.setPointSize(16)
        self.label_131.setFont(font)

        self.gridLayout_11.addWidget(self.label_131, 0, 1, 1, 1)

        self.verticalSpacer_20 = QSpacerItem(20, 436, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_11.addItem(self.verticalSpacer_20, 3, 1, 1, 1)

        self.raw_export_version_comboBox = QComboBox(self.frame_77)
        self.raw_export_version_comboBox.setObjectName(u"raw_export_version_comboBox")

        self.gridLayout_11.addWidget(self.raw_export_version_comboBox, 2, 1, 1, 1)

        self.frame = QFrame(self.frame_77)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.exportButton = QPushButton(self.frame)
        self.exportButton.setObjectName(u"exportButton")

        self.horizontalLayout.addWidget(self.exportButton)


        self.gridLayout_11.addWidget(self.frame, 4, 0, 1, 2)


        self.verticalLayout_2.addWidget(self.frame_77)


        self.retranslateUi(CgmesExportDialog)

        QMetaObject.connectSlotsByName(CgmesExportDialog)
    # setupUi

    def retranslateUi(self, CgmesExportDialog):
        CgmesExportDialog.setWindowTitle(QCoreApplication.translate("CgmesExportDialog", u"CGMES Export", None))
        self.label_112.setText(QCoreApplication.translate("CgmesExportDialog", u"Export version", None))
        self.label_145.setText("")
        self.label_131.setText(QCoreApplication.translate("CgmesExportDialog", u"Raw files", None))
        self.exportButton.setText(QCoreApplication.translate("CgmesExportDialog", u"Export", None))
    # retranslateUi

