from __future__ import with_statement

from FTrackBrowserWidget import FTrackBrowserWidget
from FnAssetAPI.ui.dialogs import TabbedBrowserDialog

__all__ = [ 'FTrackBrowserDialog', ]


class FTrackBrowserDialog(TabbedBrowserDialog):

  def __init__(self, specification, context):
    TabbedBrowserDialog.__init__(self, specification, context)
    self.addTab(FTrackBrowserWidget, "ftrack")


