# Copyright (c) 2011 The Foundry Visionmongers Ltd.  All Rights Reserved.

import FnAssetAPI

import hiero.core
import hiero.core.util
import hiero.core.nuke as nuke
import hiero.exporters

from hiero.exporters.FnNukeShotExporter import NukeShotExporter

from hiero.exporters import FnShotExporter
from hiero.exporters import FnExternalRender
from hiero.exporters import FnScriptLayout


from hiero.exporters.FnExportUtil import (
  trackItemTimeCodeNodeStartFrame,
)
from hiero.ui.nuke_bridge import FnNsFrameServer as postProcessor

from .. import items
from .. import constants
from .. import specifications
from .. import utils as assetApiUtils


class NukeShotExporter(NukeShotExporter):

  def __init__(self, initDict):
    super(NukeShotExporter, self).__init__(initDict)
    # If we're requested to publish the script, see if we can find our target

    session = FnAssetAPI.SessionManager.currentSession()
    if not session:
      return None

    self._context = session.createContext()

    if self._preset.properties()["publishScript"]:
      self._targetEntity = self.__getTargetEntityForScript(self._item, self._context)
      if not self._targetEntity:
        FnAssetAPI.logging.warning(FnAssetAPI.l("Unable to find where to " +
                                                "{publish} the Nuke Script to for %r, the file will be written, " +
                                                "but not {published}.") % self._item)
  def taskStep(self):
    FnShotExporter.ShotTask.taskStep(self)
    if self._nothingToDo:
      return False

    script = nuke.ScriptWriter()

    start, end = self.outputRange(ignoreRetimes=True, clampToSource=False)
    unclampedStart = start
    hiero.core.log.debug( "rootNode range is %s %s %s", start, end, self._startFrame )

    firstFrame = start
    if self._startFrame is not None:
      firstFrame = self._startFrame

    # if startFrame is negative we can only assume this is intentional
    if start < 0 and (self._startFrame is None or self._startFrame >= 0):
      # We dont want to export an image sequence with negative frame numbers
      self.setWarning("%i Frames of handles will result in a negative frame index.\nFirst frame clamped to 0." % self._cutHandles)
      start = 0
      firstFrame = 0

    # Clip framerate may be invalid, then use parent sequence framerate
    framerate = self._sequence.framerate()
    dropFrames = self._sequence.dropFrame()
    if self._clip and self._clip.framerate().isValid():
      framerate = self._clip.framerate()
      dropFrames = self._clip.dropFrame()
    fps = framerate.toFloat()
    showAnnotations = self._preset.properties()["showAnnotations"]

    # Create the root node, this specifies the global frame range and frame rate
    rootNode = nuke.RootNode(start, end, fps, showAnnotations)
    rootNode.addProjectSettings(self._projectSettings)
    #rootNode.setKnob("project_directory", os.path.split(self.resolvedExportPath())[0])
    script.addNode(rootNode)

    if isinstance(self._item, hiero.core.TrackItem):
      rootNode.addInputTextKnob("shot_guid", value=hiero.core.FnNukeHelpers._guidFromCopyTag(self._item),
                                tooltip="This is used to identify the master track item within the script",
                                visible=False)
      inHandle, outHandle = self.outputHandles(self._retime != True)
      rootNode.addInputTextKnob("in_handle", value=int(inHandle), visible=False)
      rootNode.addInputTextKnob("out_handle", value=int(outHandle), visible=False)

    # Set the format knob of the root node
    rootNode.setKnob("format", str(self.rootFormat()))

    # BUG 40367 - proxy_type should be set to 'scale' by default to reflect
    # the custom default set in Nuke. Sadly this value can't be queried,
    # as it's set by nuke.knobDefault, hence the hard coding.
    rootNode.setKnob("proxy_type","scale")

    # Add Unconnected additional nodes
    if self._preset.properties()["additionalNodesEnabled"]:
      script.addNode(FnExternalRender.createAdditionalNodes(FnExternalRender.kUnconnected, self._preset.properties()["additionalNodesData"], self._item))

    # Project setting for using OCIO nodes for colourspace transform
    useOCIONodes = self._project.lutUseOCIOForExport()

    useEntityRefs = self._preset.properties().get("useAssets", True)
    # A dict of arguments which are used when calling addToNukeScript on any clip/sequence/trackitem
    addToScriptCommonArgs = { 'useOCIO' : useOCIONodes,
                              'additionalNodesCallback' : self._buildAdditionalNodes,
                              'includeEffects' : self.includeEffects(),
                              'useEntityRefs': useEntityRefs}

    writeNodes = self._createWriteNodes(firstFrame, start, end, framerate, rootNode)

    # MPLEC TODO should enforce in UI that you can't pick things that won't work.
    if not writeNodes:
      # Blank preset is valid, if preset has been set and doesn't exist, report as error
      self.setWarning(str("NukeShotExporter: No write node destination selected"))

    if self.writingSequence():
      self.writeSequence(script, addToScriptCommonArgs)

    # Write out the single track item
    else:
      self.writeTrackItem(script, addToScriptCommonArgs, firstFrame)


    script.pushLayoutContext("write", "%s_Render" % self._item.name())

    metadataNode = nuke.MetadataNode(metadatavalues=[("hiero/project", self._projectName), ("hiero/project_guid", self._project.guid()), ("hiero/shot_tag_guid", self._tag_guid) ] )

    # Add sequence Tags to metadata
    metadataNode.addMetadataFromTags( self._sequence.tags() )

    # Apply timeline offset to nuke output
    if isinstance(self._item, hiero.core.TrackItem):
      if self._cutHandles is None:
        # Whole clip, so timecode start frame is first frame of clip
        timeCodeNodeStartFrame = unclampedStart
      else:
        startHandle, endHandle = self.outputHandles()
        timeCodeNodeStartFrame = trackItemTimeCodeNodeStartFrame(unclampedStart, self._item, startHandle, endHandle)
      timecodeStart = self._clip.timecodeStart()
    else:
      # Exporting whole sequence/clip
      timeCodeNodeStartFrame = unclampedStart
      timecodeStart = self._item.timecodeStart()

    script.addNode(nuke.AddTimeCodeNode(timecodeStart=timecodeStart, fps=framerate, dropFrames=dropFrames, frame=timeCodeNodeStartFrame))
    # The AddTimeCode field will insert an integer framerate into the metadata, if the framerate is floating point, we need to correct this
    metadataNode.addMetadata([("input/frame_rate",framerate.toFloat())])

    script.addNode(metadataNode)

    # Generate Write nodes for nuke renders.

    for node in writeNodes:
      script.addNode(node)

    # Check Hiero Version.
    if hiero.core.env.get('VersionMajor') < 11:  
      # add a viewer
      viewerNode = nuke.Node("Viewer")

      # Bug 45914: If the user has for some reason selected a custom OCIO config, but then set the 'Use OCIO nodes when export' option to False,
      # don't set the 'viewerProcess' knob, it's referencing a LUT in the OCIO config which Nuke doesn't know about
      setViewerProcess = True
      if not self._projectSettings['lutUseOCIOForExport'] and self._projectSettings['ocioConfigPath']:
        setViewerProcess = False

      if setViewerProcess:
        # Bug 45845 - default viewer lut should be set in the comp
        from hiero.exporters.FnNukeShotExporter import _toNukeViewerLutFormat
        viewerLut = _toNukeViewerLutFormat(self._projectSettings['lutSettingViewer'])
        viewerNode.setKnob("viewerProcess", viewerLut)
    else:
      from hiero.exporters.FnExportUtil import createViewerNode
      viewerNode = createViewerNode(self._projectSettings)

    script.addNode( viewerNode )

    # Create pre-comp nodes for external annotation scripts
    annotationsNodes = self._createAnnotationsPreComps()
    if annotationsNodes:
      script.addNode(annotationsNodes)

    scriptFilename = self.resolvedExportPath()
    hiero.core.log.debug( "Writing Script to: %s", scriptFilename )

    # Call callback before writing script to disk (see _beforeNukeScriptWrite definition below)
    self._beforeNukeScriptWrite(script)

    script.popLayoutContext()

    # Layout the script
    FnScriptLayout.scriptLayout(script)

    script.writeToDisk(scriptFilename)
    #if postProcessScript has been set to false, don't post process
    #it will be done on a background thread by create comp
    #needs to be done as part of export task so that information
    #is added in hiero workflow
    if self._preset.properties().get("postProcessScript", True):
      error = postProcessor.postProcessScript(scriptFilename)
      if error:
        hiero.core.log.error( "Script Post Processor: An error has occurred while preparing script:\n%s", scriptFilename )
    # Nothing left to do, return False.
    return False


  @FnAssetAPI.core.decorators.debugCall
  def __getTargetEntityForScript(self, item, context):

    ## @todo Do we need to always try and make this the shot, or is it actually
    ## more meaningful for the manager to get the source media? We need to look
    ## into this. There are pros and cons. Supplying the media makes more work
    ## in register(). As we try and supply the _item in the locale, then in
    ## theory this information is still available. Espeicially if in the Host
    ## we expose 'refForItem'. If we did give the Image entity, this is also a
    ## lot of work for the Manager, as it needs to check the locale - as it
    ## could be a comp script for Write node, which has a completely different
    ## meaning.
    ## For now, we'll attempt to find the Shot or nothing, to make their lives
    ## easier! Means its important they implement ParentGroupingRelationship
    ## properly though.
    entity = None


    # If the item in managed, the simply get its entity ref - as its a
    # TrackItem, it should be the applicable shot, or nothing.
    entity = assetApiUtils.entity.entityFromObj(item)

    if not entity and isinstance(item, hiero.core.TrackItem):
      # Try and find a shot by looking under a shot parent (sequence) that we
      # might already know about, for a shot with this name
      sequenceEntity = assetApiUtils.defaults.getDefaultParentEntityForShots(
        [item,], context)

      if sequenceEntity:
        shotItem = items.HieroShotTrackItem(item)
        shotSpec = shotItem.toSpecification()
        # This always returns an array of arrays
        shots = sequenceEntity.getRelatedEntities([shotSpec,], context=context)[0]
        if shots:
          entity = shots[0]

    if not entity:
      # Finally try to fall back and find an asset underneath
      anEntity = assetApiUtils.entity.anEntityFromObj(item, includeChildren=True,
          includeParents=False)

      if anEntity:
        shotSpec = FnAssetAPI.specifications.ShotSpecification()
        shots = anEntity.getRelatedEntities([shotSpec,], context=context)[0]
        if shots:
          entity = shots[0]

    return entity


  def __doWriteScript(self, script, path):
      hiero.core.log.debug( "Writing Script to: %s", path )
      script.writeToDisk(path)
      return path


  def __doWriteScriptToAsset(self, script, targetEntity, nameHint, defaultPath):

    # we use a standard file item to take care of the path manipulation/hints
    fileItem = FnAssetAPI.items.FileItem()
    fileItem.path = defaultPath
    spec = FnAssetAPI.specifications.NukeScriptSpecification()
    spec = fileItem.toSpecification(spec)
    # Override the name hint - as it will have a version number in etc...
    ## @todo Whats a good name here?
    spec.nameHint = nameHint if nameHint else "compScript"

    def workFn(path):
      return self.__doWriteScript(script, path if path else defaultPath)

    if not self._context:
      session = FnAssetAPI.SessionManager.currentSession()
      self._context = session.createContext()

    with self._context.scopedOverride():

      self._context.locale = specifications.HieroNukeScriptExportLocale()
      self._context.locale.role = constants.kHieroExportRole_Comp
      self._context.locale.scope = constants.kHieroExportScope_TrackItem
      self._context.locale.objects = [self._item,]

      entity = assetApiUtils.publishing.publishSingle(workFn, spec, targetEntity)

      # We can't do this up front in updateItem, as we don't know the final
      # entity reference So we have to cheat a bit, as were now in another
      # thread...
      def setScriptMetadata():
        self._tag.metadata().setValue("tag.script", entity.reference)

      hiero.core.executeInMainThreadWithResult(setScriptMetadata)


  def _beforeNukeScriptWrite(self, script):
    """ Call-back method introduced to allow modifications of the script object before it is written to disk.
    Note that this is a bit of a hack, please speak to the AssetMgrAPI team before improving it. """

    if self._preset.properties()["useAssets"]:
      # Allow registered listeners to work with the script
      manager = FnAssetAPI.Events.getEventManager()
      ## @todo Assuming that we're always on a thread for now, this should be verified
      manager.blockingEvent(False, 'hieroToNukeScriptBeforeWrite', self._item, script)
