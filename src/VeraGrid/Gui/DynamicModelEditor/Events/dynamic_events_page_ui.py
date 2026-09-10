# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dynamic_events_page_ui.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QGridLayout,
    QHeaderView, QLabel, QSizePolicy, QTableView,
    QToolBar, QVBoxLayout, QWidget)
from VeraGrid.Gui.Icons.icons_rc import *

class Ui_DynamicEventsPage(object):
    def setupUi(self, DynamicEventsPage):
        if not DynamicEventsPage.objectName():
            DynamicEventsPage.setObjectName(u"DynamicEventsPage")
        DynamicEventsPage.resize(900, 560)
        self.actionClearDeviceEvents = QAction(DynamicEventsPage)
        self.actionClearDeviceEvents.setObjectName(u"actionClearDeviceEvents")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/new.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionClearDeviceEvents.setIcon(icon)
        self.actionClearDeviceEvents.setPriority(QAction.Priority.LowPriority)
        self.actionSave = QAction(DynamicEventsPage)
        self.actionSave.setObjectName(u"actionSave")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/savec.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionSave.setIcon(icon1)
        self.actionSave.setPriority(QAction.Priority.LowPriority)
        self.actionSwitchSequence = QAction(DynamicEventsPage)
        self.actionSwitchSequence.setObjectName(u"actionSwitchSequence")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/area_transfer.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionSwitchSequence.setIcon(icon2)
        self.actionAdd = QAction(DynamicEventsPage)
        self.actionAdd.setObjectName(u"actionAdd")
        icon3 = QIcon()
        icon3.addFile(u":/Icons/icons/plus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionAdd.setIcon(icon3)
        self.actionRemove = QAction(DynamicEventsPage)
        self.actionRemove.setObjectName(u"actionRemove")
        icon4 = QIcon()
        icon4.addFile(u":/Icons/icons/minus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionRemove.setIcon(icon4)
        self.mainLayout = QVBoxLayout(DynamicEventsPage)
        self.mainLayout.setSpacing(0)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.eventsToolBar = QToolBar(DynamicEventsPage)
        self.eventsToolBar.setObjectName(u"eventsToolBar")
        self.eventsToolBar.setMovable(False)
        self.eventsToolBar.setIconSize(QSize(24, 24))
        self.eventsToolBar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.eventsToolBar.setFloatable(False)

        self.mainLayout.addWidget(self.eventsToolBar)

        self.eventsTreeFrame = QFrame(DynamicEventsPage)
        self.eventsTreeFrame.setObjectName(u"eventsTreeFrame")
        self.eventsTreeFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.eventsTreeLayout = QGridLayout(self.eventsTreeFrame)
        self.eventsTreeLayout.setObjectName(u"eventsTreeLayout")
        self.eventsTreeLayout.setContentsMargins(0, 0, 0, 0)
        self.eventsTableView = QTableView(self.eventsTreeFrame)
        self.eventsTableView.setObjectName(u"eventsTableView")
        self.eventsTableView.setAlternatingRowColors(False)
        self.eventsTableView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.eventsTableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.eventsTreeLayout.addWidget(self.eventsTableView, 0, 0, 1, 1)

        self.emptyModelMessage = QLabel(self.eventsTreeFrame)
        self.emptyModelMessage.setObjectName(u"emptyModelMessage")
        self.emptyModelMessage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emptyModelMessage.setWordWrap(True)

        self.eventsTreeLayout.addWidget(self.emptyModelMessage, 0, 0, 1, 1)


        self.mainLayout.addWidget(self.eventsTreeFrame)


        self.eventsToolBar.addAction(self.actionClearDeviceEvents)
        self.eventsToolBar.addAction(self.actionSave)
        self.eventsToolBar.addSeparator()
        self.eventsToolBar.addAction(self.actionSwitchSequence)
        self.eventsToolBar.addAction(self.actionAdd)
        self.eventsToolBar.addAction(self.actionRemove)

        self.retranslateUi(DynamicEventsPage)

        QMetaObject.connectSlotsByName(DynamicEventsPage)
    # setupUi

    def retranslateUi(self, DynamicEventsPage):
        DynamicEventsPage.setWindowTitle(QCoreApplication.translate("DynamicEventsPage", u"Dynamic Events", None))
        self.actionClearDeviceEvents.setText(QCoreApplication.translate("DynamicEventsPage", u"New", None))
#if QT_CONFIG(tooltip)
        self.actionClearDeviceEvents.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Delete all events of this simulation mode from the current device", None))
#endif // QT_CONFIG(tooltip)
        self.actionSave.setText(QCoreApplication.translate("DynamicEventsPage", u"Save", None))
#if QT_CONFIG(tooltip)
        self.actionSave.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Save event changes", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionSave.setShortcut(QCoreApplication.translate("DynamicEventsPage", u"Ctrl+S", None))
#endif // QT_CONFIG(shortcut)
        self.actionSwitchSequence.setText("")
#if QT_CONFIG(tooltip)
        self.actionSwitchSequence.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Create an EMT switch opening and reclosing event sequence", None))
#endif // QT_CONFIG(tooltip)
        self.actionAdd.setText("")
#if QT_CONFIG(tooltip)
        self.actionAdd.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Add an event to the selected event group", None))
#endif // QT_CONFIG(tooltip)
        self.actionRemove.setText("")
#if QT_CONFIG(tooltip)
        self.actionRemove.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Remove the selected event or event group", None))
#endif // QT_CONFIG(tooltip)
        self.emptyModelMessage.setText(QCoreApplication.translate("DynamicEventsPage", u"This dynamic model is empty. New events cannot be added until the model is built.", None))
    # retranslateUi

