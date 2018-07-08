# :coding: utf-8
# :copyright: Copyright (c) 2013 ftrack

from __future__ import with_statement
import urllib

#Make sure imports are not included in doxygen
#@cond
#
#
import os
import functools
import tempfile
from xmlserver import XMLServer

global xmlServer
from ftrackerror import FTrackError
from ftrackerror import LocationError
from ftobject import FTObject, Metable
from ftlist import FTList
from . import cache
from group import Group, getGroups


if 'FTRACK_SERVER' in os.environ:
    xmlServer = XMLServer(os.environ['FTRACK_SERVER'] + "/client/",False)
else:
    raise FTrackError('Environment variable FTRACK_SERVER was not found....')





FTObject.xmlServer = xmlServer

def getNumMessages():
    data = {'type':'nummessages'}
    response = xmlServer.action('get',data)
    return response['messages']



def getShowFromPath(path):
    return getFromPath(path)
    
def getSequenceFromPath(path):
    return getFromPath(path)

def getShotFromPath(path):
    return getFromPath(path)

class ListObject(FTObject):
    _type = 'listobject'
    
    def getId(self):
        return self.get('id')

itemsToCreate = []

def suspendCreate():
    xmlServer.startBatch()
    
def resumeCreate():
    xmlServer.endBatch()


def enableGetCache():
    '''Enable caching of 'get' calls.'''
    xmlServer.enableGetCache()


def disableGetCache():
    '''Disable caching of 'get' calls.'''
    xmlServer.disableGetCache()


def clearGetCache():
    '''Clear any data stored in 'get' cache.'''
    xmlServer.clearGetCache()


def withGetCache(function):
    '''Decorate *function* to use xmlserver get cache for duration of call.'''

    @functools.wraps(function)
    def wrapper(*args, **kw):
        enableGetCache()
        try:
            result = function(*args, **kw)
        finally:
            disableGetCache()

        return result

    return wrapper


#@endcond

NOT_STARTED = 'NOT_STARTED'
IN_PROGRESS = 'IN_PROGRESS'
DONE = 'DONE'
BLOCKED = 'BLOCKED'


def getDiagnostics():
    data = {'type':'diagnostics'}
    response = xmlServer.action('get',data)
    return response

def resetDebug():
    """
    Reset the debug data
    """      
    xmlServer.resetDebug()

def printDebug():
    """
    Print debug information for this ftrack session. Includes number of requests and time spent during requests.
    """    
    print "### DEBUG ####################################"
    totalTime = xmlServer.getTotalTime()
    requests = xmlServer.getTotalRequests()
    print "Total time: " + str(round(float(totalTime),2))
    print "Requests: " + str(requests)
    print "Requests/Second: " + str(requests/totalTime)
    print "Seconds/Request: " + str(totalTime/requests)
    print "##############################################"


class Review(object):
    '''A utility class that contains functions used by ftrackreview.

    Example of adding reviewable components to a version:

    .. code-block:: python

        import ftrack

        # Get a shot and a task on the shot
        shot = ftrack.getShot(['project', 'seq', 'shot'])
        task = shot.getTasks().pop()

        # Create an asset to publish a new reviewable version
        asset = shot.createAsset(
            name='compositing', assetType='comp', task=task
        )

        # Create a new version
        version = asset.createVersion(comment='Made som changes to the helmet')

        # Set the path to the file that should be attached to the version
        filePath = '/Users/carlclaesson/Documents/data/helmet.mov'

        # Make the version reviewable by using the util function
        # ftrack.Review.makeReviewable(). This will create an original
        # component and move it to the ``ftrack.server`` location and trigger
        # encoding.
        ftrack.Review.makeReviewable(version, filePath)

        version.publish()

    '''

    @staticmethod
    def encodeComponent(component):
        '''
        Create reviewable components from a given component.
        The component file needs to be a valid s3 key.

        :param component: ``Component`` to convert
        '''

        data = {
            'type': 'review.convertComponent',
            'entityId': component.getId()
        }

        xmlServer.action('get', data)

    @staticmethod
    def makeReviewable(version=None, filePath=None):
        '''Add web reviewable compoment to *version* based on *filePath*.'''
        import uuid
        # Inline to avoid circular import.
        from .. import LOCATION_PLUGINS

        location = LOCATION_PLUGINS.get('ftrack.server')

        if not location:
            raise LocationError(
                'Required "ftrack.server" location not found.'
            )

        component = version.createComponent(
            name=str(uuid.uuid1()),
            path=filePath,
            location=location
        )

        Review.encodeComponent(component)


class HasManagers(object):
    '''Mixin for creating and retrieving managers.'''

    def getManagers(self):
        '''Return all managers assigned to this entity.'''
        data = {
            'type': 'managers',
            'entityId': self.getId(),
            'entityType': self._type
        }
        response = xmlServer.action('get', data)
        return FTList(Manager, response)

    def createManager(self, user, managerType):
        '''Create a manager from *user* and *managerType* for this entity.

        *user* should be a :py:class:`~ftrack.User` instance.

        *managerType* should be a :py:class:`~ftrack.ManagerType` instance.

        '''
        data = {
            'type': 'manager',
            'entityId': self.getId(),
            'entityType': self._type,
            'userId': user,
            'managerTypeId': managerType
        }
        response = xmlServer.action('create', data)
        return Manager(dict=response)


class WebWidgetable(object):

    def getWebWidgetUrl(self, name, theme='dark'):
        '''Return url that can be used is a qt webwidget.

        *name* should be the name of the ftrack panel. *theme* is optional.

        '''
        return getWebWidgetUrl(
            name=name, theme=theme, entityId=self.getId(), entityType=self._type
        )

    def getURL(self):
        '''Return url that can be used to view this entity in a browser.'''
        data = {
            'type': 'entityurl',
            'entityType': self._type,
            'entityId': self.getId()
        }
        response = xmlServer.action('get', data)
        absoluteUrl = os.environ['FTRACK_SERVER'] + response
        return absoluteUrl


class Timereportable(object):
    '''Mixin for timelogging.'''

    def getTimelogs(self, start=None, end=None, includeChildren=False):
        '''Return timelogs between *start* and *end* dates.

        If *includeChildren* is set, also return timelogs on descendants.
        '''
        # Local import to avoid circular.
        from timelog import _getTimelogs

        return _getTimelogs(
            entityId=self.getId(),
            entityType=self._type,
            start=start,
            end=end,
            includeChildren=includeChildren
        )


class SequenceLegacy(object):
    def getShots(self):
        """
        Get attached Shots
        
        :rtype: FTList of Shot
        """
        return self.getChildren()

    def getShow(self):
        """
        @deprecated  Use getParent instead
        """        
        return self.getParent()

    # def createShot(self,name):
    #     """
    #     Create a shot
        
    #     :param name: a ``str`` with the name of this shot
    #     :rtype: ``Shot``
    #     """        
    #     data = {'type':'shot','sequenceid':self.getId(),'name':name}
    #     response = xmlServer.action('create',data)
    #     return Task(dict=response)          
             
class ShotLegacy(object):
    def getFrameStart(self):
            return self.get('fstart')
    
    def getFrameEnd(self):
            return self.get('fend')
            
    def getFPS(self):
            return self.get('fps')

    def getSequence(self):
        """
        @deprecated  Use getParent instead
        """        
        if 'sequence' in self.dict:
            return Sequence(dict=self.dict['sequence'])
        else:
            return Sequence(id=self.get('parent_id'))

class Parentable(object):
    
    def getParent(self):
        """
        Get parent object from this object
        
        :rtype:  ``FTObject`` of that type
        """
        data = {'type':'parent','entityId':self.getId(),'entityType':self._type}
        response = xmlServer.action('get',data)
        #print response
        entityType = response.get('entityType').replace("_","")
        #find class of parent
        
        classes = FTObject.__subclasses__()
        for c in classes:
            
            if c._type.replace("_","") == entityType:
                return c(dict=response)
            
        raise FTrackError('Parent was not found....')

    def getParents(self):
        """
        Get parent object from this object
        
        :rtype:  ``list`` owith items of that type
        """
        data = {'type':'parents','entityId':self.getId(),'entityType':self._type}
        response = xmlServer.action('get',data)
        entities = response
        
        #find class of parent
        classes = FTObject.__subclasses__()
        parents = []
        for entity in entities:
            for c in classes:
                
                if c._type.replace("_","") == entity.get('entityType').replace("_",""):
                    parents.append(c(dict=entity))
            
        return parents


