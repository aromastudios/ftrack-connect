import FnAssetAPI

import utils

__cache = utils.MiniCache()

def getCache():
  global __cache
  return __cache

# We factor out each of the three calling cases, so that its easy to add
# specific optimisations in later if we can. Otherwise, we just iterate over
# each one, using the cache where we can to avoid overly expensive queries.

# For case a)  A single entity reference, a list of specifications.
def forSpecs(entityRef, specs, context, resultSpec):
  getCache().clear()

  related = []

  for s in specs:
    related.append( getRelatedSingle(entityRef, s, context, resultSpec) )

  return related



# For case b)  A list of entity references and a single specification.
def forRefs(spec, entityRefs, context, resultSpec):

  getCache().clear()

  related = []

  for r in entityRefs:
    related.append( getRelatedSingle(r, spec, context, resultSpec) )

  return related



# For case c)  Equal length lists of references and specifications.
def forPairs(refs, specs, context, resultSpec):

  getCache().clear()

  related = []

  for r,s in zip(refs, specs):
    related.append( getRelatedSingle(r, s, context, resultSpec) )

  return related



# The main relationship query method, deals with a single entity and a single
# ref. The API used to be just this before the need to batch queries to avoid
# excessive latencies.
def getRelatedSingle(ref, spec, context, resultSpec):
  obj = utils.objectById(ref)

  # The isOfType() function should always be used for comparisons

  if spec.isOfType("group.shot"):
    return getRelatedShots(obj, spec, context, resultSpec)

  if spec.isOfType("workflow"):
    return getWorkflowRelations(obj, spec, context, resultSpec)

  if spec.isOfType("grouping.parent", includeDerived=False):
    return getParentGrouping(obj, spec, context, resultSpec)

  return []



def getRelatedShots(obj, shotSpec, context, resultSpec):
  refs = []
  c = getCache()

  nameHint = shotSpec.getField(FnAssetAPI.constants.kField_HintName, None)
  objType = utils.objectType(obj)

  if objType == 'Sequence':
    # If obj is a sequence, then look for children
    children = c.get( (obj,'getChildren'), obj.getChildren )

    if nameHint:
      # We've been asked to find a Shot with a specific name
      match = children.find('name', nameHint)
      if match and hasattr(match, 'getId'):
        refs.append(match.getEntityRef())
    else:
      # Add all child shots
      refs.extend( [ s.getEntityRef() for s in children if hasattr(s, 'getId') ] )

  if objType == 'Asset' or objType == 'AssetVersion' or objType == 'Component':

    # If obj is some non-task type, then get the parent shot, checking its name
    # if necessary

    ## @todo Does this make sense for Tasks too?

    shot = utils.shotFromObj(obj)
    requestedName = nameHint

    if shot and hasattr(shot, 'getId'):
      if not requestedName or (requestedName == shot.getName()):
        refs.append(shot.getEntityRef())

  return refs


def getWorkflowRelations(obj, spec, context, resultSpec):
    import ftrack
    refs = []

    criteria = spec.getField('criteria')
    if not criteria:
      raise ValueError("No criteria specified with Workflow Specification: %s"
          % spec)

    splitCriteria = criteria.split(',')
    version = splitCriteria[0]
    taskType = utils.objectById(splitCriteria[1])

    if isinstance(obj, ftrack.Task):
        tasks = obj.getTasks(taskTypes=[taskType])
        refs = getRefsFromTasks(tasks, version, taskType)
        return refs
    elif isinstance(obj, ftrack.Component):
        shot = obj.getVersion().getAsset().getParent()
        tasks = shot.getTasks(taskTypes=[taskType])
        refs = getRefsFromTasks(tasks, version, taskType)
        return refs
    else:
        return refs

def getRefsFromTasks(tasks, version, taskType):
    refs = []
    for task in tasks:
        assets = task.getAssets(assetTypes=['img'])
        for asset in assets:
            assetVersions = asset.getVersions()
            if len(assetVersions)>0:
                if version == 'latest':
                    targetVersion = assetVersions[-1]
                elif version == 'latestapproved':
                    for version in reversed(assetVersions):
                        if version.getStatus().getName() == 'Approved':
                            targetVersion = version
                            break

                components = targetVersion.getComponents()

                for component in components:
                    imgMain = component.getMeta('img_main')
                    if imgMain:
                        refs.append(component.getEntityRef())
    return refs

def getParentGrouping(obj, spec, context, resultSpec):

  import ftrack

  # This should find the first Sequence/Shot/Project/etc.. (ie: None-task) that
  # the object is *under*.

  # We have to handle this case first as we'll eventually get to a 'Task' when
  # walking up from some more specialised obj type
  if isinstance(obj, ftrack.Project):
    return []

  if isinstance(obj, ftrack.Task) \
     and(obj.getObjectType() == "Shot" \
         or obj.getObjectType() == "Sequence"):

    obj = obj.getParent()

  else:

    # Get us back to a non 'Task' Task

    if isinstance(obj, ftrack.Component):
      obj = obj.getVersion()

    if isinstance(obj, ftrack.AssetVersion):
      obj = obj.getAsset()

    if isinstance(obj, ftrack.Asset):
      obj = obj.getParent()

    if isinstance(obj, ftrack.Task) and obj.getObjectType() == "Task":
      obj = obj.getParent()

  # Make sure we ended up with a grouping in the end
  if isinstance(obj, ftrack.Task):
    return [obj.getEntityRef(),]
  else:
    return []


