# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

import os
import platform as _platform
import collections

from .. import _python_ntpath as ntpath
from ..client import getDisks, getAssetPathPrefix
from ..resource_identifier_transformer import ResourceIdentifierTransformer
from ..ftrackerror import FTrackError


class InternalResourceIdentifierTransformer(ResourceIdentifierTransformer):
    '''Transform resource identifier to support ftrack legacy disk locations.

    Historically, a concept of disks have been used in ftrack to manage
    different OS prefixes for paths tracked in ftrack. In addition, it was
    possible to configure a project folder attribute and, behind the scenes, an
    asset prefix that would both be used to calculate the resulting path to
    display in the UI and also when retrieved through the API.

    To provide backwards compatibility with these disks, this transformer will
    adapt relevant resource identifiers when reading them back from the
    database (see :py:meth:`decode`).

    '''

    def __init__(self, platform=None, *args, **kwargs):
        '''Initialise internal resource identifier transformer.

        *platform* will override the current platform. Acceptable arguments are
        'Linux', 'Windows' or 'Darwin'. This will change the disk 
        prefix prepended to paths.

        '''
        self._disksCache = None
        self._platform = platform

        super(
            InternalResourceIdentifierTransformer,
            self
        ).__init__(*args, **kwargs)

    @property
    def platform(self):
        '''Return platform name.'''
        if self._platform is None:
            # Delay use of platform.system to fix issue in Nuke when running in 
            # background process. Using platform.system during import causes 
            # IOError, see http://bugs.python.org/issue9867 
            self._platform = _platform.system()

        return self._platform

    @property
    def _disks(self):
        '''Return disks.'''
        if self._disksCache is None:
            self._disksCache = {}

            for disk in getDisks():
                self._disksCache[disk.get('diskid')] = disk

        return self._disksCache

    def _getPrefixFromDiskId(self, diskId):
        '''Return disk prefix based on *diskId*.''' 
        disk = self._disks[diskId]

        prefix = None
        if self.platform == 'Windows':
            prefix = disk.get('windows')
        elif self.platform in ('Linux', 'Darwin'):
            prefix = disk.get('unix')

        if prefix is None:
            raise NotImplementedError(
                'Platform {0} not supported'.format(self.platform)
            )

        return prefix

    def _stripDiskFromResourceIdentifier(self, resourceIdentifier, diskId):
        '''Return *resourceIdentifier* with disk (*diskId*) prefix removed.

        If *resourceIdentifier* starts with either the Windows or Unix path of
        the disk with *diskId*, then remove that portion from the returned
        result.

        .. note : 

            Returned resource identifier is a relative path if 
            *resourceIdentifier* is relative or it matches the Windows or Unix
            prefixes of the disk with *diskId*.

        '''
        disk = self._disks[diskId]

        diskPrefixes = [disk.get('windows'), disk.get('unix')]

        # Sort the disk prefixes by length so that the longest matching is
        # always stripped.
        diskPrefixes = sorted(diskPrefixes, key=len, reverse=True)

        for diskPrefix in diskPrefixes:

            if resourceIdentifier.startswith(diskPrefix):
                # Matching disk found so remove disk prefix from identifier.
                resourceIdentifier = resourceIdentifier[len(diskPrefix):]

                if ntpath.isabs(resourceIdentifier):
                    # Ensure that resulting path is relative by stripping any
                    # leftover prefixed slashes from string.
                    # E.g. If disk was '/tmp' and path was '/tmp/foo/bar' the
                    # result will be 'foo/bar'.
                    resourceIdentifier = resourceIdentifier.lstrip('\\/')

                # Longest matching disk prefix has been stripped. No need to
                # continue matching disks.
                break

        return resourceIdentifier

    def decode(self, resourceIdentifier, context=None):
        '''Return decoded *resourceIdentifier* based on *context*.

        Assumes that *resourceIdentifier* is a path to a resource on disk. The
        path can be relative or absolute.

        *context* must be a :py:class:`collections.Mapping` that contains a
        'component' key referring to a valid :py:class:`Component` instance.
        The component will be used to look up the relevant information including
        any configured :term:`disk prefix`, :term:`project folder` or
        :term:`asset path prefix`.

        If the path is absolute, any matching :term:`disk prefix` will be
        changed to match the prefix of the target platform.

        For example, if the project's Unix :term:`disk prefix` is set to
        '/mnt/demo' and its Window prefix set to 'd:\demo', then for a Windows
        target platform::

            '/mnt/demo/path/to/file' -> 'd:\demo\path/to/file'

        For a Linux target platform the same path is left untouched::

            '/mnt/demo/path/to/file' -> '/mnt/demo/path/to/file'

        However, a matching Windows prefix would be transformed::

            'd:\demo\path\to\file' -> '/mnt/demo/path\to\file'

        If the path does not match, it is returned as is::

            '/mymount/path/to/file' -> '/mymount/path/to/file'

        If the path is relative then it will be prepended to start with any
        :term:`disk prefix`, :term:`project folder` and 
        :term:`asset path prefix` configured for the relevant component.

        For example, if the current platform is Linux and the
        Unix :term:`disk prefix` is '/mnt/demo', :term:`project folder` is
        '/jobs/test' and the :term:`asset path prefix` is 'ftrack/assets'::

            'path/to/file' -> '/mnt/demo/jobs/test/ftrack/assets/path/to/file'

        .. note::

            The resulting path is not normalised in any way so a mixture of
            path separator styles may be present.

        '''
        if not isinstance(context, collections.Mapping):
            raise ValueError('Context must be a mapping.')

        if not 'component' in context:
            raise KeyError('Context must contain a valid component key.')

        component = context['component']
        container = component.getContainer(location=None)

        # Figure out project from component in order to access disk and project
        # folder information.
        entity = component
        if container:
            # Optimisation: Use container to retrieve parent project as the
            # lookup can be cached based on the common container id, whereas
            # each component in the container would generate a unique request.
            entity = container

        version = entity.getVersion()
        if version is not None:
            entity = version

        try:
            # This will fail if entity does not have a parent.
            project = entity.getParents()[-1]
        except FTrackError:
            return resourceIdentifier

        diskId = project.get('diskid')

        if ntpath.isabs(resourceIdentifier):
            # For absolute paths strip any matching disk prefix for the project.
            # Note: ntpath.isabs will work in this case for both Unix and
            # Window paths.
            path = self._stripDiskFromResourceIdentifier(
                resourceIdentifier,
                diskId
            )

        else:
            # For relative paths, prefix with any relevant project folder and
            # asset prefix.
            assetPathPrefix = getAssetPathPrefix()
            projectRoot = project.get('root')

            path = os.path.join(
                projectRoot,
                assetPathPrefix,
                resourceIdentifier
            )

        if not ntpath.isabs(path):
            # For relative paths, prepend disk prefixes. Note that a path that 
            # was previously stripped will have a disk prefix prepended again.
            #
            # The reason for first removing it and then adding back again is 
            # that the disk that was originally in the path might be for another
            # platform than what is requested now.
            prefix = self._getPrefixFromDiskId(diskId)
            path = os.path.join(prefix, path)

        # TODO: Consider how to handle case when path originated on different
        # platform to what this code is running on. Currently, native Python
        # path manipulators are used which can result in a mixture of path
        # separators and possibly introduce unexpected issues. Example result:
        # 'd:\\demo/project-folder/assetpath-prefix/rest\\of\\path\\to\\file'
        return path