class Statusable(object):
    def setStatus(self,status):
        """
        Set status of the object
        
        :param status: ``Status`` the status object that should be set
        """          
        return self.set('statusid',status.get('statusid'))

    def getStatus(self):
        '''Return the status of the object or None if it has no status.'''
        statusId = self.get('statusid')
        if statusId:
            return Status(id=statusId)
        else:
            return None


class Noteable(object):

    def createNote(self, note, category='auto', recipients=None):
        '''Create note with text *note*.

        Optional *category* can be specified to set the note category of the
        note. Can be either :py:class:`~ftrack.NoteCategory` or category id.
        If set to `auto` the default note category setting will be used.

        Recipients can be specified by setting *recipients* to be a list of
        :py:class:`~ftrack.User` or user ids.
        '''

        data = {
            'type': 'note',
            'parent_type': self._type,
            'parent_id': self.getId(),
            'note': note,
            'categoryid': category,
            'recipients': recipients
        }
        response = xmlServer.action('create', data)
        return Note(id=response['id'])

    def getDefaultRecipients(self):
        """
        Get default recipients for an object
        
        :rtype: ``list`` with User objects
        """        
        data = {'type':'defaultrecipients','entityType':self._type,'entityId':self.getId()}
        response = xmlServer.action('get',data)
        return FTList(User,response)

    def getNotes(self):
        """
        Fetch notes from an entity, this will include replies.
        """        
        data = {'type':'notes','entityId':self.getId(),'entityType':self._type}
        response = xmlServer.action('get',data)
        
        notes = FTList()
        for row in response:
            notes.append(Note(dict=row))
        return notes


class Assetable(object):
    '''Mixin to make a class assetable.'''

    def createAsset(self, name, assetType, task=None):
        '''Create a new asset or return existing.

        *name* is the name of the asset and *assetType* is the type of the
        asset defined by its short name. A *task* or task id can also be passed
        in which will be used as the default task when versions are created on
        this asset.

        '''

        data = {
            'type': 'asset',
            'parent_id': self.getId(),
            'parent_type': self._type,
            'name': name,
            'assetType': assetType,
            'taskid': task
        }
        response = xmlServer.action('create', data)

        return Asset(dict=response)

    def createAttachment(self, file, fileName=None, isThumb=False):
        '''Legacy method to attach files to objects.'''
        # Built-in asset type representing uploads.
        ASSET_TYPE_ID = '8f4144e0-a8e6-11e2-9e96-0800200c9a66'

        component = _createAttachment(file, fileName)

        if self.get('objecttypename') in ('Task', 'Milestone'):
            parent = self.getParent()
            asset = parent.createAsset(
                component.get('name'), ASSET_TYPE_ID, task=self
            )
        else:
            asset = self.createAsset(component.get('name'), ASSET_TYPE_ID)

        version = asset.createVersion()
        component.set('version_id', version.getId())
        version.publish()

        return component


def _createAttachment(file, fileName):
    '''Create and return a component from *file*.'''
    # Local import to avoid circular import.
    from .component import createComponent
    from location import ensureLocation

    # Check if its a file object and write to temporary file.
    if hasattr(file, 'read'):
        path = os.path.join(tempfile.gettempdir(), fileName)
        with open(path, 'wb') as temporaryFile:
            temporaryFile.write(file.read())
    else:
        path = file

    fileName, fileExtension = os.path.splitext(os.path.basename(path))

    component = createComponent(
        name=fileName,
        path=path,
        location=ensureLocation('ftrack.server')
    )

    return component


class Thumbnailable(object):
    '''Mixin to add support for thumbnails.'''

    def createThumbnail(self, file, fileName="image.jpg"):
        '''Create thumbnail from *file*.'''
        component = _createAttachment(file, fileName)
        self.setThumbnail(component)

        # If self is a version then add the thumbnail component to it.
        if isinstance(self, AssetVersion):
            component.set('version_id', self.getId())

        return component

    def setThumbnail(self, component):
        '''Set *component* as thumbnail.'''
        self.set('thumbid', component.getId())

    def getThumbnail(self):
        '''Get a url to the thumbnail.'''
        componentId = self.get('thumbid')
        if not componentId:
            return None

        params = urllib.urlencode({
            'id': componentId,
            'username': os.environ.get('LOGNAME', 'nouser'),
            'apiKey': os.environ.get('FTRACK_APIKEY', 'no-key-found')
        })
        url = '{baseUrl}/component/thumbnail?{params}'.format(
            baseUrl=os.environ['FTRACK_SERVER'], params=params
        )

        return url


class Dependable(object):
    
    def getPredecessors(self):
        """
        Returns a list of items that this item depends on
        
        :rtype: ``list``
        """           
        data = {'type':'predecessors','id':self.getId()}
        response = xmlServer.action('get',data)
        return FTList([Task],response)
    
    def getSuccessors(self):
        """
        Returns a list of items that depend on this object
        
        :rtype: ``list``
        """              
        data = {'type':'successors','id':self.getId()}
        response = xmlServer.action('get',data)
        return FTList([Task],response)

    def _addDependency(self,fromTask,toTask):
        data = {'type':'dependency','fromid':fromTask,'toid':toTask}
        response = xmlServer.action('create',data)
        return True

    def _removeDependency(self,fromTask,toTask):
        data = {'type':'removedependency','fromid':fromTask,'toid':toTask}
        response = xmlServer.action('set',data)
        return True

    def addSuccessor(self,task):
        """
        Add a dependency from this task to another task
        
        :param task: The successor task
        """    
        return self._addDependency(self,task)

    def addPredecessor(self,task):
        """
        Add a dependency from another task to this task
        
        :param task: The predecessor task
        """    
        return self._addDependency(task,self)
    
    def removeSuccessor(self,task):
        """
        remove a dependency from this task to another task
        
        :param task: The successor task
        """    
        return self._removeDependency(self,task)

    def removePredecessor(self,task):
        """
        remove a dependency another task to this task
        
        :param task: The predecessor task
        """    
        return self._removeDependency(task,self)


class BaseObject(object):
    '''Mixin representing a context.'''

    def create(self, objectType, name, statusId=None, typeId=None,
                priorityId=None):
        '''Create a context from *objectType* with *name*.'''
        response = xmlServer.action('create', {
            'type': 'context',
            'objectType': objectType,
            'name': name,
            'parent_id': self.getId(),
            'parent_type': self._type,
            'statusId': statusId,
            'typeId': typeId,
            'priorityId': priorityId
        })

        return Task(dict=response)

    def getChildren(self,objectType=None,depth=1):
        """
        Get attached Children (not tasks)
        
        :rtype: FTList of Children
        """

        if objectType == 'Asset Build':
            depth = None

        data = {'type':'getchildren','entityId':self.getId(),'entityType':self._type,'objectType':objectType,'depth':depth}
        response = xmlServer.action('get',data)
        return FTList(Task,response)
    
    def getSequences(self):
        """
        Get attached Sequences
        
        :rtype: FTList of Sequence
        """
        return self.getChildren('Sequence')

    def getShots(self):
        return self.getChildren('Shot')

    def getEpisodes(self):
        return self.getChildren('Episode')

    def createEpisode(self, name):
        '''Create an episode from *name*.'''
        return self.create('Episode', name)

    def createSequence(self, name):
        '''Create a sequence from *name*.'''
        return self.create('Sequence', name)

    def createShot(self, name):
        '''Create a shot from *name*.'''
        return self.create('Shot', name)

    def createTask(self, name, taskType=None, taskStatus=None):
        '''Create a task from *name*, *taskType* and *taskStatus*.'''
        return self.create('Task', name, typeId=taskType, statusId=taskStatus)

    def getTasks(self, *args, **argv):
        """
        Get attached Tasks

        :param users:  ``list`` with usernames like ['username1','username2'] to filter out tasks
        :param taskTypes: ``list`` representing task types. Can be ``TaskType`` objects, their IDs or their names.  
        :param taskStatuses: ``list`` representing task statuses. Can be ``TaskStatus`` objects, their IDs or their names.
        :param states: ``list`` with states. Possible states are NOT_STARTED, IN_PROGRESS, DONE, BLOCKED which are availible from the ftrack module
        :param activeProjectsOnly: ``bool`` Default to ``True``. specifying if only to query active projects.
        :param includeChildren: ``bool`` Default to ``False``. childrens tasks should be included.
        :param includePath: ``bool`` Default to ``False``. specifying if the path should be added to each task. Much faster than useing getParents on each task afterwards.

        :rtype: ``FTList`` with ``Task``
        """
        return _getTasks(parent=self, *args, **argv)



