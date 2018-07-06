# -*- coding: utf-8 -*-

"""Punch addToNukeScript() functions into core classes to add equivalent Nuke nodes to a given script."""

import hiero.core
from hiero.core import (Clip,
                        Sequence,
                        TrackItem,
                        VideoTrack,
                        Format,
                        Keys,
                        Transition,
                        Annotation,
                        AnnotationText,
                        AnnotationStroke,
                        EffectTrackItem)

from hiero.core.FnCompSourceInfo import (CompSourceInfo,
                                isNukeScript)
from hiero.core import nuke

import itertools
import math
import os
import copy

import FnAssetAPI

def _guidFromCloneTag(item):
  for tag in item.tags():
    if tag.name() == "Clone":
      return tag.metadata().value("tag.guid")
  return None


'''
    includeEffects=True, beforeBehaviour=None, afterBehaviour=None, project=None
'''


def _Clip_addToNukeScript(self, script, additionalNodes=None,
  additionalNodesCallback=None, firstFrame=None, trimmed=True,
  trimStart=None, trimEnd=None, useOCIO=False, colourTransform=None,
  metadataNode=None, includeMetadataNode=True, nodeLabel=None, enabled=True,
  includeEffects=True, beforeBehaviour=None, afterBehaviour=None, project=None,
  useEntityRefs=False):

  """
  addToNukeScript(self, script, trimmed=True, trimStart=None, trimEnd=None)

  Add a Read node to the Nuke script for each media sequence/file used in this clip. If there is no media, nothing is added.

  @param script: Nuke script object to add nodes @param additionalNodes: List of nodes to be added post read
  @param additionalNodesCallback: callback to allow custom additional node per item function([Clip|TrackItem|Track|Sequence])
  @param firstFrame: Custom offset to move start frame of clip
  @param trimmed: If True, a FrameRange node will be added to trim the range output by the Read node.
    The range defaults to the clip’s soft trim range.
    If soft trims are not enabled on the clip, the range defaults to the clip range.
    The range can be overridden by passing trimStart and/or trimEnd values.
  @param trimStart: Override the trim range start with this value.
  @param trimEnd: Override the trim range end with this value.
  @param useOCIO: Use open colourIO nodes for colour space transform
  @param colourTransform: if specified, is set as the color transform for the clip
  @param metadataNode: node containing metadata to be inserted into the script
  @param includeMetadataNode: specifies whether a metadata node should be added to the script
  @param nodeLabel: optional label for the Read node
  @param enabled: enabled status of the read node. True by default
  @param includeEffects: if True, soft effects in the clip are included
  @param beforeBehaviour: What to do for frames before the first ([hold|loop|bounce|black])
  @param afterBehaviour: What to do for frames after the last ([hold|loop|bounce|black])
  """

  hiero.core.log.debug( "trimmed=%s, trimStart=%s, trimEnd=%s, firstFrame=%s" % (str(trimmed), str(trimStart), str(trimEnd), str(firstFrame)) )
  # Check that we are on the right type of object, just to be safe.
  assert isinstance(self, Clip), "This function can only be punched into a Clip object."

  added_nodes = []

  source = self.mediaSource()

  if source is None:
    # TODO: Add a constant here so that offline media has some representation within the nuke scene.
    # For now just do nothing
    return added_nodes

  # MPLEC TODO
  # Currently, on ingest only one source media element is added to the Clip timeline.
  # However it is possible for the Clip timeline to contain multiple track items.
  # We don't currently allow other source media to be added (though stereo will do this)
  # but users can cut/trim/etc on the one that's there so this needs to be smarter.
  # It will need to do the same thing as the timeline build-out does, with multiple
  # tracks, AppendClips, gap filling -- the whole routine. Should be able to share that?
  for fi in source.fileinfos():
    quicktime = hiero.core.isQuickTimeFileExtension(os.path.splitext(fi.filename().lower())[1])

    # Get start frame. First frame of an image sequence. Zero if quicktime/r3d
    startFrame = self.sourceIn()
    hiero.core.log.debug( "startFrame: " + str(startFrame) )

    # Initialise to the source length, starting at the first frame of the media.
    start = startFrame
    end = start + self.duration()-1
    # Trim if soft trims are available and requested or they specified a trim range.
    if trimmed:
      # Everything within Hiero is zero-based so add file start frame to get real frame numbers at end.
      if self.softTrimsEnabled():
        start = self.softTrimsInTime()
        end = self.softTrimsOutTime()

      # Offset the trim range by the source.startTime() since the user sees frame numbers
      # on Sequences (including Clips) in the UI start numbering from 0.
      if trimStart is not None:
        start = trimStart + startFrame
      if trimEnd is not None:
        end = trimEnd + startFrame

    # Quicktime files in Nuke must always start at frame 1.
    # Hiero Starts at frame 0.. so adjust if Read file has .mov or .MOV extension
    if quicktime:
      start += 1
      end += 1

    # Grab clip format
    format = self.format()
    clipMetadata = self.metadata()
     # Get the filename, or an entity ref if one is present
    filename = fi.filename()
     ## @todo Re-enable when Nuke supports entity refs again
    if False and useEntityRefs and hasattr(self, 'entityReference'):
      entityRef = self.entityReference()
      if entityRef:
        filename = entityRef

    hiero.core.log.debug( "- adding Nuke node for:%s %s %s", filename, start, end )

    isRead = False
		## @todo This also needs updating when nuke supports refs, as we'd need to resolve the 
		## reference to see the ending, or some such...
    if filename.endswith( '.nk' ):
      read_node = nuke.PrecompNode( filename )
    else:
      read_node = nuke.ReadNode( filename, format.width(), format.height(), format.pixelAspect(), round(start), round(end), clipMetadata=clipMetadata )
      if firstFrame is not None:
        read_node.setKnob("frame_mode", 'start at')
        read_node.setKnob("frame", firstFrame)
      isRead = True


    # If a node name has been specified
    if nodeLabel is not None:
      read_node.setKnob("label", nodeLabel)

    if script is not None:
      script.addNode(read_node)

    if useEntityRefs:
      manager = FnAssetAPI.Events.getEventManager()
      ## @todo Assuming that we're always on a thread for now, this should be verified
      manager.blockingEvent(False, 'hieroToNukeScriptAddClip', self, filename, read_node, script)

    added_nodes.append(read_node)

    if not isRead and firstFrame is not None:

      timeClip = nuke.TimeClipNode( round(start), round(end), round(firstFrame) )
      added_nodes.append( timeClip )

    
    # Pull the colourspace from the Clip Metadata, rather than the sourceMediaColourTransform() function
    # Because sourceMediaColourTransform()  will return the gammaspace for red/arri clips.
    if colourTransform is None and "clip.properties.colourspacename" in clipMetadata:
      colourTransform = clipMetadata["clip.properties.colourspacename"]
      # Don't set knob, if set to default.
      if colourTransform.startswith("default"):
        colourTransform = None    
    
    if colourTransform is not None:
      # Don't add ocio nodes for these file types
      ocioExclusionList = [ "r3d", "ari", "arri", "arriraw" ]
      fileExtension = os.path.splitext(fi.filename())[1][1:].lower()
      # Handle OCIO colour transforms
      if useOCIO is True and fileExtension not in ocioExclusionList:

        # Make sure the read node is not applying a LUT
        read_node.setKnob("colorspace", "linear")

        colourTransformGroup = hiero.core.LUTGroup(colourTransform)
        if colourTransformGroup:
          colourTransform = "%s/%s" % (colourTransformGroup, colourTransform)  
        
        # Add a OCIO colour 
        ocioNode = nuke.Node("OCIOColorSpace", in_colorspace=colourTransform)
        if script is not None:
          script.addNode(ocioNode)
        added_nodes.append(ocioNode)
      else:
        # Apply colour Transform override
        if isRead:
          read_node.setKnob("colorspace", colourTransform)


    if not enabled:
      read_node.setKnob("disable", True)
      # If we disable the read node, we need to add some channels else the write node will error
      add_channels_node = nuke.Node("AddChannels", channels="rgb")
      if script is not None:
        script.addNode(add_channels_node)
      added_nodes.append(add_channels_node)

    if metadataNode is None:
      metadataNode = nuke.MetadataNode()
      if script is not None:
        script.addNode(metadataNode)
      added_nodes.append(metadataNode)
      metadataNode.setInputNode(0, read_node)

    metadataNode.addMetadata([("hiero/clip", self.name()), ("hiero/clip_guid", _guidFromCloneTag(self))])
    # Also set the reel name (if any) on the metadata key the dpx writer expects for this.
    if Keys.kSourceReelId in clipMetadata:
      reel = clipMetadata[Keys.kSourceReelId]
      if len(reel):
        metadataNode.addMetadata( [ ("hiero/reel", reel), ('dpx/input_device', reel), ('quicktime/reel', reel) ] )

    # Add Tags to metadata
    metadataNode.addMetadata([ ("\"hiero/tags/" + tag.name() + "\"", tag.name()) for tag in self.tags()])
    metadataNode.addMetadata([ ("\"hiero/tags/" + tag.name() + "/note\"", tag.note()) for tag in self.tags()])

    postReadNodes = []
    if callable(additionalNodesCallback):
      postReadNodes.extend(additionalNodesCallback(self))

    if additionalNodes is not None:
      postReadNodes.extend(additionalNodes)

    prevNode = metadataNode
    for node in postReadNodes:
      # Add additional nodes
      if node is not None:
        node = copy.deepcopy(node)
        node.setInputNode(0, prevNode)
        prevNode = node

        # Disable additional nodes too (in particular the Shuffle which controls the mask used to merge layers)
        if not enabled:
          node.setKnob("disable", "true")

        added_nodes.append(node)
        if script is not None:
          script.addNode(node)


  return added_nodes


