# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'plot_dialogue.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QSizePolicy, QTabWidget, QToolBar, QVBoxLayout,
    QWidget)

from VeraGrid.Gui.Widgets.qt_chart_widget import GraphsWidget

class Ui_PlotDialogue(object):
    def setupUi(self, PlotDialogue):
        if not PlotDialogue.objectName():
            PlotDialogue.setObjectName(u"PlotDialogue")
        PlotDialogue.resize(900, 620)
        self.actionSaveImage = QAction(PlotDialogue)
        self.actionSaveImage.setObjectName(u"actionSaveImage")
        self.actionResetView = QAction(PlotDialogue)
        self.actionResetView.setObjectName(u"actionResetView")
        self.verticalLayout = QVBoxLayout(PlotDialogue)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(6, 6, 6, 6)
        self.plotToolBar = QToolBar(PlotDialogue)
        self.plotToolBar.setObjectName(u"plotToolBar")
        self.plotToolBar.setMovable(False)
        self.plotToolBar.setFloatable(False)

        self.verticalLayout.addWidget(self.plotToolBar)

        self.plotTabs = QTabWidget(PlotDialogue)
        self.plotTabs.setObjectName(u"plotTabs")
        self.plotTabs.setTabPosition(QTabWidget.TabPosition.North)
        self.plotTabs.setTabsClosable(False)
        self.plotTab = QWidget()
        self.plotTab.setObjectName(u"plotTab")
        self.plotTabLayout = QVBoxLayout(self.plotTab)
        self.plotTabLayout.setObjectName(u"plotTabLayout")
        self.plotTabLayout.setContentsMargins(0, 0, 0, 0)
        self.plotwidget = GraphsWidget(self.plotTab)
        self.plotwidget.setObjectName(u"plotwidget")

        self.plotTabLayout.addWidget(self.plotwidget)

        self.plotTabs.addTab(self.plotTab, "")

        self.verticalLayout.addWidget(self.plotTabs)

        self.buttonBox = QDialogButtonBox(PlotDialogue)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)

        self.verticalLayout.addWidget(self.buttonBox)


        self.plotToolBar.addAction(self.actionSaveImage)
        self.plotToolBar.addAction(self.actionResetView)

        self.retranslateUi(PlotDialogue)

        QMetaObject.connectSlotsByName(PlotDialogue)
    # setupUi

    def retranslateUi(self, PlotDialogue):
        PlotDialogue.setWindowTitle(QCoreApplication.translate("PlotDialogue", u"Plot", None))
        self.actionSaveImage.setText(QCoreApplication.translate("PlotDialogue", u"Save image", None))
#if QT_CONFIG(tooltip)
        self.actionSaveImage.setToolTip(QCoreApplication.translate("PlotDialogue", u"Save the current plot as SVG or PNG", None))
#endif // QT_CONFIG(tooltip)
        self.actionResetView.setText(QCoreApplication.translate("PlotDialogue", u"Center data", None))
#if QT_CONFIG(tooltip)
        self.actionResetView.setToolTip(QCoreApplication.translate("PlotDialogue", u"Reset zoom and pan to show all data", None))
#endif // QT_CONFIG(tooltip)
        self.plotTabs.setTabText(self.plotTabs.indexOf(self.plotTab), QCoreApplication.translate("PlotDialogue", u"Plot", None))
    # retranslateUi
