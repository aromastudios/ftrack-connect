# :coding: utf-8
# :copyright: Copyright (c) 2013 ftrack

from .base import Location
from ..ftrackerror import LocationError, ComponentNotInLocationError


class MemoryLocation(Location):
    '''Represent storage for components.

    Unlike a standard location, only store metadata for components in this
    location in memory rather than persisting to the database.

    '''

    def __init__(self, *args, **kw):
        '''Initialise location.'''
        self._cache = {}
        super(MemoryLocation, self).__init__(*args, **kw)

    def _getComponentMetadata(self, componentId):
        '''Retrieve metadata for *componentId* in this location.

        Return mapping containing a valid 'resourceIdentifier' for the
        component in this location.

        Raise :py:exc:`ftrack.ComponentNotInLocationError` if component not
        found in this location.

        '''
        resourceIdentifier = self._cache.get(componentId)

        if resourceIdentifier is None:
            raise ComponentNotInLocationError([componentId], self.getId())

        metadata = {
            'resourceIdentifier': resourceIdentifier
        }

        return metadata

    def _getComponentsMetadata(self, componentIds=None):
        '''Retrieve metadata for *componentIds* in this location.

        If *componentIds* is not specified (or None) then retrieve metadata for
        ALL components currently in this location.

        Each entry is a tuple of the form (componentId, metadata) where metadata
        is a mapping containing a valid 'resourceIdentifier' for the component
        in this location. The order of the results matches the order of the
        specified *componentIds*.

        Raise :py:exc:`ftrack.ComponentNotInLocationError` if any of the
        specified components are not found in this location.

        '''
        if componentIds is None:
            componentIds = self._cache.keys()

        componentsMetadata = []
        for componentId in componentIds:
            componentsMetadata.append(
                (componentId, self._getComponentMetadata(componentId))
            )

        return componentsMetadata

    def _addComponentMetadata(self, component, metadata):
        '''Store *metadata* about *component* in this location.

        *metadata* should be a mapping containing a valid 'resourceIdentifier'
        for the component in this location.

        '''
        self._cache[component.getId()] = metadata['resourceIdentifier']

    def _removeComponentMetadata(self, componentId):
        '''Remove metadata for component in this location.'''
        self._cache.pop(componentId)

    def getComponentAvailability(self, componentId):
        '''Return availability as percentage of component in this location.'''
        try:
            component = self.getComponent(componentId)
        except LocationError:
            return 0.0

        availability = 0.0
        if component.isContainer():
            members = component.getMembers()
            if len(members):
                multiplier = 1.0 / len(members)

                for member in members:
                    memberPercentage = self.getComponentAvailability(
                        member.getId()
                    )

                    availability += memberPercentage * multiplier

            else:
                availability = 100.0

        else:
            availability = 100.0

        # Avoid quantization error by rounding percentage and clamping to
        # range 0-100.
        availability = round(availability, 9)
        availability = max(0.0, min(availability, 100.0))

        return availability

    def getComponentAvailabilities(self, componentIds):
        '''Return list of availabilities for components in this location.'''
        result = []
        for componentId in componentIds:
            result.append(self.getComponentAvailabilities(componentId))

        return result
