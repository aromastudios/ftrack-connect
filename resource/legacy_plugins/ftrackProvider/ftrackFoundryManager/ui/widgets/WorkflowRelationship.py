# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'WorkflowRelationship.ui'
#
# Created: Thu Aug  8 12:43:21 2013
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from QtExt import QtCore, QtGui, QtWidgets

class Ui_WorkflowRelationship(object):
    def setupUi(self, WorkflowRelationship):
        WorkflowRelationship.setObjectName("WorkflowRelationship")
        WorkflowRelationship.resize(275, 106)
        self.verticalLayout = QtWidgets.QVBoxLayout(WorkflowRelationship)
        self.verticalLayout.setObjectName("verticalLayout")
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.gridLayout.addItem(spacerItem, 2, 0, 1, 1)
        self.label = QtWidgets.QLabel(WorkflowRelationship)
        self.label.setObjectName("label")
        self.gridLayout.addWidget(self.label, 1, 0, 1, 1)
        self.taskCombo = QtWidgets.QComboBox(WorkflowRelationship)
        self.taskCombo.setObjectName("taskCombo")
        self.gridLayout.addWidget(self.taskCombo, 1, 1, 1, 1)
        self.versionCombo = QtWidgets.QComboBox(WorkflowRelationship)
        self.versionCombo.setObjectName("versionCombo")
        self.gridLayout.addWidget(self.versionCombo, 0, 1, 1, 1)
        self.label_2 = QtWidgets.QLabel(WorkflowRelationship)
        self.label_2.setObjectName("label_2")
        self.gridLayout.addWidget(self.label_2, 0, 0, 1, 1)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem1, 0, 2, 1, 1)
        self.verticalLayout.addLayout(self.gridLayout)

        self.retranslateUi(WorkflowRelationship)
        QtCore.QMetaObject.connectSlotsByName(WorkflowRelationship)

    def retranslateUi(self, WorkflowRelationship):
        WorkflowRelationship.setWindowTitle(QtWidgets.QApplication.translate("WorkflowRelationship", "Form", None, QtWidgets.QApplication.UnicodeUTF8))
        self.label.setText(QtWidgets.QApplication.translate("WorkflowRelationship", "Task:", None, QtWidgets.QApplication.UnicodeUTF8))
        self.label_2.setText(QtWidgets.QApplication.translate("WorkflowRelationship", "Version:", None, QtWidgets.QApplication.UnicodeUTF8))

