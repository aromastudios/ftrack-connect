import hiero.core
import itertools

from FnNukeShotExporter import NukeShotExporter
import _nuke # import _nuke so it does not conflict with hiero.core.nuke


class NukeShotPreset(hiero.core.TaskPresetBase):
  def __init__(self, name, properties, task=NukeShotExporter):
    """Initialise presets to default values"""
    hiero.core.TaskPresetBase.__init__(self, task, name)

    # Set any preset defaults here
    self.properties()["enable"] = True
    self.properties()["readPaths"] = []
    self.properties()["writePaths"] = []
    self.properties()["collateTracks"] = False
    self.properties()["collateShotNames"] = False
    self.properties()["annotationsPreCompPaths"] = []
    self.properties()["includeAnnotations"] = False
    self.properties()["showAnnotations"] = True
    self.properties()["includeEffects"] = True

    # If True, tracks other than the master one will not be connected to the write node
    self.properties()["connectTracks"] = False

    # Asset properties
    self.properties()["useAssets"] = True
    self.properties()["publishScript"] = True

    # Not exposed in UI
    self.properties()["collateSequence"] = False  # Collate all trackitems within sequence
    self.properties()["collateCustomStart"] = True  # Start frame is inclusive of handles

    self.properties()["additionalNodesEnabled"] = False
    self.properties()["additionalNodesData"] = []
    self.properties()["method"] = "Blend"

    # Add property to control whether the exporter does a postProcessScript call.
    # This is not in the UI, and is only changed by create_comp.  See where this is accessed
    # in _taskStep() for more details.
    self.properties()["postProcessScript"] = True

    # Update preset with loaded data
    self.properties().update(properties)

  def addCustomResolveEntries(self, resolver):
    if _nuke.env['nc']:
      resolver.addResolver("{ext}", "Extension of the file to be output", "nknc")
    else:
      resolver.addResolver("{ext}", "Extension of the file to be output", "nk")

  def supportedItems(self):
    return hiero.core.TaskPresetBase.kAllItems

  def propertiesForPathCallbacks(self):
    """ Get a list of properties used for path callbacks """
    return (self.properties()["readPaths"],
            self.properties()["writePaths"],
            self.properties()["annotationsPreCompPaths"])

  def initialiseCallbacks(self, exportStructure):
    """ Reimplemented.  This preset contains paths which reference other
    elements in the export structure.  Registers callbacks which update
    those paths when they change in the UI.
    """

    # TODO This whole mechanism is unreliable and confusing for users.  It could
    # do with a redesign.
    for path in itertools.chain(*self.propertiesForPathCallbacks()):
      element = exportStructure.childElement(path)
      if element is not None:
        element.addPathChangedCallback(self.onElementPathChanged)

  def onElementPathChanged(self, oldPath, newPath):
    """ Callback when the path for an element changes.  This updates the paths
    referencing other tasks for read/write/annotations.
    """
    for pathlist in self.propertiesForPathCallbacks():
      for path in pathlist:
        if path == oldPath:
          pathlist.remove(oldPath)
          pathlist.append(newPath)

#
hiero.core.log.debug("Registering NukeShotExporter")
hiero.core.taskRegistry.registerTask(NukeShotPreset, NukeShotExporter)
