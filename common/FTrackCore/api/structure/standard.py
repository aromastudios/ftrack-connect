# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import os
import re
import unicodedata

from . import base
from .. import client


class StandardStructure(base.Structure):
    '''Project hierarchy based structure that only supports Components.

    The resource identifier is generated from the project code, the name
    of objects in the project structure, asset name and version number::

        my_project/folder_a/folder_b/asset_name/v003

    If the component is a file component then the name of the component and the
    file type are used as filename in the resource identifier::

        my_project/folder_a/folder_b/asset_name/v003/foo.jpg

    If the component is a sequence component then a sequence expression,
    `%04d`, is used. E.g. a component with the name `foo` yields::

        my_project/folder_a/folder_b/asset_name/v003/foo.%04d.jpg

    For the member components their index in the sequence is used::

        my_project/folder_a/folder_b/asset_name/v003/foo.0042.jpg

    The name of the component is added to the resource identifier if the
    component is a container. E.g. a container component with the
    name `bar` yields::

        my_project/folder_a/folder_b/asset_name/v003/bar

    For a member of that container the file name is based on the component name
    and file type::

        my_project/folder_a/folder_b/asset_name/v003/bar/baz.pdf

    '''

    def __init__(
        self, projectVersionsPrefix=None, illegalCharacterSubstitute='_'
    ):
        '''Initialise structure.

        If *projectVersionsPrefix* is defined, insert after the project code
        for versions published directly under the project::

            my_project/<projectVersionsPrefix>/v001/foo.jpg

        Replace illegal characters with *illegalCharacterSubstitute* if
        defined.

        .. note::

            Nested component containers/sequences are not supported.

        '''
        super(StandardStructure, self).__init__()
        self.projectVersionsPrefix = projectVersionsPrefix
        self.illegalCharacterSubstitute = illegalCharacterSubstitute

    def _getParts(self, entity):
        '''Return resource identifier parts from *entity*.'''
        version = None
        structureNames = []
        for item in reversed(entity.getParents()):
            if isinstance(item, (client.Task, client.Project)):
                structureNames.append(item.getName())

            if isinstance(item, client.AssetVersion):
                version = item

        if version is None:
            raise ValueError(
                'Could not retreive version from {0!r}'.format(entity)
            )

        versionNumber = self._formatVersion(version.getVersion())

        parts = structureNames
        if len(parts) == 1 and self.projectVersionsPrefix:
            # Add *projectVersionsPrefix* if configured and the version is
            # published directly under the project.
            parts.append(self.projectVersionsPrefix)

        parts.append(item.getAsset().getName())
        parts.append(versionNumber)

        return [self.sanitiseForFilesystem(part) for part in parts]

    def _formatVersion(self, number):
        '''Return a formatted string representing version *number*.'''
        return 'v{0:03d}'.format(number)

    def sanitiseForFilesystem(self, value):
        ''''Return *value* with illegal filesystem characters replaced.

        An illegal character is one that is not typically valid for filesystem
        usage, such as non ascii characters, or can be awkward to use in a
        filesystem, such as spaces. Replace these characters with
        the character specified by *illegalCharacterSubstitute* on
        initialisation. If no character was specified as substitute then return
        *value* unmodified.

        '''
        if self.illegalCharacterSubstitute is None:
            return value

        if isinstance(value, str):
            value = value.decode('utf-8')

        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
        value = re.sub('[^\w\.-]', self.illegalCharacterSubstitute, value)
        return unicode(value.strip().lower())

    def getResourceIdentifier(self, entity, context=None):
        '''Return a resource identifier for supplied *entity*.

        *context* can be a mapping that supplies additional information, but
        is unused in this implementation.

        '''
        if not entity.isContainer():
            container = entity.getContainer()

            if container:
                # Get resource identifier for container.
                containerPath = self.getResourceIdentifier(container)

                if container.isSequence():
                    # Strip the sequence component expression from the parent
                    # container and back the correct filename, i.e.
                    # /sequence/component/sequence_component_name.0012.exr.
                    name = '{0}.{1}{2}'.format(
                        container.getName(), entity.getName(),
                        entity.getFileType()
                    )
                    parts = [
                        os.path.dirname(containerPath),
                        self.sanitiseForFilesystem(name)
                    ]

                else:
                    # Container is not a sequence component so add it as a
                    # normal component inside the container.
                    name = entity.getName() + entity.getFileType()
                    parts = [
                        containerPath, self.sanitiseForFilesystem(name)
                    ]

            else:
                # File component does not have a container, construct name from
                # component name and file type.
                parts = self._getParts(entity)
                name = entity.getName() + entity.getFileType()
                parts.append(self.sanitiseForFilesystem(name))

        elif entity.isSequence():
            # Create sequence expression for the sequence component and add it
            # to the parts.
            parts = self._getParts(entity)
            sequenceExpression = self._getSequenceExpression(entity)
            parts.append(
                '{0}.{1}{2}'.format(
                    self.sanitiseForFilesystem(entity.getName()),
                    sequenceExpression,
                    self.sanitiseForFilesystem(entity.getFileType())
                )
            )

        elif entity.isContainer():
            # Add the name of the container to the resource identifier parts.
            parts = self._getParts(entity)
            parts.append(self.sanitiseForFilesystem(entity.getName()))

        else:
            raise NotImplementedError(
                'Cannot generate resource identifier for unsupported '
                'entity {0!r}'.format(entity)
            )

        return self.pathSeparator.join(parts)
