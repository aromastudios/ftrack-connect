from FnAssetAPI.ui.toolkit import QtGui, QtWidgets
from FnAssetAPI.ui.widgets import BrowserWidget

import sys

from widgets.BrowserWidget import BrowserWidget as FTBrowserWidget

import FnAssetAPI.specifications
from .. import utils
import ftrack
import os

class FTrackBrowserWidget(BrowserWidget):

    def __init__(self, specification, context, parent=None):
        super(FTrackBrowserWidget, self).__init__(specification, context, parent)

        self._layout = QtWidgets.QHBoxLayout()
        self.setLayout(self._layout)

        self._specification = specification
        self._context = context
        showAssetNameOption = True

        self.browserWidget = FTBrowserWidget(self, specification, context)

        self._layout.addWidget(self.browserWidget)

        self.browserWidget.clickedIdSignal.connect(self._captureSelection)

        isMultiple = self._context.isForMultiple()

        if isMultiple:
            showAssetNameOption = None

        if context.isForWrite():
            self.browserWidget.ui.versionsWidget.hide()

        isGrouping = specification.isOfType(FnAssetAPI.specifications.GroupingSpecification)

        if not isGrouping:
            if context.isForRead():
                self.browserWidget.setShowTasks(False)
                showAssetNameOption = None
            else:
                if context and context.locale and context.locale.isOfType("ftrack.publish"):
                    showAssetNameOption = None

        if specification.getType() == "file.nukescript":
            self.browserWidget.setComponentFilter(['nukescript'])
        elif specification.getType() == "file.hrox":
            self.browserWidget.setComponentFilter(['hieroproject'])

        isFile = specification.isOfType(FnAssetAPI.specifications.FileSpecification)
        isImage = specification.isOfType(FnAssetAPI.specifications.ImageSpecification)

        if isImage:
            self.browserWidget.setMetaFilters(['img_main'])

        isShot = specification.isOfType(FnAssetAPI.specifications.ShotSpecification)

        if context.isForWrite():
            self.browserWidget.setShowAssetVersions(False)
            if not isFile:
                showAssetNameOption = None

        if isShot:
            if context.isForWrite():
                self.browserWidget.setShotsEnabled(False)
                self.browserWidget.setShowTasks(False)
                self.browserWidget.setShowAssets(False)
            elif context.isForRead():
                self.browserWidget.setShotsEnabled(False)
                self.browserWidget.setShowTasks(False)
                self.browserWidget.setShowAssets(False)

            showAssetNameOption = None

        elif isFile or isImage or specification.isOfType("file.hrox"):
            if context.access in ['write']:
                self.browserWidget.setShowTasks(True)
                self.browserWidget.setShowAssets(True)
            elif context.access in ['writeMultiple']:
                self.browserWidget.setShowTasks(True)
                self.browserWidget.setShowAssets(False)

            if context and context.locale and context.locale.isOfType("ftrack.publish"):
                self.browserWidget.setShowAssets(False)

        self.__selection = []

        if not showAssetNameOption:
            self.browserWidget.ui.assetNameLineEdit.hide()
            self.browserWidget.ui.overrideNamehintCheckbox.hide()

        self.browserWidget.populateBookmarks()

        referenceHint = specification.getField('referenceHint')
        if referenceHint:

            self.browserWidget.setStartLocation(referenceHint)
        elif 'FTRACK_TASKID' in os.environ:
            task = ftrack.Task(os.environ['FTRACK_TASKID'])
            self.browserWidget.setStartLocation(task.getEntityRef())

    def _captureSelection(self, selection):
        if self._context.isForRead():
            obj = utils.objectById(selection)
                # Try and get the latest version of an asset
            if isinstance(obj, ftrack.Asset) or isinstance(obj, ftrack.AssetVersion):
                componentName = None
                if self._specification.isOfType("file.nukescript"):
                    componentName = 'nukescript'
                elif self._specification.isOfType("file.hrox"):
                    componentName = 'hieroproject'

                if isinstance(obj, ftrack.Asset):
                    version = obj.getVersions()[-1]
                elif isinstance(obj, ftrack.AssetVersion):
                    version = obj

                component = None
                if componentName:
                    component = version.getComponent(name=componentName)
                else:
                    components = version.getComponents()
                    if components and len(components) == 1:
                        component = components[0]
                    else:
                        self.browserWidget.validSelection = False

                if component:
                    selection = component.getEntityRef()



        self.__selection = [selection,]
        self.selectionChanged.emit(self.__selection)

    def setSelection(self, selection):
        self.browserWidget.setSelection(selection)

    def getSelection(self):
        assetName = None
        if self.browserWidget.ui.overrideNamehintCheckbox.checkState():
            assetNameText = self.browserWidget.ui.assetNameLineEdit.text()
            if assetNameText != '':
                assetName = assetNameText
        if assetName:
            for i in range(len(self.__selection)):
                self.__selection[i] = self.__selection[i] + "&assetName=" + assetName
        return self.__selection

    def selectionValid(self):
        return self.browserWidget.validSelection


