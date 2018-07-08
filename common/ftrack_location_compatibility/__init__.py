# :coding: utf-8
# :copyright: Copyright (c) 2016 ftrack

from .plugin import register_locations
from ._monkey_patch import patch_legacy_api

sessions = list()
is_legacy_location_registered = None
is_legacy_api_patched = False