# :coding: utf-8
# :copyright: Copyright (c) 2013 FTrack

import os
import sys

from .api import _python_compatibility

from .api.client import *
from .api.location import *
from .api.component import *
from .api.review_session import *
from .api.review_session_object import *
from .api.review_session_invitee import *
from .api.timelog import *
from .api.temp_data import *
from .api.accessor import *
from .api.structure import *
from .api.resource_identifier_transformer import *
from .api.data import *
from .api.registry import Registry
from .api.event import EventHub, Event
from .api import cache
from .api.action import Action
from .api.ftrackerror import (FTrackError,
                              LocationError,
                              PermissionDeniedError,
                              ComponentNotInAnyLocationError,
                              ComponentNotInLocationError,
                              ComponentInLocationError,
                              AccessorError,
                              AccessorOperationFailedError,
                              AccessorUnsupportedOperationError,
                              AccessorPermissionDeniedError,
                              AccessorResourceIdentifierError,
                              AccessorFilesystemPathError,
                              AccessorResourceError,
                              AccessorResourceNotFoundError,
                              AccessorParentResourceNotFoundError,
                              AccessorResourceInvalidError,
                              AccessorContainerNotEmptyError,
                              EventHubError,
                              EventHubConnectionError,
                              EventHubPacketError,
                              NotUniqueError,
                              NotFoundError)

#: Default location plugin registry..
LOCATION_PLUGINS = Registry(
    os.environ.get('FTRACK_LOCATION_PLUGIN_PATH', '').split(os.pathsep)
)

#: Default event hub
EVENT_HUB = EventHub()

#: Plugins to handle event. Note that this is just one way of registering
# handlers.
EVENT_HANDLERS = Registry(
    os.environ.get('FTRACK_EVENT_PLUGIN_PATH', '').split(os.pathsep)
)

# Create and register default special origin location.
#
# Use a hard coded id and name to avoid a request to the server. The id must
# match the one defined in the migration script.
LOCATION_PLUGINS.add(
    UnmanagedMemoryLocation(
        accessor=DiskAccessor(prefix=''),
        structure=OriginStructure(),
        priority=100,
        dict={
            'id': 'ce9b348f-8809-11e3-821c-20c9d081909b',
            'name': 'ftrack.origin'
        }
    )
)

# Create and register an unmanaged location. The unmanaged location is used
# to provide backwards compatibility for disks, project folder attribute and
# the asset prefix setting.
#
# Use a hard coded id and name to avoid a request to the server. The id must
# match the one defined in the migration script.
LOCATION_PLUGINS.add(
    UnmanagedLocation(
        structure=OriginStructure(),
        accessor=DiskAccessor(prefix=''),
        resourceIdentifierTransformer=InternalResourceIdentifierTransformer(),
        priority=90,
        dict={
            'id': 'cb268ecc-8809-11e3-a7e2-20c9d081909b',
            'name': 'ftrack.unmanaged'
        }
    )
)

# Create and register default special review location.
# The review location is used to provide backwards compatibility with
# ftrackreview.
LOCATION_PLUGINS.add(
    UnmanagedLocation(
        accessor=DiskAccessor(prefix=''),
        structure=OriginStructure(),
        priority=110,
        dict={
            'id': 'cd41be70-8809-11e3-b98a-20c9d081909b',
            'name': 'ftrack.review'
        }
    )
)

# Create and register default connect location. The connect location is used to 
# publish managed data from Connect where structure is determined from ftrack
# entities (project folder, shot and asset names etc.).
#
# Use a hard coded id and name to avoid a request to the server. The id must
# match the one defined in the migration script.
LOCATION_PLUGINS.add(
    Location(
        structure=ConnectStructure(),
        accessor=DiskAccessor(prefix=''),
        resourceIdentifierTransformer=InternalResourceIdentifierTransformer(),
        priority=95,
        dict={
            'id': '07b82a97-8cf9-11e3-9383-20c9d081909b',
            'name': 'ftrack.connect'
        }
    )
)

# Create and register default server location.
LOCATION_PLUGINS.add(
    Location(
        accessor=ServerAccessor(),
        structure=EntityIdStructure(),
        priority=150,
        dict={
            'id': '3a372bde-05bc-11e4-8908-20c9d081909b',
            'name': 'ftrack.server'
        }
    )
)


def setup(actions=True):
    '''Helper function to setup FTrack.'''
    #: TODO Ideally move FTrack API into a Session based instance to avoid all
    # these globals and make testing and configuration easier. E.g.
    # ft = ftrack.FTrack()
    global LOCATION_PLUGINS
    global EVENT_HUB
    
    # Discover location plugins.
    LOCATION_PLUGINS.discover()

    if actions:
        # Start event hub connection.
        EVENT_HUB.connect()
      
        # Discover event handlers.
        EVENT_HANDLERS.discover()

    # Configure master location based on server scenario.
    systemMethods = xmlServer.xmlServer.system.listMethods()
    if 'getServerInformation' in systemMethods:
        serverInformation = xmlServer.action('getServerInformation', {})
        storageScenario = serverInformation.get('storage_scenario')
        if (
            storageScenario and
            storageScenario.get('scenario') == 'ftrack.centralized-storage'
        ):
            try:
                locationData = storageScenario['data']
                locationName = locationData['location_name']
                locationId = locationData['location_id']
                mountPoints = locationData['accessor']['mount_points']

            except KeyError:
                error_message = (
                    'Unable to read storage scenario data.'
                )
                self.logger.error(error_message)
                raise ftrack_api.exception.LocationError(
                    'Unable to configure location based on scenario.'
                )

            else:
                if sys.platform == 'darwin':
                    prefix = mountPoints['osx']
                elif sys.platform == 'linux2':
                    prefix = mountPoints['linux']
                elif sys.platform == 'win32':
                    prefix = mountPoints['windows']
                else:
                    raise LocationError(
                        (
                            'Unable to find accessor prefix for platform {0}.'
                        ).format(sys.platform)
                    )

                LOCATION_PLUGINS.add(
                    Location(
                        accessor=DiskAccessor(prefix=prefix),
                        # TODO: Update with correct structure.
                        structure=StandardStructure(),
                        priority=1,
                        dict={
                            'id': locationId,
                            'name': locationName
                        }
                    )
                )