def syncUsers():
    """
    Sync users from external service such as ldap
    """    
    response = xmlServer.action('get',{'type':'syncusers'})
    return response

def getUUID():
    """
    Retrived a unique id from the server. Same type of id as is used for objects (uuid)
    
    :rtype: ``str``
    """       
    data = {'type':'uuid'}
    response = xmlServer.action('get',data)
    return response['uuid']


def _getAttachmentUrl(componentId):
    '''Return authenticated URL to attachment component with *componentId*'''
    if not componentId:
        return None

    params = urllib.urlencode({
        'id': componentId,
        'username': os.environ.get('LOGNAME', 'nouser'),
        'apiKey': os.environ.get('FTRACK_APIKEY', 'no-key-found')
    })
    url = '{baseUrl}/component/get?{params}'.format(
        baseUrl=os.environ['FTRACK_SERVER'], params=params
    )
    return url


def _getAssets(parent,names=None,assetTypes=None,includeChildren=False,componentNames=None,excludeWithTasks=False):
    data = {'type':'assets','id':parent.getId(),'parent':parent._type,'assettypes':assetTypes,'includechildren':includeChildren,'names':names,'componentNames':componentNames,'excludeWithTasks':excludeWithTasks}
    response = xmlServer.action('get',data)
    return FTList(Asset,response)

def _getTasks(parent,users=[],taskTypes=[],taskStatuses=[],states=[], activeProjectsOnly=True, includeChildren=False, includePath=False, projects=None):
    response = []
    if ('tasks' in parent.dict and len(users) == 0 and len(taskTypes) == 0):
        response = parent.dict['tasks']
    else:
        data = {'type':'tasks','id':parent.getId(),'parent':parent._type,'users':users,'tasktypes':taskTypes,'taskstatuses':taskStatuses,'states':states,'activeProjectsOnly':activeProjectsOnly, 'includeChildren':includeChildren, 'includePath' : includePath,'projects':projects}
        response = xmlServer.action('get',data)
    return FTList(Task,response)


def getActivityEvents(projectId=None,fromEventId=0,fromDate=None,actions=None,preloadObjects=False,limit=100):
    """
    Get ActivityEvents
    :param projectId: ``str`` id of the project
    :param fromEventId: ``str`` incremental id of the events
    :param fromDate: ``datetime`` id of the project
    :param actions: ``str`` id of the project
    :param preloadObjects: ``bool`` include object in each event. Defaults to False, if False objects are fetched on request, if True objects and included in event query to minimize number of total requests.
    :param limit: ``int`` limit number of events, default is 100
    :rtype: list of Events
    """   
    import datetime
    if fromDate != None and not isinstance(fromDate,datetime.datetime):
        raise FTrackError('fromDate must be datetime object or None....')
     
    data = {'type':'events','projectId':projectId,'fromEventId':fromEventId,'fromDate':fromDate,'actions':actions,'limit':limit,'preloadObjects':preloadObjects}
    response = xmlServer.action('get',data)
    return FTList(ActivityEvent, response)

#db operations
def desc(on):
    return {'on':on,'dir':'desc'}    

def asc(on):
    return {'on':on,'dir':'asc'}  

def filter_by(arg=None,**args):
    if arg != None:
        return {'filter_by':arg}
    
    return {'filter_by':args}

def limit(limit):
    return {'limit':limit}

def order_by(*args):
    return {'order_by' : list(args)}

def createAssetType(name,short):
    """
    Create an asset type
    :param name: ``str`` the nice name for this type
    :param short: ``str`` the shot name that will be used in scripts
    """       
    data = {'type':'assettype','name':name,'short':short}

    response = xmlServer.action('create',data)
    return AssetType(dict=response)


def getProjectSchemes():
    """
    Get all project schemas. Project schemas define types and statuses that should be used
    
    :rtype: ``list`` with ``ProjectScheme``
    """       
    data = {'type':'projectschemes'}

    response = xmlServer.action('get',data)
    return FTList(ProjectScheme,response)

def createProject(fullname,name,workflow):
    """
    Create a project
    
    :param fullname: ``str`` the long name of the project
    :param name: ``str`` the shot name that will be used in scripts
    :param workflow: ``ProjectScheme`` the project scheme that should be used in this project. Defines types and statuses.
    :rtype: ``Project``
    """    
    data = {'type':'show','projectschemeid':workflow.getId(),'fullname':fullname,'name':name}
    response = xmlServer.action('create',data)
    return Show(dict=response)

def getProjects(includeHidden=False):
    """
    Get all projects
     
    :rtype: ``list`` with ``Project``
    """
    data = {'type':'shows','includeHidden':includeHidden}

    shows = xmlServer.action('get',data)
    return FTList(Show,shows)


def getUser(username):
    """
    Get a user
    :param username: ``str`` the username of the user
    :rtype: ``User``
    """
    
    try:
        return User(username)
    except FTrackError:
        pass
    
    return None

def getUsers():
    """
    Get all users
     
    :rtype: ``list`` with ``User``
    """
    data = {'type':'allusers'}

    users = xmlServer.action('get',data)
    return FTList(User,users)

def _getFromPath(path):
    data = {'type':'frompath','path':path}
    return xmlServer.action('get',data)


def getProject(path):
    """
    Get a ``Project``` from a path
    
    :param path: A ``list`` with strings representing the path to the ``Project``.
    :type path: list   
    :rtype: ``Project``
    """  
    return getFromPath(path)

def getSequence(path):
    """
    Get a ``Sequence``` from a path
    
    :param path: A ``list`` with strings representing the path to the ``Sequence``.
    :type path: list   
    :rtype: ``Sequence``
    """   
    return getFromPath(path)

def getShot(path):
    """
    Get a shot from a path
    
    :param path: A ``list`` with strings representing the path to the ``Shot``.
    :type path: list   
    :rtype: ``Shot``
    """  
      
    return getFromPath(path)

def getFromPath(path):
    data = _getFromPath(path)

    if data.get('entityType') == 'show':
        return Project(dict=data)
    
    elif data.get('entityType') == 'task':
        return Task(dict=data)

    raise FTrackError('Invalid path')

def getPriorities():
    """
    Get Priority
    
    :rtype: FTList of Priority
    """
    data = {'type':'getobjects','id':'PriorityType','sort':{'attribute':'sort','direction':'desc'}}

    items = xmlServer.action('get',data)
    return FTList(Priority,items)

def getAssetTypes():
    """
    Get AssetTypes
    
    :rtype: FTList of AssetTypes
    """
    data = {'type':'assettypes'}

    assetTypes = xmlServer.action('get',data)
    return FTList(AssetType,assetTypes)

def getTaskTypes():
    """
    Get TaskTypes
    
    :rtype: FTList of TaskTypes
    """
    data = {'type':'tasktypes'}

    response = xmlServer.action('get',data)
    return FTList(TaskType,response)

