# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dynamic_block_properties.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpacerItem, QTabWidget, QVBoxLayout,
    QWidget)
from VeraGrid.Gui.Icons import icons_rc

class Ui_DynamicBlockPropertiesDialog(object):
    def setupUi(self, DynamicBlockPropertiesDialog):
        if not DynamicBlockPropertiesDialog.objectName():
            DynamicBlockPropertiesDialog.setObjectName(u"DynamicBlockPropertiesDialog")
        DynamicBlockPropertiesDialog.resize(1200, 700)
        self.main_layout = QVBoxLayout(DynamicBlockPropertiesDialog)
        self.main_layout.setObjectName(u"main_layout")
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.tab_widget = QTabWidget(DynamicBlockPropertiesDialog)
        self.tab_widget.setObjectName(u"tab_widget")
        self.general_page = QWidget()
        self.general_page.setObjectName(u"general_page")
        self.general_page_layout = QVBoxLayout(self.general_page)
        self.general_page_layout.setObjectName(u"general_page_layout")
        self.measurement_configuration_group = QGroupBox(self.general_page)
        self.measurement_configuration_group.setObjectName(u"measurement_configuration_group")
        self.measurement_configuration_layout = QFormLayout(self.measurement_configuration_group)
        self.measurement_configuration_layout.setObjectName(u"measurement_configuration_layout")
        self.measurement_family_caption = QLabel(self.measurement_configuration_group)
        self.measurement_family_caption.setObjectName(u"measurement_family_caption")

        self.measurement_configuration_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.measurement_family_caption)

        self.measurement_family_value = QLabel(self.measurement_configuration_group)
        self.measurement_family_value.setObjectName(u"measurement_family_value")

        self.measurement_configuration_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.measurement_family_value)

        self.measurement_mode_caption = QLabel(self.measurement_configuration_group)
        self.measurement_mode_caption.setObjectName(u"measurement_mode_caption")

        self.measurement_configuration_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.measurement_mode_caption)

        self.measurement_mode_combo = QComboBox(self.measurement_configuration_group)
        self.measurement_mode_combo.setObjectName(u"measurement_mode_combo")

        self.measurement_configuration_layout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.measurement_mode_combo)

        self.measurement_target_caption = QLabel(self.measurement_configuration_group)
        self.measurement_target_caption.setObjectName(u"measurement_target_caption")

        self.measurement_configuration_layout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.measurement_target_caption)

        self.measurement_target_widget = QWidget(self.measurement_configuration_group)
        self.measurement_target_widget.setObjectName(u"measurement_target_widget")
        self.measurement_target_layout = QHBoxLayout(self.measurement_target_widget)
        self.measurement_target_layout.setObjectName(u"measurement_target_layout")
        self.measurement_target_layout.setContentsMargins(0, 0, 0, 0)
        self.measurement_target_value = QLineEdit(self.measurement_target_widget)
        self.measurement_target_value.setObjectName(u"measurement_target_value")
        self.measurement_target_value.setReadOnly(True)

        self.measurement_target_layout.addWidget(self.measurement_target_value)

        self.measurement_target_button = QPushButton(self.measurement_target_widget)
        self.measurement_target_button.setObjectName(u"measurement_target_button")

        self.measurement_target_layout.addWidget(self.measurement_target_button)

        self.measurement_target_release_button = QPushButton(self.measurement_target_widget)
        self.measurement_target_release_button.setObjectName(u"measurement_target_release_button")

        self.measurement_target_layout.addWidget(self.measurement_target_release_button)

        self.measurement_configuration_layout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.measurement_target_widget)

        self.measurement_terminal_caption = QLabel(self.measurement_configuration_group)
        self.measurement_terminal_caption.setObjectName(u"measurement_terminal_caption")

        self.measurement_configuration_layout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.measurement_terminal_caption)

        self.measurement_terminal_value = QLabel(self.measurement_configuration_group)
        self.measurement_terminal_value.setObjectName(u"measurement_terminal_value")

        self.measurement_configuration_layout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.measurement_terminal_value)

        self.general_page_layout.addWidget(self.measurement_configuration_group)

        self.tab_widget.addTab(self.general_page, "")

        self.main_layout.addWidget(self.tab_widget)

        self.status_label = QLabel(DynamicBlockPropertiesDialog)
        self.status_label.setObjectName(u"status_label")
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_label.setWordWrap(True)

        self.main_layout.addWidget(self.status_label)

        self.button_layout = QHBoxLayout()
        self.button_layout.setObjectName(u"button_layout")
        self.button_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.button_layout.addItem(self.button_spacer)

        self.apply_button = QPushButton(DynamicBlockPropertiesDialog)
        self.apply_button.setObjectName(u"apply_button")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/accept.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.apply_button.setIcon(icon)

        self.button_layout.addWidget(self.apply_button)


        self.main_layout.addLayout(self.button_layout)


        self.retranslateUi(DynamicBlockPropertiesDialog)

        self.tab_widget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(DynamicBlockPropertiesDialog)
    # setupUi

    def retranslateUi(self, DynamicBlockPropertiesDialog):
        DynamicBlockPropertiesDialog.setWindowTitle(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Block properties", None))
        self.measurement_configuration_group.setTitle(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Measurement configuration", None))
        self.measurement_family_caption.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Model family", None))
        self.measurement_family_value.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Balanced RMS physical measurement", None))
        self.measurement_mode_caption.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Measurement mode", None))
        self.measurement_target_caption.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Physical element / bus", None))
        self.measurement_target_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Choose...", None))
        self.measurement_target_release_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Release", None))
        self.measurement_terminal_caption.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Measured terminal", None))
        self.measurement_terminal_value.setText("")
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.general_page), QCoreApplication.translate("DynamicBlockPropertiesDialog", u"General options", None))
        self.status_label.setText("")
        self.apply_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Apply changes", None))
    # retranslateUi
