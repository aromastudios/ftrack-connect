import os

import FnAssetAPI
from FnAssetAPI.exceptions import InvalidEntityReference
from FnAssetAPI.ui.toolkit import QtCore, QtGui, QtWidgets
from FnAssetAPI.ui.widgets import InlinePickerWidget

from FTrackBrowserDialog import FTrackBrowserDialog
from .. import utils


class FTrackInlinePickerWidget(InlinePickerWidget):

  def __init__(self, specification, context, parent=None):
    super(FTrackInlinePickerWidget, self).__init__(specification, context, parent)

    self.selection = ''
    self._noSelectionMsg = "No ftrack destination selected"

    layout = QtWidgets.QHBoxLayout()
    self.setLayout(layout)

    ## @todo This is a duplicate of FTrackInterface.getInfo need to find a
    ## better place for this so we don't get out of sync if it changes.
    basePath = os.path.dirname(os.path.realpath(__file__))
    iconPath = os.path.join(basePath, "widgets", "PNG", "logobox.png")

    icon = QtGui.QPixmap(iconPath)
    smallIcon = icon.scaled(QtCore.QSize(24, 24),
      QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

    iconLabel = QtWidgets.QLabel()
    iconLabel.setPixmap(smallIcon)
    layout.addWidget(iconLabel)

    self._label = QtWidgets.QLabel(self._noSelectionMsg)
    self._label.setEnabled(False)
    layout.addWidget(self._label)

    layout.addStretch()

    self._browse = QtWidgets.QPushButton("Browse...")
    layout.addWidget(self._browse)

    self._browse.clicked.connect(self.browse)


  def browse(self):

    current = self.getSelection()

    # The context has been cloned from the original one passed to the
    # constructor by the base class. This ensures it has not been mutated by
    # any further requests to the API since creating the widget. Many things
    # may have happened before the user actually clicks on this button (ie:
    # context.access might have been changed for other UI elements queries)...
    browser = FTrackBrowserDialog(self._specification, self._context)
    browser.setSelection(current)

    if browser.exec_():
      self.setSelection(browser.getSelection())
      self._emitSelectionChanged()


  def getSelection(self):

    text = self.selection
    return [text,] if text else []


  def setSelection(self, refs):

    path = ''
    self.selection = ''

    if refs:
        ref = refs[0]
        try:
            obj = utils.objectById(ref)
            path = utils.getPath(obj, slash=True)
            self.selection = ref
        except InvalidEntityReference:
            import traceback
            tb = traceback.format_exc()
            FnAssetAPI.logging.debug(tb)

    label = path if path else self._noSelectionMsg
    self._label.setText(label)
    self._label.setEnabled(bool(path))

