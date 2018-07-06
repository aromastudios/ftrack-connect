from FnAssetAPI.ui.widgets import WorkflowRelationshipWidget
from FnAssetAPI.ui.toolkit import QtGui, QtWidgets

from widgets.WorkflowRelationshipWidget import WorkflowRelationshipWidget as ftrackRel

class FTrackWorkflowRelationshipWidget(WorkflowRelationshipWidget):

    def __init__(self, context, parent=None):
        super(FTrackWorkflowRelationshipWidget, self).__init__(context, parent)

        self._layout = QtWidgets.QHBoxLayout()
        self.setLayout(self._layout)

        self.workflowWidget = ftrackRel(self)

        self._layout.addWidget(self.workflowWidget)

    def getCriteriaString(self):
        return self.workflowWidget.getCriteria()

