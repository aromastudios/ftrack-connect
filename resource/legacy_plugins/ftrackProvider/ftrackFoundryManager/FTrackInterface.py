import FnAssetAPI
from FnAssetAPI.implementation import ManagerInterfaceBase
from FnAssetAPI.exceptions import EntityResolutionError, InvalidEntityReference, PreflightError, RegistrationError


import utils

class FTrackInterface(ManagerInterfaceBase):

  kIdentifier = "com.ftrack"

  _metamap = {
      'fullname' : FnAssetAPI.constants.kField_DisplayName,
      'fstart' : FnAssetAPI.constants.kField_FrameStart,
      'fend' : FnAssetAPI.constants.kField_FrameEnd
  }

  _metakeys = {
    'Project' : [ 'fullname', 'startdate', 'enddate' ],
    'Task' : [ 'fstart', 'fend' ],
    'AssetVersion' : [ 'comment' ]
  }

  def __init__(self):
    super(FTrackInterface, self).__init__()
    self._revMetamap = dict( (v,k) for k,v in self._metamap.iteritems() )

    self.ftrackMetaKeys = []


  def getIdentifier(self):
    return self.kIdentifier

  def getDisplayName(self):
    return "ftrack"

  def getInfo(self):
    import os

    ## @todo This is used in the FTrackInlinePickerWidget too
    basePath = os.path.dirname(os.path.realpath(__file__))

    return {
      "server" : os.environ.get("FTRACK_SERVER", None),
      "api-key" : os.environ.get("FTRACK_APIKEY", None),
      FnAssetAPI.constants.kField_Icon : os.path.join(basePath, "ui", "widgets", "PNG", "logobox.png")
    }


  def initialize(self):
    # Add event listeners
    import events
    events.registerEventHandlers()
    
    # @TODO: Dont use application wide proxy. Currently modifying qnetworkaccessmanager results in crash
    ftrackProxy = utils.getFtrackQNetworkProxy()
    if ftrackProxy != None:
        from QtExt import QtNetwork
        QtNetwork.QNetworkProxy.setApplicationProxy(ftrackProxy)


  def flushCaches(self):
    utils.flushEntityCache()


  def isEntityReference(self, token, context):
    # You could look this up here, but there is no prerequisite to
    # determine if it is valid at this point, its more to do with
    # establishing if the manager should be involved
    return utils.isEntityReference(token)

  def containsEntityReference(self, string):
    raise NotImplementedError

  def entityExists(self, entityRef, context):
    obj = utils.objectById(entityRef, False)
    return True if obj else False


  def getDefaultEntityReference(self, specification, context):
    return ""


  def thumbnailSpecification(self, specification, context, options):

    if specification and specification.isOfType(("file", "group.shot")):
      return True

    return False


  def managementPolicy(self, specification, context, entityRef=None):
    ## @todo Inspect specification and set ignored
    ## on the types we don't understand.
    ## We don't set the path management flag.
    policy = 0
    return policy ^ FnAssetAPI.constants.kManaged

  def resolveInlineEntityReferences(self, string, context):
    '''Return copy of input *string* with all references resolved.'''
    return string


  def resolveEntityReference(self, entityRef, context):

    import ftrack

    obj = utils.objectById(entityRef)

    if isinstance(obj, ftrack.Component):
      # For now, check noones trying to write to it, as we're a tracker, and so
      # anyone writing to an exiting asset is BAD and we should disallow it
      if context and context.isForWrite():
        raise InvalidEntityReference("You can't overwrite an existing asset", entityRef)
      importPath = obj.getImportPath()
      if '#' in importPath:
          importPath = self.convertHashes(importPath)
      return importPath
    else:
      try:
        objName = utils.objectName(obj)
        return objName
      except:
        raise EntityResolutionError("Unable to resolve", entityRef)


  def convertHashes(self, path):
      import re
      match = re.search('#{1,20}', path)
      middle = path[match.start(0): match.end(0)]
      sprintfstring = '%' + str(len(middle)).zfill(2) + 'd'
      return path[:match.start(0)] + sprintfstring + path[match.end(0):]


  def resolveEntityReferences(self, string, context):
    raise NotImplementedError


  def getEntityName(self, entityRef, context):
    obj = utils.objectById(entityRef)
    return utils.objectName(obj)

  def getEntityDisplayName(self, entityRef, context):
    # For now, we'll return the hierarchy path to this item

    ## @todo Will this be horrendously slow?

    obj = utils.objectById(entityRef)

    name = ''
    if context and context.locale:
      if context.locale.isOfType("clip"):
        name = self._displayNameForClip(obj, context)

    if name:
      return name

    parents = obj.getParents()

    nameParts = []
    nameParts.append(str(utils.objectName(obj)))
    for p in parents:
      nameParts.append(str(utils.objectName(p)))
    return " / ".join(nameParts[::-1])


  def _displayNameForClip(self, obj, context):

    import ftrack

    if isinstance(obj, ftrack.Component):
      # Hiero is sensitive to names, so it should just be the name of the asset
      asset = obj.getParent().getAsset()
      return asset.getName()

    return ""



  def getEntityVersionName(self, entityRef, context):

    obj = utils.objectById(entityRef)
    version = self._getVersionName(obj)
    return str(version)


  def getEntityVersions(self, entityRef, context, includeMetaVersions=False,
      maxResults=-1):

    obj = utils.objectById(entityRef)

    versionObjects = []
    try:
      versionObjects = self._objectVersions(obj)
    except Exception, e:
      raise EntityResolutionError(e)

    # Max results gives limits to most recent
    numVersions = len(versionObjects)
    if maxResults > 0 and numVersions > maxResults:
      versionObjects = versionObjects[numVersions-maxResults:]

    versions = dict( (str(self._getVersionName(v)),v.getEntityRef()) for v in versionObjects )
    return versions


  def getFinalizedEntityVersion(self, entityRef, context, version=None):

    # Presently, this doesn't support the concept of 'latest' etc...

    obj = utils.objectById(entityRef)
    objVersion = self.getEntityVersionName(entityRef, context)

    if not version:
      # This is where we would start dealing with vLatest, etc.. but for
      # now, we assume if no version is specified, they want the input
      # version
      return entityRef

    if objVersion == version:
      return entityRef

    versions = self._objectVersions(obj)
    versionsDict = dict( (str(self._getVersionName(v)),v) for v in versions )
    matchingVersionObj = versionsDict.get(version, None)

    if not matchingVersionObj:
      raise EntityResolutionError(
          "Unable to find a version matching '%s' for '%s'"
            % (version, self.getEntityDisplayName(entityRef,context)))

    if matchingVersionObj:
      return matchingVersionObj.getEntityRef()
    else:
      raise EntityResolutionError(
        "Unable to resolve the version '%s' for '%s'"
          % (version, self.getEntityDisplayName(entityRef, context)))


  def getEntityMetadata(self, entityRef, context):

    obj = utils.objectById(entityRef)
    metadata = obj.getMeta()
    # We map certain metadata keys into our own properties
    try:
      mapkey = obj.__class__.__name__
      for k in self._metakeys.get(mapkey, []):
        metadata[self._metamap.get(k,k)] = obj.get(k)
    except AttributeError:
      pass

    return dict(metadata)

  def setEntityMetadata(self, entityRef, data, context, merge=True):
    obj = utils.objectById(entityRef)

    # This is a little hacky but will give us a handle value in ftrack
    if data.get(FnAssetAPI.constants.kField_FrameIn, None) and data.get(FnAssetAPI.constants.kField_FrameStart, None):
        frameStart = int(data.get(FnAssetAPI.constants.kField_FrameStart, 0))
        frameIn = int(data.get(FnAssetAPI.constants.kField_FrameIn, 0))
        handleWidth = frameIn - frameStart
        obj.set('handles', handleWidth)

    # We map certain metadata keys into our own properties
    # So set those if we have them and pop them from the blind data
    try:
      mapkey = obj.__class__.__name__
      keys = self._metakeys.get(mapkey, [])
      for k in keys:
        fnKey= self._metamap.get(k, k)
        if fnKey in data:
          v = data.pop(fnKey)
          v = utils.preProcessMeta(k, v)
          obj.set(k, v)
    except AttributeError:
      pass

    if merge:
      existing = obj.getMeta()
      existing.update(data)
      data = existing

    obj.setMeta(data)


  def getEntityMetadataEntry(self, entityRef, fnKey, context):

    obj = utils.objectById(entityRef)
    try:
      mapkey = obj.__class__.__name__
      keys = self._metakeys.get(mapkey, [])
      key = self._revMetamap.get(fnKey, fnKey)
      if key in keys:
        return obj.get(key)
    except AttributeError:
      pass

    return obj.getMeta(fnKey)


  def setEntityMetadataEntry(self, entityRef, fnKey, value, context):

    obj = utils.objectById(entityRef)
    try:
      mapkey = obj.__class__.__name__
      keys = self._metakeys.get(mapkey, [])
      key = self._revMetamap.get(fnKey, fnKey)
      if key in keys:
        obj.set(key, value)
    except AttributeError:
      pass

    return obj.setMeta(key, value)



  def getRelatedReferences(self, entityRefs, specs, context, resultSpec=None):
    import FTrackGetRelated
    numRefs = len(entityRefs)
    numSpecs = len(specs)

    if numRefs == numSpecs:
      return FTrackGetRelated.forPairs(entityRefs, specs, context, resultSpec)
    elif numRefs == 1:
      return FTrackGetRelated.forSpecs(entityRefs[0], specs, context, resultSpec)
    elif numSpecs == 1:
      return FTrackGetRelated.forRefs(specs[0], entityRefs, context,resultSpec)

    else:
      raise ValueError("Incorrect number of refs (%d) or specs (%s)"
          % (numRefs, numSpecs))


  def setRelatedReferences(self, entityRef, relationshipSpec, relatedRefs, context):
    pass


  def preflight(self, targetEntityRef, entitySpec, context):

    # As we don't yet have the ability to represent 'potential' assets (As were
    # using the UUID as the reference, then we should raise if we don't already
    # have a path for this item).

    ## @todo Consider the impact of allowing people to publish to existing
    ## assets

    if not self.entityExists(targetEntityRef, context):
      raise PreflightError("The referenced entity doesn't exist, unable to "+
          "write to this asset", targetEntityRef)

    return targetEntityRef


  def register(self, stringData, targetEntityRef, entitySpec, context):
    import ftrack
    try:
      import FTrackPublish

      ## The 'isOfType' function should always be used for comparisons instead
      ## of 'isinstance' as it is more robust in the case of 'python/c/python'
      ## roudtrips. In cases of objects from the core API, then the Class can
      ## be passed. However, if there are ever application-specific classes,
      ## etc.. then the type string "Specification.getType()" should be used
      ## instead, as the Class might not be available at runtime.

      # Projects
      if entitySpec.isOfType(FnAssetAPI.specifications.ProjectSpecification):
        return FTrackPublish.registerProject(stringData, targetEntityRef,
            entitySpec, context)

      # Shots/etc...
      elif entitySpec.isOfType(FnAssetAPI.specifications.GroupingSpecification):
        return FTrackPublish.registerGrouping(stringData, targetEntityRef,
            entitySpec, context)

      # ImageSpecification
      elif entitySpec.isOfType(FnAssetAPI.specifications.ImageSpecification):
        return FTrackPublish.registerImageFile(stringData, targetEntityRef,
            entitySpec, context)

      # NukeScripts
      elif entitySpec.isOfType("file.nukescript"):
        return FTrackPublish.registerNukeScript(stringData, targetEntityRef,
            entitySpec, context)

      # Hiero Projects
      elif entitySpec.isOfType("file.hrox"):
        return FTrackPublish.registerHieroProject(stringData, targetEntityRef,
            entitySpec, context)

      elif entitySpec.isOfType("file"):
        return FTrackPublish.registerGenericFile(stringData, targetEntityRef,
          entitySpec, context)

      else:
        raise RegistrationError("Unknown entity Specification: %s" %
            entitySpec, targetEntityRef)


    except ftrack.api.ftrackerror.FTrackError, e:
      raise RegistrationError(e, targetEntityRef)



  ## @name Utility methods
  ## @{
  def _objectVersions(self, obj):
    import ftrack
    # Attempts to find versions relevant to the input object, dealing with
    # the fact that in ftrack, versions are represented be explicit objects
    # in the hierarchy. An empty list will be returned if no versions are
    # relevant
    versionObjects = []
    versions = []
    # Default to main component if trying to get versions
    # from other than components
    name = "main"
    if isinstance(obj, ftrack.Component):
      # We need to keep track of the component name
      name = obj.getName()
      versions = obj.getVersion().getParent().getVersions()
    elif isinstance(obj, ftrack.AssetVersion):
      versions = obj.getParent().getVersions()
    elif isinstance(obj, ftrack.Asset):
      versions = obj.getVersions()

    for v in versions:
      try:
        c = v.getComponent(name=name)
      except ftrack.FTrackError:
        continue
      versionObjects.append(c)

    return versionObjects


  def _getVersionName(self, obj):
    import ftrack
    name = ''
    if isinstance(obj, ftrack.Component):
      obj = obj.getParent()
      name = obj.getVersion()
    elif isinstance(obj, ftrack.AssetVersion):
      name = obj.getVersion()
    elif isinstance(obj, ftrack.Asset):
      obj = obj.getVersions()[-1]
      name = obj.getVersion()
    return name

  ## @}