Clip.addToNukeScript = _Clip_addToNukeScript


def _TrackItem_getTransitions(trackItem):
    # Check for transitions
  inTransition, outTransition = trackItem.inTransition(), trackItem.outTransition()

  return inTransition, outTransition


def _TrackItem_addToNukeScript(self, script, firstFrame=None,
    additionalNodes=[], additionalNodesCallback=None, includeRetimes=False,
    retimeMethod=None, startHandle=None, endHandle=None, trimStart=None,
    useOCIO=False, colourTransform=None, offset=0, nodeLabel=None, includeAnnotations=False,
    includeEffects=True, outputToSequenceFormat=False,
    useEntityRefs=False):
  """This is a variation on the Clip.addToNukeScript() method that remaps the
  Read frame range to the range of the this TrackItem rather than the Clip's
  range. TrackItem retimes and reverses are applied via Retime and OFlow nodes
  if needed. The additionalNodes parameter takes a list of nodes to add before
  the source material is shifted to the TrackItem timeline time and trimmed to
  black outside of the cut. This means timing can be set in the original
  source range and adding channels, etc won't affect frames outside the cut
  length.

  @param retimeMethod: "Motion", "Blend", "Frame" - Knob setting for OFlow retime method
  @param offset: Optional, Global frame offset applied across whole script
  """

  # Check that we are on the right type of object, just to be safe.
  assert isinstance(self, TrackItem), "This function can only be punched into a TrackItem object."

  hiero.core.log.debug( "Add TrackItem (%s) to script, startHandle = %s, endHandle = %s, firstFrame=%s" % (self.name(), str(startHandle), str(endHandle), str(firstFrame)) )

  added_nodes = []

  retimeRate = 1.0
  if includeRetimes:
    retimeRate = self.playbackSpeed()

  # Compensate for retime in HandleLength!!
  if startHandle is None:
    startHandle = 0
  if endHandle is None:
    endHandle = 0

  # Check for transitions
  inTransition, outTransition = _TrackItem_getTransitions(self)
  inTransitionHandle, outTransitionHandle = 0, 0
  
  # Adjust the clips to cover dissolve transition
  if outTransition is not None:
    if outTransition.alignment() == Transition.kDissolve:
      # Calculate the delta required to move the end of the clip to cover the dissolve transition
      outTransitionHandle = (outTransition.timelineOut() - self.timelineOut())
  if inTransition is not None:
    if inTransition.alignment() == Transition.kDissolve:
      # Calculate the delta required to move the beginning of the clip to cover the dissolve transition
      inTransitionHandle = (self.timelineIn() - inTransition.timelineIn())
      

  
  # If the clip is reversed, we need to swap the start and end times
  start = min(self.sourceIn(), self.sourceOut())
  end = max(self.sourceIn(), self.sourceOut())  
  
  # Extend handles to incorporate transitions
  # If clip is reversed, handles are swapped
  if retimeRate >= 0.0:
    inHandle = startHandle + inTransitionHandle
    outHandle = endHandle + outTransitionHandle
  else:
    inHandle = startHandle + outTransitionHandle
    outHandle = endHandle + inTransitionHandle
  
  clip = self.source()
  # Recalculate handles clamping to available media range
  readStartHandle = min(start,  math.ceil(inHandle * abs(retimeRate) ))
  readEndHandle = min((clip.duration() - 1) - end ,  math.ceil(outHandle * abs(retimeRate) ))
  
  hiero.core.log.debug ( "readStartHandle", readStartHandle, "readEndHandle", readEndHandle )
    
  # Add handles to source range    
  start -= readStartHandle
  end += readEndHandle
  
  
  # Read node frame range
  readStart, readEnd = start, end
  # First frame identifies the starting frame of the output. Defaults to timeline in time
  readNodeFirstFrame = firstFrame
  if readNodeFirstFrame is None:
    readNodeFirstFrame = self.timelineIn() -  min( min(self.sourceIn(), self.sourceOut()), inHandle)
  else:
    # If we have trimmed the handles, bump the start frame up by the difference
    readNodeFirstFrame += round(inHandle * abs(retimeRate)) - readStartHandle
  
  # trim start is used to trim the beginning of the read when applying a fade in
  if trimStart:
    readStart += trimStart
    readNodeFirstFrame += trimStart
  
  # Apply global offset
  readNodeFirstFrame+=offset


  # Create a metadata node
  metadataNode = nuke.MetadataNode()
  reformatNode = None

  # Add TrackItem metadata to node
  metadataNode.addMetadata([("hiero/shot", self.name()), ("hiero/shot_guid", _guidFromCloneTag(self))])
  
  # Add Tags to metadata
  metadataNode.addMetadata([("\"hiero/tags/" + tag.name() + "\"", tag.name()) for tag in self.tags()])
  metadataNode.addMetadata([("\"hiero/tags/" + tag.name() + "/note\"", tag.note()) for tag in self.tags()])

  # Add Track and Sequence here as these metadata nodes are going to be added per clip/track item. Not per sequence or track.
  if self.parent():
    metadataNode.addMetadata([("hiero/track", self.parent().name()), ("hiero/track_guid", _guidFromCloneTag(self.parent()))])
    if self.parentSequence():
      metadataNode.addMetadata([("hiero/sequence", self.parentSequence().name()), ("hiero/sequence_guid", _guidFromCloneTag(self.parentSequence()))])

      # If we have clip and we're in a sequence then we output the reformat settings as another reformat node.
      reformat = self.reformatState()
      if reformat.type() != nuke.ReformatNode.kDisabled:
        seq = self.parent().parent()
        seqFormat = seq.format()

        formatString = "%i %i 0 0 %i %i %f %s" % (seqFormat.width(), seqFormat.height(), seqFormat.width(), seqFormat.height(), seqFormat.pixelAspect(), seqFormat.name())

        reformatNode = nuke.ReformatNode(resize=reformat.resizeType(), center=reformat.resizeCenter(), flip=reformat.resizeFlip(), flop=reformat.resizeFlop(), turn=reformat.resizeTurn(), to_type=reformat.type(), format=formatString, scale=reformat.scale())


  # Capture the clip nodes without adding to the script, so that we can group them as necessary
  clip_nodes = clip.addToNukeScript( None, firstFrame=readNodeFirstFrame,
      trimmed=True, trimStart=readStart, trimEnd=readEnd, useOCIO=useOCIO,
      colourTransform=colourTransform, metadataNode=metadataNode,
      nodeLabel=nodeLabel, enabled=self.isEnabled(), useEntityRefs=useEntityRefs)

  # Add the read node to the script
  # This assumes the read node will be the first node
  read_node = clip_nodes[0]
  if script:
    script.addNode(read_node)
  added_nodes.append(read_node)

  # Create a group to encapsulate all of the additional nodes
  clip_group = nuke.GroupNode("HieroData")
  clip_group.addNode(nuke.Node("Input", inputs=0))
  if script:
    script.addNode(clip_group)
  added_nodes.append(clip_group)

  # Add all other clip nodes to the group
  for node in clip_nodes[1:]:
    clip_group.addNode(node)

  # Add reformat node
  if reformatNode is not None:
    clip_group.addNode(reformatNode)

  # Add metadata node
  clip_group.addNode(metadataNode)

  first_frame=start
  last_frame=end

  # Calculate the frame range, != read range as read range may be clamped to available media range
  if firstFrame is not None:
    # if firstFrame is specified
    last_frame =  firstFrame + (startHandle + inTransitionHandle) + (self.duration() -1) + (endHandle + outTransitionHandle)
    hiero.core.log.debug( "last_frame(%i) =  firstFrame(%i) + startHandle(%i) + (self.duration() -1)(%i) + endHandle(%i)" % (last_frame, firstFrame, startHandle + inTransitionHandle, (self.duration() -1), endHandle + outTransitionHandle) )
    first_frame = firstFrame
  else:
    # if firstFrame not specified, use timeline time
    last_frame =  self.timelineIn() + (self.duration() -1) + (endHandle + outTransitionHandle)
    first_frame = (self.timelineIn() - (startHandle + inTransitionHandle))
    hiero.core.log.debug( "first_frame(%i) =  self.timelineIn(%i) - (startHandle(%i) + inTransitionHandle(%i)" % (first_frame, self.timelineIn(), startHandle, inTransitionHandle) )
    
    
  if trimStart:
    first_frame += trimStart

  # This parameter allow the whole nuke script to be shifted by a number of frames
  first_frame += offset
  last_frame += offset
  
  # Frame range is used to correct the range from OFlow
  framerange = nuke.Node("FrameRange", first_frame=first_frame, last_frame=last_frame)
  framerange.setKnob('label', 'Set frame range to [knob first_frame] - [knob last_frame]')
  added_nodes.append(framerange)
  clip_group.addNode(framerange)

  # Add Additional nodes.
  postReadNodes = []
  if callable(additionalNodesCallback):
    postReadNodes.extend(additionalNodesCallback(self))
  if additionalNodes is not None:
    postReadNodes.extend(additionalNodes)

  # Add any additional nodes.
  for node in postReadNodes:
    if node is not None:
      node = copy.deepcopy(node)
      # Disable additional nodes too (in particular the Shuffle which controls the mask used to merge layers)
      if not self.isEnabled():
        node.setKnob("disable", True)

      added_nodes.append(node)
      clip_group.addNode(node)

  # If the clip is retimed we need to also add an OFlow node.
  if includeRetimes and retimeRate != 1 and retimeMethod != 'None':
    # Obtain keyFrames
    tIn, tOut = self.timelineIn(), self.timelineOut()
    sIn, sOut = self.sourceIn(), self.sourceOut()

    hiero.core.log.debug("sIn %f sOut %f tIn %i tOut %i" % (sIn, sOut, tIn, tOut))
    # Offset keyFrames, so that they match the input range (source times) and produce expected output range (timeline times)
    # timeline values must start at first_frame
    tOffset = (first_frame + startHandle + inTransitionHandle) - self.timelineIn()
    tIn += tOffset
    tOut += tOffset
    sOffset = readNodeFirstFrame - readStart
    sIn += sOffset
    sOut += sOffset
    
    hiero.core.log.debug("Creating OFlow:", tIn, sIn, tOut, sOut)
    # Create OFlow node for computed keyFrames
    keyFrames = "{{curve l x%d %f x%d %f}}" % (tIn, sIn, tOut, sOut)
    oflow = nuke.Node("OFXuk.co.thefoundry.time.oflow_v100", method="Blend", timing="Source Frame", timingFrame=keyFrames)

    # Override Retime Method
    if retimeMethod is not None:
      oflow.setKnob('method', retimeMethod)
    oflow.setKnob('label', 'retime ' + str(retimeRate))
    added_nodes.append(oflow)
    clip_group.addNode(oflow)

  clip_group.addNode(nuke.Node("Output"))

  return added_nodes

