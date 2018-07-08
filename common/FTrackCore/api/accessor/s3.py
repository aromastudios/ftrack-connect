# :coding: utf-8
# :copyright: Copyright (c) 2013 ftrack

import os
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

BOTO_AVAILABLE = False
try:
    import boto
    import boto.exception

    BOTO_AVAILABLE = True
except ImportError:
    pass

from .base import Accessor
from ..data import FileWrapper
from ..ftrackerror import (AccessorOperationFailedError,
                           AccessorUnsupportedOperationError,
                           AccessorResourceInvalidError,
                           AccessorResourceNotFoundError,
                           AccessorContainerNotEmptyError,
                           AccessorParentResourceNotFoundError)


class S3File(FileWrapper):
    '''S3 Buffered File.
    
    TODO: Implement read/write restriction based on mode. Should that be at the
    base data level?
    
    '''
    
    def __init__(self, key, mode='rb'):
        '''Initialise S3 file with S3 *key* and *mode*.'''
        self.key = key
        self.mode = mode
        wrapped_file = StringIO()
        super(S3File, self).__init__(wrapped_file)
        self._read()
        
    def flush(self):
        '''Flush all changes.'''
        super(S3File, self).flush()
        self._write()
        
    def _read(self):
        '''Read all remote content from key into wrapped_file.'''
        position = self.tell()
        self.seek(0)
        self.key.get_contents_to_file(self.wrapped_file)
        self.seek(position)
        
    def _write(self):
        '''Write current data to remote key.'''
        position = self.tell()
        self.seek(0)
        self.key.set_contents_from_file(self.wrapped_file)
        self.seek(position)


