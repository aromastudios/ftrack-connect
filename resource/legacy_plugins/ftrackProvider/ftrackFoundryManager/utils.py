def register_scheme(scheme):
    import urlparse
    for method in filter(lambda s: s.startswith('uses_'), dir(urlparse)):
        getattr(urlparse, method).append(scheme)

register_scheme('ftrack')

class MiniCache(object):

  # A quick and dirty cache that can be used to avoid slow calls to the server

  def __init__(self):
    self.__data = {}

  def clear(self):
    self.__data = {}

  def get(self, key, default=None):
    """If default is callable, it will be called to construct the value."""
    if key in self.__data:
      return self.__data[key]
    if hasattr(default, '__call__'):
      default = default()
    if default is not None:
      return self.__data.setdefault(key, default)
    else:
      return None

  def set(self, key, value):
    self.__data[key] = value


## For now, we cache entityRef -> obj
__entityCache = MiniCache()

def flushEntityCache():
  global __entityCache
  __entityCache = MiniCache()


def preProcessMeta(key, value):
  import ftrack
  """
  Because the FTrack API takes strong types, we may need to massage some data
  that will have come in as a string from the ManagerInterfaceBase API.
  """

  if key == 'status':
    value = str(value)
    nativeStatus = None
    available = []
    for s in ftrack.getTaskStatuses():
      available.append(s.getName())
      if s.getName() == s:
        nativeStatus = s
        break
    if not nativeStatus:
      raise ValueError("Unable to find the status '%s' in %s"
        % (value, available))
    value = nativeStatus

  return value


def isEntityReference(token):
    import urlparse
    url = urlparse.urlparse(token)
    token = url.netloc
    return len(token) == 36 and token.count('-') == 4


def objectName(obj):
    """
    Not all object have getName(), so we need to do something intelligent
    in these cases.
    """
    if hasattr(obj, "getName"):
        return obj.getName()
    elif hasattr(obj, "getVersion"):
        return 'v' + str(obj.getVersion()).zfill(3)
    else:
        return "unknown"


def objectType(obj):
  import ftrack
  """
  Returns a string that identifies the type of the object.
  """
  if hasattr(obj, 'getObjectType'):
    return obj.getObjectType()
  elif isinstance(obj, ftrack.Asset):
    return 'Asset'
  elif isinstance(obj, ftrack.AssetVersion):
    return 'AssetVersion'
  elif isinstance(obj, ftrack.Component):
    return 'Component'
  elif isinstance(obj, ftrack.Project):
    return 'Project'
  return ''


def objectById(identifier, throw=True):
    import ftrack
    import urlparse
    obj = None
    
    if identifier !='':       
        if 'ftrack://' in identifier:
            url = urlparse.urlparse(identifier)
            query = urlparse.parse_qs(url.query)      
            entityType = query.get('entityType')[0]
                
            identifier = url.netloc
            
            cached = __entityCache.get(identifier)
            if cached:
                return cached
            try:
                # Entity type is checked against 'assettake' to maintain
                # backwards compatibility towards project files created before
                # ftrack 2.4v1 in which 'assettake' where switched for
                # 'component'.
                if entityType in ('component', 'assettake'):
                    obj = ftrack.Component(identifier)
                elif entityType == 'asset_version':
                    obj = ftrack.AssetVersion(identifier)
                elif entityType == 'asset':
                    obj = ftrack.Asset(identifier)
                elif entityType == 'show':
                    obj = ftrack.Project(identifier)
                elif entityType == 'task':
                    obj = ftrack.Task(identifier)
                elif entityType == 'tasktype':
                    obj = ftrack.TaskType(identifier)
            except:
                pass
                
        else:
            ftrackObjectClasses = [
                ftrack.Task,
                ftrack.Asset, ftrack.AssetVersion, ftrack.Component,
                ftrack.Project,
                ftrack.TaskType
            ]
            
            cached = __entityCache.get(identifier)
            if cached:
                return cached
              
            for cls in ftrackObjectClasses:
              try:
                obj = cls(id = identifier)
                break
              except ftrack.api.ftrackerror.FTrackError as e:
                if e.message.find("was not found") == -1:
                  raise
                pass
              except Exception, e:
                import FnAssetAPI.logging as logging
                logging.log("Exception caught trying to create %s: %s" %
                    (cls.__name__, e), logging.kError)
                raise

    if not obj and throw:
      import FnAssetAPI.exceptions as exceptions
      raise exceptions.InvalidEntityReference, "Unknown Entity ID: '%s'" % identifier
    __entityCache.set(identifier, obj)

    return obj

