import os
from QtExt import QtCore, QtGui, QtWidgets
import ftrack

from ... import utils

class DetailsWidget(QtWidgets.QWidget):
    def __init__(self, parent):
        super(DetailsWidget, self).__init__(parent=parent)
        
        self.placholderThumbnail = (os.environ['FTRACK_SERVER'] + '/img/thumbnail2.png')
        self.thumbnailCache = {}
        
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        
        self.thumbnailWidget = QtWidgets.QLabel()
        self.thumbnailWidget.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        self.thumbnailWidget.setAlignment(QtCore.Qt.AlignCenter)
        #self.thumbnailWidget.setFixedWidth(240)
        self.thumbnailWidget.setFixedHeight(160)
        
        self.verticalLayout.addWidget(self.thumbnailWidget)
        
        self.propertyTable = QtWidgets.QTableWidget(self)
        self.propertyTable.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.propertyTable.setColumnCount(1)
        self.propertyTable.setObjectName("propertyTable")
        self.propertyTable.horizontalHeader().setVisible(False)
        
        self.verticalLayout.addWidget(self.propertyTable)
        
        self.headers = (
            'Name', 'Author', 'Version', 'Date', 'Comment', 'Status', 'Priority'
        )
        self.propertyTable.setRowCount(len(self.headers))
        self.propertyTable.setVerticalHeaderLabels(self.headers)
        #self.propertyTable.setRowCount(5)
        
        horizontalHeader = self.propertyTable.horizontalHeader()
        horizontalHeader.hide()
        horizontalHeader.setResizeMode(QtWidgets.QHeaderView.Stretch)
        
        verticalHeader = self.propertyTable.verticalHeader()
        verticalHeader.setResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        
    def updateDetails(self, ftrackID):
        obj = utils.objectById(ftrackID)
        self.setEnabled(True)
        assetVersion = None
        thumbUrl = None
        if isinstance(obj, ftrack.Asset):
            assetVersion = obj.getVersions()[-1]
        elif isinstance(obj, ftrack.AssetVersion):
            assetVersion = obj
        elif isinstance(obj, ftrack.Component):
            assetVersion = obj.getVersion()

        
        name = str(utils.objectName(obj))    
        if assetVersion:
        
            authorUser = assetVersion.getUser()    
            version = str(assetVersion.getVersion())
            comment = assetVersion.getComment() 
            vdate = str(assetVersion.getDate()) 
            
            
            author = str(authorUser.getName().encode("ascii", "replace"))
            
            self.propertyTable.setRowHidden(1, False)
            self.propertyTable.setRowHidden(2, False)
            self.propertyTable.setRowHidden(3, False)
            self.propertyTable.setRowHidden(4, False)
            self.propertyTable.setRowHidden(5, True)
            self.propertyTable.setRowHidden(6, True)
            
            self.propertyTable.setItem(0, 1, QtWidgets.QTableWidgetItem(author))
            self.propertyTable.setItem(0, 3, QtWidgets.QTableWidgetItem(vdate))
            self.propertyTable.setItem(0, 2, QtWidgets.QTableWidgetItem(version))
            self.propertyTable.setItem(0, 4, QtWidgets.QTableWidgetItem(comment))
            
            thumbUrl = assetVersion.getThumbnail()
        else:
            if hasattr(obj, 'getThumbnail'):
                thumbUrl = obj.getThumbnail()
            self.propertyTable.setRowHidden(1, True)
            self.propertyTable.setRowHidden(2, True)
            self.propertyTable.setRowHidden(3, True)
            self.propertyTable.setRowHidden(4, True)
            self.propertyTable.setRowHidden(5, False)
            self.propertyTable.setRowHidden(6, False)

            priorityName = ''
            if hasattr(obj, 'getPriority'):
                priority = obj.getPriority()
                if priority:
                    priorityName = priority.getName()

            statusName = ''
            if hasattr(obj, 'getStatus'):
                status = obj.getStatus()
                if status:
                    statusName = status.getName()

            self.propertyTable.setItem(
                0, 5, QtWidgets.QTableWidgetItem(statusName)
            )
            self.propertyTable.setItem(
                0, 6, QtWidgets.QTableWidgetItem(priorityName)
            )

        self.propertyTable.setItem(0, 0, QtWidgets.QTableWidgetItem(name))
        
        if not thumbUrl:
            thumbUrl = self.placholderThumbnail
        self._updateThumbnail([self.thumbnailWidget, thumbUrl])
        
        self.propertyTable.resizeRowsToContents()
        
    def _updateThumbnail(self, arg):
        '''Update thumbnail for *label* with image at *url*.'''
        label = arg[0]
        url = arg[1]
        label.setText('')
        pixmap = self._pixmapFromUrl(url)

        scaledPixmap = pixmap.scaledToWidth(
            label.width(),
            mode=QtCore.Qt.SmoothTransformation
        )
        
        if scaledPixmap.height() > label.height():        
            scaledPixmap = pixmap.scaledToHeight(
                label.height(),
                mode=QtCore.Qt.SmoothTransformation
            )
        
        label.setPixmap(scaledPixmap)
            
    def _pixmapFromUrl(self, url):
        '''Retrieve *url* and return data as a pixmap.'''
        pixmap = self.thumbnailCache.get(url)
        if pixmap is None:
            data = utils.getFileFromUrl(url)
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(data)
            self.thumbnailCache[url] = pixmap
        
        # Handle null pixmaps. E.g. JPG on Windows.
        if pixmap.isNull():
            pixmap = self.thumbnailCache.get(self.placholderThumbnail, pixmap)
            
        return pixmap