TrackItem.addToNukeScript = _TrackItem_addToNukeScript


def _addTrackSubTrackItems(itemFilter, track, script, offset, inputs, cliptype):
  """ Write out the sub-track items of type itemType for a track. """

  # Build a list of effects across all the sub-tracks
  items = [ item for item in itertools.chain(*track.subTrackItems()) if itemFilter(item) ]

  # Write them to the script.  If the track has no clips on it and the sequence is being written disconnected,
  # there might not be any inputs, after the first item is added set inputs to 1.
  added_nodes = []
  for item in items:
    itemNodes = item.addToNukeScript(script, offset, inputs, cliptype)
    added_nodes.extend(itemNodes)
    inputs=1

  return added_nodes


def _addEffectsAnnotationsForTrack(track, includeEffects, includeAnnotations, script, offset, inputs=1, cliptype=None):
  """ Write the soft effects and annotations for a given track. """

  added_nodes = []

  if includeAnnotations:
    annotationNodes = _addTrackSubTrackItems( lambda x: isinstance(x, Annotation), track, script, offset, inputs, cliptype )
    if annotationNodes:
      added_nodes.extend( annotationNodes )
      inputs = 1

  if includeEffects:

    ## first add metadata node so the sequence time is correct in case of retimes on the clips

    sequence = track.parent()
    timecodeStart = sequence.timecodeStart()
    try:
     firstFrame = sequence.inTime()
    except:
     firstFrame = 0
    timecodeFrame = timecodeStart + firstFrame - offset
    scriptFrame = firstFrame

    timecodeStr = hiero.core.Timecode.timeToString(timecodeFrame, sequence.framerate(), hiero.core.Timecode.kDisplayTimecode)

    metadataNode = nuke.MetadataNode()
    metadataNode.addMetadata( [   ("hiero/sequence/timecode", "[make_timecode %s %s %d]" % (timecodeStr, str(sequence.framerate()), scriptFrame) ) ] )
    script.addNode( metadataNode )

    # Add track level effects, not including ones linked to a track item.  Those are added in TrackItem.addToNukeScript
    added_nodes.extend( _addTrackSubTrackItems( lambda x: isinstance(x, EffectTrackItem) and not x.linkedItems(), track, script, offset, inputs, cliptype ) )

  return added_nodes


