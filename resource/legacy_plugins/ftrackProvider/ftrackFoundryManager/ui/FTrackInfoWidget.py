
from FnAssetAPI.ui.toolkit import QtCore, QtGui, QtNetwork, QtWidgets, QtWebCompat
from FnAssetAPI.ui.widgets import InfoWidget
import FnAssetAPI.ui
import ftrack
import os

from FnAssetAPI.exceptions import *

from .. import utils

import widgets.ftrackresources_rc

class FTrackInfoWidget(InfoWidget):

    def __init__(self, parent = None):
        super(FTrackInfoWidget, self).__init__(parent)
        self._initUI()

    @classmethod
    def getDisplayName(cls):
        return "ftrack Info Panel"

    def _initUI(self):
        self.ftrackProxy = utils.getFtrackQNetworkProxy()
        
        self.setMinimumHeight(400)
        self.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding))
    
        self.setWindowTitle("ftrack Info Panel")
        self.setObjectName("com.ftrack.infopanel.1")
        #self.setLayout(QtWidgets.QVBoxLayout())
        
        if 'FTRACK_TASKID' in os.environ:     
            self.layout = QtWidgets.QVBoxLayout(self)
            self.layout.setContentsMargins(0, 0, 0, 0)
    
            self.__tabWidget = QtWidgets.QTabWidget(self)
            self.layout.addWidget(self.__tabWidget)
            
            self.firstTab = QtWidgets.QWidget(self)
            self.verticalLayout = QtWidgets.QVBoxLayout()
            self.firstTab.setLayout(self.verticalLayout)
            
            self.__tabWidget.addTab(self.firstTab, 'Selection')
            
            
            self.secondTab = QtWidgets.QWidget(self)
            self.verticalLayoutSecond = QtWidgets.QVBoxLayout()
            self.verticalLayoutSecond.setContentsMargins(0, 0, 0, 0)
            self.verticalLayoutSecond.setSpacing(0)
            self.secondTab.setLayout(self.verticalLayoutSecond)
            
            self.__tabWidget.addTab(self.secondTab, 'Working Task')
            
            task = utils.objectById(os.environ['FTRACK_TASKID'])
            url = task.getWebWidgetUrl('info', theme='tf')
            
            self.webViewTask = QtWebCompat.QWebView()
            self.verticalLayoutSecond.addWidget(self.webViewTask)         
            self.webViewTask.load(QtCore.QUrl(url))
        
        else:
            self.verticalLayout = QtWidgets.QVBoxLayout(self)
    
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)
        
        self.spacerItemTop = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(self.spacerItemTop)
        
        self.nothingLabel = QtWidgets.QLabel(self)
        self.nothingLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.nothingLabel.setText("Nothing selected")
        self.logoLabel = QtWidgets.QLabel(self)
        self.logoLabel.setMinimumSize(QtCore.QSize(300, 108))
        self.logoLabel.setMaximumSize(QtCore.QSize(300, 108))
        self.logoLabel.setText("")
        self.logoLabel.setPixmap(QtGui.QPixmap(":/ftrack-logo-grayscale.png"))
        self.logoLabel.setScaledContents(True)
        
        self.verticalLayout.addWidget(self.nothingLabel)
        
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        
        self.horizontalLayout.addWidget(self.logoLabel)
        self.verticalLayout.addLayout(self.horizontalLayout)
    
        self.webView = QtWebCompat.QWebView()
        self.verticalLayout.addWidget(self.webView)
        self.webView.hide()
        
        self.spacerItemBottom = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(self.spacerItemBottom)

    def setEntityReference(self, entityReference):
        obj = None
        if entityReference:
            try:
                obj = utils.objectById(entityReference)
            except InvalidEntityReference:
                import traceback
                tb = traceback.format_exc()
                FnAssetAPI.logging.debug(tb)
        if obj:
            self.setNode(obj)


    def setNode(self, obj):
        # If no page is loaded get the URL from the node.
        if isinstance(obj, ftrack.Component):
            obj = obj.getVersion()
        if self.webView.url().isEmpty():
            # Hide initial state
            self.logoLabel.hide()
            self.nothingLabel.hide()
            self.spacerItemBottom.changeSize(0,0)
            self.spacerItemTop.changeSize(0,0)
            self.webView.show()
            # TODO: Some types of entities don't have this yet, eg assetversions.
            # Add some checking here if it's not going to be available from all entities.
            if hasattr(obj, 'getWebWidgetUrl'):
                url = obj.getWebWidgetUrl(name='info', theme='tf')
                FnAssetAPI.logging.debug(url)
                if url is not None:
                    # Shouldn't be, but safety first...
                    self.webView.load( QtCore.QUrl( url ) )
        else:
            task = obj
            # Otherwise, just send some manager-specific javascript to update to the new entity.
            itemType = None
            if task:
                itemId = task.getId()
                itemType = task._type # Was get('entityType') but that wasn't on assetversions so using this at Carl's suggestion.
                js = 'FT.WebMediator.setEntity({entityId:"%s",entityType:"%s"})' % (itemId, itemType)
                self.webView.page().mainFrame().evaluateJavaScript(js)
