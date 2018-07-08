# :coding: utf-8
# :copyright: Copyright (c) 2013 ftrack

import copy
import re
import itertools

from ..client import xmlServer, withGetCache
from ..ftlist import FTList
from ..ftobject import FTObject
from ..component import Component
from ..ftrackerror import (FTrackError, LocationError,
                           ComponentNotInLocationError,
                           ComponentInLocationError,
                           AccessorResourceNotFoundError,
                           AccessorParentResourceNotFoundError,
                           EventHubConnectionError)
from .. import cache
from ..event import Event as _Event


#: Topics published by locations
COMPONENT_ADDED_TO_LOCATION_TOPIC = 'ftrack.location.component-added'
COMPONENT_REMOVED_FROM_LOCATION_TOPIC = 'ftrack.location.component-removed'


_COMPONENT_NOT_IN_LOCATION_REGEX = re.compile(
    '(?P<componentIds>([a-z0-9\-](, )?)+) not present in location'
)


@cache.memoise
def _getLocations(includeHidden=False):
    '''Return :py:class:`FTList` of all :py:class:`Locations<Location>`.
    
    If *includeHidden* is True then hidden locations typically used for internal
    purposes will also be returned.

    '''
    data = {}
    response = xmlServer.action('getLocations', data)
    locations = sorted(FTList(Location, response),
                       key=lambda location: location.getPriority())

    # Filter out special locations.
    if not includeHidden:
        locations = filter(
            lambda location: location.getName() not in ('ftrack.origin',),
            locations
        )

    return locations


def getLocations(includeHidden=False, excludeInaccessible=False):
    '''Return :py:class:`FTList` of all :py:class:`Locations<Location>`.

    If *includeHidden* is True then hidden locations typically used for internal
    purposes will also be returned.

    If *excludeInaccessible* is True then only locations that currently have a
    valid accessor will be returned.

    '''
    locations = _getLocations(includeHidden=includeHidden)

    if excludeInaccessible:
        locations = filter(
            lambda location: location.getAccessor() is not None,
            locations
        )

    # Convert locations back to FTList since that is lost on sorted and filter.
    locationsFTList = FTList()
    locationsFTList.extend(locations)
    return locationsFTList


def createLocation(name):
    '''Create and return a new :py:class:`Location` with *name*.'''
    data = {
        'type': 'location',
        'name': name
    }
    response = xmlServer.action('create', data)

    # Clear getLocations cache.
    cacheKey = cache.memoiser.keyMaker.key(_getLocations)
    cache.memoiser.cache.clear(pattern='^{0}'.format(cacheKey))

    return Location(dict=response)


def ensureLocation(name):
    '''Return location with *name*, creating if necessary.'''
    try:
        location = Location(name)
    except FTrackError:
        location = createLocation(name)
    
    return location


def getComponentAvailability(componentId, locationIds=None):
    '''Return component with *componentId* availability in locations.
    
    Use *locationIds* to specify a list of locations by id that should be
    checked. If not specified then all known locations will be checked.
    
    Return a dictionary of {locationId:percentage_availability}
    
    '''
    response = getComponentAvailabilities(
        [componentId], locationIds=locationIds
    )
    return response[0]


def getComponentAvailabilities(componentIds, locationIds=None):
    '''Return availability of each component in *componentIds*.

    Use *locationIds* to specify a list of locations by id that should be
    checked. If not specified then all known locations will be checked.

    Return a list of dictionaries, {locationId:percentage_availability}, that
    can be mapped against the list of *componentIds*.

    '''
    if locationIds is None:
        locations = getLocations()
        locationIds = [location.getId() for location in locations]

    data = {
        'componentIds': componentIds,
        'locationIds': locationIds
    }
    response = xmlServer.action('getComponentAvailabilities', data)
    return response


def pickLocation(componentId=None, includeHidden=False):
    '''Return an appropriate location to use.

    If *componentId* is None return highest priority location that is
    accessible. If *componentId* is not None return highest priority
    accessible location that has the component matching that id.

    If *includeHidden* is True then hidden locations typically used for
    internal purposes only will also be considered.

    Return None if no suitable location could be picked.

    '''
    if componentId is not None:
        location = pickLocations([componentId], includeHidden=includeHidden)[0]

    else:
        # Pick highest priority location.
        locations = getLocations(
            includeHidden=includeHidden,
            excludeInaccessible=True
        )
        if locations:
            location = locations[0]
        else:
            location = None

    return location


