
import os

from .base import Structure
from ..component import Component


class IdStructure(Structure):
    '''Id based structure supporting Components only.

    A components unique id will be used to form a path to store the data at.
    To avoid millions of entries in one directory each id is chunked into four
    prefix directories with the remainder used to name the file::

        /prefix/1/2/3/4/56789

    If the component has a defined filetype it will be added to the path::

        /prefix/1/2/3/4/56789.exr

    Components that are children of container components will be placed inside
    the id structure of their parent::

        /prefix/1/2/3/4/56789/355827648d.exr
        /prefix/1/2/3/4/56789/ajf24215b5.exr

    However, sequence children will be named using their label as an index and
    a common prefix of 'file.'::

        /prefix/1/2/3/4/56789/file.0001.exr
        /prefix/1/2/3/4/56789/file.0002.exr

    '''

    def getResourceIdentifier(self, entity):
        '''Return a *resourceIdentifier* for supplied *entity*.'''
        if not isinstance(entity, Component):
            raise NotImplementedError('Cannot generate path for unsupported '
                                      'entity {0}'.format(entity))

        systemType = entity.getSystemType()

        if systemType in ('file',):
            # When in a container, place the file inside a directory named
            # after the container.
            container = entity.getContainer(location=None)
            if container:
                path = self.getResourceIdentifier(container)

                if container.getSystemType() in ('sequence',):
                    # Label doubles as index for now.
                    name = 'file.{0}{1}'.format(
                        entity.getName(), entity.getFileType()
                    )
                    parts = [os.path.dirname(path), name]

                else:
                    # Just place uniquely identified file into directory
                    name = entity.getId() + entity.getFileType()
                    parts = [path, name]

            else:
                name = entity.getId()[4:] + entity.getFileType()
                parts = ([self.prefix] + list(entity.getId()[:4]) + [name])

        elif systemType in ('sequence',):
            name = 'file'

            # Add a sequence identifier.
            sequenceExpression = self._getSequenceExpression(entity)
            name += '.{0}'.format(sequenceExpression)

            if entity.getFileType():
                name += entity.getFileType()

            parts = ([self.prefix] + list(entity.getId()[:4])
                     + [entity.getId()[4:]] + [name])

        elif entity.isContainer():
            # Just an id directory
            parts = ([self.prefix] +
                     list(entity.getId()[:4]) + [entity.getId()[4:]])

        else:
            raise NotImplementedError('Cannot generate path for unsupported '
                                      'entity {0}'.format(entity))

        return self.pathSeparator.join(parts).strip('/')
