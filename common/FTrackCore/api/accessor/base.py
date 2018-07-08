# :coding: utf-8
# :copyright: Copyright (c) 2013 ftrack

from abc import ABCMeta, abstractmethod

from ..ftrackerror import AccessorUnsupportedOperationError


class Accessor(object):
    '''Provide data access to a location.

    A location represents a specific storage, but access to that storage may
    vary. For example, both local filesystem and FTP access may be possible for
    the same storage. An accessor implements these different ways of accessing
    the same data location.

    As different accessors may access the same location, only part of a data
    path that is commonly understood may be stored in the database. The format
    of this path should be a contract between the accessors that require access
    to the same location and is left as an implementation detail. As such, this
    system provides no guarantee that two different accessors can provide access
    to the same location, though this is a clear goal. The path stored centrally
    is referred to as the **resource identifier** and should be used when
    calling any of the accessor methods that accept a *resourceIdentifier*
    argument.

    '''

    __metaclass__ = ABCMeta

    def __init__(self):
        '''Initialise location accessor.'''
        super(Accessor, self).__init__()

    @abstractmethod
    def list(self, resourceIdentifier):
        '''Return list of entries in *resourceIdentifier* container.

        Each entry in the returned list should be a valid resource identifier.

        Raise :py:class:`~ftrack.ftrackerror.AccessorResourceNotFoundError` if
        *resourceIdentifier* does not exist or 
        :py:class:`~ftrack.ftrackerror.AccessorResourceInvalidError` if
        *resourceIdentifier* is not a container.

        '''

    @abstractmethod
    def exists(self, resourceIdentifier):
        '''Return if *resourceIdentifier* is valid and exists in location.'''

    @abstractmethod
    def isFile(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a file.'''

    @abstractmethod
    def isContainer(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a container.'''

    @abstractmethod
    def isSequence(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a file sequence.'''

    @abstractmethod
    def open(self, resourceIdentifier, mode='rb'):
        '''Return :py:class:`~ftrack.Data` for *resourceIdentifier*.'''

    @abstractmethod
    def remove(self, resourceIdentifier):
        '''Remove *resourceIdentifier*.

        Raise :py:class:`~ftrack.ftrackerror.AccessorResourceNotFoundError` if
        *resourceIdentifier* does not exist.

        '''

    @abstractmethod
    def makeContainer(self, resourceIdentifier, recursive=True):
        '''Make a container at *resourceIdentifier*.

        If *recursive* is True, also make any intermediate containers.

        Should silently ignore existing containers and not recreate them.

        '''

    @abstractmethod
    def getContainer(self, resourceIdentifier):
        '''Return resourceIdentifier of container for *resourceIdentifier*.

        Raise 
        :py:class:`~ftrack.ftrackerror.AccessorParentResourceNotFoundError` if 
        container of *resourceIdentifier* could not be determined.

        '''

    def removeContainer(self, resourceIdentifier):
        '''Remove container at *resourceIdentifier*.'''
        return self.remove(resourceIdentifier)

    def getFilesystemPath(self, resourceIdentifier):
        '''Return filesystem path for *resourceIdentifier*.

        Raise AccessorFilesystemPathError if filesystem path could not be
        determined from *resourceIdentifier* or
        AccessorUnsupportedOperationError if retrieving filesystem paths is not
        supported by this accessor.

        '''
        raise AccessorUnsupportedOperationError(
            'getFilesystemPath', resourceIdentifier=resourceIdentifier
        )

    def getUrl(self, resourceIdentifier):
        '''Return URL for *resourceIdentifier*.

         Raise :py:exc:`ftrack.AccessorUrlError` if URL could not be determined
         from resourceIdentifier* or
         :py:exc:`ftrack.AccessorUnsupportedOperationError` if retrieving URL's
         is not supported by this accessor.

        '''
        raise AccessorUnsupportedOperationError(
            'getUrl', resourceIdentifier=resourceIdentifier
        )