def _VideoTrack_addToNukeScript(self, script, additionalNodes=[],
    additionalNodesCallback=None, includeRetimes=False, retimeMethod=None,
    offset=0, useOCIO=False, skipOffline=True, mediaToSkip=[], disconnected=False, includeAnnotations=False,
    includeEffects=False, useEntityRefs=False):
  """Add a Read node for each track item to the script with AppendClip nodes
  to join them in a sequence. Blank Constants nodes are added to pad any gaps
  between clips.

  @param retimeMethod: "Motion", "Blend", "Frame" - Knob setting for OFlow retime method
  @param additionalNodesCallback: callback to allow custom additional node per item function([Clip|TrackItem|Track|Sequence])
  @param offset: Optional, Global frame offset applied across whole script
  """

  # Check that we are on the right type of object, just to be safe.
  assert isinstance(self, VideoTrack), "This function can only be punched into a VideoTrack object."

  added_nodes = []

  append_clip_nodes = []

  # Grab reformat node so that the same format can later be applied to Constant nodes
  reformat = None
  for node in additionalNodes:
    if node and node.type() == 'Reformat':
      reformat = node

  # Build the track by generating script for each TrackItem and adding blank Constant nodes
  # wherever there are gaps to keep the appended clips in the correct timing.
  lastInTime = self.parent().duration()
  lastTrackItem = None
  startingWithGap = False
  # Work backwards so that the AppendClip nodes hook up the right way around.
  for trackItem in reversed(self.items()):
    if not trackItem.source().mediaSource().isMediaPresent() and skipOffline:
      continue

    hiero.core.log.debug( "  - " + str(trackItem) )

    # Check for transitions
    inTransition, outTransition = _TrackItem_getTransitions(trackItem)

    fadeIn = inTransition and inTransition.alignment() == Transition.kFadeIn
    fadeOut = outTransition and outTransition.alignment() == Transition.kFadeOut


    # Fill any gap between previous item and this one.
    # This is backwards because we walk the list in reverse to get the
    # AppendClip nodes to join up properly.
    if lastInTime - trackItem.timelineOut() > 1:
      # The Constants for gaps are transparent so that lower tracks show
      # through just like they do in Hiero's viewer.
      start = trackItem.timelineOut()+1
      end = lastInTime-1
      gap = nuke.Node("Constant", first=start + offset, last=end + offset)
      gap.setKnob('label', 'fill gap [value first] - [value last]')
      if reformat is not None:
        gap.setKnob('format', reformat.knob('format'))
      added_nodes.append(gap)
      if script is not None:
        script.addNode(gap)

      if lastTrackItem is None:
        startingWithGap = True
      else:
        append = nuke.AppendClipNode(2, firstFrame=0)

        added_nodes.append(append)
        if script is not None:
          script.addNode(append)


    # Incase additional nodes is a Tuple, we need to be able to append.
    tiAdditionalNodes = list(additionalNodes)

    # Add the Read for this item.
    # Also create a shuffle node that sets the alpha to solid so that when the
    # tracks are stacked up the higher clips completely cover the lower ones.
    tiAdditionalNodes.append(nuke.Node("add_layer", track="track.mask"))

    shuffleNode = nuke.Node("Shuffle", red="white", out="track")
    # in is a reserved word, so add separately
    shuffleNode.setKnob("in", "none")
    tiAdditionalNodes.append(shuffleNode)
    if fadeOut:
      # Add constant frames to form the FadeOut from black
      black = nuke.Node("Constant", first=outTransition.timelineIn() + 1 + offset, last=outTransition.timelineOut() + 1 + offset)
      if reformat is not None:
        black.setKnob('format', reformat.knob('format'))

      added_nodes.append(black)
      if script is not None:
        script.addNode(black)

    # On a fade in trim the read by one frame to ensure first frame 100% black
    trimStart = 1 if fadeIn else None

    trackitem_nodes = trackItem.addToNukeScript(script,
        additionalNodes=tiAdditionalNodes,
        additionalNodesCallback=additionalNodesCallback, trimStart=trimStart,
        includeRetimes=includeRetimes, retimeMethod=retimeMethod,
        offset=offset, useOCIO=useOCIO, useEntityRefs=useEntityRefs)

    added_nodes = added_nodes + trackitem_nodes
    if lastTrackItem is not None or startingWithGap:
      append = nuke.AppendClipNode(2, firstFrame=0)
      # Has an out transition
      if outTransition is not None:
        # Dissolve
        if outTransition.alignment() == Transition.kDissolve:
          dissolveFrames = outTransition.timelineOut() - outTransition.timelineIn()
          if dissolveFrames > 1:
            dissolveFrames += 1
          append.setKnob('dissolve', dissolveFrames)
      append_clip_nodes.append(append)

    lastTrackItem = trackItem
    lastInTime = lastTrackItem.timelineIn()


    if fadeIn:
      # Add constant frames to form the FadeIn from black
      black = nuke.Node("Constant", first=inTransition.timelineIn() + offset, last=inTransition.timelineOut() + 1 + offset )
      if reformat is not None:
        black.setKnob('format', reformat.knob('format'))

      added_nodes.append(black)
      if script is not None:
        script.addNode(black)


      # Append Clip to FadeIn constant node
      append = nuke.AppendClipNode(2, firstFrame=0, dissolve=(inTransition.timelineOut() - inTransition.timelineIn()) + 1)
      added_nodes.append(append)
      if script is not None:
        script.addNode(append)

    if fadeOut:
      # Append Clip to fadeOut constant node
      append = nuke.AppendClipNode(2, firstFrame=0, dissolve=(outTransition.timelineOut() - outTransition.timelineIn()) + 1)
      added_nodes.append(append)
      if script is not None:
        script.addNode(append)


  # One last gap fill for the start of the track.
  if lastTrackItem is not None and lastInTime > 0:
    gap = nuke.Node("Constant", first=0, last=lastInTime-1 + offset)
    gap.setKnob('label', 'fill gap [value first] - [value last]')
    if reformat is not None:
      gap.setKnob('format', reformat.knob('format'))

    added_nodes.append(gap)
    if script is not None:
      script.addNode(gap)


    append = nuke.AppendClipNode(2, firstFrame=0)
    added_nodes.append(append)
    if script is not None:
      script.addNode(append)


  # Have to apply the append nodes in reverse order
  for node in reversed(append_clip_nodes):
    added_nodes.append(node)
    if script is not None:
      script.addNode(node)

  perTrackNodes = []
  if callable(additionalNodesCallback):
    perTrackNodes.extend(additionalNodesCallback(self))

  # Add any additional nodes.
  for node in perTrackNodes:
    if node is not None:
      added_nodes.append(node)
      if script is not None:
        script.addNode(node)

  return added_nodes


