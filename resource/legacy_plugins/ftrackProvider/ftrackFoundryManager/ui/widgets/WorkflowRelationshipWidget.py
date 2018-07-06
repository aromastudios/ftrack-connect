import os
from QtExt import QtCore, QtGui, QtWidgets
from WorkflowRelationship import Ui_WorkflowRelationship
import ftrack
import FnAssetAPI

class WorkflowRelationshipWidget(QtWidgets.QWidget):

    def __init__(self, parent):
        super(WorkflowRelationshipWidget, self).__init__(parent=parent)
        self.ui = Ui_WorkflowRelationship()
        self.ui.setupUi(self)
        
        
        self.ui.versionCombo.addItem('Latest', 'latest')
        self.ui.versionCombo.addItem('Latest Approved', 'latestapproved')
        
        
        taskTypes = ftrack.getTaskTypes()
        
        session = FnAssetAPI.SessionManager.currentSession()
        host = session.getHost()
        hostId = host.getIdentifier()
        
        selectTaskType = ''     
        if hostId == 'uk.co.foundry.hiero':
            selectTaskType = 'Compositing'
        
        rowCntr = 0
        for taskType in sorted(taskTypes, key=lambda x: x.getName().lower()):
            self.ui.taskCombo.addItem(taskType.getName(), taskType.getEntityRef())
            if taskType.getName() == selectTaskType:
                self.ui.taskCombo.setCurrentIndex(rowCntr)
            rowCntr += 1
        
    def getCriteria(self):
        return self.ui.versionCombo.itemData(self.ui.versionCombo.currentIndex()) + ',' + self.ui.taskCombo.itemData(self.ui.taskCombo.currentIndex())
