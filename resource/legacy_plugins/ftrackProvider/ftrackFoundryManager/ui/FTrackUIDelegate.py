import hiero

from FnAssetAPI.ui.implementation import ManagerUIDelegate

# Check if QtWebKit or QWebEngine is avaliable.
from FnAssetAPI.ui.toolkit import is_webwidget_supported
has_webwidgets = is_webwidget_supported()

if has_webwidgets:
  from FTrackInfoWidget import FTrackInfoWidget
  from FTrackTasksWidget import FTrackTasksWidget

from FTrackBrowserWidget import FTrackBrowserWidget
from FTrackInlinePickerWidget import FTrackInlinePickerWidget
from FTrackWorkflowRelationshipWidget import FTrackWorkflowRelationshipWidget
from FTrackRegistrationOptionsWidget import FTrackRegistrationOptionsWidget



class FTrackUIDelegate(ManagerUIDelegate):

  def getWidget(self, identifier):

    import FnAssetAPI.ui

    if has_webwidgets:
      if identifier == FTrackInfoWidget.getIdentifier():
        return FTrackInfoWidget

      elif identifier == FTrackTasksWidget.getIdentifier():
        return FTrackTasksWidget

    if identifier == FTrackBrowserWidget.getIdentifier():
      return FTrackBrowserWidget

    elif identifier == FTrackInlinePickerWidget.getIdentifier():
      return FTrackInlinePickerWidget

    elif identifier == FTrackWorkflowRelationshipWidget.getIdentifier():
      return FTrackWorkflowRelationshipWidget

    elif identifier == FTrackRegistrationOptionsWidget.getIdentifier():
      return FTrackRegistrationOptionsWidget

    return None


  def getWidgets(self, host):

    import FnAssetAPI.ui

    widgets = {}
    if has_webwidgets:
      widgets[FTrackInfoWidget.getIdentifier()] = FTrackInfoWidget
      widgets[FTrackTasksWidget.getIdentifier()] = FTrackTasksWidget

    widgets[FTrackBrowserWidget.getIdentifier()] = FTrackBrowserWidget
    widgets[FTrackInlinePickerWidget.getIdentifier()] = FTrackInlinePickerWidget
    widgets[FTrackWorkflowRelationshipWidget.getIdentifier()] = FTrackWorkflowRelationshipWidget
    widgets[FTrackRegistrationOptionsWidget.getIdentifier()] = FTrackRegistrationOptionsWidget

    return widgets





