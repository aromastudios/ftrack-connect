# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'CreateDialog.ui'
#
# Created: Wed Aug 28 18:14:58 2013
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from QtExt import QtCore, QtGui, QtWidgets

class Ui_CreateDialog(object):
    def setupUi(self, CreateDialog):
        CreateDialog.setObjectName("CreateDialog")
        CreateDialog.resize(268, 133)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(CreateDialog)
        self.verticalLayout_2.setContentsMargins(6, 6, 6, 6)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName("verticalLayout")
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.nameLbl = QtWidgets.QLabel(CreateDialog)
        self.nameLbl.setObjectName("nameLbl")
        self.gridLayout.addWidget(self.nameLbl, 2, 0, 1, 1)
        self.typeLbl = QtWidgets.QLabel(CreateDialog)
        self.typeLbl.setEnabled(True)
        self.typeLbl.setObjectName("typeLbl")
        self.gridLayout.addWidget(self.typeLbl, 1, 0, 1, 1)
        self.objLbl = QtWidgets.QLabel(CreateDialog)
        self.objLbl.setObjectName("objLbl")
        self.gridLayout.addWidget(self.objLbl, 0, 0, 1, 1)
        self.nameLine = QtWidgets.QLineEdit(CreateDialog)
        self.nameLine.setObjectName("nameLine")
        self.gridLayout.addWidget(self.nameLine, 2, 1, 1, 1)
        self.typeCombo = QtWidgets.QComboBox(CreateDialog)
        self.typeCombo.setEnabled(True)
        self.typeCombo.setObjectName("typeCombo")
        self.gridLayout.addWidget(self.typeCombo, 1, 1, 1, 1)
        self.objectCombo = QtWidgets.QComboBox(CreateDialog)
        self.objectCombo.setObjectName("objectCombo")
        self.gridLayout.addWidget(self.objectCombo, 0, 1, 1, 1)
        self.verticalLayout.addLayout(self.gridLayout)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.cancelButton = QtWidgets.QPushButton(CreateDialog)
        self.cancelButton.setObjectName("cancelButton")
        self.horizontalLayout.addWidget(self.cancelButton)
        self.createButton = QtWidgets.QPushButton(CreateDialog)
        self.createButton.setAutoDefault(True)
        self.createButton.setDefault(True)
        self.createButton.setObjectName("createButton")
        self.horizontalLayout.addWidget(self.createButton)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.retranslateUi(CreateDialog)
        QtCore.QObject.connect(self.objectCombo, QtCore.SIGNAL("currentIndexChanged(int)"), CreateDialog.objectTypeChanged)
        QtCore.QMetaObject.connectSlotsByName(CreateDialog)

    def retranslateUi(self, CreateDialog):
        CreateDialog.setWindowTitle(QtWidgets.QApplication.translate("CreateDialog", "Form", None, QtWidgets.QApplication.UnicodeUTF8))
        self.nameLbl.setText(QtWidgets.QApplication.translate("CreateDialog", "Name", None, QtWidgets.QApplication.UnicodeUTF8))
        self.typeLbl.setText(QtWidgets.QApplication.translate("CreateDialog", "Type", None, QtWidgets.QApplication.UnicodeUTF8))
        self.objLbl.setText(QtWidgets.QApplication.translate("CreateDialog", "Object", None, QtWidgets.QApplication.UnicodeUTF8))
        self.cancelButton.setText(QtWidgets.QApplication.translate("CreateDialog", "Cancel", None, QtWidgets.QApplication.UnicodeUTF8))
        self.createButton.setText(QtWidgets.QApplication.translate("CreateDialog", "Create", None, QtWidgets.QApplication.UnicodeUTF8))

