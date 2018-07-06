# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Details.ui'
#
# Created: Thu Aug  1 19:10:23 2013
#      by: pyside-uic 0.2.14 running on PySide 1.1.2
#
# WARNING! All changes made in this file will be lost!

from QtExt import QtCore, QtGui, QtWidgets

class Ui_Details(object):
    def setupUi(self, Details):
        Details.setObjectName("Details")
        Details.resize(461, 333)
        self.verticalLayout = QtWidgets.QVBoxLayout(Details)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.propertyTable = QtWidgets.QTableWidget(Details)
        self.propertyTable.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.propertyTable.setRowCount(3)
        self.propertyTable.setColumnCount(1)
        self.propertyTable.setObjectName("propertyTable")
        self.propertyTable.setColumnCount(1)
        self.propertyTable.setRowCount(3)
        self.propertyTable.horizontalHeader().setVisible(False)
        self.verticalLayout.addWidget(self.propertyTable)

        self.retranslateUi(Details)
        QtCore.QMetaObject.connectSlotsByName(Details)

    def retranslateUi(self, Details):
        Details.setWindowTitle(QtWidgets.QApplication.translate("Details", "Form", None, QtWidgets.QApplication.UnicodeUTF8))