VideoTrack.addToNukeScript = _VideoTrack_addToNukeScript


def getConnectedDisconnectedTracks(sequence, masterTrackItem, disconnected, includeEffects, includeAnnotations):
  """ Helper function to determine the connected and disconnected tracks for the given sequence, master track item and disconnected setting. """
  connectedTracks = []
  disconnectedTracks = []

  tracks = []
  for track in sequence.videoTracks():

    # If the track has no TrackItems, check if it should be included based on the includeEffects and includeAnnotations settings.
    if not track.items():
      hasEffects, hasAnnotations = False, False
      for item in itertools.chain(*track.subTrackItems()):
        if isinstance(item, Annotation):
          hasAnnotations = True
        elif isinstance(item, EffectTrackItem):
          hasEffects = True

      if (not includeAnnotations and hasAnnotations and not hasEffects) or (not includeEffects and hasEffects and not hasAnnotations):
        continue

    tracks.append(track)

  # If the disconnected parameter is not True, or no masterTrackItem was given, all tracks are connected.
  if disconnected and masterTrackItem:
    # A track is connected if:
    # a) it contains the master track item, or
    # b) it only has effects/annotations, and it is above the master track
    # c) blending is enabled

    masterTrack = masterTrackItem.parentTrack()

    for track in tracks:
      isMaster = (track == masterTrack)
      isEffectsOnly = (not track.items() and len(connectedTracks) > 0)
      isBlended = track.isBlendEnabled()

      if isMaster or isEffectsOnly or isBlended:
        connectedTracks.append(track)
      else:
        disconnectedTracks.append(track)

  else:
    connectedTracks = tracks

  return connectedTracks, disconnectedTracks