def targetAssetNameFromRef(targetRef):
    import urlparse
    url = urlparse.urlparse(targetRef)
    query = urlparse.parse_qs(url.query)
    if 'assetName' in query:
        return query.get('assetName')[0]
    else:
        return None

def shotFromObj(obj):

  """Returns the Shot that is the parent of obj. If obj is the parent of shots,
  None is returned."""

  ## Dont know how sensible/sane/reliable this is, but its a proof of concept

  objType = objectType(obj)
  while obj and objType != 'Shot' and objType != 'Project':
    obj = obj.getParent() if hasattr(obj, 'getParent') else None
    objType = objectType(obj)

  return obj if objType == 'Shot' else None


def getPath(task, unders=False, slash=False, includeAssettype=False):
    import ftrack
    if task.get('entityType') == 'show':
        return task.getName()
    else:
        shotparents = task.getParents()
        shotparents = [parent for parent in reversed(shotparents)]
        shotpath = shotparents + [task]
        shotpathstr = []
        for obj in shotpath:
            if isinstance(obj, ftrack.Asset) and includeAssettype==True:
                path = objectName(obj) + '.' + obj.getType().getShort()
            else:
                path = objectName(obj)
        
            shotpathstr.append(path)
        
        if unders:
            shotpath = '_'.join(shotpathstr)
        elif slash:
            shotpath = ' / '.join(shotpathstr)
        else:
            shotpath = '.'.join(shotpathstr)
        return shotpath


def lockFile(path):
  """
  Locks a file, preserving other flags. According to the python docs this
  should work on Windows too... I think.
  """

  import os, stat

  # Get just the write bits
  writeBits = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
  # Invert them
  readExBits = ~writeBits

  # AND them with the original mode so we just set the write bits to 0 and
  # leave the rest as they were
  mode = os.stat(path).st_mode
  mode = mode & readExBits

  os.chmod(path, mode)

def getFileFromUrl(url, toFile=None, returnResponse=None):
    import urllib2
    import os

    ftrackProxy = os.getenv('FTRACK_PROXY', '')
    ftrackServer = os.getenv('FTRACK_SERVER', '')
    if ftrackProxy != '':
        if ftrackServer.startswith('https'):
            httpHandle = 'https'
        else:
            httpHandle = 'http'
            
        proxy  = urllib2.ProxyHandler({httpHandle: ftrackProxy})
        opener = urllib2.build_opener(proxy)
        response = opener.open(url)
        html = response.read()
    else:
        response = urllib2.urlopen(url)
        html = response.read()
    
    if toFile:
        output = open(toFile,'wb')      
        output.write(html)
        output.close()
    
    if returnResponse:
        return response
    
    return html

def getFtrackQNetworkProxy():
    import os
    ftrackProxy = os.getenv('FTRACK_PROXY', '')
    if ftrackProxy != '':
        from QtExt import QtNetwork
        proxyAdress = ftrackProxy.split(':')[0]
        proxyPort = int(ftrackProxy.split(':')[1])
        proxy = QtNetwork.QNetworkProxy(QtNetwork.QNetworkProxy.HttpProxy, proxyAdress, proxyPort)
        
        return proxy
    
    return None