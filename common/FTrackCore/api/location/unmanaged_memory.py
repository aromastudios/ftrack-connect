# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

from .unmanaged import UnmanagedLocation
from .memory import MemoryLocation


class UnmanagedMemoryLocation(MemoryLocation, UnmanagedLocation):
    '''Represent memory based location for un-managed components.

    .. seealso::

        :py:class:`ftrack.MemoryLocation`
        :py:class:`ftrack.UnmanagedLocation`

    '''