def _Sequence_addToNukeScript(self,
    script = nuke.ScriptWriter(),
    additionalNodes=[],
    additionalNodesCallback=None,
    includeRetimes=False,
    retimeMethod=None,
    offset=0,
    useOCIO=False,
    skipOffline=True,
    mediaToSkip=[],
    disconnected=False,
    masterTrackItem=None,
    includeAnnotations=False,
    includeEffects=True,
    outputToFormat=None,
    useEntityRefs = False
    ):
  """addToNukeScript(self, script)
  @param script: Nuke script object to add nodes to.
  @param includeRetimes: True/False include retimes
  @param retimeMethod: "Motion", "Blend", "Frame" - Knob setting for OFlow retime method
  @param additionalNodesCallback: callback to allow custom additional node per item function([Clip|TrackItem|Track|Sequence])
  @param offset: Optional, Global frame offset applied across whole script
  @param useOCIO: If True, use open colourIO nodes for colour space transform
  @param skipOffline: If True, offline clips are not included in the export
  @param mediaToSkip: List of MediaSources which should be excluded from the export
  @param disconnected: If True, tracks other than that containing the masterTrackItem are not connected to any inputs
  @param masterTrackItem: Used for controlling the script output if disconnected is specified
  @param includeAnnotations: If True, annotations are included in the exported script
  @param includeEffects: If True, soft effects are included in the exported script
  @param outputToFormat: Format to use for output.  If not specified, the sequence's own format is used.
  @return: None

  Add nodes representing this Sequence to the specified script.
  If there are no clips in the Sequence, nothing is added."""

  # Check that we are on the right type of object, just to be safe.
  assert isinstance(self, Sequence), "This function can only be punched into a Sequence object."

  added_nodes = []

  hiero.core.log.debug( '<'*10 + "Sequence.addToNukeScript()" + '>'*10 )
  previousTrack = None


  # First write the tracks in reverse order.  When it comes to detemining the inputs for the merges below,
  # Nuke uses a stack.  We also need to add each track's annotations and soft effects in the right place.
  # Effects/annotations on a track which also has clips should only apply to that track, so are added before the
  # track is merged.  Otherwise they should apply to all the tracks below, so are added after.
  # So for example if there are 4 tracks (Video 1, Video 2, Effects 1, Video 3) then the order is as follows:
  #   Video 3
  #   Video 3 annotations
  #   Video 3 effects
  #   Video 2
  #   Video 2 annotations
  #   Video 2 effects
  #   Video 1
  #   Video 1 annotations
  #   Video 1 effects
  #   Merge track 2 over track 1
  #   Effects 1
  #   Merge track 3 over track 2
  #   Write

  # If there is an output format specified, to make sure effects and annotations appear in the right place,
  # they should have their 'cliptype' knob set to 'bbox'.
  effectsClipType = "bbox" if outputToFormat else None

  tracksWithVideo = set()

  # If layout is disconnected, only the 'master' track is connected to the Write node, any others
  # will be placed in the script but with clips disconnected.  To make this work, connected tracks
  # needs to be written last, so re-order the list. Effects/annotations which apply to the master track
  # also need to be connected

  connectedTracks, disconnectedTracks = getConnectedDisconnectedTracks(self, masterTrackItem, disconnected, includeEffects, includeAnnotations)
  tracks = connectedTracks + disconnectedTracks

  # First write out the tracks and their annotations in reverse order, as described above
  for track in reversed(tracks):
    trackDisconnected = track in disconnectedTracks

    # Add the track and whether it is disconnected as data to the layout context
    script.pushLayoutContext("track", track.name(), track=track, disconnected=trackDisconnected)

    # If the track has any clips, write them and the effects out.
    trackItems = track.items()
    if len(trackItems) > 0:
      track_nodes = track.addToNukeScript(script,
                                         additionalNodes=additionalNodes,
                                         additionalNodesCallback=additionalNodesCallback,
                                         includeRetimes=includeRetimes,
                                         retimeMethod=retimeMethod,
                                         offset=offset,
                                         useOCIO=useOCIO,
                                         skipOffline=skipOffline,
                                         mediaToSkip=mediaToSkip,
                                         disconnected=trackDisconnected,
                                         includeAnnotations=includeAnnotations,
                                         includeEffects=includeEffects,
                                         useEntityRefs=useEntityRefs)
      added_nodes = added_nodes + track_nodes

      added_nodes.extend( _addEffectsAnnotationsForTrack(track, includeEffects, includeAnnotations, script, offset, cliptype=effectsClipType) )

      tracksWithVideo.add(track)

    elif trackDisconnected:
      added_nodes.extend( _addEffectsAnnotationsForTrack(track, includeEffects, includeAnnotations, script, offset, inputs=0, cliptype=effectsClipType) )

    script.popLayoutContext()

  # Add a 'Background' Constant node, which will assure that there are channels available for the full duration of
  # the sequence.  Otherwise gaps in the timeline could end up with no channels, because the Constants used for those
  # do not add any
  backgroundConstantNode = None

  # Now iterate over the tracks in order, writing merges and their soft effects
  previousTrack = None
  for track in tracks:
    script.pushLayoutContext("track", track.name(), track=track)

    trackDisconnected = track in disconnectedTracks

    if not trackDisconnected:
      # We need a merge if this track contains any clips, if it's the first track it will go over
      # the background Constant node added above
      #
      # If blending is enabled, a Merge node is created, otherwise Copy.
      if track in tracksWithVideo:
        merge = nuke.MergeNode() if track.isBlendEnabled() else nuke.CopyNode()
        if previousTrack:
          merge.setKnob( 'label', track.name()+' over '+previousTrack.name() )
        else:
          merge.setKnob( 'label', track.name() )

        if not backgroundConstantNode:
          backgroundConstantNode = nuke.ConstantNode(max(0, offset), self.duration()-1+offset, channels="rgb", label="Background", format=str(self.format()))
          script.addNode(backgroundConstantNode)
          added_nodes.append(backgroundConstantNode)
          backgroundConstantNode.setAlignToNode(merge)

        script.addNode(merge)
        added_nodes.append(merge)

      # If there were no clips on the track, write the effects and annotations after the merge so they get applied to the tracks below
      else:
        added_nodes.extend( _addEffectsAnnotationsForTrack(track, includeEffects, includeAnnotations, script, offset, cliptype=effectsClipType) )

    script.popLayoutContext()

    previousTrack = track

  # If an output format is specified, add a reformat node at the end.  Put this in the layout of the last connected track
  if outputToFormat:
    script.pushLayoutContext("track", connectedTracks[-1].name())
    added_nodes.append( outputToFormat.addToNukeScript(script, resize=nuke.ReformatNode.kResizeNone, black_outside=False) )
    script.popLayoutContext()

  perSequenceNodes = []
  if callable(additionalNodesCallback):
    perSequenceNodes.extend(additionalNodesCallback(self))

  # Add any additional nodes.
  for node in perSequenceNodes:
    if node is not None:
      added_nodes.append(node)
      script.addNode(node)

  # Add crop node with Sequence Format parameters
