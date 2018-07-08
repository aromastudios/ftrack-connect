# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

from .ftobject import FTObject
from .ftlist import FTList
from .review_session_object_status import ReviewSessionObjectStatus
from .client import (xmlServer, Noteable)


class ReviewSessionObject(FTObject, Noteable):
    '''Represent review session object.'''

    _type = 'reviewsessionobject'

    def _resolveCloudUrl(self):
        '''Return resolved cloud url if available in ftrack.review location.

        If object not available in ftrack.review None will be returned.

        '''
        data = {
            'reviewSessionObjectId': self.getId()
        }

        response = xmlServer.action(
            'review_session_object_resolveCloudUrl', data
        )

        return response

    def getStatuses(self):
        '''Return list of :py:class:`ftrack.ReviewSessionObjectStatus`.

        If the list is empty no invitees has voted.

        '''

        data = {
            'reviewSessionObjectId': self.getId(),
            'type': 'reviewsessionobjectstatuses'
        }

        response = xmlServer.action(
            'get', data
        )

        return FTList([ReviewSessionObjectStatus], response)

    def setStatus(self, status, invitee):
        '''Set *status* on object for *invitee*.

        *invitee* should be of type :py:class:`ftrack.ReviewSessionInvitee`.

        '''

        data = {
            'reviewSessionObjectId': self.getId(),
            'inviteeId': invitee.getId(),
            'status': status
        }

        response = xmlServer.action(
            'review_session_object_setStatus', data
        )

        return ReviewSessionObjectStatus(dict=response)
