# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

from .ftobject import FTObject
from .ftlist import FTList
from .client import xmlServer, User


def createTimelog(duration, start=None, userId=None, contextId=None, name=None,
                  comment=None, timeZoneOffset=None):
    '''Create a timelog with *duration* in seconds.

    *start* is the datetime for the timelog and will default to now.

    *userId* will default to the current user but can be overriden.

    *contextId* is an id of a task or project this timelog should be created
    for.

    *name* is optional but should be included if this timelog does not have a
    context or a ValueError will be raised.

    *comment* is optional.

    *timeZoneOffset* is optional and only recommended if time zone support is
    enabled on the server. It can be used to manually set the offset from UTC.
    If not set the offset will be automatically calculated based on the API
    user.

    '''
    if contextId is None and name is None:
        raise ValueError('Name must be set if contextId is None.')

    data = {
        'type': 'timelog',
        'start': start,
        'duration': duration,
        'user_id': userId,
        'context_id': contextId,
        'name': name,
        'comment': comment,
        'time_zone_offset': timeZoneOffset
    }

    response = xmlServer.action('create', data)
    return Timelog(dict=response)


def _getTimelogs(entityId, entityType, start, end, includeChildren=False):
    '''Return timelogs.

    *entityId* and *entityType* identifies the entity for which timelogs should
    be queried.

    *start* and *end* are datetimes for filtering that timelogs.

    If *includeChildren* is set, also retrieve any timelogs reported against 
    descendants of the entity.

    '''
    data = {
        'entityId': entityId,
        'entityType': entityType,
        'start': start,
        'end': end,
        'includeChildren': includeChildren
    }

    response = xmlServer.action('getTimelogs', data)
    items = FTList([Timelog], response)

    return items


class Timelog(FTObject):
    '''Represent a timelog.'''

    _type = 'timelog'

    def getUser(self):
        '''Return timelog user.'''
        return User(self.get('user_id'))