def pickLocations(componentIds, includeHidden=False):
    '''Return appropriate locations to use for *componentIds*.

    Return list of highest priority locations that can be mapped against each
    component referenced in *componentIds*.

    If *includeHidden* is True then hidden locations, typically used for
    internal purposes, will also be considered.

    If no suitable location could be picked for a component then its location
    entry will be None.

    '''
    candidateLocations = getLocations(
        includeHidden=includeHidden,
        excludeInaccessible=True
    )

    availabilities = getComponentAvailabilities(
        componentIds,
        locationIds=[location.getId() for location in candidateLocations]
    )

    locations = []
    for index, componentId in enumerate(componentIds):
        availability = availabilities[index]
        location = None

        for candidateLocation in candidateLocations:
            if availability.get(candidateLocation.getId()) > 0.0:
                location = candidateLocation
                break

        locations.append(location)

    return locations


class LocationFactory(type):
    '''Connect database instances to registered plugins dynamically.'''

    def __call__(self, *args, **kw):
        '''Return instance of location.'''
        from ... import LOCATION_PLUGINS
        
        instance = super(LocationFactory, self).__call__(*args, **kw)
        plugin = LOCATION_PLUGINS.get(instance.getName())

        if plugin is not None:
            # TODO: Return a deepcopy with all attributes and dict updated?
            return plugin
        
        return instance