def getTaskStatuses():
    """
    Get TaskStatus
    
    :rtype: FTList of TaskStatus
    """
    data = {'type':'taskstatuses'}

    response = xmlServer.action('get',data)
    return FTList(TaskStatus,response)

def getNoteCategories():
    """
    Get NoteCategories
    
    :rtype: FTList of NoteCategory
    """
    data = {'type':'notecategories'}

    response = xmlServer.action('get',data)
    return FTList(NoteCategory,response)

def getListCategories():
    """
    Get ListCategories
    
    :rtype: FTList of ListCategory
    """
    data = {'type':'listcategories'}

    response = xmlServer.action('get',data)
    return FTList(ListCategory,response)

def getDisks():
    """
    Get Disks
    
    :rtype: FTList of Disk
    """
    data = {'type':'disks'}

    response = xmlServer.action('get',data)
    return FTList(Disk,response)


@cache.memoise
def getAssetPathPrefix():
    '''Return asset path prefix.'''
    data = {'type': 'assetpathprefix'}
    response = xmlServer.action('get', data)
    return response['assetpathprefix']


def safeURL(url):
    """
    Converts a string to one that is safe to use in a filename
    
    :param url: A ``str``.
    :rtype: string
    """
    import re
    url = url.replace(" ","_")
    return re.sub('[^a-zA-Z0-9_-.()]+', '', url)


def getWebWidgetUrl(name, theme='dark', entityId=None, entityType=None):
    '''Return URL to web widget with *name* for *entityId* and *entityType*

    *theme* is optional and can be specifed to set which theme the widget
    should use.

    '''
    data = {
        'type': 'webwidgeturl',
        'name': name,
        'theme': theme
    }

    if entityId and entityType:
        data.update({
            'entityType': entityType,
            'entityId': entityId
        })

    response = xmlServer.action('get', data)
    absoluteUrl = os.environ['FTRACK_SERVER'] + response
    return absoluteUrl


class Project(FTObject, Noteable, Thumbnailable, Metable,
              Timereportable, WebWidgetable, BaseObject, HasManagers,
              Assetable):
    """
    Used to get data from a project or its children
    @param  id  show id
    """
    _type = 'show'
    _idkey = 'showid'
    
    def getAssets(self,assetTypes=None,includeChildren=False, componentNames=None, excludeWithTasks=False):
        """
        Get attached Assets
        
        :param names: A ``list`` with names of the assets
        :param assetTypes: A ``list`` with names of the asset types or short names of the asset types or asset type ids
        :param componentNames: A ``list`` with names of components that the versions must have at least one of
        :param excludeWithTasks: A ``bool`` which defaults to False, can be used to get assets with versions that are not connected to any tasks
        
        :rtype: FTList of Asset
        """
        return _getAssets(parent=self,assetTypes=assetTypes,includeChildren=includeChildren,componentNames=componentNames,excludeWithTasks=excludeWithTasks)

    def getFPS(self):
        return self.get('fps')
        
    def getRoot(self):
        return self.getPath()

    def getPath(self,full=False):
        """
        Get OS specific path to project folder
        
        :param full: ``bool`` Include asset prefix setting at end of path
        :rtype: A string with the file path to the project
        """          
        data = {'type':'path','showid':self.getId(),'full':full}
        response = xmlServer.action('get',data)
        return response
            
    def getName(self):
        return self.get('name')
        
    def getFullName(self):
        return self.get('fullname')
        
    def getId(self):
        return self.get("showid")

    def createAssetBuild(self, name, typeid=None):
        '''Create an asset build from *name* and *typeid*.'''
        return self.create('Asset build', name, typeId=typeid)

    def getAssetBuilds(self):
        return self.getChildren('Asset Build')

    def getAssetBuildTypes(self):
        '''Return the asset build types valid for this project.'''
        response = xmlServer.action('getAssetBuildTypes', {
            'projectId': self.getId()
        })
        return FTList(TaskType, response)

    def getTaskTypes(self):
        """
        Get TaskStatus
        
        :rtype: FTList of TaskTypes
        """
        data = {'type':'tasktypes_fromshow','showid':self.getId()}

        response = xmlServer.action('get',data)
        return FTList(TaskType,response)

    def getStatuses(self, name):
        '''Return valid statuses for object of type *name*.'''
        data = {
            'type': 'objectstatuses',
            'name': name,
            'projectId': self.getId()
        }

        response = xmlServer.action('get',data)

        return FTList(Status,response)

    def getTaskStatuses(self,typeid=None):
        """
        Get TaskStatus that are defined by this projects workflow schema.
        
        :param typeid: Defaults to ``None``. The id or ``TaskType`` object. This should always be used since it makes sure the correct statuses are returned if there is an override in place for this type.
        :rtype: FTList of TaskStatus
        """
        
        if typeid and type(typeid).__name__ != 'str':
            typeid = typeid.getId()
        
        data = {'type':'taskstatuses_fromshow','showid':self.getId(),'typeid':typeid}

        response = xmlServer.action('get',data)
        return FTList(TaskStatus,response)
    

    def getVersionStatuses(self):
        """
        Get version statuses from project workflow scheme used by this project
     
        :rtype: FTList of ``VersionStatus``
        """
        data = {'type':'versionstatuses_fromshow','showid':self.getId()}

        response = xmlServer.action('get',data)
        return FTList(VersionStatus,response)

    def getList(self,name):
        """
        Returns a list by name
     
        :param name: Name of the list on this project. 
        :rtype: ``List``
        """        
        data = {'type':'listbyname','showid':self.getId(),'name':name}

        response = xmlServer.action('get',data)
        return List(dict=response)

    def getLists(self, name=None, categories=None):
        """
        Returns all lists for this project
     
        :param name: Used to match the names.  
        :param categories: list of ListCategory to use as filter. 

        :rtype: ``list``
        """        
        data = {'type':'lists','showid':self.getId(),'name':name,'categories':categories}

        response = xmlServer.action('get',data)
        return FTList(List,response)

    def createList(self,name,category,objectType=None):
        """
        Creates a list for this project
     
        :param name: A ``str`` with the name of the list
        :param category: A ``ListCategory`` object that defines the category for this list
        :param objectType: A ``ListCategory`` object that defines what this list should contain. This should be ``AssetVersion`` or None
        :rtype: ``List``
        """          
        entityType = 'task'
        if objectType:
            entityType = objectType._type
        
        data = {'type':'list','showid':self.getId(),'name':name,'categoryid':category.getId(),'entityType':entityType}
        response = xmlServer.action('create',data)
        return List(dict=response)

    def getUsers(self):
        data = {'type':'users','entityId':self.getId(),'entityType':self._type}
        response = xmlServer.action('get',data)
        return FTList(User,response)

    def getPhases(self):
        '''
        Return all phases for this project
        '''

        data = {'type':'phases','entityId':self.getId(),'entityType':self._type, 'showid':self.getId()}
        response = xmlServer.action('get',data)

        return FTList(Phase,response)

    def getBookings(self):
        '''
        Return all bookings for this project
        '''

        data = {'type':'bookings', 'entityId':self.getId(),'entityType':self._type}
        response = xmlServer.action('get',data)

        return FTList(Booking,response)

    def createPhase(self, description, startdate, enddate, color=None):
        ''' 
        Create a phase for this project 

        :param description: A ``str`` with the description of this phase
        :param startdate: A ``datetime`` with the start date of this phase
        :param enddate: A ``datetime`` with the end date of this phase
        :param color: A ``str`` with the color of this phase
        '''
        
        # TODO, support color and typeids

        data = {'type':'phase','projectid':self.getId(),'description': description,'startdate': startdate,'enddate': enddate, 'color' : color}
        response = xmlServer.action('create',data)
        return Phase(dict=response)

    def getAllocatedGroups(self):
        '''Return groups allocated on the project.'''
        response = xmlServer.action(
            'getAllocatedGroups', {'id': self.getId(), 'type': self._type}
        )

        return FTList(Group, response)

    def getAllocatedUsers(self):
        '''Return users allocated on the project.'''
        response = xmlServer.action(
            'getAllocatedUsers', {'id': self.getId(), 'type': self._type}
        )

        return FTList(User, response)

    def getReviewSessions(self):
        '''Return all review sessions on project.'''

        # Inline to avoid circular import.
        from . import review_session

        return review_session.getReviewSessions(self.getId())

    def createReviewSession(self, name, description):
        '''Create a new review session with *name* and *description*.'''

        # Inline to avoid circular import.
        from . import review_session

        return review_session.createReviewSession(
            name, description, self.getId()
        )


