
from abc import ABCMeta, abstractmethod


class Structure(object):
    '''Structure plugin interface.
    
    A structure plugin should compute appropriate paths for data.
    
    '''

    __metaclass__ = ABCMeta

    def __init__(self, prefix=''):
        '''Initialise structure.'''
        self.prefix = prefix
        self.pathSeparator = '/'
        super(Structure, self).__init__()
    
    @abstractmethod
    def getResourceIdentifier(self, entity):
        '''Return a *resourceIdentifier* for supplied *entity*.'''

    def _getSequenceExpression(self, sequence):
        '''Return a sequence expression for *sequence* component.'''
        padding = sequence.getPadding()
        if padding:
            expression = '%0{0}d'.format(padding)
        else:
            expression = '%d'

        return expression
