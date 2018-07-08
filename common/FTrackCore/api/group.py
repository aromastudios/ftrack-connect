# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

from .ftobject import FTObject
from .ftlist import FTList


def getGroups():
    '''Return all top level groups.'''
    from .client import xmlServer

    response = xmlServer.action(
        'getGroups', {}
    )

    return FTList(Group, response)


class Group(FTObject):
    '''Represent a group.'''

    _type = 'group'

    def getSubgroups(self):
        '''Return list of subgroups.'''
        # Local import to avoid circular.
        from .client import xmlServer

        response = xmlServer.action(
            'getSubgroups', {'id': self.getId()}
        )

        return FTList(Group, response)

    def getMembers(self):
        '''Return list of users in the group.'''
        # Local import to avoid circular.
        from .client import xmlServer, User

        response = xmlServer.action(
            'getMembers', {'id': self.getId()}
        )

        return FTList(User, response)