def getManagerTypes():
    '''Return a list of all manager types.'''
    response = xmlServer.action('get', {
        'type': 'managerTypes'
    })
    return FTList(ManagerType, response)


class Manager(FTObject):
    '''Represent managers for projects and entities.

    A manager is a :py:class:`~ftrack.User` associated with a
    :py:class:`~ftrack.ManagerType`. The manager is connected to an entity
    such as a project or sequence.

    '''

    _type = 'manager'
    _idkey = 'managerid'

    def getUser(self):
        '''Return the user for this manager.'''
        return User(self.get('userid'))

    def getType(self):
        '''Return the type for this manager.'''
        return ManagerType(self.get('typeid'))


class ManagerType(FTObject):
    '''Represent the type of a :py:class:`~ftrack.Manager`.

    Manager types can be created in :menuselection:`Settings --> Manager types`.
    A manager type has a name that can be used to fetch that type by passing it
    to the constructor. Examples of manager types are "supervisor" or
    "producer".

    '''

    _type = 'manager_type'
    _idkey = 'typeid'

    def getName(self):
        '''Return name of the manager type.'''
        return self.get('name')


class Booking(FTObject, Metable, Parentable):

    # Type of bookings 
    VACATION, PROJECT = ('vacation', 'project')

    _type = 'booking'
    _idkey = 'id'

    def getUser(self):
        '''
        Return the user for this booking
        '''
        data = {'type':'bookinguser','entityId':self.getId(),'entityType':self._type}
        response = xmlServer.action('get',data)

        return User(dict=response)

    def getProject(self):
        '''
        Return the project for this booking
        '''
        data = {'type':'bookingproject','entityId':self.getId(),'entityType':self._type}
        response = xmlServer.action('get',data)

        return Project(dict=response)

class Phase(FTObject, Metable, Parentable):


    _type = 'phase'
    _idkey = 'id'

    def assignUser(self, user):
        '''
        Assign a user to this phase

        :param user: A ``User`` to assign to this phase
        '''
        data = {'type':'assignuserphase','id':self.getId(),'userid':user.getId()}
        response = xmlServer.action('set',data)

    def unAssignUser(self, user):
        '''
        Un-assign a user to this phase

        :param user: Un-assign a ``User`` from this phase
        '''
        data = {'type':'unassignuserphase','id':self.getId(),'userid':user.getId()}
        response = xmlServer.action('set',data)

    def getUsers(self):
        '''
        Return all users assigned to this phase
        '''
        response = []
        if 'users' in self.dict:
            response = self.dict['users']
        else:
            data = {'type':'phaseusers','entityId':self.getId(),'entityType':self._type}
            response = xmlServer.action('get',data)
        return FTList(User,response)

    def addTaskType(self, taskType):
        '''Add *taskType* to the phase.'''
        xmlServer.action('addTaskTypeToPhase', {
            'phaseId': self.getId(),
            'typeId': taskType
        })

    def removeTaskType(self, taskType):
        '''Remove *taskType* from the phase.'''
        xmlServer.action('removeTaskTypeFromPhase', {
            'phaseId': self.getId(),
            'typeId': taskType
        })

    def getTaskTypes(self):
        '''Return task types for phase.'''
        response = xmlServer.action('getTaskTypesFromPhase', {
            'phaseId': self.getId()
        })
        return FTList(TaskType, response)


class Asset(FTObject,Metable,Parentable):
    _type = 'asset'
    _idkey = 'assetid'
    _newVersion = None
        
    def getVersions(self,*args,**argv):
        """
        Get AssetVersions
        
        :param componentNames: A ``list`` with names of components that the versions must have at least one of

        :rtype: FTList of AssetVersions
        """
        response = []
        if 'versions' in self.dict:
            response = self.dict['versions']
        else:
            data = {'type':'assetversions','id':self.get('assetid'),'parent':self._type,'args':args,'argv':argv}
            response = xmlServer.action('get',data)
        return FTList(AssetVersion,response)
        
    def createVersion(self,comment="",taskid=None):
        """
        Create an AssetVersion for publishing
        
        :param  comment:  'this is a comment'
        :param taskid:  'id-of-a-task'
        :rtype: AssetVersion
        """

        data = {'type':'assetversion','assetid':self.getId(),'taskid':taskid,'comment':comment}
        response = xmlServer.action('create',data)
        
        self._newVersion = AssetVersion(dict=response)
        
        return self._newVersion
        
    def publish(self):
        """
        Publish the asset together with its new version and components
        
        :rtype: bool
        """
        if self._newVersion != None:
            if (self._newVersion.newComponents != None 
                and len(self._newVersion.newComponents)
            ):
                data = {}
                data['type'] = 'asset'
                data['assetid'] = self.getId()
                data['versionid'] = self._newVersion.getId()
                data['components'] = []
                for component in self._newVersion.newComponents:
                    data['components'].append({
                        'id': component.getId()
                    })
                    
                response = xmlServer.action('commit', data)
                
                for component in self._newVersion.newComponents:
                    component.__init__(id=component.getId())
                
                return True
            
            response = xmlServer.action('commit', {
                'type': 'assetversion',
                'versionid': self._newVersion.getId()
            })
            
            return True

        #HACK - commit latest version?
        response = xmlServer.action('commit', {
            'type': 'latestversion',
            'assetid': self.getId()
        })
        
        return True

        return False
        
    def getName(self):
        return self.get('name')
        
    def getId(self):
        return self.get("assetid")

    def getType(self):
        return AssetType(self.get('typeid'))
    
