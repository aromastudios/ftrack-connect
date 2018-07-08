# :coding: utf-8
# :copyright: Copyright (c) 2016 ftrack


import types
import logging

import ftrack
import ftrack_api
import ftrack_api.entity
import ftrack_api.accessor.base
import ftrack_api.structure.base
import ftrack_api.resource_identifier_transformer.base


logger = logging.getLogger('ftrack-location-compatibility')


class ProxyAccessor(ftrack_api.accessor.base.Accessor):
    '''Proxy accessor.'''

    def __init__(self, legacy_accessor):
        '''Instantiate proxy with *legacy_accessor*.'''
        self._legacy_accessor = legacy_accessor
        super(ProxyAccessor, self).__init__()

    def get_container(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.getContainer(
            resource_identifier, *args, **kwargs
        )

    def is_container(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.isContainer(
            resource_identifier, *args, **kwargs
        )

    def is_file(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.isFile(
            resource_identifier, *args, **kwargs
        )

    def is_sequence(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.isSequence(
            resource_identifier, *args, **kwargs
        )

    def list(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.list(
            resource_identifier, *args, **kwargs
        )

    def make_container(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.makeContainer(
            resource_identifier, *args, **kwargs
        )

    def open(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.open(
            resource_identifier, *args, **kwargs
        )

    def remove(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.remove(
            resource_identifier, *args, **kwargs
        )

    def exists(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.exists(
            resource_identifier, *args, **kwargs
        )

    def remove_container(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.removeContainer(
            resource_identifier, *args, **kwargs
        )

    def get_filesystem_path(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.getFilesystemPath(
            resource_identifier, *args, **kwargs
        )

    def get_url(self, resource_identifier, *args, **kwargs):
        '''Proxy method.'''
        return self._legacy_accessor.getUrl(
            resource_identifier, *args, **kwargs
        )


class ProxyStructure(ftrack_api.structure.base.Structure):
    '''Proxy structure.'''

    def __init__(self, legacy_structure):
        '''Instantiate proxy with *legacy_structure*.'''
        self._legacy_structure = legacy_structure
        super(ProxyStructure, self).__init__()

    def get_resource_identifier(self, entity, context=None):
        '''Return resource identifier from *entity*.'''
        if context and context.keys() != ['source_resource_identifier']:
            logger.warning(
                'Legacy api does not support passing context to a structure, '
                'and {0!r} will be dropped.'.format(context)
            )

        component = ftrack.Component(entity['id'])
        return self._legacy_structure.getResourceIdentifier(
            component
        )


class ProxyOriginStructure(ftrack_api.structure.base.Structure):
    '''Proxy origin structure.'''

    def __init__(self, legacy_structure):
        '''Instantiate proxy with *legacy_structure*.'''
        self._legacy_structure = legacy_structure
        super(ProxyOriginStructure, self).__init__()

    def get_resource_identifier(self, entity, context=None):
        '''Return resource identifier from *entity*.'''
        if context and context.keys() != ['source_resource_identifier']:
            logger.warning(
                'Legacy api does not support passing context to a structure, '
                'and {0!r} will be dropped.'.format(context)
            )

        component = ftrack.Component(entity['id'])

        if component.getResourceIdentifier():
            return self._legacy_structure.getResourceIdentifier(
                component
            )
        else:
            return context['source_resource_identifier']


class ProxyResourceIdentifierTransformer(
    ftrack_api.resource_identifier_transformer.base.ResourceIdentifierTransformer
):
    '''Proxy resource transformer.'''

    def __init__(self, legacy_resource_identifier_transformer, session):
        '''Instantiate proxy with *legacy_resource_identifier_transformer*.'''
        self._legacy_resource_identifier_transformer = (
            legacy_resource_identifier_transformer
        )
        super(ProxyResourceIdentifierTransformer, self).__init__(session)

    def encode(self, resource_identifier, context=None):
        '''Proxy method.'''
        if context:
            # Shallow copy context.
            context = dict(context.items())

            if 'component' in context:
                context['component'] = ftrack.Component(
                    context['component']['id']
                )

        return self._legacy_resource_identifier_transformer.encode(
            resource_identifier, context
        )

    def decode(self, resource_identifier, context=None):
        '''Proxy method.'''
        if context:
            # Shallow copy context.
            context = dict(context.items())

            if 'component' in context:
                context['component'] = ftrack.Component(
                    context['component']['id']
                )

        return self._legacy_resource_identifier_transformer.decode(
            resource_identifier, context
        )


class ProxyLegacyLocationMixin(object):
    '''Proxy legacy location mixin.'''

    def get_resource_identifiers(self, components):
        '''Return resource identifiers for *components*.

        Raise :exc:`ftrack_api.exception.ComponentNotInLocationError` if any
        of the components are not present in this location.

        '''
        resource_identifiers = self._get_resource_identifiers(components)

        # Optionally decode resource identifier.
        if self.resource_identifier_transformer:
            for index, resource_identifier in enumerate(resource_identifiers):
                resource_identifiers[index] = (
                    self.resource_identifier_transformer.decode(
                        resource_identifier, {'component': components[index]}
                    )
                )

        return resource_identifiers

    def add_components(self, *args, **kwargs):
        '''Wrap add_components method with a commit.'''
        self.session.commit()
        original_method = types.MethodType(
            ftrack_api.entity.location.Location.add_components, self
        )
        return original_method(*args, **kwargs)


def register_locations(session):
    '''Register proxy locations.'''
    for location in session.query('select name from Location'):

        # The un-managed location in the ftrack-python-api does not translate
        # disks between operating systems and must therefore be proxied to the
        # legacy api to keep the same functionality.
        if (
            location.accessor and
            location['id'] is not ftrack_api.symbol.UNMANAGED_LOCATION_ID
        ):
            # Location already configured.
            continue

        legacy_location = ftrack.LOCATION_PLUGINS.get(location['name'])

        if legacy_location is None or not legacy_location.getAccessor():
            # Not configured in the legacy location either.
            continue

        if location['id'] is not ftrack_api.symbol.UNMANAGED_LOCATION_ID:
            logger.warning(
                u'Location {0!r} does not have a configured '
                u'accessor configured in {1!r}. Setting up proxy for legacy '
                u'api location. Consider rewriting this location to a '
                u'ftrack-python-api location.'.format(location['name'], session)
            )

        else:
            logger.info(
                u'Proxying {0!r} location to the legacy api in order to support'
                u'OS specific path translation.'.format(location['name'])
            )


        ftrack_api.mixin(
            location, ProxyLegacyLocationMixin,
            'ProxyLegacyLocation'
        )

        location.priority = legacy_location.getPriority()
        location.accessor = ProxyAccessor(legacy_location.getAccessor())

        if legacy_location.getResourceIdentifierTransformer():
                transformer = ProxyResourceIdentifierTransformer(
                    legacy_location.getResourceIdentifierTransformer(),
                    session
                )
                location.resource_identifier_transformer = transformer

        if location['id'] is not ftrack_api.symbol.UNMANAGED_LOCATION_ID:
            location.structure = ProxyStructure(legacy_location.getStructure())
        else:
            # The ftrack-python-api calls get_resource_identifier on the target
            # location even if it is a un-managed location. This is not
            # supported in the legacy api and must be handled with special
            # logic
            location.structure = ProxyOriginStructure(
                legacy_location.getStructure()
            )
