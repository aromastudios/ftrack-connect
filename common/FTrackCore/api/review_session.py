# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

from .ftobject import FTObject
from .ftlist import FTList
from .client import xmlServer
from .review_session_object import ReviewSessionObject
from .review_session_invitee import ReviewSessionInvitee


def getReviewSessions(projectId):
    '''Return all review sessions on *projectId*.'''

    response = xmlServer.action(
        'getReviewSessions', {
            'project_id': projectId
        }
    )

    return FTList(ReviewSession, response)


def createReviewSession(name, description, projectId):
    '''Create review session on *projectId* with *name* and *description*.'''

    data = {
        'type': 'reviewsession',
        'description': description,
        'name': name,
        'project_id': projectId
    }
    response = xmlServer.action('create', data)

    return ReviewSession(dict=response)


class ReviewSession(FTObject):
    '''Represent review session.'''

    _type = 'reviewsession'

    def reviewSessionObjects(self):
        '''Return a `ftrack.FTList` of `ftrack.ReviewSessionObject`.

        .. warning::
            Deprecated method, use :meth:`ftrack.ReviewSession.getObjects`.

        '''
        return self.getObjects()

    def getObjects(self):
        '''Return a `ftrack.FTList` of `ftrack.ReviewSessionObject`.'''
        data = {
            'type': 'reviewsessionobjects',
            'id': self.getId()
        }

        response = xmlServer.action('get', data)
        items = FTList([ReviewSessionObject], response)

        return items

    def createObject(
        self, assetVersion, name='', description='', version='',
        syncAssetVersionData=False
    ):
        '''Create a new review session object on review session.

        *assetVersion* should be an instance of :py:class:`ftrack.AssetVersion`.

        Optionally specify a *name*, *description*, *version* number which will
        be visible when viewing the review session in the web interface.

        If *syncAssetVersionData* is set to `True` the name, description and
        version will be set based on the assetVersion.

        '''

        data = dict(
            name=name, description=description, version=version,
            version_id=assetVersion.getId(),
            review_session_id=self.getId(),
            syncAssetVersionData=syncAssetVersionData,
            type='reviewsessionobject'
        )

        response = xmlServer.action('create', data)

        return ReviewSessionObject(dict=response)

    def getInvitees(self):
        '''Return all invitees on review session.'''
        data = dict(
            type='reviewsessioninvitees',
            id=self.getId()
        )

        response = xmlServer.action('get', data)
        items = FTList([ReviewSessionInvitee], response)

        return items

    def createInvitee(self, email, name):
        '''Create a new invitee with *email* and *name* on review session.'''
        data = dict(
            name=name,
            email=email,
            review_session_id=self.getId(),
            type='reviewsessioninvitee'
        )

        response = xmlServer.action('create', data)

        return ReviewSessionInvitee(dict=response)