#  format = self.format()
#  crop = nuke.Node("Crop", box=('{0 0 %i %i}' % (format.width(), format.height())),  reformat='true' )
#  script.addNode(crop)
#  added_nodes.append(crop)

  return added_nodes

Sequence.addToNukeScript = _Sequence_addToNukeScript


def  _Format_addToNukeScript(self, script=None, resize=nuke.ReformatNode.kResizeWidth, black_outside=True):
  """self.addToNukeScript(self, script, to_type) -> adds a Reformat node matching this Format to the specified script and returns the nuke node object.

  @param script: Nuke script object to add nodes to, or None to just generate and return the node.
  @param resize: Type of resize (use constants from nuke.ReformatNode, default is kResizeWidth).
  @parm black_outside: Value for the black_outside knob.
  @return: hiero.core.nuke.ReformatNode object
  """
  #Build the string representing the reformat
  formatstring = "%i %i 0 0 %i %i %f %s" % (self.width(), self.height(), self.width(), self.height(), self.pixelAspect(), self.name())
  #Add Reformat node to script
  reformatNode = nuke.ReformatNode(resize=resize, to_type=nuke.ReformatNode.kToFormat, format=formatstring,  black_outside=black_outside)
  if script is not None:
    script.addNode(reformatNode)

  return reformatNode

Format.addToNukeScript = _Format_addToNukeScript



def offsetNodeAnimationFrames(node, offset):
  """ Iterate over all the knobs in a Nuke node, offsetting the key frame numbers. """

  if offset == 0:
    return

  isTimeWarp = node.Class() == "TimeWarp"
  for knob in node.knobs().values():

    # Some knobs can have isAnimated True, but not actually have an animations() method.
    # This happens if the user chooses if for example 'Set key on all knobs'.
    # Swallow any exceptions that occur due to these issues.
    try:
      # If this is a link knob, need to modify the knob being linked to
      if isinstance(knob, _nuke.Link_Knob):
        knob = knob.getLinkedKnob()

      if knob.isAnimated():
        for curve in knob.animations():
          for key in curve.keys():
            key.x = key.x + offset
            if isTimeWarp and knob.name() == "lookup":
              # time warp maps input frames to output so we need to adjust both the x and y curves
              key.y = key.y + offset
    except:
      pass