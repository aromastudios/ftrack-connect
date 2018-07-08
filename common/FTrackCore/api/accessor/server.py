# :coding: utf-8
# :copyright: Copyright (c) 2013 ftrack

import os
import getpass
import hashlib
import base64
import json

import requests

from .base import Accessor
from ..data import String
from ..ftrackerror import (
    AccessorOperationFailedError, AccessorResourceNotFoundError,
    AccessorUnsupportedOperationError
)


class ServerFile(String):
    '''Server File.'''
    def __init__(self, resourceIdentifier, mode='rb', **kwargs):
        '''Initialise server file.'''
        self.resourceIdentifier = resourceIdentifier
        self.mode = mode
        self._hasRead = False
        super(ServerFile, self).__init__(**kwargs)

    def flush(self):
        '''Flush all changes.'''
        super(ServerFile, self).flush()

        # TODO: Handle other modes.
        if self.mode == 'wb':
            self._write()

    def read(self):
        '''Read all remote content from resourceIdentifier into wrapped_file.'''
        if not self._hasRead:
            position = self.tell()
            self.wrapped_file.seek(0)

            response = requests.get(
                '{0}/component/get'.format(os.environ['FTRACK_SERVER']),
                params={
                    'id': self.resourceIdentifier,
                    'username': getpass.getuser(),
                    'apiKey': os.environ.get('FTRACK_APIKEY', 'nokeyfound')
                }
            )

            if response.status_code != 200:
                raise AccessorResourceNotFoundError(response.text)

            self.wrapped_file.write(response.content)
            self.seek(position)

            self._hasRead = True

        return self.wrapped_file.read()

    def _write(self):
        '''Write current data to remote *resourceIdentifier*.'''
        position = self.tell()
        self.seek(0)

        serverUrl = '{0}/component/getPutMetadata'.format(
            os.environ['FTRACK_SERVER']
        )

        # Get put metadata.
        response = requests.get(
            serverUrl,
            params={
                'id': self.resourceIdentifier,
                'username': getpass.getuser(),
                'apiKey': os.environ['FTRACK_APIKEY'],
                'checksum': self._computeChecksum(),
                'fileSize': self._getSize()
            }
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            raise AccessorOperationFailedError(
                'Failed to get put metadata: {0}.'.format(error)
            )

        metadata = json.loads(response.text)

        self.seek(0)

        # Put the file based on the metadata.
        response = requests.put(
            metadata['url'],
            data=self.wrapped_file,
            headers=metadata['headers']
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            raise AccessorOperationFailedError(
                'Failed to put file to server: {0}.'.format(error)
            )

        self.seek(position)

    def _getSize(self):
        '''Return size of file in bytes.'''
        position = self.tell()
        self.seek(0, os.SEEK_END)
        length = self.tell()
        self.seek(position)
        return length

    def _computeChecksum(self):
        '''Return checksum for file.'''
        fp = self.wrapped_file
        bufSize = 8192
        hash_obj = hashlib.md5()
        spos = fp.tell()

        s = fp.read(bufSize)
        while s:
            hash_obj.update(s)
            s = fp.read(bufSize)

        base64_digest = base64.encodestring(hash_obj.digest())
        if base64_digest[-1] == '\n':
            base64_digest = base64_digest[0:-1]

        fp.seek(spos)
        return base64_digest


class ServerAccessor(Accessor):
    '''Provide server location access.'''

    def __init__(self, **kw):
        '''Initialise location accessor.'''
        super(ServerAccessor, self).__init__(**kw)

    def open(self, resourceIdentifier, mode='rb'):
        '''Return :py:class:`~ftrack.Data` for *resourceIdentifier*.'''
        return ServerFile(resourceIdentifier, mode=mode)

    def remove(self, resourceIdentifier):
        '''Remove *resourceIdentifier*.'''
        response = requests.get(
            '{0}/component/remove'.format(os.environ['FTRACK_SERVER']),
            params={
                'id': resourceIdentifier,
                'username': getpass.getuser(),
                'apiKey': os.environ.get('FTRACK_APIKEY', 'nokeyfound')
            }
        )
        if response.status_code != 200:
            raise AccessorOperationFailedError(
                'Failed to remove file.'
            )

    def getContainer(self, resourceIdentifier):
        '''Return resourceIdentifier of container for *resourceIdentifier*.'''
        return None

    def makeContainer(self, resourceIdentifier, recursive=True):
        '''Make a container at *resourceIdentifier*.'''
        raise AccessorUnsupportedOperationError('makeContainer')

    def list(self, resourceIdentifier):
        '''Return list of entries in *resourceIdentifier* container.'''
        raise AccessorUnsupportedOperationError('list')

    def exists(self, resourceIdentifier):
        '''Return if *resourceIdentifier* is valid and exists in location.'''
        return None

    def isFile(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a file.'''
        raise AccessorUnsupportedOperationError('isFile')

    def isContainer(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a container.'''
        raise AccessorUnsupportedOperationError('isContainer')

    def isSequence(self, resourceIdentifier):
        '''Return whether *resourceIdentifier* refers to a file sequence.'''
        raise AccessorUnsupportedOperationError('isSequence')

    def getUrl(self, resourceIdentifier):
        '''Return url for *resourceIdentifier*.'''
        urlString = (
            u'{url}/component/get?id={id}&username={username}'
            u'&apiKey={apiKey}'
        )
        return urlString.format(
            url=os.environ['FTRACK_SERVER'],
            id=resourceIdentifier,
            username=getpass.getuser(),
            apiKey=os.environ.get('FTRACK_APIKEY', 'nokeyfound')
        )
