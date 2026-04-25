# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'procedural_grid_ui.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
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
    QHBoxLayout, QLabel, QListView, QPushButton,
    QSizePolicy, QSpacerItem, QSpinBox, QSplitter,
    QVBoxLayout, QWidget)

from VeraGrid.Gui.Widgets.matplotlibwidget import MatplotlibWidget
from VeraGrid.Gui.Icons.icons_rc import *

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(807, 650)
        self.verticalLayout_3 = QVBoxLayout(Dialog)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.mainSplitter = QSplitter(Dialog)
        self.mainSplitter.setObjectName(u"mainSplitter")
        self.mainSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.frame_2 = QFrame(self.mainSplitter)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout = QVBoxLayout(self.frame_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label = QLabel(self.frame_2)
        self.label.setObjectName(u"label")

        self.verticalLayout.addWidget(self.label)

        self.methodComboBox = QComboBox(self.frame_2)
        self.methodComboBox.setObjectName(u"methodComboBox")

        self.verticalLayout.addWidget(self.methodComboBox)

        self.label_3 = QLabel(self.frame_2)
        self.label_3.setObjectName(u"label_3")

        self.verticalLayout.addWidget(self.label_3)

        self.targetSubstationListView = QListView(self.frame_2)
        self.targetSubstationListView.setObjectName(u"targetSubstationListView")

        self.verticalLayout.addWidget(self.targetSubstationListView)

        self.label_2 = QLabel(self.frame_2)
        self.label_2.setObjectName(u"label_2")

        self.verticalLayout.addWidget(self.label_2)

        self.candidateSubstationListView = QListView(self.frame_2)
        self.candidateSubstationListView.setObjectName(u"candidateSubstationListView")

        self.verticalLayout.addWidget(self.candidateSubstationListView)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.mainSplitter.addWidget(self.frame_2)
        self.plotFrame = QFrame(self.mainSplitter)
        self.plotFrame.setObjectName(u"plotFrame")
        self.plotFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.plotFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.plotFrame)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.plotwidget = MatplotlibWidget(self.plotFrame)
        self.plotwidget.setObjectName(u"plotwidget")

        self.verticalLayout_2.addWidget(self.plotwidget)

        self.mainSplitter.addWidget(self.plotFrame)

        self.verticalLayout_3.addWidget(self.mainSplitter)

        self.frame = QFrame(Dialog)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(1, 1, 1, 1)
        self.topClosestSpinBox = QSpinBox(self.frame)
        self.topClosestSpinBox.setObjectName(u"topClosestSpinBox")
        self.topClosestSpinBox.setMinimum(1)
        self.topClosestSpinBox.setMaximum(9999999)
        self.topClosestSpinBox.setValue(5)

        self.horizontalLayout.addWidget(self.topClosestSpinBox)

        self.computeCandidatesButton = QPushButton(self.frame)
        self.computeCandidatesButton.setObjectName(u"computeCandidatesButton")

        self.horizontalLayout.addWidget(self.computeCandidatesButton)

        self.computeButton = QPushButton(self.frame)
        self.computeButton.setObjectName(u"computeButton")

        self.horizontalLayout.addWidget(self.computeButton)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.acceptButton = QPushButton(self.frame)
        self.acceptButton.setObjectName(u"acceptButton")

        self.horizontalLayout.addWidget(self.acceptButton)


        self.verticalLayout_3.addWidget(self.frame)


        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Procedural Grid", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"Procedural grid method", None))
        self.label_3.setText(QCoreApplication.translate("Dialog", u"Substation to connect", None))
        self.label_2.setText(QCoreApplication.translate("Dialog", u"Connection substation candidates", None))
#if QT_CONFIG(tooltip)
        self.candidateSubstationListView.setToolTip(QCoreApplication.translate("Dialog", u"List of subations that can be connected to the selected substations", None))
#endif // QT_CONFIG(tooltip)
        self.topClosestSpinBox.setSuffix(QCoreApplication.translate("Dialog", u" Substations", None))
#if QT_CONFIG(tooltip)
        self.computeCandidatesButton.setToolTip(QCoreApplication.translate("Dialog", u"Compute the N closest candiate substations", None))
#endif // QT_CONFIG(tooltip)
        self.computeCandidatesButton.setText(QCoreApplication.translate("Dialog", u"Get candiates", None))
        self.computeButton.setText(QCoreApplication.translate("Dialog", u"Compute", None))
        self.acceptButton.setText(QCoreApplication.translate("Dialog", u"Accept", None))
    # retranslateUi

