# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'measurements_dialog_ui.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QDialog,
    QDialogButtonBox, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QListWidgetItem, QSizePolicy, QSpacerItem,
    QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget)

from VeraGrid.Gui.DynamicModelEditor.Editor.ElementDialogues.MeasurementsDialog.measurement_widgets import (DeviceSelectionLabel, MeasurementReferenceList)

class Ui_MeasurementsDialog(object):
    def setupUi(self, MeasurementsDialog):
        if not MeasurementsDialog.objectName():
            MeasurementsDialog.setObjectName(u"MeasurementsDialog")
        MeasurementsDialog.resize(789, 514)
        self.verticalLayout_4 = QVBoxLayout(MeasurementsDialog)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.frame = QFrame(MeasurementsDialog)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(-1, 0, 0, 0)
        self.busTitleLabel = QLabel(self.frame)
        self.busTitleLabel.setObjectName(u"busTitleLabel")

        self.horizontalLayout.addWidget(self.busTitleLabel)

        self.bus_label = DeviceSelectionLabel(self.frame)
        self.bus_label.setObjectName(u"bus_label")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.bus_label.sizePolicy().hasHeightForWidth())
        self.bus_label.setSizePolicy(sizePolicy)
        self.bus_label.setMinimumSize(QSize(140, 26))
        self.bus_label.setMaximumSize(QSize(260, 16777215))
        self.bus_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.bus_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.bus_label.setFrameShape(QFrame.Shape.Panel)
        self.bus_label.setFrameShadow(QFrame.Shadow.Sunken)
        self.bus_label.setMargin(5)

        self.horizontalLayout.addWidget(self.bus_label)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)


        self.verticalLayout_4.addWidget(self.frame)

        self.explanation_label = QLabel(MeasurementsDialog)
        self.explanation_label.setObjectName(u"explanation_label")
        self.explanation_label.setWordWrap(True)

        self.verticalLayout_4.addWidget(self.explanation_label)

        self.splitter = QSplitter(MeasurementsDialog)
        self.splitter.setObjectName(u"splitter")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.splitter.sizePolicy().hasHeightForWidth())
        self.splitter.setSizePolicy(sizePolicy1)
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.frame_2 = QFrame(self.splitter)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout = QVBoxLayout(self.frame_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, -1, -1, -1)
        self.measurement_tree = QTreeWidget(self.frame_2)
        self.measurement_tree.setObjectName(u"measurement_tree")
        self.measurement_tree.setAlternatingRowColors(True)
        self.measurement_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.measurement_tree.setRootIsDecorated(True)

        self.verticalLayout.addWidget(self.measurement_tree)

        self.splitter.addWidget(self.frame_2)
        self.frame_3 = QFrame(self.splitter)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_3.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.frame_3)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.label = QLabel(self.frame_3)
        self.label.setObjectName(u"label")

        self.verticalLayout_2.addWidget(self.label)

        self.input_list = MeasurementReferenceList(self.frame_3)
        self.input_list.setObjectName(u"input_list")

        self.verticalLayout_2.addWidget(self.input_list)

        self.splitter.addWidget(self.frame_3)
        self.frame_4 = QFrame(self.splitter)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.frame_4)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(-1, -1, 0, -1)
        self.label_2 = QLabel(self.frame_4)
        self.label_2.setObjectName(u"label_2")

        self.verticalLayout_3.addWidget(self.label_2)

        self.output_list = MeasurementReferenceList(self.frame_4)
        self.output_list.setObjectName(u"output_list")

        self.verticalLayout_3.addWidget(self.output_list)

        self.splitter.addWidget(self.frame_4)

        self.verticalLayout_4.addWidget(self.splitter)

        self.button_box = QDialogButtonBox(MeasurementsDialog)
        self.button_box.setObjectName(u"button_box")
        self.button_box.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout_4.addWidget(self.button_box)


        self.retranslateUi(MeasurementsDialog)

        QMetaObject.connectSlotsByName(MeasurementsDialog)
    # setupUi

    def retranslateUi(self, MeasurementsDialog):
        MeasurementsDialog.setWindowTitle(QCoreApplication.translate("MeasurementsDialog", u"Configure measurement block", None))
        self.busTitleLabel.setText(QCoreApplication.translate("MeasurementsDialog", u"Bus", None))
#if QT_CONFIG(tooltip)
        self.bus_label.setToolTip(QCoreApplication.translate("MeasurementsDialog", u"Click to select a bus", None))
#endif // QT_CONFIG(tooltip)
        self.bus_label.setText(QCoreApplication.translate("MeasurementsDialog", u"Select bus...", None))
        self.explanation_label.setText(QCoreApplication.translate("MeasurementsDialog", u"Check one measurement type, choose its variables, and drag variables between Outputs and Inputs.", None))
        ___qtreewidgetitem = self.measurement_tree.headerItem()
        ___qtreewidgetitem.setText(0, QCoreApplication.translate("MeasurementsDialog", u"Measurement variables", None))
        self.label.setText(QCoreApplication.translate("MeasurementsDialog", u"Inputs", None))
        self.label_2.setText(QCoreApplication.translate("MeasurementsDialog", u"Outputs", None))
    # retranslateUi

