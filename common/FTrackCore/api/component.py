# :coding: utf-8
# :copyright: Copyright (c) 2013 ftrack

import os

import clique

from .client import (xmlServer, Parentable, AssetVersion,
                     withGetCache)
from .ftobject import FTObject, Metable
from .ftlist import FTList
import ftrackerror


def _createComponent(name, path, versionId, systemType, location,
                     manageData, originLocation, size, containerId,
                     padding):
    '''Create and return component.

    See public function :py:func:`createComponent` for argument details.

    '''
    if path:
        fileType = os.path.splitext(path)[-1]
    else:
        fileType = ''

    data = {
        'type': 'component',
        'name': name,
        'fileType': fileType,
        'systemType': systemType,
        'versionId': versionId,
        'size': size,
        'containerId': containerId
    }

    # Padding should only be set for 'sequence' systemTypes.
    if padding is not None:
        data['padding'] = padding

    response = xmlServer.action('create', data)

    # Optimise initialisation of new component by using location=None.
    # As the component is not in any location yet, this will prevent
    # Component.switchLocation being called and issuing a redundant call to
    # the server.
    component = Component(dict=response, location=None)

    if path:
        component.setResourceIdentifier(path)

        # Add to origin location so that the component can be subsequently
        # added to other locations.
        #
        # Optimisation: Recursive is always False as container members are
        # created separately *after* the container. Using True here would result
        # in a redundant call to Component.getMembers.
        component = originLocation.addComponent(component, recursive=False)

        if location == 'auto':
            # Check if the component name matches one of the ftrackreview
            # specific names. Add the component to the ftrack.review location if
            # so. This is used to not break backwards compatibility.
            if name in (
                'ftrackreview-mp4', 'ftrackreview-webm', 'ftrackreview-image'
            ):
                # Inline to avoid circular import
                from .location import Location
                location = Location('ftrack.review')

            else:
                # Inline to avoid circular import
                from .location import pickLocation
                location = pickLocation()

        if location:
            try:
                # Optimisation: Recursive is always False as container members
                # are created separately *after* the container. Using True here
                # would result in a redundant call to Component.getMembers.
                if manageData is None:
                    component = location.addComponent(
                        component, recursive=False
                    )
                else:
                    component = location.addComponent(
                        component, manageData=manageData, recursive=False
                    )

            except:
                # If adding the component to the location fails, remove the
                # component and re-raise the error.
                component.delete()
                raise

    return component


