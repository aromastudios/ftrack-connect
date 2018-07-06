from FnAssetAPI.implementation import ManagerPlugin

class FTrackPlugin(ManagerPlugin):

  @classmethod
  def getIdentifier(cls):
    from FTrackInterface import FTrackInterface
    return FTrackInterface.kIdentifier

  @classmethod
  def getInterface(cls):
    from FTrackInterface import FTrackInterface
    return FTrackInterface()

  @classmethod
  def getUIDelegate(cls, interfaceInstance):
    import ui
    return ui.FTrackUIDelegate()