class Location(FTObject):
    '''Represent storage for components.'''
    
    _type = 'location'
    _idkey = 'id'
    
    __metaclass__ = LocationFactory
    
    def __init__(self, id=None, dict=None, eagerload=None, accessor=None,
                 structure=None, resourceIdentifierTransformer=None,
                 priority=50):
        '''Initialise location with either *id* or *dict*.

        *accessor* can be an instance of :py:class:`ftrack.Accessor` and will
        manage access to data in this location for this instance.

        *structure* can be an instance of :py:class:`ftrack.Structure` and will
        be used to provide structure hints when adding components.

        *resourceIdentifierTransformer* can be an instance of
        :py:class:`ftrack.ResourceIdentifierTransformer` and, if set, will be
        called to encode resource identifiers before storing them centrally or
        to decode centrally retrieved identifiers before setting on a component.

        *priority* is a basic hint for the priority of the location versus
        others in this session. The lower the number the higher the priority
        with zero considered highest priority.

        '''
        self._accessor = None
        self._structure = None
        self._resourceIdentifierTransformer = resourceIdentifierTransformer
        self._priority = None
        super(Location, self).__init__(id=id, dict=dict, eagerload=eagerload)
        
        self.setPriority(priority)
        self.setAccessor(accessor)
        self.setStructure(structure)
    
    def getId(self):
        '''Return id.'''
        return self.get('id')
    
    def getName(self):
        '''Return name.'''
        return self.get('name')
    
    def getPriority(self):
        '''Return priority.'''
        return self._priority
    
    def setPriority(self, priority):
        '''Set *priority*.'''
        self._priority = priority
    
    def getAccessor(self):
        '''Return current accessor for this location.'''
        return self._accessor
    
    def setAccessor(self, accessor):
        '''Set current *accessor* for this location.'''
        self._accessor = accessor
    
    def getStructure(self):
        '''Return current structure for this location.'''
        return self._structure
    
    def setStructure(self, structure):
        '''Set current *structure* for this location.'''
        self._structure = structure

    def getResourceIdentifierTransformer(self):
        '''Return current resource identifier transformer for this location.'''
        return self._resourceIdentifierTransformer

    def setResourceIdentifierTransformer(self, resourceIdentifierTransformer):
        '''Set current *resourceIdentifierTransformer* for this location.'''
        self._resourceIdentifierTransformer = resourceIdentifierTransformer

    def adoptComponent(self, component):
        '''Adopt and return *component*.

        Set location on *component* to this location, as well as retrieving and
        setting appropriate resource identifier.

        Raise :py:exc:`ftrack.ComponentNotInLocationError` if component not
        found in this location.

        Note that this compliments :py:meth:`getComponent` rather than
        :py:meth:`addComponent`.

        .. seealso::

            :py:meth:`getComponent`.

        '''
        return self.adoptComponents([component])[0]

    @withGetCache
    def adoptComponents(self, components):
        '''Adopt and return *components*.

        For each component in *components*, set location to this location, as
        well as retrieving and setting appropriate resource identifier.

        Raise :py:exc:`ftrack.ComponentNotInLocationError` if any of the
        components are not found in this location.

        .. seealso::

            :py:meth:`getComponents`.

        '''
        adopted = []
        componentIds = [component.getId() for component in components]

        componentsMetadata = self._getComponentsMetadata(componentIds)
        for component, (_, metadata) in itertools.izip(
            components, componentsMetadata
        ):
            self._adoptComponent(component, metadata)
            adopted.append(component)

        return adopted

    def getComponent(self, componentId):
        '''Retrieve component with *componentId* from this location.
        
        Raise :py:exc:`ftrack.ComponentNotInLocationError` if component not
        found in this location.

        .. note::
        
            If an accessor is available for this location then the access path
            will also be set on the returned component.

        .. seealso::

            :py:meth:`adoptComponent`.

        '''
        return self.getComponents([componentId])[0]

    @withGetCache
    def getComponents(self, componentIds=None):
        '''Retrieve components with *componentIds* from this location.

        Raise :py:exc:`ftrack.ComponentNotInLocationError` if any of the
        specified components are not found in this location.

        If *componentIds* is not specified (or None) then retrieve ALL
        components currently in this location.

        .. note::

            If an accessor is available for this location then the access path
            will also be set on the returned component.

        .. seealso::

            :py:meth:`adoptComponents`.

        '''
        # Batch fetch metadata about components in this location.
        componentsMetadata = self._getComponentsMetadata(componentIds)

        components = []
        for componentId, metadata in componentsMetadata:
            # Optimise initialisation of new component by using
            # location=None. As the component will be manually configured
            # for this location, will prevent Component.switchLocation being
            # called and issuing a redundant call to the server.
            component = Component(componentId, location=None)
            self._adoptComponent(component, metadata)
            components.append(component)

        return components

    def _getComponentMetadata(self, componentId):
        '''Retrieve metadata for *componentId* in this location.

        Return mapping containing a valid 'resourceIdentifier' for the
        component in this location.

        Raise :py:exc:`ftrack.ComponentNotInLocationError` if component not
        found in this location.

        '''
        return self._getComponentsMetadata([componentId])[0][1]

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
        locationId = self.getId()

        data = {
            'componentIds': componentIds,
            'locationId': locationId
        }

        try:
            # TODO: Page the requests to the server to properly handle large
            # numbers of components.
            response = xmlServer.action('location.getComponents', data)
        except FTrackError as error:
            # TODO: Improve the passing of error types between backend and
            # frontend.
            match = _COMPONENT_NOT_IN_LOCATION_REGEX.search(error.message)
            if match:
                raise ComponentNotInLocationError(
                    match.group('componentIds').split(', '), locationId
                )
            else:
                raise LocationError(error.message)

        componentsMetadata = []
        for entry in response:
            metadata = {
                'resourceIdentifier': entry['metadata']['resourceIdentifier']
            }
            componentsMetadata.append(
                (entry['componentId'], metadata)
            )

        return componentsMetadata

    def _adoptComponent(self, component, metadata):
        '''Configure existing *component* in this location using *metadata*.'''
        component._setLocation(self)

        # Optionally decode resource identifier before setting on component.
        resourceIdentifier = metadata['resourceIdentifier']

        resourceIdentifierTransformer = self.getResourceIdentifierTransformer()
        if resourceIdentifierTransformer is not None:
            resourceIdentifier = resourceIdentifierTransformer.decode(
                resourceIdentifier,
                context={'component': component}
            )

        component.setResourceIdentifier(resourceIdentifier)

    @withGetCache
    def addComponent(self, component, recursive=True, manageData=True):
        '''Add *component* to this location transferring relevant data.

        If *component* is a container and *recursive* is True then also
        add each member of the container to this location.

        If *manageData* is True then manage transfer of data to the location (
        an accessor must be set for this location and the location of the
        component). If False assume data has been managed externally.

        .. note::

            Externally managed data must still match the path generated by this
            location's structure interface. No existence check is currently
            performed.

        Raise :exc:`ftrack.ComponentInLocationError` if the *component*
        already exists in this location.

        Raise :exc:`ftrack.LocationError` if the generated target structure for
        the component already exists according to the accessor. This helps
        prevent potential data loss by avoiding overwriting existing data. Note
        that there is a race condition between the check and the write so if
        another process creates data at the same target during that period it
        will be overwritten.

        Return component in this location.

        '''
        componentId = component.getId()
        try:
            self._getComponentMetadata(componentId)
        except ComponentNotInLocationError:
            # Component does not already exist in location so it is fine to
            # continue to add it.
            pass
        else:
            raise ComponentInLocationError(componentId, self.getId())

        targetStructure = self.getStructure()
        if targetStructure is None:
            raise LocationError('No structure defined for location.')

        targetPath = targetStructure.getResourceIdentifier(component)

        if recursive and component.isContainer():
            for member in component.getMembers():
                self.addComponent(
                    member, recursive=recursive, manageData=manageData
                )

        if manageData:
            sourceLocation = component.getLocation()
            if sourceLocation is None:
                raise LocationError('No location defined for component.')

            sourceAccessor = sourceLocation.getAccessor()
            if sourceAccessor is None:
                raise LocationError('No accessor defined for component\'s '
                                    'current location.')

            targetAccessor = self.getAccessor()
            if targetAccessor is None:
                raise LocationError('No accessor defined for location.')

            container = None
            try:
                container = targetAccessor.getContainer(targetPath)
            except AccessorParentResourceNotFoundError:
                # Container could not be retrieved from targetPath. Assume that
                # there is no need to make the container.
                pass

            if container is not None:
                # No need for existence check as makeContainer does not recreate
                # existing containers.
                targetAccessor.makeContainer(container)

            if not component.isContainer():
                source = sourceAccessor.open(
                    component.getResourceIdentifier(), 'rb'
                )

                if targetAccessor.exists(targetPath):
                    # Note: There is a race condition here in that the data may
                    # be added externally between the check for existence and
                    # the actual write which would still result in potential
                    # data loss. However, there is no good cross platform, cross
                    # accessor solution for this at present.
                    raise LocationError(
                        'Cannot add component as data already exists and '
                        'overwriting could result in data loss. Computed '
                        'target resource identifier was: {0}'.format(targetPath)
                    )

                target = targetAccessor.open(targetPath, 'wb')
                target.write(source.read())
                target.close()
                source.close()

        # Optionally encode resource identifier before storing centrally.
        resourceIdentifier = targetPath

        resourceIdentifierTransformer = self.getResourceIdentifierTransformer()
        if resourceIdentifierTransformer is not None:
            resourceIdentifier = resourceIdentifierTransformer.encode(
                resourceIdentifier,
                context={'component': component}
            )

        metadata = {'resourceIdentifier': resourceIdentifier}
        self._addComponentMetadata(component, metadata)

        self._publishEvent(
            _Event(
                topic=COMPONENT_ADDED_TO_LOCATION_TOPIC,
                data=dict(
                    componentId=component.getId(),
                    locationId=self.getId()
                )
            )
        )

        # Construct component to return.
        componentInLocation = copy.deepcopy(component)
        self._adoptComponent(componentInLocation, metadata)

        return componentInLocation

    def _addComponentMetadata(self, component, metadata):
        '''Store *metadata* about *component* in this location.

        *metadata* should be a mapping containing a valid 'resourceIdentifier'
        for the component in this location.

        '''
        xmlServer.action('location.addComponent', {
            'componentId': component.getId(),
            'locationId': self.getId(),
            'resourceIdentifier': metadata['resourceIdentifier']
        })

    def removeComponent(self, componentId, recursive=True, manageData=True):
        '''Remove component with *componentId* from this location.

        If *component* is a container and *recursive* is True then also
        remove each member of the container from this location.

        If *manageData* is True then manage removal of data from this location (
        an accessor must be set for this location). If False assume data has
        been managed externally.

        '''
        # Check component is in this location
        component = self.getComponent(componentId)

        if recursive and component.isContainer():
            for member in component.getMembers():
                self.removeComponent(
                    member.getId(), recursive=recursive, manageData=manageData
                )

        if manageData:
            accessor = self.getAccessor()
            if accessor is None:
                raise LocationError('No accessor defined for location.')

            try:
                accessor.remove(
                    component.getResourceIdentifier()
                )
            except AccessorResourceNotFoundError:
                # If accessor does not support detecting sequence paths then an
                # AccessorResourceNotFoundError is raised. For now, if the
                # component type is 'sequence' assume success.
                if not component.isSequence():
                    raise

        # Remove metadata.
        self._removeComponentMetadata(componentId)

        # Emit event.
        self._publishEvent(
            _Event(
                topic=COMPONENT_REMOVED_FROM_LOCATION_TOPIC,
                data=dict(
                    componentId=componentId,
                    locationId=self.getId()
                )
            )
        )

    def _removeComponentMetadata(self, componentId):
        '''Remove metadata for component in this location.'''
        xmlServer.action('location.removeComponent', {
            'componentId': componentId,
            'locationId': self.getId()
        })

    def getComponentAvailability(self, componentId):
        '''Return availability as percentage of component in this location.'''
        mapping = getComponentAvailability(componentId, [self.getId()])
        return mapping[self.getId()]

    def getComponentAvailabilities(self, componentIds):
        '''Return list of availabilities for components in this location.'''
        locationId = self.getId()
        availabilities = getComponentAvailabilities(
            componentIds, [locationId]
        )
        result = []
        for mapping in availabilities:
            result.append(mapping[locationId])

        return result

    def _publishEvent(self, event):
        '''Publish an event.'''
        from ... import EVENT_HUB
        try:
            EVENT_HUB.publish(event)
        except EventHubConnectionError:
            # TODO: Maybe do something else here; either log error 
            # or try to connect.
            pass
