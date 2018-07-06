from QtExt import QtCore, QtGui, QtWidgets
from Browser import Ui_Browser
from CreateDialog import Ui_CreateDialog
import ftrack
from ... import utils
import FnAssetAPI
from FnAssetAPI.exceptions import *

class CreateDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, currentHref=None):
        QtGui.QDialog.__init__(self, parent)
        
        if not currentHref:
            self.reject()
        
        self.parent = parent
        self.ui = Ui_CreateDialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Create ftrack Object')
        
        obj = utils.objectById(currentHref)
        objectType = utils.objectType(obj)
        
        disableType = None
        self.currentHref = self.setWhereToCreate(obj)
        obj = utils.objectById(self.currentHref)
        
        if hasattr(obj, 'createSequence'):
            self.ui.objectCombo.addItem('Sequence', 'seq')
            disableType = True
        if hasattr(obj, 'createShot'):
            if objectType in ['Project', 'Sequence']:
                self.ui.objectCombo.addItem('Shot', 'shot')
                disableType = True
        if hasattr(obj, 'createTask'):
            self.ui.objectCombo.addItem('Task', 'task')
        
        ftTaskTypes = ftrack.getTaskTypes()
        for ftTaskType in ftTaskTypes:
            self.ui.typeCombo.addItem(ftTaskType.getName(), ftTaskType.getEntityRef())
        
        QtCore.QObject.connect(self.ui.createButton, QtCore.SIGNAL("clicked()"), self.accept)
        QtCore.QObject.connect(self.ui.cancelButton, QtCore.SIGNAL("clicked()"), self.reject)
        
        if disableType:
            self.ui.typeCombo.setEnabled(False)
            self.ui.typeLbl.setEnabled(False)
        
    def getName(self):
        return self.ui.nameLine.text()
    
    def getObject(self):
        currentIndex = self.ui.objectCombo.currentIndex()
        return self.ui.objectCombo.itemData(currentIndex)
    
    def getType(self):
        currentIndex = self.ui.typeCombo.currentIndex()
        return self.ui.typeCombo.itemData(currentIndex)
    
    def objectTypeChanged(self, currentIndex):
        itemData = self.ui.objectCombo.itemData(currentIndex)
        if itemData == 'task':
            self.ui.typeCombo.setEnabled(True)
            self.ui.typeLbl.setEnabled(True)
        else:
            self.ui.typeCombo.setEnabled(False)
            self.ui.typeLbl.setEnabled(False)
    
    def setWhereToCreate(self, obj):
        objectType = utils.objectType(obj)
        if objectType == 'Component':
            obj = obj.getVersion().getAsset().getParent()
        elif objectType == 'AssetVersion':
            obj = obj.getAsset().getParent()
        elif objectType == 'Asset':
            obj = obj.getParent()
        elif objectType == 'Task':
            obj = obj.getParent()
            
        return obj.getEntityRef()


