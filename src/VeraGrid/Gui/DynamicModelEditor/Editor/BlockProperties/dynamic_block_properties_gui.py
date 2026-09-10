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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog,
    QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QSizePolicy,
    QSpacerItem, QSplitter, QTabWidget, QTableView,
    QToolButton, QTreeView, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget)
from VeraGrid.Gui.Icons.icons_rc import *

class Ui_DynamicBlockPropertiesDialog(object):
    def setupUi(self, DynamicBlockPropertiesDialog):
        if not DynamicBlockPropertiesDialog.objectName():
            DynamicBlockPropertiesDialog.setObjectName(u"DynamicBlockPropertiesDialog")
        DynamicBlockPropertiesDialog.resize(847, 682)
        self.main_layout = QVBoxLayout(DynamicBlockPropertiesDialog)
        self.main_layout.setObjectName(u"main_layout")
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.tab_widget = QTabWidget(DynamicBlockPropertiesDialog)
        self.tab_widget.setObjectName(u"tab_widget")
        self.general_page = QWidget()
        self.general_page.setObjectName(u"general_page")
        self.verticalLayout_3 = QVBoxLayout(self.general_page)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.property_tools_panel = QWidget(self.general_page)
        self.property_tools_panel.setObjectName(u"property_tools_panel")
        self.verticalLayout_4 = QVBoxLayout(self.property_tools_panel)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.property_tree_panel = QWidget(self.property_tools_panel)
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
        self.property_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.property_tree.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked|QAbstractItemView.EditTrigger.EditKeyPressed)
        self.property_tree.setAlternatingRowColors(True)
        self.property_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.property_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.property_tree.setRootIsDecorated(True)
        self.property_tree.setUniformRowHeights(True)
        self.property_tree.setItemsExpandable(True)

        self.property_tree_layout.addWidget(self.property_tree)


        self.verticalLayout_4.addWidget(self.property_tree_panel)


        self.verticalLayout_3.addWidget(self.property_tools_panel)

        self.tab_widget.addTab(self.general_page, "")
        self.dae_model_page = QWidget()
        self.dae_model_page.setObjectName(u"dae_model_page")
        self.verticalLayout = QVBoxLayout(self.dae_model_page)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.owner_layout = QHBoxLayout()
        self.owner_layout.setObjectName(u"owner_layout")
        self.equation_owner_label = QLabel(self.dae_model_page)
        self.equation_owner_label.setObjectName(u"equation_owner_label")

        self.owner_layout.addWidget(self.equation_owner_label)

        self.equation_owner_combo = QComboBox(self.dae_model_page)
        self.equation_owner_combo.setObjectName(u"equation_owner_combo")

        self.owner_layout.addWidget(self.equation_owner_combo)


        self.verticalLayout.addLayout(self.owner_layout)

        self.code_search_layout = QHBoxLayout()
        self.code_search_layout.setObjectName(u"code_search_layout")
        self.dae_code_search = QLineEdit(self.dae_model_page)
        self.dae_code_search.setObjectName(u"dae_code_search")
        self.dae_code_search.setClearButtonEnabled(True)

        self.code_search_layout.addWidget(self.dae_code_search)

        self.dae_search_status = QLabel(self.dae_model_page)
        self.dae_search_status.setObjectName(u"dae_search_status")

        self.code_search_layout.addWidget(self.dae_search_status)

        self.dae_search_previous_button = QToolButton(self.dae_model_page)
        self.dae_search_previous_button.setObjectName(u"dae_search_previous_button")
        self.dae_search_previous_button.setEnabled(False)

        self.code_search_layout.addWidget(self.dae_search_previous_button)

        self.dae_search_next_button = QToolButton(self.dae_model_page)
        self.dae_search_next_button.setObjectName(u"dae_search_next_button")
        self.dae_search_next_button.setEnabled(False)

        self.code_search_layout.addWidget(self.dae_search_next_button)

        self.procedural_add_button = QPushButton(self.dae_model_page)
        self.procedural_add_button.setObjectName(u"procedural_add_button")

        self.code_search_layout.addWidget(self.procedural_add_button)


        self.verticalLayout.addLayout(self.code_search_layout)

        self.dae_editor_container = QWidget(self.dae_model_page)
        self.dae_editor_container.setObjectName(u"dae_editor_container")
        self.dae_editor_layout = QVBoxLayout(self.dae_editor_container)
        self.dae_editor_layout.setObjectName(u"dae_editor_layout")
        self.dae_editor_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout.addWidget(self.dae_editor_container)

        self.frame = QFrame(self.dae_model_page)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.dae_validation_status_label = QLabel(self.frame)
        self.dae_validation_status_label.setObjectName(u"dae_validation_status_label")
        self.dae_validation_status_label.setWordWrap(False)
        self.dae_validation_status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.horizontalLayout.addWidget(self.dae_validation_status_label)

        self.horizontalSpacer = QSpacerItem(849, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)


        self.verticalLayout.addWidget(self.frame)

        self.tab_widget.addTab(self.dae_model_page, "")
        self.latex_page = QWidget()
        self.latex_page.setObjectName(u"latex_page")
        self.verticalLayout_2 = QVBoxLayout(self.latex_page)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
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
        icon = QIcon()
        icon.addFile(u":/Icons/icons/download.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.export_rendered_button.setIcon(icon)

        self.export_layout.addWidget(self.export_rendered_button)


        self.latex_source_layout.addLayout(self.export_layout)

        self.latex_splitter.addWidget(self.latex_source_panel)

        self.verticalLayout_2.addWidget(self.latex_splitter)

        self.tab_widget.addTab(self.latex_page, "")
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

        self.status_label = QLabel(DynamicBlockPropertiesDialog)
        self.status_label.setObjectName(u"status_label")
        self.status_label.setVisible(False)
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.main_layout.addWidget(self.status_label)

        self.button_layout = QHBoxLayout()
        self.button_layout.setObjectName(u"button_layout")
        self.button_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.button_layout.addItem(self.button_spacer)

        self.validate_code_button = QPushButton(DynamicBlockPropertiesDialog)
        self.validate_code_button.setObjectName(u"validate_code_button")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/accept.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.validate_code_button.setIcon(icon1)

        self.button_layout.addWidget(self.validate_code_button)

        self.apply_button = QPushButton(DynamicBlockPropertiesDialog)
        self.apply_button.setObjectName(u"apply_button")
        self.apply_button.setIcon(icon1)

        self.button_layout.addWidget(self.apply_button)


        self.main_layout.addLayout(self.button_layout)


        self.retranslateUi(DynamicBlockPropertiesDialog)

        self.tab_widget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(DynamicBlockPropertiesDialog)
    # setupUi

    def retranslateUi(self, DynamicBlockPropertiesDialog):
        DynamicBlockPropertiesDialog.setWindowTitle(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Block properties", None))
        self.property_search.setPlaceholderText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Search properties...", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.general_page), QCoreApplication.translate("DynamicBlockPropertiesDialog", u"General options", None))
        self.equation_owner_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Equation owner", None))
        self.dae_code_search.setPlaceholderText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Search Python code...", None))
        self.dae_search_status.setText("")
        self.dae_search_previous_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Previous", None))
        self.dae_search_next_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Next", None))
#if QT_CONFIG(tooltip)
        self.procedural_add_button.setToolTip(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Add one procedural behavior to the active equation owner's Python code.", None))
#endif // QT_CONFIG(tooltip)
        self.procedural_add_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"+ Add procedural logic", None))
        self.dae_validation_status_label.setText("")
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.dae_model_page), QCoreApplication.translate("DynamicBlockPropertiesDialog", u"DAE model", None))
        self.latex_explanation_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Select the equation groups to include. Each internal block and each DAE section can be selected independently.", None))
        ___qtreewidgetitem = self.latex_selection_tree.headerItem()
        ___qtreewidgetitem.setText(1, QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Equations", None))
        ___qtreewidgetitem.setText(0, QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Block / equation group", None))
        self.latex_select_all_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Select all", None))
        self.latex_clear_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Clear", None))
        self.latex_source_label.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"LaTeX source", None))
        self.latex_source_preview.setPlaceholderText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Select equation groups to generate copyable LaTeX source.", None))
        self.export_rendered_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Download rendered PDF", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.latex_page), QCoreApplication.translate("DynamicBlockPropertiesDialog", u"LaTeX rendering", None))
        self.special_settings_description.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"These settings contain structured data used to regenerate the block. Edit sequences with valid Python tuple/list syntax.", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.special_settings_page), QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Special configuration", None))
        self.status_label.setText("")
        self.validate_code_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Validate model", None))
        self.apply_button.setText(QCoreApplication.translate("DynamicBlockPropertiesDialog", u"Apply changes", None))
    # retranslateUi

