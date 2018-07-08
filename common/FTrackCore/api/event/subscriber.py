# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

from .subscription import Subscription as _Subscription


class Subscriber(object):
    '''Represent event subscriber.'''

    def __init__(self, subscription, callback, metadata, priority):
        '''Initialise subscriber.'''
        self.subscription = _Subscription(subscription)
        self.callback = callback
        self.metadata = metadata
        self.priority = priority
        self.active = False

    def __str__(self):
        '''Return string representation.'''
        return '<{0} metadata={1} subscription={2}>'.format(
            self.__class__.__name__, self.metadata, self.subscription
        )

    def interestedIn(self, event):
        '''Return whether subscriber interested in *event*.'''
        if not self.active:
            return False

        return self.subscription.includes(event)