class S3Accessor(Accessor):
    '''Provide Amazon S3 location access.

    To use, please first install the :term:`Boto` package.
    '''

    def __init__(self, bucketName, accessKey, secretKey):
        '''Initialise location accessor.

        *bucketName* is the name of the bucket to provide access to using
        *accessKey* and *secretKey* credentials.
        '''
        if not BOTO_AVAILABLE:
            raise NotImplementedError(
                'S3Accessor not available as failed to import boto package. '
                'Please install boto if you want to use this accessor.'
            )

        self.accessKey = accessKey
        self.secretKey = secretKey
        self.bucketName = bucketName
        self._connection = None
        self._bucket = None
        super(S3Accessor, self).__init__()

    def __deepcopy__(self, memo):
        '''Return a new S3Accessor instance

        There is a known issue on some operating systems when using :term:`Boto`
        >= 2.29 against :term:`Python` >= 2.7. The issue typically manifests
        itself with the following error::

            TypeError: cannot deepcopy this pattern object

        To work around the issue we return a new instance of the accessor which
        does not contain the compiled patterns in the Boto internals.
        '''
        return S3Accessor(self.bucketName, self.accessKey, self.secretKey)

    @property
    def connection(self):
        '''Return S3 connection.'''
        if self._connection is None:
            self._connection = boto.connect_s3(self.accessKey, self.secretKey)
        
        return self._connection
    
    @property
    def bucket(self):
        '''Return bucket.'''
        if self._bucket is None:
            self._bucket = self.connection.get_bucket(self.bucketName,
                                                      validate=False)
        
        return self._bucket
        
    def list(self, resourceIdentifier):
        '''Return list of entries in *resourceIdentifier* container.

        Each entry in the returned list should be a valid resource identifier.

        Raise :py:class:`~ftrack.ftrackerror.AccessorResourceNotFoundError` if
        *resourceIdentifier* does not exist or
        :py:class:`~ftrack.ftrackerror.AccessorResourceInvalidError` if
        *resourceIdentifier* is not a container.

        '''
        if not resourceIdentifier.endswith('/'):
            resourceIdentifier += '/'
        
        if resourceIdentifier == '/':
            resourceIdentifier = ''
        
        listing = []
        for entry in self.bucket.list(prefix=resourceIdentifier, delimiter='/'):
            if entry.name != resourceIdentifier:
                listing.append(entry.name.rstrip('/'))

        return listing
        
    def exists(self, resourceIdentifier):
        '''Return if *resourceIdentifier* is valid and exists in location.'''
        # Root directory always exists
        if not resourceIdentifier:
            return True
        
        return (self.isContainer(resourceIdentifier) or
                self.isFile(resourceIdentifier))
    
    def isFile(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a file.'''
        # Root is a directory
        if not resourceIdentifier:
            return False
        
        resourceIdentifier = resourceIdentifier.rstrip('/')
        try:
            key = self.bucket.get_key(resourceIdentifier)
        except boto.exception.S3ResponseError as error:
            if error.status == 403:
                # Permission denied
                return False
            
            else:
                raise AccessorOperationFailedError(
                    opertion='isFile',
                    resourceIdentifier=resourceIdentifier,
                    details=error
                )
        
        return key is not None
    
    def isContainer(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a container.'''
        # Root is a directory
        if not resourceIdentifier:
            return True
        
        # Check if list request returns any files. This avoids relying on the
        # presence of a special empty file for directories.
        if not resourceIdentifier.endswith('/'):
            resourceIdentifier += '/'
        
        keys = self.bucket.list(prefix=resourceIdentifier, delimiter='/')
        try:
            iter(keys).next()
        except StopIteration:
            return False
        else:
            return True
    
    def isSequence(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a file sequence.'''
        raise AccessorUnsupportedOperationError('isSequence')
    
    def open(self, resourceIdentifier, mode='rb'):
        '''Return :py:class:`~ftrack.Data` for *resourceIdentifier*.'''
        if self.isContainer(resourceIdentifier):
            raise AccessorResourceInvalidError(
                resourceIdentifier,
                message='Cannot open a directory: {resourceIdentifier}'
            )
        
        key = self.bucket.get_key(resourceIdentifier)
        
        if key is None:
            if 'w' not in mode and 'a' not in mode:
                raise AccessorResourceNotFoundError(resourceIdentifier)
            
            if not self.isContainer(self.getContainer(resourceIdentifier)):
                raise AccessorResourceNotFoundError(
                    self.getContainer(resourceIdentifier)
                )
            
            # New file
            key = self.bucket.new_key(resourceIdentifier)
            key.set_contents_from_string('')
        
        elif 'w' in mode:
            # Truncate file
            key = self.bucket.new_key(resourceIdentifier)
            key.set_contents_from_string('')
        
        # TODO: Optimise to avoid having entire file in memory.
        data = S3File(key, mode=mode)
        return data
    
    def remove(self, resourceIdentifier):
        '''Remove *resourceIdentifier*.

        Raise :py:class:`~ftrack.ftrackerror.AccessorResourceNotFoundError` if
        *resourceIdentifier* does not exist.

        '''
        if self.isFile(resourceIdentifier):
            self.bucket.delete_key(resourceIdentifier)
        
        elif self.isContainer(resourceIdentifier):
            contents = self.list(resourceIdentifier)
            if contents:
                raise AccessorContainerNotEmptyError(resourceIdentifier)
            
            self.bucket.delete_key(resourceIdentifier + '/')

        else:
            raise AccessorResourceNotFoundError(resourceIdentifier)

    def getContainer(self, resourceIdentifier):
        '''Return resourceIdentifier of container for *resourceIdentifier*.

        Raise 
        :py:class:`~ftrack.ftrackerror.AccessorParentResourceNotFoundError` if 
        container of *resourceIdentifier* could not be determined.

        '''
        if os.path.normpath(resourceIdentifier) in ('/', ''):
            raise AccessorParentResourceNotFoundError(
                resourceIdentifier,
                message='Could not determine container for '
                        '{resourceIdentifier} as it is the root.'
            )

        return os.path.dirname(resourceIdentifier.rstrip('/'))

    def makeContainer(self, resourceIdentifier, recursive=True):
        '''Make a container at *resourceIdentifier*.
        
        If *recursive* is True, also make any intermediate containers.
        
        '''
        if not resourceIdentifier:
            # Root bucket directory
            return
        
        if not resourceIdentifier.endswith('/'):
            resourceIdentifier += '/'
        
        if self.exists(resourceIdentifier):
            if self.isFile(resourceIdentifier):
                raise AccessorResourceInvalidError(
                    resourceIdentifier,
                    message=('Resource already exists as a file: '
                             '{resourceIdentifier}')
                )
            
            else:
                return
        
        parent = self.getContainer(resourceIdentifier)
        if not self.isContainer(parent):
            if recursive:
                self.makeContainer(parent, recursive=recursive)
            else:
                raise AccessorParentResourceNotFoundError(parent)
        
        key = self.bucket.new_key(resourceIdentifier)
        key.set_contents_from_string('')