class AssetVersion(FTObject,Statusable,Noteable,Thumbnailable,Metable,Parentable,WebWidgetable):
    _type = 'asset_version'
    _idkey = 'versionid'
    newComponents = None
    

    def publish(self):
        response = xmlServer.action('commit',{'type':'assetversion','versionid':self.getId()})
        return True

    def addUsesVersions(self,versions):
        """
        Add links to versions to inform that they are used by this version

        :param versions: A ``list`` with ``AssetVersion`` that should be linked to this version.
        :type versions: list
        """            
        ids = []
        
        if type(versions).__name__ != 'list':
            versions = [versions]
        
        for v in versions:
            if type(v).__name__ == 'str':
                ids.append(v)
            else:
                ids.append(v.getId())
        
        data = {'type':'versionlink','versionid':self.getId(),'ids':ids}
        response = xmlServer.action('create',data)
        return response
        
    def removeUsesVersions(self,versions):
        """
        Remove versions that are used in this version

        :param versions: A ``list`` with ``AssetVersion`` that should be un-linked from this version.
        :type versions: list
        """            
        ids = []
        
        if type(versions).__name__ != 'list':
            versions = [versions]
        
        for v in versions:
            if type(v).__name__ == 'str':
                ids.append(v)
            else:
                ids.append(v.getId())
        
        data = {'type':'versionunlink','versionid':self.getId(),'ids':ids}
        response = xmlServer.action('create',data)
        return response        
        
    def usesVersions(self):
        """
        Returns versions used in this version
        
        :rtype: ``list`` with ``AssetVersion``
        """           
        data = {'type':'usesversions','versionid':self.getId()}
    
        response = xmlServer.action('get',data)
        return FTList(AssetVersion,response)
    
        
    def usedInVersions(self):
        """
        Returns versions this version is used in
        
        :rtype: ``list`` with ``AssetVersion``
        """           
        data = {'type':'usedinversions','versionid':self.getId()}
    
        response = xmlServer.action('get',data)
        return FTList(AssetVersion,response)
    
    def getAsset(self):
        """
        Get the asset that this version belongs to
        
        :rtype: ``Asset``
        """           
        return Asset(id=self.get("assetid"))

    def getComponent(self, name='main', location='auto'):
        '''Return component with *name*.

        *location* can be set to specify the initial location the retrieved
        *component should be switched to. See :py:class:`~ftrack.Component` for
        more information on supported values for *location*.

        '''
        components = self.getComponents(location=location)
        
        for component in components:
            if component.get('name') == name:
                return component
            
        raise FTrackError('Component ({0}) was not found'.format(name))

    def getComponents(self, location='auto'):
        '''Return list of components attached to this asset version.
        
        *location* can be set to specify the initial location the retrieved
        *component should be switched to. See :py:class:`~ftrack.Component` for
        more information on supported values for *location*.
        
        '''
        if 'components' in self.dict:
            response = self.dict['components']
            
        else:
            data = {
                'type': 'components',
                'id': self.get('versionid'),
                'parent': self._type
            }
            
            response = xmlServer.action('get', data)

        # Local import to avoid circular import.
        from .component import Component
        from .location import pickLocations

        # Optimisation: Batch requests to reduce overhead. Remove this if a
        # lower level request batching optimisation is implemented.
        componentIds = [item['id'] for item in response]

        if location == 'auto':
            locations = pickLocations(componentIds)
        else:
            locations = [location] * len(componentIds)

        components = []
        componentsByLocation = {}

        for data, location in zip(response, locations):
            component = Component(dict=data, location=None)
            components.append(component)

            # Index component against location for batch adoption.
            componentsByLocation.setdefault(location, []).append(component)

        # Further optimisation by batch adopting all components in the same
        # location.
        for location, componentsInLocation in componentsByLocation.items():
            if location is not None:
                location.adoptComponents(componentsInLocation)

        result = FTList()
        result.extend(components)

        return result

    def createComponent(self, name='main', path='', systemType=None,
                        file=None, location='auto', manageData=None, size=None):
        '''Create a Component with *name*.

        The *name* property defaults to 'main' and needs to be unique for each
        version. Will raise :py:exc:`ftrack.FTrackError` if the name already
        exists.

        *path* can be a string representing a filesystem path to the data to use
        for the component. The *path* can also be specified as a sequence
        string, in which case a sequence component with child components for
        each item in the sequence will be created automatically. The accepted
        format for a sequence is '{head}{padding}{tail} [{ranges}]'. For
        example::

            '/path/to/file.%04d.ext [1-5, 7, 8, 10-20]'

        .. seealso::

            `Clique documentation <http://clique.readthedocs.org>`_

        If *location* is specified, then the created component will be
        automatically added to that location. The returned component will also
        be configured with that *location* set as its current location. It
        should be an instance of :py:class:`ftrack.Location`, the string 'auto'
        (default) or None.

        .. note::

            If *path* is not specified the *location* property will be ignored.

        If *location* is set to 'auto' the most suitable location will be
        selected and used. If no suitable location is found the component will
        be created without being added to a location.

        If *name* is set to be 'ftrackreview-mp4', 'ftrackreview-webm' or
        'ftrackreview-image' when 'auto' is specified the review location will
        be used.

        If the specified *location* is of type :py:class:`ftrack.Location`, it
        needs to be configured with a location plugin that is loaded in the
        current session. If the component fails to be added to the specified
        location, it will be removed and the underlying exception will be
        raised.

        .. note::

            If a *location* is not specified at component creation time then no
            path data will be stored in ftrack and the data not moved in any
            way. Instead, the returned component will be configured with a
            special 'origin' location allowing the component to be added to
            other locations manually using
            :py:meth:`ftrack.Location.addComponent`.

        If *manageData* is True then manage transfer of data to the location.
        If False, assume the data has been managed externally and just record
        the component as present in that location. If *manageData* is None, let
        the location decide if data should be managed.

        .. note::

            If no *location* is specified, *manageData* will be ignored.

        An optional *versionId* can be passed to specify the version entity that
        this component should be linked to.

        .. warning::

            A component cannot currently be attached to a version after
            creation.

        If *systemType* is not specified it will be inferred from the *path*.
        If no *path* set it will default to 'file'.

        *size* is the size of the component in bytes. *size* will be calculated 
        automatically from the path if not specified. If *size* is specified for 
        a sequence it will be stored for the sequence and for child components 
        as *size* / number of child components.

        *file* is a deprecated synonym for *path*. Please update code to use
        *path* in future.

        '''
        # Local import to avoid circular import.
        from .component import createComponent

        component = createComponent(
            name=name,
            path=path,
            versionId=self.getId(),
            systemType=systemType,
            file=file,
            location=location,
            manageData=manageData,
            size=size
        )

        if (self.newComponents is None):
            self.newComponents = []

        self.newComponents.append(component)

        return component

    def getId(self):
        return self.get("versionid")
        
    def getVersion(self):
        return self.get("version")

    def getOwner(self):
        if 'user' in self.dict:
            return User(dict=self.dict['user'])
        else:
            return User(id=self.get("userid"))

    def getUser(self):
        """
        Get the user that published this version
        
        :rtype: ``User``
        """            
        return self.getOwner()

    def getTask(self):
        """
        Get the task this version is connected to
        
        :rtype: ``Task``
        """            
        if 'task' in self.dict:
            return Task(dict=self.dict['task'])
        else:
            return Task(id=self.get("taskid"))

    def getDate(self):
        return self.get('date')

    def getComment(self):
        return self.get('comment')


class AssetType(FTObject):
    _type = 'assettype'

    def getName(self):
        return self.get('name')

    def getShort(self):
        return self.get('short')

    def getId(self):
        return self.get("typeid")


class Task(FTObject, Statusable, Noteable, Thumbnailable,
           Dependable, Metable, Parentable, Timereportable,
           SequenceLegacy, ShotLegacy, WebWidgetable, BaseObject, HasManagers,
           Assetable):
    _type = 'task'
    _idkey = 'taskid'
    _object_typeid = '11c137c0-ee7e-4f9c-91c5-8c77cec22b2c'

    def getAssetVersions(self):
        """
        Get AssetVersions
        
        :rtype: ``list`` of AssetVersions
        """
        response = []
        if 'assetVersions' in self.dict:
            response = self.dict['assetVersions']
        else:
            data = {'type':'assetversions','id':self.getId(),'parent':self._type}
            response = xmlServer.action('get',data)
        return FTList(AssetVersion,response)

    def getAsset(self,name, assetType):
        """
        Get an Asset
        
        :param name: ``str`` with the name of the asset
        :param assetType: a string with the asset type like 'geo'
        :rtype: ``Asset``
        """
        assets = self.getAssets(names=[name],assetTypes=[assetType])
        if len(assets) > 0:
            return assets[0]
        
        raise FTrackError('Asset does do exist')

    def getAssets(self,assetTypes=None,names=None,includeChildren=False,componentNames=None,excludeWithTasks=False):
        """
        Get Assets
        
        :param names: A ``list`` with names of the assets
        :param assetTypes: A ``list`` with names of the asset types or short names of the asset types or asset type ids
        :param componentNames: A ``list`` with names of components that the versions must have at least one of
        :param excludeWithTasks: A ``bool`` which defaults to False, can be used to get assets with versions that are not connected to any tasks

        :rtype: FTList of Assets
        """
        return _getAssets(parent=self,assetTypes=assetTypes,names=names,includeChildren=includeChildren, componentNames=componentNames, excludeWithTasks=excludeWithTasks)


    def getUsers(self):
        """
        Get Users assigned to this Task
        
        :rtype: FTList of User
        """
        response = []
        if 'users' in self.dict:
            response = self.dict['users']
        else:
            data = {'type':'users','entityId':self.getId(),'entityType':self._type}
            response = xmlServer.action('get',data)
        return FTList(User,response)

    def getId(self):
        return self.get("taskid")

    def getDescription(self):
        return self.get("description")

    def getName(self):
        return self.get("name")

    def getBid(self):
        return self.get("bid")
    
    def getStartDate(self):
        return self.get("startdate")

    def getEndDate(self):
        return self.get("enddate")

    def setStartDate(self,theDate):
        return self.set("startdate",theDate)

    def setEndDate(self,theDate):
        return self.set("enddate",theDate)

    def getType(self):
        '''Return the type of the object or None if it has no type.'''
        typeId = self.get('typeid')
        if typeId:
            return TaskType(id=typeId)
        else:
            return None

    def getObjectType(self):
        return self.get('objecttypename')

    def assignUser(self,user):
        """
        Assigns a user to a task
        
        :param user: A ``User`` object representing the user that should be assigned to the task.
        """
        data = {'type':'assignuser','taskid':self.getId(),'userid':user.getId()}
        response = xmlServer.action('set',data)
    
    def unAssignUser(self,user):
        """
        Unassigns a user from a task
        
        :param user: A ``User`` object representing the user that should be unassigned from the task.
        """ 
        data = {'type':'unassignuser','taskid':self.getId(),'userid':user.getId()}
        response = xmlServer.action('set',data)           

    def getLists(self):
        """
        Returns the lists that have been linked/associated with this task.
        NOTE: There is a difference between a task being added to a list and lists linked to a task
        
        :rtype: ``list``
        """  
        data = {'type':'tasklists','taskid':self.getId()}
        response = xmlServer.action('get',data)
        return FTList(List,response)

    def getProject(self):
        """
        Get project this object belongs to
        
        :rtype: Project
        """        
        return Project(self.get('showid'))

    def getPriority(self):
        '''Return the priority of the object or None if it has no priority.'''
        priorityId = self.get('priorityid')
        if priorityId:
            return Priority(priorityId)
        else:
            return None

    def setPriority(self,priority):
        self.set('priorityid',priority)


