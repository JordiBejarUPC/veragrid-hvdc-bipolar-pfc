# -*- coding: utf-8 -*-

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from PySide6.QtCore import QMetaObject, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)


class Ui_TemplateDeviceEditorDialog(object):
    def setupUi(self, TemplateDeviceEditorDialog):
        if not TemplateDeviceEditorDialog.objectName():
            TemplateDeviceEditorDialog.setObjectName("TemplateDeviceEditorDialog")
        TemplateDeviceEditorDialog.resize(1180, 780)
        TemplateDeviceEditorDialog.setWindowTitle("Device editor")

        self.main_layout = QVBoxLayout(TemplateDeviceEditorDialog)
        self.main_layout.setObjectName("main_layout")

        self.tab_widget = QTabWidget(TemplateDeviceEditorDialog)
        self.tab_widget.setObjectName("tab_widget")
        self.main_layout.addWidget(self.tab_widget)

        # Properties tab
        self.properties_tab = QWidget()
        self.properties_tab.setObjectName("properties_tab")
        self.properties_layout = QVBoxLayout(self.properties_tab)
        self.properties_layout.setObjectName("properties_layout")

        self.time_controls_frame = QFrame(self.properties_tab)
        self.time_controls_frame.setObjectName("time_controls_frame")
        self.time_controls_layout = QHBoxLayout(self.time_controls_frame)
        self.time_controls_layout.setObjectName("time_controls_layout")

        self.time_step_title_label = QLabel(self.time_controls_frame)
        self.time_step_title_label.setObjectName("time_step_title_label")
        self.time_step_title_label.setText("Time step")
        self.time_controls_layout.addWidget(self.time_step_title_label)

        self.time_step_slider = QSlider(self.time_controls_frame)
        self.time_step_slider.setObjectName("time_step_slider")
        self.time_step_slider.setOrientation(Qt.Orientation.Horizontal)
        self.time_controls_layout.addWidget(self.time_step_slider)

        self.time_step_label = QLabel(self.time_controls_frame)
        self.time_step_label.setObjectName("time_step_label")
        self.time_step_label.setMinimumWidth(260)
        self.time_step_label.setText("Snapshot")
        self.time_controls_layout.addWidget(self.time_step_label)

        self.properties_layout.addWidget(self.time_controls_frame)

        self.properties_table_view = QTableView(self.properties_tab)
        self.properties_table_view.setObjectName("properties_table_view")
        self.properties_layout.addWidget(self.properties_table_view)

        self.tab_widget.addTab(self.properties_tab, "Properties")

        # Profiles tab
        self.profiles_tab = QWidget()
        self.profiles_tab.setObjectName("profiles_tab")
        self.profiles_layout = QVBoxLayout(self.profiles_tab)
        self.profiles_layout.setObjectName("profiles_layout")

        self.profiles_tools_frame = QFrame(self.profiles_tab)
        self.profiles_tools_frame.setObjectName("profiles_tools_frame")
        self.profiles_tools_layout = QHBoxLayout(self.profiles_tools_frame)
        self.profiles_tools_layout.setObjectName("profiles_tools_layout")

        self.profiles_copy_button = QPushButton(self.profiles_tools_frame)
        self.profiles_copy_button.setObjectName("profiles_copy_button")
        self.profiles_copy_button.setText("")
        self.profiles_tools_layout.addWidget(self.profiles_copy_button)

        self.profiles_paste_button = QPushButton(self.profiles_tools_frame)
        self.profiles_paste_button.setObjectName("profiles_paste_button")
        self.profiles_paste_button.setText("")
        self.profiles_tools_layout.addWidget(self.profiles_paste_button)

        self.profiles_plot_selected_button = QPushButton(self.profiles_tools_frame)
        self.profiles_plot_selected_button.setObjectName("profiles_plot_selected_button")
        self.profiles_plot_selected_button.setText("")
        self.profiles_tools_layout.addWidget(self.profiles_plot_selected_button)

        self.profiles_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.profiles_tools_layout.addItem(self.profiles_spacer)
        self.profiles_layout.addWidget(self.profiles_tools_frame)

        self.profiles_table_view = QTableView(self.profiles_tab)
        self.profiles_table_view.setObjectName("profiles_table_view")
        self.profiles_layout.addWidget(self.profiles_table_view)

        self.tab_widget.addTab(self.profiles_tab, "Profiles")

        # Associations tab
        self.associations_tab = QWidget()
        self.associations_tab.setObjectName("associations_tab")
        self.associations_layout = QVBoxLayout(self.associations_tab)
        self.associations_layout.setObjectName("associations_layout")

        self.associations_controls_frame = QFrame(self.associations_tab)
        self.associations_controls_frame.setObjectName("associations_controls_frame")
        self.associations_controls_layout = QHBoxLayout(self.associations_controls_frame)
        self.associations_controls_layout.setObjectName("associations_controls_layout")

        self.associations_property_label = QLabel(self.associations_controls_frame)
        self.associations_property_label.setObjectName("associations_property_label")
        self.associations_property_label.setText("Association")
        self.associations_controls_layout.addWidget(self.associations_property_label)

        self.associations_combo_box = QComboBox(self.associations_controls_frame)
        self.associations_combo_box.setObjectName("associations_combo_box")
        self.associations_combo_box.setMinimumWidth(220)
        self.associations_controls_layout.addWidget(self.associations_combo_box)

        self.associations_units_title_label = QLabel(self.associations_controls_frame)
        self.associations_units_title_label.setObjectName("associations_units_title_label")
        self.associations_units_title_label.setText("Units")
        self.associations_controls_layout.addWidget(self.associations_units_title_label)

        self.associations_units_value_label = QLabel(self.associations_controls_frame)
        self.associations_units_value_label.setObjectName("associations_units_value_label")
        self.associations_units_value_label.setMinimumWidth(120)
        self.associations_units_value_label.setText("")
        self.associations_controls_layout.addWidget(self.associations_units_value_label)

        self.associations_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.associations_controls_layout.addItem(self.associations_spacer)
        self.associations_layout.addWidget(self.associations_controls_frame)

        self.associations_table_view = QTableView(self.associations_tab)
        self.associations_table_view.setObjectName("associations_table_view")
        self.associations_layout.addWidget(self.associations_table_view)

        self.tab_widget.addTab(self.associations_tab, "Associations")

        self.button_box = QDialogButtonBox(TemplateDeviceEditorDialog)
        self.button_box.setObjectName("button_box")
        self.button_box.setStandardButtons(QDialogButtonBox.StandardButton.Close)
        self.main_layout.addWidget(self.button_box)

        QMetaObject.connectSlotsByName(TemplateDeviceEditorDialog)
