# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import logging

import ftrack


class Action(object):
    '''Action base class.'''

    #: Set action identifier.
    identifier = None

    #: Set action label.
    label = None

    #: Action icon
    icon = None

    #: Action description
    description = None

    #: Action variant
    variant = None

    def __init__(self):
        '''Initialise action handler.'''
        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

        if self.label is None:
            raise ValueError('The action must be given a label.')

        if self.identifier is None:
            raise ValueError('The action must be given an identifier.')

    def register(self):
        '''Register action.'''
        ftrack.EVENT_HUB.subscribe(
            'topic=ftrack.action.discover',
            self.discover
        )

        ftrack.EVENT_HUB.subscribe(
            'topic=ftrack.action.launch and data.actionIdentifier={0}'.format(
                self.identifier
            ),
            self.launch
        )

    def discover(self, event):
        '''Return action config.'''
        return {
            'items': [{
                'actionIdentifier': self.identifier,
                'label': self.label,
                'icon': self.icon,
                'description': self.description,
                'variant': self.variant
            }]
        }

    def launch(self, event):
        '''Callback method for custom action.'''
        raise NotImplementedError()