class User(FTObject, Thumbnailable, Timereportable, Metable):
    """
    Username can be supplied to constructor to fetch a user
    
    :param username: A string with the username of the user
    """    
    _type = 'user'
    
    def getId(self):
        return self.get("userid")

    def getUsername(self):
        return self.get("username")

    def getName(self):
        return self.get("firstname") + " " + self.get("lastname")

    def getEmail(self):
        return self.get("email")

    def getTasks(self,*args,**argv):
        """
        Get Tasks assigned to this User
        
        :param taskTypes: ``list`` representing task types. Can be ``TaskType`` objects, their IDs or their names.  
        :param taskStatuses: ``list`` representing task statuses. Can be ``TaskStatus`` objects, their IDs or their names.
        :param states: ``list`` with states. Possible states are NOT_STARTED, IN_PROGRESS, DONE, BLOCKED which are availible from the ftrack module
        :param activeProjectsOnly: ``bool`` Default to ``True``. specifying if only to query active projects.
        :param projects: ``list`` representing Projects. Can be ``Project`` objects or their IDs.
        :param includePath: ``bool`` Default to ``False``. specifying if the path should be added to each task. Much faster than useing getParents on each task afterwards.
        :rtype: ``FTList`` with ``Task``
        """
        return _getTasks(parent=self,*args,**argv)
    
    def getRoles(self):
        """
        Get Roles that belong to this user
        :rtype: ``FTList`` with ``Role``
        """
        
        data = {'type':'roles','userid':self.getId()}
        response = xmlServer.action('get',data)        
        return FTList(Role,response)

    def addRole(self, role, project=None):
        '''Add role to this user.
        If *project* is None the role will be added to all projects.
        '''
        data = {
            'userId': self.getId(),
            'roleId': role,
            'projectId': project
        }
        xmlServer.action('addRole', data)

    def removeRole(self, role, project=None):
        '''Remove *role* from *project*.

        If *project* is None the role will be removed from all projects.
        '''
        data = {
            'userId': self.getId(),
            'roleId': role,
            'projectId': project
        }
        xmlServer.action('removeRole', data)

    def getRoleProjects(self, role):
        '''Return active projects a *role* is valid for.'''
        data = {
            'userId': self.getId(),
            'roleId': role
        }
        response = xmlServer.action('getRoleProjects', data)
        return FTList(Project, response)

    def getApiKey(self):
        """
        Get the api that can be used for this user. Will raise error if you dont have the correct permission to do this.
        :rtype: ``str``
        """
        
        data = {'type':'getuserapikey','userid':self.getId()}
        response = xmlServer.action('get',data)        
        return response
        
    def resetApiKey(self):
        """
        Reset the user api key. Will raise error if you dont have the correct permission to do this.
        :rtype: ``str``
        """
        
        data = {'type':'resetuserapikey','userid':self.getId()}
        response = xmlServer.action('get',data)

    def getBookings(self):
        '''
        Return all bookings for this project
        '''

        data = {'type':'bookings', 'entityId':self.getId(),'entityType':self._type}
        response = xmlServer.action('get',data)

        return FTList(Booking,response)

    def createBooking(self, description, startdate, enddate, project=None, bookingType=None):
        ''' 
        Create a booking for this project 

        :param description: A ``str`` with the description of this booking
        :param startdate: A ``datetime`` with the start date of this booking
        :param enddate: A ``datetime`` with the end date of this booking
        :param user: A ``Project`` to book on (optional)
        :param bookingType: A ``str`` Booking type. Use Booking.VACATION 
        or Booking.PROJECT. If project param is used, the bookingType must be 
        Booking.PROJECT.
        '''

        if bookingType == None:
            bookingType = Booking.PROJECT


        assert project == None or bookingType == Booking.PROJECT, 'If project is set, booking must be of PROJECT type.'


        projectId = None

        if project:
            projectId = project.getId()
        
        data = {'type':'booking','description': description,'startdate': startdate,'enddate': enddate, 'projectid' : projectId, 'userid' : self.getId(), 'bookingType' : bookingType}
        response = xmlServer.action('create',data)
        return Booking(dict=response)

    
class TaskType(FTObject):
    _type = 'tasktype'

    def getName(self):
        return self.get('name')

    def getId(self):
        return self.get("typeid")


class Status(FTObject):
    _type = 'taskstatus'

    def getName(self):
        return self.get('name')

    def getId(self):
        return self.get("statusid")

    def getState(self):
        return self.get("state")

    def __eq__(self, other):
        return self.getName() == other or self.getState() == other


class ShotStatus(FTObject):
    _type = 'shotstatus'

    def getName(self):
        return self.get('name')

    def getId(self):
        return self.get("statusid")

class Role(FTObject):
    _type = 'auth_role'

    def getName(self):
        return self.get('name')

    def getId(self):
        return self.get("roleid")


class Note(FTObject,Metable,Noteable):
    _type = 'note'
    _idkey = 'noteid'

    def getId(self):
        return self.get("noteid")
    
    def getText(self):
        return self.get("text")
    
    def getDate(self):
        return self.get("date")
    
    def getUser(self):
        return User(id=self.get("userid"))   
    
    def getCategory(self):
        return NoteCategory(id=self.get("categoryid"))
    
    def createReply(self,*args,**argv):
        """
        Used to add a note on a note
        
        :param note: the note text as a string
        :param category: ``NoteCategory`` (optional)
        """
        return self.createNote(*args,**argv)
    
    def isReply(self):
        return self.get('noteparentid') != None

    def getRecipients(self):
        """
        Get recipients for this note. Recipients are users that were notified when it was created.
        """        
        data = {'type':'recipients','entityType':self._type,'entityId':self.getId()}
        response = xmlServer.action('get',data)
        return FTList(User,response)

    def createAttachment(self, file, fileName=None):
        '''Create an attachment from *file*.'''
        component = _createAttachment(file, fileName)

        xmlServer.action(
            'addNoteComponent',
            {
                'id': self.getId(),
                'component_id': component.getId()
            }
        )

        return component

    def getAttachments(self):
        '''Return attachments.'''
        # Local import to avoid circular.
        from .component import Component

        response = xmlServer.action('getNoteComponents', {'id': self.getId()})

        return FTList(Component, response)


