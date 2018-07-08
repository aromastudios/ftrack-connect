
from .base import Structure
from ..component import Component


class OriginStructure(Structure):
    '''Origin structure supporting Components only.
    
    Will maintain original internal component path.
    
    '''

    def getResourceIdentifier(self, entity):
        '''Return a *resourceIdentifier* for supplied *entity*.'''
        if not isinstance(entity, Component):
            raise NotImplementedError('Cannot generate path for unsupported '
                                      'entity {0}'.format(entity))
        
        path = entity.getResourceIdentifier()
        if path is None:
            raise ValueError('Could not generate path for component that has '
                             'no original path.')
        
        return path
