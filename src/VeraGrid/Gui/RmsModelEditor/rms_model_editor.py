# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'rms_model_editor.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout,
    QMainWindow, QPushButton, QSizePolicy, QSpacerItem,
    QTabWidget, QVBoxLayout, QWidget)
from .icons_rc import *

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(966, 538)
        self.actionCheckModel = QAction(MainWindow)
        self.actionCheckModel.setObjectName(u"actionCheckModel")
        self.actionCheckModel.setMenuRole(QAction.MenuRole.NoRole)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.model_selector_comboBox = QComboBox(self.frame)
        self.model_selector_comboBox.addItem("")
        self.model_selector_comboBox.addItem("")
        self.model_selector_comboBox.addItem("")
        self.model_selector_comboBox.setObjectName(u"model_selector_comboBox")

        self.horizontalLayout.addWidget(self.model_selector_comboBox)

        self.apply_selected_model_pushButton = QPushButton(self.frame)
        self.apply_selected_model_pushButton.setObjectName(u"apply_selected_model_pushButton")

        self.horizontalLayout.addWidget(self.apply_selected_model_pushButton)

        self.horizontalSpacer = QSpacerItem(856, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)


        self.verticalLayout.addWidget(self.frame)

        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setTabPosition(QTabWidget.TabPosition.South)
        self.tab_3 = QWidget()
        self.tab_3.setObjectName(u"tab_3")
        self.verticalLayout_2 = QVBoxLayout(self.tab_3)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.templatesLayout = QVBoxLayout()
        self.templatesLayout.setObjectName(u"templatesLayout")

        self.verticalLayout_2.addLayout(self.templatesLayout)

        self.tabWidget.addTab(self.tab_3, "")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.verticalLayout_4 = QVBoxLayout(self.tab)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.editorLayout = QVBoxLayout()
        self.editorLayout.setObjectName(u"editorLayout")

        self.verticalLayout_4.addLayout(self.editorLayout)

        self.tabWidget.addTab(self.tab, "")
        self.tab_edit = QWidget()
        self.tab_edit.setObjectName(u"tab_edit")
        self.horizontalLayout_2 = QHBoxLayout(self.tab_edit)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.equations_editor_layout = QHBoxLayout()
        self.equations_editor_layout.setObjectName(u"equations_editor_layout")

        self.horizontalLayout_2.addLayout(self.equations_editor_layout)

        self.tabWidget.addTab(self.tab_edit, "")

        self.verticalLayout.addWidget(self.tabWidget)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.actionCheckModel.setText(QCoreApplication.translate("MainWindow", u"CheckModel", None))
        self.model_selector_comboBox.setItemText(0, QCoreApplication.translate("MainWindow", u"Template model", None))
        self.model_selector_comboBox.setItemText(1, QCoreApplication.translate("MainWindow", u"Block editor model", None))
        self.model_selector_comboBox.setItemText(2, QCoreApplication.translate("MainWindow", u"Equations editor model", None))

        self.model_selector_comboBox.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Select model to apply", None))
        self.apply_selected_model_pushButton.setText(QCoreApplication.translate("MainWindow", u"Apply", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_3), QCoreApplication.translate("MainWindow", u"Template", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("MainWindow", u"Block editor", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_edit), QCoreApplication.translate("MainWindow", u"Equations editor", None))
    # retranslateUi