@withGetCache
def createComponent(name='main', path='', versionId=None, systemType=None,
                    file=None, location='auto', manageData=None, size=None,
                    padding=None, containerId=None):
    '''Create a component with *name*.

    *path* can be a string representing a filesystem path to the data to use
    for the component. The *path* can also be specified as a sequence string,
    in which case a sequence component with child components for each item in
    the sequence will be created automatically. The accepted format for a
    sequence is '{head}{padding}{tail} [{ranges}]'. For example::

        '/path/to/file.%04d.ext [1-5, 7, 8, 10-20]'

    .. seealso::

        `Clique documentation <http://clique.readthedocs.org>`_

    If *location* is specified, then the created component will be
    automatically added to that location. The returned component will also
    be configured with that *location* set as its current location. It should
    be an instance of :py:class:`ftrack.Location`, the string 'auto' (default)
    or None.

    .. note::

        If *path* is not specified the *location* property will be ignored.

    If *location* is set to 'auto' the most suitable location will be selected
    and used. If no suitable location is found the component will be created
    without being added to a location.

    If *name* is set to be 'ftrackreview-mp4', 'ftrackreview-webm' or
    'ftrackreview-image' when 'auto' is specified the review location will be
    used.

    If the specified *location* is of type :py:class:`ftrack.Location`, it
    needs to be configured with a location plugin that is loaded in the
    current session. If the component fails to be added to the specified
    location, it will be removed and the underlying exception will be raised.

    .. note::

        If a *location* is not specified at component creation time then no path
        data will be stored in ftrack and the data not moved in any way.
        Instead, the returned component will be configured with a special
        'origin' location allowing the component to be added to other locations
        manually using :py:meth:`ftrack.Location.addComponent`.

    If *manageData* is True then manage transfer of data to the location.
    If False, assume the data has been managed externally and just record the
    component as present in that location. If *manageData* is None, let the
    location decide if data should be managed.

    .. note::

        If no *location* is specified, *manageData* will be ignored.

    An optional *versionId* can be passed to specify the version entity that
    this component should be linked to.

    .. warning::

        A component cannot currently be attached to a version after
        creation.

    If *systemType* is not specified it will be inferred from the *path*.
    If no *path* set it will default to 'file'.

    *size* is the size of the component in bytes. *size* will be calculated 
    automatically from the path if not specified. If *size* is specified for a 
    sequence it will be stored for the sequence and for child components as
    *size* / number of child components.

    *padding* refers to the padding value for a sequence. It makes no sense for
    other component types and an :py:exc:`~ftrack.FTrackError` will be raised if
    *padding* is attempted to be set on non-sequence components. If not set and
    a *path* is used to determine the sequence, then the value will be
    calculated automatically.

    *file* is a deprecated synonym for *path*. Please update code to use
    *path* in future.

    An optional *containerId* can be passed to specify the container component
    that this component should be added to. The id must refer to an existing
    container component.

    '''
    # Backwards compatibility
    if path and file:
        raise TypeError('Cannot accept both path and file as arguments. '
                        'Path is the new correct name. Please use exclusively.')

    if file is not None:
        print('"file" is deprecated. Please use "path" in future.')
        path = file

    from .. import LOCATION_PLUGINS
    origin = LOCATION_PLUGINS.get('ftrack.origin')
    if origin is None:
        raise ftrackerror.FTrackError(
            'Could not retrieve required "ftrack.origin" location plugin'
        )

    def _getSize(path):
        '''Return size from *path*'''
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        return size

    if path and systemType is None:
        try:
            collection = clique.parse(path)
        except ValueError:
            pass
        else:

            # Caluclate size of container and members.
            containerSize = 0
            memberSize = 0
            fileSizes = {}
            if size is not None:
                containerSize = size
                if len(collection.indexes) > 0:
                    memberSize = int(round(size / len(collection.indexes)))
            else:
                for item in collection:
                    fileSizes[item] = _getSize(item)
                    containerSize += fileSizes[item]

            # Create sequence component
            containerPath = collection.format('{head}{padding}{tail}')

            if padding is None:
                padding = collection.padding

            container = _createComponent(
                name, containerPath, versionId, 'sequence', location,
                manageData, origin, containerSize, containerId, padding
            )

            # Create member components for sequence.
            for item in collection:
                _createComponent(
                    collection.match(item).group('index'),
                    item, 
                    None, 
                    'file', 
                    location, 
                    manageData, 
                    origin, 
                    fileSizes.get(item, memberSize),
                    container.getId(),
                    None,  # Padding not relevant for 'file' type.
                )

            return container

    if size is None:
        size = _getSize(path)

    return _createComponent(
        name, path, versionId, systemType, location, manageData, origin, size,
        containerId, padding
    )


