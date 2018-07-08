# :coding: utf-8
# :copyright: Copyright (c) 2014 FTrack


class ResourceIdentifierTransformer(object):
    '''Transform resource identifiers.

    Provide ability to modify resource identifier before it is stored centrally
    (:py:meth:`encode`), or after it has been retrieved, but before it is used
    locally (:py:meth:`decode`).

    For example, you might want to decompose paths into a set of key, value
    pairs to store centrally and then compose a path from those values when
    reading back.

    .. note::

        This is separate from any transformations an
        :py:class:`ftrack.Accessor` may perform and is targeted towards common
        transformations.

    '''

    def encode(self, resourceIdentifier, context=None):
        '''Return encoded *resourceIdentifier* for storing centrally.

        A mapping of *context* values may be supplied to guide the
        transformation.

        '''
        return resourceIdentifier

    def decode(self, resourceIdentifier, context=None):
        '''Return decoded *resourceIdentifier* for use locally.

        A mapping of *context* values may be supplied to guide the
        transformation.

        '''
        return resourceIdentifier
