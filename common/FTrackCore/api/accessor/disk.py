# :coding: utf-8
# :copyright: Copyright (c) 2013 ftrack

import os
import sys
import errno
import contextlib

from .. import _python_ntpath as ntpath
from .base import Accessor
from ..data import File
from ..ftrackerror import (AccessorFilesystemPathError,
                           AccessorUnsupportedOperationError,
                           AccessorResourceNotFoundError,
                           AccessorOperationFailedError,
                           AccessorPermissionDeniedError,
                           AccessorResourceInvalidError,
                           AccessorContainerNotEmptyError,
                           AccessorParentResourceNotFoundError)


class DiskAccessor(Accessor):
    '''Provide disk access to a location.

    Expect resource identifiers to refer to relative filesystem paths.

    '''

    def __init__(self, prefix, **kw):
        '''Initialise location accessor.

        *prefix* specifies the base folder for the disk based structure and
        will be prepended to any path. It should be specified in the syntax of
        the current OS.

        '''
        if prefix:
            prefix = os.path.expanduser(os.path.expandvars(prefix))
            prefix = os.path.abspath(prefix)
        self.prefix = prefix

        super(DiskAccessor, self).__init__(**kw)

    def list(self, resourceIdentifier):
        '''Return list of entries in *resourceIdentifier* container.

        Each entry in the returned list should be a valid resource identifier.

        Raise :py:class:`~ftrack.ftrackerror.AccessorResourceNotFoundError` if
        *resourceIdentifier* does not exist or 
        :py:class:`~ftrack.ftrackerror.AccessorResourceInvalidError` if
        *resourceIdentifier* is not a container.

        '''
        filesystemPath = self.getFilesystemPath(resourceIdentifier)
        
        with errorHandler(
            operation='list', resourceIdentifier=resourceIdentifier
        ):
            listing = []
            for entry in os.listdir(filesystemPath):
                listing.append(os.path.join(resourceIdentifier, entry))
        
        return listing

    def exists(self, resourceIdentifier):
        '''Return if *resourceIdentifier* is valid and exists in location.'''
        filesystemPath = self.getFilesystemPath(resourceIdentifier)
        return os.path.exists(filesystemPath)

    def isFile(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a file.'''
        filesystemPath = self.getFilesystemPath(resourceIdentifier)
        return os.path.isfile(filesystemPath)

    def isContainer(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a container.'''
        filesystemPath = self.getFilesystemPath(resourceIdentifier)
        return os.path.isdir(filesystemPath)

    def isSequence(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a file sequence.'''
        raise AccessorUnsupportedOperationError('isSequence')

    def open(self, resourceIdentifier, mode='rb'):
        '''Return :py:class:`~ftrack.Data` for *resourceIdentifier*.'''
        filesystemPath = self.getFilesystemPath(resourceIdentifier)

        with errorHandler(
            operation='open', resourceIdentifier=resourceIdentifier
        ):
            data = File(filesystemPath, mode)

        return data

    def remove(self, resourceIdentifier):
        '''Remove *resourceIdentifier*.

        Raise :py:class:`~ftrack.ftrackerror.AccessorResourceNotFoundError` if
        *resourceIdentifier* does not exist.

        '''
        filesystemPath = self.getFilesystemPath(resourceIdentifier)

        if self.isFile(filesystemPath):
            with errorHandler(
                operation='remove', resourceIdentifier=resourceIdentifier
            ):
                os.remove(filesystemPath)

        elif self.isContainer(filesystemPath):
            with errorHandler(
                operation='remove', resourceIdentifier=resourceIdentifier
            ):
                os.rmdir(filesystemPath)

        else:
            raise AccessorResourceNotFoundError(filesystemPath)

    def makeContainer(self, resourceIdentifier, recursive=True):
        '''Make a container at *resourceIdentifier*.

        If *recursive* is True, also make any intermediate containers.

        '''
        filesystemPath = self.getFilesystemPath(resourceIdentifier)

        with errorHandler(
            operation='makeContainer', resourceIdentifier=resourceIdentifier
        ):
            try:
                if recursive:
                    os.makedirs(filesystemPath)
                else:
                    try:
                        os.mkdir(filesystemPath)
                    except OSError as error:
                        if error.errno == errno.ENOENT:
                            raise AccessorParentResourceNotFoundError(
                                resourceIdentifier
                            )
                        else:
                            raise

            except OSError, error:
                if error.errno != errno.EEXIST:
                    raise

    def getContainer(self, resourceIdentifier):
        '''Return resourceIdentifier of container for *resourceIdentifier*.

        Raise 
        :py:class:`~ftrack.ftrackerror.AccessorParentResourceNotFoundError` if 
        container of *resourceIdentifier* could not be determined.

        '''
        filesystemPath = self.getFilesystemPath(resourceIdentifier)

        container = os.path.dirname(filesystemPath)

        if self.prefix:
            if not container.startswith(self.prefix):
                raise AccessorParentResourceNotFoundError(
                    resourceIdentifier,
                    message='Could not determine container for '
                            '{resourceIdentifier} as container falls outside '
                            'of configured prefix.'
                )

            # Convert container filesystem path into resource identifier.
            container = container[len(self.prefix):]
            if ntpath.isabs(container):
                # Ensure that resulting path is relative by stripping any
                # leftover prefixed slashes from string.
                # E.g. If prefix was '/tmp' and path was '/tmp/foo/bar' the
                # result will be 'foo/bar'.
                container = container.lstrip('\\/')

        return container

    def getFilesystemPath(self, resourceIdentifier):
        '''Return filesystem path for *resourceIdentifier*.

        For example::

            >>> accessor = DiskAccessor('my.location', '/mountpoint')
            >>> print accessor.getFilesystemPath('test.txt')
            /mountpoint/test.txt
            >>> print accessor.getFilesystemPath('/mountpoint/test.txt')
            /mountpoint/test.txt

        Raise AccessorFilesystemPathError if filesystem path could not be
        determined from *resourceIdentifier*.

        '''
        filesystemPath = resourceIdentifier
        if filesystemPath:
            filesystemPath = os.path.normpath(filesystemPath)

        if self.prefix:
            if not os.path.isabs(filesystemPath):
                filesystemPath = os.path.normpath(
                    os.path.join(self.prefix, filesystemPath)
                )

            if not filesystemPath.startswith(self.prefix):
                raise AccessorFilesystemPathError(
                    resourceIdentifier,
                    message='Could not determine access path for '
                            'resourceIdentifier outside of configured prefix: '
                            '{resourceIdentifier}.'
                )

        return filesystemPath


@contextlib.contextmanager
def errorHandler(**kw):
    '''Conform raised OSError/IOError exception to appropriate FTrack error.'''
    try:
        yield
        
    except (OSError, IOError) as error:
        (exceptionType, exceptionValue, traceback) = sys.exc_info()
        kw.setdefault('details', error)
        
        errorCode = getattr(error, 'errno')
        if not errorCode:
            raise AccessorOperationFailedError(**kw), None, traceback
    
        if errorCode == errno.ENOENT:
            raise AccessorResourceNotFoundError(**kw), None, traceback
        
        elif errorCode == errno.EPERM:
            raise AccessorPermissionDeniedError(**kw), None, traceback
        
        elif errorCode == errno.ENOTEMPTY:
            raise AccessorContainerNotEmptyError(**kw), None, traceback
            
        elif errorCode in (errno.ENOTDIR, errno.EISDIR, errno.EINVAL):
            raise AccessorResourceInvalidError(**kw), None, traceback
        
        else:
            raise AccessorOperationFailedError(**kw), None, traceback
    
    except Exception:
        raise
