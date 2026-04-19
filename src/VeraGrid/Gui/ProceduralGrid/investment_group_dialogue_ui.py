# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'investment_group_dialogue_ui.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox,
    QHBoxLayout, QLabel, QLineEdit, QSizePolicy,
    QVBoxLayout, QWidget)


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(420, 180)
        self.verticalLayout = QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(u"verticalLayout")

        self.questionLabel = QLabel(Dialog)
        self.questionLabel.setObjectName(u"questionLabel")
        self.questionLabel.setWordWrap(True)
        self.verticalLayout.addWidget(self.questionLabel)

        self.groupSelectLayout = QHBoxLayout()
        self.groupSelectLayout.setObjectName(u"groupSelectLayout")

        self.groupLabel = QLabel(Dialog)
        self.groupLabel.setObjectName(u"groupLabel")
        self.groupSelectLayout.addWidget(self.groupLabel)

        self.groupComboBox = QComboBox(Dialog)
        self.groupComboBox.setObjectName(u"groupComboBox")
        self.groupSelectLayout.addWidget(self.groupComboBox)

        self.verticalLayout.addLayout(self.groupSelectLayout)

        self.newGroupLayout = QHBoxLayout()
        self.newGroupLayout.setObjectName(u"newGroupLayout")

        self.newGroupLabel = QLabel(Dialog)
        self.newGroupLabel.setObjectName(u"newGroupLabel")
        self.newGroupLayout.addWidget(self.newGroupLabel)

        self.groupNameLineEdit = QLineEdit(Dialog)
        self.groupNameLineEdit.setObjectName(u"groupNameLineEdit")
        self.newGroupLayout.addWidget(self.groupNameLineEdit)

        self.verticalLayout.addLayout(self.newGroupLayout)

        self.buttonBox = QDialogButtonBox(Dialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.questionLabel.setText(QCoreApplication.translate("Dialog", u"Do you want to assign the generated objects to an investment group?", None))
        self.groupLabel.setText(QCoreApplication.translate("Dialog", u"Investment group:", None))
        self.newGroupLabel.setText(QCoreApplication.translate("Dialog", u"New group name:", None))
    # retranslateUi
