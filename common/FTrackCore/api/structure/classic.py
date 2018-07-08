
from .base import Structure
from ..component import Component


ENTITY_TYPES = {
    '11c137c0-ee7e-4f9c-91c5-8c77cec22b2c': 'task',
    '4be63b64-5010-42fb-bf1f-428af9d638f0': 'asset_build',
    'bad911de-3bd6-47b9-8b46-3476e237cb36': 'shot',
    'e5139355-61da-4c8f-9db4-3abc870166bc': 'sequence'
}


class ClassicStructure(Structure):
    '''Classic structure supporting Components only.

    Components will be examined and paths generated to support a typical
    studio structure.

    :TODO: Give examples!

    '''

    def __init__(self, fieldSeparator='_', *args, **kwargs):
        '''Initialise structure.

        *fieldSeparator* will be used to join fields in filenames.

        '''
        self.fieldSeparator = fieldSeparator
        super(ClassicStructure, self).__init__(*args, **kwargs)

    def getResourceIdentifier(self, entity):
        '''Return a *resourceIdentifier* for supplied *entity*.'''
        if not isinstance(entity, Component):
            raise NotImplementedError('Cannot generate path for unsupported '
                                      'entity {0}'.format(entity))

        component = entity
        version = None
        
        container = component.getContainer(location=None)
        if container is not None:
            version = container.getVersion()
        else:
            version = component.getVersion()
            
        if version is None:
            raise NotImplementedError('Cannot generate path for entity {0} '
                                      'as could not find attached version.'
                                      .format(component))

        task = None
        if version.get('taskid'):
            task = version.getTask()

        parents = version.getParents()
        show = sequence = shot = asset = None
        
        for parent in parents:
            entityType = parent.get('entityType')
            if entityType == 'task':
                entityType = ENTITY_TYPES.get(
                    parent.get('object_typeid'), None
                )

            if entityType == 'asset':
                asset = parent
            elif entityType == 'shot':
                shot = parent
            elif entityType == 'sequence':
                sequence = parent
            elif entityType == 'show':
                show = parent

        path = []
        if self.prefix:
            path.append(self.prefix)
            
        filename = []

        if show:
            path.append(show.getName())

        path.append('publish')

        if sequence or shot:
            path.append('shots')

            if sequence:
                path.append(sequence.getName())
                filename.append(sequence.getName())

            if shot:
                path.append(shot.getName())
                filename.append(shot.getName())

        else:
            path.append('global')

        if asset:
            path.append(asset.getName())
            filename.append(asset.getName())
            assetType = asset.getType()

        if task:
            path.append(task.getName())

        if assetType:
            path.append(assetType.getName())
            filename.append(assetType.getName())

        version = 'v{0:03d}'.format(version.getVersion())
        path.append(version)

        filename = self.fieldSeparator.join(filename)

        if container:
            if container.getName():
                filename = self.fieldSeparator.join((
                    filename, container.getName()
                ))

            filename = self.fieldSeparator.join((filename, version))
            filename += '.{0}'.format(component.getName())
        else:
            if component.getName():
                filename = self.fieldSeparator.join((
                    filename, component.getName()
                ))

            filename = self.fieldSeparator.join((filename, version))

            if component.isSequence():
                # Add a sequence identifier.
                sequenceExpression = self._getSequenceExpression(component)
                filename += '.{0}'.format(sequenceExpression)

        if component.getFileType():
            filename += component.getFileType()

        path.append(filename)

        # :TODO: Replace invalid characters.
        return self.pathSeparator.join(path).lower().strip('/')
