# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dynamic_block_properties.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QDialog, QDoubleSpinBox, QFormLayout, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLayout, QLineEdit, QPlainTextEdit, QPushButton,
    QSizePolicy, QSpacerItem, QSplitter, QTabWidget,
    QTableView, QToolButton, QTreeView, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget)
from VeraGrid.Gui.Icons.icons_rc import *

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
        self.general_layout = QVBoxLayout(self.general_page)
        self.general_layout.setObjectName(u"general_layout")
        self.general_layout.setContentsMargins(6, 6, 6, 6)
        self.general_header_layout = QHBoxLayout()
        self.general_header_layout.setObjectName(u"general_header_layout")
        self.general_header_layout.setContentsMargins(0, 0, 0, 0)
        self.identity_group = QGroupBox(self.general_page)
        self.identity_group.setObjectName(u"identity_group")
        self.identity_layout = QFormLayout(self.identity_group)
        self.identity_layout.setObjectName(u"identity_layout")
        self.block_type_label = QLabel(self.identity_group)
        self.block_type_label.setObjectName(u"block_type_label")

        self.identity_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.block_type_label)

        self.block_type_value_label = QLabel(self.identity_group)
        self.block_type_value_label.setObjectName(u"block_type_value_label")
        self.block_type_value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.identity_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.block_type_value_label)

        self.documentation_label = QLabel(self.identity_group)
        self.documentation_label.setObjectName(u"documentation_label")

        self.identity_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.documentation_label)

        self.documentation_button_layout = QHBoxLayout()
        self.documentation_button_layout.setObjectName(u"documentation_button_layout")
        self.documentation_button_layout.setContentsMargins(0, 0, 0, 0)
        self.block_info_button = QPushButton(self.identity_group)
        self.block_info_button.setObjectName(u"block_info_button")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/message.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.block_info_button.setIcon(icon)

        self.documentation_button_layout.addWidget(self.block_info_button)

        self.documentation_button_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.documentation_button_layout.addItem(self.documentation_button_spacer)


        self.identity_layout.setLayout(1, QFormLayout.ItemRole.FieldRole, self.documentation_button_layout)


        self.general_header_layout.addWidget(self.identity_group)


        self.general_layout.addLayout(self.general_header_layout)

        self.dae_splitter = QSplitter(self.general_page)
        self.dae_splitter.setObjectName(u"dae_splitter")
        self.dae_splitter.setOrientation(Qt.Orientation.Horizontal)
        self.dae_splitter.setHandleWidth(6)
        self.property_tools_panel = QWidget(self.dae_splitter)
        self.property_tools_panel.setObjectName(u"property_tools_panel")
        self.property_tools_layout = QVBoxLayout(self.property_tools_panel)
        self.property_tools_layout.setSpacing(6)
        self.property_tools_layout.setObjectName(u"property_tools_layout")
        self.property_tools_layout.setContentsMargins(0, 0, 0, 0)
        self.property_tools_splitter = QSplitter(self.property_tools_panel)
        self.property_tools_splitter.setObjectName(u"property_tools_splitter")
        self.property_tools_splitter.setOrientation(Qt.Orientation.Vertical)
        self.property_tools_splitter.setHandleWidth(6)
        self.property_tools_splitter.setChildrenCollapsible(False)
        self.property_tree_panel = QWidget(self.property_tools_splitter)
        self.property_tree_panel.setObjectName(u"property_tree_panel")
        self.property_tree_panel.setMinimumSize(QSize(260, 0))
        self.property_tree_layout = QVBoxLayout(self.property_tree_panel)
        self.property_tree_layout.setObjectName(u"property_tree_layout")
        self.property_tree_layout.setContentsMargins(0, 0, 0, 0)
        self.property_search = QLineEdit(self.property_tree_panel)
        self.property_search.setObjectName(u"property_search")
        self.property_search.setClearButtonEnabled(True)

        self.property_tree_layout.addWidget(self.property_search)

        self.property_tree = QTreeView(self.property_tree_panel)
        self.property_tree.setObjectName(u"property_tree")
        self.property_tree.setAlternatingRowColors(True)
        self.property_tree.setRootIsDecorated(True)
        self.property_tree.setUniformRowHeights(True)
        self.property_tree.setItemsExpandable(True)
        self.property_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.property_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.property_tree.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked|QAbstractItemView.EditTrigger.EditKeyPressed)
        self.property_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.property_tree_layout.addWidget(self.property_tree)

        self.property_tools_splitter.addWidget(self.property_tree_panel)
        self.add_symbol_group = QGroupBox(self.property_tools_splitter)
        self.add_symbol_group.setObjectName(u"add_symbol_group")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.add_symbol_group.sizePolicy().hasHeightForWidth())
        self.add_symbol_group.setSizePolicy(sizePolicy)
        self.add_symbol_layout = QGridLayout(self.add_symbol_group)
        self.add_symbol_layout.setObjectName(u"add_symbol_layout")
        self.add_symbol_layout.setHorizontalSpacing(6)
        self.add_symbol_layout.setVerticalSpacing(3)
        self.add_symbol_layout.setContentsMargins(6, 4, 6, 4)
        self.new_symbol_owner_label = QLabel(self.add_symbol_group)
        self.new_symbol_owner_label.setObjectName(u"new_symbol_owner_label")

        self.add_symbol_layout.addWidget(self.new_symbol_owner_label, 0, 0, 1, 1)

        self.new_symbol_owner = QComboBox(self.add_symbol_group)
        self.new_symbol_owner.setObjectName(u"new_symbol_owner")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.new_symbol_owner.sizePolicy().hasHeightForWidth())
        self.new_symbol_owner.setSizePolicy(sizePolicy1)

        self.add_symbol_layout.addWidget(self.new_symbol_owner, 1, 0, 1, 1)

        self.new_symbol_name_label = QLabel(self.add_symbol_group)
        self.new_symbol_name_label.setObjectName(u"new_symbol_name_label")

        self.add_symbol_layout.addWidget(self.new_symbol_name_label, 2, 0, 1, 1)

        self.new_symbol_name = QLineEdit(self.add_symbol_group)
        self.new_symbol_name.setObjectName(u"new_symbol_name")
        sizePolicy1.setHeightForWidth(self.new_symbol_name.sizePolicy().hasHeightForWidth())
        self.new_symbol_name.setSizePolicy(sizePolicy1)

        self.add_symbol_layout.addWidget(self.new_symbol_name, 3, 0, 1, 1)

        self.new_symbol_category_label = QLabel(self.add_symbol_group)
        self.new_symbol_category_label.setObjectName(u"new_symbol_category_label")

        self.add_symbol_layout.addWidget(self.new_symbol_category_label, 4, 0, 1, 1)

        self.new_symbol_category = QComboBox(self.add_symbol_group)
        self.new_symbol_category.setObjectName(u"new_symbol_category")
        sizePolicy1.setHeightForWidth(self.new_symbol_category.sizePolicy().hasHeightForWidth())
        self.new_symbol_category.setSizePolicy(sizePolicy1)

        self.add_symbol_layout.addWidget(self.new_symbol_category, 5, 0, 1, 1)

        self.new_symbol_kind_label = QLabel(self.add_symbol_group)
        self.new_symbol_kind_label.setObjectName(u"new_symbol_kind_label")

        self.add_symbol_layout.addWidget(self.new_symbol_kind_label, 6, 0, 1, 1)

        self.new_symbol_kind = QComboBox(self.add_symbol_group)
        self.new_symbol_kind.setObjectName(u"new_symbol_kind")
        sizePolicy1.setHeightForWidth(self.new_symbol_kind.sizePolicy().hasHeightForWidth())
        self.new_symbol_kind.setSizePolicy(sizePolicy1)

        self.add_symbol_layout.addWidget(self.new_symbol_kind, 7, 0, 1, 1)

        self.new_variable_options = QWidget(self.add_symbol_group)
        self.new_variable_options.setObjectName(u"new_variable_options")
        sizePolicy1.setHeightForWidth(self.new_variable_options.sizePolicy().hasHeightForWidth())
        self.new_variable_options.setSizePolicy(sizePolicy1)
        self.new_variable_options_layout = QHBoxLayout(self.new_variable_options)
        self.new_variable_options_layout.setObjectName(u"new_variable_options_layout")
        self.new_variable_options_layout.setContentsMargins(0, 0, 0, 0)
        self.new_symbol_exported = QCheckBox(self.new_variable_options)
        self.new_symbol_exported.setObjectName(u"new_symbol_exported")

        self.new_variable_options_layout.addWidget(self.new_symbol_exported)

        self.new_state_derivative = QCheckBox(self.new_variable_options)
        self.new_state_derivative.setObjectName(u"new_state_derivative")

        self.new_variable_options_layout.addWidget(self.new_state_derivative)

        self.new_variable_options_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.new_variable_options_layout.addItem(self.new_variable_options_spacer)


        self.add_symbol_layout.addWidget(self.new_variable_options, 8, 0, 1, 1)

        self.new_parameter_value_label = QLabel(self.add_symbol_group)
        self.new_parameter_value_label.setObjectName(u"new_parameter_value_label")

        self.add_symbol_layout.addWidget(self.new_parameter_value_label, 8, 0, 1, 1)

        self.new_parameter_value = QDoubleSpinBox(self.add_symbol_group)
        self.new_parameter_value.setObjectName(u"new_parameter_value")
        sizePolicy1.setHeightForWidth(self.new_parameter_value.sizePolicy().hasHeightForWidth())
        self.new_parameter_value.setSizePolicy(sizePolicy1)
        self.new_parameter_value.setDecimals(12)
        self.new_parameter_value.setMinimum(-10000000000000000159028911097599180468360808563945281389781327557747838772170381060813469985856815104.000000000000000)
        self.new_parameter_value.setMaximum(10000000000000000159028911097599180468360808563945281389781327557747838772170381060813469985856815104.000000000000000)

        self.add_symbol_layout.addWidget(self.new_parameter_value, 9, 0, 1, 1)

        self.new_static_reference_label = QLabel(self.add_symbol_group)
        self.new_static_reference_label.setObjectName(u"new_static_reference_label")

        self.add_symbol_layout.addWidget(self.new_static_reference_label, 8, 0, 1, 1)

        self.new_static_reference = QComboBox(self.add_symbol_group)
        self.new_static_reference.setObjectName(u"new_static_reference")
        sizePolicy1.setHeightForWidth(self.new_static_reference.sizePolicy().hasHeightForWidth())
        self.new_static_reference.setSizePolicy(sizePolicy1)
        self.new_static_reference.setEditable(True)

        self.add_symbol_layout.addWidget(self.new_static_reference, 9, 0, 1, 1)

        self.new_external_reference_label = QLabel(self.add_symbol_group)
        self.new_external_reference_label.setObjectName(u"new_external_reference_label")

        self.add_symbol_layout.addWidget(self.new_external_reference_label, 10, 0, 1, 1)

        self.new_external_reference = QComboBox(self.add_symbol_group)
        self.new_external_reference.setObjectName(u"new_external_reference")
        sizePolicy1.setHeightForWidth(self.new_external_reference.sizePolicy().hasHeightForWidth())
        self.new_external_reference.setSizePolicy(sizePolicy1)
        self.new_external_reference.setEditable(True)

        self.add_symbol_layout.addWidget(self.new_external_reference, 11, 0, 1, 1)

        self.add_symbol_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.add_symbol_layout.addItem(self.add_symbol_spacer, 12, 0, 1, 1)

        self.add_symbol_button = QPushButton(self.add_symbol_group)
        self.add_symbol_button.setObjectName(u"add_symbol_button")

        self.add_symbol_layout.addWidget(self.add_symbol_button, 13, 0, 1, 1)

        self.property_tools_splitter.addWidget(self.add_symbol_group)

        self.property_tools_layout.addWidget(self.property_tools_splitter)

        self.dae_splitter.addWidget(self.property_tools_panel)
        self.equation_tools_panel = QWidget(self.dae_splitter)
        self.equation_tools_panel.setObjectName(u"equation_tools_panel")
        self.equation_tools_layout = QVBoxLayout(self.equation_tools_panel)
        self.equation_tools_layout.setSpacing(6)
        self.equation_tools_layout.setObjectName(u"equation_tools_layout")
        self.equation_tools_layout.setContentsMargins(0, 0, 0, 0)
        self.equation_panel = QTabWidget(self.equation_tools_panel)
        self.equation_panel.setObjectName(u"equation_panel")
        self.python_code_page = QWidget()
        self.python_code_page.setObjectName(u"python_code_page")
        self.python_code_layout = QVBoxLayout(self.python_code_page)
        self.python_code_layout.setObjectName(u"python_code_layout")
        self.owner_layout = QHBoxLayout()
        self.owner_layout.setObjectName(u"owner_layout")
        self.equation_owner_label = QLabel(self.python_code_page)
        self.equation_owner_label.setObjectName(u"equation_owner_label")

        self.owner_layout.addWidget(self.equation_owner_label)

        self.equation_owner_combo = QComboBox(self.python_code_page)
        self.equation_owner_combo.setObjectName(u"equation_owner_combo")

        self.owner_layout.addWidget(self.equation_owner_combo)


        self.python_code_layout.addLayout(self.owner_layout)

        self.code_search_layout = QHBoxLayout()
        self.code_search_layout.setObjectName(u"code_search_layout")
        self.dae_code_search = QLineEdit(self.python_code_page)
        self.dae_code_search.setObjectName(u"dae_code_search")
        self.dae_code_search.setClearButtonEnabled(True)

        self.code_search_layout.addWidget(self.dae_code_search)

        self.dae_search_status = QLabel(self.python_code_page)
        self.dae_search_status.setObjectName(u"dae_search_status")

        self.code_search_layout.addWidget(self.dae_search_status)

        self.dae_search_previous_button = QToolButton(self.python_code_page)
        self.dae_search_previous_button.setObjectName(u"dae_search_previous_button")
        self.dae_search_previous_button.setEnabled(False)

        self.code_search_layout.addWidget(self.dae_search_previous_button)

        self.dae_search_next_button = QToolButton(self.python_code_page)
        self.dae_search_next_button.setObjectName(u"dae_search_next_button")
        self.dae_search_next_button.setEnabled(False)

        self.code_search_layout.addWidget(self.dae_search_next_button)

        self.procedural_add_button = QPushButton(self.python_code_page)
        self.procedural_add_button.setObjectName(u"procedural_add_button")

        self.code_search_layout.addWidget(self.procedural_add_button)


        self.python_code_layout.addLayout(self.code_search_layout)

        self.dae_editor_container = QWidget(self.python_code_page)
        self.dae_editor_container.setObjectName(u"dae_editor_container")
        self.dae_editor_layout = QVBoxLayout(self.dae_editor_container)
        self.dae_editor_layout.setObjectName(u"dae_editor_layout")
        self.dae_editor_layout.setContentsMargins(0, 0, 0, 0)

        self.python_code_layout.addWidget(self.dae_editor_container)

        self.equation_panel.addTab(self.python_code_page, "")
        self.latex_page = QWidget()
        self.latex_page.setObjectName(u"latex_page")
        self.latex_layout = QVBoxLayout(self.latex_page)
        self.latex_layout.setObjectName(u"latex_layout")
        self.latex_splitter = QSplitter(self.latex_page)
        self.latex_splitter.setObjectName(u"latex_splitter")
        self.latex_splitter.setOrientation(Qt.Orientation.Vertical)
        self.latex_splitter.setHandleWidth(6)
        self.latex_splitter.setChildrenCollapsible(False)
        self.latex_selection_panel = QWidget(self.latex_splitter)
        self.latex_selection_panel.setObjectName(u"latex_selection_panel")
        self.latex_selection_layout = QVBoxLayout(self.latex_selection_panel)
        self.latex_selection_layout.setObjectName(u"latex_selection_layout")
        self.latex_selection_layout.setContentsMargins(0, 0, 0, 0)
        self.latex_explanation_label = QLabel(self.latex_selection_panel)
        self.latex_explanation_label.setObjectName(u"latex_explanation_label")
        self.latex_explanation_label.setWordWrap(True)

        self.latex_selection_layout.addWidget(self.latex_explanation_label)

        self.latex_selection_tree = QTreeWidget(self.latex_selection_panel)
        self.latex_selection_tree.setObjectName(u"latex_selection_tree")
        self.latex_selection_tree.setAlternatingRowColors(True)

        self.latex_selection_layout.addWidget(self.latex_selection_tree)

        self.selection_button_layout = QHBoxLayout()
        self.selection_button_layout.setObjectName(u"selection_button_layout")
        self.latex_select_all_button = QPushButton(self.latex_selection_panel)
        self.latex_select_all_button.setObjectName(u"latex_select_all_button")

        self.selection_button_layout.addWidget(self.latex_select_all_button)

        self.latex_clear_button = QPushButton(self.latex_selection_panel)
        self.latex_clear_button.setObjectName(u"latex_clear_button")

        self.selection_button_layout.addWidget(self.latex_clear_button)

        self.selection_button_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.selection_button_layout.addItem(self.selection_button_spacer)


        self.latex_selection_layout.addLayout(self.selection_button_layout)

        self.latex_splitter.addWidget(self.latex_selection_panel)
        self.latex_source_panel = QWidget(self.latex_splitter)
        self.latex_source_panel.setObjectName(u"latex_source_panel")
        self.latex_source_layout = QVBoxLayout(self.latex_source_panel)
        self.latex_source_layout.setObjectName(u"latex_source_layout")
        self.latex_source_layout.setContentsMargins(0, 0, 0, 0)
        self.latex_source_label = QLabel(self.latex_source_panel)
        self.latex_source_label.setObjectName(u"latex_source_label")

        self.latex_source_layout.addWidget(self.latex_source_label)

        self.latex_source_preview = QPlainTextEdit(self.latex_source_panel)
        self.latex_source_preview.setObjectName(u"latex_source_preview")
        self.latex_source_preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.latex_source_preview.setReadOnly(True)

        self.latex_source_layout.addWidget(self.latex_source_preview)

        self.export_layout = QHBoxLayout()
        self.export_layout.setObjectName(u"export_layout")
        self.export_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.export_layout.addItem(self.export_spacer)

        self.export_rendered_button = QPushButton(self.latex_source_panel)
        self.export_rendered_button.setObjectName(u"export_rendered_button")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/download.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.export_rendered_button.setIcon(icon1)

        self.export_layout.addWidget(self.export_rendered_button)


        self.latex_source_layout.addLayout(self.export_layout)

        self.latex_splitter.addWidget(self.latex_source_panel)

        self.latex_layout.addWidget(self.latex_splitter)

        self.equation_panel.addTab(self.latex_page, "")

        self.equation_tools_layout.addWidget(self.equation_panel)

        self.validation_panel = QWidget(self.equation_tools_panel)
        self.validation_panel.setObjectName(u"validation_panel")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.validation_panel.sizePolicy().hasHeightForWidth())
        self.validation_panel.setSizePolicy(sizePolicy2)
        self.validation_layout = QHBoxLayout(self.validation_panel)
        self.validation_layout.setObjectName(u"validation_layout")
        self.validation_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.validation_layout.setContentsMargins(0, 0, 0, 0)
        self.dae_validation_status_label = QLabel(self.validation_panel)
        self.dae_validation_status_label.setObjectName(u"dae_validation_status_label")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.dae_validation_status_label.sizePolicy().hasHeightForWidth())
        self.dae_validation_status_label.setSizePolicy(sizePolicy3)
        self.dae_validation_status_label.setWordWrap(False)
        self.dae_validation_status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.validation_layout.addWidget(self.dae_validation_status_label, 0, Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.validate_code_button = QPushButton(self.validation_panel)
        self.validate_code_button.setObjectName(u"validate_code_button")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/accept.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.validate_code_button.setIcon(icon2)

        self.validation_layout.addWidget(self.validate_code_button, 0, Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)


        self.equation_tools_layout.addWidget(self.validation_panel)

        self.dae_splitter.addWidget(self.equation_tools_panel)

        self.general_layout.addWidget(self.dae_splitter)

        self.status_label = QLabel(self.general_page)
        self.status_label.setObjectName(u"status_label")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.general_layout.addWidget(self.status_label)

        self.tab_widget.addTab(self.general_page, "")
        self.special_settings_page = QWidget()
        self.special_settings_page.setObjectName(u"special_settings_page")
        self.special_settings_layout = QVBoxLayout(self.special_settings_page)
        self.special_settings_layout.setObjectName(u"special_settings_layout")
        self.special_settings_description = QLabel(self.special_settings_page)
        self.special_settings_description.setObjectName(u"special_settings_description")
        self.special_settings_description.setWordWrap(True)

        self.special_settings_layout.addWidget(self.special_settings_description)

        self.special_settings_table = QTableView(self.special_settings_page)
        self.special_settings_table.setObjectName(u"special_settings_table")
        self.special_settings_table.setAlternatingRowColors(True)

        self.special_settings_layout.addWidget(self.special_settings_table)

        self.tab_widget.addTab(self.special_settings_page, "")

        self.main_layout.addWidget(self.tab_widget)

        self.button_layout = QHBoxLayout()
        self.button_layout.setObjectName(u"button_layout")
        self.button_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.button_layout.addItem(self.button_spacer)

        self.apply_button = QPushButton(DynamicBlockPropertiesDialog)
        self.apply_button.setObjectName(u"apply_button")
        self.apply_button.setIcon(icon2)

        self.button_layout.addWidget(self.apply_button)


        self.main_layout.addLayout(self.button_layout)


        self.retranslateUi(DynamicBlockPropertiesDialog)

        self.tab_widget.setCurrentIndex(0)
        self.equation_panel.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(DynamicBlockPropertiesDialog)
    # setupUi

    def retranslateUi(self, DynamicBlockPropertiesDialog):
        DynamicBlockPropertiesDialog.setWindowTitle(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Block properties", None))
        self.identity_group.setTitle(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Block configuration", None))
        self.block_type_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Type", None))
        self.block_type_value_label.setText("")
        self.documentation_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Documentation", None))
        self.block_info_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Block info", None))
        self.property_search.setPlaceholderText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Search properties...", None))
        self.add_symbol_group.setTitle(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Add symbol to selected block", None))
        self.new_symbol_owner_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Owner block", None))
        self.new_symbol_name_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"New symbol name", None))
        self.new_symbol_name.setPlaceholderText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Enter a name", None))
        self.new_symbol_category_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Symbol category", None))
        self.new_symbol_kind_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Type", None))
        self.new_symbol_exported.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Output", None))
        self.new_state_derivative.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Create derivative variable", None))
        self.new_parameter_value_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Initial numeric value", None))
        self.new_static_reference_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Static device mapping", None))
#if QT_CONFIG(tooltip)
        self.new_external_reference_label.setToolTip(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Power-flow variable used to initialize this dynamic variable.", None))
#endif // QT_CONFIG(tooltip)
        self.new_external_reference_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Power-flow variable", None))
        self.add_symbol_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Add symbol", None))
        self.equation_owner_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Equation owner", None))
        self.dae_code_search.setPlaceholderText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Search Python code...", None))
        self.dae_search_status.setText("")
        self.dae_search_previous_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Previous", None))
        self.dae_search_next_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Next", None))
#if QT_CONFIG(tooltip)
        self.procedural_add_button.setToolTip(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Add one procedural behavior to the active equation owner's Python code.", None))
#endif // QT_CONFIG(tooltip)
        self.procedural_add_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"+ Add procedural logic", None))
        self.equation_panel.setTabText(self.equation_panel.indexOf(self.python_code_page), QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Python code", None))
        self.latex_explanation_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Select the equation groups to include. Each internal block and each DAE section can be selected independently.", None))
        ___qtreewidgetitem = self.latex_selection_tree.headerItem()
        ___qtreewidgetitem.setText(1, QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Equations", None))
        ___qtreewidgetitem.setText(0, QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Block / equation group", None))
        self.latex_select_all_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Select all", None))
        self.latex_clear_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Clear", None))
        self.latex_source_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"LaTeX source", None))
        self.latex_source_preview.setPlaceholderText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Select equation groups to generate copyable LaTeX source.", None))
        self.export_rendered_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Download rendered PDF", None))
        self.equation_panel.setTabText(self.equation_panel.indexOf(self.latex_page), QCoreApplication.translate("DynamicBlockPropertiesDialog", u"LaTeX", None))
        self.dae_validation_status_label.setText("")
        self.validate_code_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Validate model", None))
        self.status_label.setText("")
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.general_page), QCoreApplication.translate("DynamicBlockPropertiesDialog", u"General options", None))
        self.special_settings_description.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"These settings contain structured data used to regenerate the block. Edit sequences with valid Python tuple/list syntax.", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.special_settings_page), QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Special configuration", None))
        self.apply_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Apply changes", None))
    # retranslateUi

