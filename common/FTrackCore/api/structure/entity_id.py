# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

from .base import Structure


class EntityIdStructure(Structure):
    '''Id pass-through structure.'''

    def getResourceIdentifier(self, entity):
        '''Return a *resourceIdentifier* for supplied *entity*.'''
        return entity.getId()