class BrowserWidget(QtWidgets.QWidget):
    clickedIdSignal = QtCore.Signal(str, name='clickedIdSignal')
    
    def __init__(self, parent, specification, context):
        super(BrowserWidget, self).__init__(parent=parent)
        self.ui = Ui_Browser()
        self.ui.setupUi(self)
        
        # Hide bookmark options until they are implemented correctly
        self.ui.pushButton_3.hide()
        self.ui.pushButton_4.hide()
        self.ui.pushButton_2.hide()
        
        self._specification = specification
        self._context = context
        
        self.validSelection = False
        self.compFilter = None
        self.metaFilters = None
        
        self.showAssets = True
        self.showTasks = True
        self.showAssetVersions = True
        self.showShots = True
        self.shotsEnabled = True
        
        self.ui.assetTypeFilterCombo.hide()
        self.ui.filterLabel.hide()
        
        self.currentBrowsingId = None
        
        #self.populateBookmarks()
        
        
    def populateBookmarks(self):
        self.ui.bookmarkWidget.setRowCount(0)
        
        ftrackProjects = ftrack.getProjects()
        self.ui.bookmarkWidget.setRowCount(len(ftrackProjects))
        
        ftrackProjects = sorted(ftrackProjects, key=lambda x: utils.objectName(x).lower())
        
        for i in range(len(ftrackProjects)):
            tabItem = QtWidgets.QTableWidgetItem(ftrackProjects[i].getName())
            tabItem.setData(QtCore.Qt.UserRole, ftrackProjects[i].getEntityRef())
            
            icon1 = QtGui.QIcon()
            icon1.addPixmap(QtGui.QPixmap(":/PNG/home.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
            tabItem.setIcon(icon1)
            
            self.ui.bookmarkWidget.setItem(i,0, tabItem)
            
        self.updateMainWidget(ftrackProjects[0].getEntityRef())
            
    def bookmarkCellClicked(self, x, y):
        item = self.ui.bookmarkWidget.item(x,y)
        self.updateMainWidget(targetRef=item.data(QtCore.Qt.UserRole))
        
    def mainCellClicked(self, x, y):
        item = self.ui.mainWidget.item(x, y)
        flags = item.flags()
        if not (flags & QtCore.Qt.ItemIsEnabled):
            return
        
        self.updateMainWidget(targetRef=item.data(QtCore.Qt.UserRole))
        
    def versionCellClicked(self, x, y):
        item = self.ui.versionsWidget.item(x, y)
        self.updateMainWidget(targetRef=item.data(QtCore.Qt.UserRole))
        
    def componentCellClicked(self, x, y):
        item = self.ui.componentsWidget.item(x, y)
        self.updateMainWidget(targetRef=item.data(QtCore.Qt.UserRole))
        
    def levelUp(self):
        obj = utils.objectById(self.currentBrowsingId)
        if hasattr(obj, 'getParent'):
            parent = obj.getParent()
            self.updateMainWidget(parent.getEntityRef())
            
    def updateComponentsWidget(self, importableComponents=[]):
        self.ui.componentsWidget.setRowCount(0)
        self.ui.componentsWidget.setRowCount(len(importableComponents))
        numComps = len(importableComponents)
        for i in range(numComps):
            tabText = utils.objectName(importableComponents[i])   
            tabItem = QtWidgets.QTableWidgetItem(tabText)
            tabItem.setData(QtCore.Qt.UserRole, importableComponents[i].getEntityRef())          
            self.ui.componentsWidget.setItem(i, 0, tabItem) 
        self.ui.componentsWidget.setCurrentCell(0,0)
        self.updateMainWidget(importableComponents[0].getEntityRef())
            
    def updateVersionsWidget(self, assetObject):
        self.ui.versionsWidget.setRowCount(0)
        if self.compFilter:
            versions = assetObject.getVersions(componentNames=self.compFilter)
        else:
            versions = assetObject.getVersions()
            
        self.ui.versionsWidget.setRowCount(len(versions))
        self.ui.detailsWidget.updateDetails(assetObject.getEntityRef())
        numVersions = len(versions)
        for i in range(numVersions):
            j = numVersions - i - 1 
            tabText = utils.objectName(versions[j])   
            tabItem = QtWidgets.QTableWidgetItem(tabText)
            tabItem.setData(QtCore.Qt.UserRole, versions[j].getEntityRef())
            
            self.ui.versionsWidget.setItem(i, 0, tabItem)
        
        self.ui.versionsWidget.setCurrentCell(0,0)
        self.updateMainWidget(versions[-1].getEntityRef())
        
    def getCorrectIcon(self, obj):
        iconPath = None
        if isinstance(obj, ftrack.Project):
            iconPath = ":/PNG/home.png"
        elif isinstance(obj, ftrack.Task):
            objectType = obj.getObjectType()
            if objectType == 'Sequence':
                iconPath = ":/PNG/folder-open.png"
            elif objectType == 'Shot':
                iconPath = ":/PNG/movie.png"
            elif objectType == 'Task':
                iconPath = ":/PNG/signup.png"
            elif objectType == 'Asset Build':
                iconPath = ":/PNG/box.png"
            elif objectType == None:
                # Check for asset build id until getObjectType fixed
                if obj.get('object_typeid') == 'ab77c654-df17-11e2-b2f3-20c9d0831e59':
                    iconPath = ":/PNG/box.png"
        elif isinstance(obj, ftrack.Asset):
            iconPath = ":/PNG/layers.png"
        
        if iconPath:
            icon1 = QtGui.QIcon()
            icon1.addPixmap(QtGui.QPixmap(iconPath), QtGui.QIcon.Normal, QtGui.QIcon.Off)
            
            return icon1
        
        return None
        
        
    def updateMainWidget(self, targetRef):
        
        obj = utils.objectById(targetRef)
        self.ui.pathLineEdit.setText(utils.getPath(obj, slash=True, includeAssettype=True))
        self.currentBrowsingId = targetRef
        
        clickedObjectType = utils.objectType(obj)
        self.validSelection = self.isValid(clickedObjectType, obj)
        
        self.clickedIdSignal.emit(self.currentBrowsingId)
        
        self.ui.detailsWidget.updateDetails(self.currentBrowsingId)
        
        if hasattr(obj, 'getVersions'):
            if self.showAssetVersions == True:
                self.updateVersionsWidget(obj)
                self.ui.versionsWidget.show()
            return
        elif hasattr(obj, 'getComponents'):
            components = obj.getComponents()
            importableComponents = []
            self.ui.componentsWidget.hide()
            for comp in components:
                if self.compFilter:
                    if not comp in self.compFilter:
                        continue
                if self.metaFilters:
                    metaData = comp.getMeta()
                    # img_main to be replaced by settable option
                    for metaFilter in self.metaFilters:
                        if metaFilter in metaData:
                            importableComponents.append(comp)
                else:
                    importableComponents.append(comp)
            
            if len(importableComponents) > 1:
                self.updateComponentsWidget(importableComponents)
                self.ui.componentsWidget.show()
            elif len(importableComponents) == 1:
                self.updateMainWidget(importableComponents[0].getEntityRef())
            return
        elif clickedObjectType == 'Task':
            return
        elif isinstance(obj, ftrack.Component):
            return
        else:
            self.ui.versionsWidget.hide()
            self.ui.componentsWidget.hide()
        

        self.ui.mainWidget.setRowCount(0)
        self.ui.versionsWidget.setRowCount(0)
        
        self.ui.mainWidget.setHorizontalHeaderLabels([utils.objectName(obj)])
        
        children = []
        tasks = []
        assets = []
        
        if isinstance(obj, ftrack.Project) or isinstance(obj, ftrack.Task):
            children = obj.getChildren()
        
        if hasattr(obj, 'getTasks') and self.showTasks == True:
            tasks = obj.getTasks()
            
        if hasattr(obj, 'getAssets'):
            if not isinstance(obj, ftrack.Project) and obj.getObjectType() in ['Shot', 'Sequence'] and self.showAssets == True:
                if self.compFilter:
                    assets = obj.getAssets(componentNames=self.compFilter)
                else:
                    assets = obj.getAssets()
                        
            
        subobjects = children + tasks + assets
        subobjects = sorted(subobjects, key=lambda x: utils.objectName(x).lower())
        
        self.ui.mainWidget.setRowCount(len(subobjects))
        for i in range(len(subobjects)):
            makeBold = None
            makeItalic = None
            makeDisabled = None
            
            if isinstance(subobjects[i], ftrack.Task) and subobjects[i].getObjectType() in ['Shot', 'Sequence']:
                tabText = utils.objectName(subobjects[i]) + '/'
                makeBold = True
            elif isinstance(subobjects[i], ftrack.Task) and subobjects[i].getObjectType() in ['Task']:
                tabText = utils.objectName(subobjects[i])
                makeItalic = True        
                if isinstance(subobjects[i].getParent(), ftrack.Project):
                    makeDisabled = True
            elif isinstance(subobjects[i], ftrack.Asset):
                tabText = utils.objectName(subobjects[i]) + '.' + subobjects[i].getType().getShort()
            else:
                tabText = utils.objectName(subobjects[i])
                
            if clickedObjectType == 'Sequence' and self.shotsEnabled == False:
                makeDisabled = True
            
            tabItem = QtWidgets.QTableWidgetItem(tabText)
            
            tabItem.setData(QtCore.Qt.UserRole, subobjects[i].getEntityRef())
            
            icon = self.getCorrectIcon(subobjects[i])
            if icon:
                tabItem.setIcon(icon)
            
            if makeDisabled:
                tabItem.setFlags(QtCore.Qt.NoItemFlags)
            
            self.ui.mainWidget.setItem(i,0, tabItem)
            if makeBold:
                f = QtGui.QFont()
                f.setBold(True)
                self.ui.mainWidget.item(i,0).setFont(f)
            elif makeItalic:
                f = QtGui.QFont()
                f.setItalic(True)
                self.ui.mainWidget.item(i,0).setFont(f)
                
            
    def setShowAssets(self, val):
        self.showAssets = val

    def setShowTasks(self, val):
        self.showTasks = val

    def setShowAssetVersions(self, val):
        self.showAssetVersions = val

    def setShotsEnabled(self, val):
        self.shotsEnabled = val
        
    def setComponentFilter(self, val):
        self.compFilter = val
        
    def setMetaFilters(self, val):
        self.metaFilters = val
        
    def isValid(self, clickedObjectType, clickedTask):
        validSelection = False
        
        import FnAssetAPI
        isImage = isinstance(self._specification, FnAssetAPI.specifications.ImageSpecification)
        isFile = isinstance(self._specification, FnAssetAPI.specifications.FileSpecification)
        isShot = isinstance(self._specification, FnAssetAPI.specifications.ShotSpecification)
        if isShot:
            if self._context.access in ['write', 'writeMultiple']:
                if clickedObjectType in ['Sequence']:
                    validSelection = True
            elif self._context.access in ['read', 'readMultiple']:
                if clickedObjectType in ['Sequence']:
                    validSelection = True
        elif isImage or isFile or self._specification.getType() == "file.hrox":
            if clickedObjectType in ['Task']:
                if self._context.access in ['write', 'writeMultiple']:
                    parentEntity = clickedTask.getParent().get('entityType')
                    if parentEntity != 'show':
                        validSelection = True
            elif clickedObjectType in ['Sequence', 'Shot']:
                if self._context.access in ['write', 'writeMultiple']:
                    validSelection = True
            elif isinstance(clickedTask, ftrack.Asset):
                if self._context.access in ['write']:
                    validSelection = True

            if self._context.access in ['read', 'readMultiple']:
                if isinstance(clickedTask, ftrack.Asset) or isinstance(clickedTask, ftrack.AssetVersion) or isinstance(clickedTask, ftrack.Component):
                    validSelection = True
                    
            if self._context and self._context.locale and self._context.locale.getType().startswith("ftrack.publish"):
                if clickedObjectType != 'Task':
                    validSelection = False
                else:
                    validSelection = True
                
                
        return validSelection
    
    def setStartLocation(self, startTargetHref):
        try:
            obj = utils.objectById(startTargetHref)
        except InvalidEntityReference:
            import traceback
            tb = traceback.format_exc()
            FnAssetAPI.logging.debug(tb)
            return
        targetHref = None
        if isinstance(obj, ftrack.Component):
#            targetHref = obj.getVersion().get('taskid')
 #           if not targetHref:
            targetHref = obj.getVersion().getAsset().getParent().getEntityRef()               
        elif isinstance(obj, ftrack.Task):
            if obj.getObjectType() == 'Task':
                targetHref = obj.getParent().getEntityRef()
            else:
                targetHref = obj.getEntityRef()
     
        if targetHref:        
            self.updateMainWidget(targetHref)
            obj = utils.objectById(targetHref)
            clickedObjectType = utils.objectType(obj)
            self.validSelection = self.isValid(clickedObjectType, obj)
            self.clickedIdSignal.emit(self.currentBrowsingId)
                
    def showCreateDialog(self):
        createDialog = CreateDialog(self, currentHref=self.currentBrowsingId)
        res = createDialog.exec_()
        if res == 1:
            obj = utils.objectById(createDialog.currentHref)
            objToCreate = createDialog.getObject()
            objName = createDialog.getName()
            
            if objToCreate == 'seq':
                obj.createSequence(name=objName)
            elif objToCreate == 'shot':
                obj.createShot(name=objName)
            elif objToCreate == 'task':
                taskType = ftrack.TaskType(createDialog.getType())
                obj.createTask(name=objName, taskType=taskType)
            
            self.updateMainWidget(obj.getEntityRef())
    
    
    # setSelection currently only supports Components in write mode 
    # which should be the only case
    def setSelection(self, selection):
        if len(selection)>0 and selection[0]!='':
            if len(selection)>1:
                import FnAssetAPI
                FnAssetAPI.logging.debug("Multi selection not yet supported")
            selection = selection[0]
            if self._context.access in ['write', 'writeMultiple']:
                try:
                    obj = utils.objectById(selection)
                    if isinstance(obj, ftrack.Component):
                        asset = obj.getVersion().getAsset()
                        assetId = asset.getEntityRef()
                        #shotId = asset.getParent().getEntityRef()
                        
                        rowCount = self.ui.mainWidget.rowCount()
                        for i in range(rowCount):
                            item = self.ui.mainWidget.item(i, 0)      
                            targetRef = item.data(QtCore.Qt.UserRole)
                            
                            if targetRef == assetId:
                                self.updateMainWidget(targetRef)
                                self.ui.mainWidget.setCurrentCell(i,0)
                except InvalidEntityReference:
                    import traceback
                    tb = traceback.format_exc()
                    FnAssetAPI.logging.debug(tb)
        else:
            import FnAssetAPI
            FnAssetAPI.logging.debug("Could not setSelection")
