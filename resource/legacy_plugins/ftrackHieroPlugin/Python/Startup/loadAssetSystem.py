import sys

import assetmgr_hiero
import hiero

sys.modules.setdefault('hiero.asset', assetmgr_hiero)
import FnAssetAPI
currentManager = FnAssetAPI.SessionManager.currentSession().currentManager()
initManager = True
inPlayer = hiero.core.isHieroPlayer()


if currentManager:
    currentIdentifier = currentManager.getIdentifier()
    if currentIdentifier == "com.ftrack":
        initManager = False

if initManager == True:
    FnAssetAPI.SessionManager.currentSession().useManager("com.ftrack")


if 'Hiero 1.9' in hiero.core.env.get('VersionString', ''):
    FnAssetAPI.logging.debug('Applying hiero 1.9 patches.')
    from ftrack_connect_legacy_plugins.compatiblity.build_shot_from_files import buildShotFromFiles

    assetmgr_hiero.ui.buildAssetTrackActions.BuildAssetTrackAction.buildShotFromFiles = buildShotFromFiles

    if not inPlayer:
        # Certain features or imports shouldnt be available in player/batch/etc...
        from ftrack_connect_legacy_plugins.compatiblity import nukeExporter
        nukeExporter.register()


else:
    if not inPlayer:
        # Certain features or imports shouldnt be available in player/batch/etc...
        from assetmgr_hiero import nukeExporter
        nukeExporter.register()


