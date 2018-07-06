from FnAssetAPI.ui.toolkit import QtGui, QtWidgets
from FnAssetAPI.ui.widgets import RegistrationManagerOptionsWidget

from .. import FTrackPublish


class FTrackRegistrationOptionsWidget(RegistrationManagerOptionsWidget):
  """

  Presents options that can affect the publishing of assets. This is used for
  time when assets are to be published to pre-determined entity refs, and so we
  have no way of appending options to the ref string. It is also only used in
  situations whereby the context is preserved between UI interaction, and
  registration activities.

  Presently, we use this to allow the user to customise the target task type,
  but we could also allow it to set an initial status, etc...

  NOTE: The context should NEVER be modified directly, all options should be
  passed back through getOptions()

  """

  def __init__(self, specification, context, parent=None):
    super(FTrackRegistrationOptionsWidget, self).__init__(specification,
        context, parent=parent)

    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0,0,0,0)

    self.setLayout(layout)
    self._initUI(layout)


  def _initUI(self, layout):

    self._taskTypeCombo = None

    # See what options we need based on the spec

    if self._specification.isOfType("group"):

      # If we don't have any options, hide ourself
      self.setHidden(True)

    else:

      # If we're not a group, assume for now, were some kind of asset

      # Task Type
      # {

      self._taskTypeCombo = QtWidgets.QComboBox()
      self._taskTypeCombo.addItems(("Compositing", "Editing"))

      # Get a default
      taskType, taskName = FTrackPublish.getTaskTypeAndName(self._specification)
      index = self._taskTypeCombo.findText(taskType)
      if index > -1:
        self._taskTypeCombo.setCurrentIndex(index)

      taskLayout = QtWidgets.QHBoxLayout()
      taskLayout.addWidget(QtWidgets.QLabel("Create under task:"))
      taskLayout.addWidget(self._taskTypeCombo)
      layout.addLayout(taskLayout)

      self._taskTypeCombo.currentIndexChanged.connect(self._emitOptionsChanged)
      # }



  def getOptions(self):

    options = {}

    if self._taskTypeCombo:
      options[FTrackPublish.kTaskTypeKey] = str(self._taskTypeCombo.currentText())

    return options


  def setOptions(self, options):

    if self._taskTypeCombo:
      taskType = options.get(FTrackPublish.kTaskTypeKey, None)
      if taskType:
        index = self._taskTypeCombo.findText(taskType)
        if index > -1:
          self._taskTypeCombo.setCurrentIndex(index)


