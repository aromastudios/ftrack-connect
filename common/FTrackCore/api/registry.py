
import os
import uuid
import imp
import collections


class Registry(collections.MutableSet):
    '''Registry for plugins.'''
    
    def __init__(self, paths=None):
        '''Initialise plugin registry.'''
        self._set = set()
        self.paths = paths or []
        super(Registry, self).__init__()
    
    def discover(self, **kw):
        '''Find and load plugins in search paths.

        Each discovered module should implement a register function that
        accepts this registry and additional *kw*. The function should add
        appropriate instances to the registry::
        
            def register(registry, **kw):
                plugin = MyPlugin(name='plugin.name')
                registry.add(plugin)
        
        .. note::
        
            Each instance must have a 'getName' method that will identify
            the plugin.
            
        '''
        for path in self.paths:
            # Ignore empty paths that could resolve to current directory.
            path = path.strip()
            if not path:
                continue

            for base, directories, filenames in os.walk(path):
                for filename in filenames:
                    name, extension = os.path.splitext(filename)
                    if extension != '.py':
                        continue
    
                    modulePath = os.path.join(base, filename)
                    uniqueName = uuid.uuid4().hex

                    try:
                        module = imp.load_source(uniqueName, modulePath)
                    except Exception as error:
                        print(
                            'Warning: Failed to load plugin from "{0}": {1}'
                            .format(modulePath, error)
                        )
                        continue

                    try:
                        module.register
                    except AttributeError:
                        print(
                            'Warning: Failed to load plugin that did not '
                            'define a "register" function at the module level: '
                            '{0}'.format(modulePath)
                        )
                    else:
                        module.register(self, **kw)

    def get(self, name):
        '''Retrieve a discovered plugin by *name*.
        
        Return None if no matching plugin found.
        
        '''
        for plugin in self:
            if plugin.getName() == name:
                return plugin
        
        return None
    
    def add(self, plugin):
        '''Add *plugin*.'''
        self._set.add(plugin)
  
    def discard(self, plugin):
        '''Remove *plugin*.'''
        self._set.discard(plugin)
    
    def __iter__(self):
        '''Return iterator over plugins.'''
        return iter(self._set)
    
    def __len__(self):
        '''Return number of plugins in registry.'''
        return len(self._set)
    
    def __contains__(self, plugin):
        '''Return whether registry contains *plugin*.'''
        return plugin in self._set

