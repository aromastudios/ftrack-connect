class Metable(object):
    """
    Abstract class inherited by objects to enable meta functionality.
    """  
    
    def setMeta(self,key,value=None):
        """
        Set metadata on an object. This method can be used to store arbitrary data on an object.
        The data is stored in key/value pairs where key and value are strings.
        
        This method also accepts a ``dict`` with key/value pairs 
        
        :param key: A ``string`` representing the key or a ``dict`` with key/value pairs.
        :param value: A ``string`` representing the value or None if key is a ``dict``.
        """  
        data = {'type':'meta','object':self._type,'id':self.getId(),'key':key,'value':value}
        response = self.xmlServer.action('set',data)
        return True

    def getMeta(self,key=None):
        """
        Get metadata from an object. This method can be used to retrive meta data from an object.
        The data is stored in key/value pairs where key and value are strings.
        
        This method can also be used without any arguments to retrive a ``dict`` with all metadata
        key/value pairs attached to this object.
        
        :param key: A ``string`` representing the key or ``None`` to retrive all key/value pairs on this object.
        :rtype: ``string`` or ``dict``
        """          
        if 'meta' in self.dict and key != None:
            for meta in self.dict['meta']:
                if meta['variable'] == key:
                    return meta['value']
            from ftrackerror import FTrackError
            raise FTrackError("Meta ("+key+") not found on this object")
        else:
            data = {'type':'meta','id':self.getId(),'key':key}
            response = self.xmlServer.action('get',data)
            return response

    def metaKeys(self):
        '''Return keys accessible using getMeta/setMeta methods.'''
        return sorted(self.getMeta(None).keys())


import datetime

class FTObject(object):
    """
    Base object, should never be used directly
    """
    _idkey = 'id'
    
    def __init__(self,id=None,dict=None,eagerload=None):
        if eagerload is None:
            eagerload = []
            
        self._unsetValues = []
        
        if (id == None and dict == None):
            from ftrackerror import FTrackError
            raise FTrackError("Id or dict must be supplied when creating object")
        try:
            self._type
        except NameError:
            from ftrackerror import FTrackError
            raise FTrackError("Object type must be defined")
            
        self.dict = dict
        
        #Get object if created from id
        if (id != None):
            #from cache?
            
            #else
            data = {'type':self._type,'id':id,'eagerload':eagerload}
            self.dict = self.xmlServer.action('get',data)

        self.attributes = None
        
        self.isTemp = 'tempid' in self.dict
        
        if self.isTemp:
            self.xmlServer.addTempObject(self)
            self.unsavedAttributes = {}
        

    def get(self,key):
        
        try:
            #Check if xmlrpclib.DateTime, then convert to datetime.datetime
            if (str(self.dict[key].__class__).endswith('xmlrpclib.DateTime')):
                import datetime,time
                return datetime.datetime(*time.strptime(str(self.dict[key]),'%Y%m%dT%H:%M:%S')[0:6])
            
            return self.dict[key]
        except:
            
            return self._getAttributeValue(key)


    def set(self,key,value=None):
        
        values = {}
        
        #convert to dict
        if isinstance(key,dict):
            values = key
        else:
            values[key] = value
        
        #does not yet exist?
        if self.isTemp:
            self.unsavedAttributes.update(values)
            return True
        
        
        data = {'type':'set','object':self._type,'id':self.getId(),'values':values}
        response = self.xmlServer.action('set',data)

        
        #Reload after successfull set?
        if type(response).__name__ == 'dict':
            self.__init__(dict=response)

        return True
    
    def _getAttributeValue(self,key):
        if not self.attributes:
            self._loadAttributes()
            
        for attribute in self.attributes:
            if attribute.get('key') == key:
                return attribute.get('value')
            
        from ftrackerror import FTrackError
        raise FTrackError("Value ("+key+") not found on this object")
        
    def _loadAttributes(self):
        try:
            data = {'entityType':self._type,'entityId':self.getId(),'type':'attributes'}
            self.attributes = self.xmlServer.action('get',data)
        except:
            from ftrackerror import FTrackError
            raise FTrackError("Server error when loading attribute")

    def _setUnsetValues(self):
        for item in self._unsetValues:
            self.set(item['key'],item['value'])
        self._unsetValues = []
            

    def __repr__(self):
        return "<%s('%s')>" % (self._type,self.dict)





    #May not always work
    def getId(self):
        return self.get(self._idkey)




    def delete(self):
        data = {'entityType':self._type,'entityId':self.getId(),'type':'delete'}
        response = self.xmlServer.action('set',data)

        return response
    
    def keys(self):
        '''Return keys accessible using get/set methods.'''
        if self.attributes is None:
            self._loadAttributes()
        
        combinedKeys = set(self.dict.keys())
        for attribute in self.attributes:
            key = attribute.get('key')
            if key is not None:
                combinedKeys.add(key)
        
        return sorted(list(combinedKeys))
    
    def getEntityRef(self):
        return "ftrack://" + self.getId() + "?entityType=" + self._type
    
    
