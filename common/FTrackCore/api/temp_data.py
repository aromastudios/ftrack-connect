# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import datetime

from .ftobject import FTObject
from .client import xmlServer


def createTempData(data, expiry=None):
    '''Create a :py:class:`ftrack.TempData` with *data*.

    *expiry* is optional and should be a datetime object. If no expiry
    is specified it will default to 1 hour from now.

    '''

    if not expiry:
        expiry = datetime.datetime.now() + datetime.timedelta(hours=1)

    data = {
        'type': 'tempdata',
        'data': data,
        'expiry': expiry
    }

    response = xmlServer.action('create', data)
    return TempData(dict=response)


class TempData(FTObject):
    '''Represent a temp object.'''

    _type = 'tempdata'
    _idkey = 'dataid'