class Component(FTObject, Metable, Parentable):

    _type = 'component'
    _idkey = 'id'

    CONTAINER_TYPES = ['container', 'sequence']

    def __init__(self, id=None, dict=None, eagerload=None, location='auto',
                 resourceIdentifier=None):
        '''Initialise Component with either *id* or *dict*.

        Optional parameter *resourceIdentifier* will be set on the Component if
        specified.

        *location* can be set to specify the initial location this component
        should be switched to. It should be an instance of
        :py:class:`ftrack.Location`, the string 'auto' (default) or None.

        If a specific location instance is specified, but the component does
        not exist in that location then :py:exc:`ftrack.LocationError` will be
        raised.

        If 'auto' is specified then the most suitable location will be used. If
        no suitable location is found then the location property will be set to
        None and no location based information available.

        Use None for location to manage the switching manually later on.

        See :py:meth:`ftrack.Component.switchLocation` for more information.

        .. note::

            If both *location* and *resourceIdentifier* are set then no location
            switching will occur and instead the passed values will just be set
            directly. It is the callers responsibility to ensure the values are
            appropriate.

        '''
        self._resourceIdentifier = None
        self._location = None
        super(Component, self).__init__(id=id, dict=dict, eagerload=eagerload)

        if resourceIdentifier:
            # Use explicitly passed values.
            self.setResourceIdentifier(resourceIdentifier)

            if location == 'auto':

                # Inline to avoid circular import
                from .location import pickLocation

                location = pickLocation(componentId=self.getId())

                if location is None:
                    raise ftrackerror.ComponentNotInAnyLocationError(
                        'No suitable location could be found.'
                    )

            self._setLocation(location)

        elif location is not None:
            try:
                self.switchLocation(location)
            except ftrackerror.LocationError:
                # If switching to a location using 'auto' failed, then pass as
                # it would be annoying for a default value to cause failure in
                # such a way.
                if location != 'auto':
                    raise

    def getVersion(self):
        '''Return the :py:class:`AssetVersion` this component belongs to.

        If no version is associated with this component then return None.

        '''
        versionId = self.get('version_id')
        if versionId is None:
            return None

        return AssetVersion(id=versionId)

    def getContainer(self, location='auto'):
        '''Return the :py:class:`Container<Component>` of this component.

        *location* can be set to specify the initial location to switch to on
        the retrieved container.

        It should be an instance of :py:class:`ftrack.Location`, the
        string 'auto' (default) or None.

        If a specific location instance is specified, but the container does
        not exist in that location then :py:exc:`ftrack.LocationError` will be
        raised.

        If 'auto' is specified then will attempt to use the current location of
        this child component. If the container does not exist in that location
        then it will have no location set.

        Use None for location to manage the switching manually later on.

        '''
        containerId = self.get('container_id')
        if containerId is None:
            return None

        if location == 'auto':
            location = self.getLocation()

            containerComponent = Component(id=containerId, location=None)
            try:
                containerComponent.switchLocation(location)
            except ftrackerror.LocationError:
                pass

        else:
            containerComponent = Component(id=containerId, location=location)

        return containerComponent

    def getId(self):
        '''Return component id.'''
        return self.get('id')

    def getName(self):
        '''Return component name.'''
        return self.get('name')

    def getImportPath(self):
        '''Return accessible component path.

        .. deprecated:: 2.0
            Use :py:meth:`getFilesystemPath` instead.

        '''
        return self.getFilesystemPath()

    def getFile(self):
        '''Return internal resourceIdentifier.

        .. deprecated:: 2.0
            Use :py:meth:`getResourceIdentifier` instead.

        '''
        return self.getResourceIdentifier()

    def getFileType(self):
        '''Return component file type.'''
        return self.get('filetype')

    def getSize(self):
        ''' Return size of component in bytes.'''
        return self.get('size')

    def setSize(self, size):
        ''' Set the *size* of a component in bytes.'''
        self.set('size', size)

    def getSystemType(self):
        '''Return component system type.'''
        return self.get('system_type')

    def getResourceIdentifier(self):
        '''Return component resource identifier.'''
        return self._resourceIdentifier

    def setResourceIdentifier(self, resourceIdentifier):
        '''Set component resource identifier to *resourceIdentifier*.'''
        self._resourceIdentifier = resourceIdentifier

    def getFilesystemPath(self):
        '''Return filesystem path.

        Return the filesystem path for the component in currently active
        location. Will return None if no path can be calculated.

        '''
        location = self.getLocation()
        filesystemPath = None

        if location:
            accessor = location.getAccessor()

            if accessor is not None:
                try:
                    filesystemPath = accessor.getFilesystemPath(
                        self.getResourceIdentifier()
                    )
                except (ftrackerror.AccessorUnsupportedOperationError,
                        ftrackerror.AccessorFilesystemPathError):
                    pass

        return filesystemPath

    def getUrl(self):
        '''Return URL.

        Return the URL for the component in currently active
        location. Will return None if no path can be calculated.

        '''
        location = self.getLocation()
        url = None

        if location:
            accessor = location.getAccessor()

            if accessor is not None:
                try:
                    url = accessor.getUrl(
                        self.getResourceIdentifier()
                    )
                except (ftrackerror.AccessorUnsupportedOperationError,
                        ftrackerror.AccessorFilesystemPathError):
                    pass

        return url

    def getLocation(self):
        '''Return current location.'''
        return self._location

    def _setLocation(self, location):
        '''Set current *location*.

        .. note::

            This will set the location property on the component.
            To set the current location and automatically update the
            resourceIdentifier to reflect that location, use
            :py:meth:`ftrack.Component.switchLocation`.

        '''
        self._location = location

    def switchLocation(self, location):
        '''Update the current *location* of the component.

        *location* should be a :py:class:`ftrack.Location` instance, the
        string 'auto' or None.

        Will update the resourceIdentifier property of the component to reflect
        the specified location.

        If a specific location instance is specified, but the component does
        not exist in that location then :py:exc:`ftrack.LocationError` will be
        raised.

        If 'auto' is specified then the most suitable location will be used. If
        no suitable location is found then
        :py:exc:`ftrack.ComponentNotInAnyLocationError` will be raised.

        If *location* is specified as None then any location relevant properties
        will be reset to None and the component will no longer reflect the
        component in a specific location.

        '''
        # Inline to avoid circular import
        from .location import pickLocation

        if location is None:
            self._setLocation(None)
            self.setResourceIdentifier(None)

        else:
            if location == 'auto':
                location = pickLocation(componentId=self.getId())

                if location is None:
                    raise ftrackerror.ComponentNotInAnyLocationError(
                        'No suitable location could be found.'
                    )

            # Use retrieved location to adopt component and update relevant
            # values.
            location.adoptComponent(self)

    def isContainer(self):
        '''Return whether this component is a container for others.'''
        return self.getSystemType() in self.CONTAINER_TYPES

    def getMembers(self, location='auto'):
        '''Return contained members.

        *location* can be set to specify the initial location to switch to for
        each member.

        It should be an instance of :py:class:`ftrack.Location`, the
        string 'auto' (default) or None.

        If a specific location instance is specified, but a member does
        not exist in that location then :py:exc:`ftrack.LocationError` will be
        raised.

        If 'auto' is specified then will attempt to use the current location of
        this container component. If the member does not exist in that location
        then it will have no location set.

        Use None for location to manage the switching manually later on.

        Raise TypeError if not a container.

        '''
        if not self.isContainer():
            raise TypeError('Component is not a container.')

        # Fetch all members.
        data = {
            'componentId': self.getId()
        }
        response = xmlServer.action('component.getMembers', data)
        members = FTList()

        for component in response:
            newComponent = Component(dict=component, location=None)
            members.append(newComponent)

        if location == 'auto':
            location = self.getLocation()

            if location is not None:
                try:
                    location.adoptComponents(members)
                except ftrackerror.ComponentNotInLocationError as error:
                    # Some of the components are missing from *location*. Adopt the
                    # retry with the other components.
                    missingIds = error.getMissingIds()
                    membersInLocation = FTList()
                    for member in members:
                        if member.getId() not in missingIds:
                            membersInLocation.append(member)

                    location.adoptComponents(membersInLocation)

        elif location is not None:
            location.adoptComponents(members)

        return members

    def addMember(self, component):
        '''Add a *component* as a member of this container.'''
        if not self.isContainer():
            raise TypeError('Cannot add member to non-container.')
        
        data = {
            'componentId': component.getId(),
            'containerId': self.getId()
        }
        xmlServer.action('component.addMember', data)
        
        component.dict['container_id'] = self.getId()

    def removeMember(self, component):
        '''Remove *component* from being a member of this container.'''
        if not self.isContainer():
            raise TypeError('Cannot remove member from non-container.')

        data = {
            'componentId': component.getId(),
            'containerId': self.getId()
        }
        xmlServer.action('component.removeMember', data)
        
        component.dict['container_id'] = None

    def getAvailability(self, locationIds=None):
        '''Return availability in locations with *locationIds*.
        
        If *locationIds* is None, all known locations will be checked.
        
        Return a dictionary of {locationId:percentage_availability}
        
        '''
        # Avoid circular import
        from .location.base import getComponentAvailability
        return getComponentAvailability(self.getId(), locationIds)

    def isSequence(self):
        '''Return whether component is a sequence.'''
        return self.getSystemType() == 'sequence'

    def getPadding(self):
        '''Return padding value for sequence.'''
        if not self.isSequence():
            raise TypeError('Component is not a sequence.')

        return self.get('padding')

    def setPadding(self, padding):
        '''Set padding value for sequence.

        *padding* should be an integer representing the width of indexes in the
        sequence, with 0 representing no padding. For example, '0001' would be
        represented as padding=4 whilst '1' would be padding=0.

        .. note::

            Will not affect any calculated paths stored in the database.

        '''
        if not self.isSequence():
            raise TypeError('Component is not a sequence.')

        return self.set('padding', padding)
