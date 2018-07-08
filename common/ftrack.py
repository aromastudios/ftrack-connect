# :coding: utf-8
# :copyright: Copyright (c) ftrack

import os
import sys

# Set the default ftrack server and API key variables to use if no matching
# environment variables are found.
os.environ.setdefault('FTRACK_SERVER', 'https://YOUR-FTRACK-SERVER')
os.environ.setdefault('FTRACK_APIKEY', 'YOUR-API-KEY')

# Honor the legacy FTRACK_PROXY environment variable.

_proxy_variables = (
    'https_proxy',
    'http_proxy'
)


# Import core ftrack functionality into top level namespace.
from FTrackCore import *
