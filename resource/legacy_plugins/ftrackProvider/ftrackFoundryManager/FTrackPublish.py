import os

import ftrack
import utils

import FnAssetAPI
from FnAssetAPI.exceptions import RegistrationError


## @name Constants
## @{

kTaskTypeKey = 'taskType'

kTaskType_Comp = 'Compositing'
kTaskName_Comp = 'compositing'

kTaskType_Edit = 'Editing'
kTaskName_Edit = 'editing'

taskNameMap = {
  kTaskType_Comp : kTaskName_Comp,
  kTaskType_Edit : kTaskName_Edit
}

## @}


def registerProject(shortName, targetRef, spec, context):

  # Here, we don't actually care about the targetRef, as a Project is always
  # a top-level item.

  schemes = ftrack.getProjectSchemes()
  scheme = schemes[0] if schemes else None
  p = ftrack.createProject(shortName, shortName, scheme)
  return p.getEntityRef()


def getTaskId(obj, spec, context):

  taskType, taskName= getTaskTypeAndName(spec, obj, context)

  if hasattr(obj, 'getObjectType') and obj.getObjectType() in ['Shot', 'Sequence']:
    ftrackTasks = obj.getTasks(taskTypes=[taskType,])
    if len(ftrackTasks)>0:
      task = ftrackTasks[0]
      targetRef = task.getEntityRef()

    else:
      taskTypeObj = ftrack.TaskType(taskType)
      task = obj.createTask(taskName, taskTypeObj)
      targetRef = task.getEntityRef()

    return targetRef
  else:
    return obj.getEntityRef()


def getTaskTypeAndName(spec, obj=None, context=None):

  ## @todo Is obj already a task?

  # Obj might be none, when called from the RegistrationOptionsWidget

  session = FnAssetAPI.SessionManager.currentSession()

  # Fallback default

  taskType = kTaskType_Comp

  # Host specific defaults

  host = session.getHost()
  hostId = host.getIdentifier()

  if hostId == 'uk.co.foundry.nuke':
    taskType = kTaskType_Comp

  elif hostId == 'uk.co.foundry.hiero':
    taskType = kTaskType_Edit

  # Asset Type specific overrides

  # Several Apps make NukeScripts, but they should always go in comp (for now)
  if spec.isOfType("file.nukescript"):
    taskType = kTaskType_Comp

  elif spec.isOfType("file.hrox"):
    taskType = kTaskType_Edit

  # See if we've set this ourselves as a locale override
  if context and context.managerOptions:
    taskType = context.managerOptions.get(kTaskTypeKey, taskType)

  taskName = taskNameMap.get(taskType, taskType)

  return (taskType, taskName)


def registerGrouping(shortName, targetRef, spec, context):


  ## @todo if targetRef == getRootEntityReference() then make a project

  obj = utils.objectById(targetRef)
  wrongDestinationMsg = "Groupings can only be created under a Project or a Sequence."

  createFn = None
  if isinstance(obj, ftrack.Project):
    createFn = obj.createSequence
  elif isinstance(obj, ftrack.Task) and obj.getObjectType() == 'Sequence':
    createFn = obj.createShot

  if not createFn:
    raise RegistrationError(wrongDestinationMsg, targetRef)

  # For a grouping, the 'resolved string' is to be considered the name if not
  # overriden by a name hint.

  ## @todo We should make sure we always store the shortName (somewhere),
  ## as we need to pass this back to resolve later, if we're not using it for
  ## the name. Presently we resolve using the name
  name = spec.getField(FnAssetAPI.constants.kField_HintName, shortName)
  grouping = createFn(name=name)

  thumbnailPath = spec.getField('thumbnailPath', None)
  if thumbnailPath:
    grouping.createThumbnail(thumbnailPath)

  # Ensure correct tasks are created as well

  compositingTaskType = ftrack.TaskType(kTaskType_Comp)
  grouping.createTask(kTaskName_Comp, compositingTaskType)

  editingTaskType = ftrack.TaskType(kTaskType_Edit)
  grouping.createTask(kTaskName_Edit, editingTaskType)

  # Return the grouping id as we don't know which task is applicable at this
  # point - this is determined at registration when the host/spec is known
  return grouping.getEntityRef()


def registerNukeScript(path, targetRef, spec, context):
  return _registerGenericFile(path, targetRef, spec, context, 'comp',
      defaultName="nukeScript", component='nukescript')


def registerImageFile(path, targetRef, spec, context):
  return _registerGenericFile(path, targetRef, spec, context, 'img',
      defaultName="imageAsset")


def registerHieroProject(path, targetRef, spec, context):
  return _registerGenericFile(path, targetRef, spec, context, 'edit',
      defaultName="hieroProject", component='hieroproject')


def registerGenericFile(path, targetRef, spec, context):
  return _registerGenericFile(path, targetRef, spec, context,
      spec.getType(), 'asset')


def _registerGenericFile(path, targetRef, spec, context, assetType,
    component="main", defaultName="file", readOnly=True):

  # Tries to find an asset by:
  #  - Targeting a Task, look for assets with matching name, or create one
  #  - Targeting an Asset - use it
  #  - Targeting an AssetVersion get its Asset
  #
  # Then creates a new AssetVersion with a component under that asset

  name = spec.getField(FnAssetAPI.constants.kField_HintName, defaultName)

  assetNameFromRef = utils.targetAssetNameFromRef(targetRef)
  if assetNameFromRef:
      name = assetNameFromRef

  obj = utils.objectById(targetRef)
  targetRef = getTaskId(obj, spec, context)
  obj = utils.objectById(targetRef)

  asset = None
  if isinstance(obj, ftrack.Task):
    if obj.getObjectType() == 'Task':
      taskId = obj.getId()
      parentShot = obj.getParent()
      if parentShot.get('entityType') == 'show':
          raise RegistrationError("Can not publish on a task directly below a project")

      existing = parentShot.getAssets(assetTypes=[assetType,], names=[name,])
      if existing:
        asset = existing[0]
      else:
        asset = parentShot.createAsset(name, assetType)

  elif isinstance(obj, ftrack.Asset):
    asset = obj
    taskId = asset.getVersions()[-1].get('taskid')

  elif isinstance(obj, ftrack.Component):
    asset = obj.getVersion().getAsset()
    component = obj.getName()
    taskId = asset.getVersions()[-1].get('taskid')

  if not asset:
    raise RegistrationError("Unable to find a suitable asset relating to %s" % obj, targetRef)

  version = asset.createVersion(comment='', taskid=taskId)

  thumbnailPath = spec.getField('thumbnailPath', None)
  if thumbnailPath:
    version.createThumbnail(thumbnailPath)

  fcomponent = version.createComponent(file=path, name=component)

  if assetType == 'img':
      fcomponent.setMeta('img_main', 'True')

  # If we got this far, we should make it readOnly so noone else breaks it
  if readOnly and os.path.isfile(path):
    ## @todo Re-consider this when we better understand the future direction of
    ## file handling, etc... This is there for now to stop accidents
    utils.lockFile(path)

  # Publish the assetVersion if we got this far without errors
  version.publish()

  # We return the component as its the only unique way of addressing this when
  # an assset has multiple components
  return fcomponent.getEntityRef()