class ProjectScheme(FTObject):
    _type = 'project_scheme'

    def getId(self):
        return self.get("schemeid")
    
    
class Priority(FTObject):
    _type = 'priority_type'

    def getValue(self):
        return self.get('value')

    def getSort(self):
        return self.get('sort')

    def getColor(self):
        return self.get('color')

    def getName(self):
        return self.get('name')

    def getId(self):
        return self.get("priorityid")

class NoteCategory(FTObject):
    _type = 'note_category'

    def getSort(self):
        return self.get('sort')

    def getColor(self):
        return self.get('color')

    def getName(self):
        return self.get('name')

    def getId(self):
        return self.get("categoryid")
    
    
    
class ActivityEvent(FTObject):
    _type = 'social_event'

    def getId(self):
        return self.get("socialid")
    
    def getEntity(self):
        classes = FTObject.__subclasses__()
        
        for c in classes:
            
            if c._type.replace("_","") == self.get('parent_type').replace("_",""):
                
                data = self.get('object')
                
                #loaded
                if data:
                    return c(dict=data)
    
                #load
                else:
                    return c(self.get('parent_id'))
                
    def getData(self):
        return self.get('data')
    
class ListCategory(FTObject):
    _type = 'listtype'

    def getName(self):
        return self.get("name")

    def getId(self):
        return self.get("typeid")
    
class Disk(FTObject):
    _type = 'disk'

    def getName(self):
        return self.get("name")

    def getId(self):
        return self.get("diskid")

class List(FTObject):
    """
    Used to group objects (shots,tasks,versions) together. Can for example be used as a review list.
    
    :param:  id  listid
    """        
    _type = 'list'
    _idkey = 'listid'

    def __init__(self,*args,**argv):
        super(List,self).__init__(*args,**argv)
        
        self.items = []
        self.isLoaded = False

    def getName(self):
        return self.get('name')

    def _loadIfNotLoaded(self):
        if self._isDirty():
            return
        
        #load
        self._load()
        
    def _isDirty(self):
        return self.isLoaded
        
    def _setDirty(self):
        self.isLoaded = False

    def _load(self):
        data = {'type':'listobjects','id':self.getId()}
        response = xmlServer.action('get',data)
        self.items = FTList([Shot,Task,AssetVersion],response)

    def getId(self):
        return self.get("listid")

    def append(self,item):
        """
        Add item to this list
        
        :param item: The object to be added to the list
        """        
        self.extend([item])
        
    def extend(self,items):
        """
        Add multiple items to this list
        
        :param items: The objects to be added to the list
        """          
        listItems = []
        
        for item in items:
            listItems.append({'entityId':item.getId(),'entityType':item._type})           
        
        
        data = {'type':'listextend','items':listItems,'id':self.getId()}
        response = xmlServer.action('set',data)
        
        #set dirty
        self._setDirty()
    
    def remove(self,items):
        """
        Remove items from this list
        
        :param items: The entities to be remove from the list
        """         
        if type(items).__name__ != 'list':
            items = [items]
            
        listItems = []
        
        for item in items:
            listItems.append({'entityId':item.getId(),'entityType':item._type})           
        
        data = {'type':'listremove','items':listItems,'id':self.getId()}
        response = xmlServer.action('set',data)
        
        #set dirty
        self._setDirty()
    
    def getObjects(self):
        """
        Get all obejcts in this list
        """        
        self._loadIfNotLoaded()
        return self.items  
    
    def open(self):
        """
        Open this list
        """         
        self.set('isopen',True)
    
    def close(self):
        """
        Close this list to make sure nothing else can be added
        """               
        self.set('isopen',False)   
    
    def __getitem__(self, key):
        return self.getObjects()[key]

    def __len__(self):
        return len(self.getObjects())
    
    def __iter__(self):
        for elem in self.getObjects():
            yield elem    
    
    def isOpen(self):
        """
        Return True or False if the list is open or not
        """          
        return self.get('isopen')
    
    
    def getLinked(self):
        """
        Used to return all tasks that this list was linked to
        """     
        data = {'type':'listlinked','id':self.getId()}
        response = xmlServer.action('get',data)        
              
        return FTList(Task,response)
    
    def link(self,item):
        """
        Used to link a list to a task
        
        :param item: The task that the list should be linked to
        """      
        
        entity = {'entityId':item.getId(),'entityType':item._type}        
        
        data = {'type':'listlink','items':[entity],'id':self.getId()}
        response = xmlServer.action('set',data)
        
    def unlink(self,item):
        """
        Used to unlink a list from a task
        
        :param item: The task that the list should be un-linked from
        """         
          
        entity = {'entityId':item.getId(),'entityType':item._type}        
        
        data = {'type':'listunlink','items':[entity],'id':self.getId()}
        response = xmlServer.action('set',data)
    
    
    
    def getValue(self,fromObject,key):
        
        data = {'type':'listobjectattributeget','listid':self,'entityid':fromObject}
        response = xmlServer.action('get',data)
        
        listobject = ListObject(dict=response)
        
        return listobject.get(key)
    
    def setValue(self,fromObject,key,value):
        
        data = {'type':'listobjectattributeget','listid':self,'entityid':fromObject}
        response = xmlServer.action('get',data)
        
        listobject = ListObject(dict=response)
        
        return listobject.set(key,value)    


def createJob(description, status, user=None):
    """
    Create a api job visible in ftrack

    :param description: ``str`` a description of the job
    :param status: ``str`` status of the job. Possible statuses are queued, running, done, failed
    :param user: ``User`` set the user the job belongs to
    :rtype: ``Job``
    """
    data = {
        'type': 'job',
        'description': description,
        'status': status,
        'user': user
    }

    response = xmlServer.action('create', data)
    return Job(dict=response)


def getJobs(status=None):
    """
    Get Events
    :param status: ``str`` status of the jobs
    :rtype: list of Jobs
    """

    data = {
        'type': 'jobs',
        'status': status
    }

    response = xmlServer.action('get', data)
    return FTList(Job, response)


class Job(FTObject):
    _type = 'job'

    def getId(self):
        return self.get("jobid")

    def setStatus(self, status):
        """
        Sets the status of the job

        :param status: ``str`` status of the job. Possible statuses are queued, running, done, failed.
        """

        if not status in ['queued', 'running', 'done', 'failed']:
            raise FTrackError('Job status must be "queued", "running", "done" or "failed"')
        
        data = {
            'type': 'job',
            'jobid': self.getId(),
            'status': status
        }

        response = xmlServer.action('set', data)
        return response

    def setDescription(self, description):
        """
        Sets the description of the job

        :param description: ``str`` description of the job.
        """

        data = {
            'type': 'job',
            'jobid': self.getId(),
            'description': description
        }

        response = xmlServer.action('set', data)
        return response

    def createAttachment(self, file, fileName=None):
        '''Create an attachment on this job from *file*.'''
        component = _createAttachment(file, fileName)

        xmlServer.action(
            'addJobComponent',
            {
                'id': self.getId(),
                'component_id': component.getId()
            }
        )

        return component

    def getAttachments(self):
        '''Return attachments on this job.'''
        # Local import to avoid circular.
        from .component import Component

        response = xmlServer.action('getJobComponents', {'id': self.getId()})

        return FTList(Component, response)


# Legacy methods and classes.
TaskStatus = Status
VersionStatus = Status
Show = Project
createShow = createProject
getShows = getProjects
getShow = getProject    
AssetVersion.createTake = AssetVersion.createComponent
AssetVersion.getTakes = AssetVersion.getComponents
AssetVersion.getTake = AssetVersion.getComponent


class Sequence(Task):
    """
    DEPRECATED CLASS
    """


class Shot(Task):
    """
    DEPRECATED CLASS
    """    
    _object_typeid = "bad911de-3bd6-47b9-8b46-3476e237cb36"
