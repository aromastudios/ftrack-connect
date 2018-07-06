"""
A widget to display the tasks for a user..

Copyright (c) 2013 The Foundry Visionmongers Ltd.  All Rights Reserved.
"""

import os
import ftrack
from FnAssetAPI.ui.toolkit import QtCore, QtGui, QtWidgets, QtWebCompat
from FnAssetAPI.ui.widgets import BaseWidget
from FnAssetAPI.ui.widgets import attributes


class FTrackTasksWidget(BaseWidget):

  _kIdentifier = "com.ftrack.taskspanel.1"
  _kDisplayName = "ftrack Tasks Panel"

  def __init__(self, assetManager = None, parent = None):
    super(FTrackTasksWidget, self).__init__(parent)
    self.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding))

    self.setWindowTitle("ftrack Tasks Panel")
    self.setObjectName(self.getIdentifier())

    self._initUI()


  def _initUI(self):
    self.setLayout(QtWidgets.QVBoxLayout()) 
    
    url = ftrack.getWebWidgetUrl('tasks', theme='tf')
    
    self.webView = QtWebCompat.QWebView()
    self.layout().addWidget(self.webView)
    self.layout().setContentsMargins(0, 0, 0, 0)
    self.layout().setSpacing(0)
    self.webView.load( QtCore.QUrl( url ) )
    
    
  @classmethod
  def getAttributes(cls):
    attr = super(FTrackTasksWidget, cls).getAttributes()
    return attr | attributes.kCreateApplicationPanel
