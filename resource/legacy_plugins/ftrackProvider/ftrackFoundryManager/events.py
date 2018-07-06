import FnAssetAPI
import utils

def registerEventHandlers():
  """
  We use the event manager in the FnAssetAPI to handle certain export/import
  customisations, this registers our listeners with the system.
  """
  eventManager = FnAssetAPI.Events.getEventManager()

  # Adds custom knobs to Nuke Read Nodes, when exported from Hiero
  eventManager.registerListener('hieroToNukeScriptAddClip', hieroToNukeAddClip)
  eventManager.registerListener('hieroToNukeScriptAddWrite', hieroToNukeAddWrite)
  eventManager.registerListener('entityReferencesFromNukeNodes', refsFromNukeNodes)

# Adds custom knobs to Nuke Read Nodes, when exported from Hiero
def hieroToNukeAddClip(hieroClip, fileOrRef, readNode, nukeScript):

  ref = None

  if utils.isEntityReference(fileOrRef):
    ref = fileOrRef
  elif hasattr(hieroClip, 'entityReference'):
    clipRef = hieroClip.entityReference()
    if utils.isEntityReference(clipRef):
      ref = clipRef

  if ref:
    obj = utils.objectById(ref)
    assetVersion = obj.getVersion()
    asset = assetVersion.getAsset()

    readNode.addTabKnob("ftracktab", "ftrack")
    readNode.addInputTextKnob("componentId", "componentId", value=obj.getEntityRef())
    readNode.addInputTextKnob("componentName", "componentName", value=obj.getName())
    readNode.addInputTextKnob("assetVersionId", "assetVersionId", value=assetVersion.getEntityRef())
    readNode.addInputTextKnob("assetVersion", "assetVersion", value=assetVersion.getVersion())
    readNode.addInputTextKnob("assetName", "assetName", value=asset.getName())
    readNode.addInputTextKnob("assetType", "assetType", value=asset.getType().getShort())


# Adds custom knobs to the Nuke Write node when exported from Hiero
def hieroToNukeAddWrite(hieroClip, fileOrRef, writeNode, nukeScript):
  from hiero.core import nuke

  writeNode.addTabKnob("ftracktab", "ftrack")
  # This ensures the component name is 'main' rather than the name of the write
  # node, which causes all sorts of problems later.
  # writeNode.addInputTextKnob("fcompname", "componentName", value="main")

  # Having disabled the previous line we need to ensure the write node is called main, so is retained
  # as component name.
  writeNode.setName('main')

  ftrackPublishNode = nuke.GroupNode("ftrackPublish")
  inputNode = nuke.Node("Input", inputs=0)
  ftrackPublishNode.addNode(inputNode)
  outputNode = nuke.Node("Output", inputs=1)
  outputNode.setInputNode(0, inputNode)
  ftrackPublishNode.addNode(outputNode)
  ftrackPublishNode.addInputTextKnob("fpubinit", "fpubinit", value="False")

  if nukeScript:
    nukeScript.addNode(ftrackPublishNode)
  ftrackPublishNode.setInputNode(0, writeNode)


# Allow our custom knobs to be picked up by the selection tracker
def refsFromNukeNodes(nodes, entityRefSet):

  # Presently, we tag our refs on to a Nuke node as 'componentId'
  for node in nodes:
    for k in node.knobs().values():
      if k.name() != 'componentId':
        continue
      v = k.getValue()
      if utils.isEntityReference(v):
        entityRefSet.add(v)



